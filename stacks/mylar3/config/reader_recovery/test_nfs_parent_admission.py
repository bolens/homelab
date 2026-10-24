"""Owning mapping refusal controls; projected session, no NFS/SDK grant."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import importlib.util
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import comic_child_control_projection as controls
import comic_nfs_host_probe as host_probe

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

    def test_nested_probe_sources_project_outside_protected_bootstrap_ancestry(self):
        # Actual admission, Tree and command construction; no Docker/factory grant.
        m=self.m;root=Path(self.tmp.name);bootstrap=root/'bootstrap';bootstrap.mkdir(mode=0o700)
        operation=bootstrap/'operation';operation.mkdir(mode=0o700)
        library=root/'L';library.mkdir(mode=0o700)
        retention=root/'R';retention.mkdir(mode=0o700)
        admission=retention/'private';admission.mkdir(mode=0o700)
        fixture=admission/'probe';fixture.mkdir(mode=0o700)
        for leaf in ('source','target'):(fixture/leaf).mkdir(mode=0o700)
        def ref(path,value):
            raw=value if type(value)is bytes else m.encode(value)
            path.write_bytes(raw);path.chmod(0o600)
            return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),signature9=m.nine(path.lstat()))
        sources={name:ref(bootstrap/(name+'.py'),b'# checked source\n') for name in ('probe','hardlink_kernel')}
        scope=ref(bootstrap/'scope.json',dict(forbidden_roots=[str(bootstrap),str(library)]))
        image='sha256:'+'b'*64
        cohort=ref(bootstrap/'cohort.json',dict(images=dict(selected=image),sources={k:{n:v[n] for n in ('path','sha256')} for k,v in sources.items()}))
        owner=object.__new__(m.LifecycleParent)
        owner.plan=dict(version=13,kind='reviewed-archive-one-lifecycle-protocol',nonce='a'*64,selected_image=image)
        mapping=m.Paths([dict(host=str(operation),child='/_operation',write=True)])
        mapping.owner=owner;owner.mapping=mapping
        tree=controls.Tree(bootstrap/'operation-child','/_operation',operation,m.read,uid=os.geteuid(),gid=os.getegid())
        owner.left=tree.check
        owner.files={v['path']:tuple(v['signature9']) for v in (*sources.values(),scope,cohort)}
        active=dict(parent_admission=dict(path=str(admission)),active_scope={k:scope[k] for k in ('path','sha256')},source_cohort={k:cohort[k] for k in ('path','sha256')})
        mount=dict(fstype='nfs4');plan=dict(fixture_name=fixture.name,expected_device=fixture.stat().st_dev,mount_identity=mount)
        m._CHILD_TREES[owner]=tree
        m._NFS_DATA_ROOTS[owner]=(str(bootstrap),str(library),str(retention))
        m._NFS_SOURCE_CONTEXTS[owner]=({}, {},m.encode(active),m.encode(plan),'unused')
        for registry in (m._CHILD_TREES,m._NFS_DATA_ROOTS,m._NFS_SOURCE_CONTEXTS,m._NFS_LIVE_SESSIONS,m._NFS_PROBE_ROWS,m._NFS_PROBE_SEALS):self.addCleanup(registry.pop,owner,None)
        phase=tree.phase('nfs');output=phase/'active-output';output.mkdir(mode=0o700)
        probe=output/'probe';probe.mkdir(mode=0o700)
        original=ref(probe/'probe-input.json',dict(version=1,kind='reviewed-disposable-hardlink-nfs-canary',nonce='c'*64,root=str(fixture),root9=m.nine(fixture.stat()),source_parent9=m.nine((fixture/'source').stat()),target_parent9=m.nine((fixture/'target').stat()),device=plan['expected_device'],mount=mount,forbidden_roots=[str(bootstrap),str(library)],seconds=120))
        child=dict(original,path='/_operation/nfs/active-output/probe/probe-input.json')
        session=SimpleNamespace(output='/_operation/nfs/active-output',close=tree.check,cid='d'*64,original_pid=123,probe_replies=SimpleNamespace(probe=None))
        m._NFS_LIVE_SESSIONS[owner]=session
        with patch.object(mapping,'nfs_probe_binding',return_value=None):
            admitted=mapping.admit_nfs_probe(child);spec=mapping.check_nfs_probe(admitted)
        for index,key in enumerate(('probe','hardlink_kernel'),3):
            physical,virtual,write=spec['mounts'][index]
            self.assertEqual(mapping.nfs_child(physical),physical)  # Reproduces the protected-root precedence.
            self.assertTrue(virtual.startswith('/_operation/'))
            self.assertEqual(mapping.host(virtual),physical);self.assertFalse(write)
            self.assertEqual(Path(physical).read_bytes(),Path(sources[key]['path']).read_bytes())
        process=host_probe.ProbeProcess(spec,['docker'],None,tree.check)
        argv=process.command();self.assertEqual(argv[argv.index(image)+1],spec['mounts'][3][1])
        self.assertEqual(argv[argv.index('--kernel')+1],spec['mounts'][4][1])
        self.assertEqual(bootstrap.stat().st_mode&0o777,0o700)
        self.assertIn([str(bootstrap),str(bootstrap),False],spec['mounts'])
        tree.check()

if __name__=='__main__':unittest.main()
