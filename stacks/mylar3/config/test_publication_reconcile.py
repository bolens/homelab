"""Actual registered ownership, isolated backup, CAS and passive repeat controls."""
from pathlib import Path
import shutil
import os
import ast
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch,Mock

import publication_reconcile as repair
import publication_guard as guard
import publication_transaction as transaction
import test_publication_rename as fixtures
from patch_publication_reconcile import patched_source
import publication_native as native


class InstallerTests(unittest.TestCase):
    def test_fresh_upgrade_and_changed_guards(self):
        source="cmd_list=['getVersion']\nclass Api:\n    def _getVersion(self, **kwargs):pass\n"
        changed=patched_source(source);self.assertEqual(patched_source(changed),changed)
        self.assertIn('commitRetainedRepeat',changed)
        with self.assertRaises(ValueError):patched_source(changed.replace("getattr(self, 'apitype', None) != 'normal'",'False'))

    def test_actual_handlers_require_primary_exact_fields_and_handle_review(self):
        source="cmd_list=['getVersion']\nclass Api:\n    def _getVersion(self, **kwargs):pass\n"
        nodes={node.name:node for node in ast.walk(ast.parse(patched_source(source))) if isinstance(node,ast.FunctionDef)}
        module=SimpleNamespace(commit=Mock(return_value={'phase':'retained-review'}),status=Mock(return_value={'requires_review':True}))
        app=SimpleNamespace(CONFIG=SimpleNamespace(API_ENABLED=True,API_KEY='p'*32),publication_reconcile=module,publication_native=native)
        request=SimpleNamespace(method='POST');namespace={'mylar':app,'cherrypy':SimpleNamespace(request=request)}
        for name in ('_commitRetainedRepeat','_retainedRepeatStatus'):
            exec(compile(ast.Module(body=[nodes[name]],type_ignores=[]),'<actual-repeat-api>','exec'),namespace)
        obj=SimpleNamespace(apikey='p'*32,apitype='normal',_failureResponse=lambda _:False,_successResponse=lambda result:result)
        with patch.dict(sys.modules,{'mylar':app}):
            for key,kind in ((None,'normal'),('secondary','sse'),('p'*32,'sse')):
                obj.apikey=key;obj.apitype=kind;namespace['_commitRetainedRepeat'](obj,request='{}');self.assertIs(obj.data,False)
            obj.apikey='p'*32;obj.apitype='normal'
            namespace['_commitRetainedRepeat'](obj,request='{}',callback='extra');self.assertIs(obj.data,False)
            request.method='GET';namespace['_commitRetainedRepeat'](obj,request='{}');self.assertIs(obj.data,False)
            module.commit.assert_not_called();request.method='POST'
            namespace['_commitRetainedRepeat'](obj,request='{}');self.assertEqual(obj.data,{'phase':'retained-review'})
            module.commit.side_effect=native.Review();namespace['_commitRetainedRepeat'](obj,request='{}');self.assertIs(obj.data,False)
            request.method='GET';namespace['_retainedRepeatStatus'](obj,token='a'*64);self.assertEqual(obj.data,{'requires_review':True})
            namespace['_retainedRepeatStatus'](obj,token='A'*64);self.assertIs(obj.data,False)


@unittest.skipUnless((Path(fixtures.fixtures.fixtures.TOOL_ROOT)/'lib/archive_backend.py').is_file(),
                     'offline native archive verifier required')
