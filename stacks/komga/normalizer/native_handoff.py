"""Typed durable maintenance requests; no HTTP while the worker owns Writer."""
import hashlib
import json
from pathlib import Path
import re
import time

from import_recovery import handoff_read, handoff_save
from normalize import digest, identity
from publication_guard import current, evidence, scope, Unavailable, remote_unlocked

COMMANDS = frozenset(('packCatalog', 'packReport', 'workflowAcknowledge'))


def native_path(maintenance, path):
    path = Path(path)
    cache = Path(maintenance.settings['ddl_cache'])
    if path.is_relative_to(cache):
        return str(Path(maintenance.settings['mylar_ddl_cache']) / path.relative_to(cache))
    for native, worker in current(maintenance.worker).mappings:
        if path.is_relative_to(worker):return str(native / path.relative_to(worker))
    raise Unavailable('Maintenance source has no exact native mapping')


def extracted_root(maintenance, path):
    """Only receipt-owned extracted members may be local-only report witnesses."""
    root=maintenance.state/'packs'
    path=Path(path)
    if not path.is_absolute() or '..' in path.parts or not path.is_relative_to(root):return None
    parts=path.relative_to(root).parts
    if len(parts)<3 or not re.fullmatch('[a-f0-9]{64}',parts[0]) or parts[1]!='extracted':return None
    return root/parts[0]/'extracted'


def checks(maintenance, guards):
    from maintenance import scoped_file
    authority = current(maintenance.worker)
    if not isinstance(guards,list) or len(guards)>4000:
        raise Unavailable('Maintenance evidence exceeds bounds')
    proofs = []
    for row in guards:
        if not isinstance(row,dict) or set(row)!={'source','match','target'}:
            raise Unavailable('Invalid maintenance evidence')
        source=Path(row['source'])
        if not source.is_absolute() or '..' in source.parts:
            raise Unavailable('Invalid maintenance source path')
        local=extracted_root(maintenance,source)
        roots=maintenance.roots+maintenance.worker.roots+([local] if local is not None and row['target'] is not None else [])
        if not scoped_file(Path(row['source']),roots):
            raise Unavailable('Maintenance evidence is outside owned roots')
        source = Path(row['source'])
        if row['target'] is not None:
            target = Path(row['target'])
            if not target.is_absolute() or '..' in target.parts or not scoped_file(target,maintenance.worker.roots):
                raise Unavailable('Maintenance target is outside library')
            proof = authority.confirmation_check(source,target,row['match'])
        elif row['match'] is not None:proof = authority.import_check(source,row['match'])
        else:proof = authority.unowned_check(source)
        proofs.append(dict(source=str(source),identity=identity(source),sha256=digest(source),proof=proof))
    return dict(census=authority.admission()[0],guards=proofs)


def request(maintenance, command, arguments, guards):
    """Prepare once under exclusion; consume only a fresh exact completed reply."""
    if maintenance.worker.config.get('writer_state') is None:
        return maintenance.mylar(command,**arguments)
    if command not in COMMANDS or not isinstance(arguments,dict):
        raise Unavailable('Unsupported maintenance handoff')
    proof = checks(maintenance,guards)
    plan = dict(version=1,command=command,arguments=arguments,guards=guards,proof=proof)
    token = evidence.canonical_digest(plan)
    root = maintenance.state/'native-handoffs'
    root.mkdir(exist_ok=True,mode=0o700)
    paths=list(root.glob('*.json'))
    path = root/(token+'.json')
    if not path.exists():
        if len(paths) >= 4096:
            raise Unavailable('Maintenance handoff retention requires review')
        for previous in paths:
            old,_ = handoff_read(previous)
            if not isinstance(old,dict):
                raise Unavailable('Malformed maintenance history requires review')
            if (old.get('phase')=='dispatching' and old.get('command')==command
                    and evidence.same_json(old.get('arguments'),arguments)):
                raise Unavailable('Uncertain maintenance request requires review')
        handoff_save(path,dict(plan,phase='prepared',prepared_at=time.time()))
        return None
    record,_ = handoff_read(path)
    if not isinstance(record,dict):
        raise Unavailable('Malformed maintenance history requires review')
    if not evidence.same_json({key:record.get(key) for key in plan},plan):
        raise Unavailable('Maintenance handoff no longer matches')
    if record.get('phase')!='complete':return None
    return record['result']


def guard(source, match=None, target=None):
    return dict(source=str(source),match=match,target=str(target) if target is not None else None)


