"""Explicit primary-key retained API admission; no Reader or import grants."""

COMMANDS=('retainedDeliveryFinalize','retainedDeliveryStatus','retainedDeliverySession')
_LIMIT=4*1024*1024

API_METHODS='''    # homelab-retained-delivery-api-v1
    def _retainedDeliveryFinalize(self, **kwargs):
        from mylar import publication_retained_api, publication_retained_delivery, publication_guard, publication_native
        try:
            self.data = publication_retained_api.execute(self, kwargs.get('request'))
        except (ValueError, OSError, RuntimeError, TypeError, KeyError, publication_retained_delivery.o.Held, publication_guard.Unavailable, publication_native.Review):
            self.data = self._failureResponse('Retained finalization held; preserve source and review same-process status')

    def _retainedDeliveryStatus(self, **kwargs):
        from mylar import publication_retained_api, publication_retained_delivery, publication_guard, publication_native
        try:
            self.data = publication_retained_api.execute(self, kwargs.get('request'))
        except (ValueError, OSError, RuntimeError, TypeError, KeyError, publication_retained_delivery.o.Held, publication_guard.Unavailable, publication_native.Review):
            self.data = self._failureResponse('Retained status held; original same-process witness required')


    def _retainedDeliverySession(self, **kwargs):
        from mylar import publication_retained_api, publication_guard
        try:
            self.data = publication_retained_api.session_execute(self, kwargs.get('request'))
        except (ValueError, OSError, RuntimeError, TypeError, KeyError, publication_guard.Unavailable):
            self.data = self._failureResponse('Retained session held; preserve the original operation and review')

'''

# Compare actual installed handler code to the exact owning hook template.
# This compiles grammar only; it creates no Api or SDK type/capability.
_class_code=next(c for c in compile('class Api:\n'+API_METHODS,'<retained-owning-hooks>','exec').co_consts if hasattr(c,'co_name') and c.co_name=='Api')
_HOOK_CODES={c.co_name:c for c in _class_code.co_consts if hasattr(c,'co_name')}


def _code_facts(code):
    return (code.co_code,code.co_consts,code.co_names,code.co_varnames,code.co_flags,getattr(code,'co_exceptiontable',None))


def owns(handler):
    from mylar import api
    command=getattr(handler,'cmd',None)
    if type(handler) is not api.Api or command not in COMMANDS:return False
    method=getattr(handler,'_'+command,None)
    expected=getattr(api.Api,'_'+command,None)
    return (expected is not None and getattr(method,'__func__',None) is expected
            and expected.__module__=='mylar.api' and expected.__qualname__=='Api._'+command
            and _code_facts(expected.__code__)==_code_facts(_HOOK_CODES['_'+command]))


def _http_original(handler,raw):
    import mylar
    import cherrypy
    if not owns(handler):raise ValueError('Exact owning API handler required')
    command=handler.cmd;method=getattr(handler,'_'+command).__func__;method_code=method.__code__
    caller=(handler,type(handler),command,method,method_code,raw,handler.kwargs,
            (handler.apitype,handler.img,handler.file,handler.comicrn))
    key=mylar.CONFIG.API_KEY
    if (mylar.CONFIG.API_ENABLED is not True or type(key) is not str or len(key)!=32
            or handler.apikey!=key or getattr(handler,'apitype',None)!='normal'):
        raise ValueError('Primary normal API key required')
    if (getattr(handler,'img',None) or getattr(handler,'file',None) or getattr(handler,'comicrn',False)
            or set(handler.kwargs)!={'request'}):raise ValueError('Exact finite API response required')
    if cherrypy.request.method!='POST':raise ValueError('Exact retained POST required')
    if type(raw) is not str or not 0<len(raw.encode())<4096:raise ValueError('Finite retained request required')
    config=(mylar.DATA_DIR,mylar.CONFIG.DESTINATION_DIR,mylar.CONFIG.DDL_LOCATION,mylar.CONFIG.API_ENABLED,key)
    return caller,config


