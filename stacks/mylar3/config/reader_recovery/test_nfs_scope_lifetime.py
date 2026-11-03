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
        callback=getattr(self,'close_callback',None)
        if callback is not None:callback()

    def send(self, kind, payload):
        self.close()
        self.calls.append((kind, copy.deepcopy(payload)))
        self.sequence += 1
        return self.sequence

    def receive(self, sequence):
        self.close()
        need(sequence == self.sequence, 'original-sequence')
        callback=getattr(self,'reply_callback',None)
        if callback is not None:callback()
        if self.calls[-1][0] == 'nfs-readonly-roots':
            if self.readonly_proof is None:
                raise EOFError('lost response')
            callback = getattr(self, 'readonly_callback', None)
            if callback is not None:
                callback()
            return copy.deepcopy(self.readonly_proof)
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
        self.assertEqual([kind for kind, _ in self.channel.calls], ['nfs-reader-epoch'])

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

    def test_replaced_live_root_mapper_refuses_before_call(self):
        def body(lifetime):
            active.fresh_scope(self.scope, lifetime)
            def foreign(*args):
                self.fail('foreign live-root mapper invoked')
            with patch.object(interface, 'live_root_bindings', foreign):
                active.fresh_scope(self.scope, lifetime)
        with self.assertRaisesRegex(active.Held, 'scope-original-helper'):
            self.invoke(body)

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


    def bound_scopes(self):
        other = dict(kind='reviewed-komga-effective-scope-runtime', observed=985, original='effective')
        self.channel.epoch.update(version=2, original_scopes={
            value['kind']: hashlib.sha256(active.encode(value)).hexdigest() for value in (self.scope, other)})
        return other

    def test_each_original_document_first_admits_after_long_prepare_in_either_order(self):
        other = self.bound_scopes()
        self.wall += 10000
        originals = copy.deepcopy((self.scope, other))
        for documents in ((self.scope, other), (other, self.scope)):
            with self.subTest(first=documents[0]['kind']):
                def body(lifetime):
                    for value in documents: active.fresh_scope(value, lifetime)
                    self.assertEqual((self.scope, other), originals)
                with self.assertRaises(Finished): self.invoke(body)

    def test_fresh_wrong_document_cannot_borrow_parent_binding(self):
        self.bound_scopes()
        with self.assertRaisesRegex(active.Held, 'scope-original-parent-binding'):
            self.invoke(lambda lifetime: active.fresh_scope(dict(self.scope, original='foreign'), lifetime))

    def test_bound_reply_missing_other_document_refuses(self):
        self.bound_scopes()
        del self.channel.epoch['original_scopes']['reviewed-komga-effective-scope-runtime']
        with self.assertRaisesRegex(interface.Held, 'original-scope-bindings'):
            self.invoke(lambda lifetime: active.fresh_scope(self.scope, lifetime))

    def test_bound_reply_foreign_kind_or_malformed_digest_refuses(self):
        self.bound_scopes()
        for bad in ({'foreign': '0'*64}, {self.scope['kind']: True, 'reviewed-komga-effective-scope-runtime': '0'*64}):
            self.channel.epoch['original_scopes'] = bad
            with self.assertRaisesRegex(interface.Held, 'original-scope-bindings'):
                self.invoke(lambda lifetime: active.fresh_scope(self.scope, lifetime))

    def test_first_unseen_document_under_writer_never_pulses_or_admits(self):
        other = self.bound_scopes()
        with tempfile.TemporaryDirectory() as tmp:
            def body(lifetime):
                active.fresh_scope(self.scope, lifetime)
                lifetime.factory(tmp, self.channel.engine); lifetime.prepare(); lifetime.acquire()
                self.channel.calls.clear()
                with self.assertRaisesRegex(active.Held, 'prelease-original-admission-required'):
                    active.fresh_scope(other, lifetime)
                self.assertEqual(self.channel.calls, [])
            with self.assertRaises(Finished): self.invoke(body)

    def test_bound_document_epoch_restart_still_refuses(self):
        other = self.bound_scopes()
        def body(lifetime):
            active.fresh_scope(self.scope, lifetime)
            self.channel.epoch['start_ticks'] += 1
            active.fresh_scope(other, lifetime)
        with self.assertRaisesRegex(active.Held, 'scope-original-reader-epoch'): self.invoke(body)

    def test_bound_document_cannot_renew_original_deadline(self):
        self.bound_scopes()
        def body(lifetime):
            self.wall += 10000; self.tick = self.channel.deadline
            active.fresh_scope(self.scope, lifetime)
        with self.assertRaisesRegex(interface.Held, 'child-deadline'): self.invoke(body)

    def test_bound_document_requires_integer_observation_even_when_digest_matches(self):
        self.scope['observed'] = True; self.bound_scopes()
        with self.assertRaisesRegex(active.Held, 'scope-observed-type'):
            self.invoke(lambda lifetime: active.fresh_scope(self.scope, lifetime))

    def test_bound_reply_extra_authority_fields_refuse(self):
        self.bound_scopes(); self.channel.epoch['scope_grant'] = True
        with self.assertRaisesRegex(interface.Held, 'host-reader-epoch'):
            self.invoke(lambda lifetime: active.fresh_scope(self.scope, lifetime))

    def test_bound_document_mutation_after_first_admission_still_refuses(self):
        self.bound_scopes()
        def body(lifetime):
            active.fresh_scope(self.scope, lifetime)
            self.scope['observed'] += 1
            active.fresh_scope(self.scope, lifetime)
        with self.assertRaisesRegex(active.Held, 'scope-original-document'): self.invoke(body)


    def test_bound_scope_hash_helper_cannot_be_replaced_after_registration(self):
        other=self.bound_scopes()
        def body(lifetime):
            active.fresh_scope(self.scope,lifetime)
            with patch.object(active,'digest',lambda raw:'0'*64):
                active.fresh_scope(other,lifetime)
        with self.assertRaisesRegex(active.Held,'scope-original-helper'):self.invoke(body)


    def test_foreign_check_helper_is_refused_before_it_can_run(self):
        self.bound_scopes();called=[]
        def foreign(*args):called.append(args);raise AssertionError('foreign checker ran')
        def body(lifetime):
            with patch.object(active,'check',foreign):active.fresh_scope(self.scope,lifetime)
        with self.assertRaisesRegex(active.Held,'scope-original-helper'):self.invoke(body)
        self.assertEqual(called,[])

    def test_noop_check_helper_cannot_suppress_its_own_identity_guard(self):
        self.bound_scopes();called=[]
        def foreign(*args):called.append(args)
        def body(lifetime):
            with patch.object(active,'check',foreign):active.fresh_scope(self.scope,lifetime)
        with self.assertRaisesRegex(active.Held,'scope-original-helper'):self.invoke(body)
        self.assertEqual(called,[])


    def test_readonly_boundary_checks_helpers_before_metadata_or_foreign_checker(self):
        called=[]
        def foreign(*args):called.append('check')
        def metadata(*args):called.append('metadata');raise AssertionError('metadata before guard')
        def body(lifetime):
            with patch.object(active,'check',foreign),patch.object(active,'stamp',metadata):
                active.protected_root_vectors((Path('/must-not-read'),),lifetime=lifetime)
        with self.assertRaisesRegex(active.Held,'scope-original-helper'):self.invoke(body)
        self.assertEqual(called,[])


    def test_epoch_receive_cannot_dispatch_replaced_checker_before_reclosure(self):
        self.bound_scopes();called=[];original=active.check
        def foreign(*args):called.append(args)
        def body(lifetime):
            self.channel.reply_callback=lambda:setattr(active,'check',foreign)
            try:active.fresh_scope(self.scope,lifetime)
            finally:active.check=original;self.channel.reply_callback=None
        with self.assertRaisesRegex(active.Held,'scope-original-helper'):self.invoke(body)
        self.assertEqual(called,[])

    def test_pulse_receive_cannot_dispatch_replaced_checker_before_reclosure(self):
        self.bound_scopes();called=[];original=active.check
        def foreign(*args):called.append(args)
        with tempfile.TemporaryDirectory() as tmp:
            def body(lifetime):
                active.fresh_scope(self.scope,lifetime)
                lifetime.factory(tmp,self.channel.engine);lifetime.prepare();lifetime.acquire()
                self.channel.reply_callback=lambda:setattr(active,'check',foreign)
                try:active.fresh_scope(self.scope,lifetime)
                finally:active.check=original;self.channel.reply_callback=None
            with self.assertRaisesRegex(active.Held,'scope-original-helper'):self.invoke(body)
        self.assertEqual(called,[])

    def test_admit_cannot_return_with_a_replaced_checker(self):
        self.bound_scopes();called=[];original=active.check
        def foreign(*args):called.append(args)
        def body(lifetime):
            self.channel.close_callback=lambda:setattr(active,'check',foreign)
            try:active.fresh_scope(self.scope,lifetime)
            finally:active.check=original;self.channel.close_callback=None
        with self.assertRaisesRegex(active.Held,'scope-original-helper'):self.invoke(body)
        self.assertEqual(called,[])

    def test_scope_memory_change_during_epoch_callback_is_not_adopted(self):
        self.bound_scopes()
        def body(lifetime):
            self.channel.reply_callback=lambda:self.scope.update(observed=self.scope['observed']+1)
            active.fresh_scope(self.scope,lifetime)
        with self.assertRaisesRegex(active.Held,'scope-original-document'):self.invoke(body)


    def checker_replacement(self,phase,change='function',name='_scope_lifetime_current'):
        self.bound_scopes();called=[];original=getattr(active,name);code=original.__code__;defaults=original.__defaults__
        def foreign(*args):called.append(args);raise AssertionError('foreign guard called')
        def foreign_code(*args):raise AssertionError('foreign guard code called')
        def change_checker():
            if change=='code':original.__code__=foreign_code.__code__
            elif change=='defaults':original.__defaults__=()
            else:setattr(active,name,foreign)
        with tempfile.TemporaryDirectory() as tmp:
            def body(lifetime):
                if phase=='pulse':
                    active.fresh_scope(self.scope,lifetime)
                    lifetime.factory(tmp,self.channel.engine);lifetime.prepare();lifetime.acquire()
                if phase=='readonly':self.channel.readonly_proof={}
                self.channel.reply_callback=change_checker
                try:
                    if phase=='readonly':active.protected_root_vectors((),lifetime=lifetime)
                    else:active.fresh_scope(self.scope,lifetime)
                finally:
                    setattr(active,name,original);original.__code__=code;original.__defaults__=defaults
                    self.channel.reply_callback=None
            with self.assertRaisesRegex(active.Held,'scope-original-(checker|helper)'):self.invoke(body)
        self.assertEqual(called,[])

    def test_epoch_reply_cannot_replace_the_captured_guard(self):self.checker_replacement('epoch')
    def test_pulse_reply_cannot_replace_the_captured_guard(self):self.checker_replacement('pulse')
    def test_readonly_reply_cannot_replace_the_captured_guard(self):self.checker_replacement('readonly')
    def test_epoch_reply_cannot_change_guard_code(self):self.checker_replacement('epoch','code')
    def test_epoch_reply_cannot_replace_delegated_method_checker(self):self.checker_replacement('epoch',name='_scope_methods_current')
    def test_epoch_reply_cannot_change_guard_defaults(self):self.checker_replacement('epoch','defaults')


if __name__ == '__main__':
    unittest.main()
