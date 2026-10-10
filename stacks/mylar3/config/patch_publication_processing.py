"""Checked guards on actual native processing branches and review acknowledgements."""
import ast
from pathlib import Path
import sys

MARKER='# homelab-publication-processing-v1'


def _publication_source(source):
    if MARKER in source:
        if source.count(MARKER)!=1:
            raise ValueError('Native publication processing guards changed')
        tree=ast.parse(source);lines=source.splitlines(keepends=True)
        owned=[node for node in ast.walk(tree) if isinstance(node,ast.Expr)
               and isinstance(node.value,ast.Call)
               and ast.unparse(node.value.func) in ('processing_guard.publication',
                     'processing_guard.placement','processing_guard.displacement','processing_guard.cleanup','processing_guard.cleanup_scope')]
        if len(owned)!=47:raise ValueError('Native publication guard statements changed')
        for node in sorted(owned,key=lambda value:value.lineno,reverse=True):
            del lines[node.lineno-1:node.end_lineno]
        clean=''.join(lines).replace(MARKER+'\n','',1)
        if _publication_source(clean)!=source:
            raise ValueError('Native publication guard arguments or placement changed')
        return source
    tree=ast.parse(source);parents={child:node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    edits={};counts=dict(duplicate=0,tagger=0,scripts=0,placement=0,status=0,cleanup=0,deletion=0,directory=0)
    def ancestry(node,kind):
        while node in parents:
            node=parents[node]
            if isinstance(node,kind):return node
        raise ValueError('Native publication boundary has no enclosing node')
    def add(node,path,issue='issueid',comic=None,*,destination=None,displace=False,clean=False,options=''):
        statement=ancestry(node,ast.stmt);function=ancestry(node,ast.FunctionDef).name
        if comic is None:comic="ml['ComicID']" if function=='Process' else 'comicid'
        if displace:value='processing_guard.displacement(self, '+path+')'
        else:
            method='cleanup' if clean else ('publication' if destination is None else 'placement')
            args=path if destination is None else path+', '+destination
            value='processing_guard.'+method+'(self, '+args+', issueid='+issue + ', comicid='+comic+options+')'
        edits.setdefault(statement.lineno-1,set()).add(' '*statement.col_offset+value+'\n')
    for node in ast.walk(tree):
        if not isinstance(node,ast.Call):continue
        name=ast.unparse(node.func);function=ancestry(node,ast.FunctionDef).name
        if name=='helpers.duplicate_filecheck':
            counts['duplicate']+=1;keywords={value.arg:ast.unparse(value.value) for value in node.keywords}
            add(node,ast.unparse(node.args[0]),keywords['IssueID'],keywords['ComicID'])
        elif name=='cmtagmylar.run':
            counts['tagger']+=1;keywords={value.arg:ast.unparse(value.value) for value in node.keywords}
            path='processing_guard.source('+ast.unparse(node.args[0])+', '+keywords['filename']+')'
            add(node,path,keywords['issueid'])
        elif name=='self._run_pre_scripts':
            counts['scripts']+=1
            add(node,'os.path.join(subpath, orig_filename)')
        elif name=='helpers.file_ops':
            counts['placement']+=1
            options=''.join(', '+value.arg+'='+ast.unparse(value.value) for value in node.keywords)
            add(node,ast.unparse(node.args[0]),destination=ast.unparse(node.args[1]),options=options)
        elif name=='self.tidyup':
            counts['cleanup']+=1
            add(node,'src' if function=='Process_next' else 'grab_src',
                destination='dst' if function=='Process_next' else 'grab_dst',clean=True)
        elif name=='filechecker.validateAndCreateDirectory':
            counts['directory']+=1
            if function=='duplicate_process':
                add(node,"dupeinfo['to_dupe']",displace=True)
            else:
                target=ast.unparse(node.args[0])
                add(node,'src' if target=='comlocation' else ('dst' if function=='Process_next' else 'grab_src'))
        elif name in ('myDB.upsert','updater.foundsearch','updater.totals'):
            counts['status']+=1
            if function=='Process':
                target="(grab_dst if mylar.CONFIG.STORYARCDIR and mylar.CONFIG.COPY2ARCDIR else ml['ComicLocation'])"
            else:
                target='dst' if function=='Process_next' and not (name=='myDB.upsert' and ast.unparse(node.args[0])=="'storyarcs'") else 'grab_dst'
            add(node,target)
        elif name=='myDB.action' and node.args and isinstance(node.args[0],ast.Constant) and node.args[0].value.lower().startswith('delete from nzblog '):
            counts['deletion']+=1
            if function=='Process':
                target="(grab_dst if mylar.CONFIG.STORYARCDIR and mylar.CONFIG.COPY2ARCDIR else ml['ComicLocation'])"
            elif function=='Process_next':
                target='grab_dst' if 'SARC' in node.args[0].value else 'dst'
            else:target='grab_dst'
            add(node,target)
    if counts!=dict(duplicate=3,tagger=4,scripts=1,placement=5,status=11,cleanup=8,deletion=5,directory=6):
        raise ValueError('Native publication branch coverage changed: '+str(counts))
    # Unconditional early guards also cover disabled tagging and run before the
    # native inline storyarc/oneoff routes can invoke any mutating helper.
    anchors={
        "                        ofilename = orig_filename = ml['ComicLocation']\n":
            "                        processing_guard.publication(self, ofilename, issueid=issueid, comicid=ml['ComicID'])\n",
    }
    lines=source.splitlines(keepends=True)
    for index,values in sorted(edits.items(),reverse=True):lines[index:index]=sorted(values)
    source=''.join(lines)
    for anchor,value in anchors.items():
        if source.count(anchor)!=1:raise ValueError('Native publication early boundary changed')
        source=source.replace(anchor,anchor+value,1)
    anchor='            #Run Pre-script\n\n            if mylar.CONFIG.ENABLE_PRE_SCRIPTS:'
    if source.count(anchor)!=1:raise ValueError('Native pre-script boundary changed')
    source=source.replace(anchor,'            processing_guard.publication(self, os.path.join(subpath, orig_filename), issueid=issueid, comicid=comicid)\n'+anchor,1)
    anchor='    def tidyup(self, odir=None, del_nzbdir=False, sub_path=None, cacheonly=False, filename=None):\n'
    if source.count(anchor)!=1:raise ValueError('Native cleanup scope boundary changed')
    source=source.replace(anchor,anchor+'        processing_guard.cleanup_scope(self, odir, del_nzbdir, sub_path, cacheonly, filename)\n',1)
    tree=ast.parse(source)
    function=next(node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=='nzb_or_oneoff_pp')
    matches=[node for node in ast.walk(function) if isinstance(node,ast.If)
             and ast.unparse(node.test)=='mylar.CONFIG.CMTAG_START_YEAR_AS_VOLUME']
    if len(matches)!=1:raise ValueError('Expected one inline oneoff pre-tag boundary')
    node=matches[0];lines=source.splitlines(keepends=True)
    lines.insert(node.lineno-1,' '*node.col_offset+'processing_guard.publication(self, processing_guard.source(location or self.nzb_folder, ofilename), issueid=issueid, comicid=comicid)\n')
    source=MARKER+'\n'+''.join(lines);ast.parse(source);return source


def patched_process(source):
    marker='# homelab-publication-review-outcome-v1'
    blocks=[]
    for indent in (16,12):
        blocks.append(' '*indent+"if any(row.get('mode') == 'review' for row in chk):\n"+' '*(indent+4)+"logger.warn('Publication identity requires review; source retained')\n"+' '*(indent+4)+'return\n')
    blocks.append("        if any(row.get('mode') == 'review' for row in getattr(locals().get('PostProcess'), 'valreturn', [])):\n            return\n\n")
    if marker in source:
        if source.count(marker)!=1 or any(source.count(block)!=1 for block in blocks):
            raise ValueError('Native review outcome patch changed')
        clean=source.replace(marker+'\n','',1)
        for block in blocks:clean=clean.replace(block,'',1)
        if patched_process(clean)!=source:raise ValueError('Native review outcome placement changed')
        return source
    for indent in (16,12):
        anchor='\n'+' '*indent+'chk = ppqueue.get()\n'
        if source.count(anchor)!=1:raise ValueError('Native processing queue boundary changed')
        extra=' '*indent+"if any(row.get('mode') == 'review' for row in chk):\n"+' '*(indent+4)+"logger.warn('Publication identity requires review; source retained')\n"+' '*(indent+4)+'return\n'
        source=source.replace(anchor,anchor+extra,1)
    anchor='        if self.failed is True:\n'
    if source.count(anchor)!=1:raise ValueError('Native failed processing boundary changed')
    extra="        if any(row.get('mode') == 'review' for row in getattr(locals().get('PostProcess'), 'valreturn', [])):\n            return\n\n"
    source=marker+'\n'+source.replace(anchor,extra+anchor,1);ast.parse(source);return source


def main(directory):
    root=Path(directory)
    changes={root/'PostProcessor.py':patched_source((root/'PostProcessor.py').read_text()),
             root/'process.py':patched_process((root/'process.py').read_text())}
    for path,source in changes.items():path.write_text(source)




# The wrapper migrates both unpatched and exact v1 native processing sources.
IMPORT_MARKER='# homelab-ordinary-import-completion-v1'
IMPORT_HOOK='                processing_guard.import_success(self, dst, issueid=issueid, comicid=comicid)\n'
IMPORT_FILE_OP='helpers.file_ops(src, dst)'
IMPORT_FILE_COPY='processing_guard.import_file_ops(self, helpers.file_ops, src, dst)'
IMPORT_CLEANUPS=(
    'self.tidyup(odir, True, filename=os.path.basename(orig_filename))',
    'self.tidyup(odir, True, subpath, filename=os.path.basename(orig_filename))')


def patched_source(source):
    if IMPORT_MARKER in source:
        if source.count(IMPORT_MARKER)!=1 or source.count(IMPORT_HOOK)!=1:
            raise ValueError('Ordinary import completion boundary changed')
        clean=source.replace(IMPORT_MARKER+'\n','',1).replace(IMPORT_HOOK,'',1)
        if clean.count(IMPORT_FILE_COPY)!=2:raise ValueError('Ordinary file placement changed')
        clean=clean.replace(IMPORT_FILE_COPY,IMPORT_FILE_OP)
        for original in IMPORT_CLEANUPS:
            replacement=original.replace('self.tidyup(',
                'processing_guard.defer_import_cleanup(self, self.tidyup, ',1)
            if clean.count(replacement)!=1:raise ValueError('Import cleanup boundary changed')
            clean=clean.replace(replacement,original,1)
        if patched_source(clean)!=source:raise ValueError('Ordinary import hook moved')
        return source
    source=_publication_source(source)
    if source.count(IMPORT_FILE_OP)!=2:raise ValueError('Ordinary file placement changed')
    source=source.replace(IMPORT_FILE_OP,IMPORT_FILE_COPY)
    anchor='                myDB.upsert(updatetable, newVal, ctrlVal)\n'
    if source.count(anchor)!=1:raise ValueError('Ordinary catalog success boundary changed')
    source=source.replace(anchor,anchor+IMPORT_HOOK,1)
    for original in IMPORT_CLEANUPS:
        if source.count(original)!=1:raise ValueError('Ordinary source cleanup boundary changed')
        source=source.replace(original,original.replace('self.tidyup(',
            'processing_guard.defer_import_cleanup(self, self.tidyup, ',1),1)
    source=IMPORT_MARKER+'\n'+source
    tree=ast.parse(source)
    hook=next(n for n in ast.walk(tree) if isinstance(n,ast.Expr)
              and isinstance(n.value,ast.Call) and ast.unparse(n.value.func)=='processing_guard.import_success')
    parents={child:node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    body=parents[hook].body;index=body.index(hook)
    if index==0 or ast.unparse(body[index-1])!='myDB.upsert(updatetable, newVal, ctrlVal)':
        raise ValueError('Ordinary catalog success hook is not adjacent')
    return source

if __name__=='__main__':main(sys.argv[1])
