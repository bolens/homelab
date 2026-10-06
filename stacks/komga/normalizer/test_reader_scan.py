"""Completion scans preserve queued work and stay outside media publication."""
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

from reader_scan import ScanBatch, policy, tagged_cbz


class ScanTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.media = self.root/'comics'; self.media.mkdir()
        self.state = self.root/'state'; self.state.mkdir()
        self.jobs = self.state/'jobs'; self.jobs.mkdir()
        self.mylar = self.root/'mylar'; self.mylar.mkdir()
        self.db = sqlite3.connect(self.mylar/'mylar.db'); self.addCleanup(self.db.close)
        self.db.executescript('''CREATE TABLE comics (ComicID TEXT, ComicLocation TEXT);
            CREATE TABLE issues (IssueID TEXT, ComicID TEXT, Status TEXT, Location TEXT);
            CREATE TABLE annuals (IssueID TEXT, ComicID TEXT, Status TEXT, Location TEXT, Deleted INTEGER);
        ''')
        self.db.execute('INSERT INTO comics VALUES (?,?)', ('series', str(self.media)))
        self.db.commit()
        self.workflow = sqlite3.connect(self.mylar/'workflow.sqlite'); self.addCleanup(self.workflow.close)
        self.workflow.execute('CREATE TABLE records (kind TEXT, key TEXT, value TEXT, updated REAL)')
        self.workflow.commit()
        self.now = 1000
        self.requests = []
        self.libraries = [{'id':'comics-id', 'root':self.media.as_uri()},
                          {'id':'other', 'root':(self.root/'manga').as_uri()}]
        def request(route, data=None):
            if data is None:return self.libraries
            self.requests.append(route)
        self.worker = SimpleNamespace(config={'reader_scan':{'enabled':True}, 'settle_seconds':120,
            'writer_state':str(self.root/'writer'), 'mylar':{'config_dir':str(self.mylar)}},
            roots=[self.media], state=self.state, jobs=self.jobs, reader=SimpleNamespace(call=Mock(side_effect=request)))
        self.scan = ScanBatch(self.worker, clock=lambda:self.now)
        # These legacy batching vectors do not initialize publication authority.
        self.coordination_policy = patch('reader_scan.policy', side_effect=lambda config:policy(dict(config, writer_state=str(self.root/'writer'))))
        self.coordination_policy.start(); self.addCleanup(self.coordination_policy.stop)
        self.worker.config['writer_state'] = None

    def cycle(self, advance=0):
        self.now += advance
        self.assertTrue(self.scan.collect())
        self.scan.dispatch()

    def add(self, name, xml=b'<ComicInfo><Series>Fixture</Series></ComicInfo>', nested=False):
        path = self.media/(name+'.cbz')
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('page.jpg', b'fixture image')
            if xml is not None:z.writestr('ComicInfo.xml', xml)
            if nested:z.writestr('sub/ComicInfo.xml', b'<ComicInfo/>')
        self.db.execute('INSERT INTO issues VALUES (?,?,?,?)', (name,'series','Downloaded',path.name))
        self.db.commit()
        return path

    def ready(self, count=5):
        self.cycle()
        for i in range(count):self.add(str(i))
        self.cycle()
        self.cycle(120)

    def test_initial_catalog_baseline_never_opens_archives_or_replays(self):
        self.add('existing')
        with patch('reader_scan.tagged_cbz', side_effect=AssertionError('baseline opened archive')):
            self.cycle()
        self.assertEqual(len(self.scan.state['known']),1)
        self.assertFalse(self.scan.state['pending']); self.assertFalse(self.requests)
        self.cycle(1000); self.assertFalse(self.requests)

    def test_startup_baseline_needs_no_archive_or_writer_access(self):
        self.add('existing')
        with patch('reader_scan.tagged_cbz',side_effect=AssertionError('archive opened')):
            self.assertTrue(self.scan.initialize())
        self.assertEqual(len(self.scan.state['known']),1)
        self.assertFalse(self.scan.state['pending'])
        self.worker.reader.call.assert_not_called()
        self.add('new-after-startup')
        self.assertTrue(self.scan.initialize())
        self.assertEqual(len(self.scan.state['known']),1, 'Restart must not rebaseline new additions')
        self.cycle();self.assertEqual(len(self.scan.state['pending']),1)

    def test_unrelated_pending_conversion_does_not_block_completed_batch(self):
        self.cycle()
        for i in range(6):self.add(str(i))
        folder=self.jobs/'active';folder.mkdir()
        (folder/'receipt.json').write_text(json.dumps({'phase':'submitted','destination':str(self.media/'5.cbz')}))
        self.cycle();self.cycle(120)
        self.assertEqual(len(self.requests),1)
        self.assertEqual(len(self.scan.state['pending']),1)
        self.assertEqual(next(iter(self.scan.state['pending'].values()))['path'],str(self.media/'5.cbz'))

    def test_five_ready_additions_scan_only_matching_library_once(self):
        self.ready()
        self.assertEqual(self.requests, ['/api/v1/libraries/comics-id/scan'])
        self.assertFalse(self.scan.state['pending'])
        self.cycle(1000); self.assertEqual(len(self.requests),1)

    def test_tail_flush_survives_restart_and_obeys_minimum_interval(self):
        self.ready(1)
        self.assertFalse(self.requests)
        self.scan = ScanBatch(self.worker,clock=lambda:self.now)
        self.cycle(299); self.assertFalse(self.requests)
        self.cycle(1); self.assertEqual(len(self.requests),1)
        self.worker.config['reader_scan']['batch_size'] = 1
        self.worker.config['settle_seconds'] = 0
        self.scan = ScanBatch(self.worker,clock=lambda:self.now)
        self.add('next'); self.cycle(1); self.assertEqual(len(self.requests),1)
        self.cycle(119); self.assertEqual(len(self.requests),2)

    def test_unfinished_metadata_and_changed_identity_defer(self):
        self.cycle()
        paths = [self.add('no-tags',None), self.add('bad-tags',b'<bad'),
                 self.add('nested',nested=True), self.add('unstable')]
        self.cycle()
        paths[-1].write_bytes(paths[-1].read_bytes()+b'changed')
        self.cycle(120); self.cycle(1000)
        self.assertFalse(self.requests)
        self.assertTrue(all(x['ready_at'] is None for x in self.scan.state['pending'].values()))
        self.assertFalse(tagged_cbz(paths[0].with_suffix('.cbr')))

    def test_pending_tag_and_conversion_receipts_revoke_readiness(self):
        self.ready(1)
        path = self.media/'0.cbz'
        self.workflow.execute('INSERT INTO records VALUES (?,?,?,0)',
                              ('converted_tag','one',json.dumps({'path':str(path),'phase':'tagging'})))
        self.workflow.commit()
        self.cycle(300); self.assertFalse(self.requests)
        self.workflow.execute('UPDATE records SET value=?',(json.dumps({'path':str(path),'phase':'completed'}),))
        self.workflow.commit()
        folder=self.jobs/'convert'; folder.mkdir(); receipt=folder/'receipt.json'
        receipt.write_text(json.dumps({'phase':'done','destination':str(path),'mylar_tag_pending':True}))
        self.cycle(300); self.assertFalse(self.requests)
        receipt.write_text(json.dumps({'phase':'done','destination':str(path)}))
        self.cycle(); self.cycle(300); self.assertEqual(len(self.requests),1)

    def test_annual_deleted_ambiguous_and_out_of_scope_catalog(self):
        self.cycle()
        annual=self.add('annual')
        self.db.execute('INSERT INTO annuals VALUES (?,?,?,?,?)',('annual','series','Downloaded',annual.name,0))
        self.db.execute('INSERT INTO annuals VALUES (?,?,?,?,?)',('deleted','series','Downloaded','deleted.cbz',1))
        self.db.execute('INSERT INTO issues VALUES (?,?,?,?)',('escape','series','Downloaded','../escape.cbz'))
        self.db.commit()
        catalog=self.scan.catalog(); self.assertEqual(list(catalog.values()),[str(annual)])
        self.db.execute('INSERT INTO issues VALUES (?,?,?,?)',('duplicate','series','Downloaded',annual.name))
        self.db.commit(); self.assertFalse(self.scan.catalog())

    def test_missing_symlink_and_deleted_pending_entries_never_dispatch(self):
        self.ready(1)
        path=self.media/'0.cbz'; target=self.root/'outside.cbz'; path.rename(target); path.symlink_to(target)
        self.cycle(300); self.assertFalse(self.requests)
        path.unlink(); self.cycle(300); self.assertFalse(self.requests)
        self.db.execute('DELETE FROM issues'); self.db.commit(); self.cycle()
        self.assertFalse(self.scan.state['pending'])

    def test_api_failure_retains_candidates_and_pacing_across_restart(self):
        self.cycle()
        for i in range(5):self.add(str(i))
        self.cycle()
        original=self.worker.reader.call.side_effect
        self.worker.reader.call.side_effect=OSError('fixture')
        self.cycle(120)
        self.assertEqual(len(self.scan.state['pending']),5)
        self.assertTrue(json.loads(self.scan.status_path.read_text())['errors'])
        self.worker.reader.call.reset_mock()
        self.scan=ScanBatch(self.worker,clock=lambda:self.now)
        self.cycle(119); self.worker.reader.call.assert_not_called()
        self.worker.reader.call.side_effect=original
        self.cycle(1); self.assertEqual(len(self.requests),1)
        self.assertFalse(json.loads(self.scan.status_path.read_text())['errors'])

    def test_partial_library_acknowledgment_retries_only_unacknowledged_group(self):
        self.cycle()
        second=self.media/'second'; second.mkdir()
        self.libraries=[{'id':'first','root':(self.media/'first').as_uri()},
                        {'id':'second','root':second.as_uri()}]
        first=self.media/'first'; first.mkdir()
        self.worker.config['reader_scan']['batch_size']=1
        self.scan=ScanBatch(self.worker,clock=lambda:self.now)
        for name,folder in [('one',first),('two',second)]:
            path=self.add(name); path.rename(folder/path.name)
            self.db.execute('UPDATE issues SET Location=? WHERE IssueID=?',(str(folder/path.name),name))
        self.db.commit(); self.cycle()
        original=self.worker.reader.call.side_effect
        def call(route,data=None):
            if route.endswith('/second/scan'):raise OSError('fixture')
            return original(route,data)
        self.worker.reader.call.side_effect=call
        self.cycle(120)
        self.assertEqual(len(self.scan.state['pending']),1)
        self.assertEqual(self.requests,['/api/v1/libraries/first/scan'])
        self.worker.reader.call.side_effect=original
        self.cycle(120)
        self.assertEqual(self.requests,['/api/v1/libraries/first/scan','/api/v1/libraries/second/scan'])

    def test_unknown_or_ambiguous_library_preserves_queue(self):
        self.libraries.append(dict(self.libraries[0],id='overlap'))
        self.ready()
        self.assertFalse(self.requests); self.assertEqual(len(self.scan.state['pending']),5)
        self.assertTrue(json.loads(self.scan.status_path.read_text())['errors'])

    def test_corrupt_journal_is_never_silently_rebaselined(self):
        self.cycle()
        original=self.scan.path.read_text()
        for content in ('[]', '{}', '{broken', original.replace('"pending": {}','"pending": {"bad": null}')):
            self.scan.path.write_text(content)
            self.assertFalse(self.scan.collect())
            self.assertEqual(self.scan.path.read_text(),content)
            self.assertTrue(json.loads(self.scan.status_path.read_text())['errors'])

    def test_fifty_file_budget_is_fair_and_stale_readiness_is_not_dispatched(self):
        self.cycle()
        for i in range(110):self.add(str(i))
        original=tagged_cbz
        with patch('reader_scan.tagged_cbz',side_effect=original) as inspect:
            for _ in range(8):
                inspect.reset_mock(); self.cycle(120)
                self.assertLessEqual(inspect.call_count,50)
        self.assertFalse(self.scan.state['pending'])
        # A ready but not inspected entry must not be dispatched on old evidence.
        self.add('later'); self.cycle(); self.now+=120
        self.assertTrue(self.scan.collect()); self.scan.validated.clear(); self.now+=300
        count=len(self.requests); self.scan.dispatch(); self.assertEqual(len(self.requests),count)

    def test_reads_only_comicinfo_and_rejects_entities_and_oversize_xml(self):
        path=self.add('one')
        original=zipfile.ZipFile.open
        opened=[]
        def inspect(archive,name,*args,**kwargs):
            opened.append(name.filename if isinstance(name,zipfile.ZipInfo) else name)
            return original(archive,name,*args,**kwargs)
        with patch.object(zipfile.ZipFile,'open',inspect):self.assertTrue(tagged_cbz(path))
        self.assertEqual(opened,['ComicInfo.xml'])
        self.assertFalse(tagged_cbz(self.add('entities',b'<!DOCTYPE ComicInfo><ComicInfo/>')))
        self.assertFalse(tagged_cbz(self.add('huge',b'<ComicInfo>'+b'x'*262144+b'</ComicInfo>')))

    def test_policy_rejects_invalid_types_ranges_and_missing_coordination(self):
        self.assertFalse(policy({})['enabled'])
        for setting,value in [('enabled',1),('batch_size',True),('batch_size',0),('batch_size',101),
                              ('max_wait_seconds',0),('min_interval_seconds',1.5)]:
            with self.subTest(setting=setting,value=value),self.assertRaises(ValueError):
                policy({'reader_scan':{setting:value}})
        for extra in ({},{'writer_state':[]},{'writer_state':'relative'},
                      {'writer_state':'/valid','mylar':{'config_dir':''}}):
            with self.assertRaises(ValueError):policy(dict(extra,reader_scan={'enabled':True}))


if __name__=='__main__':unittest.main()
