"""Public data-only historical device fixture; no past-remount/runtime grant.

Historical identities are projected ONLY while constructing fixture genesis.
All resulting immutable rows/tokens/tagger bytes are captured before adoption.
Private accepted ledger envelopes model operator review, not verified backups.
"""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import unittest

HERE = Path(__file__).absolute().parent
CONFIG = HERE
sys.path.insert(0, str(CONFIG))
sys.path.insert(0, str(HERE))
import publication_guard as guard
import publication_identity_adoption as adoption
import publication_identity_readers as readers
import test_publication_guard as fixture
from media_writer import Writer
from workflow_store import Store


class HistoricalFixture(unittest.TestCase):
    record = fixture.RegistryTests.record
    body = fixture.RegistrationTransactionTests.body
    observe = fixture.RegistrationTransactionTests.observe

    def setUp(self):
        fixture.RegistryTests.setUp(self)
        self.current = dict(database_identity=list(self.state.identity),
                            writer_identity=list(self.state.writer_binding))
        self.old = copy.deepcopy(self.current)
        old_device = self.current['database_identity'][0]+101
        for name, indexes in (('database_identity', (0,)), ('writer_identity', (0, 2))):
            for index in indexes:
                self.old[name][index] = old_device
        # This is fixture GENESIS, not migration of preexisting authority:
        # create a canonical old-device bootstrap and history in real SQLite.
        genesis = self.store.get('publication_intent', self.initialization)
        genesis['plan']['binding'].update(copy.deepcopy(self.old))
        token = guard.canonical_digest(genesis['plan'])
        with self.store.connection() as db:
            db.execute("DELETE FROM records WHERE kind='publication_intent' AND key=?", (self.initialization,))
            db.execute('INSERT INTO records VALUES(?,?,?,?)',
                       ('publication_intent', token, json.dumps(genesis), 0))
        self.initialization = token
        self.state.identity = self.old['database_identity']
        self.state.writer_binding = self.old['writer_identity']
        fixture.RegistryTests.seed(self, [self.record(0), self.record(1)])
        self.state = guard.RegistryState(self.store.path, self.writer)
        self.rows_original = self.rows()
        self.marker_original = self.marker.read_bytes()
        self.bootstrap_original = self.store.get('publication_intent', token)
        root = self.root/'modern-tagger-v2'
        self.paths = (root, root/'journal-v2', root/'staging', root/'staging-receipts')
        for path in self.paths:
            path.mkdir(mode=0o700)
        self.assertTrue(all(path.stat().st_dev == self.current['database_identity'][0] for path in self.paths))
        self.binding = self.writer.root/'tagger-state-v2.identity'
        self.binding_original = readers.tagger_digest([(old_device, path.stat().st_ino) for path in self.paths])
        self.binding.write_bytes(self.binding_original)
        self.binding.chmod(0o600)
        self.ledger = self.writer.root/'identity-adoptions-v1'
        self.ledger.mkdir(mode=0o700)
        self.evidence = dict(backup_digest='a'*64, restore_digest='b'*64,
                             review_digest='c'*64, current_state_digest='d'*64,
                             prospective_fs=None,
                             tagger=dict(binding_sha256=hashlib.sha256(self.binding_original).hexdigest(),
                                         binding_inode=self.binding.stat().st_ino,
                                         directory_inodes=[p.stat().st_ino for p in self.paths]))
        with self.store.connection() as db:
            db.execute('BEGIN')
            self.plan = adoption.prepare_plan(db, self.old, self.current, self.evidence)
        self.token = adoption.digest(adoption.encoded(self.plan))
        self.ledger_file = self.ledger/(self.token+'.json')
        # Explicit PUBLIC FIXTURE review envelope, no operational proof claim.
        self.envelope = dict(version=1, kind='committed-device-identity-edge',
                             token=self.token, accepted=True, plan=self.plan)
        self.ledger_file.write_bytes(adoption.encoded(self.envelope))
        self.ledger_file.chmod(0o600)

    def rows(self):
        with self.store.connection() as db:
            return {(kind, key): raw for kind, key, raw in db.execute(
                "SELECT kind,key,value FROM records WHERE kind IN "
                "('publication_intent','publication_attestation') ORDER BY kind,key")}

    def validate(self):
        return readers.validate_tagger_binding(self.writer, self.store.path, self.binding, self.paths)

    def register(self, revision):
        state = guard.RegistrationState(self.store.path, self.writer)
        body = self.body(revision)
        token = state.prepare_registration(body, observe=self.observe)
        return state.register(token, accepted_token=token, observe=self.observe)


