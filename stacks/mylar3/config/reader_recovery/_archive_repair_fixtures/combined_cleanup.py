"""Exact native private-pair retirement; retained history grants no replay."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import stat
import threading

if __package__:
    from . import publication_guard as guard, publication_native as native
    from .media_writer import checked_file, sync
else:
    import publication_guard as guard
    import publication_native as native
    from media_writer import checked_file, sync

_LOCAL = threading.local()
KIND = 'combined_cleanup'


def modules():
    import mylar
    from mylar import combined_publication, native_writers, publication_transaction, release_naming
    return mylar, combined_publication, native_writers, publication_transaction, release_naming


def detached(value):
    return json.loads(json.dumps(value))


def current():
    value = getattr(_LOCAL, 'cleanup', None)
    if value is not None and type(value) is not Cleanup:
        raise guard.Unavailable('Exact owned cleanup required')
    return value


def admitted(value, writer):
    if type(value) is not Cleanup or current() is not value:
        raise guard.Unavailable('Exact live cleanup required')
    value.check(writer)


def history(writer, name='combined-cleanup-v1', *, create=True):
    path = writer.root/name
    if create and not path.exists():
        path.mkdir(mode=0o700); sync(writer.root)
    info = path.lstat()
    if (path.is_symlink() or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise guard.Unavailable('Private cleanup history required')
    return path


def capsule(path):
    path = Path(path)
    before = guard.private_evidence(path)
    value = guard.private_json(path)
    if guard.private_evidence(path) != before:
        raise guard.Unavailable('Cleanup predecessor changed during capture')
    return dict(path=str(path), incarnation=before, digest=guard.canonical_digest(value), value=value)


def retained(value):
    path = Path(value['path'])
    if (guard.private_evidence(path) != value['incarnation']
            or not guard.same_json(guard.private_json(path), value['value'])
            or guard.canonical_digest(value['value']) != value['digest']):
        raise guard.Unavailable('Cleanup predecessor history changed')


def acceptance(value, job, acknowledgement):
    if (not isinstance(value, dict) or set(value) != {'version','combined_token','binding','lineage','reader'}
            or type(value['version']) is not int or value['version'] != 1
            or value['combined_token'] != job['token'] or value['binding'] != job['binding']
            or value['lineage'] != acknowledgement['lineage']):
        raise guard.Unavailable('Exact final combined acceptance required')
    reader = value['reader']; previous = job['reader_move']
    if (not isinstance(reader, dict) or set(reader) != set(previous)
            or type(reader['version']) is not int or reader['version'] != 1
            or type(reader['pages']) is not int or reader['pages'] < 1
            or reader['sha256'] != acknowledgement['after']
            or any(reader[key] != previous[key] for key in
                   ('binding','destination','bookid','pages','libraryid','seriesid'))
            or not isinstance(reader['hash'],str) or not reader['hash']):
        raise guard.Unavailable('Exact restored reader acceptance required')
    return detached(value)


def snapshot(writer, folder, job, request):
    mylar, combined, _, transaction, naming = modules()
    combined.verified_complete(writer, job)
    ack = combined.acknowledgement(writer, job)
    request = acceptance(request, job, ack)
    metadata = job['metadata']; source = Path(metadata['source'])
    actual, observed = combined.current(writer, job, source, metadata['after'])
    result = dict(version=1, kind='combined-cleanup-v1', request=request,
        writer=guard.writer_identity(writer),
        combined=capsule(folder/'receipt.json'),
        source=dict(path=str(source),sha256=metadata['after'],
                    signature=actual['inventory']['source_signature'], owner=job['owner'],
                    payload=job['payload'], census=job['census'], observed=observed),
        policy=job['policy'], pair=job['pair'], rename=None, supplement=None)
    if job['rename']['token'] is not None:
        key=job['rename']['token']; saved=naming.services()[1].get('release_name',key)
        result['rename']=dict(job=saved,
            history_identity=guard.signature((writer.root/'release-completed-v1').lstat())[:2],
            witness=capsule(writer.root/'release-completed-v1'/(key+'.json')))
    else:
        result['rename']=dict(noop=job['rename'])
    if metadata['token'] is not None:
        witness=capsule(writer.root/'tagger-completed-v1'/(metadata['token']+'.json'))
        closed=witness['value']['job']
        result['supplement']=dict(closed_result=metadata, witness=witness,
            receipt=capsule(Path(closed['completion']['receipt'])),
            history_identity=transaction.history_identity(writer.root/'tagger-completed-v1'),
            recovery=transaction.state_evidence(writer))
    else:
        result['supplement']=dict(closed_result=metadata,
            unchanged=capsule(folder/'unchanged-terminal.json'))
    # Capture only facts established by the existing closed producers; final
    # verification brackets all copies and retained predecessor snapshots.
    combined.verified_complete(writer, job)
    for item in (result['combined'], result['rename'].get('witness'),
                 result['supplement'].get('witness'),result['supplement'].get('receipt'),
                 result['supplement'].get('unchanged')):
        if item is not None:retained(item)
    transaction.preserved_pair(job['pair'],job['request']['sha256'])
    result=detached(result)
    result['token']=guard.canonical_digest(request)
    result['binding']=guard.canonical_digest(result)
    return result


class Cleanup:
    """Only this live invocation may unlink its captured detached private pair."""
    def __init__(self, writer, value):
        _, combined, writers, transaction, naming = modules()
        writers.admission(writer)
        folder,job=combined.read(writer,value['request']['combined_token'])
        if job['phase']!='complete' or not guard.same_json(snapshot(writer,folder,job,value['request']),value):
            raise guard.Unavailable('Cleanup requires actual current closed producer facts')
        if current() is not None or transaction.present(writer):
            raise guard.Unavailable('Existing publication or cleanup retained')
        self.writer=writer; self.thread=threading.get_ident(); self.fd=None
        self.root=history(writer); self.root_identity=guard.signature(self.root.lstat())[:2]
        self.path=self.root/(value['token']+'.json');self.value=detached(value)
        link=history(writer,'combined-cleanup-links-v1')/(value['request']['combined_token']+'.json')
        transaction._write(link,dict(version=1,combined_token=value['request']['combined_token'],
                                    cleanup_token=value['token']),exclusive=True)
        self.value['link']=capsule(link)
        self.value['binding']=guard.canonical_digest({key:item for key,item in self.value.items() if key!='binding'})
        self.store=naming.services()[1]
        self.value.update(phase='attempted',fence=None,removed=[])
        self.record=dict(version=1,kind=KIND,token=value['token'],phase='attempted',
                         binding=self.value['binding'],attempt_digest=guard.canonical_digest(self.value),terminal_digest=None)
        if not self.store.create(KIND,value['token'],self.record):
            raise guard.Unavailable('Cleanup already attempted; explicit review required')
        transaction._write(self.path,self.value,exclusive=True)
        self.evidence=guard.private_evidence(self.path)
        self.marker=writer.root/transaction.NAME
        self.mark=dict(version=1,kind=KIND,token=value['token'],binding=self.value['binding'],path=str(self.path))
        transaction._write(self.marker,self.mark,exclusive=True)
        self.marker_evidence=guard.private_evidence(self.marker)
        writer.mark_release_pending();self.fd=checked_file(writer.release_pending)
        self.fence=guard.signature(os.fstat(self.fd))
        updated=dict(self.value,fence=self.fence)
        record=dict(self.record,attempt_digest=guard.canonical_digest(updated))
        if not self.store.replace(KIND,value['token'],self.record,record):
            raise guard.Unavailable('Cleanup attempt changed during fencing')
        self.record=record;self.value=updated
        self.sealed=detached({key:item for key,item in self.value.items() if key not in ('phase','fence','removed')})
        transaction._write(self.path,self.value,exclusive=False);self.evidence=guard.private_evidence(self.path)

    def check(self, writer):
        expected_record=dict(version=1,kind=KIND,token=self.value['token'],phase=self.value['phase'],
            binding=self.value['binding'],attempt_digest=guard.canonical_digest(dict(self.value,phase='attempted')),
            terminal_digest=guard.canonical_digest(self.value) if self.value['phase']=='complete' else None)
        if (self.root!=writer.root/'combined-cleanup-v1'
                or self.path!=self.root/(self.value['token']+'.json')
                or self.marker!=writer.root/modules()[3].NAME
                or self.mark['path']!=str(self.path)
                or self.value['phase'] not in ('attempted','complete')
                or self.value['removed'] not in ([],['original'],['original','restore'])
                or (self.value['phase']=='complete' and self.value['removed']!=['original','restore'])
                or not guard.same_json(self.record,expected_record)
                or not guard.same_json({key:item for key,item in self.value.items() if key not in ('phase','fence','removed')},self.sealed)
                or threading.get_ident()!=self.thread or type(self.fd) is not int
                or writer.root!=self.writer.root or not writer.local[1].depth
                or not guard.same_json(guard.writer_identity(writer),self.value['writer'])
                or guard.signature(self.root.lstat())[:2]!=self.root_identity
                or not writer.fenced(release=True) or writer.fenced() or writer.fenced(tagger=True)
                or guard.signature(writer.release_pending.lstat())!=self.fence
                or guard.signature(os.fstat(self.fd))!=self.fence
                or guard.private_evidence(self.marker)!=self.marker_evidence
                or not guard.same_json(guard.private_json(self.marker),self.mark)
                or guard.private_evidence(self.path)!=self.evidence
                or not guard.same_json(guard.private_json(self.path),self.value)
                or not guard.same_json(self.store.get(KIND,self.value['token']),self.record)):
            raise guard.Unavailable('Cleanup capability or independent attempt changed')
        mylar, *_=modules()
        census,_=guard.registry_snapshot(Path(mylar.DATA_DIR)/'workflow.sqlite',writer.root/'publication-v1.json')
        if not guard.same_json(census,self.value['source']['census']):
            raise guard.Unavailable('Cleanup census changed')

    def observation_path(self, path):
        admitted(self,self.writer)
        return Path(path)

    def checkpoint(self):
        admitted(self,self.writer)
        mylar, _, _, transaction, naming=modules(); facts=self.value['source']
        proof=native.require(Path(facts['path']),issueid=facts['owner']['issueid'],
                             comicid=facts['owner']['parentcomicid'],transaction=self)
        selected=guard.observe_owners(Path(mylar.DATA_DIR)/'mylar.db',self.writer,[facts['owner']],
                                     [mylar.CONFIG.DESTINATION_DIR],transaction=self)['observed']
        if (not guard.same_json(proof['owner'],facts['owner'])
                or proof['inventory']['payload']!=facts['payload']
                or proof['inventory']['source_sha256']!=facts['sha256']
                or not guard.same_json(proof['inventory']['source_signature'],facts['signature'])
                or not guard.same_json(selected,facts['observed'])):
            raise guard.Unavailable('Cleanup current publication changed')
        for item in (self.value['link'],self.value['combined'],self.value['rename'].get('witness'),
                     self.value['supplement'].get('witness'),self.value['supplement'].get('receipt'),
                     self.value['supplement'].get('unchanged')):
            if item is not None:retained(item)
        rename=self.value['rename']; supplement=self.value['supplement']
        if 'job' in rename and (not guard.same_json(naming.services()[1].get('release_name',rename['job']['key']),rename['job'])
                or guard.signature((self.writer.root/'release-completed-v1').lstat())[:2]!=rename['history_identity']):
            raise guard.Unavailable('Cleanup Rename history changed')
        if 'witness' in supplement and (transaction.history_identity(self.writer.root/'tagger-completed-v1')!=supplement['history_identity']
                or not guard.same_json(transaction.state_evidence(self.writer),supplement['recovery'])):
            raise guard.Unavailable('Cleanup Tagging history changed')
        for name,row in self.value['pair'].items():
            path=Path(row['path'])
            if name in self.value['removed']:
                if os.path.lexists(path):raise guard.Unavailable('Retired copy recreated')
            else:
                signature,checksum=guard.file_hash(path)
                before=self.value['combined']['value']['request']['sha256']
                if checksum!=before or not guard.same_json(signature,row['signature']):
                    raise guard.Unavailable('Cleanup preserved copy changed')
        self.check(self.writer)
        if not guard.same_json(guard.signature(Path(facts['path']).lstat()),facts['signature']):
            raise guard.Unavailable('Cleanup final source incarnation changed')

    @contextmanager
    def owned(self):
        if current() is not None:raise guard.Unavailable('Nested cleanup refused')
        _LOCAL.cleanup=self
        try:yield self
        finally:
            _LOCAL.cleanup=None
            if self.fd is not None:os.close(self.fd);self.fd=None

    def unlink(self, name):
        _, _, _, transaction, _=modules()
        self.checkpoint()
        if name != ('original' if not self.value['removed'] else 'restore') or name in self.value['removed']:
            raise guard.Unavailable('Exact private unlink required')
        row=self.value['pair'][name];path=Path(row['path'])
        folder=Path(self.value['combined']['path']).parent
        if path!=folder/(name+'.cbz') or path.stat().st_nlink!=1:
            raise guard.Unavailable('Private original namespace changed')
        # Admission does not expose an archive publisher or catalog mutation.
        path.unlink();sync(folder)
        updated=dict(self.value,removed=self.value['removed']+[name])
        record=dict(self.record,attempt_digest=guard.canonical_digest(updated))
        if not self.store.replace(KIND,self.value['token'],self.record,record):
            raise guard.Unavailable('Cleanup deletion acknowledgment changed')
        self.value=updated;self.record=record
        transaction._write(self.path,self.value,exclusive=False);self.evidence=guard.private_evidence(self.path)

    def complete(self):
        _, _, _, transaction, _=modules()
        self.checkpoint()
        if set(self.value['removed'])!={'original','restore'}:
            raise guard.Unavailable('Cleanup pair incomplete')
        updated=dict(self.value,phase='complete')
        record=dict(self.record,phase='complete',terminal_digest=guard.canonical_digest(updated))
        transaction._write(self.path,updated,exclusive=False)
        self.value=updated;self.evidence=guard.private_evidence(self.path)
        if not self.store.replace(KIND,self.value['token'],self.record,record):
            raise guard.Unavailable('Cleanup terminal acknowledgment changed')
        self.record=record;self.checkpoint()
        try:
            self.writer.clear_release_pending();self.marker.unlink();sync(self.writer.root)
        except BaseException:
            if not os.path.lexists(self.marker):transaction._write(self.marker,self.mark,exclusive=True)
            raise
        return detached(self.record)


def clean(request):
    _, combined, writers, _, naming=modules()
    try:
        if (not isinstance(request,dict) or not isinstance(request.get('combined_token'),str)
                or not re.fullmatch('[0-9a-f]{64}',request['combined_token'])):
            raise guard.Unavailable('Exact cleanup acceptance required')
        with writers.operation() as writer:
            key=guard.canonical_digest(request)
            prior=naming.services()[1].get(KIND,key)
            if prior is not None:
                if prior.get('phase')!='complete':raise guard.Unavailable('Uncertain cleanup requires explicit review')
                path=history(writer,create=False)/(key+'.json');saved=guard.private_json(path);facts=saved['source']
                retired_supplement(writer,cleanup_token=key,source=Path(facts['path']),
                    owner=facts['owner'],payload=facts['payload'],census=facts['census'],lineage=request['lineage'])
                if not guard.same_json(saved['request'],request):raise guard.Unavailable('Cleanup acceptance changed')
                return prior
            folder,job=combined.read(writer,request['combined_token'])
            if job['phase']!='complete':raise guard.Unavailable('Final combined acceptance required')
            value=snapshot(writer,folder,job,request)
            capability=Cleanup(writer,value)
            with capability.owned():
                capability.unlink('original');capability.unlink('restore')
                return capability.complete()
    except (guard.Unavailable,OSError,ValueError,TypeError,KeyError):
        raise native.Review('combined-cleanup-requires-review') from None


def retired_supplement(writer, *, cleanup_token, source, owner, payload, census, lineage):
    """Read a terminal retirement; never reconstruct deletion or publication rights."""
    mylar, combined, writers, transaction, naming=modules()
    writers.admission(writer)
    if (not writers.active() or writers.owner().root!=writer.root or not writer.local[1].depth
            or transaction.present(writer) or any(writer.fenced(**flags) for flags in
                ({},{'tagger':True},{'release':True}))
            or not isinstance(cleanup_token,str) or not re.fullmatch('[0-9a-f]{64}',cleanup_token)):
        raise guard.Unavailable('Closed retirement requires fresh native admission')
    root=history(writer,create=False);root_id=guard.signature(root.lstat())[:2]
    path=root/(cleanup_token+'.json');evidence=guard.private_evidence(path);value=guard.private_json(path)
    owner=guard.exact_owner(owner);census=guard.census_value(census);source=Path(source)
    fields={'version','kind','request','writer','combined','source','policy','pair','rename','supplement',
            'token','binding','phase','fence','removed','link'}
    base={key:item for key,item in value.items() if key not in ('binding','phase','fence','removed')}
    attempted=dict(value,phase='attempted')
    expected=dict(version=1,kind=KIND,token=cleanup_token,phase='complete',binding=value.get('binding'),
        attempt_digest=guard.canonical_digest(attempted),terminal_digest=guard.canonical_digest(value))
    record=naming.services()[1].get(KIND,cleanup_token)
    if (set(value)!=fields or type(value['version']) is not int or value['version']!=1
            or value['kind']!='combined-cleanup-v1' or value['phase']!='complete'
            or value['token']!=cleanup_token or guard.canonical_digest(value['request'])!=cleanup_token
            or guard.canonical_digest(base)!=value['binding'] or value['removed']!=['original','restore']
            or not guard.same_json(record,expected) or not guard.same_json(value['writer'],guard.writer_identity(writer))
            or value['request']['lineage']!=lineage or value['source']['path']!=str(source)
            or not guard.same_json(value['source']['owner'],owner) or value['source']['payload']!=payload
            or not guard.same_json(value['source']['census'],census)):
        raise guard.Unavailable('Closed retirement is not independently bound')
    job=value['combined']['value']
    if (job['phase']!='complete' or value['request']['combined_token']!=job['token']
            or value['request']['binding']!=job['binding']
            or guard.canonical_digest(combined.immutable(job))!=job['binding']
            or not guard.same_json(value['pair'],job['pair']) or not guard.same_json(value['policy'],job['policy'])
            or not guard.same_json(value['supplement']['closed_result'],job['metadata'])):
        raise guard.Unavailable('Closed retirement combined history changed')
    acceptance(value['request'],job,combined.acknowledgement(writer,job))
    folder=Path(value['combined']['path']).parent
    if folder!=writer.root/'combined-publication-v1'/job['token']:
        raise guard.Unavailable('Closed retirement pair namespace changed')
    def private_final():
        for name,row in value['pair'].items():
            if name not in ('original','restore') or row['path']!=str(folder/(name+'.cbz')) or os.path.lexists(row['path']):
                raise guard.Unavailable('Closed retired pair differs or was recreated')
        expected_link=writer.root/'combined-cleanup-links-v1'/(job['token']+'.json')
        if (value['link']['path']!=str(expected_link) or not guard.same_json(value['link']['value'],
                dict(version=1,combined_token=job['token'],cleanup_token=cleanup_token))):
            raise guard.Unavailable('Closed retirement link differs from independent terminal')
        for item in (value['link'],value['combined'],value['rename'].get('witness'),value['supplement'].get('witness'),
                     value['supplement'].get('receipt'),value['supplement'].get('unchanged')):
            if item is not None:retained(item)
        rename=value['rename'];supplement=value['supplement']
        if 'job' in rename:
            saved=rename['job'];witness=rename['witness']['value']
            if (not guard.same_json(naming.services()[1].get('release_name',saved['key']),saved)
                    or guard.signature((writer.root/'release-completed-v1').lstat())[:2]!=rename['history_identity']
                    or not guard.same_json(witness['job'],saved)):
                raise guard.Unavailable('Closed retired Rename history changed')
        if 'witness' in supplement:
            closed=supplement['witness']['value']['job'];terminal=closed['completion']
            if (transaction.history_identity(writer.root/'tagger-completed-v1')!=supplement['history_identity']
                    or not guard.same_json(transaction.state_evidence(writer),supplement['recovery'])
                    or not guard.same_json(supplement['receipt']['value'],terminal['record'])
                    or supplement['receipt']['path']!=terminal['receipt']
                    or not guard.same_json(supplement['receipt']['incarnation'],terminal['receipt_evidence'])
                    or transaction.terminal_digest(terminal)!=job['metadata']['receipt_digest']
                    or supplement['witness']['digest']!=job['metadata']['witness_digest']):
                raise guard.Unavailable('Closed retired Tagging history changed')
        if (guard.private_evidence(path)!=evidence or not guard.same_json(guard.private_json(path),value)
                or guard.signature(root.lstat())[:2]!=root_id
                or not guard.same_json(naming.services()[1].get(KIND,cleanup_token),record)):
            raise guard.Unavailable('Closed retirement evidence changed during read')
    private_final()
    facts=value['source']
    actual=native.require(source,issueid=owner['issueid'],comicid=owner['parentcomicid'])
    selected=guard.observe_owners(Path(mylar.DATA_DIR)/'mylar.db',writer,[owner],
                                  [mylar.CONFIG.DESTINATION_DIR])['observed']
    fresh,_=guard.registry_snapshot(Path(mylar.DATA_DIR)/'workflow.sqlite',writer.root/'publication-v1.json')
    if (actual['inventory']['source_sha256']!=facts['sha256'] or actual['inventory']['payload']!=payload
            or not guard.same_json(actual['inventory']['source_signature'],facts['signature'])
            or not guard.same_json(actual['owner'],owner) or not guard.same_json(selected,facts['observed'])
            or not guard.same_json(fresh,census)):
        raise guard.Unavailable('Closed retirement current publication changed')
    if not guard.same_json(guard.signature(source.lstat()),facts['signature']):
        raise guard.Unavailable('Closed retirement final source incarnation changed')
    writers.admission(writer)
    if transaction.present(writer) or any(writer.fenced(**flags) for flags in ({},{'tagger':True},{'release':True})):
        raise guard.Unavailable('Closed retirement admission changed')
    if not guard.same_json(guard.signature(source.lstat()),facts['signature']):
        raise guard.Unavailable('Closed retirement source changed during final admission')
    final_selected=guard.observe_owners(Path(mylar.DATA_DIR)/'mylar.db',writer,[owner],
                                       [mylar.CONFIG.DESTINATION_DIR])['observed']
    if not guard.same_json(final_selected,facts['observed']):
        raise guard.Unavailable('Closed retirement catalog changed during final admission')
    private_final()
    if (not guard.same_json(guard.signature(source.lstat()),facts['signature'])
            or transaction.present(writer) or any(writer.fenced(**flags) for flags in ({},{'tagger':True},{'release':True}))):
        raise guard.Unavailable('Closed retirement final source or exclusion changed')
    return dict(value['supplement']['closed_result'],cleanup_token=cleanup_token,
                cleanup_digest=record['terminal_digest'])


def resolve(writer, combined_token):
    """Resolve a passive link only through a completed independently bound proof."""
    _, combined, _, transaction, _=modules()
    if not isinstance(combined_token,str) or not re.fullmatch('[0-9a-f]{64}',combined_token):
        raise guard.Unavailable('Exact combined cleanup link token required')
    link=writer.root/'combined-cleanup-links-v1'/(combined_token+'.json')
    if not os.path.lexists(link):return None
    saved=capsule(link);value=saved['value']
    if (set(value)!={'version','combined_token','cleanup_token'} or type(value['version']) is not int
            or value['version']!=1 or value['combined_token']!=combined_token
            or not isinstance(value['cleanup_token'],str) or not re.fullmatch('[0-9a-f]{64}',value['cleanup_token'])):
        raise guard.Unavailable('Exact closed cleanup link required')
    path=history(writer,create=False)/(value['cleanup_token']+'.json');terminal=guard.private_json(path)
    if not guard.same_json(terminal.get('link'),saved):raise guard.Unavailable('Cleanup link is not independently bound')
    facts=terminal['source'];request=terminal['request']
    closed=transaction.closed_retired_supplement(writer,cleanup_token=value['cleanup_token'],source=Path(facts['path']),
        owner=facts['owner'],payload=facts['payload'],census=facts['census'],lineage=request['lineage'])
    retained(saved)
    ack=combined.acknowledgement(writer,terminal['combined']['value'])
    return dict(ack,cleanup=dict(version=1,token=value['cleanup_token'],digest=closed['cleanup_digest'],phase='complete'))
