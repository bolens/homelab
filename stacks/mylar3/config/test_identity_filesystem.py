"""Public kernel byte fixtures and real FD/SQLite custody; no remount proof."""
import copy
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).absolute().parent
sys.path.insert(0, str(HERE))
from identity_kernel_fixture import kernel_bytes
import test_identity_tagger as fixture
import publication_filesystem_binding as filesystem


class StableIdentity(fixture.HistoricalFixture):
    def setUp(self):
        kernel = kernel_bytes()
        kernel.__enter__()
        self.addCleanup(kernel.__exit__, None, None, None)
        super().setUp()
        self.ledger_file.unlink()
        self.evidence['prospective_fs'] = filesystem.observe(self.store.path, self.writer.root)
        self.tip = copy.deepcopy(self.current)
        for name, positions in (('database_identity', (0,)), ('writer_identity', (0, 2))):
            for position in positions:
                self.tip[name][position] += 202
        self.publish()

    def publish(self):
        with self.store.connection() as db:
            db.execute('BEGIN')
            self.plan = fixture.adoption.prepare_plan(db, self.old, self.tip, self.evidence)
        token = fixture.adoption.digest(fixture.adoption.encoded(self.plan))
        for leaf in self.ledger.iterdir():
            leaf.unlink()  # Fixture-genesis ledger only, before each case's use.
        self.ledger_file = self.ledger/(token+'.json')
        self.ledger_file.write_bytes(fixture.adoption.encoded(dict(version=1, kind='committed-device-identity-edge',
                                                                token=token, accepted=True, plan=self.plan)))
        self.ledger_file.chmod(0o600)

    def test_destination_stable_query_permits_device_only_future_projection(self):
        self.assertEqual(fixture.guard.registry_snapshot(self.store.path, self.marker)[0]['revision'], 2)
        self.assertEqual(self.rows(), self.rows_original)
        self.assertEqual(self.marker.read_bytes(), self.marker_original)
        self.assertIsNone(self.validate())

    def test_future_real_registration_after_stable_projection_and_restart(self):
        self.assertEqual(self.register(2)['revision'], 3)
        self.store = fixture.Store(self.store.path.parent, existing_only=True)
        self.writer = fixture.Writer(self.writer.root, create=False)
        self.assertEqual(fixture.guard.RegistryState(self.store.path, self.writer).snapshot()[0]['revision'], 3)
        self.assertIsNone(self.validate())
        now = self.rows()
        self.assertTrue(all(now.get(key) == raw for key, raw in self.rows_original.items()))

    def test_wrong_filesystem_uuid_refuses(self):
        self.evidence['prospective_fs']['filesystem_uuid'] = '00000000-0000-0000-0000-000000000001'
        self.publish()
        with self.assertRaises(fixture.guard.Unavailable):
            fixture.guard.registry_snapshot(self.store.path, self.marker)

    def test_wrong_subvolume_or_anchor_refuses(self):
        for field, value in (('subvolume', '999:00000000-0000-0000-0000-000000000001'),
                             ('path_anchor_digest', '0'*64)):
            previous = self.evidence['prospective_fs'][field]
            self.evidence['prospective_fs'][field] = value
            self.publish()
            with self.subTest(field=field), self.assertRaises(fixture.guard.Unavailable):
                fixture.guard.registry_snapshot(self.store.path, self.marker)
            self.evidence['prospective_fs'][field] = previous

    def test_current_argument_cannot_spoof_actual_kernel_physical_pair(self):
        false_current = copy.deepcopy(self.current)
        for name, positions in (('database_identity', (0,)), ('writer_identity', (0, 2))):
            for position in positions:
                false_current[name][position] += 303
        with self.store.connection() as db:
            db.execute('BEGIN')
            with self.assertRaisesRegex(fixture.guard.Unavailable, 'identity-prospective-current-physical-pair'):
                fixture.adoption.resolve(db, self.ledger, self.old, false_current)

    def test_unsupported_ioctl_has_no_device_fallback(self):
        real = filesystem.fcntl.ioctl
        def unavailable(*args):
            raise OSError(25, 'fixture unsupported ioctl')
        filesystem.fcntl.ioctl = unavailable
        try:
            with self.assertRaises(fixture.guard.Unavailable):
                fixture.guard.registry_snapshot(self.store.path, self.marker)
        finally:
            filesystem.fcntl.ioctl = real
        self.assertEqual(self.marker.read_bytes(), self.marker_original)


if __name__ == '__main__':
    unittest.main()
