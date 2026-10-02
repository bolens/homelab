"""Durable pack ownership and authenticated member reports, separate from issues."""
import hashlib
import base64
import json
from pathlib import Path
import re
import time

from mylar import workflow
from mylar.workflow_store import identifier, ddl_identifier, label

KINDS = {'issue', 'annual', 'supplement', 'sidecar', 'review'}
PHASES = {'discovered', 'ready', 'submitted', 'review', 'confirmed', 'preserved'}
HEX = re.compile(r'[0-9a-f]{64}\Z')


def is_pack(value):
    return value is True or str(value).lower() in ('1', 'true')


def capture(processor):
    """Defer a downloaded pack before native anchor-based imports can run."""
    if not workflow.policy().get('pack_automation') or not getattr(processor, 'ddl', False):
        return False
    from mylar import db
    info = getattr(processor, 'download_info', None) or {}
    ddl_id = ddl_identifier(info.get('id'))
    if not ddl_id:
        return False  # Individual verified recovery submissions have no DDL ID.
    row = db.DBConnection().selectone('SELECT pack FROM ddl_info WHERE id=?', [ddl_id]).fetchone()
    if not row or not is_pack(row['pack']):
        return False
    source = Path(processor.nzb_folder)
    if source.is_dir() and source.with_name(source.name + '.zip').is_file():
        source = source.with_name(source.name + '.zip')
    key = hashlib.sha256((ddl_id + '\0' + str(source)).encode()).hexdigest()
    record = {'id': key, 'ddl_id': ddl_id, 'source': str(source), 'name': label(processor.nzb_name),
              'phase': 'discovered', 'members': [], 'inventory_complete': False, 'created_at': time.time()}
    workflow.store().create('pack', key, record)
    workflow.emit('processing', 'Pack handed to member verification', name=record['name'], key='pack:' + key)
    processor.queue.put([{'mode': 'stop'}])
    return True


def work():
    if workflow.policy().get('pack_automation'):
        import mylar
        from mylar import db
        existing = {r['ddl_id'] for r in workflow.store().all('pack', 10000)}
        root = Path(mylar.CONFIG.DDL_LOCATION)
        for row in db.DBConnection().select("SELECT id,pack,filename,series FROM ddl_info WHERE status='Completed' ORDER BY updated_date DESC"):
            ddl_id = str(row['id'])
            if ddl_id in existing or not is_pack(row['pack']) or not row['filename']:
                continue
            name = Path(row['filename']).name
            source = root / name
            if not source.exists() and source.suffix.lower() == '.zip' and source.with_suffix('').is_dir():
                source = source.with_suffix('')
            if not source.exists() or source.is_symlink():
                continue
            key = hashlib.sha256((ddl_id + '\0' + str(source)).encode()).hexdigest()
            workflow.store().create('pack', key, {'id': key, 'ddl_id': ddl_id, 'source': str(source),
                'name': label(row['series']), 'phase': 'discovered', 'members': [],
                'inventory_complete': False, 'created_at': time.time()})
    store = workflow.store()
    pending = [r for r in store.active('pack', {'discovered', 'review', 'confirmed'})
               if r['phase'] != 'confirmed' or not r.get('cleanup_complete')
               or any(not member_present(member) for member in r['members'])]
    offset = store.get('meta', 'pack_cursor', 0) % max(1, len(pending))
    page = (pending[offset:] + pending[:offset])[:50]
    store.set('meta', 'pack_cursor', (offset + len(page)) % max(1, len(pending)))
    protected = [r['source'] for r in pending]
    protected.extend(str(Path(r['source']).with_suffix('')) for r in pending if Path(r['source']).suffix.lower() == '.zip')
    return {'enabled': bool(workflow.policy().get('pack_automation')), 'packs': page, 'protected': protected}



