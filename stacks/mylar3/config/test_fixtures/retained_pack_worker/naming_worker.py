"""Bounded native release naming with content and reader restoration proofs."""
from contextlib import closing, contextmanager
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
from publication_guard import scope, remote_unlocked, current, Unavailable
import publication_evidence as evidence


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
        if (not isinstance(data, dict) or not isinstance(data.get('content'), list)
                or len(data['content']) > 500 or len(result)+len(data['content']) > 100000):
            raise ValueError('Reader catalog exceeds naming proof bounds')
        result.extend(data['content'])
        if type(data.get('last', True)) is not bool:raise ValueError('Invalid reader pagination proof')
        if data.get('last', True):return result
        if page >= 199:raise ValueError('Reader pagination exceeds naming proof bounds')
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
        self.root_identity = (info.st_dev, info.st_ino)
        self.state_path = self.root/'catalog.json'
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else None
        if self.state is not None and (self.state.get('version') != 1 or not isinstance(self.state.get('known'), dict)):
            raise ValueError('Release naming catalog state requires review')

    def api(self, command, **values):
        return Maintenance.mylar(self, command, **values)

    @contextmanager
    def authority(self):
        try:
            active = current(self.worker)
        except Unavailable:
            writer = Writer(self.worker.config['writer_state'])
            with writer.hold(timeout=0), scope(self.worker, writer) as active:
                yield active
        else:
            yield active

    def publication(self, path, request):
        """Reobserve the complete census and this exact current catalog archive."""
        if self.worker.config.get('writer_state') is None:
            return None
        match = {key: request[key] for key in ('issueid', 'comicid')}
        with self.authority() as authority:
            if not evidence.same_json(authority.target_match(path), match):
                raise ValueError('Naming catalog owner changed')
            return authority.confirmation_check(path, path, match)

    def preparation_binding(self, job):
        return evidence.canonical_digest({name: job.get(name) for name in
            ('request','reader','publication','preservation_facts')})

    def read_receipt(self, folder):
        folder = Path(folder)
        root = self.root.lstat()
        if (root.st_dev, root.st_ino) != self.root_identity:
            raise ValueError('Naming state identity changed')
        if (folder.parent != self.root or any(p.is_symlink() for p in (folder, *folder.parents))):
            raise ValueError('Unsafe naming receipt directory')
        directory = folder.lstat()
        if (not stat.S_ISDIR(directory.st_mode) or directory.st_uid != os.geteuid()
                or directory.st_mode & 0o077):
            raise ValueError('Unsafe naming receipt directory')
        receipt = folder/'receipt.json'
        saved = receipt.lstat()
        if (not stat.S_ISREG(saved.st_mode) or saved.st_nlink != 1 or saved.st_uid != os.geteuid()
                or saved.st_mode & 0o022 or saved.st_size > 2*1024*1024):
            raise ValueError('Unsafe naming receipt')
        raw = receipt.read_text()
        if evidence.signature(receipt.lstat()) != evidence.signature(saved):
            raise ValueError('Naming receipt changed during read')
        job = json.loads(raw)
        request = job.get('request')
        if (not isinstance(request, dict) or type(request.get('version')) is not int
                or request['version'] not in (1, 2)
                or set(request) != ({'version','source','target','sha256','issueid','comicid'}
                                  | ({'retry_of'} if request['version'] == 2 else set()))
                or job.get('key') != token(request) or folder.name != job.get('key')
                or job.get('phase') not in ('prepared','native-uncertain','native-committed','reader-pending','done','review')):
            raise ValueError('Naming receipt binding changed')
        if not isinstance(request['source'], str):raise ValueError('Invalid naming source spelling')
        path = Path(request['source'])
        if (not path.is_absolute() or '..' in path.parts or not isinstance(request['target'], str)
                or Path(request['target']).name != request['target'] or request['target'] in ('', '.', '..') or '\\' in request['target']
                or not request['target'].lower().endswith('.cbz')
                or not isinstance(request['sha256'], str) or len(request['sha256']) != 64
                or any(c not in '0123456789abcdef' for c in request['sha256'])
                or any(not isinstance(request[n], str) or not request[n].isdigit()
                       or not 1 <= len(request[n]) <= 16 or request[n][0] == '0'
                       for n in ('issueid','comicid'))):
            raise ValueError('Unsafe naming request')
        binding = job.get('preparation_binding')
        if ((binding is not None and binding != self.preparation_binding(job))
                or (job.get('publication') is not None and binding is None)):
            raise ValueError('Naming preparation binding changed')
        return job

    def copies(self, folder, request):
        """Copies remain owned exact witnesses; never unlink foreign replacements."""
        signatures = {}
        for name in ('original.cbz', 'restore.cbz'):
            path = folder/name
            saved = path.lstat()
            if (not stat.S_ISREG(saved.st_mode) or saved.st_nlink != 1 or saved.st_uid != os.geteuid()
                    or any(p.is_symlink() for p in (path, *path.parents))
                    or digest(path) != request['sha256']
                    or evidence.signature(path.lstat()) != evidence.signature(saved)):
                raise ValueError('Naming preservation copy changed')
            signatures[name] = evidence.signature(saved)
        return signatures

    def scan(self, folder, job):
        from reader_handoff import queue
        request = job['request']
        target = Path(request['source']).with_name(request['target'])
        with self.authority():
            self.publication(target, request)
            result = queue(self.worker, 'library_scan', [dict(source=str(target), target=str(target),
                match={key: request[key] for key in ('issueid','comicid')})], folder=target.parent)
        if result is not None:
            job['scan_at'] = time.time()
            save(folder/'receipt.json', job)
        return result

    def catalog(self):
        if self.worker.config.get('writer_state') is None:
            return self.catalog_rows()
        with self.authority() as authority:
            return self.catalog_rows(authority)

    def catalog_rows(self, authority=None):
        result = {}
        directory = Path(self.worker.config['mylar']['config_dir'])
        with closing(sqlite3.connect((directory/'mylar.db').as_uri()+'?mode=ro', uri=True)) as db:
            for table in ('comics','issues','annuals'):
                if db.execute('SELECT count(*) FROM '+table).fetchone()[0] > evidence.CATALOG_ROWS:
                    raise ValueError('Naming catalog exceeds proof bounds')
            for table in ('issues', 'annuals'):
                extra = ' AND COALESCE(i.Deleted,0)=0' if table == 'annuals' else ' AND NOT EXISTS (SELECT 1 FROM annuals a WHERE a.IssueID=i.IssueID)'
                rows = db.execute('SELECT i.IssueID,i.ComicID,c.ComicLocation,i.Location FROM '+table+
                                  " i JOIN comics c ON c.ComicID=i.ComicID WHERE i.Status IN ('Downloaded','Archived')"+extra)
                for issue, comic, folder, location in rows:
                    if not folder or not location or Path(location).name != location:continue
                    path = Path(folder)/location
                    if authority is not None:path = authority.mapped(str(path))
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

    def plan(self, limit=10000, *, combined=None):
        remote_unlocked(self.worker)
        # This is an explicit reviewed supplement preview, never automatic credit approval.
        reviews = None
        if combined is not None:
            from combined_handoff import reviewed_preview
            reviews = reviewed_preview(combined)
            health=self.api('getHealth')
            if not isinstance(health,dict) or type(health.get('combined_preview')) is not int or health['combined_preview']!=1:
                raise ValueError('Current native supplementation preview capability required')
        result = []; books = all_books(self.worker.reader)
        for row in list(self.catalog().values())[:limit]:
            path = Path(row['source'])
            try:
                proposal = self.api('getReleaseNaming', source=str(path))
                target = render(proposal)
                request = {name:proposal[name] for name in ('version','source','sha256','issueid','comicid')}
                request['target'] = target
                preview = None
                if reviews is not None:
                    preview = reviews.get(str(path))
                    if preview is None or preview['source_sha256'] != request['sha256']:
                        raise ValueError('Exact reviewed supplement preview required')
                    if digest(path) != request['sha256']:
                        raise ValueError('Reviewed supplement source changed')
                native=None
                if preview is not None:
                    from combined_handoff import native_source,native_preview
                    native_request=dict(request,source=native_source(self,path))
                    native=self.api('combinedPublication',request=json.dumps(dict(version=1,action='preview',
                        arguments=dict(naming=native_request,policy=combined['policy']))))
                    native_preview(native,native_request,combined['policy'])
                    if not evidence.same_json(native['additions'],preview['additions']):
                        raise ValueError('Approved additions differ from actual native derivation')
                if target == path.name and (preview is None or not native['additions']):
                    result.append(dict(row, phase='unchanged')); continue
                if target != path.name and any(p.name.casefold() == target.casefold() for p in path.parent.iterdir()):
                    raise ValueError('Release destination collision')
                proof = self.reader_proof(path, books)
                entry = dict(row, phase='planned', proposal=proposal, request=request, reader=proof)
                if preview is not None:
                    if digest(path) != request['sha256']:
                        raise ValueError('Reviewed supplement source changed during reader proof')
                    entry['metadata_review'] = {key: preview[key] for key in ('status','source_sha256','evidence')}
                    entry['metadata_plan'] = dict(version=1, additions=preview['additions'],
                        policy_sha256=evidence.canonical_digest(combined['policy']),native_preview=native)
                result.append(entry)
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
        manifest = dict(version=1, created_at=time.time(), entries=result)
        if combined is not None:
            manifest.update(kind='combined-root-v1', policy=combined['policy'])
        return manifest

    def recovery_entry(self, predecessor, preservation=None):
        """Explicitly replace a rejected attempt; ordinary ticks never call this."""
        remote_unlocked(self.worker)
        if (not self.rules['enabled'] or not isinstance(predecessor, str)
                or len(predecessor) != 64 or any(c not in '0123456789abcdef' for c in predecessor)):
            raise ValueError('Invalid rejected naming predecessor')
        folder = self.root/predecessor
        receipt = folder/'receipt.json'
        if any(p.is_symlink() for p in (folder, receipt)):
            raise ValueError('Linked rejected naming evidence')
        info = folder.stat(); recorded = receipt.stat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700
                or not stat.S_ISREG(recorded.st_mode) or recorded.st_uid != os.geteuid()
                or recorded.st_nlink != 1 or recorded.st_mode & 0o022 or recorded.st_size > 2*1024*1024):
            raise ValueError('Unsafe rejected naming evidence')
        old = self.read_receipt(folder); original = old['request']
        if old['phase'] != 'review' or old['key'] != predecessor or token(original) != predecessor:
            raise ValueError('Naming predecessor is not held for review')
        path = Path(original['source'])
        if not scoped_file(path, self.worker.roots) or digest(path) != original['sha256']:
            raise ValueError('Rejected naming source changed')
        preservation = preservation or dict(original=str(folder/'original.cbz'), restore=str(folder/'restore.cbz'))
        if set(preservation) != {'original', 'restore'}:
            raise ValueError('Expected both rejected naming copies')
        copies = [Path(preservation[n]) for n in ('original', 'restore')]
        if (any(not p.is_absolute() or '..' in p.parts for p in copies)
                or copies[0] == copies[1] or copies[0].parent != copies[1].parent):
            raise ValueError('Expected distinct copies in one private folder')
        parent = copies[0].parent; saved = parent.stat()
        if (not parent.resolve().is_relative_to(self.worker.state.resolve()) or not stat.S_ISDIR(saved.st_mode)
                or any(p.is_symlink() for p in (parent, *parent.parents))
                or saved.st_uid != os.geteuid() or stat.S_IMODE(saved.st_mode) != 0o700):
            raise ValueError('Unsafe rejected preservation directory')
        import zipfile
        for copy in copies:
            saved = copy.lstat()
            if (not stat.S_ISREG(saved.st_mode) or saved.st_nlink != 1 or saved.st_uid != os.geteuid()
                    or digest(copy) != original['sha256']):
                raise ValueError('Rejected preservation copy changed')
            with zipfile.ZipFile(copy) as archive:
                if archive.testzip() is not None:raise ValueError('Rejected restore archive failed integrity')
        if self.api('releaseNamingStatus', token=predecessor).get('phase') != 'rejected':
            raise ValueError('Native naming predecessor is not rejected')
        fresh = self.api('getReleaseNaming', source=str(path))
        if type(fresh.get('version')) is not int or fresh['version'] != 1 or any(fresh[n] != original[n] for n in ('source','sha256','issueid','comicid')):
            raise ValueError('Rejected naming owner changed')
        self.publication(path, original)
        reader = self.reader_proof(path, all_books(self.worker.reader)); before = old['reader']
        if any(reader[n] != before[n] for n in ('id','hash','pages','seriesid','libraryid')):
            raise ValueError('Rejected reader identity changed')
        progress, current = before.get('progress'), reader.get('progress')
        if progress and (not current or current.get('page',0) < progress.get('page',0)
                         or (progress.get('completed') and not current.get('completed'))):
            raise ValueError('Rejected reader progress changed')
        request = {n:fresh[n] for n in ('version','source','sha256','issueid','comicid')}
        request.update(version=2, retry_of=predecessor, target=render(fresh))
        return dict(source=str(path), issueid=request['issueid'], comicid=request['comicid'], phase='planned',
                    proposal=fresh, request=request, reader=reader, preservation=preservation)

    def prepare(self, entry):
        remote_unlocked(self.worker)
        path = Path(entry['source'])
        if not scoped_file(path, self.worker.roots):raise ValueError('Release source scope changed')
        request = entry['request']; folder = self.root/token(request)
        if folder.exists():
            if folder.is_symlink() or not (folder/'receipt.json').is_file():
                raise ValueError('Incomplete release preparation requires review')
            held = self.read_receipt(folder)
            if held['request'] != request or held.get('reader') != entry.get('reader'):
                raise ValueError('Existing naming preparation differs from plan')
            if held['phase'] not in ('done', 'review'):
                self.copies(folder, request)
                if held['phase'] == 'prepared':self.publication(path, request)
            return folder
        if request.get('version') == 2:
            if self.recovery_entry(request.get('retry_of'), entry.get('preservation')) != entry:
                raise ValueError('Rejected naming recovery plan is stale')
        fresh = self.api('getReleaseNaming', source=str(path))
        expected = {name:fresh[name] for name in ('version','source','sha256','issueid','comicid')}
        expected['target'] = render(fresh)
        if request.get('version') == 2:
            expected.update(version=2, retry_of=request['retry_of'])
        if fresh != entry['proposal'] or expected != request:
            raise ValueError('Release naming plan is stale')
        proof = self.reader_proof(path, all_books(self.worker.reader))
        if proof != entry['reader']:raise ValueError('Reader naming plan is stale')
        baseline = self.publication(path, request)
        with Writer(self.worker.config['writer_state']).hold(timeout=0):
            if not evidence.same_json(baseline, self.publication(path, request)):
                raise ValueError('Naming authority changed before preservation')
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
            if identity(path) != before or digest(path) != request['sha256']:
                raise ValueError('Release source changed during preservation')
            if not evidence.same_json(baseline, self.publication(path, request)):
                raise ValueError('Naming authority changed during preservation')
            sync_directory(staging)
            prepared = dict(entry, phase='prepared', key=token(request), publication=baseline,
                            preservation_facts=self.copies(staging, request))
            prepared['preparation_binding'] = self.preparation_binding(prepared)
            save(staging/'receipt.json', prepared)
            if folder.exists():raise ValueError('Release preparation destination exists')
            staging.rename(folder); sync_directory(self.root)
        return folder

    def advance(self, folder, *, defer_scan=False, reader_books=None):
        remote_unlocked(self.worker)
        receipt = folder/'receipt.json'; job = self.read_receipt(folder)
        if job['phase'] in ('done', 'review'):return job
        kept = self.copies(folder, job['request'])
        recorded = job.get('preservation_facts')
        if recorded is not None and not evidence.same_json(recorded, kept):
            raise ValueError('Naming preservation identities changed')
        request = job['request']; destination = Path(request['source']).with_name(request['target'])
        if job['phase'] == 'prepared':
            self.copies(folder, request)
            fresh = self.publication(Path(request['source']), request)
            if fresh is not None and not evidence.same_json(fresh, job.get('publication')):
                raise ValueError('Prepared naming publication evidence changed')
            job['phase'] = 'native-uncertain'; save(receipt, job)
            try:
                response = self.api('renameLibraryFile', naming=json.dumps(request))
            except Exception:
                return job  # Reconcile the durable native journal; never replay an uncertain mutation.
            if (response.get('phase') != 'committed' or response.get('key') != job['key']
                    or type(response.get('version')) is not int or response['version'] != 1):
                raise ValueError('Native naming acknowledgement mismatch')
            job['phase'] = 'native-committed'; save(receipt, job)
        elif job['phase'] == 'native-uncertain':
            status = self.api('releaseNamingStatus', token=job['key'])
            if status.get('key') != job['key'] or type(status.get('version')) is not int or status['version'] != 1:
                raise ValueError('Native naming status acknowledgement mismatch')
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
            self.publication(destination, request)
            self.copies(folder, request)
            job['phase'] = 'reader-pending'; save(receipt, job)
            if defer_scan:
                return job
            self.scan(folder, job)
        if job['phase'] == 'reader-pending':
            baseline = self.publication(destination, request)
            kept = self.copies(folder, request)
            books = reader_books if reader_books is not None else all_books(self.worker.reader)
            matches = [b for b in books if not b.get('deleted') and api_path(b['url']) == destination]
            if len(matches) != 1 or matches[0].get('media', {}).get('status') != 'READY':
                if time.time()-job.get('scan_at',0) > 300:
                    self.scan(folder, job)
                return job
            book = matches[0]; old = job['reader']; progress = old['progress']
            if (book.get('fileHash') != old['hash'] or book['media']['pagesCount'] != old['pages']
                    or any(old.get(key) is not None and book.get(actual) != old[key]
                           for key, actual in (('libraryid','libraryId'), ('seriesid','seriesId')))
                    or sum(b.get('fileHash') == old['hash'] for b in books) != 1):
                raise ValueError('Renamed reader content mismatch')
            current = book.get('readProgress')
            if progress and (not current or current.get('page',0) < progress.get('page',0)
                             or (progress.get('completed') and not current.get('completed'))):
                raise ValueError('Renamed reader progress lost')
            if any(not b.get('deleted') and api_path(b['url']) == Path(request['source']) for b in books):
                return job
            if digest(destination) != request['sha256']:raise ValueError('Renamed release changed during reader verification')
            with Writer(self.worker.config['writer_state']).hold(timeout=0):
                if (not evidence.same_json(baseline, self.publication(destination, request))
                        or self.copies(folder, request) != kept
                        or self.read_receipt(folder) != job
                        or digest(destination) != request['sha256']):
                    raise ValueError('Naming completion evidence changed')
                job.update(phase='done', reader_bookid=book['id'], verified_at=time.time()); save(receipt, job)
                # Only this proven preservation pair is eligible. Interrupted
                # preparation folders retain their own independent evidence.
                (folder/'original.cbz').unlink(); (folder/'restore.cbz').unlink()
                sync_directory(folder)
        return job

    def apply(self, manifest, limit=1):
        remote_unlocked(self.worker)
        if manifest.get('kind') == 'combined-root-v1':
            from combined_handoff import Combined
            return Combined(self).apply(manifest, limit)
        if (type(manifest.get('version')) is not int or manifest.get('version') != 1
                or not isinstance(manifest.get('entries'), list) or type(limit) is not int or not 1 <= limit <= 100):
            raise ValueError('Invalid release naming manifest or batch limit')
        # Reconcile the last bounded batch before accepting additional media changes.
        active = [p.parent for p in sorted(self.root.glob('*/receipt.json'))
                  if not p.parent.name.startswith('.') and self.read_receipt(p.parent)['phase'] not in ('done', 'review')]
        books = all_books(self.worker.reader) if active else None
        results = [self.advance(folder, reader_books=books) for folder in active]
        if any(row['phase'] not in ('done', 'review') for row in results):return results
        results = []; pending = []
        try:
            for entry in manifest['entries']:
                if entry.get('phase') != 'planned':continue
                folder = self.root/token(entry['request'])
                if (folder/'receipt.json').exists() and self.read_receipt(folder)['phase'] in ('done', 'review'):
                    continue
                folder = self.prepare(entry)
                job = self.advance(folder, defer_scan=True)
                results.append(job)
                if job['phase'] == 'reader-pending':pending.append((folder, job))
                if job['phase'] == 'native-uncertain' or len(results) >= limit:break
        finally:
            # Persist exact destination-bound scans even if a later preflight fails.
            for folder, job in pending:
                self.scan(folder, job)
        return results

    def reconcile(self):
        """Ask the native owner to recover before ordinary writer admission."""
        remote_unlocked(self.worker)
        if (self.worker.state/'combined-release-v1').exists():
            from combined_handoff import Combined
            Combined(self).reconcile()
        for receipt in sorted(self.root.glob('*/receipt.json')):
            if receipt.parent.name.startswith('.'):continue
            job = self.read_receipt(receipt.parent)
            if job['phase'] in ('native-uncertain', 'native-committed', 'reader-pending'):
                self.advance(receipt.parent)

    def initialize(self):
        if self.state is None:
            self.state = dict(version=1, known=self.catalog())
            save(self.state_path, self.state)

    def tick(self):
        remote_unlocked(self.worker)
        if (self.worker.state/'combined-release-v1').exists():
            from combined_handoff import Combined
            if Combined(self).reconcile():
                return
        # Complete existing work before accepting another rename or reader scan.
        for receipt in sorted(self.root.glob('*/receipt.json')):
            if receipt.parent.name.startswith('.'):continue
            job = self.read_receipt(receipt.parent)
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
