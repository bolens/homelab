"""Existing-only owning preparation; saved JSON is never mutation authority."""
import copy
import hashlib
import os
from pathlib import Path
import re
import stat
import time
from mylar import publication_archive_owned as o
from mylar import publication_reader_lifecycle as lifecycle

OWNED_SHA='dbd40b36800ea8eeeae90d6043e3113655bae7e798a52efc175c070a4e2c54a1'
LIFECYCLE_SHA='2335f450a8998ce2155fffc05f496ed3f7ac42b8521de11bd142911f6fbc7ebe'
MAX=512*1024**2+2
NAMES={'intent.json','original.arc','restored-original.arc','prepared.cbz','preparation.json'}
PENDING=('negative-retirement-v1.pending','negative-retirement-v1.terminal-pending','archive-repair-v1.pending','archive-repair-v1.terminal-pending','normalizer-v1.pending','tagger-v2.pending','release-v1.pending','tagger-publication-v1.json','nested-derivative-v1.json','tagger-recovery-v1.pending')

def installed():
    for module, name, expected in ((o,'publication_archive_owned.py',OWNED_SHA),(lifecycle,'publication_reader_lifecycle.py',LIFECYCLE_SHA)):
        path=Path(module.__file__)
        o.check(path==Path('/app/mylar3/mylar')/name and path.resolve()==path,'existing-preparation-installed-dependency')
        o.check(hashlib.sha256(path.read_bytes()).hexdigest()==expected,'existing-preparation-dependency-source')
    path=Path(__file__)
    o.check(path==Path('/app/mylar3/mylar/publication_archive_preparation_existing.py') and path.resolve()==path,'existing-preparation-installed-factory')

def from_existing(controller,writer,owner,operation_id,custody):
    try:return _from_existing(controller,writer,owner,operation_id,custody)
    except (OSError,UnicodeError) as error:raise o.Held("existing-preparation-unavailable-original-state") from error

