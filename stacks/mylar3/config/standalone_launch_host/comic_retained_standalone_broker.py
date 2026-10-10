"""Fixed root-owned standalone launch. Public defaults grant no installation authority."""
import hashlib
import copy
import importlib.util
import json
import os
from pathlib import Path
import select
import sys
import subprocess
import threading
import time
import weakref

ENROLLMENT = Path('/etc/mylar-publication-launch/enrollment-v1.json')
INSTALLATION = Path('/etc/mylar-publication-launch/deployment-v1.json')
PACKAGE = Path('/usr/local/lib/mylar-publication-launch')
KEY = Path('/var/lib/mylar-publication-launch/root-signing-ed25519.der')
ROOT_UID = 0
LIMIT = 65536
SOURCE_LIMIT = 4*1024**2
PREAUTH_SECONDS = 5
TOTAL_SECONDS = 3600
LOGICAL_PROFILE_SHA = hashlib.sha256(b'standalone-retained-recovery-policy-v1:original-existing-bind-or-named-volume:readonly-uid1000-capdrop-all-no-new-privileges-network-none:no-new-mounts:no-overlay:four-full-roles:3600-1800-120-180:512GiB:100000:no-resume-import-cleanup-index-replay').hexdigest()
REGISTRY_LIMIT = 512  # exact owning publication_guard registry ceiling
NAMES = ('private_crypto.py','comic_reader_backup_primitives.py',
         'comic_retained_standalone_backup.py','comic_retained_standalone_parent.py',
         'comic_retained_standalone_broker.py','comic_native_process_probe.py',
         'publication_native_configured_scope.py','BOOTSTRAP.py')
_INSTALLATIONS = weakref.WeakKeyDictionary()
_LAUNCHES = weakref.WeakKeyDictionary()
_INSTALLATION_SEALS = weakref.WeakKeyDictionary()
_LAUNCH_SEALS = weakref.WeakKeyDictionary()
_LOADED_MODULES = {}
_PHASES = weakref.WeakKeyDictionary()
_EXITS = weakref.WeakKeyDictionary()

class Held(ValueError): pass

def canonical(value):
    data=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')
    if not 0<len(data)<=LIMIT:raise Held('fixed-launch-frame-bound')
    return data

