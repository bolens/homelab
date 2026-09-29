# Implementation plan: Automatic library metadata maintenance

## Technical context

Python modules applied to the pinned Mylar image, SQLite workflow records, existing authenticated Activity policy controls and post-processing monitor. No new dependency, port, mount or privilege. The serialized post-processing idle poll owns admission. Shared native writer coordination excludes normalizer and native mutations.

## Constitution check

Portable opt-in settings, unchanged storage/security contracts, private runtime state and no generated-file hand edits satisfy all five principles. Live acceptance uses verified application backups and isolated fixture archives, preserves library files in place and never restarts dependent services.

## Design and source ownership

- `library_metadata.py`: bounded catalog traversal, source-version cache, missing-tag admission and durable nested-repair lifecycle.
- `metadata_repair.py`: strict identity agreement, root-preserving reconciliation, source provenance rename and archive preservation proof.
- `tagger_archive.py`: explicitly requested nested inspection; existing default stays strict.
- `tagger_adapter.py`: explicit repair operation through the existing v2 staging and publication journal, without invoking ComicTagger.
- `workflow.py` / `workflow.html`: separate opt-in policies.
- `pp_monitor.py` / `post_processing.html`: maintenance status and review outcomes.
- `patch_library_metadata.py`: checked installation, ordered after converted-tagging patch.

## Execution

One catalog file per idle poll. Keyset cursor handles issues and non-deleted annuals with unique downloaded ownership. A completed sweep waits one hour before starting another. Source-version cache avoids repeated full reads. Suspect files require bounded full archive validation and exact catalog ownership before durable admission. Existing converted-tag jobs handle missing metadata. Nested repairs use a separate workflow kind and current NFS publisher; recovery remains compatible because receipts retain the existing v2 schema and publication steps.

## Verification and delivery

Fixtures cover source/identity conflicts, provenance collisions, unsafe archives, attribute/page preservation, queue deduplication, policy gating, annuals and publication interruption. Run focused tests, isolated image gate, repository validators and CI before merge/image publication. Live activation waits for Mylar to be idle, backs up affected app state, restores/checks it in isolation, deploys only Mylar, and verifies catalog/media preservation and authenticated UI. Keep backups on uncertainty, restore prior image/state on verified loss. Do not enable background mutation until the deployed canary passes. Preserve only affected canary media, never clone the library.
