"""Native workflow observations, durable handoffs and intake admission."""
from functools import wraps
import hashlib
import inspect
import json
import re
from pathlib import Path
import shutil
import threading
import time
import uuid

from mylar import library_status
from mylar.workflow_store import Store, LOCK, identifier, ddl_identifier, label

_STORE=None
_CONTEXT=threading.local()
_STARTED=False
_LAST_TICK=0
_OBSERVER_ERRORS=0
_ISSUE_LOCKS={}
_ISSUE_GUARD=threading.Lock()
_DEFAULTS={'library_missing_tags':False,'library_nested_metadata':False,'ddl_kind':'mixed','ddl_order':'fifo','ddl_paused':False,'pack_automation':False,'auto_handoff':False,'handoff_hours':2,'intake_enabled':True,
           'queue_high':50,'queue_low':20,'free_stop_gib':5,'free_resume_gib':8}
IMPORT_HELD={'queued','claimed','submitted','review'}
DISPATCH_HELD={'sending','review','accepted'}
HELD={'queued','searching','dispatching','accepted','review'}


def issue_lock(issueid):
    with _ISSUE_GUARD:return _ISSUE_LOCKS.setdefault(str(issueid),threading.RLock())


def store():
    global _STORE
    import mylar
    if __package__:
        from . import native_writers
        with LOCK:_STORE=native_writers.existing_store(mylar.DATA_DIR,cached=_STORE)
    elif _STORE is None:
        with LOCK:
            if _STORE is None:_STORE=Store(mylar.DATA_DIR)
    return _STORE


def emit(stage,outcome,**kwargs):
    global _OBSERVER_ERRORS
    try:store().event(stage,outcome,**kwargs)
    except Exception:_OBSERVER_ERRORS+=1


def policy():
    value = dict(_DEFAULTS, **store().get('policy', 'current', {}))
    if value['ddl_order'] in ('singles', 'packs', 'alternate'):
        value['ddl_kind'], value['ddl_order'] = value['ddl_order'], 'fifo'
    return value


def set_policy(values):
    with LOCK:
        value=policy()
        if not isinstance(values,dict) or set(values)-set(_DEFAULTS):raise ValueError('Unknown policy setting')
        values = dict(values)
        if values.get('ddl_order') in ('singles', 'packs', 'alternate'):
            values.setdefault('ddl_kind', values['ddl_order'])
            values['ddl_order'] = 'fifo'
        for k,v in values.items():
            if k=='ddl_order':
                if v not in ('fifo','newest','release_oldest','release_newest'):raise ValueError('Unknown DDL download order')
            elif k=='ddl_kind':
                if v not in ('mixed','singles','packs','alternate'):raise ValueError('Unknown DDL download type')
            elif isinstance(_DEFAULTS[k],bool):
                if not isinstance(v,bool):raise ValueError('Expected an enabled or disabled setting')
            elif not isinstance(v,int) or isinstance(v,bool):raise ValueError('Expected whole-number thresholds')
            value[k]=v
        if not (1<=value['handoff_hours']<=168 and 1<=value['queue_low']<value['queue_high']<=1000
                and 1<=value['free_stop_gib']<value['free_resume_gib']<=10240):
            raise ValueError('Thresholds must be ordered and within the displayed limits')
        store().set('policy','current',value)
        cached=store().get('intake','current',{})
        if cached:
            cached['checked_at']=0
            store().set('intake','current',cached)
        emit('intake','Workflow settings updated')
        return value


def intake():
    import mylar
    with LOCK:
        rules=policy(); now=time.time(); old=store().get('intake','current',{})
        if now-old.get('checked_at',0)<10:return old
        depth=mylar.PP_QUEUE.qsize()+int(bool(mylar.APILOCK))
        roots=[]
        for key in ('DESTINATION_DIR','DDL_LOCATION','CACHE_DIR'):
            p=getattr(mylar.CONFIG,key,None)
            if p and p not in roots:roots.append(p)
        if getattr(mylar.CONFIG,'ENABLE_CHECK_FOLDER',False):
            p=getattr(mylar.CONFIG,'CHECK_FOLDER',None)
            if p and p not in roots:roots.append(p)
        free=None;error=False
        try:
            if not roots:raise OSError('No configured storage')
            for root in roots:
                if not Path(root).is_dir():raise OSError('Missing configured storage')
                amount=shutil.disk_usage(root).free
                free=amount if free is None else min(free,amount)
        except OSError:error=True
        paused=old.get('paused',False)
        if not rules['intake_enabled']:paused=False;reason='Intake limits disabled'
        elif error:paused=True;reason='Configured storage is missing or unreadable'
        elif (depth>rules['queue_low'] if paused else depth>=rules['queue_high']):paused=True;reason='Waiting for post-processing backlog to drain'
        elif free<(rules['free_resume_gib'] if paused else rules['free_stop_gib'])*1024**3:paused=True;reason='Waiting for free storage'
        else:paused=False;reason='Accepting new searches and downloads'
        value={'paused':paused,'reason':reason,'depth':depth,'free_bytes':free,'checked_at':now}
        if paused!=old.get('paused') or reason!=old.get('reason'):emit('intake',reason)
        store().set('intake','current',value)
        return value


