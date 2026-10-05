"""Immediate alternate discovery and durable priority for replacement DDL mirrors."""
from functools import wraps
from contextvars import ContextVar

_RETRY = ContextVar("ddl_retry", default=None)


def preferred(links, priorities, upscaled):
    """Select only present, already filtered links in configured provider order."""
    groups = ('HD-Upscaled', 'HD-Digital', 'SD-Digital', 'normal') if upscaled else (
        'SD-Digital', 'normal', 'HD-Digital', 'HD-Upscaled')
    sites = {'main': ('download now', 'mirror download'), 'mega': ('mega',),
             'pixeldrain': ('pixeldrain',), 'mediafire': ('mediafire',)}
    for provider in priorities:
        for group in groups:
            for site in sites.get(provider, ()):
                name = group + ':' + site
                for link in links:
                    if link.get('site_type') == name:
                        return link
    return None


def excluded(site, failures):
    provider = {'main server':'GC-Main', 'download now':'GC-Main',
                'mirror download':'GC-Mirror', 'mega':'GC-Mega',
                'mediafire':'GC-Media', 'pixeldrain':'GC-Pixel'}.get(site.lower().strip())
    return provider in {value.replace('GC_Mirror', 'GC-Mirror') for value in failures}


def discovery(method):
    @wraps(method)
    def discover(self, id, mainlink, comicinfo=None, packinfo=None, link_type_failure=None):
        if not link_type_failure:
            return method(self, id, mainlink, comicinfo, packinfo, link_type_failure)
        from mylar import queue_control, db
        row = db.DBConnection().selectone('SELECT * FROM ddl_info WHERE id=?', [id]).fetchone()
        if (not row or row['status'] not in ('Queued', 'Downloading') or row['mainlink'] != mainlink
                or str(row['issueid']) != str(self.issueid) or str(row['comicid']) != str(self.comicid)):
            return {'success': False, 'cancelled': True}
        with queue_control._LOCK:
            state = queue_control.store()
            record = state.data['items'].get(str(id), {})
            failed = list(dict.fromkeys(list(link_type_failure) + record.get('failed_providers', [])))
            if record.get('attempts', 0) >= queue_control.ATTEMPT_LIMIT:
                return {'success': False, 'links_exhausted': failed}
            cooling = [name for name, value in state.data['providers'].items()
                       if value.get('until', 0) > state.clock() and name not in failed]
        # Native SQLite names the primary key ID. Row lookup ignores case, but
        # converting to dict does not. Keep the ownership snapshot canonical.
        token = _RETRY.set({name.lower(): row[name] for name in row.keys()})
        try:
            result = method(self, id, mainlink, comicinfo, packinfo, failed + cooling)
            if cooling and isinstance(result, dict) and 'links_exhausted' in result:
                # Temporary cooldown is not permanent exhaustion. Retain a replacement
                # in the queue when every remaining mirror is cooling; admission waits.
                result = method(self, id, mainlink, comicinfo, packinfo, failed)
            return result
        finally:
            _RETRY.reset(token)
    return discover


def persist(database, values, keys, failed):
    """Publish a retry only if the original record and issue ownership still agree."""
    if not failed:
        database.upsert('ddl_info', values, keys)
        return True
    from mylar import queue_control, workflow
    from mylar.workflow_store import LOCK
    previous = _RETRY.get()
    if not previous or str(previous['id']) != str(keys['id']):
        return False
    with queue_control._LOCK, LOCK:
        issueid = previous.get('issueid')
        if workflow.reservation(issueid) or workflow.import_owner(issueid) or workflow.dispatch_owner(issueid):
            return False
        # Preserve the original release's ownership and pack contract.
        values = dict(values)
        for key in ('comicid', 'issueid', 'pack', 'issues'):
            values[key] = previous.get(key)
        fields = ('id', 'status', 'link', 'mainlink', 'comicid', 'issueid')
        result = database.action('UPDATE ddl_info SET ' + ','.join(key+'=?' for key in values) +
                                 ' WHERE ' + ' AND '.join(key+' IS ?' for key in fields),
                                 list(values.values()) + [previous.get(key) for key in fields])
        if result is None or result.rowcount != 1:
            return False
        return True


