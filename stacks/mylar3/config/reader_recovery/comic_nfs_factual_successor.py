"""Host-only NFS facts: completed active canary -> owned stop -> execute prerequisite.

No SDK mutation authority, no transfer/reconstruction of the released canary lock.
"""
import argparse
import copy
import os
from pathlib import Path
import threading
import weakref

class Held(ValueError):pass
_REG=weakref.WeakKeyDictionary()

def need(v,r):
    if not v:raise Held(r)

def parent_module(owner):
    method=owner.left;g=method.__func__.__globals__
    need(type(owner) is g.get('LifecycleParent') and g.get('_CORES',{}).get(owner)==owner.core and owner.thread==threading.get_ident(),'nfs-existing-owning-parent')
    need(str(Path(method.__func__.__code__.co_filename).absolute())==owner.source_ref['path'],'nfs-source-bound-parent')
    owner.left();g['read'](owner.source_ref);return g

def seal(owner,record):
    return record['module'].encode(dict(parent=id(owner),engine=id(owner.engine),thread=owner.thread,plan=owner.plan_ref,source=owner.source_ref,
        nonce=owner.plan['nonce'],original=record['original'],canary=id(record['canary']),canary_source=record['canary_source'],phase=record['phase'],stopped=record.get('stopped'),execute=record.get('execute')))

def record(owner,phase):
    g=parent_module(owner);r=_REG.get(owner)
    need(r is not None and r['phase']==phase and r['seal']==seal(owner,r),'nfs-process-local-owning-phase')
    g['read'](r['canary_source']);r['canary'].close();return g,r

def originals(owner,canary):
    files={str(p):tuple(v) for p,v in owner.files.items()};nodes={str(p):tuple(v) for p,v in owner.nodes.items()}
    nodes[str(owner.op)]=tuple(owner.op_fact)
    for p,ref in owner.generated.items():
        v=tuple(ref['signature9']);need(p not in files or files[p]==v,'nfs-original-file-conflict');files[p]=v
    for p,v in canary.files:
        need(p not in files or files[p]==tuple(v),'nfs-original-canary-file-conflict');files[p]=tuple(v)
    for p,v in canary.nodes:
        need(p not in nodes or nodes[p]==tuple(v),'nfs-original-canary-node-conflict');nodes[p]=tuple(v)
    return tuple(files.items()),tuple(nodes.items()),tuple(canary.names),tuple(canary.absent)

def preflight(owner):
    g=parent_module(owner);plan=owner.plan['nfs']
    need(type(plan) is dict and set(plan)=={'adapter','active_parent','active_input'},'nfs-finite-plan')
    for ref in plan.values():g['read'](ref)
    module=g['pinned_module'](plan['active_parent'])
    need(callable(getattr(module,'run_active_factual',None)) and hasattr(module,'ActiveNFSCanaryObservation'),'nfs-owning-active-factory-required')
    need(owner.phase=='admitted' and owner not in _REG,'nfs-no-replay')
    return g,module

def run_active(owner):
    g,module=preflight(owner)
    original=copy.deepcopy(owner.baselines)
    for key,row in original.items():need(g['same_runtime'](owner.inspect(row['Id']),row),'nfs-original-active-runtime')
    ref=owner.plan['nfs']['active_input'];source=owner.plan['nfs']['active_parent']
    need(g['decode'](g['read'](ref))['operation_output']!=str(owner.op),'nfs-distinct-canary-operation')
    def engine(argv,**kwargs):
        # Exact inspected host parent owns the finite engine route; all additional
        # args are the source-pinned canary's fixed Docker/findmnt verbs.
        kwargs['timeout']=min(kwargs.get('timeout',0),owner.left())
        return owner.engine.canary(argv,**kwargs)
    need(callable(getattr(owner.engine,'canary',None)),'nfs-finite-canary-engine-required')
    args=argparse.Namespace(input=ref['path'],input_sha256=ref['sha256'],source_sha256=source['sha256'],execute=True)
    canary=module.run_active_factual(args,engine)
    need(type(canary) is module.ActiveNFSCanaryObservation,'nfs-exact-completed-canary')
    diagnostic=canary.binding
    need(all(diagnostic.get(k) is True for k in ('disposable_probe_verified','platform_supported','owned_fixture_absence_verified')), 'nfs-owning-canary-incomplete')
    rows={row['Name']:row for row in canary.current(stopped=False)}
    for key in ('reader','held_native','held_worker'):
        row=original[key];need(g['same_runtime'](rows[row['Name']],row),'nfs-original-common-parent-runtime')
    r=dict(module=module,canary=canary,canary_source=copy.deepcopy(source),phase='active',original=original)
    r['seal']=seal(owner,r);_REG[owner]=r
    canary.close();owner.left()

