"""Reader-sequenced combined passes with exact native terminal lineage."""
import json
import os
from pathlib import Path
import stat
import time

import publication_evidence as evidence
from publication_guard import remote_unlocked
from normalize import api_path, digest, save, sync_directory


PHASES = ('prepared', 'prepare-uncertain', 'native-prepared', 'rename-uncertain',
          'reader-move-pending', 'metadata-uncertain', 'reader-final-pending', 'done',
          'cleanup-uncertain', 'cleanup-complete')


def load_reviewed_preview(path):
    """Bounded explicit input; duplicate/non-finite/deep JSON is never approval."""
    with Path(path).open('rb') as stream:
        raw=stream.read(16*1024*1024+1)
    if len(raw)>16*1024*1024:
        raise ValueError('Reviewed supplement preview exceeds bounds')
    try:
        def integer(text):
            if len(text)>16:raise ValueError('Preview integer exceeds bounds')
            return int(text)
        def reject(_):raise ValueError('Preview requires finite integer facts')
        value=json.loads(raw.decode('utf-8'),object_pairs_hook=evidence.object_pairs,
                         parse_int=integer,parse_float=reject,parse_constant=reject)
    except (ValueError,UnicodeError,RecursionError,evidence.Unavailable):
        raise ValueError('Invalid reviewed supplement preview JSON') from None
    reviewed_preview(value)
    return value


def reviewed_preview(value):
    """Validate explicit source-bound review input; native alone derives additions."""
    if (not isinstance(value, dict) or set(value) != {'version','policy','reviews'}
            or type(value['version']) is not int or value['version'] != 1
            or not isinstance(value['policy'], dict) or len(value['policy'])>9 or not isinstance(value['reviews'], list)
            or len(value['reviews']) > 10000):
        raise ValueError('Exact reviewed combined preview required')
    if any(not isinstance(k,str) or not isinstance(v,str) or not v.strip() or len(v)>65536 or any(ord(c)<32 for c in v)
           for k,v in value['policy'].items()):
        raise ValueError('Invalid reviewed metadata policy')
    result = {}
    for row in value['reviews']:
        if (not isinstance(row,dict) or set(row) != {'source','source_sha256','status','evidence','additions'}
                or not isinstance(row['source'],str) or not Path(row['source']).is_absolute()
                or '..' in Path(row['source']).parts or row['source'] in result
                or row['status'] != 'verified' or not isinstance(row['additions'],dict) or len(row['additions'])>9
                or any(not isinstance(k,str) or not isinstance(v,str) or not v.strip() or len(v)>65536 or any(ord(c)<32 for c in v)
                       for k,v in row['additions'].items())
                or any(not isinstance(row[k],str) or len(row[k])!=64
                       or any(c not in '0123456789abcdef' for c in row[k])
                       for k in ('source_sha256','evidence'))):
            raise ValueError('Exact verified source supplement review required')
        result[row['source']] = json.loads(json.dumps(row))
    return result


def native_source(naming,path):
    with naming.authority() as authority:
        matches=[native/path.relative_to(worker) for native,worker in authority.mappings if path.is_relative_to(worker)]
    if len(matches)!=1:raise ValueError('Exact native source mapping required')
    return str(matches[0])


def native_preview(value,request,policy):
    keys={'version','protocol','request','policy','owner','census','payload','observed','writer','source_signature','additions','binding'}
    if (not isinstance(value,dict) or set(value)!=keys or type(value['version']) is not int or value['version']!=1
            or value['protocol']!='combined-preview-v1' or not evidence.same_json(value['request'],request)
            or not evidence.same_json(value['policy'],policy) or not isinstance(value['additions'],dict)
            or value['binding']!=evidence.canonical_digest({k:v for k,v in value.items() if k!='binding'})):
        raise ValueError('Exact current native supplement preview required')
    return value


