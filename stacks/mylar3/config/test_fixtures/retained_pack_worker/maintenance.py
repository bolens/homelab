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
import stat
import subprocess
import time
import threading
import zipfile
from pdf_conversion import Pending as PDFPending

from normalize import archive_suffix, digest, identity, request, save, sync_directory


class CorruptArchive(ValueError):
    pass


def native_work(maintenance, command):
    """Only read-side work uses this cycle's prefetched replies under Writer."""
    if maintenance.worker.config.get('writer_state') is None:
        return maintenance.mylar(command)
    from publication_guard import current, NativeBatch, Unavailable
    batch = current(maintenance.worker).native_batch
    if type(batch) is not NativeBatch:
        raise Unavailable('Pre-lock native work collection required')
    return batch.read(maintenance.worker,command)


def name_key(value):
    value = re.sub(r'#\d+$', '', value).split('(')[0].casefold()
    return re.sub(r'\d+', lambda m: str(int(m[0])), re.sub(r'[^a-z0-9]', '', value))


def release_key(value):
    return ''.join(c for c in re.sub(r'\[__\d+__\]', '', re.sub(r'#\d+$', '', value)).casefold() if c.isalnum())


def scoped_file(path, roots):
    """Reject links in every component, including links inside a mounted root."""
    if not path.is_absolute() or '..' in path.parts:
        return False
    for root in roots:
        if path.is_relative_to(root):
            current = path
            while current != root.parent:
                if current.is_symlink():
                    return False
                current = current.parent
            return path.is_file()
    return False


