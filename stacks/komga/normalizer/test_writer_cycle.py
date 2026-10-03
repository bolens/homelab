"""Normalizer fences span asynchronous publication and exceptions."""
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from media_writer import Writer, Busy
from writer_cycle import cycle


class CycleTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.state=self.root/'worker';self.state.mkdir()
        self.jobs=self.state/'jobs';self.jobs.mkdir()
        self.owner=Writer(self.root/'shared',create=True)
        self.worker=SimpleNamespace(config={'writer_state':str(self.owner.root)},jobs=self.jobs,state=self.state,cycle=Mock())
        self.maintenance=SimpleNamespace(cycle=Mock())

    def test_naming_reconciles_native_fence_before_ordinary_writer_admission(self):
        with self.owner.hold(allow_release_pending=True):self.owner.mark_release_pending()
        def native_recovery():
            # Simulate the remote native owner responding to releaseNamingStatus.
            with self.owner.hold(allow_release_pending=True):self.owner.clear_release_pending()
        self.worker.naming=SimpleNamespace(reconcile=Mock(side_effect=native_recovery),tick=Mock())
        self.assertTrue(cycle(self.worker));self.assertFalse(self.owner.fenced(release=True))
        self.worker.naming.reconcile.assert_called_once();self.worker.cycle.assert_called_once()
        self.worker.naming.tick.assert_called_once()

    def test_whole_cycle_is_owned_and_clean_completion_unfences(self):
        def check():
            self.assertTrue(self.owner.fenced())
            self.assertTrue(self.owner.local[1].allow_pending)
        self.worker.cycle.side_effect=check;self.maintenance.cycle.side_effect=check
        self.assertTrue(cycle(self.worker,self.maintenance));self.assertFalse(self.owner.fenced())

    def test_submitted_or_uncertain_upgrade_blocks_mylar_until_verified_done(self):
        folder=self.jobs/'job';folder.mkdir();receipt=folder/'receipt.json'
        for phase in ('submitted','refresh'):
            receipt.write_text(json.dumps({'phase':phase}));cycle(self.worker)
            with self.assertRaises(Busy):
                with self.owner.hold(timeout=0):pass
        receipt.write_text(json.dumps({'phase':'done'}));cycle(self.worker)
        with self.owner.hold(timeout=0):pass

    def test_exception_keeps_fence_for_recovery(self):
        self.worker.cycle.side_effect=RuntimeError('fixture')
        with self.assertRaises(RuntimeError):cycle(self.worker)
        self.assertTrue(self.owner.fenced())
        self.worker.cycle.side_effect=None;cycle(self.worker)
        self.assertFalse(self.owner.fenced())

    def test_legacy_without_setting_retains_existing_behavior(self):
        self.worker.config={};self.assertTrue(cycle(self.worker,self.maintenance))
        self.worker.cycle.assert_called_once();self.maintenance.cycle.assert_called_once()
        self.assertFalse(self.owner.fenced())

    def test_busy_native_writer_skips_all_work_and_preserves_errors(self):
        script="from media_writer import Writer;import sys,time\nwith Writer(sys.argv[1]).hold():\n print('locked',flush=True);time.sleep(60)"
        self.worker.scan_batch = Mock()
        child=subprocess.Popen([sys.executable,'-c',script,str(self.owner.root)],
              env=dict(os.environ,PYTHONPATH=str(Path(__file__).parent)),stdout=subprocess.PIPE,text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(),'locked')
            for name in ('status.json','maintenance-status.json','reader-scan-status.json'):
                (self.state/name).write_text(json.dumps({'errors':['existing'],'checked_at':1,'pending':2}))
            self.assertFalse(cycle(self.worker,self.maintenance))
            self.worker.cycle.assert_not_called();self.maintenance.cycle.assert_not_called()
            self.worker.scan_batch.collect.assert_not_called();self.worker.scan_batch.dispatch.assert_not_called()
            for name in ('status.json','maintenance-status.json','reader-scan-status.json'):
                value=json.loads((self.state/name).read_text())
                self.assertEqual(value['errors'],['existing']);self.assertEqual(value['pending'],2)
                self.assertGreater(value['checked_at'],1)
                self.assertEqual(value['state'],'waiting for media writer')
        finally:child.kill();child.wait(5);child.stdout.close()

    def test_missing_or_replaced_recovery_directory_never_clears_fence(self):
        self.worker.cycle.side_effect=RuntimeError('fixture')
        with self.assertRaises(RuntimeError):cycle(self.worker)
        self.worker.cycle.reset_mock();self.worker.cycle.side_effect=None
        self.jobs.rename(self.state/'old-jobs')
        with self.assertRaises(FileNotFoundError):cycle(self.worker)
        self.jobs.mkdir()
        with self.assertRaises(ValueError):cycle(self.worker)
        self.worker.cycle.assert_not_called();self.assertTrue(self.owner.fenced())

    def test_notification_runs_after_release_and_retries_without_conversion(self):
        folder=self.jobs/'job';folder.mkdir();receipt=folder/'receipt.json'
        receipt.write_text(json.dumps({'phase':'done','mylar_refresh_pending':True}))
        def notify(job):
            self.assertFalse(self.owner.fenced())
            self.assertEqual(getattr(self.owner.local[1],'depth',0),0)
            with self.owner.hold(timeout=0):pass
            raise RuntimeError('API unavailable')
        self.worker.refresh_mylar=Mock(side_effect=notify)
        with self.assertRaises(RuntimeError):cycle(self.worker)
        self.assertTrue(json.loads(receipt.read_text())['mylar_refresh_pending'])
        self.worker.refresh_mylar.side_effect=None
        self.assertTrue(cycle(self.worker))
        self.assertNotIn('mylar_refresh_pending',json.loads(receipt.read_text()))

    def test_one_failed_notification_does_not_starve_later_receipts(self):
        receipts = []
        for name in ('first', 'second'):
            folder = self.jobs/name; folder.mkdir(); receipt = folder/'receipt.json'
            receipt.write_text(json.dumps({'phase':'done', 'mylar_refresh_pending':True, 'name':name}))
            receipts.append(receipt)
        def notify(job):
            if job['name'] == 'first': raise RuntimeError('unavailable')
        self.worker.refresh_mylar = Mock(side_effect=notify)
        with self.assertRaises(RuntimeError): cycle(self.worker)
        self.assertEqual(self.worker.refresh_mylar.call_count, 2)
        self.assertTrue(json.loads(receipts[0].read_text())['mylar_refresh_pending'])
        self.assertNotIn('mylar_refresh_pending', json.loads(receipts[1].read_text()))

    def test_reader_followup_runs_outside_writer_and_survives_failure(self):
        folder=self.jobs/'job';folder.mkdir();receipt=folder/'receipt.json'
        receipt.write_text(json.dumps({'phase':'done','mylar_tag_pending':True}))
        def refresh(job):
            self.assertFalse(self.owner.fenced())
            self.assertEqual(getattr(self.owner.local[1],'depth',0),0)
            raise RuntimeError('Reader unavailable')
        self.worker.refresh_tagged=Mock(side_effect=refresh)
        with self.assertRaises(RuntimeError):cycle(self.worker)
        self.assertTrue(json.loads(receipt.read_text())['mylar_tag_pending'])
        self.worker.refresh_tagged.side_effect=lambda job:job.pop('mylar_tag_pending')
        self.assertTrue(cycle(self.worker))
        self.assertNotIn('mylar_tag_pending',json.loads(receipt.read_text()))

    def test_reader_refresh_save_failure_replays_only_idempotent_notification(self):
        folder=self.jobs/'job';folder.mkdir();receipt=folder/'receipt.json'
        receipt.write_text(json.dumps({'phase':'done','mylar_tag_pending':True}))
        self.worker.refresh_tagged=Mock(side_effect=lambda job:job.pop('mylar_tag_pending'))
        with patch('normalize.save', side_effect=OSError('fixture write failure')):
            with self.assertRaises(RuntimeError):cycle(self.worker)
        self.assertTrue(json.loads(receipt.read_text())['mylar_tag_pending'])
        cycle(self.worker)
        self.assertEqual(self.worker.refresh_tagged.call_count, 2)
        self.assertNotIn('mylar_tag_pending', json.loads(receipt.read_text()))

    def test_tagger_crash_fence_blocks_even_worker_recovery(self):
        with self.owner.hold(allow_tagger_pending=True):self.owner.mark_tagger_pending()
        self.assertFalse(cycle(self.worker,self.maintenance))
        self.worker.cycle.assert_not_called();self.maintenance.cycle.assert_not_called()

    def test_scan_collects_under_lock_and_dispatches_after_release(self):
        def collect():
            self.assertEqual(self.owner.local[1].depth, 1)
            self.assertFalse(self.owner.fenced())
            return True
        def dispatch():
            self.assertEqual(self.owner.local[1].depth, 0)
            self.assertFalse(self.owner.fenced())
        self.worker.scan_batch = SimpleNamespace(collect=Mock(side_effect=collect), dispatch=Mock(side_effect=dispatch))
        self.assertTrue(cycle(self.worker))
        self.worker.scan_batch.dispatch.assert_called_once()

    def test_pending_conversion_allows_scanning_other_completed_paths(self):
        folder=self.jobs/'pending'; folder.mkdir()
        (folder/'receipt.json').write_text(json.dumps({'phase':'submitted'}))
        self.worker.scan_batch = Mock()
        self.assertTrue(cycle(self.worker))
        self.worker.scan_batch.collect.assert_called_once()
        self.worker.scan_batch.dispatch.assert_called_once()
        self.assertTrue(self.owner.fenced())

    def test_failed_scan_readiness_does_not_retain_media_fence(self):
        self.worker.scan_batch = SimpleNamespace(collect=Mock(return_value=False), dispatch=Mock())
        self.assertTrue(cycle(self.worker))
        self.worker.scan_batch.dispatch.assert_not_called()
        self.assertFalse(self.owner.fenced())

    def test_other_failed_notification_does_not_starve_ready_scan(self):
        folder=self.jobs/'done'; folder.mkdir()
        (folder/'receipt.json').write_text(json.dumps({'phase':'done','mylar_refresh_pending':True}))
        self.worker.refresh_mylar=Mock(side_effect=OSError('fixture'))
        self.worker.scan_batch=SimpleNamespace(collect=Mock(return_value=True),dispatch=Mock())
        with self.assertRaises(RuntimeError):cycle(self.worker)
        self.worker.scan_batch.dispatch.assert_called_once()
        self.assertFalse(self.owner.fenced())

    def test_missing_protocol_never_runs_writers(self):
        self.worker.config={'writer_state':str(self.root/'absent')}
        with self.assertRaises(FileNotFoundError):cycle(self.worker,self.maintenance)
        self.worker.cycle.assert_not_called();self.maintenance.cycle.assert_not_called()


if __name__=='__main__':unittest.main()
