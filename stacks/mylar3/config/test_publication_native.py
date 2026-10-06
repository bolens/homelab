"""Native admission controls use genuine registry/catalog/archive fixtures."""
from pathlib import Path
import ast
import importlib.util
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from unittest.mock import Mock
from contextlib import contextmanager,closing
import zipfile

import publication_native as native
import publication_guard as guard
import publication_api as api
import test_publication_api as fixtures


class CandidateTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)

    def test_unique_nested_archive_and_direct_archive_agree(self):
        folder=self.root/'nested';folder.mkdir();source=folder/'input.cbz';source.write_bytes(b'fixture')
        self.assertEqual(native.candidate(self.root),source)
        self.assertEqual(native.candidate(source),source)

    def test_ambiguous_directory_never_selects_last_archive(self):
        for name in ('one.cbz','two.cbr'):(self.root/name).write_bytes(b'retained')
        with self.assertRaises(guard.Unavailable):native.candidate(self.root)
        self.assertEqual(len(list(self.root.iterdir())),2)

    def test_linked_directory_member_or_direct_archive_is_retained(self):
        source=self.root/'one.cbz';source.write_bytes(b'retained')
        link=self.root/'alias.cbz';link.symlink_to(source)
        for path in (self.root,link):
            with self.assertRaises(guard.Unavailable):native.candidate(path)
        self.assertTrue(link.is_symlink());self.assertEqual(source.read_bytes(),b'retained')

    def test_empty_missing_or_unsupported_candidate_is_refused(self):
        text=self.root/'notes.txt';text.write_text('retained')
        for path in (self.root,self.root/'missing',text):
            with self.assertRaises(guard.Unavailable):native.candidate(path)

    def test_unreadable_descendant_cannot_certify_unique_archive(self):
        (self.root/'visible.cbz').write_bytes(b'retained')
        def failed_walk(path,**kwargs):
            yield str(path),['unreadable'],['visible.cbz']
            kwargs['onerror'](PermissionError('isolated descendant error'))
        (self.root/'unreadable').mkdir()
        with patch.object(native.os,'walk',side_effect=failed_walk),self.assertRaises(guard.Unavailable):
            native.candidate(self.root)

    def test_pdf_sibling_or_nested_pdf_holds_before_native_last_hit_selection(self):
        (self.root/'visible.cbz').write_bytes(b'retained')
        folder=self.root/'nested';folder.mkdir();pdf=folder/'native-last-hit.pdf';pdf.write_bytes(b'retained PDF')
        with self.assertRaises(guard.Unavailable):native.candidate(self.root)
        self.assertEqual(pdf.read_bytes(),b'retained PDF')


class TerminalTests(unittest.TestCase):
    def test_review_bypasses_legacy_fallback_and_is_consumed_under_writer(self):
        import queue
        import processing_guard
        import pp_monitor
        import workflow_store
        held=[];mutate=Mock();events=[];state={}
        @contextmanager
        def operation():
            held.append(True)
            try:yield None
            finally:held.pop()
        class Store:
            def set(self,kind,key,value):state[(kind,key)]=value
        workflow=types.SimpleNamespace(store=lambda:Store(),emit=lambda *args,**kwargs:events.append(args))
        mylar=types.ModuleType('mylar');mylar.APILOCK=False
        mylar.native_writers=types.SimpleNamespace(operation=operation)
        mylar.pack_intake=types.SimpleNamespace(capture=lambda _:False)
        mylar.logger=Mock()
        obj=types.SimpleNamespace(queue=queue.Queue(),valreturn=[],nzb_name='retained fixture',
                                  nzb_folder='/private/fixture',issueid='123',comicid='456',ddl=True,
                                  download_info=dict(id='7'))
        @processing_guard.run
        @pp_monitor.observe
        def process(self):
            try:processing_guard.publication(self,'retained.cbz',issueid='123',comicid='456')
            except Exception:mutate()
            mutate()
        modules={'mylar':mylar,'mylar.media_writer':types.SimpleNamespace(Busy=RuntimeError),
                 'mylar.workflow':workflow,'mylar.workflow_store':workflow_store}
        with patch.dict(sys.modules,modules),patch.object(native,'require',side_effect=native.Review('verified-correction')):
            obj.queue.put=Mock(wraps=obj.queue.put,side_effect=lambda value:
                (self.assertTrue(held),queue.Queue.put(obj.queue,value))[1])
            process(obj)
        mutate.assert_not_called();self.assertFalse(mylar.APILOCK);self.assertEqual(held,[])
        self.assertEqual(obj.queue.get()[0]['mode'],'review')
        self.assertTrue(obj.valreturn[0]['retained'])
        self.assertEqual(state[('ddl_processing','7')]['phase'],'review')
        self.assertIn('source retained',events[-1][1])
        self.assertNotIn('finished',events[-1][1]);self.assertNotIn('raised an error',events[-1][1])

    def test_queued_handoff_refusal_precedes_pack_capture_and_processing(self):
        import queue
        import processing_guard
        mutate=Mock();capture=Mock(return_value=False)
        @contextmanager
        def operation():yield None
        mylar=types.ModuleType('mylar');mylar.APILOCK=False
        mylar.native_writers=types.SimpleNamespace(operation=operation)
        mylar.pack_intake=types.SimpleNamespace(capture=capture);mylar.logger=Mock()
        obj=types.SimpleNamespace(queue=queue.Queue(),valreturn=[],download_info={})
        wrapped=processing_guard.run(mutate)
        modules={'mylar':mylar,'mylar.media_writer':types.SimpleNamespace(Busy=RuntimeError)}
        with patch.dict(sys.modules,modules),patch.object(native,'resume_handoff',side_effect=native.Review('queued-import-handoff-changed')):
            wrapped(obj)
        capture.assert_not_called();mutate.assert_not_called()
        self.assertEqual(obj.queue.get()[0]['mode'],'review')
        self.assertIsNone(obj._publication_handoff);self.assertFalse(mylar.APILOCK)

    def test_bound_processing_refuses_payload_or_owner_substitution(self):
        import processing_guard
        obj=types.SimpleNamespace(valreturn=[],_publication_handoff=dict(payload='a'*64,owner={'issueid':'123'}))
        for result in (None,dict(inventory={'payload':'b'*64},owner={'issueid':'123'}),
                       dict(inventory={'payload':'a'*64},owner={'issueid':'999'})):
            with patch.object(native,'require',return_value=result),self.assertRaises(native.Review):
                processing_guard.publication(obj,'fixture',issueid='123')
        result=dict(inventory={'payload':'a'*64},owner={'issueid':'123'})
        with patch.object(native,'require',return_value=result):
            self.assertEqual(processing_guard.publication(obj,'fixture',issueid='123'),result)



