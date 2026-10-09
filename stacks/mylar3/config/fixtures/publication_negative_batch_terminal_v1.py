"""Owning five-retired terminal marker clearance, prospective source only.

No SQL, reader resume, ordinary Writer reacquisition, generic bypass or publication
acceptance is minted here. A durable exact clear-ready intent precedes unlink.
"""
from pathlib import Path
_PORTABLE_ROOT = next((p for p in Path(__file__).resolve().parents if (p / '.portable-cohort').is_file()))
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import stat
import threading
import weakref
_KEY = object()
_SEALS = weakref.WeakKeyDictionary()
_STATES = weakref.WeakKeyDictionary()
NAME = 'negative-retirement-v1.pending'
SUCCESSOR = 'negative-retirement-v1.terminal-pending'

class Held(ValueError):
    pass

def check(value, reason):
    if not value:
        raise Held(reason)

def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def nine(z):
    return [z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns, z.st_mode, z.st_uid, z.st_gid, z.st_nlink]

def five(z):
    return [z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid]

def direct(path, expected):
    try:
        value = nine(os.lstat(path))
    except FileNotFoundError:
        value = None
    check(value == expected, 'terminal-direct-leaf')

def merge(*vectors):
    value = {}
    for vector in vectors:
        check(type(vector) is dict, 'terminal-plain-vector')
        for p, fact in vector.items():
            p = Path(p)
            fact = list(fact)
            check(p not in value or value[p] == fact, 'terminal-conflicting-vector')
            value[p] = fact
    return value

def canonical(path):
    p = Path(path)
    check(p.is_absolute() and '..' not in p.parts and (p.resolve(strict=True) == p), 'terminal-canonical')
    for node in (p, *p.parents):
        check(not node.is_symlink(), 'terminal-parent-link')
    return p

def read_exact(path, expected, maximum):
    check(stat.S_ISREG(expected[5]) and expected[8] == 1 and (0 < expected[2] <= maximum), 'terminal-file-bound')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        check(nine(os.fstat(fd)) == expected, 'terminal-read-FD')
        raw = bytearray()
        while len(raw) <= expected[2]:
            block = os.read(fd, min(65536, expected[2] + 1 - len(raw)))
            if not block:
                break
            raw.extend(block)
        check(len(raw) == expected[2] and nine(os.fstat(fd)) == expected, 'terminal-readback')
        direct(path, expected)
        return bytes(raw)
    finally:
        os.close(fd)

