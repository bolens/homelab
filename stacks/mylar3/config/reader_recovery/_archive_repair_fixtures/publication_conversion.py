"""One native producer for lossless container relocation; interrupted intents hold."""
from contextlib import contextmanager, closing
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
    from . import publication_guard as guard, publication_native as native, tagger_attributes
    from .publication_transaction import NAME, _write
    from .media_writer import checked_file, sync
else:
    import publication_guard as guard
    import publication_native as native
    import tagger_attributes
    from publication_transaction import NAME, _write
    from media_writer import checked_file, sync

_LOCAL=threading.local()
FIELDS={'version','source','target','prepared','issueid','comicid','source_sha256',
        'output_sha256','inventory_sha256','census'}


def inventory_digest(value):
    return guard.canonical_digest({key:value[key] for key in ('members','pages','payload')})


def stage_token(source, source_sha256, output_sha256):
    return guard.canonical_digest(dict(source=str(source),source_sha256=source_sha256,
                                       output_sha256=output_sha256))


def validate(raw):
    value=guard.decode_json(raw) if isinstance(raw,(str,bytes)) else raw
    if (not isinstance(value,dict) or set(value)!=FIELDS or type(value['version']) is not int
            or value['version']!=1 or any(not isinstance(value[key],str) for key in FIELDS-{'version','census'})
            or len(guard.compact(value))>guard.MAX_OUTPUT
            or any(not re.fullmatch('[a-f0-9]{64}',value[key]) for key in ('source_sha256','output_sha256','inventory_sha256'))
            or any(not re.fullmatch('[1-9][0-9]{0,15}',value[key]) for key in ('issueid','comicid'))):
        raise ValueError('Exact conversion request required')
    source=Path(value['source']);prepared=Path(value['prepared'])
    if (not source.is_absolute() or '..' in source.parts or source.suffix.lower() not in ('.cbr','.cb7','.7z')
            or not prepared.is_absolute() or '..' in prepared.parts
            or value['target']!=source.stem+'.cbz' or len(value['target'].encode())>255):
        raise ValueError('Only lossless container suffix relocation is supported')
    return json.loads(json.dumps(value))


def private_directory(path):
    if any(item.is_symlink() for item in (path,*path.parents)):
        raise guard.Unavailable('Linked conversion recovery state')
    if not path.exists():path.mkdir(mode=0o700);sync(path.parent)
    info=path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.geteuid() or stat.S_IMODE(info.st_mode)!=0o700):
        raise guard.Unavailable('Private conversion state required')
    return guard.signature(info)[:2]


def file_state(path):
    with guard.regular(path) as stream:
        value=guard.signature(os.fstat(stream.fileno()))
        if value[8]!=1:raise guard.Unavailable('Conversion physical alias')
    attributes=tagger_attributes.capture(path);signature,sha=guard.file_hash(path)
    if signature!=value or tagger_attributes.capture(path)!=attributes:raise guard.Unavailable('Conversion file changed during read')
    return dict(signature=value,attributes=attributes,sha256=sha)


def retained(path, checksum):
    value=file_state(path)
    if (value['sha256']!=checksum or value['signature'][6]!=os.geteuid()
            or stat.S_IMODE(value['signature'][5])!=0o600):
        raise guard.Unavailable('Private retained original changed')
    return value


def admitted(capability, writer):
    if type(capability) is not Conversion or getattr(_LOCAL,'conversion',None) is not capability:
        raise guard.Unavailable('Exact active conversion capability required')
    capability.check(writer)


def catalog_row(path, owner):
    """Capture every owner column; projected census alone omits ComicSize."""
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        db.row_factory=sqlite3.Row
        rows=db.execute('SELECT * FROM '+owner['table']+' WHERE IssueID=?',(owner['issueid'],)).fetchall()
    if len(rows)!=1:return None
    return dict(rows[0])


