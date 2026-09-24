"""Native workflow observations, durable handoffs and intake admission."""
from functools import wraps
import inspect
from pathlib import Path
import shutil
import threading
import time
import uuid

from mylar.workflow_store import Store, LOCK, identifier, label

_STORE=None
_CONTEXT=threading.local()
_STARTED=False
_LAST_TICK=0
_OBSERVER_ERRORS=0
_ISSUE_LOCKS={}
_ISSUE_GUARD=threading.Lock()
_DEFAULTS={'auto_handoff':False,'handoff_hours':2,'intake_enabled':True,
           'queue_high':50,'queue_low':20,'free_stop_gib':5,'free_resume_gib':8}
IMPORT_HELD={'queued','claimed','submitted','review'}
DISPATCH_HELD={'sending','review','accepted'}
HELD={'queued','searching','dispatching','accepted','review'}


def issue_lock(issueid):
    with _ISSUE_GUARD:return _ISSUE_LOCKS.setdefault(str(issueid),threading.RLock())


def store():
    global _STORE
    if _STORE is None:
        import mylar
        with LOCK:
            if _STORE is None:_STORE=Store(mylar.DATA_DIR)
    return _STORE


def emit(stage,outcome,**kwargs):
    global _OBSERVER_ERRORS
    try:store().event(stage,outcome,**kwargs)
    except Exception:_OBSERVER_ERRORS+=1


def policy():return dict(_DEFAULTS,**store().get('policy','current',{}))


def set_policy(values):
    value=policy()
    if not isinstance(values,dict) or set(values)-set(_DEFAULTS):raise ValueError('Unknown policy setting')
    for k,v in values.items():
        if isinstance(_DEFAULTS[k],bool):
            if not isinstance(v,bool):raise ValueError('Expected an enabled or disabled setting')
        elif not isinstance(v,int) or isinstance(v,bool):raise ValueError('Expected whole-number thresholds')
        value[k]=v
    if not (1<=value['handoff_hours']<=168 and 1<=value['queue_low']<value['queue_high']<=1000
            and 1<=value['free_stop_gib']<value['free_resume_gib']<=10240):
        raise ValueError('Thresholds must be ordered and within the displayed limits')
    store().set('policy','current',value)
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
    if reservation(issueid) or dispatch_owner(issueid) or import_owner(issueid,command_id) or native_busy(issueid):
        raise ValueError('Another download or processing task owns this issue')


def processing_put(queue,item,command_id=None):
    """Atomic final admission, with a durable receipt before a guided queue write."""
    from mylar import queue_control
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
            row.update(dispatched=True,updated_at=time.time());store().set('command',command_id,row)
        elif import_owner(iid) or (reservation(iid) and reservation(iid)['phase'] not in ('accepted','review')):
            raise ValueError('Issue is reserved for another workflow')
        queue.put(item)


def defer_search(issueid,comicid=None):
    iid=identifier(issueid)
    if iid:
        from mylar import db
        row=db.DBConnection().selectone('SELECT ComicID FROM issues WHERE IssueID=?',[iid]).fetchone()
        cid=identifier(comicid) or (identifier(row['ComicID']) if row else '')
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


def eligible(ddl_id,allow_held=False):
    from mylar import db
    database=db.DBConnection()
    raw=database.selectone('SELECT * FROM ddl_info WHERE id=?',[ddl_id]).fetchone()
    if not raw:raise ValueError('DDL entry no longer exists')
    row=dict(raw);iid=identifier(row.get('issueid'));cid=identifier(row.get('comicid'))
    if not iid or not cid or str(row.get('pack')).lower() not in ('0','false','none',''):
        raise ValueError('Only regular single-issue downloads can be switched')
    if row.get('site')!='DDL(GetComics)':raise ValueError('This download source cannot be switched')
    allowed=('Queued','NZB handoff') if allow_held else ('Queued',)
    if row['status'] not in allowed:raise ValueError('Only waiting, inactive DDL entries can be switched')
    issue=database.selectone('SELECT Status,ComicID,Location FROM issues WHERE IssueID=?',[iid]).fetchone()
    if not issue or str(issue['ComicID'])!=cid or issue['Status']=='Downloaded' or issue['Location']:
        raise ValueError('Issue is missing, already downloaded, or needs library review')
    others=database.select("SELECT id FROM ddl_info WHERE issueid=? AND id!=? AND status IN ('Queued','Downloading','NZB handoff','Completed')",[iid,ddl_id])
    sending=store().get('dispatch',iid,{})
    if others or busy_issue(iid) or import_owner(iid) or sending.get('phase') in DISPATCH_HELD:raise ValueError('Another download or processing task owns this issue')
    import mylar
    if iid in {str(k) for k in mylar.PACK_ISSUEIDS_DONT_QUEUE}:raise ValueError('This issue belongs to a queued pack')
    return row


