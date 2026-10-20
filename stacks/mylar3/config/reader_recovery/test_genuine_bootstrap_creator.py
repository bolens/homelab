"""Real disposable files and original Bootstrap; engine/API responses are doubles.

No Docker, Polkit, NFS, native schema, daemon, ACK or factory acceptance is
claimed. The connected path must stop at the missing actual startup database.
"""
import ast
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import genuine_bootstrap_creator as c
import genuine_reader_quiescence as q

CONFIG_KEYS=('API_ENABLED API_KEY HTTP_PORT HTTP_ROOT ENABLE_HTTPS DESTINATION_DIR CACHE_DIR DDL_LOCATION CHECK_FOLDER LOG_DIR SECURE_DIR BACKUP_LOCATION ENABLE_META RENAME_FILES ENABLE_PRE_SCRIPTS ENABLE_EXTRA_SCRIPTS FILE_OPTS ENFORCE_PERMS CHMOD_FILE CHMOD_DIR POST_PROCESSING ENABLE_CHECK_FOLDER ENABLE_TORRENTS').split()


def ref(path):
    return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=c.p.nine(path.stat()))


def private(path,value):
    path.write_bytes(value if isinstance(value,bytes) else c.p.encode(value));path.chmod(0o600)
    return ref(path)


def tar(raw,name):
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w')as archive:
        entry=tarfile.TarInfo(name);entry.size=len(raw);archive.addfile(entry,io.BytesIO(raw))
    return stream.getvalue()


