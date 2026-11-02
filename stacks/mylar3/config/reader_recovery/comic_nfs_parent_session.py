"""Retained original FIFO pump for the owning Parent's finite NFS session.

This transport owns no engine, SDK, ACK or canary authority. The Parent supplies
its original registered process and fixed handlers; the genuine canary stays in
the UID1000 child. Unknown EOF/timeouts retain the process and refuse replay.
"""
import hashlib
import json
import os
from pathlib import PurePosixPath
import re
import select
import stat
import subprocess
import sys
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


def readonly_mount_observation(raw,protected,writable):
    """Parse actual helper mountinfo; returned facts grant no continuation rights.

    The owning Parent must additionally retain its helper/process/plan originals
    and compare this observation with the original configured Docker profile.
    """
    need(type(raw) is bytes and 0<len(raw)<=MAX,'nfs-readonly-mountinfo-bound')
    def path(value):
        need(type(value) is str and value.startswith('/') and not value.startswith('//')
             and str(PurePosixPath(value))==value and '..' not in PurePosixPath(value).parts
             and not any(c in value for c in ('\x00','\n','\r','\t')),'nfs-readonly-path')
        return PurePosixPath(value)
    def field(value):
        need(re.search(r'\\(?!040|011|012|134)',value) is None,'nfs-readonly-mountinfo-escape')
        return re.sub(r'\\(040|011|012|134)',lambda m:chr(int(m.group(1),8)),value)
    need(type(protected) in (list,tuple) and 1<=len(protected)<=32
         and type(writable) in (list,tuple) and len(writable)==2,'nfs-readonly-scope-shape')
    protected=tuple(path(p) for p in protected);writable=tuple(path(p) for p in writable)
    need(len(set(protected))==len(protected) and len(set(writable))==2
         and all(not(a==b or a in b.parents or b in a.parents)for a in protected for b in writable),
         'nfs-readonly-scope-disjoint')
    rows=[];ids=set()
    lines=raw.decode('utf-8',errors='strict').splitlines()
    need(1<=len(lines)<=8192,'nfs-readonly-mount-count')
    for line in lines:
        columns=line.split(' ');need(columns.count('-')==1,'nfs-readonly-mountinfo-separator')
        split=columns.index('-');need(split>=6 and len(columns)==split+4,'nfs-readonly-mountinfo-shape')
        need(all(re.fullmatch('[0-9]{1,20}',v) for v in columns[:2])
             and 0<int(columns[0])<2**63 and 0<int(columns[1])<2**63
             and re.fullmatch('[0-9]{1,10}:[0-9]{1,10}',columns[2]),'nfs-readonly-mountinfo-identity')
        mid=int(columns[0]);need(mid not in ids,'nfs-readonly-mountinfo-duplicate-id');ids.add(mid)
        root=path(field(columns[3]));point=path(field(columns[4]));options=columns[5].split(',')
        need(len(options)==len(set(options)) and (('ro'in options)!=('rw'in options)),
             'nfs-readonly-mountinfo-options')
        rows.append(dict(id=mid,parent=int(columns[1]),device=columns[2],root=str(root),point=str(point),readonly='ro'in options,
                         propagation=columns[6:split],filesystem=columns[split+1],source=field(columns[split+2])))
    def exact(point):
        found=[r for r in rows if r['point']==str(point)]
        need(len(found)==1,'nfs-readonly-exact-mount');return found[0]
    need(exact(PurePosixPath('/'))['readonly'],'nfs-readonly-root-filesystem')
    original_roots={str(p):exact(p) for p in protected}
    original_writable={str(p):exact(p) for p in writable}
    need(all(not r['readonly'] for r in original_writable.values()),'nfs-readonly-owned-writable-mounts')
    by_point={r['point']:r for r in rows}
    need(len(by_point)==len(rows),'nfs-readonly-stacked-mount')
    root_mount=by_point['/']
    need(root_mount['parent']==root_mount['id'] or root_mount['parent']not in ids,
         'nfs-readonly-root-parent')
    # Mountinfo includes hidden mounts. A lexical prefix alone does not prove
    # that the recorded bind is visible beneath intervening ancestor mounts.
    for row in rows:
        if row['point']=='/':continue
        ancestors=[by_point[str(p)] for p in PurePosixPath(row['point']).parents if str(p)in by_point]
        need(bool(ancestors) and row['parent']==ancestors[0]['id'],'nfs-readonly-hidden-mount')
    covered={};descendant_rows={}
    for p,original in original_roots.items():
        base=PurePosixPath(p)
        descendants=[r for r in rows if PurePosixPath(r['point'])==base or base in PurePosixPath(r['point']).parents]
        need(len({r['point']for r in descendants})==len(descendants),'nfs-readonly-stacked-protected-mount')
        need(all(r['readonly']for r in descendants),'nfs-readonly-protected-submount')
        ancestry=[by_point[str(q)] for q in (base,*base.parents)if str(q)in by_point]
        need(not any(v.split(':',1)[0]in('shared','master','propagate_from')
                     for r in (*ancestry,*descendants)for v in r['propagation']),
             'nfs-readonly-protected-submount')
        descendant_rows[p]=descendants
        covered.update((r['id'],r)for r in descendants)
    for original in covered.values():
        source_root=PurePosixPath(original['root'])
        for row in rows:
            if row['readonly']:continue
            same=row['device']==original['device']
            same=same or (row['filesystem']in('nfs','nfs4') and original['filesystem']in('nfs','nfs4')
                          and row['source']==original['source'])
            if not same:continue
            other=PurePosixPath(row['root'])
            need(not(other==source_root or other in source_root.parents or source_root in other.parents),
                 'nfs-readonly-writable-physical-alias')
    return dict(mountinfo_sha256=hashlib.sha256(raw).hexdigest(),protected=original_roots,
                protected_descendants=descendant_rows,
                writable=original_writable,mutation_authority=False,publication_authority=False)


