"""Native transfer preflights retain exact protected files and catalog bindings."""
import ast
import os
from pathlib import Path
import types
import unittest
from unittest.mock import Mock, patch
import zipfile

import test_publication_native as cases
import publication_native as native
import publication_mutation as mutation
import processing_guard
from patch_media_writers import mutation_source


@unittest.skipUnless((Path(cases.fixtures.TOOL_ROOT)/'lib/archive_backend.py').is_file(),
                     'offline archive verifier required; custom image gate supplies it')
class TransferTests(unittest.TestCase):
    setUp=cases.AdmissionTests.setUp
    call=cases.AdmissionTests.call
    bootstrap=cases.AdmissionTests.bootstrap
    prepare=cases.AdmissionTests.prepare
    registered=cases.AdmissionTests.registered
    sql=cases.AdmissionTests.sql

    def transfer(self,source=None,destination=None,**kwargs):
        values=dict(issueid='123',comicid='456');values.update(kwargs)
        with self.writer.hold():
            mutation.transfer(source or self.incoming,destination or self.root/'output.cbz',**values)

    def test_wrong_known_payload_is_retained_before_move_or_copy(self):
        self.registered();self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',None,'Snatched'))
        before=(self.incoming.read_bytes(),self.database.read_bytes())
        for action in ('move','copy','hardlink','softlink'):
            with self.assertRaises(native.Review):self.transfer(issueid='999',comicid='888',action=action)
        self.assertEqual((self.incoming.read_bytes(),self.database.read_bytes()),before)
        self.assertFalse((self.root/'output.cbz').exists())

    def test_protected_original_moves_and_links_hold_before_losing_catalog_path(self):
        self.registered();before=(self.source.read_bytes(),self.database.read_bytes())
        for action in ('move','hardlink','softlink'):
            with self.assertRaises(native.Review):self.transfer(self.source,action=action)
        self.assertEqual((self.source.read_bytes(),self.database.read_bytes()),before)

    def test_correct_original_copy_to_new_cache_path_is_eligible(self):
        self.registered();self.transfer(self.source,action='copy')
        self.assertTrue(self.source.is_file());self.assertFalse((self.root/'output.cbz').exists())

    def test_catalog_destination_and_physical_alias_are_not_overwritten(self):
        self.registered();alias=self.root/'alias.cbz';os.link(self.source,alias)
        for target in (self.source,alias):
            with self.assertRaises(native.Review):self.transfer(destination=target,action='copy')
        with self.assertRaises(native.Review):self.transfer(self.source,self.library,action='copy')
        self.assertEqual(self.source.read_bytes(),self.incoming.read_bytes())

    def test_ownerless_known_payload_does_not_guess_owner(self):
        self.registered()
        with self.assertRaises(native.Review):self.transfer(issueid=None,comicid=None)

    def test_directory_discovery_cannot_authorize_moving_a_parent_of_protected_archive(self):
        self.registered()
        with self.assertRaises(native.Review):self.transfer(self.library)
        self.assertTrue(self.source.is_file())

    def test_active_processing_owner_supplies_helper_binding(self):
        self.registered()
        processor=types.SimpleNamespace(_publication_owner=dict(issueid='123',parentcomicid='456'))
        with patch.object(processing_guard._ACTIVE,'processor',processor,create=True):
            self.transfer(issueid=None,comicid=None)

    def test_genuinely_different_unbound_archive_remains_eligible(self):
        self.registered();different=self.root/'different.cbz'
        with zipfile.ZipFile(different,'w') as archive:archive.writestr('01.jpg',b'different real pages')
        self.transfer(different,issueid=None,comicid='888')
        self.assertTrue(different.is_file())

    def test_lost_current_binding_does_not_allow_overwriting_attested_correct_path(self):
        self.registered();self.sql("UPDATE issues SET Location=NULL,Status='Wanted' WHERE IssueID='123'")
        different=self.root/'different.cbz'
        with zipfile.ZipFile(different,'w') as archive:archive.writestr('01.jpg',b'different real pages')
        with self.assertRaises(native.Review):self.transfer(different,self.source,issueid=None,comicid=None)
        self.assertTrue(self.source.is_file())

    def test_ownerless_different_payload_cannot_bypass_native_catalog_recovery(self):
        self.registered();different=self.root/'different.cbz'
        with zipfile.ZipFile(different,'w') as archive:archive.writestr('01.jpg',b'different real pages')
        sidecar=Path(str(self.database)+'-journal');sidecar.write_bytes(b'retained interrupted state')
        before=(self.database.read_bytes(),sidecar.read_bytes())
        with self.assertRaises(native.Review):self.transfer(different,issueid=None,comicid=None)
        self.assertEqual((self.database.read_bytes(),sidecar.read_bytes()),before)

    def test_different_archive_bound_to_rejected_row_still_requires_catalog_relocation(self):
        self.registered();different=self.library/'different.cbz'
        with zipfile.ZipFile(different,'w') as archive:archive.writestr('01.jpg',b'different real pages')
        self.sql('INSERT INTO comics VALUES (?,?,?)',('888',str(self.library),'Paused'))
        self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',different.name,'Downloaded'))
        with self.assertRaises(native.Review):self.transfer(different,issueid='999',comicid='888')
        self.transfer(different,issueid='999',comicid='888',action='copy')

    def test_linked_destination_and_unsupported_policy_are_retained(self):
        self.registered();linked=self.root/'linked';linked.symlink_to(self.library,target_is_directory=True)
        with self.assertRaises(native.Review):self.transfer(destination=linked/'output.cbz')
        with self.assertRaises(native.Review):self.transfer(action='unknown')

    @unittest.skipUnless(os.environ.get('MYLAR_WORKFLOW_SOURCE'),'actual native source required')
    def test_actual_native_file_policies_cannot_enter_io_or_failure_fallback(self):
        self.registered();self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',None,'Snatched'))
        source=mutation_source((Path(os.environ['MYLAR_WORKFLOW_SOURCE'])/'helpers.py').read_text(),'helpers.py')
        function=next(node for node in ast.parse(source).body if isinstance(node,ast.FunctionDef) and node.name=='file_ops')
        function.decorator_list=[]
        io=Mock();logger=Mock()
        namespace=dict(mylar=self.mylar,publication_mutation=mutation,shutil=io,os=io,logger=logger)
        exec(compile(ast.Module(body=[function],type_ignores=[]),'<actual native file_ops>','exec'),namespace)
        processor=types.SimpleNamespace(_publication_owner=dict(issueid='999',parentcomicid='888'),valreturn=[])
        with patch.object(processing_guard._ACTIVE,'processor',processor,create=True),self.writer.hold():
            for policy in ('copy','move','hardlink','softlink'):
                self.mylar.CONFIG.FILE_OPTS=policy
                with self.assertRaises(native.Review):namespace['file_ops'](str(self.incoming),str(self.root/'output.cbz'))
        self.assertEqual(io.mock_calls,[]);logger.error.assert_not_called()
        self.assertTrue(processor.valreturn);self.assertTrue(self.incoming.is_file())


class SourcePatchTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('MYLAR_WORKFLOW_SOURCE'),'actual native source required')
    def test_actual_transfer_guards_are_idempotent_and_immediately_precede_mutation(self):
        from patch_media_writers import TRANSFERS
        root=Path(os.environ['MYLAR_WORKFLOW_SOURCE'])
        for name in ('helpers.py',*TRANSFERS):
            source=(root/name).read_text();patched=mutation_source(source,name)
            self.assertEqual(mutation_source(patched,name),patched)
            ast.parse(patched)
            for call,check in TRANSFERS.get(name,()):
                lines=patched.splitlines();index=next(i for i,line in enumerate(lines) if line.strip()==call)
                self.assertEqual(lines[index-1].strip(),check)
            if name=='helpers.py':
                check=patched.index('publication_mutation.transfer(path, dst, action=')
                for operation in ('shutil.copy( path , dst )','shutil.move( path , dst )','os.open( path, os.O_RDWR|os.O_CREAT )'):
                    self.assertLess(check,patched.index(operation))

    def test_unknown_native_layout_is_refused(self):
        with self.assertRaises(ValueError):mutation_source('import mylar\n','webserve.py')


if __name__=='__main__':unittest.main()
