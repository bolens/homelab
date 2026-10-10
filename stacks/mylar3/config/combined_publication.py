"""Finite native combined-pass orchestration; journals never grant mutation rights."""
from functools import wraps
import json
import os
from pathlib import Path
import re
import shutil
import stat
import uuid
import zipfile


def modules():
    import mylar
    from mylar import native_writers, publication_guard, publication_native, release_naming
    from mylar import publication_transaction, tagger_supplement, publication_rename
    return (mylar, native_writers, publication_guard, publication_native, release_naming,
            publication_transaction, tagger_supplement, publication_rename)


def held(function):
    @wraps(function)
    def run(*args, **kwargs):
        _, _, guard, native, *_ = modules()
        try:
            return function(*args, **kwargs)
        except (guard.Unavailable, OSError, ValueError, TypeError, KeyError, zipfile.BadZipFile):
            raise native.Review('combined-publication-evidence-unavailable') from None
    return run


def immutable(job):
    value = {key: job[key] for key in ('version', 'kind', 'token', 'request', 'policy',
            'manifest', 'owner', 'payload', 'census', 'observed', 'writer', 'pair', 'metadata_token')}
    if 'preview' in job:
        value['preview']=job['preview'];value['approved_additions']=job['approved_additions']
    return value


def root(writer):
    path = writer.root/'combined-publication-v1'
    if not path.exists():
        path.mkdir(mode=0o700)
        from mylar.media_writer import sync
        sync(writer.root)
    info = path.lstat()
    if (path.is_symlink() or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise ValueError('Private native combined state required')
    return path


def read(writer, token):
    _, _, guard, _, _, transaction, *_ = modules()
    if not isinstance(token, str) or not re.fullmatch('[0-9a-f]{64}', token):
        raise ValueError('Exact combined token required')
    folder = root(writer)/token
    info = folder.lstat()
    if (folder.is_symlink() or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise ValueError('Private combined preparation required')
    job = guard.private_json(folder/'receipt.json')
    if (job.get('version') != 1 or type(job.get('version')) is not int
            or job.get('kind') != 'combined-root-v1' or job.get('token') != token
            or job.get('phase') not in ('prepared', 'rename-uncertain', 'renamed',
                                      'metadata-uncertain', 'complete')
            or guard.canonical_digest(immutable(job)) != job.get('binding')
            or not guard.same_json(job['writer'], guard.writer_identity(writer))
            or guard.canonical_digest(dict(request=job['request'], policy=job['policy'],
                                           manifest=job['manifest'])) != token):
        raise ValueError('Immutable combined preparation changed')
    for name, row in job['pair'].items():
        if name not in ('original', 'restore') or row['path'] != str(folder/(name+'.cbz')):
            raise ValueError('Combined preservation namespace changed')
    transaction.preserved_pair(job['pair'], job['request']['sha256'])
    return folder, job


def save(folder, job, *, exclusive=False):
    from mylar.publication_transaction import _write
    _write(folder/'receipt.json', job, exclusive=exclusive)


def receipt_check(writer,folder,expected,evidence):
    _, _, guard, native, *_=modules()
    if (guard.private_evidence(folder/'receipt.json')!=evidence
            or not guard.same_json(read(writer,expected['token'])[1],expected)):
        raise native.Review('combined-receipt-incarnation-changed')


def envelope_check(folder,expected,evidence):
    _, _, guard, native, *_=modules()
    if (guard.private_evidence(folder/'receipt.json')!=evidence
            or not guard.same_json(guard.private_json(folder/'receipt.json'),expected)):
        raise native.Review('combined-receipt-envelope-changed')


def current(writer, job, path, checksum):
    mylar, _, guard, native, _, _, _, _ = modules()
    census, _ = guard.registry_snapshot(Path(mylar.DATA_DIR)/'workflow.sqlite',
                                        writer.root/'publication-v1.json')
    proof = native.require(path, issueid=job['request']['issueid'],
                           comicid=job['request']['comicid'])
    selected = guard.observe_owners(Path(mylar.DATA_DIR)/'mylar.db', writer, [job['owner']],
                                    [mylar.CONFIG.DESTINATION_DIR])['observed']
    if (not guard.same_json(census, job['census'])
            or not guard.same_json(proof['owner'], job['owner'])
            or proof['inventory']['payload'] != job['payload']
            or proof['inventory']['source_sha256'] != checksum
            or selected[0]['catalog']['path'] != str(path)
            or selected[0]['source_sha256'] != checksum):
        raise native.Review('combined-current-publication-changed')
    before = job['observed'][0]['catalog']
    after = selected[0]['catalog']
    if not guard.same_json({k: v for k, v in before.items() if k not in ('path', 'location')},
                           {k: v for k, v in after.items() if k not in ('path', 'location')}):
        raise native.Review('combined-current-catalog-changed')
    return proof, selected


def preview_arguments(value):
    from mylar.tagger_enrichment import validate
    if not isinstance(value,dict) or set(value)!={'naming','policy'}:
        raise ValueError('Exact native supplement preview arguments required')
    request=json.loads(json.dumps(value['naming']))
    policy=json.loads(json.dumps(validate(value['policy'])))
    if (not isinstance(request,dict) or set(request)!={'version','source','target','sha256','issueid','comicid'}
            or type(request['version']) is not int or request['version']!=1
            or not isinstance(request['source'],str) or not Path(request['source']).is_absolute()
            or '..' in Path(request['source']).parts or not isinstance(request['target'],str)
            or Path(request['target']).name!=request['target'] or not request['target'].endswith('.cbz')
            or not isinstance(request['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',request['sha256'])
            or any(not isinstance(request[k],str) or not re.fullmatch('[1-9][0-9]{0,15}',request[k])
                   for k in ('issueid','comicid'))):
        raise ValueError('Exact native supplement preview source required')
    return request,policy


def preview_observation(writer,request,policy):
    """Actual native derivation and current authority; no journals or capabilities."""
    mylar,writers,guard,native,naming,_,supplement,_=modules()
    from mylar.tagger_enrichment import supplements
    paths=[Path(mylar.DATA_DIR)/name for name in ('mylar.db','workflow.sqlite')]
    paths.append(writer.root/'publication-v1.json')
    source=Path(request['source'])
    originals={}
    for path in (*paths,source):
        info=path.lstat()
        originals[str(path)]=(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,
            info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)
    ancestors={parent for path in (*paths,source,writer.lock) for parent in path.parents}
    nodes={}
    for parent in ancestors:
        info=parent.lstat()
        nodes[str(parent)]=(info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)
    lock_info=writer.lock.lstat()
    lock_stamp=(lock_info.st_dev,lock_info.st_ino,lock_info.st_size,lock_info.st_mtime_ns,
                lock_info.st_ctime_ns,lock_info.st_mode,lock_info.st_uid,lock_info.st_gid,lock_info.st_nlink)
    writers.admission(writer)
    identity=guard.writer_identity(writer)
    stamps={str(path):guard.file_hash(path) for path in paths}
    if any(tuple(stamps[str(path)][0])!=originals[str(path)] for path in paths):
        raise native.Review('combined-preview-initial-control-changed')
    database,_=naming.services();proposal=naming.proposal(database,source)
    if any(proposal[key]!=request[key] for key in ('version','source','sha256','issueid','comicid')):
        raise native.Review('combined-preview-proposal-stale')
    proof=native.require(source,issueid=request['issueid'],comicid=request['comicid'])
    census=guard.media_snapshot(paths[1],paths[2])[0]
    observed=guard.observe_owners(paths[0],writer,[proof['owner']],[mylar.CONFIG.DESTINATION_DIR])['observed']
    additions=supplements(supplement.metadata(source),policy)
    fresh=native.require(source,issueid=request['issueid'],comicid=request['comicid'])
    if (not guard.same_json(fresh,proof) or observed[0]['catalog']['path']!=str(source)
            or observed[0]['source_sha256']!=request['sha256']
            or proof['inventory']['source_sha256']!=request['sha256']
            or tuple(proof['inventory']['source_signature'])!=originals[str(source)]):
        raise native.Review('combined-preview-source-changed')
    writers.admission(writer)
    if (guard.writer_identity(writer)!=identity
            or any(guard.file_hash(path)!=stamps[str(path)] for path in paths)
            or guard.file_hash(source)!=(list(originals[str(source)]),request['sha256'])):
        raise native.Review('combined-preview-authority-changed')
    guard.ordinary_root(writer.root)
    if (writer.fenced() or writer.fenced(tagger=True) or writer.fenced(release=True)
            or any(os.path.lexists(writer.root/name) for name in
                   ('tagger-publication-v1.json','nested-derivative-v1.json','tagger-recovery-v1.pending'))):
        raise native.Review('combined-preview-pending-publication')
    if guard.writer_identity(writer)!=identity:
        raise native.Review('combined-preview-writer-changed')
    value=dict(version=1,protocol='combined-preview-v1',request=request,policy=policy,
        owner=proof['owner'],census=census,payload=proof['inventory']['payload'],observed=observed,
        writer=identity,source_signature=list(originals[str(source)]),additions=additions)
    value['binding']=guard.canonical_digest(value)
    # Retain helper observations, but never let their replaceable callbacks be the
    # last authority check. Response construction also precedes the raw closure.
    if (any(tuple(guard.signature(path.lstat()))!=originals[str(path)] for path in paths)
            or tuple(guard.signature(source.lstat()))!=originals[str(source)]):
        raise native.Review('combined-preview-final-evidence-changed')
    absent=[Path(str(path)+suffix) for path in paths[:2] for suffix in ('-journal','-wal','-shm')]
    absent.extend(writer.root/name for name in ('normalizer-v1.pending','tagger-v2.pending',
        'release-v1.pending','tagger-publication-v1.json','nested-derivative-v1.json',
        'tagger-recovery-v1.pending'))
    for path in absent:
        try:path.lstat()
        except FileNotFoundError:pass
        else:raise native.Review('combined-preview-final-pending-changed')
    for parent in ancestors:
        info=parent.lstat()
        if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=nodes[str(parent)]:
            raise native.Review('combined-preview-final-ancestor-changed')
    info=writer.lock.lstat()
    if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,
            info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=lock_stamp:
        raise native.Review('combined-preview-final-writer-changed')
    for path in (*paths,source):
        expected=originals[str(path)]
        info=path.lstat()
        if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,
                info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=expected:
            raise native.Review('combined-preview-final-evidence-changed')
    return value


@held
def preview(value):
    request,policy=preview_arguments(value)
    with modules()[1].operation() as writer:
        return preview_observation(writer,request,policy)


@held
def prepare(value):
    mylar, writers, guard, native, naming, transaction, _, _ = modules()
    if (not isinstance(value, dict) or set(value) not in ({'naming', 'policy', 'manifest'},{'naming', 'policy', 'manifest','preview','approved_additions'})
            or not isinstance(value['manifest'], str)
            or not re.fullmatch('[0-9a-f]{64}', value['manifest'])):
        raise ValueError('Reviewed combined manifest binding required')
    value=json.loads(json.dumps(value))
    from mylar.tagger_enrichment import validate
    request = json.loads(json.dumps(value['naming']))
    policy = json.loads(json.dumps(validate(value['policy'])))
    if (not isinstance(request, dict) or set(request) !=
            {'version', 'source', 'target', 'sha256', 'issueid', 'comicid'}
            or type(request['version']) is not int or request['version'] != 1
            or Path(request['target']).name != request['target'] or not request['target'].endswith('.cbz')):
        raise ValueError('Exact ordinary naming request required')
    token = guard.canonical_digest(dict(request=request, policy=policy, manifest=value['manifest']))
    with writers.operation() as writer:
        folder = writer.root/'combined-publication-v1'/token
        supplied=value.get('preview')
        if 'preview' in value and (not isinstance(supplied,dict) or not isinstance(value['approved_additions'],dict)):
            raise native.Review('combined-preview-required')
        if not folder.exists() and supplied is not None:
            actual=preview_observation(writer,request,policy)
            if (not guard.same_json(actual,supplied)
                    or not guard.same_json(actual['additions'],value['approved_additions'])):
                raise native.Review('combined-approved-preview-changed')
            if Path(request['source']).name==request['target'] and not actual['additions']:
                raise native.Review('combined-canonical-no-additions')
        folder = root(writer)/token
        if folder.exists():
            _, job = read(writer, token)
            if (not guard.same_json(job.get('preview'),supplied)
                    or not guard.same_json(job.get('approved_additions'),value.get('approved_additions'))):
                raise native.Review('combined-existing-preview-changed')
            evidence=guard.private_evidence(folder/'receipt.json')
            if job['phase']=='complete':
                verified_complete(writer,job)
            elif job['phase']=='renamed':
                rename_closed(writer,job)
            elif job['phase']=='prepared':
                current(writer,job,Path(job['request']['source']),job['request']['sha256'])
            else:
                raise native.Review('combined-existing-attempt-requires-status')
            transaction.preserved_pair(job['pair'],job['request']['sha256'])
            envelope_check(folder,job,evidence)
            return acknowledgement(writer, job)
        source = Path(request['source'])
        database, _ = naming.services()
        proposal = naming.proposal(database, source)
        if any(proposal[key] != request[key] for key in ('version', 'source', 'sha256', 'issueid', 'comicid')):
            raise native.Review('combined-proposal-stale')
        proof = native.require(source, issueid=request['issueid'], comicid=request['comicid'])
        census, _ = guard.registry_snapshot(Path(mylar.DATA_DIR)/'workflow.sqlite',
                                            writer.root/'publication-v1.json')
        observed = guard.observe_owners(Path(mylar.DATA_DIR)/'mylar.db', writer, [proof['owner']],
                                       [mylar.CONFIG.DESTINATION_DIR])['observed']
        if observed[0]['catalog']['path'] != str(source):
            raise native.Review('combined-original-not-current')
        if supplied is not None and (not guard.same_json(proof['owner'],supplied['owner'])
                or not guard.same_json(census,supplied['census'])
                or not guard.same_json(observed,supplied['observed'])
                or proof['inventory']['payload']!=supplied['payload']
                or not guard.same_json(proof['inventory']['source_signature'],supplied['source_signature'])
                or guard.writer_identity(writer)!=supplied['writer']):
            raise native.Review('combined-preview-changed-before-copies')
        folder.mkdir(mode=0o700)
        from mylar.media_writer import sync
        sync(folder.parent)
        pair = {}
        for name in ('original', 'restore'):
            copy = folder/(name+'.cbz')
            with guard.regular(source) as reader, copy.open('xb') as target:
                shutil.copyfileobj(reader, target, 1024*1024)
                target.flush()
                shutil.copystat(source, copy)
                os.fsync(target.fileno())
            signature, checksum = guard.file_hash(copy)
            if checksum != request['sha256']:
                raise native.Review('combined-copy-verification-failed')
            pair[name] = dict(path=str(copy), signature=signature)
        transaction.preserved_pair(pair, request['sha256'])
        sync(folder)
        job = dict(version=1, kind='combined-root-v1', token=token, request=request,
                   policy=policy, manifest=value['manifest'], owner=proof['owner'],
                   payload=proof['inventory']['payload'], census=census, observed=observed,
                   writer=guard.writer_identity(writer), pair=pair, phase='prepared', metadata_token=uuid.uuid4().hex)
        if supplied is not None:
            job['preview']=json.loads(json.dumps(supplied))
            job['approved_additions']=json.loads(json.dumps(value['approved_additions']))
        job['binding'] = guard.canonical_digest(immutable(job))
        fresh, selected = current(writer, job, source, request['sha256'])
        if (not guard.same_json(selected, observed)
                or not guard.same_json(fresh['inventory']['source_signature'], proof['inventory']['source_signature'])):
            raise native.Review('combined-original-changed-during-copy')
        transaction.preserved_pair(job['pair'],request['sha256'])
        save(folder, job, exclusive=True)
        return acknowledgement(writer, job)


def acknowledgement(writer, job):
    _, _, guard, _, _, _, _, _ = modules()
    return dict(version=1, protocol='combined-root-v1', token=job['token'], phase=job['phase'],
                binding=job['binding'], request=job['request'], owner=job['owner'], payload=job['payload'],
                census=job['census'], before=job['request']['sha256'],
                after=job.get('metadata', {}).get('after', job['request']['sha256']),
                lineage=guard.canonical_digest({key: job.get(key) for key in
                    ('binding', 'rename', 'reader_move', 'metadata')}))


def rename_closed(writer, job):
    _, _, guard, native, naming, transaction, _, rename = modules()
    if Path(job['request']['source']).name == job['request']['target']:
        current(writer, job, Path(job['request']['source']), job['request']['sha256'])
        transaction.preserved_pair(job['pair'],job['request']['sha256'])
        return dict(token=None, digest=job['binding'], destination=job['request']['source'],
                    sha256=job['request']['sha256'])
    saved = naming.services()[1].get('release_name', naming.key(job['request']))
    if saved is None or saved.get('phase') != 'committed':
        raise native.Review('combined-rename-uncertain')
    witness_path=writer.root/'release-completed-v1'/(saved['key']+'.json')
    witness_evidence=guard.private_evidence(witness_path)
    path = Path(job['request']['source']).with_name(job['request']['target'])
    current(writer, job, path, job['request']['sha256'])
    witness=rename.terminal(writer,saved)
    transaction.preserved_pair(job['pair'],job['request']['sha256'])
    if (guard.private_evidence(witness_path)!=witness_evidence
            or not guard.same_json(guard.private_json(witness_path),witness)
            or not guard.same_json(naming.services()[1].get('release_name',saved['key']),saved)):
        raise native.Review('combined-rename-incarnation-changed')
    return dict(token=saved['key'], digest=saved['terminal_proof'],
                destination=str(path), sha256=job['request']['sha256'])


@held
def rename(token):
    _, writers, guard, native, naming, *_ = modules()
    with writers.operation() as writer:
        folder, job = read(writer, token)
        if job['phase'] == 'rename-uncertain':
            expected=json.loads(json.dumps(job));evidence=guard.private_evidence(folder/'receipt.json')
            result=rename_closed(writer,job)
            envelope_check(folder,expected,evidence)
            job['rename'] = result
            job['phase'] = 'renamed'
            save(folder, job)
        elif job['phase'] == 'prepared':
            current(writer, job, Path(job['request']['source']), job['request']['sha256'])
            job['phase'] = 'rename-uncertain'
            save(folder, job)
            expected=json.loads(json.dumps(job));evidence=guard.private_evidence(folder/'receipt.json')
            if Path(job['request']['source']).name != job['request']['target']:
                naming.rename(job['request'])
            receipt_check(writer,folder,expected,evidence)
            result=rename_closed(writer,job)
            envelope_check(folder,expected,evidence)
            job['rename'] = result
            job['phase'] = 'renamed'
            save(folder, job)
        elif job['phase'] == 'renamed':
            evidence=guard.private_evidence(folder/'receipt.json')
            if not guard.same_json(rename_closed(writer, job), job['rename']):
                raise native.Review('combined-rename-terminal-changed')
            envelope_check(folder,job,evidence)
        else:
            raise native.Review('combined-rename-replay-refused')
        return acknowledgement(writer, job)


def reader_move(value, job):
    """Bind worker's independently verified move; never grant owner authority."""
    if (not isinstance(value, dict) or set(value) !=
            {'version', 'binding', 'destination', 'sha256', 'bookid', 'hash', 'pages', 'libraryid', 'seriesid'}
            or type(value['version']) is not int or value['version'] != 1
            or value['binding'] != job['binding'] or value['destination'] != job['rename']['destination']
            or value['sha256'] != job['request']['sha256'] or type(value['pages']) is not int or value['pages'] < 1
            or any(not isinstance(value[key], str) or not value[key] for key in
                   ('bookid', 'hash', 'libraryid', 'seriesid'))):
        raise ValueError('Exact worker reader move binding required')
    return json.loads(json.dumps(value))


def metadata_closed(writer, job):
    _, _, _, native, _, transaction, _, _ = modules()
    method = getattr(transaction, 'closed_supplement', None)
    if not callable(method):
        raise native.Review('combined-terminal-reader-capability-required')
    result=method(writer, token=job['metadata_token'], source=Path(job['rename']['destination']),
                  before_sha256=job['request']['sha256'], owner=job['owner'], payload=job['payload'],
                  census=job['census'], preservation=job['pair'], policy=job['policy'])
    return dict(result,state='unchanged' if result['before']==result['after'] else 'committed')


@held
def metadata(token, move):
    _, writers, guard, native, _, _, supplement, _ = modules()
    with writers.operation() as writer:
        folder, job = read(writer, token)
        expected=json.loads(json.dumps(job));receipt_evidence=guard.private_evidence(folder/'receipt.json')
        if job['phase'] == 'metadata-uncertain':
            if (folder/'unchanged-terminal.json').exists():
                closed,digest=unchanged_closed(writer,job)
                job['unchanged_terminal']=digest
            else:
                closed = metadata_closed(writer, job)
        elif job['phase'] == 'renamed':
            if not guard.same_json(rename_closed(writer, job), job['rename']):
                raise native.Review('combined-rename-terminal-changed')
            job['reader_move'] = reader_move(move, job)
            path = Path(job['rename']['destination'])
            current(writer, job, path, job['request']['sha256'])
            if 'preview' in job:
                from mylar.tagger_enrichment import supplements
                if not guard.same_json(supplements(supplement.metadata(path),job['policy']),job['preview']['additions']):
                    raise native.Review('combined-approved-additions-changed')
            job.update(phase='metadata-uncertain')
            save(folder, job)
            submitted=json.loads(json.dumps(job))
            expected=submitted;receipt_evidence=guard.private_evidence(folder/'receipt.json')
            publisher = supplement.bound_publisher(writer)
            result = supplement.apply_preserved(path, job['policy'], writer, publisher,
                Path(job['pair']['original']['path']), Path(job['pair']['restore']['path']),
                job['request']['sha256'], job['metadata_token'])
            if result['state'] == 'unchanged' and result['token'] is None:
                # No Tagging receipt exists; retain a separate exact unchanged
                # witness before allowing any restart acknowledgment.
                current(writer, job, path, job['request']['sha256'])
                closed = dict(version=1, token=None, source=str(path), before=job['request']['sha256'],
                              after=job['request']['sha256'], owner=job['owner'], payload=job['payload'],
                              census=job['census'], state='unchanged')
                proof, observed = current(writer, job, path, job['request']['sha256'])
                witness=dict(version=1,kind='combined-unchanged-v1',binding=job['binding'],
                    rename=job['rename'],reader_move=job['reader_move'],metadata=closed,
                    signature=proof['inventory']['source_signature'],observed=observed)
                from mylar.publication_transaction import _write
                _write(folder/'unchanged-terminal.json',witness,exclusive=True)
                job['unchanged_terminal']=guard.canonical_digest(witness)
            else:
                closed = metadata_closed(writer, job)
            if read(writer, token)[1] != submitted:
                raise native.Review('combined-metadata-journal-changed')
        elif job['phase'] == 'complete':
            verified_complete(writer, job)
            return acknowledgement(writer, job)
        else:
            raise native.Review('combined-reader-move-required-before-metadata')
        if not isinstance(closed, dict) or closed.get('state') not in ('committed', 'unchanged'):
            raise native.Review('combined-metadata-terminal-required')
        current(writer, job, Path(job['rename']['destination']), closed['after'])
        receipt_check(writer,folder,expected,receipt_evidence)
        if closed.get('token') is not None and not guard.same_json(metadata_closed(writer,job),closed):
            raise native.Review('combined-terminal-changed-at-completion')
        elif closed.get('token') is None:
            verified,digest=unchanged_closed(writer,job)
            if not guard.same_json(verified,closed):raise native.Review('combined-unchanged-terminal-changed')
        envelope_check(folder,expected,receipt_evidence)
        job.update(metadata=closed, phase='complete')
        save(folder, job)
        return acknowledgement(writer, job)


def unchanged_closed(writer,job):
    _, _, guard, native, _, _, _, _=modules()
    path_witness=root(writer)/job['token']/'unchanged-terminal.json'
    witness_evidence=guard.private_evidence(path_witness)
    witness=guard.private_json(path_witness)
    closed=witness.get('metadata')
    path=Path(job['rename']['destination'])
    proof,observed=current(writer,job,path,job['request']['sha256'])
    modules()[5].preserved_pair(job['pair'],job['request']['sha256'])
    expected=dict(version=1,token=None,source=str(path),before=job['request']['sha256'],
                  after=job['request']['sha256'],owner=job['owner'],payload=job['payload'],
                  census=job['census'],state='unchanged')
    if witness!=dict(version=1,kind='combined-unchanged-v1',binding=job['binding'],
            rename=job['rename'],reader_move=job['reader_move'],metadata=expected,
            signature=proof['inventory']['source_signature'],observed=observed) or closed!=expected:
        raise native.Review('combined-unchanged-terminal-changed')
    if (guard.private_evidence(path_witness)!=witness_evidence
            or not guard.same_json(guard.private_json(path_witness),witness)):
        raise native.Review('combined-unchanged-witness-incarnation-changed')
    return expected,guard.canonical_digest(witness)


def verified_complete(writer, job):
    folder=root(writer)/job['token']
    _, _, guard, native, naming, _, _, rename_module = modules()
    receipt_evidence=guard.private_evidence(folder/'receipt.json')
    prior_path=None
    if job['rename']['token'] is None:
        expected=dict(token=None,digest=job['binding'],destination=job['request']['source'],sha256=job['request']['sha256'])
        if Path(job['request']['source']).name!=job['request']['target'] or job['rename']!=expected:
            raise native.Review('combined-unchanged-name-binding-changed')
    else:
        prior = naming.services()[1].get('release_name', naming.key(job['request']))
        prior_path=writer.root/'release-completed-v1'/(prior['key']+'.json')
        prior_evidence=guard.private_evidence(prior_path)
        witness = guard.private_json(prior_path)
        if (prior.get('phase') != 'committed' or not guard.same_json(prior['request'], job['request'])
                or rename_module.terminal_digest(witness) != prior.get('terminal_proof')
                or not guard.same_json(witness.get('job'), prior)
                or job['rename'] != dict(token=prior['key'], digest=prior['terminal_proof'],
                    destination=str(Path(job['request']['source']).with_name(job['request']['target'])),
                    sha256=job['request']['sha256'])):
            raise native.Review('combined-prior-rename-witness-changed')
    reader_move(job['reader_move'], job)
    receipt_check(writer,folder,job,receipt_evidence)
    closed = job['metadata']
    current(writer, job, Path(job['rename']['destination']), closed['after'])
    if closed.get('token') is None:
        saved,digest=unchanged_closed(writer,job)
        if not guard.same_json(saved,closed) or digest!=job.get('unchanged_terminal'):
            raise native.Review('combined-unchanged-terminal-changed')
    elif not guard.same_json(metadata_closed(writer, job), closed):
        raise native.Review('combined-metadata-terminal-changed')
    if prior_path is not None and (guard.private_evidence(prior_path)!=prior_evidence
            or not guard.same_json(guard.private_json(prior_path),witness)
            or not guard.same_json(naming.services()[1].get('release_name',prior['key']),prior)):
        raise native.Review('combined-historical-rename-incarnation-changed')
    envelope_check(folder,job,receipt_evidence)


@held
def status(token):
    _, writers, guard, _, _, transaction, _, _ = modules()
    with writers.operation() as writer:
        if __package__:
            from . import combined_cleanup
        else:
            import combined_cleanup
        retired=combined_cleanup.resolve(writer,token)
        if retired is not None:return retired
        _, job = read(writer, token)
        phase = job['phase']
    if phase == 'rename-uncertain':
        return rename(token)
    if phase == 'metadata-uncertain':
        return metadata(token, None)
    with writers.operation() as writer:
        folder, job = read(writer, token)
        evidence=guard.private_evidence(folder/'receipt.json')
        if job['phase'] == 'complete':
            verified_complete(writer, job)
        elif job['phase'] == 'renamed':
            rename_closed(writer, job)
        else:
            current(writer, job, Path(job['request']['source']), job['request']['sha256'])
        transaction.preserved_pair(job['pair'],job['request']['sha256'])
        envelope_check(folder,job,evidence)
        return acknowledgement(writer, job)


def execute(raw):
    if not isinstance(raw, str) or len(raw.encode()) > 131072:
        raise ValueError('Bounded combined request required')
    # Reject nesting before invoking the recursive JSON decoder. Quotes and
    # escaped quotes do not contribute structural depth.
    depth = 0
    quoted = escaped = False
    for character in raw:
        if quoted:
            if escaped:
                escaped = False
            elif character == '\\':
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character in '{[':
            depth += 1
            if depth > 32:
                raise ValueError('Combined protocol nesting exceeds bounds')
        elif character in '}]':
            depth -= 1
            if depth < 0:
                raise ValueError('Malformed combined protocol')
    if __package__:
        from . import publication_guard as guard
    else:
        import publication_guard as guard
    def integer(value):
        if len(value.lstrip('-')) > 20:
            raise ValueError('Combined integer exceeds bounds')
        return int(value)
    try:
        value = json.loads(raw, object_pairs_hook=guard.object_pairs,
                           parse_int=integer, parse_float=lambda _: (_ for _ in ()).throw(
                               ValueError('Combined protocol requires finite integer facts')),
                           parse_constant=lambda _: (_ for _ in ()).throw(
                               ValueError('Non-finite combined protocol')))
    except (guard.Unavailable, RecursionError, OverflowError):
        raise ValueError('Bounded unique combined protocol required') from None
    if (not isinstance(value, dict) or type(value.get('version')) is not int or value['version'] != 1
            or value.get('action') not in ('prepare', 'preview', 'rename', 'metadata', 'status', 'cleanup')
            or set(value) != {'version', 'action', 'arguments'} or not isinstance(value['arguments'], dict)):
        raise ValueError('Exact combined protocol required')
    action, args = value['action'], value['arguments']
    if action == 'preview':
        return preview(args)
    if action == 'prepare':
        return prepare(args)
    if action == 'cleanup':
        if __package__:
            from . import combined_cleanup
        else:
            import combined_cleanup
        combined_cleanup.clean(args)
        return status(args['combined_token'])
    if set(args) != ({'token', 'reader_move'} if action == 'metadata' else {'token'}):
        raise ValueError('Exact combined action arguments required')
    if action == 'rename':
        return rename(args['token'])
    if action == 'metadata':
        return metadata(args['token'], args['reader_move'])
    return status(args['token'])
