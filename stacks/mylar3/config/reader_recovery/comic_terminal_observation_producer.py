"""Source-bound factual terminal manifest; no capability reconstruction or replay."""
import hashlib
import json
import os
from pathlib import Path
import stat

OBSERVER_SHA = 'ec84afea896371e6c3e29c566a30613979561a63f53e924ff45c5def6a1d7c04'
ROLES = {'stopped_runtime','backup_ack','backup_manifest','backup_acceptance','rows','schema','reviewed_plan','timestamp_evidence','custody'}
class Held(ValueError): pass

def need(v, why):
    if not v: raise Held(why)


def merge(destination, values, reason):
    for path,value in values.items():
        path=str(path);value=tuple(value)
        old=destination.setdefault(path,value);need(old==value,reason)

def emit(path, value, nodes, names):
    """Exclusive dirFD output; intended bytes, original ancestor chain and census."""
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    need(len(raw)<=1024*1024,'terminal-output-bound');fds=[]
    try:
        d=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);fds.append(d)
        z=os.fstat(d);need((z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)==nodes['/'],'terminal-output-root')
        node=Path('/')
        for part in path.parent.parts[1:]:
            node/=part;d=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=d);fds.append(d);z=os.fstat(d)
            need((z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)==nodes[str(node)],'terminal-output-parent')
        need(frozenset(os.listdir(d))==names,'terminal-output-original-census')
        f=os.open(path.name,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=d);fds.append(f)
        created=os.fstat(f)
        need(stat.S_ISREG(created.st_mode) and stat.S_IMODE(created.st_mode)==0o600 and created.st_uid==os.geteuid() and created.st_gid==os.getegid() and created.st_nlink==1 and created.st_size==0,'terminal-output-intended-metadata')
        identity=(created.st_dev,created.st_ino,created.st_mode,created.st_uid,created.st_gid,created.st_nlink)
        offset=0
        while offset<len(raw):offset+=os.write(f,raw[offset:])
        os.fsync(f);os.lseek(f,0,0);seen=bytearray()
        while len(seen)<=len(raw):
            chunk=os.read(f,65536)
            if not chunk:break
            seen.extend(chunk)
        need(bytes(seen)==raw,'terminal-output-readback');z=os.fstat(f)
        need((z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)==identity and z.st_size==len(raw),'terminal-output-intended-metadata')
        stamp=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
        leaf=os.stat(path.name,dir_fd=d,follow_symlinks=False)
        need(stamp==(leaf.st_dev,leaf.st_ino,leaf.st_size,leaf.st_mtime_ns,leaf.st_ctime_ns,leaf.st_mode,leaf.st_uid,leaf.st_gid,leaf.st_nlink),'terminal-output-leaf-CAS')
        need(frozenset(os.listdir(d))==names|{path.name},'terminal-output-created-census');os.fsync(d);z=os.fstat(d)
        need((z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)==nodes[str(path.parent)],'terminal-output-parent-metadata')
        parent=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
        result=dict(path=str(path),signature9=list(stamp),sha256=hashlib.sha256(raw).hexdigest())
        for node,original in nodes.items():
            z=os.lstat(node)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=original:raise Held('terminal-output-node-final')
        for z in (os.fstat(f),os.stat(path.name,dir_fd=d,follow_symlinks=False)):
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:raise Held('terminal-output-file-final')
        z=os.fstat(d)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=parent:raise Held('terminal-output-directory-final')
    finally:
        for f in reversed(fds):os.close(f)
    return result,parent

