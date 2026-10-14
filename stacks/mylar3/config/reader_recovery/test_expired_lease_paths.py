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
  lease=object.__new__(h.HostWriterLease);lease.owner=owner;lease.g={'read':parent.read,'_CORES':{owner:owner.core}};lease.tree=tree;lease.helper=ref;lease.projected=physical;lease.admitted_empty=dict(path=str(empty),signature9=list(h.nine(empty.lstat())));lease.empty=str(empty);lease.empty9=tuple(h.nine(empty.lstat()));lease.empty_nodes=tuple((str(q),h.five(q.lstat())) for q in empty.parents);lease.root=writer;lease.root5,lease.writer_files=h.namespace(writer);lease.writer_nodes=tuple((str(q),h.five(q.lstat())) for q in writer.parents);lease.writer_sha='c'*64;lease.image='source-method-projection';lease.token='a'*64;lease.name='fixture';lease.mounts=();lease.command=();lease.create_args=()
  lease.tape=h.encode(dict(helper=lease.helper,projected=lease.projected,empty=lease.empty,empty9=lease.empty9,empty_nodes=lease.empty_nodes,writer_original=(lease.root5,lease.writer_files,lease.writer_nodes),root=str(lease.root),writer_sha=lease.writer_sha,image=lease.image,token=lease.token,name=lease.name,mounts=lease.mounts,command=lease.command,create=lease.create_args));self.lease=lease
 def test_actual_paths_expired_refuses_active_but_local_original_closure_succeeds(self):
  with self.assertRaisesRegex(ValueError,'actual-expired-Paths-owner'):self.lease.owner.mapping.child_host_ref(self.lease.helper)
  with self.assertRaisesRegex(ValueError,'actual-expired-Paths-owner'):self.lease.owner.mapping.check_nfs_empty(self.lease.admitted_empty)
  self.lease.original(allow_expired=True)
 def test_expired_local_closure_still_refuses_original_empty_mode_drift(self):
  Path(self.lease.empty).chmod(0o750)
  with self.assertRaisesRegex(h.Held,'lease-projection-originals'):self.lease.original(allow_expired=True)
if __name__=='__main__':unittest.main()
