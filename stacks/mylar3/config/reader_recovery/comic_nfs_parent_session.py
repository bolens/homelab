"""Retained original FIFO pump for the owning Parent's finite NFS session.

This transport owns no engine, SDK, ACK or canary authority. The Parent supplies
its original registered process and fixed handlers; the genuine canary stays in
the UID1000 child. Unknown EOF/timeouts retain the process and refuse replay.
"""
import json
import os
import select
import stat
import subprocess
import time
import weakref

MAX=16*1024**2
_SEALS=weakref.WeakKeyDictionary()
_SESSION_SEALS=weakref.WeakKeyDictionary()
_SESSION_PUMPS=weakref.WeakKeyDictionary()
_EXITED_PUMPS=weakref.WeakKeyDictionary()
class Held(ValueError):pass

def need(v,r):
    if not v:raise Held(r)

def five(z):return (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
def encode(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def decode(raw):
    def pairs(rows):
        value={}
        for k,v in rows:need(k not in value,'nfs-pump-duplicate');value[k]=v
        return value
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(Held('nfs-pump-nonfinite')))

class OriginalPump:
    def __init__(self,process,deadline,guard):
        need(type(process) is subprocess.Popen and all(v is not None for v in (process.stdin,process.stdout,process.stderr)),'nfs-pump-real-process')
        self.process=process;self.streams=(process.stdin,process.stdout,process.stderr)
        self.descriptors=tuple((v.fileno(),five(os.fstat(v.fileno()))) for v in self.streams)
        need(all(stat.S_ISFIFO(v[2]) for _,v in self.descriptors),'nfs-pump-original-FIFO')
        need(type(deadline) in (int,float) and deadline>time.monotonic() and callable(guard),'nfs-pump-bounded-lifetime')
        self.pid=process.pid;self.deadline=deadline;self.guard=guard
        self.pending=bytearray();self.stderr=bytearray();self.stderr_open=True;self.failed=False;self.finished=False
        _SEALS[self]=(process,self.streams,self.descriptors,self.pid,deadline,guard)
        self.check()
    def check(self):
        seal=_SEALS.get(self)
        need(not self.failed and not self.finished and seal==(self.process,self.streams,self.descriptors,self.pid,self.deadline,self.guard),'nfs-pump-original-seal')
        need(self.process.pid==self.pid and (self.process.stdin,self.process.stdout,self.process.stderr)==self.streams and time.monotonic()<self.deadline,'nfs-pump-original-process')
        for fd,v in seal[2]:
            z=os.fstat(fd)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('nfs-pump-original-descriptor')
        self.guard()
        if _SEALS.get(self)!=seal or (self.process,self.streams,self.descriptors,self.pid,self.deadline,self.guard)!=seal:raise Held('nfs-pump-callback-seal')
        for fd,v in seal[2]:
            z=os.fstat(fd)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('nfs-pump-callback-descriptor')
    def read(self):
        try:
            while b'\n' not in self.pending:
                self.check();readers=[self.descriptors[1][0]]+([self.descriptors[2][0]] if self.stderr_open else [])
                ready=select.select(readers,[],[],max(0,self.deadline-time.monotonic()))[0]
                need(bool(ready),'nfs-pump-lost-response')
                for fd in ready:
                    self.check();raw=os.read(fd,65536)
                    if fd==self.descriptors[2][0]:
                        if raw:self.stderr.extend(raw);need(len(self.stderr)<=4*1024**2,'nfs-pump-stderr-bound')
                        else:self.stderr_open=False
                        continue
                    need(bool(raw),'nfs-pump-unexpected-EOF');self.pending.extend(raw);need(len(self.pending)<=MAX,'nfs-pump-frame-bound')
            raw,_,rest=self.pending.partition(b'\n');self.pending=bytearray(rest)
            value=decode(raw);self.check();return value
        except BaseException:
            self.failed=True;raise
    def write(self,frame):
        try:
            raw=encode(frame)+b'\n';need(len(raw)<=MAX,'nfs-pump-write-bound');pending=memoryview(raw)
            while pending:
                self.check();need(select.select([],[self.descriptors[0][0]],[],max(0,self.deadline-time.monotonic()))[1],'nfs-pump-write-timeout')
                count=os.write(self.descriptors[0][0],pending[:4096]);need(count>0,'nfs-pump-write-unknown');pending=pending[count:]
            self.check()
        except BaseException:
            self.failed=True;raise
    def close_original_input_after_failure(self):
        original=_SEALS.get(self)
        need(self.failed and original==(self.process,self.streams,self.descriptors,self.pid,self.deadline,self.guard),'nfs-pump-failure-original-seal')
        need(self.process.pid==self.pid and (self.process.stdin,self.process.stdout,self.process.stderr)==self.streams,'nfs-pump-failure-original-process')
        stream=self.streams[0];fd,stamp=self.descriptors[0]
        need(not stream.closed and stream.fileno()==fd and five(os.fstat(fd))==stamp,'nfs-pump-failure-original-input')
        stream.close()
        return dict(original_input_closed=True,terminal_accepted=False,cleanup_accepted=False,automatic_replay=False)

    def finish(self):
        # Only caller's genuine nfs-done frame permits this terminal operation.
        try:
            self.check();need(not self.pending,'nfs-pump-trailing-frame')
            result=self.process.wait(timeout=max(.001,self.deadline-time.monotonic()))
            self.check();need(result==0,'nfs-pump-child-exit')
            original=_SEALS[self]
            for stream in original[1]:stream.close()
            need(_SEALS.get(self) is original and original==(self.process,self.streams,self.descriptors,self.pid,self.deadline,self.guard)
                 and self.process.pid==original[3] and self.process.returncode==0
                 and (self.process.stdin,self.process.stdout,self.process.stderr)==original[1]
                 and all(stream.closed for stream in original[1]),'nfs-pump-original-successful-exit')
            self.finished=True;_EXITED_PUMPS[self]=(original,0)
        except BaseException:
            self.failed=True;raise

    def successful_exit(self):
        """Closed original transport only; no new work or elapsed-deadline bypass."""
        value=_EXITED_PUMPS.get(self)
        need(self.finished and not self.failed and value is not None,'nfs-pump-no-successful-exit')
        original,result=value
        need(result==0 and _SEALS.get(self) is original
             and original==(self.process,self.streams,self.descriptors,self.pid,self.deadline,self.guard)
             and self.process.pid==original[3] and self.process.returncode==0
             and (self.process.stdin,self.process.stdout,self.process.stderr)==original[1]
             and all(stream.closed for stream in original[1]),'nfs-pump-successful-exit-originals')
        return value

class RetainedChild:
    """Finite existing Parent dialogue; no serialized canary reconstruction."""
    def __init__(self,owner,cid,process,engine_replies,lease_replies,probe_replies,packet_ref,operation_output,created_static):
        g=owner.left.__func__.__globals__
        need(type(owner) is g.get('LifecycleParent') and g.get('_CORES',{}).get(owner)==owner.core and type(owner.engine) is g.get('ScopedDocker'),'nfs-session-original-parent')
        need(g['digest'](cid) and packet_ref['path'] in owner.generated and owner.generated[packet_ref['path']]==packet_ref,'nfs-session-own-packet')
        packet=g['decode'](g['read'](packet_ref))
        need(packet['nonce']==owner.plan['nonce'] and packet['kind']=='owning-nfs-retained-host-lease-child-v2','nfs-session-original-nonce')
        host_modules=g['LifecycleParent'].nfs_host_modules
        bound=owner.nfs_host_modules
        need(getattr(bound,'__self__',None) is owner and getattr(bound,'__func__',None) is host_modules,
             'nfs-session-original-module-checker')
        self.host_modules_guard=(host_modules,host_modules.__code__,host_modules.__defaults__)
        modules=host_modules(owner)
        need(host_modules.__code__ is self.host_modules_guard[1]
             and host_modules.__defaults__ is self.host_modules_guard[2]
             and getattr(owner.nfs_host_modules,'__func__',None) is host_modules,
             'nfs-session-module-checker-constructor-drift')
        need(type(engine_replies) is modules['comic_nfs_host_engine.py'].EngineReplies and type(lease_replies) is modules['comic_nfs_lease_session.py'].HostLeaseReplies and type(probe_replies) is modules['comic_nfs_host_probe.py'].HostProbeReplies,'nfs-session-original-handler-types')
        self.lease_class=modules['comic_nfs_host_lease.py'].HostWriterLease
        self.abort_method=self.lease_class.abort_original;self.abort_code=self.abort_method.__code__
        self.abort_result=None
        self.owner,self.g,self.cid=owner,g,cid
        self.engine_replies,self.lease_replies,self.probe_replies=engine_replies,lease_replies,probe_replies
        # All handlers must belong to this exact original registered dialogue.
        need(engine_replies.owner is owner and engine_replies.cid==cid and lease_replies.dialogue is engine_replies and probe_replies.dialogue is engine_replies,'nfs-session-original-handlers')
        self.packet_ref=dict(path=packet_ref['path'],sha256=packet_ref['sha256'],signature9=list(packet_ref['signature9']));self.output=operation_output
        packet_original=(packet_ref['path'],packet_ref['sha256'],tuple(packet_ref['signature9']))
        self.seal=(owner,g,cid,engine_replies,lease_replies,probe_replies,packet_original,operation_output,self.host_modules_guard)
        _SESSION_SEALS[self]=self.seal
        self.created_static=bytes(created_static)
        self.last=None;self.state='starting';self.original_pid=process.pid
        _SESSION_SEALS[self]=(*self.seal,self.created_static,self.lease_class,self.abort_method,self.abort_code)
        self.pump=OriginalPump(process,min(owner.deadline,g['_DIALOGUE_SEALS'][owner.engine][cid][6]),self.close)
        _SESSION_PUMPS[self]=self.pump
    def close(self):
        if self in _SESSION_PUMPS:need(self.pump is _SESSION_PUMPS[self],'nfs-session-original-pump')
        need(_SESSION_SEALS.get(self)==(*self.seal,self.created_static,self.lease_class,self.abort_method,self.abort_code)
             and self.seal[-1] is self.host_modules_guard,'nfs-session-original-module-guard-seal')
        method,code,defaults=self.host_modules_guard
        bound=self.owner.nfs_host_modules
        need(type(self.owner) is self.g.get('LifecycleParent')
             and type(self.owner).nfs_host_modules is method
             and getattr(bound,'__self__',None) is self.owner and getattr(bound,'__func__',None) is method
             and method.__globals__ is self.g and method.__code__ is code and method.__defaults__ is defaults,
             'nfs-session-original-module-checker')
        # The sealed original checker calls the full Parent.left itself. Keep
        # every transport guard; avoid a second identical Parent closure here.
        method(self.owner)
        self.g['read'](self.packet_ref);self.g['dialogue_close'](self.owner.engine,self.cid)
        need(_SESSION_SEALS.get(self)==(*self.seal,self.created_static,self.lease_class,self.abort_method,self.abort_code) and self.seal==(self.owner,self.g,self.cid,self.engine_replies,self.lease_replies,self.probe_replies,(self.packet_ref['path'],self.packet_ref['sha256'],tuple(self.packet_ref['signature9'])),self.output,self.host_modules_guard),'nfs-session-original-seal')
        epoch=self.g['_NFS_CHILD_EPOCHS'].get(self.owner)
        if epoch is not None:
            need(len(epoch)==6 and epoch[0] is self and epoch[1]==self.cid,'nfs-session-original-local-epoch')
            ticks=int(self.g['Path']('/proc/'+str(epoch[2])+'/stat').read_text().rsplit(')',1)[1].split()[19]);need(ticks==epoch[4],'nfs-session-original-local-starttick')
        need(self.owner.generated.get(self.packet_ref['path'])==self.packet_ref,'nfs-session-original-packet-row')
        need(self.engine_replies.owner is self.owner and self.engine_replies.cid==self.cid and self.engine_replies.nonce==self.owner.plan['nonce'] and self.lease_replies.dialogue is self.engine_replies and self.probe_replies.dialogue is self.engine_replies,'nfs-session-original-binding')
        bound=self.owner.nfs_host_modules
        need(type(self.owner).nfs_host_modules is method and method.__globals__ is self.g
             and getattr(bound,'__self__',None) is self.owner and getattr(bound,'__func__',None) is method
             and method.__code__ is code and method.__defaults__ is defaults
             and self.host_modules_guard is self.seal[-1]
             and _SESSION_SEALS.get(self)==(*self.seal,self.created_static,self.lease_class,self.abort_method,self.abort_code),
             'nfs-session-module-checker-callback-drift')
    def until(self,kind):
        need(kind in ('nfs-ready','nfs-result','nfs-done') and self.state not in ('failed','finished'),'nfs-session-finite-state')
        original_pump=_SESSION_PUMPS.get(self,self.pump)
        need(type(original_pump) is OriginalPump,'nfs-session-retained-original-pump')
        try:
            while True:
                self.close();frame=self.pump.read()
                need(type(frame) is dict and set(frame)=={'type','nonce','sequence','payload'},'nfs-session-frame')
                if frame['type']=='nfs-role-namespace':
                    response=self.owner.nfs_role_namespace_reply(frame);self.pump.write(response);continue
                if frame['type']=='nfs-library-query':
                    response=self.owner.nfs_library_query_reply(frame);self.pump.write(response);continue
                if frame['type']=='nfs-reader-epoch':
                    response=self.owner.nfs_reader_epoch_reply(frame);self.pump.write(response);continue
                if frame['type'] in ('nfs-engine','nfs-lease','nfs-probe'):
                    handler={'nfs-engine':self.engine_replies,'nfs-lease':self.lease_replies,'nfs-probe':self.probe_replies}[frame['type']]
                    response=handler.accept(frame)
                    need(type(response) is bytes and response.endswith(b'\n'),'nfs-session-fixed-response')
                    # Handler already owns exact nonce and consumed sequence.
                    self.pump.write(decode(response[:-1]));continue
                need(frame['type']==kind,'nfs-session-unexpected-fact')
                result=self.engine_replies.fact(frame,kind);self.last=frame['sequence'];self.close();return result
        except BaseException:
            self.state='failed'
            try:
                lease=self.lease_replies.lease
                if lease is not None and self.lease_replies.done is not True:
                    need(_SESSION_SEALS.get(self)==(*self.seal,self.created_static,self.lease_class,self.abort_method,self.abort_code) and type(lease) is self.lease_class and self.lease_class.abort_original is self.abort_method and self.abort_method.__code__ is self.abort_code,'nfs-session-original-lease-supervision')
                    self.abort_result=self.abort_method(lease)
            finally:
                # Handler/owner failures occur outside read/write too. Release
                # only the constructor-retained original stdin even if nested
                # lease supervision itself refuses; never grant terminal work.
                original_pump.failed=True
                original_pump.close_original_input_after_failure()
            raise
    def profile_after_release(self):
        need(self.lease_replies.lease is None or self.lease_replies.done is True,'nfs-session-no-remote-under-lease')
        current=self.owner.inspect(self.cid)
        original=self.g['_NFS_CHILD_EPOCHS'].get(self.owner)
        need(original is not None and len(original)==6 and original[0] is self and original[1]==self.cid
             and self.g['encode'](self.g['static'](current))==original[5] and current['Id']==self.cid,'nfs-session-original-container-static')
        need(current['State'].get('Dead') is False and current['State'].get('OOMKilled') is False,'nfs-session-container-failure')
        original=self.g['_NFS_CHILD_EPOCHS'].get(self.owner)
        need(original is not None and original[0] is self and original[1]==self.cid and current['State']['Pid']==original[2] and self.g['encode'](self.g['lifecycle_state'](current))==original[3],'nfs-session-original-running-epoch')
        ticks=int(self.g['Path']('/proc/'+str(original[2])+'/stat').read_text().rsplit(')',1)[1].split()[19]);need(ticks==original[4],'nfs-session-original-running-starttick')
        self.close();return current

    def successful_exit(self):
        """Only a finished original release dialogue supplies this local witness."""
        need(self.state=='finished' and _SESSION_PUMPS.get(self) is self.pump,'nfs-session-release-exit-required')
        need(_SESSION_SEALS.get(self)==(*self.seal,self.created_static,self.lease_class,self.abort_method,self.abort_code)
             and self.seal==(self.owner,self.g,self.cid,self.engine_replies,self.lease_replies,self.probe_replies,(self.packet_ref['path'],self.packet_ref['sha256'],tuple(self.packet_ref['signature9'])),self.output,self.host_modules_guard),'nfs-session-exit-original-seal')
        value=self.pump.successful_exit()
        self.owner.left();self.owner.nfs_host_modules();self.g['read'](self.packet_ref)
        need(self.owner.generated.get(self.packet_ref['path'])==self.packet_ref
             and self.lease_replies.done is True and self.lease_replies.lease.physical_exit() is True
             and self.lease_replies.lease.channel.released is True and self.lease_replies.lease.channel.aborted is False,'nfs-session-complete-physical-release')
        need(self.state=='finished' and _SESSION_SEALS.get(self)==(*self.seal,self.created_static,self.lease_class,self.abort_method,self.abort_code)
             and self.seal==(self.owner,self.g,self.cid,self.engine_replies,self.lease_replies,self.probe_replies,(self.packet_ref['path'],self.packet_ref['sha256'],tuple(self.packet_ref['signature9'])),self.output,self.host_modules_guard)
             and _SESSION_PUMPS.get(self) is self.pump and self.pump.successful_exit()==value,'nfs-session-exit-final-originals')
        return (self,self.owner,self.cid,self.original_pid,self.created_static,value)

    def ready(self):
        need(self.state=='starting','nfs-session-no-replay')
        result=self.until('nfs-ready');self.profile_after_release();self.state='ready';return result
    def request(self,operation,*,stopped):
        need(self.state=='ready' and operation in ('current','check','release') and type(stopped) is bool and type(self.last) is int,'nfs-session-own-command')
        self.close()
        self.pump.write(dict(type='nfs-host',nonce=self.owner.plan['nonce'],sequence=self.last,payload=dict(operation=operation,stopped=stopped)))
        result=self.until('nfs-done' if operation=='release' else 'nfs-result')
        if operation=='release':self.pump.finish();self.state='finished'
        return result
