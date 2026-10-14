"""Configured artifact construction; no installed invocation or fake grant."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import ast
import hashlib
import json
from pathlib import Path
import unittest
import subprocess
import tempfile
import sys
import install_configured_reader_parent as m

class Installation(unittest.TestCase):
    def setUp(self):
        refs=json.loads(Path(__file__).with_name('INSTALLER-SOURCE-LOCATORS.json').read_text())
        self.sources={name:(Path(__file__).parent/path).read_bytes() for name,path in refs.items()}
        self.path='/private/public-operation/comic_reader_lifecycle_parent.py'
    def test_approved_artifacts_preserve_bodies_and_originals(self):
        before=dict(self.sources);files,receipt=m.build(self.sources,self.path)
        self.assertEqual(self.sources,before)
        self.assertEqual(len(files),7)
        self.assertEqual(receipt['parent_sha256'],hashlib.sha256(files['comic_reader_lifecycle_parent.py']).hexdigest())
        self.assertIn(b'CHILD_CONTROL_PROJECTION_ENABLED = True',files['comic_reader_lifecycle_parent.py'])
        self.assertIn(receipt['parent_sha256'].encode(),files['publication_reader_admission.py'])
        self.assertIn(receipt['child_parent_source'].encode(),files['publication_reader_admission.py'])
        self.assertIn(b'PARENT_SHA = None',self.sources['admission'])
        self.assertIn(b'PARENT_SOURCE_SHA=None',self.sources['archive_action'])
        self.assertFalse(receipt['installation_authority']);self.assertFalse(receipt['lifecycle_authority']);self.assertFalse(receipt['base_image_parity'])
        for raw in files.values():ast.parse(raw,feature_version=(3,10))
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
    CURRENT_PINS=(('api.py',
                  'a4b8bd68338297d6c0f0039c9d95b9386ebddee8c989085d610c227a70611c2b'),('native_writers.py','43622672cbc3ff49edc45c905f3a57883213102a5ec7203b3a1233ac2ef916fd'),('pack_catalog.py','00d63d4d2958a650681eaf927dcf2b36c17f2f85647e3a85a8397f93efba8f9f'))
    OLD_PINS=(('api.py',
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
        self.assertEqual(sdk,before);self.assertEqual(len(base['base_installed_sources']),175);self.assertEqual(len(base['required_sdk_names']),100)
        for name,pin in self.CURRENT_PINS:self.assertEqual(base['base_installed_sources'][name],pin)
        self.assertEqual([name for name in sdk if sdk[name]!=effective[name]],['publication_reader_admission.py'])
        self.assertFalse(cohort['runtime_acceptance']);self.assertFalse(cohort['publication_acceptance']);self.assertIsNone(base['image']);self.assertFalse(base['installed_acceptance'])
    def test_each_old_generation_sdk_digest_still_refuses(self):
        raw,base,sdk,artifacts,receipt=self.setup_current()
        for name,pin in self.OLD_PINS:
            bad=dict(sdk);bad[name]=pin
            with self.subTest(name=name),self.assertRaisesRegex(m.Held,'configured-base-sdk-pins'):m.configured_maps(bad,raw,artifacts,receipt)
    def test_current_cohort_provenance_and_all_strict_guards_remain(self):
        raw,base,sdk,artifacts,receipt=self.setup_current()
        self.assertEqual(base['base_cohort_sha256'],'0aac9c3a43f063f040b182dfb15b198572a6e1ce7413af2565c7c14b0423f2f4')
        self.assertEqual(len(base['base_cohort']['modules']),25);self.assertEqual(len(base['base_cohort']['existing_sdk_closure']),74)
        for name,pin in self.CURRENT_PINS:
            if name!='api.py':self.assertEqual(base['base_cohort']['existing_sdk_closure'][name[:-3]]['tracked_source_sha256'],pin)
        with self.assertRaisesRegex(m.Held,'configured-base-source-manifest'):m.configured_maps(sdk,raw+b' ',artifacts,receipt)
        missing=dict(sdk);missing.pop('pack_catalog.py')
        with self.assertRaisesRegex(m.Held,'configured-complete-known-sdk'):m.configured_maps(missing,raw,artifacts,receipt)
        foreign=dict(sdk);foreign['foreign.py']='0'*64
        with self.assertRaisesRegex(m.Held,'configured-complete-known-sdk'):m.configured_maps(foreign,raw,artifacts,receipt)

if __name__=='__main__':unittest.main()
