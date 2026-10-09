"""Prospective stopped-reader phase projection; not installed or a JSON grant.

The current source does not mint an owning invocation or aggregate native fence.
Those exact package factories must be installed before commit_staged can reach SQL.
"""
from pathlib import Path
_PORTABLE_ROOT = next((p for p in Path(__file__).resolve().parents if (p / '.portable-cohort').is_file()))
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import sqlite3
import threading
_KEY = object()

class Held(ValueError):
    pass

def check(value, reason):
    if not value:
        raise Held(reason)

def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def signature(path):
    s = os.lstat(path)
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode, s.st_uid, s.st_gid, s.st_nlink)

def merge(*vectors):
    value = {}
    for vector in vectors:
        for path, fact in vector.items():
            p = Path(path)
            fact = tuple(fact)
            check(p not in value or value[p] == fact, 'conflicting-reader-vector')
            value[p] = fact
    return value

class StoppedReaderPhase:
    """Carried reader projection handed off before the durable native phase.

    Native controls and owned source aliases belong to NativePhaseFence. This
    class never mutates/reseals the frozen original admission/coordinator.
    """

    def __init__(self, key, admission):
        check(key is _KEY, 'owning-reader-phase-factory')
        admission.revalidate()
        self.original = admission
        self.thread = threading.get_ident()
        self.origin_core = admission._core
        self.origin_state = admission._state_seal
        self.invocation = admission._invocation
        self.disk = admission._disk
        self.plan = copy.deepcopy(admission._plan)
        self.schema = copy.deepcopy(admission._schema)
        self.before = copy.deepcopy(admission._observed)
        self.after = copy.deepcopy(admission._expected)
        self.root = admission._root
        self.restore = admission._restore
        self.scratch = admission._scratch
        self.operation = admission._operation
        self.preparations = tuple(admission._native)
        self.pairs = copy.deepcopy(admission._pairs)
        self.custody = copy.deepcopy(admission._custody)
        self.nodes = dict(admission._nodes)
        self.directory = admission._reader_directory
        self.restore_directory = admission._restore_directory
        self.names = set(admission._root_names)
        self.phase = 'before'
        self.batch = None
        self.core = self._core()
        self.state = self._state()
        self.close_native_phase_passive(None)

    def _core(self):
        return hashlib.sha256(encode(dict(plan=self.plan, schema=self.schema, before=self.before, after=self.after, custody=self.custody, root=str(self.root), restore=str(self.restore), scratch=str(self.scratch), operation=str(self.operation), origin=[self.origin_core, self.origin_state], objects=[id(self.original), id(self.invocation), id(self.disk), *[id(p) for p in self.preparations]], nodes={str(p): v for p, v in self.nodes.items()}))).hexdigest()

    def _state(self):
        return hashlib.sha256(encode(dict(phase=self.phase, pairs=self.pairs, directory=self.directory, restore_directory=self.restore_directory, names=sorted(self.names), batch=id(self.batch)))).hexdigest()

    def _origin(self):
        check(threading.get_ident() == self.thread and self._core() == self.core and (self._state() == self.state), 'immutable-reader-phase')
        check(self.original._core == self.origin_core and self.original._state_seal == self.origin_state and (self.original._core_value() == self.origin_core) and (self.original._state_value() == self.origin_state), 'original-admission-must-not-reseal')
        self.invocation.close_passive()

    def _vectors(self):
        files = merge(self.invocation._facts, {self.root: self.directory, self.restore: self.restore_directory})
        for base, pairs in ((self.root, self.pairs), (self.restore, self.custody)):
            for name, facts in pairs.items():
                for suffix, fact in facts.items():
                    files[Path(str(base / name) + suffix)] = tuple(fact['signature9'])
        nodes = merge(self.invocation._ancestors, self.nodes)
        return (files, nodes)

    def close_native_phase_passive(self, fence):
        self._origin()
        if fence is not None:
            check(fence.reader is self and fence.preparation in self.preparations, 'reader-native-binding')
        for base, pairs in ((self.root, self.pairs), (self.restore, self.custody)):
            for name, facts in pairs.items():
                for suffix in ('-journal', '-wal', '-shm'):
                    if suffix not in facts:
                        try:
                            os.lstat(str(base / name) + suffix)
                        except FileNotFoundError:
                            pass
                        else:
                            raise Held('unexpected-reader-companion')
        check(set(os.listdir(self.root)) == self.names, 'reader-root-census')
        files, nodes = self._vectors()
        for p, fact in files.items():
            s = os.lstat(p)
            check((s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode, s.st_uid, s.st_gid, s.st_nlink) == fact, 'reader-phase-file')
        for p, fact in nodes.items():
            s = os.lstat(p)
            check((s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid) == fact, 'reader-phase-ancestor')

    def native_syscall_controls(self, fence):
        self.close_native_phase_passive(fence)
        return self._vectors()

    def revalidate_before_native(self, preparation):
        check(self.phase == 'before' and preparation in self.preparations, 'exact-reader-before-purpose')
        self.original.revalidate()
        self.close_native_phase_passive(None)

    def revalidate_committed(self, fence):
        check(self.phase == 'committed', 'reader-commit-required')
        self.close_native_phase_passive(fence)
        check(self.original._observe() == self.after, 'reader-after-all-tables')
        for name, facts in self.pairs.items():
            check(self.disk.pair(self.root / name) == facts, 'reader-after-pair')
        self.close_native_phase_passive(fence)

    def revalidate_rollback_ready(self, fence):
        check(self.phase in ('before', 'rolled-back'), 'reader-rollback-required-before-source')
        self.close_native_phase_passive(fence)
        check(self.original._observe() == self.before, 'reader-original-all-tables')
        self.close_native_phase_passive(fence)

    def commit_staged(self, batch):
        try:
            module = importlib.import_module('mylar.publication_negative_batch')
        except ModuleNotFoundError:
            raise Held('aggregate-native-phase-not-installed-before-SQL') from None
        path = Path(module.__file__)
        check(path.parent == Path('/app/mylar3/mylar') and path.resolve() == path and (type(batch) is module.NegativeBatchReservation), 'exact-owning-native-batch')
        batch.revalidate_staged(self, self.preparations)
        raise Held('aggregate-SQL-phase-custody-handshake-not-installed-before-SQL')