def reservation(issueid):
    row=store().get('handoff',identifier(issueid))
    return row if row and row['phase'] in HELD else None


def import_owner(issueid,except_id=None):
    return next((r for r in store().active('command',IMPORT_HELD)
                 if r['issueid']==str(issueid) and r['id']!=except_id),None)


def dispatch_owner(issueid):
    row=store().get('dispatch',identifier(issueid),{})
    return row if row.get('phase') in DISPATCH_HELD else None


def native_busy(issueid,active_only=False):
    import mylar
    from mylar import db,workflow_nzb
    if mylar.APILOCK or workflow_nzb.busy(issueid):return True
    for name in ('NZB_QUEUE','PP_QUEUE'):
        queue=getattr(mylar,name,None)
        if queue:
            with queue.mutex:
                if any(isinstance(x,dict) and str(x.get('issueid'))==str(issueid) for x in queue.queue):return True
    states="('Downloading')" if active_only else "('Queued','Downloading','NZB handoff')"
    return bool(db.DBConnection().select('SELECT id FROM ddl_info WHERE issueid=? AND status IN '+states,[str(issueid)]))


def admit_import(issueid,command_id=None):
    from mylar import db
    current=library_status.issue(db.DBConnection(), issueid)
    if not current or current['Status'] in ('Downloaded','Archived'):
        raise ValueError('Issue is imported, archived, deleted or unavailable')
    if reservation(issueid) or dispatch_owner(issueid) or import_owner(issueid,command_id) or native_busy(issueid):
        raise ValueError('Another download or processing task owns this issue')


def processing_put(queue,item,command_id=None):
    """Atomic final admission, with a durable receipt before a guided queue write."""
    from mylar import queue_control
    proof=getattr(_CONTEXT,'publication_handoff',None)
    if proof is not None:
        from pathlib import Path
        if (str(item.get('issueid'))!=proof['owner']['issueid']
                or str(item.get('comicid'))!=proof['owner']['parentcomicid']
                or str(Path(item.get('nzb_folder',''))/item.get('nzb_name',''))!=proof['source']
                or item.get('download_info') is not None):
            raise ValueError('Queued import differs from verified native handoff')
        item=dict(item,download_info={'publication_handoff':proof})
    iid=identifier(item.get('issueid'))
    if not iid:
        if command_id:raise ValueError('Guided imports require a regular issue ID')
        return queue.put(item)
    with issue_lock(iid),queue_control._LOCK,LOCK:
        if command_id:
            row=store().get('command',command_id)
            if not row or row['issueid']!=iid or row['comicid']!=identifier(item.get('comicid')) or row['phase']!='claimed' or row.get('dispatched'):
                raise ValueError('Guided import has already been submitted or needs review')
            admit_import(iid,command_id)
            row.update(dispatched=True,updated_at=time.time())
            if proof is not None:row.update(phase='submitted')
            store().set('command',command_id,row)
        elif import_owner(iid) or (reservation(iid) and reservation(iid)['phase'] not in ('accepted','review')):
            raise ValueError('Issue is reserved for another workflow')
        queue.put(item)


def defer_search(issueid,comicid=None):
    iid=identifier(issueid)
    if iid:
        from mylar import db
        row=library_status.issue(db.DBConnection(), iid)
        cid=identifier(row['ComicID']) if row else ''
        if cid:store().set('deferred',iid,{'issueid':iid,'comicid':cid,'phase':'waiting'})


def in_handoff(issueid=None):
    row=getattr(_CONTEXT,'handoff',None)
    return bool(row and (issueid is None or str(issueid)==row['issueid']))


def provider_order(order,nzbproviders):
    return [p for p in order if p in nzbproviders] if in_handoff() else order


def busy_issue(issueid):
    import mylar
    from mylar import workflow_nzb
    if mylar.APILOCK or workflow_nzb.busy(issueid):return True
    for name in ('NZB_QUEUE','PP_QUEUE'):
        queue=getattr(mylar,name,None)
        if queue:
            with queue.mutex:
                if any(isinstance(x,dict) and str(x.get('issueid'))==issueid for x in queue.queue):return True
    # AUTO-COMPLETE-NZB removes entries while polling; native release records also protect dispatch.
    from mylar import db
    rows=db.DBConnection().select('SELECT PROVIDER FROM nzblog WHERE IssueID=?',[issueid])
    return any(str(r['PROVIDER']).casefold() not in ('ddl','ddl(getcomics)','ddl(external)') for r in rows)


