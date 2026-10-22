"""Actual original-process exits and directory custody; Parent/NFS facts projected explicitly."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import threading
import types
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import comic_nfs_parent_session as S
import comic_nfs_factual_successor as N
import comic_reader_lifecycle_parent as P


def seal_fixture_owner(owner):
    # Explicit constructor projection; actual Parent.left and metadata readers
    # retain their original method/module/thread/source and registry contracts.
    owner.core=P.encode(dict(plan=owner.plan,files=owner.files,nodes=owner.nodes,
        source=owner.source_ref,input=owner.plan_ref,engine=id(owner.engine),
        thread=owner.thread,deadline=owner.deadline))
    P._CORES[owner]=owner.core;P._GENERATED[owner]=P.encode(owner.generated)


def fixture_owner():
    owner=object.__new__(P.LifecycleParent)
    owner.thread=threading.get_ident();owner.deadline=time.monotonic()+3600
    owner.op=Path('/fixture-operation');owner.plan=dict(nonce='fixture',operation=str(owner.op))
    owner.engine=object();owner.files={};owner.nodes={};owner.plan_ref={};owner.generated={}
    source=Path(P.__file__).absolute()
    owner.source_ref=dict(path=str(source),sha256=P.hashlib.sha256(source.read_bytes()).hexdigest(),signature9=P.nine(source.stat()))
    seal_fixture_owner(owner)
    return owner

class Exit(unittest.TestCase):
    def pump(self,body='pass'):
        process=subprocess.Popen([sys.executable,'-I','-B','-u','-c',body],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        streams=(process.stdin,process.stdout,process.stderr)
        def cleanup():
            if process.poll() is None:process.kill()
            process.wait(timeout=5)
            for stream in streams:
                if not stream.closed:stream.close()
        self.addCleanup(cleanup)
        return process,S.OriginalPump(process,time.monotonic()+5,lambda:None)
    def test_original_zero_exit_survives_elapsed_child_budget_without_callback(self):
        process,pump=self.pump();pump.finish();value=pump.successful_exit()
        with patch.object(S.time,'monotonic',return_value=pump.deadline+121):
            self.assertIs(pump.successful_exit(),value)
        self.assertEqual(process.returncode,0);self.assertTrue(all(v.closed for v in pump.streams))
        with self.assertRaises(S.Held):pump.write({})
    def test_nonzero_exit_never_mints_successor(self):
        _,pump=self.pump('raise SystemExit(3)')
        with self.assertRaisesRegex(S.Held,'child-exit'):pump.finish()
        with self.assertRaisesRegex(S.Held,'no-successful-exit'):pump.successful_exit()
    def test_unfinished_live_process_never_mints_successor(self):
        process,pump=self.pump('input()')
        with self.assertRaisesRegex(S.Held,'no-successful-exit'):pump.successful_exit()
        self.assertIsNone(process.poll())
    def test_original_pid_or_stream_substitution_after_exit_refuses(self):
        process,pump=self.pump();pump.finish();original=process.pid;process.pid+=1
        with self.assertRaises(S.Held):pump.successful_exit()
        process.pid=original;process.stdin=process.stdout
        with self.assertRaises(S.Held):pump.successful_exit()
    def test_exited_private_registry_loss_refuses(self):
        _,pump=self.pump();pump.finish();del S._EXITED_PUMPS[pump]
        with self.assertRaises(S.Held):pump.successful_exit()

class SessionExit(unittest.TestCase):
    """Real finished pump, projected owning Parent and already-verified lease only."""
    pump=Exit.pump
    def session(self):
        _,pump=self.pump();pump.finish()
        owner=fixture_owner();owner.nfs_host_modules=lambda:None
        session=object.__new__(S.RetainedChild);session.owner=owner;session.pump=pump;session.state='finished'
        session.cid='a'*64;session.original_pid=pump.pid;session.created_static=b'original';session.output='/fixture'
        session.packet_ref=dict(path='/fixture/packet',sha256='b'*64,signature9=[1]*9);owner.generated[session.packet_ref['path']]=session.packet_ref
        seal_fixture_owner(owner)
        session.engine_replies=object();session.probe_replies=object()
        session.lease_replies=types.SimpleNamespace(done=True,lease=types.SimpleNamespace(physical_exit=lambda:True,channel=types.SimpleNamespace(released=True,aborted=False)))
        session.g=dict(read=lambda ref:None);session.lease_class=object();session.abort_method=object();session.abort_code=object()
        session.seal=(owner,session.g,session.cid,session.engine_replies,session.lease_replies,session.probe_replies,('/fixture/packet','b'*64,(1,)*9),session.output)
        S._SESSION_PUMPS[session]=pump;S._SESSION_SEALS[session]=(*session.seal,session.created_static,session.lease_class,session.abort_method,session.abort_code)
        return session
    def test_finished_original_session_positive_after_child_budget(self):
        session=self.session()
        with patch.object(S.time,'monotonic',return_value=session.pump.deadline+121):
            result=session.successful_exit()
        self.assertIs(result[0],session);self.assertEqual(result[3],session.pump.pid)
    def test_unknown_physical_release_refuses(self):
        session=self.session();session.lease_replies.lease.physical_exit=lambda:False
        with self.assertRaisesRegex(S.Held,'physical-release'):session.successful_exit()
    def test_aborted_exit_is_physical_only_and_cannot_mint_successor(self):
        session=self.session();session.lease_replies.lease.channel.aborted=True
        with self.assertRaisesRegex(S.Held,'physical-release'):session.successful_exit()
    def test_last_source_callback_session_substitution_refuses(self):
        session=self.session()
        def callback(ref):session.state='ready'
        session.g['read']=callback
        with self.assertRaisesRegex(S.Held,'final-originals'):session.successful_exit()

class Retention(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.root.chmod(0o700)
        self.library=self.root/'library';self.library.mkdir(mode=0o700)
        self.retention=self.root/'retention';self.retention.mkdir(mode=0o700)
    def original(self,**kwargs):
        return P.retention_original(str(self.retention),str(self.library),kwargs.get('device',self.library.stat().st_dev))
    def test_actual_uid1000_same_device_private_empty_positive(self):
        self.assertEqual(os.geteuid(),1000,'This public fixture requires its declared UID1000 owner')
        row=self.original();self.assertEqual(row[0],str(self.retention));self.assertEqual(row[1],tuple(P.nine(self.retention.stat())))
    def test_wrong_device_and_boolean_device_refuse(self):
        for device in (self.library.stat().st_dev+1,True):
            with self.subTest(device=device),self.assertRaises(P.Held):self.original(device=device)
    def test_mode_and_foreign_namespace_refuse(self):
        self.retention.chmod(0o750)
        with self.assertRaises(P.Held):self.original()
        self.retention.chmod(0o700);(self.retention/'foreign').touch()
        with self.assertRaises(P.Held):self.original()
    def test_overlap_and_symlink_refuse(self):
        with self.assertRaises(P.Held):P.retention_original(str(self.library),str(self.library),self.library.stat().st_dev)
        link=self.root/'link';link.symlink_to(self.retention,target_is_directory=True)
        with self.assertRaises(P.Held):P.retention_original(str(link),str(self.library),self.library.stat().st_dev)
    def test_replaced_directory_during_namespace_callback_refuses(self):
        actual=os.listdir;fired=[]
        def listing(path):
            if Path(path)==self.retention and not fired:
                fired.append(True);self.retention.rename(self.root/'old');self.retention.mkdir(mode=0o700)
            return actual(path)
        with patch.object(P.os,'listdir',side_effect=listing),self.assertRaises(P.Held):self.original()
        self.assertTrue(fired)
    def test_unbound_mapping_and_unregistered_parent_keep_default_refusal(self):
        mapping=P.Paths([dict(host=str(self.root),child=str(self.root),write=True)])
        with self.assertRaisesRegex(P.Held,'owning-mapping'):mapping.archive_retention_original(str(self.retention))
        owner=object.__new__(P.LifecycleParent);owner.thread=-1;owner.deadline=time.monotonic()+60
        # No _CORES registration, original Parent.left remains the actual guard.
        with self.assertRaisesRegex(P.Held,'parent-lifetime'):owner.admit_archive_retention(object())
    def test_foreign_declared_owner_refuses_without_chown(self):
        # Owner predicate test only: genuine stat tuple with one declared UID changed.
        actual=P.nine
        def nine(z):
            row=actual(z)
            if z.st_ino==self.retention.stat().st_ino:row[6]=0
            return row
        with patch.object(P,'nine',side_effect=nine),self.assertRaises(P.Held):self.original()


class RetentionCustody(unittest.TestCase):
    """Actual retained directory checks; owning handoff/constructor prerequisites projected."""
    def setUp(self):
        Retention.setUp(self);self.row=Retention.original(self)
        self.control=self.root/'scopes.json';self.control.write_bytes(b'{}');self.control.chmod(0o600)
        self.ref=dict(path=str(self.control),sha256=P.hashlib.sha256(b'{}').hexdigest(),signature9=P.nine(self.control.stat()))
        self.owner=object.__new__(P.LifecycleParent)
        self.handoff=object.__new__(N.StoppedNFSHandoff);self.handoff.owner=self.owner
        N._STOPPED_HANDOFFS[self.handoff]=('explicit-projected-constructor',)
        P._NFS_ADAPTERS[self.owner]=N
        self.record=(self.row,self.handoff,(),'adopt-'+('a'*32),(self.ref['path'],self.ref['sha256'],tuple(self.ref['signature9'])))
        P._ARCHIVE_RETENTION[self.owner]=self.record
    def test_original_empty_and_finite_execute_transition(self):
        self.owner.check_archive_retention()
        P._ARCHIVE_RETENTION_ACTIVE[self.owner]=self.record
        (self.retention/self.record[3]).mkdir(mode=0o700)
        self.owner.check_archive_retention()
    def test_retention_descriptor_keeps_initial9_across_execute_metadata(self):
        self.owner.left=lambda:3600.
        before=self.owner.archive_retention_original(str(self.retention))
        self.assertEqual(before['phase'],'initial');self.assertEqual(before['signature9'],before['original_signature9'])
        P._ARCHIVE_RETENTION_ACTIVE[self.owner]=self.record
        (self.retention/self.record[3]).mkdir(mode=0o700)
        after=self.owner.archive_retention_original(str(self.retention))
        self.assertEqual(after['original_signature9'],before['original_signature9']);self.assertNotEqual(after['signature9'],before['signature9'])
        self.assertEqual(after['phase'],'execute-owned');self.assertEqual(after['signature9'],P.nine(self.retention.stat()))
    def test_retention_descriptor_callback_cannot_refresh_current9(self):
        def callback():
            self.retention.chmod(0o750);self.retention.chmod(0o700)
        self.owner.left=callback
        with self.assertRaises(P.Held):self.owner.archive_retention_original(str(self.retention))
    def test_foreign_child_after_enter_refuses(self):
        P._ARCHIVE_RETENTION_ACTIVE[self.owner]=self.record
        (self.retention/'foreign').mkdir(mode=0o700)
        with self.assertRaises(P.Held):self.owner.check_archive_retention()
    def test_unsealed_admission_and_modified_scope_ref_refuse(self):
        del N._STOPPED_HANDOFFS[self.handoff]
        with self.assertRaises(P.Held):self.owner.check_archive_retention()
    def test_final_namespace_callback_cannot_add_foreign_entry(self):
        P._ARCHIVE_RETENTION_ACTIVE[self.owner]=self.record
        actual=P.os.listdir;calls=[]
        def listing(path):
            result=actual(path)
            if Path(path)==self.retention:
                calls.append(True)
                if len(calls)==1:(self.retention/'foreign').mkdir(mode=0o700)
            return result
        with patch.object(P.os,'listdir',side_effect=listing),self.assertRaises(P.Held):self.owner.check_archive_retention()
        self.assertTrue(calls)
    def test_original_empty_full9_is_not_refreshed(self):
        self.retention.chmod(0o750)
        with self.assertRaises(P.Held):self.owner.check_archive_retention()

class RetainedClose(unittest.TestCase):
    """Actual retained close and actual Parent.final; constructor/NFS dialogue projected."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.root.chmod(0o700)
        self.leaf=self.root/'leaf';self.leaf.write_bytes(b'original');self.leaf.chmod(0o600)
        self.owner=fixture_owner();self.owner.phase='admitted'
        self.session=types.SimpleNamespace(state='ready',request=lambda *a,**k:None)
        self.canary=object.__new__(N.RetainedObservation);c=self.canary;c.owner=self.owner;c.session=self.session
        c.tape=b'original-ready-facts';c.binding=dict(native_grant=False);c.mount=dict(fstype='nfs4');c.device=self.root.stat().st_dev
        c.files=((str(self.leaf),tuple(P.nine(self.leaf.stat()))),);c.nodes=((str(self.root),tuple(P.five(self.root.stat()))),)
        c.names=((str(self.root),frozenset(['leaf'])),);c.absent=(str(self.root/'missing'),)
        c.g=dict(encode=P.encode,final=P.final,_NFS_LIVE_SESSIONS={self.owner:self.session})
        c.original=(self.owner,self.session,c.tape,P.encode(dict(binding=c.binding,mount=c.mount,device=c.device)),c.files,c.nodes,c.names,c.absent)
        N._RETAINED[c]=c.original
    def test_actual_parent_final_accepts_real_names_files_nodes_and_absence(self):
        self.canary.close()
        self.assertEqual(self.leaf.read_bytes(),b'original')
    def test_foreign_namespace_refuses(self):
        (self.root/'foreign').touch()
        with self.assertRaisesRegex(N.Held,'namespace-tail'):self.canary.close()
    def test_appeared_original_absence_refuses(self):
        # Update only explicit fixture namespace to reach actual Parent.final absence guard.
        (self.root/'missing').touch();self.canary.names=((str(self.root),frozenset(['leaf','missing'])),)
        c=self.canary;c.original=(*c.original[:6],c.names,c.absent);N._RETAINED[c]=c.original
        with self.assertRaisesRegex(P.Held,'absence-final'):c.close()

