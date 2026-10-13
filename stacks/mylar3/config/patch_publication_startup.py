"""Keep held startup available for the authenticated API, without media work."""
import ast
from pathlib import Path
import sys

MARKER = '# homelab-publication-startup-v1'
BUSY_MARKER = '# homelab-publication-startup-busy-v2'
OLD_START = "    from mylar import native_writers\n    if native_writers.startup_status()['state'] != 'ready':\n        return False\n"
OLD_QUEUE = "    from mylar import native_writers\n    if mode == 'start' and native_writers.startup_status()['state'] != 'ready':\n        return False\n"
START_PREFIX = "    from mylar import native_writers\n    startup = native_writers.startup_status()\n    if startup['state'] != 'ready' and (startup['state'], startup.get('reason')) != ('held', 'writer-busy'):\n        return False\n"
QUEUE_PREFIX = "    from mylar import native_writers\n    if mode == 'start':\n        startup = native_writers.startup_status()\n        if startup['state'] != 'ready' and (startup['state'], startup.get('reason')) != ('held', 'writer-busy'):\n            return False\n"


def _wrap_function(source, name, prefix, context):
    tree=ast.parse(source)
    nodes=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name==name]
    if len(nodes)!=1:
        raise ValueError('Expected one native startup function: '+name)
    node=nodes[0];lines=source.splitlines(keepends=True)
    body=''.join(lines[node.body[0].lineno-1:node.end_lineno])
    wrapped=prefix+context+''.join('    '+line if line.strip() else line for line in body.splitlines(keepends=True))
    lines[node.body[0].lineno-1:node.end_lineno]=[wrapped]
    return ''.join(lines)


def patched_source(source):
    if MARKER in source:
        required=(MARKER,'native_writers.initialize_publication()',
                  'with native_writers.operation(startup=True) as publication_writer:',
                  'native_writers.startup_catalog(publication_writer)','native_writers.complete_startup()',
                  'with native_writers.queue_operation(mode):')
        if any(source.count(value)!=1 for value in required):
            raise ValueError('Publication startup patch changed')
        if BUSY_MARKER in source:
            if source.count(BUSY_MARKER)!=1 or source.count(START_PREFIX)!=1 or source.count(QUEUE_PREFIX)!=1:
                raise ValueError('Publication busy startup patch changed')
        else:
            if source.count(OLD_START)!=1 or source.count(OLD_QUEUE)!=1:
                raise ValueError('Expected exact prior startup advisory guards')
            source=BUSY_MARKER+'\n'+source.replace(OLD_START,START_PREFIX,1).replace(OLD_QUEUE,QUEUE_PREFIX,1)
        ast.parse(source);return source
    anchor='        native_writers.initialize()\n'
    if source.count(anchor)!=1:
        raise ValueError('Publication startup no longer matches native initialization')
    source=source.replace(anchor,"""        if native_writers.initialize_publication()['state'] != 'ready':
            _INITIALIZED = True
            logger.warn('Publication authority held; authenticated review required before media work')
            return True
""",1)
    failure="            logger.error('Cannot connect to the database: %s' % e)\n"
    if source.count(failure)!=1:
        raise ValueError('Expected one native database initialization failure boundary')
    source=source.replace(failure,failure+"            return False\n",1)
    first=source.index('        # Initialize the database\n')
    tree=ast.parse(source)
    init=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='initialize']
    if len(init)!=1 or not init[0].lineno<source[:first].count('\n')+1<=init[0].end_lineno:
        raise ValueError('Expected initialization database boundary')
    lines=source.splitlines(keepends=True);start=source[:first].count('\n');end=init[0].end_lineno
    body=lines[start:end]
    if sum(line.strip()=='return True' for line in body)!=1:
        raise ValueError('Expected one native startup completion')
    body=[line.replace('return True','native_writers.complete_startup()\n        return True') if line.strip()=='return True' else line for line in body]
    lines[start:end]=['        with native_writers.operation(startup=True) as publication_writer:\n',
                      '            try:\n',
                      '                native_writers.startup_catalog(publication_writer)\n',
                      '            except Exception:\n',
                      '                _INITIALIZED = True\n',
                      "                logger.warn('Native catalog held; authenticated review required')\n",
                      '                return True\n']+['    '+line if line.strip() else line for line in body]
    source=''.join(lines)
    source=_wrap_function(source,'start',START_PREFIX,'    with native_writers.operation():\n')
    source=_wrap_function(source,'queue_schedule',QUEUE_PREFIX,'    with native_writers.queue_operation(mode):\n')
    source=BUSY_MARKER+'\n'+MARKER+'\n'+source;ast.parse(source);return source


