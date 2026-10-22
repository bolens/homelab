"""Retained UID1000 NFS child; no lifecycle/ACK authority from serialized facts.

The owning host supplies explicitly produced child-private controls. This module
never transforms references, invokes Docker locally, or reconstructs a canary.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import select
import stat
import subprocess
import time
import types

MAX = 16 * 1024**2
ACTIVE_SOURCE_SHA = None
LEASE_INTERFACE_SOURCE_SHA = None
class Held(ValueError):
    pass

def need(ok, reason):
    if not ok:
        raise Held(reason)

def nine(z):
    return (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)

def five(z):
    return (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)

def decode(raw):
    def pairs(items):
        result={}
        for key,value in items:
            need(key not in result,'duplicate-key');result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(Held('nonfinite')))

def encode(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def namespace_reply(bootstrap,result):
    keys={'version','kind','plan','source','roles','ancestors'}
    need(type(bootstrap) is dict and set(bootstrap)==keys and type(bootstrap['version']) is int and bootstrap['version']==1
         and bootstrap['kind']=='parent-original-current-three-role-bootstrap' and bootstrap['ancestors']=={},'child-role-bootstrap')
    need(type(result) is dict and set(result)==keys and result['kind']=='parent-original-current-three-role-selectors'
         and type(result['version']) is int and result['version']==1
         and all(encode(result[k])==encode(bootstrap[k]) for k in ('plan','source','roles')),'child-original-role-namespace')
    need(type(result['ancestors']) is dict and result['ancestors'],'child-role-actual-ancestors')
    wanted={str(p) for key in ('plan','source') for p in Path(result[key]['path']).parents}
    need(set(result['ancestors'])==wanted and all(type(v) is list and len(v)==5 and all(type(x) is int for x in v) for v in result['ancestors'].values()),'child-role-complete-namespace')
    return encode(result)

def original(ref):
    need(type(ref) is dict and set(ref)=={'path','sha256','signature9'},'child-ref-shape')
    path=Path(ref['path']);expected=tuple(ref['signature9'])
    need(path.is_absolute() and str(path)==ref['path'] and '..' not in path.parts and len(expected)==9
         and all(type(v) is int for v in expected) and stat.S_ISREG(expected[5])
         and stat.S_IMODE(expected[5])==0o600 and expected[6]==os.geteuid() and expected[8]==1
         and 0<expected[2]<=MAX,'child-ref-private')
    nodes={str(p):five(os.lstat(p)) for p in path.parents}
    need(all(stat.S_ISDIR(v[2]) for v in nodes.values()),'child-ref-ancestors')
    directory=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        need(five(os.fstat(directory))==nodes['/'],'child-root-FD')
        current=Path('/')
        for part in path.parts[1:-1]:
            current/=part
            nxt=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=directory)
            try:need(five(os.fstat(nxt))==nodes[str(current)],'child-parent-FD')
            except BaseException:
                os.close(nxt);raise
            os.close(directory);directory=nxt
        fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=directory)
    finally:os.close(directory)
    try:
        need(nine(os.fstat(fd))==expected,'child-ref-FD');raw=bytearray()
        while len(raw)<expected[2]:
            block=os.read(fd,min(65536,expected[2]-len(raw)));need(bool(block),'child-ref-short');raw.extend(block)
        need(hashlib.sha256(raw).hexdigest()==ref['sha256'] and nine(os.fstat(fd))==expected,'child-ref-hash')
    finally:
        os.close(fd)
    for p,v in nodes.items():
        if five(os.lstat(p))!=v:raise Held('child-ref-final5')
    if nine(os.lstat(path))!=expected:raise Held('child-ref-final9')
    return bytes(raw),(str(path),expected),tuple(nodes.items())

class Channel:
    """Original inherited pipes, nonce, independent monotonically increasing seq."""
    def __init__(self,read_fd,write_fd,nonce,seconds):
        need(type(nonce) is str and len(nonce)==64 and all(c in '0123456789abcdef' for c in nonce),'child-nonce')
        need(type(seconds) is int and 1<=seconds<=3600,'child-seconds')
        self.read_fd,self.write_fd=read_fd,write_fd
        # FIFO I/O changes mtime/ctime. Retain the original object and security
        # identity, as the owning host pump does, rather than content metadata.
        self.facts=(five(os.fstat(read_fd)),five(os.fstat(write_fd)))
        need(all(stat.S_ISFIFO(v[2]) for v in self.facts),'child-original-pipes')
        self.nonce,self.sequence,self.deadline=nonce,0,time.monotonic()+seconds;self.pending=bytearray()
    def close(self):
        need((five(os.fstat(self.read_fd)),five(os.fstat(self.write_fd)))==self.facts,'child-original-pipe-drift')
        need(time.monotonic()<self.deadline,'child-deadline')
    def send(self,kind,payload):
        self.close();self.sequence+=1
        raw=encode(dict(type=kind,nonce=self.nonce,sequence=self.sequence,payload=payload))+b'\n'
        need(len(raw)<=MAX,'child-frame-bound');view=memoryview(raw)
        while view:
            self.close();need(select.select([],[self.write_fd],[],max(0,self.deadline-time.monotonic()))[1],'child-write-timeout')
            n=os.write(self.write_fd,view[:4096]);need(n>0,'child-write-short');view=view[n:]
        self.close();return self.sequence
    def receive(self,sequence):
        while b'\n' not in self.pending:
            self.close();need(select.select([self.read_fd],[],[],max(0,self.deadline-time.monotonic()))[0],'child-read-timeout')
            block=os.read(self.read_fd,65536);need(bool(block),'child-lost-host');self.pending.extend(block)
            need(len(self.pending)<=MAX,'child-response-bound')
        raw,_,rest=self.pending.partition(b'\n');self.pending=bytearray(rest);value=decode(raw)
        need(type(value) is dict and set(value)=={'type','nonce','sequence','payload'}
             and value['type']=='nfs-host' and value['nonce']==self.nonce
             and type(value['sequence']) is int and value['sequence']==sequence,'child-host-frame')
        self.close();return value['payload']
    def engine(self,argv,**kwargs):
        need(type(argv) is list and all(type(x) is str for x in argv),'child-engine-argv')
        need(set(kwargs)<= {'input','capture_output','timeout','check'} and kwargs.get('capture_output') is True
             and kwargs.get('check') is False and type(kwargs.get('timeout')) in (int,float)
             and 0<kwargs['timeout']<=900,'child-engine-shape')
        data=kwargs.get('input');need(data is None or type(data) is bytes and len(data)<=8*1024**2,'child-engine-input')
        sequence=self.send('nfs-engine',dict(argv=argv,input=None if data is None else base64.b64encode(data).decode(),timeout=kwargs['timeout']))
        result=self.receive(sequence)
        need(type(result) is dict and set(result)=={'returncode','stdout','stderr'} and type(result['returncode']) is int,'child-engine-response')
        out=base64.b64decode(result['stdout'],validate=True);err=base64.b64decode(result['stderr'],validate=True)
        need(len(out)<=8*1024**2 and len(err)<=4*1024**2,'child-engine-output')
        return subprocess.CompletedProcess(argv,result['returncode'],out,err)
    def role_namespace(self,bootstrap):
        # Validate the explicitly pending original before any host callback.
        need(type(bootstrap) is dict and set(bootstrap)=={'version','kind','plan','source','roles','ancestors'}
             and type(bootstrap['version']) is int and bootstrap['version']==1
             and bootstrap.get('kind')=='parent-original-current-three-role-bootstrap'
             and bootstrap.get('ancestors')=={},'child-role-bootstrap')
        original_bootstrap=encode(bootstrap)
        need(len(original_bootstrap)<=8*1024**2,'child-bootstrap-bound')
        seq=self.send('nfs-role-namespace',{})
        result=self.receive(seq)
        need(encode(bootstrap)==original_bootstrap,'child-original-bootstrap-after-reply')
        return namespace_reply(decode(original_bootstrap),result)

def serve(packet_ref):
    need(os.geteuid()==1000 and os.getegid()==1000,'nfs-child-actual-uid')
    raw,packet_file,packet_nodes=original(packet_ref);packet=decode(raw)
    host=type(packet) is dict and packet.get('kind') in ('owning-nfs-retained-host-lease-child-v1','owning-nfs-retained-host-lease-child-v2')
    namespace=host and packet['kind']=='owning-nfs-retained-host-lease-child-v2'
    keys={'version','kind','nonce','seconds','active_source','active_input','roles'}
    if host:keys.add('lease_interface')
    need(type(packet) is dict and set(packet)==keys and type(packet['version']) is int and packet['version']==1
         and packet['kind'] in ('owning-nfs-retained-child-v1','owning-nfs-retained-host-lease-child-v1','owning-nfs-retained-host-lease-child-v2'),'nfs-child-packet')
    source,source_file,source_nodes=original(packet['active_source'])
    need(type(ACTIVE_SOURCE_SHA) is str and len(ACTIVE_SOURCE_SHA)==64 and packet['active_source']['sha256']==ACTIVE_SOURCE_SHA,'nfs-child-source-default-unbound')
    _,input_file,input_nodes=original(packet['active_input']);roles,role_file,role_nodes=original(packet['roles'])
    channel=Channel(0,1,packet['nonce'],packet['seconds'])
    module=types.ModuleType('owning_nfs_child_active');module.__file__=packet['active_source']['path']
    exec(compile(source,module.__file__,'exec'),module.__dict__)
    args=argparse.Namespace(input=packet['active_input']['path'],input_sha256=packet['active_input']['sha256'],source_sha256=packet['active_source']['sha256'],execute=True)
    if host:
        ref=packet['lease_interface'];interface_raw,interface_file,interface_nodes=original(ref)
        need(type(LEASE_INTERFACE_SOURCE_SHA) is str and ref['sha256']==LEASE_INTERFACE_SOURCE_SHA,'nfs-child-host-interface-default-unbound')
        interface=types.ModuleType('owning_nfs_host_lease_interface');interface.__file__=ref['path'];exec(compile(interface_raw,interface.__file__,'exec'),interface.__dict__)
        lease=interface.ChildLeaseInterface(channel)
        if namespace:roles=channel.role_namespace(decode(roles))
        canary=module.run_active_host_factual(args,channel.engine,interface_module=interface,lease_interface=lease,interface_ref=ref,roles=roles)
    else:
        interface_file=None;interface_nodes=()
        canary=module.run_active_factual(args,channel.engine,roles=roles)
    need(type(canary) is module.ActiveNFSCanaryObservation,'nfs-child-original-canary')
    # The object stays in this process. This frame is facts, never a canary grant.
    seq=channel.send('nfs-ready',dict(binding=canary.binding,mount=canary.mount,device=canary.device,files=canary.files,nodes=canary.nodes,names=[(p,sorted(v)) for p,v in canary.names],absent=canary.absent))
    while True:
        command=channel.receive(seq)
        need(type(command) is dict and set(command)=={'operation','stopped'},'nfs-child-operation')
        operation=command['operation'];need(operation in ('current','check','release') and type(command['stopped']) is bool,'nfs-child-operation-kind')
        canary.close()
        if operation=='current':result=canary.current(stopped=command['stopped'])
        else:result=None
        for p,v in (*packet_nodes,*source_nodes,*input_nodes,*role_nodes,*interface_nodes):
            if five(os.lstat(p))!=v:raise Held('nfs-child-control5')
        for p,v in (packet_file,source_file,input_file,role_file,*((interface_file,) if interface_file is not None else ())):
            if nine(os.lstat(p))!=v:raise Held('nfs-child-control9')
        seq=channel.send('nfs-done' if operation=='release' else 'nfs-result',result)
        if operation=='release':
            canary.close();channel.close()
            for p,v in (*packet_nodes,*source_nodes,*input_nodes,*role_nodes,*interface_nodes):
                z=os.lstat(p)
                if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('nfs-child-release5')
            for p,v in (packet_file,source_file,input_file,role_file,*((interface_file,) if interface_file is not None else ())):
                z=os.lstat(p)
                if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('nfs-child-release9')
            return

def failure_diagnostic(error):
    """Bounded transport diagnosis without exception text, locals or host paths."""
    frames=[];trace=error.__traceback__
    while trace is not None:
        name=Path(trace.tb_frame.f_code.co_filename).name
        if name not in ('comic_nfs_uid_child.py','nfs-uid-child.py','comic_nfs_lease_session.py',
                        'comic_negative_nfs_active_parent.py'):
            name='external'
        frames.append(dict(source=name,line=trace.tb_lineno));frames=frames[-8:]
        trace=trace.tb_next
    kind=('held' if type(error) is Held else
          'os-error' if isinstance(error,OSError) else 'other')
    reason=None
    if type(error) is Held and len(error.args)==1 and type(error.args[0]) is str:
        if error.args[0] in ('child-original-pipe-drift','child-deadline',
                            'child-read-timeout','child-lost-host','child-host-frame',
                            'child-write-timeout','child-write-short',
                            'child-response-bound','child-frame-bound'):
            reason=error.args[0]
    return encode(dict(kind='nfs-child-failure',exception=kind,reason=reason,
                       frames=frames,terminal_accepted=False,automatic_replay=False))+b'\n'

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--packet',required=True);parser.add_argument('--packet-sha256',required=True);parser.add_argument('--packet9',required=True)
    arguments=parser.parse_args()
    try:serve(dict(path=arguments.packet,sha256=arguments.packet_sha256,signature9=decode(arguments.packet9)))
    except BaseException as error:
        try:os.write(2,failure_diagnostic(error))
        except BaseException:pass
        raise SystemExit(2) from None
