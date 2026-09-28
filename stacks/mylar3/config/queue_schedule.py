"""Choose the next queued transfer without changing the active download."""
import time


def choose(items, rows, providers, mode, preferred, last, now, ages=None):
    ages=ages or {str(item.get("id")):index for index,item in enumerate(items) if isinstance(item,dict)}
    if 'exit' in items:
        return items.index('exit')
    eligible=[]
    for index,item in enumerate(items):
        if not isinstance(item,dict):
            continue
        row=rows.get(str(item.get('id')))
        if not row or row['status']!='Queued':
            continue
        provider=str(item.get('link_type') or 'GC-Main')
        if providers.get(provider,{}).get('until',0)>now:
            continue
        pack=str(row.get('pack')).lower() in ('1','true')
        group=('pack' if pack else 'single')
        wanted=('single' if mode=='singles' else 'pack' if mode=='packs' else
                'single' if mode=='alternate' and last=='pack' else 'pack' if mode=='alternate' else '')
        eligible.append(((str(item['id'])!=preferred, bool(wanted and group!=wanted), -ages[str(item['id'])] if mode=='newest' else ages[str(item['id'])], index),index))
    return min(eligible)[1] if eligible else None


def arrival_order(items):
    from mylar import workflow
    from mylar.workflow_store import LOCK
    with LOCK:
        record=workflow.store().get('meta','ddl_arrivals',{'next':0,'ids':{}})
        changed=False
        for item in items:
            if isinstance(item,dict) and str(item.get('id')) not in record['ids']:
                record['ids'][str(item['id'])]=record['next'];record['next']+=1;changed=True
        if changed:workflow.store().set('meta','ddl_arrivals',record)
        return record['ids']


def take(queue):
    from mylar import db,workflow,queue_control
    with queue.mutex:
        items=list(queue.queue)
    if 'exit' in items:
        index=items.index('exit')
    else:
        ages=arrival_order(items)
        rules=workflow.policy()
        if rules['ddl_paused']:
            return None
        rows={str(r['id']):dict(r) for r in db.DBConnection().select("SELECT id,pack,status FROM ddl_info WHERE status='Queued'")}
        with queue_control._LOCK:
            providers=dict(queue_control.store().data['providers'])
        preferred=workflow.store().get('meta','ddl_next','')
        index=choose(items,rows,providers,rules['ddl_order'],preferred,
                     workflow.store().get('meta','ddl_last_kind',''),time.time(),ages)
        if index is None:
            # Drop obsolete queue entries through the existing begin() check,
            # while keeping live cooldown entries queued without spending attempts.
            index=next((i for i,r in enumerate(items) if isinstance(r,dict) and str(r.get('id')) not in rows),None)
        if index is None:
            return None
    selected=items[index]
    with queue.not_full:
        # Another caller may have added/removed entries since the snapshot.
        position=next((i for i,r in enumerate(queue.queue) if r is selected),None)
        if position is None:
            return None
        del queue.queue[position]
        queue.not_full.notify()
    return selected


def started(item):
    """Consume priority only after cooldown and intake admission succeeds."""
    from mylar import db,workflow
    from mylar.workflow_store import LOCK
    row=db.DBConnection().selectone('SELECT pack FROM ddl_info WHERE id=?',[item['id']]).fetchone()
    with LOCK:
        workflow.store().set('meta','ddl_last_kind','pack' if row and str(row['pack']).lower() in ('1','true') else 'single')
        if workflow.store().get('meta','ddl_next','')==str(item['id']):
            workflow.store().delete('meta','ddl_next')


def next_item(key):
    from mylar import db,workflow
    from mylar.workflow_store import ddl_identifier
    key=ddl_identifier(key)
    row=db.DBConnection().selectone("SELECT id FROM ddl_info WHERE id=? AND status='Queued'",[key]).fetchone()
    if not row:
        raise ValueError('Choose a queued download; the active item is unchanged')
    workflow.store().set('meta','ddl_next',key)
    workflow.emit('download','Queued item marked to download next',key='ddl-next:'+key)
    return {'next':key}
