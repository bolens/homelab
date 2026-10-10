"""Genuine owning initialization/publication failure resource lifetimes."""
import gc
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import test_publication_retained_standalone as owning

s=owning.s


def live_fds():
    result={}
    for fd in os.listdir('/proc/self/fd'):
        try:result[int(fd)]=os.readlink('/proc/self/fd/'+fd)
        except FileNotFoundError:pass
    return result


class Resources(unittest.TestCase):
    def setUp(self):
        # Retire unrelated prior SQLite cycles before the exact FD baseline.
        # Keep automatic collection stable for the entire resource-fault fixture.
        enabled=gc.isenabled();gc.collect();gc.disable()
        self.addCleanup(gc.enable if enabled else gc.disable)
        self.case=owning.Standalone('test_standalone_positive_exact_noop_and_sole_workflow_record')
        self.case.setUp();self.addCleanup(self.case.doCleanups)

    def test_sources_failure_closes_original_unregistered_directory(self):
        with self.case.writer.hold():
            before=live_fds()
            with patch.object(s,'_sources',side_effect=ValueError('sources-before-registration')):
                with self.assertRaisesRegex(ValueError,'sources-before-registration'):self.case.init()
            self.assertEqual(live_fds(),before)

    def test_first_stamp_helper_failure_closes_immediately_registered_FD(self):
        with self.case.writer.hold():
            before=live_fds()
            with patch.object(s,'_fd9',side_effect=ValueError('first-stamp-helper')):
                with self.assertRaisesRegex(ValueError,'first-stamp-helper'):self.case.init()
            self.assertEqual(live_fds(),before)

    def test_second_directory_open_failure_closes_first_original(self):
        journal=self.case.c.root/s.NAME;journal.mkdir(mode=0o700)
        original=s._open_directory;calls=[]
        def fail(path,*args):
            calls.append(Path(path))
            if len(calls)==2:raise ValueError('second-directory-open')
            return original(path,*args)
        with self.case.writer.hold():
            before=live_fds()
            with patch.object(s,'_open_directory',fail):
                with self.assertRaisesRegex(ValueError,'second-directory-open'):self.case.init()
            self.assertEqual(len(calls),2);self.assertEqual(live_fds(),before)
            self.assertTrue(journal.is_dir())

    def test_post_session_journal_failure_closes_owned_FDs_keeps_markers(self):
        with self.case.writer.hold():
            before=live_fds();original=set(s._CORES)
            with patch.object(s,'_journal_output',side_effect=ValueError('journal-after-registration')):
                with self.assertRaisesRegex(ValueError,'journal-after-registration'):self.case.init()
            self.assertEqual(live_fds(),before);self.assertEqual(set(s._CORES),original)
            journal=self.case.c.root/s.NAME
            self.assertTrue(journal.is_dir());self.assertEqual(len(list(journal.iterdir())),1)
            self.assertTrue(next(journal.iterdir()).is_dir())

    def test_reused_same_number_foreign_FD_is_not_closed(self):
        foreign=self.case.case.root/'foreign-resource';foreign.write_bytes(b'foreign original bytes')
        reused=[]
        def replace(*args,**kwargs):
            fd=next(fd for fd,path in live_fds().items() if path==str(self.case.c.native_database.parent))
            donor=os.open(foreign,os.O_RDONLY);os.dup2(donor,fd);os.close(donor);reused.append(fd)
            raise ValueError('sources-replaced-FD')
        with self.case.writer.hold(),patch.object(s,'_sources',replace):
            with self.assertRaisesRegex(owning.o.Held,'resource-identity-unknown'):self.case.init()
        self.assertEqual(len(reused),1);fd=reused[0];self.addCleanup(os.close,fd)
        self.assertEqual(os.read(fd,100),b'foreign original bytes')

    def test_body_new_directory_failure_closes_only_new_FDs(self):
        original=s._open_directory;fired=[]
        def fail(path,*args):
            original(path,*args);fired.append(True)
            raise ValueError('new-carrier-after-open')
        with self.case.writer.hold():
            session=self.case.init();before=live_fds();registry=s._DIRS[session]
            with patch.object(s,'_open_directory',fail):
                with self.assertRaisesRegex(ValueError,'new-carrier-after-open'):self.case.channel.initialized(session)
            self.assertTrue(fired);self.assertEqual(live_fds(),before);self.assertIs(s._DIRS[session],registry)
            for _,fd,_ in registry:os.fstat(fd)
            self.assertTrue((self.case.c.root/s.CARRIER).is_dir())


if __name__=='__main__':unittest.main()
