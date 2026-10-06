"""Genuine container, catalog, correction and crash controls for owned conversion."""
import ast
import base64
import os
import json
from pathlib import Path
import struct
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
import zipfile
import zlib

import publication_conversion as conversion
import publication_guard as guard
import publication_native as native
import publication_transaction as transaction
import test_publication_rename as naming_fixtures
import test_publication_native as fixtures
from patch_publication_conversion import patched_source


def rar4():
    name,data=b'01.jpg',b'one'
    def header(kind,flags,body):
        raw=struct.pack('<BHH',kind,flags,7+len(body))+body
        return struct.pack('<H',zlib.crc32(raw)&0xffff)+raw
    return (b'Rar!\x1a\x07\x00'+header(0x73,0,bytes(6))
        +header(0x74,0x8000,struct.pack('<IIBIIBBHI',len(data),len(data),3,zlib.crc32(data),0,20,0x30,len(name),0o100644)+name)
        +data+header(0x7b,0,b''))

SEVEN=base64.b64decode('N3q8ryccAANwYwOYDQAAAAAAAABkAAAAAAAAAKP2ZM0AN5uI3lgj///3PEAA'
    'AQQGAAEJDQAHCwEAASMDAQEFXQAAgAAMAwAICgHxhmx6AAAFAREPADAAMQAu'
    'AGoAcABnAAAAFAoBAOmGTeEhVN0BEgoBAOmGTeEhVN0BEwoBANVTTeEhVN0B'
    'FQYBACCApIEAAA==')


class InstallerTests(unittest.TestCase):
    def test_fresh_and_upgrade_whitelist_guards_are_exact(self):
        source="cmd_list=['getVersion',]\nclass Api:\n    def _getVersion(self, **kwargs):\n        pass\n"
        changed=patched_source(source);self.assertEqual(patched_source(changed),changed)
        self.assertIn("'commitConvertedArchive'",changed)
        with self.assertRaises(ValueError):patched_source(changed.replace("cherrypy.request.method != 'POST'","False"))
        with self.assertRaises(ValueError):patched_source("cmd_list=external\nclass Api:\n    def _getVersion(self):pass")

    def test_guarded_handlers_primary_exact_fields_post_and_terminal_review(self):
        source="cmd_list=['getVersion']\nclass Api:\n    def _getVersion(self, **kwargs):\n        pass\n"
        nodes={node.name:node for node in ast.walk(ast.parse(patched_source(source))) if isinstance(node,ast.FunctionDef)}
        app=SimpleNamespace(CONFIG=SimpleNamespace(API_ENABLED=True,API_KEY='p'*32),
            publication_conversion=SimpleNamespace(commit=Mock(return_value={'ok':True}),status=Mock(return_value={'phase':'committed'})),
            publication_native=native)
        request=SimpleNamespace(method='POST');namespace={'mylar':app,'cherrypy':SimpleNamespace(request=request)}
        for name in ('_commitConvertedArchive','_convertedArchiveStatus'):
            exec(compile(ast.Module(body=[nodes[name]],type_ignores=[]),'<actual-conversion-handler>','exec'),namespace)
        obj=SimpleNamespace(apikey='p'*32,apitype='normal',_failureResponse=lambda _: 'denied',_successResponse=lambda value:value)
        with patch.dict(sys.modules,{'mylar':app}):
            for key,apitype in ((None,'normal'),('secondary','sse'),('p'*32,'sse')):
                obj.apikey=key;obj.apitype=apitype
                namespace['_commitConvertedArchive'](obj,request='{}');self.assertEqual(obj.data,'denied')
            obj.apikey='p'*32;obj.apitype='normal'
            for fields in ({},{'request':{}},{'request':'{}','callback':'leak'},{'request':'x'*(2*1024*1024+1)}):
                namespace['_commitConvertedArchive'](obj,**fields);self.assertEqual(obj.data,'denied')
            request.method='GET';namespace['_commitConvertedArchive'](obj,request='{}');self.assertEqual(obj.data,'denied')
            app.publication_conversion.commit.assert_not_called()
            request.method='POST';namespace['_commitConvertedArchive'](obj,request='{}');self.assertEqual(obj.data,{'ok':True})
            app.publication_conversion.commit.side_effect=native.Review('retained review')
            namespace['_commitConvertedArchive'](obj,request='{}');self.assertEqual(obj.data,'denied')
            request.method='GET';namespace['_convertedArchiveStatus'](obj,token='a'*64);self.assertEqual(obj.data,{'phase':'committed'})
            namespace['_convertedArchiveStatus'](obj,token='a'*64,request='unsafe');self.assertEqual(obj.data,'denied')
            app.CONFIG.API_KEY=None;obj.apikey=None
            namespace['_convertedArchiveStatus'](obj,token='a'*64);self.assertEqual(obj.data,'denied')


