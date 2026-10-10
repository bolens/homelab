"""Owning real SQLite/Writer/archive lineage controls, explicit host app fixtures.

Canonical installed-process proof remains a separate root image gate. These
source fixtures activate genuine native_writers over disposable initialized
state; upstream DB/PostProcessor/rename proposals are existing fixture adapters.
"""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import ordinary_import_observation as observation
import ordinary_import_history as history
import ordinary_import_continuity as continuity
import publication_guard as guard
import test_ordinary_import_continuity as fixtures


class Common:
    def installed_runtime(self):
        path=Path(__file__).with_name('native_writers.py')
        spec=importlib.util.spec_from_file_location('mylar.native_writers',path)
        runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)
        p=patch.dict(sys.modules,{'mylar.native_writers':runtime,'mylar.ordinary_import_observation':observation});p.start();self.addCleanup(p.stop)
        self.mylar.native_writers=runtime
        # Disposable fixture emulates already initialized native startup only.
        runtime._PUBLICATION=True;runtime._STARTUP_COMPLETE=True
        p=patch.object(observation,'ENABLED',True);p.start();self.addCleanup(p.stop)
        return runtime
    def build_request(self,target):
        original,attempt,ack=continuity._original(history,self.token)
        target_fact,_=history._file(target)
        with self.writer.hold():census,_=guard.registry_snapshot(self.root/'workflow.sqlite',self.writer.root/'publication-v1.json')
        return dict(version=1,nonce='9'*64,token=self.token,owner=self.owner,destination=str(target),
            attempt_sha256=hashlib.sha256(original['attempt'].encode()).hexdigest(),ack_sha256=hashlib.sha256(original['ack'].encode()).hexdigest(),
            target=target_fact,payload=attempt['payload'],census=census)
    def observe(self,target):return observation.observe(json.dumps(self.build_request(target)))


