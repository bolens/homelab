"""Scheduling keeps provider cooldowns and the current transfer intact."""
import queue
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from ddl_schedule import choose,take,started,projected_order,positions,release_dates
from workflow_store import Store


class ScheduleTest(unittest.TestCase):
    def setUp(self):
        self.items=[{'id':str(i),'link_type':'GC-Main'} for i in range(1,5)]
        self.rows={str(i):{'id':str(i),'pack':i%2,'status':'Queued'} for i in range(1,5)}
    def pick(self,mode,preferred='',last='',providers=None):
        return choose(self.items,self.rows,providers or {},mode,preferred,last,100,{str(i):i for i in range(1,5)})
    def test_modes_preserve_fifo_within_group(self):
        self.assertEqual(self.pick('fifo'),0)
        self.assertEqual(self.pick('newest'),3)
        self.assertEqual(self.pick('singles'),1)
        self.assertEqual(self.pick('packs'),0)
        self.assertEqual(self.pick('alternate',last='pack'),1)
        self.assertEqual(self.pick('alternate',last='single'),0)
    def test_explicit_next_does_not_bypass_cooldown(self):
        self.assertEqual(self.pick('singles','3'),2)
        self.items[1]['link_type']='GC-Mirror'
        self.assertEqual(self.pick('packs','3',providers={'GC-Main':{'until':101}}),1)
        self.assertIsNone(self.pick('fifo',providers={'GC-Main':{'until':101},'GC-Mirror':{'until':101}}))
    def test_requeue_does_not_change_oldest_or_newest_age(self):
        self.items.reverse()
        self.assertEqual(self.pick('fifo'),3)
        self.assertEqual(self.pick('newest'),0)

    def test_native_split_ids_are_opaque_and_arrival_is_persistent(self):
        from ddl_schedule import arrival_order
        with tempfile.TemporaryDirectory() as root:
            store=Store(root);mylar=SimpleNamespace(workflow=SimpleNamespace(store=lambda:store))
            items=[{'id':'90000','link_type':'GC-Main'},{'id':'12345-1','link_type':'GC-Main'}]
            rows={r['id']:{'status':'Queued','pack':1} for r in items}
            with patch.dict(sys.modules,{'mylar':mylar,'mylar.workflow_store':sys.modules['workflow_store']}):
                ages=arrival_order(items)
                self.assertEqual(choose(items,rows,{},'fifo','','',100,ages),0)
                self.assertEqual(choose(items,rows,{},'newest','','',100,ages),1)
                items.reverse()
                self.assertEqual(arrival_order(items),ages)
                self.assertEqual(choose(items,rows,{},'fifo','','',100,ages),1)
                self.assertEqual(choose(items,rows,{},'newest','','',100,ages),0)
            from workflow_store import ddl_identifier,identifier
            self.assertEqual(ddl_identifier('12345-1'),'12345-1')
            self.assertEqual(identifier('12345-1'),'')

    def test_active_and_removed_are_not_selected(self):
        self.rows['1']['status']='Downloading'
        del self.rows['2']
        self.assertEqual(self.pick('fifo'),2)

    def test_projection_matches_successive_admissions_for_every_preference(self):
        import itertools
        import random
        randomizer = random.Random(31)
        for key, day in zip(self.rows, (300, None, 100, 300)):
            self.rows[key].update(release_oldest=day, release_newest=day)
        for mode, kind, preferred, last, cooling in itertools.product(
                ('fifo', 'newest', 'release_oldest', 'release_newest'), ('mixed', 'singles', 'packs', 'alternate'), ('', '1', '3', ['3','1']), ('single', 'pack'), (False, True)):
            items = list(self.items)
            randomizer.shuffle(items)
            items[0] = dict(items[0], link_type='GC-Mirror')
            providers = {'GC-Main': {'until': 101}} if cooling else {}
            ages = {str(i): i for i in range(1, 5)}
            projected = projected_order(items, self.rows, providers, mode, preferred, last, 100, ages, kind)
            pending = list(items)
            expected = []
            for blocked, availability in ((False, providers), (True, {})):
                while pending:
                    index = choose(pending, self.rows, availability, mode, preferred, last, 100, ages, kind)
                    if index is None:
                        break
                    item = pending.pop(index)
                    expected.append((item['id'], blocked))
                    last = 'pack' if self.rows[item['id']]['pack'] else 'single'
                    if item['id'] == preferred:
                        preferred = ''
            self.assertEqual(projected, expected)

    def test_release_order_uses_catalog_dates_and_pack_range_not_queue_age(self):
        import queue_control
        database = sqlite3.connect(':memory:')
        self.addCleanup(database.close)
        database.row_factory = sqlite3.Row
        database.executescript("""
            CREATE TABLE ddl_info(id TEXT,comicid TEXT,issueid TEXT,issues TEXT,pack INTEGER,status TEXT);
            CREATE TABLE issues(IssueID TEXT,ComicID TEXT,Issue_Number TEXT,ReleaseDate TEXT,IssueDate TEXT);
            CREATE TABLE annuals(IssueID TEXT,ComicID TEXT,Issue_Number TEXT,ReleaseDate TEXT,IssueDate TEXT);
            INSERT INTO ddl_info VALUES ('1','c','i1',NULL,0,'Queued'),('2','c','i2',NULL,0,'Queued'),
              ('3','c','a1',NULL,0,'Queued'),('4','c','unknown',NULL,0,'Queued'),
              ('5','c','i1','1-2',1,'Queued'),('6','c','i1','1 + Annual',1,'Queued');
            INSERT INTO issues VALUES ('i1','c','1','2024-02-07','2024-04-01'),
              ('i2','c','2','0000-00-00','2025-01-01'),('i3','c','3','2026-01-01',NULL);
            INSERT INTO annuals VALUES ('a1','c','1','2023-05-03','2023-07-01');
        """)
        rows = {r['id']: dict(r) for r in database.execute('SELECT * FROM ddl_info')}
        adapter = SimpleNamespace(select=lambda sql: database.execute(sql).fetchall())
        with patch.dict(sys.modules, {'mylar.queue_control': queue_control}):
            release_dates(rows, adapter)
        self.assertLess(rows['1']['release_newest'], rows['2']['release_oldest'])
        self.assertEqual(rows['5']['release_oldest'], rows['1']['release_oldest'])
        self.assertEqual(rows['5']['release_newest'], rows['2']['release_newest'])
        self.assertEqual(rows['6']['release_newest'], rows['1']['release_newest'])
        self.assertIsNone(rows['4']['release_newest'])
        items = [{'id': key} for key in rows]
        ages = {item['id']: i for i, item in enumerate(items)}
        def ordered(mode):
            return [key for key, _ in projected_order(items, rows, {}, mode, '', '', 100, ages)]
        self.assertEqual(ordered('release_newest'), ['2', '5', '1', '6', '3', '4'])
        self.assertEqual(ordered('release_oldest'), ['3', '1', '5', '6', '2', '4'])
        self.assertEqual(ordered('fifo'), list(rows))
        self.assertEqual(ordered('newest'), list(reversed(rows)))

    def test_positions_are_read_only_while_paused_and_keep_history_last(self):
        import threading
        with tempfile.TemporaryDirectory() as root:
            store = Store(root)
            store.set('meta', 'ddl_next', '3')
            q = queue.Queue()
            for item in self.items:
                q.put(item)
            rows = dict(self.rows, active={'id': 'active', 'status': 'Downloading'},
                        past={'id': 'past', 'status': 'Completed'},
                        absent={'id': 'absent', 'status': 'Queued'})
            mylar = SimpleNamespace(DDL_QUEUE=q,
                workflow=SimpleNamespace(store=lambda:store, policy=lambda:{'ddl_order':'singles', 'ddl_paused':True}),
                queue_control=SimpleNamespace(_LOCK=threading.RLock(),store=lambda:SimpleNamespace(data={'providers':{}})))
            with patch.dict(sys.modules, {'mylar':mylar, 'mylar.workflow_store':sys.modules['workflow_store']}):
                result = positions(rows.values())
            self.assertEqual(result['active']['sort'], 0)
            self.assertEqual(result['3']['sort'], 1)
            self.assertLess(result['2']['sort'], result['1']['sort'])
            self.assertGreater(result['absent']['sort'], result['4']['sort'])
            self.assertGreater(result['past']['sort'], result['absent']['sort'])
            self.assertEqual(list(q.queue), self.items)
            self.assertEqual(q.unfinished_tasks, 4)
            self.assertEqual(store.get('meta','ddl_next'), '3')
            self.assertIsNone(store.get('meta','ddl_arrivals'))
    def test_pause_exit_and_queue_accounting(self):
        import threading
        with tempfile.TemporaryDirectory() as root:
            store=Store(root);rules={'ddl_order':'singles','ddl_paused':True}
            database=Mock();database.select.return_value=list(self.rows.values())
            database.selectone.return_value.fetchone.return_value={'pack':0}
            mylar=SimpleNamespace(db=SimpleNamespace(DBConnection=lambda:database),
                workflow=SimpleNamespace(policy=lambda:rules,store=lambda:store,emit=Mock()),
                queue_control=SimpleNamespace(_LOCK=threading.RLock(),store=lambda:SimpleNamespace(data={'providers':{}})))
            q=queue.Queue()
            for item in self.items:q.put(item)
            with patch.dict(sys.modules,{'mylar':mylar,'mylar.workflow_store':sys.modules['workflow_store']}):
                self.assertIsNone(take(q));self.assertEqual(q.qsize(),4)
                rules['ddl_paused']=False
                store.set('meta','ddl_next','2')
                item=take(q);self.assertEqual(item['id'],'2');self.assertEqual(q.qsize(),3)
                self.assertEqual(store.get('meta','ddl_next'),'2')
                self.assertIsNone(store.get('meta','ddl_last_kind'))
                from workflow_store import LOCK
                with patch.dict(sys.modules,{'mylar.workflow_store':SimpleNamespace(LOCK=LOCK)}):started(item)
                self.assertIsNone(store.get('meta','ddl_next'))
                self.assertEqual(store.get('meta','ddl_last_kind'),'single')
                self.assertEqual(q.unfinished_tasks,4)
                q.task_done();self.assertEqual(q.unfinished_tasks,3)
                rules['ddl_paused']=True;q.put('exit')
                self.assertEqual(take(q),'exit')
                self.assertEqual(q.qsize(),3)


if __name__=='__main__':unittest.main()
