"""Genuine owning initialization/publication failure resource lifetimes."""
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




class CacheStartupResources(unittest.TestCase):
    def test_copied_native_startup_initializes_original_shared_cache_lock(self):
        # A fresh process sees only the finite copied auth source directory.
        # Package alias/effective CONFIG are public fixture data; admission,
        # Store/Writer, original config bytes and lock inode are genuine.
        import subprocess
        import sys
        import tempfile
        program = r'''
import hashlib,importlib,json,os,sys,types
from pathlib import Path
source=Path(sys.argv[1]).resolve();root=Path(sys.argv[2]).resolve()
pkg=types.ModuleType('mylar');pkg.__path__=[str(source)];pkg.DATA_DIR=str(root)
sys.modules['mylar']=pkg
cache=root/'cache';cache.mkdir(mode=0o700)
pkg.CONFIG=types.SimpleNamespace(CACHE_DIR=str(cache),DDL_LOCATION=str(cache),DDL_CACHE_MAX_GIB=7,DDL_CACHE_MIN_FREE_GIB=2)
config=root/'config.ini';config.write_bytes(b'[DDL]\nddl_cache_max_gib=7\nddl_cache_min_free_gib=2\n');config.chmod(0o644)
raw=config.read_bytes();original=config.stat()
writers=importlib.import_module('mylar.native_writers')
guard=importlib.import_module('mylar.publication_guard')
Store=importlib.import_module('mylar.workflow_store').Store
Writer=importlib.import_module('mylar.media_writer').Writer
store=Store(root);writer=Writer(root/'media-writer',create=True)
state=guard.RegistryState(store.path,writer)
token=state.prepare_bootstrap(dict(manifest_sha256='a'*64,restore_sha256='b'*64,description='public copied auth startup fixture'),epoch='c'*64)
state.initialize(token,accepted_token=token)
lock=root/'cache-admission-v1.lock';assert not lock.exists()
assert 'mylar.cache_admission' not in sys.modules and 'mylar.cache_reservation' not in sys.modules
assert writers.initialize_publication()['state']=='ready'
with writers.operation(startup=True):writers.complete_startup()
assert writers.startup_status()['state']=='ready'
policy=importlib.import_module('mylar.cache_admission');shared=importlib.import_module('mylar.cache_reservation')
for module,name in ((policy,'cache_admission.py'),(shared,'cache_reservation.py')):
 assert Path(module.__file__).resolve()==source/name
assert lock.is_file() and lock.stat().st_mode & 0o777==0o600
stamp=policy.identity(lock.stat())
with writers.operation():packet=policy.policy_snapshot()
assert packet['maximum']==7*shared.GIB and packet['reserve']==2*shared.GIB
assert packet['config']['sha256']==hashlib.sha256(raw).hexdigest()
assert packet['config']['signature9']==list(policy.identity(original))
with writers.operation(startup=True):writers.complete_startup()
assert policy.identity(lock.stat())==stamp
assert config.read_bytes()==raw and policy.identity(config.stat())==policy.identity(original)
print(json.dumps(dict(genuine_startup=True,lazy_helpers=True,original_lock_reused=True,configured_policy=True,installed_acceptance=False)))
'''
        with tempfile.TemporaryDirectory(prefix='auth-cache-startup-') as temporary:
            result=subprocess.run([sys.executable,'-I','-B','-c',program,
                str(Path(__file__).resolve().parent),temporary],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('"genuine_startup": true',result.stdout)
        self.assertIn('"original_lock_reused": true',result.stdout)
        self.assertIn('"installed_acceptance": false',result.stdout)

if __name__=='__main__':unittest.main()