def eligible(ddl_id,allow_held=False,exhausted=False):
    from mylar import db
    database=db.DBConnection()
    raw=database.selectone('SELECT * FROM ddl_info WHERE id=?',[ddl_id]).fetchone()
    if not raw:raise ValueError('DDL entry no longer exists')
    # SQLite's native ID column loses case-insensitive lookup in a plain dict.
    row={name.lower(): raw[name] for name in raw.keys()}
    iid=identifier(row.get('issueid'));cid=identifier(row.get('comicid'))
    if not iid or not cid or str(row.get('pack')).lower() not in ('0','false','none',''):
        raise ValueError('Only regular single-issue downloads can be switched')
    if row.get('site')!='DDL(GetComics)':raise ValueError('This download source cannot be switched')
    allowed=('Queued','NZB handoff') if allow_held else (('Failed',) if exhausted else ('Queued',))
    if row['status'] not in allowed:raise ValueError('Only waiting, inactive DDL entries can be switched')
    issue=database.selectone('SELECT Status,ComicID,Location FROM issues WHERE IssueID=?',[iid]).fetchone()
    if not issue or str(issue['ComicID'])!=cid or issue['Status'] in ('Downloaded','Archived') or issue['Location']:
        raise ValueError('Issue is missing, already downloaded, or needs library review')
    others=database.select("SELECT id FROM ddl_info WHERE issueid=? AND id!=? AND status IN ('Queued','Downloading','NZB handoff','Completed')",[iid,ddl_id])
    sending=store().get('dispatch',iid,{})
    if others or busy_issue(iid) or import_owner(iid) or sending.get('phase') in DISPATCH_HELD:raise ValueError('Another download or processing task owns this issue')
    import mylar
    if iid in {str(k) for k in mylar.PACK_ISSUEIDS_DONT_QUEUE}:raise ValueError('This issue belongs to a queued pack')
    if exhausted and str(ddl_id) in {str(k) for k in mylar.DDL_QUEUED}:
        raise ValueError('DDL failure cleanup is still active')
    held=reservation(iid) if allow_held else None
    if held and held.get('exhausted_release') and exhausted_release(row)!=held['exhausted_release']:
        raise ValueError('Exhausted release changed before NZB search')
    return row


def exhausted_release(row):
    """Only a current terminal mirror receipt permits automatic Failed admission."""
    from mylar import queue_control
    record=queue_control.store().data['items'].get(str(row['id']),{})
    release=hashlib.sha256((str(row.get('mainlink'))+':'+str(row.get('issueid'))).encode()).hexdigest()
    if (record.get('release')!=release or record.get('retry_stopped')!='mirrors_exhausted'
            or record.get('attempts',0)>=queue_control.ATTEMPT_LIMIT):
        raise ValueError('No confirmed mirror exhaustion for this release')
    return release


def request_handoff(ddl_id,exhausted=False):
    import mylar
    from mylar import queue_control,db,search
    preliminary=db.DBConnection().selectone('SELECT issueid FROM ddl_info WHERE id=?',[ddl_identifier(ddl_id)]).fetchone()
    if not preliminary:raise ValueError('DDL entry no longer exists')
    with issue_lock(preliminary['issueid']),queue_control._LOCK,LOCK:
        existing=reservation(preliminary['issueid'])
        if existing and existing['ddl_id']==str(ddl_id):return existing
        row=eligible(ddl_identifier(ddl_id),exhausted=exhausted);iid=str(row['issueid'])
        release=exhausted_release(row) if exhausted else None
        if exhausted and store().get('exhaustion_attempt',str(ddl_id),{}).get('release')==release:
            raise ValueError('NZB fallback already attempted for this release')
        old=reservation(iid)
        if old:return old
        providers=search.provider_order()['prov_order']
        if not any(p.startswith('newznab:') or p.lower()=='experimental' for p in providers):
            raise ValueError('No enabled, unblocked NZB indexer is available')
        if not (mylar.USE_NZBGET or mylar.USE_SABNZBD):raise ValueError('Handoff requires NZBGet or SABnzbd')
        value={'id':uuid.uuid4().hex,'ddl_id':str(row['id']),'issueid':iid,'comicid':str(row['comicid']),
               'name':label(row['series']),'phase':'queued','created_at':time.time(),'reason':'Waiting for NZB search'}
        if exhausted:
            value.update(exhausted_release=release,reason='Mirrors exhausted; waiting for NZB-only fallback')
        # Durable reservation precedes native status change; DDL begin checks both.
        store().set('handoff',iid,value)
        if exhausted:store().set('exhaustion_attempt',str(row['id']),{'release':release})
        db.DBConnection().upsert('ddl_info',{'status':'NZB handoff'},{'id':row['id']})
        mylar.SEARCH_QUEUE.put({'issueid':iid,'comicid':value['comicid'],'workflow_handoff':value['id']})
        emit('handoff',value['reason'] if exhausted else 'Reserved for NZB-only search',issueid=iid,comicid=value['comicid'],name=value['name'])
        return value


def set_handoff(row,phase,reason):
    value=dict(row,phase=phase,reason=reason,updated_at=time.time())
    store().set('handoff',row['issueid'],value)
    emit('handoff',reason,issueid=row['issueid'],comicid=row['comicid'],name=row['name'])
    return value


def restore_ddl(row,no_result=False):
    import mylar
    from mylar import db,queue_control
    with queue_control._LOCK,LOCK:
        if no_result and row.get('exhausted_release'):
            db.DBConnection().upsert('ddl_info',{'status':'Failed'},{'id':row['ddl_id']})
            set_handoff(row,'no-result','No NZB accepted; exhausted DDL remains Failed')
            return
        db.DBConnection().upsert('ddl_info',{'status':'Queued'},{'id':row['ddl_id']})
        set_handoff(row,'no-result','No NZB accepted; DDL queue restored')
        queue_control.recover(mylar.DDL_QUEUE, record_id=row['ddl_id'])


