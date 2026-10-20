"""Real local originals and finite profiles; no Docker/NFS/factory proof implied."""
import ast
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('disposable_mapping', HERE/'comic_negative_nfs_active_parent.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def ref(path, raw):
    path.write_bytes(raw); path.chmod(0o600)
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), signature9=m.stamp(path))


class Mapping(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.assertEqual((os.geteuid(), os.getegid()), (1000, 1000), 'Owning fixture requires UID/GID1000')
        self.nonce = 'a'*64
        self.common = self.base/('archive-publication-'+self.nonce)
        self.state = self.base/('archive-bootstrap-'+self.nonce)
        self.library = self.common/'L'; self.retention = self.common/'R'
        for path in (self.common, self.library, self.retention, self.state):path.mkdir(mode=0o700)
        self.geometry = dict(version=1, kind='private-common-root-nfs', **{
            role:dict(path=str(path), signature9=m.stamp(path)) for role,path in
            (('common_root',self.common),('library',self.library),('retention',self.retention))})
        self.rows = []
        mounts = {'native':[(str(self.state/'native'),'/config',True),(str(self.library),str(self.library),True)],
                  'reader':[(str(self.state/'reader'),'/config',True),(str(self.library),str(self.library),False)],
                  'worker':[(str(self.state/'worker'),'/state',True),(str(self.state/'native'/'data'),'/mylar',False),(str(self.library),'/data/comics',True)]}
        self.images = {}
        for n,role in enumerate(('native','worker','reader'),1):
            running = role != 'worker'; image = 'sha256:'+str(n)*64; self.images[role] = image
            self.rows.append(dict(Id=str(n)*64, Image=image, Name='/archive-bootstrap-'+self.nonce[:16]+'-'+role,
                Path='original-entry',Args=[],Config={'Labels':{'com.homelab.archive.bootstrap':self.nonce,'com.homelab.archive.purpose':'genuine-archive-fixture'}},
                HostConfig={'NetworkMode':'b'*64 if running else 'none'},
                NetworkSettings={'Ports':{},'Networks':{'private':{'NetworkID':'b'*64}} if running else {}},
                Mounts=[dict(Type='bind',Source=s,Destination=d,RW=w) for s,d,w in mounts[role]],
                State=dict(Status='running' if running else 'created',Running=running,Pid=400+n if running else 0,
                    Paused=False,Restarting=False,Dead=False,OOMKilled=False,StartedAt='original-'+str(n),FinishedAt='')))
        self.image_patch = patch.multiple(m,NATIVE_IMAGE=self.images['native'],WORKER=self.images['worker'],KOMGA=self.images['reader'])
        self.image_patch.start(); self.addCleanup(self.image_patch.stop)
        self.plan = dict(version=13,kind='reviewed-archive-one-lifecycle-protocol',terminal_mode='same-child-v1',action='archive-one',nonce=self.nonce,
                         publication_geometry=self.geometry,native=dict(data='/config/data',roots=[str(self.library)]),
                         mounts=[dict(host=str(self.common),child=str(self.common),write=True)])
        self.source = ref(self.base/'parent.py', b'# Captured source fixture, not an installed Parent\n')
        self.seal()

    def seal(self):
        roles = {}
        for role,row in zip(('native','worker','reader'),self.rows):
            roles[role] = dict(id=row['Id'],image=row['Image'],profile={k:copy.deepcopy(row[k]) for k in m.ROLE_STATIC},epoch=copy.deepcopy(row['State']))
            self.plan[m.ROLE_KEYS[role]] = dict(id=row['Id'],profile=copy.deepcopy(roles[role]['profile']))
        plan_ref = ref(self.base/'plan.json',m.encode(self.plan)); ancestors = {}
        for control in (plan_ref,self.source):ancestors.update(m.ancestry([Path(control['path'])]))
        self.roles = m.current_roles(m.encode(dict(version=1,kind='parent-original-current-three-role-selectors',plan=plan_ref,source=self.source,roles=roles,ancestors=ancestors)))

    def mapping(self, roots=None):
        return m.current_mapping(self.rows,[self.library] if roots is None else roots,self.roles)

    def test_creator_geometry_roundtrip_and_no_grants(self):
        result = self.mapping()
        self.assertEqual(result['media_mounts'],[dict(source=str(self.library),destination=str(self.library),rw=False)])
        self.assertEqual(m.selected_library_root(result,self.roles),self.library)
        self.assertEqual(set(result),{'native_worker','reader','media_mounts'})
        self.assertEqual(result['reader']['id'],self.rows[2]['Id'])
        with self.assertRaisesRegex(m.Held,'mylar-media-map'):m.live_mapping(self.rows,[self.library],self.roles)

    def test_additional_protected_config_root_preserved(self):
        self.assertEqual(self.mapping([self.state,self.library]),self.mapping())

    def test_descendant_writes_preserve_original_common_root(self):
        for path in (self.library,self.retention):(path/'owned').write_bytes(b'fixture')
        self.mapping()
        self.assertEqual(m.stamp(self.common),self.geometry['common_root']['signature9'])

    def test_changed_plan_ref_after_capture_refuses(self):
        (self.base/'plan.json').write_bytes(m.encode(dict(self.plan,nonce='f'*64)))
        with self.assertRaises(m.Held):self.mapping()

    def test_source_same_bytes_replacement_refuses(self):
        path=Path(self.source['path']); original=path.read_bytes(); path.rename(self.base/'retained.py'); path.write_bytes(original);path.chmod(0o600)
        with self.assertRaises(m.Held):self.mapping()

    def test_mixed_plan_source_ref_and_missing_controls_refuse(self):
        for key in ('plan','source'):
            with self.subTest(key=key):
                value=copy.deepcopy(self.roles);value[key]['sha256']='0'*64
                with self.assertRaises(m.Held):m.current_mapping(self.rows,[self.library],value)
        value=copy.deepcopy(self.roles);del value['source']
        with self.assertRaises(m.Held):m.current_mapping(self.rows,[self.library],value)

    def test_foreign_and_duplicate_original_cids_refuse(self):
        for rows in (self.rows[:2],[self.rows[0],self.rows[0],self.rows[2]]):
            with self.assertRaises(m.Held):m.current_mapping(rows,[self.library],self.roles)
        rows=copy.deepcopy(self.rows);rows[0]['Id']='f'*64
        with self.assertRaises(m.Held):m.current_mapping(rows,[self.library],self.roles)

    def test_wrong_nonce_name_or_purpose_in_original_profiles_refuse(self):
        for key in ('nonce','purpose','name'):
            with self.subTest(key=key):
                original=copy.deepcopy(self.rows)
                if key=='name':self.rows[0]['Name']='/mylar3'
                else:self.rows[0]['Config']['Labels']['com.homelab.archive.'+('bootstrap' if key=='nonce' else 'purpose')]='foreign'
                self.seal()
                with self.assertRaisesRegex(m.Held,'original-purpose'):self.mapping()
                self.rows=original

    def test_missing_or_wrong_geometry_refuses_without_fallback(self):
        original=copy.deepcopy(self.plan)
        for change in ({'publication_geometry':None},{'kind':'foreign'},{'terminal_mode':'foreign'},{'action':'foreign'}):
            self.plan=copy.deepcopy(original);self.plan.update(change);self.seal()
            with patch.object(m,'live_mapping',side_effect=AssertionError('no legacy fallback')):
                with self.assertRaises(m.Held):self.mapping()

    def test_noncanonical_or_foreign_library_path_refuses(self):
        self.plan['publication_geometry']['library']['path']=str(self.common/'other');self.seal()
        with self.assertRaises(m.Held):self.mapping()

    def test_common_root_timestamp_drift_refuses(self):
        z=self.common.stat();os.utime(self.common,ns=(z.st_atime_ns,z.st_mtime_ns+1))
        with self.assertRaises(m.Held):self.mapping()

    def test_extra_common_child_even_with_rebased_frame_refuses(self):
        (self.common/'foreign').mkdir();self.geometry['common_root']['signature9']=m.stamp(self.common);self.seal()
        with self.assertRaisesRegex(m.Held,'namespace'):self.mapping()

    def test_original_child_replacement_refuses(self):
        self.library.rename(self.base/'original-L');self.library.mkdir(mode=0o700)
        self.geometry['common_root']['signature9']=m.stamp(self.common);self.seal()
        with self.assertRaises(m.Held):self.mapping()

    def test_foreign_readonly_and_writable_mounts_refuse(self):
        for writable in (False,True):
            original=copy.deepcopy(self.rows)
            self.rows[2]['Mounts'].append(dict(Type='bind',Source=str(self.retention),Destination=str(self.retention),RW=writable));self.seal()
            with self.assertRaisesRegex(m.Held,'exact-mounts'):self.mapping()
            self.rows=original

    def test_reader_library_writable_or_aliased_refuses(self):
        original=copy.deepcopy(self.rows)
        for key,value in (('RW',True),('Destination','/data/comics'),('Source',str(self.retention))):
            self.rows=copy.deepcopy(original);self.rows[2]['Mounts'][1][key]=value;self.seal()
            with self.assertRaises(m.Held):self.mapping()

    def test_declared_common_bind_alias_mode_and_shadows_refuse(self):
        exact=dict(host=str(self.common),child=str(self.common),write=True)
        for mounts in ([],[dict(exact,write=False)],[dict(exact,child='/other')],
                       [exact,dict(host=str(self.library),child='/extra',write=False)],
                       [exact,dict(host='/other',child=str(self.retention),write=True)],
                       [exact,dict(host=str(self.base),child='/ancestor',write=False)]):
            self.plan['mounts']=mounts;self.seal()
            with self.assertRaises(m.Held):self.mapping()

    def test_worker_wrong_data_or_start_refuses(self):
        self.rows[1]['Mounts'][1]['Source']=str(self.state/'native'/'foreign');self.seal()
        with self.assertRaisesRegex(m.Held,'exact-mounts'):self.mapping()
        self.rows[1]['Mounts'][1]['Source']=str(self.state/'native'/'data')
        self.rows[1]['State'].update(Status='running',Running=True,Pid=999);self.seal()
        with self.assertRaises(m.Held):self.mapping()

    def test_network_split_host_and_published_port_refuse(self):
        original=copy.deepcopy(self.rows)
        for host in ({'NetworkMode':'host'},{'NetworkMode':'c'*64},{'NetworkMode':'b'*64,'PortBindings':{'25600/tcp':[{}]}}, {'NetworkMode':'b'*64,'Privileged':True}):
            self.rows=copy.deepcopy(original);self.rows[2]['HostConfig']=host;self.seal()
            with self.assertRaises(m.Held):self.mapping()

    def test_native_roots_and_protected_canary_scope_refuse(self):
        for roots in ([],[self.common],[self.library,self.retention]):
            with self.assertRaises(m.Held):self.mapping(roots)
        self.plan['native']['roots']=['/data/comics'];self.seal()
        with self.assertRaises(m.Held):self.mapping()

    def test_selected_library_cannot_be_a_fabricated_alias(self):
        result=self.mapping();result['media_mounts'][0]['destination']='/data/comics'
        with self.assertRaises(m.Held):m.selected_library_root(result,self.roles)

    def test_final_source_callback_cannot_replace_directory_or_profile(self):
        original=m.current_plan
        calls=[]
        def checked(roles):
            value=original(roles);calls.append(None)
            if len(calls)==3:self.library.chmod(0o755)
            return value
        with patch.object(m,'current_plan',side_effect=checked):
            with self.assertRaisesRegex(m.Held,'final-directory'):self.mapping()
        self.library.chmod(0o700);calls.clear()
        def changed(roles):
            value=original(roles);calls.append(None)
            if len(calls)==3:self.rows[2]['Mounts'][1]['RW']=True
            return value
        with patch.object(m,'current_plan',side_effect=changed):
            with self.assertRaisesRegex(m.Held,'static-original'):self.mapping()

    def test_legacy_function_source_bytes_remain_exact(self):
        source=Path(m.__file__).read_text()
        functions={n.name:n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)}
        # Exact original435 source text; independent of interpreter AST fields.
        expected={'current_roles':'c705e8305b670dde509200de8338fbafd494177367cf5934465f4b1a58960e20',
                  'select_roles':'b0e5c49812325edde05f053cdb03af03014a61764561b97f0e46d9c16af7fef4',
                  'live_mapping':'566a2a7e6eaf6d5b429bb08373eea1a55c0c3cdfa2998dc79b4479b0a060686b',
                  'identities':'e397a116f7c61ce51391f0d8b613e3100a8cb66523a33005beb4e14825b1d532',
                  'map_library_documents':'e97c393a1bffbe3252f3234622d299eb93d0251b3be7c71fe7f8717d1a0711fa',
                  'mount_identity':'bf6306bd230e333dcc2b27358fc29359de7a5b492fd12a30025e2f104e7184f1'}
        for name,sha in expected.items():
            self.assertEqual(hashlib.sha256(ast.get_source_segment(source,functions[name]).encode()).hexdigest(),sha,name)

    def test_versions_twelve_and_unconfigured_dispatch_legacy_exactly(self):
        self.plan['version']=12;self.seal(); expected=object()
        with patch.object(m,'live_mapping',return_value=expected) as legacy:
            self.assertIs(self.mapping(),expected);legacy.assert_called_once_with(self.rows,[self.library],self.roles)
        with patch.object(m,'live_mapping',return_value=expected) as legacy:
            self.assertIs(m.current_mapping(self.rows,[self.library]),expected);legacy.assert_called_once_with(self.rows,[self.library],None)
        self.assertEqual(m.selected_library_root(dict(media_mounts=[dict(source=str(self.library),destination='/data/comics',rw=False)]),self.roles),self.library)

    def test_actual_legacy_twelve_media_mapping_and_library_choice(self):
        media=self.base/'media';media.mkdir();comics=media/'comics';comics.mkdir();manga=media/'manga';manga.mkdir()
        self.rows[0]['Mounts'].append(dict(Type='bind',Source=str(media),Destination='/data',RW=True))
        self.rows[2]['Mounts']=[dict(Type='bind',Source=str(self.state/'reader'),Destination='/config',RW=True),
                               dict(Type='bind',Source=str(comics),Destination='/data/comics',RW=False),
                               dict(Type='bind',Source=str(manga),Destination='/data/manga',RW=False)]
        self.plan['version']=12;self.seal()
        actual=self.mapping([comics,manga])
        self.assertEqual(actual,m.live_mapping(self.rows,[comics,manga],self.roles))
        self.assertEqual(m.selected_library_root(actual,self.roles),comics)

    def test_actual_owning_calls_use_dispatch_and_selected_real_library(self):
        source=ast.parse(Path(m.__file__).read_bytes())
        functions={n.name:n for n in source.body if isinstance(n,ast.FunctionDef)}
        for name in ('probe_existing_parent','_probe_gated_phases','_run_owned_lifecycle'):
            called=[n.func.id for n in ast.walk(functions[name]) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
            self.assertIn('current_mapping',called);self.assertNotIn('live_mapping',called)
        called=[n.func.id for n in ast.walk(functions['_run_owned_lifecycle']) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
        self.assertIn('selected_library_root',called)


if __name__=='__main__':unittest.main(verbosity=2)
