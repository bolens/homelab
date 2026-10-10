"""Checked finite self-admitted API hooks; kernels remain disabled."""
import ast
from pathlib import Path
import sys

from publication_retained_api import API_METHODS as METHODS


def patched_source(source):
    if '# homelab-retained-delivery-api-v1' in source:
        if source.count(METHODS)!=1 or source.count("'retainedDeliveryFinalize'")!=1 or source.count("'retainedDeliveryStatus'")!=1:raise ValueError('Retained owning hook changed')
        ast.parse(source);return source
    tree=ast.parse(source);classes=[x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='Api']
    if len(classes)!=1:raise ValueError('Exact native Api required')
    methods=[x for x in classes[0].body if isinstance(x,ast.FunctionDef) and x.name=='_getHealth']
    lists=[x for x in ast.walk(tree) if isinstance(x,ast.List) and all(isinstance(y,ast.Constant) and isinstance(y.value,str) for y in x.elts) and any(y.value=='packCatalog' for y in x.elts)]
    if len(methods)!=1 or len(lists)!=1:raise ValueError('Exact installed dispatcher required')
    node=lists[0]
    if any(x.value in ('retainedDeliveryFinalize','retainedDeliveryStatus') for x in node.elts):raise ValueError('Partial retained hook')
    lines=source.splitlines(keepends=True);line=lines[node.end_lineno-1].encode()
    lines[node.end_lineno-1]=(line[:node.end_col_offset-1]+b", 'retainedDeliveryFinalize', 'retainedDeliveryStatus'"+line[node.end_col_offset-1:]).decode()
    lines.insert(methods[0].lineno-1,METHODS)
    result=''.join(lines);ast.parse(result)
    if result.count(METHODS)!=1:raise ValueError('Retained hook installation drift')
    return result


def main(directory):
    root=Path(directory);path=root/'api.py';result=patched_source(path.read_text())
    (root/'publication_retained_api.py').write_bytes(Path(__file__).with_name('publication_retained_api.py').read_bytes());path.write_text(result)

if __name__=='__main__':main(sys.argv[1])
