"""Explicit substituted factory observations; NOT installed positive authority."""
from contextlib import contextmanager
import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
P=Path(str(Path(__file__).resolve().parent / 'comic_negative_reader_action.py'))
s=importlib.util.spec_from_file_location('action_fixture',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.root.chmod(0o700);self.operation=self.root/'operation';self.operation.mkdir(mode=0o700)
  self.config=self.root/'reader';self.config.mkdir();self.restore=self.root/'restore';self.restore.mkdir();self.scratch=self.root/'scratch';self.scratch.mkdir();self.library=self.root/'library';self.library.mkdir();self.data=self.root/'native';self.data.mkdir();self.events=[]
  self.controls={k:self.ref(k,{}) for k in ('stopped_runtime','backup_ack','backup_manifest','backup_acceptance','rows','schema','reviewed_plan','timestamp_evidence','custody')}
  self.input=self.ref('provider',{})
  self.plan={'operation':str(self.operation),'provider_input':self.input,'controls':self.controls,'nonce':'a'*64,'parent_sha256':'b'*64,'admission_source_sha256':'c'*64}
  self.action={'members':[{'source':str(self.library/f'{i}.cbz'),'owner':{'fixture':i},'counterpart':str(self.library/f'{i}-correct.cbz'),'retained':str(self.root/f'{i}-retained'),'restore':str(self.root/f'{i}-restore')} for i in range(5)],'targets':[str(self.root/f'target-{i}') for i in range(5)],'batch_journal':str(self.root/'batch'),'start_journal':str(self.root/'start'),'commit_journal':str(self.root/'commit'),'operation':str(self.operation)}
  self.plan['action_input']=self.ref('action',self.action)
  self.binding={'input_path':self.input['path'],'input_sha256':self.input['sha256'],'parent_sha256':self.plan['parent_sha256'],'provider_sha256':'d'*64,'command':['explicit-fixture'],'nonce':self.plan['nonce']}
  self.lifecycle=SimpleNamespace(config_root=self.config,restore_root=self.restore,scratch=self.scratch,invocation_binding=lambda:self.binding)
  class Writer:
   root=self.data
   @contextmanager
   def hold(w,timeout):
    self.events.append(('hold',timeout));yield;self.events.append('released')
  self.controller=SimpleNamespace(roots=[self.library]);self.writer=Writer()
  class Scope:
   def controller_writer(x):self.events.append('configured-pair');return self.controller,self.writer
   def revalidate(x):self.events.append('configured-revalidate')
  self.scope=Scope();self.coordinator=SimpleNamespace(revalidate=lambda:self.events.append('coordinator-original'),close_owned_terminal=lambda a:self.events.append('coordinator-terminal'))
  def prep(*args):self.events.append(('prep',args[3]));return SimpleNamespace(revalidate=lambda:{'fixture_only':True})
  reader=SimpleNamespace(close_native_phase_passive=lambda _:self.events.append('reader-original'))
  self.terminal=SimpleNamespace(status=lambda:{'marker_cleared':True,'publication_acceptance':False})
  class Aggregate:
   def __init__(x):x.phase='prepared';x.terminal=self.terminal
   def execute(x):self.events.append('execute');x.phase='terminal'
  self.aggregate=Aggregate()
  preimage=patch.object(m,'persist_preimage',return_value={'fixture_only':True});preimage.start();self.addCleanup(preimage.stop)
  # Orchestration doubles only; this does not exercise owning receipt capture.
  terminalrefs=patch.object(m,'owning_terminal_refs',return_value={'fixture_only':True});terminalrefs.start();self.addCleanup(terminalrefs.stop)
  def admission(*args,**kwargs):self.events.append('invocation');self.invocation=m.decode(Path(args[0]).read_bytes());return object()
  self.modules={'publication_native_configured_scope':SimpleNamespace(NativeConfiguredScope=Scope,from_checked_parent=lambda l:self.scope),'publication_reader_admission':SimpleNamespace(PARENT_SHA=self.plan['parent_sha256'],enter_checked_child=admission,admit_child=lambda *a:SimpleNamespace(binding={'fixture_only':True})),'publication_reader_native_coordinator':SimpleNamespace(from_held_existing=lambda *a:self.coordinator),'publication_negative':SimpleNamespace(prepare_existing=prep),'publication_reader_phase':SimpleNamespace(from_admission=lambda a:reader),'publication_negative_batch':SimpleNamespace(prepare_existing=lambda *a:self.events.append('batch-marker') or object()),'publication_negative_batch_transition':SimpleNamespace(from_prepared=lambda *a:object()),'publication_negative_aggregate':SimpleNamespace(NegativeReaderAggregate=Aggregate,from_staged_preparation=lambda *a:self.aggregate)}
 def ref(self,name,value):
  p=self.root/(name+'.json');p.write_bytes(m.encoded(value));p.chmod(0o600);return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'signature9':m.nine(p.lstat())}
 def run_purpose(self,execute=False):return m.purpose_existing(self.plan,self.lifecycle,self.modules,execute=execute)
 def test_prepare_observes_only_no_batch_SQL_or_retirement(self):
  r=self.run_purpose();self.assertFalse(r['source_retirement_authority']);self.assertNotIn('batch-marker',self.events);self.assertNotIn('execute',self.events);self.assertEqual(self.events[-1],'released');self.assertEqual(sum(type(e) is tuple and e[0]=='prep' for e in self.events),5)
 def test_execute_same_objects_terminal_before_coordinator_successor(self):
  r=self.run_purpose(True);self.assertFalse(r['publication_acceptance']);self.assertFalse(r['reader_resume_authority']);self.assertEqual(self.events[-3:],['execute','coordinator-terminal','released'])
 def test_no_caller_native_roots_used(self):
  self.plan['native']={'data':'/invented','roots':['/invented']};self.run_purpose();self.assertEqual(self.events[0],'configured-pair')
 def test_actual_provider_input_and_admission_source_distinct(self):
  self.run_purpose();self.assertEqual(self.invocation['provider_input_path'],self.input['path']);self.assertEqual(self.invocation['child_source_sha256'],'d'*64);self.assertEqual(self.invocation['admission_source_sha256'],'c'*64)
 def test_wrong_parent_before_Writer(self):
  self.plan['parent_sha256']='f'*64
  with self.assertRaisesRegex(m.Held,'owning-parent-pin'):self.run_purpose()
  self.assertFalse(any(type(e) is tuple and e[0]=='hold' for e in self.events))
 def test_fifth_member_missing_holds_before_invocation(self):
  self.action['members'].pop();self.plan['action_input']=self.ref('action',self.action)
  with self.assertRaisesRegex(m.Held,'five-only'):self.run_purpose()
  self.assertNotIn('invocation',self.events)
 def test_foreign_operation_not_written(self):
  self.action['operation']=str(self.library);self.plan['action_input']=self.ref('action',self.action)
  with self.assertRaisesRegex(m.Held,'operation-binding'):self.run_purpose()
  self.assertFalse((self.library/'invocation.json').exists())
 def test_output_inside_native_scope_held_before_write(self):
  op=self.library/'op';op.mkdir(mode=0o700);self.plan['operation']=str(op)
  with self.assertRaisesRegex(m.Held,'outside-native'):self.run_purpose()
  self.assertFalse((op/'invocation.json').exists())
 def test_output_inside_reader_scope_held_before_factory(self):
  op=self.config/'op';op.mkdir(mode=0o700);self.plan['operation']=str(op)
  with self.assertRaisesRegex(m.Held,'outside-reader'):self.run_purpose()
  self.assertEqual(self.events,[])
 def test_forged_scope_class_holds(self):
  self.modules['publication_native_configured_scope'].from_checked_parent=lambda _:True
  with self.assertRaisesRegex(m.Held,'exact-configured-scope'):self.run_purpose()
 def test_unknown_member_field_holds(self):
  self.action['members'][0]['override']=True;self.plan['action_input']=self.ref('action',self.action)
  with self.assertRaisesRegex(m.Held,'member-schema'):self.run_purpose()
 def test_uncertain_terminal_not_accepted_or_coordinator_consumed(self):
  self.terminal.status=lambda:{'marker_cleared':False,'publication_acceptance':False}
  with self.assertRaisesRegex(m.Held,'terminal-observation'):self.run_purpose(True)
  self.assertNotIn('coordinator-terminal',self.events)
 def test_missing_actual_scope_factory_not_replaced_by_JSON(self):
  self.modules['publication_native_configured_scope'].from_checked_parent=lambda _:(_ for _ in ()).throw(m.Held('installed-factory-missing'))
  with self.assertRaisesRegex(m.Held,'installed-factory-missing'):self.run_purpose(True)
  self.assertEqual(self.events,[])
 def test_late_control_change_holds_after_prepare_callbacks(self):
  self.coordinator.revalidate=lambda:Path(self.controls['custody']['path']).chmod(0o640)
  with self.assertRaisesRegex(m.Held,'original-file'):self.run_purpose()
 def test_initial_operation_ancestor_rebuild_holds_before_write(self):
  real=self.scope.controller_writer
  def changed():
   result=real();self.operation.rename(self.root/'retained-operation');self.operation.mkdir(mode=0o700);return result
  self.scope.controller_writer=changed
  with self.assertRaisesRegex(m.Held,'original-ancestor'):self.run_purpose()
  self.assertFalse((self.operation/'invocation.json').exists())
 def test_preimage_write_lost_ACK_never_reaches_batch_or_execute(self):
  with patch.object(m,'persist_preimage',side_effect=OSError('fixture-lost-preimage-ACK')):
   with self.assertRaises(OSError):self.run_purpose(True)
  self.assertNotIn('batch-marker',self.events);self.assertNotIn('execute',self.events)
 def test_preimage_readback_failure_never_reaches_batch_or_execute(self):
  with patch.object(m,'persist_preimage',side_effect=m.Held('preimage-intended-readback')):
   with self.assertRaisesRegex(m.Held,'intended-readback'):self.run_purpose(True)
  self.assertNotIn('batch-marker',self.events);self.assertNotIn('execute',self.events)
 def test_write_root_alias_never_writes_foreign_output(self):
  foreign=self.root/'foreign';foreign.mkdir(mode=0o700);saved=self.root/'saved';real=m.os.open;fired=[False]
  def altered(path,flags,*a,**kw):
   if path=='result.json' and 'dir_fd' in kw and not fired[0]:
    fired[0]=True;self.operation.rename(saved);self.operation.symlink_to(foreign,target_is_directory=True)
   return real(path,flags,*a,**kw)
  with patch.object(m.os,'open',altered),self.assertRaises(m.Held):m.write(self.operation/'result.json',{})
  self.assertTrue(fired[0]);self.assertFalse((foreign/'result.json').exists());self.assertTrue((saved/'result.json').exists())
