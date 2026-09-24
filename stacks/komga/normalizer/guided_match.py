"""Worker-owned guided import identities, conservative aliases and durable receipts."""
from contextlib import closing
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time

from import_match import catalog, metadata, number, title
from normalize import digest, identity, save

HEX32 = re.compile(r'^[a-f0-9]{32}$')
HEX64 = re.compile(r'^[a-f0-9]{64}$')


def safe_display(value):
    """Reject unsafe optional guidance rather than poisoning the combined report."""
    if isinstance(value, str):
        return '://' not in value and not any(ord(c) < 32 for c in value)
    if isinstance(value, list):
        return all(safe_display(item) for item in value)
    if isinstance(value, dict):
        return all(safe_display(item) for item in value.values())
    return True


def evidence(path):
    """Keep filename and metadata evidence separate, including disagreements."""
    meta = metadata(path)
    clean = re.sub(r'\[__\d+__\]', '', path.stem).strip()
    parsed = re.fullmatch(r'(.+?)\s+#?(\d+(?:\.\d+)?)\s+\(((?:19|20)\d{2})\)(?:\s+\([^)]*\))*', clean)
    points = []
    if parsed:
        points.append((parsed[1], parsed[2], parsed[3], 'filename'))
    if meta.get('Series') and meta.get('Number'):
        year = meta.get('Volume', '')
        points.append((meta['Series'], meta['Number'], year if re.fullmatch(r'(19|20)\d{2}', year) else '', 'metadata'))
    ids = re.findall(r'\[__(\d+)__\]', path.name) + re.findall(
        r'https?://(?:www\.)?comicvine\.gamespot\.com/[^\s<>]*?4000-(\d+)(?:/|\b)', meta.get('Web', ''))
    return points, ids, meta


def scope(points):
    scoped = {(title(series), year) for series, issue, year, origin in points if year and number(issue) is not None}
    if len(scoped) != 1 or len({number(p[1]) for p in points}) != 1:
        return None
    series, year = next(iter(scoped))
    if not series or any(title(p[0]) != series for p in points):
        return None
    return {'series': series[:160], 'year': year} if len(series) <= 160 else None


def candidate(row, points, ids):
    agrees, conflicts = [], []
    for series, issue, year, origin in points:
        for label, equal in ((origin + ' series', title(series) == title(row[5])),
                             (origin + ' issue', number(issue) == number(row[3])),
                             (origin + ' year', not year or year == str(row[6]))):
            (agrees if equal else conflicts).append(label)
    if ids:
        (agrees if set(ids) == {str(row[0])} else conflicts).append('explicit issue ID')
    return {'issueid': str(row[0]), 'comicid': str(row[1]), 'title': str(row[5])[:160],
            'year': str(row[6])[:4], 'number': str(row[3])[:20], 'status': str(row[2])[:30],
            'agrees': agrees[:6], 'conflicts': conflicts[:6]}


def alias_match(path, rows, aliases):
    try:
        points, ids, meta = evidence(path)
    except Exception:
        return None
    key = scope(points)
    if (not key or not points or len(ids) != len(set(ids))
            or any(re.search(r'\b(annual|special|omnibus|collection|tpb)\b', p[0], re.I) for p in points)):
        return None
    rules = [a for a in aliases if a.get('enabled') is True and a.get('series') == key['series'] and a.get('year') == key['year']]
    comicids = {str(a.get('comicid')) for a in rules}
    if len(comicids) != 1:
        return None
    choices = [row for row in rows if str(row[1]) in comicids and str(row[6]) == key['year']
               and all(number(p[1]) is not None and number(p[1]) == number(row[3]) for p in points)
               and (not ids or set(ids) == {str(row[0])})]
    if len(choices) != 1 or choices[0][2] == 'Downloaded':
        return None
    row = choices[0]
    if ((meta.get('Number') and number(meta['Number']) != number(row[3]))
            or (meta.get('Series') and title(meta['Series']) != key['series'])
            or (meta.get('Volume') and str(meta['Volume']) != key['year'])
            or (meta.get('Year') and str(meta['Year']) != str(row[4])[:4])):
        return None
    return {'issueid': str(row[0]), 'comicid': str(row[1])}