_RETAINED=weakref.WeakKeyDictionary()
_STOPPED_HANDOFFS=weakref.WeakKeyDictionary()
_STOPPED_KEY=object()

class RetainedObservation:
    """Source-owned session proxy; never an ActiveNFSCanaryObservation."""
    def __init__(self,owner,session,facts):
        g=parent_module(owner);modules=owner.nfs_host_modules()
        need(type(session) is modules['comic_nfs_parent_session.py'].RetainedChild and g['_NFS_LIVE_SESSIONS'].get(owner) is session and session.owner is owner and session.state=='ready','nfs-retained-original-session')
        need(type(facts) is dict and set(facts)=={'binding','mount','device','files','nodes','names','absent'},'nfs-retained-ready-facts')
        need(type(facts['binding']) is dict and all(facts['binding'].get(k) is False for k in ('actual_library_platform_verified','future_mylar_destination_verified','native_grant','publication_authority','writer_lifecycle_resume_authorized')),'nfs-retained-factual-rights-only')
        need(session.lease_replies.done is True and all(facts['binding'].get(k) is True for k in ('disposable_probe_verified','platform_supported','owned_fixture_absence_verified')),'nfs-retained-source-complete')
        self.owner,self.session,self.g=owner,session,g;self.tape=g['encode'](facts)
        self.binding,self.mount,self.device=copy.deepcopy(facts['binding']),copy.deepcopy(facts['mount']),facts['device']
        # Leaf9 is identical across each verified bind projection. Child-only
        # namespace ancestors stay checked by the genuine process-local canary;
        # host ancestors are independently retained Parent/Tree originals.
        tree=g['_CHILD_TREES'][owner];files=[]
        need(all(type(facts[key]) is list and len(facts[key])<=512 for key in ('files','nodes','names','absent')) and type(facts['device']) is int and facts['device']>0 and type(facts['mount']) is dict and facts['mount'].get('fstype')=='nfs4','nfs-retained-bounded-real-nfs-facts')
        for path,stamp in facts['files']:
            need(type(path) is str and type(stamp) is list and len(stamp)==9 and all(type(v) is int for v in stamp),'nfs-retained-original-file-vector')
            host=owner.mapping.host(path);expected=tuple(stamp)
            need(tuple(g['nine'](os.lstat(host)))==expected,'nfs-retained-mapped-original-leaf9');files.append((host,expected))
        nodes=dict(owner.nodes)
        for path,stamp in (*tree.nodes,*tree.directories):
            need(path not in nodes or nodes[path]==tuple(stamp),'nfs-retained-host-node-conflict');nodes[path]=tuple(stamp)
        names=[]
        for path,expected in facts['names']:
            host=owner.mapping.host(path);need(tuple(sorted(os.listdir(host)))==tuple(sorted(expected)),'nfs-retained-original-namespace');names.append((host,frozenset(expected)))
        absent=tuple(owner.mapping.host(path) for path in facts['absent'])
        self.files,self.nodes,self.names,self.absent=tuple(files),tuple(nodes.items()),tuple(names),absent
        self.original=(owner,session,self.tape,g['encode'](dict(binding=self.binding,mount=self.mount,device=self.device)),self.files,self.nodes,self.names,self.absent)
        _RETAINED[self]=self.original;self.close()
    def close(self):
        owner,session,tape,diagnostic,files,nodes,names,absent=_RETAINED.get(self,(None,)*8)
        need(self.original==(owner,session,tape,diagnostic,files,nodes,names,absent) and self.owner is owner and self.session is session and self.tape==tape and self.g['encode'](dict(binding=self.binding,mount=self.mount,device=self.device))==diagnostic and (self.files,self.nodes,self.names,self.absent)==(files,nodes,names,absent),'nfs-retained-original-proxy')
        need(self.g['_NFS_LIVE_SESSIONS'].get(owner) is session and session.state=='ready','nfs-retained-original-live-session')
        session.request('check',stopped=owner.phase not in ('admitted','stopping'))
        owner.left()
        for path,expected in names:
            need(frozenset(os.listdir(path))==expected,'nfs-retained-original-namespace-tail')
        self.g['final'](dict(files),dict(nodes),absent)
        for path in absent:
            try:os.lstat(path)
            except FileNotFoundError:continue
            raise Held('nfs-retained-original-absence')
    def current(self,*,stopped):
        self.close();result=self.session.request('current',stopped=stopped);self.close();return result

