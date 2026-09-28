"""Regressions for annual filename IDs and empty/failed processing runs."""
import ast
from contextlib import nullcontext
from pathlib import Path
import queue
import sqlite3
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

from processing_guard import run
from patch_postprocessing import processor, processing
from patch_pack_intake import helpers, search
from patch_ddl_schedule import scheduler
from patch_series_preservation import startup

SOURCE = Path(sys.argv.pop(1)) if len(sys.argv) > 1 and not sys.argv[1].startswith('-') else None


class ProcessingTest(unittest.TestCase):
    def test_empty_error_and_success_release_owned_lock(self):
        mylar = SimpleNamespace(APILOCK=False, native_writers=SimpleNamespace(owner=lambda:SimpleNamespace(hold=lambda **kwargs:nullcontext())), pack_intake=SimpleNamespace(capture=Mock(return_value=False)))
        for error in (False, True):
            obj = SimpleNamespace(queue=queue.Queue())
            @run
            def operation(self):
                self.assert_locked = mylar.APILOCK
                if error:
                    raise ValueError('unreadable source')
            with patch.dict(sys.modules, {'mylar': mylar}):
                if error:
                    with self.assertRaises(ValueError):
                        operation(obj)
                else:
                    operation(obj)
            self.assertTrue(obj.assert_locked)
            self.assertFalse(mylar.APILOCK)
            self.assertEqual(obj.queue.get_nowait(), [{'mode': 'stop'}])

    def test_concurrent_call_waits_for_owner(self):
        mylar = SimpleNamespace(APILOCK=False, native_writers=SimpleNamespace(owner=lambda:SimpleNamespace(hold=lambda **kwargs:nullcontext())), pack_intake=SimpleNamespace(capture=Mock(return_value=False)))
        entered, release, second = threading.Event(), threading.Event(), threading.Event()
        @run
        def operation(self):
            if self.first:
                entered.set()
                release.wait(3)
            else:
                second.set()
            self.locked = mylar.APILOCK
        a = SimpleNamespace(first=True, queue=queue.Queue())
        b = SimpleNamespace(first=False, queue=queue.Queue())
        with patch.dict(sys.modules, {'mylar': mylar}):
            one = threading.Thread(target=operation, args=(a,))
            two = threading.Thread(target=operation, args=(b,))
            one.start()
            self.assertTrue(entered.wait(1))
            two.start()
            self.assertFalse(second.wait(.05))
            self.assertTrue(mylar.APILOCK)
            release.set()
            one.join(3)
            two.join(3)
        self.assertTrue(a.locked and b.locked)
        self.assertFalse(mylar.APILOCK)

    @unittest.skipUnless(SOURCE and (SOURCE/'helpers.py').exists(), 'native image source required')
    def test_pack_failure_releases_reservations_without_overwriting_issue_status(self):
        patched=helpers((SOURCE/'helpers.py').read_text())
        node=next(n for n in ast.parse(patched).body if isinstance(n,ast.FunctionDef) and n.name=='reverse_the_pack_snatch')
        database=Mock();mylar=SimpleNamespace(PACK_ISSUEIDS_DONT_QUEUE={'downloaded':'pack','wanted':'pack','other':'another'})
        scope={'logger':Mock(),'mylar':mylar,'db':SimpleNamespace(DBConnection=lambda:database)}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'helpers.py','exec'),scope)
        scope['reverse_the_pack_snatch']('pack','series')
        database.upsert.assert_not_called()
        self.assertEqual(mylar.PACK_ISSUEIDS_DONT_QUEUE,{'other':'another'})
        self.assertNotIn("for isid in issinfo['issues']:",search((SOURCE/'search.py').read_text()))
        source=scheduler((SOURCE/'queues/ddl.py').read_text())
        self.assertEqual(scheduler(source),source)
        self.assertIn('queue_schedule.take(queue)',source)

    @unittest.skipUnless(SOURCE and (SOURCE/'__init__.py').exists(), 'native image source required')
    def test_startup_preserves_incomplete_series_with_issue_or_annual(self):
        source=startup((SOURCE/'__init__.py').read_text())
        self.assertEqual(startup(source),source)
        query=next(n.value for n in ast.walk(ast.parse(source)) if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.startswith('DELETE from comics WHERE ('))
        db=sqlite3.connect(':memory:');self.addCleanup(db.close)
        db.executescript("CREATE TABLE comics(ComicID,ComicName);CREATE TABLE issues(ComicID);CREATE TABLE annuals(ComicID);INSERT INTO comics VALUES('1','Comic ID: 1'),('2','Comic ID: 2'),('3','Comic ID: 3'),('4','Valid name');INSERT INTO issues VALUES('1');INSERT INTO annuals VALUES('2');")
        db.execute(query)
        self.assertEqual(db.execute('SELECT ComicID FROM comics ORDER BY ComicID').fetchall(),[('1',),('2',),('4',)])

    @unittest.skipUnless(SOURCE, 'native image source required')
    def test_native_filename_identity_prefers_annual_and_honors_tombstone(self):
        source=processor((SOURCE/'PostProcessor.py').read_text())
        tree=ast.parse(source)
        block=next(n for n in ast.walk(tree) if isinstance(n,ast.If)
                   and ast.unparse(n.test)=="fl['issueid'] is not None"
                   and any(isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='annchk' for t in x.targets) for x in n.body))
        end=next(i for i,n in enumerate(block.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='osi' for t in n.targets))
        loop=ast.parse("for fl in files:\n    results.append((fl['issueid'], dict(csi) if csi else None, annchk))").body[0]
        loop.body=block.body[:end]+loop.body
        db=sqlite3.connect(':memory:');self.addCleanup(db.close);db.row_factory=sqlite3.Row
        db.executescript("""CREATE TABLE comics(ComicID,ComicName,ComicYear,AgeRating);
            CREATE TABLE issues(ComicID,IssueID,Issue_Number);
            CREATE TABLE annuals(ComicID,IssueID,Issue_Number,ReleaseComicName,ReleaseComicID,Deleted);
            INSERT INTO comics VALUES('1','Parent','2020','Teen'),('2','Shadow','2020','Teen');
            INSERT INTO issues VALUES('2','100','1'),('2','101','1'),('2','102','1');
            INSERT INTO annuals VALUES('1','100','1','Parent Annual','3',0),('1','101','2','Parent Annual','3',1);
        """)
        def selectone(query,args):
            if 'FROM storyarcs' in query:return SimpleNamespace(fetchone=lambda:None)
            return db.execute(query,args)
        scope={'files':[{'issueid':i} for i in ('100','101','102')],'results':[],
               'myDB':SimpleNamespace(selectone=selectone),'logger':Mock()}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[loop],type_ignores=[])),'native-identity','exec'),scope)
        self.assertEqual([(i,row['ComicID'],annual) for i,row,annual in scope['results']], [('100','1','yes'),('102','2','no')])

    @unittest.skipUnless(SOURCE, 'native image source required')
    def test_annual_query_executes_with_downstream_fields_and_deleted_filter(self):
        source = processor((SOURCE / 'PostProcessor.py').read_text())
        self.assertEqual(processor(source), source)
        tree = ast.parse(source)
        query = next(n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
                     and isinstance(n.value, str) and 'JOIN annuals as i' in n.value and 'AgeRating' in n.value)
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.row_factory = sqlite3.Row
        db.executescript('''CREATE TABLE comics(ComicID, ComicName, ComicYear, AgeRating);
            CREATE TABLE annuals(ComicID, IssueID, Issue_Number, ReleaseComicName, ReleaseComicID, Deleted);
            INSERT INTO comics VALUES('1','Space Heroes','2019','Teen');
            INSERT INTO annuals VALUES('1','100','1','Space Heroes Annual','2',0);
            INSERT INTO annuals VALUES('1','101','1','Space Heroes Annual','3',1);''')
        row = db.execute(query, ['100']).fetchone()
        self.assertEqual(row['ReleaseComicName'], 'Space Heroes Annual')
        self.assertEqual(row['ComicID'], '1')
        self.assertIsNone(db.execute(query, ['101']).fetchone())
        native = processing((SOURCE / 'process.py').read_text())
        self.assertEqual(processing(native), native)
        self.assertNotIn('threading.Thread(target=PostProcess.Process).start()', native)


if __name__ == '__main__':
    unittest.main()
