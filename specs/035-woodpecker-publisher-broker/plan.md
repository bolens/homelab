# Implementation and trust boundaries

The stack owns Go source/tests, pinned build image and dependency lock, complete
compiled dependency notices, optional Compose and Caddy fragments, private config
example, explicit preparation, metadata and operating documentation. The owning
Woodpecker step runs race tests, repository preparation fixtures and vet. Docker
and Go module updates are monitored by Dependabot.

The broker uses the same HTTPS signature library as Woodpecker 3.20.1. A public
PEM pin identifies the intended instance; database-backed server signing state
normally survives restart. Private files supply the publication App key and
limited GHCR PAT. A persistent local directory holds signature fingerprints and
hashed capability records. Only one broker process may own it.

The compiler extension validates before issuing a capability, using a revoked
after-use read-only inspection token. Redemption reserves an attempt atomically,
revalidates current source/flag metadata and mints a newly scoped installation
token. Public helpers send no credentials in URLs and retain tokens only in
memory. Root coordinates helper integration, OAuth/App permissions, live files,
Caddy routing, pipeline settings, backups, deployment and acceptance.

Constitution checks: portable examples use placeholders; all stack contract
surfaces move together; preparation preserves operator state and never starts
containers; network/credential boundaries are explicit; generated metadata must
be regenerated from source if delivery updates catalogs. No source change
expands operational authority or replaces existing data-retention policy.
