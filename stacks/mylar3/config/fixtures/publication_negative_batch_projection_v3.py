"""Exact finite five-member alias namespace projection, prospective source only.

This component performs observations and durable intent/witness writes. It does
not link/unlink media, open SQL, mint publication grants, or clear a native hold.
The owning batch adapter must combine it with the reviewed native/reader phase.
"""
from pathlib import Path
_PORTABLE_ROOT = next((p for p in Path(__file__).resolve().parents if (p / '.portable-cohort').is_file()))
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import threading
_KEY = object()
KERNEL = Path(str(_PORTABLE_ROOT / 'publication_negative_namespace_kernel.py'))
KERNEL_SHA = 'f35887c5dad8985baf41fb5861423c18f556db1311f0e4fde202021f4cb59633'

class Held(ValueError):
    pass

def check(value, reason):
    if not value:
        raise Held(reason)

def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def sig(p):
    s = os.lstat(p)
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode, s.st_uid, s.st_gid, s.st_nlink]

def canonical(p):
    p = Path(p)
    check(p.is_absolute() and p.resolve() == p and ('..' not in p.parts) and (not any((q.is_symlink() for q in (p, *p.parents)))), 'canonical')
    return p

def kernel():
    before = sig(KERNEL)
    raw = KERNEL.read_bytes()
    check(sig(KERNEL) == before and stat.S_ISREG(before[5]) and (before[6] == os.geteuid()) and (stat.S_IMODE(before[5]) == 384) and (before[8] == 1) and (hashlib.sha256(raw).hexdigest() == KERNEL_SHA), 'frozen-kernel')
    s = importlib.util.spec_from_loader('batch_projection_kernel', loader=None)
    m = importlib.util.module_from_spec(s)
    m.__file__ = str(KERNEL)
    exec(compile(raw, str(KERNEL), 'exec'), m.__dict__)
    return m

