"""Bounded native release naming with content and reader restoration proofs."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import time
import tempfile

from normalize import api_path, digest, identity, save, sync_directory
from release_naming import policy, render
from maintenance import Maintenance, scoped_file
from media_writer import Writer


def reader_hash(path):
    import xxhash
    result = xxhash.xxh3_128()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            result.update(block)
    return result.hexdigest()


def token(request):
    return hashlib.sha256(json.dumps(request, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def all_books(reader):
    result = []; page = 0
    while True:
        data = reader.call(f'/api/v1/books/list?page={page}&size=500', {})
        result.extend(data['content'])
        if data.get('last', True):return result
        page += 1


class Naming:
    def __init__(self, worker):
        self.worker = worker
        self.rules = policy(worker.config)
        self.root = worker.state/'release-naming'
        self.root.mkdir(mode=0o700, exist_ok=True)
        info = self.root.lstat()
        if (self.root.is_symlink() or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o700):
            raise ValueError('Release naming state must be private and owned')
        self.state_path = self.root/'catalog.json'
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else None
        if self.state is not None and (self.state.get('version') != 1 or not isinstance(self.state.get('known'), dict)):
            raise ValueError('Release naming catalog state requires review')

    def api(self, command, **values):
        return Maintenance.mylar(self, command, **values)

    def catalog(self):
        result = {}
        directory = Path(self.worker.config['mylar']['config_dir'])
        with closing(sqlite3.connect((directory/'mylar.db').as_uri()+'?mode=ro', uri=True)) as db:
            for table in ('issues', 'annuals'):
                extra = ' AND COALESCE(i.Deleted,0)=0' if table == 'annuals' else ' AND NOT EXISTS (SELECT 1 FROM annuals a WHERE a.IssueID=i.IssueID)'
                rows = db.execute('SELECT i.IssueID,i.ComicID,c.ComicLocation,i.Location FROM '+table+
                                  " i JOIN comics c ON c.ComicID=i.ComicID WHERE i.Status IN ('Downloaded','Archived')"+extra)
                for issue, comic, folder, location in rows:
                    if not folder or not location or Path(location).name != location:continue
                    path = Path(folder)/location
                    if path.is_absolute() and '..' not in path.parts and path.suffix.lower() == '.cbz' and scoped_file(path, self.worker.roots):
                        result[table+':'+str(issue)] = dict(issueid=str(issue), comicid=str(comic), source=str(path))
        return result

    def reader_proof(self, path, books):
        matches = [book for book in books if not book.get('deleted') and api_path(book['url']) == path]
        if len(matches) != 1:raise ValueError('Reader source path needs review')
        book = matches[0]; checksum = reader_hash(path)
        if (book.get('fileHash') != checksum or book.get('media', {}).get('status') != 'READY'
                or sum(other.get('fileHash') == checksum for other in books) != 1):
            raise ValueError('Reader hash is stale or ambiguous; review required')
        return dict(id=book['id'], hash=checksum, pages=book['media']['pagesCount'],
                    progress=book.get('readProgress'), seriesid=book['seriesId'], libraryid=book['libraryId'])

    def plan(self, limit=10000):
        result = []; books = all_books(self.worker.reader)
        for row in list(self.catalog().values())[:limit]:
            path = Path(row['source'])
            try:
                proposal = self.api('getReleaseNaming', source=str(path))
                target = render(proposal)
                request = {name:proposal[name] for name in ('version','source','sha256','issueid','comicid')}
                request['target'] = target
                if target == path.name:
                    result.append(dict(row, phase='unchanged')); continue
                if any(p.name.casefold() == target.casefold() for p in path.parent.iterdir()):
                    raise ValueError('Release destination collision')
                proof = self.reader_proof(path, books)
                result.append(dict(row, phase='planned', proposal=proposal, request=request, reader=proof))
            except (ValueError, RuntimeError) as error:
                result.append(dict(row, phase='review', reason=str(error)))
        owned = {row['source'] for row in self.catalog().values()}
        for root in self.worker.roots:
            for path in root.rglob('*'):
                if path.suffix.lower() not in ('.cbz', '.cbr', '.cb7', '.pdf') or str(path) in owned:
                    continue
                reason = 'Uncataloged publication, alternate or supplement requires explicit identity'
                if path.suffix.lower() != '.cbz':reason = 'Preserved format is outside CBZ release naming'
                if not scoped_file(path, self.worker.roots):reason = 'Unsafe or linked publication path'
                result.append(dict(source=str(path), phase='review', reason=reason))
        return dict(version=1, created_at=time.time(), entries=result)

    def prepare(self, entry):
        path = Path(entry['source'])
        if not scoped_file(path, self.worker.roots):raise ValueError('Release source scope changed')
        request = entry['request']; folder = self.root/token(request)
        if folder.exists():
            if folder.is_symlink() or not (folder/'receipt.json').is_file():
                raise ValueError('Incomplete release preparation requires review')
            return folder
        fresh = self.api('getReleaseNaming', source=str(path))
        expected = {name:fresh[name] for name in ('version','source','sha256','issueid','comicid')}
        expected['target'] = render(fresh)
        if fresh != entry['proposal'] or expected != request:
            raise ValueError('Release naming plan is stale')
        proof = self.reader_proof(path, all_books(self.worker.reader))
        if proof != entry['reader']:raise ValueError('Reader naming plan is stale')
        with Writer(self.worker.config['writer_state']).hold(timeout=0):
            before = identity(path)
            if digest(path) != request['sha256']:raise ValueError('Release source changed')
            staging = Path(tempfile.mkdtemp(prefix='.'+token(request)+'.preparing-', dir=self.root))
            for name in ('original.cbz', 'restore.cbz'):
                shutil.copy2(path, staging/name)
                if digest(staging/name) != request['sha256']:raise ValueError('Release preservation copy verification failed')
                with (staging/name).open('rb') as stream:os.fsync(stream.fileno())
            # Verify every archive member in the isolated restore before native publication.
            import zipfile
            with zipfile.ZipFile(staging/'restore.cbz') as archive:
                if archive.testzip() is not None:raise ValueError('Release restore archive failed integrity')
            if identity(path) != before:raise ValueError('Release source changed during preservation')
            sync_directory(staging)
            save(staging/'receipt.json', dict(entry, phase='prepared', key=token(request)))
            if folder.exists():raise ValueError('Release preparation destination exists')
            staging.rename(folder); sync_directory(self.root)
        return folder

    def advance(self, folder, *, defer_scan=False, reader_books=None):
        receipt = folder/'receipt.json'; job = json.loads(receipt.read_text())
        if job['phase'] in ('done', 'review'):return job
        request = job['request']; destination = Path(request['source']).with_name(request['target'])
        if job['phase'] == 'prepared':
            job['phase'] = 'native-uncertain'; save(receipt, job)
            try:
                response = self.api('renameLibraryFile', naming=json.dumps(request))
            except Exception:
                return job  # Reconcile the durable native journal; never replay an uncertain mutation.
            if response.get('phase') != 'committed' or response.get('key') != job['key']:
                raise ValueError('Native naming acknowledgement mismatch')
            job['phase'] = 'native-committed'; save(receipt, job)
        elif job['phase'] == 'native-uncertain':
            status = self.api('releaseNamingStatus', token=job['key'])
            if status.get('phase') == 'committed':
                job['phase'] = 'native-committed'; save(receipt, job)
            elif status.get('phase') in ('absent', 'rejected'):
                job.update(phase='review', reason='Uncertain native admission needs review'); save(receipt, job)
                return job
            else:return job
        if job['phase'] == 'native-committed':
            if not scoped_file(destination, self.worker.roots) or digest(destination) != request['sha256']:
                raise ValueError('Renamed release content changed')
            if Path(request['source']).exists():raise ValueError('Original naming path still exists')
            catalog = self.catalog()
            if not any(r['issueid'] == request['issueid'] and r['comicid'] == request['comicid']
                       and r['source'] == str(destination) for r in catalog.values()):
                raise ValueError('Renamed release catalog acknowledgement missing')
            job['phase'] = 'reader-pending'; save(receipt, job)
            if defer_scan:
                return job
            self.worker.reader.call('/api/v1/libraries/'+job['reader']['libraryid']+'/scan', {})
            job['scan_at'] = time.time(); save(receipt, job)
        if job['phase'] == 'reader-pending':
            books = reader_books if reader_books is not None else all_books(self.worker.reader)
            matches = [b for b in books if not b.get('deleted') and api_path(b['url']) == destination]
            if len(matches) != 1 or matches[0].get('media', {}).get('status') != 'READY':
                if time.time()-job.get('scan_at',0) > 300:
                    self.worker.reader.call('/api/v1/libraries/'+job['reader']['libraryid']+'/scan', {})
                    job['scan_at'] = time.time(); save(receipt, job)
                return job
            book = matches[0]; old = job['reader']; progress = old['progress']
            if book.get('fileHash') != old['hash'] or book['media']['pagesCount'] != old['pages']:
                raise ValueError('Renamed reader content mismatch')
            current = book.get('readProgress')
            if progress and (not current or current.get('page',0) < progress.get('page',0)
                             or (progress.get('completed') and not current.get('completed'))):
                raise ValueError('Renamed reader progress lost')
            if any(not b.get('deleted') and api_path(b['url']) == Path(request['source']) for b in books):
                return job
            if digest(destination) != request['sha256']:raise ValueError('Renamed release changed during reader verification')
            job.update(phase='done', reader_bookid=book['id'], verified_at=time.time()); save(receipt, job)
            # Compact receipts remain; remove only verified temporary copies for this entry.
            (folder/'original.cbz').unlink(missing_ok=True); (folder/'restore.cbz').unlink(missing_ok=True)
            sync_directory(folder)
            for staging in self.root.glob('.'+job['key']+'.preparing-*'):
                if (not staging.is_symlink() and staging.is_dir()
                        and all(p.name in {'original.cbz','restore.cbz','receipt.json','receipt.new'}
                                and not p.is_symlink() for p in staging.iterdir())):
                    shutil.rmtree(staging)
            sync_directory(self.root)
        return job

    def apply(self, manifest, limit=1):
        if (type(manifest.get('version')) is not int or manifest.get('version') != 1
                or not isinstance(manifest.get('entries'), list) or type(limit) is not int or not 1 <= limit <= 100):
            raise ValueError('Invalid release naming manifest or batch limit')
        # Reconcile the last bounded batch before accepting additional media changes.
        active = [p.parent for p in sorted(self.root.glob('*/receipt.json'))
                  if not p.parent.name.startswith('.') and json.loads(p.read_text())['phase'] not in ('done', 'review')]
        books = all_books(self.worker.reader) if active else None
        results = [self.advance(folder, reader_books=books) for folder in active]
        if any(row['phase'] not in ('done', 'review') for row in results):return results
        results = []; pending = []
        try:
            for entry in manifest['entries']:
                if entry.get('phase') != 'planned':continue
                folder = self.root/token(entry['request'])
                if (folder/'receipt.json').exists() and json.loads((folder/'receipt.json').read_text())['phase'] in ('done', 'review'):
                    continue
                folder = self.prepare(entry)
                job = self.advance(folder, defer_scan=True)
                results.append(job)
                if job['phase'] == 'reader-pending':pending.append((folder, job))
                if job['phase'] == 'native-uncertain' or len(results) >= limit:break
        finally:
            # One scan per library, including after a later entry fails preflight.
            for library in {job['reader']['libraryid'] for _,job in pending}:
                self.worker.reader.call('/api/v1/libraries/'+library+'/scan', {})
            for folder,job in pending:
                job['scan_at'] = time.time(); save(folder/'receipt.json', job)
        return results

    def reconcile(self):
        """Ask the native owner to recover before ordinary writer admission."""
        for receipt in sorted(self.root.glob('*/receipt.json')):
            if receipt.parent.name.startswith('.'):continue
            job = json.loads(receipt.read_text())
            if job['phase'] in ('native-uncertain', 'native-committed', 'reader-pending'):
                self.advance(receipt.parent)

    def initialize(self):
        if self.state is None:
            self.state = dict(version=1, known=self.catalog())
            save(self.state_path, self.state)

    def tick(self):
        # Complete existing work before accepting another rename or reader scan.
        for receipt in sorted(self.root.glob('*/receipt.json')):
            if receipt.parent.name.startswith('.'):continue
            job = json.loads(receipt.read_text())
            if job['phase'] not in ('done', 'review'):
                self.advance(receipt.parent); return
        current = self.catalog()
        if self.state is None:
            self.state = dict(version=1, known=current)
            save(self.state_path,self.state); return
        pending = [row for key,row in current.items() if self.state['known'].get(key) != row]
        books = all_books(self.worker.reader) if pending else []
        completed = 0
        for row in pending:
            path = Path(row['source'])
            try:
                proposal = self.api('getReleaseNaming', source=str(path)); target = render(proposal)
                if target == path.name:
                    self.state['known'][next(k for k,v in current.items() if v == row)] = row
                    self.state.setdefault('waiting', {}).pop(row['source'], None)
                    continue
                request = {name:proposal[name] for name in ('version','source','sha256','issueid','comicid')};request['target']=target
                entry = dict(row,phase='planned',proposal=proposal,request=request,reader=self.reader_proof(path,books))
                job = self.advance(self.prepare(entry))
                if job['phase'] not in ('done','review'):return
                key = next(k for k,v in current.items() if v == row)
                self.state['known'][key] = self.catalog().get(key, row)
                self.state.setdefault('waiting', {}).pop(row['source'], None)
                completed += 1
                if completed >= self.rules['batch_size']:break
            except (ValueError, RuntimeError) as error:
                # Keep retrying incomplete metadata without blocking unrelated publications.
                self.state.setdefault('waiting', {})[row['source']] = dict(reason=str(error), checked_at=time.time())
                continue
        save(self.state_path,self.state)