def completed_retained_original(owner,canary,session,g,expected):
    """Original frozen proxy record without requesting expired/live child work."""
    module=owner.nfs_host_modules()['comic_nfs_parent_session.py'];method=session.successful_exit
    need(type(canary) is RetainedObservation and canary.g is g
         and canary.owner is owner and canary.session is session
         and _RETAINED.get(canary) is expected and canary.original is expected
         and expected==(owner,session,canary.tape,g['encode'](dict(binding=canary.binding,mount=canary.mount,device=canary.device)),canary.files,canary.nodes,canary.names,canary.absent),
         'nfs-stopped-original-proxy-record')
    need(type(session) is module.RetainedChild and g['_NFS_LIVE_SESSIONS'].get(owner) is session
         and getattr(method,'__self__',None) is session and getattr(method,'__func__',None) is module.RetainedChild.successful_exit,
         'nfs-stopped-original-source-session')
    return expected

class StoppedNFSHandoff:
    """Private completed-stop successor; never a reconstructed active canary."""
    def __init__(self,key,owner,canary,session,observed):
        need(key is _STOPPED_KEY,'nfs-stopped-owning-key')
        proxy=_RETAINED.get(canary);r=_REG.get(owner);phase_seal=r.get('seal') if type(r) is dict else None
        observed_original=copy.deepcopy(observed)
        g=parent_module(owner)
        need(proxy is not None and type(r) is dict and _REG.get(owner) is r and r['seal']==phase_seal==seal(owner,r),'nfs-stopped-earliest-owning-phase')
        need(type(canary) is RetainedObservation and _RETAINED.get(canary)==canary.original
             and canary.owner is owner and canary.session is session
             and r is not None and r['phase']=='stopped' and r['canary'] is canary
             and r['stopped']==observed and owner.stop_state==observed['reader']['State'],
             'nfs-stopped-original-canary-stop')
        completed_retained_original(owner,canary,session,g,proxy);stopped_tape=g['encode'](observed_original)
        need(g['encode'](observed)==stopped_tape,'nfs-stopped-earliest-observed-roles')
        exit_proof=session.successful_exit()
        need(completed_retained_original(owner,canary,session,g,proxy) is proxy
             and _REG.get(owner) is r and r['seal']==phase_seal==seal(owner,r)
             and g['encode'](observed)==stopped_tape,'nfs-stopped-final-original-proxy')
        self.owner,self.g,self.session=owner,g,session
        self.files,self.nodes,self.names,self.absent=proxy[4:]
        diagnostic=g['decode'](proxy[3]);self.binding=diagnostic['binding'];self.mount=diagnostic['mount'];self.device=diagnostic['device']
        self.stopped=g['decode'](stopped_tape)
        context=g['_NFS_SOURCE_CONTEXTS'].get(owner);need(context is not None,'nfs-stopped-configured-only')
        self.library=g['decode'](context[3])['library_root']
        self.origin=(owner,owner.core,owner.engine,owner.thread,owner.plan['nonce'],session,canary,exit_proof)
        self.tape=g['encode'](dict(binding=self.binding,mount=self.mount,device=self.device,stopped=self.stopped,library=self.library))
        _STOPPED_HANDOFFS[self]=(self.g,self.origin,self.tape,self.files,self.nodes,self.names,self.absent)
        self.close()
    def close(self):
        saved=_STOPPED_HANDOFFS.get(self)
        need(saved is not None and len(saved)==7,'nfs-stopped-original-handoff-registry')
        g,origin,tape,files,nodes,names,absent=saved;owner=origin[0];session=origin[5]
        def original():
            need(_STOPPED_HANDOFFS.get(self) is saved and self.g is g and self.owner is owner and self.session is session
                 and (self.origin,self.tape,self.files,self.nodes,self.names,self.absent)==(origin,tape,files,nodes,names,absent)
                 and origin[:5]==(owner,owner.core,owner.engine,owner.thread,owner.plan['nonce']),
                 'nfs-stopped-original-exit-custody')
        original();owner.left()
        need(session.successful_exit()==origin[7],'nfs-stopped-original-successful-exit')
        need(g['encode'](dict(binding=self.binding,mount=self.mount,device=self.device,stopped=self.stopped,library=self.library))==tape,'nfs-stopped-original-facts')
        for path,expected in names:
            need(frozenset(os.listdir(path))==expected,'nfs-stopped-original-namespace-tail')
        need(g['encode'](dict(binding=self.binding,mount=self.mount,device=self.device,stopped=self.stopped,library=self.library))==tape,'nfs-stopped-final-original-facts')
        original()
        g['final'](dict(files),dict(nodes),absent)
        for path,expected in names:
            need(frozenset(os.listdir(path))==expected,'nfs-stopped-final-namespace')
        original()
        # Raw retained vectors again after the final replaceable helper.
        for path,fact in nodes:
            z=os.lstat(path)
            need((z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)==tuple(fact),'nfs-stopped-final-node')
        for path,fact in files:
            z=os.lstat(path)
            need((z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)==tuple(fact),'nfs-stopped-final-file')
        for path in absent:
            try:os.lstat(path)
            except FileNotFoundError:continue
            raise Held('nfs-stopped-original-owned-absence')
    def current(self,*,stopped):
        need(stopped is True,'nfs-stopped-no-active-reader-route')
        saved=_STOPPED_HANDOFFS.get(self);need(saved is not None,'nfs-stopped-original-handoff-registry')
        g,origin,tape,*_=saved;owner=origin[0];facts=g['decode'](tape)
        self.close();g['nfs_remote_guard'](owner.engine)
        current=owner.continuous()  # Exact stopped epoch plus existing full event history.
        need(all(g['same_runtime'](row,facts['stopped'][key]) for key,row in current.items()),'nfs-stopped-original-current-roles')
        result=owner.engine.canary(['findmnt','--json','--target',facts['library'],'--output','SOURCE,TARGET,FSTYPE,FSROOT,OPTIONS,MAJ:MIN'],input=None,capture_output=True,check=False,timeout=min(30,owner.left()))
        need(result.returncode==0 and len(result.stdout)<=1024**2 and len(result.stderr)<=1024**2
             and g['decode'](result.stdout)=={'filesystems':[facts['mount']]},'nfs-stopped-original-current-export')
        need(os.lstat(facts['library']).st_dev==facts['device'],'nfs-stopped-original-library-device')
        self.close();need(_STOPPED_HANDOFFS.get(self) is saved,'nfs-stopped-final-current-registry')
        return list(current.values())

