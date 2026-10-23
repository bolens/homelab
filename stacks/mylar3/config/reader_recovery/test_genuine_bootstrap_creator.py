"""Real disposable files and original Bootstrap; engine/API responses are doubles.

No Docker, Polkit, NFS, native schema, daemon, ACK or factory acceptance is
claimed. The connected path must stop at the missing actual startup database.
"""
import ast
import base64
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
        self.route_rows=[dict(dst='default')];self.existing_subnets=[];self.ipam_drift=False
    def mount(self,path,seconds):return copy.deepcopy(self.owner.document['nfs_mount'])
    def routes(self,seconds):return c.p.encode(self.route_rows)
    def docker(self,args,seconds,data=None):
        self.calls.append(copy.deepcopy(args));o=self.owner
        if self.fail==args[0] or self.fail==' '.join(args[:2]):raise c.p.Held('injected-lost-response')
        if args[:2]==['image','inspect']:return c.p.encode(next(v for v in o.metadata.values()if v[0]['Id']==args[2]))
        if args[:2]==['network','create']:return self.network.encode()
        if args[:2]==['network','ls']:return ('8'*64+'\n').encode()
        if args[:2]==['network','inspect'] and args[2:]==['8'*64]:
            return c.p.encode([dict(Id='8'*64,IPAM=dict(Config=[dict(Subnet=v)for v in self.existing_subnets]))])
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
            profile=dict(Id=self.network,Internal=True,Driver='bridge',Labels={c.b.LABEL:o.nonce,c.b.PURPOSE:'genuine-archive-fixture'},Containers={cid:dict(EndpointID=row['NetworkSettings']['Networks']['private']['EndpointID'])for cid,row in self.rows.items()if row['State']['Running']})
            if o.document['version']==4:
                subnet=c.explicit_subnet(o.document['network']);profile.update(EnableIPv6=False,IPAM=dict(Driver='default',Config=[dict(Subnet=str(subnet),Gateway=str(subnet.network_address+(2 if self.ipam_drift else 1)))]))
            return c.p.encode([profile])
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
    def searchable_request(self):
        self.document['version']=3
        self.document['sources']['reader_queue']=ref(HERE/'genuine_reader_quiescence.py')
        Path(self.document['nfs_parent']['path']).chmod(0o711)
        self.document['nfs_parent']=c.Creator.directory_ref(Path(self.document['nfs_parent']['path']))

    def explicit_network_request(self):
        self.searchable_request();self.document['version']=4
        self.document['network']=dict(version=1,kind='explicit-disposable-ipv4',subnet='10.99.0.0/28')

    def test_v4_explicit_internal_network_reaches_actual_bootstrap_boundary(self):
        self.explicit_network_request();owner,driver=self.creator();seen=[]
        def boundary(session,**options):
            self.assertIs(type(session),c.b.Bootstrap);session.queue_originals()
            self.assertEqual(session.geometry[1]['version'],2);seen.append(options)
            c.p.close_common_root(session.geometry);return dict(boundary_double=True)
        with patch.object(c.b.Bootstrap,'execute',boundary):result=owner.execute()
        creates=[a for a in driver.calls if a[:2]==['network','create']]
        self.assertEqual(len(creates),1);self.assertEqual(creates[0][:7],['network','create','--internal','--driver','bridge','--subnet','10.99.0.0/28'])
        self.assertEqual(len(seen),1);self.assertFalse(result['installed_factories_verified'])
        self.assertFalse(result['publication_acceptance'])
        self.assertTrue((owner.journal/'network-preflight.json').is_file())

    def test_v4_subnet_schema_and_canonical_rfc1918_range(self):
        self.explicit_network_request()
        for value in ('10.99.0.1/28','10.99.0.0/24','8.8.8.0/28','127.0.0.0/28','169.254.0.0/28','100.64.0.0/28','2001:db8::/28','bad'):
            with self.subTest(value=value),self.assertRaises(c.p.Held):
                c.explicit_subnet(dict(self.document['network'],subnet=value))
        for value in (dict(self.document['network'],version=True),dict(self.document['network'],extra=True),{},None):
            with self.assertRaises(c.p.Held):c.explicit_subnet(value)
        for value in ('10.99.0.0/28','172.16.0.0/28','192.168.0.0/28'):
            self.assertEqual(str(c.explicit_subnet(dict(self.document['network'],subnet=value))),value)

    def test_legacy_versions_refuse_network_extension(self):
        self.explicit_network_request()
        for version in (1,2,3):
            self.document['version']=version
            with self.assertRaisesRegex(c.p.Held,'creator-schema'):self.creator()

    def test_v3_network_args_remain_automatic_without_new_census(self):
        self.searchable_request();owner,driver=self.creator();owner.directories();owner.engine.create_network()
        self.assertEqual(driver.calls,[['network','create','--internal','--driver','bridge',*owner.labels(),owner.name('network')]])

    def test_v4_host_overlap_refuses_before_any_docker_call(self):
        self.explicit_network_request();owner,driver=self.creator();owner.directories()
        driver.route_rows=[dict(dst='10.0.0.0/8',table=123)]
        with self.assertRaisesRegex(c.p.Held,'creator-network-host-overlap'):owner.engine.create_network()
        self.assertEqual(driver.calls,[]);self.assertIsNone(owner.engine.network)

    def test_v4_docker_overlap_refuses_before_network_create(self):
        self.explicit_network_request();owner,driver=self.creator();owner.directories();driver.existing_subnets=['10.99.0.0/24']
        with self.assertRaisesRegex(c.p.Held,'creator-network-docker-overlap'):owner.engine.create_network()
        self.assertFalse(any(a[:2]==['network','create']for a in driver.calls))

    def test_v4_ipv6_existing_network_does_not_overlap_ipv4(self):
        self.explicit_network_request();owner,driver=self.creator();owner.directories();driver.existing_subnets=['fd00::/64']
        owner.engine.create_network();self.assertEqual(owner.engine.network,driver.network)

    def test_v4_malformed_routes_refuse_without_create(self):
        self.explicit_network_request();owner,driver=self.creator();owner.directories()
        for rows in ([],{},[{}],[dict(dst='bad')],[dict(dst='::/0')]):
            driver.route_rows=rows
            with self.assertRaises(c.p.Held):owner.engine.create_network()
        self.assertEqual(driver.calls,[])

    def test_v4_malformed_network_census_refuses_without_create(self):
        self.explicit_network_request();owner,driver=self.creator();owner.directories()
        with patch.object(driver,'docker',return_value=b'not-an-id'),self.assertRaisesRegex(c.p.Held,'creator-network-census'):
            owner.engine.create_network()
        self.assertIsNone(owner.engine.network)

    def test_v4_created_ipam_drift_retains_network_without_containers(self):
        self.explicit_network_request();owner,driver=self.creator();owner.directories();driver.ipam_drift=True
        with self.assertRaisesRegex(c.p.Held,'creator-original-network-ipam'):owner.engine.create_network()
        self.assertEqual(owner.engine.network,driver.network);self.assertEqual(owner.engine.ids,{})
        before=len(driver.calls)
        with self.assertRaisesRegex(c.p.Held,'network-create-once'):owner.engine.create_network()
        self.assertEqual(len(driver.calls),before)

    def test_v4_lost_network_create_is_never_replayed(self):
        self.explicit_network_request();owner,driver=self.creator();owner.directories();driver.fail='network create'
        with self.assertRaises(c.p.Held):owner.engine.create_network()
        before=len(driver.calls)
        with self.assertRaisesRegex(c.p.Held,'creator-unknown-outcome-held'):owner.engine.create_network()
        self.assertEqual(len(driver.calls),before);self.assertTrue(owner.engine.poisoned)

    def test_v4_late_ipam_drift_refuses_bootstrap_plan(self):
        self.explicit_network_request();owner,driver=self.creator();original=driver.docker
        def changed(args,seconds,data=None):
            if args==['network','inspect',driver.network] and owner.engine.started=={'native','reader'}:
                driver.ipam_drift=True
            return original(args,seconds,data)
        with patch.object(driver,'docker',changed),self.assertRaisesRegex(c.p.Held,'creator-original-network-ipam'):
            owner.prepare()
        self.assertFalse(owner.engine.connected);self.assertFalse((owner.journal/'bootstrap-plan.json').exists())

    def test_v4_malformed_network_profiles_refuse_without_create(self):
        self.explicit_network_request()
        for index,profiles in enumerate(([dict(Id='8'*64)],[],[dict(Id='8'*64,IPAM=dict(Config=[dict(Subnet='bad')]))])):
            state=Path(self.local.name)/str(index);state.mkdir(mode=0o700)
            remote=Path(self.remote.name)/str(index);remote.mkdir(mode=0o711);remote.chmod(0o711)
            self.document['state_parent']=c.Creator.directory_ref(state)
            self.document['nfs_parent']=c.Creator.directory_ref(remote)
            owner,driver=self.creator();owner.directories();original=driver.docker
            def changed(args,seconds,data=None):
                if args[:2]==['network','inspect']:return c.p.encode(profiles)
                return original(args,seconds,data)
            with patch.object(driver,'docker',changed),self.assertRaises(c.p.Held):owner.engine.create_network()
            self.assertFalse(any(a[:2]==['network','create']for a in driver.calls))
            # Each iteration is a distinct local modeled owner/nonce, not a retry.
            self.document['nonce']=hashlib.sha256(self.document['nonce'].encode()).hexdigest()

    def test_fixed_route_command_and_output_bounds(self):
        driver=c.Driver();reply=type('Reply',(),dict(stdout=b'[]',stderr=b''))()
        with patch.object(c.subprocess,'run',return_value=reply)as call:
            self.assertEqual(driver.routes(900),b'[]')
        self.assertEqual(call.call_args.args[0],['/usr/bin/ip','-json','-4','route','show','table','all'])
        self.assertEqual(call.call_args.kwargs,dict(capture_output=True,check=True,timeout=30))
        reply.stdout=b'x'*(4*1024**2+1)
        with patch.object(c.subprocess,'run',return_value=reply),self.assertRaises(c.p.Held):driver.routes(900)

    def test_v3_fresh_searchable_geometry_under_private_umask(self):
        self.searchable_request();owner,_=self.creator()
        before=os.umask(0o077)
        try:owner.prepare()
        finally:os.umask(before)
        self.assertEqual(owner.common.stat().st_mode&0o777,0o711)
        self.assertEqual([v.stat().st_mode&0o777 for v in(owner.root,owner.library,owner.retention)],[0o700]*3)
        self.assertEqual(owner.geometry[1]['version'],2)
        self.assertEqual(owner.geometry[1]['kind'],'searchable-common-root-nfs')
        c.p.check_common_root(owner.geometry)

    def test_v3_actual_bootstrap_constructor_keeps_queue_and_geometry(self):
        self.searchable_request();owner,_=self.creator();seen=[]
        def boundary(session,**options):
            self.assertIs(type(session),c.b.Bootstrap);session.queue_originals()
            self.assertEqual(session.geometry[1]['version'],2)
            self.assertEqual(session.geometry[1]['kind'],'searchable-common-root-nfs')
            seen.append(options);c.p.close_common_root(session.geometry)
            return dict(boundary_double=True)
        with patch.object(c.b.Bootstrap,'execute',boundary):result=owner.execute()
        self.assertEqual(seen,[dict(native_catalog_helper=self.document['sources']['catalog_helper'],reader_queue_helper=self.document['sources']['reader_queue'])])
        self.assertFalse(result['installed_factories_verified']);self.assertFalse(result['publication_acceptance'])

    def test_v3_parent_contract_exact_and_legacy_parent_unchanged(self):
        self.searchable_request()
        for mode in(0o700,0o755,0o777,0o710):
            parent=Path(self.document['nfs_parent']['path']);parent.chmod(mode)
            self.document['nfs_parent']=c.Creator.directory_ref(parent)
            with self.assertRaises(c.p.Held):self.creator()
        parent.chmod(0o711);self.document['nfs_parent']=c.Creator.directory_ref(parent)
        self.document['version']=2
        with self.assertRaises(c.p.Held):self.creator()
        self.document['version']=3
        (parent/'existing').mkdir(mode=0o700)
        self.document['nfs_parent']=c.Creator.directory_ref(parent)
        with self.assertRaisesRegex(c.p.Held,'creator-empty-searchable-parent'):self.creator()

    def test_v3_existing_common_never_chmod_or_adopt(self):
        self.searchable_request();owner,driver=self.creator()
        owner.common.mkdir(mode=0o700);original=c.p.nine(owner.common.lstat())
        with self.assertRaises((FileExistsError,c.p.Held)):owner.directories()
        self.assertEqual(c.p.nine(owner.common.lstat()),original)
        self.assertEqual(driver.calls,[])

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
    def test_config_export_accepts_only_plain_or_owning_ordereddict_literal(self):
        expected=c.config_sections(self.config_source,CONFIG_KEYS)
        self.assertEqual(len(expected),23)
        wrapped=self.config_source.replace(b'= {',b'= OrderedDict({').replace(b'}\n',b'})\n')
        # These names deliberately cannot be imported: the parser only reads AST.
        wrapped=b'import forbidden_config_provider\n'+wrapped
        self.assertEqual(c.config_sections(wrapped,CONFIG_KEYS),expected)
        plain=b'_CONFIG_DEFINITIONS={"API_KEY":(str,"API",None)}'
        self.assertEqual(c.config_sections(plain,['API_KEY']),{'API_KEY':'API'})

    def test_config_export_rejects_other_calls_wrappers_duplicates_and_missing_fields(self):
        literal='{"API_KEY":(str,"API",None)}'
        expressions=(f'Other({literal})',f'collections.OrderedDict({literal})',
                     f'OrderedDict({literal}, {literal})',f'OrderedDict(items={literal})',
                     f'OrderedDict({literal}, unexpected=True)', 'OrderedDict()',
                     'OrderedDict([( "API_KEY", (str,"API",None))])',
                     f'OrderedDict(Other({literal}))', 'OrderedDict({**provider})',
                     'OrderedDict({"API_KEY":(str,"API",None),"API_KEY":(str,"General",None)})',
                     'OrderedDict({})', 'OrderedDict({"API_KEY":(str,compute(),None)})')
        for expression in expressions:
            with self.subTest(expression=expression),self.assertRaises(c.p.Held):
                c.config_sections(('_CONFIG_DEFINITIONS='+expression).encode(),['API_KEY'])
        with self.assertRaises(c.p.Held):
            c.config_sections(self.config_source,CONFIG_KEYS+['MISSING'])

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
            value=dict(nonce=nonce,cid=cid,operation=operation,email='bootstrap-'+nonce[:48]+'@example.invalid',password='b'*64,seconds=10)
            script=wrapper+"\nexec("+repr(c.ENROLL_PROGRAM)+")\nprint('\\n'+json.dumps(captured))"
            result=subprocess.run([sys.executable,'-I','-B','-c',script,'--disposable-reader-claim-v1',nonce,cid],input=c.p.encode(value),capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr.decode());request=json.loads(result.stdout.splitlines()[-1])
            self.assertTrue(request['url'].startswith('http://reader-'+nonce[:16]+':25600/api/'))
            if operation=='claim':
                self.assertEqual(request['method'],'POST');self.assertEqual(request['body'],'')
                self.assertEqual(request['headers']['X-komga-email'],value['email']);self.assertEqual(request['headers']['X-komga-password'],value['password'])
            elif operation=='key':
                self.assertEqual(base64.b64decode(request['headers']['Authorization'].removeprefix('Basic ')).decode(),value['email']+':'+value['password']);self.assertEqual(json.loads(request['body']),dict(comment='bootstrap-'+nonce))
                self.assertTrue(request['url'].endswith('/api/v2/users/me/api-keys'))
            else:self.assertEqual(request['method'],'GET');self.assertIsNone(request['body'])
    def test_claim_email_fits_validator_bound_and_old_or_foreign_inputs_never_dispatch(self):
        # Komga1.28.1 ClaimController @Email; its Boot3.5.16 BOM selects
        # HibernateValidator8.0.3, whose local-part limit is64 characters.
        nonce='a'*64;cid='1'*64
        valid=dict(nonce=nonce,cid=cid,operation='claim',email='bootstrap-'+nonce[:48]+'@example.invalid',password='b'*64,seconds=10)
        self.assertEqual(len(valid['email'].split('@')[0]),58)
        wrapper="""import urllib.request
urllib.request.build_opener=lambda *args:(_ for _ in ()).throw(RuntimeError('TRANSPORT-MUST-NOT-BE-REACHED'))
"""
        old=dict(valid,email='bootstrap-'+nonce+'@example.invalid')
        wrong_nonce=dict(valid,nonce='c'*64)
        wrong_cid=dict(valid,cid='2'*64)
        for value in (old,wrong_nonce,wrong_cid):
            with self.subTest(case=value['email'][:12],nonce=value['nonce'][:1],cid=value['cid'][:1]):
                result=subprocess.run([sys.executable,'-I','-B','-c',wrapper+'\nexec('+repr(c.ENROLL_PROGRAM)+')','--disposable-reader-claim-v1',nonce,cid],input=c.p.encode(value),capture_output=True,timeout=10)
                self.assertNotEqual(result.returncode,0)
                self.assertIn(b'AssertionError',result.stderr)
                self.assertNotIn(b'TRANSPORT-MUST-NOT-BE-REACHED',result.stderr)
        owner,driver=self.creator();original=driver.docker;sent=[]
        def capture(args,seconds,data=None):
            if len(args)>9 and args[0]=='exec'and args[9]==c.ENROLL_PROGRAM:sent.append(c.p.decode(data))
            return original(args,seconds,data)
        driver.docker=capture;owner.prepare()
        login=json.loads((owner.journal/'reader-login.json').read_bytes())
        self.assertEqual(login['email'],'bootstrap-'+owner.nonce[:48]+'@example.invalid')
        self.assertEqual(sum(v['operation']=='claim'for v in sent),1)
        self.assertTrue(all(v['email']==login['email'] and v['nonce']==owner.nonce and v['cid']==owner.engine.ids['native']for v in sent))

    def test_closed_lifetime_and_mutating_call_budget_never_dispatch_again(self):
        owner,driver=self.creator();owner.prepare();before=len(driver.calls)
        args=['restart','--timeout','30',owner.engine.ids['native']]
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

    def failure_transport(self, code, *, stdout=b'PRIVATE-OUT', stderr=b'PRIVATE-ERR'):
        original=subprocess.Popen;calls=[]
        program='import sys;sys.stdout.buffer.write('+repr(stdout)+');sys.stdout.flush();sys.stderr.buffer.write('+repr(stderr)+');sys.stderr.flush();'+code
        def child(command,**kwargs):
            calls.append(command)
            return original([sys.executable,'-I','-B','-c',program],**kwargs)
        return child,calls

    def test_nonzero_driver_retains_actual_bounded_pipes_and_fixed_reason(self):
        child,calls=self.failure_transport('sys.exit(23)',stderr=b'PRIVATE-ERR\xff')
        with patch.object(c.subprocess,'Popen',side_effect=child),self.assertRaisesRegex(c.p.Held,'^creator-engine-held-no-replay$')as caught:
            c.Driver().docker(['create','fixture'],10)
        diagnostic=caught.exception.creator_engine_failure
        self.assertEqual(diagnostic['returncode'],23);self.assertEqual(base64.b64decode(diagnostic['stdout_base64']),b'PRIVATE-OUT');self.assertEqual(base64.b64decode(diagnostic['stderr_base64']),b'PRIVATE-ERR\xff')
        self.assertFalse(diagnostic['stdout_truncated']);self.assertFalse(diagnostic['stderr_truncated']);self.assertNotIn('PRIVATE',str(caught.exception));self.assertEqual(len(calls),1)

    def test_first_private_journal_failure_poison_blocks_replay_without_printing(self):
        owner,driver=self.creator();owner.prepare();owner.engine.driver=c.Driver();child,calls=self.failure_transport('sys.exit(23)')
        with patch.object(c.subprocess,'Popen',side_effect=child),patch('sys.stdout',new_callable=io.StringIO)as stdout,patch('sys.stderr',new_callable=io.StringIO)as stderr:
            with self.assertRaisesRegex(c.p.Held,'^creator-engine-held-no-replay$'):owner.engine.call('fixture-failure',1,['create','fixture'])
            with self.assertRaisesRegex(c.p.Held,'^creator-unknown-outcome-held$'):owner.engine.call('fixture-failure',1,['create','fixture'])
        path=owner.journal/'engine-failure.private.json';saved=json.loads(path.read_bytes());self.assertEqual(saved['operation'],'fixture-failure');self.assertEqual(saved['diagnostic']['returncode'],23);self.assertEqual(base64.b64decode(saved['diagnostic']['stderr_base64']),b'PRIVATE-ERR')
        self.assertEqual(path.stat().st_mode&0o777,0o600);self.assertEqual(path.stat().st_uid,1000);self.assertEqual(path.stat().st_nlink,1);self.assertFalse(saved['automatic_replay']);self.assertFalse(saved['cleanup']);self.assertTrue(owner.engine.poisoned);self.assertEqual(len(calls),1);self.assertEqual(stdout.getvalue()+stderr.getvalue(),'')

    def test_diagnostic_write_failure_preserves_primary_failure_and_poison(self):
        owner,driver=self.creator();owner.prepare();owner.engine.driver=c.Driver();child,calls=self.failure_transport('sys.exit(23)');put=c.b.put
        def failed(path,value):
            if path.name=='engine-failure.private.json':raise OSError('private-diagnostic-storage-failed')
            return put(path,value)
        with patch.object(c.subprocess,'Popen',side_effect=child),patch.object(c.b,'put',side_effect=failed),self.assertRaisesRegex(c.p.Held,'^creator-engine-held-no-replay$')as caught:
            owner.engine.call('fixture-failure',1,['create','fixture'])
        self.assertEqual(caught.exception.creator_diagnostic_failure,'OSError');self.assertEqual(caught.exception.creator_engine_failure['returncode'],23);self.assertTrue(owner.engine.poisoned);self.assertEqual(len(calls),1)

    def test_output_bound_retains_only_bounded_prefix_and_never_accepts(self):
        child,calls=self.failure_transport('sys.exit(23)',stdout=b'x'*4096,stderr=b'')
        with patch.object(c.subprocess,'Popen',side_effect=child),patch.object(c,'LIMIT',1024),self.assertRaisesRegex(c.p.Held,'^creator-engine-output-bound$')as caught:
            c.Driver().docker(['create','fixture'],10)
        diagnostic=caught.exception.creator_engine_failure;self.assertEqual(len(base64.b64decode(diagnostic['stdout_base64'])),1024);self.assertTrue(diagnostic['stdout_truncated']);self.assertEqual(diagnostic['stream_byte_limit'],1024);self.assertEqual(len(calls),1)

    def test_timeout_retains_partial_reply_with_unknown_returncode(self):
        child,calls=self.failure_transport('import time;time.sleep(5)')
        with patch.object(c.subprocess,'Popen',side_effect=child),self.assertRaisesRegex(c.p.Held,'^creator-engine-outcome-unknown-no-replay$')as caught:
            c.Driver().docker(['create','fixture'],1)
        diagnostic=caught.exception.creator_engine_failure;self.assertIsNone(diagnostic['returncode']);self.assertEqual(base64.b64decode(diagnostic['stdout_base64']),b'PRIVATE-OUT');self.assertEqual(base64.b64decode(diagnostic['stderr_base64']),b'PRIVATE-ERR');self.assertEqual(len(calls),1)

    def test_later_readonly_failure_preserves_first_journal_without_overwrite(self):
        owner,driver=self.creator();owner.prepare();owner.engine.driver=c.Driver();child,calls=self.failure_transport('sys.exit(23)')
        with patch.object(c.subprocess,'Popen',side_effect=child):
            with self.assertRaises(c.p.Held):owner.engine.call('fixture-first',1,['inspect','fixture'],readonly=True)
            path=owner.journal/'engine-failure.private.json';before=path.read_bytes();frame=c.p.nine(path.stat())
            with self.assertRaises(c.p.Held):owner.engine.call('fixture-later',1,['inspect','fixture'],readonly=True)
        self.assertFalse(owner.engine.poisoned);self.assertEqual(path.read_bytes(),before);self.assertEqual(c.p.nine(path.stat()),frame);self.assertEqual(len(calls),2)


    def test_held_diagnostic_authenticates_creator_frame_without_private_values(self):
        owner,driver=self.creator();driver.fail='start'
        with self.assertRaises(c.p.Held)as caught:owner.execute()
        saved=json.loads((owner.journal/'held.json').read_bytes());failure=saved['failure']
        self.assertEqual(failure['exception_class'],'Held')
        frame=failure['source_frame'];self.assertIsNotNone(frame)
        self.assertEqual(set(frame),{'function','line','source_sha256'})
        self.assertEqual(frame['source_sha256'],owner.document['sources']['creator']['sha256'])
        self.assertGreater(frame['line'],0)
        encoded=json.dumps(saved)
        for private_value in (str(owner.root),str(HERE),str(caught.exception),'PRIVATE-FIXTURE-KEY'):
            self.assertNotIn(private_value,encoded)
        self.assertFalse(saved['cleanup']);self.assertFalse(saved['automatic_replay'])
        self.assertEqual(sum(args[0]=='start'for args in driver.calls),1)

    def test_foreign_traceback_and_dynamic_exception_name_are_not_disclosed(self):
        owner,driver=self.creator()
        scope={};exec(compile("def private_local():\n raise RuntimeError('PRIVATE-MESSAGE')\n",str(HERE/'genuine_bootstrap_creator.py'),'exec'),scope)
        try:scope['private_local']()
        except RuntimeError as error:result=owner.failure_diagnostic(error)
        self.assertEqual(result,dict(exception_class='RuntimeError',source_frame=None))
        private_error=type('PRIVATE_CLASS',(Exception,),{})('PRIVATE-MESSAGE')
        self.assertEqual(owner.failure_diagnostic(private_error),dict(exception_class='unclassified-exception',source_frame=None))

    def test_changed_original_source_cannot_authenticate_traceback(self):
        owner,driver=self.creator();driver.fail='start';read=c.p.read
        def changed(ref,**options):
            raw=read(ref,**options)
            return raw+b'\n'if ref==owner.document['sources']['creator']else raw
        # Only the diagnostic read is changed; the primary failing operation is genuine.
        diagnostic=owner.failure_diagnostic
        with patch.object(owner,'failure_diagnostic',side_effect=lambda error:self._changed_diagnostic(diagnostic,error,changed)),self.assertRaises(c.p.Held):owner.execute()
        self.assertIsNone(json.loads((owner.journal/'held.json').read_bytes())['failure']['source_frame'])

    def _changed_diagnostic(self,diagnostic,error,read):
        with patch.object(c.p,'read',side_effect=read):return diagnostic(error)

    def test_held_write_failure_preserves_exact_primary_exception(self):
        owner,driver=self.creator();owner.prepare();primary=RuntimeError('PRIVATE-PRIMARY');put=c.b.put
        def failed(path,value):
            if path.name=='held.json':raise KeyboardInterrupt('PRIVATE-SECONDARY')
            return put(path,value)
        with patch.object(owner,'prepare',side_effect=primary),patch.object(c.b,'put',side_effect=failed),self.assertRaises(RuntimeError)as caught:owner.execute()
        self.assertIs(caught.exception,primary);self.assertTrue(owner.closed)
        self.assertFalse((owner.journal/'held.json').exists())

    def test_existing_held_diagnostic_is_not_rewritten(self):
        owner,driver=self.creator();owner.prepare();path=owner.journal/'held.json'
        c.b.put(path,dict(original='PRIVATE-ORIGINAL'));before=ref(path)
        primary=RuntimeError('PRIVATE-PRIMARY')
        with patch.object(owner,'prepare',side_effect=primary),self.assertRaises(RuntimeError)as caught:owner.execute()
        self.assertIs(caught.exception,primary);self.assertEqual(ref(path),before)

    def test_first_profiles_retain_raw_false_to_null_transition_without_overwrite(self):
        owner,driver=self.creator();original=driver.docker
        def changed(args,seconds,data=None):
            raw=original(args,seconds,data)
            if args[0]=='start':driver.rows[args[1]]['HostConfig']['OomKillDisable']=None
            return raw
        # Raw created false and running null remain distinct diagnostic evidence.
        def seeded(args,seconds,data=None):
            raw=changed(args,seconds,data)
            if args[0]=='create':driver.rows[raw.decode()]['HostConfig']['OomKillDisable']=False
            return raw
        driver.docker=seeded
        # Only the confirmed false-to-null transition is accepted; the connected
        # run still reaches the original missing-schema refusal, never success.
        with self.assertRaises(c.p.Held)as caught:owner.execute()
        self.assertNotEqual(str(caught.exception),'created-original-static-drift')
        created=owner.journal/'first-created-native.private.json';running=owner.journal/'first-running-native.private.json'
        before=ref(created);left=json.loads(created.read_bytes());right=json.loads(running.read_bytes())
        self.assertIs(left['profile']['HostConfig']['OomKillDisable'],False)
        self.assertIsNone(right['profile']['HostConfig']['OomKillDisable'])
        self.assertEqual(ref(created),before)
        for path,value in ((created,left),(running,right)):
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            self.assertEqual(value['response_sha256'],hashlib.sha256(c.p.encode([value['profile']])).hexdigest())
        self.assertEqual(sum(args[0]=='start'for args in driver.calls),2)

    def test_profile_diagnostic_storage_failure_does_not_change_admission(self):
        owner,driver=self.creator();put=c.b.put
        def failed(path,value):
            if path.name.startswith('first-'):raise OSError('PRIVATE-STORAGE')
            return put(path,value)
        with patch.object(c.b,'put',side_effect=failed):plan=owner.prepare()
        self.assertEqual(set(plan['roles']),{'native','reader','worker'})
        self.assertFalse(any(owner.journal.glob('first-*.private.json')))


    def test_oom_start_transition_rejects_missing_true_integer_and_other_drift(self):
        for mutation in ('missing','true','zero','config','mount'):
            with self.subTest(mutation=mutation):
                fixture=CreatorTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
                owner,driver=fixture.creator();original=driver.docker
                def changed(args,seconds,data=None):
                    raw=original(args,seconds,data)
                    if args[0]=='create':driver.rows[raw.decode()]['HostConfig']['OomKillDisable']=False
                    if args[0]=='start':
                        row=driver.rows[args[1]];row['HostConfig']['OomKillDisable']=None
                        if mutation=='missing':del row['HostConfig']['OomKillDisable']
                        elif mutation=='true':row['HostConfig']['OomKillDisable']=True
                        elif mutation=='zero':row['HostConfig']['OomKillDisable']=0
                        elif mutation=='config':row['Config']['Foreign']='unapproved'
                        elif mutation=='mount':row['Mounts'][0]['RW']=False
                    return raw
                driver.docker=changed
                with self.assertRaises(c.p.Held):owner.execute()
                self.assertEqual(sum(args[0]=='start'for args in driver.calls),1)

    def test_oom_transition_is_not_allowed_prestart_or_between_running_observations(self):
        owner,driver=self.creator();owner.prepare();cid=owner.engine.ids['native']
        # The fixture originally omitted this field; freeze an explicit raw baseline.
        row=driver.rows[cid];row['HostConfig']['OomKillDisable']=False
        owner.engine.created_static['native']['HostConfig']['OomKillDisable']=False
        owner.engine.runtime_static['native']['HostConfig']['OomKillDisable']=False
        row['HostConfig']['OomKillDisable']=None
        running=copy.deepcopy(row['State']);row['State'].update(Status='created',Running=False,Pid=0)
        with self.assertRaisesRegex(c.p.Held,'created-original-static-drift'):owner.engine.inspect('native',running=False)
        row['State']=running
        with self.assertRaisesRegex(c.p.Held,'created-runtime-static-drift'):owner.engine.inspect('native',running=True)

    def test_restart_timeout_flag_contract_rejects_deprecated_flag_without_dispatch(self):
        owner,driver=self.creator();owner.prepare();owner.engine.connected=True
        before=len(driver.calls)
        with self.assertRaisesRegex(c.p.Held,'only-original-native-restart'):
            owner.engine.run(['restart','--time','30',owner.engine.ids['native']],30)
        self.assertEqual(len(driver.calls),before)
        owner.engine.run(['restart','--timeout','30',owner.engine.ids['native']],30)
        self.assertEqual(driver.calls[-1],['restart','--timeout','30',owner.engine.ids['native']])


    def test_expected_probe_then_catalog_failure_have_distinct_private_intent_records(self):
        owner,driver=self.creator();owner.prepare();owner.engine.driver=c.Driver()
        probe,probe_calls=self.failure_transport('sys.exit(2)',stdout=b'EXPECTED-PROBE',stderr=b'EXPECTED-PROBE-ERR')
        with patch.object(c.subprocess,'Popen',side_effect=probe),self.assertRaises(c.p.Held):
            owner.engine.call('native-probe',256,['inspect','fixture'],readonly=True)
        first=owner.journal/'engine-failure.private.json';before=first.read_bytes();frame=c.p.nine(first.stat());self.assertFalse(owner.engine.poisoned)
        catalog,catalog_calls=self.failure_transport('sys.exit(7)',stdout=b'PRIVATE-CATALOG-OUT',stderr=b'PRIVATE-CATALOG-ERR')
        with patch.object(c.subprocess,'Popen',side_effect=catalog),patch('sys.stdout',new_callable=io.StringIO)as out,patch('sys.stderr',new_callable=io.StringIO)as err:
            with self.assertRaises(c.p.Held):owner.engine.call('catalog-seed',1,['exec','fixture'])
            with self.assertRaisesRegex(c.p.Held,'creator-unknown-outcome-held'):owner.engine.call('catalog-seed',1,['exec','fixture'])
        records=[json.loads(path.read_bytes())for path in sorted(owner.journal.glob('*-engine-failure.private.json'))]
        self.assertEqual([row['operation']for row in records],['native-probe','catalog-seed'])
        self.assertEqual([row['diagnostic']['returncode']for row in records],[2,7])
        self.assertEqual(base64.b64decode(records[1]['diagnostic']['stderr_base64']),b'PRIVATE-CATALOG-ERR')
        for row in records:
            intent=json.loads((owner.journal/(str(row['journal_operation_id']).zfill(4)+'-intent.json')).read_bytes())
            self.assertEqual(intent['kind'],row['operation']);self.assertFalse(row['cleanup']);self.assertFalse(row['automatic_replay'])
        self.assertEqual(first.read_bytes(),before);self.assertEqual(c.p.nine(first.stat()),frame)
        self.assertEqual(len(probe_calls),len(catalog_calls),1);self.assertTrue(owner.engine.poisoned);self.assertEqual(out.getvalue()+err.getvalue(),'')

    def test_operation_failure_record_has_independent_64k_stream_bounds(self):
        owner,driver=self.creator();owner.prepare();owner.engine.driver=c.Driver()
        original=subprocess.Popen;calls=[]
        def child(command,**kwargs):
            calls.append(command)
            return original([sys.executable,'-I','-B','-c',"import sys;sys.stdout.buffer.write(b'O'*131072);sys.stdout.flush();sys.stderr.buffer.write(b'E'*131072);sys.stderr.flush();sys.exit(2)"],**kwargs)
        with patch.object(c.subprocess,'Popen',side_effect=child),self.assertRaises(c.p.Held):owner.engine.call('native-probe',256,['inspect','fixture'],readonly=True)
        path=next(owner.journal.glob('*-engine-failure.private.json'));row=json.loads(path.read_bytes());diagnostic=row['diagnostic']
        self.assertEqual(diagnostic['retained_stream_byte_limit'],65536)
        for stream in ('stdout','stderr'):
            self.assertEqual(len(base64.b64decode(diagnostic[stream+'_base64'])),65536);self.assertTrue(diagnostic[stream+'_truncated'])
        original=json.loads((owner.journal/'engine-failure.private.json').read_bytes())
        self.assertEqual(len(base64.b64decode(original['diagnostic']['stdout_base64'])),131072)
        self.assertEqual(path.stat().st_mode&0o777,0o600);self.assertEqual(path.stat().st_nlink,1);self.assertEqual(len(calls),1)

    def test_per_operation_diagnostic_storage_failure_preserves_primary_and_first_record(self):
        owner,driver=self.creator();owner.prepare();owner.engine.driver=c.Driver();child,calls=self.failure_transport('sys.exit(2)');put=c.b.put
        def fail(path,value):
            if path.name.endswith('-engine-failure.private.json'):raise OSError('PRIVATE-STORAGE-FAILURE')
            return put(path,value)
        with patch.object(c.subprocess,'Popen',side_effect=child),patch.object(c.b,'put',side_effect=fail),self.assertRaisesRegex(c.p.Held,'^creator-engine-held-no-replay$')as caught:
            owner.engine.call('catalog-seed',1,['exec','fixture'])
        self.assertEqual(caught.exception.creator_diagnostic_failure,'OSError');self.assertEqual(caught.exception.creator_engine_failure['returncode'],2)
        self.assertTrue((owner.journal/'engine-failure.private.json').exists());self.assertTrue(owner.engine.poisoned);self.assertEqual(len(calls),1)


if __name__=='__main__':unittest.main(verbosity=2)