def queue_item(item,queue):
    """Called by the sole native search worker before local-file checks."""
    import mylar
    if intake()['paused']:
        queue.put(item);time.sleep(5);return True
    token=item.get('workflow_handoff')
    if not token:return bool(reservation(item.get('issueid')) or import_owner(item.get('issueid')) or dispatch_owner(item.get('issueid')))
    from mylar import queue_control
    with queue_control._LOCK,LOCK:
        row=reservation(item.get('issueid'))
        if not row or row['id']!=token or row['phase']!='queued':return True
        try:eligible(row['ddl_id'],True)
        except ValueError:
            set_handoff(row,'review','Issue changed before search; review required');return True
        row=set_handoff(row,'searching','Searching enabled NZB indexers')
    _CONTEXT.handoff=row
    try:
        mylar.search.searchforissue(row['issueid'],manual=False)
    except Exception:
        current=reservation(row['issueid'])
        if current and current['phase']=='searching':set_handoff(current,'review','Search interrupted; review required')
    finally:
        _CONTEXT.handoff=None
    with queue_control._LOCK,LOCK:
        current=reservation(row['issueid'])
        if current and current['phase']=='searching':
            if store().get('deferred',row['issueid']):
                set_handoff(current,'queued','Waiting for intake capacity')
            else:restore_ddl(current,no_result=True)
        elif current and current['phase']=='dispatching':set_handoff(current,'review','Downloader acceptance is uncertain; review required')
    return True


def send_allowed(issueid,comicinfo):
    row=reservation(issueid)
    if row and not (in_handoff(issueid) and row['phase']=='searching'):return False
    if intake()['paused']:
        defer_search(issueid);return False
    if import_owner(issueid) or dispatch_owner(issueid):return False
    if row:
        if not comicinfo or comicinfo[0].get('pack') or comicinfo[0].get('oneoff'):return False
        try:eligible(row['ddl_id'],True)
        except ValueError:return False
    return True


def sender(function,issueid):
    """Persist external-send intent before crossing the downloader boundary."""
    from mylar import queue_control
    with issue_lock(issueid),queue_control._LOCK,LOCK:
        if intake()['paused']:
            defer_search(issueid);return {'status':False}
        if import_owner(issueid) or dispatch_owner(issueid):return {'status':False}
        row=reservation(issueid)
        if row:
            if not in_handoff(issueid) or row['phase']!='searching':return {'status':False}
            try:eligible(row['ddl_id'],True)
            except ValueError:return {'status':False}
            row=set_handoff(row,'dispatching','Sending NZB; acceptance pending')
        if not row and identifier(issueid):store().set('dispatch',str(issueid),{'issueid':str(issueid),'phase':'sending','reason':'Downloader acceptance pending'})
    try:result=function()
    except Exception:
        if row:set_handoff(row,'review','Downloader acceptance is uncertain; review required')
        elif identifier(issueid):store().set('dispatch',str(issueid),{'issueid':str(issueid),'phase':'review','reason':'Downloader acceptance is uncertain'})
        raise
    if row:
        if isinstance(result,dict) and result.get('status') is True:
            set_handoff(row,'accepted','NZB accepted; original DDL held')
        else:
            # Native clients collapse transport timeouts and rejections; do not guess.
            set_handoff(row,'review','Downloader acceptance is uncertain; review required')
    elif identifier(issueid):
        store().set('dispatch',str(issueid),{'issueid':str(issueid),'phase':'accepted' if isinstance(result,dict) and result.get('status') is True else 'review','reason':'Awaiting library confirmation or downloader review'})
    return result


def dispatch(function):
    signature=inspect.signature(function)
    @wraps(function)
    def wrapped(*args,**kwargs):
        values=signature.bind(*args,**kwargs).arguments;iid=values.get('IssueID')
        from mylar import queue_control
        with issue_lock(iid):
            with queue_control._LOCK,LOCK:
                if not send_allowed(iid,values.get('comicinfo')):
                    emit('intake','Download deferred by intake limit or issue reservation',issueid=iid)
                    return 'downloadchk-fail'
            result=function(*args,**kwargs)
        emit('download','Release sent to downloader' if isinstance(result,dict) else 'Download submission did not complete',
             issueid=iid,comicid=values.get('ComicID'),name=values.get('nzbname'),provider=values.get('nzbprov'))
        return result
    return wrapped


def observe_search(function):
    signature=inspect.signature(function)
    @wraps(function)
    def wrapped(*args,**kwargs):
        values=signature.bind(*args,**kwargs).arguments
        info={'issueid':values.get('IssueID'),'comicid':values.get('ComicID'),'name':values.get('ComicName')}
        if intake()['paused']:
            defer_search(info['issueid'],info['comicid'])
            emit('search','Search deferred by intake limits',**info)
            return ([] if values.get('manual') else {'status':False},'None')
        store().delete('deferred',identifier(info['issueid']))
        _CONTEXT.issue=info
        emit('search','Search started',**info)
        try:
            result=function(*args,**kwargs)
            found=isinstance(result,tuple) and isinstance(result[0],dict) and result[0].get('status') is True
            emit('search','Matching release found' if found else 'Search finished without an accepted release',**info)
            return result
        except Exception:
            emit('search','Search failed; check application logs',**info);raise
        finally:_CONTEXT.issue=None
    return wrapped


