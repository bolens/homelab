"""Activity layout preserves owning forms and review controls."""
from pathlib import Path
import sys
import unittest


class ActivityUITest(unittest.TestCase):
    def test_body_keeps_review_destinations_and_action_forms(self):
        if Path('/app/mylar3/lib').is_dir():
            sys.path.insert(0,'/app/mylar3/lib')
        from mako.template import Template
        source=Path(__file__).with_name('workflow.html').read_text().replace('<%inherit file="base.html"/>','')
        body=Template(source).get_def('body').render()
        self.assertLess(body.index('<section id="wf_history"'),body.index('<section id="wf_packs"'))
        self.assertLess(body.index('<section id="guided_matches"'),body.index('<section id="wf_settings"'))
        for name in ('wf_filter','wf_handoff_form','wf_policy_form','wf_pack_search','wf_pack_state'):
            self.assertEqual(body.count('id="'+name+'"'),1)
        self.assertIn('type="button" id="wf_pack_clear"',body)
        self.assertIn('aria-label="Activity sections"',body)


if __name__=='__main__':unittest.main()
