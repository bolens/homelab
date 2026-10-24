"""Finite host-created probe; child argv never reaches ScopedDocker.

The Parent mapping admission is intentionally required. No local/NFS bypass and
no terminal capability is returned by this transport.
"""
import copy
import hashlib
import base64
import json
import re
import uuid
import os
import stat
import subprocess
import select
import time
import weakref
_PROCESS_SEALS=weakref.WeakKeyDictionary()
_PREPARED_ACKS=weakref.WeakKeyDictionary()
_PARENT_PROFILES=weakref.WeakKeyDictionary()
_FULL_PROFILES=weakref.WeakKeyDictionary()


class Held(ValueError):
    pass


def need(ok, reason):
    if not ok:
        raise Held(reason)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def mount_namespace(host, rows, host_root, child_root, expected9, actual9, *, binding=None, retention9=None):
    """Join one original export to this exact owned RW subdirectory bind."""
    from pathlib import PurePosixPath
    keys={'source','target','fstype','fsroot','options','maj:min'}
    need(type(host) is dict and set(host)==keys and type(rows) is dict
         and set(rows)=={'source','target'},'namespace-mount-schema')
    def absolute(value):
        need(type(value) is str and value.startswith('/') and '\\' not in value
             and '\0' not in value and '..' not in value.split('/')
             and str(PurePosixPath(value))==value,'namespace-canonical-path')
        return PurePosixPath(value)
    for row in (host,*rows.values()):
        need(type(row) is dict and set(row)==keys and all(type(v) is str and v for v in row.values())
             and row['fstype']=='nfs4','namespace-nfs-row')
        absolute(row['target']);absolute(row['fsroot'])
    original=absolute(host_root);target=absolute(child_root);mountpoint=absolute(host['target'])
    need(original!=mountpoint and mountpoint in original.parents,'namespace-selected-host-subtree')
    bind_original,bind_target=original,target
    if binding is not None:
        need(type(binding) is dict and set(binding)=={'host_root','child_root','root5'},'namespace-retention-binding-schema')
        bind_original=absolute(binding['host_root']);bind_target=absolute(binding['child_root'])
        need(original==target and bind_original==bind_target and bind_original.name=='R'
             and re.fullmatch('archive-publication-[a-f0-9]{64}',bind_original.parent.name) is not None
             and original.parent.parent==bind_original
             and re.fullmatch(r'\.comic-nfs-private-[a-f0-9]{32}',original.parent.name) is not None
             and re.fullmatch(r'\.comic-nfs-probe-[a-f0-9]{32}',original.name) is not None
             and mountpoint in bind_original.parents,'namespace-exact-retention-subtree')
        root5=binding['root5']
        need(type(root5) is list and len(root5)==5 and all(type(v) is int for v in root5)
             and type(retention9) in (list,tuple) and len(retention9)==9
             and all(type(v) is int for v in retention9)
             and [retention9[i] for i in (0,1,5,6,7)]==root5
             and root5[0]>0 and root5[1]>0 and stat.S_ISDIR(root5[2])
             and stat.S_IMODE(root5[2])==0o700 and root5[3:]==[1000,1000],
             'namespace-original-retention-identity')
    else:need(retention9 is None,'namespace-unrequested-retention')
    expected_root=str(absolute(host['fsroot'])/bind_original.relative_to(mountpoint))
    def export(row):
        suffix='['+row['fsroot']+']'
        source=row['source']
        return source[:-len(suffix)] if source.endswith(suffix) else source
    need(type(expected9) in (list,tuple) and len(expected9)==9
         and all(type(v) is int for v in expected9)
         and type(actual9) in (list,tuple) and list(actual9)==list(expected9)
         and expected9[0]>0 and expected9[1]>0 and stat.S_ISDIR(expected9[5])
         and stat.S_IMODE(expected9[5])==0o700 and expected9[6]==1000,
         'namespace-original-root9')
    if binding is not None:need(retention9[0]==expected9[0] and retention9[1]!=expected9[1] and expected9[7]==1000,'namespace-distinct-retention-fixture')
    need(host['maj:min']==str(os.major(expected9[0]))+':'+str(os.minor(expected9[0])),'namespace-original-device-number')
    need(rows['source']==rows['target'],'namespace-one-child-bind')
    row=rows['source']
    same_export=(row['fsroot']==expected_root and export(row)==export(host))
    source_suffix=(host['fsroot']==row['fsroot']=='/'
                   and row['source']==export(host).rstrip('/')+'/'+str(bind_original.relative_to(mountpoint)))
    need(row['target']==str(bind_target) and (same_export or source_suffix)
         and row['maj:min']==host['maj:min']
         and row['options']==host['options']
         and 'rw' in row['options'].split(',') and 'ro' not in row['options'].split(','),
         'namespace-original-export-bind')
    proof=dict(version=1,kind='original-nfs-bind-namespace-v1',host=copy.deepcopy(host),
               rows=copy.deepcopy(rows),host_root=str(original),child_root=str(target),root9=list(expected9))
    if binding is not None:
        proof.update(version=2,kind='original-nfs-retention-bind-namespace-v2',binding=copy.deepcopy(binding),retention9=list(retention9))
    return proof


