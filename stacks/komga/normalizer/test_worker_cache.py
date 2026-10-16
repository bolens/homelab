"""Focused private filesystem fixtures; no API, Docker, or live configuration."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
import zipfile
from unittest.mock import patch

import cache_reservation as core
import worker_cache as worker
import pack_recovery as packs


class WorkerCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='worker-cache-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / 'data'; self.data.mkdir(mode=0o700)
        self.cache = self.data / 'cache'; self.cache.mkdir(mode=0o700)
        self.state = self.root / 'state'; self.state.mkdir(mode=0o700)
        self.lock = self.data / 'cache-admission-v1.lock'; self.lock.touch(mode=0o600)
        self.config = self.data / 'config.ini'; self.config.write_text('[DDL]\nddl_cache_max_gib=20\n')
        self.owner = types.SimpleNamespace(config=self.data)
        self.m = types.SimpleNamespace(worker=object(), settings={
            'mylar_ddl_cache': '/native/cache', 'ddl_cache': str(self.cache)})
        self.packet = {'version': 1, 'kind': 'effective-ddl-cache-policy-v1',
            'data': {'path': '/native', 'identity5': list(core.directory_identity(self.data.stat()))},
            'roots': [{'path': '/native/cache', 'identity5': list(core.directory_identity(self.cache.stat()))}],
            'ddl': {'path': '/native/cache', 'identity5': list(core.directory_identity(self.cache.stat()))},
            'lock': {'path': '/native/cache-admission-v1.lock', 'signature9': list(core.identity(self.lock.stat()))},
            'config': {'path': '/native/config.ini', 'signature9': list(core.identity(self.config.stat())),
                       'sha256': hashlib.sha256(self.config.read_bytes()).hexdigest()},
            'maximum': 1024**3, 'reserve': 1}
        maintenance = types.ModuleType('maintenance')
        maintenance.native_work = lambda m, command: {'cache_policy': self.packet}
        guard = types.ModuleType('publication_guard')
        guard.current = lambda w: self.owner
        self.patcher = patch.dict(sys.modules, maintenance=maintenance, publication_guard=guard)
        self.patcher.start(); self.addCleanup(self.patcher.stop)

    def policy(self):
        return worker.Policy(self.m)

    def test_exact_packet_and_originals(self):
        p = self.policy(); self.assertEqual(p.roots, (self.cache,)); p.check()

    def test_no_policy_defaults(self):
        for value in (None, {}, {'version': 1}):
            self.packet = value
            with self.assertRaises(core.Held): self.policy()

    def test_limits_strict_integer_and_positive(self):
        for value in (True, 0, -1, '20', 4097 * core.GIB):
            self.packet['maximum'] = value
            with self.assertRaises(core.Held): self.policy()

    def test_changed_config_after_snapshot_refused(self):
        p = self.policy(); self.config.write_text('changed')
        with self.assertRaises(core.Held): p.check()

    def test_replaced_lock_refused(self):
        p = self.policy(); self.lock.unlink(); self.lock.touch(mode=0o600)
        with self.assertRaises(core.Held): p.check()

    def test_missing_lock_never_created(self):
        self.lock.unlink()
        with self.assertRaises((core.Held, OSError)): self.policy()
        self.assertFalse(self.lock.exists())

    def test_shadowed_mapping_refused(self):
        alternate = self.root / 'alternate'; alternate.mkdir()
        self.m.settings['ddl_cache'] = str(alternate)
        with self.assertRaises(core.Held): self.policy()

    def test_unmapped_root_refused(self):
        self.packet['roots'][0]['path'] = '/unmapped'
        with self.assertRaises(core.Held): self.policy()

    def test_independent_rejects_cache(self):
        p = self.policy()
        self.assertEqual(p.independent(self.state), self.state)
        with self.assertRaises(core.Held): p.independent(self.cache)

    def test_finalized_copy_and_no_overwrite(self):
        p = self.policy(); source = self.state / 'issue.cbz'; source.write_bytes(b'a' * (1024**2 + 7))
        before = core.identity(source.stat()); stage = self.cache / '.mylar-pack-fixture'
        output = stage / source.name
        worker.publish(p, source, stage, output)
        self.assertEqual(output.read_bytes(), source.read_bytes())
        self.assertEqual(core.identity(source.stat()), before)
        with self.assertRaises(core.Held): worker.publish(p, source, stage, output)
        self.assertEqual(output.read_bytes(), source.read_bytes())
        self.assertFalse(any(stage.glob('.partial-*')))

    def test_budget_refuses_new_but_allows_existing_only(self):
        self.packet['maximum'] = 1
        p = self.policy()
        with p.allocation(self.cache, 0, nodes=0): pass
        source = self.state / 'issue.cbz'; source.write_bytes(b'abc')
        stage = self.cache / '.mylar-pack-small'
        with self.assertRaises(core.Held): worker.publish(p, source, stage, stage / source.name)
        self.assertFalse(stage.exists())

    def test_chunk_policy_recheck_retains_partial(self):
        p = self.policy(); original = p.check; count = [0]
        def check():
            original(); count[0] += 1
            if count[0] >= 4: raise core.Held('fixture policy changed')
        p.check = check
        source = self.state / 'issue.cbz'; source.write_bytes(b'a' * (1024**2 + 7))
        stage = self.cache / '.mylar-pack-change'
        with self.assertRaises(core.Held): worker.publish(p, source, stage, stage / source.name)
        self.assertTrue(source.exists())
        self.assertFalse((stage / source.name).exists())
        self.assertTrue(list(stage.glob('.partial-*')))

    def pack_fixture(self):
        source = self.state / 'Issue 1 (2020).cbz'
        with zipfile.ZipFile(source, 'w') as archive: archive.writestr('001.jpg', b'page')
        member = {'source': str(source), 'id': 'a' * 64,
                  'identity': packs.identity(source), 'sha256': packs.digest(source)}
        self.m.info = lambda p: {'page_count': 1, 'pages': [hashlib.sha256(zipfile.ZipFile(p).read('001.jpg')).hexdigest()], 'other_files': []}
        value = packs.Packs.__new__(packs.Packs)
        value.m = self.m; value.worker = self.m.worker; value.cache = self.cache
        return value, member, source

    def test_pack_fresh_exact_stage_then_full_cache_reuse(self):
        value, member, source = self.pack_fixture()
        before = source.read_bytes()
        output, _ = value.prepared(member, self.state)
        self.assertEqual(output.read_bytes(), before)
        self.assertEqual(source.read_bytes(), before)
        self.assertTrue(list(self.state.glob('pack-conversion-*')))
        self.packet['maximum'] = 1
        reused, _ = value.prepared(member, self.state)
        self.assertEqual(reused, output)
        self.assertEqual(output.read_bytes(), before)

    def test_pack_budget_refuses_after_independent_conversion(self):
        value, member, source = self.pack_fixture()
        with patch.object(worker,'publish',side_effect=core.Held('capacity changed after conversion')), self.assertRaises(core.Held): value.prepared(member, self.state)
        self.assertFalse(list(self.cache.glob('.mylar-pack-*')))
        self.assertTrue(source.exists())
        self.assertTrue(list(self.state.glob('pack-conversion-*/*.cbz')))

    def test_pack_orphan_partial_is_preserved(self):
        value, member, source = self.pack_fixture()
        stage = self.cache / ('.mylar-pack-' + member['id']); stage.mkdir(mode=0o700)
        partial = stage / '.partial-previous'; partial.write_bytes(b'preserved')
        output, _ = value.prepared(member, self.state)
        self.assertEqual(partial.read_bytes(), b'preserved')
        self.assertEqual(output.read_bytes(), source.read_bytes())

    def test_converter_output_is_finalized_outside_cache(self):
        value, member, source = self.pack_fixture()
        renamed = source.with_suffix('.cbr'); source.rename(renamed)
        member.update(source=str(renamed), identity=packs.identity(renamed))
        seen = []
        def convert(command, apply, output_flag, output, original):
            self.assertTrue(Path(output).is_relative_to(self.state))
            self.assertFalse(Path(output).is_relative_to(self.cache))
            seen.append(Path(output))
            Path(output).write_bytes(Path(original).read_bytes())
        self.m.worker = types.SimpleNamespace(convert_tool=convert)
        value.worker = self.m.worker
        output, _ = value.prepared(member, self.state)
        self.assertEqual(len(seen), 1)
        self.assertEqual(output.read_bytes(), renamed.read_bytes())

    def test_filesystem_reserve_refuses_growth(self):
        p = self.policy()
        filesystem = types.SimpleNamespace(f_bavail=1, f_frsize=1)
        with patch.object(core.os, 'fstatvfs', return_value=filesystem):
            with p.allocation(self.cache, 0, nodes=0): pass
            with self.assertRaises(core.Held):
                with p.allocation(self.cache, 1, nodes=1): pass

    def test_symlinked_stage_is_refused(self):
        p = self.policy(); source = self.state / 'issue.cbz'; source.write_bytes(b'abc')
        other = self.state / 'other'; other.mkdir()
        stage = self.cache / '.mylar-pack-link'; stage.symlink_to(other, target_is_directory=True)
        with self.assertRaises((core.Held, OSError)):
            worker.publish(p, source, stage, stage / source.name)
        self.assertEqual(list(other.iterdir()), [])

    def test_native_lock_excludes_other_process(self):
        p = self.policy()
        with p.allocation(self.cache, 0, nodes=0):
            code = '''import fcntl,os,sys
fd=os.open(sys.argv[1],os.O_RDONLY)
try: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError: sys.exit(0)
sys.exit(1)
'''
            result = subprocess.run([sys.executable, '-c', code, str(self.lock)], check=False)
            self.assertEqual(result.returncode, 0)

    def test_policy_closes_original_config_after_last_descriptor_callback(self):
        p=self.policy();actual=worker.os.close;fired=[]
        def changed(fd):
            target=Path('/proc/self/fd/'+str(fd)).readlink()
            result=actual(fd)
            if target==p.lock and not fired:
                fired.append(True);p.config.write_text('late original change')
            return result
        with patch.object(worker.os,'close',changed),self.assertRaises(core.Held):p.check()
        self.assertEqual(fired,[True])

    def test_reservation_exit_closes_policy_after_unlock_callbacks(self):
        p=self.policy();actual=worker.os.close;fired=[];reservation_fd=[None]
        def changed(fd):
            result=actual(fd)
            if fd==reservation_fd[0] and not fired:
                fired.append(True);self.config.write_text('changed at reservation release')
            return result
        with patch.object(worker.os,'close',changed),self.assertRaises(core.Held):
            with p.allocation(self.cache,0) as lease:reservation_fd[0]=lease.fd
        self.assertEqual(fired,[True])

    def test_full_cache_preflight_does_not_create_conversion_workspace(self):
        value,member,source=self.pack_fixture();self.packet['maximum']=1
        for _ in range(3):
            with self.assertRaises(core.Held):value.prepared(member,self.state)
        self.assertEqual(list(self.state.glob('pack-conversion-*')),[]);self.assertTrue(source.is_file())

    def test_late_capacity_refusal_reuses_one_finalized_attempt_then_resumes(self):
        value,member,source=self.pack_fixture();real=value.m.info;conversions=[];blocked=[True]
        def observed(path):
            if str(path).startswith(str(self.state)):
                conversions.append(str(path))
            return real(path)
        original_publish=worker.publish
        def late(*args):
            if blocked[0]:
                with patch.object(core.os,'fstatvfs',return_value=types.SimpleNamespace(f_bavail=0,f_frsize=1)):
                    return original_publish(*args)
            return original_publish(*args)
        with patch.object(worker,'publish',late),patch.object(value.m,'info',observed):
            for _ in range(3):
                with self.assertRaises(core.Held):value.prepared(member,self.state)
            works=list(self.state.glob('pack-conversion-*'));self.assertEqual(len(works),1)
            prepared=list(works[0].glob('*.cbz'));self.assertEqual(len(prepared),1)
            before=core.identity(prepared[0].stat());raw=prepared[0].read_bytes()
            blocked[0]=False;output,_=value.prepared(member,self.state)
        self.assertEqual(output.read_bytes(),source.read_bytes());self.assertEqual(prepared[0].read_bytes(),raw)
        self.assertEqual(core.identity(prepared[0].stat()),before);self.assertEqual(len(list(self.state.glob('pack-conversion-*'))),1)
        self.assertTrue(conversions)

    def test_incomplete_or_changed_attempt_is_retained_without_reconversion(self):
        value,member,source=self.pack_fixture()
        with patch.object(worker,'publish',side_effect=core.Held('late capacity')),self.assertRaises(core.Held):value.prepared(member,self.state)
        work=next(self.state.glob('pack-conversion-*'));receipt=work/'finalized-v1.json';output=next(work.glob('*.cbz'))
        output.write_bytes(b'changed retained original');bad=output.read_bytes()
        with self.assertRaises(core.Held):value.prepared(member,self.state)
        self.assertEqual(output.read_bytes(),bad);self.assertEqual(len(list(self.state.glob('pack-conversion-*'))),1)
        receipt.unlink()
        with self.assertRaises(core.Held):value.prepared(member,self.state)
        self.assertTrue(source.is_file());self.assertEqual(output.read_bytes(),bad)

    def test_replaced_workspace_refuses_without_reconversion(self):
        value,member,_=self.pack_fixture()
        with patch.object(worker,'publish',side_effect=core.Held('late capacity')),self.assertRaises(core.Held):value.prepared(member,self.state)
        work=next(self.state.glob('pack-conversion-*'));moved=self.state/'retained-work';work.rename(moved);work.mkdir(mode=0o700)
        for child in list(moved.iterdir()):child.rename(work/child.name)
        with self.assertRaises(core.Held):value.prepared(member,self.state)
        self.assertEqual(len(list(work.iterdir())),2)

    def test_late_receipt_mode_change_retains_copy_but_refuses_completion(self):
        value,member,source=self.pack_fixture();actual=worker.Policy.check;fired=[]
        def late(policy):
            actual(policy)
            receipts=list(self.state.glob('pack-conversion-*/finalized-v1.json'))
            if receipts and list(self.cache.glob('.mylar-pack-*/*.cbz')) and not fired:
                fired.append(True);receipts[0].chmod(0o640)
        with patch.object(worker.Policy,'check',late),self.assertRaises(core.Held):value.prepared(member,self.state)
        self.assertEqual(fired,[True]);self.assertTrue(source.is_file())
        self.assertEqual(len(list(self.state.glob('pack-conversion-*'))),1)

    def test_incomplete_conversion_after_callback_failure_is_not_repeated(self):
        value,member,source=self.pack_fixture();actual=value.m.info;fired=[]
        def fail(path):
            if Path(path).parent.name.startswith('pack-conversion-'):
                fired.append(True);raise core.Held('fixture conversion interrupted before receipt')
            return actual(path)
        with patch.object(value.m,'info',fail),self.assertRaises(core.Held):value.prepared(member,self.state)
        self.assertEqual(fired,[True]);work=next(self.state.glob('pack-conversion-*'))
        output=next(work.glob('*.cbz'));raw=output.read_bytes()
        self.assertFalse((work/'finalized-v1.json').exists())
        with self.assertRaises(core.Held):value.prepared(member,self.state)
        self.assertEqual(output.read_bytes(),raw);self.assertTrue(source.is_file())
        self.assertEqual(len(list(self.state.glob('pack-conversion-*'))),1)

    def test_readonly_hardlinked_original_is_preserved(self):
        value,member,source=self.pack_fixture();other=self.state/'retained-source-link.cbz'
        other.hardlink_to(source);member['identity']=packs.identity(source)
        before=core.identity(source.stat());raw=source.read_bytes()
        output,_=value.prepared(member,self.state)
        self.assertEqual(output.read_bytes(),raw);self.assertEqual(other.read_bytes(),raw)
        self.assertEqual(core.identity(source.stat()),before);self.assertEqual(source.stat().st_nlink,2)


    def test_original_conversion_request_drift_after_publish_refuses(self):
        for field in ('id','source','sha256','identity'):
            with self.subTest(field=field):
                f=type(self)('run');f.setUp();self.addCleanup(f.doCleanups)
                value,member,source=f.pack_fixture();before=source.read_bytes();actual=worker.Policy.check;fired=[]
                def late(policy):
                    actual(policy)
                    if list(f.cache.glob('.mylar-pack-*/*.cbz')) and not fired:
                        if field=='id':member[field]='f'*64
                        elif field=='source':member[field]=str(f.root/'foreign-source')
                        elif field=='sha256':member[field]='0'*64
                        else:member[field]=[0]*len(member[field])
                        fired.append(True)
                with patch.object(worker.Policy,'check',late),self.assertRaisesRegex(core.Held,'Original conversion request changed'):
                    value.prepared(member,f.state)
                self.assertEqual(fired,[True]);self.assertEqual(source.read_bytes(),before)
                self.assertTrue(list(f.state.glob('pack-conversion-*/finalized-v1.json')))

    def test_original_conversion_request_drift_before_first_cache_copy_refuses(self):
        value,member,source=self.pack_fixture();before=source.read_bytes();actual=worker.Policy.check;fired=[]
        def late(policy):
            actual(policy)
            if list(self.state.glob('pack-conversion-*/finalized-v1.json')) and not fired:
                member['id']='f'*64;fired.append(True)
        with patch.object(worker.Policy,'check',late),self.assertRaisesRegex(core.Held,'Original conversion request changed'):
            value.prepared(member,self.state)
        self.assertEqual(fired,[True]);self.assertEqual(source.read_bytes(),before)
        self.assertFalse(list(self.cache.glob('.mylar-pack-*/*.cbz')))

    def test_original_conversion_request_drift_in_final_namespace_refuses(self):
        value,member,source=self.pack_fixture();before=source.read_bytes();actual=worker.os.listdir;fired=[]
        def late(path):
            names=actual(path)
            if str(path).startswith(str(self.state/'pack-conversion-')) and list(self.cache.glob('.mylar-pack-*/*.cbz')) and not fired:
                member['id']='f'*64;fired.append(True)
            return names
        with patch.object(worker.os,'listdir',late),self.assertRaisesRegex(core.Held,'Original conversion request changed'):
            value.prepared(member,self.state)
        self.assertEqual(fired,[True]);self.assertEqual(source.read_bytes(),before)

if __name__ == '__main__': unittest.main(verbosity=2)
