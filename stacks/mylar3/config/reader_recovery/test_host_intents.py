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

if __name__=='__main__':unittest.main()
