"""Actual native preservation and at-most-once combined-pass controls."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import combined_publication as combined
import publication_native as native
import publication_guard as guard
import test_publication_maintenance as fixtures
from patch_combined_publication import api


@unittest.skipUnless((Path(fixtures.native_cases.fixtures.TOOL_ROOT)/'lib/archive_backend.py').is_file(),
                     'offline native archive verifier required')
class CombinedTests(unittest.TestCase):
    connection = fixtures.PreservedSupplementTests.connection
    call = fixtures.PreservedSupplementTests.call
    bootstrap = fixtures.PreservedSupplementTests.bootstrap
    prepare = fixtures.PreservedSupplementTests.prepare
    registered = fixtures.PreservedSupplementTests.registered

    def setUp(self):
        fixtures.PreservedSupplementTests.setUp(self)
        self.request['sha256'] = self.before
        self.info.update(self.request)
        self.value = dict(naming=self.request, policy={}, manifest='b'*64)
        self.mylar.combined_publication = combined
        self.context = patch.dict(sys.modules, {'mylar.combined_publication': combined})
        self.context.start()
        self.addCleanup(self.context.stop)

    def admitted(self):
        return combined.prepare(self.value)

    def move(self, admitted):
        return dict(version=1, binding=admitted['binding'], destination=str(self.target),
                    sha256=self.before, bookid='moved-book', hash='reader-hash', pages=1,
                    libraryid='library', seriesid='series')

    def test_native_pair_prepare_and_rename_keep_original_bytes_until_reader_move(self):
        first = self.admitted()
        self.assertEqual(first['phase'], 'prepared')
        folder = self.writer.root/'combined-publication-v1'/first['token']
        for name in ('original', 'restore'):
            self.assertEqual(guard.file_hash(folder/(name+'.cbz'))[1], self.before)
        renamed = combined.rename(first['token'])
        self.assertEqual(renamed['phase'], 'renamed')
        self.assertEqual(guard.file_hash(self.target)[1], self.before)
        self.assertFalse(self.source.exists())
        with self.assertRaises(native.Review):
            combined.metadata(first['token'], None)
        self.assertTrue((folder/'restore.cbz').exists())

    def test_exact_reader_move_precedes_verified_unchanged_metadata(self):
        first = self.admitted()
        combined.rename(first['token'])
        result = combined.metadata(first['token'], self.move(first))
        self.assertEqual(result['phase'], 'complete')
        self.assertEqual((result['before'], result['after']), (self.before, self.before))
        self.assertEqual(combined.status(first['token']), result)
        self.assertEqual(combined.metadata(first['token'], None), result)

    def test_prepared_pair_policy_and_owner_drift_never_grant_rename_rights(self):
        first = self.admitted()
        folder = self.writer.root/'combined-publication-v1'/first['token']
        path = folder/'receipt.json'
        original = guard.private_json(path)
        changed = dict(original, policy={'AgeRating': 'Teen'})
        path.write_text(json.dumps(changed))
        with self.assertRaises(native.Review):
            combined.rename(first['token'])
        self.assertTrue(self.source.exists())
        self.assertFalse(self.writer.fenced(release=True))

    def test_lost_rename_ack_reconciles_closed_witness_without_second_move(self):
        first = self.admitted()
        actual = combined.rename_closed
        with patch.object(combined, 'rename_closed', side_effect=OSError('lost local acknowledgement')):
            with self.assertRaises(native.Review):
                combined.rename(first['token'])
        with patch.object(combined, 'rename_closed', wraps=actual), patch.object(
                self.mylar.release_naming, 'rename', side_effect=AssertionError('No replay')):
            self.assertEqual(combined.status(first['token'])['phase'], 'renamed')

    def test_missing_closed_tagging_seam_retains_uncertainty_and_pair(self):
        self.value['policy'] = {'AgeRating': 'Teen'}
        first = self.admitted()
        combined.rename(first['token'])
        with patch.object(self.mylar.publication_transaction,'closed_supplement',None):
            with self.assertRaises(native.Review):
                combined.metadata(first['token'], self.move(first))
        self.assertNotEqual(guard.file_hash(self.target)[1], self.before)
        with patch.object(self.mylar.tagger_supplement, 'apply_preserved', side_effect=AssertionError('No replay')):
            result=combined.status(first['token'])
            self.assertEqual(result['phase'],'complete')
            self.assertNotEqual(result['before'],result['after'])
        self.assertTrue((self.writer.root/'combined-publication-v1'/first['token']/'original.cbz').exists())

    def test_positive_root_metadata_lineage_preserves_pair_and_current_payload(self):
        self.value['policy']={'AgeRating':'Teen'}
        first=self.admitted();combined.rename(first['token'])
        result=combined.metadata(first['token'],self.move(first))
        self.assertEqual(result['phase'],'complete');self.assertNotEqual(result['before'],result['after'])
        self.assertEqual(combined.status(first['token']),result)
        folder=self.writer.root/'combined-publication-v1'/first['token']
        self.assertEqual(guard.file_hash(folder/'restore.cbz')[1],self.before)
        self.assertFalse(self.writer.fenced(tagger=True));self.assertFalse(self.writer.fenced(release=True))

    def test_already_named_publication_still_requires_reader_proof_before_metadata(self):
        self.value['naming']=dict(self.request,target=self.source.name)
        first=self.admitted();combined.rename(first['token'])
        move=dict(self.move(first),destination=str(self.source))
        with self.assertRaises(native.Review):combined.metadata(first['token'],None)
        self.assertEqual(combined.metadata(first['token'],move)['phase'],'complete')
        self.assertTrue(self.source.exists());self.assertFalse(self.target.exists())

    def test_lost_metadata_completion_reconciles_closed_tagging_without_old_rename_ack_or_replay(self):
        self.value['policy']={'AgeRating':'Teen'}
        first=self.admitted();combined.rename(first['token'])
        actual=combined.save
        def lost(folder,job,**kwargs):
            if job['phase']=='complete':raise OSError('lost completion acknowledgement')
            return actual(folder,job,**kwargs)
        with patch.object(combined,'save',side_effect=lost),self.assertRaises(native.Review):
            combined.metadata(first['token'],self.move(first))
        self.assertNotEqual(guard.file_hash(self.target)[1],self.before)
        with (patch.object(self.mylar.tagger_supplement,'apply_preserved',side_effect=AssertionError('No metadata replay')),
              patch.object(self.mylar.publication_rename,'terminal',side_effect=AssertionError('No old-hash acknowledgement'))):
            result=combined.status(first['token'])
            self.assertEqual(result['phase'],'complete')
            self.assertEqual(combined.status(first['token']),result)
        self.assertTrue((self.writer.root/'combined-publication-v1'/first['token']/'restore.cbz').exists())

    def complete(self,policy):
        self.value['policy']=policy
        first=self.admitted();combined.rename(first['token'])
        combined.metadata(first['token'],self.move(first))
        return first,self.writer.root/'combined-publication-v1'/first['token']

    def test_combined_receipt_replacement_during_final_source_read_cannot_get_complete_ack(self):
        first,folder=self.complete({'AgeRating':'Teen'});actual=native.require;changed=False
        def replacement(path,*args,**kwargs):
            nonlocal changed
            result=actual(path,*args,**kwargs)
            if Path(path)==self.target and not changed:
                changed=True;job=guard.private_json(folder/'receipt.json');job['review']='new independent review'
                (folder/'receipt.json').write_text(json.dumps(job))
            return result
        with patch.object(native,'require',side_effect=replacement),self.assertRaises(native.Review):combined.status(first['token'])
        self.assertEqual(guard.private_json(folder/'receipt.json')['review'],'new independent review')
        self.assertTrue((folder/'restore.cbz').exists())

    def test_closed_metadata_witness_replacement_during_final_source_read_is_retained(self):
        first,folder=self.complete({'AgeRating':'Teen'});actual=native.require;changed=False
        job=guard.private_json(folder/'receipt.json')
        witness=self.writer.root/'tagger-completed-v1'/(job['metadata_token']+'.json')
        def replacement(path,*args,**kwargs):
            nonlocal changed
            result=actual(path,*args,**kwargs)
            if Path(path)==self.target and not changed:changed=True;witness.write_text('{}')
            return result
        with patch.object(native,'require',side_effect=replacement),self.assertRaises(native.Review):combined.status(first['token'])
        self.assertEqual(witness.read_text(),'{}');self.assertTrue((folder/'original.cbz').exists())

    def test_historical_rename_witness_replacement_during_final_source_read_is_retained(self):
        first,folder=self.complete({'AgeRating':'Teen'});actual=native.require;changed=False
        job=guard.private_json(folder/'receipt.json')
        witness=self.writer.root/'release-completed-v1'/(job['rename']['token']+'.json')
        def replacement(path,*args,**kwargs):
            nonlocal changed
            result=actual(path,*args,**kwargs)
            if Path(path)==self.target and not changed:changed=True;witness.write_text('{}')
            return result
        with patch.object(native,'require',side_effect=replacement),self.assertRaises(native.Review):combined.status(first['token'])
        self.assertEqual(witness.read_text(),'{}');self.assertTrue((folder/'restore.cbz').exists())

    def test_unchanged_final_source_read_rechecks_original_pair(self):
        first,folder=self.complete({});actual=combined.current;changed=False
        def replacement(*args,**kwargs):
            nonlocal changed
            result=actual(*args,**kwargs)
            if not changed:changed=True;(folder/'original.cbz').write_bytes(b'replaced retained archive')
            return result
        with patch.object(combined,'current',side_effect=replacement),self.assertRaises(native.Review):combined.status(first['token'])
        self.assertTrue((folder/'restore.cbz').exists());self.assertEqual(guard.file_hash(self.target)[1],self.before)

    def test_lost_unchanged_ack_uses_exact_witness_without_running_supplement_again(self):
        first=self.admitted();combined.rename(first['token']);actual=combined.save
        def lost(folder,job,**kwargs):
            if job['phase']=='complete':raise OSError('lost unchanged completion')
            return actual(folder,job,**kwargs)
        with patch.object(combined,'save',side_effect=lost),self.assertRaises(native.Review):combined.metadata(first['token'],self.move(first))
        with patch.object(self.mylar.tagger_supplement,'apply_preserved',side_effect=AssertionError('No replay')):
            self.assertEqual(combined.status(first['token'])['phase'],'complete')

    def test_rename_callback_cannot_replace_native_combined_receipt(self):
        first=self.admitted();folder=self.writer.root/'combined-publication-v1'/first['token']
        naming=self.mylar.release_naming;actual=naming.rename
        def replacement(request):
            result=actual(request);job=guard.private_json(folder/'receipt.json')
            job['review']='new independent review';combined.save(folder,job)
            return result
        with patch.object(naming,'rename',side_effect=replacement),self.assertRaises(native.Review):
            combined.rename(first['token'])
        retained=guard.private_json(folder/'receipt.json')
        self.assertEqual(retained['phase'],'rename-uncertain');self.assertEqual(retained['review'],'new independent review')
        self.assertTrue((folder/'original.cbz').exists())

    def test_renamed_ack_rechecks_closed_witness_after_current_source_observation(self):
        first=self.admitted();combined.rename(first['token']);actual=combined.current
        folder=self.writer.root/'combined-publication-v1'/first['token'];job=guard.private_json(folder/'receipt.json')
        witness=self.writer.root/'release-completed-v1'/(job['rename']['token']+'.json')
        def replacement(*args,**kwargs):
            result=actual(*args,**kwargs);witness.write_text('{}');return result
        with patch.object(combined,'current',side_effect=replacement),self.assertRaises(native.Review):
            combined.status(first['token'])
        self.assertTrue((folder/'restore.cbz').exists())

    def test_repeated_preparation_rechecks_current_source_without_new_copies(self):
        first=self.admitted();folder=self.writer.root/'combined-publication-v1'/first['token']
        before=guard.file_hash(folder/'original.cbz');self.source.write_bytes(b'foreign source')
        with self.assertRaises(native.Review):self.admitted()
        self.assertEqual(guard.file_hash(folder/'original.cbz'),before)


class EndpointTests(unittest.TestCase):
    def test_primary_post_exact_envelope_and_sanitized_review(self):
        source = "class Api:\n    allowed = ['getVersion', 'checkGithub']\n    def _getVersion(self, **kwargs): pass\n"
        patched = api(source)
        self.assertEqual(api(patched), patched)
        runtime = SimpleNamespace(CONFIG=SimpleNamespace(API_ENABLED=True, API_KEY='p'*32))
        request = SimpleNamespace(method='POST')
        namespace = dict(mylar=runtime, cherrypy=SimpleNamespace(request=request))
        exec(compile(patched, '<fixture>', 'exec'), namespace)
        endpoint = namespace['Api']()
        endpoint.apikey = 'p'*32
        endpoint.apitype = 'normal'
        endpoint._failureResponse = lambda reason:dict(success=False, reason=reason)
        endpoint._successResponse = lambda data:dict(success=True, data=data)
        function = Mock(side_effect=native.Review('/private/path secret'))
        with patch.dict(sys.modules, {'mylar': SimpleNamespace(combined_publication=SimpleNamespace(execute=function),
                                                             publication_native=native, publication_guard=guard)}):
            endpoint._combinedPublication(request='{}')
            self.assertEqual(endpoint.data['reason'], 'Combined publication requires review; originals retained')
            request.method = 'GET'
            endpoint._combinedPublication(request='{}')
            self.assertEqual(function.call_count, 1)

    def test_boolean_protocol_and_extra_fields_are_rejected_before_any_operation(self):
        for value in (dict(version=True, action='status', arguments={'token':'a'*64}),
                      dict(version=1, action='status', arguments={'token':'a'*64}, waive=True)):
            with self.assertRaises(ValueError):
                combined.execute(json.dumps(value))


    def test_bounded_unique_finite_protocol_rejects_without_native_operations(self):
        values = ['{"version":1,"version":1,"action":"status","arguments":{"token":"a"}}',
                  '{"version":1,"action":"status","arguments":{"token":"a","token":"b"}}',
                  '['*1000+']'*1000, '{',
                  '{"version":1,"action":"status","arguments":{"token":NaN}}',
                  '{"version":1,"action":"status","arguments":{"token":1.5}}',
                  '{"version":1,"action":"status","arguments":{"token":'+('9'*1000)+'}}']
        with patch.object(combined, 'status', side_effect=AssertionError('No native admission')):
            for value in values:
                with self.subTest(value=value[:80]), self.assertRaises(ValueError):
                    combined.execute(value)

    def test_structural_characters_inside_token_do_not_change_nesting(self):
        token = 'quoted"['*40
        with patch.object(combined, 'status', return_value={'held':True}) as status:
            self.assertEqual(combined.execute(json.dumps(dict(version=1, action='status',
                            arguments={'token':token}))), {'held':True})
            status.assert_called_once_with(token)

    def test_checked_upgraded_endpoint_refuses_changed_method(self):
        source = "class Api:\n    allowed = ['getVersion', 'checkGithub']\n    def _getVersion(self, **kwargs): pass\n"
        upgraded = api(api(source))
        with self.assertRaises(ValueError):
            api(upgraded.replace("set(kwargs) != {'request'}", "False"))
        self.assertEqual(upgraded.count('def _combinedPublication'), 1)

    def test_fresh_and_upgraded_routes_sanitize_malformed_and_unavailable_evidence(self):
        source="class Api:\n    allowed = ['getVersion', 'checkGithub']\n    def _getVersion(self, **kwargs): pass\n"
        for installed in (api(source),api(api(source))):
            runtime=SimpleNamespace(CONFIG=SimpleNamespace(API_ENABLED=True,API_KEY='p'*32))
            namespace=dict(mylar=runtime,cherrypy=SimpleNamespace(request=SimpleNamespace(method='POST')))
            exec(compile(installed,'<checked-route>','exec'),namespace)
            endpoint=namespace['Api']();endpoint.apikey='p'*32;endpoint.apitype='normal'
            endpoint._failureResponse=lambda reason:dict(success=False,reason=reason)
            endpoint._successResponse=lambda data:dict(success=True,data=data)
            with patch.dict(sys.modules,{'mylar':SimpleNamespace(combined_publication=combined,
                                          publication_native=native,publication_guard=guard)}):
                for raw in ('{"version":1,"version":1}', '['*1000+']'*1000, '{'):
                    endpoint._combinedPublication(request=raw)
                    self.assertEqual(endpoint.data,dict(success=False,
                        reason='Combined publication request or evidence unavailable'))
                with patch.object(combined,'execute',side_effect=guard.Unavailable('/private secret')):
                    endpoint._combinedPublication(request='{}')
                    self.assertEqual(endpoint.data['reason'],'Combined publication request or evidence unavailable')


if __name__ == '__main__':
    unittest.main()
