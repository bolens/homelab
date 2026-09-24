"""Bounded, non-secret classification of pending DDL cooldown waits."""
import math


def classify(rows, providers, now):
    result = {'valid': True, 'pending': 0, 'ready': 0, 'cooling': 0,
              'active': 0, 'all_cooling': False, 'next_retry_at': None,
              'retry_seconds': 0, 'status': 'Idle'}
    deadlines = []
    for row in rows:
        if row['status'] not in ('Queued', 'Downloading'):
            continue
        result['pending'] += 1
        if row['status'] == 'Downloading':
            result['active'] += 1
            continue
        provider = row['link_type'] or 'GC-Main'
        state = providers.get(provider, {})
        until = state.get('until', 0)
        if isinstance(until, bool) or not isinstance(until, (int, float)) or not math.isfinite(until):
            raise ValueError('Invalid provider cooldown')
        if until > now:
            result['cooling'] += 1
            deadlines.append(until)
        else:
            result['ready'] += 1
    result['all_cooling'] = bool(result['pending'] and result['cooling'] == result['pending'])
    result['next_retry_at'] = min(deadlines) if deadlines else None
    result['retry_seconds'] = max(0, math.ceil(min(deadlines) - now)) if deadlines else 0
    result['status'] = ('Downloading' if result['active'] else
                        'Waiting for provider cooldown' if result['all_cooling'] else
                        'Ready' if result['ready'] else 'Idle')
    return result


def snapshot(database):
    from mylar import queue_control
    try:
        with queue_control._LOCK:
            state = queue_control.store()
            rows = database.select("SELECT status, link_type FROM ddl_info WHERE status IN ('Queued', 'Downloading')")
            return classify(rows, state.data['providers'], state.clock())
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        return {'valid': False, 'status': 'DDL cooldown state requires review',
                'all_cooling': False, 'next_retry_at': None, 'retry_seconds': 0}
