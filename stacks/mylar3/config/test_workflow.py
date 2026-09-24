"""Workflow ownership, admission, security and native integration regressions."""
import ast
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
    def upsert(self,table,values,where):
        self.conn.execute('UPDATE '+table+' SET '+','.join(k+'=?' for k in values)+' WHERE '+' AND '.join(k+'=?' for k in where),list(values.values())+list(where.values()));self.conn.commit()

class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.conn=sqlite3.connect(':memory:',check_same_thread=False);self.conn.row_factory=sqlite3.Row;self.addCleanup(self.conn.close)
        self.conn.executescript("""
            CREATE TABLE issues(IssueID TEXT,ComicID TEXT,ComicName TEXT,Status TEXT,Location TEXT);
            INSERT INTO issues VALUES ('10','20','Example','Snatched',NULL);
            CREATE TABLE ddl_info(id TEXT,issueid TEXT,comicid TEXT,series TEXT,pack TEXT,status TEXT,site TEXT,updated_date TEXT,link_type TEXT);
            INSERT INTO ddl_info VALUES ('1','10','20','Example #1','0','Queued','DDL(GetComics)','2026-01-01 00:00','GC-Main');
            CREATE TABLE nzblog(IssueID TEXT,PROVIDER TEXT);
        """)
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

    def test_native_patch_is_idempotent_and_preserves_return_contract(self):
        import patch_workflow
        for name,patcher in [('search.py',patch_workflow.search),('queues/search.py',patch_workflow.search_queue),('queues/ddl.py',patch_workflow.ddl),('webserve.py',patch_workflow.server),('api.py',patch_workflow.api)]:
            source=Path('/app/mylar3/mylar')/name
            if not source.exists():source=Path('/tmp/mylar-workflow-native/mylar')/name
            if not source.exists():self.skipTest('Native fixture not available')
            changed=patcher(source.read_text());self.assertEqual(patcher(changed),changed);ast.parse(changed)
        changed=patch_workflow.search(source.parent.joinpath('search.py').read_text())
        self.assertIn('not manual and not workflow.in_handoff(issueid)',changed)
        with self.assertRaises(ValueError):patch_workflow.search('def replaced():pass')

if __name__=='__main__':unittest.main()
