"""Failover is immediate, bounded and prioritized without bypassing admission."""
import os
from pathlib import Path
import queue
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import ddl_failover
import ddl_schedule
import queue_control
import workflow_store
from patch_ddl_failover import patched_source


class FailoverTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.control = queue_control.Store(self.temp.name, clock=lambda:100)
        self.store = workflow_store.Store(self.temp.name)
        self.queue = queue.Queue()
        self.item = dict(id='123-1', mainlink='release', issueid='42', comicid='7', link_type='GC-Main')
        self.connection=sqlite3.connect(':memory:');self.connection.row_factory=sqlite3.Row
        self.addCleanup(self.connection.close)
        self.connection.execute('CREATE TABLE ddl_info(id TEXT PRIMARY KEY,status TEXT,pack INTEGER,issues TEXT,comicid TEXT,issueid TEXT,link TEXT,mainlink TEXT,link_type TEXT)')
        for id,pack in [('123-1',1),('900',0)]:
            self.connection.execute('INSERT INTO ddl_info VALUES (?,?,?,NULL,?,?,NULL,?,?)', (id,'Queued',pack,'7','42','release','GC-Main'))
        self.rows={row['id']:dict(row) for row in self.connection.execute('SELECT * FROM ddl_info')}
        def action(sql,args=()):
            result=self.connection.execute(sql,args);self.connection.commit();return result
        self.database=database=SimpleNamespace(action=action,
            select=lambda sql,args=():self.connection.execute(sql,args).fetchall(),
            selectone=lambda sql,args=():self.connection.execute(sql,args), upsert=Mock())
        self.before_persist=lambda:None
        self.owner=SimpleNamespace(issueid='42',comicid='7')
        self.rules = {'ddl_order':'newest','ddl_kind':'singles','ddl_paused':False}
        self.mylar = SimpleNamespace(DDL_QUEUE=self.queue, queue_control=queue_control, ddl_failover=ddl_failover, ddl_schedule=ddl_schedule, getcomics=SimpleNamespace(GC=Mock()), logger=Mock(),
            db=SimpleNamespace(DBConnection=lambda:database),
            workflow=SimpleNamespace(store=lambda:self.store, policy=lambda:self.rules,emit=Mock(), reservation=lambda key:None, import_owner=lambda key:None, dispatch_owner=lambda key:None))
        self.addCleanup(patch.stopall)
        patch.object(queue_control,'_STORE',self.control).start()
        patch('ddl_schedule.time.time',return_value=100).start()
        patch.dict(sys.modules,{'mylar':self.mylar,'mylar.workflow_store':workflow_store}).start()

    def parser(self, available):
        calls=[]
        def parse(owner,id,mainlink,comicinfo,packinfo,failed):
            calls.append(list(failed or []))
            provider=next((v for v in available if v not in (failed or [])),None)
            if provider is None:return {'success':False,'links_exhausted':failed}
            item=dict(self.item,id=id,link_type=provider,link=provider)
            self.before_persist()
            if failed and not ddl_failover.persist(self.database,dict(status='Queued',link=provider,link_type=provider),{'id':id},failed):
                return {'success':False,'cancelled':True}
            ddl_failover.enqueue(item,failed)
            return {'success':True,'site':provider}
        return ddl_failover.discovery(parse),calls

    def failed_download(self):
        self.assertEqual(self.control.begin(self.item),'ready')
        self.control.finish(self.item,False)

    def test_failure_checks_alternate_now_then_takes_it_before_newer_singles(self):
        self.failed_download();self.queue.put(dict(id='900',link_type='GC-Mega'))
        parse,calls=self.parser(['GC-Main','GC-Mirror'])
        result=parse(self.owner,'123-1','release',link_type_failure=['GC-Main'])
        self.assertEqual(result['site'],'GC-Mirror');self.assertEqual(calls,[['GC-Main']])
        selected=ddl_schedule.take(self.queue)
        self.assertEqual((selected['id'],selected['link_type']),('123-1','GC-Mirror'))
        self.assertEqual(self.control.record(self.item)['attempts'],1)
        self.assertEqual(self.queue.unfinished_tasks,2)
        ddl_schedule.started(selected)
        self.assertEqual(self.store.get('meta','ddl_retry_next'),[])

    def test_cooling_alternative_is_skipped_but_all_cooling_stays_queued(self):
        self.failed_download();self.control.data['providers']['GC-Mirror']={'until':200}
        parse,calls=self.parser(['GC-Main','GC-Mirror','GC-Mega'])
        self.assertEqual(parse(self.owner,'123-1','release',link_type_failure=['GC-Main'])['site'],'GC-Mega')
        self.assertEqual(len(calls),1)
        self.queue.get_nowait()
        self.control.data['providers']['GC-Mega']={'until':200}
        result=parse(self.owner,'123-1','release',link_type_failure=['GC-Main'])
        self.assertTrue(result['success']);self.assertEqual(len(calls),3)
        self.assertIsNone(ddl_schedule.take(self.queue))
        self.assertEqual(self.control.record(self.item)['attempts'],1)
        self.assertEqual(self.store.get('meta','ddl_retry_next'),['123-1'])

    def test_pause_keeps_priority_and_restart_preserves_failure_history(self):
        self.failed_download();parse,_=self.parser(['GC-Mirror'])
        parse(self.owner,'123-1','release',link_type_failure=['GC-Main'])
        self.rules['ddl_paused']=True
        self.assertIsNone(ddl_schedule.take(self.queue))
        self.store=workflow_store.Store(self.temp.name)
        self.control=queue_control.Store(self.temp.name,clock=lambda:100)
        queue_control._STORE=self.control
        self.assertEqual(self.control.record(self.item)['failed_providers'],['GC-Main'])
        self.assertEqual(self.store.get('meta','ddl_retry_next'),['123-1'])
        self.rules['ddl_paused']=False
        self.assertEqual(ddl_schedule.take(self.queue)['id'],'123-1')
        self.control.reset('123-1')
        self.assertEqual(self.control.record(self.item)['failed_providers'],[])

    def test_attempt_limit_prevents_new_discovery_and_exhaustion_adds_no_priority(self):
        self.failed_download();self.control.record(self.item)['attempts']=6
        parse,calls=self.parser(['GC-Mirror'])
        self.assertIn('links_exhausted',parse(self.owner,'123-1','release',link_type_failure=['GC-Main']))
        self.assertEqual(calls,[]);self.assertEqual(self.queue.qsize(),0)
        self.control.record(self.item)['attempts']=1
        parse,calls=self.parser(['GC-Main'])
        self.assertIn('links_exhausted',parse(self.owner,'123-1','release',link_type_failure=['GC-Main']))
        self.assertIsNone(self.store.get('meta','ddl_retry_next'))

    def test_discovery_errors_propagate_to_existing_bounded_worker_retry(self):
        parser=ddl_failover.discovery(Mock(side_effect=OSError('DNS failure')))
        with self.assertRaises(OSError):parser(self.owner,'123-1','release',link_type_failure=['GC-Main'])
        self.assertEqual(self.queue.qsize(),0)

    def test_split_retries_keep_order_and_manual_next_is_retained(self):
        self.store.set('meta','ddl_next','900')
        ddl_failover.enqueue(dict(self.item,id='123-1'),['GC-Main'])
        self.connection.execute("INSERT INTO ddl_info SELECT '123-2',status,pack,issues,comicid,issueid,link,mainlink,link_type FROM ddl_info WHERE id='123-1'")
        ddl_failover.enqueue(dict(self.item,id='123-2'),['GC-Main'])
        self.assertEqual(ddl_schedule.priorities(self.store),['123-1','123-2','900'])
        self.assertEqual(self.store.get('meta','ddl_next'),'900')

    def test_fresh_search_does_not_gain_priority(self):
        parse,calls=self.parser(['GC-Main'])
        parse(self.owner,'123-1','release')
        self.assertIsNone(self.store.get('meta','ddl_retry_next'))
        self.assertEqual(self.queue.qsize(),1)

    def test_cooldown_sweep_uses_queue_preferences_and_replaces_one_pending_payload(self):
        self.control.data['providers']['GC-Main']={'until':1000}
        self.queue.put(dict(self.item,site='DDL(GetComics)'))
        self.queue.put(dict(self.item,id='900',site='DDL(GetComics)'))
        seen=[]
        def parse(id,link,comicinfo,packinfo,excluded):
            seen.append((id,packinfo,excluded))
            self.database.action("UPDATE ddl_info SET link_type='GC-Mega' WHERE id=?",[id])
            ddl_failover.enqueue(dict(self.item,id=id,link_type='GC-Mega'),excluded)
            return {'success':True}
        self.mylar.getcomics.GC.return_value.parse_downloadresults.side_effect=parse
        self.assertIsNone(ddl_schedule.take(self.queue))
        self.assertEqual(seen[0][0],'900')  # newer single precedes older pack
        self.assertEqual(seen[0][2],['GC-Main'])
        self.assertEqual(self.queue.qsize(),2)
        self.assertEqual(self.queue.unfinished_tasks,2)
        self.assertEqual(ddl_schedule.take(self.queue)['link_type'],'GC-Mega')
        self.assertEqual(self.store.get('meta','ddl_retry_next'),['900'])
        self.assertEqual(self.control.record(self.item)['attempts'],0)

    def test_cooldown_sweep_advances_after_miss_and_paces_repeat_checks(self):
        self.rules.update(ddl_order='fifo',ddl_kind='mixed')
        self.control.data['providers']['GC-Main']={'until':1000}
        self.queue.put(dict(self.item,site='DDL(GetComics)'))
        self.queue.put(dict(self.item,id='900',site='DDL(GetComics)'))
        parser=self.mylar.getcomics.GC.return_value.parse_downloadresults
        parser.return_value={'success':False,'links_exhausted':['GC-Main']}
        self.assertIsNone(ddl_schedule.take(self.queue))
        self.assertEqual(parser.call_args.args[0],'123-1')
        self.assertTrue(parser.call_args.args[3]['pack'])
        self.assertIsNone(ddl_schedule.take(self.queue));self.assertEqual(parser.call_count,1)
        with patch('ddl_schedule.time.time',return_value=106):
            self.assertIsNone(ddl_schedule.take(self.queue))
        self.assertEqual(parser.call_args.args[0],'900')
        with patch('ddl_schedule.time.time',return_value=112):
            self.assertIsNone(ddl_schedule.take(self.queue))
        self.assertEqual(parser.call_count,2)
        self.assertEqual(self.queue.qsize(),2)
        self.assertIsNone(self.store.get('meta','ddl_retry_next'))

    def test_ready_item_and_pause_do_not_trigger_cooldown_discovery(self):
        self.control.data['providers']['GC-Main']={'until':1000}
        self.queue.put(dict(self.item,site='DDL(GetComics)'))
        self.queue.put(dict(self.item,id='900',link_type='GC-Mega',site='DDL(GetComics)'))
        self.assertEqual(ddl_schedule.take(self.queue)['id'],'900')
        self.mylar.getcomics.GC.assert_not_called()
        self.rules['ddl_paused']=True
        self.assertIsNone(ddl_schedule.take(self.queue))
        self.mylar.getcomics.GC.assert_not_called()

    def test_concurrent_cancel_handoff_or_changed_link_cannot_be_republished(self):
        for mutation in ("DELETE FROM ddl_info WHERE id='123-1'",
                         "UPDATE ddl_info SET status='NZB handoff' WHERE id='123-1'",
                         "UPDATE ddl_info SET link='newer' WHERE id='123-1'"):
            with self.subTest(mutation=mutation):
                self.connection.execute("INSERT OR REPLACE INTO ddl_info VALUES ('123-1','Queued',1,NULL,'7','42',NULL,'release','GC-Main')")
                self.before_persist=lambda:self.database.action(mutation)
                parse,_=self.parser(['GC-Mirror'])
                result=parse(self.owner,'123-1','release',link_type_failure=['GC-Main'])
                self.assertTrue(result['cancelled'])
                self.assertEqual(self.queue.qsize(),0)
                self.assertIsNone(self.store.get('meta','ddl_retry_next'))
        self.before_persist=lambda:None
        self.mylar.workflow.reservation=lambda key:{'phase':'queued'}
        parse,_=self.parser(['GC-Mirror'])
        self.assertTrue(parse(self.owner,'123-1','release',link_type_failure=['GC-Main'])['cancelled'])
        self.assertEqual(self.queue.qsize(),0)

    def test_deleted_priority_and_probe_records_are_pruned(self):
        self.store.set('meta','ddl_retry_next',['missing','123-1'])
        self.store.set('ddl_mirror_probe','missing',{'after':1000})
        self.store.set('ddl_mirror_probe','123-1',{'after':1000})
        ddl_schedule.prune_priorities(self.store,self.rows)
        self.assertEqual(self.store.get('meta','ddl_retry_next'),['123-1'])
        self.assertIsNone(self.store.get('ddl_mirror_probe','missing'))
        self.assertIsNotNone(self.store.get('ddl_mirror_probe','123-1'))

    def test_installed_native_patch_is_idempotent_and_wired(self):
        source=os.environ.get('MYLAR_WORKFLOW_SOURCE')
        if not source:self.skipTest('Native source supplied by image gate')
        value=patched_source((Path(source)/'getcomics.py').read_text())
        self.assertEqual(patched_source(value),value)
        self.assertIn('ddl_failover.enqueue(queue_payload, link_type_failure)',value)
        self.assertIn('GC.parse_downloadresults = ddl_failover.discovery(GC.parse_downloadresults)',value)


if __name__=='__main__':unittest.main()
