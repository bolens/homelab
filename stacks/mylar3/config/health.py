"""Probe real Mylar workers, retaining progress observations between checks."""
import copy
import configparser
import json
import os
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request


def assess(snapshot, previous, now, stall_seconds=900):
    errors = []
    observations = {}
    queues = snapshot['queues']
    for name in snapshot['enabled']:
        if not queues.get(name, {}).get('alive'):
            errors.append(name + ' is down')
    for name, token, active in (
        ('POST-PROCESS-QUEUE', [snapshot['downloaded'], -snapshot.get('completed', 0)], snapshot['processing'] or snapshot.get('completed', 0) > 0),
        ('DDL-QUEUE', snapshot.get('ddl_useful', snapshot['ddl_active']), bool(snapshot['ddl_active'])),
    ):
        size = queues.get(name, {}).get('size', 0) or 0
        old = previous.get(name, {})
        changed = token != old.get('token') or size < old.get('size', size)
        if name == 'POST-PROCESS-QUEUE' and isinstance(old.get('token'), list):
            changed = token[0] != old['token'][0] or token[1] > old['token'][1] or size < old.get('size', size)
        if name == 'DDL-QUEUE' and 'ddl_useful' in snapshot and isinstance(old.get('token'), list):
            before = old['token']
            changed = len(before) != 2 or not all(isinstance(x, (int, float)) for x in before) or any(a > b for a, b in zip(token, before))
        waiting = name in snapshot['enabled'] and (size > 0 or active)
        since = old.get('since', now) if waiting and not changed else now
        observations[name] = {'token': copy.deepcopy(token), 'size': size, 'since': since}
        if waiting and now - since >= stall_seconds:
            errors.append(name + ' has made no progress for 15 minutes')
    return {'checked_at': now, 'observations': observations, 'errors': errors}


def main():
    directory = Path(os.environ.get('MYLAR_CONFIG_DIR', '/config/mylar'))
    parser = configparser.ConfigParser()
    parser.read(directory / 'config.ini')
    key = next(parser.get(s, 'api_key') for s in parser.sections() if parser.has_option(s, 'api_key'))
    port = next((parser.get(s, 'http_port') for s in parser.sections() if parser.has_option(s, 'http_port')), '8090')
    body = urllib.parse.urlencode({'apikey': key, 'cmd': 'getHealth'}).encode()
    req = urllib.request.Request('http://127.0.0.1:' + port + '/api', data=body)
    with urllib.request.urlopen(req, timeout=10) as response:
        payload = json.load(response)
    if not payload.get('success'):
        raise RuntimeError('Health API unavailable')
    state = directory / 'worker-health.json'
    try:
        previous = json.loads(state.read_text())['observations']
    except (FileNotFoundError, ValueError, KeyError):
        previous = {}
    result = assess(payload['data'], previous, time.time())
    temporary = state.with_suffix('.new')
    temporary.write_text(json.dumps(result)); temporary.chmod(0o600)
    os.replace(temporary, state)
    print(json.dumps({'healthy': not result['errors'], 'errors': result['errors']}))
    return int(bool(result['errors']))


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        print('Mylar worker health probe failed; check API availability and configuration')
        sys.exit(1)
