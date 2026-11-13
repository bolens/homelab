#!/usr/bin/env python3
"""Build only Pystemon's private runtime; never launch collectors or change AILENV."""
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath

IMPORTER = 'screen -S "Feeder_Pystemon" -X screen -t "Pystemon_feeder" bash -c "cd ${AIL_BIN}; ${ENV_PY} ./importer/PystemonImporter.py; read x"'
COLLECTOR = 'screen -S "Feeder_Pystemon" -X screen -t "Pystemon" bash -c "cd ${AIL_HOME}/../pystemon; ${ENV_PY} ./pystemon.py; read x"'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def download(spec, target):
    """Accept only the selected public HTTPS artifact, capped before extraction."""
    if not spec['url'].startswith(('https://github.com/', 'https://raw.githubusercontent.com/',
                                   'https://codeload.github.com/')):
        raise ValueError('unexpected supplier origin')
    with urllib.request.urlopen(spec['url'], timeout=60) as response, target.open('xb') as output:
        total = 0
        while block := response.read(1024 * 1024):
            total += len(block)
            if total > 64 * 1024 * 1024:
                raise ValueError('supplier archive too large')
            output.write(block)
    if sha(target) != spec['sha256']:
        raise ValueError('supplier hash mismatch')


def safe_data_filter(member, destination):
    """Keep data-filter bounds with parent-relative symlinks on Jammy Python 3.10."""
    if not member.issym():
        return tarfile.data_filter(member, destination)
    if PurePosixPath(member.name) == PurePosixPath('.') or os.path.isabs(member.linkname):
        raise ValueError('absolute link or destination-root replacement')
    # Jammy's data_filter incorrectly joins symlink targets to the archive root.
    # tar_filter still checks the member pathname. Supply the correct link bound
    # and the same ownership/mode stripping that data_filter applies to symlinks.
    filtered = tarfile.tar_filter(member, destination)
    root = Path(destination).resolve()
    parent = (root / filtered.name).parent.resolve()
    target = (parent / filtered.linkname).resolve()
    if not parent.is_relative_to(root) or not target.is_relative_to(root):
        raise ValueError('symlink target escapes extraction directory')
    return filtered.replace(mode=None, uid=None, gid=None, uname=None, gname=None, deep=False)


def extract(archive, target):
    """Validate the whole archive before writing. Preserve only internal symlinks."""
    if not hasattr(tarfile, 'data_filter'):
        raise RuntimeError('Python tarfile.data_filter is required')
    with tarfile.open(archive) as source:
        members = source.getmembers()
        names = set()
        size = 0
        for member in members:
            if (PurePosixPath(member.name).is_absolute() or '..' in PurePosixPath(member.name).parts
                    or member.name in names or member.islnk() or not (
                    member.isfile() or member.isdir() or member.issym())):
                raise ValueError('duplicate or unsupported archive member')
            names.add(member.name)
            size += member.size
            if size > 512 * 1024 * 1024:
                raise ValueError('expanded supplier too large')
            safe_data_filter(member, str(target))
        source.extractall(target, members=members, filter=safe_data_filter)
        # Later aliases can change an earlier link's resolution. Admit the final
        # namespace too before the caller executes anything from this prefix.
        for member in members:
            if member.issym():
                safe_data_filter(member, str(target))


def verify_source(source, contract):
    actual = {p.relative_to(source).as_posix(): sha(p) for p in source.rglob('*.py')
              if '.git' not in p.relative_to(source).parts}
    if actual != contract['pythonFiles'] or any(p.is_symlink() for p in source.rglob('*.py')):
        raise ValueError('Pystemon source census changed')