class DriverDouble:
    """Finite response boundary; never presented as an installed engine."""
    def __init__(self):
        self.owner=None;self.calls=[];self.rows={};self.network='4'*64;self.fail=None;self.ready=False;self.password=None;self.claimed=False;self.wrong_probe=False;self.status_failures=0
    def mount(self,path,seconds):return copy.deepcopy(self.owner.document['nfs_mount'])
    def docker(self,args,seconds,data=None):
        self.calls.append(copy.deepcopy(args));o=self.owner
        if self.fail==args[0] or self.fail==' '.join(args[:2]):raise c.p.Held('injected-lost-response')
        if args[:2]==['image','inspect']:return c.p.encode(next(v for v in o.metadata.values()if v[0]['Id']==args[2]))
        if args[:2]==['network','create']:return self.network.encode()
        if args[0]=='create':
            role=args[args.index('--name')+1].rsplit('-',1)[-1];cid={'native':'1','reader':'2','worker':'3'}[role]*64
            self.rows[cid]=dict(Id=cid,Name='/'+o.name(role),Image=o.document['images'][role]['id'],Path='/actual-default',Args=[],
                Config=dict(Labels={c.b.LABEL:o.nonce,c.b.PURPOSE:'genuine-archive-fixture'}),HostConfig=dict(Privileged=False,Devices=[],DeviceRequests=[],CapAdd=[],PortBindings={},NetworkMode='none'if role=='worker'else self.network),
                Mounts=[dict(Type='bind',Source=str(a),Destination=t,RW=w)for a,t,w in o.mounts(role)],NetworkSettings=dict(Ports={},SandboxID='original',Networks={}),
                State=dict(Status='created',Running=False,Pid=0,StartedAt='never',Paused=False,Restarting=False,Dead=False,OOMKilled=False))
            return cid.encode()
        if args[0]=='inspect':return c.p.encode([self.rows[args[1]]])
        if args[0]=='cp':
            path=args[1].split(':',1)[1];raw=o.config_source if path.endswith('config.py')else o.service_source
            return tar(raw,Path(path).name)
        if args[0]=='start':
            row=self.rows[args[1]];role='native'if args[1]=='1'*64 else 'reader';row['State'].update(Status='running',Running=True,Pid=123,StartedAt='started')
            row['NetworkSettings']['Networks']={'private':dict(NetworkID=self.network,Aliases=[o.reader_host]if role=='reader'else [],EndpointID='original')}
            return args[1].encode()
        if args[:2]==['network','inspect']:
            return c.p.encode([dict(Id=self.network,Internal=True,Driver='bridge',Labels={c.b.LABEL:o.nonce,c.b.PURPOSE:'genuine-archive-fixture'},Containers={cid:dict(EndpointID=row['NetworkSettings']['Networks']['private']['EndpointID'])for cid,row in self.rows.items()if row['State']['Running']})])
        if args[0]=='restart':
            self.ready=True;row=self.rows[args[-1]];row['State'].update(Pid=456,StartedAt='restarted');return args[-1].encode()
        if args[0]=='exec' and args[-2:]==['sha256sum',c.JAR]:return (c.JAR_SHA+'  '+c.JAR+'\n').encode()
        if args[0]=='exec' and 'reader_queue'in o.raw and args[9]==o.raw['reader_queue'].decode():
            if self.fail=='queue':raise c.p.Held('injected-queue-response-lost')
            q.request(c.p.decode(data))
            return c.p.encode(dict(queue_empty_observed=True,zero_events=2,separation_ms=10000,elapsed_ms=11000,frames=2,lines=6,bytes=140))
        if args[0]=='exec' and args[9]==c.ENROLL_PROGRAM:
            value=c.p.decode(data);operation=value['operation']
            if self.fail=='enroll-'+operation:raise c.p.Held('injected-enrollment-reply-lost')
            if operation=='status':
                if self.status_failures:self.status_failures-=1;raise c.p.Held('not-ready')
                return c.p.encode(dict(isClaimed=self.claimed))
            if operation=='claim':self.claimed=True;self.password=value['password'];return c.p.encode(dict(id='fixture-user',roles=['ADMIN'],sharedAllLibraries=True,sharedLibrariesIds=[],labelsAllow=[],labelsExclude=[]))
            if operation=='key':return c.p.encode(dict(userId='fixture-user',comment='bootstrap-'+o.nonce,key='PRIVATE-FIXTURE-KEY'))
        if args[0]=='exec' and args[9]==c.b.IMAGE_PROGRAM:return c.p.encode(o.sdk)
        if args[0]=='exec' and args[9]==o.raw['probe'].decode():
            path=o.data/'config.ini'
            return c.p.encode(dict(version=1,nonce=o.nonce,source_sha256=o.document['sources']['probe']['sha256'],process=dict(pid=123,start_ticks=1,argv=['foreign']if self.wrong_probe else o.contract['argv']),
                config=dict(ref(path),path=o.child_data+'/config.ini'),publication=dict(state='ready'if self.ready else 'held')))
        if args[0]=='exec' and args[9]==o.raw['http'].decode():
            value=c.p.decode(data);c.http.request(value);operation=value['operation']
            if value['kind']=='reader':
                result={'principal':dict(id='fixture-user',roles=['ADMIN'],sharedAllLibraries=True,sharedLibrariesIds=[],labelsAllow=[],labelsExclude=[]),'libraries':[],'books':dict(totalElements=0)}[operation]
            else:
                result=dict(success=True,data=dict(publication=dict(state='ready'if self.ready else 'held')))
                if operation in ('prepare-fresh','initialize-bootstrap'):result=dict(success=True,data=dict(outcome='prepared'if operation=='prepare-fresh'else 'committed',token='f'*64))
            return c.p.encode(dict(result=result))
        raise AssertionError(args[:6])


