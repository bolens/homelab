"""Shared component integration belongs to the base template."""
from pathlib import Path
import unittest
import sys
from patch_wide_layout import component_template, login_template


SOURCE=Path(sys.argv.pop(1)) if len(sys.argv)>1 else None

class ComponentTest(unittest.TestCase):
    def test_integration_updates_once_and_preserves_native_markup(self):
        source='<head><link href="native-theme.css"></head><body><button disabled>Native action</button></body>'
        first=component_template(source,'control styles','control behavior')
        second=component_template(first,'updated styles','updated behavior')
        self.assertEqual(component_template(second,'updated styles','updated behavior'),second)
        self.assertEqual(second.count('<!-- homelab-components-v1 -->'),1)
        self.assertIn('<link href="native-theme.css">',second)
        self.assertIn('<button disabled>Native action</button>',second)
        self.assertNotIn('control behavior',second)

    @unittest.skipUnless(SOURCE,'native template source required')
    def test_native_base_preserves_assets_and_is_repeatable(self):
        source=(SOURCE.parent/'data/interfaces/default/base.html').read_text()
        result=component_template(source,'shared css','shared js')
        self.assertEqual(component_template(result,'shared css','shared js'),result)
        for line in source.splitlines():
            if '<script' in line or '<link' in line:
                self.assertIn(line,result)
        self.assertEqual(result.count('data-mylar-theme='),1)

    @unittest.skipUnless(SOURCE,'native template source required')
    def test_standalone_login_preserves_auth_contract(self):
        source=(SOURCE.parent/'data/interfaces/default/login.html').read_text()
        result=login_template(source,'shared css')
        self.assertEqual(login_template(result,'shared css'),result)
        self.assertIn('action="${http_root}auth/login" method="post"',result)
        self.assertIn('name="from_page" value="${from_page}"',result)
        self.assertIn('autocomplete="current-password"',result)
        self.assertIn('<label for="current_username">',result)
        self.assertEqual(result.count('</form>'),1)

    @unittest.skipUnless(SOURCE,'native template source required')
    def test_maintenance_preserves_native_assets(self):
        source=(SOURCE.parent/'data/interfaces/default/maintenance_base.html').read_text()
        result=component_template(source,'shared css','shared js')
        self.assertEqual(component_template(result,'shared css','shared js'),result)
        for line in source.splitlines():
            if '<script' in line or '<link' in line:
                self.assertIn(line,result)

    def test_ambiguous_base_is_refused(self):
        with self.assertRaises(ValueError):
            component_template('<head></head></head>','','')

    def test_selected_theme_is_escaped_and_keeps_native_assets(self):
        if Path('/app/mylar3/lib').is_dir():
            sys.path.insert(0,'/app/mylar3/lib')
        from mako.template import Template
        source=component_template('<head><link href="interfaces/${interface | h}/css/jquery-ui.css"></head><body></body>','','')
        for theme in ('default','carbon'):
            page=Template(source).render(interface=theme)
            self.assertIn('data-mylar-theme="'+theme+'"',page)
            self.assertIn('interfaces/'+theme+'/css/jquery-ui.css',page)
        page=Template(source).render(interface='carbon" invalid="value')
        self.assertIn('carbon&#34; invalid=&#34;value',page)


if __name__=='__main__':unittest.main()
