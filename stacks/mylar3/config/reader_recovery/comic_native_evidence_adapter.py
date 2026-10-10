"""Fresh native evidence adapter; engine access stays in the owning host parent."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import time
import types

PROBE_SHA = '77325f0a7fd14b6e2e1a1f91aaf4c66cb53b5e2fd4cffdd34453642002afd1ec'
SCOPE_SHA = '6d4b43c84a653aa56cbf22e25563b26e4cb8a5c700cce5d8a124612be3818608'
PRODUCER_SHA = '3d5e8eab3618a9aa24bb148579f240b000b6bdbf526fbeb01acf0672cef4efab'
TERMINAL_PRODUCER_SHA = '00d3e0b2df9c0a2af3145761a8e3d44cacfd3ce7b16f14caf05eae6eb9ff07dc'
MAX = 1024*1024
class Held(ValueError): pass

def need(value, reason):
    if not value: raise Held(reason)

def nine(z): return (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
def five(z): return (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
def encode(value): return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def decode(raw):
    def unique(items):
        value = {}
        for key,item in items:
            need(key not in value,'adapter-duplicate'); value[key]=item
        return value
    return json.loads(raw,object_pairs_hook=unique)

class Reads:
    def __init__(self): self.files={}; self.nodes={}
    def raw(self,path):
        path=Path(path); need(path.is_absolute() and '..' not in path.parts,'adapter-path')
        for p in reversed(path.parents):
            z=os.lstat(p); need(stat.S_ISDIR(z.st_mode),'adapter-parent-type')
            old=self.nodes.setdefault(str(p),five(z)); need(old==five(z),'adapter-parent-CAS')
        z=os.lstat(path); stamp=nine(z)
        need(stat.S_ISREG(z.st_mode) and z.st_nlink==1 and z.st_size<=MAX,'adapter-file')
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            need(nine(os.fstat(fd))==stamp,'adapter-FD-CAS'); raw=bytearray()
            while len(raw)<=MAX:
                part=os.read(fd,min(65536,MAX+1-len(raw)))
                if not part: break
                raw.extend(part)
            need(len(raw)==z.st_size and nine(os.fstat(fd))==stamp,'adapter-read-CAS')
        finally:os.close(fd)
        old=self.files.setdefault(str(path),stamp);need(old==stamp and nine(os.lstat(path))==stamp,'adapter-path-CAS');return bytes(raw)
    def ref(self,ref,json_value=True):
        need(type(ref) is dict and set(ref)=={'path','sha256','signature9'},'adapter-ref')
        raw=self.raw(ref['path']);need(self.files[ref['path']]==tuple(ref['signature9']) and hashlib.sha256(raw).hexdigest()==ref['sha256'],'adapter-ref-CAS')
        return decode(raw) if json_value else raw
    def module(self,name,pin):
        path=Path(__file__).with_name(name);raw=self.raw(path);need(hashlib.sha256(raw).hexdigest()==pin,'adapter-module-pin')
        spec=importlib.util.spec_from_file_location('native_checked_'+name.replace('.','_'),path);module=importlib.util.module_from_spec(spec);exec(compile(raw,str(path),'exec'),module.__dict__);return module

def deadline(request):
    remaining=request['deadline_monotonic']-time.monotonic();need(0<remaining<=3600,'adapter-expired');return remaining

# This function has the only additional engine verb: read-only exec of the
# exact verified buffer on one original native ID. No shell/key in argv.
def probe_exec(container,source,request,seconds):
    need(type(container) is str and len(container)==64 and all(x in '0123456789abcdef' for x in container),'adapter-native-ID')
    args=['pkexec','/usr/bin/docker','--host','unix:///run/docker.sock','exec','--user','1000:1000','-i',container,
          '/lsiopy/bin/python3','-I','-B','-c',source.decode('utf-8')]
    try: result=subprocess.run(args,input=encode(request),capture_output=True,timeout=seconds,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
    except (OSError,subprocess.TimeoutExpired):raise Held('adapter-native-probe-unavailable') from None
    need(result.returncode==0 and len(result.stdout)<=MAX and len(result.stderr)<=MAX,'adapter-native-probe-held')
    return decode(result.stdout)

def context(request,watch):
    need(callable(watch) and getattr(watch,'__self__',None) is not None and watch.__func__.__name__=='continuous'
         and str(Path(watch.__func__.__code__.co_filename).absolute())==request['parent_source']['path'],'adapter-owning-watch')
    o=Reads();plan=o.ref(request['parent_plan']);o.ref(request['parent_source'],False)
    need(plan['nonce']==request['nonce'] and plan['operation']==request['operation'],'adapter-parent-binding')
    own=o.raw(Path(__file__).absolute());need(hashlib.sha256(own).hexdigest()==plan['producer']['sha256'],'adapter-own-source')
    scope=o.module('publication_native_configured_scope.py',SCOPE_SHA)
    sdk=o.ref(plan['sdk_map']);need(sdk.get('publication_native_configured_scope.py')==SCOPE_SHA,'adapter-scope-SDK')
    source=o.raw(Path(__file__).with_name('comic_native_process_probe.py'));need(hashlib.sha256(source).hexdigest()==PROBE_SHA,'adapter-probe-pin')
    return o,plan,scope,sdk,source

def native_observation(request,*,watch):
    o,plan,scope,sdk,source=context(request,watch);ctx=request['context']
    need(set(ctx)=={'observations','child','child_mounts'},'adapter-native-context')
    expected=copy.deepcopy(ctx);initial=copy.deepcopy(watch());same=watch.__func__.__globals__.get('same_runtime');need(callable(same),'adapter-parent-runtime-projection-required')
    need(set(initial)==set(expected['observations']) and all(same(initial[k],expected['observations'][k]) for k in initial),'adapter-fresh-original-inspects')
    pins={}
    for name in ('worker_health.py','native_writers.py'):
        digest=sdk.get(name);need(type(digest) is str and len(digest)==64,'adapter-daemon-source-pin-required');pins['/app/mylar3/mylar/'+name]=digest
    native=initial['held_native'];worker=initial['held_worker'];child=expected['child'];owner=watch.__self__
    scope.observed_worker(worker);need(same(owner.inspect(child['Id']),child) and child['Image']==plan['selected_image'],'adapter-selected-child')
    query=dict(version=1,nonce=request['nonce'],source_sha256=PROBE_SHA,seconds=max(1,min(120,int(deadline(request)))),module_pins=pins,scope_source=o.raw(Path(__file__).with_name('publication_native_configured_scope.py')).decode())
    response=probe_exec(native['Id'],source,query,deadline(request))
    need(type(response) is dict and set(response)=={'version','nonce','source_sha256','process','publication','config'}
         and type(response['version']) is int and response['version']==1 and response['nonce']==request['nonce'] and response['source_sha256']==PROBE_SHA,'adapter-native-response')
    value=dict(inspect=native,process=response['process'],publication=response['publication']);scope.observed_native(value)
    data=scope.data_from_argv(response['process']['argv']);need(response['config']['path']==data+'/config.ini','adapter-config-launch')
    # Host config bytes are independently bound to daemon probe digest; its CHILD
    # dev/inode facts are never compared with or relabelled as host signatures.
    host=scope.projection(native['Mounts'],response['config']['path']);config=o.raw(host)
    need(hashlib.sha256(config).hexdigest()==response['config']['sha256'],'adapter-config-host-child-hash')
    library=scope.destination(config);native_host=scope.projection(native['Mounts'],library)
    need(type(plan['native']['roots']) is list and len(plan['native']['roots'])==1,'adapter-single-configured-library-required')
    need(scope.projection(worker['Mounts'],plan['native']['roots'][0])==native_host,'adapter-worker-library')
    need(scope.projection(child['Mounts'],library)==native_host and scope.projection(child['Mounts'],response['config']['path'])==host,'adapter-child-native-host-geometry')
    need(expected['child_mounts']==child['Mounts'],'adapter-child-mounts')
    files=tuple((p,tuple(v)) for p,v in o.files.items());nodes=tuple((p,tuple(v)) for p,v in o.nodes.items())
    last=copy.deepcopy(watch());need(set(last)==set(initial) and all(same(last[k],initial[k]) for k in initial) and same(owner.inspect(child['Id']),child),'adapter-final-runtime')
    value['inspect']=last['held_native'];result=copy.deepcopy(dict(native=value,worker=last['held_worker'],child_mounts=child['Mounts']));deadline(request)
    for path,value in nodes:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise Held('adapter-final-parent')
    for path,value in files:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:raise Held('adapter-final-file')
    return result

def current_observations(watch, expected, reason):
    # Only the exact already-source-bound parent projection may normalize Health.
    same=watch.__func__.__globals__.get('same_runtime')
    need(callable(same),'adapter-parent-runtime-projection-required')
    actual=watch()
    need(type(actual) is dict and set(actual)==set(expected)
         and all(same(actual[k],expected[k]) for k in expected),reason)

def worker_library_destination(scope, mounts, physical):
    # Inverse the unique most-specific bind Source; then re-project Destination
    # to reject nested bind/volume shadows and duplicate destination geometry.
    physical=scope.absolute(physical);candidates=[]
    need(type(mounts) is list and len(mounts)<=64,'custody-worker-mount-bound')
    for row in mounts:
        need(type(row) is dict,'custody-worker-mount-row')
        if row.get('Type')!='bind':continue
        source=scope.absolute(row.get('Source'));destination=scope.absolute(row.get('Destination'))
        if physical==source or source in physical.parents:
            candidates.append((len(source.parts),destination/physical.relative_to(source)))
    need(bool(candidates),'custody-worker-library-unmapped')
    maximum=max(depth for depth,_ in candidates)
    selected=[path for depth,path in candidates if depth==maximum]
    need(len(selected)==1,'custody-worker-library-ambiguous')
    result=str(selected[0])
    need(scope.projection(mounts,result)==str(physical),'custody-worker-library-shadow')
    return result

def reader_pair_birth_request(request,*,watch):
    """Factual seedversion2 pair descriptors; never HOST incarnation as CHILD9.

    These descriptors never assert a CHILD incarnation. Phase-custody proposes
    unchanged original signatures; the actual child lifecycle must compare its
    own kernel values, and holds on any mismatch.
    """
    o,plan,scope,sdk,source=context(request,watch);ctx=request['context']
    need(set(ctx)=={'backup','controls','observations','phase','invocation','stage'}
         and ctx['stage']=='prebirth' and ctx['phase'] in ('prepare','execute'),'adapter-prebirth-context')
    expected=copy.deepcopy(ctx);current_observations(watch,expected['observations'],'adapter-prebirth-runtime')
    roles={'stopped_runtime','backup_ack','backup_manifest','backup_acceptance','rows','schema','reviewed_plan','timestamp_evidence','custody'}
    need(set(ctx['controls'])==roles,'adapter-prebirth-nine-roles')
    controls={name:o.ref(ref) for name,ref in ctx['controls'].items()}
    need(controls['stopped_runtime']['container']==expected['observations']['reader'],'adapter-prebirth-stopped')
    custody=controls['custody'];need(set(custody)=={'restore_root','pairs','reader_root','current_pairs'},'adapter-custody-schema')
    roots={'current':custody['reader_root'],'restore':custody['restore_root']};mapped={};pairs={};absent=[];budget=0;identities=set()
    need(five(os.lstat(roots['current']))[:2]!=five(os.lstat(roots['restore']))[:2],'adapter-independent-restore-identity')
    owner=watch.__self__
    for role,root in roots.items():
        mapped[role]=owner.mapping.child(root);pairs[role]={}
        need(set(custody['current_pairs' if role=='current' else 'pairs'])=={'database.sqlite','tasks.sqlite'},'adapter-pair-database-roles')
        for name in ('database.sqlite','tasks.sqlite'):
            supplied=custody['current_pairs' if role=='current' else 'pairs'][name]
            need('' in supplied and set(supplied)<= {'','-wal','-shm'} and ('-wal' in supplied)==('-shm' in supplied),'adapter-pair-coherence')
            pairs[role][name]={}
            for suffix in ('','-wal','-shm','-journal'):
                path=Path(root)/(name+suffix)
                for parent in path.parents:
                    z=os.lstat(parent);value=five(z);old=o.nodes.setdefault(str(parent),value);need(stat.S_ISDIR(z.st_mode) and old==value,'adapter-pair-parent')
                if suffix not in supplied:
                    try:os.lstat(path)
                    except FileNotFoundError:absent.append(str(path));pairs[role][name][suffix]=None;continue
                    raise Held('adapter-pair-absence')
                fact=supplied[suffix];stamp=tuple(fact['signature9']);need(len(stamp)==9 and 0<stamp[2]<=1024**3 and stamp[8]==1,'adapter-pair-bound')
                need(stamp[:2] not in identities,'adapter-independent-pair-identity');identities.add(stamp[:2])
                budget+=stamp[2];need(budget<=4*1024**3,'adapter-pair-total-bound');deadline(request)
                need(nine(os.lstat(path))==stamp and stat.S_ISREG(stamp[5]),'adapter-pair-original')
                fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW);h=hashlib.sha256();count=0
                try:
                    need(nine(os.fstat(fd))==stamp,'adapter-pair-FD')
                    while True:
                        part=os.read(fd,65536)
                        if not part:break
                        count+=len(part);need(count<=stamp[2],'adapter-pair-size');h.update(part);deadline(request)
                    need(count==stamp[2] and nine(os.fstat(fd))==stamp and h.hexdigest()==fact['sha256'],'adapter-pair-hash-CAS')
                finally:os.close(fd)
                old=o.files.setdefault(str(path),stamp);need(old==stamp,'adapter-pair-vector-conflict')
                pairs[role][name][suffix]=dict(sha256=h.hexdigest(),attributes=dict(size=stamp[2],mode=stamp[5],uid=stamp[6],gid=stamp[7],nlink=stamp[8]))
    need(roots['current']!=roots['restore'] and mapped['current']!=mapped['restore'],'adapter-pair-independent-roots')
    result=copy.deepcopy(dict(roots=mapped,pairs=pairs));files=tuple(o.files.items());nodes=tuple(o.nodes.items());missing=tuple(absent)
    current_observations(watch,expected['observations'],'adapter-prebirth-final-runtime');deadline(request)
    for path,value in nodes:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise Held('adapter-prebirth-final-parent')
    for path,value in files:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:raise Held('adapter-prebirth-final-file')
    for path in missing:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise Held('adapter-prebirth-final-absence')
    return result

def phase_custody(request, *, watch):
    """Prebirth proposals; actual child lifecycle must check every supplied9."""
    ctx=request['context']
    terminal=ctx.get('phase')=='verify-terminal'
    expected_keys={'backup','controls','observations','phase','invocation','stage'}|({'terminal_manifest','execute_ack'} if terminal else set())
    need(type(ctx) is dict and set(ctx)==expected_keys
         and ctx['phase'] in ('prepare','execute','verify-terminal') and ctx['stage']=='prebirth','custody-context')
    roles={'stopped_runtime','backup_ack','backup_manifest','backup_acceptance','rows','schema','reviewed_plan','timestamp_evidence','custody'}
    need(type(ctx['controls']) is dict and set(ctx['controls'])==roles,'custody-nine-roles')
    # Capture every declared role ancestor before any source/JSON/import callback.
    admission=Reads()
    need(type(ctx['backup']) is dict and 'restore_root' in ctx['backup'] and 'manifest' in ctx['backup'],'custody-original-backup')
    mounts=ctx['observations']['reader']['Mounts'];config_mounts=[m for m in mounts if m['Destination']=='/config']
    need(len(config_mounts)==1 and config_mounts[0]['Type']=='bind','custody-reader-config-mount')
    declared=[Path(ctx['backup']['restore_root']),Path(config_mounts[0]['Source']),Path(ctx['controls']['custody']['path']).parent/'scratch',Path(__file__).absolute()]
    for name in ('publication_native_configured_scope.py','comic_native_process_probe.py'):
        declared.append(Path(__file__).with_name(name))
    for row in ctx['observations'].values():
        declared.extend(Path(m['Source']) for m in row['Mounts'] if m['Type'] in ('bind','volume'))
    directory_originals={}
    for p in declared:
        if p in (Path(ctx['backup']['restore_root']),Path(config_mounts[0]['Source']),Path(ctx['controls']['custody']['path']).parent/'scratch'):
            z=os.lstat(p);need(stat.S_ISDIR(z.st_mode),'custody-initial-directory');directory_originals[str(p)]=nine(z)
        try:original=os.lstat(p)
        except OSError:raise Held('custody-declared-source-unavailable') from None
        for node in ([p,*p.parents] if stat.S_ISDIR(original.st_mode) else p.parents):
            z=os.lstat(node);need(stat.S_ISDIR(z.st_mode),'custody-declared-parent')
            old=admission.nodes.setdefault(str(node),five(z));need(old==five(z),'custody-declared-parent-CAS')
    for ref in [request['parent_plan'],request['parent_source'],*ctx['controls'].values(),*([ctx['terminal_manifest'],ctx['execute_ack']] if terminal else [])]:
        need(type(ref) is dict and set(ref)=={'path','sha256','signature9'},'custody-ref')
        p=Path(ref['path']);need(p.is_absolute() and '..' not in p.parts,'custody-path')
        for node in p.parents:
            z=os.lstat(node);need(stat.S_ISDIR(z.st_mode),'custody-parent')
            old=admission.nodes.setdefault(str(node),five(z));need(old==five(z),'custody-parent-CAS')
    o,plan,scope,sdk,_=context(request,watch)
    for path,value in admission.nodes.items():
        previous=o.nodes.setdefault(path,value);need(previous==value,'custody-admission-ancestor')
    owner=watch.__self__;mapping=owner.mapping;expected=copy.deepcopy(ctx)
    current_observations(watch,expected['observations'],'custody-stopped-current')
    controls={k:o.ref(v) for k,v in ctx['controls'].items()}
    stopped=controls['stopped_runtime'];runtime=expected['observations']['reader']
    need(set(stopped)=={'version','kind','nonce','observed','container'} and stopped['version']==1
         and stopped['kind']=='root-owned-reader-stopped-observation' and stopped['nonce']==request['nonce']
         and type(stopped['observed']) is int and 0<=time.time()-stopped['observed'] and (terminal or time.time()-stopped['observed']<=120)
         and stopped['container']==runtime,'custody-fresh-stop')
    state=runtime['State'];need(state['Status']=='exited' and state['Running'] is False and type(state['Pid']) is int and state['Pid']==0
         and all(state.get(k) is False for k in ('Paused','Restarting','Dead','OOMKilled')),'custody-stopped-state')
    ack=controls['backup_ack'];acceptance=controls['backup_acceptance'];manifest=controls['backup_manifest'];rows=controls['rows']
    need(ack.get('backup_verified') is True and ack.get('targeted_eleven_row_observation_verified') is True
         and all(ack.get(k) is False for k in ('repair_authority','mutation_authority','publication_acceptance','automatic_restart'))
         and ack['acceptance_sha256']==ctx['controls']['backup_acceptance']['sha256']
         and ack['backup_manifest_sha256']==ctx['controls']['backup_manifest']['sha256']
         and ack['rows_report_sha256']==ctx['controls']['rows']['sha256'],'custody-backup-joins')
    need(acceptance['kind']=='stopped-reader-full-backup-acceptance' and acceptance['backup_verified'] is False
         and acceptance['final_ack_required'] is True and acceptance['container_id']==runtime['Id']
         and acceptance['image']==runtime['Image'],'custody-backup-pending')
    need(manifest['kind']=='verified-reader-backup-copies' and manifest['source_sha256']=='f165a0cb5834dc62f400d6dbe9e4070310823f28ec4bc1c4ecb12ae250503be3'
         and manifest['primitives_sha256']=='e21c79487e255a47d2099ee053678cbf874b1e2827087468041fc97c566c98a0'
         and rows['kind']=='reader-restored-eleven-row-observation' and rows['source_sha256']=='ebac3228fa3c6055b86e3636fb33368f4ccf21950b452e7d6c10070af4a2c99a'
         and rows['backup_manifest_sha256']==ctx['controls']['backup_manifest']['sha256']
         and rows['schema_sha256']==ctx['controls']['schema']['sha256'],'custody-source-joins')
    need(controls['reviewed_plan']['timestamp_encoding_evidence_sha256']==ctx['controls']['timestamp_evidence']['sha256'],'custody-reviewed-timestamp')
    custody=controls['custody'];need(set(custody)=={'restore_root','pairs','reader_root','current_pairs'},'custody-pairs')
    # Immutable admitted primitive snapshots precede every copying/mapping
    # callback. Mutable decoded JSON is never a terminal physical baseline.
    terminal_originals=None
    terminal_pairs=None
    if terminal:
        module=o.module('comic_terminal_observation_producer.py',TERMINAL_PRODUCER_SHA)
        terminal_pairs,terminal_originals=module.current_pairs(request,watch=watch,adapter=types.SimpleNamespace(**globals()),reads=o,plan=plan)
    admitted_pairs=[]
    for role,key in (('current','current_pairs'),('restore','pairs')):
        pair=terminal_pairs if terminal and role=='current' else custody[key];need(set(pair)=={'database.sqlite','tasks.sqlite'},'custody-original-two-databases')
        databases=[]
        for name,facts in pair.items():
            need('' in facts and set(facts)<= {'','-wal','-shm'} and ('-wal' in facts)==('-shm' in facts),'custody-original-companions')
            leaves=[]
            for suffix,fact in facts.items():
                stamp=tuple(fact['signature9']);digest=fact['sha256']
                need(len(stamp)==9 and all(type(x) is int for x in stamp) and stat.S_ISREG(stamp[5]) and stamp[8]==1
                     and type(digest) is str and len(digest)==64,'custody-original-pair-fact')
                leaves.append((suffix,stamp,digest))
            databases.append((name,tuple(leaves)))
        admitted_pairs.append((role,tuple(databases)))
    admitted_pairs=tuple(admitted_pairs)
    original_pair_values={role:{name:{suffix:dict(signature9=list(stamp),sha256=digest) for suffix,stamp,digest in leaves}
                              for name,leaves in databases} for role,databases in admitted_pairs}
    roots=[Path(custody['reader_root']),Path(custody['restore_root'])]
    need(roots[0]==Path(config_mounts[0]['Source']) and roots[1]==Path(ctx['backup']['restore_root'])
         and ctx['backup']['manifest']['path']==ctx['controls']['backup_manifest']['path']
         and ctx['backup']['manifest']['sha256']==ctx['controls']['backup_manifest']['sha256'],'custody-original-backup-join')
    scratch=Path(ctx['controls']['custody']['path']).parent/'scratch'
    for root in [*roots,scratch]:
        for node in [root,*root.parents]:
            z=os.lstat(node);need(stat.S_ISDIR(z.st_mode),'custody-root-directory')
            old=o.nodes.setdefault(str(node),five(z));need(old==five(z),'custody-root-CAS')
    need(not roots[0].is_relative_to(roots[1]) and not roots[1].is_relative_to(roots[0])
         and all(not scratch.is_relative_to(r) and not r.is_relative_to(scratch) for r in roots)
         and stat.S_IMODE(os.lstat(scratch).st_mode)==0o700,'custody-disjoint-roots')
    # This rehashes actual SQLite files, with original full9 and missing companions.
    if not terminal:reader_pair_birth_request(request,watch=watch)
    # Preserve supplied signatures verbatim; child must actually compare its own
    # os.lstat values. No namespace assumption and no signature relabelling.
    inv=expected['invocation'];need(set(inv)=={'input_path','input_sha256','parent_sha256','provider_sha256','command','nonce'}
         and inv['nonce']==request['nonce'] and inv['parent_sha256']==request['parent_source']['sha256']
         and inv['provider_sha256']==plan['provider']['sha256'],'custody-invocation')
    input_host=mapping.host(inv['input_path']);raw=o.raw(input_host)
    need(hashlib.sha256(raw).hexdigest()==inv['input_sha256'],'custody-input-digest');value=decode(raw)
    command=['/lsiopy/bin/python3','-I','-B',mapping.child(plan['provider']['path']),'--phase',ctx['phase'],'--input',inv['input_path'],'--input-sha256',inv['input_sha256'],'--source-sha256',inv['provider_sha256']]
    need(inv['command']==command and value['command_template']==command[:9]+['<INPUT_SHA256>']+command[10:]
         and value['nonce']==request['nonce'] and value['parent_sha256']==inv['parent_sha256']
         and value['selected_image']==plan['selected_image'] and value['version']==1,'custody-exact-command')
    mapped_controls={name:dict(ref,path=mapping.child(ref['path'])) for name,ref in ctx['controls'].items()}
    need(value['controls']==mapped_controls,'custody-input-nine-role-join')
    if terminal:need(value.get('execute_ack')==dict(ctx['execute_ack'],path=mapping.child(ctx['execute_ack']['path'])),'custody-input-execute-ACK')
    if terminal:need(value.get('terminal_manifest')==dict(ctx['terminal_manifest'],path=mapping.child(ctx['terminal_manifest']['path'])),'custody-input-terminal-manifest')
    native=plan['native'];need(set(native)=={'data','roots'} and len(native['roots'])==1,'custody-native-scope')
    config_path=str(Path(native['data'])/'config.ini');config_host=scope.projection(expected['observations']['held_native']['Mounts'],config_path)
    need(mapping.child(config_host)==config_path,'custody-config-geometry');config=o.raw(config_host)
    library=scope.destination(config);need(library==native['roots'][0],'custody-config-library')
    physical=scope.projection(expected['observations']['held_native']['Mounts'],library)
    worker_library=worker_library_destination(scope,expected['observations']['held_worker']['Mounts'],physical)
    need(mapping.child(physical)==library,'custody-library-child-geometry')
    reader=dict(config_root=mapping.child(roots[0]),restore_root=mapping.child(roots[1]),scratch=mapping.child(scratch),
                backup_manifest=dict(ctx['controls']['backup_manifest'],path=mapping.child(ctx['controls']['backup_manifest']['path'])),
                backup_acceptance=dict(ctx['controls']['backup_acceptance'],path=mapping.child(ctx['controls']['backup_acceptance']['path'])),
                current_pairs=copy.deepcopy(original_pair_values['current']),restore_pairs=copy.deepcopy(original_pair_values['restore']),
                runtime=runtime,child_source_sha256=inv['provider_sha256'],child_image=plan['selected_image'])
    seed=dict(version=1,kind='selected-child-native-scope-birth',invocation=inv,
              parent_source=dict(request['parent_source'],path=mapping.child(request['parent_source']['path'])),
              birth_source=dict(path='/app/mylar3/mylar/publication_native_scope_birth.py',sha256=plan['birth_source_sha256']),
              config=dict(path=config_path,sha256=hashlib.sha256(config).hexdigest()),worker_library=worker_library,selected_image=plan['selected_image'])
    proofs=dict(ctx['controls'])
    if terminal:proofs.update(terminal_observation=ctx['terminal_manifest'],execute_ack=ctx['execute_ack'])
    result=copy.deepcopy(dict(reader=reader,proofs=proofs,birth_seed=seed))
    files=tuple(o.files.items())+tuple(directory_originals.items());nodes=tuple(o.nodes.items())
    # Carry the original pair signatures and absences through the very last
    # watch/mapping/deadline callback; never adopt callback-produced baselines.
    missing=[]
    for role,databases in admitted_pairs:
        root=roots[0] if role=='current' else roots[1]
        for name,leaves in databases:
            originals={suffix:stamp for suffix,stamp,digest in leaves}
            for suffix in ('','-wal','-shm','-journal'):
                path=str(root/(name+suffix))
                if suffix in originals:files+=((path,originals[suffix]),)
                else:missing.append(path)
    terminal_censuses=()
    if terminal:
        files+=tuple((str(p),tuple(v)) for p,v in terminal_originals['files'].items())
        nodes+=tuple((str(p),tuple(v)) for p,v in terminal_originals['nodes'].items())
        missing.extend(map(str,terminal_originals['absent']))
        terminal_censuses=tuple((str(p),frozenset(v)) for p,v in terminal_originals['censuses'].items())
    current_observations(watch,expected['observations'],'custody-final-runtime');deadline(request)
    for path,names in terminal_censuses:
        if frozenset(os.listdir(path))!=names:raise Held('custody-terminal-census')
    for path,stamp in nodes:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=stamp:raise Held('custody-final-node')
    for path,stamp in files:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:raise Held('custody-final-file')
    for path in missing:
        try:os.lstat(path)
        except FileNotFoundError:continue
        raise Held('custody-final-absence')
    return result

def terminal_observation(request,*,watch):
    o=Reads();module=o.module('comic_terminal_observation_producer.py',TERMINAL_PRODUCER_SHA)
    files=tuple(o.files.items());nodes=tuple(o.nodes.items())
    result=module.produce(request,watch=watch,adapter=types.SimpleNamespace(**globals()))
    for path,fact in nodes:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=fact:raise Held('terminal-loader-parent')
    for path,fact in files:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=fact:raise Held('terminal-loader-source')
    return result

def terminal_phase_custody(request,*,watch):
    need(request['context'].get('phase')=='verify-terminal','custody-terminal-only')
    return phase_custody(request,watch=watch)

def produce(phase,request,*,watch):
    need(type(request) is dict and set(request)=={'version','phase','nonce','operation','deadline_monotonic','parent_plan','parent_source','context'}
         and type(request['version']) is int and request['version']==1 and request['phase']==phase,'adapter-request');deadline(request)
    if phase=='native-observation':evidence=native_observation(request,watch=watch)
    elif phase=='backup-controls':
        o=Reads();module=o.module('comic_reader_proof_producer.py',PRODUCER_SHA);return module.produce(phase,request,watch=watch)
    elif phase=='terminal-observation':evidence=terminal_observation(request,watch=watch)
    elif phase=='phase-custody':
        evidence=terminal_phase_custody(request,watch=watch) if request['context'].get('phase')=='verify-terminal' else phase_custody(request,watch=watch)
    else:raise Held('adapter-owning-'+phase+'-required')
    return dict(version=1,phase=phase,nonce=request['nonce'],evidence=evidence)
