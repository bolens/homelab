"""Backend preference and readiness shared by settings and native dispatch.

Legacy remains available throughout migration. A configured modern preference must
never silently run legacy after a modern operation fails.
"""
CHOICES = ('legacy', 'modern')
MODERN_UNAVAILABLE = 'Modern tagging is unavailable in this image.'


def choice(value):
    if type(value) is not str or value not in CHOICES:
        raise ValueError('Choose Legacy or Modern ComicTagger.')
    return value


def status():
    # Native ownership, startup recovery, live canary and rollback gates passed.
    # Job admission still verifies writer state and recovery receipts.
    return {'modern_available': True,
            'message': 'Modern is opt-in for CBZ ComicRack metadata. ComicBookLover writing '
                       'and conversion-only tagging are unsupported; use the normalizer for conversions.'}


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
    if status()['modern_available']:
        from mylar import tagger_native
        return tagger_native.run(*args, **kwargs)
    mylar.logger.warn(MODERN_UNAVAILABLE)
    return tagger_handoff.Failure('unsupported')
