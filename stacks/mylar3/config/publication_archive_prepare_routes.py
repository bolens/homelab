"""Authenticated publicationControl owned-repair PREPARE/status proposal.

Only the existing primary-key adapter may expose these Controller branches.
No stage selection from paths, adoption, catalog/reader write or replay.
"""
import copy
import hashlib
import importlib
import os
from pathlib import Path
import re
import stat
import time
import zipfile

CORE_SHA='dbd40b36800ea8eeeae90d6043e3113655bae7e798a52efc175c070a4e2c54a1'
MAX_OPERATIONS=8
MAX_STAGE_BYTES=4*1024**3
NAMES={'intent.json','original.arc','restored-original.arc','prepared.cbz','preparation.json'}


def module():
    name=(__package__+'.publication_archive_owned') if __package__ else 'publication_archive_owned'
    value=importlib.import_module(name)
    if __package__ and Path(value.__file__)!=Path('/app/mylar3/mylar/publication_archive_owned.py'):
        raise ValueError('Installed owned repair module required')
    if hashlib.sha256(Path(value.__file__).read_bytes()).hexdigest()!=CORE_SHA:
        raise ValueError('Owned repair module changed')
    return value


def namespace(c,m,deadline):
    root=m.canonical(c.root);before=m.signature(root);nodes=m.ancestors([root]);files={};directories={};names=set();total=0;count=0
    with os.scandir(root) as entries:
        for entry in entries:
            count+=1;m.check(count<=4096,'stage-root-entry-bound')
            if not entry.name.startswith('archive-repair-'):continue
            m.check(re.fullmatch('archive-repair-[0-9a-f]{64}',entry.name) is not None,'unknown-stage-name')
            p=root/entry.name;signature=m.signature(p)
            m.check(stat.S_ISDIR(signature[5]) and stat.S_IMODE(signature[5])==0o700 and signature[6]==os.geteuid(),'private-stage-directory')
            names.add(entry.name);m.check(len(names)<=MAX_OPERATIONS,'stage-count-bound');directories[p]=signature
            m.merge_nodes(nodes,m.ancestors([p]))
            with os.scandir(p) as children:
                for child in children:
                    m.check(child.name in NAMES and p/child.name not in files,'unknown-stage-member')
                    f=m.fact(p/child.name,512*1024**2+2,deadline);total+=f['signature9'][2]
                    m.check(total<=MAX_STAGE_BYTES,'stage-byte-bound');files[p/child.name]=f
    m.check(m.signature(root)==before,'stage-root-census-CAS')
    return dict(root=before,names=names,files=files,directories=directories,nodes=nodes,bytes=total)


def close(c,m,snapshot,root_signature,deadline):
    # All custom calls precede the final direct incarnation vector.
    now=namespace(c,m,deadline)
    m.check(time.monotonic()<deadline,'request-deadline')
    m.check(now['names']==snapshot['names'] and now['files']==snapshot['files']
            and now['directories']==snapshot['directories'],'stage-namespace-CAS')
    for p,f in snapshot['files'].items():m.check(m.stat9(os.lstat(p))==f['signature9'],'terminal-stage-file')
    for p,v in snapshot['directories'].items():m.check(m.stat9(os.lstat(p))==v,'terminal-stage-directory')
    for p,v in snapshot['nodes'].items():m.check(m.stat5(os.lstat(p))==v,'terminal-stage-ancestor')
    m.check(m.stat9(os.lstat(c.root))==root_signature,'terminal-stage-root')


