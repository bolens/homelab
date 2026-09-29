"""Nested metadata preservation, ambiguity and publication interruption tests."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import metadata_repair as repair
import tagger_adapter as base
import tagger_archive as archive
import tagger_attributes as attributes
from tagger_nfs import Publisher
TOKEN='c'*32
ROOT='<ComicInfo><Series>Fixture</Series><Number>1</Number><Notes>root notes</Notes></ComicInfo>'
NESTED='<ComicInfo><Series>fixture</Series><Number>1.00</Number><Notes>source notes</Notes><Genre>Fantasy</Genre></ComicInfo>'
def fixture(path,nested=NESTED,extra=False):
    with zipfile.ZipFile(path,'w',compression=8) as z:
        z.writestr('001.jpg',b'page'*1024);z.writestr('extra.txt',b'extras')
        z.writestr('ComicInfo.xml',ROOT);z.writestr('original/ComicInfo.xml',nested)
        if extra:z.writestr('original/SourceMetadata.xml',b'existing')
        z.comment=b'archive comment'
    path.chmod(0o640)
class RepairTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'comic.cbz';fixture(self.source)
        self.original=self.source.read_bytes();os.setxattr(self.source,'user.fixture',b'preserved')
        self.attrs=attributes.capture(self.source);self.publisher=Publisher(self.root/'state')
    def test_preservation_and_replay(self):
        before=archive.snapshot(self.source,allow_nested_metadata=True)
        with patch.object(base,'save',side_effect=AssertionError('No tagger invocation')):
            result=self.publisher.tag(self.source,{},token=TOKEN,repair_nested=True,expected_digest=base.fingerprint(self.source))
        self.assertEqual(result.state,'committed');after=archive.snapshot(self.source)
        self.assertEqual(after.members,tuple((n.replace('original/ComicInfo.xml','original/SourceMetadata.xml'),s,h) for n,s,h in before.members))
        self.assertEqual((after.mode,after.uid,after.gid,after.comment),(before.mode,before.uid,before.gid,before.comment))
        self.assertEqual(attributes.capture(self.source),self.attrs)
        xml=repair.metadata.parse(after.xml);self.assertEqual(xml.findtext('Notes'),'root notes');self.assertEqual(xml.findtext('Genre'),'Fantasy')
        with zipfile.ZipFile(self.source) as z:self.assertEqual(z.read('original/SourceMetadata.xml'),NESTED.encode())
        self.assertEqual(self.publisher.recover(TOKEN).state,'committed');self.assertFalse(list(self.root.glob('.mylar-tag-*')))
    def test_default_inspection_remains_strict(self):
        with self.assertRaises(ValueError):archive.snapshot(self.source)
        self.assertEqual(self.publisher.tag(self.source,{},token=TOKEN).state,'failed')
        self.assertEqual(self.source.read_bytes(),self.original)
    def test_identity_conflict_collision_and_invalid_xml(self):
        for nested,extra in ((NESTED.replace('1.00','2.00'),False),(NESTED,True)):
            fixture(self.source,nested,extra);original=self.source.read_bytes()
            with self.assertRaises(ValueError):repair.prepare(self.source,self.root/'output.cbz')
            self.assertEqual(self.source.read_bytes(),original)
        for xml in ('<ComicInfo><Series>Fixture</Series></ComicInfo>','<!DOCTYPE x><ComicInfo/>'):
            with self.assertRaises(ValueError):repair.merge(ROOT.encode(),xml.encode())
    def test_nested_page_indexes_remain_provenance_only(self):
        xml=NESTED.replace('</ComicInfo>','<Pages><Page Image="90"/></Pages></ComicInfo>')
        self.assertIsNone(repair.metadata.parse(repair.merge(ROOT.encode(),xml.encode())).find('Pages'))
    def test_different_web_links_preserve_root_and_do_not_override_identity(self):
        root=ROOT.replace('</ComicInfo>','<Web>https://catalog.example/issue/1</Web></ComicInfo>')
        nested=NESTED.replace('</ComicInfo>','<Web>https://publisher.example/comic/1</Web></ComicInfo>')
        xml=repair.metadata.parse(repair.merge(root.encode(),nested.encode()))
        self.assertEqual(xml.findtext('Web'),'https://catalog.example/issue/1')
    def test_wrong_digest_preserves_source(self):
        result=self.publisher.tag(self.source,{},token=TOKEN,repair_nested=True,expected_digest='0'*64)
        self.assertEqual(result.state,'conflict');self.assertEqual(self.source.read_bytes(),self.original)
    def test_interruption_recovery(self):
        code="""import os,sys
from pathlib import Path
import tagger_adapter as base
from tagger_nfs import Publisher
base._checkpoint=lambda stage: os._exit(71) if stage==sys.argv[2] else None
root=Path(sys.argv[1]);Publisher(root/'state').tag(root/'comic.cbz',{},token='c'*32,repair_nested=True)
"""
        for stage in ('staged','before_exchange','after_displace','after_link','after_unlink','after_exchange'):
            with self.subTest(stage=stage),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);source=root/'comic.cbz';fixture(source);before=source.read_bytes()
                result=subprocess.run([sys.executable,'-c',code,folder,stage],env=dict(os.environ,PYTHONPATH=str(Path(__file__).parent)),timeout=20)
                self.assertEqual(result.returncode,71);state=Publisher(root/'state').recover(TOKEN).state
                self.assertIn(state,('committed','failed'))
                if state=='failed':self.assertEqual(source.read_bytes(),before)
                else:self.assertIsNotNone(archive.snapshot(source).xml)
                self.assertFalse(list(root.glob('.mylar-tag-*')))
if __name__=='__main__':unittest.main()
