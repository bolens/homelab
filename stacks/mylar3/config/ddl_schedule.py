"""Choose the next queued transfer without changing the active download."""
import time
from collections import deque


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


def projected_order(items, rows, providers, mode, preferred, last, now, ages):
    """Project admission order without consuming priority or changing the queue."""
    groups = {False: [], True: []}
    seen = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        key = str(item.get('id'))
        row = rows.get(key)
        if key in seen or not row or row['status'] != 'Queued':
            continue
        seen.add(key)
        blocked = providers.get(str(item.get('link_type') or 'GC-Main'), {}).get('until', 0) > now
        age = ages.get(key, index)
        kind = 'pack' if str(row.get('pack')).lower() in ('1', 'true') else 'single'
        groups[blocked].append(((-age if mode == 'newest' else age, index), key, kind))
    result = []
    for blocked, group in groups.items():
        group.sort()
        priority = next((row for row in group if row[1] == preferred), None)
        if priority:
            group.remove(priority)
            result.append((priority[1], blocked))
            last = priority[2]
        if mode == 'alternate':
            singles = deque(row for row in group if row[2] == 'single')
            packs = deque(row for row in group if row[2] == 'pack')
            while singles or packs:
                selected = singles if last == 'pack' else packs
                if not selected:
                    selected = packs if singles is selected else singles
                row = selected.popleft()
                result.append((row[1], blocked))
                last = row[2]
        else:
            wanted = {'singles': 'single', 'packs': 'pack'}.get(mode)
            if wanted:
                group.sort(key=lambda row: row[2] != wanted)
            result.extend((row[1], blocked) for row in group)
    return result


def positions(downloads):
    import mylar
    from mylar import workflow, queue_control
    from mylar.workflow_store import LOCK
    with mylar.DDL_QUEUE.mutex:
        items = list(mylar.DDL_QUEUE.queue)
    with LOCK:
        store = workflow.store()
        record = store.get('meta', 'ddl_arrivals', {'next': 0, 'ids': {}})
        ages = dict(record['ids'])
        sequence = record['next']
        for item in items:
            if isinstance(item, dict) and str(item.get('id')) not in ages:
                ages[str(item['id'])] = sequence
                sequence += 1
        mode = workflow.policy()['ddl_order']
        preferred = store.get('meta', 'ddl_next', '')
        last = store.get('meta', 'ddl_last_kind', '')
    with queue_control._LOCK:
        providers = {key: dict(value) for key, value in queue_control.store().data['providers'].items()}
    rows = {str(row['id']): dict(row) for row in downloads}
    result = {key: {'sort': 0 if row['status'] == 'Downloading' else 1000000000 if row['status'] == 'Queued' else 2000000000,
                    'label': 'Active' if row['status'] == 'Downloading' else 'Not scheduled' if row['status'] == 'Queued' else ''}
              for key, row in rows.items()}
    for position, (key, blocked) in enumerate(projected_order(items, rows, providers, mode, preferred, last, time.time(), ages), 1):
        result[key] = {'sort': position, 'label': '#%s%s' % (position, ' · cooldown' if blocked else '')}
    return result


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
