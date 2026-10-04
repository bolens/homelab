"""Exact, journaled transitions for previously verified pack library members."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import stat
import re

if __package__:
    from .tagger_adapter import fingerprint
else:
    from tagger_adapter import fingerprint


FIELDS = ('issueid', 'comicid', 'kind', 'phase', 'destination', 'destination_sha256', 'signature')


def validate(intent):
    if intent is None:
        return
    if (not isinstance(intent, dict) or set(intent) != {'version', 'source', 'destination', 'owner', 'bindings'}
            or type(intent['version']) is not int or intent['version'] != 1
            or not isinstance(intent['owner'], dict) or set(intent['owner']) != {'issueid', 'comicid'}
            or any(not isinstance(v, str) or not v.isdecimal() for v in intent['owner'].values())
            or not isinstance(intent['bindings'], list) or not intent['bindings']):
        raise ValueError('Invalid pack transition intent')
    for path in ('source', 'destination'):
        if not isinstance(intent[path], str) or not Path(intent[path]).is_absolute() or '..' in Path(intent[path]).parts:
            raise ValueError('Invalid pack transition path')
    seen = set()
    for binding in intent['bindings']:
        if not isinstance(binding, dict) or set(binding) != {'pack', 'member', 'before'}:
            raise ValueError('Invalid pack transition member')
        if any(not isinstance(binding[f], str) or not re.fullmatch(r'[a-f0-9]{64}', binding[f]) for f in ('pack', 'member')):
            raise ValueError('Invalid pack transition key')
        pair = (binding['pack'], binding['member'])
        before = binding['before']
        if (pair in seen or not isinstance(before, dict) or set(before) != set(FIELDS)
                or before['destination'] != intent['source'] or before['kind'] == 'sidecar'
                or before['phase'] not in ('confirmed', 'preserved')
                or any(before[f] != intent['owner'][f] for f in ('issueid', 'comicid'))
                or not isinstance(before['destination_sha256'], str)
                or not re.fullmatch(r'[a-f0-9]{64}', before['destination_sha256'])
                or not isinstance(before['signature'], list) or len(before['signature']) != 5
                or any(type(v) is not int for v in before['signature'])):
            raise ValueError('Invalid pack transition proof')
        seen.add(pair)


def signature(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Unsafe pack publication path')
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('Unsafe pack publication file')
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def owner(root, path):
    """Read native ownership without importing or initializing the Mylar daemon."""
    database = Path(root)/'mylar.db'
    if any(p.is_symlink() for p in (database, *database.parents)):
        raise ValueError('Linked native catalog')
    found = []
    with closing(sqlite3.connect(database.as_uri()+'?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        parents = db.execute('SELECT * FROM comics WHERE ComicLocation=?', (str(Path(path).parent),)).fetchall()
        for parent in parents:
            for table in ('issues', 'annuals'):
                rows = db.execute('SELECT * FROM '+table+' WHERE ComicID=? AND Location=?',
                                  (parent['ComicID'], Path(path).name)).fetchall()
                found.extend(dict(row) for row in rows)
        if len(found) == 1:
            matches = sum(len(db.execute('SELECT IssueID FROM '+table+' WHERE IssueID=?',
                                        (found[0]['IssueID'],)).fetchall()) for table in ('issues', 'annuals'))
            if matches != 1:
                raise ValueError('Pack publication catalog owner is shadowed')
    if len(found) != 1 or found[0].get('Deleted') or found[0]['Status'] not in ('Downloaded', 'Archived'):
        raise ValueError('Pack publication catalog ownership needs review')
    return {field: str(found[0][native]) for field, native in (('issueid', 'IssueID'), ('comicid', 'ComicID'))}


def capture(store, source, destination, *, catalog_owner=None):
    """Return an intent to persist in the publisher's journal before mutation."""
    source, destination = str(source), str(destination)
    bindings = []
    with store.connection() as db:
        for row in db.execute("SELECT key,value FROM records WHERE kind='pack'"):
            record = json.loads(row['value'])
            for member in record.get('members', []):
                if (member.get('kind') != 'sidecar' and member.get('phase') in ('confirmed', 'preserved')
                        and member.get('destination') == source):
                    bindings.append(dict(pack=row['key'], member=member['id'],
                                         before={field: member.get(field) for field in FIELDS}))
    if not bindings:
        return None
    prior = signature(source)
    digest = fingerprint(Path(source))
    if signature(source) != prior:
        raise ValueError('Pack source changed during proof')
    catalog_owner = catalog_owner or owner(store.path.parent, source)
    for binding in bindings:
        before = binding['before']
        if (before['signature'] != prior or before['destination_sha256'] != digest
                or any(before[field] != catalog_owner[field] for field in ('issueid', 'comicid'))):
            raise ValueError('Existing pack evidence is stale or foreign')
    intent = dict(version=1, source=source, destination=destination, owner=catalog_owner, bindings=bindings)
    validate(intent)
    return intent


def finalize(store, intent, digest, *, catalog_owner=None):
    """Atomically rebind every captured member, or leave all records unchanged."""
    if intent is None:
        return
    validate(intent)
    destination = Path(intent['destination'])
    current = signature(destination)
    if fingerprint(destination) != digest or signature(destination) != current:
        raise ValueError('Pack publication digest changed')
    catalog_owner = catalog_owner or owner(store.path.parent, destination)
    if catalog_owner != intent['owner']:
        raise ValueError('Pack publication owner changed')
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        records = {}
        pending = list(intent['bindings'])
        known = {(b['pack'], b['member']) for b in pending}
        # A report already in flight can add another overlapping pack after
        # capture. The original exact proof also covers that identical member.
        for row in db.execute("SELECT key,value FROM records WHERE kind='pack'"):
            record = json.loads(row['value'])
            for member in record.get('members', []):
                actual = {field: member.get(field) for field in FIELDS}
                if ((row['key'], member.get('id')) not in known
                        and any(actual == b['before'] for b in intent['bindings'])):
                    pending.append(dict(pack=row['key'], member=member['id'], before=actual))
        for binding in pending:
            key = binding['pack']
            if key not in records:
                row = db.execute("SELECT value FROM records WHERE kind='pack' AND key=?", (key,)).fetchone()
                if row is None:
                    raise ValueError('Pack record disappeared')
                records[key] = json.loads(row[0])
            members = [m for m in records[key]['members'] if m.get('id') == binding['member']]
            if len(members) != 1:
                raise ValueError('Pack member ownership changed')
            member = members[0]
            before = binding['before']
            after = dict(before, destination=str(destination), destination_sha256=digest, signature=current)
            actual = {field: member.get(field) for field in FIELDS}
            if actual not in (before, after):
                raise ValueError('Pack member changed during publication')
            member.update(after)
        if signature(destination) != current:
            raise ValueError('Pack publication changed during rebinding')
        for key, record in records.items():
            db.execute("UPDATE records SET value=?,updated=? WHERE kind='pack' AND key=?",
                       (json.dumps(record), store.clock(), key))
