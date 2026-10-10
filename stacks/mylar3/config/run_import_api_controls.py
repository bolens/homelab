"""Build-only closed public API controls; all test writes stay in private copies."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).parent
API_SHA = '0fade189a300b8c26ea083355d4c13a464c7960a47c6b81a4a66f76f307c83a7'

def full(st):
    return (st.st_dev, st.st_ino, st.st_mode, st.st_uid, st.st_gid,
            st.st_nlink, st.st_size, st.st_mtime_ns, st.st_ctime_ns)

def node(st):
    return (st.st_dev, st.st_ino, st.st_mode, st.st_uid, st.st_gid)

def main(family="all"):
    assert family in ("all", "observation", "retained")
    entries = json.loads((ROOT / 'import_api_control_sources.json').read_text())
    assert isinstance(entries, list) and 1 <= len(entries) <= 512
    files, nodes, buffers = {}, {}, {}
    # Capture the complete original set before the first source read.
    for row in entries:
        assert set(row) == {'path', 'sha256'}
        rel = Path(row['path'])
        assert not rel.is_absolute() and '..' not in rel.parts and rel.suffix == '.py'
        path = ROOT / rel
        assert path not in files
        st = os.lstat(path)
        assert stat.S_ISREG(st.st_mode) and st.st_nlink == 1
        files[path] = full(st)
        for parent in path.parents:
            stamp = node(os.lstat(parent))
            assert parent not in nodes or nodes[parent] == stamp
            assert (stamp[2] & 0o170000) == 0o040000
            nodes[parent] = stamp
    total = 0
    for row in entries:
        path = ROOT / row['path']
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            assert full(os.fstat(fd)) == files[path]
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                data = stream.read(32 * 1024 * 1024 + 1)
            assert full(os.fstat(fd)) == files[path]
        finally:
            os.close(fd)
        total += len(data)
        assert total <= 32 * 1024 * 1024
        assert hashlib.sha256(data).hexdigest() == row['sha256']
        buffers[row['path']] = data
    with tempfile.TemporaryDirectory(prefix='mylar-import-api-controls-') as tmp:
        root = Path(tmp)
        config = root / 'config'
        config.mkdir()
        preimages = root / 'preimages'
        preimages.mkdir()
        for name, data in buffers.items():
            if name == 'import_api_fixtures/api_predecessor.py':
                assert hashlib.sha256(data).hexdigest() == API_SHA
                (preimages / 'api.py').write_bytes(data)
            else:
                assert len(Path(name).parts) == 1
                (config / name).write_bytes(data)
        source = (preimages / 'api.py').read_text()
        for name in ('patch_ordinary_import_observation', 'patch_retained_delivery_api'):
            spec = importlib.util.spec_from_file_location(name, config / (name + '.py'))
            module = importlib.util.module_from_spec(spec)
            sys.path.insert(0, str(config))
            try:
                spec.loader.exec_module(module)
                source = module.patched_source(source)
                assert module.patched_source(source) == source
            finally:
                sys.path.pop(0)
        (config / 'api.py').write_text(source)
        code = 0
        # Owning host fixture package identities are isolated by suite family.
        families = {
            'observation': ('test_ordinary_import_observation', 'test_ordinary_import_continuity'),
            'retained': ('test_retained_delivery_api', 'test_retained_native_operation',
                         'test_publication_retained_finalize', 'test_publication_retained_delivery'),
        }
        selected = families.values() if family == 'all' else (families[family],)
        for suites in selected:
            result = subprocess.run([sys.executable, '-B', '-m', 'unittest', *suites], cwd=config)
            code = code or result.returncode
    # No helper callback follows this complete original raw closure.
    for path, original in files.items():
        st = os.lstat(path)
        assert (st.st_dev, st.st_ino, st.st_mode, st.st_uid, st.st_gid,
                st.st_nlink, st.st_size, st.st_mtime_ns, st.st_ctime_ns) == original
    for path, original in nodes.items():
        st = os.lstat(path)
        assert (st.st_dev, st.st_ino, st.st_mode, st.st_uid, st.st_gid) == original
    return code

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--family', choices=('all', 'observation', 'retained'), default='all')
    raise SystemExit(main(parser.parse_args().family))
