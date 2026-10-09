"""Fresh exact installed-source proof; never opens data or mints owning custody."""
import hashlib
import importlib
import json
from pathlib import Path
import stat
import sys


def main():
    assert sys.dont_write_bytecode, 'Requires -B'
    fixes = Path(__file__).parent
    manifest = json.loads((fixes / 'publication_reader_cohort.json').read_text())
    sys.path[:0] = ['/app/mylar3', '/app/mylar3/lib']
    modules = {}
    for name, row in manifest['modules'].items():
        module = importlib.import_module('mylar.' + name)
        path = Path(module.__file__)
        assert path == Path('/app/mylar3/mylar') / row['filename'] and path.resolve() == path, name
        before = path.lstat()
        assert stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and stat.S_IMODE(before.st_mode) in (0o600, 0o644), name
        raw = path.read_bytes()
        assert (path.lstat().st_dev, path.lstat().st_ino, path.lstat().st_size, path.lstat().st_mtime_ns, path.lstat().st_ctime_ns, path.lstat().st_mode, path.lstat().st_uid, path.lstat().st_gid, path.lstat().st_nlink) == (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns, before.st_mode, before.st_uid, before.st_gid, before.st_nlink) and hashlib.sha256(raw).hexdigest() == row['sha256'], name
        assert raw == (fixes / row['filename']).read_bytes(), name
        modules[name] = module
    core = modules['publication_archive_owned']
    api, writers, guard = core.sdk()[:3]
    negative = modules['publication_negative']
    mutation = importlib.import_module('mylar.publication_mutation')
    catalog = modules['publication_negative_catalog']
    assert negative.guard is api.guard is guard
    assert negative.mutation is mutation and negative.catalog is catalog
    assert api.Writer is writers.Writer and negative._sdk() == (api, writers)
    assert 'publication_guard' not in sys.modules and 'publication_mutation' not in sys.modules
    for name in manifest['existing_sdk_closure']:
        module = importlib.import_module('mylar.' + name)
        path = Path(module.__file__)
        assert path == Path('/app/mylar3/mylar') / (name + '.py') and path.resolve() == path, name
    loader = modules['publication_negative_namespace']
    kernel = loader.kernel()
    assert kernel.__file__ == str(loader.KERNEL_PATH)
    assert loader.KERNEL_SHA == manifest['modules']['publication_negative_namespace_kernel']['sha256']
    disk = modules['publication_reader_disk']
    assert disk.k is modules['publication_reader_softdelete']
    assert disk.KERNEL_SHA == manifest['modules']['publication_reader_softdelete']['sha256']
    admission = modules['publication_reader_admission']
    assert admission.PARENT_SHA is manifest['parent_sha256'] is None
    assert admission.NEGATIVE_SHA == manifest['modules']['publication_negative']['sha256']
    assert admission.LIFECYCLE_SHA == manifest['modules']['publication_reader_lifecycle']['sha256']
    scope = modules['publication_native_configured_scope']
    # The pinned upstream image ships these sources group-writable. Preserve
    # their bytes while proving the image build closes that source boundary.
    for filename, digest, mode in ((scope.CONFIG_PATH, scope.CONFIG_SHA, 0o644),
                                   (scope.MAIN_PATH, scope.MAIN_SHA, 0o755)):
        path = Path(filename)
        assert path.lstat().st_uid == 0 and stat.S_IMODE(path.lstat().st_mode) == mode
        scope.bounded_read(path, digest, scope.nine(path.lstat()), scope.ancestors([path]))
    lifecycle = modules['publication_reader_lifecycle']
    birth = modules['publication_native_scope_birth']
    assert lifecycle.BIRTH_SOURCE == Path(birth.__file__)
    assert birth.life is lifecycle
    assert callable(lifecycle.from_birth) and callable(birth.from_checked_parent)
    assert modules['publication_reader_sql_transition'].sql_five_transition is modules['publication_reader_phase'].sql_five_transition
    print('Installed prospective reader source/origin/type proof passed; owning admission remains held')


if __name__ == '__main__':
    main()
