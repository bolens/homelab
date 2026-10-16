"""Probe real Mylar workers, retaining progress observations between checks."""
import copy
import configparser
import json
import math
import os
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request


def _postprocessing_work(snapshot):
    work = snapshot.get('pp_work')
    names = {'version', 'queued', 'active', 'manual_active', 'oldest_manual_seconds',
             'recent_finished', 'observer_errors'}
    if type(work) is not dict or set(work) != names:
        return None
    if any(type(value) is not int or not 0 <= value < 2**63 for value in work.values()):
        return None
    if (work['version'] != 1 or work['active'] > 16 or work['manual_active'] > work['active']
            or work['recent_finished'] > 50 or work['observer_errors'] != 0
            or (work['manual_active'] == 0 and work['oldest_manual_seconds'] != 0)
            or work['queued'] != (snapshot['queues'].get('POST-PROCESS-QUEUE', {}).get('size', 0) or 0)):
        return None
    return work


def assess(snapshot, previous, now, stall_seconds=900):
    errors = []
    observations = {}
    if snapshot.get('publication',{}).get('state')=='held':
        if snapshot['publication'].get('reason')=='writer-busy':
            return _busy(snapshot,previous,now,stall_seconds)
        return dict(checked_at=now,observations=copy.deepcopy(previous),
                    errors=['Publication authority held; authenticated review and native restart required'])
    workflow = snapshot.get('workflow', {})
    if workflow and not workflow.get('valid'):
        errors.append('Workflow state is unavailable; review Activity and application logs')
    queues = snapshot['queues']
    for name in snapshot['enabled']:
        if not queues.get(name, {}).get('alive'):
            errors.append(name + ' is down')
    pp_work = _postprocessing_work(snapshot)
    pp_active = snapshot['processing'] or snapshot.get('completed', 0) > 0
    intake_review = None
    if pp_work is not None:
        # A known running manual scan has its own invocation-duration check.
        # Retained input inventory is not evidence of an accepted queue job.
        pp_active = pp_work['active'] > pp_work['manual_active'] or (snapshot['processing'] and pp_work['active'] == 0)
        if 'POST-PROCESS-QUEUE' in snapshot['enabled'] and pp_work['oldest_manual_seconds'] >= stall_seconds:
            errors.append('Folder monitor scan has not completed for 15 minutes')
        if snapshot.get('completed', 0) > 0:
            intake_review = dict(completed_files=snapshot['completed'], classification='unresolved-check-folder-inputs')
    for name, token, active in (
        ('POST-PROCESS-QUEUE', [snapshot['downloaded'], -snapshot.get('completed', 0)], pp_active),
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
        cooldown = snapshot.get('ddl_cooldown') if name == 'DDL-QUEUE' else None
        pending = cooldown.get('pending', 0) if cooldown else 0
        waiting = name in snapshot['enabled'] and (size > 0 or active or pending > 0)
        since = old.get('since', now) if waiting and not changed else now
        observations[name] = {'token': copy.deepcopy(token), 'size': size, 'since': since, 'waiting': bool(waiting)}
        if name == 'DDL-QUEUE' and not active and workflow.get('ddl_paused'):
            observations[name]['since'] = now
            continue
        expected_wait = False
        expiry_stalled = False
        if cooldown and name in snapshot['enabled']:
            if not cooldown.get('valid'):
                errors.append('DDL cooldown state requires review')
            elif waiting and not active and not cooldown.get('active'):
                deadline = old.get('cooldown_deadline')
                if changed:
                    deadline = None
                if cooldown.get('all_cooling'):
                    deadline = cooldown['next_retry_at']
                elif deadline is not None and now < deadline:
                    # New ready work must not inherit another provider's wait.
                    deadline = None
                if deadline is not None:
                    observations[name]['cooldown_deadline'] = deadline
                    expected_wait = now < deadline + 120 and now - since < 3600
                    expiry_stalled = now >= deadline + 120
                if deadline is not None and now - since >= 3600:
                    errors.append('DDL-QUEUE has made no useful progress for one hour during provider cooldowns')
                    continue
        if name == 'DDL-QUEUE' and not active and workflow.get('intake', {}).get('paused'):
            expected_wait = True
        if waiting and not expected_wait and (expiry_stalled or now - since >= stall_seconds):
            errors.append(name + (' did not resume within two minutes of provider cooldown expiry'
                                 if expiry_stalled else ' has made no progress for 15 minutes'))
    result = {'checked_at': now, 'observations': observations, 'errors': errors}
    if intake_review is not None:
        result['intake_review'] = intake_review
    return result


def _busy(snapshot, previous, now, stall_seconds):
    """Bounded liveness grace, retaining unknown authority and old progress clocks."""
    error='Publication Writer is busy; current startup and worker health are unavailable'
    result=dict(checked_at=now,observations=copy.deepcopy(previous),errors=[error])
    publication=snapshot.get('publication',{})
    packet=snapshot.get('busy_workers')
    names=('SEARCH-QUEUE','POST-PROCESS-QUEUE','DDL-QUEUE','AUTO-COMPLETE-NZB','AUTO-SNATCHER')
    if (type(publication.get('version')) is not int or publication.get('version')!=1
            or publication.get('census','missing') is not None
            or type(packet) is not dict or set(packet)!={'version','startup_complete','enabled','queues'}
            or type(packet['version']) is not int or packet['version']!=1 or packet['startup_complete'] is not True):
        return result
    enabled,queues=packet['enabled'],packet['queues']
    if (type(enabled) is not list or not enabled or any(type(n) is not str or n not in names for n in enabled)
            or len(set(enabled))!=len(enabled) or 'SEARCH-QUEUE' not in enabled
            or type(queues) is not dict or any(n not in names for n in queues) or any(n not in queues for n in enabled)):
        return result
    for row in queues.values():
        if (type(row) is not dict or set(row)!={'alive','size'} or type(row['alive']) is not bool
                or type(row['size']) is not int or not 0<=row['size']<2**63):
            return result
    finite=lambda n:type(n) in (int,float) and -2**53<n<2**53 and math.isfinite(n)
    if not finite(now) or not finite(snapshot.get('time')) or abs(now-snapshot['time'])>30:
        return result
    old=previous.get('_publication_busy',{})
    if '_publication_busy' in previous and (type(old) is not dict or set(old)!={'since'}):
        return result
    since=old.get('since',now)
    if not finite(since) or since>now:
        return result
    result['observations']['_publication_busy']=dict(since=since)
    result['errors']=[n+' is down' for n in enabled if not queues[n]['alive']]
    for name in ('POST-PROCESS-QUEUE','DDL-QUEUE'):
        prior=previous.get(name,{})
        size=prior.get('size',0) if type(prior) is dict else 0
        if (name in enabled and type(prior) is dict and (prior.get('waiting') is True or type(size) is int and size>0)
                and finite(prior.get('since')) and now-prior['since']>=min(stall_seconds,900)):
            result['errors'].append(name+' progress is overdue and cannot be verified while the Writer is busy')
    prior=previous.get('DDL-QUEUE',{})
    if 'DDL-QUEUE' in enabled and type(prior) is dict and 'cooldown_deadline' in prior:
        deadline=prior['cooldown_deadline']
        if not finite(deadline) or now>=deadline+120:
            result['errors'].append('DDL-QUEUE provider cooldown expiry cannot be verified while the Writer is busy')
    if not finite(stall_seconds) or stall_seconds<=0 or now-since>=min(stall_seconds,900):
        result['errors'].append('Publication Writer remains busy; authority and progress could not be checked within 15 minutes')
    return result


def main():
    directory = Path(os.environ.get('MYLAR_CONFIG_DIR', '/config/mylar'))
    parser = configparser.ConfigParser()
    parser.read(directory / 'config.ini')
    key = next(parser.get(s, 'api_key') for s in parser.sections() if parser.has_option(s, 'api_key'))
    port = next((parser.get(s, 'http_port') for s in parser.sections() if parser.has_option(s, 'http_port')), '8090')
    body = urllib.parse.urlencode({'apikey': key, 'cmd': 'getHealth'}).encode()
    root = next((parser.get(s, 'http_root') for s in parser.sections() if parser.has_option(s, 'http_root')), '/')
    root = '/' + root.strip('/') if root.strip('/') else ''
    req = urllib.request.Request('http://127.0.0.1:' + port + root + '/api', data=body)
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
