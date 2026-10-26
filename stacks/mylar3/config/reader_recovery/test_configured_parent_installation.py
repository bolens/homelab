"""Configured artifact construction; no installed invocation or fake grant."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import ast
import importlib.util
import hashlib
import json
from pathlib import Path
import unittest
import subprocess
import tempfile
import sys
import install_configured_reader_parent as m

CONSTRUCTOR_PROGRAM = '"""Real generated Parent constructor; fixtures are private inputs, never admitted roles/Birth.\n\nDefault uses exact build output in a host namespace. Root may separately select\n--actual-install for the genuine root-only installer output/returned references.\nNo Docker/API/canary/stop/Birth call is permitted; profile boundary deliberately\nraises, so even the corrected run does not claim constructor admission.\n"""\nimport hashlib,importlib.util,json,os,sys,tempfile,types\nfrom pathlib import Path\nPUBLIC=Path(sys.argv[1]);sys.path.insert(0,str(PUBLIC))\nimport install_configured_reader_parent as installer\n\ndef ref(path):\n z=path.stat();return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=[z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink])\ndef put(path,value):\n path.write_bytes(value if type(value)is bytes else (json.dumps(value,sort_keys=True)+\'\\n\').encode());path.chmod(0o600);return ref(path)\nclass ProfilesNotRun(Exception):pass\nwith tempfile.TemporaryDirectory()as directory:\n root=Path(directory);output=root/\'configured\';operation=root/\'operation\';native=root/\'native\';native.mkdir(mode=0o700)\n locators=json.loads((PUBLIC/\'INSTALLER-SOURCE-LOCATORS.json\').read_text())\n paths={role:str((PUBLIC/path).resolve())for role,path in locators.items()};sources={role:Path(path).read_bytes()for role,path in paths.items()}\n worker_source=put(root/\'archive_terminal_observation.py\',(PUBLIC/\'_archive_worker_fixtures/archive_terminal_observation.py\').read_bytes())\n image=\'sha256:\'+\'a\'*64;image_ref=put(root/\'worker-image.json\',[dict(Id=image,Os=\'linux\',Architecture=\'amd64\')])\n map_ref=put(root/\'worker-map.json\',{\'/app/archive_terminal_observation.py\':installer.WORKER_OBSERVER_SOURCE_SHA})\n worker=dict(mode=\'original-pipes-v1\',source=worker_source,image_sources=map_ref,image_metadata=image_ref)\n base_path=PUBLIC/\'configured_reader_parent_base_sources.json\';base=json.loads(base_path.read_bytes())\n sdk={name:base[\'base_installed_sources\'][name]for name in base[\'required_sdk_names\']};sdk_ref=put(root/\'base-sdk.json\',sdk)\n actual=\'--actual-install\'in sys.argv\n if actual:\n  assert os.geteuid()==0,\'Root-only isolated fixture; no privilege projection\'\n  result=installer.install(paths,str(output),sdk_ref=sdk_ref,base_manifest_path=str(base_path),worker_observation=worker)\n  refs=result[\'output_refs\'];parent_ref=refs[str(output/\'comic_reader_lifecycle_parent.py\')]\n  effective=refs[str(output/\'configured-sdk-map.json\')]\n else:\n  artifacts,receipt=installer.build(sources,str(output/\'comic_reader_lifecycle_parent.py\'),worker_observation=worker,worker_image=image)\n  effective_sdk,_=installer.configured_maps(sdk,base_path.read_bytes(),artifacts,receipt)\n  output.mkdir(mode=0o700);refs={str(output/name):put(output/name,raw)for name,raw in artifacts.items()}\n  parent_ref=refs[str(output/\'comic_reader_lifecycle_parent.py\')];effective=put(root/\'effective-sdk.json\',effective_sdk)\n # Load precisely the returned configured Parent bytes, never an installed/default alternative.\n module=types.ModuleType(\'actual_configured_parent\');module.__file__=parent_ref[\'path\']\n exec(compile(Path(parent_ref[\'path\']).read_bytes(),parent_ref[\'path\'],\'exec\'),module.__dict__)\n sys.path.insert(0,str(output))\n projection=put(root/\'publication_native_configured_scope.py\',(PUBLIC/\'publication_native_configured_scope.py\').read_bytes())\n observer=put(root/\'comic_archive_terminal_vectors.py\',(PUBLIC/\'comic_archive_terminal_vectors.py\').read_bytes())\n adapter=put(root/\'comic_nfs_factual_successor.py\',(PUBLIC/\'comic_nfs_factual_successor.py\').read_bytes())\n active=put(root/\'comic_negative_nfs_active_parent.py\',(PUBLIC/\'comic_negative_nfs_active_parent.py\').read_bytes())\n active_input=put(root/\'active.json\',{})\n request=put(root/\'request.json\',dict(version=1,owner={\'issueid\':\'12\',\'comicid\':\'34\'},operation_id=\'b\'*64))\n scopes=put(root/\'scopes.json\',dict(version=1,scratch=str(root/\'scratch\'),retention_root=str(root/\'retention\')))\n source=lambda name:refs[str(output/name)]\n plan=dict(version=12,kind=\'reviewed-archive-one-lifecycle-protocol\',nonce=\'b\'*64,seconds=60,operation=str(operation),\n  reader=dict(id=\'1\'*64,profile={}),held_native=dict(id=\'2\'*64,profile={}),held_worker=dict(id=\'3\'*64,profile={}),selected_image=image,\n  provider=source(\'comic_archive_repair_action.py\'),backup_provider=source(\'comic_archive_backup_action.py\'),producer=source(\'comic_archive_evidence_adapter.py\'),\n  observer=observer,sdk_map=effective,mounts=[dict(host=str(operation),child=\'/_operation\',write=True),dict(host=str(native),child=\'/fixture-native\',write=False)],\n  native=dict(data=\'/fixture-native\',roots=[\'/fixture-native\']),action=\'archive-one\',producer_inputs=dict(archive_request=request,archive_scopes=scopes),\n  birth_source_sha256=sdk[\'publication_native_scope_birth.py\'],scope_projection=projection,bounds={},\n  nfs=dict(adapter=adapter,active_parent=active,active_input=active_input),terminal_mode=\'same-child-v1\',worker_observation={k:worker[k]for k in (\'mode\',\'source\',\'image_sources\')})\n plan_ref=put(root/\'plan.json\',plan);engine=module.ScopedDocker();calls=[]\n def no_engine(args,seconds):calls.append(args[0]);raise ProfilesNotRun()\n engine.run=no_engine\n try:module.LifecycleParent(plan_ref,parent_ref,engine)\n except FileNotFoundError as error:\n  assert Path(error.filename)==output/\'comic_archive_worker_vectors.py\'\n  assert not calls and not operation.exists()\n  print(json.dumps(dict(actual_install=actual,missing_reviewed_sibling=True,operation_created=False,engine_calls=0,birth=False,constructor_admission=False),sort_keys=True))\n except ProfilesNotRun:\n  assert calls==[\'inspect\']and not operation.exists()\n  assert (output/\'comic_archive_worker_vectors.py\').is_file()\n  print(json.dumps(dict(actual_install=actual,missing_reviewed_sibling=False,operation_created=False,engine_calls=0,profile_boundary_reached=True,birth=False,constructor_admission=False),sort_keys=True))\n else:raise AssertionError(\'Fixture must never claim real admission\')\n'

ARCHIVE_GRAPH_PROGRAM = "import hashlib,json,sys,tempfile,types\nfrom pathlib import Path\npublic=Path(sys.argv[1]);mode=sys.argv[2];sys.path.insert(0,str(public));import install_configured_reader_parent as installer\n\ndef load(path):\n m=types.ModuleType(path.stem);m.__file__=str(path);exec(compile(path.read_bytes(),str(path),'exec'),m.__dict__);return m\n\ndef put(path,raw):path.write_bytes(raw);path.chmod(0o600)\ndef ref(path):\n z=path.stat();return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=[z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns,z.st_mode,z.st_uid,z.st_gid,z.st_nlink])\ndef held(cls,fn):\n try:fn()\n except cls:return\n raise AssertionError('Expected original-bound refusal')\ndef all_loads(folder):\n backup=load(folder/'comic_archive_backup_action.py');o=backup.p.Originals([])\n for name,pin in backup.p.PINS.items():\n  assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==pin\n  backup.p.module(name,o)\n reader=backup.p.module('comic_reader_backup.py',o)\n assert reader.PRIMITIVES==folder/'comic_reader_backup_primitives.py'\n assert hashlib.sha256(reader.PRIMITIVES.read_bytes()).hexdigest()==reader.PRIMITIVES_SHA\n reader.load(reader.PRIMITIVES.read_bytes())\n adapter=load(folder/'comic_archive_evidence_adapter.py');reads=adapter.Reads()\n reads.module('publication_native_configured_scope.py',adapter.SCOPE_SHA)\n reads.module('comic_native_process_probe.py',adapter.PROBE_SHA)\n reads.module('comic_archive_repair_action.py',adapter.ACTION_SHA)\n reads.module('comic_archive_proof_producer.py',adapter.PRODUCER_SHA)\n assert adapter.PRODUCER_SHA==adapter.TERMINAL_PRODUCER_SHA\n return backup\nwith tempfile.TemporaryDirectory()as d:\n root=Path(d);out=root/'output';out.mkdir(mode=0o700)\n loc=json.loads((public/'INSTALLER-SOURCE-LOCATORS.json').read_text());sources={n:(public/p).read_bytes()for n,p in loc.items()}\n artifacts,_=installer.build(sources,str(out/'comic_reader_lifecycle_parent.py'))\n for n,raw in artifacts.items():put(out/n,raw)\n assert len(artifacts)==13\n if mode=='host':all_loads(out)\n else:\n  backup=all_loads(out);projection=load(public/'comic_child_control_projection.py')\n  names={'comic_archive_backup_action.py','comic_archive_repair_action.py','comic_archive_evidence_adapter.py','comic_archive_proof_producer.py',*backup.p.PINS,'comic_native_process_probe.py'}\n  assert len(names)==9;refs={n:ref(out/n)for n in names};old={n:r.copy()for n,r in refs.items()}\n  original=root/'operation';original.mkdir(mode=0o700)\n  def tree(name):return projection.Tree(root/name,Path('/_operation'),original,lambda r:backup.a.checked(r)[0])\n  if mode=='projection':\n   t=tree('child');projected=t.archive_sources(refs);folder=Path(next(iter(projected.values()))['path']).parent\n   assert all(Path(r['path']).parent==folder for r in projected.values())\n   all_loads(folder);assert t.archive_sources(refs)==projected\n   assert t.project(refs['comic_archive_backup_action.py'])==projected['comic_archive_backup_action.py']\n   for n,r in refs.items():assert ref(Path(r['path']))==old[n]\n   assert len(t.readonly_files())==9\n   for host,child in t.readonly_files():assert t.host(child)==host\n   # Unrelated files retain the old individual per-file control directory.\n   other=root/'other.json';put(other,b'{}');pr=t.project(ref(other))\n   assert Path(pr['path']).parent.name=='control-'+hashlib.sha256(str(other).encode()).hexdigest()[:24]\n   t.check()\n  elif mode=='refusals':\n   t=tree('missing');bad=dict(refs);bad.pop('comic_reader_schema.py');held(projection.Held,lambda:t.archive_sources(bad));assert not t.pairs\n   bad=dict(refs,foreign=refs['comic_reader_schema.py']);held(projection.Held,lambda:t.archive_sources(bad))\n   bad=dict(refs);bad['comic_reader_schema.py']=refs['comic_reader_backup.py'];held(projection.Held,lambda:t.archive_sources(bad))\n   t=tree('partial');t.project(refs['comic_reader_schema.py']);held(projection.Held,lambda:t.archive_sources(refs))\n   t=tree('collision');prefix=t.root/('control-archive-'+hashlib.sha256(str(out).encode()).hexdigest()[:24]);prefix.mkdir();held(projection.Held,lambda:t.archive_sources(refs))\n   t=tree('foreign');rows=t.archive_sources(refs);folder=Path(next(iter(rows.values()))['path']).parent;put(folder/'foreign.py',b'x');held(projection.Held,t.check)\n   t=tree('changed');rows=t.archive_sources(refs);put(Path(rows['comic_reader_schema.py']['path']),b'foreign');held(projection.Held,t.check)\n   t=tree('old-original');put(out/'comic_reader_schema.py',(out/'comic_reader_schema.py').read_bytes()+b'\\n');held(backup.a.Held,lambda:t.archive_sources(refs))\n  else:raise AssertionError(mode)\n print(json.dumps(dict(mode=mode,passed=True,Parent_admission=False,Birth=False,operations=False),sort_keys=True))\n"

class Installation(unittest.TestCase):
    def setUp(self):
        refs=json.loads(Path(__file__).with_name('INSTALLER-SOURCE-LOCATORS.json').read_text())
        self.sources={name:(Path(__file__).parent/path).read_bytes() for name,path in refs.items()}
        self.path='/private/public-operation/comic_reader_lifecycle_parent.py'
    def test_approved_artifacts_preserve_bodies_and_originals(self):
        before=dict(self.sources);files,receipt=m.build(self.sources,self.path)
        self.assertEqual(self.sources,before)
        self.assertEqual(len(files),13)
        self.assertEqual(receipt['parent_sha256'],hashlib.sha256(files['comic_reader_lifecycle_parent.py']).hexdigest())
        self.assertIn(b'CHILD_CONTROL_PROJECTION_ENABLED = True',files['comic_reader_lifecycle_parent.py'])
        self.assertIn(receipt['parent_sha256'].encode(),files['publication_reader_admission.py'])
        self.assertIn(receipt['child_parent_source'].encode(),files['publication_reader_admission.py'])
        self.assertIn(b'PARENT_SHA = None',self.sources['admission'])
        self.assertIn(b'PARENT_SOURCE_SHA=None',self.sources['archive_action'])
        self.assertFalse(receipt['installation_authority']);self.assertFalse(receipt['lifecycle_authority']);self.assertFalse(receipt['base_image_parity'])
        for raw in files.values():ast.parse(raw,feature_version=(3,10))
    def test_worker_sibling_is_fixed_pinned_and_in_effective_outputs(self):
        files,receipt=m.build(self.sources,self.path)
        raw=self.sources['worker_vectors']
        self.assertEqual(files['comic_archive_worker_vectors.py'],raw)
        self.assertEqual(receipt['effective_sources']['comic_archive_worker_vectors.py'],m.EXPECTED['worker_vectors'])
        parent=ast.parse(files['comic_reader_lifecycle_parent.py'])
        pin=ast.literal_eval(next(n.value for n in parent.body if isinstance(n,ast.Assign) and getattr(n.targets[0],'id',None)=='WORKER_VECTORS_SHA'))
        self.assertEqual(pin,hashlib.sha256(raw).hexdigest())
        missing=dict(self.sources);missing.pop('worker_vectors')
        with self.assertRaisesRegex(m.Held,'configured-source-roles'):m.build(missing,self.path)
        changed=dict(self.sources);changed['worker_vectors']+=b'\n'
        with self.assertRaisesRegex(m.Held,'configured-reviewed-source-pin'):m.build(changed,self.path)
        base,sdk=self.base_map();files.pop('comic_archive_worker_vectors.py')
        with self.assertRaisesRegex(m.Held,'configured-derived-artifact-joins'):m.configured_maps(sdk,base,files,receipt)
    def test_actual_generated_constructor_closes_sibling_before_profile_boundary(self):
        result=subprocess.run([sys.executable,'-I','-B','-c',CONSTRUCTOR_PROGRAM,str(Path(__file__).parent)],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        value=json.loads(result.stdout)
        self.assertFalse(value['missing_reviewed_sibling'])
        self.assertTrue(value['profile_boundary_reached'])
        self.assertFalse(value['operation_created']);self.assertFalse(value['birth'])
        self.assertFalse(value['constructor_admission']);self.assertFalse(value['actual_install'])
        self.assertEqual(value['engine_calls'],0)
    def test_configured_loader_graph_joins_actual_generated_leaves(self):
        files,_=m.build(self.sources,self.path)
        pins={name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()}
        backup=ast.parse(files['comic_archive_backup_action.py'])
        calls=[n for n in ast.walk(backup) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='_helper']
        for call in calls:
            name=ast.literal_eval(call.args[0]);pin=ast.literal_eval(call.args[1])
            if name in pins:self.assertEqual(pin,pins[name],name)
        producer=ast.parse(files['comic_archive_proof_producer.py'])
        table=ast.literal_eval(next(n.value for n in producer.body if isinstance(n,ast.Assign) and getattr(n.targets[0],'id',None)=='PINS'))
        self.assertEqual(table['comic_archive_repair_action.py'],pins['comic_archive_repair_action.py'])
        adapter=ast.parse(files['comic_archive_evidence_adapter.py'])
        table={n.targets[0].id:ast.literal_eval(n.value) for n in adapter.body if isinstance(n,ast.Assign) and getattr(n.targets[0],'id',None) in ('ACTION_SHA','PRODUCER_SHA','TERMINAL_PRODUCER_SHA')}
        self.assertEqual(table,{'ACTION_SHA':pins['comic_archive_repair_action.py'],'PRODUCER_SHA':pins['comic_archive_proof_producer.py'],'TERMINAL_PRODUCER_SHA':pins['comic_archive_proof_producer.py']})
    def test_generated_backup_loads_actual_generated_producer(self):
        files,_=m.build(self.sources,self.path)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name,raw in files.items():(root/name).write_bytes(raw)
            script="import sys;sys.path.insert(0,sys.argv[1]);import comic_archive_backup_action as b;import hashlib;from pathlib import Path;assert b.p.PINS['comic_archive_repair_action.py']==hashlib.sha256(Path(b.a.__file__).read_bytes()).hexdigest();print('actual-generated-load')"
            result=subprocess.run([sys.executable,'-I','-B','-c',script,str(root)],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.strip(),'actual-generated-load')
    def archive_graph(self,mode):
        result=subprocess.run([sys.executable,'-I','-B','-c',ARCHIVE_GRAPH_PROGRAM,str(Path(__file__).parent),mode],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        value=json.loads(result.stdout);self.assertTrue(value['passed'])
        self.assertFalse(value['operations']);self.assertFalse(value['Parent_admission']);self.assertFalse(value['Birth'])
    def test_generated_provider_complete_fixed_graph_loads(self):self.archive_graph('host')
    def test_actual_child_projection_preserves_fixed_provider_siblings(self):self.archive_graph('projection')
    def test_fixed_group_refuses_missing_collision_foreign_and_original_drift(self):self.archive_graph('refusals')
    def test_actual_child_label_predicate_preserves_inherited_labels(self):
        # Exact owning caller predicate only; no Parent/factory positive claim.
        tree=ast.parse(self.sources['parent'])
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='LifecycleParent')
        fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='child_phase')
        start=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.Assign) and any(getattr(t,'id',None)=='expected_labels' for t in n.targets))
        body=ast.Module(body=fn.body[start:start+4],type_ignores=[]);code=compile(ast.fix_missing_locations(body),'<actual-child-label-predicate>','exec')
        holder=object();labels={'org.opencontainers.image.source':'public-fixture'}
        def run(current,original=labels):
            exec(code,{'self':holder,'name':'owned','created':{'Config':{'Labels':current}},'_CONFIGURED_IMAGE_LABELS':{holder:tuple(sorted(original.items()))},'need':m.need,'Held':m.Held})
        run({**labels,'com.homelab.reader.lifecycle':'owned'})
        with self.assertRaisesRegex(m.Held,'child-exact-label'):run({'com.homelab.reader.lifecycle':'owned'})
        with self.assertRaisesRegex(m.Held,'child-exact-label'):run({**labels,'com.homelab.reader.lifecycle':'owned','foreign':'value'})
        with self.assertRaisesRegex(m.Held,'reserved-label'):run({}, {'com.homelab.reader.lifecycle':'foreign'})
    def test_foreign_source_cannot_set_parent_digest(self):
        self.sources['parent']+=b'\nforeign=True\n'
        with self.assertRaisesRegex(m.Held,'configured-reviewed-source-pin'):m.build(self.sources,self.path)
    def test_caller_cannot_add_an_arbitrary_source_role(self):
        self.sources['foreign']=b'x'
        with self.assertRaisesRegex(m.Held,'configured-source-roles'):m.build(self.sources,self.path)
    def test_noncanonical_or_foreign_parent_paths_refuse(self):
        for p in ('relative.py','/private/../comic_reader_lifecycle_parent.py','/private//comic_reader_lifecycle_parent.py','/private/other.py'):
            with self.subTest(path=p),self.assertRaisesRegex(m.Held,'configured-parent-original-path'):m.build(self.sources,p)
    def base_map(self):
        raw=Path(__file__).with_name('configured_reader_parent_base_sources.json').read_bytes();base=json.loads(raw)
        return raw,{name:base['base_installed_sources'][name] for name in base['required_sdk_names']}
    def before_channel_deadline(self,raw):
        base=json.loads(raw)
        previous={
            'publication_native_configured_scope.py':'43dfd29de92f2dd963b876b261add29f1d251b11d612f18f56e43b72ed9516ed',
            'publication_reader_lifecycle.py':'b565928be8931506545e3665d0c76ceabaa4b9d6bf5a021a555c8a9dcc15c8a2',
            'publication_native_scope_birth.py':'28dfcb92ec2f0267ecf97ac05f12136ee9ff2fbe242ea20d155c399567e610ef',
            'publication_reader_admission.py':'123868982120d6b2071d88defd1635fd3205d0777bfb925728e8672b881a8475',
            'publication_archive_preparation_existing.py':'59c118351011a01cbce48cff679862fd3a5f499acbb97811d542968d7512fae4',
            'publication_archive_history.py':'dc9a4a66342ebf5fb34b676c1a1e736e0d929582054298703efb8fa0c4526456'}
        for name,pin in previous.items():raw=raw.replace(base['base_installed_sources'][name].encode(),pin.encode())
        return raw
    def test_reviewed_adoption_base_successor_preserves_historical_membership(self):
        raw,sdk=self.base_map();base=json.loads(raw)
        name='publication_archive_adoption.py'
        new=m.sha(Path(__file__).parent.parent.joinpath(name).read_bytes())
        old='29a7580ecfcb2f9ead388dd0b3ad4f2954ee6fdc0d431508af87b34798e900e9'
        self.assertNotEqual(new,old)
        self.assertEqual(base['base_installed_sources'][name],new)
        historical=self.before_channel_deadline(raw).replace(b'    "worker_health.py",\n',b'').replace(new.encode(),old.encode()).replace(base['base_cohort_sha256'].encode(),b'c447d5f6fcb44563f71b95faab69dba128125ec724087b39a17c4f695e1efde0').replace(b'92771edb84e81fa547906f9813d7440b76b3fa390022261f641ae1777025bb9e',b'3da7fb0fc4c72ac20b321e405a5567db8d173bf6e27ab25994b89aaf1df6b680').replace(b'b19d1254ed66603aae924393e1fc77ba70fe175e3249dc2b8f7f4dcccb8c5866',b'200db5062daec20e226de5d59b20624e5c7e73ae43a555327156c9167718b744')
        self.assertEqual(m.sha(historical),'b6d0c3571128ac80c57961bd9396bd719b302b30578afb9763238bc531e7df1c')
        before=json.loads(historical)
        self.assertEqual([n for n in base['required_sdk_names'] if n!='worker_health.py'],before['required_sdk_names'])
        self.assertEqual(set(base['base_installed_sources']),set(before['base_installed_sources']))
        self.assertEqual(len(sdk),103);self.assertEqual(len(base['base_installed_sources']),180)
        self.assertEqual(base['base_cohort'],json.loads(Path(__file__).parent.parent.joinpath('publication_reader_cohort.json').read_bytes()))

    def test_stale_adoption_base_and_sdk_refuse_new_reviewed_source_joins(self):
        raw,sdk=self.base_map();files,receipt=m.build(self.sources,self.path)
        new=sdk['publication_archive_adoption.py'];old='29a7580ecfcb2f9ead388dd0b3ad4f2954ee6fdc0d431508af87b34798e900e9'
        stale=self.before_channel_deadline(raw).replace(b'    "worker_health.py",\n',b'').replace(new.encode(),old.encode()).replace(json.loads(raw)['base_cohort_sha256'].encode(),b'c447d5f6fcb44563f71b95faab69dba128125ec724087b39a17c4f695e1efde0').replace(b'92771edb84e81fa547906f9813d7440b76b3fa390022261f641ae1777025bb9e',b'3da7fb0fc4c72ac20b321e405a5567db8d173bf6e27ab25994b89aaf1df6b680').replace(b'b19d1254ed66603aae924393e1fc77ba70fe175e3249dc2b8f7f4dcccb8c5866',b'200db5062daec20e226de5d59b20624e5c7e73ae43a555327156c9167718b744')
        self.assertEqual(m.sha(stale),'b6d0c3571128ac80c57961bd9396bd719b302b30578afb9763238bc531e7df1c')
        with self.assertRaisesRegex(m.Held,'configured-base-source-manifest'):m.configured_maps(sdk,stale,files,receipt)
        old_sdk=dict(sdk);old_sdk['publication_archive_adoption.py']=old
        with self.assertRaisesRegex(m.Held,'configured-base-sdk-pins'):m.configured_maps(old_sdk,raw,files,receipt)
        effective,cohort=m.configured_maps(sdk,raw,files,receipt)
        self.assertEqual(effective['publication_archive_adoption.py'],new)
        self.assertFalse(cohort['runtime_acceptance']);self.assertFalse(cohort['publication_acceptance'])

    def test_effective_sdk_and_cohort_only_admission_hash_changes(self):
        raw,sdk=self.base_map();before=dict(sdk);files,receipt=m.build(self.sources,self.path)
        effective,cohort=m.configured_maps(sdk,raw,files,receipt)
        self.assertEqual(sdk,before);self.assertEqual(set(effective),set(sdk))
        self.assertEqual([name for name in sdk if sdk[name]!=effective[name]],['publication_reader_admission.py'])
        original=json.loads(raw)['base_cohort'];expected=json.loads(json.dumps(original));expected['parent_sha256']=receipt['parent_sha256'];expected['modules']['publication_reader_admission']['sha256']=effective['publication_reader_admission.py']
        self.assertEqual(cohort,expected);self.assertFalse(cohort['runtime_acceptance']);self.assertFalse(cohort['publication_acceptance'])
    def test_incomplete_foreign_sdk_or_changed_base_source_refuses(self):
        raw,sdk=self.base_map();files,receipt=m.build(self.sources,self.path)
        missing=dict(sdk);missing.pop('publication_reader_admission.py')
        with self.assertRaisesRegex(m.Held,'configured-complete-known-sdk'):m.configured_maps(missing,raw,files,receipt)
        foreign=dict(sdk);foreign['publication_guard.py']='0'*64
        with self.assertRaisesRegex(m.Held,'configured-base-sdk-pins'):m.configured_maps(foreign,raw,files,receipt)
        with self.assertRaisesRegex(m.Held,'configured-base-source-manifest'):m.configured_maps(sdk,raw+b' ',files,receipt)
        for name,pin in {'publication_native_configured_scope.py':'43dfd29de92f2dd963b876b261add29f1d251b11d612f18f56e43b72ed9516ed','publication_native_scope_birth.py':'a0379e5a4b41b112249155ef8baaa5c3a15e7efaa26721aab513cdfb5ead29a1'}.items():
            stale=dict(sdk);stale[name]=pin
            with self.subTest(module=name),self.assertRaisesRegex(m.Held,'configured-base-sdk-pins'):m.configured_maps(stale,raw,files,receipt)
    def test_derived_artifact_map_join_cannot_adopt_changed_output(self):
        raw,sdk=self.base_map();files,receipt=m.build(self.sources,self.path);files['publication_reader_admission.py']+=b'\nforeign=True\n'
        with self.assertRaisesRegex(m.Held,'configured-derived-artifact-joins'):m.configured_maps(sdk,raw,files,receipt)
    def test_projection_pair_path_exactly_derived_from_original(self):
        _,r=m.build(self.sources,self.path)
        expected='/_operation/control-'+hashlib.sha256(self.path.encode()).hexdigest()[:24]+'/comic_reader_lifecycle_parent.py'
        self.assertEqual(r['child_parent_source'],expected)
        _,other=m.build(self.sources,'/other/public-operation/comic_reader_lifecycle_parent.py')
        self.assertNotEqual(r['child_parent_source'],other['child_parent_source'])
    def test_nfs_helpers_are_exact_host_only_sources(self):
        sources={name:Path(__file__).with_name(name).read_bytes() for name in m.EXPECTED_NFS}
        self.assertEqual(m.build_nfs(sources),sources)
        self.assertNotIn('publication_reader_admission.py',sources)
        self.assertNotIn('native_writers.py',sources)
    def test_nfs_unknown_and_changed_sources_refuse(self):
        sources={name:Path(__file__).with_name(name).read_bytes() for name in m.EXPECTED_NFS}
        with self.assertRaisesRegex(m.Held,'exact-source-roles'):m.build_nfs(dict(sources,unknown=b'public'))
        key=next(iter(sources));sources[key]+=b'\n'
        with self.assertRaisesRegex(m.Held,'reviewed-source-pin'):m.build_nfs(sources)


class CurrentBase(unittest.TestCase):
    def test_required_sdk_reaches_actual_native_adapter_probe(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        raw,base,sdk,artifacts,receipt=self.setup_current()
        effective,_=m.configured_maps(sdk,raw,artifacts,receipt)
        # Keep real map derivation, built archive adapter and both pin consumers.
        # Process custody and engine transport are projected, not runtime proof.
        for name,source in [('comic_archive_evidence_adapter.py',artifacts['comic_archive_evidence_adapter.py']),('comic_native_evidence_adapter.py',Path(__file__).with_name('comic_native_evidence_adapter.py').read_bytes())]:
            spec=importlib.util.spec_from_file_location('configured_adapter',Path(__file__).with_name(name))
            actual=importlib.util.module_from_spec(spec)
            exec(compile(source,spec.origin,'exec'),actual.__dict__)
            observed={'held_native':{'Id':'a'*64},'held_worker':{}}
            child={'Id':'b'*64,'Image':'selected','Mounts':[]}
            class Owner:
                def continuous(self):return observed
                def inspect(self,cid):
                    self_test.assertEqual(cid,child['Id']);return child
            self_test=self;owner=Owner();captured=[]
            class ReachedProbe(Exception):pass
            def probe(cid,source,query,seconds):
                captured.append(query['module_pins']);raise ReachedProbe
            context=(SimpleNamespace(raw=lambda p:b'checked scope'),{'selected_image':'selected'},SimpleNamespace(observed_worker=lambda w:None),effective,b'checked probe')
            with patch.object(actual,'context',return_value=context),patch.object(actual,'deadline',return_value=20),patch.object(actual,'probe_exec',side_effect=probe),patch.dict(Owner.continuous.__globals__,same_runtime=lambda a,b:a==b):
                with self.assertRaises(ReachedProbe):
                    actual.native_observation({'nonce':'c'*64,'context':{'observations':observed,'child':child,'child_mounts':[]}},watch=owner.continuous)
            self.assertEqual(captured,[{'/app/mylar3/mylar/'+name:base['base_installed_sources'][name] for name in ('worker_health.py','native_writers.py')}])

    def test_required_native_probe_sources_cannot_be_omitted_from_sdk(self):
        raw,base,sdk,artifacts,receipt=self.setup_current()
        for name in ('worker_health.py','native_writers.py','publication_native_configured_scope.py'):
            missing=dict(sdk);missing.pop(name)
            with self.subTest(name=name),self.assertRaisesRegex(m.Held,'configured-complete-known-sdk'):
                m.configured_maps(missing,raw,artifacts,receipt)

    # Exact original449 / checked adapter / derived output source-only pins.
    # The private derivation replays actual raw bytes; this is not image proof.
    GETCOMICS_DERIVATION=('200db5062daec20e226de5d59b20624e5c7e73ae43a555327156c9167718b744',
        '9e5a1e0a161a3c34ae17692ce4519c0f6d89439c8d7b766145ab02dccc082892',
        'b19d1254ed66603aae924393e1fc77ba70fe175e3249dc2b8f7f4dcccb8c5866')
    CURRENT_PINS=(
        ('publication_guard.py',
         'dac064334086345760b572debdcbc0dade39d17fb7a7e60d2b2bbb38f026f582'),
        ('comic_retained_standalone_action.py','92771edb84e81fa547906f9813d7440b76b3fa390022261f641ae1777025bb9e'),
        ('api.py',
         'a4b8bd68338297d6c0f0039c9d95b9386ebddee8c989085d610c227a70611c2b'),
        ('native_writers.py',
         '98c09f8620aa900e133bc00eed6f475d3245311ba9d5252edd4a2aa61649ee74'),
        ('pack_catalog.py',
         '00d63d4d2958a650681eaf927dcf2b36c17f2f85647e3a85a8397f93efba8f9f'))
    OLD_PINS=(('getcomics.py','200db5062daec20e226de5d59b20624e5c7e73ae43a555327156c9167718b744'),('comic_retained_standalone_action.py','3da7fb0fc4c72ac20b321e405a5567db8d173bf6e27ab25994b89aaf1df6b680'),('publication_guard.py','a07fae80712894ca67433db570b89b0382fc7f328d4c98b4c54fa2fcfa1752b1'),('api.py',
                  '23b8e01c547f70a8dd74004560f206fb29e553128aca819d6b4f81d8e250997d'),('native_writers.py','cb36fc620262ea810d7328c228f9722cd4af34a6b818e10d94257aa1165e5202'),('pack_catalog.py','908fcb7df3ab25916290bb1139761e3e1286cfaa460c8c089a6f002495cfee20'))
    def setup_current(self):
        refs=json.loads(Path(__file__).with_name('INSTALLER-SOURCE-LOCATORS.json').read_text())
        sources={name:(Path(__file__).parent/path).read_bytes() for name,path in refs.items()}
        artifacts,receipt=m.build(sources,'/private/public-operation/comic_reader_lifecycle_parent.py')
        raw=Path(__file__).with_name('configured_reader_parent_base_sources.json').read_bytes();base=json.loads(raw)
        sdk={name:base['base_installed_sources'][name] for name in base['required_sdk_names']}
        for name,pin in self.CURRENT_PINS:sdk[name]=pin
        return raw,base,sdk,artifacts,receipt
    def test_reviewed_current_sdk_and_optional_api_join_exactly(self):
        raw,base,sdk,artifacts,receipt=self.setup_current();before=dict(sdk)
        effective,cohort=m.configured_maps(sdk,raw,artifacts,receipt)
        self.assertEqual(sdk,before);self.assertEqual(len(base['base_installed_sources']),180);self.assertEqual(len(base['required_sdk_names']),103)
        for name,pin in self.CURRENT_PINS:self.assertEqual(base['base_installed_sources'][name],pin)
        self.assertEqual([name for name in sdk if sdk[name]!=effective[name]],['publication_reader_admission.py'])
        original,adapter,derived=self.GETCOMICS_DERIVATION
        self.assertEqual(dict(self.OLD_PINS)['getcomics.py'],original)
        self.assertNotEqual(original,derived);self.assertEqual(len(adapter),64)
        self.assertNotIn('getcomics.py',base['required_sdk_names'])
        self.assertEqual(base['base_installed_sources']['getcomics.py'],derived)
        full=dict(sdk,**{'getcomics.py':derived})
        joined,_=m.configured_maps(full,raw,artifacts,receipt)
        self.assertEqual(joined['getcomics.py'],derived)
        self.assertFalse(cohort['runtime_acceptance']);self.assertFalse(cohort['publication_acceptance']);self.assertIsNone(base['image']);self.assertFalse(base['installed_acceptance'])
    def test_each_old_generation_sdk_digest_still_refuses(self):
        raw,base,sdk,artifacts,receipt=self.setup_current()
        for name,pin in self.OLD_PINS:
            bad=dict(sdk);bad[name]=pin
            with self.subTest(name=name),self.assertRaisesRegex(m.Held,'configured-base-sdk-pins'):m.configured_maps(bad,raw,artifacts,receipt)
    def test_current_cohort_provenance_and_all_strict_guards_remain(self):
        raw,base,sdk,artifacts,receipt=self.setup_current()
        self.assertEqual(base['base_cohort_sha256'],'3ed607e05797f48f4a93d8193919567718e507c077e930c6fc02560661d74cd7')
        self.assertEqual(len(base['base_cohort']['modules']),25);self.assertEqual(len(base['base_cohort']['existing_sdk_closure']),80)
        fixes=Path(__file__).parent.parent
        parent=ast.parse((fixes/'reader_recovery/comic_reader_lifecycle_parent.py').read_bytes())
        pin=next(ast.literal_eval(n.value) for n in parent.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='BASE_ADMISSION_SHA' for t in n.targets))
        self.assertEqual(pin,base['base_installed_sources']['publication_reader_admission.py'])
        self.assertEqual(pin,m.sha((fixes/'publication_reader_admission.py').read_bytes()))
        action=fixes/'reader_recovery/comic_retained_standalone_action.py'
        tree=ast.parse((fixes/'patch_publication_retained_standalone.py').read_text())
        sources=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SOURCES' for t in n.targets)))
        relative,pin=sources['comic_retained_standalone_action']
        self.assertEqual(fixes/relative,action);self.assertEqual(m.sha(action.read_bytes()),pin)
        self.assertEqual(base['base_installed_sources'][action.name],pin)
        for name,pin in self.CURRENT_PINS:
            if name!='api.py':self.assertEqual(base['base_cohort']['existing_sdk_closure'][name[:-3]]['tracked_source_sha256'],pin)
        with self.assertRaisesRegex(m.Held,'configured-base-source-manifest'):m.configured_maps(sdk,raw+b' ',artifacts,receipt)
        missing=dict(sdk);missing.pop('pack_catalog.py')
        with self.assertRaisesRegex(m.Held,'configured-complete-known-sdk'):m.configured_maps(missing,raw,artifacts,receipt)
        foreign=dict(sdk);foreign['foreign.py']='0'*64
        with self.assertRaisesRegex(m.Held,'configured-complete-known-sdk'):m.configured_maps(foreign,raw,artifacts,receipt)

if __name__=='__main__':unittest.main()
