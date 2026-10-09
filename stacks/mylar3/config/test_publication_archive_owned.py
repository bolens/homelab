"""Disposable genuine public catalog/registry/Writer; stdlib pure ZIP verifier.

SDK import-resolution is substituted for host tests only. These are not actual
installed-image gates, reader/adoption proof, or operational capability tests.
"""
import inspect
import hashlib
import importlib
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import publication_archive_owned as m
import publication_api as api
import media_writer as writers
import publication_guard as g
import test_publication_api as fixture

class Controls(unittest.TestCase):
 call=fixture.NativeProtocolTests.call
 bootstrap=fixture.NativeProtocolTests.bootstrap
 sql=fixture.fixtures.NativeObservationTests.sql
 def setUp(self):
  self.tool=tempfile.TemporaryDirectory();self.addCleanup(self.tool.cleanup)
  tool=Path(self.tool.name);(tool/'lib').mkdir();(tool/'lib/comics.py').write_text('PAGE_EXTENSIONS='+repr(g.PAGE_EXTENSIONS))
  for mod,name,value in ((fixture,'TOOL_ROOT',tool),(g,'TOOL_ROOT',tool)):
   p=patch.object(mod,name,value);p.start();self.addCleanup(p.stop)
  fixture.NativeProtocolTests.setUp(self);self.bootstrap()
  self.modules=[api,writers,g]+[importlib.import_module(n) for n in ('publication_derivative','publication_archive_repair','publication_archive_derivative','publication_archive_layout')]
  p=patch.object(m,'sdk',return_value=self.modules);p.start();self.addCleanup(p.stop)
  self.archive();self.operation_id='1'*64
 def archive(self,ordinary=False,name='Folder',extra=None):
  with zipfile.ZipFile(self.source,'w') as z:
   entry=zipfile.ZipInfo(name+('/' if ordinary else ''));entry.create_system=3;entry.external_attr=((stat.S_IFDIR|0o755)<<16)|0x10
   z.writestr(entry,b'');z.writestr('Folder/page01.jpg',b'page one');z.writestr('ComicInfo.xml',b'<ComicInfo><Title>fixture</Title></ComicInfo>')
   if extra:z.writestr(*extra)
 def prepare(self):return m.prepare_existing(self.controller,self.writer,self.owner,self.operation_id)
 def register_source(self):
  self.archive(ordinary=True)
  def inventory(p,**kw):
   raw=Path(p).read_bytes();inv,_=self.modules[5].independent(raw,g,__import__('time').monotonic()+20)
   return dict(inv,source_signature=m.signature(p),source_sha256=hashlib.sha256(raw).hexdigest())
  with patch.object(g,'inventory',side_effect=inventory):
   prepared=fixture.NativeProtocolTests.prepare(self,census=self.call('status')['census']);self.call('register',token=prepared['token'])
  self.archive()
 def register_two(self):
  self.archive(ordinary=True);other=self.library/'other.cbz';other.write_bytes(self.source.read_bytes())
  self.other_owner=dict(table='issues',issueid='789',parentcomicid='456',releasecomicid='456')
  self.sql('INSERT INTO issues VALUES (?,?,?,?)',('789','456',other.name,'Downloaded'))
  def inventory(p,**kw):
   raw=Path(p).read_bytes();inv,_=self.modules[5].independent(raw,g,__import__('time').monotonic()+20)
   return dict(inv,source_signature=m.signature(p),source_sha256=hashlib.sha256(raw).hexdigest())
  with patch.object(g,'inventory',side_effect=inventory):
   inv=inventory(self.source)
   body={k:inv[k] for k in ('version','members','pages','payload')}
   prepared=self.call('prepare-registration',census=self.call('status')['census'],inventory=body,allowed=[self.owner,self.other_owner],rejected=[dict(table='issues',issueid='999',parentcomicid='888',releasecomicid='888')],created=1,evidence=dict(sha256='d'*64,description='private fixture'))
   self.call('register',token=prepared['token'])
  self.archive();return other,inventory
 def test_current_owner_prepare_retains_original_and_has_no_authority(self):
  before=self.source.read_bytes();sig=m.signature(self.source)
  with self.writer.hold():
   p=self.prepare();b=p.revalidate();self.assertEqual(b['policy']['decision'],'unknown')
   for k in ('executable','native_grant','mutation_authority','adoption_authority','publication_acceptance','reader_preservation_verified'):self.assertIs(b[k],False)
   op=p._operation
   self.assertEqual((op/'original.arc').read_bytes(),before);self.assertEqual((op/'restored-original.arc').read_bytes(),before)
   with zipfile.ZipFile(op/'prepared.cbz') as z:self.assertEqual(z.namelist(),['Folder/','Folder/page01.jpg','ComicInfo.xml']);self.assertEqual(z.read('Folder/page01.jpg'),b'page one')
   with self.assertRaisesRegex(m.Held,'adoption'):p.adopt()
  self.assertEqual(self.source.read_bytes(),before);self.assertEqual(m.signature(self.source),sig)
 def test_binding_copy_does_not_mutate_capability(self):
  with self.writer.hold():
   p=self.prepare();b=p.binding;b['mutation_authority']=True;self.assertIs(p.binding['mutation_authority'],False)
 def test_ordinary_zip_is_not_exception(self):
  self.archive(ordinary=True)
  with self.writer.hold(),self.assertRaisesRegex(m.Held,'supported-defect'):self.prepare()
 def test_crc_failure_not_repair(self):
  self.source.write_bytes(self.source.read_bytes().replace(b'page one',b'bad page'))
  with self.writer.hold(),self.assertRaisesRegex(m.Held,'supported-defect'):self.prepare()
 def test_truncated_source_not_repair(self):
  self.source.write_bytes(self.source.read_bytes()[:-15])
  with self.writer.hold(),self.assertRaisesRegex(m.Held,'supported-defect'):self.prepare()
 def test_unsafe_member_not_repair(self):
  self.archive(extra=('../foreign.jpg',b'bad'))
  with self.writer.hold(),self.assertRaisesRegex(m.Held,'supported-defect'):self.prepare()
 def test_two_spelling_defects_not_repair(self):
  with zipfile.ZipFile(self.source,'a') as z:
   e=zipfile.ZipInfo('Second');e.create_system=3;e.external_attr=((stat.S_IFDIR|0o755)<<16)|0x10;z.writestr(e,b'')
  with self.writer.hold(),self.assertRaisesRegex(m.Held,'supported-defect'):self.prepare()
 def test_no_writer_held(self):
  with self.assertRaisesRegex(m.Held,'held-ordinary'):self.prepare()
 def test_fake_controller_held(self):
  with self.writer.hold(),self.assertRaisesRegex(m.Held,'exact-sdk'):m.prepare_existing(object(),self.writer,self.owner,self.operation_id)
 def test_pending_fence_held(self):
  with self.writer.hold():
   (self.writer.root/'normalizer-v1.pending').write_bytes(b'foreign')
   with self.assertRaisesRegex(m.Held,'pending'):self.prepare()
 def test_catalog_wal_held(self):
  Path(str(self.database)+'-wal').write_bytes(b'foreign')
  with self.writer.hold(),self.assertRaises(Exception):self.prepare()
 def test_unowned_NULL_source_held(self):
  self.sql('UPDATE issues SET Location=NULL')
  with self.writer.hold(),self.assertRaises(Exception):self.prepare()
 def test_wanted_owner_held(self):
  self.sql("UPDATE issues SET Status='Wanted'")
  with self.writer.hold(),self.assertRaises(Exception):self.prepare()
 def test_inactive_duplicate_path_claim_held(self):
  self.sql('INSERT INTO issues VALUES (?,?,?,?)',('777','456',self.source.name,'Wanted'))
  with self.writer.hold(),self.assertRaisesRegex(m.Held,'physical-owner'):self.prepare()
 def test_deleted_annual_shadow_same_issue_held(self):
  self.sql('INSERT INTO annuals VALUES (?,?,?,?,?,?)',('123','456','456','foreign.cbz','Wanted',1))
  with self.writer.hold(),self.assertRaisesRegex(m.Held,'sole-issue'):self.prepare()
 def test_source_hardlink_held(self):
  os.link(self.source,self.library/'alias.cbz')
  with self.writer.hold(),self.assertRaisesRegex(m.Held,'file-bound'):self.prepare()
 def test_source_symlink_held(self):
  retained=self.library/'retained.cbz';self.source.rename(retained);self.source.symlink_to(retained)
  with self.writer.hold(),self.assertRaises(Exception):self.prepare()
 def test_operation_collision_no_overwrite(self):
  op=self.root/('archive-repair-'+self.operation_id);op.mkdir();(op/'foreign').write_bytes(b'keep')
  with self.writer.hold(),self.assertRaisesRegex(m.Held,'private-stage'):self.prepare()
  self.assertEqual((op/'foreign').read_bytes(),b'keep')
 def test_source_replacement_after_prepare_held(self):
  with self.writer.hold():
   p=self.prepare();raw=self.source.read_bytes();self.source.unlink();self.source.write_bytes(raw)
   with self.assertRaises(m.Held):p.revalidate()
 def test_source_mode_after_prepare_held(self):
  with self.writer.hold():
   p=self.prepare();self.source.chmod(0o600)
   with self.assertRaises(m.Held):p.revalidate()
 def test_custody_corruption_held(self):
  with self.writer.hold():
   p=self.prepare();(p._operation/'restored-original.arc').write_bytes(b'foreign')
   with self.assertRaises(m.Held):p.revalidate()
 def test_expired_hold_held(self):
  with self.writer.hold():p=self.prepare()
  with self.assertRaises(m.Held):p.revalidate()
 def test_mutable_private_baseline_reseal_held(self):
  with self.writer.hold():
   p=self.prepare();p._directory=m.signature(self.root)
   with self.assertRaisesRegex(m.Held,'lifetime'):p.revalidate()
 def test_late_writer_callback_creates_wal_held(self):
  with self.writer.hold():
   p=self.prepare();real=m.writer_pair;fired=[]
   def late(*a):
    v=real(*a)
    if not fired:Path(str(self.database)+'-wal').write_bytes(b'late');fired.append(True)
    return v
   with patch.object(m,'writer_pair',side_effect=late),self.assertRaisesRegex(m.Held,'terminal-companion'):p.close_passive()
   self.assertTrue(fired)
 def test_late_writer_callback_adds_operation_child_held(self):
  with self.writer.hold():
   p=self.prepare();real=m.writer_pair
   def late(*a):
    v=real(*a);(p._operation/'foreign').write_bytes(b'late');return v
   with patch.object(m,'writer_pair',side_effect=late),self.assertRaisesRegex(m.Held,'terminal-operation'):p.close_passive()
 def test_late_copy_failure_retains_intent_no_preparation(self):
  with self.writer.hold(),patch.object(m,'preserve',side_effect=m.Held('fixture-copy-failed')),self.assertRaises(m.Held):self.prepare()
  op=self.root/('archive-repair-'+self.operation_id);self.assertTrue((op/'intent.json').is_file());self.assertFalse((op/'preparation.json').exists())
 def test_late_preparation_write_corruption_not_adopted(self):
  real=m.write
  def late(p,raw,*a):
   real(p,raw,*a)
   if p.name=='preparation.json':p.write_bytes(b'{}')
  with self.writer.hold(),patch.object(m,'write',side_effect=late),self.assertRaisesRegex(m.Held,'intended-preparation'):self.prepare()
 def test_late_custody_alias_catalog_claim_held(self):
  self.sql('INSERT INTO issues VALUES (?,?,?,?)',('777','456','late.cbz','Wanted'))
  real=m.preserve;fired=[]
  def late(*a):
   real(*a)
   if not fired:os.symlink(self.source,self.library/'late.cbz');fired.append(True)
  with self.writer.hold(),patch.object(m,'preserve',side_effect=late),self.assertRaises(Exception):self.prepare()
  self.assertTrue(fired)

 def test_registered_allowed_owner_remains_allowed(self):
  self.register_source()
  with self.writer.hold():self.assertEqual(self.prepare().binding['policy']['decision'],'allowed')
 def test_registered_rejected_owner_not_exception(self):
  self.register_source();self.owner=dict(table='issues',issueid='999',parentcomicid='888',releasecomicid='888')
  self.sql('INSERT INTO comics VALUES (?,?,?)',('888',str(self.library),'Active'))
  self.sql('UPDATE issues SET Location=NULL')
  self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',self.source.name,'Downloaded'))
  with self.writer.hold(),self.assertRaisesRegex(m.Held,'rejected-or-unreviewed'):self.prepare()
 def test_late_xattr_change_is_not_adopted(self):
  real=m.preserve;fired=[]
  def late(*a):
   real(*a)
   if not fired:os.setxattr(self.source,'user.fixture',b'foreign');fired.append(True)
  with self.writer.hold(),patch.object(m,'preserve',side_effect=late),self.assertRaises(m.Held):self.prepare()
  self.assertTrue(fired)
 def test_late_stage_read_adds_foreign_child_not_adopted(self):
  real=m.fact;fired=[]
  def late(p,*a):
   v=real(p,*a)
   if Path(p).name=='preparation.json' and not fired:(Path(p).parent/'foreign').write_bytes(b'late');fired.append(True)
   return v
  with self.writer.hold(),patch.object(m,'fact',side_effect=late),self.assertRaises(m.Held):self.prepare()
  self.assertTrue(fired)
 def test_initial_control_hash_external_parent_rebuild_held(self):
  # Rebuild an admitted external ancestor, preserving every original leaf.
  external=self.root/'external';external.mkdir();self.library.rename(external/'library')
  self.library=external/'library';self.source=self.library/self.source.name
  self.controller=api.Controller(self.root,[self.library],tool_root=g.TOOL_ROOT)
  self.sql('UPDATE comics SET ComicLocation=?',(str(self.library),))
  real=m.fact;fired=[]
  def late(p,*a):
   v=real(p,*a)
   if Path(p)==self.controller.database and not fired:
    retained=self.root/'old-external';external.rename(retained);external.mkdir();(retained/'library').rename(external/'library');fired.append(True)
   return v
  with self.writer.hold(),patch.object(m,'fact',side_effect=late),self.assertRaises(m.Held):self.prepare()
  self.assertTrue(fired)
 def test_final_census_callback_ancestor_rebuild_held(self):
  with self.writer.hold():
   p=self.prepare();real=m.writer_pair;fired=[]
   def late(*a):
    v=real(*a)
    if not fired:
     retained=self.root/'old-library';self.library.rename(retained);self.library.mkdir()
     for child in retained.iterdir():child.rename(self.library/child.name)
     fired.append(True)
    return v
   with patch.object(m,'writer_pair',side_effect=late),self.assertRaises(m.Held):p.close_passive()
   self.assertTrue(fired)
 def test_private_state_and_seal_cannot_be_refreshed(self):
  with self.writer.hold():
   p=self.prepare();p._directory=m.signature(self.root);p._seal=p._core()
   with self.assertRaisesRegex(m.Held,'lifetime'):p.close_passive()
 def test_late_final_hash_source_rewrite_held(self):
  with self.writer.hold():
   p=self.prepare();real=m.fact;fired=[]
   def late(path,*a):
    value=real(path,*a)
    if Path(path).name=='preparation.json' and not fired:self.source.write_bytes(b'foreign');fired.append(True)
    return value
   with patch.object(m,'fact',side_effect=late),self.assertRaises(m.Held):p.revalidate()
   self.assertTrue(fired)

 def test_other_matched_owner_uses_ordinary_inventory(self):
  other,inventory=self.register_two()
  with self.writer.hold(),patch.object(g,'inventory',side_effect=inventory) as scanner:
   result=self.prepare();self.assertEqual(result.binding['policy']['decision'],'allowed');self.assertEqual(len(result.binding['policy']['other_observed']),1)
   self.assertTrue(scanner.call_args_list);self.assertTrue(all(Path(c.args[0])==other for c in scanner.call_args_list))
 def test_other_malformed_owner_cannot_borrow_exception(self):
  other,inventory=self.register_two();other.write_bytes(self.source.read_bytes())
  with self.writer.hold(),patch.object(g,'inventory',side_effect=inventory),self.assertRaises(ValueError):self.prepare()
 def test_annual_exact_release_owner_supported(self):
  self.sql('DELETE FROM issues');self.sql('INSERT INTO annuals VALUES (?,?,?,?,?,?)',('123','456','789',self.source.name,'Archived',0))
  self.owner=dict(table='annuals',issueid='123',parentcomicid='456',releasecomicid='789')
  with self.writer.hold():self.assertEqual(self.prepare().binding['owner'],self.owner)
 def test_deleted_annual_owner_held(self):
  self.sql('DELETE FROM issues');self.sql('INSERT INTO annuals VALUES (?,?,?,?,?,?)',('123','456','789',self.source.name,'Archived',1))
  self.owner=dict(table='annuals',issueid='123',parentcomicid='456',releasecomicid='789')
  with self.writer.hold(),self.assertRaises(ValueError):self.prepare()

 def test_transient_parent_alias_cannot_read_foreign_archive(self):
  foreign=self.root/'foreign';foreign.mkdir();other=foreign/self.source.name
  other.write_bytes(self.source.read_bytes().replace(b'page one',b'evil one'))
  original=self.source.read_bytes();real=m.os.open;fired=[]
  def race(path,flags,*args,**kw):
   if path==self.source.name and 'dir_fd' in kw and not fired:
    retained=self.root/'retained-library';self.library.rename(retained);self.library.symlink_to(foreign,target_is_directory=True)
    try:fd=real(path,flags,*args,**kw)
    finally:self.library.unlink();retained.rename(self.library)
    fired.append(True);return fd
   return real(path,flags,*args,**kw)
  with self.writer.hold(),patch.object(m.os,'open',side_effect=race):
   p=self.prepare();self.assertEqual((p._operation/'original.arc').read_bytes(),original)
   self.assertEqual(p.binding['source']['sha256'],hashlib.sha256(original).hexdigest())
  self.assertTrue(fired)
 def test_transient_directory_alias_before_fd_admission_held(self):
  foreign=self.root/'foreign';foreign.mkdir();(foreign/self.source.name).write_bytes(self.source.read_bytes())
  real=m.os.open;fired=[]
  def race(path,flags,*args,**kw):
   if path=='library' and 'dir_fd' in kw and not fired:
    retained=self.root/'retained-library';self.library.rename(retained);self.library.symlink_to(foreign,target_is_directory=True)
    try:return real(path,flags,*args,**kw)
    finally:self.library.unlink();retained.rename(self.library);fired.append(True)
   return real(path,flags,*args,**kw)
  with self.writer.hold(),patch.object(m.os,'open',side_effect=race),self.assertRaises(OSError):self.prepare()
  self.assertTrue(fired)
 def test_leaf_fd_same_path_foreign_inode_held(self):
  real=m.os.open;fired=[];original=self.source.read_bytes()
  def race(path,flags,*args,**kw):
   if path==self.source.name and 'dir_fd' in kw and not fired:
    retained=self.library/'retained';self.source.rename(retained);self.source.write_bytes(original.replace(b'page one',b'evil one'))
    try:fd=real(path,flags,*args,**kw)
    finally:self.source.unlink();retained.rename(self.source);fired.append(True)
    return fd
   return real(path,flags,*args,**kw)
  with self.writer.hold(),patch.object(m.os,'open',side_effect=race),self.assertRaisesRegex(m.Held,'read-fd-CAS'):self.prepare()
  self.assertTrue(fired);self.assertEqual(self.source.read_bytes(),original)
 def test_many_xattr_names_refused_before_values(self):
  with patch.object(m.os,'listxattr',return_value=['user.x'+str(i) for i in range(65)]),patch.object(m.os,'getxattr') as get,self.assertRaisesRegex(m.Held,'xattr-name-bound'):m.attributes(self.source)
  get.assert_not_called()
 def test_incremental_xattr_budget_stops_reads(self):
  with patch.object(m.os,'listxattr',return_value=['user.x'+str(i) for i in range(20)]),patch.object(m.os,'getxattr',return_value=b'x'*65536) as get,self.assertRaisesRegex(m.Held,'xattr-bound'):m.attributes(self.source)
  self.assertLess(get.call_count,20)
 def test_final_read_uses_checked_fd_for_receipt(self):
  with self.writer.hold():
   p=self.prepare();real=m.os.open;fired=[]
   def race(path,flags,*args,**kw):
    if path=='preparation.json' and 'dir_fd' in kw and not fired:
     target=p._operation/'preparation.json';retained=p._operation/'retained';target.rename(retained);target.write_bytes(b'{}')
     try:fd=real(path,flags,*args,**kw)
     finally:target.unlink();retained.rename(target);fired.append(True)
     return fd
    return real(path,flags,*args,**kw)
   with patch.object(m.os,'open',side_effect=race),self.assertRaisesRegex(m.Held,'read-fd-CAS'):p.revalidate()
   self.assertTrue(fired)

 def test_replaced_operation_parent_refused_before_file_write(self):
  real=m.write;fired=[]
  def late(p,raw,*args):
   if not fired:
    retained=p.parent.with_name('retained-operation');p.parent.rename(retained);p.parent.mkdir(mode=0o700)
    (p.parent/'operator-file').write_bytes(b'keep');fired.append(True)
   return real(p,raw,*args)
  with self.writer.hold(),patch.object(m,'write',side_effect=late),self.assertRaisesRegex(m.Held,'owned-directory-fd'):self.prepare()
  op=self.root/('archive-repair-'+self.operation_id);self.assertEqual(set(c.name for c in op.iterdir()),{'operator-file'})
  self.assertEqual((op/'operator-file').read_bytes(),b'keep')

 def test_persisted_custody_full9_matches_created_files(self):
  with self.writer.hold():
   p=self.prepare();body=__import__('json').loads((p._operation/'preparation.json').read_text())
   for name,key in (('original.arc','original'),('restored-original.arc','restore')):
    self.assertEqual(body['custody'][key],m.fact(p._operation/name,512*1024**2,__import__('time').monotonic()+10))

 def test_final_ordinary_purpose_cannot_create_inactive_catalog_alias(self):
  import inspect
  self.sql('INSERT INTO issues VALUES (?,?,?,?)',('777','456','late.cbz','Wanted'))
  alias=self.library/'late.cbz';real=g.ordinary_purpose;fired=[]
  def late(writer):
   result=real(writer)
   if not fired and any(frame.function=='close_passive' and frame.code_context and
         'self._modules[2].ordinary_purpose' in frame.code_context[0] for frame in inspect.stack()):
    os.symlink(self.source,alias);fired.append(True)
   return result
  with self.writer.hold():
   preparation=self.prepare()
   with patch.object(g,'ordinary_purpose',side_effect=late),self.assertRaises(m.Held):preparation.close_passive()
  self.assertTrue(fired);self.assertTrue(alias.is_symlink())

 def test_final_ordinary_purpose_cannot_create_negative_marker(self):
  import inspect
  real=g.ordinary_purpose;fired=[]
  def late(writer):
   result=real(writer)
   if not fired and any(frame.function=='close_passive' and frame.code_context and
         'self._modules[2].ordinary_purpose' in frame.code_context[0] for frame in inspect.stack()):
    (writer.root/'negative-retirement-v1.pending').write_bytes(b'fixture');fired.append(True)
   return result
  with self.writer.hold():
   preparation=self.prepare()
   with patch.object(g,'ordinary_purpose',side_effect=late),self.assertRaises(m.Held):preparation.close_passive()
  self.assertTrue(fired)

 def test_terminal_successor_after_last_semantic_callback_holds(self):
  real=g.ordinary_purpose;fired=[]
  def late(writer):
   result=real(writer)
   if not fired and any(frame.function=='close_passive' and frame.code_context and 'self._modules[2].ordinary_purpose' in frame.code_context[0] for frame in inspect.stack()):
    (writer.root/'negative-retirement-v1.terminal-pending').write_bytes(b'fixture');fired.append(True)
   return result
  with self.writer.hold():
   preparation=self.prepare()
   with patch.object(g,'ordinary_purpose',side_effect=late),self.assertRaises(m.Held):preparation.close_passive()
  self.assertTrue(fired)

 def test_repair_hold_after_last_semantic_callback_refuses_preparation(self):
  for name in ('archive-repair-v1.pending','archive-repair-v1.terminal-pending'):
   with self.subTest(name=name):
    real=g.ordinary_purpose;fired=[];marker=self.writer.root/name
    def late(writer):
     result=real(writer)
     if not fired and any(frame.function=='close_passive' and frame.code_context and 'self._modules[2].ordinary_purpose' in frame.code_context[0] for frame in inspect.stack()):
      marker.write_bytes(b'pending');fired.append(True)
     return result
    with self.writer.hold():
     preparation=self.prepare()
     with patch.object(g,'ordinary_purpose',side_effect=late),self.assertRaises(m.Held):preparation.close_passive()
    self.assertTrue(fired);marker.unlink();self.operation_id='2'*64

if __name__=='__main__':unittest.main()
