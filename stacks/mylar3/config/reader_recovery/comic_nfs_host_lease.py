"""Host-owned real Writer lease process; no child RemotePopen or copied grant."""
import copy
import json
import os
from pathlib import Path
import re
import select
import stat
import subprocess
import threading
import time
import uuid
import weakref

HELPER_SHA='2bb4985f72fc4b270ab551d35cb921a00990397dd6662e6a54668d0825423f21'
_WINDOWS=weakref.WeakKeyDictionary()
_FULL_PROFILES=weakref.WeakKeyDictionary()
_PROFILE_CONTRACTS=weakref.WeakKeyDictionary()
MAX=4*1024**2
class Held(ValueError):pass

def need(ok,reason):
    if not ok:raise Held(reason)
def five(z):return (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
def nine(z):return (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def decode(raw):
    def pairs(items):
        result={}
        for key,value in items:
            need(key not in result,'lease-duplicate-key');result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(Held('lease-nonfinite')))
def ticks(pid):
    raw=Path('/proc',str(pid),'stat').read_bytes();tail=raw[raw.rfind(b') ')+2:].split()
    need(len(tail)>=20,'lease-client-stat');return int(tail[19])
def namespace(root):
    root=Path(root);z=os.lstat(root);need(stat.S_ISDIR(z.st_mode) and z.st_uid==1000 and stat.S_IMODE(z.st_mode)==0o700,'lease-writer-root')
    rows=[]
    for name in sorted(os.listdir(root)):
        need(name in ('writer-v1.lock','normalizer-v1.pending','tagger-v2.pending','release-v1.pending','publication-v1.json'),'lease-writer-marker')
        p=root/name;v=nine(os.lstat(p));need(stat.S_ISREG(v[5]) and v[6]==1000 and stat.S_IMODE(v[5])==0o600 and v[8]==1 and v[2]<=1024**2,'lease-writer-original')
        rows.append((str(p),v))
    need(any(Path(p).name=='writer-v1.lock' for p,_ in rows),'lease-writer-lock')
    return five(z),tuple(rows)

def required_label(labels,name):
    need(type(labels) is dict and labels.get('com.homelab.nfs.lease')==name,'lease-own-label')

def stopped_epoch(state,epoch):
    need(type(epoch) is tuple and len(epoch)==2 and state.get('StartedAt')==epoch[1],'lease-original-stopped-epoch')

class LeaseChannel:
    """Real Popen and inherited FD/ACK lifetime. Never emulates subprocess."""
    def __init__(self,process,token,writer_root,writer_sha,seconds=900,*,owner=None):
        need(type(process) is subprocess.Popen and process.poll() is None,'lease-real-process')
        need(type(token) is str and re.fullmatch('[a-f0-9]{64}',token) and re.fullmatch('[a-f0-9]{64}',writer_sha),'lease-token-source')
        self.owner=owner
        if owner is not None:
            g=owner.left.__func__.__globals__
            need(type(owner) is g.get('LifecycleParent') and g.get('_CORES',{}).get(owner)==owner.core
                 and owner.thread==threading.get_ident() and str(Path(owner.left.__func__.__code__.co_filename).absolute())==owner.source_ref['path'],'lease-release-owning-read-parent')
        self.process=process;self.token=token;self.root=Path(writer_root);self.writer_sha=writer_sha;self.thread=threading.get_ident()
        self.streams=(process.stdin,process.stdout,process.stderr);need(all(x is not None for x in self.streams),'lease-real-streams')
        self.fds=tuple((s.fileno(),five(os.fstat(s.fileno()))) for s in self.streams)
        need(all(stat.S_ISFIFO(v[2]) for _,v in self.fds),'lease-pipes')
        self.pid=process.pid;self.start=ticks(self.pid);self.deadline=time.monotonic()+seconds;self.released=False;self.aborted=False
        self.root5,self.files=namespace(self.root);self.nodes=tuple((str(p),five(os.lstat(p))) for p in self.root.parents)
        self.pending=bytearray();self.seal=(self.pid,self.start,self.token,str(self.root),self.writer_sha,self.thread,self.fds,self.root5,self.files,self.nodes,self.deadline,id(self.owner))
    def raw(self):
        for p,v in self.nodes:
            z=os.lstat(p)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('lease-original-node')
        z=os.lstat(self.root)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=self.root5:raise Held('lease-original-root')
        if tuple(sorted(os.listdir(self.root)))!=tuple(sorted(Path(p).name for p,_ in self.files)):raise Held('lease-original-namespace')
        for p,v in self.files:
            z=os.lstat(p)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('lease-original-file')
    def check(self):
        need(not self.released and not self.aborted and threading.get_ident()==self.thread and self.process.poll() is None,'lease-process-lifetime')
        need(self.seal==(self.pid,self.start,self.token,str(self.root),self.writer_sha,self.thread,self.fds,self.root5,self.files,self.nodes,self.deadline,id(self.owner)),'lease-original-logical')
        need(self.process.pid==self.pid and self.streams==(self.process.stdin,self.process.stdout,self.process.stderr)
             and ticks(self.pid)==self.start and tuple((s.fileno(),five(os.fstat(s.fileno()))) for s in self.streams)==self.fds,'lease-original-process-pipes')
        need(time.monotonic()<self.deadline,'lease-deadline');self.raw()
    def receive(self,state):
        self.check()
        while b'\n' not in self.pending:
            need(select.select([self.fds[1][0]],[],[],max(0,self.deadline-time.monotonic()))[0],'lease-ACK-timeout')
            self.check();block=os.read(self.fds[1][0],4096);need(bool(block),'lease-lost-ACK');self.pending.extend(block);need(len(self.pending)<=4096,'lease-ACK-bound')
        raw,_,rest=self.pending.partition(b'\n');self.pending=bytearray(rest);ack=decode(raw)
        need(type(ack) is dict and set(ack)=={'version','kind','token','state','writer_identity','source_sha256','markers_unchanged','native_grant','publication_authority'}
             and type(ack['version']) is int and ack['version']==1 and ack['kind']=='owned-nfs-existing-writer-lease'
             and ack['token']==self.token and ack['state']==state and ack['writer_identity']==list(self.root5[:2])
             and ack['source_sha256']==self.writer_sha and ack['markers_unchanged'] is True
             and ack['native_grant'] is False and ack['publication_authority'] is False,'lease-original-ACK')
        self.check();return ack
    def send(self,action,absent):
        self.check();raw=encode(dict(token=self.token,action=action,owned_absence_verified=absent))+b'\n'
        self.process.stdin.flush();self.check()
        need(os.write(self.fds[0][0],raw)==len(raw),'lease-write-unknown-no-replay');self.check()
    def pulse(self):
        self.send('pulse',False);return self.receive('held')
    def release_stat(self,path):
        if self.owner is None:return os.lstat(path)
        owner=self.owner;g=owner.left.__func__.__globals__
        need(type(owner) is g.get('LifecycleParent') and g.get('_CORES',{}).get(owner)==owner.core and owner.thread==threading.get_ident(),'lease-release-original-read-parent')
        g['owner_root_guard']();return g['nfs_lstat'](path)
    def release(self,absent,files=(),nodes=()):
        """Only exact owning caller supplies its detached absence/original tapes."""
        absent=tuple(str(Path(p)) for p in absent);files=tuple((str(p),tuple(v)) for p,v in files);nodes=tuple((str(p),tuple(v)) for p,v in nodes)
        self.pulse();self.process.stdin.flush();self.check()
        for p,v in nodes:
            z=self.release_stat(p)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('lease-release-original5')
        for p,v in files:
            z=self.release_stat(p)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('lease-release-original9')
        for p in absent:
            try:self.release_stat(p)
            except FileNotFoundError:continue
            raise Held('lease-release-owned-present')
        raw=encode(dict(token=self.token,action='release',owned_absence_verified=True))+b'\n'
        need(os.write(self.fds[0][0],raw)==len(raw),'lease-release-unknown-no-replay')
        # Release ACK may coincide with normal process exit; do not require pollNone.
        need(select.select([self.fds[1][0]],[],[],30)[0],'lease-release-ACK-timeout')
        raw=self.process.stdout.readline(4097);need(0<len(raw)<=4096,'lease-release-ACK-bound');ack=decode(raw)
        expected=dict(version=1,kind='owned-nfs-existing-writer-lease',token=self.token,state='release-reviewed',writer_identity=list(self.root5[:2]),source_sha256=self.writer_sha,markers_unchanged=True,native_grant=False,publication_authority=False)
        need(ack==expected and type(ack.get('version')) is int and not self.pending and self.process.wait(timeout=30)==0,'lease-release-ACK-exit')
        need(self.process.pid==self.pid and self.streams==(self.process.stdin,self.process.stdout,self.process.stderr)
             and tuple((stream.fileno(),five(os.fstat(stream.fileno()))) for stream in self.streams)==self.fds,'lease-release-original-process-pipes')
        for p in absent:
            try:self.release_stat(p)
            except FileNotFoundError:continue
            raise Held('lease-postrelease-owned-present')
        self.raw()
        # All readline/wait/namespace helpers precede the detached original tail.
        for p,v in nodes:
            z=self.release_stat(p)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('lease-final-release-original5')
        for p,v in files:
            z=self.release_stat(p)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('lease-final-release-original9')
        for p in absent:
            try:self.release_stat(p)
            except FileNotFoundError:continue
            raise Held('lease-final-release-absence')
        self.released=True;return ack
    def abort_original(self):
        """Failure resource release only. No successful release or cleanup ACK."""
        need(not self.released and not self.aborted and threading.get_ident()==self.thread
             and type(self.process) is subprocess.Popen,'lease-abort-original-process')
        need(self.seal==(self.pid,self.start,self.token,str(self.root),self.writer_sha,self.thread,self.fds,self.root5,self.files,self.nodes,self.deadline,id(self.owner))
             and self.process.pid==self.pid and self.streams==(self.process.stdin,self.process.stdout,self.process.stderr), 'lease-abort-original-seal')
        original_seal=self.seal;original_files=tuple((p,tuple(v)) for p,v in self.files);original_nodes=tuple((p,tuple(v)) for p,v in self.nodes)
        for stream,(fd,v) in zip(self.streams,self.fds):
            need(not stream.closed and stream.fileno()==fd and five(os.fstat(fd))==v,'lease-abort-original-pipe')
        if self.process.poll() is None:need(ticks(self.pid)==self.start,'lease-abort-original-starttick')
        # Mark uncertainty first, so close/wait failure never permits replay.
        self.aborted=True
        self.streams[0].close()
        result=self.process.wait(timeout=30)
        need(type(result) is int and self.process.pid==self.pid and self.streams==(self.process.stdin,self.process.stdout,self.process.stderr)
             and self.streams[0].closed,'lease-abort-original-terminal')
        for stream,(fd,v) in zip(self.streams[1:],self.fds[1:]):
            need(not stream.closed and stream.fileno()==fd and five(os.fstat(fd))==v,'lease-abort-final-original-pipe')
        self.raw()
        need(self.seal==original_seal and original_seal==(self.pid,self.start,self.token,str(self.root),self.writer_sha,self.thread,self.fds,self.root5,self.files,self.nodes,self.deadline,id(self.owner)),'lease-abort-final-original-seal')
        for path,v in original_nodes:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('lease-abort-final-marker5')
        for path,v in original_files:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('lease-abort-final-marker9')
        return dict(original_stdin_closed=True,returncode=result,release_reviewed=False,cleanup_accepted=False,publication_authority=False)

class HostWriterLease:
    """Actual root Parent owns lease CID/spec and real host Popen; child sees facts."""
    def __init__(self,owner,helper_ref,*,admitted_empty=None):
        g=owner.left.__func__.__globals__
        need(os.geteuid()==0 and type(owner) is g.get('LifecycleParent') and g.get('_CORES',{}).get(owner)==owner.core
             and type(owner.engine) is g.get('ScopedDocker'),'lease-owning-root-parent')
        need(owner.left.__func__ is g['LifecycleParent'].left,'lease-source-profile-helpers')
        guard=g.get('none_network_profile_contract');need(callable(guard)and guard.__globals__ is g,'lease-source-profile-contract')
        contract=(guard,guard.__code__,guard())
        need(callable(getattr(owner,'begin_nfs_writer_window',None)) and callable(getattr(owner,'end_nfs_writer_window',None)),'lease-parent-window-unbound')
        need(helper_ref['sha256']==HELPER_SHA and helper_ref['path'] in owner.files
             and tuple(helper_ref['signature9'])==tuple(owner.files[helper_ref['path']]),'lease-retained-helper-original')
        root=Path(owner.mapping.host(owner.plan['native']['data']))/'media-writer'
        root5,writer_files=namespace(root);writer_nodes=tuple((str(p),five(os.lstat(p))) for p in root.parents)
        g['read'](helper_ref);tree=g['_CHILD_TREES'].get(owner);need(tree is not None,'lease-child-projection-required')
        projected=owner.mapping.child_host_ref(helper_ref);need(projected['sha256']==HELPER_SHA,'lease-helper-exact-child-copy')
        empty_ref=(owner.mapping.child_empty('nfs-lease-empty-config') if admitted_empty is None else owner.mapping.check_nfs_empty(admitted_empty));need(type(empty_ref) is dict and set(empty_ref)=={'path','signature9'},'lease-empty-creator-ref')
        empty=empty_ref['path'];need(tuple(empty_ref['signature9'])==nine(os.lstat(empty)) and stat.S_ISDIR(empty_ref['signature9'][5])
             and empty_ref['signature9'][6:8]==[1000,1000] and stat.S_IMODE(empty_ref['signature9'][5])==0o700 and not os.listdir(empty),'lease-empty-owned-config');tree.check()
        sdk=g['decode'](g['read'](owner.plan['sdk_map']));sha=sdk.get('media_writer.py');need(g['digest'](sha),'lease-installed-writer-source')
        need(namespace(root)==(root5,writer_files),'lease-preprojection-writer-original')
        self.owner,self.g,self.tree=owner,g,tree;_PROFILE_CONTRACTS[self]=contract;self.helper=copy.deepcopy(helper_ref);self.projected=copy.deepcopy(projected)
        self.empty_nodes=tuple((str(q),five(os.lstat(q))) for q in Path(empty).parents)
        self.admitted_empty=copy.deepcopy(admitted_empty);self.empty=str(empty);self.empty9=tuple(empty_ref['signature9']);self.root=root;self.root5=root5;self.writer_files=writer_files;self.writer_nodes=writer_nodes;self.writer_sha=sha;self.image=owner.plan['selected_image']
        self.token=uuid.uuid4().hex+uuid.uuid4().hex;self.name='comic-nfs-lease-'+uuid.uuid4().hex
        self.mounts=((projected['path'],'/lease-helper.py',False),(str(root),'/writer',True),(str(empty),'/config',False))
        self.command=['/lease-helper.py','--lease-child','--writer-source','/app/mylar3/mylar/media_writer.py','--writer-sha256',sha,'--writer-root','/writer','--token',self.token,'--lease-seconds',str(min(900,max(1,int(owner.left())))),'--defer-acquire']
        args=['create','--pull','never','--name',self.name,'--label','com.homelab.nfs.lease='+self.name,'--user','1000:1000','--read-only','--network','none','--ipc','private','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','32','--memory','64m','--cpus','0.25','--env','PYTHONDONTWRITEBYTECODE=1','--interactive','--entrypoint','/lsiopy/bin/python3']
        for src,dst,rw in self.mounts:
            need(not any(c in src+dst for c in ',\n\r'),'lease-mount-spelling');args+=['--mount','type=bind,src='+src+',dst='+dst+('' if rw else ',readonly')]
        self.create_args=tuple(args+[self.image,*self.command]);self.channel=None;self.process=None;self.cid=None;self.cid_original=None;self.epoch=None;self.profile_original=None;self.profile_running=None;self.profile_terminal=None;_FULL_PROFILES[self]=(None,None,None)
        self.tape=encode(dict(helper=self.helper,projected=self.projected,empty=self.empty,empty9=self.empty9,empty_nodes=self.empty_nodes,writer_original=(self.root5,self.writer_files,self.writer_nodes),root=str(root),writer_sha=sha,image=self.image,token=self.token,name=self.name,mounts=self.mounts,command=self.command,create=self.create_args))
    def profile_contract(self):
        need(self in _PROFILE_CONTRACTS,'lease-source-profile-contract')
        guard,code,token=_PROFILE_CONTRACTS[self]
        need(self.g.get('none_network_profile_contract')is guard and guard.__code__ is code and guard.__globals__ is self.g and guard()is token,'lease-profile-contract-original')
    def original(self,*,allow_expired=False):
        need(type(allow_expired) is bool,'lease-original-deadline-mode');tape=self.tape
        if self in _PROFILE_CONTRACTS:self.profile_contract()
        if self in _FULL_PROFILES:need(_FULL_PROFILES[self]==(self.profile_original,self.profile_running,self.profile_terminal),'lease-full-profile-seal')
        if not allow_expired:self.owner.left()
        else:need(threading.get_ident()==self.owner.thread and self.g.get('_CORES',{}).get(self.owner)==self.owner.core,'lease-expired-original-owner')
        self.g['read'](self.helper);self.tree.check()
        original=(self.helper['path'],self.helper['sha256'],tuple(self.helper['signature9']))
        projected=(self.projected['path'],self.projected['sha256'],tuple(self.projected['signature9']))
        tree=self.tree;pairs=[row for row in tree.pairs if row[0]==original]
        need(self.g.get('_CHILD_TREES',{}).get(self.owner) is tree and len(pairs)==1 and pairs[0][1]==projected,
             'lease-original-retained-helper-pair')
        if allow_expired:
            for path,v in self.empty_nodes:
                z=os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('lease-expired-original-empty5')
        else:
            if self.admitted_empty is not None:need(self.owner.mapping.check_nfs_empty(self.admitted_empty)==dict(path=self.empty,signature9=list(self.empty9)),'lease-original-admitted-empty')
        need(nine(os.lstat(self.empty))==self.empty9 and not os.listdir(self.empty),'lease-projection-originals')
        need(self.tape==encode(dict(helper=self.helper,projected=self.projected,empty=self.empty,empty9=self.empty9,empty_nodes=self.empty_nodes,writer_original=(self.root5,self.writer_files,self.writer_nodes),root=str(self.root),writer_sha=self.writer_sha,image=self.image,token=self.token,name=self.name,mounts=self.mounts,command=self.command,create=self.create_args)),'lease-host-original-spec')
        for p,v in self.writer_nodes:
            z=os.lstat(p)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('lease-host-writer-original5')
        if namespace(self.root)!=(self.root5,self.writer_files):raise Held('lease-host-writer-original9')
        z=os.lstat(self.projected['path'])
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=tuple(self.projected['signature9']):raise Held('lease-host-final-pair9')
        if os.listdir(self.empty):raise Held('lease-host-final-empty-names')
        z=os.lstat(self.empty)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=self.empty9:raise Held('lease-host-final-empty9')
        if self in _PROFILE_CONTRACTS:self.profile_contract()
        tree.check()
        pairs=[row for row in tree.pairs if row[0]==original]
        need(self.tree is tree and self.g.get('_CHILD_TREES',{}).get(self.owner) is tree
             and len(pairs)==1 and pairs[0][1]==projected and self.tape==tape
             and tape==encode(dict(helper=self.helper,projected=self.projected,empty=self.empty,empty9=self.empty9,empty_nodes=self.empty_nodes,writer_original=(self.root5,self.writer_files,self.writer_nodes),root=str(self.root),writer_sha=self.writer_sha,image=self.image,token=self.token,name=self.name,mounts=self.mounts,command=self.command,create=self.create_args)),
             'lease-final-retained-helper-pair')
    def window_state(self):
        """Local original process/pipe/source proof; no engine or application call."""
        entry=_WINDOWS.get(self);need(entry is not None,'lease-original-window')
        self.original(allow_expired=entry[0]=='RELEASED_PHYSICAL')
        state,seal=entry
        need(seal==(self.cid_original,self.process,self.channel,self.epoch,self.runtime_pid,self.runtime_ticks),'lease-original-window-seal')
        need(self.cid==self.cid_original and self.channel.process is self.process,'lease-original-window-process')
        if state in ('PREPARED','ACQUIRING','HELD','RELEASING'):
            self.channel.check();need(ticks(self.runtime_pid)==self.runtime_ticks,'lease-original-inner-process')
        elif state=='RELEASED_PHYSICAL':self.physical_exit()
        else:raise Held('lease-original-window-state')
        return state
    def physical_exit(self):
        entry=_WINDOWS.get(self);need(entry is not None and entry[0]=='RELEASED_PHYSICAL','lease-physical-exit-required')
        seal=entry[1];need(seal==(self.cid_original,self.process,self.channel,self.epoch,self.runtime_pid,self.runtime_ticks),'lease-physical-original-window-seal')
        need(self.process is self.channel.process and ((self.process.poll()==0 and self.channel.released) or (self.process.poll() is not None and self.channel.aborted)),'lease-original-physical-exit')
        try:current=ticks(self.runtime_pid)
        except FileNotFoundError:current=None
        need(current!=self.runtime_ticks,'lease-original-inner-still-present')
        self.channel.raw();self.original(allow_expired=True)
        if _WINDOWS.get(self)!=entry or seal!=(self.cid_original,self.process,self.channel,self.epoch,self.runtime_pid,self.runtime_ticks):raise Held('lease-physical-final-window-seal')
        return True
    def local_running(self):
        need(self.window_state() in ('ACQUIRING','HELD','RELEASING'),'lease-local-held-window')
        return dict(held=True,cid=self.cid_original,epoch=list(self.epoch),native_grant=False,publication_authority=False)
    def profile(self,status):
        entry=_WINDOWS.get(self)
        need(entry is None or entry[0] in ('PREPARED','RELEASED_PHYSICAL'),'lease-remote-profile-while-Writer-refused')
        self.profile_contract();self.original(allow_expired=entry is not None and entry[0]=='RELEASED_PHYSICAL');need(self.cid==self.cid_original and self.g['digest'](self.cid),'lease-original-CID');row=self.owner.inspect(self.cid)
        self.profile_contract()
        current_static=encode(dict(self.g['static'](row),Created=row['Created']));candidate=None
        need(self in _FULL_PROFILES,'lease-original-profile-tape');need(_FULL_PROFILES[self]==(self.profile_original,self.profile_running,self.profile_terminal),'lease-full-profile-seal')
        if self.profile_original is None:
            need(status=='created','lease-original-birth-profile-required');candidate=(current_static,None,None)
        else:
            created=decode(self.profile_original);need(encode(row['Created'])==encode(created.pop('Created')),'lease-original-created-time')
            if status=='running'and self.profile_running is None:
                need(self.g['checked_none_network_started_static'](created,self.g['static'](row),self.cid),'lease-original-started-static');candidate=(self.profile_original,current_static,None)
            elif status=='exited':
                need(self.profile_running is not None,'lease-original-running-profile-required')
                if self.profile_terminal is None:
                    running=decode(self.profile_running);running.pop('Created');need(self.g['checked_none_network_exited_static'](running,self.g['static'](row),self.cid),'lease-original-exited-static');candidate=(self.profile_original,self.profile_running,current_static)
                else:need(current_static==self.profile_terminal,'lease-original-terminal-static-exact')
            else:need(current_static==(self.profile_running if status=='running'else self.profile_original),'lease-original-full-static-profile')
        h,c,s=row['HostConfig'],row['Config'],row['State']
        required_label(c['Labels'],self.name)
        need(row['Id']==self.cid and row['Image']==self.image and row['Name']=='/'+self.name and c['User']=='1000:1000'
             and c['Labels'].get('com.homelab.nfs.lease')==self.name and c['Entrypoint']==['/lsiopy/bin/python3'] and c['Cmd']==self.command
             and s['Status']==status and s['Running'] is (status=='running') and all(s.get(k,False) is False for k in ('Paused','Restarting','Dead','OOMKilled'))
             and type(s['Pid']) is int and (s['Pid']>0 if status=='running' else s['Pid']==0),'lease-exact-own-CID-runtime')
        need(h['ReadonlyRootfs'] is True and h['Privileged'] is False and h['NetworkMode']=='none' and h['PidMode']=='' and h['IpcMode']=='private'
             and not h.get('CapAdd') and h['CapDrop']==['ALL'] and h['SecurityOpt']==['no-new-privileges'] and h['PidsLimit']==32
             and not h.get('Devices') and not h.get('DeviceRequests') and not h.get('Binds') and not h.get('Tmpfs') and not h.get('PortBindings')
             and h.get('RestartPolicy',{}).get('Name') in ('','no'),'lease-exact-isolation')
        need(len(row['Mounts'])==len(self.mounts) and all(m['Type']=='bind' for m in row['Mounts'])
             and sorted((m['Source'],m['Destination'],m['RW']) for m in row['Mounts'])==sorted(self.mounts),'lease-original-mounts')
        if status=='running':
            current=(s['Pid'],s['StartedAt'])
            if self.epoch is None:self.epoch=current
            else:need(current==self.epoch,'lease-original-child-epoch')
        if status=='exited':stopped_epoch(s,self.epoch)
        self.original()
        if candidate is not None:
            self.profile_original,self.profile_running,self.profile_terminal=candidate;_FULL_PROFILES[self]=candidate;self.original()
        self.profile_contract()
        return row
    def prepare(self):
        need(self.cid is None and self.channel is None,'lease-no-replay');self.original()
        self.owner.emit('nfs-lease-create-intent.json',dict(command=list(self.create_args),automatic_replay=False))
        cid=self.owner.engine.run(list(self.create_args),self.owner.left()).decode().strip();need(self.g['digest'](cid),'lease-create-ACK-unknown')
        self.cid=cid;self.cid_original=cid;self.profile('created')
        process=subprocess.Popen([*self.g['DOCKER'],'start','--attach','--interactive',cid],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        self.process=process
        self.channel=LeaseChannel(process,self.token,self.root,self.writer_sha,max(1,int(self.owner.left())),owner=self.owner)
        ack=self.channel.receive('prepared');row=self.profile('running')
        self.runtime_pid=row['State']['Pid'];self.runtime_ticks=ticks(self.runtime_pid)
        _WINDOWS[self]=('PREPARED',(self.cid_original,self.process,self.channel,self.epoch,self.runtime_pid,self.runtime_ticks))
        self.window_state();return ack
    def acquire(self):
        need(self.window_state()=='PREPARED','lease-prepare-before-acquire')
        # Parent seals original session and blocks ALL engine paths BEFORE write.
        self.owner.begin_nfs_writer_window(self)
        seal=_WINDOWS[self][1];_WINDOWS[self]=('ACQUIRING',seal)
        self.channel.check();raw=encode(dict(token=self.token,action='acquire',owned_absence_verified=False))+b'\n'
        need(os.write(self.channel.fds[0][0],raw)==len(raw),'lease-acquire-unknown-no-replay')
        ack=self.channel.receive('held');_WINDOWS[self]=('HELD',seal);self.local_running();return ack
    def start(self):
        self.prepare();return self.acquire()
    def check(self):
        need(self.channel is not None,'lease-not-started');return self.local_running()
    def _pulse_owned(self):
        """Physical heartbeat inside an already bracketed original-source call."""
        entry=_WINDOWS.get(self)
        need(type(self) is HostWriterLease and entry is not None
             and entry[0] in ('ACQUIRING','HELD','RELEASING'),'lease-pulse-owning-window')
        seal=entry[1]
        def local():
            need(_WINDOWS.get(self) is entry and seal==(self.cid_original,self.process,self.channel,self.epoch,self.runtime_pid,self.runtime_ticks)
                 and self.cid==self.cid_original and type(self.channel) is LeaseChannel
                 and self.channel.process is self.process,'lease-pulse-original-window-seal')
            self.channel.check()
            need(ticks(self.runtime_pid)==self.runtime_ticks,'lease-pulse-original-inner-process')
        local();ack=self.channel.pulse();local();return ack
    def pulse(self,_pulse=_pulse_owned,_pulse_code=_pulse_owned.__code__):
        need((_pulse,_pulse_code)==HostWriterLease.pulse.__defaults__
             and _pulse is HostWriterLease._pulse_owned and _pulse.__code__ is _pulse_code
             and '_pulse_owned' not in self.__dict__,'lease-original-owned-pulse')
        self.check();ack=_pulse(self);self.check()
        need((_pulse,_pulse_code)==HostWriterLease.pulse.__defaults__
             and _pulse is HostWriterLease._pulse_owned and _pulse.__code__ is _pulse_code
             and '_pulse_owned' not in self.__dict__,'lease-final-owned-pulse')
        return ack
    def release_after_absence(self,paths,*,original_files=(),original_nodes=()):
        paths=tuple(str(Path(p)) for p in paths)
        self.check();seal=_WINDOWS[self][1];_WINDOWS[self]=('RELEASING',seal)
        ack=self.channel.release(paths,original_files,original_nodes)
        # Original helper exit and inner PID disappearance precede ANY inspect.
        try:current=ticks(self.runtime_pid)
        except FileNotFoundError:current=None
        need(current!=self.runtime_ticks,'lease-original-inner-still-present')
        _WINDOWS[self]=('RELEASED_PHYSICAL',seal);self.physical_exit();self.owner.end_nfs_writer_window(self)
        row=self.profile('exited')
        need(row['State']['ExitCode']==0,'lease-own-child-zero-exit')
        for p in paths:
            try:self.g['nfs_lstat'](p)
            except FileNotFoundError:continue
            raise Held('lease-own-final-absence')
        return ack
    def abort_original(self):
        """Original lease-only EOF supervision even after the Parent deadline."""
        need(os.geteuid()==0 and threading.get_ident()==self.owner.thread
             and self.g.get('_CORES',{}).get(self.owner)==self.owner.core
             and type(self.owner) is self.g.get('LifecycleParent')
             and type(self.owner.engine) is self.g.get('ScopedDocker'), 'lease-abort-owning-parent')
        need(self.channel is not None and self.process is self.channel.process
             and self.cid==self.cid_original and self.g['digest'](self.cid)
             and self.profile_original is not None,'lease-abort-owning-CID')
        need(_FULL_PROFILES.get(self)==(self.profile_original,self.profile_running,self.profile_terminal),'lease-abort-original-profile-seal')
        self.profile_contract()
        need(self.tape==encode(dict(helper=self.helper,projected=self.projected,empty=self.empty,empty9=self.empty9,empty_nodes=self.empty_nodes,writer_original=(self.root5,self.writer_files,self.writer_nodes),root=str(self.root),writer_sha=self.writer_sha,image=self.image,token=self.token,name=self.name,mounts=self.mounts,command=self.command,create=self.create_args)),'lease-abort-original-spec')
        owner=self.owner;engine=owner.engine;cid=self.cid_original;original_static=self.profile_original;original_profiles=_FULL_PROFILES.get(self);epoch=None if self.epoch is None else tuple(self.epoch)
        parent_core=encode(dict(plan=owner.plan,files=owner.files,nodes=owner.nodes,source=owner.source_ref,input=owner.plan_ref,engine=id(engine),thread=owner.thread,deadline=owner.deadline))
        need(parent_core==owner.core,'lease-abort-original-parent-core')
        originals=tuple((ref['path'],tuple(ref['signature9'])) for ref in (self.helper,self.projected))
        original_nodes=tuple(self.writer_nodes)
        # Closing original input is permitted only for this exact original real
        # process. No Docker stop/kill/remove or fixture deletion is performed.
        result=self.channel.abort_original()
        self.profile_contract()
        need(self.owner is owner and owner.engine is engine and self.cid==self.cid_original==cid
             and self.profile_original==original_static and _FULL_PROFILES.get(self)==original_profiles and (self.profile_original,self.profile_running,self.profile_terminal)==original_profiles and (None if self.epoch is None else tuple(self.epoch))==epoch,'lease-abort-post-wait-original-binding')
        entry=_WINDOWS.get(self)
        need(entry is not None,'lease-abort-unsealed-window-retained')
        try:current=ticks(self.runtime_pid)
        except FileNotFoundError:current=None
        need(current!=self.runtime_ticks,'lease-abort-inner-still-present')
        was_blocked=entry[0] in ('ACQUIRING','HELD','RELEASING')
        _WINDOWS[self]=('RELEASED_PHYSICAL',entry[1]);self.physical_exit()
        if was_blocked:self.owner.end_nfs_writer_window(self)
        raw=engine.run(['inspect',cid],30);rows=decode(raw)
        need(type(rows) is list and len(rows)==1,'lease-abort-one-own-profile');row=rows[0]
        need(original_profiles is not None and self.profile_running is not None,'lease-abort-original-running-static')
        running=decode(self.profile_running);need(encode(row['Created'])==encode(running.pop('Created'))and self.g['checked_none_network_exited_static'](running,self.g['static'](row),cid),'lease-abort-original-static')
        if self.profile_terminal is not None:need(encode(dict(self.g['static'](row),Created=row['Created']))==self.profile_terminal,'lease-abort-terminal-static-exact')
        s=row['State'];need(s['Status']=='exited' and s['Running'] is False and type(s['Pid']) is int and s['Pid']==0
                            and (epoch is None or s['StartedAt']==epoch[1]) and all(s.get(k,False) is False for k in ('Paused','Restarting','Dead','OOMKilled')),'lease-abort-own-exit')
        response=dict(result,cid=cid,unknown_fixture_retained=True,native_grant=False,original_running_epoch_verified=epoch is not None)
        need(self.owner is owner and owner.engine is engine and self.cid==self.cid_original==cid
             and self.profile_original==original_static and _FULL_PROFILES.get(self)==original_profiles and (self.profile_original,self.profile_running,self.profile_terminal)==original_profiles and (None if self.epoch is None else tuple(self.epoch))==epoch,'lease-abort-final-original-binding')
        for path,v in original_nodes:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=tuple(v):raise Held('lease-abort-final-original5')
        for path,v in originals:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('lease-abort-final-original9')
        self.profile_contract()
        return response
