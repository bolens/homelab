"""Batch reader discovery after catalog placement, conversion and tagging finish."""
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import struct
import time
from urllib.parse import quote
import xml.etree.ElementTree as ET
import zipfile
import zlib

from normalize import api_path, identity, save


def policy(config):
    value = config.get('reader_scan', {})
    if not isinstance(value, dict) or type(value.get('enabled', False)) is not bool:
        raise ValueError('reader_scan.enabled must be boolean')
    result = dict(enabled=value.get('enabled', False))
    for name, default, maximum in (('batch_size', 5, 100), ('max_wait_seconds', 300, 86400),
                                    ('min_interval_seconds', 120, 86400)):
        number = value.get(name, default)
        if type(number) is not int or not 1 <= number <= maximum:
            raise ValueError('Invalid reader_scan.' + name)
        result[name] = number
    if result['enabled']:
        mylar = config.get('mylar')
        paths = (config.get('writer_state'), mylar.get('config_dir') if isinstance(mylar, dict) else None)
        if any(not isinstance(path, str) or not path or not Path(path).is_absolute() for path in paths):
            raise ValueError('Reader scans require absolute Mylar config_dir and shared writer coordination')
    return result


def tagged_cbz(path):
    """Read bounded directory/XML metadata, never decompress image pages."""
    if path.suffix.lower() != '.cbz':
        return False
    with path.open('rb') as stream:
        stream.seek(0, 2)
        size = stream.tell()
        stream.seek(max(0, size - 65557))
        tail = stream.read(65557)
    offset = tail.rfind(b'PK\x05\x06')
    if offset < 0 or len(tail) < offset + 22:
        return False
    _, disk, start_disk, count_disk, count, directory_size, directory_offset, comment = struct.unpack(
        '<4s4H2LH', tail[offset:offset+22])
    if (disk or start_disk or count != count_disk or not 0 < count <= 10000
            or directory_size > 8*1024*1024 or directory_offset == 0xffffffff
            or directory_offset + directory_size > size or offset+22+comment != len(tail)):
        return False
    with zipfile.ZipFile(path) as archive:
        metadata = [entry for entry in archive.infolist()
                    if Path(entry.filename.replace('\\', '/')).name.casefold() == 'comicinfo.xml']
        if len(metadata) != 1:
            return False
        entry = metadata[0]
        if (entry.filename.casefold() != 'comicinfo.xml' or entry.flag_bits & 1
                or not 0 < entry.file_size <= 262144 or entry.compress_size > 1048576):
            return False
        with archive.open(entry) as source:
            raw = source.read(262145)
        if len(raw) > 262144 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
            return False
        return ET.fromstring(raw).tag == 'ComicInfo'