def report(payload):
    if not isinstance(payload, str) or len(payload) > 2000000:
        raise ValueError('Pack report exceeds limit')
    value = json.loads(payload)
    key = value.get('id', '')
    if not HEX.fullmatch(key):
        raise ValueError('Invalid pack identity')
    old = workflow.store().get('pack', key)
    if not old:
        raise ValueError('Unknown pack')
    members = value.get('members')
    if not isinstance(members, list) or len(members) > 2000:
        raise ValueError('Invalid member inventory')
    clean = []
    seen = set()
    for row in members:
        token = row.get('id', '')
        if not HEX.fullmatch(token) or token in seen or row.get('kind') not in KINDS or row.get('phase') not in PHASES:
            raise ValueError('Invalid pack member')
        seen.add(token)
        member = {k: row[k] for k in ('id', 'kind', 'phase')}
        member.update(name=label(row.get('name'), 255), reason=label(row.get('reason', '')),
                      format=label(row.get('format', ''), 20), issueid=identifier(row.get('issueid')),
                      comicid=identifier(row.get('comicid')))
        if member['kind'] == 'sidecar' and member['phase'] == 'preserved':
            encoded = row.get('sidecar', '')
            if not isinstance(encoded, str) or len(encoded) > 350000:
                raise ValueError('Sidecar exceeds limit')
            raw = base64.b64decode(encoded, validate=True)
            if hashlib.sha256(raw).hexdigest() != row.get('sha256'):
                raise ValueError('Sidecar checksum differs')
            member.update(sidecar=encoded, sha256=row['sha256'])
        elif member['phase'] in ('confirmed', 'preserved'):
            import mylar
            path = Path(row.get('destination', ''))
            root = Path(mylar.CONFIG.DESTINATION_DIR)
            if (not path.is_absolute() or '..' in path.parts or not path.is_relative_to(root)
                    or any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file()):
                raise ValueError('Library destination is unavailable')
            expected = row.get('destination_sha256', '')
            if not HEX.fullmatch(expected):
                raise ValueError('Missing destination verification')
            previous = next((m for m in old['members'] if m['id'] == token), {})
            stat = path.stat()
            signature = [stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns]
            if previous.get('signature') != signature or previous.get('destination_sha256') != expected:
                with path.open('rb') as stream:
                    checksum = hashlib.sha256()
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        checksum.update(chunk)
                    actual = checksum.hexdigest()
                after = path.stat()
                if actual != expected or signature != [after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns]:
                    raise ValueError('Library destination changed')
            member.update(destination=str(path), destination_sha256=expected, signature=signature)
        clean.append(member)
    old.update(members=clean, inventory_complete=value.get('inventory_complete') is True,
               updated_at=time.time(), phase='review', cleanup_complete=bool(value.get('cleaned_at')))
    if old['inventory_complete'] and clean and all(m['phase'] in ('confirmed', 'preserved') for m in clean):
        old['phase'] = 'confirmed'
    workflow.store().set('pack', key, old)
    return {'recorded': len(clean), 'phase': old['phase']}


def member_present(member):
    try:
        if member.get('kind') == 'sidecar':
            return hashlib.sha256(base64.b64decode(member['sidecar'])).hexdigest() == member['sha256']
        path = Path(member['destination'])
        stat = path.stat()
        return not path.is_symlink() and member.get('signature') == [stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns]
    except (KeyError, OSError):
        return False


def snapshot(records=None):
    result = []
    store = workflow.store()
    if records is None:
        records = store.active('pack', {'discovered', 'review'}) + [r for r in store.all('pack', 200) if r['phase'] == 'confirmed'][:20]
    for record in records:
        members = []
        for original in record['members']:
            row = {k: v for k, v in original.items() if k not in ('destination', 'destination_sha256', 'signature', 'sidecar', 'sha256')}
            if row['phase'] in ('confirmed', 'preserved') and not member_present(original):
                row.update(phase='review', reason='Library file changed or is missing')
            members.append(row)
        confirmed = sum(m['phase'] in ('confirmed', 'preserved') for m in members)
        result.append({'id': record['id'], 'ddl_id': record['ddl_id'], 'name': record['name'],
                       'inventory_complete': record['inventory_complete'], 'members': members,
                       'confirmed': confirmed, 'total': len(members),
                       'complete': bool(record['inventory_complete'] and members and confirmed == len(members))})
    return result


def evidence(record_ids=None):
    # Presentation history must never limit authoritative DDL membership evidence.
    records = workflow.store().active('pack', {'discovered', 'review', 'confirmed'})
    if record_ids is not None:
        requested = {str(key) for key in record_ids}
        records = [r for r in records if r['ddl_id'] in requested]
    return {r['ddl_id']: (('Pack in library' if r['complete'] else 'Pack member review') +
                          ' (%d/%d members)' % (r['confirmed'], r['total']), r['complete']) for r in snapshot(records)}
