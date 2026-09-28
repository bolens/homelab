"""Archive reconciliation preserves originals and rejects unverified contents."""

import hashlib
import os
from pathlib import Path
import shutil
import stat
import struct
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

import tagger_archive as subject
from tagger_metadata import parse


class ArchiveTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original = self.root / 'original.cbz'
        self.tagged = self.root / 'tagged.cbz'
        self.output = self.root / 'verified.cbz'

    def fixture(self, path, xml=None, page=b'page bytes', sidecar=b'credits', comment=b'CBL comment'):
        with zipfile.ZipFile(path, 'w') as archive:
            info = zipfile.ZipInfo('001.png', date_time=(2020, 1, 2, 3, 4, 6))
            info.external_attr = (stat.S_IFREG | 0o640) << 16
            info.comment = b'page comment'
            archive.writestr(info, page)
            archive.writestr('extras/credits.txt', sidecar)
            if xml is not None:
                archive.writestr('ComicInfo.xml', xml)
            archive.comment = comment
        path.chmod(0o640)

    def pair(self, old=None):
        self.fixture(self.original, old)
        self.fixture(self.tagged, b'<ComicInfo><Series>New</Series><Number>1</Number></ComicInfo>')
        return hashlib.sha256(self.original.read_bytes()).hexdigest()

    def unchanged_source(self, digest):
        self.assertEqual(hashlib.sha256(self.original.read_bytes()).hexdigest(), digest)
        self.assertEqual(stat.S_IMODE(self.original.stat().st_mode), 0o640)

    def test_adds_verified_metadata_and_preserves_zip_attributes(self):
        digest = self.pair()
        self.assertEqual(subject.prepare(self.original, self.tagged, self.output), 'added')
        before, after = subject.snapshot(self.original), subject.snapshot(self.output)
        self.assertEqual(before.members, after.members)
        self.assertEqual(before.comment, after.comment)
        self.assertEqual((after.mode, after.uid, after.gid), (before.mode, before.uid, before.gid))
        self.assertEqual(parse(after.xml).findtext('Series'), 'New')
        with zipfile.ZipFile(self.original) as old, zipfile.ZipFile(self.output) as new:
            for field in ('external_attr', 'comment', 'date_time', 'extra', 'compress_type'):
                self.assertEqual(getattr(old.getinfo('001.png'), field), getattr(new.getinfo('001.png'), field))
        self.unchanged_source(digest)

    def test_duplicate_identity_never_creates_verified_output(self):
        digest = self.pair()
        self.fixture(self.tagged, b'<ComicInfo><Number>1</Number><Number>2</Number></ComicInfo>')
        with self.assertRaises(ValueError):
            subject.prepare(self.original, self.tagged, self.output)
        self.unchanged_source(digest)
        self.assertFalse(self.output.exists())

    def test_processing_instruction_is_preserved_and_distinct_from_comment(self):
        old = b'<ComicInfo><?vendor retain?><Series>Old</Series></ComicInfo>'
        digest = self.pair(old)
        self.assertEqual(subject.prepare(self.original, self.tagged, self.output), 'updated')
        self.assertIn(b'<?vendor retain?>', subject.snapshot(self.output).xml)
        self.assertNotEqual(subject.semantic(old), subject.semantic(old.replace(b'<?vendor retain?>', b'<!--vendor retain-->')))
        self.unchanged_source(digest)

    def test_existing_notes_unknown_fields_pages_and_explicit_arcs_survive_in_archive(self):
        old = b'<ComicInfo><Series>Old</Series><Notes>Preserve</Notes><Extension a="b">Extra</Extension><Pages><Page Image="0" Bookmark="Cover"/></Pages><StoryArc>Old</StoryArc><StoryArcNumber>9</StoryArcNumber></ComicInfo>'
        digest = self.pair(old)
        self.assertEqual(subject.prepare(self.original, self.tagged, self.output,
            updates={'Volume':'1','StoryArc':'First,Second','StoryArcNumber':'1,2'}, replace_fields=('Series',)), 'updated')
        root = parse(subject.snapshot(self.output).xml)
        expected = {'Series':'New','Notes':'Preserve','Extension':'Extra','Volume':'1',
                    'StoryArc':'First,Second','StoryArcNumber':'1,2','Number':'1'}
        self.assertEqual({node.tag:node.text for node in root if node.tag!='Pages'}, expected)
        self.assertEqual(root.find('Extension').attrib, {'a':'b'})
        self.assertEqual(root.find('Pages/Page').attrib, {'Image':'0','Bookmark':'Cover'})
        self.unchanged_source(digest)

    def test_unchanged_metadata_does_not_create_output(self):
        old = b'<ComicInfo><Number>1</Number><Series>Old</Series><Notes>Keep</Notes></ComicInfo>'
        digest = self.pair(old)
        self.assertEqual(subject.prepare(self.original, self.tagged, self.output), 'unchanged')
        self.assertFalse(self.output.exists())
        self.unchanged_source(digest)

    def test_repeated_reconciliation_is_unchanged(self):
        self.pair()
        subject.prepare(self.original, self.tagged, self.output)
        second = self.root/'second.cbz'
        self.assertEqual(subject.prepare(self.output, self.tagged, second), 'unchanged')
        self.assertFalse(second.exists())

    def test_page_sidecar_comment_or_member_changes_are_rejected(self):
        digest = self.pair()
        for changed in ({'page':b'changed'}, {'sidecar':b'changed'}, {'comment':b'changed'}):
            with self.subTest(changed=changed):
                self.fixture(self.tagged, b'<ComicInfo><Series>New</Series></ComicInfo>', **changed)
                with self.assertRaises(ValueError):subject.prepare(self.original, self.tagged, self.output)
                self.assertFalse(self.output.exists())
                self.unchanged_source(digest)
        self.pair()
        with zipfile.ZipFile(self.tagged, 'a') as archive:archive.writestr('extra.txt', b'extra')
        with self.assertRaises(ValueError):subject.prepare(self.original, self.tagged, self.output)

    def test_missing_empty_and_pages_only_metadata_are_rejected(self):
        digest = self.pair()
        for xml in (None, b'<ComicInfo/>', b'<ComicInfo><Pages><Page Image="0"/></Pages></ComicInfo>'):
            self.fixture(self.tagged, xml)
            with self.assertRaises(ValueError):subject.prepare(self.original, self.tagged, self.output)
            self.assertFalse(self.output.exists())
            self.unchanged_source(digest)

    def test_malformed_and_oversized_xml_are_rejected(self):
        self.pair()
        for xml in (b'bad', b'<!DOCTYPE ComicInfo><ComicInfo/>', b'x'*(subject.MAX_XML+1)):
            self.fixture(self.tagged, xml)
            with self.assertRaises(ValueError):subject.prepare(self.original, self.tagged, self.output)

    def test_duplicate_unsafe_and_ambiguous_metadata_members_are_rejected(self):
        for name in ('001.png', '../page.png', '/page.png', 'a/./page.png', 'a//page.png', 'a\\page.png', 'C:page.png', 'comicinfo.xml', 'nested/ComicInfo.xml'):
            with self.subTest(name=name):
                self.pair()
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', UserWarning)
                    with zipfile.ZipFile(self.tagged, 'a') as archive:archive.writestr(name, b'x')
                with self.assertRaises(ValueError):subject.snapshot(self.tagged)

    def test_zip_symlink_is_rejected(self):
        self.pair()
        info = zipfile.ZipInfo('link.png')
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(self.tagged, 'a') as archive:archive.writestr(info, b'elsewhere')
        with self.assertRaises(ValueError):subject.snapshot(self.tagged)

    def test_nul_truncated_member_name_is_rejected(self):
        with zipfile.ZipFile(self.tagged,'w') as archive:archive.writestr('001.pngXXXXX',b'page')
        self.tagged.write_bytes(self.tagged.read_bytes().replace(b'001.pngXXXXX',b'001.png\0evil'))
        with self.assertRaises(ValueError):subject.snapshot(self.tagged)

    def test_member_and_total_limits(self):
        self.pair()
        for name, limit in (('MAX_MEMBERS',1),('MAX_MEMBER',1),('MAX_UNPACKED',1)):
            with self.subTest(limit=name), patch.object(subject,name,limit):
                with self.assertRaises(ValueError):subject.snapshot(self.tagged)

    def test_bad_crc_and_truncated_archive_are_rejected(self):
        self.pair()
        data = self.tagged.read_bytes()
        self.tagged.write_bytes(data.replace(b'page bytes', b'bad! bytes', 1))
        with self.assertRaises((ValueError, zipfile.BadZipFile)):subject.snapshot(self.tagged)
        self.tagged.write_bytes(data[:-40])
        with self.assertRaises((ValueError, zipfile.BadZipFile)):subject.snapshot(self.tagged)

    def test_directory_allocation_is_bounded_before_zipfile_parses(self):
        self.pair()
        data = bytearray(self.tagged.read_bytes())
        offset = data.rfind(b'PK\x05\x06')
        struct.pack_into('<L', data, offset+12, subject.MAX_DIRECTORY+1)
        self.tagged.write_bytes(data)
        with patch.object(subject.zipfile, 'ZipFile', side_effect=AssertionError('Unbounded allocation')):
            with self.assertRaises(ValueError):subject.snapshot(self.tagged)

    def test_zip64_locator_outside_maximum_comment_tail_is_rejected(self):
        self.pair()
        data = self.tagged.read_bytes()
        offset = data.rfind(b'PK\x05\x06')
        footer = bytearray(data[offset:offset+22])
        struct.pack_into('<H', footer, 20, 65535)
        record = struct.pack('<4sQ2H2L4Q', b'PK\x06\x06',44,45,45,0,0,3,3,16*1024**2,0)
        locator = struct.pack('<4sLQL', b'PK\x06\x07',0,offset,1)
        self.tagged.write_bytes(data[:offset] + record + locator + footer + b'x'*65535)
        with patch.object(subject.zipfile, 'ZipFile', side_effect=AssertionError('Unbounded allocation')):
            with self.assertRaises(ValueError):subject.snapshot(self.tagged)

    def test_maximum_comment_without_zip64_remains_supported(self):
        self.pair()
        with zipfile.ZipFile(self.tagged,'a') as archive:archive.comment=b'x'*65535
        self.assertEqual(subject.snapshot(self.tagged).comment,b'x'*65535)

    def test_archive_without_pages_is_rejected(self):
        with zipfile.ZipFile(self.tagged,'w') as archive:archive.writestr('credits.txt',b'text')
        with self.assertRaises(ValueError):subject.snapshot(self.tagged)

    def test_existing_output_symlinks_and_fifo_are_rejected_without_mutation(self):
        digest = self.pair()
        self.output.write_bytes(b'existing')
        with self.assertRaises(FileExistsError):subject.prepare(self.original, self.tagged, self.output)
        self.assertEqual(self.output.read_bytes(), b'existing')
        link = self.root/'link.cbz';link.symlink_to(self.original)
        with self.assertRaises(OSError):subject.snapshot(link)
        fifo = self.root/'fifo.cbz';os.mkfifo(fifo)
        with self.assertRaises(ValueError):subject.snapshot(fifo)
        self.unchanged_source(digest)

    def test_source_replacement_during_tagged_verification_is_rejected(self):
        self.pair()
        snapshot = subject.snapshot
        def race(path):
            result = snapshot(path)
            if path == self.tagged:
                replacement=self.root/'replacement.cbz';shutil.copy2(self.original,replacement)
                os.replace(replacement,self.original)
            return result
        with patch.object(subject,'snapshot',race):
            with self.assertRaises(ValueError):subject.prepare(self.original,self.tagged,self.output)
        self.assertFalse(self.output.exists())

    def test_output_failure_removes_only_new_staging_and_retains_original(self):
        digest = self.pair()
        with patch.object(subject.os, 'fsync', side_effect=OSError('No space left')):
            with self.assertRaises(OSError):subject.prepare(self.original,self.tagged,self.output)
        self.assertFalse(self.output.exists())
        self.unchanged_source(digest)


if __name__ == '__main__':
    unittest.main()
