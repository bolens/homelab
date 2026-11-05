# Trusted Woodpecker publisher credentials

Status: implementation in progress; live deployment and publication are pending.
This contract records the approved design and remaining proof during development.

## User scenarios

1. A trusted native GitHub pipeline waits behind other CI work, then obtains a
   fresh repository-scoped credential immediately before publishing. Queue time
   does not consume the installation-token lifetime.
2. An untrusted PR, fork, feature, manual or cron pipeline receives no publication
   authority, including when it forges similarly named environment variables.
3. An operator explicitly prepares and deploys an optional broker without
   replacing existing stack configuration, keys, data or agent registration.

## Requirements

- Authenticate genuine Woodpecker 3.20.1 signed extension requests using the
  pinned instance Ed25519 PEM key and official signature helper; validate body
  digest, target, freshness and persistent replay protection. Transfer no netrc.
- Bind an explicit four-repository native GitHub allowlist by forge ID, remote
  repository ID, full name, event/ref and exact commit. GitHub metadata must
  establish `WOODPECKER_PUBLISHING=true`, repository identity and protected main.
- Main publication must use the current protected main SHA. Release tags must be
  annotated, cryptographically verified, correctly bound, unchanged when reread,
  and reachable from protected main. Audio permits main CD; the other three
  permit main Pages and signed release tags.
- Return a 256-bit opaque `github_publish_lease` with 12-hour validity. Persist
  only its hash and bound metadata. Authenticate TLS redemption by capability;
  match repository, SHA, purpose and fresh 128-bit request ID. Share the pipeline budget across all its leases, limit attempts to
  eight or fewer, reject repeated request IDs and revalidate source policy at
  every use. Installation credentials remain in helper memory and expire in one
  hour; refresh near expiry rather than caching them on shared disk.
- Keep App keys and GHCR PAT source files private and read-only. Return GHCR
  credentials only for Audio main/uDDNS tags, with exact Kaniko image/event
  filters. Command-based GitHub lease consumers have no plugin image filter.
- Fail closed on malformed, stale, replayed, mismatched, revoked or unavailable
  authorization. Operators must remove overlapping local fallback secrets.
- Add no public host port, Docker socket, privileged job, live application
  operation or automatic broker activation. Caddy exposes only the exact TLS
  redemption route; the extension remains internal. Bound requests, concurrency,
  rate, HTTP deadlines, credential logging and writable state.

## Acceptance evidence

Source tests must cover legitimate signed requests and denied signature/body/time
variants, replay across restart, source/ref/forge/remote-ID/destination mismatches,
lease lifetime and attempt persistence, changed authorization, GitHub metadata
failures, unsigned/retargeted/unreachable tags, private state and redaction.
Verify preparation twice with isolated public fixtures and a stub Docker CLI.
Validate source, licenses, Compose, ingress and the intended image runtime.

Only independent review plus genuine server signatures, credential/proxy/queue
fixtures, backup recovery and unchanged-state checks can establish live readiness.
Source tests do not establish publication, deployment or protected-check cutover.