class TerminalClearance:
    """One exact committed reader + retired five under the same held Writer."""

    def __init__(self, key, reservation, commit):
        check(key is _KEY, 'owning-terminal-factory')
        self.reservation = reservation
        self.commit = commit
        self.batch = reservation.batch
        self.thread = threading.get_ident()
        self.writer = self.batch.writer
        self.local = self.writer.local
        self.original_ids = tuple((id(p) for p in self.batch.preparations))
        check(len(self.original_ids) == 5 and len(set(self.original_ids)) == 5, 'exact-five-original-identities')
        check(commit.reservation is reservation and commit.reader is reservation.reader, 'same-committed-reader-reservation')
        self.commit_binding = copy.deepcopy(commit.binding)
        check(self.commit_binding['phase'] == 'committed' and self.commit_binding['reservation_id'] == id(reservation) and (self.commit_binding['preparation_ids'] == list(self.original_ids)), 'committed-five-binding')
        self.marker = canonical(self.batch.marker)
        check(self.marker == self.writer.root / NAME, 'fixed-owning-marker')
        self.marker_fact = list(self.batch.marker_fact)
        self.marker_raw = read_exact(self.marker, self.marker_fact, 65536)
        check(hashlib.sha256(self.marker_raw).hexdigest() == self.batch.marker_sha, 'exact-original-marker-bytes')
        self.initial_root = list(self.batch.root_fact)
        self.root_names = set(self.batch.writer_names)
        self.projection = reservation.projection
        self.directory = self.batch.journal.parent / (self.batch.journal.name + '.terminal-v1')
        check(not any((self.directory.is_relative_to(Path(p)) or Path(p).is_relative_to(self.directory) for p in self.batch.controller.roots)), 'terminal-custody-outside-all-publication-roots')
        check(not os.path.lexists(self.directory), 'exclusive-terminal-custody')
        canonical(self.directory.parent)
        parent = os.lstat(self.directory.parent)
        check(stat.S_IMODE(parent.st_mode) == 448 and parent.st_uid == os.geteuid(), 'private-terminal-parent')
        self.parents = {p: five(os.lstat(p)) for p in (self.directory.parent, *self.directory.parent.parents)}
        check(all((stat.S_ISDIR(v[2]) for v in self.parents.values())), 'terminal-custody-parent')
        self.phase = 'pending'
        self.receipts = {}
        self.directory_fact = None
        self.root_fact = self.initial_root
        self.successor_fact = None
        self.successor_raw = None
        self.core = self._core()
        _SEALS[self] = self.core
        self._update_state()
        self._prove()

    def _core(self):
        return hashlib.sha256(encode(dict(objects=[id(self.reservation), id(self.commit), id(self.batch), id(self.writer), id(self.local), id(self.projection)], thread=self.thread, original_ids=self.original_ids, commit=self.commit_binding, marker=str(self.marker), marker_fact=self.marker_fact, marker_sha=hashlib.sha256(self.marker_raw).hexdigest(), root=self.initial_root, names=sorted(self.root_names), directory=str(self.directory), parents={str(p): v for p, v in self.parents.items()}, reservation_core=self.reservation.core))).hexdigest()

    def _state(self):
        return hashlib.sha256(encode(dict(phase=self.phase, receipts=self.receipts, directory_fact=self.directory_fact, root_fact=self.root_fact, successor_fact=self.successor_fact, successor_sha=hashlib.sha256(self.successor_raw).hexdigest() if self.successor_raw else None))).hexdigest()

    def _update_state(self):
        self.state = self._state()
        _STATES[self] = self.state

    def _lifetime(self):
        check(self._core() == self.core == _SEALS.get(self) and self._state() == self.state == _STATES.get(self) and (self.thread == threading.get_ident()) and (self.writer.local is self.local) and (getattr(self.local[1], 'depth', 0) > 0) and (tuple((id(p) for p in self.batch.preparations)) == self.original_ids), 'immutable-terminal-lifetime')
        self.reservation._lifetime()
        check(self.projection is self.reservation.projection and self.batch is self.reservation.batch and (self.writer is self.batch.writer), 'same-owning-terminal-components')
        check(self.commit.reservation is self.reservation and self.commit.reader is self.reservation.reader, 'same-reader-terminal-identity')

    def _prove(self):
        self._lifetime()
        r = self.reservation
        b = self.batch
        q = self.projection
        check(q.phases == ['retained'] * 5 and q.pending is None, 'all-five-retired-durable-phases')
        census, records = b.guard.registry_snapshot(b.controller.database, b.writer.root / 'publication-v1.json')
        check(b.guard.same_json(census, b.census) and b.guard.same_json(records, b.records), 'terminal-current-complete-census')
        for bound in r.bound:
            proof = b.controller.observe(b.writer, {'allowed': [bound['owner']]})
            check(len(proof['observed']) == 1 and proof['observed'][0]['catalog']['path'] == bound['counterpart'], 'terminal-current-proper-owner')
            check(b.negative._protected_paths(b.controller, b.writer) == set(map(Path, bound['protected_paths'])), 'terminal-protected-originals')
            for path, fact in bound['file_facts'].items():
                if Path(path) in r.sources:
                    continue
                actual = q.k._fact(Path(path), 1)
                check(actual['signature9'] == fact['signature9'] and actual['sha256'] == fact['sha256'] and (b.negative.attrs(Path(path)) == bound['xattrs'][path]), 'terminal-preserved-custody')
        q.close()
        files, nodes, absent = self.commit.close_committed(r)
        check(self.commit.binding == self.commit_binding, 'terminal-immutable-committed-binding')
        files = merge(r.files, files)
        nodes = merge(r.nodes, q.nodes, self.parents, nodes)
        check(type(absent) is tuple, 'terminal-plain-absence-vector')
        if self.phase == 'pending':
            check(read_exact(self.marker, self.marker_fact, 65536) == self.marker_raw, 'terminal-marker-readback')
        namespaces = q.expected_namespaces()
        self._direct(files, nodes, absent, namespaces)
        return (files, nodes, absent, namespaces)

    def _direct(self, files, nodes, absent, namespaces):
        b = self.batch
        q = self.projection
        for db in (b.controller.database, b.controller.native_database):
            for suffix in ('-journal', '-wal', '-shm'):
                direct(str(db) + suffix, None)
        for bound in self.reservation.bound:
            claims = bound['complete_catalog_absence']
            for p, v in claims['passive_claim_files'].items():
                direct(p, v)
            for group in ('passive_claim_ancestors', 'passive_scope_ancestors'):
                for p, v in claims[group].items():
                    try:
                        actual = five(os.lstat(p))
                    except FileNotFoundError:
                        actual = None
                    check(actual == v, 'terminal-complete-claim-ancestor')
        for p in absent:
            direct(p, None)
        for p, v in files.items():
            direct(p, v)
        for p, v in nodes.items():
            check(five(os.lstat(p)) == v, 'terminal-direct-ancestor')
        expected_names = self.root_names if self.phase == 'pending' else self.root_names - {NAME}
        if self.successor_fact is not None and self.phase != 'complete':
            expected_names = expected_names | {SUCCESSOR}
        check(set(os.listdir(self.writer.root)) == expected_names, 'terminal-Writer-namespace')
        direct(self.writer.root, self.root_fact)
        direct(self.marker, self.marker_fact if self.phase == 'pending' else None)
        direct(self.writer.root / SUCCESSOR, self.successor_fact if self.phase != 'complete' else None)
        check(set(os.listdir(q.journal)) == {p.name for p in q.receipts}, 'terminal-phase-receipt-census')
        direct(q.journal, q.directory)
        for p, (fact, digest) in q.receipts.items():
            direct(p, fact)
        for parent, values in namespaces.items():
            check(set(os.listdir(parent)) == set(values), 'terminal-all-five-namespace')
            direct(parent, q.parents[parent])
            for name, v in values.items():
                direct(parent / name, v)
        for member in q.members:
            direct(member['source'], None)
        if self.directory_fact is not None:
            check(set(os.listdir(self.directory)) == set(self.receipts), 'terminal-private-receipt-census')
            direct(self.directory, self.directory_fact)
            for name, (fact, digest) in self.receipts.items():
                direct(self.directory / name, fact)

    def _write(self, name, body):
        check(name in ('clear-ready.json', 'cleared.json', 'uncertain.json'), 'finite-terminal-receipt')
        raw = encode(body)
        check(len(raw) <= 16 * 1024 ** 2, 'terminal-receipt-bound')
        d = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            check(nine(os.fstat(d)) == self.directory_fact, 'terminal-owned-receipt-directory-FD')
            fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 384, dir_fd=d)
            try:
                os.write(fd, raw)
                os.fsync(fd)
                os.lseek(fd, 0, os.SEEK_SET)
                observed = bytearray()
                while len(observed) < len(raw):
                    block = os.read(fd, len(raw) - len(observed))
                    if not block:
                        break
                    observed.extend(block)
                check(bytes(observed) == raw, 'terminal-intended-receipt-readback')
                fact = nine(os.fstat(fd))
                check(nine(os.stat(name, dir_fd=d, follow_symlinks=False)) == fact, 'terminal-receipt-incarnation')
            finally:
                os.close(fd)
            os.fsync(d)
            self.directory_fact = nine(os.fstat(d))
            direct(self.directory, self.directory_fact)
        finally:
            os.close(d)
        self.receipts[name] = (fact, hashlib.sha256(raw).hexdigest())
        self._update_state()

    def _create_directory(self):
        d = os.open(self.directory.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            check(five(os.fstat(d)) == self.parents[self.directory.parent], 'terminal-parent-FD')
            for p, v in self.parents.items():
                check(five(os.lstat(p)) == v, 'terminal-before-create-parent')
            os.mkdir(self.directory.name, mode=448, dir_fd=d)
            os.fsync(d)
            z = os.stat(self.directory.name, dir_fd=d, follow_symlinks=False)
            check(stat.S_ISDIR(z.st_mode) and stat.S_IMODE(z.st_mode) == 448 and (z.st_uid == os.geteuid()), 'private-terminal-custody')
            self.directory_fact = nine(z)
            direct(self.directory, self.directory_fact)
            self._update_state()
        finally:
            os.close(d)

    def _successor(self):
        self._prove()
        raw = encode(dict(version=1, kind='negative-terminal-presence-hold', nonce=self.batch.nonce, binding_sha256=self.core, writer_root_identity=self.initial_root, operation_root=str(self.directory), publication_acceptance=False))
        d = os.open(self.writer.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            files, nodes, absent, namespaces = self._prove()
            check(nine(os.fstat(d)) == self.root_fact, 'successor-original-Writer-FD')
            self._direct(files, nodes, absent, namespaces)
            fd = os.open(SUCCESSOR, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 384, dir_fd=d)
            try:
                os.write(fd, raw)
                os.fsync(fd)
                os.lseek(fd, 0, os.SEEK_SET)
                check(os.read(fd, len(raw) + 1) == raw, 'successor-intended-readback')
                fact = nine(os.fstat(fd))
                check(nine(os.stat(SUCCESSOR, dir_fd=d, follow_symlinks=False)) == fact, 'successor-relative-leaf')
            finally:
                os.close(fd)
            os.fsync(d)
            root_fact = nine(os.fstat(d))
            check([root_fact[i] for i in (0, 1, 5, 6, 7, 8)] == [self.initial_root[i] for i in (0, 1, 5, 6, 7, 8)], 'successor-same-Writer-identity')
            self.successor_raw = raw
            self.successor_fact = fact
            self.root_fact = root_fact
            self._update_state()
            self._prove()
        finally:
            os.close(d)

    def clear(self):
        check(self.phase == 'pending' and self.directory_fact is None, 'no-terminal-replay')
        self._prove()
        self._successor()
        self._create_directory()
        intent = dict(version=1, kind='five-retired-negative-clear-ready', binding_sha256=self.core, commit=self.commit_binding, marker_sha256=hashlib.sha256(self.marker_raw).hexdigest(), marker_fact=self.marker_fact, members=copy.deepcopy(self.projection.members), phase_facts=copy.deepcopy(self.projection.facts), phase_receipts={str(p): v for p, v in self.projection.receipts.items()}, publication_acceptance=False)
        self._write('clear-ready.json', intent)
        d = os.open(self.writer.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        marker_fd = None
        try:
            marker_fd = os.open(NAME, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=d)
            check(nine(os.fstat(marker_fd)) == self.marker_fact, 'terminal-exact-marker-FD')
            files, nodes, absent, namespaces = self._prove()
            check(nine(os.fstat(d)) == self.root_fact, 'terminal-exact-Writer-FD')
            check(nine(os.fstat(marker_fd)) == self.marker_fact, 'terminal-last-marker-FD')
            check(nine(os.stat(NAME, dir_fd=d, follow_symlinks=False)) == self.marker_fact, 'terminal-last-relative-marker')
            self._direct(files, nodes, absent, namespaces)
            os.unlink(NAME, dir_fd=d)
            os.fsync(d)
            self.phase = 'cleared'
            self.root_fact = nine(os.fstat(d))
            self._update_state()
            direct(self.writer.root, self.root_fact)
            check(os.fstat(marker_fd).st_nlink == 0, 'terminal-only-exact-marker-unlinked')
            self._prove()
            self._write('cleared.json', dict(version=1, kind='five-retired-negative-cleared', binding_sha256=self.core, clear_ready_sha256=self.receipts['clear-ready.json'][1], commit_receipt=self.commit_binding['receipt'], publication_acceptance=False))
            files, nodes, absent, namespaces = self._prove()
            successor_fd = os.open(SUCCESSOR, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=d)
            try:
                check(nine(os.fstat(successor_fd)) == self.successor_fact, 'last-successor-FD')
                check(nine(os.stat(SUCCESSOR, dir_fd=d, follow_symlinks=False)) == self.successor_fact, 'last-successor-relative-leaf')
                self._direct(files, nodes, absent, namespaces)
                os.unlink(SUCCESSOR, dir_fd=d)
                os.fsync(d)
                check(os.fstat(successor_fd).st_nlink == 0, 'only-owned-successor-unlinked')
            finally:
                os.close(successor_fd)
            self.phase = 'complete'
            self.root_fact = nine(os.fstat(d))
            self._update_state()
            return self.status()
        except BaseException:
            try:
                os.stat(SUCCESSOR, dir_fd=d, follow_symlinks=False)
            except FileNotFoundError:
                try:
                    fd = os.open(SUCCESSOR, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 384, dir_fd=d)
                    try:
                        os.write(fd, self.successor_raw)
                        os.fsync(fd)
                    finally:
                        os.close(fd)
                    os.fsync(d)
                except OSError:
                    pass
            self.phase = 'uncertain'
            self._update_state()
            raise Held('terminal-clear-uncertain-evidence-retained') from None
        finally:
            if marker_fd is not None:
                os.close(marker_fd)
            os.close(d)

    def status(self):
        check(self.phase in ('pending', 'complete'), 'terminal-uncertain-requires-review')
        self._prove()
        return dict(version=1, outcome='cleared' if self.phase == 'complete' else 'retained-pending', retired_count=5, reader_commit_verified=True, marker_cleared=self.phase == 'complete', publication_acceptance=False, reader_resume_authority=False, mutation_authority=False)

def from_retired(reservation, commit):
    modules = []
    for name, kind in (('publication_negative_batch_transition', 'NegativeBatchReservation'), ('publication_reader_sql_commit', 'ReaderSQLCommit')):
        try:
            m = importlib.import_module('mylar.' + name)
        except ModuleNotFoundError:
            raise Held('owning-terminal-components-not-installed') from None
        p = Path(m.__file__)
        check(p.parent == Path('/app/mylar3/mylar') and p.resolve() == p, 'installed-terminal-component')
        modules.append((m, kind))
    check(type(reservation) is getattr(*modules[0]) and type(commit) is getattr(*modules[1]), 'exact-owning-terminal-types')
    return TerminalClearance(_KEY, reservation, commit)