API_BUSY_MARKER = '# homelab-publication-api-startup-busy-v2'
OLD_API_PREFIX = "        # homelab-publication-api-startup-v1\n        from mylar import native_writers\n        if (native_writers.publication_mode()\n                and self.cmd not in native_writers.PASSIVE_API\n                and native_writers.startup_status()['state'] != 'ready'):\n            self.data = self._failureResponse('Publication authority held; authenticated review required')\n            return\n"
API_PREFIX = "        # homelab-publication-api-startup-v1\n        # homelab-publication-api-startup-busy-v2\n        from mylar import native_writers\n        if native_writers.publication_mode() and self.cmd not in native_writers.PASSIVE_API:\n            startup = native_writers.startup_status()\n            busy = ((startup['state'], startup.get('reason')) == ('held', 'writer-busy')\n                    and self.cmd not in native_writers.SELF_ADMITTED_API)\n            if startup['state'] != 'ready' and not busy:\n                self.data = self._failureResponse('Publication authority held; authenticated review required')\n                return\n"

def main(directory):
    root=Path(directory)
    changes={root/'__init__.py':patched_source((root/'__init__.py').read_text())}
    source=(root/'api.py').read_text()
    api_marker='# homelab-publication-api-startup-v1'
    if api_marker not in source:
        anchor="        self.data = 'OK'\n"
        if source.count(anchor)!=1:raise ValueError('Expected one API admission boundary')
        source=source.replace(anchor,API_PREFIX+anchor,1)
    elif API_BUSY_MARKER not in source:
        if source.count(OLD_API_PREFIX)!=1:raise ValueError('Publication API startup predecessor changed')
        source=source.replace(OLD_API_PREFIX,API_PREFIX,1)
    elif source.count(API_PREFIX)!=1:
        raise ValueError('Publication API busy guard changed')
    tree=ast.parse(source)
    classes=[node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='Api']
    if len(classes)!=1:raise ValueError('Expected native API class')
    methods=[node for node in classes[0].body if isinstance(node,ast.FunctionDef) and node.name=='fetchData']
    if len(methods)!=1:raise ValueError('Expected native API execution boundary')
    method=methods[0]
    decorators=[d for d in method.decorator_list if ast.unparse(d)=='native_writers.publication_api_call']
    if not decorators:
        lines=source.splitlines(keepends=True)
        lines.insert(method.lineno-1,' '*method.col_offset+'@native_writers.publication_api_call\n')
        source=''.join(lines)
    elif len(decorators)!=1:raise ValueError('Native API execution guard changed')
    if source.count(api_marker)!=1 or source.count("self.cmd not in native_writers.PASSIVE_API")!=1:
        raise ValueError('Publication API startup guard changed')
    ast.parse(source);changes[root/'api.py']=source
    source=(root/'webserve.py').read_text();web_marker='# homelab-publication-http-startup-v1'
    dispatcher='''    # homelab-publication-http-startup-v1
    def __getattribute__(self, name):
        value = object.__getattribute__(self, name)
        if name != 'api' and callable(value) and getattr(value, 'exposed', False):
            return native_writers.publication_http(value)
        return value

'''
    if web_marker not in source:
        anchor='class WebInterface(object):\n'
        if source.count(anchor)!=1:raise ValueError('Expected native WebInterface')
        source=source.replace(anchor,anchor+'\n'+dispatcher,1)
    if source.count(dispatcher)!=1:raise ValueError('Publication HTTP dispatcher changed')
    ast.parse(source);changes[root/'webserve.py']=source
    for path,source in changes.items():path.write_text(source)


if __name__=='__main__':main(sys.argv[1])
