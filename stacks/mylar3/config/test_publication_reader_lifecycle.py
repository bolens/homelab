"""Disposable custody controls; fake parent observations are NOT runtime proof."""
import copy
from contextlib import closing
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
P=Path(__file__).resolve().with_name('publication_reader_lifecycle.py')
spec=importlib.util.spec_from_file_location('lifecycle_fixture',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.root.chmod(0o700)
  self.config=self.root/'config';self.config.mkdir();self.restore=self.root/'restore';self.restore.mkdir();self.scratch=self.root/'scratch';self.scratch.mkdir(mode=0o700);self.library=self.root/'library';self.library.mkdir();self.source=self.library/'a comic.cbz';self.source.write_bytes(b'comic')
  self.nonce='a'*64;self.parent=self.write('parent.py',b'pass\n');self.input=self.write('input.json',m.encoded({'test':'explicit fake'}) );self.acceptance=self.write('acceptance.json',b'{}');self.manifest=self.write('manifest.json',b'{}')
  for root in (self.config,self.restore):
   for name in ('database.sqlite','tasks.sqlite'):
    con=sqlite3.connect(root/name);con.execute('CREATE TABLE BOOK(ID INTEGER, URL TEXT)');con.execute('INSERT INTO BOOK VALUES (1,?)',('file:///data/library/a%20comic.cbz',));con.commit();con.close()
  self.state={'Id':'1'*64,'Name':'/reader','Image':'sha256:'+'2'*64,'Path':'/entry','Args':[],'Config':{},'HostConfig':{},'Mounts':[{'Type':'bind','Source':str(self.library),'Destination':'/data/library'}],'State':{'Running':False,'Pid':0,'Status':'exited'}}
  self.reader={'config_root':str(self.config),'restore_root':str(self.restore),'scratch':str(self.scratch),'backup_manifest':self.manifest,'backup_acceptance':self.acceptance,'restore_pairs':self.pairs(self.restore),'current_pairs':self.pairs(self.config),'runtime':self.state,'child_source_sha256':'3'*64,'child_image':'sha256:'+'4'*64}
  self.doc={'version':1,'kind':'owning-reader-pipe-custody','nonce':self.nonce,'input_sha256':self.input['sha256'],'command':['fixture'],'parent_source':self.parent,'reader':self.reader,'proofs':{'manifest':self.manifest,'acceptance':self.acceptance},'deadline_seconds':60}
  self.write('input.lifecycle.json',m.encoded(self.doc));self.channel=m.ParentPipe.__new__(m.ParentPipe);self.channel.thread=threading.get_ident();self.channel.seq=0
  readfd,writefd=os.pipe();self.addCleanup(os.close,readfd);self.addCleanup(os.close,writefd);self.channel.input=readfd;self.channel.output=writefd;self.channel.facts=(tuple(m.five(os.fstat(readfd))),tuple(m.five(os.fstat(writefd))));m._PIPE_SEALS[self.channel]=(readfd,writefd,self.channel.thread,self.channel.facts)
  self.response={'reader':copy.deepcopy(self.state),'child_source_sha256':'3'*64,'child_image':'sha256:'+'4'*64}
  self.mock=patch.object(m.ParentPipe,'challenge',lambda *args:copy.deepcopy(self.response));self.mock.start();self.addCleanup(self.mock.stop);self.addCleanup(self.tmp.cleanup)
  class Scope:
   def __init__(obj,custody):obj.custody=custody
   @property
   def binding(obj):return {'roots':[str(self.library)],'host_scopes':{'library':str(self.library)}}
   def vectors(obj):return {},{}
   def revalidate(obj):obj.custody.revalidate_stopped()
  self.scope_class=Scope;self.scope_module=SimpleNamespace(__file__='/app/mylar3/mylar/publication_native_configured_scope.py',NativeConfiguredScope=Scope,from_checked_parent=lambda custody:Scope(custody))
  self.scope_patch=patch.object(m.importlib,'import_module',lambda name:self.scope_module if name=='mylar.publication_native_configured_scope' else (_ for _ in ()).throw(m.Held('fixture-no-other-import')));self.scope_patch.start();self.addCleanup(self.scope_patch.stop)
 def write(self,name,raw):
  p=self.root/name;p.write_bytes(raw);p.chmod(0o600);return {'path':str(p),'sha256':hashlib.sha256(raw).hexdigest(),'signature9':m.nine(p.lstat())}
 def pairs(self,root):
  return {name:{'':{'sha256':hashlib.sha256((root/name).read_bytes()).hexdigest(),'signature9':m.nine((root/name).lstat())}} for name in ('database.sqlite','tasks.sqlite')}
 def make(self):return m.StoppedReaderCustody(m._KEY,self.input['path'],self.input['sha256'],self.nonce,self.parent['sha256'],['fixture'],self.channel)
 def test_positive_control_and_original_vectors(self):
  c=self.make();files,nodes,absent=c.vectors();self.assertIn(self.config/'database.sqlite',files);self.assertEqual(len(absent),12);self.assertIn(self.config,nodes)
 def test_mutating_current_pair_excluded_only_control_vectors(self):
  c=self.make();(self.config/'database.sqlite').chmod(0o600);c.control_vectors()
  with self.assertRaises(m.Held):c.vectors()
 def test_observed_stored_URL_spelling(self):self.assertEqual(self.make().native_url(self.source),'file:///data/library/a%20comic.cbz')
 def test_ambiguous_stored_URL_refused(self):
  con=sqlite3.connect(self.config/'database.sqlite');con.execute('INSERT INTO BOOK VALUES (2,?)',('file:///data/library/a comic.cbz',));con.commit();con.close();self.reader['current_pairs']=self.pairs(self.config);self.write('input.lifecycle.json',m.encoded(self.doc))
  with self.assertRaises(m.Held):self.make().native_url(self.source)
 def test_no_stored_URL_refused(self):
  other=self.library/'other.cbz';other.write_bytes(b'existing')
  with self.assertRaises(m.Held):self.make().native_url(other)
 def test_public_constructor_rejects_foreign_channel(self):
  with self.assertRaises(m.Held):m.StoppedReaderCustody(m._KEY,self.input['path'],self.input['sha256'],self.nonce,self.parent['sha256'],['fixture'],object())
 def test_running_reader_refused(self):
  c=self.make();self.response['reader']['State']['Running']=True
  with self.assertRaises(m.Held):c.revalidate_stopped()
 def test_stopped_incarnation_change_refused(self):
  c=self.make();self.response['reader']['State']['FinishedAt']='foreign'
  with self.assertRaises(m.Held):c.revalidate_stopped()
 def test_mount_change_refused(self):
  c=self.make();self.response['reader']['Mounts'][0]['Destination']='/data/foreign'
  with self.assertRaises(m.Held):c.revalidate_stopped()
 def test_foreign_child_source_refused(self):
  c=self.make();self.response['child_source_sha256']='9'*64
  with self.assertRaises(m.Held):c.revalidate_stopped()
 def test_foreign_child_image_refused(self):
  c=self.make();self.response['child_image']='sha256:'+'9'*64
  with self.assertRaises(m.Held):c.revalidate_stopped()
 def test_deadline_attribute_mutation_refused(self):
  c=self.make();c.deadline+=999
  with self.assertRaises(m.Held):c.revalidate_stopped()
 def test_path_attribute_mutation_refused(self):
  c=self.make();c.main=self.restore/'database.sqlite'
  with self.assertRaises(m.Held):c.native_url(self.source)
 def test_late_parent_challenge_control_mutation_refused(self):
  c=self.make()
  def challenge(*args):Path(self.manifest['path']).write_bytes(b'foreign');return copy.deepcopy(self.response)
  with patch.object(m.ParentPipe,'challenge',challenge),self.assertRaises(m.Held):c.control_vectors()
 def test_late_passive_callback_absence_mutation_refused(self):
  c=self.make();real=m.passive
  def changed(*args):real(*args);(self.restore/'database.sqlite-wal').write_bytes(b'foreign')
  with patch.object(m,'passive',changed),self.assertRaises(m.Held):c.control_vectors()
 def test_late_URL_passive_callback_live_absence_mutation_refused(self):
  c=self.make();real=m.passive;fired=[False]
  def changed(files,nodes,absent=()):
   real(files,nodes,absent)
   if self.config/'database.sqlite' in files and not fired[0]:fired[0]=True;(self.config/'database.sqlite-journal').write_bytes(b'foreign')
  with patch.object(m,'passive',changed),self.assertRaises(m.Held):c.native_url(self.source)
  self.assertTrue(fired[0])
 def test_control_mode_refused(self):
  Path(self.manifest['path']).chmod(0o644)
  with self.assertRaises(m.Held):self.make()
 def test_control_symlink_refused(self):
  p=Path(self.manifest['path']);p.unlink();p.symlink_to(Path(self.acceptance['path']))
  with self.assertRaises(m.Held):self.make()
 def test_duplicate_control_keys_refused(self):
  self.write('input.lifecycle.json',b'{"version":1,"version":1}')
  with self.assertRaises(m.Held):self.make()
 def test_pair_symlink_refused(self):
  p=self.config/'database.sqlite';p.unlink();p.symlink_to(self.restore/'database.sqlite')
  with self.assertRaises((m.Held,OSError)):self.make()
 def test_descriptor_foreign_leaf_refused(self):
  real=os.open;original=Path(self.manifest['path']);foreign=Path(self.acceptance['path'])
  def opened(path,flags,*args,**kwargs):
   if path==original.name and 'dir_fd' in kwargs:return real(foreign,flags)
   return real(path,flags,*args,**kwargs)
  with patch.object(m.os,'open',opened),self.assertRaises(m.Held):m.read(original,self.manifest['sha256'])
 def test_last_read_ancestor_helper_mutation_refused(self):
  real=m.five;count=[0];path=Path(self.manifest['path']);maximum=2*len(path.parents)+len(path.parents)
  def changed(z):
   result=real(z);count[0]+=1
   # Admission ancestor capture + root/walk FD + final semantic ancestors.
   if count[0]==maximum:path.write_bytes(b'foreign')
   return result
  with patch.object(m,'five',changed),self.assertRaises(m.Held):m.read(path,self.manifest['sha256'])
  self.assertEqual(count[0],maximum)
 def test_native_factory_refuses_reader_only_frame(self):
  with self.assertRaisesRegex(m.Held,'native-observation-required'):self.make().native_observation()
 def test_native_observation_is_fresh_copied(self):
  self.response.update(native={'fixture':1},worker={'fixture':2},child_mounts=[]);c=self.make()
  x=c.native_observation();x['native']['fixture']=99
  self.assertEqual(c.native_observation()['native']['fixture'],1)
 def test_native_proof_is_bound_immutable_control(self):
  ref=self.write('native.json',b'{}');self.doc['proofs']['native_scope']=ref;self.write('input.lifecycle.json',m.encoded(self.doc));c=self.make()
  self.assertEqual(c.native_proof(),ref);c.proofs['native_scope']['sha256']='f'*64
  with self.assertRaises(m.Held):c.native_proof()
 def test_checked_invocation_binding(self):
  c=self.make();b=c.invocation_binding();self.assertEqual(b,dict(input_path=self.input['path'],input_sha256=self.input['sha256'],parent_sha256=self.parent['sha256'],provider_sha256='3'*64,command=['fixture'],nonce=self.nonce));b['command'].append('foreign');self.assertEqual(c.invocation_binding()['command'],['fixture'])
 def test_command_attribute_mutation_refused(self):
  c=self.make();c.command=('foreign',)
  with self.assertRaises(m.Held):c.invocation_binding()
 def test_late_challenge_reader_rebase_refused(self):
  c=self.make()
  def changed(*args):
   c.reader['runtime']['Image']='sha256:'+'9'*64;value=copy.deepcopy(self.response);value['reader']['Image']=c.reader['runtime']['Image'];return value
  with patch.object(m.ParentPipe,'challenge',changed),self.assertRaises(m.Held):c.revalidate_stopped()
 def test_same_root_restore_refused(self):
  self.reader['restore_root']=str(self.config);self.reader['restore_pairs']=self.pairs(self.config);self.write('input.lifecycle.json',m.encoded(self.doc))
  with self.assertRaises(m.Held):self.make()
 def test_nested_source_scratch_refused(self):
  sub=self.config/'scratch';sub.mkdir(mode=0o700);self.reader['scratch']=str(sub);self.write('input.lifecycle.json',m.encoded(self.doc))
  with self.assertRaises(m.Held):self.make()
 def test_public_scratch_refused(self):
  self.scratch.chmod(0o755)
  with self.assertRaises(m.Held):self.make()
 def test_source_unchanged(self):
  c=self.make();before=(self.source.read_bytes(),m.nine(self.source.lstat()),self.pairs(self.config));c.native_url(self.source);self.assertEqual(before,(self.source.read_bytes(),m.nine(self.source.lstat()),self.pairs(self.config)))
 def test_native_child_to_host_to_reader_geometry(self):
  c=self.make();native=self.root/'native-child';native.mkdir();source=native/self.source.name;source.write_bytes(b'comic')
  self.scope_class.binding=property(lambda obj:{'roots':[str(native)],'host_scopes':{'library':str(self.library)}})
  self.assertEqual(c.native_url(source),'file:///data/library/a%20comic.cbz')
 def test_host_path_is_not_native_child_alias(self):
  c=self.make();native=self.root/'native-child';native.mkdir()
  self.scope_class.binding=property(lambda obj:{'roots':[str(native)],'host_scopes':{'library':str(self.library)}})
  with self.assertRaisesRegex(m.Held,'source-outside-native-library'):c.native_url(self.source)
 def test_foreign_scope_module_origin_holds(self):
  c=self.make();self.scope_module.__file__='/tmp/foreign.py'
  with self.assertRaisesRegex(m.Held,'installed-native-scope'):c.native_url(self.source)
 def test_equal_specific_reader_mounts_hold(self):
  self.state['Mounts'].append(dict(self.state['Mounts'][0],Destination='/data/other'));self.write('input.lifecycle.json',m.encoded(self.doc));self.response['reader']=copy.deepcopy(self.state)
  with self.assertRaisesRegex(m.Held,'native-reader-mapping'):self.make().native_url(self.source)
 def test_more_specific_reader_mount_selects_stored_URL(self):
  self.state['Mounts'].append({'Type':'bind','Source':str(self.root),'Destination':'/data/broad'});self.write('input.lifecycle.json',m.encoded(self.doc));self.response['reader']=copy.deepcopy(self.state)
  self.assertEqual(self.make().native_url(self.source),'file:///data/library/a%20comic.cbz')
 def test_parent_callback_cannot_substitute_or_reseal_native_proof(self):
  for reseal in (False,True):
   with self.subTest(reseal=reseal):
    c=self.make();real=m.ParentPipe.challenge;foreign=self.write('foreign-proof.json',b'{}')
    def changed(*args):
     response=real(*args);c.proofs['native_scope']=foreign
     if reseal:c.core=c._core();m._SEALS[c]=c.core
     return response
    with patch.object(m.ParentPipe,'challenge',changed),self.assertRaises(m.Held):c.native_proof()
 def test_last_passive_callback_cannot_refresh_control_proof(self):
  c=self.make();real=m.passive;foreign=self.write('foreign-proof.json',b'{}');fired=[]
  def changed(*args):
   real(*args)
   if not fired:c.proofs['native_scope']=foreign;c.core=c._core();m._SEALS[c]=c.core;fired.append(True)
  with patch.object(m,'passive',changed),self.assertRaises(m.Held):c.control_vectors()
  self.assertTrue(fired)
 def test_channel_callback_cannot_refresh_admitted_descriptor_identity(self):
  c=self.make();real=m.ParentPipe.challenge;readfd,writefd=os.pipe();self.addCleanup(os.close,readfd);self.addCleanup(os.close,writefd)
  def changed(*args):
   response=real(*args);self.channel.input=readfd;self.channel.output=writefd;self.channel.facts=(tuple(m.five(os.fstat(readfd))),tuple(m.five(os.fstat(writefd))));m._PIPE_SEALS[self.channel]=(readfd,writefd,self.channel.thread,self.channel.facts);return response
  with patch.object(m.ParentPipe,'challenge',changed),self.assertRaises(m.Held):c.revalidate_stopped()
 def test_reader_destination_overmount_refuses_wrong_host(self):
  sub=self.library/'sub';sub.mkdir();source=sub/self.source.name;source.write_bytes(b'comic');foreign=self.root/'foreign-reader';foreign.mkdir();(foreign/self.source.name).write_bytes(b'foreign')
  self.state['Mounts'].append({'Type':'bind','Source':str(foreign),'Destination':'/data/library/sub'})
  with closing(sqlite3.connect(self.config/'database.sqlite')) as db,db:db.execute('UPDATE BOOK SET URL=?',('file:///data/library/sub/a%20comic.cbz',))
  self.reader['current_pairs']=self.pairs(self.config);self.write('input.lifecycle.json',m.encoded(self.doc));self.response['reader']=copy.deepcopy(self.state)
  with self.assertRaisesRegex(m.Held,'destination-shadow'):self.make().native_url(source)
 def test_reader_destination_duplicate_refuses_ambiguity(self):
  self.state['Mounts'].append({'Type':'bind','Source':str(self.root),'Destination':'/data/library'});self.write('input.lifecycle.json',m.encoded(self.doc));self.response['reader']=copy.deepcopy(self.state)
  with self.assertRaisesRegex(m.Held,'destination-shadow'):self.make().native_url(self.source)
 def test_matching_more_specific_reader_destination_stays_valid(self):
  sub=self.library/'sub';sub.mkdir();source=sub/self.source.name;source.write_bytes(b'comic');self.state['Mounts'].append({'Type':'bind','Source':str(sub),'Destination':'/data/library/sub'})
  with closing(sqlite3.connect(self.config/'database.sqlite')) as db,db:db.execute('UPDATE BOOK SET URL=?',('file:///data/library/sub/a%20comic.cbz',))
  self.reader['current_pairs']=self.pairs(self.config);self.write('input.lifecycle.json',m.encoded(self.doc));self.response['reader']=copy.deepcopy(self.state)
  self.assertEqual(self.make().native_url(source),'file:///data/library/sub/a%20comic.cbz')
class PipeTests(unittest.TestCase):
 def child(self,mode):
  code="import importlib.util; s=importlib.util.spec_from_file_location('m',%r);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.ParentPipe().challenge('a'*64,'b'*64,'c'*64)" % str(P)
  process=subprocess.Popen([sys.executable,'-I','-B','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  request=json.loads(process.stdout.readline());response={**request,'type':'observation','reader':{},'child_source_sha256':'d'*64,'child_image':'sha256:'+'e'*64}
  if mode=='extended':response.update(native={},worker={},child_mounts=[])
  if mode=='partial-native':response.update(native={})
  if mode=='stale':response['sequence']=0
  if mode=='nonce':response['nonce']='f'*64
  if mode=='extra':response['foreign']=True
  if mode=='challenge':response['challenge']='0'*64
  if mode!='closed':process.stdin.write(m.encoded(response)+b'\n');process.stdin.flush()
  process.stdin.close();process.stdin=None;out,err=process.communicate(timeout=5);return process.returncode,out,err
 def test_actual_inherited_pipe_redirection_is_refused(self):
  code="import importlib.util,os; s=importlib.util.spec_from_file_location('m',%r);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);c=m.ParentPipe();r,w=os.pipe();c.input=r;c.output=w;c.facts=(tuple(m.five(os.fstat(r))),tuple(m.five(os.fstat(w))));c.challenge('a'*64,'b'*64,'c'*64)" % str(P)
  result=subprocess.run([sys.executable,'-I','-B','-c',code],input=b'',stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5)
  self.assertNotEqual(result.returncode,0);self.assertIn(b'lifecycle-original-pipe',result.stderr);self.assertEqual(result.stdout,b'')
 def test_extended_inherited_pipe_positive(self):self.assertEqual(self.child('extended')[0],0)
 def test_partial_native_frame_refused(self):self.assertNotEqual(self.child('partial-native')[0],0)
 def test_fresh_inherited_pipe_positive(self):self.assertEqual(self.child('fresh')[0],0)
 def test_stale_sequence(self):self.assertNotEqual(self.child('stale')[0],0)
 def test_foreign_nonce(self):self.assertNotEqual(self.child('nonce')[0],0)
 def test_foreign_challenge(self):self.assertNotEqual(self.child('challenge')[0],0)
 def test_extra_schema(self):self.assertNotEqual(self.child('extra')[0],0)
 def test_parent_eof(self):self.assertNotEqual(self.child('closed')[0],0)
if __name__=='__main__':unittest.main()
