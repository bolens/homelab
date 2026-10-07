"""Checked primary-key API installation for native-owned retained-repeat reconciliation."""
import ast
from pathlib import Path
import sys

MARKER='# homelab-retained-repeat-v1'
METHODS='''    # homelab-retained-repeat-v1
    def _commitRetainedRepeat(self, **kwargs):
        if (not mylar.CONFIG.API_ENABLED or not isinstance(mylar.CONFIG.API_KEY, str)
                or len(mylar.CONFIG.API_KEY) != 32 or not isinstance(self.apikey, str) or self.apikey != mylar.CONFIG.API_KEY
                or getattr(self, 'apitype', None) != 'normal'):
            self.data = self._failureResponse('Primary API key required')
            return
        if cherrypy.request.method != 'POST':
            self.data = self._failureResponse('Repeat protocol requires POST request')
            return
        if set(kwargs) != {'request'} or not isinstance(kwargs['request'], str) or len(kwargs['request'].encode('utf-8')) > 2 * 1024 * 1024:
            self.data = self._failureResponse('Exact bounded repeat request required')
            return
        from mylar import publication_reconcile, publication_native
        try:
            result = publication_reconcile.commit(kwargs.get('request'))
        except (ValueError, OSError, RuntimeError, TypeError, KeyError, publication_native.Review):
            self.data = self._failureResponse('Repeat requires retained evidence review')
        else:
            self.data = self._successResponse(result)

    def _retainedRepeatStatus(self, **kwargs):
        if (not mylar.CONFIG.API_ENABLED or not isinstance(mylar.CONFIG.API_KEY, str)
                or len(mylar.CONFIG.API_KEY) != 32 or not isinstance(self.apikey, str) or self.apikey != mylar.CONFIG.API_KEY
                or getattr(self, 'apitype', None) != 'normal'):
            self.data = self._failureResponse('Primary API key required')
            return
        if (cherrypy.request.method not in ('GET', 'POST') or set(kwargs) != {'token'}
                or not isinstance(kwargs['token'], str) or len(kwargs['token']) != 64
                or any(char not in '0123456789abcdef' for char in kwargs['token'])):
            self.data = self._failureResponse('Exact passive repeat token required')
            return
        from mylar import publication_reconcile, publication_native
        try:
            result = publication_reconcile.status(kwargs.get('token'))
        except (ValueError, OSError, RuntimeError, TypeError, KeyError, publication_native.Review):
            self.data = self._failureResponse('Repeat acknowledgement requires review')
        else:
            self.data = self._successResponse(result)

'''


def patched_source(source):
    tree=ast.parse(source)
    classes=[node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='Api']
    if len(classes)!=1:raise ValueError('Exact native API class required')
    methods=classes[0].body
    lists=[node for node in tree.body if isinstance(node,ast.Assign)
           and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='cmd_list']
    if (len(lists)!=1 or not isinstance(lists[0].value,ast.List)
            or any(not isinstance(item,ast.Constant) or not isinstance(item.value,str) for item in lists[0].value.elts)):
        raise ValueError('Exact literal API dispatch whitelist required')
    names=[item.value for item in lists[0].value.elts];commands=('commitRetainedRepeat','retainedRepeatStatus')
    if len(names)!=len(set(names)) or names.count('getVersion')!=1:raise ValueError('API whitelist boundary changed')
    if MARKER in source:
        if any(names.count(command)!=1 for command in commands):raise ValueError('Repeat whitelist changed')
        for expected in ast.parse('class Api:\n'+METHODS).body[0].body:
            nodes=[node for node in methods if isinstance(node,ast.FunctionDef) and node.name==expected.name]
            if len(nodes)!=1 or ast.dump(nodes[0])!=ast.dump(expected):raise ValueError('Repeat API guard changed')
        return source
    if any(command in names for command in commands):raise ValueError('Partial repeat installation')
    anchors=[node for node in methods if isinstance(node,ast.FunctionDef) and node.name=='_getVersion']
    if len(anchors)!=1 or anchors[0].col_offset!=4:raise ValueError('Repeat API boundary changed')
    lines=source.splitlines(keepends=True)
    lines.insert(anchors[0].lineno-1,METHODS)
    # Insert before the literal list closing bracket using its AST UTF-8 span.
    node=lists[0].value.elts[-1];raw=lines[node.end_lineno-1].encode()
    lines[node.end_lineno-1]=(raw[:node.end_col_offset]+b", 'commitRetainedRepeat', 'retainedRepeatStatus'"+raw[node.end_col_offset:]).decode()
    result=''.join(lines);ast.parse(result);return patched_source(result)


def main(directory):
    root=Path(directory);path=root/'api.py'
    value=patched_source(path.read_text())
    (root/'publication_reconcile.py').write_text(Path(__file__).with_name('publication_reconcile.py').read_text())
    path.write_text(value)


if __name__=='__main__':main(sys.argv[1])
