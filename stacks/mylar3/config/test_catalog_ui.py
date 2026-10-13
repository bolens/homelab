"""Native library and Wanted presentation contracts."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from patch_wide_layout import catalog_template

SOURCE = Path(sys.argv.pop(1)) if len(sys.argv) > 1 else None
ROOT = Path(__file__).parent


class CatalogUITest(unittest.TestCase):
    def test_source_drift_is_refused(self):
        with self.assertRaises(ValueError):
            catalog_template('changed source', 'index', '', '')

    @unittest.skipUnless(SOURCE, 'native source required')
    def test_native_routes_survive_and_patch_repeats(self):
        for page in ('index', 'upcoming'):
            source=(SOURCE.parent/'data/interfaces/default'/ (page+'.html')).read_text()
            result=catalog_template(source,page,(ROOT/'catalog_ui.css').read_text(),(ROOT/'catalog_ui.js').read_text())
            self.assertEqual(result,catalog_template(result,page,'',''))
            self.assertIn('comicDetails?ComicID=',result)
            self.assertIn('id="catalog_review"',result)
            if page=='upcoming':
                for route in ('forceSearch','markissues','removeautowant','future_check','detailStoryArc'):
                    self.assertIn(route,result)
                self.assertNotIn('onChange="mark_the_issues()"',result)
                self.assertIn('type="button" id="catalog_apply" disabled',result)

    @unittest.skipUnless(SOURCE, 'native source required')
    def test_both_native_bodies_render_without_live_configuration(self):
        if Path('/app/mylar3/lib').is_dir():
            sys.path.insert(0,'/app/mylar3/lib')
        from mako.template import Template
        mock=SimpleNamespace(CONFIG=SimpleNamespace(SEARCH_TIER_CUTOFF=90),helpers=SimpleNamespace(),db=SimpleNamespace())
        with patch.dict(sys.modules,{'mylar':mock}):
            for page in ('index','upcoming'):
                source=(SOURCE.parent/'data/interfaces/default'/(page+'.html')).read_text()
                result=catalog_template(source,page,'','')
                result=result.replace('<%inherit file="base.html"/>','').replace('<%inherit file="base.html" />','')
                body=Template(result).get_def('body').render(icons={'icon_wanted':'','icon_upcoming':''},
                    upcoming=[],upcoming_count=0,mismatched=[],mismatched_count=0,future_nodata_upcoming=[])
                self.assertIn('id="catalog_review"',body)


if __name__=='__main__':unittest.main()
