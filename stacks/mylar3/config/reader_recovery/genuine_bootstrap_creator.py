"""Explicit UID1000 disposable creator; unknown outcomes retain all resources.

Three accepted original image metadata inputs, a reviewed DATA precondition and
an existing admitted NFS parent are required. No default Docker fallback,
production role adoption, worker start, cleanup, ACK or factory grant exists.
Komga enrollment follows tag 1.28.1:
https://github.com/gotson/komga/blob/1.28.1/komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/ClaimController.kt
https://github.com/gotson/komga/blob/1.28.1/komga/src/main/kotlin/org/gotson/komga/interfaces/api/rest/UserController.kt
The original actors exclusively own these disposable names; no independent
process may mutate their files, containers or network during the operation.
"""
import argparse
import ast
import base64
import configparser
import copy
import hashlib
import io
import os
from pathlib import Path
import re
import secrets
import selectors
import stat
import subprocess
import sys
import tarfile
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import genuine_application_bootstrap as b
import genuine_bootstrap_http as http

p = b.p
need = p.need
SOURCES = {'creator': 'genuine_bootstrap_creator.py', 'bootstrap': 'genuine_application_bootstrap.py',
           'http': 'genuine_bootstrap_http.py', 'probe': 'comic_native_process_probe.py',
           'scope': 'publication_native_configured_scope.py', 'catalog': 'genuine_native_catalog.py',
           'catalog_helper': 'genuine_native_catalog_helper.py'}
PREFIX = ('pkexec', '/usr/bin/docker', '--host', 'unix:///run/docker.sock')
JAR = '/app/application.jar'
# Original public dependency facts: actual 1.28.1 application.jar, not a tag guess.
JAR_SHA = 'f76aff7d31f2735ed902e3a004540e869568be42dc099a5560d72fd3d8f2c0fe'
LIMIT = 16 * 1024**2
ENROLL_PROGRAM = r'''import base64,json,os,re,sys,urllib.request
assert sys.flags.isolated and sys.dont_write_bytecode and os.geteuid()==1000
assert len(sys.argv)==4 and sys.argv[1]=='--disposable-reader-claim-v1'
v=json.load(sys.stdin);assert set(v)=={'nonce','cid','operation','email','password','seconds'}
assert sys.argv[2:]==[v['nonce'],v['cid']] and all(re.fullmatch('[a-f0-9]{64}',v[k])for k in ('nonce','cid'))
assert v['email']=='bootstrap-'+v['nonce'][:48]+'@example.invalid' and re.fullmatch('[a-f0-9]{64}',v['password'])
assert type(v['seconds'])is int and 1<=v['seconds']<=30
base='http://reader-'+v['nonce'][:16]+':25600';headers={};data=None
if v['operation']=='status':route='/api/v1/claim';method='GET'
elif v['operation']=='claim':
 route='/api/v1/claim';method='POST';data=b'';headers={'X-Komga-Email':v['email'],'X-Komga-Password':v['password']}
elif v['operation']=='key':
 route='/api/v2/users/me/api-keys';method='POST';data=json.dumps({'comment':'bootstrap-'+v['nonce']}).encode()
 headers={'Content-Type':'application/json','Authorization':'Basic '+base64.b64encode((v['email']+':'+v['password']).encode()).decode()}
else:raise ValueError('operation')
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**k):raise ValueError('redirect')
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
with opener.open(urllib.request.Request(base+route,data=data,method=method,headers=headers),timeout=v['seconds'])as response:
 raw=response.read(1024**2+1);assert len(raw)<=1024**2
value=json.loads(raw);sys.stdout.write(json.dumps(value))
'''


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def config_sections(raw, names):
    """Read only owning literal section names; never import Config/read providers."""
    tree = ast.parse(raw, feature_version=(3, 10))
    nodes = [n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '_CONFIG_DEFINITIONS' for t in n.targets)]
    need(len(nodes) == 1, 'original-config-definitions')
    definitions = nodes[0].value
    if isinstance(definitions, ast.Call):
        need(isinstance(definitions.func, ast.Name) and definitions.func.id == 'OrderedDict'
             and len(definitions.args) == 1 and not definitions.keywords, 'original-config-definitions')
        definitions = definitions.args[0]
    need(isinstance(definitions, ast.Dict) and all(key is not None for key in definitions.keys), 'original-config-definitions')
    result = {}
    for key, value in zip(definitions.keys, definitions.values):
        if isinstance(key, ast.Constant) and key.value in names:
            need(isinstance(value, (ast.Tuple, ast.List)) and len(value.elts) >= 2
                 and isinstance(value.elts[1], ast.Constant) and type(value.elts[1].value) is str, 'literal-config-section')
            need(key.value not in result, 'duplicate-config-definition')
            result[key.value] = value.elts[1].value
    need(set(result) == set(names), 'required-config-definitions')
    return result