def target_absence(database, target, roots):
    """Even missing/deleted/annual catalog paths reserve their exact spelling."""
    before=guard.signature(database.lstat());deadline=time.monotonic()+guard.TIMEOUT
    sidecars=[str(database)+suffix for suffix in ('-journal','-wal','-shm')]
    if any(os.path.lexists(path) for path in sidecars):raise guard.Unavailable('Catalog requires recovery')
    with closing(sqlite3.connect(database.as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        db.set_progress_handler(lambda:int(time.monotonic()>=deadline),1000)
        rows={};count=size=0
        for table,fields in (('comics',('ComicID','ComicLocation')),('issues',('ComicID','Location')),('annuals',('ComicID','Location'))):
            total,amount=db.execute('SELECT count(*),coalesce(sum('+ '+'.join('coalesce(length(CAST('+field+' AS BLOB)),0)' for field in fields)+'),0) FROM '+table).fetchone()
            count+=total;size+=amount
            if count>guard.CATALOG_ROWS or size>guard.CATALOG_BYTES:raise guard.Unavailable('Conversion catalog exceeds bounds')
            rows[table]=list(db.execute('SELECT '+','.join(fields)+' FROM '+table))
        parents={}
        for comicid,location in rows['comics']:parents.setdefault(comicid,[]).append(location)
        for comicid,location in rows['issues']+rows['annuals']:
            if time.monotonic()>=deadline:raise guard.Unavailable('Conversion catalog timed out')
            if not location:continue
            parent=parents.get(comicid,[])
            if len(parent)!=1:raise guard.Unavailable('Ambiguous conversion catalog parent')
            path=guard._catalog_path(parent[0],location,roots)
            if path==target:raise guard.Unavailable('Conversion target is already catalog claimed')
    if guard.signature(database.lstat())!=before or any(os.path.lexists(path) for path in sidecars):
        raise guard.Unavailable('Conversion target catalog changed')


class Conversion:
    def __init__(self, writer, request):
        import mylar
        from mylar import native_writers
        if getattr(_LOCAL,'conversion',None) is not None or not native_writers.active():
            raise guard.Unavailable('Fresh native conversion producer required')
        native_writers.admission(writer)
        self.deadline=time.monotonic()+guard.TIMEOUT
        self.writer=writer;self.request=validate(request);self.token=guard.canonical_digest(self.request)
        self.source=Path(request['source']);self.target=self.source.with_name(request['target'])
        self.prepared=Path(request['prepared']);self.catalog=Path(mylar.DATA_DIR)/'mylar.db'
        expected=Path(mylar.CONFIG.CACHE_DIR)/'comic-conversions'/stage_token(
            self.source,request['source_sha256'],request['output_sha256'])/'prepared.cbz'
        if self.prepared!=expected:raise guard.Unavailable('Prepared archive has no exact shared-cache binding')
        self.census=native_writers.admission(writer)
        if not guard.same_json(self.census,request['census']):raise guard.Unavailable('Conversion census changed')
        self.proof=native.require(self.source,issueid=request['issueid'],comicid=request['comicid'])
        if self.proof is None or self.proof['owner'] is None:raise guard.Unavailable('Conversion needs current native owner')
        self.owner=self.proof['owner'];self.input=self.proof['inventory']
        self.output=guard.inventory(self.prepared)
        if (self.input['source_sha256']!=request['source_sha256']
                or self.output['source_sha256']!=request['output_sha256']
                or inventory_digest(self.input)!=request['inventory_sha256']
                or inventory_digest(self.input)!=inventory_digest(self.output)):
            raise guard.Unavailable('Conversion is not an exact lossless container change')
        self.source_state=file_state(self.source);self.prepared_state=retained(self.prepared,request['output_sha256'])
        self.observed=guard.observe_owners(self.catalog,writer,[self.owner],[mylar.CONFIG.DESTINATION_DIR])['observed']
        if self.observed[0]['catalog']['path']!=str(self.source):raise guard.Unavailable('Source is not current catalog publication')
        target_absence(self.catalog,self.target,[mylar.CONFIG.DESTINATION_DIR])
        self.row=catalog_row(self.catalog,self.owner)
        if self.row is None or 'ComicSize' not in self.row:raise guard.Unavailable('Incomplete conversion catalog')
        old=self.row['Location'];self.new_location=(str(self.target) if Path(old).is_absolute()
            else str(Path(old).with_name(self.target.name)))
        if any(p.name.casefold()==self.target.name.casefold() for p in self.source.parent.iterdir()):
            raise guard.Unavailable('Conversion target collision')
        root=writer.root/'conversion-originals-v1';private_directory(root)
        self.folder=root/self.token;self.folder_id=private_directory(self.folder)
        self.original=self.folder/('original'+self.source.suffix.lower())
        self.history=writer.root/'conversion-completed-v1';self.history_id=private_directory(self.history)
        if os.path.lexists(self.original):raise guard.Unavailable('Prior conversion original requires review')
        self.path=writer.root/NAME;self.fd=None;self.phase='prepared'
        self.parents={str(path):native.parents(path) for path in (self.source,self.target,self.prepared,self.original)}
        self.value=dict(version=1,kind='conversion',token=self.token,request=self.request,
            writer=guard.writer_identity(writer),census=self.census,owner=self.owner,row=self.row,
            source_state=self.source_state,prepared_state=self.prepared_state,
            inventory_sha256=inventory_digest(self.input),observed=self.observed,
            original=str(self.original),folder=self.folder_id,history=self.history_id,
            journal=guard.signature(Path(mylar.DATA_DIR,'workflow.sqlite').lstat())[:2],phase='prepared',fence=None,
            states=dict(original=None,target=None))
        self.store=native_writers.existing_store(mylar.DATA_DIR)
        self.value['projection']=self.projection();self.value=json.loads(json.dumps(self.value))
        self.binding=guard.canonical_digest({key:value for key,value in self.value.items() if key not in ('phase','fence','states')})
        self.journal_state=dict(version=1,token=self.token,request=self.request,binding=self.binding,phase='prepared',states=self.value['states'])
        if not self.store.create('owned_conversion',self.token,self.journal_state):
            raise guard.Unavailable('Prior conversion attempt requires passive acknowledgement or review')
        _write(self.path,self.value,exclusive=True)
        self.evidence=guard.private_evidence(self.path)
        writer.mark_release_pending();self.fd=checked_file(writer.release_pending)
        self.value.update(fence=guard.signature(os.fstat(self.fd)))
        _write(self.path,self.value,exclusive=False);self.evidence=guard.private_evidence(self.path)

    def projection(self):
        return dict(request=self.request,source=str(self.source),target=str(self.target),prepared=str(self.prepared),
            catalog=str(self.catalog),census=self.census,proof=self.proof,owner=self.owner,input=self.input,output=self.output,
            source_state=self.source_state,prepared_state=self.prepared_state,observed=self.observed,row=self.row,
            new_location=self.new_location,folder=str(self.folder),folder_id=self.folder_id,original=str(self.original),
            history=str(self.history),history_id=self.history_id,path=str(self.path),store=str(self.store.path),token=self.token,
            deadline=self.deadline,parents=self.parents)

    def check(self, writer):
        import mylar
        if (time.monotonic()>=self.deadline or writer is not self.writer or not writer.local[1].depth or type(self.fd) is not int
                or guard.writer_identity(writer)!=self.value['writer'] or not writer.fenced(release=True)
                or writer.fenced() or writer.fenced(tagger=True)
                or guard.signature(os.fstat(self.fd))!=self.value['fence']
                or guard.signature(writer.release_pending.lstat())!=self.value['fence']
                or guard.private_evidence(self.path)!=self.evidence
                or not guard.same_json(guard.private_json(self.path),self.value)
                or not guard.same_json(self.request,self.value['request'])
                or not guard.same_json(self.projection(),self.value['projection'])
                or self.phase!=self.value['phase'] or self.phase!=self.journal_state['phase']
                or not guard.same_json(dict(original=getattr(self,'original_state',None),target=getattr(self,'target_state',None)),self.value['states'])
                or not guard.same_json(self.journal_state['states'],self.value['states'])
                or guard.signature(self.folder.lstat())[:2]!=self.folder_id
                or guard.signature(self.history.lstat())[:2]!=self.history_id
                or guard.signature(Path(mylar.DATA_DIR,'workflow.sqlite').lstat())[:2]!=self.value['journal']
                or os.path.lexists(writer.root/'tagger-recovery-v1.pending')):
            raise guard.Unavailable('Conversion capability or durable state changed')
        if not guard.same_json(self.store.get('owned_conversion',self.token),self.journal_state):
            raise guard.Unavailable('Immutable conversion journal changed')
        census,_=guard.registry_snapshot(Path(mylar.DATA_DIR)/'workflow.sqlite',writer.root/'publication-v1.json')
        if not guard.same_json(census,self.census):raise guard.Unavailable('Conversion census changed')

    def observation_path(self, path):
        return Path(path)  # Catalog is conditionally moved before source retirement.

    def checkpoint(self):
        import mylar
        admitted(self,self.writer)
        if not guard.same_json(file_state(self.prepared),self.prepared_state):raise guard.Unavailable('Prepared conversion changed')
        if os.path.lexists(self.source):
            if not guard.same_json(file_state(self.source),self.source_state):raise guard.Unavailable('Original source changed')
            source_proof=native.require(self.source,issueid=self.request['issueid'],comicid=self.request['comicid'],transaction=self)
            if inventory_digest(source_proof['inventory'])!=self.request['inventory_sha256']:
                raise guard.Unavailable('Source members changed')
        elif self.phase not in ('retired','committed'):raise guard.Unavailable('Premature conversion source retirement')
        if self.phase!='prepared' and not guard.same_json(retained(self.original,self.request['source_sha256']),self.original_state):
            raise guard.Unavailable('Retained original identity changed')
        observed=guard.observe_owners(self.catalog,self.writer,[self.owner],[mylar.CONFIG.DESTINATION_DIR],transaction=self)['observed']
        expected=self.observed[0];actual=observed[0]
        if (actual['catalog']['path']!=str(self.target if self.phase in ('cataloged','retired','committed') else self.source)
                or not guard.same_json({k:v for k,v in actual['catalog'].items() if k not in ('path','location')},
                                       {k:v for k,v in expected['catalog'].items() if k not in ('path','location')})
                or not guard.same_json(actual['owner'],self.owner)):
            raise guard.Unavailable('Conversion catalog owner changed')
        row=catalog_row(self.catalog,self.owner);changed=dict(self.row)
        if self.phase in ('cataloged','retired','committed'):
            changed.update(Location=self.new_location,ComicSize=self.output['source_signature'][2])
        if not guard.same_json(row,changed):raise guard.Unavailable('Conversion owner row changed')
        if os.path.lexists(self.target):
            output=guard.inventory(self.target)
            target_state=file_state(self.target)
            if not guard.same_json(target_state,self.target_state):raise guard.Unavailable('Conversion target identity changed')
            if (output['source_sha256']!=self.request['output_sha256']
                    or inventory_digest(output)!=self.request['inventory_sha256']
                    or target_state['attributes']!=self.source_state['attributes']
                    or target_state['signature'][3:4]!=self.source_state['signature'][3:4]
                    or target_state['signature'][5:8]!=self.source_state['signature'][5:8]):
                raise guard.Unavailable('Conversion output or access attributes changed')
            native.require(self.target,issueid=self.request['issueid'],comicid=self.request['comicid'],transaction=self)
        elif self.phase not in ('prepared','preserved'):raise guard.Unavailable('Conversion target missing')
        admitted(self,self.writer)
        for path,binding in self.parents.items():
            if native.parents(Path(path))!=binding:raise guard.Unavailable('Final conversion parent identity changed')
        if self.phase!='prepared' and not guard.same_json(guard.signature(self.original.lstat()),self.original_state['signature']):
            raise guard.Unavailable('Final retained original identity changed')
        if not guard.same_json(guard.signature(self.prepared.lstat()),self.prepared_state['signature']):
            raise guard.Unavailable('Final prepared output identity changed')
        if self.phase not in ('prepared','preserved') and not guard.same_json(guard.signature(self.target.lstat()),self.target_state['signature']):
            raise guard.Unavailable('Final conversion target identity changed')
        if os.path.lexists(self.source):
            if not guard.same_json(guard.signature(self.source.lstat()),self.source_state['signature']):
                raise guard.Unavailable('Final conversion source identity changed')
        elif self.phase not in ('retired','committed'):raise guard.Unavailable('Final conversion source disappeared')
        return observed

    def phase_to(self, phase):
        admitted(self,self.writer)
        updated=dict(self.journal_state,phase=phase)
        if not self.store.replace('owned_conversion',self.token,self.journal_state,updated):
            raise guard.Unavailable('Conversion journal CAS changed')
        self.journal_state=updated
        self.phase=phase;self.value=dict(self.value,phase=phase)
        _write(self.path,self.value,exclusive=False);self.evidence=guard.private_evidence(self.path)

    def seal_states(self,**states):
        admitted(self,self.writer);updated=dict(self.value['states'],**states)
        journal=dict(self.journal_state,states=updated)
        if not self.store.replace('owned_conversion',self.token,self.journal_state,journal):
            raise guard.Unavailable('Conversion archive states CAS changed')
        self.journal_state=journal;self.value=dict(self.value,states=updated)
        for key,value in states.items():setattr(self,key+'_state',value)
        _write(self.path,self.value,exclusive=False);self.evidence=guard.private_evidence(self.path)

    @contextmanager
    def owned(self):
        if getattr(_LOCAL,'conversion',None) is not None:raise guard.Unavailable('Nested conversion capability')
        _LOCAL.conversion=self
        try:yield self
        finally:
            _LOCAL.conversion=None
            if self.fd is not None:os.close(self.fd);self.fd=None

    def publish(self, *, boundary=lambda _:None):
        import mylar
        from mylar import pack_bindings, native_writers
        self.checkpoint();boundary('prepared')
        reserve=128*1024**2
        if (shutil.disk_usage(self.folder).free<self.input['source_signature'][2]+reserve
                or shutil.disk_usage(self.source.parent).free<self.output['source_signature'][2]+reserve):
            raise guard.Unavailable('Insufficient verified conversion preservation space')
        with guard.regular(self.source) as incoming,self.original.open('xb') as out:
            os.chmod(self.original,0o600);shutil.copyfileobj(incoming,out,1024**2);out.flush();os.fsync(out.fileno())
        sync(self.folder);self.seal_states(original=retained(self.original,self.request['source_sha256']))
        self.phase_to('preserved');self.checkpoint();boundary('preserved')
        store=native_writers.existing_store(mylar.DATA_DIR)
        bindings=pack_bindings.capture(store,self.source,self.target,catalog_owner={
            'issueid':self.request['issueid'],'comicid':self.request['comicid']})
        self.value=dict(self.value,pack_bindings=bindings)
        _write(self.path,self.value,exclusive=False);self.evidence=guard.private_evidence(self.path)
        self.checkpoint()
        temporary=self.source.parent/('.conversion-'+self.token+'.tmp')
        with guard.regular(self.prepared) as incoming,temporary.open('xb') as out:
            shutil.copyfileobj(incoming,out,1024**2);out.flush();os.fsync(out.fileno())
        st=self.source_state['signature']
        os.chown(temporary,st[6],st[7]);os.chmod(temporary,stat.S_IMODE(st[5]))
        tagger_attributes.apply(temporary,self.source_state['attributes'])
        os.utime(temporary,ns=(self.source.stat().st_atime_ns,st[3]))
        if guard.file_hash(temporary)[1]!=self.request['output_sha256']:raise guard.Unavailable('Library copy changed')
        temporary_state=file_state(temporary)
        self.checkpoint();target_absence(self.catalog,self.target,[mylar.CONFIG.DESTINATION_DIR]);boundary('copy')
        if any(p.name.casefold()==self.target.name.casefold() for p in self.source.parent.iterdir()):
            raise guard.Unavailable('Conversion target collision after copy')
        self.checkpoint();target_absence(self.catalog,self.target,[mylar.CONFIG.DESTINATION_DIR])
        if not guard.same_json(file_state(temporary),temporary_state):raise guard.Unavailable('Prepared library copy changed before link')
        os.link(temporary,self.target);temporary.unlink();sync(self.source.parent)
        self.seal_states(target=file_state(self.target))
        self.phase_to('linked');self.checkpoint();boundary('linked')
        old=self.row['Location']
        self.checkpoint()
        with closing(sqlite3.connect(self.catalog)) as db:
            db.execute('BEGIN IMMEDIATE')
            current=dict(zip([r[1] for r in db.execute('PRAGMA table_info('+self.owner['table']+')')],
                db.execute('SELECT * FROM '+self.owner['table']+' WHERE IssueID=?',(self.owner['issueid'],)).fetchone()))
            if not guard.same_json(current,self.row):raise guard.Unavailable('Conversion catalog CAS changed')
            updated=db.execute('UPDATE '+self.owner['table']+' SET Location=?,ComicSize=? WHERE IssueID=? AND ComicID=? AND Location=? AND Status=?',
                (self.new_location,self.output['source_signature'][2],self.owner['issueid'],self.owner['parentcomicid'],old,self.row['Status']))
            if updated.rowcount!=1:raise guard.Unavailable('Conversion catalog CAS failed')
            db.commit()
        self.phase_to('cataloged');self.checkpoint();boundary('cataloged')
        self.checkpoint()
        self.source.unlink();sync(self.source.parent)
        self.phase_to('retired');self.checkpoint();boundary('retired')
        self.checkpoint()
        pack_bindings.finalize(store,bindings,self.request['output_sha256'],catalog_owner={
            'issueid':self.request['issueid'],'comicid':self.request['comicid']})
        self.phase_to('committed');observed=self.checkpoint();boundary('pack-bound')
        observed=self.checkpoint()
        witness=dict(version=1,kind='conversion-terminal',token=self.token,intent=self.value,
            observed=observed,original=retained(self.original,self.request['source_sha256']),target=file_state(self.target),
            pack_bindings=bindings)
        _write(self.history/(self.token+'.json'),witness,exclusive=True)
        self.checkpoint()
        terminal=dict(self.journal_state,result=result(witness))
        if not self.store.replace('owned_conversion',self.token,self.journal_state,terminal):
            raise guard.Unavailable('Conversion terminal journal CAS changed')
        self.journal_state=terminal;self.checkpoint();boundary('witness')
        self.checkpoint();boundary('clearing');self.checkpoint()
        try:
            self.writer.clear_release_pending();self.path.unlink();sync(self.writer.root)
        except BaseException:
            # An unacknowledged removal/fsync must never make recovery look empty.
            if not os.path.lexists(self.path):_write(self.path,self.value,exclusive=True)
            raise
        return result(witness)


def result(witness):
    request=witness['intent']['request']
    return dict(version=1,token=witness['token'],phase='committed',source=request['source'],
        destination=str(Path(request['source']).with_name(request['target'])),sha256=request['output_sha256'],
        inventory_sha256=request['inventory_sha256'],witness=guard.canonical_digest(witness))


def _commit(raw, *, boundary=lambda _:None):
    from mylar import native_writers
    request=validate(raw)
    if not native_writers.publication_mode():raise ValueError('Owned conversion protocol required')
    with native_writers.operation() as writer:
        token=guard.canonical_digest(request)
        if os.path.lexists(writer.root/'conversion-completed-v1'/(token+'.json')):
            raise ValueError('Conversion already attempted; reconcile through passive status')
        capability=Conversion(writer,request)
        with capability.owned():return capability.publish(boundary=boundary)


def _status(token):
    """Passive exact current terminal witness; never reconstruct publication rights."""
    import mylar
    from mylar import native_writers
    if not native_writers.publication_mode():raise ValueError('Owned conversion protocol required')
    if not isinstance(token,str) or not re.fullmatch('[a-f0-9]{64}',token):raise ValueError('Invalid conversion token')
    with native_writers.operation() as writer:
        terminal_path=writer.root/'conversion-completed-v1'/(token+'.json')
        terminal_evidence=guard.private_evidence(terminal_path)
        witness=guard.private_json(terminal_path)
        if (not isinstance(witness,dict) or set(witness)!={'version','kind','token','intent','observed','original','target','pack_bindings'}
                or witness['version']!=1 or witness['kind']!='conversion-terminal' or witness['token']!=token):
            raise ValueError('Invalid conversion terminal witness')
        intent=witness['intent'];request=validate(intent['request'])
        binding=guard.canonical_digest({key:value for key,value in intent.items() if key not in ('phase','fence','pack_bindings','states')})
        journal=native_writers.existing_store(mylar.DATA_DIR).get('owned_conversion',token)
        expected_journal=dict(version=1,token=token,request=request,binding=binding,phase='committed',states=intent['states'],result=result(witness))
        if not guard.same_json(journal,expected_journal):raise ValueError('Conversion terminal journal or immutable witness changed')
        if (intent['kind']!='conversion' or guard.writer_identity(writer)!=intent['writer']
                or guard.signature((writer.root/'conversion-originals-v1'/token).lstat())[:2]!=intent['folder']
                or guard.signature((writer.root/'conversion-completed-v1').lstat())[:2]!=intent['history']
                or guard.signature(Path(mylar.DATA_DIR,'workflow.sqlite').lstat())[:2]!=intent['journal']):
            raise ValueError('Conversion terminal state identity changed')
        if guard.canonical_digest(request)!=token or intent['token']!=token:raise ValueError('Conversion terminal binding changed')
        if os.path.lexists(request['source']):raise ValueError('Converted source was recreated')
        original=Path(intent['original']);target=Path(request['source']).with_name(request['target'])
        expected_original=writer.root/'conversion-originals-v1'/token/('original'+Path(request['source']).suffix.lower())
        if (original!=expected_original or not guard.same_json(retained(original,request['source_sha256']),witness['original'])
                or not guard.same_json(file_state(target),witness['target'])):raise ValueError('Conversion terminal archives changed')
        census,_=guard.registry_snapshot(Path(mylar.DATA_DIR)/'workflow.sqlite',writer.root/'publication-v1.json')
        if not guard.same_json(census,intent['census']):raise ValueError('Conversion terminal census changed')
        proof=native.require(target,issueid=request['issueid'],comicid=request['comicid'])
        if proof is None or inventory_digest(proof['inventory'])!=request['inventory_sha256']:
            raise ValueError('Conversion terminal payload changed')
        observed=guard.observe_owners(Path(mylar.DATA_DIR)/'mylar.db',writer,[intent['owner']],[mylar.CONFIG.DESTINATION_DIR])['observed']
        if not guard.same_json(observed,witness['observed']):raise ValueError('Conversion terminal catalog changed')
        row=dict(intent['row']);old=row['Location']
        row.update(Location=str(target) if Path(old).is_absolute() else str(Path(old).with_name(target.name)),
                   ComicSize=witness['target']['signature'][2])
        if not guard.same_json(catalog_row(Path(mylar.DATA_DIR)/'mylar.db',intent['owner']),row):
            raise ValueError('Conversion terminal full owner row changed')
        final_paths=(Path(mylar.DATA_DIR,'workflow.sqlite'),writer.root/'publication-v1.json',Path(mylar.DATA_DIR,'mylar.db'))
        final_stamps=[guard.signature(candidate.lstat()) for candidate in final_paths]
        final_census=native_writers.admission(writer)
        if not guard.same_json(final_census,intent['census']):raise ValueError('Conversion final census changed')
        if (guard.private_evidence(terminal_path)!=terminal_evidence
                or not guard.same_json(guard.private_json(terminal_path),witness)
                or not guard.same_json(native_writers.existing_store(mylar.DATA_DIR).get('owned_conversion',token),expected_journal)
                or not guard.same_json(retained(original,request['source_sha256']),witness['original'])
                or not guard.same_json(file_state(target),witness['target'])
                or os.path.lexists(request['source'])):
            raise ValueError('Conversion terminal evidence changed during final admission')
        if not guard.same_json(guard.writer_identity(writer),intent['writer']):
            raise ValueError('Conversion final writer protocol changed')
        if (any(os.path.lexists(candidate) for candidate in (writer.pending,writer.tagger_pending,writer.release_pending,writer.root/NAME,writer.root/'nested-derivative-v1.json',writer.root/'tagger-recovery-v1.pending'))
                or any(os.path.lexists(str(database)+suffix) for database in (final_paths[0],final_paths[2]) for suffix in ('-journal','-wal','-shm'))
                or any(not guard.same_json(guard.signature(candidate.lstat()),expected) for candidate,expected in zip(final_paths,final_stamps))
                or not guard.same_json(guard.signature(terminal_path.lstat()),terminal_evidence['signature'])
                or not guard.same_json(guard.signature(original.lstat()),witness['original']['signature'])
                or not guard.same_json(guard.signature(target.lstat()),witness['target']['signature'])):
            raise ValueError('Conversion final current or private evidence changed')
        return result(witness)


def commit(raw, *, boundary=lambda _:None):
    try:return _commit(raw,boundary=boundary)
    except native.Review:
        raise ValueError('Conversion owner or retained evidence requires review') from None


def status(token):
    try:return _status(token)
    except native.Review:
        raise ValueError('Conversion terminal evidence requires review') from None