def run_active_retained(owner):
    """Registered child/source/pipe route; base direct factory remains strict."""
    g,module=preflight(owner);original=copy.deepcopy(owner.baselines)
    for row in original.values():need(g['same_runtime'](owner.inspect(row['Id']),row),'nfs-retained-original-prelaunch-runtime')
    packet,source=owner.prepare_nfs_packet(min(120,int(owner.left())))
    session=owner.open_nfs_child(packet,source);facts=session.ready()
    canary=RetainedObservation(owner,session,facts)
    rows={row['Name']:row for row in canary.current(stopped=False)}
    for row in original.values():need(g['same_runtime'](rows[row['Name']],row),'nfs-retained-original-current-runtime')
    r=dict(module=module,canary=canary,canary_source=copy.deepcopy(owner.plan['nfs']['active_parent']),phase='active',original=original)
    r['seal']=seal(owner,r);_REG[owner]=r;canary.close();owner.left()

def stop_owned(owner):
    g,r=record(owner,'active');rows={row['Name']:row for row in r['canary'].current(stopped=False)}
    for row in r['original'].values():need(g['same_runtime'](rows[row['Name']],row),'nfs-prestop-current-original')
    # Only this exact owning transition performs the stop; a receipt cannot bind it.
    before=originals(owner,r['canary'])
    owner.phase='stopping'
    intent=owner.emit('stop-intent.json',dict(id=owner.plan['reader']['id'],automatic_replay=False))
    r['phase']='stop-uncertain';r['seal']=seal(owner,r)
    seconds=owner.left();r['canary'].close()
    final_files=(*before[0],(intent['path'],tuple(intent['signature9'])))
    for p,v in before[2]:
        if frozenset(os.listdir(p)) != v:raise Held('nfs-prestop-census')
    for p,v in before[1]:
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('nfs-prestop-ancestor')
    for p,v in final_files:
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('nfs-prestop-file')
    for p in before[3]:
        try:os.lstat(p)
        except FileNotFoundError:continue
        raise Held('nfs-prestop-cleanup-absence')
    raw=owner.engine.run(['stop','--timeout','60',owner.plan['reader']['id']],seconds)
    need(raw.decode().strip()==owner.plan['reader']['id'],'nfs-stop-ACK-unknown-no-replay')
    observed=owner.continuous();rows={row['Name']:row for row in r['canary'].current(stopped=True)}
    for row in observed.values():need(g['same_runtime'](rows[row['Name']],row),'nfs-stopped-current-join')
    owner.stop_state=copy.deepcopy(observed['reader']['State'])
    r['phase']='stopped';r['stopped']=copy.deepcopy(observed);r['seal']=seal(owner,r)
    r['canary'].close();owner.left()
    if type(r['canary']) is RetainedObservation:
        original_canary=r['canary'];session=original_canary.session
        session.request('release',stopped=True)
        handoff=StoppedNFSHandoff(_STOPPED_KEY,owner,original_canary,session,observed)
        r['canary']=handoff;r['seal']=seal(owner,r)
        handoff.close()
        if owner.plan.get('action')=='archive-one':owner.admit_archive_retention(handoff)
    return observed

