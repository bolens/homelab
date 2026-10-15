"""Explicit operator-reviewed migration transaction; default remains disabled.

The caller supplies an explicitly reviewed private package; committed readers are shared.
No package is accepted merely because its self-described booleans are true.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import stat

if __package__:
    from . import publication_guard as guard
    from . import publication_identity_adoption as adoption
    from .media_writer import Writer, sync
    from .workflow_store import Store
else:
    import publication_guard as guard
    import publication_identity_adoption as adoption
    from media_writer import Writer, sync
    from workflow_store import Store

COMMIT_BINDINGS = None
FENCE = 'publication-recovery-v1.json'


def nine(z):
    return [z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
            z.st_mode, z.st_uid, z.st_gid, z.st_nlink]


class Originals:
    def __init__(self):
        self.files, self.nodes = {}, {}

    def read(self, ref):
        adoption.need(type(ref) is dict and set(ref) == {'path', 'sha256', 'signature9'}, 'review-original-ref-schema')
        path = Path(ref['path'])
        adoption.need(path.is_absolute() and str(path) == ref['path']
                      and all(x not in ('', '.', '..') for x in ref['path'].split('/')[1:]), 'review-original-canonical-path')
        for parent in path.parents:
            z = os.lstat(parent)
            row = [z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid]
            adoption.need(stat.S_ISDIR(z.st_mode) and self.nodes.get(str(parent), row) == row, 'review-original-ancestor')
            self.nodes.setdefault(str(parent), row)
        parent = os.lstat(path.parent)
        adoption.need(parent.st_uid == os.geteuid() and stat.S_IMODE(parent.st_mode) == 0o700, 'review-private-parent')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            z = os.fstat(fd)
            row = nine(z)
            adoption.need(type(ref['signature9']) is list and all(type(x) is int for x in ref['signature9'])
                          and row == ref['signature9'] and stat.S_ISREG(z.st_mode)
                          and z.st_uid == os.geteuid() and z.st_nlink == 1
                          and stat.S_IMODE(z.st_mode) == 0o600 and 0 < z.st_size <= 4*1024*1024, 'review-original-private9')
            adoption.need(self.files.get(str(path), row) == row, 'review-original-conflict')
            self.files.setdefault(str(path), row)
            raw = b''
            while len(raw) < z.st_size:
                block = os.read(fd, min(65536, z.st_size-len(raw)))
                adoption.need(bool(block), 'review-original-short-read')
                raw += block
            adoption.need(nine(os.fstat(fd)) == row and nine(os.lstat(path)) == row
                          and adoption.digest(raw) == ref['sha256'], 'review-original-hash9')
        finally:
            os.close(fd)
        self.check()
        return raw

    def check(self):
        for path, row in self.nodes.items():
            z = os.lstat(path)
            adoption.need([z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid] == row, 'review-final-ancestor5')
        for path, row in self.files.items():
            adoption.need(nine(os.lstat(path)) == row, 'review-final-file9')


class Maintenance:
    def __init__(self, store, writer, marker, *, reviewed_package_ref=None):
        selected = COMMIT_BINDINGS if reviewed_package_ref is None else reviewed_package_ref
        adoption.need(selected is not None, 'identity-maintenance-not-configured')
        adoption.need(type(store) is Store and store.existing_only is True and type(writer) is Writer, 'identity-maintenance-existing-owning-types')
        self.store, self.writer, self.marker = store, writer, Path(marker)
        adoption.need(store.path == writer.root.parent/'workflow.sqlite', 'identity-maintenance-fixed-data-pair')
        adoption.need(self.marker == writer.root/'publication-v1.json', 'identity-maintenance-fixed-marker')
        self.db9 = list(guard.database_stamp(store.path))
        self.writer_pair = list(guard.writer_identity(writer))
        self.bindings = json.loads(adoption.encoded(selected))
        self.tape = adoption.encoded(selected)
        self.selected_original = selected
        self.originals = Originals()
        raw = self.originals.read(self.bindings)
        package = guard.decode_json(raw.decode())
        adoption.need(type(package) is dict and set(package) in ({
            'version', 'kind', 'backup_ref', 'restore_ref', 'old_identity', 'new_identity',
            'current_state_digest', 'marker_ref', 'verified_backup', 'verified_restore'},
            {'version', 'kind', 'backup_ref', 'restore_ref', 'old_identity', 'new_identity',
             'current_state_digest', 'marker_ref', 'verified_backup', 'verified_restore', 'tagger'})
            and type(package['version']) is int and package['version'] == 1
            and package['kind'] == 'operator-reviewed-device-migration-v1'
            and package['verified_backup'] is True and package['verified_restore'] is True,
            'reviewed-migration-package-schema')
        # Exact installed package pin is the operator-review boundary. These
        # original artifacts are retained; this does not rerun a restore drill.
        for key in ('backup_ref', 'restore_ref', 'marker_ref'):
            self.originals.read(package[key])
        adoption.need(package['marker_ref']['path'] == str(self.marker), 'reviewed-marker-exact-path')
        adoption.device_edge(package['old_identity'], package['new_identity'])
        self.package = json.loads(adoption.encoded(package))
        self.package_tape = adoption.encoded(package)
        self.ledger = writer.root/'identity-adoptions-v1'
        self.fence = writer.root/FENCE

    def close(self):
        adoption.need(adoption.encoded(self.selected_original) == self.tape
                      and adoption.encoded(self.package) == self.package_tape, 'review-configured-original-changed')
        self.writer.validate_root()
        adoption.need(list(guard.database_stamp(self.store.path)) == self.db9, 'identity-original-database9')
        adoption.need(list(guard.writer_identity(self.writer)) == self.writer_pair, 'identity-original-writer-pair')
        self.originals.check()
        adoption.need(nine(os.lstat(self.store.path)) == self.db9, 'identity-final-original-database9')

    @contextmanager
    def session(self, own_fence=False):
        with self.writer.hold():
            with self.store.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                for name in adoption.PENDING:
                    if own_fence and name == FENCE:
                        continue
                    adoption.need(not os.path.lexists(self.writer.root/name), 'identity-maintenance-pending-held')
                current = dict(database_identity=list(guard.database_stamp(self.store.path)[:2]),
                               writer_identity=list(guard.writer_identity(self.writer)))
                adoption.need(current == self.package['new_identity'], 'identity-maintenance-current-exact')
                self.close()
                yield db
                self.close()

    def state(self, db):
        value = dict(prefix=adoption.capture_prefix(db), workflow=guard.full_workflow_snapshot(db),
                     marker_sha256=self.package['marker_ref']['sha256'])
        return adoption.digest(adoption.encoded(value))

    def evidence(self):
        if __package__:
            from .publication_filesystem_binding import observe
        else:
            from publication_filesystem_binding import observe
        stable = observe(self.store.path, self.writer.root)
        evidence = dict(backup_digest=self.package['backup_ref']['sha256'],
                        restore_digest=self.package['restore_ref']['sha256'],
                        review_digest=self.bindings['sha256'], current_state_digest=self.package['current_state_digest'],
                        prospective_fs=stable)
        if 'tagger' in self.package:
            evidence['tagger'] = self.package['tagger']
        adoption.evidence_value(evidence)
        self.close()
        return evidence

    def prepare(self):
        with self.session() as db:
            adoption.need(self.state(db) == self.package['current_state_digest'], 'identity-reviewed-state-stale')
            evidence = self.evidence()
            adoption.need(not os.path.lexists(self.ledger), 'identity-existing-ledger-requires-separate-reviewed-chain')
            plan = adoption.prepare_plan(db, self.package['old_identity'], self.package['new_identity'], evidence)
            self.close()
            return plan

    def save_exclusive(self, path, raw):
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            born = os.fstat(fd)
            adoption.need(stat.S_ISREG(born.st_mode) and born.st_nlink == 1
                          and born.st_uid == os.geteuid() and stat.S_IMODE(born.st_mode) == 0o600, 'identity-exclusive-birth')
            left = memoryview(raw)
            while left:
                written = os.write(fd, left)
                adoption.need(written > 0, 'identity-exclusive-write')
                left = left[written:]
            os.fsync(fd)
            after = os.fstat(fd)
            adoption.need([after.st_dev, after.st_ino, after.st_mode, after.st_uid, after.st_gid, after.st_nlink]
                          == [born.st_dev, born.st_ino, born.st_mode, born.st_uid, born.st_gid, born.st_nlink]
                          and after.st_size == len(raw), 'identity-exclusive-born-static')
            row = nine(after)
            os.lseek(fd, 0, os.SEEK_SET)
            readback = b''
            while len(readback) < len(raw):
                part = os.read(fd, len(raw)-len(readback))
                adoption.need(bool(part), 'identity-exclusive-readback-short')
                readback += part
            adoption.need(readback == raw and nine(os.fstat(fd)) == row and nine(os.lstat(path)) == row,
                          'identity-exclusive-readback9')
            adoption.need(str(path) not in self.originals.files, 'identity-exclusive-original-not-overwritten')
            self.originals.files[str(path)] = row
        finally:
            os.close(fd)
        sync(path.parent)
        self.close()

    def commit(self, plan, *, accepted_token, boundary=lambda _: None):
        adoption.validate_plan(plan)
        caller_plan = plan
        plan_tape = adoption.encoded(plan)
        plan = json.loads(plan_tape)
        token = adoption.digest(plan_tape)
        adoption.need(accepted_token == token, 'identity-exact-reviewed-acceptance')
        with self.session() as db:
            adoption.need(plan == self.prepare_plan_in_session(db), 'identity-prepared-plan-stale')
            fence = adoption.encoded(dict(version=1, kind='accepted-device-identity-migration-v1',
                                          token=token, review=self.bindings, plan=plan))
            self.save_exclusive(self.fence, fence)
            boundary('fence-durable')
            self.close()
            adoption.need(adoption.encoded(caller_plan) == plan_tape, 'identity-original-plan-changed')
            def original_boundary(stage):
                boundary(stage)
                adoption.need(adoption.encoded(caller_plan) == plan_tape, 'identity-original-plan-changed')
            result = self.finish(db, plan, token, original_boundary)
            adoption.need(adoption.encoded(caller_plan) == plan_tape, 'identity-terminal-original-plan-changed')
            self.close()
            return result

    def prepare_plan_in_session(self, db):
        adoption.need(self.state(db) == self.package['current_state_digest'], 'identity-reviewed-state-stale')
        evidence = self.evidence()
        return adoption.prepare_plan(db, self.package['old_identity'], self.package['new_identity'], evidence)

    def finish(self, db, plan, token, boundary):
        adoption.need(self.state(db) == self.package['current_state_digest'], 'identity-recovery-state-stale')
        if not os.path.lexists(self.ledger):
            os.mkdir(self.ledger, 0o700)
            sync(self.writer.root)
        z = os.lstat(self.ledger)
        adoption.need(stat.S_ISDIR(z.st_mode) and z.st_uid == os.geteuid() and stat.S_IMODE(z.st_mode) == 0o700,
                      'identity-ledger-owned-root')
        row = [z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid]
        adoption.need(self.originals.nodes.get(str(self.ledger), row) == row, 'identity-ledger-original-root')
        self.originals.nodes.setdefault(str(self.ledger), row)
        leaf = self.ledger/(token+'.json')
        adoption.need(token == adoption.digest(adoption.encoded(plan)), 'identity-committed-exact-token')
        raw = adoption.encoded(dict(version=1, kind='committed-device-identity-edge', token=token, accepted=True, plan=plan))
        adoption.need(len(raw) <= adoption.MAX_RECORD_BYTES, 'identity-committed-record-bound')
        if os.path.lexists(leaf):
            records, nodes, files, names = adoption._read_ledger(self.ledger)
            adoption.need(names == {leaf.name} and records[token]['plan'] == plan, 'identity-recovery-record-exact')
            for path, value in files.items():
                adoption.need(self.originals.files.get(path, list(value)) == list(value), 'identity-record-original-conflict')
                self.originals.files.setdefault(path, list(value))
            for path, value in nodes.items():
                adoption.need(self.originals.nodes.get(path, list(value)) == list(value), 'identity-record-ancestor-conflict')
                self.originals.nodes.setdefault(path, list(value))
        else:
            adoption.need(not os.listdir(self.ledger), 'identity-recovery-foreign-namespace')
            self.save_exclusive(leaf, raw)
        boundary('edge-durable')
        adoption.need(self.state(db) == self.package['current_state_digest'], 'identity-post-edge-state-stale')
        self.close()
        adoption.need(set(os.listdir(self.ledger)) == {leaf.name}, 'identity-final-exclusive-namespace')
        self.close()
        boundary('before-fence-removal')
        adoption.need(self.state(db) == self.package['current_state_digest'], 'identity-before-removal-state-stale')
        self.close()
        adoption.need(set(os.listdir(self.ledger)) == {leaf.name}, 'identity-pre-removal-exclusive-namespace')
        self.close()
        # Remove only our retained accepted fence, never old markers or journals.
        self.originals.check()
        os.unlink(self.fence)
        del self.originals.files[str(self.fence)]
        sync(self.writer.root)
        boundary('fence-removed')
        adoption.need(self.state(db) == self.package['current_state_digest'], 'identity-terminal-state-stale')
        adoption.need(not os.path.lexists(self.fence), 'identity-fence-reappeared')
        adoption.need(set(os.listdir(self.ledger)) == {leaf.name}, 'identity-terminal-namespace')
        self.close()
        return token

    def recover(self, *, accepted_token, boundary=lambda _: None):
        with self.session(own_fence=True) as db:
            if not os.path.lexists(self.fence):
                plan = self.prepare_plan_in_session(db)
                token = adoption.digest(adoption.encoded(plan))
                adoption.need(accepted_token == token, 'identity-completed-recovery-exact-token')
                records, nodes, files, names = adoption._read_ledger(self.ledger)
                adoption.need(names == {token+'.json'} and records[token]['plan'] == plan,
                              'identity-completed-recovery-original-record')
                for path, row in files.items():
                    adoption.need(self.originals.files.get(path, list(row)) == list(row), 'identity-completed-record-conflict')
                    self.originals.files.setdefault(path, list(row))
                for path, row in nodes.items():
                    adoption.need(self.originals.nodes.get(path, list(row)) == list(row), 'identity-completed-node-conflict')
                    self.originals.nodes.setdefault(path, list(row))
                adoption.need(self.state(db) == self.package['current_state_digest'], 'identity-completed-recovery-state')
                adoption.need(set(os.listdir(self.ledger)) == names and not os.path.lexists(self.fence),
                              'identity-completed-recovery-namespace')
                self.close()
                return token
            fd = os.open(self.fence, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                z = os.fstat(fd)
                ref = dict(path=str(self.fence), signature9=nine(z))
                adoption.need(0 < z.st_size <= adoption.MAX_RECORD_BYTES, 'identity-fence-bound')
                raw = os.read(fd, z.st_size+1)
                ref['sha256'] = adoption.digest(raw)
                adoption.need(nine(os.fstat(fd)) == ref['signature9'] and nine(os.lstat(self.fence)) == ref['signature9'], 'identity-fence-original9')
            finally:
                os.close(fd)
            raw = self.originals.read(ref)
            value = guard.decode_json(raw.decode())
            adoption.need(type(value) is dict and set(value) == {'version', 'kind', 'token', 'review', 'plan'}
                          and type(value['version']) is int and value['version'] == 1
                          and value['kind'] == 'accepted-device-identity-migration-v1'
                          and value['review'] == self.bindings and value['token'] == accepted_token
                          and adoption.digest(adoption.encoded(value['plan'])) == accepted_token,
                          'identity-recovery-exact-accepted-fence')
            adoption.need(value['plan'] == self.prepare_plan_in_session(db), 'identity-recovery-reviewed-plan')
            return self.finish(db, value['plan'], accepted_token, boundary)