def _http_close(caller,config):
    import mylar
    handler,kind,command,method,code,raw,kwargs,formatting=caller
    if (not owns(handler) or type(handler) is not kind or handler.cmd!=command
            or getattr(handler,'_'+command).__func__ is not method or method.__code__ is not code
            or handler.kwargs is not kwargs or handler.kwargs!={'request':raw}
            or tuple(type(v) for v in (handler.apitype,handler.img,handler.file,handler.comicrn))!=tuple(type(v) for v in formatting)
            or (handler.apitype,handler.img,handler.file,handler.comicrn)!=formatting
            or handler.apikey!=config[4] or mylar.CONFIG.API_ENABLED is not True
            or (mylar.DATA_DIR,mylar.CONFIG.DESTINATION_DIR,mylar.CONFIG.DDL_LOCATION,
                mylar.CONFIG.API_ENABLED,mylar.CONFIG.API_KEY)!=config):
        raise ValueError('Original retained HTTP caller changed')


def execute(handler,raw):
    import mylar
    from mylar import native_writers,publication_guard as guard,publication_retained_delivery as retained,publication_retained_finalize as finalizer
    from mylar.publication_api import Controller
    admission_clock=time.monotonic
    original_caller,original_config=_http_original(handler,raw)
    command=original_caller[2];method=original_caller[3];method_code=original_caller[4]
    value=retained.request(guard.decode_json(raw));request_bytes=retained.o.compact(value)
    frame=finalizer.response_sources()
    source_table=finalizer._SOURCE_FRAMES;source=source_table.get(frame)
    if source is None:raise ValueError('Original API source frame required')
    source_vector=json.loads(source[3])
    source_files=tuple((path,tuple(stamp)) for path,stamp in source_vector['files9'])
    source_nodes=tuple((path,tuple(stamp)) for path,stamp in source_vector['nodes5'])
    source_hashes=tuple(source[4].items())
    if not native_writers.publication_mode():raise ValueError('Current publication mode required')
    writer=native_writers.owner()
    admission=None
    try:
        # The original strict outer hold outlives inner exit-admission callbacks.
        with writer.hold(timeout=0):
            with native_writers.operation(ordinary=True,retained_session=session_for_request(value)) as original_writer:
                controller=Controller(mylar.DATA_DIR,[mylar.CONFIG.DESTINATION_DIR])
                if (finalizer._SOURCE_FRAMES is not source_table or source_table.get(frame) is not source
                        or source[:2]!=(os.getpid(),threading.get_ident())
                        or tuple(source[4].items())!=source_hashes):raise ValueError('Original API source frame changed before admission')
                actual=getattr(handler,'_'+command)
                if (handler.cmd!=command or getattr(actual,'__func__',None) is not method
                        or method.__code__ is not method_code or retained.o.compact(value)!=request_bytes
                        or type(handler) is not original_caller[1] or handler.kwargs is not original_caller[6]
                        or handler.kwargs!={'request':raw} or time.monotonic is not admission_clock):raise ValueError('Original API caller changed before admission')
                admission=object.__new__(NativeRetainedAdmission);state={'phase':'admitted'}
                seal=(state,(os.getpid(),threading.get_ident()),source[2],handler,method,method_code,
                    command,request_bytes,frame,source,
                    source_files,source_nodes,source_hashes,
                    original_config,controller,original_writer,retained._controller_binding(controller),
                    retained._writer_binding(original_writer),(_ADMISSIONS,_ADMISSION_SEALS,source_table,_ADMISSION_PHASES),original_caller,admission_clock)
                state['seal']=seal;_ADMISSIONS[admission]=state;_ADMISSION_SEALS[admission]=seal
                _ADMISSION_PHASES[admission]=state['phase']
                check_admission(admission,controller,original_writer,value)
                if command=='retainedDeliveryFinalize':
                    cap=retained.prepare_existing(controller,original_writer,value,admission=admission)
                    advance_admission(admission,controller,original_writer,value,'prepared')
                    cap.accept();advance_admission(admission,controller,original_writer,value,'accepted')
                    receipt=finalizer.finalize(cap,response_handler=handler,response_frame=frame)
                    advance_admission(admission,controller,original_writer,value,'finalized')
                else:receipt=finalizer.response_existing(controller,original_writer,value,admission=admission)
                advance_admission(admission,controller,original_writer,value,'encoding')
                envelope=receipt.encode(handler,frame)
                advance_admission(admission,controller,original_writer,value,'encoded')
            if original_config!=(mylar.DATA_DIR,mylar.CONFIG.DESTINATION_DIR,mylar.CONFIG.DDL_LOCATION,mylar.CONFIG.API_ENABLED,mylar.CONFIG.API_KEY):
                raise ValueError('Original API configuration changed')
            receipt.close(envelope)
            advance_admission(admission,controller,original_writer,value,'closed')
        # No new admission or proof refresh after release. Only the same originals.
        result=receipt.finish(envelope)
        state['phase']='finished';_ADMISSION_PHASES[admission]='finished'
        return result
    finally:
        if admission is not None:
            current=_ADMISSIONS.get(admission)
            if current is not None and current['phase']!='finished':
                current['phase']='uncertain';_ADMISSION_PHASES[admission]='uncertain'


