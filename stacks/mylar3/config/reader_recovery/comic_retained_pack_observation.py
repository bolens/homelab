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
_PROCESS_IMAGES=weakref.WeakKeyDictionary()
IMAGE_SOURCE_PREFIXES=('/app','/opt/mylar-publication-launch')
IMAGE_SOURCE_UID=0


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
        def attributes(fd):
            keys=os.listxattr(fd);need(len(keys)<=64,'owner-observation-xattr-count')
            result={};size=0
            for key in keys:
                value=os.getxattr(fd,key);size+=len(key.encode())+2*len(value)
                need(size<=1048576,'owner-observation-xattr-bound');result[key]=value.hex()
            return result
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
                retain(attrs,text,attributes(fd));retain(hashes,text,digest.hexdigest())
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


def process_ticks(pid):
    fd=os.open('/proc/'+str(pid)+'/stat',os.O_RDONLY|os.O_NOFOLLOW)
    try:raw=os.read(fd,65537)
    finally:os.close(fd)
    need(len(raw)<=65536,'image-process-bound')
    fields=raw.rsplit(b')',1)[1].split()
    return fields[19]


def image_mounts(fd):
    os.lseek(fd,0,os.SEEK_SET);result=bytearray()
    while block:=os.read(fd,65536):
        result.extend(block)
        need(len(result)<=4*1024**2,'image-mountinfo-bound')
    return bytes(result)


def _close_image_fds(originals):
    errors=[]
    for fd,wanted in reversed(originals):
        try:
            z=os.fstat(fd)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=wanted:
                raise ValueError('image-cleanup-foreign-FD')
            os.close(fd)
        except (OSError,ValueError) as error:errors.append(error)
    if errors:raise errors[0]


