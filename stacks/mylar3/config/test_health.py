"""Worker liveness, progress, idle, and image patch contract regression tests."""
import ast
from pathlib import Path
import sys
import unittest

from health import assess
from patch_diagnostics_api import patched_source

SOURCE = Path(sys.argv.pop(1)) if len(sys.argv) > 1 else None


class HealthTest(unittest.TestCase):
    def setUp(self):
        self.value = {'enabled': ['POST-PROCESS-QUEUE', 'DDL-QUEUE'],
                      'queues': {name: {'alive': True, 'size': 0} for name in ('POST-PROCESS-QUEUE', 'DDL-QUEUE')},
                      'downloaded': 12, 'completed': 0, 'processing': False, 'ddl_active': []}

    def test_worker_progress_includes_annuals_without_deleted_shadows(self):
        import sqlite3, sys, worker_health
        from types import SimpleNamespace
        from unittest.mock import patch, Mock
        database=sqlite3.connect(':memory:');self.addCleanup(database.close)
        database.row_factory=sqlite3.Row
        database.executescript("""
            CREATE TABLE issues(IssueID TEXT,Status TEXT);
            CREATE TABLE annuals(IssueID TEXT,Status TEXT,Deleted INT);
            CREATE TABLE ddl_info(ID TEXT,status TEXT);
            INSERT INTO issues VALUES ('1','Downloaded'),('2','Downloaded'),('3','Downloaded');
            INSERT INTO annuals VALUES ('2','Downloaded',0),('3','Downloaded',1),('4','Archived',0);
        """)
        app=SimpleNamespace(CONFIG=SimpleNamespace(POST_PROCESSING=True,ENABLE_DDL=True,NZB_DOWNLOADER=1,
            NZBGET_CLIENT_POST_PROCESSING=True,ENABLE_TORRENTS=False,ENABLE_CHECK_FOLDER=False,FAILED_AUTO=True),
            APILOCK=False,db=SimpleNamespace(DBConnection=lambda:SimpleNamespace(
                selectone=lambda q:database.execute(q),select=lambda q:database.execute(q).fetchall())),
            queue_control=SimpleNamespace(diagnostics=Mock(),useful_progress=lambda:[0,0]),
            cooldown_health=SimpleNamespace(snapshot=lambda db:{'valid':True}),
            workflow=SimpleNamespace(state_health=lambda:{'valid':True}))
        with patch.dict(sys.modules,{'mylar':app,'mylar.queues':SimpleNamespace(queue_info=lambda:[])}):
            self.assertEqual(worker_health.snapshot()['downloaded'],3)

    def test_probe_uses_configured_url_root(self):
        import health, json, tempfile
        from unittest.mock import patch
        from io import BytesIO
        with tempfile.TemporaryDirectory() as directory:
            Path(directory,'config.ini').write_text('[General]\napi_key=fixture\n[Interface]\nhttp_port=8090\nhttp_root=/comics/\n')
            reply=BytesIO(json.dumps({'success':True,'data':self.value}).encode())
            with patch.dict(health.os.environ,MYLAR_CONFIG_DIR=directory), patch.object(health.urllib.request,'urlopen',return_value=reply) as request:
                self.assertEqual(health.main(),0)
            self.assertEqual(request.call_args.args[0].full_url,'http://127.0.0.1:8090/comics/api')

    def test_idle_is_healthy_indefinitely(self):
        initial = assess(self.value, {}, 0)
        self.assertFalse(assess(self.value, initial['observations'], 10000)['errors'])

    def test_paused_queue_is_expected_but_active_stalls_still_alert(self):
        self.value['workflow']={'valid':True,'ddl_paused':True}
        self.value['queues']['DDL-QUEUE']['size']=5
        initial=assess(self.value,{},0)
        self.assertFalse(assess(self.value,initial['observations'],10000)['errors'])
        self.value['ddl_active']=[['id',1,'date']]
        initial=assess(self.value,{},0)
        self.assertTrue(assess(self.value,initial['observations'],1000)['errors'])

    def test_dead_worker_is_immediate_error(self):
        self.value['queues']['DDL-QUEUE']['alive'] = False
        self.assertIn('DDL-QUEUE is down', assess(self.value, {}, 0)['errors'])

    def test_new_arrivals_cannot_hide_stall(self):
        self.value['processing'] = True
        initial = assess(self.value, {}, 0)
        self.value['completed'] = 2
        self.value['queues']['POST-PROCESS-QUEUE']['size'] = 4
        self.assertFalse(assess(self.value, initial['observations'], 899)['errors'])
        self.assertIn('POST-PROCESS-QUEUE has made no progress for 15 minutes',
                      assess(self.value, initial['observations'], 900)['errors'])

    def test_download_progress_resets_stall_and_idle_recovers(self):
        self.value['ddl_active'] = [['id', 1, 'date']]
        initial = assess(self.value, {}, 0)
        self.assertTrue(assess(self.value, initial['observations'], 900)['errors'])
        self.value['ddl_active'][0][1] = 2
        self.assertFalse(assess(self.value, initial['observations'], 900)['errors'])
        self.value['ddl_active'] = []
        self.assertFalse(assess(self.value, initial['observations'], 900)['errors'])

    def test_completed_import_resets_timer(self):
        self.value['completed'] = 3
        initial = assess(self.value, {}, 0)
        self.value['downloaded'] += 1
        self.assertFalse(assess(self.value, initial['observations'], 900)['errors'])

    def test_unknown_api_source_fails_closed(self):
        with self.assertRaises(ValueError):
            patched_source('def changed(): pass')

    @unittest.skipUnless(SOURCE, 'Provide candidate source directory')
    def test_candidate_patch_idempotent_and_primary_key_required(self):
        source = patched_source((SOURCE / 'api.py').read_text())
        self.assertEqual(patched_source(source), source)
        tree = ast.parse(source)
        for name in ('_getHealth', '_reportFailedDownload'):
            node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
            from types import SimpleNamespace
            from unittest.mock import Mock
            obj = SimpleNamespace(apikey='download-key', _failureResponse=Mock(return_value='denied'))
            namespace = {'mylar': SimpleNamespace(CONFIG=SimpleNamespace(API_ENABLED=True, API_KEY='primary-key'))}
            exec(compile(ast.Module(body=[node], type_ignores=[]), '<api>', 'exec'), namespace)
            namespace[name](obj)
            self.assertEqual(obj.data, 'denied')


if __name__ == '__main__':
    unittest.main()
