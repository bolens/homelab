"""Worker liveness, progress, idle, and image patch contract regression tests."""
import ast
from pathlib import Path
import sys
import unittest

from health import assess
from patch_diagnostics_api import patched_source

SOURCE = Path(sys.argv.pop(1)) if len(sys.argv) > 1 else None

# Exact public queue_info() export from the selected upstream package.
UPSTREAM_QUEUE_INFO_SOURCE = '"""Queue info helpers."""\n\nfrom collections import namedtuple\n\nimport mylar\n\nQueueInfo = namedtuple("QueueInfo", ("name", "is_alive", "size"))\n\n\ndef queue_info():\n    yield from (\n        QueueInfo(queue_name, thread_obj.is_alive() if thread_obj is not None else None, queue.qsize())\n        for (queue_name, thread_obj, queue) in [\n            ("AUTO-COMPLETE-NZB", mylar.NZBPOOL, mylar.NZB_QUEUE),\n            ("AUTO-SNATCHER", mylar.SNPOOL, mylar.SNATCHED_QUEUE),\n            ("DDL-QUEUE", mylar.DDLPOOL, mylar.DDL_QUEUE),\n            ("JD2-QUEUE", mylar.JD2POOL, mylar.JD2_QUEUE),\n            ("POST-PROCESS-QUEUE", mylar.PPPOOL, mylar.PP_QUEUE),\n            ("SEARCH-QUEUE", mylar.SEARCHPOOL, mylar.SEARCH_QUEUE),\n        ]\n    )\n\n'


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



    def actual_six_queue_module(self):
        import queue
        import threading
        from types import ModuleType
        pairs=(('NZBPOOL','NZB_QUEUE'),('SNPOOL','SNATCHED_QUEUE'),('DDLPOOL','DDL_QUEUE'),
               ('JD2POOL','JD2_QUEUE'),('PPPOOL','PP_QUEUE'),('SEARCHPOOL','SEARCH_QUEUE'))
        for pool, pending in pairs:
            setattr(self.f.mylar,pool,None if pool=='JD2POOL' else threading.current_thread())
            setattr(self.f.mylar,pending,queue.Queue())
        self.f.mylar.SEARCH_QUEUE.put('fixture-only')
        module=ModuleType('mylar.queues')
        exec(compile(UPSTREAM_QUEUE_INFO_SOURCE,'actual-public-upstream-queue-info','exec'),module.__dict__)
        return module

    def test_actual_six_queue_contract_keeps_five_monitored_workers(self):
        from unittest.mock import patch
        module=self.actual_six_queue_module()
        self.assertEqual([q.name for q in module.queue_info()],['AUTO-COMPLETE-NZB','AUTO-SNATCHER','DDL-QUEUE','JD2-QUEUE','POST-PROCESS-QUEUE','SEARCH-QUEUE'])
        with patch.dict(sys.modules,{'mylar.queues':module}):sample=self.held_sample()
        self.assertEqual(set(sample['busy_workers']['queues']),{'AUTO-COMPLETE-NZB','AUTO-SNATCHER','DDL-QUEUE','POST-PROCESS-QUEUE','SEARCH-QUEUE'})
        self.assertNotIn('JD2-QUEUE',sample['busy_workers']['enabled'])
        self.assertEqual(sample['busy_workers']['queues']['SEARCH-QUEUE']['size'],1)
        self.assertEqual(sample['publication'],dict(version=1,state='held',reason='writer-busy',census=None))
        self.assertFalse(assess(sample,{},sample['time'])['errors'])
        self.f.mylar.DDLPOOL=None
        with patch.dict(sys.modules,{'mylar.queues':module}):dead=self.held_sample()
        self.assertIn('DDL-QUEUE is down',assess(dead,{},dead['time'])['errors'])

    def test_actual_six_queue_contract_still_refuses_bad_observed_rows(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        module=self.actual_six_queue_module()
        original=list(module.queue_info());jd2=next(q for q in original if q.name=='JD2-QUEUE')
        cases=[original+[jd2],original+[module.QueueInfo('UNKNOWN-QUEUE',True,0)]]
        for size in (True,-1,2**63):
            cases.append([module.QueueInfo(q.name,q.is_alive,size) if q.name=='JD2-QUEUE' else q for q in original])
        for rows in cases:
            with self.subTest(rows=rows),patch.dict(sys.modules,{'mylar.queues':SimpleNamespace(queue_info=lambda:rows)}):
                sample=self.held_sample()
                self.assertNotIn('busy_workers',sample)
                self.assertTrue(assess(sample,{},sample['time'])['errors'])



class IntakeWorkHealthTest(unittest.TestCase):
    def sample(self, **work):
        packet=dict(version=1,queued=0,active=0,manual_active=0,oldest_manual_seconds=0,
                    recent_finished=1,observer_errors=0)
        packet.update(work)
        return dict(enabled=['POST-PROCESS-QUEUE'],
                    queues={'POST-PROCESS-QUEUE':dict(alive=True,size=packet['queued'])},
                    downloaded=12,completed=9,processing=False,ddl_active=[],pp_work=packet)

    def test_retained_inventory_is_review_advisory_not_accepted_queue_work(self):
        value=self.sample()
        initial=assess(value,{},0)
        result=assess(value,initial['observations'],10000)
        self.assertEqual(result['errors'],[])
        self.assertFalse(result['observations']['POST-PROCESS-QUEUE']['waiting'])
        self.assertEqual(result['intake_review'],dict(completed_files=9,classification='unresolved-check-folder-inputs'))
        self.assertEqual(result['observations']['POST-PROCESS-QUEUE']['token'],[12,-9])

    def test_repeated_scan_completions_cannot_hide_real_queued_or_active_stall(self):
        for work in ({'queued':2},{'active':1}):
            value=self.sample(**work)
            old=assess(value,{},0)['observations']
            value['pp_work']['recent_finished']=50
            self.assertIn('POST-PROCESS-QUEUE has made no progress for 15 minutes',assess(value,old,900)['errors'])

    def test_manual_scan_has_its_own_real_invocation_duration_limit(self):
        value=self.sample(active=1,manual_active=1,oldest_manual_seconds=899)
        value['processing']=True
        old=assess(value,{},0)['observations']
        self.assertEqual(assess(value,old,10000)['errors'],[])
        value['pp_work']['oldest_manual_seconds']=900
        self.assertIn('Folder monitor scan has not completed for 15 minutes',assess(value,old,10001)['errors'])

    def test_unknown_or_changed_observation_preserves_conservative_inventory_stall(self):
        for edit in (None,{'observer_errors':1},{'queued':True},{'manual_active':1},
                     {'oldest_manual_seconds':1},{'recent_finished':51},{'extra':0}):
            value=self.sample()
            if edit is None:value.pop('pp_work')
            else:value['pp_work'].update(edit)
            old=assess(value,{},0)['observations']
            with self.subTest(edit=edit):
                self.assertIn('POST-PROCESS-QUEUE has made no progress for 15 minutes',assess(value,old,900)['errors'])
        value=self.sample(queued=1);value['queues']['POST-PROCESS-QUEUE']['size']=0
        old=assess(value,{},0)['observations']
        self.assertTrue(assess(value,old,900)['errors'])

    def test_unobserved_processing_lock_remains_real_pending_work(self):
        value=self.sample();value['processing']=True
        old=assess(value,{},0)['observations']
        self.assertTrue(assess(value,old,900)['errors'])

    def test_busy_writer_never_uses_new_telemetry_to_reset_old_clock(self):
        value=self.sample(queued=1);old=assess(value,{},0)['observations']
        busy=dict(publication=dict(version=1,state='held',reason='writer-busy',census=None),time=900,
                  busy_workers=dict(version=1,startup_complete=True,enabled=['SEARCH-QUEUE','POST-PROCESS-QUEUE'],
                                    queues={n:dict(alive=True,size=0) for n in ('SEARCH-QUEUE','POST-PROCESS-QUEUE')}),
                  pp_work=self.sample()['pp_work'])
        result=assess(busy,old,900)
        self.assertEqual(result['observations']['POST-PROCESS-QUEUE'],old['POST-PROCESS-QUEUE'])
        self.assertIn('POST-PROCESS-QUEUE progress is overdue and cannot be verified while the Writer is busy',result['errors'])

if __name__ == '__main__':
    unittest.main()
