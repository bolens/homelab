"""Native producer fixtures: source ownership, lookup policy and recovery admission."""
from contextlib import contextmanager
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import tagger_service
import tagger_adapter
import tagger_handoff
from tagger_lookup import LookupResult
from tagger_cli import TagResult
from tagger_archive import snapshot


class ServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'comic.cbz'
        with zipfile.ZipFile(self.source,'w') as archive:archive.writestr('001.png',b'page')
        self.before=self.source.read_bytes();self.cache=self.root/'cache';self.cache.mkdir(mode=0o700)
        self.publisher=tagger_adapter.Publisher(self.root/'journal')
        self.locked=False;self.lookups=0
        @contextmanager
        def coordinate():
            self.assertFalse(self.locked);self.locked=True
            try:yield
            finally:self.locked=False
        def lookup(**kwargs):
            self.assertTrue(self.locked);self.lookups+=1
            self.assertEqual((kwargs['issueid'],kwargs['volumeid']),('123','456'))
            return LookupResult('ok',{'series':'Fixture Annual','issue':'1'})
        self.service=tagger_service.Service(self.publisher,self.cache,lookup,tagger_handoff,coordinate)
        def save(path,metadata,**kwargs):
            self.assertTrue(self.locked)
            with zipfile.ZipFile(path,'a') as archive:
                archive.writestr('ComicInfo.xml','<ComicInfo><Series>Fixture Annual</Series><Number>1</Number></ComicInfo>')
            return TagResult('saved')
        self.patch=patch.object(tagger_adapter,'save',side_effect=save);self.patch.start();self.addCleanup(self.patch.stop)

    def tag(self,**kwargs):return self.service.tag(self.source,issueid='123',volumeid='456',**kwargs)

    def test_manual_publishes_verified_result_under_owner(self):
        result=self.tag(manualmeta=True,volume='1',reading_order=[('Arc',2)])
        self.assertIsInstance(result,tagger_handoff.Published);self.assertTrue(result.valid_for(self.source))
        self.assertEqual(result.metadata,'added');self.assertEqual(self.lookups,1)
        self.assertIn(b'<StoryArcNumber>2</StoryArcNumber>',snapshot(self.source).xml)

    def test_automatic_returns_disposable_path_and_preserves_source(self):
        result=self.tag()
        self.assertIs(type(result),str);self.assertNotEqual(result,'fail')
        output=Path(result);self.assertEqual(output.parent.parent,self.cache)
        self.assertEqual(output.name,self.source.name);self.assertTrue(snapshot(output).xml)
        self.assertEqual(self.source.read_bytes(),self.before)
        self.assertEqual(tagger_handoff.automatic(result),result)

    def test_no_overwrite_avoids_lookup_and_cli(self):
        self.assertEqual(self.tag(manualmeta=True).state,'committed')
        before=self.source.read_bytes()
        with patch.object(tagger_adapter,'save',side_effect=AssertionError('No overwrite')):
            self.assertEqual(self.tag(manualmeta=True,volume='9').state,'unchanged')
            result=self.tag()
        self.assertEqual(self.lookups,1);self.assertEqual(self.source.read_bytes(),before)
        self.assertEqual(Path(result).read_bytes(),before)

    def test_future_modern_tag_adds_reader_labels_and_publisher_collection(self):
        self.service.lookup = lambda **kwargs: LookupResult('ok', {
            'series':'Fixture Annual', 'issue':'1', 'publisher':'DC',
            'characters':['Batman'], 'teams':['Justice League']})
        self.assertEqual(self.tag(manualmeta=True).state, 'committed')
        xml = snapshot(self.source).xml
        self.assertIn(b'<Tags>Character: Batman, Team: Justice League</Tags>', xml)
        self.assertIn(b'<SeriesGroup>Publisher: DC</SeriesGroup>', xml)

    def test_unsupported_modes_do_not_lookup_or_change_source(self):
        for options in ({'enabled':False},{'comicrack':False},{'comicbooklover':True},{'conversion_only':True}):
            result=self.tag(**options);self.assertEqual(result,'fail');self.assertEqual(result.state,'unsupported')
        self.assertEqual(self.lookups,0);self.assertEqual(self.source.read_bytes(),self.before)

    def test_failed_lookup_preserves_source_and_reports_timeout(self):
        self.service.lookup=lambda **kwargs:LookupResult('timed_out')
        result=self.tag();self.assertEqual(result,'fail');self.assertEqual(result.state,'timed_out')
        self.assertEqual(self.source.read_bytes(),self.before);self.assertEqual(list(self.cache.iterdir()),[])

    def test_bad_journal_blocks_lookup_and_publication(self):
        self.publisher.receipt('a'*32).write_text('invalid')
        result=self.tag();self.assertEqual(result.state,'conflict');self.assertEqual(self.lookups,0)
        self.assertEqual(self.source.read_bytes(),self.before)

    def test_corrupt_archive_returns_failure_without_lookup_or_source_change(self):
        corrupted=self.source.read_bytes().replace(b'page',b'bad!')
        self.source.write_bytes(corrupted)
        for manual in (False,True):
            result=self.tag(manualmeta=manual)
            self.assertEqual(result.state,'failed')
            self.assertEqual(self.source.read_bytes(),corrupted)
        self.assertEqual(self.lookups,0)

    def test_backend_choice_never_falls_back_after_modern_failure(self):
        calls=[]
        def legacy():calls.append('legacy');return 'legacy'
        def modern():calls.append('modern');return 'fail'
        self.assertEqual(tagger_service.select('modern',legacy,modern),'fail')
        self.assertEqual(calls,['modern'])
        self.assertEqual(tagger_service.select('legacy',legacy,modern),'legacy')
        with self.assertRaises(ValueError):tagger_service.select('unknown',legacy,modern)


if __name__=='__main__':unittest.main()
