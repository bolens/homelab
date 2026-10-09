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
