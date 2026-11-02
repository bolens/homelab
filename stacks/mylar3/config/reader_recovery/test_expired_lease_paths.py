"""Actual Paths + real projection/file tapes; Parent constructor remains projected."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import hashlib,os,tempfile,threading,unittest
import comic_nfs_host_lease as h
import comic_child_control_projection as projection
import comic_reader_lifecycle_parent as parent
class Owner:pass
class Expired(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);base=Path(self.tmp.name);op=base/'original';op.mkdir(mode=0o700);helper=op/'helper.py';helper.write_bytes(b'# exact retained public helper\n');helper.chmod(0o600)
  ref=dict(path=str(helper),sha256=hashlib.sha256(helper.read_bytes()).hexdigest(),signature9=list(h.nine(helper.lstat())))
  tree=projection.Tree(base/'child',Path('/_operation'),op,lambda r:parent.read(r),uid=os.geteuid(),gid=os.getegid());virtual=tree.projected(ref);physical=dict(virtual,path=tree.host(virtual['path']))
  empty=base/'empty';empty.mkdir(mode=0o700);writer=base/'writer';writer.mkdir(mode=0o700);lock=writer/'writer-v1.lock';lock.write_bytes(b'');lock.chmod(0o600)
  owner=Owner();owner.thread=threading.get_ident();owner.core=b'original-method-only-core';owner.mapping=parent.Paths([]) if False else parent.Paths([dict(host=str(base),child='/fixture',write=False)]);owner.mapping.owner=owner
  def expired():raise ValueError('actual-expired-Paths-owner')
  owner.left=expired;parent._CHILD_TREES[owner]=tree
  lease=object.__new__(h.HostWriterLease);lease.owner=owner;lease.g={'read':parent.read,'_CORES':{owner:owner.core},'_CHILD_TREES':parent._CHILD_TREES};lease.tree=tree;lease.helper=ref;lease.projected=physical;lease.admitted_empty=dict(path=str(empty),signature9=list(h.nine(empty.lstat())));lease.empty=str(empty);lease.empty9=tuple(h.nine(empty.lstat()));lease.empty_nodes=tuple((str(q),h.five(q.lstat())) for q in empty.parents);lease.root=writer;lease.root5,lease.writer_files=h.namespace(writer);lease.writer_nodes=tuple((str(q),h.five(q.lstat())) for q in writer.parents);lease.writer_sha='c'*64;lease.image='source-method-projection';lease.token='a'*64;lease.name='fixture';lease.mounts=();lease.command=();lease.create_args=()
  lease.tape=h.encode(dict(helper=lease.helper,projected=lease.projected,empty=lease.empty,empty9=lease.empty9,empty_nodes=lease.empty_nodes,writer_original=(lease.root5,lease.writer_files,lease.writer_nodes),root=str(lease.root),writer_sha=lease.writer_sha,image=lease.image,token=lease.token,name=lease.name,mounts=lease.mounts,command=lease.command,create=lease.create_args));self.lease=lease
 def test_actual_paths_expired_refuses_active_but_local_original_closure_succeeds(self):
  with self.assertRaisesRegex(ValueError,'actual-expired-Paths-owner'):self.lease.owner.mapping.child_host_ref(self.lease.helper)
  with self.assertRaisesRegex(parent.Held,'nfs-empty-original-unbound'):self.lease.owner.mapping.check_nfs_empty(self.lease.admitted_empty)
  self.lease.original(allow_expired=True)
 def test_expired_local_closure_still_refuses_original_empty_mode_drift(self):
  Path(self.lease.empty).chmod(0o750)
  with self.assertRaisesRegex(h.Held,'lease-projection-originals'):self.lease.original(allow_expired=True)
 def normal(self):
  self.lease.owner.left=lambda:1;self.lease.admitted_empty=None
  self.addCleanup(parent._CHILD_TREES.pop,self.lease.owner,None)
 def test_retained_helper_closes_tree_twice_without_reprojection(self):
  from unittest.mock import patch
  self.normal();tree=self.lease.tree;calls=[];original=tree.check
  def check():calls.append(True);return original()
  with patch.object(tree,'check',side_effect=check),patch.object(self.lease.owner.mapping,'child_host_ref',side_effect=AssertionError('retained pair must not reenter projection')):
   self.lease.original()
  self.assertEqual(len(calls),2)
 def test_late_registered_tree_replacement_refuses(self):
  from unittest.mock import patch
  self.normal();original=h.namespace
  def namespace(path):
   result=original(path);parent._CHILD_TREES[self.lease.owner]=object();return result
  with patch.object(h,'namespace',side_effect=namespace):
   with self.assertRaises((h.Held,projection.Held,parent.Held)):self.lease.original()
 def test_late_retained_pair_substitution_refuses(self):
  from unittest.mock import patch
  self.normal();original=h.namespace
  def namespace(path):
   result=original(path);self.lease.tree.pairs=();return result
  with patch.object(h,'namespace',side_effect=namespace):
   with self.assertRaises((h.Held,projection.Held,parent.Held)):self.lease.original()
 def test_late_original_source_mutation_refuses(self):
  from unittest.mock import patch
  self.normal();original=h.namespace
  def namespace(path):
   result=original(path);Path(self.lease.helper['path']).write_bytes(b'# changed retained original\n');return result
  with patch.object(h,'namespace',side_effect=namespace):
   with self.assertRaises((h.Held,projection.Held,parent.Held)):self.lease.original()
class AdmittedEmpty(unittest.TestCase):
 """Actual Paths/session/Parent/lease closure; session construction is projected."""
 def setUp(self):
  import test_nfs_stopped_handoff as stopped
  Expired.setUp(self);self.original_owner=self.lease.owner
  session,self.calls,_=stopped.SessionClose.session(self);owner=session.owner
  import importlib.util
  # Execute exact private-copy bytes under their actual origin, without changing
  # an installed/public module's origin or weakening the private source policy.
  path=Path(self.tmp.name)/'session.py';path.write_bytes(Path(stopped.S.__file__).read_bytes());path.chmod(0o600)
  spec=importlib.util.spec_from_file_location('_admitted_session_fixture',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  sys.modules[module.__name__]=module;self.addCleanup(sys.modules.pop,module.__name__,None)
  original=session;session=object.__new__(module.RetainedChild);session.__dict__.update(original.__dict__)
  module._SESSION_SEALS[session]=stopped.S._SESSION_SEALS[original]
  self.session=session;self.stopped=stopped
  owner.mapping=parent.Paths([dict(host=str(Path(self.lease.empty).parent),child='/fixture',write=False)]);owner.mapping.owner=owner
  parent._CHILD_TREES[owner]=self.lease.tree
  parent._CONFIGURED_OVERLAYS[owner]=parent._CONFIGURED_OVERLAY_SEALS[owner]=();parent._CONFIGURED_IMAGE_LABELS[owner]=parent._CONFIGURED_IMAGE_SEALS[owner]=()
  ref=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=parent.nine(path.stat()))
  refs={'comic_nfs_parent_session.py':ref};raws={next(iter(refs)):parent.read(ref,private=False)}
  parent._NFS_SOURCE_CONTEXTS[owner]=(refs,raws,parent.encode({}),parent.encode({}),'/fixture')
  parent._NFS_SOURCE_SEALS[owner]=parent.encode(dict(refs=refs,raw_sha={k:hashlib.sha256(v).hexdigest() for k,v in raws.items()},active={},probe={},output='/fixture',effective_absences=[]))
  method=module.RetainedChild.close
  modules={'comic_nfs_parent_session.py':module};entry=('comic_nfs_parent_session.py',module,module.__name__,((module.RetainedChild,'close',method,method.__code__,method.__defaults__,method.__kwdefaults__),))
  parent._NFS_HOST_MODULES[owner]=modules;parent._NFS_HOST_MODULE_SEALS[owner]=(tuple(modules.items()),(entry,))
  parent._NFS_LIVE_SESSIONS[owner]=session;session.original_pid=os.getpid()
  self.row=('/_operation/empty',self.lease.empty,self.lease.empty9,tuple(parent.parents(Path(self.lease.empty)).items()),session,session.cid,session.original_pid,owner.plan['nonce'])
  parent._NFS_EMPTY_ROWS[owner]=self.row
  self.lease.owner=owner;self.lease.g=parent.__dict__
  guard=parent.none_network_profile_contract;checker=parent.Paths.check_nfs_empty
  h._PROFILE_CONTRACTS[self.lease]=(guard,guard.__code__,guard(),(owner.mapping,parent.Paths,checker,checker.__code__,checker.__defaults__))
  for registry in (parent._NFS_EMPTY_ROWS,parent._NFS_LIVE_SESSIONS,parent._NFS_HOST_MODULES,parent._NFS_HOST_MODULE_SEALS,parent._NFS_SOURCE_CONTEXTS,parent._NFS_SOURCE_SEALS,parent._NFS_EFFECTIVE_ABSENCES,parent._CHILD_TREES,parent._CORES,parent._GENERATED):self.addCleanup(registry.pop,owner,None)
  self.addCleanup(h._PROFILE_CONTRACTS.pop,self.lease,None)
  self.addCleanup(parent._CHILD_TREES.pop,self.original_owner,None)
 def test_original_uses_one_full_parent_closure_and_two_tree_closures(self):
  from unittest.mock import patch,Mock
  self.lease.empty_contract=Mock(side_effect=AssertionError('removed helper must not be called'))
  with patch.object(self.lease.tree,'check',wraps=self.lease.tree.check) as check:self.lease.original()
  self.lease.empty_contract.assert_not_called()
  self.assertEqual(len(self.calls),1);self.assertEqual(check.call_count,3)
 def test_expired_parent_still_refuses_admitted_empty(self):
  from unittest.mock import patch
  with patch.object(parent.time,'monotonic',return_value=self.lease.owner.deadline+1):
   with self.assertRaisesRegex(parent.Held,'parent-lifetime'):self.lease.original()
 def test_reply_uses_two_parent_closures_and_keeps_each_pulse(self):
  from types import SimpleNamespace
  from unittest.mock import Mock
  import comic_nfs_lease_session as replies_module
  channel=object.__new__(h.LeaseChannel);channel.process=object();channel.check=Mock();channel.pulse=Mock(return_value=dict(held=True))
  lease=self.lease;lease.channel=channel;lease.process=channel.process;lease.cid=lease.cid_original='c'*64;lease.epoch=(os.getpid(),'projected-ACK');lease.runtime_pid=os.getpid();lease.runtime_ticks=h.ticks(os.getpid())
  h._WINDOWS[lease]=('HELD',(lease.cid_original,lease.process,channel,lease.epoch,lease.runtime_pid,lease.runtime_ticks));self.addCleanup(h._WINDOWS.pop,lease,None)
  dialogue=SimpleNamespace(close=Mock(),nonce='a'*64,sequence=0)
  replies=object.__new__(replies_module.HostLeaseReplies);replies.dialogue=dialogue;replies.lease=lease;replies.absent=replies.absence_tape=('/owned/child','/owned');replies.done=False
  frame=dict(type='nfs-lease',nonce=dialogue.nonce,sequence=1,payload=dict(operation='pulse',absent=[],empty=None))
  raw=replies.accept(frame)
  self.assertEqual(len(self.calls),2);self.assertEqual(dialogue.close.call_count,3)
  self.assertEqual(replies_module.json.loads(raw)['sequence'],1);channel.pulse.assert_called_once_with();self.assertEqual(channel.check.call_count,2)
 def test_missing_contract_refuses_without_falling_back(self):
  h._PROFILE_CONTRACTS.pop(self.lease)
  with self.assertRaisesRegex(h.Held,'original-empty-contract'):self.lease.original()
  self.assertEqual(self.calls,[])
 def test_mapping_instance_and_class_replacement_refuse_before_parent(self):
  from unittest.mock import patch
  mapping=self.lease.owner.mapping
  for target in (mapping,parent.Paths):
   with self.subTest(target=type(target).__name__),patch.object(target,'check_nfs_empty',lambda *a: self.lease.admitted_empty):
    with self.assertRaisesRegex(h.Held,'original-empty-checker'):self.lease.original()
  self.assertEqual(self.calls,[])
 def test_mapping_code_and_defaults_replacement_refuse(self):
  method=parent.Paths.check_nfs_empty;code=method.__code__;defaults=method.__defaults__
  try:
   method.__code__=(lambda self,value:value).__code__
   with self.assertRaisesRegex(h.Held,'original-empty-checker'):self.lease.original()
   method.__code__=code;method.__defaults__=(None,)
   with self.assertRaisesRegex(h.Held,'original-empty-checker'):self.lease.original()
  finally:method.__code__=code;method.__defaults__=defaults
  self.assertEqual(self.calls,[])
 def test_session_instance_and_code_replacement_refuse(self):
  from unittest.mock import patch
  for target in (self.session,type(self.session)):
   with self.subTest(target=type(target).__name__),patch.object(target,'close',lambda *a:None):
    with self.assertRaisesRegex(parent.Held,'original-session-checker'):self.lease.original()
  method=type(self.session).close;code=method.__code__
  try:
   method.__code__=(lambda self:None).__code__
   with self.assertRaisesRegex(parent.Held,'original-session-checker'):self.lease.original()
  finally:method.__code__=code
  self.assertEqual(self.calls,[])
 def test_late_row_and_live_session_replacement_refuse(self):
  from unittest.mock import patch
  original=parent.nfs_names;owner=self.lease.owner
  for registry,replacement in ((parent._NFS_EMPTY_ROWS,tuple(list(self.row))),(parent._NFS_LIVE_SESSIONS,object())):
   def names(path):
    result=original(path);registry[owner]=replacement;return result
   with self.subTest(registry=id(registry)),patch.object(parent,'nfs_names',side_effect=names):
    with self.assertRaisesRegex(parent.Held,'original-session-checker'):self.lease.original()
   parent._NFS_EMPTY_ROWS[owner]=self.row;parent._NFS_LIVE_SESSIONS[owner]=self.session
 def test_late_contract_replacement_refuses(self):
  from unittest.mock import patch
  original=parent.nfs_names;contract=h._PROFILE_CONTRACTS[self.lease]
  def names(path):
   result=original(path);h._PROFILE_CONTRACTS[self.lease]=tuple(list(contract));return result
  with patch.object(parent,'nfs_names',side_effect=names):
   with self.assertRaisesRegex(h.Held,'original-empty-contract'):self.lease.original()
 def mutate_late(self,mutate):
  from unittest.mock import patch
  original=h.namespace
  def namespace(path):
   result=original(path);mutate();return result
  with patch.object(h,'namespace',side_effect=namespace):
   with self.assertRaises((h.Held,parent.Held,projection.Held)):self.lease.original()
 def test_late_empty_mutation_refuses(self):self.mutate_late(lambda:Path(self.lease.empty).chmod(0o750))
 def test_late_helper_mutation_refuses(self):self.mutate_late(lambda:Path(self.lease.helper['path']).write_bytes(b'changed'))
 def test_late_pair_mutation_refuses(self):self.mutate_late(lambda:setattr(self.lease.tree,'pairs',()))
class LeaseReplyClosure(unittest.TestCase):
 """Actual lease/Tree originals; dialogue and pulse result are projected."""
 def setUp(self):
  from types import SimpleNamespace
  from unittest.mock import Mock
  import comic_nfs_lease_session as session
  Expired.setUp(self);self.lease.owner.left=lambda:1;self.lease.admitted_empty=None
  self.addCleanup(parent._CHILD_TREES.pop,self.lease.owner,None)
  self.session=session;self.pulse=Mock(return_value=dict(held=True))
  self.channel=object.__new__(h.LeaseChannel);self.channel.process=object();self.channel.check=Mock();self.channel.pulse=self.pulse
  self.lease.channel=self.channel;self.lease.process=self.channel.process;self.lease.cid=self.lease.cid_original='c'*64;self.lease.epoch=(os.getpid(),'projected-channel-ACK');self.lease.runtime_pid=os.getpid();self.lease.runtime_ticks=h.ticks(os.getpid())
  h._WINDOWS[self.lease]=('HELD',(self.lease.cid_original,self.lease.process,self.channel,self.lease.epoch,self.lease.runtime_pid,self.lease.runtime_ticks));self.addCleanup(h._WINDOWS.pop,self.lease,None)
  self.dialogue=SimpleNamespace(close=Mock(),nonce='a'*64,sequence=0)
  self.replies=object.__new__(session.HostLeaseReplies);self.replies.dialogue=self.dialogue;self.replies.lease=self.lease
  self.replies.absent=self.replies.absence_tape=('/owned/child','/owned');self.replies.done=False
  self.frame=dict(type='nfs-lease',nonce=self.dialogue.nonce,sequence=1,payload=dict(operation='pulse',absent=[],empty=None))
 def test_reply_closes_originals_before_verb_and_after_encoding(self):
  from unittest.mock import patch
  with patch.object(self.lease,'original',wraps=self.lease.original) as original:
   raw=self.replies.accept(self.frame)
  self.assertEqual(original.call_count,2);self.assertEqual(self.dialogue.close.call_count,3)
  self.assertEqual(self.dialogue.sequence,1);self.assertEqual(self.session.json.loads(raw)['sequence'],1);self.pulse.assert_called_once_with()
 def test_encoding_source_drift_refuses_before_returning_ack(self):
  from unittest.mock import patch
  original=self.session.encode
  def encode(value):
   Path(self.lease.helper['path']).write_bytes(b'# changed while encoding reply\n');return original(value)
  with patch.object(self.session,'encode',side_effect=encode):
   with self.assertRaises((h.Held,projection.Held,parent.Held)):self.replies.accept(self.frame)
  self.assertEqual(self.dialogue.sequence,1);self.pulse.assert_called_once_with()
 def test_final_dialogue_pair_drift_refuses_before_returning_ack(self):
  calls=[]
  def close():
   calls.append(True)
   if len(calls)==3:self.lease.tree.pairs=()
  self.dialogue.close=close
  with self.assertRaises((h.Held,projection.Held,parent.Held)):self.replies.accept(self.frame)
  self.assertEqual(self.dialogue.sequence,1);self.pulse.assert_called_once_with()
 def test_replayed_sequence_refuses_before_second_verb(self):
  self.replies.accept(self.frame)
  with self.assertRaisesRegex(self.session.Held,'original-frame'):self.replies.accept(self.frame)
  self.pulse.assert_called_once_with();self.assertEqual(self.dialogue.sequence,1)
 def test_owned_reply_uses_two_full_originals_and_real_inner_ticks(self):
  from unittest.mock import patch
  with patch.object(self.lease,'original',wraps=self.lease.original) as original,patch.object(h,'ticks',wraps=h.ticks) as ticks:
   self.replies.accept(self.frame)
  self.assertEqual(original.call_count,2);self.assertEqual(ticks.call_count,2);self.assertEqual(self.channel.check.call_count,2)
 def test_public_pulse_keeps_its_full_original_bracket(self):
  from unittest.mock import patch
  with patch.object(self.lease,'original',wraps=self.lease.original) as original:
   self.assertEqual(self.lease.pulse(),dict(held=True))
  self.assertEqual(original.call_count,2);self.pulse.assert_called_once_with()
 def test_foreign_window_refuses_before_heartbeat(self):
  self.lease.cid='d'*64
  with self.assertRaisesRegex(h.Held,'pulse-original-window-seal'):self.replies.accept(self.frame)
  self.pulse.assert_not_called()
 def test_foreign_pipe_refuses_before_heartbeat(self):
  self.channel.check.side_effect=h.Held('projected-original-FD-refusal')
  with self.assertRaisesRegex(h.Held,'original-FD-refusal'):self.replies.accept(self.frame)
  self.pulse.assert_not_called()
 def test_post_ACK_window_substitution_refuses(self):
  def changed():self.lease.cid='d'*64;return dict(held=True)
  self.pulse.side_effect=changed
  with self.assertRaisesRegex(h.Held,'pulse-original-window-seal'):self.replies.accept(self.frame)
  self.pulse.assert_called_once_with()
 def test_post_ACK_inner_process_substitution_refuses(self):
  from unittest.mock import patch
  with patch.object(h,'ticks',side_effect=[self.lease.runtime_ticks,self.lease.runtime_ticks+1]):
   with self.assertRaisesRegex(h.Held,'pulse-original-inner-process'):self.replies.accept(self.frame)
 def test_explicit_foreign_primitive_override_refuses_before_heartbeat(self):
  def foreign(lease):return dict(held=True)
  with self.assertRaises(TypeError):
   self.replies.accept(self.frame,foreign,foreign.__code__)
  self.pulse.assert_not_called()
 def test_final_encoding_primitive_replacement_refuses(self):
  from unittest.mock import patch
  original=self.session.encode
  def foreign(lease):return dict(held=True)
  def encode(value):
   h.HostWriterLease._pulse_owned=foreign;return original(value)
  with patch.object(h.HostWriterLease,'_pulse_owned',h.HostWriterLease._pulse_owned),patch.object(self.session,'encode',side_effect=encode):
   with self.assertRaisesRegex(self.session.Held,'final-owned-pulse'):self.replies.accept(self.frame)
 def test_instance_primitive_override_refuses_before_heartbeat(self):
  self.lease._pulse_owned=lambda:dict(held=True)
  with self.assertRaisesRegex(self.session.Held,'original-owned-pulse'):self.replies.accept(self.frame)
  self.pulse.assert_not_called()
 def test_child_source_exec_requires_no_host_module_import(self):
  from unittest.mock import patch
  import builtins
  raw=Path(self.session.__file__).read_bytes();actual=builtins.__import__;imports=[]
  def guarded(name,*args,**kwargs):
   if name.startswith('comic_nfs_host_'):imports.append(name);raise ImportError('host imports forbidden in actual child source exec')
   return actual(name,*args,**kwargs)
  namespace=dict(__name__='owning_nfs_host_lease_interface',__file__=self.session.__file__)
  with patch.object(builtins,'__import__',side_effect=guarded):exec(compile(raw,self.session.__file__,'exec'),namespace)
  self.assertTrue(isinstance(namespace['ChildLeaseInterface'],type));self.assertEqual(imports,[])
 def test_final_public_pulse_default_replacement_refuses(self):
  from unittest.mock import patch
  original=self.session.encode;defaults=h.HostWriterLease.pulse.__defaults__
  def foreign(lease):return dict(held=True)
  def encode(value):
   h.HostWriterLease.pulse.__defaults__=(foreign,foreign.__code__);return original(value)
  with patch.object(h.HostWriterLease.pulse,'__defaults__',defaults),patch.object(self.session,'encode',side_effect=encode):
   with self.assertRaisesRegex(self.session.Held,'final-owned-pulse'):self.replies.accept(self.frame)
if __name__=='__main__':unittest.main()
