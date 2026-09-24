"""Normalize comic containers through archiving-utils and the reader APIs."""

import argparse
import configparser
import fcntl
import hashlib
import json
import os
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

SUFFIXES = ('.cbt.tar.zst', '.cbt.tar.gz', '.cbt.tar.bz2', '.cbt.tar.xz',
            '.cbt.zst', '.cbt.bz2', '.cbt.gz', '.cbt.xz', '.tar.zst', '.tar.bz2',
            '.tar.gz', '.tar.xz', '.cbz', '.cbr', '.cb7', '.cbt', '.zip', '.rar',
            '.7z', '.tar', '.tgz', '.tbz2', '.txz', '.tzst', '.cba', '.ace')


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
        self.observed = {}
        self.errors = []
        self.rejected = {}

    def convert_tool(self, *args):
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

    def prepare(self, path, books):
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
        if receipt.exists():
            return receipt
        directory.mkdir(exist_ok=True)
        original = directory / ('original' + archive_suffix(path))
        prepared_dir = directory / 'prepared'
        prepared_dir.mkdir(exist_ok=True)
        prepared = prepared_dir / name
        if not original.exists():
            pending = directory / 'original.pending'
            pending.unlink(missing_ok=True)
            shutil.copy2(path, pending)
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
        save(receipt, job)
        return receipt

    def publish(self, job):
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
            if destination == source:
                os.replace(temporary, destination)
            else:
                # Atomic no-clobber publication on the library filesystem.
                os.link(temporary, destination)
                sync_directory(source.parent)
                if digest(source) != job['source_hash']:
                    raise RuntimeError('Source changed after publication; retained both files')
                source.unlink()
            sync_directory(source.parent)
        finally:
            temporary.unlink(missing_ok=True)

    def refresh_mylar(self, job):
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
        for comic_id, location in rows:
            if location and Path(location) == parent:
                result = request(settings['url'], '/api', form={
                    'apikey': key, 'cmd': 'recheckFiles', 'id': comic_id})
                if isinstance(result, dict) and result.get('success') is False:
                    raise RuntimeError('Mylar rejected the series recheck')

    def advance(self, receipt, books):
        job = json.loads(receipt.read_text())
        if job['phase'] == 'done':
            return
        source, destination = Path(job['source']), Path(job['destination'])
        # Resolve a crash after publication before doing any further mutation.
        published = destination.is_file() and digest(destination) == job['output_hash']
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
            source.unlink()
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
        self.refresh_mylar(job)
        job['replacement_id'] = current['id']
        job['phase'] = 'done'
        job['completed_at'] = time.time()
        save(receipt, job)
        print(json.dumps({'event': 'converted', 'source': job['source'],
                          'pages': job['inventory']['page_count']}), flush=True)

    def cycle(self):
        self.errors = []
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
                books = self.reader.books()
                if path.suffix.lower() in ('.cbr', '.rar', '.zip') and str(path) not in books:
                    self.reader.scan()
                    continue
                self.advance(self.prepare(path, books), books)
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
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    state = Path(config.get('state', '/state'))
    if args.health:
        if time.time() - (state / 'heartbeat').stat().st_mtime > 90:
            raise SystemExit(1)
        conversion = json.loads((state / 'status.json').read_text())
        if conversion.get('errors') or time.time() - conversion['checked_at'] > 900:
            raise SystemExit(1)
        if config.get('maintenance', {}).get('enabled'):
            result = json.loads((state / 'maintenance-status.json').read_text())
            limit = max(180, config['maintenance'].get('interval_seconds', 300) * 3)
            if result.get('errors') or time.time() - result['checked_at'] > limit:
                raise SystemExit(1)
        return
    normalizer = Normalizer(config)
    maintenance = None
    if config.get('maintenance', {}).get('enabled'):
        from maintenance import Maintenance
        maintenance = Maintenance(normalizer)
    with (state / 'worker.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        def heartbeat():
            while True:
                (state / 'heartbeat').touch()
                time.sleep(20)
        threading.Thread(target=heartbeat, daemon=True).start()
        while True:
            try:
                normalizer.cycle()
                if maintenance:
                    maintenance.cycle()
            except Exception as exc:
                save(state / 'status.json', {'checked_at': time.time(),
                                            'errors': [{'error': str(exc)}]})
                print(json.dumps({'event': 'cycle_failed', 'error': str(exc)}), flush=True)
                if args.once:
                    raise
            if args.once:
                return
            time.sleep(config.get('poll_seconds', 60))


if __name__ == '__main__':
    main()
