"""Independent literal derivative vectors and actual worker catalog controls."""
from contextlib import closing
import copy
import hashlib
import json
import sqlite3
import unittest
from unittest.mock import patch

import publication_derivative_evidence as derivative
import publication_evidence as evidence
from publication_guard import Unavailable
from test_publication_guard import AuthorityFixture


OWNER={'table':'issues','issueid':'123','parentcomicid':'456','releasecomicid':'456'}
WRONG={'table':'issues','issueid':'999','parentcomicid':'888','releasecomicid':'888'}
OLD_BYTES=[('01.jpg',b'page-one'),('nested/',b''),('nested/ComicInfo.xml',b'<ComicInfo><Title>Original</Title></ComicInfo>')]
NEW_BYTES=[('01.jpg',b'page-one'),('nested/',b''),('nested/SourceMetadata.xml',b'<ComicInfo><Title>Original</Title></ComicInfo>'),
           ('ComicInfo.xml',b'<ComicInfo><Title>Reviewed</Title></ComicInfo>')]


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def checksum(raw):return hashlib.sha256(raw).hexdigest()


def literal_inventory(members):
    rows=[dict(name=name.rstrip('/'),bytes=len(raw),directory=name.endswith('/'),sha256=checksum(raw)) for name,raw in members]
    pages=['01.jpg']
    body=dict(version=1,members=sorted([[row['name'],row['bytes'],row['sha256']] for row in rows
        if not row['directory'] and row['name'] not in ('ComicInfo.xml','ComicBookInfo.json')]),pages=pages)
    return dict(version=1,members=rows,pages=pages,payload=checksum(json.dumps(body,separators=(',',':'),ensure_ascii=False).encode()))


OLD=literal_inventory(OLD_BYTES)
NEW=literal_inventory(NEW_BYTES)
SIGNATURE=[1,10,100,2,3,33152,1000,1000,1]


def census(keys=()):
    return dict(version=1,epoch='e'*64,revision=len(keys),keys=sorted(keys),digest=digest(sorted(keys)))


def observation(owner=OWNER,sha='1'*64):
    return dict(owner=copy.deepcopy(owner),source_sha256=sha,signature=SIGNATURE.copy(),
        catalog=dict(version=1,comic_location='/native-comics',location='correct.cbz',path='/native-comics/correct.cbz',status='Downloaded',deleted=None))


def certificate(prior=None):
    current=census() if prior is None else prior
    source=dict(copy.deepcopy(OLD),source_sha256='1'*64,source_signature=SIGNATURE.copy())
    output=dict(copy.deepcopy(NEW),source_sha256='2'*64,source_signature=[1,11,100,2,3,33152,1000,1000,1])
    mapping=[dict(from_='nested/ComicInfo.xml',to='nested/SourceMetadata.xml')]
    mapping[0]['from']=mapping[0].pop('from_')
    request=dict(version=1,source='/native-comics/correct.cbz',prepared='/private/prepared.cbz',source_sha256='1'*64,
        prepared_sha256='2'*64,owner=copy.deepcopy(OWNER),census=current,mapping=mapping,
        preservation=dict(original=dict(path='/private/original.cbz',signature=SIGNATURE.copy()),
                          restore=dict(path='/restore/original.cbz',signature=[1,12,100,2,3,33152,1000,1000,1])),
        review=dict(path='/private/review.json',sha256='3'*64),backup=dict(
            manifest='/private/manifest.json',manifest_sha256='4'*64,restore='/restore/receipt.json',restore_sha256='5'*64))
    def proof(path,sha,number):return dict(path=path,sha256=sha,signature=[1,number,100,2,3,33152,1000,1000,1])
    backup=dict(manifest=proof('/private/manifest.json','4'*64,40),restore=proof('/restore/receipt.json','5'*64,41),files=[])
    for index,(role,source_path,sha) in enumerate((('source',request['source'],'1'*64),('catalog','/config/mylar.db','6'*64),
            ('workflow','/config/workflow.sqlite','7'*64),('marker','/config/media-writer/publication-v1.json','8'*64))):
        backup['files'].append(dict(role=role,source=proof(source_path,sha,50+index),copies=[
            proof('/backup/'+role,sha,60+index),proof('/restore/'+role,sha,70+index)]))
    backup['files'][0]['source']['signature']=SIGNATURE.copy()
    request['preservation']['original']['signature'][1]=14
    request['preservation']['restore']['signature'][1]=15
    facts=dict(writer=[1,20,1,21],source=dict(path=request['source'],owner=copy.deepcopy(OWNER),inventory=source,
        decision='allowed' if current['revision'] else 'unknown',observed=[observation()] if current['revision'] else []),
        observed=[observation()],
        derivative=output,migration=dict(mapping=mapping,root_sha256=NEW['members'][-1]['sha256'],
            member_order=[name for name,_ in OLD_BYTES],derivative_order=[name for name,_ in NEW_BYTES]),
        prepared=dict(path=request['prepared'],signature=output['source_signature'],sha256='2'*64),
        review=dict(path=request['review']['path'],signature=[1,13,100,2,3,33152,1000,1000,1],sha256='3'*64),backup=backup)
    body=dict(version=1,kind='reviewed-nested-lineage',executable=False,readiness='explicit-adoption-required',request=request,facts=facts)
    return dict(body,token=digest(body))


