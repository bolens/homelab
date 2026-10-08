"""Real disposable archive/source controls for read-only diagnostic routing."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

import publication_archive_diagnostics as diagnostic
import publication_archive_repair as repair
import publication_archive_derivative as derivative
import publication_archive_layout as layout
try:
    import publication_evidence as guard
except ImportError:
    import publication_guard as guard


class Controls(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='archive-diagnostic-fixture-')
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.source=self.root/'private-publication.cbz'
        self.build()

    def build(self, directory='Folder', content=b''):
        with zipfile.ZipFile(self.source,'w') as archive:
            entry=zipfile.ZipInfo(directory)
            entry.create_system=3
            entry.external_attr=((stat.S_IFDIR|0o755)<<16)|0x10
            archive.writestr(entry,content)
            archive.writestr('Folder/page01.jpg',b'page one')
            archive.writestr('ComicInfo.xml',b'<ComicInfo><Title>fixture</Title></ComicInfo>')

    def diagnose(self):
        return diagnostic.diagnose(self.source,guard,time.monotonic()+10)

    def test_exact_candidate_is_public_summary_and_preserves_full_source(self):
        before=self.source.read_bytes();signature=diagnostic.stamp(self.source.stat())
        result=self.diagnose()
        self.assertEqual(result['status'],'repair-candidate')
        self.assertEqual(result['reason'],'zip32-one-empty-directory-missing-slash')
        self.assertIs(result['source_unchanged_verified'],True)
        self.assertIs(result['original_writes'],False)
        self.assertEqual(set(result),{'version','status','reason','original_writes','source_unchanged_verified','mutation_authority','native_grant','publication_acceptance'})
        self.assertNotIn(str(self.source),json.dumps(result))
        self.assertNotIn(hashlib.sha256(before).hexdigest(),json.dumps(result))
        self.assertNotIn('page01.jpg',json.dumps(result))
        self.assertEqual(self.source.read_bytes(),before)
        self.assertEqual(diagnostic.stamp(self.source.stat()),signature)
        for key in ('mutation_authority','native_grant','publication_acceptance'):self.assertIs(result[key],False)

    def test_regular_zip_never_returns_repair(self):
        with zipfile.ZipFile(self.source,'w') as archive:archive.writestr('page.png',b'page')
        self.assertEqual(self.diagnose()['status'],'verified-no-repair')

    def test_crc_error_is_held(self):
        self.source.write_bytes(self.source.read_bytes().replace(b'page one',b'bad page'))
        self.assertEqual(self.diagnose()['status'],'review-needed')

    def test_truncation_is_held(self):
        self.source.write_bytes(self.source.read_bytes()[:-12])
        self.assertEqual(self.diagnose()['status'],'review-needed')

    def test_invalid_deflate_stream_is_retained_without_exception_escape(self):
        with zipfile.ZipFile(self.source,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('page.png',b'page')
        raw=bytearray(self.source.read_bytes())
        length=30+struct.unpack_from('<H',raw,26)[0]+struct.unpack_from('<H',raw,28)[0]
        raw[length]=0xff
        self.source.write_bytes(raw);before=self.source.read_bytes()
        result=self.diagnose()
        self.assertEqual(result['status'],'review-needed')
        self.assertEqual(self.source.read_bytes(),before)
        self.assertFalse(result['publication_acceptance'])

    def test_encryption_flags_are_held(self):
        raw=bytearray(self.source.read_bytes());struct.pack_into('<H',raw,6,1)
        central=raw.index(b'PK\x01\x02');struct.pack_into('<H',raw,central+8,1)
        self.source.write_bytes(raw)
        self.assertEqual(self.diagnose()['status'],'review-needed')

    def test_unsafe_name_does_not_sanitize_content(self):
        with zipfile.ZipFile(self.source,'w') as archive:archive.writestr('../page.png',b'page')
        before=self.source.read_bytes()
        self.assertEqual(self.diagnose()['reason'],'unsafe-or-noncanonical-member-name')
        self.assertEqual(self.source.read_bytes(),before)

    def test_decoder_retry_is_not_verified_compatibility(self):
        self.source.write_bytes(b'Rar!\x1a\x07\x01\x00fixture')
        result=self.diagnose()
        self.assertEqual(result['status'],'decoder-verification-required')
        self.assertFalse(result['publication_acceptance'])

    def test_pdf_is_conversion_required(self):
        self.source.write_bytes(b'%PDF-1.7\nfixture')
        self.assertEqual(self.diagnose()['status'],'conversion-required')

    def test_deadline_prevents_classification(self):
        with patch.object(diagnostic.repair,'classify') as classify:
            result=diagnostic.diagnose(self.source,guard,time.monotonic()-1)
        classify.assert_not_called()
        self.assertIs(result['source_unchanged_verified'],False)
        self.assertEqual(result['reason'],'stable-source-diagnostic-unavailable')

    def test_runtime_buffer_cap_respects_worker_memory_contract(self):
        self.assertEqual(diagnostic.MAX_SOURCE,128 * 1024**2)

    def test_size_bound_prevents_classification(self):
        with patch.object(diagnostic,'MAX_SOURCE',1),patch.object(diagnostic.repair,'classify') as classify:
            self.assertEqual(self.diagnose()['reason'],'stable-source-diagnostic-unavailable')
        classify.assert_not_called()

    def test_symlink_and_hardlink_are_held_without_classifying(self):
        link=self.root/'alias.cbz';link.symlink_to(self.source)
        with patch.object(diagnostic.repair,'classify') as classify:
            self.assertEqual(diagnostic.diagnose(link,guard,time.monotonic()+10)['status'],'review-needed')
            link.unlink();os.link(self.source,link)
            self.assertEqual(self.diagnose()['status'],'review-needed')
        classify.assert_not_called()

    def test_noncanonical_parent_symlink_is_held(self):
        alias=self.root/'alias';alias.symlink_to(self.root,target_is_directory=True)
        self.assertEqual(diagnostic.diagnose(alias/self.source.name,guard,time.monotonic()+10)['reason'],
                         'stable-source-diagnostic-unavailable')

    def test_in_place_change_during_classification_is_held(self):
        original=repair.classify
        def changed(raw,*args):
            result=original(raw,*args);self.source.write_bytes(raw);return result
        with patch.object(diagnostic.repair,'classify',side_effect=changed):
            self.assertEqual(self.diagnose()['reason'],'stable-source-diagnostic-unavailable')

    def test_same_bytes_new_inode_during_classification_is_held(self):
        original=repair.classify
        def changed(raw,*args):
            result=original(raw,*args)
            replacement=self.root/'new.cbz';replacement.write_bytes(raw);os.replace(replacement,self.source)
            return result
        with patch.object(diagnostic.repair,'classify',side_effect=changed):
            self.assertEqual(self.diagnose()['reason'],'stable-source-diagnostic-unavailable')

    def test_open_file_change_during_read_is_held(self):
        original=diagnostic.os.read;changed=[]
        def read(fd,size):
            block=original(fd,size)
            if block and not changed:self.source.write_bytes(self.source.read_bytes());changed.append(True)
            return block
        with patch.object(diagnostic.os,'read',side_effect=read),patch.object(diagnostic.repair,'classify') as classify:
            self.assertEqual(self.diagnose()['reason'],'stable-source-diagnostic-unavailable')
        classify.assert_not_called()

    def test_public_reason_rejects_path_or_exception_disclosure(self):
        original=repair.classify
        def disclose(raw,*args):
            result=original(raw,*args);result['reason']=str(self.source);return result
        with patch.object(diagnostic.repair,'classify',side_effect=disclose):
            result=self.diagnose()
        self.assertEqual(result['reason'],'stable-source-diagnostic-unavailable')
        self.assertNotIn(str(self.source),json.dumps(result))

    def witness(self):
        raw=self.source.read_bytes()
        headers,envelope=layout.layout(io.BytesIO(raw),len(raw))
        inventory,metadata=derivative.independent(raw,guard,time.monotonic()+10,0)
        fields=repair.ENTRY_FIELDS
        return dict(version=1,kind='one-zip-directory-header-virtual-inventory',
                    source=dict(path=str(self.source),signature9=diagnostic.stamp(self.source.stat()),
                                sha256=hashlib.sha256(raw).hexdigest()),
                    entry={key:headers[0][key] for key in fields},
                    proposed_directory_name=headers[0]['name']+'/',
                    virtual_original_inventory=inventory,root_metadata_sha256=metadata,
                    raw_header_commitments=[dict(row,crc_verified=True,uncompressed_sha256=member['sha256'],
                                                 virtual_directory=member['directory'],header_change_declared=index==0)
                                            for index,(row,member) in enumerate(zip(headers,inventory['members']))],
                    zip_envelope=envelope,all_members_crc_verified=True,
                    ordinary_source_admission=False,native_grant=False,mutation_authority=False,
                    publication_acceptance=False,derivative_written=False,derivative_equivalence_verified=False,
                    purpose_integration_verified=False)

    def test_pure_dispatch_full_metadata_and_source_preservation(self):
        raw=self.source.read_bytes();fact=diagnostic.stamp(self.source.stat())
        plan=repair.classify(raw,guard,time.monotonic()+10)
        repaired,evidence=repair.dispatch(raw,plan,self.witness(),guard,time.monotonic()+10)
        self.assertEqual(self.source.read_bytes(),raw)
        self.assertEqual(diagnostic.stamp(self.source.stat()),fact)
        self.assertTrue(evidence['all_members_crc_verified_before_after'])
        self.assertTrue(evidence['compressed_payloads_and_other_header_bytes_preserved'])
        self.assertFalse(evidence['publication_acceptance'])
        self.assertEqual(evidence['inventory'],plan['inventory'])
        with zipfile.ZipFile(io.BytesIO(repaired)) as archive:
            self.assertEqual(archive.read('ComicInfo.xml'),b'<ComicInfo><Title>fixture</Title></ComicInfo>')
            self.assertEqual(archive.read('Folder/page01.jpg'),b'page one')
            self.assertIsNone(archive.testzip())

    def test_pure_dispatch_rejects_plan_and_witness_rewrite(self):
        raw=self.source.read_bytes();plan=repair.classify(raw,guard,time.monotonic()+10);witness=self.witness()
        wrong=copy.deepcopy(plan);wrong['all_members_crc_verified']=1
        with self.assertRaises(ValueError):repair.dispatch(raw,wrong,witness,guard,time.monotonic()+10)
        wrong=copy.deepcopy(witness);wrong['native_grant']=True
        with self.assertRaises(ValueError):repair.dispatch(raw,plan,wrong,guard,time.monotonic()+10)

    def test_pure_dispatch_rejects_changed_source(self):
        raw=self.source.read_bytes();plan=repair.classify(raw,guard,time.monotonic()+10);witness=self.witness()
        with self.assertRaises(ValueError):repair.dispatch(raw+b'x',plan,witness,guard,time.monotonic()+10)

    def test_pure_dispatch_cannot_repair_nonempty_directory(self):
        self.build(content=b'not empty');raw=self.source.read_bytes()
        plan=repair.classify(raw,guard,time.monotonic()+10)
        self.assertEqual(plan['status'],'review-needed')
        with self.assertRaises(ValueError):repair.dispatch(raw,plan,{},guard,time.monotonic()+10)

    def test_unknown_ascii_reason_is_not_an_operator_message(self):
        original=repair.classify
        def disclose(raw,*args):
            result=original(raw,*args);result['reason']='private-archive-name';return result
        with patch.object(diagnostic.repair,'classify',side_effect=disclose):result=self.diagnose()
        self.assertEqual(result['reason'],'stable-source-diagnostic-unavailable')
        self.assertNotIn('private-archive-name',json.dumps(result))

    def test_last_parent_callback_source_rewrite_cannot_claim_unchanged(self):
        real=diagnostic.parents;calls=[]
        def changed(path):
            vector=real(path);calls.append(True)
            if len(calls)==3:self.source.write_bytes(b'foreign changed source')
            return vector
        with patch.object(diagnostic,'parents',side_effect=changed):result=self.diagnose()
        self.assertEqual(len(calls),3)
        self.assertEqual(result['status'],'review-needed')
        self.assertEqual(result['reason'],'stable-source-diagnostic-unavailable')
        self.assertIs(result['source_unchanged_verified'],False)
        self.assertFalse(result['publication_acceptance'])

    def test_summary_callback_source_rewrite_cannot_claim_unchanged(self):
        real=diagnostic.public_summary;changed=[]
        def rewrite(value):
            result=real(value)
            if not changed:self.source.write_bytes(b'foreign changed source');changed.append(True)
            return result
        with patch.object(diagnostic,'public_summary',side_effect=rewrite):result=self.diagnose()
        self.assertEqual(result['reason'],'stable-source-diagnostic-unavailable')
        self.assertIs(result['source_unchanged_verified'],False)

    def test_missing_source_is_held_without_classifying(self):
        self.source.unlink()
        with patch.object(diagnostic.repair,'classify') as classify:self.diagnose()
        classify.assert_not_called()

if __name__=='__main__':unittest.main()
