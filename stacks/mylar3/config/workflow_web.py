"""Validated browser actions and primary-key worker command exchange."""
import hmac
import json
import re
import secrets
import time
import uuid

from mylar import workflow
from mylar.workflow_store import LOCK, identifier, label
HEX32=re.compile(r'[0-9a-f]{32}\Z');HEX64=re.compile(r'[0-9a-f]{64}\Z')
REASONS={'':'','stale_source':'Source proposal changed; refresh before choosing',
         'changed_source':'Source changed after confirmation','issue_unavailable':'Issue is no longer eligible',
         'source_unavailable':'Source is unavailable or unsafe','unconfirmed':'Submission needs review'}


def require_login():
    import cherrypy
    if not getattr(cherrypy.request,'login',None):raise cherrypy.HTTPError(401,'Sign in to use workflow controls')


def csrf():
    import cherrypy
    require_login()
    if cherrypy.session.get('workflow_user')!=cherrypy.request.login:
        cherrypy.session['workflow_user']=cherrypy.request.login
        cherrypy.session['workflow_csrf']=secrets.token_urlsafe(32)
    return cherrypy.session['workflow_csrf']


def protect(token):
    import cherrypy
    require_login()
    if cherrypy.request.method!='POST':raise cherrypy.HTTPError(405,'Use POST for workflow changes')
    if not isinstance(token,str) or not hmac.compare_digest(csrf(),token):raise cherrypy.HTTPError(403,'Refresh the page before making changes')


def clean_text(value,limit=200):
    if not isinstance(value,str) or len(value)>limit or any(ord(c)<32 for c in value) or '://' in value:
        raise ValueError('Invalid display field')
    return value


def report_guidance(payload):
    if not isinstance(payload,str) or len(payload)>180000:raise ValueError('Guidance report too large')
    rows=json.loads(payload)
    if not isinstance(rows,list) or len(rows)>50:raise ValueError('Too many proposals')
    validated=[]
    for row in rows:
        if not isinstance(row,dict) or not HEX32.fullmatch(str(row.get('source_token',''))) or not HEX64.fullmatch(str(row.get('version',''))):raise ValueError('Invalid source identity')
        name=clean_text(row.get('name'),255)
        if '/' in name or '\\' in name:raise ValueError('Only filenames may be reported')
        choices=row.get('candidates');evidence=row.get('evidence')
        if not isinstance(choices,list) or len(choices)>8 or not isinstance(evidence,list) or len(evidence)>6:raise ValueError('Invalid candidate report')
        safe={'source_token':row['source_token'],'version':row['version'],'name':name,'candidates':[],
              'evidence':[clean_text(v) for v in evidence],'reported_at':time.time(),'requires_review':row.get('requires_review') is True}
        for c in choices:
            if not identifier(c.get('issueid')) or not identifier(c.get('comicid')):raise ValueError('Invalid candidate issue')
            item={k:clean_text(str(c.get(k,''))) for k in ('issueid','comicid','title','year','number','status')}
            for k in ('agrees','conflicts'):
                if not isinstance(c.get(k),list) or len(c[k])>6:raise ValueError('Invalid evidence')
                item[k]=[clean_text(v) for v in c[k]]
            safe['candidates'].append(item)
        scope=row.get('alias_scope')
        if scope:
            series=clean_text(scope.get('series'));year=clean_text(scope.get('year'))
            if not series or not re.fullmatch(r'(?:19|20)\d{2}',year):raise ValueError('Invalid alias scope')
            safe['alias_scope']={'series':series,'year':year}
        validated.append(safe)
    with LOCK:
        for row in validated:workflow.store().set('proposal',row['source_token'],row)
        workflow.store().set('meta','current_proposals',[r['source_token'] for r in validated])
    return len(validated)


def commands():
    store=workflow.store()
    rows=store.active('command',workflow.IMPORT_HELD)
    offset=store.get('meta','command_cursor',0) % max(1,len(rows))
    page=(rows[offset:]+rows[:offset])[:50]
    store.set('meta','command_cursor',(offset+len(page)) % max(1,len(rows)))
    return {'commands':page,
            'aliases':[r for r in store.all('alias') if r['enabled']][:200]}