class ProcessImageObservation:
    """Original image source FDs; closure requires no Docker or HTTP under Writer."""
    __slots__=('__weakref__',)
    def __init__(self,*args,**kwargs):raise ValueError('Original process image required')
    @classmethod
    def capture(cls,runtime,role,pins):
        import comic_retained_pack_parent as parent
        if cls is not ProcessImageObservation:raise ValueError('image-original-class')
        table=_PROCESS_IMAGES
        cleanup=_close_image_fds
        helpers=tuple((name,globals()[name],globals()[name].__code__,globals()[name].__defaults__)
                      for name in ('need','absolute','encode','nine','five','process_ticks','image_mounts','_close_image_fds'))
        methods=tuple((name,getattr(cls,name).__func__ if name=='capture' else getattr(cls,name))
                      for name in ('capture','data','nodes','close','release'))
        methods=tuple((name,function,function.__code__,function.__defaults__) for name,function in methods)
        need(os.geteuid()==0 and type(runtime) is parent.ConfiguredRuntime and role in ('native','worker'),
             'image-owning-root-runtime')
        parent.ConfiguredRuntime.close_local(runtime)
        need(type(pins) is dict and 1<=len(pins)<=512,'image-source-map-bound')
        expected=tuple(sorted((absolute(path),digest) for path,digest in pins.items()))
        need(all(any(Path(path).is_relative_to(Path(prefix)) for prefix in IMAGE_SOURCE_PREFIXES)
                 and type(digest) is str and len(digest)==64 and all(c in '0123456789abcdef' for c in digest)
                 for path,digest in expected),'image-fixed-source-paths')
        pid=runtime.baseline['native']['State']['Pid'] if role=='native' else runtime.selected_pid
        need(type(pid) is int and pid>0,'image-original-process')
        tick=process_ticks(pid);owner=(os.getpid(),threading.get_ident());fds=[];owned=[];published=False
        def held(fd):
            fds.append(fd);z=os.fstat(fd);owned.append((fd,(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)));return fd
        try:
            root=held(os.open('/proc/'+str(pid)+'/root',os.O_RDONLY|os.O_DIRECTORY))
            namespace=held(os.open('/proc/'+str(pid)+'/ns/mnt',os.O_RDONLY))
            mount_fd=held(os.open('/proc/'+str(pid)+'/mountinfo',os.O_RDONLY|os.O_NOFOLLOW))
            mount9=nine(os.fstat(mount_fd));mount_bytes=image_mounts(mount_fd)
            directories={'/':(root,five(os.fstat(root)))};files=[];total=0
            def directory(path):
                if path in directories:return directories[path][0]
                value=Path(path);up=directory(str(value.parent))
                fd=held(os.open(value.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=up))
                directories[path]=(fd,five(os.fstat(fd)));return fd
            for mount in runtime.baseline[role]['Mounts']:
                for ancestor in Path(mount['Destination']).parents:directory(str(ancestor))
            for path,digest in expected:
                value=Path(path);directory_fd=directory(str(value.parent))
                fd=held(os.open(value.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory_fd))
                stamp=nine(os.fstat(fd))
                need(stat.S_ISREG(stamp[5]) and stamp[6]==IMAGE_SOURCE_UID and not stamp[5]&0o022
                     and stamp[8]==1 and 0<stamp[2]<=4*1024**2,'image-protected-source')
                sha=hashlib.sha256();size=0
                while block:=os.read(fd,65536):
                    size+=len(block);total+=len(block)
                    need(size<=stamp[2] and total<=MAX_WIRE and time.monotonic()<runtime.deadline,'image-source-byte-bound')
                    sha.update(block)
                attributes={key:os.getxattr(fd,key).hex() for key in os.listxattr(fd)}
                need(len(attributes)<=64 and sum(len(k.encode())+len(v) for k,v in attributes.items())<=1048576,'image-source-attributes')
                need(size==stamp[2] and sha.hexdigest()==digest and nine(os.fstat(fd))==stamp,'image-source-original-bytes')
                files.append((path,fd,stamp,digest,attributes))
            output=encode({path:dict(signature9=list(stamp),sha256=digest,attrs=attributes) for path,fd,stamp,digest,attributes in files})
            value=object.__new__(cls)
            original=(runtime,role,pid,tick,owner,runtime.deadline,root,namespace,nine(os.fstat(namespace)),
                      tuple(directories.items()),tuple(files),output,parent._RUNTIMES,parent._RUNTIMES[runtime],
                      runtime.process,tuple(fds),process_ticks,process_ticks.__code__,table,methods,helpers,
                      mount_fd,mount9,mount_bytes,tuple(owned))
            need(_PROCESS_IMAGES is table,'image-original-factory-table')
            _PROCESS_IMAGES[value]=original;value.close();published=True;return value
        finally:
            if not published:
                primary=sys.exc_info()[1]
                try:cleanup(tuple(owned))
                except BaseException as error:
                    if primary is not None:raise primary from error
                    raise
    def data(self):
        original=self.close();answer=json.loads(original[11]);self.close();return answer
    def nodes(self):
        original=self.close();answer={path:list(stamp) for path,(_,stamp) in original[9]};self.close();return answer
    def close(self):
        import comic_retained_pack_parent as parent
        original=_PROCESS_IMAGES.get(self)
        if type(self) is not ProcessImageObservation or original is None:raise ValueError('image-original-observation')
        runtime,role,pid,tick,owner,deadline,root,namespace,ns9,directories,files,_,table,entry,process,_,ticks,code=original[:18]
        if not ((os.getpid(),threading.get_ident())==owner and os.geteuid()==0 and time.monotonic()<deadline
             and table is parent._RUNTIMES and table.get(runtime) is entry
             and process_ticks is ticks and process_ticks.__code__ is code and original[18] is _PROCESS_IMAGES):
            raise ValueError('image-original-custody')
        for name,function,source,defaults in original[19]:
            current=getattr(type(self),name);current=current.__func__ if name=='capture' else current
            if current is not function or current.__code__ is not source or current.__defaults__ is not defaults:raise ValueError('image-original-method')
        for name,function,source,defaults in original[20]:
            current=globals().get(name)
            if current is not function or current.__code__ is not source or current.__defaults__ is not defaults:raise ValueError('image-original-helper')
        parent.ConfiguredRuntime.close_local(runtime)
        terminal=parent._TERMINALS.get(runtime)
        exited=(role=='worker' and terminal is not None)
        if exited:
            need(terminal==(runtime.selected,runtime.selected_started,runtime.selected_static,process)
                 and runtime.process is process and process.poll()==0,'image-owning-natural-exit')
        else:
            need(process_ticks(pid)==tick and nine(os.stat('/proc/'+str(pid)+'/ns/mnt'))==ns9
                 and five(os.stat('/proc/'+str(pid)+'/root'))==dict(directories)['/'][1],
                 'image-original-live-namespace')
            need(nine(os.fstat(original[21]))==original[22] and image_mounts(original[21])==original[23],
                 'image-original-mount-geometry')
        for path,(fd,stamp) in directories:
            need(five(os.fstat(fd))==stamp,'image-original-directory-FD')
            if path!='/':
                p=Path(path);up=dict(directories)[str(p.parent)][0]
                need(five(os.stat(p.name,dir_fd=up,follow_symlinks=False))==stamp,'image-original-directory-path')
        for path,fd,stamp,digest,attributes in files:
            p=Path(path);directory=dict(directories)[str(p.parent)][0]
            need(nine(os.fstat(fd))==stamp and nine(os.stat(p.name,dir_fd=directory,follow_symlinks=False))==stamp,
                 'image-original-source')
        need(nine(os.fstat(namespace))==ns9 and _PROCESS_IMAGES.get(self) is original,'image-final-original')
        return original
    def release(self):
        original=_PROCESS_IMAGES.get(self)
        if type(self) is not ProcessImageObservation or original is None:raise ValueError('image-original-release')
        close,close_code=next((fn,code) for name,fn,code,_ in original[19] if name=='close')
        cleanup,cleanup_code=next((fn,code) for name,fn,code,_ in original[20] if name=='_close_image_fds')
        try:
            if close.__code__ is not close_code:raise ValueError('image-original-close-implementation')
            close(self)
        finally:
            primary=sys.exc_info()[1]
            if original[18].get(self) is original:original[18].pop(self)
            try:
                if cleanup.__code__ is not cleanup_code:raise ValueError('image-original-cleanup-implementation')
                cleanup(original[24])
            except BaseException as error:
                if primary is not None:raise primary from error
                raise
