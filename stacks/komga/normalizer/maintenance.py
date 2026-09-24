"""Verified completed-download cleanup and recoverable corrupt-archive quarantine."""
import configparser
from contextlib import closing
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import time

from normalize import archive_suffix, digest, identity, request, save, sync_directory


class CorruptArchive(ValueError):
    pass


def name_key(value):
    value = re.sub(r'#\d+$', '', value).split('(')[0].casefold()
    return re.sub(r'\d+', lambda m: str(int(m[0])), re.sub(r'[^a-z0-9]', '', value))


def release_key(value):
    return ''.join(c for c in re.sub(r'\[__\d+__\]', '', re.sub(r'#\d+$', '', value)).casefold() if c.isalnum())


def scoped_file(path, roots):
    """Reject links in every component, including links inside a mounted root."""
    for root in roots:
        if path.is_relative_to(root):
            current = path
            while current != root.parent:
                if current.is_symlink():
                    return False
                current = current.parent
            return path.is_file()
    return False


def preserves(source, target):
    return (source['page_count'] > 0 and source['pages'] == target['pages']
            and all(row in target['other_files'] for row in source['other_files']))


class Maintenance:
    def __init__(self, normalizer):
        self.worker = normalizer
        self.settings = normalizer.config['maintenance']
        self.root = Path(self.settings.get('completed', '/completed-comics'))
        self.roots = [self.root]
        if self.settings.get('ddl_cache'):
            self.roots.append(Path(self.settings['ddl_cache']))
        self.state = normalizer.state / 'maintenance'
        self.state.mkdir(exist_ok=True)
        self.receipts = self.state / 'receipts'
        self.receipts.mkdir(exist_ok=True)
        self.observed = {}
        self.cache = {}
        self.last_run = 0
        self.validate_roots()

    def validate_roots(self):
        for root in self.roots:
            if not root.is_dir() or root.is_symlink():
                raise ValueError('Download mount is missing or linked')
            for path in [self.worker.state, *self.worker.roots, *[r for r in self.roots if r != root]]:
                if root.resolve().is_relative_to(path.resolve()) or path.resolve().is_relative_to(root.resolve()):
                    raise ValueError('Download, library, and recovery roots must not overlap')

    def mylar(self, command, **parameters):
        settings = self.worker.config['mylar']
        parser = configparser.ConfigParser()
        parser.read(Path(settings.get('config_dir', '/mylar')) / 'config.ini')
        key = next(parser.get(s, 'api_key') for s in parser.sections() if parser.has_option(s, 'api_key'))
        result = request(settings['url'], '/api', form={'apikey': key, 'cmd': command, **parameters},
                         text=command == 'forceProcess')
        if command == 'forceProcess':
            expected = 'Successfully submitted request for post-processing for ' + parameters['nzb_name']
            if result == expected:
                return {'submitted': True}
            result = json.loads(result)
        if not isinstance(result, dict) or result.get('success') is not True:
            raise RuntimeError('Mylar maintenance API rejected the request')
        return result['data']

    def idle(self):
        value = self.mylar('getHealth')
        queue = value['queues'].get('POST-PROCESS-QUEUE', {})
        return queue.get('alive') and queue.get('size') == 0 and not value['processing']

    def info(self, path):
        fingerprint = identity(path)
        cached = self.cache.get(str(path))
        if cached and cached[0] == fingerprint:
            return cached[1]
        with path.open('rb') as stream:
            prefix = stream.read(4096).lstrip(b'\xef\xbb\xbf \t\r\n')
        if identity(path) != fingerprint:
            raise RuntimeError('Archive changed during validation')
        if re.match(rb'(?:<!doctype\s+html|<html\b)', prefix, re.I):
            raise CorruptArchive('HTML response saved in place of a comic archive')
        result = subprocess.run([self.worker.tool, 'comic-info', str(path), '--max-members', '10000',
                                 '--max-bytes', str(self.worker.config.get('max_expanded_bytes', 2147483648))],
                                capture_output=True, timeout=180,
                                env=dict(os.environ, XDG_CONFIG_HOME=str(self.state / 'empty-config')))
        if identity(path) != fingerprint:
            raise RuntimeError('Archive changed during validation')
        data = json.loads(result.stdout)
        if result.returncode:
            errors = data.get('failures', [])
            text = ' '.join(row.get('error', '') for row in errors).lower()
            confirmed = ('bad crc-32', 'crc check failed', 'bad magic number for file header', 'invalid rar4 header',
                         'bad rar file data', 'rar4 archive has no complete end header', 'invalid symbol', 'invalid code lengths',
                         'error -3 while decompressing', 'truncated', 'unexpected end of archive')
            if errors and not any(row.get('dependency') for row in errors) and any(x in text for x in confirmed):
                raise CorruptArchive('Archive decoder confirmed corrupt data')
            raise ValueError('Archive could not be validated; retained for review')
        value = data['results'][0]['result']
        if identity(path) != fingerprint:
            raise RuntimeError('Archive changed during validation')
        self.cache[str(path)] = (fingerprint, value)
        return value

    def issue_match(self, path):
        settings = self.worker.config['mylar']
        directory = Path(settings.get('config_dir', '/mylar'))
        with closing(sqlite3.connect(f'file:{directory / "mylar.db"}?mode=ro', uri=True)) as db:
            rows = db.execute('SELECT n.IssueID, n.NZBName, i.ComicID, i.Status, n.ID, n.PROVIDER FROM nzblog n '
                              'JOIN issues i ON i.IssueID=n.IssueID').fetchall()
        keys = {release_key(path.parent.name), release_key(path.stem)}
        tagged = re.findall(r'\[__(\d+)__\]', path.name)
        matches = [row for row in rows if (release_key(row[1] or '') in keys
                   or (len(tagged) == 1 and str(row[0]) == tagged[0])) and row[3] != 'Downloaded']
        if len(matches) == 1 and sum(row[0] == matches[0][0] for row in rows) == 1:
            row = matches[0]
            release = hashlib.sha256(json.dumps([row[4], row[5], row[1]], ensure_ascii=True).encode()).hexdigest()
            return {'issueid': str(row[0]), 'comicid': str(row[2]), 'release': release}
        return None

    def import_match(self, path):
        from import_match import match, catalog
        directory = Path(self.worker.config['mylar'].get('config_dir', '/mylar'))
        if self.import_catalog is None:
            self.import_catalog = catalog(directory / 'mylar.db')
        return match(path, directory / 'mylar.db', self.import_catalog)

    def pending_ddl_names(self):
        if not self.settings.get('ddl_cache'):
            return set()
        directory = Path(self.worker.config['mylar'].get('config_dir', '/mylar'))
        with closing(sqlite3.connect(f'file:{directory / "mylar.db"}?mode=ro', uri=True)) as db:
            rows = db.execute("SELECT filename, tmp_filename FROM ddl_info WHERE status IN ('Downloading', 'Queued')").fetchall()
        return {Path(name).name for row in rows for name in row if name}

    def quarantine(self, path, fingerprint):
        if not scoped_file(path, self.roots) or identity(path) != fingerprint:
            raise RuntimeError('Archive changed before quarantine')
        checksum = digest(path)
        job_id = hashlib.sha256(os.fsencode(path) + checksum.encode()).hexdigest()
        destination = self.state / 'quarantine' / job_id / path.name
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        receipt = self.receipts / (job_id + '.json')
        if not destination.exists():
            if shutil.disk_usage(self.state).free < path.stat().st_size * 2 + 128 * 1024**2:
                raise RuntimeError('Insufficient quarantine storage; original retained')
            temporary = destination.with_name('.copying')
            shutil.copyfile(path, temporary)
            with temporary.open('rb') as stream:
                os.fsync(stream.fileno())
            if digest(temporary) != checksum:
                raise RuntimeError('Quarantine copy differs; original retained')
            os.link(temporary, destination)
            temporary.unlink()
            sync_directory(destination.parent)
        if digest(destination) != checksum or identity(path) != fingerprint or digest(path) != checksum:
            raise RuntimeError('Quarantine verification failed; original retained')
        if receipt.exists():
            row = json.loads(receipt.read_text())
            if row['phase'] not in ('saved', 'quarantined'):
                # A repeated delivery of the same corrupt release must not retry again.
                if self.idle() and identity(path) == fingerprint and digest(path) == checksum:
                    path.unlink()
                    sync_directory(path.parent)
                return
            self.finish_quarantine(receipt, row)
            return
        row = {'kind': 'quarantine', 'source': str(path), 'sha256': checksum,
               'destination': str(destination), 'phase': 'saved', 'match': self.issue_match(path),
               'reason': 'Archive decoder confirmed corrupt data'}
        save(receipt, row)
        self.finish_quarantine(receipt, row)

    def finish_quarantine(self, receipt, row):
        path = Path(row['source'])
        if digest(Path(row['destination'])) != row['sha256']:
            raise RuntimeError('Quarantine recovery copy changed')
        if row['phase'] == 'saved':
            if path.exists():
                if not scoped_file(path, self.roots) or digest(path) != row['sha256']:
                    raise RuntimeError('Quarantine source changed; retained')
                if not self.idle():
                    return
                path.unlink()
                sync_directory(path.parent)
            row['phase'] = 'quarantined'
            save(receipt, row)
        if row['phase'] == 'quarantined' and row['match']:
            row['phase'] = 'retry_unconfirmed'
            save(receipt, row)  # An accepted request must never be submitted twice.
            response = self.mylar('reportFailedDownload', **row['match'])
            row['phase'] = 'retry_queued' if response['mode'] == 'retry' else 'retry_stopped'
            save(receipt, row)

    def remove_duplicate(self, source, target):
        if not scoped_file(source, self.roots) or not scoped_file(target, self.worker.roots):
            raise RuntimeError('Cleanup path is outside its scope or linked')
        source_id, target_id = identity(source), identity(target)
        original = self.info(source)
        if not preserves(original, self.info(target)):
            return False
        source_hash, target_hash = digest(source), digest(target)
        job_id = hashlib.sha256(os.fsencode(source) + source_hash.encode()).hexdigest()
        receipt = self.receipts / (job_id + '.json')
        row = {'kind': 'duplicate', 'source': str(source), 'destination': str(target),
               'sha256': source_hash, 'destination_sha256': target_hash, 'phase': 'verified',
               'pages': original['page_count']}
        save(receipt, row)
        if not self.idle():
            return False
        if (not scoped_file(source, self.roots) or not scoped_file(target, self.worker.roots)
                or identity(source) != source_id or identity(target) != target_id
                or digest(source) != source_hash or digest(target) != target_hash):
            raise RuntimeError('File changed before cleanup; source retained')
        source.unlink()
        sync_directory(source.parent)
        row['phase'] = 'removed'
        save(receipt, row)
        try:
            source.parent.rmdir()
        except OSError:
            pass
        return True

    def conversion_identities(self, paths):
        """Bind exact known library paths only; filenames are never identities."""
        settings = self.worker.config.get('mylar', {})
        if not settings:
            return {}
        wanted = {str(Path(p)) for p in paths if p and Path(p).is_absolute() and '..' not in Path(p).parts}
        if not wanted:
            return {}
        database = Path(settings.get('config_dir', '/mylar')) / 'mylar.db'
        matches = {}
        try:
            with closing(sqlite3.connect('file:' + str(database) + '?mode=ro', uri=True)) as db:
                rows = db.execute("SELECT i.IssueID,i.ComicID,i.Location,c.ComicLocation FROM issues i "
                    "JOIN comics c ON c.ComicID=i.ComicID WHERE (CASE WHEN substr(i.Location,1,1)='/' "
                    "THEN i.Location ELSE rtrim(c.ComicLocation,'/') || '/' || i.Location END) IN ("
                    + ','.join('?' for _ in wanted) + ')', sorted(wanted)).fetchall()
            for issueid, comicid, location, directory in rows:
                ids = (str(issueid), str(comicid))
                if any(not value.isdecimal() or len(value) > 20 for value in ids):
                    continue
                target = Path(location) if Path(location).is_absolute() else Path(directory) / location
                if '..' not in target.parts and str(target) in wanted:
                    matches.setdefault(str(target), set()).add(ids)
        except (OSError, sqlite3.Error, TypeError, ValueError):
            # Optional activity attribution cannot suppress conversion reporting.
            return {}
        return matches

    def conversion_report(self):
        jobs = []
        status = self.worker.state / 'status.json'
        if status.exists():
            for error in json.loads(status.read_text()).get('errors', [])[:50]:
                if error.get('path'):
                    jobs.append({'source': error['path'], 'phase': 'failed'})
        receipts = sorted((self.worker.state / 'jobs').glob('*/receipt.json'), key=lambda p: p.stat().st_mtime, reverse=True)
        for receipt in receipts[:50-len(jobs)]:
            jobs.append(json.loads(receipt.read_text()))
        identities = self.conversion_identities([job.get(key) for job in jobs for key in ('source', 'destination')])
        rows = []
        for job in jobs:
            source, phase, original = job['source'], job['phase'], job.get('original')
            name=re.sub(r'[\x00-\x1f\x7f]', '', Path(source).name)[:160]
            if '://' in name or '?' in name or '\\' in name:
                name='Name unavailable'
            container='Unknown'
            if original:
                path=Path(original)
                if path.is_relative_to(self.worker.state) and not path.is_symlink() and path.is_file():
                    with path.open('rb') as stream:header=stream.read(512)
                    for magic,label in [(b'PK','ZIP'),(b'Rar!','RAR'),(b'7z\xbc\xaf\x27\x1c','7Z'),
                                        (b'\x1f\x8b','GZIP'),(b'BZh','BZIP2'),(b'\xfd7zXZ','XZ'),(b'\x28\xb5\x2f\xfd','ZSTD')]:
                        if header.startswith(magic):container=label;break
                    if header[257:262]==b'ustar':container='TAR'
            row = {'name':name,'original_format':(archive_suffix(Path(source)) or '.unknown').lstrip('.').upper(),
                   'original_container':container,'phase':phase}
            matched = set().union(*(identities.get(str(Path(job[key])), set()) for key in ('source', 'destination') if job.get(key)))
            if len(matched) == 1:
                row['issueid'], row['comicid'] = next(iter(matched))
            rows.append(row)
        return rows

    def cycle(self, force=False):
        now = time.time()
        if not force and now - self.last_run < self.settings.get('interval_seconds', 300):
            return
        self.last_run = now
        self.import_submitted = False
        self.import_catalog = None
        self.import_attempts = None
        from guided_match import Guided
        guidance = Guided(self)
        errors, warnings, problems = [], [], []
        status = self.worker.state / 'maintenance-status.json'
        try:
            self.validate_roots()
            if not self.idle():
                previous_errors = json.loads(status.read_text()).get('errors', []) if status.exists() else []
                save(status, {'checked_at': now, 'state': 'waiting for post-processing', 'errors': previous_errors})
                return
            guidance.poll()
            for receipt in self.receipts.glob('*.json'):
                row = json.loads(receipt.read_text())
                if row['kind'] == 'quarantine' and row['phase'] in ('saved', 'quarantined'):
                    self.finish_quarantine(receipt, row)
                elif row['phase'] == 'retry_unconfirmed':
                    errors.append('Quarantine retry needs review: ' + row['source'])
            for receipt in self.receipts.glob('*.json'):
                row = json.loads(receipt.read_text())
                if row['kind'] == 'quarantine':
                    match = row.get('match') or {}
                    problems.append({'name': Path(row['source']).name, 'kind': 'retry_unconfirmed' if row['phase']=='retry_unconfirmed' else 'quarantine',
                                     'phase': row['phase'], 'issueid': match.get('issueid', ''), 'comicid': match.get('comicid', '')})
            protected_ddl = self.pending_ddl_names()
            books = self.worker.reader.books()
            candidates = {}
            for name, book in books.items():
                path = Path(name)
                if (book['media']['status'] == 'READY' and scoped_file(path, self.worker.roots)):
                    candidates.setdefault(name_key(path.stem), []).append(path)
            for directory, dirs, files in itertools.chain.from_iterable(os.walk(root, followlinks=False) for root in self.roots):
                dirs[:] = [d for d in dirs if not d.startswith('.mylar-') and not (Path(directory) / d).is_symlink()]
                for name in files:
                    path = Path(directory) / name
                    if path.is_symlink() or not path.is_file() or not archive_suffix(path):
                        continue
                    if (self.settings.get('ddl_cache') and path.is_relative_to(Path(self.settings['ddl_cache']))
                            and path.name in protected_ddl):
                        continue
                    fingerprint = identity(path)
                    previous, since = self.observed.get(str(path), (None, now))
                    if previous != fingerprint:
                        self.observed[str(path)] = (fingerprint, now)
                        continue
                    if now - since < self.settings.get('settle_seconds', 600):
                        continue
                    try:
                        self.info(path)
                        for target in candidates.get(name_key(path.stem), []):
                            if self.remove_duplicate(path, target):
                                break
                        if path.exists():
                            from import_recovery import previous_attempt
                            previous_import = previous_attempt(self, path)
                            if previous_import:
                                kind, match = previous_import
                                problems.append({'name': path.name, 'kind': kind, **match})
                                continue
                            recovery = self.import_match(path)
                            if not recovery and guidance.aliases:
                                from guided_match import alias_match
                                recovery = alias_match(path, guidance.rows(), guidance.aliases)
                            match = recovery or self.issue_match(path) or {}
                            kind = 'ready' if match else 'unmatched'
                            if identity(path) != fingerprint:
                                raise RuntimeError('Source changed while matching')
                            if recovery:
                                from import_recovery import submit
                                kind = submit(self, path, recovery)
                            guided = guidance.propose(path) if kind == 'unmatched' else {}
                            problems.append({'name': path.name, 'kind': kind, **guided,
                                             'issueid': match.get('issueid', ''), 'comicid': match.get('comicid', '')})
                    except CorruptArchive:
                        self.quarantine(path, fingerprint)
                        problems.append({'name': path.name, 'kind': 'quarantine'})
                    except (ValueError, FileNotFoundError):
                        warnings.append('Retained for review: ' + str(path))
                        problems.append({'name': path.name, 'kind': 'validation'})
                    except Exception:
                        errors.append('Maintenance failed for ' + str(path))
                        problems.append({'name': path.name, 'kind': 'failed'})
            extra = {'guidance': json.dumps(guidance.proposals)} if guidance.available else {}
            self.mylar('reportImportProblems', report=json.dumps(problems[:500]), processing=json.dumps(self.conversion_report()), **extra)
            save(status, {'checked_at': time.time(), 'state': 'checked', 'errors': errors, 'warnings': warnings})
        except Exception:
            save(status, {'checked_at': time.time(), 'state': 'failed',
                          'errors': ['Maintenance API, storage, or recovery check failed']})
