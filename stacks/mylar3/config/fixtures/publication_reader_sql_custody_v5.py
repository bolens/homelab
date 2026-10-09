"""Prospective bounded owned SQLite transaction custody, not installed.

This helper owns a BEGIN IMMEDIATE transaction, its exact journal/companions,
logical five-row delta, and physical CAS. It never creates a native/reader grant.
The caller must hold its typed batch and continuous stopped-reader lifecycle.
"""
from pathlib import Path
_PORTABLE_ROOT = next((p for p in Path(__file__).resolve().parents if (p / '.portable-cohort').is_file()))
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import threading
_KEY = object()

class Held(ValueError):
    pass

def check(v, r):
    if not v:
        raise Held(r)

def encode(v):
    return json.dumps(v, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def signature(p):
    z = os.lstat(p)
    return [z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns, z.st_mode, z.st_uid, z.st_gid, z.st_nlink]

def raw_pair(db, *, journal=False):
    result = {}
    for suffix in ('', '-wal', '-shm', '-journal'):
        p = Path(str(db) + suffix)
        try:
            before = signature(p)
        except FileNotFoundError:
            continue
        check(suffix != '-journal' or journal, 'unowned-reader-journal')
        check(p.resolve() == p and stat.S_ISREG(before[5]) and (before[8] == 1) and (before[2] <= 1024 ** 3), 'owned-reader-pair-file')
        h = hashlib.sha256()
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
        total = 0
        try:
            while True:
                block = os.read(fd, 1024 ** 2)
                if not block:
                    break
                h.update(block)
                total += len(block)
                check(total <= before[2], 'owned-reader-file-growth')
            names = sorted(os.listxattr(p, follow_symlinks=False))
            check(len(names) <= 64, 'bounded-reader-xattrs')
            attributes = {name: os.getxattr(p, name, follow_symlinks=False).hex() for name in names}
            check(sum((len(os.fsencode(name)) + len(bytes.fromhex(value)) for name, value in attributes.items())) <= 1024 ** 2, 'bounded-reader-xattr-bytes')
            z = os.fstat(fd)
            check([z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns, z.st_mode, z.st_uid, z.st_gid, z.st_nlink] == before and signature(p) == before, 'owned-reader-pair-CAS')
        finally:
            os.close(fd)
        result[suffix] = dict(signature9=before, sha256=h.hexdigest(), xattrs=attributes)
    check('' in result and ('-wal' in result) == ('-shm' in result), 'owned-coherent-reader-pair')
    return result

class SQLWritingCustody:
    """Private phase mechanic; public operational factory intentionally absent."""

    def __init__(self, key, connection, db, disk, plan, before, after, baseline):
        check(key is _KEY and type(connection) is sqlite3.Connection and connection.in_transaction, 'owned-immediate-transaction')
        db = Path(db)
        check(db.is_absolute() and db.resolve() == db, 'canonical-reader-database')
        self.nodes = {p: [signature(p)[i] for i in (0, 1, 5, 6, 7)] for p in db.parents}
        self.parent = db.parent
        self.initial_directory = signature(db.parent)
        self.names = {name: signature(db.parent / name) for name in os.listdir(db.parent) if name not in {db.name + x for x in ('', '-wal', '-shm', '-journal')}}
        rows = list(connection.execute('PRAGMA database_list'))
        check(len(rows) == 1 and rows[0][1] == 'main' and (Path(rows[0][2]) == db), 'sole-owned-main-database')
        mode = connection.execute('PRAGMA journal_mode').fetchone()[0]
        check(mode in ('delete', 'wal'), 'bounded-existing-journal-mode')
        self.connection = connection
        self.db = db
        self.disk = disk
        self.plan = plan
        self.before = before
        self.after = after
        check(raw_pair(db) == baseline, 'initial-owned-reader-pair-CAS')
        self.baseline = baseline
        self.thread = threading.get_ident()
        self.mode = mode
        self.phase = 'writing'
        check(self.logical() == before, 'owned-reader-logical-preimage')
        check(raw_pair(db) == baseline, 'initial-owned-reader-pair-after-logical-CAS')
        for p, v in self.nodes.items():
            check([signature(p)[i] for i in (0, 1, 5, 6, 7)] == v, 'initial-reader-ancestor')
        self.core = self._core()
        self.pending = None

    def _core(self):
        return hashlib.sha256(encode(dict(db=str(self.db), plan=self.plan, before=self.before, after=self.after, baseline=self.baseline, mode=self.mode, thread=self.thread, connection=id(self.connection), disk=id(self.disk), nodes={str(p): v for p, v in self.nodes.items()}, names=self.names, initial_directory=self.initial_directory))).hexdigest()

    def logical(self):
        return (self.disk.master(self.connection), self.disk.k.snapshot(self.connection), self.disk.book_rows(self.connection, self.plan))

    def apply_body(self, transition):
        check(self._core() == self.core and self.thread == threading.get_ident() and (self.phase == 'writing') and (self.pending is None), 'immutable-owned-reader-transaction')
        self._close_before_write()
        transition(self.connection, self.disk, self.plan, self.before, self.after)
        current = raw_pair(self.db, journal=True)
        directory = signature(self.parent)
        old = self.baseline['']['signature9']
        new = current['']['signature9']
        check(all((old[i] == new[i] for i in (0, 1, 5, 6, 7, 8))) and current['']['xattrs'] == self.baseline['']['xattrs'], 'owned-SQL-main-incarnation')
        check(self.logical() == self.after, 'owned-reader-logical-postimage')
        check(raw_pair(self.db, journal=True) == current, 'owned-SQL-pair-after-logical-CAS')
        self.pending = current
        self.directory = directory
        self.seal = hashlib.sha256(encode([current, directory])).hexdigest()
        return dict(transaction_verified=True, commit_performed=False, publication_acceptance=False)

    def _close_before_write(self):
        check(raw_pair(self.db) == self.baseline, 'before-SQL-physical-CAS')
        check(self.logical() == self.before, 'before-SQL-logical-preimage')
        check(raw_pair(self.db) == self.baseline, 'before-SQL-physical-after-logical-CAS')
        check(set(os.listdir(self.parent)) == set(self.names) | {self.db.name + s for s in self.baseline}, 'before-SQL-closed-namespace')
        for name, value in self.names.items():
            check(signature(self.parent / name) == value, 'before-SQL-other-file')
        check(signature(self.parent) == self.initial_directory, 'before-SQL-directory-CAS')
        for p, v in self.nodes.items():
            check([signature(p)[i] for i in (0, 1, 5, 6, 7)] == v, 'before-SQL-ancestor')
        for suffix in ('', '-wal', '-shm', '-journal'):
            try:
                actual = signature(str(self.db) + suffix)
            except FileNotFoundError:
                actual = None
            expected = self.baseline.get(suffix)
            check(actual == (expected['signature9'] if expected else None), 'before-SQL-final-leaf')
        self._direct_vector(self.baseline, self.initial_directory)

    def close_pending(self):
        check(self.thread == threading.get_ident() and self._core() == self.core and self.connection.in_transaction and (self.phase == 'writing') and (self.pending is not None) and (hashlib.sha256(encode([self.pending, self.directory])).hexdigest() == self.seal), 'immutable-owned-pending-SQL')
        check(self.logical() == self.after, 'pending-SQL-five-row-delta')
        check(raw_pair(self.db, journal=True) == self.pending, 'pending-SQL-physical-CAS')
        self.close_passive()

    def close_passive(self):
        check(self.pending is not None, 'no-owned-pending-pair')
        check(set(os.listdir(self.parent)) == set(self.names) | {self.db.name + s for s in self.pending}, 'pending-SQL-closed-namespace')
        for name, value in self.names.items():
            check(signature(self.parent / name) == value, 'pending-SQL-other-file')
        check(signature(self.parent) == self.directory, 'pending-SQL-parent-CAS')
        for p, v in self.nodes.items():
            check([signature(p)[i] for i in (0, 1, 5, 6, 7)] == v, 'pending-SQL-ancestor')
        for suffix in ('', '-wal', '-shm', '-journal'):
            p = Path(str(self.db) + suffix)
            try:
                actual = signature(p)
            except FileNotFoundError:
                actual = None
            expected = self.pending.get(suffix)
            check(actual == (expected['signature9'] if expected else None), 'pending-SQL-final-companion')
        self._direct_vector(self.pending, self.directory)

    def _direct_vector(self, pairs, directory):
        check(set(os.listdir(self.parent)) == set(self.names) | {self.db.name + s for s in pairs}, 'terminal-reader-namespace')
        leaves = {self.parent: directory, **{self.parent / name: value for name, value in self.names.items()}}
        leaves.update({Path(str(self.db) + s): pairs[s]['signature9'] if s in pairs else None for s in ('', '-wal', '-shm', '-journal')})
        for p, value in leaves.items():
            try:
                z = os.lstat(p)
                actual = [z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns, z.st_mode, z.st_uid, z.st_gid, z.st_nlink]
            except FileNotFoundError:
                actual = None
            check(actual == value, 'terminal-reader-leaf')
        for p, value in self.nodes.items():
            z = os.lstat(p)
            check([z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid] == value, 'terminal-reader-ancestor')

    def commit(self, *args, **kwargs):
        raise Held('owning-native-reader-commit-phase-handshake-not-installed')

    def rollback_owned(self):
        check(self._core() == self.core and self.thread == threading.get_ident() and self.connection.in_transaction, 'same-owned-reader-transaction')
        if self.pending is not None:
            self.close_pending()
        self.connection.rollback()
        self.phase = 'rolled-back'
        restored = raw_pair(self.db)
        directory = signature(self.parent)
        check(self.logical() == self.before and (not self.connection.in_transaction), 'reader-owned-rollback-logical')
        check(raw_pair(self.db) == restored, 'reader-owned-rollback-physical-CAS')
        old = self.baseline['']['signature9']
        new = restored['']['signature9']
        check(all((old[i] == new[i] for i in (0, 1, 5, 6, 7, 8))) and restored['']['xattrs'] == self.baseline['']['xattrs'], 'rollback-owned-main-incarnation')
        if self.mode == 'delete':
            check(restored['']['sha256'] == self.baseline['']['sha256'], 'rollback-original-main-bytes')
        self.pending = restored
        self.directory = directory
        self.seal = hashlib.sha256(encode([restored, directory])).hexdigest()
        self.close_passive()
        return dict(transaction_rollback_verified=True, publication_acceptance=False, final_ack_required=True)
if __name__ == '__main__':
    print(json.dumps(dict(executable=False, installed=False, sql_authority=False, missing='exact installed aggregate commit fence, owning reader phase successor and terminal closure')))
