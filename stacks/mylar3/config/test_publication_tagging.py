"""Fresh tagging entry controls share real archive/registry/catalog fixtures."""
from contextlib import closing, contextmanager
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import types
import uuid
import threading
import unittest
from unittest.mock import Mock, patch
import zipfile

import test_publication_native as cases
import publication_native as native
import tagger_backend
import tagger_service
import tagger_adapter
import tagger_archive
import tagger_pack
import tagger_staging
from tagger_cli import TagResult
import processing_guard
import tagger_handoff
import publication_transaction as transaction
import publication_guard as guard
import converted_tagging
import workflow_store


@contextmanager
def working_directory(path):
    """Exercise real pathlib cwd behavior on both native and host Python."""
    original=os.open('.',os.O_RDONLY|os.O_DIRECTORY)
    try:
        os.chdir(path)
        yield
    finally:
        os.fchdir(original);os.close(original)


class BackendTests(unittest.TestCase):
    call=cases.AdmissionTests.call
    bootstrap=cases.AdmissionTests.bootstrap
    prepare=cases.AdmissionTests.prepare
    registered=cases.AdmissionTests.registered
    sql=cases.AdmissionTests.sql

    def setUp(self):
        cases.AdmissionTests.setUp(self)
        self.legacy=Mock(return_value=str(self.incoming))
        self.modern=Mock(return_value=str(self.incoming))
        self.mylar.tagger_handoff=tagger_handoff
        self.mylar.publication_native=native
        self.mylar.processing_guard=processing_guard
        self.mylar.tagger_native=types.SimpleNamespace(run=self.modern)
        @contextmanager
        def operation():
            with self.writer.hold(allow_tagger_pending=True):yield self.writer
        self.runtime.operation=operation
        context=patch.dict(sys.modules,{'mylar.publication_native':native})
        context.start();self.addCleanup(context.stop)

    def dispatch(self,*,manual=False,issueid='123'):
        return tagger_backend.dispatch(self.legacy,str(self.incoming.parent),
                                      filename=str(self.incoming),issueid=issueid,manualmeta=manual)

    def test_relative_success_path_is_normalized_and_verified(self):
        self.registered();self.mylar.CONFIG.TAGGER_BACKEND='modern'
        self.modern.return_value=self.incoming.name
        with working_directory(self.incoming.parent):
            self.assertEqual(self.dispatch(),str(self.incoming))

    def test_relative_wrong_payload_output_cannot_bypass_returned_archive_check(self):
        self.registered();self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',None,'Snatched'))
        with zipfile.ZipFile(self.incoming,'w') as archive:archive.writestr('01.jpg',b'distinct eligible pages')
        returned=self.incoming.parent/'wrong-output.cbz';shutil.copyfile(self.source,returned)
        self.mylar.CONFIG.TAGGER_BACKEND='modern';self.modern.return_value=returned.name
        with working_directory(self.incoming.parent),self.assertRaises(native.Review):
            self.dispatch(issueid='999')
        self.assertTrue(returned.exists());self.assertTrue(self.incoming.exists())

    def test_wrong_owner_automatic_retains_before_either_backend(self):
        self.registered();self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',None,'Snatched'))
        before=(self.incoming.read_bytes(),self.database.read_bytes())
        for backend in ('legacy','modern'):
            with self.subTest(backend=backend):
                self.mylar.CONFIG.TAGGER_BACKEND=backend
                with self.assertRaises(native.Review):self.dispatch(issueid='999')
        self.legacy.assert_not_called();self.modern.assert_not_called()
        self.assertEqual(before,(self.incoming.read_bytes(),self.database.read_bytes()))
        self.assertFalse(self.writer.fenced(tagger=True))

    def test_wrong_owner_manual_returns_distinct_review_before_either_backend(self):
        self.registered();self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',None,'Snatched'))
        for backend in ('legacy','modern'):
            with self.subTest(backend=backend):
                self.mylar.CONFIG.TAGGER_BACKEND=backend
                result=self.dispatch(manual=True,issueid='999')
                self.assertIsInstance(result,tagger_handoff.Published)
                self.assertEqual(result.state,'review');self.assertFalse(result.valid_for(self.incoming))
        self.legacy.assert_not_called();self.modern.assert_not_called()
        self.assertFalse(self.writer.fenced(tagger=True))

    def test_synthetic_owner_cannot_tag_a_registered_payload(self):
        self.registered();self.mylar.CONFIG.TAGGER_BACKEND='legacy'
        with self.assertRaises(native.Review):self.dispatch(issueid='S123')
        self.legacy.assert_not_called()

    def test_unavailable_registry_is_retained_review_without_backend_or_recreation(self):
        self.registered();self.mylar.CONFIG.TAGGER_BACKEND='legacy'
        marker=self.writer.root/'publication-v1.json';marker.unlink()
        with self.assertRaises(native.Review):self.dispatch()
        result=self.dispatch(manual=True);self.assertEqual(result.state,'review')
        self.assertFalse(marker.exists());self.legacy.assert_not_called()

    def test_lower_guard_records_review_before_automatic_observer_unwinds(self):
        self.registered();self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',None,'Snatched'))
        self.mylar.CONFIG.TAGGER_BACKEND='legacy'
        obj=types.SimpleNamespace(valreturn=[])
        previous=getattr(processing_guard._ACTIVE,'processor',None)
        processing_guard._ACTIVE.processor=obj
        try:
            with self.assertRaises(native.Review):self.dispatch(issueid='999')
            self.assertEqual(obj.valreturn[-1]['mode'],'review')
        finally:processing_guard._ACTIVE.processor=previous
        self.legacy.assert_not_called()

    def test_correct_and_distinct_archives_preserve_modern_backend_eligibility(self):
        self.registered();self.mylar.CONFIG.TAGGER_BACKEND='modern'
        for distinct in (False,True):
            if distinct:
                with zipfile.ZipFile(self.incoming,'w') as archive:archive.writestr('01.jpg',b'distinct eligible pages')
            self.assertEqual(self.dispatch(),str(self.incoming))
        self.legacy.assert_not_called();self.assertEqual(self.modern.call_count,2)

    def test_legacy_cannot_copy_or_cleanup_before_owned_transaction_exists(self):
        self.registered();self.mylar.CONFIG.TAGGER_BACKEND='legacy'
        before=(self.incoming.read_bytes(),self.source.read_bytes(),self.database.read_bytes())
        self.legacy.side_effect=AssertionError('Legacy must not copy, launch or cleanup')
        with self.assertRaises(native.Review) as raised:self.dispatch()
        self.assertEqual(raised.exception.reason,'tagging-legacy-transaction-required')
        result=self.dispatch(manual=True)
        self.assertEqual(result.state,'review');self.assertFalse(result.valid_for(self.incoming))
        self.legacy.assert_not_called();self.modern.assert_not_called()
        self.assertEqual(before,(self.incoming.read_bytes(),self.source.read_bytes(),self.database.read_bytes()))
        self.assertFalse(self.writer.fenced(tagger=True));self.assertFalse(transaction.present(self.writer))

    def test_distinct_unknown_output_cannot_replace_another_unknown_input_payload(self):
        self.registered();self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',None,'Snatched'))
        with zipfile.ZipFile(self.incoming,'w') as archive:archive.writestr('01.jpg',b'initial unknown pages')
        output=self.root/'changed-output.cbz'
        with zipfile.ZipFile(output,'w') as archive:archive.writestr('01.jpg',b'another unknown publication')
        before=self.incoming.read_bytes();self.mylar.CONFIG.TAGGER_BACKEND='modern'
        self.modern.return_value=str(output)
        with self.assertRaises(native.Review) as raised:self.dispatch(issueid='999')
        self.assertEqual(raised.exception.reason,'tagging-payload-changed')
        self.assertEqual(self.incoming.read_bytes(),before);self.assertTrue(output.exists())

    def test_unknown_source_payload_change_is_review_even_without_registry_match(self):
        self.registered();self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',None,'Snatched'))
        with zipfile.ZipFile(self.incoming,'w') as archive:archive.writestr('01.jpg',b'initial unknown pages')
        self.mylar.CONFIG.TAGGER_BACKEND='modern'
        def changed(*args,**kwargs):
            with zipfile.ZipFile(self.incoming,'w') as archive:archive.writestr('01.jpg',b'another unknown publication')
            return str(self.incoming)
        self.modern.side_effect=changed
        with self.assertRaises(native.Review) as raised:self.dispatch(issueid='999')
        self.assertEqual(raised.exception.reason,'tagging-payload-changed');self.assertTrue(self.incoming.exists())

    def test_metadata_only_temporary_output_preserves_original_payload_eligibility(self):
        self.registered();self.mylar.CONFIG.TAGGER_BACKEND='modern'
        output=self.root/'metadata-only.cbz'
        with zipfile.ZipFile(self.incoming) as archive:
            entries=[(info,archive.read(info)) for info in archive.infolist() if info.filename!='ComicInfo.xml']
        with zipfile.ZipFile(output,'w') as archive:
            for info,data in entries:archive.writestr(info,data)
            archive.writestr('ComicInfo.xml','<ComicInfo><Series>Metadata only</Series></ComicInfo>')
        self.modern.return_value=str(output);before=self.incoming.read_bytes()
        self.assertEqual(self.dispatch(),str(output));self.assertEqual(self.incoming.read_bytes(),before)

    def test_payload_change_during_backend_cannot_reuse_initial_admission(self):
        self.registered();self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',None,'Snatched'))
        with zipfile.ZipFile(self.incoming,'w') as archive:archive.writestr('01.jpg',b'initial distinct pages')
        self.mylar.CONFIG.TAGGER_BACKEND='modern'
        def changed(*args,**kwargs):
            shutil.copyfile(self.source,self.incoming)
            return str(self.incoming)
        self.modern.side_effect=changed
        with self.assertRaises(native.Review):self.dispatch(issueid='999')
        self.assertTrue(self.incoming.exists());self.assertTrue(self.source.exists())


