"""Keep verified conversion identity when filename-only rescans cannot parse it."""
from functools import wraps
from pathlib import Path

# Longest suffix first, matching the normalizer's destination naming contract.
FORMATS = ('.cbt.tar.zst', '.cbt.tar.gz', '.cbt.tar.bz2', '.cbt.tar.xz',
           '.cbt.zst', '.cbt.bz2', '.cbt.gz', '.cbt.xz', '.tar.zst', '.tar.bz2',
           '.tar.gz', '.tar.xz', '.cbz', '.cbr', '.cb7', '.cbt', '.zip', '.rar',
           '.7z', '.tar', '.tgz', '.tbz2', '.txz', '.tzst', '.cba', '.ace')


def destination(path):
    suffix = next((s for s in FORMATS if path.name.lower().endswith(s)), None)
    return path.with_name(path.name[:-len(suffix)]+'.cbz') if suffix else None


def signature(path):
    if (not path.is_absolute() or '..' in path.parts or path.suffix.lower() != '.cbz'
            or any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file()):
        raise ValueError('Unsafe converted path')
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def owners(database, path):
    """Include conflicting/deleted rows so ambiguity cannot become ownership."""
    found = []
    for parent in database.select('SELECT ComicID,ComicLocation FROM comics', []):
        if not parent['ComicLocation'] or Path(parent['ComicLocation']) != path.parent:
            continue
        for table in ('issues', 'annuals'):
            rows = database.select('SELECT IssueID,ComicID,Location,Status'+
                                   (',Deleted' if table == 'annuals' else '')+
                                   ' FROM '+table+' WHERE ComicID=?', [parent['ComicID']])
            for row in rows:
                if not row['Location']:
                    continue
                old = Path(parent['ComicLocation'])/row['Location']
                if '..' in old.parts or old.parent != path.parent:
                    continue
                if old == path or destination(old) == path:
                    found.append(dict(row, table=table, old=str(old)))
    return found


def candidate(database, path):
    rows = owners(database, path)
    if len(rows) != 1:
        if rows:
            raise ValueError('Ambiguous converted ownership')
        return None
    row = rows[0]
    if row.get('Deleted') or row['Status'] not in ('Downloaded', 'Archived'):
        return None
    from mylar import library_status
    authoritative = library_status.issue(database, row['IssueID'])
    if not authoritative or str(authoritative['ComicID']) != str(row['ComicID']):
        raise ValueError('Conflicting converted release identity')
    if row['table'] == 'issues' and database.select('SELECT IssueID FROM annuals WHERE IssueID=?', [row['IssueID']]):
        raise ValueError('Annual identity shadows regular issue')
    old = Path(row['old'])
    if old != path and (old.exists() or old.is_symlink()):
        return None
    return row


def update(database, row, path):
    # The caller holds the shared media writer. Compare catalog state as well.
    database.action('UPDATE '+row['table']+' SET Location=?,Status=? '
                    'WHERE IssueID=? AND ComicID=? AND Location=? AND Status=?'+
                    (' AND COALESCE(Deleted,0)=0' if row['table']=='annuals' else ''),
                    [path.name, 'Downloaded', row['IssueID'], row['ComicID'], row['Location'], row['Status']])


def reconcile(database, name, digest):
    """Use a trusted conversion acknowledgment, never guess from issue numbers."""
    from mylar.converted_tagging import inspect_archive
    path = Path(name)
    before = signature(path)
    row = candidate(database, path)
    if not row:
        return False
    actual, _ = inspect_archive(name)
    if actual != digest or signature(path) != before:
        raise ValueError('Converted output differs from acknowledged archive')
    update(database, row, path)
    return True


def rescan(function):
    """Preserve established converted ownership across filename-only rescans."""
    @wraps(function)
    def wrapped(ComicID, *args, **kwargs):
        if kwargs.get('archive') is not None or (args and args[0] is not None):
            return function(ComicID, *args, **kwargs)
        from mylar import db, workflow, converted_tagging
        database = db.DBConnection()
        prior = []
        for job in workflow.store().active('converted_tag', ('completed', 'tagging', 'retry', 'waiting-settings')):
            if str(job.get('comicid')) != str(ComicID) or not job.get('issueid'):
                continue
            try:
                match = converted_tagging.catalog(job['path'])
                if match and match['issueid'] == job['issueid']:
                    prior.append((Path(job['path']), signature(Path(job['path'])), match))
            except (ValueError, OSError):
                continue
        result = function(ComicID, *args, **kwargs)
        for path, before, match in prior:
            try:
                if signature(path) != before:
                    continue
                row = candidate(database, path)
                if (row and str(row['IssueID']) == match['issueid'] and str(row['ComicID']) == match['comicid']
                        and Path(row['old']) == path and row['Status'] == 'Archived'):
                    update(database, row, path)
            except (ValueError, OSError):
                continue
        return result
    return wrapped
