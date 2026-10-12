"""Never recreate a removed DDL row from a worker status-only update."""
import ast
from pathlib import Path
import sys
MARKER='# homelab-ddl-status-retention-v1'
HELPERS=r'''# homelab-ddl-status-retention-v1
def _ddl_status_original(database, item):
    row = database.selectone('SELECT rowid AS __ddl_generation_rowid, * FROM ddl_info WHERE id=?', [item['id']]).fetchone()
    if row is None or row['status'] not in ('Queued', 'Downloading'):
        return None
    # Release provenance is required; catalog-less native one-offs retain None IDs.
    for key in ('id', 'link', 'mainlink', 'issueid', 'comicid', 'site'):
        if row[key] != item.get(key):
            return None
    if not all(isinstance(row[key], str) and row[key] for key in ('id','link','site','series')):
        return None
    keys = ('id','issueid','comicid','link','mainlink','site','series','year','issues','pack','link_type','__ddl_generation_rowid')
    return tuple((key,row[key]) for key in keys), row['updated_date']


def _ddl_status_update(database, original, values):
    if original is None:
        return None
    if (type(values) is not dict or not set(values) <= {'status','updated_date'}
            or values.get('status') not in ('Queued','Downloading','Completed','Failed')):
        raise ValueError('Unsupported DDL status update')
    if 'updated_date' in values and not isinstance(values['updated_date'], str):
        raise ValueError('Unsupported DDL update date')
    fields, date = original
    keys = tuple(values)
    columns = tuple(('rowid' if key=='__ddl_generation_rowid' else key,value) for key,value in fields)
    result = database.action('UPDATE ddl_info SET '+','.join('"'+key+'"=?' for key in keys)+
        ' WHERE '+ ' AND '.join('"'+key+'" IS ?' for key,value in columns)+
        ' AND updated_date IS ? AND status IN (\'Queued\',\'Downloading\')',
        [values[key] for key in keys]+[value for key,value in columns]+[date])
    if result is None or result.rowcount != 1:
        return None
    return fields, values.get('updated_date', date)


def _ddl_status_delete(database, original):
    if original is None:
        return False
    fields, date = original
    columns = tuple(('rowid' if key=='__ddl_generation_rowid' else key,value) for key,value in fields)
    result = database.action('DELETE FROM ddl_info WHERE '+
        ' AND '.join('"'+key+'" IS ?' for key,value in columns)+
        ' AND updated_date IS ? AND status IN (\'Queued\',\'Downloading\')',
        [value for key,value in columns]+[date])
    return result is not None and result.rowcount == 1

'''

def patched_source(source):
    if MARKER in source:
        if source.count(HELPERS)!=1:raise ValueError('DDL status guard changed')
        tree=ast.parse(source);method=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='ddl_downloader');calls=[n for n in ast.walk(method) if isinstance(n,ast.Call)]
        if (any(isinstance(n.func,ast.Attribute) and n.func.attr=='upsert' for n in calls) or sum(isinstance(n.func,ast.Name) and n.func.id=='_ddl_status_update' for n in calls)!=6 or sum(isinstance(n.func,ast.Name) and n.func.id=='_ddl_status_original' for n in calls)!=1 or sum(isinstance(n.func,ast.Name) and n.func.id=='_ddl_status_delete' for n in calls)!=1):raise ValueError('DDL guarded status sites changed')
        return source
    tree=ast.parse(source);method=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='ddl_downloader');lines=source.splitlines(keepends=True);body=''.join(lines[method.lineno-1:method.end_lineno])
    anchor="            queue_schedule.started(item)\n"
    if body.count(anchor)!=1:raise ValueError('DDL admission boundary changed')
    body=body.replace(anchor,anchor+"            status_original = _ddl_status_original(myDB, item)\n            if status_original is None:\n                queue_control.clear_active(item['id'])\n                continue\n",1)
    changed=0;out=[]
    for line in body.splitlines(keepends=True):
        stripped=line.strip()
        if stripped.startswith("myDB.upsert('ddl_info',"):
            args=ast.parse(stripped).body[0].value.args
            if len(args)!=3 or ast.literal_eval(args[0])!='ddl_info' or ast.unparse(args[2])!='ctrlval':raise ValueError('DDL status writer changed')
            value=ast.unparse(args[1]);indent=line[:len(line)-len(line.lstrip())]
            out.extend([indent+'status_original = _ddl_status_update(myDB, status_original, '+value+')\n',indent+'if status_original is None:\n',indent+"    queue_control.clear_active(item['id'])\n",indent+'    continue\n']);changed+=1
        else:out.append(line)
    if changed!=6:raise ValueError('DDL status writer count changed')
    body=''.join(out)
    external="                    myDB.action('DELETE FROM ddl_info where id=?', [item['id']])\n"
    if body.count(external)!=1:raise ValueError('External DDL failure boundary changed')
    body=body.replace(external,"                    if not _ddl_status_delete(myDB, status_original):\n                        queue_control.clear_active(item['id'])\n                        continue\n",1)
    out=body.splitlines(keepends=True)
    source=''.join(lines[:method.lineno-1])+''.join(out)+''.join(lines[method.end_lineno:])+ '\n'+HELPERS
    ast.parse(source);return source

def main(directory):
    path=Path(directory)/'queues/ddl.py';source=path.read_text();updated=patched_source(source)
    if source!=updated:path.write_text(updated)
if __name__=='__main__':main(sys.argv[1])
