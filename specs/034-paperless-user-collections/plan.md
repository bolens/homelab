# Plan: Paperless user collections

Use Paperless ownership for privacy and its filename template for owner directories.
Add an opt-in originals bind override with `create_host_path: false`. Keep existing
media state and other volumes. Update the environment example, preparation guidance
and README. Ingress and base Compose remain unchanged. Existing metadata volume roles
remain accurate because the optional bind replaces only the originals subtree.

Record live state privately outside Git. Verify the remote storage mapping, account
roles, ownership defaults and integrations. Quiesce Paperless and Redis, stop PostgreSQL,
copy all persistent state and configuration, verify restored hashes, and start only an
isolated restored PostgreSQL to prove database readability. Keep the original image.
Configure fallback and account-specific consume workflows, enable the bind and filename
template, and prove privacy and storage with disposable documents. Remove test data
and temporary backup/restore copies only after acceptance. Roll back from verified
state with the prior image if preservation fails.

Constitution: portable examples, opt-in storage, unchanged ingress, no secret output,
verified backup, explicit operational scope and read-only repository validation.

Validation: isolated base-plus-override rendering, missing-directory contract,
`make validate`, runtime mount/template checks, native database restore, two-account
privacy/download checks and baseline comparison. Report unrelated gate failures.
