"""Actual provider functions with disposable cache, network/crypto-only fixtures."""
import ast
from io import BytesIO
from pathlib import Path
import os
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import cache_admission as guard
import patch_cache_admission as installer
import verified_transfer as transfer
from test_verified_transfer import TransferTest

FIXTURE = Path(__file__).parent / 'test_fixtures/cache_admission'


def function(source, name, namespace):
    node = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<actual-provider>', 'exec'), namespace)
    return namespace[name]


class Providers(unittest.TestCase):
    setUp = TransferTest.setUp
    response = TransferTest.response
    def provider(self, kind):
        app = sys.modules['mylar']
        logger = SimpleNamespace(fdebug=lambda *a: None, warn=lambda *a: None, info=lambda *a: None)
        namespace = dict(os=os, mylar=app, cache_admission=guard, verified_transfer=transfer,
                         db=SimpleNamespace(DBConnection=lambda: self.database), logger=logger)
        method, size, owner = ('mediafire_dl',4096,'id') if kind=='mediafire' else ('pixel_ddl',1024,'self.id')
        source=installer.direct_provider((FIXTURE/(kind+'.py.txt')).read_text(), method, size, owner)
        self.assertEqual(installer.direct_provider(source, method, size, owner),source)
        run=function(source,method,namespace)
        obj=SimpleNamespace(dl_location=str(self.root),id='1',headers={},session=SimpleNamespace(get=lambda *a,**kw:self.response()))
        info={'filename':'fixture.cbz','filesize':len(self.body)}
        return lambda:run(obj,'fixture','1',info,'2') if kind=='mediafire' else run(obj,'fixture',info,'2')

    def test_mediafire_and_pixel_real_complete_downloads(self):
        for kind in ('mediafire','pixeldrain'):
            with self.subTest(kind=kind):
                result=self.provider(kind)(); self.assertTrue(result['success']);self.assertEqual(Path(result['path']).read_bytes(),self.body)

    def test_direct_providers_do_not_swallow_capacity_hold_or_overwrite_originals(self):
        with (self.root/'retained').open('wb') as stream:stream.truncate(21*guard.GIB)
        for kind in ('mediafire','pixeldrain'):
            with self.subTest(kind=kind):
                with self.assertRaises(guard.Held):self.provider(kind)()
        self.assertFalse(list(self.root.glob('*.part')))

    def mega(self, body=None, filename='mega.cbz', mac_ok=True):
        payload=self.body if body is None else body
        source=installer.mega_library((FIXTURE/'mega_library.py.txt').read_text())
        self.assertEqual(installer.mega_library(source),source)
        class Cipher:
            def decrypt(self,b):return b
            def encrypt(self,b):return bytes(16)
        namespace=dict(Path=Path,os=os,requests=SimpleNamespace(get=lambda *a,**kw:SimpleNamespace(raw=BytesIO(payload))),
                       base64_url_decode=lambda a:a,decrypt_attr=lambda a,k:{'n':filename},a32_to_str=lambda a:bytes(16),
                       str_to_a32=lambda a:(0,0,0,0) if mac_ok else (1,0,0,0),
                       Counter=SimpleNamespace(new=lambda *a,**kw:None),AES=SimpleNamespace(new=lambda *a,**kw:Cipher(),MODE_CTR=1,MODE_CBC=2),
                       get_chunks=lambda size:((i,min(4096,size-i)) for i in range(0,size,4096)),logger=SimpleNamespace(info=lambda *a:None))
        run=function(source,'_download_file',namespace)
        obj=SimpleNamespace(_api_request=lambda *a:{'g':'fixture','s':len(payload),'at':''})
        facts=dict(k=(0,0,0,0),iv=(0,0,0,0),meta_mac=(0,0),h='fixture')
        return lambda hook=None:run(obj,'fixture',None,dest_path=str(self.root),file=facts,progress_hook=hook)

    def test_actual_mega_temp_is_in_cache_and_guard_precedes_progress(self):
        seen=[];run=self.mega()
        def hook(value):
            seen.append(value)
            if value['status']=='downloading':
                self.assertEqual(Path(value['tmp_filename']).parent,self.root)
                self.assertEqual(Path(value['tmp_filename']).stat().st_size,value['current'])
        result=run(hook);self.assertEqual(result.read_bytes(),self.body);self.assertTrue(seen);self.assertFalse(list(self.root.glob('megapy_*')))

    def test_mega_denies_before_temp_or_plaintext_birth(self):
        with (self.root/'retained').open('wb') as stream:stream.truncate(21*guard.GIB)
        with self.assertRaises(guard.Held):self.mega()()
        self.assertFalse(list(self.root.glob('megapy_*')));self.assertFalse((self.root/'mega.cbz').exists())

    def test_mega_mac_failure_retains_cache_temp_and_existing_destination(self):
        target=self.root/'mega.cbz';target.write_bytes(b'original')
        with self.assertRaises(ValueError):self.mega(mac_ok=False)()
        self.assertEqual(target.read_bytes(),b'original');temps=list(self.root.glob('megapy_*'));self.assertEqual(len(temps),1);self.assertEqual(temps[0].read_bytes(),self.body)
        with self.assertRaises(FileExistsError):self.mega()()
        self.assertEqual(target.read_bytes(),b'original');self.assertEqual(len(list(self.root.glob('megapy_*'))),2)

    def test_mega_foreign_free_space_loss_refuses_before_next_plaintext_write(self):
        payload=b'x'*8192;calls=[]
        def space(fd):
            calls.append(fd);free=100*guard.GIB if len(calls)<=2 else 5*guard.GIB
            return SimpleNamespace(f_bavail=free,f_frsize=1)
        with patch.object(guard.os,'fstatvfs',side_effect=space):
            with self.assertRaises(guard.Held):self.mega(payload)()
        temps=list(self.root.glob('megapy_*'));self.assertEqual(len(temps),1);self.assertEqual(temps[0].read_bytes(),payload[:4096])

    def owning_provider(self, kind, mutation=None, progress=False):
        from types import MethodType
        import re
        import urllib.parse
        app=sys.modules['mylar'];events=[]
        def change():
            events.append(mutation)
            if mutation=='remove':self.database.action('DELETE FROM ddl_info WHERE ID=?',['1'])
            else:self.database.action("UPDATE ddl_info SET status='NZB handoff' WHERE ID=?",['1'])
        namespace=dict(os=os,Path=Path,re=re,urllib=urllib,mylar=app,cache_admission=guard,verified_transfer=transfer,
                       db=SimpleNamespace(DBConnection=lambda:self.database),helpers=SimpleNamespace(human_size=lambda v:str(v)),
                       logger=SimpleNamespace(fdebug=lambda *a:None,warn=lambda *a:None,info=lambda *a:None))
        obj=type('OriginalProviderFixture',(),{})();obj.dl_location=str(self.root);obj.headers={};obj.wrote_tmp=False
        if kind=='mega':
            source=installer.mega_provider((FIXTURE/'mega.py.txt').read_text())
            def lookup(link):
                if mutation and not progress:change()
                return dict(name='fixture.cbz',size=len(self.body))
            def download(link,dest,filename=None,progress_hook=None):
                def observed(data):
                    if mutation and progress and not events and data['status']=='downloading':change()
                    progress_hook(data)
                return self.mega(filename='fixture.cbz')(observed)
            library=SimpleNamespace(login=lambda:library,get_public_url_info=lookup,download_url=download)
            namespace['Mega']=lambda:library
            obj.testing=MethodType(function(source,'testing',namespace),obj)
            run=function(source,'ddl_download',namespace)
            return lambda:run(obj,'fixture',None,'1','2'),events
        method,chunk,owner=('mediafire_dl',4096,'id') if kind=='mediafire' else ('pixel_ddl',1024,'self.id')
        source=installer.direct_provider((FIXTURE/(kind+'.py.txt')).read_text(),method,chunk,owner)
        calls=[]
        def get(*args,**kwargs):
            calls.append(True)
            if mutation and len(calls)==1:change()
            if kind=='mediafire' and len(calls)==1:
                return SimpleNamespace(headers={'Content-Disposition':'attachment; filename="fixture.cbz"','Content-Length':str(len(self.body))})
            if kind=='pixeldrain' and len(calls)==1:return SimpleNamespace(url='https://fixture.invalid/fixture')
            if kind=='pixeldrain' and len(calls)==2:return SimpleNamespace(status_code=200,json=lambda:dict(name='fixture.cbz',size=len(self.body),availability='available',can_download=True))
            return self.response()
        obj.session=SimpleNamespace(get=get)
        setattr(obj,method,MethodType(function(source,method,namespace),obj))
        run=function(source,'ddl_download',namespace)
        return lambda:run(obj,'https://fixture.invalid/source','1','2'),events

    def test_all_three_actual_provider_entry_paths_preserve_metadata_and_downloads(self):
        for kind in ('mediafire','pixeldrain','mega'):
            with self.subTest(kind=kind):
                run,events=self.owning_provider(kind)
                result=run();self.assertTrue(result['success']);self.assertEqual(Path(result['path']).read_bytes(),self.body)
                self.assertEqual(events,[]);row=self.database.selectone('SELECT * FROM ddl_info WHERE ID=?',['1']).fetchone()
                self.assertEqual(row['status'],'Downloading');self.assertEqual(row['issueid'],'2');self.assertEqual(row['comicid'],'3')
                Path(result['path']).unlink()

    def test_all_three_actual_provider_lookup_Remove_and_handoff_never_recreate_or_change_metadata(self):
        original=dict(self.database.selectone('SELECT * FROM ddl_info WHERE ID=?',['1']).fetchone())
        for kind in ('mediafire','pixeldrain','mega'):
            for mutation in ('remove','handoff'):
                with self.subTest(kind=kind,mutation=mutation):
                    self.database.action('DELETE FROM ddl_info WHERE ID=?',['1']);self.database.upsert('ddl_info',original,{'id':'1'})
                    run,events=self.owning_provider(kind,mutation)
                    with self.assertRaises(guard.Held):run()
                    self.assertEqual(events,[mutation]);row=self.database.selectone('SELECT * FROM ddl_info WHERE ID=?',['1']).fetchone()
                    if mutation=='remove':self.assertIsNone(row)
                    else:
                        self.assertEqual(row['status'],'NZB handoff');self.assertIsNone(row['filename']);self.assertIsNone(row['tmp_filename'])
                    self.assertFalse(list(self.root.glob('*.part')));self.assertFalse(list(self.root.glob('megapy_*')))

    def test_actual_Mega_progress_Remove_and_handoff_keep_plaintext_without_metadata_skeleton(self):
        original=dict(self.database.selectone('SELECT * FROM ddl_info WHERE ID=?',['1']).fetchone())
        for mutation in ('remove','handoff'):
            self.database.action('DELETE FROM ddl_info WHERE ID=?',['1']);self.database.upsert('ddl_info',original,{'id':'1'})
            run,events=self.owning_provider('mega',mutation,progress=True)
            with self.assertRaises(guard.Held):run()
            self.assertEqual(events,[mutation]);row=self.database.selectone('SELECT * FROM ddl_info WHERE ID=?',['1']).fetchone()
            if mutation=='remove':self.assertIsNone(row)
            else:self.assertEqual(row['status'],'NZB handoff');self.assertIsNone(row['tmp_filename'])
            self.assertTrue(list(self.root.glob('megapy_*')))
            self.assertFalse((self.root/'fixture[__2__].cbz').exists())

if __name__=='__main__':
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Providers))
    raise SystemExit(not result.wasSuccessful())