def observe_provider(function):
    @wraps(function)
    def wrapped(info,*args,**kwargs):
        context=getattr(_CONTEXT,'issue',None) or {}
        provider=info.get('current_prov','')
        if isinstance(provider,dict):provider=next(iter(provider),'Provider')
        emit('provider','Provider search started',provider=provider,**context)
        try:
            result=function(info,*args,**kwargs)
            emit('provider','Provider returned a match' if result.get('status') else 'No accepted match from provider',provider=provider,**context)
            return result
        except Exception:
            emit('provider','Provider request failed; check logs',provider=provider,**context);raise
    return wrapped


def tick(queue):
    if __package__:
        from . import native_writers
        if native_writers.publication_mode():
            if native_writers.startup_status()['state'] != 'ready':return
            with native_writers.operation():return _tick(queue)
    return _tick(queue)


def _tick(queue):
    global _STARTED,_LAST_TICK
    now=time.time()
    if now-_LAST_TICK<30:return
    _LAST_TICK=now
    try:
        from mylar import db
        if not _STARTED:
            with LOCK:
                for row in store().active('handoff',HELD):
                    if row.get('exhausted_release'):
                        store().set('exhaustion_attempt',row['ddl_id'],{'release':row['exhausted_release']})
                        if row['phase']=='searching':
                            native=db.DBConnection().selectone('SELECT status FROM ddl_info WHERE id=? AND issueid=?',
                                                               [row['ddl_id'],row['issueid']]).fetchone()
                            if native and native['status']=='Failed':
                                set_handoff(row,'no-result','No NZB accepted; exhausted DDL remains Failed')
                            else:
                                set_handoff(row,'review','Restart during final NZB search; review required')
                            continue
                        # Recover a crash after reservation but before native status publication.
                        db.DBConnection().action("UPDATE ddl_info SET status='NZB handoff' WHERE id=? AND issueid=? AND status='Failed'",
                                                 [row['ddl_id'],row['issueid']])
                    if row['phase']=='dispatching':set_handoff(row,'review','Restart during downloader send; review required')
                    elif row['phase'] in ('queued','searching'):
                        row=set_handoff(row,'queued','Resuming reserved NZB search')
                        queue.put({'issueid':row['issueid'],'comicid':row['comicid'],'workflow_handoff':row['id']})
            _STARTED=True
        rows=library_status.confirmed(db.DBConnection())
        seen=store().get('meta','library_seen')
        current={str(r['IssueID']) for r in rows}
        if seen is not None:
            for r in rows:
                if str(r['IssueID']) not in seen:
                    emit('library','Confirmed in library',issueid=r['IssueID'],comicid=r['ComicID'],name=r['ComicName'])
        if seen is None or set(seen)!=current:store().set('meta','library_seen',sorted(current))
        for held in store().active('handoff',HELD|{'source-ready'}):
            if held['phase'] in ('accepted','source-ready') and held['issueid'] in current:
                db.DBConnection().upsert('ddl_info',{'status':'Completed'},{'id':held['ddl_id']})
                set_handoff(held,'completed','Issue confirmed in library; original DDL retired')
        for held in store().active('dispatch',DISPATCH_HELD):
            if held['issueid'] in current:
                store().set('dispatch',held['issueid'],dict(held,phase='completed'))
        if not intake()['paused']:
            for deferred in store().active('deferred',{'waiting'},50):
                row=reservation(deferred['issueid'])
                item=dict(deferred)
                if row:
                    if row['phase']!='queued':continue
                    item['workflow_handoff']=row['id']
                queue.put(item)
                store().delete('deferred',deferred['issueid'])
        if not intake()['paused']:
            for r in db.DBConnection().select("SELECT id FROM ddl_info WHERE status='Failed' ORDER BY updated_date"):
                try:
                    request_handoff(str(r['id']),exhausted=True)
                    break
                except ValueError:continue
        if policy()['auto_handoff'] and not intake()['paused']:
            for r in db.DBConnection().select("SELECT id,updated_date FROM ddl_info WHERE status='Queued' ORDER BY updated_date LIMIT 100"):
                try:
                    age=now-time.mktime(time.strptime(str(r['updated_date'])[:16],'%Y-%m-%d %H:%M'))
                    previous=store().get('auto_attempt',str(r['id']),{})
                    if age>=policy()['handoff_hours']*3600 and now-previous.get('at',0)>=policy()['handoff_hours']*3600:
                        request_handoff(str(r['id']));store().set('auto_attempt',str(r['id']),{'at':now});break
                except (ValueError,TypeError):continue
    except Exception:
        global _OBSERVER_ERRORS
        _OBSERVER_ERRORS+=1


def ddl_begin(function,item,queue):
    from mylar import db,queue_control
    if intake()['paused']:
        queue.put(item);time.sleep(5);return False
    with queue_control._LOCK,LOCK:
        if reservation(item.get('issueid')) or import_owner(item.get('issueid')) or dispatch_owner(item.get('issueid')):
            queue_control.clear_active(item['id']);return False
        ready=function(item,queue)
        if ready:
            db.DBConnection().upsert('ddl_info',{'status':'Downloading'},{'id':item['id']})
            emit('download','DDL transfer started',issueid=item.get('issueid'),comicid=item.get('comicid'),name=item.get('series'),provider=item.get('link_type'))
        return ready


