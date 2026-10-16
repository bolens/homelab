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



class BusyHealthTest(unittest.TestCase):
    """Real SQLite bootstrap/Writer contention; only in-process queue reports projected."""
    def setUp(self):
        import importlib
        from types import SimpleNamespace
        from unittest.mock import patch
        from test_publication_startup import ExistingAdmissionTests
        self.fixture=ExistingAdmissionTests('runTest');self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.f=self.fixture;self.f.authority();self.f.activate()
        self.worker=importlib.import_module('mylar.worker_health')
        self.f.mylar.CONFIG=SimpleNamespace(POST_PROCESSING=True,ENABLE_DDL=True,NZB_DOWNLOADER=1,
            NZBGET_CLIENT_POST_PROCESSING=True,SAB_CLIENT_POST_PROCESSING=False,ENABLE_TORRENTS=False,
            AUTO_SNATCH=False,TORRENT_DOWNLOADER=2)
        self.f.mylar.OS_DETECT='Linux'
        self.queues=[SimpleNamespace(name=n,is_alive=True,size=0) for n in ('SEARCH-QUEUE','POST-PROCESS-QUEUE','DDL-QUEUE','AUTO-COMPLETE-NZB','AUTO-SNATCHER')]
        self.queues[0].size=12047
        ctx=patch.dict(sys.modules,{'mylar.queues':SimpleNamespace(queue_info=lambda:self.queues)})
        ctx.start();self.addCleanup(ctx.stop)
        self.full=dict(publication=dict(version=1,state='ready',reason='verified',census={}),
            queues={q.name:dict(alive=q.is_alive,size=q.size) for q in self.queues},
            enabled=['SEARCH-QUEUE','POST-PROCESS-QUEUE','DDL-QUEUE','AUTO-COMPLETE-NZB'],
            downloaded=1,completed=0,processing=False,ddl_active=[])

    def held_sample(self):
        import threading
        from unittest.mock import patch
        entered=threading.Event();release=threading.Event();errors=[]
        def hold():
            try:
                with self.f.Writer(self.f.root/'media-writer',create=False).hold():
                    entered.set()
                    if not release.wait(3):raise RuntimeError('fixture deadline')
            except BaseException as error:errors.append(error)
        thread=threading.Thread(target=hold);thread.start()
        try:
            self.assertTrue(entered.wait(1))
            before={str(p):p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()}
            # The original authority probe must encounter actual exclusion before any SQL.
            with patch('sqlite3.connect',side_effect=AssertionError('busy health cannot open SQL')),patch.object(self.worker,'_snapshot',side_effect=AssertionError('busy health cannot enter mutating snapshot')):
                value=self.worker.snapshot()
            self.assertEqual(before,{str(p):p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()})
            return value
        finally:
            release.set();thread.join(3)
            self.assertFalse(thread.is_alive());self.assertEqual(errors,[])

    def test_actual_busy_is_liveness_only_without_database_or_recovery(self):
        sample=self.held_sample()
        self.assertEqual(sample['publication'],dict(version=1,state='held',reason='writer-busy',census=None))
        self.assertFalse(assess(sample,{},sample['time'])['errors'])
        self.assertIs(sample['busy_workers']['startup_complete'],True)
        self.f.tagger.recover.assert_not_called();self.f.release.recover.assert_not_called()
        self.assertNotIn('workflow',sample);self.assertNotIn('downloaded',sample)

    def test_actual_cross_process_flock_contention_remains_observational(self):
        import subprocess,select
        from unittest.mock import patch
        code="import sys;sys.path.insert(0,sys.argv[1]);from media_writer import Writer;w=Writer(sys.argv[2],create=False);\nwith w.hold():\n print('held',flush=True);sys.stdin.buffer.read(1)"
        child=subprocess.Popen([sys.executable,'-I','-B','-c',code,str(Path(__file__).parent),str(self.f.root/'media-writer')],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            self.assertTrue(select.select([child.stdout],[],[],2)[0])
            self.assertEqual(child.stdout.readline(),b'held\n')
            with patch('sqlite3.connect',side_effect=AssertionError('busy cannot open SQL')),patch.object(self.worker,'_snapshot',side_effect=AssertionError('busy cannot read Store')):
                sample=self.worker.snapshot()
            self.assertEqual(sample['publication']['reason'],'writer-busy')
            self.assertFalse(assess(sample,{},sample['time'])['errors'])
        finally:
            try:child.communicate(b'x',timeout=3)
            except subprocess.TimeoutExpired:child.kill();child.communicate()
        self.assertEqual(child.returncode,0)

    def test_busy_during_incomplete_startup_stays_unhealthy(self):
        self.f.native._STARTUP_COMPLETE=False
        sample=self.held_sample();self.assertNotIn('busy_workers',sample)
        self.assertTrue(assess(sample,{},sample['time'])['errors'])

    def test_ready_probe_then_real_contention_never_enters_long_operation(self):
        import threading,time
        from unittest.mock import patch
        entered=threading.Event();release=threading.Event();errors=[]
        def held():
            try:
                with self.f.Writer(self.f.root/'media-writer',create=False).hold():
                    entered.set()
                    if not release.wait(3):raise RuntimeError('fixture deadline')
            except BaseException as error:errors.append(error)
        thread=threading.Thread(target=held)
        actual=self.f.native.startup_status
        sql=patch('sqlite3.connect',side_effect=AssertionError('no SQL after ready-to-busy race'))
        def status():
            value=actual();self.assertEqual(value['state'],'ready')
            thread.start();self.assertTrue(entered.wait(1));sql.start()
            return value
        started=time.monotonic()
        try:
            with patch.object(self.f.native,'startup_status',side_effect=status),patch.object(self.worker,'_snapshot',side_effect=AssertionError('busy cannot enter full snapshot')):
                sample=self.worker.snapshot()
            self.assertLess(time.monotonic()-started,1)
            self.assertEqual(sample['publication']['reason'],'writer-busy')
            self.assertFalse(assess(sample,{},sample['time'])['errors'])
        finally:
            sql.stop();release.set();thread.join(3)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[])

    def test_real_negative_phase_busy_is_not_healthy_contention(self):
        from unittest.mock import patch
        marker=self.f.root/'media-writer'/'negative-retirement-v1.pending'
        marker.write_bytes(b'disposable held phase')
        before=marker.read_bytes()
        with patch('sqlite3.connect',side_effect=AssertionError('held phase cannot open SQL')):
            sample=self.worker.snapshot()
        self.assertEqual(sample['publication']['reason'],'writer-busy')
        self.assertNotIn('busy_workers',sample)
        self.assertTrue(assess(sample,{},sample['time'])['errors'])
        self.assertEqual(marker.read_bytes(),before)

    def test_actual_enabled_dead_worker_is_immediate_failure(self):
        self.queues[2].is_alive=False
        sample=self.held_sample()
        self.assertIn('DDL-QUEUE is down',assess(sample,{},sample['time'])['errors'])

    def test_disabled_dead_auto_snatcher_is_not_a_failure(self):
        self.queues[-1].is_alive=False
        sample=self.held_sample()
        self.assertNotIn('AUTO-SNATCHER',sample['busy_workers']['enabled'])
        self.assertFalse(assess(sample,{},sample['time'])['errors'])

    def test_repeat_busy_does_not_reset_deadline_or_progress_clocks(self):
        import copy
        sample=self.held_sample();start=sample['time']
        previous={'POST-PROCESS-QUEUE':dict(token=[1,0],size=0,since=start-50,waiting=False)}
        saved=copy.deepcopy(previous)
        first=assess(sample,previous,start)
        self.assertEqual(previous,saved)
        for offset in (60,899,900,901):
            sample['time']=start+offset
            current=assess(sample,first['observations'],start+offset)
            self.assertEqual(current['observations']['_publication_busy']['since'],start)
            self.assertEqual(current['observations']['POST-PROCESS-QUEUE'],saved['POST-PROCESS-QUEUE'])
            self.assertEqual(bool(current['errors']),offset>=900)
            first=current

    def test_already_stalled_progress_remains_unhealthy_during_busy_grace(self):
        sample=self.held_sample();now=sample['time']
        previous={'DDL-QUEUE':dict(token=[1,0],size=0,since=now-900,waiting=True)}
        result=assess(sample,previous,now)
        self.assertTrue(result['errors'])
        self.assertEqual(result['observations']['DDL-QUEUE'],previous['DDL-QUEUE'])

    def test_ready_revalidates_and_preserves_old_stall_clock_then_resets_busy_clock(self):
        from unittest.mock import patch
        sample=self.held_sample();start=sample['time']
        old={'POST-PROCESS-QUEUE':dict(token=[1,0],size=1,since=start-900)}
        busy=assess(sample,old,start)
        def ready():
            self.assertTrue(self.f.native.active());return self.full
        with patch.object(self.worker,'_snapshot',side_effect=ready):
            self.full['processing']=True
            self.full['queues']['POST-PROCESS-QUEUE']['size']=1
            current=self.worker.snapshot()
        result=assess(current,busy['observations'],start+1)
        self.assertIn('POST-PROCESS-QUEUE has made no progress for 15 minutes',result['errors'])
        self.assertNotIn('_publication_busy',result['observations'])
        sample['time']=start+1000
        new=assess(sample,result['observations'],start+1000)
        self.assertEqual(new['observations']['_publication_busy']['since'],start+1000)

    def test_persistent_and_unknown_publication_holds_never_gain_grace(self):
        sample=self.held_sample()
        for reason in ('media-pending','authority-unavailable','startup-restart-required','unknown'):
            sample['publication']['reason']=reason
            self.assertTrue(assess(sample,{},sample['time'])['errors'])

    def test_missing_and_malformed_busy_packets_are_not_healthy(self):
        import copy
        sample=self.held_sample()
        variants=[]
        for key,value in (('version',True),('startup_complete',False),('enabled',[]),('enabled',['SEARCH-QUEUE']*2),('queues',{})):
            changed=copy.deepcopy(sample);changed['busy_workers'][key]=value;variants.append(changed)
        for row in ({'alive':1,'size':0},{'alive':True,'size':True},{'alive':True,'size':-1},{'alive':True,'size':2**63}):
            changed=copy.deepcopy(sample);changed['busy_workers']['queues']['SEARCH-QUEUE']=row;variants.append(changed)
        missing=copy.deepcopy(sample);missing.pop('busy_workers');variants.append(missing)
        for changed in variants:self.assertTrue(assess(changed,{},changed['time'])['errors'])

    def test_stale_future_and_nonfinite_busy_samples_refuse(self):
        import copy
        sample=self.held_sample();now=sample['time']
        for stamp in (now-31,now+31,float('nan'),float('inf'),True):
            changed=copy.deepcopy(sample);changed['time']=stamp
            self.assertTrue(assess(changed,{},now)['errors'])

    def test_current_config_change_during_queue_read_refuses_telemetry(self):
        from unittest.mock import patch
        def changed():
            self.f.mylar.CONFIG.ENABLE_DDL=False
            return self.queues
        with patch.object(sys.modules['mylar.queues'],'queue_info',side_effect=changed):
            sample=self.held_sample()
        self.assertNotIn('busy_workers',sample)
        self.assertTrue(assess(sample,{},sample['time'])['errors'])

    def test_startup_fact_change_during_queue_read_refuses_telemetry(self):
        from unittest.mock import patch
        def changed():
            self.f.native._STARTUP_COMPLETE=False
            return self.queues
        with patch.object(sys.modules['mylar.queues'],'queue_info',side_effect=changed):
            sample=self.held_sample()
        self.assertNotIn('busy_workers',sample)


    def test_busy_preserves_original_provider_cooldown_expiry(self):
        import copy
        sample=self.held_sample();now=sample['time']
        previous={'DDL-QUEUE':dict(token=[1,0],size=0,since=now-200,waiting=True,cooldown_deadline=now-120)}
        saved=copy.deepcopy(previous)
        self.assertTrue(assess(sample,previous,now)['errors'])
        self.assertEqual(previous,saved)
        previous['DDL-QUEUE']['cooldown_deadline']=now-119
        self.assertFalse(assess(sample,previous,now)['errors'])
        sample['time']=now+1
        result=assess(sample,previous,now+1)
        self.assertTrue(result['errors'])
        self.assertEqual(result['observations']['DDL-QUEUE'],previous['DDL-QUEUE'])

    def test_intervening_publication_hold_cannot_reset_busy_or_progress_clock(self):
        import copy
        sample=self.held_sample();now=sample['time']
        previous={'DDL-QUEUE':dict(token=[1,0],size=0,since=now-30,waiting=False)}
        first=assess(sample,previous,now)
        saved=copy.deepcopy(first['observations'])
        held=copy.deepcopy(sample);held['publication']['reason']='media-pending'
        result=assess(held,first['observations'],now+895)
        self.assertTrue(result['errors'])
        self.assertEqual(result['observations'],saved)
        self.assertIsNot(result['observations'],first['observations'])
        sample['time']=now+901
        result=assess(sample,result['observations'],now+901)
        self.assertTrue(result['errors'])
        self.assertEqual(result['observations'],saved)


if __name__ == '__main__':
    unittest.main()
