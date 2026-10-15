"""Prospective stable Btrfs destination observation, with no device fallback.

Linux UAPI: btrfs_ioctl_fs_info_args1024/fsid16 and
btrfs_ioctl_get_subvol_info_args504/uuid296. No old UUID is inferred.
"""
import fcntl
import os
import platform
from pathlib import Path
import stat
import struct
import sys
import uuid

if __package__:
    from . import publication_guard as guard
else:
    import publication_guard as guard

FS_INFO = 2214630431
SUBVOL_INFO = 2180551740


def node(z):
    return [z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid]


def query(directory):
    directory = Path(directory)
    if sys.platform != 'linux' or sys.byteorder != 'little' or platform.machine() != 'x86_64' or sys.maxsize != 2**63-1:
        raise guard.Unavailable('Unsupported stable filesystem ABI')
    ancestors = {}
    for path in (directory, *directory.parents):
        z = os.lstat(path)
        if not stat.S_ISDIR(z.st_mode):
            raise guard.Unavailable('Linked stable filesystem ancestor')
        ancestors[str(path)] = node(z)
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        original = node(os.fstat(fd))
        filesystem = bytearray(1024)
        subvolume = bytearray(504)
        fcntl.ioctl(fd, FS_INFO, filesystem, True)
        fcntl.ioctl(fd, SUBVOL_INFO, subvolume, True)
        fsid = bytes(filesystem[16:32])
        treeid = struct.unpack_from('<Q', subvolume, 0)[0]
        subid = bytes(subvolume[296:312])
        if not any(fsid) or treeid < 5 or (not any(subid) and treeid != 5) or node(os.fstat(fd)) != original or node(os.lstat(directory)) != original:
            raise guard.Unavailable('Invalid stable filesystem observation')
        result = {'fstype': 'btrfs', 'filesystem_uuid': str(uuid.UUID(bytes=fsid)),
                  'subvolume': str(treeid)+':'+str(uuid.UUID(bytes=subid))}
    except OSError as error:
        raise guard.Unavailable('Stable filesystem observation unsupported') from error
    finally:
        os.close(fd)
    for path, original in ancestors.items():
        if node(os.lstat(path)) != original:
            raise guard.Unavailable('Stable filesystem original ancestor changed')
    return result


def database_observation(database, *, held_writer=None, transaction=None):
    if held_writer is None:
        return guard.database_stamp(database)
    if __package__:
        from .media_writer import Writer
    else:
        from media_writer import Writer
    if (type(held_writer) is not Writer or not guard.identity_transaction_owned(transaction, held_writer, database)
            or Path(database) != held_writer.root.parent/'workflow.sqlite'):
        raise guard.Unavailable('Stable transaction requires original held Writer')
    held_writer.validate_root()
    with guard.regular(database) as stream:
        before = guard.signature(os.fstat(stream.fileno()))
        header = stream.read(100)
        if (before[6] != os.geteuid() or stat.S_IMODE(before[5]) != 0o600 or before[8] != 1
                or len(header) != 100 or header[:16] != b'SQLite format 3\0' or header[18:20] != b'\x01\x01'
                or any(os.path.lexists(str(database)+suffix) for suffix in ('-wal', '-shm'))
                or guard.signature(os.fstat(stream.fileno())) != before or guard.signature(os.lstat(database)) != before):
            raise guard.Unavailable('Invalid owned rollback transaction database')
        return before


def observe(database, writer_root, *, held_writer=None, transaction=None):
    database, writer_root = Path(database), Path(writer_root)
    if not database.is_absolute() or not writer_root.is_absolute():
        raise guard.Unavailable('Stable filesystem paths must be absolute')
    before = database_observation(database, held_writer=held_writer, transaction=transaction)
    if __package__:
        from .media_writer import Writer
    else:
        from media_writer import Writer
    writer = Writer(writer_root, create=False) if held_writer is None else held_writer
    if writer.root != writer_root:
        raise guard.Unavailable('Stable transaction Writer root differs')
    pair = guard.writer_identity(writer)
    database_parent = node(os.lstat(database.parent))
    writer_parent = node(os.lstat(writer_root))
    if before[0] != database_parent[0] or pair[0] != writer_parent[0] or pair[2] != writer_parent[0]:
        raise guard.Unavailable('Stable filesystem file and directory device differ')
    left, right = query(database.parent), query(writer_root)
    if (left != right or database_observation(database, held_writer=held_writer, transaction=transaction) != before or guard.writer_identity(writer) != pair
            or node(os.lstat(database.parent)) != database_parent or node(os.lstat(writer_root)) != writer_parent):
        raise guard.Unavailable('Stable filesystem destination pair differs')
    left['path_anchor_digest'] = guard.canonical_digest(['native-workflow-db', 'native-writer-root', 'native-writer-lock', before[1], pair[1], pair[3]])
    return left
