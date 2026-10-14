"""Finite session verbs for real host-owned Writer lease; not a Popen facade."""
import json
import os
from pathlib import Path
import stat
import weakref
import base64
import copy
import subprocess

class Held(ValueError):pass
_INTERFACES=weakref.WeakKeyDictionary()

def need(ok,reason):
    if not ok:raise Held(reason)
def encode(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def epoch_reply(result):
    need(type(result) is dict and set(result)=={'version','kind','cid','pid','started_at','start_ticks','native_grant','publication_authority'}
         and type(result['version']) is int and result['version']==1 and result['kind']=='parent-original-reader-host-epoch'
         and type(result['cid']) is str and len(result['cid'])==64 and all(x in '0123456789abcdef' for x in result['cid'])
         and type(result['pid']) is int and result['pid']>0 and type(result['start_ticks']) is int and result['start_ticks']>0
         and type(result['started_at']) is str and result['started_at']
         and result['native_grant'] is False and result['publication_authority'] is False,'lease-interface-host-reader-epoch')
    return result

class HostLeaseReplies:
    def __init__(self,dialogue,lease,absent,*,helper_ref=None):
        # Actual classes from the same reviewed sibling context, not duck typing.
        from comic_nfs_host_engine import EngineReplies
        from comic_nfs_host_lease import HostWriterLease
        need(type(dialogue) is EngineReplies and (type(lease) is HostWriterLease and dialogue.owner is lease.owner
             or lease is None and helper_ref is not None),'lease-session-owning-host-types')
        dialogue.close()
        if lease is not None:lease.original()
        self.helper_ref=None if helper_ref is None else dict(helper_ref)
        self.dialogue,self.lease=dialogue,lease;self.absent=tuple(str(Path(p)) for p in absent)
        need(len(self.absent)==2 and len(set(self.absent))==2 and Path(self.absent[0]).parent==Path(self.absent[1]),'lease-session-exact-owned-absence')
        self.absence_tape=self.absent;self.done=False
    def accept(self,frame):
        d=self.dialogue;d.close()
        if self.lease is not None:self.lease.original()
        need(not self.done and self.absent==self.absence_tape and type(frame) is dict
             and set(frame)=={'type','nonce','sequence','payload'} and frame['type']=='nfs-lease'
             and frame['nonce']==d.nonce and type(frame['sequence']) is int and frame['sequence']==d.sequence+1,'lease-session-original-frame')
        payload=frame['payload'];need(type(payload) is dict and set(payload)=={'operation','absent','empty'},'lease-session-finite-verb')
        verb=payload['operation'];need(verb in ('initialize','acquire','check','pulse','release'),'lease-session-operation')
        if verb!='initialize':need(payload['empty'] is None,'lease-session-no-late-empty')
        if verb=='release':
            # Child names must exactly map to these HOST-original predeclared paths;
            # the Parent pump performs that explicit schema-owned mapping first.
            need(type(payload['absent']) is list and tuple(payload['absent'])==self.absent,'lease-session-no-foreign-release')
            files=tuple((str(p),tuple(v)) for p,v in d.owner.files.items());nodes=tuple((str(p),tuple(v)) for p,v in d.owner.nodes.items())
            result=self.lease.release_after_absence(self.absent,original_files=files,original_nodes=nodes);self.done=True
        else:
            need(payload['absent']==[],'lease-session-no-extra-fields')
            if verb=='initialize':
                need(self.lease is None and self.helper_ref is not None,'lease-session-initialize-once')
                admitted=d.owner.mapping.admit_nfs_empty(payload['empty'])
                from comic_nfs_host_lease import HostWriterLease
                self.lease=HostWriterLease(d.owner,self.helper_ref,admitted_empty=admitted)
                result=self.lease.prepare()
            elif verb=='acquire':
                need(self.lease is not None,'lease-session-uninitialized');result=self.lease.acquire()
            elif verb=='check':
                need(self.lease is not None,'lease-session-uninitialized');result=self.lease.check()
            else:
                need(self.lease is not None,'lease-session-uninitialized');result=self.lease.pulse()
        d.close();self.lease.original();d.sequence=frame['sequence']
        raw=encode(dict(type='nfs-host',nonce=d.nonce,sequence=d.sequence,payload=result))+b'\n'
        d.close();self.lease.original()
        if verb=='release':
            for p in self.absent:
                try:os.lstat(p)
                except FileNotFoundError:continue
                raise Held('lease-session-final-absence')
        return raw

class ChildLeaseInterface:
    """Explicit lease methods over original Channel, never process-like attributes."""
    def __init__(self,channel):
        import __main__
        need(os.geteuid()==1000 and hasattr(__main__,'Channel') and type(channel) is __main__.Channel and (channel.read_fd,channel.write_fd)==(0,1),'lease-session-actual-child-channel')
        channel.close();self.channel=channel;self.records={};self.started=False;self.released=False;self.output=None;self.empty=None
        _INTERFACES[self]=(channel,channel.nonce,channel.facts)
    def admit(self):
        need(_INTERFACES.get(self)==(self.channel,self.channel.nonce,self.channel.facts),'lease-interface-original-channel');self.channel.close()
    def factory(self,output,engine):
        self.admit();need(self.output is None and getattr(engine,'__self__',None) is self.channel
             and getattr(engine,'__func__',None) is type(self.channel).engine,'lease-interface-original-factory')
        output=Path(output);z=os.lstat(output)
        need(output.is_absolute() and stat.S_ISDIR(z.st_mode) and z.st_uid==os.geteuid()==1000 and stat.S_IMODE(z.st_mode)==0o700,'lease-interface-own-output')
        empty=output/'lease-empty-config';empty.mkdir(mode=0o700)
        fd=os.open(empty,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            born=os.fstat(fd);birth9=(born.st_dev,born.st_ino,born.st_size,born.st_mtime_ns,born.st_ctime_ns,born.st_mode,born.st_uid,born.st_gid,born.st_nlink);need(stat.S_ISDIR(born.st_mode) and born.st_uid==born.st_gid==1000 and stat.S_IMODE(born.st_mode)==0o700,'lease-interface-empty-birth')
            os.fsync(fd)
        finally:os.close(fd)
        need(not os.listdir(empty),'lease-interface-empty-namespace');z=os.lstat(empty)
        actual=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
        need(actual==birth9,'lease-interface-original-empty9')
        self.empty=dict(path=str(empty),signature9=list(birth9));self.output=str(output);return self
    def probe(self,input_ref):
        self.admit();need(self.started and not self.released and self.output is not None,'lease-interface-probe-phase')
        need(type(input_ref) is dict and set(input_ref)=={'path','sha256','signature9'} and input_ref['path']==str(Path(self.output)/'probe'/'probe-input.json'),'lease-interface-fixed-probe-input')
        return ChildProbe(self.channel,input_ref)
    def reader_epoch(self):
        self.admit();c=self.channel
        sequence=c.send('nfs-reader-epoch',{})
        result=c.receive(sequence);self.admit()
        return epoch_reply(result)
    def _call(self,operation,absent=()):
        self.admit();c=self.channel;c.close();sequence=c.send('nfs-lease',dict(operation=operation,absent=list(absent),empty=self.empty if operation=='initialize' else None));result=c.receive(sequence);c.close();return result
    def prepare(self):
        need(not self.started and not self.released,'lease-interface-no-replay');result=self._call('initialize');self.started=True;self.acquired=False;return result
    def acquire(self):
        need(self.started and not self.released and not self.acquired,'lease-interface-acquire-no-replay');self.acquired=True;return self._call('acquire')
    def start(self):
        need(not self.started and not self.released,'lease-interface-no-replay');result=self._call('initialize');self.started=True;return result
    def pulse(self):
        need(self.started and not self.released,'lease-interface-live-phase');return self._call('pulse')
    def profile(self):
        need(self.started and not self.released,'lease-interface-live-phase');return self._call('check')
    def release_after_absence(self,paths,*,original_files=(),original_nodes=()):
        need(self.started and not self.released,'lease-interface-live-phase');self.pulse()
        files=tuple((str(p),tuple(v)) for p,v in original_files);nodes=tuple((str(p),tuple(v)) for p,v in original_nodes);absent=tuple(str(Path(p)) for p in paths)
        self.channel.close()
        for p,v in nodes:
            z=os.lstat(p)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('lease-interface-original5')
        for p,v in files:
            z=os.lstat(p)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('lease-interface-original9')
        for p in absent:
            try:os.lstat(p)
            except FileNotFoundError:continue
            raise Held('lease-interface-owned-present')
        result=self._call('release',absent);self.released=True;return result


class ChildProbe:
    def __init__(self, channel, input_ref):
        # The source-pinned ChildLeaseInterface must construct this with its
        # original actual __main__.Channel; this helper conveys facts only.
        self.channel = channel
        self.input_ref = copy.deepcopy(input_ref)
        self.prepared = False
        self.created = False
        self.started = False

    def prepare(self):
        need(not self.prepared, 'child-probe-no-reprepare')
        self.prepared = True
        seq = self.channel.send('nfs-probe', dict(operation='initialize', input=self.input_ref))
        value = self.channel.receive(seq)
        need(type(value) is dict and set(value) == {'name', 'argv', 'mounts'}, 'child-probe-original-prebirth-spec')
        return value

    def create(self):
        need(self.prepared, 'child-probe-requires-original-spec')
        need(not self.created, 'child-probe-no-rebirth')
        self.created = True
        seq = self.channel.send('nfs-probe', dict(operation='create', input=None))
        value = self.channel.receive(seq)
        need(type(value) is dict and set(value) == {'id', 'name', 'argv', 'mounts', 'profile'}, 'child-probe-original-spec-facts')
        return value

    def start_prepare(self):
        need(self.created and not self.started,'child-probe-original-prestart');self.started=True
        seq=self.channel.send('nfs-probe',dict(operation='start_prepare',input=None));value=self.channel.receive(seq)
        need(type(value) is dict and value.get('prepared') is True and value.get('native_grant') is False and value.get('publication_authority') is False,'child-probe-original-prepared')
        return value
    def execute_local(self):
        need(self.started,'child-probe-local-prepared')
        seq=self.channel.send('nfs-probe',dict(operation='execute_local',input=None));value=self.channel.receive(seq)
        need(type(value) is dict and value.get('kernel_finished') is True and value.get('local_exit_verified') is True and value.get('terminal_profile_verified') is False and value.get('profile') is None,'child-probe-local-kernel-result')
        out=base64.b64decode(value['stdout'],validate=True);err=base64.b64decode(value['stderr'],validate=True)
        need(len(out)<=8*1024**2 and len(err)<=4*1024**2,'child-probe-output-bound')
        return subprocess.CompletedProcess(['original-local-nfs-kernel'],0,out,err)
    def finish_after_release(self):
        need(self.started,'child-probe-original-finish')
        seq=self.channel.send('nfs-probe',dict(operation='finish',input=None));value=self.channel.receive(seq)
        need(type(value) is dict and set(value)=={'stdout','stderr','profile'},'child-probe-original-terminal-facts')
        out=base64.b64decode(value['stdout'],validate=True);err=base64.b64decode(value['stderr'],validate=True)
        need(len(out)<=8*1024**2 and len(err)<=4*1024**2,'child-probe-output-bound')
        return subprocess.CompletedProcess(['original-postlease-nfs-kernel'],0,out,err),value['profile']
