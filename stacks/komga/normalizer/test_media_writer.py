"""Real process contention, crash fences and native writer admission."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from media_writer import Writer, Busy


class WriterTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'state';self.owner=Writer(self.root,create=True)

    def child(self,source):
        return subprocess.Popen([sys.executable,'-c',source,str(self.root)],
            env=dict(os.environ,PYTHONPATH=str(Path(__file__).parent)),stdout=subprocess.PIPE,text=True)

    def test_two_processes_exclude_each_other_and_release_after_kill(self):
        child=self.child("from media_writer import Writer;import sys,time\nwith Writer(sys.argv[1]).hold():\n print('locked',flush=True);time.sleep(60)")
        try:
            self.assertEqual(child.stdout.readline().strip(),'locked')
            with self.assertRaises(Busy):
                with self.owner.hold(timeout=.05):pass
        finally:child.kill();child.wait(5);child.stdout.close()
        with self.owner.hold(timeout=.2):pass

    def test_dead_worker_fence_survives_and_only_recovery_clears_it(self):
        child=self.child("from media_writer import Writer;import sys,os\nw=Writer(sys.argv[1])\nwith w.hold(allow_pending=True):\n w.mark_pending();os._exit(17)")
        self.assertEqual(child.wait(5),17);child.stdout.close()
        with self.assertRaises(Busy):
            with self.owner.hold(timeout=0):pass
        with self.assertRaises(ValueError):self.owner.clear_pending()
        with self.owner.hold(allow_pending=True):self.owner.clear_pending()
        with self.owner.hold(timeout=0):pass

    def test_dead_tagger_fence_blocks_normalizer_recovery_authority(self):
        child=self.child("from media_writer import Writer;import sys,os\nw=Writer(sys.argv[1])\nwith w.hold(allow_tagger_pending=True):\n w.mark_tagger_pending();os._exit(17)")
        self.assertEqual(child.wait(5),17);child.stdout.close()
        with self.assertRaises(Busy):
            with self.owner.hold(allow_pending=True,timeout=0):pass
        with self.assertRaises(ValueError):self.owner.clear_tagger_pending()
        with self.owner.hold(allow_tagger_pending=True):self.owner.clear_tagger_pending()
        with self.owner.hold(allow_pending=True,timeout=0):pass
        with self.owner.hold():
            with self.assertRaises(ValueError):
                with self.owner.hold(allow_tagger_pending=True):pass

    def test_threads_and_nested_instances_keep_outer_ownership(self):
        other=Writer(self.root);seen=[]
        def attempt():
            try:
                with other.hold(timeout=.05):seen.append('entered')
            except Busy:seen.append('busy')
        with self.owner.hold():
            with other.hold():pass
            thread=threading.Thread(target=attempt);thread.start();thread.join(1)
            self.assertEqual(seen,['busy'])
        with other.hold():pass

    def test_bad_files_and_replaced_lock_fail_closed(self):
        for mode in ('symlink','hardlink','wrong-mode','wrong-version'):
            with self.subTest(mode=mode):
                self.owner.lock.unlink()
                if mode=='symlink':self.owner.lock.symlink_to('/dev/null')
                else:
                    self.owner.create_file(self.owner.lock)
                    if mode=='hardlink':os.link(self.owner.lock,self.root/'alias')
                    elif mode=='wrong-mode':self.owner.lock.chmod(0o644)
                    else:self.owner.lock.write_bytes(b'x'*len(self.owner.lock.read_bytes()))
                with self.assertRaises((OSError,ValueError)):
                    with self.owner.hold(timeout=0):pass
                (self.root/'alias').unlink(missing_ok=True)
        self.owner.lock.unlink();self.owner.create_file(self.owner.lock)
        self.owner.pending.write_text('corrupt');self.owner.pending.chmod(0o600)
        with self.assertRaises(ValueError):
            with self.owner.hold(timeout=0):pass

    def test_missing_lock_is_never_recreated_while_old_inode_is_owned(self):
        child=self.child("from media_writer import Writer;import sys,time\nwith Writer(sys.argv[1]).hold():\n print('locked',flush=True);time.sleep(60)")
        try:
            self.assertEqual(child.stdout.readline().strip(),'locked')
            self.owner.lock.unlink()
            with self.assertRaises(FileNotFoundError):Writer(self.root,create=True)
            self.assertFalse(self.owner.lock.exists())
        finally:child.kill();child.wait(5);child.stdout.close()

    def test_missing_peer_root_never_created(self):
        missing=Path(self.temp.name)/'missing'
        with self.assertRaises(FileNotFoundError):Writer(missing)
        self.assertFalse(missing.exists())


if __name__=='__main__':unittest.main()
