"""Disposable local filesystem and explicit fake engine only. No NFS/API/Docker."""
import argparse
import copy
import importlib.util
import inspect
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).parent

def load(name):
    path=ROOT/(name+'.py')
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

P=load('comic_negative_nfs_active_parent')
L=load('comic_negative_nfs_active_lifecycle')
K=load('comic_negative_nfs_hardlink_probe')
C=load('comic_negative_nfs_hardlink_child')

def fixture_execute(args,engine,lease,factual_sink=None):
    # Explicit fixture-only substitution of already-admitted source readiness.
    # This exercises the genuine lifecycle implementation; never production bind.
    outer,of=P.read(args.input,args.input_sha256)
    scope,sf=P.read(outer['active_scope']['path'],outer['active_scope']['sha256'])
    own=P.fact(P.__file__,args.source_sha256,source=True)
    helper=P.fact(P.LIFECYCLE,P.LIFECYCLE_SHA,source=True)
    value=P._run_owned_lifecycle(args,outer,of,scope,sf,own,helper,engine,lease,{})
    if factual_sink is not None:factual_sink.append(value)
    return value.binding

class Lease:
    def __init__(self):self.calls=0;self.callback=None;self.interrupt_at=None
    def pulse(self):
        self.calls+=1
        if self.callback:self.callback()
        if self.calls==self.interrupt_at:raise L.Held('fixture-lease-interrupted')

class LocalEnvironment(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix='nfs-current-source-local-');self.addCleanup(tmp.cleanup)
        root=Path(tmp.name);self.root=root
        ready=root/'readiness.py';ready.write_text('# synthetic engine only\n');ready.chmod(0o644)
        parity=root/'parity.py';parity.write_text('# synthetic parity only\n');parity.chmod(0o644)
        mapping=root/'map.json';mapping.write_text(json.dumps({str(i):'fixture-only' for i in range(69)}));mapping.chmod(0o600)
        fake_writer=root/'media-writer';fake_writer.mkdir(mode=0o700)
        values=dict(IMAGE='sha256:'+'a'*64,NATIVE_IMAGE='sha256:'+'a'*64,KOMGA='sha256:'+'c'*64,WORKER='sha256:'+'b'*64,
                    READY=ready,READY_SHA=P.digest(ready.read_bytes()),PARITY=parity,PARITY_SHA=P.digest(parity.read_bytes()),
                    HARDLINK_KERNEL=Path(K.__file__),PROBE=ROOT/'comic_negative_nfs_hardlink_child.py',PROBE_SHA=P.digest((ROOT/'comic_negative_nfs_hardlink_child.py').read_bytes()),MAP=mapping,MAP_SHA=P.digest(mapping.read_bytes()),NATIVE_MAP_COUNT=69,
                    LIFECYCLE=Path(L.__file__),LIFECYCLE_SHA=P.digest(Path(L.__file__).read_bytes()),WRITER_ROOT=fake_writer,
                    _NATIVE_PROJECTOR=lambda value:dict(inspect={k:v for k,v in value['inspect'].items() if k!='State'},process=value['process'],publication={k:value['publication'][k] for k in ('state','reason','census')}),_COHORT=SimpleNamespace(facts=lambda:{}))
        c=patch.multiple(P,**values);c.start();self.addCleanup(c.stop)
        c=patch.object(P,'native_gate',return_value={});c.start();self.addCleanup(c.stop)
        c=patch.object(P,'lifecycle_module',return_value=L);c.start();self.addCleanup(c.stop)
        def fresh(call,container_id):
            raw=call(['explicit-fake-daemon-probe'],P.READY.read_bytes())
            publication=json.loads(raw.stdout if hasattr(raw,'stdout') else raw)['api_response']['data']['publication']
            return {'publication':publication,'process':{'pid':11,'start_ticks':17,'argv':['explicit-fixture']},'config':{'path':'/config/config.ini','sha256':'f'*64,'signature9':[1]*9}}
        c=patch.object(P,'fresh_native',side_effect=fresh);c.start();self.addCleanup(c.stop)

