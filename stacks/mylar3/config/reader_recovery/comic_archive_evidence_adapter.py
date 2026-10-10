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
import sys

ACTION_SHA = '38a73d2ab08cb2139181987b494efac1b27e66c2c41190f85adffb91c9d12594'
PROBE_SHA = '77325f0a7fd14b6e2e1a1f91aaf4c66cb53b5e2fd4cffdd34453642002afd1ec'
SCOPE_SHA = '6d4b43c84a653aa56cbf22e25563b26e4cb8a5c700cce5d8a124612be3818608'
PRODUCER_SHA = 'd4b292c1bf56e6eafdcf87ae1f98c200cf4225e361334faa2b155828645c9e12'
TERMINAL_PRODUCER_SHA = 'd4b292c1bf56e6eafdcf87ae1f98c200cf4225e361334faa2b155828645c9e12'
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
    need(plan['native']==dict(data=data,roots=[library]),'archive-observed-native-configured-roots')
    need(type(plan['native']['roots']) is list and len(plan['native']['roots'])==1,'adapter-single-configured-library-required')
    worker_library_destination(scope,worker['Mounts'],native_host)
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


def produce(phase,request,*,watch):
    need(request['phase']==phase and phase in ('native-observation','backup-controls','phase-custody'),'archive-adapter-phase')
    if phase=='native-observation':
        output=native_observation(request,watch=watch)
        return dict(version=1,phase=phase,nonce=request['nonce'],evidence=output)
    o=Reads();o.ref(request['parent_source'],False);plan=o.ref(request['parent_plan'])
    own=o.raw(Path(__file__).absolute());need(hashlib.sha256(own).hexdigest()==plan['producer']['sha256'],'archive-adapter-own-source')
    action=o.module('comic_archive_repair_action.py',ACTION_SHA)
    previous=sys.modules.get('comic_archive_repair_action')
    sys.modules['comic_archive_repair_action']=action
    try:module=o.module('comic_archive_proof_producer.py',PRODUCER_SHA)
    finally:
        if previous is None:sys.modules.pop('comic_archive_repair_action',None)
        else:sys.modules['comic_archive_repair_action']=previous
    original_files=tuple(o.files.items());original_nodes=tuple(o.nodes.items())
    result=module.produce(phase,request,watch=watch)
    for path,value in original_nodes:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise Held('archive-adapter-final-node')
    for path,value in original_files:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:raise Held('archive-adapter-final-file')
    return result
