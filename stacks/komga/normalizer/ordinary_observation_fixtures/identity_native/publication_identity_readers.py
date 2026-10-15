"""Configured committed-history projection; default mismatch remains refused."""
from contextlib import closing
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat

if __package__:
    from . import publication_guard as guard
    from . import publication_identity_adoption as adoption
else:
    import publication_guard as guard
    import publication_identity_adoption as adoption

def configured(ledger):
    adoption.need(os.path.lexists(ledger), 'foreign-durable-identity-no-adoption')
    records, nodes, files, names = adoption._read_ledger(ledger)
    return records, nodes, files, names


def finish(ledger, nodes, files, names):
    adoption.need(set(os.listdir(ledger)) == names, 'identity-reader-final-namespace')
    for path, row in nodes.items():
        z = os.lstat(path)
        adoption.need((z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) == tuple(row), 'identity-reader-original-node5')
    for path, row in files.items():
        adoption.need(tuple(guard.signature(os.lstat(path))) == tuple(row), 'identity-reader-original-file9')


def durable_identity(db, ledger_dir, historical_identity, current_identity, *, outcome, pending=None, writer_owner=None):
    adoption.identity(historical_identity)
    adoption.identity(current_identity)
    original_historical, original_current = historical_identity, current_identity
    historical_identity, current_identity = json.loads(adoption.encoded([historical_identity, current_identity]))
    present = os.path.lexists(ledger_dir)
    if historical_identity == current_identity and not present:
        adoption.identity(original_historical)
        adoption.identity(original_current)
        adoption.need(original_historical == historical_identity and original_current == current_identity, 'identity-reader-original-input-changed')
        return current_identity
    adoption.need(outcome == 'committed', 'identity-noncommitted-physical-mismatch')
    _, nodes, files, names = configured(ledger_dir)
    result = adoption.resolve(db, ledger_dir, historical_identity, current_identity, pending=pending, writer_owner=writer_owner)
    finish(ledger_dir, nodes, files, names)
    adoption.identity(original_historical)
    adoption.identity(original_current)
    adoption.need(original_historical == historical_identity and original_current == current_identity, 'identity-reader-original-input-changed')
    return result


def tagger_digest(identities):
    return (hashlib.sha256(json.dumps(identities).encode()).hexdigest()+'\n').encode()


def quiescent_tagger(paths):
    if __package__:
        from .tagger_adapter import Publisher, TERMINAL
        from .tagger_staging import Staging
    else:
        from tagger_adapter import Publisher, TERMINAL
        from tagger_staging import Staging
    names = {str(path): set(os.listdir(path)) for path in paths[1:]}
    adoption.need(sum(map(len, names.values())) <= 4096 and not names[str(paths[2])],
                  'identity-tagger-unreviewed-journal-or-staging')
    files = {}
    journal_parser = object.__new__(Publisher)
    journal_parser.root = paths[1]  # Read-only schema parser, no ctor/mkdir/replay.
    staging_parser = Staging(paths[2], paths[3])
    for folder in (paths[1], paths[3]):
        for name in sorted(names[str(folder)]):
            path = folder/name
            z = os.lstat(path)
            row = guard.signature(z)
            adoption.need(stat.S_ISREG(z.st_mode) and z.st_uid == os.geteuid() and z.st_nlink == 1
                          and stat.S_IMODE(z.st_mode) == 0o600 and z.st_size <= 1048576,
                          'identity-tagger-unreviewed-journal-or-staging')
            files[str(path)] = row
            if folder == paths[1] and re.fullmatch(r'[a-f0-9]{64}\.lock', name):
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                try:
                    adoption.need(guard.signature(os.fstat(fd)) == row, 'identity-tagger-original-lock9')
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except BlockingIOError as error:
                    raise guard.Unavailable('identity-tagger-active-owner') from error
                finally:
                    os.close(fd)
            else:
                adoption.need(re.fullmatch(r'[a-f0-9]{32}\.json', name) is not None,
                              'identity-tagger-unreviewed-journal-or-staging')
                try:
                    record = journal_parser.read(name[:-5]) if folder == paths[1] else staging_parser.read(path)
                except (OSError, ValueError, KeyError, TypeError) as error:
                    raise guard.Unavailable('identity-tagger-unreviewed-journal-or-staging') from error
                adoption.need(record['state'] in TERMINAL if folder == paths[1] else record['state'] == 'cleaned',
                              'identity-tagger-unreviewed-journal-or-staging')
            adoption.need(guard.signature(os.lstat(path)) == row, 'identity-tagger-original-receipt9')
    return names, files


