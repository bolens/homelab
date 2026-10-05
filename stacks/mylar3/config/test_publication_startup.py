"""Existing-only startup/admission foundation; all state is disposable."""
import ast
import importlib
import os
import queue
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock, patch


class ExistingAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.mylar=types.ModuleType('mylar');self.mylar.__path__=[str(Path(__file__).parent)]
        self.mylar.DATA_DIR=str(self.root)
        self.tagger=types.SimpleNamespace(recover=Mock())
        self.release=types.SimpleNamespace(recover=Mock())
        context=patch.dict(sys.modules,{'mylar':self.mylar,'mylar.tagger_native':self.tagger,
                                      'mylar.release_naming':self.release})
        context.start();self.addCleanup(context.stop)
        self.native=importlib.import_module('mylar.native_writers');self.mylar.native_writers=self.native
        self.native._PUBLICATION=False
        self.native._STARTUP_COMPLETE=False
        self.addCleanup(setattr,self.native,'_PUBLICATION',False)
        self.addCleanup(setattr,self.native,'_STARTUP_COMPLETE',False)
        self.guard=importlib.import_module('mylar.publication_guard')
        self.Writer=importlib.import_module('mylar.media_writer').Writer
        self.Store=importlib.import_module('mylar.workflow_store').Store

    def activate(self):
        status=self.native.initialize_publication()
        if status['state']=='ready':
            with self.native.operation(startup=True):self.native.complete_startup()
        return status

    def authority(self):
        store=self.Store(self.root);writer=self.Writer(self.root/'media-writer',create=True)
        state=self.guard.RegistryState(store.path,writer)
        backup=dict(manifest_sha256='a'*64,restore_sha256='b'*64,description='isolated reviewed fixture')
        token=state.prepare_bootstrap(backup,epoch='c'*64)
        state.initialize(token,accepted_token=token)
        return store,writer

    def test_empty_missing_namespace_stays_held_without_creation_or_recovery(self):
        with patch('sqlite3.connect') as connect:
            self.assertEqual(self.activate()['state'],'held')
            connect.assert_not_called()
        self.assertEqual(list(self.root.iterdir()),[])
        self.tagger.recover.assert_not_called();self.release.recover.assert_not_called()

    def test_uninitialized_existing_state_is_not_empty_authority(self):
        store=self.Store(self.root);self.Writer(self.root/'media-writer',create=True)
        before=store.path.read_bytes()
        self.assertEqual(self.activate()['state'],'held')
        self.assertEqual(store.path.read_bytes(),before)
        self.assertFalse((self.root/'media-writer/publication-v1.json').exists())

    def test_initialized_empty_authority_admits_existing_operation(self):
        store,writer=self.authority();before=store.path.read_bytes()
        self.assertEqual(self.activate()['state'],'ready')
        with self.native.operation(reconcile=True) as admitted:
            self.assertTrue(self.native.active());self.assertEqual(admitted.root,writer.root)
        self.assertFalse(self.native.active());self.assertEqual(store.path.read_bytes(),before)
        self.tagger.recover.assert_not_called();self.release.recover.assert_not_called()

    def test_each_operation_revalidates_lost_marker_and_does_not_recreate(self):
        self.authority();self.activate()
        (self.root/'media-writer/publication-v1.json').unlink()
        with self.assertRaises(Exception):
            with self.native.operation():pass
        self.assertFalse((self.root/'media-writer/publication-v1.json').exists())
        self.assertEqual(self.native.startup_status()['state'],'held')
        self.tagger.recover.assert_not_called()

    def test_each_operation_revalidates_census_loss(self):
        store,_=self.authority();self.activate()
        store.delete('publication_census','v1')
        with self.assertRaises(Exception):
            with self.native.operation():pass
        self.assertIsNone(store.get('publication_census','v1'))

    def test_pending_tagger_and_release_never_trigger_ordinary_recovery(self):
        _,writer=self.authority();self.activate()
        for pending in (writer.pending,writer.tagger_pending,writer.release_pending):
            writer.create_file(pending);before=pending.read_bytes()
            with self.subTest(pending=pending.name),self.assertRaises(Exception):
                with self.native.operation(reconcile=True):pass
            self.assertEqual(pending.read_bytes(),before);pending.unlink()
        self.tagger.recover.assert_not_called();self.release.recover.assert_not_called()

    def test_invalid_authority_checked_under_raw_writer_before_workflow_lock(self):
        _,writer=self.authority();self.activate()
        lock=importlib.import_module('mylar.workflow_store').LOCK
        observed=[]
        def read(database,marker):
            self.assertTrue(writer.local[1].depth);self.assertFalse(lock._is_owned())
            observed.append(True);raise self.guard.Unavailable('isolated authority hold')
        with patch.object(self.guard,'registry_snapshot',side_effect=read),self.assertRaises(self.guard.Unavailable):
            with self.native.operation():pass
        self.assertEqual(observed,[True]);self.tagger.recover.assert_not_called()

    def test_existing_store_requires_outer_admission_and_never_creates_missing_state(self):
        store,_=self.authority();self.activate()
        with self.assertRaises(Exception):self.native.existing_store(self.root)
        with self.native.operation():
            cached=self.native.existing_store(self.root)
            self.assertTrue(cached.existing_only)
            self.assertEqual(cached.path,store.path)
        store.path.unlink()
        with self.assertRaises(Exception):cached.get('pack','absent')
        self.assertFalse(store.path.exists())

    def test_pending_created_during_operation_is_retained_without_finally_replay(self):
        _,writer=self.authority();self.activate()
        with self.assertRaises(Exception):
            with self.native.operation():writer.create_file(writer.tagger_pending)
        self.assertTrue(writer.tagger_pending.exists());self.tagger.recover.assert_not_called()

    def test_activation_cannot_hot_toggle_an_active_legacy_operation(self):
        self.native.initialize()
        entered=threading.Event();release=threading.Event();failures=[]
        def legacy():
            try:
                with self.native.operation():entered.set();release.wait(3)
            except Exception as error:failures.append(error)
        thread=threading.Thread(target=legacy);thread.start()
        try:
            self.assertTrue(entered.wait(1))
            with self.assertRaises(self.guard.Unavailable):self.activate()
            self.assertFalse(self.native._PUBLICATION)
        finally:release.set();thread.join(3)
        self.assertFalse(thread.is_alive());self.assertEqual(failures,[])
        self.assertEqual(self.activate()['state'],'held')

    def test_legacy_cached_store_is_replaced_and_missing_file_never_recreated(self):
        cached,_=self.authority();self.assertFalse(cached.existing_only)
        self.activate()
        with self.native.operation():
            existing=self.native.existing_store(self.root,cached=cached)
            self.assertIsNot(existing,cached);self.assertTrue(existing.existing_only)
            self.assertIs(self.native.existing_store(self.root,cached=existing),existing)
        existing.path.unlink()
        with self.assertRaises(Exception):existing.get('pack','absent')
        self.assertFalse(existing.path.exists())

    def test_legacy_initializer_cannot_recreate_after_publication_activation(self):
        self.activate()
        with self.assertRaises(Exception):self.native.initialize()
        self.assertEqual(list(self.root.iterdir()),[])

    def test_ddl_factory_preserves_json_retry_state_and_requires_admission(self):
        control=importlib.import_module('mylar.queue_control')
        with patch.object(control,'_STORE',None):
            state=control.store()
            self.assertIsInstance(state,control.Store)
            item=dict(id='retry',mainlink='fixture',issueid='2',link_type='GC-Main')
            self.assertEqual(state.begin(item),'ready')
            self.authority();self.activate()
            with self.assertRaises(self.guard.Unavailable):control.store()
            with self.native.operation():
                self.assertIs(control.store(),state)
                self.assertEqual(state.data['items']['retry']['attempts'],1)
                state.finish(item,True)
            self.assertEqual(control.Store(self.root).data['items']['retry']['attempts'],1)

    def test_missing_existing_native_catalog_cannot_be_recreated(self):
        self.authority();self.native.initialize_publication()
        with self.native.operation(startup=True) as writer:
            with self.assertRaises(Exception):self.native.startup_catalog(writer)
        self.assertFalse((self.root/'mylar.db').exists())
        self.assertFalse(self.native._STARTUP_COMPLETE)

    def test_truncated_existing_native_catalog_cannot_initialize_empty_tables(self):
        self.authority();self.native.initialize_publication()
        for raw in (b'',b'SQLite format 3\0'+b'\0'*5000):
            (self.root/'mylar.db').write_bytes(raw)
            with self.native.operation(startup=True) as writer:
                with self.assertRaises(Exception):self.native.startup_catalog(writer)
            self.assertEqual((self.root/'mylar.db').read_bytes(),raw)

    def test_hardlinked_native_catalog_remains_held_and_unchanged(self):
        import sqlite3
        self.authority();self.native.initialize_publication()
        path=self.root/'mylar.db';db=sqlite3.connect(path)
        try:
            for table in ('comics','issues','annuals'):db.execute('CREATE TABLE '+table+'(value)')
            db.commit()
        finally:db.close()
        os.link(path,self.root/'retained-native.sqlite');before=path.read_bytes()
        with self.native.operation(startup=True) as writer:
            with self.assertRaises(self.guard.Unavailable):self.native.startup_catalog(writer)
        self.assertEqual(path.read_bytes(),before)


