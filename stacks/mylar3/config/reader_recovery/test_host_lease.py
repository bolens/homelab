"""Real helper/Popen/FIFO/Writer controls; Docker/profile launch remains unrun."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import fcntl
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('hostlease',ROOT/'comic_nfs_host_lease.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
HELPER=ROOT/'comic_negative_nfs_active_lifecycle.py'
WRITER=ROOT.parent/'media_writer.py'
SHA=hashlib.sha256(WRITER.read_bytes()).hexdigest()
w=importlib.util.spec_from_file_location('real_writer',WRITER);writer=importlib.util.module_from_spec(w);exec(compile(WRITER.read_bytes(),str(WRITER),'exec'),writer.__dict__)

@unittest.skipUnless(os.geteuid()==1000 and os.getegid()==1000,'genuine UID1000 Writer/helper required')
class RealLease(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)/'writer';writer.Writer(self.root,create=True)
        self.processes=[];self.addCleanup(self.cleanup)
    def cleanup(self):
        for p in self.processes:
            for s in (p.stdin,p.stdout,p.stderr):
                if s is not None:s.close()
            try:p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.terminate();p.wait(timeout=3)
    def launch(self,owner=None):
        token='a'*64
        p=subprocess.Popen([sys.executable,'-I','-B',str(HELPER),'--lease-child','--writer-source',str(WRITER),'--writer-sha256',SHA,'--writer-root',str(self.root),'--token',token],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.processes.append(p);c=m.LeaseChannel(p,token,self.root,SHA,10,owner=owner);c.receive('held');return c
    def test_actual_release_closes_owner_geometry_vectors_before_and_after_ACK(self):
        from unittest import mock
        import threading
        import comic_reader_lifecycle_parent as parent
        common=Path(self.tmp.name)/('archive-publication-'+'c'*64);common.mkdir(mode=0o711);common.chmod(0o711)
        (common/'L').mkdir(mode=0o700);(common/'R').mkdir(mode=0o700)
        media=common/'L'/'original';media.write_bytes(b'original')
        geometry=dict(version=2,kind='searchable-common-root-nfs',**{role:dict(path=str(path),signature9=parent.nine(path.lstat())) for role,path in (('common_root',common),('library',common/'L'),('retention',common/'R'))})
        owner=object.__new__(parent.LifecycleParent);owner.thread=threading.get_ident();owner.core=b'explicit-source-fixture';owner.source_ref=dict(path=parent.__file__)
        parent._CORES[owner]=owner.core;uid=[0];events=[]
        def switch(real,effective,saved):uid[0]=effective;events.append(effective)
        with mock.patch.object(parent.os,'getresuid',side_effect=lambda:(0,uid[0],0)),mock.patch.object(parent.os,'getresgid',return_value=(0,0,0)),mock.patch.object(parent.os,'getgroups',return_value=[0]),mock.patch.object(parent.os,'setresuid',side_effect=switch):
            actor=parent.GeometryOwnerReads(geometry);parent._OWNER_READS=actor
            try:
                channel=self.launch(owner=owner);events.clear();real_write=parent.os.write
                import comic_nfs_lease_session as session
                from types import SimpleNamespace
                owner.files={str(media):parent.nine(media.stat())};owner.nodes={str(common/'L'):parent.five((common/'L').stat())}
                absent=(str(common/'R'/'private'/'probe'),str(common/'R'/'private'))
                dialogue=SimpleNamespace(owner=owner,close=lambda:None,nonce='a'*64,sequence=0)
                lease=SimpleNamespace(original=lambda:None,channel=channel,release_after_absence=lambda paths,**kw:channel.release(paths,kw['original_files'],kw['original_nodes']))
                replies=object.__new__(session.HostLeaseReplies);replies.dialogue=dialogue;replies.lease=lease;replies.absent=replies.absence_tape=absent;replies.done=False
                real_lstat=parent.os.lstat
                def squashed(path,*args,**kwargs):
                    if uid[0]==0 and str(path) in absent:raise PermissionError('projected NFS root squash')
                    return real_lstat(path,*args,**kwargs)
                def write(fd,data):
                    if b'"action":"release"' in data:self.assertEqual(uid[0],0)
                    return real_write(fd,data)
                # Session/lease construction is projected; the helper, pipes,
                # Writer, release and owning stat observer are real.
                with mock.patch.object(parent.os,'write',side_effect=write),mock.patch.object(parent.os,'lstat',side_effect=squashed):
                    raw=replies.accept(dict(type='nfs-lease',nonce=dialogue.nonce,sequence=1,payload=dict(operation='release',absent=list(absent),empty=None)))
                ack=session.json.loads(raw)['payload']
                self.assertEqual(ack['state'],'release-reviewed');self.assertTrue(channel.released)
                self.assertIn(1000,events);self.assertEqual(uid[0],0)
            finally:parent.release_owner_reads(actor);parent._CORES.pop(owner,None)

    def test_real_lock_held_pulse_and_release(self):
        c=self.launch();before=m.namespace(self.root)
        fd=os.open(self.root/'writer-v1.lock',os.O_RDWR)
        try:
            with self.assertRaises(BlockingIOError):fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.assertEqual(c.pulse()['state'],'held');self.assertIs(c.process,self.processes[0]);self.assertEqual(c.pid,self.processes[0].pid)
            ack=c.release([]);self.assertEqual(ack['state'],'release-reviewed')
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(fd,fcntl.LOCK_UN)
            self.assertEqual(m.namespace(self.root),before)
        finally:os.close(fd)
    def test_present_owned_path_refuses_release_and_retains_lease(self):
        c=self.launch();owned=Path(self.tmp.name)/'owned';owned.write_bytes(b'retained')
        with self.assertRaisesRegex(m.Held,'owned-present'):c.release([owned])
        self.assertEqual(owned.read_bytes(),b'retained');self.assertIsNone(c.process.poll());c.pulse()
        owned.unlink();c.release([owned])
    def test_original_marker_metadata_drift_refuses(self):
        c=self.launch();(self.root/'writer-v1.lock').chmod(0o640)
        with self.assertRaisesRegex(m.Held,'original-file'):c.check()
    def test_wrong_token_refuses_before_any_command(self):
        c=self.launch();c.token='b'*64
        with self.assertRaisesRegex(m.Held,'original-logical'):c.pulse()
        self.assertIsNone(c.process.poll())
    def test_real_pipe_replacement_refuses(self):
        c=self.launch();r,w=os.pipe()
        try:
            os.dup2(r,c.fds[1][0])
            with self.assertRaisesRegex(m.Held,'process-pipes'):c.check()
        finally:os.close(r);os.close(w)

    def test_wait_callback_cannot_reseal_supplied_original(self):
        c=self.launch();original=Path(self.tmp.name)/'original';original.write_bytes(b'original');original.chmod(0o600)
        old=m.nine(os.lstat(original));real=c.process.wait;fired=[]
        def changed(*args,**kwargs):
            result=real(*args,**kwargs)
            if not fired:original.chmod(0o640);fired.append(True)
            return result
        c.process.wait=changed
        with self.assertRaisesRegex(m.Held,'final-release-original9'):c.release([],files=((str(original),old),))
        self.assertTrue(fired);self.assertEqual(original.read_bytes(),b'original');self.assertEqual(c.process.poll(),0)

class ActualType(unittest.TestCase):
    def test_non_popen_is_never_an_original_process(self):
        with self.assertRaises(m.Held):m.LeaseChannel(object(),'a'*64,'/missing','b'*64)

class ProfileRules(unittest.TestCase):
    def test_real_dockerfile_labels_retained_with_own_label(self):
        import json
        fixture=json.loads((ROOT/'image-labels.json').read_text())
        labels=dict(fixture['labels'],**{'com.homelab.nfs.lease':'owned'})
        before=dict(labels);m.required_label(labels,'owned');self.assertEqual(labels,before)
        with self.assertRaises(m.Held):m.required_label(labels,'foreign')
    def test_stopped_epoch_is_original(self):
        m.stopped_epoch({'StartedAt':'original'},(123,'original'))
        with self.assertRaises(m.Held):m.stopped_epoch({'StartedAt':'restarted'},(123,'original'))

class FullProfileTransitions(unittest.TestCase):
    def fixture(self):
        import copy
        import comic_reader_lifecycle_parent as p
        owner=object.__new__(p.LifecycleParent);lease=object.__new__(m.HostWriterLease);lease.owner=owner;lease.g=p.__dict__;lease.cid=lease.cid_original='a'*64;lease.image='sha256:'+'b'*64;lease.name='fixture-lease';lease.command=['/lease-helper.py'];lease.mounts=(('/fixture/helper','/lease-helper.py',False),);lease.epoch=None;lease.profile_original=lease.profile_running=lease.profile_terminal=None;m._FULL_PROFILES[lease]=(None,None,None);self.addCleanup(m._FULL_PROFILES.pop,lease,None);lease.original=lambda **kwargs:None;guard=p.none_network_profile_contract;m._PROFILE_CONTRACTS[lease]=(guard,guard.__code__,guard(),None);self.addCleanup(m._PROFILE_CONTRACTS.pop,lease,None)
        row=dict(Id=lease.cid,Name='/'+lease.name,Image=lease.image,Path='/lsiopy/bin/python3',Args=lease.command,Created='original-birth',Config=dict(User='1000:1000',Labels={'com.homelab.nfs.lease':lease.name},Entrypoint=['/lsiopy/bin/python3'],Cmd=lease.command),HostConfig=dict(ReadonlyRootfs=True,Privileged=False,NetworkMode='none',PidMode='',IpcMode='private',CapAdd=None,CapDrop=['ALL'],SecurityOpt=['no-new-privileges'],PidsLimit=32,Devices=None,DeviceRequests=None,Binds=None,Tmpfs=None,PortBindings=None,RestartPolicy={'Name':'no'},OomKillDisable=False),Mounts=[dict(Type='bind',Source='/fixture/helper',Destination='/lease-helper.py',RW=False)],NetworkSettings=dict(Ports={},SandboxID='',SandboxKey='',Networks={'none':dict(EndpointID='',NetworkID='',IPAddress='',Gateway='',MacAddress='')}),State=dict(Status='created',Running=False,Pid=0,Paused=False,Restarting=False,Dead=False,OOMKilled=False,StartedAt='original-epoch'))
        owner.inspect=lambda cid:copy.deepcopy(row);lease.profile('created');running=copy.deepcopy(row);running['State'].update(Status='running',Running=True,Pid=123);running['HostConfig']['OomKillDisable']=None;running['NetworkSettings'].update(SandboxID='e'*64,SandboxKey='/var/run/docker/netns/'+'e'*12);running['NetworkSettings']['Networks']['none'].update(EndpointID='c'*64,NetworkID='d'*64)
        terminal=copy.deepcopy(running);terminal['State'].update(Status='exited',Running=False,Pid=0,ExitCode=0);terminal['NetworkSettings'].update(SandboxID='',SandboxKey='');terminal['NetworkSettings']['Networks']['none']['EndpointID']=''
        return lease,owner,row,running,terminal
    def test_source_helper_start_terminal_and_held_no_inspect(self):
        import copy
        from unittest.mock import Mock
        lease,owner,born,running,terminal=self.fixture();original=lease.profile_original;owner.inspect=lambda cid:copy.deepcopy(running);lease.profile('running');started=lease.profile_running
        m._WINDOWS[lease]=('HELD',());self.addCleanup(m._WINDOWS.pop,lease,None);owner.inspect=Mock(side_effect=AssertionError('Writer-held remote read'))
        with self.assertRaisesRegex(m.Held,'while-Writer'):lease.profile('running')
        owner.inspect.assert_not_called();m._WINDOWS.pop(lease);owner.inspect=lambda cid:copy.deepcopy(terminal);lease.profile('exited');self.assertEqual(lease.profile_original,original);self.assertEqual(lease.profile_running,started)
    def test_abort_refuses_baseline_substitution_before_channel_callback(self):
        import threading
        from types import SimpleNamespace
        from unittest.mock import Mock,patch
        lease,owner,born,running,terminal=self.fixture();p=__import__('comic_reader_lifecycle_parent');owner.thread=threading.get_ident();owner.core=b'fixture-core';owner.engine=object.__new__(p.ScopedDocker);p._CORES[owner]=owner.core;self.addCleanup(p._CORES.pop,owner,None)
        lease.process=object();lease.channel=SimpleNamespace(process=lease.process,abort_original=Mock(side_effect=AssertionError('must not close input')));lease.profile_running=b'forged'
        with patch.object(m.os,'geteuid',return_value=0),self.assertRaisesRegex(m.Held,'lease-abort-original-profile-seal'):lease.abort_original()
        lease.channel.abort_original.assert_not_called()

    def test_wrong_epoch_hostconfig_and_tape_never_rebaseline(self):
        import copy
        lease,owner,born,running,terminal=self.fixture();owner.inspect=lambda cid:copy.deepcopy(running);lease.profile('running')
        terminal['State']['StartedAt']='foreign';owner.inspect=lambda cid:copy.deepcopy(terminal)
        with self.assertRaises(m.Held):lease.profile('exited')
        self.assertIsNone(lease.profile_terminal);running['HostConfig']['OomKillDisable']=False;owner.inspect=lambda cid:copy.deepcopy(running)
        with self.assertRaises(m.Held):lease.profile('running')
        lease.profile_running=b'forged'
        with self.assertRaisesRegex(m.Held,'full-profile-seal'):lease.profile('running')

class RetainedProfileContract(unittest.TestCase):
    def fixture(self):
        source=FullProfileTransitions();source._cleanups=[]
        self.addCleanup(source.doCleanups)
        import comic_reader_lifecycle_parent as p
        obj,owner,born,running,terminal=source.fixture()
        import copy
        owner.inspect=lambda cid:copy.deepcopy(running)
        return p,obj,lambda:obj.profile('running'),obj.profile_contract
    def test_same_globals_predicate_encoder_and_prefix_replacement_refuse(self):
        from unittest.mock import patch
        p,obj,run,close=self.fixture()
        scope=p.__dict__;temporary={}
        exec('def foreign(*args): return True',scope,temporary)
        for name,value in [('none_network_started_static',temporary['foreign']),
                           ('none_network_exited_static',temporary['foreign']),
                           ('_none_network_profile_bytes',temporary['foreign']),
                           ('NONE_NETWORK_SANDBOX_PARENT','/foreign')]:
            with self.subTest(name=name),patch.dict(scope,{name:value}):
                with self.assertRaisesRegex(p.Held,'original-profile-contract'):run()
                with self.assertRaisesRegex(p.Held,'original-profile-contract'):close()
        self.assertIsNone(obj.profile_running)
        run()
    def test_in_place_code_mutation_refuses_and_restoration_retains_tape(self):
        p,obj,run,close=self.fixture();function=p.none_network_started_static;original=function.__code__
        def foreign(a,b,c):return True
        try:
            function.__code__=foreign.__code__
            with self.assertRaisesRegex(p.Held,'original-profile-contract'):run()
            with self.assertRaisesRegex(p.Held,'original-profile-contract'):close()
        finally:function.__code__=original
        run();close()
    def test_retained_guard_identity_code_and_token_are_required(self):
        from unittest.mock import patch
        p,obj,run,close=self.fixture();scope=p.__dict__;temporary={}
        exec('def foreign(): return object()',scope,temporary)
        with patch.dict(scope,none_network_profile_contract=temporary['foreign']):
            with self.assertRaises(ValueError):run()
            with self.assertRaises(ValueError):close()
        run();close()
        with patch.dict(scope,NONE_NETWORK_SANDBOX_PARENT='/foreign'):
            with self.assertRaisesRegex(p.Held,'original-profile-contract'):self.fixture()
    def test_abort_contract_drift_refuses_before_original_channel_callback(self):
        import threading
        from types import SimpleNamespace
        from unittest.mock import Mock,patch
        p,lease,run,close=self.fixture();owner=lease.owner
        owner.thread=threading.get_ident();owner.core=b'fixture-core';owner.engine=object.__new__(p.ScopedDocker)
        p._CORES[owner]=owner.core;self.addCleanup(p._CORES.pop,owner,None)
        lease.process=object();lease.channel=SimpleNamespace(process=lease.process,abort_original=Mock(side_effect=AssertionError('must not close input')))
        with patch.object(m.os,'geteuid',return_value=0),patch.dict(p.__dict__,NONE_NETWORK_SANDBOX_PARENT='/foreign'):
            with self.assertRaisesRegex(p.Held,'original-profile-contract'):lease.abort_original()
        lease.channel.abort_original.assert_not_called()
    def test_in_place_dependency_and_checked_api_code_refuse(self):
        p,obj,run,close=self.fixture()
        for name in ('_none_network_profile_bytes','checked_none_network_started_static',
                     'checked_none_network_exited_static','none_network_profile_contract'):
            function=getattr(p,name);code=function.__code__
            try:
                function.__code__=code.replace(co_filename='<changed-source-code>')
                with self.subTest(name=name),self.assertRaises(ValueError):run()
                with self.assertRaises(ValueError):close()
            finally:function.__code__=code
        run();close()

@unittest.skipUnless(os.geteuid()==1000 and os.getegid()==1000,'genuine UID1000 Writer/helper required')
class ReleaseOrdering(unittest.TestCase):
    setUp=RealLease.setUp
    cleanup=RealLease.cleanup
    launch=RealLease.launch
    def test_release_callback_deadline_prevents_release_write(self):
        c=self.launch();clock=m.time.monotonic;changed=[];sent=[];write=m.os.write
        def absent(path):changed.append(True);raise FileNotFoundError(path)
        def send(fd,raw):
            if b'"action":"release"' in raw:sent.append(True)
            return write(fd,raw)
        with patch.object(c,'release_stat',side_effect=absent),patch.object(m.time,'monotonic',side_effect=lambda:c.deadline+1 if changed else clock()),patch.object(m.os,'write',side_effect=send):
            with self.assertRaisesRegex(m.Held,'lease-deadline'):c.release([self.root/'absent'])
        self.assertFalse(sent);self.assertFalse(c.released)
    def test_release_callback_replaced_pipe_receives_no_command(self):
        c=self.launch();r,w=os.pipe();saved=os.dup(c.fds[0][0]);changed=[]
        def absent(path):
            if not changed:os.dup2(w,c.fds[0][0]);changed.append(True)
            raise FileNotFoundError(path)
        try:
            with patch.object(c,'release_stat',side_effect=absent),self.assertRaises(m.Held):c.release([self.root/'absent'])
            os.set_blocking(r,False)
            with self.assertRaises(BlockingIOError):os.read(r,1)
            self.assertFalse(c.released)
        finally:os.dup2(saved,c.fds[0][0]);os.close(saved);os.close(r);os.close(w)
    def test_partial_release_ack_stall_respects_original_deadline(self):
        # Synthetic protocol peer; this tests transport timing, not Writer custody.
        token='a'*64;root5,_=m.namespace(self.root)
        held=dict(version=1,kind='owned-nfs-existing-writer-lease',token=token,state='held',writer_identity=list(root5[:2]),source_sha256=SHA,markers_unchanged=True,native_grant=False,publication_authority=False)
        body="import json,os,sys,time;held=sys.argv[1];print(held,flush=True);a=json.loads(input());assert a['action']=='pulse';print(held,flush=True);a=json.loads(input());assert a['action']=='release';os.write(1,b'{');time.sleep(2)"
        proc=subprocess.Popen([sys.executable,'-I','-B','-u','-c',body,m.encode(held).decode()],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);self.processes.append(proc)
        c=m.LeaseChannel(proc,token,self.root,SHA,.3);c.receive('held');start=m.time.monotonic()
        with self.assertRaisesRegex(m.Held,'lease-release-ACK-timeout'):c.release([])
        self.assertLess(m.time.monotonic()-start,1);self.assertFalse(c.released)

if __name__=='__main__':unittest.main()