@unittest.skipUnless((Path(fixtures.TOOL_ROOT)/'lib/archive_backend.py').is_file(),
                     'offline archive verifier required')
class AdmissionTests(unittest.TestCase):
    call=fixtures.NativeProtocolTests.call
    bootstrap=fixtures.NativeProtocolTests.bootstrap
    prepare=fixtures.NativeProtocolTests.prepare

    def setUp(self):
        fixtures.NativeProtocolTests.setUp(self)
        self.incoming=self.root/'incoming.cbz';shutil.copyfile(self.source,self.incoming)
        self.mylar=types.ModuleType('mylar')
        self.mylar.DATA_DIR=str(self.root)
        self.mylar.CONFIG=types.SimpleNamespace(DESTINATION_DIR=str(self.library))
        def admission(writer):
            if not writer.local[1].depth:raise guard.Unavailable('Writer required')
            guard.registry_snapshot(self.store.path,writer.root/'publication-v1.json')
            if any(writer.fenced(**args) for args in ({},{'tagger':True},{'release':True})):
                raise guard.Unavailable('Retained media fence')
        self.runtime=types.SimpleNamespace(publication_mode=lambda:True,active=lambda:True,
                                          owner=lambda:self.writer,admission=admission)
        self.mylar.native_writers=self.runtime
        context=patch.dict(sys.modules,{'mylar':self.mylar,'mylar.publication_api':api})
        context.start();self.addCleanup(context.stop)
        original_inventory=guard.inventory;original_controller=api.Controller
        def inventory(path,**kwargs):
            kwargs.setdefault('tool_root',fixtures.TOOL_ROOT)
            return original_inventory(path,**kwargs)
        context=patch.object(guard,'inventory',side_effect=inventory)
        context.start();self.addCleanup(context.stop)
        context=patch.object(api,'Controller',side_effect=lambda root,roots:
                             original_controller(root,roots,tool_root=fixtures.TOOL_ROOT))
        context.start();self.addCleanup(context.stop)

    def registered(self):
        prepared=self.prepare();self.call('register',token=prepared['token'])
        return prepared

    def maintenance_gateway(self):
        self.mylar.__path__=[str(Path(__file__).parent)]
        self.mylar.CONFIG.CACHE_DIR=str(self.root)
        self.mylar.publication_guard=guard;self.mylar.publication_native=native
        self.mylar.workflow=types.SimpleNamespace(store=lambda:self.store)
        spec=importlib.util.spec_from_file_location('worker_handoff_fixture',Path(__file__).with_name('worker_handoff.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.mylar.worker_handoff=module
        actual=guard.observe_owners
        def observed(*args,**kwargs):
            kwargs['tool_root']=fixtures.TOOL_ROOT
            return actual(*args,**kwargs)
        context=patch.object(guard,'observe_owners',side_effect=observed);context.start();self.addCleanup(context.stop)
        return module

    def maintenance_report(self):
        if not (self.writer.root/'publication-v1.json').exists():self.bootstrap()
        payload=json.dumps({'id':'b'*64,'members':[{'id':'c'*64,'kind':'issue','phase':'confirmed',
            'issueid':'123','comicid':'456','destination':str(self.source),
            'destination_sha256':guard.file_hash(self.source)[1]}]})
        arguments={'report':payload}
        with self.writer.hold():census=guard.registry_snapshot(self.store.path,self.writer.root/'publication-v1.json')[0]
        packet=dict(version=1,token='d'*64,command='packReport',arguments_sha256=guard.canonical_digest(arguments),census=census,
            sources=[dict(path=str(self.source),sha256=guard.file_hash(self.source)[1],
                          match={'issueid':'123','comicid':'456'},confirmation=True)])
        return arguments,packet

    def test_native_maintenance_requires_actual_catalog_destination_and_is_at_most_once(self):
        gateway=self.maintenance_gateway();arguments,packet=self.maintenance_report()
        with self.writer.hold():
            self.assertEqual(gateway.admit(json.dumps(packet),'packReport',arguments),'d'*64)
            with self.assertRaises(ValueError):gateway.admit(json.dumps(packet),'packReport',arguments)
        self.assertIsNotNone(self.store.get('worker_maintenance_attempt','d'*64))

    def test_native_maintenance_refuses_forged_scope_digest_owner_census_and_prior_proof(self):
        gateway=self.maintenance_gateway();arguments,packet=self.maintenance_report()
        before=guard.file_hash(self.source)
        for change in ({'census':dict(packet['census'],revision=99)},
                       {'sources':[dict(packet['sources'][0],sha256='0'*64)]},
                       {'sources':[dict(packet['sources'][0],path='/outside/comic.cbz')]},
                       {'sources':[dict(packet['sources'][0],match={'issueid':'999','comicid':'456'})]},
                       {'sources':[]}):
            with self.writer.hold(),self.assertRaises(ValueError):gateway.admit(json.dumps(dict(packet,**change)),'packReport',arguments)
            self.assertIsNone(self.store.get('worker_maintenance_attempt','d'*64))
            self.assertEqual(guard.file_hash(self.source),before)

    def test_native_maintenance_holds_catalog_change_after_destination_observation(self):
        gateway=self.maintenance_gateway();arguments,packet=self.maintenance_report()
        original=guard.observe_owners
        def changed(*args,**kwargs):
            result=original(*args,**kwargs)
            with closing(sqlite3.connect(self.root/'mylar.db')) as database:
                database.execute("UPDATE issues SET Status='Wanted'");database.commit()
            return result
        with self.writer.hold(),patch.object(guard,'observe_owners',side_effect=changed),self.assertRaises(ValueError):
            gateway.admit(json.dumps(packet),'packReport',arguments)
        self.assertIsNone(self.store.get('worker_maintenance_attempt','d'*64))

    def test_catalog_handoff_uses_actual_filename_bracket_evidence_before_attempt(self):
        gateway=self.maintenance_gateway();self.bootstrap()
        source=self.root/'Test #1 (2024) [digital].cbz'
        with zipfile.ZipFile(source,'w') as archive:archive.writestr('01.jpg',b'new comic')
        arguments={'evidence':json.dumps({'series':'Test','number':'1','year':'2024','edition':'Digital'}),'catalog_attempt':'1'}
        with self.writer.hold():census=guard.registry_snapshot(self.store.path,self.writer.root/'publication-v1.json')[0]
        packet=dict(version=1,token='e'*64,command='packCatalog',arguments_sha256=guard.canonical_digest(arguments),census=census,
            sources=[dict(path=str(source),sha256=guard.file_hash(source)[1],match=None,confirmation=False)])
        wrong=dict(arguments,evidence=json.dumps({'series':'Wrong','number':'1','year':'2024','edition':'Digital'}))
        with self.writer.hold(),self.assertRaises(ValueError):
            gateway.admit(json.dumps(dict(packet,arguments_sha256=guard.canonical_digest(wrong))),'packCatalog',wrong)
        self.assertIsNone(self.store.get('worker_maintenance_attempt','e'*64))
        with self.writer.hold():self.assertEqual(gateway.admit(json.dumps(packet),'packCatalog',arguments),'e'*64)

    def test_catalog_cannot_assign_an_unowned_registered_payload(self):
        self.registered();gateway=self.maintenance_gateway()
        arguments={'evidence':json.dumps({'series':'Test','number':'1','year':'2024'}),'catalog_attempt':'1'}
        with self.writer.hold():census=guard.registry_snapshot(self.store.path,self.writer.root/'publication-v1.json')[0]
        packet=dict(version=1,token='e'*64,command='packCatalog',arguments_sha256=guard.canonical_digest(arguments),census=census,
            sources=[dict(path=str(self.incoming),sha256=guard.file_hash(self.incoming)[1],match=None,confirmation=False)])
        with self.writer.hold(),self.assertRaises(ValueError):gateway.admit(json.dumps(packet),'packCatalog',arguments)
        self.assertIsNone(self.store.get('worker_maintenance_attempt','e'*64))

    def test_native_maintenance_missing_or_false_protocol_spends_no_attempt(self):
        gateway=self.maintenance_gateway();arguments,packet=self.maintenance_report()
        for raw in (None,'{}',json.dumps(dict(packet,version=True)),json.dumps(dict(packet,arguments_sha256='0'*64))):
            with self.writer.hold(),self.assertRaises(ValueError):gateway.admit(raw,'packReport',arguments)
        self.assertIsNone(self.store.get('worker_maintenance_attempt','d'*64))

    def test_guided_acknowledgement_requires_exact_choice_and_fresh_catalog_confirmation(self):
        gateway=self.maintenance_gateway();_,packet=self.maintenance_report()
        binding=dict(id='a'*32,source_token='b'*32,version='c'*64,issueid='123',comicid='456')
        self.store.set('command',binding['id'],dict(binding,phase='submitted',dispatched=True))
        arguments=dict(command_id=binding['id'],phase='confirmed',reason='',command_binding=json.dumps(binding))
        packet.update(command='workflowAcknowledge',arguments_sha256=guard.canonical_digest(arguments))
        for changed in (dict(packet,sources=[]),dict(packet,command='packReport')):
            with self.writer.hold(),self.assertRaises(ValueError):gateway.admit(json.dumps(changed),'workflowAcknowledge',arguments)
            self.assertIsNone(self.store.get('worker_maintenance_attempt','d'*64))
        with self.writer.hold():self.assertEqual(gateway.admit(json.dumps(packet),'workflowAcknowledge',arguments),'d'*64)

    def handoff(self, **changes):
        import json
        with self.writer.hold():
            proof=native.require(self.incoming,issueid='123',comicid='456')
            census,_=guard.registry_snapshot(self.store.path,self.writer.root/'publication-v1.json')
        # Use a private directory with exactly one archive as the remote stage.
        stage=self.root/'handoff-stage';stage.mkdir(exist_ok=True)
        import shutil
        target=stage/self.incoming.name;shutil.copyfile(self.incoming,target)
        request=dict(version=1,token='a'*64,source_sha256=proof['inventory']['source_sha256'],
                     payload=proof['inventory']['payload'],owner=proof['owner'],census=census)
        request.update(changes)
        return json.dumps(request),dict(nzb_folder=str(stage),nzb_name=target.name,
                                      issueid='123',comicid='456',ddl='True')

    def test_native_handoff_checks_actual_bytes_owner_and_census_before_admission(self):
        self.registered();raw,values=self.handoff()
        with self.writer.hold():
            proof=native.import_handoff(raw,values)
        self.assertEqual(proof['token'],'a'*64)
        self.assertEqual(proof['owner'],self.owner)

    def test_native_handoff_refuses_wrong_bytes_census_owner_or_ambiguous_stage(self):
        self.registered()
        for change in ({'source_sha256':'b'*64},{'payload':'b'*64},
                       {'owner':dict(table='issues',issueid='999',parentcomicid='888',releasecomicid='888')},
                       {'census':guard.empty_census('c'*64)}):
            raw,values=self.handoff(**change)
            with self.writer.hold(),self.subTest(change=change),self.assertRaises(ValueError):
                native.import_handoff(raw,values)
        raw,values=self.handoff()
        (Path(values['nzb_folder'])/'second.cbz').write_bytes(self.incoming.read_bytes())
        with self.writer.hold(),self.assertRaises(ValueError):native.import_handoff(raw,values)

    def test_native_handoff_ledger_blocks_repeat_before_queue_and_is_not_authority(self):
        import workflow_store
        self.registered();raw,values=self.handoff()
        with self.writer.hold():
            before,_=guard.registry_snapshot(self.store.path,self.writer.root/'publication-v1.json')
        self.mylar.publication_native=native
        self.mylar.library_status=types.SimpleNamespace()
        self.mylar.CONFIG.API_ENABLED=True;self.mylar.CONFIG.API_KEY='fixture'
        module=types.ModuleType('isolated_workflow_handoff')
        with patch.dict(sys.modules,{'mylar.workflow_store':workflow_store}):
            exec(compile(Path(__file__).with_name('workflow.py').read_text(),'workflow.py','exec'),module.__dict__)
        client=types.SimpleNamespace(apikey='fixture',_failureResponse=lambda reason:{'success':False},data=None)
        queued=Mock(return_value='queued')
        wrapped=module.force_process(queued)
        with self.writer.hold(),patch.object(module,'store',return_value=self.store):
            self.assertEqual(wrapped(client,publication_handoff=raw,**values),'queued')
            wrapped(client,publication_handoff=raw,**values)
            self.assertEqual(client.data,{'success':False})
            import json
            second=json.loads(raw);second['token']='b'*64
            wrapped(client,publication_handoff=json.dumps(second),**values)
            self.assertEqual(client.data,{'success':False})
            self.assertIsNone(self.store.get('worker_import_attempt','b'*64))
            census,_=guard.registry_snapshot(self.store.path,self.writer.root/'publication-v1.json')
        queued.assert_called_once()
        self.assertEqual(census,before)
        self.assertTrue(self.store.get('worker_import_attempt','a'*64))

    def test_queued_handoff_rechecks_actual_stage_and_immutable_ledger(self):
        self.registered();raw,values=self.handoff()
        processor=types.SimpleNamespace(**values,download_info=None)
        with self.writer.hold():proof=native.import_handoff(raw,values)
        processor.download_info={'publication_handoff':proof}
        self.store.set('worker_import_attempt',proof['token'],proof)
        workflow=types.SimpleNamespace(store=lambda:self.store)
        self.mylar.workflow=workflow
        with patch.dict(sys.modules,{'mylar.workflow':workflow}),self.writer.hold():
            self.assertEqual(native.resume_handoff(processor),proof)
            with self.assertRaises(native.Review):native.resume_handoff(processor)
            changed=dict(proof,payload='b'*64)
            processor.download_info={'publication_handoff':changed}
            with self.assertRaises(native.Review):native.resume_handoff(processor)
            processor.download_info={'publication_handoff':proof}
            path=Path(proof['source'])
            with zipfile.ZipFile(path,'w') as archive:archive.writestr('replacement.jpg',b'changed pages')
            with self.assertRaises(native.Review):native.resume_handoff(processor)
        self.assertEqual(self.store.get('worker_import_attempt',proof['token']),proof)

    def test_native_handoff_primary_authentication_precedes_decoder_and_queue(self):
        import workflow_store
        self.mylar.library_status=types.SimpleNamespace()
        self.mylar.CONFIG.API_ENABLED=True;self.mylar.CONFIG.API_KEY='fixture'
        self.mylar.publication_native=native
        module=types.ModuleType('isolated_workflow_handoff')
        with patch.dict(sys.modules,{'mylar.workflow_store':workflow_store}):
            exec(compile(Path(__file__).with_name('workflow.py').read_text(),'workflow.py','exec'),module.__dict__)
        client=types.SimpleNamespace(apikey='wrong',_failureResponse=lambda reason:{'success':False})
        queued=Mock()
        with patch.object(native,'import_handoff') as decoder:
            module.force_process(queued)(client,publication_handoff='invalid')
        decoder.assert_not_called();queued.assert_not_called()

    def check(self,issueid='123',comicid='456'):
        with self.writer.hold():return native.require(self.incoming,issueid=issueid,comicid=comicid)

    def sql(self,*args):fixtures.fixtures.NativeObservationTests.sql(self,*args)

    def test_registered_correct_owner_is_allowed_without_mutation(self):
        self.registered();before=(self.incoming.read_bytes(),self.database.read_bytes(),self.store.path.read_bytes())
        self.assertEqual(self.check()['decision'],'allowed')
        self.assertEqual(before,(self.incoming.read_bytes(),self.database.read_bytes(),self.store.path.read_bytes()))

    def test_exact_rejected_owner_retains_archive_and_catalog(self):
        self.registered()
        self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',None,'Snatched'))
        before=(self.incoming.read_bytes(),self.database.read_bytes())
        with self.assertRaises(native.Review) as raised:self.check('999','888')
        self.assertEqual(raised.exception.reason,'verified-correction')
        self.assertEqual(before,(self.incoming.read_bytes(),self.database.read_bytes()))

    def test_registered_payload_with_synthetic_owner_is_review(self):
        self.registered()
        for issueid in ('S123','G123','_123',None):
            with self.subTest(issueid=issueid),self.assertRaises(native.Review):self.check(issueid,None)

    def test_genuinely_distinct_archive_keeps_existing_eligibility(self):
        self.registered()
        with zipfile.ZipFile(self.incoming,'w') as archive:archive.writestr('01.jpg',b'different publication page')
        self.assertEqual(self.check()['decision'],'unknown')

    def test_lost_registry_is_review_without_recreation(self):
        self.registered();(self.writer.root/'publication-v1.json').unlink()
        before=self.incoming.read_bytes()
        with self.assertRaises(native.Review):self.check()
        self.assertFalse((self.writer.root/'publication-v1.json').exists())
        self.assertEqual(self.incoming.read_bytes(),before)

    def test_changed_matched_correct_archive_holds_repeat(self):
        self.registered()
        with zipfile.ZipFile(self.source,'w') as archive:archive.writestr('01.jpg',b'changed correct publication')
        with self.assertRaises(native.Review):self.check()

    def test_deleted_locationless_annual_shadow_holds_before_processing(self):
        self.registered()
        self.sql('INSERT INTO annuals VALUES (?,?,?,?,?,?)',('123','456','789',None,'Wanted',1))
        with self.assertRaises(native.Review):self.check()

    def test_wrong_parent_is_review_and_annual_release_parent_stay_distinct(self):
        self.bootstrap()
        with self.assertRaises(native.Review):self.check('123','789')
        self.sql('INSERT INTO annuals VALUES (?,?,?,?,?,?)',('321','456','789',None,'Wanted',0))
        result=self.check('321','456')
        self.assertEqual(result['owner'],dict(table='annuals',issueid='321',parentcomicid='456',releasecomicid='789'))

    def test_missing_outer_admission_is_terminal_review(self):
        self.bootstrap();self.runtime.active=lambda:False
        with self.assertRaises(native.Review):self.check()

    def test_authority_loss_after_fresh_observation_cannot_reuse_allowed_result(self):
        self.registered();original=self.controller._check
        def changed(*args):
            result=original(*args)
            (self.writer.root/'publication-v1.json').unlink()
            return result
        with patch.object(api,'Controller',return_value=self.controller),patch.object(self.controller,'_check',side_effect=changed):
            with self.assertRaises(native.Review):self.check()
        self.assertFalse((self.writer.root/'publication-v1.json').exists())

    def test_new_pending_fence_after_observation_is_retained_without_replay(self):
        self.registered();original=self.controller._check
        def changed(*args):
            result=original(*args);self.writer.create_file(self.writer.tagger_pending);return result
        with patch.object(api,'Controller',return_value=self.controller),patch.object(self.controller,'_check',side_effect=changed):
            with self.assertRaises(native.Review):self.check()
        self.assertTrue(self.writer.tagger_pending.exists())

    def test_parent_symlink_swap_after_observation_is_review(self):
        self.registered();parent=self.root/'incoming';parent.mkdir()
        shutil.move(self.incoming,parent/self.incoming.name);self.incoming=parent/self.incoming.name
        original=self.controller._check
        def changed(*args):
            result=original(*args);renamed=self.root/'renamed-incoming'
            parent.rename(renamed);parent.symlink_to(renamed,target_is_directory=True)
            return result
        with patch.object(api,'Controller',return_value=self.controller),patch.object(self.controller,'_check',side_effect=changed):
            with self.assertRaises(native.Review):self.check()
        self.assertTrue(parent.is_symlink());self.assertTrue(self.incoming.exists())

    def test_registered_owned_move_is_held_before_placement_and_catalog_change(self):
        import processing_guard
        self.registered();self.mylar.CONFIG.FILE_OPTS='move'
        target=self.library/'new-name.cbz';before=(self.source.read_bytes(),self.database.read_bytes())
        obj=types.SimpleNamespace(valreturn=[])
        with self.writer.hold(),self.assertRaises(native.Review):
            processing_guard.placement(obj,self.source,target,issueid='123',comicid='456')
            shutil.move(self.source,target)
        self.assertFalse(target.exists());self.assertEqual(before,(self.source.read_bytes(),self.database.read_bytes()))
        self.assertEqual(obj.valreturn[-1]['reason'],'registered-source-relocation')

    def test_registered_correct_copy_retains_original_and_rechecks_target(self):
        import processing_guard
        self.registered();self.mylar.CONFIG.FILE_OPTS='copy';target=self.library/'retained-copy.cbz'
        obj=types.SimpleNamespace(valreturn=[])
        with self.writer.hold():
            processing_guard.placement(obj,self.source,target,issueid='123',comicid='456')
            shutil.copyfile(self.source,target)
            result=processing_guard.publication(obj,target,issueid='123',comicid='456')
        self.assertEqual(result['decision'],'allowed');self.assertEqual(target.read_bytes(),self.source.read_bytes())
        self.assertEqual(obj.valreturn,[])

    def test_registered_duplicate_displacement_retains_proposed_owner_and_holds_before_move(self):
        import processing_guard
        self.registered();self.mylar.CONFIG.FILE_OPTS='move'
        obj=types.SimpleNamespace(valreturn=[])
        with self.writer.hold():
            processing_guard.publication(obj,self.incoming,issueid='123',comicid='456')
            self.assertEqual(obj._publication_owner,self.owner)
            with self.assertRaises(native.Review):processing_guard.displacement(obj,self.source)
        self.assertTrue(self.source.exists());self.assertTrue(self.incoming.exists())


@unittest.skipUnless(os.environ.get('MYLAR_WORKFLOW_SOURCE') and
                     (Path(fixtures.TOOL_ROOT)/'lib/archive_backend.py').is_file(),
                     'actual native source and offline archive verifier required')
class NativeBoundaryTests(unittest.TestCase):
    setUp=AdmissionTests.setUp
    call=AdmissionTests.call
    bootstrap=AdmissionTests.bootstrap
    prepare=AdmissionTests.prepare
    registered=AdmissionTests.registered
    sql=AdmissionTests.sql

    def statements(self):
        from patch_publication_processing import patched_source
        source=(Path(os.environ['MYLAR_WORKFLOW_SOURCE'])/'PostProcessor.py').read_text()
        result=patched_source(source);self.assertEqual(patched_source(result),result)
        tree=ast.parse(result)
        return [node for node in ast.walk(tree) if isinstance(node,ast.Expr)
                and isinstance(node.value,ast.Call)
                and ast.unparse(node.value.func) in ('processing_guard.publication',
                      'processing_guard.placement','processing_guard.displacement','processing_guard.cleanup','processing_guard.cleanup_scope')]

    def namespace(self,issueid,comicid):
        import processing_guard
        self.mylar.CONFIG.STORYARCDIR=True;self.mylar.CONFIG.COPY2ARCDIR=True;self.mylar.CONFIG.FILE_OPTS='copy'
        self.mylar.CONFIG.ARC_FILEOPS='copy';self.mylar.CONFIG.ENABLE_META=False
        obj=types.SimpleNamespace(nzb_folder=str(self.incoming),valreturn=[],issueid=issueid,
            nzb_name='Manual Run',_publication_owner=dict(issueid=issueid,parentcomicid=comicid))
        return dict(processing_guard=processing_guard,mylar=self.mylar,self=obj,os=os,
                    ml=dict(ComicLocation=str(self.incoming),ComicID=comicid),
                    dupeinfo=dict(to_dupe=str(self.incoming)),issueid=issueid,comicid=comicid,
                    ofilename=str(self.incoming),orig_filename=self.incoming.name,
                    subpath=str(self.incoming.parent),src=str(self.incoming),dst=str(self.incoming),
                    grab_src=str(self.incoming),grab_dst=str(self.incoming),
                    location=str(self.incoming.parent),odir=str(self.incoming.parent),tmp_ppdir=self.incoming.name,
                    mult_count=False,del_nzbdir=True,sub_path=None,cacheonly=False,filename=self.incoming.name)

    def test_all_actual_native_guard_expressions_hold_wrong_owner_before_mutation(self):
        self.registered();self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',None,'Snatched'))
        statements=self.statements();self.assertEqual(len(statements),47)
        before=(self.incoming.read_bytes(),self.database.read_bytes())
        for node in statements:
            with self.subTest(line=node.lineno):
                namespace=self.namespace('999','888');mutate=Mock();namespace['mutate']=mutate
                if ast.unparse(node.value.func)=='processing_guard.cleanup_scope':self.mylar.CONFIG.FILE_OPTS='move'
                body=[node,ast.parse('mutate()').body[0]]
                with self.writer.hold(),self.assertRaises(native.Review):
                    exec(compile(ast.Module(body=body,type_ignores=[]),'<actual native boundary>','exec'),namespace)
                mutate.assert_not_called()
                self.assertEqual(namespace['self'].valreturn[-1]['mode'],'review')
        self.assertEqual(before,(self.incoming.read_bytes(),self.database.read_bytes()))

    def test_all_actual_native_guard_expressions_allow_distinct_payload(self):
        self.registered()
        with zipfile.ZipFile(self.incoming,'w') as archive:archive.writestr('01.jpg',b'distinct eligible comic')
        for node in self.statements():
            with self.subTest(line=node.lineno),self.writer.hold():
                namespace=self.namespace('123','456')
                if ast.unparse(node.value.func)=='processing_guard.cleanup_scope':self.mylar.CONFIG.FILE_OPTS='move'
                exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual native boundary>','exec'),namespace)
                self.assertEqual(namespace['self'].valreturn,[])

    def test_patch_rejects_removed_or_changed_actual_guard(self):
        from patch_publication_processing import patched_source
        source=(Path(os.environ['MYLAR_WORKFLOW_SOURCE'])/'PostProcessor.py').read_text()
        result=patched_source(source)
        for changed in (result.replace('processing_guard.publication(', 'changed.publication(',1),
                        result.replace('issueid=issueid, comicid=', 'issueid=None, comicid=',1)):
            with self.assertRaises(ValueError):patched_source(changed)

    def test_source_changing_script_is_rechecked_before_actual_tagger_boundary(self):
        self.registered();self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',None,'Snatched'))
        with zipfile.ZipFile(self.incoming,'w') as archive:archive.writestr('01.jpg',b'different initial comic')
        namespace=self.namespace('999','888')
        node=next(node for node in self.statements() if
                  'os.path.join(odir, ofilename)' in ast.unparse(node))
        with self.writer.hold():
            self.assertEqual(native.require(self.incoming,issueid='999',comicid='888')['decision'],'unknown')
            # Model the authorized script replacing the candidate with a known
            # conflicting payload. Fresh tagger admission must reject it.
            shutil.copyfile(self.source,self.incoming)
            with self.assertRaises(native.Review):
                exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual post-script tagger boundary>','exec'),namespace)
        self.assertTrue(self.incoming.exists());self.assertTrue(self.source.exists())

    def test_process_acknowledgement_patch_is_checked_and_idempotent(self):
        from patch_publication_processing import patched_process
        source=(Path(os.environ['MYLAR_WORKFLOW_SOURCE'])/'process.py').read_text()
        result=patched_process(source);self.assertEqual(patched_process(result),result)
        self.assertEqual(result.count("row.get('mode') == 'review'"),3)
        for changed in (result.replace("row.get('mode') == 'review'",'False',1),
                        result.replace("source retained')\n                    return","source retained')\n                    pass",1)):
            self.assertNotEqual(changed,result)
            with self.assertRaises(ValueError):patched_process(changed)

    def actual_function(self,filename,name):
        from patch_publication_processing import patched_source
        text=(Path(os.environ['MYLAR_WORKFLOW_SOURCE'])/filename).read_text()
        if filename=='PostProcessor.py':text=patched_source(text)
        node=next(node for node in ast.walk(ast.parse(text))
                  if isinstance(node,ast.FunctionDef) and node.name==name)
        import processing_guard
        import publication_mutation
        namespace=dict(mylar=self.mylar,processing_guard=processing_guard,publication_mutation=publication_mutation,logger=Mock(),
                       os=os,shutil=shutil,errno=__import__('errno'),
                       native_writers=types.SimpleNamespace(guard=lambda function:function))
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual native '+name+'>','exec'),namespace)
        return namespace[name]

    def test_actual_file_operations_bind_oneoff_arc_multiple_and_softlink_modes(self):
        import processing_guard
        self.registered();operation=self.actual_function('helpers.py','file_ops')
        self.mylar.OS_DETECT='linux';self.mylar.CONFIG.ARC_FILEOPS_SOFTLINK_RELATIVE=False
        before=(self.source.read_bytes(),self.database.read_bytes())
        cases=[('copy','move',dict(one_off=True),True),
               ('softlink','copy',{},True),('move','copy',dict(one_off=True),False),
               ('move','move',dict(arc=True),False),
               ('move','move',dict(one_off=True,multiple=True),False)]
        for index,(ordinary,arc,options,held) in enumerate(cases):
            with self.subTest(ordinary=ordinary,arc=arc,options=options),self.writer.hold():
                self.mylar.CONFIG.FILE_OPTS=ordinary;self.mylar.CONFIG.ARC_FILEOPS=arc
                target=self.library/('mode-'+str(index)+'.cbz');obj=types.SimpleNamespace(valreturn=[])
                def apply():
                    processing_guard.placement(obj,self.source,target,issueid='123',comicid='456',**options)
                    with patch.object(processing_guard._ACTIVE,'processor',obj,create=True):
                        return operation(str(self.source),str(target),**options)
                if held:
                    with self.assertRaises(native.Review):apply()
                    self.assertFalse(target.exists())
                else:
                    self.assertTrue(apply());self.assertEqual(target.read_bytes(),before[0])
                self.assertEqual(before,(self.source.read_bytes(),self.database.read_bytes()))
                self.assertFalse(self.source.is_symlink())

    def test_actual_same_path_softlink_is_held_while_move_preserves_archive(self):
        import processing_guard
        self.registered();operation=self.actual_function('helpers.py','file_ops')
        self.mylar.OS_DETECT='linux';self.mylar.CONFIG.ARC_FILEOPS_SOFTLINK_RELATIVE=False
        before=(self.source.read_bytes(),self.database.read_bytes())
        for action in ('move','softlink'):
            with self.subTest(action=action),self.writer.hold():
                self.mylar.CONFIG.FILE_OPTS=action;obj=types.SimpleNamespace(valreturn=[])
                def apply():
                    processing_guard.placement(obj,self.source,self.source,issueid='123',comicid='456')
                    with patch.object(processing_guard._ACTIVE,'processor',obj,create=True):
                        return operation(str(self.source),str(self.source))
                if action=='softlink':
                    with self.assertRaises(native.Review):apply()
                else:self.assertTrue(apply())
                self.assertFalse(self.source.is_symlink())
                self.assertEqual(before,(self.source.read_bytes(),self.database.read_bytes()))

    def test_actual_cache_placement_then_tidyup_retains_registered_original(self):
        import processing_guard
        self.registered();self.mylar.CONFIG.FILE_OPTS='move';self.mylar.CONFIG.ARC_FILEOPS='copy'
        self.mylar.CONFIG.ARC_FILEOPS_SOFTLINK_RELATIVE=False;self.mylar.CONFIG.ENABLE_META=True
        self.mylar.OS_DETECT='linux'
        cache=self.root/'mylar_tagged';cache.mkdir();cached=cache/'tagged.cbz'
        shutil.copyfile(self.source,cached);target=self.library/'arc-copy.cbz'
        obj=types.SimpleNamespace(valreturn=[],nzb_folder=str(self.source),issueid='123',
                                 nzb_name='Manual Run',module='fixture',_log=Mock())
        operation=self.actual_function('helpers.py','file_ops')
        tidyup=self.actual_function('PostProcessor.py','tidyup');commit=Mock()
        before=(self.source.read_bytes(),self.database.read_bytes())
        with self.writer.hold():
            processing_guard.publication(obj,self.source,issueid='123',comicid='456')
            processing_guard.placement(obj,cached,target,issueid='123',comicid='456',one_off=True)
            with patch.object(processing_guard._ACTIVE,'processor',obj,create=True):
                self.assertTrue(operation(str(cached),str(target),one_off=True))
            with self.assertRaises(native.Review):
                tidyup(obj,str(cache),True,filename=self.source.name)
                commit()
        commit.assert_not_called();self.assertTrue(cached.exists());self.assertTrue(target.exists())
        self.assertEqual(before,(self.source.read_bytes(),self.database.read_bytes()))
        self.assertEqual(obj.valreturn[-1]['reason'],'registered-source-relocation')

    def test_actual_tidyup_checks_all_cache_siblings_before_first_deletion(self):
        import processing_guard
        self.registered();self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',None,'Snatched'))
        self.mylar.CONFIG.FILE_OPTS='copy';self.mylar.CONFIG.ENABLE_META=True
        cache=self.root/'mylar_cache';cache.mkdir();first=cache/'first.cbz';wrong=cache/'retained.cbz'
        with zipfile.ZipFile(first,'w') as archive:archive.writestr('01.jpg',b'distinct cache comic')
        shutil.copyfile(self.source,wrong)
        obj=types.SimpleNamespace(valreturn=[],nzb_folder=str(self.incoming),issueid='999',
                                 nzb_name='Manual Run',module='fixture',_log=Mock())
        tidyup=self.actual_function('PostProcessor.py','tidyup')
        before=(first.read_bytes(),wrong.read_bytes(),self.database.read_bytes())
        with self.writer.hold():
            processing_guard.publication(obj,first,issueid='999',comicid='888')
            with self.assertRaises(native.Review):tidyup(obj,str(cache),True,cacheonly=True)
        self.assertEqual(before,(first.read_bytes(),wrong.read_bytes(),self.database.read_bytes()))

    def test_actual_tidyup_retains_archive_with_unclassified_cache_suffix(self):
        import processing_guard
        self.registered();self.mylar.CONFIG.FILE_OPTS='copy';self.mylar.CONFIG.ENABLE_META=True
        cache=self.root/'mylar_cache';cache.mkdir();cached=cache/'eligible.cbz';retained=cache/'retained.bak'
        with zipfile.ZipFile(cached,'w') as archive:archive.writestr('01.jpg',b'distinct cache archive')
        shutil.copyfile(self.source,retained)
        obj=types.SimpleNamespace(valreturn=[],nzb_folder=str(self.incoming),issueid='123',
                                 nzb_name='Manual Run',module='fixture',_log=Mock())
        tidyup=self.actual_function('PostProcessor.py','tidyup');before=(cached.read_bytes(),retained.read_bytes())
        with self.writer.hold():
            processing_guard.publication(obj,cached,issueid='123',comicid='456')
            with self.assertRaises(native.Review):tidyup(obj,str(cache),True,cacheonly=True)
        self.assertEqual(before,(cached.read_bytes(),retained.read_bytes()))

    def test_actual_tidyup_rejects_new_cache_entry_after_payload_checks(self):
        import processing_guard
        self.registered();self.mylar.CONFIG.FILE_OPTS='copy';self.mylar.CONFIG.ENABLE_META=True
        cache=self.root/'mylar_cache';cache.mkdir();cached=cache/'eligible.cbz';retained=cache/'late.cbz'
        with zipfile.ZipFile(cached,'w') as archive:archive.writestr('01.jpg',b'distinct cache archive')
        obj=types.SimpleNamespace(valreturn=[],nzb_folder=str(self.incoming),issueid='123',
                                 nzb_name='Manual Run',module='fixture',_log=Mock())
        tidyup=self.actual_function('PostProcessor.py','tidyup');original=processing_guard.publication
        def intervene(*args,**kwargs):
            result=original(*args,**kwargs)
            shutil.copyfile(self.source,retained)
            return result
        with self.writer.hold():
            processing_guard.publication(obj,cached,issueid='123',comicid='456')
            with patch.object(processing_guard,'publication',side_effect=intervene),self.assertRaises(native.Review):
                tidyup(obj,str(cache),True,cacheonly=True)
        self.assertTrue(cached.exists());self.assertEqual(retained.read_bytes(),self.source.read_bytes())

    def test_actual_tidyup_binds_absent_original_and_absent_cache_directory(self):
        import processing_guard
        self.registered();self.mylar.CONFIG.FILE_OPTS='move';self.mylar.CONFIG.ENABLE_META=True
        tidyup=self.actual_function('PostProcessor.py','tidyup');original=processing_guard.publication
        for absent in ('original','cache'):
            with self.subTest(absent=absent):
                area=self.root/absent;area.mkdir();incoming=area/'input.cbz';cache=area/'mylar_cache'
                if absent=='original':
                    cache.mkdir();eligible=cache/'eligible.cbz'
                else:eligible=incoming
                with zipfile.ZipFile(eligible,'w') as archive:archive.writestr('01.jpg',b'distinct eligible archive')
                obj=types.SimpleNamespace(valreturn=[],nzb_folder=str(incoming),issueid='123',
                                         nzb_name='Manual Run',module='fixture',_log=Mock())
                def intervene(*args,**kwargs):
                    result=original(*args,**kwargs)
                    if absent=='original':shutil.copyfile(self.source,incoming)
                    else:
                        cache.mkdir(exist_ok=True);shutil.copyfile(self.source,cache/'retained.cbz')
                    return result
                with self.writer.hold():
                    processing_guard.publication(obj,eligible,issueid='123',comicid='456')
                    with patch.object(processing_guard,'publication',side_effect=intervene),self.assertRaises(native.Review):
                        tidyup(obj,str(cache),True,filename=incoming.name)
                self.assertTrue(eligible.exists())
                if absent=='original':self.assertEqual(incoming.read_bytes(),self.source.read_bytes())
                else:self.assertEqual((cache/'retained.cbz').read_bytes(),self.source.read_bytes())

    def test_actual_tidyup_preserves_ordinary_distinct_cleanup_eligibility(self):
        import processing_guard
        self.registered();self.mylar.CONFIG.FILE_OPTS='copy';self.mylar.CONFIG.ENABLE_META=True
        cache=self.root/'mylar_cache';cache.mkdir();cached=cache/'eligible.cbz'
        with zipfile.ZipFile(cached,'w') as archive:archive.writestr('01.jpg',b'genuinely different comic')
        obj=types.SimpleNamespace(valreturn=[],nzb_folder=str(self.incoming),issueid='123',
                                 nzb_name='Manual Run',module='fixture',_log=Mock())
        tidyup=self.actual_function('PostProcessor.py','tidyup')
        with self.writer.hold():
            processing_guard.publication(obj,cached,issueid='123',comicid='456')
            tidyup(obj,str(cache),True,cacheonly=True)
        self.assertFalse(cache.exists());self.assertTrue(self.source.exists());self.assertEqual(obj.valreturn,[])

    def test_actual_process_review_never_launches_failure_search_or_manual_retry(self):
        import queue
        from patch_publication_processing import patched_process
        source=(Path(os.environ['MYLAR_WORKFLOW_SOURCE'])/'process.py').read_text()
        tree=ast.parse(patched_process(source))
        cls=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='Process')
        method=next(node for node in cls.body if isinstance(node,ast.FunctionDef) and node.name=='post_process')
        class Thread:
            def __init__(self,target,**kwargs):self.target=target
            def start(self):self.target()
            def join(self):pass
        failed=Mock();retry=Mock()
        for name,issueid in (('automatic',None),('Manual Run','123')):
            records=[dict(mode='fail',annchk='no'),dict(mode='review',retained=True)]
            def factory(*args,**kwargs):
                return types.SimpleNamespace(valreturn=records,Process=lambda:kwargs['queue'].put(records))
            self.mylar.PostProcessor=types.SimpleNamespace(PostProcessor=factory)
            self.mylar.Failed=types.SimpleNamespace(FailedProcessor=failed)
            self.mylar.webserve=types.SimpleNamespace(WebInterface=retry)
            self.mylar.CONFIG.FAILED_DOWNLOAD_HANDLING=True
            namespace=dict(mylar=self.mylar,queue=queue,threading=types.SimpleNamespace(Thread=Thread),
                           logger=Mock(),workflow=Mock())
            exec(compile(ast.Module(body=[method],type_ignores=[]),'<actual native acknowledgement>','exec'),namespace)
            obj=types.SimpleNamespace(failed=False,nzb_name=name,nzb_folder=str(self.incoming),
                                     issueid=issueid,comicid='456',apicall=False,ddl=True,download_info={})
            namespace['post_process'](obj)
            self.assertFalse(obj.failed)
        failed.assert_not_called();retry.assert_not_called()


if __name__=='__main__':unittest.main()
