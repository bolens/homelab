"""Native private original retirement and non-replaying historical controls."""
import inspect
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import combined_cleanup as cleanup
import combined_publication as combined
import publication_guard as guard
import publication_native as native
import test_combined_publication as fixtures


@unittest.skipUnless((Path(fixtures.fixtures.native_cases.fixtures.TOOL_ROOT)/'lib/archive_backend.py').is_file(),
                     'offline native archive verifier required')
class CleanupTests(unittest.TestCase):
    connection=fixtures.CombinedTests.connection
    call=fixtures.CombinedTests.call
    bootstrap=fixtures.CombinedTests.bootstrap
    prepare=fixtures.CombinedTests.prepare
    registered=fixtures.CombinedTests.registered
    admitted=fixtures.CombinedTests.admitted
    move=fixtures.CombinedTests.move
    complete=fixtures.CombinedTests.complete

    def setUp(self):
        fixtures.CombinedTests.setUp(self)
        self.mylar.combined_cleanup=cleanup
        context=patch.dict(sys.modules,{'mylar.combined_cleanup':cleanup})
        context.start();self.addCleanup(context.stop)

    def accepted(self,policy=None):
        first,folder=self.complete(policy or {})
        ack=combined.status(first['token']);job=guard.private_json(folder/'receipt.json')
        request=dict(version=1,combined_token=first['token'],binding=ack['binding'],lineage=ack['lineage'],
                     reader=dict(job['reader_move'],sha256=ack['after'],hash='final-reader-hash'))
        return folder,ack,request

    def test_verified_unchanged_pair_is_retired_once_and_terminal_replay_is_readonly(self):
        folder,ack,request=self.accepted()
        result=cleanup.clean(request)
        self.assertEqual(result['phase'],'complete')
        self.assertFalse((folder/'original.cbz').exists());self.assertFalse((folder/'restore.cbz').exists())
        self.assertEqual(guard.file_hash(self.target)[1],ack['after'])
        closed=combined.status(request['combined_token'])
        self.assertEqual(closed['cleanup']['token'],result['token'])
        self.assertEqual(closed['after'],ack['after'])
        with patch.object(cleanup.Cleanup,'unlink',side_effect=AssertionError('No replay')):
            self.assertEqual(cleanup.clean(request),result)

    def test_metadata_receipt_remains_verifiable_after_exact_pair_retirement(self):
        folder,ack,request=self.accepted({'AgeRating':'Teen'})
        result=cleanup.clean(request)
        with self.mylar.native_writers.operation() as writer:
            closed=self.mylar.publication_transaction.closed_retired_supplement(writer,
                cleanup_token=result['token'],source=self.target,owner=ack['owner'],payload=ack['payload'],
                census=ack['census'],lineage=ack['lineage'])
            self.assertEqual(closed['after'],ack['after']);self.assertEqual(closed['before'],ack['before'])
        self.assertFalse((folder/'original.cbz').exists());self.assertNotEqual(ack['before'],ack['after'])

    def test_missing_final_reader_or_changed_lineage_keeps_both_copies(self):
        folder,_,request=self.accepted();request['reader']['sha256']='0'*64
        with self.assertRaises(native.Review):cleanup.clean(request)
        self.assertTrue((folder/'original.cbz').exists());self.assertTrue((folder/'restore.cbz').exists())

    def test_partial_delete_directory_sync_failure_keeps_shared_hold_without_retry(self):
        folder,_,request=self.accepted();actual=cleanup.sync
        def failure(path):
            if Path(path)==folder:raise OSError('uncertain private directory sync')
            return actual(path)
        with patch.object(cleanup,'sync',side_effect=failure),self.assertRaises(native.Review):cleanup.clean(request)
        self.assertFalse((folder/'original.cbz').exists());self.assertTrue((folder/'restore.cbz').exists())
        self.assertTrue((self.writer.root/self.mylar.publication_transaction.NAME).exists())
        with self.assertRaises(native.Review):cleanup.clean(request)
        self.assertTrue((folder/'restore.cbz').exists())

    def test_replaced_terminal_without_independent_workflow_binding_is_retained(self):
        folder,ack,request=self.accepted();result=cleanup.clean(request)
        path=self.writer.root/'combined-cleanup-v1'/(result['token']+'.json')
        value=guard.private_json(path);value['request']['reader']['hash']='invented proof'
        self.mylar.publication_transaction._write(path,value,exclusive=False)
        with self.mylar.native_writers.operation() as writer,self.assertRaises(guard.Unavailable):
            cleanup.retired_supplement(writer,cleanup_token=result['token'],source=self.target,
                owner=ack['owner'],payload=ack['payload'],census=ack['census'],lineage=ack['lineage'])
        self.assertFalse((folder/'restore.cbz').exists())

    def test_final_retired_admission_source_replacement_cannot_get_acknowledgment(self):
        _,ack,request=self.accepted();result=cleanup.clean(request)
        actual=self.mylar.native_writers.admission;direct=0
        def replacement(writer,**kwargs):
            nonlocal direct
            value=actual(writer,**kwargs)
            if any(frame.function=='retired_supplement' and frame.code_context
                   and frame.code_context[0].strip()=='writers.admission(writer)' for frame in inspect.stack()):
                direct+=1
                if direct==2:self.target.write_bytes(b'new foreign current publication')
            return value
        with self.mylar.native_writers.operation() as writer:
            with patch.object(self.mylar.native_writers,'admission',side_effect=replacement),self.assertRaises(guard.Unavailable):
                cleanup.retired_supplement(writer,cleanup_token=result['token'],source=self.target,
                    owner=ack['owner'],payload=ack['payload'],census=ack['census'],lineage=ack['lineage'])
        self.assertEqual(direct,2)
        self.assertEqual(self.target.read_bytes(),b'new foreign current publication')

    def test_lost_marker_unlink_ack_restores_shared_hold(self):
        _,_,request=self.accepted();actual=Path.unlink
        def lost(path,*args,**kwargs):
            answer=actual(path,*args,**kwargs)
            if path==self.writer.root/self.mylar.publication_transaction.NAME:raise OSError('lost marker unlink acknowledgment')
            return answer
        with patch.object(Path,'unlink',lost),self.assertRaises(native.Review):cleanup.clean(request)
        self.assertTrue((self.writer.root/self.mylar.publication_transaction.NAME).exists())
        with self.assertRaises(native.Review):cleanup.clean(request)

    def test_public_capability_immutable_source_and_phase_projection_cannot_be_replaced(self):
        folder,_,request=self.accepted()
        with self.mylar.native_writers.operation() as writer:
            _,job=combined.read(writer,request['combined_token'])
            value=cleanup.snapshot(writer,folder,job,request);capability=cleanup.Cleanup(writer,value)
            with capability.owned():
                capability.value['removed']=['original']
                with self.assertRaises(guard.Unavailable):capability.unlink('restore')
        self.assertTrue((folder/'original.cbz').exists());self.assertTrue((folder/'restore.cbz').exists())

    def test_passive_cleanup_link_replacement_cannot_acknowledge_pair_absence(self):
        _,_,request=self.accepted();cleanup.clean(request)
        link=self.writer.root/'combined-cleanup-links-v1'/(request['combined_token']+'.json')
        value=guard.private_json(link);value['cleanup_token']='0'*64
        self.mylar.publication_transaction._write(link,value,exclusive=False)
        with self.assertRaises(native.Review):combined.status(request['combined_token'])

    def test_serialized_snapshot_cannot_create_new_cleanup_permission(self):
        folder,_,request=self.accepted()
        with self.mylar.native_writers.operation() as writer:
            _,job=combined.read(writer,request['combined_token'])
            value=cleanup.snapshot(writer,folder,job,request)
            value['source']['signature'][2]+=1
            with self.assertRaises(guard.Unavailable):cleanup.Cleanup(writer,value)
        self.assertTrue((folder/'original.cbz').exists());self.assertTrue((folder/'restore.cbz').exists())
        self.assertFalse((self.writer.root/self.mylar.publication_transaction.NAME).exists())

    def test_last_private_history_read_cannot_hide_changed_current_publication(self):
        folder,ack,request=self.accepted();result=cleanup.clean(request)
        actual=cleanup.retained;count=0
        def replacement(value):
            nonlocal count
            answer=actual(value)
            if value['path']==str(folder/'unchanged-terminal.json'):
                count+=1
                if count==2:self.target.write_bytes(b'foreign source during final retained history read')
            return answer
        with self.mylar.native_writers.operation() as writer:
            with patch.object(cleanup,'retained',side_effect=replacement),self.assertRaises(guard.Unavailable):
                cleanup.retired_supplement(writer,cleanup_token=result['token'],source=self.target,
                    owner=ack['owner'],payload=ack['payload'],census=ack['census'],lineage=ack['lineage'])
        self.assertEqual(count,2)

    def test_checked_cleanup_protocol_returns_fresh_retired_combined_lineage(self):
        _,ack,request=self.accepted({'AgeRating':'Teen'})
        answer=combined.execute(json.dumps(dict(version=1,action='cleanup',arguments=request)))
        self.assertEqual(answer['cleanup']['phase'],'complete');self.assertEqual(answer['cleanup']['version'],1)
        self.assertEqual(answer['lineage'],ack['lineage']);self.assertEqual(answer['after'],ack['after'])
        self.assertEqual(combined.status(request['combined_token']),answer)

    def test_last_marker_directory_fsync_failure_restores_exclusive_hold(self):
        _,_,request=self.accepted();actual=cleanup.sync
        def failure(path):
            marker=self.writer.root/self.mylar.publication_transaction.NAME
            if Path(path)==self.writer.root and not marker.exists() and not self.writer.fenced(release=True):
                roots=self.writer.root/'combined-cleanup-v1'
                if roots.exists() and any(guard.private_json(item).get('phase')=='complete' for item in roots.glob('*.json')):
                    raise OSError('last native marker directory fsync failed')
            return actual(path)
        with patch.object(cleanup,'sync',side_effect=failure),self.assertRaises(native.Review):cleanup.clean(request)
        self.assertTrue((self.writer.root/self.mylar.publication_transaction.NAME).exists())
        with self.assertRaises(native.Review):combined.status(request['combined_token'])


if __name__=='__main__':unittest.main()