def execute_evidence(ack_ref, *, read_ref, to_host, to_child, execute, nonce, provider_sha, action):
    """Original ACK -> original execute report -> original owning evidence refs."""
    execute=Path(execute)
    need(type(ack_ref) is dict and set(ack_ref)=={'path','sha256','signature9'} and ack_ref['path']==to_child(execute.parent/'execute-ack.json'),'terminal-original-execute-ACK-path')
    def read_original(ref):
        need(type(ref) is dict and set(ref)=={'path','sha256','signature9'},'terminal-original-evidence-ref')
        return read_ref(dict(ref,path=to_host(ref['path'])))
    ack=read_original(ack_ref)
    need(type(ack) is dict and set(ack)=={'nonce','phase','source_sha256','report','publication_acceptance','reader_resume_authority'} and ack['nonce']==nonce and ack['phase']=='execute' and ack['source_sha256']==provider_sha and ack['publication_acceptance'] is False and ack['reader_resume_authority'] is False,'terminal-original-execute-ACK')
    report_ref=ack['report']
    need(report_ref['path']==to_child(execute/'execute-report.json'),'terminal-original-execute-report-path')
    report=read_original(report_ref)
    need(report['phase']=='execute' and report['nonce']==nonce and report['final_ack_required'] is True and report['provider_continuity_verified'] is False and report['publication_acceptance'] is False and report['reader_resume_authority'] is False,'terminal-original-execute-report')
    kinds={'negative-five-owning-terminal-observation':('observed-forward','.terminal-v1','five-retired-negative-clear-ready','five-retired-negative-cleared'),'negative-five-owning-rollback-observation':('observed-rollback','.rollback-terminal-v1','five-restored-negative-rollback-clear-ready','five-restored-negative-rollback-cleared')}
    need(report['kind'] in kinds,'terminal-original-execute-outcome');outcome,suffix,ready_kind,cleared_kind=kinds[report['kind']]
    refs=report['terminal_refs'];need(type(refs) is dict and set(refs)=={'version','outcome','binding_sha256','clear_ready','cleared'} and type(refs['version']) is int and refs['version']==1 and refs['outcome']==outcome,'terminal-original-terminal-refs')
    journal=Path(action['batch_journal']);directory=journal.parent/(journal.name+suffix)
    pre=report['preimage'];need(pre['path']==to_child(execute/'terminal-observation-preimage.json') and refs['clear_ready']['path']==str(directory/'clear-ready.json') and refs['cleared']['path']==str(directory/'cleared.json'),'terminal-original-evidence-paths')
    read_original(pre);ready=read_original(refs['clear_ready']);cleared=read_original(refs['cleared'])
    need(ready['kind']==ready_kind and cleared['kind']==cleared_kind and ready['binding_sha256']==cleared['binding_sha256']==refs['binding_sha256'] and cleared['clear_ready_sha256']==refs['clear_ready']['sha256'],'terminal-original-owning-binding')
    return dict(preimage=pre,clear_ready=refs['clear_ready'],cleared=refs['cleared'],outcome=outcome)