def ddl_finished(item,result):
    from mylar import queue_control
    with queue_control._LOCK:
        retry=queue_control.store().data['providers'].get(item.get('link_type'),{}).get('until')
    emit('download','DDL downloaded; handed to processing' if result.get('success') else 'DDL transfer failed; retry policy applies',
         issueid=item.get('issueid'),comicid=item.get('comicid'),name=item.get('series'),provider=item.get('link_type'),retry_at=retry)


def _ddl_row_digest(row):
    # Bind every native column, including private release provenance, without
    # copying URLs or paths into the removal receipt or public response.
    return hashlib.sha256(json.dumps(dict(row),sort_keys=True,separators=(',',':'),
                                     allow_nan=False).encode()).hexdigest()


def remove_handoff_ddl(ddl_id,row,receipt=None):
    """Retire queued/accepted DDL rows; preserve any accepted NZB ownership.

    Caller owns issue -> queue -> workflow locks. No downloader, media, issue,
    or processing operation belongs to this action. A prepared receipt allows
    recovery after native DELETE or its acknowledgement was interrupted.
    """
    from mylar import db
    ddl_id=ddl_identifier(ddl_id)
    if not ddl_id:raise ValueError('Invalid DDL entry')
    journal=store()
    receipt=journal.get('ddl_handoff_removal',ddl_id) if receipt is None else receipt
    if receipt is not None:
        keys={'version','ddl_id','issueid','comicid','handoff_id','row_digest','handoff_phase','phase'}
        if (type(receipt) is not dict or set(receipt)!=keys
                or type(receipt['version']) is not int or receipt['version']!=1
                or receipt['ddl_id']!=ddl_id
                or not identifier(receipt['issueid']) or not identifier(receipt['comicid'])
                or not re.fullmatch(r'[a-f0-9]{32}',str(receipt['handoff_id']))
                or not re.fullmatch(r'[a-f0-9]{64}',str(receipt['row_digest']))
                or receipt['handoff_phase'] not in ('queued','accepted')
                or receipt['phase'] not in ('prepared','removed')):
            raise ValueError('DDL removal receipt requires review')
        iid=receipt['issueid']
    elif row is not None:
        iid=str(row['issueid'])
    else:raise ValueError('DDL handoff entry unavailable')
    owner=journal.get('handoff',iid)
    allowed={'queued','accepted'} if receipt is None else ({'queued','released'} if receipt['handoff_phase']=='queued' else {'accepted','completed'})
    if (not owner or owner.get('phase') not in allowed
            or not re.fullmatch(r'[a-f0-9]{32}',str(owner.get('id')))
            or not identifier(owner.get('issueid')) or not identifier(owner.get('comicid'))
            or import_owner(iid) or dispatch_owner(iid)
            or str(owner.get('ddl_id'))!=ddl_id or str(owner.get('issueid'))!=iid
            or (receipt is not None and (owner.get('id')!=receipt['handoff_id']
                or str(owner.get('comicid'))!=receipt['comicid']))):
        raise ValueError('Confirm the NZB handoff in Activity before removing this entry')
    if row is not None:
        if (owner['phase'] not in ('queued','accepted','released') or str(row['issueid'])!=iid
                or str(row['comicid'])!=str(owner['comicid'])
                or row['status']!='NZB handoff' or str(row['pack']) not in ('0','False')
                or row['site']!='DDL(GetComics)'):
            raise ValueError('DDL handoff entry changed; review required')
        digest=_ddl_row_digest(row)
        if receipt is not None and (receipt['row_digest']!=digest or receipt['phase']=='removed'):
            raise ValueError('DDL entry was replaced; review required')
        if receipt is None:
            receipt={'version':1,'ddl_id':ddl_id,'issueid':iid,'comicid':str(owner['comicid']),
                     'handoff_id':owner['id'],'row_digest':digest,'handoff_phase':owner['phase'],'phase':'prepared'}
            if not journal.create('ddl_handoff_removal',ddl_id,receipt):
                raise ValueError('DDL removal state changed; refresh before retrying')
        if receipt['handoff_phase']=='queued' and owner['phase']=='queued':
            cancelled=dict(owner,phase='released',reason='Operator removed pending DDL handoff',updated_at=time.time())
            if not journal.replace('handoff',iid,owner,cancelled):
                raise ValueError('DDL handoff changed; removal requires review')
            owner=cancelled
        # Conditional deletion protects even against an out-of-process row edit.
        columns=list(dict(row))
        if not all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',key) for key in columns):
            raise ValueError('Unsupported DDL row schema')
        if journal.get('ddl_handoff_removal',ddl_id)!=receipt or journal.get('handoff',iid)!=owner:
            raise ValueError('DDL handoff state changed; review required')
        db.DBConnection().action('DELETE FROM ddl_info WHERE '+
            ' AND '.join('"'+key+'" IS ?' for key in columns),[row[key] for key in columns])
        remaining=db.DBConnection().selectone('SELECT * FROM ddl_info WHERE id=?',[ddl_id]).fetchone()
        if remaining is not None:raise ValueError('DDL entry changed; removal was not confirmed')
    if receipt is None:raise ValueError('DDL removal proof unavailable')
    if receipt['handoff_phase']=='queued' and owner['phase']=='queued':
        cancelled=dict(owner,phase='released',reason='Operator removed pending DDL handoff',updated_at=time.time())
        if not journal.replace('handoff',iid,owner,cancelled):
            raise ValueError('DDL handoff changed; removal requires review')
        owner=cancelled
    if journal.get('handoff',iid)!=owner:
        raise ValueError('DDL handoff changed; removal requires review')
    if receipt['phase']=='prepared':
        if not journal.replace('ddl_handoff_removal',ddl_id,receipt,dict(receipt,phase='removed')):
            raise ValueError('DDL removal state changed; refresh before retrying')
    complete=dict(receipt,phase='removed')
    if journal.get('ddl_handoff_removal',ddl_id)!=complete or journal.get('handoff',iid)!=owner:
        raise ValueError('DDL removal acknowledgement changed; review required')
    if db.DBConnection().selectone('SELECT * FROM ddl_info WHERE id=?',[ddl_id]).fetchone() is not None:
        raise ValueError('DDL entry reappeared; review required')
    message=('DDL entry removed. Pending NZB handoff cancelled before submission.'
             if receipt['handoff_phase']=='queued' else
             'DDL entry removed. The NZB download continues; its handoff reservation is retained.')
    return json.dumps({'status':True,'message':message})


