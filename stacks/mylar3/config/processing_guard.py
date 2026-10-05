"""Own the native processing lock for the complete lifetime of one run."""
from functools import wraps
from contextlib import ExitStack
import threading

_RUN = threading.RLock()
_ACTIVE = threading.local()


def source(base, filename):
    from pathlib import Path
    if filename is not None and Path(filename).is_absolute():return str(filename)
    path=Path(base)
    if path.is_file() or filename is None:return str(path)
    return str(path/filename)


def retained(review, processor=None, *, issueid=None):
    """Record a lower-boundary review before the processing observer unwinds."""
    processor=processor if processor is not None else getattr(_ACTIVE,'processor',None)
    if processor is not None and not any(row.get('mode')=='review'
            and row.get('reason')==review.reason and row.get('payload')==review.payload
            for row in processor.valreturn):
        processor.valreturn.append(dict(mode='review',retained=True,
            reason=review.reason,payload=review.payload,issueid=issueid))


def publication(processor, source, *, issueid=None, comicid=None):
    if __package__:
        from .publication_native import require, Review
    else:
        from publication_native import require, Review
    try:
        result=require(source,issueid=issueid,comicid=comicid)
        if result is not None:processor._publication_owner=result['owner']
        return result
    except Review as review:
        # Set the distinct outcome before unwinding the observer. Never encode
        # it as a legacy tagging failure or successful stopped processing run.
        retained(review,processor,issueid=issueid)
        raise


def proposed(processor,field):
    return (getattr(processor,'_publication_owner',None) or {}).get(field)


def relocation(processor, result, destination=None, *, action=None):
    """Hold existing registered source moves before any filesystem mutation.

    A later reviewed transition contract may admit these relocations. Ordinary
    acceptance cannot infer a new catalog path after losing the original one.
    """
    import mylar
    from pathlib import Path
    if action is None:action=mylar.CONFIG.FILE_OPTS
    if (result is None or result['decision']!='allowed' or action in ('copy','hardlink')
            or (action=='move' and destination is not None
                and Path(destination).absolute()==Path(result['path']).absolute())):
        return
    owned=any(Path(fact['catalog']['path'])==Path(result['path']).resolve()
              for fact in result['observed'])
    if not owned:return
    if __package__:
        from .publication_native import Review
    else:
        from publication_native import Review
    review=Review('registered-source-relocation',payload=result['inventory']['payload'])
    processor.valreturn.append(dict(mode='review',retained=True,reason=review.reason,payload=review.payload))
    raise review


def placement(processor,source,destination,*,issueid=None,comicid=None,
              arc=False,one_off=False,multiple=False):
    import mylar
    result=publication(processor,source,issueid=issueid,comicid=comicid)
    action=mylar.CONFIG.FILE_OPTS
    if any((arc,one_off)):
        action='copy' if multiple is True else mylar.CONFIG.ARC_FILEOPS
    if arc is True and action in ('copy','move'):action='copy'
    relocation(processor,result,destination,action=action)


def displacement(processor,source):
    result=publication(processor,source,issueid=proposed(processor,'issueid'),
                       comicid=proposed(processor,'parentcomicid'))
    relocation(processor,result,action='move')


def cleanup(processor,source,destination,*,issueid=None,comicid=None):
    import mylar
    import os
    from pathlib import Path
    if not mylar.native_writers.publication_mode():return
    present=False
    for path in dict.fromkeys((str(source),str(destination))):
        if os.path.lexists(path):
            publication(processor,path,issueid=issueid,comicid=comicid);present=True
    if not present:
        publication(processor,Path(source),issueid=issueid,comicid=comicid)