def confirm_import(token,version,issueid,save_alias=False,confirmation=None):
    from mylar import db,queue_control
    with workflow.issue_lock(issueid),queue_control._LOCK,LOCK:
        store=workflow.store();proposal=store.get('proposal',token)
        if not proposal or proposal['version']!=version or time.time()-proposal['reported_at']>900:
            raise ValueError('Source report changed or is stale; refresh before confirming')
        if proposal.get('requires_review') and confirmation!='checked':raise ValueError('Check the downloader and processing queues before replacing a previous import attempt')
        candidate=next((r for r in proposal['candidates'] if r['issueid']==issueid),None)
        if not candidate:raise ValueError('Choose an issue from the current candidates')
        row=db.DBConnection().selectone('SELECT ComicID,Status FROM issues WHERE IssueID=?',[issueid]).fetchone()
        if not row or str(row['ComicID'])!=candidate['comicid'] or row['Status']=='Downloaded':raise ValueError('Issue is no longer eligible')
        existing=store.active('command',workflow.IMPORT_HELD)
        for r in existing:
            if r['source_token']==token and r['version']==version:
                if r['issueid']!=issueid or r['save_alias']!=save_alias:raise ValueError('This source already has a different pending choice')
                return r
            if r['issueid']==issueid:raise ValueError('Another source already has a pending choice for this issue')
        workflow.admit_import(issueid)
        scope=proposal.get('alias_scope')
        if save_alias:
            if (not scope or scope['year']!=candidate['year'] or not any(v in candidate['agrees'] for v in ('filename issue','metadata issue'))
                    or any('issue' in v.lower() for v in candidate['conflicts'])):
                raise ValueError('This selection lacks consistent issue/year evidence for a reusable alias')
        released=store.get('released_source',token,{})
        reviewed=proposal.get('requires_review') or released.get('version')==version
        command={'reviewed_source':bool(reviewed),'id':uuid.uuid4().hex,'source_token':token,'version':version,'issueid':issueid,'comicid':candidate['comicid'],
                 'save_alias':save_alias,'phase':'queued','reason':'Waiting for maintenance worker','created_at':time.time()}
        store.set('command',command['id'],command)
        if save_alias:store.set('command_scope',command['id'],scope)
        workflow.emit('matching','Import choice queued for source verification',issueid=issueid,comicid=candidate['comicid'],name=proposal['name'])
        return command


def acknowledge(command_id,phase,reason=''):
    if phase not in ('claimed','submitted','review','rejected','confirmed') or reason not in REASONS:raise ValueError('Invalid acknowledgement')
    from mylar import queue_control
    initial=workflow.store().get('command',command_id)
    if not initial:raise ValueError('Unknown import command')
    with workflow.issue_lock(initial['issueid']),queue_control._LOCK,LOCK:
        store=workflow.store();row=store.get('command',command_id)
        if not row:raise ValueError('Unknown import command')
        allowed={'queued':{'claimed','rejected','review'},'claimed':{'claimed','submitted','review','rejected','confirmed'},
                 'submitted':{'submitted','review','confirmed'},'review':{'review','confirmed'},'confirmed':{'confirmed'},'rejected':{'rejected'}}
        if phase not in allowed[row['phase']]:raise ValueError('Import command transition requires review')
        if phase=='claimed':workflow.admit_import(row['issueid'],command_id)
        if row['phase']!=phase:
            workflow.emit('matching','Guided import '+phase,issueid=row['issueid'],comicid=row['comicid'])
        row.update(phase=phase,reason=REASONS[reason],updated_at=time.time());store.set('command',command_id,row)
        if phase=='confirmed' and row['save_alias']:
            scope=store.get('command_scope',command_id)
            if scope:
                rule=dict(scope,id=command_id,comicid=row['comicid'],enabled=True)
                # Replay must never re-enable an alias the operator disabled.
                store.create('alias',command_id,rule)
        return row


def resolve_handoff(issueid,resolution,confirmation):
    from mylar import queue_control,db
    if confirmation!='checked' or resolution not in ('keep','restore','import'):raise ValueError('Check the downloader and post-processing before resolving this hold')
    with workflow.issue_lock(issueid),queue_control._LOCK,LOCK:
        row=workflow.reservation(issueid)
        if not row or row['phase'] not in ('review','accepted'):raise ValueError('Only submitted handoffs can be reconciled')
        if resolution=='keep':return workflow.set_handoff(row,'accepted','Operator confirmed NZB in downloader; DDL held')
        raw=db.DBConnection().selectone('SELECT Status FROM issues WHERE IssueID=?',[issueid]).fetchone()
        if not raw or raw['Status']=='Downloaded' or workflow.native_busy(issueid,True):raise ValueError('Issue still has download or processing work')
        if resolution=='import':
            db.DBConnection().upsert('ddl_info',{'status':'Source review'},{'id':row['ddl_id']})
            return workflow.set_handoff(row,'source-ready','Operator selected existing archive for guided import')
        workflow.restore_ddl(row)
        return workflow.store().get('handoff',issueid)


