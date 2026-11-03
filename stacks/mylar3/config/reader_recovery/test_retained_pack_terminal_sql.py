"""Detached SQLite originals and exact retained successor SQL, without grants."""
import copy
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).parent))
import comic_retained_pack_parent as terminal
import comic_reader_backup_primitives as primitives


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def snapshot(path):
    with closing(sqlite3.connect(path)) as db:
        schema = [list(row) for row in db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name')]
        rows = {name: sorted(compact([{'blob':v.hex()} if isinstance(v, bytes) else v for v in row]).decode()
                             for row in db.execute('SELECT * FROM "'+name+'"'))
                for kind, name, _, _ in schema if kind == 'table'}
    return dict(schema=schema, rows=rows)


class SQL(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.workflow = Path(self.temp.name)/'workflow.sqlite'
        self.catalog = Path(self.temp.name)/'mylar.db'
        self.request = dict(version=1, kind='retained-ddl-existing-target-v1', ddl_id='42-1',
            pack_id='a'*64, member_id='b'*64, source_generation='e'*64, source_sha256='f'*64,
            target_sha256='d'*64, review_sha256='1'*64,
            owner=dict(table='issues', issueid='3', parentcomicid='4', releasecomicid='4'))
        self.token = hashlib.sha256(('42-1\0'+'a'*64+'\0'+'b'*64).encode()).hexdigest()
        self.pack = dict(id=self.request['pack_id'], ddl_id=self.request['ddl_id'],
            source_generation=self.request['source_generation'], phase='review', members=[
                dict(id=self.request['member_id'], kind='issue', issueid='3', comicid='4',
                     releasecomicid='4', phase='review', wanted=True,
                     destination='/library/current.cbz', destination_sha256=self.request['target_sha256'],
                     sha256=self.request['source_sha256']), dict(id='other', phase='rejected')])
        self.build_fixture()

    def build_fixture(self):
        for path in (self.workflow, self.catalog):
            if path.exists(): path.unlink()
        self.old = ['pack', self.request['pack_id'], compact(self.pack).decode(), 12.5]
        with closing(sqlite3.connect(self.workflow)) as db:
            db.execute('CREATE TABLE records(kind TEXT,id TEXT,body TEXT,updated REAL)')
            db.execute('INSERT INTO records VALUES (?,?,?,?)', self.old)
            db.execute("INSERT INTO records VALUES ('foreign','keep','{\"intent\":\"Wanted\"}',2.0)")
            db.execute('CREATE TABLE unrelated(k TEXT,v BLOB)')
            db.execute('INSERT INTO unrelated VALUES (?,?)', ('é', b'\x00\xff')); db.commit()
        with closing(sqlite3.connect(self.catalog)) as db:
            db.execute('CREATE TABLE owners(issue TEXT,status TEXT)')
            db.execute("INSERT INTO owners VALUES ('1','Downloaded')"); db.commit()
        self.before, self.before_catalog = snapshot(self.workflow), snapshot(self.catalog)
        self.backup_workflow, self.backup_catalog = primitives.database(self.workflow), primitives.database(self.catalog)
        wanted = copy.deepcopy(self.pack)
        wanted['members'][0].update(phase='retained-accepted', retained_finalization=self.token,
                                  destination='/library/current.cbz', destination_sha256=self.request['target_sha256'])
        rights = {key:False for key in ('historical_import_ack','ordinary_import_grant','cleanup_grant',
                  'mutation_authority','publication_acceptance','reader_index_acceptance','automatic_replay')}
        record = dict(version=2, kind='fresh-retained-backend-finalization', token=self.token,
            workflow_before_sha256=hashlib.sha256(compact(self.before)).hexdigest(),pack_before_row=self.old,
            request=self.request, source='/cache/member.cbz', target='/library/current.cbz', original_event={},
            original_vectors={}, pack_before=self.pack, pack_after=wanted, **rights)
        self.new = ['pack', self.request['pack_id'], compact(wanted).decode(), 12.5]
        record_bytes = compact(record).decode()
        transition = dict(version=1, kind='retained-pack-two-row-transition', request=self.request,
            native_data_root='/config', record_bytes=record_bytes, pack_before_row=self.old, pack_after_row=self.new,
            workflow_before=self.before, original_vectors={}, committed_vectors={}, committed_hashes={},
            native_source_root='/app/mylar', native_sources=[])
        self.reply = dict(success=True, data=dict(version=1, outcome='fresh-retained-backend-finalized',
            token=self.token, record_kind='retained_delivery_final', record_sha256=hashlib.sha256(record_bytes.encode()).hexdigest(),
            committed={}, transition=transition, **rights))
        with closing(sqlite3.connect(self.workflow)) as db:
            db.execute('UPDATE records SET body=? WHERE kind=? AND id=?', (self.new[2], 'pack', self.request['pack_id']))
            db.execute('INSERT INTO records VALUES (?,?,?,?)', ('retained_delivery_final', self.token, record_bytes, 0.0)); db.commit()
        self.current, self.current_catalog = snapshot(self.workflow), snapshot(self.catalog)

    def call(self):
        return terminal.verify_retained_sql(self.before, self.before_catalog, backup_workflow=self.backup_workflow,
            backup_catalog=self.backup_catalog, request=self.request, reply=self.reply,
            current=self.current, current_catalog=self.current_catalog)

    def test_real_SQLite_all_table_fingerprints_and_two_row_successor(self):
        result = self.call()
        self.assertTrue(all(value is False for key, value in result.items() if key != 'kind'))

    def test_persistent_preimage_commitment_must_match_independent_originals(self):
        answer=self.reply['data'];record=json.loads(answer['transition']['record_bytes'])
        record['workflow_before_sha256']='0'*64
        encoded=compact(record).decode();answer['transition']['record_bytes']=encoded
        answer['record_sha256']=hashlib.sha256(encoded.encode()).hexdigest()
        with self.assertRaisesRegex(ValueError,'terminal-record'):self.call()

    def test_persistent_raw_pack_preimage_cannot_rebase_updated_column(self):
        answer=self.reply['data'];record=json.loads(answer['transition']['record_bytes'])
        record['pack_before_row'][3]+=1
        encoded=compact(record).decode();answer['transition']['record_bytes']=encoded
        answer['record_sha256']=hashlib.sha256(encoded.encode()).hexdigest()
        with self.assertRaisesRegex(ValueError,'terminal-record'):self.call()

    def test_omitted_original_table_even_with_self_consistent_partial_model_refuses(self):
        del self.before['rows']['unrelated']; self.before['schema'] = [row for row in self.before['schema'] if row[1]!='unrelated']
        self.reply['data']['transition']['workflow_before'] = copy.deepcopy(self.before)
        with self.assertRaisesRegex(ValueError, 'backup-allSQL'): self.call()

    def test_omitted_original_row_refuses_against_independent_backup(self):
        self.before['rows']['records'] = [row for row in self.before['rows']['records'] if json.loads(row)[0]=='pack']
        with self.assertRaisesRegex(ValueError, 'backup-allSQL'): self.call()

    def test_extra_current_row_in_unrelated_table_refuses(self):
        with closing(sqlite3.connect(self.workflow)) as db:
            db.execute('INSERT INTO unrelated VALUES (?,?)', ('foreign', b'changed')); db.commit()
        self.current = snapshot(self.workflow)
        with self.assertRaisesRegex(ValueError, 'exact-two-row'): self.call()

    def test_current_catalog_change_refuses(self):
        with closing(sqlite3.connect(self.catalog)) as db:
            db.execute("UPDATE owners SET status='Wanted'"); db.commit()
        self.current_catalog = snapshot(self.catalog)
        with self.assertRaisesRegex(ValueError, 'unchanged-catalog'): self.call()

    def test_wrong_member_refuses(self):
        self.request = dict(self.request, member_id='e'*64)
        with self.assertRaisesRegex(ValueError, 'request-token'): self.call()

    def test_record_hash_mismatch_refuses(self):
        self.reply['data']['transition']['record_bytes'] += ' '
        with self.assertRaisesRegex(ValueError, 'record-bytes'): self.call()

    def test_rights_cannot_be_upgraded(self):
        self.reply['data']['cleanup_grant'] = True
        with self.assertRaisesRegex(ValueError, 'outcome'): self.call()

    def test_existing_finalization_or_duplicate_original_pack_refuses(self):
        self.before['rows']['records'].append(self.before['rows']['records'][0]); self.before['rows']['records'].sort()
        with self.assertRaisesRegex(ValueError, 'backup-allSQL'): self.call()

    def test_bool_version_is_not_integer_version(self):
        self.reply['data']['version'] = True
        with self.assertRaisesRegex(ValueError, 'outcome'): self.call()

    def test_consistent_foreign_token_refuses(self):
        self.token = 'c'*64; self.build_fixture()
        with self.assertRaisesRegex(ValueError, 'request-token'): self.call()

    def test_self_consistent_incomplete_request_refuses(self):
        del self.request['review_sha256']; self.build_fixture()
        with self.assertRaisesRegex(ValueError, 'request'): self.call()

    def test_request_owner_contract_refuses_even_with_matching_original_member(self):
        for change in (dict(table='unknown'), dict(issueid='0'), dict(parentcomicid='04'),
                       dict(releasecomicid='5'), dict(issueid=True)):
            with self.subTest(change=change):
                original = copy.deepcopy(self.request['owner'])
                self.request['owner'].update(change); self.build_fixture()
                with self.assertRaisesRegex(ValueError, 'request-owner'): self.call()
                self.request['owner'] = original

    def test_original_capture_contract_refuses_exact_SQL_successor(self):
        for change in (dict(id='9'*64), dict(ddl_id='43'), dict(source_generation='8'*64),
                       dict(cleanup_started=True), dict(cleanup_complete=True)):
            with self.subTest(change=change):
                original = copy.deepcopy(self.pack)
                self.pack.update(change); self.build_fixture()
                with self.assertRaisesRegex(ValueError, 'original-capture'): self.call()
                self.pack = original

    def test_original_member_contract_refuses_exact_SQL_successor(self):
        for change in (dict(kind='annual'), dict(issueid='99'), dict(comicid='99'),
                       dict(releasecomicid='99'), dict(phase='rejected'),
                       dict(ordinary_import_token='2'*64), dict(retained_finalization='3'*64)):
            with self.subTest(change=change):
                original = copy.deepcopy(self.pack['members'][0])
                self.pack['members'][0].update(change); self.build_fixture()
                with self.assertRaisesRegex(ValueError, 'member-owner'): self.call()
                self.pack['members'][0] = original

    def test_original_payload_contract_refuses_exact_SQL_successor(self):
        for change in (dict(destination='/library/foreign.cbz'), dict(destination_sha256='2'*64),
                       dict(sha256='3'*64)):
            with self.subTest(change=change):
                original = copy.deepcopy(self.pack['members'][0])
                self.pack['members'][0].update(change); self.build_fixture()
                with self.assertRaisesRegex(ValueError, 'member-original-payload'): self.call()
                self.pack['members'][0] = original

    def test_native_original_payload_fallback_semantics_are_preserved(self):
        for field in ('destination', 'destination_sha256', 'sha256'):
            self.pack['members'][0].pop(field)
        self.build_fixture(); self.call()

    def test_annual_owner_and_native_eligible_phases(self):
        self.request['owner'].update(table='annuals', releasecomicid='5')
        self.pack['members'][0].update(kind='annual', releasecomicid='5')
        for phase in ('review', 'ready', 'submitted', 'confirmed'):
            with self.subTest(phase=phase):
                self.pack['members'][0]['phase'] = phase
                self.build_fixture(); self.call()


class Mapping(unittest.TestCase):
    def map(self,mounts,child='/config/mylar/workflow.sqlite'):
        return terminal._mapped_host(dict(Mounts=mounts),child)

    def test_original_named_volume_maps_nested_native_DATA(self):
        mount=dict(Type='volume',Name='mylar3_config',Source='/volumes/mylar/_data',Destination='/config',RW=True)
        self.assertEqual(self.map([mount]),Path('/volumes/mylar/_data/mylar/workflow.sqlite'))

    def test_deepest_volume_shadows_bind(self):
        mounts=[dict(Type='bind',Source='/outer',Destination='/config',RW=True),
                dict(Type='volume',Name='data',Source='/volume',Destination='/config/mylar',RW=True)]
        self.assertEqual(self.map(mounts),Path('/volume/workflow.sqlite'))

    def test_nonphysical_shadow_refuses_instead_of_using_bind_ancestor(self):
        mounts=[dict(Type='bind',Source='/outer',Destination='/config',RW=True),
                dict(Type='tmpfs',Source='',Destination='/config/mylar',RW=True)]
        with self.assertRaisesRegex(ValueError,'nonphysical-shadow'):self.map(mounts)

    def test_duplicate_deepest_destinations_refuse(self):
        mounts=[dict(Type='bind',Source=source,Destination='/config',RW=True) for source in ('/one','/two')]
        with self.assertRaisesRegex(ValueError,'ambiguous-configured-mount'):self.map(mounts)

    def test_component_prefix_is_not_a_mount(self):
        with self.assertRaisesRegex(ValueError,'mount-required'):
            self.map([dict(Type='bind',Source='/one',Destination='/config-other',RW=True)])

    def test_original_volume_name_must_be_safe(self):
        for name in (None,'../other','volume,readonly','-bad','é'):
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'volume-name'):
                self.map([dict(Type='volume',Name=name,Source='/one',Destination='/config',RW=True)])

    def test_noncanonical_child_and_source_refuse(self):
        mount=dict(Type='bind',Source='/one',Destination='/config',RW=True)
        for child in ('//config/a','/config/../a','/config/'):
            with self.subTest(child=child),self.assertRaisesRegex(ValueError,'child-path'):self.map([mount],child)
        mount['Source']='//one'
        with self.assertRaisesRegex(ValueError,'nonphysical-shadow'):self.map([mount])

    def test_module_map_alias_selection_is_independent_of_mount_order(self):
        mounts=[dict(Type='bind',Source='/state',Destination=target,RW=False) for target in ('/z','/a')]
        for rows in (mounts,list(reversed(mounts))):
            self.assertEqual(terminal._mapped_child(dict(Mounts=rows),'/state/module-map.json'),'/a/module-map.json')

    def test_shadowed_module_map_uses_only_surviving_alias(self):
        mounts=[dict(Type='bind',Source='/state',Destination=target,RW=False) for target in ('/a','/z')]
        mounts.append(dict(Type='tmpfs',Source='',Destination='/a',RW=True))
        with self.assertRaisesRegex(ValueError,'ambiguous-configured-mount'):
            terminal._mapped_child(dict(Mounts=mounts),'/state/module-map.json')
        mounts[-1]['Destination']='/a/module-map.json'
        self.assertEqual(terminal._mapped_child(dict(Mounts=mounts),'/state/module-map.json'),'/z/module-map.json')

    def test_different_source_shadow_hides_host_alias(self):
        mounts=[dict(Type='bind',Source='/state',Destination='/a',RW=False),
                dict(Type='volume',Name='other',Source='/other',Destination='/a/module-map.json',RW=False)]
        with self.assertRaisesRegex(ValueError,'existing-mount-required'):
            terminal._mapped_child(dict(Mounts=mounts),'/state/module-map.json')

    def test_named_volume_module_map_is_supported(self):
        mounts=[dict(Type='volume',Name='state',Source='/volumes/state/_data',Destination='/state',RW=True)]
        self.assertEqual(terminal._mapped_child(dict(Mounts=mounts),'/volumes/state/_data/module-map.json'),'/state/module-map.json')

    def test_mapping_is_lexical_and_does_not_reach_filesystem(self):
        from unittest.mock import patch
        def forbidden(*args,**kwargs):raise AssertionError('Mapping performed filesystem I/O')
        with patch.object(terminal.os,'stat',forbidden),patch.object(terminal.os,'lstat',forbidden):
            self.assertEqual(self.map([dict(Type='bind',Source='/one',Destination='/config',RW=False)]),
                             Path('/one/mylar/workflow.sqlite'))


class Profile(unittest.TestCase):
    def setUp(self):
        self.original=dict(Image='sha256:'+'a'*64,Mounts=[dict(Type='volume',Name='existing',
            Source='/volumes/existing/_data',Destination='/state',RW=True,Propagation='')],
            Config=dict(User='1000:1000',Env=['PUBLIC_FIXTURE=true']),
            NetworkSettings=dict(Networks={'existing':dict(NetworkID='b'*64)}))
        self.row=copy.deepcopy(self.original)
        self.row['HostConfig']=dict(Privileged=False,CapAdd=None,PortBindings=None,NetworkMode='existing',
            ReadonlyRootfs=True,CapDrop=['ALL'],SecurityOpt=['no-new-privileges'])

    def anchors(self):
        self.row['Mounts'] += [dict(Type='bind',Source=str(terminal.ANCHOR_HOST/name),
             Destination=str(terminal.ANCHOR_PREFIX/name),RW=False,Propagation='rprivate')
             for name in terminal.ANCHOR_NAMES]

    def test_original_named_volume_and_network_are_supported(self):
        self.assertTrue(terminal.selected_profile(self.original,self.row))

    def test_only_complete_fixed_readonly_anchor_set_is_supported(self):
        self.anchors();self.assertTrue(terminal.selected_profile(self.original,self.row,installed_anchors=True))
        self.row['Mounts'].pop()
        with self.assertRaisesRegex(ValueError,'complete-public-anchors'):
            terminal.selected_profile(self.original,self.row,installed_anchors=True)

    def test_same_volume_path_cannot_hide_different_docker_volume_name(self):
        self.row['Mounts'][0]['Name']='other'
        with self.assertRaisesRegex(ValueError,'no-new-mount'):terminal.selected_profile(self.original,self.row)

    def test_network_name_is_not_a_substitute_for_original_network_id(self):
        self.row['NetworkSettings']['Networks']['existing']['NetworkID']='c'*64
        with self.assertRaisesRegex(ValueError,'existing-network'):terminal.selected_profile(self.original,self.row)

    def test_foreign_anchor_or_changed_environment_refuses(self):
        self.anchors();self.row['Mounts'][-1]['Source']='/foreign/public-ed25519.der'
        with self.assertRaisesRegex(ValueError,'exact-public-anchor'):
            terminal.selected_profile(self.original,self.row,installed_anchors=True)
        self.row['Mounts']=self.row['Mounts'][:1];self.row['Config']['Env']=['PUBLIC_FIXTURE=other']
        with self.assertRaisesRegex(ValueError,'environment'):terminal.selected_profile(self.original,self.row)


class Artifact(unittest.TestCase):
    def setUp(self):
        self.request=dict(ddl_id='42-1',pack_id='a'*64,member_id='b'*64)
        self.token=hashlib.sha256(('42-1\0'+'a'*64+'\0'+'b'*64).encode()).hexdigest()
        self.path='/state/日本/'+self.token+'.done.json';parent=str(Path(self.path).parent)
        self.body=dict(version=2,kind='retained-pack-terminal-artifact',token=self.token,
            request=self.request,reply_text='{"success":true}',
            reply_sha256=hashlib.sha256(b'{"success":true}').hexdigest(),catalog_before={},
            frame=dict(files={},nodes={parent:[1,3,0o40700,1000,1000]},absent=[self.path],names={parent:[]},claims={},hashes={},attrs={}),
            **{k:False for k in ('historical_import_ack','ordinary_import_grant','cleanup_grant',
                               'reader_index_acceptance','automatic_replay','reader_resume_grant')})
        self.build()

    def build(self):
        self.data=json.dumps(self.body,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
        self.ref=dict(path=self.path,sha256=hashlib.sha256(self.data).hexdigest(),
                      signature9=[1,2,len(self.data),4,5,0o100600,1000,1000,1])
        self.final=copy.deepcopy(self.body['frame']);self.final['absent'].remove(self.path)
        self.final['files'][self.path]=self.ref['signature9'];self.final['hashes'][self.path]=self.ref['sha256']
        self.final['names'][str(Path(self.path).parent)].append(Path(self.path).name)
        raw=json.dumps(self.final,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
        request=json.dumps(self.request,sort_keys=True,separators=(',',':')).encode()
        self.header=dict(artifact_ref=self.ref,token=self.token,pack_id=self.request['pack_id'],
            member_id=self.request['member_id'],request_sha256=hashlib.sha256(request).hexdigest(),
            reply_sha256=self.body['reply_sha256'],frame_sha256=hashlib.sha256(raw).hexdigest())

    def decode(self):
        return terminal.decode_terminal_artifact(self.data,self.ref,self.header,self.request)

    def test_unicode_uses_actual_worker_ascii_encoding(self):
        body,final=self.decode();self.assertEqual(body,self.body);self.assertEqual(final,self.final)
        self.assertNotEqual(hashlib.sha256(compact(final)).hexdigest(),self.header['frame_sha256'])

    def test_wrong_reply_bytes_refuse(self):
        self.body['reply_text']='{"success":false}';self.build()
        with self.assertRaisesRegex(ValueError,'native-reply'):self.decode()

    def test_boolean_stat_refuses(self):
        self.ref['signature9'][0]=True
        with self.assertRaisesRegex(ValueError,'original-file'):self.decode()

    def test_forged_right_refuses(self):
        self.body['reader_resume_grant']=True;self.build()
        with self.assertRaisesRegex(ValueError,'schema'):self.decode()

    def test_circular_own_file_fact_refuses(self):
        self.body['frame']['files'][self.path]=[1]*9;self.build()
        with self.assertRaises(ValueError):self.decode()

    def test_boolean_header_stat_is_not_equal_to_original_integer(self):
        self.header['artifact_ref']=copy.deepcopy(self.ref)
        self.header['artifact_ref']['signature9'][-1]=True
        with self.assertRaisesRegex(ValueError,'original-header'):self.decode()

    def test_malformed_nested_stat_refuses(self):
        self.body['frame']['files']['/state/foreign']=[True]*9;self.build()
        with self.assertRaisesRegex(ValueError,'stat-vectors'):self.decode()

    def test_duplicate_unrelated_absences_refuse(self):
        self.body['frame']['absent']+=['/state/no','/state/no'];self.build()
        with self.assertRaisesRegex(ValueError,'stat-vectors'):self.decode()

    def test_own_done_path_cannot_claim_a_directory_role(self):
        self.body['frame']['nodes'][self.path]=[1,2,0o40700,1000,1000];self.build()
        with self.assertRaises(ValueError):self.decode()

    def test_missing_artifact_parent_identity_refuses(self):
        self.body['frame']['nodes'].clear();self.build()
        with self.assertRaises(ValueError):self.decode()

    def test_claim_cannot_conflict_with_directory_node_original(self):
        parent=str(Path(self.path).parent)
        self.body['frame']['claims'][parent]=[1,999,0o40700,1000,1000,None];self.build()
        with self.assertRaisesRegex(ValueError,'claim-conflict'):self.decode()

    def test_final_frame_hash_is_bound_to_actual_artifact(self):
        self.header['frame_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'original-header'):self.decode()


if __name__ == '__main__': unittest.main()
