"""Explicit disposable application bootstrap; never a connected-factory grant.

Original containers, images, internal network and virgin paths are prerequisites.
This producer commits real Mylar genesis and creates/scans a real Komga library.
It does not create containers, enroll users, seed a native catalog or manufacture
SourceCohort/NFS/Parent admission evidence. Unknown results remain held.
"""
import argparse
import configparser
import copy
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import sys
import time
import urllib.parse
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import comic_reader_lifecycle_parent as p
import comic_negative_nfs_active_parent as active
import comic_reader_backup_primitives as backup
import genuine_archive_fixture as fixture
from genuine_bootstrap_http import identifier

Held = p.Held


class ApplicationNotReady(Held):
    pass


need = p.need
LABEL = 'com.homelab.archive.bootstrap'
PURPOSE = 'com.homelab.archive.purpose'
REQUIRED_SDK = {'media_writer.py', 'native_writers.py', 'publication_fresh.py',
                'publication_api.py', 'worker_health.py', 'publication_reader_lifecycle.py',
                'publication_native_scope_birth.py', 'publication_native_configured_scope.py'}
IMAGE_PROGRAM = """import hashlib,json,pathlib,re,sys
names=json.load(sys.stdin);assert type(names)is list and 1<=len(names)<=512
out={}
for name in names:
 assert type(name)is str and re.fullmatch('[A-Za-z_][A-Za-z0-9_]*[.]py',name)
 path=pathlib.Path('/app/mylar3/mylar')/name
 assert path.is_file() and not path.is_symlink() and path.stat().st_size<=4*1024**2
 out[name]=hashlib.sha256(path.read_bytes()).hexdigest()
sys.stdout.write(json.dumps(out,sort_keys=True))
"""


def put(path, value):
    raw = p.encode(value) + b'\n'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    backup.sync(Path(path).parent)
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), signature9=p.nine(os.lstat(path)))


def directory(ref):
    need(type(ref) is dict and set(ref) == {'path', 'signature9'}, 'directory-reference')
    path = p.absolute(ref['path']); original = ref['signature9']
    need(path.resolve(strict=True) == path and all(not x.is_symlink() for x in (path, *path.parents)), 'canonical-directory')
    need(type(original) is list and len(original) == 9 and all(type(x) is int for x in original)
         and p.nine(os.lstat(path)) == original and stat.S_ISDIR(original[5])
         and stat.S_IMODE(original[5]) == 0o700 and original[6:8] == [1000, 1000], 'private-original-directory')
    return path


