"""Executable private consumer/schema/Tree controls; no engine or factories."""
import ast
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import test_fixture_transition as f
a=f.a
spec=importlib.util.spec_from_file_location('transition_parent',HERE/'comic_reader_lifecycle_parent.py');parent=importlib.util.module_from_spec(spec);spec.loader.exec_module(parent)
spec=importlib.util.spec_from_file_location('projection_fixture',f.CONFIG/'reader_recovery/comic_child_control_projection.py');projection=importlib.util.module_from_spec(spec);spec.loader.exec_module(projection)
saved=sys.modules.get('comic_archive_repair_action');sys.modules['comic_archive_repair_action']=a
spec=importlib.util.spec_from_file_location('transition_proof',HERE/'comic_archive_proof_producer.py');proof=importlib.util.module_from_spec(spec);spec.loader.exec_module(proof)
if saved is None:del sys.modules['comic_archive_repair_action']
else:sys.modules['comic_archive_repair_action']=saved

class Consumers(f.Tests):
 # Reuse disposable setup/helpers but do not collect inherited control methods.
 pass
for name in list(vars(f.Tests)):
 if name.startswith('test_'):setattr(Consumers,name,None)

class Checks(Consumers):
 def parent_plan(self,request):
  provider=self.root/'action-provider.py'
  raw=(HERE/'comic_archive_repair_action.py').read_bytes()
  if not provider.exists():
   with provider.open('xb') as stream:stream.write(raw)
   provider.chmod(0o600)
  self.assertEqual(provider.read_bytes(),raw)
  return dict(version=13,nonce=request['fixture_transition']['nonce'],provider=f.core.fact(provider,a.FIXTURE_LIMIT,self.deadline),reader=dict(id='c'*64),held_native=dict(id='b'*64),held_worker=dict(id='d'*64),selected_image='sha256:'+'e'*64)
 def test_actual_parent_original_fact_loader_no_engine(self):
  request,plan,bootstrap,catalog=self.originals();refs=parent.archive_fixture_inputs(self.parent_plan(request),request)
  self.assertEqual(refs,{role:request['fixture_transition'][role] for role in ('bootstrap','catalog')})
  for key in ('reader','held_native','held_worker'):
   bad=self.parent_plan(request);bad[key]['id']='0'*64
   with self.assertRaisesRegex(parent.Held,'archive-fixture-original-role-joins'):parent.archive_fixture_inputs(bad,request)
 def test_real_Tree_copies_two_originals_with_distinct_full9(self):
  request,plan,bootstrap,catalog=self.originals();root=self.root/'projection';operation=self.root/'operation';operation.mkdir(mode=0o700)
  tree=projection.Tree(root,root,operation,parent.read,uid=os.geteuid(),gid=os.getegid())
  result={role:tree.projected(ref) for role,ref in parent.archive_fixture_inputs(self.parent_plan(request),request).items()}
  tree.check();self.assertEqual(len(tree.pairs),2)
  self.assertEqual(a.fixture_originals(dict(fixture_originals=result),request)[0]['path'],self.source.as_posix())
  for role in result:
   self.assertEqual(result[role]['sha256'],request['fixture_transition'][role]['sha256']);self.assertNotEqual(result[role]['signature9'][:2],request['fixture_transition'][role]['signature9'][:2])
 def input(self,version):
  request,projection_plan,bootstrap,catalog=self.originals();source=HERE/'comic_archive_repair_action.py';source_sha=hashlib.sha256(source.read_bytes()).hexdigest();input_path=str(self.root/'input.json');input_sha='a'*64
  command=['/lsiopy/bin/python3','-I','-B',str(source),'--phase','execute','--input',input_path,'--input-sha256','<INPUT_SHA256>','--source-sha256',source_sha]
  args=types.SimpleNamespace(phase='execute',input=input_path,input_sha256=input_sha,source_sha256=source_sha)
  plan=dict(version=version,action='archive-one',command_template=command,operation=str(self.root/'operation'),sdk_map=self.control,nonce='a'*64,parent_sha256='b'*64,selected_image='sha256:'+'e'*64,controls={role:self.control for role in a.ROLES},archive_scopes=self.control,owner=request['owner'],operation_id=request['operation_id'],terminal='forward',publication_protocol='rename-link-v1',terminal_mode='same-child-v1')
  if version==4:plan['fixture_originals']=projection_plan['fixture_originals']
  return plan,args,[input_sha if v=='<INPUT_SHA256>' else v for v in command]
 def test_child_input_v4_exact_v3_unchanged(self):
  plan,args,command=self.input(4);self.assertEqual(a.validate_plan(plan,args,command),plan)
  bad=copy.deepcopy(plan);bad['version']=3
  with self.assertRaisesRegex(a.Held,'repair-exact-action-input'):a.validate_plan(bad,args,command)
  del bad['fixture_originals'];self.assertEqual(a.validate_plan(bad,args,command),bad)
  bad=copy.deepcopy(plan);del bad['fixture_originals']
  with self.assertRaisesRegex(a.Held,'repair-exact-action-input'):a.validate_plan(bad,args,command)
 def terminal(self):
  request,plan,bootstrap,catalog=self.originals()
  native_state=dict(Running=True,Status='running',Pid=42,StartedAt='fixture-epoch',Paused=False,Restarting=False,Dead=False,OOMKilled=False)
  worker_state=dict(Running=False,Status='created',Pid=0,StartedAt='',Paused=False,Restarting=False,Dead=False,OOMKilled=False)
  reader=dict(Id='c'*64,State=dict(Running=False,Pid=0,Status='exited'))
  meta=dict(version=1,kind='causal-stopped-fixture-directory-marker',nonce='a'*64,fixture_nonce='a'*64,operation_id=request['operation_id'],owner=request['owner'],bootstrap=request['fixture_transition']['bootstrap'],catalog=request['fixture_transition']['catalog'],catalog_observed=dict(owner=dict(path=str(self.source))),reader_stopped=reader,native_epoch=native_state,worker_epoch=worker_state,deadline_monotonic=self.deadline,equivalence=self.evidence)
  outcome=a._fixture_replace(self.source,self.raw,self.candidate,self.fact,self.stage,f.core,self.guard,meta,f.MODULES)
  receipt=a.decode(a.checked(outcome.receipt)[0]);a.fixture_provenance(receipt,request)
  preparation=dict(source=receipt['source_after'],exceptional_witness=dict(virtual_original_inventory=self.evidence['inventory'],root_metadata_sha256=self.evidence['root_metadata_sha256']),derivative=dict(sha256=request['fixture_transition']['genesis']['sha256']),catalog=receipt['catalog_observed'])
  original=dict(version=2,kind='archive-one-original-custody',owner=request['owner'],operation_id=request['operation_id'],baseline=self.control,preparation=self.control,preparation_directory9=a.nine(self.root.stat()),reader={},publication_acceptance=False,mutation_authority=False,fixture_transition=outcome.receipt)
  native=dict(native=dict(inspect=dict(State=native_state)),worker=dict(State=worker_state));vectors=outcome.vectors();files={path:tuple(value) for path,value in vectors['files']};names={path:tuple(value) for path,value in vectors['censuses']}
  return request,original,receipt,preparation,reader,native,files,names
 def test_actual_Parent_terminal_v2_accepts_complete_causal_vectors(self):
  values=self.terminal();request,original,receipt,preparation,reader,native,files,names=values
  parent.archive_fixture_terminal(a,request,original,receipt,preparation,reader,native,str(self.stage),files,names)
  self.assertFalse(receipt['publication_acceptance']);self.assertFalse(receipt['mutation_authority'])
 def test_terminal_v2_wrong_receipt_or_preparation_refuses(self):
  request,original,receipt,preparation,reader,native,files,names=self.terminal()
  for field in ('bootstrap','catalog','source_before'):
   bad=copy.deepcopy(receipt);bad[field]=self.control
   with self.assertRaises(a.Held):parent.archive_fixture_terminal(a,request,original,bad,preparation,reader,native,str(self.stage),files,names)
  bad=copy.deepcopy(preparation);bad['derivative']['sha256']='0'*64
  with self.assertRaisesRegex(parent.Held,'archive-fixture-owning-preparation-join'):parent.archive_fixture_terminal(a,request,original,receipt,bad,reader,native,str(self.stage),files,names)
 def test_terminal_missing_copy_or_foreign_epoch_refuses(self):
  request,original,receipt,preparation,reader,native,files,names=self.terminal();bad=dict(files);del bad[receipt['genesis']['path']]
  with self.assertRaisesRegex(parent.Held,'archive-fixture-retained-original-vectors'):parent.archive_fixture_terminal(a,request,original,receipt,preparation,reader,native,str(self.stage),bad,names)
  bad=copy.deepcopy(native);bad['native']['inspect']['State']['StartedAt']='foreign'
  with self.assertRaisesRegex(parent.Held,'archive-fixture-original-native-worker-epochs'):parent.archive_fixture_terminal(a,request,original,receipt,preparation,reader,bad,str(self.stage),files,names)
 def test_actual_Parent_phase_branch_emits_v4_using_real_Tree(self):
  request,plan,bootstrap,catalog=self.originals();tree_root=self.root/'phase-tree';operation=self.root/'op';operation.mkdir(mode=0o700)
  tree=projection.Tree(tree_root,tree_root,operation,parent.read,uid=os.geteuid(),gid=os.getegid())
  owner=types.SimpleNamespace(plan=self.parent_plan(request),mapping=types.SimpleNamespace(child_ref=tree.projected))
  text=(HERE/'comic_reader_lifecycle_parent.py').read_text();parsed=ast.parse(text);cls=next(n for n in parsed.body if isinstance(n,ast.ClassDef) and n.name=='LifecycleParent');method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='archive_phase_input')
  branch=next(n for n in method.body if isinstance(n,ast.If) and 'self.plan.get' in ast.unparse(n.test) and 'execute' in ast.unparse(n.test))
  value={};scope=dict(self=owner,phase='execute',value=value,request=request,archive_fixture_inputs=parent.archive_fixture_inputs)
  exec(compile(ast.Module(body=[branch],type_ignores=[]),str(HERE/'comic_reader_lifecycle_parent.py'),'exec'),scope)
  self.assertEqual(value['version'],4);self.assertEqual(value['publication_protocol'],'rename-link-v1');a.fixture_originals(value,request);tree.check()
 def test_Root_identity_retained_originals_real_read_Tree_and_Originals(self):
  request,plan,bootstrap,catalog=self.originals();request_ref=a.write(self.root/'request-root-model.json',request)
  parent_plan=self.parent_plan(request);parent_plan.update(action='archive-one',producer_inputs=dict(archive_request=request_ref))
  # Model only Root's identity and TWO genuinely Root-owned controls. Actual
  # Bootstrap/catalog files remain real UID1000/full9 bytes throughout. No read,
  # loader, Original/Tree guard or reference validator is replaced.
  root_ids={tuple(ref['signature9'][:2]) for ref in (parent_plan['provider'],request_ref)}
  for ref in (parent_plan['provider'],request_ref):ref['signature9']=list(ref['signature9']);ref['signature9'][6:8]=[0,0]
  class RootReadOS:
   def __getattr__(self,name):return getattr(os,name)
   def geteuid(self):return 0
   def getegid(self):return 0
   def model(self,z):
    if (z.st_dev,z.st_ino) not in root_ids:return z
    return types.SimpleNamespace(**{name:(0 if name in ('st_uid','st_gid') else getattr(z,name)) for name in dir(z) if name.startswith('st_')})
   def lstat(self,path):return self.model(os.lstat(path))
   def fstat(self,fd):return self.model(os.fstat(fd))
  model=RootReadOS();operation=self.root/'root-model-operation';operation.mkdir(mode=0o700);tree_root=self.root/'root-model-tree'
  owner=types.SimpleNamespace(plan=parent_plan);reader=types.MethodType(parent.LifecycleParent.read_child_original,owner)
  with patch.object(parent,'os',model),patch.object(a,'os',model),patch.object(proof,'os',model):
   refs=parent.archive_fixture_inputs(parent_plan,request)
   self.assertEqual(reader(parent_plan['provider']),(HERE/'comic_archive_repair_action.py').read_bytes())
   with self.assertRaisesRegex(parent.Held,'ref-attributes'):parent.read(refs['bootstrap'])
   tree=projection.Tree(tree_root,tree_root,operation,reader,uid=os.geteuid(),gid=os.getegid())
   copied={role:tree.projected(ref) for role,ref in refs.items()};tree.check();self.assertEqual(len(tree.pairs),2)
   originals=proof.Originals([ref['path'] for ref in refs.values()])
   with self.assertRaisesRegex(a.Held,'action-control'):originals.ref(refs['bootstrap'])
   for role in ('bootstrap','catalog'):self.assertIsInstance(proof.fixture_source_ref(originals,request,role),dict)
   proof.close(originals.frozen())
   foreign=self.root/'foreign-user.json';foreign.write_bytes(b'{}');foreign.chmod(0o600);foreign_ref=f.core.fact(foreign,a.FIXTURE_LIMIT,self.deadline)
   with self.assertRaisesRegex(parent.Held,'ref-attributes'):reader(foreign_ref)
   with self.assertRaisesRegex(a.Held,'archive-producer-fixture-retained-role'):proof.fixture_source_ref(originals,request,'other')
  self.assertEqual(set(copied),{'bootstrap','catalog'})
 def test_source_branches_wire_v4_and_preserve_legacy_algorithm(self):
  # Function-source extraction tests the new proof's actual join branch, rather
  # than a copied implementation or a whole-schema expectation mirror.
  text=(HERE/'comic_archive_proof_producer.py').read_text();tree=ast.parse(text);function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='phase_custody')
  branch=next(n for n in function.body if isinstance(n,ast.If) and ast.unparse(n.test)=="owner['version'] == 3")
  request,plan,bootstrap,catalog=self.originals();input_doc=dict(fixture_originals=plan['fixture_originals']);expected_input=set();seen=[]
  originals=types.SimpleNamespace(admit=lambda value:seen.append(('admit',value)),ref=lambda value,**kwargs:seen.append(('ref',value)))
  scope=dict(owner=request,input_doc=input_doc,expected_input=expected_input,refchild=lambda ref:plan['fixture_originals']['bootstrap' if ref==request['fixture_transition']['bootstrap'] else 'catalog'],same=lambda x,y:x==y,need=parent.need,o=originals,fixture_source_ref=proof.fixture_source_ref)
  exec(compile(ast.Module(body=[branch],type_ignores=[]),str(HERE/'comic_archive_proof_producer.py'),'exec'),scope)
  self.assertIn('fixture_originals',expected_input);self.assertEqual(len(seen),4)
  scope['input_doc']=dict(fixture_originals={})
  with self.assertRaisesRegex(parent.Held,'archive-producer-fixture-original-projection'):exec(compile(ast.Module(body=[branch],type_ignores=[]),str(HERE/'comic_archive_proof_producer.py'),'exec'),scope)
  # Exercise the maintained guards themselves: the legacy route still accepts
  # ONLY request1, while v13 explicitly admits each finite request schema.
  text=(HERE/'comic_nfs_factual_successor.py').read_text();module=ast.parse(text)
  # Complete reviewed legacy algorithm bytes, permitting ONLY the explicit
  # owner-read metadata call substitutions introduced by this integration.
  legacy_hashes={'nfs_ready_archive':'faf7e8e6580f92b98bf7bf604c392b5461f7bf44fa1572cd2af96058b7955405','nfs_ready':'9eb978299335e18393cd356f71f4588861cdd41111a17223aebfb7de18830ee2'}
  for name,digest in legacy_hashes.items():
   function=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name==name)
   body=ast.get_source_segment(text,function)
   body=body.replace('_host_names(owner, p)','os.listdir(p)').replace('_host_stat(owner, p)','os.lstat(p)')
   self.assertEqual(hashlib.sha256(body.encode()).hexdigest(),digest)
  def schema(name):
   function=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name==name)
   statement=next(n for n in function.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and any(isinstance(x,ast.Constant) and x.value=='archive-nfs-original-owner-request' for x in n.value.args))
   return compile(ast.Module(body=[statement],type_ignores=[]),str(HERE/'comic_nfs_factual_successor.py'),'exec')
  legacy=schema('nfs_ready_archive');successor=schema('nfs_ready_archive_v13')
  v1={k:request[k] for k in ('version','owner','operation_id')};v1['version']=1
  v2=dict(v1,version=2,terminal='forward')
  for original in (v1,v2,request):
   exec(successor,dict(original=original,need=parent.need))
  exec(legacy,dict(original=v1,need=parent.need))
  for original in (v2,request,dict(v1,extra=True),dict(v1,version=True)):
   with self.assertRaisesRegex(parent.Held,'archive-nfs-original-owner-request'):exec(legacy,dict(original=original,need=parent.need))
  for original in (dict(v2,terminal='unknown'),dict(request,extra=True),dict(request,version=True),{k:v for k,v in request.items() if k!='fixture_transition'}):
   with self.assertRaisesRegex(parent.Held,'archive-nfs-original-owner-request'):exec(successor,dict(original=original,need=parent.need))


if __name__=='__main__':unittest.main()
