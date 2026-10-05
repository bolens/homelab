"""Recover before startup maintenance and guard complete native media operations."""
import ast
from pathlib import Path
import sys
from source_patches import replace_once

MARKER = '# homelab-media-writers-v2'
GUARDS = {
    'api.py': ('_delComic',),
    'webserve.py': ('deleteSeries', 'manualRename', 'ArcWatchlist', 'downloadLocal',
                    'comic_config', 'manual_metatag', 'manageBanner', 'fix_cv_removed'),
    'helpers.py': ('file_ops', 'getImage'),
    'librarysync.py': ('libraryScan',),
    'moveit.py': ('movefiles',),
    'importer.py': ('addComictoDB', 'GCDimport', 'image_it'),
    'updater.py': ('forceRescan',),
}


def guard_source(source, names):
    tree = ast.parse(source)
    edits = []
    for name in names:
        nodes = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]
        if len(nodes) != 1:
            raise ValueError('Expected one native writer: '+name)
        node = nodes[0]
        if not any(ast.unparse(d) == 'native_writers.guard' for d in node.decorator_list):
            # Keep the guard innermost, preserving expose/type decorators.
            edits.append((node.lineno-1, ' '*node.col_offset+'@native_writers.guard\n'))
    lines = source.splitlines(keepends=True)
    for index, value in sorted(edits, reverse=True):
        lines.insert(index, value)
    source = ''.join(lines)
    if 'from mylar import native_writers\n' not in source:
        source = replace_once(source, 'import mylar\n', 'import mylar\nfrom mylar import native_writers\n')
    ast.parse(source)
    return source


TRANSFERS = {
    'webserve.py': (
        ('shutil.move(srciss, renameiss[\'destination_dir\'])',
         "publication_mutation.transfer(srciss, renameiss['destination_dir'], issueid=issue['IssueID'], comicid=cid)"),
        ('shutil.copy2(issuePATH, dstPATH)',
         "publication_mutation.transfer(issuePATH, dstPATH, issueid=IssueID, comicid=comicid, action='copy')"),
    ),
    'moveit.py': (('shutil.move(srcimp, dstimp)',
                  'publication_mutation.transfer(srcimp, dstimp, comicid=comicid)'),),
    'librarysync.py': (
        ('shutil.move(orig_comlocation, dst_path)',
         'publication_mutation.transfer(orig_comlocation, dst_path, comicid=watch_comicid)'),
        ('myDB.upsert("issues", values, control)',
         "publication_rescan.require_entry(watch_the_list['OriginalLocation'], issuechk, {'ComicID': watch_comicid})"),
    ),
}


def mutation_source(source, filename):
    """Install checked preflights at each actual native mutation boundary."""
    pairs=TRANSFERS.get(filename,())
    for call,check in pairs:
        matches=[line for line in source.splitlines() if line.strip()==call]
        if len(matches)!=1:raise ValueError('Expected one native mutation: '+call)
        line=matches[0];indent=line[:len(line)-len(line.lstrip())]
        guarded=indent+check+'\n'+line
        if guarded not in source:source=replace_once(source,line,guarded)
        if source.count(guarded)!=1:raise ValueError('Ambiguous native mutation guard')
    if filename=='helpers.py':
        call="    if action_op == 'copy' or (arc is True and any([action_op == 'copy', action_op == 'move'])):"
        check="    publication_mutation.transfer(path, dst, action=('copy' if arc is True and action_op in ('copy','move') else action_op))\n\n"
        if check+call not in source:source=replace_once(source,call,check+call)
        if source.count(check+call)!=1:raise ValueError('Ambiguous native file policy guard')
    if pairs or filename=='helpers.py':
        imports='from mylar import publication_mutation, publication_rescan\n'
        if imports not in source:source=replace_once(source,'import mylar\n','import mylar\n'+imports)
    ast.parse(source)
    return source


def main(directory):
    root = Path(directory)
    changes = {}
    source = (root/'__init__.py').read_text()
    if MARKER not in source:
        old = '        from mylar import native_writers\n        native_writers.initialize()\n'
        if old in source:
            source = replace_once(source, old, '')
        source = replace_once(source, '        # Initialize the database\n',
            old+'\n        # Initialize the database\n')
        source = MARKER+'\n'+source
        ast.parse(source)
    changes[root/'__init__.py'] = source
    for name, names in GUARDS.items():
        changes[root/name] = mutation_source(guard_source((root/name).read_text(), names),name)
    for path, source in changes.items():
        path.write_text(source)
    for name in ('media_writer.py', 'native_writers.py', 'publication_mutation.py', 'publication_rescan.py'):
        (root/name).write_text(Path(__file__).with_name(name).read_text())


if __name__ == '__main__':
    main(sys.argv[1])
