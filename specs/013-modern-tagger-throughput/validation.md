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

GitHub checks, published image and Mylar-only deployment evidence are pending.
No dependency, runtime configuration, permission, mount or port changes are needed.
The existing backup/isolated-restore/preservation/rollback workflow applies to deployment.
