"""Real files/backup/request construction; explicit Docker/HTTP response doubles.

No daemon/schema, installed factory, NFS or bootstrap runtime acceptance is
claimed. In particular the full entry must refuse our missing native database.
"""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import urllib.parse
import zipfile

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import genuine_application_bootstrap as b
import genuine_bootstrap_http as h
import genuine_reader_quiescence as q


def private(path, raw):
    path.write_bytes(raw); path.chmod(0o600)
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), signature9=b.p.nine(path.stat()))


class Engine:
    """Response boundary only; never claimed to be a genuine Docker object."""
    def __init__(self, plan, sdk):
        self.plan = plan; self.sdk = sdk; self.rows = {}
        for role, original in plan['roles'].items():
            self.rows[original['id']] = dict(copy.deepcopy(original['profile']), State=copy.deepcopy(original['epoch']))
        self.network = copy.deepcopy(plan['network']['profile']); self.calls = []; self.fail = None; self.created = False; self.progress = False
    def mount(self, path, seconds):
        return copy.deepcopy(self.plan['nfs_mount'])
    def run(self, args, seconds, data=None):
        self.calls.append(tuple(args[:2]))
        if args[0]=='exec' and args[-2:]==['sha256sum',q.JAR]:return (q.JAR_SHA+'  '+q.JAR+'\n').encode()
        if args[0]=='exec' and args[10:]==['--disposable-reader-queue-v1',self.plan['nonce'],self.plan['roles']['native']['id']]:
            q.request(b.p.decode(data));self.calls.append(('queue','stream'))
            if self.fail=='queue':raise b.Held('injected-queue-reply-lost')
            change=getattr(self,'queue_change',None)
            if change is not None:change()
            return b.p.encode(dict(queue_empty_observed=True,zero_events=2,separation_ms=10000,elapsed_ms=11000,frames=2,lines=6,bytes=140))
        if args[0] == 'inspect':return b.p.encode([self.rows[args[1]]])
        if args[:2] == ['network', 'inspect']:return b.p.encode([self.network])
        if args[0] == 'restart':
            assert args==['restart','--timeout','30',self.plan['roles']['native']['id']]
            if self.fail == 'restart':raise b.Held('injected-restart-response-lost')
            row = self.rows[args[-1]]; row['State'].update(StartedAt='own-new-epoch', Pid=999)
            row['NetworkSettings']['SandboxID'] = 'own-new-sandbox'
            row['NetworkSettings']['Networks']['private']['EndpointID'] = 'own-new-endpoint'
            self.network['Containers'][args[-1]]['EndpointID'] = 'own-new-endpoint'
            return args[-1].encode()
        if args[0] == 'exec' and args[-1] == b.IMAGE_PROGRAM:return b.p.encode(self.sdk)
        if args[0]=='exec' and args[-1]==Path(self.plan['native_probe']['path']).read_text():
            return b.p.encode(dict(version=1,nonce=self.plan['nonce'],source_sha256=self.plan['native_probe']['sha256'],config=dict(self.plan['native_ini'],path='/config/config.ini'),publication=dict(state='held')))
        if args[0] != 'exec':raise AssertionError(args)
        value = b.p.decode(data); h.request(value); operation = value['operation']
        self.calls.append(('http', operation))
        if self.fail == operation:raise b.Held('injected-' + operation + '-response-lost')
        if value['kind'] == 'native':
            if operation == 'prepare-fresh':result = dict(outcome='prepared', token='f' * 64)
            elif operation == 'initialize-bootstrap':result = dict(outcome='committed', token=value['arguments']['token'])
            else:result = dict(publication=dict(state='ready'))
            return b.p.encode(dict(result=dict(success=True, data=result)))
        library = dict(id='library', root=self.plan['geometry']['library']['path'], scanOnStartup=False,
                       scanInterval='DISABLED', emptyTrashAfterScan=False, convertToCbz=False,
                       repairExtensions=False, scanForceModifiedTime=False, scanDirectoryExclusions=[], unavailable=False)
        if operation == 'principal':result = dict(id='user', roles=['ADMIN'], sharedAllLibraries=True, sharedLibrariesIds=[], labelsAllow=[], labelsExclude=[])
        elif operation == 'libraries':result = [library] if self.created else []
        elif operation == 'create-library':self.created = True; result = library
        elif operation == 'scan':result = None
        elif operation == 'set-progress':self.progress = True; result = None
        else:
            files = sorted((Path(library['root']) / 'Fixture Series').glob('*.cbz'))
            books = [dict(id='book' + str(n), url=path.as_uri(), libraryId='library', media=dict(status='READY'),
                          readProgress=dict(page=1, completed=False) if self.progress and n == 0 else None) for n, path in enumerate(files)]
            if operation == 'books':result = dict(content=books, totalElements=len(books))
            else:
                number = int(value['arguments']['book'][-1]); book = books[number]
                with zipfile.ZipFile(files[number]) as archive:
                    names = sorted(n for n in archive.namelist() if n.endswith('.png'))
                    if operation == 'pages':result = [dict(number=n + 1, fileName=name) for n, name in enumerate(names)]
                    elif operation == 'page':
                        raw = archive.read(names[value['arguments']['page'] - 1]); result = dict(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
                    elif operation == 'book':result = book
                    else:raise AssertionError(operation)
        return b.p.encode(dict(result=result))


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.base = Path(self.temp.name)
        nonce = 'a' * 64; root = self.base / ('archive-bootstrap-' + nonce); root.mkdir(mode=0o700)
        geometry = self.base / ('archive-publication-' + nonce); geometry.mkdir(mode=0o700)
        for path in (root / 'native', root / 'reader', root / 'worker', geometry / 'L', geometry / 'R'):
            path.mkdir(mode=0o700)
            if os.geteuid() == 0:os.chown(path, 1000, 1000)
        if os.geteuid() == 0:
            os.chown(root, 1000, 1000); os.chown(geometry, 1000, 1000)
        ini = root / 'native/config.ini'; native_ini = private(ini, ('[API]\napi_enabled=1\napi_key=' + 'K' * 32 + '\n[Interface]\nhttp_port=8090\nhttp_root=/\nenable_https=0\n[General]\ndestination_dir=' + str(geometry / 'L') + '\n').encode())
        if os.geteuid() == 0:os.chown(ini, 1000, 1000); native_ini['signature9'] = b.p.nine(ini.stat())
        self.sdk = dict.fromkeys(b.REQUIRED_SDK, 'b' * 64)
        scope_path=HERE/'publication_native_configured_scope.py';self.sdk['publication_native_configured_scope.py']=hashlib.sha256(scope_path.read_bytes()).hexdigest()
        sdk = private(self.base / 'sdk.json', b.p.encode(self.sdk)); credentials = private(self.base / 'credentials.json', b.p.encode(dict(api_key='PRIVATE-READER-KEY')))
        helper_path = HERE / 'genuine_bootstrap_http.py'; helper = dict(path=str(helper_path.resolve()), sha256=hashlib.sha256(helper_path.read_bytes()).hexdigest(), signature9=b.p.nine(helper_path.stat()))
        roles = {}; ids = {role: c * 64 for role, c in (('native', '1'), ('reader', '2'), ('worker', '3'))}; network_id = '4' * 64
        mounts = {'native': [(root / 'native', '/config', True), (geometry / 'L', str(geometry / 'L'), True)],
                  'reader': [(root / 'reader', '/config', True), (geometry / 'L', str(geometry / 'L'), False)],
                  'worker': [(root / 'worker', '/state', True), (root / 'native', '/mylar', False), (geometry / 'L', '/data/comics', True)]}
        for role, cid in ids.items():
            image = 'sha256:' + cid
            row = dict(Id=cid, Name='/archive-bootstrap-' + nonce[:16] + '-' + role, Image=image, Path='/fixture', Args=[],
                       Config=dict(Labels={b.LABEL: nonce, b.PURPOSE: 'genuine-archive-fixture'}),
                       HostConfig=dict(Privileged=False, Devices=[], DeviceRequests=[], PortBindings={}, NetworkMode='private'),
                       Mounts=[dict(Source=str(source), Destination=target, RW=write, Type='bind') for source, target, write in mounts[role]],
                       NetworkSettings=dict(Ports={}, SandboxID='original-sandbox', Networks=dict(private=dict(NetworkID=network_id, Aliases=['reader-fixture'] if role == 'reader' else [], EndpointID='original-endpoint'))))
            epoch = dict(Status='created' if role == 'worker' else 'running', Running=role != 'worker', Pid=0 if role == 'worker' else 123, StartedAt='original', Paused=False, Restarting=False, Dead=False, OOMKilled=False)
            roles[role] = dict(id=cid, image=image, profile=row, epoch=epoch)
        def ref(path):return dict(path=str(path), signature9=b.p.nine(path.stat()))
        native_probe_path=HERE/'comic_native_process_probe.py'
        native_probe=dict(path=str(native_probe_path.resolve()),sha256=hashlib.sha256(native_probe_path.read_bytes()).hexdigest(),signature9=b.p.nine(native_probe_path.stat()))
        scope_source=dict(path=str(scope_path.resolve()),sha256=self.sdk['publication_native_configured_scope.py'],signature9=b.p.nine(scope_path.stat()))
        self.plan = dict(version=1, kind='approved-disposable-application-bootstrap', nonce=nonce, observed=int(time.time()), seconds=60,
                         state_root=ref(root), geometry=dict(version=1, kind='private-common-root-nfs', common_root=ref(geometry), library=ref(geometry / 'L'), retention=ref(geometry / 'R')),
                         roles=roles, images={k: v['image'] for k, v in roles.items()},
                         network=dict(id=network_id, profile=dict(Id=network_id, Internal=True, Driver='bridge', Labels={b.LABEL: nonce, b.PURPOSE: 'genuine-archive-fixture'}, Containers={ids[k]: dict(EndpointID='original-endpoint') for k in ('native', 'reader')})),
                         native_sdk=sdk, native_ini=native_ini, helper=helper, native_probe=native_probe, scope_source=scope_source, nfs_mount=dict(id=123,source='example.invalid:/disposable',target=str(geometry),fstype='nfs4',fsroot='/',options='rw,vers=4.2',**{'maj:min':str(os.major(geometry.stat().st_dev))+':'+str(os.minor(geometry.stat().st_dev))}), reader_credentials=credentials, reader_host='reader-fixture', reader_port=25600)
    def session(self):
        engine = Engine(self.plan, self.sdk); session = b.Bootstrap(self.plan, engine)
        self.addCleanup(b.p.close_common_root, session.geometry)
        return session, engine
    def test_default_run_refuses_before_any_engine_or_file_access(self):
        with patch.object(b, 'Docker', side_effect=AssertionError('engine accessed')), self.assertRaisesRegex(b.Held, 'activation-required'):
            b.run(None, None)
    def test_default_cli_and_missing_prerequisites_are_not_success_or_skip(self):
        for args in ([], ['--activate']):
            result = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'genuine_application_bootstrap.py'), *args], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 2); self.assertIn(b'bootstrap-held', result.stdout)
            self.assertNotIn(b'PRIVATE-READER-KEY', result.stdout + result.stderr)
    def test_production_name_purpose_or_unaccepted_image_refuses(self):
        for field, value in (('Name', '/mylar3'), ('Image', 'sha256:' + 'f' * 64)):
            plan = copy.deepcopy(self.plan); plan['roles']['native']['profile'][field] = value
            with self.subTest(field=field), self.assertRaises(b.Held):b.plan(plan)
        plan = copy.deepcopy(self.plan); plan['roles']['reader']['profile']['Config']['Labels'][b.PURPOSE] = 'production'
        with self.assertRaisesRegex(b.Held, 'disposable-role-purpose'):b.plan(plan)
    def test_original_profiles_ports_foreign_mounts_epoch_and_alias_are_checked(self):
        for change in ('port', 'mount', 'epoch', 'alias', 'privilege'):
            session, engine = self.session(); row = engine.rows[self.plan['roles']['native']['id']]
            if change == 'port':row['HostConfig']['PortBindings'] = {'8090/tcp': [{'HostPort': '8090'}]}
            elif change == 'mount':row['Mounts'][0]['Source'] = '/production'
            elif change == 'epoch':row['State']['StartedAt'] = 'foreign'
            elif change == 'privilege':row['HostConfig']['Privileged'] = True
            else:engine.rows[self.plan['roles']['reader']['id']]['NetworkSettings']['Networks']['private']['Aliases'] = ['foreign']
            with self.subTest(change=change), self.assertRaises(b.Held):session.roles()
    def test_real_multisection_config_and_duplicate_or_wrong_section_refusal(self):
        session,_=self.session()
        self.assertEqual(session.native_base,'http://127.0.0.1:8090')
        path=Path(self.plan['native_ini']['path']);original=path.read_bytes()
        for raw in (original.replace(b'[API]',b'[WrongAPI]'), original+b'api_key=duplicate\n', b'[DEFAULT]\nhttp_port=8090\n'+original):
            self.plan['native_ini']=private(path,raw)
            with self.assertRaises(b.Held):b.Bootstrap(self.plan,Engine(self.plan,self.sdk))
        self.plan['native_ini']=private(path,original)
    def test_nfs_original_fact_refuses_local_readonly_foreign_device_or_shadow(self):
        for field,value in (('fstype','ext4'),('options','ro,vers=4.2'),('maj:min','999:999'),('target','/foreign')):
            original=copy.deepcopy(self.plan);original['nfs_mount'][field]=value
            with self.subTest(field=field),self.assertRaises(b.Held):b.plan(original)
        session,engine=self.session()
        with patch.object(engine,'mount',side_effect=lambda path,seconds:dict(self.plan['nfs_mount'],id=999) if path==session.retention else copy.deepcopy(self.plan['nfs_mount'])):
            with self.assertRaisesRegex(b.Held,'changed-or-shadowed'):session.roles()
        self.assertEqual(engine.calls,[])
    def test_native_original_process_probe_config_mismatch_refuses(self):
        session,engine=self.session();original=engine.run
        def wrong(args,seconds,data=None):
            raw=original(args,seconds,data)
            if args[0]=='exec' and args[-1]==session.probe_program:
                value=b.p.decode(raw);value['config']['sha256']='f'*64;return b.p.encode(value)
            return raw
        with patch.object(engine,'run',side_effect=wrong),self.assertRaises(b.Held):session.native_original()
        self.assertFalse(any(call[0] in ('http','restart') for call in engine.calls))
    def test_original_config_backup_and_independent_restore_are_real(self):
        session, _ = self.session(); session.output.mkdir(mode=0o700)
        evidence = session.fresh_backup()
        self.assertTrue(b.p.digest(evidence['manifest_sha256'])); self.assertTrue(b.p.digest(evidence['restore_sha256']))
        self.assertEqual((session.output / 'native-restore/config.ini').read_bytes(), (session.data / 'config.ini').read_bytes())
        self.assertFalse((session.data / 'mylar.db').exists()); self.assertFalse((session.data / 'media-writer').exists())
    def test_existing_native_state_never_uses_fresh_genesis(self):
        session, engine = self.session(); session.output.mkdir(mode=0o700); (session.data / 'mylar.db').write_bytes(b'original')
        with self.assertRaisesRegex(b.Held, 'must-be-virgin'):session.native()
        self.assertFalse(any(call[0] == 'http' for call in engine.calls))
    def test_lost_prepare_or_commit_reply_never_retries_or_restarts(self):
        for failure in ('prepare-fresh', 'initialize-bootstrap', 'restart'):
            case=BootstrapTests();case.setUp();self.addCleanup(case.doCleanups)
            session, engine = case.session(); session.output.mkdir(mode=0o700); engine.fail = failure
            with self.subTest(failure=failure), self.assertRaises(b.Held):session.native()
            actions = [call[1] for call in engine.calls if call[0] == 'http']
            self.assertEqual(actions.count('prepare-fresh'), 1)
            self.assertEqual(actions.count('initialize-bootstrap'), 0 if failure == 'prepare-fresh' else 1)
            self.assertEqual(sum(call[0] == 'restart' for call in engine.calls), int(failure == 'restart'))
            self.assertFalse((session.output / 'bootstrap.json').exists())
            # Each subcase has its own original fresh directories and evidence.
    def startup_refusal(self,publication,fail_write=False):
        session,engine=self.session();session.output.mkdir(mode=0o700);http=session.http
        session.http=lambda kind,op,*args:dict(publication=publication) if (kind,op)==('native','health') else http(kind,op,*args)
        put=b.put
        def write(path,value):
            if fail_write and path.name=='native-startup-refusal.json':raise OSError('diagnostic unavailable')
            return put(path,value)
        with patch.object(b.time,'sleep'),patch.object(b,'put',side_effect=write),self.assertRaisesRegex(b.Held,'native-startup-not-ready'):session.native()
        self.assertEqual(sum(call[0]=='restart' for call in engine.calls),1)
        self.assertFalse((session.output/'03-native-restart-done.json').exists())
        return session.output/'native-startup-refusal.json'
    def test_startup_refusal_retains_finite_original_readiness_categories(self):
        path=self.startup_refusal(dict(state='held',reason='writer-busy',census=None,private_payload='excluded'))
        value=json.loads(path.read_bytes());self.assertEqual(value,dict(kind='native-startup-readiness-refused',state='held',reason='writer-busy',census_shape='null',automatic_replay=False,reader_resume_authority=False))
    def test_startup_refusal_excludes_unknown_values_and_census_contents(self):
        path=self.startup_refusal(dict(state='private-state',reason='private-reason',census=dict(private='excluded')))
        value=json.loads(path.read_bytes());self.assertEqual((value['state'],value['reason'],value['census_shape']),('other','other','object'));self.assertNotIn('private',path.read_text())
    def test_startup_refusal_diagnostic_io_failure_preserves_original_hold(self):
        path=self.startup_refusal(dict(state='held',reason='writer-busy'),fail_write=True);self.assertFalse(path.exists())
    def test_startup_busy_waits_for_fresh_ready_before_catalog_check(self):
        session,engine=self.session();session.output.mkdir(mode=0o700);http=session.http;calls=[]
        responses=iter((b.ApplicationNotReady('starting'),dict(publication=dict(state='held',reason='writer-busy',census=None)),dict(publication=dict(state='ready'))))
        def observe(kind,operation,*args):
            if (kind,operation)!=('native','health'):return http(kind,operation,*args)
            calls.append(operation);value=next(responses)
            if isinstance(value,Exception):raise value
            return value
        session.http=observe
        with patch.object(b.time,'sleep'),self.assertRaisesRegex(b.Held,'native-catalog-not-stable'):session.native()
        self.assertEqual(len(calls),3)
        self.assertEqual(sum(call[0]=='restart' for call in engine.calls),1)
        self.assertFalse((session.output/'native-startup-refusal.json').exists())

    def test_startup_persistent_busy_is_bounded_without_another_restart(self):
        session,engine=self.session();session.output.mkdir(mode=0o700);http=session.http;calls=[]
        def observe(kind,operation,*args):
            if (kind,operation)!=('native','health'):return http(kind,operation,*args)
            calls.append(operation);return dict(publication=dict(state='held',reason='writer-busy',census=None))
        session.http=observe
        with patch.object(b.time,'sleep'),self.assertRaisesRegex(b.Held,'native-startup-not-ready'):session.native()
        self.assertEqual(len(calls),64)
        self.assertEqual(sum(call[0]=='restart' for call in engine.calls),1)
        self.assertEqual(json.loads((session.output/'native-startup-refusal.json').read_text())['reason'],'writer-busy')

    def rejected_startup_observation(self,publication):
        session,engine=self.session();session.output.mkdir(mode=0o700);http=session.http;calls=[]
        def observe(kind,operation,*args):
            if (kind,operation)!=('native','health'):return http(kind,operation,*args)
            calls.append(operation);return dict(publication=publication)
        session.http=observe
        with patch.object(b.time,'sleep'),self.assertRaisesRegex(b.Held,'native-startup-not-ready'):session.native()
        self.assertEqual(len(calls),1)
        self.assertEqual(sum(call[0]=='restart' for call in engine.calls),1)

    def test_startup_busy_does_not_retry_other_publication_holds(self):
        self.rejected_startup_observation(dict(state='held',reason='media-pending',census=None))

    def test_startup_busy_with_a_census_is_not_retried(self):
        self.rejected_startup_observation(dict(state='held',reason='writer-busy',census={}))

    def test_startup_busy_keeps_original_deadline(self):
        session,engine=self.session();session.output.mkdir(mode=0o700);http=session.http;calls=[]
        def observe(kind,operation,*args):
            if (kind,operation)!=('native','health'):return http(kind,operation,*args)
            session.seconds();calls.append(operation)
            return dict(publication=dict(state='held',reason='writer-busy',census=None))
        session.http=observe
        def elapsed(_):session.end=time.monotonic()-1
        with patch.object(b.time,'sleep',side_effect=elapsed),self.assertRaisesRegex(b.Held,'bootstrap-deadline'):session.native()
        self.assertEqual(len(calls),1)
        self.assertEqual(sum(call[0]=='restart' for call in engine.calls),1)
        self.assertFalse((session.output/'03-native-restart-done.json').exists())

    def test_real_entry_cannot_claim_success_without_actual_native_schema(self):
        session, engine = self.session()
        # execute owns its handles; remove our cleanup to avoid closing twice.
        with patch.object(b.p, 'close_common_root') as closed, self.assertRaisesRegex(b.Held, 'catalog-not-stable'):
            session.execute()
        closed.assert_called_once_with(session.geometry)
        self.assertTrue((session.output / 'held.json').exists()); self.assertFalse((session.output / 'bootstrap.json').exists())
        self.assertEqual([v[1] for v in engine.calls if v[0] == 'http'][-3:], ['prepare-fresh', 'initialize-bootstrap', 'health'])
        self.assertFalse(engine.created)
    def test_reader_producer_calls_real_request_builder_and_checks_all_pages_progress(self):
        session, engine = self.session(); session.output.mkdir(mode=0o700)
        with patch.object(b.time, 'sleep'):
            value = session.reader_state()
        self.assertEqual(len(value['books']), 2); self.assertEqual([len(v['hashes']) for v in value['books']], [3, 3])
        calls = [v[1] for v in engine.calls if v[0] == 'http']
        self.assertEqual(calls.count('create-library'), 1); self.assertEqual(calls.count('scan'), 1)
        self.assertEqual(calls.count('page'), 6); self.assertEqual(calls.count('set-progress'), 1)
        self.assertFalse((session.output / 'bootstrap.json').exists())
    def queue_fixture(self):
        session,engine=self.session();session.output.mkdir(mode=0o700)
        with patch.object(b.time,'sleep'):reader=session.reader_state()
        path=HERE/'genuine_reader_quiescence.py'
        helper=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=b.p.nine(path.stat()))
        return session,engine,reader,helper
    def test_original_reader_queue_stage_is_readonly_and_returns_false_authority(self):
        session,engine,reader,helper=self.queue_fixture()
        result=q.observe(session,helper,reader)
        self.assertTrue(result['observation']['queue_empty_observed'])
        for key in ('application_quiescence_verified','future_exclusion_verified','stop_authority','reader_resume_authority',
                    'publication_acceptance','mutation_authority','ordinary_import_verified','ordinary_ack_verified'):
            self.assertIs(result[key],False)
        self.assertEqual(engine.calls.count(('queue','stream')),1)
        self.assertFalse(any(v[0]in ('start','stop','restart')for v in engine.calls))
        self.assertNotIn('PRIVATE',json.dumps(result));self.assertFalse((session.output/'bootstrap.json').exists())
    def test_queue_session_plan_engine_and_credentials_tamper_refuses_before_stream(self):
        for fault in ('plan','engine','key','credentials'):
            case=BootstrapTests();case.setUp();self.addCleanup(case.doCleanups)
            session,engine,reader,helper=case.queue_fixture()
            if fault=='plan':session.plan['reader_host']='foreign'
            elif fault=='engine':session.engine=object()
            elif fault=='key':session.reader_key='PRIVATE-FOREIGN'
            else:Path(session.plan['reader_credentials']['path']).write_bytes(b.p.encode(dict(api_key='PRIVATE-FOREIGN')))
            with self.subTest(fault=fault),self.assertRaises(b.Held):q.observe(session,helper,reader)
            self.assertNotIn(('queue','stream'),engine.calls)
    def test_queue_role_epoch_or_library_tamper_after_reply_cannot_be_accepted(self):
        for fault in ('epoch','mount','library'):
            case=BootstrapTests();case.setUp();self.addCleanup(case.doCleanups)
            session,engine,reader,helper=case.queue_fixture()
            def change():
                row=engine.rows[session.plan['roles']['reader']['id']]
                if fault=='epoch':row['State']['Pid']+=1
                elif fault=='mount':row['Mounts'][1]['RW']=True
                else:reader['library']['root']='/foreign'
            engine.queue_change=change
            with self.subTest(fault=fault),self.assertRaises((b.Held,q.Held)):q.observe(session,helper,reader)
            self.assertEqual(engine.calls.count(('queue','stream')),1)
    def test_queue_helper_pin_and_missing_constructed_session_refuse(self):
        session,engine,reader,helper=self.queue_fixture();helper['sha256']='0'*64
        with self.assertRaises(b.Held):q.observe(session,helper,reader)
        with self.assertRaises(q.Held):q.observe(object(),helper,reader)
        bare=b.Bootstrap.__new__(b.Bootstrap)
        with self.assertRaisesRegex(b.Held,'original-bootstrap-queue-session'):bare.queue_originals()
        self.assertNotIn(('queue','stream'),engine.calls)
    def test_queue_lost_reply_has_one_request_and_no_partial_observation(self):
        session,engine,reader,helper=self.queue_fixture();engine.fail='queue'
        with self.assertRaises(b.Held):q.observe(session,helper,reader)
        self.assertEqual(engine.calls.count(('queue','stream')),1)
        self.assertFalse((session.output/'bootstrap.json').exists())
    def test_execute_orders_optional_queue_after_reader_and_preserves_all_false_flags(self):
        session,engine=self.session();path=HERE/'genuine_reader_quiescence.py'
        helper=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=b.p.nine(path.stat()))
        # Only the native initialization boundary is doubled here. This source
        # ordering regression cannot establish genuine full-schema startup.
        with patch.object(session,'native',return_value={'boundary_double':True}),patch.object(b.time,'sleep'),patch.object(b.p,'close_common_root'):
            result=b.p.decode(b.p.read(session.execute(reader_queue_helper=helper)))
        self.assertTrue(result['reader_task_empty_observation']['observation']['queue_empty_observed'])
        for key in ('native_catalog_processing_verified','task_quiescence_verified','installed_factories_verified',
                    'actual_nfs_verified','publication_acceptance','mutation_authority','automatic_replay'):
            self.assertIs(result[key],False)
        self.assertLess(engine.calls.index(('http','set-progress')),engine.calls.index(('queue','stream')))
        self.assertEqual(engine.calls.count(('queue','stream')),1)
    def test_native_install_source_mismatch_refuses_before_mutations(self):
        session, engine = self.session(); engine.sdk = dict(self.sdk, **{'publication_api.py': 'f' * 64})
        with patch.object(b.p, 'close_common_root'), self.assertRaisesRegex(b.Held, 'installed-source-parity'):session.execute()
        self.assertFalse(session.output.exists()); self.assertFalse(any(call[0] == 'http' for call in engine.calls))


    def restart_pair(self):
        native=self.plan['roles']['native']['id'];endpoint=self.plan['roles']['native']['profile']['NetworkSettings']['Networks']['private']
        endpoint['MacAddress']='02:11:22:33:44:55';self.plan['network']['profile']['Containers'][native]['MacAddress']=endpoint['MacAddress']
        session,engine=self.session();engine.run(['restart','--timeout','30',native],session.seconds())
        engine.rows[native]['NetworkSettings']['Networks']['private']['MacAddress']='02:aa:bb:cc:dd:ee'
        engine.network['Containers'][native]['MacAddress']='02:aa:bb:cc:dd:ee'
        return session,engine,native

    def test_own_restart_MAC_and_network_pair_commit_exact_successor(self):
        session,engine,native=self.restart_pair();before=copy.deepcopy((session.profiles,session.epochs,session.network_profile))
        session.roles(restarting=True)
        self.assertEqual(session.profiles['native'],b.p.static(engine.rows[native]))
        self.assertEqual(session.network_profile,engine.network)
        for role in ('reader','worker'):
            self.assertEqual(session.profiles[role],before[0][role]);self.assertEqual(session.epochs[role],before[1][role])
        session.roles()

    def test_restart_pair_refuses_unjoined_MAC_endpoint_and_foreign_fields_atomically(self):
        for fault in ('member-mac','member-endpoint','IP','alias','networkID','native-config','reader-member','extra-member','network-label'):
            with self.subTest(fault=fault):
                fixture=type(self)();fixture.setUp();self.addCleanup(fixture.doCleanups)
                session,engine,native=fixture.restart_pair();before=copy.deepcopy((session.profiles,session.epochs,session.network_profile))
                endpoint=engine.rows[native]['NetworkSettings']['Networks']['private']
                if fault=='member-mac':engine.network['Containers'][native]['MacAddress']='02:00:00:00:00:01'
                elif fault=='member-endpoint':engine.network['Containers'][native]['EndpointID']='foreign'
                elif fault=='IP':endpoint['IPAddress']='192.0.2.1'
                elif fault=='alias':endpoint['Aliases']=['foreign']
                elif fault=='networkID':endpoint['NetworkID']='foreign'
                elif fault=='native-config':engine.rows[native]['Config']['Foreign']='unapproved'
                elif fault=='reader-member':engine.network['Containers'][fixture.plan['roles']['reader']['id']]['MacAddress']='02:00:00:00:00:02'
                elif fault=='extra-member':engine.network['Containers']['f'*64]={'EndpointID':'foreign'}
                else:engine.network['Labels']['foreign']='unapproved'
                with self.assertRaises(b.Held):session.roles(restarting=True)
                self.assertEqual((session.profiles,session.epochs,session.network_profile),before)

    def test_restart_MAC_rejects_missing_malformed_multicast_or_mismatched_old_origin(self):
        session,engine,native=self.restart_pair();original=session.profiles['native'];projected=b.p.static(engine.rows[native]);oldnet=session.network_profile;newnet=engine.network
        for fault in ('missing','malformed','multicast','old-member','old-endpoint'):
            left,right,ln,rn=copy.deepcopy((original,projected,oldnet,newnet));ep=right['NetworkSettings']['Networks']['private']
            if fault=='missing':del rn['Containers'][native]['MacAddress']
            elif fault=='malformed':ep['MacAddress']=rn['Containers'][native]['MacAddress']='not-a-MAC'
            elif fault=='multicast':ep['MacAddress']=rn['Containers'][native]['MacAddress']='01:00:00:00:00:01'
            elif fault=='old-member':ln['Containers'][native]['MacAddress']='02:00:00:00:00:01'
            else:ln['Containers'][native]['EndpointID']='foreign'
            with self.subTest(fault=fault),self.assertRaises(b.Held):b.own_restart_successor(left,right,ln,rn,native)

    def test_MAC_refresh_is_not_an_ordinary_or_other_role_exception(self):
        session,engine,native=self.restart_pair();before=copy.deepcopy((session.profiles,session.epochs,session.network_profile))
        with self.assertRaises(b.Held):session.roles()
        self.assertEqual((session.profiles,session.epochs,session.network_profile),before)
        reader=self.plan['roles']['reader']['id'];engine.rows[reader]['NetworkSettings']['Networks']['private']['MacAddress']='02:00:00:00:00:02'
        with self.assertRaises(b.Held):session.roles(restarting=True)
        self.assertEqual((session.profiles,session.epochs,session.network_profile),before)


