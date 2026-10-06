"""Actual reviewed consumer and authenticated installed route controls."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import library_metadata as library
import publication_derivative as derivative
import publication_guard as guard
import test_publication_derivative as cases
import patch_publication_derivative as adapter


class ReviewedConsumerTests(cases.DerivativeTests):
    def setUp(self):
        super().setUp()
        self.mylar.publication_derivative=derivative
        self.mylar.publication_guard=guard
        self.mylar.library_metadata=library
        self.runtime.existing_store=lambda _:self.store

    def test_adopted_consumer_publishes_once_and_status_preserves_originals(self):
        before=self.source.read_bytes()
        prepared,_=self.adoption()
        result=library.reviewed_derivative(prepared['token'])
        self.assertEqual(self.source.read_bytes(),self.derivative.read_bytes())
        self.assertEqual(Path(self.request['preservation']['original']['path']).read_bytes(),before)
        with patch.object(derivative,'publish',side_effect=AssertionError('status replayed producer')):
            self.assertEqual(library.reviewed_derivative(prepared['token'],status=True),result)

    def test_unadopted_or_changed_current_source_never_enters_mutation(self):
        before=self.source.read_bytes()
        with self.assertRaises(guard.Unavailable):library.reviewed_derivative('f'*64)
        self.assertEqual(self.source.read_bytes(),before)
        prepared,_=self.adoption()
        self.source.write_bytes(b'changed current original')
        with self.assertRaises((guard.Unavailable,library.Review)):
            library.reviewed_derivative(prepared['token'])
        self.assertEqual(self.source.read_bytes(),b'changed current original')
        self.assertFalse((self.writer.root/'nested-derivative-v1.json').exists())

    def test_actual_api_patch_rejects_secondary_key_get_and_extra_fields(self):
        source="""commands=['getVersion', 'checkGithub']
class Api:
    def _getVersion(self, **kwargs): pass
"""
        changed=adapter.api(source)
        self.assertEqual(adapter.api(changed),changed)
        request=SimpleNamespace(method='POST')
        self.mylar.CONFIG.API_ENABLED=True;self.mylar.CONFIG.API_KEY='a'*32
        namespace=dict(mylar=self.mylar,cherrypy=SimpleNamespace(request=request))
        exec(changed,namespace)
        api=namespace['Api']();api.apikey='a'*32;api.apitype='normal'
        api._failureResponse=lambda message:dict(failed=True)
        api._successResponse=lambda value:dict(result=value)
        with patch.object(library,'reviewed_derivative') as consumer:
            for kwargs,method,key,kind in (({'token':'f'*64},'GET','a'*32,'normal'),
                    ({'token':'f'*64},'POST','b'*32,'normal'),
                    ({'token':'f'*64},'POST','a'*32,'extra'),
                    ({'token':'f'*64,'force':True},'POST','a'*32,'normal')):
                request.method=method;api.apikey=key;api.apitype=kind
                api._commitReviewedDerivative(**kwargs)
                self.assertEqual(api.data,{'failed':True})
            consumer.assert_not_called()
            request.method='POST';api.apikey='a'*32;api.apitype='normal'
            api._reviewedDerivativeStatus(token='f'*64)
            consumer.assert_called_once_with('f'*64,status=True)


for name in cases.DerivativeTests.__dict__:
    if name.startswith('test_'):setattr(ReviewedConsumerTests,name,None)

if __name__=='__main__':unittest.main()
