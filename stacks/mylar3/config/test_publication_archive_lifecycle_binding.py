"""Actual custody/OS pipes and preparation; parent/scope origins explicitly doubled."""
import copy,hashlib,sys,types,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import test_publication_archive_adoption as archive
import test_publication_reader_lifecycle as base
m=base.m;o=archive.o
class Tests(unittest.TestCase):
 write=base.Tests.write
 pairs=base.Tests.pairs
 def setUp(self):
  self.archive=archive.native.Controls('runTest');self.archive.setUp();self.addCleanup(self.archive.doCleanups)
  self.hold=self.archive.writer.hold();self.hold.__enter__();self.addCleanup(self.hold.__exit__,None,None,None)
  self.preparation=self.archive.prepare();base.Tests.setUp(self)
  self.owner=self.archive.owner;self.operation_id=self.archive.operation_id;self.stage=self.preparation._operation;self.metadata=self.stage/'preparation.json'
  self.phase='verify-terminal';self.record={'version':1,'kind':'archive-one-original-custody','owner':self.owner,'operation_id':self.operation_id,'baseline':{'fixture_only':True},'reader':{'fixture_only':True},'preparation':copy.deepcopy(self.preparation._files[self.metadata]),'preparation_directory9':list(self.preparation._directory),'mutation_authority':False,'publication_acceptance':False}
  self.record['preparation']={k:self.record['preparation'][k] for k in ('path','sha256','signature9')}
  self.proof=self.write('archive-originals.json',m.encoded(self.record));self.sdk=self.write('sdk.json',m.encoded({'publication_reader_lifecycle.py':hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()}))
  self.input=self.write('input.json',m.encoded({'action':'archive-one','owner':self.owner,'operation_id':self.operation_id,'sdk_map':self.sdk}));self.doc['input_sha256']=self.input['sha256'];self.doc['command']=['fixture','--phase',self.phase];self.doc['proofs']['archive_execution_originals']=self.proof;self.doc['proofs']['archive_sdk_map']=self.sdk;self.write('input.lifecycle.json',m.encoded(self.doc))
  case=self
  class Scope:
   def __init__(obj,custody):obj._custody=custody;obj.callback=None
   def revalidate(obj):
    obj._custody.revalidate_stopped()
    if obj.callback:obj.callback(obj)
   def controller_writer(obj):return case.archive.controller,case.archive.writer
  self.Scope=Scope;self.components=patch.object(m,'_archive_components',return_value=(types.SimpleNamespace(NativeConfiguredScope=Scope),o));self.components.start();self.addCleanup(self.components.stop)
 def make(self):return m.StoppedReaderCustody(m._KEY,self.input['path'],self.input['sha256'],self.nonce,self.parent['sha256'],self.doc['command'],self.channel)
 def bind(self,c=None):
  c=c or self.make();scope=self.Scope(c);return m.bind_archive_preparation(c,scope,self.owner,self.operation_id)
 def test_exact_originals_added_same_custody_channel_deadline(self):
  c=self.make();old=(c.channel,c.channel_seal,c.deadline,c.proofs.copy(),c.reader.copy());result=self.bind(c);self.assertIs(result,c);self.assertEqual((c.channel,c.channel_seal,c.deadline,c.proofs,c.reader),old)
  files,_,_=c.vectors();self.assertEqual(files[self.stage],self.record['preparation_directory9']);self.assertEqual(files[self.metadata],self.record['preparation']['signature9'])
 def test_originals_survive_ordinary_subprocess(self):
  import subprocess,json
  program='import os,sys,json;print(json.dumps([[x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_mode,x.st_uid,x.st_gid,x.st_nlink] for x in [os.lstat(sys.argv[1]),os.lstat(sys.argv[2])]]))'
  result=subprocess.run([sys.executable,'-I','-B','-c',program,str(self.metadata),str(self.stage)],capture_output=True,text=True,check=True)
  self.assertEqual(json.loads(result.stdout),[self.record['preparation']['signature9'],self.record['preparation_directory9']]);self.bind()
 def test_no_original_proof_held(self):
  self.doc['proofs'].pop('archive_execution_originals');self.write('input.lifecycle.json',m.encoded(self.doc))
  with self.assertRaises(m.Held):self.bind()
 def test_same_byte_metadata_replacement_held(self):
  replacement=self.metadata.with_name('replacement');replacement.write_bytes(self.metadata.read_bytes());replacement.chmod(0o600);replacement.replace(self.metadata)
  with self.assertRaises(m.Held):self.bind()
 def test_directory_incarnation_held(self):
  import os
  z=self.stage.stat();os.utime(self.stage,ns=(z.st_atime_ns,z.st_mtime_ns+1_000_000))
  with self.assertRaises(m.Held):self.bind()
 def test_owner_mismatch_held(self):
  with self.assertRaises(m.Held):m.bind_archive_preparation(self.make(),self.Scope(self.make()),dict(self.owner,issueid='999'),self.operation_id)
 def test_foreign_scope_custody_held(self):
  c=self.make()
  with self.assertRaises(m.Held):m.bind_archive_preparation(c,self.Scope(self.make()),self.owner,self.operation_id)
 def test_one_use_held(self):
  c=self.bind()
  with self.assertRaises(m.Held):self.bind(c)
 def test_late_scope_metadata_mode_held_invalidates_custody(self):
  c=self.make();scope=self.Scope(c);fired=[]
  def changed(obj):
   if self.stage in obj._custody.files and not fired:self.metadata.chmod(0o640);fired.append(True)
  scope.callback=changed
  with self.assertRaises(m.Held):m.bind_archive_preparation(c,scope,self.owner,self.operation_id)
  self.assertTrue(fired)
  with self.assertRaises(m.Held):c.revalidate_stopped()
 def test_original_directory_boolean_alias_held(self):
  self.record['preparation_directory9'][-1]=True;self.proof=self.write('archive-originals.json',m.encoded(self.record));self.doc['proofs']['archive_execution_originals']=self.proof;self.doc['proofs']['archive_sdk_map']=self.sdk;self.write('input.lifecycle.json',m.encoded(self.doc))
  with self.assertRaises(m.Held):self.bind()
 def test_parent_record_unknown_fields_held(self):
  self.record['grant']=True;self.proof=self.write('archive-originals.json',m.encoded(self.record));self.doc['proofs']['archive_execution_originals']=self.proof;self.doc['proofs']['archive_sdk_map']=self.sdk;self.write('input.lifecycle.json',m.encoded(self.doc))
  with self.assertRaises(m.Held):self.bind()
 def test_fresh_json_cannot_replace_missing_original_directory(self):
  self.record.pop('preparation_directory9');self.proof=self.write('archive-originals.json',m.encoded(self.record));self.doc['proofs']['archive_execution_originals']=self.proof;self.doc['proofs']['archive_sdk_map']=self.sdk;self.write('input.lifecycle.json',m.encoded(self.doc))
  with self.assertRaises(m.Held):self.bind()
 def test_existing_execute_uses_distinct_original_preparation_proof(self):
  self.record.pop('baseline');self.record.pop('reader');self.record['kind']='archive-one-original-preparation';self.proof=self.write('archive-originals.json',m.encoded(self.record));self.doc['proofs'].pop('archive_execution_originals');self.doc['proofs']['archive_preparation_originals']=self.proof;self.doc['command']=['fixture','--phase','execute'];self.write('input.lifecycle.json',m.encoded(self.doc));self.bind()
 def test_other_action_cannot_bind(self):
  self.input=self.write('input.json',m.encoded({'action':'negative-five','owner':self.owner,'operation_id':self.operation_id,'sdk_map':self.sdk}));self.doc['input_sha256']=self.input['sha256'];self.write('input.lifecycle.json',m.encoded(self.doc))
  with self.assertRaises(m.Held):self.bind()
if __name__=='__main__':unittest.main()
