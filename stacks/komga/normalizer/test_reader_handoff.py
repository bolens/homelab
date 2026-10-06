"""Reader acknowledgements never waive fresh local publication evidence."""
from contextlib import contextmanager
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from publication_guard import scope, Unavailable
from reader_handoff import queue, dispatch
from test_publication_guard import AuthorityFixture


class ReaderHandoffTest(AuthorityFixture, unittest.TestCase):
    def setUp(self):
        AuthorityFixture.setUp(self)
        state=self.root/'worker'; state.mkdir(); jobs=state/'jobs'; jobs.mkdir()
        self.worker=SimpleNamespace(state=state,jobs=jobs,roots=[self.library],
            config={'writer_state':str(self.writer.root),'mylar':{'config_dir':str(self.config)},
                    'publication_roots':[{'native':str(self.native_root),'worker':str(self.library)}]},
            reader=SimpleNamespace(call=Mock(side_effect=self.api)))
        self.bindings=[dict(source=str(self.candidate),target=str(self.source),
                            match={'issueid':'123','comicid':'456'})]
        actual=scope
        @contextmanager
        def portable(*args,**kwargs):
            with actual(*args,**kwargs) as authority:
                authority.tool_root=self.tool
                yield authority
        self.portable=portable
        self.requests=[]

    def api(self, route, data=None):
        self.assertFalse(getattr(self.writer.local[1],'depth',0))
        if route == '/api/v1/libraries':
            return [{'id':'library', 'root':self.library.as_uri()}]
        if data is None:
            return {'id':'book','url':self.source.as_uri()}
        self.assertEqual(json.loads(self.path.read_text())['phase'],'dispatching')
        self.requests.append(route)

    def prepare(self, action='library_scan'):
        with self.writer.hold(),self.portable(self.worker,self.writer):
            self.assertIsNone(queue(self.worker,action,self.bindings,
                folder=self.library if action=='library_scan' else None,
                book_id='book' if action!='library_scan' else None))
        self.path=next((self.worker.state/'reader-handoffs').glob('*.json'))
        return self.path

    def execute(self):
        with patch('reader_handoff.scope',self.portable):
            return dispatch(self.worker)

    def test_exact_current_owner_acknowledged_once_outside_writer(self):
        self.prepare()
        self.assertEqual(self.execute(),1); self.assertEqual(self.execute(),0)
        self.assertEqual(self.requests,['/api/v1/libraries/library/scan'])
        with self.writer.hold(),self.portable(self.worker,self.writer):
            self.assertEqual(queue(self.worker,'library_scan',self.bindings,folder=self.library),
                             {'acknowledged':True})

    def test_lost_reply_retains_attempt_without_replay(self):
        self.prepare()
        original=self.api
        def lost(route,data=None):
            value=original(route,data)
            if data is not None:raise TimeoutError('unknown reader outcome')
            return value
        self.worker.reader.call.side_effect=lost
        self.assertEqual(self.execute(),0); self.assertEqual(self.execute(),0)
        self.assertEqual(json.loads(self.path.read_text())['phase'],'dispatching')
        self.assertEqual(len(self.requests),1)
        self.seed(empty=True)
        with self.writer.hold(),self.portable(self.worker,self.writer),self.assertRaises(Unavailable):
            queue(self.worker,'library_scan',self.bindings,folder=self.library)

    def test_source_or_catalog_drift_prevents_request_without_receipt_rewrite(self):
        self.prepare(); before=self.path.read_bytes()
        self.sql("UPDATE issues SET Status='Wanted'")
        self.assertEqual(self.execute(),0)
        self.assertEqual(self.path.read_bytes(),before); self.assertFalse(self.requests)

    def test_changed_registered_owner_payload_cannot_gain_reader_completion(self):
        changed=self.archive('changed.cbz',[('01.jpg',b'changed')])
        self.source.write_bytes(changed.read_bytes())
        with self.writer.hold(),self.portable(self.worker,self.writer),self.assertRaises(Unavailable):
            queue(self.worker,'library_scan',self.bindings,folder=self.library)
        self.worker.reader.call.assert_not_called()

    def test_successful_http_with_changed_source_is_retained_uncertain(self):
        self.prepare()
        original=self.api
        def drift(route,data=None):
            result=original(route,data)
            if data is not None:self.candidate.write_bytes(b'changed')
            return result
        self.worker.reader.call.side_effect=drift
        self.assertEqual(self.execute(),0); self.assertEqual(self.execute(),0)
        self.assertEqual(len(self.requests),1)
        self.assertEqual(json.loads(self.path.read_text())['phase'],'dispatching')

    def test_changed_plan_is_not_dispatched_and_dispatch_under_writer_is_refused(self):
        self.prepare()
        with self.writer.hold(),self.assertRaises(Unavailable):self.execute()
        row=json.loads(self.path.read_text());row['folder']=str(self.root)
        self.path.write_text(json.dumps(row))
        with self.assertRaises(Unavailable):self.execute()
        self.worker.reader.call.assert_not_called()

    def test_book_analysis_requires_exact_current_reader_url(self):
        self.prepare('analyze')
        self.worker.reader.call.side_effect=lambda route,data=None:{'id':'book','url':self.candidate.as_uri()}
        self.assertEqual(self.execute(),0);self.assertFalse(self.requests)
        self.worker.reader.call.side_effect=self.api
        self.assertEqual(self.execute(),1)
        self.assertEqual(self.requests,['/api/v1/books/book/analyze'])

    def test_coordinated_batch_maps_native_catalog_and_consumes_only_fresh_ack(self):
        from reader_scan import ScanBatch
        self.worker.config.update(reader_scan={'enabled':True,'batch_size':1}, settle_seconds=0)
        now=[1000]
        scans=ScanBatch(self.worker,clock=lambda:now[0])
        self.assertTrue(scans.initialize())
        path=self.archive('arrival.cbz',[('01.jpg',b'new'),
            ('ComicInfo.xml',b'<ComicInfo><Series>Fixture</Series></ComicInfo>')])
        self.sql('INSERT INTO issues VALUES (?,?,?,?)',('777','456',path.name,'Downloaded'))
        with self.writer.hold(),self.portable(self.worker,self.writer):
            self.assertTrue(scans.collect())
        self.path=next((self.worker.state/'reader-handoffs').glob('*.json'))
        self.assertEqual(len(scans.state['pending']),1)
        with patch('reader_handoff.scope',self.portable):scans.dispatch()
        self.assertEqual(len(scans.state['pending']),1, 'HTTP reply alone cannot consume local scan work')
        now[0]+=120
        with self.writer.hold(),self.portable(self.worker,self.writer):
            self.assertTrue(scans.collect())
        self.assertFalse(scans.state['pending'])
        self.assertEqual(self.requests,['/api/v1/libraries/library/scan'])

    def test_coordinated_batch_requires_owned_writer_and_exact_native_owner(self):
        from reader_scan import ScanBatch
        self.worker.config.update(reader_scan={'enabled':True,'batch_size':1}, settle_seconds=0)
        scans=ScanBatch(self.worker,clock=lambda:1000)
        self.assertTrue(scans.initialize())
        path=self.archive('wrong.cbz',[('01.jpg',b'one'),
            ('ComicInfo.xml',b'<ComicInfo><Series>Wrong</Series></ComicInfo>')])
        self.sql('INSERT INTO comics VALUES (?,?)',('888',str(self.native_root)))
        self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',path.name,'Downloaded'))
        with self.writer.hold(),self.portable(self.worker,self.writer):
            self.assertFalse(scans.collect())
        self.assertTrue(path.is_file())
        self.assertFalse((self.worker.state/'reader-handoffs').exists())
        self.worker.reader.call.assert_not_called()

    def test_native_pending_tag_and_repair_paths_block_mapped_reader_additions(self):
        from contextlib import closing
        import sqlite3
        from reader_scan import ScanBatch
        self.worker.config.update(reader_scan={'enabled':True,'batch_size':1}, settle_seconds=0)
        scans=ScanBatch(self.worker,clock=lambda:1000)
        self.assertTrue(scans.initialize())
        path=self.archive('arrival.cbz',[('01.jpg',b'new'),
            ('ComicInfo.xml',b'<ComicInfo><Series>Fixture</Series></ComicInfo>')])
        self.sql('INSERT INTO issues VALUES (?,?,?,?)',('777','456',path.name,'Downloaded'))
        for kind in ('converted_tag','library_repair'):
            with closing(sqlite3.connect(self.workflow)) as db:
                db.execute('DELETE FROM records WHERE kind IN (?,?)',('converted_tag','library_repair'))
                db.execute('INSERT INTO records VALUES (?,?,?,0)',
                    (kind,'pending',json.dumps({'phase':'tagging','path':str(self.native_root/path.name)})))
                db.commit()
            with self.writer.hold(),self.portable(self.worker,self.writer):
                self.assertTrue(scans.collect())
            self.assertEqual(len(scans.state['pending']),1)
            self.assertIsNone(next(iter(scans.state['pending'].values()))['ready_at'])
            self.assertFalse((self.worker.state/'reader-handoffs').exists())
        with closing(sqlite3.connect(self.workflow)) as db:
            db.execute('UPDATE records SET value=? WHERE kind=?',
                (json.dumps({'phase':'tagging','path':'/unmapped/arrival.cbz'}),'library_repair'))
            db.commit()
        with self.writer.hold(),self.portable(self.worker,self.writer):
            self.assertFalse(scans.collect())
        self.worker.reader.call.assert_not_called()

    def test_outside_source_and_malformed_reader_roots_remain_held(self):
        import shutil
        outside=self.root/'outside.cbz'; shutil.copyfile(self.candidate,outside)
        bindings=[dict(self.bindings[0],source=str(outside))]
        with self.writer.hold(),self.portable(self.worker,self.writer),self.assertRaises(Unavailable):
            queue(self.worker,'library_scan',bindings,folder=self.library)
        self.prepare(); before=self.path.read_bytes()
        for root in ('relative', 'file:/', self.library.as_uri()+'/../library'):
            self.worker.reader.call.side_effect=lambda route,data=None:[{'id':'library','root':root}]
            self.assertEqual(self.execute(),0)
            self.assertEqual(self.path.read_bytes(),before)
        self.assertFalse(self.requests)

    def test_new_pending_native_or_worker_job_revokes_prepared_notification(self):
        from contextlib import closing
        import sqlite3
        self.prepare(); before=self.path.read_bytes()
        for kind in ('converted_tag','library_repair'):
            with closing(sqlite3.connect(self.workflow)) as db:
                db.execute('DELETE FROM records WHERE kind IN (?,?)',('converted_tag','library_repair'))
                db.execute('INSERT INTO records VALUES (?,?,?,0)',
                    (kind,'pending',json.dumps({'phase':'tagging','path':str(self.native_root/self.source.name)})))
                db.commit()
            self.assertEqual(self.execute(),0);self.assertEqual(self.path.read_bytes(),before)
        with closing(sqlite3.connect(self.workflow)) as db:
            db.execute('DELETE FROM records WHERE kind IN (?,?)',('converted_tag','library_repair')); db.commit()
        folder=self.worker.jobs/'pending';folder.mkdir()
        receipt=folder/'receipt.json'
        receipt.write_text(json.dumps({'phase':'refresh','destination':str(self.source)}))
        self.assertEqual(self.execute(),0);self.assertEqual(self.path.read_bytes(),before)
        receipt.write_text(json.dumps({'phase':'done','destination':str(self.source), 'mylar_tag_pending':True}))
        self.assertEqual(self.execute(),0);self.assertEqual(self.path.read_bytes(),before)
        receipt.write_text(json.dumps({'phase':'done','destination':str(self.source)}))
        self.assertEqual(self.execute(),1);self.assertEqual(len(self.requests),1)

    def test_new_pending_native_job_after_http_retains_uncertain_attempt(self):
        from contextlib import closing
        import sqlite3
        self.prepare()
        original=self.api
        def pending(route,data=None):
            result=original(route,data)
            if data is not None:
                with closing(sqlite3.connect(self.workflow)) as db:
                    db.execute('INSERT INTO records VALUES (?,?,?,0)',
                        ('library_repair','pending',json.dumps({'phase':'tagging','path':str(self.native_root/self.source.name)})))
                    db.commit()
            return result
        self.worker.reader.call.side_effect=pending
        self.assertEqual(self.execute(),0); self.assertEqual(self.execute(),0)
        self.assertEqual(json.loads(self.path.read_text())['phase'],'dispatching')
        self.assertEqual(len(self.requests),1)

    def test_pending_fence_and_ambiguous_library_preserve_prepared_request(self):
        self.prepare(); before=self.path.read_bytes()
        with self.writer.hold(allow_pending=True):self.writer.mark_pending()
        self.assertEqual(self.execute(),0);self.assertEqual(self.path.read_bytes(),before)
        with self.writer.hold(allow_pending=True):self.writer.clear_pending()
        self.worker.reader.call.side_effect=lambda route,data=None:[
            {'id':'one','root':self.library.as_uri()}, {'id':'two','root':self.library.as_uri()}]
        self.assertEqual(self.execute(),0); self.assertEqual(self.path.read_bytes(),before)


if __name__=='__main__':unittest.main()
