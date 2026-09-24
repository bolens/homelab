"""Observed formats and metadata changes, without changing tagger behavior."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock
import zipfile
import archive_monitor as archive
import pp_monitor

if len(sys.argv)>1:sys.argv.pop(1)


class ArchiveTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        archive._ACTIVE.clear();archive._RECENT.clear()
        context=patch.dict(sys.modules,{'mylar':SimpleNamespace(DATA_DIR=str(self.root),workflow=SimpleNamespace(emit=Mock()),pp_monitor=pp_monitor)})
        context.start();self.addCleanup(context.stop)

    def test_conversion_identity_is_preserved_and_validated(self):
        row={'name':'Example.cb7','original_format':'CB7','phase':'complete','issueid':'10','comicid':'20'}
        # Use a native supported receipt phase.
        row['phase']=next(iter(archive._PHASES))
        archive.report(json.dumps([row]))
        call=sys.modules['mylar'].workflow.emit.call_args.kwargs
        self.assertEqual((call['issueid'],call['comicid']),('10','20'))
        row['issueid']='../unsafe'
        with self.assertRaises(ValueError):archive.report(json.dumps([row]))

    def comic(self,name,metadata=None):
        path=self.root/name
        with zipfile.ZipFile(path,'w') as z:
            z.writestr('001.jpg',b'page')
            if metadata is not None:z.writestr('ComicInfo.xml',metadata)
        return path

    def run_tagger(self,before,after):
        @archive.tagging
        def tag(filename=None):return str(after)
        self.assertEqual(tag(filename=str(before)),str(after))
        return archive.snapshot()['tagging'][0]

    def test_added_updated_and_unchanged_metadata(self):
        plain=self.comic('plain.cbz');first=self.comic('first.cbz','<ComicInfo/>')
        second=self.comic('second.cbz','<ComicInfo><Title>Corrected</Title></ComicInfo>')
        self.assertEqual(self.run_tagger(plain,first)['metadata'],'Metadata added')
        self.assertEqual(self.run_tagger(first,second)['metadata'],'Metadata updated')
        self.assertEqual(self.run_tagger(first,first)['metadata'],'Metadata unchanged')
        self.assertNotIn('Corrected',json.dumps(archive.snapshot()))

    def test_conversion_and_unknown_original_metadata(self):
        rar=self.root/'original.cbr';rar.write_bytes(b'Rar!\x1a\x07\x00')
        cbz=self.comic('output.cbz','<ComicInfo/>')
        row=self.run_tagger(rar,cbz)
        self.assertEqual(row['original_format'],'CBR (RAR)')
        self.assertEqual(row['output_format'],'CBZ (ZIP)')
        self.assertEqual(row['conversion'],'Converted to CBZ (ZIP)')
        self.assertEqual(row['metadata'],'Present; original metadata not inspected')
        self.assertNotIn(str(self.root),json.dumps(row))

    def test_extension_only_change_is_not_called_conversion(self):
        source=self.comic('wrong.cbr');target=self.comic('right.cbz')
        self.assertEqual(self.run_tagger(source,target)['conversion'],'Renamed to CBZ (ZIP)')

    def test_failed_or_raising_tagger_preserves_native_behavior(self):
        path=self.comic('source.cbz')
        @archive.tagging
        def fail(filename=None):return 'fail'
        self.assertEqual(fail(filename=str(path)),'fail')
        self.assertEqual(archive.snapshot()['tagging'][0]['metadata'],'Tagging failed or incomplete')
        @archive.tagging
        def error(filename=None):raise RuntimeError('private exception')
        with self.assertRaises(RuntimeError):error(filename=str(path))
        self.assertFalse(archive._ACTIVE)
        self.assertNotIn('private exception',json.dumps(archive.snapshot()))

    def test_metadata_read_is_bounded(self):
        huge=self.comic('huge.cbz','x'*262145)
        self.assertEqual(archive.inspect_archive(huge)['metadata'],'unknown')

    def test_normalizer_report_is_bounded_and_private(self):
        row={'name':'Comic.cbt.tar.zst','original_format':'CBT.TAR.ZST','phase':'done'}
        archive.report(json.dumps([row]))
        result=archive.snapshot()['normalizer'][0]
        self.assertEqual(result['metadata'],'Preserved; archive contents verified')
        self.assertEqual(result['conversion'],'Converted and verified')
        self.assertEqual((self.root/'archive-processing.json').stat().st_mode & 0o777,0o600)
        for invalid in [dict(row,name='/private/comic.cbz'),dict(row,name='https://secret'),dict(row,phase='whatever')]:
            with self.assertRaises(ValueError):archive.report(json.dumps([invalid]))
        with self.assertRaises(ValueError):archive.report(json.dumps([row]*51))


if __name__=='__main__':unittest.main()