class Constructor(unittest.TestCase):
    """Actual source constructor/exited session; owning admission and NFS rows projected."""
    pump=Exit.pump
    session=SessionExit.session
    def fixture(self):
        session=self.session();owner=session.owner
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);root=Path(self.tmp.name);root.chmod(0o700)
        leaf=root/'leaf';leaf.write_bytes(b'original');leaf.chmod(0o600)
        owner.engine=object();owner.plan=dict(nonce='original',operation=str(owner.op));seal_fixture_owner(owner)
        owner.nfs_host_modules=lambda:{'comic_nfs_parent_session.py':S}
        observed=dict(reader=dict(Name='/reader',State=dict(Running=False,Pid=0)))
        owner.stop_state=copy.deepcopy(observed['reader']['State'])
        g=dict(encode=P.encode,decode=P.decode,final=P.final,_NFS_LIVE_SESSIONS={owner:session},_NFS_SOURCE_CONTEXTS={owner:(None,None,None,P.encode(dict(library_root=str(root))),None)})
        c=object.__new__(N.RetainedObservation);c.owner=owner;c.session=session;c.g=g;c.tape=b'facts';c.binding=dict(native_grant=False);c.mount=dict(fstype='nfs4');c.device=root.stat().st_dev
        c.files=((str(leaf),tuple(P.nine(leaf.stat()))),);c.nodes=((str(root),tuple(P.five(root.stat()))),);c.names=((str(root),frozenset(['leaf'])),);c.absent=(str(root/'absent'),)
        c.original=(owner,session,c.tape,P.encode(dict(binding=c.binding,mount=c.mount,device=c.device)),c.files,c.nodes,c.names,c.absent);N._RETAINED[c]=c.original
        r=dict(module=types.SimpleNamespace(encode=P.encode),canary=c,canary_source={},phase='stopped',original={},stopped=copy.deepcopy(observed))
        r['seal']=N.seal(owner,r);N._REG[owner]=r
        return owner,session,c,g,observed,leaf
    def test_completed_original_constructor_retains_exact_vectors(self):
        owner,session,c,g,observed,leaf=self.fixture()
        with patch.object(N,'parent_module',return_value=g):value=N.StoppedNFSHandoff(N._STOPPED_KEY,owner,c,session,observed)
        self.assertEqual(value.files,c.original[4]);self.assertEqual(leaf.read_bytes(),b'original');value.close()
    def test_release_callback_cannot_drop_original_files_and_mutate_leaf(self):
        owner,session,c,g,observed,leaf=self.fixture();fired=[]
        def callback(ref):
            if not fired:fired.append(True);c.files=();leaf.write_bytes(b'foreign')
        session.g['read']=callback
        with patch.object(N,'parent_module',return_value=g),self.assertRaisesRegex(N.Held,'proxy-record'):
            N.StoppedNFSHandoff(N._STOPPED_KEY,owner,c,session,observed)
        self.assertTrue(fired)
    def test_first_module_callback_cannot_rebaseline_proxy_table(self):
        owner,session,c,g,observed,leaf=self.fixture();fired=[]
        def modules():
            if not fired:
                fired.append(True);c.files=();c.original=(*c.original[:4],c.files,*c.original[5:]);N._RETAINED[c]=c.original;leaf.write_bytes(b'foreign')
            return {'comic_nfs_parent_session.py':S}
        owner.nfs_host_modules=modules
        with patch.object(N,'parent_module',return_value=g),self.assertRaisesRegex(N.Held,'proxy-record'):
            N.StoppedNFSHandoff(N._STOPPED_KEY,owner,c,session,observed)
        self.assertTrue(fired)
    def test_missing_original_phase_registry_is_classified_held(self):
        owner,session,c,g,observed,leaf=self.fixture();del N._REG[owner]
        with patch.object(N,'parent_module',return_value=g),self.assertRaisesRegex(N.Held,'earliest-owning-phase'):
            N.StoppedNFSHandoff(N._STOPPED_KEY,owner,c,session,observed)
    def test_first_parent_callback_cannot_rebaseline_phase_record(self):
        owner,session,c,g,observed,leaf=self.fixture();fired=[]
        def parent(value):
            fired.append(True);N._REG[owner]=dict(N._REG[owner]);return g
        with patch.object(N,'parent_module',side_effect=parent),self.assertRaisesRegex(N.Held,'earliest-owning-phase'):
            N.StoppedNFSHandoff(N._STOPPED_KEY,owner,c,session,observed)
        self.assertTrue(fired)
    def test_foreign_session_callback_cannot_replace_original_proxy_session(self):
        owner,session,c,g,observed,leaf=self.fixture()
        session.g['read']=lambda ref:setattr(c,'session',object())
        with patch.object(N,'parent_module',return_value=g),self.assertRaisesRegex(N.Held,'proxy-record'):
            N.StoppedNFSHandoff(N._STOPPED_KEY,owner,c,session,observed)

