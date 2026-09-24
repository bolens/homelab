"""Native NZB polling ownership, paused queues and verified failure boundaries."""
import ast
import importlib
from pathlib import Path
from queue import Queue
import unittest
from unittest.mock import Mock, patch

import test_workflow as fixtures
import patch_workflow

workflow = fixtures.workflow
app = fixtures.app
nzb = importlib.import_module('mylar.workflow_nzb')


class NativeNZBTest(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.WorkflowTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        app.RETURN_THE_NZBQUEUE = Queue()
        self.item = {'issueid': '10', 'comicid': '20', 'NZBID': 123}

    def test_preexisting_job_retains_ownership_after_queue_get(self):
        app.NZB_QUEUE.put(self.item)
        self.assertTrue(nzb.busy('10'))
        self.assertEqual(nzb.take(app.NZB_QUEUE), self.item)
        self.assertEqual(app.NZB_QUEUE.qsize(), 0)
        self.assertTrue(nzb.busy('10'))
        self.assertEqual(workflow.dispatch_owner('10')['phase'], 'accepted')
        with self.assertRaises(ValueError): workflow.admit_import('10')

    def test_paused_queue_and_nested_client_parameters_are_kept_private(self):
        item = dict(self.item, nzo_id='client-id', queue={'apikey': 'fixture-private'})
        app.RETURN_THE_NZBQUEUE.put(item)
        self.assertTrue(nzb.busy('10'))
        nzb.take(app.RETURN_THE_NZBQUEUE)
        record = workflow.store().get('native_nzb', '10')
        self.assertNotIn('fixture-private', str(record))
        self.assertNotIn('client-id', str(record))
        self.assertTrue(nzb.busy('10'))

    def test_removal_is_review_not_permission_to_send_again(self):
        app.NZB_QUEUE.put(self.item);nzb.take(app.NZB_QUEUE)
        nzb.complete(lambda *args: None)(app.NZB_QUEUE, self.item, {'status':'nzb removed'})
        self.assertFalse(nzb.busy('10'))
        self.assertEqual(workflow.dispatch_owner('10')['phase'], 'review')
        sender = Mock(return_value={'status':True})
        workflow.sender(sender, '10');sender.assert_not_called()

    def test_handoff_removal_becomes_review(self):
        held = self.fixture.handoff();workflow.set_handoff(held, 'accepted', 'Accepted')
        app.NZB_QUEUE.put(self.item);nzb.take(app.NZB_QUEUE)
        nzb.complete(lambda *args: None)(app.NZB_QUEUE, self.item, {'status':'file not found'})
        self.assertEqual(workflow.reservation('10')['phase'], 'review')

    def test_failed_result_stays_held_until_native_verifies_retry(self):
        app.NZB_QUEUE.put(self.item);nzb.take(app.NZB_QUEUE)
        nzb.complete(lambda *args: None)(app.NZB_QUEUE, self.item, {'status':True,'failed':True})
        self.assertEqual(workflow.dispatch_owner('10')['phase'], 'accepted')
        workflow.release_failed('10')
        self.assertIsNone(workflow.dispatch_owner('10'))

    def test_poll_failure_and_restart_keep_durable_hold_without_phantom_poll(self):
        app.NZB_QUEUE.put(self.item);nzb.take(app.NZB_QUEUE)
        with patch.object(nzb, '_RUN', 'next-process'):
            self.assertFalse(nzb.busy('10'))
            self.assertEqual(workflow.dispatch_owner('10')['phase'], 'accepted')
        with self.assertRaises(RuntimeError):
            nzb.complete(Mock(side_effect=RuntimeError))(app.NZB_QUEUE, self.item, {'status':False})
        self.assertFalse(nzb.busy('10'))
        self.assertEqual(workflow.dispatch_owner('10')['phase'], 'review')

    def test_native_hooks_are_checked_and_idempotent(self):
        root = Path('/app/mylar3/mylar')
        if not root.exists(): root = Path('/tmp/mylar-workflow-native/mylar')
        if not root.exists(): self.skipTest('Native fixture unavailable')
        for name, patcher in [('queues/nzb.py', patch_workflow.nzb_queue), ('process.py', patch_workflow.processing)]:
            source = patcher((root/name).read_text())
            self.assertEqual(patcher(source), source)
            ast.parse(source)
        changed = patch_workflow.processing((root/'process.py').read_text())
        self.assertLess(changed.index("workflow.release_failed(failchk[0]['issueid'])"), changed.index('qt = qq.queueit('))
        with self.assertRaises(ValueError): patch_workflow.nzb_queue('def changed():pass')
        with self.assertRaises(ValueError): patch_workflow.processing('def changed():pass')

    def test_actual_native_cdh_moves_poll_to_pending_processing(self):
        root = Path('/app/mylar3/mylar')
        if not root.exists(): root = Path('/tmp/mylar-workflow-native/mylar')
        if not root.exists(): self.skipTest('Native fixture unavailable')
        source = patch_workflow.nzb_queue((root/'queues/nzb.py').read_text())
        fn = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name=='cdh_monitor')
        namespace = {'mylar':app, 'workflow_nzb':nzb, 'logger':Mock(), 'time':Mock(), 'Path':Path, 'helpers':Mock()}
        exec(compile(ast.Module(body=[fn],type_ignores=[]), 'native-cdh', 'exec'), namespace)
        app.NZB_QUEUE.put(self.item);nzb.take(app.NZB_QUEUE)
        result = dict(self.item,status=True,failed=False,name='fixture.cbz',location='/fixture',apicall=True,download_info={})
        namespace['cdh_monitor'](app.NZB_QUEUE,self.item,result)
        self.assertFalse(nzb.busy('10'))
        self.assertEqual(app.PP_QUEUE.get()['issueid'], '10')
        self.assertEqual(workflow.dispatch_owner('10')['phase'], 'accepted')


if __name__=='__main__': unittest.main()