class Guided:
    def __init__(self, maintenance):
        self.m = maintenance
        self.root = maintenance.state / 'guidance'
        self.root.mkdir(exist_ok=True, mode=0o700)
        self.commands = self.root / 'commands'
        self.commands.mkdir(exist_ok=True, mode=0o700)
        self.proposals = []
        self.aliases = []
        self.available = False

    def rows(self):
        return catalog(Path(self.m.worker.config['mylar'].get('config_dir', '/mylar')) / 'mylar.db')

    def propose(self, source):
        if not self.available or len(self.proposals) >= 50:
            return {}
        from maintenance import scoped_file
        if not scoped_file(source, self.m.roots):
            return {}
        points, ids, meta = evidence(source)
        before = identity(source)
        checksum = digest(source)
        if identity(source) != before:
            raise RuntimeError('Source changed while preparing guidance')
        key = hashlib.sha256(os.fsencode(source)).hexdigest()
        destination = self.root / (key + '.json')
        previous = json.loads(destination.read_text()) if destination.exists() else {}
        token = previous.get('source_token', secrets.token_hex(16))
        version = hashlib.sha256(json.dumps([before, checksum]).encode()).hexdigest()
        rows = self.rows()
        def rank(row):
            value = candidate(row, points, ids)
            same_number = any(number(p[1]) == number(row[3]) for p in points)
            similarity = max((difflib.SequenceMatcher(None, title(p[0]), title(row[5])).ratio() for p in points), default=0)
            return (str(row[0]) in ids, same_number, len(value['agrees']), similarity)
        choices = sorted(rows, key=rank, reverse=True)[:8] if points or ids else []
        name = source.name
        if len(name) > 255 or any(c in name for c in ('/', '\\', '://')) or any(ord(c) < 32 for c in name):
            return {}
        public = {'source_token': token, 'version': version, 'name': name,
                  'candidates': [candidate(r, points, ids) for r in choices],
                  'evidence': [('%s: %s #%s%s' % (origin, series, issue, ' (' + year + ')' if year else ''))[:200]
                               for series, issue, year, origin in points][:6]}
        alias_scope = scope(points)
        if alias_scope:
            public['alias_scope'] = alias_scope
        if not safe_display(public):
            return {}
        if len(json.dumps(self.proposals + [public])) > 180000:
            return {}
        record = dict(public, source=str(source), identity=before, sha256=checksum, updated_at=time.time())
        save(destination, record)
        self.proposals.append(public)
        return {'source_token': token, 'version': version}

    def acknowledge(self, file, record, phase, reason=''):
        if phase == 'submitted' and 'submitted_at' not in record:
            record['submitted_at'] = time.time()
        record.update(phase=phase, reason=reason)
        save(file, record)
        self.m.mylar('workflowAcknowledge', command_id=record['id'], phase=phase, reason=reason)

    def confirmed(self, record):
        """A removed-source receipt proves content, but must also belong to this issue."""
        source = record.get('source')
        if not source:
            return False
        database = Path(self.m.worker.config['mylar'].get('config_dir', '/mylar')) / 'mylar.db'
        with closing(sqlite3.connect('file:' + str(database) + '?mode=ro', uri=True)) as db:
            row = db.execute('SELECT i.Status,i.Location,c.ComicLocation FROM issues i JOIN comics c ON c.ComicID=i.ComicID '
                             'WHERE i.IssueID=? AND i.ComicID=?', (record['issueid'], record['comicid'])).fetchone()
        if not row or row[0] != 'Downloaded' or not row[1] or not row[2]:
            return False
        target = Path(row[1]) if Path(row[1]).is_absolute() else Path(row[2]) / row[1]
        from maintenance import scoped_file
        if not scoped_file(target, self.m.worker.roots):
            return False
        for file in self.m.receipts.glob('*.json'):
            receipt = json.loads(file.read_text())
            if (receipt.get('kind') == 'duplicate' and receipt.get('phase') == 'removed'
                    and receipt.get('source') == source and receipt.get('sha256') == record.get('sha256')
                    and receipt.get('destination') == str(target)
                    and digest(target) == receipt.get('destination_sha256')):
                return True
        return False

    def poll(self):
        try:
            payload = self.m.mylar('workflowCommands')
            if not isinstance(payload, dict) or not isinstance(payload.get('commands'), list) or not isinstance(payload.get('aliases'), list):
                return
            self.available = True
            self.aliases = payload['aliases'][:200]
            for command in payload['commands'][:50]:
                self.process(command)
        except Exception:
            # Older servers and lost responses never erase durable work or repeat submission.
            return

    def process(self, command):
        from maintenance import scoped_file
        from import_recovery import submit
        if not isinstance(command, dict) or not HEX32.fullmatch(str(command.get('id', ''))):
            return
        file = self.commands / (command['id'] + '.json')
        if file.exists():
            record = json.loads(file.read_text())
            if record['phase'] in ('submitted', 'review', 'claimed') and self.confirmed(record):
                self.acknowledge(file, record, 'confirmed')
            elif (record['phase'] == 'claimed' or
                  (record['phase'] == 'submitted' and time.time() - record.get('submitted_at', 0) >= 1800)):
                self.acknowledge(file, record, 'review', 'unconfirmed')
            else:
                self.acknowledge(file, record, record['phase'], record.get('reason', ''))
            return
        record = dict(command)
        if not HEX32.fullmatch(str(command.get('source_token', ''))) or not HEX64.fullmatch(str(command.get('version', ''))):
            return
        proposals = [json.loads(p.read_text()) for p in self.root.glob('*.json')]
        proposal = next((p for p in proposals if p['source_token'] == command['source_token']), None)
        if not proposal or proposal['version'] != command['version']:
            self.acknowledge(file, record, 'rejected', 'stale_source')
            return
        selected = next((c for c in proposal['candidates'] if str(c['issueid']) == str(command.get('issueid'))
                         and str(c['comicid']) == str(command.get('comicid'))), None)
        if (not selected or (command.get('save_alias') and
                (not proposal.get('alias_scope') or proposal['alias_scope']['year'] != selected['year']
                 or not any(x.endswith(' issue') for x in selected['agrees'])
                 or any(x.endswith(' issue') or x == 'explicit issue ID' for x in selected['conflicts'])))):
            self.acknowledge(file, record, 'rejected', 'issue_unavailable')
            return
        source = Path(proposal['source'])
        record.update(source=str(source), sha256=proposal['sha256'])
        if (not scoped_file(source, self.m.roots) or identity(source) != proposal['identity']
                or digest(source) != proposal['sha256']):
            self.acknowledge(file, record, 'rejected', 'changed_source')
            return
        rows = [r for r in self.rows() if str(r[0]) == str(command.get('issueid')) and str(r[1]) == str(command.get('comicid'))]
        if len(rows) != 1 or rows[0][2] == 'Downloaded':
            self.acknowledge(file, record, 'rejected', 'issue_unavailable')
            return
        if source.name in self.m.pending_ddl_names() or source.suffix.casefold() not in ('.cbz', '.cbr'):
            self.acknowledge(file, record, 'rejected', 'source_unavailable')
            return
        if not self.m.idle() or self.m.import_submitted:
            return
        self.m.info(source)
        if identity(source) != proposal['identity'] or digest(source) != proposal['sha256']:
            self.acknowledge(file, record, 'rejected', 'changed_source')
            return
        self.acknowledge(file, record, 'claimed')
        result = submit(self.m, source, {'issueid': str(rows[0][0]), 'comicid': str(rows[0][1])}, explicit=True,
                        expected_identity=proposal['identity'], expected_sha256=proposal['sha256'], workflow_command=record['id'])
        phase = 'submitted' if result == 'import_queued' else 'review'
        self.acknowledge(file, record, phase, '' if phase == 'submitted' else 'unconfirmed')