class TaggerIdentityTests(HistoricalFixture):
    def test_exact_old_device_four_inode_projection_preserves_original_bytes(self):
        self.assertIsNone(self.validate())
        self.assertEqual(self.binding.read_bytes(), self.binding_original)
        self.assertEqual(self.rows(), self.rows_original)
        self.assertEqual(self.marker.read_bytes(), self.marker_original)
        self.assertEqual(guard.canonical_digest(self.bootstrap_original['plan']), self.initialization)

    def test_real_directory_and_binding_mode_drift_refused(self):
        for path, bad_mode, good_mode in ((self.paths[2], 0o750, 0o700), (self.binding, 0o640, 0o600)):
            with self.subTest(path_kind='directory' if path.is_dir() else 'binding'):
                path.chmod(bad_mode)
                with self.assertRaises(guard.Unavailable):
                    self.validate()
                path.chmod(good_mode)
        self.assertEqual(self.binding.read_bytes(), self.binding_original)

    def test_owner_predicates_reject_explicit_foreign_owner_projection(self):
        # Actual source-method predicates + genuine stat values. Only the
        # candidate owner input is projected; no global stat or EUID mock.
        function = next(n for n in ast.parse((HERE/'publication_identity_readers.py').read_bytes()).body
                        if isinstance(n, ast.FunctionDef) and n.name == 'validate_tagger_binding')
        for reason, path in (('identity-tagger-private-directory', self.paths[2]),
                             ('identity-tagger-private-binding', self.binding)):
            node = next(n for n in ast.walk(function) if isinstance(n, ast.Expr)
                        and isinstance(n.value, ast.Call) and len(n.value.args) == 2
                        and isinstance(n.value.args[1], ast.Constant) and n.value.args[1].value == reason)
            code = compile(ast.Module(body=[node], type_ignores=[]), 'actual-source-owner-predicate', 'exec')
            z = path.stat()
            exec(code, dict(adoption=adoption, stat=stat, os=os, z=z))
            foreign = list(z)
            foreign[4] = z.st_uid+1
            with self.assertRaises(guard.Unavailable):
                exec(code, dict(adoption=adoption, stat=stat, os=os, z=os.stat_result(foreign)))

    def test_replaced_directory_inode_and_wrong_original_digest_refuse(self):
        target = self.paths[2]
        target.rename(target.with_name('retained-staging'))
        target.mkdir(mode=0o700)
        with self.assertRaisesRegex(guard.Unavailable, 'identity-tagger-reviewed-originals'):
            self.validate()
        self.assertEqual(self.binding.read_bytes(), self.binding_original)
        target.rmdir()
        target.with_name('retained-staging').rename(target)
        self.assertIsNone(self.validate())
        self.binding.write_bytes(b'f'*64+b'\n')
        with self.assertRaisesRegex(guard.Unavailable, 'identity-tagger-reviewed-originals'):
            self.validate()

    def test_each_pending_marker_and_unresolved_recovery_entry_remains_held(self):
        for name in adoption.PENDING:
            path = self.writer.root/name
            path.write_bytes(b'public unresolved fixture')
            path.chmod(0o600)
            with self.subTest(marker=name), self.assertRaisesRegex(guard.Unavailable, 'identity-tagger-pending-held'):
                self.validate()
            self.assertEqual(path.read_bytes(), b'public unresolved fixture')
            path.unlink()
        for directory in self.paths[1:]:
            path = directory/'unresolved.json'
            path.write_bytes(b'public unresolved fixture')
            with self.assertRaisesRegex(guard.Unavailable, 'identity-tagger-unreviewed-journal-or-staging'):
                self.validate()
            self.assertEqual(path.read_bytes(), b'public unresolved fixture')
            path.unlink()
        self.assertEqual(self.binding.read_bytes(), self.binding_original)

    def test_prepared_formatter_cannot_substitute_committed_review(self):
        raw = adoption.record_bytes(self.plan)
        self.ledger_file.write_bytes(raw)
        with self.assertRaisesRegex(guard.Unavailable, 'identity-record-schema'):
            self.validate()
        self.assertEqual(self.rows(), self.rows_original)
        self.assertEqual(self.binding.read_bytes(), self.binding_original)

    def test_genuine_future_registration_restart_and_tagger_reader(self):
        self.assertEqual(guard.registry_snapshot(self.store.path, self.marker)[0]['revision'], 2)
        self.assertEqual(self.register(2)['revision'], 3)
        current = self.rows()
        self.assertTrue(all(current.get(key) == raw for key, raw in self.rows_original.items()))
        self.store = Store(self.root, existing_only=True)
        self.writer = Writer(self.root/'media-writer', create=False)
        self.assertEqual(guard.RegistryState(self.store.path, self.writer).snapshot()[0]['revision'], 3)
        self.assertIsNone(self.validate())
        self.assertEqual(self.binding.read_bytes(), self.binding_original)
        self.assertEqual(guard.canonical_digest(self.bootstrap_original['plan']), self.initialization)





