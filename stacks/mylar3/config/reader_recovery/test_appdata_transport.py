"""Recovery transport preserves app bytes and never archives original media."""
import copy
from contextlib import closing
import fcntl
import io
import os
from pathlib import Path
import select
import resource
import sqlite3
import zipfile
import sys
import tarfile
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent/'standalone_launch_host'))
import comic_appdata_restic_primitives as transport
import comic_reader_backup_primitives as primitives


class AppDataTransport(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.scopes = []
        for role in ('native_config', 'worker_state', 'reader_config'):
            root = self.base / role
            root.mkdir()
            (root / 'settings.json').write_bytes(b'{"placeholder":true}')
            (root / 'empty').mkdir()
            if role != 'reader_config':
                held = root / ('cache/.mylar-pack-held' if role == 'native_config' else 'held')
                held.mkdir(parents=True)
                (held / 'original.cbz').write_bytes(b'PK\x03\x04ORIGINAL PAYLOAD')
                (held / 'page.png').write_bytes(b'\x89PNG\r\n\x1a\nORIGINAL PAGE')
            if role == 'worker_state':
                os.symlink('settings.json', root / '.env')
            rows, _ = primitives.inventory(root, 'tree')
            self.scopes.append(dict(role=role, root=str(root), records=rows))
        self.index = transport.appdata_make_index(self.scopes)
        self.custody = {}
        self.addCleanup(lambda:[transport.appdata_release_restore(value) for value in self.custody.values()])

    def test_custom_native_DATA_prior_payload_layouts_are_excluded(self):
        for prefix in ('', 'mylar/', 'custom/', 'nested/custom/'):
            for name in ('target-preserved.cbz','target-restored.cbr'):
                self.assertTrue(transport.appdata_payload('native_config',prefix+'retained-standalone-v1/'+('b'*64)+'/'+name,b'PK\x03\x04',deadline=time.monotonic()+10))
        with self.assertRaises(transport.Held):
            transport.appdata_payload('native_config','custom/retained-standalone-v1/not-a-token/target-preserved.cbz',b'PK\x03\x04',deadline=time.monotonic()+10)

    def archive(self, index=None):
        result = io.BytesIO()
        transport.appdata_write_archive(result, self.index if index is None else index,
                                deadline=time.monotonic() + 10)
        return result.getvalue()

    def restore(self, raw=None, destination=None):
        target = self.base / 'restored' if destination is None else destination
        result=transport.appdata_restore_archive(io.BytesIO(self.archive() if raw is None else raw),
                                  target, self.index, deadline=time.monotonic() + 10)
        self.custody[target]=result['custody']
        return target

    def rewrite(self, *, name=None, data=None, omit=None, extra=None, symlink=None):
        output = io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(self.archive())) as source:
            with tarfile.open(fileobj=output, mode='w') as target:
                for member in source:
                    if member.name == omit:
                        continue
                    raw = source.extractfile(member).read()
                    if member.name == name:
                        raw = data
                        member.size = len(raw)
                    if member.name == symlink:
                        member.type = tarfile.SYMTYPE
                        member.linkname = '/outside'
                        member.size = 0
                    target.addfile(member, io.BytesIO(raw) if member.isfile() else None)
                if extra:
                    member = tarfile.TarInfo(extra)
                    member.size = 1
                    target.addfile(member, io.BytesIO(b'x'))
        return output.getvalue()

    def test_roundtrip_excludes_payloads_and_preserves_empty_directories_and_app_link(self):
        raw = self.archive()
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            self.assertEqual(archive.getnames(), ['source-index.json'] + [
                role + '/settings.json' for role in ('native_config', 'worker_state', 'reader_config')])
        root = self.restore(raw)
        self.assertEqual(transport.appdata_verify_restored(root, self.index, deadline=time.monotonic() + 10, custody=self.custody[root]), {'app_files': 3, 'media_copies': 0})
        self.assertTrue((root / 'native_config/cache/.mylar-pack-held').is_dir())
        self.assertFalse((root / 'native_config/cache/.mylar-pack-held/original.cbz').exists())
        self.assertEqual(os.readlink(root / 'worker_state/.env'), 'settings.json')

    def test_metadata_artwork_and_native_app_archives_stay_in_app_scope(self):
        self.assertFalse(transport.appdata_payload('native_config', 'mylar/cache/cover.png', b'\x89PNG\r\n\x1a\n'))
        self.assertFalse(transport.appdata_payload('native_config', 'mylar/cache/artwork', b'\xff\xd8\xff'))
        with self.assertRaises(transport.Held):
            transport.appdata_payload('native_config', 'backups/config.zip', b'PK\x03\x04')
        self.assertFalse(transport.appdata_payload('reader_config', 'artwork.png', b'\x89PNG\r\n\x1a\n'))
        with self.assertRaises(transport.Held):
            transport.appdata_payload('reader_config', 'uploads/book.cbz', b'PK\x03\x04')
        self.assertTrue(transport.appdata_payload('native_config', 'cache/renamed.bin', b'PK\x03\x04'))
        self.assertTrue(transport.appdata_payload('worker_state', 'historical/original.bin', b'Rar!\x1a\x07'))

    def test_owning_native_payload_layouts_and_proven_diagnostics(self):
        layouts=('archive-repair-'+64*'a'+'/original.arc',
                 'modern-tagger-v2/staging/mylar_modern_'+32*'b'+'/source.cbz',
                 'modern-tagger-v2/staging/mylar_modern_'+32*'b'+'/.mylar-tag-'+32*'c'+'/displaced.cbz',
                 'media-writer/retained-repeats-v1/'+64*'d'+'/original.cbz',
                 'private-supplement-backups/'+32*'e'+'/original.cbz',
                 'retention/adopt-'+64*'f'+'/swap.arc')
        for name in layouts:
            with self.subTest(layout=name):self.assertTrue(transport.appdata_payload('native_config','mylar/'+name,b'synthetic held source'))
        db=self.base/'fixture.sqlite'
        with closing(sqlite3.connect(db))as connection:connection.execute('CREATE TABLE app(value TEXT)');connection.commit()
        package=self.base/'carepackage_fixture.zip'
        with zipfile.ZipFile(package,'w')as archive:
            archive.writestr('mylar.db',db.read_bytes());archive.writestr('clean_config.ini','[placeholder]\n');archive.writestr('MylarRunningEnvironment.txt','synthetic fixture\n');archive.writestr('mylar.log','synthetic log\n')
        self.assertFalse(transport.appdata_payload('native_config','mylar/logs/'+package.name,b'PK\x03\x04',path=package,original=transport.appdata_signature(package.lstat())))
        with zipfile.ZipFile(package,'a')as archive:archive.writestr('001.jpg',b'original book page')
        with self.assertRaises(transport.Held):transport.appdata_payload('native_config','mylar/logs/'+package.name,b'PK\x03\x04',path=package,original=transport.appdata_signature(package.lstat()))

    def test_prior_standalone_preservation_layout_excludes_only_owned_archives(self):
        folder='retained-standalone-v1/'+64*'b'
        for prefix in ('','mylar/'):
            for stem in ('target-preserved','target-restored'):
                for suffix in ('','.cbz','.cbr','.zip','.cb7','.tar','.unusual'):
                    self.assertTrue(transport.appdata_payload('native_config',prefix+folder+'/'+stem+suffix,b'PK\x03\x04'))
        self.assertFalse(transport.appdata_payload('native_config',folder+'/accepted.json',b'{"placeholder":true}'))
        for name in (folder+'/target-preserved-extra.cbz','old/'+folder+'/subdir/target-preserved.cbz',
                     'retained-standalone-v1/'+32*'b'+'/target-restored.cbz'):
            with self.assertRaises(transport.Held):transport.appdata_payload('native_config',name,b'PK\x03\x04')

    def test_missing_wrong_extra_and_link_members_refuse(self):
        cases = [self.rewrite(omit='reader_config/settings.json'),
                 self.rewrite(name='native_config/settings.json', data=b'wrong'),
                 self.rewrite(name='source-index.json', data=b'{}'),
                 self.rewrite(extra='../../escape'),
                 self.rewrite(extra='worker_state/held/original.cbz'),
                 self.rewrite(symlink='native_config/settings.json')]
        for index, raw in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(transport.Held):
                self.restore(raw, self.base / ('failed' + str(index)))
        self.assertFalse((self.base.parent / 'escape').exists())

    def test_independent_readback_rejects_callback_damage_and_unexpected_payload(self):
        root = self.restore()
        (root / 'reader_config/settings.json').write_bytes(b'damaged')
        with self.assertRaises(transport.Held):
            transport.appdata_verify_restored(root, self.index, deadline=time.monotonic() + 10, custody=self.custody[root])
        second = self.restore(destination=self.base / 'second')
        (second / 'worker_state/held/original.cbz').write_bytes(b'payload')
        with self.assertRaises(transport.Held):
            transport.appdata_verify_restored(second, self.index, deadline=time.monotonic() + 10, custody=self.custody[second])

    def test_live_originals_are_never_restore_destinations(self):
        with self.assertRaises(transport.Held):
            self.restore(destination=Path(self.scopes[0]['root']))
        root = self.restore()
        target = root / 'native_config/settings.json'
        target.unlink()
        os.link(Path(self.scopes[0]['root']) / 'settings.json', target)
        with self.assertRaises(transport.Held):
            transport.appdata_verify_restored(root, self.index, deadline=time.monotonic() + 10, custody=self.custody[root])

    def test_external_and_payload_symlink_targets_refuse(self):
        for name in ('../settings.json', '/outside', 'held/original.cbz'):
            scopes=copy.deepcopy(self.scopes)
            row=next(row for row in scopes[1]['records'] if row['kind']=='symlink')
            row['link']=name
            with self.subTest(target=name),self.assertRaises(transport.Held):
                transport.appdata_make_index(scopes)

    def test_changed_source_and_traversal_index_refuse_before_file_stream(self):
        index = transport.appdata_policy_value(self.index)
        index['scopes'][0]['records'][1]['path'] = '../outside'
        with self.assertRaises(transport.Held):
            self.archive(index)
        (Path(self.scopes[0]['root']) / 'settings.json').write_bytes(b'changed')
        with self.assertRaises(transport.Held):
            self.archive()

    def test_saved_policy_and_retained_parser_rows_cannot_reselect_app_or_media(self):
        saved=transport.appdata_policy_value(self.index)
        for scope in saved['scopes']:
            for row in scope['records']:
                if row['kind']=='file':row['media']=not row['media']
        with self.assertRaises(transport.Held):self.archive(saved)
        retained=[];loads=transport.json.loads
        def parser(raw,*args,**kwargs):
            value=loads(raw,*args,**kwargs);retained.append(value);return value
        with patch.object(transport.json,'loads',side_effect=parser):
            original=transport.appdata_make_index(self.scopes)
        for value in retained:
            if isinstance(value,list):
                for scope in value:
                    for row in scope.get('records',[]):
                        if row['kind']=='file':row['media']=not row['media']
        root=self.restore(self.archive(original))
        self.assertEqual(transport.appdata_verify_restored(root,self.index,deadline=time.monotonic()+10,custody=self.custody[root])['app_files'],3)

    def test_identical_file_replacement_during_metadata_is_not_a_new_original(self):
        actual=os.fchown;changed=[]
        def replace(fd,uid,gid):
            path=Path(os.readlink('/proc/self/fd/'+str(fd)))
            if path.name=='settings.json'and not changed:
                raw=path.read_bytes();path.unlink();path.write_bytes(raw);changed.append(True)
            return actual(fd,uid,gid)
        with patch.object(os,'fchown',side_effect=replace),self.assertRaises(transport.Held):self.restore()
        self.assertTrue(changed)

    def test_replaced_directory_cannot_redirect_creation_or_metadata(self):
        outside=self.base/'outside';outside.mkdir();changed=[];actual=os.fchown
        def replace(fd,uid,gid):
            if not changed:
                path=self.base/'restored/worker_state';path.rename(self.base/'displaced');os.symlink(outside,path);changed.append(True)
            return actual(fd,uid,gid)
        with patch.object(os,'fchown',side_effect=replace),self.assertRaises(transport.Held):self.restore()
        self.assertTrue(changed);self.assertEqual(list(outside.iterdir()),[])

    def test_codec_alias_mutation_is_refused_before_any_archive_bytes(self):
        encoder=transport.json.dumps;output=io.BytesIO()
        def changed(value,*args,**kwargs):
            if isinstance(value,dict)and value.get('kind')=='publication-appdata-transport-v1':
                for scope in value['scopes']:
                    for row in scope['records']:
                        if row['kind']=='file':row['media']=not row['media']
            return encoder(value,*args,**kwargs)
        with patch.object(transport.json,'dumps',side_effect=changed),self.assertRaises(transport.Held):
            transport.appdata_write_archive(output,self.index,deadline=time.monotonic()+10)
        self.assertEqual(output.getvalue(),b'')

    def test_directory_replacement_during_file_birth_does_not_write_outside(self):
        outside=self.base/'outside';outside.mkdir();changed=[];opening=os.open
        def replace(path,flags,*args,**kwargs):
            if flags&os.O_CREAT and path=='settings.json'and not changed:
                parent=Path(os.readlink('/proc/self/fd/'+str(kwargs['dir_fd'])))
                if parent.name=='native_config':
                    target=self.base/'restored/worker_state';target.rename(self.base/'displaced-early');os.symlink(outside,target);changed.append(True)
            return opening(path,flags,*args,**kwargs)
        with patch.object(os,'open',side_effect=replace),self.assertRaises(transport.Held):self.restore()
        self.assertTrue(changed);self.assertEqual(list(outside.iterdir()),[])

    def test_new_directory_birth_cannot_be_replaced_before_open(self):
        opening=os.open;changed=[];held=[]
        def replaced(path,flags,*args,**kwargs):
            if path=='native_config'and flags&os.O_DIRECTORY and kwargs.get('dir_fd')is not None and not changed:
                parent=kwargs['dir_fd'];held.append(opening(path,os.O_PATH|os.O_NOFOLLOW,dir_fd=parent))
                os.rmdir(path,dir_fd=parent);os.mkdir(path,0o700,dir_fd=parent);changed.append(True)
            return opening(path,flags,*args,**kwargs)
        try:
            with patch.object(os,'open',side_effect=replaced),self.assertRaises(transport.Held):self.restore()
        finally:
            for fd in held:os.close(fd)
        self.assertTrue(changed)

    def test_false_encoder_bytes_are_refused_before_streaming(self):
        encoder=transport.json.dumps;output=io.BytesIO()
        def changed(value,*args,**kwargs):
            if isinstance(value,dict)and value.get('kind')=='publication-appdata-transport-v1':return '{}'
            return encoder(value,*args,**kwargs)
        with patch.object(transport.json,'dumps',side_effect=changed),self.assertRaises(transport.Held):
            transport.appdata_write_archive(output,self.index,deadline=time.monotonic()+10)
        self.assertEqual(output.getvalue(),b'')

    def test_opaque_policy_reaches_actual_adapter_capacity_gate(self):
        node=transport.appdata_node5(self.base.lstat());binding=dict(mounts={'/cache':str(self.base),'/repository':str(self.base)},mount_nodes={'/cache':node,'/repository':node})
        with patch.object(transport,'appdata_restic_profile',return_value=binding),patch.object(transport.shutil,'disk_usage',return_value=SimpleNamespace(free=0)):
            with self.assertRaisesRegex(transport.Held,'appdata-capacity'):
                transport.appdata_restic_backup(self.index,self.base/'actual-adapter',deadline=time.monotonic()+10)

    def test_diagnostics_stop_on_original_deadline(self):
        package=self.base/'carepackage_expiring.zip'
        with zipfile.ZipFile(package,'w')as archive:
            archive.writestr('mylar.db',b'SQLite format 3\0'+b'x'*1024)
            archive.writestr('clean_config.ini','[placeholder]\n');archive.writestr('MylarRunningEnvironment.txt','fixture\n')
        frame=transport.appdata_signature(package.lstat())
        with self.assertRaises(transport.Held):transport.appdata_carepackage(package,frame,deadline=time.monotonic()-1)
        checks=[];real=transport.check_deadline
        def expires(deadline):
            checks.append(True)
            if len(checks)>3:raise transport.Held('original-deadline')
            real(deadline)
        with patch.object(transport,'check_deadline',side_effect=expires),self.assertRaisesRegex(transport.Held,'original-deadline'):
            transport.appdata_carepackage(package,frame,deadline=time.monotonic()+10)
        self.assertGreater(len(checks),3)

    def test_poll_accepts_high_descriptor_and_enforces_deadline(self):
        limits=resource.getrlimit(resource.RLIMIT_NOFILE)
        if limits[0]<=1100:resource.setrlimit(resource.RLIMIT_NOFILE,(1101,limits[1]))
        read_fd, write_fd = os.pipe()
        high_fd = fcntl.fcntl(write_fd, fcntl.F_DUPFD_CLOEXEC, 1100)
        try:
            transport.appdata_wait_ready(high_fd, select.POLLOUT, time.monotonic() + 1)
            os.write(high_fd, b'x')
            self.assertEqual(os.read(read_fd, 1), b'x')
            with self.assertRaises(transport.Held):
                transport.appdata_wait_ready(read_fd, select.POLLIN, time.monotonic() - 1)
        finally:
            os.close(read_fd)
            os.close(write_fd)
            os.close(high_fd)
            resource.setrlimit(resource.RLIMIT_NOFILE,limits)


if __name__ == '__main__':
    unittest.main()