def planned_metadata(entry, policy):
    """Bind reviewed preview to this request, without granting publication rights."""
    plan = entry.get('metadata_plan')
    if plan is None:
        return  # Preserve existing exact reviewed legacy combined manifests.
    review = entry.get('metadata_review')
    if not isinstance(review,dict):
        raise ValueError('Exact verified metadata review required')
    if (not isinstance(plan,dict) or set(plan) != {'version','additions','policy_sha256','native_preview'}
            or type(plan['version']) is not int or plan['version'] != 1
            or plan['policy_sha256'] != evidence.canonical_digest(policy)):
        raise ValueError('Combined metadata preview policy changed')
    reviewed_preview(dict(version=1,policy=policy,reviews=[dict(
        source=entry['request']['source'],additions=plan['additions'],**(review or {}))]))
    preview=plan['native_preview']
    if not isinstance(preview,dict) or not evidence.same_json(preview.get('additions'),plan['additions']):
        raise ValueError('Approved additions differ from native derivation')
    if review['source_sha256'] != entry['request']['sha256']:
        raise ValueError('Combined metadata preview source changed')
    if (Path(entry['request']['source']).name == entry['request']['target'] and not plan['additions']):
        raise ValueError('Already-correct canonical preview requires no publication')


class Combined:
    def __init__(self, naming):
        self.naming = naming
        self.worker = naming.worker
        self.root = self.worker.state/'combined-release-v1'
        self.root.mkdir(mode=0o700, exist_ok=True)
        info = self.root.lstat()
        if self.root.is_symlink() or stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.geteuid():
            raise ValueError('Private combined worker state required')
        self.root_identity = (info.st_dev, info.st_ino)

    def binding(self, job):
        return evidence.canonical_digest({key: job[key] for key in
            ('entry', 'policy', 'manifest', 'request', 'before', 'native_token')})

    def read(self, folder):
        if ((self.root.stat().st_dev, self.root.stat().st_ino) != self.root_identity
                or folder.parent != self.root or folder.is_symlink()):
            raise ValueError('Combined state namespace changed')
        row = folder.lstat()
        if not stat.S_ISDIR(row.st_mode) or row.st_uid != os.geteuid() or row.st_mode & 0o077:
            raise ValueError('Unsafe combined receipt directory')
        path = folder/'receipt.json'
        info = path.lstat()
        if (path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_uid != os.geteuid() or info.st_mode & 0o022 or info.st_size > 2*1024*1024):
            raise ValueError('Unsafe combined receipt')
        job = json.loads(path.read_text())
        if (evidence.signature(path.lstat()) != evidence.signature(info)
                or type(job.get('version')) is not int or job['version'] != 1
                or job.get('phase') not in PHASES or folder.name != job.get('native_token')
                or self.binding(job) != job.get('binding')):
            raise ValueError('Combined prepared facts changed')
        return job

    def stamp(self,folder):
        signature,checksum=evidence.file_hash(folder/'receipt.json')
        return signature,checksum

    def transition(self,folder,expected,stamp,job,proof=None):
        with self.naming.authority():
            if proof is not None:proof()
            if self.read(folder)!=expected or self.stamp(folder)!=stamp:
                raise ValueError('Combined receipt changed before transition')
            save(folder/'receipt.json',job)
        return json.loads(json.dumps(job)),self.stamp(folder)

    def api(self, action, **arguments):
        remote_unlocked(self.worker)
        return self.naming.api('combinedPublication', request=json.dumps(
            dict(version=1, action=action, arguments=arguments)))

    def native_path(self, path):
        return native_source(self.naming,path)

    def prepare(self, entry, policy, manifest):
        remote_unlocked(self.worker)
        from naming_worker import all_books
        if (not isinstance(entry, dict) or entry.get('phase') != 'planned'
                or not isinstance(policy, dict) or not isinstance(manifest, str)
                or len(manifest) != 64 or any(c not in '0123456789abcdef' for c in manifest)):
            raise ValueError('Reviewed combined entry required')
        entry=json.loads(json.dumps(entry));policy=json.loads(json.dumps(policy))
        planned_metadata(entry, policy)
        if policy or entry.get('metadata_plan') is not None:
            review = entry.get('metadata_review')
            if (not isinstance(review, dict) or set(review) != {'status', 'source_sha256', 'evidence'}
                    or review['status'] != 'verified' or review['source_sha256'] != entry['request']['sha256']
                    or not isinstance(review['evidence'], str) or len(review['evidence']) != 64
                    or any(c not in '0123456789abcdef' for c in review['evidence'])):
                raise ValueError('Unverified credits remain deferred from metadata publication')
        source = Path(entry['request']['source'])
        request = dict(entry['request'], source=self.native_path(source))
        plan=entry.get('metadata_plan')
        token = evidence.canonical_digest(dict(request=request, policy=policy, manifest=manifest))
        folder = self.root/token
        if folder.exists():
            existing = self.read(folder)
            if (not evidence.same_json(existing['entry'], entry)
                    or not evidence.same_json(existing['policy'], policy) or existing['manifest']!=manifest):
                raise ValueError('Combined entry changed')
            return folder
        if plan is not None:
            expected=native_preview(plan['native_preview'],request,policy)
            if digest(source)!=entry['request']['sha256']:
                raise ValueError('Reviewed combined original changed')
            fresh=self.api('preview',naming=request,policy=policy)
            native_preview(fresh,request,policy)
            if not evidence.same_json(fresh,expected):
                raise ValueError('Native supplement preview changed before preparation')
        reader = self.naming.reader_proof(source, all_books(self.worker.reader))
        if not evidence.same_json(reader, entry['reader']):
            raise ValueError('Combined reader plan changed')
        before = self.naming.publication(source, entry['request'])
        if plan is not None and before is not None:
            facts=before['source']
            if (not evidence.same_json(facts['authority']['owner'],expected['owner'])
                    or not evidence.same_json(facts['authority']['census'],expected['census'])
                    or facts['inventory']['payload']!=expected['payload']):
                raise ValueError('Native supplement preview authority changed')
        if before is None or digest(source) != entry['request']['sha256']:
            raise ValueError('Current publication authority required')
        with self.naming.authority():
            if not evidence.same_json(before, self.naming.publication(source, entry['request'])):
                raise ValueError('Combined source changed before preparation')
            folder.mkdir(mode=0o700)
            job = dict(version=1, phase='prepared', entry=entry, policy=policy, manifest=manifest,
                       request=request, before=before, native_token=token)
            job['binding'] = self.binding(job)
            save(folder/'receipt.json', job)
            sync_directory(self.root)
        return folder

    def source_proof(self,job):
        request=job['entry']['request'];source=Path(request['source'])
        proof=self.naming.publication(source,request)
        if digest(source)!=request['sha256'] or not evidence.same_json(proof,job['before']):
            raise ValueError('Combined prepared source changed')
        return proof

    def proof(self, job, checksum):
        request = job['entry']['request']
        path = Path(request['source']).with_name(request['target'])
        expected = dict(request, source=str(path), sha256=checksum)
        if digest(path) != checksum:
            raise ValueError('Combined actual archive differs from terminal lineage')
        observed = self.naming.publication(path, expected)
        if observed is None:
            raise ValueError('Combined current publication authority required')
        authority = observed['source']['authority']
        before = job['before']['source']['authority']
        if (not evidence.same_json(authority['owner'], before['owner'])
                or not evidence.same_json(authority['census'], before['census'])
                or observed['source']['inventory']['payload'] != job['before']['source']['inventory']['payload']):
            raise ValueError('Combined current owner, payload or census changed')
        return observed

    def acknowledgement(self, job, result):
        before = job['before']['source']
        if (not isinstance(result, dict) or type(result.get('version')) is not int or result['version'] != 1
                or result.get('protocol') != 'combined-root-v1' or result.get('token') != job['native_token']
                or not evidence.same_json(result.get('request'), job['request'])
                or not evidence.same_json(result.get('owner'), before['authority']['owner'])
                or not evidence.same_json(result.get('census'), before['authority']['census'])
                or result.get('payload') != before['inventory']['payload']
                or result.get('before') != job['request']['sha256']
                or not isinstance(result.get('binding'), str) or len(result['binding']) != 64
                or not isinstance(result.get('after'), str) or len(result['after']) != 64
                or not isinstance(result.get('lineage'), str) or len(result['lineage']) != 64
                or (job.get('native') and result['binding'] != job['native']['binding'])):
            raise ValueError('Exact native combined lineage required')
        return result

    def ready(self, job, checksum, *, moved):
        from naming_worker import all_books, reader_hash
        path = Path(job['entry']['request']['source']).with_name(job['entry']['request']['target'])
        books = all_books(self.worker.reader)
        matches = [book for book in books if not book.get('deleted') and api_path(book['url']) == path]
        if len(matches) != 1 or matches[0].get('media', {}).get('status') != 'READY':
            return None
        book = matches[0]
        old = job['entry']['reader']
        current_hash = reader_hash(path)
        if not moved and book.get('fileHash') == old['hash'] and current_hash != old['hash']:
            return None
        if (book.get('fileHash') != current_hash or (moved and current_hash != old['hash'])
                or sum(b.get('fileHash') == current_hash for b in books) != 1
                or book['media']['pagesCount'] != old['pages']
                or book.get('libraryId') != old['libraryid'] or book.get('seriesId') != old['seriesid']):
            raise ValueError('Combined reader restoration differs from publication')
        progress = old.get('progress')
        now = book.get('readProgress')
        if progress and (not now or now.get('page', 0) < progress.get('page', 0)
                         or (progress.get('completed') and not now.get('completed'))):
            raise ValueError('Combined reader progress lost')
        source = Path(job['entry']['request']['source'])
        if source != path and any(not b.get('deleted') and api_path(b['url']) == source for b in books):
            return None
        if digest(path) != checksum:
            raise ValueError('Combined source changed during reader proof')
        return dict(version=1, binding=job['native']['binding'],
                    destination=str(Path(job['request']['source']).with_name(job['request']['target'])),
                    sha256=checksum, bookid=book['id'], hash=current_hash, pages=old['pages'],
                    libraryid=old['libraryid'], seriesid=old['seriesid'])

    def scan(self, job):
        from reader_handoff import queue
        request = job['entry']['request']
        path = Path(request['source']).with_name(request['target'])
        with self.naming.authority():
            bindings=[dict(source=str(path), target=str(path),
                match={key: request[key] for key in ('issueid', 'comicid')})]
            if job['phase']=='reader-final-pending':
                queue(self.worker, 'metadata_refresh', bindings, book_id=job['reader_move']['bookid'])
            else:
                queue(self.worker, 'library_scan', bindings, folder=path.parent)

    def advance(self, folder):
        remote_unlocked(self.worker)
        job = self.read(folder)
        expected=json.loads(json.dumps(job));stamp=self.stamp(folder)
        phase = job['phase']
        if phase in ('done','cleanup-uncertain'):
            return self.cleanup(folder,job,expected,stamp)
        if phase == 'cleanup-complete':
            return self.cleanup(folder,job,expected,stamp)
        if phase == 'prepared':
            health = self.naming.api('getHealth')
            if not isinstance(health, dict) or type(health.get('combined_publication')) is not int or health['combined_publication'] != 1:
                return job
            if (job['entry'].get('metadata_plan') is not None
                    and (type(health.get('combined_preview')) is not int or health['combined_preview']!=1)):
                return job
            with self.naming.authority():
                if not evidence.same_json(job['before'], self.naming.publication(
                        Path(job['entry']['request']['source']), job['entry']['request'])):
                    raise ValueError('Prepared combined source changed')
                job['phase'] = 'prepare-uncertain'
                expected,stamp=self.transition(folder,expected,stamp,job)
            arguments=dict(naming=job['request'],policy=job['policy'],manifest=job['manifest'])
            if job['entry'].get('metadata_plan') is not None:
                plan=job['entry']['metadata_plan']
                arguments.update(preview=plan['native_preview'],approved_additions=plan['additions'])
            result = self.api('prepare', **arguments)
            self.acknowledgement(job, result)
            if result['phase'] != 'prepared':
                raise ValueError('Combined prepare acknowledgement mismatch')
            job.update(phase='native-prepared', native=result)
            self.transition(folder,expected,stamp,job,lambda:self.source_proof(job))
            return job
        if phase == 'native-prepared':
            before=self.naming.publication(Path(job['entry']['request']['source']),job['entry']['request'])
            if not evidence.same_json(before,job['before']):raise ValueError('Combined source changed before rename')
            job['phase'] = 'rename-uncertain'
            expected,stamp=self.transition(folder,expected,stamp,job,lambda:self.source_proof(job))
            result = self.api('rename', token=job['native_token'])
        elif phase in ('prepare-uncertain', 'rename-uncertain', 'metadata-uncertain'):
            result = self.api('status', token=job['native_token'])
        elif phase in ('reader-move-pending', 'reader-final-pending'):
            fresh=self.acknowledgement(job,self.api('status',token=job['native_token']))
            if not evidence.same_json(fresh,job['native']):
                raise ValueError('Retained combined terminal lineage changed')
            after = job['native']['after'] if phase == 'reader-final-pending' else job['request']['sha256']
            before_proof = self.proof(job, after)
            ready = self.ready(job, after, moved=phase == 'reader-move-pending')
            if ready is None:
                self.scan(job)
                return job
            with self.naming.authority():
                if (self.read(folder) != job or not evidence.same_json(before_proof, self.proof(job, after))):
                    raise ValueError('Combined reader completion proof changed')
                if phase == 'reader-final-pending':
                    # Preserve the original prepared proof; terminal lineage is
                    # a separate exact descendant, never a substituted baseline.
                    job.update(phase='done', final_reader=ready, final_publication=before_proof,
                               completed_at=time.time())
                    expected,stamp=self.transition(folder,expected,stamp,job)
                    return job
                job.update(phase='metadata-uncertain', reader_move=ready)
                expected,stamp=self.transition(folder,expected,stamp,job)
            result = self.api('metadata', token=job['native_token'], reader_move=ready)
        else:
            raise ValueError('Unknown combined phase')
        self.acknowledgement(job, result)
        if result['phase'] == 'prepared' and phase == 'prepare-uncertain':
            job.update(phase='native-prepared', native=result)
        elif result['phase'] == 'renamed' and job['phase'] == 'rename-uncertain':
            self.proof(job, job['request']['sha256'])
            job.update(phase='reader-move-pending', native=result)
        elif result['phase'] == 'complete' and job['phase'] == 'metadata-uncertain':
            self.proof(job, result['after'])
            job.update(phase='reader-final-pending', native=result)
        else:
            raise ValueError('Uncertain combined action cannot be replayed')
        checksum=job['native']['after'] if job['phase']=='reader-final-pending' else job['request']['sha256']
        proof=(lambda:self.source_proof(job)) if job['phase']=='native-prepared' else (lambda:self.proof(job,checksum))
        self.transition(folder,expected,stamp,job,proof)
        if job['phase'] in ('reader-move-pending', 'reader-final-pending'):
            self.scan(job)
        return job

    def cleanup(self,folder,job,expected,stamp):
        """Consume a conclusive reader acceptance; uncertain deletion is status-only."""
        if job['phase']=='done':
            health=self.naming.api('getHealth')
            if (not isinstance(health,dict) or type(health.get('combined_cleanup')) is not int
                    or health['combined_cleanup']!=1):return job
        fresh=self.acknowledgement(job,self.api('status',token=job['native_token']))
        ordinary={key:value for key,value in fresh.items() if key!='cleanup'}
        if not evidence.same_json(ordinary,job['native']):
            raise ValueError('Cleanup current terminal lineage changed')
        checksum=job['native']['after'];proof=self.proof(job,checksum)
        ready=self.ready(job,checksum,moved=False)
        if ready is None:
            self.scan(dict(job,phase='reader-final-pending'))
            if job['phase']=='cleanup-complete':raise ValueError('Completed cleanup reader proof is no longer current')
            return job
        previous=job['reader_move']
        if any(ready[key]!=previous[key] for key in ('binding','destination','bookid','pages','libraryid','seriesid')):
            raise ValueError('Cleanup reader identity differs from verified move')
        if job['phase']=='done' and 'cleanup' not in fresh:
            request=dict(version=1,combined_token=job['native_token'],binding=job['native']['binding'],
                         lineage=job['native']['lineage'],reader=ready)
            job.update(phase='cleanup-uncertain',cleanup_request=request)
            expected,stamp=self.transition(folder,expected,stamp,job,lambda:self.proof(job,checksum))
            fresh=self.acknowledgement(job,self.api('cleanup',**request))
        elif job['phase']=='done':
            # A lost local receipt can recognize an already closed native
            # retirement; never issue another deletion request.
            job['cleanup_request']=dict(version=1,combined_token=job['native_token'],binding=job['native']['binding'],
                lineage=job['native']['lineage'],reader=ready)
        closed=fresh.get('cleanup')
        if (not isinstance(closed,dict) or set(closed)!={'version','token','digest','phase'}
                or type(closed['version']) is not int or closed['version']!=1 or closed['phase']!='complete'
                or closed['token']!=evidence.canonical_digest(job['cleanup_request'])
                or not isinstance(closed['digest'],str) or len(closed['digest'])!=64
                or any(character not in '0123456789abcdef' for character in closed['digest'])
                or not evidence.same_json({key:value for key,value in fresh.items() if key!='cleanup'},job['native'])):
            raise ValueError('Conclusive native retirement proof required; no cleanup replay')
        final=self.proof(job,checksum);reader=self.ready(job,checksum,moved=False)
        if reader is None:
            self.scan(dict(job,phase='reader-final-pending'))
            return self.read(folder)
        if not evidence.same_json(final,proof) or not evidence.same_json(reader,ready):
            raise ValueError('Cleanup reader or publication changed after native acknowledgment')
        if job['phase']=='cleanup-complete':
            if not evidence.same_json(closed,job['final_cleanup']):raise ValueError('Completed cleanup history changed')
            with self.naming.authority():
                if self.read(folder)!=expected or self.stamp(folder)!=stamp:
                    raise ValueError('Completed cleanup receipt changed during verification')
            return job
        job.update(phase='cleanup-complete',final_cleanup=closed,final_reader=reader,final_publication=final)
        self.transition(folder,expected,stamp,job,lambda:self.proof(job,checksum))
        return job

    def apply(self, manifest, limit):
        if (type(manifest.get('version')) is not int or manifest['version'] != 1
                or manifest.get('kind') != 'combined-root-v1' or not isinstance(manifest.get('entries'), list)
                or not isinstance(manifest.get('policy'), dict) or type(limit) is not int or not 1 <= limit <= 100):
            raise ValueError('Exact bounded combined manifest required')
        binding = evidence.canonical_digest(manifest)
        results = []
        for entry in manifest['entries']:
            if entry.get('phase') != 'planned':
                continue
            folder = self.prepare(entry, manifest['policy'], binding)
            results.append(self.advance(folder))
            if len(results) >= limit:
                break
        return results

    def reconcile(self):
        """Advance one explicitly prepared combined job, outside shared Writer."""
        remote_unlocked(self.worker)
        cleanup_available=None
        receipts = sorted(self.root.glob('*/receipt.json'))
        cursor = getattr(self.naming, '_combined_cursor', '')
        # Naming persists across ticks; Combined itself is reconstructed. Rotate
        # even after a retained/error result so one waiting reader cannot starve
        # unrelated receipts. This cursor conveys scheduling only.
        receipts = [r for r in receipts if r.parent.name > cursor] + [
            r for r in receipts if r.parent.name <= cursor]
        for receipt in receipts:
            if receipt.parent.name.startswith('.'):
                continue
            job = self.read(receipt.parent)
            if job['phase']=='done':
                if cleanup_available is None:
                    health=self.naming.api('getHealth')
                    cleanup_available=(isinstance(health,dict) and type(health.get('combined_cleanup')) is int
                                       and health['combined_cleanup']==1)
                if not cleanup_available:continue
            if job['phase'] != 'cleanup-complete':
                self.naming._combined_cursor = receipt.parent.name
                self.advance(receipt.parent)
                return True
        return False