class Rename(Common,fixtures.Continuity):
    def setUp(self):super().setUp()
    def prepare(self):self.call_rename();self.installed_runtime()
    def test_genuine_rename_export_retains_original_ack_and_false_rights(self):
        self.prepare();result=self.observe(self.target);value=result.payload();result.close()
        self.assertEqual(value['token'],self.token);self.assertEqual(value['current_target']['signature'],history._file(self.target)[0]['signature'])
        self.assertTrue(all(v is False for v in value['rights'].values()))
        with history._database() as db:self.assertEqual(tuple(db.execute('SELECT attempt,ack FROM completions').fetchone()),self.original)
    def handler(self):
        path=Path(__file__).with_name('api.py');tree=ast.parse(path.read_text())
        original=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Api')
        body=[n for n in original.body if (isinstance(n,ast.FunctionDef) and n.name in ('_ordinaryImportObservation','_successResponse','_failureResponse')) or
            (isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='API_ERROR_CODE_DEFAULT' for x in n.targets))]
        fixture=ast.Module(body=[ast.ClassDef(name='Api',bases=[],keywords=[],body=body,decorator_list=[])],type_ignores=[]);ast.fix_missing_locations(fixture)
        web=SimpleNamespace(request=SimpleNamespace(method='POST'),response=SimpleNamespace(headers={}))
        namespace=dict(mylar=self.mylar,cherrypy=web,json=json)
        exec(compile(fixture,str(path),'exec'),namespace)
        handler=namespace['Api']();handler.headers='application/json';handler.apikey='q'*32;handler.apitype='normal';handler.data='OK'
        self.mylar.CONFIG.API_ENABLED=True;self.mylar.CONFIG.API_KEY='q'*32
        return handler,web
    def test_actual_retained_api_method_authentication_precedes_observation(self):
        self.prepare();handler,web=self.handler();handler.apikey='wrong'
        with patch.object(observation,'observe') as called:handler._ordinaryImportObservation(request='{}');called.assert_not_called()
        self.assertFalse(json.loads(handler.data)['success'])
        handler.apikey='q'*32;web.request.method='GET'
        with patch.object(observation,'observe') as called:handler._ordinaryImportObservation(request='{}');called.assert_not_called()
    def test_actual_retained_api_method_success_and_encoded_false_rights(self):
        self.prepare();handler,_=self.handler();handler._ordinaryImportObservation(request=json.dumps(self.build_request(self.target)))
        reply=json.loads(handler.data);self.assertTrue(reply['success']);self.assertEqual(reply['data']['token'],self.token)
        self.assertTrue(all(value is False for value in reply['data']['rights'].values()))
    def test_success_envelope_last_callback_target_drift_is_failure(self):
        self.prepare();handler,_=self.handler();real=handler._successResponse;fired=[]
        def late(value):answer=real(value);self.target.chmod(0o640);fired.append(True);return answer
        handler._successResponse=late;handler._ordinaryImportObservation(request=json.dumps(self.build_request(self.target)))
        self.assertTrue(fired);self.assertFalse(json.loads(handler.data)['success'])
    def test_success_envelope_payload_mutation_is_failure(self):
        self.prepare();handler,_=self.handler();real=handler._successResponse
        def late(value):value['rights']['cleanup']=True;return real(value)
        handler._successResponse=late;handler._ordinaryImportObservation(request=json.dumps(self.build_request(self.target)))
        self.assertFalse(json.loads(handler.data)['success'])
    def test_observation_close_is_one_use(self):
        self.prepare();result=self.observe(self.target);result.close()
        with self.assertRaises(ValueError):result.close()
    def test_no_saved_json_hydration(self):
        self.prepare();result=self.observe(self.target);json.loads(json.dumps(result.payload()));result.close()
        with self.assertRaises(ValueError):observation.Observation().payload()
    def test_wrong_original_ack_digest_is_held(self):
        self.prepare();request=self.build_request(self.target);request['ack_sha256']='a'*64
        with self.assertRaises(ValueError):observation.observe(json.dumps(request))
    def test_wrong_annual_release_owner_is_held(self):
        self.prepare();request=self.build_request(self.target);request['owner']=dict(request['owner'],table='annuals',releasecomicid='999999')
        with self.assertRaises(Exception):observation.observe(json.dumps(request))
    def test_duplicate_json_is_held(self):
        self.prepare();raw=json.dumps(self.build_request(self.target));raw='{"version":1,'+raw[1:]
        with self.assertRaises(Exception):observation.observe(raw)
    def test_last_export_callback_catalog_wal_is_held(self):
        self.prepare();real=continuity._observe;fired=[]
        def late(*args,**kwargs):
            result=real(*args,**kwargs);(self.root/'mylar.db-wal').write_bytes(b'foreign');fired.append(True);return result
        with patch.object(continuity,'_observe',late),self.assertRaises(Exception):self.observe(self.target)
        self.assertTrue(fired)
    def test_last_close_helper_metadata_change_is_held(self):
        self.prepare();result=self.observe(self.target);real=observation._close;fired=[]
        def late(frame):real(frame);self.target.chmod(0o640);fired.append(True)
        with patch.object(observation,'_close',late),self.assertRaises(ValueError):result.close()
        self.assertTrue(fired)
    def test_terminal_receipt_replacement_is_held(self):
        self.prepare();path=next((self.writer.root/'release-completed-v1').glob('*.json'));raw=path.read_bytes();path.unlink();path.write_bytes(raw);path.chmod(0o600)
        with self.assertRaises(Exception):self.observe(self.target)
    def test_first_source_read_later_history_mode_change_is_held(self):
        self.prepare();request=json.dumps(self.build_request(self.target));real=os.read;fired=[]
        def late(fd,size):
            answer=real(fd,size)
            if not fired:
                (self.root/'ordinary-import-v1.sqlite').chmod(0o640);fired.append(True)
            return answer
        with patch.object(observation.os,'read',late),self.assertRaises(Exception):observation.observe(request)
        self.assertTrue(fired)
    def test_initial_catalog_companion_cannot_be_removed_by_first_read(self):
        self.prepare();request=json.dumps(self.build_request(self.target));path=self.root/'mylar.db-wal';path.write_bytes(b'foreign')
        real=os.read;fired=[]
        def late(fd,size):
            answer=real(fd,size)
            if not fired:path.unlink();fired.append(True)
            return answer
        with patch.object(observation.os,'read',late),self.assertRaises(Exception):observation.observe(request)
        self.assertFalse(fired);self.assertTrue(path.exists())
    def test_writer_pending_is_held(self):
        self.prepare();(self.writer.root/'normalizer-v1.pending').write_bytes(b'foreign')
        with self.assertRaises(Exception):self.observe(self.target)
    def test_disabled_route_refuses_before_import_or_state(self):
        with patch.object(observation,'ENABLED',False),self.assertRaises(ValueError):observation.observe('{}')


class Metadata(Common,fixtures.Metadata):
    def test_genuine_preserved_metadata_export_retains_original_ack(self):
        self.apply();self.installed_runtime();result=self.observe(self.source);value=result.payload();result.close()
        self.assertEqual(value['owner'],self.owner);self.assertEqual(value['current_target']['sha256'],history._file(self.source)[0]['sha256'])
        with history._database() as db:self.assertEqual(tuple(db.execute('SELECT attempt,ack FROM completions').fetchone()),self.original_ack)


class Installer(unittest.TestCase):
    def original(self):
        import patch_ordinary_import_observation as installer
        source=Path(__file__).with_name('api.py').read_text()
        return source.replace(installer.METHOD,'').replace(", 'ordinaryImportObservation'",'')
    def test_exact_hook_idempotent_and_python310(self):
        import patch_ordinary_import_observation as installer
        original=self.original();answer=installer.patched_source(original)
        self.assertEqual(installer.patched_source(answer),answer);ast.parse(answer,feature_version=(3,10))
    def test_partial_or_changed_hook_is_held(self):
        import patch_ordinary_import_observation as installer
        answer=installer.patched_source(self.original())
        with self.assertRaises(ValueError):installer.patched_source(answer.replace(installer.METHOD,''))
        with self.assertRaises(ValueError):installer.patched_source(answer.replace('Exact observation POST required','Different'))
    def test_unknown_dispatcher_is_held(self):
        import patch_ordinary_import_observation as installer
        with self.assertRaises(ValueError):installer.patched_source(self.original().replace("'packCatalog'","'unknownCatalog'"))


def load_tests(loader,tests,pattern):return unittest.TestSuite(cls(name) for cls in (Rename,Metadata,Installer) for name in cls.__dict__ if name.startswith('test_'))
if __name__=='__main__':unittest.main()
