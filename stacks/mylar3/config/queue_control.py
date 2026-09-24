"""Persistent DDL attempts, progress, provider cooldowns, and restart recovery."""
import hashlib
import json
import os
from pathlib import Path
import threading
import time

ATTEMPT_LIMIT = 6
COOLDOWN_SECONDS = 900
_LOCK = threading.RLock()
_STORE = None


class Store:
    def __init__(self, root, clock=time.time):
        self.root = Path(root)
        self.path = self.root / 'ddl-control.json'
        self.clock = clock
        self.data = {'version': 1, 'items': {}, 'providers': {}}
        if self.path.exists():
            self.data = json.loads(self.path.read_text())
            if self.data.get('version') != 1 or not isinstance(self.data.get('items'), dict) or not isinstance(self.data.get('providers'), dict):
                raise ValueError('DDL control state needs recovery')

    def save(self):
        temporary = self.path.with_suffix('.new')
        with temporary.open('w') as output:
            os.chmod(temporary, 0o600)
            json.dump(self.data, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, self.path)

    def record(self, item):
        key = str(item['id'])
        # A changed mirror does not grant a fresh attempt budget.
        release = hashlib.sha256((str(item.get('mainlink')) + ':' + str(item.get('issueid'))).encode()).hexdigest()
        value = self.data['items'].get(key)
        if value is None or value['release'] != release:
            value = {'release': release, 'attempts': 0, 'bytes': 0, 'high_water': 0,
                     'last_progress': None, 'sample_time': self.clock(), 'speed': 0,
                     'reason': '', 'completed': False}
            self.data['items'][key] = value
        return value

    def begin(self, item):
        value = self.record(item)
        provider = str(item.get('link_type') or 'GC-Main')
        value['provider'] = provider
        if value['completed']:
            return 'completed'
        if value['attempts'] >= ATTEMPT_LIMIT:
            value['reason'] = 'Retry limit reached; review this release before restarting'
            self.save()
            return 'exhausted'
        remaining = self.data['providers'].get(provider, {}).get('until', 0) - self.clock()
        if remaining > 0:
            value['reason'] = 'Provider cooling down'
            self.save()
            return 'cooldown'
        value['attempts'] += 1
        value['started'] = self.clock()
        value['sample_time'] = self.clock()
        value['speed'] = 0
        value['reason'] = 'Downloading' if value['attempts'] == 1 else 'Retrying download'
        self.save()
        return 'ready'

    def observe(self, key, size, active=True):
        value = self.data['items'].get(str(key))
        if value is None:
            return
        now = self.clock()
        elapsed = now - value.get('sample_time', now)
        if elapsed < 1:
            return
        previous = value.get('bytes', 0)
        value['speed'] = max(0, size - previous) / elapsed if active else 0
        if size > previous:
            value['last_progress'] = now
        value['bytes'] = size
        value['high_water'] = max(size, value.get('high_water', 0))
        value['sample_time'] = now

    def finish(self, item, success, reason=None):
        value = self.record(item)
        provider = str(item.get('link_type') or 'GC-Main')
        state = self.data['providers'].setdefault(provider, {'failures': 0, 'until': 0})
        if success:
            value['completed'] = True
            value['reason'] = 'Downloaded; handed to post-processing'
            value['speed'] = 0
            state.update(failures=0, until=0)
        else:
            state['failures'] += 1
            value['reason'] = reason or 'Download failed; checking another mirror'
            if state['failures'] >= 2 or reason == 'Provider rate limit':
                state['until'] = self.clock() + COOLDOWN_SECONDS
        self.save()

    def reset(self, key):
        value = self.data['items'].get(str(key))
        if value:
            value.update(attempts=0, completed=False, reason='Manual retry requested')
            self.save()


def store():
    global _STORE
    if _STORE is None:
        import mylar
        _STORE = Store(mylar.DATA_DIR)
    return _STORE


def reset(key):
    with _LOCK:
        store().reset(key)


def search_order(order, nzbproviders):
    """Prefer available NZB searches while every known GetComics host is cooling."""
    lowered = {name.casefold() for name in order}
    if ('ddl(getcomics)' not in lowered
            or lowered.intersection(('ddl(external)', 'airdcpp'))):
        return order
    nzb_names = {name.casefold() for name in nzbproviders}
    nzbs = [name for name in order if name.casefold() in nzb_names]
    if not nzbs:
        return order
    try:
        with _LOCK:
            state = store()
            known = [row for name, row in state.data['providers'].items()
                     if name in ('GC-Main', 'GC-Mirror', 'GC_Mirror',
                                 'GC-Mega', 'GC-Media', 'GC-Pixel')]
            now = state.clock()
            if not known or any(row.get('until', 0) <= now for row in known):
                return order
    except (OSError, ValueError, TypeError, AttributeError):
        # Optional ordering must not turn damaged DDL state into an NZB outage.
        # The existing queue/health paths still report invalid control state.
        return order
    return nzbs + [name for name in order if name.casefold() not in nzb_names]


def clear_active(key):
    import mylar
    mylar.DDL_QUEUED[:] = [value for value in mylar.DDL_QUEUED if str(value) != str(key)]


