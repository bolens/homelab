"""Owning mapping refusal controls; projected session, no NFS/SDK grant."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import importlib.util
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

class Admission(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('parent_nfs_controls',Path(__file__).with_name('comic_reader_lifecycle_parent.py'))
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name);self.mapping=self.m.Paths([dict(host=str(root),child='/fixture',write=True)])
        class Owner:
            def left(self):pass
        self.owner=Owner();self.mapping.owner=self.owner
        self.session=SimpleNamespace(output='/fixture/output',close=lambda:None)
        self.m._NFS_LIVE_SESSIONS[self.owner]=self.session
    def test_foreign_probe_path_refuses_before_read(self):
        with self.assertRaisesRegex(self.m.Held,'exact-derived-input'):
            self.mapping.admit_nfs_probe(dict(path='/fixture/foreign.json',sha256='a'*64,signature9=[]))
    def test_probe_wrong_creator_uid_refuses(self):
        stamp=[1,2,3,4,5,0o100600,0,0,1]
        with self.assertRaisesRegex(self.m.Held,'child-creator'):
            self.mapping.admit_nfs_probe(dict(path='/fixture/output/probe/probe-input.json',sha256='a'*64,signature9=stamp))
    def test_unregistered_probe_session_refuses(self):
        del self.m._NFS_LIVE_SESSIONS[self.owner]
        with self.assertRaisesRegex(self.m.Held,'original-session'):
            self.mapping.admit_nfs_probe({})
    def test_check_cannot_adopt_unadmitted_current_file(self):
        with self.assertRaisesRegex(self.m.Held,'original-unbound'):
            self.mapping.check_nfs_probe(dict(path='/fixture/foreign',sha256='a'*64,signature9=[]))

    def test_namespace_requires_original_before_lease(self):
        self.session.lease_replies=SimpleNamespace(lease=object())
        with self.assertRaisesRegex(self.m.Held,'before-lease-only'):
            self.m.LifecycleParent.nfs_role_namespace_reply(self.owner,{})
    def test_reader_epoch_does_not_accept_child_selected_pid(self):
        self.owner.plan={'nonce':'a'*64};self.session.engine_replies=SimpleNamespace(sequence=0)
        with self.assertRaisesRegex(self.m.Held,'finite-frame'):
            self.m.LifecycleParent.nfs_reader_epoch_reply(self.owner,dict(type='nfs-reader-epoch',nonce='a'*64,sequence=1,payload={'pid':123}))
    def test_reader_epoch_bool_sequence_refuses(self):
        self.owner.plan={'nonce':'a'*64};self.session.engine_replies=SimpleNamespace(sequence=0)
        with self.assertRaisesRegex(self.m.Held,'finite-frame'):
            self.m.LifecycleParent.nfs_reader_epoch_reply(self.owner,dict(type='nfs-reader-epoch',nonce='a'*64,sequence=True,payload={}))

if __name__=='__main__':unittest.main()
