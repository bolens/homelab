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
import weakref
_SEALS = weakref.WeakKeyDictionary()
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
        self.tasks_database = self.root / 'tasks.sqlite'
        self.tasks_pair = copy.deepcopy(self.pairs['tasks.sqlite'])
        self.sql_operation = None
        self.phase = 'before'
        self.batch = None
        self.sql = None
        self.commit_custody = None
        self.sql_core = None
        self.commit_core = None
        self.core = self._core()
        self._seal()
        self.close_native_phase_passive(None)

    def _core(self):
        return hashlib.sha256(encode(dict(plan=self.plan, schema=self.schema, before=self.before, after=self.after, custody=self.custody, tasks_path=str(self.tasks_database), tasks_pair=self.tasks_pair, root=str(self.root), restore=str(self.restore), scratch=str(self.scratch), operation=str(self.operation), origin=[self.origin_core, self.origin_state], objects=[id(self.original), id(self.invocation), id(self.disk), *[id(p) for p in self.preparations]], nodes={str(p): v for p, v in self.nodes.items()}))).hexdigest()

    def _state(self):
        return hashlib.sha256(encode(dict(phase=self.phase, pairs=self.pairs, directory=self.directory, restore_directory=self.restore_directory, names=sorted(self.names), batch=id(self.batch), sql=id(self.sql), sql_core=self.sql_core, commit=id(self.commit_custody), commit_core=self.commit_core, sql_operation=str(self.sql_operation)))).hexdigest()

    def _seal(self):
        self.state = self._state()
        _SEALS[self] = (self.core, self.state)

    def _origin(self):
        check(threading.get_ident() == self.thread and self._core() == self.core and (self._state() == self.state) and (_SEALS.get(self) == (self.core, self.state)), 'immutable-reader-phase')
        check(self.original._core == self.origin_core and self.original._state_seal == self.origin_state and (self.original._core_value() == self.origin_core) and (self.original._state_value() == self.origin_state), 'original-admission-must-not-reseal')
        self.invocation.close_passive()

    def _vectors(self):
        if self.sql is not None:
            return self._sql_vectors()
        files = merge(self.invocation._facts, {self.root: self.directory, self.restore: self.restore_directory})
        for base, pairs in ((self.root, self.pairs), (self.restore, self.custody)):
            for name, facts in pairs.items():
                for suffix in ('', '-wal', '-shm', '-journal'):
                    files[Path(str(base / name) + suffix)] = tuple(facts[suffix]['signature9']) if suffix in facts else None
        nodes = merge(self.invocation._ancestors, self.nodes)
        return (files, nodes)

    def close_native_phase_passive(self, fence):
        self._origin()
        if fence is not None:
            check(fence.reader is self and fence.preparation in self.preparations, 'reader-native-binding')
        if self.sql is not None:
            self._sql_passive()
            return
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
            try:
                s = os.lstat(p)
                actual = (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode, s.st_uid, s.st_gid, s.st_nlink)
            except FileNotFoundError:
                actual = None
            check(actual == fact, 'reader-phase-file')
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

    def _installed(self, name, cls, obj):
        try:
            module = importlib.import_module('mylar.' + name)
        except ModuleNotFoundError:
            raise Held('owning-' + name + '-not-installed') from None
        p = Path(module.__file__)
        check(p.parent == Path('/app/mylar3/mylar') and p.resolve() == p and (type(obj) is getattr(module, cls)), 'exact-installed-' + cls)
        return module

    def validate_sql_start(self, batch):
        self._origin()
        self._installed('publication_negative_batch_transition', 'NegativeBatchReservation', batch)
        check(self.phase == 'before' and self.sql is None and (batch.reader is self) and (batch.batch.preparations == self.preparations), 'exact-staged-reader-start')
        batch.revalidate_staged(self, self.preparations)
        current = {name: self.disk.pair(self.root / name) for name in self.pairs}
        check(current == self.pairs and self.original._observe() == self.before, 'exact-reader-before-SQL')
        check({name: self.disk.pair(self.root / name) for name in self.pairs} == current, 'before-SQL-pair-CAS')
        self.close_native_phase_passive(None)

    def bind_sql_operation(self, journal):
        self._origin()
        journal = Path(journal)
        check(self.phase == 'before' and self.sql_operation is None and journal.is_absolute() and (journal.resolve() == journal) and (not any((journal.is_relative_to(root) or root.is_relative_to(journal) for root in (self.root, self.restore, self.scratch)))), 'exclusive-SQL-operation-scope')
        z = os.lstat(journal)
        check(z.st_mode & 511 == 448 and z.st_uid == os.geteuid() and (not os.listdir(journal)), 'empty-private-SQL-operation')
        self.sql_operation = journal
        self._seal()

    def register_sql(self, sql, reservation):
        self._origin()
        self._installed('publication_reader_sql_custody', 'SQLWritingCustody', sql)
        self._installed('publication_negative_batch_transition', 'NegativeBatchReservation', reservation)
        check(self.phase == 'before' and self.sql is None and (reservation.reader is self) and (reservation.batch.preparations == self.preparations), 'one-reader-SQL-successor')
        check(sql.thread == self.thread and sql._core() == sql.core and (sql.db == self.root / 'database.sqlite') and (sql.disk is self.disk) and (sql.plan == self.plan) and (sql.before == self.before['database.sqlite']) and (sql.after == self.after['database.sqlite']) and (sql.baseline == self.pairs['database.sqlite']) and (sql.pending is None), 'exact-reader-SQL-custody')
        sql._close_before_write()
        self.batch = reservation
        self.sql = sql
        self.sql_core = sql.core
        self.phase = 'sql-writing'
        self._seal()
        self._sql_passive()

    def _sql_vectors(self):
        check(self.sql._core() == self.sql_core, 'immutable-reader-SQL-core')
        if self.commit_custody is not None:
            check(self.commit_custody.core == self.commit_core, 'immutable-reader-commit-core')
            supplied_files, supplied_nodes = self.commit_custody.vectors()
        else:
            sql = self.sql
            pair = sql.pending if sql.pending is not None else sql.baseline
            directory = sql.directory if sql.pending is not None else sql.initial_directory
            supplied_files = {sql.parent: directory, **{sql.parent / n: v for n, v in sql.names.items()}}
            supplied_files.update({Path(str(sql.db) + suffix): pair[suffix]['signature9'] if suffix in pair else None for suffix in ('', '-wal', '-shm', '-journal')})
            supplied_nodes = sql.nodes
        files = {Path(p): tuple(v) if v is not None else None for p, v in supplied_files.items()}
        stable = merge(self.invocation._facts, {self.restore: self.restore_directory})
        for base, pairs in ((self.restore, self.custody), (self.root, {'tasks.sqlite': self.pairs['tasks.sqlite']})):
            for name, pair in pairs.items():
                for suffix in ('', '-wal', '-shm', '-journal'):
                    stable[Path(str(base / name) + suffix)] = tuple(pair[suffix]['signature9']) if suffix in pair else None
        for p, v in stable.items():
            check(p not in files or files[p] == v, 'conflicting-SQL-reader-vector')
            files[p] = v
        nodes = merge(self.invocation._ancestors, self.nodes, supplied_nodes)
        return (files, nodes)

    def _sql_passive(self):
        if self.commit_custody is not None:
            self.commit_custody.close_passive()
        elif self.sql.pending is not None:
            self.sql.close_passive()
        else:
            self.sql._direct_vector(self.sql.baseline, self.sql.initial_directory)
        files, nodes = self._sql_vectors()
        for p, v in files.items():
            try:
                z = os.lstat(p)
                actual = (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns, z.st_mode, z.st_uid, z.st_gid, z.st_nlink)
            except FileNotFoundError:
                actual = None
            check(actual == v, 'reader-SQL-terminal-file')
        for p, v in nodes.items():
            z = os.lstat(p)
            check((z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) == v, 'reader-SQL-terminal-ancestor')

    def revalidate_sql_writing(self, sql, reservation):
        self._origin()
        check(self.phase == 'sql-writing' and self.sql is sql and (self.batch is reservation) and (self.commit_custody is None), 'exact-reader-SQL-writing')
        if sql.pending is None:
            sql._close_before_write()
        else:
            sql.close_pending()
        self._sql_passive()

    def sql_syscall_controls(self, sql, reservation):
        self.revalidate_sql_writing(sql, reservation)
        return self._sql_vectors()

    def _accept(self, custody, phase):
        self._origin()
        self._installed('publication_reader_sql_commit', 'ReaderSQLCommit', custody)
        check(custody.reader is self and custody.reservation is self.batch and (custody.sql_custody is self.sql), 'exact-reader-commit-successor')
        if phase == 'committed':
            check(self.phase == 'sql-writing' and self.commit_custody is None, 'one-reader-commit-handoff')
            custody.revalidate_committed()
        else:
            check(self.phase == 'committed' and self.commit_custody is custody, 'one-reader-reverse-handoff')
            custody.revalidate_reversed()
        self.commit_custody = custody
        self.commit_core = custody.core
        self.phase = phase
        self._seal()
        self.close_native_phase_passive(None)

    def accept_committed(self, custody):
        self._accept(custody, 'committed')

    def accept_reversed(self, custody):
        self._accept(custody, 'rolled-back')

    def accept_uncommitted_rollback(self, sql, reservation):
        self._origin()
        check(self.phase == 'sql-writing' and self.sql is sql and (self.batch is reservation) and (self.commit_custody is None) and (sql.phase == 'rolled-back') and (not sql.connection.in_transaction), 'exact-owned-uncommitted-rollback')
        current = self.disk.pair(sql.db)
        check(current == sql.pending and self.original._observe() == self.before, 'rollback-reader-exact-preimage')
        check(self.disk.pair(sql.db) == current, 'rollback-reader-physical-CAS')
        sql.close_passive()
        self._sql_passive()
        self.phase = 'rolled-back'
        self._seal()
        self.close_native_phase_passive(None)

    def revalidate_committed(self, fence):
        self._origin()
        check(self.phase == 'committed' and self.commit_custody is not None, 'reader-commit-required')
        self.commit_custody.revalidate_committed()
        self.close_native_phase_passive(fence)

    def revalidate_rollback_ready(self, fence):
        self._origin()
        check(self.phase in ('before', 'rolled-back'), 'reader-rollback-required-before-source')
        if self.commit_custody is not None:
            self.commit_custody.revalidate_reversed()
        else:
            check(self.original._observe() == self.before, 'reader-original-all-tables')
        self.close_native_phase_passive(fence)

    def revalidate_sql_observed(self, custody, reservation):
        self._origin()
        self._installed('publication_reader_sql_commit', 'ReaderSQLCommit', custody)
        check(custody.reader is self and custody.reservation is reservation and (reservation is self.batch) and (custody.sql_custody is self.sql) and (custody.tasks_pair == self.tasks_pair), 'exact-observed-SQL-successor')
        check(self.commit_custody in (None, custody), 'one-observed-SQL-successor')
        self._stable_vectors_direct()

    def _stable_vectors_direct(self):
        files = merge(self.invocation._facts, {self.restore: self.restore_directory})
        for base, pairs in ((self.restore, self.custody), (self.root, {'tasks.sqlite': self.tasks_pair})):
            for name, pair in pairs.items():
                for suffix in ('', '-wal', '-shm', '-journal'):
                    files[Path(str(base / name) + suffix)] = tuple(pair[suffix]['signature9']) if suffix in pair else None
        nodes = merge(self.invocation._ancestors, self.nodes)
        for p, v in files.items():
            try:
                z = os.lstat(p)
                actual = (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns, z.st_mode, z.st_uid, z.st_gid, z.st_nlink)
            except FileNotFoundError:
                actual = None
            check(actual == v, 'stable-reader-SQL-control')
        for p, v in nodes.items():
            z = os.lstat(p)
            check((z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) == v, 'stable-reader-SQL-ancestor')
        return (files, nodes)

    def sql_observed_controls(self, custody, reservation):
        self.revalidate_sql_observed(custody, reservation)
        return self._stable_vectors_direct()

    def revalidate_sql_reversing(self, custody, reverse, reservation):
        self.revalidate_sql_observed(custody, reservation)
        self._installed('publication_reader_sql_custody', 'SQLWritingCustody', reverse)
        check(self.phase == 'committed' and self.commit_custody is custody and (reverse.db == self.sql.db) and (reverse.disk is self.disk) and (reverse.plan == self.plan) and (reverse.before == self.after['database.sqlite']) and (reverse.after == self.before['database.sqlite']) and (reverse.baseline == custody.current), 'exact-owned-reader-reverse')
        reverse.close_pending()
        self._stable_vectors_direct()

    def sql_reverse_controls(self, custody, reverse, reservation):
        self.revalidate_sql_reversing(custody, reverse, reservation)
        return self._stable_vectors_direct()

    def close_original_rollback(self, reservation):
        self._origin()
        self._installed('publication_negative_batch_transition', 'NegativeBatchReservation', reservation)
        check(reservation.reader is self and tuple(reservation.batch.preparations) == self.preparations and (reservation.projection.phases == ['source'] * 5) and (self.phase in ('before', 'rolled-back')) and (self.commit_custody is None) and (self.batch in (None, reservation)), 'exact-original-reader-rollback-terminal')
        expected = self.sql.pending if self.sql is not None else self.pairs['database.sqlite']
        if self.sql is not None:
            check(self.sql.phase == 'rolled-back' and (not self.sql.connection.in_transaction), 'owned-original-SQL-rollback-required')
        current = self.disk.pair(self.root / 'database.sqlite')
        check(current == expected and self.disk.pair(self.tasks_database) == self.tasks_pair and (self.original._observe() == self.before), 'original-rollback-reader-all-tables')
        check(self.disk.pair(self.root / 'database.sqlite') == current, 'original-rollback-final-main-CAS')
        self.close_native_phase_passive(None)
        files, nodes = self._vectors()
        return (copy.deepcopy(files), copy.deepcopy(nodes))

    def original_rollback_binding(self, reservation):
        self.close_original_rollback(reservation)
        return copy.deepcopy(dict(version=1, reader_core=self.core, phase=self.phase, reservation_id=id(reservation), preparation_ids=[id(p) for p in self.preparations], before=self.before, main_pair=self.sql.pending if self.sql is not None else self.pairs['database.sqlite'], tasks_pair=self.tasks_pair, sql_phase=self.sql.phase if self.sql is not None else None, publication_acceptance=False, final_ack_required=True))

    def commit_staged(self, batch):
        self.validate_sql_start(batch)
        try:
            module = importlib.import_module('mylar.publication_reader_sql_commit')
        except ModuleNotFoundError:
            raise Held('owning-SQL-preopen-factory-not-installed-before-SQL') from None
        p = Path(module.__file__)
        check(p.parent == Path('/app/mylar3/mylar') and p.resolve() == p, 'installed-owning-SQL-factory')
        check(hasattr(module, 'prepare_existing'), 'owning-SQL-preopen-factory-not-installed-before-SQL')
        custody = module.prepare_existing(self, batch)
        self._installed('publication_reader_sql_commit', 'ReaderSQLCommit', custody)
        custody.commit()
        self.accept_committed(custody)
        return custody

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
    print(json.dumps(dict(executable=False, installed=False, sql_authority=False, missing='installed owning pre-open SQL intent factory and reviewed COMMIT custody')))
