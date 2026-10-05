"""Durable history and command contract checks with disposable state."""
import tempfile
import unittest
import os
import sqlite3
from contextlib import closing
from unittest.mock import patch
from pathlib import Path
from workflow_store import Store, protected_snapshot

class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.now=10000000; self.store=Store(self.tmp.name,lambda:self.now)
    def test_restart_preserves_events_and_idempotent_commands(self):
        self.store.event('search','Started',issueid='10',name='Example')
        self.assertTrue(self.store.create('command','abc',{'phase':'queued'}))
        self.assertFalse(self.store.create('command','abc',{'phase':'reset'}))
        reopened=Store(self.tmp.name,lambda:self.now)
        self.assertEqual(reopened.get('command','abc')['phase'],'queued')
        self.assertEqual(reopened.events(issueid='10')[0]['outcome'],'Started')
        self.assertEqual((Path(self.tmp.name)/'workflow.sqlite').stat().st_mode&0o777,0o600)
    def test_retention_and_bounded_filters(self):
        for i in range(105):self.store.event('search','Started',issueid=str(i%2))
        self.assertEqual(len(self.store.events()),100)
        self.assertEqual(len(self.store.events(issueid='1')),52)
        self.assertEqual(self.store.events(stage='tagging'),[])
        self.now+=31*86400;self.store.event('tagging','Finished')
        self.assertEqual(len(self.store.events()),1)
    def test_untrusted_display_values_are_bounded_and_redacted(self):
        self.store.event('search','Started',name='/private/file.cbz',provider='https://host/?apikey=secret',issueid='bad')
        row=self.store.events()[0]
        self.assertEqual(row['name'],'file.cbz');self.assertNotIn('secret',str(row));self.assertEqual(row['issueid'],'')
    def test_deduplicated_observations_and_corrupt_state(self):
        self.store.event('library','Confirmed',key='issue:10')
        self.store.event('library','Confirmed',key='issue:10')
        self.assertEqual(len(self.store.events()),1)
        (Path(self.tmp.name)/'workflow.sqlite').write_bytes(b'not a database')
        with self.assertRaises(Exception):self.store.events()

class BootstrapProjectionTests(unittest.TestCase):
    setUp = StoreTest.setUp
    def snapshot(self):
        with self.store.connection() as db:
            db.execute('BEGIN')
            return protected_snapshot(db)

    def test_observations_events_intents_and_envelope_do_not_stale_review(self):
        self.store.set('pack', '1', {'phase': 'imported', 'owners': ['123']})
        baseline = self.snapshot()
        self.store.event('library', 'Observed', key='new-observation')
        self.store.set('meta', 'library_seen', ['123'])
        self.store.set('publication_intent', 'reviewed-intent', {'accepted': False})
        self.now += 10
        self.store.set('pack', '1', {'phase': 'imported', 'owners': ['123']})
        self.assertEqual(self.snapshot(), baseline)

    def test_every_protected_add_remove_and_nested_change_stales_review(self):
        self.store.set('pack', '1', {'phase': 'imported', 'owners': ['123']})
        baseline = self.snapshot()
        for kind in ('unknown-future-kind', 'handoff', 'dispatch', 'publication_attestation'):
            self.store.set(kind, '1', {'phase': 'confirmed'})
            self.assertNotEqual(self.snapshot(), baseline)
            self.store.delete(kind, '1')
            self.assertEqual(self.snapshot(), baseline)
        self.store.set('pack', '1', {'phase': 'imported', 'owners': ['456']})
        self.assertNotEqual(self.snapshot(), baseline)
        self.store.delete('pack', '1')
        self.assertNotEqual(self.snapshot(), baseline)

    def test_transaction_required_and_duplicate_json_rejected(self):
        with self.store.connection() as db:
            with self.assertRaises(ValueError):protected_snapshot(db)
            db.execute('INSERT INTO records VALUES (?,?,?,?)',
                       ('pack', '1', '{"owner":"1","owner":"2"}', 0))
        with self.assertRaises(ValueError):self.snapshot()


