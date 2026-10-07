"""Closed root supplementation reads exact native witnesses without replay."""
import json
import unittest
from unittest.mock import patch

import publication_guard as guard
import publication_native as native
import publication_transaction as transaction
import test_publication_maintenance as cases


class ClosedSupplementTests(cases.PreservedSupplementTests):
    # Reuse actual native fixture setup, not the producer test methods.
    def read(self, **changes):
        witness=guard.private_json(self.writer.root/'tagger-completed-v1'/('a'*32+'.json'))
        job=witness['job']
        values=dict(token='a'*32,source=self.source,before_sha256=self.before,owner=self.owner,
                    payload=job['payload'],census=job['census'],preservation=job['policy']['preservation'],policy=self.policy)
        values.update(changes)
        with self.runtime.operation():return transaction.closed_supplement(self.writer,**values)

    def test_closed_unknown_root_supplement_is_read_without_new_receipt_or_fence(self):
        result=self.apply();before={p:p.read_bytes() for p in self.writer.root.rglob('*.json')}
        read=self.read()
        self.assertEqual((read['before'],read['after']),(result['before'],result['after']))
        self.assertEqual({p:p.read_bytes() for p in before},before)
        self.assertFalse(transaction.present(self.writer));self.assertFalse(self.writer.fenced(tagger=True))
        self.assertEqual(self.read(),read)

    def test_registered_closed_root_supplement_retains_exact_current_owner_and_census(self):
        prepared=self.prepare(self.call('status')['census']);self.call('register',token=prepared['token'])
        self.apply();read=self.read()
        self.assertEqual(read['owner'],self.owner);self.assertEqual(read['census'],self.call('status')['census'])

    def test_wrong_policy_pair_owner_source_or_before_cannot_read_a_closed_producer(self):
        self.apply()
        for change in ({'policy':{'AgeRating':'Mature'}},{'before_sha256':'f'*64},
                       {'owner':dict(self.owner,issueid='999')},{'source':self.original},
                       {'preservation':{}}):
            with self.assertRaises(native.Review):self.read(**change)

    def test_changed_closed_witness_or_receipt_is_not_an_acknowledgement(self):
        self.apply();path=self.writer.root/'tagger-completed-v1'/('a'*32+'.json')
        before=path.read_bytes();value=json.loads(before);value['job']['policy']['supplement']={'AgeRating':'Mature'}
        path.write_text(json.dumps(value))
        with self.assertRaises(native.Review):self.read(policy={'AgeRating':'Mature'})
        path.write_bytes(before)
        receipt=self.publisher.receipt('a'*32);value=json.loads(receipt.read_bytes());value['after']='f'*64
        receipt.write_text(json.dumps(value))
        with self.assertRaises(native.Review):self.read()

    def test_current_unknown_catalog_path_status_and_source_drift_are_held(self):
        self.apply()
        with self.connection() as db:db.execute("UPDATE issues SET Status='Wanted' WHERE IssueID=?",(self.owner['issueid'],))
        with self.assertRaises(native.Review):self.read()
        with self.connection() as db:db.execute("UPDATE issues SET Status='Downloaded' WHERE IssueID=?",(self.owner['issueid'],))
        self.original.write_bytes(b'changed')
        with self.assertRaises(native.Review):self.read()

    def test_final_source_observation_cannot_hide_a_new_witness_or_fence(self):
        self.apply();witness=self.writer.root/'tagger-completed-v1'/('a'*32+'.json')
        before=witness.read_bytes();actual=native.require
        for outcome in ('witness','fence','copy'):
            calls=[]
            def raced(*args,**kwargs):
                result=actual(*args,**kwargs);calls.append(True)
                if len(calls)==2:
                    if outcome=='witness':
                        value=json.loads(before);value['late_replacement']=True;witness.write_text(json.dumps(value))
                    elif outcome=='fence':self.writer.mark_tagger_pending()
                    else:self.original.write_bytes(b'late private copy replacement')
                return result
            with patch.object(native,'require',side_effect=raced),self.assertRaises(native.Review):self.read()
            witness.write_bytes(before)
            if self.writer.tagger_pending.exists():self.writer.tagger_pending.unlink()
            if outcome=='copy':break

    def test_closed_source_race_after_copy_check_is_held(self):
        self.apply();actual=transaction.preserved_pair;calls=[]
        def raced(*args):
            result=actual(*args);calls.append(True)
            if len(calls)==2:self.source.write_bytes(b'changed after retained-copy check')
            return result
        with patch.object(transaction,'preserved_pair',side_effect=raced),self.assertRaises(native.Review):self.read()


# Inherited producer controls have their own gate.
for name in list(cases.PreservedSupplementTests.__dict__):
    if name.startswith('test_'):setattr(ClosedSupplementTests,name,None)

if __name__=='__main__':unittest.main()
