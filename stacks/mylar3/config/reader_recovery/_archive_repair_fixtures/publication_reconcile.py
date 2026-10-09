"""Exact retained-repeat repair; clearing a false location still requires review."""
from contextlib import closing, contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import threading
import time

if __package__:
    from . import publication_guard as guard, publication_native as native
    from .publication_conversion import file_state, retained, private_directory
    from .publication_transaction import NAME, _write
    from .media_writer import checked_file, sync
else:
    import publication_guard as guard
    import publication_native as native
    from publication_conversion import file_state, retained, private_directory
    from publication_transaction import NAME, _write
    from media_writer import checked_file, sync

_LOCAL=threading.local()
REPAIR='retain-and-clear-exact-false-location'
FIELDS={'version','plan_path','plan_sha256','backup','census','repair'}


def exact(value, fields):
    if not isinstance(value,dict) or set(value)!=set(fields):raise guard.Unavailable('Exact repair evidence required')


def path(value):
    if not isinstance(value,str) or not value or '\\' in value or '\0' in value:
        raise guard.Unavailable('Exact repair path required')
    result=Path(value)
    if (not result.is_absolute() or result==Path('/') or '..' in result.parts
            or any(p.is_symlink() for p in (result,*result.parents))):
        raise guard.Unavailable('Unsafe repair path')
    return result


def private(value, *, maximum=guard.MAX_BYTES):
    value=path(str(value));info=value.lstat();folder=value.parent.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_nlink!=1
            or stat.S_IMODE(info.st_mode)!=0o600 or not 0<info.st_size<=maximum
            or not stat.S_ISDIR(folder.st_mode) or folder.st_uid!=os.geteuid()
            or stat.S_IMODE(folder.st_mode)!=0o700):raise guard.Unavailable('Private independent repair evidence required')
    return file_state(value)


def read(value, checksum):
    state=private(value,maximum=guard.MAX_OUTPUT)
    if state['sha256']!=checksum:raise guard.Unavailable('Repair review evidence changed')
    with guard.regular(Path(value)) as stream:raw=stream.read(guard.MAX_OUTPUT+1)
    if len(raw)>guard.MAX_OUTPUT or not guard.same_json(private(value,maximum=guard.MAX_OUTPUT),state):
        raise guard.Unavailable('Repair evidence changed while reading')
    return guard.decode_json(raw),state