class DirectNativeTests(unittest.TestCase):
    setUp=BackendTests.setUp
    call=BackendTests.call
    bootstrap=BackendTests.bootstrap
    prepare=BackendTests.prepare
    registered=BackendTests.registered
    sql=BackendTests.sql

    def run_native(self,issueid,*,manual=False):
        # Execute the actual producer entry body with real SDK/catalog/archive
        # proof. Stop at catalog dispatch so no publisher mutation can occur.
        config=self.mylar.CONFIG
        values=dict(ENABLE_META=True,CT_TAG_CR=True,CT_TAG_CBL=False,CBR2CBZ_ONLY=False,
                    CT_CBZ_OVERWRITE=False,COMICVINE_API='fixture',COMICVINE_URL='https://example.invalid',
                    CVAPI_RATE=2,CMTAG_VOLUME=False,CMTAG_START_YEAR_AS_VOLUME=False,SETDEFAULTVOLUME=False)
        for name,value in values.items():setattr(config,name,value)
        self.mylar.logger=Mock()
        source=ast.parse((Path(__file__).parent/'tagger_native.py').read_text())
        function=next(node for node in source.body if isinstance(node,ast.FunctionDef) and node.name=='run')
        self.catalog=Mock(side_effect=RuntimeError('controlled stop after entry admission'))
        self.state=Mock(side_effect=AssertionError('state must not be touched'))
        scope=dict(__package__='mylar',re=re,uuid=uuid,catalog=self.catalog,state=self.state)
        exec(compile(ast.Module(body=[function],type_ignores=[]),'actual-native-run','exec'),scope)
        with patch.dict(sys.modules,{
            'mylar.tagger_lookup':types.SimpleNamespace(lookup=Mock()),
            'mylar.publication_transaction':transaction,
            'mylar.tagger_service':types.SimpleNamespace(Service=Mock())}):
            return scope['run'](str(self.incoming.parent),filename=str(self.incoming),
                                issueid=issueid,manualmeta=manual)

    def test_direct_wrong_owner_stops_before_catalog_state_and_fence(self):
        self.registered();self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',None,'Snatched'))
        before=(self.incoming.read_bytes(),self.database.read_bytes())
        with self.assertRaises(native.Review):self.run_native('999')
        self.catalog.assert_not_called();self.state.assert_not_called()
        self.assertEqual(before,(self.incoming.read_bytes(),self.database.read_bytes()))
        self.assertFalse(self.writer.fenced(tagger=True))

    def test_direct_manual_wrong_owner_returns_retained_review(self):
        self.registered();self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',None,'Snatched'))
        result=self.run_native('999',manual=True)
        self.assertEqual(result.state,'review');self.assertFalse(result.valid_for(self.incoming))
        self.catalog.assert_not_called();self.state.assert_not_called()
        self.assertFalse(self.writer.fenced(tagger=True))

    def test_direct_correct_owner_reaches_catalog_after_fresh_proof(self):
        self.registered();result=self.run_native('123')
        self.assertEqual(result.state,'unsupported')
        self.catalog.assert_called_once_with('123');self.state.assert_not_called()
        self.assertFalse(self.writer.fenced(tagger=True))


class ConvertedTests(unittest.TestCase):
    setUp=BackendTests.setUp
    call=BackendTests.call
    bootstrap=BackendTests.bootstrap
    prepare=BackendTests.prepare
    registered=BackendTests.registered
    sql=BackendTests.sql

    def test_changed_current_owner_during_xml_check_cannot_complete(self):
        self.registered();digest=guard.file_hash(self.incoming)[1]
        key=converted_tagging.admit(json.dumps(dict(version=1,path=str(self.incoming),sha256=digest)),self.store)['key']
        def inspected(path):
            self.sql('UPDATE issues SET Location=? WHERE IssueID=?',('missing-owner.cbz','123'))
            return digest,True
        queue=converted_tagging.Queue(self.store,lambda *args:dict(issueid='123',comicid='456'),
              self.runtime.operation,inspected,Mock(),Mock(),lambda:True,
              publication=converted_tagging.publication)
        queue.tick();job=self.store.get('converted_tag',key)
        self.assertEqual(job['phase'],'review');self.assertEqual(job['attempts'],0)
        self.assertNotIn('token',job);queue.tag.assert_not_called();queue.recover.assert_not_called()

    def test_production_poll_opens_store_and_records_review_under_writer(self):
        self.registered();self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',None,'Snatched'))
        key=converted_tagging.admit(json.dumps(dict(version=1,path=str(self.incoming),
                                   sha256=guard.file_hash(self.incoming)[1])),self.store)['key']
        self.mylar.CONFIG.POST_PROCESSING=True;self.mylar.APILOCK=False
        self.mylar.PP_QUEUE=types.SimpleNamespace(empty=lambda:True)
        def journal():
            self.assertTrue(self.writer.local[1].depth)
            return self.store
        original_set=self.store.set
        def save(*args,**kwargs):
            self.assertTrue(self.writer.local[1].depth)
            return original_set(*args,**kwargs)
        with patch.object(converted_tagging,'store',side_effect=journal),\
                patch.object(converted_tagging,'catalog',return_value=dict(issueid='999',comicid='888')),\
                patch.object(self.store,'set',side_effect=save),\
                patch.object(converted_tagging,'recover') as replay,\
                patch.object(converted_tagging,'inspect_archive') as inspect:
            converted_tagging.poll()
        self.assertEqual(self.store.get('converted_tag',key)['phase'],'review')
        self.assertFalse(self.writer.local[1].depth);replay.assert_not_called();inspect.assert_not_called()

    def test_missing_owner_cannot_reconcile_registered_payload_from_filename(self):
        self.registered();reconcile=Mock(return_value=True)
        self.mylar.db=types.SimpleNamespace(DBConnection=lambda:types.SimpleNamespace(select=lambda *args:[]))
        self.mylar.converted_catalog=types.SimpleNamespace(reconcile=reconcile)
        with patch.dict(sys.modules,{'mylar.workflow_store':types.SimpleNamespace(identifier=lambda value:value)}):
            with self.writer.hold(),self.assertRaises(native.Review):
                converted_tagging.catalog(str(self.incoming),guard.file_hash(self.incoming)[1])
        reconcile.assert_not_called();self.assertTrue(self.incoming.exists())

    def test_known_wrong_conversion_enters_durable_review_before_replay_or_xml(self):
        self.registered();self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',None,'Snatched'))
        key=converted_tagging.admit(json.dumps(dict(version=1,path=str(self.incoming),
                                   sha256=guard.file_hash(self.incoming)[1])),self.store)['key']
        match=Mock(return_value=dict(issueid='999',comicid='888'))
        inspect=Mock(return_value=(guard.file_hash(self.incoming)[1],True))
        replay=Mock(return_value='added');tag=Mock(return_value='added')
        job=self.store.get('converted_tag',key);job['token']='b'*32
        self.store.set('converted_tag',key,job)
        queue=converted_tagging.Queue(self.store,match,self.runtime.operation,inspect,tag,
                                     replay,lambda:True,publication=converted_tagging.publication)
        before=(self.incoming.read_bytes(),self.database.read_bytes())
        queue.tick();job=self.store.get('converted_tag',key)
        self.assertEqual(job['phase'],'review');self.assertEqual(job['attempts'],0)
        self.assertEqual(job['token'],'b'*32)
        inspect.assert_not_called();replay.assert_not_called();tag.assert_not_called()
        self.assertEqual(before,(self.incoming.read_bytes(),self.database.read_bytes()))
        queue.tick();self.assertEqual(match.call_count,1)

    def test_unbound_replay_does_not_prepare_state_or_capture_handoff(self):
        self.registered();state=Mock(side_effect=AssertionError('must not prepare state'))
        self.mylar.tagger_native=types.SimpleNamespace(state=state)
        before=(self.incoming.read_bytes(),self.database.read_bytes())
        with self.writer.hold(),self.assertRaises(native.Review) as raised:
            converted_tagging.recover(dict(path=str(self.incoming),issueid='123',comicid='456',token='b'*32))
        self.assertEqual(raised.exception.reason,'tagging-replay-unbound');state.assert_not_called()
        self.assertEqual(before,(self.incoming.read_bytes(),self.database.read_bytes()))



