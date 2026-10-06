"""Native report admission uses actual retained archives, complete census and current catalog."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import unittest
import zipfile

import publication_guard as guard
import test_publication_native as native_fixtures
import test_publication_api as fixtures


@unittest.skipUnless((Path(fixtures.TOOL_ROOT)/'lib/archive_backend.py').is_file(),'offline archive verifier required')
class NativeReportTests(unittest.TestCase):
    setUp=native_fixtures.AdmissionTests.setUp
    call=native_fixtures.AdmissionTests.call
    bootstrap=native_fixtures.AdmissionTests.bootstrap
    prepare=native_fixtures.AdmissionTests.prepare
    maintenance_gateway=native_fixtures.AdmissionTests.maintenance_gateway

    def packet(self,report=None,processing=None,guidance=None,claims=None,source=None,match=None):
        gateway=self.maintenance_gateway();self.bootstrap()
        claims=dict(claims or dict(version=1,report=[],processing=[],guidance=[]),observed_at=int(time.time()//300)*300)
        arguments={key:json.dumps(value) for key,value in dict(report=report or [],processing=processing or [],
            guidance=guidance or [],report_binding=claims).items()}
        with self.writer.hold():census=guard.registry_snapshot(self.store.path,self.writer.root/'publication-v1.json')[0]
        sources=[] if source is None else [dict(path=str(source),sha256=guard.file_hash(source)[1],match=match,confirmation=False)]
        value=dict(version=1,token='d'*64,command='reportImportProblems',arguments_sha256=guard.canonical_digest(arguments),
                   census=census,sources=sources)
        return gateway,arguments,value

    def invoke(self,gateway,arguments,packet):
        with self.writer.hold():return gateway.admit(json.dumps(packet),'reportImportProblems',arguments)

    def test_diagnostics_need_current_census_and_record_one_native_attempt(self):
        gateway,arguments,packet=self.packet(report=[dict(name='retained.cbz',kind='failed',phase='')])
        self.assertEqual(self.invoke(gateway,arguments,packet),'d'*64)
        with self.assertRaises(ValueError):self.invoke(gateway,arguments,packet)
        self.assertIsNotNone(self.store.get('worker_maintenance_attempt','d'*64))

    def test_private_fields_false_completion_and_unowned_ids_spend_nothing(self):
        cases=[dict(name='retained.cbz',kind='failed',phase='',_source='/private/path'),
               dict(name='retained.cbz',kind='quarantine_resolved',phase=''),
               dict(name='retained.cbz',kind='import_queued',phase=''),
               dict(name='retained.cbz',kind='failed',phase='',issueid='123',comicid='456')]
        gateway,arguments,packet=self.packet()
        for row in cases:
            altered=dict(arguments,report=json.dumps([row]))
            bound=dict(packet,arguments_sha256=guard.canonical_digest(altered))
            with self.assertRaises(ValueError):self.invoke(gateway,altered,bound)
            self.assertIsNone(self.store.get('worker_maintenance_attempt','d'*64))

    def test_ready_requires_the_bound_current_actual_native_source_and_owner(self):
        report=[dict(name=self.incoming.name,kind='ready',phase='',issueid='123',comicid='456')]
        claims=dict(version=1,report=[dict(index=0,path=str(self.incoming),match=dict(issueid='123',comicid='456'),confirmation=False)],processing=[],guidance=[])
        gateway,arguments,packet=self.packet(report=report,claims=claims,source=self.incoming,match=dict(issueid='123',comicid='456'))
        missing=dict(packet,sources=[])
        with self.assertRaises(ValueError):self.invoke(gateway,arguments,missing)
        self.assertIsNone(self.store.get('worker_maintenance_attempt','d'*64))
        self.assertEqual(self.invoke(gateway,arguments,packet),'d'*64)

    def test_native_current_census_and_source_changes_hold_before_any_display_update(self):
        gateway,arguments,packet=self.packet(report=[dict(name='retained.cbz',kind='failed',phase='')])
        with self.assertRaises(ValueError):self.invoke(gateway,arguments,dict(packet,census=dict(packet['census'],revision=99)))
        self.assertFalse((self.root/'import-problems.json').exists())
        self.assertIsNone(self.store.get('worker_maintenance_attempt','d'*64))

    def test_old_future_boolean_and_unbucketed_observations_spend_no_attempt(self):
        gateway,arguments,packet=self.packet()
        binding=json.loads(arguments['report_binding'])
        for observed in (True,binding['observed_at']-1200,binding['observed_at']+600,binding['observed_at']+1):
            altered=dict(arguments,report_binding=json.dumps(dict(binding,observed_at=observed)))
            with self.assertRaises(ValueError):self.invoke(gateway,altered,dict(packet,arguments_sha256=guard.canonical_digest(altered)))
            self.assertIsNone(self.store.get('worker_maintenance_attempt','d'*64))

    def test_processing_cannot_assert_done_or_catalog_identity_without_lineage(self):
        gateway,arguments,packet=self.packet()
        for extra in (dict(phase='done'),dict(issueid='123',comicid='456'),dict(original_format='SECRET')):
            row=dict(name='comic.cbz',phase='failed',original_format='CBR',original_container='RAR');row.update(extra)
            altered=dict(arguments,processing=json.dumps([row]))
            with self.assertRaises(ValueError):self.invoke(gateway,altered,dict(packet,arguments_sha256=guard.canonical_digest(altered)))
            self.assertIsNone(self.store.get('worker_maintenance_attempt','d'*64))

    def guidance(self):
        with closing(sqlite3.connect(self.root/'mylar.db')) as db:
            db.executescript('ALTER TABLE comics ADD COLUMN ComicName TEXT; ALTER TABLE comics ADD COLUMN ComicYear TEXT;'
                'ALTER TABLE issues ADD COLUMN Issue_Number TEXT; ALTER TABLE issues ADD COLUMN IssueDate TEXT;'
                'ALTER TABLE annuals ADD COLUMN Issue_Number TEXT; ALTER TABLE annuals ADD COLUMN IssueDate TEXT;'
                'ALTER TABLE annuals ADD COLUMN ReleaseComicName TEXT;')
            db.execute("UPDATE comics SET ComicName='Test',ComicYear='2024'")
            db.execute("UPDATE issues SET Issue_Number='1',IssueDate='2024-01-01'");db.commit()
        source=self.root/'Test #1 (2024).cbz'
        with zipfile.ZipFile(source,'w') as archive:archive.writestr('01.jpg',b'genuinely different publication')
        signature=guard.signature(source.stat());checksum=guard.file_hash(source)[1]
        version=hashlib.sha256(json.dumps([[signature[1],signature[2],signature[3]],checksum]).encode()).hexdigest()
        row=dict(source_token='a'*32,version=version,name=source.name,evidence=['filename: Test #1 (2024)'],
            alias_scope=dict(series='test',year='2024'),candidates=[dict(issueid='123',comicid='456',title='Test',year='2024',
                number='1',status='Downloaded',agrees=['filename series','filename issue','filename year'],conflicts=[])])
        claims=dict(version=1,report=[],processing=[],guidance=[dict(source_token=row['source_token'],version=version,path=str(source))])
        return source,row,claims

    def test_guidance_reconstructs_source_evidence_and_current_catalog_before_attempt(self):
        source,row,claims=self.guidance()
        gateway,arguments,packet=self.packet(guidance=[row],claims=claims,source=source)
        self.assertEqual(self.invoke(gateway,arguments,packet),'d'*64)

    def test_invalid_guidance_text_is_rejected_before_durable_attempt(self):
        source,row,claims=self.guidance()
        gateway,arguments,packet=self.packet(guidance=[row],claims=claims,source=source)
        changed=json.loads(json.dumps(row));changed['candidates'][0]['title']='https://private.invalid'
        altered=dict(arguments,guidance=json.dumps([changed]))
        with self.assertRaises(ValueError):self.invoke(gateway,altered,dict(packet,arguments_sha256=guard.canonical_digest(altered)))
        self.assertIsNone(self.store.get('worker_maintenance_attempt','d'*64))
        changed=dict(row,requires_review='true');altered=dict(arguments,guidance=json.dumps([changed]))
        with self.assertRaises(ValueError):self.invoke(gateway,altered,dict(packet,arguments_sha256=guard.canonical_digest(altered)))
        self.assertIsNone(self.store.get('worker_maintenance_attempt','d'*64))

    def test_stale_or_forged_guidance_and_missing_source_cannot_create_future_choices(self):
        source,row,claims=self.guidance()
        gateway,arguments,packet=self.packet(guidance=[row],claims=claims,source=source)
        for field,value in (('evidence',['fabricated evidence']),('alias_scope',dict(series='wrong',year='2024')),
                            ('version','f'*64)):
            changed=dict(row,**{field:value});altered=dict(arguments,guidance=json.dumps([changed]))
            with self.assertRaises(ValueError):self.invoke(gateway,altered,dict(packet,arguments_sha256=guard.canonical_digest(altered)))
            self.assertIsNone(self.store.get('worker_maintenance_attempt','d'*64))
        with self.assertRaises(ValueError):self.invoke(gateway,arguments,dict(packet,sources=[]))
        with closing(sqlite3.connect(self.root/'mylar.db')) as db:
            db.execute("UPDATE issues SET Status='Wanted'");db.commit()
        with self.assertRaises(ValueError):self.invoke(gateway,arguments,packet)
        self.assertIsNone(self.store.get('worker_maintenance_attempt','d'*64))


if __name__=='__main__':unittest.main()
