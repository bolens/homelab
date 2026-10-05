"""Native publication also transfers previously confirmed pack evidence."""
import sys

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
    def backend_name(self):
        job=self.publication_job()
        if job is not None and job.value['policy'].get('backend')=='legacy':return 'legacy-1.3.5'
        return super().backend_name()

    def save_metadata(self,staged,metadata,**kwargs):
        job=self.publication_job()
        if job is None or job.value['policy'].get('backend')!='legacy':
            return super().save_metadata(staged,metadata,**kwargs)
        if __package__:
            from . import tagger_legacy, publication_native as native
        else:
            import tagger_legacy
            import publication_native as native
        try:
            record=self.read(job.value['token'])
            if str(staged)!=str(self.workspace(record)/'tagged.cbz'):
                raise native.Review('tagging-legacy-workspace-changed')
            job.proof(staged)
            result=tagger_legacy.save(staged,metadata,**kwargs)
            job.proof(staged)
            return result
        except (OSError,ValueError,TypeError,KeyError):
            raise native.Review('tagging-legacy-output-unavailable') from None

    def __init__(self, root, config_root):
        super().__init__(root)
        self.config_root = config_root

    def publication_job(self):
        runtime=sys.modules.get('mylar')
        if runtime is None or not runtime.native_writers.publication_mode():return None
        if __package__:
            from .publication_transaction import current
        else:
            from publication_transaction import current
        return current()

    def correction_checkpoint(self,record,*,cleanup=False):
        job=self.publication_job()
        if job is not None:
            try:
                job.publisher_check(self,record)
                if cleanup:job.publisher_cleanup(self,record)
            except (OSError,ValueError,TypeError,KeyError):
                if __package__:
                    from .publication_native import Review
                else:
                    from publication_native import Review
                raise Review('tagging-publication-unavailable') from None

    def tag(self,source,metadata,*,token,**kwargs):
        job=self.publication_job()
        if job is not None:
            expected=job.publisher_source(self,source)
            if token!=job.value['token']:
                if __package__:
                    from .publication_native import Review
                else:
                    from publication_native import Review
                raise Review('tagging-token-changed')
            job.proof(expected)
        return super().tag(source,metadata,token=token,**kwargs)

    def write(self,record):
        job=self.publication_job()
        self.correction_checkpoint(record)
        try:
            return super().write(record)
        except (OSError,ValueError,TypeError,KeyError):
            if job is None:raise
            if __package__:
                from .publication_native import Review
            else:
                from publication_native import Review
            # A failed durable receipt is an interrupted owned job. Ordinary
            # tagger recovery must not clean or advance its prepared copies.
            raise Review('tagging-receipt-write-unavailable') from None

    def prepare_output(self,output,record):
        self.correction_checkpoint(record)
        job=self.publication_job()
        if job is not None:job.proof(output)
        return super().prepare_output(output,record)

    def publish(self,source,output,record):
        self.correction_checkpoint(record)
        job=self.publication_job()
        if job is not None:
            if job.value['policy']['manualmeta']:
                job.bind_in_place(self,record,output)
            job.proof(output)
        return super().publish(source,output,record)

    def _recover(self,record):
        self.correction_checkpoint(record)
        return super()._recover(record)

    def recover(self,token):
        job=self.publication_job()
        if job is not None and token!=job.value['token']:
            if __package__:
                from .publication_native import Review
            else:
                from publication_native import Review
            raise Review('tagging-replay-unbound')
        return super().recover(token)

    def recover_pending(self):
        if self.publication_job() is not None:
            if __package__:
                from .publication_native import Review
            else:
                from publication_native import Review
            raise Review('tagging-replay-unbound')
        yield from super().recover_pending()

    def publication_security(self, source):
        job=self.publication_job()
        binding=job.bind_publisher(self,source) if job is not None else None
        security = super().security(source)
        if binding is not None:security['correction_guard']=binding
        security['pack_bindings'] = pack_bindings.capture(
            store(self.config_root), source, source)
        return security

    def read(self, token):
        record = super().read(token)
        job=self.publication_job()
        if job is not None and token!=job.value['token']:
            job.closed_history(self,record)
        else:self.correction_checkpoint(record)
        intent = record.get('pack_bindings')
        pack_bindings.validate(intent)
        if intent is not None and (intent['source'] != record['source'] or intent['destination'] != record['source']
                or any(b['before']['destination_sha256'] != record['before'] for b in intent['bindings'])):
            raise ValueError('Pack transition does not match publication')
        return record

    def finish(self, record, state, *, cleanup=True):
        self.correction_checkpoint(record,cleanup=cleanup and state in ('committed','unchanged','failed','timed_out','unsupported'))
        if cleanup and state == 'committed' and self.committed_intact(record):
            pack_bindings.finalize(store(self.config_root),
                                   record.get('pack_bindings'), record['after'])
        elif cleanup and state in ('failed', 'timed_out', 'unchanged') and self.original_intact(record):
            pack_bindings.finalize(store(self.config_root),
                                   record.get('pack_bindings'), record['before'])
        self.correction_checkpoint(record)
        return super().finish(record, state, cleanup=cleanup)
