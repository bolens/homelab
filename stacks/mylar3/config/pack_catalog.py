"""Conservative native catalog additions requested by the pack worker."""
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
import threading
import time
import unicodedata

from mylar import workflow
from mylar.workflow_store import identifier

_LOCK = threading.Lock()


def title(value):
    return ''.join(c for c in unicodedata.normalize('NFKC', str(value)).casefold() if c.isalnum())


def number(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


def resolve(payload, handoff=None, catalog_attempt=None):
    if not isinstance(payload, str) or len(payload) > 4000:
        raise ValueError('Invalid catalog request')
    evidence = json.loads(payload)
    if not workflow.policy().get('pack_automation'):
        return {'phase': 'review', 'reason': 'Pack automation is disabled'}
    name, year, num = evidence.get('series'), str(evidence.get('year', '')), evidence.get('number')
    if (not isinstance(name, str) or not 1 <= len(name) <= 200 or '://' in name
            or not re.fullmatch(r'(19|20)\d{2}', year) or number(num) is None):
        raise ValueError('Exact series, year and number required')
    issueid = identifier(evidence.get('issueid'))
    parentid = identifier(evidence.get('parentid'))
    edition = evidence.get('edition', '')
    if edition not in ('', 'Digital', 'Print'):
        raise ValueError('Invalid edition')
    normalized = dict(series=name, year=year, number=str(number(num)), issueid=issueid, parentid=parentid, edition=edition)
    from mylar import worker_handoff
    worker_handoff.admit(handoff,'packCatalog',{'evidence':payload,'catalog_attempt':catalog_attempt})
    key = hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()
    from mylar import db, cv, mb, importer
    with _LOCK:
        store = workflow.store()
        previous = store.get('pack_catalog', key)
        now = time.time()
        if previous and (previous.get('phase') != 'retry' or now < previous.get('retry_at', 0)):
            return previous  # Ambiguous identities and catalog writes are never replayed.
        if previous and previous.get('attempts', 0) >= 5:
            previous.update(phase='review', reason='Catalog lookup failed after five attempts; retained for review')
            store.set('pack_catalog', key, previous)
            return previous
        attempts = (previous or {}).get('attempts', 0) + 1
        record = {'phase': 'review', 'reason': 'Catalog identity needs review',
                  'created_at': (previous or {}).get('created_at', now), 'attempts': attempts}
        def finish():
            store.set('pack_catalog', key, record)
            return record
        # A crash during safe reads may retry after backoff. Persist a terminal
        # mutation intent before either native importer can change the catalog.
        retry_at = now + min(3600, 300 * 2 ** min(attempts - 1, 4))
        store.set('pack_catalog', key, dict(record, phase='retry', retry_at=retry_at))
        try:
            if issueid:
                info = cv.getComic(None, 'single_issue', issueid)
                if not info:
                    raise LookupError('Catalog issue unavailable')
                if (str(info['issueid']) != issueid or title(info['series']) != title(name)
                        or number(info['issue_number']) != number(num)):
                    return finish()
                volumeid = identifier(info['comicid'])
            else:
                candidates = mb.findComic(name, 'series', issue=None)
                if candidates is None:
                    raise LookupError('Catalog search unavailable')
                choices = {identifier(r.get('comicid')) for r in candidates
                           if title(r.get('name', r.get('comicname', ''))) == title(name)
                           and str(r.get('comicyear', r.get('year', ''))) == year
                           and (not edition or r.get('type') == edition)}
                choices.discard('')
                if len(choices) != 1:
                    return finish()
                volumeid = choices.pop()
            volume = cv.getComic(volumeid, 'comic')
            if not volume:
                raise LookupError('Catalog volume unavailable')
            if title(volume['ComicName']) != title(name):
                return finish()
            if str(volume['ComicYear']) != year:
                # An explicit issue ID may corroborate an issue publication year.
                if not issueid or str(info.get('coverdate', ''))[:4] != year:
                    return finish()
            if edition and volume.get('Type') != edition:
                return finish()
            issue_data = cv.getComic(volumeid, 'issue')
            if not issue_data or 'issuechoice' not in issue_data:
                raise LookupError('Catalog issue list unavailable')
            issues = issue_data['issuechoice']
            choices = [r for r in issues if number(r['Issue_Number']) == number(num)
                       and (not issueid or str(r['Issue_ID']) == issueid)]
            if len(choices) != 1:
                return finish()
            issueid = identifier(choices[0]['Issue_ID'])
            database = db.DBConnection()
            current = database.selectone('SELECT ComicID,Deleted FROM annuals WHERE IssueID=?', [issueid]).fetchone()
            if current:
                if current['Deleted']:
                    return finish()
                record.update(phase='ready', issueid=issueid, comicid=str(current['ComicID']), reason='Existing annual identity')
            else:
                current = database.selectone('SELECT ComicID FROM issues WHERE IssueID=?', [issueid]).fetchone()
                if current:
                    record.update(phase='ready', issueid=issueid, comicid=str(current['ComicID']), reason='Existing issue identity')
                else:
                    annual = bool(re.search(r'\bannual\b', name, re.I))
                    if annual and not parentid:
                        dom = cv.pulldetails(volumeid, 'comic')
                        descriptions = dom.getElementsByTagName('description')
                        raw = descriptions[0].firstChild.wholeText if descriptions and descriptions[0].firstChild else ''
                        linked = set(re.findall(r'(?:https?://(?:www\.)?comicvine\.gamespot\.com)?/[^\s"<>]*?4050-(\d+)(?:/|["\s<>])', raw))
                        parents = [r for r in database.select('SELECT ComicID,ComicName FROM comics')
                                   if str(r['ComicID']) in linked and title(r['ComicName']) == title(re.sub(r'\bannual\b', '', name, flags=re.I))]
                        if len(parents) == 1:
                            parentid = str(parents[0]['ComicID'])
                    parent = database.selectone('SELECT ComicName,ComicYear FROM comics WHERE ComicID=?', [parentid]).fetchone() if parentid else None
                    related = False
                    if annual and parent and title(re.sub(r'\bannual\b', '', name, flags=re.I)) == title(parent['ComicName']):
                        # Inspect the catalog's actual volume link, never a substring of an ID.
                        dom = cv.pulldetails(volumeid, 'comic')
                        description = dom.getElementsByTagName('description')
                        raw = description[0].firstChild.wholeText if description and description[0].firstChild else ''
                        related = bool(re.search(r'(?:https?://(?:www\.)?comicvine\.gamespot\.com)?/[^\s"<>]*?4050-' + re.escape(parentid) + r'(?:/|["\s<>])', raw))
                    if related:
                        rows = importer.manualAnnual(manual_comicid=volumeid, comicname=parent['ComicName'],
                                                     comicyear=parent['ComicYear'], comicid=parentid, manualupd=True)
                        if rows is None:
                            raise LookupError('Annual catalog unavailable')
                        rows = [dict(r, Status='Skipped') for r in rows if str(r['IssueID']) == issueid
                                and str(r['ReleaseComicID']) == volumeid and str(r['ComicID']) == parentid]
                        if len(rows) != 1:
                            return finish()
                        # The native write path is used only for a genuinely absent ID.
                        if not database.selectone('SELECT IssueID FROM annuals WHERE IssueID=?', [issueid]).fetchone():
                            record.update(mutation_started=True, issueid=issueid, comicid=parentid,
                                          reason='Catalog addition incomplete; retained for review')
                            finish()
                            importer.manualAnnual(annchk=rows)
                        comicid = parentid
                        current = database.selectone('SELECT IssueID FROM annuals WHERE IssueID=? AND NOT Deleted', [issueid]).fetchone()
                    else:
                        # A cataloged annual/special can be tracked as its own exact
                        # volume when the parent relationship cannot be established.
                        record.update(mutation_started=True, issueid=issueid, comicid=volumeid,
                                      reason='Catalog addition incomplete; retained for review')
                        finish()
                        importer.addComictoDB(volumeid, suppress_addall=True)
                        comicid = volumeid
                        current = database.selectone('SELECT IssueID FROM issues WHERE IssueID=? AND ComicID=?', [issueid, comicid]).fetchone()
                    if current:
                        record.update(phase='ready', issueid=issueid, comicid=comicid, reason='Exact catalog entry added')
            return finish()
        except Exception:
            if not record.get('mutation_started') and attempts < 5:
                record.update(phase='retry', retry_at=retry_at, reason='Catalog lookup unavailable; retry scheduled')
            else:
                record.update(reason='Catalog addition incomplete; retained for review' if record.get('mutation_started') else
                              'Catalog lookup failed after five attempts; retained for review')
            return finish()
