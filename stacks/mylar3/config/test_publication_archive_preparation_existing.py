"""Real detached saved preparation; explicit fixture SDK/lifecycle origins only."""
import copy
import importlib.util
import os
from pathlib import Path
import sqlite3
import sys
import time
import types
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parent))
import test_publication_archive_adoption as f
o=f.o
spec=importlib.util.spec_from_file_location('mylar.publication_archive_preparation_existing',Path(__file__).with_name('publication_archive_preparation_existing.py'))
x=importlib.util.module_from_spec(spec);spec.loader.exec_module(x)

class FixtureCustody:
    def __init__(self,prep):
        self.deadline=time.monotonic()+180;self.calls=0;self.callback=None
        self.files={prep._operation:copy.deepcopy(prep._directory),prep._operation/'preparation.json':copy.deepcopy(prep._files[prep._operation/'preparation.json']['signature9'])}
        self.nodes=o.ancestors(self.files);self.absent=set()
    def revalidate_stopped(self):
        self.calls+=1
        if self.callback:self.callback(self)
    def vectors(self):return copy.deepcopy(self.files),copy.deepcopy(self.nodes),tuple(self.absent)

class Controls(unittest.TestCase):
    def setUp(self):
        self.c=f.native.Controls('runTest');self.c.setUp();self.addCleanup(self.c.doCleanups)
        self.hold=self.c.writer.hold();self.hold.__enter__();self.addCleanup(self.hold.__exit__,None,None,None)
        self.prep=self.c.prepare();self.op=self.prep._operation;self.custody=FixtureCustody(self.prep)
        # These source controls exercise real preparation/ZIP/catalog/Writer
        # objects, not an installed or protected lifecycle claim.
        for value in (patch.object(x,'installed'),patch.object(x,'lifecycle',types.SimpleNamespace(__file__=str(Path(__file__).with_name('publication_reader_lifecycle.py')),StoppedReaderCustody=FixtureCustody))):
            value.start();self.addCleanup(value.stop)
    def call(self,**kwargs):
        args=dict(controller=self.c.controller,writer=self.c.writer,owner=self.c.owner,operation_id=self.c.operation_id,custody=self.custody);args.update(kwargs)
        return x.from_existing(**args)
    def refused(self,**kwargs):
        with self.assertRaises((o.Held,self.c.modules[2].Unavailable,FileNotFoundError)):self.call(**kwargs)
    def rewrite_body(self,change):
        path=self.op/'preparation.json';body=self.c.modules[2].decode_json(path.read_text());change(body);path.write_bytes(o.compact(body))
    def test_exact_new_preparation_same_original_saved_binding(self):
        before={p:(p.read_bytes(),o.signature(p)) for p in self.op.iterdir()};value=self.call()
        self.assertIs(type(value),o.RepairPreparation);self.assertIsNot(value,self.prep);self.assertEqual(value.binding,self.prep.binding)
        self.assertEqual(before,{p:(p.read_bytes(),o.signature(p)) for p in self.op.iterdir()})
        for key in ('mutation_authority','adoption_authority','ordinary_source_admission','publication_acceptance','reader_preservation_verified'):self.assertIs(value.binding[key],False)
    def test_missing_completed_metadata_is_typed_held(self):
        (self.op/'preparation.json').unlink()
        with self.assertRaises(o.Held):self.call()
    def test_existing_operation_after_original_writer_lifetime(self):
        original_binding=self.prep.binding;self.hold.__exit__(None,None,None)
        with self.c.writer.hold():self.assertEqual(self.call().revalidate(),original_binding)
    def test_unknown_declared_metadata_cannot_supply_read_path(self):
        self.rewrite_body(lambda body:body['source'].update(path='/unproved/arbitrary/archive'))
        self.custody.files[self.op/'preparation.json']=o.signature(self.op/'preparation.json')
        self.refused()
    def test_retokened_boolean_version_alias_refused(self):
        def changed(body):
            body['version']=True;body.pop('token');body['token']=o.digest(body)
        self.rewrite_body(changed);self.custody.files[self.op/'preparation.json']=o.signature(self.op/'preparation.json');self.refused()
    def test_retokened_adoption_flag_refused(self):
        def changed(body):
            body['adoption_authority']=True;body.pop('token');body['token']=o.digest(body)
        self.rewrite_body(changed);self.custody.files[self.op/'preparation.json']=o.signature(self.op/'preparation.json');self.refused()
    def test_never_reruns_exclusive_prepare(self):
        with patch.object(o,'prepare_existing',side_effect=AssertionError('exclusive prepare forbidden')):self.call().revalidate()
    def test_unknown_owner_refused(self):self.refused(owner=dict(self.c.owner,issueid='unknown'))
    def test_unknown_operation_refused(self):self.refused(operation_id='2'*64)
    def test_invalid_operation_type_refused(self):self.refused(operation_id=True)
    def test_no_caller_path_input(self):
        with self.assertRaises(TypeError):self.call(path=str(self.c.source))
    def test_fake_controller_refused(self):self.refused(controller=object())
    def test_fake_writer_refused(self):self.refused(writer=object())
    def test_fake_custody_refused(self):self.refused(custody=object())
    def test_missing_original_metadata_vector_refused(self):
        del self.custody.files[self.op/'preparation.json'];self.refused()
    def test_missing_original_completed_directory_vector_refused(self):
        del self.custody.files[self.op];self.refused()
    def test_original_vector_boolean_type_alias_refused(self):
        self.custody.files[self.op][0]=True;self.refused()
    def test_metadata_same_bytes_replacement_refused(self):
        path=self.op/'preparation.json';raw=path.read_bytes();path.unlink();path.write_bytes(raw);path.chmod(0o600);self.refused()
    def test_completed_directory_same_files_replacement_refused(self):
        saved=self.op.with_name('saved-directory');self.op.rename(saved);self.op.mkdir(mode=0o700)
        for p in saved.iterdir():p.rename(self.op/p.name)
        self.refused()
    def test_partial_preparation_refused(self):(self.op/'prepared.cbz').unlink();self.refused()
    def test_unknown_stage_member_refused(self):(self.op/'foreign').write_bytes(b'foreign');self.refused()
    def test_directory_mode_refused(self):self.op.chmod(0o750);self.refused()
    def test_metadata_mode_refused(self):(self.op/'preparation.json').chmod(0o640);self.refused()
    def test_source_same_bytes_replacement_refused(self):
        raw=self.c.source.read_bytes();self.c.source.unlink();self.c.source.write_bytes(raw);self.refused()
    def test_source_attributes_refused(self):self.c.source.chmod(0o600);self.refused()
    def test_original_custody_corruption_refused(self):(self.op/'original.arc').write_bytes(b'foreign');self.refused()
    def test_restore_custody_same_bytes_replacement_refused(self):
        path=self.op/'restored-original.arc';raw=path.read_bytes();path.unlink();path.write_bytes(raw);self.refused()
    def test_stage_corruption_refused(self):(self.op/'prepared.cbz').write_bytes(b'foreign');self.refused()
    def test_stage_hardlink_refused(self):os.link(self.op/'prepared.cbz',self.c.root/'foreign-link');self.refused()
    def test_stage_symlink_refused(self):
        path=self.op/'prepared.cbz';path.rename(self.c.root/'retained-stage');path.symlink_to(self.c.root/'retained-stage');self.refused()
    def test_foreign_intent_refused(self):(self.op/'intent.json').write_bytes(b'{}');self.refused()
    def test_pending_marker_refused(self):
        (self.c.writer.root/'archive-repair-v1.pending').write_bytes(b'unknown');self.refused()
    def test_native_companion_refused(self):Path(str(self.c.controller.native_database)+'-wal').write_bytes(b'foreign');self.refused()
    def test_native_unrelated_table_change_refused(self):
        with sqlite3.connect(self.c.controller.native_database) as db:db.execute("UPDATE issues SET Status='Wanted'")
        self.refused()
    def test_expired_custody_refused(self):self.custody.deadline=time.monotonic()-1;self.refused()
    def test_metadata_token_not_authority(self):
        self.rewrite_body(lambda body:body.update(mutation_authority=True));self.refused()
    def test_late_final_custody_source_drift_refused(self):
        fired=[]
        def changed(custody):
            if custody.calls==2:self.c.source.chmod(0o600);fired.append(True)
        self.custody.callback=changed;self.refused();self.assertTrue(fired)
    def test_late_final_custody_metadata_drift_refused(self):
        fired=[]
        def changed(custody):
            if custody.calls==2:(self.op/'preparation.json').chmod(0o640);fired.append(True)
        self.custody.callback=changed;self.refused();self.assertTrue(fired)
    def test_late_final_custody_namespace_refused(self):
        fired=[]
        def changed(custody):
            if custody.calls==2:(self.op/'foreign').write_bytes(b'foreign');fired.append(True)
        self.custody.callback=changed;self.refused();self.assertTrue(fired)
    def test_late_final_custody_purpose_marker_refused(self):
        fired=[]
        def changed(custody):
            if custody.calls==2:(self.c.writer.root/'archive-repair-v1.pending').write_bytes(b'unknown');fired.append(True)
        self.custody.callback=changed;self.refused();self.assertTrue(fired)
    def test_last_constructor_callback_cannot_refresh_original_source(self):
        real=o.RepairPreparation.revalidate;fired=[]
        def changed(value):
            result=real(value)
            if value is not self.prep and not fired:self.c.source.chmod(0o600);fired.append(True)
            return result
        with patch.object(o.RepairPreparation,'revalidate',changed):self.refused()
        self.assertTrue(fired)
    def test_final_claim_loop_has_no_replaceable_directory_helper(self):
        import inspect
        real=x.stat.S_ISDIR;fired=[]
        def late(mode):
            result=real(mode);frame=inspect.currentframe().f_back
            if frame.f_code.co_name=='_from_existing' and frame.f_lineno>120 and not fired:
                (self.op/'preparation.json').chmod(0o640);fired.append(True)
            return result
        with patch.object(x.stat,'S_ISDIR',late):value=self.call()
        self.assertIs(type(value),o.RepairPreparation);self.assertFalse(fired)
        self.assertEqual(o.signature(self.op/'preparation.json'),self.custody.files[self.op/'preparation.json'])

    def test_binding_mutation_does_not_reseal_new_object(self):
        value=self.call();value._binding['mutation_authority']=True
        with self.assertRaises(o.Held):value.revalidate()
    def test_expired_writer_lifetime_refused(self):
        self.hold.__exit__(None,None,None)
        self.refused()

