"""Durable pack ownership and authenticated member reports, separate from issues."""
import hashlib
import base64
import json
import os
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


def source_state(source, content=False):
    """Bounded source version, including an extracted companion when present."""
    source = Path(source)
    roots = [("source", source)]
    companion = source.with_suffix('') if source.suffix.lower() == '.zip' else None
    if source.is_file() and companion is not None and companion.exists():
        roots.append(("companion", companion))
    entries = []; total = 0
    for prefix, root in roots:
        if any(p.is_symlink() for p in (root, *root.parents)):
            raise ValueError('Linked pack source')
        paths = [root]
        if root.is_dir():
            for folder, dirs, files in os.walk(root, followlinks=False):
                paths.extend(Path(folder) / name for name in dirs + files)
                if len(paths) > 4001:
                    raise ValueError('Pack source exceeds limits')
        for path in sorted(paths):
            if path.is_symlink():
                raise ValueError('Linked pack source')
            info = path.stat()
            name = prefix + '/' + str(path.relative_to(root))
            if not path.is_file() and not path.is_dir():
                raise ValueError('Unsupported pack source')
            signature = [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]
            checksum = None
            if path.is_file():
                total += info.st_size
                if total > 32 * 1024**3:
                    raise ValueError('Pack source exceeds limits')
                if content:
                    digest = hashlib.sha256()
                    with path.open('rb') as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                            digest.update(chunk)
                    after = path.stat()
                    if signature != [after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns]:
                        raise ValueError('Pack source changed')
                    checksum = digest.hexdigest()
            entries.append([name, 'file' if path.is_file() else 'directory', checksum if content else signature])
    if not any(entry[1] == 'file' for entry in entries):
        raise ValueError('Pack source has no files')
    return hashlib.sha256(json.dumps(entries, separators=(',', ':')).encode()).hexdigest()


def discover(ddl_id, source, name):
    """Preserve each capture; path reuse never overwrites an earlier owner."""
    store = workflow.store()
    base = hashlib.sha256((ddl_id + '\0' + str(source)).encode()).hexdigest()
    records = [r for r in store.active('pack', {'discovered', 'review', 'confirmed'})
               if r['ddl_id'] == ddl_id and r['source'] == str(source)]
    # Cleanup can be resumed after removing only part of a source. That is not
    # a newly delivered generation; the worker retains its original receipt.
    cleaning = next((r for r in records if r.get('cleanup_started') and not r.get('cleanup_complete')), None)
    if cleaning:
        return cleaning
    stamp = source_state(source)
    unchanged = next((r for r in records if r.get('source_stamp') == stamp), None)
    if unchanged:
        return unchanged
    generation = source_state(source, content=True)
    if source_state(source) != stamp:
        raise ValueError('Pack source changed during capture')
    legacy = sorted(r['id'] for r in records if not r.get('source_generation'))
    key = base if not records else hashlib.sha256(
        (base + '\0' + stamp + '\0' + generation + '\0' + json.dumps(legacy)).encode()).hexdigest()
    record = {'id': key, 'ddl_id': ddl_id, 'source': str(source), 'name': label(name),
              'source_stamp': stamp, 'source_generation': generation,
              'phase': 'discovered', 'members': [], 'inventory_complete': False, 'created_at': time.time()}
    store.create('pack', key, record)
    current = store.get('pack', key)
    if current.get('source_generation') != generation or current.get('source_stamp') != stamp:
        raise ValueError('Pack generation identity conflict')
    return current


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
    record = discover(ddl_id, source, processor.nzb_name)
    key = record['id']
    workflow.emit('processing', 'Pack handed to member verification', name=record['name'], key='pack:' + key)
    processor.queue.put([{'mode': 'stop'}])
    return True


def work():
    if workflow.policy().get('pack_automation'):
        import mylar
        from mylar import db
        root = Path(mylar.CONFIG.DDL_LOCATION)
        for row in db.DBConnection().select("SELECT id,pack,filename,series FROM ddl_info WHERE status='Completed' ORDER BY updated_date DESC"):
            ddl_id = ddl_identifier(row['id'])
            if not ddl_id or not is_pack(row['pack']) or not row['filename']:
                continue
            name = Path(row['filename']).name
            source = root / name
            if not source.exists() and source.suffix.lower() == '.zip' and source.with_suffix('').is_dir():
                source = source.with_suffix('')
            if source.is_dir() and source.with_name(source.name + '.zip').is_file():
                source = source.with_name(source.name + '.zip')
            if not source.exists() or source.is_symlink():
                continue
            try:
                discover(ddl_id, source, row['series'])
            except (OSError, ValueError):
                # An unstable source cannot publish a new capture identity.
                continue
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