# Closed native admission: an explicit owning handler, never an enable boolean.
import hashlib
import json
import os
import threading
import time
import weakref

_ADMISSIONS=weakref.WeakKeyDictionary()
_ADMISSION_SEALS=weakref.WeakKeyDictionary()
_ADMISSION_PHASES=weakref.WeakKeyDictionary()

class NativeRetainedAdmission:
    __slots__=('__weakref__',)
    def __init__(self,*a,**k):raise ValueError('Owning retained API admission required')


def check_admission(admission,controller,writer,value,*,held=True,mutating=False):
    from mylar import publication_retained_finalize as f,publication_retained_delivery as r
    import mylar
    if type(admission) is not NativeRetainedAdmission:raise ValueError('Original retained API admission required')
    c=_ADMISSIONS.get(admission);seal=_ADMISSION_SEALS.get(admission)
    if type(admission) is not NativeRetainedAdmission or c is None or seal is None or seal[0] is not c:
        raise ValueError('Original retained API admission required')
    owner,deadline,handler,method,code,command,request_bytes,source_frame,source,source_files,source_nodes,source_hashes,config,controller_original,writer_original,cb,wb,tables,caller,clock=seal[1:]
    phase=_ADMISSION_PHASES.get(admission)
    if phase is None or c['phase'] is not phase:raise ValueError('Retained API admission original phase')
    if (os.getpid(),threading.get_ident())!=owner or time.monotonic()>=deadline or c['phase'] in ('finished','uncertain'):
        raise ValueError('Retained API admission lifetime')
    if mutating and command!='retainedDeliveryFinalize':raise ValueError('Read-only retained admission')
    if controller is not controller_original or writer is not writer_original or r._controller_binding(controller)!=cb or r._writer_binding(writer)!=wb:
        raise ValueError('Retained API admission original bindings')
    if r.o.compact(value)!=request_bytes:raise ValueError('Retained API admission original request')
    if ((getattr(writer.local[1],'depth',0)<=0 if held else getattr(writer.local[1],'depth',0)!=0)
            or any(getattr(writer.local[1],k,False) for k in ('allow_pending','allow_tagger_pending','allow_release_pending'))):
        raise ValueError('Retained API admission ordinary Writer')
    if phase not in ('encoding','encoded','closed') and f._SOURCE_FRAMES.get(source_frame) is not source:
        raise ValueError('Retained API admission original source frame')
    if (type(source[4]) is not dict or any(type(k) is not str or type(v) is not str for k,v in source[4].items())
            or tuple(source[4].items())!=source_hashes):raise ValueError('Retained API admission original source hashes')
    files=dict(source_files)
    for path,digest in source_hashes:
        if hashlib.sha256(r.o.read_checked(path,list(files[path]),1048576,deadline)).hexdigest()!=digest:
            raise ValueError('Retained API admission source bytes')
    # No schema/serialization/read helper follows this complete original closure.
    for path,stamp in source_nodes:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=stamp:raise ValueError('Retained API admission source node')
    for path,stamp in source_files:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:
            raise ValueError('Retained API admission source file')
    actual=getattr(handler,'_'+command)
    if (type(handler) is not caller[1] or handler.kwargs is not caller[6]
            or handler.kwargs!={'request':caller[5]}
            or tuple(type(v) for v in (handler.apitype,handler.img,handler.file,handler.comicrn))!=tuple(type(v) for v in caller[7])
            or (handler.apitype,handler.img,handler.file,handler.comicrn)!=caller[7]
            or getattr(actual,'__func__',None) is not method or method.__code__ is not code
            or handler.cmd!=command or handler.apikey!=config[4] or handler.apitype!='normal'
            or (mylar.DATA_DIR,mylar.CONFIG.DESTINATION_DIR,mylar.CONFIG.DDL_LOCATION,
                mylar.CONFIG.API_ENABLED,mylar.CONFIG.API_KEY)!=config
            or (controller.root,controller.database,controller.native_database,controller.writer_root,
                tuple(controller.roots),controller.tool_root)!=cb
            or (writer.root,writer.lock,writer.pending,writer.tagger_pending,writer.release_pending,
                tuple(writer.lock_identity),tuple(writer.root_identity),writer.local)!=wb):
        raise ValueError('Retained API admission final bindings')
    if ((getattr(writer.local[1],'depth',0)<=0 if held else getattr(writer.local[1],'depth',0)!=0)
            or any(getattr(writer.local[1],k,False) for k in ('allow_pending','allow_tagger_pending','allow_release_pending'))):
        raise ValueError('Retained API admission final purpose')
    if (_ADMISSIONS is not tables[0] or _ADMISSION_SEALS is not tables[1]
            or f._SOURCE_FRAMES is not tables[2] or _ADMISSIONS.get(admission) is not c
            or _ADMISSION_SEALS.get(admission) is not seal or c['seal'] is not seal or _ADMISSION_PHASES is not tables[3]
            or _ADMISSION_PHASES.get(admission) is not phase or c['phase'] is not phase):
        raise ValueError('Retained API admission original registry')
    if time.monotonic is not clock or clock()>=deadline:raise ValueError('Retained API admission final deadline')
    return c


