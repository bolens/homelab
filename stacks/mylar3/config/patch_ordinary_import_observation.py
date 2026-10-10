"""Exact authenticated read-only observation hook; no runtime initialization."""
import ast
from pathlib import Path
import sys

METHOD='''    # homelab-ordinary-import-observation-v1
    def _ordinaryImportObservation(self, **kwargs):
        key = mylar.CONFIG.API_KEY
        if (not mylar.CONFIG.API_ENABLED or not isinstance(key, str) or len(key) != 32
                or self.apikey != key or getattr(self, 'apitype', None) != 'normal'):
            self.data = self._failureResponse('Primary API key required')
            return
        if cherrypy.request.method != 'POST' or set(kwargs) != {'request'}:
            self.data = self._failureResponse('Exact observation POST required')
            return
        from mylar import ordinary_import_observation, publication_native, publication_guard
        try:
            original = ordinary_import_observation.observe(kwargs['request'])
            self.data = self._successResponse(original.payload())
            # Envelope callbacks run before the complete original raw closure.
            original.close(self.data)
        except (ValueError, OSError, RuntimeError, TypeError, KeyError, publication_native.Review, publication_guard.Unavailable):
            self.data = self._failureResponse('Ordinary import observation held')

'''


def patched_source(source):
    if '# homelab-ordinary-import-observation-v1' in source:
        if source.count(METHOD)!=1 or source.count("'ordinaryImportObservation'")!=1:raise ValueError('Observation hook changed')
        ast.parse(source);return source
    tree=ast.parse(source)
    classes=[x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='Api']
    if len(classes)!=1:raise ValueError('Exact native Api required')
    methods=[x for x in classes[0].body if isinstance(x,ast.FunctionDef) and x.name=='_getHealth']
    lists=[x for x in ast.walk(tree) if isinstance(x,ast.List) and all(isinstance(y,ast.Constant) and isinstance(y.value,str) for y in x.elts) and any(y.value=='packCatalog' for y in x.elts)]
    if len(methods)!=1 or len(lists)!=1:raise ValueError('Exact installed dispatcher required')
    node=lists[0]
    if any(y.value=='ordinaryImportObservation' for y in node.elts):raise ValueError('Partial observation installation')
    lines=source.splitlines(keepends=True)
    raw=lines[node.end_lineno-1].encode();lines[node.end_lineno-1]=(raw[:node.end_col_offset-1]+b", 'ordinaryImportObservation'"+raw[node.end_col_offset-1:]).decode()
    lines.insert(methods[0].lineno-1,METHOD)
    answer=''.join(lines);ast.parse(answer)
    if answer.count(METHOD)!=1:raise ValueError('Observation installation drift')
    return answer


def main(directory):
    root=Path(directory);path=root/'api.py'
    source=patched_source(path.read_text())
    (root/'ordinary_import_observation.py').write_bytes(Path(__file__).with_name('ordinary_import_observation.py').read_bytes())
    path.write_text(source)


if __name__=='__main__':main(sys.argv[1])