class WireTests(unittest.TestCase):
 def test_sdk_normal_filenames_and_unknown_refusal(self):
  self.assertEqual(m.sdk_map({'publication_api.py':'a'*64,'__init__.py':'b'*64}),{'publication_api.py':'a'*64,'__init__.py':'b'*64})
  for name in ('publication_apiXpy','publication_api\\.py','../publication_api.py','publication_api.py/','Publication_api.py','publication_api.py\x00'):
   with self.subTest(name=name),self.assertRaisesRegex(m.Held,'sdk-map'):m.sdk_map({name:'a'*64})
 def test_command_template_no_input_hash_fixed_point(self):
  args=SimpleNamespace(phase='execute',input='/private/input.json',input_sha256='a'*64,source_sha256='b'*64)
  template=['/lsiopy/bin/python3','-B',str(Path(m.__file__).absolute()),'--phase','execute','--input',args.input,'--input-sha256','<INPUT_SHA256>','--source-sha256',args.source_sha256]
  plan={'command_template':template};actual=[args.input_sha256 if x=='<INPUT_SHA256>' else x for x in template]
  self.assertEqual(m.actual_command(plan,args,actual),actual)
  args.input_sha256='c'*64;actual[8]=args.input_sha256
  self.assertEqual(m.actual_command(plan,args,actual),actual)
 def test_command_template_exact_flags_and_values(self):
  args=SimpleNamespace(phase='execute',input='/private/input.json',input_sha256='a'*64,source_sha256='b'*64)
  template=['python3','-B',str(Path(m.__file__).absolute()),'--phase','execute','--input',args.input,'--input-sha256','<INPUT_SHA256>','--source-sha256',args.source_sha256]
  actual=[args.input_sha256 if x=='<INPUT_SHA256>' else x for x in template]
  wrong=list(actual);wrong[4]='prepare'
  with self.assertRaisesRegex(m.Held,'actual-command'):m.actual_command({'command_template':template},args,wrong)
  no=list(template);no[8]='a'*64
  with self.assertRaisesRegex(m.Held,'command-template'):m.actual_command({'command_template':no},args,actual)
  double=list(template);double[2]='<INPUT_SHA256>'
  with self.assertRaisesRegex(m.Held,'command-template'):m.actual_command({'command_template':double},args,actual)
  moved=list(template);moved[8]=args.input_sha256;moved[2]='<INPUT_SHA256>'
  with self.assertRaisesRegex(m.Held,'command-template'):m.actual_command({'command_template':moved},args,actual)
  unknown=list(template);unknown[2]='<SOURCE_SHA256>'
  with self.assertRaisesRegex(m.Held,'command-template'):m.actual_command({'command_template':unknown},args,actual)
  duplicate=template[:3]+['--phase','execute']+template[3:]
  with self.assertRaisesRegex(m.Held,'command-prefix'):m.actual_command({'command_template':duplicate},args,[args.input_sha256 if x=='<INPUT_SHA256>' else x for x in duplicate])
  other=list(template);other[2]='/foreign/action.py'
  with self.assertRaisesRegex(m.Held,'command-prefix'):m.actual_command({'command_template':other},args,[args.input_sha256 if x=='<INPUT_SHA256>' else x for x in other])