def guard_requeue(function):
    @wraps(function)
    def wrapped(self,mode,id=None,issueid=None):
        from mylar import db,queue_control
        import cherrypy
        # Match request_handoff/sender lock order, including the missing-row
        # acknowledgement recovery case, whose issue is retained in the receipt.
        raw=db.DBConnection().selectone('SELECT * FROM ddl_info WHERE id=?',[id]).fetchone() if id else None
        receipt=store().get('ddl_handoff_removal',id) if id and mode=='remove' else None
        iid=str(raw['issueid']) if raw else (receipt.get('issueid') if type(receipt) is dict else issueid)
        with issue_lock(iid),queue_control._LOCK,LOCK:
            row=db.DBConnection().selectone('SELECT * FROM ddl_info WHERE id=?',[id]).fetchone() if id else None
            if row is not None and str(row['issueid'])!=str(iid):
                raise cherrypy.HTTPError(409,'DDL entry changed; refresh before retrying')
            owner=reservation(iid)
            if mode=='remove' and id and (receipt is not None or owner or (row is not None and row['status']=='NZB handoff')):
                try:return remove_handoff_ddl(id,row)
                except ValueError as exc:raise cherrypy.HTTPError(409,str(exc)) from None
            if owner or import_owner(iid) or dispatch_owner(iid):
                raise cherrypy.HTTPError(409,'This issue is reserved for NZB handoff; review it in Activity')
            return function(self,mode,id=id,issueid=issueid)
    return wrapped


def safe_queue_item(item,queue):
    try:return queue_item(item,queue)
    except Exception:
        queue.put(item)
        emit('intake','Workflow state unavailable; queued search retained')
        time.sleep(5)
        return True


def force_process(function):
    @wraps(function)
    def wrapped(self,**kwargs):
        import mylar
        command=kwargs.get('workflow_command')
        handoff=kwargs.get('publication_handoff')
        guided=kwargs.get('guided_handoff')
        if command and handoff is None:
            from mylar import native_writers
            if native_writers.publication_mode():
                self.data=self._failureResponse('Typed guided handoff required');return
        if guided is not None and (not command or handoff is None):
            self.data=self._failureResponse('Exact guided publication handoff required');return
        if (command or handoff is not None) and (not mylar.CONFIG.API_ENABLED or self.apikey!=mylar.CONFIG.API_KEY or 'apc_version' in kwargs):
            self.data=self._failureResponse('Primary API key and queue submission required');return
        try:
            proof=None
            if handoff is not None:
                if getattr(_CONTEXT,'publication_handoff',None) is not None:
                    raise ValueError('Nested publication handoff refused')
                from mylar import publication_native
                proof=publication_native.import_handoff(handoff,kwargs)
                if command:
                    if not isinstance(guided,str) or not 0<len(guided.encode())<=2048:
                        raise ValueError('Exact guided command binding required')
                    binding=publication_native.guard.decode_json(guided)
                    fields={'id','source_token','version','issueid','comicid'}
                    row=store().get('command',command)
                    if (not isinstance(binding,dict) or set(binding)!=fields or binding['id']!=command
                            or not all(isinstance(binding[key],str) for key in fields)
                            or not re.fullmatch('[a-f0-9]{32}',binding['id'])
                            or not re.fullmatch('[a-f0-9]{32}',binding['source_token'])
                            or not re.fullmatch('[a-f0-9]{64}',binding['version'])
                            or not row or any(binding[key]!=row.get(key) for key in fields)
                            or row['phase']!='queued' or row.get('dispatched')
                            or binding['issueid']!=proof['owner']['issueid']
                            or binding['comicid']!=proof['owner']['parentcomicid']):
                        raise ValueError('Guided command changed or already attempted')
                    admit_import(binding['issueid'],command)
                # This record is an at-most-once attempt, never correction
                # authority. Keep it outside the protected publication namespace.
                with store().connection() as database:
                    if database.execute("SELECT count(*) FROM records WHERE kind='worker_import_attempt'").fetchone()[0]>=4096:
                        raise ValueError('Import attempt history requires retention review')
                    if database.execute("SELECT 1 FROM records WHERE kind='worker_import_attempt' AND key=?",(proof['token'],)).fetchone():
                        raise ValueError('Import handoff already attempted')
                    for row in database.execute("SELECT value FROM records WHERE kind='worker_import_attempt'"):
                        previous=json.loads(row[0])
                        if not isinstance(previous,dict) or set(previous)!=set(proof):
                            raise ValueError('Import attempt history is malformed')
                        previous_owner=publication_native.guard.exact_owner(previous.get('owner'))
                        if previous_owner==proof['owner']:
                            raise ValueError('Native owner already has an import attempt requiring review')
                    database.execute('INSERT INTO records VALUES (?,?,?,?)',
                        ('worker_import_attempt',proof['token'],json.dumps(proof),time.time()))
                if command:
                    from mylar import queue_control
                    with issue_lock(binding['issueid']),queue_control._LOCK,LOCK:
                        current=store().get('command',command)
                        if current!=row:raise ValueError('Guided command changed before claim')
                        admit_import(binding['issueid'],command)
                        current.update(phase='claimed',updated_at=time.time())
                        store().set('command',command,current)
            if proof is None:return function(self,**kwargs)
            _CONTEXT.publication_handoff=proof
            try:return function(self,**kwargs)
            finally:_CONTEXT.publication_handoff=None
        except ValueError:
            self.data=self._failureResponse('Issue is reserved or import submission needs review')
    return wrapped