class FullLifecycleControls(LocalEnvironment):
    def fixture(self, failure=None, optional_fonts=False, use_core=False, return_factual=False):
        tmp = tempfile.TemporaryDirectory(prefix='active-nfs-whole-local-')
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        libraries = [root / 'comics', root / 'manga']
        for p in libraries:
            p.mkdir(mode=0o700)
        grandparent = root / 'private-parent-fixture'
        grandparent.mkdir(mode=0o700)
        parent = grandparent / ('.comic-nfs-private-' + 'd' * 32)
        output = root / 'operation'
        fonts_parent = root / 'effective-config'
        fonts_parent.mkdir(mode=0o700)
        events = []
        refs = {}
        for name, value in (
            ('generic', {'fixture_only': True}),
            ('protected', {'kind': 'reviewed-nfs-protected-catalog-cache-recovery-scope',
                           'roots': ['/srv/example/media/comics', '/srv/example/media/manga']})):
            p = root / (name + '.json')
            P.write(p, value)
            refs[name] = {'path': str(p), 'sha256': P.digest(p.read_bytes())}
        sources = {k: refs['generic'] for k in (
            'current_runtime_bracket', 'current_mylar_hold', 'current_worker_created',
            'current_komga_libraries', 'current_komga_effective_scope',
            'protected_catalog_cache_recovery_scope', 'continuous_raw_writer_lease')}
        sources['protected_catalog_cache_recovery_scope'] = refs['protected']
        scope = {'version': 2, 'kind': 'root-reviewed-nfs-active-disposable-scope',
                 'approved_disposable_diagnostic': True, 'observed': int(time.time()),
                 'current_active_scanner_publication_paths_reviewed': True,
                 'future_mylar_destination_verified': False, 'future_mylar_destination': None,
                 'writer_lifecycle_resume_authorized': False,
                 'forbidden_roots': ['/srv/example/media/comics', '/srv/example/media/manga'], 'sources': sources}
        scope_path = root / 'scope.json'
        P.write(scope_path, scope)
        scope_ref = {'path': str(scope_path), 'sha256': P.digest(scope_path.read_bytes())}
        mount = {'source': 'synthetic-only:/fixture', 'target': str(grandparent), 'fstype': 'nfs4',
                 'fsroot': '/', 'options': 'rw', 'maj:min': '0:1'}
        plan = {'version': 1, 'kind': 'approved-active-nfs-owned-lifecycle', 'active_scope': scope_ref,
                'parent_admission': {'path': str(parent), 'grandparent_signature': L.stamp(grandparent),
                                     'expected_device': L.stamp(grandparent)[0], 'mount_identity': mount},
                'probe_plan': {'version':2,'kind':'approved-negative-nfs-active-probe-parent','fixture_parent': str(parent), 'fixture_parent_signature': None,
                               'library_root': '/srv/example/media/comics',
                               'expected_device': L.stamp(grandparent)[0], 'mount_identity': mount,
                               'fixture_name': '.comic-nfs-probe-' + 'e' * 32, 'scope': scope_ref,
                               'output_root': str(output / 'probe')},
                'operation_output': str(output), 'native_controls': refs['generic'],
                'effective_observer_review': {'report': refs['generic']}}
        path = root / 'plan.json'
        P.write(path, plan)
        args = argparse.Namespace(input=str(path), input_sha256=P.digest(path.read_bytes()),
                                  source_sha256=P.digest(Path(P.__file__).read_bytes()), execute=True)

        def state(running, pid):
            return {'Status': 'running' if running else 'created', 'Running': running, 'Pid': pid,
                    'StartedAt': 'fixed','FinishedAt':'','ExitCode':0,'Error':'', 'Paused': False, 'Restarting': False, 'Dead': False, 'OOMKilled': False}
        reader = {'Name': '/komga', 'Id': 'c' * 64, 'Image': P.KOMGA, 'State': state(True, 3),
                  'Config': {}, 'HostConfig': {}, 'NetworkSettings': {'Networks': {'ingress-public': {'NetworkID': 'synthetic-network', 'IPAddress': '192.0.2.1'}}},
                  'Mounts': [{'Destination': '/data/comics', 'Source': '/srv/example/media/comics', 'Type': 'bind', 'RW': True},
                             {'Destination': '/data/manga', 'Source': '/srv/example/media/manga', 'Type': 'bind', 'RW': True}]}
        rows = [{'Name': '/mylar3', 'Id': 'a' * 64, 'Image': P.IMAGE, 'State': state(True, 1),
                 'Mounts': [{'Destination': '/data', 'Source': '/srv/example/media', 'Type': 'bind', 'RW': True},
                            {'Destination': '/config', 'Source': str(P.WRITER_ROOT.parent), 'Type': 'volume', 'RW': True}]},
                {'Name': '/komga-comic-normalizer-1', 'Id': 'b' * 64, 'Image': P.WORKER, 'State': state(False, 0)}, reader]
        for row in rows:
            row.setdefault('Path','fixture');row.setdefault('Args',[]);row.setdefault('Config',{});row.setdefault('HostConfig',{});row.setdefault('Mounts',[]);row.setdefault('NetworkSettings',{})
        publication = {'state': 'held', 'reason': 'startup-restart-required',
                       'census': {'revision': 13, 'keys': [str(i) for i in range(13)]}}

        childrows=[]
        def engine(argv, **kwargs):
            if argv[0] == 'findmnt':
                result = {'filesystems': [mount]}
            elif 'create' in argv:
                mounts=[]
                for i,v in enumerate(argv):
                    if v=='--mount':
                        fields=dict(item.split('=',1) for item in argv[i+1].split(',') if '=' in item);mounts.append(dict(Type='bind',Source=fields['src'],Destination=fields['dst'],RW='readonly' not in argv[i+1]))
                name=argv[argv.index('--name')+1]
                childrows[:]=[dict(Id='d'*64,Image=P.IMAGE,Config=dict(User='1000:1000',Labels={'com.homelab.nfs.probe':name},Entrypoint=['/lsiopy/bin/python3'],Cmd=argv[argv.index(P.IMAGE)+1:]),State=dict(Status='created',Running=False,Pid=0,Paused=False,Restarting=False,Dead=False,OOMKilled=False),HostConfig=dict(ReadonlyRootfs=True,Privileged=False,NetworkMode='none',PidMode='',CapDrop=['ALL'],SecurityOpt=['no-new-privileges'],PidsLimit=64),Mounts=mounts)]
                return subprocess.CompletedProcess(argv,0,('d'*64).encode(),b'')
            elif 'start' in argv:
                inp=output/'probe'/'probe-input.json'
                original_exec=exec
                def explicit_fixture_exec(code,namespace):
                    original_exec(code,namespace);namespace['mount']=lambda path:mount;namespace['nfs_magic']=lambda path:0x6969
                with patch.object(C,'exec',explicit_fixture_exec,create=True):
                    raw=C.run(str(inp),P.digest(inp.read_bytes()),P.PROBE_SHA,str(P.HARDLINK_KERNEL))
                childrows[0]['State']=dict(Status='exited',Running=False,Pid=0,ExitCode=0,Paused=False,Restarting=False,Dead=False,OOMKilled=False)
                if failure=='lost-child-ack':
                    events.append('actual-kernel-ACK-lost');raise subprocess.TimeoutExpired(argv,1)
                return subprocess.CompletedProcess(argv,0,raw,b'')
            elif 'inspect' in argv:
                result = childrows if argv[-1]=='d'*64 else rows
            elif kwargs.get('input') == P.READY.read_bytes():
                current = publication if 'lease-start' not in events or 'release-after-absence' in events else {'state': 'held', 'reason': 'writer-busy', 'census': None}
                result = {'api_response': {'success': True, 'data': {'publication': current}}}
            elif kwargs.get('input') == P.PARITY.read_bytes():
                result = P.read(P.MAP, P.MAP_SHA)[0]
            else:
                self.fail('unexpected synthetic engine command')
            return subprocess.CompletedProcess(argv, 0, P.encode(result), b'')

        class SyntheticLease(Lease):
            def __init__(inner, out, engine):
                super().__init__()
                inner.out = out

            def start(inner):
                events.append('lease-start')
                (inner.out / 'lease-empty-config').mkdir(mode=0o700)

            def pulse(inner):
                super().pulse()
                events.append('lease-pulse')
                if failure == 'interrupt-after-probe' and 'probe' in events:
                    raise L.Held('synthetic-lease-lost')

            def release_after_absence(inner, paths, **kwargs):
                self.assertTrue(all(not os.path.lexists(p) for p in paths))
                events.append('release-after-absence')

        def probe(a, engine, lease):
            events.append('probe')
            derived = P.read(a.input, a.input_sha256)[0]
            c = Path(derived['fixture_parent']) / derived['fixture_name']
            c.mkdir(mode=0o700)
            out = Path(derived['output_root'])
            out.mkdir(mode=0o700)
            (c/'source').mkdir(mode=0o700);(c/'target').mkdir(mode=0o700)
            kernelplan=dict(version=1,kind='reviewed-disposable-hardlink-nfs-canary',nonce='a'*64,root=str(c),root9=K.nine(c.lstat()),source_parent9=K.nine((c/'source').lstat()),target_parent9=K.nine((c/'target').lstat()),device=c.stat().st_dev,mount=mount,forbidden_roots=[str(p) for p in libraries],seconds=120)
            ki=root/'kernel-input.json';ki.write_bytes(K.encode(kernelplan));ki.chmod(0o600)
            kref=dict(path=str(ki),sha256=P.digest(ki.read_bytes()),signature9=K.nine(ki.lstat()))
            source=Path(K.__file__);sref=dict(path=str(source),sha256=P.digest(source.read_bytes()),signature9=K.nine(source.lstat()))
            with patch.object(K,'mount',return_value=mount),patch.object(K,'nfs_magic',return_value=0x6969):
                observation=K.run(kref,sref);observation.close()
            names={'source/source.bin','source/collision.bin','target/foreign.bin','stage-intent.json','collision-intent.json','retire-intent.json','restore-intent.json','unstage-intent.json','result.json'}
            ff={str(c/name):P.fact(c/name) for name in names}
            accepted={'fixture':str(c),'fixture_signature':P.stamp(c),'fixture_facts':ff,'fixture_directories':{name:P.stamp(c/name) for name in ('source','target')}}
            af=P.write(out/'acceptance.json',accepted)
            if failure == 'network-route-drift':
                reader['NetworkSettings']['Networks']['ingress-public']['IPAddress'] = '192.0.2.2'
            if failure == 'late-foreign-payload':
                (c / 'source' / 'source.bin').write_bytes(b'foreign-after-core-ack')
            if failure == 'unknown-fixture':
                (c / 'foreign').write_bytes(b'foreign')
            return {'probe_verified': True, 'fixture_retained': True, 'platform_supported': False,
                    'acceptance_sha256': af['sha256']}

        original_core=P.probe_existing_parent
        if use_core:
            def observe_core(a,engine,lease):
                events.append('probe')
                # Explicit local substitute only for the production literal NFS library path.
                def local_validate(core,scope):
                    self.assertEqual(core['library_root'],'/srv/example/media/comics');self.assertEqual(core['scope'],scope_ref)
                    return Path(core['fixture_parent'])/core['fixture_name'],Path(core['output_root']),libraries
                with patch.object(P,'validate',side_effect=local_validate):return original_core(a,engine,lease)
            actual_core=observe_core
        else:actual_core=probe
        original = P.canonical
        aliases = dict(zip(('/srv/example/media/comics', '/srv/example/media/manga'), libraries))

        def canonical(p):
            return original(aliases.get(str(p), p))

        with patch.object(P, 'canonical', side_effect=canonical), \
                patch.object(P, 'active_native_controls', return_value={}), \
                patch.object(P, 'active_effective_controls', return_value=({}, {'container': copy.deepcopy(reader)},
                                                                           {'container_id': reader['Id'], 'pid': 3, 'start_time': 100,
                                                                            'optional_absent_scopes': {str(fonts_parent / 'fonts'): {}} if optional_fonts else {}})), \
                patch.object(P, 'process_start', return_value=100), \
                patch.object(P, 'fresh_libraries', return_value={'fixture_only': True}), \
                patch.object(P, 'probe_existing_parent', side_effect=actual_core):
            if failure:
                with self.assertRaises((P.Held, L.Held)):
                    fixture_execute(args, engine, SyntheticLease)
                self.assertNotIn('release-after-absence', events)
                self.assertTrue(parent.exists())
                return events
            captured=[]
            result = fixture_execute(args, engine, SyntheticLease,captured)
        self.assertFalse(parent.exists())
        self.assertTrue(result['owned_fixture_absence_verified'])
        self.assertFalse(result['native_grant'])
        self.assertFalse(result['publication_authority'])
        self.assertFalse(result['future_mylar_destination_verified'])
        self.assertFalse(result['writer_lifecycle_resume_authorized'])
        self.assertLess(events.index('lease-start'), events.index('probe'))
        self.assertLess(events.index('probe'), events.index('release-after-absence'))
        if return_factual:
            fixture_projection=patch.object(P,'canonical',side_effect=canonical);fixture_projection.start();self.addCleanup(fixture_projection.stop)
            return captured[0],rows,events
        return events

    def test_late_optional_fonts_creation_holds_after_absence_check(self):
        original = L.os.listdir
        fired = []
        def inject(path):
            saved = original(path)
            if not isinstance(path, int):
                p = Path(path)
                if (p.name == 'operation' and (p / 'active-acceptance.json').exists()
                        and any(f.function == 'close_vector' for f in inspect.stack())):
                    (p.parent / 'effective-config' / 'fonts').mkdir(mode=0o700)
                    fired.append(True)
            return saved
        with patch.object(L.os, 'listdir', side_effect=inject), self.assertRaises((P.Held,L.Held)):
            self.fixture(optional_fonts=True)
        self.assertTrue(fired)

    def test_terminal_saved_census_late_foreign_owned_directory_holds(self):
        original = L.os.listdir
        for name in ('operation', 'probe', 'lease-empty-config'):
            with self.subTest(directory=name):
                fired = []
                def inject(path):
                    saved = original(path)
                    if isinstance(path, int):
                        return saved
                    p = Path(path)
                    operation = p if p.name == 'operation' else p.parent
                    if (p.name == name and (operation / 'active-acceptance.json').exists()
                            and any(f.function == 'close_vector' for f in inspect.stack())):
                        (p / 'late-foreign.json').write_bytes(b'foreign late census callback')
                        fired.append(True)
                    return saved
                with patch.object(L.os, 'listdir', side_effect=inject), self.assertRaises((P.Held,L.Held)):
                    self.fixture()
                self.assertTrue(fired)

    def test_effective_reader_network_route_drift_retains_no_release(self):
        self.fixture('network-route-drift')

    def test_complete_owned_lifecycle_default_no_future_grant(self):
        self.fixture()

    def test_whole_lifecycle_lease_loss_retains_no_release(self):
        self.fixture('interrupt-after-probe')

    def test_cleanup_binds_core_ack_original_hashes(self):
        self.fixture('late-foreign-payload')

    def test_unknown_fixture_never_cleaned_or_released(self):
        self.fixture('unknown-fixture')

