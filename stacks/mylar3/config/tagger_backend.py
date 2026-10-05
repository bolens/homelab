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
    def execute():
        if selected == 'legacy':
            return legacy(*args, **kwargs)
        if status()['modern_available']:
            from mylar import tagger_native
            return tagger_native.run(*args, **kwargs)
        mylar.logger.warn(MODERN_UNAVAILABLE)
        return tagger_handoff.Failure('unsupported')
    from mylar import native_writers
    if not native_writers.publication_mode():return execute()
    from mylar import publication_native, processing_guard
    try:
        with native_writers.operation():
            source=processing_guard.source(args[0],kwargs.get('filename'))
            before=publication_native.require(source,issueid=kwargs.get('issueid'))
            if selected == 'legacy':
                # Legacy's world-writable temporary folder and fallback .BAD
                # placement are not bounded by an owned publication job.
                # Refuse before its first copy or child until that adapter exists.
                raise publication_native.Review('tagging-legacy-transaction-required')
            def same_payload(path):
                current=publication_native.require(path,issueid=kwargs.get('issueid'))
                if (current['inventory']['payload']!=before['inventory']['payload']
                        or not publication_native.guard.same_json(current['owner'],before['owner'])
                        or not publication_native.guard.same_json(current['observed'],before['observed'])):
                    raise publication_native.Review('tagging-payload-changed',payload=current['inventory']['payload'])
            result=execute()
            same_payload(source)
            # A temporary returned path is independently checked; a failure
            # sentinel must never stand in for a successful publication proof.
            if isinstance(result,str) and result not in ('fail','unrar error','corrupt'):
                from pathlib import Path
                # Legacy permits a relative configured cache directory. Bind its
                # returned path to this call's working directory and verify it
                # before any caller copies or acknowledges the result.
                result=str(Path(result).absolute())
                same_payload(result)
            return result
    except (publication_native.guard.Unavailable,OSError,ValueError,TypeError,TimeoutError):
        review=publication_native.Review()
        processing_guard.retained(review)
        if kwargs.get('manualmeta') is True:return tagger_handoff.Published('review')
        raise review from None
    except publication_native.Review as review:
        processing_guard.retained(review)
        if kwargs.get('manualmeta') is True:return tagger_handoff.Published('review')
        raise