def state_health():
    try:
        store().get('policy','current')
        result = {'valid':True,'observer_errors':_OBSERVER_ERRORS,'intake':intake(),'ddl_paused':policy()['ddl_paused'],'publication_handoff':1,'maintenance_handoff':1,'guided_handoff':1,'maintenance_reports':1}
        try:
            from mylar import publication_archive_diagnostics as diagnostics
            from mylar import publication_archive_repair as archive_repair
        except ImportError:
            pass
        else:
            if all(callable(getattr(module, name, None)) for module, name in (
                    (diagnostics, 'diagnose'), (diagnostics, 'public_summary'),
                    (diagnostics, 'display'), (archive_repair, 'classify'),
                    (archive_repair, 'dispatch'))):
                result['archive_diagnostics'] = 1
        try:
            from mylar import api, combined_publication, publication_conversion
            from mylar.publication_transaction import closed_supplement
        except ImportError:
            return result
        if (callable(getattr(api.Api, '_combinedPublication', None))
                and callable(getattr(combined_publication, 'execute', None))
                and callable(closed_supplement)):
            result['combined_publication'] = 1
        if (callable(getattr(api.Api, '_commitConvertedArchive', None))
                and callable(getattr(api.Api, '_convertedArchiveStatus', None))
                and callable(getattr(publication_conversion, 'commit', None))
                and callable(getattr(publication_conversion, 'status', None))):
            result['owned_conversion'] = 1
        try:
            from mylar import publication_reconcile
        except ImportError:
            pass
        else:
            if (callable(getattr(api.Api, '_commitRetainedRepeat', None))
                    and callable(getattr(api.Api, '_retainedRepeatStatus', None))
                    and callable(getattr(publication_reconcile, 'commit', None))
                    and callable(getattr(publication_reconcile, 'status', None))):
                result['retained_repeat'] = 1
        try:
            from mylar import combined_cleanup
        except ImportError:
            pass
        else:
            if (result.get('combined_publication') == 1
                    and callable(getattr(combined_cleanup, 'clean', None))
                    and callable(getattr(combined_cleanup, 'retired_supplement', None))
                    and callable(getattr(combined_cleanup, 'resolve', None))):
                result['combined_cleanup'] = 1
        try:
            from mylar import publication_derivative, publication_lineage, library_metadata
        except ImportError:
            pass
        else:
            if (callable(getattr(api.Api, '_commitReviewedDerivative', None))
                    and callable(getattr(api.Api, '_reviewedDerivativeStatus', None))
                    and callable(getattr(publication_derivative, 'publish', None))
                    and callable(getattr(publication_derivative, 'status', None))
                    and callable(getattr(publication_lineage, 'prepare', None))
                    and callable(getattr(library_metadata, 'reviewed_derivative', None))):
                result['reviewed_derivative'] = 1
        return result
    except Exception:return {'valid':False,'observer_errors':_OBSERVER_ERRORS}


def release_failed(issueid):
    """Called only after authenticated native failure processing verifies a release."""
    from mylar import queue_control
    with issue_lock(issueid),queue_control._LOCK,LOCK:
        row=reservation(issueid)
        if row and row['phase']=='accepted':set_handoff(row,'failed','Accepted NZB failed verification; native replacement search allowed')
        held=dispatch_owner(issueid)
        if held and held['phase']=='accepted':store().set('dispatch',str(issueid),dict(held,phase='failed'))
