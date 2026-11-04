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
_RELEASE_SEND=weakref.WeakKeyDictionary()
_WRITER_HOLDS=weakref.WeakKeyDictionary()


def need(value,reason):
    if not value:raise ValueError(reason)


def encode(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def nine(z):return (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
def five(z):return (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)


def _writer_hold_original(function,owner=None):
    """Retain both contextmanager wrapper and its actual generator closure."""
    import types
    generator=getattr(function,'__wrapped__',None)
    need(type(function) is types.FunctionType and type(generator) is types.FunctionType,
         'control-original-Writer-contextmanager')
    need(owner is None or type(owner) is type and owner.hold is function,'control-original-Writer-class')
    rows=[]
    for fn in (function,generator):
        cells=tuple((cell,cell.cell_contents) for cell in (fn.__closure__ or ()))
        defaults=fn.__defaults__;keywords=fn.__kwdefaults__
        need(defaults is None or all(type(v) in (str,int,float,bool,type(None)) for v in defaults),
             'control-Writer-default-shape')
        need(keywords is None or all(type(k) is str and type(v) in (str,int,float,bool,type(None))
                                    for k,v in keywords.items()),'control-Writer-keyword-shape')
        rows.append((fn,fn.__code__,fn.__globals__,fn.__closure__,cells,defaults,
                     None if defaults is None else tuple((type(v),v) for v in defaults),
                     keywords,None if keywords is None else tuple(sorted((k,type(v),v) for k,v in keywords.items()))))
    need(any(value is generator for _,value in rows[0][4]),'control-original-Writer-generator')
    return function,generator,tuple(rows),owner


def _check_writer_hold(original,writer=None):
    function,generator,rows,owner=original
    need(getattr(function,'__wrapped__',None) is generator,'control-original-Writer-generator')
    need(owner is None or owner.hold is function,'control-original-Writer-class')
    if writer is not None:
        need((owner is None or type(writer) is owner)
             and getattr(writer.hold,'__func__',None) is function,'control-original-Writer-method')
    for fn,code,namespace,closure,cells,defaults,values,keywords,items in rows:
        # Reject subclass dispatch before sorting or comparing mutable defaults.
        need(fn.__kwdefaults__ is keywords and (keywords is None or all(type(k) is str
             and type(v) in (str,int,float,bool,type(None)) for k,v in keywords.items())),
             'control-original-Writer-keyword-types')
        need(fn.__code__ is code and fn.__globals__ is namespace and fn.__closure__ is closure
             and fn.__defaults__ is defaults and fn.__kwdefaults__ is keywords
             and all(cell.cell_contents is value for cell,value in cells)
             and (None if fn.__defaults__ is None else tuple((type(v),v) for v in fn.__defaults__))==values
             and (None if fn.__kwdefaults__ is None else tuple(sorted((k,type(v),v) for k,v in fn.__kwdefaults__.items())))==items,
             'control-original-Writer-implementation')


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


_AUTH_PIPES=weakref.WeakKeyDictionary()

class AuthenticatedPipe(Pipe):
    """Original fixed-anchor pack transcript; never a caller-enabled Pipe."""
    def __init__(self,*args,**kwargs):raise ValueError('Original pack admission required')
    @classmethod
    def from_binding(cls,binding,boot_ref,boot):
        import standalone_launch_auth as auth
        need(type(binding) is auth.ActionBinding and binding.purpose=='retained-pack','pack-original-auth-purpose')
        module=sys.modules[__name__];binding.check_action(module,boot_ref,0,1)
        original=binding.original_identity()
        value=object.__new__(cls)
        Pipe.__init__(value,0,1,boot['nonce'],time.monotonic()+TOTAL_SECONDS)
        value.sequence=1
        _AUTH_PIPES[value]=(auth,binding,original,module,encode(boot_ref),encode(boot),
                            binding.parent_sha256,binding.source_map_sha256,_AUTH_PIPES)
        value.close_originals();return value
    def close_originals(self):
        Pipe.close_originals(self)
        original=_AUTH_PIPES.get(self);need(original is not None,'pack-auth-original-pipe')
        auth,binding,identity,module,boot_ref,boot,parent_sha,map_sha,table=original
        need(_AUTH_PIPES is table,'pack-auth-original-table')
        need(type(binding) is auth.ActionBinding,'pack-auth-original-binding')
        binding.check_action(module,json.loads(boot_ref),self.read_fd,self.write_fd)
        need(binding.original_identity() is identity and binding.purpose=='retained-pack'
             and binding.parent_sha256==parent_sha and binding.source_map_sha256==map_sha,
             'pack-auth-original-admission')
        need(_AUTH_PIPES.get(self) is original,'pack-auth-original-registry')
    def send(self,kind,challenge,payload):
        self.close_originals();original=_AUTH_PIPES[self];binding=original[1]
        terminal_table=_TERMINAL_SEND;release_table=_RELEASE_SEND
        terminal=terminal_table.get(self);released=release_table.get(self)
        need((kind=='observed') is (terminal is not None)
             and (kind=='observed-final-ACK') is (released is not None),
             'pack-auth-original-send-guard')
        need(kind=={1:'initialized',3:'observed',5:'observed-final-ACK'}.get(self.sequence),
             'pack-auth-child-order')
        raw=encode(dict(version=3,protocol='pack-retained-repeat-v1',kind=kind,nonce=self.nonce,
                        sequence=self.sequence,challenge=challenge,payload=payload))
        need(len(raw)<FRAME_BYTES,'pack-auth-frame-bound');binding.child_frame(raw)
        self.close_originals()
        # The delimiter commits the frame. Reclose the genuine consumed action
        # immediately before every partial write and separately before newline.
        for part in (raw,b'\n'):
            view=memoryview(part)
            while view:
                need(select.select([], [self.write_fd],[],max(0,self.deadline-time.monotonic()))[1],
                     'pack-auth-write-deadline')
                self.close_originals()
                need(_TERMINAL_SEND is terminal_table and _RELEASE_SEND is release_table
                     and terminal_table.get(self) is terminal and release_table.get(self) is released,
                     'pack-auth-original-terminal-send')
                if terminal is not None:_close(terminal,terminal=True)
                if released is not None:_close(released,released=True)
                count=os.write(self.write_fd,view);need(count>0,'pack-auth-short-write')
                view=view[count:]
        self.sequence+=1;return raw
    def receive(self,kind,challenge):
        self.close_originals();original=_AUTH_PIPES[self];binding=original[1]
        need(kind=={2:'backup-ready',4:'observed-release',6:'observed-exit'}.get(self.sequence),
             'pack-auth-host-order')
        data=bytearray()
        while True:
            need(select.select([self.read_fd],[],[],max(0,self.deadline-time.monotonic()))[0],
                 'pack-auth-read-deadline')
            part=os.read(self.read_fd,1);need(part,'pack-auth-unknown-host-reply');data.extend(part)
            need(len(data)<=FRAME_BYTES,'pack-auth-envelope-bound')
            if part==b'\n':break
        raw=binding.host_frame(bytes(data[:-1]));body=json.loads(raw)
        need(body['kind']==kind and body['sequence']==self.sequence and body['nonce']==self.nonce
             and body['challenge']==challenge,'pack-auth-original-host-frame')
        self.close_originals();self.last_received=raw;self.sequence+=1;return body['payload']


def _owning_parent_pipe(pipe,parent_sha):
    if type(pipe) is Pipe:
        return ENABLED is True and type(parent_sha) is str and parent_sha==PARENT_SOURCE_SHA
    if type(pipe) is AuthenticatedPipe:
        pipe.close_originals();record=_AUTH_PIPES.get(pipe)
        return record is not None and type(parent_sha) is str and parent_sha==record[6]
    return False


class WaitingSession:
    __slots__=('__weakref__',)
    def __init__(self,*a,**k):raise ValueError('Original same-live worker required')


def _close(value,*,terminal=False,released=False):
    if type(value) is not WaitingSession:raise ValueError('original-waiting-session')
    c=_STATE.get(value);need(c is not None and (c['pid'],c['thread'])==(os.getpid(),threading.get_ident()),'original-waiting-session')
    hold_original=_WRITER_HOLDS.get(value)
    need(hold_original is not None and hold_original[0] is c
         and hold_original[1] is c['writer_hold'] and hold_original[2] is _STATE
         and hold_original[3] is _WRITER_HOLDS,'control-original-Writer-registry')
    owned_session=c['session'];original_pipe=c['pipe']
    c['pipe'].close_originals()
    from retained_pack_operations import existing
    need(existing(c['maintenance']) is c['session'],'same-original-session')
    # Actual Operations carries its immutable initialized originals through execute.
    # Verify them before allowing a parent message to advance selection.
    from retained_pack_operations import _initial_originals,_core
    owned=_core(c['session'])
    _check_writer_hold(hold_original[1],owned.get('writer'))
    if terminal:
        import retained_pack_handoff as handoff
        from publication_guard import scope
        need(owned['phase']=='retained-observed' and handoff.terminal_core(owned['action'])['maintenance'] is c['maintenance'],'control-original-consumed-action')
        original_action=owned['action'];original_terminal=handoff._TERMINAL_EXPORTS.get(original_action);original_core=handoff._CORES.get(original_action)
        need(original_terminal is not None and original_terminal[0] is original_core,'control-original-terminal-seal')
        from publication_guard import current,Unavailable
        try:active=current(c['maintenance'].worker)
        except Unavailable:
            with hold_original[1][0](owned['writer'],timeout=0),scope(c['maintenance'].worker,owned['writer']):
                terminal_frame=handoff.close_terminal(owned['action'])
        else:
            need(active.writer is owned['writer'],'control-original-held-Writer')
            terminal_frame=handoff.close_terminal(owned['action'])
    elif released:
        need(owned['phase']=='retained-observed' and getattr(owned['writer'].local[1],'depth',0)==0,
             'control-original-Writer-release')
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
    _check_writer_hold(c['writer_hold'],owned.get('writer'))
    need(_WRITER_HOLDS.get(value) is hold_original and hold_original[1] is c['writer_hold']
         and hold_original[2] is _STATE and hold_original[3] is _WRITER_HOLDS,
         'control-final-Writer-registry')
    if released:need(getattr(owned['writer'].local[1],'depth',0)==0,'control-final-Writer-release')
    return c


def initialize(maintenance,pipe,parent_sha,source_files,source_nodes,worker_lock_fd=None):
    need(_owning_parent_pipe(pipe,parent_sha) and len(parent_sha)==64,'parent-activation-required')
    from maintenance import Maintenance
    need(type(maintenance) is Maintenance and type(pipe) in (Pipe,AuthenticatedPipe),'original-Maintenance-channel')
    import fcntl
    need(type(worker_lock_fd) is int,'owning-worker-lock-FD-required')
    lock_path=maintenance.worker.state/'worker.lock';lock9=nine(os.lstat(lock_path));need(lock9[5]&0o170000==0o100000 and lock9[8]==1 and nine(os.fstat(worker_lock_fd))==lock9,'original-worker-lock-FD')
    fcntl.flock(worker_lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    # Freeze arguments BEFORE initialization callbacks; require actual source hashes at caller.
    originals=tuple((str(p),tuple(s)) for p,s in source_files);nodes=tuple((str(p),tuple(s)) for p,s in source_nodes)
    methods=tuple((name,getattr(Maintenance,name),getattr(Maintenance,name).__code__) for name in ('initialize_retained_pack','select_retained_pack','run_retained_pack','reconcile_retained_pack','retained_pack_view'))
    from media_writer import Writer
    writer_hold=_writer_hold_original(Writer.hold,Writer)
    writer_table=_WRITER_HOLDS;state_table=_STATE
    pipe.close_originals();session=maintenance.initialize_retained_pack()
    from retained_pack_operations import _core
    initial_binding=tuple(_core(session)['initial'][3])
    value=object.__new__(WaitingSession);_STATE[value]=dict(maintenance=maintenance,session=session,pipe=pipe,pid=os.getpid(),thread=threading.get_ident(),source_files=originals,source_nodes=nodes,worker_lock=(worker_lock_fd,str(lock_path),lock9),phase='waiting',deadline=time.monotonic()+WAITING_SECONDS,methods=methods,initial_binding=initial_binding,writer_hold=writer_hold)
    need(_WRITER_HOLDS is writer_table and _STATE is state_table,'control-initial-Writer-registry')
    _WRITER_HOLDS[value]=(_STATE[value],writer_hold,state_table,writer_table)
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
    if type(c['pipe']) is AuthenticatedPipe:return _authenticated_complete(value,result,challenge,pack_id,member_id)
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


def _authenticated_complete(value,result,challenge,pack_id,member_id):
    """One six-stage original transcript, with a continuous Writer observation."""
    if type(value) is not WaitingSession:raise ValueError('pack-original-authenticated-session')
    c=_STATE.get(value);need(c is not None and type(c['pipe']) is AuthenticatedPipe,'pack-original-authenticated-session')
    from retained_pack_operations import _core
    import retained_pack_handoff as handoff
    from publication_guard import scope
    owned=_core(c['session']);need(owned['phase']=='retained-observed','pack-original-consumed-result')
    writer=owned['writer'];hold=c['writer_hold'];_check_writer_hold(hold,writer)
    result_bytes=encode(result);c['phase']='terminal'
    _check_writer_hold(hold,writer)
    with hold[0](writer,timeout=0),scope(c['maintenance'].worker,writer):
        _close(value,terminal=True)
        frame=handoff.close_terminal(owned['action']);action=handoff.terminal_core(owned['action'])
        done=str(action['done']);reference=dict(path=done,signature9=list(frame['files'][done]),sha256=frame['hashes'][done])
        header=dict(version=1,kind='retained-pack-terminal-observation',pack_id=pack_id,member_id=member_id,
            token=action['token'],worker_pid=os.getpid(),result=json.loads(result_bytes),artifact_ref=reference,
            frame_sha256=hashlib.sha256(handoff.compact(frame)).hexdigest(),
            request_sha256=hashlib.sha256(action['request_bytes']).hexdigest(),
            reply_sha256=hashlib.sha256(action['reply_bytes']).hexdigest(),
            writer_lock=dict(path=str(writer.lock),signature9=list(frame['files'][str(writer.lock)])),
            ordinary_import_grant=False,cleanup_grant=False,reader_index_acceptance=False,
            historical_import_ack=False,reader_resume_grant=False,automatic_replay=False)
        _TERMINAL_SEND[c['pipe']]=value
        try:
            raw=c['pipe'].send('observed',challenge,header)
            release=c['pipe'].receive('observed-release',challenge)
            expected=dict(observed_sha256=hashlib.sha256(raw).hexdigest(),frame_sha256=header['frame_sha256'],
                          artifact_sha256=reference['sha256'],token=action['token'])
            need(type(release) is dict and encode(release)==encode(expected),'pack-original-observation-ACK')
            _close(value,terminal=True)
        finally:
            _TERMINAL_SEND.pop(c['pipe'],None)
    # The exact source-owned hold has returned after kernel unlock. No reacquire,
    # HTTP or refreshed data baseline can stand in for this original release.
    _check_writer_hold(hold,writer)
    need(getattr(writer.local[1],'depth',0)==0,'pack-original-Writer-release-ACK')
    _close(value,released=True)
    released=dict(expected,writer_released=True)
    _RELEASE_SEND[c['pipe']]=value
    try:c['pipe'].send('observed-final-ACK',challenge,released)
    finally:_RELEASE_SEND.pop(c['pipe'],None)
    final=c['pipe'].receive('observed-exit',challenge)
    need(type(final) is dict and encode(final)==encode(released),'pack-original-exit-ACK')
    _close(value,released=True);c['phase']='released'
    return result


def authenticated_main(original_preimport,admission):
    """Only the fixed source/installation loader supplies a live pack admission."""
    import standalone_launch_auth as auth
    need(type(admission) is auth.LaunchAdmission,'pack-original-launch-admission')
    need(type(original_preimport) is dict and set(original_preimport)=={'files','nodes','hashes','input_bytes'},
         'pack-original-preimport')
    need(len(sys.argv)==5 and sys.argv[1]=='--input' and sys.argv[3]=='--input-sha256','pack-original-bootstrap-argv')
    path=Path(sys.argv[2]);data=bytes(original_preimport['input_bytes']);boot=json.loads(data)
    need(encode(boot)==data and hashlib.sha256(data).hexdigest()==sys.argv[4]
         and boot.get('kind')=='pack-retained-bootstrap-v1','pack-original-bootstrap-input')
    boot_ref=dict(path=str(path),signature9=list(original_preimport['files'][str(path)]),sha256=sys.argv[4])
    binding=admission.claim_action(sys.modules[__name__],boot_ref,0,1)
    pipe=AuthenticatedPipe.from_binding(binding,boot_ref,boot)
    reference=boot['config_ref'];config_bytes=_read_original(reference['path'],tuple(reference['signature9']),1024**2)
    need(hashlib.sha256(config_bytes).hexdigest()==reference['sha256'],'pack-original-configuration')
    from normalize import Normalizer
    from maintenance import Maintenance
    import retained_pack_handoff as handoff
    import fcntl
    worker=Normalizer(json.loads(config_bytes));maintenance=Maintenance(worker)
    lock_path=worker.state/'worker.lock';stamp=nine(os.lstat(lock_path))
    need(stamp[5]&0o170000==0o100000 and stamp[8]==1 and stamp[6:8]==(1000,1000),'pack-original-worker-lock')
    fd=os.open(lock_path,os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'r+b') as lock:
        need(nine(os.fstat(lock.fileno()))==stamp,'pack-original-worker-lock-FD')
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        handoff.authenticate_control(maintenance,pipe,boot)
        files=tuple((name,tuple(value)) for name,value in original_preimport['files'].items())+((str(lock_path),stamp),)
        nodes=tuple((name,tuple(value)) for name,value in original_preimport['nodes'].items())
        session=initialize(maintenance,pipe,binding.parent_sha256,files,nodes,lock.fileno())
        wait_and_run(session,boot['challenge'],boot['request']['pack_id'],boot['request']['member_id'])
    return 0


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


def main(*,original_preimport=None,admission=None):
    if admission is not None:return authenticated_main(original_preimport,admission)
    need(original_preimport is None,'pack-unadmitted-preimport')
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
