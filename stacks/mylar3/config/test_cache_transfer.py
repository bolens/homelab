"""Real transfer/extraction fixtures; capacity projection stays fixture-only."""
from pathlib import Path
from types import SimpleNamespace
import unittest
import zipfile
import cache_admission
import verified_transfer as transfer
from test_verified_transfer import TransferTest


class CacheTransfers(unittest.TestCase):
    setUp = TransferTest.setUp
    response = TransferTest.response
    def overbudget(self):
        with (self.root / 'retained-large').open('wb') as stream:
            stream.truncate(21 * cache_admission.GIB)

    def pack(self, name='pack.zip', member='nested/comic.cbz'):
        path = self.root / name
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr(member, self.body)
        return path

    def test_known_length_denied_before_creating_partial(self):
        self.overbudget()
        with self.assertRaises(cache_admission.Held):
            transfer.receive(self.response(), self.final, None, '1')
        self.assertFalse(self.final.exists()); self.assertFalse(self.final.with_suffix('.cbz.part').exists())

    def test_unknown_length_is_checked_before_each_chunk_and_preserves_prefix(self):
        import sys
        sys.modules['mylar'].CONFIG.DDL_CACHE_MAX_GIB = 1
        with (self.root / 'retained').open('wb') as stream: stream.truncate(cache_admission.GIB - 1024 ** 2)
        response = SimpleNamespace(status_code=200, headers={}, iter_content=lambda **_: iter([b'x' * 1024, b'y' * (2 * 1024 ** 2)]))
        with self.assertRaises(cache_admission.Held): transfer.receive(response, self.final, None, '1')
        self.assertEqual(self.final.with_suffix('.cbz.part').read_bytes(), b'x' * 1024)
        self.assertFalse(self.final.exists())

    def test_projected_expansion_denied_before_stage_birth(self):
        source = self.pack(); self.overbudget()
        with self.assertRaises(cache_admission.Held): transfer.unpack('1', source, source.name)
        self.assertTrue(source.is_file()); self.assertFalse(list(self.root.glob('.mylar-unpack-*')))

    def test_same_complete_extraction_is_reused_even_when_cache_already_overbudget(self):
        source = self.pack(); first = transfer.unpack('1', source, source.name)
        target = Path(first['path']); original = {str(p.relative_to(target)): cache_admission.identity(p.lstat()) for p in [target, *target.rglob('*')]}
        self.overbudget(); second = transfer.unpack('1', source, source.name)
        self.assertEqual(first, second)
        self.assertEqual(original, {str(p.relative_to(target)): cache_admission.identity(p.lstat()) for p in [target, *target.rglob('*')]})
        self.assertFalse(list(self.root.glob('pack.recovered-*'))); self.assertFalse(list(self.root.glob('.mylar-unpack-*')))

    def test_different_existing_member_is_retained_without_recovered_copy(self):
        source = self.pack(); answer = transfer.unpack('1', source, source.name); child = Path(answer['path']) / 'nested/comic.cbz'
        child.write_bytes(b'foreign changed original')
        with self.assertRaises(ValueError): transfer.unpack('1', source, source.name)
        self.assertEqual(child.read_bytes(), b'foreign changed original'); self.assertTrue(source.exists())
        self.assertFalse(list(self.root.glob('pack.recovered-*')))

    def test_missing_existing_member_is_review_not_duplicate_extraction(self):
        source = self.pack(); answer = transfer.unpack('1', source, source.name); (Path(answer['path']) / 'nested/comic.cbz').unlink()
        with self.assertRaises(ValueError): transfer.unpack('1', source, source.name)
        self.assertFalse(list(self.root.glob('pack.recovered-*')))

    def test_implicit_directory_headroom_and_noncomic_rejection(self):
        source = self.pack(member='one/two/three/comic.cbz')
        with zipfile.ZipFile(source) as archive:
            files, directories, _ = transfer.zip_inventory(archive)
        self.assertEqual(set(files), {'one/two/three/comic.cbz'}); self.assertEqual(directories, {'', 'one', 'one/two', 'one/two/three'})
        text = self.root / 'text.zip'
        with zipfile.ZipFile(text, 'w') as archive: archive.writestr('readme.txt', 'no comic')
        with self.assertRaises(ValueError): transfer.unpack('1', text, text.name)
        self.assertFalse(text.with_suffix('').exists())

    def test_deep_namespace_refuses_before_allocation(self):
        source = self.pack(member='/'.join(['nested'] * 33) + '/comic.cbz')
        with self.assertRaises(ValueError): transfer.unpack('1', source, source.name)
        self.assertFalse(list(self.root.glob('.mylar-unpack-*')))

    def test_actual_Requests_GetComics_lookup_Remove_and_handoff_preserve_original_row(self):
        import ast
        import os
        import re
        import sys
        import urllib.parse
        from unittest.mock import MagicMock
        import patch_cache_admission as installer
        original=dict(self.database.selectone('SELECT * FROM ddl_info WHERE ID=?',['1']).fetchone())
        source=installer.getcomics((Path(__file__).parent/'test_fixtures/cache_admission/getcomics.py.txt').read_text())
        node=next(n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef) and n.name=='downloadit')
        namespace=dict(os=os,re=re,urllib=urllib,cache_admission=cache_admission,verified_transfer=transfer,
                       mylar=sys.modules['mylar'],db=SimpleNamespace(DBConnection=lambda:self.database),logger=MagicMock(),
                       requests=SimpleNamespace(Session=MagicMock(),exceptions=SimpleNamespace(Timeout=TimeoutError)))
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual-getcomics>','exec'),namespace)
        for mutation in ('remove','handoff'):
            self.database.action('DELETE FROM ddl_info WHERE ID=?',['1']);self.database.upsert('ddl_info',original,{'id':'1'})
            app=sys.modules['mylar'];app.DDL_LOCK=False;app.DDL_QUEUED=[];events=[]
            def lookup(*args,**kwargs):
                events.append(mutation)
                if mutation=='remove':self.database.action('DELETE FROM ddl_info WHERE ID=?',['1'])
                else:self.database.action("UPDATE ddl_info SET status='NZB handoff' WHERE ID=?",['1'])
                response=self.response();response.url='https://fixture.invalid/comic.cbz';return response
            obj=SimpleNamespace(headers={},cookie_receipt=lambda:None,session=SimpleNamespace(get=lookup))
            with self.assertRaises(cache_admission.Held):namespace['downloadit'](obj,'1','https://fixture.invalid/source','https://fixture.invalid/release',issueid='2',remote_filesize=len(self.body))
            self.assertEqual(events,[mutation]);row=self.database.selectone('SELECT * FROM ddl_info WHERE ID=?',['1']).fetchone()
            if mutation=='remove':self.assertIsNone(row)
            else:self.assertEqual(row['status'],'NZB handoff');self.assertIsNone(row['filename'])
            self.assertFalse(app.DDL_LOCK);self.assertFalse(list(self.root.glob('*.part')))

    def test_removed_DDL_during_stream_never_recreates_metadata_or_promotes(self):
        def chunks(**_):
            self.database.action('DELETE FROM ddl_info WHERE ID=?',['1'])
            yield self.body
        response = SimpleNamespace(status_code=200,headers={'Content-Length':str(len(self.body))},iter_content=chunks)
        with self.assertRaises(cache_admission.Held):transfer.receive(response,self.final,None,'1')
        self.assertIsNone(self.database.selectone('SELECT * FROM ddl_info WHERE ID=?',['1']).fetchone())
        self.assertFalse(self.final.exists());self.assertTrue(self.final.with_suffix('.cbz.part').exists())

    def test_NZB_handoff_during_stream_retains_prefix_and_original_handoff(self):
        def chunks(**_):
            yield self.body[:20]
            self.database.action("UPDATE ddl_info SET status='NZB handoff' WHERE ID=?",['1'])
            yield self.body[20:]
        response = SimpleNamespace(status_code=200,headers={'Content-Length':str(len(self.body))},iter_content=chunks)
        with self.assertRaises(cache_admission.Held):transfer.receive(response,self.final,None,'1')
        self.assertEqual(self.database.selectone('SELECT * FROM ddl_info WHERE ID=?',['1']).fetchone()['status'],'NZB handoff')
        self.assertEqual(self.final.with_suffix('.cbz.part').read_bytes(),self.body[:20]);self.assertFalse(self.final.exists())

    def test_removed_DDL_at_final_validation_keeps_archive_without_metadata_skeleton(self):
        from unittest.mock import patch
        actual=transfer.checked
        def removed(path):
            actual(path);self.database.action('DELETE FROM ddl_info WHERE ID=?',['1'])
        with patch.object(transfer,'checked',removed),self.assertRaises(cache_admission.Held):
            transfer.receive(self.response(),self.final,None,'1')
        self.assertIsNone(self.database.selectone('SELECT * FROM ddl_info WHERE ID=?',['1']).fetchone())
        self.assertEqual(self.final.read_bytes(),self.body)

    def test_actual_GetComics_incomplete_existing_extraction_is_nonretry_hold(self):
        import ast
        import patch_cache_admission as installer
        source=self.pack();result=transfer.unpack('1',source,source.name)
        (Path(result['path'])/'nested/comic.cbz').write_bytes(b'changed retained member')
        native=installer.getcomics((Path(__file__).parent/'test_fixtures/cache_admission/getcomics.py.txt').read_text())
        node=next(n for n in ast.walk(ast.parse(native)) if isinstance(n,ast.FunctionDef) and n.name=='zip_zip')
        namespace=dict(verified_transfer=transfer,cache_admission=cache_admission)
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual-getcomics>','exec'),namespace)
        with self.assertRaises(cache_admission.Held):namespace['zip_zip'](None,'1',str(source),source.name)
        self.assertFalse(list(self.root.glob('pack.recovered-*')))

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CacheTransfers)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    raise SystemExit(not result.wasSuccessful())