def resolve_dispatch(issueid,resolution,confirmation):
    from mylar import queue_control,db
    if confirmation!='checked' or resolution not in ('keep','retry','import'):
        raise ValueError('Check the downloader and processing queues before resolving this hold')
    with workflow.issue_lock(issueid),queue_control._LOCK,LOCK:
        row=workflow.dispatch_owner(issueid)
        if not row or row['phase'] not in ('sending','review','accepted'):raise ValueError('Only uncertain submissions can be reconciled')
        if resolution in ('retry','import'):
            current=db.DBConnection().selectone('SELECT Status FROM issues WHERE IssueID=?',[issueid]).fetchone()
            if not current or current['Status']=='Downloaded' or workflow.native_busy(issueid,True):
                raise ValueError('Issue is imported or still has download or processing work')
            if resolution=='retry':db.DBConnection().upsert('issues',{'Status':'Wanted'},{'IssueID':issueid})
        row.update(phase='accepted' if resolution=='keep' else 'released',reason='Downloader checked by operator')
        workflow.store().set('dispatch',issueid,row)
        if resolution=='retry':workflow.defer_search(issueid)
        return row


def resolve_import(command_id,confirmation):
    from mylar import db,queue_control
    if confirmation!='checked':raise ValueError('Check the downloader and processing queues before releasing this import')
    row=workflow.store().get('command',command_id)
    if not row:raise ValueError('Unknown import command')
    with workflow.issue_lock(row['issueid']),queue_control._LOCK,LOCK:
        row=workflow.store().get('command',command_id)
        issue=db.DBConnection().selectone('SELECT Status FROM issues WHERE IssueID=?',[row['issueid']]).fetchone()
        if row['phase'] not in ('queued','review') or not issue or issue['Status']=='Downloaded' or workflow.native_busy(row['issueid'],True):
            raise ValueError('Import is active or already downloaded; retain the hold until verified')
        row.update(phase='rejected',reason='Operator checked and released import hold',updated_at=time.time())
        workflow.store().set('command',command_id,row)
        workflow.store().set('released_source',row['source_token'],{'version':row['version']})
        workflow.emit('matching','Operator released import hold; originals and receipts retained',issueid=row['issueid'])
        return row


def action(name,values):
    if name=='resolve_import':return resolve_import(values.get('command_id'),values.get('confirmation'))
    if name=='resolve_dispatch':return resolve_dispatch(identifier(values.get('issueid')),values.get('resolution'),values.get('confirmation'))
    if name=='policy':
        result=workflow.set_policy(json.loads(values.get('values','{}')))
        workflow.store().delete('intake','current');return result
    if name=='handoff':return workflow.request_handoff(values.get('ddl_id'))
    if name=='resolve_handoff':return resolve_handoff(identifier(values.get('issueid')),values.get('resolution'),values.get('confirmation'))
    if name=='confirm_import':return confirm_import(values.get('source_token'),values.get('version'),identifier(values.get('issueid')),values.get('save_alias')=='true',values.get('confirmation'))
    if name=='disable_alias':
        with LOCK:
            row=workflow.store().get('alias',values.get('alias_id'))
            if not row:raise ValueError('Alias no longer exists')
            row['enabled']=False;workflow.store().set('alias',row['id'],row);return row
    raise ValueError('Unknown workflow action')


def snapshot(issueid='',stage='',before=0):
    from mylar import db,cooldown_health
    store=workflow.store();database=db.DBConnection()
    proposals=[store.get('proposal',k) for k in store.get('meta','current_proposals',[])]
    candidates=database.select("SELECT id,series,issueid FROM ddl_info WHERE status='Queued' AND (pack IS NULL OR pack IN ('0','False','false')) ORDER BY updated_date LIMIT 100")
    return {'checked_at':time.time(),'csrf':csrf(),'events':store.events(issueid,stage,before),
            'policy':workflow.policy(),'intake':workflow.intake(),'cooldown':cooldown_health.snapshot(database),
            'dispatches':store.active('dispatch',workflow.DISPATCH_HELD),'handoffs':store.active('handoff',workflow.HELD)+[r for r in store.all('handoff',100) if r['phase'] not in workflow.HELD],'ddl_candidates':[{'id':str(r['id']),'name':label(r['series']),'issueid':identifier(r['issueid'])} for r in candidates],
            'proposals':[r for r in proposals if r],'commands':store.active('command',workflow.IMPORT_HELD)+[r for r in store.all('command',100) if r['phase'] not in workflow.IMPORT_HELD],'aliases':store.all('alias',200),
            'observer_errors':workflow._OBSERVER_ERRORS}
