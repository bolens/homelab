"""Post-processing observation lifecycle, privacy, and read-only queue behavior."""
import ast
import json
from pathlib import Path
from queue import Queue
import sqlite3
import sys
import threading
import tempfile
import archive_monitor
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock
import pp_monitor as monitor
from patch_pp_monitor import processor, server, navigation, tagger, api

SOURCE = Path(sys.argv.pop(1)) if len(sys.argv) > 1 else None


class MonitorTest(unittest.TestCase):
    def setUp(self):
        monitor._ACTIVE.clear();monitor._RECENT.clear();monitor._ERRORS=0
        self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
        self.addCleanup(self.db.close)
        self.db.executescript("""
            CREATE TABLE issues(IssueID TEXT, ComicID TEXT, ComicName TEXT, Issue_Number TEXT, Status TEXT, Location TEXT);
            CREATE TABLE snatched(IssueID TEXT, Status TEXT, DateAdded TEXT);
            INSERT INTO issues VALUES ('1','2','Comic','1','Downloaded','comic.cbz'),('3','2','Comic','2','Snatched',NULL);
            INSERT INTO snatched VALUES ('1','Post-Processed','2026-09-24 12:00:00'),('3','Snatched','2026-09-24 12:01:00');
        """)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.mylar=SimpleNamespace(DATA_DIR=self.temp.name, workflow=SimpleNamespace(emit=Mock()), archive_monitor=archive_monitor, pp_monitor=monitor, PP_QUEUE=Queue(),PPPOOL=SimpleNamespace(is_alive=lambda:True),
                                  APILOCK=False,CONFIG=SimpleNamespace(POST_PROCESSING=True),
                                  db=SimpleNamespace(DBConnection=lambda:SimpleNamespace(select=lambda q:self.db.execute(q).fetchall())))
        context=patch.dict(sys.modules,{'mylar':self.mylar});context.start();self.addCleanup(context.stop)

    def job(self, **kwargs):
        return SimpleNamespace(nzb_name='/private/Comic.cbz',nzb_folder='/private/downloads',
                               issueid='1',comicid='2',ddl=True,valreturn=[],**kwargs)

    def test_snapshot_preserves_queue_and_bounds_exposure(self):
        for i in range(110):self.mylar.PP_QUEUE.put({'nzb_name':'/private/comic%d.cbz'%i,'issueid':'1','comicid':'2','ddl':True})
        original=list(self.mylar.PP_QUEUE.queue)
        value=monitor.snapshot()
        self.assertEqual(value['status'],'Queued');self.assertEqual(value['queue_depth'],110)
        self.assertEqual(len(value['waiting']),100);self.assertTrue(value['waiting_truncated'])
        self.assertEqual(original,list(self.mylar.PP_QUEUE.queue));self.assertNotIn('/private',json.dumps(value))
        self.assertEqual([r['name'] for r in value['imports']],['Comic #1'])

    def test_worker_states_are_distinct(self):
        self.assertEqual(monitor.snapshot()['status'],'Idle')
        self.mylar.APILOCK=True
        self.assertIn('lock held',monitor.snapshot()['status'])
        self.mylar.PPPOOL=None
        self.assertEqual(monitor.snapshot()['status'],'Worker unavailable')
        self.mylar.CONFIG.POST_PROCESSING=False
        self.assertEqual(monitor.snapshot()['status'],'Disabled')

    def test_observation_tracks_actual_background_thread_lifetime(self):
        entered=threading.Event();release=threading.Event()
        @monitor.observe
        def process(job):
            entered.set();release.wait(5);return 'native result'
        result=[]
        thread=threading.Thread(target=lambda:result.append(process(self.job())))
        thread.start();self.addCleanup(lambda:(release.set(),thread.join(5)))
        self.assertTrue(entered.wait(2))
        value=monitor.snapshot();self.assertEqual(value['status'],'Processing')
        self.assertEqual(value['active'][0]['name'],'Comic.cbz')
        self.assertEqual(value['recent'],[])
        release.set();thread.join(2)
        self.assertEqual(result,['native result']);self.assertEqual(monitor.snapshot()['active'],[])
        self.assertIn('check confirmed imports',monitor.snapshot()['recent'][0]['outcome'])

    def test_exception_propagates_and_is_not_called_success(self):
        @monitor.observe
        def process(job):raise RuntimeError('secret-path-or-url')
        with self.assertRaisesRegex(RuntimeError,'secret-path-or-url'):process(self.job())
        value=monitor.snapshot();self.assertFalse(value['active'])
        self.assertIn('error',value['recent'][0]['outcome']);self.assertNotIn('secret-path-or-url',json.dumps(value))

    def test_monitor_failure_does_not_change_native_return(self):
        @monitor.observe
        def process(job):return 42
        with patch.object(monitor,'item_info',side_effect=RuntimeError('observer failed')):
            self.assertEqual(process(self.job()),42)
        self.assertEqual(monitor.snapshot()['observer_errors'],1)

    def test_history_bound_and_failure_outcome(self):
        @monitor.observe
        def process(job):job.valreturn=[{'mode':'fail','self.log':'private'}]
        for _ in range(60):process(self.job())
        value=monitor.snapshot();self.assertEqual(len(value['recent']),50)
        self.assertEqual(value['recent'][0]['outcome'],'Processing reported a failure')
        self.assertNotIn('private',json.dumps(value))

    def test_names_and_identifiers_reject_remote_secrets(self):
        self.assertEqual(monitor.display_name('https://host/path?token=secret'),'Name unavailable')
        self.assertEqual(monitor.display_name('C:\\private\\Comic.cbz'),'Comic.cbz')
        self.assertEqual(monitor.identifier('<script>'),'')
        self.assertEqual(monitor.item_info({'nzb_name':'Manual Run','nzb_folder':'/private/comics'})['name'],'comics')

    @unittest.skipUnless(SOURCE,'image source required')
    def test_api_submission_preserves_local_cache_handoff(self):
        from patch_pp_monitor import recovery_api
        from queue import Queue
        from types import SimpleNamespace
        source=recovery_api((SOURCE/'api.py').read_text())
        node=next(n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef) and n.name=='_forceProcess')
        queue=Queue()
        namespace={'workflow':SimpleNamespace(force_process=lambda fn:fn,processing_put=lambda q,item,token=None:q.put(item)),'mylar':SimpleNamespace(PP_QUEUE=queue),'logger':SimpleNamespace(info=lambda *args:None)}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<native-api>','exec'),namespace)
        namespace['_forceProcess'](SimpleNamespace(),nzb_name='Comic.cbz',nzb_folder='/cache/recovery',issueid='1',comicid='2',ddl='True')
        item=queue.get_nowait()
        self.assertIs(item['ddl'],True)
        self.assertIn('download_info',item)
        self.assertIsNone(item['download_info'])

    def test_source_drift_idempotence_and_authenticated_routes(self):
        for fn,name in [(processor,'PostProcessor.py'),(server,'webserve.py'),(tagger,'cmtagmylar.py'),(api,'api.py')]:
            value=fn((SOURCE/name).read_text());self.assertEqual(fn(value),value)
            with self.assertRaises(ValueError):fn('incompatible')
        value=(SOURCE/'webserve.py').read_text()
        self.assertIn('postProcessing.exposed = True',value)
        self.assertIn('postProcessingStatus.exposed = True',value)
        for name in ('manage.html','queue_management.html','import_problems.html'):
            value=(SOURCE.parent/'data/interfaces/default'/name).read_text()
            self.assertEqual(navigation(value),value);self.assertIn('href="postProcessing"',value)
        with self.assertRaises(ValueError):navigation('incompatible')


if __name__=='__main__':unittest.main()