class NewTerminalControls(LocalEnvironment):
    fixture=FullLifecycleControls.fixture
    # Do not duplicate inherited controls in discovery.
    def test_post_release_parent_reappearance(self):
        original=P.write;fired=[]
        def inject(path,value):
            result=original(path,value)
            if value.get('kind')=='active-owned-disposable-nfs-acceptance':
                p=Path(path).parent.parent/'private-parent-fixture'/('.comic-nfs-private-'+'d'*32)
                p.mkdir(mode=0o700);fired.append(True)
            return result
        with patch.object(P,'write',side_effect=inject),self.assertRaisesRegex((P.Held,L.Held),'terminal-owned-absence'):
            self.fixture()
        self.assertTrue(fired)

    def test_post_release_fixture_reappearance(self):
        original=P.write;fired=[]
        def inject(path,value):
            result=original(path,value)
            if value.get('kind')=='active-owned-disposable-nfs-acceptance':
                p=Path(path).parent.parent/'private-parent-fixture'/('.comic-nfs-private-'+'d'*32)
                p.mkdir(mode=0o700);(p/('.comic-nfs-probe-'+'e'*32)).mkdir(mode=0o700);fired.append(True)
            return result
        with patch.object(P,'write',side_effect=inject),self.assertRaisesRegex((P.Held,L.Held),'terminal-owned-absence'):
            self.fixture()
        self.assertTrue(fired)

    def test_last_close_vector_callback_reappearance(self):
        original=L.close_vector;fired=[]
        def inject(leaves,nodes,censuses,absent=()):
            original(leaves,nodes,censuses,absent)
            if absent and any(Path(p).name.startswith('.comic-nfs-private-') for p in absent):
                p=next(Path(p) for p in absent if Path(p).name.startswith('.comic-nfs-private-'))
                p.mkdir(mode=0o700);fired.append(True)
        with patch.object(L,'close_vector',side_effect=inject),self.assertRaisesRegex((P.Held,L.Held),'terminal-owned-absence'):
            self.fixture()
        self.assertTrue(fired)

