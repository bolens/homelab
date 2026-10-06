"""Catalog additions are exact and preserve existing/deleted annual intent."""
from pathlib import Path
import json
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from xml.dom.minidom import parseString
from test_pack_records import load
from workflow_store import Store


class CatalogTest(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.store=Store(Path(tmp.name))
        self.db=Mock()
        self.db.selectone.return_value.fetchone.return_value=None
        self.cv=Mock()
        self.cv.getComic.side_effect=lambda volume,kind,*args: (
            {'series':'Space Heroes Annual','comicid':'20','issueid':'200','issue_number':'1','coverdate':'2024-04-01'} if kind=='single_issue' else
            {'ComicName':'Space Heroes Annual','ComicYear':'2024','Type':'Print'} if kind=='comic' else
            {'issuechoice':[{'Issue_ID':'200','Issue_Number':'1'}]})
        self.db.select.return_value=[]
        self.cv.pulldetails.return_value=parseString('<response><description/></response>')
        self.importer=Mock()
        self.mylar=SimpleNamespace(workflow=SimpleNamespace(store=lambda:self.store,policy=lambda:{'pack_automation':True}),
                                  db=SimpleNamespace(DBConnection=lambda:self.db),cv=self.cv,mb=Mock(),importer=self.importer,
                                  worker_handoff=SimpleNamespace(admit=Mock(return_value=None)))
        patcher=patch.dict(sys.modules,{'mylar':self.mylar,'mylar.workflow_store':sys.modules['workflow_store']})
        patcher.start();self.addCleanup(patcher.stop)
        self.module=load('pack_catalog')
        self.payload=json.dumps({'series':'Space Heroes Annual','year':'2024','number':'1','issueid':'200'})

    def test_existing_annual_preserves_status_and_adds_nothing(self):
        self.db.selectone.return_value.fetchone.return_value={'ComicID':'10','Deleted':0}
        result=self.module.resolve(self.payload)
        self.assertEqual((result['phase'],result['comicid']),('ready','10'))
        self.importer.manualAnnual.assert_not_called()
        self.importer.addComictoDB.assert_not_called()

    def test_deleted_annual_never_revives_as_regular_series(self):
        self.db.selectone.return_value.fetchone.return_value={'ComicID':'10','Deleted':1}
        self.assertEqual(self.module.resolve(self.payload)['phase'],'review')
        self.importer.addComictoDB.assert_not_called()

    def test_transient_read_retries_after_backoff_and_recovers(self):
        healthy=self.cv.getComic.side_effect
        with patch.object(self.module.time,'time',return_value=1000):
            self.cv.getComic.side_effect=RuntimeError('network unavailable')
            first=self.module.resolve(self.payload)
            self.assertEqual(first['phase'],'retry');self.assertEqual(first['retry_at'],1300)
            self.assertEqual(self.module.resolve(self.payload),first)
        self.cv.getComic.assert_called_once()
        self.cv.getComic.side_effect=healthy
        self.db.selectone.return_value.fetchone.return_value={'ComicID':'10','Deleted':0}
        with patch.object(self.module.time,'time',return_value=1300):
            self.assertEqual(self.module.resolve(self.payload)['phase'],'ready')
        self.importer.addComictoDB.assert_not_called()

    def test_read_failures_stop_after_five_attempts(self):
        self.cv.getComic.side_effect=RuntimeError('network unavailable')
        for attempt in range(5):
            with patch.object(self.module.time,'time',return_value=1000+attempt*10000):
                result=self.module.resolve(self.payload)
        self.assertEqual(result['phase'],'review');self.assertEqual(result['attempts'],5)
        self.module.resolve(self.payload);self.assertEqual(self.cv.getComic.call_count,5)

    def test_ambiguous_identity_and_uncertain_write_are_never_repeated(self):
        self.importer.addComictoDB.side_effect=RuntimeError('write acknowledgement lost')
        first=self.module.resolve(self.payload)
        self.assertEqual(first['phase'],'review');self.assertTrue(first['mutation_started'])
        self.assertEqual(self.module.resolve(self.payload),first)
        self.importer.addComictoDB.assert_called_once()

    def test_missing_response_is_retryable_but_conflict_is_not(self):
        self.cv.getComic.return_value=None;self.cv.getComic.side_effect=None
        self.assertEqual(self.module.resolve(self.payload)['phase'],'retry')
        payload=json.loads(self.payload);payload['number']='2'
        self.cv.getComic.return_value={'series':'Other','comicid':'20','issueid':'200','issue_number':'2'}
        first=self.module.resolve(json.dumps(payload));self.assertEqual(first['phase'],'review')
        self.assertEqual(self.module.resolve(json.dumps(payload)),first)

    def test_missing_catalog_add_uses_suppression_and_verifies_result(self):
        results=[None,None,{'IssueID':'200'}]
        self.db.selectone.return_value.fetchone.side_effect=lambda:results.pop(0)
        result=self.module.resolve(self.payload)
        self.importer.addComictoDB.assert_called_once_with('20',suppress_addall=True)
        self.assertEqual(result['phase'],'ready')

    def test_missing_id_uses_native_search_signature(self):
        def native_find(name, mode, issue, **kwargs):
            self.assertIsNone(issue)
            return [{'name':'Space Heroes Annual','comicyear':'2024','comicid':'20','type':'Print'}]
        self.mylar.mb.findComic=native_find
        self.db.selectone.return_value.fetchone.return_value={'ComicID':'10','Deleted':0}
        payload=json.loads(self.payload);payload.pop('issueid')
        self.assertEqual(self.module.resolve(json.dumps(payload))['phase'],'ready')

    def test_annual_preparation_failure_retries_before_any_write(self):
        self.cv.pulldetails.return_value=parseString('<response><description><![CDATA[Annual to /space-heroes/4050-10/]]></description></response>')
        self.db.select.return_value=[{'ComicID':'10','ComicName':'Space Heroes'}]
        def row(query,args):
            value={'ComicName':'Space Heroes','ComicYear':'2023'} if query.startswith('SELECT ComicName') else None
            return SimpleNamespace(fetchone=lambda:value)
        self.db.selectone.side_effect=row
        self.importer.manualAnnual.return_value=None
        with patch.object(self.module.time,'time',return_value=1000):
            first=self.module.resolve(self.payload)
        self.assertEqual(first['phase'],'retry');self.assertNotIn('mutation_started',first)
        self.importer.manualAnnual.side_effect=RuntimeError('catalog read unavailable')
        with patch.object(self.module.time,'time',return_value=1300):
            second=self.module.resolve(self.payload)
        self.assertEqual(second['phase'],'retry')
        self.assertTrue(all(c.kwargs.get('manualupd') for c in self.importer.manualAnnual.call_args_list))

    def test_annual_parent_link_does_not_require_matching_publication_year(self):
        self.cv.pulldetails.return_value=parseString('<response><description><![CDATA[Annual to <a href="https://comicvine.gamespot.com/space-heroes/4050-10/">Space Heroes</a>]]></description></response>')
        self.db.select.return_value=[{'ComicID':'10','ComicName':'Space Heroes'}]
        results=[None,None,{'ComicName':'Space Heroes','ComicYear':'2023'},None,{'IssueID':'200'}]
        self.db.selectone.return_value.fetchone.side_effect=lambda:results.pop(0)
        self.importer.manualAnnual.side_effect=lambda **kw: ([{'IssueID':'200','ComicID':'10','ReleaseComicID':'20'}] if kw.get('manualupd') else None)
        result=self.module.resolve(self.payload)
        self.assertEqual((result['phase'],result['comicid']),('ready','10'))
        self.importer.addComictoDB.assert_not_called()
        self.assertEqual(self.importer.manualAnnual.call_args.kwargs['annchk'][0]['Status'],'Skipped')


if __name__=='__main__':unittest.main()