class ReconcileTests(unittest.TestCase):
    call=fixtures.RenameTests.call
    bootstrap=fixtures.RenameTests.bootstrap
    prepare=fixtures.RenameTests.prepare
    connection=fixtures.RenameTests.connection

    def setUp(self):
        fixtures.RenameTests.setUp(self)
        def existing_store(_):
            self.store.existing_only=True
            return self.store
        self.runtime.existing_store=existing_store
        original=self.runtime.admission
        def admission(writer):
            value=original(writer)
            if (writer.root/transaction.NAME).exists():raise guard.Unavailable('Retained native intent')
            return value
        self.runtime.admission=admission
        self.wrong=dict(table='issues',issueid='999',parentcomicid='888',releasecomicid='888')
        self.repeat=self.library/'repeat.cbz';shutil.copyfile(self.source,self.repeat)
        with self.connection() as db:
            db.execute('INSERT INTO comics VALUES (?,?,?)',('888',str(self.library),'Active'))
            db.execute('INSERT INTO issues (IssueID,ComicID,Location,Status,ComicSize,ComicName) VALUES (?,?,?,?,?,?)',
                ('999','888',self.repeat.name,'Downloaded',self.repeat.stat().st_size,'Legitimate wanted name'))
        self.private=self.root/'private-review';self.private.mkdir(mode=0o700)
        self.evidence=self.private/'evidence';self.evidence.write_bytes(b'operator reviewed exact repeat');self.evidence.chmod(0o600)
        census=guard.registry_snapshot(self.store.path,self.writer.root/'publication-v1.json')[0]
        with self.writer.hold():observed=guard.observe_owners(self.database,self.writer,[self.owner],[self.library])
        prepared=self.call('prepare-registration',census=census,inventory=observed['inventory'],allowed=[self.owner],
            rejected=[self.wrong],created=1,evidence=dict(sha256=guard.file_hash(self.evidence)[1],description='reviewed repeat'))
        self.call('register',token=prepared['token'])
        self.build()

    def build(self):
        census=guard.registry_snapshot(self.store.path,self.writer.root/'publication-v1.json')[0]
        with self.writer.hold():
            correct_owners=getattr(self,'correct_owners',[self.owner])
            correct,_=repair.correct_observation(self.database,self.store.path,self.writer,correct_owners,[self.library],guard.inventory(self.repeat)['payload'])
            rejected=guard.observe_owners(self.database,self.writer,[self.wrong],[self.library])
        required=dict(catalog=self.database,workflow=self.store.path,marker=self.writer.root/'publication-v1.json',
            repeat=self.repeat)
        required.update({'correct_'+str(index):Path(item['catalog']['path']) for index,item in enumerate(correct['observed'])})
        manifest=dict(version=1,files=[]);receipt=dict(version=1,manifest_sha256=None,files=[])
        for role,source in required.items():
            for name in ('backup-'+role,'restore-'+role):
                folder=self.private/name;folder.mkdir(mode=0o700,exist_ok=True)
                output=folder/'copy';shutil.copyfile(source,output);output.chmod(0o600)
            sha=guard.file_hash(source)[1]
            manifest['files'].append(dict(role=role,source=str(source),backup=str(self.private/('backup-'+role)/'copy'),
                restore=str(self.private/('restore-'+role)/'copy'),sha256=sha))
            receipt['files'].append(dict(role=role,sha256=sha))
        manifest_path=self.private/'manifest.json';transaction._write(manifest_path,manifest,exclusive=not manifest_path.exists())
        receipt['manifest_sha256']=guard.file_hash(manifest_path)[1]
        receipt_path=self.private/'restore.json';transaction._write(receipt_path,receipt,exclusive=not receipt_path.exists())
        backup=dict(manifest_path=str(manifest_path),manifest_sha256=guard.file_hash(manifest_path)[1],
            restore_receipt_path=str(receipt_path),restore_receipt_sha256=guard.file_hash(receipt_path)[1])
        facts,_=repair.backup(backup,required,[self.library])
        records=guard.registry_snapshot(self.store.path,self.writer.root/'publication-v1.json')[1]
        rejected_owners={guard.canonical_digest(owner):owner for record in repair.family(records,rejected['inventory']['payload']) for owner in record['rejected']}
        registration=dict(version=1,action='prepare-registration',census=census,inventory=correct['inventory'],
            allowed=correct_owners,rejected=[rejected_owners[key] for key in sorted(rejected_owners)],created=1,
            evidence=dict(sha256=guard.file_hash(self.evidence)[1],description='reviewed repeat'))
        body=dict(version=1,kind='publication-correction-plan',executable=False,readiness='registration-preparation-only',
            scope=dict(version=1,config_dir=str(self.root),library_roots=[str(self.library)],tool_root=str(guard.TOOL_ROOT)),
            registration_request=registration,registration_commit=dict(action='register',requires='exact-token-returned-by-native-prepare'),
            observations=correct,writer_identity=guard.writer_identity(self.writer),backup=facts,
            evidence=dict(path=str(self.evidence),sha256=guard.file_hash(self.evidence)[1],description='reviewed repeat'),
            repeat=dict(executable=False,readiness='native-reconciliation-authority-unimplemented',source=rejected['observed'][0],
                inventory=rejected['inventory'],correct=correct['observed'],acquisition_provenance=None,failed_release_binding=None,
                retention='verified-outside-library-copy-required-before-any-unlink'))
        plan=dict(body,token=guard.canonical_digest(body));self.plan=self.private/'plan.json'
        transaction._write(self.plan,plan,exclusive=not self.plan.exists())
        self.request=dict(version=1,plan_path=str(self.plan),plan_sha256=guard.file_hash(self.plan)[1],
            backup=backup,census=census,repair=repair.REPAIR)

    def row(self):
        with self.connection() as db:return dict(db.execute('SELECT * FROM issues WHERE IssueID=?',('999',)).fetchone())

    def test_exact_registered_repeat_retained_location_only_and_passive_ack(self):
        correct=self.source.read_bytes();before=self.row();answer=repair.commit(self.request)
        self.assertEqual(answer['phase'],'retained-review');self.assertTrue(answer['requires_review'])
        self.assertIsNone(answer['failed_release_binding']);self.assertIsNone(answer['acquisition_provenance'])
        self.assertFalse(self.repeat.exists());self.assertEqual(self.source.read_bytes(),correct)
        self.assertEqual(self.row(),dict(before,Location=None));self.assertEqual(repair.status(answer['token']),answer)
        original=self.writer.root/'retained-repeats-v1'/answer['token']/'original.cbz'
        self.assertEqual(original.read_bytes(),correct);self.assertEqual(original.stat().st_mode&0o777,0o600)
        with self.assertRaises((guard.Unavailable,ValueError)):repair.commit(self.request)

    def test_registered_annual_archived_repeat_preserves_release_owner_and_status(self):
        with self.connection() as db:
            db.execute("DELETE FROM issues WHERE IssueID='999'")
            db.execute('INSERT INTO annuals (IssueID,ComicID,ReleaseComicID,Location,Status,Deleted,ComicName) VALUES (?,?,?,?,?,?,?)',
                ('999','888','777',self.repeat.name,'Archived',0,'wanted annual history'))
        self.wrong=dict(table='annuals',issueid='999',parentcomicid='888',releasecomicid='777')
        census=guard.registry_snapshot(self.store.path,self.writer.root/'publication-v1.json')[0]
        with self.writer.hold():observed=guard.observe_owners(self.database,self.writer,[self.owner],[self.library])
        prepared=self.call('prepare-registration',census=census,inventory=observed['inventory'],allowed=[self.owner],
            rejected=[self.wrong],created=2,evidence=dict(sha256=guard.file_hash(self.evidence)[1],description='reviewed annual repeat'))
        self.call('register',token=prepared['token']);self.build()
        with self.connection() as db:before=dict(db.execute("SELECT * FROM annuals WHERE IssueID='999'").fetchone())
        answer=repair.commit(self.request);self.assertEqual(repair.status(answer['token']),answer)
        with self.connection() as db:self.assertEqual(dict(db.execute("SELECT * FROM annuals WHERE IssueID='999'").fetchone()),dict(before,Location=None))

    def test_changed_backup_or_nonindependent_restore_holds_before_intent(self):
        manifest=guard.private_json(self.request['backup']['manifest_path'])
        first=manifest['files'][0];Path(first['restore']).write_bytes(b'changed isolated restore')
        with self.assertRaises(guard.Unavailable):repair.commit(self.request)
        self.assertTrue(self.repeat.exists());self.assertFalse((self.writer.root/transaction.NAME).exists())

    def test_hardlinked_protected_original_is_never_retired(self):
        self.repeat.unlink();os.link(self.source,self.repeat)
        with self.assertRaises(guard.Unavailable):repair.commit(self.request)
        self.assertTrue(self.source.exists());self.assertTrue(self.repeat.exists());self.assertFalse(self.writer.fenced(release=True))

    def test_changed_payload_cannot_be_promoted_as_registered_repeat(self):
        self.repeat.write_bytes(b'not an admitted repeat')
        with self.assertRaises(guard.Unavailable):repair.commit(self.request)
        self.assertTrue(self.repeat.exists());self.assertFalse((self.writer.root/transaction.NAME).exists())

    def test_pre_registration_census_and_missing_registered_rejection_hold(self):
        value=dict(self.request,census=dict(self.request['census'],revision=0))
        with self.assertRaises(guard.Unavailable):repair.commit(value)
        self.assertTrue(self.repeat.exists());self.assertFalse(self.writer.fenced(release=True))

    def test_correct_change_before_row_cas_keeps_repeat_and_fence(self):
        before=self.row()
        def boundary(phase):
            if phase=='preserved':self.source.write_bytes(b'changed protected correct publication')
        with self.assertRaises(guard.Unavailable):repair.commit(self.request,boundary=boundary)
        self.assertTrue(self.repeat.exists());self.assertEqual(self.row(),before);self.assertTrue(self.writer.fenced(release=True))

    def test_repeat_replacement_after_location_cas_is_never_unlinked(self):
        def boundary(phase):
            if phase=='cataloged':self.repeat.write_bytes(b'new unrelated source')
        with self.assertRaises(guard.Unavailable):repair.commit(self.request,boundary=boundary)
        self.assertEqual(self.repeat.read_bytes(),b'new unrelated source');self.assertTrue(self.writer.fenced(release=True))

    def test_private_original_final_read_cannot_hide_changed_repeat_before_unlink(self):
        original=repair.retained;changed=False
        def retained(path,checksum):
            nonlocal changed
            value=original(path,checksum)
            if not changed and self.row()['Location'] is None and self.repeat.exists():
                changed=True;self.repeat.write_bytes(b'foreign replacement during private proof')
            return value
        with patch.object(repair,'retained',side_effect=retained),self.assertRaises(guard.Unavailable):repair.commit(self.request)
        self.assertEqual(self.repeat.read_bytes(),b'foreign replacement during private proof');self.assertTrue(self.writer.fenced(release=True))

    def test_live_source_attribute_cannot_redirect_retirement_to_protected_correct(self):
        def boundary(phase):
            if phase=='cataloged':
                cap=repair._LOCAL.reconcile;cap.source=self.source;cap.source_state=repair.file_state(self.source)
                cap.source_inventory=guard.inventory(self.source);cap.source_parents=native.parents(self.source)
        with self.assertRaises(guard.Unavailable):repair.commit(self.request,boundary=boundary)
        self.assertTrue(self.source.exists());self.assertTrue(self.repeat.exists());self.assertTrue(self.writer.fenced(release=True))

    def test_interruptions_hold_and_do_not_reconstruct_capability(self):
        def boundary(phase):
            if phase=='preserved':raise RuntimeError('interrupted')
        with self.assertRaises(RuntimeError):repair.commit(self.request,boundary=boundary)
        self.assertTrue(self.repeat.exists());self.assertTrue(self.writer.fenced(release=True))
        with self.assertRaises(guard.Unavailable):repair.commit(self.request)

    def test_wanted_row_fields_and_unrelated_catalog_changes_are_never_overwritten(self):
        def boundary(phase):
            if phase=='preserved':
                with self.connection() as db:db.execute("UPDATE issues SET ComicName='new wanted choice' WHERE IssueID='999'")
        with self.assertRaises(guard.Unavailable):repair.commit(self.request,boundary=boundary)
        self.assertEqual(self.row()['ComicName'],'new wanted choice');self.assertTrue(self.repeat.exists())

    def test_retained_original_changed_during_final_status_admission_holds(self):
        answer=repair.commit(self.request);original=self.writer.root/'retained-repeats-v1'/answer['token']/'original.cbz'
        admit=self.runtime.admission
        def changed(writer):
            value=admit(writer);original.write_bytes(b'changed private original');return value
        with patch.object(self.runtime,'admission',side_effect=changed),self.assertRaises(guard.Unavailable):repair.status(answer['token'])

    def test_final_status_admission_correct_source_replacement_is_held(self):
        answer=repair.commit(self.request);admit=self.runtime.admission;calls=0
        def changed(writer):
            nonlocal calls
            value=admit(writer);calls+=1
            if calls>=2:self.source.write_bytes(b'changed protected publication')
            return value
        with patch.object(self.runtime,'admission',side_effect=changed),self.assertRaises((guard.Unavailable,ValueError)):
            repair.status(answer['token'])

    def test_last_status_catalog_read_cannot_ack_changed_correct_source(self):
        answer=repair.commit(self.request);original=repair.catalog;calls=[]
        def changed(*args,**kwargs):
            value=original(*args,**kwargs);calls.append(None)
            if len(calls)==3:self.source.write_bytes(b'foreign protected publication')
            return value
        with patch.object(repair,'catalog',side_effect=changed),self.assertRaises(guard.Unavailable):repair.status(answer['token'])

    def test_final_status_journal_read_cannot_ack_changed_complete_census(self):
        answer=repair.commit(self.request);original=self.store.get;calls=[]
        def changed(kind,key):
            value=original(kind,key)
            if kind=='retained_repeat':
                calls.append(None)
                if len(calls)==2:(self.writer.root/'publication-v1.json').write_text('{}')
            return value
        with patch.object(self.store,'get',side_effect=changed),self.assertRaises(guard.Unavailable):repair.status(answer['token'])

    def test_final_status_journal_read_cannot_ack_new_workflow_sidecar(self):
        answer=repair.commit(self.request);original=self.store.get;calls=[]
        def changed(kind,key):
            value=original(kind,key)
            if kind=='retained_repeat':
                calls.append(None)
                if len(calls)==2:Path(str(self.store.path)+'-wal').write_bytes(b'foreign recovery state')
            return value
        with patch.object(self.store,'get',side_effect=changed),self.assertRaises(guard.Unavailable):repair.status(answer['token'])

    def test_final_status_journal_read_cannot_ack_new_media_exclusion(self):
        answer=repair.commit(self.request);original=self.store.get
        for target in (self.writer.pending,self.writer.tagger_pending,self.writer.release_pending,self.writer.root/transaction.NAME,self.writer.root/'nested-derivative-v1.json',self.writer.root/'tagger-recovery-v1.pending'):
            calls=[]
            def changed(kind,key):
                value=original(kind,key)
                if kind=='retained_repeat':
                    calls.append(None)
                    if len(calls)==2:self.writer.create_file(target)
                return value
            with self.subTest(target=target.name),patch.object(self.store,'get',side_effect=changed),self.assertRaises(guard.Unavailable):repair.status(answer['token'])
            self.assertTrue(target.exists());target.unlink()

    def test_final_status_journal_read_cannot_ack_replaced_writer_lock(self):
        answer=repair.commit(self.request);original=self.store.get;calls=[]
        def changed(kind,key):
            value=original(kind,key)
            if kind=='retained_repeat':
                calls.append(None)
                if len(calls)==2:
                    replacement=self.writer.root/'foreign-lock';self.writer.create_file(replacement);replacement.replace(self.writer.lock)
            return value
        with patch.object(self.store,'get',side_effect=changed),self.assertRaises(guard.Unavailable):repair.status(answer['token'])

    def test_rewritten_witness_and_recreated_source_never_acknowledge(self):
        answer=repair.commit(self.request);terminal=self.writer.root/'reconciled-repeats-v1'/(answer['token']+'.json')
        value=guard.private_json(terminal);value['catalog_sha256']='e'*64
        transaction._write(terminal,value,exclusive=False)
        with self.assertRaises(guard.Unavailable):repair.status(answer['token'])

    def test_final_unlink_ack_failure_restores_owned_marker(self):
        unlink=Path.unlink;failed=False
        def uncertain(path,*args,**kwargs):
            nonlocal failed
            result=unlink(path,*args,**kwargs)
            if path==self.writer.root/transaction.NAME and not failed:
                failed=True;raise OSError('lost unlink acknowledgement')
            return result
        with patch.object(Path,'unlink',uncertain),self.assertRaises(OSError):repair.commit(self.request)
        self.assertTrue((self.writer.root/transaction.NAME).exists())
        self.assertFalse(self.repeat.exists())
        with self.assertRaises(guard.Unavailable):repair.commit(self.request)



