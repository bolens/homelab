# Data model

A proposal binds version, source path, source SHA-256, catalog table/issue/parent, original location/status, parsed publication identity, labels, target basename and reader hash/book/progress.

A native receipt binds the exact request to a token and original inode, permissions and attributes. States record prepared, target linked, source unlinked, catalog committed, or review. Recovery proves owned source/target identity and never replaces an unrelated destination.

An explicit rejected-attempt replacement uses a version-2 request with `retry_of`. The new native journal records `predecessor_sha256`, covering the entire retained rejected record. The predecessor remains unchanged; the replacement has its own token, publication states and worker preservation set. Uncertain children are reconciled through their own token, never resubmitted through the predecessor.

A worker receipt binds the proposal to restore-verified copies. It records prepared, native submission uncertain/committed, reader pending, complete or review. No uncertain external acknowledgement is blindly replayed. Completion includes exact destination bytes, catalog ownership and reader restoration; only temporary copies for conclusively completed entries are eligible for cleanup.

A bulk manifest contains a policy/version, proposals and review reasons. Apply checks source, catalog and reader freshness again. It does not activate the daemon policy or authorize unrelated metadata writes.
