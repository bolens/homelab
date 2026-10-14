"""Pure response validation only; no Parent/PID namespace/factory grant."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import copy
import json
from pathlib import Path
import unittest

import comic_nfs_uid_child as c
import comic_nfs_lease_session as s

class Namespace(unittest.TestCase):
    def setUp(self):
        ref=dict(path='/_operation/private/plan.json',sha256='a'*64,signature9=list(range(9)))
        self.bootstrap=dict(version=1,kind='parent-original-current-three-role-bootstrap',plan=ref,source=dict(ref,path='/_operation/private/parent.py'),roles={'retained-fixture':'unchanged opaque values'},ancestors={})
        self.reply=copy.deepcopy(self.bootstrap);self.reply['kind']='parent-original-current-three-role-selectors'
        self.reply['ancestors']={str(p):[1,2,3,1000,1000] for key in ('plan','source') for p in Path(self.reply[key]['path']).parents}
    def test_only_kind_and_complete_genuine_namespace_fields_may_change(self):
        before=copy.deepcopy(self.bootstrap)
        self.assertEqual(json.loads(c.namespace_reply(self.bootstrap,self.reply)),self.reply)
        self.assertEqual(self.bootstrap,before)
    def test_changed_role_ref_or_hash_refuses(self):
        for field in ('plan','source','roles'):
            changed=copy.deepcopy(self.reply);changed[field]={'foreign':'replacement'}
            with self.assertRaises(c.Held):c.namespace_reply(self.bootstrap,changed)
    def test_saved_nonempty_bootstrap_namespace_refuses(self):
        self.bootstrap['ancestors']=copy.deepcopy(self.reply['ancestors'])
        with self.assertRaises(c.Held):c.namespace_reply(self.bootstrap,self.reply)
    def test_missing_extra_wrong_shape_ancestor_refuses(self):
        for ancestors in ({}, {'/foreign':[1,2,3,4,5]},dict(self.reply['ancestors'],**{'/':[1,2,3,4]})):
            changed=copy.deepcopy(self.reply);changed['ancestors']=ancestors
            with self.assertRaises(c.Held):c.namespace_reply(self.bootstrap,changed)

class Epoch(unittest.TestCase):
    def setUp(self):
        self.reply=dict(version=1,kind='parent-original-reader-host-epoch',cid='a'*64,pid=42,started_at='fixture-start',start_ticks=17,native_grant=False,publication_authority=False)
    def test_exact_factual_epoch_and_no_rights(self):
        self.assertIs(s.epoch_reply(self.reply),self.reply)
    def test_boolean_PID_nonpositive_ticks_and_badCID_refuse(self):
        for key,value in (('pid',True),('start_ticks',0),('cid','foreign')):
            with self.assertRaises(s.Held):s.epoch_reply(dict(self.reply,**{key:value}))
    def test_grant_or_extra_selector_refuses(self):
        for reply in (dict(self.reply,native_grant=True),dict(self.reply,publication_authority=True),dict(self.reply,selector='foreign')):
            with self.assertRaises(s.Held):s.epoch_reply(reply)

if __name__=='__main__':unittest.main()
