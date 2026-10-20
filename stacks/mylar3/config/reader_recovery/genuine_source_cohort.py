"""Opt-in causal source-fixture emitter; never NFS or owning factory acceptance.

Root supplies an ORIGINAL already-running isolated source-fixture container and
an exact read-only /checks bundle. This module never creates/starts/stops it.
Readiness is emitted only by the same invocation that executes the owning
installed-source verifier and strict recovery runner, then closes originals.
Host tests double transport explicitly; they establish no selected-image proof.
"""
import ast
import copy
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import time

import genuine_plan13_producer as producer

p = producer.p
need = p.need
HERE = Path(__file__).absolute().parent
DOCKER = ['/usr/bin/docker', '--host', 'unix:///run/docker.sock']
ROLES = ('probe', 'hardlink_kernel', 'scope_projection', 'lifecycle', 'readiness',
         'readiness_input', 'parity', 'native_map', 'selected_sdk', 'writer', 'tests',
         'effective_helper', 'effective_parent', 'core_parent', 'core_tests', 'writer_fixture')
RIGHTS = ('actual_nfs_verified', 'native_grant', 'publication_authority', 'library_support_verified')
OWNING_SOURCES = {'probe': 'reader_recovery/comic_negative_nfs_hardlink_child.py',
    'hardlink_kernel': 'reader_recovery/comic_negative_nfs_hardlink_probe.py',
    'scope_projection': 'publication_native_configured_scope.py',
    'lifecycle': 'reader_recovery/comic_negative_nfs_active_lifecycle.py',
    'readiness': 'reader_recovery/comic_native_process_probe.py', 'writer': 'media_writer.py',
    'tests': 'reader_recovery/test_nfs_current_source.py'}
VERIFY_LINE = b'Installed prospective reader source/origin/type proof passed; owning admission remains held\n'
MAX = 16 * 1024**2
# LinuxServer's declared /config is masked, never converted to an anonymous volume.
CONFIG_TMPFS = 'rw,nosuid,nodev,noexec,size=16777216,mode=0700,uid=1000,gid=1000'
TMPFS = {'/tmp': 'rw,nosuid,nodev,size=536870912,mode=1777', '/config': CONFIG_TMPFS}
IDLE_ENTRYPOINT = ['/bin/sleep']
IDLE_COMMAND = ['infinity']
RUNTIME_PROGRAM = """import hashlib,json,os,pathlib,stat,sys
v=json.load(sys.stdin);assert set(v)=={'nonce','modules','executable_sha256'}
assert os.geteuid()==os.getegid()==1000 and sys.flags.isolated and sys.dont_write_bytecode
assert sys.version_info[:2]==(3,10)
def digest(path):
 z=path.lstat();assert stat.S_ISREG(z.st_mode) and z.st_nlink==1 and z.st_size<=32*1024**2
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  def sig(x):return(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_mode,x.st_uid,x.st_gid,x.st_nlink)
  before=sig(z);assert sig(os.fstat(fd))==before;h=hashlib.sha256()
  while True:
   b=os.read(fd,65536)
   if not b:break
   h.update(b)
  assert sig(os.fstat(fd))==before==sig(path.lstat());return h.hexdigest()
 finally:os.close(fd)
exe=digest(pathlib.Path(sys.executable).resolve(strict=True));assert exe==v['executable_sha256']
actual={}
for name,pin in v['modules'].items():
 assert type(name)is str and __import__('re').fullmatch('[A-Za-z_][A-Za-z0-9_]*[.]py',name)
 actual[name]=digest(pathlib.Path('/app/mylar3/mylar')/name);assert actual[name]==pin
print(json.dumps({'nonce':v['nonce'],'executable_sha256':exe,'modules':actual},sort_keys=True))
"""


def sha(raw):return hashlib.sha256(raw).hexdigest()


def remember(originals, nodes):
    for name, value in nodes.items():
        need(name not in originals.nodes or originals.nodes[name] == value, 'source-original-ancestor-conflict')
        originals.nodes[name] = value


def fixed(error):
    return error.args[0] if type(error) is p.Held and len(error.args) == 1 and type(error.args[0]) is str and re.fullmatch('[a-z0-9-]{1,100}', error.args[0]) else None