class Driver:
    """Only PurposeEngine calls this fixed existing Polkit client prefix."""
    def _spawn(self, args, data):
        """Default transport remains one existing Polkit client per call."""
        return subprocess.Popen([*PREFIX,*args],stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})

    def _kill_process(self, process):
        """Transport owns only the exact Popen client; daemon outcome stays unknown."""
        process.kill()

    def docker(self, args, seconds, data=None):
        need(type(args)is list and type(seconds)is int and 1<=seconds<=30 and (data is None or type(data)is bytes and len(data)<=8*1024**2),'bounded-engine-request')
        process=None;streams=[];deadline=time.monotonic()+seconds;output={};pending=memoryview(data or b'')
        try:
            process=self._spawn(args, data)
            with selectors.DefaultSelector()as poll:
                for stream in (process.stdout,process.stderr):
                    streams.append(stream);output[stream]=bytearray();os.set_blocking(stream.fileno(),False);poll.register(stream,selectors.EVENT_READ)
                if process.stdin is not None:
                    streams.append(process.stdin)
                    if pending:os.set_blocking(process.stdin.fileno(),False);poll.register(process.stdin,selectors.EVENT_WRITE)
                    else:process.stdin.close()
                while poll.get_map():
                    left=deadline-time.monotonic();need(left>0,'creator-engine-outcome-unknown-no-replay')
                    for key,events in poll.select(min(0.2,left)):
                        stream=key.fileobj
                        if events & selectors.EVENT_WRITE:
                            count=os.write(stream.fileno(),pending[:65536]);need(count>0,'engine-input-short');pending=pending[count:]
                            if not pending:poll.unregister(stream);stream.close()
                        else:
                            block=os.read(stream.fileno(),min(65536,LIMIT+1-len(output[stream])))
                            if not block:poll.unregister(stream)
                            else:output[stream].extend(block);need(len(output[stream])<=LIMIT,'creator-engine-output-bound')
            need(process.wait(timeout=max(0.001,deadline-time.monotonic()))==0,'creator-engine-held-no-replay')
            return bytes(output[process.stdout])
        except BaseException as error:
            failure = (p.Held('creator-engine-outcome-unknown-no-replay')
                       if isinstance(error, (OSError, subprocess.TimeoutExpired)) else error)
            # Private diagnostic only: never retain input/argv or print pipe data.
            # A missing return code is uncertainty, not evidence of no effects.
            failure.creator_engine_failure = dict(
                returncode=None if process is None else process.poll(),
                stdout_base64=base64.b64encode(bytes(output.get(None if process is None else process.stdout, b''))[:LIMIT]).decode('ascii'),
                stderr_base64=base64.b64encode(bytes(output.get(None if process is None else process.stderr, b''))[:LIMIT]).decode('ascii'),
                stdout_truncated=process is not None and len(output.get(process.stdout, b'')) > LIMIT,
                stderr_truncated=process is not None and len(output.get(process.stderr, b'')) > LIMIT,
                stream_byte_limit=LIMIT)
            if failure is error:raise
            raise failure from None
        finally:
            primary=sys.exc_info()[1]
            if process is not None and process.poll()is None:
                try:self._kill_process(process)
                except OSError:pass  # A privileged client may outlive its unknown reply.
                except BaseException as secondary:
                    if primary is None:raise
                    primary.creator_client_cleanup_failure=type(secondary).__name__
                try:process.wait(timeout=0.1)
                except subprocess.TimeoutExpired:pass
            for stream in streams:stream.close()

    def mount(self, path, seconds):
        return b.Docker.mount(self, path, seconds)


def copied_file(raw, expected):
    need(len(raw) <= LIMIT, 'source-copy-bound')
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        members = archive.getmembers()
        need(len(members) == 1 and members[0].isfile() and not members[0].issym()
             and members[0].name == Path(expected['path']).name and members[0].size <= 4 * 1024**2, 'exact-source-copy')
        content = archive.extractfile(members[0]).read(4 * 1024**2 + 1)
    need(digest(content) == expected['sha256'], 'original-image-file-hash')
    return content


