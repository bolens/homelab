"""Deterministic configured overlays from this reviewed finite source graph.

This builds bytes only. It grants no lifecycle/SDK authority and does not write
or load modules. Base admission and provider defaults remain refusing.
"""
import ast
import hashlib
from pathlib import Path

EXPECTED={'admission': '2bdc483dec44c9f3296dd9b2d36d71c6fc8079d264c1b548682dfa0d6d9ac771', 'archive_action': '83432ab4e367e227668ceceb4caa87697397b9103b271a6a164b36cb24e3cf65', 'archive_adapter': '32cc523bba6c5d6233649c946199ddcac542852062ce7df22435bcc81e715d02', 'backup_action': 'b709a9613ded63e2b6a1e9efafde802ced6214852fc34b27b02badea7617d484', 'parent': '5e727425687c91fa16bf8a6b1a54a5427e1b90f6bb4f67995949ba7136e34e56', 'producer': '29c2808981512354af402c8b067d888220f27ed42ac6b920db9a42db624c94d4', 'projection': '343022f6cb9fb2ffb569077033fe03a5218bd6a40ea22cd532eb7d685d3d7646', 'worker_vectors': '3fa569e80a8812de545ef71c31ea81f12518fb31454a5249f2605d099dd310d2', 'reader_backup': 'f165a0cb5834dc62f400d6dbe9e4070310823f28ec4bc1c4ecb12ae250503be3', 'backup_primitives': 'e21c79487e255a47d2099ee053678cbf874b1e2827087468041fc97c566c98a0', 'reader_schema': 'e711b3f4d3ec4b909ca4038f803ce0829950c28eb50623b8282901be3e21f7e7', 'native_scope': '4214f649b4f5d45377d6336d1e306753f869d33a77dd8a4b110c129793761770', 'native_probe': '86d3d10f84b5b71b8905db9ea911f7529ce6d3c7529f88bb0506c051a4906407'}
EXPECTED_NFS={'comic_nfs_host_engine.py': 'f844875b212d86063327091cf262a047d4e7d8d84eb65b697174857a297dfb89', 'comic_nfs_host_lease.py': '25d479d74dd343caa34e3481ea59b42bf42cb2e952cb5fa87c4ba66dbee551bb', 'comic_nfs_lease_session.py': '0c7fca1e79cde9881eff8ded3ffab9e4513e517ec120c5689667b68df08383ba', 'comic_nfs_host_probe.py': 'e54fd98f806575fc1443f9c6c1def31ecb8402fd2029f4b36ebb2a02e8ff4882', 'comic_nfs_uid_child.py': 'fc31ad1ce7bef468a838d265833e3869ebc592561907b7994610a4ad2e497550', 'comic_nfs_parent_session.py': 'ceb70bbfec9bb844c5b056672a709b7cfc9c9d786ccbc6399feefbc19a7f5996', 'comic_nfs_child_input_projection.py': '0ac693f437fe3940f99b8ad8276a069b9647ec42abe435c346fa91e55a5fcd02', 'comic_negative_nfs_active_lifecycle.py': '2bb4985f72fc4b270ab551d35cb921a00990397dd6662e6a54668d0825423f21', 'comic_negative_nfs_active_parent.py': 'f175f7f7340a3854dbe42fffd8f593be1f4450e205a2fae2f47e442f9028bdb3', 'comic_nfs_factual_successor.py': 'fb941ca03e9a7b2df23fa70d51ca1c98a4d2cfa3e20f58a66ba46cf333e9cfb5'}
WORKER_OBSERVER_SOURCE_SHA = 'ede41d9758cb09696e1fdd6faa600363d4b24a53e36e8f0a5999ff5672bd4862'
CHILD_OPERATION = Path('/_operation')
BASE_SOURCE_MANIFEST_SHA='7e06e47429389a0e61e4efca545229c06f1ca15db3ae2d591ae129edf3bd7768'
class Held(ValueError):pass

