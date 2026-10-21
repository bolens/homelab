"""Exact intent boundary only; invocation spy is not genuine Parent/engine proof."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import copy
import hashlib
import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('host',Path(__file__).with_name('comic_nfs_host_engine.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Intents(unittest.TestCase):
    def setUp(self):
        self.cid='a'*64;self.nonce='b'*64;self.calls=[]
        self.argv=['docker','exec','-i',self.cid,'/lsiopy/bin/python3','-I','-B','-']
        self.document=dict(version=1,kind='host-original-nfs-engine-intents-v1',nonce=self.nonce,calls=[dict(argv=self.argv,input_sha256=hashlib.sha256(b'original source').hexdigest(),timeout_max=30,uses=1)])
    def contract(self):return m.ExactCalls(self.document,self.nonce,['docker'],[self.cid])
    def dispatch(self,contract,argv,data=b'original source',timeout=30):
        contract.approve(argv,data,timeout);self.calls.append((argv,data,timeout))
    def test_exact_call_and_no_replay(self):
        c=self.contract();self.dispatch(c,self.argv);self.assertEqual(len(self.calls),1)
        with self.assertRaises(m.Held):self.dispatch(c,self.argv)
        self.assertEqual(len(self.calls),1)
    def test_foreign_CID_image_argv_options_never_invoked(self):
        variants=[]
        foreign=self.argv.copy();foreign[3]='c'*64;variants.append(foreign)
        image=self.argv.copy();image[3]='sha256:'+'c'*64;variants.append(image)
        option=self.argv.copy();option.insert(2,'--privileged');variants.append(option)
        command=self.argv.copy();command[-1]='foreign.py';variants.append(command)
        for argv in variants:
            with self.subTest(argv=argv),self.assertRaises(m.Held):self.dispatch(self.contract(),argv)
        self.assertEqual(self.calls,[])
    def test_changed_stdin_or_timeout_never_invoked(self):
        for data,timeout in ((b'foreign source',30),(b'original source',31)):
            with self.assertRaises(m.Held):self.dispatch(self.contract(),self.argv,data,timeout)
        self.assertEqual(self.calls,[])
    def test_unowned_creation_and_start_default_refuse(self):
        for argv in (['docker','create','--privileged','sha256:'+'c'*64],['docker','start',self.cid]):
            doc=copy.deepcopy(self.document);doc['calls'][0]['argv']=argv
            with self.assertRaisesRegex(m.Held,'birth-session-unbound'):m.ExactCalls(doc,self.nonce,['docker'],[self.cid])
    def test_declared_foreign_inspect_refuses(self):
        doc=copy.deepcopy(self.document);doc['calls'][0]['argv']=['docker','inspect','c'*64]
        with self.assertRaisesRegex(m.Held,'original-role-CID'):m.ExactCalls(doc,self.nonce,['docker'],[self.cid])
class FixedUser(unittest.TestCase):
    def test_declared_fixed_user_and_findmnt_only(self):
        cid='a'*64;nonce='b'*64
        for argv in (['docker','exec','--user','1000:1000',cid,'/lsiopy/bin/python3'],['docker','exec','-i','--user','1000:1000',cid,'/lsiopy/bin/python3'],['findmnt','--json','--target','/public-fixture','--output','SOURCE,TARGET,FSTYPE,FSROOT,OPTIONS,MAJ:MIN']):
            doc=dict(version=1,kind='host-original-nfs-engine-intents-v1',nonce=nonce,calls=[dict(argv=argv,input_sha256=None,timeout_max=30,uses=1)])
            m.ExactCalls(doc,nonce,['docker'],[cid]).approve(argv,None,30)
        argv=['docker','exec','--user','0',cid,'/lsiopy/bin/python3']
        doc['calls'][0]['argv']=argv
        with self.assertRaisesRegex(m.Held,'fixed-exec-user'):m.ExactCalls(doc,nonce,['docker'],[cid])


class Producer(unittest.TestCase):
    """Real strict source reads; no configured engine or factory acceptance."""
    def setUp(self):
        import tempfile
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700);self.refs={}
        self.ids={name:letter*64 for name,letter in zip(('native','worker','reader'),'abc')}
        self.images={name:'sha256:'+letter*64 for name,letter in zip(('native','worker','reader'),'def')}
        self.ready=self.put('readiness.py',b'print("fixed readiness")\n')
        self.request=self.put('request.json',m.encode(dict(nonce='8'*32)))
        self.parity=self.put('parity.py',b'print("fixed parity")\n')
        cohort=dict(version=1,kind='approved-disposable-nfs-current-source-cohort',
                    images=dict(self.images,selected=self.images['native']),
                    sources=dict(readiness=self.two(self.ready),readiness_input=self.two(self.request),parity=self.two(self.parity)))
        self.cohort=self.put('cohort.json',m.encode(cohort))
        active=dict(version=1,kind='approved-active-nfs-owned-lifecycle',source_cohort=self.two(self.cohort),
                    parent_admission=dict(path='/fixture/G/.comic-nfs-private-'+'1'*32),
                    probe_plan=dict(fixture_parent='/fixture/G/.comic-nfs-private-'+'1'*32,library_root='/fixture/G/L'))
        self.active=self.put('active.json',m.encode(active))
        self.roles=self.put('roles.json',m.encode(dict(nonce='9'*64,observed=1,native_process={},roles={name:dict(id=self.ids[name],image=self.images[name],profile=dict(Id=self.ids[name],Image=self.images[name]),epoch={})for name in self.ids})))
    def put(self,name,raw):
        import os
        path=self.root/name;path.write_bytes(raw);path.chmod(0o600);z=os.lstat(path)
        ref=dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),signature9=[z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink])
        self.refs[str(path)]=ref;return ref
    def two(self,ref):return {key:ref[key]for key in ('path','sha256')}
    def build(self):return m.build_intents(self.active,self.roles,self.refs)
    def test_produces_only_fixed_original_calls_and_exact_stdin(self):
        document=self.build();c=m.ExactCalls(document,'9'*64,['pkexec','/usr/bin/docker','--host','unix:///run/docker.sock'],self.ids.values())
        for row in document['calls']:
            argv=row['argv'];self.assertNotIn('create',argv);self.assertNotIn('start',argv)
            self.assertLessEqual(row['uses'],1024)
        ready=next(r for r in document['calls']if '-c'in r['argv'])
        self.assertEqual(ready['argv'][-1],self.ready_raw())
        self.assertEqual(ready['input_sha256'],self.request['sha256'])
        parity=next(r for r in document['calls']if r['input_sha256']==self.parity['sha256'])
        self.assertEqual(parity['uses'],5)  # four outer parity reads plus inner preflight
        c.approve(ready['argv'],Path(self.request['path']).read_bytes(),900)
        with self.assertRaises(m.Held):c.approve(ready['argv'],b'changed',900)
        self.assertEqual({r['argv'][3]for r in document['calls']if r['argv'][:2]==['findmnt','--json']},{'/fixture/G/L','/fixture/G','/fixture/G/.comic-nfs-private-'+'1'*32})
    def ready_raw(self):return Path(self.ready['path']).read_text()
    def test_changed_or_missing_original_extra_source_and_foreign_role_refuse(self):
        for change in ('bytes','missing','extra','role'):
            with self.subTest(change=change):
                self.setUp()
                if change=='bytes':Path(self.ready['path']).write_bytes(b'changed')
                elif change=='missing':self.refs.pop(self.parity['path'])
                elif change=='extra':self.put('extra.py',b'not a scoped input')
                else:
                    value=__import__('json').loads(Path(self.roles['path']).read_bytes());value['roles']['native']['id']=self.ids['worker']
                    self.roles=self.put('roles.json',m.encode(value))
                with self.assertRaises((m.Held,ValueError)):self.build()
    def test_no_birth_permission_and_finite_consumption(self):
        document=self.build();c=m.ExactCalls(document,'9'*64,['pkexec','/usr/bin/docker','--host','unix:///run/docker.sock'],self.ids.values())
        row=next(r for r in document['calls']if r['argv'][:2]==['findmnt','--json'] and r['argv'][3].endswith('/L'))
        for _ in range(row['uses']):c.approve(row['argv'],None,30)
        with self.assertRaisesRegex(m.Held,'intent-limit'):c.approve(row['argv'],None,30)

    def test_actual_fresh_native_uses_generated_argv_and_independent_request_nonce(self):
        from unittest.mock import patch
        import comic_reader_lifecycle_parent as parent
        spec=importlib.util.spec_from_file_location('active_intent_fixture',Path(__file__).with_name('comic_negative_nfs_active_parent.py'))
        active=importlib.util.module_from_spec(spec);spec.loader.exec_module(active)
        document=self.build();contract=m.ExactCalls(document,'9'*64,parent.DOCKER,self.ids.values());calls=[]
        def call(argv,data):
            contract.approve(argv,data,900);calls.append(argv)
            return m.encode(dict(version=1,nonce='8'*32,source_sha256=self.ready['sha256'],
                                 process=dict(pid=1,start_ticks=1,argv=['original']),
                                 publication={},config=dict(path='/config/config.ini',sha256='7'*64,signature9=[1]*9)))
        with patch.multiple(active,READY=Path(self.ready['path']),READY_SHA=self.ready['sha256'],
                            READY_INPUT=Path(self.request['path']),READY_INPUT_SHA=self.request['sha256']):
            result=active.fresh_native(call,self.ids['native'])
        self.assertEqual(len(calls),1);self.assertEqual(result['nonce'],'8'*32)

    def test_source_change_after_read_refuses_final_custody(self):
        from unittest.mock import patch
        import comic_reader_lifecycle_parent as parent
        original=parent.read;changed=[]
        def read(ref,private=True):
            raw=original(ref,private=private)
            if ref==self.parity and not changed:
                changed.append(True);Path(self.ready['path']).write_bytes(b'changed after first read')
            return raw
        with patch.object(parent,'read',side_effect=read):
            with self.assertRaises(ValueError):self.build()
        self.assertEqual(changed,[True])

if __name__=='__main__':unittest.main()
