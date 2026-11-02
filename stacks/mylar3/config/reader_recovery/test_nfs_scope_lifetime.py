"""Fresh admission versus original configured continuation; no Docker or grant."""
import __main__
import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
import comic_negative_nfs_active_parent as active
import comic_nfs_lease_session as interface
from comic_nfs_uid_child import decode, five as five

need = interface.need
encode = interface.encode


class Finished(Exception):
    pass


class Channel:
    """Finite protocol peer for the actual source-checked interface, no engine."""
    def __init__(self):
        self.read_fd, self.write_fd = 0, 1
        self.nonce = 'a' * 64
        self.facts = ((1, 2), (3, 4))
        self.deadline = time.monotonic() + 900
        self.sequence = 0
        self.calls = []
        self.epoch = dict(version=1, kind='parent-original-reader-host-epoch',
                          cid='b' * 64, pid=41, started_at='original', start_ticks=100,
                          native_grant=False, publication_authority=False)

    def close(self):
        need(time.monotonic() < self.deadline, 'child-deadline')

    def send(self, kind, payload):
        self.close()
        self.calls.append((kind, copy.deepcopy(payload)))
        self.sequence += 1
        return self.sequence

    def receive(self, sequence):
        self.close()
        need(sequence == self.sequence, 'original-sequence')
        if self.calls[-1][0] == 'nfs-reader-epoch':
            return decode(encode(self.epoch))
        return decode(encode(dict(held=True)))

    def engine(self, *args, **kwargs):
        raise AssertionError('scope continuation must not call Docker or HTTP')