class PhaseCaller(unittest.TestCase):
    """Actual producer phase method/real backup fixture; no Root UID or terminal ACK claim."""
    def fixture(self):
        import test_archive_proof_producer as q
        f=q.Controls('test_real_neutral_full_backup_eight_roles');f.setUp();self.addCleanup(f.doCleanups)
        return q,f
    def test_execute_phase_passes_exact_original_parent_mapping(self):
        q,f=self.fixture();request=f.phase();original=q.p.private_scopes;seen=[]
        def scopes(o,s,expected,restore,mapping=None):
            self.assertIs(mapping,f.parent.mapping);seen.append(True)
            return original(o,s,expected,restore,mapping)
        with patch.object(q.p,'private_scopes',side_effect=scopes):q.p.phase_custody(request,watch=f.parent.continuous)
        self.assertTrue(seen)
    def test_terminal_phase_passes_mapping_before_later_terminal_proof(self):
        q,f=self.fixture();request=f.phase();request['context']['phase']='verify-terminal';request['context']['execution_originals']={}
        original=q.p.private_scopes;seen=[]
        class BoundaryReached(Exception):pass
        def scopes(o,s,expected,restore,mapping=None):
            self.assertIs(mapping,f.parent.mapping);original(o,s,expected,restore,mapping);seen.append(True);raise BoundaryReached()
        with patch.object(q.p,'private_scopes',side_effect=scopes),self.assertRaises(BoundaryReached):q.p.phase_custody(request,watch=f.parent.continuous)
        self.assertTrue(seen)