def launcher_text(text, contract, prefix):
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+', str(prefix)):
        raise ValueError('unsafe runtime path')
    replacement = COLLECTOR.replace('${ENV_PY}', str(prefix / 'venv/bin/python'))
    if replacement in text:
        if text.count(replacement) != 1:
            raise ValueError('duplicate patched launcher')
        original = text.replace(replacement, COLLECTOR)
    else:
        original = text
    if hashlib.sha256(original.encode()).hexdigest() != contract['sha256']:
        raise ValueError('AIL launcher source changed')
    if original.count(IMPORTER) != 1 or original.count(COLLECTOR) != 1:
        raise ValueError('launcher commands changed')
    return original.replace(COLLECTOR, replacement)


def clean_env(home):
    return {'PATH': '/usr/bin:/bin', 'HOME': str(home), 'LANG': 'C.UTF-8',
            'PYTHONDONTWRITEBYTECODE': '1', 'PIP_CONFIG_FILE': os.devnull}


def run(argv, home, **kwargs):
    subprocess.run([str(x) for x in argv], env=clean_env(home), check=True, timeout=600, **kwargs)


def runtime_files(prefix):
    return {p.relative_to(prefix).as_posix(): (
        {'link': os.readlink(p)} if p.is_symlink() else {'sha256': sha(p)})
        for p in prefix.rglob('*') if (p.is_file() or p.is_symlink())
        and p != prefix / 'inputs.json'}


def install(manifest, requirements, source, launcher, prefix):
    contract = json.loads(manifest.read_text())
    verify_source(source, contract['pystemon'])
    patched = launcher_text(launcher.read_text(), contract['launcher'], prefix)
    identity = {'manifest': sha(manifest), 'requirements': sha(requirements),
                'installer': sha(Path(__file__)), 'prefix': str(prefix)}
    marker = prefix / 'inputs.json'
    if prefix.exists():
        if prefix.is_symlink() or not marker.is_file():
            raise ValueError('existing runtime is not owned by this installer')
        state = json.loads(marker.read_text())
        if state['inputs'] != identity or state['files'] != runtime_files(prefix):
            raise ValueError('existing runtime inputs or bytes changed')
        run([prefix / 'venv/bin/python', '-I', '-B', '-m', 'pip', 'check'], prefix)
        launcher.write_text(patched)
        return
    prefix.parent.mkdir(parents=True, exist_ok=True)
    prefix.mkdir(mode=0o755)
    try:
        with tempfile.TemporaryDirectory(prefix='pystemon-build-') as tmp:
            work = Path(tmp)
            archive = work / 'python.tar.gz'
            machine = platform.machine()
            if platform.system() != 'Linux' or machine not in contract['python']:
                raise ValueError('unsupported private Python architecture')
            download(contract['python'][machine], archive)
            extract(archive, prefix)
            python = prefix / 'python/bin/python3'
            run([python, '-I', '-B', '-c',
                 f'import platform; assert platform.python_version() == {contract["pythonVersion"]!r}'], work)
            run([python, '-I', '-B', '-m', 'venv', '--copies', '--without-pip', prefix / 'venv'], work)
            private = prefix / 'venv/bin/python'
            # ensurepip's bundled bytecode is part of the checked baseline too.
            run([private, '-I', '-B', '-m', 'ensurepip'], work)
            run([private, '-I', '-B', '-m', 'pip', '--isolated', 'install',
                 '--disable-pip-version-check', '--no-cache-dir', '--no-compile', '--only-binary=:all:',
                 '--require-hashes', '--index-url', 'https://pypi.org/simple', '-r', requirements], work)
            run([private, '-I', '-B', '-m', 'pip', 'check'], work)
        marker.write_text(json.dumps({'inputs': identity, 'files': runtime_files(prefix)},
                                     sort_keys=True) + '\n')
        launcher.write_text(patched)
    except BaseException:
        shutil.rmtree(prefix)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--requirements', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--launcher', type=Path, required=True)
    parser.add_argument('--prefix', type=Path, default=Path('/opt/pystemon-runtime'))
    args = parser.parse_args()
    install(args.manifest.resolve(), args.requirements.resolve(), args.source.resolve(),
            args.launcher.resolve(), args.prefix.absolute())


if __name__ == '__main__':
    main()
