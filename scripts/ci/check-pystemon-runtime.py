#!/usr/bin/env python3
"""Qualify the private collector without starting AIL, screen, or any collection."""
import argparse
import importlib.util
import json
import re
import socketserver
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
STACK = ROOT / 'stacks/ail-framework'
SPEC = importlib.util.spec_from_file_location('pystemon_runtime', STACK / 'install-pystemon-runtime.py')
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)


def redis_wire_check(source, expect_redis8_rejection=False):
    """Exercise the pinned storage against a small Redis 5 RESP2 wire fixture."""
    contract = json.loads((STACK / 'pystemon-runtime.json').read_text())
    RUNTIME.verify_source(source, contract['pystemon'])
    sys.path.insert(0, str(source))
    import redis
    from pystemon.storage.redisstorage import RedisStorage

    class Redis5Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.request.settimeout(10)
            while header := self.rfile.readline(8192):
                assert header.startswith(b'*')
                count = int(header[1:])
                assert 0 < count <= 32
                command = []
                for _ in range(count):
                    size_header = self.rfile.readline(8192)
                    assert size_header.startswith(b'$')
                    size = int(size_header[1:])
                    assert 0 <= size <= 65536
                    value = self.rfile.read(size)
                    assert len(value) == size and self.rfile.read(2) == b'\r\n'
                    command.append(value)
                with self.server.lock:
                    self.server.commands.append(command)
                name = command[0].upper()
                if name == b'HELLO':
                    response = b"-ERR unknown command 'HELLO'\r\n"
                elif name == b'CLIENT':
                    assert command[1].upper() == b'SETINFO'
                    response = b"-ERR Unknown subcommand or wrong number of arguments for 'SETINFO'\r\n"
                elif name == b'SELECT':
                    assert command[1:] == [b'10']
                    response = b'+OK\r\n'
                elif name == b'PING':
                    assert len(command) == 1
                    response = b'+PONG\r\n'
                elif name == b'LPUSH':
                    assert len(command) == 3 and command[1] == b'pastes'
                    response = b':1\r\n'
                else:
                    raise AssertionError('unexpected fixture command: ' + repr(name))
                self.wfile.write(response)
                self.wfile.flush()

    class Redis5Server(socketserver.ThreadingTCPServer):
        def handle_error(self, _request, _client_address):
            with self.lock:
                self.errors.append(repr(sys.exc_info()[1]))

    # Binding/listening happens before the client runs; no readiness sleeps or port probe.
    server = Redis5Server(('127.0.0.1', 0), Redis5Handler)
    server.commands, server.errors, server.lock = [], [], threading.Lock()
    worker = threading.Thread(target=server.serve_forever)
    clients = []
    original = redis.StrictRedis

    def tracked_client(*args, **kwargs):
        client = original(*args, **kwargs)
        clients.append(client)
        return client

    def create_storage():
        return RedisStorage(save_dir='/fixture/pastes', archive_dir=None,
                            server='127.0.0.1', port=server.server_address[1],
                            database=10, **{'save-all': True})

    worker.start()
    try:
        with patch.object(redis, 'StrictRedis', tracked_client):
            if expect_redis8_rejection:
                try:
                    create_storage()
                except redis.exceptions.ResponseError as error:
                    assert "unknown command 'HELLO'" in str(error)
                else:
                    raise AssertionError('Redis 8 default unexpectedly accepted by Redis 5')
                assert redis.__version__ == '8.1.0'
            else:
                storage = create_storage()
                storage.save_pastie(SimpleNamespace(
                    matched=True, site=SimpleNamespace(site='example', name='fixture'),
                    filename='synthetic.txt', id=1))
        if not expect_redis8_rejection:
            with server.lock:
                positive = list(server.commands)
            assert not any(c[0].upper() == b'HELLO' for c in positive)
            assert [c[0] for c in positive].count(b'PING') == 1
            writes = [c for c in positive if c[0].upper() == b'LPUSH']
            assert len(writes) == 1 and re.fullmatch(
                rb'/fixture/pastes/example/\d{4}/\d{2}/\d{2}/synthetic\.txt', writes[0][2])
            # A RESP3 client really fails on this fixture; it cannot silently accept HELLO.
            bad = redis.Redis(host='127.0.0.1', port=server.server_address[1], protocol=3)
            clients.append(bad)
            try:
                bad.ping()
            except redis.exceptions.ResponseError as error:
                assert 'HELLO' in str(error)
            else:
                raise AssertionError('Redis 5 fixture accepted RESP3')
            assert redis.__version__ == '5.3.1'
    finally:
        for client in clients:
            client.close()
            client.connection_pool.disconnect()
        server.shutdown()
        server.server_close()
        worker.join(timeout=10)
        assert not worker.is_alive(), 'fixture worker did not exit'
    assert not server.errors, server.errors
    if expect_redis8_rejection:
        assert server.commands == [[b'HELLO', b'3']], server.commands
        print('PYSTEMON_REDIS8_NEGATIVE_RESULT ' + json.dumps({
            'redis': redis.__version__, 'actualPinnedStorage': True,
            'hello3Rejected': True, 'fixture': 'Redis5 RESP2 command subset',
            'realRedisServerQualified': False}))
        return
    assert any(c[0].upper() == b'HELLO' for c in server.commands)
    print('PYSTEMON_REDIS_WIRE_RESULT ' + json.dumps({
        'redis': redis.__version__, 'actualPinnedStorage': True,
        'constructorPing': True, 'queueLpush': True, 'forcedResp3Rejected': True,
        'fixture': 'Redis5 RESP2 command subset', 'realRedisServerQualified': False}))


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
        RUNTIME.run([python, '-B', Path(__file__), '--redis-source', source], work)
        # The old client is isolated regression data, never installed into the runtime.
        negative = work / 'redis8-negative'
        RUNTIME.run([prefix / 'python/bin/python3', '-I', '-B', '-m', 'venv',
                     '--copies', '--without-pip', negative], work)
        negative_python = negative / 'bin/python'
        RUNTIME.run([negative_python, '-I', '-B', '-m', 'ensurepip'], work)
        RUNTIME.run([negative_python, '-I', '-B', '-m', 'pip', '--isolated', 'install',
                     '--disable-pip-version-check', '--no-cache-dir', '--no-compile',
                     '--no-deps', '--only-binary=:all:', '--require-hashes',
                     '--index-url', 'https://pypi.org/simple', '-r',
                     ROOT / 'scripts/ci/fixtures/pystemon-redis8-negative.txt'], work)
        RUNTIME.run([negative_python, '-B', Path(__file__), '--redis-source', source,
                     '--expect-redis8-rejection'], work)
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
            'fullAilImageBuildOrStartupQualified': False,
            'redis5WireFixture': True, 'redis8NegativeFixture': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-jammy', action='store_true')
    parser.add_argument('--redis-source', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--expect-redis8-rejection', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.expect_redis8_rejection and not args.redis_source:
        parser.error('the negative control requires the pinned source fixture')
    if args.redis_source:
        redis_wire_check(args.redis_source, args.expect_redis8_rejection)
    else:
        qualify(args.require_jammy)