def record(plan=None,parents=(),rejected=()):
    plan=certificate() if plan is None else plan
    return dict(version=2,epoch='e'*64,prior_revision=plan['request']['census']['revision'],inventory=copy.deepcopy(NEW),
        allowed=[copy.deepcopy(OWNER)],rejected=copy.deepcopy(list(rejected)),
        evidence=dict(sha256=plan['token'],description='Reviewed exact nested metadata migration'),observed=[observation()],
        intent='f'*64,created=2,lineage=dict(version=1,plan=plan,parents=sorted(parents)))


def base():
    return dict(version=1,epoch='e'*64,prior_revision=0,inventory=copy.deepcopy(OLD),allowed=[copy.deepcopy(OWNER)],
        rejected=[copy.deepcopy(WRONG)],evidence=dict(sha256='d'*64,description='Reviewed original'),
        observed=[observation()],intent='a'*64,created=1)


def retoken(plan):
    plan['token']=digest({key:value for key,value in plan.items() if key!='token'});return plan


class LiteralDerivativeTests(unittest.TestCase):
    def test_fixed_payload_tokens_use_version_member_page_order(self):
        self.assertEqual(OLD['payload'],'846ccec1dc0e885f7af66e875603f21c40819105086c57c0ef4c693ffdbadc3e')
        self.assertEqual(NEW['payload'],'bb158f78f215a8844d92d5b891230a0d7e8ad169beea35afb592c35c179db99a')
        evidence.validate(OLD);evidence.validate(NEW)

    def test_fixed_canonical_certificate_and_attestation_digests(self):
        value=certificate();row=record(value)
        self.assertEqual(value['token'],'f6c1ba6ecc45ea4bc52c0856ae34735b55953c21ca871b89ec59a1984f985077')
        self.assertEqual(derivative.attestation(row),'09d582a8d8fd81a2b4cce3421ac7d9083dccd1db3b04906181771238f99fb860')
        self.assertEqual(evidence.attestation(base()),'2c965dc67a0e66a6cc737c98b4a97ba2508f6f30835da19afde2caa8417e8f67')

    def test_unknown_family_has_both_payloads_and_no_invented_wrong_claim(self):
        row=record();key=digest(row);self.assertEqual(derivative.attestation(row),key)
        index,groups=derivative.families({key:row})
        self.assertEqual(index[OLD['payload']],index[NEW['payload']]);self.assertEqual(set(groups[index[OLD['payload']]]),{key})
        bad=record(rejected=[WRONG])
        with self.assertRaises(evidence.Unavailable):derivative.families({digest(bad):bad})

    def test_registered_family_inherits_exact_wrong_owner_across_old_and_new(self):
        before=base();parent=digest(before);row=record(certificate(census([parent])),[parent],[WRONG]);key=digest(row)
        records={parent:before,key:row};index,groups=derivative.families(records)
        self.assertEqual(index[OLD['payload']],index[NEW['payload']]);self.assertEqual(set(groups[index[OLD['payload']]]),set(records))
        self.assertEqual(set(derivative.matched(records,NEW['payload'])),set(records))
        row['rejected']=[]
        with self.assertRaises(evidence.Unavailable):derivative.families({parent:before,digest(row):row})

    def test_missing_foreign_parent_and_payload_join_are_refused(self):
        before=base();parent=digest(before)
        for parents in ([],['b'*64],[parent,'b'*64]):
            row=record(certificate(census([parent])),parents,[WRONG])
            with self.subTest(parents=parents),self.assertRaises(evidence.Unavailable):derivative.families({parent:before,digest(row):row})
        unrelated=dict(before,inventory=copy.deepcopy(NEW),prior_revision=1,intent='b'*64)
        row=record(certificate(census([parent,digest(unrelated)])),[parent],[WRONG])
        with self.assertRaises(evidence.Unavailable):derivative.families({parent:before,digest(unrelated):unrelated,digest(row):row})

    def test_self_predecessor_and_duplicate_output_cycle_are_refused(self):
        row=record();row['lineage']['parents']=[digest(row)]
        with self.assertRaises(evidence.Unavailable):derivative.families({digest(row):row})
        first=record();key=digest(first)
        second=record(certificate(census([key])),[key]);second['intent']='b'*64
        with self.assertRaises(evidence.Unavailable):derivative.families({key:first,digest(second):second})

    def test_member_page_root_and_mapping_drift_require_exact_relation(self):
        for edit in (
            lambda p:p['facts']['derivative']['members'][0].update(sha256='a'*64),
            lambda p:p['facts']['derivative']['pages'].append('ghost.jpg'),
            lambda p:p['facts']['migration'].update(root_sha256='a'*64),
            lambda p:p['request']['mapping'][0].update(to='unrelated.xml'),
            lambda p:p['facts']['migration']['derivative_order'].reverse(),
        ):
            value=certificate();edit(value);retoken(value)
            with self.subTest(edit=edit),self.assertRaises(evidence.Unavailable):derivative.certificate(value)

    def test_full_fact_headers_and_complete_member_order_are_required(self):
        for edit in (
            lambda p:p['facts'].update(writer=None),
            lambda p:p['facts']['prepared'].update(signature=None),
            lambda p:p['facts']['source']['inventory'].update(source_signature=[True]*9),
            lambda p:p['facts']['migration'].update(member_order=[],derivative_order=['ComicInfo.xml']),
            lambda p:p['facts'].update(backup=None),
            lambda p:p['facts'].update(observed=[]),
            lambda p:p['facts']['source'].update(decision='unknown-like-string'),
        ):
            value=certificate();edit(value);retoken(value)
            with self.subTest(edit=edit),self.assertRaises(evidence.Unavailable):derivative.certificate(value)

    def test_unknown_and_allowed_source_history_have_consistent_observations(self):
        for edit in (
            lambda p:p['facts']['source'].update(observed=[observation()]),
            lambda p:p['facts']['source'].update(decision='allowed',observed=[]),
        ):
            value=certificate();edit(value);retoken(value)
            with self.subTest(edit=edit),self.assertRaises(evidence.Unavailable):derivative.certificate(value)

    def test_private_preservation_is_exclusive_and_owned_evidence_has_private_modes(self):
        for edit in (
            lambda p:p['request']['preservation']['restore'].update(signature=p['request']['preservation']['original']['signature']),
            lambda p:p['request']['preservation']['original']['signature'].__setitem__(8,2),
            lambda p:p['request']['preservation']['restore']['signature'].__setitem__(5,33188),
            lambda p:p['facts']['review']['signature'].__setitem__(8,2),
        ):
            value=certificate();edit(value);retoken(value)
            with self.subTest(edit=edit),self.assertRaises(evidence.Unavailable):derivative.certificate(value)

    def test_review_backup_source_digest_and_inode_alias_drift_are_refused(self):
        for edit in (
            lambda p:p['facts']['review'].update(sha256='a'*64),
            lambda p:p['facts']['backup']['files'][0]['copies'][0].update(sha256='a'*64),
            lambda p:p['facts']['backup']['files'][0]['copies'][0].update(signature=p['facts']['backup']['files'][0]['source']['signature']),
            lambda p:p['facts']['backup']['files'].pop(),
            lambda p:p['facts']['prepared'].update(signature=SIGNATURE.copy()),
            lambda p:p['facts']['source']['inventory'].update(source_sha256='a'*64),
        ):
            value=certificate();edit(value);retoken(value)
            with self.subTest(edit=edit),self.assertRaises(evidence.Unavailable):derivative.certificate(value)

    def test_directory_header_order_is_exact_and_canonical_coverage_unique(self):
        value=certificate();self.assertEqual(derivative.certificate(value),(OLD,NEW))
        for edit in (
            lambda p:p['facts']['migration']['member_order'].append('nested'),
            lambda p:p['facts']['migration']['member_order'].__setitem__(1,'01.jpg/'),
            lambda p:p['facts']['migration']['derivative_order'].__setitem__(1,'nested'),
        ):
            value=certificate();edit(value);retoken(value)
            with self.subTest(edit=edit),self.assertRaises(evidence.Unavailable):derivative.certificate(value)


