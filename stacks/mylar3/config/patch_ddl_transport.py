"""Wire discovery-only sessions and a validated next-operation preference."""
import ast
from pathlib import Path
import sys
from source_patches import replace_once

MARKER = '# homelab-ddl-transport-v1'


def configuration(source):
    if MARKER in source: return source
    source = replace_once(source, "    'ENABLE_DDL': (bool, 'DDL', False),",
        "    " + MARKER + "\n    'DDL_DISCOVERY_BACKEND': (str, 'DDL', 'requests'),\n    'ENABLE_DDL': (bool, 'DDL', False),")
    anchor = '        for name, value in list(kwargs.items()):\n'
    return replace_once(source, anchor, '''        transport_keys = [key for key in kwargs if key.upper() == 'DDL_DISCOVERY_BACKEND']
        if transport_keys:
            from mylar import ddl_transport
            if len(transport_keys) != 1:
                raise ValueError('Duplicate DDL discovery backend preference')
            ddl_transport.validate_update(kwargs[transport_keys[0]])
''' + anchor)


def web(source):
    if MARKER in source: return source
    source = replace_once(source, '                    "enable_ddl": helpers.checked(mylar.CONFIG.ENABLE_DDL),',
        '''                    # homelab-ddl-transport-v1
                    "ddl_discovery_backend": mylar.CONFIG.DDL_DISCOVERY_BACKEND,
                    "ddl_transport_status": __import__('mylar.ddl_transport', fromlist=['status']).status(),
                    "enable_ddl": helpers.checked(mylar.CONFIG.ENABLE_DDL),''')
    anchor = '    def configUpdate(self, **kwargs):\n'
    return replace_once(source, anchor, anchor + '''        transport_keys = [key for key in kwargs if key.upper() == 'DDL_DISCOVERY_BACKEND']
        if transport_keys:
            from mylar import ddl_transport
            try:
                if len(transport_keys) != 1:
                    raise ValueError('Duplicate DDL discovery backend preference')
                ddl_transport.validate_update(kwargs[transport_keys[0]])
            except ValueError as exc:
                raise cherrypy.HTTPError(400, str(exc))
''')


def caller(source):
    if MARKER in source: return source
    source = MARKER + '\nfrom mylar import ddl_transport\n' + source
    # Deliberately do not change __init__ or downloadit: self.session remains Requests.
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    for node in sorted((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                        and n.name in ('cookie_receipt', 'search', 'loadsite', 'perform_search_queries')),
                       key=lambda n:n.lineno, reverse=True):
        block = ''.join(lines[node.lineno-1:node.end_lineno]).replace('self.session.', 'self._discovery_session.')
        lines[node.lineno-1:node.end_lineno] = [block]
    return ''.join(lines) + '\n' + '\n'.join(
        'GC.'+name+' = ddl_transport.discovery(GC.'+name+')'
        for name in ('cookie_receipt', 'search', 'loadsite')) + '\n'


def template(source):
    marker = '<!-- homelab-ddl-transport-v1 -->'
    if marker in source: return source
    anchor = '                                   <div id="ddl_providers">\n'
    return replace_once(source, anchor, anchor + '''                                       <!-- homelab-ddl-transport-v1 -->
                                       <div class="row clearfix">
                                           <label for="ddl_discovery_backend">DDL discovery transport</label>
                                           <select id="ddl_discovery_backend" name="ddl_discovery_backend" aria-describedby="ddl_transport_help">
                                               <option value="requests" ${'selected="selected"' if config['ddl_discovery_backend'] == 'requests' else ''}>Requests (default)</option>
                                               <option value="curl" ${'selected="selected"' if config['ddl_discovery_backend'] == 'curl' else ''} ${'' if config['ddl_transport_status']['curl_available'] else 'disabled="disabled"'}>Curl (experimental)</option>
                                           </select>
                                           <p id="ddl_transport_help" class="tagger-backend-help">${config['ddl_transport_status']['message'] | h} Changes apply to the next discovery operation; active work retains its transport.</p>
                                       </div>
''')


def main(directory):
    root = Path(directory)
    for path, patch in [(root/'config.py', configuration), (root/'webserve.py', web),
                        (root/'getcomics.py', caller), (root.parent/'data/interfaces/default/config.html', template)]:
        value = patch(path.read_text())
        if path.suffix == '.py': ast.parse(value)
        path.write_text(value)
    for name in ('ddl_transport.py', 'ddl_transport_worker.py'):
        (root/name).write_text(Path(__file__).with_name(name).read_text())


if __name__ == '__main__': main(sys.argv[1])
