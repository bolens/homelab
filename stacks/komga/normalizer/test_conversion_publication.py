"""Current local ownership, preserved full archives and one native attempt."""
from contextlib import contextmanager
import base64
import json
import os
from pathlib import Path
import shutil
import struct
import zlib
import types
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import zipfile

import conversion_handoff as handoff
from import_recovery import handoff_read
from publication_guard import Unavailable,evidence
from test_publication_guard import AuthorityFixture


class ConversionPublicationTests(AuthorityFixture,unittest.TestCase):
    def setUp(self):
        super().setUp()
        source=self.source.with_suffix('.cbr');self.source.rename(source);self.source=source
        self.sql('UPDATE issues SET Location=?',(source.name,));self.seed()
        state=self.root/'state';state.mkdir();jobs=state/'jobs';jobs.mkdir()
        cache=self.root/'cache';cache.mkdir();completed=self.root/'completed';completed.mkdir()
        self.worker=SimpleNamespace(state=state,jobs=jobs,roots=[self.library],config={
            'writer_state':str(self.writer.root),'mylar':{'config_dir':str(self.config)},
            'publication_roots':[{'native':str(self.native_root),'worker':str(self.library)}],
            'maintenance':{'ddl_cache':str(cache),'mylar_ddl_cache':'/native-cache','completed':str(completed)}})
        def convert(*args):
            output=Path(args[args.index('--output')+1])
            with zipfile.ZipFile(args[-1]) as incoming,zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as outgoing:
                for item in incoming.infolist():outgoing.writestr(item,incoming.read(item))
        self.worker.reader=Mock();self.worker.reader.books.return_value={}
        self.worker.convert_tool=Mock(side_effect=convert)
        self.client=Mock();self.client.mylar.side_effect=self.api
        self.actual_scope=handoff.scope
        @contextmanager
        def portable(*args,**kwargs):
            with self.actual_scope(*args,**kwargs) as authority:
                authority.tool_root=self.tool
                yield authority
        self.portable=portable

    @contextmanager
    def owned(self):
        with self.writer.hold(),patch('conversion_handoff.current',return_value=self.authority):yield

    def prepare(self):
        with self.owned():return handoff.prepare(self.worker,self.source,{})

    def api(self,command,**kwargs):
        self.assertFalse(getattr(self.writer.local[1],'depth',0))
        if command=='getHealth':return {'workflow':{'valid':True,'owned_conversion':1}}
        path=next((self.worker.state/'conversion-handoffs').glob('*.json'));record,_=handoff_read(path)
        self.assertEqual(record['phase'],'dispatching')
        if command=='commitConvertedArchive':
            request=json.loads(kwargs['request']);self.assertEqual(request,record['request'])
            shutil.copyfile(record['stage'],record['target']);self.source.unlink()
            self.sql('UPDATE issues SET Location=?',(Path(record['target']).name,))
        elif command=='convertedArchiveStatus':self.assertEqual(kwargs['token'],path.stem)
        else:self.fail('Unexpected API '+command)
        request=record['request']
        return dict(version=1,token=path.stem,phase='committed',source=request['source'],
            destination=str(Path(request['source']).with_name(request['target'])),sha256=request['output_sha256'],
            inventory_sha256=request['inventory_sha256'],witness='a'*64)

    def dispatch(self):
        with patch('conversion_handoff.api',side_effect=lambda worker,command,**kwargs:self.client.mylar(command,**kwargs)),patch('conversion_handoff.scope',self.portable):
            return handoff.dispatch(self.worker)

    @unittest.skipUnless((Path(os.environ.get('ARCHIVING_UTILS_ROOT','/opt/archiving-utils'))/'bin/archiving-utils').is_file(),
                         'Pinned offline converter required for real RAR worker preparation')
    def test_real_rar_worker_converter_prepares_full_identical_inventory(self):
        from normalize import Normalizer
        tool=Path(os.environ.get('ARCHIVING_UTILS_ROOT','/opt/archiving-utils'))
        name=b'01.png';data=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j9ZkAAAAASUVORK5CYII=')
        def header(kind,flags,body):
            raw=struct.pack('<BHH',kind,flags,7+len(body))+body
            return struct.pack('<H',zlib.crc32(raw)&0xffff)+raw
        self.source.write_bytes(b'Rar!\x1a\x07\x00'+header(0x73,0,bytes(6))+
            header(0x74,0x8000,struct.pack('<IIBIIBBHI',len(data),len(data),3,zlib.crc32(data),0,20,0x30,len(name),0o100644)+name)+data+header(0x7b,0,b''))
        self.tool=tool;self.authority.tool_root=tool;self.seed()
        self.worker.tool=str(tool/'bin/archiving-utils')
        (self.worker.state/'tmp').mkdir();(self.worker.state/'empty-config').mkdir()
        self.worker.convert_tool=types.MethodType(Normalizer.convert_tool,self.worker)
        path=self.prepare();record,_=handoff_read(path)
        source=evidence.inventory(self.source,tool_root=tool)
        output=evidence.inventory(Path(record['stage']),tool_root=tool)
        self.assertEqual(handoff.inventory_digest(source),handoff.inventory_digest(output))
        self.assertNotEqual(source['source_sha256'],output['source_sha256']);self.assertTrue(self.source.exists())

    def test_registered_preparation_retains_source_original_and_exact_shared_stage(self):
        before=self.source.read_bytes();path=self.prepare();record,_=handoff_read(path)
        self.assertEqual(record['phase'],'prepared');self.assertEqual(self.source.read_bytes(),before)
        self.assertEqual(Path(record['original']).read_bytes(),before)
        self.assertEqual(Path(record['prepared']).read_bytes(),Path(record['stage']).read_bytes())
        self.assertEqual(Path(record['stage']).stat().st_mode&0o777,0o600)
        self.client.mylar.assert_not_called()
        with self.owned():self.assertEqual(handoff.prepare(self.worker,self.source,{}),path)

    def test_unknown_owned_archived_preparation_and_separate_dispatch(self):
        self.sql("UPDATE issues SET Status='Archived'");self.seed(empty=True)
        path=self.prepare();self.assertEqual(self.dispatch(),1)
        record,_=handoff_read(path);self.assertEqual(record['phase'],'committed')
        self.assertFalse(self.source.exists());self.assertEqual(self.dispatch(),0)

    def test_no_maintenance_configuration_or_handoff_needs_no_client_or_new_directories(self):
        self.worker.config.pop('maintenance')
        with patch('conversion_handoff.api') as api,patch('maintenance.Maintenance') as constructor:
            self.assertEqual(handoff.dispatch(self.worker),0)
        api.assert_not_called();constructor.assert_not_called()
        self.assertFalse((self.worker.state/'conversion-handoffs').exists())

    def test_narrow_client_reads_mylar_config_without_maintenance_lifecycle(self):
        from maintenance import Maintenance
        self.worker.config.pop('maintenance');self.worker.config['mylar']['url']='http://fixture.invalid'
        (self.config/'config.ini').write_text('[General]\napi_key='+('p'*32)+'\n')
        value={'workflow':{'valid':True,'owned_conversion':1}}
        with patch.object(Maintenance,'__init__',side_effect=AssertionError('constructor forbidden')),patch('maintenance.request',return_value={'success':True,'data':value}):
            self.assertEqual(handoff.api(self.worker,'getHealth'),value)
        self.assertFalse((self.worker.state/'maintenance').exists())

    def test_conversion_only_dispatch_uses_no_maintenance_constructor(self):
        path=self.prepare();record,_=handoff_read(path)
        self.worker.config.pop('maintenance')
        # Preserve the explicit existing staging mappings independently of any
        # maintenance lifecycle. Default public spellings match this fixture.
        self.worker.config['conversion']={'ddl_cache':str(self.root/'cache'),'mylar_ddl_cache':'/native-cache'}
        with patch('maintenance.Maintenance') as constructor:
            self.assertEqual(self.dispatch(),1)
        constructor.assert_not_called();self.assertEqual(handoff_read(path)[0]['phase'],'committed')

    def test_lost_commit_response_never_replays_and_reconciles_only_status(self):
        path=self.prepare();actual=self.api
        def lost(command,**kwargs):
            result=actual(command,**kwargs)
            if command=='commitConvertedArchive':raise OSError('lost response after native commit')
            return result
        self.client.mylar.side_effect=lost
        self.assertEqual(self.dispatch(),0);self.assertEqual(handoff_read(path)[0]['phase'],'dispatching')
        self.assertEqual(self.dispatch(),1)
        self.assertEqual(sum(call.args[0]=='commitConvertedArchive' for call in self.client.mylar.call_args_list),1)
        self.assertEqual(sum(call.args[0]=='convertedArchiveStatus' for call in self.client.mylar.call_args_list),1)

    def test_old_protocol_stage_drift_and_foreign_owner_hold_before_attempt(self):
        path=self.prepare();before=path.read_bytes()
        for flag in (None,True,1.0,2):
            self.client.mylar.return_value={'workflow':{'valid':True,'owned_conversion':flag}};self.client.mylar.side_effect=None
            self.assertEqual(self.dispatch(),0);self.assertEqual(path.read_bytes(),before)
        self.client.mylar.side_effect=self.api
        record,_=handoff_read(path);Path(record['stage']).write_bytes(b'changed')
        with self.assertRaises(Unavailable):self.dispatch()
        self.assertTrue(self.source.exists());self.assertEqual(path.read_bytes(),before)

    def test_reader_owner_sidecars_unknown_unowned_and_census_drift_hold(self):
        with self.owned(),self.assertRaises(Unavailable):handoff.prepare(self.worker,self.source,{str(self.source):{'id':'existing'}})
        sidecar=self.source.with_suffix('.nfo');sidecar.write_text('retained')
        with self.owned(),self.assertRaises(Unavailable):handoff.prepare(self.worker,self.source,{})
        sidecar.unlink();self.sql('UPDATE issues SET Location=NULL');self.seed(empty=True)
        with self.owned(),self.assertRaises(Unavailable):handoff.prepare(self.worker,self.source,{})
        self.worker.convert_tool.assert_not_called()

    def test_reader_discovery_after_preparation_holds_attempt_unspent(self):
        path=self.prepare();before=path.read_bytes()
        self.worker.reader.books.return_value={str(self.source):{'id':'new-reader-owner'}}
        with self.assertRaises(Unavailable):self.dispatch()
        self.assertEqual(path.read_bytes(),before);self.assertTrue(self.source.exists())
        self.assertFalse(any(call.args[0]=='commitConvertedArchive' for call in self.client.mylar.call_args_list))

    def test_alias_converter_output_is_held_before_permission_change(self):
        def alias(*args):os.link(self.source,Path(args[args.index('--output')+1]))
        before=self.source.stat().st_mode;self.worker.convert_tool.side_effect=alias
        with self.owned(),self.assertRaises(Unavailable):handoff.prepare(self.worker,self.source,{})
        self.assertEqual(self.source.stat().st_mode,before)

    def test_reader_completion_requires_exact_hash_pages_unique_book_and_ack(self):
        path=self.prepare();self.dispatch();record,_=handoff_read(path);target=record['target']
        book=dict(id='reader-target',media=dict(status='READY',pagesCount=1),fileHash='fresh-hash')
        books={target:book}
        with patch('reader_handoff.queue',return_value=None),patch('naming_worker.reader_hash',return_value='fresh-hash'),self.owned():
            handoff.collect(self.worker,books)
        self.assertEqual(handoff_read(path)[0]['phase'],'committed')
        with patch('reader_handoff.queue',return_value={'acknowledged':True}) as notify,patch('naming_worker.reader_hash',return_value='fresh-hash'):
            for bad in ({target:dict(book,fileHash='stale')},{target:dict(book,media=dict(status='READY',pagesCount=2))},
                        {target:book,'/other/book.cbz':dict(book)}):
                with self.owned():handoff.collect(self.worker,bad)
                self.assertEqual(handoff_read(path)[0]['phase'],'committed')
            with self.owned():handoff.collect(self.worker,books)
            self.assertEqual(notify.call_args.args[2],[dict(source=target,target=target,match={'issueid':'123','comicid':'456'})])
        self.assertEqual(handoff_read(path)[0]['phase'],'done')

    def test_same_page_payload_with_metadata_loss_is_held_before_shared_stage(self):
        with zipfile.ZipFile(self.source,'a') as archive:archive.writestr('ComicInfo.xml','<ComicInfo><Title>Retained</Title></ComicInfo>')
        def drop(*args):
            with zipfile.ZipFile(Path(args[args.index('--output')+1]),'w') as archive:archive.writestr('01.jpg',b'one')
        self.worker.convert_tool.side_effect=drop
        with self.owned(),self.assertRaises(Unavailable):handoff.prepare(self.worker,self.source,{})
        self.assertTrue(self.source.exists());self.assertFalse((Path(self.worker.config['maintenance']['ddl_cache'])/'comic-conversions').exists())

    def test_owned_normalizer_routes_lossless_candidates_through_dedicated_handoff(self):
        from normalize import Normalizer
        self.worker.errors=[];self.worker.rejected={};self.worker.candidates=Mock(return_value=[self.source])
        self.worker.reader_snapshot=(threading.get_ident(),time.monotonic(),evidence.compact({}))
        with patch('publication_guard.current',return_value=self.authority),patch('conversion_handoff.collect') as collect,patch('conversion_handoff.prepare') as prepare,self.writer.hold():
            Normalizer.cycle(self.worker)
        collect.assert_called_once_with(self.worker,{})
        prepare.assert_called_once_with(self.worker,self.source,{})
        self.worker.reader.books.assert_not_called()

    def test_uncertain_wrong_reply_and_changed_target_never_mark_committed(self):
        path=self.prepare();actual=self.api
        def wrong(command,**kwargs):
            value=actual(command,**kwargs)
            if command!='getHealth':value['token']='b'*64
            return value
        self.client.mylar.side_effect=wrong
        with self.assertRaises(Unavailable):self.dispatch()
        self.assertEqual(handoff_read(path)[0]['phase'],'dispatching')
        self.client.mylar.side_effect=actual
        Path(handoff_read(path)[0]['target']).write_bytes(b'changed')
        with self.assertRaises(Unavailable):self.dispatch()
        self.assertEqual(handoff_read(path)[0]['phase'],'dispatching')


if __name__=='__main__':unittest.main()