class HttpTests(unittest.TestCase):
    def value(self, **changes):
        return dict(dict(kind='reader', base='http://disposable-reader:25600', key='private-key', operation='principal', arguments={}, seconds=10), **changes)
    def test_native_exact_authenticated_post_form_and_no_key_in_url(self):
        outgoing, binary = h.request(self.value(kind='native', base='http://127.0.0.1:8090/prefix', key='K' * 32, operation='initialize-bootstrap', arguments=dict(token='a' * 64)))
        self.assertEqual(outgoing.method, 'POST'); self.assertEqual(outgoing.full_url, 'http://127.0.0.1:8090/prefix/api'); self.assertFalse(binary)
        form = urllib.parse.parse_qs(outgoing.data.decode()); self.assertEqual(set(form), {'cmd', 'apikey', 'request'})
        self.assertEqual(json.loads(form['request'][0]), dict(version=1, action='initialize-bootstrap', token='a' * 64))
    def test_reader_creation_disables_automatic_mutations_and_uses_actual_tag_fields(self):
        outgoing, _ = h.request(self.value(operation='create-library', arguments=dict(name='fixture', root='/fixture/L')))
        self.assertEqual(outgoing.method, 'POST'); self.assertTrue(outgoing.full_url.endswith('/api/v1/libraries'))
        body = json.loads(outgoing.data); self.assertEqual(body['scanInterval'], 'DISABLED')
        for field in ('scanOnStartup', 'convertToCbz', 'repairExtensions', 'emptyTrashAfterScan', 'scanForceModifiedTime'):self.assertIs(body[field], False)
    def test_finite_page_and_progress_requests(self):
        outgoing, binary = h.request(self.value(operation='page', arguments=dict(book='own-book', page=2)))
        self.assertTrue(binary); self.assertTrue(outgoing.full_url.endswith('/own-book/pages/2?contentNegotiation=false'))
        outgoing, _ = h.request(self.value(operation='set-progress', arguments=dict(book='own-book')))
        self.assertEqual(outgoing.method, 'PATCH'); self.assertEqual(json.loads(outgoing.data), dict(page=1, completed=False))
    def test_unknown_routes_selectors_redirects_or_native_remote_origins_refuse(self):
        for value in (self.value(operation='delete'), self.value(arguments={'url': '/foreign'}),
                      self.value(base='http://user:password@reader:25600'), self.value(operation='page', arguments=dict(book='../foreign', page=1)),
                      self.value(kind='native', base='http://remote:8090', key='K' * 32, operation='status')):
            with self.subTest(value=value['operation']), self.assertRaises(h.Held):h.request(value)
        with self.assertRaisesRegex(h.Held, 'redirect'):h.NoRedirect().redirect_request(None, None, None, None, None, None)
    def test_helper_refusal_never_echoes_private_inputs(self):
        value = self.value(operation='unknown', key='NEVER-PRINT-THIS-KEY')
        result = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'genuine_bootstrap_http.py')], input=h.encode(value), capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2); self.assertNotIn(b'NEVER-PRINT-THIS', result.stdout + result.stderr)


class OriginalReaderRoleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.library=Path(self.temp.name)
        self.rows=[];self.roles={'roles':{}}
        for role,char in (('native','1'),('worker','2'),('reader','3')):
            row=dict(Id=char*64,Name='/disposable-'+role,Image='sha256:'+char*64,Path='/fixture',Args=[],Config={},HostConfig={},NetworkSettings={},Mounts=[])
            if role=='reader':row['Mounts']=[dict(Source=str(self.library),Destination='/library',Type='bind')]
            row['State']=dict(Status='running' if role!='worker' else 'created',Running=role!='worker',Pid=100 if role!='worker' else 0)
            self.rows.append(row);self.roles['roles'][role]=dict(id=row['Id'],profile=b.p.static(row),epoch=copy.deepcopy(row['State']))
        user=dict(id='fixture-admin',roles=['ADMIN'],sharedAllLibraries=True,sharedLibrariesIds=[],labelsAllow=[],labelsExclude=[])
        library=dict(id='fixture-library',root='/library',scanOnStartup=False,scanInterval='DISABLED',emptyTrashAfterScan=False,convertToCbz=False,repairExtensions=False,scanForceModifiedTime=False,scanDirectoryExclusions=[],unavailable=False)
        self.documents=dict(user=user,libraries=[library],repeated_libraries=[copy.deepcopy(library)])
    def test_original_disposable_reader_name_maps_without_fact_renaming(self):
        before=copy.deepcopy((self.rows,self.roles))
        result=b.active.map_library_documents(self.documents,self.rows,[self.library],roles=self.roles)
        self.assertEqual(result['mapped_roots'],[str(self.library)]);self.assertEqual((self.rows,self.roles),before)
    def test_foreign_reader_id_profile_epoch_or_literal_name_never_falls_back(self):
        for change in ('id','profile','epoch'):
            rows=copy.deepcopy(self.rows)
            if change=='id':rows[-1]['Id']='f'*64;rows[-1]['Name']='/komga'
            elif change=='profile':rows[-1]['Name']='/komga'
            else:rows[-1]['State']['Pid']=999
            with self.subTest(change=change),self.assertRaises(b.active.Held):b.active.map_library_documents(self.documents,rows,[self.library],roles=self.roles)
    def test_legacy_selector_remains_exact_without_original_roles(self):
        rows=copy.deepcopy(self.rows);rows[-1]['Name']='/komga'
        self.assertEqual(b.active.map_library_documents(self.documents,rows,[self.library])['mapped_roots'],[str(self.library)])
        with self.assertRaises(StopIteration):b.active.map_library_documents(self.documents,self.rows,[self.library])
    def test_fresh_library_observation_carries_original_role_selection(self):
        query=dict(version=1,kind='approved-active-komga-library-query',configuration={},expected_base_url='http://fixture.invalid:25600')
        reply=dict(version=1,kind='parent-original-library-query',query_plan_sha256=b.active.digest(b.active.encode(query)),documents=self.documents,native_grant=False,publication_authority=False)
        result=b.active.fresh_libraries(query,self.rows,{},[self.library],roles=self.roles,library_observer=lambda:reply)
        self.assertEqual(result['mapped_roots'],[str(self.library)])
    def test_all_owning_pre_and_postlease_calls_forward_original_roles(self):
        tree=ast.parse(Path(b.active.__file__).read_text());function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_run_owned_lifecycle')
        calls=[n for n in ast.walk(function) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='fresh_libraries']
        self.assertEqual(len(calls),3)
        for call in calls:self.assertTrue(any(k.arg=='roles' and isinstance(k.value,ast.Name) and k.value.id=='roles' for k in call.keywords))


if __name__ == '__main__':
    unittest.main()
