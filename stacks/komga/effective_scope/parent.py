from collections import Counter
"""Disabled original-process-bound Komga environment observation; no authority grant."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import selectors
import secrets
import stat
import subprocess
import sys
import time

ACTIVATE = False
PLAN = None
SUPPLIER_PINS = None
HERE = Path(__file__).parent
IMAGE = None
JAR = 'f76aff7d31f2735ed902e3a004540e869568be42dc099a5560d72fd3d8f2c0fe'
COMMIT = '2ab7a5a61a8b8bb12a6edd576fed380b4b613c99'
CLASSES = ('KomgaEffectiveScope.class', 'KomgaEffectiveScope$Held.class', 'KomgaClasspathMetadata.class')
RIGHTS = dict(backup_verified=False, publication_acceptance=False, mutation_authority=False)
CONFIG_NAME = re.compile(r'application(?:-[A-Za-z0-9_-]+)?\.(?:yml|yaml|properties|xml)\Z')
AGENTS = {'JAVA_TOOL_OPTIONS', 'JDK_JAVA_OPTIONS', '_JAVA_OPTIONS'}


def need(value, code):
    if not value:
        raise ValueError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def nine(z):
    return [z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
            z.st_mode, z.st_uid, z.st_gid, z.st_nlink]


def five(z):
    return [z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid]


def bounded(path, maximum, *, owner=None, mode=None):
    path = Path(path)
    z = path.lstat()
    need(stat.S_ISREG(z.st_mode) and z.st_nlink == 1 and z.st_size <= maximum,
         'original-file')
    need(owner is None or (z.st_uid, z.st_gid) == owner, 'original-owner')
    need(mode is None or stat.S_IMODE(z.st_mode) == mode, 'original-mode')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        need(nine(os.fstat(fd)) == nine(z), 'original-open')
        raw = os.read(fd, maximum + 1)
        need(len(raw) == z.st_size and nine(os.fstat(fd)) == nine(path.lstat()) == nine(z),
             'original-read-close')
        return raw, nine(z)
    finally:
        os.close(fd)


class Suppliers:
    def __init__(self, pins):
        need(type(pins) is dict and set(pins) == {
            'owned.py', 'KomgaEffectiveScope.class', 'KomgaEffectiveScope$Held.class', 'KomgaEffectiveScope.java',
            'KomgaClasspathMetadata.class', 'original-public-dependency-facts.json'}, 'supplier-set')
        self.parents, self.frames, self.raw = {}, {}, {}
        for name, pin in pins.items():
            p = HERE / name
            for ancestor in (p.parent, *p.parent.parents):
                z = ancestor.lstat()
                need(stat.S_ISDIR(z.st_mode), 'supplier-parent')
                need(self.parents.setdefault(ancestor, five(z)) == five(z), 'supplier-parent-original')
            raw, frame = bounded(p, 1048576, owner=(1000, 1000), mode=0o600)
            need(digest(raw) == pin, 'supplier-pin')
            self.raw[name], self.frames[p] = raw, frame
        self.close()

    def close(self):
        need(all(five(p.lstat()) == f for p, f in self.parents.items()) and
             all(nine(p.lstat()) == f for p, f in self.frames.items()), 'supplier-final')


def process_snapshot(pid):
    need(type(pid) is int and pid > 1, 'original-pid')
    root = Path('/proc') / str(pid)
    def identity():
        raw = (root / 'stat').read_bytes()
        fields = raw[raw.rfind(b')') + 2:].split()
        need(len(fields) >= 20 and fields[0] not in (b'Z', b'X'), 'original-process-live')
        return int(fields[19])
    epoch = identity()
    cmd = (root / 'cmdline').read_bytes()
    env = (root / 'environ').read_bytes()
    need(len(cmd) <= 262144 and len(env) <= 262144 and cmd.endswith(b'\0') and env.endswith(b'\0'),
         'original-process-input-bound')
    cwd = os.readlink(root / 'cwd')
    executable = os.readlink(root / 'exe')
    status = (root / 'status').read_text()
    uid = re.search(r'^Uid:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)$', status, re.M)
    need(uid is not None and len(set(uid.groups())) == 1, 'original-process-uid')
    need(identity() == epoch, 'original-process-epoch')
    return dict(pid=pid, start_time=epoch, cmd=cmd, env=env, cwd=cwd,
                executable=executable, uid=int(uid.group(1)))


def heap_only(value):
    return type(value) is str and value.isascii() and (not value.strip() or re.fullmatch(r'-Xm[sx][1-9][0-9]*[kKmMgG]?(?:[ \t\r\n]+-Xm[sx][1-9][0-9]*[kKmMgG]?)*', value.strip()) is not None)


def original_inputs(snapshot, passwd):
    argv = snapshot['cmd'][:-1].decode().split('\0')
    envrows = snapshot['env'][:-1].decode().split('\0')
    environment = {}
    for row in envrows:
        need('=' in row, 'original-env-shape')
        k, v = row.split('=', 1)
        need(k and k not in environment and (k not in AGENTS or heap_only(v)), 'original-env-duplicate-or-agent')
        environment[k] = v
    need(argv and Path(argv[0]).name == 'java', 'original-java-entrypoint')
    properties, index = {}, 1
    while index < len(argv) and argv[index] != '-jar':
        item = argv[index]
        if item.startswith('-D') and '=' in item[2:]:
            key, value = item[2:].split('=', 1)
            need(key and key not in properties, 'original-property-duplicate')
            need(not key.startswith(('java.system.', 'java.protocol.', 'java.nio.', 'java.security.', 'jdk.', 'sun.')) and key not in ('java.home', 'java.class.path', 'java.version', 'java.vendor'), 'unsupported-jvm-provider')
            properties[key] = value
        else:
            need(item == '--enable-native-access=ALL-UNNAMED', 'unsupported-original-jvm-option')
        index += 1
    need(index + 1 < len(argv) and argv[index + 1] in ('application.jar', '/app/application.jar') and
         snapshot['cwd'] == '/app', 'original-main-contract')
    args = argv[index + 2:]
    need(all(s.startswith('--') and '\0' not in s for s in args), 'original-application-arguments')
    accounts = []
    for line in passwd.decode().splitlines():
        parts = line.split(':')
        if len(parts) == 7 and parts[2].isdigit() and int(parts[2]) == snapshot['uid']:
            accounts.append(parts)
    need(len(accounts) == 1, 'original-user-defaults')
    defaults = {'user.dir': snapshot['cwd'], 'user.home': accounts[0][5], 'user.name': accounts[0][0]}
    for key, value in defaults.items():
        properties.setdefault(key, value)
    need(properties['user.dir'] == '/app', 'original-working-directory')
    return properties, environment, args


class ConfigOriginals:
    """Only direct config candidates + selected scope nodes, never payload traversal."""
    def __init__(self, source):
        self.anchors = {}
        try:
            self.root = Path(source)
            need(self.root.is_absolute() and self.root == self.root.resolve(strict=True), 'config-source-canonical')
            self.parents = {}
            for path in (self.root, *self.root.parents):
                z = path.lstat()
                need(stat.S_ISDIR(z.st_mode), 'config-parent-directory')
                self.parents[path] = self.hold(path, five(z))
            self.files, self.raw, self.entries = {}, {}, {}
            scan = os.open('.', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self.anchors[self.root])
            try:
                with os.scandir(scan) as entries:
                    names = [entry.name for entry in entries]
            finally:
                os.close(scan)
            need(len(names) <= 1024 and len(names) == len(set(names)), 'config-direct-entry-bound')
            for name in names:
                z = os.stat(name, dir_fd=self.anchors[self.root], follow_symlinks=False)
                self.entries[name] = self.hold(self.root / name, five(z), self.anchors[self.root])
                if CONFIG_NAME.fullmatch(name):
                    need(not name.endswith('.xml'), 'unsupported-existing-xml-config')
                    raw, frame = bounded(self.root / name, 1048576)
                    self.files[name] = dict(sha256=digest(raw), signature9=frame)
                    self.raw[name] = raw
            need(len(self.files) <= 64 and sum(map(len, self.raw.values())) <= 4194304, 'config-total-bound')
            self.selected = None
            self.close()
        except BaseException:
            try:
                self.release()
            except OSError:
                pass
            raise

    def hold(self, path, original, parent=None):
        flags = os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC
        fd = os.open(path if parent is None else path.name, flags, dir_fd=parent)
        try:
            need(five(os.fstat(fd)) == original == five(path.lstat()), 'config-node-capture')
            need(path not in self.anchors, 'config-node-duplicate')
            self.anchors[path] = fd
        except BaseException:
            os.close(fd)
            raise
        return original

    def original_node(self, path, expected, code):
        need(path in self.anchors and five(os.fstat(self.anchors[path])) == expected == five(path.lstat()), code)

    def release(self):
        anchors, self.anchors = self.anchors, {}
        error = None
        for fd in anchors.values():
            try:
                os.close(fd)
            except OSError as failure:
                error = error or failure
        if error is not None:
            raise error

    def child_input(self):
        need(bool(self.anchors), 'config-custody-released')
        return dict(host_path=str(self.root), root_identity=self.parents[self.root], entries=self.entries,
                    config_files={'/config/' + n: f for n, f in self.files.items()})

    def close(self):
        need(bool(self.anchors), 'config-custody-released')
        for path, expected in self.parents.items():
            self.original_node(path, expected, 'config-root-final')
        names = {p.name for p in self.root.iterdir() if CONFIG_NAME.fullmatch(p.name)}
        need(names == set(self.files), 'config-file-namespace-final')
        for name, ref in self.files.items():
            raw, frame = bounded(self.root / name, 1048576)
            need(frame == ref['signature9'] and digest(raw) == ref['sha256'], 'config-file-final')
        if self.selected is not None:
            for path, expected in self.selected['scope_identities'].items():
                self.original_node(Path(path), expected, 'scope-final')
            for path, row in self.selected['optional_absent_scopes'].items():
                need(not os.path.lexists(path), 'scope-absence-final')
                self.original_node(Path(row['nearest_existing_ancestor']), row['ancestor_identity'], 'scope-absence-final')
            need(not any(os.path.lexists(p) for p in self.selected['absent_config_files']), 'config-absence-final')

    def accept(self, report):
        need(report['config_files'] == {str(self.root / n): f for n, f in self.files.items() if str(self.root / n) in report['config_files']}, 'report-config-join')
        need(set(report['scopes']) == set(report['scope_presence']) == {'config', 'database', 'tasks', 'index', 'fonts'}, 'report-scope-set')
        need(all(Path(x).parent == self.root and CONFIG_NAME.fullmatch(Path(x).name) for x in report['absent_config_files']), 'report-config-absence-scope')
        expected_present, expected_absent = set(), set()
        for role, value in report['scopes'].items():
            need(type(value) is dict and set(value) == {'host_path'}, 'report-scope-shape')
            p = Path(value['host_path'])
            need(p == self.root or p.parent == self.root, 'report-config-subscope')
            if report['scope_presence'][role]:
                expected_present.add(str(p))
                original = self.parents[self.root] if p == self.root else self.entries.get(p.name)
                need(original is not None and original == report['scope_identities'].get(str(p)), 'report-original-scope-node')
            else:
                need(role == 'fonts' and p.name not in self.entries, 'report-optional-fonts')
                expected_absent.add(str(p))
                need(report['optional_absent_scopes'].get(str(p)) == dict(nearest_existing_ancestor=str(self.root), ancestor_identity=self.parents[self.root]), 'report-original-absence-parent')
        need(set(report['scope_identities']) == expected_present and set(report['optional_absent_scopes']) == expected_absent, 'report-node-census')
        self.selected = report
        self.close()


class OriginalCode:
    """Join public image bytes to the original process mount namespace, not image ID alone."""
    def __init__(self, pid, facts):
        self.root = Path('/proc') / str(pid) / 'root'
        self.refs = {}
        app = self.root / 'app'
        self.app_node = five(app.lstat())
        need(not os.path.lexists(app / 'config') and not any(CONFIG_NAME.fullmatch(n) for n in os.listdir(app)), 'unsupported-original-image-config')
        rows = [facts['application'], *facts['dependencies']]
        need(len(rows) == 158 and [r['path'] for r in rows] == ['/app/application.jar', *['/app/' + v for v in facts['classpath']]], 'original-code-census')
        for row in rows:
            relative = Path(row['path']).relative_to('/')
            need(str(relative) == 'app/application.jar' or re.fullmatch(r'app/lib/[A-Za-z0-9_.+\-]+\.jar', str(relative)), 'original-code-path')
            path = self.root / relative
            raw, frame = bounded(path, 256 * 1024**2)
            need(digest(raw) == row['sha256'], 'original-code-public-join')
            self.refs[path] = (frame, row['sha256'])
        self.close()

    def close(self):
        app = self.root / 'app'
        need(five(app.lstat()) == self.app_node and not os.path.lexists(app / 'config') and not any(CONFIG_NAME.fullmatch(n) for n in os.listdir(app)), 'original-image-config-final')
        for path, (frame, sha) in self.refs.items():
            # Full9 recheck closes each already hashed immutable original leaf.
            need(nine(path.lstat()) == frame, 'original-code-final')


def original_service(row, cid):
    s = row['State']
    need(row['Id'] == cid and row['Image'] == IMAGE and s['Running'] is True and s['Paused'] is False
         and s['Restarting'] is False and s['Pid'] > 1, 'original-reader-running')
    mounts = [m for m in row['Mounts'] if m['Destination'] == '/config']
    need(len(mounts) == 1 and mounts[0]['Type'] in ('bind', 'volume') and mounts[0]['RW'] is True, 'original-config-mount')
    destinations = [m['Destination'] for m in row['Mounts']]
    need(len(destinations) == len(set(destinations)) and set(destinations) <= {'/config', '/normalizer-state', '/data/comics', '/data/manga'}, 'supported-original-mount-destinations')
    need(all(m['Type'] == 'bind' and type(m['RW']) is bool for m in row['Mounts'] if m['Destination'] != '/config'), 'supported-original-media-mounts')
    need(not any(m['Destination'].startswith('/config/') or m['Destination'] == '/' or m['Destination'] == '/app' or m['Destination'].startswith('/app/') for m in row['Mounts']), 'original-nested-config-mount')
    return mounts[0]['Source']



# Only the maintained bootstrap declaration; never a caller-provided mount list.
BOOTSTRAP_SOURCE_SHA = '98064a0b4d125cc026e0dd4a115abe3a8b4667918592e2f90d64afe1246b487f'


class BootstrapOriginals(ConfigOriginals):
    """Retain exact bootstrap evidence, not a new bootstrap or NFS admission.

    Original geometry vectors stay historical. No library/state payload is read
    or restamped; the observer still mounts only the original config directory.
    """
    def __init__(self, refs):
        self.anchors = {}; self.frames = {}; self.parents = {}; self.refs = {}
        try:
            need(type(refs) is dict and set(refs) == {'plan', 'source'}, 'bootstrap-original-refs')
            raw = {}
            for role, ref in refs.items():
                need(type(ref) is dict and set(ref) == {'path', 'sha256', 'signature9'}
                     and type(ref['path']) is str and re.fullmatch('[a-f0-9]{64}', ref['sha256'])
                     and type(ref['signature9']) is list and len(ref['signature9']) == 9
                     and all(type(v) is int for v in ref['signature9']), 'bootstrap-original-ref')
                path = Path(ref['path'])
                need(path.is_absolute() and '..' not in path.parts and str(path) == ref['path'], 'bootstrap-original-path')
                for node in reversed((path.parent, *path.parent.parents)):
                    z = node.lstat(); need(stat.S_ISDIR(z.st_mode), 'bootstrap-original-parent')
                    if node not in self.anchors:
                        self.hold(node, five(z), self.anchors.get(node.parent)); self.parents[node] = five(z)
                    else:self.original_node(node, self.parents[node], 'bootstrap-original-parent-drift')
                need(path not in self.anchors, 'bootstrap-original-distinct')
                z = path.lstat(); self.hold(path, five(z), self.anchors[path.parent])
                value, frame = bounded(path, 2*1024**2, owner=(1000, 1000))
                need(frame == ref['signature9'] and stat.S_IMODE(frame[5]) in ((0o600,) if role == 'plan' else (0o600, 0o644))
                     and digest(value) == ref['sha256'], 'bootstrap-original-bytes')
                self.frames[path] = frame; self.refs[role] = dict(ref); raw[role] = value
            need(self.refs['source']['sha256'] == BOOTSTRAP_SOURCE_SHA
                 and Path(self.refs['source']['path']).name == 'genuine_application_bootstrap.py', 'bootstrap-source-pin')
            def pairs(rows):
                result = {}
                for key, value in rows:
                    need(key not in result, 'bootstrap-duplicate-key'); result[key] = value
                return result
            self.document = json.loads(raw['plan'], object_pairs_hook=pairs,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError('bootstrap-nonfinite')))
            self.document_raw = encode(self.document)
            self.close()
        except BaseException:
            self.release(); raise

    def close(self):
        need(bool(self.anchors) and encode(self.document) == self.document_raw, 'bootstrap-originals-released-or-changed')
        for path, frame in self.frames.items():
            need(nine(os.fstat(self.anchors[path])) == frame == nine(path.lstat()), 'bootstrap-original-final9')
        for path, frame in self.parents.items():self.original_node(path, frame, 'bootstrap-original-final5')

    def service(self, row, cid):
        self.close(); value = self.document
        need(type(value) is dict and type(value.get('version')) is int and value['version'] == 1
             and value.get('kind') == 'approved-disposable-application-bootstrap'
             and type(value.get('nonce')) is str and re.fullmatch('[a-f0-9]{64}', value['nonce']), 'bootstrap-original-kind')
        nonce = value['nonce']; roles = value['roles']; images = value['images']
        need(type(roles) is dict and type(images) is dict and set(roles) == set(images) == {'native', 'reader', 'worker'}
             and len({r['id'] for r in roles.values()}) == 3, 'bootstrap-original-role-set')
        for name, role in roles.items():
            need(type(role) is dict and set(role) == {'id', 'image', 'profile', 'epoch'}
                 and re.fullmatch('[a-f0-9]{64}', role['id']) and role['image'] == images[name]
                 and re.fullmatch('sha256:[a-f0-9]{64}', role['image']), 'bootstrap-original-role')
            profile = role['profile']
            need(profile['Id'] == role['id'] and profile['Image'] == role['image']
                 and profile['Name'] == '/archive-bootstrap-' + nonce[:16] + '-' + name
                 and profile['Config']['Labels'].get('com.homelab.archive.bootstrap') == nonce
                 and profile['Config']['Labels'].get('com.homelab.archive.purpose') == 'genuine-archive-fixture', 'bootstrap-original-purpose')
        reader = roles['reader']; state = row['State']
        need(row['Id'] == cid == reader['id'] and row['Image'] == IMAGE == reader['image']
             and state['Running'] is True and state['Paused'] is False and state['Restarting'] is False
             and type(state['Pid']) is int and state['Pid'] > 1, 'bootstrap-original-reader-running')
        need(set(reader['profile']) == {'Id','Name','Image','Path','Args','Config','HostConfig','Mounts','NetworkSettings'}
             and all(row[key] == val for key,val in reader['profile'].items())
             and {k:v for k,v in state.items() if k != 'Health'} == reader['epoch'], 'bootstrap-original-profile-epoch')
        def directory(ref, *, searchable=False):
            need(type(ref) is dict and set(ref) == {'path','signature9'} and type(ref['path']) is str, 'bootstrap-directory-ref')
            path = Path(ref['path']); frame = ref['signature9']
            need(path.is_absolute() and '..' not in path.parts and str(path) == ref['path']
                 and type(frame) is list and len(frame) == 9 and all(type(v) is int for v in frame)
                 and stat.S_ISDIR(frame[5]) and stat.S_IMODE(frame[5]) == (0o711 if searchable else 0o700) and frame[6:8] == [1000,1000], 'bootstrap-directory-declaration')
            return path
        root = directory(value['state_root']); geometry = value['geometry']
        need(set(geometry) == {'version','kind','common_root','library','retention'}
             and type(geometry['version']) is int and (geometry['version'],geometry['kind']) in ((1,'private-common-root-nfs'),(2,'searchable-common-root-nfs')), 'bootstrap-geometry')
        common, library, retention = (directory(geometry[key],searchable=geometry['version']==2 and key=='common_root') for key in ('common_root','library','retention'))
        need(root.name == 'archive-bootstrap-' + nonce and common.name == 'archive-publication-' + nonce
             and library == common/'L' and retention == common/'R'
             and root != common and root not in common.parents and common not in root.parents
             and all(not (v == Path('/app') or Path('/app') in v.parents or v == Path('/config') or Path('/config') in v.parents) for v in (root,common)), 'bootstrap-finite-geometry')
        expected = [(str(root/'reader'), '/config', True), (str(library), str(library), False)]
        need(len(row['Mounts']) == 2 and all(m['Type'] == 'bind' and type(m['RW']) is bool for m in row['Mounts'])
             and sorted((m['Source'],m['Destination'],m['RW']) for m in row['Mounts']) == sorted(expected), 'bootstrap-exact-reader-mounts')
        self.close(); return str(root/'reader')


def static_service(row):
    return {k: row[k] for k in ('Id', 'Image', 'Config', 'HostConfig', 'Mounts', 'RestartCount')} | {
        'state': {k: row['State'][k] for k in ('Running', 'Paused', 'Restarting', 'Pid', 'StartedAt')}}


def child_command(name, token, cidpath, code, config):
    return ['/usr/bin/docker', 'run', '--interactive', '--name', name,
            '--label', 'com.homelab.isolated-verification=' + token, '--cidfile', str(cidpath),
            '--pull', 'never', '--read-only', '--network', 'none', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--user', '1000:1000', '--memory', '512m',
            '--memory-swap', '512m', '--pids-limit', '64', '--no-healthcheck',
            *[part for leaf in CLASSES for part in ('--volume', str(code / leaf) + ':/checks/' + leaf + ':ro')],
            '--volume', config + ':/config:ro', '--entrypoint', 'java', IMAGE,
            '-XX:-UsePerfData', '-cp', '/checks:/app/application.jar', 'KomgaEffectiveScope']


def child_profile(row, name, token, code, config, image_env):
    need(row['Image'] == IMAGE and row['Config']['Image'] == IMAGE and row['Name'] == '/' + name, 'child-image')
    c, h = row['Config'], row['HostConfig']
    need(c['User'] == '1000:1000' and c['Entrypoint'] == ['java'] and
         c['Cmd'] == ['-XX:-UsePerfData', '-cp', '/checks:/app/application.jar', 'KomgaEffectiveScope'] and
         c.get('Env') == image_env and c.get('Labels', {}).get('com.homelab.isolated-verification') == token and
         c.get('Healthcheck') == {'Test': ['NONE']}, 'child-command')
    need(h['ReadonlyRootfs'] is True and h['NetworkMode'] == 'none' and h['CapDrop'] == ['ALL'] and
         h['SecurityOpt'] == ['no-new-privileges'] and h['Privileged'] is False and
         h['Memory'] == h['MemorySwap'] == 536870912 and h['PidsLimit'] == 64, 'child-isolation')
    expected = {str(code / leaf): '/checks/' + leaf for leaf in CLASSES} | {config: '/config'}
    need(type(h.get('Binds')) is list and Counter(h['Binds']) == Counter(s + ':' + d + ':ro' for s, d in expected.items()) and not h.get('Tmpfs') and
         not h.get('Mounts') and not h.get('Devices') and not h.get('DeviceRequests') and
         not h.get('PortBindings') and h.get('PublishAllPorts') is False, 'child-bind-security')
    need(len(row['Mounts']) == len(CLASSES) + 1 and all(m['Type'] == 'bind' for m in row['Mounts']) and
         {(m['Source'], m['Destination'], m['RW']) for m in row['Mounts']} ==
         {(source, destination, False) for source, destination in expected.items()}, 'child-exact-mounts')


def line(stream, deadline, limit):
    # Unbuffered pipe plus bytewise bounded reads avoids read-ahead hiding ACK bytes.
    data = bytearray()
    with selectors.DefaultSelector() as selector:
        selector.register(stream, selectors.EVENT_READ)
        while True:
            remaining = deadline - time.monotonic()
            need(remaining > 0 and selector.select(remaining), 'child-pipe-deadline')
            raw = os.read(stream.fileno(), 1)
            need(raw and len(data) < limit, 'child-pipe-bound-or-eof')
            if raw == b'\n':
                return bytes(data)
            data.extend(raw)


def pending_report(raw, runtime_sha, producer_sha, original):
    report = json.loads(raw)
    need(report.get('kind') == 'komga-effective-persistent-scope-observation' and
         report.get('source_sha256') == producer_sha and report.get('runtime_sha256') == runtime_sha and
         report.get('image') == IMAGE and report.get('jar_sha256') == JAR and report.get('source_commit') == COMMIT and
         report.get('container_id') == original['container_id'] and report.get('pid') == original['pid'] and
         report.get('start_time') == original['start_time'], 'pending-source-and-process')
    need(report.get('final_ack_required') is True and all(report.get(k) is False for k in (
        'scope_observation_verified', 'unsupported_imports_observed', 'all_library_settings_verified',
        'process_verified_by_parent', 'application_context_started')), 'pending-no-rights')
    return report


def observation_references(output, producer, producer_sha, parent, parent_sha):
    """Original code identities join SourceCohort; five proof records are outputs."""
    roles = {'runtime': 'runtime.private.json', 'report': 'report.private.json',
             'acceptance': 'acceptance.private.json', 'ack': 'ack.private.json',
             'parent_ack': 'parent-ack.private.json'}
    refs = {role: dict(path=str(output / leaf), sha256=digest((output / leaf).read_bytes()))
            for role, leaf in roles.items()}
    refs.update(producer=dict(path=str(producer), sha256=producer_sha),
                parent_source=dict(path=str(parent), sha256=parent_sha))
    return refs


def main():
    need(ACTIVATE is True and IMAGE is not None and PLAN is not None and SUPPLIER_PINS is not None and os.geteuid() == 0 and
         sys.flags.isolated and sys.dont_write_bytecode, 'disabled')
    need(set(PLAN) in ({'container_id', 'output'}, {'container_id', 'output', 'bootstrap_originals'})
         and re.fullmatch('[a-f0-9]{64}', PLAN['container_id']), 'plan')
    suppliers = Suppliers(SUPPLIER_PINS)
    owned_path = HERE / 'owned.py'
    spec = importlib.util.spec_from_file_location('_effective_owned', owned_path)
    owned = importlib.util.module_from_spec(spec)
    exec(compile(suppliers.raw['owned.py'], str(owned_path), 'exec'), owned.__dict__)
    class Output(owned.JarOutput):
        NAMES = {'export.cid', *CLASSES,
                 'producer-source.class', 'parent-source.py', 'runtime.private.json', 'input.private.json',
                 'report.private.json', 'acceptance.private.json', 'ack.private.json', 'parent-ack.private.json',
                 'child.stderr', 'result.private.json'}
    original = owned.inspect(PLAN['container_id'])
    need(original is not None, 'original-container')
    bootstrap = BootstrapOriginals(PLAN['bootstrap_originals']) if 'bootstrap_originals' in PLAN else None
    try:
        config = ConfigOriginals(bootstrap.service(original, PLAN['container_id']) if bootstrap is not None
                                 else original_service(original, PLAN['container_id']))
    except BaseException:
        if bootstrap is not None:bootstrap.release()
        raise
    try:
        process = process_snapshot(original['State']['Pid'])
        passwd_path = Path('/proc') / str(process['pid']) / 'root/etc/passwd'
        passwd, passwd_frame = bounded(passwd_path, 65536)
        properties, environment, args = original_inputs(process, passwd)
        service = static_service(original)
        facts = json.loads(suppliers.raw['original-public-dependency-facts.json'])
        code_originals = OriginalCode(process['pid'], facts)
        source, source_frame = bounded(__file__, 131072, owner=(1000, 1000), mode=0o600)
        parent_sha = digest(source)
        def close():
            if bootstrap is not None:bootstrap.close()
            suppliers.close()
            need(nine(Path(__file__).lstat()) == source_frame, 'parent-source-final')
            need(static_service(owned.inspect(PLAN['container_id'])) == service and
                 process_snapshot(process['pid']) == process, 'original-runtime-final')
            need(bounded(passwd_path, 65536) == (passwd, passwd_frame), 'original-user-defaults-final')
            config.close()
            code_originals.close()
        close()
        runtime = dict(kind='reviewed-komga-effective-scope-runtime', observed=int(time.time()),
                       jar_sha256=JAR, source_commit=COMMIT, container=original,
                       pid=process['pid'], start_time=process['start_time'])
        runtime_raw = encode(runtime)
        producer_sha = SUPPLIER_PINS['KomgaEffectiveScope.class']
        input_value = dict(version=1, kind='original-komga-effective-input-v1', properties=properties,
                           environment=environment, args=args, config_roots=['/config'],
                           source_sha256=producer_sha, runtime_sha256=digest(runtime_raw), image=IMAGE,
                           container_id=PLAN['container_id'], pid=process['pid'], start_time=process['start_time'],
                           mount=config.child_input())
        # This preflight binds the independently captured public factory graph, not a guessed provider set.
        need(facts['application']['sha256'] == JAR and len(facts['dependencies']) == len(facts['classpath']) == 157,
             'public-dependency-source')
        image = json.loads(subprocess.run(['/usr/bin/docker', 'image', 'inspect', IMAGE], capture_output=True,
                                         check=True, timeout=30).stdout)
        need(len(image) == 1 and image[0]['Id'] == IMAGE and image[0]['Os'] == 'linux' and
             image[0]['Architecture'] == 'amd64' and image[0]['Config']['WorkingDir'] == '/app' and
             set(image[0]['Config'].get('Volumes') or {}) == {'/config'}, 'original-public-image')
        image_env = image[0]['Config']['Env']
        need(not any(v.split('=', 1)[0] in AGENTS for v in image_env), 'public-image-no-agents')
        output_path = Path(PLAN['output'])
        need(output_path.is_absolute() and not output_path.is_relative_to(config.root) and
             not config.root.is_relative_to(output_path), 'output-outside-config')
        out = Output(output_path)
        proc = None
        name = 'komga-effective-' + secrets.token_hex(16)
        token = name.removeprefix('komga-effective-')
        deadline = time.monotonic() + 100
        try:
            out.write('producer-source.class', suppliers.raw['KomgaEffectiveScope.class'])
            out.write('parent-source.py', source)
            for name0 in CLASSES:
                out.write(name0, suppliers.raw[name0])
                fd = os.open(name0, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=out.fd)
                try:
                    os.fchmod(fd, 0o444)
                    out.files[name0] = tuple(nine(os.fstat(fd)))
                finally:
                    os.close(fd)
            out.write('runtime.private.json', runtime_raw)
            out.write('input.private.json', encode(input_value))
            close()
            need(owned.inspect(name) is None, 'fresh-child')
            out.close()
            err = out.create('child.stderr')
            command = child_command(name, token, Path('/proc/self/fd') / str(out.fd) / 'export.cid', out.path, str(config.root))
            def limit():
                resource.setrlimit(resource.RLIMIT_FSIZE, (1048576, 1048576))
            proc = subprocess.Popen(command, preexec_fn=limit, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err,
                                    bufsize=0, pass_fds=(out.fd,), umask=0o077)
            pipes = tuple((p.fileno(), os.fstat(p.fileno()).st_ino) for p in (proc.stdin, proc.stdout))
            proc.stdin.write(encode(input_value) + b'\n')
            ready = line(proc.stdout, deadline, 1500000)
            need(ready.startswith(b'SCOPE_READY '), 'child-ready')
            raw = base64.b64decode(ready.removeprefix(b'SCOPE_READY '), validate=True)
            need(len(raw) <= 1048576, 'child-report-bound')
            report = pending_report(raw, digest(runtime_raw), producer_sha,
                                    dict(container_id=PLAN['container_id'], pid=process['pid'], start_time=process['start_time']))
            config.accept(report)
            out.cid()
            child = owned.inspect(name)
            child_profile(child, name, token, out.path, str(config.root), image_env)
            need(child['State']['Running'] is True and proc.poll() is None, 'same-child-awaiting-ack')
            close()
            out.close()
            need(all(os.fstat(fd).st_ino == ino for fd, ino in pipes), 'same-original-pipes')
            out.write('report.private.json', raw)
            report_sha = digest(raw)
            acceptance = dict(kind='accepted-komga-effective-scope', scope_observation_verified=False,
                              final_ack_required=True, same_process_verified=True, report_sha256=report_sha,
                              source_sha256=parent_sha, helper_sha256=producer_sha, **RIGHTS)
            acceptance_raw = encode(acceptance)
            out.write('acceptance.private.json', acceptance_raw)
            close()
            out.close()
            proc.stdin.write(('ACCEPT ' + report_sha + '\n').encode())
            proc.stdin.close()
            need(line(proc.stdout, deadline, 100) == ('SCOPE_ACK ' + report_sha).encode(), 'producer-final-ack')
            need(proc.wait(timeout=max(0.1, deadline - time.monotonic())) == 0 and proc.stdout.read(1) == b'', 'producer-completed')
            out.seal('child.stderr', 1048576)
            child = owned.inspect(name)
            child_profile(child, name, token, out.path, str(config.root), image_env)
            need(child['State']['Status'] == 'exited' and child['State']['ExitCode'] == 0 and
                 child['State']['Pid'] == 0 and child['State']['Running'] is False and not child['State'].get('OOMKilled'), 'child-terminal')
            close()
            out.close()
            out.write('ack.private.json', encode(dict(scope_observation_verified=True, report_sha256=report_sha, **RIGHTS)))
            out.write('parent-ack.private.json', encode(dict(scope_observation_verified=True, same_process_verified=True,
                      acceptance_sha256=digest(acceptance_raw), report_sha256=report_sha, **RIGHTS)))
            subprocess.run(['/usr/bin/docker', 'container', 'rm', '--volumes', child['Id']], capture_output=True,
                           check=True, timeout=30)
            need(owned.inspect(name) is None, 'owned-child-cleanup')
            close()
            out.close()
            refs = observation_references(out.path, HERE / 'KomgaEffectiveScope.class', producer_sha,
                                          Path(__file__).absolute(), parent_sha)
            out.close()
            out.write('result.private.json', encode(dict(kind='reviewed-komga-effective-originals-v1', references=refs,
                      scope_observation_verified=True, same_process_verified=True, **RIGHTS)))
            close()
            out.close()
            print(json.dumps(dict(scope_observation_verified=True, same_process_verified=True, **RIGHTS)), flush=True)
        finally:
            # Uncertainty never grants acceptance or cleanup of a running child. Preserve all artifacts.
            if proc is not None:
                for pipe in (proc.stdin, proc.stdout):
                    if pipe and not pipe.closed:
                        pipe.close()
            primary = sys.exc_info()[1]
            try:
                out.release()
            except BaseException:
                if primary is None:
                    raise
                # Preserve the original refusal; no success result or acceptance is inferred.
    finally:
        primary = sys.exc_info()[1]
        release_error = None
        try:
            config.release()
        except BaseException as error:
            release_error = error
        if bootstrap is not None:
            try:bootstrap.release()
            except BaseException as error:
                release_error = release_error or error
        if primary is None and release_error is not None:raise release_error


if __name__ == '__main__':
    main()
