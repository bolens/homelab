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
                                  db=SimpleNamespace(DBConnection=lambda:self.db),cv=self.cv,mb=Mock(),importer=self.importer)
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

    def test_conflicting_catalog_or_failed_lookup_is_not_repeated(self):
        self.cv.getComic.side_effect=RuntimeError('network unavailable')
        self.assertEqual(self.module.resolve(self.payload)['phase'],'review')
        self.assertEqual(self.module.resolve(self.payload)['phase'],'review')
        self.cv.getComic.assert_called_once()
        self.importer.addComictoDB.assert_not_called()

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
