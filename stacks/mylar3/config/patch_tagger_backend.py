"""Add a validated, readiness-aware backend choice to native settings."""
import ast
from pathlib import Path
import sys
from source_patches import replace_once

MARKER = '# homelab-tagger-backend-v1'


def configuration(source):
    if MARKER in source:
        return source
    source = replace_once(source, "    'ENABLE_META': (bool, 'Metatagging', False),",
                          "    " + MARKER + "\n    'TAGGER_BACKEND': (str, 'Metatagging', 'legacy'),\n    'ENABLE_META': (bool, 'Metatagging', False),")
    # Validate the whole request before mutating any native settings. This also
    # covers non-web callers and case-insensitive native configuration keys.
    anchor = '        for name, value in list(kwargs.items()):\n'
    source = replace_once(source, anchor, '''        from mylar import tagger_backend
        backend_keys = [key for key in kwargs if key.upper() == 'TAGGER_BACKEND']
        if len(backend_keys) > 1:
            raise ValueError('Duplicate ComicTagger backend preference')
        for key in backend_keys:
            tagger_backend.validate_update(kwargs[key])
''' + anchor)
    ast.parse(source)
    return source


def web(source):
    if MARKER in source:
        return source
    anchor = '                    "ct_tag_cr": helpers.checked(mylar.CONFIG.CT_TAG_CR),'
    source = replace_once(source, anchor, '''                    # homelab-tagger-backend-v1
                    "tagger_backend": mylar.CONFIG.TAGGER_BACKEND,
                    "tagger_backend_status": __import__('mylar.tagger_backend', fromlist=['status']).status(),
''' + anchor)
    anchor = '    def configUpdate(self, **kwargs):\n'
    source = replace_once(source, anchor, anchor + '''        from mylar import tagger_backend
        backend_keys = [key for key in kwargs if key.upper() == 'TAGGER_BACKEND']
        try:
            if len(backend_keys) > 1:
                raise ValueError('Duplicate ComicTagger backend preference')
            for key in backend_keys:
                tagger_backend.validate_update(kwargs[key])
        except ValueError as exc:
            raise cherrypy.HTTPError(400, str(exc))
''')
    ast.parse(source)
    return source


def caller(source):
    if MARKER in source:
        return source
    anchor = '@archive_monitor.tagging\ndef run(dirName, nzbName=None, issueid=None, comversion=None, manual=None, filename=None, module=None, manualmeta=False, readingorder=None, agerating=None):\n'
    source = replace_once(source, anchor, '''# homelab-tagger-backend-v1
@archive_monitor.tagging
def run(dirName, nzbName=None, issueid=None, comversion=None, manual=None, filename=None, module=None, manualmeta=False, readingorder=None, agerating=None):
    from mylar import tagger_backend
    return tagger_backend.dispatch(_legacy_run, dirName, nzbName=nzbName, issueid=issueid,
        comversion=comversion, manual=manual, filename=filename, module=module,
        manualmeta=manualmeta, readingorder=readingorder, agerating=agerating)


def _legacy_run(dirName, nzbName=None, issueid=None, comversion=None, manual=None, filename=None, module=None, manualmeta=False, readingorder=None, agerating=None):
''')
    ast.parse(source)
    return source


def template(source):
    marker = '<!-- homelab-tagger-backend-v1 -->'
    if marker in source:
        return source
    anchor = '                                        <div id="metataggingoptions">\n'
    block = '''                                            <!-- homelab-tagger-backend-v1 -->
                                            <div class="row clearfix">
                                                <label for="tagger_backend">ComicTagger backend</label>
                                                <select id="tagger_backend" name="tagger_backend" aria-describedby="tagger_backend_help">
                                                    <option value="legacy" ${'selected="selected"' if config['tagger_backend'] == 'legacy' else ''}>Legacy (default)</option>
                                                    <option value="modern" ${'selected="selected"' if config['tagger_backend'] == 'modern' else ''} ${'' if config['tagger_backend_status']['modern_available'] else 'disabled="disabled"'}>Modern (experimental)</option>
                                                </select>
                                                <p id="tagger_backend_help" class="tagger-backend-help">${config['tagger_backend_status']['message'] | h} Legacy remains available during testing. Changing the backend applies to the next tagging job.</p>
                                            </div>
'''
    return replace_once(source, anchor, anchor + block)


def main(directory):
    root = Path(directory)
    paths = {root/'config.py':configuration, root/'webserve.py':web, root/'cmtagmylar.py':caller,
             root.parent/'data/interfaces/default/config.html':template}
    changed = {path:patch(path.read_text()) for path,patch in paths.items()}
    for path,source in changed.items():
        path.write_text(source)
    (root/'tagger_backend.py').write_text(Path(__file__).with_name('tagger_backend.py').read_text())


if __name__ == '__main__':
    main(sys.argv[1])