class FreshPreparationTests(unittest.TestCase):
    setUp=ExistingAdmissionTests.setUp

    def fresh(self):
        self.native.initialize_publication()
        return importlib.import_module('mylar.publication_fresh')

    def backup(self):
        return dict(manifest_sha256='a'*64,restore_sha256='b'*64,description='independently reviewed fresh installation')

    def test_explicit_creation_stays_held_until_exact_bootstrap_acceptance(self):
        fresh=self.fresh();token=fresh.prepare(self.root,self.backup(),epoch='c'*64)
        self.assertEqual(fresh.prepared_token(self.root),token)
        self.assertEqual(self.native.startup_status()['state'],'held')
        self.assertFalse((self.root/'mylar.db').exists())
        self.assertFalse((self.root/'media-writer/publication-v1.json').exists())
        writer=self.Writer(self.root/'media-writer')
        state=self.guard.RegistryState(self.root/'workflow.sqlite',writer)
        with self.assertRaises(self.guard.Unavailable):state.initialize(token,accepted_token='e'*64)
        state.initialize(token,accepted_token=token)
        with self.native.operation(startup=True) as admitted:self.native.startup_catalog(admitted)
        # The first creation permission is consumed even if native creation
        # subsequently crashes. A restart cannot recreate a missing catalog.
        with self.native.operation(startup=True) as admitted:
            with self.assertRaises(self.guard.Unavailable):self.native.startup_catalog(admitted)
        self.assertEqual(self.native.startup_status()['reason'],'startup-restart-required')
        with self.native.operation(startup=True):self.native.complete_startup()
        self.assertEqual(self.native.startup_status()['state'],'ready')
        self.tagger.recover.assert_not_called();self.release.recover.assert_not_called()

    def test_authenticated_protocol_fresh_prepare_status_and_acceptance(self):
        self.fresh()
        api=importlib.import_module('mylar.publication_api')
        controller=api.Controller(self.root,[])
        value=api.request(__import__('json').dumps(dict(version=1,action='prepare-fresh',epoch='c'*64,backup=self.backup())))
        prepared=controller.dispatch(value)
        self.assertEqual(prepared['outcome'],'prepared')
        status=controller.dispatch(dict(version=1,action='status'))
        self.assertEqual(status['state'],'held');self.assertEqual(status['intent']['token'],prepared['token'])
        self.assertNotIn('description',str(status));self.assertNotIn(str(self.root),str(status))
        accepted=controller.dispatch(dict(version=1,action='initialize-bootstrap',token=prepared['token']))
        self.assertEqual(accepted['outcome'],'committed')
        status=controller.dispatch(dict(version=1,action='status'))
        self.assertEqual(status['state'],'ready');self.assertEqual(status['intent']['outcome'],'committed')

    def test_partial_fresh_status_retains_claim_without_sqlite_access(self):
        fresh=self.fresh()
        with patch.object(fresh,'Store',side_effect=ValueError('isolated interruption')):
            with self.assertRaises(self.guard.Unavailable):fresh.prepare(self.root,self.backup(),epoch='c'*64)
        api=importlib.import_module('mylar.publication_api');controller=api.Controller(self.root,[])
        before=(self.root/fresh.CLAIM).read_bytes()
        with patch('sqlite3.connect') as connect:
            result=controller.dispatch(dict(version=1,action='status'))
            connect.assert_not_called()
        self.assertEqual(result['state'],'held');self.assertEqual(result['fresh']['outcome'],'unavailable')
        self.assertEqual((self.root/fresh.CLAIM).read_bytes(),before)
        self.assertFalse((self.root/'workflow.sqlite').exists())

    def test_fresh_creation_requires_excluded_legacy_startup(self):
        fresh=importlib.import_module('mylar.publication_fresh')
        with self.assertRaises(self.guard.Unavailable):fresh.prepare(self.root,self.backup(),epoch='c'*64)
        self.assertEqual(list(self.root.iterdir()),[])

    def test_invalid_evidence_does_not_claim_or_create_state(self):
        fresh=self.fresh()
        for backup,epoch in ((dict(self.backup(),description='x'*1025),'c'*64),
                             (self.backup(),'invalid'),(dict(self.backup(),extra='bad'),'c'*64)):
            with self.assertRaises(self.guard.Unavailable):fresh.prepare(self.root,backup,epoch=epoch)
            self.assertEqual(list(self.root.iterdir()),[])

    def test_any_existing_or_dangling_namespace_is_retained_unchanged(self):
        fresh=self.fresh()
        for name in ('mylar.db','workflow.sqlite','media-writer',fresh.CLAIM,'mylar.db-wal','workflow.sqlite-journal'):
            path=self.root/name;path.symlink_to(self.root/'missing-target')
            with self.subTest(name=name),self.assertRaises(self.guard.Unavailable):
                fresh.prepare(self.root,self.backup(),epoch='c'*64)
            self.assertTrue(path.is_symlink());self.assertEqual(len(list(self.root.iterdir())),1);path.unlink()

    def test_partial_creation_failure_is_retained_and_never_recreated(self):
        fresh=self.fresh()
        with patch.object(fresh,'Store',side_effect=ValueError('isolated creation interruption')):
            with self.assertRaises(self.guard.Unavailable):fresh.prepare(self.root,self.backup(),epoch='c'*64)
        before=(self.root/fresh.CLAIM).read_bytes();writer_identity=(self.root/'media-writer').stat().st_ino
        with self.assertRaises(self.guard.Unavailable):fresh.prepare(self.root,self.backup(),epoch='c'*64)
        self.assertEqual((self.root/fresh.CLAIM).read_bytes(),before)
        self.assertEqual((self.root/'media-writer').stat().st_ino,writer_identity)
        self.assertFalse((self.root/'workflow.sqlite').exists())
        self.assertEqual(self.native.startup_status()['state'],'held')

    def test_native_journal_appearing_during_preparation_stays_held(self):
        fresh=self.fresh();original=self.guard.RegistryState.prepare_bootstrap
        def injected(state,*args,**kwargs):
            token=original(state,*args,**kwargs)
            (self.root/'mylar.db-journal').write_bytes(b'foreign retained evidence')
            return token
        with patch.object(self.guard.RegistryState,'prepare_bootstrap',injected):
            with self.assertRaises(self.guard.Unavailable):fresh.prepare(self.root,self.backup(),epoch='c'*64)
        self.assertEqual((self.root/'mylar.db-journal').read_bytes(),b'foreign retained evidence')
        with self.assertRaises(self.guard.Unavailable):fresh.prepared_token(self.root)
        self.assertTrue((self.root/'workflow.sqlite').exists())
        self.assertEqual(self.native.startup_status()['state'],'held')

    def test_native_catalog_appearance_during_preparation_holds_result(self):
        fresh=self.fresh();original=self.guard.RegistryState.prepare_bootstrap
        def changed(state,*args,**kwargs):
            token=original(state,*args,**kwargs);(self.root/'mylar.db').write_bytes(b'changed native catalog');return token
        with patch.object(self.guard.RegistryState,'prepare_bootstrap',new=changed):
            with self.assertRaises(self.guard.Unavailable):fresh.prepare(self.root,self.backup(),epoch='c'*64)
        self.assertEqual(self.native.startup_status()['state'],'held')
        self.assertFalse((self.root/'media-writer/publication-v1.json').exists())
        with self.assertRaises(self.guard.Unavailable):fresh.prepared_token(self.root)


