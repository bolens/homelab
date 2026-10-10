"""Only exact standalone reserved names are blocked before owning handoff."""
import importlib
import json
import unittest
from unittest.mock import patch
import test_publication_retained_delivery as fixture
assert fixture.pkg.__name__=='mylar'  # Explicit host package setup prerequisite.
p=importlib.import_module('mylar.pack_intake')
h=importlib.import_module('mylar.worker_handoff')

class Deny(unittest.TestCase):
    def test_exact_reserved_scalar_fields_top_and_member_before_handoff(self):
        values=[{'phase':'standalone-retained-accepted'},{'record_kind':'retained_standalone'},
            {'kind':'fresh-standalone-retained-finalization'}]
        values.extend({key:None} for key in ('standalone_retained_token','standalone_retained_event','standalone_retained_finalization','fresh_standalone_acceptance'))
        for row in values:
            for body in (dict(row,id='a'*64),{'id':'a'*64,'members':[row]}):
                with self.subTest(body=body),patch.object(h,'admit') as admit,self.assertRaises(ValueError):p.report(json.dumps(body))
                admit.assert_not_called()

    def test_legitimate_generic_metadata_reaches_original_handoff(self):
        class Reached(Exception):pass
        body={'id':'a'*64,'phase':'review','token':'legitimate','event':'metadata','kind':'other','members':[{'phase':'review','token':'legitimate'}]}
        with patch.object(h,'admit',side_effect=Reached) as admit,self.assertRaises(Reached):p.report(json.dumps(body))
        admit.assert_called_once()

if __name__=='__main__':unittest.main()