def validate_tagger_binding(writer, database, binding_path, paths, *, binding_original=None, directory_originals=None):
    """Read-only mismatch route; preserves original identity bytes and journals."""
    root = writer.root.parent/'modern-tagger-v2'
    expected_paths = (root, root/'journal-v2', root/'staging', root/'staging-receipts')
    adoption.need(tuple(paths) == expected_paths and Path(binding_path) == writer.root/'tagger-state-v2.identity',
                  'identity-tagger-fixed-paths')
    directory_rows = []
    for path in paths:
        adoption.need(not any(p.is_symlink() for p in (path, *path.parents)), 'identity-tagger-linked-state')
        z = os.lstat(path)
        adoption.need(stat.S_ISDIR(z.st_mode) and z.st_uid == os.geteuid() and stat.S_IMODE(z.st_mode) == 0o700,
                      'identity-tagger-private-directory')
        directory_rows.append((z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid))
    adoption.need(directory_originals is None or [list(row) for row in directory_rows] == directory_originals,
                  'identity-tagger-caller-original-directories5')
    fd = os.open(binding_path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        z = os.fstat(fd)
        original = guard.signature(z)
        adoption.need(binding_original is None or original == binding_original, 'identity-tagger-caller-original-binding9')
        adoption.need(stat.S_ISREG(z.st_mode) and z.st_nlink == 1 and z.st_uid == os.geteuid()
                      and stat.S_IMODE(z.st_mode) == 0o600 and z.st_size == 65, 'identity-tagger-private-binding')
        raw = os.read(fd, 66)
        adoption.need(guard.signature(os.fstat(fd)) == original and guard.signature(os.lstat(binding_path)) == original,
                      'identity-tagger-original-binding9')
    finally:
        os.close(fd)
    ledger = writer.root/'identity-adoptions-v1'
    records, nodes, files, names = configured(ledger)
    policies = [record['plan']['evidence'].get('tagger') for record in records.values() if record['plan']['evidence'].get('tagger') is not None]
    adoption.need(bool(policies) and all(value == policies[0] for value in policies), 'identity-tagger-one-reviewed-policy')
    tagger = policies[0]
    adoption.need(type(tagger) is dict and set(tagger) == {'binding_sha256', 'binding_inode', 'directory_inodes'}
                  and guard.digest_value(tagger['binding_sha256']) and type(tagger['binding_inode']) is int
                  and type(tagger['directory_inodes']) is list and len(tagger['directory_inodes']) == 4
                  and all(type(x) is int and x > 0 for x in tagger['directory_inodes'])
                  and tagger['binding_inode'] == original[1]
                  and tagger['directory_inodes'] == [row[1] for row in directory_rows]
                  and adoption.digest(raw) == tagger['binding_sha256'], 'identity-tagger-reviewed-originals')
    adoption.need(not any(os.path.lexists(writer.root/name) for name in adoption.PENDING), 'identity-tagger-pending-held')
    namespaces, receipts = quiescent_tagger(paths)
    database = Path(database)
    db9 = guard.database_stamp(database)
    current = dict(database_identity=db9[:2], writer_identity=guard.writer_identity(writer))
    adoption.need(all(row[0] == current['database_identity'][0] for row in directory_rows), 'identity-tagger-one-current-device')
    candidates = []
    for record in records.values():
        old = record['plan']['old']
        if raw == tagger_digest([(old['database_identity'][0], row[1]) for row in directory_rows]):
            candidates.append(old)
    adoption.need(bool(candidates), 'identity-tagger-original-digest-preimage')
    import sqlite3
    with closing(sqlite3.connect(database.as_uri()+'?mode=ro&immutable=1', uri=True)) as db:
        db.execute('BEGIN')
        adoption.resolve(db, ledger, candidates[0], current)
    adoption.need(guard.database_stamp(database) == db9, 'identity-tagger-original-database9')
    adoption.need({str(path): set(os.listdir(path)) for path in paths[1:]} == namespaces, 'identity-tagger-final-namespace')
    finish(ledger, nodes, files, names)
    for path, row in zip(paths, directory_rows):
        z = os.lstat(path)
        adoption.need((z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) == row, 'identity-tagger-final-directory5')
    for path, row in receipts.items():
        adoption.need(guard.signature(os.lstat(path)) == row, 'identity-tagger-final-receipt9')
    adoption.need(guard.signature(os.lstat(binding_path)) == original, 'identity-tagger-final-binding9')
