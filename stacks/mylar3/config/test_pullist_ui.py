"""Weekly UI preserves native week navigation and action contracts."""
from pathlib import Path
from html.parser import HTMLParser
import re
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from patch_pullist_ui import template, TABLE_OPTIONS
from patch_weekly_identity import template as weekly_identity

SOURCE = Path(sys.argv.pop(1)) if len(sys.argv) > 1 else None
ROOT = Path(__file__).parent


def native():
    return (SOURCE if SOURCE.is_file() else SOURCE.parent/'data/interfaces/default/weeklypull.html').read_text()


def scripts(text):
    normalized = text.replace('"sSearch": "Filter releases:"', '"sSearch": ""').replace(TABLE_OPTIONS, '')
    line_starts = [0] + [index + 1 for index, char in enumerate(normalized) if char == '\n']
    class ScriptBlocks(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.blocks = []
            self.start = None
        def source_index(self):
            line, column = self.getpos()
            return line_starts[line - 1] + column
        def handle_starttag(self, tag, attrs):
            if tag == 'script' and self.start is None:
                self.start = self.source_index()
        def handle_endtag(self, tag):
            if tag == 'script' and self.start is not None:
                end = normalized.index('>', self.source_index()) + 1
                self.blocks.append(normalized[self.start:end])
                self.start = None
    parser = ScriptBlocks()
    parser.feed(normalized)
    parser.close()
    if parser.start is not None:
        raise ValueError('Unclosed script in native contract')
    return parser.blocks


class PullistUITest(unittest.TestCase):
    def test_script_contract_uses_html_tag_parsing(self):
        tags = ['<script>first()</script>', '<SCRIPT src="example.js"></SCRIPT>', '<ScRiPt>third()</sCrIpT >', '<script>fourth()</script\t\n bar>', '<script>fifth()</script/>']
        self.assertEqual(scripts('\n'.join(tags)), tags)
    def test_unclosed_script_contract_is_refused(self):
        with self.assertRaises(ValueError):
            scripts('<script>unfinished()')

    def test_changed_source_is_refused(self):
        with self.assertRaises(ValueError):
            template('changed native template', '')

    @unittest.skipUnless(SOURCE, 'native source required')
    def test_native_handlers_and_week_navigation_survive_repeat_installation(self):
        source = native()
        result = template(source, (ROOT/'pullist_ui.css').read_text())
        self.assertEqual(result, template(result, ''))
        self.assertEqual(re.findall(r'onclick="([^"]+)"', source), re.findall(r'onclick="([^"]+)"', result))
        self.assertEqual(scripts(source), scripts(result))
        for route in ('MassWeeklyDownload', 'dump_that_shizzle', 'queueit?', 'queueissue?', 'addbyid?', 'add2futurewatchlist?', 'searchit?', 'torrentit?', 'download_specific_release'):
            self.assertEqual(source.count(route), result.count(route), route)
        for hidden in ('massyear', 'massnumber', 'weeknumber', 'year', 'page_name'):
            self.assertIn('id="'+hidden+'"', result)
        self.assertIn('aria-label="Choose release week"', result)
        self.assertEqual(result.count(TABLE_OPTIONS), 1)
        self.assertIn('"sDom": \'lfr<"pull_table_scroll"t>ip\'', result)
        # This patch is installed before the existing identity label patch.
        after_identity = weekly_identity(result)
        self.assertIn('Release needs review', after_identity)
        self.assertEqual(after_identity, template(after_identity, ''))
        with self.assertRaises(ValueError):
            if 'homelab-pullist-ui-v1' in source:
                template(source.replace('id="pullist_page"', 'id="changed"'), '')
            else:
                template(source.replace('onclick="arrows_page();"', 'onclick="changed();"'), '')

    @unittest.skipUnless(SOURCE, 'native source required')
    def test_body_and_header_render_native_states_and_settings(self):
        from mako.template import Template
        from html.parser import HTMLParser
        class Elements(HTMLParser):
            def __init__(self):
                super().__init__(); self.links=[]; self.rows=0
            def handle_starttag(self, tag, attrs):
                attrs=dict(attrs)
                if tag=='a': self.links.append(attrs)
                if tag=='tr' and 'data-pull-status' in attrs: self.rows+=1
        config=SimpleNamespace(WEEKFOLDER=True, ENABLE_TORRENT_SEARCH=False, ENABLE_32P=False, MODE_32P=False, AUTO_SNATCH=False, SHOW_ICONS=True)
        mock=SimpleNamespace(CONFIG=config, db=SimpleNamespace())
        helpers=SimpleNamespace(checked=lambda value: 'checked' if value else '')
        week={key:'example' for key in ('startweek','endweek','last_update','midweek')}
        week.update(weeknumber=20,year=2026,prev_weeknumber=19,prev_year=2026,next_weeknumber=21,next_year=2026)
        rows=[]
        for index,state in enumerate(('Wanted','Snatched','Downloaded','Skipped','Paused','Mismatched')):
            rows.append(dict(PUBLISHER='Example',COMIC='Example Comic',ISSUE='1',STATUS=state,AUTOWANT=False,HAVEIT='Yes',COMICID='123',ISSUEID=str(index),LINK='https://example.com',VOLUME=None,SERIESYEAR=None,FORMAT='Digital',HASH=None))
        with patch.dict(sys.modules, {'mylar':mock,'mylar.helpers':helpers}):
            source=template(native(),'').replace('<%inherit file="base.html"/>','')
            view=Template(source)
            for icons_enabled in (False,True):
                config.SHOW_ICONS=icons_enabled
                output=view.get_def('body').render(weekinfo=week,wantedcount=2,weeklyresults=rows,pullfilter=True,weekfold='/data/weekly',icons={})
                parsed=Elements(); parsed.feed(output)
                self.assertEqual(parsed.rows,6)
                self.assertEqual(sum(link.get('onclick')=='arrows_page();' for link in parsed.links),2)
                self.assertIn('data-pull-status="Mismatched"',output)
                self.assertIn('pull_badge',output)
                self.assertIn('Filter releases:',source)
                self.assertIn('queueissue?',output)
                actions=[link for link in parsed.links if 'doAjaxCall(' in link.get('onclick','')]
                self.assertTrue(actions)
                self.assertTrue(all(link.get('data-mylar-component')=='button' for link in actions))
                header=view.get_def('headerIncludes').render(weekinfo=week,auto_mass_add='',weekfold='/data/weekly')
                self.assertIn('Add series by publisher',header)
                self.assertIn('for="publishers"',header)
                self.assertIn('Search wanted issues',header)
                self.assertNotIn('download_0day?',header)
            empty=view.get_def('body').render(weekinfo=week,wantedcount=0,weeklyresults=[],pullfilter=True,weekfold='/data/weekly',icons={})
            self.assertIn('0 releases listed',empty)


if __name__ == '__main__':
    unittest.main()