class ServicePublicationTests(unittest.TestCase):
    setUp=BackendTests.setUp
    call=BackendTests.call
    bootstrap=BackendTests.bootstrap
    prepare=BackendTests.prepare
    registered=BackendTests.registered
    sql=BackendTests.sql
    def build_service(self, job=None):
        if job is None:
            cache=self.root/'service-cache';cache.mkdir(mode=0o700)
            self.publisher=tagger_adapter.Publisher(self.root/'service-journal');staging=None
        else:
            paths=[Path(row[0]) for row in job.value['recovery']['directories']]
            cache=paths[2]
            self.publisher=tagger_pack.Publisher(paths[1],self.root)
            staging=tagger_staging.Staging(paths[2],paths[3])
        self.replay=Mock(wraps=self.publisher.recover_pending)
        self.publisher.recover_pending=self.replay
        self.lookup=Mock(side_effect=AssertionError('lookup must not run'))
        coordinate=self.runtime.operation if job is None else job.coordinate
        self.service=tagger_service.Service(self.publisher,cache,self.lookup,
                              tagger_handoff,coordinate,publication=job,staging=staging)
        return self.service

    def service_tag(self, **options):
        return self.service.tag(self.incoming, issueid=options.pop('issueid','123'),
                                volumeid='456', **options)

    @staticmethod
    def save_metadata(path,metadata,**kwargs):
        with zipfile.ZipFile(path) as archive:
            entries=[(info,archive.read(info)) for info in archive.infolist()
                     if info.filename!='ComicInfo.xml']
        with zipfile.ZipFile(path,'w') as archive:
            for info,data in entries:archive.writestr(info,data)
            archive.writestr('ComicInfo.xml','<ComicInfo><Series>Fixture Annual</Series><Number>1</Number></ComicInfo>')
        return TagResult('saved')

    def provider(self):
        self.service.lookup=lambda **kwargs:types.SimpleNamespace(state='ok',metadata={'series':'Fixture Annual','issue':'1'})

    def policy(self, **options):
        value=dict(manualmeta=False,enabled=True,comicrack=True,comicbooklover=False,
                   conversion_only=False,overwrite=False,volume=None,reading_order=None,
                   age_rating=None,volumeid='456',expected_digest=None)
        value.update(options);return value

    def native_tag(self, *, manual=False, overwrite=False, lookup=None, enabled=True, action=None, catalog_volume="456"):
        """Run the actual native entry and state binding with real producers."""
        config=self.mylar.CONFIG
        for name,value in dict(TAGGER_BACKEND="modern",ENABLE_META=enabled,CT_TAG_CR=True,CT_TAG_CBL=False,
                CBR2CBZ_ONLY=False,CT_CBZ_OVERWRITE=overwrite,COMICVINE_API='fixture',
                COMICVINE_URL='https://example.invalid',CVAPI_RATE=2,CMTAG_VOLUME=False,
                CMTAG_START_YEAR_AS_VOLUME=False,SETDEFAULTVOLUME=False).items():
            setattr(config,name,value)
        self.mylar.logger=Mock()
        tree=ast.parse((Path(__file__).parent/'tagger_native.py').read_text())
        functions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in ('run','state')]
        namespace=dict(__package__='mylar',re=re,uuid=uuid,hashlib=hashlib,json=json,os=os,
                       stat=transaction.stat,sync=transaction.sync,Publisher=tagger_pack.Publisher,
                       Staging=tagger_staging.Staging,catalog=lambda issueid:(issueid,catalog_volume,{}))
        exec(compile(ast.Module(body=functions,type_ignores=[]),'actual-native-producer','exec'),namespace)
        provider=lookup or Mock(side_effect=AssertionError('no-overwrite must not query provider'))
        with patch.dict(sys.modules,{'mylar.publication_transaction':transaction,
                'mylar.tagger_lookup':types.SimpleNamespace(lookup=provider),
                'mylar.tagger_service':tagger_service,
                'mylar.tagger_archive':tagger_archive,'mylar.tagger_adapter':tagger_adapter,
                'mylar.workflow_store':workflow_store}):
            if action is not None:
                with patch.object(self.mylar,'tagger_native',types.SimpleNamespace(
                        run=namespace['run'],state=namespace['state'],catalog=namespace['catalog'])):
                    return action()
            return namespace['run'](str(self.incoming.parent),filename=str(self.incoming),
                                     issueid='123',manualmeta=manual)

    def use_real_native_runtime(self):
        tree=ast.parse((Path(__file__).parent/'native_writers.py').read_text())
        names={'_mode','operation','owner','admission','active','publication_mode'}
        functions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
        runtime=types.ModuleType('mylar.native_writers')
        runtime.__dict__.update(__package__='mylar',Path=Path,threading=threading,
            contextmanager=contextmanager,Writer=type(self.writer),_LOCAL=threading.local(),
            _MODE_LOCK=threading.Lock(),_OPERATIONS=0,_PUBLICATION=True,_STARTUP_COMPLETE=True)
        exec(compile(ast.Module(body=functions,type_ignores=[]),'actual-native-runtime','exec'),runtime.__dict__)
        self.runtime=runtime;self.mylar.native_writers=runtime
        aliases=patch.dict(sys.modules,{'mylar.native_writers':runtime,'mylar.publication_guard':guard})
        aliases.start();self.addCleanup(aliases.stop)

    def test_real_native_operation_preserves_failed_publication_review_and_hold(self):
        self.registered();self.use_real_native_runtime();before=self.incoming.read_bytes()
        with self.assertRaises(native.Review):
            with self.runtime.operation():
                self.native_tag(overwrite=True,lookup=lambda **kwargs:types.SimpleNamespace(state='failed'))
        self.assertEqual(self.incoming.read_bytes(),before)
        self.assertTrue(transaction.present(self.writer));self.assertTrue(self.writer.fenced(tagger=True))
        with self.assertRaises(guard.Unavailable),self.runtime.operation():self.fail('held operation admitted')

    def test_real_native_manual_review_crosses_owning_admission_without_unsupported_fallback(self):
        self.registered();self.incoming=self.source
        self.use_real_native_runtime();before=self.incoming.read_bytes()
        provider=lambda **kwargs:types.SimpleNamespace(state='ok',metadata={'series':'Fixture Annual','issue':'1'})
        with patch.object(tagger_adapter,'save',side_effect=self.save_metadata):
            result=self.native_tag(manual=True,overwrite=True,lookup=provider)
        self.assertEqual(result.state,'review');self.assertEqual(self.incoming.read_bytes(),before)
        self.assertTrue(transaction.present(self.writer));self.assertTrue(self.writer.fenced(tagger=True))

    def test_real_native_automatic_success_clears_own_hold_before_admission_exit(self):
        self.registered();self.use_real_native_runtime()
        with self.runtime.operation():result=self.native_tag()
        self.assertNotEqual(result,'fail');self.assertTrue(Path(result).is_file())
        self.assertFalse(transaction.present(self.writer));self.assertFalse(self.writer.fenced(tagger=True))

    def test_actual_native_automatic_producer_completes_owned_temporary_output(self):
        self.registered();before=self.incoming.read_bytes()
        result=self.native_tag()
        self.assertIsInstance(result,str);self.assertNotEqual(result,'fail')
        self.assertEqual(Path(result).read_bytes(),before);self.assertEqual(self.incoming.read_bytes(),before)
        self.assertFalse(self.writer.fenced(tagger=True));self.assertFalse(transaction.present(self.writer))

    def test_disabled_native_tagging_preserves_eligibility_without_preparing_a_job(self):
        self.registered();before=self.incoming.read_bytes();result=self.native_tag(enabled=False)
        self.assertEqual(result.state,'unsupported');self.assertEqual(self.incoming.read_bytes(),before)
        self.assertFalse(transaction.present(self.writer));self.assertFalse(self.writer.fenced(tagger=True))
        self.assertFalse((self.writer.root.parent/'modern-tagger-v2').exists())

    def test_unsupported_native_source_preserves_eligibility_without_an_orphan_fence(self):
        self.registered();replacement=self.incoming.with_suffix('.cbr');self.incoming.rename(replacement)
        self.incoming=replacement;before=self.incoming.read_bytes();result=self.native_tag()
        self.assertEqual(result.state,'unsupported');self.assertEqual(self.incoming.read_bytes(),before)
        self.assertFalse(transaction.present(self.writer));self.assertFalse(self.writer.fenced(tagger=True))

    def test_native_recovery_state_failure_is_review_before_tagging_fallback(self):
        self.registered();TransactionTests.recovery_state(self);before=self.incoming.read_bytes()
        binding=self.writer.root/'tagger-state-v2.identity';binding.write_text('changed retained state\n')
        with self.assertRaises(native.Review):self.native_tag()
        self.assertEqual(self.incoming.read_bytes(),before);self.assertEqual(binding.read_text(),'changed retained state\n')

    def test_second_native_job_preserves_verified_closed_receipt_without_replaying_it(self):
        self.registered();before=self.incoming.read_bytes();first=self.native_tag()
        receipts=self.writer.root.parent/'modern-tagger-v2/journal-v2'
        receipt=next(receipts.glob('*.json'));retained=receipt.read_bytes()
        with patch.object(tagger_pack.Publisher,'recover_pending',side_effect=AssertionError('closed history cannot replay')):
            second=self.native_tag()
        self.assertNotEqual(first,second);self.assertEqual(Path(second).read_bytes(),before)
        self.assertEqual(receipt.read_bytes(),retained);self.assertTrue(Path(first).is_file())
        self.assertFalse(self.writer.fenced(tagger=True));self.assertFalse(transaction.present(self.writer))

    def test_changed_closed_receipt_holds_new_job_without_replaying_or_overwriting_history(self):
        self.registered();before=self.incoming.read_bytes();first=self.native_tag()
        receipts=self.writer.root.parent/'modern-tagger-v2/journal-v2'
        receipt=next(receipts.glob('*.json'));row=json.loads(receipt.read_text())
        row['metadata']='updated';receipt.write_text(json.dumps(row));retained=receipt.read_bytes()
        with self.assertRaises(native.Review),patch.object(tagger_pack.Publisher,'recover_pending',side_effect=AssertionError('tampered history cannot replay')):
            self.native_tag()
        self.assertEqual(receipt.read_bytes(),retained);self.assertEqual(self.incoming.read_bytes(),before)
        self.assertTrue(Path(first).is_file());self.assertTrue(transaction.present(self.writer))

    def test_consumed_temporary_output_does_not_replay_or_block_verified_closed_history(self):
        self.registered();first=self.native_tag();Path(first).unlink()
        second=self.native_tag()
        self.assertTrue(Path(second).is_file());self.assertFalse(Path(first).exists())
        self.assertFalse(transaction.present(self.writer));self.assertFalse(self.writer.fenced(tagger=True))

    def test_missing_terminal_witness_keeps_closed_receipt_and_requires_review(self):
        self.registered();first=self.native_tag();before=self.incoming.read_bytes()
        next((self.writer.root/'tagger-completed-v1').glob('*.json')).unlink()
        receipt=next((self.writer.root.parent/'modern-tagger-v2/journal-v2').glob('*.json'))
        retained=receipt.read_bytes()
        with self.assertRaises(native.Review):self.native_tag()
        self.assertEqual(receipt.read_bytes(),retained);self.assertTrue(Path(first).is_file())
        self.assertEqual(self.incoming.read_bytes(),before);self.assertTrue(transaction.present(self.writer))

    def test_boolean_terminal_witness_version_cannot_authorize_historical_reads(self):
        self.registered();first=self.native_tag()
        witness=next((self.writer.root/'tagger-completed-v1').glob('*.json'))
        row=json.loads(witness.read_text());row['version']=True;witness.write_text(json.dumps(row))
        retained=witness.read_bytes()
        with self.assertRaises(native.Review):self.native_tag()
        self.assertEqual(witness.read_bytes(),retained);self.assertTrue(Path(first).is_file())

    def test_terminal_witness_never_grants_old_token_replay_to_a_new_job(self):
        self.registered();first=self.native_tag()
        receipts=self.writer.root.parent/'modern-tagger-v2/journal-v2'
        receipt=next(receipts.glob('*.json'));token=receipt.stem;retained=receipt.read_bytes()
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','b'*32,self.policy(),modern=True) as job:
                self.build_service(job)
                with self.assertRaises(native.Review):self.publisher.recover(token)
                self.assertEqual(receipt.read_bytes(),retained);self.assertTrue(Path(first).is_file())
                self.assertTrue(self.writer.fenced(tagger=True));self.assertTrue(job.path.exists())

    def test_witness_only_job_tampering_cannot_authorize_closed_history(self):
        self.registered();first=self.native_tag()
        receipt=next((self.writer.root.parent/'modern-tagger-v2/journal-v2').glob('*.json'))
        record=json.loads(receipt.read_text());before=receipt.read_bytes()
        witness=self.writer.root/'tagger-completed-v1'/(receipt.stem+'.json')
        original=json.loads(witness.read_text())
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','b'*32,self.policy(),modern=True) as job:
                self.build_service(job)
                for field in ('census','owner','source','policy','payload'):
                    with self.subTest(field=field):
                        row=json.loads(json.dumps(original))
                        if field=='census':row['job']['census']['epoch']='0'*64
                        elif field=='owner':row['job']['owner']['issueid']='999'
                        elif field=='policy':row['job']['policy']['overwrite']=True
                        else:row['job'][field]='changed retained fact'
                        witness.write_text(json.dumps(row))
                        with self.assertRaises((native.Review,guard.Unavailable)):
                            job.closed_history(self.publisher,record)
                self.assertEqual(receipt.read_bytes(),before);self.assertTrue(Path(first).is_file())

    def test_terminal_witness_change_before_release_keeps_own_fence_and_all_outputs(self):
        self.registered();TransactionTests.recovery_state(self)
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,self.policy(),modern=True) as job:
                self.build_service(job);result=self.service_tag();write=transaction._write
                def changed(path,value,**kwargs):
                    write(path,value,**kwargs)
                    if path.parent==job.history:
                        row=json.loads(path.read_text());row['job']['census']['epoch']='0'*64
                        path.write_text(json.dumps(row))
                with patch.object(transaction,'_write',side_effect=changed),self.assertRaises(native.Review):
                    job.complete(self.publisher,self.service.staging,result)
                self.assertTrue(self.writer.fenced(tagger=True));self.assertTrue(job.path.exists())
                self.assertTrue(Path(result).is_file());self.assertEqual(job.value['phase'],'completing')

    def test_witness_only_completion_changes_cannot_authorize_historical_reads(self):
        self.registered();first=self.native_tag()
        receipt=next((self.writer.root.parent/'modern-tagger-v2/journal-v2').glob('*.json'))
        record=json.loads(receipt.read_text());retained=receipt.read_bytes()
        witness=self.writer.root/'tagger-completed-v1'/(receipt.stem+'.json')
        original=json.loads(witness.read_text())
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','b'*32,self.policy(),modern=True) as job:
                self.build_service(job)
                for field in ('sha256','stage','target','signature'):
                    with self.subTest(field=field):
                        row=json.loads(json.dumps(original));terminal=row['job']['completion']
                        if field=='sha256':terminal[field]='0'*64
                        elif field=='stage':terminal[field]=None
                        elif field=='target':terminal[field]='/foreign/missing.cbz'
                        else:terminal[field][4]+=1
                        witness.write_text(json.dumps(row))
                        with self.assertRaises(native.Review):job.closed_history(self.publisher,record)
                self.assertEqual(receipt.read_bytes(),retained);self.assertTrue(Path(first).is_file())

    def test_terminal_witness_change_after_marker_removal_keeps_the_intent_hold(self):
        self.registered();TransactionTests.recovery_state(self)
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,self.policy(),modern=True) as job:
                self.build_service(job);result=self.service_tag();verify=job.verify_completion
                def changed():
                    if not self.writer.fenced(tagger=True):
                        witness=job.history/('a'*32+'.json');row=json.loads(witness.read_text())
                        row['job']['policy']['overwrite']=True;witness.write_text(json.dumps(row))
                    return verify()
                with patch.object(job,'verify_completion',side_effect=changed),self.assertRaises(native.Review):
                    job.complete(self.publisher,self.service.staging,result)
                self.assertFalse(self.writer.fenced(tagger=True));self.assertTrue(job.path.exists())
                self.assertTrue(Path(result).is_file());self.assertEqual(job.value['phase'],'completing')

    def test_actual_native_manual_no_overwrite_completes_exact_handoff(self):
        self.registered();before=self.incoming.read_bytes()
        result=self.native_tag(manual=True)
        self.assertTrue(result.valid_for(self.incoming));self.assertEqual(self.incoming.read_bytes(),before)
        self.assertFalse(self.writer.fenced(tagger=True));self.assertFalse(transaction.present(self.writer))

    def test_actual_native_metadata_output_preserves_acquisition_and_pages(self):
        self.registered();before=self.incoming.read_bytes()
        provider=lambda **kwargs:types.SimpleNamespace(state='ok',metadata={'series':'Fixture Annual','issue':'1'})
        with patch.object(tagger_adapter,'save',side_effect=self.save_metadata):
            result=self.native_tag(overwrite=True,lookup=provider)
        self.assertNotEqual(result,'fail');self.assertNotEqual(Path(result).read_bytes(),before)
        self.assertEqual(self.incoming.read_bytes(),before)
        with self.writer.hold():
            self.assertEqual(native.require(result,issueid='123')['inventory']['payload'],
                             native.require(self.incoming,issueid='123')['inventory']['payload'])
        self.assertFalse(transaction.present(self.writer));self.assertFalse(self.writer.fenced(tagger=True))

    def test_actual_native_changed_manual_publication_retains_before_displacement(self):
        self.registered();self.incoming=self.source;before=self.incoming.read_bytes()
        provider=lambda **kwargs:types.SimpleNamespace(state='ok',metadata={'series':'Fixture Annual','issue':'1'})
        with patch.object(tagger_adapter,'save',side_effect=self.save_metadata):
            result=self.native_tag(manual=True,overwrite=True,lookup=provider)
        self.assertEqual(result.state,'review');self.assertEqual(self.incoming.read_bytes(),before)
        self.assertTrue(transaction.present(self.writer));self.assertTrue(self.writer.fenced(tagger=True))

    def test_manual_metadata_on_retained_copy_preserves_registered_archive(self):
        self.registered();original=self.source.read_bytes();before=self.incoming.read_bytes()
        provider=lambda **kwargs:types.SimpleNamespace(state='ok',metadata={'series':'Fixture Annual','issue':'1'})
        with patch.object(tagger_adapter,'save',side_effect=self.save_metadata):
            result=self.native_tag(manual=True,overwrite=True,lookup=provider)
        self.assertEqual(result.state,'committed');self.assertTrue(result.valid_for(self.incoming))
        self.assertNotEqual(self.incoming.read_bytes(),before);self.assertEqual(self.source.read_bytes(),original)
        self.assertFalse(transaction.present(self.writer));self.assertFalse(self.writer.fenced(tagger=True))
        with self.writer.hold():
            self.assertEqual(native.require(self.incoming,issueid='123')['inventory']['payload'],
                             native.require(self.source,issueid='123')['inventory']['payload'])

    def test_real_converted_followup_publishes_and_completes_once(self):
        self.registered();original=self.source.read_bytes()
        folder=self.library/'converted';folder.mkdir()
        self.incoming=folder/'converted.cbz'
        with zipfile.ZipFile(self.incoming,'w') as archive:
            archive.writestr('01.jpg',b'distinct converted publication pages')
        self.sql('ALTER TABLE comics ADD COLUMN AgeRating TEXT')
        self.sql('INSERT INTO comics (ComicID,ComicLocation) VALUES (?,?)',('888',str(folder)))
        self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',self.incoming.name,'Downloaded'))
        self.sql('CREATE TABLE storyarcs (ComicID TEXT,IssueID TEXT,StoryArc TEXT,ReadingOrder TEXT)')
        database=self.database
        class Database:
            def select(_,sql,args):
                with closing(sqlite3.connect(database)) as db:
                    db.row_factory=sqlite3.Row
                    return db.execute(sql,args).fetchall()
        self.mylar.db=types.SimpleNamespace(DBConnection=Database)
        digest=guard.file_hash(self.incoming)[1]
        key=converted_tagging.admit(json.dumps(dict(version=1,path=str(self.incoming),sha256=digest)),self.store)['key']
        self.use_real_native_runtime()
        queue=converted_tagging.Queue(self.store,converted_tagging.catalog,
              self.runtime.operation,converted_tagging.inspect_archive,converted_tagging.tag,
              converted_tagging.recover,lambda:True,publication=converted_tagging.publication)
        provider=lambda **kwargs:types.SimpleNamespace(state='ok',metadata={'series':'Fixture Annual','issue':'1'})
        with patch.object(tagger_adapter,'save',side_effect=self.save_metadata):
            self.native_tag(lookup=provider,action=queue.tick,catalog_volume="888")
        job=self.store.get('converted_tag',key)
        self.assertEqual((job['phase'],job['attempts']),('completed',1))
        self.assertIsNotNone(tagger_archive.snapshot(self.incoming).xml)
        self.assertEqual(self.source.read_bytes(),original)
        self.assertFalse(transaction.present(self.writer));self.assertFalse(self.writer.fenced(tagger=True))
        before=self.incoming.read_bytes();queue.tick()
        self.assertEqual(self.incoming.read_bytes(),before)
        self.assertEqual(self.store.get('converted_tag',key),job)

    @unittest.skipUnless(Path('/opt/comictagger/bin/comictagger').is_file(),
                         'pinned ComicTagger executable required; custom image gate')
    def test_real_sdk_guarded_retained_copy_publication(self):
        from test_modern_tagger import png
        with zipfile.ZipFile(self.source,'w') as archive:
            archive.writestr('01.png',png())
            archive.writestr('02.png',png())
            archive.writestr('extras/credit.txt',b'Preserve publication credit')
            archive.writestr('ComicInfo.xml','<ComicInfo><Series>Original fixture</Series><Number>1</Number></ComicInfo>')
        shutil.copy2(self.source,self.incoming)
        self.registered();original=self.source.read_bytes()
        provider=lambda **kwargs:types.SimpleNamespace(state='ok',metadata={'series':'Fixture Annual','issue':'1'})
        result=self.native_tag(manual=True,overwrite=True,lookup=provider)
        self.assertEqual(result.state,'committed');self.assertTrue(result.valid_for(self.incoming))
        self.assertEqual(self.source.read_bytes(),original)
        self.assertEqual(tagger_archive.snapshot(self.incoming).xml is not None,True)
        self.assertFalse(transaction.present(self.writer));self.assertFalse(self.writer.fenced(tagger=True))
        with self.writer.hold():
            self.assertEqual(native.require(self.incoming,issueid='123')['inventory']['payload'],
                             native.require(self.source,issueid='123')['inventory']['payload'])

    def test_expired_in_place_proof_does_not_recreate_lost_recovery_state(self):
        self.registered();original=self.source.read_bytes();captured=[]
        provider=lambda **kwargs:types.SimpleNamespace(state='ok',metadata={'series':'Fixture Annual','issue':'1'})
        def interrupted(stage):
            if stage=='after_displace':
                captured.append(transaction.current())
                self.sql('UPDATE issues SET Location=? WHERE IssueID=?',('missing-owner.cbz','123'))
        with patch.object(tagger_adapter,'save',side_effect=self.save_metadata),\
                patch.object(tagger_adapter,'_checkpoint',side_effect=interrupted):
            result=self.native_tag(manual=True,overwrite=True,lookup=provider)
        self.assertEqual(result.state,'review');self.assertEqual(len(captured),1)
        job=captured[0];journal=Path(job.value['recovery']['directories'][1][0])
        shutil.rmtree(journal)
        with self.writer.hold(allow_tagger_pending=True):
            with self.assertRaises((native.Review,guard.Unavailable,OSError)):
                job.proof(self.incoming,original=True)
        self.assertFalse(journal.exists())
        self.assertEqual(self.source.read_bytes(),original)
        self.assertTrue(transaction.present(self.writer));self.assertTrue(self.writer.fenced(tagger=True))

    def test_retained_copy_owner_drift_after_displacement_holds_before_link(self):
        self.registered();before=self.incoming.read_bytes();original=self.source.read_bytes()
        provider=lambda **kwargs:types.SimpleNamespace(state='ok',metadata={'series':'Fixture Annual','issue':'1'})
        def changed(stage):
            if stage=='after_displace':self.sql('UPDATE issues SET Location=? WHERE IssueID=?',('missing-owner.cbz','123'))
        with patch.object(tagger_adapter,'save',side_effect=self.save_metadata),\
                patch.object(tagger_adapter,'_checkpoint',side_effect=changed):
            result=self.native_tag(manual=True,overwrite=True,lookup=provider)
        self.assertEqual(result.state,'review');self.assertFalse(self.incoming.exists())
        folder=next(self.incoming.parent.glob('.mylar-tag-*'))
        self.assertEqual((folder/'displaced.cbz').read_bytes(),before)
        self.assertEqual((folder/'original.cbz').read_bytes(),before)
        self.assertEqual(self.source.read_bytes(),original)
        self.assertTrue(transaction.present(self.writer));self.assertTrue(self.writer.fenced(tagger=True))

    def test_actual_native_failed_lookup_retains_owned_intent_before_failure_fallback(self):
        self.registered();before=self.incoming.read_bytes()
        with self.assertRaises(native.Review):
            self.native_tag(overwrite=True,lookup=lambda **kwargs:types.SimpleNamespace(state='failed'))
        self.assertEqual(self.incoming.read_bytes(),before)
        self.assertTrue(transaction.present(self.writer));self.assertTrue(self.writer.fenced(tagger=True))

    def test_direct_service_wrong_owner_retains_before_replay_lookup_and_receipt(self):
        self.registered();self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',None,'Snatched'))
        self.build_service();before=(self.incoming.read_bytes(),self.database.read_bytes())
        with self.assertRaises(native.Review):self.service_tag(issueid='999')
        self.replay.assert_not_called();self.lookup.assert_not_called()
        self.assertEqual(list(self.publisher.root.iterdir()),[])
        self.assertEqual(before,(self.incoming.read_bytes(),self.database.read_bytes()))

    def test_direct_service_correct_owner_requires_bound_producer_before_replay(self):
        self.registered();self.build_service()
        with self.assertRaises(native.Review) as raised:self.service_tag()
        self.assertEqual(raised.exception.reason,'tagging-producer-unbound')
        self.replay.assert_not_called();self.lookup.assert_not_called()
        self.assertFalse(self.writer.fenced(tagger=True))

    def test_owned_service_no_overwrite_returns_real_verified_temporary_archive(self):
        self.registered()
        before=self.incoming.read_bytes()
        TransactionTests.recovery_state(self)
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,self.policy(),modern=True) as job:
                self.build_service(job)
                with patch.object(tagger_adapter,'save',side_effect=AssertionError('no overwrite')):
                    result=self.service_tag()
                self.assertIs(type(result),str)
                self.assertEqual(Path(result).read_bytes(),before)
                self.assertEqual(self.incoming.read_bytes(),before)
                self.assertEqual(self.publisher.read('a'*32)['state'],'unchanged')
                self.assertTrue(self.publisher.read('a'*32)['cleaned'])
        self.replay.assert_not_called();self.lookup.assert_not_called()
        self.assertTrue(self.writer.fenced(tagger=True))
        self.assertTrue((self.writer.root/transaction.NAME).exists())

    def test_owned_service_actual_metadata_output_preserves_pages_and_original(self):
        self.registered();TransactionTests.recovery_state(self)
        before=self.incoming.read_bytes()
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,self.policy(overwrite=True),modern=True) as job:
                self.build_service(job)
                self.service.lookup=lambda **kwargs:types.SimpleNamespace(state='ok',metadata={'series':'Fixture Annual','issue':'1'})
                with patch.object(tagger_adapter,'save',side_effect=self.save_metadata):
                    result=self.service_tag(overwrite=True)
                self.assertIs(type(result),str);output=Path(result)
                self.assertNotEqual(output.read_bytes(),before)
                self.assertEqual(self.incoming.read_bytes(),before)
                self.assertEqual(job.proof(output)['inventory']['payload'],job.value['payload'])
                self.assertEqual(self.publisher.read('a'*32)['state'],'committed')
                self.assertTrue(self.publisher.read('a'*32)['cleaned'])
                receipt=self.service.staging.receipts/('a'*32+'.json')
                self.assertEqual(self.service.staging.read(receipt)['state'],'ready')
                job.complete(self.publisher,self.service.staging,output)
                self.assertFalse(self.writer.fenced(tagger=True));self.assertFalse(job.path.exists())
        self.replay.assert_not_called();self.assertFalse(self.writer.fenced(tagger=True))

    def test_direct_native_publisher_requires_job_before_any_receipt_or_replay(self):
        self.registered();paths,_=TransactionTests.recovery_state(self)
        publisher=tagger_pack.Publisher(paths[1],self.root)
        receipt=publisher.receipt('b'*32);receipt.write_bytes(b'foreign retained')
        with self.writer.hold(allow_tagger_pending=True):
            with self.assertRaises(native.Review):publisher.tag(self.incoming,{},token='a'*32)
            with self.assertRaises(native.Review):list(publisher.recover_pending())
        self.assertEqual(receipt.read_bytes(),b'foreign retained')
        self.assertEqual(len(list(paths[1].iterdir())),1)
        self.assertFalse((self.incoming.parent/('.mylar-tag-'+'a'*32)).exists())

    def test_changed_owner_during_cli_keeps_every_copy_before_publish_or_pack_finish(self):
        self.registered();TransactionTests.recovery_state(self);before=self.incoming.read_bytes()
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,self.policy(overwrite=True),modern=True) as job:
                self.build_service(job);self.provider()
                def changed(path,metadata,**kwargs):
                    result=self.save_metadata(path,metadata,**kwargs)
                    self.sql('UPDATE issues SET Location=? WHERE IssueID=?',('missing-owner.cbz','123'))
                    return result
                with patch.object(tagger_adapter,'save',side_effect=changed),                        patch.object(tagger_pack.pack_bindings,'finalize') as finish,                        self.assertRaises(native.Review):self.service_tag(overwrite=True)
                finish.assert_not_called()
                target=self.service.cache/('mylar_modern_'+'a'*32)/self.incoming.name
                self.assertEqual(target.read_bytes(),before)
                record=json.loads(self.publisher.receipt('a'*32).read_text())
                self.assertEqual(record['state'],'staged');self.assertFalse(record['cleaned'])
                folder=target.parent/('.mylar-tag-'+'a'*32)
                self.assertEqual((folder/'original.cbz').read_bytes(),before)
                self.assertTrue((folder/'tagged.cbz').exists());self.assertTrue((folder/'verified.cbz').exists())
        self.assertEqual(self.incoming.read_bytes(),before)

    def test_owner_change_after_displacement_holds_before_link_and_retains_original(self):
        self.registered();TransactionTests.recovery_state(self);before=self.incoming.read_bytes()
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,self.policy(overwrite=True),modern=True) as job:
                self.build_service(job);self.provider()
                def changed(stage):
                    if stage=='after_displace':
                        self.sql('UPDATE issues SET Location=? WHERE IssueID=?',('missing-owner.cbz','123'))
                with patch.object(tagger_adapter,'save',side_effect=self.save_metadata),                        patch.object(tagger_adapter,'_checkpoint',side_effect=changed),                        patch.object(tagger_pack.pack_bindings,'finalize') as finish,                        self.assertRaises(native.Review):self.service_tag(overwrite=True)
                finish.assert_not_called()
                target=self.service.cache/('mylar_modern_'+'a'*32)/self.incoming.name
                self.assertFalse(target.exists())
                record=json.loads(self.publisher.receipt('a'*32).read_text())
                self.assertEqual(record['state'],'publishing');self.assertFalse(record['cleaned'])
                folder=target.parent/('.mylar-tag-'+'a'*32)
                self.assertEqual((folder/'displaced.cbz').read_bytes(),before)
                self.assertTrue((folder/'original.cbz').exists());self.assertTrue((folder/'verified.cbz').exists())
        self.assertEqual(self.incoming.read_bytes(),before)

    def test_unknown_workspace_entry_prevents_pack_finish_and_copy_deletion(self):
        self.registered();TransactionTests.recovery_state(self);before=self.incoming.read_bytes()
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,self.policy(overwrite=True),modern=True) as job:
                self.build_service(job);self.provider()
                target=self.service.cache/('mylar_modern_'+'a'*32)/self.incoming.name
                folder=target.parent/('.mylar-tag-'+'a'*32)
                def changed(stage):
                    if stage=='after_unlink':(folder/'foreign.txt').write_bytes(b'retain this evidence')
                with patch.object(tagger_adapter,'save',side_effect=self.save_metadata),                        patch.object(tagger_adapter,'_checkpoint',side_effect=changed),                        patch.object(tagger_pack.pack_bindings,'finalize') as finish,                        self.assertRaises(native.Review) as raised:self.service_tag(overwrite=True)
                self.assertEqual(raised.exception.reason,'tagging-cleanup-scope-changed')
                finish.assert_not_called();self.assertEqual((folder/'foreign.txt').read_bytes(),b'retain this evidence')
                self.assertEqual((folder/'original.cbz').read_bytes(),before)
                self.assertEqual((folder/'displaced.cbz').read_bytes(),before)
                record=json.loads(self.publisher.receipt('a'*32).read_text());self.assertFalse(record['cleaned'])
        self.assertEqual(self.incoming.read_bytes(),before)

    def test_changed_in_place_job_holds_before_displacing_the_registered_library_name(self):
        self.registered();TransactionTests.recovery_state(self)
        self.incoming=self.source;before=self.source.read_bytes()
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.source,'123','a'*32,self.policy(manualmeta=True,overwrite=True),modern=True) as job:
                self.build_service(job);self.provider()
                with patch.object(tagger_adapter,'save',side_effect=self.save_metadata),                        self.assertRaises(native.Review) as raised:self.service_tag(manualmeta=True,overwrite=True)
                self.assertEqual(raised.exception.reason,'tagging-in-place-transition-unbound')
                self.assertEqual(self.source.read_bytes(),before)
                folder=self.source.parent/('.mylar-tag-'+'a'*32)
                self.assertFalse((folder/'displaced.cbz').exists())
                self.assertEqual((folder/'original.cbz').read_bytes(),before)
                self.assertTrue((folder/'verified.cbz').exists())
                record=json.loads(self.publisher.receipt('a'*32).read_text());self.assertFalse(record['cleaned'])

    def test_verified_automatic_terminal_receipts_clear_only_the_owned_fence_and_intent(self):
        self.registered();TransactionTests.recovery_state(self);before=self.incoming.read_bytes()
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,self.policy(),modern=True) as job:
                self.build_service(job);result=self.service_tag()
                target=Path(result);receipt=self.publisher.receipt('a'*32)
                accepted_receipt=receipt.read_bytes()
                stage=self.service.staging.receipts/('a'*32+'.json');accepted_stage=stage.read_bytes()
                job.complete(self.publisher,self.service.staging,target)
                self.assertEqual(job.value['phase'],'released')
                self.assertFalse(self.writer.fenced(tagger=True));self.assertFalse(job.path.exists())
                completed=json.loads(receipt.read_text());anchor=completed.pop('terminal_proof')
                self.assertEqual(completed,json.loads(accepted_receipt))
                self.assertEqual(anchor['version'],1);self.assertRegex(anchor['digest'],r'^[0-9a-f]{64}$')
                self.assertEqual(stage.read_bytes(),accepted_stage)
                self.assertEqual(self.incoming.read_bytes(),before);self.assertEqual(target.read_bytes(),before)
                self.runtime.admission(self.writer)
                with self.assertRaises(native.Review):native.require(target,issueid='123',transaction=job)
        self.assertFalse(self.writer.fenced(tagger=True))

    def test_verified_manual_no_overwrite_completion_preserves_registered_library_bytes(self):
        self.registered();TransactionTests.recovery_state(self)
        self.incoming=self.source;before=self.source.read_bytes()
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.source,'123','a'*32,self.policy(manualmeta=True),modern=True) as job:
                self.build_service(job);result=self.service_tag(manualmeta=True)
                self.assertEqual(result.state,'unchanged');self.assertTrue(result.valid_for(self.source))
                job.complete(self.publisher,self.service.staging,self.source)
                self.assertFalse(self.writer.fenced(tagger=True));self.assertFalse(job.path.exists())
                self.assertTrue(result.valid_for(self.source));self.assertEqual(self.source.read_bytes(),before)
                self.runtime.admission(self.writer)
        self.assertEqual(self.source.read_bytes(),before)

    def test_replaced_terminal_receipt_retains_the_fence_before_completion(self):
        self.registered();TransactionTests.recovery_state(self)
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,self.policy(),modern=True) as job:
                self.build_service(job);result=self.service_tag()
                receipt=self.publisher.receipt('a'*32);row=json.loads(receipt.read_text())
                row['correction_guard']['owner']['issueid']='999';receipt.write_text(json.dumps(row))
                with self.assertRaises(native.Review):job.complete(self.publisher,self.service.staging,result)
                self.assertTrue(self.writer.fenced(tagger=True));self.assertTrue(job.path.exists())
                self.assertEqual(json.loads(receipt.read_text())['correction_guard']['owner']['issueid'],'999')

    def test_new_foreign_pending_after_owned_unlink_keeps_terminal_intent(self):
        self.registered();TransactionTests.recovery_state(self)
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,self.policy(),modern=True) as job:
                self.build_service(job);result=self.service_tag();verify=job.verify_completion;calls=[]
                def replaced():
                    calls.append(True)
                    if not self.writer.fenced(tagger=True):self.writer.mark_tagger_pending()
                    return verify()
                with patch.object(job,'verify_completion',side_effect=replaced),self.assertRaises(native.Review):
                    job.complete(self.publisher,self.service.staging,result)
                self.assertEqual(job.value['phase'],'completing')
                self.assertTrue(self.writer.fenced(tagger=True));self.assertTrue(job.path.exists())
                self.assertEqual(os.fstat(job.pending_fd).st_nlink,0)
                self.assertNotEqual(self.writer.tagger_pending.stat().st_ino,os.fstat(job.pending_fd).st_ino)
                self.assertTrue(Path(result).exists())

    def test_failure_after_owned_fence_unlink_retains_intent_and_all_terminal_outputs(self):
        self.registered();TransactionTests.recovery_state(self)
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,self.policy(),modern=True) as job:
                self.build_service(job);result=self.service_tag();real_sync=transaction.sync
                def interrupted(path):
                    if not self.writer.fenced(tagger=True):raise OSError('controlled post-unlink fsync failure')
                    return real_sync(path)
                with patch.object(transaction,'sync',side_effect=interrupted),self.assertRaises(native.Review):
                    job.complete(self.publisher,self.service.staging,result)
                self.assertEqual(job.value['phase'],'completing');self.assertTrue(job.path.exists())
                self.assertFalse(self.writer.fenced(tagger=True));self.assertTrue(Path(result).exists())
                self.assertTrue(transaction.present(self.writer))
        self.assertTrue(job.path.exists())
        with self.assertRaises(native.Review):native.require(result,issueid='123',transaction=job)

    def test_final_intent_unlink_failure_keeps_completion_hold_and_outputs(self):
        self.registered();TransactionTests.recovery_state(self)
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,self.policy(),modern=True) as job:
                self.build_service(job);result=self.service_tag();unlink=Path.unlink
                def interrupted(path,*args,**kwargs):
                    if path==job.path:raise OSError('controlled intent unlink failure')
                    return unlink(path,*args,**kwargs)
                with patch.object(Path,'unlink',interrupted),self.assertRaises(native.Review):
                    job.complete(self.publisher,self.service.staging,result)
                self.assertEqual(job.value['phase'],'completing');self.assertTrue(job.path.exists())
                self.assertFalse(self.writer.fenced(tagger=True));self.assertTrue(Path(result).exists())

    def test_final_intent_fsync_failure_restores_typed_hold_without_deleting_outputs(self):
        self.registered();TransactionTests.recovery_state(self)
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,self.policy(),modern=True) as job:
                self.build_service(job);result=self.service_tag();real_sync=transaction.sync
                def interrupted(path):
                    if not job.path.exists():raise OSError('controlled final directory fsync failure')
                    return real_sync(path)
                with patch.object(transaction,'sync',side_effect=interrupted),self.assertRaises(native.Review):
                    job.complete(self.publisher,self.service.staging,result)
                self.assertEqual(job.value['phase'],'completing');self.assertTrue(job.path.exists())
                self.assertEqual(guard.private_json(job.path)['phase'],'completing')
                self.assertFalse(self.writer.fenced(tagger=True));self.assertTrue(Path(result).exists())

    def test_owned_service_policy_change_retains_before_replay_or_source_mutation(self):
        self.registered();before=self.incoming.read_bytes()
        TransactionTests.recovery_state(self)
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,self.policy(),modern=True) as job:
                self.build_service(job)
                with self.assertRaises(native.Review) as raised:self.service_tag(overwrite=True)
                self.assertEqual(raised.exception.reason,'tagging-policy-changed')
        self.replay.assert_not_called();self.lookup.assert_not_called()
        self.assertEqual(before,self.incoming.read_bytes())
        self.assertEqual(list(self.publisher.root.iterdir()),[])

    def test_owned_service_retains_foreign_receipt_without_recovery(self):
        self.registered()
        TransactionTests.recovery_state(self)
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,self.policy(),modern=True) as job:
                self.build_service(job);receipt=self.publisher.receipt('b'*32)
                receipt.write_bytes(b'foreign retained receipt');before=receipt.read_bytes()
                with self.assertRaises(native.Review) as raised:self.service_tag()
                self.assertEqual(raised.exception.reason,'tagging-replay-unbound')
                self.assertEqual(receipt.read_bytes(),before)
        self.replay.assert_not_called();self.lookup.assert_not_called()

    def test_service_objects_cannot_substitute_foreign_private_recovery_roots(self):
        self.registered();TransactionTests.recovery_state(self)
        foreign=self.root/'foreign-private';foreign.mkdir(mode=0o700)
        before=self.incoming.read_bytes()
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,self.policy(),modern=True) as job:
                self.build_service(job)
                for obj,field in ((self.service,'cache'),(self.publisher,'root'),
                                  (self.publisher,'config_root'),(self.service.staging,'root'),
                                  (self.service.staging,'receipts')):
                    with self.subTest(field=field),patch.object(obj,field,foreign),                            self.assertRaises(native.Review) as raised:
                        self.service_tag()
                    self.assertEqual(raised.exception.reason,'tagging-producer-state-changed')
                self.assertEqual(list(foreign.iterdir()),[])
                self.assertEqual(list(self.publisher.root.iterdir()),[])
                self.assertEqual(list(self.service.staging.receipts.iterdir()),[])
        self.replay.assert_not_called();self.lookup.assert_not_called()
        self.assertEqual(self.incoming.read_bytes(),before)

    def test_receipt_appearing_after_scan_is_retained_before_handoff(self):
        self.registered()
        TransactionTests.recovery_state(self)
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,self.policy(manualmeta=True),modern=True) as job:
                self.build_service(job);path=self.publisher.receipt('a'*32)
                original_receipt=self.publisher.receipt
                def appeared(token):
                    result=original_receipt(token)
                    result.write_bytes(b'late retained receipt')
                    return result
                with patch.object(self.publisher,'receipt',side_effect=appeared),                        patch.object(tagger_handoff,'capture') as capture,                        self.assertRaises(native.Review) as raised:
                    self.service_tag(manualmeta=True,publication_token='a'*32)
                self.assertEqual(raised.exception.reason,'tagging-replay-unbound')
                self.assertEqual(path.read_bytes(),b'late retained receipt')
                capture.assert_not_called()
        self.replay.assert_not_called();self.lookup.assert_not_called()

    def test_changed_caller_token_holds_before_publisher_receipt_creation(self):
        self.registered()
        TransactionTests.recovery_state(self)
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,self.policy(manualmeta=True),modern=True) as job:
                self.build_service(job)
                with self.assertRaises(native.Review) as raised:
                    self.service_tag(manualmeta=True,publication_token='b'*32)
                self.assertEqual(raised.exception.reason,'tagging-token-changed')
                self.assertEqual(list(self.publisher.root.iterdir()),[])
        self.replay.assert_not_called();self.lookup.assert_not_called()

    def test_failed_lookup_with_changed_source_is_review_before_failure_fallback(self):
        self.registered()
        TransactionTests.recovery_state(self)
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,self.policy(overwrite=True),modern=True) as job:
                self.build_service(job)
                def failed(**kwargs):
                    with zipfile.ZipFile(self.incoming,'w') as archive:archive.writestr('01.jpg',b'foreign pages')
                    return types.SimpleNamespace(state='timed_out')
                self.service.lookup=failed
                with self.assertRaises(native.Review):self.service_tag(overwrite=True)
                self.assertEqual(list(self.publisher.root.iterdir()),[])
        self.replay.assert_not_called()

    def test_lookup_source_change_holds_before_staging_or_publisher(self):
        self.registered();old=self.incoming.read_bytes()
        TransactionTests.recovery_state(self)
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,self.policy(overwrite=True),modern=True) as job:
                self.build_service(job)
                def changed(**kwargs):
                    with zipfile.ZipFile(self.incoming,'w') as archive:archive.writestr('01.jpg',b'foreign pages')
                    return types.SimpleNamespace(state='ok',metadata={'series':'Fixture'})
                self.service.lookup=changed
                with self.assertRaises(native.Review):self.service_tag(overwrite=True)
                self.assertNotEqual(self.incoming.read_bytes(),old)
                self.assertEqual(list(self.service.cache.iterdir()),[])
                self.assertEqual(list(self.publisher.root.iterdir()),[])
        self.replay.assert_not_called()


