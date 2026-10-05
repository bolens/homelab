"""A real mismatched weekly entry must retain an existing issue decision."""
import ast
import datetime
import os
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from patch_weekly_identity import patched, template


class WeeklyIdentityTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('MYLAR_WORKFLOW_SOURCE'),'actual pinned source required')
    def test_actual_mismatched_weekly_date_preserves_issue_and_annual_status(self):
        source=(Path(os.environ['MYLAR_WORKFLOW_SOURCE'])/'updater.py').read_text()
        source=patched(source);self.assertEqual(patched(source),source)
        function=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='upcoming_update')
        for name in ('Absolute Batman','Absolute Batman annual'):
            for status in ('Wanted','Skipped','Downloaded','Archived','Snatched','Ignored'):
                with self.subTest(name=name,status=status):
                    row=dict(IssueID='1194150',Issue_Number='24',ReleaseDate='2026-09-23',
                             DigitalDate='0000-00-00',IssueDate='2026-11-01',Status=status)
                    db=Mock();db.selectone.return_value.fetchone.return_value=row
                    helpers=Mock();helpers.weekly_info.return_value=dict(startweek='October 04, 2026',endweek='October 10, 2026')
                    mylar=SimpleNamespace(CONFIG=SimpleNamespace(ALT_PULL=2,PULL_REFRESH='2026-10-05 12:00:00',ANNUALS_ON=True),PULLBYFILE=False)
                    namespace=dict(db=SimpleNamespace(DBConnection=lambda:db),mylar=mylar,
                                   logger=Mock(),helpers=helpers,datetime=datetime,re=re)
                    exec(compile(ast.Module(body=[function],type_ignores=[]),'<actual upcoming_update>','exec'),namespace)
                    result=namespace['upcoming_update']('160294',name,'24','2026-10-07',weekinfo=dict(weeknumber='40',year='2026'))
                    self.assertEqual(result,dict(Status='incorrect_match',ComicID='160294',IssueID='1194150'))
                    db.upsert.assert_not_called();db.action.assert_not_called();self.assertEqual(row['Status'],status)

    @unittest.skipUnless(os.environ.get('MYLAR_WORKFLOW_SOURCE'),'actual pinned template required')
    def test_actual_template_explains_review_without_changing_status_contract(self):
        path=Path(os.environ['MYLAR_WORKFLOW_SOURCE']).parent/'data/interfaces/default/weeklypull.html'
        source=template(path.read_text());self.assertEqual(template(source),source)
        self.assertIn("weekly['STATUS'] == 'Mismatched'",source)
        self.assertIn('Release needs review</a>',source);self.assertNotIn('Incorrectly matched series',source)
        self.assertIn('upcoming#tabs-3',source)

    def test_unknown_source_and_template_are_refused(self):
        with self.assertRaises(ValueError):patched('pass\n')
        with self.assertRaises(ValueError):template('<p>unknown layout</p>')


if __name__=='__main__':unittest.main()
