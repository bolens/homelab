"""Actual child pipes + original real host helper Writer process, not NFS positive."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('real_host_fixture',ROOT/'test_host_lease.py');t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
class ChildFactoryInterface(t.RealLease):
    def test_real_child_factory_host_lease_initialize_pulse_release(self):
        c=self.launch();output=Path(self.tmp.name)/'active-output'
        p=subprocess.Popen([sys.executable,'-I','-B',str(ROOT/'lease_interface_child_fixture.py'),str(output)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.processes.append(p);seq=0;seen=[]
        while True:
            raw=p.stdout.readline(65537);self.assertTrue(raw);self.assertLessEqual(len(raw),65536);frame=json.loads(raw)
            self.assertEqual(frame['nonce'],'b'*64);seq+=1;self.assertEqual(frame['sequence'],seq)
            if frame['type']=='nfs-done':
                self.assertEqual(frame['payload'],{'uid':1000,'released':True});break
            self.assertEqual(frame['type'],'nfs-lease');payload=frame['payload'];seen.append(payload['operation'])
            if payload['operation']=='initialize':
                empty=payload['empty'];self.assertEqual(empty['path'],str(output/'lease-empty-config'))
                self.assertEqual(empty['signature9'],list(t.m.nine(os.lstat(empty['path']))));self.assertEqual(os.listdir(empty['path']),[])
                result=c.pulse() # Host real helper already initialized for this fixture.
            elif payload['operation']=='pulse':result=c.pulse()
            else:
                self.assertEqual(payload['operation'],'release');self.assertEqual(payload['absent'],[str(output/'owned-parent'/'owned-fixture'),str(output/'owned-parent')]);result=c.release(payload['absent'])
            response=dict(type='nfs-host',nonce='b'*64,sequence=seq,payload=result)
            p.stdin.write(json.dumps(response).encode()+b'\n');p.stdin.flush()
        self.assertEqual(p.wait(timeout=10),0);self.assertEqual(seen,['initialize','pulse','pulse','release']);self.assertTrue(c.released)
        self.assertEqual(os.listdir(output),['lease-empty-config'])

if __name__=='__main__':unittest.main()
