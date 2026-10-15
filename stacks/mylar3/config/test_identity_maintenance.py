"""Real source maintenance/readers with projected historical GENESIS only.

Kernel ioctl bytes are deterministic public fixtures; actual directory FDs are real.
Dummy reviewed backup artifacts prove no actual application restore acceptance.
"""
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).absolute().parent
sys.path.insert(0, str(HERE))
from identity_kernel_fixture import kernel_bytes
import test_identity_tagger as fixture
import publication_identity_maintenance as maintenance
import publication_filesystem_binding as filesystem
from workflow_store import Store


class MaintenanceIntegration(fixture.HistoricalFixture):
    def setUp(self):
        kernel = kernel_bytes()
        kernel.__enter__()
        self.addCleanup(kernel.__exit__, None, None, None)
        super().setUp()
        self.ledger_file.unlink()
        self.ledger.rmdir()
        self.store = Store(self.store.path.parent, existing_only=True)
        self.backup = self.root/'dummy-reviewed-backup.json'
        self.restore = self.root/'dummy-reviewed-isolated-restore.json'
        for path in (self.backup, self.restore):
            path.write_bytes(b'{"public_fixture":true,"actual_application_backup":false}')
            path.chmod(0o600)
        def ref(path):
            return dict(path=str(path), sha256=fixture.adoption.digest(path.read_bytes()),
                        signature9=maintenance.nine(path.stat()))
        marker = ref(self.marker)
        with self.store.connection() as db:
            db.execute('BEGIN')
            state = dict(prefix=fixture.adoption.capture_prefix(db), workflow=fixture.guard.full_workflow_snapshot(db),
                         marker_sha256=marker['sha256'])
        package = dict(version=1, kind='operator-reviewed-device-migration-v1',
                       backup_ref=ref(self.backup), restore_ref=ref(self.restore),
                       old_identity=self.old, new_identity=self.current,
                       current_state_digest=fixture.adoption.digest(fixture.adoption.encoded(state)),
                       marker_ref=marker, verified_backup=True, verified_restore=True,
                       tagger=self.evidence['tagger'])
        self.review = self.root/'dummy-operator-reviewed-package.json'
        self.review.write_bytes(fixture.adoption.encoded(package))
        self.review.chmod(0o600)
        self.owner = maintenance.Maintenance(self.store, self.writer, self.marker, reviewed_package_ref=ref(self.review))

    def adopt(self):
        plan = self.owner.prepare()
        token = fixture.adoption.digest(fixture.adoption.encoded(plan))
        self.assertIsNotNone(plan['evidence']['prospective_fs'])
        self.assertEqual(plan['evidence']['prospective_fs'], filesystem.observe(self.store.path, self.writer.root))
        self.assertEqual(self.owner.commit(plan, accepted_token=token), token)
        return plan, token

    def test_actual_transaction_restores_current_readers_then_genuine_future_registration(self):
        self.adopt()
        self.assertEqual(self.rows(), self.rows_original)
        self.assertEqual(self.marker.read_bytes(), self.marker_original)
        self.assertIsNone(self.validate())
        self.assertEqual(fixture.guard.registry_snapshot(self.store.path, self.marker)[0]['revision'], 2)
        status = fixture.guard.authority_status(self.store.path, self.writer.root)
        self.assertEqual((status['state'], status['reason']), ('ready', 'verified'))
        self.assertEqual(self.register(2)['revision'], 3)
        self.store = Store(self.store.path.parent, existing_only=True)
        self.writer = fixture.Writer(self.writer.root, create=False)
        self.assertEqual(fixture.guard.RegistryState(self.store.path, self.writer).snapshot()[0]['revision'], 3)
        self.assertIsNone(self.validate())
        self.assertEqual(self.binding.read_bytes(), self.binding_original)
        current = self.rows()
        self.assertTrue(all(current.get(key) == raw for key, raw in self.rows_original.items()))

    def test_unaccepted_formatter_envelope_is_not_adoption(self):
        plan = self.owner.prepare()
        raw = fixture.adoption.record_bytes(plan)
        value = json.loads(raw)
        self.assertIs(value['accepted'], False)
        self.ledger.mkdir(mode=0o700)
        leaf = self.ledger/(value['token']+'.json')
        leaf.write_bytes(raw)
        leaf.chmod(0o600)
        with self.assertRaises(fixture.guard.Unavailable):
            fixture.guard.registry_snapshot(self.store.path, self.marker)
        self.assertEqual(self.rows(), self.rows_original)
        self.assertEqual(self.marker.read_bytes(), self.marker_original)

    def test_last_before_removal_caller_plan_change_retains_accepted_fence(self):
        plan = self.owner.prepare()
        token = fixture.adoption.digest(fixture.adoption.encoded(plan))
        fired = []
        def mutate(stage):
            if stage == 'before-fence-removal':
                plan['evidence']['review_digest'] = '0'*64
                fired.append(True)
        with self.assertRaisesRegex(fixture.guard.Unavailable, 'identity-original-plan-changed'):
            self.owner.commit(plan, accepted_token=token, boundary=mutate)
        self.assertEqual(fired, [True])
        self.assertTrue(self.owner.fence.exists())
        self.assertEqual(self.rows(), self.rows_original)
        self.assertEqual(self.marker.read_bytes(), self.marker_original)

    def test_malformed_ledger_after_future_current_marker_still_holds(self):
        self.adopt()
        self.register(2)
        self.assertEqual(fixture.guard.authority_status(self.store.path, self.writer.root)['state'], 'ready')
        unknown = self.ledger/'unknown.json'
        unknown.write_bytes(b'{"foreign":true}')
        unknown.chmod(0o600)
        self.assertEqual(fixture.guard.authority_status(self.store.path, self.writer.root)['state'], 'held')
        self.assertEqual(unknown.read_bytes(), b'{"foreign":true}')

    def test_completed_migration_crash_recovery_preserves_originals(self):
        plan = self.owner.prepare()
        token = fixture.adoption.digest(fixture.adoption.encoded(plan))
        def crash(stage):
            if stage == 'edge-durable':
                raise RuntimeError('fixture-process-crash')
        with self.assertRaisesRegex(RuntimeError, 'fixture-process-crash'):
            self.owner.commit(plan, accepted_token=token, boundary=crash)
        self.assertTrue(self.owner.fence.exists())
        with self.assertRaises(fixture.guard.Unavailable):
            fixture.guard.registry_snapshot(self.store.path, self.marker)
        self.assertEqual(self.owner.recover(accepted_token=token), token)
        self.assertFalse(self.owner.fence.exists())
        self.assertEqual(self.rows(), self.rows_original)
        self.assertEqual(self.marker.read_bytes(), self.marker_original)
        self.assertIsNone(self.validate())


if __name__ == '__main__':
    unittest.main()
