"""Default-disabled one-shot worker; original pipe/session through backup barrier."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import sys
import stat
import threading
import time
import weakref

ENABLED=False
PARENT_SOURCE_SHA=None
TOTAL_SECONDS=3600
WAITING_SECONDS=1800
FRAME_BYTES=65536
MEMBERS=1
_STATE=weakref.WeakKeyDictionary()
_TERMINAL_SEND=weakref.WeakKeyDictionary()


def need(value,reason):
    if not value:raise ValueError(reason)


def encode(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def nine(z):return (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
def five(z):return (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)


class Pipe:
    """Bounded original actual pipe, independently useful mechanism, never backup authority."""
    def __init__(self,read_fd,write_fd,nonce,deadline):
        need(type(nonce) is str and len(nonce)==64 and all(c in '0123456789abcdef' for c in nonce),'pipe-nonce')
        self.read_fd=read_fd;self.write_fd=write_fd;self.nonce=nonce;self.deadline=deadline
        self.original=(nine(os.fstat(read_fd)),nine(os.fstat(write_fd)));self.sequence=0;self.pid=os.getpid();self.thread=threading.get_ident()
        need(all(s[5]&0o170000==0o010000 for s in self.original),'original-FIFO-required')
    def close_originals(self):
        need((os.getpid(),threading.get_ident())==(self.pid,self.thread) and time.monotonic()<self.deadline,'original-pipe-lifetime')
        for fd,wanted in zip((self.read_fd,self.write_fd),self.original):
            z=os.fstat(fd);need((z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)==wanted,'original-pipe-FD')
    def send(self,kind,challenge,payload):
        self.close_originals();need(type(challenge) is str and len(challenge)==64,'frame-challenge')
        data=encode(dict(version=1,kind=kind,nonce=self.nonce,sequence=self.sequence,challenge=challenge,payload=payload))+b'\n'
        need(len(data)<=FRAME_BYTES,'frame-bound');self.close_originals();offset=0
        while offset<len(data):
            need(select.select([], [self.write_fd],[],max(0,self.deadline-time.monotonic()))[1],'pipe-write-timeout')
            session=_TERMINAL_SEND.get(self)
            if session is not None:_close(session,terminal=True)
            offset+=os.write(self.write_fd,data[offset:]);self.close_originals()
        self.sequence+=1;return data[:-1]
    def receive(self,kind,challenge):
        self.close_originals();parts=bytearray()
        while True:
            need(select.select([self.read_fd],[],[],max(0,self.deadline-time.monotonic()))[0],'pipe-read-timeout')
            value=os.read(self.read_fd,1);need(value,'pipe-unknown-ACK');parts.extend(value)
            need(len(parts)<=FRAME_BYTES,'frame-bound')
            if value==b'\n':break
        raw=bytes(parts[:-1]);body=json.loads(raw)
        need(type(body) is dict and set(body)=={'version','kind','nonce','sequence','challenge','payload'} and type(body['version']) is int and body['version']==1 and type(body['sequence']) is int,'frame-schema')
        need(encode(body)==raw and (body['kind'],body['nonce'],body['sequence'],body['challenge'])==(kind,self.nonce,self.sequence,challenge),'original-frame')
        self.close_originals();self.last_received=raw;self.sequence+=1;return body['payload']


class WaitingSession:
    __slots__=('__weakref__',)
    def __init__(self,*a,**k):raise ValueError('Original same-live worker required')


def _close(value,*,terminal=False):
    c=_STATE.get(value);need(c is not None and (c['pid'],c['thread'])==(os.getpid(),threading.get_ident()),'original-waiting-session')
    owned_session=c['session'];original_pipe=c['pipe']
    c['pipe'].close_originals()
    from retained_pack_operations import existing
    need(existing(c['maintenance']) is c['session'],'same-original-session')
    # Actual Operations carries its immutable initialized originals through execute.
    # Verify them before allowing a parent message to advance selection.
    from retained_pack_operations import _initial_originals,_core
    owned=_core(c['session'])
    if terminal:
        import retained_pack_handoff as handoff
        from publication_guard import scope
        need(owned['phase']=='retained-observed' and handoff._core(owned['action'],'consumed')['maintenance'] is c['maintenance'],'control-original-consumed-action')
        original_action=owned['action'];original_terminal=handoff._TERMINAL_EXPORTS.get(original_action);original_core=handoff._CORES.get(original_action)
        need(original_terminal is not None and original_terminal[0] is original_core,'control-original-terminal-seal')
        with owned['writer'].hold(timeout=0),scope(c['maintenance'].worker,owned['writer']):
            terminal_frame=handoff.close_terminal(owned['action'])
    else:_initial_originals(owned)
    for path,wanted in c['source_files']:
        z=os.lstat(path);need((z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)==wanted,'control-original-source')
    for path,wanted in c['source_nodes']:
        z=os.lstat(path);need((z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)==wanted,'control-original-node')
    fd,path,wanted=c['worker_lock']
    for z in (os.fstat(fd),os.lstat(path)):
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=wanted:raise ValueError('control-original-worker-lock')
    m=c['maintenance'];binding=c['initial_binding']
    if (m.state,m.worker,tuple(m.worker.roots),m.worker.config['writer_state'],m.settings.get('ddl_cache'),m.settings.get('mylar_ddl_cache'),m.worker.config['mylar'].get('url'),m.worker.config['mylar'].get('config_dir','/mylar'),tuple((row['native'],row['worker']) for row in m.worker.config['publication_roots']))!=binding:raise ValueError('control-final-Maintenance')
    for name,fn,code in c['methods']:
        actual=getattr(m,name)
        if getattr(actual,'__func__',None) is not fn or fn.__code__ is not code:raise ValueError('control-original-method')
    if terminal:
        # All source/lock/method/FD helpers precede complete genuine post-CAS originals.
        handoff._raw(terminal_frame)
        for p,names in terminal_frame['names'].items():
            if tuple(sorted(os.listdir(p)))!=tuple(names):raise ValueError('control-terminal-namespace')
        for p,v in terminal_frame['nodes'].items():
            z=os.lstat(p)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=tuple(v):raise ValueError('control-terminal-node')
        for p,v in terminal_frame['files'].items():
            z=os.lstat(p)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=tuple(v):raise ValueError('control-terminal-file')
        for p in terminal_frame['absent']:
            try:os.lstat(p)
            except FileNotFoundError:continue
            raise ValueError('control-terminal-absence')
        for p,v in terminal_frame['claims'].items():
            try:z=os.lstat(p)
            except FileNotFoundError:
                if v is None:continue
                raise ValueError('control-terminal-claim')
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if z.st_mode&0o170000==0o040000 else z.st_nlink)!=(None if v is None else tuple(v)):raise ValueError('control-terminal-claim')
        # Final terminal helpers cannot mutate the original control/lock or logical action.
        for path,wanted in c['source_files']:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=wanted:raise ValueError('control-terminal-source')
        for path,wanted in c['source_nodes']:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=wanted:raise ValueError('control-terminal-source-node')
        for z in (os.fstat(fd),os.lstat(c['worker_lock'][1])):
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=c['worker_lock'][2]:raise ValueError('control-terminal-worker-lock')
        action=owned['action'];record=handoff._TERMINAL_EXPORTS.get(action);core=handoff._CORES.get(action)
        if action is not original_action or record is not original_terminal or core is not original_core:raise ValueError('control-terminal-action-registry')
        pending=[core];projection=[]
        while pending:
            item=pending.pop();kind=type(item)
            if kind is dict:
                keys=tuple(sorted(item));projection.append(('dict',keys));pending.extend(item[k] for k in reversed(keys))
            elif kind in (list,tuple):projection.append((kind.__name__,len(item)));pending.extend(reversed(item))
            elif kind in (str,int,float,bool,bytes,type(None)):projection.append((kind.__name__,item))
            else:projection.append(('identity',id(kind),id(item)))
        if tuple(projection)!=record[4] or core['token']!=record[5] or core['reply_bytes'] is not record[6]:raise ValueError('control-terminal-action-original')
        if _STATE.get(value) is not c or c['maintenance'] is not m or c['session'] is not owned_session or c['pipe'] is not original_pipe:raise ValueError('control-terminal-original-registry')
        if (m.state,m.worker,tuple(m.worker.roots),m.worker.config['writer_state'],m.settings.get('ddl_cache'),m.settings.get('mylar_ddl_cache'),m.worker.config['mylar'].get('url'),m.worker.config['mylar'].get('config_dir','/mylar'),tuple((row['native'],row['worker']) for row in m.worker.config['publication_roots']))!=binding:raise ValueError('control-terminal-final-Maintenance')
    return c


def initialize(maintenance,pipe,parent_sha,source_files,source_nodes,worker_lock_fd=None):
    need(ENABLED is True and type(parent_sha) is str and parent_sha==PARENT_SOURCE_SHA and len(parent_sha)==64,'parent-activation-required')
    from maintenance import Maintenance
    need(type(maintenance) is Maintenance and type(pipe) is Pipe,'original-Maintenance-channel')
    import fcntl
    need(type(worker_lock_fd) is int,'owning-worker-lock-FD-required')
    lock_path=maintenance.worker.state/'worker.lock';lock9=nine(os.lstat(lock_path));need(lock9[5]&0o170000==0o100000 and lock9[8]==1 and nine(os.fstat(worker_lock_fd))==lock9,'original-worker-lock-FD')
    fcntl.flock(worker_lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    # Freeze arguments BEFORE initialization callbacks; require actual source hashes at caller.
    originals=tuple((str(p),tuple(s)) for p,s in source_files);nodes=tuple((str(p),tuple(s)) for p,s in source_nodes)
    methods=tuple((name,getattr(Maintenance,name),getattr(Maintenance,name).__code__) for name in ('initialize_retained_pack','select_retained_pack','run_retained_pack','reconcile_retained_pack','retained_pack_view'))
    pipe.close_originals();session=maintenance.initialize_retained_pack()
    from retained_pack_operations import _core
    initial_binding=tuple(_core(session)['initial'][3])
    value=object.__new__(WaitingSession);_STATE[value]=dict(maintenance=maintenance,session=session,pipe=pipe,pid=os.getpid(),thread=threading.get_ident(),source_files=originals,source_nodes=nodes,worker_lock=(worker_lock_fd,str(lock_path),lock9),phase='waiting',deadline=time.monotonic()+WAITING_SECONDS,methods=methods,initial_binding=initial_binding)
    _close(value);return value


def wait_and_run(value,challenge,pack_id,member_id):
    c=_close(value);need(c['phase']=='waiting' and time.monotonic()<c['deadline'],'original-waiting-phase')
    from retained_pack_operations import _core
    initialized=_core(c['session'])['initial'];path,stamp,nodes,_=initialized
    # Facts only; host independently checks fixed configured path and kernel identity.
    c['pipe'].send('initialized',challenge,dict(journal=path,signature9=list(stamp),nodes5=dict(nodes),worker_pid=os.getpid()))
    total_deadline=c['pipe'].deadline;c['pipe'].deadline=min(total_deadline,c['deadline'])
    token=c['pipe'].receive('backup-ready',challenge)
    need(time.monotonic()<c['deadline'],'waiting-backup-deadline');c['pipe'].deadline=total_deadline
    need(type(token) is dict and set(token)=={'kind','backup_digest','initialized_sha256','pack_id','member_id'} and token['kind']=='verified-retained-backup-v1','backup-frame-schema')
    original_digest=hashlib.sha256(encode(dict(journal=path,signature9=list(stamp),nodes5=dict(nodes),worker_pid=os.getpid()))).hexdigest()
    need(token['initialized_sha256']==original_digest and (token['pack_id'],token['member_id'])==(pack_id,member_id) and type(token['backup_digest']) is str and len(token['backup_digest'])==64,'same-initialized-backup-join')
    _close(value);c['phase']='selected';m=c['maintenance'];m.select_retained_pack(pack_id,member_id)
    try:result=m.run_retained_pack()
    except Exception:
        # No new attempt. Only an actual still-dispatching live action can status once.
        from retained_pack_operations import _core as core
        import retained_pack_handoff as h
        action=core(c['session'])['action']
        if action is None or h.live_state(action)!='dispatching':raise
        result=m.reconcile_retained_pack()
    c['phase']='terminal';c['pipe'].close_originals();_TERMINAL_SEND[c['pipe']]=value
    result_raw=c['pipe'].send('worker-result',challenge,result)
    expected=dict(result_sha256=hashlib.sha256(result_raw).hexdigest(),pack_id=pack_id,member_id=member_id,worker_pid=os.getpid(),publication=False,ordinary_import=False,index=False,cleanup=False,replay=False,resume=False)
    release=c['pipe'].receive('observed-release',challenge)
    need(type(release) is dict and encode(release)==encode(expected),'control-original-result-release')
    _close(value,terminal=True);c['pipe'].send('observed-final-ACK',challenge,expected)
    final=c['pipe'].receive('observed-exit',challenge)
    need(type(final) is dict and encode(final)==encode(expected),'control-original-final-exit')
    _close(value,terminal=True);c['phase']='released'
    # Parent cannot grant cleanup/import/index through this factual result.
    return result


def _regular(path,expected):
    path=Path(path);stamp=nine(os.lstat(path))
    need(type(expected) is list and len(expected)==9 and all(type(v) is int for v in expected) and stamp==tuple(expected),'control-original-regular-ref')
    need(stamp[5]&0o170000==0o100000 and stamp[8]==1,'control-regular-source')
    return stamp


def _read_original(path,stamp,limit):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        need(nine(os.fstat(fd))==stamp,'control-original-read-FD');parts=[];size=0
        while chunk:=os.read(fd,1048576):
            size+=len(chunk);need(size<=limit,'control-source-bound');parts.append(chunk)
        need(nine(os.fstat(fd))==stamp and nine(os.lstat(path))==stamp,'control-read-original');return b''.join(parts)
    finally:os.close(fd)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--input-sha256',required=True);args=parser.parse_args()
    need(ENABLED is True and PARENT_SOURCE_SHA is not None,'retained-control-default-disabled')
    path=Path(args.input);original=nine(os.lstat(path));own=Path(__file__).absolute()
    original_nodes={}
    for q in (path,own):
        for parent in q.parents:
            value=five(os.lstat(parent));need(str(parent) not in original_nodes or original_nodes[str(parent)]==value,'control-original-ancestor-conflict');original_nodes[str(parent)]=value
    need(stat.S_ISREG(original[5]) and original[8]==1 and original[5]&0o7777==0o600,'control-input-private')
    raw=_read_original(path,original,FRAME_BYTES);need(hashlib.sha256(raw).hexdigest()==args.input_sha256,'control-input-pin');plan=json.loads(raw)
    need(encode(plan)==raw and set(plan)=={'version','nonce','parent_sha','config','config_sha256','config_signature9','pack_id','member_id','challenge','worker_manifest','worker_manifest_sha256','worker_manifest_signature9','worker_lock_signature9'} and type(plan['version']) is int and plan['version']==1,'control-input-schema')
    config=Path(plan['config']);manifest=Path(plan['worker_manifest']);config9=_regular(config,plan['config_signature9']);map9=_regular(manifest,plan['worker_manifest_signature9'])
    for q in (config,manifest):
        for parent in q.parents:
            value=five(os.lstat(parent));need(str(parent) not in original_nodes or original_nodes[str(parent)]==value,'control-original-ancestor-conflict');original_nodes[str(parent)]=value
    source_files={str(path):original,str(config):config9,str(manifest):map9}
    encoded_map=_read_original(manifest,map9,1024**2);need(hashlib.sha256(encoded_map).hexdigest()==plan['worker_manifest_sha256'],'control-module-map-pin');entries=json.loads(encoded_map)
    need(type(entries) is dict and 1<=len(entries)<=128,'control-module-map-bound')
    source_root=own.parent
    for name,digest in entries.items():
        need(type(name) is str and Path(name).name==name and name.endswith('.py') and all(c in 'abcdefghijklmnopqrstuvwxyz_0123456789.' for c in name),'control-canonical-module-name')
        need(type(digest) is str and len(digest)==64 and all(c in '0123456789abcdef' for c in digest),'control-module-SHA')
        module=source_root/name;stamp=nine(os.lstat(module));need(stamp[5]&0o170000==0o100000 and stamp[8]==1,'control-module-type')
        need(str(module) not in source_files or source_files[str(module)]==stamp,'control-module-original-conflict');source_files[str(module)]=stamp
        for parent in module.parents:
            value=five(os.lstat(parent));need(str(parent) not in original_nodes or original_nodes[str(parent)]==value,'control-module-node-conflict');original_nodes[str(parent)]=value
    need({'retained_pack_control.py','normalize.py','maintenance.py','retained_pack_operations.py','retained_pack_handoff.py','media_writer.py','publication_guard.py'}.issubset(entries),'control-owning-module-closure-required')
    for name,digest in entries.items():need(hashlib.sha256(_read_original(source_root/name,source_files[str(source_root/name)],8*1024**2)).hexdigest()==digest,'control-installed-module-pin')
    data=_read_original(config,config9,1024**2);need(hashlib.sha256(data).hexdigest()==plan['config_sha256'],'control-config-pin')
    sys.path.insert(0,str(source_root))
    from normalize import Normalizer
    from maintenance import Maintenance
    import fcntl
    worker=Normalizer(json.loads(data));m=Maintenance(worker)
    lock_path=worker.state/'worker.lock';lock9=_regular(lock_path,plan['worker_lock_signature9']);source_files[str(lock_path)]=lock9
    fd=os.open(lock_path,os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'r+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        pipe=Pipe(0,1,plan['nonce'],time.monotonic()+TOTAL_SECONDS)
        session=initialize(m,pipe,plan['parent_sha'],tuple(source_files.items()),tuple(original_nodes.items()),lock.fileno())
        wait_and_run(session,plan['challenge'],plan['pack_id'],plan['member_id'])


if __name__=='__main__':main()
