"""Independent bounded owner-principal media observations; no lifecycle rights.

Root retains its identity. A private child reads UID1000-owned media, including
root-squashed NFS. Neither saved JSON nor construction of this mechanism grants
backup, publication, worker or reader authority.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import select
import signal
import stat
import sys
import threading
import time
import weakref

MAX_NODES=100000
MAX_WIRE=64*1024**2
MAX_HASH_BYTES=32*1024**3
_OBSERVATIONS=weakref.WeakKeyDictionary()
_SEALS=weakref.WeakKeyDictionary()


def need(value,reason):
    if not value:raise ValueError(reason)


def encode(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def nine(z):
    return (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)


def five(z):return (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)


def absolute(value):
    need(type(value) is str and '\x00' not in value and Path(value).is_absolute()
         and str(Path(value))==value and not value.startswith('//') and '..' not in Path(value).parts,
         'owner-observation-canonical-path')
    return value


def _measure(roots,streams,deadline):
    """Only this fixed code runs in the private owner process."""
    need(os.geteuid()==os.getegid()==1000,'owner-observation-principal')
    files={};nodes={};names={};hashes={};attrs={}
    directories={}
    def directory(text):
        if text in directories:return directories[text]
        path=Path(text)
        if text=='/':fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        else:fd=os.open(path.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,
                        dir_fd=directory(str(path.parent)))
        directories[text]=fd
        return fd
    def observed(text):
        if text=='/':return os.fstat(directory('/'))
        path=Path(text)
        return os.stat(path.name,dir_fd=directory(str(path.parent)),follow_symlinks=False)
    try:
        wire_bytes=128
        def alive():need(time.monotonic()<deadline,'owner-observation-deadline')
        def retain(group,key,value):
            nonlocal wire_bytes
            if key not in group:
                wire_bytes+=len(encode({key:value}))+2
                need(wire_bytes<=MAX_WIRE,'owner-observation-aggregate-bound')
                group[key]=value
        def children(text):
            result=[];spelling=0
            with os.scandir(directory(text)) as entries:
                for entry in entries:
                    alive();spelling+=len(encode(entry.name))+1
                    need(len(result)<MAX_NODES and spelling<=MAX_WIRE,'owner-observation-namespace-bound')
                    result.append(entry.name)
            return tuple(sorted(result))
        # Capture all known roots and first ancestors before enumerating anything.
        for text in roots:
            path=Path(text)
            for parent in (path,*path.parents):
                value=five(observed(str(parent)));need(stat.S_ISDIR(value[2]),'owner-observation-directory')
                name=str(parent);need(name not in nodes or nodes[name]==value,'owner-observation-first-node')
                retain(nodes,name,value)
            retain(files,text,nine(observed(str(path))))
        pending=list(reversed(roots));seen=set()
        while pending:
            alive();text=pending.pop()
            if text in seen:continue
            seen.add(text);value=nine(observed(text))
            need(text not in files or files[text]==value,'owner-observation-first-file')
            retain(files,text,value)
            need(len(files)<=MAX_NODES,'owner-observation-node-bound')
            if stat.S_ISDIR(value[5]):
                node=(value[0],value[1],value[5],value[6],value[7])
                need(text not in nodes or nodes[text]==node,'owner-observation-first-node')
                need(five(os.fstat(directory(text)))==node,'owner-observation-directory-FD')
                retain(nodes,text,node)
                entries=children(text);retain(names,text,entries)
                need(len(files)+len(pending)+len(entries)<=MAX_NODES,'owner-observation-node-bound')
                pending.extend(str(Path(text)/name) for name in reversed(entries))
        # Streams must be members of the original complete trees; no arbitrary
        # extra file selector or symlink-following open is admitted here.
        total=0
        for text in streams:
            alive();need(text in files,'owner-observation-stream-membership');original=files[text]
            need(stat.S_ISREG(original[5]) and original[8]==1,'owner-observation-exclusive-stream')
            total+=original[2];need(total<=MAX_HASH_BYTES,'owner-observation-byte-bound')
            fd=os.open(Path(text).name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,
                       dir_fd=directory(str(Path(text).parent)))
            try:
                need(nine(os.fstat(fd))==original,'owner-observation-original-FD')
                digest=hashlib.sha256();size=0
                while block:=os.read(fd,1048576):
                    alive();size+=len(block);need(size<=original[2],'owner-observation-stream-growth');digest.update(block)
                need(size==original[2] and nine(os.fstat(fd))==original,'owner-observation-stream-original')
                keys=os.listxattr(fd);need(len(keys)<=64,'owner-observation-xattr-count')
                attributes={};attribute_bytes=0
                for key in keys:
                    raw=os.getxattr(fd,key);attribute_bytes+=len(key.encode())+2*len(raw)
                    need(attribute_bytes<=1048576,'owner-observation-xattr-bound');attributes[key]=raw.hex()
                retain(attrs,text,attributes);retain(hashes,text,digest.hexdigest())
                need(nine(os.fstat(fd))==original,'owner-observation-stream-final-FD')
            finally:os.close(fd)
        # Full final physical closure follows content and attribute callbacks.
        for text,expected in names.items():
            alive();need(children(text)==expected,'owner-observation-final-namespace')
        for text,expected in nodes.items():
            need(five(observed(text))==expected and five(os.fstat(directory(text)))==expected,
                 'owner-observation-final-node')
        for text,expected in files.items():
            need(nine(observed(text))==expected,'owner-observation-final-file')
        alive()
        return dict(files=files,nodes=nodes,names=names,hashes=hashes,attrs=attrs)
    finally:
        for fd in reversed(tuple(directories.values())):
            try:os.close(fd)
            except OSError:pass  # private child exits immediately after this fixed reader


def _owner_read(roots,streams,deadline):
    encoder=encode
    need(os.geteuid() in (0,1000),'owner-observation-parent-principal')
    need(len(os.listdir('/proc/self/task'))==1,'owner-observation-single-thread-required')
    original_owner=(os.getpid(),os.geteuid(),os.getegid(),threading.get_ident())
    read_fd,write_fd=os.pipe();pid=None;reaped=False
    try:
        pid=os.fork()
        if pid==0:
            os.close(read_fd)
            try:
                if os.geteuid()==0:os.setgroups([]);os.setgid(1000);os.setuid(1000)
                body=encoder(dict(version=1,kind='owner-media-observation',data=_measure(roots,streams,deadline)))
                need(len(body)<=MAX_WIRE,'owner-observation-wire-bound')
                view=memoryview(body)
                while view:
                    need(time.monotonic()<deadline,'owner-observation-deadline')
                    count=os.write(write_fd,view[:65536]);need(count>0,'owner-observation-child-write');view=view[count:]
                os.close(write_fd);os._exit(0)
            except BaseException as error:
                # Do not export private paths, contents or exception payloads.
                reason=('permission' if isinstance(error,PermissionError) else
                        'not-found' if isinstance(error,FileNotFoundError) else
                        'bound-or-changed' if isinstance(error,ValueError) else
                        'io' if isinstance(error,OSError) else 'unexpected')
                try:os.write(write_fd,encoder(dict(version=1,kind='owner-media-refused',reason=reason)))
                except BaseException:pass
                os._exit(1)
        os.close(write_fd);write_fd=None;parts=[];size=0
        while True:
            remaining=deadline-time.monotonic()
            need(remaining>0 and select.select([read_fd],[],[],remaining)[0],'owner-observation-parent-deadline')
            block=os.read(read_fd,65536)
            if not block:break
            size+=len(block);need(size<=MAX_WIRE,'owner-observation-parent-wire-bound');parts.append(block)
        observed,status=os.waitpid(pid,0);reaped=True
        raw=b''.join(parts);value=json.loads(raw)
        if observed==pid and os.WIFEXITED(status) and os.WEXITSTATUS(status)==1:
            need(type(value) is dict and set(value)=={'version','kind','reason'}
                 and type(value['version']) is int and value['version']==1
                 and value['kind']=='owner-media-refused'
                 and value['reason'] in ('permission','not-found','bound-or-changed','io','unexpected'),
                 'owner-observation-invalid-refusal')
            raise ValueError('owner-observation-child-'+value['reason'])
        need(observed==pid and os.WIFEXITED(status) and os.WEXITSTATUS(status)==0,'owner-observation-child-refused')
        need(type(value) is dict and set(value)=={'version','kind','data'} and type(value['version']) is int
             and value['version']==1 and value['kind']=='owner-media-observation' and encoder(value)==raw,
             'owner-observation-child-envelope')
        need((os.getpid(),os.geteuid(),os.getegid(),threading.get_ident())==original_owner
             and time.monotonic()<deadline,'owner-observation-parent-original')
        return value['data']
    finally:
        primary=sys.exc_info()[0];cleanup_failed=False
        for fd in (read_fd,write_fd):
            if fd is None:continue
            try:os.close(fd)
            except OSError:cleanup_failed=True
        if pid is not None and pid>0 and not reaped:
            try:waited,_=os.waitpid(pid,os.WNOHANG)
            except OSError:cleanup_failed=True;waited=None
            if waited==0:
                # An unreaped direct child cannot have its PID reused. A kill
                # error must not prevent the independent reap attempt.
                try:os.kill(pid,signal.SIGKILL)
                except OSError:cleanup_failed=True
                try:os.waitpid(pid,0)
                except OSError:cleanup_failed=True
        if cleanup_failed and primary is None:raise ValueError('owner-observation-cleanup-held')


class OwnerObservation:
    __slots__=('__weakref__',)
    def __init__(self,*args,**kwargs):raise ValueError('Original owner observation required')
    @classmethod
    def capture(cls,roots,streams,*,deadline):
        need(type(roots) in (list,tuple) and 1<=len(roots)<=16 and type(streams) in (list,tuple)
             and len(streams)<=MAX_NODES,'owner-observation-input-bound')
        roots=tuple(absolute(p) for p in roots);streams=tuple(absolute(p) for p in streams)
        need(len(set(roots))==len(roots) and len(set(streams))==len(streams)
             and all(not Path(a).is_relative_to(Path(b)) for a in roots for b in roots if a!=b),
             'owner-observation-distinct-roots')
        need(type(deadline) in (int,float) and math.isfinite(deadline)
             and time.monotonic()<deadline,'owner-observation-original-deadline')
        owner=(os.getpid(),os.geteuid(),os.getegid(),threading.get_ident())
        table=_OBSERVATIONS;seals=_SEALS
        function=_owner_read;code=function.__code__;measure=_measure;measure_code=measure.__code__
        helpers=tuple((name,globals()[name],globals()[name].__code__,globals()[name].__defaults__,
                       globals()[name].__kwdefaults__) for name in ('encode','need','nine','five','absolute'))
        methods=tuple((name,vars(cls)[name],vars(cls)[name].__code__,vars(cls)[name].__defaults__,
                       vars(cls)[name].__kwdefaults__) for name in ('original','data','close'))
        data=function(roots,streams,deadline);encoded=encode(data)
        value=object.__new__(cls)
        need(_OBSERVATIONS is table and _SEALS is seals,'owner-observation-initial-registry')
        original=(roots,streams,deadline,owner,encoded,function,code,measure,measure_code,table,seals,helpers,methods)
        _OBSERVATIONS[value]=original;_SEALS[value]=original;value.original();return value
    def original(self):
        original=_OBSERVATIONS.get(self)
        if not (type(self) is OwnerObservation and original is not None and _SEALS.get(self) is original
             and _OBSERVATIONS is original[9] and _SEALS is original[10]
             and (os.getpid(),os.geteuid(),os.getegid(),threading.get_ident())==original[3]
             and time.monotonic()<original[2] and _owner_read is original[5]
             and _owner_read.__code__ is original[6] and _measure is original[7]
             and _measure.__code__ is original[8]):raise ValueError('owner-observation-original-custody')
        for name,function,code,defaults,kwdefaults in original[11]:
            current=globals().get(name)
            if (current is not function or current.__code__ is not code or current.__defaults__ is not defaults
                    or current.__kwdefaults__ is not kwdefaults):raise ValueError('owner-observation-original-helper')
        for name,function,code,defaults,kwdefaults in original[12]:
            current=vars(OwnerObservation).get(name)
            if (current is not function or current.__code__ is not code or current.__defaults__ is not defaults
                    or current.__kwdefaults__ is not kwdefaults):raise ValueError('owner-observation-original-method')
        return original
    def data(self):
        original=self.original();result=json.loads(original[4])
        need(self.original() is original,'owner-observation-final-registry');return result
    def close(self):
        original=self.original();current=original[5](original[0],original[1],original[2])
        if self.original() is not original:raise ValueError('owner-observation-final-registry')
        need(encode(current)==original[4],'owner-observation-unchanged-media')
        result=json.loads(original[4])
        need(self.original() is original,'owner-observation-final-registry')
        return result