class BirthRouteTests(unittest.TestCase):
 def test_same_exact_token_and_original_argv_passed(self):
  token=object();custody=object();events=[];args=SimpleNamespace(input='/private/actual.json',input_sha256='a'*64);plan=dict(nonce='b'*64,parent_sha256='c'*64);argv=['/lsiopy/bin/python3','-B','actual-provider','--input',args.input]
  def birth(*a,**kw):events.append(('birth',a,kw));return token
  def consume(value):self.assertIs(value,token);events.append('from-birth');return custody
  modules={'publication_native_scope_birth':SimpleNamespace(from_checked_parent=birth),'publication_reader_lifecycle':SimpleNamespace(from_birth=consume)}
  with patch.object(m.sys,'orig_argv',argv):self.assertIs(m.born_lifecycle(modules,args,plan),custody)
  self.assertEqual(events[0][1],(args.input,args.input_sha256,plan['nonce']));self.assertEqual(events[0][2],dict(parent_sha=plan['parent_sha256'],argv=argv));self.assertEqual(events[-1],'from-birth');self.assertEqual(argv,['/lsiopy/bin/python3','-B','actual-provider','--input',args.input])
 def test_birth_failure_never_calls_lifecycle(self):
  events=[];modules={'publication_native_scope_birth':SimpleNamespace(from_checked_parent=lambda *a,**kw:(_ for _ in ()).throw(m.Held('birth-unavailable'))),'publication_reader_lifecycle':SimpleNamespace(from_birth=lambda token:events.append('forbidden'))}
  with self.assertRaisesRegex(m.Held,'birth-unavailable'):m.born_lifecycle(modules,SimpleNamespace(input='p',input_sha256='a'*64),dict(nonce='b'*64,parent_sha256='c'*64))
  self.assertFalse(events)
 def test_no_fallback_to_old_reader_only_factory(self):
  old=[];modules={'publication_native_scope_birth':SimpleNamespace(from_checked_parent=lambda *a,**kw:object()),'publication_reader_lifecycle':SimpleNamespace(from_birth=lambda _:(_ for _ in ()).throw(m.Held('exact-birth-held')),from_checked_parent=lambda *a,**kw:old.append(True))}
  with self.assertRaisesRegex(m.Held,'exact-birth-held'):m.born_lifecycle(modules,SimpleNamespace(input='p',input_sha256='a'*64),dict(nonce='b'*64,parent_sha256='c'*64))
  self.assertFalse(old)