class Stopped(unittest.TestCase):
    """Constructor prerequisites projected; actual raw files/process exit remain original."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name);root.chmod(0o700);self.library=root/'library';self.library.mkdir(mode=0o700)
        self.leaf=root/'original';self.leaf.write_bytes(b'original');self.leaf.chmod(0o600)
        process=subprocess.Popen([sys.executable,'-I','-B','-c','pass'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        pump=S.OriginalPump(process,time.monotonic()+5,lambda:None);pump.finish()
        self.addCleanup(lambda:process.wait(timeout=5));self.pump=pump
        self.rows={k:dict(Name='/'+k,State=dict(Pid=0,Running=False)) for k in ('reader','held_native','held_worker')}
        self.mount=dict(source='server:/export',target=str(root),fstype='nfs4',fsroot='/',options='rw,vers=4.2',**{'maj:min':'0:1'})
        owner=fixture_owner();self.owner=owner;owner.plan=dict(nonce='n',operation=str(owner.op));owner.engine=types.SimpleNamespace()
        owner.continuous=lambda:copy.deepcopy(self.rows);seal_fixture_owner(owner)
        self.remote=[]
        def canary(*args,**kwargs):
            self.remote.append(args);return types.SimpleNamespace(returncode=0,stdout=json.dumps({'filesystems':[self.mount]}).encode(),stderr=b'')
        owner.engine.canary=canary
        self.session=types.SimpleNamespace(successful_exit=pump.successful_exit)
        self.handoff=object.__new__(N.StoppedNFSHandoff);h=self.handoff
        h.owner,h.session=owner,self.session
        h.files=((str(self.leaf),tuple(P.nine(self.leaf.stat()))),);h.nodes=();h.names=((str(self.library),frozenset()),);h.absent=(str(root/'owned-absent'),)
        h.binding=dict(native_grant=False);h.mount=copy.deepcopy(self.mount);h.device=self.library.stat().st_dev;h.library=str(self.library);h.stopped=copy.deepcopy(self.rows)
        h.g=dict(encode=P.encode,decode=P.decode,final=P.final,nfs_remote_guard=lambda engine:None,same_runtime=lambda a,b:a==b)
        h.origin=(owner,owner.core,owner.engine,owner.thread,'n',self.session,object(),pump.successful_exit())
        h.tape=P.encode(dict(binding=h.binding,mount=h.mount,device=h.device,stopped=h.stopped,library=h.library))
        N._STOPPED_HANDOFFS[h]=(h.g,h.origin,h.tape,h.files,h.nodes,h.names,h.absent)
    def test_delayed_backup_over_child120_budget_uses_only_original_exit(self):
        with patch.object(S.time,'monotonic',return_value=self.pump.deadline+121):
            self.assertEqual(self.handoff.current(stopped=True),list(self.rows.values()))
        self.assertEqual(len(self.remote),1)
    def test_exit_callback_cannot_drop_retained_vectors(self):
        fired=[];original=self.session.successful_exit
        def callback():
            if not fired:fired.append(True);self.handoff.files=();self.leaf.write_bytes(b'foreign')
            return original()
        self.session.successful_exit=callback
        with self.assertRaisesRegex(N.Held,'exit-custody'):self.handoff.close()
        self.assertTrue(fired)
    def test_changed_stopped_actor_refuses_before_export_query(self):
        self.rows['reader']['State']['Pid']=99
        with self.assertRaisesRegex(N.Held,'current-roles'):self.handoff.current(stopped=True)
        self.assertEqual(self.remote,[])
    def test_changed_original_export_refuses(self):
        self.mount['source']='foreign:/export'
        with self.assertRaisesRegex(N.Held,'current-export'):self.handoff.current(stopped=True)
    def test_original_leaf_or_owned_absence_drift_refuses(self):
        self.leaf.write_bytes(b'replaced')
        with self.assertRaises(P.Held):self.handoff.current(stopped=True)
    def test_no_active_or_unknown_exit_or_foreign_core_route(self):
        with self.assertRaises(N.Held):self.handoff.current(stopped=False)
        self.owner.core=b'foreign'
        with self.assertRaises(N.Held):self.handoff.close()
    def test_parent_expiry_and_remote_window_hold_are_not_bypassed(self):
        def held():raise P.Held('original-parent-expired')
        self.owner.left=held
        with self.assertRaisesRegex(P.Held,'parent-expired'):self.handoff.current(stopped=True)
    def test_final_callback_cannot_add_foreign_original_namespace(self):
        original=self.handoff.g['final'];fired=[]
        def callback(files,nodes,absent):
            original(files,nodes,absent);(self.library/'foreign').touch();fired.append(True)
        self.handoff.g['final']=callback
        with self.assertRaisesRegex(N.Held,'final-namespace'):self.handoff.close()
        self.assertTrue(fired)
    def test_remote_guard_holds_before_any_observation(self):
        def held(engine):raise P.Held('Writer-still-held')
        self.handoff.g['nfs_remote_guard']=held
        with self.assertRaisesRegex(P.Held,'Writer-still-held'):self.handoff.current(stopped=True)
        self.assertEqual(self.remote,[])
    def test_unregistered_handoff_cannot_admit(self):
        del N._STOPPED_HANDOFFS[self.handoff]
        with self.assertRaises(N.Held):self.handoff.close()


# Exact source-mode startup/terminal transition controls. The private author
# capsule retains original-method RED evidence; these portable controls exercise
# the actual maintained Parent/session methods and owning phase/profile guards.
import ast
import hashlib
import importlib.util
p=P
s=S
BASE=Path(__file__).parent
def _started_load(path,name):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def _started_model():
 cid='a'*64
 created=dict(Id=cid,Name='/source-model',Image='sha256:'+'b'*64,Path='/lsiopy/bin/python3',Args=['-I','-B','probe.py'],Config=dict(User='1000:1000',Labels={},ExposedPorts={'8090/tcp':{}}),HostConfig=dict(NetworkMode='none',OomKillDisable=False,ReadonlyRootfs=True,Privileged=False,CapDrop=['ALL'],PortBindings={}),Mounts=[dict(Type='bind',Source='/fixture',Destination='/_operation',RW=False)],NetworkSettings=dict(Ports={},SandboxID='',SandboxKey='',Networks={'none':dict(EndpointID='',NetworkID='',IPAddress='',Gateway='',MacAddress='')}))
 started=copy.deepcopy(created);started['HostConfig']['OomKillDisable']=None;started['NetworkSettings'].update(SandboxID='e'*64,SandboxKey='/var/run/docker/netns/'+'e'*12);started['NetworkSettings']['Networks']['none'].update(EndpointID='c'*64,NetworkID='d'*64)
 terminal=copy.deepcopy(started);terminal['NetworkSettings'].update(SandboxID='',SandboxKey='');terminal['NetworkSettings']['Networks']['none']['EndpointID']=''
 def state(status):return dict(Status=status,Running=status=='running',Paused=False,Restarting=False,OOMKilled=False,Dead=False,Pid=os.getpid() if status=='running' else 0,ExitCode=0,Error='',StartedAt='same-start',FinishedAt='finish' if status=='exited' else '')
 for row,status in ((created,'created'),(started,'running'),(terminal,'exited')):row['State']=state(status)
 return cid,created,started,terminal

class StartedProfiles(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.root.chmod(0o700)
 def namespace(self,current=None,after=None):
  cid,created,started,terminal=_started_model();current=copy.deepcopy(current or started);after=copy.deepcopy(after or current)
  owner=object.__new__(p.LifecycleParent);owner.op=self.root/'operation';owner.op.mkdir(mode=0o700);owner.op_fact=tuple(p.five(owner.op.stat()));owner.generated={};owner.plan=dict(nonce='f'*64);owner.left=lambda:None
  p._GENERATED[owner]=p.encode({})
  def put(name,raw):
   path=self.root/name;path.write_bytes(raw);path.chmod(0o600);return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),signature9=p.nine(path.stat()))
  ref=put('source.py',b'# exact source fixture\n');plan=put('plan.json',b'{}');bootstrap=put('roles.json',p.encode(dict(version=1,kind='parent-original-current-three-role-bootstrap',plan=plan,source=ref,roles={},ancestors={})))
  owner.mapping=types.SimpleNamespace(original_ref=lambda value:value)
  dialogue=types.SimpleNamespace(sequence=0);session=types.SimpleNamespace(cid=cid,created_static=p.encode(p.static(created)),lease_replies=types.SimpleNamespace(lease=None),engine_replies=dialogue,close=lambda:None)
  p._NFS_LIVE_SESSIONS[owner]=session;p._NFS_PACKET_ROWS[owner]=(None,None,bootstrap)
  calls=iter((current,after));owner.inspect=lambda value:copy.deepcopy(next(calls))
  frame=dict(type='nfs-role-namespace',nonce=owner.plan['nonce'],sequence=1,payload={})
  return owner,session,frame,created,started
 def test_namespace_actual_method_seals_running_profile_and_original_created(self):
  owner,session,frame,created,started=self.namespace();answer=owner.nfs_role_namespace_reply(frame)
  self.assertEqual(answer['sequence'],1);self.assertEqual(len(p._NFS_CHILD_EPOCHS[owner]),6);self.assertEqual(p._NFS_CHILD_EPOCHS[owner][5],p.encode(p.static(started)));self.assertEqual(session.created_static,p.encode(p.static(created)))
  diagnostic=p.decode(p.read(owner.generated[str(owner.op/'nfs-first-started-profile.json')]))
  self.assertEqual(diagnostic['profile'],started)
 def test_namespace_foreign_static_or_boolean_refuses_before_seal_with_diagnostic(self):
  for kind in ('port','bool','id'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
    originalroot=self.root;self.root=Path(tmp);_,_,row,_=_started_model()
    if kind=='port':row['NetworkSettings']['Ports']={'8090/tcp':None}
    elif kind=='bool':row['HostConfig']['Privileged']=0
    else:row['Id']='b'*64
    owner,session,frame,_,_=self.namespace(row)
    with self.assertRaisesRegex(p.Held,'own-running-child'):owner.nfs_role_namespace_reply(frame)
    self.assertNotIn(owner,p._NFS_CHILD_EPOCHS);self.assertEqual(p.decode(p.read(owner.generated[str(owner.op/'nfs-first-started-profile.json')]))['profile'],row);self.root=originalroot
 def test_namespace_late_profile_or_startedat_drift_refuses(self):
  for kind in ('static','epoch'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
    originalroot=self.root;self.root=Path(tmp);_,_,row,_=_started_model()
    if kind=='static':row['Config']['User']='0:0'
    else:row['State']['StartedAt']='other-start'
    owner,session,frame,_,_=self.namespace(after=row)
    with self.assertRaisesRegex(p.Held,'original-child-epoch'):owner.nfs_role_namespace_reply(frame)
    self.assertNotIn(owner,p._NFS_CHILD_EPOCHS);self.root=originalroot
 def test_retained_session_checks_new_running_static_and_epoch(self):
  owner,session,frame,created,started=self.namespace();owner.nfs_role_namespace_reply(frame)
  actual=object.__new__(s.RetainedChild);actual.owner=owner;actual.cid=session.cid;actual.created_static=session.created_static;actual.lease_replies=types.SimpleNamespace(lease=None);actual.g=p.__dict__;actual.close=lambda:None
  row=p._NFS_CHILD_EPOCHS[owner];p._NFS_CHILD_EPOCHS[owner]=(actual,*row[1:]);owner.inspect=lambda cid:copy.deepcopy(started)
  self.assertEqual(actual.profile_after_release(),started)
  for kind in ('static','epoch'):
   changed=copy.deepcopy(started)
   if kind=='static':changed['HostConfig']['OomKillDisable']=False
   else:changed['State']['StartedAt']='restarted'
   owner.inspect=lambda cid,value=changed:copy.deepcopy(value)
   with self.assertRaises(s.Held):actual.profile_after_release()


class PhaseProfiles(unittest.TestCase):
 def phase(self,module,*,late=False):
  t=_started_load(BASE/'test_reader_lifecycle_parent.py','existing_phase_controls');t.p=module
  fixture=t.Tests();fixture.setUp();self.addCleanup(fixture.tearDown) if 'tearDown' in t.Tests.__dict__ else None
  self.addCleanup(fixture.doCleanups);self.addCleanup(fixture.temp.cleanup)
  owner,ref,command,calls=fixture.child_fixture();engine=owner.engine;original=engine.run
  cid,created,started,exited=_started_model();counts={}
  def run(args,seconds):
   raw=original(args,seconds)
   if args[0]=='inspect':
    row=module.decode(raw)[0]
    if row['Id']=='4'*64:
     status=row['State']['Status'];template={'created':created,'running':started,'exited':exited}[status]
     row['NetworkSettings']=copy.deepcopy(template['NetworkSettings']);row['HostConfig']['OomKillDisable']=template['HostConfig']['OomKillDisable']
     counts[status]=counts.get(status,0)+1
     if late and status=='exited':row['Config']['User']='0:0'
    raw=module.encode([row])
   return raw
  engine.run=run
  return owner,ref,command,fixture
 def test_actual_full_phase_start_and_terminal_green(self):
  owner,ref,cmd,fixture=self.phase(p);result=owner.child_phase('backup',ref,cmd)
  self.assertEqual(result['phase'],'backup')
  for stage in ('created','first-started','first-exited'):
   path=owner.op/('backup-'+stage+'-profile.json');self.assertTrue(path.is_file());self.assertFalse(p.decode(p.read(owner.generated[str(path)]))['automatic_replay'])
 def test_actual_full_phase_refuses_late_foreign_terminal_and_retains_diagnostics(self):
  owner,ref,cmd,fixture=self.phase(p,late=True)
  with self.assertRaisesRegex(p.Held,'child-final-static'):owner.child_phase('backup',ref,cmd)
  self.assertEqual(p.decode(p.read(owner.generated[str(owner.op/'backup-first-exited-profile.json')]))['profile']['Config']['User'],'0:0')

class WorkerProfiles(unittest.TestCase):
 def worker(self):
  tree=ast.parse(Path(p.__file__).read_text());outer=next(n for n in ast.walk(tree)if isinstance(n,ast.FunctionDef)and n.name=='observe_archive_worker');fn=copy.deepcopy(next(n for n in outer.body if isinstance(n,ast.FunctionDef)and n.name=='child_profile'))
  # Extract the ACTUAL nested source, preserving its nonlocal state machine.
  wrapper=ast.parse("def factory(self,cid,created_static,protocol,intent):\n running=None;started_static=None;terminal_static=None\n return None\n").body[0]
  wrapper.body[-1:]=[fn,ast.Return(ast.Tuple(elts=[ast.Name(id='child_profile',ctx=ast.Load()),ast.Lambda(args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]),body=ast.Tuple(elts=[ast.Name(id=n,ctx=ast.Load())for n in ('running','started_static','terminal_static')],ctx=ast.Load()))],ctx=ast.Load()))]
  scope=p.__dict__.copy();exec(compile(ast.fix_missing_locations(ast.Module(body=[wrapper],type_ignores=[])),'actual-worker-profile-extraction','exec'),scope)
  cid,created,started,exited=_started_model()
  for row in(created,started,exited):
   row['Config'].update(Entrypoint=['python3'],Cmd=['worker.py'],OpenStdin=True,Tty=False,Labels={'com.homelab.reader.worker-observer':'fixture'})
   row['HostConfig'].update(IpcMode='private',PidMode='',SecurityOpt=['no-new-privileges'],PidsLimit=32,Memory=768*1024**2,MemorySwap=768*1024**2,NanoCpus=500000000,RestartPolicy=dict(Name='no'))
  owner=object.__new__(p.LifecycleParent);self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);owner.op=Path(self.temp.name);owner.op_fact=tuple(p.five(owner.op.stat()));owner.generated={};owner.left=lambda:None
  intent=((),('worker.py',),(('/fixture','/_operation'),),'fixture',{},(),created['Image'],0);protocol=types.SimpleNamespace(step=0)
  check,state=scope['factory'](owner,cid,p.static(created),protocol,intent)
  return owner,check,state,protocol,created,started,exited
 def test_actual_nested_worker_profiles_seal_first_start_then_first_exit(self):
  owner,check,state,protocol,created,started,exited=self.worker();check(created);check(started);check(started);protocol.step=4;check(exited);check(exited)
  self.assertEqual(state()[1],p.encode(p.static(started)));self.assertEqual(state()[2],p.encode(p.static(exited)))
  # Actual cleanup consumer uses only the Parent-sealed terminal row; the
  # original Created registry stays unchanged. No Docker command is executed.
  engine=object.__new__(p.ScopedDocker);cid=created['Id'];owned=('fixture',copy.deepcopy(p.static(created)))
  p._OBSERVER_OWNED[engine]={cid:owned};p._OBSERVER_RELEASED[engine]={cid:(object(),{},state()[2])}
  from unittest.mock import patch
  with patch.object(p.subprocess,'run',return_value=types.SimpleNamespace(returncode=0,stdout=b'',stderr=b'')) as run:
   engine.remove_observer(cid,exited);self.assertEqual(run.call_count,1)
   foreign=copy.deepcopy(exited);foreign['Config']['User']='0:0'
   with self.assertRaisesRegex(p.Held,'worker-owned-exited-cleanup'):engine.remove_observer(cid,foreign)
   self.assertEqual(run.call_count,1)
  self.assertEqual(p._OBSERVER_OWNED[engine][cid],owned)
  self.assertNotIn(str(owner.op/'worker-first-started-profile.json'),owner.generated)
  changed=copy.deepcopy(exited);changed['NetworkSettings']['Networks']['none']['NetworkID']='f'*64
  with self.assertRaisesRegex(p.Held,'static-through-dialogue'):check(changed)
 def test_worker_missing_start_invalid_terminal_and_false_boolean_refuse(self):
  owner,check,state,protocol,created,started,exited=self.worker();protocol.step=4
  with self.assertRaisesRegex(p.Held,'started-to-exited'):check(exited)
  # Fresh owner: rejection preserves first current row and cannot seal a baseline.
  owner,check,state,protocol,created,started,exited=self.worker();changed=copy.deepcopy(started);changed['HostConfig']['Privileged']=0
  with self.assertRaisesRegex(p.Held,'created-to-started'):check(changed)
  self.assertIsNone(state()[0]);self.assertIsNone(state()[1])



class ProfileContractSeal(unittest.TestCase):
 def test_actual_parent_methods_reject_explicit_foreign_or_none_pair(self):
  owner=object.__new__(p.LifecycleParent);calls=[]
  def foreign():calls.append(True)
  for name in ('left','nfs_host_modules'):
   method=getattr(p.LifecycleParent,name)
   for guard,code in ((foreign,foreign.__code__),(None,None)):
    with self.subTest(method=name,none=guard is None):
     with self.assertRaisesRegex(p.Held,'original-profile-binding'):
      method(owner,_profile_guard=guard,_profile_code=code)
     self.assertEqual(calls,[])
 def test_same_globals_replacement_clone_and_inplace_code_refuse(self):
  import types
  cid,created,started,terminal=_started_model()
  original=p.none_network_started_static;token=p.none_network_profile_contract()
  self.assertIs(p.none_network_profile_contract(),token)
  self.assertTrue(p.checked_none_network_started_static(p.static(created),p.static(started),cid))
  self.assertTrue(p.checked_none_network_exited_static(p.static(started),p.static(terminal),cid))
  clone=types.FunctionType(original.__code__,original.__globals__)
  for replacement in (clone,types.FunctionType((lambda *args:True).__code__,original.__globals__)):
   p.none_network_started_static=replacement
   try:
    with self.assertRaisesRegex(p.Held,'original-profile-contract'):p.checked_none_network_started_static(p.static(created),p.static(started),cid)
   finally:p.none_network_started_static=original
  code=original.__code__;original.__code__=(lambda *args:True).__code__
  try:
   with self.assertRaisesRegex(p.Held,'original-profile-contract'):p.none_network_profile_contract()
  finally:original.__code__=code
  # Same-globals foreign predicate cannot authorize an actual Parent phase.
  fixture=PhaseProfiles();owner,ref,cmd,_=fixture.phase(p)
  p.none_network_started_static=types.FunctionType((lambda *args:True).__code__,original.__globals__)
  try:
   with self.assertRaisesRegex(p.Held,'original-profile-contract'):owner.child_phase('backup',ref,cmd)
  finally:p.none_network_started_static=original;fixture.doCleanups()
 def test_private_encoder_dependency_prefix_and_checked_api_refuse(self):
  cid,created,started,_=_started_model()
  for name,replacement in (('_none_network_profile_bytes',lambda value:b'foreign'),('NONE_NETWORK_SANDBOX_PARENT','/foreign'),('checked_none_network_started_static',lambda *args:True)):
   original=getattr(p,name);setattr(p,name,replacement)
   try:
    with self.assertRaisesRegex(p.Held,'original-profile-contract'):p.none_network_profile_contract()
   finally:setattr(p,name,original)
  for module,name in ((p.json,'dumps'),(p.copy,'deepcopy'),(p.re,'fullmatch')):
   original=getattr(module,name);setattr(module,name,lambda *args,**kwargs:None)
   try:
    with self.assertRaisesRegex(p.Held,'original-profile-contract'):p.none_network_profile_contract()
   finally:setattr(module,name,original)
  self.assertTrue(p.checked_none_network_started_static(p.static(created),p.static(started),cid))
 def test_callback_mutation_is_closed_after_each_predicate(self):
  # A deterministic Python callback mutates after the pure predicate's last
  # instruction; the checked call must refuse instead of returning its True.
  cid,created,started,terminal=_started_model()
  for pure,checked,left,right in ((p.none_network_started_static,p.checked_none_network_started_static,created,started),(p.none_network_exited_static,p.checked_none_network_exited_static,started,terminal)):
   for kind in ('prefix','dependency'):
    prefix=p.NONE_NETWORK_SANDBOX_PARENT;dependency=p.json.dumps;oldtrace=sys.gettrace();seen=[]
    def callback(frame,event,arg):
     if frame.f_code is pure.__code__ and event=='return' and not seen:
      seen.append(True)
      if kind=='prefix':p.NONE_NETWORK_SANDBOX_PARENT='/foreign'
      else:p.json.dumps=lambda *args,**kwargs:'foreign'
     return callback
    try:
     sys.settrace(callback)
     with self.assertRaisesRegex(p.Held,'original-profile-contract'):checked(p.static(left),p.static(right),cid)
    finally:sys.settrace(oldtrace);p.NONE_NETWORK_SANDBOX_PARENT=prefix;p.json.dumps=dependency
    self.assertEqual(seen,[True])



# Typed startup/exit relation models; no runtime or publication authority.
h=P
CID='a'*64


PARENT='/var/run/docker/netns'  # Root confirmed this exact relation; rows remain synthetic.


def rows():
    created=dict(Id=CID,Name='/owned-none-model',Image='sha256:'+'b'*64,
        Path='/lsiopy/bin/python3',Args=['-I','-B','probe.py'],
        Config=dict(User='1000:1000',Entrypoint=['/lsiopy/bin/python3'],Cmd=['-I','-B','probe.py'],
                    Labels={'owned':'fixture'},ExposedPorts={'8090/tcp':{}}),
        HostConfig=dict(NetworkMode='none',OomKillDisable=False,ReadonlyRootfs=True,
                        Privileged=False,CapDrop=['ALL'],PortBindings={}),
        Mounts=[dict(Type='bind',Source='/fixture/original',Destination='/_operation',RW=False)],
        NetworkSettings=dict(Ports={},SandboxID='',SandboxKey='',Networks={'none':dict(
            EndpointID='',NetworkID='',IPAddress='',Gateway='',MacAddress='')}))
    started=copy.deepcopy(created);started['HostConfig']['OomKillDisable']=None
    started['NetworkSettings']['Networks']['none'].update(EndpointID='c'*64,NetworkID='d'*64)
    started['NetworkSettings'].update(SandboxID='e'*64,SandboxKey=PARENT+'/'+'e'*12)
    return created,started


class Controls(unittest.TestCase):
    def setUp(self):
        self.old,self.new=rows();self.prefix=patch.object(h,'NONE_NETWORK_SANDBOX_PARENT',PARENT);self.prefix.start();self.addCleanup(self.prefix.stop)
    def test_exact_five_fields_and_no_input_mutation(self):
        old,new=copy.deepcopy(self.old),copy.deepcopy(self.new)
        self.assertNotEqual(self.old,self.new)  # Predecessor exact-static comparison is RED.
        self.assertTrue(h.none_network_started_static(self.old,self.new,CID))
        self.assertEqual(self.old,old);self.assertEqual(self.new,new)
    def test_equal_none_network_profiles_retain_legacy_success(self):
        self.assertTrue(h.none_network_started_static(self.old,copy.deepcopy(self.old),CID))
        self.assertTrue(h.none_network_started_static(self.new,copy.deepcopy(self.new),CID))
    def test_unbound_prefix_refuses_transition(self):
        with patch.object(h,'NONE_NETWORK_SANDBOX_PARENT',None):
            self.assertFalse(h.none_network_started_static(self.old,self.new,CID))
    def test_each_missing_transition_refuses(self):
        paths=[('HostConfig','OomKillDisable'),('NetworkSettings','SandboxID'),('NetworkSettings','SandboxKey'),('NetworkSettings','Networks','none','EndpointID'),('NetworkSettings','Networks','none','NetworkID')]
        for path in paths:
            with self.subTest(path=path):
                value=copy.deepcopy(self.new);left=self.old;right=value
                for key in path[:-1]:left=left[key];right=right[key]
                right[path[-1]]=left[path[-1]]
                self.assertFalse(h.none_network_started_static(self.old,value,CID))
    def test_wrong_identity_and_each_top_level_drift_refuse(self):
        for field,value in [('Id','f'*64),('Name','/foreign'),('Image','sha256:'+'f'*64),('Path','foreign'),('Args',['foreign']),('Config',{}),('HostConfig',{}),('Mounts',[]),('NetworkSettings',{})]:
            with self.subTest(field=field):
                row=copy.deepcopy(self.new);row[field]=value;self.assertFalse(h.none_network_started_static(self.old,row,CID));self.assertFalse(h.none_network_started_static(self.new,row,CID))
        self.assertFalse(h.none_network_started_static(self.old,self.new,'f'*64))
    def test_each_unrelated_nested_field_refuses(self):
        changes=[(('Config','User'),'0:0'),(('Config','Labels'),{'foreign':'fixture'}),
          (('Config','ExposedPorts'),{}),(('HostConfig','ReadonlyRootfs'),False),
          (('HostConfig','Privileged'),True),(('HostConfig','CapDrop'),[]),
          (('HostConfig','PortBindings'),{'8090/tcp':[{'HostPort':'8090'}]}),
          (('NetworkSettings','Ports'),{'8090/tcp':None}),
          (('NetworkSettings','Networks','none','IPAddress'),'127.0.0.1'),
          (('NetworkSettings','Networks','none','Gateway'),'127.0.0.1'),
          (('NetworkSettings','Networks','none','MacAddress'),'02:00:00:00:00:01')]
        for path,value in changes:
            with self.subTest(path=path):
                row=copy.deepcopy(self.new);target=row
                for key in path[:-1]:target=target[key]
                target[path[-1]]=value;self.assertFalse(h.none_network_started_static(self.old,row,CID));self.assertFalse(h.none_network_started_static(self.new,row,CID))
    def test_malformed_id_or_sandbox_relation_refuses(self):
        for key in ('EndpointID','NetworkID'):
            for value in ('','A'*64,'x'*64,'c'*63,None):
                row=copy.deepcopy(self.new);row['NetworkSettings']['Networks']['none'][key]=value
                self.assertFalse(h.none_network_started_static(self.old,row,CID))
        for value in ('/untrusted/'+'e'*12,PARENT+'/'+'f'*12,PARENT+'/../'+'e'*12,PARENT+'/'+'e'*64,None):
            row=copy.deepcopy(self.new);row['NetworkSettings']['SandboxKey']=value
            self.assertFalse(h.none_network_started_static(self.old,row,CID))
    def test_missing_extra_keys_and_extra_network_refuse(self):
        for base in ('HostConfig','NetworkSettings'):
            row=copy.deepcopy(self.new);row[base]['unknown']=1
            self.assertFalse(h.none_network_started_static(self.old,row,CID))
        row=copy.deepcopy(self.new);row['NetworkSettings']['Networks']['foreign']={}
        self.assertFalse(h.none_network_started_static(self.old,row,CID))
        row=copy.deepcopy(self.new);del row['HostConfig']['OomKillDisable']
        self.assertFalse(h.none_network_started_static(self.old,row,CID))
    def test_reverse_or_refresh_of_sealed_running_profile_refuses(self):
        self.assertFalse(h.none_network_started_static(self.new,self.old,CID))
        for section,key,value in [('NetworkSettings','SandboxID','f'*64),('NetworkSettings','SandboxKey',PARENT+'/'+'f'*12),('HostConfig','OomKillDisable',False)]:
            row=copy.deepcopy(self.new);row[section][key]=value
            self.assertFalse(h.none_network_started_static(self.new,row,CID))
    def test_oom_true_missing_or_other_transition_refuses(self):
        for before,after in ((True,None),(None,None),(False,False),(False,True)):
            old,new=copy.deepcopy(self.old),copy.deepcopy(self.new);old['HostConfig']['OomKillDisable']=before;new['HostConfig']['OomKillDisable']=after
            self.assertFalse(h.none_network_started_static(old,new,CID))


def exited(running):
    result=copy.deepcopy(running)
    result['NetworkSettings']['Networks']['none']['EndpointID']=''
    result['NetworkSettings']['SandboxID']=''
    result['NetworkSettings']['SandboxKey']=''
    return result


class ExitControls(unittest.TestCase):
    def setUp(self):
        self.created,self.running=rows();self.terminal=exited(self.running)
    def test_exact_three_fields_preserve_network_id_and_inputs(self):
        before,after=copy.deepcopy(self.running),copy.deepcopy(self.terminal)
        self.assertNotEqual(before,after)
        self.assertTrue(h.none_network_exited_static(self.running,self.terminal,CID))
        self.assertEqual(self.running,before);self.assertEqual(self.terminal,after)
        self.assertEqual(before['NetworkSettings']['Networks']['none']['NetworkID'],after['NetworkSettings']['Networks']['none']['NetworkID'])
        self.assertFalse(h.none_network_started_static(before,after,CID))
    def test_exact_equality_preserved_but_reverse_and_created_input_refuse(self):
        self.assertTrue(h.none_network_exited_static(self.running,copy.deepcopy(self.running),CID))
        self.assertTrue(h.none_network_exited_static(self.terminal,copy.deepcopy(self.terminal),CID))
        self.assertFalse(h.none_network_exited_static(self.terminal,self.running,CID))
        self.assertFalse(h.none_network_exited_static(self.created,self.terminal,CID))
    def test_partial_teardown_refuses(self):
        for path in [('NetworkSettings','SandboxID'),('NetworkSettings','SandboxKey'),('NetworkSettings','Networks','none','EndpointID')]:
            with self.subTest(path=path):
                row=copy.deepcopy(self.terminal);old=self.running;target=row
                for k in path[:-1]:old=old[k];target=target[k]
                target[path[-1]]=old[path[-1]]
                self.assertFalse(h.none_network_exited_static(self.running,row,CID))
    def test_network_id_clear_or_change_and_any_other_static_drift_refuse(self):
        changes=[(('NetworkSettings','Networks','none','NetworkID'),''),
          (('NetworkSettings','Networks','none','NetworkID'),'f'*64),
          (('NetworkSettings','Networks','none','IPAddress'),'127.0.0.1'),
          (('NetworkSettings','Ports'),{'8090/tcp':None}),
          (('HostConfig','OomKillDisable'),False),(('HostConfig','Privileged'),True),
          (('HostConfig','ReadonlyRootfs'),False),(('Config','User'),'0:0'),
          (('Config','Labels'),{}),(('Mounts',),[]),(('Image',),'sha256:'+'f'*64),
          (('Name',),'/foreign'),(('Args',),[])]
        for path,value in changes:
            with self.subTest(path=path):
                row=copy.deepcopy(self.terminal);target=row
                for k in path[:-1]:target=target[k]
                target[path[-1]]=value
                self.assertFalse(h.none_network_exited_static(self.running,row,CID))
        self.assertFalse(h.none_network_exited_static(self.running,self.terminal,'f'*64))
    def test_malformed_original_relation_or_prefix_refuses(self):
        for value in ('','A'*64,'x'*64,None):
            row=copy.deepcopy(self.running);row['NetworkSettings']['SandboxID']=value
            self.assertFalse(h.none_network_exited_static(row,self.terminal,CID))
        row=copy.deepcopy(self.running);row['NetworkSettings']['SandboxKey']='/foreign/'+'e'*12
        self.assertFalse(h.none_network_exited_static(row,self.terminal,CID))
        with patch.object(h,'NONE_NETWORK_SANDBOX_PARENT',None):
            self.assertFalse(h.none_network_exited_static(self.running,self.terminal,CID))
    def test_missing_or_extra_keys_networks_refuse(self):
        row=copy.deepcopy(self.terminal);del row['NetworkSettings']['SandboxID']
        self.assertFalse(h.none_network_exited_static(self.running,row,CID))
        row=copy.deepcopy(self.terminal);row['NetworkSettings']['Networks']['bridge']={}
        self.assertFalse(h.none_network_exited_static(self.running,row,CID))
        row=copy.deepcopy(self.terminal);row['State']={'Status':'exited'}
        self.assertFalse(h.none_network_exited_static(self.running,row,CID))


class TypedControls(unittest.TestCase):
    def test_bool_integer_aliases_refuse_equality_and_startup_expected_paths(self):
        for old_value,new_value in ((True,1),(False,0)):
            created,running=rows()
            created['Config']['UnrelatedBoolean']=old_value
            running['Config']['UnrelatedBoolean']=new_value
            self.assertEqual(old_value,new_value)  # The predecessor's Python alias.
            self.assertFalse(h.none_network_started_static(created,running,CID))
            same=copy.deepcopy(created);same['Config']['UnrelatedBoolean']=new_value
            self.assertEqual(created,same)
            self.assertFalse(h.none_network_started_static(created,same,CID))
    def test_bool_integer_aliases_refuse_exit_expected_and_equal_paths(self):
        for old_value,new_value in ((True,1),(False,0)):
            _,running=rows();running['Config']['UnrelatedBoolean']=old_value
            terminal=exited(running);terminal['Config']['UnrelatedBoolean']=new_value
            self.assertFalse(h.none_network_exited_static(running,terminal,CID))
            same=copy.deepcopy(running);same['Config']['UnrelatedBoolean']=new_value
            self.assertEqual(running,same)
            self.assertFalse(h.none_network_exited_static(running,same,CID))
    def test_nonfinite_nonjson_and_cyclic_profiles_refuse_without_exception(self):
        values=(float('nan'),float('inf'),float('-inf'),object(),b'not-json',{1,2},complex(1,2))
        for value in values:
            with self.subTest(kind=type(value).__name__):
                created,running=rows();created['Config']['Invalid']=value;running['Config']['Invalid']=value
                self.assertFalse(h.none_network_started_static(created,created,CID))
                self.assertFalse(h.none_network_started_static(created,running,CID))
                self.assertFalse(h.none_network_exited_static(running,running,CID))
                self.assertFalse(h.none_network_exited_static(running,exited(running),CID))
        created,_=rows();created['Config']['Cycle']=created
        self.assertFalse(h.none_network_started_static(created,created,CID))
        self.assertFalse(h.none_network_exited_static(created,created,CID))
    def test_encoding_matches_exact_parent_contract(self):
        for value in (rows()[0],rows()[1],exited(rows()[1])):
            expected=json.dumps(value,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()
            self.assertEqual(h._none_network_profile_bytes(value),expected)
        self.assertNotEqual(h._none_network_profile_bytes({'v':True}),h._none_network_profile_bytes({'v':1}))
        self.assertNotEqual(h._none_network_profile_bytes({'v':False}),h._none_network_profile_bytes({'v':0}))


if __name__=='__main__':unittest.main()
