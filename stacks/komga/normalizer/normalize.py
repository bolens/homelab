"""Normalize comic containers through archiving-utils and the reader APIs."""

import argparse
import configparser
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import sqlite3
from contextlib import closing
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pdf_conversion import Pending as PDFPending

SUFFIXES = ('.cbt.tar.zst', '.cbt.tar.gz', '.cbt.tar.bz2', '.cbt.tar.xz',
            '.cbt.zst', '.cbt.bz2', '.cbt.gz', '.cbt.xz', '.tar.zst', '.tar.bz2',
            '.tar.gz', '.tar.xz', '.cbz', '.cbr', '.cb7', '.cbt', '.zip', '.rar',
            '.7z', '.tar', '.tgz', '.tbz2', '.txz', '.tzst', '.cba', '.ace', '.pdf')


def archive_suffix(path):
    return next((suffix for suffix in SUFFIXES if path.name.lower().endswith(suffix)), None)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def identity(path):
    value = path.stat(follow_symlinks=False)
    return [value.st_ino, value.st_size, value.st_mtime_ns]


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def save(path, value):
    temporary = path.with_suffix('.new')
    with temporary.open('w') as stream:
        json.dump(value, stream, ensure_ascii=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    sync_directory(path.parent)


def api_path(value):
    if value.startswith('/'):
        return Path(value)
    return Path(urllib.parse.unquote(urllib.parse.urlparse(value).path))


def request(base, route, data=None, key=None, form=None, text=False):
    headers = {}
    if key:
        headers['X-API-Key'] = key
    body = None
    if data is not None:
        headers['Content-Type'] = 'application/json'
        body = json.dumps(data).encode()
    elif form is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        body = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(base.rstrip('/') + route, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read()
            if text:
                return content.decode("utf-8")
            return json.loads(content) if content else None
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'Library API returned HTTP {exc.code}') from None
    except urllib.error.URLError:
        raise RuntimeError('Library API unavailable') from None


class Reader:
    def __init__(self, config):
        self.base = config['url']
        self.key = config['api_key']
        if not self.key or self.key == 'REPLACE_ME':
            raise ValueError('Configure a Komga API key before enabling normalization')

    def call(self, route, data=None):
        return request(self.base, route, data=data, key=self.key)

    def books(self):
        result = {}
        page = 0
        while True:
            data = self.call(f'/api/v1/books/list?page={page}&size=500', {})
            for book in data['content']:
                if not book.get('deleted'):
                    result[str(api_path(book['url']))] = book
            if data.get('last', True):
                return result
            page += 1

    def scan(self):
        for library in self.call('/api/v1/libraries'):
            self.call(f"/api/v1/libraries/{library['id']}/scan", {})

    def analyze(self, book_id):
        self.call(f'/api/v1/books/{book_id}/analyze', {})

    def refresh_metadata(self, book_id):
        # ComicInfoProvider checks the cached media file list. Reanalysis discovers
        # newly added ComicInfo and schedules metadata import only after success.
        self.analyze(book_id)

    def upgrade(self, job):
        self.call('/api/v1/books/import', {
            'copyMode': 'COPY', 'books': [{
                'sourceFile': job['reader_prepared'],
                'seriesId': job['book']['seriesId'],
                'upgradeBookId': job['book']['id'],
                'destinationName': Path(job['destination']).stem,
            }],
        })


class Normalizer:
    def __init__(self, config, reader=None):
        self.config = config
        tagging = (config.get('mylar') or {}).get('tag_converted', False)
        refresh = (config.get('mylar') or {}).get('refresh_reader_after_tagging', False)
        if type(tagging) is not bool or type(refresh) is not bool or ((tagging or refresh) and
                (not isinstance(config.get('writer_state'), str) or not config['writer_state'])):
            raise ValueError('Automatic converted tagging requires boolean opt-in and shared writer coordination')
        self.state = Path(config.get('state', '/state'))
        self.roots = [Path(path) for path in config['roots']]
        if not self.state.is_dir() or self.state.is_symlink():
            raise ValueError('Recovery state directory must already exist')
        for root in self.roots:
            if not root.is_dir() or root.is_symlink():
                raise ValueError('Library roots must already exist and cannot be symlinks')
            if self.state.resolve().is_relative_to(root.resolve()):
                raise ValueError('Recovery state must be outside scanned libraries')
        self.jobs = self.state / 'jobs'
        self.jobs.mkdir(exist_ok=True)
        (self.state / 'tmp').mkdir(exist_ok=True)
        self.tool = config.get('converter', '/opt/archiving-utils/bin/archiving-utils')
        self.reader = reader if reader is not None else Reader(config['komga'])
        from pdf_conversion import policy
        self.pdf_policy = policy(config)
        self.pdf_pending = None
        self.pdf_failures = {}
        self.pdf_defer = False
        self.observed = {}
        self.errors = []
        self.rejected = {}
        from reader_scan import ScanBatch, policy
        self.scan_batch = ScanBatch(self) if policy(config)['enabled'] else None
        from release_naming import policy as naming_policy
        self.naming_rules = naming_policy(config)
        self.naming = None

    def convert_tool(self, *args):
        if args[0] == 'comic-to-cbz' and Path(args[-1]).suffix.lower() == '.pdf':
            from pdf_conversion import derivative
            prepared = derivative(self, Path(args[-1]))
            destination = Path(args[args.index('--output') + 1])
            fd, pending_name = tempfile.mkstemp(prefix='.pdf-copy-', dir=destination.parent)
            pending = Path(pending_name)
            try:
                with prepared.open('rb') as source, os.fdopen(fd, 'wb') as target:
                    shutil.copyfileobj(source, target)
                    target.flush()
                    os.fsync(target.fileno())
                if digest(pending) != digest(prepared):
                    raise ValueError('PDF CBZ copy failed verification')
                os.link(pending, destination)
                sync_directory(destination.parent)
            finally:
                pending.unlink(missing_ok=True)
            return {'results': [{'result': self.info(destination)}]}
        environment = dict(os.environ, TMPDIR=str(self.state / 'tmp'),
                           XDG_CONFIG_HOME=str(self.state / 'empty-config'))
        result = subprocess.run([self.tool, *map(str, args), '--max-members', '10000',
                                 '--max-bytes', str(self.config.get('max_expanded_bytes', 2147483648))], capture_output=True,
                                env=environment, timeout=600, check=False)
        if result.returncode:
            # Archive-tool diagnostics may include file contents; retain only the exit status.
            raise RuntimeError(f'Archive validation/conversion failed ({result.returncode})')
        return json.loads(result.stdout)

    def info(self, path):
        if Path(path).suffix.lower() == '.pdf':
            from pdf_conversion import derivative
            path = derivative(self, path)
        return self.convert_tool('comic-info', path)['results'][0]['result']

    def candidates(self):
        settle = self.config.get('settle_seconds', 120)
        for root in self.roots:
            if not root.is_dir():
                raise RuntimeError('Library mount disappeared; refusing to create it')
            for directory, dirs, files in os.walk(root, followlinks=False):
                dirs[:] = [d for d in dirs if not (Path(directory) / d).is_symlink()]
                for name in sorted(files):
                    path = Path(directory) / name
                    if path.is_symlink() or not path.is_file() or not archive_suffix(path):
                        continue
                    if path.suffix.lower() == '.pdf' and not self.pdf_policy['enabled']:
                        continue
                    current = identity(path)
                    prior, since = self.observed.get(str(path), (None, time.time()))
                    if current != prior:
                        self.observed[str(path)] = (current, time.time())
                        if settle:
                            continue
                    elif time.time() - since < settle:
                        continue
                    if path.suffix.lower() == '.cbz' and zipfile.is_zipfile(path):
                        continue
                    yield path

    def conversion_source(self, path):
        """Fresh unknown-payload authority before preserving or converting media."""
        if self.config.get('writer_state') is None:
            return None
        from publication_guard import current, Unavailable
        path = Path(path)
        if (not path.is_absolute() or '..' in path.parts
                or not any(path.is_relative_to(root) for root in self.roots)
                or any(item.is_symlink() for item in (path, *path.parents))):
            raise Unavailable('Conversion source is outside trusted library roots')
        if path.suffix.lower() == '.pdf':
            raise Unavailable('PDF conversion needs reviewed source-to-rendered payload lineage')
        return current(self).uncataloged_check(path)

    def conversion_check(self, job, *, published=False):
        """A receipt binds the preserved predecessor, output and complete census."""
        if self.config.get('writer_state') is None:
            return
        from publication_guard import current, Unavailable
        import publication_evidence as evidence
        if not isinstance(job, dict):
            raise Unavailable('Invalid conversion receipt')
        binding = job.get('publication_binding')
        if (not isinstance(binding, dict) or set(binding) != {'version', 'source', 'destination',
                'original', 'prepared', 'source_hash', 'output_hash', 'inventory', 'sidecars',
                'source_identity', 'reader_prepared', 'book', 'proof'}
                or type(binding['version']) is not int or binding['version'] != 1
                or job.get('publication_token') != evidence.canonical_digest(binding)
                or any(binding[key] != job.get(key) for key in
                       ('source', 'destination', 'original', 'prepared', 'source_hash', 'output_hash',
                        'inventory', 'sidecars', 'source_identity', 'reader_prepared', 'book'))):
            raise Unavailable('Conversion receipt has no exact immutable publication binding')
        if (any(not isinstance(job.get(key), str) for key in
                ('source', 'destination', 'original', 'prepared', 'source_hash', 'output_hash'))
                or any(re.fullmatch('[0-9a-f]{64}',job[key]) is None for key in ('source_hash','output_hash'))
                or not isinstance(binding['proof'],dict)
                or not isinstance(binding['proof'].get('inventory'),dict)
                or binding['proof'].get('source') != job['source']
                or binding['proof']['inventory'].get('source_sha256') != job['source_hash']):
            raise Unavailable('Malformed conversion predecessor binding')
        source, destination = Path(job['source']), Path(job['destination'])
        suffix = archive_suffix(source)
        if (suffix is None or destination != source.with_name(source.name[:-len(suffix)] + '.cbz')
                or not source.is_absolute() or '..' in source.parts
                or not any(source.is_relative_to(root) for root in self.roots)):
            raise Unavailable('Conversion receipt destination changed')
        directory = self.jobs / hashlib.sha256(os.fsencode(source) + b'\0' + job['source_hash'].encode()).hexdigest()
        if (Path(job['original']) != directory / ('original' + archive_suffix(source))
                or Path(job['prepared']) != directory / 'prepared' / destination.name):
            raise Unavailable('Conversion private predecessor path changed')
        authority = current(self)
        proof = binding['proof']
        if not evidence.same_json(authority.admission()[0], proof.get('census')):
            raise Unavailable('Conversion correction census changed')
        for path, checksum in ((Path(job['original']), job['source_hash']),
                               (Path(job['prepared']), job['output_hash'])):
            if any(item.is_symlink() for item in (path, *path.parents)):
                raise Unavailable('Linked conversion predecessor or prepared output')
            private = path.stat(follow_symlinks=False)
            if private.st_nlink != 1 or private.st_uid != os.geteuid():
                raise Unavailable('Conversion predecessor or output has a physical alias')
            actual = evidence.inventory(path, tool_root=authority.tool_root)
            if (actual['source_sha256'] != checksum
                    or actual['payload'] != proof['inventory']['payload']):
                raise Unavailable('Conversion predecessor or exact member payload changed')
        if source.exists():
            if not evidence.same_json(self.conversion_source(source), proof):
                raise Unavailable('Conversion source or authority changed since preparation')
        elif not published:
            raise Unavailable('Conversion source disappeared before publication')
        if published:
            target = self.conversion_source(destination)
            if (target['inventory']['source_sha256'] != job['output_hash']
                    or target['inventory']['payload'] != proof['inventory']['payload']
                    or not evidence.same_json(target['census'], proof['census'])):
                raise Unavailable('Conversion destination no longer binds the predecessor')
        if not evidence.same_json(authority.admission()[0], proof['census']):
            raise Unavailable('Conversion authority changed during receipt verification')

    def prepare(self, path, books):
        path = Path(path)
        source_proof = self.conversion_source(path)
        if source_proof is not None and books.get(str(path)):
            from publication_guard import Unavailable
            raise Unavailable('Reader-owned conversion requires reviewed outside-writer relocation')
        original_identity = identity(path)
        if original_identity[1] > self.config.get('max_expanded_bytes', 2147483648):
            raise ValueError('Source archive exceeds the configured size limit')
        source_hash = digest(path)
        name = path.name[:-len(archive_suffix(path))] + '.cbz'
        destination = path.with_name(name)
        # Refuse case-insensitive collisions too, since reader libraries may be portable.
        for sibling in path.parent.iterdir():
            if sibling.name.casefold() == name.casefold() and sibling != path:
                raise FileExistsError('CBZ destination already exists')
        job_id = hashlib.sha256(os.fsencode(path) + b'\0' + source_hash.encode()).hexdigest()
        directory = self.jobs / job_id
        receipt = directory / 'receipt.json'
        if source_proof is not None:
            from publication_guard import Unavailable
            paths = (directory, receipt, directory / 'receipt.new', directory / 'prepared',
                     directory / 'prepared' / name, directory / ('original' + archive_suffix(path)),
                     directory / 'original.pending')
            if any(item.is_symlink() for value in paths for item in (value, *value.parents)):
                raise Unavailable('Linked conversion recovery state')
            if receipt.exists() and (not receipt.is_file() or receipt.stat().st_size > 2097152):
                raise Unavailable('Invalid conversion recovery receipt')
        if receipt.exists():
            self.conversion_check(json.loads(receipt.read_text()))
            return receipt
        directory.mkdir(exist_ok=True, mode=0o700)
        original = directory / ('original' + archive_suffix(path))
        prepared_dir = directory / 'prepared'
        prepared_dir.mkdir(exist_ok=True)
        prepared = prepared_dir / name
        if not original.exists():
            pending = directory / 'original.pending'
            if source_proof is not None and pending.exists():
                raise RuntimeError('Interrupted conversion preservation requires review')
            pending.unlink(missing_ok=True)
            shutil.copy2(path, pending)
            if source_proof is not None:
                pending.chmod(0o600)
            if digest(pending) != source_hash:
                raise RuntimeError('Source changed while saving the recovery copy')
            with pending.open('rb') as stream:
                os.fsync(stream.fileno())
            os.link(pending, original)
            pending.unlink()
            sync_directory(directory)
        if digest(original) != source_hash:
            raise RuntimeError('Original recovery copy does not match source')
        before = self.info(original)
        if not before['page_count']:
            raise ValueError('Archive has no recognizable comic pages')
        if not prepared.exists():
            self.convert_tool('comic-to-cbz', '--apply', '--output', prepared, original)
        if self.info(prepared) != before:
            raise RuntimeError('Converted archive member inventory differs')
        if source_proof is not None:
            private = prepared.stat(follow_symlinks=False)
            if private.st_nlink != 1 or private.st_uid != os.geteuid():
                raise RuntimeError('Aliased conversion preparation requires review')
        os.chmod(prepared, path.stat().st_mode & 0o777)
        if identity(path) != original_identity or digest(path) != source_hash:
            raise RuntimeError('Source changed during conversion')
        sidecars = {}
        for sibling in path.parent.iterdir():
            if sibling.name.startswith(path.stem + '.') and not archive_suffix(sibling):
                if sibling.is_symlink():
                    raise ValueError('Refusing a linked book sidecar')
                if sibling.is_file():
                    shutil.copy2(sibling, prepared_dir / sibling.name)
                    sidecars[sibling.name] = digest(sibling)
        book = books.get(str(path))
        job = dict(source=str(path), destination=str(destination), original=str(original),
                   source_hash=source_hash, source_identity=original_identity,
                   prepared=str(prepared), output_hash=digest(prepared), inventory=before,
                   sidecars=sidecars, book=book, phase='prepared',
                   reader_prepared=str(Path(self.config.get('reader_state', '/normalizer-state')) /
                                       prepared.relative_to(self.state)))
        if source_proof is not None:
            import publication_evidence as evidence
            binding = dict(version=1, **{key: job[key] for key in ('source', 'destination',
                'original', 'prepared', 'source_hash', 'output_hash', 'inventory', 'sidecars',
                'source_identity', 'reader_prepared', 'book')}, proof=source_proof)
            job.update(publication_binding=binding, publication_token=evidence.canonical_digest(binding))
            self.conversion_check(job)
        save(receipt, job)
        return receipt

    def publish(self, job):
        self.conversion_check(job)
        if self.config.get('writer_state') is not None:
            from publication_guard import Unavailable
            raise Unavailable('Conversion publication requires reviewed typed catalog and reader relocation')
        source, destination = Path(job['source']), Path(job['destination'])
        if identity(source) != job['source_identity'] or digest(source) != job['source_hash']:
            raise RuntimeError('Source changed before publication')
        if digest(Path(job['prepared'])) != job['output_hash']:
            raise RuntimeError('Prepared CBZ changed before publication')
        mode = source.stat().st_mode & 0o777
        fd, temporary_name = tempfile.mkstemp(prefix='.cbz-normalize-', suffix='.tmp', dir=source.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, 'wb') as stream, Path(job['prepared']).open('rb') as incoming:
                shutil.copyfileobj(incoming, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, mode)
            if digest(temporary) != job['output_hash'] or digest(source) != job['source_hash']:
                raise RuntimeError('Publication verification failed')
            self.conversion_check(job)
            if destination == source:
                os.replace(temporary, destination)
            else:
                # Atomic no-clobber publication on the library filesystem.
                os.link(temporary, destination)
                sync_directory(source.parent)
                if digest(source) != job['source_hash']:
                    raise RuntimeError('Source changed after publication; retained both files')
                self.conversion_check(job, published=True)
                source.unlink()
            sync_directory(source.parent)
        finally:
            temporary.unlink(missing_ok=True)

    def refresh_mylar(self, job):
        from publication_guard import remote_unlocked, Unavailable
        remote_unlocked(self)
        if self.config.get('writer_state') is not None:
            raise Unavailable('Converted catalog notification requires a typed predecessor handoff')
        settings = self.config.get('mylar')
        if not settings:
            return
        directory = Path(settings.get('config_dir', '/mylar'))
        parser = configparser.ConfigParser()
        parser.read(directory / 'config.ini')
        key = next((parser.get(section, 'api_key') for section in parser.sections()
                    if parser.has_option(section, 'api_key')), None)
        if not key:
            raise RuntimeError('Mylar API key is unavailable')
        with closing(sqlite3.connect(f'file:{directory / "mylar.db"}?mode=ro', uri=True)) as db:
            rows = db.execute('SELECT ComicID, ComicLocation FROM comics').fetchall()
        parent = Path(job['destination']).parent
        matched = False
        for comic_id, location in rows:
            if location and Path(location) == parent:
                matched = True
                result = request(settings['url'], '/api', form={
                    'apikey': key, 'cmd': 'recheckFiles', 'id': comic_id})
                # Native recheckFiles returns JSON null on successful dispatch.
                # Only the versioned tagging endpoint has a durable acknowledgment.
                if result is not None and (not isinstance(result, dict) or result.get('success') is not True):
                    raise RuntimeError('Mylar rejected the series recheck')
        if matched and settings.get('tag_converted', False):
            self.tagging_status(job)
            if settings.get('refresh_reader_after_tagging', False):
                job['mylar_tag_pending'] = True

    def tagging_status(self, job):
        """Duplicate admission reads durable status without rescan or retagging."""
        from publication_guard import remote_unlocked, Unavailable
        remote_unlocked(self)
        if self.config.get('writer_state') is not None:
            raise Unavailable('Converted tagging requires a typed predecessor handoff')
        settings = self.config.get('mylar') or {}
        parser = configparser.ConfigParser()
        parser.read(Path(settings.get('config_dir', '/mylar'))/'config.ini')
        key = next((parser.get(section, 'api_key') for section in parser.sections()
                    if parser.has_option(section, 'api_key')), None)
        if not key:
            raise RuntimeError('Mylar API key is unavailable')
        conversion = dict(version=1, path=job['destination'], sha256=job['output_hash'])
        payload = json.dumps(conversion, sort_keys=True, separators=(',', ':'))
        expected = hashlib.sha256(payload.encode()).hexdigest()
        result = request(settings['url'], '/api', form={
            'apikey': key, 'cmd': 'queueConvertedTag', 'conversion': payload})
        acknowledgment = result.get('data') if isinstance(result, dict) else None
        if (not isinstance(result, dict) or result.get('success') is not True
                or not isinstance(acknowledgment, dict)
                or type(acknowledgment.get('version')) is not int or acknowledgment['version'] != 1
                or acknowledgment.get('key') != expected
                or acknowledgment.get('phase') not in ('queued', 'waiting-library', 'waiting-settings',
                                                       'tagging', 'retry', 'review', 'completed')):
            raise RuntimeError('Mylar did not acknowledge converted tagging; notification retained')
        job['mylar_tag_key'] = expected
        return acknowledgment['phase']

    def refresh_tagged(self, job):
        """Request idempotent reader metadata refresh after verified Mylar completion."""
        from publication_guard import remote_unlocked, Unavailable
        remote_unlocked(self)
        if self.config.get('writer_state') is not None:
            raise Unavailable('Converted reader notification requires a typed predecessor handoff')
        if not (self.config.get('mylar') or {}).get('refresh_reader_after_tagging', False):
            job.pop('mylar_tag_pending', None)
            job['mylar_reader_refresh'] = 'disabled'
            return
        phase = self.tagging_status(job)
        if phase == 'review':
            job.pop('mylar_tag_pending', None)
            job['mylar_reader_refresh'] = 'tagging requires review'
        elif phase == 'completed':
            book_id = job.get('replacement_id')
            if not isinstance(book_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', book_id):
                raise ValueError('Converted reader book identity is unavailable')
            self.reader.refresh_metadata(book_id)
            job.pop('mylar_tag_pending', None)
            job['mylar_reader_refresh'] = 'metadata refresh requested'
            job['mylar_reader_refresh_at'] = time.time()

    def advance(self, receipt, books):
        job = json.loads(receipt.read_text())
        if job['phase'] == 'done':
            return
        source, destination = Path(job['source']), Path(job['destination'])
        # Resolve a crash after publication before doing any further mutation.
        published = destination.is_file() and digest(destination) == job['output_hash']
        self.conversion_check(job, published=published)
        if self.config.get('writer_state') is not None:
            from publication_guard import Unavailable
            raise Unavailable('Conversion recovery retains its source until typed relocation is verified')
        if job['phase'] == 'prepared' and not published:
            if job['book'] and source != destination:
                if identity(source) != job['source_identity'] or digest(source) != job['source_hash']:
                    raise RuntimeError('Source changed before reader upgrade')
                job['phase'] = 'submitted'
                job['submitted_at'] = time.time()
                save(receipt, job)  # Never blindly resubmit an ambiguously accepted API request.
                self.reader.upgrade(job)
                return
            self.publish(job)
            published = True
        if not published:
            if job['phase'] == 'submitted' and time.time() - job['submitted_at'] > 600:
                raise RuntimeError('Reader upgrade is unconfirmed; recovery receipt retained for review')
            return
        if source != destination and source.exists():
            # A pending native upgrade owns its source until Komga confirms replacement.
            if job['phase'] == 'submitted':
                return
            if digest(source) != job['source_hash']:
                raise RuntimeError('Source changed; refusing cleanup')
            self.conversion_check(job, published=True)
            source.unlink()
            sync_directory(source.parent)
        if job['phase'] in ('prepared', 'submitted'):
            job['phase'] = 'refresh'
            save(receipt, job)
            if source == destination and job['book']:
                self.reader.analyze(job['book']['id'])
            else:
                self.reader.scan()
        current = books.get(str(destination))
        if not current or current['media']['status'] != 'READY':
            # Analysis/scan can be retried safely after a connection failure.
            if job['book'] and source == destination:
                self.reader.analyze(job['book']['id'])
            else:
                self.reader.scan()
            return
        if current['media']['pagesCount'] != job['inventory']['page_count']:
            raise RuntimeError('Reader page count differs from the verified archive')
        if job['book'] and source != destination and current['id'] == job['book']['id']:
            return
        prior_progress = (job.get('book') or {}).get('readProgress')
        if prior_progress:
            current_progress = current.get('readProgress') or {}
            if (current_progress.get('page', 0) < prior_progress.get('page', 0)
                    or prior_progress.get('completed') and not current_progress.get('completed')):
                raise RuntimeError('Reader progress preservation needs review')
        for name, expected in job['sidecars'].items():
            if digest(destination.parent / name) != expected:
                raise RuntimeError('Book sidecar preservation check failed')
        if self.config.get('writer_state'):
            # Persist the notification before releasing ownership. The guarded
            # Mylar rescan must run only after our complete cycle releases flock.
            job['mylar_refresh_pending'] = True
        else:
            self.refresh_mylar(job)
        job['replacement_id'] = current['id']
        job['phase'] = 'done'
        job['completed_at'] = time.time()
        save(receipt, job)
        print(json.dumps({'event': 'converted', 'source': job['source'],
                          'pages': job['inventory']['page_count']}), flush=True)

    def prepare_cycle(self):
        """Collect one immutable bounded reader observation before writer exclusion."""
        if self.config.get('writer_state') is None:
            return
        from publication_guard import remote_unlocked, Unavailable
        import publication_evidence as evidence
        remote_unlocked(self)
        self.reader_snapshot = None
        books = self.reader.books()
        if not isinstance(books, dict) or len(books) > evidence.CATALOG_ROWS:
            raise Unavailable('Reader snapshot exceeds bounded library observation')
        # Reader responses include large optional metadata. Preserve only the
        # native upgrade/recovery facts that this worker actually consumes.
        projection = {}
        for path, book in books.items():
            if not isinstance(path, str) or not isinstance(book, dict):
                raise Unavailable('Malformed reader library observation')
            projection[path] = {key: book[key] for key in
                                ('id', 'seriesId', 'media', 'readProgress') if key in book}
        raw = evidence.compact(projection)
        if len(raw) > evidence.CATALOG_BYTES:
            raise Unavailable('Reader snapshot exceeds bounded library observation')
        self.reader_snapshot = (threading.get_ident(), time.monotonic(), raw)

    def cycle(self):
        self.errors = []
        coordinated = self.config.get('writer_state') is not None
        if coordinated:
            from publication_guard import current, Unavailable
            import publication_evidence as evidence
            current(self).admission()
            snapshot = getattr(self, 'reader_snapshot', None)
            self.reader_snapshot = None
            if (not isinstance(snapshot, tuple) or len(snapshot) != 3
                    or snapshot[0] != threading.get_ident()
                    or not 0 <= time.monotonic() - snapshot[1] <= 120
                    or not isinstance(snapshot[2], bytes) or len(snapshot[2]) > evidence.CATALOG_BYTES):
                raise Unavailable('Fresh outside-writer reader snapshot required')
            books = evidence.decode_json(snapshot[2])
            if not isinstance(books, dict):
                raise Unavailable('Invalid immutable reader snapshot')
        else:
            books = self.reader.books()  # No media mutation while reader state is unavailable.
        pending_sources = set()
        for receipt in sorted(self.jobs.glob('*/receipt.json')):
            job = json.loads(receipt.read_text())
            if job['phase'] != 'done':
                pending_sources.add(job['source'])
                try:
                    self.advance(receipt, books)
                except Exception as exc:
                    self.errors.append({'path': job['source'], 'error': str(exc)})
        for path in self.candidates():
            if str(path) in pending_sources:
                continue
            rejected = self.rejected.get(str(path))
            if rejected and rejected[0] == identity(path) and time.time() - rejected[1] < 3600:
                self.errors.append({'path': str(path), 'error': rejected[2]})
                continue
            try:
                # Let the reader register formats it already recognizes first. This
                # ensures its native upgrade operation transfers existing user state.
                if not coordinated:
                    books = self.reader.books()
                if path.suffix.lower() in ('.cbr', '.rar', '.zip', '.pdf') and str(path) not in books:
                    if coordinated:
                        raise Unavailable('Unindexed conversion needs a typed reader discovery handoff')
                    self.reader.scan()
                    continue
                self.advance(self.prepare(path, books), books)
            except PDFPending:
                continue
            except Exception as exc:
                self.errors.append({'path': str(path), 'error': str(exc)})
                if path.exists():
                    self.rejected[str(path)] = (identity(path), time.time(), str(exc))
        phases = [json.loads(path.read_text())['phase']
                  for path in self.jobs.glob('*/receipt.json')]
        save(self.state / 'status.json', {'checked_at': time.time(), 'errors': self.errors,
                                         'pending': sum(phase != 'done' for phase in phases),
                                         'completed': phases.count('done')})
        for error in self.errors:
            print(json.dumps({'event': 'error', **error}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='/config/normalizer.json')
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--health', action='store_true')
    parser.add_argument('--naming-plan', metavar='MANIFEST')
    parser.add_argument('--naming-apply', metavar='MANIFEST')
    parser.add_argument('--naming-limit', type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.naming_limit <= 100 or (args.naming_plan and args.naming_apply):
        parser.error('Choose one naming action and a limit from 1 to 100')
    config = json.loads(Path(args.config).read_text())
    state = Path(config.get('state', '/state'))
    if args.health:
        if time.time() - (state / 'heartbeat').stat().st_mtime > 90:
            raise SystemExit(1)
        conversion = json.loads((state / 'status.json').read_text())
        if conversion.get('errors') or time.time() - conversion['checked_at'] > 900:
            raise SystemExit(1)
        if config.get('reader_scan', {}).get('enabled'):
            scan = json.loads((state / 'reader-scan-status.json').read_text())
            if scan.get('errors') or time.time() - scan['checked_at'] > 900:
                raise SystemExit(1)
        if config.get('maintenance', {}).get('enabled'):
            result = json.loads((state / 'maintenance-status.json').read_text())
            limit = max(180, config['maintenance'].get('interval_seconds', 300) * 3)
            if result.get('errors') or time.time() - result['checked_at'] > limit:
                raise SystemExit(1)
        return
    normalizer = Normalizer(config)
    normalizer.pdf_defer = True
    maintenance = None
    if config.get('maintenance', {}).get('enabled'):
        from maintenance import Maintenance
        maintenance = Maintenance(normalizer)
    with (state / 'worker.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.naming_plan or args.naming_apply or normalizer.naming_rules['enabled']:
            from naming_worker import Naming
            normalizer.naming = Naming(normalizer)
        if args.naming_plan:
            save(Path(args.naming_plan), normalizer.naming.plan())
            return
        if args.naming_apply:
            result = normalizer.naming.apply(json.loads(Path(args.naming_apply).read_text()), args.naming_limit)
            print(json.dumps({'phases': [row['phase'] for row in result]}), flush=True)
            return
        if normalizer.naming:
            normalizer.naming.initialize()
        if normalizer.scan_batch:
            normalizer.scan_batch.initialize()
        def heartbeat():
            while True:
                (state / 'heartbeat').touch()
                time.sleep(20)
        threading.Thread(target=heartbeat, daemon=True).start()
        while True:
            try:
                from writer_cycle import cycle
                cycle(normalizer, maintenance)
            except Exception as exc:
                save(state / 'status.json', {'checked_at': time.time(),
                                            'errors': [{'error': str(exc)}]})
                print(json.dumps({'event': 'cycle_failed', 'error': str(exc)}), flush=True)
                if args.once:
                    raise
            from pdf_conversion import render_pending
            render_pending(normalizer)  # Preserved inputs only; shared media writer has been released.
            if args.once:
                return
            time.sleep(config.get('poll_seconds', 60))


if __name__ == '__main__':
    main()
