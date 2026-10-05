"""Native publication also transfers previously confirmed pack evidence."""
if __package__:
    from . import pack_bindings, workflow_store
    from .tagger_nfs import Publisher as NFSPublisher
else:
    import pack_bindings
    import workflow_store
    from tagger_nfs import Publisher as NFSPublisher


def store(root):
    if __package__:
        from . import native_writers
        return native_writers.existing_store(root)
    return workflow_store.Store(root)


class Publisher(NFSPublisher):
    def __init__(self, root, config_root):
        super().__init__(root)
        self.config_root = config_root

    def publication_security(self, source):
        security = super().security(source)
        security['pack_bindings'] = pack_bindings.capture(
            store(self.config_root), source, source)
        return security

    def read(self, token):
        record = super().read(token)
        intent = record.get('pack_bindings')
        pack_bindings.validate(intent)
        if intent is not None and (intent['source'] != record['source'] or intent['destination'] != record['source']
                or any(b['before']['destination_sha256'] != record['before'] for b in intent['bindings'])):
            raise ValueError('Pack transition does not match publication')
        return record

    def finish(self, record, state, *, cleanup=True):
        if cleanup and state == 'committed' and self.committed_intact(record):
            pack_bindings.finalize(store(self.config_root),
                                   record.get('pack_bindings'), record['after'])
        elif cleanup and state in ('failed', 'timed_out', 'unchanged') and self.original_intact(record):
            pack_bindings.finalize(store(self.config_root),
                                   record.get('pack_bindings'), record['before'])
        return super().finish(record, state, cleanup=cleanup)