def database(value):
    value=path(str(value));before=guard.signature(value.lstat())
    if any(os.path.lexists(str(value)+suffix) for suffix in ('-journal','-wal','-shm')):
        raise guard.Unavailable('Repair database has pending state')
    with closing(sqlite3.connect(value.as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        deadline=time.monotonic()+guard.TIMEOUT
        db.set_progress_handler(lambda:int(time.monotonic()>=deadline),1000)
        if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:raise guard.Unavailable('Repair database unreadable')
    if guard.signature(value.lstat())!=before:raise guard.Unavailable('Repair database changed')


def catalog(database_path):
    """Bound every row/column so no unrelated status or wanted field is lost."""
    database(database_path);before=guard.signature(database_path.lstat());deadline=time.monotonic()+guard.TIMEOUT
    tables={};count=size=0
    with closing(sqlite3.connect(database_path.as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        db.set_progress_handler(lambda:int(time.monotonic()>=deadline),1000)
        names=db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        if len(names)>64:raise guard.Unavailable('Repair catalog schema exceeds bound')
        for (name,) in names:
            if not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*',name):raise guard.Unavailable('Unsupported repair catalog table')
            fields=[row[1] for row in db.execute('PRAGMA table_info('+name+')')]
            if not fields or len(fields)>256 or any(not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*',field) for field in fields):
                raise guard.Unavailable('Unsupported repair catalog columns')
            total,amount=db.execute('SELECT count(*),coalesce(sum('+ '+'.join('coalesce(length(CAST('+field+' AS BLOB)),0)' for field in fields)+'),0) FROM '+name).fetchone()
            count+=total;size+=amount
            if count>guard.CATALOG_ROWS or size>guard.CATALOG_BYTES:raise guard.Unavailable('Repair catalog exceeds bound')
            rows=[dict(zip(fields,row)) for row in db.execute('SELECT * FROM '+name)]
            rows.sort(key=guard.canonical_digest);tables[name]=rows
    if guard.signature(database_path.lstat())!=before:raise guard.Unavailable('Repair catalog changed while reading')
    return tables


def backup(review, required, roots, *, original=True):
    exact(review,('manifest_path','manifest_sha256','restore_receipt_path','restore_receipt_sha256'))
    manifest,manifest_state=read(review['manifest_path'],review['manifest_sha256'])
    receipt,receipt_state=read(review['restore_receipt_path'],review['restore_receipt_sha256'])
    exact(manifest,('version','files'));exact(receipt,('version','manifest_sha256','files'))
    if (type(manifest['version']) is not int or manifest['version']!=1 or type(receipt['version']) is not int
            or receipt['version']!=1 or receipt['manifest_sha256']!=review['manifest_sha256']
            or not isinstance(manifest['files'],list) or len(manifest['files'])!=len(required)
            or not isinstance(receipt['files'],list) or len(receipt['files'])!=len(required)):
        raise guard.Unavailable('Complete isolated restore required')
    restored={}
    for row in receipt['files']:
        exact(row,('role','sha256'))
        if not isinstance(row['role'],str) or row['role'] in restored:raise guard.Unavailable('Duplicate restore role')
        restored[row['role']]=row['sha256']
    facts={};immutable={}
    for row in manifest['files']:
        exact(row,('role','source','backup','restore','sha256'));role=row['role']
        if (not isinstance(role,str) or role not in required or role in facts or row['source']!=str(required[role])
                or not guard.digest_value(row['sha256']) or restored.get(role)!=row['sha256']):
            raise guard.Unavailable('Repair backup scope differs')
        if any(path(row[key]).is_relative_to(root) for key in ('backup','restore') for root in roots):
            raise guard.Unavailable('Restore copies must remain outside libraries')
        states={key:private(row[key]) for key in ('backup','restore')}
        if any(value['sha256']!=row['sha256'] for value in states.values()):raise guard.Unavailable('Restored backup differs')
        if Path(row['backup']).parent==Path(row['restore']).parent:raise guard.Unavailable('Independent restore directory required')
        signatures=[states[key]['signature'] for key in ('backup','restore')]
        if original:
            source=file_state(path(row['source']))
            if source['sha256']!=row['sha256']:raise guard.Unavailable('Backup is stale against current source')
            signatures.insert(0,source['signature'])
        if len({tuple(signature[:2]) for signature in signatures})!=len(signatures):
            raise guard.Unavailable('Independent backup and restore inodes required')
        if role in ('catalog','workflow'):
            for key in (('source','backup','restore') if original else ('backup','restore')):database(row[key])
        facts[role]=dict(row,signatures=signatures);immutable[role]=states
    if set(restored)!=set(required) or set(facts)!=set(required):raise guard.Unavailable('Missing restore scope')
    return dict(manifest_sha256=review['manifest_sha256'],restore_sha256=review['restore_receipt_sha256'],files=facts),dict(
        manifest=manifest_state,receipt=receipt_state,files=immutable)


def request(raw):
    value=guard.decode_json(raw) if isinstance(raw,(str,bytes)) else raw
    exact(value,FIELDS)
    if (type(value['version']) is not int or value['version']!=1 or value['repair']!=REPAIR
            or not guard.digest_value(value['plan_sha256']) or len(guard.compact(value))>guard.MAX_OUTPUT):
        raise guard.Unavailable('Exact retained-repeat repair request required')
    path(value['plan_path']);guard.census_value(value['census'])
    exact(value['backup'],('manifest_path','manifest_sha256','restore_receipt_path','restore_receipt_sha256'))
    return json.loads(json.dumps(value))


def family(records, payload):
    if any(record['version']==2 for record in records.values()):
        if __package__:
            from .publication_derivative import matches
        else:
            from publication_derivative import matches
        return list(matches(records,payload).values())
    return [record for record in records.values() if record['inventory']['payload']==payload]


def correct_observation(database, workflow, writer, owners, roots, payload, *, transaction=None):
    _,records=guard.registry_snapshot(workflow,writer.root/'publication-v1.json')
    matches=family(records,payload)
    member_payloads={record['inventory']['payload'] for record in matches}
    if any(record['version']==2 for record in matches):
        member_payloads.update(record['lineage']['plan']['facts']['source']['inventory']['payload']
                              for record in matches if record['version']==2)
    inventories=[];observed=[]
    for owner in owners:
        actual=guard.observe_owners(database,writer,[owner],roots,transaction=transaction)
        if actual['inventory']['payload'] not in (member_payloads or {payload}):
            raise guard.Unavailable('Protected correct publication left exact reviewed family')
        inventories.append(actual['inventory']);observed.extend(actual['observed'])
    if not inventories:raise guard.Unavailable('Protected correct owner required')
    return dict(inventory=inventories[0],observed=observed),inventories


def admitted(capability, writer):
    if type(capability) is not Reconcile or getattr(_LOCAL,'reconcile',None) is not capability:
        raise guard.Unavailable('Exact live retained-repeat capability required')
    capability.check(writer)


class Reconcile:
    def __init__(self,writer,raw):
        import mylar
        from mylar import native_writers
        from mylar.publication_api import Controller
        if not native_writers.active() or getattr(_LOCAL,'reconcile',None) is not None:
            raise guard.Unavailable('Fresh native retained-repeat producer required')
        native_writers.admission(writer)
        self.writer=writer;self.request=request(raw);self.token=guard.canonical_digest(self.request)
        self.deadline=time.monotonic()+guard.TIMEOUT;self.config=Path(mylar.DATA_DIR);self.roots=[Path(mylar.CONFIG.DESTINATION_DIR)]
        self.catalog=self.config/'mylar.db';self.workflow=self.config/'workflow.sqlite'
        if any(self.config.is_relative_to(root) for root in self.roots):raise guard.Unavailable('Private native state must remain outside libraries')
        self.plan,self.plan_state=read(self.request['plan_path'],self.request['plan_sha256'])
        plan=self.plan
        exact(plan,('version','kind','executable','readiness','scope','registration_request','registration_commit',
                    'observations','writer_identity','backup','evidence','repeat','token'))
        if (type(plan['version']) is not int or plan['version']!=1 or plan['kind']!='publication-correction-plan'
                or plan['executable'] is not False or plan['token']!=guard.canonical_digest({k:v for k,v in plan.items() if k!='token'})
                or not guard.same_json(plan['writer_identity'],guard.writer_identity(writer))):
            raise guard.Unavailable('Correction plan is not current native evidence')
        exact(plan['scope'],('version','config_dir','library_roots','tool_root'))
        if (plan['scope']['version']!=1 or plan['scope']['config_dir']!=str(self.config)
                or plan['scope']['library_roots']!=[str(p) for p in self.roots]
                or plan['scope']['tool_root']!=str(guard.TOOL_ROOT)):
            raise guard.Unavailable('Plan scope differs from trusted native configuration')
        if any(path(value).is_relative_to(root) for value in (
                self.request['plan_path'],plan['evidence']['path'],self.request['backup']['manifest_path'],
                self.request['backup']['restore_receipt_path']) for root in self.roots):
            raise guard.Unavailable('Private review evidence must remain outside libraries')
        self.census,records=guard.registry_snapshot(self.workflow,writer.root/'publication-v1.json')
        registration=plan['registration_request']
        if (not guard.same_json(self.request['census'],self.census)
                or not guard.same_json(registration['census'],self.census)):
            raise guard.Unavailable('New current-census plan required after registration')
        repeat=plan['repeat']
        exact(repeat,('executable','readiness','source','inventory','correct','acquisition_provenance','failed_release_binding','retention'))
        if (repeat['executable'] is not False or repeat['acquisition_provenance'] is not None
                or repeat['failed_release_binding'] is not None):raise guard.Unavailable('Repeat provenance must remain unresolved')
        self.owner=guard.exact_owner(repeat['source']['owner']);self.source=path(repeat['source']['catalog']['path'])
        matches=family(records,repeat['inventory']['payload'])
        allowed={guard.canonical_digest(owner):owner for record in matches for owner in record['allowed']}
        rejected={guard.canonical_digest(owner) for record in matches for owner in record['rejected']}
        if (guard.canonical_digest(self.owner) not in rejected or not matches
                or {guard.canonical_digest(item) for item in registration['allowed']}!=set(allowed)
                or {guard.canonical_digest(item) for item in registration['rejected']}!=rejected
                or not 1<=len(allowed)<=8
                or plan['evidence']['sha256']!=registration['evidence']['sha256']
                or not any(record['evidence']['sha256']==plan['evidence']['sha256'] for record in matches)):
            raise guard.Unavailable('Repeat must have registered reviewed rejected ownership')
        self.correct_owners=registration['allowed'];self.controller=Controller(mylar.DATA_DIR,[str(p) for p in self.roots])
        self.correct,self.correct_inventories=correct_observation(self.catalog,self.workflow,writer,self.correct_owners,self.roots,repeat['inventory']['payload'])
        observed=guard.observe_owners(self.catalog,writer,[self.owner],self.roots)
        if (not guard.same_json(self.correct,plan['observations']) or not guard.same_json(self.correct['observed'],repeat['correct'])
                or not guard.same_json(observed,dict(inventory=repeat['inventory'],observed=[repeat['source']]))
                or observed['inventory']['payload']!=repeat['inventory']['payload']):
            raise guard.Unavailable('Current repeat or protected correct publication changed')
        self.source_state=file_state(self.source);self.source_inventory=guard.inventory(self.source)
        self.source_parents=native.parents(self.source)
        if any(file_state(path(item['catalog']['path']))['signature'][:2]==self.source_state['signature'][:2]
               for item in self.correct['observed']):raise guard.Unavailable('Protected original cannot be retired')
        self.required=dict(catalog=self.catalog,workflow=self.workflow,marker=writer.root/'publication-v1.json',repeat=self.source)
        self.required.update({'correct_'+str(index):path(item['catalog']['path']) for index,item in enumerate(self.correct['observed'])})
        restored,self.backup_state=backup(self.request['backup'],self.required,self.roots)
        if not guard.same_json(restored,plan['backup']):raise guard.Unavailable('Plan restore verification differs')
        self.evidence_state=private(plan['evidence']['path'])
        if self.evidence_state['sha256']!=plan['evidence']['sha256']:raise guard.Unavailable('Review evidence changed')
        self.baseline=catalog(self.catalog);rows=[row for row in self.baseline[self.owner['table']] if row['IssueID']==self.owner['issueid']]
        if len(rows)!=1 or not rows[0]['Location']:raise guard.Unavailable('Exact false catalog claim required')
        self.row=rows[0];self.changed=dict(self.row,Location=None)
        self.path=writer.root/NAME;self.phase='prepared';self.fd=None
        self.folder=writer.root/'retained-repeats-v1';private_directory(self.folder)
        self.folder=self.folder/self.token;self.folder_id=private_directory(self.folder)
        self.original=self.folder/('original'+self.source.suffix.lower())
        self.history=writer.root/'reconciled-repeats-v1';self.history_id=private_directory(self.history)
        if os.path.lexists(self.original):raise guard.Unavailable('Prior retained repeat requires passive review')
        self.store=native_writers.existing_store(mylar.DATA_DIR)
        self.value=dict(version=1,kind='reconcile',token=self.token,request=self.request,writer=guard.writer_identity(writer),
            census=self.census,plan_token=plan['token'],owner=self.owner,row=self.row,changed=self.changed,
            source=str(self.source),source_state=self.source_state,source_inventory=self.source_inventory,
            source_parents=self.source_parents,correct=self.correct,
            original=str(self.original),folder=self.folder_id,history=self.history_id,
            journal=guard.signature(self.workflow.lstat())[:2],phase='prepared',fence=None,original_state=None,
            projection=self.projection())
        self.value=json.loads(json.dumps(self.value))
        self.binding=guard.canonical_digest({k:v for k,v in self.value.items() if k not in ('phase','fence','original_state')})
        self.journal=dict(version=1,token=self.token,binding=self.binding,request=self.request,phase='prepared')
        if not self.store.create('retained_repeat',self.token,self.journal):raise guard.Unavailable('Repeat repair already attempted')
        _write(self.path,self.value,exclusive=True);self.intent_state=guard.private_evidence(self.path)
        writer.mark_release_pending();self.fd=checked_file(writer.release_pending)
        self.value['fence']=guard.signature(os.fstat(self.fd));_write(self.path,self.value,exclusive=False)
        self.intent_state=guard.private_evidence(self.path)

    def observation_path(self, value):return Path(value)

    def projection(self):
        return dict(source=str(self.source),source_state=self.source_state,inventory=self.source_inventory,
            parents=self.source_parents,owner=self.owner,row=self.row,changed=self.changed,correct=self.correct,
            correct_owners=self.correct_owners,correct_inventories=self.correct_inventories,census=self.census,baseline=guard.canonical_digest(self.baseline),
            plan=guard.canonical_digest(self.plan),plan_state=self.plan_state,backup_state=self.backup_state,
            evidence_state=self.evidence_state,request=self.request,config=str(self.config),roots=[str(root) for root in self.roots],
            catalog=str(self.catalog),workflow=str(self.workflow),required={key:str(value) for key,value in self.required.items()},
            original=str(self.original),folder=str(self.folder),folder_id=self.folder_id,history=str(self.history),history_id=self.history_id,
            path=str(self.path),store=str(self.store.path),token=self.token)

    def check(self,writer):
        if (writer is not self.writer or time.monotonic()>=self.deadline or not writer.local[1].depth or type(self.fd) is not int
                or guard.writer_identity(writer)!=self.value['writer'] or not writer.fenced(release=True)
                or writer.fenced() or writer.fenced(tagger=True)
                or guard.signature(os.fstat(self.fd))!=self.value['fence']
                or guard.signature(writer.release_pending.lstat())!=self.value['fence']
                or guard.private_evidence(self.path)!=self.intent_state
                or not guard.same_json(guard.private_json(self.path),self.value)
                or guard.signature(self.folder.lstat())[:2]!=self.folder_id
                or guard.signature(self.history.lstat())[:2]!=self.history_id
                or guard.signature(self.workflow.lstat())[:2]!=self.value['journal']
                or not guard.same_json(self.store.get('retained_repeat',self.token),self.journal)
                or not guard.same_json(self.projection(),self.value['projection'])
                or self.phase!=self.value['phase'] or self.phase!=self.journal['phase']
                or not guard.same_json(getattr(self,'original_state',None),self.value['original_state'])
                or not guard.same_json(self.journal.get('original_state'),self.value['original_state'])
                or os.path.lexists(writer.root/'tagger-recovery-v1.pending')):
            raise guard.Unavailable('Retained-repeat capability changed')
        if not guard.same_json(guard.registry_snapshot(self.workflow,writer.root/'publication-v1.json')[0],self.census):
            raise guard.Unavailable('Retained-repeat census changed')

    def checkpoint(self):
        admitted(self,self.writer)
        if (not guard.same_json(private(self.request['plan_path'],maximum=guard.MAX_OUTPUT),self.plan_state)
                or not guard.same_json(private(self.plan['evidence']['path']),self.evidence_state)):
            raise guard.Unavailable('Reviewed plan changed')
        _,immutable=backup(self.request['backup'],self.required,self.roots,original=False)
        if not guard.same_json(immutable,self.backup_state):raise guard.Unavailable('Verified restore evidence changed')
        current,inventories=correct_observation(self.catalog,self.workflow,self.writer,self.correct_owners,self.roots,self.source_inventory['payload'],transaction=self)
        if not guard.same_json(inventories,self.correct_inventories) or not guard.same_json(current,self.correct):raise guard.Unavailable('Protected correct publication changed')
        for owner in self.correct_owners:
            proof=self.controller._check(dict(payload=self.source_inventory['payload'],owner=owner),self.writer,transaction=self)
            if proof['decision']!='allowed':raise guard.Unavailable('Correct publication must remain registered allowed')
        expected=json.loads(json.dumps(self.baseline))
        if self.phase in ('cataloged','retired','committed'):
            expected[self.owner['table']]=[self.changed if row==self.row else row for row in expected[self.owner['table']]]
            expected[self.owner['table']].sort(key=guard.canonical_digest)
        if not guard.same_json(catalog(self.catalog),expected):raise guard.Unavailable('Full catalog changed outside exact Location CAS')
        if self.phase not in ('retired','committed'):
            if (not guard.same_json(file_state(self.source),self.source_state)
                    or not guard.same_json(guard.inventory(self.source),self.source_inventory)):
                raise guard.Unavailable('Retained-repeat source changed')
        elif os.path.lexists(self.source):raise guard.Unavailable('Retired repeat source recreated')
        if self.phase!='prepared' and not guard.same_json(retained(self.original,self.source_state['sha256']),self.original_state):
            raise guard.Unavailable('Private retained repeat changed')
        admitted(self,self.writer)
        # All expensive archive/private authority reads precede these final
        # incarnation checks. A replaced repeat must never reach unlink.
        if not guard.same_json(catalog(self.catalog),expected):raise guard.Unavailable('Final exact catalog changed')
        if self.phase!='prepared' and not guard.same_json(guard.signature(self.original.lstat()),self.original_state['signature']):
            raise guard.Unavailable('Final retained original incarnation changed')
        for item in self.correct['observed']:
            if not guard.same_json(guard.signature(path(item['catalog']['path']).lstat()),item['signature']):
                raise guard.Unavailable('Final protected correct source changed')
        if self.phase not in ('retired','committed'):
            if (native.parents(self.source)!=self.source_parents
                    or not guard.same_json(guard.signature(self.source.lstat()),self.source_state['signature'])):
                raise guard.Unavailable('Final repeat source incarnation changed')
        elif os.path.lexists(self.source):raise guard.Unavailable('Final retired repeat was recreated')

    def advance(self,phase):
        admitted(self,self.writer);updated=dict(self.journal,phase=phase)
        if not self.store.replace('retained_repeat',self.token,self.journal,updated):raise guard.Unavailable('Repeat journal CAS changed')
        self.journal=updated;self.phase=phase;self.value=dict(self.value,phase=phase)
        _write(self.path,self.value,exclusive=False);self.intent_state=guard.private_evidence(self.path)

    @contextmanager
    def owned(self):
        if getattr(_LOCAL,'reconcile',None) is not None:raise guard.Unavailable('Nested retained-repeat capability')
        _LOCAL.reconcile=self
        try:yield self
        finally:
            _LOCAL.reconcile=None
            if self.fd is not None:os.close(self.fd);self.fd=None

    def publish(self,*,boundary=lambda _:None):
        self.checkpoint();boundary('prepared');self.checkpoint()
        if shutil.disk_usage(self.folder).free<self.source_state['signature'][2]+128*1024**2:
            raise guard.Unavailable('Insufficient private repeat preservation space')
        with guard.regular(self.source) as incoming,self.original.open('xb') as out:
            os.chmod(self.original,0o600);shutil.copyfileobj(incoming,out,1024**2);out.flush();os.fsync(out.fileno())
        sync(self.folder);original_state=retained(self.original,self.source_state['sha256'])
        updated=dict(self.journal,original_state=original_state)
        if not self.store.replace('retained_repeat',self.token,self.journal,updated):raise guard.Unavailable('Retained original journal changed')
        self.journal=updated;self.original_state=original_state;self.value=dict(self.value,original_state=original_state)
        _write(self.path,self.value,exclusive=False);self.intent_state=guard.private_evidence(self.path)
        self.advance('preserved');self.checkpoint();boundary('preserved');self.checkpoint()
        with closing(sqlite3.connect(self.catalog)) as db:
            db.row_factory=sqlite3.Row;db.execute('BEGIN IMMEDIATE')
            rows=db.execute('SELECT * FROM '+self.owner['table']+' WHERE IssueID=?',(self.owner['issueid'],)).fetchall()
            if len(rows)!=1 or not guard.same_json(dict(rows[0]),self.row):raise guard.Unavailable('False owner row CAS changed')
            count=db.execute('UPDATE '+self.owner['table']+' SET Location=NULL WHERE IssueID=? AND ComicID=? AND Location=? AND Status IS ?',
                (self.owner['issueid'],self.owner['parentcomicid'],self.row['Location'],self.row['Status'])).rowcount
            if count!=1:raise guard.Unavailable('False location CAS failed')
            db.commit()
        self.advance('cataloged');self.checkpoint();boundary('cataloged');self.checkpoint()
        self.source.unlink();sync(self.source.parent)
        self.advance('retired');self.checkpoint();boundary('retired');self.checkpoint()
        self.advance('committed');self.checkpoint()
        witness=dict(version=1,kind='retained-repeat-terminal',token=self.token,intent=self.value,
            original=self.original_state,correct=self.correct,catalog_sha256=guard.canonical_digest(catalog(self.catalog)))
        _write(self.history/(self.token+'.json'),witness,exclusive=True)
        terminal=dict(self.journal,result=result(witness))
        if not self.store.replace('retained_repeat',self.token,self.journal,terminal):raise guard.Unavailable('Repeat terminal CAS changed')
        self.journal=terminal;self.checkpoint();boundary('witness');self.checkpoint();boundary('clearing');self.checkpoint()
        try:self.writer.clear_release_pending();self.path.unlink();sync(self.writer.root)
        except BaseException:
            if not os.path.lexists(self.path):_write(self.path,self.value,exclusive=True)
            raise
        return result(witness)


def result(witness):
    return dict(version=1,token=witness['token'],phase='retained-review',requires_review=True,
        source=witness['intent']['source'],owner=witness['intent']['owner'],witness=guard.canonical_digest(witness),
        acquisition_provenance=None,failed_release_binding=None)


def commit(raw,*,boundary=lambda _:None):
    from mylar import native_writers
    if not native_writers.publication_mode():raise ValueError('Owned retained-repeat protocol required')
    try:
        with native_writers.operation() as writer:
            capability=Reconcile(writer,raw)
            with capability.owned():return capability.publish(boundary=boundary)
    except native.Review:raise ValueError('Retained repeat requires review') from None


def status(token):
    import mylar
    from mylar import native_writers
    if not native_writers.publication_mode() or not guard.digest_value(token):raise ValueError('Exact passive repeat protocol required')
    try:
        with native_writers.operation() as writer:
            terminal=writer.root/'reconciled-repeats-v1'/(token+'.json')
            stamp=guard.private_evidence(terminal);witness=guard.private_json(terminal)
            exact(witness,('version','kind','token','intent','original','correct','catalog_sha256'))
            if witness['version']!=1 or witness['kind']!='retained-repeat-terminal' or witness['token']!=token:
                raise guard.Unavailable('Malformed repeat terminal witness')
            intent=witness['intent'];value=request(intent['request'])
            binding=guard.canonical_digest({k:v for k,v in intent.items() if k not in ('phase','fence','original_state')})
            expected=dict(version=1,token=token,binding=binding,request=value,phase='committed',original_state=witness['original'],result=result(witness))
            store=native_writers.existing_store(mylar.DATA_DIR)
            original=writer.root/'retained-repeats-v1'/token/('original'+Path(intent['source']).suffix.lower())
            if (guard.canonical_digest(value)!=token or intent['kind']!='reconcile' or intent['token']!=token
                    or not guard.same_json(store.get('retained_repeat',token),expected)
                    or guard.writer_identity(writer)!=intent['writer'] or intent['original']!=str(original)
                    or guard.signature(original.parent.lstat())[:2]!=intent['folder']
                    or guard.signature(terminal.parent.lstat())[:2]!=intent['history']
                    or guard.signature(Path(mylar.DATA_DIR,'workflow.sqlite').lstat())[:2]!=intent['journal']
                    or os.path.lexists(intent['source']) or not guard.same_json(retained(original,intent['source_state']['sha256']),witness['original'])):
                raise guard.Unavailable('Retained repeat terminal identities changed')
            projection=intent['projection']
            plan,plan_state=read(value['plan_path'],value['plan_sha256'])
            if (not guard.same_json(plan_state,projection['plan_state'])
                    or guard.canonical_digest(plan)!=projection['plan']
                    or not guard.same_json(private(plan['evidence']['path']),projection['evidence_state'])):
                raise guard.Unavailable('Retained review history changed')
            _,immutable=backup(value['backup'],{key:path(source) for key,source in projection['required'].items()},
                               [Path(mylar.CONFIG.DESTINATION_DIR)],original=False)
            if not guard.same_json(immutable,projection['backup_state']):raise guard.Unavailable('Retained isolated restore history changed')
            census=guard.registry_snapshot(Path(mylar.DATA_DIR,'workflow.sqlite'),writer.root/'publication-v1.json')[0]
            if not guard.same_json(census,intent['census']):raise guard.Unavailable('Repeat terminal census changed')
            owners=[item['owner'] for item in witness['correct']['observed']]
            current,inventories=correct_observation(Path(mylar.DATA_DIR,'mylar.db'),Path(mylar.DATA_DIR,'workflow.sqlite'),writer,owners,[mylar.CONFIG.DESTINATION_DIR],intent['source_inventory']['payload'])
            if not guard.same_json(inventories,projection['correct_inventories']) or not guard.same_json(current,witness['correct']):raise guard.Unavailable('Correct publication changed after retention')
            for item in current['observed']:
                proof=native.require(item['catalog']['path'],issueid=item['owner']['issueid'],comicid=item['owner']['parentcomicid'])
                if proof is None or proof['decision']!='allowed':raise guard.Unavailable('Correct publication is no longer registered allowed')
            if guard.canonical_digest(catalog(Path(mylar.DATA_DIR,'mylar.db')))!=witness['catalog_sha256']:
                raise guard.Unavailable('Retained repeat catalog changed')
            census_paths=(Path(mylar.DATA_DIR,'workflow.sqlite'),writer.root/'publication-v1.json')
            census_stamps=[guard.signature(candidate.lstat()) for candidate in census_paths]
            final=native_writers.admission(writer)
            if not guard.same_json(final,intent['census']):raise guard.Unavailable('Final repeat census changed')
            final_correct,final_inventories=correct_observation(Path(mylar.DATA_DIR,'mylar.db'),Path(mylar.DATA_DIR,'workflow.sqlite'),writer,owners,[mylar.CONFIG.DESTINATION_DIR],intent['source_inventory']['payload'])
            if (not guard.same_json(final_inventories,projection['correct_inventories']) or not guard.same_json(final_correct,witness['correct'])
                    or guard.canonical_digest(catalog(Path(mylar.DATA_DIR,'mylar.db')))!=witness['catalog_sha256']):
                raise guard.Unavailable('Protected publication changed during final admission')
            catalog_path=Path(mylar.DATA_DIR,'mylar.db');catalog_stamp=guard.signature(catalog_path.lstat())
            if guard.canonical_digest(catalog(catalog_path))!=witness['catalog_sha256']:
                raise guard.Unavailable('Final retained repeat catalog changed')
            if (guard.private_evidence(terminal)!=stamp or not guard.same_json(guard.private_json(terminal),witness)
                    or not guard.same_json(store.get('retained_repeat',token),expected)
                    or not guard.same_json(retained(original,intent['source_state']['sha256']),witness['original'])
                    or os.path.lexists(intent['source'])):raise guard.Unavailable('Repeat terminal changed during final proof')
            if not guard.same_json(guard.writer_identity(writer),intent['writer']):
                raise guard.Unavailable('Final retained repeat writer protocol changed')
            for item in witness['correct']['observed']:
                if not guard.same_json(guard.signature(path(item['catalog']['path']).lstat()),item['signature']):
                    raise guard.Unavailable('Final protected correct incarnation changed')
            if (any(os.path.lexists(candidate) for candidate in (writer.pending,writer.tagger_pending,writer.release_pending,writer.root/NAME,writer.root/'nested-derivative-v1.json',writer.root/'tagger-recovery-v1.pending'))
                    or any(os.path.lexists(str(database)+suffix) for database in (census_paths[0],catalog_path) for suffix in ('-journal','-wal','-shm'))
                    or any(not guard.same_json(guard.signature(candidate.lstat()),expected_stamp) for candidate,expected_stamp in zip(census_paths,census_stamps))
                    or not guard.same_json(guard.signature(catalog_path.lstat()),catalog_stamp)
                    or not guard.same_json(guard.signature(terminal.lstat()),stamp['signature'])
                    or not guard.same_json(guard.signature(original.lstat()),witness['original']['signature'])):
                raise guard.Unavailable('Final retained repeat current or private evidence changed')
            return result(witness)
    except native.Review:raise ValueError('Retained repeat terminal requires review') from None