def nfs_ready(owner,request,*,watch):
    g,r=record(owner,'stopped')
    need(watch.__self__ is owner and watch.__func__ is type(owner).continuous,'nfs-owning-stopped-watch')
    need(request['phase']=='nfs-ready' and request['nonce']==owner.plan['nonce'] and request['operation']==str(owner.op)
         and request['parent_plan']==owner.plan_ref and request['parent_source']==owner.source_ref,'nfs-request-owning-binding')
    before=originals(owner,r['canary'])
    context=request['context'];need(set(context)=={'input','command','context'},'nfs-request-context')
    inp=context['input'];g['read'](inp)
    need(inp==owner.generated.get(str(owner.op/'execute-input.json')),'nfs-original-execute-input')
    expected=['/lsiopy/bin/python3','-I','-B',owner.mapping.child(owner.plan['provider']['path']),'--phase','execute','--input',owner.mapping.child(inp['path']),
              '--input-sha256',inp['sha256'],'--source-sha256',owner.plan['provider']['sha256']]
    need(context['command']==expected,'nfs-exact-action-command')
    ctx=context['context'];need(set(ctx)=={'backup','controls','observations'} and set(ctx['controls'])==g['ROLES'],'nfs-original-nine-controls')
    for ref in ctx['controls'].values():g['read'](ref)
    current=watch();rows={row['Name']:row for row in r['canary'].current(stopped=True)}
    for key,row in current.items():
        need(g['same_runtime'](row,r['stopped'][key]) and g['same_runtime'](rows[row['Name']],row),'nfs-stopped-continuity')
    # Factual evidence only. The action child still acquires its OWN exact Writer,
    # fresh complete native registry/catalog/census and nine-role admission.
    facts=dict(version=1,kind='owning-active-to-stopped-nfs-facts',nonce=request['nonce'],execute_input=copy.deepcopy(inp),command=list(expected),
               canary_source=copy.deepcopy(r['canary_source']),mount=copy.deepcopy(r['canary'].mount),device=r['canary'].device,
               canary=copy.deepcopy(r['canary'].binding),stopped=copy.deepcopy(current['reader']),canary_writer_lease_released=True,
               continuous_action_lock=False,actual_library_platform_verified=False,native_grant=False,publication_authority=False,reader_resume_authority=False)
    output=owner.emit('nfs-ready.json',facts)
    r['execute']=copy.deepcopy(inp);r['phase']='consumed';r['seal']=seal(owner,r)
    result=dict(version=1,phase='nfs-ready',nonce=request['nonce'],evidence=dict(evidence=copy.deepcopy(output)))
    r['canary'].close();owner.continuous();owner.left()
    for p,v in before[2]:
        if frozenset(os.listdir(p))!=v:raise Held('nfs-ready-census')
    for p,v in before[1]:
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('nfs-ready-ancestor')
    for p,v in (*before[0],(output['path'],tuple(output['signature9']))):
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('nfs-ready-file')
    for p in before[3]:
        try:os.lstat(p)
        except FileNotFoundError:continue
        raise Held('nfs-ready-cleanup-absence')
    return result