def consume_admission(admission,controller,writer,value,stage):
    c=check_admission(admission,controller,writer,value,mutating=True)
    wanted={'prepare':('admitted','preparing'),'finalize':('accepted','finalizing')}
    if type(stage) is not str or stage not in wanted or c['phase']!=wanted[stage][0]:
        raise ValueError('Retained API admission phase or replay')
    c['phase']=wanted[stage][1];_ADMISSION_PHASES[admission]=c['phase']


def advance_admission(admission,controller,writer,value,phase):
    c=check_admission(admission,controller,writer,value)
    order={'preparing':'prepared','prepared':'accepted','finalizing':'finalized',
           'finalized':'encoding','admitted':'encoding','encoding':'encoded','encoded':'closed'}
    if type(phase) is not str or order.get(c['phase'])!=phase:
        raise ValueError('Retained API admission transition')
    c['phase']=phase;_ADMISSION_PHASES[admission]=phase


def admission_request(admission):
    seal=_ADMISSION_SEALS.get(admission)
    if type(admission) is not NativeRetainedAdmission or seal is None or _ADMISSIONS.get(admission) is not seal[0]:
        raise ValueError('Original retained admission request required')
    return json.loads(seal[7])


# A source-owned reservation excludes background native operations while the
# owning Root controller verifies backup, terminal SQL and Reader resumption.
# A saved marker is a fence, never a reconstructed live reservation.
from collections import namedtuple
from pathlib import Path
import re

_SESSION_SECONDS=3600
if __package__:
    from .media_writer import NATIVE_SESSION_PENDING as _SESSION_PENDING
else:
    from media_writer import NATIVE_SESSION_PENDING as _SESSION_PENDING
if __package__:
    from .media_writer import NATIVE_SESSION_CLOSED as _SESSION_CLOSED
else:
    from media_writer import NATIVE_SESSION_CLOSED as _SESSION_CLOSED
_SESSION_HISTORY='retained-native-session-history-v1'
_NativeSession=namedtuple('_NativeSession','root root5 nonce request_bytes config pid deadline marker_bytes marker9 files nodes hashes history history5 history_parent5')
_ROOT_SESSION=None