class CreatorTests(unittest.TestCase):
    def setUp(self):
        self.base=tempfile.TemporaryDirectory();self.addCleanup(self.base.cleanup);self.proofs=Path(self.base.name)
        # Two real disposable local devices model the local/NFS device join.
        # DriverDouble's declared NFS response is not actual NFS evidence.
        self.local=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.local.cleanup);self.remote=tempfile.TemporaryDirectory();self.addCleanup(self.remote.cleanup)
        state=Path(self.local.name);remote=Path(self.remote.name);nonce='a'*64
        self.config_source=('_CONFIG_DEFINITIONS = {'+','.join(repr(k)+': (str, '+repr('API'if k.startswith('API_')else'Interface'if k in ('HTTP_PORT','HTTP_ROOT','ENABLE_HTTPS')else'General')+', None)'for k in CONFIG_KEYS)+'}\n').encode()
        self.service_source=b'#!/command/with-contenv bash\nexec python3 /app/mylar3/Mylar.py --datadir /config/mylar --nolaunch\n'
        sdk=dict.fromkeys(c.b.REQUIRED_SDK|{'__init__.py','config.py','db.py','PostProcessor.py'},'b'*64);sdk['config.py']=hashlib.sha256(self.config_source).hexdigest();sdk['publication_native_configured_scope.py']=ref(HERE/'publication_native_configured_scope.py')['sha256']
        images={}
        for role,char in (('native','5'),('reader','6'),('worker','7')):
            image='sha256:'+char*64;images[role]=dict(id=image,metadata=private(self.proofs/(role+'.json'),[dict(Id=image,Os='linux',Architecture='amd64')]))
        contract=dict(version=1,kind='reviewed-image-data-precondition',image=images['native']['id'],relative='mylar',argv=['python3','/app/mylar3/Mylar.py','--datadir','/config/mylar','--nolaunch'],service_path='/etc/s6-overlay/s6-rc.d/svc-mylar3/run',service_sha256=hashlib.sha256(self.service_source).hexdigest())
        self.document=dict(version=1,kind='approved-disposable-three-role-creator',nonce=nonce,observed=int(c.time.time()),seconds=900,
            state_parent=c.Creator.directory_ref(state),nfs_parent=c.Creator.directory_ref(remote),nfs_mount=dict(id=123,source='example.invalid:/disposable',target=str(remote),fstype='nfs4',fsroot='/',options='rw,vers=4.2',**{'maj:min':str(os.major(remote.stat().st_dev))+':'+str(os.minor(remote.stat().st_dev))}),
            images=images,native_sdk=private(self.proofs/'sdk.json',sdk),data_contract=private(self.proofs/'data.json',contract),sources={k:ref(HERE/v)for k,v in c.SOURCES.items()})
    def creator(self):
        driver=DriverDouble()
        # Give the explicit double only its declared original mount fact during
        # constructor preflight; no production admission or factory is replaced.
        driver.owner=type('MountOwner',(),{'document':self.document})()
        owner=c.Creator(self.document,driver=driver);driver.owner=owner;owner.config_source=self.config_source;owner.service_source=self.service_source
        self.addCleanup(lambda:c.p.close_common_root(owner.geometry)if owner.geometry is not None else None)
        return owner,driver
    def queue_call(self,owner):
        args=['exec','--interactive','--user','1000:1000',owner.engine.ids['native'],'/lsiopy/bin/python3','-I','-B','-c',
              (HERE/'genuine_reader_quiescence.py').read_text(),'--disposable-reader-queue-v1',owner.nonce,owner.engine.ids['native']]
        value=dict(version=1,nonce=owner.nonce,native_cid=owner.engine.ids['native'],base='http://'+owner.reader_host+':25600',key=owner.reader_key,seconds=30)
        return args,value
    def test_v1_source_schema_and_engine_refuse_queue_extension(self):
        owner,driver=self.creator();owner.prepare();args,value=self.queue_call(owner);before=len(driver.calls)
        with self.assertRaisesRegex(c.p.Held,'undeclared-creator-program'):owner.engine.run(args,30,c.p.encode(value))
        self.assertEqual(len(driver.calls),before)
        document=copy.deepcopy(self.document);document['sources']['reader_queue']=ref(HERE/'genuine_reader_quiescence.py')
        with self.assertRaisesRegex(c.p.Held,'source-closure'):c.Creator(document,driver=driver)
    def test_v2_requires_exact_helper_source_before_directories_or_engine(self):
        self.document['version']=2
        with self.assertRaisesRegex(c.p.Held,'source-closure'):self.creator()
        self.document['sources']['reader_queue']=ref(HERE/'genuine_reader_quiescence.py');self.document['sources']['reader_queue']['sha256']='0'*64
        with self.assertRaises(c.p.Held):self.creator()
    def test_v2_one_readonly_queue_call_and_two_exact_jar_reads(self):
        self.document['version']=2;self.document['sources']['reader_queue']=ref(HERE/'genuine_reader_quiescence.py')
        owner,driver=self.creator();owner.prepare();args,value=self.queue_call(owner)
        result=c.p.decode(owner.engine.run(args,30,c.p.encode(value)))
        self.assertTrue(result['queue_empty_observed']);before=len(driver.calls)
        with self.assertRaisesRegex(c.p.Held,'call-budget'):owner.engine.run(args,30,c.p.encode(value))
        self.assertEqual(len(driver.calls),before)
        jar=['exec','--user','1000:1000',owner.engine.ids['reader'],'sha256sum',c.JAR]
        for _ in range(2):self.assertIn(c.JAR_SHA.encode(),owner.engine.run(jar,30))
        with self.assertRaisesRegex(c.p.Held,'call-budget'):owner.engine.run(jar,30)
        self.assertEqual(owner.engine.started,{'native','reader'});self.assertFalse(owner.engine.poisoned)
        self.assertFalse(any(call[0]in ('rm','stop')for call in driver.calls))
    def test_v2_wrong_queue_origin_key_selector_or_program_never_reaches_driver(self):
        self.document['version']=2;self.document['sources']['reader_queue']=ref(HERE/'genuine_reader_quiescence.py')
        owner,driver=self.creator();owner.prepare();args,value=self.queue_call(owner);before=len(driver.calls)
        for change in ({'base':'http://foreign:25600'},{'key':'PRIVATE-FOREIGN'},{'native_cid':'f'*64},{'nonce':'f'*64}):
            with self.assertRaises((c.p.Held,q.Held)):owner.engine.run(args,30,c.p.encode(dict(value,**change)))
        for index,changed in ((9,'print("foreign")'),(4,owner.engine.ids['reader']),(-1,'f'*64)):
            alternate=list(args);alternate[index]=changed
            with self.assertRaises(c.p.Held):owner.engine.run(alternate,30,c.p.encode(value))
        self.assertEqual(len(driver.calls),before)
    def test_v2_unknown_readonly_reply_is_not_replayed_or_upgraded(self):
        self.document['version']=2;self.document['sources']['reader_queue']=ref(HERE/'genuine_reader_quiescence.py')
        owner,driver=self.creator();owner.prepare();args,value=self.queue_call(owner);driver.fail='queue'
        with self.assertRaises(c.p.Held):owner.engine.run(args,30,c.p.encode(value))
        before=len(driver.calls)
        with self.assertRaisesRegex(c.p.Held,'call-budget'):owner.engine.run(args,30,c.p.encode(value))
        self.assertEqual(len(driver.calls),before);self.assertFalse(owner.engine.poisoned)
    def test_v2_original_bootstrap_constructor_receives_bound_helper_without_grants(self):
        self.document['version']=2;self.document['sources']['reader_queue']=ref(HERE/'genuine_reader_quiescence.py')
        owner,_=self.creator();observed=[]
        def boundary(session,**options):
            self.assertIs(type(session),c.b.Bootstrap);session.queue_originals();observed.append(options)
            # Source forwarding only; genuine startup/processing is not run.
            c.p.close_common_root(session.geometry)
            return dict(boundary_double=True)
        with patch.object(c.b.Bootstrap,'execute',boundary):result=owner.execute()
        self.assertEqual(observed,[dict(native_catalog_helper=self.document['sources']['catalog_helper'],reader_queue_helper=self.document['sources']['reader_queue'])])
        for key in ('installed_factories_verified','publication_acceptance','actual_nfs_verified','ordinary_ack_verified',
                    'birth_verified','mutation_authority','reader_resume_authority','automatic_replay'):self.assertIs(result[key],False)
    def test_default_run_and_cli_refuse_before_engine_or_files(self):
        with patch.object(c,'Creator',side_effect=AssertionError('creator called')),self.assertRaises(c.p.Held):c.run(None)
        result=subprocess.run([sys.executable,'-I','-B',str(HERE/'genuine_bootstrap_creator.py')],capture_output=True,timeout=10)
        self.assertEqual(result.returncode,2);self.assertNotIn(b'PRIVATE',result.stdout+result.stderr)
    def test_no_root_actor_or_implicit_data_or_foreign_source(self):
        with patch.object(c.os,'geteuid',return_value=0),self.assertRaises(c.p.Held):self.creator()
        bad=copy.deepcopy(self.document);bad.pop('data_contract')
        with self.assertRaises(c.p.Held):c.Creator(bad,driver=DriverDouble())
        bad=copy.deepcopy(self.document);bad['sources']['scope']['path']='/foreign.py'
        with self.assertRaises(c.p.Held):c.Creator(bad,driver=DriverDouble())
    def test_complete_prepare_constructs_actual_bootstrap_without_factory_substitution(self):
        owner,driver=self.creator();plan=owner.prepare()
        session=c.b.Bootstrap(plan,owner.engine);self.addCleanup(c.p.close_common_root,session.geometry)
        session.roles();self.assertEqual(session.installed_sources(),owner.sdk);session.native_original()
        self.assertEqual(set(owner.engine.ids),{'native','reader','worker'});self.assertEqual(owner.engine.started,{'native','reader'})
        self.assertEqual(driver.rows[owner.engine.ids['worker']]['State']['Status'],'created')
        self.assertEqual(plan['native_ini']['path'],str(owner.data/'config.ini'));self.assertEqual(plan['roles']['reader']['id'],'2'*64)
        self.assertEqual(owner.reader_key,'PRIVATE-FIXTURE-KEY');self.assertTrue((owner.journal/'reader-key.json').exists())
        self.assertEqual([a[0]for a in driver.calls].count('create'),3);self.assertEqual([a[0]for a in driver.calls].count('start'),2)
        self.assertTrue(all('--pull'in a and a[a.index('--pull')+1]=='never'for a in driver.calls if a[0]=='create'))
    def test_connected_entry_reaches_original_missing_schema_refusal_not_green(self):
        owner,driver=self.creator()
        with self.assertRaises((sqlite3.Error,FileNotFoundError,c.p.Held)):owner.execute()
        self.assertTrue((owner.journal/'held.json').exists());self.assertFalse((owner.data/'mylar.db').exists())
        self.assertEqual(sum(a[0]=='restart'for a in driver.calls),1)
        self.assertFalse(any(a[0]in ('rm','remove')for a in driver.calls))
    def test_unknown_network_create_poison_prevents_adoption_or_second_call(self):
        owner,driver=self.creator();driver.fail='network create'
        with self.assertRaises(c.p.Held):owner.execute()
        before=len(driver.calls)
        with self.assertRaises(c.p.Held):owner.engine.create_network()
        self.assertEqual(len(driver.calls),before);self.assertEqual(owner.engine.ids,{})
        self.assertTrue((owner.journal/'held.json').exists())
    def test_unknown_start_never_starts_worker_or_retries(self):
        owner,driver=self.creator();driver.fail='start'
        with self.assertRaises(c.p.Held):owner.execute()
        self.assertEqual(sum(a[0]=='start'for a in driver.calls),1)
        self.assertEqual(owner.engine.started,set())
    def test_lost_claim_or_key_reply_is_held_without_reenrollment(self):
        for action in ('claim','key'):
            with self.subTest(action=action):
                case=CreatorTests();case.setUp()
                try:
                    owner,driver=case.creator();driver.fail='enroll-'+action
                    with self.assertRaises(c.p.Held):owner.execute()
                    self.assertEqual(owner.engine.counts['enroll-'+action],1)
                    self.assertTrue((owner.journal/'held.json').exists());self.assertFalse((owner.journal/'reader-key.json').exists())
                finally:case.doCleanups()
    def test_readonly_enrollment_readiness_can_retry_only_status(self):
        owner,driver=self.creator();driver.status_failures=1
        with patch.object(c.time,'sleep'):owner.prepare()
        self.assertEqual(owner.engine.counts['enroll-status'],2);self.assertEqual(owner.engine.counts['enroll-claim'],1);self.assertEqual(owner.engine.counts['enroll-key'],1)
    def test_foreign_process_refuses_before_claim(self):
        owner,driver=self.creator();driver.wrong_probe=True
        with self.assertRaises(c.p.Held):owner.execute()
        self.assertNotIn('enroll-claim',owner.engine.counts);self.assertFalse(driver.claimed)
    def test_original_image_metadata_or_copied_sources_must_match_before_start(self):
        for change in ('image','service','config'):
            with self.subTest(change=change):
                case=CreatorTests();case.setUp()
                try:
                    owner,driver=case.creator()
                    if change=='image':
                        original=driver.docker
                        def wrong(args,seconds,data=None):
                            raw=original(args,seconds,data)
                            return c.p.encode([dict(owner.metadata['native'][0],Id='sha256:'+'f'*64)])if args[:2]==['image','inspect']else raw
                        with patch.object(driver,'docker',side_effect=wrong),self.assertRaises(c.p.Held):owner.execute()
                        self.assertFalse(any(a[0]=='create'for a in driver.calls))
                    else:
                        setattr(owner,'service_source'if change=='service'else'config_source',b'foreign-source')
                        with self.assertRaises(c.p.Held):owner.execute()
                    self.assertFalse(any(a[0]=='start'for a in driver.calls))
                finally:case.doCleanups()
    def test_no_replay_existing_root_or_geometry(self):
        owner,_=self.creator();owner.root.mkdir(mode=0o700)
        with self.assertRaises(c.p.Held):self.creator()
    def test_scope_mount_drift_refuses_before_any_creation(self):
        owner,driver=self.creator()
        with patch.object(driver,'mount',return_value=dict(self.document['nfs_mount'],id=999)),self.assertRaises(c.p.Held):owner.execute()
        self.assertEqual(driver.calls,[]);self.assertFalse(owner.root.exists())
    def test_connected_adapter_rejects_foreign_selectors_programs_and_worker_start(self):
        owner,driver=self.creator();owner.prepare();before=len(driver.calls)
        for args in (['start',owner.engine.ids['worker']],['inspect','f'*64],['network','inspect','f'*64],['exec','foreign','/bin/sh'],['restart',owner.engine.ids['reader']]):
            with self.subTest(args=args[:2]),self.assertRaises(c.p.Held):owner.engine.run(args,10)
        self.assertEqual(len(driver.calls),before)
    def test_config_export_is_literal_section_only_and_rejects_missing_or_dynamic(self):
        self.assertEqual(c.config_sections(self.config_source,['API_KEY']),{'API_KEY':'API'})
        for raw in (b'import forbidden\n_CONFIG_DEFINITIONS = {}',b'_CONFIG_DEFINITIONS={"API_KEY":(str, compute(),None)}'):
            with self.assertRaises(c.p.Held):c.config_sections(raw,['API_KEY'])
    def test_copy_never_extracts_links_multientry_or_foreign_bytes(self):
        expected=dict(path='/config.py',sha256=hashlib.sha256(b'actual').hexdigest())
        self.assertEqual(c.copied_file(tar(b'actual','config.py'),expected),b'actual')
        with self.assertRaises(c.p.Held):c.copied_file(tar(b'foreign','config.py'),expected)
        with self.assertRaises(c.p.Held):c.copied_file(tar(b'actual','foreign.py'),expected)
    def test_pinned_claim_headers_and_basic_api_key_contract_execute_exact_program(self):
        nonce='a'*64;cid='1'*64
        wrapper="""import urllib.request,json
captured={}
class Response:
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self,n):return b'{"id":"fixture-response"}'
class Opener:
 def open(self,request,timeout):
  captured.update(url=request.full_url,method=request.get_method(),headers=dict(request.header_items()),body=None if request.data is None else request.data.decode());return Response()
urllib.request.build_opener=lambda *a:Opener()
"""
        for operation in ('status','claim','key'):
            value=dict(nonce=nonce,cid=cid,operation=operation,email='bootstrap-'+nonce+'@example.invalid',password='b'*64,seconds=10)
            script=wrapper+"\nexec("+repr(c.ENROLL_PROGRAM)+")\nprint('\\n'+json.dumps(captured))"
            result=subprocess.run([sys.executable,'-I','-B','-c',script,'--disposable-reader-claim-v1',nonce,cid],input=c.p.encode(value),capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr.decode());request=json.loads(result.stdout.splitlines()[-1])
            self.assertTrue(request['url'].startswith('http://reader-'+nonce[:16]+':25600/api/'))
            if operation=='claim':
                self.assertEqual(request['method'],'POST');self.assertEqual(request['body'],'')
                self.assertEqual(request['headers']['X-komga-email'],value['email']);self.assertEqual(request['headers']['X-komga-password'],value['password'])
            elif operation=='key':
                self.assertTrue(request['headers']['Authorization'].startswith('Basic '));self.assertEqual(json.loads(request['body']),dict(comment='bootstrap-'+nonce))
                self.assertTrue(request['url'].endswith('/api/v2/users/me/api-keys'))
            else:self.assertEqual(request['method'],'GET');self.assertIsNone(request['body'])
    def test_closed_lifetime_and_mutating_call_budget_never_dispatch_again(self):
        owner,driver=self.creator();owner.prepare();before=len(driver.calls)
        args=['restart','--time','30',owner.engine.ids['native']]
        owner.engine.run(args,10)
        with self.assertRaises(c.p.Held):owner.engine.run(args,10)
        self.assertEqual(len(driver.calls),before+1)
        owner.closed=True
        with self.assertRaises(c.p.Held):owner.engine.run(['inspect',owner.engine.ids['native']],10)
        self.assertEqual(len(driver.calls),before+1)
    def test_foreign_static_profile_is_rejected_before_enrollment(self):
        owner,driver=self.creator();original=driver.docker
        def replacement(args,seconds,data=None):
            raw=original(args,seconds,data)
            if args[0]=='start':driver.rows[args[1]]['Config']['Unexpected']='foreign'
            return raw
        with patch.object(driver,'docker',side_effect=replacement),self.assertRaises(c.p.Held):owner.execute()
        self.assertNotIn('enroll-claim',owner.engine.counts)
    def test_engine_prefix_and_bounded_actual_pipe_transport_without_docker(self):
        original=subprocess.Popen;calls=[]
        def child(command,**kwargs):
            calls.append(command)
            return original([sys.executable,'-I','-B','-c','import sys;raw=sys.stdin.buffer.read();sys.stderr.write("diagnostic");sys.stdout.buffer.write(raw)'],**kwargs)
        with patch.object(c.subprocess,'Popen',side_effect=child):self.assertEqual(c.Driver().docker(['inspect','a'*64],10,b'bounded'),b'bounded')
        self.assertEqual(tuple(calls[0][:4]),c.PREFIX)
        def oversized(command,**kwargs):return original([sys.executable,'-I','-B','-c','import sys;sys.stdout.buffer.write(b"x"*2048)'],**kwargs)
        with patch.object(c.subprocess,'Popen',side_effect=oversized),patch.object(c,'LIMIT',1024),self.assertRaisesRegex(c.p.Held,'output-bound'):c.Driver().docker(['inspect','a'*64],10)
    def test_engine_timeout_is_unknown_and_never_falls_back(self):
        original=subprocess.Popen;calls=[]
        def waiting(command,**kwargs):
            calls.append(command);return original([sys.executable,'-I','-B','-c','import time;time.sleep(5)'],**kwargs)
        with patch.object(c.subprocess,'Popen',side_effect=waiting),self.assertRaisesRegex(c.p.Held,'unknown-no-replay'):c.Driver().docker(['inspect','a'*64],1)
        self.assertEqual(len(calls),1)
    def test_python310_and_no_startup_or_factory_override(self):
        raw=(HERE/'genuine_bootstrap_creator.py').read_text();ast.parse(raw,feature_version=(3,10))
        for forbidden in ('object.__new__','_CORES[','initialize_publication(','complete_startup(','chmod(0o777','docker.sock:'):
            self.assertNotIn(forbidden,raw)


if __name__=='__main__':unittest.main(verbosity=2)