ARCHIVE_ROLES=frozenset({'stopped_runtime','backup_ack','backup_manifest','backup_acceptance','schema','reader_snapshot','archive_request','custody'})

def nfs_ready_archive(owner,request,*,watch):
    """Distinct archive-only one-use fact; default negative-five route unchanged."""
    g,r=record(owner,'stopped')
    need(owner.plan.get('kind')=='reviewed-archive-one-lifecycle-protocol','archive-nfs-default-disabled')
    need(watch.__self__ is owner and watch.__func__ is type(owner).continuous,'archive-nfs-owning-watch')
    need(set(request)=={'version','phase','nonce','operation','deadline_monotonic','parent_plan','parent_source','context'} and type(request['version']) is int and request['version']==1 and request['phase']=='archive-nfs-ready' and request['nonce']==owner.plan['nonce'] and request['operation']==str(owner.op) and type(request['deadline_monotonic']) is float and request['deadline_monotonic']==owner.deadline and request['parent_plan']==owner.plan_ref and request['parent_source']==owner.source_ref,'archive-nfs-request-binding')
    before=originals(owner,r['canary']);files=dict(before[0]);nodes=dict(before[1])
    for p,v in g.get('_OUTPUT_NODES',{}).get(owner,{}).items():
        need(p not in nodes or nodes[p]==tuple(v),'archive-nfs-output-node-conflict');nodes[p]=tuple(v)
    context=request['context'];need(set(context)=={'input','command','context'},'archive-nfs-context')
    ctx=context['context'];need(set(ctx)=={'backup','controls','archive_scopes','observations'} and set(ctx['controls'])==ARCHIVE_ROLES,'archive-nfs-eight-roles')
    inp=context['input'];need(inp==owner.generated.get(str(owner.op/'execute-input.json')),'archive-nfs-original-execute-input')
    refs=[*ctx['controls'].values(),ctx['archive_scopes'],owner.plan['producer_inputs']['archive_request']]
    for ref in refs:
        need(type(ref)==dict and set(ref)=={'path','sha256','signature9'} and type(ref['signature9']) is list and len(ref['signature9'])==9 and all(type(v) is int for v in ref['signature9']),'archive-nfs-original-reference')
        p=ref['path'];fact=tuple(ref['signature9']);need(p not in files or files[p]==fact,'archive-nfs-original-file-conflict');files[p]=fact
        for path,value in g['parents'](Path(p)).items():
            value=tuple(value);need(path not in nodes or nodes[path]==value,'archive-nfs-original-node-conflict');nodes[path]=value
    for ref in refs:g['read'](ref)
    doc=g['decode'](g['read'](inp));original=g['decode'](g['read'](owner.plan['producer_inputs']['archive_request']))
    need(type(original) is dict and set(original)=={'version','owner','operation_id'} and type(original['version']) is int and original['version']==1,'archive-nfs-original-owner-request')
    expected=['/lsiopy/bin/python3','-I','-B',owner.mapping.child(owner.plan['provider']['path']),'--phase','execute','--input',owner.mapping.child(inp['path']),'--input-sha256',inp['sha256'],'--source-sha256',owner.plan['provider']['sha256']]
    need(context['command']==expected and doc['action']=='archive-one' and doc['owner']==original['owner'] and doc['operation_id']==original['operation_id'],'archive-nfs-exact-owner-command')
    need(doc['controls']=={k:owner.mapping.child_ref(v) for k,v in ctx['controls'].items()} and doc['archive_scopes']==owner.mapping.child_ref(ctx['archive_scopes']),'archive-nfs-original-input-controls')
    current=watch();rows={row['Name']:row for row in r['canary'].current(stopped=True)}
    for key,row in current.items():need(g['same_runtime'](row,r['stopped'][key]) and g['same_runtime'](rows[row['Name']],row),'archive-nfs-stopped-continuity')
    facts=dict(version=1,kind='archive-one-owning-active-to-stopped-nfs-facts',nonce=request['nonce'],execute_input=copy.deepcopy(inp),command=list(expected),owner=copy.deepcopy(original['owner']),operation_id=original['operation_id'],canary_source=copy.deepcopy(r['canary_source']),mount=copy.deepcopy(r['canary'].mount),device=r['canary'].device,canary=copy.deepcopy(r['canary'].binding),stopped=copy.deepcopy(current['reader']),canary_writer_lease_released=True,continuous_action_lock=False,actual_library_platform_verified=False,native_grant=False,publication_authority=False,reader_resume_authority=False)
    r['phase']='archive-ready-uncertain';r['seal']=seal(owner,r)
    output=owner.emit('archive-nfs-ready.json',facts)
    r['execute']=copy.deepcopy(inp);r['phase']='consumed';r['seal']=seal(owner,r)
    result=dict(version=1,phase='archive-nfs-ready',nonce=request['nonce'],evidence=dict(evidence=copy.deepcopy(output)))
    files[output['path']]=tuple(output['signature9'])
    file_items=tuple(files.items());node_items=tuple(nodes.items())
    r['canary'].close();owner.continuous();owner.left()
    for p,v in before[2]:
        if frozenset(os.listdir(p))!=v:raise Held('archive-nfs-final-census')
    for p,v in node_items:
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=v:raise Held('archive-nfs-final-node')
    for p,v in file_items:
        z=os.lstat(p)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=v:raise Held('archive-nfs-final-file')
    for p in before[3]:
        try:os.lstat(p)
        except FileNotFoundError:continue
        raise Held('archive-nfs-final-cleanup-absence')
    return result