def ticks(pid):
    raw=(__import__('pathlib').Path('/proc')/str(pid)/'stat').read_text();return int(raw[raw.rfind(')')+2:].split()[19])

def fd5(stream):
    z=os.fstat(stream.fileno());return (stream.fileno(),(z.st_dev,z.st_ino,z.st_mode,z.st_uid,z.st_gid))

class ProbeProcess:
    """Command/profile boundary. Constructor inputs are owning-host originals."""
    def __init__(self, spec, docker, execute, close,*,gated=False,launcher=None,namespace=None,owner=None):
        need(type(spec) is dict and set(spec) in ({'image', 'mounts', 'probe', 'kernel', 'input', 'input_sha256', 'probe_sha256'}, {'image', 'mounts', 'probe', 'kernel', 'input', 'input_sha256', 'probe_sha256','binding'}), 'probe-spec-schema')
        need(re.fullmatch(r'sha256:[a-f0-9]{64}', spec['image']) is not None, 'probe-image')
        for key in ('input_sha256', 'probe_sha256'):
            need(type(spec[key]) is str and re.fullmatch('[a-f0-9]{64}', spec[key]) is not None, 'probe-source-digest')
        mounts = spec['mounts']
        need(type(mounts) is list and 6 <= len(mounts) <= 38, 'probe-mount-bound')
        for row in mounts:
            need(type(row) is list and len(row) == 3 and type(row[2]) is bool
                 and all(type(p) is str and p.startswith('/') and '..' not in p.split('/')
                         and not any(c in p for c in ',\n\r') for p in row[:2]), 'probe-mount-shape')
        need(len({r[1] for r in mounts}) == len(mounts), 'probe-mount-destinations')
        # Fixed six mounts plus readonly protected roots. All paths are host
        # mapping originals; virtual destinations remain literal child paths.
        need(mounts[0][2] is True and mounts[1][1:] == ['/config', False]
             and mounts[0][0] == mounts[1][0] and mounts[2][2] is True
             and mounts[3][1:] == [spec['probe'], False]
             and mounts[4][1:] == [spec['kernel'], False]
             and mounts[5][1:] == [spec['input'], False]
             and all(r[2] is False for r in mounts[6:]), 'probe-finite-mount-contract')
        need(type(gated) is bool and (not gated or callable(launcher)),'probe-gated-original-launcher')
        need(namespace is None or type(namespace) is dict and set(namespace) in ({'host','host_root','child_root','root9'},{'host','host_root','child_root','root9','binding'}),'probe-namespace-original-input')
        if 'binding' in spec:
            need(type(spec['binding']) is dict and set(spec['binding'])=={'host_root','child_root','root5'},'probe-retention-binding-schema')
            need(owner is not None and namespace is not None and namespace.get('binding')==spec['binding']
                 and mounts[0]==[spec['binding']['host_root'],spec['binding']['child_root'],True], 'probe-retention-original-owner-binding')
        else:need(namespace is None or 'binding' not in namespace,'probe-unrequested-retention-binding')
        self.namespace_original=copy.deepcopy(namespace);self.namespace_tape=encode(namespace);self.namespace_proof=None
        self.gated,self.launcher=gated,launcher
        self.process=None;self.pipe_original=None;self.pid_original=None;self.process_start=None;self.running_epoch=None;self.execution_sent=False;self.kernel_output=None
        self.spec = copy.deepcopy(spec)
        self.docker = tuple(docker)
        self.name = 'comic-nfs-probe-' + uuid.uuid4().hex
        self.execute, self.close = execute, close
        self.original = encode(dict(spec=self.spec, docker=self.docker, name=self.name))
        self.cid = None
        self.cid_original = None
        self.static = None
        self.started = False
        self.terminal = False
        self.full_created=self.full_running=self.full_terminal=None
        builder=ProbeProcess._command
        self.command_builder=(builder,builder.__code__)
        _FULL_PROFILES[self]=(None,None,None,self.command_builder)
        if owner is not None:
            g=owner.left.__func__.__globals__
            need(type(owner)is g.get('LifecycleParent')and owner.left.__func__ is g['LifecycleParent'].left and g.get('_CORES',{}).get(owner)==owner.core and type(owner.engine)is g.get('ScopedDocker')
                 and getattr(execute,'__self__',None)is owner.engine and getattr(execute,'__func__',None)is g['ScopedDocker'].canary,'probe-source-owning-parent')
            helpers=tuple(g.get(k)for k in ('checked_none_network_started_static','checked_none_network_exited_static'))
            need(all(callable(f)and getattr(f,'__globals__',None)is g for f in helpers),'probe-source-profile-helpers')
            guard=g.get('none_network_profile_contract')
            need(callable(guard)and guard.__globals__ is g,'probe-source-profile-contract')
            contract=(guard,guard.__code__,guard())
            if 'binding' in spec:need(owner.mapping.nfs_probe_binding(namespace['host_root'])==spec['binding'],'probe-retention-original-parent-geometry')
            _PARENT_PROFILES[self]=(owner,g,owner.core,owner.engine,helpers,contract)

    def original_close(self):
        self.close()
        need(_FULL_PROFILES.get(self)==(self.full_created,self.full_running,self.full_terminal,self.command_builder),'probe-full-profile-seal')
        builder,code=self.command_builder
        need(ProbeProcess._command is builder and builder.__code__ is code
             and getattr(self._command,'__func__',None) is builder,'probe-original-command-builder')
        parent=_PARENT_PROFILES.get(self)
        if parent is not None:
            owner,g,core,engine,helpers,contract=parent
            need(type(owner)is g.get('LifecycleParent')and owner.core==g.get('_CORES',{}).get(owner)==core and owner.engine is engine
                 and getattr(self.execute,'__self__',None)is engine and getattr(self.execute,'__func__',None)is g['ScopedDocker'].canary
                 and helpers==tuple(g.get(k)for k in ('checked_none_network_started_static','checked_none_network_exited_static')),'probe-profile-parent-original')
            guard,code,token=contract
            need(g.get('none_network_profile_contract')is guard and guard.__code__ is code and guard.__globals__ is g and guard()is token,'probe-profile-contract-original')
        need(encode(self.namespace_original)==self.namespace_tape,'probe-namespace-original-tape')
        need(encode(dict(spec=self.spec, docker=self.docker, name=self.name)) == self.original, 'probe-original-spec')
        need(self.cid_original is None or self.cid == self.cid_original, 'probe-original-born-CID')

    def _command(self):
        """Construct argv without callbacks; callers own the boundary checks."""
        args = list(self.docker) + ['create', '--pull', 'never', '--name', self.name,
                '--label', 'com.homelab.nfs.probe=' + self.name, '--user', '1000:1000',
                '--read-only', '--network', 'none', '--cap-drop', 'ALL', '--security-opt',
                'no-new-privileges', '--pids-limit', '64', '--entrypoint', '/lsiopy/bin/python3']
        for src, dst, rw in self.spec['mounts']:
            args += ['--mount', 'type=bind,src=' + src + ',dst=' + dst + ('' if rw else ',readonly')]
        if self.gated:args+=['--interactive']
        args += [self.spec['image'], self.spec['probe'], '--input', self.spec['input'],
                 '--input-sha256', self.spec['input_sha256'], '--source-sha256',
                 self.spec['probe_sha256'], '--kernel', self.spec['kernel']]
        if self.gated:args+=['--defer-execute']
        return args

    def command(self):
        self.original_close()
        args = self.command_builder[0](self)
        self.original_close()
        return args

    def call(self, args):
        self.original_close()
        result = self.execute(args, input=None, capture_output=True, check=False, timeout=900)
        need(type(result.returncode) is int and result.returncode == 0
             and type(result.stdout) is bytes and len(result.stdout) <= 8 * 1024**2
             and type(result.stderr) is bytes and len(result.stderr) <= 4 * 1024**2, 'probe-engine-ack')
        self.original_close()
        return result

    def profile(self, row, terminal=False, running=False):
        self.original_close()
        builder,code=self.command_builder
        command = builder(self)
        need(ProbeProcess._command is builder and builder.__code__ is code
             and getattr(self._command,'__func__',None) is builder,'probe-original-command-builder')
        need(type(row) is dict and row.get('Id') == self.cid and row.get('Image') == self.spec['image'], 'probe-original-CID-image')
        c, h, s = row['Config'], row['HostConfig'], row['State']
        need(c['User'] == '1000:1000' and c['Labels'].get('com.homelab.nfs.probe') == self.name
             and c.get('Entrypoint') == ['/lsiopy/bin/python3']
             and c.get('Cmd') == command[command.index(self.spec['image']) + 1:], 'probe-original-command-label')
        need(h['ReadonlyRootfs'] is True and h['Privileged'] is False and h['NetworkMode'] == 'none'
             and h['PidMode'] == '' and not h.get('CapAdd') and h['CapDrop'] == ['ALL']
             and h['SecurityOpt'] == ['no-new-privileges'] and h['PidsLimit'] == 64
             and not h.get('Binds') and not h.get('Tmpfs') and not h.get('Devices'), 'probe-original-security')
        need(len(row['Mounts']) == len(self.spec['mounts']) and all(m['Type'] == 'bind' for m in row['Mounts'])
             and sorted([m['Source'], m['Destination'], m['RW']] for m in row['Mounts'])
             == sorted(self.spec['mounts']), 'probe-original-mounts')
        need(s['Status'] == ('exited' if terminal else 'running' if running else 'created') and s['Running'] is running
             and type(s['Pid']) is int and (s['Pid']>0 if running else s['Pid']==0)
             and all(s.get(k) is False for k in ('Paused', 'Restarting', 'Dead', 'OOMKilled'))
             and (not terminal or type(s['ExitCode']) is int and s['ExitCode'] == 0), 'probe-original-state')
        parent=_PARENT_PROFILES.get(self);candidate=None
        if parent is None:
            if self.static is not None:need(encode({k:row[k]for k in ('Config','HostConfig','Mounts')})==self.static,'probe-original-terminal-static')
        else:
            owner,g,core,engine,helpers,contract=parent;full=encode(g['static'](row))
            if self.full_created is None:
                need(not running and not terminal,'probe-original-created-full-required');candidate=(full,None,None)
            elif running and self.full_running is None:
                need(helpers[0](json.loads(self.full_created),g['static'](row),self.cid),'probe-original-started-full-profile');candidate=(self.full_created,full,None)
            elif terminal:
                need(self.full_running is not None,'probe-original-running-full-required')
                if self.full_terminal is None:
                    need(helpers[1](json.loads(self.full_running),g['static'](row),self.cid),'probe-original-exited-full-profile');candidate=(self.full_created,self.full_running,full)
                else:need(full==self.full_terminal,'probe-original-terminal-full-exact')
            else:need(full==(self.full_running if running else self.full_created),'probe-original-full-profile-exact')
        self.original_close()
        if candidate is not None:
            self.full_created,self.full_running,self.full_terminal=candidate;_FULL_PROFILES[self]=(*candidate,self.command_builder)
            self.original_close()

    def inspect(self, terminal=False, running=False):
        need(self.cid is not None, 'probe-unborn')
        rows = json.loads(self.call(list(self.docker) + ['inspect', self.cid]).stdout)
        need(type(rows) is list and len(rows) == 1, 'probe-one-profile')
        self.profile(rows[0], terminal,running)
        return rows[0]

    def create(self):
        need(self.cid is None, 'probe-create-no-replay')
        # Mark uncertain creation before engine callback: never replay on loss.
        self.cid = 'creation-ack-pending'
        result = self.call(self.command())
        need(re.fullmatch(b'[a-f0-9]{64}\n?', result.stdout) is not None, 'probe-created-id-ack')
        self.cid = result.stdout.decode().rstrip('\n')
        self.cid_original = self.cid
        row = self.inspect()
        self.static = encode({k: row[k] for k in ('Config', 'HostConfig', 'Mounts')})
        self.original_close()
        return dict(id=self.cid, name=self.name, argv=self.command(), mounts=copy.deepcopy(self.spec['mounts']), profile=row)

    def prepare(self):
        need(self.cid is None, 'probe-prepare-before-birth')
        result = dict(name=self.name, argv=self.command(), mounts=copy.deepcopy(self.spec['mounts']))
        self.original_close()
        return result

    def local(self):
        self.original_close();seal=_PROCESS_SEALS.get(self)
        need(seal is not None and seal==(self.process,self.pid_original,self.process_start,self.streams,self.pipe_original,self.running_epoch),'probe-original-process-seal')
        need(type(self.process) is subprocess.Popen and self.process.pid==self.pid_original,'probe-original-real-process')
        need((self.process.stdin,self.process.stdout,self.process.stderr)==self.streams and tuple(fd5(x) for x in self.streams)==self.pipe_original,'probe-original-FIFOs')
        try:client=ticks(self.pid_original)
        except FileNotFoundError:client=None
        try:inner=ticks(self.running_epoch[0])
        except FileNotFoundError:inner=None
        if client!=self.process_start or inner!=self.running_epoch[2]:
            need(self.execution_sent and self.process.poll()==0 and inner!=self.running_epoch[2],'probe-original-inner-exit-unknown')
        need(_PROCESS_SEALS.get(self)==seal and seal==(self.process,self.pid_original,self.process_start,self.streams,self.pipe_original,self.running_epoch),'probe-final-original-process-seal')
    def line(self,seconds=30):
        self.local();deadline=time.monotonic()+seconds;raw=bytearray()
        while b'\n' not in raw:
            self.local();need(len(raw)<8*1024**2 and select.select([self.pipe_original[1][0]],[],[],max(0,deadline-time.monotonic()))[0],'probe-original-pipe-deadline')
            block=os.read(self.pipe_original[1][0],min(65536,8*1024**2-len(raw)));need(bool(block),'probe-original-pipe-EOF');raw.extend(block)
        line,_,tail=raw.partition(b'\n');need(not tail,'probe-original-single-frame');self.local();return bytes(line)
    def prepared_ack(self, proof=None):
        expected=dict(kind='original-nfs-probe-gate',state='prepared',token=self.spec['input_sha256'],source_sha256=self.spec['probe_sha256'],native_grant=False,publication_authority=False)
        need(encode(self.namespace_original)==self.namespace_tape,'probe-namespace-original-tape')
        if self.namespace_original is not None:
            keys={'version','kind','host','rows','host_root','child_root','root9'}
            if 'binding' in self.namespace_original:keys|={'binding','retention9'}
            need(type(proof) is dict and set(proof)==keys and type(proof['version']) is int,'probe-actual-namespace-required')
            n=self.namespace_original
            actual=mount_namespace(n['host'],proof['rows'],n['host_root'],n['child_root'],n['root9'],proof['root9'],binding=n.get('binding'),retention9=proof.get('retention9'))
            need(proof==actual,'probe-original-namespace-proof');expected['namespace']=actual
        else:need(proof is None,'probe-unrequested-namespace')
        return expected

    def start_prepare(self):
        need(self.gated and self.cid is not None and not self.started,'probe-original-prestart')
        self.inspect();self.started=True
        process=self.launcher(self.cid);need(type(process) is subprocess.Popen and process.poll() is None,'probe-original-launcher-Popen')
        self.process=process;self.streams=(process.stdin,process.stdout,process.stderr);need(all(x is not None for x in self.streams),'probe-original-stdio')
        self.pipe_original=tuple(fd5(x) for x in self.streams);need(all(stat.S_ISFIFO(x[1][2]) for x in self.pipe_original),'probe-original-FIFOs')
        self.pid_original=process.pid;self.process_start=ticks(process.pid)
        row=self.inspect(running=True);self.running_epoch=(row['State']['Pid'],row['State']['StartedAt'],ticks(row['State']['Pid']))
        _PROCESS_SEALS[self]=(self.process,self.pid_original,self.process_start,self.streams,self.pipe_original,self.running_epoch)
        ack=json.loads(self.line(30));expected=self.prepared_ack(ack.get('namespace') if type(ack) is dict else None)
        need(ack==expected,'probe-original-prepared-ACK')
        self.namespace_proof=copy.deepcopy(ack.get('namespace'))
        self.local();_PREPARED_ACKS[self]=(_PROCESS_SEALS[self],encode(ack));return dict(prepared=True,id=self.cid,epoch=list(self.running_epoch),native_grant=False,publication_authority=False)
    def execute_local(self):
        need(self.gated and self.started and not self.execution_sent,'probe-original-execute-no-replay');self.local();self.execution_sent=True
        raw=encode(dict(token=self.spec['input_sha256'],operation='execute'))+b'\n';need(os.write(self.pipe_original[0][0],raw)==len(raw),'probe-original-execute-unknown');self.local()
        self.kernel_output=self.line(120);need(self.process.wait(timeout=30)==0,'probe-original-local-exit');self.local()
        try:inner=ticks(self.running_epoch[0])
        except FileNotFoundError:inner=None
        need(inner!=self.running_epoch[2],'probe-original-local-inner-present')
        return dict(stdout=base64.b64encode(self.kernel_output+b'\n').decode(),stderr='',profile=None,kernel_finished=True,local_exit_verified=True,terminal_profile_verified=False)
    def finish_after_release(self):
        need(self.gated and self.execution_sent and self.kernel_output is not None and not self.terminal,'probe-original-finish-no-replay')
        # Remote terminal inspect is legal only after Parent hard guard cleared.
        need(self.process.wait(timeout=30)==0,'probe-original-zero-process-exit')
        terminal=self.inspect(terminal=True);need(terminal['State']['StartedAt']==self.running_epoch[1],'probe-original-terminal-epoch')
        self.terminal=True;self.original_close()
        return dict(stdout=self.kernel_output+b'\n',stderr=b'',profile=terminal)
    def start(self):
        need(not self.gated and self.cid is not None and self.static is not None and not self.started, 'probe-start-no-replay')
        self.inspect()
        self.started = True
        result = self.call(list(self.docker) + ['start', '-a', self.cid])
        terminal = self.inspect(terminal=True)
        self.terminal = True
        self.original_close()
        return dict(stdout=result.stdout, stderr=result.stderr, profile=terminal)


