"""Default-off retained parent conversation; distinct from archive parent authority."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import threading
import time
import weakref

from comic_retained_pack_backup import BackupObservation,copy_and_verify,encode,five,nine,need,raw
from retained_pack_control import Pipe,TOTAL_SECONDS,WAITING_SECONDS
import comic_retained_pack_backup as backup_module
import retained_pack_control as control_module

ENABLED=False
PRIMITIVES_SOURCE_SHA=None
NATIVE_PROBE_SOURCE_SHA=None
BACKUP_SOURCE_SHA=None
SCOPE_SOURCE_SHA='6d4b43c84a653aa56cbf22e25563b26e4cb8a5c700cce5d8a124612be3818608'
MAX_MOUNTS=32
MAX_NETWORKS=4
IMAGE_PREFIXES=('/app','/usr','/lib','/lib64','/etc','/bin','/sbin','/opt/archiving-utils')
_ACTIVE=weakref.WeakKeyDictionary()
_RUNTIMES=weakref.WeakKeyDictionary()
_TERMINALS=weakref.WeakKeyDictionary()
_TERMINAL_ABSENT=object()


class RetainedParentConversation:
    __slots__=('__weakref__',)
    def __init__(self,*args,**kwargs):raise ValueError('Original owning retained parent required')


def _core(value,terminal_original=_TERMINAL_ABSENT):
    c=_ACTIVE.get(value);need(c is not None and (c['pid'],c['thread'])==(os.getpid(),threading.get_ident()) and time.monotonic()<c['deadline'],'retained-parent-lifetime')
    need(encode(c['plan'])==c['plan_bytes'],'original-parent-plan-memory')
    c['runtime'].close();c['pipe'].close_originals();raw(c['plan_frame'])
    if _RUNTIMES is not c['runtime_table'] or _RUNTIMES.get(c['runtime']) is not c['runtime_registry']:raise ValueError('parent-original-runtime-registry')
    if _TERMINALS is not c['terminal_table']:raise ValueError('parent-original-terminal-table')
    if terminal_original is _TERMINAL_ABSENT:
        if c['runtime'] in _TERMINALS:raise ValueError('parent-original-terminal-absence')
    elif c['runtime'] not in _TERMINALS or _TERMINALS.get(c['runtime']) is not terminal_original:raise ValueError('parent-original-terminal-registry')
    return c


def from_original_pipe(plan_ref,source_ref,read_fd,write_fd,runtime):
    """Mechanism factory. Does not launch, inspect, stop or grant a native action."""
    # Immutable actual registry is retained before the first replaceable callback.
    if type(runtime) is not ConfiguredRuntime:raise ValueError('actual-configured-runtime-required')
    runtime_table=_RUNTIMES;runtime_registry=runtime_table.get(runtime);terminal_table=_TERMINALS
    if type(runtime_registry) is not bytes:raise ValueError('original-runtime-registry-required')
    if runtime in terminal_table:raise ValueError('original-terminal-absence-required')
    need(ENABLED is True,'parent-default-disabled')
    need(type(runtime) is ConfiguredRuntime and runtime in _RUNTIMES,'actual-configured-runtime-required')
    need(type(plan_ref) is dict and set(plan_ref)=={'path','sha256','signature9'},'original-parent-plan-ref')
    p=Path(plan_ref['path']);stamp=tuple(plan_ref['signature9']);nodes=tuple((str(q),five(os.lstat(q))) for q in p.parents)
    own=Path(__file__).absolute();own9=nine(os.lstat(own));own_nodes=tuple((str(q),five(os.lstat(q))) for q in own.parents)
    dependencies=tuple(Path(q.__file__).absolute() for q in (backup_module,control_module))
    dep_files=tuple((str(q),nine(os.lstat(q))) for q in dependencies)
    dep_nodes=tuple((str(a),five(os.lstat(a))) for q in dependencies for a in q.parents)
    frame=(((str(p),stamp),(str(own),own9))+dep_files,nodes+own_nodes+dep_nodes,())
    runtime.close();raw(frame);need(own9[5]&0o170000==0o100000 and own9[8]==1,'parent-source-original')
    need(type(source_ref) is dict and set(source_ref)=={'path','sha256','signature9'} and source_ref['path']==str(own) and tuple(source_ref['signature9'])==own9,'parent-source-original-ref')
    actual_source,_=_ref(own);need(actual_source==source_ref,'parent-source-pin')
    actual_plan,data=_ref(p);need(actual_plan==plan_ref,'parent-plan-pin');plan=json.loads(data)
    need(encode(plan)==data and type(plan) is dict and set(plan)=={'version','kind','nonce','pack_id','member_id','journal_host','worker_pid','backup_scopes','backup_output','primitives','challenge'},'parent-plan-schema')
    need(type(plan['version']) is int and plan['version']==1 and plan['kind']=='retained-pack-preproof-conversation-v1','parent-plan-version')
    need(all(type(plan[k]) is str and len(plan[k])==64 and all(x in '0123456789abcdef' for x in plan[k]) for k in ('nonce','pack_id','member_id','challenge')),'parent-selector')
    need(type(plan['worker_pid']) is int and plan['worker_pid']>0,'original-worker-process')
    need(_strict_ref(plan['primitives'])['sha256']==PRIMITIVES_SOURCE_SHA and PRIMITIVES_SOURCE_SHA is not None,'parent-primitives-pin')
    raw((((plan['primitives']['path'],tuple(plan['primitives']['signature9'])),),(),()))
    # State-root identity is retained before the first conversation callback;
    # initialization may change its directory times, never its incarnation.
    roots=tuple(Path(q['root']) for q in plan['backup_scopes'])
    additional=tuple((str(q),five(os.lstat(q))) for root in roots for q in (root,*root.parents))
    frame=(frame[0],frame[1]+additional,frame[2])
    raw(frame);value=object.__new__(RetainedParentConversation)
    _ACTIVE[value]=dict(plan=plan,plan_frame=frame,pipe=Pipe(read_fd,write_fd,plan['nonce'],time.monotonic()+TOTAL_SECONDS),pid=os.getpid(),thread=threading.get_ident(),deadline=time.monotonic()+TOTAL_SECONDS,phase='waiting',backup=None,runtime=runtime,runtime_table=runtime_table,runtime_registry=runtime_registry,terminal_table=terminal_table,plan_bytes=data,driver=None if runtime.process is None else (runtime.process,runtime.process.pid,runtime.process.stdin,runtime.process.stdout,runtime.process.stderr))
    _core(value);return value


def initialized(value):
    c=_core(value);need(c['phase']=='waiting','parent-waiting-once');plan=c['plan']
    wanted=time.monotonic()+WAITING_SECONDS;c['pipe'].deadline=min(c['deadline'],wanted)
    message=c['pipe'].receive('initialized',plan['challenge'])
    need(type(message) is dict and set(message)=={'journal','signature9','nodes5','worker_pid'} and type(message['worker_pid']) is int and message['worker_pid']==plan['worker_pid'],'parent-original-worker-ACK')
    # HOST path supplied by inspected original mapping; CHILD facts are not relabeled.
    # This helper deliberately refuses differing namespace facts. Runtime adapter must
    # validate and pass the exact physical bind mapping rather than invent equality.
    journal=Path(plan['journal_host']);s=tuple(message['signature9']);need(len(s)==9 and all(type(v) is int for v in s),'parent-journal-vector')
    z=os.lstat(journal);need(nine(z)==s and z.st_mode&0o170000==0o040000 and z.st_mode&0o7777==0o700,'parent-initialized-journal')
    worker_root=Path(next(q['root'] for q in plan['backup_scopes'] if q['role']=='worker_state'))
    child_parents=tuple(Path(message['journal']).parents);original_nodes=dict(c['plan_frame'][1]);nodes=[]
    need(type(message['nodes5']) is dict and journal.is_relative_to(worker_root),'original-initialized-node-map')
    for index,parent in enumerate(journal.parents):
        if parent.is_relative_to(worker_root):
            need(index<len(child_parents) and str(child_parents[index]) in message['nodes5'],'initialized-original-child-node')
            wanted=tuple(message['nodes5'][str(child_parents[index])]);need(len(wanted)==5 and all(type(v) is int for v in wanted),'initialized-node-schema')
        else:
            need(str(parent) in original_nodes,'initialized-original-host-ancestor');wanted=original_nodes[str(parent)]
        nodes.append((str(parent),wanted))
    nodes=tuple(nodes)
    c['initialized']=message;c['init_frame']=(((str(journal),s),),nodes,());c['initialized_sha']=hashlib.sha256(encode(message)).hexdigest()
    _core(value);raw(c['init_frame']);c['phase']='initialized';return dict(initialized_sha256=c['initialized_sha'])


def backup(value):
    c=_core(value);need(c['phase']=='initialized','parent-backup-once');raw(c['init_frame'])
    plan=c['plan'];observation=copy_and_verify(plan['backup_scopes'],plan['backup_output'],plan['primitives']['path'],PRIMITIVES_SOURCE_SHA)
    need(type(observation) is BackupObservation,'actual-neutral-backup-observation');summary=observation.close();c['backup']=observation
    _core(value);raw(c['init_frame']);c['summary']=summary;c['phase']='backup-verified';return summary


def release_backup(value):
    """Requires actual in-memory verified observation; saved JSON cannot release."""
    c=_core(value);need(c['phase']=='backup-verified' and type(c['backup']) is BackupObservation,'parent-owned-backup-required')
    need(c['runtime'].native_open and c['runtime'].selected is not None,'actual-selected-worker-native-phase')
    summary=c['backup'].close();need(summary==c['summary'],'parent-backup-original-summary')
    _core(value);raw(c['init_frame']);plan=c['plan']
    c['pipe'].deadline=c['deadline']
    c['pipe'].send('backup-ready',plan['challenge'],dict(kind='verified-retained-backup-v1',backup_digest=summary['digest'],initialized_sha256=c['initialized_sha'],pack_id=plan['pack_id'],member_id=plan['member_id']))
    c['phase']='released'


def _projection(value):
    pending=[value];out=[]
    while pending:
        item=pending.pop();kind=type(item)
        if kind is dict:
            keys=tuple(sorted(item));out.append(('dict',keys));pending.extend(item[k] for k in reversed(keys))
        elif kind in (tuple,list):out.append((kind.__name__,len(item)));pending.extend(reversed(item))
        elif kind in (str,int,float,bool,bytes,type(None)):out.append((kind.__name__,item))
        else:out.append(('identity',id(kind),id(item)))
    return tuple(out)


def _final_close(value,c,original,frames,result,result_original,pipe_original,backup_original,terminal_original=_TERMINAL_ABSENT):
    # All replaceable semantic/runtime/FD/time/schema helpers precede raw originals.
    c['backup'].close_copies();_core(value,terminal_original)
    current=_projection((c,c['runtime'].__dict__,backup_original));observed_result=_projection(result)
    pipe=c['pipe'];pipe.close_originals();runtime=c['runtime']
    observed_pid=os.getpid();observed_thread=threading.get_ident();now=time.monotonic()
    for frame in frames:raw(frame)
    for files,nodes,spaces in frames:
        for path,names in spaces:
            if tuple(sorted(os.listdir(path)))!=names:raise ValueError('parent-final-namespace')
        for path,stamp in nodes:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=stamp:raise ValueError('parent-final-node')
        for path,stamp in files:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:raise ValueError('parent-final-file')
    # Recompute primitive memory projections after the final physical callbacks.
    for item,wanted in (((c,c['runtime'].__dict__,backup_original),original),(result,result_original)):
        pending=[item];out=[]
        while pending:
            item=pending.pop();kind=type(item)
            if kind is dict:
                keys=tuple(sorted(item));out.append(('dict',keys));pending.extend(item[k] for k in reversed(keys))
            elif kind in (tuple,list):out.append((kind.__name__,len(item)));pending.extend(reversed(item))
            elif kind in (str,int,float,bool,bytes,type(None)):out.append((kind.__name__,item))
            else:out.append(('identity',id(kind),id(item)))
        if tuple(out)!=wanted:raise ValueError('parent-final-logical-original')
    if current!=original or observed_result!=result_original or _ACTIVE.get(value) is not c or backup_module._OBS.get(c['backup']) is not backup_original:raise ValueError('parent-final-registry')
    if (pipe.read_fd,pipe.write_fd,pipe.nonce,pipe.original,pipe.pid,pipe.thread)!=pipe_original or observed_pid!=c['pid'] or observed_thread!=c['thread'] or now>=c['deadline']:raise ValueError('parent-final-original-pipe-owner')
    if _RUNTIMES is not c['runtime_table'] or _RUNTIMES.get(runtime) is not c['runtime_registry']:raise ValueError('parent-final-original-runtime-registry')
    if _TERMINALS is not c['terminal_table']:raise ValueError('parent-final-original-terminal-table')
    if terminal_original is _TERMINAL_ABSENT:
        if runtime in _TERMINALS:raise ValueError('parent-final-original-terminal-absence')
    elif runtime not in _TERMINALS or _TERMINALS.get(runtime) is not terminal_original:raise ValueError('parent-final-original-terminal-registry')
    driver=c['driver']
    if driver is None or runtime.process is not driver[0] or (runtime.process.pid,runtime.process.stdin,runtime.process.stdout,runtime.process.stderr)!=driver[1:]:raise ValueError('parent-final-original-driver')


def collect(value):
    c=_core(value);need(c['phase']=='released','parent-collect-once');plan=c['plan'];pipe=c['pipe'];runtime=c['runtime']
    backup_original=backup_module._OBS[c['backup']]
    # Original copy/source frames and object identities precede receive/schema callbacks.
    frames=(c['plan_frame'],backup_original['copies'],backup_original['source_code'])
    pipe_original=(pipe.read_fd,pipe.write_fd,pipe.nonce,pipe.original,pipe.pid,pipe.thread)
    original=_projection((c,runtime.__dict__,backup_original))
    result=pipe.receive('worker-result',plan['challenge']);result_original=_projection(result)
    received=pipe.last_received;result_digest=hashlib.sha256(received).hexdigest()
    need(type(result) is dict and set(result)=={'version','phase','pack_id','member_id','selected_members','retained_observed_members','review_members','uncertain','imported_members','cleanup_grant','ordinary_import_grant','historical_import_ack','reader_index_acceptance','automatic_replay'} and type(result['version']) is int and result['version']==1 and result['phase'] in ('retained-observed','uncertain-review') and type(result['uncertain']) is bool and all(type(result[k]) is int and result[k] in (0,1) for k in ('selected_members','retained_observed_members','review_members','imported_members')) and result['selected_members']==1 and result['retained_observed_members']==int(result['phase']=='retained-observed') and result['review_members']==int(result['phase']!='retained-observed') and result['uncertain'] is (result['phase']=='uncertain-review') and result.get('pack_id')==plan['pack_id'] and result.get('member_id')==plan['member_id'] and result.get('imported_members')==0 and all(result.get(k) is False for k in ('cleanup_grant','ordinary_import_grant','historical_import_ack','reader_index_acceptance','automatic_replay')),'parent-factual-only-result')
    payload=dict(result_sha256=result_digest,pack_id=plan['pack_id'],member_id=plan['member_id'],worker_pid=plan['worker_pid'],publication=False,ordinary_import=False,index=False,cleanup=False,replay=False,resume=False)
    release=encode(dict(version=1,kind='observed-release',nonce=plan['nonce'],sequence=pipe.sequence,challenge=plan['challenge'],payload=payload))+b'\n'
    need(len(release)<=control_module.FRAME_BYTES,'parent-release-bound')
    _final_close(value,c,original,frames,result,result_original,pipe_original,backup_original)
    # No serializer/schema/need callback follows complete closure before direct write.
    if os.write(pipe.write_fd,release)!=len(release):raise ValueError('parent-release-unknown-no-replay')
    pipe.sequence+=1
    ack=pipe.receive('observed-final-ACK',plan['challenge'])
    need(ack==payload and encode(ack)==encode(payload),'parent-final-original-result-ACK')
    # Child waits for this precise final receipt before natural exit.
    _final_close(value,c,original,frames,result,result_original,pipe_original,backup_original)
    final=encode(dict(version=1,kind='observed-exit',nonce=plan['nonce'],sequence=pipe.sequence,challenge=plan['challenge'],payload=payload))+b'\n'
    need(len(final)<=control_module.FRAME_BYTES,'parent-final-exit-bound')
    _final_close(value,c,original,frames,result,result_original,pipe_original,backup_original)
    if os.write(pipe.write_fd,final)!=len(final):raise ValueError('parent-final-exit-unknown-no-replay')
    pipe.sequence+=1
    # Only after same-channel ACK and exact exit frame can this original child exit.
    terminal_original=(runtime.selected,runtime.selected_started,runtime.selected_static,runtime.process)
    if _TERMINALS is not c['terminal_table'] or runtime in _TERMINALS:raise ValueError('parent-exclusive-original-terminal-absence')
    _TERMINALS[runtime]=terminal_original
    process=runtime.process;need(process is not None and process.wait(timeout=max(.001,c['deadline']-time.monotonic()))==0,'parent-original-child-exit-ACK')
    _final_close(value,c,original,frames,result,result_original,pipe_original,backup_original,terminal_original)
    c['phase']='observed';return dict(worker_result=result,reader_resume_grant=False,operational_custody_complete=False)


def challenge():return secrets.token_hex(32)


def operational_entry(*args,**kwargs):
    """No arbitrary inspect/quiescence callback can complete missing runtime custody."""
    need(len(args)==2 and not kwargs,'exact-retained-parent-entry')
    return run_operation(*args)

# Host lifecycle mechanism. It intentionally has no engine/inspect callback argument.
# The privileged caller invokes only this source-pinned helper; this code never
# escalates privileges or starts a daemon by itself.
class ConfiguredRuntime:
    def __init__(self,*a,**k):raise ValueError('Original configured runtime required')
    @classmethod
    def observe(cls,ids):
        need(type(ids) is dict and set(ids)=={'reader','native','worker'} and len(set(ids.values()))==3,'exact-runtime-identities')
        need(all(type(v) is str and len(v)==64 and all(c in '0123456789abcdef' for c in v) for v in ids.values()),'runtime-ID')
        value=object.__new__(cls);value.ids=dict(ids);value.started=time.time();value.pid=os.getpid();value.thread=threading.get_ident();value.deadline=time.monotonic()+TOTAL_SECONDS
        value.baseline={k:value.inspect(cid) for k,cid in ids.items()}
        need(value.baseline['reader']['State']['Running'] is True and value.baseline['reader']['State']['Paused'] is False,'reader-original-running')
        native=value.baseline['native']['State'];need(native['Running'] is True and native['Paused'] is False and native['Pid']>0,'native-original-running')
        worker=value.baseline['worker']['State'];need(worker['Running'] is False and worker['Status'] in ('created','exited'),'normal-worker-must-already-be-stopped')
        value.selected=None;value.quiescent=False;value.native_open=False;value.process=None
        _RUNTIMES[value]=encode(dict(ids=value.ids,baseline=value.baseline,pid=value.pid,thread=value.thread,deadline=value.deadline))
        return value
    def command(self,args):
        import subprocess
        need((os.getpid(),threading.get_ident())==(self.pid,self.thread) and time.monotonic()<self.deadline,'runtime-original-lifetime')
        try:result=subprocess.run(['docker',*args],capture_output=True,timeout=max(1,min(60,self.deadline-time.monotonic())),check=True)
        except (subprocess.SubprocessError,OSError):raise ValueError('runtime-command-failed-private-evidence-required') from None
        need(len(result.stdout)<=4*1024**2,'runtime-output-bound');return result.stdout
    def inspect(self,cid):
        rows=json.loads(self.command(['inspect',cid]));need(type(rows) is list and len(rows)==1 and rows[0]['Id']==cid,'runtime-fresh-inspect');return rows[0]
    def static(self,row):
        # Config may contain credentials; retain privately, never emit it.
        return encode(dict(Id=row['Id'],Image=row['Image'],Config=row['Config'],HostConfig=row['HostConfig'],Mounts=row['Mounts'],Networks={k:v['NetworkID'] for k,v in row['NetworkSettings']['Networks'].items()}))
    def quiesce(self):
        need(not self.quiescent,'runtime-quiesce-once')
        self.command(['pause',self.ids['native']]);self.command(['stop','--time','30',self.ids['reader']]);self.quiescent=True
        self.stopped_reader=self.inspect(self.ids['reader'])['State'];self.paused_native=self.inspect(self.ids['native'])['State'];self.close()
    def close(self):
        need(self in _RUNTIMES and _RUNTIMES[self]==encode(dict(ids=self.ids,baseline=self.baseline,pid=self.pid,thread=self.thread,deadline=self.deadline)),'original-runtime-seal')
        need(self.quiescent,'runtime-quiescence-required')
        for key,cid in self.ids.items():
            row=self.inspect(cid);need(self.static(row)==self.static(self.baseline[key]),'runtime-original-profile')
            if key=='reader':need(row['State']==self.stopped_reader and row['State']['Running'] is False,'reader-stopped-incarnation')
            elif key=='worker':need(row['State']==self.baseline[key]['State'],'normal-worker-stays-stopped')
            else:
                state=row['State'];before=self.baseline[key]['State']
                need(state['Pid']==before['Pid'] and state['StartedAt']==before['StartedAt'] and state['Running'] is True and state['Paused'] is (not self.native_open),'native-same-process-pause-phase')
        # Source-owned exact event refusal: no outside restart/start/unpause.
        until=str(time.time());data=self.command(['events','--since',str(self.started),'--until',until,'--format','{{json .}}'])
        counts={}
        for line in data.splitlines():
            event=json.loads(line);actor=event.get('Actor',{}).get('ID')
            if event.get('Type')!='container' or actor not in self.ids.values():continue
            action=event.get('Action',event.get('status'))
            if action not in ('pause','unpause','stop','kill','die','start','restart','destroy'):continue
            allowed={'pause','unpause'} if actor==self.ids['native'] else ({'stop','kill','die'} if actor==self.ids['reader'] else set())
            need(action in allowed,'runtime-unexpected-event')
            key=(actor,action);counts[key]=counts.get(key,0)+1;need(counts[key]<=1,'runtime-repeated-lifecycle-event')
            if actor==self.ids['native'] and action=='unpause':need(self.native_open,'native-unpause-before-owned-transition')
        if self.selected is not None:
            row=self.inspect(self.selected);terminal=_TERMINALS.get(self)
            need(self.static(row)==self.selected_static and row['State']['StartedAt']==self.selected_started,'selected-original-worker')
            if terminal is None:need(row['State']['Running'] is True and row['State']['Pid']==self.selected_pid,'selected-original-worker')
            else:need(terminal==(self.selected,self.selected_started,self.selected_static,self.process) and self.process.poll()==0 and row['State']['Running'] is False and row['State']['Status']=='exited' and row['State']['Pid']==0 and row['State']['ExitCode']==0 and row['State'].get('Paused') is False and not any(row['State'].get(k) for k in ('Restarting','Dead','OOMKilled')),'selected-original-terminal-exit')
    def open_native(self):
        self.close();need(not self.native_open,'native-open-once');self.native_open=True
        try:self.command(['unpause',self.ids['native']]);self.close()
        except Exception:
            # Unknown ACK keeps custody uncertain, never replay unpause or restart.
            raise
    def selected_profile(self,row):
        original=self.baseline['worker'];need(row['Image']==original['Image'],'selected-configured-image')
        need(len(row['Mounts'])<=MAX_MOUNTS,'selected-mount-bound')
        for mount in row['Mounts']:
            path=Path(mount['Destination']);need(all(not path.is_relative_to(Path(prefix)) and not Path(prefix).is_relative_to(path) for prefix in IMAGE_PREFIXES),'selected-runtime-overlay')
        mounts=lambda r:sorted((m['Source'],m['Destination'],m['RW'],m['Type']) for m in r['Mounts'])
        need(mounts(row)==mounts(original),'selected-no-new-mount')
        need(set(row['NetworkSettings']['Networks'])==set(original['NetworkSettings']['Networks']),'selected-existing-network')
        h=row['HostConfig'];need(not h.get('Privileged') and not h.get('CapAdd') and not h.get('PortBindings') and h.get('NetworkMode')!='host','selected-no-expanded-privilege')
        need(row['Config']['User']==original['Config']['User']=='1000:1000','selected-existing-user')
        for m in row['Mounts']:need(m['Destination']!='/var/run/docker.sock','selected-no-socket')
        need(h.get('ReadonlyRootfs') is True and h.get('CapDrop')==['ALL'] and 'no-new-privileges' in h.get('SecurityOpt',[]),'selected-exact-hardened-profile')
        return True

# The concrete root-owned launch prefix below remains default-disabled.
# Independent current terminal/restart proof is deliberately not inferred
# from a factual worker result or copied profile JSON.

    def native_observation(self,probe_ref,scope_ref,pins,nonce,config_ref):
        import subprocess
        import importlib.util
        need(NATIVE_PROBE_SOURCE_SHA is not None,'native-probe-pin-required')
        for ref in (probe_ref,scope_ref,config_ref):_strict_ref(ref)
        # All known references/parents fixed before any read/compile/HTTP callback.
        references=(probe_ref,scope_ref,config_ref);frame=(tuple((ref['path'],tuple(ref['signature9'])) for ref in references),tuple((str(q),five(os.lstat(q))) for ref in references for q in Path(ref['path']).parents),())
        raw(frame);need(probe_ref['sha256']==NATIVE_PROBE_SOURCE_SHA and scope_ref['sha256']==SCOPE_SOURCE_SHA,'native-exact-observer-code')
        actual_probe,code=_ref(probe_ref['path']);actual_scope,scope_code=_ref(scope_ref['path']);need(actual_probe==probe_ref and actual_scope==scope_ref,'native-code-original-FD')
        need(hashlib.sha256(code).hexdigest()==NATIVE_PROBE_SOURCE_SHA and hashlib.sha256(scope_code).hexdigest()==SCOPE_SOURCE_SHA,'native-observer-code-readback')
        need(type(pins) is dict and set(pins)=={'/app/mylar3/mylar/worker_health.py','/app/mylar3/mylar/native_writers.py'} and all(type(v) is str and len(v)==64 and all(c in '0123456789abcdef' for c in v) for v in pins.values()),'native-protected-daemon-source-roles')
        request=dict(version=1,nonce=nonce,source_sha256=NATIVE_PROBE_SOURCE_SHA,seconds=30,module_pins=pins,scope_source=scope_code.decode())
        raw(frame);before=self.inspect(self.ids['native'])
        need(self.static(before)==self.static(self.baseline['native']) and before['State']['Running'] is True and before['State']['Paused'] is False,'native-live-probe-phase')
        try:result=subprocess.run(['docker','exec','--interactive',self.ids['native'],'python3','-I','-B','-c',code.decode()],input=encode(request),capture_output=True,timeout=45,check=True)
        except (subprocess.SubprocessError,OSError):raise ValueError('native-source-probe-held') from None
        need(len(result.stdout)<=1024**2,'native-probe-output-bound');value=json.loads(result.stdout)
        need(set(value)=={'version','nonce','source_sha256','process','publication','config'} and type(value['version']) is int and value['version']==1 and value['nonce']==nonce and value['source_sha256']==NATIVE_PROBE_SOURCE_SHA,'native-source-observation-schema')
        module=importlib.util.module_from_spec(importlib.util.spec_from_loader('retained_geometry_parser',loader=None));exec(compile(scope_code,'retained_geometry_parser','exec'),module.__dict__)
        data=module.data_from_argv(value['process']['argv']);host=_mapped_host(before,data+'/config.ini')
        need(str(host)==config_ref['path'] and value['config']['path']==data+'/config.ini' and value['config']['sha256']==config_ref['sha256'],'native-config-launch-source-join')
        actual_config,_=_ref(host);need(actual_config==config_ref,'native-config-original-bytes')
        publication=value['publication'];need(type(publication) is dict and publication.get('state')=='ready','native-ordinary-admissible-required')
        after=self.inspect(self.ids['native']);need(self.static(after)==self.static(before) and after['State']['Pid']==before['State']['Pid'] and after['State']['StartedAt']==before['State']['StartedAt'],'native-probe-container-incarnation')
        answer=dict(data=data,process=value['process'],publication=publication,config=value['config'])
        raw(frame)
        for files,nodes,spaces in (frame,):
            for path,stamp in nodes:
                z=os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=stamp:raise ValueError('native-final-observer-node')
            for path,stamp in files:
                z=os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:raise ValueError('native-final-observer-file')
        return answer

    def launch(self,input_host,input_child,input_sha):
        import subprocess
        self.close();need(self.selected is None and not self.native_open,'selected-launch-once')
        original=self.baseline['worker'];networks=tuple(original['NetworkSettings']['Networks'])
        need(1<=len(networks)<=MAX_NETWORKS and original['Config']['User']=='1000:1000','bounded-configured-network-required')
        need(Path(input_host).is_absolute() and Path(input_child).is_absolute(),'selected-input-absolute')
        candidates=[m for m in original['Mounts'] if m['Type']=='bind' and Path(input_child).is_relative_to(Path(m['Destination']))]
        need(candidates,'selected-input-existing-mount')
        candidates.sort(key=lambda m:len(Path(m['Destination']).parts),reverse=True);m=candidates[0]
        need(Path(m['Source'])/Path(input_child).relative_to(m['Destination'])==Path(input_host),'selected-input-original-mapping')
        initial=nine(os.lstat(input_host));need(initial[5]&0o170000==0o100000 and initial[5]&0o7777==0o600 and initial[8]==1,'selected-input-private')
        input_ref,_=_ref(input_host);need(input_ref['sha256']==input_sha and tuple(input_ref['signature9'])==initial,'selected-input-source-pin')
        args=['create','--pull','never','--interactive','--read-only','--network',networks[0],'--user','1000:1000','--cap-drop','ALL','--security-opt','no-new-privileges','--entrypoint','python3']
        for mount in original['Mounts']:
            need(mount['Type']=='bind' and not any(c in mount['Source']+mount['Destination'] for c in ',\n\r'),'selected-exact-bind-only')
            args+=['--mount','type=bind,src='+mount['Source']+',dst='+mount['Destination']+('' if mount['RW'] else ',readonly')]
        # Existing configured environment is retained privately, never printed.
        for item in original['Config']['Env']:args+=['--env',item]
        args+=[original['Image'],'-I','-B','/app/retained_pack_control.py','--input',str(input_child),'--input-sha256',input_sha]
        self.close();cid=self.command(args).decode().strip();need(len(cid)==64 and all(c in '0123456789abcdef' for c in cid),'selected-created-ID')
        for network in networks[1:]:self.command(['network','connect',network,cid])
        created=self.inspect(cid);self.selected_profile(created)
        need(created['Config']['Entrypoint']==['python3'] and created['Config']['Cmd']==args[-7:],'selected-exact-command')
        self.selected=cid;self.selected_static=self.static(created)
        self.process=subprocess.Popen(['docker','start','--attach','--interactive',cid],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        # No background replayer/restart. Initialized frame is the first worker ACK.
        return self.process
    def bind_running(self):
        need(self.selected is not None,'owning-selected-child-required');row=self.inspect(self.selected);self.selected_profile(row)
        need(self.static(row)==self.selected_static and row['State']['Running'] is True and row['State']['Pid']>0,'selected-original-running-profile')
        self.selected_started=row['State']['StartedAt'];self.selected_pid=row['State']['Pid'];self.close()


def _mapped_host(row,child):
    child=Path(child);need(child.is_absolute() and '..' not in child.parts,'configured-child-path')
    matches=[m for m in row['Mounts'] if m['Type']=='bind' and child.is_relative_to(Path(m['Destination']))]
    need(matches,'existing-configured-bind-required');matches.sort(key=lambda m:len(Path(m['Destination']).parts),reverse=True)
    need(len(matches)==1 or len(Path(matches[0]['Destination']).parts)!=len(Path(matches[1]['Destination']).parts),'ambiguous-configured-bind')
    m=matches[0];return Path(m['Source'])/child.relative_to(m['Destination'])


def _strict_ref(ref):
    need(type(ref) is dict and set(ref)=={'path','sha256','signature9'} and type(ref['path']) is str and type(ref['sha256']) is str and len(ref['sha256'])==64 and all(c in '0123456789abcdef' for c in ref['sha256']) and type(ref['signature9']) is list and len(ref['signature9'])==9 and all(type(v) is int for v in ref['signature9']),'exact-original-reference')
    return ref


def _ref(path):
    path=Path(path);stamp=nine(os.lstat(path));need(stamp[5]&0o170000==0o100000 and stamp[8]==1,'regular-original-reference');need(stamp[2]<=1024*1024,'control-reference-byte-bound')
    nodes=tuple((str(p),five(os.lstat(p))) for p in path.parents);parent=dict(nodes)[str(path.parent)]
    directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        need(five(os.fstat(directory))==parent,'reference-original-parent-FD')
        fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=directory)
        try:
            need(nine(os.fstat(fd))==stamp,'reference-original-leaf-FD');parts=[];size=0
            while chunk:=os.read(fd,65536):
                size+=len(chunk);need(size<=1024*1024,'reference-stream-bound');parts.append(chunk)
            data=b''.join(parts);need(nine(os.fstat(fd))==stamp,'reference-original-read-FD')
        finally:os.close(fd)
        need(nine(os.stat(path.name,dir_fd=directory,follow_symlinks=False))==stamp and five(os.fstat(directory))==parent,'reference-original-relative-CAS')
    finally:os.close(directory)
    raw((((str(path),stamp),),nodes,()))
    return dict(path=str(path),sha256=hashlib.sha256(data).hexdigest(),signature9=list(stamp)),data


def _exclusive(path,data,uid,gid):
    path=Path(path);parent=five(os.lstat(path.parent));need(not os.path.lexists(path),'exclusive-control-absence')
    d=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        need(five(os.fstat(d))==parent,'control-parent-FD')
        fd=os.open(path.name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=d)
        try:
            created=nine(os.fstat(fd));need(created[5]&0o7777==0o600 and created[8]==1,'control-created-original')
            offset=0
            while offset<len(data):offset+=os.write(fd,data[offset:])
            os.fchown(fd,uid,gid);os.fsync(fd);stamp=nine(os.fstat(fd))
            need(stamp[5]&0o7777==0o600 and stamp[6:]==(uid,gid,1) and stamp[:2]==created[:2],'control-owned-output')
        finally:os.close(fd)
        os.fsync(d);need(nine(os.stat(path.name,dir_fd=d,follow_symlinks=False))==stamp and five(os.fstat(d))==parent,'control-durable-original')
    finally:os.close(d)
    return dict(path=str(path),sha256=hashlib.sha256(data).hexdigest(),signature9=list(stamp))


def run_operation(plan_ref,source_ref):
    """Concrete root-owned prefix. Factual result retains reader/worker stop;
    no resumed-service or completed-feature claim without terminal observer.
    """
    need(ENABLED is True and PRIMITIVES_SOURCE_SHA is not None and NATIVE_PROBE_SOURCE_SHA is not None and BACKUP_SOURCE_SHA is not None,'parent-default-disabled')
    need(os.geteuid()==0,'owning-root-runtime-required')
    early_refs=(_strict_ref(plan_ref),_strict_ref(source_ref))
    early_frame=(tuple((q['path'],tuple(q['signature9'])) for q in early_refs),tuple((str(parent),five(os.lstat(parent))) for q in early_refs for parent in Path(q['path']).parents),())
    raw(early_frame)
    ref,data=_ref(plan_ref['path']);need(ref==plan_ref,'original-root-plan')
    own,_=_ref(Path(__file__).absolute());need(own==source_ref,'original-parent-source')
    plan=json.loads(data);need(encode(plan)==data and set(plan)=={'version','kind','nonce','pack_id','member_id','containers','worker_manifest','output_root','primitives','native_probe','scope_source','native_module_pins','native_config_ref','worker_config_ref','backup_observer','control_source'},'retained-root-plan-schema')
    need(type(plan['version']) is int and plan['version']==1 and plan['kind']=='retained-pack-preproof-runtime-v1','retained-root-plan-kind')
    need(all(type(plan[k]) is str and len(plan[k])==64 and all(c in '0123456789abcdef' for c in plan[k]) for k in ('nonce','pack_id','member_id')),'retained-root-selection')
    # Original plan-bound control facts precede the first runtime observation.
    bound_refs=tuple(_strict_ref(plan[k]) for k in ('worker_config_ref','worker_manifest','native_probe','scope_source','native_config_ref','primitives','backup_observer','control_source'))
    original_files=((ref['path'],tuple(ref['signature9'])),(own['path'],tuple(own['signature9'])))+tuple((q['path'],tuple(q['signature9'])) for q in bound_refs)
    source_frame=(original_files,early_frame[1]+tuple((str(q),five(os.lstat(q))) for path,_ in original_files for q in Path(path).parents),())
    raw(source_frame)
    import comic_retained_pack_backup as observer
    import retained_pack_control as control
    for module,key,pin in ((observer,'backup_observer',BACKUP_SOURCE_SHA),(control,'control_source',plan['control_source']['sha256'])):
        need(str(Path(module.__file__).absolute())==plan[key]['path'] and plan[key]['sha256']==pin,'owning-imported-source-reference')
        observed,_=_ref(plan[key]['path']);need(observed==plan[key],'owning-imported-source-original')
    raw(source_frame)
    runtime=ConfiguredRuntime.observe(plan['containers']);worker=runtime.baseline['worker']
    need(worker['Config']['Entrypoint']==['python3','/app/normalize.py'],'configured-worker-command')
    cmd=worker['Config']['Cmd'];need(cmd in ([],['--once']) or len(cmd)==2 and cmd[0]=='--config','configured-worker-args')
    config_child=cmd[1] if len(cmd)==2 else '/config/normalizer.json';config_host=_mapped_host(worker,config_child)
    need(str(config_host)==plan['worker_config_ref']['path'],'worker-fixed-config-original-path')
    config_ref,cfg_bytes=_ref(config_host);need(config_ref==plan['worker_config_ref'],'worker-original-config-reference');cfg=json.loads(cfg_bytes)
    observation=runtime.native_observation(plan['native_probe'],plan['scope_source'],plan['native_module_pins'],plan['nonce'],plan['native_config_ref'])
    state_child=cfg.get('state','/state');state_host=_mapped_host(worker,state_child)
    manifest,manifest_bytes=_ref(plan['worker_manifest']['path']);need(manifest==plan['worker_manifest'],'worker-original-module-map')
    manifest_child=next((str(Path(m['Destination'])/Path(manifest['path']).relative_to(m['Source'])) for m in worker['Mounts'] if m['Type']=='bind' and Path(manifest['path']).is_relative_to(m['Source'])),None)
    need(manifest_child is not None,'module-map-existing-bind-required')
    module_map=json.loads(manifest_bytes);need(module_map.get('retained_pack_control.py')==plan['control_source']['sha256'],'installed-control-source-map')
    output=Path(plan['output_root']);need(output.is_absolute() and output.is_dir() and five(os.lstat(output))[2]&0o7777==0o700,'private-output-root')
    scopes=[dict(role='native_config',root=str(_mapped_host(runtime.baseline['native'],'/config')),databases=[str(Path(observation['data'])/name) for name in ('mylar.db','workflow.sqlite')]),
            dict(role='worker_state',root=str(state_host),databases=[]),
            dict(role='reader_config',root=str(_mapped_host(runtime.baseline['reader'],'/config')),databases=['database.sqlite','tasks.sqlite'])]
    native_data_host=_mapped_host(runtime.baseline['native'],observation['data']);native_root=Path(scopes[0]['root'])
    need(native_data_host.is_relative_to(native_root),'native-data-in-covered-config-required')
    scopes[0]['databases']=[str(native_data_host.relative_to(native_root)/name) for name in ('mylar.db','workflow.sqlite')]
    need(all((native_root/name).is_file() for name in scopes[0]['databases']),'native-actual-database-required')
    need(plan['primitives']['sha256']==PRIMITIVES_SOURCE_SHA,'neutral-primitives-source-pin')
    for path in (state_host,Path(manifest['path']),config_host,output):need(not path.is_symlink(),'original-configured-path')
    raw(source_frame);nonce=plan['nonce'];ch=challenge()
    worker_input=state_host/('retained-control-'+nonce+'.json');worker_input_child=str(Path(state_child)/worker_input.name)
    child_body=dict(version=1,nonce=nonce,parent_sha=own['sha256'],config=config_child,config_sha256=config_ref['sha256'],config_signature9=config_ref['signature9'],pack_id=plan['pack_id'],member_id=plan['member_id'],challenge=ch,worker_manifest=manifest_child,worker_manifest_sha256=manifest['sha256'],worker_manifest_signature9=manifest['signature9'])
    lock_ref,_=_ref(state_host/'worker.lock');child_body['worker_lock_signature9']=lock_ref['signature9']
    input_ref=_exclusive(worker_input,encode(child_body),1000,1000)
    # Initialization/control inputs precede the verified backup lifetime.
    runtime.quiesce();raw(source_frame)
    process=runtime.launch(worker_input,worker_input_child,input_ref['sha256'])
    runtime.bind_running()
    conversation_body=dict(version=1,kind='retained-pack-preproof-conversation-v1',nonce=nonce,pack_id=plan['pack_id'],member_id=plan['member_id'],journal_host=str(state_host/'maintenance/retained-pack-handoffs'),worker_pid=1,backup_scopes=scopes,backup_output=str(output/nonce),primitives=plan['primitives'],challenge=ch)
    conversation_path=output/('conversation-'+nonce+'.json');conversation_ref=_exclusive(conversation_path,encode(conversation_body),0,0)
    parent=from_original_pipe(conversation_ref,source_ref,process.stdout.fileno(),process.stdin.fileno(),runtime)
    initialized(parent);backup(parent);raw(source_frame)
    runtime.open_native()
    repeated=runtime.native_observation(plan['native_probe'],plan['scope_source'],plan['native_module_pins'],plan['nonce'],plan['native_config_ref'])
    need(repeated==observation,'native-original-process-config-publication-after-pause')
    release_backup(parent)
    result=collect(parent);raw(source_frame)
    # Deliberately no automatic restart or backup cleanup: current returned view
    # is factual, not an independent source-bound native terminal/resume proof.
    return result


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--input-sha256',required=True);parser.add_argument('--source-sha256',required=True);args=parser.parse_args()
    need(ENABLED is True,'parent-default-disabled')
    paths=(Path(args.input),Path(__file__).absolute());initial=tuple((str(q),nine(os.lstat(q))) for q in paths);nodes=tuple((str(a),five(os.lstat(a))) for q in paths for a in q.parents)
    plan,_=_ref(args.input);own,_=_ref(Path(__file__).absolute());raw((initial,nodes,()))
    need(plan['sha256']==args.input_sha256 and own['sha256']==args.source_sha256,'owning-entry-source-input')
    result=run_operation(plan,own)
    print(encode(result).decode())

if __name__=='__main__':main()