def readonly_namespace_nodes(root,root5,paths,deadline):
    """Finite owner-principal metadata read through the original namespace FD."""
    need(os.getresuid()==os.getresgid()==(0,0,0),'nfs-readonly-root-node-observer')
    need(type(root) is int and root>=0 and type(root5) is tuple and len(root5)==5
         and all(type(v)is int for v in root5) and type(paths) is tuple
         and 1<=len(paths)<=32
         and all(type(p)is str and p.startswith('/') and str(PurePosixPath(p))==p
                 and '..'not in PurePosixPath(p).parts for p in paths)
         and len(set(paths))==len(paths)
         and type(deadline) in(int,float) and deadline>time.monotonic(),
         'nfs-readonly-node-request')
    # This literal belongs to the sealed function code. No source path, script
    # overlay or caller-supplied program is accepted by the metadata child.
    program="""import json,os,stat,sys
v=json.loads(sys.argv[1]);fd=v['fd'];original=tuple(v['root5'])
def five(z):return(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
assert os.getresuid()==os.getresgid()==(1000,1000,1000) and os.getgroups()==[]
assert five(os.fstat(fd))==original and stat.S_ISDIR(original[2])
rows={p:five(os.stat(p.lstrip('/'),dir_fd=fd,follow_symlinks=False)) for p in v['paths']}
assert five(os.fstat(fd))==original
print(json.dumps(dict(uid=list(os.getresuid()),gid=list(os.getresgid()),groups=os.getgroups(),root5=list(original),nodes=rows),sort_keys=True,separators=(',',':')),flush=True)
"""
    result=subprocess.run([sys.executable,'-I','-B','-c',program,
                           encode(dict(fd=root,root5=root5,paths=paths)).decode()],
                          pass_fds=(root,),user=1000,group=1000,extra_groups=(),
                          stdin=subprocess.DEVNULL,capture_output=True,
                          timeout=max(.001,deadline-time.monotonic()),check=False,
                          env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
    need(type(result.returncode)is int and result.returncode==0 and type(result.stdout)is bytes and len(result.stdout)<=MAX
         and result.stderr==b'','nfs-readonly-node-helper-result')
    value=decode(result.stdout)
    need(type(value)is dict and set(value)=={'uid','gid','groups','root5','nodes'}
         and value['uid']==value['gid']==[1000,1000,1000] and value['groups']==[]
         and type(value['root5'])is list and len(value['root5'])==5
         and all(type(n)is int for n in value['root5']) and value['root5']==list(root5)
         and type(value['nodes'])is dict
         and set(value['nodes'])==set(paths)
         and all(type(v)is list and len(v)==5 and all(type(n)is int for n in v)
                 and stat.S_ISDIR(v[2]) for v in value['nodes'].values()),
         'nfs-readonly-owner-node-census')
    need(five(os.fstat(root))==root5 and time.monotonic()<deadline,'nfs-readonly-node-original-FD-deadline')
    return value['nodes']


def observe_readonly_namespace(pid,start_ticks,protected,writable,deadline):
    """Root-only kernel observation, not a Parent/session capability factory."""
    need(os.getresuid()==os.getresgid()==(0,0,0),'nfs-readonly-root-observer')
    need(type(pid) is int and pid>0 and type(start_ticks) is int and start_ticks>0,
         'nfs-readonly-original-process')
    need(type(protected) is dict and 1<=len(protected)<=32
         and all(type(p) is str and type(v) in(list,tuple)and len(v)==9
                 and all(type(n)is int for n in v)and stat.S_ISDIR(v[5])
                 for p,v in protected.items()),'nfs-readonly-original-roots')
    originals=tuple((p,tuple(v))for p,v in protected.items())
    def bounded(name,maximum):
        fd=os.open('/proc/'+str(pid)+'/'+name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            chunks=[];size=0
            while size<=maximum:
                part=os.read(fd,min(65536,maximum+1-size))
                if not part:break
                chunks.append(part);size+=len(part)
            need(size<=maximum,'nfs-readonly-proc-bound');return b''.join(chunks)
        finally:os.close(fd)
    def process():
        raw=bounded('stat',65536).decode();split=raw.rfind(')')
        need(split>0 and raw[:raw.index('(')].strip()==str(pid),'nfs-readonly-proc-pid')
        fields=raw[split+2:].split();need(len(fields)>19 and int(fields[19])==start_ticks,
                                      'nfs-readonly-original-starttick')
        lines=[line.split()[1:]for line in bounded('status',65536).decode().splitlines()
               if line.startswith('NSpid:')]
        need(len(lines)==1 and 1<=len(lines[0])<=64 and all(v.isdecimal() for v in lines[0])
             and int(lines[0][0])==pid and all(int(v)>0 for v in lines[0]),'nfs-readonly-pid-namespace')
        return int(lines[0][-1])
    namespace_pid=process()
    root=os.open('/proc/'+str(pid)+'/root',os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:
        root5=five(os.fstat(root));before=bounded('mountinfo',MAX)
        observation=readonly_mount_observation(before,list(protected),writable)
        def close_nodes():
            need(five(os.fstat(root))==root5,'nfs-readonly-original-namespace-root')
            nodes=readonly_namespace_nodes(root,root5,tuple(p for p,_ in originals),deadline)
            for path,original in originals:
                need(tuple(nodes[path])==tuple(original[i]for i in(0,1,5,6,7)),
                     'nfs-readonly-original-mounted-node')
        close_nodes()
        after=bounded('mountinfo',MAX)
        need(after==before and process()==namespace_pid,'nfs-readonly-namespace-closure')
        close_nodes()
        return dict(namespace_pid=namespace_pid,roots={p:list(v)for p,v in originals},
                    namespace_root5=list(root5),mounts=observation,
                    mutation_authority=False,publication_authority=False)
    finally:os.close(root)

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
        if time.monotonic()>=self.deadline:raise Held('nfs-pump-callback-deadline')
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
        base=(*self.seal,self.created_static,self.lease_class,self.abort_method,self.abort_code)
        original=_SESSION_SEALS.get(self);epoch=self.g['_NFS_CHILD_EPOCHS'].get(self.owner)
        release=original[len(base):] if type(original) is tuple else ()
        releasing=(getattr(self,'state',None)=='releasing' and len(release)==1 and type(release[0]) is tuple
                   and len(release[0])==3 and release[0][0] is self.pump
                   and release[0][1] is epoch and type(release[0][2]) is int)
        need(original==base or (releasing and original==(*base,*release)),
             'nfs-session-original-release-seal')
        need(self.seal[-1] is self.host_modules_guard,'nfs-session-original-module-guard-seal')
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
        need(_SESSION_SEALS.get(self)==(*self.seal,self.created_static,self.lease_class,self.abort_method,self.abort_code,*release) and self.seal==(self.owner,self.g,self.cid,self.engine_replies,self.lease_replies,self.probe_replies,(self.packet_ref['path'],self.packet_ref['sha256'],tuple(self.packet_ref['signature9'])),self.output,self.host_modules_guard),'nfs-session-original-seal')
        epoch=self.g['_NFS_CHILD_EPOCHS'].get(self.owner)
        if epoch is not None:
            need(len(epoch)==6 and epoch[0] is self and epoch[1]==self.cid,'nfs-session-original-local-epoch')
            try:raw=self.g['Path']('/proc/'+str(epoch[2])+'/stat').read_text()
            except FileNotFoundError:
                # The original child may exit immediately after its release
                # frame. Only the source-owned, sealed release request may
                # drain that frame and reap the original client; it is not
                # successful until both facts have been verified.
                need(releasing and self.state=='releasing' and release[0][1] is epoch,
                     'nfs-session-original-local-release-required')
            else:
                ticks=int(raw.rsplit(')',1)[1].split()[19]);need(ticks==epoch[4],'nfs-session-original-local-starttick')
        need(self.owner.generated.get(self.packet_ref['path'])==self.packet_ref,'nfs-session-original-packet-row')
        need(self.engine_replies.owner is self.owner and self.engine_replies.cid==self.cid and self.engine_replies.nonce==self.owner.plan['nonce'] and self.lease_replies.dialogue is self.engine_replies and self.probe_replies.dialogue is self.engine_replies,'nfs-session-original-binding')
        bound=self.owner.nfs_host_modules
        need(type(self.owner).nfs_host_modules is method and method.__globals__ is self.g
             and getattr(bound,'__self__',None) is self.owner and getattr(bound,'__func__',None) is method
             and method.__code__ is code and method.__defaults__ is defaults
             and self.host_modules_guard is self.seal[-1]
             and _SESSION_SEALS.get(self)==(*self.seal,self.created_static,self.lease_class,self.abort_method,self.abort_code,*release)
             and _SESSION_SEALS.get(self) is original
             and (not release or (self.state=='releasing' and release[0][0] is self.pump
                  and release[0][1] is epoch and self.g['_NFS_CHILD_EPOCHS'].get(self.owner) is epoch)),
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
                if frame['type']=='nfs-readonly-roots':
                    response=self.owner.nfs_readonly_roots_reply(frame);self.pump.write(response);continue
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
        original=_SESSION_SEALS[self]
        if operation=='release':
            epoch=self.g['_NFS_CHILD_EPOCHS'].get(self.owner)
            need(epoch is not None and epoch[0] is self and epoch[1]==self.cid,'nfs-session-original-release-epoch')
            self.state='releasing'
            _SESSION_SEALS[self]=(*original,(self.pump,epoch,self.last))
        try:
            self.pump.write(dict(type='nfs-host',nonce=self.owner.plan['nonce'],sequence=self.last,payload=dict(operation=operation,stopped=stopped)))
            result=self.until('nfs-done' if operation=='release' else 'nfs-result')
            if operation=='release':
                self.pump.finish()
                need(_SESSION_SEALS.get(self)==(*original,(self.pump,epoch,self.last-1)),
                     'nfs-session-original-release-completed')
                _SESSION_SEALS[self]=original;self.state='finished'
            return result
        except BaseException:
            self.state='failed';raise