class TransactionTests(unittest.TestCase):
    setUp=BackendTests.setUp
    call=BackendTests.call
    bootstrap=BackendTests.bootstrap
    prepare=BackendTests.prepare
    registered=BackendTests.registered
    sql=BackendTests.sql

    def test_active_job_keeps_original_pending_inode_alive_and_closes_it_on_exit(self):
        self.registered()
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,{}) as job:
                pending_fd=job.pending_fd;identity=os.fstat(pending_fd).st_ino
                path=self.writer.tagger_pending
                path.unlink();self.writer.mark_tagger_pending()
                self.assertNotEqual(path.stat().st_ino,identity)
                self.assertEqual(os.fstat(pending_fd).st_ino,identity)
                self.assertEqual(os.fstat(pending_fd).st_nlink,0)
                with self.assertRaises(native.Review):job.proof(self.incoming)
                self.assertTrue(path.exists())
        with self.assertRaises(OSError):os.fstat(pending_fd)
        self.assertTrue(path.exists());self.assertTrue((self.writer.root/transaction.NAME).exists())

    def test_changed_prepared_intent_is_not_overwritten_when_fence_appears(self):
        self.registered();path=self.writer.root/transaction.NAME
        mark=self.writer.mark_tagger_pending
        def replaced():
            mark();path.write_text('{"retained":"foreign prepared intent"}')
        with self.writer.hold(allow_tagger_pending=True),patch.object(self.writer,'mark_tagger_pending',side_effect=replaced):
            with self.assertRaises(guard.Unavailable):
                with transaction.tagging(self.writer,self.incoming,'123','a'*32,{}):
                    self.fail('foreign intent admitted')
        self.assertEqual(path.read_text(),'{"retained":"foreign prepared intent"}')
        self.assertTrue(self.writer.fenced(tagger=True));self.assertTrue(self.incoming.exists())

    def recovery_state(self):
        root=self.writer.root.parent/'modern-tagger-v2'
        paths=(root,root/'journal-v2',root/'staging',root/'staging-receipts')
        for path in paths:path.mkdir(mode=0o700)
        identities=[(p.stat().st_dev,p.stat().st_ino) for p in paths]
        binding=self.writer.root/'tagger-state-v2.identity'
        binding.write_text(hashlib.sha256(json.dumps(identities).encode()).hexdigest()+'\n')
        binding.chmod(0o600)
        return paths,binding

    def test_modern_job_binds_existing_state_but_allows_new_private_children(self):
        self.registered();paths,binding=self.recovery_state()
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,{},modern=True) as job:
                (paths[2]/'mylar_modern_fixture').mkdir(mode=0o700)
                (paths[1]/'fixture.txt').write_text('child entry changes timestamps')
                job.proof(self.incoming,original=True)
                self.assertEqual(job.value['recovery'],transaction.state_evidence(self.writer))
        self.assertTrue(binding.exists());self.assertTrue(self.writer.fenced(tagger=True))

    def test_replaced_recovery_directory_cannot_borrow_modern_job(self):
        self.registered();paths,binding=self.recovery_state()
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,{},modern=True) as job:
                old=paths[2].with_name('retained-staging');paths[2].rename(old)
                paths[2].mkdir(mode=0o700)
                identities=[(p.stat().st_dev,p.stat().st_ino) for p in paths]
                binding.write_text(hashlib.sha256(json.dumps(identities).encode()).hexdigest()+'\n')
                with self.assertRaises(native.Review):job.proof(self.incoming)
                self.assertTrue(old.exists())
        self.assertTrue(self.incoming.exists());self.assertTrue(self.writer.fenced(tagger=True))

    def test_identical_replaced_state_binding_cannot_borrow_modern_job(self):
        self.registered();_,binding=self.recovery_state()
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,{},modern=True) as job:
                retained=binding.with_name('retained-binding');binding.rename(retained)
                shutil.copyfile(retained,binding);binding.chmod(0o600)
                with self.assertRaises(native.Review):job.proof(self.incoming)
        self.assertTrue(self.writer.fenced(tagger=True));self.assertTrue(retained.exists())

    def test_invalid_or_missing_modern_state_retained_before_intent_and_fence(self):
        self.registered()
        with self.writer.hold(allow_tagger_pending=True):
            with self.assertRaises(OSError):
                with transaction.tagging(self.writer,self.incoming,'123','a'*32,{},modern=True):
                    self.fail('missing state admitted')
            paths,_=self.recovery_state();paths[3].chmod(0o755)
            with self.assertRaises(guard.Unavailable):
                with transaction.tagging(self.writer,self.incoming,'123','a'*32,{},modern=True):
                    self.fail('unsafe state admitted')
        self.assertFalse((self.writer.root/transaction.NAME).exists())
        self.assertFalse(self.writer.fenced(tagger=True));self.assertTrue(self.incoming.exists())

    def test_linked_modern_state_retained_before_intent_and_fence(self):
        self.registered();paths,_=self.recovery_state()
        retained=paths[2].with_name('retained-staging');paths[2].rename(retained)
        os.symlink(retained,paths[2])
        with self.writer.hold(allow_tagger_pending=True),self.assertRaises(guard.Unavailable):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,{},modern=True):
                self.fail('linked state admitted')
        self.assertFalse((self.writer.root/transaction.NAME).exists())
        self.assertFalse(self.writer.fenced(tagger=True));self.assertTrue(retained.exists())

    def test_exact_owned_job_can_check_payload_while_ordinary_admission_stays_held(self):
        self.registered()
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,{}) as job:
                with job.coordinate():
                    self.assertEqual(job.proof(self.incoming,original=True)['decision'],'allowed')
                with self.assertRaises(guard.Unavailable):self.runtime.admission(self.writer)
                result=cases.api.Controller(self.root,[self.library])._check(
                    dict(payload=job.value['payload'],owner=self.owner),self.writer)
                self.assertEqual(result['decision'],'held')
            with self.assertRaises(native.Review):native.require(self.incoming,issueid='123',transaction=job)
        self.assertTrue(self.writer.fenced(tagger=True))
        self.assertTrue((self.writer.root/transaction.NAME).exists())

    def test_rejected_job_creates_neither_intent_nor_fence(self):
        self.registered();self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',None,'Snatched'))
        before=(self.incoming.read_bytes(),self.database.read_bytes())
        with self.writer.hold(allow_tagger_pending=True),self.assertRaises(native.Review):
            with transaction.tagging(self.writer,self.incoming,'999','a'*32,{}):self.fail('admitted')
        self.assertFalse(self.writer.fenced(tagger=True))
        self.assertFalse((self.writer.root/transaction.NAME).exists())
        self.assertEqual(before,(self.incoming.read_bytes(),self.database.read_bytes()))

    def test_replaced_or_foreign_fence_cannot_borrow_the_exact_job(self):
        self.registered()
        with self.writer.hold(allow_pending=True,allow_tagger_pending=True,allow_release_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,{}) as job:
                before=self.incoming.read_bytes()
                self.writer.tagger_pending.unlink();self.writer.mark_tagger_pending()
                with self.assertRaises(native.Review):job.proof(self.incoming)
                with self.assertRaises(guard.Unavailable):transaction.admission(True,self.writer)
                self.assertEqual(self.incoming.read_bytes(),before)
        self.assertTrue(self.writer.fenced(tagger=True))

    def test_scope_revalidates_matched_correct_owner_and_original_content(self):
        self.registered()
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,{}) as job:
                with zipfile.ZipFile(self.source,'w') as archive:archive.writestr('01.jpg',b'changed current owner')
                with self.assertRaises(native.Review):job.proof(self.incoming)
        self.assertTrue(self.writer.fenced(tagger=True))
        self.assertTrue(self.incoming.exists())

    def test_same_payload_metadata_change_stales_original_binding(self):
        self.registered()
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,{}) as job:
                with zipfile.ZipFile(self.incoming) as archive:
                    entries=[(info.filename,archive.read(info)) for info in archive.infolist()
                             if info.filename!='ComicInfo.xml']
                with zipfile.ZipFile(self.incoming,'w') as archive:
                    for name,content in entries:archive.writestr(name,content)
                    archive.writestr('ComicInfo.xml','<ComicInfo><Title>Intervening update</Title></ComicInfo>')
                self.assertEqual(guard.inventory(self.incoming)['payload'],job.value['payload'])
                with self.assertRaises(native.Review):job.proof(self.incoming,original=True)
        self.assertTrue(self.writer.fenced(tagger=True))

    def test_same_payload_correct_owner_path_drift_stales_prepared_job(self):
        self.registered()
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,{}) as job:
                target=self.library/'moved-owner.cbz';shutil.copyfile(self.source,target)
                self.sql('UPDATE issues SET Location=? WHERE IssueID=?',(target.name,'123'))
                self.assertEqual(guard.inventory(target)['payload'],job.value['payload'])
                with self.assertRaises(native.Review):job.proof(self.incoming)
        self.assertTrue(self.writer.fenced(tagger=True));self.assertTrue(self.source.exists())

    def test_caller_policy_changes_cannot_rewrite_prepared_job(self):
        self.registered();policy={'manualmeta':True,'overwrite':False}
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,policy) as job:
                policy['overwrite']=True
                self.assertFalse(job.value['policy']['overwrite'])
                job.proof(self.incoming,original=True)
        self.assertFalse(guard.private_json(self.writer.root/transaction.NAME)['policy']['overwrite'])

    def test_interrupted_typed_intent_cannot_initialize_another_job(self):
        self.registered()
        with self.writer.hold(allow_tagger_pending=True):
            with transaction.tagging(self.writer,self.incoming,'123','a'*32,{}):pass
            before=(self.writer.root/transaction.NAME).read_bytes()
            with self.assertRaises(guard.Unavailable):
                with transaction.tagging(self.writer,self.incoming,'123','b'*32,{}):self.fail('admitted')
            self.assertEqual((self.writer.root/transaction.NAME).read_bytes(),before)
        self.assertTrue(self.writer.fenced(tagger=True))


if __name__=='__main__':unittest.main()
