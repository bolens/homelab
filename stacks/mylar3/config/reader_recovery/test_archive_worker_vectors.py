"""Detached packet conformance only; no process admission or capability proof."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import comic_archive_worker_vectors as h

class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.worker=Path(__file__).parent/'_archive_worker_fixtures/archive_terminal_observation.py'
  self.owner=dict(table='issues',issueid='12',parentcomicid='11',releasecomicid='11')
  self.paths={r:self.root/(r+'.fixture') for r in ('archive','catalog','authority','marker')}
  for r,p in self.paths.items():p.write_bytes(r.encode())
  def nine(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink)
  def five(s):return (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid)
  self.host=dict(files9=[(str(p),nine(p.stat())) for p in self.paths.values()],nodes5=[(str(self.root),five(self.root.stat()))],claims=[],namespaces=[],absent=[str(p)+s for p in (self.paths['catalog'],self.paths['authority']) for s in ('-wal','-shm','-journal')],hashes=[])
  self.roles={r:dict(path=str(p),signature9=nine(p.stat()),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for r,p in self.paths.items()};self.roles['catalog_native_target']=str(self.paths['archive'])
  self.source_sha=hashlib.sha256(self.worker.read_bytes()).hexdigest()
  self.source=dict(files9=[(str(self.worker),nine(self.worker.stat()))],nodes5=[(str(p),five(p.stat())) for p in self.worker.parents],claims=[],namespaces=[],absent=[],hashes=[(str(self.worker),self.source_sha)])
  self.birth_nodes=[(str(p),five(p.stat())) for p in self.root.parents]
  self.patches=[patch.object(h,'READ_ROOTS',(str(self.root),)),patch.object(h,'SOURCE_ENTRY',str(self.worker))]
  for p in self.patches:p.start();self.addCleanup(p.stop)
 def round(self,**extra):
  empty={k:[] for k in h.KEYS};ref=dict(path='/foreign/report.json',signature9=[1,2,3,4,5,0o100600,1000,1000,1],sha256='c'*64)
  args=dict(nonce='a'*64,operation='b'*64,owner=self.owner,outcome='observed-forward',roles=self.roles,host=self.host,producer=empty,producer_ref=ref,history_ref=ref,mounts=[dict(Type='bind',Source=str(self.root),Destination=str(self.root),RW=True)],source_sha=self.source_sha);args.update(extra);return h.Round(**args)
 def birth(self,round):return dict(protocol=h.PROTOCOL,type='receiver-birth',nonce='a'*64,operation_id='b'*64,sequence=0,source_map_sha256=hashlib.sha256(h.encode(round.sources)).hexdigest(),receiver_only_nodes5=self.birth_nodes,source_originals=self.source,source_originals_sha256=hashlib.sha256(h.encode(self.source)).hexdigest(),rights=dict(h.RIGHTS))
 def hello(self,round):return dict(protocol=h.PROTOCOL,type='hello',nonce='a'*64,operation_id='b'*64,sequence=1,challenge='d'*64,source_map_sha256=hashlib.sha256(h.encode(round.sources)).hexdigest(),local_originals_sha256=round.local_sha,receiver_birth_sha256=round.birth_sha)
 def advance(self):
  r=self.round();r.accept(h.encode(self.birth(r)));r.accept(h.encode(self.hello(r)));return r
 def observed(self,r):
  foreign=dict(producer_originals=h.pack(r.producer),host_projection=h.pack(r.host),producer_ref=r.producer_ref,producer_history_ref=r.history_ref)
  proof=dict(originals_sha256=r.local_sha,catalog_logical_sha256='e'*64,catalog_owner=dict(self.owner,status='Downloaded',native_path=r.roles['catalog_native_target']))
  for role in ('archive','catalog','authority','marker'):proof[role+'_sha256']=r.local['hashes'][r.roles[role]]
  return dict(protocol=h.PROTOCOL,type='observed',nonce='a'*64,operation_id='b'*64,sequence=1,challenge=r.challenge,request_sha256=hashlib.sha256(r.request).hexdigest(),owner=self.owner,outcome='observed-forward',local_proof=proof,foreign_unrestated=foreign,rights=dict(h.RIGHTS),receiver_birth_sha256=r.birth_sha)
 def test_complete_exact_readonly_finite_frames(self):
  r=self.advance();release=h.decode(r.accept(h.encode(self.observed(r))));self.assertIsNone(r.accept(h.encode(dict(release,type='released'))));self.assertEqual(r.step,4)
  with self.assertRaises(h.Held):r.accept(h.encode(dict(release,type='released')))
 def test_bool_sequence_rejected(self):
  r=self.round();b=self.birth(r);b['sequence']=False
  with self.assertRaises(h.Held):r.accept(h.encode(b))
 def test_source_map_widening_rejected(self):
  r=self.round();b=self.birth(r);b['source_originals']['files9'].append(('/other.py',[1]*9))
  with self.assertRaises(h.Held):r.accept(h.encode(b))
 def test_shared_root_birth_rebase_rejected(self):
  r=self.round();b=self.birth(r);b['receiver_only_nodes5'].append((str(self.root),(1,2,0o40700,1000,1000)))
  with self.assertRaises(h.Held):r.accept(h.encode(b))
 def test_hello_birth_nonce_foreign_rejected(self):
  r=self.round();r.accept(h.encode(self.birth(r)));v=self.hello(r);v['nonce']='0'*64
  with self.assertRaises(h.Held):r.accept(h.encode(v))
 def test_receiver_ancestor_conflicting_original_rejected(self):
  host=copy.deepcopy(self.host);host['nodes5'].append(('/tmp',(1,2,0o40755,1000,1000)))
  # This HOST ancestor is foreign above the bind, not receiver-local.
  r=self.round(host=host);r.accept(h.encode(self.birth(r)));self.assertNotEqual(r.local['nodes5']['/tmp'],(1,2,0o40755,1000,1000))
 def test_original_role_full9_mismatch_rejected(self):
  roles=copy.deepcopy(self.roles);roles['archive']['signature9']=list(roles['archive']['signature9']);roles['archive']['signature9'][1]+=1
  with self.assertRaises(h.Held):self.round(roles=roles)
 def test_ambiguous_same_source_mount_rejected(self):
  mounts=[dict(Type='bind',Source=str(self.root),Destination=str(self.root),RW=False),dict(Type='bind',Source=str(self.root),Destination=str(self.root/'alias'),RW=False)]
  with self.assertRaises(h.Held):self.round(mounts=mounts)
 def test_source_overlay_rejected(self):
  with self.assertRaises(h.Held):self.round(mounts=[dict(Type='bind',Source=str(self.root),Destination='/app',RW=False)])
 def test_wrong_annual_owner_rejected(self):
  r=self.advance();v=self.observed(r);v['local_proof']['catalog_owner']['releasecomicid']='13'
  with self.assertRaises(h.Held):r.accept(h.encode(v))
 def test_wrong_catalog_path_rejected(self):
  r=self.advance();v=self.observed(r);v['local_proof']['catalog_owner']['native_path']='/other/book.cbz'
  with self.assertRaises(h.Held):r.accept(h.encode(v))
 def test_factual_hash_drift_rejected(self):
  r=self.advance();v=self.observed(r);v['local_proof']['catalog_sha256']='0'*64
  with self.assertRaises(h.Held):r.accept(h.encode(v))
 def test_foreign_originals_cannot_be_relabelled(self):
  r=self.advance();v=self.observed(r);v['foreign_unrestated']['producer_originals']['nodes5'].append(('/foreign',(1,2,0o40755,1000,1000)))
  with self.assertRaises(h.Held):r.accept(h.encode(v))
 def test_no_right_widening(self):
  r=self.advance();v=self.observed(r);v['rights']['cleanup']=True
  with self.assertRaises(h.Held):r.accept(h.encode(v))
 def test_plain_state_mutation_before_decoder_rejected(self):
  r=self.advance();r.owner['issueid']='99'
  with self.assertRaises(h.Held):r.accept(h.encode(self.observed(r)))
 def test_late_encoder_mutation_rejected(self):
  r=self.round();real=h.encode;raw=real(self.birth(r));fired=[]
  def late(value):
   out=real(value)
   if value.get('type')=='bootstrap':fired.append(True);r.outcome='observed-rollback'
   return out
  with patch.object(h,'encode',late),self.assertRaises(h.Held):r.accept(raw)
  self.assertTrue(fired)

if __name__=='__main__':unittest.main()