class SourceControls(unittest.TestCase):
    def test_default_off_no_engine(self):
        result=P.execute(SimpleNamespace(execute=False),engine=lambda *a,**k:self.fail('no engine'))
        self.assertFalse(result['executable']);self.assertFalse(result['publication_authority'])

    def test_no_current_cohort_refuses_before_engine(self):
        with tempfile.TemporaryDirectory(prefix='nfs-cohort-local-') as d:
            p=Path(d)/'plan.json';p.write_bytes(b'{}');p.chmod(0o600)
            a=SimpleNamespace(execute=True,input=str(p),input_sha256=P.digest(p.read_bytes()))
            with patch.object(P,'_COHORT',None),self.assertRaises(P.Held):
                P.execute(a,engine=lambda *a,**k:self.fail('no engine'))

    def test_lifecycle_terminal_require_is_not_callback(self):
        with tempfile.TemporaryDirectory(prefix='nfs-vector-local-') as d:
            p=Path(d)/'file';p.write_bytes(b'original');p.chmod(0o600)
            signature=L.stamp(p)
            with patch.object(L,'require',side_effect=AssertionError('final helper called')):
                L.close_vector({p:signature},{},{})

class CohortControls(unittest.TestCase):
    def make(self,fault=None):
        tmp=tempfile.TemporaryDirectory(prefix='nfs-cohort-fake-evidence-only-');self.addCleanup(tmp.cleanup)
        base=Path(tmp.name);base.chmod(0o700)
        def emit(name,value,source=False):
            p=base/name
            p.write_bytes(value if type(value) is bytes else P.encode(value));p.chmod(0o644 if source else 0o600)
            return dict(path=str(p),sha256=P.digest(p.read_bytes()))
        roles=('probe','hardlink_kernel','scope_projection','lifecycle','readiness','readiness_input','parity','native_map','selected_sdk','writer','tests','effective_helper','effective_parent','core_parent','core_tests','writer_fixture')
        refs={}
        for role in roles:
            if role=='readiness':refs[role]=emit(role+'.py',(ROOT/'comic_native_process_probe.py').read_bytes(),True)
            elif role=='scope_projection':refs[role]=dict(path=str(ROOT/'publication_native_configured_scope.py'),sha256=P.SCOPE_SHA)
            elif role=='hardlink_kernel':refs[role]=dict(path=str(ROOT/'comic_negative_nfs_hardlink_probe.py'),sha256=P.HARDLINK_KERNEL_SHA)
            elif role=='readiness_input':refs[role]=emit(role+'.json',dict(version=1,nonce='a'*64,source_sha256=P.CHECKED_PROBE_SHA,seconds=30,module_pins={},scope_source='fixture only; not executed'))
            elif role=='native_map':refs[role]=emit(role+'.json',{'fixture':'map'})
            elif role=='selected_sdk':refs[role]=emit(role+'.json',{'modules':{str(i):{'fixture_only':True} for i in range(25)},'parent_sha256':None})
            else:refs[role]=emit(role+'.py',b'# explicit fixture source, never executed\n',True)
        images={role:'sha256:'+char*64 for role,char in [('native','a'),('selected','b'),('reader','c'),('worker','d')]}
        parent=dict(path=P.__file__,sha256=P.digest(Path(P.__file__).read_bytes()))
        logs={role:emit(role+'.log',b'explicit fake selected-runtime receipt, not actual image\n') for role in ('stdout','stderr')}
        receipt=dict(kind='owned-nfs-current-source-fixture-readiness',images=images,parent_sha256=parent['sha256'],source_pins={k:v['sha256'] for k,v in refs.items()},
                     exit_code=0,zero_skips=True,count=1,actual_nfs_verified=False,native_grant=False,publication_authority=False,library_support_verified=False,**logs)
        if fault=='receipt-grant':receipt['actual_nfs_verified']=True
        if fault=='old-image':receipt['images']=dict(images,selected=images['native'])
        receipt_ref=emit('receipt.json',receipt)
        writer=base/'writer';writer.mkdir(mode=0o700)
        value=dict(version=1,kind='approved-disposable-nfs-current-source-cohort',images=images,sources=refs,writer_root=str(writer),writer_sha256=refs['writer']['sha256'],
                   native_map_count=1,selected_module_count=25,parent=parent,receipt=receipt_ref,logs=logs,effective_jar_sha256='e'*64,effective_commit='f'*40)
        if fault=='writer-pin':value['writer_sha256']='0'*64
        if fault=='old-map':value['selected_module_count']=69
        cohort_ref=emit('cohort.json',value)
        return cohort_ref,refs

    def test_first_source_fact_ancestor_change_not_adopted(self):
        ref,refs=self.make();original=P.fact;fired=[]
        def late(path,*args,**kwargs):
            result=original(path,*args,**kwargs)
            if str(path)==refs['probe']['path'] and not fired:
                Path(path).parent.chmod(0o750);fired.append(True)
            return result
        with patch.object(P,'fact',side_effect=late),self.assertRaisesRegex(P.Held,'cohort-ancestor-conflict'):
            P.SourceCohort(ref)
        self.assertTrue(fired)

    def test_first_receipt_read_source_ancestor_change_not_adopted(self):
        ref,refs=self.make();original=P.read;fired=[]
        def late(path,*args,**kwargs):
            result=original(path,*args,**kwargs)
            if Path(path).name=='receipt.json' and not fired:
                Path(refs['probe']['path']).parent.chmod(0o750);fired.append(True)
            return result
        with patch.object(P,'read',side_effect=late),self.assertRaisesRegex(P.Held,'cohort-ancestor-conflict'):
            P.SourceCohort(ref)
        self.assertTrue(fired)

    def test_same_bytes_first_source_replaced_before_fact_refuses(self):
        ref,refs=self.make();original=P.fact;fired=[]
        def late(path,*args,**kwargs):
            if str(path)==refs['probe']['path'] and not fired:
                p=Path(path);raw=p.read_bytes();p.unlink();p.write_bytes(raw);p.chmod(0o644);fired.append(True)
            return original(path,*args,**kwargs)
        with patch.object(P,'fact',side_effect=late),self.assertRaisesRegex(P.Held,'cohort-original-file-CAS'):
            P.SourceCohort(ref)
        self.assertTrue(fired)

    def test_distinct_native_selected_original_roles(self):
        ref,_=self.make();c=P.SourceCohort(ref)
        self.assertNotEqual(dict(c.images)['native'],dict(c.images)['selected']);c.close()

    def test_current_readiness_has_no_nfs_grant(self):
        ref,_=self.make('receipt-grant')
        with self.assertRaises(P.Held):P.SourceCohort(ref)

    def test_old_image_receipt_not_relabelled(self):
        ref,_=self.make('old-image')
        with self.assertRaises(P.Held):P.SourceCohort(ref)

    def test_old_selected69_map_not_relabelled(self):
        ref,_=self.make('old-map')
        with self.assertRaises(P.Held):P.SourceCohort(ref)

    def test_exact_writer_pin_required(self):
        ref,_=self.make('writer-pin')
        with self.assertRaises(P.Held):P.SourceCohort(ref)

    def test_original_source_incarnation_after_receipt(self):
        ref,refs=self.make();c=P.SourceCohort(ref)
        Path(refs['probe']['path']).chmod(0o640)
        with self.assertRaisesRegex(P.Held,'cohort-source-CAS'):c.close()

    def test_no_second_cohort_rebind(self):
        ref,_=self.make()
        with patch.object(P,'_COHORT',object()),self.assertRaisesRegex(P.Held,'source-cohort-no-rebind'):P.bind_cohort(ref)

