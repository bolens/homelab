"""Regressions for annual filename IDs and empty/failed processing runs."""
import ast
from pathlib import Path
import queue
import sqlite3
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

from processing_guard import run
from patch_pack_intake import processor, processing, helpers, search, scheduler

SOURCE = Path(sys.argv.pop(1)) if len(sys.argv) > 1 and not sys.argv[1].startswith('-') else None


class ProcessingTest(unittest.TestCase):
    def test_empty_error_and_success_release_owned_lock(self):
        mylar = SimpleNamespace(APILOCK=False, pack_intake=SimpleNamespace(capture=Mock(return_value=False)))
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
        mylar = SimpleNamespace(APILOCK=False, pack_intake=SimpleNamespace(capture=Mock(return_value=False)))
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