def terminal(c,w,m,snapshot,root_signature,files,nodes,claims,g):
    # Complete shared vectors after the last namespace/SDK/read callback.
    merged=dict(snapshot['files'])
    for p,f in files.items():
        m.check(p not in merged or merged[p]==f,'terminal-conflicting-file');merged[p]=f
    parents=dict(snapshot['nodes'])
    for p,v in nodes.items():
        m.check(p not in parents or parents[p]==v,'terminal-conflicting-ancestor');parents[p]=v
    g.ordinary_purpose(w)
    for p,v in claims.items():
        try:s=os.lstat(p)
        except FileNotFoundError:m.check(v is None,'terminal-claim-absence');continue
        m.check((s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,None if stat.S_ISDIR(s.st_mode) else s.st_nlink)==v,'terminal-claim-CAS')
    for db in (c.database,c.native_database):
        for suffix in ('-wal','-shm','-journal'):
            try:os.lstat(str(db)+suffix)
            except FileNotFoundError:continue
            raise m.Held('terminal-companion')
    for name in ('negative-retirement-v1.pending','negative-retirement-v1.terminal-pending',
                 'archive-repair-v1.pending','archive-repair-v1.terminal-pending','normalizer-v1.pending','tagger-v2.pending','release-v1.pending',
                 'tagger-publication-v1.json','nested-derivative-v1.json','tagger-recovery-v1.pending'):
        try:os.lstat(w.root/name)
        except FileNotFoundError:continue
        raise m.Held('terminal-pending')
    for p,v in snapshot['directories'].items():
        s=os.lstat(p);m.check([s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink]==v,'terminal-directory')
    s=os.lstat(c.root)
    m.check([s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink]==root_signature,'terminal-root')
    for p,f in merged.items():
        s=os.lstat(p);m.check([s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_gid,s.st_nlink]==f['signature9'],'terminal-control')
    for p,v in parents.items():
        s=os.lstat(p);m.check([s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid]==v,'terminal-ancestor')

def summary(action,owner,operation_id,outcome,*,binding=None):
    return dict(version=1,action=action,owner=owner,operation_id=operation_id,outcome=outcome,
                token=binding['token'] if binding is not None else None,
                census=binding['census'] if binding is not None else None,
                executable=False,native_grant=False,mutation_authority=False,adoption_authority=False,
                publication_acceptance=False,reader_preservation_verified=False,
                source_preservation_verified=binding is not None)


