"""Real local FD/link/unlink fixtures; NFS/export detection explicitly doubled.

No Docker, live library, real NFS or active-parent custody acceptance.
"""
import errno
import hashlib
import importlib.util
import inspect
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location('hardlink_probe', ROOT/'comic_negative_nfs_hardlink_probe.py')
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)


class Controls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name); self.base.chmod(0o700)
        self.root = self.base/'fixture'; self.root.mkdir(mode=0o700)
        self.src = self.root/'source'; self.src.mkdir(mode=0o700)
        self.dst = self.root/'target'; self.dst.mkdir(mode=0o700)
        self.protected = self.base/'protected'; self.protected.mkdir(mode=0o700)
        self.mount = dict(source='explicit-fake-export:/unit',target='/unit',fstype='nfs4',fsroot='/',options='rw',**{'maj:min':'0:1'})
        self.plan = dict(version=1,kind='reviewed-disposable-hardlink-nfs-canary',nonce='a'*64,
                         root=str(self.root),root9=p.nine(self.root.lstat()),source_parent9=p.nine(self.src.lstat()),
                         target_parent9=p.nine(self.dst.lstat()),device=self.root.stat().st_dev,mount=self.mount,
                         forbidden_roots=[str(self.protected)],seconds=120)
        self.input = self.base/'input.json'
        self.refresh()
        source = ROOT/'comic_negative_nfs_hardlink_probe.py'
        self.source = dict(path=str(source),signature9=p.nine(source.lstat()),sha256=hashlib.sha256(source.read_bytes()).hexdigest())

    def refresh(self):
        self.input.write_bytes(p.encode(self.plan)); self.input.chmod(0o600)
        self.ref = dict(path=str(self.input),signature9=p.nine(self.input.lstat()),sha256=hashlib.sha256(self.input.read_bytes()).hexdigest())

    def run_probe(self):
        with patch.object(p,'mount',return_value=self.mount),patch.object(p,'nfs_magic',return_value=0x6969):
            return p.run(self.ref,self.source)

    def test_real_link_retire_restore_unstage_and_foreign_collision(self):
        observation=self.run_probe();value=observation.binding
        self.assertEqual([(v['action'],v['nlink']) for v in value['transitions']],
                         [('stage',2),('collision',2),('retire',1),('restore',2),('unstage',1)])
        self.assertEqual(value['collision_errno'],errno.EEXIST)
        self.assertEqual((self.src/'source.bin').read_bytes(),b'owned NFS hardlink canary\x00')
        self.assertEqual((self.dst/'foreign.bin').read_bytes(),b'foreign collision destination\x02')
        self.assertEqual((self.src/'source.bin').stat().st_nlink,1)
        self.assertFalse((self.dst/'retained.bin').exists())
        for key in ('actual_library_platform_verified','native_grant','publication_authority','reader_resume_authority','active_parent_custody_verified'):
            self.assertIs(value[key],False)

    def test_no_repeat_existing_fixture(self):
        self.run_probe()
        with self.assertRaises(p.Held):self.run_probe()

    def test_nfs_detection_refuses_local_backend(self):
        with patch.object(p,'mount',return_value=self.mount),patch.object(p,'nfs_magic',return_value=0),self.assertRaises(p.Held):
            p.run(self.ref,self.source)
        self.assertFalse((self.src/'source.bin').exists())

    def test_wrong_export_refused_before_creation(self):
        with patch.object(p,'mount',side_effect=[self.mount,dict(self.mount,source='different:/export')]),self.assertRaises(p.Held):
            p.run(self.ref,self.source)
        self.assertFalse((self.src/'source.bin').exists())

    def test_wrong_original_parent_mode_held(self):
        self.src.chmod(0o750)
        with self.assertRaises(p.Held):self.run_probe()

    def test_last_mount_callback_ancestor_drift_held(self):
        fired=[]
        def mount(path):
            if not fired:self.base.chmod(0o750);fired.append(True)
            return self.mount
        with patch.object(p,'mount',side_effect=mount),patch.object(p,'nfs_magic',return_value=0x6969),self.assertRaises(p.Held):p.run(self.ref,self.source)
        self.assertTrue(fired);self.assertFalse((self.src/'source.bin').exists())

    def test_private_scope_overlap_held(self):
        self.plan['forbidden_roots']=[str(self.root)];self.refresh()
        with self.assertRaises(p.Held):self.run_probe()

    def test_late_encoding_source_change_before_link_holds(self):
        real=p.encode;fired=[];links=[];link=os.link
        def encode(value):
            raw=real(value)
            if isinstance(value,dict) and value.get('phase')=='stage':
                (self.src/'source.bin').chmod(0o640);fired.append(True)
            return raw
        def track(*args,**kwargs):links.append(args);return link(*args,**kwargs)
        with patch.object(p,'encode',side_effect=encode),patch.object(p.os,'link',side_effect=track),self.assertRaises(p.Held):self.run_probe()
        self.assertTrue(fired);self.assertEqual(links,[])

    def test_last_prelink_closure_callback_source_change_holds(self):
        real=p.raw_close;fired=[];links=[];link=os.link
        def close(*args):
            result=real(*args)
            if (self.root/'stage-intent.json').exists() and not fired:
                (self.src/'source.bin').chmod(0o640);fired.append(True)
            return result
        def track(*args,**kwargs):links.append(args);return link(*args,**kwargs)
        with patch.object(p,'raw_close',side_effect=close),patch.object(p.os,'link',side_effect=track),self.assertRaises(p.Held):self.run_probe()
        self.assertTrue(fired);self.assertEqual(links,[])

    def test_lost_link_fsync_ack_retains_two_names_without_replay(self):
        real=os.fsync;fired=[]
        def sync(fd):
            real(fd)
            if (self.dst/'retained.bin').exists() and not fired:fired.append(True);raise OSError('explicit fixture lost fsync ACK')
        with patch.object(p.os,'fsync',side_effect=sync),self.assertRaises(p.Held):self.run_probe()
        self.assertTrue(fired);self.assertEqual((self.src/'source.bin').stat().st_nlink,2)
        self.assertTrue((self.root/'stage-intent.json').exists())

    def test_collision_unknown_errno_held_without_retire(self):
        real=os.link
        def link(a,b,**kw):
            if a=='collision.bin':raise OSError(errno.EIO,'fixture error')
            return real(a,b,**kw)
        with patch.object(p.os,'link',side_effect=link),self.assertRaises(p.Held):self.run_probe()
        self.assertEqual((self.src/'source.bin').stat().st_nlink,2)
        self.assertEqual((self.dst/'foreign.bin').read_bytes(),b'foreign collision destination\x02')
        self.assertFalse((self.root/'retire-intent.json').exists())

    def test_foreign_extra_child_holds(self):
        (self.dst/'foreign-child').write_bytes(b'unchanged foreign')
        with self.assertRaises(p.Held):self.run_probe()
        self.assertEqual((self.dst/'foreign-child').read_bytes(),b'unchanged foreign')

    def test_wrong_source_pin_held(self):
        self.source['sha256']='0'*64
        with self.assertRaises(p.Held):self.run_probe()

    def test_samebytes_input_replacement_held(self):
        raw=self.input.read_bytes();self.input.unlink();self.input.write_bytes(raw);self.input.chmod(0o600)
        with self.assertRaises(p.Held):self.run_probe()

    def test_serialized_constructor_does_not_mint_observation(self):
        with self.assertRaises(p.Held):p.HardlinkCanaryObservation(object(),{},(),(),(),())

    def test_final_object_encoding_callback_changes_source_holds(self):
        real=p.encode;fired=[]
        def encode(value):
            result=real(value)
            if isinstance(value,tuple) and len(value)==6 and not fired:
                (self.src/'source.bin').chmod(0o640);fired.append(True)
            return result
        with patch.object(p,'encode',side_effect=encode),self.assertRaises(p.Held):self.run_probe()
        self.assertTrue(fired)

    def test_observation_last_helper_namespace_change_holds(self):
        observation=self.run_probe();real=p.raw_close;fired=[]
        def close(*args):
            result=real(*args)
            if not fired:(self.dst/'new-child').write_bytes(b'fixture');fired.append(True)
            return result
        with patch.object(p,'raw_close',side_effect=close),self.assertRaises(p.Held):observation.binding
        self.assertTrue(fired)

    def test_original_source_xattr_retained(self):
        real=os.fsync;seeded=[]
        def sync(fd):
            real(fd)
            if (self.src/'source.bin').exists() and not seeded:
                os.setxattr(self.src/'source.bin','user.comic_canary',b'original xattr');seeded.append(True)
        with patch.object(p.os,'fsync',side_effect=sync):observation=self.run_probe()
        self.assertTrue(seeded);self.assertEqual(os.getxattr(self.src/'source.bin','user.comic_canary'),b'original xattr')
        self.assertIn('user.comic_canary',observation.binding['source_xattrs'])

    def test_late_xattr_drift_holds_before_retire(self):
        real=p.encode;fired=[]
        def encode(value):
            raw=real(value)
            if isinstance(value,dict) and value.get('phase')=='retire':
                os.setxattr(self.src/'source.bin','user.foreign',b'changed');fired.append(True)
            return raw
        with patch.object(p,'encode',side_effect=encode),self.assertRaises(p.Held):self.run_probe()
        self.assertTrue(fired);self.assertEqual((self.src/'source.bin').stat().st_nlink,2)

    def test_restore_foreign_name_never_overwritten(self):
        real=p.encode;fired=[]
        def encode(value):
            raw=real(value)
            if isinstance(value,dict) and value.get('phase')=='restore':
                (self.src/'source.bin').write_bytes(b'foreign at restored name');fired.append(True)
            return raw
        with patch.object(p,'encode',side_effect=encode),self.assertRaises(p.Held):self.run_probe()
        self.assertTrue(fired);self.assertEqual((self.src/'source.bin').read_bytes(),b'foreign at restored name')
        self.assertTrue((self.dst/'retained.bin').exists())

    def test_retire_lost_fsync_ack_retains_original_inode(self):
        real=os.fsync;fired=[]
        def sync(fd):
            real(fd)
            if (self.root/'retire-intent.json').exists() and not (self.src/'source.bin').exists() and not fired:
                fired.append(True);raise OSError('fixture lost retire fsync ACK')
        with patch.object(p.os,'fsync',side_effect=sync),self.assertRaises(p.Held):self.run_probe()
        self.assertTrue(fired);self.assertEqual((self.dst/'retained.bin').read_bytes(),b'owned NFS hardlink canary\x00')
        self.assertFalse((self.src/'source.bin').exists())

    def test_last_return_helper_missing_name_reappearance_holds(self):
        real=p.raw_close;fired=[]
        def close(*args):
            result=real(*args)
            if (self.root/'result.json').exists() and not fired:
                (self.dst/'retained.bin').write_bytes(b'foreign after final helper');fired.append(True)
            return result
        with patch.object(p,'raw_close',side_effect=close),self.assertRaises(p.Held):self.run_probe()
        self.assertTrue(fired)

    def test_expired_deadline_refused(self):
        with patch.object(p.time,'monotonic',side_effect=[0]+[121]*30),self.assertRaises(p.Held):self.run_probe()
        self.assertFalse((self.dst/'retained.bin').exists())

    def transient_open(self, selected):
        (self.protected/'source').mkdir(mode=0o700);(self.protected/'target').mkdir(mode=0o700)
        real=os.open;fired=[]
        def changed(path,flags,*args,**kwargs):
            if Path(path)==selected and not fired:
                saved=self.base/'retained';self.root.rename(saved);self.root.symlink_to(self.protected,target_is_directory=True)
                try:fd=real(path,flags,*args,**kwargs)
                finally:self.root.unlink();saved.rename(self.root)
                fired.append(True);return fd
            return real(path,flags,*args,**kwargs)
        with patch.object(p.os,'open',side_effect=changed),self.assertRaises(p.Held):self.run_probe()
        self.assertEqual(fired,[True])
        self.assertEqual(list((self.protected/'source').iterdir()),[])
        self.assertEqual(list((self.protected/'target').iterdir()),[])
        self.assertEqual(list(self.src.iterdir()),[]);self.assertEqual(list(self.dst.iterdir()),[])

    def test_literal_transient_source_parent_FD_never_writes_protected(self):
        self.transient_open(self.src)

    def test_symmetric_transient_target_parent_FD_never_writes_protected(self):
        self.transient_open(self.dst)

    def test_literal_last_run_census_callback_holds(self):
        real=os.listdir;fired=[]
        def changed(path):
            values=real(path);caller=inspect.currentframe().f_back
            if Path(path)==self.root and caller.f_code.co_name=='run' and (self.root/'result.json').exists() and not fired:
                (self.root/'late-foreign').write_bytes(b'foreign');fired.append(True)
            return values
        with patch.object(p.os,'listdir',changed),self.assertRaises(p.Held):self.run_probe()
        self.assertEqual(fired,[True]);self.assertTrue((self.root/'late-foreign').exists())

    def test_literal_last_binding_census_callback_holds(self):
        observation=self.run_probe();real=os.listdir;fired=[]
        def changed(path):
            values=real(path);caller=inspect.currentframe().f_back
            if Path(path)==self.root and caller.f_code.co_name=='close' and not fired:
                (self.root/'late-foreign').write_bytes(b'foreign');fired.append(True)
            return values
        with patch.object(p.os,'listdir',changed),self.assertRaises(p.Held):observation.binding
        self.assertEqual(fired,[True]);self.assertTrue((self.root/'late-foreign').exists())

    def test_after_owned_root_create_callback_cannot_refresh_root9(self):
        real=p.read_at;fired=[]
        def read(fd,name,expected,maximum=p.MAX):
            result=real(fd,name,expected,maximum)
            if name=='result.json' and not fired:
                (self.root/'late-foreign').write_bytes(b'foreign');fired.append(True)
            return result
        with patch.object(p,'read_at',side_effect=read),self.assertRaises(p.Held):self.run_probe()
        self.assertEqual(fired,[True])

    def test_wrong_thread_held(self):
        observation=self.run_probe();held=[]
        def check():
            try:observation.close()
            except p.Held:held.append(True)
        t=threading.Thread(target=check);t.start();t.join();self.assertEqual(held,[True])


if __name__=='__main__':unittest.main()
