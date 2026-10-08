"""Disposable ZIP-byte controls for pure repair routing."""
import copy
import importlib.util
from pathlib import Path
import stat
import struct
import time
import unittest
import zipfile


import sys
import shutil
import tempfile
import publication_archive_repair as dispatch
import test_publication_archive_diagnostics as fixtures
guard = fixtures.guard


class Controls(unittest.TestCase):
    def setUp(self):
        fixtures.Controls.setUp(self)
        self.p = self.source

    def build(self, directory='Folder', size=b''):
        fixtures.Controls.build(self, directory, size)

    produce = fixtures.Controls.witness

    def route(self, raw=None):
        return dispatch.classify(self.p.read_bytes() if raw is None else raw,
                                 guard, time.monotonic() + 10)

    def simple(self, names):
        with zipfile.ZipFile(self.p, 'w') as archive:
            for name, content in names:
                archive.writestr(name, content)

    def assert_review(self, raw=None):
        value = self.route(raw)
        self.assertEqual(value['status'], 'review-needed')
        self.assertFalse(value['repair_performed'])
        self.assertFalse(value['mutation_authority'])
        self.assertFalse(value['publication_acceptance'])
        self.assertTrue(value['requires_review'])
        return value

    def test_exact_candidate_and_full_dispatch_preserve_source(self):
        original = self.p.read_bytes()
        plan = self.route()
        self.assertEqual(plan['status'], 'repair-candidate')
        repaired, evidence = dispatch.dispatch(original, plan, self.produce(),
                                               guard, time.monotonic() + 10)
        self.assertEqual(self.p.read_bytes(), original)
        self.assertEqual(len(repaired), len(original) + 2)
        self.assertTrue(evidence['all_members_crc_verified_before_after'])
        self.assertTrue(evidence['compressed_payloads_and_other_header_bytes_preserved'])
        self.assertFalse(evidence['publication_acceptance'])
        self.assertEqual(self.route(repaired)['status'], 'verified-no-repair')

    def test_ordinary_zip_needs_no_repair(self):
        self.simple([('page01.png', b'page'), ('sidecar.txt', b'sidecar')])
        original = self.p.read_bytes()
        value = self.route()
        self.assertEqual(value['status'], 'verified-no-repair')
        self.assertTrue(value['all_members_crc_verified'])
        self.assertEqual(self.p.read_bytes(), original)

    def test_bad_crc_is_not_repaired(self):
        self.simple([('page.png', b'PAGECONTENT')])
        raw = self.p.read_bytes().replace(b'PAGECONTENT', b'BROKENBYTES')
        self.assertEqual(self.assert_review(raw)['reason'], 'zip-integrity-or-structure-failure')

    def test_truncated_zip_is_not_repaired(self):
        self.assert_review(self.p.read_bytes()[:-11])

    def test_encrypted_zip_flags_are_not_repaired(self):
        self.simple([('page.png', b'page')])
        raw = bytearray(self.p.read_bytes())
        struct.pack_into('<H', raw, 6, 1)
        central = raw.index(b'PK\x01\x02')
        struct.pack_into('<H', raw, central + 8, 1)
        self.assert_review(bytes(raw))

    def test_traversal_and_noncanonical_names_are_not_sanitized(self):
        for name in ('../page.png', '/page.png', './page.png', 'a//page.png', 'a\\page.png'):
            with self.subTest(name=name):
                self.simple([(name, b'page')])
                self.assert_review()

    def test_duplicate_and_file_parent_collision_are_not_discarded(self):
        for names in ([('page.png', b'a'), ('page.png', b'b')],
                      [('Folder', b'file'), ('Folder/page.png', b'page')]):
            self.simple(names)
            self.assert_review()

    def test_case_and_metadata_aliases_are_not_repaired(self):
        self.simple([('page.png', b'page'), ('comicinfo.xml', b'<ComicInfo/>')])
        self.assert_review()
        self.simple([('page.png', b'page'), ('ComicInfo.xml', b'<ComicInfo/>'),
                     ('ComicBookInfo.json', b'{"ComicBookInfo/1.0":{}}')])
        self.assert_review()

    def test_nonempty_directory_is_not_repaired(self):
        self.build(size=b'not empty')
        self.assert_review()

    def test_multiple_directory_defects_are_not_repaired(self):
        with zipfile.ZipFile(self.p, 'a') as archive:
            entry = zipfile.ZipInfo('Second')
            entry.create_system = 3
            entry.external_attr = ((stat.S_IFDIR | 0o755) << 16) | 0x10
            archive.writestr(entry, b'')
        self.assertEqual(self.assert_review()['reason'], 'multiple-directory-spelling-defects')

    def test_rar_crc_error_cannot_grant_repair_or_compatibility(self):
        value = self.route(b'Rar!\x1a\x07\x01\x00truncated')
        self.assertEqual(value['status'], 'decoder-verification-required')
        self.assertFalse(value['compatibility_verified'])
        self.assertFalse(value['repair_performed'])
        self.assertFalse(value['publication_acceptance'])

    def test_pdf_routes_to_conversion_without_corruption_claim(self):
        value = self.route(b'%PDF-1.7\nfixture')
        self.assertEqual(value['status'], 'conversion-required')
        self.assertFalse(value['repair_performed'])

    def test_7z_requires_decoder_verification(self):
        value = self.route(b'7z\xbc\xaf\x27\x1cfixture')
        self.assertEqual(value['status'], 'decoder-verification-required')
        self.assertFalse(value['compatibility_verified'])

    def test_symlink_member_is_held(self):
        self.simple([('page.png', b'page')])
        with zipfile.ZipFile(self.p, 'a') as archive:
            info = zipfile.ZipInfo('link')
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, b'page.png')
        self.assertEqual(self.assert_review()['reason'], 'linked-or-special-member')

    def test_directory_file_alias_is_held(self):
        self.simple([('Folder/', b''), ('Folder', b'file'), ('page.png', b'page')])
        self.assertEqual(self.assert_review()['reason'], 'duplicate-or-directory-file-collision')

    def test_boolean_integer_plan_alias_is_held(self):
        raw, plan, witness = self.p.read_bytes(), self.route(), self.produce()
        plan['all_members_crc_verified'] = 1
        with self.assertRaises(ValueError):
            dispatch.dispatch(raw, plan, witness, guard, time.monotonic() + 10)

    def test_package_relative_imports_preserve_classification(self):
        temporary = tempfile.TemporaryDirectory(prefix='archive-package-fixture-')
        self.addCleanup(temporary.cleanup)
        package_root = Path(temporary.name)
        (package_root / '__init__.py').write_text('')
        for filename in ('publication_archive_layout.py', 'publication_archive_derivative.py',
                         'publication_archive_repair.py'):
            shutil.copyfile(Path(__file__).with_name(filename), package_root / filename)
        name = 'archive_repair_package_fixture'
        spec = importlib.util.spec_from_file_location(name, package_root / '__init__.py',
                                                     submodule_search_locations=[str(package_root)])
        package = importlib.util.module_from_spec(spec)
        sys.modules[name] = package
        self.addCleanup(lambda: [sys.modules.pop(key, None) for key in list(sys.modules)
                                 if key == name or key.startswith(name + '.')])
        spec.loader.exec_module(package)
        packaged = importlib.import_module(name + '.publication_archive_repair')
        self.assertEqual(packaged.classify(self.p.read_bytes(), guard,
                                          time.monotonic() + 10), self.route())

    def test_unknown_format_is_held(self):
        self.assertEqual(self.assert_review(b'unknown')['reason'], 'unsupported-format')

    def test_expired_deadline_holds(self):
        value = dispatch.classify(self.p.read_bytes(), guard, time.monotonic() - 1)
        self.assertEqual(value['reason'], 'verification-deadline')

    def test_rewritten_plan_and_witness_cannot_dispatch(self):
        raw, plan, witness = self.p.read_bytes(), self.route(), self.produce()
        wrong = copy.deepcopy(plan)
        wrong['inventory']['pages'].append('invented.png')
        with self.assertRaises(ValueError):
            dispatch.dispatch(raw, wrong, witness, guard, time.monotonic() + 10)
        wrong = copy.deepcopy(witness)
        wrong['native_grant'] = True
        with self.assertRaises(ValueError):
            dispatch.dispatch(raw, plan, wrong, guard, time.monotonic() + 10)

    def test_changed_source_cannot_dispatch(self):
        raw, plan, witness = self.p.read_bytes(), self.route(), self.produce()
        with self.assertRaises(ValueError):
            dispatch.dispatch(raw + b'x', plan, witness, guard, time.monotonic() + 10)


if __name__ == '__main__':
    unittest.main()