class ScanBatch:
    def __init__(self, worker, clock=time.time):
        self.worker, self.clock = worker, clock
        self.rules = policy(worker.config)
        self.path = worker.state/'reader-scan.json'
        self.status_path = worker.state/'reader-scan-status.json'
        self.config_dir = Path(worker.config['mylar']['config_dir'])
        self.scope = hashlib.sha256(json.dumps([str(self.config_dir), sorted(map(str, worker.roots))]).encode()).hexdigest()
        self.state = None
        self.validated = set()

    def load(self):
        if not self.path.exists():
            return None
        value = json.loads(self.path.read_text())
        def number(item):
            return type(item) in (int, float) and math.isfinite(item) and item >= 0
        if (not isinstance(value, dict) or value.get('version') != 1 or value.get('scope') != self.scope
                or not isinstance(value.get('known'), dict) or not isinstance(value.get('pending'), dict)
                or not number(value.get('next_allowed'))):
            raise ValueError('Reader scan state requires review')
        for key, path in value['known'].items():
            if not isinstance(key, str) or not isinstance(path, str):
                raise ValueError('Invalid reader scan catalog')
        for key, row in value['pending'].items():
            if (not isinstance(row, dict) or row.get('path') != value['known'].get(key)
                    or not isinstance(row.get('path'), str) or not number(row.get('last_checked'))
                    or (row.get('ready_at') is not None and not number(row['ready_at']))
                    or ('stable_since' in row and not number(row['stable_since']))
                    or ('identity' in row and (not isinstance(row['identity'], list)
                        or len(row['identity']) != 3 or any(type(x) is not int for x in row['identity'])
                        or 'stable_since' not in row))):
                raise ValueError('Invalid pending reader scan')
        return value

    def catalog(self):
        paths = {}
        with closing(sqlite3.connect((self.config_dir/'mylar.db').as_uri()+'?mode=ro', uri=True)) as db:
            for table in ('issues', 'annuals'):
                sql = ('SELECT i.IssueID,i.ComicID,c.ComicLocation,i.Location FROM '+table+
                       " i JOIN comics c ON c.ComicID=i.ComicID WHERE i.Status IN ('Downloaded','Archived')"
                       + (' AND COALESCE(i.Deleted,0)=0' if table == 'annuals' else
                          ' AND NOT EXISTS (SELECT 1 FROM annuals a WHERE a.IssueID=i.IssueID)'))
                for issue, comic, folder, location in db.execute(sql):
                    if not folder or not location:
                        continue
                    root, path = Path(folder), Path(folder)/location
                    if (not root.is_absolute() or '..' in path.parts or not path.is_relative_to(root)
                            or not any(path.is_relative_to(r) for r in self.worker.roots)):
                        continue
                    key = hashlib.sha256(json.dumps([table, str(issue), str(comic), str(path)]).encode()).hexdigest()
                    paths.setdefault(str(path), {})[key] = str(path)
        return {key: path for owners in paths.values() if len(owners) == 1 for key, path in owners.items()}

    def blocked(self):
        paths = set()
        for receipt in self.worker.jobs.glob('*/receipt.json'):
            job = json.loads(receipt.read_text())
            if job['phase'] != 'done' or job.get('mylar_refresh_pending') or job.get('mylar_tag_pending'):
                paths.update(p for p in (job.get('source'), job.get('destination')) if p)
        with closing(sqlite3.connect((self.config_dir/'workflow.sqlite').as_uri()+'?mode=ro', uri=True)) as db:
            for (raw,) in db.execute("SELECT value FROM records WHERE kind IN ('converted_tag','library_repair')"):
                job = json.loads(raw)
                if job.get('phase') != 'completed' and job.get('path'):
                    paths.add(job['path'])
        return paths

    def status(self, error=None):
        state = self.state or {}
        pending = state.get('pending', {})
        save(self.status_path, dict(checked_at=self.clock(), pending=len(pending),
             ready=sum(row.get('ready_at') is not None for row in pending.values()),
             last_requested=state.get('last_requested'), errors=[error or state['last_error']] if error or state.get('last_error') else []))

    def waiting(self):
        previous = json.loads(self.status_path.read_text()) if self.status_path.exists() else {'errors': []}
        previous.update(checked_at=self.clock(), state='waiting for conversion recovery')
        save(self.status_path, previous)

    def collect(self):
        """Called only with the normalizer's shared writer lock held."""
        self.validated = set()
        try:
            self.state = None
            current = self.catalog()
            self.state = self.load()
            if self.state is None:
                self.state = dict(version=1, scope=self.scope, known=current, pending={}, next_allowed=0)
                save(self.path, self.state)
                self.status()
                return True
            state, now = self.state, self.clock()
            pending = state['pending']
            for key in list(pending):
                if key not in current:
                    del pending[key]
            for key, path in current.items():
                if key not in state['known']:
                    pending[key] = dict(path=path, last_checked=0, ready_at=None)
            state['known'] = current
            blocked = self.blocked()
            # Revalidate previously ready entries every cycle, even outside the
            # inspection budget, so a newly pending tag job revokes readiness.
            for row in pending.values():
                if row['path'] in blocked:
                    row['ready_at'] = None
            candidates = sorted(pending.items(), key=lambda pair: pair[1].get('last_checked', 0))[:50]
            for key, row in candidates:
                row['last_checked'] = now
                path = Path(row['path'])
                try:
                    if (str(path) in blocked or any(p.is_symlink() for p in (path, *path.parents))
                            or not path.is_file()):
                        row['ready_at'] = None
                        continue
                    fingerprint = identity(path)
                    if fingerprint != row.get('identity'):
                        row.update(identity=fingerprint, stable_since=now, ready_at=None)
                    if now-row['stable_since'] < self.worker.config.get('settle_seconds', 120):
                        continue
                    if tagged_cbz(path) and identity(path) == fingerprint:
                        if row.get('ready_at') is None:
                            row['ready_at'] = now
                        self.validated.add(key)
                    else:
                        row['ready_at'] = None
                except (OSError, ValueError, ET.ParseError, zipfile.BadZipFile, RuntimeError, EOFError, zlib.error):
                    row['ready_at'] = None
            save(self.path, state)
            self.status()
            return True
        except Exception as exc:
            self.status('Readiness check failed: '+type(exc).__name__)
            return False

    def dispatch(self):
        """Request only affected libraries after releasing media writer ownership."""
        state, now = self.state, self.clock()
        ready = {key: row for key, row in state['pending'].items() if row.get('ready_at') is not None}
        if (not ready or now < state['next_allowed'] or
                (len(ready) < self.rules['batch_size'] and
                 now-min(row['ready_at'] for row in ready.values()) < self.rules['max_wait_seconds'])):
            return
        ready = {key: row for key, row in ready.items() if key in self.validated}
        if not ready:
            return
        # Persist pacing before any request, including ambiguous timeout/restart.
        state['next_allowed'] = now+self.rules['min_interval_seconds']
        save(self.path, state)
        try:
            libraries = self.worker.reader.call('/api/v1/libraries')
            groups = {}
            for key, row in ready.items():
                path = Path(row['path'])
                matches = []
                for library in libraries:
                    root = api_path(library['root'])
                    if root.is_absolute() and '..' not in root.parts and path.is_relative_to(root):
                        matches.append(str(library['id']))
                if len(matches) != 1:
                    raise ValueError('Ready addition has no unique reader library')
                groups.setdefault(matches[0], []).append(key)
            for library, keys in groups.items():
                if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', library):
                    raise ValueError('Invalid reader library identity')
                self.worker.reader.call('/api/v1/libraries/'+quote(library, safe='')+'/scan', {})
                state['last_requested'] = now
                for key in keys:
                    del state['pending'][key]
                save(self.path, state)
            state.pop('last_error', None)
            save(self.path, state)
            self.status()
        except Exception as exc:
            state['last_error'] = 'Reader scan request failed: '+type(exc).__name__
            save(self.path, state)
            self.status()