class TaggerHistoryCardinalityTests(unittest.TestCase):
    """Real private history files; no remount, publication or migration grant."""
    def setUp(self):
        import tempfile
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)/'modern-tagger-v2'
        self.paths = (root, root/'journal-v2', root/'staging', root/'staging-receipts')
        for path in self.paths:
            path.mkdir(mode=0o700)

    def lock_history(self, count):
        for number in range(count):
            path = self.paths[1]/('%064x.lock' % number)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)

    def receipt(self, folder, number, record):
        token = '%032x' % number
        path = folder/(token+'.json')
        path.write_text(json.dumps(dict(record, token=token)))
        path.chmod(0o600)
        return path

    def test_large_valid_terminal_history_preserved_and_malformed_still_refused(self):
        self.lock_history(4097)
        record = dict(version=1, state='committed', cleaned=True,
                      source='/public-fixture/retained.cbz', request='a'*64,
                      before='b'*64, after='c'*64, source_identity=[1,2,3,4,5],
                      workspace=[1,2], permissions=[0o600,os.geteuid(),os.getegid()],
                      candidate_identity=[1,2,3,4,5], metadata='updated')
        journal = self.receipt(self.paths[1], 1, record)
        clean = self.receipt(self.paths[3], 2, dict(version=1, state='cleaned',
            source='/public-fixture/retained.cbz', before='b'*64,
            source_identity=[1,2,3,4,5], folder_identity=[1,2], filename='retained.cbz'))
        originals = {p: (guard.signature(p.lstat()), p.read_bytes()) for p in (journal, clean)}
        names, files = readers.quiescent_tagger(self.paths)
        self.assertEqual(sum(map(len, names.values())), 4099)
        self.assertEqual(len(files), 4099)
        for path, (row, raw) in originals.items():
            self.assertEqual(guard.signature(path.lstat()), row)
            self.assertEqual(path.read_bytes(), raw)
        journal.write_text('{}')
        with self.assertRaisesRegex(guard.Unavailable, 'identity-tagger-unreviewed-journal-or-staging'):
            readers.quiescent_tagger(self.paths)

    def test_finite_upper_bound_refuses_real_oversized_history_without_removal(self):
        self.lock_history(65537)
        with self.assertRaisesRegex(guard.Unavailable, 'identity-tagger-unreviewed-journal-or-staging'):
            readers.quiescent_tagger(self.paths)
        self.assertEqual(len(os.listdir(self.paths[1])), 65537)

    def test_staging_and_retained_receipt_remain_unreviewed(self):
        stage = self.paths[2]/'retained'
        stage.mkdir(mode=0o700)
        with self.assertRaisesRegex(guard.Unavailable, 'identity-tagger-unreviewed-journal-or-staging'):
            readers.quiescent_tagger(self.paths)
        self.assertTrue(stage.is_dir())
        stage.rmdir()
        receipt = self.receipt(self.paths[3], 1, dict(version=1,state='retained',
            source='/public-fixture/retained.cbz',before='b'*64,
            source_identity=[1,2,3,4,5],folder_identity=[1,2],filename='retained.cbz'))
        original = receipt.read_bytes()
        with self.assertRaisesRegex(guard.Unavailable, 'identity-tagger-unreviewed-journal-or-staging'):
            readers.quiescent_tagger(self.paths)
        self.assertEqual(receipt.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
