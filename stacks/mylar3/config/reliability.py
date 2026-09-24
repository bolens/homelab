"""# homelab-reliability-v1: authenticated, non-secret Mylar diagnostics."""
import hashlib
import json
import os
import queue
import time


def snapshot():
    import mylar
    from mylar import db, queue_control
    from mylar.queues import queue_info
    database = db.DBConnection()
    queues = {q.name: {'alive': bool(q.is_alive), 'size': q.size} for q in queue_info()}
    enabled = ['SEARCH-QUEUE']
    if mylar.CONFIG.POST_PROCESSING:
        enabled.append('POST-PROCESS-QUEUE')
    if mylar.CONFIG.ENABLE_DDL:
        enabled.append('DDL-QUEUE')
    nzb_monitor = ((mylar.CONFIG.NZB_DOWNLOADER == 1 and mylar.CONFIG.NZBGET_CLIENT_POST_PROCESSING)
                   or (mylar.CONFIG.NZB_DOWNLOADER == 0 and mylar.CONFIG.SAB_CLIENT_POST_PROCESSING))
    if mylar.CONFIG.POST_PROCESSING and nzb_monitor:
        enabled.append('AUTO-COMPLETE-NZB')
    if (mylar.CONFIG.ENABLE_TORRENTS and mylar.CONFIG.AUTO_SNATCH
            and mylar.OS_DETECT != 'Windows' and mylar.CONFIG.TORRENT_DOWNLOADER in (2, 4)):
        enabled.append('AUTO-SNATCHER')
    downloaded = database.selectone("SELECT count(*) AS n FROM issues WHERE Status='Downloaded'").fetchone()['n']
    active = []
    active_rows = database.select("SELECT * FROM ddl_info WHERE status='Downloading'")
    queue_control.diagnostics(active_rows)
    for row in active_rows:
        paths = [row['tmp_filename']]
        if row['filename']:
            paths.append(os.path.join(mylar.CONFIG.DDL_LOCATION or mylar.CONFIG.CACHE_DIR, row['filename']))
        size = 0
        for path in paths:
            try:
                if path:
                    size = max(size, os.path.getsize(path))
            except OSError:
                pass
        active.append([row['id'], size, row['updated_date']])
    completed = 0
    if mylar.CONFIG.ENABLE_CHECK_FOLDER and mylar.CONFIG.CHECK_FOLDER:
        for directory, dirs, files in os.walk(mylar.CONFIG.CHECK_FOLDER, followlinks=False):
            dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(directory, d))]
            completed += sum(name.lower().endswith(('.cbr', '.cbz', '.cb7', '.cbt')) for name in files)
    return {'completed': completed, 'queues': queues, 'enabled': enabled, 'downloaded': downloaded,
            'processing': bool(mylar.APILOCK), 'ddl_active': sorted(active),
            'ddl_useful': queue_control.useful_progress(),
            'time': time.time(), 'failed_auto': bool(mylar.CONFIG.FAILED_AUTO)}


def report_failed(issueid, comicid, release):
    import mylar
    from mylar import db, Failed, webserve
    database = db.DBConnection()
    issue = database.selectone('SELECT ComicID, Status FROM issues WHERE IssueID=?', [issueid]).fetchone()
    releases = database.select('SELECT ID, PROVIDER, NZBName FROM nzblog WHERE IssueID=?', [issueid])
    if not issue or issue['Status'] == 'Downloaded' or str(issue['ComicID']) != str(comicid) or len(releases) != 1:
        raise ValueError('Issue or release mapping is ambiguous; review quarantine receipt')
    actual = hashlib.sha256(json.dumps([releases[0][key] for key in ('ID', 'PROVIDER', 'NZBName')], ensure_ascii=True).encode()).hexdigest()
    if actual != release:
        raise ValueError('Download release changed; review quarantine receipt')
    if not mylar.CONFIG.FAILED_DOWNLOAD_HANDLING or not mylar.CONFIG.FAILED_AUTO:
        raise ValueError('Automatic failed-download recovery is disabled')
    result = queue.Queue()
    Failed.FailedProcessor(issueid=issueid, comicid=comicid, queue=result).Process()
    entry = result.get_nowait()[0]
    if entry['mode'] == 'retry':
        webserve.WebInterface().queueit(
            mode='want_ann' if entry['annchk'] != 'no' else 'want',
            ComicID=entry['comicid'], IssueID=entry['issueid'],
            ComicName=entry['comicname'], ComicIssue=entry['issuenumber'], manualsearch=True)
    return {'mode': entry['mode']}