@unittest.skipUnless((Path(fixtures.fixtures.TOOL_ROOT)/'lib/archive_backend.py').is_file(),
                     'offline native archive verifier required')
class ConversionTests(unittest.TestCase):
    call=fixtures.AdmissionTests.call
    bootstrap=fixtures.AdmissionTests.bootstrap
    prepare=fixtures.AdmissionTests.prepare
    registered=fixtures.AdmissionTests.registered
    connection=naming_fixtures.RenameTests.connection

    def setUp(self):
        naming_fixtures.RenameTests.setUp(self)
        original_admission=self.runtime.admission
        def admission(writer):
            value=original_admission(writer)
            if (writer.root/transaction.NAME).exists():raise guard.Unavailable('Retained native publication intent')
            return value
        self.runtime.admission=admission
        def existing_store(_):
            self.store.existing_only=True
            return self.store
        self.runtime.existing_store=existing_store
        self.mylar.publication_conversion=conversion
        context=patch.dict(sys.modules,{'mylar.publication_conversion':conversion});context.start();self.addCleanup(context.stop)
        self.cache=self.root/'cache';self.cache.mkdir();self.mylar.CONFIG.CACHE_DIR=str(self.cache)
        source=self.source.with_suffix('.cbr');self.source.rename(source);self.source=source
        self.source.write_bytes(rar4())
        with self.connection() as db:db.execute('UPDATE issues SET Location=?,ComicSize=? WHERE IssueID=?',
            (self.source.name,self.source.stat().st_size,self.owner['issueid']))
        self.rebuild()

    def rebuild(self):
        source_hash=guard.file_hash(self.source)[1]
        preliminary=self.cache/'output.cbz'
        with zipfile.ZipFile(preliminary,'w',compression=zipfile.ZIP_DEFLATED) as archive:archive.writestr('01.jpg',b'one')
        output_hash=guard.file_hash(preliminary)[1]
        folder=self.cache/'comic-conversions'/conversion.stage_token(self.source,source_hash,output_hash)
        folder.mkdir(parents=True,exist_ok=True);self.prepared=folder/'prepared.cbz'
        preliminary.replace(self.prepared);self.prepared.chmod(0o600)
        self.target=self.source.with_suffix('.cbz')
        self.request=dict(version=1,source=str(self.source),target=self.target.name,prepared=str(self.prepared),
            source_sha256=source_hash,output_sha256=output_hash,inventory_sha256=conversion.inventory_digest(guard.inventory(self.source)),
            issueid=self.owner['issueid'],comicid=self.owner['parentcomicid'],
            census=guard.registry_snapshot(self.store.path,self.writer.root/'publication-v1.json')[0])

    def test_real_rar_lossless_positive_and_passive_acknowledgement(self):
        before=self.source.read_bytes();answer=conversion.commit(self.request)
        self.assertEqual(answer['phase'],'committed');self.assertFalse(self.source.exists())
        self.assertEqual(conversion.status(answer['token']),answer)
        self.assertFalse(self.writer.fenced(release=True));self.assertFalse((self.writer.root/transaction.NAME).exists())
        original=self.writer.root/'conversion-originals-v1'/answer['token']/'original.cbr'
        self.assertEqual(original.read_bytes(),before);self.assertEqual(original.stat().st_mode&0o777,0o600)
        with self.connection() as db:
            row=db.execute('SELECT Location,Status,ComicSize FROM issues WHERE IssueID=?',(self.owner['issueid'],)).fetchone()
        self.assertEqual(tuple(row),(self.target.name,'Downloaded',self.target.stat().st_size))
        with self.assertRaises(ValueError):conversion.commit(self.request)

    def test_real_7zip_registered_archived_positive(self):
        source=self.source.with_suffix('.cb7');self.source.rename(source);self.source=source;source.write_bytes(SEVEN)
        with self.connection() as db:db.execute("UPDATE issues SET Location=?,Status='Archived',ComicSize=? WHERE IssueID=?",
            (source.name,source.stat().st_size,self.owner['issueid']))
        self.rebuild();registration=self.prepare(census=self.request['census']);self.call('register',token=registration['token']);self.rebuild()
        answer=conversion.commit(self.request);self.assertEqual(conversion.status(answer['token']),answer)
        with self.connection() as db:self.assertEqual(db.execute('SELECT Status FROM issues WHERE IssueID=?',(self.owner['issueid'],)).fetchone()[0],'Archived')

    def test_annual_archived_owner_with_distinct_release_identity(self):
        with self.connection() as db:
            db.execute('ALTER TABLE annuals ADD COLUMN ComicSize INTEGER')
            db.execute('DELETE FROM issues WHERE IssueID=?',(self.owner['issueid'],))
            db.execute('INSERT INTO annuals (IssueID,ComicID,ReleaseComicID,Location,Status,Deleted,ComicSize) VALUES (?,?,?,?,?,?,?)',
                (self.owner['issueid'],self.owner['parentcomicid'],'777',self.source.name,'Archived',0,self.source.stat().st_size))
        self.owner=dict(self.owner,table='annuals',releasecomicid='777');self.rebuild()
        registration=self.prepare(census=self.request['census']);self.call('register',token=registration['token']);self.rebuild()
        answer=conversion.commit(self.request);self.assertEqual(conversion.status(answer['token']),answer)
        with self.connection() as db:
            self.assertEqual(tuple(db.execute('SELECT Status,ReleaseComicID,Location FROM annuals').fetchone()),
                ('Archived','777',self.target.name))

    def test_missing_deleted_catalog_claim_reserves_target_before_intent(self):
        with self.connection() as db:db.execute('INSERT INTO annuals (IssueID,ComicID,ReleaseComicID,Location,Status,Deleted) VALUES (?,?,?,?,?,?)',
            ('444','456','456',self.target.name,'Archived',1))
        with self.assertRaises(guard.Unavailable):conversion.commit(self.request)
        self.assertTrue(self.source.exists());self.assertFalse(self.target.exists())
        self.assertFalse((self.writer.root/transaction.NAME).exists())

    def test_permissions_attributes_and_timestamp_survive(self):
        self.source.chmod(0o640);os.setxattr(self.source,'user.comic-test',b'preserved')
        before=self.source.stat();self.rebuild()
        answer=conversion.commit(self.request);self.assertEqual(conversion.status(answer['token']),answer)
        self.assertEqual(os.getxattr(self.target,'user.comic-test'),b'preserved')
        self.assertEqual(self.target.stat().st_mode&0o777,0o640)
        self.assertEqual(self.target.stat().st_mtime_ns,before.st_mtime_ns)

    def test_target_identity_drift_after_link_holds_source_and_original(self):
        def replace(phase):
            if phase=='linked':
                raw=self.target.read_bytes();self.target.unlink();self.target.write_bytes(raw)
        with self.assertRaises(guard.Unavailable):conversion.commit(self.request,boundary=replace)
        self.assertTrue(self.source.exists());self.assertTrue(self.target.exists())
        self.assertTrue(self.writer.fenced(release=True))

    def test_full_root_metadata_directory_members_are_preserved(self):
        entries=[('folder/',b''),('01.jpg',b'one'),('ComicInfo.xml',b'<ComicInfo><Series>Authored</Series></ComicInfo>')]
        with zipfile.ZipFile(self.source,'w') as archive:
            for name,data in entries:archive.writestr(name,data)
        self.rebuild()
        with zipfile.ZipFile(self.prepared,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,data in entries:archive.writestr(name,data)
        checksum=guard.file_hash(self.prepared)[1]
        folder=self.cache/'comic-conversions'/conversion.stage_token(self.source,self.request['source_sha256'],checksum)
        folder.mkdir();prepared=folder/'prepared.cbz';self.prepared.replace(prepared);prepared.chmod(0o600)
        self.prepared=prepared;self.request.update(prepared=str(prepared),output_sha256=checksum)
        answer=conversion.commit(self.request);self.assertEqual(conversion.status(answer['token']),answer)
        with zipfile.ZipFile(self.target) as archive:
            self.assertEqual([(item.filename,archive.read(item)) for item in archive.infolist()],entries)

    def test_root_metadata_change_same_payload_is_not_lossless(self):
        with zipfile.ZipFile(self.source,'w') as archive:
            archive.writestr('01.jpg',b'one');archive.writestr('ComicInfo.xml','<ComicInfo><Title>Retained</Title></ComicInfo>')
        self.rebuild()
        # output has the same page payload but drops the root metadata.
        self.assertEqual(guard.inventory(self.source)['payload'],guard.inventory(self.prepared)['payload'])
        with self.assertRaises(guard.Unavailable):conversion.commit(self.request)
        self.assertTrue(self.source.exists());self.assertFalse(self.target.exists())

    def test_retained_original_mutation_before_link_stays_fenced(self):
        def corrupt(phase):
            if phase=='preserved':
                token=guard.canonical_digest(self.request)
                (self.writer.root/'conversion-originals-v1'/token/'original.cbr').write_bytes(b'changed')
        with self.assertRaises(guard.Unavailable):conversion.commit(self.request,boundary=corrupt)
        self.assertTrue(self.source.exists());self.assertFalse(self.target.exists());self.assertTrue(self.writer.fenced(release=True))

    def test_confirmed_pack_member_is_rebound_to_actual_output(self):
        import pack_bindings
        self.store.set('pack','a'*64,dict(members=[dict(id='b'*64,kind='issue',phase='confirmed',
            issueid=self.owner['issueid'],comicid=self.owner['parentcomicid'],destination=str(self.source),
            destination_sha256=self.request['source_sha256'],signature=pack_bindings.signature(self.source))]))
        answer=conversion.commit(self.request)
        member=self.store.get('pack','a'*64)['members'][0]
        self.assertEqual(member['destination'],str(self.target));self.assertEqual(member['destination_sha256'],self.request['output_sha256'])
        self.assertEqual(member['signature'],pack_bindings.signature(self.target))
        self.assertEqual(conversion.status(answer['token']),answer)

    def test_collision_and_stage_member_change_hold_original(self):
        self.target.write_bytes(b'foreign')
        with self.assertRaises((ValueError,guard.Unavailable,native.Review)):conversion.commit(self.request)
        self.assertTrue(self.source.exists());self.target.unlink()
        with zipfile.ZipFile(self.prepared,'a') as archive:archive.writestr('ComicInfo.xml','<ComicInfo/>')
        self.request['output_sha256']=guard.file_hash(self.prepared)[1]
        with self.assertRaises((ValueError,guard.Unavailable,native.Review)):conversion.commit(self.request)
        self.assertTrue(self.source.exists());self.assertFalse(self.target.exists())

    def test_interruptions_never_reconstruct_rights_and_keep_original(self):
        for phase in ('prepared','preserved','copy','linked','cataloged','retired','pack-bound','witness','clearing'):
            with self.subTest(phase=phase):
                if phase!='prepared':
                    self.doCleanups();self.setUp()
                def crash(current):
                    if current==phase:raise OSError('simulated process boundary')
                with self.assertRaises(OSError):conversion.commit(self.request,boundary=crash)
                self.assertTrue(self.writer.fenced(release=True));self.assertTrue((self.writer.root/transaction.NAME).exists())
                with self.assertRaises((guard.Unavailable,native.Review)):conversion.commit(self.request)
                if phase not in ('prepared',):
                    token=guard.canonical_digest(self.request)
                    self.assertEqual((self.writer.root/'conversion-originals-v1'/token/'original.cbr').read_bytes(),rar4())

    def test_temporary_output_changed_at_copy_boundary_never_enters_library(self):
        def corrupt(phase):
            if phase=='copy':
                token=guard.canonical_digest(self.request)
                (self.source.parent/('.conversion-'+token+'.tmp')).write_bytes(b'foreign copy')
        with self.assertRaises(guard.Unavailable):conversion.commit(self.request,boundary=corrupt)
        self.assertTrue(self.source.exists());self.assertFalse(self.target.exists());self.assertTrue(self.writer.fenced(release=True))

    def test_source_replaced_after_catalog_update_is_not_retired(self):
        def replace(phase):
            if phase=='cataloged':
                self.source.unlink();self.source.write_bytes(b'new source must be retained')
        with self.assertRaises(guard.Unavailable):conversion.commit(self.request,boundary=replace)
        self.assertEqual(self.source.read_bytes(),b'new source must be retained')
        self.assertTrue(self.target.exists());self.assertTrue(self.writer.fenced(release=True))

    def test_live_derived_source_cannot_redirect_retirement_to_published_target(self):
        def boundary(phase):
            if phase=='cataloged':
                cap=conversion._LOCAL.conversion;cap.source=self.target;cap.source_state=conversion.file_state(self.target)
        with self.assertRaises(guard.Unavailable):conversion.commit(self.request,boundary=boundary)
        self.assertTrue(self.source.exists());self.assertTrue(self.target.exists());self.assertTrue(self.writer.fenced(release=True))

    def test_live_fixed_derived_attributes_are_bound_to_private_intent(self):
        def boundary(phase):
            if phase!='prepared':return
            cap=conversion._LOCAL.conversion
            for name,value in (('target',self.target.with_name('foreign.cbz')),('prepared',self.source),
                               ('new_location','invented.cbz'),('row',{}),('input',{}),('output',{})):
                with self.subTest(field=name):
                    previous=getattr(cap,name);setattr(cap,name,value)
                    with self.assertRaises(guard.Unavailable):cap.check(self.writer)
                    setattr(cap,name,previous)
            raise guard.Unavailable('Completed attribute refusal controls')
        with self.assertRaises(guard.Unavailable):conversion.commit(self.request,boundary=boundary)
        self.assertTrue(self.source.exists());self.assertFalse(self.target.exists())

    def test_final_private_original_read_cannot_hide_changed_source_before_unlink(self):
        original=conversion.retained;changed=False
        def retained(path,checksum):
            nonlocal changed
            value=original(path,checksum);cap=conversion._LOCAL.conversion
            if cap is not None and cap.phase=='cataloged' and not changed:
                changed=True;self.source.write_bytes(b'foreign source during private proof')
            return value
        with patch.object(conversion,'retained',side_effect=retained),self.assertRaises(guard.Unavailable):conversion.commit(self.request)
        self.assertEqual(self.source.read_bytes(),b'foreign source during private proof');self.assertTrue(self.writer.fenced(release=True))

    def test_witness_boundary_drift_never_clears_recovery_fence(self):
        def change(phase):
            if phase=='witness':self.target.write_bytes(b'changed after terminal preparation')
        with self.assertRaises((guard.Unavailable,ValueError)):conversion.commit(self.request,boundary=change)
        self.assertTrue(self.writer.fenced(release=True));self.assertTrue((self.writer.root/transaction.NAME).exists())

    def test_source_catalog_and_census_drift_before_link_are_held(self):
        def drift(phase):
            if phase=='preserved':
                with self.connection() as db:db.execute("UPDATE issues SET Status='Wanted' WHERE IssueID=?",(self.owner['issueid'],))
        with self.assertRaises((guard.Unavailable,native.Review)):conversion.commit(self.request,boundary=drift)
        self.assertTrue(self.source.exists());self.assertFalse(self.target.exists())

    def test_rewritten_witness_and_missing_terminal_journal_never_acknowledge(self):
        answer=conversion.commit(self.request);path=self.writer.root/'conversion-completed-v1'/(answer['token']+'.json')
        witness=guard.private_json(path);witness['pack_bindings']={'rewritten':True};path.write_text(json.dumps(witness))
        with self.assertRaises(ValueError):conversion.status(answer['token'])
        witness['pack_bindings']=None;path.write_text(json.dumps(witness))
        self.store.delete('owned_conversion',answer['token'])
        with self.assertRaises(ValueError):conversion.status(answer['token'])

    def test_final_admission_drift_is_checked_before_passive_return(self):
        answer=conversion.commit(self.request);actual=self.runtime.admission;calls=[]
        original=self.writer.root/'conversion-originals-v1'/answer['token']/'original.cbr'
        def drift(writer):
            value=actual(writer);calls.append(True)
            if len(calls)==2:original.write_bytes(b'changed during final admission')
            return value
        with patch.object(self.runtime,'admission',side_effect=drift),self.assertRaises(ValueError):conversion.status(answer['token'])

    def test_final_intent_removal_fsync_failure_restores_recovery_hold(self):
        actual=conversion.sync;failed=[]
        def fail(path):
            if (path==self.writer.root and not (path/transaction.NAME).exists()
                    and not self.writer.fenced(release=True) and any((path/'conversion-completed-v1').glob('*.json')) and not failed):
                failed.append(True);raise OSError('final directory durability failed')
            actual(path)
        with patch.object(conversion,'sync',side_effect=fail),self.assertRaises(OSError):conversion.commit(self.request)
        self.assertTrue(failed);self.assertTrue((self.writer.root/transaction.NAME).exists())
        with self.assertRaises(guard.Unavailable):conversion.commit(self.request)
        self.assertTrue(self.target.exists());self.assertFalse(self.source.exists())

    def test_terminal_final_read_detects_retained_original_drift_during_native_proof(self):
        answer=conversion.commit(self.request);actual=native.require
        original=self.writer.root/'conversion-originals-v1'/answer['token']/'original.cbr'
        def drift(*args,**kwargs):
            value=actual(*args,**kwargs);original.write_bytes(b'changed during final native proof');return value
        with patch.object(native,'require',side_effect=drift),self.assertRaises(ValueError):conversion.status(answer['token'])

    def test_passive_witness_rejects_changed_archive_and_recreated_source(self):
        answer=conversion.commit(self.request);self.source.write_bytes(rar4())
        with self.assertRaises(ValueError):conversion.status(answer['token'])
        self.source.unlink();self.target.write_bytes(b'changed')
        with self.assertRaises((ValueError,guard.Unavailable,native.Review)):conversion.status(answer['token'])

    def test_final_status_journal_read_holds_every_new_media_exclusion(self):
        answer=conversion.commit(self.request);original=self.store.get
        for target in (self.writer.pending,self.writer.tagger_pending,self.writer.release_pending,self.writer.root/conversion.NAME,self.writer.root/'nested-derivative-v1.json',self.writer.root/'tagger-recovery-v1.pending'):
            calls=[]
            def changed(kind,key):
                value=original(kind,key)
                if kind=='owned_conversion':
                    calls.append(None)
                    if len(calls)==2:self.writer.create_file(target)
                return value
            with self.subTest(target=target.name),patch.object(self.store,'get',side_effect=changed),self.assertRaises(ValueError):conversion.status(answer['token'])
            self.assertTrue(target.exists());target.unlink()

    def test_final_status_journal_read_holds_replaced_writer_lock(self):
        answer=conversion.commit(self.request);original=self.store.get;calls=[]
        def changed(kind,key):
            value=original(kind,key)
            if kind=='owned_conversion':
                calls.append(None)
                if len(calls)==2:
                    replacement=self.writer.root/'foreign-lock';self.writer.create_file(replacement);replacement.replace(self.writer.lock)
            return value
        with patch.object(self.store,'get',side_effect=changed),self.assertRaises(guard.Unavailable):conversion.status(answer['token'])

    def test_final_status_journal_read_holds_replaced_complete_census(self):
        answer=conversion.commit(self.request);original=self.store.get;calls=[]
        def changed(kind,key):
            value=original(kind,key)
            if kind=='owned_conversion':
                calls.append(None)
                if len(calls)==2:(self.writer.root/'publication-v1.json').write_text('{}')
            return value
        with patch.object(self.store,'get',side_effect=changed),self.assertRaises(ValueError):conversion.status(answer['token'])

    def test_final_status_journal_read_holds_new_workflow_sidecar(self):
        answer=conversion.commit(self.request);original=self.store.get;calls=[]
        def changed(kind,key):
            value=original(kind,key)
            if kind=='owned_conversion':
                calls.append(None)
                if len(calls)==2:Path(str(self.store.path)+'-wal').write_bytes(b'foreign recovery state')
            return value
        with patch.object(self.store,'get',side_effect=changed),self.assertRaises(ValueError):conversion.status(answer['token'])


if __name__=='__main__':unittest.main()
