"""Bounded ComicVine lookup for the modern tagger; credentials stay in private files.

The parent enforces a process deadline and output limit. The worker does no media
writes, follows no redirects, and verifies issue/volume identity before mapping.
"""
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.parse import urlsplit

if __package__:
    from .tagger_runtime import run, MAX_OUTPUT
    from .tagger_volume_cache import VolumeCache, context, fresh, TTL, MAX_BYTES
else:
    from tagger_runtime import run, MAX_OUTPUT
    from tagger_volume_cache import VolumeCache, context, fresh, TTL, MAX_BYTES

VOLUMES = VolumeCache()

MAX_RESPONSE = 1024 * 1024
FIELDS = 'id,name,issue_number,volume,description,cover_date,site_detail_url,person_credits,character_credits,team_credits,location_credits'
VOLUME_FIELDS = 'id,name,count_of_issues,publisher'
ROLES = {'writer':'Writer','penciler':'Penciller','penciller':'Penciller','inker':'Inker',
         'colorist':'Colorist','letterer':'Letterer','cover':'Cover','cover artist':'Cover',
         'editor':'Editor','translator':'Translator'}


@dataclass(frozen=True)
class LookupResult:
    state: str
    metadata: dict = field(default_factory=dict, repr=False)
    volume: dict = field(default_factory=dict, repr=False)
    expires: float = field(default=0, repr=False)


def identifier(value):
    if isinstance(value, bool) or not re.fullmatch(r'[1-9][0-9]{0,15}', str(value)):
        raise ValueError('Invalid catalog identity')
    return str(value)


def text(value, *, required=False):
    if value is None and not required:
        return None
    if (not isinstance(value, str) or len(value) > 131072
            or any(ord(c) < 32 and c not in '\n\r\t' for c in value)
            or (required and not value.strip())):
        raise ValueError('Invalid catalog text')
    return value.strip()


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        elif tag in ('p', 'br', 'div', 'li'):
            self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden-1)
        elif tag in ('p', 'div', 'li'):
            self.parts.append('\n')
    def handle_data(self, value):
        if not self.hidden:
            self.parts.append(value)


def mapping(issue, volume, issueid, volumeid=None):
    if not isinstance(issue, dict) or not isinstance(volume, dict):
        raise ValueError('Invalid catalog objects')
    issueid = identifier(issueid)
    linked = issue.get('volume')
    if not isinstance(linked, dict):
        raise ValueError('Missing issue volume')
    linked_id = identifier(linked.get('id'))
    if (identifier(issue.get('id')) != issueid or identifier(volume.get('id')) != linked_id
            or (volumeid is not None and identifier(volumeid) != linked_id)):
        raise ValueError('Catalog identity mismatch')
    metadata = {'series':text(volume.get('name'), required=True),
                'issue':text(issue.get('issue_number'), required=True)}
    for source, target in [('name','title'),('description','description')]:
        value = text(issue.get(source))
        if value:
            if source == 'description':
                parser = PlainText(); parser.feed(value); parser.close()
                value = ''.join(parser.parts).strip()
            if value:
                metadata[target] = value
    cover_date = issue.get('cover_date')
    if cover_date:
        parsed = date.fromisoformat(text(cover_date, required=True))
        metadata.update(year=parsed.year, month=parsed.month, day=parsed.day)
    count = volume.get('count_of_issues')
    if count is not None:
        if type(count) is not int or count < 1:
            raise ValueError('Invalid issue count')
        metadata['issue_count'] = count
    publisher = volume.get('publisher')
    if publisher:
        if not isinstance(publisher, dict):
            raise ValueError('Invalid publisher')
        metadata['publisher'] = text(publisher.get('name'), required=True)
    web = text(issue.get('site_detail_url'))
    if web:
        parsed = urlsplit(web)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Invalid issue URL')
        metadata['web_links'] = [web]
    for source, target in [('character_credits','characters'),('team_credits','teams'),('location_credits','locations')]:
        entries = issue.get(source) or []
        if not isinstance(entries, list) or len(entries) > 1024:
            raise ValueError('Invalid catalog list')
        names = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError('Invalid credit')
            name = text(entry.get('name'), required=True)
            if name not in names:
                names.append(name)
        if names:
            metadata[target] = names
    credits = issue.get('person_credits') or []
    if not isinstance(credits, list) or len(credits) > 1024:
        raise ValueError('Invalid credits')
    mapped = []
    for credit in credits:
        if not isinstance(credit, dict):
            raise ValueError('Invalid credit')
        person = text(credit.get('name'), required=True)
        for role in text(credit.get('role'), required=True).lower().split(','):
            role = ROLES.get(role.strip())
            value = {'person':person, 'role':role}
            if role and value not in mapped:
                mapped.append(value)
    if mapped:
        metadata['credits'] = mapped
    return metadata


