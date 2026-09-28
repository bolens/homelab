"""Shared regular/annual identity and library-presence checks."""
from pathlib import Path


def issue(database, issueid):
    rows = database.select('SELECT IssueID,ComicID,ComicName,Status,Location,Deleted FROM annuals WHERE IssueID=?', [str(issueid)])
    if rows:
        return dict(rows[0]) if len(rows) == 1 and not rows[0]['Deleted'] else None
    rows = database.select('SELECT IssueID,ComicID,ComicName,Status,Location FROM issues WHERE IssueID=?', [str(issueid)])
    return dict(rows[0]) if len(rows) == 1 else None


def present(folder, location, status):
    if status not in ('Downloaded', 'Archived') or not folder or not location:
        return False
    try:
        root = Path(folder)
        path = root / location
        if '..' in path.parts or not path.is_relative_to(root):
            return False
        return (not any(p.is_symlink() for p in (path, *path.parents))
                and path.is_file() and path.stat().st_size > 0)
    except (OSError, ValueError):
        return False


def confirmed(database):
    rows = database.select('''
        SELECT i.IssueID,i.ComicID,i.ComicName,i.Status,i.Location,c.ComicLocation
        FROM issues i JOIN comics c ON c.ComicID=i.ComicID
        WHERE i.Status IN ('Downloaded','Archived') AND COALESCE(i.Location,'')!=''
              AND NOT EXISTS (SELECT 1 FROM annuals a WHERE a.IssueID=i.IssueID)
        UNION ALL
        SELECT i.IssueID,i.ComicID,i.ComicName,i.Status,i.Location,c.ComicLocation
        FROM annuals i JOIN comics c ON c.ComicID=i.ComicID
        WHERE i.Status IN ('Downloaded','Archived') AND COALESCE(i.Location,'')!=''
              AND COALESCE(i.Deleted,0)=0
    ''')
    return [r for r in rows if present(r['ComicLocation'], r['Location'], r['Status'])]


def recent_imports(database):
    rows = database.select("""
        SELECT i.IssueID,i.ComicID,i.ComicName AS name,i.Issue_Number AS issue,
               i.Status,i.Location,c.ComicLocation,MAX(s.DateAdded) AS imported_at
        FROM snatched s JOIN issues i ON s.IssueID=i.IssueID
        JOIN comics c ON c.ComicID=i.ComicID
        WHERE s.Status='Post-Processed' AND i.Status IN ('Downloaded','Archived')
              AND NOT EXISTS (SELECT 1 FROM annuals a WHERE a.IssueID=i.IssueID)
        GROUP BY i.IssueID
        UNION ALL
        SELECT i.IssueID,i.ComicID,COALESCE(NULLIF(i.ReleaseComicName,''),i.ComicName || ' Annual'),
               i.Issue_Number,i.Status,i.Location,c.ComicLocation,MAX(s.DateAdded)
        FROM snatched s JOIN annuals i ON s.IssueID=i.IssueID
        JOIN comics c ON c.ComicID=i.ComicID
        WHERE s.Status='Post-Processed' AND i.Status IN ('Downloaded','Archived') AND COALESCE(i.Deleted,0)=0
        GROUP BY i.IssueID
        ORDER BY imported_at DESC LIMIT 100
    """)
    return [r for r in rows if present(r['ComicLocation'],r['Location'],r['Status'])][:25]
