"""History review preserves native endpoints and requires explicit bulk submission."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from patch_wide_layout import history_template

SOURCE = Path(sys.argv.pop(1)) if len(sys.argv) > 1 else None
ROOT = Path(__file__).parent


class HistoryUITest(unittest.TestCase):
    def test_source_drift_is_refused(self):
        with self.assertRaises(ValueError):
            history_template('<html>Changed source</html>', '', '')

    @unittest.skipUnless(SOURCE, 'native template source required')
    def test_patch_preserves_routes_and_is_repeatable(self):
        source = (SOURCE.parent/'data/interfaces/default/history.html').read_text()
        css = (ROOT/'history_ui.css').read_text()
        javascript = (ROOT/'history_ui.js').read_text()
        result = history_template(source, css, javascript)
        self.assertEqual(history_template(result, css, javascript), result)
        for route in ('clearhistory?status_type=all', 'clearhistory?status_type=Processed',
                      'clearhistory?status_type=Unprocessed', 'clearhistory?status_type=Snatched',
                      'wipenzblog', 'retryissue', 'markissues'):
            self.assertIn(route, result)
        self.assertNotIn('onChange="doAjaxCall', result)
        self.assertNotIn("$('html,body').scrollTop(0)", result)
        self.assertIn('history_apply', result)
        self.assertIn('Clear history / reset status', result)

    @unittest.skipUnless(SOURCE, 'native template source required')
    def test_rendered_body_exposes_selection_and_maintenance_separately(self):
        if Path('/app/mylar3/lib').is_dir():
            sys.path.insert(0, '/app/mylar3/lib')
        from mako.template import Template
        source = (SOURCE.parent/'data/interfaces/default/history.html').read_text()
        result = history_template(source, (ROOT/'history_ui.css').read_text(),
                                  (ROOT/'history_ui.js').read_text())
        with patch.dict(sys.modules, {'mylar': SimpleNamespace(helpers=SimpleNamespace())}):
            page = Template(result.replace('<%inherit file="base.html"/>', '')).get_def('body').render()
        self.assertIn('id="history_apply" type="button" disabled', page)
        self.assertIn('<details class="history_maintenance">', page)
        self.assertIn('Clear the download log?', page)
        self.assertIn('cannot be undone', page)


if __name__ == '__main__':
    unittest.main()