class PurposeEngine:
    """Finite original creator state, then the unchanged Bootstrap engine interface."""
    def __init__(self, owner, driver):
        self.owner, self.driver = owner, driver
        self.ids = {}; self.network = None; self.started = set(); self.counts = {}; self.connected = False
        self.poisoned = False; self.created_static = {}; self.runtime_static = {}

    def call(self, name, maximum, args, data=None, *, readonly=False):
        need(not self.poisoned, 'creator-unknown-outcome-held')
        self.owner.check()
        count = self.counts.get(name, 0); need(count < maximum, 'creator-call-budget')
        self.counts[name] = count + 1
        self.owner.note('intent', name)
        try:
            raw = self.driver.docker(args, self.owner.seconds(), data)
            self.owner.note('done', name, digest(raw))
            self.owner.check()
            return raw
        except BaseException as error:
            self.poisoned = not readonly
            diagnostic = getattr(error, 'creator_engine_failure', None)
            if diagnostic is not None and self.owner.journal is not None:
                try:
                    path = self.owner.journal/'engine-failure.private.json'
                    if not os.path.lexists(path):
                        b.put(path, dict(kind='creator-first-engine-failure', operation=name,
                            diagnostic=diagnostic, automatic_replay=False, cleanup=False))
                except BaseException as secondary:
                    # Losing diagnostic storage must not hide the actual refusal.
                    error.creator_diagnostic_failure = type(secondary).__name__
            raise

    def image(self, role):
        row = self.owner.document['images'][role]
        actual = p.decode(self.call('image-' + role, 1, ['image', 'inspect', row['id']], readonly=True))
        need(actual == self.owner.metadata[role], 'original-image-metadata')

    def create_network(self):
        need(self.network is None and not self.ids, 'network-create-once')
        args = ['network', 'create', '--internal', '--driver', 'bridge', *self.owner.labels(), self.owner.name('network')]
        raw = self.call('network-create', 1, args).decode().strip()
        need(p.digest(raw), 'original-created-network-id'); self.network = raw
        b.put(self.owner.journal/'original-network.json',dict(id=raw,nonce=self.owner.nonce))

    def create(self, role):
        need(self.network is not None and role not in self.ids and not self.started, 'three-role-create-before-start')
        args = ['create', '--pull', 'never', '--name', self.owner.name(role), *self.owner.labels(),
                '--security-opt', 'no-new-privileges', '--restart', 'no', '--pids-limit', '512']
        args += ['--network', 'none' if role == 'worker' else self.network]
        if role == 'reader':args += ['--network-alias', self.owner.reader_host, '--user', '1000:1000', '--cap-drop', 'ALL', '--env', 'SERVER_PORT=25600']
        if role == 'worker':args += ['--user', '1000:1000', '--cap-drop', 'ALL']
        if role == 'native':args += ['--env', 'PUID=1000', '--env', 'PGID=1000']
        for source, target, write in self.owner.mounts(role):
            need(all(',' not in str(x) for x in (source, target)), 'mount-delimiter')
            args += ['--mount', 'type=bind,src=' + str(source) + ',dst=' + target + ('' if write else ',readonly')]
        args += [self.owner.document['images'][role]['id']]
        cid = self.call('create-' + role, 1, args).decode().strip()
        need(p.digest(cid) and cid not in self.ids.values(), 'original-created-role-id'); self.ids[role] = cid
        b.put(self.owner.journal/('original-'+role+'.json'),dict(id=cid,image=self.owner.document['images'][role]['id'],nonce=self.owner.nonce))
        self.inspect(role, running=False)

    def inspect(self, role, *, running):
        cid = self.ids[role]; raw = self.call('inspect-' + role, 1024, ['inspect', cid], readonly=True); rows = p.decode(raw)
        need(type(rows) is list and len(rows) == 1, 'one-created-role')
        row = rows[0]
        # First observations are private diagnostics, never admission substitutes.
        try:
            path = self.owner.journal/('first-'+('running' if running else 'created')+'-'+role+'.private.json')
            if not os.path.lexists(path):
                b.put(path, dict(kind='creator-first-profile-diagnostic', role=role,
                                phase='running' if running else 'created',
                                response_sha256=digest(raw), profile=row,
                                automatic_replay=False, cleanup=False))
        except BaseException:pass
        self.owner.profile(role, row, running)
        projected=p.static(row)
        fixed={k:v for k,v in projected.items()if k!='NetworkSettings'}
        if role in self.created_static:
            original=self.created_static[role]; compared=copy.deepcopy(fixed)
            old_host=original['HostConfig']; new_host=fixed['HostConfig']
            if 'OomKillDisable' in old_host:
                need('OomKillDisable' in new_host,'created-original-static-drift')
                before,after=old_host['OomKillDisable'],new_host['OomKillDisable']
                transition=running and before is False and after is None
                need((type(before)is type(after) and before==after) or transition,'created-original-static-drift')
                if transition:compared['HostConfig']['OomKillDisable']=False
            need(compared==original,'created-original-static-drift')
        else:self.created_static[role]=copy.deepcopy(fixed)
        if running:
            if role in self.runtime_static:need(projected==self.runtime_static[role],'created-runtime-static-drift')
            else:self.runtime_static[role]=copy.deepcopy(projected)
        return row

    def copy(self, path, checksum):
        need(not self.started and 'native' in self.ids, 'source-copy-before-start')
        return copied_file(self.call('copy-' + path, 1, ['cp', self.ids['native'] + ':' + path, '-'], readonly=True), dict(path=path, sha256=checksum))

    def start(self, role):
        need(set(self.ids) == {'native', 'reader', 'worker'} and role in ('native', 'reader') and role not in self.started, 'creator-start-only-two-once')
        self.inspect(role, running=False)
        raw = self.call('start-' + role, 1, ['start', self.ids[role]]).decode().strip()
        need(raw == self.ids[role], 'original-start-response'); self.started.add(role)
        self.inspect(role, running=True)

    def enroll(self, operation, password):
        need(self.started == {'native', 'reader'} and not self.connected, 'original-enrollment-phase')
        for role in ('native', 'reader'):self.inspect(role, running=True)
        packet = dict(nonce=self.owner.nonce, cid=self.ids['native'], operation=operation,
                      email='bootstrap-' + self.owner.nonce[:48] + '@example.invalid', password=password, seconds=self.owner.seconds())
        args = ['exec', '--interactive', '--user', '1000:1000', self.ids['native'], '/lsiopy/bin/python3', '-I', '-B', '-c', ENROLL_PROGRAM,
                '--disposable-reader-claim-v1', self.owner.nonce, self.ids['native']]
        return p.decode(self.call('enroll-' + operation, 128 if operation == 'status' else 1, args, p.encode(packet), readonly=operation=='status'))

    def mount(self, path, seconds):
        need(Path(path) in (self.owner.nfs_parent, self.owner.common, self.owner.library, self.owner.retention), 'finite-mount-selector')
        self.owner.seconds()
        return self.driver.mount(path, min(seconds, self.owner.seconds()))

    def run(self, args, seconds, data=None):
        """Called by original Bootstrap/Catalog only after original plan capture."""
        need(self.connected and type(args) is list and 0 < seconds <= 30, 'creator-connected-engine')
        if args[0] == 'inspect':
            need(len(args) == 2 and args[1] in self.ids.values() and data is None, 'original-role-selector')
            return self.call('connected-inspect', 4096, args, readonly=True)
        if args[:2] == ['network', 'inspect']:
            need(args == ['network', 'inspect', self.network] and data is None, 'original-network-selector')
            return self.call('connected-network', 2048, args, readonly=True)
        if args[0] == 'restart':
            need(args == ['restart', '--timeout', '30', self.ids['native']] and data is None, 'only-original-native-restart')
            return self.call('connected-restart', 1, args)
        if self.owner.document['version'] in (2,3) and args==['exec','--user','1000:1000',self.ids['reader'],'sha256sum',JAR]:
            need(data is None,'queue-reader-jar-no-input')
            return self.call('queue-reader-original-jar',2,args,readonly=True)
        need(args[0] == 'exec' and args[:5] == ['exec', '--interactive', '--user', '1000:1000', self.ids['native']]
             and args[5:9] == ['/lsiopy/bin/python3', '-I', '-B', '-c'], 'fixed-native-exec')
        program = args[9]; sources = self.owner.raw
        if program == b.IMAGE_PROGRAM:
            need(len(args) == 10 and p.decode(data) == sorted(self.owner.sdk), 'fixed-installed-map-request')
            name, maximum = 'installed-map', 256
        elif program == sources['probe'].decode():
            value = p.decode(data)
            need(len(args) == 10 and value == dict(version=1, nonce=self.owner.nonce, source_sha256=self.owner.document['sources']['probe']['sha256'],
                seconds=value.get('seconds'), module_pins={'/app/mylar3/mylar/' + n:self.owner.sdk[n] for n in ('worker_health.py','native_writers.py')}, scope_source=sources['scope'].decode())
                and type(value['seconds']) is int and 1 <= value['seconds'] <= 30, 'fixed-native-probe-request')
            name, maximum = 'native-probe', 256
        elif program == sources['http'].decode():
            need(args[10:] == ['--owning-disposable-bootstrap-http-v1', self.owner.nonce, self.ids['native']], 'fixed-http-invocation')
            value = p.decode(data); http.request(value)
            need(value['base'] == (self.owner.native_base if value['kind'] == 'native' else 'http://' + self.owner.reader_host + ':25600')
                 and value['key'] == (self.owner.native_key if value['kind'] == 'native' else self.owner.reader_key), 'original-http-origin-credentials')
            limits = {'health':64,'status':2,'prepare-fresh':1,'initialize-bootstrap':1,'force-process-fixture':2,
                      'principal':8,'libraries':16,'books':40,'create-library':1,'scan':1,'book':16,'pages':4,'page':8,'set-progress':1}
            name, maximum = 'http-' + value['kind'] + '-' + value['operation'], limits[value['operation']]
        elif program == sources['catalog_helper'].decode():
            need(args[10:] == ['--disposable-native-catalog-v1', self.owner.nonce, self.ids['native']], 'fixed-catalog-invocation')
            value = p.decode(data)
            need(value.get('nonce') == self.owner.nonce and value.get('cid') == self.ids['native'] and value.get('root') == self.owner.child_data
                 and value.get('library') == str(self.owner.library) and value.get('sdk') == self.owner.sdk and value.get('action') in ('seed','observe'), 'fixed-catalog-scope')
            name, maximum = 'catalog-' + value['action'], 1 if value['action'] == 'seed' else 64
        elif self.owner.document['version'] in (2,3) and program==sources['reader_queue'].decode():
            from genuine_reader_quiescence import request as queue_request
            need(args[10:]==['--disposable-reader-queue-v1',self.owner.nonce,self.ids['native']],'fixed-queue-invocation')
            value=p.decode(data);queue_request(value)
            need(value['nonce']==self.owner.nonce and value['native_cid']==self.ids['native']
                 and value['base']=='http://'+self.owner.reader_host+':25600' and value['key']==self.owner.reader_key,
                 'original-queue-origin-credentials')
            name,maximum='reader-task-empty',1
        else:raise p.Held('undeclared-creator-program')
        return self.call(name, maximum, args, data, readonly=name not in {'http-native-prepare-fresh','http-native-initialize-bootstrap','http-native-force-process-fixture','http-reader-create-library','http-reader-scan','http-reader-set-progress','catalog-seed'})


