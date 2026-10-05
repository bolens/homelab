"""Exact in-process tagging capability; interrupted intents never grant replay."""
from contextlib import contextmanager
import json
import hashlib
import os
from pathlib import Path
import re
import stat
import threading
import uuid

if __package__:
    from . import publication_guard as guard, publication_native as native
    from .media_writer import sync, checked_file
else:
    import publication_guard as guard
    import publication_native as native
    from media_writer import sync, checked_file

NAME='tagger-publication-v1.json'
_LOCAL=threading.local()
IN_PLACE_FIELDS=('token','source','before','after','source_identity','candidate_identity',
                 'permissions','attributes','workspace','publication')


def present(writer):
    return os.path.lexists(writer.root/NAME)


def admission(capability,writer):
    """A boolean, deserialized intent or unrelated scope grants no permission."""
    if not isinstance(capability,Tagging) or getattr(_LOCAL,'tagging',None) is not capability:
        raise guard.Unavailable('Exact active tagging transaction required')
    capability.check(writer)


def current():
    job=getattr(_LOCAL,'tagging',None)
    if not isinstance(job,Tagging):raise native.Review('tagging-producer-unbound')
    try:admission(job,job.writer)
    except (guard.Unavailable,OSError,ValueError,TypeError):
        raise native.Review('tagging-transaction-changed') from None
    return job


def _write(path,value,*,exclusive):
    raw=json.dumps(value,sort_keys=True,allow_nan=False,separators=(',',':')).encode()
    if len(raw)>guard.MARKER_BYTES:raise guard.Unavailable('Tagging intent exceeds bounds')
    target=path if exclusive else path.with_name('.'+path.name+'.'+uuid.uuid4().hex)
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        if not exclusive:os.replace(target,path)
        sync(path.parent)
    except BaseException:
        # A durable partial intent/copy is retained; never recover implicitly.
        raise


def state_evidence(writer):
    """Observe already prepared recovery state; never create or repair it."""
    root=writer.root.parent/'modern-tagger-v2'
    paths=(root,root/'journal-v2',root/'staging',root/'staging-receipts')
    rows=[]
    for path in paths:
        if any(p.is_symlink() for p in (path,*path.parents)):
            raise guard.Unavailable('Linked tagging recovery state')
        info=path.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.geteuid()
                or stat.S_IMODE(info.st_mode)!=0o700):
            raise guard.Unavailable('Expected private tagging recovery state')
        # Children are created during a job. Directory timestamps and link
        # counts therefore cannot identify the recovery directory itself.
        rows.append([str(path),info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid])
    binding=writer.root/'tagger-state-v2.identity'
    expected=(hashlib.sha256(json.dumps([(r[1],r[2]) for r in rows]).encode()).hexdigest()+'\n').encode()
    with guard.regular(binding) as stream:
        info=os.fstat(stream.fileno())
        if (info.st_nlink!=1 or info.st_uid!=os.geteuid()
                or stat.S_IMODE(info.st_mode)!=0o600 or stream.read(66)!=expected
                or guard.signature(binding.lstat())!=guard.signature(info)):
            raise guard.Unavailable('Tagging state binding changed')
    return dict(directories=rows,binding=guard.private_evidence(binding))


def history_identity(path):
    if any(p.is_symlink() for p in (path,*path.parents)):
        raise guard.Unavailable('Linked tagging terminal history')
    info=path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.geteuid()
            or stat.S_IMODE(info.st_mode)!=0o700):
        raise guard.Unavailable('Expected private tagging terminal history')
    return [str(path),info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid]


def terminal_digest(result):
    """Bind terminal facts without a receipt hashing itself recursively."""
    value={key:item for key,item in result.items() if key!='receipt_evidence'}
    value['record']={key:item for key,item in result['record'].items() if key!='terminal_proof'}
    return guard.canonical_digest(value)


