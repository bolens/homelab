"""Workflow ownership, admission, security and native integration regressions."""
import ast
import os
import importlib
import json
from pathlib import Path
from queue import Queue
import sqlite3
import sys
import tempfile
import threading
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

# Exercise the actual modules as Mylar imports them, with disposable application state.
app=ModuleType('mylar');app.__path__=[str(Path(__file__).parent)]
sys.modules['mylar']=app
workflow=importlib.import_module('mylar.workflow')
web=importlib.import_module('mylar.workflow_web')
control=importlib.import_module('mylar.queue_control')
Store=importlib.import_module('mylar.workflow_store').Store

class DB:
    def __init__(self,connection):self.conn=connection
    def select(self,q,args=()):return self.conn.execute(q,args).fetchall()
    def selectone(self,q,args=()):return self.conn.execute(q,args)
    def action(self,q,args=()):
        result=self.conn.execute(q,args);self.conn.commit();return result
    def upsert(self,table,values,where):
        self.conn.execute('UPDATE '+table+' SET '+','.join(k+'=?' for k in values)+' WHERE '+' AND '.join(k+'=?' for k in where),list(values.values())+list(where.values()));self.conn.commit()

class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.conn=sqlite3.connect(':memory:',check_same_thread=False);self.conn.row_factory=sqlite3.Row;self.addCleanup(self.conn.close)
        self.conn.executescript("""
            CREATE TABLE issues(IssueID TEXT,ComicID TEXT,ComicName TEXT,Status TEXT,Location TEXT);
            INSERT INTO issues VALUES ('10','20','Example','Snatched',NULL);
            CREATE TABLE ddl_info(ID TEXT,issueid TEXT,comicid TEXT,series TEXT,pack TEXT,status TEXT,site TEXT,updated_date TEXT,link_type TEXT,mainlink TEXT);
            INSERT INTO ddl_info VALUES ('1','10','20','Example #1','0','Queued','DDL(GetComics)','2026-01-01 00:00','GC-Main','https://example.com/release');
            CREATE TABLE nzblog(IssueID TEXT,PROVIDER TEXT);
            CREATE TABLE annuals(IssueID TEXT,ComicID TEXT,ComicName TEXT,Status TEXT,Location TEXT,Deleted INT);
            CREATE TABLE comics(ComicID TEXT,ComicLocation TEXT);
        """)
        self.conn.execute('INSERT INTO comics VALUES (?,?)',('20',self.tmp.name))
        app.DATA_DIR=self.tmp.name;app.db=SimpleNamespace(DBConnection=lambda:DB(self.conn))
        app.CONFIG=SimpleNamespace(DESTINATION_DIR=self.tmp.name,CACHE_DIR=self.tmp.name,DDL_LOCATION=self.tmp.name,ENABLE_CHECK_FOLDER=False)
        app.PP_QUEUE=Queue();app.NZB_QUEUE=Queue();app.RETURN_THE_NZBQUEUE=Queue();app.SEARCH_QUEUE=Queue();app.DDL_QUEUE=Queue();app.APILOCK=False
        app.DDL_QUEUED=[];app.PACK_ISSUEIDS_DONT_QUEUE={};app.USE_NZBGET=True;app.USE_SABNZBD=False
        app.search=SimpleNamespace(provider_order=lambda:{'prov_order':['DDL(GetComics)','newznab: fixture']},searchforissue=Mock())
        workflow._STORE=Store(self.tmp.name);workflow._CONTEXT=threading.local();workflow._STARTED=False;workflow._LAST_TICK=0
        workflow._OBSERVER_ERRORS=0;control._STORE=control.Store(self.tmp.name)
        self.recover=patch.object(control,'recover',Mock());self.recover.start();self.addCleanup(self.recover.stop)
        self.disk=patch.object(workflow.shutil,'disk_usage',return_value=SimpleNamespace(free=20*1024**3));self.disk.start();self.addCleanup(self.disk.stop)
    def handoff(self):return workflow.request_handoff('1')
    def status(self):return self.conn.execute('SELECT status FROM ddl_info WHERE id="1"').fetchone()[0]
    def exhaust(self):
        self.conn.execute("UPDATE ddl_info SET status='Failed'")
        control.stop_retry({'id':'1','issueid':'10','mainlink':'https://example.com/release'}, {'links_exhausted':['GC-Main']})

    def cycle(self):
        workflow._LAST_TICK=0
        workflow.tick(app.SEARCH_QUEUE)
        self.assertEqual(workflow._OBSERVER_ERRORS,0)

    def test_exhausted_fallback_is_nzb_only_and_no_result_stays_failed(self):
        self.exhaust();self.assertFalse(workflow.policy()['auto_handoff'])
        self.cycle();self.assertEqual(self.status(),'NZB handoff')
        def search(iid,manual):
            self.assertTrue(workflow.in_handoff(iid));self.assertFalse(manual)
            self.assertEqual(workflow.provider_order(['DDL(GetComics)','newznab: fixture','torrent'],['newznab: fixture']),['newznab: fixture'])
        app.search.searchforissue=Mock(side_effect=search)
        workflow.queue_item(app.SEARCH_QUEUE.get_nowait(),app.SEARCH_QUEUE)
        self.assertEqual(self.status(),'Failed');control.recover.assert_not_called()
        workflow._STORE=Store(self.tmp.name);workflow._STARTED=False
        self.cycle();self.cycle()
        self.assertTrue(app.SEARCH_QUEUE.empty());app.search.searchforissue.assert_called_once()
        self.assertEqual(workflow.store().get('handoff','10')['phase'],'no-result')

    def test_exhausted_fallback_excludes_other_failures_and_stale_receipts(self):
        self.exhaust()
        record=control.store().data['items']['1']
        for values in ({'retry_stopped':'lookup_failed'},{'retry_stopped':'layout_changed'},
                       {'retry_stopped':None},{'attempts':control.ATTEMPT_LIMIT}, {'release':'stale'}):
            with self.subTest(values=values):
                original=dict(record);record.update(values)
                self.cycle();self.assertTrue(app.SEARCH_QUEUE.empty());self.assertEqual(self.status(),'Failed')
                record.clear();record.update(original)

    def test_exhausted_fallback_waits_for_config_intake_and_cleanup(self):
        self.exhaust()
        app.USE_NZBGET=False;self.cycle();self.assertTrue(app.SEARCH_QUEUE.empty())
        app.USE_NZBGET=True
        with patch.object(app.search,'provider_order',return_value={'prov_order':['DDL(GetComics)']}):
            self.cycle();self.assertTrue(app.SEARCH_QUEUE.empty())
        with patch.object(workflow,'intake',return_value={'paused':True}):
            self.cycle();self.assertTrue(app.SEARCH_QUEUE.empty())
        app.DDL_QUEUED=['1'];self.cycle();self.assertTrue(app.SEARCH_QUEUE.empty())
        app.DDL_QUEUED=[];self.cycle();self.assertEqual(app.SEARCH_QUEUE.qsize(),1)

    def test_exhausted_fallback_reuses_pack_import_and_duplicate_guards(self):
        self.exhaust()
        for statement,restore in (("UPDATE ddl_info SET pack='1'","UPDATE ddl_info SET pack='0'"),
                                  ("UPDATE issues SET Status='Downloaded'","UPDATE issues SET Status='Snatched'"),
                                  ("INSERT INTO nzblog VALUES ('10','newznab: fixture')","DELETE FROM nzblog")):
            self.conn.execute(statement);self.cycle();self.assertTrue(app.SEARCH_QUEUE.empty())
            self.conn.execute(restore)
        workflow.store().set('dispatch','10',{'issueid':'10','phase':'review'})
        self.cycle();self.assertTrue(app.SEARCH_QUEUE.empty())

    def test_exhausted_fallback_restart_repairs_reservation_publication_gap(self):
        self.exhaust();self.cycle()
        app.SEARCH_QUEUE.get_nowait()
        self.conn.execute("UPDATE ddl_info SET status='Failed'")
        workflow.store().delete('exhaustion_attempt','1')
        workflow._STORE=Store(self.tmp.name);workflow._STARTED=False
        self.cycle();self.assertEqual(self.status(),'NZB handoff')
        self.assertEqual(app.SEARCH_QUEUE.qsize(),1)
        self.assertIsNotNone(workflow.store().get('exhaustion_attempt','1'))

    def test_exhausted_fallback_restart_does_not_replay_interrupted_search(self):
        for native_status,phase in (('Failed','no-result'),('NZB handoff','review')):
            with self.subTest(native_status=native_status):
                self.exhaust();self.cycle()
                app.SEARCH_QUEUE.get_nowait()
                row=workflow.reservation('10')
                workflow.set_handoff(row,'searching','Searching enabled NZB indexers')
                self.conn.execute('UPDATE ddl_info SET status=?',(native_status,))
                workflow._STORE=Store(self.tmp.name);workflow._STARTED=False
                self.cycle();self.cycle()
                self.assertTrue(app.SEARCH_QUEUE.empty())
                app.search.searchforissue.assert_not_called()
                self.assertEqual(workflow.store().get('handoff','10')['phase'],phase)
                self.assertEqual(self.status(),native_status)
                workflow.store().delete('handoff','10');workflow.store().delete('exhaustion_attempt','1')

    def test_exhausted_fallback_revalidates_release_before_search(self):
        self.exhaust();self.cycle()
        self.conn.execute("UPDATE ddl_info SET mainlink='https://example.com/changed'")
        workflow.queue_item(app.SEARCH_QUEUE.get_nowait(),app.SEARCH_QUEUE)
        app.search.searchforissue.assert_not_called()
        self.assertEqual(workflow.reservation('10')['phase'],'review')

    def test_exhausted_fallback_still_allows_explicit_ddl_restore(self):
        self.exhaust();self.cycle()
        row=workflow.reservation('10')
        workflow.set_handoff(row,'review','Uncertain response')
        web.resolve_handoff('10','restore','checked')
        self.assertEqual(self.status(),'Queued')
        control.recover.assert_called_once()

    def test_exhausted_fallback_acceptance_and_uncertainty_stay_held(self):
        for response,phase in (({'status':True},'accepted'),({'status':False},'review')):
            with self.subTest(phase=phase):
                self.exhaust();self.cycle()
                send=Mock(return_value=response)
                app.search.searchforissue=lambda iid,manual:workflow.sender(send,iid)
                item=app.SEARCH_QUEUE.get_nowait()
                workflow.queue_item(item,app.SEARCH_QUEUE)
                workflow._STORE=Store(self.tmp.name);workflow._STARTED=False
                self.cycle();workflow.queue_item(item,app.SEARCH_QUEUE)
                send.assert_called_once();self.assertEqual(workflow.reservation('10')['phase'],phase)
                self.assertEqual(self.status(),'NZB handoff')
                workflow.store().delete('handoff','10');workflow.store().delete('exhaustion_attempt','1')
    def test_download_type_and_sort_are_independent_and_legacy_policy_survives(self):
        workflow.store().set('policy','current',{'ddl_order':'packs','ddl_paused':True})
        rules=workflow.policy()
        self.assertEqual((rules['ddl_kind'],rules['ddl_order']),('packs','fifo'))
        workflow.set_policy({'ddl_order':'release_newest'})
        self.assertEqual(workflow.policy()['ddl_kind'],'packs')
        workflow.set_policy({'ddl_kind':'alternate'})
        self.assertEqual(workflow.policy()['ddl_order'],'release_newest')
        self.assertTrue(workflow.policy()['ddl_paused'])
        with self.assertRaises(ValueError):workflow.set_policy({'ddl_kind':'invalid'})
    def test_concurrent_partial_policy_updates_preserve_both_changes(self):
        store=workflow.store();original=store.get
        first_read=threading.Event();release=threading.Event();second_done=threading.Event()
        errors=[]
        def get(kind,key,default=None):
            value=original(kind,key,default)
            if kind=='policy' and threading.current_thread().name=='first-save':
                first_read.set();release.wait(2)
            return value
        def save(values,done=None):
            try:workflow.set_policy(values)
            except Exception as error:errors.append(error)
            finally:
                if done:done.set()
        with patch.object(store,'get',side_effect=get):
            first=threading.Thread(target=save,args=({'ddl_paused':True},),name='first-save')
            second=threading.Thread(target=save,args=({'pack_automation':True},second_done))
            first.start();self.assertTrue(first_read.wait(1));second.start()
            second_done.wait(.1);release.set();first.join(2);second.join(2)
        self.assertFalse(errors);self.assertFalse(first.is_alive() or second.is_alive())
        self.assertTrue(workflow.policy()['ddl_paused']);self.assertTrue(workflow.policy()['pack_automation'])

    def test_policy_change_invalidates_cached_intake_without_losing_hysteresis(self):
        workflow.store().set('intake','current',{'paused':True,'checked_at':123})
        web.action('policy',{'values':json.dumps({'queue_high':60})})
        cached=workflow.store().get('intake','current')
        self.assertTrue(cached['paused']);self.assertEqual(cached['checked_at'],0)

    def test_split_single_handoff_keeps_exact_download_identity(self):
        self.conn.execute("UPDATE ddl_info SET id='1-1' WHERE id='1'");self.conn.commit()
        row=workflow.request_handoff('1-1')
        self.assertEqual(row['ddl_id'],'1-1')
        self.assertEqual(self.conn.execute("SELECT status FROM ddl_info WHERE id='1-1'").fetchone()[0],'NZB handoff')
        self.assertEqual(app.SEARCH_QUEUE.qsize(),1)
        self.assertEqual(workflow.request_handoff('1-1'),row)
        self.assertEqual(app.SEARCH_QUEUE.qsize(),1)

    def test_archived_issue_cannot_be_handed_off_or_retried(self):
        self.conn.execute("UPDATE issues SET Status='Archived'")
        with self.assertRaises(ValueError):self.handoff()
        workflow.store().set('dispatch','10',{'issueid':'10','phase':'review'})
        with self.assertRaises(ValueError):web.resolve_dispatch('10','retry','checked')
        self.assertEqual(self.conn.execute('SELECT Status FROM issues').fetchone()[0],'Archived')

    def test_annual_deferred_search_retains_parent_and_excludes_deleted(self):
        self.conn.execute("INSERT INTO annuals VALUES ('11','20','Example Annual','Wanted',NULL,0)")
        workflow.defer_search('11')
        self.assertEqual(workflow.store().get('deferred','11')['comicid'],'20')
        self.conn.execute("UPDATE annuals SET Deleted=1")
        workflow.store().delete('deferred','11')
        workflow.defer_search('11')
        self.assertIsNone(workflow.store().get('deferred','11'))

    def test_restoring_handoff_preserves_another_active_transfer(self):
        self.recover.stop()
        for column in ('link','year','size','filename','remote_filesize'):
            self.conn.execute('ALTER TABLE ddl_info ADD COLUMN '+column+' TEXT')
        self.conn.execute("UPDATE ddl_info SET status='NZB handoff' WHERE id='1'")
        self.conn.execute("INSERT INTO ddl_info(id,issueid,comicid,series,pack,status,site,updated_date,link_type) "
                          "VALUES ('active','12','20','Another comic','0','Downloading','DDL(GetComics)','2026-01-01','GC-Main')")
        app.DDL_QUEUED=['active']
        row={'id':'handoff-token','ddl_id':'1','issueid':'10','comicid':'20','name':'Example','phase':'searching'}
        workflow.store().set('handoff','10',row)
        workflow.restore_ddl(row)
        workflow.restore_ddl(row)
        self.assertEqual(self.status(),'Queued')
        self.assertEqual(self.conn.execute("SELECT status FROM ddl_info WHERE id='active'").fetchone()[0],'Downloading')
        self.assertEqual(app.DDL_QUEUED,['active'])
        self.assertEqual([item['id'] for item in app.DDL_QUEUE.queue],['1'])
        self.assertFalse(workflow.reservation('10'))
        available=[]
        def probe():
            for lock in (control._LOCK,workflow.LOCK):
                acquired=lock.acquire(timeout=1)
                available.append(acquired)
                if acquired:lock.release()
        thread=threading.Thread(target=probe);thread.start();thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(available,[True,True])

    def test_guided_final_admission_rechecks_archived_and_deleted_intent(self):
        proposal=self.proposal()
        command=web.confirm_import(proposal['source_token'],proposal['version'],'10')
        self.conn.execute("UPDATE issues SET Status='Archived'")
        with self.assertRaises(ValueError):web.acknowledge(command['id'],'claimed')
        self.conn.execute("UPDATE issues SET Status='Wanted'")
        web.acknowledge(command['id'],'claimed')
        self.conn.execute("INSERT INTO annuals VALUES ('10','20','Deleted Annual','Wanted',NULL,1)")
        with self.assertRaises(ValueError):
            workflow.processing_put(app.PP_QUEUE,{'issueid':'10','comicid':'20'},command['id'])
        self.assertTrue(app.PP_QUEUE.empty())
        self.assertFalse(workflow.store().get('command',command['id']).get('dispatched'))

    def test_guided_annual_claim_confirm_and_release_preserve_identity(self):
        proposal=self.proposal()
        self.conn.execute("INSERT INTO annuals VALUES ('11','20','Example Annual','Wanted',NULL,0)")
        proposal['candidates'][0].update(issueid='11',title='Example Annual')
        web.report_guidance(json.dumps([proposal]))
        command=web.confirm_import(proposal['source_token'],proposal['version'],'11')
        web.acknowledge(command['id'],'claimed')
        web.acknowledge(command['id'],'review')
        self.assertEqual(web.resolve_import(command['id'],'checked')['phase'],'rejected')
        self.conn.execute("UPDATE annuals SET Deleted=1")
        self.conn.execute("INSERT INTO issues VALUES ('11','20','Shadow','Wanted',NULL)")
        with self.assertRaises(ValueError):web.confirm_import(proposal['source_token'],proposal['version'],'11')

    def test_library_confirmation_requires_file_and_includes_annuals(self):
        self.conn.execute("UPDATE issues SET Status='Downloaded',Location='missing.cbz'")
        self.conn.execute("INSERT INTO annuals VALUES ('11','20','Example Annual','Archived','annual.cbz',0)")
        for iid in ('10','11'):
            workflow.store().set('dispatch',iid,{'issueid':iid,'phase':'accepted'})
        (Path(self.tmp.name)/'annual.cbz').write_bytes(b'archive')
        workflow.tick(app.SEARCH_QUEUE)
        self.assertEqual(workflow.store().get('dispatch','10')['phase'],'accepted')
        self.assertEqual(workflow.store().get('dispatch','11')['phase'],'completed')
        self.assertEqual(workflow._OBSERVER_ERRORS,0)

    def test_download_next_preserves_native_worker_scheduler(self):
        native = Mock()
        with patch.object(app, 'queue_schedule', native, create=True):
            result = web.action('ddl_next', {'ddl_id': '1'})
            self.assertEqual(result, {'next': '1'})
            self.assertEqual(workflow.store().get('meta', 'ddl_next'), '1')
            self.assertIs(app.queue_schedule, native)
            native.assert_not_called()
    def test_duplicate_handoff_has_one_reservation_and_one_queue_entry(self):
        first=self.handoff();second=self.handoff()
        self.assertEqual(first,second);self.assertEqual(app.SEARCH_QUEUE.qsize(),1)
        self.assertEqual(self.status(),'NZB handoff');self.assertEqual(self.conn.execute('SELECT Status FROM issues').fetchone()[0],'Snatched')
    def test_active_pack_downloaded_and_other_work_reject(self):
        for table,column,value in [('ddl_info','status','Downloading'),('ddl_info','pack','1'),('issues','Status','Downloaded')]:
            old=self.conn.execute('SELECT '+column+' FROM '+table).fetchone()[0]
            self.conn.execute('UPDATE '+table+' SET '+column+'=?',(value,))
            with self.assertRaises(ValueError):self.handoff()
            self.conn.execute('UPDATE '+table+' SET '+column+'=?',(old,))
        app.PP_QUEUE.put({'issueid':'10'})
        with self.assertRaises(ValueError):self.handoff()
    def test_nzb_scope_and_no_result_restore_without_touching_settings(self):
        self.handoff()
        def search(iid,manual):
            self.assertFalse(manual)
            self.assertTrue(workflow.in_handoff(iid))
            self.assertEqual(workflow.provider_order(['DDL(GetComics)','newznab: fixture'],['newznab: fixture']),['newznab: fixture'])
        app.search.searchforissue=search
        workflow.queue_item(app.SEARCH_QUEUE.get(),app.SEARCH_QUEUE)
        self.assertEqual(self.status(),'Queued');self.assertFalse(workflow.reservation('10'));control.recover.assert_called_once()
        self.assertFalse(workflow.in_handoff())
    def test_accepted_send_and_timeout_are_not_repeated(self):
        self.handoff();sender=Mock(return_value={'status':True})
        app.search.searchforissue=lambda iid,manual:workflow.sender(sender,iid)
        item=app.SEARCH_QUEUE.get();workflow.queue_item(item,app.SEARCH_QUEUE);workflow.queue_item(item,app.SEARCH_QUEUE)
        sender.assert_called_once();self.assertEqual(workflow.reservation('10')['phase'],'accepted')
        self.assertEqual(self.status(),'NZB handoff')
    def test_unknown_send_survives_restart_and_blocks_requeue(self):
        row=self.handoff();workflow.set_handoff(row,'dispatching','Sending')
        workflow.tick(app.SEARCH_QUEUE)
        self.assertEqual(workflow.reservation('10')['phase'],'review')
        calls=[]
        allowed=workflow.ddl_begin(lambda *a:calls.append(True) or True,{'id':'1','issueid':'10'},app.DDL_QUEUE)
        self.assertFalse(allowed);self.assertFalse(calls)
        self.assertFalse(workflow.send_allowed('10',[{'pack':False,'oneoff':False}]))
    def test_worker_and_handoff_claim_race_has_one_winner(self):
        barrier=threading.Barrier(2);results=[]
        def claim():
            barrier.wait();results.append(('ddl',workflow.ddl_begin(lambda *a:True,{'id':'1','issueid':'10','comicid':'20'},app.DDL_QUEUE)))
        def switch():
            barrier.wait()
            try:self.handoff();results.append(('handoff',True))
            except ValueError:results.append(('handoff',False))
        threads=[threading.Thread(target=f) for f in (claim,switch)]
        for t in threads:t.start()
        for t in threads:t.join(5);self.assertFalse(t.is_alive())
        self.assertEqual(sum(r[1] for r in results),1)
    def test_intake_hysteresis_preserves_deferred_queue(self):
        workflow.set_policy({'queue_high':3,'queue_low':1})
        for _ in range(3):app.PP_QUEUE.put({})
        self.assertTrue(workflow.intake()['paused'])
        item={'issueid':'10','comicid':'20'}
        with patch.object(workflow.time,'sleep'):
            self.assertTrue(workflow.queue_item(item,app.SEARCH_QUEUE))
        self.assertEqual(app.SEARCH_QUEUE.get(),item)
        app.PP_QUEUE.get();workflow.store().delete('intake','current')
        # Preserve the previous paused latch while forcing a fresh sample.
        workflow.store().set('intake','current',{'paused':True,'checked_at':0})
        self.assertTrue(workflow.intake()['paused'])
        app.PP_QUEUE.get();workflow.store().set('intake','current',{'paused':True,'checked_at':0})
        self.assertFalse(workflow.intake()['paused'])
    def test_disk_hysteresis_and_missing_root(self):
        with patch.object(workflow.shutil,'disk_usage',return_value=SimpleNamespace(free=4*1024**3)):
            self.assertTrue(workflow.intake()['paused'])
        workflow.store().set('intake','current',{'paused':True,'checked_at':0})
        with patch.object(workflow.shutil,'disk_usage',return_value=SimpleNamespace(free=7*1024**3)):
            self.assertTrue(workflow.intake()['paused'])
        workflow.store().set('intake','current',{'paused':True,'checked_at':0})
        self.assertFalse(workflow.intake()['paused'])
        app.CONFIG.DESTINATION_DIR=self.tmp.name+'/missing';workflow.store().delete('intake','current')
        self.assertTrue(workflow.intake()['paused']);self.assertFalse(Path(app.CONFIG.DESTINATION_DIR).exists())
    def proposal(self):
        self.conn.execute("UPDATE ddl_info SET status='Completed'")
        row={'source_token':'a'*32,'version':'b'*64,'name':'Alias 1 (2020).cbz','evidence':['filename evidence'],
             'alias_scope':{'series':'alias','year':'2020'},'candidates':[{'issueid':'10','comicid':'20','title':'Example','year':'2020','number':'1','status':'Wanted','agrees':['filename issue'],'conflicts':['filename series']}]}
        web.report_guidance(json.dumps([row]));return row
    def test_guided_confirmation_replay_and_alias_requires_verified_completion(self):
        p=self.proposal();cmd=web.confirm_import(p['source_token'],p['version'],'10',True)
        self.assertEqual(cmd,web.confirm_import(p['source_token'],p['version'],'10',True))
        self.assertEqual(web.commands()['aliases'],[])
        web.acknowledge(cmd['id'],'claimed');web.acknowledge(cmd['id'],'submitted')
        self.assertEqual(web.commands()['aliases'],[])
        web.acknowledge(cmd['id'],'confirmed')
        self.assertEqual(len(web.commands()['aliases']),1)
        web.action('disable_alias',{'alias_id':cmd['id']});web.acknowledge(cmd['id'],'confirmed')
        self.assertEqual(web.commands()['aliases'],[])
    def test_stale_or_conflicting_import_is_rejected(self):
        p=self.proposal()
        with self.assertRaises(ValueError):web.confirm_import(p['source_token'],'c'*64,'10')
        p['candidates'][0]['conflicts'].append('filename issue');web.report_guidance(json.dumps([p]))
        with self.assertRaises(ValueError):web.confirm_import(p['source_token'],p['version'],'10',True)
        with self.assertRaises(ValueError):web.report_guidance(json.dumps([dict(p,name='/private/file')]))
    def test_mutations_require_login_post_and_current_session_token(self):
        class HTTPError(Exception):pass
        cp=SimpleNamespace(request=SimpleNamespace(login=None,method='POST'),session={},HTTPError=HTTPError)
        with patch.dict(sys.modules,{'cherrypy':cp}):
            with self.assertRaises(HTTPError):web.protect('x')
            cp.request.login='fixture';token=web.csrf()
            with self.assertRaises(HTTPError):web.protect('bad')
            cp.request.method='GET'
            with self.assertRaises(HTTPError):web.protect(token)
            cp.request.method='POST';web.protect(token)
            cp.request.login='another'
            with self.assertRaises(HTTPError):web.protect(token)
    def test_settings_validation_and_safe_observer_failure(self):
        with self.assertRaises(ValueError):workflow.set_policy({'queue_high':2,'queue_low':20})
        with self.assertRaises(ValueError):workflow.set_policy({'auto_handoff':'true'})
        with patch.object(workflow,'store',side_effect=OSError('private')):workflow.emit('search','Started')
        self.assertGreater(workflow._OBSERVER_ERRORS,0)
    def test_archive_diagnostics_capability_requires_installed_functions(self):
        diagnostics = importlib.import_module('mylar.publication_archive_diagnostics')
        repair = importlib.import_module('mylar.publication_archive_repair')
        value = workflow.state_health()
        self.assertTrue(value['valid'])
        self.assertEqual(value['archive_diagnostics'], 1)
        self.assertNotIn('archive_repair', value)
        self.assertNotIn('archive_adoption', value)
        for module, name in ((diagnostics, 'diagnose'), (diagnostics, 'public_summary'),
                             (diagnostics, 'display'), (repair, 'classify'),
                             (repair, 'dispatch')):
            with self.subTest(name=name), patch.object(module, name, None):
                self.assertNotIn('archive_diagnostics', workflow.state_health())

    def test_archive_diagnostics_survives_unrelated_optional_import_failure(self):
        import builtins
        original = builtins.__import__
        def imports(name, globals=None, locals=None, fromlist=(), level=0):
            if name == 'mylar' and fromlist and 'combined_publication' in fromlist:
                raise ImportError('optional combined modules absent')
            return original(name, globals, locals, fromlist, level)
        with patch.object(builtins, '__import__', side_effect=imports):
            value = workflow.state_health()
        self.assertTrue(value['valid'])
        self.assertEqual(value['archive_diagnostics'], 1)
        self.assertNotIn('combined_publication', value)
        self.assertNotIn('archive_repair', value)

    def test_healthy_workflow_advertises_native_handoff_version(self):
        value=workflow.state_health()
        self.assertTrue(value['valid'])
        self.assertIs(type(value['publication_handoff']),int)
        self.assertEqual(value['publication_handoff'],1)
        self.assertIs(type(value['guided_handoff']),int)
        self.assertEqual(value['guided_handoff'],1)
        self.assertIs(type(value['maintenance_handoff']),int)
        self.assertEqual(value['maintenance_handoff'],1)
        self.assertIs(type(value['maintenance_reports']),int)
        self.assertEqual(value['maintenance_reports'],1)

    def test_publication_capabilities_require_installed_routes_and_owners(self):
        api = SimpleNamespace(Api=SimpleNamespace())
        combined = SimpleNamespace(execute=lambda _: None)
        conversion = SimpleNamespace(commit=lambda _: None, status=lambda _: None)
        with patch.object(app, 'api', api, create=True), \
                patch.object(app, 'combined_publication', combined, create=True), \
                patch.object(app, 'publication_conversion', conversion, create=True):
            value = workflow.state_health()
            self.assertNotIn('combined_publication', value)
            self.assertNotIn('owned_conversion', value)
            api.Api._combinedPublication = lambda _: None
            api.Api._commitConvertedArchive = lambda _: None
            api.Api._convertedArchiveStatus = lambda _: None
            value = workflow.state_health()
            self.assertEqual(value['combined_publication'], 1)
            self.assertEqual(value['owned_conversion'], 1)
            conversion.status = None
            self.assertNotIn('owned_conversion', workflow.state_health())
            repeat = SimpleNamespace(commit=lambda _: None, status=lambda _: None)
            cleanup = SimpleNamespace(clean=lambda _: None, retired_supplement=lambda _: None, resolve=lambda _: None)
            with patch.object(app, 'publication_reconcile', repeat, create=True), \
                    patch.object(app, 'combined_cleanup', cleanup, create=True):
                self.assertNotIn('retained_repeat', workflow.state_health())
                api.Api._commitRetainedRepeat = lambda _: None
                api.Api._retainedRepeatStatus = lambda _: None
                value = workflow.state_health()
                self.assertEqual(value['retained_repeat'], 1)
                self.assertEqual(value['combined_cleanup'], 1)
                self.assertIs(type(value['combined_cleanup']), int)
                repeat.status = None
                self.assertNotIn('retained_repeat', workflow.state_health())
                cleanup.resolve = None
                self.assertNotIn('combined_cleanup', workflow.state_health())
            derivative = SimpleNamespace(publish=lambda _: None, status=lambda _: None)
            lineage = SimpleNamespace(prepare=lambda _: None)
            metadata = SimpleNamespace(reviewed_derivative=lambda _: None)
            with patch.object(app, 'publication_derivative', derivative, create=True), \
                    patch.object(app, 'publication_lineage', lineage, create=True), \
                    patch.object(app, 'library_metadata', metadata, create=True):
                self.assertNotIn('reviewed_derivative', workflow.state_health())
                api.Api._commitReviewedDerivative = lambda _: None
                api.Api._reviewedDerivativeStatus = lambda _: None
                self.assertEqual(workflow.state_health()['reviewed_derivative'], 1)
                lineage.prepare = None
                self.assertNotIn('reviewed_derivative', workflow.state_health())

    def guided_submission(self):
        proposal=self.proposal();command=web.confirm_import(proposal['source_token'],proposal['version'],'10')
        binding={key:command[key] for key in ('id','source_token','version','issueid','comicid')}
        proof={'token':'a'*64,'source':'/fixture/stage/comic.cbz',
               'owner':{'issueid':'10','parentcomicid':'20','releasecomicid':'20','table':'issues'}}
        native=SimpleNamespace(import_handoff=Mock(return_value=proof),guard=importlib.import_module('mylar.publication_guard'))
        app.publication_native=native;app.CONFIG.API_ENABLED=True;app.CONFIG.API_KEY='fixture'
        client=SimpleNamespace(apikey='fixture',_failureResponse=lambda reason:{'success':False})
        arguments=dict(publication_handoff='fixture',workflow_command=command['id'],guided_handoff=json.dumps(binding))
        item=dict(issueid='10',comicid='20',nzb_folder='/fixture/stage',nzb_name='comic.cbz',download_info=None)
        return command,native,client,arguments,item

    def test_guided_handoff_claims_and_queues_once_without_separate_acknowledgement(self):
        command,native,client,arguments,item=self.guided_submission()
        def submit(client,**kwargs):workflow.processing_put(app.PP_QUEUE,item,kwargs['workflow_command'])
        with patch.dict(sys.modules,{'mylar.publication_native':native}):
            workflow.force_process(submit)(client,**arguments)
            row=workflow.store().get('command',command['id'])
            self.assertEqual(row['phase'],'submitted');self.assertTrue(row['dispatched'])
            self.assertEqual(app.PP_QUEUE.qsize(),1)
            workflow.force_process(submit)(client,**arguments)
        self.assertEqual(app.PP_QUEUE.qsize(),1)
        self.assertEqual(client.data,{'success':False})

    def test_guided_handoff_stale_choice_or_missing_dependency_spends_nothing(self):
        command,native,client,arguments,item=self.guided_submission();submit=Mock()
        for binding in ({},{'id':command['id']},dict(json.loads(arguments['guided_handoff']),version='f'*64)):
            with patch.dict(sys.modules,{'mylar.publication_native':native}):
                workflow.force_process(submit)(client,**dict(arguments,guided_handoff=json.dumps(binding)))
            self.assertEqual(workflow.store().get('command',command['id'])['phase'],'queued')
            self.assertIsNone(workflow.store().get('worker_import_attempt','a'*64))
        submit.assert_not_called();self.assertTrue(app.PP_QUEUE.empty())

    def test_guided_queue_failure_retains_spent_attempt_and_never_replays(self):
        command,native,client,arguments,item=self.guided_submission()
        queue=Mock();queue.put.side_effect=RuntimeError('queue interruption')
        def submit(client,**kwargs):workflow.processing_put(queue,item,kwargs['workflow_command'])
        with patch.dict(sys.modules,{'mylar.publication_native':native}):
            with self.assertRaises(RuntimeError):workflow.force_process(submit)(client,**arguments)
            self.assertIsNotNone(workflow.store().get('worker_import_attempt','a'*64))
            workflow.force_process(submit)(client,**arguments)
        self.assertEqual(queue.put.call_count,1)

    def test_native_queue_handoff_binds_exact_item_and_clears_thread_context(self):
        proof={'token':'a'*64,'source':'/fixture/stage/comic.cbz',
               'owner':{'issueid':'10','parentcomicid':'20','releasecomicid':'20','table':'issues'}}
        app.CONFIG.API_ENABLED=True;app.CONFIG.API_KEY='fixture'
        native=SimpleNamespace(import_handoff=Mock(return_value=proof),guard=importlib.import_module('mylar.publication_guard'))
        app.publication_native=native
        client=SimpleNamespace(apikey='fixture',_failureResponse=lambda reason:{'success':False})
        item=dict(issueid='10',comicid='20',nzb_folder='/fixture/stage',nzb_name='comic.cbz',download_info=None)
        def submit(client,**kwargs):workflow.processing_put(app.PP_QUEUE,item)
        with patch.dict(sys.modules,{'mylar.publication_native':native}):
            workflow.force_process(submit)(client,publication_handoff='fixture')
        queued=app.PP_QUEUE.get_nowait()
        self.assertEqual(queued['download_info'],{'publication_handoff':proof})
        self.assertIsNone(getattr(workflow._CONTEXT,'publication_handoff',None))
        self.assertIsNone(item['download_info'])
        workflow._CONTEXT.publication_handoff=proof
        try:
            for changed in (dict(item,comicid='99'),dict(item,nzb_name='other.cbz'),dict(item,download_info={})):
                with self.assertRaises(ValueError):workflow.processing_put(app.PP_QUEUE,changed)
        finally:workflow._CONTEXT.publication_handoff=None
        self.assertTrue(app.PP_QUEUE.empty())
        workflow.store().set('worker_import_attempt','c'*64,dict(proof,owner=None))
        native.import_handoff.return_value=dict(proof,token='d'*64,owner=dict(proof['owner'],issueid='11'))
        queued=Mock()
        with patch.dict(sys.modules,{'mylar.publication_native':native}):
            workflow.force_process(queued)(client,publication_handoff='fixture')
        queued.assert_not_called()
        self.assertEqual(client.data,{'success':False})
        self.assertIsNone(workflow.store().get('worker_import_attempt','d'*64))

    def test_terminal_history_does_not_hide_pending_owner(self):
        p=self.proposal();cmd=web.confirm_import(p['source_token'],p['version'],'10')
        for n in range(1002):workflow.store().set('command',str(n),{'id':str(n),'phase':'confirmed'})
        self.assertEqual(web.commands()['commands'],[cmd])
        self.assertEqual(web.confirm_import(p['source_token'],p['version'],'10')['id'],cmd['id'])
    def test_guided_owner_blocks_handoff_and_send_and_repeated_processing(self):
        p=self.proposal();cmd=web.confirm_import(p['source_token'],p['version'],'10')
        self.conn.execute("UPDATE ddl_info SET status='Queued'")
        with self.assertRaises(ValueError):self.handoff()
        sender=Mock(return_value={'status':True})
        self.assertFalse(workflow.sender(sender,'10')['status']);sender.assert_not_called()
        self.conn.execute("UPDATE ddl_info SET status='Completed'")
        web.acknowledge(cmd['id'],'claimed')
        workflow.processing_put(app.PP_QUEUE,{'issueid':'10','comicid':'20'},cmd['id'])
        with self.assertRaises(ValueError):workflow.processing_put(app.PP_QUEUE,{'issueid':'10','comicid':'20'},cmd['id'])
        with self.assertRaises(ValueError):workflow.processing_put(app.PP_QUEUE,{},cmd['id'])
        with self.assertRaises(ValueError):workflow.processing_put(app.PP_QUEUE,{'issueid':'10','comicid':'99'},cmd['id'])
        self.assertEqual(app.PP_QUEUE.qsize(),1)
    def test_handoff_owner_blocks_guided_confirmation(self):
        self.handoff();p=self.proposal()
        with self.assertRaises(ValueError):web.confirm_import(p['source_token'],p['version'],'10')
    def test_ordinary_uncertain_send_cannot_repeat_after_restart(self):
        sender=Mock(return_value={'status':False})
        workflow.sender(sender,'10');workflow._STORE=Store(self.tmp.name)
        workflow.sender(sender,'10');sender.assert_called_once()
        self.assertFalse(workflow.send_allowed('10',[]))
        self.assertEqual(workflow.dispatch_owner('10')['phase'],'review')
    def test_pressure_at_actual_send_retains_search(self):
        sender=Mock(return_value={'status':True})
        workflow.set_policy({'queue_high':2,'queue_low':1})
        app.PP_QUEUE.put({});app.PP_QUEUE.put({})
        self.assertFalse(workflow.sender(sender,'10')['status']);sender.assert_not_called()
        self.assertIsNotNone(workflow.store().get('deferred','10'))
        app.PP_QUEUE.get();app.PP_QUEUE.get()
        workflow.store().set('intake','current',{'paused':True,'checked_at':0})
        workflow.tick(app.SEARCH_QUEUE)
        self.assertEqual(app.SEARCH_QUEUE.qsize(),1)
        self.assertEqual(app.SEARCH_QUEUE.get()['comicid'],'20')

    def test_reviewed_import_release_rejects_delayed_token_and_allows_new_choice(self):
        p=self.proposal();cmd=web.confirm_import(p['source_token'],p['version'],'10')
        web.acknowledge(cmd['id'],'claimed');web.acknowledge(cmd['id'],'review')
        with self.assertRaises(ValueError):web.resolve_import(cmd['id'],'')
        app.PP_QUEUE.put({'issueid':'10'})
        with self.assertRaises(ValueError):web.resolve_import(cmd['id'],'checked')
        app.PP_QUEUE.get();web.resolve_import(cmd['id'],'checked')
        with self.assertRaises(ValueError):workflow.processing_put(app.PP_QUEUE,{'issueid':'10','comicid':'20'},cmd['id'])
        new=web.confirm_import(p['source_token'],p['version'],'10')
        self.assertNotEqual(new['id'],cmd['id']);self.assertTrue(new['reviewed_source'])
    def test_existing_archive_transfer_does_not_schedule_replacement(self):
        p=self.proposal();workflow.sender(lambda:{'status':True},'10')
        with self.assertRaises(ValueError):web.confirm_import(p['source_token'],p['version'],'10')
        web.resolve_dispatch('10','import','checked')
        self.assertIsNone(workflow.store().get('deferred','10'))
        self.assertEqual(self.conn.execute('SELECT Status FROM issues').fetchone()[0],'Snatched')
        self.assertEqual(web.confirm_import(p['source_token'],p['version'],'10')['phase'],'queued')
    def test_previous_import_proposal_requires_checked_confirmation(self):
        p=self.proposal();p['requires_review']=True;web.report_guidance(json.dumps([p]))
        with self.assertRaises(ValueError):web.confirm_import(p['source_token'],p['version'],'10')
        cmd=web.confirm_import(p['source_token'],p['version'],'10',confirmation='checked')
        self.assertTrue(cmd['reviewed_source'])

    def test_handoff_completion_retires_original_ddl_status(self):
        row=self.handoff();workflow.set_handoff(row,'source-ready','Existing source')
        self.conn.execute("UPDATE ddl_info SET status='Source review'")
        workflow.tick(app.SEARCH_QUEUE);self.assertEqual(self.status(),'Source review')
        self.conn.execute("UPDATE issues SET Status='Downloaded',Location='Example.cbz'")
        (Path(self.tmp.name)/'Example.cbz').write_bytes(b'comic')
        workflow._LAST_TICK=0;workflow.tick(app.SEARCH_QUEUE)
        self.assertEqual(self.status(),'Completed')
        self.assertEqual(workflow.store().get('handoff','10')['phase'],'completed')

    def test_existing_workflow_api_migrates_typed_acknowledgement_idempotently(self):
        import patch_workflow
        original="""cmd_list = ['getHealth', 'reportImportProblems', 'workflowCommands', 'workflowAcknowledge']
class Api:
    # homelab-workflow-v1
    def _workflowAcknowledge(self, **kwargs):
        try:
            result = workflow_web.acknowledge(kwargs.get('command_id'), kwargs.get('phase'), kwargs.get('reason', ''))
        except ValueError:
            return
"""
        changed=patch_workflow.api(original)
        self.assertEqual(patch_workflow.api(changed),changed)
        self.assertLess(changed.index('worker_handoff.admit'),changed.index('result = workflow_web.acknowledge'))
        self.assertIn("kwargs.get('maintenance_handoff')",changed)

    def test_fresh_workflow_patch_targets_whitelist_with_existing_report_guard(self):
        import patch_workflow
        from patch_queue_views import report_api
        source="""cmd_list = ['getHealth', 'reportImportProblems', 'other']
class Api:
    def _forceProcess(self, **kwargs):
            mylar.PP_QUEUE.put({'nzb_name':    self.nzb_name,
                                'download_info': None})
    def _reportImportProblems(self, **kwargs):
        if self.apikey != mylar.CONFIG.API_KEY:
            return
        try:
            result = import_problems.report(kwargs.get('report'))
        except ValueError:
            return
    def _getHealth(self, **kwargs):
        pass
"""
        guarded=report_api(source)
        self.assertEqual(guarded.count("'reportImportProblems',"),2)
        changed=patch_workflow.api(guarded)
        self.assertEqual(patch_workflow.api(changed),changed)
        self.assertEqual(report_api(changed),changed)
        nodes=ast.parse(changed)
        commands=next(node.value for node in nodes.body if isinstance(node,ast.Assign))
        self.assertEqual(ast.literal_eval(commands),['getHealth','reportImportProblems','workflowCommands','workflowAcknowledge','other'])
        report=next(node for node in ast.walk(nodes) if isinstance(node,ast.FunctionDef) and node.name=='_reportImportProblems')
        body=next(node for node in report.body if isinstance(node,ast.Try)).body
        self.assertEqual(ast.unparse(body[1].value.func),'worker_handoff.admit')
        self.assertLess(changed.index('if self.apikey'),changed.index("'reportImportProblems', {key:"))
        # A report guard must not hide a missing acknowledgement guard on upgrade.
        legacy=changed.replace("            from mylar import worker_handoff\n            worker_handoff.admit(kwargs.get('maintenance_handoff'), 'workflowAcknowledge', {key: kwargs.get(key, '') for key in ('command_id', 'phase', 'reason', 'command_binding')})\n",'')
        self.assertEqual(patch_workflow.api(legacy),changed)

    def test_workflow_whitelist_rejects_ambiguous_or_partial_dispatch(self):
        from patch_workflow import workflow_commands
        for source in ("cmd_list = commands", "cmd_list=['reportImportProblems','reportImportProblems']",
                       "cmd_list=['reportImportProblems','workflowCommands']",
                       "cmd_list=['reportImportProblems']\ncmd_list=['other']",
                       "cmd_list=['other']", "alias=cmd_list=['reportImportProblems']"):
            with self.subTest(source=source),self.assertRaises(ValueError):workflow_commands(source)

    def test_native_patch_is_idempotent_and_preserves_return_contract(self):
        import patch_workflow
        for name,patcher in [('search.py',patch_workflow.search),('queues/search.py',patch_workflow.search_queue),('queues/ddl.py',patch_workflow.ddl),('webserve.py',patch_workflow.server),('api.py',patch_workflow.api)]:
            source=Path(os.environ.get('MYLAR_WORKFLOW_SOURCE','/app/mylar3/mylar'))/name
            if not source.exists():source=Path('/tmp/mylar-workflow-native/mylar')/name
            if not source.exists():self.skipTest('Native fixture not available')
            changed=patcher(source.read_text());self.assertEqual(patcher(changed),changed);ast.parse(changed)
        changed=patch_workflow.search(source.parent.joinpath('search.py').read_text())
        self.assertIn('not manual and not workflow.in_handoff(issueid)',changed)
        with self.assertRaises(ValueError):patch_workflow.search('def replaced():pass')

    def accepted_handoff(self):
        owner=self.handoff()
        return workflow.set_handoff(owner,'accepted','Downloader confirmed')

    def remove_ddl(self,legacy=None):
        class HTTPError(Exception):
            def __init__(self,status,message):self.status=status;super().__init__(message)
        with patch.dict(sys.modules,{'cherrypy':SimpleNamespace(HTTPError=HTTPError)}):
            return workflow.guard_requeue(legacy or Mock())(None,'remove',id='1')

    def test_confirmed_handoff_remove_preserves_downstream_and_original(self):
        owner=self.accepted_handoff()
        archive=Path(self.tmp.name)/'original.cbz';archive.write_bytes(b'protected archive')
        self.conn.execute("INSERT INTO nzblog VALUES ('10','fixture')")
        app.NZB_QUEUE.put({'issueid':'10','NZBID':'client-accepted'})
        legacy=Mock(side_effect=AssertionError('Legacy removal must not run'))
        response=json.loads(self.remove_ddl(legacy))
        self.assertIs(response['status'],True)
        self.assertIsNone(self.conn.execute('SELECT * FROM ddl_info').fetchone())
        self.assertEqual(workflow.reservation('10'),owner)
        self.assertEqual(archive.read_bytes(),b'protected archive')
        self.assertEqual(app.NZB_QUEUE.qsize(),1)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM nzblog').fetchone()[0],1)
        self.assertEqual(self.conn.execute('SELECT Status FROM issues').fetchone()[0],'Snatched')
        workflow._STORE=Store(self.tmp.name)
        self.assertIs(json.loads(self.remove_ddl(legacy))['status'],True)
        sender=Mock(return_value={'status':True})
        self.assertFalse(workflow.sender(sender,'10')['status']);sender.assert_not_called()
        self.assertEqual(workflow.store().get('ddl_handoff_removal','1')['phase'],'removed')

    def test_pending_handoff_remove_cancels_search_before_submission(self):
        self.handoff();item=app.SEARCH_QUEUE.get_nowait()
        response=json.loads(self.remove_ddl())
        self.assertIn('cancelled before submission',response['message'])
        self.assertIsNone(self.conn.execute('SELECT * FROM ddl_info').fetchone())
        self.assertEqual(workflow.store().get('handoff','10')['phase'],'released')
        self.assertFalse(workflow.reservation('10'))
        workflow._STORE=Store(self.tmp.name)
        workflow.queue_item(item,app.SEARCH_QUEUE)
        app.search.searchforissue.assert_not_called()
        self.assertIs(json.loads(self.remove_ddl())['status'],True)

    def test_pending_handoff_delete_failure_retains_cancelled_search_proof(self):
        self.handoff();item=app.SEARCH_QUEUE.get_nowait();real=DB.action
        def interrupted(database,query,args=()):
            if query.startswith('DELETE FROM ddl_info'):raise OSError('interrupted')
            return real(database,query,args)
        with patch.object(DB,'action',interrupted),self.assertRaises(OSError):self.remove_ddl()
        self.assertEqual(self.status(),'NZB handoff')
        self.assertEqual(workflow.store().get('handoff','10')['phase'],'released')
        workflow.queue_item(item,app.SEARCH_QUEUE);app.search.searchforissue.assert_not_called()
        self.assertIs(json.loads(self.remove_ddl())['status'],True)

    def test_uncertain_handoff_remove_never_changes_row_or_calls_legacy(self):
        row=self.handoff()
        for phase in ('searching','dispatching','review'):
            workflow.set_handoff(row,phase,'Needs proof')
            legacy=Mock()
            with self.subTest(phase=phase),self.assertRaises(Exception) as caught:
                self.remove_ddl(legacy)
            self.assertEqual(caught.exception.status,409)
            self.assertEqual(self.status(),'NZB handoff');legacy.assert_not_called()
            self.assertIsNone(workflow.store().get('ddl_handoff_removal','1'))

    def test_removal_delete_lost_ack_recovers_without_resubmission(self):
        self.accepted_handoff()
        real=Store.replace
        def interrupted(journal,kind,*args,**kwargs):
            if kind=='ddl_handoff_removal':raise OSError('lost acknowledgement')
            return real(journal,kind,*args,**kwargs)
        with patch.object(Store,'replace',interrupted),self.assertRaises(OSError):self.remove_ddl()
        self.assertIsNone(self.conn.execute('SELECT * FROM ddl_info').fetchone())
        self.assertEqual(workflow.store().get('ddl_handoff_removal','1')['phase'],'prepared')
        workflow._STORE=Store(self.tmp.name)
        self.assertIs(json.loads(self.remove_ddl())['status'],True)
        self.assertEqual(workflow.reservation('10')['phase'],'accepted')

    def test_removal_prepared_crash_retries_exact_row_but_holds_changed_provenance(self):
        self.accepted_handoff()
        real=DB.action
        def interrupted(database,query,args=()):
            if query.startswith('DELETE FROM ddl_info'):raise OSError('interrupted before deletion')
            return real(database,query,args)
        with patch.object(DB,'action',interrupted),self.assertRaises(OSError):self.remove_ddl()
        self.assertEqual(self.status(),'NZB handoff')
        self.conn.execute("UPDATE ddl_info SET mainlink='https://example.com/different'")
        with self.assertRaises(Exception) as caught:self.remove_ddl()
        self.assertEqual(caught.exception.status,409);self.assertEqual(self.status(),'NZB handoff')
        self.conn.execute("UPDATE ddl_info SET mainlink='https://example.com/release'")
        self.assertIs(json.loads(self.remove_ddl())['status'],True)

    def test_removal_conditional_delete_holds_concurrent_row_replacement(self):
        self.accepted_handoff();real=DB.action
        def replaced(database,query,args=()):
            if query.startswith('DELETE FROM ddl_info'):
                self.conn.execute("UPDATE ddl_info SET mainlink='https://example.com/foreign'")
            return real(database,query,args)
        with patch.object(DB,'action',replaced),self.assertRaises(Exception) as caught:self.remove_ddl()
        self.assertEqual(caught.exception.status,409);self.assertEqual(self.status(),'NZB handoff')
        self.assertEqual(workflow.store().get('ddl_handoff_removal','1')['phase'],'prepared')

    def test_removed_receipt_cannot_delete_reused_native_id_or_changed_owner(self):
        owner=self.accepted_handoff();self.remove_ddl()
        self.conn.execute("INSERT INTO ddl_info VALUES ('1','10','20','Example #1','0','NZB handoff','DDL(GetComics)','2026-01-01 00:00','GC-Main','https://example.com/release')")
        with self.assertRaises(Exception) as caught:self.remove_ddl()
        self.assertEqual(caught.exception.status,409);self.assertEqual(self.status(),'NZB handoff')
        self.conn.execute('DELETE FROM ddl_info')
        workflow.store().set('handoff','10',dict(owner,id='b'*32))
        with self.assertRaises(Exception) as caught:self.remove_ddl()
        self.assertEqual(caught.exception.status,409)

    def test_ordinary_remove_delegates_and_removed_handoff_receipt_is_strict(self):
        legacy=Mock(return_value='native result')
        self.assertEqual(self.remove_ddl(legacy),'native result');legacy.assert_called_once()
        self.accepted_handoff();self.remove_ddl()
        old=workflow.store().get('ddl_handoff_removal','1')
        for invalid in (dict(old,version=True),dict(old,phase='accepted'),dict(old,unexpected=True)):
            workflow.store().set('ddl_handoff_removal','1',invalid)
            with self.assertRaises(Exception) as caught:self.remove_ddl()
            self.assertEqual(caught.exception.status,409)

    def test_handoff_removal_prompt_explains_pending_vs_accepted(self):
        source=(Path(__file__).parent/'ddl_queue.js').read_text()
        self.assertIn("status==='NZB handoff'",source)
        self.assertIn('Pending NZB searches are cancelled. Accepted NZB downloads continue.',source)
        self.assertIn('Uncertain handoffs require Activity review.',source)
        self.assertIn('xhr.status===409',source)
        self.assertIn("if (mode==='remove' && !confirmed) return;",source)

    def test_orphan_nzb_handoff_label_does_not_prove_safe_removal(self):
        self.conn.execute("UPDATE ddl_info SET status='NZB handoff'")
        legacy=Mock()
        with self.assertRaises(Exception) as caught:self.remove_ddl(legacy)
        self.assertEqual(caught.exception.status,409);legacy.assert_not_called()
        self.assertEqual(self.status(),'NZB handoff')

if __name__=='__main__':unittest.main()
