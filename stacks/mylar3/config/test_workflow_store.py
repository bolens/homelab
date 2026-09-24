"""Durable history and command contract checks with disposable state."""
import tempfile
import unittest
from pathlib import Path
from workflow_store import Store

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

if __name__=='__main__':unittest.main()
