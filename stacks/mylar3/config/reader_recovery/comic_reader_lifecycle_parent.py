"""Source-only stopped-reader protocol parent; CLI cannot operate services.

Root installs and accepts real producers/image before calling run_operation.
Only this host parent owns engine access; children use inherited pipes.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import select
import stat
import subprocess
import threading
import time
import weakref

_CORES = weakref.WeakKeyDictionary()
_GENERATED = weakref.WeakKeyDictionary()
_PHASES = weakref.WeakKeyDictionary()
_PROJECTORS = weakref.WeakKeyDictionary()
_OUTPUT_NODES = weakref.WeakKeyDictionary()

DOCKER = ('pkexec', '/usr/bin/docker', '--host', 'unix:///run/docker.sock')
MAX = 64 * 1024**2
ROLES = frozenset(('stopped_runtime', 'backup_ack', 'backup_manifest',
                  'backup_acceptance', 'rows', 'schema', 'reviewed_plan',
                  'timestamp_evidence', 'custody'))
ARCHIVE_ROLES=frozenset(('stopped_runtime','backup_ack','backup_manifest','backup_acceptance','schema','reader_snapshot','archive_request','custody'))
FALSE_RIGHTS = ('publication_acceptance', 'reader_resume_authority')


class Held(ValueError):
    pass


def need(value, reason):
    if not value:
        raise Held(reason)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode()


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate-json')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(Held('number')))


def digest(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def nine(value):
    return [value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns,
            value.st_ctime_ns, value.st_mode, value.st_uid, value.st_gid, value.st_nlink]


def five(value):
    return [value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid]


def absolute(value):
    need(type(value) is str and value.startswith('/') and str(PurePosixPath(value)) == value
         and not any(x in value for x in ('\x00', '\n', '\r', ',', '\\'))
         and '..' not in PurePosixPath(value).parts, 'path-spelling')
    return Path(value)


def parents(path):
    result = {}
    for node in path.parents:
        value = os.lstat(node)
        need(stat.S_ISDIR(value.st_mode), 'ancestor-type')
        result[str(node)] = five(value)
    return result


def read(ref, private=True):
    need(type(ref) is dict and set(ref) == {'path', 'sha256', 'signature9'}
         and digest(ref['sha256']), 'ref-shape')
    path = absolute(ref['path']); expected = tuple(ref['signature9'])
    need(len(expected) == 9 and all(type(x) is int for x in expected)
         and stat.S_ISREG(expected[5]) and expected[8] == 1
         and 0 < expected[2] <= MAX
         and (not private or expected[6] == os.geteuid()
              and stat.S_IMODE(expected[5]) == 0o600), 'ref-attributes')
    nodes = parents(path)
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        need(five(os.fstat(fd)) == nodes['/'], 'root-FD')
        current = Path('/')
        for part in path.parts[1:-1]:
            current /= part
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            try:
                need(five(os.fstat(nxt)) == nodes[str(current)], 'parent-FD')
            except BaseException:
                os.close(nxt)
                raise
            os.close(fd); fd = nxt
        leaf = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
        try:
            need(tuple(nine(os.fstat(leaf))) == expected, 'leaf-FD')
            blocks = []; left = expected[2]
            while left:
                block = os.read(leaf, min(left, 1024**2))
                need(bool(block), 'read-short'); blocks.append(block); left -= len(block)
            raw = b''.join(blocks)
            need(hashlib.sha256(raw).hexdigest() == ref['sha256'], 'ref-hash')
            need(tuple(nine(os.fstat(leaf))) == expected, 'leaf-FD-final')
            final({str(path): expected}, nodes, ())
            return raw
        finally:
            os.close(leaf)
    finally:
        os.close(fd)


def final(files, nodes, absent):
    """Raw kernel closure; caller freezes tuples before semantic callbacks."""
    for path, expected in nodes.items():
        z = os.lstat(path)
        if (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) != tuple(expected):
            raise Held('ancestor-final')
    for path, expected in files.items():
        z = os.lstat(path)
        if (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
                z.st_mode, z.st_uid, z.st_gid, z.st_nlink) != tuple(expected):
            raise Held('file-final')
    for path in absent:
        try:
            os.lstat(path)
        except FileNotFoundError:
            continue
        raise Held('absence-final')


def pinned_module(source):
    """Compile exactly the FD-checked buffer, never a second pathname read."""
    raw = read(source)
    spec = importlib.util.spec_from_loader('checked_parent_component_' + source['sha256'], loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = source['path']
    exec(compile(raw, source['path'], 'exec'), module.__dict__)
    read(source)
    return module


class Paths:
    def __init__(self, mounts):
        need(type(mounts) is list and 1 <= len(mounts) <= 64, 'mount-bound')
        self.mounts = copy.deepcopy(mounts)
        for row in mounts:
            need(set(row) == {'host', 'child', 'write'} and type(row['write']) is bool, 'mount-shape')
            absolute(row['host']); absolute(row['child'])
        need(len({x['child'] for x in mounts}) == len(mounts), 'mount-duplicate')

    def child(self, host):
        path = absolute(str(host)); candidates = []
        for row in self.mounts:
            root = Path(row['host'])
            if path == root or root in path.parents:
                candidates.append((len(root.parts), row, path.relative_to(root)))
        need(bool(candidates), 'unmapped-host')
        depth = max(x[0] for x in candidates); selected = [x for x in candidates if x[0] == depth]
        need(len(selected) == 1, 'ambiguous-host')
        _, row, rest = selected[0]
        result = str(Path(row['child']) / rest)
        need(self.host(result) == str(path), 'shadowed-mount')
        return result

    def host(self, child):
        path = absolute(str(child)); candidates = []
        for row in self.mounts:
            root = Path(row['child'])
            if path == root or root in path.parents:
                candidates.append((len(root.parts), row, path.relative_to(root)))
        need(bool(candidates), 'unmapped-child')
        depth = max(x[0] for x in candidates); selected = [x for x in candidates if x[0] == depth]
        need(len(selected) == 1, 'ambiguous-child')
        _, row, rest = selected[0]
        return str(Path(row['host']) / rest)

    def child_ref(self, value):
        read(value)
        return {**value, 'path': self.child(value['path'])}


def command_template(provider, phase, input_path):
    need(phase in ('backup', 'prepare', 'execute', 'verify-terminal') and digest(provider['sha256']), 'phase-command')
    return ['/lsiopy/bin/python3', '-I', '-B', str(absolute(provider['path'])),
            '--phase', phase, '--input', str(absolute(input_path)),
            '--input-sha256', '<INPUT_SHA256>', '--source-sha256', provider['sha256']]


def actual_command(template, input_sha):
    need(digest(input_sha) and template.count('<INPUT_SHA256>') == 1
         and template[-3] == '<INPUT_SHA256>', 'command-placeholder')
    need(all('<' not in x and '>' not in x for x in template if x != '<INPUT_SHA256>'), 'command-placeholder')
    return [input_sha if x == '<INPUT_SHA256>' else x for x in template]


def validate_ack(ack, phase, nonce, provider_sha):
    need(type(ack) is dict and set(ack) == {'nonce', 'phase', 'source_sha256', 'report',
                                         'publication_acceptance', 'reader_resume_authority'}, 'ACK-schema')
    need(ack['nonce'] == nonce and ack['phase'] == phase and ack['source_sha256'] == provider_sha
         and all(ack[key] is False for key in FALSE_RIGHTS), 'ACK-binding-or-grant')
    return copy.deepcopy(ack['report'])


def producer_inputs(value):
    need(type(value) is dict and set(value) == {'schema', 'reviewed_selection', 'timestamp_evidence'},
         'producer-input-roles')
    original = copy.deepcopy(value)
    files = {r['path']: tuple(r['signature9']) for r in original.values()}
    nodes = {}
    for r in original.values():
        nodes.update(parents(absolute(r['path'])))
    for r in original.values():
        read(r)
    final(files, nodes, ())
    return original


def static(row):
    return {key: copy.deepcopy(row[key]) for key in ('Id', 'Name', 'Image', 'Path', 'Args',
                                                   'Config', 'HostConfig', 'Mounts', 'NetworkSettings')}


def lifecycle_state(row):
    # Docker health probe logs/counters are observations, not incarnation facts.
    # No other lifecycle field is silently excluded or defaulted.
    value = row['State']
    names = ('Status', 'Running', 'Paused', 'Restarting', 'OOMKilled', 'Dead',
             'Pid', 'ExitCode', 'Error', 'StartedAt', 'FinishedAt')
    need(type(value) is dict and set(value) in (set(names), set(names) | {'Health'}),
         'lifecycle-state-fields')
    need(value['Status'] in ('created', 'running', 'paused', 'restarting', 'removing', 'exited', 'dead')
         and all(type(value[k]) is bool for k in ('Running', 'Paused', 'Restarting', 'OOMKilled', 'Dead'))
         and type(value['Pid']) is int and value['Pid'] >= 0
         and type(value['ExitCode']) is int
         and all(type(value[k]) is str for k in ('Error', 'StartedAt', 'FinishedAt')),
         'lifecycle-state-types')
    return tuple(value[k] for k in names)


def same_runtime(first, second):
    names = {'Id','Name','Image','Path','Args','Config','HostConfig','Mounts','NetworkSettings','State'}
    need(type(first) is dict and type(second) is dict and names <= set(first) and names <= set(second),
         'lifecycle-inspect-shape')
    return static(first) == static(second) and lifecycle_state(first) == lifecycle_state(second)


def stopped(row):
    state = row['State']
    need(state['Running'] is False and state['Pid'] == 0 and state['Status'] == 'exited'
         and all(state.get(k) is False for k in ('Paused', 'Restarting', 'Dead', 'OOMKilled')), 'reader-not-stopped')
_NFS_ADAPTERS=weakref.WeakKeyDictionary()

class ScopedDocker:
 """Exact argv only; private stderr never appears in public diagnostics."""
 def run(self,args,seconds):
  need(type(args) is list and bool(args) and args[0] in ('inspect','stop','start','create','events'),'engine-command')
  try:r=subprocess.run([*DOCKER,*args],capture_output=True,timeout=seconds,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
  except (OSError,subprocess.TimeoutExpired):raise Held('engine-ACK-unknown-no-replay') from None
  need(len(r.stdout)<=MAX and len(r.stderr)<=MAX and r.returncode==0,'engine-command-held');return r.stdout
 def canary(self,args,**kwargs):
  # Only the separately source-pinned diagnostic parent uses this transport.
  need(type(args) is list and (args[:len(DOCKER)]==DOCKER and args[len(DOCKER)] in ('create','inspect','start','exec')
       or args[:2]==['findmnt','--json']), 'nfs-engine-command')
  need(set(kwargs)<={'input','capture_output','timeout','check'} and kwargs.get('capture_output') is True
       and kwargs.get('check') is False and 0<kwargs.get('timeout',0)<=900,'nfs-engine-call-shape')
  try:return subprocess.run(args,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'},**kwargs)
  except (OSError,subprocess.TimeoutExpired):raise Held('nfs-engine-ACK-unknown') from None
 def interactive(self,cid,handler,seconds):
  end=time.monotonic()+seconds
  try:p=subprocess.Popen([*DOCKER,'start','--attach','--interactive',cid],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
  except OSError:raise Held('child-start-ACK-unknown') from None
  streams={p.stdout:'stdout',p.stderr:'stderr'};out=bytearray();err=bytearray();line=bytearray();ack=None
  try:
   while streams:
    need(time.monotonic()<end,'child-ACK-deadline')
    ready=select.select(list(streams),[],[],min(1,max(0,end-time.monotonic())))[0]
    if not ready:handler(None);continue
    for stream in ready:
     block=os.read(stream.fileno(),65536)
     if not block:del streams[stream];continue
     buf=out if streams[stream]=='stdout' else err;buf.extend(block);need(len(buf)<=MAX,'child-output-bound')
     if streams[stream]=='stderr':continue
     line.extend(block)
     while b'\n' in line:
      raw,_,remainder=line.partition(b'\n');line=bytearray(remainder);message=decode(raw)
      if message.get('type') in ('challenge', 'birth-commit'):
       response=handler(message);need(type(response) is bytes and response.endswith(b'\n') and len(response)<=MAX,'parent-fixed-response-bytes');p.stdin.write(response);p.stdin.flush()
      else:need(message.get('type')=='ACK' and ack is None,'child-output-protocol');ack=message['ack']
   need(not line and p.wait(timeout=max(0.001,end-time.monotonic()))==0 and ack is not None,'child-ACK-unknown')
   return ack
  except BaseException:
   # Do not stop/remove/replay an unknown Docker child or resume the reader.
   raise Held('child-uncertain-proof-retained') from None
  finally:
   for stream in (p.stdin,p.stdout,p.stderr):stream.close()


class LifecycleParent:
    """Finite producer protocol; all concrete producer sources must be reviewed.

    Engine and producer are host-owned. No child report authorizes restart.
    Missing required real producers fails before execute and leaves reader held.
    """
    def __init__(self, plan_ref, source_ref, engine):
        self.thread = threading.get_ident()
        self.plan_ref = copy.deepcopy(plan_ref); self.source_ref = copy.deepcopy(source_ref)
        plan = decode(read(plan_ref)); read(source_ref)
        archive=type(plan) is dict and plan.get('kind')=='reviewed-archive-one-lifecycle-protocol'
        base_keys={'version', 'kind', 'nonce', 'seconds',
             'operation', 'reader', 'held_native', 'held_worker', 'selected_image',
             'provider', 'producer', 'observer', 'sdk_map', 'mounts', 'native',
             'action_inputs', 'producer_inputs', 'birth_source_sha256', 'scope_projection', 'bounds', 'admission_source_sha256', 'nfs'}
        if archive:base_keys=(base_keys-{'action_inputs','admission_source_sha256'})|{'action','backup_provider'}
        need(type(plan) is dict and set(plan)==base_keys,'plan-schema')
        need(plan['version'] == (10 if archive else 9) and type(plan['version']) is int
             and plan['kind'] == ('reviewed-archive-one-lifecycle-protocol' if archive else 'reviewed-negative-five-lifecycle-protocol')
             and digest(plan['nonce']) and type(plan['seconds']) is int
             and 1 <= plan['seconds'] <= 3600, 'plan-kind')
        need(re.fullmatch('sha256:[0-9a-f]{64}', plan['selected_image']) is not None,
             'selected-image-digest')
        self.plan = copy.deepcopy(plan); self.engine = engine
        self.deadline = time.monotonic() + plan['seconds']; self.phase = 'admitted'; self.event_start = str(int(time.time()))
        self.mapping = Paths(plan['mounts']); self.op = absolute(plan['operation'])
        need(not os.path.lexists(self.op), 'exclusive-operation')
        need(any(r['host'] == str(self.op) and r['write'] is True for r in plan['mounts']),
             'private-operation-exact-writable-mount')
        parent = os.lstat(self.op.parent)
        need(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.geteuid()
             and stat.S_IMODE(parent.st_mode) == 0o700, 'operation-parent-private')
        self.files = {}; self.nodes = parents(self.op); self.generated = {}
        # Admit every archive role ancestor before any source/evidence read callback.
        if archive:
            for ref in (plan['backup_provider'], plan['observer'], *plan['producer_inputs'].values()):
                for node, value in parents(Path(ref['path'])).items():
                    need(node not in self.nodes or self.nodes[node] == value, 'archive-input-original-node')
                    self.nodes[node] = value
        for value in (plan_ref, source_ref, plan['provider'], plan['sdk_map'], plan['observer']):
            read(value); self.files[value['path']] = tuple(value['signature9'])
            for node,value in parents(Path(value['path'])).items():
                need(node not in self.nodes or self.nodes[node]==value,'parent-original-ancestor-conflict');self.nodes[node]=value
        need(plan['producer'] is not None, 'fresh-proof-producer-required')
        read(plan['producer']); self.files[plan['producer']['path']] = tuple(plan['producer']['signature9'])
        for node,value in parents(Path(plan['producer']['path'])).items():
            need(node not in self.nodes or self.nodes[node]==value,'parent-original-ancestor-conflict');self.nodes[node]=value
        if archive:
            need(plan['action']=='archive-one' and set(plan['producer_inputs'])=={'archive_request','archive_scopes'},'archive-only-plan')
            request=decode(read(plan['producer_inputs']['archive_request']))
            need(type(request) is dict and set(request)=={'version','owner','operation_id'} and type(request['version']) is int and request['version']==1 and digest(request['operation_id']),'archive-owner-request')
            for ref in (plan['backup_provider'],plan['observer'],*plan['producer_inputs'].values()):
                for node,value in parents(Path(ref['path'])).items():
                    need(node not in self.nodes or self.nodes[node]==value,'archive-input-original-node');self.nodes[node]=value
                read(ref);need(ref['path'] not in self.files or self.files[ref['path']]==tuple(ref['signature9']),'archive-input-original-file');self.files[ref['path']]=tuple(ref['signature9'])
            scopes=decode(read(plan['producer_inputs']['archive_scopes']))
            need(type(scopes) is dict and set(scopes)=={'version','scratch','retention_root'} and type(scopes['version']) is int and scopes['version']==1,'archive-private-scope-input')
            writable={str(self.op),self.mapping.host(plan['native']['data']),*[self.mapping.host(x) for x in plan['native']['roots']],scopes['scratch'],scopes['retention_root']}
            need(all(not row['write'] or row['host'] in writable for row in plan['mounts']),'archive-finite-writable-host-scope')
            # Immutable image code cannot be overlaid by any declared child mount.
            for row in plan['mounts']:
                child=absolute(row['child'])
                need(not any(child == protected or child in protected.parents or protected in child.parents for protected in map(Path, ('/app', '/lsiopy', '/usr', '/lib', '/lib64', '/bin', '/sbin', '/opt/archiving-utils', '/etc'))),'archive-image-overlay')
        else:
            need(type(plan['action_inputs']) is dict and set(plan['action_inputs']) == {'prepare', 'execute'}, 'phase-action-refs')
            actions = {}
            for phase, action_ref in plan['action_inputs'].items():
                actions[phase] = decode(read(action_ref))
                self.files[action_ref['path']] = tuple(action_ref['signature9'])
                for node,value in parents(Path(action_ref['path'])).items():
                    need(node not in self.nodes or self.nodes[node]==value,'parent-original-ancestor-conflict');self.nodes[node]=value
                need(actions[phase]['operation'] == self.mapping.child(self.op / phase), 'phase-action-operation')
            need(actions['prepare']['members'] == actions['execute']['members']
                 and actions['prepare']['targets'] == actions['execute']['targets'], 'same-five-phase-actions')
            for producer_ref in producer_inputs(plan['producer_inputs']).values():
                self.files[producer_ref['path']] = tuple(producer_ref['signature9'])
                for node,value in parents(Path(producer_ref['path'])).items():
                    need(node not in self.nodes or self.nodes[node]==value,'parent-original-ancestor-conflict');self.nodes[node]=value
        need(digest(plan['birth_source_sha256']), 'installed-birth-pin-required')
        mapping = decode(read(plan['sdk_map']))
        need(mapping.get('publication_native_scope_birth.py') == plan['birth_source_sha256'], 'birth-pin-SDK-map')
        projection_ref = plan['scope_projection']; read(projection_ref)
        need(mapping.get('publication_native_configured_scope.py') == projection_ref['sha256'], 'scope-projection-SDK-pin')
        self.files[projection_ref['path']] = tuple(projection_ref['signature9'])
        for node,value in parents(Path(projection_ref['path'])).items():
            need(node not in self.nodes or self.nodes[node]==value,'parent-original-ancestor-conflict');self.nodes[node]=value
        projection = pinned_module(projection_ref)
        need(callable(getattr(projection, 'observed_native', None)), 'scope-projection-interface')
        _PROJECTORS[self] = projection.observed_native
        self.producer = pinned_module(plan['producer'])
        need(callable(getattr(self.producer, 'produce', None)), 'producer-interface')
        need(type(plan['nfs']) is dict and set(plan['nfs'])=={'adapter','active_parent','active_input'},'nfs-finite-plan-required')
        # Capture every NFS source ancestor before the first source read callback.
        nfs_nodes={}
        for ref in plan['nfs'].values():
            for node,value in parents(Path(ref['path'])).items():
                need(node not in nfs_nodes or nfs_nodes[node]==value,'nfs-parent-original-conflict');nfs_nodes[node]=value
        for node,value in nfs_nodes.items():
            need(node not in self.nodes or self.nodes[node]==value,'nfs-parent-original-conflict');self.nodes[node]=value
        for ref in plan['nfs'].values():
            need(ref['path'] not in self.files or self.files[ref['path']]==tuple(ref['signature9']),'nfs-source-original-conflict')
            read(ref);self.files[ref['path']]=tuple(ref['signature9'])
        final(dict(self.files),dict(self.nodes),())
        nfs_module=pinned_module(plan['nfs']['adapter'])
        need(all(callable(getattr(nfs_module,name,None)) for name in (('preflight','run_active','stop_owned','nfs_ready_archive') if archive else ('preflight','run_active','stop_owned','nfs_ready'))),'nfs-implementation-required')
        _NFS_ADAPTERS[self]=nfs_module
        self.observer = pinned_module(plan['observer'])
        need(callable(getattr(self.observer, 'partition', None) if archive else getattr(self.observer, 'observe_mapped_with_originals', None)), 'observer-interface')
        self.baselines = {}
        for key in ('reader', 'held_native', 'held_worker'):
            expected = plan[key]
            need(set(expected) == {'id', 'profile'}, 'container-plan-shape')
            row = self.inspect(expected['id'])
            need(static(row) == expected['profile'], 'fresh-container-profile')
            self.baselines[key] = row
        reader = self.baselines['reader']
        need(reader['State']['Running'] is True and reader['State']['Paused'] is False,
             'reader-compatible-initial-runtime')
        worker = self.baselines['held_worker']['State']
        need(worker['Status'] == 'created' and worker['Running'] is False and worker['Pid'] == 0,
             'worker-must-stay-created')
        # A running native daemon's explicit held publication state/process is
        # proven only by the required fresh producer, never by container health.
        self.core = encode(dict(plan=self.plan, files=self.files, nodes=self.nodes,
                                source=self.source_ref, input=self.plan_ref, engine=id(self.engine),
                                thread=self.thread, deadline=self.deadline))
        final(dict(self.files), dict(self.nodes), ())
        _CORES[self] = self.core; _GENERATED[self] = encode(self.generated); _PHASES[self] = {}
        self.op.mkdir(mode=0o700); self.op_fact = tuple(five(os.lstat(self.op))); self.sync(self.op.parent)
        self.emit('intent.json', dict(version=2, nonce=plan['nonce'], automatic_replay=False,
                                      publication_acceptance=False))

    def left(self):
        need(threading.get_ident() == self.thread and time.monotonic() < self.deadline, 'parent-lifetime')
        need(encode(dict(plan=self.plan, files=self.files, nodes=self.nodes,
                         source=self.source_ref, input=self.plan_ref, engine=id(self.engine),
                                thread=self.thread, deadline=self.deadline)) == _CORES.get(self), 'original-parent-core')
        need(str(self.op) == self.plan['operation'] and encode(self.generated) == _GENERATED.get(self), 'parent-output-core')
        return max(0.001, self.deadline - time.monotonic())

    def inspect(self, cid):
        need(digest(cid), 'exact-container-id')
        rows = decode(self.engine.run(['inspect', cid], max(0.001, self.deadline - time.monotonic())))
        need(type(rows) is list and len(rows) == 1 and rows[0]['Id'] == cid, 'fresh-inspect')
        return rows[0]

    def sync(self, path):
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def emit(self, name, document):
        need(re.fullmatch(r'[a-z0-9_-]+(?:\.(?:lifecycle|birth))?\.json', name) is not None, 'finite-output')
        self.left()
        raw = encode(document); need(0 < len(raw) <= MAX, 'output-bound')
        directory = os.open(self.op, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            need(tuple(five(os.fstat(directory))) == self.op_fact
                 and tuple(five(os.lstat(self.op))) == self.op_fact, 'operation-directory-FD')
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            try:
                offset = 0
                while offset < len(raw):
                    count = os.write(fd, raw[offset:]); need(count > 0, 'write-short'); offset += count
                os.fsync(fd); fact = nine(os.fstat(fd))
            finally:
                os.close(fd)
            os.fsync(directory)
            value = dict(path=str(self.op / name), sha256=hashlib.sha256(raw).hexdigest(), signature9=fact)
            need(read(value) == raw, 'durable-readback')
            self.generated[value['path']] = copy.deepcopy(value)
            _GENERATED[self] = encode(self.generated)
            self.left()
            return value
        finally:
            os.close(directory)

    def continuous(self):
        files = dict(self.files); nodes = dict(self.nodes)
        files.update({p: tuple(v['signature9']) for p, v in self.generated.items()})
        nodes[str(self.op)] = self.op_fact
        for path,fact in _OUTPUT_NODES.get(self,{}).items():
            need(path not in nodes or nodes[path]==fact,'output-node-original-conflict');nodes[path]=fact
        self.left()
        for value in (self.plan_ref, self.source_ref, self.plan['provider'],
                      self.plan['producer'], self.plan['observer'], self.plan['sdk_map']):
            read(value)
        values = {key: self.inspect(self.plan[key]['id'])
                  for key in ('reader', 'held_native', 'held_worker')}
        for key, value in values.items():
            need(static(value) == static(self.baselines[key]), 'continuous-profile')
        need(lifecycle_state(values['held_native']) == lifecycle_state(self.baselines['held_native'])
             and lifecycle_state(values['held_worker']) == lifecycle_state(self.baselines['held_worker']),
             'other-writer-incarnation')
        stopped(values['reader'])
        if hasattr(self, 'stop_state'):
            need(lifecycle_state(values['reader']) == lifecycle_state({'State': self.stop_state}), 'reader-stop-incarnation')
        self.events()
        self.left(); final(files, nodes, ())
        return values

    def events(self):
        for key in ('reader', 'held_native', 'held_worker'):
            raw = self.engine.run(['events', '--since', self.event_start, '--until', str(int(time.time()) + 1),
                                   '--filter', 'container=' + self.plan[key]['id'], '--format', '{{json .}}'], self.left())
            for line in raw.splitlines():
                event = decode(line)
                need(event.get('Actor', {}).get('ID') == self.plan[key]['id'], 'event-scope')
                need(event.get('Action') not in ('start', 'restart', 'unpause', 'destroy', 'kill', 'die')
                     or key == 'reader' and event.get('Action') in ('kill', 'die')
                     and self.phase == 'stopping', 'continuous-quiescence-event')

    def produce(self, phase, context):
        need(phase in ('native-observation', 'backup-controls', 'phase-custody',
                       'nfs-ready', 'archive-nfs-ready', 'terminal-observation'), 'producer-phase')
        request = dict(version=1, phase=phase, nonce=self.plan['nonce'],
                       operation=str(self.op), deadline_monotonic=self.deadline,
                       parent_plan=copy.deepcopy(self.plan_ref), parent_source=copy.deepcopy(self.source_ref),
                       context=copy.deepcopy(context))
        expected_files = dict(self.files); expected_nodes = dict(self.nodes)
        for path,fact in _OUTPUT_NODES.get(self,{}).items():
            need(path not in expected_nodes or expected_nodes[path]==fact,'producer-output-node-conflict');expected_nodes[path]=fact
        if phase in ('nfs-ready','archive-nfs-ready'):
            module=_NFS_ADAPTERS.get(self);need(module is not None,'nfs-owning-module-required')
            result=(module.nfs_ready_archive if phase=='archive-nfs-ready' else module.nfs_ready)(self,request,watch=self.continuous)
        else:result = self.producer.produce(phase, request, watch=self.continuous)
        need(type(result) is dict and set(result) == {'version', 'phase', 'nonce', 'evidence'}
             and type(result['version']) is int and result['version'] == 1
             and result['phase'] == phase and result['nonce'] == self.plan['nonce'], 'producer-result-schema')
        output = copy.deepcopy(result['evidence'])
        self.left(); read(self.plan['producer']); final(expected_files, expected_nodes, ())
        return output

    def phase_input(self, phase, payload, custody_context=None):
        if self.plan.get('action')=='archive-one':return self.archive_phase_input(phase,payload,custody_context)
        need(phase in ('backup', 'prepare', 'execute', 'verify-terminal'), 'finite-parent-phase')
        action_phase = 'execute' if phase == 'verify-terminal' else phase
        if phase == 'verify-terminal':
            need(custody_context is not None and 'terminal_manifest' in custody_context
                 and payload.get('terminal_manifest') == self.mapping.child_ref(custody_context['terminal_manifest']),
                 'terminal-phase-manifest-binding')
            need(payload.get('execute_ack')==self.mapping.child_ref(custody_context['execute_ack']),'terminal-phase-execute-ACK-binding')
        host_path = self.op / (phase + '-input.json')
        phase_directory = self.op / phase
        phase_directory.mkdir(mode=0o700)
        info=os.lstat(phase_directory);phase_fact=tuple(five(info))
        need(stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode)==0o700 and info.st_uid==os.geteuid(),'phase-directory-intended-metadata')
        _OUTPUT_NODES.setdefault(self,{})[str(phase_directory)]=phase_fact
        self.sync(self.op)
        provider = self.mapping.child_ref(self.plan['provider'])
        command = command_template(provider, phase, self.mapping.child(host_path))
        value = dict(payload, version=1, nonce=self.plan['nonce'], action='negative-five',
                     parent_sha256=self.source_ref['sha256'], command_template=command,
                     operation=self.mapping.child(phase_directory), selected_image=self.plan['selected_image'],
                     sdk_map=self.mapping.child_ref(self.plan['sdk_map']),
                     admission_source_sha256=self.plan['admission_source_sha256'],
                     **({} if phase == 'backup' else {'action_input': self.mapping.child_ref(self.plan['action_inputs'][action_phase])}),
                     native=copy.deepcopy(self.plan['native']), bounds=copy.deepcopy(self.plan['bounds']),
                     seconds=max(1, int(self.left())))
        input_ref = self.emit(phase + '-input.json', value)
        actual = actual_command(command, input_ref['sha256'])
        if phase != 'backup':
            need(custody_context is not None, 'phase-custody-required')
            invocation = dict(input_path=self.mapping.child(input_ref['path']),
                              input_sha256=input_ref['sha256'], parent_sha256=self.source_ref['sha256'],
                              provider_sha256=self.plan['provider']['sha256'], command=actual, nonce=self.plan['nonce'])
            custody = self.produce('phase-custody', dict(custody_context, phase=phase,
                                                        invocation=invocation, stage='prebirth'))
            need(set(custody) == {'reader', 'proofs', 'birth_seed'}
                 and 'native_scope' not in custody['proofs'], 'prebirth-custody-producer')
            seed = copy.deepcopy(custody['birth_seed'])
            need(set(seed) == {'version', 'kind', 'invocation', 'parent_source', 'birth_source',
                              'config', 'worker_library', 'selected_image'}
                 and type(seed['version']) is int and seed['version'] == 1
                 and seed['kind'] == 'selected-child-native-scope-birth'
                 and seed['invocation'] == invocation
                 and seed['parent_source'] == self.mapping.child_ref(self.source_ref)
                 and seed['birth_source'] == dict(path='/app/mylar3/mylar/publication_native_scope_birth.py',
                                                 sha256=self.plan['birth_source_sha256'])
                 and seed['selected_image'] == self.plan['selected_image'], 'prebirth-seed-binding')
            need(set(seed['config']) == {'path', 'sha256'} and digest(seed['config']['sha256']), 'birth-config-ref')
            absolute(seed['config']['path']); absolute(seed['worker_library'])
            seed_ref = self.emit(phase + '-input.birth.json', seed)
            pending = dict(phase=phase, input=copy.deepcopy(input_ref), invocation=invocation,
                           reader=copy.deepcopy(custody['reader']),
                           proofs={k: self.mapping.child_ref(v) for k, v in custody['proofs'].items()},
                           seed=seed, seed_ref=seed_ref, accepted=False)
            _PHASES[self][phase] = pending
        need(tuple(five(os.lstat(phase_directory))) == phase_fact, 'phase-directory-final')
        return input_ref, actual

    def native_equivalent(self, original, current):
        # Use the exact checked installed scope's complete projection, never
        # a parent-maintained list of fields or generic counter exceptions.
        projection = _PROJECTORS.get(self)
        need(projection is not None, 'original-scope-projector')
        if 'scope_projection' in self.plan:
            read(self.plan['scope_projection'])
        first = projection(copy.deepcopy(original))
        second = projection(copy.deepcopy(current))
        if 'scope_projection' in self.plan:
            read(self.plan['scope_projection'])
        return first == second

    def accept_birth(self, phase, input_ref, actual, message, fresh, child):
        # Capture ALL admitted original vectors before copy/read/projection/IPC
        # callbacks. New birth facts never refresh or overwrite those baselines.
        original_files = {path: tuple(value) for path, value in self.files.items()}
        for path, value in self.generated.items():
            signature = tuple(value['signature9'])
            if path in original_files and original_files[path] != signature:
                raise Held('birth-original-generated-conflict')
            original_files[path] = signature
        original_nodes = {path: tuple(value) for path, value in self.nodes.items()}
        if str(self.op) in original_nodes and original_nodes[str(self.op)] != self.op_fact:
            raise Held('birth-original-operation-conflict')
        original_nodes[str(self.op)] = self.op_fact
        expected_child = copy.deepcopy(child)
        pending = copy.deepcopy(_PHASES.get(self, {}).get(phase))
        need(pending is not None and pending['accepted'] is False
             and pending['input'] == input_ref and pending['invocation']['command'] == actual,
             'birth-original-phase')
        need(type(message['birth']) is dict and set(message['birth']) == {'source_sha256', 'seed_sha256', 'native_scope'},
             'birth-commit-shape')
        birth = copy.deepcopy(message['birth'])
        need(birth['source_sha256'] == self.plan['birth_source_sha256']
             and birth['seed_sha256'] == pending['seed_ref']['sha256'], 'birth-source-seed')
        child_ref = birth['native_scope']
        child_path = str(Path(self.mapping.child(input_ref['path'])).with_suffix('.native-scope.json'))
        need(type(child_ref) is dict and set(child_ref) == {'path', 'sha256', 'signature9'}
             and child_ref['path'] == child_path and digest(child_ref['sha256'])
             and type(child_ref['signature9']) is list and len(child_ref['signature9']) == 9
             and all(type(x) is int for x in child_ref['signature9'])
             and stat.S_ISREG(child_ref['signature9'][5])
             and stat.S_IMODE(child_ref['signature9'][5]) == 0o600
             and child_ref['signature9'][6] == 1000 and child_ref['signature9'][8] == 1
             and 0 < child_ref['signature9'][2] <= MAX, 'birth-fixed-child-proof')
        host_path = absolute(self.mapping.host(child_path))
        # HOST incarnation is captured independently. CHILD dev/inode facts are
        # checked by the child against its original namespace, never host-normalized.
        z = os.lstat(host_path)
        host_ref = dict(path=str(host_path), sha256=child_ref['sha256'], signature9=nine(z))
        raw = read(host_ref); document = decode(raw)
        if self.plan.get('action')=='archive-one':
            self.generated[host_ref['path']]=copy.deepcopy(host_ref);_GENERATED[self]=encode(self.generated)
        need(set(document) == {'version', 'kind', 'invocation', 'native', 'worker', 'child_mounts', 'config',
                               'config_module', 'main_module', 'worker_library', 'tool_root', 'ancestors'}
             and document['version'] == 1 and type(document['version']) is int
             and document['kind'] == 'existing-native-configured-scope'
             and document['invocation'] == pending['invocation']
             and self.native_equivalent(document['native'], fresh['native'])
             and document['worker'] == fresh['worker']
             and document['child_mounts'] == fresh['child_mounts']
             and document['config']['path'] == pending['seed']['config']['path']
             and document['config']['sha256'] == pending['seed']['config']['sha256']
             and document['worker_library'] == pending['seed']['worker_library'], 'birth-proof-observation-binding')
        proofs = copy.deepcopy(pending['proofs']); proofs['native_scope'] = child_ref
        sidecar = dict(version=1, kind='owning-reader-pipe-custody', nonce=self.plan['nonce'],
                       input_sha256=input_ref['sha256'], command=actual,
                       parent_source=self.mapping.child_ref(self.source_ref), reader=pending['reader'],
                       proofs=proofs, deadline_seconds=max(1, int(self.left())))
        sidecar_ref = self.emit(phase + '-input.lifecycle.json', sidecar)
        lifecycle = dict(path=self.mapping.child(sidecar_ref['path']), sha256=sidecar_ref['sha256'])
        response = {**message, 'type': 'birth-accepted', 'birth': birth, 'lifecycle': lifecycle,
                    'execution_authority': False, 'publication_acceptance': False, **fresh,
                    'child_source_sha256': self.phase_provider(phase)['sha256'], 'child_image': self.plan['selected_image']}
        response = encode(copy.deepcopy(response)) + b'\n'
        need(len(response) <= MAX, 'birth-response-bound')
        expected_files = {host_ref['path']: tuple(host_ref['signature9']),
                          sidecar_ref['path']: tuple(sidecar_ref['signature9']),
                          pending['seed_ref']['path']: tuple(pending['seed_ref']['signature9'])}
        expected_nodes = parents(host_path); expected_nodes.update(parents(Path(sidecar_ref['path'])))
        for path, value in original_files.items():
            if path in expected_files and expected_files[path] != value:
                raise Held('birth-merged-file-conflict')
            expected_files[path] = value
        for path, value in original_nodes.items():
            if path in expected_nodes and tuple(expected_nodes[path]) != value:
                raise Held('birth-merged-node-conflict')
            expected_nodes[path] = value
        self.continuous(); self.left()
        need(same_runtime(self.inspect(expected_child['Id']), expected_child), 'birth-final-child-profile')
        # No source/hash/copy/producer helper follows this raw closure.
        for path, expected in expected_nodes.items():
            z = os.lstat(path)
            if (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) != tuple(expected):
                raise Held('birth-ancestor-final')
        for path, expected in expected_files.items():
            z = os.lstat(path)
            if (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
                    z.st_mode, z.st_uid, z.st_gid, z.st_nlink) != expected:
                raise Held('birth-file-final')
        _PHASES[self][phase]['accepted'] = True
        return response

    def phase_provider(self,phase):
        return self.plan['backup_provider'] if self.plan.get('action')=='archive-one' and phase=='backup' else self.plan['provider']

    def child_phase(self, phase, input_ref, actual):
        self.continuous(); name = 'reader-' + phase + '-' + self.plan['nonce'][:16]
        command = actual[1:]
        mounts = copy.deepcopy(self.plan['mounts'])
        args = ['create', '--pull', 'never', '--name', name, '--label', 'com.homelab.reader.lifecycle=' + name,
                '--interactive', '--read-only', '--network', 'none', '--ipc', 'private', '--user', '1000:1000',
                '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '32',
                '--memory', '2g', '--memory-swap', '2g', '--env', 'PYTHONDONTWRITEBYTECODE=1',
                '--entrypoint', '/lsiopy/bin/python3']
        if self.plan.get('action')=='archive-one' and phase=='backup':args.extend(['--env','TMPDIR='+self.mapping.child(self.op/'backup')])
        for row in mounts:
            write = self.phase_write(row,phase)
            # Only private operation/scratch may be writable during backup/preparation.
            if Path(self.op) == Path(row['host']):
                write = True
            args.extend(['--mount', 'type=bind,src=' + row['host'] + ',dst=' + row['child']
                         + ('' if write else ',readonly')])
        args.extend([self.plan['selected_image'], *command])
        self.emit(phase + '-create-intent.json', dict(command=args, automatic_replay=False))
        self.continuous(); cid = self.engine.run(args, self.left()).decode().strip()
        need(digest(cid), 'child-create-ACK'); created = self.inspect(cid)
        expected_mounts = sorted((r['host'], r['child'], self.phase_write(r,phase)) for r in mounts)
        need(created['Config']['Labels'] == {'com.homelab.reader.lifecycle': name}, 'child-exact-label')
        self.profile(created, cid, command, expected_mounts, False)
        child_static = static(created); sequence = 0
        self.emit(phase + '-start-intent.json', dict(id=cid, automatic_replay=False))
        def challenge(message):
            nonlocal sequence
            original_files = dict(self.files)
            original_files.update({p: tuple(v['signature9']) for p, v in self.generated.items()})
            original_nodes = dict(self.nodes); original_nodes[str(self.op)] = self.op_fact
            observed = self.continuous()
            if message is None:
                return None
            base = {'protocol', 'type', 'nonce', 'input_sha256', 'parent_sha256', 'sequence', 'challenge'}
            need((set(message) == base and message['type'] == 'challenge'
                  or set(message) == base | {'birth'} and message['type'] == 'birth-commit')
                 and message['protocol'] == 'reader-lifecycle-pipe-v1' and message['nonce'] == self.plan['nonce']
                 and message['input_sha256'] == input_ref['sha256']
                 and message['parent_sha256'] == self.source_ref['sha256']
                 and type(message['sequence']) is int and message['sequence'] == sequence + 1
                 and digest(message['challenge']), 'challenge-binding')
            sequence += 1; current = self.inspect(cid)
            need(static(current) == child_static and current['State']['Running'] is True
                 and current['State']['Pid'] > 0 and current['State']['Paused'] is False, 'child-running-profile')
            fresh = self.produce('native-observation', dict(observations=observed, child=current,
                                                           child_mounts=current['Mounts']))
            need(set(fresh) == {'native', 'worker', 'child_mounts'}
                 and same_runtime(fresh['native']['inspect'], observed['held_native'])
                 and same_runtime(fresh['worker'], observed['held_worker'])
                 and fresh['child_mounts'] == current['Mounts'], 'fresh-native-worker-mounts')
            # Reinspect after producer callbacks; stale snapshots never close.
            self.continuous(); need(same_runtime(self.inspect(cid), current), 'late-child-profile')
            if message['type'] == 'birth-commit':
                need(phase in ('prepare', 'execute', 'verify-terminal'), 'birth-purpose')
                return self.accept_birth(phase, input_ref, actual, message,
                                         {**fresh, 'reader': observed['reader']}, current)
            response = encode({**message, 'type': 'observation', 'reader': observed['reader'],
                               'child_source_sha256': self.phase_provider(phase)['sha256'],
                               'child_image': self.plan['selected_image'], **fresh}) + b'\n'
            need(len(response) <= MAX, 'challenge-response-bound')
            self.continuous(); need(same_runtime(self.inspect(cid), current), 'challenge-final-child')
            for path, expected in original_nodes.items():
                z = os.lstat(path)
                if (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) != tuple(expected):
                    raise Held('challenge-ancestor-final')
            for path, expected in original_files.items():
                z = os.lstat(path)
                if (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
                        z.st_mode, z.st_uid, z.st_gid, z.st_nlink) != tuple(expected):
                    raise Held('challenge-file-final')
            return response
        ack = self.engine.interactive(cid, challenge, self.left())
        if phase != 'backup':
            need(_PHASES.get(self, {}).get(phase, {}).get('accepted') is True, 'child-ACK-before-birth')
        report_ref = validate_ack(ack, phase, self.plan['nonce'], self.phase_provider(phase)['sha256'])
        exited = self.inspect(cid)
        need(static(exited) == child_static, 'child-final-static')
        self.profile(exited, cid, command, expected_mounts, True)
        self.continuous()
        need(report_ref['path'] == self.mapping.child(self.op / phase / (phase + '-report.json')), 'fixed-report-child-path')
        host_ref = {**report_ref, 'path': self.mapping.host(report_ref['path'])}
        report = decode(read(host_ref))
        if self.plan.get('action')=='archive-one':
            self.generated[host_ref['path']]=copy.deepcopy(host_ref);_GENERATED[self]=encode(self.generated)
        need(report['phase'] == phase and report['nonce'] == self.plan['nonce']
             and report['final_ack_required'] is True and report['provider_continuity_verified'] is False,
             'report-factual-only')
        self.emit(phase + '-ack.json', ack)
        return report

    def profile(self, row, cid, command, mounts, exited):
        h, c, s = row['HostConfig'], row['Config'], row['State']
        need(row['Id'] == cid and row['Image'] == self.plan['selected_image']
             and c['User'] == '1000:1000' and c['Entrypoint'] == ['/lsiopy/bin/python3']
             and c['Cmd'] == command and c['OpenStdin'] is True and c['Tty'] is False, 'child-profile-command')
        need(h['ReadonlyRootfs'] is True and h['Privileged'] is False and h['NetworkMode'] == 'none'
             and h['IpcMode'] == 'private' and h['PidMode'] == '' and h['CapDrop'] == ['ALL']
             and not h.get('CapAdd') and h['SecurityOpt'] == ['no-new-privileges']
             and h['PidsLimit'] == 32 and h['Memory'] == 2 * 1024**3
             and h['MemorySwap'] == 2 * 1024**3
             and h.get('RestartPolicy', {}).get('Name') in ('', 'no')
             and all(not h.get(k) for k in ('Devices', 'DeviceRequests', 'Binds', 'Tmpfs', 'PortBindings')), 'child-isolation')
        need(len(row['Mounts']) == len(mounts) and all(r['Type'] == 'bind' for r in row['Mounts'])
             and sorted((r['Source'], r['Destination'], r['RW']) for r in row['Mounts']) == mounts, 'child-mount-profile')
        need(s['Status'] == ('exited' if exited else 'created') and s['Running'] is False and s['Pid'] == 0
             and all(s.get(k) is False for k in ('Paused', 'Restarting', 'Dead', 'OOMKilled'))
             and (not exited or s['ExitCode'] == 0), 'child-final-state')

    def terminal_mapper(self):
        # Freeze source-bound mount spelling before observer/copy callbacks.
        mounts = tuple((row['host'], row['child'], row['write']) for row in self.plan['mounts'])
        host_roots = tuple(Path(host) for host, child, write in mounts)
        source_root = Path(self.source_ref['path']).parent
        paths = Paths([dict(host=host, child=child, write=write) for host, child, write in mounts])
        def mapped(value):
            path = absolute(str(value))
            if any(path == root or root in path.parents for root in (*host_roots, source_root)):
                return str(path)
            host = paths.host(str(path))
            need(paths.child(host) == str(path), 'terminal-host-path-roundtrip')
            return host
        return mapped

    def archive_phase_input(self,phase,payload,custody_context):
        need(phase in ('backup','execute','verify-terminal'),'archive-finite-phase')
        host_path=self.op/(phase+'-input.json');directory=self.op/phase
        directory.mkdir(mode=0o700);fact=tuple(five(os.lstat(directory)))
        need((fact[2]&0o777)==0o700 and fact[3]==os.geteuid(),'archive-phase-private')
        _OUTPUT_NODES.setdefault(self,{})[str(directory)]=fact;self.sync(self.op)
        provider=self.mapping.child_ref(self.phase_provider(phase));command=command_template(provider,phase,self.mapping.child(host_path))
        value=dict(payload,version=1,nonce=self.plan['nonce'],action='archive-one-backup' if phase=='backup' else 'archive-one',parent_sha256=self.source_ref['sha256'],command_template=command,operation=self.mapping.child(directory),selected_image=self.plan['selected_image'],sdk_map=self.mapping.child_ref(self.plan['sdk_map']))
        if phase=='backup':value.update(native=copy.deepcopy(self.plan['native']),bounds=copy.deepcopy(self.plan['bounds']),seconds=max(1,int(self.left())))
        else:
            request=decode(read(self.plan['producer_inputs']['archive_request']))
            value.update(owner=request['owner'],operation_id=request['operation_id'])
        ref=self.emit(phase+'-input.json',value);actual=actual_command(command,ref['sha256'])
        if phase!='backup':
            need(custody_context is not None,'archive-phase-custody-required')
            invocation=dict(input_path=self.mapping.child(ref['path']),input_sha256=ref['sha256'],parent_sha256=self.source_ref['sha256'],provider_sha256=self.plan['provider']['sha256'],command=actual,nonce=self.plan['nonce'])
            supplied=self.produce('phase-custody',dict(custody_context,phase=phase,invocation=invocation,stage='prebirth'))
            need(set(supplied)=={'reader','proofs','birth_seed'} and 'native_scope' not in supplied['proofs'] and 'archive_sdk_map' in supplied['proofs'],'archive-owning-prebirth-custody')
            need(supplied['proofs']['archive_sdk_map']==self.plan['sdk_map'],'archive-original-SDK-proof')
            seed=copy.deepcopy(supplied['birth_seed'])
            need(set(seed)=={'version','kind','invocation','parent_source','birth_source','config','worker_library','selected_image'} and type(seed['version']) is int and seed['version']==1 and seed['kind']=='selected-child-native-scope-birth' and seed['invocation']==invocation and seed['parent_source']==self.mapping.child_ref(self.source_ref) and seed['birth_source']==dict(path='/app/mylar3/mylar/publication_native_scope_birth.py',sha256=self.plan['birth_source_sha256']) and seed['selected_image']==self.plan['selected_image'],'archive-prebirth-source-binding')
            seedref=self.emit(phase+'-input.birth.json',seed)
            _PHASES[self][phase]=dict(phase=phase,input=copy.deepcopy(ref),invocation=invocation,reader=copy.deepcopy(supplied['reader']),proofs={k:self.mapping.child_ref(v) for k,v in supplied['proofs'].items()},seed=seed,seed_ref=seedref,accepted=False)
        need(tuple(five(os.lstat(directory)))==fact,'archive-phase-original-directory')
        return ref,actual

    def phase_write(self,row,phase):
        if Path(row['host'])==self.op:return True
        if self.plan.get('action')!='archive-one':return row['write'] and phase=='execute'
        if phase=='execute':return row['write']
        if phase=='verify-terminal':
            scope=decode(read(self.plan['producer_inputs']['archive_scopes']))
            return row['write'] and row['host']==scope['scratch']
        return False

    def execute_archive(self):
        try:
            nfs=_NFS_ADAPTERS.get(self);need(nfs is not None,'archive-NFS-owner-required')
            need(callable(getattr(self.observer,'partition',None)),'archive-terminal-vector-implementation')
            for ref in (self.plan['backup_provider'],self.plan['observer']):read(ref)
            for ref in (self.plan['provider'],self.plan['backup_provider']):
                module=pinned_module(ref);need(getattr(module,'PARENT_SOURCE_SHA',None)==self.source_ref['sha256'],'archive-reviewed-parent-pin-required-before-stop')
            nfs.preflight(self);nfs.run_active(self);observed=nfs.stop_owned(self)
            runtime=copy.deepcopy(observed['reader'])
            for mount in runtime['Mounts']:
                if mount['Type']=='bind':need(self.mapping.child(mount['Source'])==mount['Source'],'archive-backup-host-canonical-bind')
            inp,cmd=self.phase_input('backup',dict(runtime=runtime));backup=self.child_phase('backup',inp,cmd)
            backup=dict(backup,manifest={**backup['manifest'],'path':self.mapping.host(backup['manifest']['path'])},restore_root=self.mapping.host(backup['restore_root']))
            # Child backup control refs use canonical HOST mount spelling. No
            # copied HOST inode is asserted as a CHILD inode at birth.
            controls=self.produce('backup-controls',dict(backup=backup,observations=observed))
            need(set(controls)=={'controls','archive_scopes'} and set(controls['controls'])==ARCHIVE_ROLES,'archive-eight-neutral-roles')
            for ref in (*controls['controls'].values(),controls['archive_scopes']):read(ref)
            context=dict(backup=backup,controls=controls['controls'],archive_scopes=controls['archive_scopes'],observations=self.continuous())
            payload=dict(controls={k:self.mapping.child_ref(v) for k,v in controls['controls'].items()},archive_scopes=self.mapping.child_ref(controls['archive_scopes']))
            inp,cmd=self.phase_input('execute',payload,context)
            ready=self.produce('archive-nfs-ready',dict(input=inp,command=cmd,context=context));need(set(ready)=={'evidence'},'archive-NFS-finite-facts');read(ready['evidence'])
            report=self.child_phase('execute',inp,cmd)
            request=decode(read(self.plan['producer_inputs']['archive_request']))
            need(report['kind']=='archive-one-owning-execute-observation' and report['owner']==request['owner'] and report['operation_id']==request['operation_id'] and report['outcome'] in ('observed-forward','observed-rollback'),'archive-execute-owning-result')
            need(all(report[k] is False for k in ('reader_index_acceptance','ordinary_import_grant','publication_acceptance','mutation_authority','automatic_replay')),'archive-execute-false-rights')
            originals=report['originals'];expected=self.mapping.child(self.op/'execute'/'execution-originals.json')
            need(type(originals) is dict and originals['path']==expected,'archive-original-fixed-execute-record')
            original_host={**originals,'path':self.mapping.host(originals['path'])};read(original_host)
            # ACK/report/record remain original references, never status-derived.
            ack=copy.deepcopy(self.generated[str(self.op/'execute-ack.json')]);ackvalue=decode(read(ack));reportref=ackvalue['report'];hostreport={**reportref,'path':self.mapping.host(reportref['path'])}
            need(decode(read(hostreport))==report,'archive-original-execute-report')
            context.update(observations=self.continuous(),execution_originals=original_host)
            payload['execution_originals']=self.mapping.child_ref(original_host)
            inp,cmd=self.phase_input('verify-terminal',payload,context)
            verified=self.child_phase('verify-terminal',inp,cmd)
            need(verified['owner']==request['owner'] and verified['operation_id']==request['operation_id'] and verified['originals']==originals and verified['baseline']==report['baseline'] and verified['outcome']==report['outcome'],'archive-fresh-terminal-original-join')
            sdk=decode(read(self.plan['sdk_map']));phaseproof=self.op/'verify-terminal-input.native-scope.json'
            scope_ref=self.generated.get(str(phaseproof))
            # accept_birth retains the independent HOST proof ref after exact
            # selected-child/source/mount/config-module observation joins.
            need(scope_ref is not None,'archive-original-accepted-native-scope')
            native=decode(read(scope_ref));image_sources={native[k]['path']:native[k] for k in ('config_module','main_module')}
            mapper=self.terminal_mapper()
            vectors=self.observer.partition(verified,path_mapper=mapper,sdk_map=sdk,mounts=copy.deepcopy(self.plan['mounts']),image_sources=image_sources)
            files={str(k):tuple(v) for k,v in vectors['files'].items()};nodes={str(k):tuple(v) for k,v in vectors['nodes'].items()};claims=tuple((str(k),None if v is None else tuple(v)) for k,v in vectors['claims'].items());absent=tuple(vectors['absent']);names=tuple((str(k),tuple(v)) for k,v in vectors['censuses'].items())
            for ref in (original_host,ack,hostreport):
                need(ref['path'] not in files or files[ref['path']]==tuple(ref['signature9']),'archive-terminal-original-ref-conflict');files[ref['path']]=tuple(ref['signature9'])
            for group,original in ((files,self.files),(nodes,self.nodes)):
                for path,value in original.items():
                    value=tuple(value);need(path not in group or group[path]==value,'archive-terminal-original-control-conflict');group[path]=value
            for path,ref in self.generated.items():
                value=tuple(ref['signature9']);need(path not in files or files[path]==value,'archive-terminal-generated-conflict');files[path]=value
            for path,value in _OUTPUT_NODES.get(self,{}).items():
                need(path not in nodes or nodes[path]==value,'archive-terminal-phase-node-conflict');nodes[path]=value
            need(str(self.op) not in nodes or nodes[str(self.op)]==self.op_fact,'archive-operation-original-conflict');nodes[str(self.op)]=self.op_fact
            intent=self.emit('resume-intent.json',dict(reader=self.plan['reader']['id'],outcome=verified['outcome'],child_image_vectors=dict(files=vectors['child_image_files'],nodes=vectors['child_image_nodes']),reader_index_acceptance=False,publication_acceptance=False,automatic_replay=False))
            files[intent['path']]=tuple(intent['signature9'])
            self.continuous();seconds=self.left()
            # Last semantic, source, engine and mapping callbacks have finished.
            for path,expected_names in names:
                if tuple(sorted(os.listdir(path)))!=expected_names:raise Held('archive-resume-census')
            for path,value in nodes.items():
                z=os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid)!=value:raise Held('archive-resume-node')
            for path,value in files.items():
                z=os.lstat(path)
                if (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)!=value:raise Held('archive-resume-file')
            for path,value in claims:
                try:z=os.lstat(path)
                except FileNotFoundError:
                    if value is not None:raise Held('archive-resume-missing-claim')
                    continue
                actual=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
                if value is None or actual!=value or (z.st_mode&0o170000)==0o040000:raise Held('archive-resume-claim')
            for path in absent:
                try:os.lstat(path)
                except FileNotFoundError:continue
                raise Held('archive-resume-absence')
            resumed=self.engine.run(['start',self.plan['reader']['id']],seconds).decode().strip();need(resumed==self.plan['reader']['id'],'archive-resume-ACK-unknown')
            current=self.inspect(resumed);need(static(current)==static(self.baselines['reader']) and current['State']['Running'] is True and current['State']['Paused'] is False and current['State']['Pid']>0,'archive-compatible-reader-resume')
            self.phase='complete'
            return self.emit('complete.json',dict(version=1,action='archive-one',outcome='parent-complete',reader_index_acceptance=False,ordinary_import_grant=False,publication_acceptance=False,automatic_replay=False))
        except BaseException:
            self.phase='uncertain';raise Held('archive-parent-uncertain-hold-no-replay-or-resume') from None

    def execute(self):
        if self.plan.get('action')=='archive-one':return self.execute_archive()
        operation_path = str(self.op); operation_original = tuple(self.op_fact)
        try:
            mapper = self.terminal_mapper()
            # Checked producer implementation availability is required BEFORE
            # any stop/execute; callable presence creates no runtime authority.
            need(all(callable(getattr(self.producer, name, None)) for name in
                     ('terminal_observation', 'terminal_phase_custody')), 'terminal-producer-implementation-required')
            need(callable(getattr(self.observer, 'observe_mapped_with_originals', None)), 'terminal-observer-implementation-required')
            nfs_module=_NFS_ADAPTERS.get(self)
            need(nfs_module is not None,'nfs-owning-module-required')
            nfs_module.preflight(self)  # implementation and source evidence before stop
            nfs_module.run_active(self) # owning running-reader canary, no receipt reconstruction
            observed=nfs_module.stop_owned(self)
            runtime = copy.deepcopy(observed['reader'])
            # Provider backup sees canonical host config roots also mounted in child.
            for mount in runtime['Mounts']:
                if mount['Type'] == 'bind':
                    need(self.mapping.child(mount['Source']) == mount['Source'], 'backup-host-path-not-mounted-canonically')
            inp, command = self.phase_input('backup', dict(runtime=runtime))
            backup = self.child_phase('backup', inp, command)
            controls = self.produce('backup-controls', dict(backup=backup, observations=observed))
            need(set(controls) == {'controls'} and set(controls['controls']) == ROLES, 'nine-role-producer')
            for value in controls['controls'].values():
                read(value)
            reports = {}
            for phase in ('prepare', 'execute'):
                context = dict(backup=backup, controls=controls['controls'], observations=self.continuous())
                payload = dict(controls={k: self.mapping.child_ref(v) for k, v in controls['controls'].items()})
                inp, command = self.phase_input(phase, payload, context)
                if phase == 'execute':
                    nfs = self.produce('nfs-ready', dict(input=inp, command=command, context=context))
                    need(set(nfs) == {'evidence'}, 'nfs-producer-schema'); read(nfs['evidence'])
                reports[phase] = self.child_phase(phase, inp, command)
            execute_ack = copy.deepcopy(self.generated[str(self.op/'execute-ack.json')])
            terminal = self.produce('terminal-observation', dict(
                backup=backup, controls=controls['controls'], observations=self.continuous(),
                execute_action=self.plan['action_inputs']['execute'], execute_ack=execute_ack))
            need(set(terminal) == {'manifest', 'outcome'} and terminal['outcome'] in
                 ('observed-forward', 'observed-rollback'), 'terminal-producer-schema')
            read(terminal['manifest'])
            context = dict(backup=backup, controls=controls['controls'], observations=self.continuous(),
                           terminal_manifest=terminal['manifest'], execute_ack=execute_ack)
            payload = dict(controls={k: self.mapping.child_ref(v) for k, v in controls['controls'].items()},
                           terminal_manifest=self.mapping.child_ref(terminal['manifest']), execute_ack=self.mapping.child_ref(execute_ack))
            inp, command = self.phase_input('verify-terminal', payload, context)
            # Fresh selected child/birth independently verifies factual state;
            # neither its six-field ACK nor its report grants resume.
            self.child_phase('verify-terminal', inp, command)
            result, originals = self.observer.observe_mapped_with_originals(
                terminal['manifest'], source_sha256=self.plan['observer']['sha256'], path_mapper=mapper)
            need(result['outcome'] == terminal['outcome']
                 and all(result[k] is False for k in ('publication_acceptance', 'mutation_authority',
                         'reader_resume_authority', 'recovery_capability', 'application_quiescence_verified')),
                 'observer-factual-outcome')
            need(set(originals) == {'files', 'nodes', 'absent', 'censuses'}
                 and originals['files'] and originals['nodes'], 'observer-original-vectors')
            # Primitive snapshots precede emit/copy/engine/deadline callbacks.
            files = {str(k): tuple(v) for k, v in originals['files'].items()}
            nodes = {str(k): tuple(v) for k, v in originals['nodes'].items()}
            absent = tuple(str(k) for k in originals['absent'])
            censuses = tuple((str(k), tuple(v)) for k, v in originals['censuses'].items())
            for group, admitted in ((files, self.files), (nodes, self.nodes)):
                for path, vector in admitted.items():
                    vector = tuple(vector)
                    if path in group and group[path] != vector:
                        raise Held('resume-original-conflict')
                    group[path] = vector
            for path, ref in self.generated.items():
                vector = tuple(ref['signature9'])
                if path in files and files[path] != vector:
                    raise Held('resume-generated-conflict')
                files[path] = vector
            for path,fact in _OUTPUT_NODES.get(self,{}).items():
                if path in nodes and nodes[path]!=fact:raise Held('resume-output-node-conflict')
                nodes[path]=fact
            if operation_path in nodes and nodes[operation_path] != operation_original:
                raise Held('resume-operation-original-conflict')
            nodes[operation_path] = operation_original
            intent = self.emit('resume-intent.json', dict(reader=self.plan['reader']['id'], factual_observation=result,
                                                         automatic_replay=False, publication_acceptance=False))
            intent_path = intent['path']; intent_original = tuple(intent['signature9'])
            if intent_path in files and files[intent_path] != intent_original:
                raise Held('resume-intent-original-conflict')
            files[intent_path] = intent_original
            self.continuous(); seconds = self.left()
            # All semantic/engine/producer callbacks have completed.
            for path, expected in censuses:
                if tuple(sorted(os.listdir(path))) != expected:
                    raise Held('resume-namespace-final')
            for path, expected in nodes.items():
                z = os.lstat(path)
                if (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) != expected:
                    raise Held('resume-ancestor-final')
            for path, expected in files.items():
                z = os.lstat(path)
                if (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
                        z.st_mode, z.st_uid, z.st_gid, z.st_nlink) != expected:
                    raise Held('resume-file-final')
            for path in absent:
                try:
                    os.lstat(path)
                except FileNotFoundError:
                    continue
                raise Held('resume-absence-final')
            # Root still supplies real fresh producer/image/NFS acceptance before invocation.
            resumed = self.engine.run(['start', self.plan['reader']['id']], seconds).decode().strip()
            need(resumed == self.plan['reader']['id'], 'resume-ACK-unknown')
            current = self.inspect(resumed)
            need(static(current) == static(self.baselines['reader']) and current['State']['Running'] is True
                 and current['State']['Paused'] is False and current['State']['Pid'] > 0, 'compatible-resume')
            self.phase = 'complete'
            return self.emit('complete.json', dict(version=2, nonce=self.plan['nonce'], outcome='parent-complete',
                                                   publication_acceptance=False, automatic_replay=False))
        except BaseException:
            self.phase = 'uncertain'
            raise Held('parent-uncertain-evidence-retained-no-replay-or-resume') from None


def run_operation(plan_ref, source_ref, *, engine):
    """Explicit owning host integration; no service operations on module import."""
    return LifecycleParent(plan_ref, source_ref, engine).execute()


if __name__ == '__main__':
    raise SystemExit('Source proposal: accepted owning producer/runtime integration required')