def need(ok,reason):
    if not ok:raise Held(reason)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def assignments(raw, edits):
    text=raw.decode('utf-8');tree=ast.parse(text,feature_version=(3,10));lines=text.splitlines(keepends=True);spans=[]
    for name,value in edits.items():
        nodes=[n for n in tree.body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id==name]
        need(len(nodes)==1 and nodes[0].lineno==nodes[0].end_lineno,'configured-unique-assignment')
        n=nodes[0];spans.append((n.lineno-1,n.col_offset,n.end_col_offset,value))
    for index,start,end,value in sorted(spans,reverse=True):lines[index]=lines[index][:start]+value+lines[index][end:]
    result=''.join(lines).encode();changed=ast.parse(result,feature_version=(3,10))
    stripped=lambda t:ast.dump(ast.Module(body=[n for n in t.body if not (isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in edits)],type_ignores=[]),include_attributes=False)
    need(stripped(tree)==stripped(changed),'configured-body-unchanged')
    return result

def worker_profile(value):
    import copy
    import re
    need(type(value) is dict and set(value)=={'mode','source','image_sources','image_metadata'}
         and value['mode']=='original-pipes-v1','configured-worker-finite-profile')
    for name in ('source','image_sources','image_metadata'):
        ref=value[name]
        need(type(ref) is dict and set(ref)=={'path','sha256','signature9'}
             and type(ref['path']) is str and Path(ref['path']).is_absolute()
             and all(x not in ('','.','..') for x in ref['path'].split('/')[1:])
             and type(ref['sha256']) is str and re.fullmatch('[a-f0-9]{64}',ref['sha256'])
             and type(ref['signature9']) in (list,tuple) and len(ref['signature9'])==9
             and all(type(x) is int for x in ref['signature9']),'configured-worker-original-ref')
    need(value['source']['sha256']==WORKER_OBSERVER_SOURCE_SHA,'configured-worker-reviewed-source')
    return copy.deepcopy(value)