def enqueue(item, failed):
    import mylar
    if failed:
        from mylar import workflow, queue_control, db
        from mylar.workflow_store import LOCK
        key = str(item['id'])
        with queue_control._LOCK, LOCK:
            row = db.DBConnection().selectone('SELECT status,link,issueid,comicid FROM ddl_info WHERE id=?', [key]).fetchone()
            if (not row or row['status'] != 'Queued' or row['link'] != item.get('link')
                    or str(row['issueid']) != str(item.get('issueid')) or str(row['comicid']) != str(item.get('comicid'))
                    or workflow.reservation(row['issueid']) or workflow.import_owner(row['issueid'])
                    or workflow.dispatch_owner(row['issueid'])):
                return
            state = workflow.store()
            priority = state.get('meta', 'ddl_retry_next', [])
            state.set('meta', 'ddl_retry_next', [key] + [old for old in priority if old != key])
        with queue_control._LOCK:
            control = queue_control.store()
            value = control.record(item)
            value['reason'] = 'Alternate mirror selected; queued next'
            control.save()
        workflow.emit('download', 'Alternate mirror selected; queued next',
                      issueid=item.get('issueid'), comicid=item.get('comicid'),
                      provider=item.get('link_type'), key='ddl-mirror:'+key)
    # Discovery replaces the queued mirror, including cooldown probes. Remove
    # only pending copies of this ID and preserve Queue unfinished-task accounting.
    queue = mylar.DDL_QUEUE
    with queue.not_full:
        removed = [old for old in queue.queue if isinstance(old, dict) and str(old.get('id')) == str(item['id'])]
        for old in removed:
            queue.queue.remove(old)
        queue.unfinished_tasks -= len(removed)
        if not queue.unfinished_tasks:
            queue.all_tasks_done.notify_all()
        queue.not_full.notify_all()
    queue.put(item)


def refresh_cooling(items, rows, providers, rules, preferred, last, ages, now):
    """Probe one queued release in execution order when no transfer is eligible."""
    from mylar import ddl_schedule, workflow, queue_control
    from mylar.workflow_store import LOCK
    import hashlib
    import json
    with LOCK:
        state = workflow.store()
        if state.get('meta', 'ddl_mirror_probe_after', 0) > now:
            return
    cooling = [name for name, value in providers.items() if value.get('until', 0) > now]
    if not cooling:
        return
    pending = list(items)
    while pending:
        index = ddl_schedule.choose(pending, rows, {}, rules['ddl_order'], preferred,
                                    last, now, ages, rules.get('ddl_kind'))
        if index is None:
            return
        item = pending.pop(index)
        if item.get('site') != 'DDL(GetComics)':
            continue
        key = str(item['id'])
        with queue_control._LOCK:
            record = queue_control.store().data['items'].get(key, {})
            if record.get('attempts', 0) >= queue_control.ATTEMPT_LIMIT:
                continue
            failed = record.get('failed_providers', [])
        signature = hashlib.sha256(json.dumps([item.get('mainlink'), item.get('link_type'),
                    failed, sorted((name, providers[name]['until']) for name in cooling)], sort_keys=True).encode()).hexdigest()
        with LOCK:
            previous = state.get('ddl_mirror_probe', key, {})
            if previous.get('signature') == signature and previous.get('after', 0) > now:
                continue
            # Record before network I/O so restart and failed lookups cannot loop.
            state.set('ddl_mirror_probe', key, {'signature': signature, 'after': now + 300})
            state.set('meta', 'ddl_mirror_probe_after', now + 5)
        try:
            from mylar import getcomics, logger
            owner = getcomics.GC(comicid=item.get('comicid'), issueid=item.get('issueid'),
                                 oneoff=item.get('oneoff', False))
            packinfo = item.get('packinfo')
            if packinfo is None:
                row = rows[key]
                packinfo = {'pack':str(row.get('pack')).lower() in ('1','true'),
                            'pack_numbers':row.get('issues'), 'pack_issuelist':None}
            # Exclude cooling providers as well as actual failed providers. A miss
            # leaves the original queued mirror intact until its cooldown expires.
            result = owner.parse_downloadresults(item['id'], item['mainlink'], item.get('comicinfo'),
                                                 packinfo, list(dict.fromkeys(failed + cooling)))
            outcome = 'Available mirror queued next' if isinstance(result, dict) and result.get('success') else 'No available mirror; retaining queued download'
            workflow.emit('download', outcome, issueid=item.get('issueid'), comicid=item.get('comicid'), key='ddl-probe:'+key)
        except Exception as exc:
            logger.warn('DDL cooldown mirror check deferred after %s', type(exc).__name__)
        return
