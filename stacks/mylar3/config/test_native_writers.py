"""Native operation ownership includes placement, errors and queue completion."""
from importlib import import_module
from pathlib import Path
import queue
import shutil
import ast
import os
import sys
import tempfile
import threading
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from processing_guard import run


class NativeWriterTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.mylar=ModuleType('mylar');self.mylar.__path__=[str(Path(__file__).parent)]
        self.mylar.DATA_DIR=self.temp.name;self.mylar.APILOCK=False
        self.mylar.PP_QUEUE=queue.Queue();self.mylar.logger=Mock()
        self.mylar.pack_intake=SimpleNamespace(capture=Mock(return_value=False))
        context=patch.dict(sys.modules,{'mylar':self.mylar});context.start();self.addCleanup(context.stop)
        self.native=import_module('mylar.native_writers');self.mylar.native_writers=self.native
        self.native.initialize()

    def test_manual_and_processing_share_lock_until_final_return(self):
        entered,release,processed=threading.Event(),threading.Event(),threading.Event()
        @self.native.guard
        def manual():
            entered.set();release.wait(3)
        @run
        def processing(obj):
            self.assertTrue(self.mylar.APILOCK);processed.set()
        obj=SimpleNamespace(queue=queue.Queue())
        one=threading.Thread(target=manual);two=threading.Thread(target=processing,args=(obj,))
        one.start();self.assertTrue(entered.wait(1));two.start()
        try:self.assertFalse(processed.wait(.05))
        finally:release.set();one.join(3);two.join(3)
        self.assertTrue(processed.is_set());self.assertFalse(self.mylar.APILOCK)
        self.assertEqual(obj.queue.get_nowait(),[{'mode':'stop'}])

    def test_busy_admission_requeues_exact_job_then_processes_once(self):
        owner=self.native.owner()
        with owner.hold(allow_pending=True):owner.mark_pending()
        operation=Mock()
        wrapped=run(lambda obj:operation())
        obj=SimpleNamespace(queue=queue.Queue(), nzb_name='Issue.cbz',
                            nzb_folder='/cache/Issue.cbz', issueid='35', comicid='12',
                            apicall=True, ddl=True, download_info={'provider':'DDL','id':'99'})
        proxy=SimpleNamespace(hold=lambda **kwargs:owner.hold(timeout=0))
        with patch.object(self.native,'owner',return_value=proxy):
            wrapped(obj)
        operation.assert_not_called();self.assertFalse(self.mylar.APILOCK)
        self.assertEqual(obj.queue.get_nowait(),[{'mode':'stop'}])
        self.assertEqual(self.mylar.PP_QUEUE.get_nowait(), {
            'nzb_name':'Issue.cbz', 'nzb_folder':'/cache/Issue.cbz',
            'issueid':'35', 'comicid':'12', 'failed':False, 'apicall':True,
            'ddl':True, 'download_info':{'provider':'DDL','id':'99'}})
        with owner.hold(allow_pending=True):owner.clear_pending()
        wrapped(obj)
        operation.assert_called_once()
        self.assertTrue(self.mylar.PP_QUEUE.empty())

    def test_failure_after_admission_never_replays_processing(self):
        from mylar.media_writer import Busy
        obj=SimpleNamespace(queue=queue.Queue())
        operation=Mock(side_effect=Busy('failure after writing began'))
        with self.assertRaises(Busy):run(lambda obj:operation())(obj)
        operation.assert_called_once()
        self.assertTrue(self.mylar.PP_QUEUE.empty())
        self.assertFalse(self.mylar.APILOCK)
        self.assertEqual(obj.queue.get_nowait(),[{'mode':'stop'}])

    def test_invalid_admission_is_not_retried(self):
        obj=SimpleNamespace(queue=queue.Queue())
        with patch.object(self.native,'owner',side_effect=ValueError('invalid protocol')):
            with self.assertRaises(ValueError):run(lambda obj:None)(obj)
        self.assertTrue(self.mylar.PP_QUEUE.empty())
        self.assertEqual(obj.queue.get_nowait(),[{'mode':'stop'}])

    @unittest.skipUnless(os.getenv('MYLAR_WORKFLOW_SOURCE'), 'Patched native source required')
    def test_patch_guards_all_declared_callers_and_recovers_before_database(self):
        from patch_media_writers import GUARDS, main
        root=Path(self.temp.name)/'native-copy'
        shutil.copytree(Path(os.environ['MYLAR_WORKFLOW_SOURCE']),root)
        before={p:p.read_bytes() for p in [root/'__init__.py', *(root/name for name in GUARDS)]}
        main(root)
        self.assertEqual(before,{p:p.read_bytes() for p in before})
        for filename,names in GUARDS.items():
            tree=ast.parse((root/filename).read_text())
            for name in names:
                nodes=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name]
                self.assertEqual(len(nodes),1)
                self.assertEqual(sum(ast.unparse(d)=='native_writers.guard' for d in nodes[0].decorator_list),1)
        source=(root/'__init__.py').read_text()
        self.assertLess(source.index('native_writers.initialize_publication()'),source.index('# Initialize the database'))

    def test_error_releases_manual_lock(self):
        @self.native.guard
        def manual():raise ValueError('fixture')
        with self.assertRaises(ValueError):manual()
        with self.native.owner().hold(timeout=0):pass


if __name__=='__main__':unittest.main()
