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
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
  self.fixture=self.base/'owned-parent'/'fixture';(self.fixture/'source').mkdir(parents=True);(self.fixture/'target').mkdir()
  self.control=self.base/'probe-input.json';raw=b'{"actual":"retained input"}';self.control.write_bytes(raw);self.control.chmod(0o600)
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
if __name__=='__main__':unittest.main()