def preserves(source, target, metadata_changed=False):
    return (source['page_count'] > 0 and source['pages'] == target['pages']
            and all(row in target['other_files'] for row in source['other_files']
                    if not (metadata_changed and Path(row['name']).name.casefold() == 'comicinfo.xml')))


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
        from publication_guard import remote_unlocked
        remote_unlocked(self.worker)
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

    def mylar_observation(self, encoded_request):
        """Exact bounded authenticated return bytes, never data reconstruction."""
        from publication_guard import remote_unlocked
        remote_unlocked(self.worker)
        if type(encoded_request) is not bytes or len(encoded_request)>4*1024*1024:
            raise ValueError('Bounded original observation request required')
        settings=self.worker.config['mylar']
        parser=configparser.ConfigParser()
        parser.read(Path(settings.get('config_dir','/mylar'))/'config.ini')
        key=next(parser.get(s,'api_key') for s in parser.sections() if parser.has_option(s,'api_key'))
        raw=request(settings['url'],'/api',form={'apikey':key,'cmd':'ordinaryImportObservation',
            'request':encoded_request.decode('utf-8')},text=True,limit=4*1024*1024)
        if type(raw) is not str:raise ValueError('Original encoded API response required')
        original=raw.encode('utf-8')
        if len(original)>4*1024*1024:raise ValueError('Original API response exceeds bound')
        return original

    def retained_pack_return(self, command, encoded_request):
        """Only the two finite retained POST commands; original bounded bytes."""
        from publication_guard import remote_unlocked
        remote_unlocked(self.worker)
        if (command not in ('retainedDeliveryFinalize','retainedDeliveryStatus')
                or type(encoded_request) is not bytes or not 0<len(encoded_request)<4096):
            raise ValueError('Exact retained request required')
        settings=self.worker.config['mylar']
        parser=configparser.ConfigParser()
        parser.read(Path(settings.get('config_dir','/mylar'))/'config.ini')
        key=next(parser.get(s,'api_key') for s in parser.sections() if parser.has_option(s,'api_key'))
        raw=request(settings['url'],'/api',form={'apikey':key,'cmd':command,
            'request':encoded_request.decode('utf-8')},text=True,limit=4*1024*1024)
        if type(raw) is not str or not 0<len(raw.encode())<=4*1024*1024:
            raise ValueError('Original retained response bytes required')
        return raw.encode()

    def idle(self):
        value = native_work(self,'getHealth')
        queue = value['queues'].get('POST-PROCESS-QUEUE', {})
        return queue.get('alive') and queue.get('size') == 0 and not value['processing']

    def prepare(self):
        from publication_guard import NativeBatch
        values = {}
        self.reader_snapshot=None
        if time.time() - self.last_run >= self.settings.get('interval_seconds',300):
            for command in ('getHealth','workflowCommands',*(['packWork'] if self.settings.get('pack_import',False) else [])):
                try:values[command] = self.mylar(command)
                except Exception:values[command] = None
            if self.worker.config.get('writer_state') is not None:
                from publication_guard import remote_unlocked,evidence,Unavailable
                remote_unlocked(self.worker)
                snapshot=getattr(self.worker,'reader_snapshot',None)
                if snapshot is None:
                    books=self.worker.reader.books()
                    if not isinstance(books,dict) or len(books)>evidence.CATALOG_ROWS:
                        raise Unavailable('Maintenance reader observation exceeds bounds')
                    books={key:{name:row.get(name) for name in ('id','seriesId','media','readProgress')}
                           for key,row in books.items()}
                    raw=evidence.compact(books)
                    if len(raw)>evidence.CATALOG_BYTES:
                        raise Unavailable('Maintenance reader observation exceeds bounds')
                    snapshot=(threading.get_ident(),time.monotonic(),raw)
                self.reader_snapshot=snapshot
        return NativeBatch(self.worker,values)

    def reader_books(self):
        if self.worker.config.get('writer_state') is None:
            return self.worker.reader.books()
        from publication_guard import current,evidence,Unavailable
        current(self.worker)
        snapshot=getattr(self,'reader_snapshot',None)
        if (not isinstance(snapshot,tuple) or len(snapshot)!=3
                or snapshot[0]!=threading.get_ident() or time.monotonic()-snapshot[1]>120
                or not isinstance(snapshot[2],bytes) or len(snapshot[2])>evidence.CATALOG_BYTES):
            raise Unavailable('Owned current maintenance reader snapshot required')
        books=evidence.decode_json(snapshot[2])
        if not isinstance(books,dict) or len(books)>evidence.CATALOG_ROWS:
            raise Unavailable('Maintenance reader observation exceeds bounds')
        return books

    def enqueue_archive_repair(self, owner, operation_id):
        # Explicit primary-key request only; no source path/reader receipt/grant.
        from archive_repair_handoff import enqueue
        return enqueue(self.worker, owner, operation_id)

    def archive_repair_status(self, owner, operation_id):
        from archive_repair_handoff import status
        return status(self.worker, owner, operation_id)

    def dispatch(self):
        from import_recovery import dispatch_prepared
        from native_handoff import dispatch
        from archive_repair_handoff import dispatch as repair_dispatch
        return dispatch_prepared(self)+dispatch(self)+repair_dispatch(self.worker)

    def info(self, path):
        fingerprint = identity(path)
        cached = self.cache.get(str(path))
        if cached and cached[0] == fingerprint:
            return cached[1]
        if path.suffix.lower() == '.pdf':
            value = self.worker.info(path)
            if identity(path) != fingerprint:
                raise RuntimeError('PDF changed during validation')
            self.cache[str(path)] = (fingerprint, value)
            return value
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
            if errors and not any(row.get('dependency') for row in errors) and prefix.startswith(b'PK\x03\x04'):
                # ZIP's end record must be within 22 bytes plus its maximum comment.
                # Do not load a directory rejected by the bounded decoder.
                with path.open('rb') as stream:
                    stream.seek(max(0, fingerprint[1] - 65557))
                    tail = stream.read(65557)
                if identity(path) != fingerprint:
                    raise RuntimeError('Archive changed during validation')
                if b'PK\x05\x06' not in tail:
                    raise CorruptArchive('ZIP end record is missing')
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
        if self.worker.config.get('writer_state') is not None:
            from publication_guard import Unavailable
            raise Unavailable('Corrupt archive needs reviewed owned quarantine evidence')
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
        if self.worker.config.get('writer_state') is not None:
            from publication_guard import Unavailable
            raise Unavailable('Legacy quarantine cannot replay in coordinated publication mode')
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

    def duplicate_proof(self, source, target, *, expected=None):
        from publication_guard import current, evidence, Unavailable
        if self.worker.config.get('writer_state') is None:
            return None
        value = current(self.worker).cleanup_check(source,target,
            match=expected['match'] if expected else None)
        if expected is not None and not evidence.same_json(value,expected):
            raise Unavailable('Duplicate cleanup proof changed; source retained')
        return value

    def duplicate_receipt(self, receipt):
        from import_recovery import handoff_read
        if not receipt.exists() and not receipt.is_symlink():
            return None
        if self.worker.config.get('writer_state') is not None:
            record,signature=handoff_read(receipt)
            from publication_guard import evidence, Unavailable
            required={'kind','source','destination','sha256','destination_sha256','phase','pages',
                      'publication','retained_original','binding'}
            if (not isinstance(record,dict) or set(record)!=required or record['kind']!='duplicate'
                    or record['phase'] not in ('verified','removed')
                    or type(record['pages']) is not int or record['pages']<=0
                    or not isinstance(record['source'],str) or not isinstance(record['sha256'],str)
                    or hashlib.sha256(os.fsencode(record['source'])+record['sha256'].encode()).hexdigest()!=receipt.stem
                    or evidence.canonical_digest({key:record[key] for key in sorted(required-{'phase','binding'})})!=record['binding']):
                raise Unavailable('Duplicate receipt immutable plan changed')
            return record,signature
        if receipt.is_symlink():
            raise RuntimeError('Linked duplicate receipt; source retained')
        return json.loads(receipt.read_text()), None

    def save_duplicate(self, receipt, row, previous=None):
        from publication_guard import evidence
        from import_recovery import handoff_save
        if self.worker.config.get('writer_state') is not None:
            body={key:value for key,value in row.items() if key not in ('phase','binding')}
            # Bind every immutable fact while allowing only the phase to advance.
            row['binding']=evidence.canonical_digest({key:body[key] for key in sorted(body)})
            return handoff_save(receipt,row,expected=previous)
        if previous is not None and not evidence.same_json(json.loads(receipt.read_text()),previous[0]):
            raise RuntimeError('Duplicate receipt changed; source retained')
        if previous is None and (receipt.exists() or receipt.is_symlink()):
            raise RuntimeError('Prior duplicate receipt must not be replaced')
        save(receipt,row)

    def remove_duplicate(self, source, target):
        from publication_guard import evidence
        if not scoped_file(source, self.roots) or not scoped_file(target, self.worker.roots):
            raise RuntimeError('Cleanup path is outside its scope or linked')
        proof = self.duplicate_proof(source,target)
        source_id, target_id = identity(source), identity(target)
        original, current = self.info(source), self.info(target)
        metadata_changed = not preserves(original, current)
        if metadata_changed:
            # Native tagging may rewrite ComicInfo, but no other source payload
            # may disappear. Keep the complete original archive before cleanup.
            root_metadata_only = dict(original, other_files=[row for row in original['other_files']
                                      if row['name'].casefold() != 'comicinfo.xml'])
            if (not preserves(root_metadata_only, current)
                    or not all(any(row['name'].casefold() == 'comicinfo.xml'
                                   for row in info['other_files']) for info in (original, current))):
                return False
            from import_match import metadata
            # Unsupported containers cannot provide bounded XML identity proof.
            if not zipfile.is_zipfile(source) or not zipfile.is_zipfile(target):
                return False
            before_meta, after_meta = metadata(source), metadata(target)
            identity_fields = ('Series', 'Number', 'Volume', 'Year', 'Month', 'Day', 'Format', 'Web',
                               'Title', 'Publisher', 'Imprint', 'Count', 'AlternateSeries', 'AlternateNumber',
                               'AlternateCount', 'ISBN', 'GTIN', 'ComicVineIssueID', 'ComicVineSeriesID',
                               'Edition', 'Variant', 'Reprint', 'CoverOnly', 'ReleaseType', 'SeriesVersion')
            if any(before_meta.get(key, '').strip() != after_meta.get(key, '').strip()
                   for key in identity_fields):
                return False
            if not self.idle():
                return False
        source_hash, target_hash = digest(source), digest(target)
        job_id = hashlib.sha256(os.fsencode(source) + source_hash.encode()).hexdigest()
        receipt = self.receipts / (job_id + '.json')
        row = {'kind': 'duplicate', 'source': str(source), 'destination': str(target),
               'sha256': source_hash, 'destination_sha256': target_hash, 'phase': 'verified',
               'pages': original['page_count']}
        if proof is not None:
            row['publication'] = proof
        previous = self.duplicate_receipt(receipt)
        if previous is not None:
            # A prior proof, terminal result or legacy receipt is never refreshed
            # into a new authorization simply because the source still exists.
            expected = dict(previous[0]); expected.pop('retained_original',None); expected.pop('binding',None)
            from publication_guard import evidence
            if not evidence.same_json(expected,row):
                raise RuntimeError('Prior duplicate proof differs; source retained')
        self.duplicate_proof(source,target,expected=proof)
        if metadata_changed or proof is not None:
            row['retained_original'] = str(self.retain_original(source, source_id, source_hash, job_id,
                check=lambda:self.duplicate_proof(source,target,expected=proof)))
        self.duplicate_proof(source,target,expected=proof)
        if previous is None:
            self.save_duplicate(receipt,row)
        elif not evidence.same_json({key:value for key,value in previous[0].items() if key!='binding'},row):
            raise RuntimeError('Retained original proof differs; source retained')
        prepared = self.duplicate_receipt(receipt)
        if not self.idle():
            return False
        if (not scoped_file(source, self.roots) or not scoped_file(target, self.worker.roots)
                or identity(source) != source_id or identity(target) != target_id
                or digest(source) != source_hash or digest(target) != target_hash
                or ((metadata_changed or proof is not None) and (Path(row['retained_original']).is_symlink()
                    or any(p.is_symlink() for p in Path(row['retained_original']).parents)
                    or digest(Path(row['retained_original'])) != source_hash))):
            raise RuntimeError('File changed before cleanup; source retained')
        if proof is not None:
            self.private_original(Path(row['retained_original']),source_hash)
        self.duplicate_proof(source,target,expected=proof)
        fresh_receipt=self.duplicate_receipt(receipt)
        from publication_guard import evidence
        if (fresh_receipt is None or fresh_receipt[1]!=prepared[1]
                or not evidence.same_json(fresh_receipt[0],prepared[0])):
            raise RuntimeError('Duplicate receipt changed before cleanup')
        source.unlink()
        sync_directory(source.parent)
        row['phase'] = 'removed'
        self.save_duplicate(receipt,row,prepared)
        try:
            if source.parent not in self.roots:
                source.parent.rmdir()
        except OSError:
            pass
        return True

    def retain_original(self, source, fingerprint, checksum, job_id, check=lambda:None):
        """Retain exact pre-tagging archive bytes; failed copies never authorize cleanup."""
        check()
        folder = self.state / 'retained-originals' / job_id
        if any(path.is_symlink() for path in (folder, folder.parent)):
            raise RuntimeError('Original retention path is linked; source retained')
        folder.parent.mkdir(exist_ok=True, mode=0o700)
        folder.mkdir(exist_ok=True, mode=0o700)
        sync_directory(folder.parent)
        sync_directory(self.state)
        destination = folder / source.name
        if destination.is_symlink():
            raise RuntimeError('Original retention file is linked; source retained')
        if not destination.exists():
            if shutil.disk_usage(self.state).free < source.stat().st_size * 2 + 128 * 1024**2:
                raise RuntimeError('Insufficient original retention storage; source retained')
            temporary = folder / '.copying'
            if temporary.exists() or temporary.is_symlink():
                previous = temporary.lstat()
                if (not stat.S_ISREG(previous.st_mode) or previous.st_nlink != 1
                        or previous.st_uid != os.geteuid() or stat.S_IMODE(previous.st_mode) != 0o600
                        or identity(source) != fingerprint or digest(source) != checksum):
                    raise RuntimeError('Interrupted original copy is unsafe; source retained')
                check()
                temporary.unlink()
                sync_directory(folder)
            check()
            with source.open('rb') as src, temporary.open('xb') as dst:
                os.chmod(temporary, 0o600)
                shutil.copyfileobj(src, dst, 1024**2)
                dst.flush()
                os.fsync(dst.fileno())
            if digest(temporary) != checksum:
                raise RuntimeError('Original retention copy differs; source retained')
            check()
            os.link(temporary, destination)
            check()
            temporary.unlink()
            sync_directory(folder)
        if (not destination.is_file() or digest(destination) != checksum
                or identity(source) != fingerprint or digest(source) != checksum):
            raise RuntimeError('Original retention verification failed; source retained')
        check()
        return destination

    def private_original(self, path, checksum):
        from publication_guard import evidence, Unavailable
        if not scoped_file(path,[self.state/'retained-originals']):
            raise Unavailable('Retained original is outside private scope')
        with evidence.regular(path) as stream:
            before=evidence.signature(os.fstat(stream.fileno()))
            if (before[6]!=os.geteuid() or before[8]!=1 or stat.S_IMODE(before[5])!=0o600):
                raise Unavailable('Retained original is not private and exclusive')
        signature,sha=evidence.file_hash(path)
        if signature!=before or sha!=checksum:
            raise Unavailable('Retained original changed')

    def reconcile_retained_duplicate(self, receipt, row):
        """Finish a proven cleanup if acknowledgement was interrupted after unlink."""
        previous = self.duplicate_receipt(receipt)
        from publication_guard import evidence
        if (previous is None or not evidence.same_json(previous[0],row)
                or row.get('kind')!='duplicate' or row.get('phase') != 'verified'):
            return False
        source, target, original = (Path(row[key]) for key in ('source', 'destination', 'retained_original'))
        if (source.exists() or source.is_symlink() or not source.is_absolute()
                or '..' in source.parts or not any(source.is_relative_to(root) for root in self.roots)
                or any(parent.is_symlink() for parent in source.parents)
                or not scoped_file(target, self.worker.roots)
                or not scoped_file(original, [self.state / 'retained-originals'])
                or digest(original) != row['sha256']
                or digest(target) != row['destination_sha256']):
            return False
        if self.worker.config.get('writer_state') is not None:
            from publication_guard import current, evidence, Unavailable
            expected = row.get('publication')
            if not isinstance(expected,dict):
                raise Unavailable('Legacy cleanup has no owned publication proof')
            self.private_original(original,row['sha256'])
            fresh = current(self.worker).cleanup_check(original,target,match=expected['match'])
            # Only the retained witness path/inode differs after unlink. Its
            # bytes, payload, census, owner and complete target proof must match.
            observed = fresh['confirmation']['source']
            historical = expected['confirmation']['source']
            observed['source'] = historical['source']
            observed['inventory']['source_signature'] = historical['inventory']['source_signature']
            if not evidence.same_json(fresh,expected):
                raise Unavailable('Interrupted cleanup proof changed; retained')
        if (source.exists() or source.is_symlink() or digest(original)!=row['sha256']
                or digest(target)!=row['destination_sha256']):
            return False
        complete = dict(row,phase='removed')
        self.save_duplicate(receipt,complete,previous)
        row.update(complete)
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
                    for magic,label in [(b'%PDF-','PDF'),(b'PK','ZIP'),(b'Rar!','RAR'),(b'7z\xbc\xaf\x27\x1c','7Z'),
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
            from pack_recovery import Packs
            protected_packs = Packs(self).cycle() if self.settings.get('pack_import', False) else set()
            for receipt in self.receipts.glob('*.json'):
                row = json.loads(receipt.read_text())
                if row['kind'] == 'quarantine' and row['phase'] in ('saved', 'quarantined'):
                    self.finish_quarantine(receipt, row)
                elif row['kind'] == 'duplicate' and row['phase'] == 'verified' and row.get('retained_original'):
                    self.reconcile_retained_duplicate(receipt, row)
                elif row['phase'] == 'retry_unconfirmed':
                    errors.append('Quarantine retry needs review: ' + row['source'])
            for receipt in self.receipts.glob('*.json'):
                row = json.loads(receipt.read_text())
                if row['kind'] == 'quarantine':
                    match = row.get('match') or {}
                    resolved = False
                    if match and self.worker.config.get('mylar'):
                        from import_recovery import issue_state
                        directory = Path(self.worker.config['mylar'].get('config_dir', '/mylar'))
                        with closing(sqlite3.connect('file:' + str(directory / 'mylar.db') + '?mode=ro', uri=True)) as database:
                            current = issue_state(database, match)
                            parent = database.execute('SELECT ComicLocation FROM comics WHERE ComicID=?', [match['comicid']]).fetchone()
                        if current and current[0] in ('Downloaded', 'Archived') and current[1] and parent:
                            target = Path(parent[0]) / current[1]
                            resolved = scoped_file(target, self.worker.roots) and target.stat().st_size > 0
                    problems.append({'name': Path(row['source']).name, 'kind': 'quarantine_resolved' if resolved else 'retry_unconfirmed' if row['phase']=='retry_unconfirmed' else 'quarantine',
                                     'phase': row['phase'], 'issueid': match.get('issueid', ''), 'comicid': match.get('comicid', '')})
            protected_ddl = self.pending_ddl_names()
            books = self.reader_books()
            candidates = {}
            for name, book in books.items():
                path = Path(name)
                if (book['media']['status'] == 'READY' and scoped_file(path, self.worker.roots)):
                    candidates.setdefault(name_key(path.stem), []).append(path)
            for directory, dirs, files in itertools.chain.from_iterable(os.walk(root, followlinks=False) for root in self.roots):
                dirs[:] = [d for d in dirs if not d.startswith('.mylar-') and not (Path(directory) / d).is_symlink()]
                for name in files:
                    path = Path(directory) / name
                    if any(path == root or path.is_relative_to(root) for root in protected_packs):
                        continue
                    if path.is_symlink() or not path.is_file() or not archive_suffix(path):
                        continue
                    if (self.settings.get('ddl_cache') and path.is_relative_to(Path(self.settings['ddl_cache']))
                            and path.name in protected_ddl):
                        continue
                    if path.suffix.lower() == '.pdf' and not self.worker.pdf_policy['enabled']:
                        continue
                    fingerprint = identity(path)
                    previous, since = self.observed.get(str(path), (None, now))
                    if previous != fingerprint:
                        self.observed[str(path)] = (fingerprint, now)
                        continue
                    if now - since < self.settings.get('settle_seconds', 600):
                        continue
                    problem_start=len(problems)
                    try:
                        self.info(path)
                        for target in ([] if path.suffix.lower() == '.pdf' else candidates.get(name_key(path.stem), [])):
                            if self.remove_duplicate(path, target):
                                break
                        if path.exists():
                            from import_recovery import previous_attempt
                            previous_import = previous_attempt(self, path)
                            if previous_import:
                                kind, match = previous_import
                                guided=guidance.propose(path) if kind=='import_review' else {}
                                if guided:guidance.proposals[-1]['requires_review']=True
                                problems.append({'name': path.name, 'kind': kind, **match, **guided})
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
                    except PDFPending:
                        problems.append({'name': path.name, 'kind': 'pdf_rendering'})
                    except CorruptArchive:
                        if self.worker.config.get('writer_state') is not None:
                            problems.append({'name':path.name,'kind':'validation'})
                            warnings.append('Corrupt archive retained for owned review')
                        else:
                            self.quarantine(path, fingerprint)
                            problems.append({'name': path.name, 'kind': 'quarantine'})
                    except (ValueError, FileNotFoundError) as error:
                        from publication_guard import ArchiveDiagnosticUnavailable
                        warnings.append(str(error) if isinstance(error,ArchiveDiagnosticUnavailable) else
                                        'Retained for review: ' + str(path))
                        problems.append({'name': path.name, 'kind': 'validation'})
                    except Exception:
                        errors.append('Maintenance failed for ' + str(path))
                        problems.append({'name': path.name, 'kind': 'failed'})
                    finally:
                        if self.worker.config.get('writer_state') is not None:
                            for row in problems[problem_start:]:row['_source']=str(path)
            extra = {'guidance': json.dumps(guidance.proposals)} if guidance.available else {}
            if self.worker.config.get('writer_state') is not None:
                from maintenance_report import prepare
                prepare(self,problems[:500],self.conversion_report(),guidance.proposals if guidance.available else [])
            else:
                self.mylar('reportImportProblems', report=json.dumps(problems[:500]), processing=json.dumps(self.conversion_report()), **extra)
            save(status, {'checked_at': time.time(), 'state': 'checked', 'errors': errors, 'warnings': warnings})
        except Exception:
            save(status, {'checked_at': time.time(), 'state': 'failed',
                          'errors': ['Maintenance API, storage, or recovery check failed']})