class SDKLoaderTests(unittest.TestCase):
 """Fresh -I/-B imports real temporary files; not installed SDK authority."""
 def test_fixed_image_bundled_path(self):
  self.assertEqual(m.LIB,Path('/app/mylar3/lib'))
 def run_isolated(self,mode):
  import subprocess
  import sys
  driver=r'''
import ast,hashlib,importlib.util,json,os,sys,tempfile
from pathlib import Path
assert sys.dont_write_bytecode
source=Path(sys.argv[1]);mode=sys.argv[2]
spec=importlib.util.spec_from_file_location('provider_fresh',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
assert not any(n=='mylar' or n.startswith('mylar.') or n=='bencode' for n in sys.modules)
with tempfile.TemporaryDirectory() as temp:
 root=Path(temp);app=root/'app';app.mkdir();sdk=app/'mylar';sdk.mkdir();lib=app/'lib';lib.mkdir()
 # Explicit fixture path substitution; no sys.modules mocks or preload.
 m.ROOT=sdk;m.LIB=lib
 names=next(ast.literal_eval(n.value) for f in ast.parse(source.read_text()).body if isinstance(f,ast.FunctionDef) and f.name=='sdk' for n in f.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='names' for x in n.targets))
 (sdk/'__init__.py').write_text('import bencode\nassert bencode.VALUE == "physical-bundled-import"\n')
 (lib/'bencode.py').write_text('VALUE="physical-bundled-import"\n')
 for name in names:(sdk/(name+'.py')).write_text('# physical fixture module\n')
 mapping={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sdk.iterdir()};control=root/'sdk-map.json';control.write_text(json.dumps(mapping));control.chmod(0o600)
 ref=dict(path=str(control),sha256=hashlib.sha256(control.read_bytes()).hexdigest())
 if mode=='missing':(lib/'bencode.py').unlink()
 if mode=='symlink':lib.rename(app/'foreign');lib.symlink_to(app/'foreign',target_is_directory=True)
 original_checked=m.checked;changed=[]
 def checked(ref,private=True):
  value=original_checked(ref,private)
  if mode=='first-source-ancestor' and Path(ref['path']).parent==sdk and not changed:
   sdk.chmod(0o700);changed.append(True)
  if mode=='map-ancestor' and Path(ref['path'])==control and not changed:
   root.chmod(0o750);changed.append(True)
  if mode=='map-leaf' and Path(ref['path'])==control and not changed:
   control.chmod(0o640);changed.append(True)
  return value
 m.checked=checked
 original=m.importlib.import_module;calls=[]
 def imported(name):
  result=original(name);calls.append(name)
  if name=='mylar.'+names[-1]:
   if mode=='late-sdk':(sdk/'publication_guard.py').chmod(0o600)
   if mode=='late-lib':lib.rename(app/'oldlib');lib.mkdir()
  return result
 m.importlib.import_module=imported
 try:
  modules,files,nodes=m.sdk(ref)
 except (m.Held,ModuleNotFoundError) as error:
  assert mode!='positive',(mode,str(error))
  if mode=='missing':assert isinstance(error,ModuleNotFoundError)
  else:assert isinstance(error,m.Held)
  if mode in ('first-source-ancestor','map-ancestor','map-leaf'):assert changed
  if mode in ('first-source-ancestor','map-ancestor'):assert str(error)=='action-sdk-ancestor-conflict',str(error)
  if mode=='map-leaf':assert str(error)=='action-sdk-terminal-CAS',str(error)
  print(json.dumps({'held':True,'mode':mode}));sys.exit(0)
 assert mode=='positive',mode
 assert Path(sys.modules['bencode'].__file__)==lib/'bencode.py'
 assert set(modules)==set(names) and lib in nodes
 print(json.dumps({'genuine_fresh_import':True,'bytecode_off':sys.dont_write_bytecode,'bundled_origin':str(Path(sys.modules['bencode'].__file__).relative_to(root))}))
'''
  result=subprocess.run([sys.executable,'-I','-B','-c',driver,str(P),mode],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
  return result.stdout
 def test_fresh_real_bundled_import(self):self.assertIn('genuine_fresh_import',self.run_isolated('positive'))
 def test_missing_bundled_dependency_refuses(self):self.assertIn('held',self.run_isolated('missing'))
 def test_symlink_bundled_directory_refuses(self):self.assertIn('held',self.run_isolated('symlink'))
 def test_first_source_ancestor_original_refuses(self):self.assertIn('held',self.run_isolated('first-source-ancestor'))
 def test_sdkmap_ancestor_original_refuses(self):self.assertIn('held',self.run_isolated('map-ancestor'))
 def test_sdkmap_leaf_original_refuses(self):self.assertIn('held',self.run_isolated('map-leaf'))
 def test_last_import_sdk_mode_mutation_refuses(self):self.assertIn('held',self.run_isolated('late-sdk'))
 def test_last_import_bundled_directory_replacement_refuses(self):self.assertIn('held',self.run_isolated('late-lib'))

if __name__=='__main__':unittest.main()
