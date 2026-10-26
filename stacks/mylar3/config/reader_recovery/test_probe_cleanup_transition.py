"""Actual Paths/end methods, original files/dirs/Popen; kernel/lease prerequisites
are explicit source-method projections, not installed/NFS/terminal authority.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import importlib.util,hashlib,os,shutil,subprocess,tempfile,threading,unittest
from types import SimpleNamespace
spec=importlib.util.spec_from_file_location('cleanup_parent',Path(__file__).with_name('comic_reader_lifecycle_parent.py'));p=importlib.util.module_from_spec(spec);exec(compile(Path(spec.origin).read_bytes(),spec.origin,'exec'),p.__dict__)
class Cleanup(unittest.TestCase):
 def fixture_path(self):return self.base/'owned-parent'/'fixture'
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
  self.fixture=self.fixture_path();(self.fixture/'source').mkdir(parents=True);(self.fixture/'target').mkdir()
  self.control=self.base/'probe-input.json';raw=p.encode(dict(actual='retained input',root=str(self.fixture)));self.control.write_bytes(raw);self.control.chmod(0o600)
  self.owner=object.__new__(p.LifecycleParent);o=self.owner;o.engine=p.ScopedDocker();o.thread=threading.get_ident();o.deadline=p.time.monotonic()+30;o.plan={'nonce':'a'*64};o.source_ref={};o.plan_ref={};o.generated={};o.left=lambda:1
  o.files={};o.nodes={}
  cohort=self.base/'cohort.json';body=p.encode({'sources':{'hardlink_kernel':{'sha256':'d'*64}}});cohort.write_bytes(body);cohort.chmod(0o600);self.cohort=dict(path=str(cohort),sha256=hashlib.sha256(body).hexdigest());o.files[str(cohort)]=tuple(p.nine(cohort.stat()));o.nodes.update({k:tuple(v) for k,v in p.parents(cohort).items()})
  o.core=p.encode(dict(plan=o.plan,files=o.files,nodes=o.nodes,source=o.source_ref,input=o.plan_ref,engine=id(o.engine),thread=o.thread,deadline=o.deadline));p._CORES[o]=o.core
  self.outer=subprocess.Popen([sys.executable,'-c','import sys;sys.stdin.buffer.read()'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);self.inner=subprocess.Popen([sys.executable,'-c','pass'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);self.inner.wait(timeout=3)
  self.addCleanup(self.clean_processes)
  self.cid='b'*64;self.probe_cid='c'*64
  for cid,process in ((self.cid,self.outer),(self.probe_cid,self.inner)):
   streams=(process.stdin,process.stdout,process.stderr);fds=tuple((v.fileno(),tuple(p.five(os.fstat(v.fileno())))) for v in streams);p.dialogue_register(o.engine,cid,process,streams,fds,p.time.monotonic()+30,process.pid)
  self.directories=tuple((str(q),tuple(p.nine(q.stat()))) for q in (self.fixture,self.fixture/'source',self.fixture/'target'))
  self.kernel=dict(version=1,kind='checked-hardlink-canary-child',source_sha256='e'*64,kernel_sha256='d'*64,input_sha256=hashlib.sha256(raw).hexdigest(),report={},transitions=[],facts={},directories={k:list(v) for k,(_,v) in zip(('source','target'),self.directories[1:])},root9=list(self.directories[0][1]),actual_library_platform_verified=False,native_grant=False,publication_authority=False)
  class Probe:
   def prepared_descriptor(self):return None
  self.probe=Probe();self.probe.process=SimpleNamespace(process=self.inner,started=True,execution_sent=True,kernel_output=p.encode(self.kernel))
  class Lease:
   def window_state(self):return 'RELEASED_PHYSICAL'
   def physical_exit(self):return True
  self.lease=Lease();self.lease.channel=SimpleNamespace(released=True)
  absence=(str(self.fixture),str(self.fixture.parent))
  self.session=SimpleNamespace(owner=o,cid=self.cid,original_pid=self.outer.pid,close=lambda:None,probe_replies=SimpleNamespace(probe=self.probe),lease_replies=SimpleNamespace(lease=self.lease,absent=absence,absence_tape=absence,done=False));p._NFS_LIVE_SESSIONS[o]=self.session
  child=dict(path='/virtual/probe-input.json',sha256=hashlib.sha256(raw).hexdigest(),signature9=list(p.nine(self.control.stat())));nodes=tuple((k,tuple(v)) for k,v in p.parents(self.control).items());self.specification={'image':'original source-method projection','probe_sha256':'e'*64,'input_sha256':child['sha256'],'mounts':[[str(self.fixture),'/virtual/owned-parent/fixture',True]]}
  self.row=(child,str(self.control),nodes,self.directories,self.session,self.cid,self.outer.pid,o.plan['nonce'],self.specification);p._NFS_PROBE_ROWS[o]=self.row;p._NFS_PROBE_SEALS[o]=p.encode(dict(child=child,host=str(self.control),nodes=nodes,directories=self.directories,cid=self.cid,pid=self.outer.pid,nonce=o.plan['nonce'],spec=self.specification))
  p._NFS_SOURCE_CONTEXTS[o]=({}, {},p.encode({'source_cohort':self.cohort}),b'', '')
  self.mapping=p.Paths([dict(host=str(self.base),child='/virtual',write=False)]);self.mapping.owner=o;self.ref=dict(path=str(self.control),sha256=child['sha256'],signature9=child['signature9'])
  self.birth=(o,self.session,self.probe,Probe,self.probe.process,None,None,None,None,None,None,None,Probe.prepared_descriptor,Probe.prepared_descriptor.__code__);p._NFS_PROBE_BIRTHS[o.engine]={self.probe_cid:self.birth}
  launch=(self.birth,self.inner,p._DIALOGUE_SEALS[o.engine][self.probe_cid]);p._NFS_PROBE_LAUNCHES[o.engine]={self.probe_cid:launch};modules={'comic_nfs_host_lease.py':SimpleNamespace(HostWriterLease=Lease)};p._NFS_HOST_MODULES[o]=modules;p._NFS_HOST_MODULE_SEALS[o]=(tuple(modules.items()),())
  self.record=(o,o.core,o.thread,o.plan['nonce'],self.session,self.cid,self.lease,Lease,p._DIALOGUE_SEALS[o.engine][self.cid],self.outer,Lease.window_state,Lease.window_state.__code__,Lease.physical_exit,Lease.physical_exit.__code__,self.birth,p.encode(dict(cid=self.probe_cid)),launch);p._NFS_REMOTE_WINDOWS[o.engine]=self.record
 def clean_processes(self):
  self.outer.stdin.close();self.outer.wait(timeout=3)
  for process in (self.outer,self.inner):
   for stream in (process.stdin,process.stdout,process.stderr):
    if not stream.closed:stream.close()
  for registry in (p._NFS_REMOTE_WINDOWS,p._NFS_PROBE_BIRTHS,p._NFS_PROBE_LAUNCHES,p._DIALOGUES,p._DIALOGUE_SEALS):registry.pop(self.owner.engine,None)
  for registry in (p._CORES,p._NFS_LIVE_SESSIONS,p._NFS_HOST_MODULES,p._NFS_HOST_MODULE_SEALS,p._NFS_PROBE_ROWS,p._NFS_PROBE_SEALS,p._NFS_SOURCE_CONTEXTS,p._NFS_PROBE_REMOVED):registry.pop(self.owner,None)
 def remove(self):shutil.rmtree(self.fixture.parent)
 def release(self):self.owner.end_nfs_writer_window(self.lease);self.session.lease_replies.done=True
 def test_actual_paths_accept_only_original_cleanup_after_successful_release(self):
  self.assertEqual(self.mapping.check_nfs_probe(self.ref),self.specification);self.remove()
  with self.assertRaisesRegex(p.Held,'missing-before-cleanup-proof'):self.mapping.check_nfs_probe(self.ref)
  self.release();self.assertEqual(self.mapping.check_nfs_probe(self.ref),self.specification);self.assertEqual(tuple(p.nine(self.control.stat())),tuple(self.ref['signature9']))
 def test_aborted_physical_exit_records_no_cleanup_transition(self):
  self.remove();self.lease.channel.released=False;self.release();self.assertNotIn(self.owner,p._NFS_PROBE_REMOVED)
  with self.assertRaisesRegex(p.Held,'missing-before-cleanup-proof'):self.mapping.check_nfs_probe(self.ref)
 def test_failed_or_foreign_kernel_input_cannot_record_transition(self):
  self.remove();self.kernel['input_sha256']='f'*64;self.probe.process.kernel_output=p.encode(self.kernel)
  with self.assertRaisesRegex(p.Held,'kernel-ACK'):self.release()
  self.assertIn(self.owner.engine,p._NFS_REMOTE_WINDOWS);self.assertNotIn(self.owner,p._NFS_PROBE_REMOVED)
 def test_reappeared_original_parent_or_control_drift_refuses(self):
  self.remove();self.release();self.fixture.parent.mkdir()
  with self.assertRaisesRegex(p.Held,'absence-drift'):self.mapping.check_nfs_probe(self.ref)
  self.fixture.parent.rmdir();self.control.write_bytes(b'{"actual":"modified input"}')
  with self.assertRaises(p.Held):self.mapping.check_nfs_probe(self.ref)
 def test_missing_success_ack_done_or_original_row_refuses(self):
  self.remove();self.release();self.session.lease_replies.done=False
  with self.assertRaisesRegex(p.Held,'successful-release'):self.mapping.check_nfs_probe(self.ref)
  self.session.lease_replies.done=True;p._NFS_PROBE_ROWS[self.owner]=tuple(list(self.row))
  with self.assertRaisesRegex(p.Held,'successful-release'):self.mapping.check_nfs_probe(self.ref)
class ProjectedCleanup(unittest.TestCase):
 def setUp(self):
  self.fixture=Cleanup();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
  f=self.fixture;operation=f.base/'operation';operation.mkdir(mode=0o700)
  spec=importlib.util.spec_from_file_location('cleanup_report_tree',Path(__file__).with_name('comic_child_control_projection.py'))
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  tree=module.Tree(f.base/'report-child','/_operation',operation,p.read);tree._mkdir(tree.root/'backup')
  source=tree.root/'backup/backup-report.json';source.write_bytes(b'{"phase":"backup"}');source.chmod(0o600)
  child=dict(path='/_operation/backup/backup-report.json',sha256=hashlib.sha256(source.read_bytes()).hexdigest(),signature9=list(p.nine(source.stat())))
  _,self.view=tree.output(child,child['path'],'report');self.alias=str(operation/'backup/backup-report.json')
  f.owner.generated[self.alias]=self.view
 def test_release_checks_physical_copy_without_stating_alias(self):
  f=self.fixture;f.remove();original=p.nfs_lstat
  def checked(path):
   self.assertNotEqual(str(path),self.alias)
   return original(path)
  from unittest.mock import patch
  with patch.object(p,'nfs_lstat',side_effect=checked):f.release()
  self.assertNotIn(f.owner.engine,p._NFS_REMOTE_WINDOWS)
 def test_release_rejects_conflicting_physical_generated_facts(self):
  f=self.fixture;other=dict(self.view,signature9=list(self.view['signature9']));other['signature9'][1]+=1;f.owner.generated['another-logical-alias']=other;f.remove()
  with self.assertRaisesRegex(p.Held,'nfs-writer-window-generated-conflict'):f.release()
  self.assertIn(f.owner.engine,p._NFS_REMOTE_WINDOWS)
 def test_release_rejects_physical_drift_after_cleanup_callback(self):
  f=self.fixture;original=f.owner.nfs_probe_cleanup_transition
  def late(*args):
   result=original(*args);Path(self.view['path']).chmod(0o640);return result
  f.owner.nfs_probe_cleanup_transition=late;f.remove()
  with self.assertRaises(p.Held):f.release()
  self.assertIn(f.owner.engine,p._NFS_REMOTE_WINDOWS)

class RetentionCleanup(Cleanup):
 def fixture_path(self):
  root=self.base/('archive-publication-'+'a'*64);root.mkdir(mode=0o711);root.chmod(0o711)
  (root/'L').mkdir(mode=0o700);(root/'R').mkdir(mode=0o700)
  return root/'R'/('.comic-nfs-private-'+'b'*32)/('.comic-nfs-probe-'+'c'*32)
 def setUp(self):
  super().setUp();self.bind_retention()
 def bind_retention(self):
  o=self.owner;root=self.fixture.parent.parent.parent
  geometry=dict(version=2,kind='searchable-common-root-nfs',**{role:dict(path=str(path),signature9=p.nine(path.stat())) for role,path in (('common_root',root),('library',root/'L'),('retention',root/'R'))})
  self.common=p.admit_common_root(geometry,[dict(host=str(root),child=str(root),write=True)],str(root/'L'),str(root/'R'),[])
  self.addCleanup(p.close_common_root,self.common);self.addCleanup(p._ARCHIVE_COMMON_ROOTS.pop,o,None)
  p._ARCHIVE_COMMON_ROOTS[o]=self.common;o.plan.update(version=13,kind='reviewed-archive-one-lifecycle-protocol',publication_geometry=geometry)
  o.mapping=self.mapping;self.mapping.nfs_roots=lambda:(str(root),)
  stamp=geometry['retention']['signature9'];retention=str(root/'R')
  self.specification.update(binding=dict(host_root=retention,child_root=retention,root5=[stamp[i] for i in (0,1,5,6,7)]),mounts=[[retention,retention,True],[retention,'/config',False]])
  self.reseal();o.core=p.encode(dict(plan=o.plan,files=o.files,nodes=o.nodes,source=o.source_ref,input=o.plan_ref,engine=id(o.engine),thread=o.thread,deadline=o.deadline));p._CORES[o]=o.core
  self.record=tuple(o.core if i==1 else value for i,value in enumerate(self.record));p._NFS_REMOTE_WINDOWS[o.engine]=self.record
 def reseal(self):
  child,host,nodes,directories,session,cid,pid,nonce,specification=self.row
  p._NFS_PROBE_SEALS[self.owner]=p.encode(dict(child=child,host=host,nodes=nodes,directories=directories,cid=cid,pid=pid,nonce=nonce,spec=specification))
 def test_physical_cleanup_does_not_reenter_expired_operational_deadline(self):
  self.remove()
  def expired():raise p.Held('operational-deadline-expired')
  o=self.owner;o.deadline=p.time.monotonic()-1;o.left=expired
  o.core=p.encode(dict(plan=o.plan,files=o.files,nodes=o.nodes,source=o.source_ref,input=o.plan_ref,engine=id(o.engine),thread=o.thread,deadline=o.deadline));p._CORES[o]=o.core
  self.record=tuple(o.core if i==1 else value for i,value in enumerate(self.record));p._NFS_REMOTE_WINDOWS[o.engine]=self.record
  self.release()
  self.assertIn(self.owner,p._NFS_PROBE_REMOVED);p.check_common_root(self.common)
 def test_retention_descriptor_and_mounts_remain_exact(self):
  import copy
  original=copy.deepcopy(self.specification);self.remove()
  for mutate in (lambda s:s['binding']['root5'].__setitem__(1,-1),lambda s:s['binding'].__setitem__('child_root','/other'),lambda s:s['mounts'][0].__setitem__(2,False),lambda s:s['mounts'][1].__setitem__(1,'/other'),lambda s:s['mounts'][1].__setitem__(2,True)):
   self.specification.clear();self.specification.update(copy.deepcopy(original));mutate(self.specification);self.reseal()
   with self.assertRaises(p.Held):self.release()
   self.assertNotIn(self.owner,p._NFS_PROBE_REMOVED)
 def test_foreign_common_geometry_and_reused_retention_fd_refuse(self):
  self.remove();row=p._ARCHIVE_COMMON_ROOTS[self.owner]
  p._ARCHIVE_COMMON_ROOTS[self.owner]=(row[0],dict(row[1],version=1),row[2],row[3])
  with self.assertRaises(p.Held):self.release()
  p._ARCHIVE_COMMON_ROOTS[self.owner]=row
  fd=row[2][1];other=os.open(self.base,os.O_RDONLY|os.O_DIRECTORY)
  try:os.dup2(other,fd)
  finally:os.close(other)
  with self.assertRaises(p.Held):self.release()
  # Restore the owned descriptor for fixture teardown only.
  restored=os.open(row[1]['retention']['path'],os.O_RDONLY|os.O_DIRECTORY)
  try:os.dup2(restored,fd)
  finally:os.close(restored)
 def test_late_common_row_replacement_during_absence_refuses(self):
  from unittest import mock
  self.remove();original=p.nfs_absent
  def absent(path):
   answer=original(path);p._ARCHIVE_COMMON_ROOTS[self.owner]=tuple(list(self.common));return answer
  with mock.patch.object(p,'nfs_absent',side_effect=absent):
   with self.assertRaises(p.Held):self.release()
  self.assertNotIn(self.owner,p._NFS_PROBE_REMOVED)
 def test_last_release_absence_callback_cannot_replace_retention_row(self):
  from unittest import mock
  self.remove();original=p.nfs_absent;calls=[]
  def absent(path):
   answer=original(path);calls.append(path)
   if len(calls)==3:p._ARCHIVE_COMMON_ROOTS[self.owner]=tuple(list(self.common))
   return answer
  with mock.patch.object(p,'nfs_absent',side_effect=absent):
   with self.assertRaises(p.Held):self.release()
  self.assertGreaterEqual(len(calls),3);self.assertNotIn(self.owner,p._NFS_PROBE_REMOVED)
 def test_final_retention_check_cannot_replace_original_remote_block(self):
  from unittest import mock
  self.remove();original=p.check_common_root;calls=[];replacement=tuple(list(self.record))
  def check(row):
   original(row);calls.append(row)
   if len(calls)==3:p._NFS_REMOTE_WINDOWS[self.owner.engine]=replacement
  with mock.patch.object(p,'check_common_root',side_effect=check):
   with self.assertRaises(p.Held):self.release()
  self.assertIs(p._NFS_REMOTE_WINDOWS[self.owner.engine],replacement)
  self.assertNotIn(self.owner,p._NFS_PROBE_REMOVED)
class IntegratedProbe(unittest.TestCase):
 """Actual Parent/session/common-root checks; constructors and handlers projected."""
 fixture_path=RetentionCleanup.fixture_path
 reseal=RetentionCleanup.reseal
 clean_processes=Cleanup.clean_processes
 def setUp(self):
  import types,uuid
  Cleanup.setUp(self);RetentionCleanup.bind_retention(self);o=self.owner
  source=Path(__file__).with_name('comic_nfs_parent_session.py');private=self.base/'session.py';private.write_bytes(source.read_bytes());private.chmod(0o600)
  name='probe_custody_session_'+uuid.uuid4().hex;module=types.ModuleType(name);module.__file__=str(private)
  exec(compile(private.read_bytes(),str(private),'exec'),module.__dict__);sys.modules[name]=module;self.addCleanup(sys.modules.pop,name,None)
  scope=self.base/'scope.json';scope.write_bytes(p.encode(dict(forbidden_roots=[self.common[1]['library']['path']])));scope.chmod(0o600)
  ref=dict(path=str(scope),sha256=hashlib.sha256(scope.read_bytes()).hexdigest(),signature9=p.nine(scope.stat()));self.scope=scope
  session_ref=dict(path=str(private),sha256=hashlib.sha256(private.read_bytes()).hexdigest(),signature9=p.nine(private.stat()))
  active=dict(active_scope={k:ref[k] for k in ('path','sha256')},parent_admission=dict(path=str(self.fixture.parent)))
  refs={'comic_nfs_parent_session.py':session_ref};raws={'comic_nfs_parent_session.py':private.read_bytes()}
  p._NFS_SOURCE_CONTEXTS[o]=(refs,raws,p.encode(active),p.encode({}),'/fixture')
  p._NFS_EFFECTIVE_ABSENCES[o]=p.encode([]);self.addCleanup(p._NFS_EFFECTIVE_ABSENCES.pop,o,None)
  p._NFS_SOURCE_SEALS[o]=p.encode(dict(refs=refs,raw_sha={k:hashlib.sha256(v).hexdigest() for k,v in raws.items()},active=active,probe={},output='/fixture',effective_absences=[]));self.addCleanup(p._NFS_SOURCE_SEALS.pop,o,None)
  p._NFS_DATA_ROOTS[o]=(self.common[1]['library']['path'],str(self.fixture.parent.parent));del self.mapping.nfs_roots;self.addCleanup(p._NFS_DATA_ROOTS.pop,o,None)
  for item in (ref,session_ref):
   o.files[item['path']]=tuple(item['signature9']);o.nodes.update(p.parents(Path(item['path'])))
  o.op=self.base/'operation';o.op.mkdir(mode=0o700);o.plan['operation']=str(o.op)
  self.lefts=[];original=p.LifecycleParent.left
  def left():self.lefts.append(True);return original(o)
  o.left=left
  o.core=p.encode(dict(plan=o.plan,files=o.files,nodes=o.nodes,source=o.source_ref,input=o.plan_ref,engine=id(o.engine),thread=o.thread,deadline=o.deadline));p._CORES[o]=o.core;p._GENERATED[o]=p.encode(o.generated);self.addCleanup(p._GENERATED.pop,o,None)
  session=object.__new__(module.RetainedChild);session.owner=o;session.g=p.__dict__;session.cid=self.cid;session.original_pid=self.outer.pid;session.state='ready'
  engine=SimpleNamespace(owner=o,cid=self.cid,nonce=o.plan['nonce'])
  session.engine_replies=engine;session.lease_replies=SimpleNamespace(dialogue=engine,lease=self.lease,done=False);session.probe_replies=SimpleNamespace(dialogue=engine,probe=self.probe)
  session.packet_ref=self.ref;o.generated[self.ref['path']]=self.ref;p._GENERATED[o]=p.encode(o.generated)
  session.output='/fixture';session.created_static=b'constructor projection';session.lease_class=object;session.abort_method=object;session.abort_code=None
  method=p.LifecycleParent.nfs_host_modules;session.host_modules_guard=(method,method.__code__,method.__defaults__)
  session.seal=(o,session.g,self.cid,engine,session.lease_replies,session.probe_replies,(self.ref['path'],self.ref['sha256'],tuple(self.ref['signature9'])),session.output,session.host_modules_guard)
  module._SESSION_SEALS[session]=(*session.seal,session.created_static,session.lease_class,session.abort_method,session.abort_code)
  p._NFS_LIVE_SESSIONS[o]=session;self.session=session
  entry=('comic_nfs_parent_session.py',module,name,((module.RetainedChild,'close',module.RetainedChild.close,module.RetainedChild.close.__code__),))
  p._NFS_HOST_MODULES[o]={'comic_nfs_parent_session.py':module};p._NFS_HOST_MODULE_SEALS[o]=(tuple(p._NFS_HOST_MODULES[o].items()),(entry,))
  child,host,nodes,directories,_,cid,pid,nonce,spec=self.row;self.row=(child,host,nodes,directories,session,cid,pid,nonce,spec);p._NFS_PROBE_ROWS[o]=self.row;self.reseal()
 def test_initial_and_final_actual_parent_closures(self):
  self.assertEqual(self.mapping.check_nfs_probe(self.ref),self.specification);self.assertEqual(len(self.lefts),2)
 def test_host_boundary_has_three_actual_parent_closures(self):
  import comic_nfs_host_probe as host
  probe=object.__new__(host.HostProbe);probe.dialogue=SimpleNamespace(close=self.owner.left);probe.owner=self.owner;probe.admitted=self.ref;probe.spec_tape=host.encode(self.specification)
  probe.close();self.assertEqual(len(self.lefts),3)
 def test_instance_session_checker_replacement_refuses(self):
  self.session.close=lambda:None
  with self.assertRaisesRegex(p.Held,'original-session-checker'):self.mapping.check_nfs_probe(self.ref)
 def test_final_source_callback_input_drift_refuses(self):
  from unittest.mock import patch
  original=p.dialogue_close;calls=[]
  def close(*args):
   result=original(*args);calls.append(True)
   if len(calls)==2:self.control.write_bytes(b'late admitted input drift')
   return result
  with patch.object(p,'dialogue_close',side_effect=close),self.assertRaises(p.Held):self.mapping.check_nfs_probe(self.ref)
 def test_late_scope_drift_refuses(self):
  from unittest.mock import patch
  original=p.nfs_lstat;changed=[]
  def stat(path):
   result=original(path)
   if str(path)==str(self.control) and not changed:self.scope.write_bytes(b'late scope drift');changed.append(True)
   return result
  with patch.object(p,'nfs_lstat',side_effect=stat),self.assertRaises(p.Held):self.mapping.check_nfs_probe(self.ref)
 def test_final_callback_context_replacement_refuses(self):
  from unittest.mock import patch
  original=p.dialogue_close;calls=[]
  def close(*args):
   result=original(*args);calls.append(True)
   if len(calls)==2:p._NFS_SOURCE_CONTEXTS[self.owner]=tuple(list(p._NFS_SOURCE_CONTEXTS[self.owner]))
   return result
  with patch.object(p,'dialogue_close',side_effect=close),self.assertRaisesRegex(p.Held,'original-context'):self.mapping.check_nfs_probe(self.ref)
 def test_final_source_callback_scope_drift_refuses(self):
  from unittest.mock import patch
  original=p.dialogue_close;calls=[]
  def close(*args):
   result=original(*args);calls.append(True)
   if len(calls)==2:self.scope.write_bytes(b'final source callback scope drift')
   return result
  with patch.object(p,'dialogue_close',side_effect=close),self.assertRaises(p.Held):self.mapping.check_nfs_probe(self.ref)
 def test_final_callback_cannot_adopt_different_physical_phase(self):
  from unittest.mock import patch
  original=p.dialogue_close;calls=[]
  def close(*args):
   result=original(*args);calls.append(True)
   if len(calls)==2:self.probe.process.started=False
   return result
  with patch.object(p,'dialogue_close',side_effect=close),self.assertRaisesRegex(p.Held,'original-physical-phase'):self.mapping.check_nfs_probe(self.ref)
 def test_final_callback_cannot_clear_original_source_refs(self):
  self.context_mutation(lambda context:context[0].clear())
 def test_final_callback_cannot_replace_original_raw_source(self):
  self.context_mutation(lambda context:context[1].__setitem__('comic_nfs_parent_session.py',b'foreign raw bytes'))
 def test_final_callback_cannot_replace_equal_valued_ref_dictionary(self):
  def replace(context):self.owner_context=(dict(context[0]),*context[1:]);p._NFS_SOURCE_CONTEXTS[self.owner]=self.owner_context
  self.context_mutation(replace)
 def test_final_callback_cannot_reseal_changed_context(self):
  def reseal(context):
   context[0].clear();p._NFS_SOURCE_SEALS[self.owner]=p.encode(dict(refs={},raw_sha={},active={},probe={},output='/fixture',effective_absences=[]))
  self.context_mutation(reseal)
 def context_mutation(self,mutate):
  from unittest.mock import patch
  original=p.dialogue_close;calls=[]
  def close(*args):
   result=original(*args);calls.append(True)
   if len(calls)==2:mutate(p._NFS_SOURCE_CONTEXTS[self.owner])
   return result
  with patch.object(p,'dialogue_close',side_effect=close),self.assertRaisesRegex(p.Held,'original-context'):self.mapping.check_nfs_probe(self.ref)
 def test_final_callback_retention_fd_substitution_refuses(self):
  from unittest.mock import patch
  original=p.dialogue_close;calls=[];fd=self.common[2][1];saved=os.dup(fd)
  def close(*args):
   result=original(*args);calls.append(True)
   if len(calls)==2:
    other=os.open(self.base,os.O_RDONLY|os.O_DIRECTORY)
    try:os.dup2(other,fd)
    finally:os.close(other)
   return result
  try:
   with patch.object(p,'dialogue_close',side_effect=close),self.assertRaises(p.Held):self.mapping.check_nfs_probe(self.ref)
  finally:os.dup2(saved,fd);os.close(saved)

if __name__=='__main__':unittest.main()
