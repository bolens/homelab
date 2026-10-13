"""Cache holds retain the native original DDL generation and provider attempts."""
import copy
import datetime
from pathlib import Path
from queue import Queue
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import cache_admission
import patch_cache_admission as cache_patch
import patch_ddl_status_retention as status_patch
import queue_control
from test_status_retention import DB, DDL, function


class CacheDDL(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.db=DB();self.addCleanup(self.db.connection.close)
        self.item=dict(id='fixture',issueid='42',comicid='7',link='https://fixture.invalid/source',mainlink='https://fixture.invalid/release',site='DDL(GetComics)',series='Fixture #2',link_type='GC-Main',resume=None,remote_filesize=0,oneoff=False,comicinfo=None,packinfo=None)
        self.values={k:self.item[k] for k in ('issueid','comicid','link','mainlink','site','series','link_type')}
        self.values.update(status='Queued',updated_date='original',year='2023',issues='2',pack=0)
        self.db.upsert('ddl_info',self.values,{'id':'fixture'})
        self.store=queue_control.Store(Path(self.temp.name));self.assertEqual(self.store.begin(self.item),'ready')
        value=self.store.record(self.item);self.item['_cache_admission_attempt']=(value['release'],value['attempts'],value['started'])
        self.app=types.SimpleNamespace(DDL_LOCK=False,DDL_QUEUED=['fixture'],CONFIG=types.SimpleNamespace(POST_PROCESSING=False))
        self.addCleanup(patch.stopall)
        patch.dict(sys.modules,{'mylar':self.app}).start()
        patch.object(queue_control,'store',return_value=self.store).start()
        patch.object(queue_control.time,'sleep',return_value=None).start()
        self.source=cache_patch.worker(status_patch.patched_source(DDL.read_text()))
        self.assertEqual(cache_patch.worker(self.source),self.source)

    def run_worker(self, mutation=None):
        q=Queue();q.put(copy.deepcopy(self.item));q.put('exit')
        def download(*a):
            if mutation=='remove':self.db.action('DELETE FROM ddl_info')
            elif mutation=='handoff':self.db.action("UPDATE ddl_info SET status='NZB handoff'")
            elif mutation=='date':self.db.action("UPDATE ddl_info SET updated_date='foreign'")
            raise cache_admission.Held('Cache byte budget reached; retained originals require owning recovery')
        control=types.SimpleNamespace(recover=lambda q:None,begin=lambda *a:True,clear_active=queue_control.clear_active,cache_held=queue_control.cache_held)
        ns=dict(mylar=self.app,cache_admission=cache_admission,db=types.SimpleNamespace(DBConnection=lambda:self.db),queue_control=control,
                queue_schedule=types.SimpleNamespace(take=lambda q:q.get_nowait(),started=lambda i:None),
                workflow=types.SimpleNamespace(ddl_begin=lambda f,i,q:f(i,q),ddl_finished=lambda *a:None),
                logger=types.SimpleNamespace(info=lambda *a:None,fdebug=lambda *a:None,warn=lambda *a:None),
                getcomics=types.SimpleNamespace(GC=lambda *a,**kw:types.SimpleNamespace(downloadit=download)),
                datetime=datetime,time=types.SimpleNamespace(sleep=lambda *a:None))
        exec(status_patch.HELPERS,ns);function(self.source,'_ddl_cache_requeue',ns)
        function(self.source,'ddl_downloader',ns)(q)
        return q

    def test_owning_worker_capacity_hold_refunds_only_original_attempt(self):
        q=self.run_worker();row=dict(self.db.selectone('SELECT * FROM ddl_info').fetchone())
        self.assertEqual(row['status'],'Queued');self.assertEqual(row['issueid'],'42');self.assertEqual(row['comicid'],'7')
        self.assertEqual(self.store.record(self.item)['attempts'],0);self.assertIn('Cache byte budget',self.store.record(self.item)['reason'])
        self.assertEqual(q.qsize(),1);self.assertEqual(self.app.DDL_QUEUED,[]);self.assertFalse(self.app.DDL_LOCK)

    def test_late_remove_never_recreates_row_or_refunds_foreign_generation(self):
        q=self.run_worker('remove');self.assertIsNone(self.db.selectone('SELECT * FROM ddl_info').fetchone())
        self.assertEqual(q.qsize(),0);self.assertEqual(self.store.record(self.item)['attempts'],1);self.assertEqual(self.app.DDL_QUEUED,[])

    def test_late_nzb_handoff_remains_removable_without_cache_status_change(self):
        q=self.run_worker('handoff');row=dict(self.db.selectone('SELECT * FROM ddl_info').fetchone())
        self.assertEqual(row['status'],'NZB handoff');self.assertEqual(q.qsize(),0);self.assertEqual(self.store.record(self.item)['attempts'],1)
        self.db.action('DELETE FROM ddl_info WHERE ID=?',['fixture']);self.assertIsNone(self.db.selectone('SELECT * FROM ddl_info').fetchone())

    def test_late_generation_date_refuses_refund_and_requeue(self):
        q=self.run_worker('date');row=dict(self.db.selectone('SELECT * FROM ddl_info').fetchone())
        self.assertEqual(row['updated_date'],'foreign');self.assertEqual(q.qsize(),0);self.assertEqual(self.store.record(self.item)['attempts'],1)

if __name__=='__main__':unittest.main()
