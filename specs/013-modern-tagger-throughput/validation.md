# Validation: modern tagger throughput

## Controlled measurements

Five runs per version, 64 MiB generated stored-page CBZ, local temporary filesystem,
real Service/Publisher/handoff and mocked CLI, no provider/network time:

| Path | Baseline median | Candidate median | Result |
| --- | --- | --- | --- |
| Existing ComicInfo, preserve policy | 0.3312 s | 0.2630 s | 20.6% lower elapsed time; no archive staging |
| Missing metadata | 0.6933 s | 0.6948 s | Unchanged within run variability |

Baseline is the adapter at commit d8634e3; both versions use identical fixtures.
These are local controlled measurements, not NFS or live throughput claims.
Full archive snapshots and final source verification remain in both versions.
A real worker/loopback HTTP test confirms two same-volume issues make three
provider requests instead of four and return the same metadata. Each actual
request retains its configured delay; a cache hit avoids one volume request and
its delay. Ten same-volume issues within the TTL consequently need eleven
requests instead of twenty; this is an extrapolation from the request contract.

## Regression evidence

74 focused cache, worker, publication, NFS-publication and service tests pass;
one real pinned-CLI test requires the image and is skipped on the host.
New negative cases cover fixed expiry, expiry during the issue request, credential,
endpoint and TLS isolation, capacity, oversized entries, malformed identities,
failed responses, source/attribute races and interrupted empty workspaces.

An initial broad host discovery invocation was unsuitable for source-patch tests
that require a Mylar source-directory argument (15 setup errors). The focused
modules pass; the image gate supplies the required source argument for all modules.

## Delivery gates

The full candidate image gate passed, including pinned real-CLI checks. `make
validate` and `make ci-local` passed. The first full hook run detected concurrent
staging as a changed-file condition; a stable rerun passed without suppressions.

Two independent reviews inspected cache/worker contracts and publication/recovery/
packaging. The cache reviewer reproduced an output-budget regression, including warnings on
stderr: optional cache data could exceed the runner's combined 64 KiB budget for
large valid metadata. The final protocol keeps stdout unchanged and transfers
optional cache data through a bounded 0600 sidecar in the existing private lookup
directory. Sidecar failures are cache misses and cleanup removes it with the request.
Real worker reuse and large metadata plus stderr regressions pass. Preservation
review found no defects or actionable nits. Review follow-up covers the final repair.

PR [#159](https://github.com/bolens/homelab/pull/159) merged as
`4baf57f36ff6942ac43d03c272cd6ed97b41eedd` after all current-head checks passed.
The final reviewed head was `30be0704c0256c668047ce6aded955e1a4d3406f`.
Post-merge validation, CodeQL, source lint, Pages and custom-image publication all
passed. The final local image gate also passed with the sidecar protocol.
Gitleaks and a TruffleHog scan of the candidate commit range reported no secrets.

Published image:
`ghcr.io/bolens/homelab-mylar3@sha256:6a79526bb5de5eac63eabeb551b8b8f6728a46adb0167d855dc10d95780c0c52`.
The pulled image's lookup, cache and publication modules match the merged sources
by SHA-256. Local main and the authorized mirror were synchronized to the merge;
the exact merged feature branch was removed locally and confirmed absent remotely.

The published digest is deployed. The rollout drained active processing, verified a
quiesced application backup against an isolated restore by file hashes and SQLite
integrity checks, and verified library files in place without copying the library.
Post-update catalog identities, downloaded issue/annual statuses and locations,
and existing library sizes/timestamps matched the baseline. Every Mylar setting
was preserved. A fixture executed through the deployed package's NFS publisher
verified unchanged publication, cleanup and a valid handoff without touching comics.

Both Mylar monitors in Uptime Kuma confirmed health after restart. NZBGet, Komga,
the normalizer and Uptime Kuma retained their container identities/start times and
were healthy. The original DDL pause policy was restored. Only this operation's
backup and isolated restore were removed after success. No real power-loss test
was performed, and no rollback was needed.
No dependency, runtime configuration, permission, mount or port changes are needed.
The existing backup/isolated-restore/preservation/rollback workflow applies to deployment.