class ReleaseControls(unittest.TestCase):
    def test_last_profile_source_change_prevents_release_write(self):
        with tempfile.TemporaryDirectory(prefix='nfs-release-local-') as d:
            base=Path(d);source=base/'source';source.write_bytes(b'original');source.chmod(0o600)
            original=tuple(P.stamp(source));r,w=os.pipe();stream=os.fdopen(w,'wb',buffering=0)
            lease=object.__new__(P.WriterLease);lease.token='a'*64
            lease.process=SimpleNamespace(stdin=stream);lease.pulse=lambda:None
            lease.profile=lambda:source.chmod(0o640)
            writes=[]
            try:
                with patch.object(P.os,'write',side_effect=lambda *args:writes.append(args)),self.assertRaisesRegex(P.Held,'lease-release-original-file'):
                    lease.release_after_absence((base/'absent',),original_files=((str(source),original),))
                self.assertEqual(writes,[])
            finally:stream.close();os.close(r)

class FreshProcessControls(LocalEnvironment):
    fixture=FullLifecycleControls.fixture
    def drift(self,role):
        original_fresh=P.fresh_native;original_write=P.write;phase=[]
        def emit(path,value):
            result=original_write(path,value)
            if Path(path).name=='acceptance.json' and Path(path).parent.name=='probe':phase.append(True)
            return result
        def fresh(call,cid):
            result=original_fresh(call,cid)
            if phase:result['process'][role]+=1
            return result
        with patch.object(P,'write',side_effect=emit),patch.object(P,'fresh_native',side_effect=fresh),self.assertRaisesRegex(P.Held,'post-probe-active-bracket'):
            self.fixture()
        self.assertTrue(phase)
    def test_native_process_startticks_change_refuses(self):self.drift('start_ticks')
    def test_native_daemon_pid_change_refuses(self):self.drift('pid')

