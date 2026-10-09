"""Real disposable FD/INI/source/pipe birth; explicitly fake parent and origins."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import os
import sys
import threading
import unittest
from unittest.mock import patch
# Host fixtures use a disposable canonical package, never installed origin grants.
root=Path(__file__).resolve().parent
import types
package=types.ModuleType('mylar');package.__path__=[str(root)];sys.modules['mylar']=package
b=importlib.import_module('mylar.publication_native_scope_birth')
l=importlib.import_module('mylar.publication_reader_lifecycle')
s=importlib.import_module('mylar.publication_native_configured_scope')

REAL_IMPORT_MODULE = importlib.import_module

FIXTURES = Path(__file__).resolve().with_name('reader_birth_fixtures')
spec=importlib.util.spec_from_file_location('owning_scope_controls',FIXTURES/'test_publication_native_configured_scope.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)

class Controls(unittest.TestCase):
    def setUp(self):
        self.fixture=f.Controls();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        p=patch.object(l.importlib,'import_module',lambda name: b if name=='mylar.publication_native_scope_birth' else s if name=='mylar.publication_native_configured_scope' else REAL_IMPORT_MODULE(name));p.start();self.addCleanup(p.stop)
        self.c=self.fixture.c;self.input=Path(self.c.input['path']);self.nonce=self.c.nonce
        self.sha=self.c.input['sha256'];self.parent=self.c.parent['sha256'];self.argv=['fixture-direct-provider']
        self.reader=copy.deepcopy(self.c.doc['reader']);self.provider=self.reader['child_source_sha256']
        self.response=copy.deepcopy(self.c.response)
        self.source=Path(b.__file__);self.source_sha=hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.input.with_suffix('.lifecycle.json').unlink()
        self.seed=dict(version=1,kind='selected-child-native-scope-birth',invocation=dict(
            input_path=str(self.input),input_sha256=self.sha,parent_sha256=self.parent,
            provider_sha256=self.provider,command=self.argv,nonce=self.nonce),
            parent_source=copy.deepcopy(self.c.parent),birth_source=dict(path=str(self.source),sha256=self.source_sha),
            config=dict(path=str(self.fixture.config),sha256=hashlib.sha256(self.fixture.config.read_bytes()).hexdigest()),
            worker_library='/data/comics',selected_image=self.reader['child_image'])
        self.write_seed();self.after_commit=None;self.reply_change=None;self.errors=[];self.frames=[]
        for module,name,value in [(b,'SOURCE',self.source),(l,'BIRTH_SOURCE',self.source),
            (s,'CONFIG_PATH',str(self.fixture.cfg)),(s,'CONFIG_SHA',hashlib.sha256(self.fixture.cfg.read_bytes()).hexdigest()),
            (s,'MAIN_PATH',str(self.fixture.main)),(s,'MAIN_SHA',hashlib.sha256(self.fixture.main.read_bytes()).hexdigest()),
            (s,'installed',lambda:None),(s,'lifecycle',lambda:l),(sys,'orig_argv',self.argv)]:
            p=patch.object(module,name,value);p.start();self.addCleanup(p.stop)
        self.down_read,self.down_write=os.pipe();self.up_read,self.up_write=os.pipe()
        for fd in (self.down_read,self.down_write,self.up_read,self.up_write):self.addCleanup(lambda fd=fd:os.close(fd))
        owner=self
        def initialize(channel):
            channel.input=owner.down_read;channel.output=owner.up_write;channel.seq=0;channel.thread=threading.get_ident()
            channel.facts=(tuple(l.five(os.fstat(channel.input))),tuple(l.five(os.fstat(channel.output))))
            l._PIPE_SEALS[channel]=(channel.input,channel.output,channel.thread,channel.facts)
        p=patch.object(l.ParentPipe,'__init__',initialize);p.start();self.addCleanup(p.stop)
        self.thread=threading.Thread(target=self.parent_loop,daemon=True);self.thread.start()
        self.addCleanup(self.stop_parent)
    def stop_parent(self):
        os.write(self.up_write,b'{}\n');self.thread.join(timeout=2)
    def write_seed(self):
        p=self.input.with_suffix('.birth.json');p.write_bytes(l.encoded(self.seed));p.chmod(0o600)
    def parent_loop(self):
        with os.fdopen(os.dup(self.up_read),'rb') as stream:
            for raw in stream:
                try:
                    request=l.decoded(raw)
                    if request=={}:return
                    self.frames.append(copy.deepcopy(request))
                    self.assertEqual(request['nonce'],self.nonce);self.assertEqual(request['input_sha256'],self.sha)
                    self.assertEqual(request['sequence'],len(self.frames))
                    response=dict(request,type='observation',**copy.deepcopy(self.response))
                    if request['type']=='birth-commit':
                        proof=request['birth']['native_scope'];raw=Path(proof['path']).read_bytes()
                        self.assertEqual(hashlib.sha256(raw).hexdigest(),proof['sha256'])
                        self.assertEqual(l.decoded(raw)['invocation'],self.seed['invocation'])
                        document=copy.deepcopy(self.c.doc);document['command']=self.argv;document['proofs']={'native_scope':proof}
                        p=self.input.with_suffix('.lifecycle.json');p.write_bytes(l.encoded(document));p.chmod(0o600)
                        response.update(type='birth-accepted',lifecycle=dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()),execution_authority=False,publication_acceptance=False)
                        if self.after_commit:self.after_commit()
                        if self.reply_change:self.reply_change(response)
                    os.write(self.down_write,l.encoded(response)+b'\n')
                except BaseException as e:
                    self.errors.append(e);os.write(self.down_write,b'{}\n')
    def born(self):
        result=b.from_checked_parent(self.input,self.sha,self.nonce,parent_sha=self.parent,argv=self.argv)
        self.assertFalse(self.errors);return result
    def test_real_birth_original_child_nodes_and_no_rights(self):
        token=self.born();document=l.decoded(self.input.with_suffix('.native-scope.json').read_bytes())
        self.assertEqual(document['ancestors']['/'],l.five(Path('/').lstat()))
        self.assertEqual(document['config']['signature9'],l.nine(self.fixture.config.lstat()))
        self.assertEqual(self.frames[0]['type'],'challenge');self.assertEqual(self.frames[1]['type'],'birth-commit')
        token.original()
    def test_handoff_same_pipe_then_actual_lifecycle_scope_factory(self):
        token=self.born();channel=token.channel;custody=l.from_birth(token)
        self.assertIs(custody.channel,channel);self.assertGreater(channel.seq,2)
        scope=s.from_checked_parent(custody);self.assertEqual(scope.binding['roots'],[str(self.fixture.library)])
        self.assertFalse(scope.binding['mutation_authority']);self.assertFalse(scope.binding['publication_acceptance'])
        with self.assertRaises(l.Held):l.from_birth(token)
    def test_seed_has_no_ancestor_DTO(self):
        self.seed['ancestors']={'/':[1,2,3,4,5]};self.write_seed()
        with self.assertRaises(l.Held):self.born()
        self.assertFalse(self.input.with_suffix('.native-scope.json').exists())
    def test_caller_config_path_cannot_change_derived_scope(self):
        self.seed['config']['path']=str(self.fixture.cfg);self.write_seed()
        with self.assertRaises(l.Held):self.born()
    def test_expected_config_hash_drift_refuses(self):
        self.fixture.config.write_text('[General]\ndestination_dir = /foreign\n')
        with self.assertRaises(s.Held):self.born()
    def test_existing_proof_never_overwritten(self):
        p=self.input.with_suffix('.native-scope.json');p.write_bytes(b'old');p.chmod(0o600)
        with self.assertRaises(l.Held):self.born()
        self.assertEqual(p.read_bytes(),b'old')
    def test_parent_mount_drift_after_capture_refuses(self):
        self.reply_change=lambda r:r['child_mounts'][0].update(RW=True)
        with self.assertRaises(l.Held):self.born()
    def test_last_parent_ACK_config_drift_refuses(self):
        self.after_commit=lambda:self.fixture.config.chmod(0o640)
        with self.assertRaises(l.Held):self.born()
    def test_last_parent_ACK_root_drift_refuses(self):
        self.after_commit=lambda:self.fixture.library.chmod(0o750)
        with self.assertRaises(l.Held):self.born()
    def test_harmless_parent_publication_counter_is_not_identity(self):
        self.reply_change=lambda r:r['native']['publication'].update(request_counter=2)
        token=self.born();token.original()
    def test_parent_birth_envelope_drift_refuses(self):
        self.reply_change=lambda r:r['birth'].update(seed_sha256='f'*64)
        with self.assertRaises(l.Held):self.born()
    def test_boolean_zero_is_not_false_right(self):
        self.reply_change=lambda r:r.update(execution_authority=0)
        with self.assertRaises(l.Held):self.born()
    def test_stale_token_no_rebaseline(self):
        token=self.born();self.fixture.config.chmod(0o640)
        with self.assertRaises(l.Held):l.from_birth(token)
    def test_tampered_token_cannot_reseal(self):
        token=self.born();token.nodes[Path('/')][1]+=1;token.seal=token.core()
        with self.assertRaises(l.Held):token.original()
    def test_canonical_production_module_and_type_identity(self):
        self.assertIs(b.life,l);self.assertIs(b.scope,s)
        token=self.born();self.assertIs(type(token.channel),l.ParentPipe);self.assertIs(type(token),b.BirthMetadata)
    def test_census_drift_during_birth_is_identity(self):
        self.reply_change=lambda r:r['native']['publication']['census'].update(revision=2)
        with self.assertRaises(s.Held):self.born()
    def test_token_cannot_cross_threads(self):
        token=self.born();errors=[]
        def check():
            try:token.original()
            except BaseException as e:errors.append(e)
        thread=threading.Thread(target=check);thread.start();thread.join()
        self.assertEqual(len(errors),1);self.assertIs(type(errors[0]),l.Held)
    def test_late_sidecar_decode_callback_cannot_rebaseline(self):
        token=self.born();original=l.decoded
        def decode(raw):
            value=original(raw)
            if value.get('kind')=='owning-reader-pipe-custody':self.fixture.config.chmod(0o640)
            return value
        with patch.object(l,'decoded',decode):
            with self.assertRaises(l.Held):l.from_birth(token)
    def test_noncanonical_foreign_token_rejected(self):
        with self.assertRaises(l.Held):l.from_birth(object())
    def test_actual_provider_argv_required(self):
        with self.assertRaises(l.Held):b.from_checked_parent(self.input,self.sha,self.nonce,parent_sha=self.parent,argv=['foreign'])
    def test_changed_birth_module_pin_refuses_before_parent_capture(self):
        self.seed['birth_source']['sha256']='f'*64;self.write_seed()
        with self.assertRaises(s.Held):self.born()
        self.assertFalse(self.frames)
if __name__=='__main__':unittest.main()