class WorkerDerivativeTests(AuthorityFixture,unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.source=self.archive('correct.cbz',OLD_BYTES);self.candidate=self.archive('candidate.cbz',NEW_BYTES)
        self.candidate.chmod(0o600)
        self.seed();self.append()

    def append(self,*,unknown=False,foreign_header=False):
        if unknown:self.seed(empty=True)
        with self.writer.hold():
            old,records=evidence.registry_snapshot(self.workflow,self.marker)
            observed=evidence.observe_owners(self.catalog,self.writer,[self.owner],[self.native_root],tool_root=self.tool,path_mapper=self.authority.mapped)
            binding=None
            with closing(sqlite3.connect(self.workflow)) as db:
                entries=db.execute("SELECT value FROM records WHERE kind='publication_intent'").fetchall()
                for (raw,) in entries:binding=json.loads(raw)['plan']['binding']
            plan=certificate(old);actual=evidence.inventory(self.source,tool_root=self.tool)
            if foreign_header:plan['request']['census']=census(['a'*64])
            prepared=evidence.inventory(self.candidate,tool_root=self.tool)
            plan['request'].update(source=str(self.native_root/self.source.name),source_sha256=actual['source_sha256'],prepared_sha256=prepared['source_sha256'])
            plan['facts']['source'].update(path=plan['request']['source'],inventory=actual,owner=self.owner)
            plan['facts']['derivative']=prepared;plan['facts']['observed']=observed['observed']
            plan['facts']['source']['observed']=[] if unknown else observed['observed']
            backup_source=plan['facts']['backup']['files'][0]['source']
            backup_source.update(path=plan['request']['source'],sha256=actual['source_sha256'],signature=actual['source_signature'])
            for row in plan['facts']['backup']['files'][0]['copies']:row['sha256']=actual['source_sha256']
            for row in plan['request']['preservation'].values():row['signature'][2]=actual['source_signature'][2]
            for row in plan['facts']['backup']['files'][0]['copies']:row['signature'][2]=actual['source_signature'][2]
            plan['facts']['prepared'].update(sha256=prepared['source_sha256'],signature=prepared['source_signature']);retoken(plan)
            parents=sorted(records);row=record(plan,parents,[] if unknown else [self.rejected]);row['observed']=observed['observed']
            body={key:value for key,value in row.items() if key!='intent'}
            register=dict(version=1,action='register',old=old,binding=binding,body=body)
            intent=digest(register);row['intent']=intent;key=digest(row)
            keys=sorted(old['keys']+[key]);new=census(keys)
            with closing(sqlite3.connect(self.workflow)) as db:
                db.execute('INSERT INTO records VALUES (?,?,?,0)',('publication_intent',intent,json.dumps(dict(plan=register,accepted=True,outcome='committed'))))
                db.execute('INSERT INTO records VALUES (?,?,?,0)',('publication_attestation',key,json.dumps(row)))
                db.execute("UPDATE records SET value=? WHERE kind='publication_census'",(json.dumps(new),));db.commit()
            marker=json.loads(self.marker.read_text());marker['census']=new;self.marker.write_text(json.dumps(marker));self.marker.chmod(0o600)

    def test_actual_catalog_old_and_new_variants_allow_only_registered_owner(self):
        for current in (OLD_BYTES,NEW_BYTES):
            self.archive(self.source.name,current)
            with self.subTest(current=current),self.writer.hold():
                result=self.authority.check(self.candidate,self.owner);self.assertEqual(result['authority']['decision'],'allowed')
                with self.assertRaises(Unavailable):self.authority.check(self.candidate,self.rejected)

    def test_unknown_transition_has_no_wrong_owner_or_unowned_permission(self):
        self.append(unknown=True)
        with self.writer.hold():
            self.assertEqual(self.authority.check(self.candidate,self.owner)['authority']['decision'],'allowed')
            with self.assertRaises(Unavailable):self.authority.check(self.candidate,self.rejected)
            with self.assertRaises(Unavailable):self.authority.unowned_check(self.candidate)

    def test_genuinely_unrelated_payload_remains_unknown_without_family_alias(self):
        different=self.archive('unrelated.cbz',[('01.jpg',b'genuinely different page')])
        with self.writer.hold():
            self.assertEqual(self.authority.check(different,self.owner)['authority']['decision'],'unknown')
            self.authority.unowned_check(different)

    def test_same_revision_deleted_shadow_and_missing_current_claim_hold(self):
        self.sql('INSERT INTO annuals VALUES (?,?,?,?,?,?)',('777','456','789',self.source.name,'Skipped',1))
        with self.writer.hold(),self.assertRaises(Unavailable):self.authority.check(self.candidate,self.owner)
        self.sql('DELETE FROM annuals');self.sql('UPDATE issues SET Location=NULL')
        with self.writer.hold(),self.assertRaises(Unavailable):self.authority.check(self.candidate,self.owner)

    def test_reviewed_census_header_must_match_immutable_registration_predecessor(self):
        self.seed();self.append(foreign_header=True)
        with self.writer.hold(),self.assertRaises(Unavailable):self.authority.admission()

    def test_same_revision_correct_archive_or_catalog_drift_is_held(self):
        self.archive(self.source.name,[('01.jpg',b'unrelated page')])
        with self.writer.hold(),self.assertRaises(Unavailable):self.authority.check(self.candidate,self.owner)
        self.archive(self.source.name,OLD_BYTES)
        self.sql("UPDATE issues SET Status='Wanted'")
        with self.writer.hold(),self.assertRaises(Unavailable):self.authority.check(self.candidate,self.owner)

    def test_source_drift_after_correct_observation_and_foreign_state_are_held(self):
        observe=evidence.observe_owners
        def changed(*args,**kwargs):
            value=observe(*args,**kwargs);self.archive(self.candidate.name,[('01.jpg',b'foreign candidate')]);return value
        with patch.object(evidence,'observe_owners',side_effect=changed),self.writer.hold(),self.assertRaises(Unavailable):
            self.authority.check(self.candidate,self.owner)
        marker=json.loads(self.marker.read_text());marker['census']['epoch']='a'*64;self.marker.write_text(json.dumps(marker))
        with self.writer.hold(),self.assertRaises(Unavailable):self.authority.check(self.candidate,self.owner)

    def test_cleanup_cas_without_filesystem_intent_holds_authority(self):
        for value in ({'phase':'prepared'},dict(version=1,kind='combined_cleanup',token='a'*64,
                 phase='uncertain',binding='b'*64,attempt_digest='c'*64,terminal_digest='d'*64)):
            with self.subTest(value=value):
                with closing(sqlite3.connect(self.workflow)) as db:
                    db.execute("DELETE FROM records WHERE kind='combined_cleanup'")
                    db.execute('INSERT INTO records VALUES (?,?,?,0)',('combined_cleanup','a'*64,json.dumps(value)));db.commit()
                self.assertFalse((self.writer.root/'comic-publication-v1.json').exists())
                with self.writer.hold(),self.assertRaises(Unavailable):self.authority.admission()

    def test_completed_cleanup_passive_admission_does_not_create_pair(self):
        value=dict(version=1,kind='combined_cleanup',token='a'*64,phase='complete',binding='b'*64,
                   attempt_digest='c'*64,terminal_digest='d'*64)
        with closing(sqlite3.connect(self.workflow)) as db:
            db.execute('INSERT INTO records VALUES (?,?,?,0)',('combined_cleanup','a'*64,json.dumps(value)));db.commit()
        before=sorted(str(path.relative_to(self.root)) for path in self.root.rglob('*'))
        with self.writer.hold():self.authority.admission()
        self.assertEqual(sorted(str(path.relative_to(self.root)) for path in self.root.rglob('*')),before)


if __name__=='__main__':unittest.main()
