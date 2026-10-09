"""Private factual vectors: mutable HOST roundtrip vs immutable CHILD image."""
from pathlib import Path
import re

class Held(ValueError):pass

def partition(report,*,path_mapper,sdk_map,mounts,image_sources):
    if type(report) is not dict or report.get('kind')!='archive-one-independent-terminal-observation' or report.get('outcome') not in ('observed-forward','observed-rollback'):raise Held('archive-terminal-kind')
    if any(report.get(k) is not False for k in ('reader_index_acceptance','ordinary_import_grant','publication_acceptance','mutation_authority','automatic_replay')):raise Held('archive-terminal-rights')
    if type(sdk_map) is not dict or not sdk_map or any(type(n) is not str or re.fullmatch(r'[a-z_]+\.py',n) is None or type(v) is not str or re.fullmatch('[0-9a-f]{64}',v) is None for n,v in sdk_map.items()):raise Held('archive-terminal-SDK-shape')
    # Exact immutable image whitelist; every other original must HOST roundtrip.
    image_paths={'/app/mylar3/mylar/'+name for name in sdk_map}
    if type(image_sources) is not dict or set(image_sources)!={'/app/mylar3/mylar/config.py','/app/mylar3/Mylar.py'}:raise Held('archive-terminal-image-source-provenance')
    for path,ref in image_sources.items():
        if type(ref) is not dict or ref.get('path')!=path or type(ref.get('signature9')) not in (list,tuple) or len(ref['signature9'])!=9 or not all(type(x) is int for x in ref['signature9']):raise Held('archive-terminal-image-ref')
    image_originals={path:tuple(ref['signature9']) for path,ref in image_sources.items()}
    image_paths.update(image_sources)
    image_nodes={str(p) for path in image_paths for p in Path(path).parents}
    for mount in mounts:
        if type(mount) is not dict or set(mount)!={'host','child','write'} or type(mount['write']) is not bool:raise Held('archive-terminal-mount')
        child=Path(mount['child'])
        if not child.is_absolute() or any(child==protected or child in protected.parents or protected in child.parents for protected in map(Path,('/app','/lsiopy','/usr','/lib','/lib64','/bin','/sbin','/opt/archiving-utils','/etc'))):raise Held('archive-terminal-image-overlay')
        image_nodes.update(str(p) for p in child.parents)
    v=report.get('original_vectors')
    if type(v) is not dict or set(v)!={'files','nodes','claims','censuses','absent'}:raise Held('archive-terminal-vector-shape')
    files={};nodes={};claims={};names={};absent=set();child_files={};child_nodes={}
    def add(target,path,value):
        if path in target and target[path]!=value:raise Held('archive-terminal-vector-conflict')
        target[path]=value
    def rows(key,length,allow_none=False):
        result=[]
        if type(v[key]) not in (list,tuple) or len(v[key])>100000:raise Held('archive-terminal-vector-bound')
        for row in v[key]:
            if type(row) not in (list,tuple) or len(row)!=2 or type(row[0]) is not str or not Path(row[0]).is_absolute() or '..' in Path(row[0]).parts:raise Held('archive-terminal-vector-row')
            value=row[1]
            if value is None and allow_none:result.append((row[0],None));continue
            if type(value) not in (list,tuple) or len(value)!=length or any(type(x) is not int for x in value):raise Held('archive-terminal-vector-types')
            result.append((row[0],tuple(value)))
        return tuple(result)
    file_rows=rows('files',9);node_rows=rows('nodes',5);claim_rows=rows('claims',9,True)
    # Freeze all original tuples before the first caller mapping callback.
    census_rows=tuple((row[0],tuple(row[1])) for row in v['censuses']);absence_rows=tuple(v['absent'])
    for path,value in file_rows:
        if path in image_paths:
            if path in image_originals and image_originals[path]!=value:raise Held('archive-terminal-image-original')
            add(child_files,path,value)
        else:add(files,str(path_mapper(path)),value)
    for path,value in node_rows:
        try:host=str(path_mapper(path))
        except (ValueError,KeyError):
            if path not in image_nodes:raise Held('archive-terminal-unmapped-node') from None
            add(child_nodes,path,value)
        else:add(nodes,host,value)
    for path,value in claim_rows:add(claims,str(path_mapper(path)),value)
    for path in absence_rows:
        if type(path) is not str or not Path(path).is_absolute():raise Held('archive-terminal-absence-path')
        absent.add(str(path_mapper(path)))
    for path,value in census_rows:
        if type(path) is not str or not Path(path).is_absolute() or any(type(x) is not str or '/' in x or x in ('','.','..') for x in value) or len(set(value))!=len(value):raise Held('archive-terminal-census-types')
        add(names,str(path_mapper(path)),tuple(sorted(value)))
    return {'files':files,'nodes':nodes,'claims':claims,'absent':tuple(sorted(absent)),'censuses':names,'child_image_files':child_files,'child_image_nodes':child_nodes,'publication_acceptance':False,'mutation_authority':False}