class HardlinkChildProfileControls(LocalEnvironment):
    fixture=FullLifecycleControls.fixture
    def test_actual_kernel_through_checked_child_profile_and_owned_cleanup(self):self.fixture(use_core=True)
    def test_journal_copy_callback_cannot_refresh_original_child_root9(self):
        original=P.write;fired=[]
        def changed(path,value):
            result=original(path,value)
            if Path(path).name=='kernel-result.json' and not fired:
                root=Path(value['original_child_ref']['path']).parent
                foreign=root/'late-transient';foreign.write_bytes(b'foreign');foreign.unlink();fired.append(True)
            return result
        with patch.object(P,'write',changed),self.assertRaisesRegex(P.Held,'fixture-root-drift'):
            self.fixture(use_core=True)
        self.assertEqual(fired,[True])
    def test_terminal_exited_child_nonzero_PID_never_cleans_or_releases(self):
        original=P.json.loads;fired=[]
        def changed(raw,*args,**kwargs):
            value=original(raw,*args,**kwargs)
            if type(value) is list and len(value)==1 and value[0].get('Id')=='d'*64 and value[0].get('State',{}).get('Status')=='exited':
                value[0]['State']['Pid']=44;fired.append(True)
            return value
        with patch.object(P.json,'loads',changed),self.assertRaisesRegex(P.Held,'child-terminal'):
            self.fixture(use_core=True)
        self.assertEqual(fired,[True])
    def test_lost_actual_child_ACK_never_cleans_or_releases(self):
        events=self.fixture('lost-child-ack',use_core=True);self.assertIn('actual-kernel-ACK-lost',events)

