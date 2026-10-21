"""Explicit transport doubles only: never Docker, installed or NFS acceptance."""
import copy
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

# Original accepted native405 full-map deltas; no runtime is executed here.
NATIVE405_DELTAS = {'PostProcessor.py': 'ede1c59507a9bd6274482fc0ef944dcf7c99362b9490a47f58aadfaedf5a0198',
                    'filechecker.py': 'd93a32ccd1342822fd14d5d4884cce25bf905693881216eb6e0efc42f5e9f70b'}
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import genuine_source_cohort as g
import comic_negative_nfs_active_parent as active


def ref(path):return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), signature9=g.p.nine(path.stat()))
def two(value):return {k:value[k] for k in ('path','sha256')}
def put(path, value):
    path.write_bytes(g.p.encode(value)); path.chmod(0o600); return ref(path)


class Fixture:
    def __init__(self, root, bundle, bundle_files):
        self.root = root; self.nonce = 'a'*64; self.output = root/'output'; self.calls=[]; self.fault=None; self.callback=None
        self.rows=[]; self.sdk=g.p.decode((HERE.parent/'reader_recovery/configured_reader_parent_base_sources.json').read_bytes())['base_installed_sources'];self.sdk.update(NATIVE405_DELTAS)
        native=put(root/'native.json',self.sdk); selected=put(root/'selected.json',g.p.decode((HERE.parent/'publication_reader_cohort.json').read_bytes()))
        generic=root/'explicit-test-source.py';generic.write_text('# Explicit response fixture only; never executed as installed code.\n');generic.chmod(0o600)
        source={k:ref(generic) for k in g.ROLES}
        for name, filename in [('probe','comic_negative_nfs_hardlink_child.py'),('hardlink_kernel','comic_negative_nfs_hardlink_probe.py'),('scope_projection','publication_native_configured_scope.py'),('readiness','comic_native_process_probe.py'),('lifecycle','comic_negative_nfs_active_lifecycle.py')]:source[name]=ref(HERE/filename)
        source['native_map']=native;source['selected_sdk']=selected
        parity=root/'parity.py';parity.write_bytes(g.derive_parity_program(g.producer.bootstrap.IMAGE_PROGRAM,self.sdk));parity.chmod(0o600);source['parity']=ref(parity)
        source['core_tests']=ref(HERE/'test_reader_lifecycle_parent.py');source['writer_fixture']=ref(HERE.parent/'test_media_writer.py')
        source['readiness_input']=put(root/'request.json',dict(version=1,nonce=self.nonce,source_sha256=source['readiness']['sha256'],seconds=30,module_pins={},scope_source='fixture only, never executed'))
        source['writer']=ref(HERE.parent/'media_writer.py');source['tests']=ref(HERE/'test_nfs_current_source.py')
        source['scope_projection']=ref(HERE.parent/'publication_native_configured_scope.py')
        source['readiness_input']=put(root/'request.json',dict(version=1,nonce=self.nonce,source_sha256=source['readiness']['sha256'],seconds=30,module_pins={'/app/mylar3/mylar/'+n:self.sdk[n]for n in ('worker_health.py','native_writers.py')},scope_source=(HERE.parent/'publication_native_configured_scope.py').read_text()))
        parent=ref(HERE/'comic_negative_nfs_active_parent.py');writer=root/'writer';writer.mkdir(mode=0o700)
        images={role:'sha256:'+char*64 for role,char in [('native','b'),('selected','b'),('reader','c'),('worker','d')]}
        cohort=dict(version=1,kind='approved-disposable-nfs-current-source-cohort',images=images,sources={k:two(v)for k,v in source.items()},writer_root=str(writer),writer_sha256=source['writer']['sha256'],native_map_count=len(self.sdk),selected_module_count=25,parent=two(parent),effective_jar_sha256='e'*64,effective_commit='f'*40)
        state=dict(Status='running',Running=True,Paused=False,Restarting=False,OOMKilled=False,Dead=False,Pid=123,ExitCode=0,Error='',StartedAt='original',FinishedAt='')
        self.profile=dict(Id='1'*64,Name='/source-cohort-'+self.nonce[:16],Image=images['selected'],Path='/bin/sleep',Args=['infinity'],Config=dict(User='1000:1000',Entrypoint=['/bin/sleep'],Cmd=['infinity'],Healthcheck={'Test':['NONE']},Labels={'com.homelab.archive.source-fixture':self.nonce}),
            HostConfig=dict(ReadonlyRootfs=True,NetworkMode='none',RestartPolicy={'Name':'no'},CapDrop=['ALL'],SecurityOpt=['no-new-privileges'],Tmpfs={'/tmp':'rw,nosuid,nodev,size=536870912,mode=1777','/config':'rw,nosuid,nodev,noexec,size=16777216,mode=0700,uid=1000,gid=1000'}),
            NetworkSettings=dict(Networks={'none':{}},Ports={}),Mounts=[dict(Type='bind',Source=str(bundle),Destination='/checks',RW=False)],State=state)
        image=[dict(Id=images['selected'],Os='linux',Architecture='amd64',Config={'Volumes':{'/config':{}}})]
        self.document=dict(version=1,kind='original-selected-source-fixture-run',nonce=self.nonce,observed=int(time.time()),profile=put(root/'profile.json',self.profile),image=put(root/'image.json',image),executable_sha256='2'*64,bundle=str(bundle),bundle_files=bundle_files,cohort=cohort,originals=list({r['path']:r for r in [*source.values(),parent]}.values()),output=str(self.output))
        self.request_ref=put(root/'causal.json',self.document)
        self.inventory=g.suites((HERE.parent/'run_reader_recovery_controls.py').read_bytes())
    def owner(self):return g.Emitter(self.request_ref,self.output,transport=self.transport)
    def transport(self, argv, **kwargs):
        self.calls.append(argv);rc=0;err=b''
        if argv[3]=='inspect':
            row=copy.deepcopy(self.profile)
            if self.fault=='late-profile' and len([a for a in self.calls if a[3]=='inspect'])>1:row['State']['Pid']=999
            raw=g.p.encode([row])
        elif argv[-1]==g.RUNTIME_PROGRAM:
            value=g.p.decode(kwargs['input'])
            if self.fault=='runtime':value['executable_sha256']='f'*64
            occurrence=len([a for a in self.calls if a[-1]==g.RUNTIME_PROGRAM])
            if (self.fault=='runtime-map-before' and occurrence==1) or (self.fault=='runtime-map-after' and occurrence==2):
                historical=g.p.decode((HERE/'configured_reader_parent_base_sources.json').read_bytes())['base_installed_sources']
                value['modules']['PostProcessor.py']=historical['PostProcessor.py']
            raw=g.p.encode(value)
        elif argv[-1]=='/checks/verify_publication_reader_cohort.py':raw=g.VERIFY_LINE
        elif argv[-1]=='/checks/run_reader_recovery_controls.py':
            value=dict(kind='private-build-only-reader-recovery-controls',tests=sum(n for _,n in self.inventory),suites=[dict(suite=n,count=c,skips=0,stdout_sha256='3'*64,stderr_sha256='4'*64)for n,c in self.inventory],original_source_unchanged=True,installed_factory_verified=False,publication_acceptance=False,reader_resume_authority=False)
            if self.callback:self.callback()
            if self.fault=='timeout':raise subprocess.TimeoutExpired(argv,kwargs['timeout'],output=b'partial original output',stderr=b'partial error')
            if self.fault=='exit':rc=7;err=b'actual fixture failure';raw=b'partial result'
            else:
                if self.fault=='partial':value['suites'].pop()
                if self.fault=='skips':value['suites'][0]['skips']=1
                if self.fault=='boolean-count':value['suites'][0]['count']=True
                if self.fault=='grant':value['installed_factory_verified']=True
                raw=g.p.encode(value)
        else:raise AssertionError('Unexpected test transport argv')
        return subprocess.CompletedProcess(argv,rc,raw,err)


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.bundle=Path(cls.tmp.name)/'config';cls.bundle.mkdir(mode=0o700)
        public=HERE.parent;outer=g.p.decode((public/'standalone_control_sources.json').read_bytes());manifest=g.p.decode((HERE/'source-manifest.json').read_bytes())
        names={r['path']for r in outer}|{'reader_recovery/'+n for n in manifest['files']}|{'standalone_control_sources.json','reader_recovery/source-manifest.json','publication_reader_cohort.json'}
        cls.bundle_files={}
        for name in names:
            target=cls.bundle/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(public/name,target);target.chmod(0o600);cls.bundle_files[name]=ref(target)
        for folder, dirs, files in os.walk(cls.bundle):Path(folder).chmod(0o700)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):
        self.tmpcase=tempfile.TemporaryDirectory();self.addCleanup(self.tmpcase.cleanup);self.f=Fixture(Path(self.tmpcase.name),self.bundle,self.bundle_files)
    def fixture_payload(self):
        # Explicit PURE SCHEMA fixture only; default run() cannot use a double.
        owner=self.f.owner()
        with self.assertRaisesRegex(g.p.Held,'original-transport-required'):owner.execute()
        self.assertFalse((self.f.output/'readiness.json').exists());self.assertFalse((self.f.output/'cohort.json').exists())
        raw=(self.f.output/'controls.stdout').read_bytes();result=g.checked_result(raw,self.f.inventory)
        closing=put(self.f.root/'FIXTURE-ONLY-closing.json',dict(fixture_only=True))
        receipt=g.payload(self.f.document['cohort'],self.f.request_ref,two(closing),result,two(ref(self.f.output/'controls.stdout')),two(ref(self.f.output/'controls.stderr')))
        receipt_ref=put(self.f.root/'FIXTURE-ONLY-readiness.json',receipt)
        cohort=dict(self.f.document['cohort'],receipt=two(receipt_ref),logs={k:receipt[k]for k in ('stdout','stderr')})
        return two(put(self.f.root/'FIXTURE-ONLY-cohort.json',cohort)),receipt
    def runtime_version_guard(self):
        # Execute the exact owning assertion AST, not a rewritten test predicate.
        import ast
        tree=ast.parse(g.RUNTIME_PROGRAM)
        guards=[node for node in tree.body if isinstance(node,ast.Assert)
                and 'sys.version_info' in ast.get_source_segment(g.RUNTIME_PROGRAM,node)]
        self.assertEqual(len(guards),1)
        return compile(ast.Module(body=guards,type_ignores=[]),'<owning-runtime-version>','exec')

    def test_parity_is_exact_owning_template_with_literal_original_names(self):
        import ast
        template=g.producer.bootstrap.IMAGE_PROGRAM
        program=g.derive_parity_program(template,self.f.sdk)
        self.assertEqual(program,template.replace('names=json.load(sys.stdin)','names='+repr(sorted(self.f.sdk)),1).encode())
        tree=ast.parse(program);self.assertEqual(ast.literal_eval(tree.body[1].value),sorted(self.f.sdk))
        self.assertNotIn(b'json.load(sys.stdin)',program)
        self.assertTrue(all(pin.encode() not in program for pin in self.f.sdk.values()))
        reverse=dict(reversed(list(self.f.sdk.items())))
        self.assertEqual(g.derive_parity_program(template,reverse),program)
        alternate=dict(self.f.sdk);alternate['Alternate.py']=alternate.pop('PostProcessor.py')
        self.assertNotEqual(g.derive_parity_program(template,alternate),program)

    def test_parity_refuses_changed_template_or_non_original_map_shape(self):
        template=g.producer.bootstrap.IMAGE_PROGRAM
        with self.assertRaisesRegex(g.p.Held,'owning-template'):
            g.derive_parity_program(template+'# changed\n',self.f.sdk)
        for mutation in ('missing','extra','unsafe','hash','boolean','not-map'):
            value=copy.deepcopy(self.f.sdk)
            if mutation=='missing':value.pop('PostProcessor.py')
            elif mutation=='extra':value['Extra.py']='a'*64
            elif mutation=='unsafe':value['../bad.py']=value.pop('PostProcessor.py')
            elif mutation=='hash':value['PostProcessor.py']='not-a-digest'
            elif mutation=='boolean':value['PostProcessor.py']=True
            else:value=list(value)
            with self.subTest(mutation=mutation),self.assertRaisesRegex(g.p.Held,'original-map'):
                g.derive_parity_program(template,value)

    def test_hash_bound_arbitrary_map_printer_is_not_parity(self):
        q=copy.deepcopy(self.f.document)
        path=self.f.root/'arbitrary-parity.py';path.write_text('print('+repr(g.p.encode(self.f.sdk).decode())+')\n');path.chmod(0o600)
        old=q['cohort']['sources']['parity']['path'];original=ref(path)
        q['cohort']['sources']['parity']=two(original)
        q['originals']=[r for r in q['originals'] if r['path']!=old]+[original]
        with self.assertRaisesRegex(g.p.Held,'owning-parity-program'):
            g.Emitter(put(self.f.root/'bad-parity.json',q),self.f.output,transport=self.f.transport)
        self.assertEqual(self.f.calls,[])

    def test_core_test_and_writer_fixture_require_canonical_source_bytes(self):
        for role in ('core_tests','writer_fixture'):
            q=copy.deepcopy(self.f.document);old=q['cohort']['sources'][role]['path']
            path=self.f.root/(role+'.py');path.write_text('# unrelated fixture\n');path.chmod(0o600);original=ref(path)
            q['cohort']['sources'][role]=two(original)
            q['originals']=[r for r in q['originals'] if r['path']!=old]+[original]
            with self.subTest(role=role),self.assertRaisesRegex(g.p.Held,'owning-role-bytes'):
                g.Emitter(put(self.f.root/'bad-role.json',q),self.f.output,transport=self.f.transport)
        self.assertEqual(self.f.calls,[])

    def test_current_native310_runtime_guard_accepts(self):
        from types import SimpleNamespace
        exec(self.runtime_version_guard(),{'sys':SimpleNamespace(version_info=(3,10,22))})

    def test_modern_tagger313_is_not_native_runtime(self):
        from types import SimpleNamespace
        with self.assertRaises(AssertionError):
            exec(self.runtime_version_guard(),{'sys':SimpleNamespace(version_info=(3,13,16))})

    def test_connected_source_emitter_and_actual_consumer_keep_rights_false(self):
        emitted,receipt=self.fixture_payload();cohort=active.SourceCohort(emitted);cohort.close()
        self.assertTrue(all(receipt[k]is False for k in g.RIGHTS));self.assertEqual(receipt['count'],sum(n for _,n in self.f.inventory))
        self.assertEqual(len(self.f.calls),7);self.assertEqual([a[-1]for a in self.f.calls if a[3]!='inspect'].count('/checks/run_reader_recovery_controls.py'),1)
    def test_missing_causal_request_and_disabled_entry_refuse(self):
        with self.assertRaises(g.p.Held):g.run(None,None)
        bad=copy.deepcopy(self.f.document);bad.pop('profile')
        with self.assertRaises(g.p.Held):g.Emitter(put(self.f.root/'bad.json',bad),self.f.output,transport=self.f.transport)
        self.assertEqual(self.f.calls,[])
    def test_wrong_nonce_readiness_refuses_before_transport(self):
        q=copy.deepcopy(self.f.document);q['nonce']='b'*64
        with self.assertRaises(g.p.Held):g.Emitter(put(self.f.root/'bad.json',q),self.f.output,transport=self.f.transport)
        self.assertEqual(self.f.calls,[])
    def test_created_worker_or_wrong_image_never_started(self):
        for key,value in [('Name','/komga-comic-normalizer-1'),('Image','sha256:'+'f'*64),('State',dict(self.f.profile['State'],Status='created',Running=False,Pid=0))]:
            q=copy.deepcopy(self.f.document);q['profile']=put(self.f.root/('bad-'+key+'.json'),dict(self.f.profile,**{key:value}))
            with self.subTest(key=key),self.assertRaises(g.p.Held):g.Emitter(put(self.f.root/'bad.json',q),self.f.output,transport=self.f.transport)
        self.assertEqual(self.f.calls,[])
    def test_live_extra_mount_or_network_refuses(self):
        for change in ('mount','network','ports'):
            row=copy.deepcopy(self.f.profile)
            if change=='mount':row['Mounts'].append(dict(Type='bind',Source='/unrelated',Destination='/data',RW=False))
            elif change=='network':row['HostConfig']['NetworkMode']='bridge'
            else:row['HostConfig']['PortBindings']={'8080/tcp':[{}]}
            q=copy.deepcopy(self.f.document);q['profile']=put(self.f.root/'profile-bad.json',row)
            with self.subTest(change=change),self.assertRaises(g.p.Held):g.Emitter(put(self.f.root/'bad.json',q),self.f.output,transport=self.f.transport)
        self.assertEqual(self.f.calls,[])
    def test_changed_source_original_refuses_before_any_exec(self):
        owner=self.f.owner();(self.f.root/'explicit-test-source.py').write_bytes(b'changed')
        with self.assertRaises(g.p.Held):owner.execute()
        self.assertEqual(self.f.calls,[]);self.assertFalse(self.f.output.exists())
    def test_wrong_runtime_binary_refuses_and_postinspect_still_runs(self):
        self.f.fault='runtime'
        with self.assertRaisesRegex(g.p.Held,'runtime-reply'):self.f.owner().execute()
        self.assertEqual(len([a for a in self.f.calls if a[3]=='inspect']),2);self.assertFalse((self.f.output/'readiness.json').exists())
    def test_nonzero_keeps_raw_stdout_stderr_before_refusal(self):
        self.f.fault='exit'
        with self.assertRaisesRegex(g.p.Held,'command-refused'):self.f.owner().execute()
        self.assertEqual((self.f.output/'controls.stdout').read_bytes(),b'partial result');self.assertEqual((self.f.output/'controls.stderr').read_bytes(),b'actual fixture failure');self.assertTrue((self.f.output/'after.stdout').exists());self.assertFalse((self.f.output/'readiness.json').exists())
    def test_partial_timeout_retained_never_retried(self):
        self.f.fault='timeout';owner=self.f.owner()
        with self.assertRaises(subprocess.TimeoutExpired):owner.execute()
        self.assertEqual((self.f.output/'controls.stdout').read_bytes(),b'partial original output');self.assertTrue((self.f.output/'after.stdout').exists())
        with self.assertRaisesRegex(g.p.Held,'no-replay'):owner.execute()
    def test_partial_suites_skip_boolean_and_grant_refuse(self):
        for fault in ('partial','skips','boolean-count','grant'):
            self.f.fault=fault
            with self.subTest(fault=fault),self.assertRaises(g.p.Held):self.f.owner().execute()
            self.assertFalse((self.f.output/'readiness.json').exists());self.f.output=self.f.root/('output-'+fault);self.f.document['output']=str(self.f.output);self.f.request_ref=put(self.f.root/('request-'+fault+'.json'),self.f.document)
    def test_late_profile_epoch_refuses_without_ready(self):
        self.f.fault='late-profile'
        with self.assertRaisesRegex(g.p.Held,'runtime-closure'):self.f.owner().execute()
        self.assertFalse((self.f.output/'readiness.json').exists())
    def test_late_source_change_refuses_without_ready(self):
        self.f.callback=lambda:(self.f.root/'explicit-test-source.py').write_bytes(b'late change')
        with self.assertRaises(g.p.Held):self.f.owner().execute()
        self.assertFalse((self.f.output/'readiness.json').exists());self.assertTrue((self.f.output/'controls.stdout').exists());self.assertTrue((self.f.output/'after.stdout').exists())
    def test_stale_request_and_output_rebinding_refuse(self):
        for change in ('expired','output'):
            q=copy.deepcopy(self.f.document)
            if change=='expired':q['observed']-=121
            else:q['output']=str(self.f.root/'different')
            with self.subTest(change=change),self.assertRaises(g.p.Held):g.Emitter(put(self.f.root/'bad.json',q),self.f.output,transport=self.f.transport)
        self.assertEqual(self.f.calls,[])
    def test_same_request_cannot_be_replayed_in_new_object(self):
        with self.assertRaisesRegex(g.p.Held,'original-transport-required'):self.f.owner().execute()
        with self.assertRaisesRegex(g.p.Held,'no-adoption'):self.f.owner()
        self.assertEqual(len(self.f.calls),7)
    def test_emitted_log_replacement_rejected_by_actual_source_consumer(self):
        out,_=self.fixture_payload();path=self.f.output/'controls.stdout';path.write_bytes(b'foreign')
        with self.assertRaises(active.Held):active.SourceCohort(out)
    def test_empty_or_partial_inventory_is_not_readiness(self):
        for raw in (b'',b'SUITES=()\n',b'SUITES=(("test_x.py",True),)\n'):
            with self.assertRaises((g.p.Held,SyntaxError)):g.suites(raw)
    def test_transport_argv_is_only_fixed_inspect_and_finite_exec(self):
        with self.assertRaisesRegex(g.p.Held,'original-transport-required'):self.f.owner().execute()
        for argv in self.f.calls:
            self.assertEqual(argv[:3],g.DOCKER);self.assertIn(argv[3],('inspect','exec'))
            if argv[3]=='exec':self.assertIn('1000:1000',argv);self.assertIn('/lsiopy/bin/python3',argv);self.assertIn('-I',argv);self.assertIn('-B',argv)

    def test_asserted_receipt_fields_are_not_execution_inputs(self):
        q=copy.deepcopy(self.f.document);q['cohort']['receipt']={'exit_code':0,'zero_skips':True,'count':1}
        with self.assertRaises(g.p.Held):g.Emitter(put(self.f.root/'forged.json',q),self.f.output,transport=self.f.transport)
        self.assertEqual(self.f.calls,[])
    def test_wrong_owning_writer_source_refuses_before_transport(self):
        q=copy.deepcopy(self.f.document);q['cohort']['sources']['writer']=q['cohort']['sources']['writer_fixture'];q['cohort']['writer_sha256']=q['cohort']['sources']['writer']['sha256']
        with self.assertRaisesRegex(g.p.Held,'owning-role'):g.Emitter(put(self.f.root/'forged.json',q),self.f.output,transport=self.f.transport)
        self.assertEqual(self.f.calls,[])
    def test_configured_cohort_cannot_replace_original_base25(self):
        q=copy.deepcopy(self.f.document);row=next(r for r in q['originals']if r['path']==q['cohort']['sources']['selected_sdk']['path']);value=g.p.decode(Path(row['path']).read_bytes());value['parent_sha256']='a'*64
        fresh=put(self.f.root/'configured.json',value);q['originals']=[fresh if r==row else r for r in q['originals']];q['cohort']['sources']['selected_sdk']=two(fresh)
        with self.assertRaisesRegex(g.p.Held,'original-maps'):g.Emitter(put(self.f.root/'forged.json',q),self.f.output,transport=self.f.transport)
        self.assertEqual(self.f.calls,[])
    def test_unknown_bundle_file_refuses_before_any_container_call(self):
        extra=self.bundle/'not-an-admitted-source';extra.write_bytes(b'private fixture only');self.addCleanup(extra.unlink)
        with self.assertRaisesRegex(g.p.Held,'no-extra-files'):self.f.owner()
        self.assertEqual(self.f.calls,[])
    def test_original_same_nonce_request_changed_after_construction_refuses(self):
        owner=self.f.owner();self.f.document['observed']+=1;put(Path(self.f.request_ref['path']),self.f.document)
        with self.assertRaises(g.p.Held):owner.execute()
        self.assertEqual(self.f.calls,[])
    def test_output_parent_replacement_cannot_adopt_foreign_namespace(self):
        parent=self.f.root/'outparent';parent.mkdir(mode=0o700);self.f.output=parent/'output';self.f.document['output']=str(self.f.output);self.f.request_ref=put(self.f.root/'new.json',self.f.document)
        def replace():parent.rename(parent.with_name('retained-parent'));parent.mkdir(mode=0o700)
        self.f.callback=replace
        with self.assertRaises(g.p.Held):self.f.owner().execute()
        self.assertEqual(list(parent.iterdir()),[])
    def test_output_leaf_replacement_during_fsync_refuses(self):
        original=os.fsync;replaced=[]
        def replace(fd):
            original(fd);path=self.f.output/'controls.stdout'
            if path.exists() and path.stat().st_ino==os.fstat(fd).st_ino and not replaced:
                raw=path.read_bytes();path.unlink();path.write_bytes(raw);path.chmod(0o600);replaced.append(True)
        with patch.object(g.os,'fsync',side_effect=replace),self.assertRaises(g.p.Held):self.f.owner().execute()
        self.assertEqual(replaced,[True]);self.assertFalse((self.f.output/'readiness.json').exists())
    def test_primary_timeout_survives_secondary_epoch_failure(self):
        self.f.fault='timeout';self.f.callback=lambda:self.f.profile['State'].update(Pid=999)
        with self.assertRaises(subprocess.TimeoutExpired):self.f.owner().execute()
        value=g.p.decode((self.f.output/'failure.json').read_bytes());self.assertEqual(value['exception_type'],'TimeoutExpired');self.assertIs(value['readiness_returned'],False);self.assertNotIn('readiness_emitted',value);self.assertEqual(value['secondary_fixed_code'],'source-original-runtime-closure');self.assertFalse((self.f.output/'readiness.json').exists())

    def test_published_linuxserver_config_volume_is_exactly_masked(self):
        # Matches the immutable published native405 Config.Volumes declaration.
        owner=self.f.owner();self.assertEqual(owner.image[0]['Config']['Volumes'],{'/config':{}})
        self.assertEqual(owner.profile['HostConfig']['Tmpfs']['/config'],'rw,nosuid,nodev,noexec,size=16777216,mode=0700,uid=1000,gid=1000')
        self.assertEqual(owner.profile['Config']['Entrypoint'],['/bin/sleep']);self.assertEqual(owner.profile['Config']['Healthcheck'],{'Test':['NONE']})
        self.assertEqual(owner.profile['Mounts'],[dict(Type='bind',Source=str(self.bundle),Destination='/checks',RW=False)])
        self.assertEqual(self.f.calls,[])
    def test_unsupported_image_volume_declarations_refuse_without_rewriting(self):
        for volumes in ({},None,{'/other':{}},{'/config':{},'/other':{}},{'/config':{'unexpected':True}}):
            image=g.p.decode(Path(self.f.document['image']['path']).read_bytes());image[0]['Config']['Volumes']=volumes
            q=copy.deepcopy(self.f.document);q['image']=put(self.f.root/'unsupported-image.json',image)
            before=Path(q['image']['path']).read_bytes()
            with self.subTest(volumes=volumes),self.assertRaisesRegex(g.p.Held,'original-image'):g.Emitter(put(self.f.root/'bad.json',q),self.f.output,transport=self.f.transport)
            self.assertEqual(Path(q['image']['path']).read_bytes(),before)
        self.assertEqual(self.f.calls,[])
    def test_unmasked_anonymous_or_shadowed_config_refuses(self):
        for change in ('unmasked','extra-tmpfs','oversized','wrong-owner','anonymous','bind-shadow'):
            row=copy.deepcopy(self.f.profile)
            if change=='unmasked':row['HostConfig']['Tmpfs'].pop('/config')
            elif change=='extra-tmpfs':row['HostConfig']['Tmpfs']['/config/subdir']='rw,size=1048576'
            elif change=='oversized':row['HostConfig']['Tmpfs']['/config']=g.CONFIG_TMPFS.replace('16777216','33554432')
            elif change=='wrong-owner':row['HostConfig']['Tmpfs']['/config']=g.CONFIG_TMPFS.replace('uid=1000','uid=0')
            elif change=='anonymous':row['Mounts'].append(dict(Type='volume',Source='/anonymous',Destination='/config',RW=True))
            else:row['Mounts'].append(dict(Type='bind',Source='/foreign',Destination='/config',RW=False))
            q=copy.deepcopy(self.f.document);q['profile']=put(self.f.root/'shadow-profile.json',row)
            with self.subTest(change=change),self.assertRaisesRegex(g.p.Held,'isolated-profile'):g.Emitter(put(self.f.root/'bad.json',q),self.f.output,transport=self.f.transport)
        self.assertEqual(self.f.calls,[])
    def test_default_health_or_application_startup_cannot_be_source_fixture(self):
        for change in ('health-missing','health-command','entrypoint','command','process-path','process-args'):
            row=copy.deepcopy(self.f.profile)
            if change=='health-missing':row['Config'].pop('Healthcheck')
            elif change=='health-command':row['Config']['Healthcheck']={'Test':['CMD-SHELL','getHealth']}
            elif change=='entrypoint':row['Config']['Entrypoint']=['/init']
            elif change=='command':row['Config']['Cmd']=None
            elif change=='process-path':row['Path']='/init'
            else:row['Args']=['10']
            q=copy.deepcopy(self.f.document);q['profile']=put(self.f.root/'active-profile.json',row)
            with self.subTest(change=change),self.assertRaisesRegex(g.p.Held,'isolated-profile'):g.Emitter(put(self.f.root/'bad.json',q),self.f.output,transport=self.f.transport)
        self.assertEqual(self.f.calls,[])

    def test_current_native405_map_preserves_census_without_historical_hash_adoption(self):
        historical=g.p.decode((HERE/'configured_reader_parent_base_sources.json').read_bytes())['base_installed_sources']
        owner=self.f.owner();self.assertEqual(set(owner.module_map),set(historical));self.assertEqual(len(owner.module_map),180)
        self.assertEqual({n:owner.module_map[n]for n in owner.module_map if owner.module_map[n]!=historical[n]},NATIVE405_DELTAS)
        selected=g.p.decode(Path(self.f.document['cohort']['sources']['selected_sdk']['path']).read_bytes())
        self.assertTrue(all(owner.module_map[r['filename']]==r['sha256']for r in selected['modules'].values()))
        self.assertEqual(self.f.calls,[])
    def test_missing_extra_and_same_count_foreign_native_names_refuse(self):
        for change in ('missing','extra','replacement'):
            native=copy.deepcopy(self.f.sdk)
            if change in ('missing','replacement'):native.pop('PostProcessor.py')
            if change in ('extra','replacement'):native['Unreviewed.py']='e'*64
            q=copy.deepcopy(self.f.document);old=q['cohort']['sources']['native_map'];fresh=put(self.f.root/('native-'+change+'.json'),native)
            q['originals']=[fresh if r['path']==old['path']else r for r in q['originals']];q['cohort']['sources']['native_map']=two(fresh);q['cohort']['native_map_count']=len(native)
            with self.subTest(change=change),self.assertRaisesRegex(g.p.Held,'complete-original-native-map'):g.Emitter(put(self.f.root/'bad.json',q),self.f.output,transport=self.f.transport)
        self.assertEqual(self.f.calls,[])
    def test_all180_hashes_are_checked_before_and_after_actual_collection(self):
        for index,fault in enumerate(('runtime-map-before','runtime-map-after')):
            self.f.calls=[];self.f.fault=fault;self.f.output=self.f.root/('map-output-'+str(index));self.f.document['output']=str(self.f.output);self.f.request_ref=put(self.f.root/('map-input-'+str(index)+'.json'),self.f.document)
            original=Path(self.f.document['cohort']['sources']['native_map']['path']).read_bytes()
            with self.subTest(fault=fault),self.assertRaisesRegex(g.p.Held,'runtime-reply'):self.f.owner().execute()
            label='runtime-before'if index==0 else'runtime-after';saved=g.p.decode((self.f.output/(label+'.stdout')).read_bytes())
            self.assertEqual(len(saved['modules']),180);self.assertNotEqual(saved['modules']['PostProcessor.py'],NATIVE405_DELTAS['PostProcessor.py'])
            self.assertEqual((self.f.output/'controls.stdout').exists(),index==1);self.assertTrue((self.f.output/'after.stdout').exists())
            self.assertFalse((self.f.output/'readiness.json').exists());self.assertEqual(Path(self.f.document['cohort']['sources']['native_map']['path']).read_bytes(),original)


if __name__=='__main__':unittest.main()