class BatchNamespace:
    """Only five explicit participant deltas are admitted in shared parents."""

    def __init__(self, key, participants, journal):
        check(key is _KEY and type(participants) in (list, tuple) and (len(participants) == 5), 'exact-five-owned-participants')
        check(all((type(v) is dict and set(v) == {'source', 'target', 'original'} for v in participants)), 'exact-reviewed-participant-fields')
        declared = [Path(v[name]) for v in participants for name in ('source', 'target')] + [Path(journal), KERNEL]
        entry = {p: [sig(p)[i] for i in (0, 1, 5, 6, 7)] for leaf in declared for p in leaf.parents}
        entry[Path(journal)] = [sig(journal)[i] for i in (0, 1, 5, 6, 7)]
        self.thread = threading.get_ident()
        self.k = kernel()
        self.journal = canonical(journal)
        j = sig(self.journal)
        check(stat.S_ISDIR(j[5]) and stat.S_IMODE(j[5]) == 448 and (j[6] == os.geteuid()) and (not os.listdir(self.journal)), 'empty-owned-journal')
        self.members = []
        paths = []
        for participant in participants:
            source = canonical(participant['source'])
            target = canonical(participant['target'])
            check(source.parent != target.parent and source != target and (not os.path.lexists(target)), 'distinct-absent-target')
            paths.extend((source, target))
            actual = self.k._fact(source, 1)
            check(actual == participant['original'], 'reviewed-full-original-CAS')
            self.members.append(dict(source=str(source), target=str(target), original=copy.deepcopy(actual)))
        check(len(set(paths)) == 10 and len({tuple(v['original']['signature9'][:2]) for v in self.members}) == 5, 'five-distinct-physical-originals')
        parents = set((p.parent for p in paths))
        check(self.journal not in parents and (not any((self.journal.is_relative_to(p) or p.is_relative_to(self.journal) for p in parents))), 'journal-disjoint')
        self.parents = {p: sig(p) for p in parents}
        self.namespaces = {p: self.k._namespace(p) for p in parents}
        self.nodes = {p: [sig(p)[i] for i in (0, 1, 5, 6, 7)] for leaf in (*parents, self.journal) for p in (leaf, *leaf.parents)}
        for p, v in entry.items():
            check([sig(p)[i] for i in (0, 1, 5, 6, 7)] == v, 'initial-declared-ancestor')
        self.nodes.update(entry)
        self.phases = ['source'] * 5
        self.facts = [copy.deepcopy(v['original']) for v in self.members]
        self.pending = None
        self.receipts = {}
        self.directory = sig(self.journal)
        self.core = hashlib.sha256(encode(dict(members=self.members, namespaces={str(p): v for p, v in self.namespaces.items()}, nodes={str(p): v for p, v in self.nodes.items()}, journal=str(self.journal)))).hexdigest()
        self.seal = self._state()
        self._append('prepared', None)
        self.close()

    def _state(self):
        return hashlib.sha256(encode(dict(phases=self.phases, facts=self.facts, pending=self.pending, receipts={str(p): v for p, v in self.receipts.items()}, directory=self.directory, parents={str(p): v for p, v in self.parents.items()}))).hexdigest()

    def _lifetime(self):
        check(self.thread == threading.get_ident() and self._state() == self.seal and (hashlib.sha256(encode(dict(members=self.members, namespaces={str(p): v for p, v in self.namespaces.items()}, nodes={str(p): v for p, v in self.nodes.items()}, journal=str(self.journal)))).hexdigest() == self.core), 'immutable-batch-projection')

    def expected_namespaces(self, override=None):
        values = copy.deepcopy(self.namespaces)
        for i, member in enumerate(self.members):
            phase, fact = (override[1], override[2]) if override is not None and override[0] == i else (self.phases[i], self.facts[i])
            src = Path(member['source'])
            dst = Path(member['target'])
            values[src.parent].pop(src.name, None)
            values[dst.parent].pop(dst.name, None)
            if phase in ('source', 'linked'):
                values[src.parent][src.name] = fact['signature9']
            if phase in ('linked', 'retained'):
                values[dst.parent][dst.name] = fact['signature9']
        return values

    def close(self, override=None):
        self._lifetime()
        expected = self.expected_namespaces(override)
        check(set(os.listdir(self.journal)) == {p.name for p in self.receipts}, 'closed-batch-journal')
        for p, namespace in expected.items():
            check(self.k._namespace(p) == namespace, 'whole-batch-namespace')
        files = {**self.parents, self.journal: self.directory}
        for p, namespace in expected.items():
            for name, fact in namespace.items():
                files[p / name] = fact
        for p, (fact, digest) in self.receipts.items():
            check(hashlib.sha256(p.read_bytes()).hexdigest() == digest, 'batch-intended-receipt')
            files[p] = fact
        for p, expected9 in files.items():
            z = os.lstat(p)
            check([z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns, z.st_mode, z.st_uid, z.st_gid, z.st_nlink] == expected9, 'batch-direct-file')
        for p, expected5 in self.nodes.items():
            z = os.lstat(p)
            check([z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid] == expected5, 'batch-direct-ancestor')

    def _append(self, phase, index):
        self._lifetime()
        check(set(os.listdir(self.journal)) == {p.name for p in self.receipts}, 'before-intent-journal')
        raw = encode(dict(version=1, kind='five-member-negative-namespace-witness', phase=phase, index=index, core=self.core, phases=self.phases, facts=self.facts, pending=self.pending, publication_acceptance=False, mutation_authority=False))
        check(len(raw) <= 16 * 1024 ** 2, 'bounded-private-witness')
        name = f'{len(self.receipts):02d}.json'
        p = self.journal / name
        d = os.open(self.journal, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            z = os.fstat(d)
            check([z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid] == self.nodes[self.journal], 'admitted-journal-FD')
            check([z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns, z.st_mode, z.st_uid, z.st_gid, z.st_nlink] == self.directory, 'before-write-journal-FD-CAS')
            fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 384, dir_fd=d)
            try:
                with os.fdopen(os.dup(fd), 'wb') as f:
                    f.write(raw)
                    f.flush()
                    os.fsync(f.fileno())
                os.fsync(d)
                os.lseek(fd, 0, os.SEEK_SET)
                observed = bytearray()
                while len(observed) <= len(raw):
                    block = os.read(fd, min(1024 ** 2, len(raw) + 1 - len(observed)))
                    if not block:
                        break
                    observed.extend(block)
                check(bytes(observed) == raw, 'intended-batch-witness')
                z = os.fstat(fd)
                before = [z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns, z.st_mode, z.st_uid, z.st_gid, z.st_nlink]
                z = os.stat(name, dir_fd=d, follow_symlinks=False)
                check([z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns, z.st_mode, z.st_uid, z.st_gid, z.st_nlink] == before, 'relative-journal-leaf-CAS')
            finally:
                os.close(fd)
            z = os.fstat(d)
            directory = [z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns, z.st_mode, z.st_uid, z.st_gid, z.st_nlink]
            check(sig(self.journal) == directory, 'post-write-journal-binding')
        finally:
            os.close(d)
        self.receipts[p] = (before, hashlib.sha256(raw).hexdigest())
        self.directory = directory
        self.seal = self._state()

    def intent(self, index, action):
        check(type(index) is int and 0 <= index < 5 and (action in ('link', 'retire', 'unstage', 'restore')), 'finite-batch-intent')
        self.close()
        check(self.pending is None, 'one-syscall-intent-at-a-time')
        check(self.phases[index] == ('source' if action == 'link' else 'retained' if action == 'restore' else 'linked'), 'finite-batch-predecessor')
        self.pending = [index, action]
        self.seal = self._state()
        self._append(action + '-intent', index)
        self.close()
        return dict(intent_retained=True, syscall_authority=False)

    def observe_transition(self, index):
        self._lifetime()
        check(self.pending is not None and self.pending[0] == index, 'exact-owned-intent')
        action = self.pending[1]
        member = self.members[index]
        src = Path(member['source'])
        dst = Path(member['target'])
        if action in ('link', 'restore'):
            value = self.k._fact(src, 2)
            check(value == self.k._fact(dst, 2), 'exact-two-owned-aliases')
            phase = 'linked'
            links = 2
        elif action == 'retire':
            check(not os.path.lexists(src), 'owned-retired-source-absence')
            value = self.k._fact(dst, 1)
            phase = 'retained'
            links = 1
        else:
            check(not os.path.lexists(dst), 'owned-unstaged-target-absence')
            value = self.k._fact(src, 1)
            phase = 'source'
            links = 1
        check(self.k._preserved(value, member['original'], links), 'preserved-five-member-original')
        changed = {src.parent, dst.parent}
        current = {p: sig(p) for p in changed}
        for p, fact in current.items():
            check([fact[i] for i in (0, 1, 5, 6, 7)] == [self.parents[p][i] for i in (0, 1, 5, 6, 7)], 'transition-parent-identity')
        old = self.parents
        self.parents = {**old, **current}
        self.seal = self._state()
        try:
            self.close((index, phase, value))
        except BaseException:
            self.parents = old
            self.seal = self._state()
            raise
        self.phases[index] = phase
        self.facts[index] = value
        self.pending = None
        self.seal = self._state()
        self._append(phase, index)
        self.close()
        return dict(observation_verified=True, mutation_authority=False, publication_acceptance=False)
if __name__ == '__main__':
    print(json.dumps(dict(executable=False, installed=False, mutation_authority=False, missing='owning native batch factory, reader custody handshake and terminal closure')))
