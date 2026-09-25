"""Install authenticated post-processing observations with checked source anchors."""
import ast
from pathlib import Path
import sys
from patch_queue_control import replace_once

MARKER = '# homelab-pp-monitor-v1'


def processor(source):
    if MARKER in source:
        return source
    source = replace_once(source, 'class PostProcessor(object):',
                          'from mylar import pp_monitor\n\nclass PostProcessor(object):')
    source = replace_once(source, '    def Process(self):',
                          '    ' + MARKER + '\n    @pp_monitor.observe\n    def Process(self):')
    ast.parse(source)
    return source


def server(source):
    if MARKER in source:
        return source
    source = replace_once(source, '    def queueManage(self):', '''    # homelab-pp-monitor-v1
    def postProcessing(self):
        return serve_template(templatename='post_processing.html', title='Post-processing')
    postProcessing.exposed = True

    def postProcessingStatus(self):
        from mylar import pp_monitor
        cherrypy.response.headers['Content-Type'] = 'application/json'
        cherrypy.response.headers['Cache-Control'] = 'no-store'
        return json.dumps(pp_monitor.snapshot())
    postProcessingStatus.exposed = True

    def queueManage(self):''')
    ast.parse(source)
    return source


def tagger(source):
    if '# homelab-tag-observer-v1' in source:
        return source
    source = replace_once(source, 'def run(dirName,',
                          'from mylar import archive_monitor\n\n# homelab-tag-observer-v1\n@archive_monitor.tagging\ndef run(dirName,')
    ast.parse(source)
    return source


def api(source):
    if '# homelab-conversion-report-v1' in source:
        return source
    source = replace_once(source, "            result = import_problems.report(kwargs.get('report'))", """            # homelab-conversion-report-v1
            if kwargs.get('processing') is not None:
                from mylar import archive_monitor
                archive_monitor.report(kwargs['processing'])
            result = import_problems.report(kwargs.get('report'))""")
    ast.parse(source)
    return source


def recovery_api(source):
    if '# homelab-local-cache-submit-v1' in source:
        return source
    return replace_once(source, "                                'ddl':         ddl})",
                        "                                'ddl':         ddl,\n"
                        "                                # homelab-local-cache-submit-v1\n"
                        "                                'download_info': None})")


def navigation(source):
    if '<!-- homelab-pp-navigation-v1 -->' in source:
        return source
    return replace_once(source, '<div id="subhead_menu">',
                        '<div id="subhead_menu">\n<!-- homelab-pp-navigation-v1 -->\n'
                        '<a id="menu_link_manualmeta" href="postProcessing">Post-processing</a>\n')


def base(source):
    marker = 'tt.value != "post_processing" && tt.value != "import_problems"'
    if marker in source:
        return source
    before = 'tt.value != "storyarc_detail" && tt.value != "config")'
    return replace_once(source, before, 'tt.value != "storyarc_detail" && ' + marker + ' && tt.value != "config")')


def processing_identity(source):
    marker = '# homelab-ddl-processing-identity-v1'
    if marker in source:
        return source
    anchor = '            if any([self.nzb_name == '
    if source.count(anchor) != 1:
        raise ValueError('Processing handoff changed; review DDL identity patch')
    return source.replace(anchor, '            ' + marker + '\n'
                          '            PostProcess.download_info = self.download_info\n' + anchor, 1)


def main(directory):
    root = Path(directory)
    templates = root.parent/'data/interfaces/default'
    changes = {templates/'base.html': base((templates/'base.html').read_text()),
               root/'cmtagmylar.py': tagger((root/'cmtagmylar.py').read_text()),
               root/'api.py': recovery_api(api((root/'api.py').read_text())),
               root/'process.py': processing_identity((root/'process.py').read_text()),
               root/'PostProcessor.py': processor((root/'PostProcessor.py').read_text()),
               root/'webserve.py': server((root/'webserve.py').read_text())}
    for name in ('manage.html', 'queue_management.html', 'import_problems.html'):
        changes[templates/name] = navigation((templates/name).read_text())
    for path, value in changes.items():
        path.write_text(value)
    for name, destination in [('pp_monitor.py', root), ('archive_monitor.py', root), ('post_processing.html', templates)]:
        (destination/name).write_text(Path(__file__).with_name(name).read_text())
    print('Authenticated post-processing monitor verified')


if __name__ == '__main__':
    main(sys.argv[1])
