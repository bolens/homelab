"""Bounded maintenance reports and an authenticated import troubleshooting view."""
import json
import os
import re
from pathlib import Path
import time
from urllib.parse import urlencode

ACTIONS = {
    'quarantine_resolved': ('Quarantined download replaced', 'A replacement is recorded in the library. The corrupt source and its receipt remain in private recovery storage.'),
    'ready': ('Ready to import', 'Use Manual Post-Processing for the completed download folder.'),
    'import_cleanup': ('Mylar reports downloaded; source retained', 'Waiting for verified duplicate cleanup. Review filenames if this persists; the retained source has not been deleted.'),
    'import_queued': ('Automatic import submitted', 'Waiting for Mylar post-processing. The original download is retained.'),
    'import_review': ('Automatic import needs review', 'The previous submission is unconfirmed or took over 30 minutes. Check post-processing before retrying.'),
    'pdf_rendering': ('PDF conversion pending', 'Original PDF preserved; page rendering runs outside the shared media writer lock before import.'),
    'import_unsupported': ('Matched; format needs conversion', 'Automatic recovery currently submits CBZ and CBR files only. The source is retained.'),
    'unmatched': ('No unique issue match', 'Automatic matching found no unambiguous identity. Check series, volume, year, and issue number.'),
    'validation': ('Could not validate archive', 'Inspect the retained source and decoder availability.'),
    'quarantine': ('Corrupt archive quarantined', 'Review the recovery copy and replacement-search status.'),
    'retry_unconfirmed': ('Replacement request unconfirmed', 'Check Mylar history before retrying to avoid a duplicate search.'),
    'failed': ('Maintenance check failed', 'Check maintenance health and storage access.'),
}


def next_steps(row):
    """Link to existing review screens without initiating recovery work."""
    kind = row.get('kind', '')
    phase = row.get('phase', '')
    steps = []
    if kind == 'quarantine_resolved':
        steps.append(('Verify library import', 'postProcessing#pp_confirmed'))
    elif row.get('source_token'):
        steps.append(('Review issue matches', 'activity?' + urlencode({'source_token': row['source_token']}) + '#guided_matches'))
    elif kind in ('ready', 'import_queued', 'import_review', 'import_cleanup', 'snatched'):
        steps.append(('Check post-processing', 'postProcessing#pp_work'))
    elif kind in ('pdf_rendering', 'import_unsupported', 'validation'):
        steps.append(('Review conversion status', 'postProcessing#pp_conversion'))
    elif kind in ('quarantine', 'retry_unconfirmed', 'failed_download'):
        steps.append(('Check download queue', 'queueManage'))
    elif kind == 'unmatched':
        steps.append(('Review import matches', 'activity#guided_matches'))
    else:
        steps.append(('Check processing status', 'postProcessing'))
    if phase in ('retry_queued', 'retry_stopped', 'retry_unconfirmed') and kind != 'quarantine_resolved':
        if not any(url == 'queueManage' for _, url in steps):
            steps.append(('Check replacement queue', 'queueManage'))
    issueid = str(row.get('issueid', ''))
    if issueid.isdecimal() and len(issueid) <= 20:
        steps.append(('View issue activity', 'activity?' + urlencode({'issueid': issueid}) + '#wf_history'))
    return [{'label': label, 'href': href} for label, href in steps]


def report_age(seconds):
    if seconds < 60:
        return '%s seconds' % seconds
    if seconds < 3600:
        return '%s minutes' % (seconds // 60)
    if seconds < 86400:
        return '%s hours' % (seconds // 3600)
    return '%s days' % (seconds // 86400)


def path():
    import mylar
    return Path(mylar.DATA_DIR) / 'import-problems.json'


def report(payload):
    if not isinstance(payload, str) or len(payload) > 200000:
        raise ValueError('Report exceeds size limit')
    rows = json.loads(payload)
    if not isinstance(rows, list) or len(rows) > 500:
        raise ValueError('Report exceeds row limit')
    safe = []
    for row in rows:
        if not isinstance(row, dict) or row.get('kind') not in ACTIONS:
            raise ValueError('Invalid problem type')
        name = row.get('name', '')
        if not isinstance(name, str) or len(name) > 255 or '/' in name or '\\' in name or '://' in name:
            raise ValueError('Report must contain filenames only')
        ids = {key: str(row.get(key, '')) for key in ('issueid', 'comicid')}
        if any(value and (not value.isdecimal() or len(value) > 20) for value in ids.values()):
            raise ValueError('Invalid issue identifier')
        phase = row.get('phase', '')
        if phase not in ('', 'saved', 'quarantined', 'retry_queued', 'retry_stopped', 'retry_unconfirmed'):
            raise ValueError('Invalid recovery phase')
        item=dict(name=name, kind=row['kind'], phase=phase, **ids)
        if row.get('source_token'):
            if not re.fullmatch(r'[0-9a-f]{32}', str(row['source_token'])) or not re.fullmatch(r'[0-9a-f]{64}',str(row.get('version',''))):
                raise ValueError('Invalid guidance identity')
            item.update(source_token=row['source_token'],version=row['version'])
        safe.append(item)
    target = path()
    temporary = target.with_suffix('.new')
    with temporary.open('w') as output:
        os.chmod(temporary, 0o600)
        json.dump({'checked_at': time.time(), 'rows': safe}, output)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, target)
    return {'accepted': len(safe)}


def view():
    from mylar import db, queue_control
    try:
        value = json.loads(path().read_text())
        age = max(0, int(time.time() - value['checked_at']))
        report_state = 'stale' if age > 900 else 'current'
        report_status = 'Maintenance report is %s old.' % report_age(age)
        if age > 900:
            report_status += ' Report is stale; check the maintenance worker.'
    except (OSError, ValueError, KeyError):
        value = {'rows': []}
        report_state = 'missing'
        report_status = 'No maintenance report is available. Enable the comic maintenance worker to inspect completed files.'
    rows = []
    for row in value['rows']:
        reason, action = ACTIONS[row['kind']]
        rows.append(dict(row, reason=reason, action=action))
    database = db.DBConnection()
    for row in database.select("SELECT i.IssueID,i.ComicID,i.ComicName,i.Issue_Number,MAX(s.DateAdded) AS added "
                               "FROM issues i JOIN snatched s ON i.IssueID=s.IssueID WHERE i.Status='Snatched' "
                               "GROUP BY i.IssueID HAVING julianday('now')-julianday(MAX(s.DateAdded))>1 LIMIT 200"):
        rows.append({'name': '%s #%s' % (row['ComicName'], row['Issue_Number']), 'kind': 'snatched', 'reason': 'Snatched for over 24 hours',
                     'action': 'Check downloader completion, then match this issue to its completed file.',
                     'phase': '', 'comicid': str(row['ComicID']) if str(row['ComicID']).isdecimal() else '', 'issueid': str(row['IssueID'])})
    with queue_control._LOCK:
        for key, row in queue_control.store().data['items'].items():
            if row.get('attempts', 0) >= queue_control.ATTEMPT_LIMIT and not row.get('completed'):
                rows.append({'name': 'DDL record ' + key, 'kind': 'failed_download', 'reason': row['reason'], 'phase': '',
                             'action': 'Review mirrors in DDL Queue Management, then explicitly restart if appropriate.',
                             'comicid': '', 'issueid': ''})
    for row in rows:
        row['next_steps'] = next_steps(row)
    return {'report_status': report_status, 'report_state': report_state, 'rows': rows[:1000]}