class ExistingStoreTests(unittest.TestCase):
    """Opt-in connection foundation; native activation is a separate adapter."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        Store(self.root).set('pack', '1', {'phase': 'review'})
        self.path = self.root / 'workflow.sqlite'

    def existing(self):
        return Store(self.root, existing_only=True)

    def test_existing_mode_reads_writes_without_schema_or_permission_changes(self):
        before = self.path.stat()
        store = self.existing()
        self.assertEqual(store.get('pack', '1'), {'phase': 'review'})
        store.set('pack', '1', {'phase': 'confirmed'})
        self.assertEqual(self.existing().get('pack', '1'), {'phase': 'confirmed'})
        after = self.path.stat()
        self.assertEqual((before.st_dev, before.st_ino, before.st_mode),
                         (after.st_dev, after.st_ino, after.st_mode))

    def test_missing_database_or_parent_is_never_created(self):
        self.path.unlink()
        with self.assertRaises(Exception):self.existing()
        self.assertFalse(self.path.exists())
        absent = self.root / 'absent'
        with self.assertRaises(Exception):Store(absent, existing_only=True)
        self.assertFalse(absent.exists())

    def test_cached_store_refuses_loss_and_replacement(self):
        store = self.existing()
        retained = self.root / 'retained.sqlite'
        self.path.rename(retained)
        with self.assertRaises(Exception):store.events()
        self.assertFalse(self.path.exists())
        Store(self.root)
        original = self.path.read_bytes()
        with self.assertRaises(Exception):store.set('pack', '1', {})
        self.assertEqual(self.path.read_bytes(), original)

    def test_sidecars_even_dangling_links_hold_before_sqlite_open(self):
        store = self.existing()
        for suffix in ('-journal', '-wal', '-shm'):
            for linked in (False, True):
                sidecar = Path(str(self.path) + suffix)
                if linked:sidecar.symlink_to(self.root / 'missing')
                else:sidecar.write_bytes(b'retained interrupted transaction')
                original = self.path.read_bytes()
                with patch('workflow_store.sqlite3.connect', side_effect=AssertionError('opened')) as connect:
                    with self.assertRaises(ValueError):store.events()
                    connect.assert_not_called()
                self.assertEqual(self.path.read_bytes(), original)
                self.assertTrue(os.path.lexists(sidecar))
                sidecar.unlink()

    def test_unsafe_files_and_parent_links_never_get_chmod_or_open(self):
        for mode in (0o644, 0o400):
            self.path.chmod(mode)
            with self.assertRaises(ValueError):self.existing()
            self.assertEqual(self.path.stat().st_mode & 0o777, mode)
        self.path.chmod(0o600)
        link = self.root / 'linked.sqlite'
        os.link(self.path, link)
        with self.assertRaises(ValueError):self.existing()
        link.unlink()
        alias = self.root / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):Store(alias, existing_only=True)

    def test_schema_changes_are_not_repaired_on_existing_connections(self):
        store = self.existing()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP INDEX events_issue');db.commit()
        original = self.path.read_bytes()
        with self.assertRaises(ValueError):store.events()
        self.assertEqual(self.path.read_bytes(), original)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE events');db.commit()
        original = self.path.read_bytes()
        with self.assertRaises(ValueError):self.existing()
        self.assertEqual(self.path.read_bytes(), original)

    def test_mode_is_a_strict_boolean(self):
        for value in (1, 'true', None):
            with self.assertRaises(ValueError):Store(self.root, existing_only=value)

    def test_real_interrupted_transaction_is_not_rolled_back(self):
        store = self.existing()
        pid = os.fork()
        if pid == 0:
            db = sqlite3.connect(self.path)
            db.execute('PRAGMA cache_size=1')
            db.execute('BEGIN IMMEDIATE')
            for index in range(40):
                db.execute('INSERT INTO records VALUES (?,?,?,?)',
                           ('spill', str(index), 'x' * 16384, 0))
            os._exit(78)
        self.assertEqual(os.waitpid(pid, 0)[1], 78 << 8)
        journal = Path(str(self.path) + '-journal')
        before = (self.path.read_bytes(), journal.read_bytes())
        with patch('workflow_store.sqlite3.connect') as connect:
            with self.assertRaises(ValueError):store.events()
            with self.assertRaises(ValueError):self.existing()
            connect.assert_not_called()
        self.assertEqual((self.path.read_bytes(), journal.read_bytes()), before)

    def test_non_database_and_wal_header_hold_without_opening(self):
        for content in (b'not SQLite', self.path.read_bytes()[:18] + b'\x02\x02' + self.path.read_bytes()[20:]):
            self.path.write_bytes(content)
            with patch('workflow_store.sqlite3.connect') as connect:
                with self.assertRaises(ValueError):self.existing()
                connect.assert_not_called()
            self.assertEqual(self.path.read_bytes(), content)

if __name__=='__main__':unittest.main()