def worker_original_inputs(profile):
    """Finite three private originals; no daemon query or installed parity grant."""
    import json
    import os
    import stat
    profile=worker_profile(profile)
    rows=[];nodes={};payload={}
    vector=lambda z:(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
    node=lambda z:(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
    for role in ('source','image_sources','image_metadata'):
        path=Path(profile[role]['path'])
        for parent in path.parents:
            z=os.lstat(parent);need(stat.S_ISDIR(z.st_mode),'configured-worker-original-node-type')
            need(nodes.setdefault(str(parent),node(z))==node(z),'configured-worker-original-node')
    for role in ('source','image_sources','image_metadata'):
        ref=profile[role];path=Path(ref['path']);expected=tuple(ref['signature9'])
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            value=vector(os.fstat(fd))
            need(value==expected and vector(os.lstat(path))==expected and stat.S_ISREG(value[5])
                 and stat.S_IMODE(value[5])==0o600 and value[6]==os.geteuid() and value[8]==1
                 and 0<value[2]<=1024**2,'configured-worker-original9')
            raw=b''
            while len(raw)<value[2]:
                part=os.read(fd,min(65536,value[2]-len(raw)));need(bool(part),'configured-worker-original-length');raw+=part
            need(sha(raw)==ref['sha256'] and vector(os.fstat(fd))==value and vector(os.lstat(path))==value,
                 'configured-worker-original-hash')
            rows.append((str(path),value));payload[role]=raw
        finally:os.close(fd)
    def unique(items):
        result={}
        for key,value in items:need(key not in result,'configured-worker-original-duplicate');result[key]=value
        return result
    need(json.loads(payload['image_sources'],object_pairs_hook=unique)=={'/app/archive_terminal_observation.py':WORKER_OBSERVER_SOURCE_SHA},
         'configured-worker-exact-image-sources')
    metadata=json.loads(payload['image_metadata'],object_pairs_hook=unique)
    need(type(metadata) is list and len(metadata)==1 and type(metadata[0]) is dict
         and type(metadata[0].get('Id')) is str and metadata[0].get('Os')=='linux'
         and metadata[0].get('Architecture')=='amd64','configured-worker-original-image-metadata')
    import re
    need(re.fullmatch('sha256:[a-f0-9]{64}',metadata[0]['Id']) is not None,'configured-worker-original-image-id')
    for path,value in nodes.items():
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise Held('configured-worker-original-node-final')
    for path,value in rows:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:raise Held('configured-worker-original9-final')
    return metadata[0]['Id'],rows,nodes


def build(sources, parent_original_path, *, worker_observation=None, worker_image=None):
    need(type(sources) is dict and set(sources)==set(EXPECTED),'configured-source-roles')
    for name,raw in sources.items():need(type(raw) is bytes and sha(raw)==EXPECTED[name],'configured-reviewed-source-pin')
    need(type(parent_original_path) is str and Path(parent_original_path).is_absolute() and all(x not in ('','.','..') for x in parent_original_path.split('/')[1:]) and Path(parent_original_path).name=='comic_reader_lifecycle_parent.py','configured-parent-original-path')
    edits={'CHILD_CONTROL_PROJECTION_ENABLED':'CHILD_CONTROL_PROJECTION_ENABLED = True','CHILD_CONTROL_SOURCE_SHA':'CHILD_CONTROL_SOURCE_SHA = '+repr(EXPECTED['projection'])}
    need(worker_observation is not None or worker_image is None,'configured-worker-no-image-without-profile')
    if worker_observation is not None:
        profile=worker_profile(worker_observation)
        import re
        need(type(worker_image) is str and re.fullmatch('sha256:[a-f0-9]{64}',worker_image),'configured-worker-original-image-id')
        observation={key:profile[key] for key in ('mode','source','image_sources')}
        edits.update(WORKER_OBSERVATION_ENABLED='WORKER_OBSERVATION_ENABLED = True',
                     WORKER_OBSERVATION_ORIGINALS='WORKER_OBSERVATION_ORIGINALS = '+repr(observation),
                     WORKER_OBSERVATION_IMAGE='WORKER_OBSERVATION_IMAGE = '+repr(worker_image),
                     WORKER_OBSERVATION_IMAGE_ORIGINAL='WORKER_OBSERVATION_IMAGE_ORIGINAL = '+repr(profile['image_metadata']))
    parent=assignments(sources['parent'],edits)
    parent_sha=sha(parent)
    child_parent=str(CHILD_OPERATION/('control-'+sha(parent_original_path.encode())[:24])/Path(parent_original_path).name)
    admission=assignments(sources['admission'],{'PARENT_SOURCE':'PARENT_SOURCE = Path('+repr(child_parent)+')','PARENT_SHA':'PARENT_SHA = '+repr(parent_sha)})
    action=assignments(sources['archive_action'],{'PARENT_SOURCE_SHA':'PARENT_SOURCE_SHA='+repr(parent_sha)})
    pins=ast.literal_eval(next(n.value for n in ast.parse(sources['producer']).body if isinstance(n,ast.Assign) and getattr(n.targets[0],'id',None)=='PINS'));pins=dict(pins);pins['comic_archive_repair_action.py']=sha(action)
    producer=assignments(sources['producer'],{'PINS':'PINS='+repr(pins)})
    backup_source=sources['backup_action'].replace(EXPECTED['archive_action'].encode(),sha(action).encode()).replace(EXPECTED['producer'].encode(),sha(producer).encode())
    # The original backup producer loader names its exact historical preimage.
    backup_source=backup_source.replace(b'c75332b81a5cbb8bed3dd002b8a5a0e7a1fc85366782c128d987276fa23b411a',sha(producer).encode())
    backup=assignments(backup_source,{'PARENT_SOURCE_SHA':'PARENT_SOURCE_SHA='+repr(parent_sha)})
    adapter=assignments(sources['archive_adapter'],{'PRODUCER_SHA':'PRODUCER_SHA = '+repr(sha(producer)),'TERMINAL_PRODUCER_SHA':'TERMINAL_PRODUCER_SHA = '+repr(sha(producer)),'ACTION_SHA':'ACTION_SHA = '+repr(sha(action))})
    artifacts={'comic_reader_lifecycle_parent.py':parent,'comic_child_control_projection.py':sources['projection'],'publication_reader_admission.py':admission,'comic_archive_repair_action.py':action,'comic_archive_backup_action.py':backup,'comic_archive_proof_producer.py':producer,'comic_archive_evidence_adapter.py':adapter,'comic_archive_worker_vectors.py':sources['worker_vectors'],**{name:sources[role] for role,name in {'reader_backup':'comic_reader_backup.py','backup_primitives':'comic_reader_backup_primitives.py','reader_schema':'comic_reader_schema.py','native_scope':'publication_native_configured_scope.py','native_probe':'comic_native_process_probe.py'}.items()}}
    return artifacts,dict(parent_sha256=parent_sha,child_parent_source=child_parent,base_sources=dict(EXPECTED),effective_sources={name:sha(raw) for name,raw in artifacts.items()},installation_authority=False,lifecycle_authority=False,base_image_parity=False)

def build_nfs(sources):
    """Finite host-only helpers; no SDK/cohort or installed-admission grant."""
    need(type(sources) is dict and set(sources)==set(EXPECTED_NFS),'configured-nfs-exact-source-roles')
    for name,raw in sources.items():need(type(raw) is bytes and sha(raw)==EXPECTED_NFS[name],'configured-nfs-reviewed-source-pin')
    return dict(sources)

def install(source_paths, output, *, sdk_ref=None, base_manifest_path=None, nfs_source_paths=None, worker_observation=None):
    """Create one exclusive root-private configured artifact set; never deploy.

    Root caller supplies reviewed public source paths, not digests or code edits.
    This does not replace installed files. Canonical admission overlay is a
    separate own UID1000 leaf; Parent and provider originals remain root600.
    """
    import json
    import os
    import stat
    need(os.geteuid()==0,'configured-install-root-required')
    need(type(source_paths) is dict and set(source_paths)==set(EXPECTED),'configured-install-source-roles')
    need(type(sdk_ref) is dict and set(sdk_ref)=={'path','sha256','signature9'} and type(sdk_ref['signature9']) in (list,tuple) and len(sdk_ref['signature9'])==9 and all(type(x) is int for x in sdk_ref['signature9']) and base_manifest_path is not None,'configured-install-original-maps-required')
    import copy
    original_worker=worker_observation
    worker_tape=None if worker_observation is None else json.dumps(worker_observation,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
    worker_observation=None if worker_tape is None else worker_profile(json.loads(worker_tape))
    original_paths=source_paths;original_sdk=sdk_ref
    original_nfs=nfs_source_paths
    need(nfs_source_paths is None or type(nfs_source_paths) is dict and set(nfs_source_paths)==set(EXPECTED_NFS),'configured-install-exact-nfs-roles')
    nfs_tape=None if nfs_source_paths is None else tuple(sorted(nfs_source_paths.items()))
    if nfs_tape is not None:need(all(type(k) is str and type(v) is str for k,v in nfs_tape),'configured-install-nfs-path-types')
    paths_tape=tuple(sorted(source_paths.items()));sdk_tape=(sdk_ref['path'],sdk_ref['sha256'],tuple(sdk_ref['signature9']))
    need(all(type(k) is str and type(v) is str for k,v in paths_tape) and type(sdk_tape[0]) is str and type(sdk_tape[1]) is str,'configured-install-original-input-types')
    source_paths=dict(paths_tape)
    combined_paths=dict(source_paths)
    if nfs_tape is not None:combined_paths.update(dict(nfs_tape))
    expected_pins={**EXPECTED,**(EXPECTED_NFS if nfs_tape is not None else {})}
    sdk_ref={'path':sdk_tape[0],'sha256':sdk_tape[1],'signature9':sdk_tape[2]}
    output=Path(output)
    need(output.is_absolute() and all(x not in ('','.','..') for x in str(output).split('/')[1:]),'configured-install-output')
    vector=lambda z:(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
    node=lambda z:(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
    files=[];nodes={};fds=[];sources={};created=[]
    for path in [output,Path(sdk_ref['path']),Path(base_manifest_path),*map(Path,combined_paths.values()),*([Path(worker_observation[k]['path']) for k in ('source','image_sources','image_metadata')] if worker_observation is not None else [])]:
        need(path.is_absolute() and all(x not in ('','.','..') for x in str(path).split('/')[1:]),'configured-install-canonical')
        for parent in path.parents:
            z=os.lstat(parent);need(stat.S_ISDIR(z.st_mode),'configured-install-ancestor')
            previous=nodes.setdefault(str(parent),node(z));need(previous==node(z),'configured-install-original-ancestor')
    try:
        for role,value in combined_paths.items():
            path=Path(value);old=vector(os.lstat(path));need(stat.S_ISREG(old[5]) and old[8]==1 and 0<old[2]<=1024**2,'configured-install-source-bound')
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC);fds.append(fd);need(vector(os.fstat(fd))==old,'configured-install-source-FD')
            chunks=[];remaining=old[2]
            while remaining:
                piece=os.read(fd,min(remaining,65536));need(bool(piece),'configured-install-source-length');chunks.append(piece);remaining-=len(piece)
            raw=b''.join(chunks);need(sha(raw)==expected_pins[role] and vector(os.fstat(fd))==old and vector(os.lstat(path))==old,'configured-install-reviewed-original')
            sources[role]=raw;files.append((str(path),old))
        map_bytes={}
        for role,path,expected_hash,expected9 in (('sdk',Path(sdk_ref['path']),sdk_ref['sha256'],tuple(sdk_ref['signature9'])),('base',Path(base_manifest_path),BASE_SOURCE_MANIFEST_SHA,None)):
            old=vector(os.lstat(path));need(stat.S_ISREG(old[5]) and old[8]==1 and 0<old[2]<=1024**2 and (expected9 is None or old==expected9),'configured-install-map-original9')
            if role=='sdk':need(stat.S_IMODE(old[5])==0o600 and old[6]==0,'configured-install-map-private')
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC);fds.append(fd);need(vector(os.fstat(fd))==old,'configured-install-map-FD')
            raw=b'';remaining=old[2]
            while remaining:
                part=os.read(fd,min(remaining,65536));need(bool(part),'configured-install-map-length');raw+=part;remaining-=len(part)
            need(sha(raw)==expected_hash and vector(os.fstat(fd))==old and vector(os.lstat(path))==old,'configured-install-map-pin');files.append((str(path),old));map_bytes[role]=raw
        def unique(rows):
            result={}
            for key,value in rows:need(key not in result,'configured-install-map-duplicate');result[key]=value
            return result
        if worker_observation is not None:
            worker_image,worker_rows,worker_nodes=worker_original_inputs(worker_observation)
            files.extend(worker_rows)
            for path,value in worker_nodes.items():
                need(path not in nodes or nodes[path]==value,'configured-worker-install-node-conflict');nodes[path]=value
        else:worker_image=None
        base_sdk=json.loads(map_bytes['sdk'],object_pairs_hook=unique)
        artifacts,receipt=build({role:sources[role] for role in EXPECTED},str(output/'comic_reader_lifecycle_parent.py'),worker_observation=worker_observation,worker_image=worker_image)
        sdk,cohort=configured_maps(base_sdk,map_bytes['base'],artifacts,receipt)
        output.mkdir(mode=0o700);rootfd=os.open(output,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC);fds.append(rootfd)
        birth=node(os.fstat(rootfd));need(stat.S_ISDIR(birth[2]) and stat.S_IMODE(birth[2])==0o700 and birth[3:]==(0,os.getegid()) and node(os.lstat(output))==birth,'configured-install-root-creator');nodes[str(output)]=birth
        # Overlay leaf is independently child-readable; root originals never chowned.
        overlay='publication_reader_admission.overlay.py'
        blobs={**artifacts,overlay:artifacts['publication_reader_admission.py'],'configured-sdk-map.json':(json.dumps(sdk,sort_keys=True,indent=2)+'\n').encode(),'configured-cohort.json':(json.dumps(cohort,sort_keys=True,indent=2)+'\n').encode()}
        if nfs_tape is not None:
            blobs.update(build_nfs({name:sources[name] for name in EXPECTED_NFS}))
            receipt['nfs_host_only_sources']={name:EXPECTED_NFS[name] for name in EXPECTED_NFS}
            receipt['nfs_session_admission_proven']=False
        if worker_observation is not None:
            receipt['worker_observation_profile']=copy.deepcopy(worker_observation)
            receipt['worker_observation_image']=worker_image
            receipt['worker_observation_installed_parity_verified']=False
        receipt['readonly_overlay']={'source':str(output/overlay),'destination':'/app/mylar3/mylar/publication_reader_admission.py','uid':1000,'gid':1000,'mode':'0600','sha256':sha(blobs[overlay])}
        receipt['base_sdk_ref']={'path':sdk_ref['path'],'sha256':sdk_ref['sha256'],'signature9':list(sdk_ref['signature9'])}
        receipt['effective_sdk_map_sha256']=sha(blobs['configured-sdk-map.json']);receipt['effective_cohort_sha256']=sha(blobs['configured-cohort.json']);receipt['actual_overlay_origins_verified']=False
        receipt['original_source_refs']={role:{'path':combined_paths[role],'sha256':expected_pins[role],'signature9':list(next(v for p,v in files if p==combined_paths[role]))} for role in combined_paths}
        blobs['configured-source-observation.json']=(json.dumps(receipt,sort_keys=True,indent=2)+'\n').encode()
        for name,raw in blobs.items():
            fd=os.open(name,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=rootfd);fds.append(fd);before=vector(os.fstat(fd))
            need(stat.S_ISREG(before[5]) and stat.S_IMODE(before[5])==0o600 and before[6:]==(0,os.getegid(),1),'configured-install-file-creator')
            view=memoryview(raw)
            while view:
                size=os.write(fd,view);need(size>0,'configured-install-write');view=view[size:]
            if name==overlay:os.fchown(fd,1000,1000)
            os.fsync(fd);current=vector(os.fstat(fd));owner=(1000,1000) if name==overlay else (0,os.getegid())
            need(current[:2]==before[:2] and current[2]==len(raw) and current[5]==before[5] and current[6:]==(*owner,1),'configured-install-own-transition')
            os.lseek(fd,0,0);need(os.read(fd,len(raw)+1)==raw and vector(os.fstat(fd))==current and vector(os.stat(name,dir_fd=rootfd,follow_symlinks=False))==current,'configured-install-exact-readback')
            created.append((str(output/name),current))
        os.fsync(rootfd);result={'output':str(output),'prepared':True,'lifecycle_performed':False,'configured_admission_proven':False}
        # Return original producer incarnations for the immediate runtime consumer;
        # a consumer must not adopt freshly observed output metadata instead.
        result['root_signature5']=list(birth)
        result['output_refs']={path:{'path':path,'sha256':sha(blobs[Path(path).name]),'signature9':list(stamp)} for path,stamp in created}
    finally:
        for fd in reversed(fds):os.close(fd)
    # All serializers, writes, chown/fsync, callbacks and FD cleanup are finished.
    if worker_tape is not None and json.dumps(original_worker,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)!=worker_tape:raise Held('configured-worker-original-input-final')
    if nfs_tape is not None and tuple(sorted(original_nfs.items()))!=nfs_tape:raise Held('configured-install-original-nfs-inputs-final')
    if tuple(sorted(original_paths.items()))!=paths_tape or (original_sdk['path'],original_sdk['sha256'],tuple(original_sdk['signature9']))!=sdk_tape:raise Held('configured-install-original-inputs-final')
    if tuple(sorted(os.listdir(output)))!=tuple(sorted(blobs)):raise Held('configured-install-output-namespace')
    for path,expected in nodes.items():
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=expected:raise Held('configured-install-final5')
    for path,expected in (*files,*created):
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=expected:raise Held('configured-install-final9')
    return result


def configured_maps(base_sdk, base_manifest, artifacts, receipt):
    """Derive only admission's configured hash; never admit an unknown SDK leaf.

    The caller must independently prove original base image/source map and
    effective overlay origins. This pure map derivation grants no admission.
    """
    import json
    need(type(base_manifest) is bytes and sha(base_manifest)==BASE_SOURCE_MANIFEST_SHA,'configured-base-source-manifest')
    base=json.loads(base_manifest);known=base['base_installed_sources'];required=set(base['required_sdk_names'])
    need(type(base_sdk) is dict and required<=set(base_sdk) and set(base_sdk)<=set(known),'configured-complete-known-sdk')
    need(all(type(name) is str and type(value) is str and known[name]==value for name,value in base_sdk.items()),'configured-base-sdk-pins')
    need(set(artifacts)=={'comic_reader_lifecycle_parent.py','comic_child_control_projection.py','publication_reader_admission.py','comic_archive_repair_action.py','comic_archive_backup_action.py','comic_archive_proof_producer.py','comic_archive_evidence_adapter.py','comic_archive_worker_vectors.py','comic_reader_backup.py','comic_reader_backup_primitives.py','comic_reader_schema.py','publication_native_configured_scope.py','comic_native_process_probe.py'} and receipt['effective_sources']=={name:sha(raw) for name,raw in artifacts.items()} and receipt['parent_sha256']==sha(artifacts['comic_reader_lifecycle_parent.py']),'configured-derived-artifact-joins')
    sdk=dict(base_sdk);sdk['publication_reader_admission.py']=sha(artifacts['publication_reader_admission.py'])
    cohort=json.loads(json.dumps(base['base_cohort']));cohort['parent_sha256']=receipt['parent_sha256'];cohort['modules']['publication_reader_admission']['sha256']=sdk['publication_reader_admission.py']
    need(cohort['runtime_acceptance'] is False and cohort['publication_acceptance'] is False,'configured-cohort-no-runtime-grant')
    return sdk,cohort