def suites(raw):
    """Read the original literal inventory; never import a substituted runner."""
    tree = ast.parse(raw, feature_version=(3, 10)); result = ()
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1 or getattr(node.targets[0], 'id', None) != 'SUITES':continue
        value = node.value
        if isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add) and isinstance(value.left, ast.Name) and value.left.id == 'SUITES':
            result += ast.literal_eval(value.right)
        else:
            need(not result, 'source-original-suite-assignment'); result = ast.literal_eval(value)
    need(type(result) is tuple and 1 <= len(result) <= 128
         and len({row[0] for row in result}) == len(result)
         and all(type(row) is tuple and len(row) == 2 and re.fullmatch('test_[a-z0-9_]+[.]py', row[0])
                 and type(row[1]) is int and 0 < row[1] <= 1000 for row in result), 'source-original-suite-inventory')
    return result


def checked_result(raw, inventory):
    value = p.decode(raw)
    need(type(value) is dict and set(value) == {'kind', 'tests', 'suites', 'original_source_unchanged',
         'installed_factory_verified', 'publication_acceptance', 'reader_resume_authority'}
         and value['kind'] == 'private-build-only-reader-recovery-controls'
         and type(value['tests']) is int and value['tests'] == sum(n for _, n in inventory)
         and value['original_source_unchanged'] is True
         and all(value[k] is False for k in ('installed_factory_verified', 'publication_acceptance', 'reader_resume_authority')),
         'source-owning-result')
    need(type(value['suites']) is list and len(value['suites']) == len(inventory), 'source-complete-suites')
    for row, (name, count) in zip(value['suites'], inventory):
        need(type(row) is dict and set(row) == {'suite', 'count', 'skips', 'stdout_sha256', 'stderr_sha256'}
             and row['suite'] == name and type(row['count']) is int and row['count'] == count
             and type(row['skips']) is int and row['skips'] == 0
             and p.digest(row['stdout_sha256']) and p.digest(row['stderr_sha256']), 'source-exact-suite-result')
    return value


def payload(template, request_ref, closing_ref, result, stdout_ref, stderr_ref):
    """Pure schema projection only; execution authority belongs to run().

    Calling this function with fixture inputs establishes no runtime evidence.
    """
    receipt = dict(kind='owned-nfs-current-source-fixture-readiness', images=template['images'],
        parent_sha256=template['parent']['sha256'], source_pins={k: v['sha256'] for k, v in template['sources'].items()},
        exit_code=0, zero_skips=True, count=result['tests'], stdout=stdout_ref, stderr=stderr_ref,
        closing=closing_ref, causal_request=request_ref, **{k: False for k in RIGHTS})
    return receipt


