"""Real pure ZIP/FD failure controls; these do not establish installed custody."""
from contextlib import closing
import copy
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import stat
import sqlite3
import sys
import types
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile
HERE=Path(__file__).resolve().parent
CONFIG=HERE.parent
sys.path.insert(0,str(CONFIG));sys.path.insert(0,str(CONFIG/'reader_recovery'))
spec=importlib.util.spec_from_file_location('transition_action',HERE/'comic_archive_repair_action.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
import publication_guard as guard
import publication_archive_owned as core
import publication_archive_layout as layout
import publication_archive_repair as repair
import publication_archive_derivative as derivative
import genuine_archive_fixture as fixture
MODULES=dict(publication_guard=guard,publication_archive_owned=core,publication_archive_layout=layout,publication_archive_repair=repair,publication_archive_derivative=derivative)

class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.source=self.root/'target.cbz';self.raw=fixture.archive(identity=('Bootstrap Target',2,2024));self.source.write_bytes(self.raw);self.source.chmod(0o644)
  self.stage=self.root/'fixture-transition';self.deadline=time.monotonic()+20;self.fact=core.fact(self.source,a.FIXTURE_LIMIT,self.deadline)
  self.candidate,self.evidence=a.fixture_inverse(self.raw,MODULES,self.deadline)
  control=self.root/'control.json';control.write_bytes(b'{}');control.chmod(0o600);self.control=core.fact(control,a.FIXTURE_LIMIT,self.deadline)
  self.calls=[]
 def guard(self,phase):self.calls.append(phase)
 def apply(self,guard=None):
  return a._fixture_replace(self.source,self.raw,self.candidate,self.fact,self.stage,core,guard or self.guard,dict(deadline_monotonic=self.deadline,kind='fixture-unit-evidence-only'),MODULES)
 def test_exact_real_algorithms_roundtrip(self):
  self.assertEqual(repair.classify(self.candidate,guard,self.deadline)['status'],'repair-candidate')
  copyfile=self.root/'copy.cbz';copyfile.write_bytes(self.candidate);copyfile.chmod(0o600)
  evidence=a.fixture_roundtrip(self.raw,self.candidate,MODULES,self.deadline,core.fact(copyfile,a.FIXTURE_LIMIT,self.deadline))
  self.assertTrue(evidence['roundtrip_verified']);self.assertEqual(evidence['reconstructed_sha256'],hashlib.sha256(self.raw).hexdigest())
 def test_all_file_payloads_xml_pages_and_comments_exact(self):
  with zipfile.ZipFile(io.BytesIO(self.raw)) as original,zipfile.ZipFile(io.BytesIO(self.candidate)) as candidate:
   for left,right in zip(original.infolist(),candidate.infolist()):
    self.assertEqual(original.read(left),candidate.read(right));self.assertEqual(left.comment,right.comment);self.assertEqual(left.extra,right.extra);self.assertEqual(left.CRC,right.CRC)
  self.assertEqual(self.evidence['inventory']['pages'],['Pages/page01.png','Pages/page02.png','Pages/page03.png']);self.assertIn('ComicInfo.xml',self.evidence['root_metadata_sha256'])
 def test_exact_owned_write_retains_genesis_and_candidate(self):
  outcome=self.apply();outcome.close();self.assertEqual(self.source.read_bytes(),self.candidate)
  self.assertEqual((self.stage/'genesis.cbz').read_bytes(),self.raw);self.assertEqual((self.stage/'candidate.cbz').read_bytes(),self.candidate)
  self.assertEqual(self.calls,['candidate-durable','before-write','after-write']);self.assertEqual(a.nine(self.source.stat())[:2],self.fact['signature9'][:2]);self.assertEqual(self.source.stat().st_mtime_ns,self.fact['signature9'][3])
  self.assertFalse(a.decode((self.stage/'successor.json').read_bytes())['reset_authority'])
  self.assertEqual(len(outcome.vectors()['files']),5)
 def test_600_original_unchanged_permission(self):
  self.source.chmod(0o600);self.fact=core.fact(self.source,a.FIXTURE_LIMIT,self.deadline);self.apply();self.assertEqual(stat.S_IMODE(self.source.stat().st_mode),0o600)
 def test_unsafe_modes_refused_before_mutation(self):
  for mode in (0o666,0o664,0o755):
   with self.subTest(mode=mode):
    self.source.chmod(mode);self.fact=core.fact(self.source,a.FIXTURE_LIMIT,self.deadline)
    with self.assertRaisesRegex(a.Held,'fixture-original-write-FD'):self.apply()
    self.assertEqual(self.source.read_bytes(),self.raw)
    self.stage=self.root/('fixture-transition-'+str(mode))
 def test_missing_directory_marker_refused(self):
  stream=io.BytesIO()
  with zipfile.ZipFile(stream,'w') as z:z.writestr('page.png',fixture.png(1,2,3))
  with self.assertRaisesRegex(a.Held,'fixture-exact-empty-Pages-marker'):a.fixture_inverse(stream.getvalue(),MODULES,self.deadline)
 def test_malformed_input_is_not_adopted(self):
  with self.assertRaisesRegex(a.Held,'fixture-valid-genesis-only'):a.fixture_inverse(self.candidate,MODULES,self.deadline)
 def test_crc_corruption_refused(self):
  bad=self.raw.replace(b'<ComicInfo>',b'<ComicInfX>',1)
  with self.assertRaisesRegex(a.Held,'fixture-valid-genesis-only'):a.fixture_inverse(bad,MODULES,self.deadline)
 def test_deadline_refused(self):
  with self.assertRaisesRegex(a.Held,'fixture-bounded-genesis'):a.fixture_inverse(self.raw,MODULES,time.monotonic()-1)
 def test_preexisting_stage_no_replay(self):
  self.stage.mkdir()
  with self.assertRaisesRegex(a.Held,'fixture-no-replay'):self.apply()
  self.assertEqual(self.source.read_bytes(),self.raw)
 def test_changed_candidate_copy_refused(self):
  target=self.root/'copy.cbz';target.write_bytes(self.candidate);ref=core.fact(target,a.FIXTURE_LIMIT,self.deadline);target.write_bytes(self.candidate+b'x')
  with self.assertRaises(a.Held):a.fixture_roundtrip(self.raw,self.candidate,MODULES,self.deadline,ref)
 def test_foreign_replacement_in_callback_preserved_before_write(self):
  def replace(phase):
   if phase=='before-write':self.source.unlink();self.source.write_bytes(b'foreign')
  with patch.object(a.os,'pwrite',side_effect=AssertionError('must not write foreign')):
   with self.assertRaisesRegex(a.Held,'fixture-source-final-CAS'):self.apply(replace)
  self.assertEqual(self.source.read_bytes(),b'foreign');self.assertEqual((self.stage/'genesis.cbz').read_bytes(),self.raw)
 def test_hardlink_refused(self):
  os.link(self.source,self.root/'alias');self.fact=dict(self.fact,signature9=a.nine(self.source.stat()))
  with self.assertRaisesRegex(a.Held,'fixture-original-write-FD'):self.apply()
  self.assertEqual(self.source.read_bytes(),self.raw)
 def test_each_owning_callback_failure_holds_without_reset(self):
  for index,phase in enumerate(('candidate-durable','before-write','after-write')):
   with self.subTest(phase=phase):
    self.stage=self.root/('stage-'+str(index));self.source.write_bytes(self.raw);self.fact=core.fact(self.source,a.FIXTURE_LIMIT,self.deadline)
    def fail(actual):
     if actual==phase:raise ValueError('fixture-injected-boundary')
    with self.assertRaisesRegex(ValueError,'fixture-injected-boundary'):self.apply(fail)
    self.assertEqual(self.source.read_bytes(),self.candidate if phase=='after-write' else self.raw)
    self.assertEqual((self.stage/'genesis.cbz').read_bytes(),self.raw)
 def test_partial_write_preserves_independent_copies_no_reset(self):
  original=os.pwrite;calls=[]
  def broken(fd,data,offset):
   calls.append(offset)
   if len(calls)==1:return original(fd,data[:40],offset)
   raise OSError('fixture-injected-write')
  with patch.object(a.os,'pwrite',broken):
   with self.assertRaisesRegex(OSError,'fixture-injected-write'):self.apply()
  self.assertNotEqual(self.source.read_bytes(),self.raw);self.assertEqual((self.stage/'genesis.cbz').read_bytes(),self.raw);self.assertEqual((self.stage/'candidate.cbz').read_bytes(),self.candidate);self.assertFalse((self.stage/'successor.json').exists())
 def test_late_retained_copy_tamper_refused(self):
  outcome=self.apply();(self.stage/'genesis.cbz').write_bytes(b'foreign')
  with self.assertRaises(a.Held):outcome.close()
 def test_every_fsync_boundary_refuses_without_auto_reset(self):
  real=os.fsync;calls=[]
  def count(fd):calls.append(fd);return real(fd)
  with patch.object(a.os,'fsync',count):self.apply()
  total=len(calls);self.assertGreater(total,8)
  for fault in range(1,total+1):
   with self.subTest(boundary=fault):
    self.stage=self.root/('fsync-'+str(fault));self.source.write_bytes(self.raw);self.fact=core.fact(self.source,a.FIXTURE_LIMIT,self.deadline);seen=[]
    def fail(fd):
     seen.append(fd)
     if len(seen)==fault:raise OSError('fixture-fsync')
     return real(fd)
    with patch.object(a.os,'fsync',fail):
     with self.assertRaisesRegex(OSError,'fixture-fsync'):self.apply()
    if self.source.read_bytes()!=self.raw:
     self.assertEqual((self.stage/'genesis.cbz').read_bytes(),self.raw);self.assertEqual((self.stage/'candidate.cbz').read_bytes(),self.candidate)
 def test_arbitrary_factories_refused(self):
  with self.assertRaises(Exception):a.fixture_transition({'version':4,'terminal_mode':'same-child-v1'},MODULES,object(),object(),object(),object(),{})
  self.assertEqual(self.source.read_bytes(),self.raw)
 def test_request_v1_v2_preserved_and_v3_strict(self):
  owner=dict(table='issues',issueid='1',parentcomicid='2',releasecomicid='2')
  for version in (1,2):
   request=dict(version=version,owner=owner,operation_id='a'*64)
   if version==2:request['terminal']='forward'
   self.assertEqual(a.owner_request(request),request)
  value=dict(version=1,kind='disposable-stopped-directory-marker-v1',nonce='a'*64,bootstrap=self.control,catalog=self.control,genesis=self.fact,native_id='b'*64,reader_id='c'*64,worker_id='d'*64)
  request=dict(version=3,owner=owner,operation_id='a'*64,terminal='rollback',fixture_transition=value);self.assertEqual(a.owner_request(request),request)
  for key in value:
   bad=copy.deepcopy(request);del bad['fixture_transition'][key]
   with self.assertRaises(a.Held):a.owner_request(bad)
 def test_retained_genesis_callback_tamper_refused_before_write(self):
  def corrupt(phase):
   if phase=='before-write':(self.stage/'genesis.cbz').write_bytes(b'changed')
  with patch.object(a.os,'pwrite',side_effect=AssertionError('must retain genesis')):
   with self.assertRaises(a.Held):self.apply(corrupt)
  self.assertEqual(self.source.read_bytes(),self.raw)
 def test_disposable_profile_purpose_nonce_and_cids_exact(self):
  value=dict(nonce='a'*64,native_id='b'*64,reader_id='c'*64,worker_id='d'*64)
  rows=tuple(dict(Id=value[key],Config=dict(Labels={'com.homelab.archive.bootstrap':value['nonce'],'com.homelab.archive.purpose':'genuine-archive-fixture'})) for key in ('native_id','reader_id','worker_id'))
  a.fixture_roles(value,rows)
  for index in range(3):
   for field in ('Id','nonce','purpose'):
    bad=copy.deepcopy(rows)
    if field=='Id':bad[index]['Id']='f'*64
    else:bad[index]['Config']['Labels']['com.homelab.archive.'+('bootstrap' if field=='nonce' else 'purpose')]='foreign'
    with self.assertRaisesRegex(a.Held,'fixture-original-disposable-roles'):a.fixture_roles(value,bad)
 def test_private_DATA_stage_mode_refused(self):
  public=self.root/'public';public.mkdir(mode=0o755);self.stage=public/'stage'
  with self.assertRaisesRegex(a.Held,'fixture-private-DATA-stage'):self.apply()
  self.assertEqual(self.source.read_bytes(),self.raw)
 def test_missing_writer_session_refuses_before_catalog_or_stage(self):
  scope=types.SimpleNamespace(_writer_proof=lambda:(_ for _ in ()).throw(a.Held('fixture-test-writer-not-held')))
  controller=object();writer=object()
  # Only the outer owning-type gate is projected to reach this refusal. This
  # fixture cannot create a real custody or return a genuine successor.
  with patch.object(a,'exact_pair',return_value=(controller,writer)),patch.object(core,'catalog',side_effect=AssertionError('must not query')):
   with self.assertRaisesRegex(a.Held,'fixture-test-writer-not-held'):
    a.fixture_transition(dict(version=4,terminal_mode='same-child-v1'),MODULES,object(),scope,controller,writer,{})
  self.assertFalse(self.stage.exists());self.assertEqual(self.source.read_bytes(),self.raw)
 def test_reader_stop_refusal_before_catalog_or_stage(self):
  value=dict(version=1,kind='disposable-stopped-directory-marker-v1',nonce='a'*64,bootstrap=self.control,catalog=self.control,genesis=self.fact,native_id='b'*64,reader_id='c'*64,worker_id='d'*64)
  rows=tuple(dict(Id=value[key],Config=dict(Labels={'com.homelab.archive.bootstrap':value['nonce'],'com.homelab.archive.purpose':'genuine-archive-fixture'})) for key in ('native_id','reader_id','worker_id'))
  scope=types.SimpleNamespace(_writer_proof=lambda:None,_native=dict(inspect=rows[0]),_worker=dict(inspect=rows[2]),revalidate=lambda:None)
  custody=types.SimpleNamespace(reader=dict(runtime=rows[1]),deadline=self.deadline,revalidate_stopped=lambda:(_ for _ in ()).throw(a.Held('fixture-test-reader-running')))
  controller=object();writer=object()
  with patch.object(a,'exact_pair',return_value=(controller,writer)),patch.object(core,'sdk',return_value=()),patch.object(core,'writer_pair'),patch.object(core,'catalog',side_effect=AssertionError('must not query')):
   with self.assertRaisesRegex(a.Held,'fixture-test-reader-running'):
    a.fixture_transition(dict(version=4,terminal_mode='same-child-v1'),MODULES,custody,scope,controller,writer,dict(fixture_transition=value))
  self.assertFalse(self.stage.exists());self.assertEqual(self.source.read_bytes(),self.raw)
 def test_geometry_refuses_outside_and_overlapping_roots(self):
  data=self.root/'data';library=self.root/'L';controller=types.SimpleNamespace(root=data,roots=[library])
  self.assertEqual(a.fixture_stage(controller,library/'owner.cbz','a'*64),data/('fixture-transition-'+'a'*64))
  for target in (library,self.root/'foreign.cbz'):
   with self.assertRaisesRegex(a.Held,'fixture-original-library-target'):a.fixture_stage(controller,target,'a'*64)
  for root in (library,library/'nested',self.root):
   controller.root=root
   with self.assertRaisesRegex(a.Held,'fixture-stage-outside-library'):a.fixture_stage(controller,library/'owner.cbz','a'*64)
 def test_actual_SQLite_sentinel_and_unrelated_archive_unchanged(self):
  database=self.root/'sentinel.sqlite'
  with closing(sqlite3.connect(database)) as db,db:
   db.execute('CREATE TABLE owner (id TEXT PRIMARY KEY, value TEXT)');db.executemany('INSERT INTO owner VALUES (?,?)',[('target','owner'),('unrelated','other')])
  unrelated=self.root/'unrelated.cbz';unrelated.write_bytes(fixture.archive(unrelated=True));database_before=database.read_bytes();unrelated_before=unrelated.read_bytes()
  def closure(phase):
   self.assertEqual(database.read_bytes(),database_before);self.assertEqual(unrelated.read_bytes(),unrelated_before)
   with closing(sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True)) as db:self.assertEqual(db.execute('SELECT * FROM owner ORDER BY id').fetchall(),[('target','owner'),('unrelated','other')])
  self.apply(closure);closure('final')
 def test_primary_write_failure_preserved_when_source_close_also_fails(self):
  original_close=os.close;source_id=tuple(self.fact['signature9'][:2]);closed=[]
  def broken_close(fd):
   z=os.fstat(fd);is_source=(z.st_dev,z.st_ino)==source_id
   original_close(fd)
   if is_source:closed.append(fd);raise OSError('fixture-secondary-close')
  with patch.object(a.os,'pwrite',side_effect=OSError('fixture-primary-write')),patch.object(a.os,'close',broken_close):
   with self.assertRaisesRegex(OSError,'fixture-primary-write'):self.apply()
  self.assertEqual(len(closed),1)
 def test_forward_genesis_and_rollback_preimage_are_distinct(self):
  self.apply();preimage=self.source.read_bytes();plan=repair.classify(preimage,guard,self.deadline);fact=core.fact(self.source,a.FIXTURE_LIMIT,self.deadline)
  witness=core.witness(preimage,fact,plan,(None,None,guard,None,None,derivative,layout),self.deadline)
  forward,evidence=repair.dispatch(preimage,plan,witness,guard,self.deadline)
  self.assertEqual(forward,self.raw);self.assertEqual(preimage,self.candidate);self.assertNotEqual(preimage,self.raw)
  # This proves the actual normal derivative and its rollback preimage, not
  # installed adoption/reversal or permission to reset the fixture afterward.
  self.assertFalse(evidence['publication_acceptance'])
 def originals(self):
  owner=dict(table='issues',issueid='1',parentcomicid='2',releasecomicid='2');other=self.root/'other.cbz';other.write_bytes(fixture.archive(unrelated=True));other.chmod(0o600)
  pages=[member['sha256'] for member in self.evidence['inventory']['members'] if member['name'] in self.evidence['inventory']['pages']]
  rows=[dict(self.fact,role='target',owner=owner,pages=pages),dict(core.fact(other,a.FIXTURE_LIMIT,self.deadline),role='unrelated',owner=dict(owner,issueid='3'),pages=['a'*64]*3)]
  catalog=dict(kind='disposable-native-catalog-processing-observation',nonce='a'*64,native_CID='b'*64,native_image='sha256:'+'e'*64,files=rows,native_catalog_processing_observed=True,ordinary_ack_verified=False,birth_verified=False,publication_acceptance=False,mutation_authority=False,automatic_replay=False)
  cr=a.write(self.root/'catalog-original.json',catalog)
  bootstrap=dict(kind='disposable-application-bootstrap-observation',nonce='a'*64,native_catalog_processing=cr,native_catalog_processing_observed=True,ordinary_ack_verified=False,publication_acceptance=False,mutation_authority=False,automatic_replay=False,reader=dict(books=[dict(path=row['path'],hashes=row['pages']) for row in rows]))
  br=a.write(self.root/'bootstrap-original.json',bootstrap)
  value=dict(version=1,kind='disposable-stopped-directory-marker-v1',nonce='a'*64,bootstrap=br,catalog=cr,genesis=self.fact,native_id='b'*64,reader_id='c'*64,worker_id='d'*64)
  request=dict(version=3,owner=owner,operation_id='f'*64,terminal='forward',fixture_transition=value)
  projected={}
  for role,ref in (('bootstrap',br),('catalog',cr)):
   path=self.root/(role+'-projected.json');path.write_bytes(Path(ref['path']).read_bytes());path.chmod(0o600);projected[role]=core.fact(path,a.FIXTURE_LIMIT,self.deadline)
  return request,dict(version=4,fixture_originals=projected),bootstrap,catalog
 def test_projected_copies_join_originals_and_parse_actual_documents(self):
  request,plan,bootstrap,catalog=self.originals();target,other=a.fixture_originals(plan,request)
  self.assertEqual(target['path'],self.source.as_posix());self.assertNotEqual(target['owner'],other['owner'])
  for role in ('bootstrap','catalog'):
   self.assertEqual(plan['fixture_originals'][role]['sha256'],request['fixture_transition'][role]['sha256']);self.assertNotEqual(plan['fixture_originals'][role]['signature9'][:2],request['fixture_transition'][role]['signature9'][:2])
 def test_wrong_bootstrap_original_ref_refused_before_transition(self):
  request,plan,bootstrap,catalog=self.originals();request['fixture_transition']['bootstrap']=self.control
  with self.assertRaisesRegex(a.Held,'fixture-projected-original-source-hash'):a.fixture_originals(plan,request)
  self.assertEqual(self.source.read_bytes(),self.raw);self.assertFalse(self.stage.exists())
 def test_wrong_bootstrap_catalog_and_genesis_paths_refused(self):
  request,plan,bootstrap,catalog=self.originals()
  bad=copy.deepcopy(bootstrap);bad['native_catalog_processing']=self.control
  with self.assertRaisesRegex(a.Held,'fixture-original-bootstrap-join'):a.fixture_documents(request,bad,catalog)
  bad=copy.deepcopy(catalog);bad['native_CID']='0'*64
  with self.assertRaisesRegex(a.Held,'fixture-original-catalog-join'):a.fixture_documents(request,bootstrap,bad)
  bad=copy.deepcopy(request);bad['fixture_transition']['genesis']=dict(self.fact,path=str(self.root/'foreign.cbz'))
  with self.assertRaisesRegex(a.Held,'fixture-genesis-catalog-owner-join'):a.fixture_documents(bad,bootstrap,catalog)
  target=copy.deepcopy(catalog['files'][0]);target['path']=bad['fixture_transition']['genesis']['path']
  with self.assertRaisesRegex(a.Held,'fixture-genesis-actual-source-path'):a.fixture_source(bad,target,self.source)
  self.assertEqual(self.source.read_bytes(),self.raw);self.assertFalse(self.stage.exists())
 def test_original_execution_v1_remains_exact_v2_requires_request3(self):
  request,plan,bootstrap,catalog=self.originals()
  value=dict(version=1,kind='archive-one-original-custody',owner=request['owner'],operation_id=request['operation_id'],baseline=self.control,preparation=self.control,preparation_directory9=a.nine(self.root.stat()),reader={},publication_acceptance=False,mutation_authority=False)
  ordinary=dict(version=2,owner=request['owner'],operation_id=request['operation_id'],terminal='forward')
  self.assertEqual(a.original_execution(value,ordinary),value)
  with self.assertRaisesRegex(a.Held,'repair-original-execute-schema'):a.original_execution(value,request)
  extended=dict(value,version=2,fixture_transition=self.control);self.assertEqual(a.original_execution(extended,request),extended)
  with self.assertRaisesRegex(a.Held,'repair-original-execute-schema'):a.original_execution(extended,ordinary)
 def test_control_join_rejects_request_input_cross_versions(self):
  request,projection_plan,bootstrap,catalog=self.originals()
  for input_version,request_value in ((3,request),(4,dict(version=2,owner=request['owner'],operation_id=request['operation_id'],terminal='forward'))):
   ref=a.write(self.root/('request-'+str(input_version)+'.json'),request_value)
   controls={role:self.control for role in a.ROLES};controls['archive_request']=ref
   custody=types.SimpleNamespace(proofs=controls,backup_manifest=controls['backup_manifest'],backup_acceptance=controls['backup_acceptance'])
   plan=dict(version=input_version,controls=controls,owner=request['owner'],operation_id=request['operation_id'],terminal='forward')
   with self.assertRaisesRegex(a.Held,'repair-fixture-input-request-version'):a.control_join(plan,custody)
 def test_exact_successor_type_cannot_be_restored_from_JSON(self):
  with self.assertRaisesRegex(a.Held,'fixture-owning-successor-only'):a._FixtureSuccessor(None,self.stage,{}, {},{})
  outcome=self.apply();outcome.receipt['sha256']='a'*64
  with self.assertRaisesRegex(a.Held,'fixture-successor-seal'):outcome.close()

if __name__=='__main__':unittest.main()