def fetch(settings, *, session_factory=None):
    """Worker-only HTTP function; invoke through lookup() for the total deadline."""
    import requests
    try:
        issueid = identifier(settings['issueid'])
        expected = settings.get('volumeid')
        if expected is not None:
            expected = identifier(expected)
        base = settings['base_url'].rstrip('/')
        parsed = urlsplit(base)
        if (parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment):
            raise ValueError('Invalid catalog endpoint')
        key = settings['api_key']
        if not isinstance(key, str) or not key.strip() or len(key) > 1024:
            raise ValueError('Missing API credential')
        verify = settings.get('verify', True)
        interval = settings.get('interval', 2)
        if type(verify) is not bool or type(interval) not in (int, float) or not math.isfinite(interval) or not 2 <= interval <= 10:
            raise ValueError('Invalid lookup settings')
        with (session_factory or requests.Session)() as session:
            def get(endpoint, fields):
                time.sleep(interval)
                with session.get(base+'/'+endpoint+'/', params={'api_key':key,'format':'json','field_list':fields},
                                 headers={'User-Agent':'Mylar metadata lookup','Accept':'application/json'},
                                 allow_redirects=False, stream=True, timeout=(5, 15), verify=verify) as response:
                    if response.status_code != 200:
                        raise ValueError('Catalog response failed')
                    raw = bytearray()
                    for block in response.iter_content(chunk_size=16384):
                        if len(raw)+len(block) > MAX_RESPONSE:
                            raise ValueError('Oversized catalog response')
                        raw.extend(block)
                    value = json.loads(raw)
                    if not isinstance(value, dict) or value.get('status_code') != 1 or not isinstance(value.get('results'), dict):
                        raise ValueError('Invalid catalog response')
                    return value['results']
            issue = get('issue/4000-'+issueid, FIELDS)
            if identifier(issue.get('id')) != issueid or not isinstance(issue.get('volume'), dict):
                raise ValueError('Unexpected issue identity')
            volumeid = identifier(issue['volume'].get('id'))
            if expected is not None and expected != volumeid:
                raise ValueError('Unexpected volume identity')
            cached = settings.get('cached_volume')
            # Recheck after the fresh issue request, which can consume the TTL.
            # A bad cache candidate is a miss, never an alternative identity.
            if isinstance(cached, dict) and fresh(cached.get('expires'), time.monotonic()):
                try:
                    volume = cached['volume']
                    if len(json.dumps(volume, allow_nan=False).encode()) <= MAX_BYTES:
                        return LookupResult('ok', mapping(issue, volume, issueid, expected))
                except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
                    pass
            volume = get('volume/4050-'+volumeid, VOLUME_FIELDS)
            metadata = mapping(issue, volume, issueid, expected)
            # Keep only fields used by mapping, and only return validated data.
            selected = {key: volume[key] for key in ('id', 'name', 'count_of_issues', 'publisher') if key in volume}
            if len(json.dumps(selected, allow_nan=False).encode()) > MAX_BYTES:
                selected = {}
            return LookupResult('ok', metadata, selected, time.monotonic()+TTL)
    except (requests.RequestException, ValueError, TypeError, KeyError, RecursionError, OverflowError):
        return LookupResult('failed')


def lookup(*, workdir, issueid, api_key, base_url, volumeid=None, verify=True, interval=2):
    """Private request, bounded child, sanitized output; no credentials in argv."""
    settings = dict(issueid=issueid, api_key=api_key, base_url=base_url, volumeid=volumeid,
                    verify=verify, interval=interval)
    payload = json.dumps(settings, allow_nan=False)
    if len(payload.encode()) > 32768:
        return LookupResult('failed')
    cache_key = None
    if volumeid is not None:
        try:
            cache_key = context(base_url, api_key, verify, identifier(volumeid))
            cached = VOLUMES.get(cache_key)
            if cached:
                candidate = json.dumps(dict(settings, cached_volume=cached), allow_nan=False)
                if len(candidate.encode()) <= 32768:
                    payload = candidate
        except (ValueError, TypeError, AttributeError):
            pass  # Invalid settings are still rejected by the worker.
    with tempfile.TemporaryDirectory(prefix='.lookup-', dir=workdir) as folder:
        path = Path(folder)/'request.json'
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(payload)
        result = run([sys.executable, str(Path(__file__).resolve()), str(path)], cwd=folder, timeout=45)
        if result.state != 'ok':
            return LookupResult(result.state)
        try:
            value = json.loads(result.stdout)
            if value['state'] == 'ok' and isinstance(value.get('metadata'), dict) and value['metadata']:
                volume = value.get('volume')
                if cache_key is not None and isinstance(volume, dict) and volume:
                    try:
                        # Revalidate the worker's volume before retaining it.
                        mapping({'id':issueid, 'issue_number':'1', 'volume':{'id':volumeid}},
                                volume, issueid, volumeid)
                        VOLUMES.put(cache_key, volume, value.get('expires'))
                    except (ValueError, TypeError, KeyError):
                        pass
                return LookupResult('ok', value['metadata'])
        except (ValueError, TypeError, KeyError, RecursionError):
            pass
        return LookupResult('failed')


def encode_result(result):
    """Optional cache admission must not consume the metadata output budget."""
    value = {'state':result.state, 'metadata':result.metadata}
    if result.volume:
        candidate = json.dumps(dict(value, volume=result.volume, expires=result.expires),
                               ensure_ascii=True, allow_nan=False)
        if len(candidate.encode()) + 1 <= MAX_OUTPUT:  # print adds a newline
            return candidate
    return json.dumps(value, ensure_ascii=True, allow_nan=False)


if __name__ == '__main__':
    try:
        raw = Path(sys.argv[1]).read_bytes()
        if len(raw) > 32768:
            raise ValueError('Oversized settings')
        result = fetch(json.loads(raw))
        print(encode_result(result))
    except Exception:
        print('{"state":"failed"}')
