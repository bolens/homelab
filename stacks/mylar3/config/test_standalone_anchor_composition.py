"""Actual source/files in a disposable UID projection, not root enrollment/Docker."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).parent
HOST=ROOT/'standalone_launch_host'
sys.path.insert(0,str(HOST))

def load(name):
    spec=importlib.util.spec_from_file_location(name,HOST/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class Anchors(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path.home());self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.root.chmod(0o700);self.review=self.root/'reviewed-child';self.review.mkdir(mode=0o700)
        self.child=self.root/'child';self.enroll=self.root/'enrollment-v1.json';self.deployment=self.root/'deployment-v1.json'
        self.package=self.root/'package';self.package.mkdir(mode=0o700)
        for name in ('private_crypto.py','comic_reader_backup_primitives.py','comic_retained_standalone_backup.py','comic_retained_standalone_parent.py','comic_retained_standalone_broker.py','comic_native_process_probe.py','publication_native_configured_scope.py','BOOTSTRAP.py'):
            path=self.package/name;path.write_bytes((HOST/name).read_bytes());path.chmod(0o444)
        spec=importlib.util.spec_from_file_location('actual_copied_broker',self.package/'comic_retained_standalone_broker.py')
        self.b=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.b)
        self.key=self.root/'key';self.key.write_bytes(b'public fixture unused signing key');self.key.chmod(0o600)
        self.ctx=patch.multiple(self.b,ROOT_UID=os.geteuid(),PACKAGE=self.package,KEY=self.key,ENROLLMENT=self.enroll,INSTALLATION=self.deployment,REVIEWED_ANCHORS=self.review,CHILD_ANCHORS=self.child);self.ctx.start();self.addCleanup(self.ctx.stop)
        sources={**{'/opt/mylar-publication-launch/auth/'+x:'1'*64 for x in ('private_crypto.py','v3_auth_core.py','standalone_launch_auth.py')},**{'/app/mylar3/mylar/source_'+str(i)+'.py':'2'*64 for i in range(9)}}
        inv=self.b.canonical(dict(version=1,kind='standalone-leaf-inventory-v1',sources=sources))
        key=bytes.fromhex('302a300506032b6570032100'+'11'*32)
        self.doc=dict(deployment='a'*64,profile=self.b.LOGICAL_PROFILE_SHA,broker_sources='b'*64,parent_sha256='c'*64,bootstrap_sha256='d'*64,inventory_sha256=self.b.sha(inv),key_sha256=self.b.sha(key),public_der=key.hex())
        host_sources={n:self.b.sha((self.package/n).read_bytes()) for n in self.b.NAMES}
        self.doc.update(version=1,kind='standalone-root-deployment-v1',image='f'*64,runtime_profile_sha256='e'*64,host_sources=host_sources,daemon_sources={'/app/mylar3/mylar/worker_health.py':'6'*64,'/app/mylar3/mylar/native_writers.py':'7'*64},ids=dict(native='1'*64,reader='2'*64,worker='3'*64))
        self.doc.update(broker_sources=self.b.sha(self.b.canonical(host_sources)),parent_sha256=host_sources['comic_retained_standalone_parent.py'],bootstrap_sha256=host_sources['BOOTSTRAP.py'])
        anchor=self.b.canonical(dict(version=1,kind='standalone-installation-anchor-v1',**{k:self.doc[k] for k in ('deployment','profile','broker_sources','parent_sha256','bootstrap_sha256','inventory_sha256','key_sha256')}));self.doc['anchor_sha256']=self.b.sha(anchor)
        for name,raw in zip(self.b.ANCHOR_NAMES,(anchor,inv,key)):
            p=self.review/name;p.write_bytes(raw);p.chmod(0o444)
        self.deployment.write_bytes(self.b.canonical(self.doc));self.deployment.chmod(0o600)
        self.enroll.write_bytes(self.b.canonical(dict(version=1,kind='standalone-root-enrollment-v1',deployment_sha256=self.b.sha(self.deployment.read_bytes()))));self.enroll.chmod(0o600)
    def test_exact_exclusive_public_copy_and_idempotence(self):
        self.assertFalse(self.b.provision_original_anchors()['activation'])
        before={p.name:self.b.nine(p.stat()) for p in self.child.iterdir()}
        self.b.provision_original_anchors();self.assertEqual(before,{p.name:self.b.nine(p.stat()) for p in self.child.iterdir()})
        for p in self.child.iterdir():
            self.assertEqual(p.read_bytes(),(self.review/p.name).read_bytes());self.assertNotEqual(p.stat().st_ino,(self.review/p.name).stat().st_ino)
    def test_missing_empty_and_symlink_originals_refuse(self):
        leaf=self.review/self.b.ANCHOR_NAMES[0];raw=leaf.read_bytes();leaf.unlink()
        with self.assertRaises(FileNotFoundError):self.b.provision_original_anchors()
        leaf.write_bytes(b'');leaf.chmod(0o444)
        with self.assertRaises(ValueError):self.b.provision_original_anchors()
        leaf.unlink();other=self.root/'other';other.write_bytes(raw);leaf.symlink_to(other)
        with self.assertRaises(ValueError):self.b.provision_original_anchors()
        self.assertFalse(self.child.exists())
    def test_changed_key_and_inventory_refuse(self):
        for name in self.b.ANCHOR_NAMES[1:]:
            p=self.review/name;raw=p.read_bytes();p.chmod(0o600);p.write_bytes(raw+b' ');p.chmod(0o444)
            with self.assertRaises(ValueError):self.b.provision_original_anchors()
            p.chmod(0o600);p.write_bytes(raw);p.chmod(0o444)
        self.assertFalse(self.child.exists())
    def test_late_original_replacement_refuses(self):
        real=self.b.read;fired=[];leaf=self.review/self.b.ANCHOR_NAMES[0]
        def change(path,frame):
            raw=real(path,frame)
            if Path(path).name==self.b.ANCHOR_NAMES[-1]:
                replacement=self.root/'replace';replacement.write_bytes(leaf.read_bytes());replacement.chmod(0o444);replacement.replace(leaf);fired.append(True)
            return raw
        with patch.object(self.b,'read',change),self.assertRaises(ValueError):self.b.provision_original_anchors()
        self.assertTrue(fired);self.assertFalse(self.child.exists())
    def test_created_leaf_fsync_mode_drift_refuses(self):
        real=self.b.os.fsync
        def change(fd):real(fd);os.fchmod(fd,0o640)
        with patch.object(self.b.os,'fsync',change),self.assertRaises(ValueError):self.b.provision_original_anchors()
    def test_partial_or_foreign_destination_never_filled(self):
        self.child.mkdir(mode=0o700);(self.child/'foreign').write_bytes(b'public')
        with self.assertRaises(ValueError):self.b.provision_original_anchors()
        self.assertEqual(set(os.listdir(self.child)),{'foreign'})
    def test_changed_installed_source_refuses_before_destination(self):
        path=self.package/'comic_retained_standalone_parent.py';path.chmod(0o600);path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'source-digest'):self.b.provision_original_anchors()
        self.assertFalse(self.child.exists())
    def test_profile_mismatch_refuses_before_destination(self):
        self.doc['profile']='0'*64;self.deployment.write_bytes(self.b.canonical(self.doc));self.enroll.write_bytes(self.b.canonical(dict(version=1,kind='standalone-root-enrollment-v1',deployment_sha256=self.b.sha(self.deployment.read_bytes()))))
        with self.assertRaises(ValueError):self.b.provision_original_anchors()
        self.assertFalse(self.child.exists())
    def test_placeholder_only_genuine_bootstrap_read_refuses(self):
        import ast
        import types
        tree=ast.parse((HOST/'BOOTSTRAP.py').read_bytes())
        names={'need','nine','read'}
        selected=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[])
        module=types.ModuleType('original_bootstrap_read');module.os=os
        exec(compile(selected,str(HOST/'BOOTSTRAP.py'),'exec'),module.__dict__)
        path=self.root/'empty-placeholder';path.write_bytes(b'');path.chmod(0o444)
        with self.assertRaisesRegex(ValueError,'bootstrap-size'):
            module.read(str(path),module.nine(path.stat()),65536)
    def test_last_namespace_callback_cannot_adopt_creator_mode(self):
        original=self.b.os.listdir;fired=[]
        def callback(path):
            result=original(path)
            if Path(path)==self.child and len(result)==3:
                os.chmod(self.child/self.b.ANCHOR_NAMES[0],0o600);fired.append(True)
            return result
        with patch.object(self.b.os,'listdir',callback),self.assertRaisesRegex(ValueError,'final-creator'):
            self.b.provision_original_anchors()
        self.assertTrue(fired)
    def test_existing_writable_anchor_is_not_repaired(self):
        self.b.provision_original_anchors();path=self.child/self.b.ANCHOR_NAMES[0];path.chmod(0o600)
        with self.assertRaisesRegex(ValueError,'existing-mode'):self.b.provision_original_anchors()
        self.assertEqual(path.stat().st_mode&0o777,0o600)
    def test_no_caller_mount_or_callback_parameters(self):
        for kwargs in ({'source':self.root},{'callback':lambda:None},{'mounts':[]}):
            with self.assertRaises(TypeError):self.b.provision_original_anchors(**kwargs)

class Profile(unittest.TestCase):
    def setUp(self):
        self.p=load('comic_retained_standalone_parent')
        self.native={'Image':'sha256:'+'a'*64,'Mounts':[dict(Type='bind',Source='/public/data',Destination='/config',RW=True)]}
        self.selected={'Image':self.native['Image'],'Config':{'User':'1000:1000'},'HostConfig':dict(ReadonlyRootfs=True,Privileged=False,CapAdd=None,CapDrop=['ALL'],PortBindings={},Devices=[],NetworkMode='none',SecurityOpt=['no-new-privileges']),'NetworkSettings':{'Networks':{}},'Mounts':[dict(self.native['Mounts'][0])]+[dict(Type='bind',Source=self.p.ANCHOR_SOURCE+n,Destination=self.p.ANCHOR_TARGET+n,RW=False) for n in self.p.ANCHOR_NAMES]}
    def test_actual_launch_argument_builder_adds_only_fixed_readonly_leaves(self):
        import ast
        broker=load('comic_retained_standalone_broker')
        tree=ast.parse((HOST/'comic_retained_standalone_broker.py').read_bytes())
        method=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='launch_original')
        first=next(i for i,n in enumerate(method.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='arguments' for t in n.targets))
        last=next(i for i,n in enumerate(method.body[first:],first) if isinstance(n,ast.AugAssign) and isinstance(n.target,ast.Name) and n.target.id=='arguments')
        body=ast.Module(body=method.body[first:last+1],type_ignores=[])
        native=dict(self.native,Config={'Env':[]})
        scope=dict(Path=Path,Held=broker.Held,native=native,ANCHOR_NAMES=broker.ANCHOR_NAMES,CHILD_ANCHORS=Path('/etc/mylar-publication-launch/child'),bootstrap=b'# public argv fixture',input_child='/config/input.json',input_ref={'sha256':'f'*64})
        exec(compile(body,str(HOST/'comic_retained_standalone_broker.py'),'exec'),scope)
        args=scope['arguments'];mounts=[args[i+1] for i,x in enumerate(args) if x=='--mount']
        self.assertEqual(mounts,['type=bind,src=/public/data,dst=/config']+['type=bind,src=/etc/mylar-publication-launch/child/'+n+',dst=/opt/mylar-publication-launch/'+n+',readonly' for n in broker.ANCHOR_NAMES])
        self.assertIn('--read-only',args);self.assertEqual(args[args.index('--network')+1],'none')
    def test_exact_finite_mount_profile_and_legacy_strict(self):
        self.assertTrue(self.p.selected_profile(self.native,self.selected,installed_anchors=True))
        with self.assertRaises(ValueError):self.p.selected_profile(self.native,self.selected)
    def test_writable_extra_duplicate_and_foreign_source_refuse(self):
        original=list(self.selected['Mounts'])
        variants=[original+[dict(original[-1])],original+[dict(Type='bind',Source='/foreign',Destination='/extra',RW=False)],original[:-1],original[:-1]+[dict(original[-1],RW=True)],original[:-1]+[dict(original[-1],RW=0)],original[:-1]+[dict(original[-1],Source='/foreign')]]
        for mounts in variants:
            self.selected['Mounts']=mounts
            with self.assertRaises(ValueError):self.p.selected_profile(self.native,self.selected,installed_anchors=True)
    def test_protected_native_overlay_and_nonboolean_profile_refuse(self):
        for dest in ('/app','/etc','/opt/mylar-publication-launch'):
            mount=dict(Type='bind',Source='/foreign',Destination=dest,RW=False)
            self.native['Mounts']=[mount];self.selected['Mounts'][0]=mount
            with self.assertRaises(ValueError):self.p.selected_profile(self.native,self.selected,installed_anchors=True)
        with self.assertRaises(ValueError):self.p.selected_profile(self.native,self.selected,installed_anchors=1)

if __name__=='__main__':unittest.main()