class Lifetime(unittest.TestCase):
    def setUp(self):
        self.wall, self.tick = 1000, 100
        self.scope = dict(kind='root-reviewed-nfs-active-disposable-scope',observed=990, original='scope')
        self.channel = Channel()
        self.main_channel = patch.object(__main__, 'Channel', Channel, create=True)
        self.main_channel.start()
        self.addCleanup(self.main_channel.stop)
        self.lease = interface.ChildLeaseInterface(self.channel)
        self.channel.deadline = 1000
        self.ref = dict(path=str(ROOT / 'comic_nfs_lease_session.py'),
                        sha256=hashlib.sha256((ROOT / 'comic_nfs_lease_session.py').read_bytes()).hexdigest(),
                        signature9=active.stamp(ROOT / 'comic_nfs_lease_session.py'))

    def invoke(self, body):
        def entered(*args):
            lifetime = args[-1]
            self.assertIs(lifetime, self.lease)
            body(lifetime)
            raise Finished()
        try:
            with patch.object(active.time, 'time', lambda: self.wall), \
                    patch.object(active.time, 'monotonic', lambda: self.tick), \
                    patch.object(active, '_execute_factual', entered):
                active.run_active_host_factual(types.SimpleNamespace(execute=True), self.channel.engine,
                    interface_module=interface, lease_interface=self.lease, interface_ref=self.ref)
        finally:
            self.assertNotIn(self.lease, active._SCOPE_LIFETIMES)

    def test_original_scope_survives_long_prepare_without_rebasing_timestamp(self):
        original = copy.deepcopy(self.scope)
        def body(lifetime):
            active.fresh_scope(self.scope, lifetime)
            self.wall += 10000
            self.tick += 191
            active.fresh_scope(self.scope, lifetime)
            self.assertEqual(self.scope, original)
            self.assertEqual([k for k, _ in self.channel.calls], ['nfs-reader-epoch'] * 2)
        with self.assertRaises(Finished):
            self.invoke(body)

    def test_stale_first_document_is_not_a_continuation(self):
        self.wall += 191
        with self.assertRaisesRegex(active.Held, 'scope-expired'):
            self.invoke(lambda lifetime: active.fresh_scope(self.scope, lifetime))
        self.assertEqual(self.channel.calls, [])

    def test_changed_or_detached_document_cannot_borrow_old_admission(self):
        def body(lifetime):
            active.fresh_scope(self.scope, lifetime)
            self.wall += 191
            with self.assertRaisesRegex(active.Held, 'scope-original-document'):
                active.fresh_scope(dict(self.scope, original='replacement'), lifetime)
            with self.assertRaisesRegex(active.Held, 'scope-expired'):
                active.fresh_scope(self.scope)
            with self.assertRaisesRegex(active.Held, 'scope-original-document-kind'):
                active.fresh_scope(dict(self.scope,kind='foreign'),lifetime)
        with self.assertRaises(Finished):
            self.invoke(body)

    def test_live_writer_uses_only_its_existing_heartbeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            def body(lifetime):
                active.fresh_scope(self.scope, lifetime)
                lifetime.factory(tmp, self.channel.engine)
                lifetime.prepare()
                lifetime.acquire()
                self.channel.calls.clear()
                self.wall += 191
                active.fresh_scope(self.scope, lifetime)
                self.assertEqual(self.channel.calls, [('nfs-lease', dict(operation='pulse', absent=[], empty=None))])
                lifetime.release_after_absence((Path(tmp) / 'absent-a', Path(tmp) / 'absent-b'))
                self.channel.calls.clear()
                active.fresh_scope(self.scope, lifetime)
                self.assertEqual([k for k, _ in self.channel.calls], ['nfs-reader-epoch'])
            with self.assertRaises(Finished):
                self.invoke(body)

    def test_reader_restart_refuses_even_with_fresh_wall_clock(self):
        def body(lifetime):
            active.fresh_scope(self.scope, lifetime)
            self.channel.epoch['start_ticks'] += 1
            active.fresh_scope(self.scope, lifetime)
        with self.assertRaisesRegex(active.Held, 'scope-original-reader-epoch'):
            self.invoke(body)

    def test_original_deadline_is_not_renewed(self):
        def body(lifetime):
            active.fresh_scope(self.scope, lifetime)
            self.tick = self.channel.deadline
            active.fresh_scope(self.scope, lifetime)
        with self.assertRaisesRegex(interface.Held, 'child-deadline'):
            self.invoke(body)

    def test_replaced_channel_identity_or_deadline_refuses(self):
        for field, replacement in [('nonce', 'c' * 64), ('facts', ((9, 9),)),
                                   ('deadline', 2000), ('read_fd', 6), ('write_fd', 7)]:
            with self.subTest(field=field):
                old = getattr(self.channel, field)
                def body(lifetime):
                    active.fresh_scope(self.scope, lifetime)
                    setattr(self.channel, field, replacement)
                    active.fresh_scope(self.scope, lifetime)
                try:
                    with self.assertRaisesRegex(active.Held, 'scope-original-channel'):
                        self.invoke(body)
                finally:
                    setattr(self.channel, field, old)

    def test_replaced_interface_or_channel_methods_refuse(self):
        for owner, name in [(interface.ChildLeaseInterface, 'admit'), (Channel, 'close'),
                            (interface.ChildLeaseInterface, 'pulse'), (Channel, 'receive')]:
            with self.subTest(method=name):
                def body(lifetime):
                    active.fresh_scope(self.scope, lifetime)
                    with patch.object(owner, name, lambda *a, **k: None):
                        active.fresh_scope(self.scope, lifetime)
                with self.assertRaisesRegex(active.Held, 'scope-original-method'):
                    self.invoke(body)
        def changed_defaults(lifetime):
            active.fresh_scope(self.scope,lifetime)
            with patch.dict(interface.ChildLeaseInterface.release_after_absence.__kwdefaults__,
                            original_files=('foreign',)):
                active.fresh_scope(self.scope,lifetime)
        with self.assertRaisesRegex(active.Held, 'scope-original-method-defaults'):
            self.invoke(changed_defaults)
        def changed_decoder(lifetime):
            active.fresh_scope(self.scope,lifetime)
            self.wall += 191
            def foreign(*args):
                self.fail('foreign response decoder invoked')
            with patch.dict(Channel.receive.__globals__,decode=foreign):
                active.fresh_scope(self.scope,lifetime)
        with self.assertRaisesRegex(active.Held, 'scope-original-helper'):
            self.invoke(changed_decoder)

    def test_foreign_interface_cannot_use_original_registration(self):
        def body(lifetime):
            active.fresh_scope(self.scope, lifetime)
            foreign = interface.ChildLeaseInterface(self.channel)
            with self.assertRaisesRegex(active.Held, 'scope-original-lifetime'):
                active.fresh_scope(self.scope, foreign)
        with self.assertRaises(Finished):
            self.invoke(body)

    def test_instance_method_shadows_are_never_called(self):
        for owner, name in [(self.channel, 'send'), (self.channel, 'receive'),
                            (self.lease, '_call'), (self.lease, 'admit'),
                            (self.lease, 'pulse'), (self.lease, 'reader_epoch')]:
            with self.subTest(method=name):
                def foreign(*args, **kwargs):
                    self.fail('foreign instance function invoked')
                def body(lifetime):
                    active.fresh_scope(self.scope, lifetime)
                    self.wall += 191
                    with patch.object(owner, name, foreign):
                        active.fresh_scope(self.scope, lifetime)
                with self.assertRaisesRegex(active.Held, 'scope-original-instance-methods'):
                    self.invoke(body)
                self.wall = 1000

    def test_preexisting_instance_shadow_cannot_enter_lifetime(self):
        with patch.object(self.lease, 'admit', lambda: self.fail('foreign admission invoked')):
            with self.assertRaisesRegex(active.Held, 'scope-original-instance-methods'):
                self.invoke(lambda lifetime: self.fail('entered foreign lifetime'))

    def test_parent_loss_refuses_after_original_admission(self):
        def body(lifetime):
            active.fresh_scope(self.scope, lifetime)
            # The original peer's receive fails; do not replace the method.
            self.channel.sequence = -1
            original_send = self.channel.calls
            class Lost(list):
                def append(self, value):
                    raise EOFError('original Parent exited')
            self.channel.calls = Lost(original_send)
            active.fresh_scope(self.scope, lifetime)
        with self.assertRaisesRegex(EOFError, 'original Parent exited'):
            self.invoke(body)


if __name__ == '__main__':
    unittest.main()
