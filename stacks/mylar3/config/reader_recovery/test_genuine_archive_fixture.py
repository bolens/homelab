"""Input preparation tests; these deliberately establish no runtime admission."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import sys
sys.path.insert(0,str(Path(__file__).parent))
import genuine_archive_fixture as fixture


class Tests(unittest.TestCase):
    def test_real_pure_classifier_and_independent_member_preservation(self):
        evidence = fixture.verify_inputs(fixture.archive(), fixture.archive(malformed=True),
                                         fixture.archive(unrelated=True))
        self.assertEqual(evidence['reason'], 'zip32-one-empty-directory-missing-slash')
        self.assertEqual(evidence['inventory']['pages'], [f'Pages/page{i:02}.png' for i in range(1, 4)])
        with zipfile.ZipFile(io.BytesIO(fixture.archive())) as stream:
            self.assertIsNone(stream.testzip())
            for name in evidence['inventory']['pages']:
                self.assertTrue(stream.read(name).startswith(b'\x89PNG\r\n\x1a\n'))

    def test_deterministic_exclusive_private_bundle_and_false_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'new-inputs'
            result = fixture.build(root)
            self.assertEqual(json.loads((root / 'fixture.json').read_bytes()), result)
            for name, facts in result['files'].items():
                raw = (root / name).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), facts['sha256'])
                self.assertEqual(len(raw), facts['bytes'])
                self.assertEqual((root / name).stat().st_mode & 0o777, 0o600)
            for flag in ('runtime_acceptance', 'birth_verified', 'reader_preservation_verified',
                         'publication_acceptance', 'rollback_runtime_verified'):
                self.assertIs(result[flag], False)
            before = (root / 'fixture.json').read_bytes()
            with self.assertRaises(FileExistsError):
                fixture.build(root)
            self.assertEqual((root / 'fixture.json').read_bytes(), before)

    def test_symlink_ancestor_refused_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'actual').mkdir()
            (root / 'alias').symlink_to(root / 'actual', target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'fixture-output-canonical'):
                fixture.build(root / 'alias' / 'new')
            self.assertEqual(list((root / 'actual').iterdir()), [])

    def test_wrong_payload_cannot_be_reported_preserved(self):
        with self.assertRaisesRegex(ValueError, 'fixture-payload-or-metadata-differ'):
            fixture.verify_inputs(fixture.archive(unrelated=True), fixture.archive(malformed=True),
                                  fixture.archive(unrelated=True))

class PlatformTests(unittest.TestCase):
    def test_actual_local_exchange_is_only_platform_evidence_and_cleans_own_files(self):
        import legacy_archive_exchange_probe as platform
        with tempfile.TemporaryDirectory() as directory:
            result = platform.probe_exchange(directory)
            self.assertIn(result['exchange_supported'], (True, False))
            self.assertTrue(result['owned_probe_removed'])
            self.assertEqual(list(Path(directory).iterdir()), [])
            self.assertFalse(result['runtime_acceptance'])
            self.assertFalse(result['birth_verified'])
            self.assertFalse(result['terminal_ack_verified'])

    def test_real_cli_refuses_non_nfs_without_creating_probe(self):
        import subprocess
        import sys
        import legacy_archive_exchange_probe as platform
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'library').mkdir()
            (root / 'grandparent').mkdir()
            try:
                platform.mount_identity(root)
            except platform.Held:
                pass
            else:
                self.fail('This host-only control requires local scratch; use the mandatory NFS probe separately')
            command = [sys.executable, '-B', str(Path(platform.__file__)),
                       '--disposable-grandparent', str(root / 'grandparent'),
                       '--library', str(root / 'library'), '--protected-root', str(root / 'library')]
            result = subprocess.run(command, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b'integration-unproved', result.stdout)
            self.assertEqual(list((root / 'grandparent').iterdir()), [])


if __name__ == '__main__':
    unittest.main()