def produce(request, *, watch, adapter):
    own=Path(__file__).absolute();z=os.lstat(own)
    own_original=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
    ctx=request['context']
    need(type(ctx) is dict and set(ctx)=={'backup','controls','observations','execute_action','execute_ack'},'terminal-producer-context')
    need(type(ctx['controls']) is dict and set(ctx['controls'])==ROLES,'terminal-original-nine')
    # Capture complete declared control/root ancestry before module/JSON helpers.
    entry={}
    known=[request['parent_plan'],request['parent_source'],ctx['execute_action'],ctx['execute_ack'],*ctx['controls'].values()]
    for p in [Path(__file__),*(Path(r['path']) for r in known)]:
        for node in p.parents:
            z=os.lstat(node);v=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)
            need(stat.S_ISDIR(z.st_mode),'terminal-admitted-parent')
            old=entry.setdefault(str(node),v);need(old==v,'terminal-admitted-parent-CAS')
    o,plan,scope,_sdk,_source=adapter.context(request,watch)
    for p,v in entry.items():need(o.nodes.setdefault(p,v)==v,'terminal-admission-conflict')
    mapping=watch.__self__.mapping
    adapter.current_observations(watch,ctx['observations'],'terminal-runtime-before')
    need(ctx['execute_action']==plan['action_inputs']['execute'],'terminal-original-action-ref')
    action=o.ref(ctx['execute_action']);execute=Path(request['operation'])/'execute'
    need(action['operation']==mapping.child(execute) and len(action['members'])==len(action['targets'])==5,'terminal-original-execute-action')
    need(execute.is_absolute() and execute.is_dir(),'terminal-execute-directory')
    original_names=frozenset(os.listdir(execute))
    target=execute/'terminal-observation-manifest.json';need(target.name not in original_names,'terminal-manifest-no-replay')
    journal=Path(mapping.host(action['batch_journal']))
    need(journal.is_relative_to(execute),'terminal-original-journal-scope')
    layouts=((journal.parent/(journal.name+'.terminal-v1'),'five-retired-negative-clear-ready','observed-forward'),
             (journal.parent/(journal.name+'.rollback-terminal-v1'),'five-restored-negative-rollback-clear-ready','observed-rollback'))
    candidates=[];missing=[]
    for directory,kind,outcome in layouts:
        if os.path.lexists(directory):candidates.append((directory,kind,outcome))
        else:missing.append(str(directory))
    need(len(candidates)==1,'terminal-exactly-one-owning-layout')
    directory,kind,outcome=candidates[0]
    # Original bound parent directories must remain physically unchanged while read.
    nodes=dict(o.nodes)
    for p in [execute,directory,journal]:
        for q in (p,*p.parents):
            z=os.lstat(q);v=adapter.five(z);need(stat.S_ISDIR(z.st_mode),'terminal-journal-parent')
            need(nodes.setdefault(str(q),v)==v,'terminal-journal-parent-CAS')
    observer=o.module('comic_negative_terminal_observer.py',OBSERVER_SHA)
    def host_path(value):
        value=Path(value)
        # Exact actual mounted host Sources are identities, not a path grant.
        sources=[Path(m['Source']) for row in ctx['observations'].values() for m in row['Mounts'] if m['Type'] in ('bind','volume')]
        sources += [Path(request['operation']),Path(__file__).parent,Path(ctx['backup']['restore_root'])]
        if any(value==p or p in value.parents for p in sources):return str(value)
        result=mapping.host(str(value))
        need(mapping.child(result)==str(value),'terminal-host-child-roundtrip')
        return result
    observation=observer.Observation(host_path)
    evidence=execute_evidence(dict(ctx['execute_ack'],path=mapping.child(ctx['execute_ack']['path'])),read_ref=observation.ref,to_host=host_path,to_child=mapping.child,execute=execute,nonce=request['nonce'],provider_sha=plan['provider']['sha256'],action=action)
    need(evidence['outcome']==outcome,'terminal-original-layout-outcome')
    evidence_files={str(p):tuple(v) for p,v in observation.files.items()};evidence_nodes={str(p):tuple(v) for p,v in observation.nodes.items()}
    pre_ref=evidence['preimage'];ready_ref=evidence['clear_ready'];cleared_ref=evidence['cleared']
    pre=observation.ref(pre_ref);ready=observation.ref(ready_ref);cleared=observation.ref(cleared_ref)
    need(ready['kind']==kind and cleared['kind']==('five-retired-negative-cleared' if outcome=='observed-forward' else 'five-restored-negative-rollback-cleared'),'terminal-owning-kind-layout')
    controls={k:dict(ref,path=mapping.child(ref['path'])) for k,ref in ctx['controls'].items()}
    need(pre['backup_controls']==controls and pre['reviewed_plan']==controls['reviewed_plan'],'terminal-original-controls')
    for intended,target_path,bound,member in zip(action['members'],action['targets'],pre['native'],ready['members']):
        need(bound['source']==intended['source']==member['source'] and bound['counterpart']==intended['counterpart'] and bound['owner']==intended['owner'] and member['target']==target_path,'terminal-original-five-action')
    need(len(pre['native'])==len(ready['members'])==5,'terminal-five-action-bound')
    # Current roots come from original reviewed custody plus inspected /config.
    custody=o.ref(ctx['controls']['custody']);mounts=[m for m in ctx['observations']['reader']['Mounts'] if m['Destination']=='/config']
    need(len(mounts)==1 and mounts[0]['Type']=='bind' and custody['reader_root']==mounts[0]['Source'],'terminal-current-reader-geometry')
    need(custody['restore_root']==ctx['backup']['restore_root'] and pre['restore_main']['path']==mapping.child(Path(custody['restore_root'])/'database.sqlite') and pre['restore_tasks']['path']==mapping.child(Path(custody['restore_root'])/'tasks.sqlite'),'terminal-original-restore-geometry')
    value=dict(version=1,preimage=pre_ref,clear_ready=ready_ref,cleared=cleared_ref,restore_main=pre['restore_main'],restore_tasks=pre['restore_tasks'],current_main=mapping.child(Path(custody['reader_root'])/'database.sqlite'),current_tasks=mapping.child(Path(custody['reader_root'])/'tasks.sqlite'),writer_root=str(Path(pre['native_paths']['publication']).parent))
    # Observe the intended candidate via the same source-bound observer without
    # publishing an unverified manifest: temporary read-only observation control.
    o.module('comic_negative_reader_action.py',plan['provider']['sha256'])
    private=execute/'terminal-observation-candidate.json'
    need(not os.path.lexists(private),'terminal-candidate-no-replay')
    candidate,first_dir=emit(private,value,nodes,original_names)
    # Candidate remains durable on any failure; no automatic replay or removal.
    result,originals=observer.observe_mapped_with_originals(candidate,source_sha256=OBSERVER_SHA,path_mapper=host_path)
    need(result['outcome']==outcome and all(result[k] is False for k in ('publication_acceptance','mutation_authority','reader_resume_authority','recovery_capability','application_quiescence_verified')),'terminal-observation-only')
    # Candidate creation is the sole owned namespace change before manifest.
    need(frozenset(os.listdir(execute))==original_names|{private.name},'terminal-candidate-namespace')
    need(tuple(adapter.nine(os.lstat(execute)))==first_dir,'terminal-candidate-dir-CAS')
    emitted,last_dir=emit(target,value,nodes,original_names|{private.name})
    output=dict(manifest=emitted,outcome=outcome)
    merged_files={};merged_nodes={}
    for values in ({own:own_original},o.files,evidence_files,originals['files'],{private:candidate['signature9'],target:emitted['signature9'],execute:last_dir}):merge(merged_files,values,'terminal-file-conflict')
    for values in (nodes,evidence_nodes,observation.nodes,originals['nodes']):merge(merged_nodes,values,'terminal-node-conflict')
    files=tuple((p,tuple(v)) for p,v in merged_files.items());node_items=tuple((p,tuple(v)) for p,v in merged_nodes.items())
    absences=tuple([*missing,*originals['absent']]);censuses=tuple((p,frozenset(v)) for p,v in originals['censuses'].items())
    # No baseline refresh: exclusive write must be the exact new leaf only.
    adapter.current_observations(watch,ctx['observations'],'terminal-runtime-after');adapter.deadline(request)
    for p,names in censuses:
        if frozenset(os.listdir(p))!=names:raise Held('terminal-final-journal-census')
    if frozenset(os.listdir(execute))!=original_names|{private.name,target.name}:raise Held('terminal-final-output-census')
    for p,v in node_items:
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('terminal-final-node')
    for p,v in files:
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('terminal-final-file')
    for p in absences:
        try:os.lstat(p)
        except FileNotFoundError:continue
        raise Held('terminal-final-absence')
    return output