def request_handoff(ddl_id):
    import mylar
    from mylar import queue_control,db,search
    preliminary=db.DBConnection().selectone('SELECT issueid FROM ddl_info WHERE id=?',[identifier(ddl_id)]).fetchone()
    if not preliminary:raise ValueError('DDL entry no longer exists')
    with issue_lock(preliminary['issueid']),queue_control._LOCK,LOCK:
        existing=reservation(preliminary['issueid'])
        if existing and existing['ddl_id']==str(ddl_id):return existing
        row=eligible(identifier(ddl_id));iid=str(row['issueid'])
        old=reservation(iid)
        if old:return old
        providers=search.provider_order()['prov_order']
        if not any(p.startswith('newznab:') or p.lower()=='experimental' for p in providers):
            raise ValueError('No enabled, unblocked NZB indexer is available')
        if not (mylar.USE_NZBGET or mylar.USE_SABNZBD):raise ValueError('Handoff requires NZBGet or SABnzbd')
        value={'id':uuid.uuid4().hex,'ddl_id':str(row['id']),'issueid':iid,'comicid':str(row['comicid']),
               'name':label(row['series']),'phase':'queued','created_at':time.time(),'reason':'Waiting for NZB search'}
        # Durable reservation precedes native status change; DDL begin checks both.
        store().set('handoff',iid,value)
        db.DBConnection().upsert('ddl_info',{'status':'NZB handoff'},{'id':row['id']})
        mylar.SEARCH_QUEUE.put({'issueid':iid,'comicid':value['comicid'],'workflow_handoff':value['id']})
        emit('handoff','Reserved for NZB-only search',issueid=iid,comicid=value['comicid'],name=value['name'])
        return value


def set_handoff(row,phase,reason):
    value=dict(row,phase=phase,reason=reason,updated_at=time.time())
    store().set('handoff',row['issueid'],value)
    emit('handoff',reason,issueid=row['issueid'],comicid=row['comicid'],name=row['name'])
    return value


def restore_ddl(row):
    import mylar
    from mylar import db,queue_control
    with queue_control._LOCK,LOCK:
        db.DBConnection().upsert('ddl_info',{'status':'Queued'},{'id':row['ddl_id']})
        set_handoff(row,'no-result','No NZB accepted; DDL queue restored')
        queue_control.recover(mylar.DDL_QUEUE)


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
            else:restore_ddl(current)
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
    global _STARTED,_LAST_TICK
    now=time.time()
    if now-_LAST_TICK<30:return
    _LAST_TICK=now
    try:
        from mylar import db
        if not _STARTED:
            with LOCK:
                for row in store().active('handoff',HELD):
                    if row['phase']=='dispatching':set_handoff(row,'review','Restart during downloader send; review required')
                    elif row['phase'] in ('queued','searching'):
                        row=set_handoff(row,'queued','Resuming reserved NZB search')
                        queue.put({'issueid':row['issueid'],'comicid':row['comicid'],'workflow_handoff':row['id']})
            _STARTED=True
        rows=db.DBConnection().select("SELECT IssueID,ComicID,ComicName FROM issues WHERE Status='Downloaded' AND COALESCE(Location,'')!=''")
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


def guard_requeue(function):
    @wraps(function)
    def wrapped(self,mode,id=None,issueid=None):
        from mylar import db,queue_control
        import cherrypy
        with queue_control._LOCK,LOCK:
            row=db.DBConnection().selectone('SELECT issueid FROM ddl_info WHERE id=?',[id]).fetchone() if id else None
            iid=str(row['issueid']) if row else issueid
            if reservation(iid) or import_owner(iid) or dispatch_owner(iid):raise cherrypy.HTTPError(409,'This issue is reserved for NZB handoff; review it in Activity')
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
        if command and (not mylar.CONFIG.API_ENABLED or self.apikey!=mylar.CONFIG.API_KEY or 'apc_version' in kwargs):
            self.data=self._failureResponse('Primary API key and queue submission required');return
        try:return function(self,**kwargs)
        except ValueError:
            self.data=self._failureResponse('Issue is reserved or import submission needs review')
    return wrapped


def state_health():
    try:
        store().get('policy','current')
        return {'valid':True,'observer_errors':_OBSERVER_ERRORS,'intake':intake()}
    except Exception:return {'valid':False,'observer_errors':_OBSERVER_ERRORS}


def release_failed(issueid):
    """Called only after authenticated native failure processing verifies a release."""
    from mylar import queue_control
    with issue_lock(issueid),queue_control._LOCK,LOCK:
        row=reservation(issueid)
        if row and row['phase']=='accepted':set_handoff(row,'failed','Accepted NZB failed verification; native replacement search allowed')
        held=dispatch_owner(issueid)
        if held and held['phase']=='accepted':store().set('dispatch',str(issueid),dict(held,phase='failed'))
