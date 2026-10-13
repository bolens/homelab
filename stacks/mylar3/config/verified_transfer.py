"""Stage HTTP downloads and validate archives before native post-processing."""
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile

MAX_MEMBERS = 100000
MAX_EXPANDED = 32 * 1024 ** 3
_VALIDATED = set()

ARCHIVES = ('.cbr', '.cbz', '.cb7', '.cbt', '.zip', '.rar', '.7z', '.tar', '.tar.gz', '.tar.xz', '.tgz', '.pdf')


def safe_member(name):
    path = PurePosixPath(name.replace('\\', '/'))
    if path.is_absolute() or '..' in path.parts or (path.parts and ':' in path.parts[0]):
        raise ValueError('Unsafe archive member')


def validate(path):
    """Runs in a bounded child process so damaged decoders cannot stall the worker."""
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing or linked archive')
    with path.open('rb') as source:
        header = source.read(8)
    if header.startswith(b'%PDF-'):
        # Download validation checks the document structure. The normalizer owns
        # full-page rendering and must verify all pages before a CBZ is imported.
        result = subprocess.run(['pdfinfo', str(path)], capture_output=True, timeout=60,
                                env=dict(os.environ, LC_ALL='C'))
        info = result.stdout.decode('utf-8', errors='replace')
        pages = re.search(r'^Pages:\s+(\d+)\s*$', info, re.M)
        if (result.returncode or result.stderr or not pages or not 0 < int(pages[1]) <= 1000
                or not re.search(r'^Encrypted:\s+no\s*$', info, re.M)):
            raise ValueError('Invalid, encrypted or oversized PDF; source retained')
    elif header.startswith(b'PK'):

        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_MEMBERS or sum(x.file_size for x in entries) > MAX_EXPANDED:
                raise ValueError('Archive exceeds validation limits or is empty')
            for entry in entries:
                safe_member(entry.filename)
                if stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1:
                    raise ValueError('Linked or encrypted archive member')
            if archive.testzip() is not None:
                raise ValueError('Archive CRC check failed')
    elif header.startswith(b'Rar!'):
        # Mylar ships its decoder under lib.rarfile rather than site-packages.
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        try:
            from lib.rarfile import rarfile
        except ModuleNotFoundError:
            import rarfile
        with rarfile.RarFile(path) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_MEMBERS or sum(x.file_size for x in entries) > MAX_EXPANDED:
                raise ValueError('Archive exceeds validation limits or is empty')
            for entry in entries:
                safe_member(entry.filename)
                if entry.is_symlink() or entry.needs_password():
                    raise ValueError('Linked or encrypted archive member')
            archive.testrar()
    elif header.startswith(b'7z\xbc\xaf\x27\x1c'):
        tool = shutil.which('7zz') or shutil.which('7z')
        if not tool:
            raise ValueError('7z validation tool unavailable')
        subprocess.run([tool, 't', '-bd', '-y', str(path)], check=True, timeout=150,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    elif tarfile.is_tarfile(path):
        with tarfile.open(path) as archive:
            total = count = 0
            for entry in archive:
                count += 1
                total += entry.size
                safe_member(entry.name)
                if count > MAX_MEMBERS or total > MAX_EXPANDED or not (entry.isfile() or entry.isdir()):
                    raise ValueError('Unsupported tar member or limit exceeded')
                if entry.isfile():
                    with archive.extractfile(entry) as source:
                        while source.read(1024 * 1024):
                            pass
            if not count:
                raise ValueError('Empty archive')
    else:
        raise ValueError('Unsupported or invalid archive')


def checked(path):
    path = Path(path)
    before = path.stat()
    signature = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
    if not path.is_symlink() and signature in _VALIDATED:
        return
    result = subprocess.run([sys.executable, __file__, 'validate', str(path)], timeout=180,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    after = path.stat()
    actual = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
    if result.returncode or actual != signature:
        raise ValueError('Archive validation failed or file changed; source retained')
    if len(_VALIDATED) >= 1024:
        _VALIDATED.clear()
    _VALIDATED.add(signature)


def retain(path):
    """Move, never discard, conflicting or restarted partial bytes."""
    path = Path(path)
    if path.exists():
        if path.is_symlink():
            raise ValueError('Refusing linked transfer path')
        target = path.with_name(path.name + '.retained-' + str(time.time_ns()))
        path.rename(target)
        return target


def cache_guard():
    from mylar import cache_admission
    return cache_admission


def zip_inventory(archive):
    """One finite projected namespace, including implicit ZIP directories."""
    files = {}; dirs = {''}; declared = set(); expanded = 0
    entries = archive.infolist()
    if not entries or len(entries) > MAX_MEMBERS:
        raise ValueError('Pack inventory exceeds limits')
    for entry in entries:
        safe_member(entry.filename)
        name = str(PurePosixPath(entry.filename.replace('\\', '/')))
        if name in ('', '.') or name in declared or len(PurePosixPath(name).parts) > 32:
            raise ValueError('Ambiguous or deep pack inventory; source retained')
        declared.add(name)
        if entry.is_dir(): dirs.add(name)
        else: files[name] = entry; expanded += entry.file_size
        dirs.update(str(p) for p in PurePosixPath(name).parents if str(p) != '.')
        if len(dirs) + len(files) > MAX_MEMBERS or expanded > MAX_EXPANDED:
            raise ValueError('Pack expanded namespace exceeds limits')
    if set(files) & dirs or not any(name.lower().endswith(ARCHIVES) for name in files):
        raise ValueError('Pack contains no complete comic archive inventory')
    return files, dirs, expanded


def existing_extraction(archive, target):
    """Reuse only the exact complete companion of this original ZIP."""
    guard = cache_guard()
    files, dirs, _ = zip_inventory(archive)
    root_fd, _ = guard.open_directory(target)
    captured_files = []; captured_dirs = []; seen_files = set(); seen_dirs = {''}
    def scan(fd, relative):
        value = guard.identity(os.fstat(fd)); names = tuple(sorted(os.listdir(fd)))
        captured_dirs.append((relative, value, names))
        for name in names:
            rel = str(PurePosixPath(relative) / name); z = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(z.st_mode):
                seen_dirs.add(rel); child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    if guard.identity(os.fstat(child)) != guard.identity(z): raise ValueError('Pack directory changed')
                    scan(child, rel)
                finally: os.close(child)
            elif stat.S_ISREG(z.st_mode) and z.st_nlink == 1:
                seen_files.add(rel); captured_files.append((rel, guard.identity(z)))
            else: raise ValueError('Linked or unsupported existing extraction; source retained')
    try:
        scan(root_fd, '')
    finally: os.close(root_fd)
    original_files = tuple(captured_files); original_dirs = tuple(captured_dirs)
    if seen_files != set(files) or seen_dirs != dirs:
        raise ValueError('Existing pack extraction is incomplete or unrelated; source retained')
    for name, before in original_files:
        parent_fd, _ = guard.open_directory((target / name).parent)
        try: fd = os.open(Path(name).name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
        finally: os.close(parent_fd)
        try:
            if guard.identity(os.fstat(fd)) != before: raise ValueError('Pack member changed')
            actual = hashlib.sha256(); expected = hashlib.sha256()
            with archive.open(files[name]) as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b''): expected.update(chunk)
            while True:
                chunk = os.read(fd, 1024 * 1024)
                if not chunk: break
                actual.update(chunk)
            if actual.digest() != expected.digest() or os.fstat(fd).st_size != files[name].file_size:
                raise ValueError('Existing pack member differs; source retained')
            if guard.identity(os.fstat(fd)) != before: raise ValueError('Pack member changed')
        finally: os.close(fd)
    for name in files:
        if name.lower().endswith(ARCHIVES): checked(target / name)
    # All read/hash/FD cleanup callbacks precede the physical original tails.
    for name, _, names in original_dirs:
        fd, _ = guard.open_directory(target / name)
        try:
            if tuple(sorted(os.listdir(fd))) != names: raise ValueError('Pack namespace changed')
        finally: os.close(fd)
    for name, before in original_files:
        if guard.identity(os.lstat(target / name)) != before: raise ValueError('Pack member changed')
    for name, before, _ in original_dirs:
        if guard.identity(os.lstat(target / name)) != before: raise ValueError('Pack directory changed')
    return original_files, original_dirs


def ddl_generation(database, record_id):
    """Use the native worker's existing full original-row/date generation."""
    from mylar.queues.ddl import _ddl_status_original
    row = database.selectone('SELECT * FROM ddl_info WHERE id=?', [record_id]).fetchone()
    if row is None:
        raise cache_guard().Held('DDL generation is no longer available; original retained')
    item = {key: row[key] for key in ('id', 'link', 'mainlink', 'issueid', 'comicid', 'site')}
    original = _ddl_status_original(database, item)
    if original is None:
        raise cache_guard().Held('DDL generation is no longer available; original retained')
    return original


def ddl_metadata(database, original, values=None):
    """Never insert metadata or mutate a Removed/NZB/foreign generation."""
    fields, date = original
    columns = tuple(('rowid' if key == '__ddl_generation_rowid' else key, value) for key, value in fields)
    where = ' AND '.join('"'+key+'" IS ?' for key, _ in columns)
    where += " AND updated_date IS ? AND status IN ('Queued','Downloading')"
    expected = [value for _, value in columns] + [date]
    if values is None:
        present = database.selectone('SELECT 1 FROM ddl_info WHERE '+where, expected).fetchone() is not None
    else:
        if type(values) is not dict or not values or not set(values) <= {'tmp_filename','remote_filesize','filename','size'}:
            raise ValueError('Unsupported DDL transfer metadata')
        keys = tuple(values)
        result = database.action('UPDATE ddl_info SET '+','.join('"'+key+'"=?' for key in keys)+' WHERE '+where,
                                 [values[key] for key in keys] + expected)
        present = result is not None and result.rowcount == 1
    if not present:
        raise cache_guard().Held('DDL generation changed; original transfer bytes retained')


def receive(response, final, resume, record_id, original_generation=None):
    from mylar import queue_control, db
    database = db.DBConnection()
    if original_generation is None:
        original_generation = ddl_generation(database, record_id)
    ddl_metadata(database, original_generation)
    final = Path(final)
    partial = final.with_name(final.name + '.part')
    # Admit the original destination before even retaining a legacy partial.
    with cache_guard().allocation(final.parent, 0):
        pass
    if final.is_symlink() or partial.is_symlink():
        raise ValueError('Refusing linked transfer path')
    expected = None
    offset = int(resume or 0)
    if response.status_code == 206:
        match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('Content-Range', ''))
        if not match or int(match[1]) != offset or int(match[2]) < offset or int(match[2]) >= int(match[3]):
            raise ValueError('Invalid resume response')
        expected = int(match[3])
        if offset:
            if not partial.exists() and final.is_file() and final.stat().st_size == offset:
                final.rename(partial)
            if not partial.is_file() or partial.stat().st_size != offset:
                raise ValueError('Saved DDL file does not match the requested resume offset')
    elif response.status_code == 200:
        if offset or partial.exists():
            retain(partial)
            # A legacy partial may still use the final file name.
            if offset:
                retain(final)
        offset = 0
    else:
        raise ValueError('Download server rejected request')
    encoding = response.headers.get('Content-Encoding', 'identity').lower()
    if encoding not in ('identity', ''):
        raise ValueError('Encoded archive response cannot be verified by byte range')
    length = response.headers.get('Content-Length')
    if length is not None:
        length = int(length)
        if length < 0 or (expected is not None and expected != offset + length):
            raise ValueError('Conflicting download size headers')
        expected = offset + length
    if not offset and partial.exists():
        retain(partial)
    with cache_guard().allocation(final.parent, None if expected is None else expected - offset, nodes=0 if partial.exists() else 1) as reservation:
        ddl_metadata(database, original_generation, {'tmp_filename': str(partial), 'remote_filesize': expected or 0})
        flags = os.O_WRONLY | os.O_NOFOLLOW | (os.O_APPEND if offset else os.O_CREAT | os.O_EXCL)
        output_fd = os.open(partial.name, flags, 0o600, dir_fd=reservation.dirfd)
        birth = os.fstat(output_fd)
        if not stat.S_ISREG(birth.st_mode) or birth.st_nlink != 1:
            os.close(output_fd)
            raise ValueError('Transfer partial is not an original regular file')
        with os.fdopen(output_fd, 'ab' if offset else 'wb') as output:
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    ddl_metadata(database, original_generation)
                    reservation.before_write(len(chunk))
                    current = os.fstat(output.fileno())
                    if (current.st_dev, current.st_ino) != (birth.st_dev, birth.st_ino) or current.st_nlink != 1 or cache_guard().identity(os.stat(partial.name, dir_fd=reservation.dirfd, follow_symlinks=False)) != cache_guard().identity(current):
                        raise ValueError('Original transfer partial changed')
                    output.write(chunk)
                    offset += len(chunk)
                    if expected is not None and offset > expected:
                        raise ValueError('Download exceeds declared size')
                    with queue_control._LOCK:
                        state = queue_control.store()
                        previous = state.data['items'].get(str(record_id), {}).get('sample_time', 0)
                        state.observe(record_id, offset)
                        if state.clock() - previous >= 2:
                            state.save()
            output.flush()
            os.fsync(output.fileno())
            written = cache_guard().identity(os.fstat(output.fileno()))
        if cache_guard().identity(os.stat(partial.name, dir_fd=reservation.dirfd, follow_symlinks=False)) != written:
            raise ValueError('Original transfer partial changed')
        if expected is not None and offset != expected:
            raise ValueError('Truncated download; partial retained')
        checked(partial)
        if final.exists():
            raise cache_guard().Held('Existing download destination requires owning recovery; partial retained')
        reservation.originals()
        if cache_guard().identity(os.stat(partial.name, dir_fd=reservation.dirfd, follow_symlinks=False)) != written:
            raise ValueError('Original verified partial changed')
        try:
            os.link(partial.name, final.name, src_dir_fd=reservation.dirfd,
                    dst_dir_fd=reservation.dirfd, follow_symlinks=False)
        except FileExistsError:
            raise cache_guard().Held('Download destination appeared; original and verified partial retained') from None
        linked = os.stat(final.name, dir_fd=reservation.dirfd, follow_symlinks=False)
        if (linked.st_dev, linked.st_ino) != written[:2] or linked.st_nlink != 2:
            raise ValueError('Verified transfer promotion identity changed')
        os.unlink(partial.name, dir_fd=reservation.dirfd)
        ddl_metadata(database, original_generation, {'tmp_filename': None})


def unpack(record_id, path, filename):
    """Validate, reserve expansion, and never duplicate a complete companion."""
    path = Path(path); guard = cache_guard(); original = guard.identity(os.lstat(path)); reused = None
    checked(path)
    if path.suffix.lower() != '.zip':
        if guard.identity(os.lstat(path)) != original: raise ValueError('Pack original changed')
        return {'success': True, 'filename': filename, 'path': str(path)}
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        if guard.identity(os.fstat(fd)) != original: raise ValueError('Pack original changed')
        with os.fdopen(fd, 'rb', closefd=False) as source, zipfile.ZipFile(source) as archive:
            target = path.with_suffix('')
            if os.path.lexists(target):
                try:
                    reused = existing_extraction(archive, target)
                except (ValueError, OSError):
                    raise guard.Held('Existing extraction needs owning review; originals retained') from None
                answer = {'success': True, 'filename': None, 'path': str(target)}
            else:
                files, directories, expanded = zip_inventory(archive)
                with guard.allocation(path.parent, expanded, nodes=len(files) + len(directories)) as reservation:
                    temporary = Path(tempfile.mkdtemp(prefix='.mylar-unpack-', dir=path.parent))
                    try:
                        for name in sorted(directories - {''}, key=lambda n: (len(PurePosixPath(n).parts), n)):
                            reservation.originals()
                            (temporary / name).mkdir()
                        for name, entry in files.items():
                            reservation.originals()
                            parent_fd, _ = guard.open_directory((temporary / name).parent)
                            try:
                                child_fd = os.open(Path(name).name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                                   0o600, dir_fd=parent_fd)
                                with os.fdopen(child_fd, 'wb') as output, archive.open(entry) as source_member:
                                    for chunk in iter(lambda: source_member.read(65536), b''):
                                        reservation.before_write(len(chunk))
                                        output.write(chunk)
                                    output.flush(); os.fsync(output.fileno())
                            finally: os.close(parent_fd)
                        archives = [p for p in temporary.rglob('*') if p.is_file() and p.name.lower().endswith(ARCHIVES)]
                        if not archives: raise ValueError('Pack contains no comic archives')
                        for child in archives: checked(child)
                        if os.path.lexists(target): raise ValueError('Pack target appeared; source retained')
                        temporary.rename(target)
                        answer = {'success': True, 'filename': None, 'path': str(target)}
                    except guard.Held:
                        raise
                    except Exception:
                        # The owned stage and original remain available for review.
                        raise ValueError('Pack validation failed; source retained') from None
    finally: os.close(fd)
    if reused is not None:
        for name, _, names in reused[1]:
            check_fd, _ = guard.open_directory(target / name)
            try:
                if tuple(sorted(os.listdir(check_fd))) != names: raise ValueError('Pack namespace changed')
            finally: os.close(check_fd)
        for name, before in reused[0]:
            if guard.identity(os.lstat(target / name)) != before: raise ValueError('Pack member changed')
        for name, before, _ in reused[1]:
            if guard.identity(os.lstat(target / name)) != before: raise ValueError('Pack directory changed')
    if guard.identity(os.lstat(path)) != original: raise ValueError('Pack original changed')
    return answer


def validate_result(result, item):
    if not isinstance(result, dict):
        result = {'success': False, 'filename': None, '_queue_reason': 'Provider returned no result'}
    if result.get('success'):
        try:
            path = Path(result['path'])
            if path.is_file():
                checked(path)
            elif path.is_dir() and not path.is_symlink():
                files = [p for p in path.rglob('*') if p.is_file() and p.name.lower().endswith(ARCHIVES)]
                if not files:
                    raise ValueError('No comic archives')
                for file in files:
                    checked(file)
            else:
                raise ValueError('Downloaded archive is missing')
        except Exception:
            result.update(success=False, _queue_reason='Archive validation failed; source retained')
    return result


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] != 'validate':
        raise SystemExit(2)
    try:
        validate(sys.argv[2])
    except Exception:
        raise SystemExit(1)