class Emitter:
    """Actual entry uses fixed subprocess calls; optional transport is test-only."""
    def __init__(self, request_ref, output, *, transport=None):
        self.originals = producer.Originals(); self.request = self.originals.json(request_ref)
        q = self.request
        need(type(q) is dict and set(q) == {'version', 'kind', 'nonce', 'observed', 'profile', 'image',
             'executable_sha256', 'bundle', 'bundle_files', 'cohort', 'originals', 'output'}
             and type(q['version']) is int and q['version'] == 1 and q['kind'] == 'original-selected-source-fixture-run'
             and p.digest(q['nonce']) and type(q['observed']) is int and 0 <= time.time() - q['observed'] <= 120,
             'source-causal-request')
        self.request_ref = copy.deepcopy(request_ref)
        self.profile = self.originals.json(q['profile']); self.image = self.originals.json(q['image'])
        self.bundle = p.absolute(q['bundle']); bundle_stat = os.lstat(self.bundle)
        need(self.bundle.name == 'config' and stat.S_ISDIR(bundle_stat.st_mode) and stat.S_IMODE(bundle_stat.st_mode) == 0o700
             and bundle_stat.st_uid == bundle_stat.st_gid == 1000, 'source-config-bundle')
        self.cohort = copy.deepcopy(q['cohort'])
        need(type(self.cohort) is dict and set(self.cohort) == {'version', 'kind', 'images', 'sources', 'writer_root',
             'writer_sha256', 'native_map_count', 'selected_module_count', 'parent', 'effective_jar_sha256', 'effective_commit'}
             and type(self.cohort['version']) is int and self.cohort['version'] == 1
             and self.cohort['kind'] == 'approved-disposable-nfs-current-source-cohort'
             and set(self.cohort['sources']) == set(ROLES)
             and set(self.cohort['images']) == {'native', 'selected', 'reader', 'worker'}
             and all(re.fullmatch('sha256:[a-f0-9]{64}', v) for v in self.cohort['images'].values())
             and self.cohort['images']['native'] == self.cohort['images']['selected']
             and p.digest(q['executable_sha256']) and p.digest(self.cohort['effective_jar_sha256'])
             and re.fullmatch('[a-f0-9]{40}', self.cohort['effective_commit']), 'source-cohort-template')
        self._profile(self.profile)
        need(type(self.image) is list and len(self.image) == 1 and self.image[0]['Id'] == self.profile['Image']
             and self.image[0]['Os'] == 'linux' and self.image[0]['Architecture'] == 'amd64'
             and self.image[0]['Config'].get('Volumes') == {'/config': {}}, 'source-original-image')
        supplied = q['originals']; need(type(supplied) is list and 1 <= len(supplied) <= 64, 'source-finite-originals')
        refs = {r['path']: r for r in supplied}; need(len(refs) == len(supplied), 'source-distinct-originals')
        used = set()
        def original(ref):
            need(type(ref) is dict and set(ref) == {'path', 'sha256'} and ref['path'] in refs
                 and refs[ref['path']]['sha256'] == ref['sha256'], 'source-required-original')
            used.add(ref['path']); return self.originals.read(refs[ref['path']], private=False)
        self.module_map = p.decode(original(self.cohort['sources']['native_map']))
        selected = p.decode(original(self.cohort['sources']['selected_sdk']))
        need(type(self.module_map) is dict and len(self.module_map) == self.cohort['native_map_count'] > 0
             and all(re.fullmatch('[A-Za-z_][A-Za-z0-9_]*[.]py', n) and p.digest(v) for n, v in self.module_map.items())
             and selected.get('parent_sha256') is None and len(selected.get('modules', {})) == self.cohort['selected_module_count'] == 25
             and selected.get('runtime_acceptance') is False and selected.get('publication_acceptance') is False, 'source-distinct-original-maps')
        for role in ROLES:original(self.cohort['sources'][role])
        for role, filename in OWNING_SOURCES.items():
            need(original(self.cohort['sources'][role]) == (HERE.parent / filename).read_bytes(), 'source-owning-role-bytes')
        need(original(self.cohort['parent']) == (HERE / 'comic_negative_nfs_active_parent.py').read_bytes(), 'source-owning-active-parent')
        need(all(self.module_map.get(row['filename']) == row['sha256'] for row in selected['modules'].values()), 'source-selected-native-module-join')
        original(self.cohort['parent']); need(used == set(refs), 'source-no-unused-originals')
        need(self.cohort['writer_sha256'] == self.cohort['sources']['writer']['sha256'], 'source-original-writer')
        writer = p.absolute(self.cohort['writer_root']); z = os.lstat(writer)
        need(stat.S_ISDIR(z.st_mode) and stat.S_IMODE(z.st_mode) == 0o700 and z.st_uid == z.st_gid == 1000, 'source-existing-writer')
        remember(self.originals, p.parents(writer)); remember(self.originals, {str(writer): p.five(z)})
        self._bundle(q['bundle_files'])
        request = p.decode(original(self.cohort['sources']['readiness_input']))
        need(type(request) is dict and set(request) == {'version', 'nonce', 'source_sha256', 'seconds', 'module_pins', 'scope_source'}
             and type(request['version']) is int and request['version'] == 1 and request['nonce'] == q['nonce']
             and type(request['seconds']) is int and 1 <= request['seconds'] <= 120
             and request['source_sha256'] == self.cohort['sources']['readiness']['sha256']
             and request['module_pins'] == {'/app/mylar3/mylar/' + n: self.module_map[n] for n in ('worker_health.py', 'native_writers.py')}
             and request['scope_source'] == original(self.cohort['sources']['scope_projection']).decode(), 'source-original-readiness-nonce')
        self.tape = p.encode(q); self.state_tape = p.encode([self.profile, self.image, self.cohort, self.module_map, self.inventory]); self.entered = False; self.transport = transport
        self.output = p.absolute(str(output)); need(q['output'] == str(self.output), 'source-request-output-binding'); need(not os.path.lexists(self.output), 'source-output-no-adoption')
        z = os.lstat(self.output.parent); need(stat.S_ISDIR(z.st_mode) and stat.S_IMODE(z.st_mode) == 0o700 and z.st_uid == os.geteuid(), 'source-private-output-parent')
        remember(self.originals, p.parents(self.output)); self.parent5 = p.five(z); self.parent_fd = None; self.fd = None; self.files = {}; self.names = set()
        self.end = time.monotonic() + len(self.inventory) * 120 + 240
        self.originals.close(); self.close()

    def _bundle(self, rows):
        need(type(rows) is dict and 1 <= len(rows) <= 1024, 'source-finite-bundle')
        raw = {}; total = 0; actual = set()
        for folder, dirs, files in os.walk(self.bundle, followlinks=False):
            node = Path(folder); z = os.lstat(node)
            need(stat.S_ISDIR(z.st_mode) and z.st_uid == z.st_gid == 1000 and stat.S_IMODE(z.st_mode) == 0o700
                 and not any((node / n).is_symlink() for n in dirs + files), 'source-private-bundle-namespace')
            remember(self.originals, {str(node): p.five(z)}); self.originals.namespaces[str(node)] = set(dirs + files)
            actual.update(str((node / n).relative_to(self.bundle)) for n in files)
            need(len(actual) <= 1024 and len(self.originals.namespaces) <= 1024, 'source-bundle-namespace-bound')
        need(actual == set(rows), 'source-bundle-no-extra-files')
        for name, ref in rows.items():
            rel = PurePosixPath(name)
            need(type(name) is str and str(rel) == name and not rel.is_absolute() and '..' not in rel.parts
                 and ref['path'] == str(self.bundle / name), 'source-bundle-original-path')
            need(ref['signature9'][6:8] == [1000, 1000] and stat.S_IMODE(ref['signature9'][5]) in (0o600, 0o644), 'source-child-readable-bundle')
            raw[name] = self.originals.read(ref, private=False); total += len(raw[name]); need(total <= 32 * 1024**2, 'source-bundle-byte-bound')
        map_name = 'standalone_control_sources.json'; need(map_name in raw, 'source-owning-copy-map')
        source_rows = p.decode(raw[map_name]); expected = {r['path']: r['sha256'] for r in source_rows}
        manifest_name = 'reader_recovery/source-manifest.json'; need(manifest_name in raw, 'source-recovery-manifest-required')
        manifest = p.decode(raw[manifest_name]); recovery = {'reader_recovery/' + n: r['sha256'] for n, r in manifest['files'].items()}
        need(set(raw) == set(expected) | set(recovery) | {map_name, manifest_name, 'publication_reader_cohort.json'}
             and all(sha(raw[row['path']]) == row['sha256'] for row in source_rows)
             and all(sha(raw[name]) == pin for name, pin in recovery.items()), 'source-exact-bundle-copy-map')
        for name in ('run_reader_recovery_controls.py', 'verify_publication_reader_cohort.py', 'publication_reader_cohort.json', 'standalone_control_sources.json', 'reader_recovery/source-manifest.json'):
            need(name in raw and raw[name] == (HERE.parent / name).read_bytes(), 'source-owning-runner-bytes')
        need(p.decode(raw['publication_reader_cohort.json']) == p.decode(self.originals.read(
            next(r for r in self.request['originals'] if r['path'] == self.cohort['sources']['selected_sdk']['path']), private=False)), 'source-base-cohort-original')
        base = p.decode(raw['reader_recovery/configured_reader_parent_base_sources.json'])
        # The historical installer base is a name census, not the current full
        # native-image hash map. Actual hashes are joined to all installed files
        # by both runtime probes; the distinct 25-module SDK join remains exact.
        need(set(self.module_map) == set(base['base_installed_sources']), 'source-complete-original-native-map')
        manifest = p.decode(raw['reader_recovery/source-manifest.json'])
        need(all('reader_recovery/' + n in raw and sha(raw['reader_recovery/' + n]) == r['sha256'] for n, r in manifest['files'].items()), 'source-recovery-manifest')
        self.inventory = suites(raw['run_reader_recovery_controls.py'])

    def _profile(self, row):
        q = self.request; host = row['HostConfig']; cfg = row['Config']; state = row['State']
        need(p.digest(row['Id']) and row['Image'] == self.cohort['images']['selected']
             and row['Name'] == '/source-cohort-' + q['nonce'][:16]
             and cfg['User'] == '1000:1000'
             and cfg.get('Entrypoint') == IDLE_ENTRYPOINT and cfg.get('Cmd') == IDLE_COMMAND
             and cfg.get('Healthcheck') == {'Test': ['NONE']}
             and row.get('Path') == '/bin/sleep' and row.get('Args') == IDLE_COMMAND and cfg.get('Labels', {}).get('com.homelab.archive.source-fixture') == q['nonce']
             and host.get('ReadonlyRootfs') is True and host.get('NetworkMode') == 'none'
             and not host.get('Privileged') and not host.get('Devices') and not host.get('DeviceRequests') and not host.get('CapAdd')
             and host.get('CapDrop') == ['ALL'] and host.get('SecurityOpt') == ['no-new-privileges']
             and not host.get('PortBindings') and host.get('PidMode', '') == '' and host.get('IpcMode', '') in ('', 'private')
             and not host.get('AutoRemove') and host.get('RestartPolicy', {}).get('Name') in ('', 'no')
             and host.get('Tmpfs') == TMPFS
             and set(row.get('NetworkSettings', {}).get('Networks', {})) == {'none'}
             and not row['NetworkSettings']['Networks']['none'].get('IPAddress') and not row['NetworkSettings']['Networks']['none'].get('GlobalIPv6Address')
             and all(not v for v in row['NetworkSettings'].get('Ports', {}).values())
             and len(row['Mounts']) == 1 and row['Mounts'][0]['Type'] == 'bind'
             and row['Mounts'][0]['Source'] == str(self.bundle) and row['Mounts'][0]['Destination'] == '/checks' and row['Mounts'][0]['RW'] is False
             and state['Status'] == 'running' and state['Running'] is True and type(state['Pid']) is int and state['Pid'] > 0
             and all(not state.get(k) for k in ('Paused', 'Restarting', 'Dead', 'OOMKilled')), 'source-original-isolated-profile')

    def close(self):
        # Initial reads bind bytes/full9; callbacks cannot refresh those originals.
        p.final({name: tuple(ref['signature9']) for name, ref in self.originals.refs.items()}, self.originals.nodes, ())
        for path, names in self.originals.namespaces.items():need(set(os.listdir(path)) == names, 'source-original-bundle-namespace')
        need(p.encode(self.request) == self.tape
             and p.encode([self.profile, self.image, self.cohort, self.module_map, self.inventory]) == self.state_tape, 'source-original-request-changed')
        self.output_close()

    def output_close(self):
        # Raw replies must survive a separate SOURCE closure refusal.
        p.final({}, {str(n): v for n, v in self.originals.nodes.items() if str(n) in {str(x) for x in self.output.parents}}, ())
        if self.parent_fd is not None:need(p.five(os.fstat(self.parent_fd)) == self.parent5, 'source-output-parent-FD')
        if self.fd is not None:
            need(p.five(os.fstat(self.fd)) == self.node == p.five(os.lstat(self.output))
                 and set(os.listdir(self.output)) == self.names, 'source-output-directory')
            p.final(self.files, {}, ())

    def write(self, name, raw):
        need(name not in self.names and re.fullmatch('[a-z0-9-]+[.](json|stdout|stderr)', name) and type(raw) is bytes and len(raw) <= MAX, 'source-output-file')
        self.output_close(); fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=self.fd)
        try:
            born = p.nine(os.fstat(fd)); offset = 0
            need(stat.S_ISREG(born[5]) and stat.S_IMODE(born[5]) == 0o600 and born[6:] == [os.geteuid(), os.getegid(), 1], 'source-output-birth')
            while offset < len(raw):
                count = os.write(fd, raw[offset:]); need(count > 0, 'source-output-short-write'); offset += count
            os.fsync(fd); stamp = p.nine(os.fstat(fd)); os.lseek(fd, 0, 0)
            need(stamp[:2] == born[:2] and stamp[2] == len(raw) and stamp[5:] == born[5:]
                 and os.read(fd, len(raw) + 1) == raw and p.nine(os.fstat(fd)) == stamp, 'source-output-readback')
        finally:os.close(fd)
        self.names.add(name); self.files[str(self.output / name)] = stamp; os.fsync(self.fd); self.output_close()
        return dict(path=str(self.output / name), sha256=sha(raw))

    def call(self, label, args, data=None):
        (self.output_close if label == 'after' else self.close)(); remaining = self.end - time.monotonic(); need(remaining > 0, 'source-run-deadline')
        timeout = min(remaining, len(self.inventory) * 120 + 60 if label == 'controls' else 30)
        argv = DOCKER + args
        self.write(label + '-intent.json', p.encode(dict(nonce=self.request['nonce'], argv=argv, stdin_sha256=None if data is None else sha(data), automatic_replay=False)))
        try:
            result = (self.transport or subprocess.run)(argv, input=data, capture_output=True, timeout=timeout,
                check=False, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        except subprocess.TimeoutExpired as error:
            for suffix, raw in (('stdout', error.stdout), ('stderr', error.stderr)):
                if raw is not None:self.write(label + '.' + suffix, raw[:MAX])
            raise
        need(type(result.returncode) is int and type(result.stdout) is bytes and type(result.stderr) is bytes
             and len(result.stdout) <= MAX and len(result.stderr) <= MAX, 'source-command-output-bound')
        self.write(label + '.stdout', result.stdout); self.write(label + '.stderr', result.stderr)
        self.write(label + '-exit.json', p.encode(dict(nonce=self.request['nonce'], returncode=result.returncode)))
        need(result.returncode == 0, 'source-command-refused'); return result.stdout

    def probe(self, label):
        data = dict(nonce=self.request['nonce'], modules=self.module_map, executable_sha256=self.request['executable_sha256'])
        raw = self.call(label, ['exec', '--interactive', '--user', '1000:1000', self.profile['Id'], '/lsiopy/bin/python3', '-I', '-B', '-c', RUNTIME_PROGRAM], p.encode(data))
        need(p.decode(raw) == data, 'source-original-runtime-reply')

    def inspect(self, label):
        rows = p.decode(self.call(label, ['inspect', self.profile['Id']]))
        need(type(rows) is list and len(rows) == 1 and p.static(rows[0]) == p.static(self.profile)
             and p.lifecycle_state(rows[0]) == p.lifecycle_state(self.profile), 'source-original-runtime-closure')
        self._profile(rows[0])

    def execute(self):
        need(not self.entered, 'source-no-replay'); self.entered = True
        need(0 <= time.time() - self.request['observed'] <= 120, 'source-request-expired')
        self.close(); self.parent_fd = os.open(self.output.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            need(p.five(os.fstat(self.parent_fd)) == self.parent5, 'source-original-output-parent')
            os.mkdir(self.output.name, mode=0o700, dir_fd=self.parent_fd)
            self.fd = os.open(self.output.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self.parent_fd)
        except BaseException:
            os.close(self.parent_fd); self.parent_fd = None; raise
        self.node = p.five(os.fstat(self.fd)); primary = None; secondary = None; result = None; raw = None
        try:
            try:
                self.inspect('before'); self.probe('runtime-before')
                prefix = ['exec', '--user', '1000:1000', self.profile['Id'], '/lsiopy/bin/python3', '-I', '-B']
                need(self.call('installed-before', prefix + ['/checks/verify_publication_reader_cohort.py']) == VERIFY_LINE, 'source-installed-verifier-result')
                raw = self.call('controls', prefix + ['/checks/run_reader_recovery_controls.py']); result = checked_result(raw, self.inventory)
                need(self.call('installed-after', prefix + ['/checks/verify_publication_reader_cohort.py']) == VERIFY_LINE, 'source-installed-verifier-result')
                self.probe('runtime-after')
            except BaseException as error:primary = error
            # Independent final inspect is attempted even after partial/failing exec.
            secondary = None
            try:self.inspect('after')
            except BaseException as error:secondary = error
            try:self.originals.close(); self.close()
            except BaseException as error:
                if secondary is None:secondary = error
            if primary is not None:raise primary
            if secondary is not None:raise secondary
            # An explicit test double cannot emit operational readiness.
            need(self.transport is None, 'source-original-transport-required')
            closing = self.write('closing.json', p.encode(dict(nonce=self.request['nonce'], request=self.request_ref,
                original_runtime_closed=True, original_sources_closed=True, fixture_result_sha256=sha(raw), **{k: False for k in RIGHTS})))
            receipt = payload(self.cohort, self.request_ref, closing, result,
                dict(path=str(self.output/'controls.stdout'), sha256=sha(raw)),
                dict(path=str(self.output/'controls.stderr'), sha256=sha((self.output/'controls.stderr').read_bytes())))
            receipt_ref = self.write('readiness.json', p.encode(receipt))
            cohort = dict(self.cohort, receipt=receipt_ref, logs={k: receipt[k] for k in ('stdout','stderr')})
            ref = self.write('cohort.json', p.encode(cohort)); self.close(); return ref
        except BaseException as error:
            primary = error
            try:self.write('failure.json', p.encode(dict(exception_type=type(error).__name__, fixed_code=fixed(error), secondary_fixed_code=fixed(secondary) if secondary is not None else None, readiness_returned=False, automatic_replay=False)))
            except BaseException:pass
            raise
        finally:
            try:self.close()
            except BaseException:
                if primary is None:raise
            finally:
                os.close(self.fd); os.close(self.parent_fd); self.fd = self.parent_fd = None


def run(request_ref, output, *, activate=False):
    need(activate is True and os.geteuid() == 0, 'source-explicit-root-activation')
    return Emitter(request_ref, output).execute()