@unittest.skipUnless((Path(fixtures.fixtures.fixtures.TOOL_ROOT)/'lib/archive_backend.py').is_file(),
                     'offline native archive verifier required')
class FamilyReconcileTests(unittest.TestCase):
    call=ReconcileTests.call
    bootstrap=ReconcileTests.bootstrap
    prepare=ReconcileTests.prepare
    connection=ReconcileTests.connection
    build=ReconcileTests.build
    row=ReconcileTests.row

    def setUp(self):
        import test_publication_derivative as lineage_fixtures
        import publication_derivative as derivative
        for name in ('refresh_review','capture_backup','document','plan','api_controller'):
            setattr(self,name,getattr(lineage_fixtures.DerivativeTests,name).__get__(self))
        lineage_fixtures.DerivativeTests.setUp(self)
        def existing_store(_):
            self.store.existing_only=True
            return self.store
        self.runtime.existing_store=existing_store
        self.wrong=dict(table='issues',issueid='999',parentcomicid='888',releasecomicid='888')
        self.repeat=self.library/'rejected-old.cbz';shutil.copyfile(self.source,self.repeat)
        self.old_bytes=self.repeat.read_bytes()
        self.annual=self.library/'protected-annual-old.cbz';shutil.copyfile(self.source,self.annual)
        self.annual_owner=dict(table='annuals',issueid='321',parentcomicid='456',releasecomicid='789')
        self.correct_owners=[self.owner,self.annual_owner]
        with self.connection() as db:
            db.execute('INSERT INTO comics (ComicID,ComicLocation) VALUES (?,?)',('888',str(self.library)))
            db.execute('INSERT INTO issues (IssueID,ComicID,Location,Status,ComicSize,ComicName) VALUES (?,?,?,?,?,?)',
                ('999','888',self.repeat.name,'Downloaded',self.repeat.stat().st_size,'Unresolved wanted history'))
        self.evidence=self.private/'correction-evidence';self.evidence.write_bytes(b'operator reviewed complete inherited family')
        self.evidence.chmod(0o600)
        with self.writer.hold():observed=guard.observe_owners(self.database,self.writer,[self.owner],[self.library])
        with self.connection() as db:
            db.execute('INSERT INTO annuals (IssueID,ComicID,ReleaseComicID,Location,Status,Deleted) VALUES (?,?,?,?,?,?)',('321','456','789',self.annual.name,'Archived',0))
        registered=self.call('prepare-registration',census=self.request['census'],inventory=observed['inventory'],allowed=self.correct_owners,rejected=[self.wrong],created=1,evidence=dict(sha256=guard.file_hash(self.evidence)[1],description='reviewed repeat'))
        self.request['census']=self.call('register',token=registered['token'])['census']
        lineage_fixtures.DerivativeTests.refresh_review(self)
        self.backupdir.rename(self.root/'prior-backup');self.restoredir.rename(self.root/'prior-restore')
        lineage_fixtures.DerivativeTests.capture_backup(self)
        # Helper calls are borrowed explicitly; no invented attestation records.
        self.api_controller=lambda:lineage_fixtures.DerivativeTests.api_controller(self)
        self.plan=lambda:lineage_fixtures.DerivativeTests.plan(self)
        prepared,_=lineage_fixtures.DerivativeTests.adoption(self)
        with self.runtime.operation() as writer:derivative.publish(writer,prepared['token'])
        self.database=self.root/'mylar.db'
        self.build()

    def test_adopted_new_correct_variant_retains_rejected_old_and_status_only(self):
        new=self.source.read_bytes();before=self.row()
        self.assertNotEqual(guard.inventory(self.source)['payload'],guard.inventory(self.repeat)['payload'])
        answer=repair.commit(self.request)
        self.assertEqual(answer['phase'],'retained-review');self.assertEqual(self.row(),dict(before,Location=None))
        self.assertEqual(self.source.read_bytes(),new);self.assertEqual(self.annual.read_bytes(),self.old_bytes);self.assertFalse(self.repeat.exists())
        original=self.writer.root/'retained-repeats-v1'/answer['token']/'original.cbz'
        self.assertEqual(original.read_bytes(),self.old_bytes);self.assertEqual(repair.status(answer['token']),answer)

    def test_current_unrelated_correct_payload_cannot_borrow_family(self):
        import zipfile
        with zipfile.ZipFile(self.source,'w') as archive:archive.writestr('01.jpg',b'unrelated correct')
        with self.assertRaises(guard.Unavailable):repair.commit(self.request)
        self.assertTrue(self.repeat.exists());self.assertFalse((self.writer.root/transaction.NAME).exists())

    def test_family_plan_missing_inherited_rejected_owner_is_held(self):
        value=guard.private_json(self.plan)
        value['registration_request']['rejected']=[]
        body={key:item for key,item in value.items() if key!='token'};value['token']=guard.canonical_digest(body)
        transaction._write(self.plan,value,exclusive=False);self.request['plan_sha256']=guard.file_hash(self.plan)[1]
        with self.assertRaises(guard.Unavailable):repair.commit(self.request)
        self.assertTrue(self.repeat.exists())

if __name__=='__main__':unittest.main()
