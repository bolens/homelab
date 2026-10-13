"""Rendered post-processing navigation and section boundaries."""
from html.parser import HTMLParser
from pathlib import Path
import sys
import unittest


class Sections(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.tables = {}
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'section':
            self.stack.append(attrs.get('aria-labelledby'))
        if tag == 'table':
            self.tables[attrs['id']] = self.stack[-1] if self.stack else None
        if tag == 'a':
            self.links.append(attrs['href'])

    def handle_endtag(self, tag):
        if tag == 'section':
            self.stack.pop()


class PostProcessingUITest(unittest.TestCase):
    def setUp(self):
        if Path('/app/mylar3/lib').is_dir():
            sys.path.insert(0, '/app/mylar3/lib')
        from mako.template import Template
        source = Path(__file__).with_name('post_processing.html').read_text()
        self.template = Template(source.replace('<%inherit file="base.html"/>', ''))

    def test_review_tables_have_separate_named_sections(self):
        parser = Sections()
        parser.feed(self.template.get_def('body').render())
        self.assertEqual(parser.stack, [])
        for table, section in [('pp_recent', 'pp_runs'), ('pp_archives', 'pp_conversion'),
                               ('pp_converted', 'pp_tagging'), ('pp_library', 'pp_library_metadata'),
                               ('pp_imports', 'pp_confirmed')]:
            self.assertEqual(parser.tables[table], section)

    def test_navigation_reaches_review_settings_and_confirmation(self):
        parser = Sections()
        parser.feed(self.template.get_def('body').render())
        for link in ['#pp_library_metadata', '#pp_confirmed', 'importProblems',
                     'queueManage', 'config', 'activity#wf_settings', 'home']:
            self.assertIn(link, parser.links)


if __name__ == '__main__':
    unittest.main()
