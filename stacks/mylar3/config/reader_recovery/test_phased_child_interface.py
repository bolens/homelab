"""Actual child Channel/helper Writer frames; host constructor/NFS remain false."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import json,os,subprocess,unittest
import test_deferred_lease as t
class Phased(t.Deferred):
 def test_original_prepare_acquire_pulse_release_child_frames(self):
  helper=Path(__file__).with_name('comic_negative_nfs_active_lifecycle.py')
  proc=subprocess.Popen([sys.executable,'-I','-B',str(helper),'--lease-child','--writer-source',str(t.t.WRITER),'--writer-sha256',t.t.SHA,'--writer-root',str(self.root),'--token','a'*64,'--lease-seconds','5','--defer-acquire'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);self.processes.append(proc)
  channel=t.t.m.LeaseChannel(proc,'a'*64,self.root,t.t.SHA,10);prepared_ack=channel.receive('prepared');output=Path(self.tmp.name)/'active-output'
  p=subprocess.Popen([sys.executable,'-I','-B',str(Path(__file__).with_name('lease_interface_phased_child_fixture.py')),str(output)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);self.processes.append(p);seen=[];sequence=0
  while True:
   raw=p.stdout.readline(65537);self.assertTrue(raw);self.assertLessEqual(len(raw),65536);frame=json.loads(raw);sequence+=1;self.assertEqual(frame['nonce'],'b'*64);self.assertEqual(frame['sequence'],sequence)
   if frame['type']=='nfs-done':
    self.assertEqual(frame['payload'],{'uid':1000,'released':True});break
   self.assertEqual(frame['type'],'nfs-lease');v=frame['payload'];seen.append(v['operation'])
   if v['operation']=='initialize':
    self.free();self.assertEqual(v['empty']['path'],str(output/'lease-empty-config'));self.assertEqual(os.listdir(v['empty']['path']),[]);result=prepared_ack
   elif v['operation']=='acquire':
    self.command(channel);result=channel.receive('held')
    with self.assertRaises(BlockingIOError):self.free()
   elif v['operation']=='pulse':result=channel.pulse()
   else:
    self.assertEqual(v['operation'],'release');self.assertEqual(v['absent'],[str(output/'owned-parent'/'owned-fixture'),str(output/'owned-parent')]);result=channel.release(v['absent']);self.free()
   p.stdin.write((json.dumps(dict(type='nfs-host',nonce='b'*64,sequence=sequence,payload=result))+'\n').encode());p.stdin.flush()
  self.assertEqual(p.wait(timeout=5),0);self.assertEqual(seen,['initialize','acquire','pulse','pulse','release']);self.assertTrue(channel.released);self.assertEqual(os.listdir(output),['lease-empty-config'])
if __name__=='__main__':unittest.main()