def plan(value):
    need(type(value) is dict and set(value) == {'version', 'kind', 'nonce', 'observed', 'seconds',
         'state_root', 'geometry', 'roles', 'images', 'network', 'native_sdk', 'native_ini',
         'helper', 'native_probe', 'scope_source', 'nfs_mount', 'reader_credentials', 'reader_host', 'reader_port'}, 'bootstrap-plan-schema')
    need(type(value['version']) is int and value['version'] == 1
         and value['kind'] == 'approved-disposable-application-bootstrap' and p.digest(value['nonce'])
         and type(value['observed']) is int and 0 <= time.time() - value['observed'] <= 120
         and type(value['seconds']) is int and 30 <= value['seconds'] <= 900, 'bootstrap-plan-kind-deadline')
    root = directory(value['state_root'])
    need(root.name == 'archive-bootstrap-' + value['nonce'], 'disposable-state-name')
    need(set(value['roles']) == set(value['images']) == {'native', 'reader', 'worker'}, 'three-original-roles')
    need(len({v['id'] for v in value['roles'].values()}) == 3, 'distinct-original-roles')
    for role, row in value['roles'].items():
        need(type(row) is dict and set(row) == {'id', 'image', 'profile', 'epoch'}
             and p.digest(row['id']) and re.fullmatch('sha256:[0-9a-f]{64}', row['image'])
             and row['image'] == value['images'][role], 'original-image-role')
        profile = row['profile']
        need(profile.get('Id') == row['id'] and profile.get('Image') == row['image']
             and profile.get('Name') == '/archive-bootstrap-' + value['nonce'][:16] + '-' + role
             and profile.get('Config', {}).get('Labels', {}).get(LABEL) == value['nonce']
             and profile['Config']['Labels'].get(PURPOSE) == 'genuine-archive-fixture', 'disposable-role-purpose')
    geometry = value['geometry']; need(type(geometry) is dict and set(geometry) == {'version', 'kind', 'common_root', 'library', 'retention'}, 'publication-geometry')
    need(geometry['common_root']['path'].endswith('/archive-publication-' + value['nonce']), 'disposable-publication-name')
    for role in ('common_root', 'library', 'retention'):directory(geometry[role])
    need(type(value['network']) is dict and set(value['network']) == {'id', 'profile'} and p.digest(value['network']['id']), 'network-original')
    need(type(value['reader_port']) is int and 1 <= value['reader_port'] <= 65535
         and type(value['reader_host']) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', value['reader_host']), 'reader-original-origin')
    nfs_mount(value['nfs_mount'], Path(geometry['common_root']['path']))
    return copy.deepcopy(value)


def nfs_mount(value, common):
    need(type(value) is dict and set(value) == {'id', 'source', 'target', 'fstype', 'fsroot', 'options', 'maj:min'}, 'original-nfs-mount-schema')
    try:active.mount_identity(dict(filesystems=[{k:v for k,v in value.items() if k!='id'}]))
    except active.Held:raise Held('original-nfs4-mount-required') from None
    need(type(value['id']) in (int, str) and str(value['id']).isdigit() and int(value['id']) > 0
         and all(type(value[k]) is str and value[k] for k in ('source','target','fsroot','options','maj:min'))
         and re.fullmatch('[0-9]+:[0-9]+',value['maj:min']) and 'rw' in value['options'].split(','), 'original-writable-nfs-mount')
    target=p.absolute(value['target'])
    need(target==common or target in common.parents, 'original-nfs-mount-target')
    device=os.lstat(common).st_dev
    need(value['maj:min']==str(os.major(device))+':'+str(os.minor(device)), 'original-nfs-mount-device')
    return value


class Docker:
    """Direct client only; no pkexec, pull or operational fallback."""
    def mount(self, path, seconds):
        result = subprocess.run(['/usr/bin/findmnt', '--json', '--target', str(path), '--output', 'ID,SOURCE,TARGET,FSTYPE,FSROOT,OPTIONS,MAJ:MIN'], capture_output=True, timeout=seconds, check=False, env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        need(result.returncode==0 and len(result.stdout)<=65536, 'actual-nfs-mount-held')
        value=p.decode(result.stdout)
        need(type(value) is dict and set(value)=={'filesystems'} and type(value['filesystems']) is list and len(value['filesystems'])==1, 'one-actual-nfs-mount')
        return value['filesystems'][0]

    def run(self, args, seconds, data=None):
        result = subprocess.run(['/usr/bin/docker', '--host', 'unix:///run/docker.sock', *args],
                                input=data, capture_output=True, timeout=seconds, check=False,
                                env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        need(result.returncode == 0 and len(result.stdout) <= 16 * 1024**2, 'disposable-engine-held')
        return result.stdout


class Bootstrap:
    def __init__(self, value, engine):
        self.plan = plan(value); self.engine = engine; self.end = time.monotonic() + value['seconds']
        self.root = Path(value['state_root']['path']); self.output = self.root / ('bootstrap-' + value['nonce'])
        need(not os.path.lexists(self.output), 'bootstrap-no-replay')
        self.native_mount = self.root / 'native'; self.data = Path(value['native_ini']['path']).parent; self.reader = self.root / 'reader'; self.worker = self.root / 'worker'
        self.library = Path(value['geometry']['library']['path']); self.retention = Path(value['geometry']['retention']['path'])
        for path in (self.native_mount, self.data, self.reader, self.worker):
            directory(dict(path=str(path), signature9=p.nine(os.lstat(path))))
        self.sdk = p.decode(p.read(value['native_sdk'])); need(REQUIRED_SDK <= set(self.sdk) and len(self.sdk) <= 512, 'native-installed-map')
        need(all(re.fullmatch('[A-Za-z_][A-Za-z0-9_]*[.]py', k) and p.digest(v) for k, v in self.sdk.items()), 'native-installed-map-fields')
        need(Path(value['helper']['path']) == HERE/'genuine_bootstrap_http.py', 'fixed-http-helper')
        self.program = p.read(value['helper'], private=False).decode()
        need(Path(value['native_probe']['path'])==HERE/'comic_native_process_probe.py' and Path(value['scope_source']['path'])==HERE/'publication_native_configured_scope.py','owning-native-probe-sources')
        self.probe_program=p.read(value['native_probe'],private=False).decode();self.scope_source=p.read(value['scope_source'],private=False).decode()
        need(value['scope_source']['sha256']==self.sdk['publication_native_configured_scope.py'],'original-installed-scope-parser')
        creds = p.decode(p.read(value['reader_credentials']))
        need(type(creds) is dict and set(creds) == {'api_key'} and type(creds['api_key']) is str
             and creds['api_key'] and not any(c in creds['api_key'] for c in '\r\n'), 'reader-private-key')
        self.reader_key = creds['api_key']; ini = value['native_ini']
        need(ini['path'] == str(self.data / 'config.ini') and (self.data==self.native_mount or self.native_mount in self.data.parents) and ini['signature9'][6] == 1000
             and stat.S_IMODE(ini['signature9'][5]) == 0o600, 'original-private-native-config')
        cfg = configparser.ConfigParser(interpolation=None, strict=True); cfg.read_string(p.read(ini, private=False).decode())
        need(not cfg.defaults(), 'native-config-defaults')
        def one(section, key, default=None):
            values=[cfg.get(s,key,raw=True) for s in cfg.sections() if cfg.has_option(s,key)]
            if not values and default is not None:return default
            need(len(values)==1 and cfg.has_option(section,key), 'native-config-unique-section')
            return values[0]
        def boolean(section,key,default=None):
            value=one(section,key,default).casefold()
            need(value in ('0','1','false','true'), 'native-config-boolean')
            return value in ('1','true')
        need(boolean('API','api_enabled') and not boolean('Interface','enable_https','0'), 'native-primary-api')
        self.native_key = one('API','api_key'); raw_port=one('Interface','http_port')
        need(raw_port.isdecimal(), 'native-http-port'); port=int(raw_port)
        prefix = one('Interface','http_root','').rstrip('/')
        need(len(self.native_key) == 32 and 1 <= port <= 65535 and (not prefix or prefix.startswith('/'))
             and not any(x in prefix for x in ('..', '?', '#', '\\', '://'))
             and one('General','destination_dir') == str(self.library), 'native-configured-origin-library')
        self.native_base = 'http://127.0.0.1:' + str(port) + prefix
        self.reader_base = 'http://' + value['reader_host'] + ':' + str(value['reader_port'])
        self.epochs = {k: copy.deepcopy(v['epoch']) for k, v in value['roles'].items()}; self.steps = 0
        self.profiles = {k: copy.deepcopy(v['profile']) for k,v in value['roles'].items()}
        self.network_profile = copy.deepcopy(value['network']['profile'])
        self.geometry = p.admit_common_root(value['geometry'], [dict(host=value['geometry']['common_root']['path'], child=value['geometry']['common_root']['path'], write=True)], str(self.library), str(self.retention), [str(self.root)])

    def seconds(self):
        left = self.end - time.monotonic(); need(left > 0, 'bootstrap-deadline')
        return min(30, max(1, int(left)))

    def roles(self, *, restarting=False):
        p.check_common_root(self.geometry)
        common=Path(self.plan['geometry']['common_root']['path'])
        for path in (common,self.library,self.retention):
            observed=self.engine.mount(path,self.seconds())
            need(nfs_mount(observed,common)==self.plan['nfs_mount'], 'original-nfs-mount-changed-or-shadowed')
        rows = {}
        mounts = {'native': [(str(self.native_mount), '/config', True), (str(self.library), str(self.library), True)],
                  'reader': [(str(self.reader), '/config', True), (str(self.library), str(self.library), False)],
                  'worker': [(str(self.worker), '/state', True), (str(self.data), '/mylar', False), (str(self.library), '/data/comics', True)]}
        for role, expected in self.plan['roles'].items():
            result = p.decode(self.engine.run(['inspect', expected['id']], self.seconds()))
            need(type(result) is list and len(result) == 1, 'one-original-role')
            row = result[0]; original = self.profiles[role]
            if restarting and role == 'native':
                projected = p.static(row); before = copy.deepcopy(original['NetworkSettings']); after = copy.deepcopy(projected['NetworkSettings'])
                for item in (before,after):
                    item.pop('SandboxID',None);item.pop('SandboxKey',None)
                    for endpoint in item.get('Networks',{}).values():endpoint.pop('EndpointID',None)
                need(before==after and {k:v for k,v in projected.items() if k!='NetworkSettings'}=={k:v for k,v in original.items() if k!='NetworkSettings'},'own-restart-static-successor')
                self.profiles[role]=projected
            else:need(p.static(row) == original, 'original-role-static')
            host = row['HostConfig']; state = row['State']
            need(not host.get('Privileged') and not host.get('Devices') and not host.get('DeviceRequests') and not host.get('CapAdd')
                 and all(x=='no-new-privileges' for x in (host.get('SecurityOpt') or []))
                 and not host.get('PortBindings') and host.get('NetworkMode') not in ('host', 'container')
                 and host.get('PidMode', '') != 'host' and host.get('IpcMode', '') != 'host'
                 and all(not x for x in row['NetworkSettings'].get('Ports', {}).values()), 'isolated-role-profile')
            need(all(m['Type'] == 'bind' for m in row['Mounts']) and sorted((m['Source'], m['Destination'], m['RW']) for m in row['Mounts']) == sorted(mounts[role]), 'no-foreign-role-mounts')
            need(all(not state.get(k) for k in ('Paused', 'Restarting', 'Dead', 'OOMKilled')), 'role-state')
            need(state['Status'] == ('created' if role == 'worker' else 'running')
                 and state['Running'] is (role != 'worker') and (state['Pid'] == 0 if role == 'worker' else state['Pid'] > 0), 'role-runtime')
            epoch = {k: v for k, v in state.items() if k != 'Health'}
            if restarting and role == 'native':
                need(epoch['StartedAt'] != self.epochs[role]['StartedAt'], 'native-own-restart-epoch')
                self.epochs[role] = epoch
            else:need(epoch == self.epochs[role], 'original-role-epoch')
            rows[role] = row
        net = p.decode(self.engine.run(['network', 'inspect', self.plan['network']['id']], self.seconds()))
        need(type(net) is list and len(net) == 1, 'one-original-network')
        if restarting:
            before=copy.deepcopy(self.network_profile);after=copy.deepcopy(net[0]);native=self.plan['roles']['native']['id']
            for item in (before,after):
                if native in item.get('Containers',{}):item['Containers'][native].pop('EndpointID',None)
            need(before==after,'own-restart-network-successor');self.network_profile=net[0]
        need(net[0] == self.network_profile
             and net[0].get('Internal') is True and net[0].get('Driver') == 'bridge'
             and net[0].get('Labels',{}).get(LABEL)==self.plan['nonce']
             and net[0]['Labels'].get(PURPOSE)=='genuine-archive-fixture'
             and set(net[0].get('Containers', {})) <= {r['Id'] for r in rows.values()}, 'original-internal-network')
        for role in ('native', 'reader'):
            networks = rows[role]['NetworkSettings']['Networks']
            need(len(networks) == 1 and next(iter(networks.values()))['NetworkID'] == self.plan['network']['id'], 'same-private-network')
        aliases = next(iter(rows['reader']['NetworkSettings']['Networks'].values())).get('Aliases') or []
        need(self.plan['reader_host'] in aliases, 'original-reader-alias')
        return rows

    def http(self, kind, operation, arguments=None):
        self.roles()
        request = dict(kind=kind, base=self.native_base if kind == 'native' else self.reader_base,
                       key=self.native_key if kind == 'native' else self.reader_key,
                       operation=operation, arguments=arguments or {}, seconds=self.seconds())
        try:
            raw = self.engine.run(['exec', '--interactive', '--user', '1000:1000', self.plan['roles']['native']['id'],
                                   '/lsiopy/bin/python3', '-I', '-B', '-c', self.program, '--owning-disposable-bootstrap-http-v1', self.plan['nonce'], self.plan['roles']['native']['id']], self.seconds(), p.encode(request))
        except Held:
            if kind=='native' and operation=='health':raise ApplicationNotReady('native-read-only-health-not-ready') from None
            raise
        value = p.decode(raw); need(type(value) is dict and set(value) == {'result'}, 'original-http-result')
        self.roles()
        result = value['result']
        if kind == 'native' and operation == 'force-process-fixture':
            need(type(result)is str,'native-queue-response');return result
        if kind == 'native':
            need(type(result) is dict and result.get('success') is True and type(result.get('data')) is dict, 'native-primary-response')
            return result['data']
        return result

    def step(self, name, operation):
        self.roles(); self.steps += 1; prefix = str(self.steps).zfill(2) + '-' + name
        put(self.output / (prefix + '-intent.json'), dict(kind=name, automatic_replay=False))
        result = operation()
        self.roles(); put(self.output / (prefix + '-done.json'), dict(kind=name, result=result))
        return result

    def installed_sources(self):
        observed=p.decode(self.engine.run(['exec','--interactive','--user','1000:1000',self.plan['roles']['native']['id'],'/lsiopy/bin/python3','-I','-B','-c',IMAGE_PROGRAM],self.seconds(),p.encode(sorted(self.sdk))))
        need(observed==self.sdk,'actual-native-installed-source-parity');return observed

    def native_original(self):
        self.roles();request=dict(version=1,nonce=self.plan['nonce'],source_sha256=self.plan['native_probe']['sha256'],seconds=self.seconds(),module_pins={'/app/mylar3/mylar/'+name:self.sdk[name] for name in ('worker_health.py','native_writers.py')},scope_source=self.scope_source)
        value=p.decode(self.engine.run(['exec','--interactive','--user','1000:1000',self.plan['roles']['native']['id'],'/lsiopy/bin/python3','-I','-B','-c',self.probe_program],self.seconds(),p.encode(request)))
        expected='/config/'+str(Path(self.plan['native_ini']['path']).relative_to(self.native_mount))
        need(value.get('version')==1 and value.get('nonce')==self.plan['nonce'] and value.get('source_sha256')==self.plan['native_probe']['sha256']
             and value.get('config')==dict(self.plan['native_ini'],path=expected) and value.get('publication',{}).get('state')=='held','original-virgin-native-process-config')
        self.roles();return value

    def fresh_backup(self):
        need(not any(os.path.lexists(self.data / name) for name in ('mylar.db', 'workflow.sqlite', 'media-writer', 'publication-fresh-v1.json'))
             and not any(os.path.lexists(self.data / (name + suffix)) for name in ('mylar.db', 'workflow.sqlite') for suffix in ('-wal', '-shm', '-journal')), 'native-must-be-virgin')
        # Reuse the owning inventory/copy/metadata algorithms; no dummy database.
        count = total = 0
        for folder, dirs, files in os.walk(self.data, followlinks=False):
            for name in dirs + files:
                row = os.lstat(Path(folder) / name); count += 1; total += row.st_size
                need(not stat.S_ISLNK(row.st_mode) and (stat.S_ISDIR(row.st_mode) or stat.S_ISREG(row.st_mode) and row.st_nlink == 1)
                     and count <= 1024 and total <= 32 * 1024**2, 'virgin-backup-bounds')
        before, _ = backup.inventory(self.data, 'tree')
        backup.copy_scope(self.data, self.output / 'native-backup', before)
        backup.copy_scope(self.output / 'native-backup', self.output / 'native-restore', before)
        self.roles()
        need(backup.inventory(self.data, 'tree')[0] == before, 'virgin-backup-original-drift')
        restored, _ = backup.inventory(self.output / 'native-restore', 'tree', detached=True)
        need(backup.logical(restored) == backup.logical(before), 'virgin-restore-mismatch')
        manifest = put(self.output / 'virgin-manifest.json', dict(source=str(self.data), records=before))
        proof = put(self.output / 'virgin-restore.json', dict(manifest=manifest, records=restored))
        return dict(manifest_sha256=manifest['sha256'], restore_sha256=proof['sha256'], description='Exclusive disposable virgin native configuration, verified independent restore')

    def native(self):
        evidence = self.fresh_backup()
        prepared = self.step('prepare-fresh', lambda: self.http('native', 'prepare-fresh', dict(epoch=self.plan['nonce'], backup=evidence)))
        need(prepared.get('outcome') == 'prepared' and p.digest(prepared.get('token')), 'actual-prepared-token')
        token = prepared['token']
        committed = self.step('initialize-bootstrap', lambda: self.http('native', 'initialize-bootstrap', dict(token=token)))
        need(committed.get('token') == token and committed.get('outcome') == 'committed', 'actual-bootstrap-commit')
        self.roles(); self.steps += 1; prefix = str(self.steps).zfill(2) + '-native-restart'
        put(self.output / (prefix + '-intent.json'), dict(id=self.plan['roles']['native']['id'], automatic_replay=False))
        result = self.engine.run(['restart', '--time', '30', self.plan['roles']['native']['id']], self.seconds()).decode().strip()
        need(result == self.plan['roles']['native']['id'], 'original-restart-ack')
        self.roles(restarting=True)
        while True:
            try:health = self.http('native', 'health');break
            except ApplicationNotReady:time.sleep(min(0.2,self.seconds()))
        need(health.get('publication', {}).get('state') == 'ready', 'native-startup-not-ready')
        database = self.data / 'mylar.db'
        need(database.is_file() and not database.is_symlink() and not any(os.path.lexists(str(database) + s) for s in ('-wal', '-shm', '-journal')), 'native-catalog-not-stable')
        with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
            need(db.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'native-catalog-integrity')
            schema = db.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
            names = {row[1] for row in schema if row[0] == 'table'}
            need({'comics', 'issues', 'annuals', 'ddl_info', 'snatched'} <= names and len(names) >= 10, 'genuine-native-full-schema')
            need(all(db.execute('SELECT count(*) FROM ' + name).fetchone()[0] == 0 for name in ('comics', 'issues', 'annuals')), 'native-not-empty')
        self.roles();self.installed_sources(); put(self.output / (prefix + '-done.json'), dict(schema=schema, publication=health['publication']))
        return dict(token=token, schema=schema)

    def reader_state(self, native_catalog=None):
        if native_catalog is None:
            need(not os.listdir(self.library) and not os.listdir(self.retention), 'reader-seed-exclusive-empty')
            fixture.build(self.output / 'archive-inputs')
            series = self.library / 'Fixture Series'; series.mkdir(mode=0o700)
            expected = {}
            for name, source in (('001-target.cbz', 'target.cbz'), ('002-unrelated.cbz', 'unrelated.cbz')):
                raw = (self.output / 'archive-inputs' / 'seed' / source).read_bytes()
                path = series / name; fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, 'wb') as stream:stream.write(raw); stream.flush(); os.fsync(stream.fileno())
                os.chown(path, 1000, 1000)
                with zipfile.ZipFile(path) as archive:
                    expected[str(path)] = [hashlib.sha256(archive.read(n)).hexdigest() for n in sorted(archive.namelist()) if n.endswith('.png')]
            os.chown(series, 1000, 1000); backup.sync(series); backup.sync(self.library)
        else:
            files=native_catalog['result']['files']
            need(len(files)==2 and {v['role'] for v in files}=={'target','unrelated'},'native-reader-original-files')
            expected={v['path']:v['pages'] for v in files}
            for value in files:
                path=Path(value['path']);need(self.library in path.parents and p.nine(os.lstat(path))==value['signature9'] and hashlib.sha256(path.read_bytes()).hexdigest()==value['sha256'],'native-reader-original-generation')
            actual=[]
            for folder,dirs,names in os.walk(self.library,followlinks=False):
                need(all(not (Path(folder)/n).is_symlink() for n in dirs+names),'native-reader-no-links')
                actual.extend(str(Path(folder)/n)for n in names)
            need(set(actual)==set(expected) and not os.listdir(self.retention),'native-reader-exact-census')
        library = self.step('reader-create-library', lambda: self.http('reader', 'create-library', dict(name='Archive bootstrap ' + self.plan['nonce'][:16], root=str(self.library))))
        identifier(library.get('id')); need(library.get('root') == str(self.library), 'actual-created-library')
        self.step('reader-scan', lambda: self.http('reader', 'scan', dict(library=library['id'])))
        books = None
        while self.seconds():
            response = self.http('reader', 'books')
            need(type(response) is dict and type(response.get('content')) is list and response.get('totalElements') == len(response['content']) <= 1000, 'complete-reader-book-census')
            current = response['content']
            if len(current) == len(expected) and all(v.get('media', {}).get('status') == 'READY' for v in current):
                if books == current:break
                books = current
            time.sleep(min(0.2, self.seconds()))
        need(books is not None and len({v['id'] for v in books}) == len(expected), 'reader-index-not-complete')
        records = []
        for book in books:
            identifier(book['id']); path = urllib.parse.unquote(urllib.parse.urlsplit(book['url']).path)
            need(path in expected and book['libraryId'] == library['id'], 'only-created-fixture-books')
            pages = self.http('reader', 'pages', dict(book=book['id']))
            need(type(pages) is list and [v.get('number') for v in pages] == list(range(1, len(expected[path]) + 1)), 'actual-page-order')
            hashes = [self.http('reader', 'page', dict(book=book['id'], page=n))['sha256'] for n in range(1, len(pages) + 1)]
            need(hashes == expected[path], 'actual-page-content')
            records.append(dict(path=path, book=self.http('reader', 'book', dict(book=book['id'])), pages=pages, hashes=hashes))
        target_path = None if native_catalog is None else next(v['path'] for v in native_catalog['result']['files'] if v['role']=='target')
        target = next(v for v in records if v['path'].endswith('/001-target.cbz')) if target_path is None else next(v for v in records if v['path']==target_path)
        self.step('reader-progress', lambda: self.http('reader', 'set-progress', dict(book=target['book']['id'])))
        after = self.http('reader', 'book', dict(book=target['book']['id']))
        need(after.get('readProgress', {}).get('page') == 1 and after['readProgress'].get('completed') is False, 'actual-user-progress')
        target['book'] = after
        unrelated = next(v for v in records if v is not target)
        need(self.http('reader', 'book', dict(book=unrelated['book']['id'])) == unrelated['book'], 'unrelated-reader-book-changed')
        active.checked_library_documents(dict(user=self.http('reader', 'principal'), libraries=self.http('reader', 'libraries'), repeated_libraries=self.http('reader', 'libraries')))
        return dict(library=library, books=records)

    def execute(self, *, native_catalog_helper=None):
        try:
            self.roles()
            observed=self.installed_sources();native_original=self.native_original()
            active.checked_library_user(self.http('reader', 'principal'))
            need(self.http('reader', 'libraries') == [] and self.http('reader', 'books').get('totalElements') == 0, 'reader-must-be-empty')
            self.output.mkdir(mode=0o700); backup.sync(self.root)
            native = self.native(); catalog = None
            if native_catalog_helper is not None:
                from genuine_native_catalog import Catalog
                catalog = Catalog(self,native_catalog_helper,native).execute()
            reader = self.reader_state(catalog); self.roles()
            result = dict(version=1, kind='disposable-application-bootstrap-observation', nonce=self.plan['nonce'],
                          native=native, reader=reader, native_original=native_original, source_parity=observed,
                          native_catalog_processing_verified=False, task_quiescence_verified=False,
                          installed_factories_verified=False, actual_nfs_verified=False,
                          publication_acceptance=False, mutation_authority=False, automatic_replay=False)
            if catalog is not None:
                result['native_catalog_processing']=catalog['ref']
                result['native_catalog_processing_observed']=True
                result['ordinary_ack_verified']=False
            return put(self.output / 'bootstrap.json', result)
        except Exception:
            try:
                if self.output.is_dir():put(self.output / 'held.json', dict(kind='bootstrap-held-evidence-retained', automatic_replay=False, reader_resume_authority=False))
            except Exception:pass  # Preserve the original refusal and all unknown artifacts.
            raise
        finally:p.close_common_root(self.geometry)


def run(plan_ref, source_sha256, *, activate=False, native_catalog_helper=None):
    need(activate is True, 'explicit-bootstrap-activation-required')
    need(os.geteuid() == 0 and p.digest(source_sha256) and hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == source_sha256, 'accepted-bootstrap-source-root')
    return Bootstrap(p.decode(p.read(plan_ref)), Docker()).execute(native_catalog_helper=native_catalog_helper)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--activate', action='store_true')
    for name in ('plan', 'plan-sha256', 'source-sha256'):parser.add_argument('--' + name)
    args = parser.parse_args(argv)
    try:
        need(args.activate and all((args.plan, args.plan_sha256, args.source_sha256)), 'explicit-bootstrap-activation-required')
        ref = dict(path=args.plan, sha256=args.plan_sha256, signature9=p.nine(os.lstat(args.plan)))
        run(ref, args.source_sha256, activate=args.activate)
        print('application-bootstrap-produced; connected-runtime-unproved')
        return 0
    except Exception:
        print('application-bootstrap-held; no-replay-or-runtime-grant')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
