"""UID-owned isolated installation fixtures, NOT actual root installation authority."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import standalone_launch_auth as a
import v3_auth_core as c

spec=importlib.util.spec_from_file_location('host_fixture_crypto',str(Path(__file__).parent.parent/'host_crypto/private_crypto.py'))
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)

class Fixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keys=tempfile.TemporaryDirectory(prefix='comic-install-fixture-key-');cls.key=Path(cls.keys.name)/'key.pem';Path(cls.keys.name).chmod(0o700)
        cls.runtime=h._HostExperiment();z=cls.runtime._execute(['genpkey','-algorithm','ED25519','-out',str(cls.key)]);assert z.returncode==0;cls.key.chmod(0o600)
        fd=os.open(cls.key,os.O_RDONLY|os.O_NOFOLLOW)
        try:z=cls.runtime._execute(['pkey','-pubout','-outform','DER','-in','/proc/self/fd/'+str(fd)],key_fd=fd);assert z.returncode==0;cls.public=z.stdout
        finally:os.close(fd)
    @classmethod
    def tearDownClass(cls):cls.keys.cleanup()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='comic-install-fixture-');self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.install=self.root/'installation';self.install.mkdir();self.native=self.root/'native';self.native.mkdir();self.auth=Path(a.__file__).parent
        sources={}
        for name in a._REQUIRED:
            p=self.native/name;p.write_bytes(b'ENABLED=False\n');sources[str(p)]=c._hash(p.read_bytes())
        for name in ('standalone_launch_auth.py','v3_auth_core.py','private_crypto.py'):
            p=self.auth/name;sources[str(p)]=c._hash(p.read_bytes())
        self.inventory={'version':1,'kind':'standalone-leaf-inventory-v1','sources':sources}
        self.anchor={'version':1,'kind':'standalone-installation-anchor-v1','deployment':'1'*64,'profile':'2'*64,'broker_sources':'3'*64,'parent_sha256':'4'*64,'bootstrap_sha256':c._hash(b'PRIVATE FIXTURE PAYLOAD'),'inventory_sha256':c._hash(c._canonical(self.inventory)),'key_sha256':c._hash(self.public)}
        self.write()
        self.patches=[patch.object(a,'_INSTALL',self.install),patch.object(a,'_AUTH',self.auth),patch.object(a,'_NATIVE',self.native),patch.object(a,'_ANCHOR',self.install/'installation-v1.json'),patch.object(a,'_INVENTORY',self.install/'inventory-v1.json'),patch.object(a,'_KEY',self.install/'public-ed25519.der')]
        for ctx in self.patches:ctx.start();self.addCleanup(ctx.stop)
    def write(self):
        (self.install/'installation-v1.json').write_bytes(c._canonical(self.anchor));(self.install/'inventory-v1.json').write_bytes(c._canonical(self.inventory));(self.install/'public-ed25519.der').write_bytes(self.public)
    def fixture_security(self,frame):
        # Explicit UID-owned fixture substitute; production root check is NOT proved.
        for p in frame.leaves:
            z=p.lstat()
            if z.st_uid!=os.geteuid() or z.st_mode&0o022:raise c.Held('fixture-owner-mode')
    def load(self):
        with patch.object(a,'_root_security',self.fixture_security):return a.load_original_installation()
    def test_production_root_boundary_rejects_UID_fixture(self):
        with self.assertRaisesRegex(c.Held,'root-security'):a.load_original_installation()
    def test_fixture_finite_loader_positive_no_default_activation(self):
        obj=self.load()
        with patch.object(a,'_root_security',self.fixture_security):row=obj.close()
        self.assertEqual(row['native_map'],{n:c._hash(b'ENABLED=False\n') for n in a._REQUIRED})
        self.assertNotEqual(self.anchor['deployment'],'7'*64)
    def test_anchor_inventory_and_key_wrong_pins_hold(self):
        for name in ('inventory_sha256','key_sha256'):
            saved=self.anchor[name];self.anchor[name]='9'*64;self.write()
            with self.assertRaises(c.Held):self.load()
            self.anchor[name]=saved
        self.write()
    def test_extra_anchor_and_boolean_version_hold(self):
        self.anchor['extra']=1;self.write()
        with self.assertRaises(c.Held):self.load()
        self.anchor.pop('extra');self.anchor['version']=True;self.write()
        with self.assertRaises(c.Held):self.load()
    def test_inventory_cannot_embed_anchor_or_itself(self):
        for path in (self.install/'installation-v1.json',self.install/'inventory-v1.json'):
            self.inventory['sources'][str(path)]='9'*64;self.anchor['inventory_sha256']=c._hash(c._canonical(self.inventory));self.write()
            with self.assertRaises(c.Held):self.load()
            del self.inventory['sources'][str(path)]
    def test_foreign_source_path_and_missing_canonical_leaf_hold(self):
        self.inventory['sources']['/etc/passwd']='9'*64;self.anchor['inventory_sha256']=c._hash(c._canonical(self.inventory));self.write()
        with self.assertRaises(c.Held):self.load()
        del self.inventory['sources']['/etc/passwd'];del self.inventory['sources'][str(self.native/'publication_api.py')];self.anchor['inventory_sha256']=c._hash(c._canonical(self.inventory));self.write()
        with self.assertRaises(c.Held):self.load()
    def test_canonical_crypto_origin_is_required(self):
        with patch.object(a.crypto,'__file__','/tmp/foreign-crypto.py'),self.assertRaisesRegex(c.Held,'canonical-auth-origins'):self.load()
    def test_auth_bytecode_absence_is_original(self):
        path=self.auth/'private_crypto.pyc';self.addCleanup(path.unlink,missing_ok=True);path.write_bytes(b'not trusted source')
        with self.assertRaises(c.Held):self.load()
        path.unlink();obj=self.load();path.write_bytes(b'late bytecode')
        with patch.object(a,'_root_security',self.fixture_security),self.assertRaises(c.Held):obj.close()

    def test_original_source_change_after_loader_hold(self):
        obj=self.load();(self.native/'config.py').chmod(0o600)
        with patch.object(a,'_root_security',self.fixture_security),self.assertRaises(c.Held):obj.close()
    def test_last_declared_security_callback_source_fault_hold(self):
        real=self.fixture_security;fired=[]
        def later(frame):
            real(frame)
            if (self.native/'config.py') in frame.leaves and not fired:
                (self.native/'config.py').chmod(0o600);fired.append(True)
        with patch.object(a,'_root_security',later),self.assertRaises(c.Held):a.load_original_installation()
        self.assertTrue(fired)
    def test_source_symlink_hold(self):
        p=self.native/'config.py';p.unlink();p.symlink_to(self.native/'__init__.py')
        with self.assertRaises(c.Held):self.load()
    def test_source_hardlink_hold(self):
        os.link(self.native/'config.py',self.root/'foreign-alias')
        with self.assertRaises(c.Held):self.load()

    def test_plain_constructor_and_copied_token_hold(self):
        for cls in (a.LaunchAdmission,a.ActionBinding,a._Installation):
            with self.assertRaises(c.Held):cls()
        token=object.__new__(a.LaunchAdmission)
        with self.assertRaises(c.Held):token.claim_action(sys.modules[__name__],{},0,1)
    def test_auth_envelope_canonical_and_bad_signature_shapes(self):
        for raw in (b'{"assertion":{},"signature":"00"}',b'{"assertion":{},"signature":"'+b'A'*128+b'"}',b'{"assertion":{},"signature":"'+b'0'*128+b'","extra":1}'):
            with self.assertRaises(c.Held):a._envelope(raw)
    def test_no_caller_selected_stdio_before_install_load(self):
        with patch.object(a,'load_original_installation',side_effect=AssertionError('must not load')):
            with self.assertRaises(c.Held):a.authenticate_original({},8,9,{})
    def test_fixed_stdio_requires_actual_pipe_types(self):
        with patch.object(a.os,'fstat',return_value=type('Fact',(),{'st_mode':0o100600})()),patch.object(a,'load_original_installation',side_effect=AssertionError('must not load')):
            with self.assertRaisesRegex(c.Held,'stdio-pipes'):a.authenticate_original({},0,1,{})
    def test_v3_regular_headers_strict(self):
        value={'version':3,'protocol':'standalone-retained-repeat-v3','kind':'initialized','nonce':'5'*64,'sequence':1,'challenge':'6'*64,'payload':{}}
        self.assertEqual(a._wire(c._canonical(value)),value)
        for k,v in [('version',True),('version',2),('sequence',True),('protocol','other')]:
            changed=dict(value);changed[k]=v
            with self.assertRaises(c.Held):a._wire(c._canonical(changed))

    def _sign(self,raw):
        fd=os.open(self.key,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            with h._Memfd(raw) as m:
                z=self.runtime._execute(['pkeyutl','-sign','-rawin','-provider','default','-propquery','provider=default','-in',m.path,'-inkey','/proc/self/fd/'+str(fd)],(m,),key_fd=fd)
                self.assertEqual(z.returncode,0);return z.stdout
        finally:os.close(fd)
    def _worker(self,alter=None,fault=None):
        def ref(path):
            path.chmod(0o600);frame=a._OriginalSources([path]);return {'path':str(path),'sha256':c._hash(path.read_bytes()),'signature9':list(frame.leaves[path][0])}
        review=self.root/'review.json';review.write_bytes(c._canonical({'fixture':'NOT GENUINE REVIEW'}))
        mapping=self.root/'map.json';mapping.write_bytes(c._canonical({n:c._hash(b'ENABLED=False\n') for n in a._REQUIRED}))
        config=self.root/'config.json';config.write_bytes(c._canonical({'fixture':'NO CONFIG IMPORT'}))
        boot={'version':1,'kind':'standalone-retained-bootstrap-v1','nonce':'5'*64,'challenge':'6'*64,'parent_sha256':self.anchor['parent_sha256'],'request':{},'config_ref':ref(config),'data_root':str(self.root),'source_map_ref':ref(mapping),'review_ref':ref(review)}
        path=self.root/'input.json';path.write_bytes(c._canonical(boot));boot_ref=ref(path)
        settings={'backend':str(Path(__file__).parent.parent/'host_crypto/private_crypto.py'),'boot_ref':boot_ref,'fault':fault};(self.root/'settings.json').write_text(json.dumps(settings))
        worker=subprocess.Popen([sys.executable,'-I','-B','-c',"import sys;sys.path.insert(0,sys.argv[1]);sys.argv=sys.argv[1:];exec(open(sys.argv[0]+'/fixture_worker.py').read())",str(self.auth),str(self.root)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            challenge=worker.stdout.readline().rstrip(b'\n');self.assertTrue(challenge);packet=c._parse(challenge)
            assertion={'domain':c._DOMAIN,'measured':packet['measured'],'challenge':packet['challenge'],'child_pid':packet['child_pid'],'child_start':packet['child_start'],'challenge_frame':c._hash(challenge),'session':'7'*64,'broker_nonce':'8'*64,'purpose':'retained-standalone','lifetime_ms':5000,'host_observation':{'container':'9'*64,'start':'a'*64,'host_pid':worker.pid,'image':'b'*64}}
            if alter:alter(assertion)
            raw=c._canonical(assertion);signature=self._sign(raw);worker.stdin.write(c._canonical({'assertion':assertion,'signature':signature.hex()})+b'\n');worker.stdin.flush()
            transcript=__import__('hashlib').sha256(challenge+raw+signature).digest();admission=c._hash(raw+signature)
            if not alter and (not fault or fault=='delayed'):
                for sequence,kind in ((1,'initialized'),(3,'observed'),(5,'observed-final-ACK')):
                    rawchild=worker.stdout.readline().rstrip(b'\n');child=c._parse(rawchild);self.assertEqual(child['sequence'],sequence)
                    normal=c._canonical({'sequence':sequence,'kind':'final-ACK' if sequence==5 else kind,'payload':child});transcript=__import__('hashlib').sha256(transcript+normal).digest()
                    wire={'version':3,'protocol':'standalone-retained-repeat-v3','kind':{2:'backup-ready',4:'observed-release',6:'observed-exit'}[sequence+1],'nonce':boot['nonce'],'sequence':sequence+1,'challenge':boot['challenge'],'payload':{'fixture':'NO BACKUP AUTHORITY'}}
                    stage={'domain':'standalone-fixed-stage-v3','session':'7'*64,'admission':admission,'challenge':packet['challenge'],'sequence':sequence+1,'kind':wire['kind'],'previous':transcript.hex(),'payload':wire,'payload_digest':c._hash(c._canonical(wire))}
                    rawstage=c._canonical(stage);sig=self._sign(rawstage);worker.stdin.write(c._canonical({'assertion':stage,'signature':sig.hex()})+b'\n');worker.stdin.flush();transcript=__import__('hashlib').sha256(transcript+rawstage+sig).digest()
            out,err=worker.communicate(timeout=10)
            return worker.returncode,out,err
        finally:
            if worker.poll() is None:worker.kill();worker.wait()
            for stream in (worker.stdin,worker.stdout,worker.stderr):stream.close()
    def test_real_fixture_stdio_preauth_mint_once_and_six_signed_rounds(self):
        code,out,err=self._worker();self.assertEqual(code,0,err.decode());self.assertEqual(out,b'')
    def test_real_fixture_delayed_initialization_after_typed_consume(self):
        code,out,err=self._worker(fault='delayed');self.assertEqual(code,0,err.decode());self.assertEqual(out,b'')
    def test_real_fixture_expired_consume_no_native_round(self):
        code,out,err=self._worker(fault='expired-consume');self.assertNotEqual(code,0);self.assertEqual(out,b'');self.assertIn(b'original-context',err)
    def test_real_fixture_wrong_challenge_no_native_round_or_token(self):
        code,out,err=self._worker(lambda assertion:assertion.update(challenge='0'*64));self.assertNotEqual(code,0);self.assertEqual(out,b'');self.assertIn(b'admission-claims',err)

    def test_real_fixture_last_data_close_source_fault_no_native_round(self):
        code,out,err=self._worker(fault='source');self.assertNotEqual(code,0);self.assertEqual(out,b'');self.assertIn(b'auth-original-source',err)
    def test_real_fixture_last_data_close_original_null_fact_no_native_round(self):
        code,out,err=self._worker(fault='null');self.assertNotEqual(code,0);self.assertEqual(out,b'');self.assertIn(b'auth-original-null',err)
    def test_real_fixture_last_data_close_logical_fault_no_native_round(self):
        code,out,err=self._worker(fault='logical');self.assertNotEqual(code,0);self.assertEqual(out,b'');self.assertIn(b'auth-final-original-logical',err)
    def test_real_fixture_last_start_helper_state_fault_no_native_round(self):
        code,out,err=self._worker(fault='start-state');self.assertNotEqual(code,0);self.assertEqual(out,b'');self.assertIn(b'auth-original-transcript-state',err)
    def test_real_fixture_last_data_close_state_fault_no_native_round(self):
        code,out,err=self._worker(fault='state');self.assertNotEqual(code,0);self.assertEqual(out,b'');self.assertIn(b'auth-original-transcript-state',err)
    def test_real_fixture_last_data_close_pipe_fault_no_native_round(self):
        code,out,err=self._worker(fault='pipe');self.assertNotEqual(code,0);self.assertEqual(out,b'');self.assertIn(b'auth-final-original-pipe',err)

if __name__=='__main__':unittest.main()