def current_pairs(request,*,watch,adapter,reads,plan):
    """Fresh terminal pairs independently joined; original custody is untouched."""
    ctx=request['context'];mapping=watch.__self__.mapping
    ref=ctx['terminal_manifest'];execute=Path(request['operation'])/'execute'
    need(ref['path']==str(execute/'terminal-observation-manifest.json'),'terminal-custody-fixed-manifest')
    manifest=reads.ref(ref)
    action=reads.ref(plan['action_inputs']['execute'])
    need(action['operation']==mapping.child(execute),'terminal-custody-original-action')
    journal=Path(mapping.host(action['batch_journal']))
    layouts=[journal.parent/(journal.name+'.terminal-v1'),journal.parent/(journal.name+'.rollback-terminal-v1')]
    selected=[p for p in layouts if os.path.lexists(p)]
    need(len(selected)==1,'terminal-custody-exact-layout')
    directory=selected[0]
    need(manifest['clear_ready']['path']==mapping.child(directory/'clear-ready.json') and manifest['cleared']['path']==mapping.child(directory/'cleared.json'),'terminal-custody-owning-receipts')
    def mapper(value):
        p=Path(value)
        sources=[Path(m['Source']) for row in ctx['observations'].values() for m in row['Mounts'] if m['Type'] in ('bind','volume')]
        sources += [Path(request['operation']),Path(__file__).parent,Path(ctx['backup']['restore_root'])]
        if any(p==r or r in p.parents for r in sources):return str(p)
        actual=mapping.host(str(p));need(mapping.child(actual)==str(p),'terminal-custody-path-roundtrip');return actual
    observer=reads.module('comic_negative_terminal_observer.py',OBSERVER_SHA)
    # Freeze the owning pair tuples before any independent observer/copy callback.
    obs=observer.Observation(mapper)
    evidence=execute_evidence(dict(ctx['execute_ack'],path=mapping.child(ctx['execute_ack']['path'])),read_ref=obs.ref,to_host=mapper,to_child=mapping.child,execute=execute,nonce=request['nonce'],provider_sha=plan['provider']['sha256'],action=action)
    need(all(manifest[name]==evidence[name] for name in ('preimage','clear_ready','cleared')),'terminal-custody-original-execute-evidence')
    ready=obs.ref(manifest['clear_ready']);pre=obs.ref(manifest['preimage']);cleared=obs.ref(manifest['cleared']);commit=ready['commit']
    need(manifest['preimage']['path']==mapping.child(execute/'terminal-observation-preimage.json'),'terminal-custody-fixed-preimage')
    rollback=directory.name.endswith('.rollback-terminal-v1')
    need(ready['kind']==('five-restored-negative-rollback-clear-ready' if rollback else 'five-retired-negative-clear-ready') and cleared['kind']==('five-restored-negative-rollback-cleared' if rollback else 'five-retired-negative-cleared'),'terminal-custody-kind-layout')
    controls={k:dict(v,path=mapping.child(v['path'])) for k,v in ctx['controls'].items()}
    need(pre['backup_controls']==controls and pre['reviewed_plan']==controls['reviewed_plan'],'terminal-custody-original-controls')
    custody=reads.ref(ctx['controls']['custody'])
    need(manifest['current_main']==mapping.child(Path(custody['reader_root'])/'database.sqlite') and manifest['current_tasks']==mapping.child(Path(custody['reader_root'])/'tasks.sqlite'),'terminal-custody-current-roots')
    need(manifest['restore_main']['path']==mapping.child(Path(custody['restore_root'])/'database.sqlite') and manifest['restore_tasks']['path']==mapping.child(Path(custody['restore_root'])/'tasks.sqlite') and custody['restore_root']==ctx['backup']['restore_root'],'terminal-custody-restore-roots')
    need(len(pre['native'])==len(ready['members'])==len(action['members'])==len(action['targets'])==5,'terminal-custody-five')
    for intended,target,bound,member in zip(action['members'],action['targets'],pre['native'],ready['members']):
        need(bound['source']==intended['source']==member['source'] and bound['counterpart']==intended['counterpart'] and bound['owner']==intended['owner'] and member['target']==target,'terminal-custody-action-join')
    pairs={};original_files={};original_absent=[];original_nodes={}
    for name,key,pathkey in (('database.sqlite','main_pair','current_main'),('tasks.sqlite','tasks_pair','current_tasks')):
        values=[];root=Path(mapper(manifest[pathkey]))
        for suffix in ('','-wal','-shm','-journal'):
            path=str(root)+suffix
            if suffix not in commit[key]:original_absent.append(path);continue
            fact=commit[key][suffix];stamp=tuple(fact['signature9']);digest=fact['sha256']
            need(len(stamp)==9 and stat.S_ISREG(stamp[5]) and stamp[8]==1 and len(digest)==64,'terminal-custody-pair-fact')
            values.append((suffix,stamp,digest));original_files[path]=stamp
            for q in Path(path).parents:
                z=os.lstat(q);v=(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid);need(stat.S_ISDIR(z.st_mode),'terminal-custody-parent');merge(original_nodes,{str(q):v},'terminal-custody-parent-conflict')
        need(bool(values) and values[0][0]=='','terminal-custody-main-required')
        pairs[name]={suffix:dict(signature9=list(stamp),sha256=digest) for suffix,stamp,digest in values}
    merge(original_files,obs.files,'terminal-custody-execute-file-conflict');merge(original_nodes,obs.nodes,'terminal-custody-execute-node-conflict')
    result,originals=observer.observe_mapped_with_originals(ref,source_sha256=OBSERVER_SHA,path_mapper=mapper)
    need(result['outcome'] in ('observed-forward','observed-rollback'),'terminal-custody-factual-result')
    merge(original_files,originals['files'],'terminal-custody-file-conflict');merge(original_nodes,originals['nodes'],'terminal-custody-node-conflict')
    originals=dict(files=original_files,nodes=original_nodes,absent=tuple(set(original_absent)|set(map(str,originals['absent']))),censuses=originals['censuses'])
    return pairs,originals