def report(maintenance, value):
    if maintenance.worker.config.get('writer_state') is None:
        return maintenance.mylar('packReport',report=json.dumps(value))
    guards=[]
    for member in value.get('members',[]):
        if member.get('kind')=='sidecar' or member.get('phase') not in ('confirmed','preserved'):continue
        target=Path(member['destination'])
        match=({key:str(member[key]) for key in ('issueid','comicid')}
               if member.get('phase')=='confirmed' and member.get('issueid') else None)
        source=Path(member.get('prepared') or member.get('source') or target)
        if not source.is_file():source=target
        guards.append(guard(source,match,target if match else None))
        original=Path(member.get('source') or source)
        if match and original!=source and original.is_file():
            guards.append(guard(original,match,target))
        if not match and source!=target:guards.append(guard(target))
    public=json.loads(json.dumps(value))
    for member in public.get('members',[]):
        if member.get('destination'):member['destination']=native_path(maintenance,member['destination']) if maintenance.worker.config.get('writer_state') else member['destination']
    return request(maintenance,'packReport',{'report':json.dumps(public)},guards)


def packet(maintenance, record, token):
    sources=[]
    for index,row in enumerate(record['guards']):
        observed=record['proof']['guards'][index]
        paths=[row['source']]+([row['target']] if row['target'] is not None else [])
        for path in dict.fromkeys(paths):
            source=Path(path)
            if extracted_root(maintenance,source) is not None and row['target'] is not None and path==row['source']:
                continue  # Native validates the shared target; the worker binds its private original.
            confirmation=row['target'] is not None and path==row['target']
            checksum=(observed['proof']['target']['inventory']['source_sha256'] if confirmation else observed['sha256'])
            sources.append(dict(path=native_path(maintenance,source),sha256=checksum,
                match=row['match'],confirmation=confirmation))
    return dict(version=1,token=token,command=record['command'],
                arguments_sha256=evidence.canonical_digest(record['arguments']),
                census=record['proof']['census'],sources=sources)


def dispatch(maintenance):
    from media_writer import Writer, Busy
    from writer_cycle import bind_state
    worker=maintenance.worker
    remote_unlocked(worker)
    root=maintenance.state/'native-handoffs'
    if not root.exists():return 0
    if maintenance.state!=worker.state/'maintenance':raise Unavailable('Foreign maintenance state')
    paths=sorted(root.glob('*.json'))
    if len(paths)>4096:raise Unavailable('Maintenance handoff count exceeds bound')
    writer=Writer(worker.config['writer_state'],create=False)
    for path in paths:
        try:
            old,_=handoff_read(path)
            if not isinstance(old,dict):raise Unavailable('Malformed maintenance history requires review')
            if old.get('phase')!='prepared':continue
            health=maintenance.mylar('getHealth').get('workflow',{})
            if (health.get('valid') is not True or type(health.get('maintenance_handoff')) is not int
                    or health['maintenance_handoff']!=1):return 0
            with writer.hold(timeout=0),scope(worker,writer):
                bind_state(writer,worker)
                record,signature=handoff_read(path)
                plan_fields={'version','command','arguments','guards','proof'}
                if (set(record)!=plan_fields|{'phase','prepared_at'} or record['phase']!='prepared'
                        or record['version']!=1 or type(record['version']) is not int
                        or record['command'] not in COMMANDS
                        or path.name!=evidence.canonical_digest({key:record[key] for key in plan_fields})+'.json'
                        or not evidence.same_json(record['proof'],checks(maintenance,record['guards']))):
                    raise Unavailable('Maintenance handoff source, binding or authority changed')
                binding=packet(maintenance,record,path.stem)
                attempted=dict(record,phase='dispatching',submitted_at=time.time())
                handoff_save(path,attempted,expected=(record,signature))
            try:result=maintenance.mylar(record['command'],maintenance_handoff=json.dumps(binding),**record['arguments'])
            except Exception:return 0
            with writer.hold(timeout=0),scope(worker,writer):
                bind_state(writer,worker)
                old,signature=handoff_read(path)
                if (not evidence.same_json(old,attempted)
                        or not evidence.same_json(record['proof'],checks(maintenance,record['guards']))):
                    raise Unavailable('Maintenance handoff changed before acknowledgement')
                handoff_save(path,dict(attempted,phase='complete',result=result),expected=(old,signature))
            return 1
        except (Busy,Unavailable,OSError,ValueError,TypeError,KeyError):return 0
    return 0