class NativeStartupSourceTests(unittest.TestCase):
    setUp=ExistingAdmissionTests.setUp
    authority=ExistingAdmissionTests.authority

    def functions(self):
        from patch_publication_startup import patched_source
        source=(Path(os.environ['MYLAR_WORKFLOW_SOURCE'])/'__init__.py').read_text()
        patched=patched_source(source);self.assertEqual(patched_source(patched),patched)
        tree=ast.parse(patched)
        names={'initialize','start','queue_schedule'}
        nodes=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
        self.assertEqual(len(nodes),3)
        config=types.SimpleNamespace(LOCMOVE=True)
        self.mylar.config=types.SimpleNamespace(Config=lambda _:types.SimpleNamespace(read=lambda **kwargs:config))
        namespace=dict(mylar=self.mylar,INIT_LOCK=threading.RLock(),logger=Mock(),_INITIALIZED=False,
                       dbcheck=Mock(),helpers=Mock(),SCHED=Mock(),threading=Mock())
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'<actual native startup>','exec'),namespace)
        return namespace

    @unittest.skipUnless(os.environ.get('MYLAR_WORKFLOW_SOURCE'),'actual pinned source required')
    def test_actual_held_initialization_stops_before_database_and_location_work(self):
        namespace=self.functions()
        with patch('sqlite3.connect') as connect:
            self.assertTrue(namespace['initialize']('unused'))
            connect.assert_not_called()
        self.assertTrue(namespace['_INITIALIZED'])
        namespace['dbcheck'].assert_not_called();namespace['helpers'].updateComicLocation.assert_not_called()
        self.assertEqual(list(self.root.iterdir()),[])
        self.tagger.recover.assert_not_called();self.release.recover.assert_not_called()

    @unittest.skipUnless(os.environ.get('MYLAR_WORKFLOW_SOURCE'),'actual pinned source required')
    def test_actual_database_failure_keeps_startup_held_and_stops_initialization(self):
        self.authority();namespace=self.functions()
        import sqlite3
        db=sqlite3.connect(self.root/'mylar.db')
        try:
            for table in ('comics','issues','annuals'):db.execute('CREATE TABLE '+table+'(value)')
            db.commit()
        finally:db.close()
        namespace['dbcheck'].side_effect=RuntimeError('isolated unreadable native database')
        self.assertFalse(namespace['initialize']('unused'))
        self.assertFalse(self.native._STARTUP_COMPLETE)
        self.assertEqual(self.native.startup_status()['state'],'held')
        namespace['helpers'].updateComicLocation.assert_not_called()
        namespace['SCHED'].add_job.assert_not_called()

    @unittest.skipUnless(os.environ.get('MYLAR_WORKFLOW_SOURCE'),'actual pinned source required')
    def test_actual_start_and_queue_start_stay_held_without_jobs_or_threads(self):
        namespace=self.functions();self.native.initialize_publication()
        self.assertFalse(namespace['start']())
        self.assertFalse(namespace['queue_schedule']('pp_queue','start'))
        namespace['SCHED'].add_job.assert_not_called();namespace['threading'].Thread.assert_not_called()
        self.assertEqual(list(self.root.iterdir()),[])

    @unittest.skipUnless(os.environ.get('MYLAR_WORKFLOW_SOURCE'),'actual pinned source required')
    def test_actual_pending_initialization_preserves_fences_without_location_work(self):
        _,writer=self.authority();writer.create_file(writer.release_pending)
        before=writer.release_pending.read_bytes();namespace=self.functions()
        self.assertTrue(namespace['initialize']('unused'))
        namespace['dbcheck'].assert_not_called();namespace['helpers'].updateComicLocation.assert_not_called()
        self.assertEqual(writer.release_pending.read_bytes(),before)
        self.tagger.recover.assert_not_called();self.release.recover.assert_not_called()

    def test_worker_health_remains_passive_and_reports_held_without_native_database(self):
        self.native.initialize_publication()
        health=importlib.import_module('mylar.worker_health')
        with patch('sqlite3.connect') as connect:
            result=health.snapshot();connect.assert_not_called()
        self.assertEqual(result['publication']['state'],'held')
        from health import assess
        self.assertTrue(assess(result,{},1)['errors'])
        self.assertEqual(list(self.root.iterdir()),[])

    def test_completed_authority_does_not_start_media_before_native_initialization(self):
        self.authority();self.native.initialize_publication()
        self.assertEqual(self.native.authority_probe()['state'],'ready')
        self.assertEqual(self.native.startup_status()['reason'],'startup-restart-required')
        with self.assertRaises(self.guard.Unavailable):
            with self.native.operation():pass
        health=importlib.import_module('mylar.worker_health')
        self.assertEqual(health.snapshot()['publication']['state'],'held')
        self.assertFalse((self.root/'mylar.db').exists())

    def test_http_hold_precedes_redirects_or_database_helpers(self):
        self.native.initialize_publication();called=Mock()
        held=self.native.publication_http(called)
        with patch('sqlite3.connect') as connect:
            result=held();connect.assert_not_called()
        self.assertIn('processing is held',result);called.assert_not_called()
        self.assertEqual(list(self.root.iterdir()),[])

    @unittest.skipUnless(os.environ.get('MYLAR_WORKFLOW_SOURCE'),'actual pinned source required')
    def test_startup_adapter_installs_twice_and_checks_owned_guards(self):
        import shutil
        from patch_publication_startup import main
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ('__init__.py','api.py','webserve.py'):
                shutil.copyfile(Path(os.environ['MYLAR_WORKFLOW_SOURCE'])/name,root/name)
            main(root);before={path:path.read_bytes() for path in root.iterdir()}
            main(root);self.assertEqual(before,{path:path.read_bytes() for path in root.iterdir()})
            for name,old,new in (('__init__.py','with native_writers.operation(startup=True) as publication_writer:','with native_writers.operation():'),
                                 ('api.py','self.cmd not in native_writers.PASSIVE_API','self.cmd not in ()'),
                                 ('webserve.py',"name != 'api'","name != 'changed'")):
                path=root/name;path.write_bytes(before[path].replace(old.encode(),new.encode(),1))
                with self.assertRaises(ValueError):main(root)
                for saved,raw in before.items():saved.write_bytes(raw)

    @unittest.skipUnless(os.environ.get('MYLAR_WORKFLOW_SOURCE'),'actual pinned source required')
    def test_actual_api_router_holds_regular_commands_but_preserves_publication_route(self):
        import shutil
        from patch_publication_startup import main
        self.native.initialize_publication()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ('__init__.py','api.py','webserve.py'):
                shutil.copyfile(Path(os.environ['MYLAR_WORKFLOW_SOURCE'])/name,root/name)
            main(root);tree=ast.parse((root/'api.py').read_text())
            cls=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='Api')
            method=next(node for node in cls.body if isinstance(node,ast.FunctionDef) and node.name=='checkParams')
            self.mylar.CONFIG=types.SimpleNamespace(API_ENABLED=True,API_KEY='p'*32);self.mylar.SSE_KEY='s'*32
            namespace=dict(mylar=self.mylar,cmd_list=['getIndex','publicationControl'],logger=Mock())
            exec(compile(ast.Module(body=[method],type_ignores=[]),'<actual native API router>','exec'),namespace)
            handler=types.SimpleNamespace(_failureResponse=lambda message:message,apitype=None)
            with patch('sqlite3.connect') as connect:
                namespace['checkParams'](handler,cmd='getIndex',apikey='p'*32)
                self.assertIn('authority held',handler.data)
                namespace['cmd_list'].append('checkGlobalMessages')
                namespace['checkParams'](handler,cmd='checkGlobalMessages',apikey='p'*32)
                self.assertIn('authority held',handler.data)
                namespace['checkParams'](handler,cmd='publicationControl',apikey='p'*32,request='not decoded by router')
                self.assertEqual(handler.data,'OK');self.assertEqual(handler.apitype,'normal')
                connect.assert_not_called()
        self.assertEqual(list(self.root.iterdir()),[])

    def test_ready_api_and_http_entries_own_writer_before_workflow_access(self):
        self.authority();self.native.initialize_publication()
        with self.native.operation(startup=True):self.native.complete_startup()
        entered=[]
        def web():
            self.assertTrue(self.native.active());entered.append('web')
            return self.native.existing_store(self.root).get('pack','absent')
        def api(handler):
            self.assertTrue(self.native.active());entered.append('api')
            return self.native.existing_store(self.root).get('pack','absent')
        self.assertIsNone(self.native.publication_http(web)())
        self.assertIsNone(self.native.publication_api_call(api)(types.SimpleNamespace(cmd='getIndex',data='OK')))
        self.assertEqual(entered,['web','api'])

    def test_passive_stream_and_control_api_never_require_ordinary_admission(self):
        self.native.initialize_publication();called=Mock(return_value='passive')
        wrapped=self.native.publication_api_call(called)
        for command in self.native.PASSIVE_API:
            self.assertEqual(wrapped(types.SimpleNamespace(cmd=command,data='OK')),'passive')
        self.assertEqual(called.call_count,len(self.native.PASSIVE_API))
        self.assertEqual(list(self.root.iterdir()),[])

    @unittest.skipUnless(os.environ.get('MYLAR_WORKFLOW_SOURCE'),'actual pinned source required')
    def test_actual_http_dispatcher_preserves_api_and_blocks_held_exposed_routes(self):
        import shutil
        from patch_publication_startup import main
        self.native.initialize_publication()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ('__init__.py','api.py','webserve.py'):
                shutil.copyfile(Path(os.environ['MYLAR_WORKFLOW_SOURCE'])/name,root/name)
            main(root);tree=ast.parse((root/'webserve.py').read_text())
            cls=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='WebInterface')
            method=next(node for node in cls.body if isinstance(node,ast.FunctionDef) and node.name=='__getattribute__')
            method.col_offset=4
            class_node=ast.ClassDef(name='Routes',bases=[],keywords=[],decorator_list=[],body=[method])
            ast.fix_missing_locations(class_node);namespace={'native_writers':self.native}
            exec(compile(ast.Module(body=[class_node],type_ignores=[]),'<actual HTTP dispatcher>','exec'),namespace)
            called=[]
            def route(self):called.append(True);return 'original'
            route.exposed=True
            routes=namespace['Routes'];routes.index=route;routes.api=route;routes.private=lambda self:'private'
            obj=routes()
            self.assertIn('processing is held',obj.index());self.assertEqual(called,[])
            self.assertEqual(obj.api(),'original');self.assertEqual(called,[True])
            self.assertEqual(obj.private(),'private')
        self.assertEqual(list(self.root.iterdir()),[])

    def test_invalid_api_response_does_not_attempt_ordinary_admission(self):
        self.native.initialize_publication();called=Mock(return_value='failure response')
        handler=types.SimpleNamespace(cmd=None,data='invalid key')
        with patch.object(self.native,'operation') as operation:
            self.assertEqual(self.native.publication_api_call(called)(handler),'failure response')
            operation.assert_not_called()
        self.assertEqual(list(self.root.iterdir()),[])

    def test_native_workflow_tick_held_before_store_sql_or_queue_changes(self):
        self.native.initialize_publication();workflow=importlib.import_module('mylar.workflow')
        workflow._STARTED=False;workflow._LAST_TICK=0;workflow._STORE=None
        pending=queue.Queue()
        with patch.object(workflow,'Store') as store,patch('sqlite3.connect') as connect:
            workflow.tick(pending);store.assert_not_called();connect.assert_not_called()
        self.assertFalse(workflow._STARTED);self.assertEqual(workflow._LAST_TICK,0)
        self.assertTrue(pending.empty());self.assertEqual(list(self.root.iterdir()),[])


if __name__=='__main__':unittest.main()
