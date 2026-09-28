"""Choose the next queued transfer without changing the active download."""
import time
from collections import deque
from datetime import date
from decimal import Decimal, InvalidOperation


def release_day(row):
    for field in ('ReleaseDate', 'IssueDate'):
        try:
            return date.fromisoformat(str(row.get(field))).toordinal()
        except ValueError:
            pass
    return None


def release_dates(rows, database):
    """Use issue release dates, never the series start year or queue timestamp."""
    from mylar.queue_control import pack_numbers
    targets = {str(row.get('comicid')) for row in rows.values()}
    linked, series = {}, {}
    for table in ('issues', 'annuals'):
        for found in database.select('SELECT IssueID,ComicID,Issue_Number,ReleaseDate,IssueDate FROM ' + table +
                                     ' WHERE ComicID IN (SELECT comicid FROM ddl_info WHERE status=\'Queued\')'):
            issue = dict(found)
            if str(issue['ComicID']) not in targets:
                continue
            day = release_day(issue)
            linked[str(issue['IssueID'])] = day
            if table == 'issues':
                try:
                    number = Decimal(str(issue['Issue_Number']))
                    if number.is_finite() and number == number.to_integral_value():
                        series.setdefault(str(issue['ComicID']), {}).setdefault(int(number), []).append(day)
                except InvalidOperation:
                    pass
    for row in rows.values():
        days = []
        if str(row.get('pack')).lower() in ('1', 'true'):
            numbers = pack_numbers(row.get('issues'))
            if numbers:
                known = series.get(str(row.get('comicid')), {})
                days = [known[n][0] for n in numbers if len(known.get(n, [])) == 1 and known[n][0]]
        if not days and linked.get(str(row.get('issueid'))):
            days = [linked[str(row['issueid'])]]
        row['release_oldest'] = min(days) if days else None
        row['release_newest'] = max(days) if days else None


def order_key(row, mode, age):
    if mode in ('release_oldest', 'release_newest'):
        day = row.get(mode)
        return (day is None, -day if day and mode == 'release_newest' else day or 0, age)
    return (False, -age if mode == 'newest' else age, age)


def choose(items, rows, providers, mode, preferred, last, now, ages=None, kind=None):
    ages=ages or {str(item.get("id")):index for index,item in enumerate(items) if isinstance(item,dict)}
    if 'exit' in items:
        return items.index('exit')
    kind = kind or (mode if mode in ('singles', 'packs', 'alternate') else 'mixed')
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
        wanted=('single' if kind=='singles' else 'pack' if kind=='packs' else
                'single' if kind=='alternate' and last=='pack' else 'pack' if kind=='alternate' else '')
        eligible.append(((str(item['id'])!=preferred, bool(wanted and group!=wanted), order_key(row, mode, ages[str(item['id'])]), index),index))
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


def projected_order(items, rows, providers, mode, preferred, last, now, ages, kind=None):
    """Project admission order without consuming priority or changing the queue."""
    kind = kind or (mode if mode in ('singles', 'packs', 'alternate') else 'mixed')
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
        item_kind = 'pack' if str(row.get('pack')).lower() in ('1', 'true') else 'single'
        groups[blocked].append(((order_key(row, mode, age), index), key, item_kind))
    result = []
    for blocked, group in groups.items():
        group.sort()
        priority = next((row for row in group if row[1] == preferred), None)
        if priority:
            group.remove(priority)
            result.append((priority[1], blocked))
            last = priority[2]
        if kind == 'alternate':
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
            wanted = {'singles': 'single', 'packs': 'pack'}.get(kind)
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
        rules = workflow.policy()
        mode = rules['ddl_order']
        preferred = store.get('meta', 'ddl_next', '')
        last = store.get('meta', 'ddl_last_kind', '')
    with queue_control._LOCK:
        providers = {key: dict(value) for key, value in queue_control.store().data['providers'].items()}
    rows = {str(row['id']): dict(row) for row in downloads}
    if mode in ('release_oldest', 'release_newest'):
        from mylar import db
        release_dates(rows, db.DBConnection())
    result = {key: {'sort': 0 if row['status'] == 'Downloading' else 1000000000 if row['status'] == 'Queued' else 2000000000,
                    'label': 'Active' if row['status'] == 'Downloading' else 'Not scheduled' if row['status'] == 'Queued' else ''}
              for key, row in rows.items()}
    for position, (key, blocked) in enumerate(projected_order(items, rows, providers, mode, preferred, last, time.time(), ages, rules.get('ddl_kind')), 1):
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
        database = db.DBConnection()
        rows={str(r['id']):dict(r) for r in database.select("SELECT id,pack,status,comicid,issueid,issues FROM ddl_info WHERE status='Queued'")}
        if rules['ddl_order'] in ('release_oldest', 'release_newest'):
            release_dates(rows, database)
        with queue_control._LOCK:
            providers=dict(queue_control.store().data['providers'])
        preferred=workflow.store().get('meta','ddl_next','')
        index=choose(items,rows,providers,rules['ddl_order'],preferred,
                     workflow.store().get('meta','ddl_last_kind',''),time.time(),ages,rules.get('ddl_kind'))
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
