# Validation and review

- Both Linux amd64 candidate images build from pinned upstream digests. Mylar's
  source compatibility gate passes 67 checks; the worker passes 37 real-archive
  and recovery checks. Final stages omit test suites and private configuration.
- Image selection and optional Compose contract tests pass (14 checks). Dockerfile
  lint, workflow syntax/security, source correctness lint, and local pre-commit
  gates pass. Full repository validation skips only the externally generated
  PostHog Compose bundle, as documented by that stack.
- Publication scanning covers tracked and proposed untracked files: no detected
  secrets or skipped files. The existing history scan covers 326 commits with no
  detected leaks. Gitleaks and TruffleHog separately checked the exact outgoing commit range:
  one commit, about 334 KB, with no findings. TruffleHog scanned 109 chunks
  with remote credential verification disabled.
- A separate self-review traced queue/API handoffs, bounded authenticated reports,
  preservation and durable recovery receipts, image stage contents, build contexts,
  and Compose persistence boundaries. It found a SQLite connection left open after
  series recheck; the connection and test fixtures now close explicitly. Independent
  agent review was unavailable under this session's delegation restrictions.
- Prior live acceptance for recovery, preservation, desktop navigation, and monitor
  refresh is recorded in features 006 and 007. Published-image rollout and remote
  delivery evidence is recorded below.

## Publication

[PR #106](https://github.com/bolens/homelab/pull/106) was squash-merged with all
applicable checks passing and no unresolved review conversations. Publication
revision: `e21b13be1cf3c4cc79702e5d0e60ad4b765ca943`.

Both images support `latest` and
`sha-e21b13be1cf3c4cc79702e5d0e60ad4b765ca943`. Anonymous registry requests verified
the manifests, Linux amd64 platform, SLSA provenance naming the merged revision,
and SPDX SBOMs. Pulled artifacts passed isolated runtime-content checks.

| Image | Verified digest |
| --- | --- |
| `ghcr.io/bolens/homelab-mylar3` | `sha256:4bb8598dfa8aa8ead21397a6acca9ba6a40bdb3062bcc32e413b9018a1afa997` |
| `ghcr.io/bolens/homelab-comic-normalizer` | `sha256:80879ccb4c4f6a685cb2183f63be8a7393bc94338d378c52166c433d9d82b935` |

The trusted-main image matrix, repository checks, and Pages deployment passed.
The configured Gitea mirror was verified at the same merged revision.

## Published-image rollout

The running Mylar and comic worker use the verified digests above. Their source
bind mounts were removed; persistent mounts, networks, resource limits, and private
worker settings are preserved. The original checkout was synchronized through a
scoped safety stash. A synchronization guard initially stopped on the private JSON
file becoming temporarily unignored under the old revision; the merged ignore rule
preserved it, and the deployment was completed from the correct merged Compose files.

The deployed images passed authenticated browser checks across 17 loaded pages at
1024, 1200, 1440, 2560, and 3440 pixels. Checks covered queue navigation, active-page
indicators, keyboard activation, Escape/outside dismissal, refresh theme styling,
stale-state recovery, non-overlapping requests, output escaping, and pagination.
No unexpected JavaScript or HTTP errors occurred. The post-processing page and
open desktop menu were also inspected visually.

All 684 baseline library files and 13 retained originals passed SHA-256 comparison
after deployment. Mylar and Komga databases passed integrity and original-record
checks. Both maintenance reports were fresh and error-free, all four containers
were healthy, and both Uptime Kuma worker monitors reported UP. Private worker
configuration and credentials were unchanged.

Automatic approval review rejected deletion of the merged feature branch because
branch deletion had not been explicitly authorized. The branch is retained; this
does not affect the reviewed merge, published artifacts, or deployed services.

Temporary application/library backups, isolated restores, and the task-created
source-safety stash were removed after verification. Existing backups and the
pre-existing Git stash were preserved. The primary checkout is clean at the merged
release; only the optional task-branch deletion remains blocked.