def _session_nine(value):
    return (value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns,value.st_ctime_ns,
            value.st_mode,value.st_uid,value.st_gid,value.st_nlink)


def _session_five(value):
    return (value.st_dev,value.st_ino,value.st_mode,value.st_uid,value.st_gid)


def _session_read(path,stamp):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        if _session_nine(os.fstat(fd))!=stamp or not 0<stamp[2]<=4096:
            raise ValueError('Original native reservation file required')
        data=os.read(fd,4097)
        if (len(data)!=stamp[2] or _session_nine(os.fstat(fd))!=stamp
                or _session_nine(os.lstat(path))!=stamp):
            raise ValueError('Native reservation file changed')
        return data
    finally:os.close(fd)


def _session_save(root,name,data,root5=None):
    original=_session_five(os.lstat(root)) if root5 is None else root5
    d=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        if _session_five(os.fstat(d))!=original:raise ValueError('Original native reservation directory changed')
        fd=os.open(name,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=d)
        try:
            born=_session_nine(os.fstat(fd))
            if born[5]&0o177777!=0o100600 or born[6:]!=(os.geteuid(),os.getegid(),1):
                raise ValueError('Private native reservation birth required')
            view=memoryview(data)
            while view:
                count=os.write(fd,view)
                if count<=0:raise ValueError('Native reservation short write')
                view=view[count:]
            os.fsync(fd);os.lseek(fd,0,os.SEEK_SET);stamp=_session_nine(os.fstat(fd))
            if (stamp[:2]+stamp[5:]!=born[:2]+born[5:] or stamp[2]!=len(data)
                    or os.read(fd,len(data)+1)!=data or _session_nine(os.stat(name,dir_fd=d,follow_symlinks=False))!=stamp):
                raise ValueError('Native reservation created file changed')
        finally:os.close(fd)
        os.fsync(d)
        if (_session_five(os.fstat(d))!=original or _session_five(os.lstat(root))!=original
                or _session_nine(os.stat(name,dir_fd=d,follow_symlinks=False))!=stamp):
            raise ValueError('Native reservation final directory changed')
        return stamp
    finally:os.close(d)


def session_pending():
    """Negative authority only: live custody never becomes a readiness grant."""
    return _ROOT_SESSION is not None