class HardlinkCleanupFailureControls(LocalEnvironment):
    fixture=FullLifecycleControls.fixture
    def test_transient_cleanup_parent_FD_never_deletes_foreign(self):
        original=os.open;fired=[];foreign=[]
        def changed(path,flags,*args,**kwargs):
            if not isinstance(path,int) and Path(path).name=='source' and any(f.function=='cleanup_hardlink_owned' for f in inspect.stack()) and not fired:
                c=Path(path).parent;protected=c.parent.parent/'foreign-cleanup';protected.mkdir(mode=0o700)
                (protected/'source').mkdir(mode=0o700);(protected/'source'/'source.bin').write_bytes(b'foreign-preserve')
                saved=c.with_name(c.name+'-saved');c.rename(saved);c.symlink_to(protected,target_is_directory=True)
                try:fd=original(path,flags,*args,**kwargs)
                finally:c.unlink();saved.rename(c)
                foreign.append(protected/'source'/'source.bin');fired.append(True);return fd
            return original(path,flags,*args,**kwargs)
        with patch.object(L.os,'open',changed),self.assertRaisesRegex(L.Held,'hardlink-cleanup-original-FD'):
            self.fixture()
        self.assertEqual(fired,[True]);self.assertEqual(foreign[0].read_bytes(),b'foreign-preserve')
        # The fixture cleanup deletes only its TemporaryDirectory, never via the canary FD.
    def admitted_mode_drift(self,grandparent):
        original=P.read;fired=[]
        def changed(path,expected=None):
            value=original(path,expected)
            if Path(path).name=='acceptance.json' and Path(path).parent.name=='probe' and not fired:
                fixture=Path(value[0]['fixture']);target=fixture.parent.parent if grandparent else fixture.parent
                target.chmod(0o750);fired.append(True)
            return value
        with patch.object(P,'read',changed),self.assertRaisesRegex(L.Held,'hardlink-cleanup-original-parent-node'):
            self.fixture(use_core=True)
        self.assertEqual(fired,[True])
    def test_original_staging_parent_mode_after_coreACK_never_releases(self):self.admitted_mode_drift(False)
    def test_original_grandparent_mode_after_coreACK_never_releases(self):self.admitted_mode_drift(True)
    def test_lost_cleanup_fsync_never_releases(self):
        original=os.fsync;fired=[]
        def changed(fd):
            original(fd)
            if any(f.function=='cleanup_hardlink_owned' for f in inspect.stack()) and not fired:
                fired.append(True);raise L.Held('explicit-lost-cleanup-fsync-ACK')
        with patch.object(L.os,'fsync',changed),self.assertRaisesRegex(L.Held,'explicit-lost-cleanup-fsync-ACK'):
            self.fixture()
        self.assertEqual(fired,[True])

class RefusalACKControls(unittest.TestCase):
    def test_parent_actual_cli_missing_current_cohort_all_acceptance_false(self):
        with tempfile.TemporaryDirectory(prefix='nfs-cli-local-only-') as d:
            p=Path(d)/'plan.json';p.write_bytes(b'{}');p.chmod(0o600)
            result=subprocess.run(['python','-I','-B',P.__file__,'--execute','--input',str(p),'--input-sha256',P.digest(p.read_bytes()),'--source-sha256',P.digest(Path(P.__file__).read_bytes())],capture_output=True,check=False)
            self.assertEqual(result.returncode,2)
            value=json.loads(result.stdout)
            for key in ('probe_verified','disposable_probe_verified','platform_supported','owned_fixture_absence_verified','actual_library_platform_verified','native_grant','publication_authority'):
                self.assertIs(value[key],False)

if __name__=='__main__':unittest.main()