def cleanup_scope(processor,odir=None,del_nzbdir=False,sub_path=None,
                  cacheonly=False,filename=None):
    """Admit the complete actual tidyup deletion set before its first deletion."""
    import mylar
    import os
    from pathlib import Path
    if not mylar.native_writers.publication_mode():return
    if __package__:
        from . import publication_native as native
    else:
        import publication_native as native
    targets=[];scopes={}
    def snapshot(path):
        return native.scope_snapshot(path) if os.path.lexists(path) else None
    try:
        if not mylar.native_writers.active():raise native.guard.Unavailable('Outer admission required')
        writer=mylar.native_writers.owner()
        if not writer.local[1].depth:raise native.guard.Unavailable('Writer required')
        mylar.native_writers.admission(writer)
        if mylar.CONFIG.ENABLE_META and odir is not None and 'mylar_' in str(odir):
            scopes[str(odir)]=snapshot(odir)
            for path in (scopes[str(odir)] or {}) if os.path.isdir(odir) else {}:
                item=Path(path)
                if item.is_file():
                    if item.suffix.lower() not in native.EXTENSIONS:
                        raise native.guard.Unavailable('Unclassified cache cleanup entry')
                    targets.append(item)
        if not cacheonly and mylar.CONFIG.FILE_OPTS=='move' and filename is not None and (
                processor.nzb_name=='Manual Run' or del_nzbdir is True):
            original=processor.nzb_folder
            if (sub_path is not None and sub_path!=original
                    and sub_path!=os.path.join(original,'mega') and processor.issueid is None):
                original=sub_path
            folder=Path(original)
            if folder.name==filename and not folder.is_dir():folder=folder.parent
            target=folder/filename
            scopes[str(folder)]=snapshot(folder)
            scopes[str(target)]=snapshot(target)
            if scopes[str(target)] is not None:
                targets.extend(native.discover(target))
        for target in dict.fromkeys(targets):
            result=publication(processor,target,issueid=proposed(processor,'issueid'),
                               comicid=proposed(processor,'parentcomicid'))
            relocation(processor,result,action='move')
        if any(snapshot(path)!=before for path,before in scopes.items()):
            raise native.guard.Unavailable('Cleanup deletion set changed during admission')
        mylar.native_writers.admission(writer)
    except (native.guard.Unavailable,OSError,ValueError,TypeError):
        review=native.Review()
        processor.valreturn.append(dict(mode='review',retained=True,reason=review.reason))
        raise review from None


def run(function):
    @wraps(function)
    def wrapped(self, *args, **kwargs):
        import mylar
        from mylar import pack_intake, native_writers
        from mylar.media_writer import Busy
        if __package__:
            from .publication_native import Review
        else:
            from publication_native import Review
        try:
            # Always acquire the shared writer first: a guarded rescan can call
            # processing synchronously. Reversing these locks deadlocks callers.
            with ExitStack() as admission:
                try:
                    admission.enter_context(native_writers.operation())
                except Busy:
                    # No processing has begun. Preserve the exact job for the
                    # serial worker rather than consuming it as a finished run.
                    mylar.PP_QUEUE.put({
                        'nzb_name': self.nzb_name, 'nzb_folder': self.nzb_folder,
                        'issueid': self.issueid, 'comicid': self.comicid,
                        'failed': False, 'apicall': self.apicall, 'ddl': self.ddl,
                        'download_info': getattr(self, 'download_info', None),
                    })
                    from mylar import logger
                    logger.warn('Media writer busy; post-processing retained in queue for retry')
                    return None
                with _RUN:
                    mylar.APILOCK = True
                    previous=getattr(_ACTIVE,'processor',None)
                    _ACTIVE.processor=self
                    try:
                        if pack_intake.capture(self):
                            return None
                        try:
                            return function(self, *args, **kwargs)
                        except Review as review:
                            retained(review,self)
                            from mylar import logger
                            logger.warn('Publication identity requires review; source retained')
                            self.queue.put(self.valreturn)
                            raise
                    finally:
                        _ACTIVE.processor=previous
                        mylar.APILOCK = False
        except Review:
            # Acknowledge under the Writer, then let the refusal cross every
            # owning admission context before consuming it at this boundary.
            return None
        finally:
            # Admission failures must complete a synchronous caller's queue too,
            # without clearing APILOCK belonging to another active processor.
            queue = getattr(self, 'queue', None)
            if queue is not None and queue.empty():
                queue.put([{'mode': 'stop'}])
    return wrapped
