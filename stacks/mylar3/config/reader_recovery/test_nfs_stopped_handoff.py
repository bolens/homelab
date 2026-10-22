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

if __name__=='__main__':unittest.main()