def begin(item, queue):
    from mylar import db, helpers
    database = db.DBConnection()
    current = database.selectone('SELECT status FROM ddl_info WHERE id=?', [item['id']]).fetchone()
    if not current or current['status'] not in ('Queued', 'Downloading'):
        clear_active(item['id'])
        return False
    with _LOCK:
        decision = store().begin(item)
    if decision in ('exhausted', 'completed'):
        status = 'Completed' if decision == 'completed' else 'Failed'
        database.upsert('ddl_info', {'status': status}, {'id': item['id']})
        clear_active(item['id'])
        if decision == 'exhausted':
            helpers.reverse_the_pack_snatch(item['id'], item['comicid'])
        return False
    if decision == 'cooldown':
        database.upsert('ddl_info', {'status': 'Queued'}, {'id': item['id']})
        clear_active(item['id'])
        queue.put(item)
        time.sleep(1)
        return False
    return True


def finish(item, result):
    with _LOCK:
        store().finish(item, bool(result.get('success')), result.get('_queue_reason'))
    if not result.get('success'):
        clear_active(item['id'])


def recover(queue):
    """Called by the sole native DDL worker before consuming its first item."""
    import mylar
    from mylar import db
    database = db.DBConnection()
    with queue.mutex:
        pending = {str(item['id']) for item in queue.queue if isinstance(item, dict)}
    for row in database.select("SELECT * FROM ddl_info WHERE status IN ('Queued', 'Downloading') ORDER BY CASE status WHEN 'Downloading' THEN 0 ELSE 1 END, updated_date"):
        key = str(row['id'])
        if key in pending:
            continue
        item = {name: row[name] for name in ('id', 'link', 'mainlink', 'series', 'year', 'size', 'comicid',
                                             'issueid', 'link_type', 'filename', 'site', 'remote_filesize')}
        item.update(oneoff=False, comicinfo=None, packinfo=None, resume=None)
        if row['filename'] and row['link_type'] in (None, 'GC-Main', 'GC-Mirror') and mylar.CONFIG.DDL_AUTORESUME:
            final = Path(mylar.CONFIG.DDL_LOCATION) / Path(row['filename']).name
            partial = final.with_name(final.name + '.part')
            candidate = partial if partial.is_file() else final
            if candidate.is_file() and not candidate.is_symlink():
                size = candidate.stat().st_size
                try:
                    total = int(row['remote_filesize'] or 0)
                except (TypeError, ValueError):
                    total = 0
                if size > 0 and (total <= 0 or size < total):
                    item['resume'] = size
        database.upsert('ddl_info', {'status': 'Queued'}, {'id': row['id']})
        clear_active(row['id'])
        queue.put(item)
        pending.add(key)


def byte_count(row, directory):
    paths = [row['tmp_filename']]
    if row['filename'] and directory:
        final = Path(directory) / row['filename']
        paths.extend([str(final) + '.part', final])
    for path in paths:
        try:
            if path and Path(path).is_file():
                return Path(path).stat().st_size
        except OSError:
            pass
    return 0


def diagnostics(rows):
    import mylar
    # Download completion is distinct from import completion. Read current issue
    # state on each poll so imports completed after finish() are visible too.
    from mylar import db
    imported = {str(row['id']) for row in db.DBConnection().select("""
        SELECT d.id FROM ddl_info d
        JOIN issues i ON i.IssueID = d.issueid
        WHERE d.status = 'Completed' AND COALESCE(d.pack, 0) = 0
          AND i.Status = 'Downloaded' AND COALESCE(i.Location, '') != ''
        UNION
        SELECT d.id FROM ddl_info d
        JOIN annuals i ON i.IssueID = d.issueid
        WHERE d.status = 'Completed' AND COALESCE(d.pack, 0) = 0
          AND i.Status = 'Downloaded' AND COALESCE(i.Location, '') != ''
    """)}
    result = {}
    with _LOCK:
        state = store()
        now = state.clock()
        for row in rows:
            key = str(row['id'])
            value = state.data['items'].get(key, {})
            active = row['status'] == 'Downloading'
            if active:
                state.observe(key, byte_count(row, mylar.CONFIG.DDL_LOCATION))
            elapsed = now - value.get('sample_time', now)
            speed = value.get('speed', 0) if active and elapsed <= 15 else 0
            last = value.get('last_progress')
            cooldown = max(0, int(state.data['providers'].get(value.get('provider'), {}).get('until', 0) - now))
            finished = row['status'] == 'Completed'
            reason = ('Post-processed; in library' if key in imported else
                      'Downloaded; awaiting post-processing' if finished else value.get('reason', ''))
            result[key] = {'finished': finished, 'bytes': value.get('bytes', 0), 'speed': round(speed),
                           'last_progress_seconds': int(now - last) if last is not None else None,
                           'attempts': value.get('attempts', 0), 'reason': reason,
                           'cooldown_seconds': 0 if finished else cooldown}
        state.save()
    return result


def useful_progress():
    with _LOCK:
        values = store().data['items'].values()
        return [sum(v.get('high_water', 0) for v in values), sum(bool(v.get('completed')) for v in values)]


def rate_limited(key):
    with _LOCK:
        state = store()
        value = state.data['items'].get(str(key))
        if value:
            provider = value.get('provider', 'GC-Main')
            state.data['providers'][provider] = {'failures': 2, 'until': state.clock() + COOLDOWN_SECONDS}
            value['reason'] = 'Provider rate limit'
            state.save()
