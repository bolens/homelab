"""Stage HTTP downloads and validate archives before native post-processing."""
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

ARCHIVES = ('.cbr', '.cbz', '.cb7', '.cbt', '.zip', '.rar', '.7z', '.tar', '.tar.gz', '.tar.xz', '.tgz')


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
    if header.startswith(b'PK'):
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


def receive(response, final, resume, record_id):
    from mylar import queue_control, db
    final = Path(final)
    partial = final.with_name(final.name + '.part')
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
    database = db.DBConnection()
    database.upsert('ddl_info', {'tmp_filename': str(partial), 'remote_filesize': expected or 0}, {'id': record_id})
    with partial.open('ab' if offset else 'xb') as output:
        for chunk in response.iter_content(chunk_size=65536):
            if chunk:
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
    if expected is not None and offset != expected:
        raise ValueError('Truncated download; partial retained')
    checked(partial)
    if final.exists():
        retain(final)
    os.replace(partial, final)
    database.upsert('ddl_info', {'tmp_filename': None}, {'id': record_id})


def unpack(record_id, path, filename):
    """Validate before extraction; only publish a complete pack directory."""
    path = Path(path)
    checked(path)
    if path.suffix.lower() != '.zip':
        return {'success': True, 'filename': filename, 'path': str(path)}
    temporary = Path(tempfile.mkdtemp(prefix='.mylar-unpack-', dir=path.parent))
    try:
        with zipfile.ZipFile(path) as archive:
            archive.extractall(temporary)
        archives = [p for p in temporary.rglob('*') if p.is_file() and p.name.lower().endswith(ARCHIVES)]
        if not archives:
            raise ValueError('Pack contains no comic archives')
        for child in archives:
            checked(child)
        target = path.with_suffix('')
        if target.exists():
            target = target.with_name(target.name + '.recovered-' + str(time.time_ns()))
        temporary.rename(target)
        # Keep the original ZIP until normal maintenance proves it is redundant.
        return {'success': True, 'filename': None, 'path': str(target)}
    except Exception:
        # Keep staged data and the original archive for investigation.
        raise ValueError('Pack validation failed; source retained') from None


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
