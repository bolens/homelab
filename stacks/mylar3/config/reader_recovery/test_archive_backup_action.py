"""Actual neutral copy/restore/SQLite; synthetic stopped profile and watch only."""
from pathlib import Path
import hashlib
import importlib.util
import os
import types
import json
import shutil
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import comic_archive_backup_action as b
import test_archive_proof_producer as fixture

class Controls(fixture.Controls):
    # Select tests explicitly in the owning runner; inherited producer controls
    # retain their independent suite, never inflated backup counts.
    def setUp(self):
        super().setUp()
        self.backup_code=self.root/'backup-child-code';self.backup_code.mkdir(mode=0o700)
        for name in ('comic_reader_backup.py','comic_reader_backup_primitives.py'):
            shutil.copy2(Path(__file__).parent/name,self.backup_code/name);(self.backup_code/name).chmod(0o600)
        self.patch=patch.object(b,'HERE',self.backup_code);self.patch.start();self.addCleanup(self.patch.stop)
        self.work=self.root/'archive-neutral-backup';self.work.mkdir(mode=0o700)
        self.plan={'version':1,'action':'archive-one-backup','nonce':'b'*64,'parent_sha256':'a'*64,'command_template':[], 'operation':str(self.work),'selected_image':'sha256:'+'c'*64,'sdk_map':{},'runtime':self.observations['reader'],'native':{'data':str(self.native),'roots':[str(self.library)]},'bounds':{'files':100,'bytes':10**7},'seconds':60}
    def call(self,watch=lambda:None):return b.backup_existing(self.plan,watch)
    def test_backup_real_copy_restore_alltables(self):
        result,vectors=self.call();self.assertEqual(set(result),{'manifest','restore_root','backup_helper_ack','full_backup_restore_observed','mutation_authority','publication_acceptance','application_quiescence_authority'})
        self.assertFalse(result['publication_acceptance']);self.assertFalse(result['application_quiescence_authority'])
        manifest=json.loads(Path(result['manifest']['path']).read_bytes());self.assertEqual(manifest['databases']['config:database.sqlite']['tables']['BOOK']['rows'],2);self.assertTrue(vectors[0])
    def test_backup_projected_config_uses_exact_child_path_without_rewriting_original_runtime(self):
        self.plan.update(version=2,config_binding=dict(host='/configured/reader-state',child=str(self.config),signature9=list(b.a.nine(self.config.lstat()))))
        self.plan['runtime']['Mounts'][0]['Source']='/configured/reader-state'
        before=json.loads(json.dumps(self.plan['runtime']))
        result,_=self.call()
        self.assertTrue(result['full_backup_restore_observed'])
        self.assertEqual(self.plan['runtime'],before)

    def test_backup_named_volume_projection_preserves_original_runtime_and_restores_tables(self):
        mount=self.plan['runtime']['Mounts'][0]
        mount.update(Type='volume',Driver='local',Name='reader_config',RW=True,Source='/configured/reader-state')
        self.plan.update(version=2,config_binding=dict(host=mount['Source'],child=str(self.config),signature9=list(b.a.nine(self.config.lstat()))))
        before=json.loads(json.dumps(self.plan['runtime']))
        result,_=self.call()
        self.assertTrue(result['full_backup_restore_observed'])
        self.assertEqual(self.plan['runtime'],before)
        manifest=json.loads(Path(result['manifest']['path']).read_bytes())
        self.assertEqual(manifest['databases']['config:database.sqlite']['tables']['BOOK']['rows'],2)

    def test_backup_foreign_volume_driver_refuses_before_copy(self):
        self.plan['runtime']['Mounts'][0].update(Type='volume',Driver='foreign',Name='reader_config',RW=True)
        with self.assertRaisesRegex(b.a.Held,'archive-backup-config-root'):self.call()
        self.assertFalse((self.work/'reader-backup').exists())

    def test_backup_projected_config_refuses_wrong_host_or_original_identity_before_backup(self):
        for fault in ('host','signature9'):
            value=dict(host=self.plan['runtime']['Mounts'][0]['Source'],child=str(self.config),signature9=list(b.a.nine(self.config.lstat())))
            if fault=='host':value['host']='/foreign'
            else:value['signature9'][1]+=1
            self.plan.update(version=2,config_binding=value)
            with self.subTest(fault=fault),self.assertRaises(b.a.Held):self.call()
            self.assertFalse((self.work/'reader-backup').exists())

    def test_backup_first_watch_original_mode_roundtrip(self):
        fired=[];path=self.config/'database.sqlite'
        def watch():
            if not fired:fired.append(True);path.chmod(0o640);path.chmod(0o644)
        with self.assertRaises(b.a.Held):self.call(watch)
        self.assertTrue(fired);self.assertFalse((self.work/'reader-backup').exists())
    def test_backup_output_replay_refuses(self):
        self.call()
        with self.assertRaises(b.a.Held):self.call()
    def test_backup_returned_completion_cannot_refresh_copy_incarnation(self):
        real=b.load;fired=[]
        def load(name,originals):
            module=real(name,originals)
            if name=='comic_reader_backup.py':
                run=module.run
                def after(args):
                    result=run(args);path=self.work/'reader-backup/restore/config/database.sqlite';path.chmod(0o640);path.chmod(0o644);fired.append(True);return result
                module.run=after
            return module
        with patch.object(b,'load',side_effect=load),self.assertRaises(b.a.Held):self.call()
        self.assertTrue(fired)
    def test_backup_running_reader_refuses(self):
        self.plan['runtime']['State']['Running']=True
        with self.assertRaises(b.a.Held):self.call()
    def test_backup_no_negative_plan_roles(self):
        self.plan['reviewed_selection']={}
        with self.assertRaises(b.a.Held):self.call()
    def test_backup_last_watch_original_SQL_change(self):
        count=[]
        def watch():
            count.append(True)
            if len(count)==3:(self.config/'database.sqlite').chmod(0o640)
        with self.assertRaises(b.a.Held):self.call(watch)
        self.assertEqual(len(count),3)
    def test_backup_last_close_cannot_acknowledge_mode_change(self):
        original=b.p.close;fired=[]
        def callback(vector):
            original(vector)
            if (self.work/'reader-backup/manifest.json').exists():
                fired.append(True);(self.config/'database.sqlite').chmod(0o640)
        with patch.object(b.p,'close',side_effect=callback),self.assertRaises(b.a.Held):self.call()
        self.assertTrue(fired)

    def main_backup(self, change=None):
        import comic_reader_lifecycle_parent as parent
        self.work=self.root/'backup';self.work.mkdir(mode=0o700);self.plan['operation']=str(self.work)
        own=self.root/'comic_archive_backup_action.py';own.write_bytes(Path(b.__file__).read_bytes());own.chmod(0o600)
        helper=self.root/'comic_archive_repair_action.py';helper.write_bytes(Path(b.a.__file__).read_bytes());helper.chmod(0o600)
        source_sha=hashlib.sha256(own.read_bytes()).hexdigest();inp=self.root/'backup-input.json'
        self.plan['command_template']=parent.command_template({'path':str(own),'sha256':source_sha},'backup',str(inp))
        if change:change(self.plan)
        inp.write_bytes(b.a.encoded(self.plan));inp.chmod(0o600);input_sha=hashlib.sha256(inp.read_bytes()).hexdigest()
        command=parent.actual_command(self.plan['command_template'],input_sha)
        self.challenges=[];frames=[];write=os.write
        def challenge(nonce,sha,parent_sha):
            self.challenges.append((nonce,sha,parent_sha))
            return dict(reader=self.plan['runtime'],child_source_sha256=source_sha,child_image=self.plan['selected_image'])
        def channel(*,seconds):
            self.assertEqual(seconds,self.plan['seconds'])
            return types.SimpleNamespace(challenge=challenge)
        modules={'publication_reader_lifecycle':types.SimpleNamespace(ParentPipe=channel)}
        def output(fd,raw):
            if fd==sys.stdout.fileno():frames.append(raw);return len(raw)
            return write(fd,raw)
        with patch.object(b,'__file__',str(own)),patch.object(b.a,'__file__',str(helper)),patch.object(b,'PARENT_SOURCE_SHA',self.plan['parent_sha256']),patch.object(b.a,'sdk',return_value=(modules,{},{})),patch.dict(os.environ,TMPDIR=str(self.work)),patch.object(sys,'argv',[str(own),*command[4:]]),patch.object(sys,'orig_argv',command),patch.object(os,'write',output):
            b.main()
        return b.a.decode(frames[0])
    def test_backup_actual_main_parent_command_copy_restore_and_ack(self):
        frame=self.main_backup();self.assertEqual(frame['type'],'ACK');self.assertGreaterEqual(len(self.challenges),3)
        report=b.a.decode(Path(frame['ack']['report']['path']).read_bytes());self.assertTrue(report['full_backup_restore_observed']);self.assertFalse(frame['ack']['reader_resume_authority'])
        manifest=b.a.decode(Path(report['manifest']['path']).read_bytes());self.assertEqual(manifest['databases']['config:database.sqlite']['tables']['BOOK']['rows'],2)
    def test_backup_main_wrong_repair_entry_refused_before_copy(self):
        def wrong(plan):plan['command_template'][3]=str(self.root/'comic_archive_repair_action.py')
        with self.assertRaisesRegex(b.a.Held,'action-command-prefix'):self.main_backup(wrong)
        self.assertFalse((self.work/'reader-backup').exists())
    def test_backup_main_wrong_purpose_refused_before_copy(self):
        with self.assertRaisesRegex(b.a.Held,'action-backup-purpose'):self.main_backup(lambda plan:plan.update(action='archive-one'))
        self.assertFalse((self.work/'reader-backup').exists())

    def primitive_variants(self):
        paths=(Path(__file__).with_name('comic_reader_backup_primitives.py'),Path(__file__).parent.parent/'standalone_launch_host/comic_reader_backup_primitives.py')
        for index,path in enumerate(paths):
            spec=importlib.util.spec_from_file_location('durability_primitive_'+str(index),path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            yield index,module
    def durability_source(self,index):
        root=self.root/('durability-'+str(index));root.mkdir();source=root/'source';source.mkdir();(source/'nested').mkdir()
        (source/'one').write_bytes(b'payload\0bytes');(source/'nested'/'empty.lock').write_bytes(b'');(source/'link').symlink_to('one')
        (source/'one').chmod(0o640);os.setxattr(source/'one','user.test',b'preserved')
        return source,root/'copy'
    def test_backup_copy_durability_order_and_exact_payload_metadata(self):
        for index,h in self.primitive_variants():
            with self.subTest(variant=index):
                source,target=self.durability_source(index);rows,_=h.inventory(source,'tree');events=[];attrs=h.apply_attrs;sync=h.sync
                def apply(path,value):
                    events.append(('attrs',Path(path)));return attrs(path,value)
                def durable(path):
                    events.append(('sync',Path(path)));return sync(path)
                with patch.object(h,'apply_attrs',apply),patch.object(h,'sync',durable):h.copy_scope(source,target,rows)
                copied,_=h.inventory(target,'tree');self.assertEqual(h.logical(rows),h.logical(copied))
                self.assertEqual((target/'one').read_bytes(),b'payload\0bytes');self.assertEqual(os.readlink(target/'link'),'one')
                attr_events=[i for i,v in enumerate(events)if v[0]=='attrs'];sync_events=[i for i,v in enumerate(events)if v[0]=='sync'];self.assertLess(max(attr_events),min(sync_events))
                paths=[p for kind,p in events if kind=='sync'];expected=[target if row['path']=='.'else target/row['path']for row in sorted(rows,key=lambda row:len(Path(row['path']).parts),reverse=True)if row['kind']!='symlink']+[target.parent]
                self.assertEqual(paths,expected);self.assertEqual(len(paths),len(set(paths)))
    def test_backup_copy_no_early_file_fsync(self):
        for index,h in self.primitive_variants():
            source,target=self.durability_source(index);rows,_=h.inventory(source,'tree');seen=[]
            with patch.object(h,'sync',lambda path:seen.append(Path(path))),patch.object(h.os,'fsync',side_effect=AssertionError('early durability barrier')):h.copy_scope(source,target,rows)
            self.assertTrue(seen);self.assertEqual(seen[-1],target.parent)
    def durability_failure(self,kind):
        for index,h in self.primitive_variants():
            source,target=self.durability_source(index);rows,_=h.inventory(source,'tree');events=[];real=h.sync;error=OSError('durability-'+kind)
            def fail(path):
                path=Path(path);events.append(path)
                chosen=(kind=='file'and path.is_file())or(kind=='directory'and path==target/'nested')or(kind=='parent'and path==target.parent)
                if chosen:raise error
                return real(path)
            with patch.object(h,'sync',fail),self.assertRaises(OSError)as caught:h.copy_scope(source,target,rows)
            self.assertIs(caught.exception,error)
            if kind!='parent':self.assertNotIn(target.parent,events)
            self.assertEqual((source/'one').read_bytes(),b'payload\0bytes')
    def test_backup_copy_file_barrier_failure_refuses(self):self.durability_failure('file')
    def test_backup_copy_directory_barrier_failure_refuses(self):self.durability_failure('directory')
    def test_backup_copy_parent_barrier_failure_refuses(self):self.durability_failure('parent')

if __name__=='__main__':
    names=[name for name in Controls.__dict__ if name.startswith('test_backup_')]
    result=unittest.TextTestRunner().run(unittest.TestSuite(Controls(name) for name in names))
    raise SystemExit(not result.wasSuccessful() or bool(result.skipped) or result.testsRun!=20)