class InstallerControls(unittest.TestCase):
    def test_public_installer_copies_exact_new_factory_idempotently(self):
        import tempfile
        import patch_publication_guard as adapter
        import patch_publication_processing as processing
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'api.py').write_text('class Api:\n'+adapter.METHOD+"commands = ['publicationControl']\n")
            with patch.object(processing,'main'):
                adapter.main(root);first=(root/'publication_archive_preparation_existing.py').read_bytes();adapter.main(root)
            self.assertEqual(first,Path(x.__file__).read_bytes())
            self.assertEqual(first,(root/'publication_archive_preparation_existing.py').read_bytes())
    def test_host_origin_cannot_claim_installed_factory(self):
        with self.assertRaises(o.Held):x.installed()

class ConsumerControls(unittest.TestCase):
    setUp=f.Tests.setUp
    def test_fresh_existing_preparation_enters_exact_reader_adoption_pipeline(self):
        original=self.c.prepare();custody=FixtureCustody(original)
        fake=types.SimpleNamespace(__file__=str(Path(__file__).with_name('publication_reader_lifecycle.py')),StoppedReaderCustody=FixtureCustody)
        with patch.object(x,'installed'),patch.object(x,'lifecycle',fake):
            value=x.from_existing(self.c.controller,self.c.writer,self.c.owner,self.c.operation_id,custody)
        self.assertIs(type(value),o.RepairPreparation)
        lease=f.r.from_stopped(self.life,self.c.source,self.scratch)
        cap=f.a.prepare_existing(value,lease,self.retention)
        self.assertIs(type(cap),f.a.RepairAdoption);cap.install();cap.reverse()
        self.assertEqual(self.c.source.read_bytes(),self.original);self.assertEqual(cap.binding['phase'],'reversed')

if __name__=='__main__':unittest.main()
