"""Explicit primary-key retained API admission; no Reader or import grants."""

COMMANDS=('retainedDeliveryFinalize','retainedDeliveryStatus')
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


def execute(handler,raw):
    import mylar
    from mylar import native_writers,publication_guard as guard,publication_retained_delivery as retained,publication_retained_finalize as finalizer
    from mylar.publication_api import Controller
    if not owns(handler):raise ValueError('Exact owning API handler required')
    command=handler.cmd;method=getattr(handler,'_'+command).__func__;method_code=method.__code__
    admission_clock=time.monotonic
    original_caller=(handler,type(handler),command,method,method_code,raw,handler.kwargs,
                     (handler.apitype,handler.img,handler.file,handler.comicrn))
    key=mylar.CONFIG.API_KEY
    if (mylar.CONFIG.API_ENABLED is not True or type(key) is not str or len(key)!=32
            or handler.apikey!=key or getattr(handler,'apitype',None)!='normal'):
        raise ValueError('Primary normal API key required')
    if (getattr(handler,'img',None) or getattr(handler,'file',None) or getattr(handler,'comicrn',False)
            or set(handler.kwargs)!={'request'}):raise ValueError('Exact finite API response required')
    import cherrypy
    if cherrypy.request.method!='POST':raise ValueError('Exact retained POST required')
    if type(raw) is not str or not 0<len(raw.encode())<4096:raise ValueError('Finite retained request required')
    original_config=(mylar.DATA_DIR,mylar.CONFIG.DESTINATION_DIR,mylar.CONFIG.DDL_LOCATION,mylar.CONFIG.API_ENABLED,key)
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
            with native_writers.operation(ordinary=True) as original_writer:
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
