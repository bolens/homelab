"""Backend preference and readiness shared by settings and native dispatch.

Legacy remains available throughout migration. A configured modern preference must
never silently run legacy while native writer/recovery integration is incomplete.
"""
CHOICES = ('legacy', 'modern')
MODERN_UNAVAILABLE = ('Modern tagging is not available yet. Native routing, recovery cleanup '
                      'and canary verification are still pending.')


def choice(value):
    if type(value) is not str or value not in CHOICES:
        raise ValueError('Choose Legacy or Modern ComicTagger.')
    return value


def status():
    # This is a code capability gate, not a user-controlled setting or environment
    # flag. Remove it only with the native ownership and rollout acceptance proof.
    return {'modern_available': False, 'message': MODERN_UNAVAILABLE}


def validate_update(value):
    selected = choice(value)
    if selected == 'modern' and not status()['modern_available']:
        raise ValueError(MODERN_UNAVAILABLE)
    return selected


def dispatch(legacy, *args, **kwargs):
    import mylar
    from mylar import tagger_handoff
    try:
        selected = choice(getattr(mylar.CONFIG, 'TAGGER_BACKEND', 'legacy'))
    except ValueError:
        mylar.logger.warn('Invalid ComicTagger backend; retaining the source without tagging')
        return tagger_handoff.Failure('unsupported')
    if selected == 'legacy':
        return legacy(*args, **kwargs)
    mylar.logger.warn(MODERN_UNAVAILABLE)
    return tagger_handoff.Failure('unsupported')