def report(payload, handoff=None):
    if not isinstance(payload, str) or len(payload) > 2000000:
        raise ValueError('Pack report exceeds limit')
    value = json.loads(payload)
    # This namespace belongs only to the live native retained finalizer.
    if value.get('phase')=='retained-accepted' or value.get('record_kind')=='retained_delivery_final' or any(k in value for k in ('retained_finalization','retained_delivery_final','fresh_retained_acceptance')) or any(
            any(k in m for k in ('retained_finalization','retained_delivery_final','fresh_retained_acceptance'))
            or m.get('phase')=='retained-accepted' for m in value.get('members',[]) if isinstance(m,dict)):
        raise ValueError('Reserved native retained finalization')
    from mylar import worker_handoff
    worker_handoff.admit(handoff,'packReport',{'report':payload})
    key = value.get('id', '')
    if not HEX.fullmatch(key):
        raise ValueError('Invalid pack identity')
    old = workflow.store().get('pack', key)
    if not old:
        raise ValueError('Unknown pack')
    if any(m.get('retained_finalization') or m.get('phase')=='retained-accepted' for m in old['members']):
        raise ValueError('Native retained capture cannot be rewritten by worker report')
    expected_record = json.loads(json.dumps(old))
    members = value.get('members')
    if not isinstance(members, list) or len(members) > 2000:
        raise ValueError('Invalid member inventory')
    previous_members={row['id']:row for row in old['members']}
    if not set(previous_members)<= {row.get('id') for row in members}:
        raise ValueError('Pack report cannot erase prior member evidence')
    clean = []
    seen = set()
    for row in members:
        token = row.get('id', '')
        if not HEX.fullmatch(token) or token in seen or row.get('kind') not in KINDS or row.get('phase') not in PHASES:
            raise ValueError('Invalid pack member')
        seen.add(token)
        previous_member=previous_members.get(token,{})
        if previous_member.get('phase') in ('confirmed','preserved'):
            if (row.get('phase')!=previous_member.get('phase')
                    or row.get('kind')!=previous_member.get('kind')
                    or any(identifier(row.get(key))!=identifier(previous_member.get(key)) for key in ('issueid','comicid'))
                    or row.get('destination')!=previous_member.get('destination')
                    or row.get('destination_sha256')!=previous_member.get('destination_sha256')
                    or (row.get('kind')=='sidecar' and row.get('sha256')!=previous_member.get('sha256'))):
                raise ValueError('Delayed report cannot replace verified member evidence')
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
        if member['kind']!='sidecar' and member['phase']=='confirmed':
            from mylar import ordinary_import_history,publication_native
            ordinary_token=row.get('ordinary_import_token','')
            owner=publication_native.owner(__import__('mylar').DATA_DIR,member['issueid'],member['comicid'])
            if (not HEX.fullmatch(ordinary_token) or owner is None
                    or not ordinary_import_history.confirmed_token(ordinary_token,owner,member['destination'])):
                raise ValueError('Pack member lacks exact ordinary import acknowledgement')
            if previous_member.get('ordinary_import_token') not in (None,ordinary_token):
                raise ValueError('Pack acknowledgement changed')
            member['ordinary_import_token']=ordinary_token
        clean.append(member)
    old.update(members=clean, inventory_complete=bool(old.get('inventory_complete') or value.get('inventory_complete') is True),
               updated_at=time.time(), phase='review', cleanup_complete=bool(old.get('cleanup_complete') or value.get('cleaned_at')),
               cleanup_started=bool(old.get('cleanup_started') or value.get('cleanup_verified_at')))
    if old['inventory_complete'] and clean and all((m['phase']=='confirmed' and m['kind']!='sidecar') or (m['kind']=='sidecar' and m['phase']=='preserved') for m in clean):
        old['phase'] = 'confirmed'
    def verify_destinations():
        # Recheck under the journal write transaction. A delayed HTTP report
        # must not publish pre-mutation signatures after binding finalization.
        for member in clean:
            if member['kind'] != 'sidecar' and member['phase'] in ('confirmed', 'preserved'):
                path = Path(member['destination'])
                info = path.stat()
                if (any(p.is_symlink() for p in (path, *path.parents))
                        or member['signature'] != [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]):
                    raise ValueError('Library destination changed before report commit')
    if not workflow.store().replace('pack', key, expected_record, old, verify=verify_destinations):
        raise ValueError('Pack changed while report was being verified')
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
            if row['kind']!='sidecar' and row['phase']=='confirmed':
                from mylar import ordinary_import_history,publication_native
                token=original.get('ordinary_import_token','')
                acknowledged=False
                if isinstance(token,str) and HEX.fullmatch(token):
                    from mylar import publication_guard
                    try:
                        owner=publication_native.owner(__import__('mylar').DATA_DIR,original['issueid'],original['comicid'])
                        acknowledged=owner is not None and ordinary_import_history.confirmed_token(token,owner,original['destination'])
                    except (publication_native.Review,publication_guard.Unavailable,OSError,ValueError,KeyError,TypeError):
                        # Passive observation retains members and their original evidence.
                        acknowledged=False
                if not acknowledged:
                    row.update(phase='review',reason='Ordinary import acknowledgement missing or changed')
            members.append(row)
        confirmed = sum((m['phase']=='confirmed' and m['kind']!='sidecar') or (m['kind']=='sidecar' and m['phase']=='preserved') for m in members)
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
    grouped = {}
    for record in snapshot(records):
        group = grouped.setdefault(record['ddl_id'], {'complete': True, 'confirmed': 0, 'total': 0})
        # Every capture retains its own member references. One completed capture
        # cannot establish completion of another delivery sharing the DDL ID.
        group['complete'] = group['complete'] and record['complete']
        group['confirmed'] += record['confirmed']
        group['total'] += record['total']
    return {key: (('Pack in library' if group['complete'] else 'Pack member review') +
                  ' (%d/%d members)' % (group['confirmed'], group['total']), group['complete'])
            for key, group in grouped.items()}
