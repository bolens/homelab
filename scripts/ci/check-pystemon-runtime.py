#!/usr/bin/env python3
"""Qualify the private collector without starting AIL, screen, or any collection."""
import argparse
import importlib.util
import json
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STACK = ROOT / 'stacks/ail-framework'
SPEC = importlib.util.spec_from_file_location('pystemon_runtime', STACK / 'install-pystemon-runtime.py')
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)


def qualify(require_jammy):
    os_release = Path('/etc/os-release').read_text()
    jammy = bool(re.search(r'^ID=ubuntu$', os_release, re.MULTILINE) and
                 re.search(r'^VERSION_ID="22.04"$', os_release, re.MULTILINE))
    if require_jammy and not jammy:
        raise RuntimeError('this gate requires the AIL Ubuntu 22.04 native ABI')
    contract = json.loads((STACK / 'pystemon-runtime.json').read_text())
    with tempfile.TemporaryDirectory(prefix='ail-pystemon-check-') as tmp:
        work = Path(tmp)
        source_archive = work / 'pystemon.tar.gz'
        RUNTIME.download(contract['pystemon'], source_archive)
        RUNTIME.extract(source_archive, work / 'source')
        source = work / 'source' / ('pystemon-' + contract['pystemon']['commit'])
        launcher = work / 'LAUNCH.sh'
        RUNTIME.download(contract['launcher'], launcher)
        original = launcher.read_text()
        prefix = work / 'runtime'
        args = (STACK / 'pystemon-runtime.json', STACK / 'requirements-pystemon.txt',
                source, launcher, prefix)
        RUNTIME.install(*args)
        before = RUNTIME.sha(prefix / 'inputs.json')
        RUNTIME.install(*args)
        assert before == RUNTIME.sha(prefix / 'inputs.json')
        tamper = prefix / 'python/lib/python3.13/__pycache__/fixture.cpython-313.pyc'
        tamper.parent.mkdir(exist_ok=True)
        tamper.write_bytes(b'changed bytecode')
        try:
            RUNTIME.install(*args)
        except ValueError:
            pass
        else:
            raise AssertionError('modified runtime was accepted')
        tamper.unlink()
        assert RUNTIME.IMPORTER in launcher.read_text()
        assert launcher.read_text().replace(str(prefix / 'venv/bin/python'), '${ENV_PY}') == original
        shell = ('''screen() { printf '%s\\0' "$@"; }; '''
                 'AIL_BIN=/fixture/AIL/bin; AIL_HOME=/fixture/AIL; '
                 'ENV_PY=/fixture/AIL/AILENV/bin/python;\n' +
                 RUNTIME.IMPORTER + '\n' +
                 RUNTIME.COLLECTOR.replace('${ENV_PY}', str(prefix / 'venv/bin/python')))
        captured = subprocess.run(['bash', '-c', shell], env=RUNTIME.clean_env(work),
                                  capture_output=True, check=True, timeout=10).stdout.split(b'\0')
        assert captured == [b'-S', b'Feeder_Pystemon', b'-X', b'screen', b'-t',
                            b'Pystemon_feeder', b'bash', b'-c',
                            b'cd /fixture/AIL/bin; /fixture/AIL/AILENV/bin/python ./importer/PystemonImporter.py; read x',
                            b'-S', b'Feeder_Pystemon', b'-X', b'screen', b'-t',
                            b'Pystemon', b'bash', b'-c',
                            ('cd /fixture/AIL/../pystemon; ' + str(prefix / 'venv/bin/python') +
                             ' ./pystemon.py; read x').encode(), b'']
        python = prefix / 'venv/bin/python'
        smoke = '''import json, platform, ssl, yaml, requests, redis, charset_normalizer, soupsieve
from bs4 import BeautifulSoup
from lxml import etree
assert etree.fromstring(b"<root><node/></root>").find("node") is not None
assert platform.python_version() == "3.13.18"
assert soupsieve.__version__ == "4.0.1"
assert yaml.__with_libyaml__
assert len(BeautifulSoup("<main><section><p>a</p><p>b</p></section></main>", "html.parser").select("main section p")) == 2
print(json.dumps({"python":platform.python_version(), "openssl":ssl.OPENSSL_VERSION,
                  "soupsieve":soupsieve.__version__, "nativeYaml":yaml.__with_libyaml__}))'''
        RUNTIME.run([python, '-I', '-B', '-c', smoke], work)
        # --help and optparse's error path return before configuration/main/threads.
        for argv, expected in ((['--help'], 0), (['--not-a-pystemon-option'], 2),
                               (['--config', '/fixture/config with spaces.yaml', '--help'], 0)):
            result = subprocess.run([str(python), '-B', str(source / 'pystemon.py'), *argv],
                                    cwd=source, env=RUNTIME.clean_env(work),
                                    capture_output=True, text=True, timeout=30, check=False)
            if result.returncode != expected or 'Traceback' in result.stderr:
                raise RuntimeError('pinned Pystemon entrypoint contract failed: ' + result.stderr[-2000:])
            assert ('Usage:' in result.stdout) if expected == 0 else ('no such option' in result.stderr)
        # Scan the actual interpreter AND native wheels. Jammy provides glibc 2.35.
        elf_count = 0
        max_glibc = (0, 0)
        for path in prefix.rglob('*'):
            if not path.is_file() or path.is_symlink():
                continue
            with path.open('rb') as handle:
                if handle.read(4) != b'\x7fELF':
                    continue
            elf_count += 1
            symbols = subprocess.run(['readelf', '--version-info', str(path)], check=True,
                                     capture_output=True, text=True, timeout=30).stdout
            versions = [(int(a), int(b)) for a, b in re.findall(r'GLIBC_(\d+)\.(\d+)', symbols)]
            max_glibc = max([max_glibc, *versions])
        assert elf_count >= 10 and max_glibc <= (2, 35), (elf_count, max_glibc)
        # Successful controlled imports/entrypoints must leave the full baseline intact.
        RUNTIME.install(*args)
        assert before == RUNTIME.sha(prefix / 'inputs.json')
        print('PYSTEMON_RUNTIME_RESULT ' + json.dumps({
            'jammyExecuted': jammy, 'architecture': RUNTIME.platform.machine(),
            'python': contract['pythonVersion'], 'sourcePythonFiles': len(contract['pystemon']['pythonFiles']),
            'entrypointCases': 3, 'repeatIdentical': True, 'elfObjects': elf_count,
            'maxRequiredGlibc': '.'.join(map(str, max_glibc)), 'collectorStarted': False,
            'fullAilImageBuildOrStartupQualified': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-jammy', action='store_true')
    qualify(parser.parse_args().require_jammy)
