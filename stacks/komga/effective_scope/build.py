"""Compile reviewed observer sources into a new private packet; never Docker or live reads."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import types

HERE = Path(__file__).parent
PRODUCTION = ('KomgaClasspathMetadata.java', 'KomgaEffectiveScope.java', 'TargetEffectiveScopeCase.java')
PARENT_CLASSES = ('KomgaClasspathMetadata.class', 'KomgaEffectiveScope.class', 'KomgaEffectiveScope$Held.class')
TARGET_CLASSES = (*PARENT_CLASSES, 'TargetEffectiveScopeCase.class', 'TargetEffectiveScopeCase$Observation.class')
SUPPLIERS = ('owned.py', 'KomgaEffectiveScope.class', 'KomgaEffectiveScope$Held.class', 'KomgaEffectiveScope.java', 'KomgaClasspathMetadata.class', 'original-public-dependency-facts.json')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def sources():
    document = json.loads((HERE / 'sources.json').read_bytes())
    assert set(document) == {'version', 'files', 'compiled', 'authority'}, 'source-manifest-schema'
    assert document['version'] == 1 and document['authority'] is False, 'source-manifest-no-authority'
    result = {}
    for name, pin in document['files'].items():
        assert re.fullmatch(r'[A-Za-z0-9_.-]+', name) and re.fullmatch('[a-f0-9]{64}', pin), 'source-name'
        p = HERE / name
        before = p.lstat()
        assert stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= 1048576, 'source-file'
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            raw = os.read(fd, 1048577)
            signature = lambda z: (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns, z.st_mode, z.st_uid, z.st_gid, z.st_nlink)
            assert signature(os.fstat(fd)) == signature(p.lstat()) == signature(before) and len(raw) == before.st_size and sha(raw) == pin, 'source-pin'
            result[name] = raw
        finally:
            os.close(fd)
    return document, result


def build(output, java_home):
    assert os.geteuid() != 0, 'compile-as-unprivileged-user'
    output = Path(output)
    assert output.is_absolute() and not os.path.lexists(output), 'fresh-output'
    toolchain = Path(java_home).resolve(strict=True)
    javac = toolchain / 'bin/javac'
    version = subprocess.run([str(javac), '-version'], capture_output=True, check=True, timeout=15).stdout.decode()
    assert re.fullmatch(r'javac 21(?:[. +\-][^\n]*)?\n?', version), 'reviewed-jdk-21'
    manifest, raw = sources()
    assert set(manifest['compiled']) == set(TARGET_CLASSES), 'exact-compiled-inventory'
    clean_env = {k: v for k, v in os.environ.items() if k not in {'JAVA_TOOL_OPTIONS', 'JDK_JAVA_OPTIONS', '_JAVA_OPTIONS'}}
    with tempfile.TemporaryDirectory(prefix='komga-effective-build-') as directory:
        work = Path(directory)
        for name in PRODUCTION:
            (work / name).write_bytes(raw[name])
        subprocess.run([str(javac), '--release', '17', '-d', str(work), *[str(work / n) for n in PRODUCTION]], env=clean_env, capture_output=True, check=True, timeout=60)
        generated = {p.name: p.read_bytes() for p in work.glob('*.class')}
        assert set(generated) == set(TARGET_CLASSES) and {n: sha(b) for n, b in generated.items()} == manifest['compiled'], 'compiled-source-closure'
        module = types.ModuleType('_komga_build_output')
        module.__file__ = str(HERE / 'owned.py')
        exec(compile(raw['owned.py'], str(HERE / 'owned.py'), 'exec'), module.__dict__)
        class Output(module.JarOutput):
            NAMES = {*raw, *generated, 'artifacts.json'}
        out = Output(output)
        try:
            for name, value in {**raw, **generated}.items():
                out.write(name, value)
            refs = {name: dict(path=str(output / name), sha256=sha((output / name).read_bytes())) for name in ('parent.py', *PARENT_CLASSES)}
            out.close()
            result = dict(kind='compiled-komga-effective-source-artifacts-v1', sources=refs,
                          producer=refs['KomgaEffectiveScope.class'], parent=refs['parent.py'],
                          parent_classes=list(PARENT_CLASSES), target_classes=list(TARGET_CLASSES),
                          supplier_pins={n: sha((raw | generated)[n]) for n in SUPPLIERS},
                          backup_verified=False, publication_acceptance=False, mutation_authority=False,
                          scope_observation_verified=False, compiled_source_verified=True)
            out.write('artifacts.json', (json.dumps(result, indent=2) + '\n').encode())
            out.close()
        finally:
            out.release()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--java-home', required=True)
    args = parser.parse_args()
    result = build(args.output, args.java_home)
    print(json.dumps(dict(compiled_source_verified=result['compiled_source_verified'], scope_observation_verified=False, mutation_authority=False)))


if __name__ == '__main__':
    main()