def durable_status(c,w,owner,op,m,modules,deadline):
    """Recompute owning facts; persisted JSON never supplies authority or paths."""
    owner=modules[2].exact_owner(owner)
    g=modules[2];controls=[Path(m.__file__),c.database,c.native_database,w.lock,w.root/'publication-v1.json']
    nodes=m.ancestors([op,*controls,*map(Path,c.roots)]);files={p:m.fact(p,256*1024**2,deadline) for p in controls}
    initial_directory=m.signature(op);census,records=g.media_snapshot(c.database,w.root/'publication-v1.json')
    observed,claims,extra=m.catalog(c,owner,g,deadline);m.merge_nodes(nodes,extra)
    source=Path(observed['owner']['path']);sourcefact=m.fact(source,512*1024**2,deadline);files[source]=sourcefact
    sourceattrs=m.attributes(source);m.historical_claims(owner,sourcefact,records,claims,g)
    m.merge_nodes(nodes,m.ancestors([source]))
    present=set(os.listdir(op));m.check(present<=NAMES and 'intent.json' in present,'retained-intent-required')
    intent_fact=m.fact(op/'intent.json',1024**2,deadline);files[op/'intent.json']=intent_fact
    intent=g.decode_json(m.read_checked(op/'intent.json',intent_fact['signature9'],1024**2,deadline).decode())
    expected_intent=dict(version=1,kind='owned-archive-repair-prepare-intent',source=sourcefact,owner=owner,
                         census=census,operation_id=op.name[len('archive-repair-'):],executable=False,mutation_authority=False)
    m.check(intent==expected_intent,'current-retained-intent')
    if present!=NAMES:
        # Retain partial evidence. No automatic retry, completion, deletion or token.
        for name in present:files[op/name]=m.fact(op/name,512*1024**2+2,deadline)
        outcome='retained-incomplete';binding=None
    else:
        prepared_fact=m.fact(op/'preparation.json',512*1024**2+2,deadline);files[op/'preparation.json']=prepared_fact
        body=g.decode_json(m.read_checked(op/'preparation.json',prepared_fact['signature9'],512*1024**2+2,deadline).decode())
        required={'version','kind','implementation','owner','census','catalog','policy','writer_identity','source','source_attributes',
                  'exceptional_witness','derivative','preservation','operation_id','custody','controls','ancestors','claims','executable','native_grant','mutation_authority',
                  'adoption_authority','ordinary_source_admission','publication_acceptance','reader_preservation_verified','token'}
        m.check(type(body) is dict and set(body)==required,'prepared-shape')
        token=body['token'];untokened={k:v for k,v in body.items() if k!='token'}
        m.check(g.digest_value(token) and token==m.digest(untokened),'prepared-token')
        for key in ('executable','native_grant','mutation_authority','adoption_authority','ordinary_source_admission','publication_acceptance','reader_preservation_verified'):
            m.check(body[key] is False,'prepared-no-authority')
        expected_controls={str(p):files[p] for p in controls}
        expected_nodes={str(p):v for p,v in nodes.items()}
        expected_claims=g.decode_json(m.compact({str(p):v for p,v in claims.items()}).decode())
        m.check(body['controls']==expected_controls and body['ancestors']==expected_nodes and body['claims']==expected_claims,'prepared-control-namespace-CAS')
        m.check(body['version']==1 and type(body['version']) is int and body['kind']=='owned-archive-repair-preparation'
                and body['operation_id']==op.name[len('archive-repair-'):] and body['owner']==owner and body['census']==census
                and body['implementation']==files[Path(m.__file__)] and body['catalog']==observed
                and body['source']==sourcefact and body['source_attributes']==sourceattrs
                and body['writer_identity']==g.writer_identity(w),'prepared-current-facts')
        raw=m.read_checked(source,sourcefact['signature9'],512*1024**2,deadline)
        plan=modules[4].classify(raw,g,deadline);m.check(plan['status']=='repair-candidate','prepared-supported-defect')
        witness=m.witness(raw,sourcefact,plan,modules,deadline);repaired,evidence=modules[5].derive(raw,witness,g,deadline)
        policy=m.policy(c,w,owner,plan['inventory'],records,modules,deadline)
        m.check(body['exceptional_witness']==witness and body['preservation']==evidence and body['policy']==policy,'prepared-independent-proof')
        m.check(type(body['custody']) is dict and set(body['custody'])=={'original','restore'},'prepared-custody-shape')
        for name,key in (('original.arc','original'),('restored-original.arc','restore')):
            f=m.fact(op/name,512*1024**2,deadline);files[op/name]=f
            m.check(f==body['custody'][key] and f['sha256']==sourcefact['sha256'] and m.attributes(op/name)==sourceattrs,'prepared-custody-CAS')
        f=m.fact(op/'prepared.cbz',512*1024**2+2,deadline);files[op/'prepared.cbz']=f
        stage=m.read_checked(op/'prepared.cbz',f['signature9'],512*1024**2+2,deadline)
        m.check(f==body['derivative'] and stage==repaired,'prepared-stage-bytes-CAS')
        inventory,metadata=modules[5].independent(stage,g,deadline)
        m.check(inventory==plan['inventory'] and metadata==plan['root_metadata_sha256'],'prepared-stage-CAS')
        outcome='prepared';binding=body
    # Revalidation callbacks precede complete direct file/claim/ancestor/absence closure.
    m.check(g.media_snapshot(c.database,w.root/'publication-v1.json')==(census,records),'status-current-authority')
    m.check(m.writer_pair(c,w,modules)[1]==g.writer_identity(w),'status-writer')
    for p,f in files.items():m.check(m.fact(p,max(1,f['signature9'][2]),deadline)==f,'status-file-CAS')
    for p,v in claims.items():
        try:s=os.lstat(p)
        except FileNotFoundError:m.check(v is None,'status-claim-absence');continue
        m.check((s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,None if stat.S_ISDIR(s.st_mode) else s.st_nlink)==v,'status-claim-CAS')
    for db in (c.database,c.native_database):
        for suffix in ('-wal','-shm','-journal'):
            try:os.lstat(str(db)+suffix)
            except FileNotFoundError:continue
            raise m.Held('status-companion')
    for p,f in files.items():m.check(m.stat9(os.lstat(p))==f['signature9'],'status-terminal-file')
    for p,v in nodes.items():m.check(m.stat5(os.lstat(p))==v,'status-terminal-ancestor')
    m.check(m.stat9(os.lstat(op))==initial_directory,'status-terminal-operation')
    return outcome,binding,files,nodes,claims


