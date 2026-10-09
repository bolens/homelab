"""Original negative38 read-only controls + strict new consume dispatch fixtures."""
from pathlib import Path
_PORTABLE_ROOT = next((p for p in Path(__file__).resolve().parents if (p / '.portable-cohort').is_file()))
import importlib.util
import sys
import types
import unittest
from unittest.mock import patch

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
old = load('negative_tests_original', str(_PORTABLE_ROOT / 'fixtures/test_publication_negative_v4.py'))
new = load('negative_producer_v6', str(_PORTABLE_ROOT / 'publication_negative.py'))
import hashlib
assert Path(new.__file__).resolve() == _PORTABLE_ROOT / 'publication_negative.py'
assert hashlib.sha256(Path(new.__file__).read_bytes()).hexdigest() == '85615fc4403982153adae10d2b72248f877e712f16329c16fdb2a2e6742d3d41'
old.m = new

class ConsumeDispatchTests(unittest.TestCase):

    def prep(self):
        return new.NativeNegativePreparation.__new__(new.NativeNegativePreparation)

    def test_missing_installed_phase_held(self):
        with patch.dict(sys.modules, {'mylar.publication_negative_phase': None}):
            with self.assertRaises(new.guard.Unavailable):
                self.prep().consume(True)

    def test_unknown_json_never_reservation(self):
        module = types.ModuleType('mylar.publication_negative_phase')
        module.__file__ = '/app/mylar3/mylar/publication_negative_phase.py'
        module.NegativeCommitReservation = type('TypedReservation', (), {})
        with patch.dict(sys.modules, {'mylar.publication_negative_phase': module}):
            with self.assertRaises(new.guard.Unavailable):
                self.prep().consume({'reader_verified': True})

    def test_wrong_phase_module_path_held(self):
        module = types.ModuleType('mylar.publication_negative_phase')
        module.__file__ = '/tmp/foreign.py'
        module.NegativeCommitReservation = type('TypedReservation', (), {})
        with patch.dict(sys.modules, {'mylar.publication_negative_phase': module}):
            with self.assertRaises(new.guard.Unavailable):
                self.prep().consume(module.NegativeCommitReservation())

    def test_no_subclass_reservation(self):
        module = types.ModuleType('mylar.publication_negative_phase')
        module.__file__ = '/app/mylar3/mylar/publication_negative_phase.py'
        module.NegativeCommitReservation = type('TypedReservation', (), {})
        child = type('Subtype', (module.NegativeCommitReservation,), {})
        with patch.dict(sys.modules, {'mylar.publication_negative_phase': module}):
            with self.assertRaises(new.guard.Unavailable):
                self.prep().consume(child())

    def test_exact_dispatch_keeps_owned_phase_result_not_boolean(self):
        prep = self.prep()
        calls = []

        class Reservation:

            def consume_native(self, actual):
                calls.append(actual)
                return {'negative_fence_retained': True, 'operation_verified': False}
        module = types.ModuleType('mylar.publication_negative_phase')
        module.__file__ = '/app/mylar3/mylar/publication_negative_phase.py'
        module.NegativeCommitReservation = Reservation
        with patch.dict(sys.modules, {'mylar.publication_negative_phase': module}):
            result = prep.consume(Reservation())
        self.assertEqual(calls, [prep])
        self.assertFalse(result['operation_verified'])

class BatchConsumeDispatchTests(unittest.TestCase):

    def prep(self):
        return new.NativeNegativePreparation.__new__(new.NativeNegativePreparation)

    def test_exact_batch_dispatch_same_original_preparation(self):
        prep = self.prep()
        calls = []

        class Reservation:

            def consume_native(self, actual):
                calls.append(actual)
                return {'marker_retained': True, 'publication_acceptance': False}
        module = types.ModuleType('mylar.publication_negative_batch_transition')
        module.__file__ = '/app/mylar3/mylar/publication_negative_batch_transition.py'
        module.NegativeBatchReservation = Reservation
        with patch.dict(sys.modules, {'mylar.publication_negative_batch_transition': module}):
            ack = prep.consume(Reservation())
        self.assertEqual(calls, [prep])
        self.assertFalse(ack['publication_acceptance'])

    def test_batch_subclass_not_allowed(self):
        module = types.ModuleType('mylar.publication_negative_batch_transition')
        module.__file__ = '/app/mylar3/mylar/publication_negative_batch_transition.py'
        module.NegativeBatchReservation = type('Batch', (), {})
        with patch.dict(sys.modules, {'mylar.publication_negative_batch_transition': module}):
            with self.assertRaises(new.guard.Unavailable):
                self.prep().consume(type('Child', (module.NegativeBatchReservation,), {})())

    def test_batch_wrong_module_path_held(self):
        module = types.ModuleType('mylar.publication_negative_batch_transition')
        module.__file__ = '/tmp/foreign.py'
        module.NegativeBatchReservation = type('Batch', (), {})
        with patch.dict(sys.modules, {'mylar.publication_negative_batch_transition': module}):
            with self.assertRaises(new.guard.Unavailable):
                self.prep().consume(module.NegativeBatchReservation())
if __name__ == '__main__':
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(old), unittest.defaultTestLoader.loadTestsFromTestCase(ConsumeDispatchTests), unittest.defaultTestLoader.loadTestsFromTestCase(BatchConsumeDispatchTests)])
    result = unittest.TextTestRunner().run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