def _session_history(root,nonce):
    parent=root/_SESSION_HISTORY
    try:os.mkdir(parent,0o700)
    except FileExistsError:pass
    parent5=_session_five(os.lstat(parent))
    if parent5[2]&0o177777!=0o40700 or parent5[3:]!=(os.geteuid(),os.getegid()):
        raise ValueError('Private native session history required')
    d=os.open(parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        if _session_five(os.fstat(d))!=parent5 or len(os.listdir(d))>=4096:
            raise ValueError('Original bounded native session history required')
        os.mkdir(nonce,0o700,dir_fd=d)
        birth=_session_five(os.stat(nonce,dir_fd=d,follow_symlinks=False))
        os.fsync(d)
        if _session_five(os.stat(nonce,dir_fd=d,follow_symlinks=False))!=birth:
            raise ValueError('Original native session history creation changed')
    finally:os.close(d)
    return parent/nonce,birth,parent5


def _session_retire(record,closed9,sql_original):
    """Archive verified independent copies; unlink pending is the commit point.

    Before that point the original pending marker fences restart. After it,
    caught failures restore a negative fence; saved history never grants access.
    """
    d=os.open(record.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        h=os.open(record.history,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            def originals():
                if (_ROOT_SESSION is not record or _session_five(os.fstat(d))!=record.root5
                        or _session_five(os.lstat(record.root))!=record.root5
                        or _session_five(os.fstat(h))!=record.history5
                        or _session_five(os.lstat(record.history))!=record.history5
                        or _session_five(os.lstat(record.history.parent))!=record.history_parent5):
                    raise ValueError('Original native retirement directories changed')
                for path,stamp in (*record.files,*sql_original[0]):
                    if _session_nine(os.lstat(path))!=stamp:raise ValueError('Original native retirement source changed')
                for path,stamp in (*record.nodes,*sql_original[1]):
                    if _session_five(os.lstat(path))!=stamp:raise ValueError('Original native retirement ancestor changed')
                for path in sql_original[2]:
                    if os.path.lexists(path):raise ValueError('Native retirement SQL sidecar appeared')
            originals()
            if os.listdir(h):raise ValueError('Original empty retirement destination required')
            archived=[]
            for name,stamp,target in ((_SESSION_PENDING,record.marker9,'pending.json'),(_SESSION_CLOSED,closed9,'closed.json')):
                data=_session_read(record.root/name,stamp)
                copied=_session_save(record.history,target,data,record.history5)
                archived.append((target,copied,data))
            def copies():
                if sorted(os.listdir(h))!=['closed.json','pending.json']:
                    raise ValueError('Native retirement namespace changed')
                for name,stamp,data in archived:
                    if _session_read(record.history/name,stamp)!=data:
                        raise ValueError('Original native retirement copy changed')
            copies();originals()
            if _session_nine(os.stat(_SESSION_CLOSED,dir_fd=d,follow_symlinks=False))!=closed9:
                raise ValueError('Original native completion record changed')
            os.unlink(_SESSION_CLOSED,dir_fd=d);os.fsync(d)
            copies();originals()
            if _session_read(record.root/_SESSION_PENDING,record.marker9)!=record.marker_bytes:
                raise ValueError('Original native pending record changed')
            # All business state and both durable copies precede the commit.
            os.unlink(_SESSION_PENDING,dir_fd=d);os.fsync(d)
            copies();originals()
        finally:os.close(h)
    finally:os.close(d)


def _session_refence(record,closed):
    """A caught post-commit failure retains negative restart evidence."""
    if not any(os.path.lexists(record.root/name) for name in (_SESSION_PENDING,_SESSION_CLOSED)):
        _session_save(record.root,_SESSION_CLOSED,closed,record.root5)


def session_fenced(root):
    try:return _session_fenced(root)
    except (OSError,ValueError,TypeError,AttributeError):return True


def _session_fenced(root):
    """Active or incomplete markers fence; retired history grants no custody."""
    return _ROOT_SESSION is not None or any(os.path.lexists(Path(root)/name) for name in (_SESSION_PENDING,_SESSION_CLOSED))


def session_mode(record):
    """Called under native _MODE_LOCK before counting a new operation."""
    from .media_writer import Busy
    current=_ROOT_SESSION
    if current is None:
        if record is not None:raise ValueError('No live native reservation')
        return
    if (type(current) is not _NativeSession or record is not current
            or current.pid!=os.getpid() or time.monotonic()>=current.deadline):
        raise Busy('Native operations reserved for the owning retained request')


def session_file(writer,record):
    """Persistent presence also fences startup after loss of live custody."""
    import mylar
    from .media_writer import Busy
    session_mode(record)
    if record is None:
        if session_fenced(writer.root):
            raise Busy('Retained native reservation requires original-process review')
        return
    if (writer.root!=record.root or _session_five(os.lstat(record.root))!=record.root5
            or record.config!=(mylar.DATA_DIR,mylar.CONFIG.DESTINATION_DIR,mylar.CONFIG.DDL_LOCATION,
                              mylar.CONFIG.API_ENABLED,mylar.CONFIG.API_KEY)
            or _session_read(record.root/_SESSION_PENDING,record.marker9)!=record.marker_bytes
            or _session_five(os.lstat(record.history))!=record.history5
            or _session_five(os.lstat(record.history.parent))!=record.history_parent5 or os.listdir(record.history)):
        raise ValueError('Original native reservation changed')
    for path,digest in record.hashes:
        if hashlib.sha256(_session_source_read(path,dict(record.files)[path],record.deadline)).hexdigest()!=digest:
            raise ValueError('Native reservation source bytes changed')
    for path,stamp in record.nodes:
        if _session_five(os.lstat(path))!=stamp:raise ValueError('Native reservation source node changed')
    for path,stamp in record.files:
        if _session_nine(os.lstat(path))!=stamp:raise ValueError('Native reservation source file changed')
    if (_ROOT_SESSION is not record or _session_nine(os.lstat(record.root/_SESSION_PENDING))!=record.marker9
            or _session_five(os.lstat(record.root))!=record.root5):
        raise ValueError('Native reservation final custody changed')
    session_mode(record)


def _session_source_read(path,stamp,deadline):
    from mylar import publication_retained_delivery as retained
    return retained.o.read_checked(path,list(stamp),1048576,deadline)


def session_for_request(value):
    from mylar import publication_retained_delivery as retained
    record=_ROOT_SESSION
    if record is None:return None
    if type(record) is not _NativeSession or retained.o.compact(value)!=record.request_bytes:
        raise ValueError('Only the exact reserved retained request may enter')
    return record


def _session_packet(raw):
    from mylar import publication_guard as guard,publication_retained_delivery as retained
    body=guard.decode_json(raw)
    if (type(body) is not dict or set(body)!={'version','kind','action','nonce','request','proof'}
            or type(body['version']) is not int or body['version']!=1
            or body['kind']!='retained-native-session-v1' or body['action'] not in ('open','observe','close')
            or type(body['nonce']) is not str or not re.fullmatch('[0-9a-f]{64}',body['nonce'])):
        raise ValueError('Exact retained native session request required')
    value=retained.request(body['request'])
    if body['action']!='close':
        if body['proof'] is not None:raise ValueError('No session proof is admitted before close')
    else:
        proof=body['proof']
        if (type(proof) is not dict or set(proof)!={'workflow_sha256','catalog_sha256','record_sha256',
                'root_release_nonce','worker_ack_sha256'}
                or any(type(v) is not str or not re.fullmatch('[0-9a-f]{64}',v) for v in proof.values())
                or proof['root_release_nonce']==body['nonce']):
            raise ValueError('Exact original Root terminal proof required')
    return body,value


def _session_sql(data_root,request,proof_items):
    from mylar import publication_retained_delivery as retained
    proof=dict(proof_items)
    paths=(Path(data_root)/'workflow.sqlite',Path(data_root)/'mylar.db')
    files={str(p):tuple(retained.o.signature(p)) for p in paths}
    nodes=retained._nodes(paths)
    absent=[str(p)+suffix for p in paths for suffix in ('-wal','-shm','-journal')]
    retained._raw(files,nodes,absent,{})
    workflow,catalog=(retained._sql(p,files[str(p)]) for p in paths)
    digest=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    if digest(workflow)!=proof['workflow_sha256'] or digest(catalog)!=proof['catalog_sha256']:
        raise ValueError('Root terminal SQL does not match current reserved originals')
    token=hashlib.sha256((request['ddl_id']+'\0'+request['pack_id']+'\0'+request['member_id']).encode()).hexdigest()
    rows=[json.loads(row) for row in workflow['rows'].get('records',[]) if json.loads(row)[:2]==['retained_delivery_final',token]]
    if (len(rows)!=1 or len(rows[0])!=4 or type(rows[0][2]) is not str
            or hashlib.sha256(rows[0][2].encode()).hexdigest()!=proof['record_sha256']
            or json.loads(rows[0][2]).get('request')!=request):
        raise ValueError('Original finalized retained record required before native release')
    retained._raw(files,nodes,absent,{})
    return tuple(files.items()),tuple(nodes.items()),tuple(absent)


def session_execute(handler,raw):
    """Primary POST control for one exact request; no Reader or import grants."""
    global _ROOT_SESSION
    from mylar import native_writers,publication_retained_delivery as retained,publication_retained_finalize as finalizer
    deadline=time.monotonic()+_SESSION_SECONDS
    caller,config=_http_original(handler,raw)
    if caller[2]!='retainedDeliverySession':raise ValueError('Owning session handler required')
    body,value=_session_packet(raw);request_bytes=retained.o.compact(value)
    action,nonce=body['action'],body['nonce']
    proof_items=tuple(sorted(body['proof'].items())) if action=='close' else ()
    frame=finalizer.response_sources();source=finalizer._SOURCE_FRAMES[frame]
    vector=json.loads(source[3]);files=tuple((p,tuple(v)) for p,v in vector['files9'])
    nodes=tuple((p,tuple(v)) for p,v in vector['nodes5']);hashes=tuple(source[4].items())
    writer=native_writers.owner();root=writer.root
    with native_writers._MODE_LOCK:
        if native_writers._OPERATIONS!=0:raise ValueError('Native operations must settle before reservation control')
        if action=='observe':
            record=_ROOT_SESSION
            state='factual-held' if os.path.lexists(root/_SESSION_PENDING) else 'factual-unreserved'
            if record is not None:
                if record.nonce!=nonce or record.request_bytes!=request_bytes:raise ValueError('Original reservation selector required')
                session_file(writer,record);state='active-original-process'
            answer=dict(version=1,kind='retained-native-session-observation',state=state,nonce=nonce)
        elif action=='open':
            if (_ROOT_SESSION is not None or not native_writers.publication_mode()
                    or os.path.lexists(root/_SESSION_PENDING) or os.path.lexists(root/_SESSION_CLOSED)):
                raise ValueError('Retained native reservation already present or publication unavailable')
            with writer.hold(timeout=0):
                root5=_session_five(os.lstat(root))
                native_writers.admission(writer);_http_close(caller,config)
                marker=retained.o.compact(dict(version=1,kind='retained-native-session-fence-v1',nonce=nonce,
                    request_sha256=hashlib.sha256(request_bytes).hexdigest(),pid=os.getpid()))
                history,history5,history_parent5=_session_history(root,nonce)
                stamp=_session_save(root,_SESSION_PENDING,marker,root5)
                record=_NativeSession(root,root5,nonce,request_bytes,config,
                    os.getpid(),deadline,marker,stamp,files,nodes,hashes,history,history5,history_parent5)
                if _ROOT_SESSION is not None:raise ValueError('Original native reservation absence changed')
                _ROOT_SESSION=record;session_file(writer,record)
                answer=dict(version=1,kind='retained-native-session-opened',nonce=record.nonce,
                    request_sha256=hashlib.sha256(request_bytes).hexdigest(),pid=record.pid,
                    marker_sha256=hashlib.sha256(marker).hexdigest(),marker_signature9=list(stamp))
        else:
            record=_ROOT_SESSION
            if (record is None or record.nonce!=nonce or record.request_bytes!=request_bytes):
                raise ValueError('Only original live native reservation can close')
            closed=None
            try:
                with writer.hold(timeout=0):
                    session_file(writer,record);_http_close(caller,config)
                    _session_sql(config[0],value,proof_items);session_file(writer,record)
                    answer=dict(version=1,kind='retained-native-session-closed',nonce=record.nonce,
                        request_sha256=hashlib.sha256(request_bytes).hexdigest(),proof=dict(proof_items),pid=record.pid)
                    closed=retained.o.compact(answer);closed9=_session_save(root,_SESSION_CLOSED,closed,record.root5)
                    answer.update(mutation_authority=False,reader_resume_grant=False,ordinary_import_grant=False,cleanup_grant=False)
                    result=retained.o.compact(dict(success=True,data=answer)).decode()
                    _http_close(caller,config)
                    sql_original=_session_sql(config[0],value,proof_items)
                    session_file(writer,record)
                    if _session_read(root/_SESSION_CLOSED,closed9)!=closed:
                        raise ValueError('Native reservation close uncertainty')
                    _http_close(caller,config);session_file(writer,record)
                    if _session_nine(os.lstat(root/_SESSION_CLOSED))!=closed9:
                        raise ValueError('Original native completion record changed')
                    _session_retire(record,closed9,sql_original)
            except BaseException:
                if closed is not None:_session_refence(record,closed)
                raise
            _ROOT_SESSION=None
            return result
        answer.update(mutation_authority=False,reader_resume_grant=False,ordinary_import_grant=False,cleanup_grant=False)
        _http_close(caller,config)
        result=retained.o.compact(dict(success=True,data=answer)).decode()
        _http_close(caller,config)
        if action=='open':session_file(writer,record)
        return result