def _dispatch(controller,writer,value):
    m=module();modules=m.sdk();g=modules[2];m.writer_pair(controller,writer,modules)
    # Original configuration and held purpose survive every preparation/history callback.
    controller_binding=(controller.root,controller.database,controller.native_database,controller.writer_root,tuple(controller.roots),controller.tool_root)
    writer_binding=(writer.root,writer.lock,writer.pending,writer.tagger_pending,writer.release_pending,tuple(writer.lock_identity),tuple(writer.root_identity),writer.local)
    local=writer.local
    history_vectors=None;history_originals=None
    action=value['action'];owner=g.exact_owner(value['owner']);operation_id=value['operation_id']
    m.check(action in ('prepare-archive-repair','archive-repair-status') and type(operation_id) is str
            and re.fullmatch('[0-9a-f]{64}',operation_id),'exact-owned-route')
    deadline=time.monotonic()+g.TIMEOUT;before=namespace(controller,m,deadline)
    op=controller.root/('archive-repair-'+operation_id)
    if action=='prepare-archive-repair':
        m.check(op.name not in before['names'] and len(before['names'])<MAX_OPERATIONS,'exclusive-stage-required')
        # Reserve the largest bounded three custody/stage files, plus receipts.
        m.check(before['bytes']+3*(512*1024**2+2)+128*1024**2<=MAX_STAGE_BYTES,'stage-reservation-bound')
        prep=m.prepare_existing(controller,writer,owner,operation_id);root_after=m.signature(controller.root)
        root_signature=copy.deepcopy(root_after)
        original_files=copy.deepcopy(prep._files);original_nodes=copy.deepcopy(prep._nodes);original_claims=copy.deepcopy(prep._claims)
        history_ref=None
        if os.path.lexists(controller.root/'archive-history-v1'):
            from mylar import publication_archive_history as history
            history_ref=copy.deepcopy(history.prepared(prep))
            raw=m.read_checked(Path(history_ref['path']),history_ref['signature9'],history.MAX_BYTES,deadline)
            if hashlib.sha256(raw).hexdigest()!=history_ref['sha256']:raise m.Held('route-emitted-history-hash')
            history_originals=copy.deepcopy(g.decode_json(raw.decode())['original_vectors'])
            # Preserve the complete emitted originals before subsequent callbacks.
            history_vectors=copy.deepcopy(history.record_vectors(copy.deepcopy(history_ref)))
        after=namespace(controller,m,deadline)
        m.check(after['names']==before['names']|{op.name},'new-stage-census')
        for p,f in before['files'].items():m.check(after['files'].get(p)==f,'old-stage-file-CAS')
        for p,v in before['directories'].items():m.check(after['directories'].get(p)==v,'old-stage-directory-CAS')
        final_snapshot=copy.deepcopy(after)
        binding=prep.revalidate();result=summary(action,owner,operation_id,'prepared',binding=binding)
        close(controller,m,copy.deepcopy(after),copy.deepcopy(root_after),deadline);prep.close_passive()
        m.check(time.monotonic()<deadline,'request-deadline')
        snapshot=final_snapshot;files=original_files;nodes=original_nodes;claims=original_claims
        terminal(controller,writer,m,copy.deepcopy(snapshot),copy.deepcopy(root_signature),copy.deepcopy(files),copy.deepcopy(nodes),copy.deepcopy(claims),g)
    elif op.name not in before['names']:
        snapshot=copy.deepcopy(before);root_signature=copy.deepcopy(before['root'])
        result=summary(action,owner,operation_id,'missing');close(controller,m,copy.deepcopy(before),before['root'],deadline)
        m.check(time.monotonic()<deadline,'request-deadline')
        files={};nodes={};claims={}
        terminal(controller,writer,m,copy.deepcopy(snapshot),copy.deepcopy(root_signature),copy.deepcopy(files),copy.deepcopy(nodes),copy.deepcopy(claims),g)
    else:
        outcome,binding,files,nodes,claims=durable_status(controller,writer,owner,op,m,modules,deadline)
        snapshot=copy.deepcopy(before);root_signature=copy.deepcopy(before['root']);files=copy.deepcopy(files);nodes=copy.deepcopy(nodes);claims=copy.deepcopy(claims)
        result=summary(action,owner,operation_id,outcome,binding=binding)
        close(controller,m,copy.deepcopy(before),before['root'],deadline)
        m.check(time.monotonic()<deadline,'request-deadline')
        files=copy.deepcopy(files);nodes=copy.deepcopy(nodes);claims=copy.deepcopy(claims)
        terminal(controller,writer,m,copy.deepcopy(snapshot),copy.deepcopy(root_signature),copy.deepcopy(files),copy.deepcopy(nodes),copy.deepcopy(claims),g)
    # Conflict-refusing detached originals, never a fresh observation permission.
    vectors={'files9':{},'nodes5':{},'claims':{},'namespaces':{},'absent':set()}
    def merge(field,path,value):
        path=str(path);value=None if value is None else tuple(value)
        if path in vectors[field] and vectors[field][path]!=value:raise m.Held('route-original-conflict')
        vectors[field][path]=value
    for path,fact in {**snapshot['files'],**files}.items():
        if path in snapshot['files'] and path in files and snapshot['files'][path]!=files[path]:raise m.Held('route-file-conflict')
        merge('files9',path,fact['signature9'])
    for path,value in snapshot['directories'].items():merge('files9',path,value)
    merge('files9',controller_binding[0],root_signature)
    for collection in (snapshot['nodes'],nodes):
        for path,value in collection.items():merge('nodes5',path,value)
    for path,value in claims.items():merge('claims',path,value)
    for directory in snapshot['directories']:
        merge('namespaces',directory,sorted(Path(path).name for path in snapshot['files'] if Path(path).parent==directory))
    if history_vectors is not None:
        for originals in (history_originals,history_vectors):
            for field in ('files9','nodes5','claims','namespaces'):
                for path,value in originals[field]:merge(field,path,sorted(value) if field=='namespaces' else value)
            vectors['absent'].update(originals['absent'])
        merge('files9',history_ref['path'],history_ref['signature9'])
    for database in controller_binding[1:3]:
        vectors['absent'].update(str(database)+suffix for suffix in ('-wal','-shm','-journal'))
    vectors['absent'].update(str(writer_binding[0]/name) for name in (
        'negative-retirement-v1.pending','negative-retirement-v1.terminal-pending',
        'archive-repair-v1.pending','archive-repair-v1.terminal-pending','normalizer-v1.pending',
        'tagger-v2.pending','release-v1.pending','tagger-publication-v1.json',
        'nested-derivative-v1.json','tagger-recovery-v1.pending'))
    # No SDK/signature/digest/serializer/namespace helper follows this primitive closure.
    if (controller.root,controller.database,controller.native_database,controller.writer_root,tuple(controller.roots),controller.tool_root)!=controller_binding:
        raise m.Held('route-controller-binding')
    if (writer.root,writer.lock,writer.pending,writer.tagger_pending,writer.release_pending,tuple(writer.lock_identity),tuple(writer.root_identity),writer.local)!=writer_binding or writer.local is not local:
        raise m.Held('route-writer-binding')
    if getattr(local[1],'depth',0)<=0 or any(getattr(local[1],name,False) for name in ('allow_pending','allow_tagger_pending','allow_release_pending')):
        raise m.Held('route-writer-purpose')
    for path,names in vectors['namespaces'].items():
        if tuple(sorted(os.listdir(path)))!=names:raise m.Held('route-original-namespace')
    for path,expected in vectors['claims'].items():
        try:info=os.lstat(path)
        except FileNotFoundError:
            if expected is not None:raise m.Held('route-original-claim-absence')
            continue
        if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,None if info.st_mode & 0o170000 == 0o040000 else info.st_nlink)!=expected:
            raise m.Held('route-original-claim')
    for path in vectors['absent']:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise m.Held('route-original-absence')
    for path,expected in vectors['files9'].items():
        info=os.lstat(path)
        if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_mode,info.st_uid,info.st_gid,info.st_nlink)!=expected:
            raise m.Held('route-original-file')
    for path,expected in vectors['nodes5'].items():
        info=os.lstat(path)
        if (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)!=expected:raise m.Held('route-original-node')
    return result


def dispatch(controller,writer,value):
    try:return _dispatch(controller,writer,value)
    except (ValueError,OSError,RuntimeError,zipfile.BadZipFile) as error:
        # No archive-controlled names, private paths or arbitrary reasons leave
        # the authenticated adapter's fixed failure response.
        if __package__:
            from .publication_guard import Unavailable
        else:
            from publication_guard import Unavailable
        raise Unavailable('Owned archive preparation requires review') from error