class Tagging:
    """Created only before the fence under uninterrupted admitted raw Writer."""
    def __init__(self,writer,source,issueid,token,policy,*,modern=False):
        import mylar
        if (not isinstance(token,str) or not re.fullmatch('[0-9a-f]{32}',token)
                or not isinstance(policy,dict) or type(modern) is not bool
                or getattr(_LOCAL,'tagging',None) is not None):
            raise guard.Unavailable('Invalid tagging transaction')
        if present(writer):raise guard.Unavailable('Explicit tagging intent recovery required')
        proof=native.require(source,issueid=issueid)
        if proof is None:raise guard.Unavailable('Publication mode is required')
        census,_=guard.registry_snapshot(Path(mylar.DATA_DIR)/'workflow.sqlite',writer.root/'publication-v1.json')
        # Capture a canonical policy copy, never a caller-mutated dictionary.
        policy=json.loads(json.dumps(policy,sort_keys=True,allow_nan=False))
        recovery=state_evidence(writer) if modern else None
        self.history=writer.root/'tagger-completed-v1'
        self.history.mkdir(mode=0o700,exist_ok=True)
        history=history_identity(self.history);sync(writer.root)
        self.writer=writer;self.path=writer.root/NAME
        self.value=dict(version=1,kind='tagging',phase='prepared',token=token,
            writer=guard.writer_identity(writer),source=proof['path'],owner=proof['owner'],
            payload=proof['inventory']['payload'],source_sha256=proof['inventory']['source_sha256'],
            source_signature=list(proof['inventory']['source_signature']),census=census,
            policy=policy,observed=proof['observed'],recovery=recovery,history=history,fence=None,
            in_place=None)
        _write(self.path,self.value,exclusive=True)
        self.evidence=guard.private_evidence(self.path)
        writer.mark_tagger_pending()
        if (guard.private_evidence(self.path)!=self.evidence
                or not guard.same_json(guard.private_json(self.path),self.value)):
            raise guard.Unavailable('Prepared tagging intent changed before fencing')
        self.value['fence']=list(guard.signature(writer.tagger_pending.lstat()))
        self.value['phase']='fenced'
        _write(self.path,self.value,exclusive=False)
        self.evidence=guard.private_evidence(self.path)
        # Keep the marker inode alive for the whole owned job. A replacement
        # cannot borrow a recycled inode during a later exact completion check.
        pending_fd=checked_file(writer.tagger_pending)
        if list(guard.signature(os.fstat(pending_fd)))!=self.value['fence']:
            os.close(pending_fd)
            raise guard.Unavailable('Tagging fence changed before descriptor binding')
        self.pending_fd=pending_fd
        self.removed_fence_signature=None
        self.terminal_witness=None

    def check(self,writer):
        import mylar
        if type(self.pending_fd) is not int:
            raise guard.Unavailable('Tagging capability has been closed')
        if (not writer.local[1].depth or guard.writer_identity(writer)!=self.value['writer']
                or writer.root!=self.writer.root or self.value['phase'] not in ('fenced','completing')
                or writer.fenced() or writer.fenced(release=True)
                or (self.removed_fence_signature is None and (
                    not writer.fenced(tagger=True)
                    or list(guard.signature(writer.tagger_pending.lstat()))!=self.value['fence']
                    or list(guard.signature(os.fstat(self.pending_fd)))!=self.value['fence']))
                or (self.removed_fence_signature is not None and (
                    self.value['phase']!='completing' or os.path.lexists(writer.tagger_pending)
                    or guard.signature(os.fstat(self.pending_fd))!=self.removed_fence_signature))
                or guard.private_evidence(self.path)!=self.evidence
                or history_identity(self.history)!=self.value['history']
                or not guard.same_json(guard.private_json(self.path),self.value)):
            raise guard.Unavailable('Tagging transaction or fence changed')
        census,_=guard.registry_snapshot(Path(mylar.DATA_DIR)/'workflow.sqlite',writer.root/'publication-v1.json')
        if not guard.same_json(census,self.value['census']):
            raise guard.Unavailable('Tagging correction authority changed')
        if self.value['recovery'] is not None and not guard.same_json(
                state_evidence(writer),self.value['recovery']):
            raise guard.Unavailable('Tagging recovery state changed')

    def closed_history(self,publisher,record):
        """Validate completed history for reading; confer no replay permission."""
        self.check(self.writer)
        token=record.get('token')
        if (not isinstance(token,str) or not re.fullmatch('[0-9a-f]{32}',token)
                or token==self.value['token'] or record.get('cleaned') is not True
                or record.get('state') not in ('committed','unchanged')):
            raise native.Review('tagging-replay-unbound')
        witness=guard.private_json(self.history/(token+'.json'))
        closed=witness.get('job') if isinstance(witness,dict) else None
        recovery=self.value['recovery']
        if (not isinstance(closed,dict) or witness.get('kind')!='tagging-terminal-proof'
                or set(witness)!={'version','kind','job'}
                or not guard.same_json(witness.get('version'),1)
                or set(closed)!={'version','kind','phase','token','writer','source','owner','payload',
                    'source_sha256','source_signature','census','policy','observed','recovery',
                    'history','fence','publisher','completion','in_place'}
                or closed.get('phase')!='completing' or closed.get('token')!=token
                or not guard.same_json(closed.get('writer'),self.value['writer'])
                or not guard.same_json(closed.get('history'),self.value['history'])
                or not guard.same_json(closed.get('recovery'),recovery)
                or recovery is None or str(publisher.root)!=recovery['directories'][1][0]):
            raise native.Review('tagging-closed-history-changed')
        census=guard.census_value(closed['census']);current=self.value['census']
        predecessor={key:value for key,value in closed.items() if key not in ('publisher','completion')}
        predecessor['phase']='fenced'
        predecessor['in_place']=None
        binding=closed['publisher']
        if (not isinstance(binding,dict) or census['epoch']!=current['epoch']
                or census['revision']>current['revision'] or not set(census['keys']).issubset(current['keys'])
                or guard.canonical_digest(predecessor)!=binding.get('intent_sha256')
                or not guard.same_json(binding.get('owner'),closed['owner'])
                or not guard.same_json(binding.get('payload'),closed['payload'])
                or not guard.same_json(binding.get('census'),census)
                or not guard.same_json(binding.get('in_place'),closed['in_place'])):
            raise native.Review('tagging-closed-history-changed')
        terminal=closed.get('completion')
        if (not isinstance(terminal,dict)
                or set(terminal)!={'target','sha256','signature','receipt','receipt_evidence','record','stage'}
                or terminal.get('receipt')!=str(publisher.receipt(token))
                or terminal.get('target')!=record['source']
                or terminal.get('sha256')!=record['after' if record['state']=='committed' else 'before']
                or not guard.same_json(terminal.get('record'),record)
                or guard.private_evidence(publisher.receipt(token))!=terminal.get('receipt_evidence')
                or not guard.same_json(record.get('correction_guard'),closed.get('publisher'))
                or not guard.same_json(record.get('terminal_proof'),dict(version=1,digest=terminal_digest(terminal)))):
            raise native.Review('tagging-closed-history-changed')
        self.check(self.writer)

    def publisher_source(self,publisher,source):
        if self.value['phase']!='fenced':raise native.Review('tagging-terminal-job')
        admission(self,self.writer)
        if __package__:
            from .tagger_pack import Publisher
        else:
            from tagger_pack import Publisher
        if type(publisher) is not Publisher:raise native.Review('tagging-producer-state-changed')
        recovery=self.value['recovery']
        if (recovery is None or str(publisher.root)!=recovery['directories'][1][0]
                or Path(publisher.config_root).absolute()!=self.writer.root.parent
                or type(self.value['policy'].get('manualmeta')) is not bool):
            raise native.Review('tagging-producer-state-changed')
        original=Path(self.value['source']);token=self.value['token']
        self.proof(original,original=True)
        expected=original if self.value['policy']['manualmeta'] else (
            Path(recovery['directories'][2][0])/('mylar_modern_'+token)/original.name)
        if Path(source).absolute()!=expected:
            raise native.Review('tagging-publication-path-changed')
        if not self.value['policy']['manualmeta']:
            if __package__:
                from .tagger_staging import Staging
            else:
                from tagger_staging import Staging
            stage=Staging(recovery['directories'][2][0],recovery['directories'][3][0])
            row=stage.read(stage.receipts/(token+'.json'))
            if (row['token']!=token or row['source']!=str(original)
                    or row['before']!=self.value['source_sha256']
                    or row['source_identity']!=self.value['source_signature'][:5]
                    or row['filename']!=original.name or row['state'] not in ('copying','ready')
                    or row['folder_identity']!=list(guard.signature(expected.parent.lstat())[:2])):
                raise native.Review('tagging-staging-changed')
        return expected

    def bind_publisher(self,publisher,source):
        expected=self.publisher_source(publisher,source)
        if 'publisher' in self.value:raise native.Review('tagging-replay-unbound')
        proof=self.proof(expected)
        if proof['inventory']['source_sha256']!=self.value['source_sha256']:
            raise native.Review('tagging-staged-source-changed')
        binding=dict(version=1,token=self.value['token'],source=str(expected),
            before=self.value['source_sha256'],source_signature=proof['inventory']['source_signature'],
            owner=self.value['owner'],payload=self.value['payload'],census=self.value['census'],
            intent_sha256=guard.canonical_digest(self.value))
        self.check(self.writer)
        self.value['publisher']=binding
        _write(self.path,self.value,exclusive=False)
        self.evidence=guard.private_evidence(self.path)
        return json.loads(json.dumps(binding))

    def publisher_check(self,publisher,record):
        bound=self.value.get('publisher')
        if (not isinstance(bound,dict) or not guard.same_json(record.get('correction_guard'),bound)
                or record.get('token')!=self.value['token'] or record.get('source')!=bound['source']
                or record.get('before')!=bound['before']
                or record.get('source_identity')!=bound['source_signature'][:5]):
            raise native.Review('tagging-receipt-unbound')
        source=self.publisher_source(publisher,record['source'])
        if source.exists() or source.is_symlink():
            self.proof(source)
        elif (record.get('state')=='publishing' and
                (not self.value['policy']['manualmeta'] or self.value['in_place'] is not None)):
            # Only an uncatalogued owned staging name may be temporarily absent.
            # The original acquisition and all registered owner facts stay intact.
            displaced=publisher.workspace(record)/'displaced.cbz'
            if not publisher.matches(displaced,record,links=(1,2)):
                raise native.Review('tagging-displaced-source-changed')
            self.proof(displaced)
        else:raise native.Review('tagging-source-missing')

    def bind_in_place(self,publisher,record,output):
        """Bind only a retained copy; never displace a registered owner archive."""
        self.publisher_check(publisher,record)
        if (not self.value['policy']['manualmeta'] or self.value['in_place'] is not None
                or record.get('state')!='publishing'
                or any(item['catalog']['path']==self.value['source'] for item in self.value['observed'])):
            raise native.Review('tagging-in-place-transition-unbound')
        self.proof(output)
        if not publisher.matches(output,record,True):
            raise native.Review('tagging-in-place-output-changed')
        transition={key:record[key] for key in IN_PLACE_FIELDS}
        self.check(self.writer)
        self.value['publisher']['in_place']=json.loads(json.dumps(transition))
        _write(self.path,self.value,exclusive=False)
        self.evidence=guard.private_evidence(self.path)
        record['correction_guard']=json.loads(json.dumps(self.value['publisher']))
        # Intent precedes receipt. An interrupted binding remains held; it
        # cannot admit another job or implicitly upgrade this receipt.
        publisher.write(record)
        self.in_place_publisher=publisher
        self.value['in_place']=json.loads(json.dumps(transition))
        _write(self.path,self.value,exclusive=False)
        self.evidence=guard.private_evidence(self.path)

    def in_place_source(self,path):
        """Observe the exact before/displaced/after file without replay."""
        if __package__:
            from .tagger_pack import Publisher
        else:
            from tagger_pack import Publisher
        source=Path(self.value['source'])
        if Path(path).absolute()!=source:raise native.Review('tagging-source-changed')
        self.check(self.writer)
        publisher=getattr(self,'in_place_publisher',None)
        if (type(publisher) is not Publisher
                or str(publisher.root)!=self.value['recovery']['directories'][1][0]
                or Path(publisher.config_root).absolute()!=self.writer.root.parent):
            raise native.Review('tagging-in-place-producer-changed')
        record=guard.private_json(publisher.receipt(self.value['token']))
        transition={key:record[key] for key in IN_PLACE_FIELDS}
        if (not guard.same_json(transition,self.value['in_place'])
                or not guard.same_json(record.get('correction_guard'),self.value['publisher'])
                or record.get('state') not in ('publishing','committed')
                or not guard.same_json(self.value['publisher'].get('in_place'),transition)):
            raise native.Review('tagging-in-place-receipt-changed')
        if source.exists() or source.is_symlink():
            if publisher.matches(source,record,links=(1,2)):
                return source,record['before']
            if publisher.matches(source,record,True,links=(1,2)):
                return source,record['after']
        elif record['state']=='publishing':
            displaced=publisher.workspace(record)/'displaced.cbz'
            if publisher.matches(displaced,record,links=(1,2)):
                return displaced,record['before']
        raise native.Review('tagging-in-place-source-changed')

    def publisher_cleanup(self,publisher,record):
        self.publisher_check(publisher,record)
        folder=publisher.workspace(record)
        before=native.scope_snapshot(folder)
        allowed={'original.cbz','tagged.cbz','verified.cbz','displaced.cbz'}
        for value in before:
            path=Path(value)
            if path==folder:continue
            if path.parent!=folder or path.name not in allowed or not stat.S_ISREG(path.lstat().st_mode):
                raise native.Review('tagging-cleanup-scope-changed')
            proof=self.proof(path)
            if (path.name in ('original.cbz','displaced.cbz')
                    and proof['inventory']['source_sha256']!=self.value['source_sha256']):
                raise native.Review('tagging-preserved-source-changed')
        if native.scope_snapshot(folder)!=before:
            raise native.Review('tagging-cleanup-scope-changed')

    def completion_snapshot(self,publisher,staging,target):
        target=Path(target).absolute()
        self.publisher_source(publisher,target)
        token=self.value['token'];record=publisher.read(token)
        if (record['state'] not in ('committed','unchanged') or not record['cleaned']
                or record['source']!=str(target)
                or not publisher.matches(target,record,record['state']=='committed')):
            raise native.Review('tagging-terminal-receipt-required')
        proof=self.proof(target)
        digest=record['after'] if record['state']=='committed' else record['before']
        if proof['inventory']['source_sha256']!=digest:
            raise native.Review('tagging-terminal-source-changed')
        receipt=publisher.receipt(token)
        result=dict(target=str(target),sha256=digest,signature=proof['inventory']['source_signature'],
            receipt=str(receipt),receipt_evidence=guard.private_evidence(receipt),record=record,
            stage=None)
        if not self.value['policy']['manualmeta']:
            if __package__:
                from .tagger_staging import Staging
            else:
                from tagger_staging import Staging
            recovery=self.value['recovery']
            if (type(staging) is not Staging or str(staging.root)!=recovery['directories'][2][0]
                    or str(staging.receipts)!=recovery['directories'][3][0]):
                raise native.Review('tagging-producer-state-changed')
            path=staging.receipts/(token+'.json');row=staging.read(path)
            if row['state']!='ready' or row.get('after')!=digest:
                raise native.Review('tagging-terminal-staging-required')
            result['stage']=dict(path=str(path),evidence=guard.private_evidence(path),record=row)
        return result

    def verify_completion(self):
        result=self.value['completion']
        self.check(self.writer)
        self.proof(self.value['source'],original=True)
        proof=self.proof(result['target'])
        if (proof['inventory']['source_sha256']!=result['sha256']
                or proof['inventory']['source_signature']!=result['signature']
                or guard.private_evidence(Path(result['receipt']))!=result['receipt_evidence']
                or not guard.same_json(guard.private_json(Path(result['receipt'])),result['record'])):
            raise native.Review('tagging-terminal-evidence-changed')
        stage=result['stage']
        if stage is not None and (
                guard.private_evidence(Path(stage['path']))!=stage['evidence']
                or not guard.same_json(guard.private_json(Path(stage['path'])),stage['record'])):
            raise native.Review('tagging-terminal-staging-changed')
        if self.terminal_witness is not None:
            witness=self.terminal_witness;path=Path(witness['path'])
            if (guard.private_evidence(path)!=witness['evidence']
                    or not guard.same_json(guard.private_json(path),witness['value'])):
                raise native.Review('tagging-terminal-witness-changed')

    def complete(self,publisher,staging,target):
        try:self._complete(publisher,staging,target)
        except (guard.Unavailable,OSError,ValueError,TypeError,KeyError):
            raise native.Review('tagging-completion-unavailable') from None

    def _complete(self,publisher,staging,target):
        """Remove only this captured marker after durable exact terminal proof.

        A crash between marker and intent removal remains held by the intent;
        another process cannot borrow this in-memory completion capability.
        """
        if self.value['phase']!='fenced':raise native.Review('tagging-terminal-job')
        result=self.completion_snapshot(publisher,staging,target)
        record=result['record']
        if 'terminal_proof' in record:raise native.Review('tagging-terminal-proof-already-present')
        record['terminal_proof']=dict(version=1,digest=terminal_digest(result))
        publisher.write(record)
        result=self.completion_snapshot(publisher,staging,target)
        if not guard.same_json(result['record'].get('terminal_proof'),
                               dict(version=1,digest=terminal_digest(result))):
            raise native.Review('tagging-terminal-proof-changed')
        self.check(self.writer)
        self.value.update(phase='completing',completion=result)
        _write(self.path,self.value,exclusive=False)
        self.evidence=guard.private_evidence(self.path)
        self.verify_completion()
        # Preserve independently bound terminal evidence before releasing the
        # intent. Later jobs may read this exact closed receipt without replay;
        # unbound or modified history still requires explicit review.
        witness_path=self.history/(self.value['token']+'.json')
        witness_value=json.loads(json.dumps(dict(version=1,kind='tagging-terminal-proof',job=self.value)))
        _write(witness_path,witness_value,exclusive=True)
        self.terminal_witness=dict(path=str(witness_path),value=witness_value,
                                  evidence=guard.private_evidence(witness_path))
        self.verify_completion()
        # The still-open descriptor pins the exact original pending inode.
        if (guard.signature(os.fstat(self.pending_fd))!=self.value['fence']
                or guard.signature(self.writer.tagger_pending.lstat())!=self.value['fence']):
            raise native.Review('tagging-completion-fence-changed')
        self.writer.tagger_pending.unlink()
        removed=guard.signature(os.fstat(self.pending_fd))
        if (removed[:4]!=self.value['fence'][:4] or removed[5:8]!=self.value['fence'][5:8]
                or removed[8]!=0):raise native.Review('tagging-completion-fence-changed')
        self.removed_fence_signature=removed
        sync(self.writer.root)
        self.verify_completion()
        # Pin the final owned intent inode too, rather than unlinking a path
        # which could have been replaced while terminal evidence was observed.
        with guard.regular(self.path) as stream:
            info=os.fstat(stream.fileno())
            if (guard.private_evidence(self.path)!=self.evidence
                    or guard.signature(self.path.lstat())!=guard.signature(info)
                    or not guard.same_json(guard.decode_json(stream.read(guard.MARKER_BYTES+1)),self.value)):
                raise native.Review('tagging-completion-intent-changed')
            self.path.unlink()
            try:sync(self.writer.root)
            except OSError:
                # A failed durability acknowledgement must not open ordinary
                # admission. Restore the typed hold only if no foreign intent
                # occupies the name; never replace another writer's evidence.
                if not os.path.lexists(self.path):_write(self.path,self.value,exclusive=True)
                raise
        self.value['phase']='released'

    @contextmanager
    def coordinate(self):
        """No ordinary operation bypass: only this exact job reuses its owner."""
        def check():
            try:admission(self,self.writer)
            except (guard.Unavailable,OSError,ValueError,TypeError):
                raise native.Review('tagging-transaction-changed') from None
        check()
        try:yield self.writer
        finally:check()

    def proof(self,path,*,original=False):
        owner=self.value['owner']
        transitioned=original and self.value['in_place'] is not None
        if transitioned:path,digest=self.in_place_source(path)
        result=native.require(path,issueid=None if owner is None else owner['issueid'],
                              transaction=self)
        if (result['inventory']['payload']!=self.value['payload']
                or not guard.same_json(result['owner'],owner)
                or not guard.same_json(result['observed'],self.value['observed'])
                or (transitioned and result['inventory']['source_sha256']!=digest)
                or (original and not transitioned and (result['path']!=self.value['source']
                    or result['inventory']['source_sha256']!=self.value['source_sha256']
                    or list(result['inventory']['source_signature'])!=self.value['source_signature']))):
            raise native.Review('tagging-source-changed',payload=result['inventory']['payload'])
        return result


@contextmanager
def tagging(writer,source,issueid,token,policy,*,modern=False):
    job=Tagging(writer,source,issueid,token,policy,modern=modern)
    _LOCAL.tagging=job
    try:
        admission(job,writer)
        yield job
    finally:
        _LOCAL.tagging=None
        os.close(job.pending_fd)
        job.pending_fd=None
        # Completion/clearance is deliberately a separate verified producer
        # action. Every incomplete scope retains both typed intent and fence.
