"""Literal filesystem publication projection only; no source event/cap grant."""
import copy
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import comic_retained_standalone_parent as p

class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        owner=dict(table='issues',issueid='12',parentcomicid='34',releasecomicid='34')
        self.request=dict(version=1,kind='standalone-retained-ddl-v1',ddl_id='12',owner=owner,
                          source_sha256='a'*64,target_sha256='b'*64,review_sha256='c'*64)
        self.token=p.digest(dict(ddl_id='12',owner=owner,kind=self.request['kind']))
        self.boot=dict(data_root='/config/mylar',request=self.request,input_sha256='d'*64,
                       source_map_ref={'sha256':'e'*64})
        self.mounts=[dict(Type='bind',Source=str(self.root),Destination='/config/mylar',RW=True)]
        self.carrier=self.root/p.CARRIER_NAME;self.directory=self.carrier/self.token
    def tearDown(self):self.tmp.cleanup()
    def mkdir(self,path):
        path.mkdir(mode=0o700)
        if os.geteuid()==0:os.chown(path,1000,1000)
    def stamp(self,path):return list(p.nine(os.lstat(path)))
    def create(self,existing=False):
        if existing:self.mkdir(self.carrier)
        before=self.stamp(self.carrier) if existing else None
        prelaunch=dict(carrier9=None if before is None else tuple(before),carrier_names=(),token_absent=not self.directory.exists())
        if not existing:self.mkdir(self.carrier)
        self.mkdir(self.directory);carrier_after=self.stamp(self.carrier);directory_before=self.stamp(self.directory)
        body=self.directory/'initialized-body.json';body.write_bytes(p.encode({'all':'original canonical bytes'}));body.chmod(0o600)
        if os.geteuid()==0:os.chown(body,1000,1000)
        publication=dict(carrier='/config/mylar/'+p.CARRIER_NAME,carrier_baseline='existing' if existing else 'absent',
                         carrier_before9=before,carrier_after9=carrier_after,carrier_before_names=[],carrier_after_names=[self.token],
                         directory='/config/mylar/'+p.CARRIER_NAME+'/'+self.token,directory_before9=directory_before,
                         directory_after9=self.stamp(self.directory),before_names=[],after_names=['initialized-body.json'],
                         sql_parents_after_publication=[dict(path=self.boot['data_root'],signature9=self.stamp(self.root),names=sorted(os.listdir(self.root)))])
        ref=dict(path=publication['directory']+'/initialized-body.json',sha256=hashlib.sha256(body.read_bytes()).hexdigest(),signature9=self.stamp(body))
        header=dict(input_sha256='d'*64,source_map_sha256='e'*64,request_sha256=p.digest(self.request),generation='f'*64,
                    phase='initialized',body_ref=ref,publication=publication)
        frame=p.capture_publication_originals(str(self.root),self.token,'initialized')
        return header,frame,prelaunch
    def join(self,header,frame,prelaunch,initial=None):return p.join_publication(header,self.boot,self.mounts,frame,prelaunch,initial)
    def test_exclusive_absent_carrier_and_real_same_bind_projection(self):
        h,f,pr=self.create();result=self.join(h,f,pr)
        self.assertEqual(result['path'],str(self.directory/'initialized-body.json'))
    def test_existing_original_empty_carrier_exact_single_token(self):
        h,f,pr=self.create(True);self.join(h,f,pr)
    def test_present_None_cannot_alias_existing_original(self):
        h,f,pr=self.create();h['publication']['carrier_baseline']='existing'
        with self.assertRaises(ValueError):self.join(h,f,pr)
    def test_original_ref9_must_match_actual_same_bind(self):
        h,f,pr=self.create();h['body_ref']['signature9'][0]+=1
        with self.assertRaises(ValueError):self.join(h,f,pr)
    def test_foreign_namespace_not_hidden_by_header(self):
        h,f,pr=self.create();(self.directory/'foreign').write_text('retain')
        with self.assertRaises(ValueError):self.join(h,f,pr)
    def test_readonly_nonbind_shadow_refuses(self):
        h,f,pr=self.create();self.mounts.append(dict(Type='tmpfs',Source='',Destination='/config/mylar/'+p.CARRIER_NAME,RW=False))
        with self.assertRaises(ValueError):self.join(h,f,pr)
    def test_final_raw_callback_mapping_mutation_refuses(self):
        h,f,pr=self.create();original=p.raw;fired=[]
        def mutation(frame):
            original(frame)
            if not fired:fired.append(True);self.mounts[0]['Source']+='/.'
        with patch.object(p,'raw',mutation),self.assertRaises(ValueError):self.join(h,f,pr)
        self.assertTrue(fired)
    def test_finalized_only_second_artifact_insertion_preserves_first(self):
        h,f,pr=self.create();self.join(h,f,pr);initial=copy.deepcopy(h['publication'])
        old=self.stamp(self.directory);body=self.directory/'observed-body.json';body.write_bytes(p.encode({'all':'complete terminal'}));body.chmod(0o600)
        if os.geteuid()==0:os.chown(body,1000,1000)
        pub=h['publication'];pub.update(carrier_baseline='existing',carrier_before9=pub['carrier_after9'],carrier_before_names=[self.token],
                                      directory_before9=old,directory_after9=self.stamp(self.directory),before_names=['initialized-body.json'],
                                      after_names=['initialized-body.json','observed-body.json'])
        h['phase']='finalized';h['body_ref']=dict(path=pub['directory']+'/observed-body.json',sha256=hashlib.sha256(body.read_bytes()).hexdigest(),signature9=self.stamp(body))
        final=p.capture_publication_originals(str(self.root),self.token,'finalized');self.join(h,final,pr,initial)
        h['publication']['carrier_before9']=h['publication']['carrier_before9'].copy();h['publication']['carrier_before9'][4]+=1
        with self.assertRaises(ValueError):self.join(h,final,pr,initial)



    def wire_process(self,header):
        import subprocess
        packet=p.encode(dict(version=2,protocol=p.PROTOCOL,kind='initialized',nonce='a'*64,challenge='b'*64,sequence=1,payload=header))+b'\n'
        process=subprocess.Popen([sys.executable,'-I','-B','-c',"import os,sys;os.write(1,"+repr(packet)+");sys.stdin.readline()"],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.addCleanup(lambda:process.communicate(timeout=3))
        self.addCleanup(lambda:process.kill() if process.poll() is None else None)
        return process
    def test_real_packet_captures_fixed_body_before_first_decode(self):
        h,f,pr=self.create();process=self.wire_process(h);pipe=p.OriginalPipe.from_process(process,'a'*64,'b'*64)
        value,raw,known=pipe.receive(data_root=self.boot['data_root'],request=self.request,mounts=self.mounts)
        self.assertEqual(value['payload'],h);self.assertEqual(dict(known[0])[str(self.directory/'initialized-body.json')],tuple(h['body_ref']['signature9']))
        self.assertEqual(p.hashlib.sha256(raw).hexdigest(),p.hashlib.sha256(p.encode(value)).hexdigest())
    def test_first_packet_decode_callback_cannot_rebaseline_body(self):
        h,f,pr=self.create();process=self.wire_process(h);pipe=p.OriginalPipe.from_process(process,'a'*64,'b'*64)
        original=p.decode;fired=[]
        def changed(data):
            result=original(data);fired.append(True);os.chmod(self.directory/'initialized-body.json',0o640);return result
        with patch.object(p,'decode',changed),self.assertRaises(ValueError):
            pipe.receive(data_root=self.boot['data_root'],request=self.request,mounts=self.mounts)
        self.assertTrue(fired)
    def test_first_packet_decode_callback_foreign_namespace_refuses(self):
        h,f,pr=self.create();process=self.wire_process(h);pipe=p.OriginalPipe.from_process(process,'a'*64,'b'*64)
        original=p.decode;fired=[]
        def changed(data):
            result=original(data);fired.append(True);(self.directory/'foreign').write_text('retain');return result
        with patch.object(p,'decode',changed),self.assertRaises(ValueError):
            pipe.receive(data_root=self.boot['data_root'],request=self.request,mounts=self.mounts)
        self.assertTrue(fired)

if __name__=='__main__':unittest.main()
