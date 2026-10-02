"""Release-specific Prowlarr identities without storing download credentials."""
import hashlib
import json
import re
from urllib.parse import parse_qs, urlsplit


def release_id(link):
    parts = urlsplit(link)
    values = parse_qs(parts.query).get('link', [])
    if not re.fullmatch(r'.*/\d+/download/?', parts.path) or len(values) != 1 or not values[0]:
        return None
    identity = json.dumps([parts.path.rstrip('/'), values[0]], separators=(',', ':'))
    return 'prowlarr:' + hashlib.sha256(identity.encode()).hexdigest()


def failed_record(database, identity, name):
    row = database.selectone('SELECT * FROM failed WHERE ID=?', [identity]).fetchone()
    if row is None and identity.startswith('prowlarr:'):
        # Preserve genuine legacy failures without treating one endpoint as every release.
        row = database.selectone('SELECT * FROM failed WHERE ID=? AND NZBName=?',
                                 ['download', name]).fetchone()
    return row