def from_admission(admission):
    """Only the reviewed owning installed admission factory can hand off."""
    try:
        module = importlib.import_module('mylar.publication_reader_admission')
    except ModuleNotFoundError:
        raise Held('owning-reader-admission-not-installed') from None
    p = Path(module.__file__)
    check(p.parent == Path('/app/mylar3/mylar') and p.resolve() == p and (type(admission) is module.StoppedReaderAdmission), 'exact-owning-reader-admission')
    check(module.PARENT_SHA is not None, 'owning-parent-pin-not-installed')
    return StoppedReaderPhase(_KEY, admission)

def sql_five_transition(connection, disk, plan, before, after, *, rollback=False):
    """Exact SQL transaction body, called only by a future owning phase handshake.

    It never commits or opens a database. The caller must already own an actual
    stopped-reader transaction/physical CAS and must seal all native controls
    again before committing. No public CLI or source constructor calls this.
    """
    check(type(connection) is sqlite3.Connection and connection.in_transaction, 'owned-SQL-transaction')
    expected = after if rollback else before
    result = before if rollback else after
    disk.healthy(connection)
    check((disk.master(connection), disk.k.snapshot(connection), disk.book_rows(connection, plan)) == expected, 'exact-reader-preimage')
    if rollback:
        parameters = []
        for bid in plan['active_wrong_ids']:
            row = disk.k.row_decode(plan['before_rows'][bid])
            current = disk.k.row_decode(plan['after_rows'][bid])
            parameters.append((row[11], row[2], bid, current[11], current[2]))
    else:
        parameters = [[disk.k.untyped(v) for v in p] for p in plan['parameters']]
    for parameters_row in parameters:
        check(connection.execute('UPDATE BOOK SET DELETED_DATE=?, LAST_MODIFIED_DATE=? WHERE ID=? AND DELETED_DATE IS ? AND LAST_MODIFIED_DATE IS ?' if rollback else disk.k.SQL, parameters_row).rowcount == 1, 'exact-reader-five-row-update')
    check((disk.master(connection), disk.k.snapshot(connection), disk.book_rows(connection, plan)) == result, 'only-approved-reader-delta')
    disk.healthy(connection)
    return dict(transaction_verified=True, commit_performed=False, publication_acceptance=False)
if __name__ == '__main__':
    print(json.dumps(dict(executable=False, installed=False, sql_authority=False, missing='owning installed admission and aggregate native SQL phase custody handshake')))