class Creator:
    def __init__(self, document, *, driver=None):
        need(os.geteuid() == os.getegid() == 1000, 'creator-actual-uid1000-required')
        need(type(document) is dict and set(document) == {'version','kind','nonce','observed','seconds','state_parent','nfs_parent','nfs_mount','images','native_sdk','data_contract','sources'}, 'creator-schema')
        need(type(document['version']) is int and document['version'] in (1,2,3) and document['kind'] == 'approved-disposable-three-role-creator'
             and p.digest(document['nonce']) and type(document['observed']) is int and 0 <= time.time()-document['observed'] <= 120
             and type(document['seconds']) is int and 30 <= document['seconds'] <= 900, 'creator-original-deadline')
        self.document = copy.deepcopy(document); self.nonce = document['nonce']; self.end = time.monotonic()+document['seconds']
        self.raw = {}
        source_names=dict(SOURCES)
        if document['version'] in (2,3):source_names['reader_queue']='genuine_reader_quiescence.py'
        need(set(document['sources']) == set(source_names), 'creator-source-closure')
        for name, filename in source_names.items():
            ref = document['sources'][name]; need(Path(ref['path']) == HERE/filename, 'creator-source-path')
            self.raw[name] = p.read(ref, private=False)
        self.state_parent = b.directory(document['state_parent']); self.nfs_parent = (b.searchable_directory if document['version']==3 else b.directory)(document['nfs_parent'])
        if document['version']==3:need(not os.listdir(self.nfs_parent),'creator-empty-searchable-parent')
        need(self.state_parent != self.nfs_parent and self.state_parent not in self.nfs_parent.parents and self.nfs_parent not in self.state_parent.parents, 'disjoint-creator-parents')
        self.root = self.state_parent/('archive-bootstrap-'+self.nonce); self.common = self.nfs_parent/('archive-publication-'+self.nonce)
        self.library = self.common/'L'; self.retention = self.common/'R'; self.reader_host = 'reader-'+self.nonce[:16]
        need(not os.path.lexists(self.root) and not os.path.lexists(self.common), 'creator-no-adoption-or-replay')
        self.sdk = p.decode(p.read(document['native_sdk'])); need(type(self.sdk)is dict and b.REQUIRED_SDK | {'config.py','__init__.py','db.py'} <= set(self.sdk) and len(self.sdk)<=512 and all(re.fullmatch('[A-Za-z_][A-Za-z0-9_]*[.]py',n)and p.digest(v)for n,v in self.sdk.items()), 'creator-complete-sdk')
        self.contract = p.decode(p.read(document['data_contract']))
        need(type(self.contract) is dict and set(self.contract) == {'version','kind','image','relative','argv','service_path','service_sha256'}
             and type(self.contract['version']) is int and self.contract['version'] == 1 and self.contract['kind'] == 'reviewed-image-data-precondition'
             and re.fullmatch(r'[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+){0,2}', self.contract['relative'])
             and re.fullmatch(r'/etc/s6-overlay/s6-rc.d/[A-Za-z0-9_-]+/run', self.contract['service_path']) and p.digest(self.contract['service_sha256']), 'explicit-reviewed-data-precondition')
        self.data = self.root/'native'/self.contract['relative']; self.child_data = '/config/'+self.contract['relative']
        from publication_native_configured_scope import data_from_argv
        need(data_from_argv(self.contract['argv']) == self.child_data and '--port' not in self.contract['argv'] and '-p' not in self.contract['argv'], 'reviewed-data-argv')
        need(set(document['images']) == {'native','reader','worker'}, 'three-accepted-image-inputs')
        self.metadata = {}
        for role, row in document['images'].items():
            need(set(row) == {'id','metadata'} and re.fullmatch('sha256:[a-f0-9]{64}',row['id']), 'accepted-image-id')
            value = p.decode(p.read(row['metadata'])); need(type(value) is list and len(value) == 1 and value[0]['Id'] == row['id']
                and value[0].get('Os') == 'linux' and value[0].get('Architecture') == 'amd64', 'accepted-original-image-metadata')
            self.metadata[role] = value
        need(self.contract['image'] == document['images']['native']['id'], 'data-precondition-image')
        self.engine = PurposeEngine(self, driver or Driver()); self.journal = None; self.serial = 0; self.geometry = None; self.closed=False
        observed = self.engine.mount(self.nfs_parent, self.seconds())
        need(b.nfs_mount(observed,self.nfs_parent) == document['nfs_mount'] and os.lstat(self.state_parent).st_dev != os.lstat(self.nfs_parent).st_dev, 'original-nfs-parent-local-state')
        self.native_key = secrets.token_hex(16); self.reader_key = None; self.native_base = 'http://127.0.0.1:8090'

    def seconds(self):
        remaining = self.end-time.monotonic(); need(remaining > 0, 'creator-deadline')
        return max(1,min(30,int(remaining)))

    def check(self):
        need(not self.closed,'creator-lifetime-ended')
        self.seconds()
        for ref in self.document['sources'].values():p.read(ref,private=False)
        p.read(self.document['native_sdk']); p.read(self.document['data_contract'])
        for row in self.document['images'].values():p.read(row['metadata'])
        if self.geometry is not None:p.check_common_root(self.geometry)

    def note(self, phase, name, output=None):
        if self.journal is not None:
            self.serial += 1
            b.put(self.journal/(str(self.serial).zfill(4)+'-'+phase+'.json'), dict(kind=name,phase=phase,output_sha256=output,automatic_replay=False))

    def name(self, role):return 'archive-bootstrap-'+self.nonce[:16]+'-'+role
    def labels(self):return ['--label',b.LABEL+'='+self.nonce,'--label',b.PURPOSE+'=genuine-archive-fixture']
    def mounts(self, role):
        return {'native':[(self.root/'native','/config',True),(self.library,str(self.library),True)],
                'reader':[(self.root/'reader','/config',True),(self.library,str(self.library),False)],
                'worker':[(self.root/'worker','/state',True),(self.data,'/mylar',False),(self.library,'/data/comics',True)]}[role]

    def profile(self, role, row, running):
        host = row['HostConfig']; state = row['State']
        need(row['Id'] == self.engine.ids[role] and row['Image'] == self.document['images'][role]['id'] and row['Name'] == '/'+self.name(role)
             and row['Config'].get('Labels',{}).get(b.LABEL) == self.nonce and row['Config']['Labels'].get(b.PURPOSE) == 'genuine-archive-fixture', 'created-role-original')
        need(not host.get('Privileged') and not host.get('Devices') and not host.get('DeviceRequests') and not host.get('CapAdd')
             and not host.get('PortBindings') and host.get('NetworkMode') == ('none' if role == 'worker' else self.engine.network)
             and host.get('PidMode','') != 'host' and host.get('IpcMode','') != 'host'
             and all(not v for v in row['NetworkSettings'].get('Ports',{}).values()), 'created-role-isolation')
        need(all(m['Type']=='bind' for m in row['Mounts']) and sorted((m['Source'],m['Destination'],m['RW'])for m in row['Mounts']) == sorted((str(a),c,w)for a,c,w in self.mounts(role)), 'created-role-exact-mounts')
        need(state['Status'] == ('running' if running else 'created') and state['Running'] is running and (state['Pid'] > 0 if running else state['Pid'] == 0)
             and all(not state.get(k)for k in ('Paused','Restarting','Dead','OOMKilled')), 'created-role-state')
        if running:
            networks = row['NetworkSettings']['Networks']; need(len(networks)==1 and next(iter(networks.values()))['NetworkID']==self.engine.network, 'created-role-private-network')
            if role=='reader':need(self.reader_host in (next(iter(networks.values())).get('Aliases')or []), 'created-reader-alias')

    def directories(self):
        self.check(); b.directory(self.document['state_parent']); (b.searchable_directory if self.document['version']==3 else b.directory)(self.document['nfs_parent'])
        if self.document['version']==3:need(not os.listdir(self.nfs_parent),'creator-empty-searchable-parent')
        need(self.engine.mount(self.nfs_parent,self.seconds())==self.document['nfs_mount'],'nfs-parent-mount-changed')
        self.root.mkdir(mode=0o700)
        self.journal=self.root/'creator';self.journal.mkdir(mode=0o700)
        self.common.mkdir(mode=0o700)
        if self.document['version']==3:
            # Only this just-created directory is changed, never an existing path.
            fd=os.open(self.common,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            try:
                original=p.five(os.fstat(fd));need(original==p.five(os.lstat(self.common)) and original[3:]==[1000,1000] and stat.S_IMODE(original[2])==0o700 and not os.listdir(fd),'creator-fresh-searchable-common')
                os.fchmod(fd,0o711)
                need(p.five(os.fstat(fd))==p.five(os.lstat(self.common)) and stat.S_IMODE(os.fstat(fd).st_mode)==0o711,'creator-searchable-common-mode')
            finally:os.close(fd)
        for path in (self.root/'native',self.root/'reader',self.root/'worker',self.library,self.retention):path.mkdir(mode=0o700)
        current=self.root/'native'
        for part in Path(self.contract['relative']).parts:
            current/=part;current.mkdir(mode=0o700)
        self.geometry = p.admit_common_root(dict(version=2 if self.document['version']==3 else 1,kind='searchable-common-root-nfs' if self.document['version']==3 else 'private-common-root-nfs',common_root=self.directory_ref(self.common),library=self.directory_ref(self.library),retention=self.directory_ref(self.retention)),[dict(host=str(self.common),child=str(self.common),write=True)],str(self.library),str(self.retention),[str(self.root)])

    @staticmethod
    def directory_ref(path):return dict(path=str(path),signature9=p.nine(os.lstat(path)))

    def ini(self, source):
        child = self.child_data
        values = dict(API_ENABLED=1,API_KEY=self.native_key,HTTP_PORT=8090,HTTP_ROOT='',ENABLE_HTTPS=0,
                      DESTINATION_DIR=str(self.library),CACHE_DIR=child+'/cache',DDL_LOCATION=child+'/downloads',CHECK_FOLDER=child+'/downloads',
                      LOG_DIR=child+'/logs',SECURE_DIR=child+'/.secure',BACKUP_LOCATION=child+'/backup',ENABLE_META=False,RENAME_FILES=False,
                      ENABLE_PRE_SCRIPTS=False,ENABLE_EXTRA_SCRIPTS=False,FILE_OPTS='move',ENFORCE_PERMS=True,CHMOD_FILE='0600',CHMOD_DIR='0700',
                      POST_PROCESSING=True,ENABLE_CHECK_FOLDER=False,ENABLE_TORRENTS=False)
        sections = config_sections(source, values); cfg = configparser.ConfigParser(interpolation=None)
        for key,value in values.items():
            section=sections[key]
            if not cfg.has_section(section):cfg.add_section(section)
            cfg.set(section,key.lower(),str(value))
        for leaf in ('cache','downloads','logs','.secure','backup'):(self.data/leaf).mkdir(mode=0o700)
        target=self.data/'config.ini'
        with os.fdopen(os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'w')as stream:cfg.write(stream);stream.flush();os.fsync(stream.fileno())
        b.backup.sync(self.data)

    def virgin_process(self):
        ref=self.document['sources']['probe']; request=dict(version=1,nonce=self.nonce,source_sha256=ref['sha256'],seconds=self.seconds(),
            module_pins={'/app/mylar3/mylar/'+n:self.sdk[n] for n in ('worker_health.py','native_writers.py')},scope_source=self.raw['scope'].decode())
        args=['exec','--interactive','--user','1000:1000',self.engine.ids['native'],'/lsiopy/bin/python3','-I','-B','-c',self.raw['probe'].decode()]
        value=None
        for _ in range(30):
            request['seconds']=self.seconds()
            try:value=p.decode(self.engine.call('creator-virgin-probe',30,args,p.encode(request),readonly=True));break
            except p.Held:self.seconds();time.sleep(min(0.2,self.seconds()))
        ini=self.data/'config.ini';z=os.lstat(ini)
        need(type(value)is dict and value.get('version')==1 and value.get('nonce')==self.nonce and value.get('source_sha256')==ref['sha256']
             and value.get('process',{}).get('argv')==self.contract['argv'] and value.get('publication',{}).get('state')=='held'
             and value.get('config')==dict(path=self.child_data+'/config.ini',sha256=digest(ini.read_bytes()),signature9=p.nine(z)), 'actual-virgin-process-data-config')
        need(not any(os.path.lexists(self.data/n)for n in ('mylar.db','workflow.sqlite','media-writer','publication-fresh-v1.json')),'actual-native-still-virgin')
        return value

    def prepare(self):
        self.directories()
        for role in ('native','reader','worker'):self.engine.image(role)
        self.engine.create_network()
        for role in ('native','reader','worker'):self.engine.create(role)
        self.engine.copy(self.contract['service_path'],self.contract['service_sha256'])
        self.ini(self.engine.copy('/app/mylar3/mylar/config.py',self.sdk['config.py']))
        for role in ('native','reader'):self.engine.start(role)
        jar = self.engine.call('reader-original-jar',1,['exec','--user','1000:1000',self.engine.ids['reader'],'sha256sum',JAR],readonly=True).decode().split()
        need(jar == [JAR_SHA,JAR], 'accepted-reader-1-28-1-jar')
        # Retry only the read-only unclaimed readiness request. A mutation is
        # never retried, even if its reply was lost after the server committed.
        password=secrets.token_hex(32)
        b.put(self.journal/'reader-login.json',dict(email='bootstrap-'+self.nonce[:48]+'@example.invalid',password=password))
        self.virgin_process()
        status=None
        for _ in range(128):
            try:status=self.engine.enroll('status',password);break
            except p.Held:self.seconds();time.sleep(min(1,self.seconds()))
        need(status == {'isClaimed':False}, 'reader-already-claimed')
        claimed=self.engine.enroll('claim',password)
        b.active.checked_library_user(claimed)
        key=self.engine.enroll('key',password)
        need(type(key)is dict and key.get('userId')==claimed.get('id') and key.get('comment')=='bootstrap-'+self.nonce
             and type(key.get('key'))is str and key['key'] and key['key']!='******', 'original-reader-api-key')
        self.reader_key=key['key'];credentials=b.put(self.journal/'reader-key.json',dict(api_key=self.reader_key))
        roles={}
        for role in ('native','reader','worker'):
            row=self.engine.inspect(role,running=role!='worker')
            roles[role]=dict(id=row['Id'],image=row['Image'],profile=p.static(row),epoch={k:v for k,v in row['State'].items()if k!='Health'})
        net=p.decode(self.engine.call('network-capture',1,['network','inspect',self.engine.network],readonly=True));need(type(net)is list and len(net)==1,'original-network-capture')
        need(net[0].get('Internal')is True and net[0].get('Driver')=='bridge' and set(net[0].get('Containers',{}))=={self.engine.ids[k]for k in ('native','reader')},'only-two-original-network-members')
        self.check()
        ini=self.data/'config.ini';raw=ini.read_bytes();z=ini.lstat()
        need(stat.S_ISREG(z.st_mode)and z.st_uid==1000 and stat.S_IMODE(z.st_mode)==0o600 and z.st_nlink==1,'actual-virgin-config')
        need(not any(os.path.lexists(self.data/n)for n in ('mylar.db','workflow.sqlite','media-writer','publication-fresh-v1.json')),'actual-native-still-virgin')
        plan=dict(version=1,kind='approved-disposable-application-bootstrap',nonce=self.nonce,observed=int(time.time()),seconds=int(self.end-time.monotonic()),
                  state_root=self.directory_ref(self.root),geometry=dict(version=2 if self.document['version']==3 else 1,kind='searchable-common-root-nfs' if self.document['version']==3 else 'private-common-root-nfs',common_root=self.directory_ref(self.common),library=self.directory_ref(self.library),retention=self.directory_ref(self.retention)),
                  roles=roles,images={k:v['id']for k,v in self.document['images'].items()},network=dict(id=self.engine.network,profile=net[0]),
                  native_sdk=self.document['native_sdk'],native_ini=dict(path=str(ini),sha256=digest(raw),signature9=p.nine(z)),helper=self.document['sources']['http'],
                  native_probe=self.document['sources']['probe'],scope_source=self.document['sources']['scope'],nfs_mount=self.document['nfs_mount'],reader_credentials=credentials,reader_host=self.reader_host,reader_port=25600)
        b.plan(plan);self.plan=plan
        self.plan_ref=b.put(self.journal/'bootstrap-plan.json',plan)
        self.engine.connected=True
        return plan

    def failure_diagnostic(self, error):
        """Only fixed exception tokens and authenticated public Creator locations."""
        classes = (AssertionError, ValueError, TypeError, KeyError, RuntimeError,
                   OSError, TimeoutError, PermissionError, FileNotFoundError,
                   UnicodeError, SystemExit, KeyboardInterrupt)
        token = next((kind.__name__ for kind in classes if type(error) is kind),
                     'Held' if type(error) is p.Held else 'unclassified-exception')
        answer = dict(exception_class=token, source_frame=None)
        try:
            ref = self.document['sources']['creator']
            path = HERE/'genuine_bootstrap_creator.py'
            need(Path(ref['path']) == path, 'diagnostic-original-source-path')
            raw = p.read(ref, private=False)
            need(raw == self.raw['creator'], 'diagnostic-original-source-bytes')
            root = compile(raw, str(path), 'exec')
            codes = []; pending = [(root, 0)]
            while pending:
                code, depth = pending.pop()
                need(depth <= 12 and len(codes) < 512, 'diagnostic-code-bound')
                codes.append(code)
                pending.extend((item, depth+1) for item in code.co_consts if isinstance(item, type(root)))
            trace = error.__traceback__; count = 0; selected = None
            while trace is not None and count < 64:
                frame = trace.tb_frame; code = frame.f_code
                if (frame.f_globals is globals() and code.co_filename == str(path)
                        and code in codes and re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,79}', code.co_name)):
                    selected = dict(function=code.co_name, line=trace.tb_lineno,
                                    source_sha256=hashlib.sha256(raw).hexdigest())
                trace = trace.tb_next; count += 1
            if trace is None:
                answer['source_frame'] = selected
            # Close the same original source after traceback/code inspection.
            p.read(ref, private=False)
        except BaseException:
            answer['source_frame'] = None
        return answer

    def execute(self):
        try:
            plan=self.prepare()
            options={} if self.document['version']==1 else dict(reader_queue_helper=self.document['sources']['reader_queue'])
            result=b.Bootstrap(plan,self.engine).execute(native_catalog_helper=self.document['sources']['catalog_helper'],**options)
            return dict(bootstrap=result,installed_factories_verified=False,publication_acceptance=False,actual_nfs_verified=False,ordinary_ack_verified=False,birth_verified=False,mutation_authority=False,reader_resume_authority=False,automatic_replay=False)
        except BaseException as error:
            try:
                if self.journal is not None and not os.path.lexists(self.journal/'held.json'):
                    b.put(self.journal/'held.json',dict(kind='creator-held-all-resources-retained',automatic_replay=False,cleanup=False,
                                                     failure=self.failure_diagnostic(error)))
            except BaseException:pass  # Diagnostic failure cannot replace the original failure.
            raise
        finally:
            if self.geometry is not None:p.close_common_root(self.geometry);self.geometry=None
            self.closed=True


def run(ref, *, activate=False):
    need(activate is True,'explicit-creator-activation-required')
    need(os.geteuid()==os.getegid()==1000,'creator-actual-uid1000-required')
    need(sys.flags.isolated and sys.dont_write_bytecode,'creator-isolated-bytecode-disabled-required')
    return Creator(p.decode(p.read(ref))).execute()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--activate',action='store_true');parser.add_argument('--input');parser.add_argument('--sha256')
    args=parser.parse_args(argv)
    try:
        need(args.activate and args.input and p.digest(args.sha256),'explicit-creator-activation-required')
        ref=dict(path=args.input,sha256=args.sha256,signature9=p.nine(os.lstat(args.input)))
        run(ref,activate=True);print('disposable-creator-produced; factory-runtime-unproved');return 0
    except Exception:
        print('disposable-creator-held; resources-retained; no-replay');return 2


if __name__=='__main__':raise SystemExit(main())
