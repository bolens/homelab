"""Production-shaped source fixtures; no installed/NFS/publication acceptance."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import sys
sys.path.insert(0,str(Path(__file__).parent))
import configured_plan13_producer as c
import test_genuine_plan13_producer as legacy


class Controls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.fixture=legacy.Fixture(Path(self.temp.name));f=self.fixture
        old=f.doc;self.document={k:copy.deepcopy(v) for k,v in old.items()
                               if k not in ('bootstrap_plan','bootstrap_result','catalog')}
        self.document['kind']='configured-original-plan13-input'
        f.library.rename(f.common/'comics');f.library=f.common/'comics'
        f.retention.rename(f.common/'.repair');f.retention=f.common/'.repair'
        f.common.chmod(0o777);f.library.chmod(0o777);(f.common/'manga').mkdir(mode=0o775)
        self.document['publication_geometry']=dict(version=3,kind='configured-common-root-nfs',
            **{role:f.directory(path) for role,path in
               (('common_root',f.common),('library',f.library),('retention',f.retention))},
            source_mount=dict(host=str(f.common),child='/data',write=True),
            namespace={p.name:c.p.five(p.lstat()) for p in f.common.iterdir()})
        current=json.loads(Path(old['current_roles']['path']).read_bytes())
        for name,row in current['roles'].items():
            row['profile']['Name']='/configured-'+name
            row['profile']['Config']['Labels']={}
            row['epoch']=dict(Status='created' if name=='worker' else 'running',
                Running=name!='worker',Pid=0 if name=='worker' else 123,
                StartedAt='fixture',FinishedAt='',ExitCode=0,Error='',
                Paused=False,Restarting=False,Dead=False,OOMKilled=False)
        current['roles']['native']['profile']['Mounts']=[
            dict(Type='volume',Driver='local',Source=str(f.data),Destination='/config',RW=True),
            dict(Type='bind',Source=str(f.common),Destination='/data',RW=True)]
        current['roles']['reader']['profile']['Mounts']=[
            dict(Type='bind',Source=str(f.common/name),Destination='/data/'+name,RW=False)
            for name in ('comics','manga')]
        self.document['current_roles']=f.put(current)
        self.document['native']=dict(data='/config',roots=['/data/comics'])
        self.document['native_config']=f.raw(f.data/'config.ini',b'[General]\ndestination_dir = /data/comics\n')
        self.document['archive_original']=f.raw(f.library/'target.cbz',b'source-mode-target')
        self.document['archive_scopes']=f.put(dict(version=1,scratch=str(f.scratch),retention_root=str(f.retention)))
        self.document['mounts']=[dict(host=str(path),child=child,write=True) for path,child in
            ((f.common,'/data'),(f.data,'/config'),(f.scratch,'/scratch'),(f.state/'operation','/_operation'))]

    def compose(self,document=None):
        frame=c.Originals();installation=c.shared.checked_installation(frame,self.fixture.install_ref,self.fixture.base_manifest)
        return c.compose(copy.deepcopy(document or self.document),frame,installation),frame

    def test_existing_native_volume_and_media_bind_compose_without_bootstrap_authority(self):
        (plan,_,_,_),frame=self.compose()
        self.assertEqual(plan['version'],13)
        self.assertEqual(plan['native'],dict(data='/config',roots=['/data/comics']))
        self.assertEqual(plan['configured_original'],self.document['archive_original'])
        self.assertNotIn('fixture_transition',plan)
        current=json.loads(Path(self.document['current_roles']['path']).read_bytes())
        for row in current['roles'].values():
            self.assertEqual(row['profile'],c.p.static(row['profile']))
            c.p.lifecycle_state({'State':row['epoch']})
        frame.close()

    def test_embedded_lifecycle_state_cannot_replace_static_profile(self):
        current=json.loads(Path(self.document['current_roles']['path']).read_bytes())
        current['roles']['reader']['profile']['State']=copy.deepcopy(current['roles']['reader']['epoch'])
        value=copy.deepcopy(self.document);value['current_roles']=self.fixture.put(current)
        with self.assertRaisesRegex(ValueError,'configured-producer-original-role'):self.compose(value)

    def test_epoch_remains_complete_typed_and_without_health(self):
        for change in ('missing','health','type'):
            with self.subTest(change=change):
                current=json.loads(Path(self.document['current_roles']['path']).read_bytes())
                state=current['roles']['native']['epoch']
                if change=='missing':del state['FinishedAt']
                elif change=='health':state['Health']={'Status':'healthy'}
                else:state['Pid']=True
                value=copy.deepcopy(self.document);value['current_roles']=self.fixture.put(current)
                with self.assertRaises(ValueError):self.compose(value)

    def test_role_phase_drift_refuses(self):
        for role in ('native','reader','worker'):
            with self.subTest(role=role):
                current=json.loads(Path(self.document['current_roles']['path']).read_bytes())
                state=current['roles'][role]['epoch']
                state.update(Status='running'if role=='worker'else'exited',Running=role=='worker',Pid=123 if role=='worker'else 0)
                value=copy.deepcopy(self.document);value['current_roles']=self.fixture.put(current)
                with self.assertRaisesRegex(ValueError,'configured-producer-role-phase'):self.compose(value)

    def test_disposable_kind_cannot_borrow_configured_geometry(self):
        value=copy.deepcopy(self.document);value['kind']='disposable-original-plan13-input'
        with self.assertRaises(ValueError):self.compose(value)

    def test_caller_cannot_substitute_series_directory_for_configured_library(self):
        value=copy.deepcopy(self.document);value['native']['roots']=['/data/comics/Series']
        with self.assertRaises(ValueError):self.compose(value)

    def test_extra_child_shadow_refuses(self):
        value=copy.deepcopy(self.document);value['mounts'].append(dict(host=str(self.fixture.scratch),child='/data/comics',write=False))
        with self.assertRaises(ValueError):self.compose(value)

    def test_foreign_retention_does_not_match_original_scopes(self):
        value=copy.deepcopy(self.document);value['publication_geometry']['retention']['path']=str(self.fixture.scratch)
        with self.assertRaises(ValueError):self.compose(value)

    def test_changed_original_archive_identity_refuses_before_entry(self):
        _,frame=self.compose();target=Path(self.document['archive_original']['path'])
        target.chmod(0o640)
        with self.assertRaises(ValueError):frame.close()

    def test_changed_original_namespace_refuses_before_composition(self):
        (self.fixture.common/'foreign').mkdir()
        with self.assertRaises(ValueError):self.compose()

    def test_fixture_request_cannot_enter_production_constructor(self):
        value=copy.deepcopy(self.document)
        request=json.loads(Path(value['archive_request']['path']).read_bytes())
        request.update(version=3,fixture_transition={});value['archive_request']=self.fixture.put(request)
        with self.assertRaises(ValueError):self.compose(value)

    def test_unknown_constructor_fields_refuse(self):
        value=copy.deepcopy(self.document);value['bootstrap_result']={}
        with self.assertRaises(ValueError):self.compose(value)

    def test_no_selected_original_refresh_is_allowed(self):
        _,frame=self.compose();ref=copy.deepcopy(self.document['archive_original']);ref['sha256']='a'*64
        with self.assertRaises(ValueError):frame.select(ref)


if __name__=='__main__':unittest.main()
