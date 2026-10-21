import ast
import base64
import json
import copy
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from contextlib import contextmanager

# Preserve real syscalls before finite fixture ownership projections.
HOST_STAT, HOST_LSTAT, HOST_FSTAT = os.stat, os.lstat, os.fstat
HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('effective_parent', HERE / 'parent.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
assert p.IMAGE is None, "portable-unbound-image"
p.IMAGE = "sha256:" + "a" * 64


class Tests(unittest.TestCase):
    def snapshot(self):
        return dict(cmd=b'java\0-Dspring.profiles.include=docker\0--enable-native-access=ALL-UNNAMED\0-jar\0application.jar\0--spring.config.additional-location=file:/config/\0', env=b'KOMGA_CONFIGDIR=/config\0PATH=/bin\0', uid=1000, cwd='/app')

    def account(self):
        return b'test:x:1000:1000:Test:/home/test:/bin/sh\n'

    def test_original_jvm_and_cli(self):
        props, env, args = p.original_inputs(self.snapshot(), self.account())
        self.assertEqual(props, {'spring.profiles.include': 'docker', 'user.dir': '/app', 'user.home': '/home/test', 'user.name': 'test'})
        self.assertEqual(env['KOMGA_CONFIGDIR'], '/config')
        self.assertEqual(args, ['--spring.config.additional-location=file:/config/'])

    def test_explicit_property_wins(self):
        s = self.snapshot(); s['cmd'] = s['cmd'].replace(b'java\0', b'java\0-Duser.home=/explicit\0')
        self.assertEqual(p.original_inputs(s, self.account())[0]['user.home'], '/explicit')

    def test_unknown_jvm_option(self):
        s = self.snapshot(); s['cmd'] = s['cmd'].replace(b'java\0', b'java\0-javaagent:/bad.jar\0')
        with self.assertRaisesRegex(ValueError, 'unsupported-original-jvm-option'):
            p.original_inputs(s, self.account())

    def test_inherited_agents(self):
        for key in p.AGENTS:
            s = self.snapshot(); s['env'] += key.encode() + b'=-javaagent:/unreviewed.jar\0'
            with self.assertRaises(ValueError): p.original_inputs(s, self.account())

    def test_duplicate_env_and_jvm_refused(self):
        s = self.snapshot(); s['env'] += b'PATH=/other\0'
        with self.assertRaises(ValueError): p.original_inputs(s, self.account())
        s = self.snapshot(); s['cmd'] = s['cmd'].replace(b'java\0', b'java\0-Duser.home=/x\0-Duser.home=/y\0')
        with self.assertRaises(ValueError): p.original_inputs(s, self.account())

    def test_no_account_guess(self):
        with self.assertRaisesRegex(ValueError, 'original-user-defaults'):
            p.original_inputs(self.snapshot(), b'nobody:x:65534:65534::/:/bin/false\n')

    def test_direct_config_file_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); q = root / 'application.yml'; q.write_text('komga:\n  config-dir: /config\n')
            c = p.ConfigOriginals(root); self.addCleanup(c.release); self.assertEqual(set(c.child_input()['config_files']), {'/config/application.yml'})
            q.write_text('komga: changed\n')
            with self.assertRaisesRegex(ValueError, 'config-file-final'): c.close()

    def test_heap_only_original_options_are_not_inherited_agents(self):
        s = self.snapshot(); s['env'] += b'JAVA_TOOL_OPTIONS=-Xms64m -Xmx256m\0'
        self.assertEqual(p.original_inputs(s, self.account())[1]['JAVA_TOOL_OPTIONS'], '-Xms64m -Xmx256m')
        for value in ('-Djava.io.tmpdir=/config', '-Xmx1g -javaagent:/bad', '-XX:Unknown=1', '-Xmx1g-Xms1g'):
            self.assertFalse(p.heap_only(value))

    def test_missing_xml_candidate_is_custodied_and_existing_xml_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            c = p.ConfigOriginals(d); self.addCleanup(c.release); xml = Path(d) / 'application.xml'; xml.write_text('<not-supported/>')
            with self.assertRaisesRegex(ValueError, 'config-file-namespace-final'): c.close()
            with self.assertRaisesRegex(ValueError, 'unsupported-existing-xml-config'): p.ConfigOriginals(d)

    def test_new_candidate_config_refused(self):
        with tempfile.TemporaryDirectory() as d:
            c = p.ConfigOriginals(d); self.addCleanup(c.release); (Path(d) / 'application-docker.yml').write_text('x: y')
            with self.assertRaisesRegex(ValueError, 'config-file-namespace-final'): c.close()

    def test_no_payload_read_or_timestamp_guard(self):
        with tempfile.TemporaryDirectory() as d:
            q = Path(d) / 'database.sqlite'; q.write_bytes(b'original')
            c = p.ConfigOriginals(d); self.addCleanup(c.release); q.write_bytes(b'live database changes')
            c.close(); self.assertEqual(c.files, {})

    def report(self, c):
        root = c.root
        roles = dict(config=str(root), database=str(root / 'database.sqlite'), tasks=str(root / 'tasks.sqlite'), index=str(root / 'lucene'), fonts=str(root / 'fonts'))
        identities = {str(root): c.parents[root]} | {str(root / name): c.entries[name] for name in ('database.sqlite', 'tasks.sqlite', 'lucene')}
        return copy.deepcopy(dict(scopes={k: {'host_path': v} for k, v in roles.items()}, scope_presence={k: k != 'fonts' for k in roles}, scope_identities=identities, optional_absent_scopes={str(root / 'fonts'): dict(nearest_existing_ancestor=str(root), ancestor_identity=c.parents[root])}, config_files={}, absent_config_files=[str(root / 'application.yml')]))

    def config(self, d):
        root = Path(d); (root / 'database.sqlite').write_bytes(b''); (root / 'tasks.sqlite').write_bytes(b''); (root / 'lucene').mkdir()
        result = p.ConfigOriginals(root); self.addCleanup(result.release); return result

    def test_node_descriptors_pin_original_inodes_and_release(self):
        with tempfile.TemporaryDirectory() as d:
            c = self.config(d); q = Path(d) / 'database.sqlite'; old = os.fstat(c.anchors[q])
            q.unlink(); q.write_bytes(b'new')
            self.assertEqual(os.fstat(c.anchors[q]).st_ino, old.st_ino)
            self.assertNotEqual(q.stat().st_ino, old.st_ino)
            fds = list(c.anchors.values()); c.release(); c.release()
            for fd in fds:
                with self.assertRaises(OSError): os.fstat(fd)
            with self.assertRaisesRegex(ValueError, 'config-custody-released'): c.close()

    def test_scope_replaced_before_late_selection_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            c = self.config(d); report = self.report(c); q = Path(d) / 'database.sqlite'
            q.unlink(); q.write_bytes(b'new')
            with self.assertRaisesRegex(ValueError, 'scope-final'): c.accept(report)

    def test_parent_directory_replacement_refuses_with_original_fd(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'config'; root.mkdir(); c = p.ConfigOriginals(root); self.addCleanup(c.release)
            root.rename(Path(d) / 'original'); root.mkdir()
            with self.assertRaisesRegex(ValueError, 'config-root-final'): c.close()

    def test_capture_symlink_substitution_refuses_and_releases(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); q = root / 'database.sqlite'; q.write_bytes(b'original'); target = root / 'other'; target.write_bytes(b'other')
            original_open = p.os.open; opened = []
            def replace_on_open(path, flags, *args, **kwargs):
                if path == q.name and flags & os.O_PATH:
                    q.unlink(); q.symlink_to(target.name)
                fd = original_open(path, flags, *args, **kwargs); opened.append(fd); return fd
            with patch.object(p.os, 'open', replace_on_open):
                with self.assertRaisesRegex(ValueError, 'config-node-capture'): p.ConfigOriginals(root)
            for fd in opened:
                with self.assertRaises(OSError): os.fstat(fd)

    def test_partial_capture_failure_releases_every_descriptor(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root / 'application.xml').write_text('<unsupported/>'); opened = []; original_open = p.os.open
            def record(path, flags, *args, **kwargs):
                fd = original_open(path, flags, *args, **kwargs); opened.append(fd); return fd
            with patch.object(p.os, 'open', record):
                with self.assertRaisesRegex(ValueError, 'unsupported-existing-xml-config'): p.ConfigOriginals(root)
            for fd in opened:
                with self.assertRaises(OSError): os.fstat(fd)

    def test_pre_output_main_failure_releases_config_descriptors(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); held = []; original = p.ConfigOriginals
            class Recorded(original):
                def __init__(self, source):
                    super().__init__(source); held.extend(self.anchors.values())
            supplier = type('FakeSuppliers', (), {'raw': {'owned.py': b'from types import SimpleNamespace\ninspect=lambda cid: {"State":{"Pid":1}}\nclass JarOutput: pass\n'}})()
            with patch.object(p, 'ACTIVATE', True), patch.object(p, 'IMAGE', 'sha256:'+'a'*64), patch.object(p, 'PLAN', {'container_id':'a'*64,'output':str(root/'out')}), patch.object(p, 'SUPPLIER_PINS', {}), patch.object(p.os, 'geteuid', return_value=0), patch.object(p, 'Suppliers', return_value=supplier), patch.object(p, 'ConfigOriginals', Recorded), patch.object(p, 'original_service', return_value=str(root)), patch.object(p, 'process_snapshot', side_effect=ValueError('pre-output-fixture')):
                with self.assertRaisesRegex(ValueError, 'pre-output-fixture'): p.main()
            self.assertTrue(held)
            for fd in held:
                with self.assertRaises(OSError): os.fstat(fd)

    def test_actual_selected_scope_custody(self):
        with tempfile.TemporaryDirectory() as d:
            c = self.config(d); r = self.report(c); c.accept(r)
            q = Path(d) / 'database.sqlite'; q.unlink(); q.write_bytes(b'new')
            with self.assertRaisesRegex(ValueError, 'scope-final'): c.close()

    def test_report_foreign_scope_refused(self):
        with tempfile.TemporaryDirectory() as d:
            c = self.config(d); r = self.report(c); r['scopes']['database']['host_path'] = '/outside/data'
            with self.assertRaisesRegex(ValueError, 'report-config-subscope'): c.accept(r)

    def test_absent_scope_parent_cannot_be_invented(self):
        with tempfile.TemporaryDirectory() as d:
            c = self.config(d); r = self.report(c); r['optional_absent_scopes'][str(c.root / 'fonts')]['ancestor_identity'][1] += 1
            with self.assertRaises(ValueError): c.accept(r)

    def test_absent_config_outside_refused(self):
        with tempfile.TemporaryDirectory() as d:
            c = self.config(d); r = self.report(c); r['absent_config_files'] = ['/elsewhere/application.yml']
            with self.assertRaisesRegex(ValueError, 'report-config-absence-scope'): c.accept(r)

    def test_real_proc_snapshot_stable_identity(self):
        s = p.process_snapshot(os.getpid()); self.assertEqual(s, p.process_snapshot(os.getpid()))
        self.assertEqual(s['pid'], os.getpid()); self.assertGreater(s['start_time'], 0)

    def test_real_pipe_no_readahead(self):
        child = subprocess.Popen([sys.executable, '-c', 'import sys;sys.stdout.write("READY\\nACK\\n");sys.stdout.flush()'], stdout=subprocess.PIPE, bufsize=0)
        try:
            self.assertEqual(p.line(child.stdout, time.monotonic()+3, 32), b'READY')
            self.assertEqual(p.line(child.stdout, time.monotonic()+3, 32), b'ACK')
            self.assertEqual(child.wait(timeout=3), 0)
        finally: child.stdout.close()

    def test_pipe_bound(self):
        r, w = os.pipe()
        try:
            os.write(w, b'too long\n')
            with os.fdopen(r, 'rb', buffering=0) as stream:
                with self.assertRaisesRegex(ValueError, 'child-pipe-bound'): p.line(stream, time.monotonic()+2, 3)
        finally: os.close(w)

    def test_only_nonce_child_image_and_readonly_mounts(self):
        cmd = p.child_command('owned', 'nonce', Path('/fd/cid'), Path('/code'), '/original/config')
        self.assertIn('--network', cmd); self.assertEqual(cmd[cmd.index('--network')+1], 'none')
        binds = [cmd[i+1] for i, s in enumerate(cmd) if s == '--volume']
        self.assertEqual(len(binds), len(p.CLASSES) + 1); self.assertTrue(all(s.endswith(':ro') for s in binds))
        self.assertNotIn('compose', cmd); self.assertNotIn('--privileged', cmd)

    def child_row(self):
        code=Path('/code');config='/original/config';env=['KOMGA_CONFIGDIR=/config']
        mappings={str(code/n):'/checks/'+n for n in p.CLASSES}|{config:'/config'}
        c=dict(Image=p.IMAGE,User='1000:1000',Entrypoint=['java'],Cmd=['-XX:-UsePerfData','-cp','/checks:/app/application.jar','KomgaEffectiveScope'],Env=env,Labels={'com.homelab.isolated-verification':'nonce'},Healthcheck={'Test':['NONE']})
        h=dict(ReadonlyRootfs=True,NetworkMode='none',CapDrop=['ALL'],SecurityOpt=['no-new-privileges'],Privileged=False,Memory=536870912,MemorySwap=536870912,PidsLimit=64,Binds=[s+':'+d+':ro' for s,d in mappings.items()],Tmpfs={},Mounts=[],Devices=[],DeviceRequests=[],PortBindings={},PublishAllPorts=False)
        return dict(Image=p.IMAGE,Name='/case',Config=c,HostConfig=h,Mounts=[dict(Type='bind',Source=s,Destination=d,RW=False) for s,d in mappings.items()]),code,config,env

    def test_child_bind_order_is_not_authority(self):
        row,code,config,env=self.child_row();row['HostConfig']['Binds'].reverse();p.child_profile(row,'case','nonce',code,config,env)

    def test_child_bind_duplicate_missing_and_changed_refuse(self):
        for change in ('duplicate','missing','changed','mapping'):
            row,code,config,env=self.child_row();binds=row['HostConfig']['Binds']
            if change=='duplicate':binds[1]=binds[0]
            if change=='missing':binds.pop()
            if change=='changed':binds[0]+='changed'
            if change=='mapping':row['HostConfig']['Binds']=dict.fromkeys(binds,1)
            with self.assertRaisesRegex(ValueError,'child-bind-security'):p.child_profile(row,'case','nonce',code,config,env)

    def test_disabled_actual_main(self):
        with self.assertRaisesRegex(ValueError, 'disabled'): p.main()

    def test_retained_original_media_mounts_preserved_not_projected(self):
        row = dict(Id='a'*64, Image=p.IMAGE, State=dict(Running=True, Paused=False, Restarting=False, Pid=42), Mounts=[dict(Destination='/config', Source='/original/config', Type='volume', RW=True), dict(Destination='/normalizer-state', Source='/original/state', Type='bind', RW=False), dict(Destination='/data/comics', Source='/original/comics', Type='bind', RW=True), dict(Destination='/data/manga', Source='/original/manga', Type='bind', RW=True)])
        self.assertEqual(p.original_service(row, 'a'*64), '/original/config')
        for destination in ('/config/extra', '/app', '/app/lib', '/'):
            tampered = copy.deepcopy(row); tampered['Mounts'].append(dict(Destination=destination, Source='/unreviewed', Type='bind', RW=False))
            with self.assertRaises(ValueError): p.original_service(tampered, 'a'*64)

    def test_actual_equal_order_factory_sequence(self):
        facts = json.loads((HERE / 'original-public-dependency-facts.json').read_bytes())
        boot = next(row for row in facts['dependencies'] if row['path'].split('/')[-1] == 'spring-boot-3.5.16.jar')
        factories = base64.b64decode(boot['resources_base64']['META-INF/spring.factories']).decode()
        cloud = 'org.springframework.boot.cloud.CloudFoundryVcapEnvironmentPostProcessor'
        application_json = 'org.springframework.boot.env.SpringApplicationJsonEnvironmentPostProcessor'
        self.assertLess(factories.index(cloud), factories.index(application_json))
        source = (HERE / 'KomgaEffectiveScope.java').read_text()
        self.assertLess(source.index('processor("' + cloud), source.index('processor("' + application_json))

    def test_python310_syntax(self):
        ast.parse((HERE / 'parent.py').read_text(), feature_version=(3, 10))

    def test_no_java_application_bootstrap(self):
        source = (HERE / 'KomgaEffectiveScope.java').read_text()
        self.assertNotIn('runApplication(', source); self.assertNotIn('SpringApplication.run(', source)
        self.assertNotIn('getApplicationContext', source); self.assertNotIn('DataSourcesConfiguration', source)
        self.assertIn('getDeclaredMethod("postProcessEnvironment"', source)
        self.assertIn('unclosed-config-origin', source)



class DisposableOriginals(unittest.TestCase):
    """Disposable files and source-original references, never runtime admission."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700);self.nonce='b'*64
        self.source=Path(__file__).parents[2]/'mylar3/config/reader_recovery/genuine_application_bootstrap.py'
        self.plan_path=self.root/'bootstrap.json'
        owner=self.owner_model();owner.__enter__();self.addCleanup(owner.__exit__,None,None,None)
        source_ref=self.ref(self.source)
        root='/fixture/state/archive-bootstrap-'+self.nonce
        common='/fixture/nfs/archive-publication-'+self.nonce
        library=common+'/L';retention=common+'/R'
        self.row=dict(Id='a'*64,Name='/archive-bootstrap-'+self.nonce[:16]+'-reader',Image=p.IMAGE,Created='original',Path='java',Args=[],
            Config=dict(Labels={'com.homelab.archive.bootstrap':self.nonce,'com.homelab.archive.purpose':'genuine-archive-fixture'}),
            HostConfig={},Mounts=[dict(Type='bind',Source=root+'/reader',Destination='/config',RW=True),dict(Type='bind',Source=library,Destination=library,RW=False)],
            State=dict(Running=True,Paused=False,Restarting=False,Pid=42,StartedAt='original'))
        profile={key:self.row[key]for key in ('Id','Name','Image','Path','Args','Config','HostConfig','Mounts','Created')}
        roles={name:dict(id=letter*64,image=p.IMAGE,profile=copy.deepcopy(profile),epoch=copy.deepcopy(self.row['State']))for name,letter in zip(('native','reader','worker'),'cad')}
        for name,value in roles.items():
            value['profile']['Id']=value['id'];value['profile']['Name']='/archive-bootstrap-'+self.nonce[:16]+'-'+name
        self.document=dict(version=1,kind='approved-disposable-application-bootstrap',nonce=self.nonce,
            state_root=dict(path=root,signature9=[1,2,0,1,1,0o40700,1000,1000,2]),geometry=dict(version=1,kind='private-common-root-nfs',common_root=dict(path=common,signature9=[1,2,0,1,1,0o40700,1000,1000,2]),library=dict(path=library,signature9=[1,2,0,1,1,0o40700,1000,1000,2]),retention=dict(path=retention,signature9=[1,2,0,1,1,0o40700,1000,1000,2])),
            roles=roles,images={name:p.IMAGE for name in roles})
        self.write_plan();self.refs=dict(plan=self.plan_ref,source=source_ref)
    @contextmanager
    def owner_model(self, *, host_owner=None, project=True):
        """Only two declared files model UID1000 evidence on any host account.

        Real opens, bytes, modes, inode identities, nlink and all timestamps/ns
        remain unchanged. Production bounded()/need()/owner checks run intact.
        """
        paths={str(self.plan_path.absolute()),str(self.source.resolve())}
        actual=(os.getuid(),os.getgid());observed=actual if host_owner is None else host_owner
        class View:
            def __init__(self,row,owner):self.row=row;self.st_uid,self.st_gid=owner
            def __getattr__(self,name):return getattr(self.row,name)
        def view(row,path):
            if path in paths and (row.st_uid,row.st_gid)==actual:
                return View(row,(1000,1000) if project else observed)
            return row
        def stat(path,*args,**kwargs):return view(HOST_STAT(path,*args,**kwargs),os.path.abspath(os.fspath(path)))
        def lstat(path,*args,**kwargs):return view(HOST_LSTAT(path,*args,**kwargs),os.path.abspath(os.fspath(path)))
        def fstat(fd):
            try:path=os.readlink('/proc/self/fd/'+str(fd))
            except OSError:path=None
            return view(HOST_FSTAT(fd),path)
        # Python3.10 pathlib caches its accessor syscalls at import time.
        with patch.object(p.os,'stat',side_effect=stat),patch.object(p.os,'lstat',side_effect=lstat),patch.object(p.os,'fstat',side_effect=fstat),patch.object(Path,'stat',stat),patch.object(Path,'lstat',lstat):yield

    def ref(self,path):return dict(path=str(path.resolve()),sha256=p.digest(path.read_bytes()),signature9=p.nine(path.stat()))
    def write_plan(self):
        self.plan_path.write_bytes(p.encode(self.document));self.plan_path.chmod(0o600);self.plan_ref=self.ref(self.plan_path)
    def originals(self):return p.BootstrapOriginals(self.refs)
    def test_default_refuses_but_exact_original_disposable_mounts_pass(self):
        with self.assertRaisesRegex(ValueError,'supported-original-mount-destinations'):p.original_service(self.row,'a'*64)
        original=self.originals();self.addCleanup(original.release)
        self.assertEqual(original.service(self.row,'a'*64),self.row['Mounts'][0]['Source']);original.close()
        self.assertEqual(p.child_command('case','token','/cid',Path('/checks'),'/exact/config').count('/exact/config:/config:ro'),1)
    def test_no_caller_mount_list_overlays_writes_foreign_profile_or_nonce(self):
        for change in ('extra','write','source','duplicate','epoch','nonce'):
            with self.subTest(change=change):
                row=copy.deepcopy(self.row)
                if change=='extra':row['Mounts'].append(dict(Type='bind',Source='/foreign',Destination='/app/x',RW=False))
                elif change=='write':row['Mounts'][1]['RW']=True
                elif change=='source':row['Mounts'][1]['Source']='/foreign'
                elif change=='duplicate':row['Mounts'].append(copy.deepcopy(row['Mounts'][1]))
                elif change=='epoch':row['State']['Pid']+=1
                else:row['Config']['Labels']['com.homelab.archive.bootstrap']='c'*64
                original=self.originals();self.addCleanup(original.release)
                with self.assertRaises(ValueError):original.service(row,'a'*64)
    def test_wrong_pin_original_replacement_and_duplicate_json_refuse(self):
        refs=copy.deepcopy(self.refs);refs['source']['sha256']='0'*64
        with self.assertRaises(ValueError):p.BootstrapOriginals(refs)
        original=self.originals();self.addCleanup(original.release)
        self.plan_path.write_bytes(self.plan_path.read_bytes()+b' ')
        with self.assertRaises(ValueError):original.close()
        self.plan_path.write_bytes(b'{"nonce":1,"nonce":2}');self.plan_path.chmod(0o600)
        refs=copy.deepcopy(self.refs);refs['plan']=self.ref(self.plan_path)
        with self.assertRaises(ValueError):p.BootstrapOriginals(refs)

    def test_self_consistent_foreign_mount_or_geometry_still_refuses(self):
        for change in ('extra', 'writable', 'library', 'state', 'memory'):
            with self.subTest(change=change):
                row=copy.deepcopy(self.row);document=copy.deepcopy(self.document)
                if change=='extra':row['Mounts'].append(dict(Type='bind',Source='/foreign',Destination='/foreign',RW=False))
                elif change=='writable':row['Mounts'][1]['RW']=True
                elif change=='library':document['geometry']['library']['path']='/foreign'
                elif change=='state':document['state_root']['path']='/app/archive-bootstrap-'+self.nonce
                document['roles']['reader']['profile']['Mounts']=copy.deepcopy(row['Mounts'])
                self.plan_path.write_bytes(p.encode(document));self.plan_path.chmod(0o600)
                refs=copy.deepcopy(self.refs);refs['plan']=self.ref(self.plan_path)
                original=p.BootstrapOriginals(refs);self.addCleanup(original.release)
                if change=='memory':original.document['nonce']='c'*64
                with self.assertRaises(ValueError):original.service(row,'a'*64)

    def test_refusal_releases_evidence_descriptors(self):
        before=set(os.listdir('/proc/self/fd'))
        refs=copy.deepcopy(self.refs);refs['source']['sha256']='0'*64
        with self.assertRaises(ValueError):p.BootstrapOriginals(refs)
        self.assertEqual(set(os.listdir('/proc/self/fd')),before)

    def test_optional_main_refusal_releases_both_original_descriptor_groups(self):
        held=[];bootstrap=p.BootstrapOriginals;config=p.ConfigOriginals
        root=self.root;row=self.row
        class RecordedBootstrap(bootstrap):
            def __init__(self,refs):
                super().__init__(refs);held.extend(self.anchors.values())
        class LocalConfig(config):
            def __init__(self,source):
                if source != row['Mounts'][0]['Source']:raise AssertionError('wrong config source')
                super().__init__(root);held.extend(self.anchors.values())
        supplier=type('SourceDouble',(),{'raw':{'owned.py':b'inspect=lambda cid: ORIGINAL\nclass JarOutput: pass\n'}})()
        # Only inspected transport and process effects are projected. The exact
        # original bootstrap source/plan and both FD groups are really consumed.
        import builtins
        with patch.object(builtins,'ORIGINAL',row,create=True), patch.object(p,'ACTIVATE',True), patch.object(p,'SUPPLIER_PINS',{}), patch.object(p.os,'geteuid',return_value=0), patch.object(p,'Suppliers',return_value=supplier), patch.object(p,'PLAN',dict(container_id='a'*64,output=str(root/'out'),bootstrap_originals=self.refs)), patch.object(p,'BootstrapOriginals',RecordedBootstrap), patch.object(p,'ConfigOriginals',LocalConfig), patch.object(p,'process_snapshot',side_effect=ValueError('fixed-pre-output-failure')):
            with self.assertRaisesRegex(ValueError,'fixed-pre-output-failure'):p.main()
        self.assertTrue(held)
        for fd in held:
            with self.assertRaises(OSError):os.fstat(fd)

    def test_host_uid1001_model_preserves_real_foreign_owner_refusal(self):
        with self.owner_model(host_owner=(1001,1001),project=False):
            self.assertEqual(self.plan_path.stat().st_uid,1001)
            refs=dict(plan=self.ref(self.plan_path),source=self.ref(self.source))
            with self.assertRaisesRegex(ValueError,'original-owner'):p.BootstrapOriginals(refs)
        with self.owner_model(host_owner=(1001,1001)):
            refs=dict(plan=self.ref(self.plan_path),source=self.ref(self.source))
            original=p.BootstrapOriginals(refs);self.addCleanup(original.release)
            self.assertEqual(original.service(self.row,'a'*64),self.row['Mounts'][0]['Source'])
            refs=copy.deepcopy(refs);refs['source']['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'bootstrap-original-bytes'):p.BootstrapOriginals(refs)
        # Check that the projection never changes non-ownership file metadata.
        expected=p.nine(HOST_STAT(self.plan_path));observed=p.nine(self.plan_path.stat())
        self.assertEqual(observed[:6]+observed[8:],expected[:6]+expected[8:])

if __name__ == '__main__': unittest.main(verbosity=2)