class HostProbe:
    """Requires original Parent mapping admission; unimplemented APIs refuse."""
    def __init__(self, dialogue, child_input_ref):
        from comic_nfs_host_engine import EngineReplies
        need(type(dialogue) is EngineReplies, 'probe-original-dialogue-type')
        dialogue.close()
        self.dialogue = dialogue
        self.owner = dialogue.owner
        mapping = self.owner.mapping
        need(callable(getattr(mapping, 'admit_nfs_probe', None))
             and callable(getattr(mapping, 'check_nfs_probe', None)), 'probe-parent-mapping-unbound')
        self.admitted = mapping.admit_nfs_probe(child_input_ref)
        spec = mapping.check_nfs_probe(self.admitted)
        need(spec.get('image') == self.owner.plan['selected_image'], 'probe-original-selected-image')
        need(callable(getattr(self.owner,'register_nfs_probe_birth',None)) and callable(getattr(self.owner.engine,'probe_interactive',None)),'probe-owning-gated-launcher-unbound')
        self.spec_tape = encode(spec)
        # Read the already-admitted original child input; never adopt current metadata.
        ref=self.admitted;fd=os.open(ref['path'],os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            original=tuple(ref['signature9']);need(len(original)==9 and original[2]<=1024**2,'probe-original-namespace-input-bound')
            def stamp(z):return (z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink)
            need(stamp(os.fstat(fd))==original,'probe-original-namespace-input-FD')
            raw=bytearray()
            while len(raw)<original[2]:
                block=os.read(fd,min(65536,original[2]-len(raw)));need(bool(block),'probe-original-namespace-input-short');raw.extend(block)
            need(hashlib.sha256(raw).hexdigest()==ref['sha256'] and stamp(os.fstat(fd))==original and stamp(os.lstat(ref['path']))==original,'probe-original-namespace-input-hash9')
            plan=json.loads(raw)
        finally:os.close(fd)
        self.close()
        need(spec['mounts'][0][0]==spec['mounts'][0][1],'probe-current-canonical-fixture-bind')
        namespace=dict(host=plan['mount'],host_root=plan['root'],child_root=plan['root'],root9=plan['root9'])
        if 'binding' in spec:
            need(spec['binding']==mapping.nfs_probe_binding(plan['root']),'probe-original-retention-binding')
            namespace['binding']=copy.deepcopy(spec['binding'])
        else:need(plan['root']==spec['mounts'][0][1],'probe-current-canonical-fixture-bind')
        self.process = ProbeProcess(spec, dialogue.g['DOCKER'], self.owner.engine.canary, self.close,gated=True,launcher=self.owner.engine.probe_interactive,namespace=namespace,owner=self.owner)
        self.close()

    def birth_descriptor(self,created_profile):
        self.close();p=self.process;need(type(p) is ProbeProcess and p.cid==p.cid_original and p.static is not None and not p.started,'probe-original-prestart-descriptor')
        p.profile(created_profile)
        return dict(cid=p.cid_original,name=p.name,spec=copy.deepcopy(p.spec),static=p.static.hex(),profile=copy.deepcopy(created_profile))
    def prepared_descriptor(self):
        self.close();p=self.process;p.local()
        ack=encode(p.prepared_ack(p.namespace_proof))
        need(p.gated and p.started and not p.execution_sent and p.process.poll() is None and _PREPARED_ACKS.get(p)==(_PROCESS_SEALS.get(p),ack),'probe-original-prepared-descriptor')
        return dict(cid=p.cid_original,name=p.name,spec=copy.deepcopy(p.spec),static=p.static.hex(),process_pid=p.pid_original,process_start_ticks=p.process_start,inner_epoch=list(p.running_epoch),pipes=[[fd,list(v)] for fd,v in p.pipe_original],native_grant=False,publication_authority=False)
    def close(self):
        self.dialogue.close()
        need(encode(self.owner.mapping.check_nfs_probe(self.admitted)) == self.spec_tape, 'probe-parent-original-mapping')


class HostProbeReplies:
    """Single original dialogue, single birth, single start; never child argv."""
    def __init__(self, dialogue):
        from comic_nfs_host_engine import EngineReplies
        need(type(dialogue) is EngineReplies, 'probe-original-dialogue-type')
        dialogue.close()
        self.dialogue = dialogue
        self.probe = None

    def accept(self, frame):
        d = self.dialogue
        d.close()
        need(type(frame) is dict and set(frame) == {'type', 'nonce', 'sequence', 'payload'}
             and frame['type'] == 'nfs-probe' and frame['nonce'] == d.nonce
             and type(frame['sequence']) is int and frame['sequence'] == d.sequence + 1
             and len(encode(frame)) <= 16 * 1024**2,
             'probe-original-dialogue-frame')
        payload = frame['payload']
        need(type(payload) is dict and set(payload) == {'operation', 'input'}
             and payload['operation'] in ('initialize','create','start_prepare','execute_local','finish'), 'probe-finite-frame')
        if payload['operation'] == 'initialize':
            need(self.probe is None and type(payload['input']) is dict
                 and set(payload['input']) == {'path', 'sha256', 'signature9'}, 'probe-original-input')
            # Retain the boundary before any operation; lost response cannot
            # cause another birth on this same dialogue.
            self.probe = HostProbe(d, payload['input'])
            result = self.probe.process.prepare()
        elif payload['operation'] == 'create':
            need(self.probe is not None and payload['input'] is None, 'probe-own-create')
            result = self.probe.process.create()
            self.probe.owner.register_nfs_probe_birth(self.probe,result['profile'])
        elif payload['operation']=='start_prepare':
            need(self.probe is not None and payload['input'] is None,'probe-own-prestart');result=self.probe.process.start_prepare()
        elif payload['operation']=='execute_local':
            need(self.probe is not None and payload['input'] is None,'probe-own-local-execute');result=self.probe.process.execute_local()
        else:
            need(self.probe is not None and payload['input'] is None, 'probe-own-start')
            result = self.probe.process.finish_after_release()
            result = dict(stdout=base64.b64encode(result['stdout']).decode(),
                          stderr=base64.b64encode(result['stderr']).decode(), profile=result['profile'])
        self.probe.close()
        response = encode(dict(type='nfs-host', nonce=d.nonce, sequence=frame['sequence'], payload=result)) + b'\n'
        d.close()
        d.sequence = frame['sequence']
        return response
