"""Actual admission/reader/FD mechanics; installed/native types explicit doubles."""
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
p=load('preimage_provider',str(Path(__file__).resolve().parent / 'comic_negative_reader_action.py'))
o=load('observer_fixtures',str(Path(__file__).resolve().parent / 'test_negative_terminal_observer.py'))
f=load('new_admission_fixtures',str(Path(__file__).resolve().parent / '_negative_reader_fixtures/fixture_test_publication_reader_admission_v11.py'))
r=load('new_reader',str(Path(__file__).resolve().parent / '_negative_reader_fixtures/fixture_publication_reader_phase_v10.py'))
class Controls(unittest.TestCase):
 def setUp(self):
  self.of=o.Controls();self.of.setUp();self.addCleanup(self.of.doCleanups)
  self.af=f.AdmissionTests();self.af.setUp();self.addCleanup(self.af.doCleanups)
  c=self.of
  external=self.af.root/'external';external.mkdir(mode=0o700);self.af.operation=external/'operation';self.af.operation.mkdir(mode=0o700)
  # Original path is physically restored only in disposable fixture setup.
  for member in c.members:
   src=Path(member['source']);target=Path(member['target']);src.hardlink_to(target);target.unlink()
  class Controller:pass
  class Writer:pass
  self.controller=Controller();self.controller.database=c.root/'workflow';self.controller.native_database=c.root/'catalog'
  self.writer=Writer();self.writer.root=c.root;pub=self.writer.root/'publication-v1.json';pub.write_bytes(b'publication');pub.chmod(0o600)
  self.coord=self.af.coordinator;self.coord._controller=self.controller;self.coord._writer=self.writer;self.coord._census={'epoch':13}
  class Prep:
   def __init__(self,b):self.binding=copy.deepcopy(b)
   def revalidate(self):
    obs=o.m.Observation()
    for path,expected in self.binding['file_facts'].items():
     actual=obs.fact(path);p.need(actual['signature9']==expected['signature9'] and actual['sha256']==expected['sha256'] and actual['xattrs']==self.binding['xattrs'][path],'fixture-native-drift')
    obs.close();return copy.deepcopy(self.binding)
  self.preps=[]
  for b in c.native:
   b=copy.deepcopy(b);actual=o.m.Observation().fact(b['source']);b['file_facts'][b['source']]={k:v for k,v in actual.items() if k!='xattrs'};b['xattrs'][b['source']]=actual['xattrs'];self.preps.append(Prep(b))
  self.af.negative=self.preps
  doc=copy.deepcopy(self.af.context._document);doc['controls']=c.pre['backup_controls'];doc['operation']=str(self.af.operation)
  self.af.context=f.m.CheckedChildInvocation(f.m._KEY,'a'*64,{self.af.control:f.m.sig(self.af.control)},f.m.parents([self.af.control]),doc,lifecycle=self.af.lifecycle)
  self.admitted=self.af.admission();self.reader=r.StoppedReaderPhase(r._KEY,self.admitted)
  self.modules={'publication_api':SimpleNamespace(Controller=Controller),'media_writer':SimpleNamespace(Writer=Writer),'publication_reader_native_coordinator':SimpleNamespace(NativeReadCoordinator=type(self.coord)),'publication_reader_admission':SimpleNamespace(StoppedReaderAdmission=f.m.StoppedReaderAdmission),'publication_reader_phase':SimpleNamespace(StoppedReaderPhase=r.StoppedReaderPhase),'publication_negative':SimpleNamespace(NativeNegativePreparation=Prep)}
  self.plan={'operation':str(self.af.operation)};self.nodes={q:p.five(q.lstat()) for q in (self.af.operation,*self.af.operation.parents)}
 def go(self):return p.persist_preimage(self.plan,self.modules,self.controller,self.writer,self.coord,self.preps,self.admitted,self.reader,self.nodes)
 def test_actual_readonly_admission_restore_preimage_before_mutation(self):
  ref=self.go();value=p.decode(Path(ref['path']).read_bytes());self.assertEqual(value['restore_pairs'],self.admitted._custody);self.assertEqual(len(value['native']),5);self.assertEqual(value['census'],self.coord._census);self.assertFalse(any('pending' in x.name for x in self.of.root.iterdir()))
 def test_write_loss_no_returned_preimage(self):
  real=p.write
  def lost(*args,**kwargs):real(*args,**kwargs);raise OSError('fixture-lost-write-ACK')
  with patch.object(p,'write',new=lost):
   with self.assertRaises(OSError):self.go()
  self.assertTrue((self.af.operation/'terminal-observation-preimage.json').exists())
 def test_intended_readback_corruption_held(self):
  real=p.write
  def changed(*args,**kwargs):ref=real(*args,**kwargs);Path(ref['path']).write_bytes(b'{}');return ref
  with patch.object(p,'write',new=changed):
   with self.assertRaises(p.Held):self.go()
 def test_source_change_after_write_holds(self):
  real=p.write
  def changed(*args,**kwargs):ref=real(*args,**kwargs);Path(self.preps[0].binding['source']).chmod(0o640);return ref
  with patch.object(p,'write',new=changed):
   with self.assertRaises(Exception):self.go()
 def test_original_reader_pair_after_write_holds(self):
  real=p.write
  def changed(*args,**kwargs):ref=real(*args,**kwargs);(self.admitted._root/'tasks.sqlite').chmod(0o640);return ref
  with patch.object(p,'write',new=changed):
   with self.assertRaises(Exception):self.go()
 def test_preimage_is_exclusive_no_replay(self):
  self.go()
  with self.assertRaises(FileExistsError):self.go()
 def test_last_readback_operation_parent_rebuild_holds(self):
  real=p.checked;fired=[]
  def changed(ref,*args,**kwargs):
   result=real(ref,*args,**kwargs)
   if Path(ref['path']).name=='terminal-observation-preimage.json' and not fired:
    root=self.af.operation.parent;saved=root.with_name('saved-external');root.rename(saved);root.mkdir(mode=0o700);(saved/'operation').rename(root/'operation')
    fired.append(True)
   return result
  with patch.object(p,'checked',new=changed):
   with self.assertRaisesRegex(ValueError,'ancestor'):self.go()
  self.assertTrue(fired)
if __name__=='__main__':unittest.main()
