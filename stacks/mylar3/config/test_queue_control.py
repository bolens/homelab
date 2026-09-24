"""Persistent retry, progress, cooldown, and restart invariants."""
from pathlib import Path
from queue import Queue
import sys
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
import queue_control as control

if len(sys.argv) > 1:
    sys.argv.pop(1)


class ControlTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = 1000
        self.state = control.Store(self.root, lambda: self.now)
        self.item = dict(id='1', issueid='2', mainlink='private', comicid='3', link_type='GC-Main')

    def test_attempt_limit_survives_restart_and_mirror_changes(self):
        for attempt in range(6):
            self.item['link_type'] = 'mirror-' + str(attempt)
            self.assertEqual(self.state.begin(self.item), 'ready')
            self.state.finish(self.item, False)
        restored = control.Store(self.root, lambda: self.now)
        self.assertEqual(restored.begin(self.item), 'exhausted')
        restored.reset('1')
        self.assertEqual(restored.begin(self.item), 'ready')

    def test_provider_cooldown_does_not_block_other_provider(self):
        for _ in range(2):
            self.state.begin(self.item)
            self.state.finish(self.item, False)
        self.assertEqual(self.state.begin(dict(self.item, id='other')), 'cooldown')
        self.assertEqual(self.state.begin(dict(self.item, id='third', link_type='GC-Pixel')), 'ready')
        self.now += 901
        self.assertEqual(self.state.begin(self.item), 'ready')

    def test_repeated_bytes_do_not_count_as_new_useful_progress(self):
        self.state.begin(self.item)
        self.now += 10
        self.state.observe('1', 100)
        self.assertEqual(self.state.data['items']['1']['speed'], 10)
        self.now += 10
        self.state.observe('1', 0)
        self.now += 10
        self.state.observe('1', 100)
        self.assertEqual(self.state.data['items']['1']['high_water'], 100)
        self.state.finish(self.item, True)
        self.assertEqual(self.state.begin(self.item), 'completed')

    def test_corrupt_control_state_is_not_silently_discarded(self):
        self.state.path.write_text('{broken')
        with self.assertRaises(ValueError):
            control.Store(self.root)
        self.assertEqual(self.state.path.read_text(), '{broken')

    def test_recovery_is_idempotent_and_prefers_matching_partial(self):
        row = dict(self.item, link='redacted', series='Comic', year='2026', size='100 B', filename='comic.cbz',
                   site='DDL(GetComics)', remote_filesize=100, status='Downloading')
        (self.root/'comic.cbz.part').write_bytes(b'x'*20)
        database = MagicMock()
        database.select.return_value = [row, dict(row, id='existing', status='Queued')]
        mylar = SimpleNamespace(CONFIG=SimpleNamespace(DDL_LOCATION=str(self.root), DDL_AUTORESUME=True),
                                DDL_QUEUED=['1'], db=SimpleNamespace(DBConnection=lambda: database))
        queue = Queue();queue.put(dict(row, id='existing'))
        with patch.dict(sys.modules, {'mylar': mylar}):
            control.recover(queue)
            control.recover(queue)
        self.assertEqual(queue.qsize(), 2)
        queue.get()
        restored = queue.get()
        self.assertEqual(restored['resume'], 20)
        self.assertEqual(mylar.DDL_QUEUED, [])

    def test_diagnostics_follow_import_state_without_rewriting_attempt_history(self):
        database = sqlite3.connect(':memory:')
        self.addCleanup(database.close)
        database.row_factory = sqlite3.Row
        database.executescript("""
            CREATE TABLE ddl_info(id TEXT, issueid TEXT, status TEXT, pack INTEGER);
            CREATE TABLE issues(IssueID TEXT, Status TEXT, Location TEXT);
            CREATE TABLE annuals(IssueID TEXT, Status TEXT, Location TEXT);
            INSERT INTO ddl_info VALUES ('1','2','Completed',0),('pack','2','Completed',1),
              ('annual','3','Completed',0),('queued','2','Queued',0),('missing','4','Completed',0);
            INSERT INTO issues VALUES ('2','Snatched',NULL),('4','Downloaded',NULL);
            INSERT INTO annuals VALUES ('3','Downloaded','annual.cbz');
        """)
        mylar = SimpleNamespace(db=SimpleNamespace(DBConnection=lambda: SimpleNamespace(
            select=lambda query: database.execute(query).fetchall())))
        self.state.begin(self.item)
        self.state.finish(self.item, True)
        self.state.data['providers']['GC-Main']['until'] = self.now + 900
        rows = database.execute('SELECT * FROM ddl_info').fetchall()
        with patch.dict(sys.modules, {'mylar': mylar}), patch.object(control, '_STORE', self.state):
            before = control.diagnostics(rows)
            self.assertEqual(before['1']['reason'], 'Downloaded; awaiting post-processing')
            database.execute("UPDATE issues SET Status='Downloaded', Location='comic.cbz' WHERE IssueID='2'")
            after = control.diagnostics(rows)
        self.assertEqual(after['1']['reason'], 'Post-processed; in library')
        self.assertEqual(after['annual']['reason'], 'Post-processed; in library')
        for key in ('pack', 'missing'):
            self.assertEqual(after[key]['reason'], 'Downloaded; awaiting post-processing')
        self.assertFalse(after['queued']['finished'])
        self.assertTrue(after['1']['finished'])
        self.assertEqual(after['1']['cooldown_seconds'], 0)
        self.assertEqual(after['1']['attempts'], 1)
        self.assertEqual(self.state.data['items']['1']['reason'], 'Downloaded; handed to post-processing')

    def test_health_does_not_treat_retry_churn_as_progress(self):
        from health import assess
        value = {'enabled': ['DDL-QUEUE'], 'queues': {'DDL-QUEUE': {'alive': True, 'size': 10}},
                 'downloaded': 1, 'completed': 0, 'processing': False, 'ddl_active': [['1', 100, 'now']], 'ddl_useful': [100, 0]}
        before = assess(value, {}, 0)
        value['ddl_active'] = [['2', 0, 'later']]
        value['queues']['DDL-QUEUE']['size'] = 9
        self.assertIn('DDL-QUEUE has made no progress for 15 minutes', assess(value, before['observations'], 900)['errors'])
        value['ddl_useful'][0] = 101
        self.assertFalse(assess(value, before['observations'], 900)['errors'])


if __name__ == '__main__':
    unittest.main()