def _from_existing(controller,writer,owner,operation_id,custody):
    """Use only the original completed stage bound by genuine stopped custody.

    No operation creation, mutation, path argument, Writer bypass or receipt
    constructor exists. Historical stages without original metadata/directory
    custody are Held. Same-byte incarnation changes are not refreshed.
    """
    initial_deadline=time.monotonic()+180
    implementation=Path(__file__);nodes=o.ancestors([implementation,Path(o.__file__),Path(lifecycle.__file__)])
    factory_original=o.fact(implementation,1024**2,initial_deadline)
    dependency_originals={Path(module.__file__):o.fact(Path(module.__file__),1024**2,initial_deadline) for module in (o,lifecycle)}
    installed();o.check(type(custody) is lifecycle.StoppedReaderCustody,'existing-preparation-exact-custody')
    modules=o.sdk();g=modules[2]
    o.check(type(controller) is modules[0].Controller and type(writer) is modules[1].Writer,'existing-preparation-exact-sdk-types')
    roots,identity=o.writer_pair(controller,writer,modules)
    owner=g.exact_owner(owner);o.check(type(operation_id) is str and re.fullmatch('[0-9a-f]{64}',operation_id),'existing-preparation-operation-id')
    deadline=min(time.monotonic()+g.TIMEOUT,custody.deadline)
    stage=o.canonical(controller.root/('archive-repair-'+operation_id));metadata=stage/'preparation.json'
    o.check(all(not stage.is_relative_to(root) and not root.is_relative_to(stage) for root in roots),'existing-preparation-stage-scope')
    custody.revalidate_stopped();parent_files,parent_nodes,parent_absent=custody.vectors()
    parent_files=copy.deepcopy(parent_files);parent_nodes=copy.deepcopy(parent_nodes);parent_absent=tuple(parent_absent)
    o.merge_nodes(nodes,parent_nodes)
    for path in (metadata,stage):
        value=parent_files.get(path)
        o.check(type(value) in (list,tuple) and len(value)==9 and all(type(x) is int for x in value),'existing-preparation-original-stage-required')
        o.check(o.signature(path)==list(value),'existing-preparation-original-stage-incarnation')
    directory=list(parent_files[stage])
    o.check(stat.S_ISDIR(directory[5]) and stat.S_IMODE(directory[5])==0o700 and directory[6]==os.geteuid(),'existing-preparation-private-stage')
    o.check(set(os.listdir(stage))==NAMES,'existing-preparation-completed-census')
    metadata_fact=o.fact(metadata,MAX,deadline)
    o.check(metadata_fact['signature9']==list(parent_files[metadata]) and stat.S_IMODE(metadata_fact['signature9'][5])==0o600 and metadata_fact['signature9'][6]==os.geteuid(),'existing-preparation-original-metadata')
    raw_metadata=o.read_checked(metadata,metadata_fact['signature9'],MAX,deadline)
    body=g.decode_json(raw_metadata.decode())
    # Caller-controlled declarations are not used to select any read path.
    control=[Path(o.__file__),controller.database,controller.native_database,writer.lock,writer.root/'publication-v1.json']
    original_nodes=o.ancestors([Path(o.__file__),controller.root,writer.root,*roots,*control,stage])
    files={p:o.fact(p,256*1024**2,deadline) for p in control}
    o.check(files[Path(o.__file__)]==dependency_originals[Path(o.__file__)],'existing-preparation-owned-before-sdk')
    census,records=g.media_snapshot(controller.database,writer.root/'publication-v1.json')
    catalog,claims,extra=o.catalog(controller,owner,g,deadline);o.merge_nodes(original_nodes,extra)
    source=Path(catalog['owner']['path']);o.merge_nodes(original_nodes,o.ancestors([source]))
    source_fact=o.fact(source,512*1024**2,deadline);source_attrs=o.attributes(source)
    o.check(source_fact['signature9'][6]==os.geteuid(),'existing-preparation-source-owner')
    raw=o.read_checked(source,source_fact['signature9'],512*1024**2,deadline)
    plan=modules[4].classify(raw,g,deadline);o.check(plan['status']=='repair-candidate','existing-preparation-supported-original')
    witness=o.witness(raw,source_fact,plan,modules,deadline);repaired,evidence=modules[5].derive(raw,witness,g,deadline)
    policy=o.policy(controller,writer,owner,plan['inventory'],records,modules,deadline)
    o.historical_claims(owner,source_fact,records,claims,g)
    files[source]=source_fact
    for item in policy['other_observed']:
        path=Path(item['catalog']['path']);files[path]=dict(path=str(path),signature9=item['signature'],sha256=item['source_sha256']);o.merge_nodes(original_nodes,o.ancestors([path]))
    # A complete exclusive preparation has exact canonical intended metadata.
    intent=dict(version=1,kind='owned-archive-repair-prepare-intent',source=source_fact,owner=owner,census=census,operation_id=operation_id,executable=False,mutation_authority=False)
    intent_path=stage/'intent.json';files[intent_path]=o.fact(intent_path,1024**2,deadline)
    o.check(o.read_checked(intent_path,files[intent_path]['signature9'],1024**2,deadline)==o.compact(intent),'existing-preparation-original-intent')
    attrs={source:source_attrs};custodians={}
    for name,key in (('original.arc','original'),('restored-original.arc','restore')):
        path=stage/name;value=o.fact(path,512*1024**2,deadline);files[path]=value;attrs[path]=o.attributes(path)
        o.check(value['sha256']==source_fact['sha256'] and attrs[path]==source_attrs,'existing-preparation-independent-custody')
        custodians[key]=value
    path=stage/'prepared.cbz';derivative=o.fact(path,MAX,deadline);files[path]=derivative
    staged=o.read_checked(path,derivative['signature9'],MAX,deadline)
    o.check(staged==repaired,'existing-preparation-recomputed-stage')
    inventory,metadata_hash=modules[5].independent(staged,g,deadline)
    o.check(inventory==plan['inventory'] and metadata_hash==plan['root_metadata_sha256'],'existing-preparation-independent-stage')
    expected=dict(version=1,kind='owned-archive-repair-preparation',implementation=files[Path(o.__file__)],owner=owner,census=census,
        controls={str(p):files[p] for p in control},ancestors={str(p):v for p,v in original_nodes.items()},claims={str(p):v for p,v in claims.items()},
        catalog=catalog,policy=policy,writer_identity=identity,source=source_fact,source_attributes=source_attrs,exceptional_witness=witness,
        derivative=derivative,preservation=evidence,operation_id=operation_id,custody=custodians,executable=False,native_grant=False,
        mutation_authority=False,adoption_authority=False,ordinary_source_admission=False,publication_acceptance=False,reader_preservation_verified=False)
    expected['token']=o.digest(expected)
    # Canonical bytes also reject Boolean/numeric aliases and unknown keys.
    o.check(type(body) is dict and o.compact(body)==o.compact(expected),'existing-preparation-complete-original-metadata')
    o.check(raw_metadata==o.compact(expected),'existing-preparation-intended-metadata-bytes')
    files[metadata]=metadata_fact;files[implementation]=factory_original
    for path,value in dependency_originals.items():
        o.check(path not in files or files[path]==value,'existing-preparation-source-conflict');files[path]=value
    o.merge_nodes(nodes,original_nodes)
    # Freeze the original complete tuples before every constructor/revalidation
    # callback, including custody proof sources, original absences and claims.
    combined={p:tuple(value) for p,value in parent_files.items()}
    for path,value in files.items():
        fact=tuple(value['signature9']);o.check(path not in combined or combined[path]==fact,'existing-preparation-file-conflict');combined[path]=fact
    combined[stage]=tuple(directory)
    file_items=tuple((str(p),value) for p,value in combined.items());node_items=tuple((str(p),tuple(v)) for p,v in nodes.items())
    claim_items=tuple((str(p),None if v is None else tuple(v)) for p,v in claims.items())
    absent=tuple(str(p) for p in parent_absent)+tuple(str(db)+suffix for db in (controller.database,controller.native_database) for suffix in ('-wal','-shm','-journal'))+tuple(str(writer.root/name) for name in PENDING)
    result=o.RepairPreparation(o._KEY,controller,writer,modules,files,attrs,nodes,claims,census,records,copy.deepcopy(expected),deadline,stage,directory)
    result.revalidate();custody.revalidate_stopped()
    if time.monotonic()>=deadline:raise o.Held('existing-preparation-final-deadline')
    if set(os.listdir(stage))!=NAMES:raise o.Held('existing-preparation-final-census')
    for path,value in file_items:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:raise o.Held('existing-preparation-final-file')
    for path,value in node_items:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise o.Held('existing-preparation-final-node')
    for path,value in claim_items:
        try:z=os.lstat(path)
        except FileNotFoundError:
            if value is not None:raise o.Held('existing-preparation-final-claim')
            continue
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,None if z.st_mode & 0o170000==0o040000 else z.st_nlink)!=value:raise o.Held('existing-preparation-final-claim')
    for path in absent:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise o.Held('existing-preparation-final-absence')
    return result
