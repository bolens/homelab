"""Actual owner-process reads over disposable media, without Docker or services."""
import hashlib
import os
from pathlib import Path
import tempfile
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import comic_retained_pack_observation as observation


class OwnerReads(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.media = self.root / 'media'
        self.media.mkdir()
        self.payload = self.media / 'original.cbz'
        self.payload.write_bytes(b'original archive bytes')
        self.principal = (os.getpid(), os.geteuid(), os.getegid())
        # Root runners grant access only to this new disposable tree.
        if os.geteuid() == 0:
            for path in (self.root, self.media, self.payload):
                os.chown(path, 1000, 1000)

    def capture(self, streams=None):
        return observation.OwnerObservation.capture([str(self.media)],
            [str(self.payload)] if streams is None else streams,
            deadline=time.monotonic() + 15)

    def test_actual_child_hashes_original_and_preserves_parent_identity(self):
        held = self.capture()
        actual = held.data()
        self.assertEqual(actual['hashes'][str(self.payload)],
                         hashlib.sha256(self.payload.read_bytes()).hexdigest())
        self.assertEqual(actual['names'][str(self.media)], ['original.cbz'])
        self.assertEqual(actual, held.close())
        self.assertEqual(self.principal, (os.getpid(), os.geteuid(), os.getegid()))
        actual['hashes'].clear()
        self.assertIn(str(self.payload), held.data()['hashes'])

    def test_changed_payload_refuses_original_closure(self):
        held = self.capture()
        self.payload.write_bytes(b'foreign replacement')
        with self.assertRaisesRegex(ValueError, 'unchanged-media'):
            held.close()

    def test_late_directory_child_refuses_original_closure(self):
        held = self.capture()
        (self.media / 'late.cbz').write_bytes(b'late')
        with self.assertRaisesRegex(ValueError, 'unchanged-media'):
            held.close()

    def test_selected_symlink_refuses_without_following_target(self):
        link = self.media / 'alias.cbz'
        link.symlink_to(self.payload.name)
        with self.assertRaisesRegex(ValueError, 'child-bound-or-changed'):
            self.capture([str(link)])

    def test_stream_outside_complete_tree_refuses(self):
        outside = self.root / 'outside.cbz'
        outside.write_bytes(b'not selected')
        with self.assertRaisesRegex(ValueError, 'child-bound-or-changed'):
            self.capture([str(outside)])

    def test_actual_unreadable_directory_reports_principal_failure(self):
        locked = self.media / 'locked'
        locked.mkdir(mode=0)
        self.addCleanup(locked.chmod, 0o700)
        with self.assertRaisesRegex(ValueError, 'child-permission'):
            self.capture()

    def test_constructor_cannot_hydrate_saved_observation(self):
        with self.assertRaisesRegex(ValueError, 'Original owner observation'):
            observation.OwnerObservation(self.capture().data())

    def test_equal_replacement_record_does_not_recreate_original(self):
        held = self.capture()
        original = observation._OBSERVATIONS[held]
        replacement = tuple(list(original))
        self.assertEqual(original, replacement)
        self.assertIsNot(original, replacement)
        observation._OBSERVATIONS[held] = replacement
        with self.assertRaisesRegex(ValueError, 'original-custody'):
            held.close()

    def test_registry_replacement_refuses(self):
        held = self.capture()
        with patch.object(observation, '_OBSERVATIONS', dict(observation._OBSERVATIONS)):
            with self.assertRaisesRegex(ValueError, 'original-custody'):
                held.close()

    def test_encoder_substitution_cannot_hide_changed_media(self):
        held = self.capture()
        original_bytes = observation._OBSERVATIONS[held][4]
        encoder = observation.encode
        self.payload.write_bytes(b'foreign')
        def substituted(value):
            if type(value) is dict and set(value) == {'files','nodes','names','hashes','attrs'}:
                return original_bytes
            return encoder(value)
        with patch.object(observation, 'encode', substituted):
            with self.assertRaisesRegex(ValueError, 'original-helper'):
                held.close()

    def test_foreign_checker_never_dispatches(self):
        held = self.capture()
        fired = []
        def foreign(*args):
            fired.append(True)
        with patch.object(observation, 'need', foreign):
            with self.assertRaisesRegex(ValueError, 'original-helper'):
                held.close()
        self.assertFalse(fired)

    def test_root_path_cannot_cross_symlink_ancestor(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.media, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'child-'):
            observation.OwnerObservation.capture([str(alias)], [], deadline=time.monotonic()+15)

    def test_expired_original_deadline_refuses(self):
        with self.assertRaisesRegex(ValueError, 'original-deadline'):
            observation.OwnerObservation.capture([str(self.media)], [], deadline=time.monotonic()-1)

    def test_nonfinite_original_deadline_refuses(self):
        for deadline in (float('inf'), float('nan')):
            with self.assertRaisesRegex(ValueError, 'original-deadline'):
                observation.OwnerObservation.capture([str(self.media)], [], deadline=deadline)

    def test_aggregate_bound_applies_during_collection(self):
        for index in range(8):
            (self.media / ('more-'+str(index))).write_bytes(b'original')
        with patch.object(observation, 'MAX_WIRE', 512):
            with self.assertRaisesRegex(ValueError, 'child-bound-or-changed'):
                self.capture()

    def test_extended_attributes_are_independently_read(self):
        os.setxattr(self.payload, 'user.retained-test', b'preserve')
        held = self.capture()
        self.assertEqual(held.data()['attrs'][str(self.payload)], {'user.retained-test': b'preserve'.hex()})
        os.setxattr(self.payload, 'user.retained-test', b'changed')
        with self.assertRaisesRegex(ValueError, 'unchanged-media'):
            held.close()


class ProcessImageReads(unittest.TestCase):
    """Actual self-process namespace/FDs with an explicit runtime/principal double."""
    def setUp(self):
        import comic_retained_pack_parent as parent
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.path=self.root/'public.py';self.path.write_bytes(b'# public source\n');self.path.chmod(0o644)
        self.runtime=object.__new__(parent.ConfiguredRuntime)
        self.runtime.baseline={'native':{'State':{'Pid':os.getpid()},'Mounts':[]}};self.runtime.deadline=time.monotonic()+30
        self.runtime.process=None;parent._RUNTIMES[self.runtime]=b'explicit mechanics fixture'
        self.addCleanup(parent._RUNTIMES.pop,self.runtime,None)
        uid=os.geteuid()
        for context in (patch.object(parent.ConfiguredRuntime,'close_local',lambda _:None),
                        patch.object(observation.os,'geteuid',return_value=0),
                        patch.object(observation,'IMAGE_SOURCE_UID',uid),
                        patch.object(observation,'IMAGE_SOURCE_PREFIXES',(str(self.root),))):
            context.start();self.addCleanup(context.stop)
        self.pins={str(self.path):hashlib.sha256(self.path.read_bytes()).hexdigest()}
    def capture(self):return observation.ProcessImageObservation.capture(self.runtime,'native',self.pins)
    def test_live_namespace_and_source_FDs_close_without_engine_calls(self):
        value=self.capture();data=value.data();self.assertEqual(data[str(self.path)]['sha256'],self.pins[str(self.path)])
        original=value.close();fds=original[15];value.release()
        for fd in fds:
            with self.assertRaises(OSError):os.fstat(fd)
    def test_same_bytes_replacement_refuses_and_release_still_closes_owned_FDs(self):
        value=self.capture();fds=value.close()[15]
        replacement=self.root/'replacement';replacement.write_bytes(self.path.read_bytes());replacement.chmod(0o644)
        os.replace(replacement,self.path)
        with self.assertRaisesRegex(ValueError,'original-source'):value.close()
        with self.assertRaises(ValueError):value.release()
        for fd in fds:
            with self.assertRaises(OSError):os.fstat(fd)
    def test_changed_same_result_helper_is_not_a_new_source_witness(self):
        value=self.capture();encode=observation.encode
        with patch.object(observation,'encode',lambda data:encode(data)):
            with self.assertRaisesRegex(ValueError,'original-helper'):value.close()
        value.release()
    def test_foreign_checker_is_refused_before_it_can_run(self):
        value=self.capture();called=[]
        def foreign(*args):called.append(True)
        with patch.object(observation,'need',foreign):
            with self.assertRaisesRegex(ValueError,'original-helper'):value.close()
        self.assertEqual(called,[]);value.release()

    def test_release_preserves_foreign_reused_FD_and_closes_other_owned_FDs(self):
        value=self.capture();original=value.close();selected=original[10][0][1]
        foreign=self.root/'foreign';foreign.write_bytes(b'foreign')
        os.close(selected);replacement=os.open(foreign,os.O_RDONLY)
        self.addCleanup(os.close,replacement);self.assertEqual(replacement,selected)
        with self.assertRaises(ValueError):value.release()
        self.assertEqual(os.fstat(replacement).st_ino,foreign.stat().st_ino)
        for fd in original[15]:
            if fd!=replacement:
                with self.assertRaises(OSError):os.fstat(fd)

    def test_failed_capture_closes_all_new_descriptors(self):
        original=len(os.listdir('/proc/self/fd'));self.pins[str(self.path)]='a'*64
        with self.assertRaisesRegex(ValueError,'original-bytes'):self.capture()
        self.assertEqual(len(os.listdir('/proc/self/fd')),original)


if __name__ == '__main__':
    unittest.main()
