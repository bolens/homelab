"""Finite self-admitted retained API; disabled, factual, same-daemon only."""

ENABLED=False
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
    if ENABLED is not True or retained.ENABLED is not True or finalizer.ENABLED is not True:raise ValueError('Retained endpoint disabled')
    if not owns(handler):raise ValueError('Exact owning API handler required')
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
    frame=finalizer.response_sources()
    value=retained.request(guard.decode_json(raw))
    if not native_writers.publication_mode():raise ValueError('Current publication mode required')
    writer=native_writers.owner()
    # The original strict outer hold outlives inner exit-admission callbacks.
    with writer.hold(timeout=0):
        with native_writers.operation(ordinary=True) as original_writer:
            controller=Controller(mylar.DATA_DIR,[mylar.CONFIG.DESTINATION_DIR])
            if handler.cmd=='retainedDeliveryFinalize':
                cap=retained.prepare_existing(controller,original_writer,value);cap.accept()
                receipt=finalizer.finalize(cap)
            else:receipt=finalizer.response_existing(controller,original_writer,value)
            envelope=receipt.encode(handler,frame)
        if original_config!=(mylar.DATA_DIR,mylar.CONFIG.DESTINATION_DIR,mylar.CONFIG.DDL_LOCATION,mylar.CONFIG.API_ENABLED,mylar.CONFIG.API_KEY):
            raise ValueError('Original API configuration changed')
        receipt.close(envelope)
    # No new admission or proof refresh after release. Only the same originals.
    return receipt.finish(envelope)