def sha(data):return hashlib.sha256(data).hexdigest()
def hexadecimal(value):return type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value)
def nine(z):return (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
def five(z):return (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)

def parse(data):
    def pairs(rows):
        result={}
        for key,value in rows:
            if key in result:raise Held('fixed-launch-duplicate')
            result[key]=value
        return result
    value=json.loads(data,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(Held('fixed-launch-number')))
    if type(value) is not dict or canonical(value)!=data:raise Held('fixed-launch-canonical')
    return value

def capture(paths):
    leaves={};nodes={}
    for path in paths:
        path=Path(path)
        for parent in path.parents:
            z=os.lstat(parent);fact=five(z)
            if z.st_mode&0o170000!=0o040000 or z.st_uid not in (0,ROOT_UID) or z.st_mode&0o022:raise Held('fixed-launch-root-ancestor')
            if parent in nodes and nodes[parent]!=fact:raise Held('fixed-launch-first-ancestor')
            nodes.setdefault(parent,fact)
        z=os.lstat(path)
        if z.st_mode&0o170000!=0o100000 or z.st_uid!=ROOT_UID or z.st_mode&0o022 or z.st_nlink!=1:raise Held('fixed-launch-root-file')
        leaves[path]=nine(z)
    return (tuple(leaves.items()),tuple(nodes.items()))

def raw(frame):
    for path,original in frame[1]:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=original:raise Held('fixed-launch-original-node')
    for path,original in frame[0]:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=original:raise Held('fixed-launch-original-file')

def read(path,frame):
    expected=dict(frame[0])[Path(path)];fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        if nine(os.fstat(fd))!=expected:raise Held('fixed-launch-original-FD')
        data=bytearray()
        while chunk:=os.read(fd,65536):
            data.extend(chunk)
            if len(data)>SOURCE_LIMIT:raise Held('fixed-launch-source-bound')
        if nine(os.fstat(fd))!=expected:raise Held('fixed-launch-FD-drift')
    finally:
        try:z=os.fstat(fd)
        except OSError:z=None
        if z is not None and (z.st_dev,z.st_ino,z.st_mode&0o170000)==(expected[0],expected[1],expected[5]&0o170000):os.close(fd)
    raw(frame)
    return bytes(data)

class Installation:
    def __init__(self,*args,**kwargs):raise Held('fixed-root-installation-required')
    def close(self):
        row=_INSTALLATIONS.get(self);seal=_INSTALLATION_SEALS.get(self)
        if row is None or seal is None or seal[0] is not row:raise Held('fixed-installation-original')
        original_frame,original_bytes,original_owner,original_deadline,original_modules,original_public,original_document=seal[1:]
        if (os.getpid(),threading.get_ident())!=original_owner or time.monotonic()>original_deadline:raise Held('fixed-installation-original')
        encoded=canonical(row['document'])
        # Serialization and all declared helpers precede copied original closure.
        raw(original_frame)
        for path,original in original_frame[1]:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=original:raise Held('fixed-installation-final-node')
        for path,original in original_frame[0]:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=original:raise Held('fixed-installation-final-file')
        pending=[(row['document'],original_document)]
        while pending:
            actual,expected=pending.pop()
            if type(actual) is not type(expected):raise Held('fixed-installation-final-document-type')
            if type(expected) is dict:
                if actual.keys()!=expected.keys():raise Held('fixed-installation-final-document-keys')
                pending.extend((actual[key],expected[key]) for key in expected)
            elif type(expected) in (list,tuple):
                if len(actual)!=len(expected):raise Held('fixed-installation-final-document-length')
                pending.extend(zip(actual,expected))
            elif actual!=expected:raise Held('fixed-installation-final-document-value')
        if encoded!=original_bytes or row['bytes']!=original_bytes or row['frame']!=original_frame or row['owner']!=original_owner or row['deadline']!=original_deadline or row['public']!=original_public:raise Held('fixed-installation-logical')
        if len(row['modules'])!=len(original_modules) or any(row['modules'].get(name) is not module for name,module in original_modules):raise Held('fixed-installation-module-identity')
        if _INSTALLATIONS.get(self) is not row or _INSTALLATION_SEALS.get(self) is not seal:raise Held('fixed-installation-registry')
        return row


def load_original_installation():
    if os.geteuid()!=ROOT_UID:raise Held('fixed-root-broker-process-required')
    # All fixed root sources are originals before the first read/parse/import.
    try:frame=capture((ENROLLMENT,INSTALLATION,KEY,*[PACKAGE/name for name in NAMES]))
    except FileNotFoundError:raise Held('reviewed-root-installation-unprovisioned') from None
    marker=parse(read(ENROLLMENT,frame))
    if set(marker)!={'version','kind','deployment_sha256'} or type(marker['version']) is not int or marker['version']!=1 or marker['kind']!='standalone-root-enrollment-v1' or not hexadecimal(marker['deployment_sha256']):raise Held('fixed-enrollment-schema')
    data=read(INSTALLATION,frame)
    if sha(data)!=marker['deployment_sha256']:raise Held('fixed-installation-digest')
    value=parse(data)
    fields={'version','kind','deployment','image','profile','runtime_profile_sha256','broker_sources','parent_sha256',
            'bootstrap_sha256','inventory_sha256','anchor_sha256','key_sha256','public_der','host_sources','daemon_sources','ids'}
    if set(value)!=fields or type(value['version']) is not int or value['version']!=1 or value['kind']!='standalone-root-deployment-v1':raise Held('fixed-installation-schema')
    if not all(hexadecimal(value[k]) for k in fields-{'version','kind','public_der','host_sources','daemon_sources','ids'}):raise Held('fixed-installation-claims')
    if value['profile']!=LOGICAL_PROFILE_SHA:raise Held('fixed-source-owned-logical-policy')
    public=bytes.fromhex(value['public_der'])
    if len(public)!=44 or public[:12]!=bytes.fromhex('302a300506032b6570032100') or sha(public)!=value['key_sha256']:raise Held('fixed-installation-public-key')
    if set(value['host_sources'])!=set(NAMES) or not all(hexadecimal(x) for x in value['host_sources'].values()):raise Held('fixed-installation-source-map')
    if type(value['daemon_sources']) is not dict or set(value['daemon_sources'])!={'/app/mylar3/mylar/worker_health.py','/app/mylar3/mylar/native_writers.py'} or not all(hexadecimal(x) for x in value['daemon_sources'].values()):raise Held('fixed-daemon-source-pins')
    if sha(canonical(value['host_sources']))!=value['broker_sources'] or value['host_sources']['comic_retained_standalone_parent.py']!=value['parent_sha256'] or value['host_sources']['BOOTSTRAP.py']!=value['bootstrap_sha256']:raise Held('fixed-installation-owning-pin-joins')
    if set(value['ids'])!={'native','reader','worker'} or not all(hexadecimal(x) for x in value['ids'].values()) or len(set(value['ids'].values()))!=3:raise Held('fixed-installation-runtime-IDs')
    modules={}
    for name in NAMES:
        source=read(PACKAGE/name,frame)
        if sha(source)!=value['host_sources'][name]:raise Held('fixed-installation-source-digest')
        if name=='comic_retained_standalone_broker.py':
            if Path(__file__).absolute()!=PACKAGE/name:raise Held('fixed-broker-original-installation-origin')
            continue
        if name in ('BOOTSTRAP.py','comic_native_process_probe.py'):continue
        module_name=name[:-3]
        existing=sys.modules.get(module_name)
        if existing is not None and (Path(existing.__file__).absolute()!=PACKAGE/name or _LOADED_MODULES.get(module_name)!=(existing,sha(source))):raise Held('fixed-host-module-origin')
        if existing is None:
            spec=importlib.util.spec_from_file_location(module_name,PACKAGE/name)
            module=importlib.util.module_from_spec(spec);sys.modules[module_name]=module
            try:exec(compile(source,str(PACKAGE/name),'exec'),module.__dict__)
            except BaseException:
                if sys.modules.get(module_name) is module:del sys.modules[module_name]
                raise
        else:module=existing
        raw(frame);_LOADED_MODULES[module_name]=(module,sha(source))
        modules[name]=module;raw(frame)
    obj=object.__new__(Installation)
    _INSTALLATIONS[obj]=dict(document=value,bytes=data,frame=frame,modules=modules,public=public,
                            owner=(os.getpid(),threading.get_ident()),deadline=time.monotonic()+TOTAL_SECONDS)
    row=_INSTALLATIONS[obj]
    _INSTALLATION_SEALS[obj]=(row,frame,data,row['owner'],row['deadline'],tuple(modules.items()),public,json.loads(data))
    obj.close();return obj


def process_start(pid):
    with open('/proc/'+str(pid)+'/stat','rb') as stream:
        data=stream.read(65536)
    return data.rsplit(b')',1)[1].split()[19].decode('ascii')

class OriginalLaunch:
    def __init__(self,*args,**kwargs):raise Held('fixed-original-launch-required')
    def close(self):
        state=_LAUNCHES.get(self)
        seal=_LAUNCH_SEALS.get(self)
        if state is None or seal is None or seal[0] is not state:raise Held('fixed-launch-original-registry')
        original=seal[1];phase=_PHASES.get(self)
        if phase is None or tuple(state.get(key) for key in ('deadline','admission','sequence','previous','auth_challenge'))!=phase:raise Held('fixed-launch-original-phase')
        if any(state.get(key) is not value for key,value in original['objects']):raise Held('fixed-launch-original-objects')
        if any(state.get(key)!=value for key,value in original['values']):raise Held('fixed-launch-original-values')
        installation=state['installation'];row=installation.close();runtime=state['runtime']
        terminal_present=self in _EXITS;terminal_original=_EXITS[self] if terminal_present else None
        if terminal_present:
            if type(terminal_original) is not tuple or len(terminal_original)!=4:raise Held('fixed-own-terminal-shape')
            runtime.close(terminal_original)
        else:runtime.close()
        process=state['process'];now=time.monotonic()
        if type(runtime) is not row['modules']['comic_retained_standalone_parent.py'].ConfiguredRuntime or runtime.process is not process or runtime.selected!=state['cid'] or runtime.selected_started!=state['started'] or runtime.selected_pid!=state['selected_pid']:raise Held('fixed-launch-runtime-identity')
        if process.pid!=state['attach_pid'] or (not terminal_present and (process.poll() is not None or process_start(state['selected_pid'])!=state['start'])) or (terminal_present and process.poll()!=0):raise Held('fixed-launch-process-incarnation')
        if (os.getpid(),threading.get_ident())!=state['owner'] or now>state['deadline']:raise Held('fixed-launch-owner-lifetime')
        if process.stdin is not state['stdin'] or process.stdout is not state['stdout']:raise Held('fixed-launch-pipe-objects')
        for fd,fact in state['pipes']:
            if nine(os.fstat(fd))!=fact:raise Held('fixed-launch-original-pipe')
        parent=row['modules']['comic_retained_standalone_parent.py']
        parent.raw(state['bootframe']);parent.raw(state['inputframe']);raw(row['frame'])
        # No replaceable closure helper after these original physical checks.
        for frame in (state['bootframe'],state['inputframe']):
            for path,expected in frame[1]:
                z=os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=expected:raise Held('fixed-launch-original-input-node')
            for path,expected in frame[0]:
                z=os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=expected:raise Held('fixed-launch-original-input-file')
        for path,expected in row['frame'][1]:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=expected:raise Held('fixed-launch-final-source-node')
        for path,expected in row['frame'][0]:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=expected:raise Held('fixed-launch-final-source')
        pending=[(state['boot'],original['boot']),(state['preflight'],original['preflight']),(state['recovery'],original['recovery'])]
        while pending:
            actual,expected=pending.pop()
            if type(actual) is not type(expected):raise Held('fixed-launch-original-boot-type')
            if type(expected) is dict:
                if actual.keys()!=expected.keys():raise Held('fixed-launch-original-boot-keys')
                pending.extend((actual[key],expected[key]) for key in expected)
            elif type(expected) is list:
                if len(actual)!=len(expected):raise Held('fixed-launch-original-boot-length')
                pending.extend(zip(actual,expected))
            elif actual!=expected:raise Held('fixed-launch-original-boot-value')
        if any(state.get(key) is not value for key,value in original['objects']) or any(state.get(key)!=value for key,value in original['values']):raise Held('fixed-launch-final-originals')
        if (self in _EXITS)!=terminal_present or (terminal_present and _EXITS[self] is not terminal_original):raise Held('fixed-launch-final-exit-registry')
        if row['modules']['comic_retained_standalone_parent.py']._RUNTIMES is not original['runtime_table'] or row['modules']['comic_retained_standalone_parent.py']._TERMINALS is not original['terminal_table'] or row['modules']['comic_retained_standalone_parent.py']._RUNTIMES.get(runtime) is not original['runtime_registry']:raise Held('fixed-launch-final-runtime-registry')
        if (runtime in parent._TERMINALS)!=terminal_present or (terminal_present and parent._TERMINALS[runtime] is not terminal_original):raise Held('fixed-launch-final-terminal-registry')
        if _LAUNCHES.get(self) is not state or _LAUNCH_SEALS.get(self) is not seal or _PHASES.get(self) is not phase or tuple(state.get(key) for key in ('deadline','admission','sequence','previous','auth_challenge'))!=phase:raise Held('fixed-launch-final-registry')
        return state

def _image(value):
    if type(value) is not str or not value.startswith('sha256:') or not hexadecimal(value[7:]):raise Held('fixed-original-image')
    return value[7:]


def _host_original_ref(reference, mounts):
    """Translate a CHILD pathname only; preserve its original bytes/hash/full9."""
    if type(reference) is not dict or set(reference)!={'path','sha256','signature9'} or type(reference['path']) is not str or not hexadecimal(reference['sha256']) or type(reference['signature9']) not in (list,tuple) or len(reference['signature9'])!=9 or any(type(v) is not int for v in reference['signature9']):raise Held('fixed-child-control-reference')
    reference_original=(reference['path'],reference['sha256'],tuple(reference['signature9']))
    mount_original=tuple((row.get('Type'),row.get('Source'),row.get('Destination'),row.get('RW'),row.get('Name')) for row in mounts)
    child=Path(reference['path'])
    if not child.is_absolute() or str(child)!=reference['path'] or '..' in child.parts:raise Held('fixed-child-control-path')
    candidates=[];destinations=set()
    for mount in mounts:
        if type(mount) is not dict or not all(k in mount for k in ('Type','Source','Destination','RW')):raise Held('fixed-original-mount-schema')
        source=Path(mount['Source']);destination=Path(mount['Destination'])
        if not source.is_absolute() or not destination.is_absolute() or str(source)!=mount['Source'] or str(destination)!=mount['Destination'] or '..' in source.parts or '..' in destination.parts or type(mount['RW']) is not bool:raise Held('fixed-original-mount-path')
        if destination in destinations:raise Held('fixed-original-mount-ambiguity')
        destinations.add(destination)
        if child.is_relative_to(destination):candidates.append((destination,source,mount['Type'],mount.get('Name')))
    if not candidates:raise Held('fixed-unmapped-child-control')
    candidates.sort(key=lambda row:len(row[0].parts),reverse=True)
    # Control custody does not admit a nested mount shadow of the owning bind.
    if len(candidates)!=1 or candidates[0][2] not in ('bind','volume'):raise Held('fixed-child-control-shadow')
    destination,source,kind,name=candidates[0]
    if kind=='volume' and (type(name) is not str or not 1<=len(name)<=256 or not name[0].isalnum() or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-' for c in name)):raise Held('fixed-child-control-volume-name')
    host=source/child.relative_to(destination)
    original=tuple(reference['signature9'])
    z=os.lstat(host)
    if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=original:raise Held('fixed-child-control-original-nine')
    if tuple((row.get('Type'),row.get('Source'),row.get('Destination'),row.get('RW'),row.get('Name')) for row in mounts)!=mount_original or (reference['path'],reference['sha256'],tuple(reference['signature9']))!=reference_original:raise Held('fixed-child-control-original-mapping')
    return dict(path=str(host),sha256=reference_original[1],signature9=list(original))


def _existing_volume_original(runtime,mount):
    if mount.get('Type')!='volume' or type(mount.get('Name')) is not str or not 1<=len(mount['Name'])<=256 or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-' for c in mount['Name']) or not mount['Name'][0].isalnum():raise Held('fixed-original-volume-name')
    original=(mount['Name'],mount['Source'],mount['Destination'],mount['RW'])
    rows=json.loads(runtime.command(['volume','inspect',mount['Name']]))
    if type(rows) is not list or len(rows)!=1 or rows[0].get('Name')!=original[0] or rows[0].get('Mountpoint')!=original[1] or rows[0].get('Driver')!='local' or rows[0].get('Scope')!='local' or rows[0].get('Options') not in (None,{}):raise Held('fixed-original-existing-volume')
    if (mount['Name'],mount['Source'],mount['Destination'],mount['RW'])!=original:raise Held('fixed-original-volume-mapping-drift')
    return canonical(rows[0])


def _close_unpaused_original(runtime,parent):
    registry=parent._RUNTIMES.get(runtime)
    if runtime in parent._TERMINALS:raise Held('fixed-original-prepause-terminal-absence')
    if type(registry) is not bytes or runtime.quiescent or runtime.selected is not None or runtime.process is not None:raise Held('fixed-original-prepause-runtime')
    original=json.loads(registry)
    if (os.getpid(),threading.get_ident())!=(original['pid'],original['thread']) or time.monotonic()>original['deadline']:raise Held('fixed-original-prepause-owner')
    for role,cid in original['ids'].items():
        current=runtime.inspect(cid);before=original['baseline'][role]
        if runtime.static(current)!=runtime.static(before):raise Held('fixed-original-prepause-profile')
        fields=('Running','Paused','Pid','StartedAt','Restarting','Dead','OOMKilled','Status','ExitCode')
        if any(current['State'].get(key)!=before['State'].get(key) for key in fields):raise Held('fixed-original-prepause-process')
    if runtime in parent._TERMINALS or parent._RUNTIMES.get(runtime) is not registry or runtime.quiescent or runtime.selected is not None or runtime.process is not None or (runtime.pid,runtime.thread,runtime.deadline,runtime.started)!=(original['pid'],original['thread'],original['deadline'],original['started']) or runtime.ids!=original['ids'] or runtime.baseline!=original['baseline']:raise Held('fixed-original-prepause-registry')


def _verify_runtime_receipt(document,runtime):
    if document['profile']!=LOGICAL_PROFILE_SHA:raise Held('fixed-source-owned-logical-policy')
    before=runtime.baseline['native']
    if _image(before['Image'])!=document['image']:raise Held('fixed-external-image-receipt')
    # Real ConfiguredRuntime.static is already canonical encoded bytes.
    profile=runtime.static(before)
    if type(profile) is not bytes or sha(profile)!=document['runtime_profile_sha256']:raise Held('fixed-external-profile-receipt')


def launch_original(installation, input_ref, input_child):
    """No caller command/key/profile/image. Root receipt owns every launch pin."""
    if type(installation) is not Installation:raise Held('fixed-root-installation-type')
    row=installation.close();document=row['document'];parent=row['modules']['comic_retained_standalone_parent.py']
    runtime=parent.ConfiguredRuntime.observe(document['ids'])
    _verify_runtime_receipt(document,runtime)
    bootstrap=read(PACKAGE/'BOOTSTRAP.py',row['frame'])
    if sha(bootstrap)!=document['bootstrap_sha256']:raise Held('fixed-original-bootstrap-pin')
    bootframe=(tuple((str(path),value) for path,value in row['frame'][0] if path==PACKAGE/'BOOTSTRAP.py'),tuple((str(path),value) for path,value in row['frame'][1]),())
    inputs,inputframe=parent.read_original(input_ref)
    if parent.mapped_host(runtime.baseline['native']['Mounts'],input_child)!=input_ref['path']:raise Held('fixed-input-original-bind')
    boot=parent.decode(inputs)
    if boot['parent_sha256']!=document['parent_sha256']:raise Held('fixed-input-parent')
    # Installation is not a reader-stop/backup grant. Owning quiescence is real.
    recovery=observe_recovery_original(installation,runtime,boot)
    if boot['data_root']!=recovery['data']:raise Held('fixed-original-daemon-data-root')
    nonce=os.urandom(32).hex()
    preflight=_preflight_original_capacity(installation,runtime,boot,nonce)
    runtime.quiesce()
    native=runtime.baseline['native']
    arguments=['create','--pull','never','--interactive','--read-only','--network','none','--user','1000:1000',
               '--cap-drop','ALL','--security-opt','no-new-privileges','--entrypoint','python3']
    volume_originals=[]
    for mount in native['Mounts']:
        target=Path(mount['Destination']);protected=Path('/opt/mylar-publication-launch')
        if target.is_relative_to(protected) or protected.is_relative_to(target):raise Held('fixed-auth-installation-overlay')
        if any(c in mount['Source']+mount['Destination'] for c in ',\n\r'):raise Held('fixed-original-bind-profile')
        if mount['Type']=='bind':spec='type=bind,src='+mount['Source']+',dst='+mount['Destination']
        elif mount['Type']=='volume':
            volume=_existing_volume_original(runtime,mount);volume_originals.append((dict(mount),volume))
            spec='type=volume,src='+mount['Name']+',dst='+mount['Destination']+',volume-nocopy'
        else:raise Held('fixed-original-mount-type')
        arguments+=['--mount',spec+('' if mount['RW'] else ',readonly')]
    for value in native['Config']['Env']:arguments+=['--env',value]
    command=['-I','-B','-c',bootstrap.decode(),'--input',input_child,'--input-sha256',input_ref['sha256']]
    arguments += [native['Image'],*command]
    runtime.close();installation.close();parent.raw(bootframe);parent.raw(inputframe)
    for mount,volume in volume_originals:
        if _existing_volume_original(runtime,mount)!=volume:raise Held('fixed-original-volume-before-create')
    cid=runtime.command(arguments).decode().strip()
    if not hexadecimal(cid):raise Held('fixed-created-child-ID')
    observed=runtime.inspect(cid);parent.selected_profile(native,observed)
    for mount,volume in volume_originals:
        if _existing_volume_original(runtime,mount)!=volume:raise Held('fixed-original-volume-after-create')
    if observed['Config']['Entrypoint']!=['python3'] or observed['Config']['Cmd']!=command or observed['HostConfig'].get('Init'):raise Held('fixed-child-direct-PID1')
    runtime.selected=cid;runtime.selected_static=runtime.static(observed)
    process=subprocess.Popen(['docker','start','--attach','--interactive',cid],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    runtime.process=process
    # Original actual Popen FDs precede the next inspection/validation callback.
    pipes=tuple((stream.fileno(),nine(os.fstat(stream.fileno()))) for stream in (process.stdin,process.stdout,process.stderr))
    running=runtime.inspect(cid);parent.selected_profile(native,running)
    if running['State']['Running'] is not True or running['State']['Pid']<=0 or runtime.static(running)!=runtime.selected_static:raise Held('fixed-original-child-start')
    runtime.selected_started=running['State']['StartedAt'];runtime.selected_pid=running['State']['Pid']
    obj=object.__new__(OriginalLaunch)
    _LAUNCHES[obj]=dict(installation=installation,runtime=runtime,process=process,cid=cid,started=runtime.selected_started,
                       selected_pid=runtime.selected_pid,start=process_start(runtime.selected_pid),attach_pid=process.pid,
                       pipes=pipes,stdin=process.stdin,stdout=process.stdout,owner=(os.getpid(),threading.get_ident()),
                       deadline=time.monotonic()+PREAUTH_SECONDS,total_deadline=row['deadline'],bootframe=bootframe,inputframe=inputframe,
                       recovery=recovery,preflight=preflight,boot=boot,input_sha256=input_ref['sha256'],input_bytes=inputs,bootstrap=bootstrap,
                       nonce=nonce,session=os.urandom(32).hex(),admission=None,sequence=0,previous=b'',auth_challenge=None)
    state=_LAUNCHES[obj]
    object_keys=('installation','runtime','process','stdin','stdout')
    value_keys=('cid','started','selected_pid','start','attach_pid','pipes','owner','total_deadline','bootframe','inputframe','input_sha256','input_bytes','bootstrap','nonce','session')
    _LAUNCH_SEALS[obj]=(state,dict(objects=tuple((key,state[key]) for key in object_keys),values=tuple((key,state[key]) for key in value_keys),boot=json.loads(inputs),preflight=copy.deepcopy(preflight),recovery=copy.deepcopy(recovery),runtime_registry=parent._RUNTIMES[runtime],runtime_table=parent._RUNTIMES,terminal_table=parent._TERMINALS))
    _PHASES[obj]=tuple(state[key] for key in ('deadline','admission','sequence','previous','auth_challenge'))
    parent.raw(bootframe);parent.raw(inputframe);obj.close();return obj


def _packet(launch):
    state=launch.close();fd=state['stdout'].fileno();data=bytearray()
    while True:
        left=state['deadline']-time.monotonic()
        if left<=0 or not select.select([fd],[],[],left)[0]:raise Held('fixed-preauth-deadline')
        chunk=os.read(fd,1)
        if chunk==b'\n':break
        if not chunk:raise Held('fixed-original-child-EOF')
        data.extend(chunk)
        if len(data)>LIMIT:raise Held('fixed-preauth-frame-bound')
    launch.close();return bytes(data)


def _signed(launch, assertion):
    state=launch.close();row=state['installation'].close();crypto=row['modules']['private_crypto.py']
    if type(assertion) is not dict:raise Held('fixed-signer-owned-assertion')
    domain=assertion.get('domain')
    if domain=='standalone-fixed-launch-admission-v1':
        if set(assertion)!={'domain','measured','challenge','child_pid','child_start','challenge_frame','session','broker_nonce','purpose','lifetime_ms','host_observation'} or state['admission'] is not None or assertion['session']!=state['session'] or assertion['broker_nonce']!=state['nonce'] or assertion['child_pid']!=1 or assertion['child_start']!=state['start'] or assertion['purpose']!='retained-standalone' or type(assertion['lifetime_ms']) is not int or assertion['lifetime_ms']!=5000 or not hexadecimal(assertion['challenge']) or not hexadecimal(assertion['challenge_frame']):raise Held('fixed-signer-owned-admission')
        expected=dict(installation=row['document']['anchor_sha256'],key=row['document']['key_sha256'],broker_sources=row['document']['broker_sources'],child_sources=row['document']['inventory_sha256'],bootstrap=row['document']['bootstrap_sha256'],input=state['input_sha256'],review=state['boot']['review_ref']['sha256'],deployment=row['document']['deployment'],profile=row['document']['profile'])
        if assertion['measured']!=expected or assertion['host_observation']!=dict(container=state['cid'],start=sha(state['started'].encode()),host_pid=os.getpid(),image=row['document']['image']):raise Held('fixed-signer-original-observations')
    elif domain=='standalone-fixed-stage-v3':
        sequence=state['sequence']+1
        if set(assertion)!={'domain','session','admission','challenge','sequence','kind','previous','payload','payload_digest'} or sequence not in (2,4,6) or type(assertion['sequence']) is not int or assertion['sequence']!=sequence or assertion['kind']!={2:'backup-ready',4:'observed-release',6:'observed-exit'}[sequence] or assertion['session']!=state['session'] or assertion['admission']!=state['admission'] or assertion['challenge']!=state['auth_challenge'] or assertion['previous']!=state['previous'].hex():raise Held('fixed-signer-owned-stage')
        wire=assertion['payload']
        if type(wire) is not dict or set(wire)!={'version','protocol','kind','nonce','sequence','challenge','payload'} or type(wire['version']) is not int or wire['version']!=3 or wire['protocol']!='standalone-retained-repeat-v3' or wire['kind']!=assertion['kind'] or type(wire['sequence']) is not int or wire['sequence']!=sequence or wire['nonce']!=state['boot']['nonce'] or wire['challenge']!=state['boot']['challenge'] or assertion['payload_digest']!=sha(canonical(wire)):raise Held('fixed-signer-original-stage-wire')
    else:raise Held('fixed-signer-finite-domain')
    data=canonical(assertion);key_original=dict(row['frame'][0])[KEY]
    fd=os.open(KEY,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        if nine(os.fstat(fd))!=key_original or key_original[5]&0o7777!=0o600:raise Held('fixed-original-private-key')
        runtime=crypto._HostExperiment()
        with crypto._Memfd(data) as message:
            result=runtime._execute(['pkeyutl','-sign','-rawin','-provider','default','-keyform','DER','-inkey','/proc/self/fd/'+str(fd),'-in',message.path],buffers=(message,),key_fd=fd)
            if result.returncode!=0 or len(result.stdout)!=64:raise Held('fixed-signer-response')
            signature=result.stdout
        runtime._verify(data,signature,row['public'])
        if nine(os.fstat(fd))!=key_original:raise Held('fixed-key-after-sign')
    finally:
        # Match the original resource; leave foreign reused descriptor untouched.
        try:z=os.fstat(fd)
        except OSError:z=None
        if z is not None and (z.st_dev,z.st_ino,z.st_mode&0o170000)==(key_original[0],key_original[1],key_original[5]&0o170000):os.close(fd)
    packet=canonical(dict(assertion=assertion,signature=signature.hex()))
    launch.close();return packet,data,signature


def authenticate_original(launch):
    if type(launch) is not OriginalLaunch:raise Held('fixed-original-launch-type')
    state=launch.close()
    if state['admission'] is not None:raise Held('fixed-preauth-once')
    challenge_raw=_packet(launch);challenge=parse(challenge_raw);row=state['installation'].close();doc=row['document']
    expected=dict(installation=doc['anchor_sha256'],key=doc['key_sha256'],broker_sources=doc['broker_sources'],
                  child_sources=doc['inventory_sha256'],bootstrap=doc['bootstrap_sha256'],input=state['input_sha256'],
                  review=state['boot']['review_ref']['sha256'],deployment=doc['deployment'],profile=doc['profile'])
    if set(challenge)!={'domain','challenge','child_pid','child_start','measured'} or challenge['domain']!='standalone-launch-challenge-v3' or not hexadecimal(challenge['challenge']) or challenge['child_pid']!=1 or challenge['child_start']!=state['start'] or challenge['measured']!=expected:raise Held('fixed-original-child-challenge')
    assertion=dict(domain='standalone-fixed-launch-admission-v1',measured=expected,challenge=challenge['challenge'],
                   child_pid=1,child_start=state['start'],challenge_frame=sha(challenge_raw),session=state['session'],
                   broker_nonce=state['nonce'],purpose='retained-standalone',lifetime_ms=5000,
                   host_observation=dict(container=state['cid'],start=sha(state['started'].encode()),host_pid=os.getpid(),image=doc['image']))
    packet,raw_signature,signature=_signed(launch,assertion)
    _send_original(launch,packet)
    state['admission']=sha(raw_signature+signature);state['previous']=hashlib.sha256(challenge_raw+raw_signature+signature).digest()
    state['deadline']=min(state['total_deadline'],_PHASES[launch][0]-PREAUTH_SECONDS+1800);state['auth_challenge']=challenge['challenge']
    _PHASES[launch]=tuple(state[key] for key in ('deadline','admission','sequence','previous','auth_challenge'))
    launch.close();return state['admission']


def _send_original(launch,packet):
    state=launch.close();view=memoryview(packet+b'\n')
    while view:
        count=os.write(state['stdin'].fileno(),view)
        if count<=0:raise Held('fixed-original-short-write')
        view=view[count:]
    launch.close()


def _recovery_publication(value):
    """Observation only: the owning kernel still checks recovery authority."""
    if type(value) is not dict or set(value)!={'version','state','reason','census'} or type(value['version']) is not int or value['version']!=1:raise Held('fixed-recovery-status-schema')
    if (value['state'],value['reason']) not in (('ready','verified'),('held','startup-restart-required')):raise Held('fixed-recovery-held-reason')
    census=value['census']
    if type(census) is not dict or set(census)!={'version','epoch','revision','keys','digest'} or type(census['version']) is not int or census['version']!=1 or not hexadecimal(census['epoch']) or type(census['revision']) is not int or type(census['keys']) is not list or len(census['keys'])!=census['revision'] or not 0<=census['revision']<=REGISTRY_LIMIT or not all(hexadecimal(x) for x in census['keys']) or census['keys']!=sorted(set(census['keys'])) or sha(canonical(census['keys']))!=census['digest']:raise Held('fixed-recovery-current-census')


def observe_recovery_original(installation,runtime,boot):
    row=installation.close();parent=row['modules']['comic_retained_standalone_parent.py']
    if type(runtime) is not parent.ConfiguredRuntime or runtime.quiescent:raise Held('fixed-recovery-before-pause')
    scope=row['modules']['publication_native_configured_scope.py']
    probe=read(PACKAGE/'comic_native_process_probe.py',row['frame'])
    scope_bytes=read(PACKAGE/'publication_native_configured_scope.py',row['frame'])
    native_mounts=runtime.baseline['native']['Mounts']
    config_host=_host_original_ref(boot['config_ref'],native_mounts)
    config,config_frame=parent.read_original(config_host)
    before=runtime.inspect(runtime.ids['native']);static=runtime.static(before)
    if static!=runtime.static(runtime.baseline['native']) or before['State']['Running'] is not True or before['State']['Paused'] is not False:raise Held('fixed-recovery-original-native')
    nonce=os.urandom(32).hex();request=dict(version=1,nonce=nonce,source_sha256=sha(probe),seconds=30,module_pins=dict(row['document']['daemon_sources']),scope_source=scope_bytes.decode())
    result=subprocess.run(['docker','exec','--interactive',runtime.ids['native'],'python3','-I','-B','-c',probe.decode()],input=canonical(request),capture_output=True,timeout=45,check=True)
    if len(result.stdout)>1024**2:raise Held('fixed-recovery-probe-bound')
    value=json.loads(result.stdout)
    if type(value) is not dict or set(value)!={'version','nonce','source_sha256','process','publication','config'} or type(value['version']) is not int or value['version']!=1 or value['nonce']!=nonce or value['source_sha256']!=sha(probe):raise Held('fixed-recovery-probe-original')
    _recovery_publication(value['publication']);data=scope.data_from_argv(value['process']['argv'])
    if parent.mapped_host(before['Mounts'],data+'/config.ini')!=config_host['path'] or value['config']!=dict(path=data+'/config.ini',sha256=boot['config_ref']['sha256'],signature9=boot['config_ref']['signature9']):raise Held('fixed-recovery-original-config')
    after=runtime.inspect(runtime.ids['native'])
    if runtime.static(after)!=static or after['State']['Pid']!=before['State']['Pid'] or after['State']['StartedAt']!=before['State']['StartedAt']:raise Held('fixed-recovery-original-process')
    answer=dict(data=data,process=value['process'],publication=value['publication'],config=value['config'])
    _close_unpaused_original(runtime,parent);installation.close();parent.raw(config_frame)
    for path,original in config_frame[1]:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=original:raise Held('fixed-recovery-final-config-node')
    for path,original in config_frame[0]:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=original:raise Held('fixed-recovery-final-config-file')
    for path,original in row['frame'][0]:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=original:raise Held('fixed-recovery-final-source')
    return answer


def _retire_verified_bodies(parent, initialized_body, observed_body, *, initialized, observed,
                            boot, mounts, backup, initialized_header, observed_header,
                            final_original, process, original_process, ack, observed_raw, authority=None):
    """Finite original-FD retirement after full owning terminal and natural exit.

    This private observation helper grants no operation rights. The broker's
    original channel owns these arguments; descriptors stay retained on failure.
    """
    # Original helper/source leaves precede poll, FD, parser and declared close callbacks.
    authority_state=None;authority_seal=None;authority_phase=None
    if authority is None:
        code=Path(__file__);authority_frame=(((str(code),nine(os.lstat(code))),),tuple((str(path),five(os.lstat(path))) for path in code.parents),())
    else:
        if type(authority) is not OriginalLaunch:raise Held('fixed-body-original-authority-type')
        authority_state=_LAUNCHES.get(authority);authority_seal=_LAUNCH_SEALS.get(authority);authority_phase=_PHASES.get(authority)
        if authority_state is None or authority_seal is None or authority_seal[0] is not authority_state:raise Held('fixed-body-original-authority')
        installation_state=_INSTALLATIONS.get(authority_state['installation'])
        if installation_state is None:raise Held('fixed-body-original-installation')
        authority_frame=installation_state['frame']
        authority_runtime=authority_state['runtime'];authority_parent=installation_state['modules']['comic_retained_standalone_parent.py']
        authority_terminal=_EXITS.get(authority)
        if authority not in _EXITS or authority_runtime not in authority_parent._TERMINALS or authority_parent._TERMINALS[authority_runtime] is not authority_terminal:raise Held('fixed-body-original-terminal-authority')
    if (type(initialized_body) is not parent.BodyObservation or
            type(observed_body) is not parent.BodyObservation or
            type(process) is not subprocess.Popen or process is not original_process or
            process.poll()!=0):raise Held('fixed-body-original-natural-exit')
    originals=tuple((body,parent._BODIES.get(body)) for body in (initialized_body,observed_body))
    if any(type(seal) is not tuple or len(seal)!=8 for _,seal in originals):raise Held('fixed-body-original-registry')
    owner=(os.getpid(),threading.get_ident());process_identity=(process.pid,process.stdin,process.stdout)
    source_original=(tuple(final_original[0]),tuple(final_original[1]),tuple(final_original[2]))
    if (type(ack) is not dict or set(ack)!={'version','protocol','kind','nonce','sequence','challenge','payload'} or
            type(ack['version']) is not int or ack['version']!=3 or ack['protocol']!='standalone-retained-repeat-v3' or
            type(ack['sequence']) is not int or ack['sequence']!=5 or ack['kind']!='observed-final-ACK' or
            ack['nonce']!=boot['nonce'] or ack['challenge']!=boot['challenge'] or
            ack['payload']!={'observed_sha256':sha(observed_raw)}):raise Held('fixed-body-original-final-ACK')
    ack_original=canonical(ack);ack_expected=json.loads(ack_original)
    backup_table=type(backup).close.__globals__['_OBSERVATIONS'];backup_seal=backup_table.get(backup)
    if backup_seal is None:raise Held('fixed-body-original-backup')
    backup_frames=(backup_seal['code'],backup_seal['copies']);backup_digest=backup_seal['digest']
    sql_original=tuple((key,tuple((path,json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)) for path,value in backup_seal[key])) for key in ('databases','source_databases'))
    sql_expected=tuple((key,tuple((path,json.loads(value)) for path,value in rows)) for key,rows in sql_original)
    proof=parent.verify_terminal(initialized,observed,mounts=mounts,data_root=boot['data_root'],
        backup_sha256=backup_digest,backup=backup,
        initialized_header=initialized_header,observed_header=observed_header)
    successor_original=(tuple((path,tuple(fact)) for path,fact in proof['original_vectors'][0]),tuple((path,tuple(fact)) for path,fact in proof['original_vectors'][1]),tuple((path,tuple(names)) for path,names in proof['original_vectors'][2]))
    projected=[{}, {}, {}]
    for physical in (source_original,successor_original,*backup_frames,authority_frame):
        for index,entries in enumerate(physical):
            for path,fact in entries:
                if path in projected[index] and projected[index][path]!=fact:raise Held('fixed-body-original-successor-conflict')
                projected[index].setdefault(path,fact)
    successor_tail=tuple(tuple(sorted(values.items())) for values in projected)
    # The exact source-owned SQL/journal/publication successor must account for
    # every original body-frame change; mutable current facts are never a baseline.
    current_files=dict(source_original[0]);publication=observed_header['publication']
    allowed={parent.mapped_host(mounts,path) for path in (publication['carrier'],publication['directory'],boot['data_root'])}
    allowed.update(parent.mapped_host(mounts,row['path']) for row in observed['original_vectors']['sql_parents'])
    for body,seal in originals:
        if seal[:2]!=owner or (body is initialized_body and seal[3]!=parent.mapped_host(mounts,initialized_header['body_ref']['path'])) or (body is observed_body and seal[3]!=parent.mapped_host(mounts,observed_header['body_ref']['path'])):raise Held('fixed-body-original-owner-path')
        for path,stamp in seal[7][0]:
            expected=current_files.get(path)
            if expected is None:raise Held('fixed-body-unaccounted-path')
            if path not in allowed:
                if expected!=stamp:raise Held('fixed-body-original-file-changed')
            elif stamp[:2]+stamp[5:]!=expected[:2]+expected[5:] or stamp[5]&0o170000!=0o040000:
                raise Held('fixed-body-original-directory-incarnation')
        fd=seal[2]
        if nine(os.fstat(fd))!=seal[4]:raise Held('fixed-body-original-descriptor')
        os.lseek(fd,0,os.SEEK_SET);digest=hashlib.sha256();count=0
        while chunk:=os.read(fd,1024**2):
            count+=len(chunk)
            if count>256*1024**2:raise Held('fixed-body-original-byte-bound')
            digest.update(chunk)
        if count!=len(seal[6]) or digest.hexdigest()!=seal[5]:raise Held('fixed-body-original-byte-hash')
    # All parser, schema, hash and declared closure callbacks precede this tail.
    summary_original=json.loads(canonical(proof['summary']))
    backup.close_copies();parent.raw(source_original)
    for body,seal in originals:
        z=os.fstat(seal[2])
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=seal[4]:raise Held('fixed-body-final-original-FD')
    if (os.getpid(),threading.get_ident())!=owner:raise Held('fixed-body-final-original-owner')
    # All declared fstat/PID/thread helpers precede this complete original tail.
    for physical in (successor_tail,):
     for path,names in physical[2]:
        if tuple(sorted(os.listdir(path)))!=names:raise Held('fixed-body-final-namespace')
     for path,stamp in physical[1]:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=stamp:raise Held('fixed-body-final-node')
     for path,stamp in physical[0]:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:raise Held('fixed-body-final-file')
    for path,names in source_original[2]:
        if tuple(sorted(os.listdir(path)))!=names:raise Held('fixed-body-final-namespace')
    for path,stamp in source_original[1]:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=stamp:raise Held('fixed-body-final-node')
    for path,stamp in source_original[0]:
        z=os.lstat(path)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:raise Held('fixed-body-final-file')
    for body,seal in originals:
        if parent._BODIES.get(body) is not seal:raise Held('fixed-body-final-FD-registry')
    if (process.pid,process.stdin,process.stdout)!=process_identity or process.returncode!=0:raise Held('fixed-body-final-original-process')
    # Immutable original ACK representation is checked without a replaceable encoder.
    if backup_table.get(backup) is not backup_seal or (backup_seal['code'],backup_seal['copies'])!=backup_frames or backup_seal['digest']!=backup_digest:raise Held('fixed-body-final-backup-registry')
    pending=[(ack,ack_expected),(proof['summary'],summary_original)]
    for key,expected_rows in sql_expected:
        actual_rows=backup_seal[key]
        if len(actual_rows)!=len(expected_rows):raise Held('fixed-body-final-backup-SQL-length')
        for (actual_path,actual_value),(expected_path,expected_value) in zip(actual_rows,expected_rows):
            if actual_path!=expected_path:raise Held('fixed-body-final-backup-SQL-path')
            pending.append((actual_value,expected_value))
    while pending:
        actual,expected=pending.pop()
        if type(actual) is not type(expected):raise Held('fixed-body-final-ACK-type')
        if type(expected) is dict:
            if actual.keys()!=expected.keys():raise Held('fixed-body-final-ACK-fields')
            pending.extend((actual[key],expected[key]) for key in expected)
        elif type(expected) is list:
            if len(actual)!=len(expected):raise Held('fixed-body-final-ACK-length')
            pending.extend(zip(actual,expected))
        elif actual!=expected:raise Held('fixed-body-final-ACK-value')
    if authority is not None and (_LAUNCHES.get(authority) is not authority_state or _LAUNCH_SEALS.get(authority) is not authority_seal or _PHASES.get(authority) is not authority_phase or authority_state['process'] is not process):raise Held('fixed-body-final-original-authority')
    if authority is not None and (authority not in _EXITS or _EXITS[authority] is not authority_terminal or authority_runtime not in authority_parent._TERMINALS or authority_parent._TERMINALS[authority_runtime] is not authority_terminal or authority_parent._RUNTIMES is not authority_seal[1]['runtime_table'] or authority_parent._TERMINALS is not authority_seal[1]['terminal_table'] or authority_parent._RUNTIMES.get(authority_runtime) is not authority_seal[1]['runtime_registry']):raise Held('fixed-body-final-runtime-authority')
    for body,seal in originals:
        os.close(seal[2]);del parent._BODIES[body]
    return summary_original


BACKUP_PARENT=Path('/var/lib/mylar-publication-launch/backups')

def _preflight_original_capacity(installation,runtime,boot,nonce):
    """Fixed-role capacity observation; no backup or quiescence authority."""
    import configparser
    import sqlite3
    from contextlib import closing
    row=installation.close();parent=row['modules']['comic_retained_standalone_parent.py']
    helper=row['modules']['comic_retained_standalone_backup.py']
    native_mounts=runtime.baseline['native']['Mounts'];reader_mounts=runtime.baseline['reader']['Mounts']
    data=parent.mapped_host(native_mounts,boot['data_root'])
    config,config_frame=parent.read_original(_host_original_ref(boot['config_ref'],native_mounts))
    parser=configparser.ConfigParser(interpolation=None,strict=True);parser.read_string(config.decode())
    if parser.defaults():raise Held('fixed-capacity-config-defaults')
    locations={}
    for key,section,option in (('cache','DDL','ddl_location'),('library','General','destination_dir')):
        value=parser.get(section,option,raw=True)
        if value!=value.strip() or not value or '%' in value or str(Path(value))!=value or not Path(value).is_absolute() or '..' in Path(value).parts:raise Held('fixed-capacity-canonical-location')
        locations[key]=value
    reader_rows=[m for m in reader_mounts if m['Destination']=='/config' and m['Type'] in ('bind','volume')]
    if len(reader_rows)!=1:raise Held('fixed-capacity-reader-config-mount')
    reader=reader_rows[0]['Source']
    if not Path(reader).is_absolute() or str(Path(reader))!=reader:raise Held('fixed-capacity-reader-original-source')
    native_db=Path(data)/'mylar.db';z=os.lstat(native_db);db_original=nine(z)
    db_nodes=tuple((p,five(os.lstat(p))) for p in native_db.parents)
    companions=tuple(str(Path(root)/name)+suffix for root,name in ((data,'mylar.db'),(data,'workflow.sqlite')) for suffix in ('-wal','-shm','-journal'))
    for path in companions:
        if os.path.lexists(path):raise Held('fixed-capacity-current-DB-companion')
    # immutable readonly is admissible only with original absent companions,
    # complete unchanged original DB9 and final absence; never a stale WAL view.
    with closing(sqlite3.connect(native_db.as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        db.row_factory=sqlite3.Row;owner=boot['request']['owner']
        if owner['table'] not in ('issues','annuals'):raise Held('fixed-capacity-owner-table')
        rows=db.execute('SELECT * FROM '+owner['table']+' WHERE IssueID=?',(owner['issueid'],)).fetchall()
        comics=db.execute('SELECT * FROM comics WHERE ComicID=?',(owner['parentcomicid'],)).fetchall()
        ddl=db.execute('SELECT * FROM ddl_info WHERE id=?',(boot['request']['ddl_id'],)).fetchall()
        if len(rows)!=1 or len(comics)!=1 or len(ddl)!=1:raise Held('fixed-capacity-original-owner')
        vector={'request':boot['request'],'ddl':dict(ddl[0]),'catalog_row':dict(rows[0])}
        folder=comics[0]['ComicLocation'];leaf=rows[0]['Location'];name=ddl[0]['filename']
        if any(type(value) is not str or not value for value in (folder,leaf,name)):
            raise Held('fixed-capacity-original-location-fields')
        vector['source']=str(Path(locations['cache'])/name)
        vector['target']=str(Path(leaf) if Path(leaf).is_absolute() else Path(folder)/leaf)
        source_child,target_child=parent.owner_paths(vector,locations,dict(comics[0]))
    scopes=[dict(role='native_state',root=data,databases=['mylar.db','workflow.sqlite']),
            dict(role='reader_state',root=reader,databases=['database.sqlite']),
            dict(role='retained_source',root=parent.mapped_host(native_mounts,source_child),databases=[]),
            dict(role='existing_target',root=parent.mapped_host(native_mounts,target_child),databases=[])]
    # Entire raw namespace/file metadata, without streaming the whole library.
    original,_=helper.capture([Path(s['root']) for s in scopes])
    parent_original=nine(os.lstat(BACKUP_PARENT));names=tuple(sorted(os.listdir(BACKUP_PARENT)))
    if (parent_original[5]&0o170000!=0o040000 or parent_original[5]&0o7777!=0o700 or
            parent_original[6:8]!=(0,0) or nonce in names or os.path.lexists(BACKUP_PARENT/nonce)):
        raise Held('fixed-capacity-private-parent')
    parent_fd=os.open(BACKUP_PARENT,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        if nine(os.fstat(parent_fd))!=parent_original:raise Held('fixed-capacity-original-parent-FD')
        space=os.fstatvfs(parent_fd);free=space.f_bavail*space.f_frsize
        count=0;bytes_needed=0
        for _,stamp in original[0]:
            count+=1
            if stamp[5]&0o170000==0o100000:bytes_needed+=stamp[2]
        if count>100000 or bytes_needed>512*1024**3:raise Held('fixed-capacity-state-ceiling')
        # Exactly one preservation plus one independent restore, with a fixed
        # conservative filesystem allowance. No caller can increase these budgets.
        required=2*bytes_needed+(bytes_needed+19)//20+1024**2
        if free<required:raise Held('fixed-capacity-insufficient-free-space')
        result=dict(scopes=scopes,source=parent.mapped_host(native_mounts,source_child),target=parent.mapped_host(native_mounts,target_child),frame=original,
                    backup_parent9=parent_original,backup_parent_names=names,bytes=bytes_needed,
                    required=required,free=free,output=str(BACKUP_PARENT/nonce))
        _close_unpaused_original(runtime,parent);installation.close();parent.raw(config_frame);helper.raw(original)
        if nine(os.fstat(parent_fd))!=parent_original or nine(os.lstat(BACKUP_PARENT))!=parent_original or tuple(sorted(os.listdir(BACKUP_PARENT)))!=names:raise Held('fixed-capacity-final-parent')
        if os.fstatvfs(parent_fd)!=space:raise Held('fixed-capacity-free-space-changed')
        for path,stamp in db_nodes:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=stamp:raise Held('fixed-capacity-final-DB-node')
        z=os.lstat(native_db)
        if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=db_original:raise Held('fixed-capacity-final-DB-original')
        for path,names_original in original[2]:
            if tuple(sorted(os.listdir(path)))!=names_original:raise Held('fixed-capacity-final-namespace')
        for path,stamp in original[1]:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=stamp:raise Held('fixed-capacity-final-node')
        for path,stamp in original[0]:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:raise Held('fixed-capacity-final-file')
        for path in companions:
            try:os.lstat(path)
            except FileNotFoundError:pass
            else:raise Held('fixed-capacity-final-DB-companion')
        for path,stamp in config_frame[1]:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=stamp:raise Held('fixed-capacity-final-config-node')
        for path,stamp in config_frame[0]:
            z=os.lstat(path)
            if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=stamp:raise Held('fixed-capacity-final-config-file')
        return result
    finally:
        try:z=os.fstat(parent_fd)
        except OSError:pass
        else:
            if (z.st_dev,z.st_ino,z.st_mode&0o170000)==(parent_original[0],parent_original[1],0o040000):os.close(parent_fd)


def _receive_stage(launch, sequence, kind):
    state=launch.close();data=_packet(launch);wire=parse(data)
    if type(wire) is not dict or set(wire)!={'version','protocol','kind','nonce','sequence','challenge','payload'} or type(wire['version']) is not int or wire['version']!=3 or wire['protocol']!='standalone-retained-repeat-v3' or type(wire['sequence']) is not int or wire['sequence']!=sequence or wire['kind']!=kind or wire['nonce']!=state['boot']['nonce'] or wire['challenge']!=state['boot']['challenge'] or state['sequence']!=sequence-1:raise Held('fixed-original-child-stage')
    normalized=canonical(dict(sequence=sequence,kind='final-ACK' if sequence==5 else kind,payload=wire))
    launch.close()
    state['previous']=hashlib.sha256(state['previous']+normalized).digest();state['sequence']=sequence
    _PHASES[launch]=tuple(state[key] for key in ('deadline','admission','sequence','previous','auth_challenge'))
    launch.close();return data,wire


def _send_stage(launch, sequence, kind, payload, *, exit_permission=False):
    state=launch.close()
    if state['sequence']!=sequence-1 or sequence not in (2,4,6) or kind!={2:'backup-ready',4:'observed-release',6:'observed-exit'}[sequence] or exit_permission is not (sequence==6):raise Held('fixed-own-host-stage')
    regular=dict(version=3,protocol='standalone-retained-repeat-v3',kind=kind,nonce=state['boot']['nonce'],sequence=sequence,challenge=state['boot']['challenge'],payload=payload)
    assertion=dict(domain='standalone-fixed-stage-v3',session=state['session'],admission=state['admission'],challenge=state['auth_challenge'],sequence=sequence,kind=kind,previous=state['previous'].hex(),payload=regular,payload_digest=sha(canonical(regular)))
    packet,data,signature=_signed(launch,assertion)
    # Every encoding/signature callback completes while the original child is held.
    launch.close()
    if exit_permission:
        parent=state['installation'].close()['modules']['comic_retained_standalone_parent.py'];runtime=state['runtime']
        if launch in _EXITS or runtime in parent._TERMINALS:raise Held('fixed-original-terminal-absence')
        view=memoryview(packet+b'\n')
        while view:
            count=os.write(state['stdin'].fileno(),view)
            if count<=0:raise Held('fixed-original-exit-short-write')
            view=view[count:]
        # Only the exact original child may exit after the complete signed sixth frame.
        code=state['process'].wait(timeout=min(180,max(0.001,state['deadline']-time.monotonic())))
        if code!=0 or launch in _EXITS or runtime in parent._TERMINALS:raise Held('fixed-original-natural-exit')
        terminal=(runtime.selected,runtime.selected_started,runtime.selected_static,state['process'])
        parent._TERMINALS[runtime]=terminal;_EXITS[launch]=terminal
    else:_send_original(launch,packet)
    state['previous']=hashlib.sha256(state['previous']+data+signature).digest();state['sequence']=sequence
    if sequence==2:state['deadline']=min(state['total_deadline'],time.monotonic()+180)
    _PHASES[launch]=tuple(state[key] for key in ('deadline','admission','sequence','previous','auth_challenge'))
    launch.close()


def run_original(launch):
    """Fixed six-frame owner; no caller signer, ready payload, job, or grant callback."""
    if type(launch) is not OriginalLaunch:raise Held('fixed-original-run-type')
    state=launch.close();parent=state['installation'].close()['modules']['comic_retained_standalone_parent.py']
    if state['sequence']!=0 or state['admission'] is not None:raise Held('fixed-original-run-once')
    mounts=json.loads(canonical(state['runtime'].baseline['native']['Mounts']))
    boot=json.loads(canonical(state['boot']));hostboot=dict(boot,input_sha256=state['input_sha256'])
    data=parent.mapped_host(mounts,boot['data_root']);token=sha(canonical({key:boot['request'][key] for key in ('ddl_id','owner','kind')}))
    carrier=Path(data)/parent.CARRIER_NAME
    try:carrier9=nine(os.lstat(carrier));carrier_names=tuple(sorted(os.listdir(carrier)))
    except FileNotFoundError:carrier9=None;carrier_names=()
    if os.path.lexists(carrier/token):raise Held('fixed-original-token-publication-exists')
    prelaunch=dict(carrier9=carrier9,carrier_names=carrier_names,token_absent=True)
    authenticate_original(launch)
    initial_raw,initial_wire=_receive_stage(launch,1,'initialized')
    initial_original=parent.capture_publication_originals(data,token,'initialized')
    header=initial_wire['payload'];host_ref=_host_original_ref(header['body_ref'],mounts)
    first=parent.BodyObservation.read_original(header['body_ref'],host_ref['path'],initial_original)
    initialized=first.decoded()
    parent.join_publication(header,hostboot,mounts,initial_original,prelaunch)
    vector=parent.verify_initialized(initialized,boot,mounts)
    if parent.mapped_host(mounts,vector['source'])!=state['preflight']['source'] or parent.mapped_host(mounts,vector['target'])!=state['preflight']['target']:raise Held('fixed-original-preflight-owner-path')
    helper=state['installation'].close()['modules']['comic_retained_standalone_backup.py']
    backup=helper.copy_and_verify(state['preflight']['scopes'],Path(state['preflight']['output']))
    proof=backup.close();refs=[boot['config_ref'],boot['source_map_ref']]
    for key in ('source','target'):
        path=vector[key];reference=dict(path=path,sha256=vector['hashes'][path],signature9=vector['files'][path])
        _host_original_ref(reference,mounts);refs.append(reference)
    backup.close();launch.close()
    _send_stage(launch,2,'backup-ready',dict(initialized_sha256=sha(initial_raw),backup_sha256=proof['digest'],original_refs=refs))
    observed_raw,observed_wire=_receive_stage(launch,3,'observed')
    final_original=parent.capture_publication_originals(data,token,'finalized')
    final_header=observed_wire['payload'];host_ref=_host_original_ref(final_header['body_ref'],mounts)
    last=parent.BodyObservation.read_original(final_header['body_ref'],host_ref['path'],final_original)
    observed=last.decoded()
    parent.join_publication(final_header,hostboot,mounts,final_original,prelaunch,header['publication'])
    parent.verify_terminal(initialized,observed,mounts=mounts,data_root=boot['data_root'],backup_sha256=proof['digest'],backup=backup,initialized_header=header,observed_header=final_header)
    backup.close_copies();launch.close()
    _send_stage(launch,4,'observed-release',dict(observed_sha256=sha(observed_raw)))
    _,ack=_receive_stage(launch,5,'observed-final-ACK')
    if ack['payload']!={'observed_sha256':sha(observed_raw)}:raise Held('fixed-original-observed-ACK')
    # No exit permission until the complete original terminal/source/copy joins close.
    backup.close_copies();parent.raw(final_original);launch.close()
    _send_stage(launch,6,'observed-exit',dict(ack['payload']),exit_permission=True)
    launch.close()
    summary=_retire_verified_bodies(parent,first,last,initialized=initialized,observed=observed,boot=boot,mounts=mounts,backup=backup,initialized_header=header,observed_header=final_header,final_original=final_original,process=state['process'],original_process=state['process'],ack=ack,observed_raw=observed_raw,authority=launch)
    return summary
