"""Same-payload naming capability; interrupted jobs never regain replay rights."""
from contextlib import contextmanager
from functools import wraps
import json
import os
from pathlib import Path
import stat
import threading

if __package__:
    from . import publication_guard as guard, publication_native as native
    from .publication_transaction import _write, NAME
    from .media_writer import checked_file, sync
else:
    import publication_guard as guard
    import publication_native as native
    from publication_transaction import _write, NAME
    from media_writer import checked_file, sync

_LOCAL = threading.local()


def terminal_digest(witness):
    value=json.loads(json.dumps(witness))
    value['job'].pop('terminal_proof',None)
    return guard.canonical_digest(value)


def current():
    value = getattr(_LOCAL, 'rename', None)
    if value is not None and type(value) is not Rename:
        raise guard.Unavailable('Exact owned rename capability required')
    return value


def admitted(value, writer):
    if type(value) is not Rename or current() is not value:
        raise guard.Unavailable('Exact active rename capability required')
    value.check(writer)


def history(writer):
    root = writer.root/'release-completed-v1'
    if not root.exists():
        root.mkdir(mode=0o700);sync(writer.root)
    info = root.lstat()
    if (root.is_symlink() or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise guard.Unavailable('Private rename terminal history required')
    return root, guard.signature(info)[:2]


def held(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:return function(*args, **kwargs)
        except (guard.Unavailable,OSError,ValueError,TypeError,KeyError):
            if function.__name__ == '__init__' and type(getattr(args[0],'fd',None)) is int:
                os.close(args[0].fd);args[0].fd=None
            raise native.Review('rename-evidence-unavailable') from None
    return wrapped


class Rename:
    @held
    def __init__(self, writer, job):
        import mylar
        from mylar import native_writers
        if current() is not None or not native_writers.active():
            raise guard.Unavailable('Fresh outer native rename admission required')
        native_writers.admission(writer)
        self.writer = writer;self.path = writer.root/NAME;self.fd = None;self.terminal_proof=None
        self.request = json.loads(json.dumps(job['request']))
        self.source = Path(self.request['source']);self.target = self.source.with_name(self.request['target'])
        proof = native.require(self.source, issueid=self.request['issueid'], comicid=self.request['comicid'])
        if proof is None or proof['owner'] is None or proof['inventory']['source_sha256'] != self.request['sha256']:
            raise guard.Unavailable('Exact rename source and owner required')
        observed = guard.observe_owners(Path(mylar.DATA_DIR)/'mylar.db', writer, [proof['owner']],
                                       [mylar.CONFIG.DESTINATION_DIR])
        if (observed['observed'][0]['catalog']['path'] != str(self.source)
                or observed['inventory']['payload'] != proof['inventory']['payload']
                or observed['observed'][0]['source_sha256'] != self.request['sha256']
                or observed['observed'][0]['signature'] != proof['inventory']['source_signature']):
            raise guard.Unavailable('Rename source is not the unique current catalog archive')
        self.history, history_id = history(writer)
        self.value = dict(version=1, kind='rename', phase='prepared', token=job['key'],
            writer=guard.writer_identity(writer), request=self.request, stamp=job['stamp'],
            attributes=job['attributes'], job={key:value for key,value in job.items()
                if key not in ('phase','publication_binding','terminal_proof')}, owner=proof['owner'], payload=proof['inventory']['payload'],
            observed=observed['observed'], census=native_writers.admission(writer),
            history=history_id, journal=guard.signature(Path(mylar.DATA_DIR,'workflow.sqlite').lstat())[:2],
            fence=None)
        self.value=json.loads(json.dumps(self.value))
        self.binding = guard.canonical_digest({key:value for key,value in self.value.items()
                                               if key not in ('phase','fence')})
        self.value['binding'] = self.binding
        _write(self.path, self.value, exclusive=True)
        self.evidence = guard.private_evidence(self.path)
        writer.mark_release_pending()
        self.fd = checked_file(writer.release_pending)
        self.value.update(phase='fenced', fence=guard.signature(os.fstat(self.fd)))
        _write(self.path, self.value, exclusive=False)
        self.evidence = guard.private_evidence(self.path)

    def check(self, writer):
        import mylar
        if (not guard.same_json(self.request,self.value['request'])
                or str(self.source)!=self.value['request']['source']
                or str(self.target)!=str(Path(self.value['request']['source']).with_name(self.value['request']['target']))
                or type(self.fd) is not int or not writer.local[1].depth or writer.root != self.writer.root
                or guard.writer_identity(writer) != self.value['writer']
                or self.value['phase'] not in ('fenced','terminal')
                or not writer.fenced(release=True) or writer.fenced() or writer.fenced(tagger=True)
                or guard.signature(writer.release_pending.lstat()) != self.value['fence']
                or guard.signature(os.fstat(self.fd)) != self.value['fence']
                or os.path.lexists(writer.root/'tagger-recovery-v1.pending')
                or guard.private_evidence(self.path) != self.evidence
                or not guard.same_json(guard.private_json(self.path), self.value)
                or guard.signature(self.history.lstat())[:2] != self.value['history']
                or guard.signature(Path(mylar.DATA_DIR,'workflow.sqlite').lstat())[:2] != self.value['journal']):
            raise guard.Unavailable('Rename capability, fence or journal changed')
        census,_ = guard.registry_snapshot(Path(mylar.DATA_DIR)/'workflow.sqlite', writer.root/'publication-v1.json')
        if not guard.same_json(census,self.value['census']):
            raise guard.Unavailable('Rename census changed')

    def observation_path(self, path):
        path = Path(path)
        if path == self.source and not os.path.lexists(path):
            # Only this exact request's old catalog spelling is projected. The
            # checkpoint verifies unchanged bytes/inode/attributes at target.
            return self.target
        return path

    @held
    def checkpoint(self, job):
        import mylar
        from mylar import release_naming
        admitted(self,self.writer)
        if (not guard.same_json({key:value for key,value in job.items()
                                  if key not in ('phase','publication_binding','terminal_proof')},self.value['job'])
                or str(self.source)!=self.value['request']['source']
                or str(self.target)!=str(Path(self.value['request']['source']).with_name(self.value['request']['target']))
                or job.get('terminal_proof')!=self.terminal_proof
                or job['key'] != self.value['token'] or not guard.same_json(job['request'],self.request)
                or job.get('publication_binding') != self.binding):
            raise native.Review('rename-journal-binding-changed')
        existing = [path for path in (self.source,self.target) if os.path.lexists(path)]
        if not existing:
            raise native.Review('rename-source-missing')
        for path in existing:
            release_naming.verified(path,job)
            proof = native.require(path, issueid=self.request['issueid'], comicid=self.request['comicid'], transaction=self)
            if proof['inventory']['payload'] != self.value['payload']:
                raise native.Review('rename-payload-changed')
        if len(existing) == 2 and existing[0].stat().st_ino != existing[1].stat().st_ino:
            raise native.Review('rename-foreign-destination')
        observed = guard.observe_owners(Path(mylar.DATA_DIR)/'mylar.db',self.writer,[self.value['owner']],
                                       [mylar.CONFIG.DESTINATION_DIR],transaction=self)['observed']
        expected = self.value['observed'][0];actual = observed[0]
        if not guard.same_json(expected['owner'],actual['owner']):
            raise native.Review('rename-owner-changed')
        before = expected['catalog'];after = actual['catalog']
        if (after['path'] not in (str(self.source),str(self.target))
                or not guard.same_json({k:v for k,v in before.items() if k not in ('path','location')},
                                       {k:v for k,v in after.items() if k not in ('path','location')})
                or actual['source_sha256'] != self.request['sha256']):
            raise native.Review('rename-catalog-changed')
        admitted(self,self.writer)
        return observed

    @held
    def complete(self, job):
        self.checkpoint(job)
        if job['phase'] not in ('committed','rejected'):
            raise native.Review('rename-terminal-journal-required')
        path = self.target if job['phase']=='committed' else self.source
        retired = self.source if job['phase']=='committed' else self.target
        if os.path.lexists(retired):raise native.Review('rename-terminal-paths-incomplete')
        witness = dict(version=1,kind='rename-terminal',job=json.loads(json.dumps(job)),
                       intent=self.value, observed=self.checkpoint(job), archive=str(path),
                       signature=guard.signature(path.lstat()))
        self.terminal_proof=terminal_digest(witness)
        job['terminal_proof']=self.terminal_proof
        from mylar import release_naming
        release_naming.services()[1].set('release_name',job['key'],job)
        witness['job']=json.loads(json.dumps(job))
        terminal = self.history/(job['key']+'.json')
        _write(terminal,witness,exclusive=True)
        self.value = dict(self.value,phase='terminal',terminal=guard.canonical_digest(witness))
        _write(self.path,self.value,exclusive=False);self.evidence=guard.private_evidence(self.path)
        self.check(self.writer)
        if not guard.same_json(guard.private_json(terminal),witness):
            raise native.Review('rename-terminal-witness-changed')
        self.checkpoint(job)
        self.writer.clear_release_pending()
        self.path.unlink()
        try:sync(self.writer.root)
        except OSError:
            if not os.path.lexists(self.path):_write(self.path,self.value,exclusive=True)
            raise

    @contextmanager
    def owned(self):
        if current() is not None:raise guard.Unavailable('Nested rename capability refused')
        _LOCAL.rename = self
        try:
            yield self
        finally:
            _LOCAL.rename = None
            if self.fd is not None:os.close(self.fd);self.fd=None


@held
def terminal(writer, job):
    """Fresh acknowledgement of a closed exact witness; no replay or clearing."""
    import mylar
    from mylar import native_writers, release_naming
    native_writers.admission(writer)
    root = writer.root/'release-completed-v1'
    info=root.lstat()
    if (root.is_symlink() or not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.geteuid()
            or stat.S_IMODE(info.st_mode)!=0o700):raise native.Review('rename-terminal-unbound')
    witness = guard.private_json(root/(job['key']+'.json'))
    if (witness.get('kind')!='rename-terminal' or type(witness.get('version')) is not int
            or witness['version']!=1 or not guard.same_json(witness.get('job'),job)
            or witness['intent'].get('kind')!='rename'
            or witness['intent']['binding'] != job.get('publication_binding')
            or not isinstance(job.get('terminal_proof'),str)
            or terminal_digest(witness)!=job['terminal_proof']):
        raise native.Review('rename-terminal-unbound')
    intent=witness['intent']
    if (type(intent.get('version')) is not int or intent['version']!=1
            or intent.get('phase')!='fenced' or intent.get('token')!=job['key']
            or not guard.same_json(intent.get('request'),job['request'])
            or guard.writer_identity(writer)!=intent['writer']
            or guard.signature(root.lstat())[:2]!=intent['history']
            or guard.signature(Path(mylar.DATA_DIR,'workflow.sqlite').lstat())[:2]!=intent['journal']
            or guard.canonical_digest({k:v for k,v in intent.items() if k not in ('phase','fence','binding')})!=intent['binding']):
        raise native.Review('rename-terminal-binding-changed')
    census,_=guard.registry_snapshot(Path(mylar.DATA_DIR)/'workflow.sqlite',writer.root/'publication-v1.json')
    if not guard.same_json(census,witness['intent']['census']):raise native.Review('rename-terminal-census-changed')
    expected=Path(job['request']['source'])
    if job['phase']=='committed':expected=expected.with_name(job['request']['target'])
    elif job['phase']!='rejected':raise native.Review('rename-terminal-phase-changed')
    if witness['archive']!=str(expected):raise native.Review('rename-terminal-path-changed')
    path=Path(witness['archive']);release_naming.verified(path,job)
    proof=native.require(path,issueid=job['request']['issueid'],comicid=job['request']['comicid'])
    observed=guard.observe_owners(Path(mylar.DATA_DIR)/'mylar.db',writer,[proof['owner']],
                                 [mylar.CONFIG.DESTINATION_DIR])['observed']
    if (observed[0]['catalog']['path']!=str(expected)
            or not guard.same_json(observed,witness['observed'])
            or guard.signature(path.lstat())!=witness['signature']
            or proof['inventory']['payload']!=witness['intent']['payload']):
        raise native.Review('rename-terminal-facts-changed')
    return witness
