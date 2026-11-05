# Optional publisher credential broker

[Stack documentation](../README.md)

This service targets Woodpecker **3.18.1** and four explicitly configured native
GitHub repositories: Appicon, AUR Response Toolkit, uDDNS, and Audio Utils. It is
an optional secret extension, not a registry or a replacement CI server. It
publishes no host ports and mounts neither a Docker socket nor a host Nix store.

## Trust and credential flow

Woodpecker fetches extension secrets while compiling the pipeline, **before**
work enters the agent queue. A GitHub installation token minted then can expire
before a publisher runs. The extension therefore returns `github_publish_lease`,
a 256-bit opaque capability valid for 12 hours. Only its SHA-256 hash and signed
source metadata are persisted. App private keys and the GHCR PAT remain in
read-only private files; neither enters a pipeline or image build context.

1. `/secrets` accepts only Woodpecker's RFC 9421 Ed25519 signatures over
   `@request-target` and `content-digest`, verified with the pinned instance PEM
   key and the same `httpsign` library version used by Woodpecker 3.18.1. The
   signature must be no older than 30 seconds or more than 3 seconds in the
   future. Authenticated signature fingerprints persist across restarts.
2. Repository forge ID, immutable GitHub repository ID, exact full name, source
   SHA and event/ref must match the private allowlist. PRs, forks, feature
   branches, manual runs, cron jobs and any transferred `netrc` are denied.
3. A short-lived, single-repository read-only inspection token verifies GitHub
   repository identity, `WOODPECKER_PUBLISHING=true`, and protected `main`.
   Pushes must match its current SHA. Releases require an annotated, verified
   signed `vX.Y.Z` tag pointing to the pipeline commit, reachable from protected
   `main`; the tag ref is reread to detect retargeting. Inspection tokens are
   revoked after use. GitHub API redirects, errors and missing metadata deny
   authorization.
4. Immediately before publishing, a trusted helper redeems its capability over
   TLS. The broker repeats the policy and GitHub checks and mints a fresh,
   single-repository installation token with only the configured permissions.
   The helper keeps it in memory and refreshes with a new request ID when fewer
   than 120 seconds remain. The App key is never sent to the helper.

The public URL is the configured Woodpecker origin plus `/publisher/credentials`.
Explicitly import `caddy_routes.conf.example` and use its named snippet in the
one configured HTTPS site, replacing that site's bare proxy. The base ingress
example does not activate this route. Caddy rewrites this exact path to `/redeem`. It must not expose `/secrets` or
`/healthz`. Send credentials only in a POST JSON body, never a URL:

```json
{
  "lease": "REPLACE_WITH_PIPELINE_CAPABILITY",
  "repository": "example-owner/uddns",
  "commit": "REPLACE_WITH_EXACT_SOURCE_SHA",
  "purpose": "github",
  "request_id": "REPLACE_WITH_FRESH_32_LOWERCASE_HEX_CHARACTERS"
}
```

The response contains `token` and RFC 3339 `expires_at`. Do not print, persist,
cache on shared disk, or pass the token to unrelated subprocesses. Strip inherited
GitHub/debug/trace variables from authenticated child environments. Each lease
allows eight redemption attempts by default (configurable downwards), including
failed or ambiguous attempts. Reusing a request ID returns 409 without minting.
This covers independent publisher phases and bounded refresh/retries without a
shared token file. Rate limits allow 32 requests in a burst, refill at two per
second, and permit at most eight simultaneous redemptions. A saturated, expired,
replayed or unavailable authorization path fails closed.

`github_publish_lease` intentionally has no image filter: Woodpecker's plugin
filter rejects command-based publisher helpers. The strong boundary is the
signed native forge/repository/ref and immutable source policy. Static
`ghcr_username` / `ghcr_password` are returned only for Audio main pushes and
uDDNS release tags when configured, restricted to the exact reviewed Kaniko
image digest and event. Pull-only registry credentials serve a different purpose.

**Woodpecker falls back to local secrets when an extension fails.** Before
cutover, verify that repository, organization and global scopes contain none of
`github_publish_lease`, `github_publish_token`, `ghcr_username` or `ghcr_password`
as a publication fallback. Keep global and per-repository netrc transfer disabled.
The broker does not enable publishing merely because a pipeline supplies a
similarly named environment variable: it reads the GitHub repository variable.

## Private preparation

From the owning stack directory, explicitly opt in:

```sh
WOODPECKER_PREPARE_PUBLISHER_BROKER=1 ./prepare-stack.sh
```

This creates ignored, operator-owned directories with mode 0700 and copies
`config.json.example` only if no configuration exists. It does not create keys,
print credentials, activate the override, or start any service. Set
`WOODPECKER_BROKER_UID` / `WOODPECKER_BROKER_GID` to the owner of these files.
Preparation never changes ownership or overwrites an operator file.

Under `publisher-broker/runtime/private`, supply:

- `config.json`, mode 0600, containing actual forge/repository/installation IDs,
  the App ID, public HTTPS origin, narrow trusted Caddy source IP/CIDR, username,
  and per-repository permissions. The example deliberately fails validation.
- `woodpecker-public.pem`, the independently verified Ed25519 public key from
  the intended server's `/api/signature/public-key` endpoint.
- `github-app.pem`, mode 0600, from the publication App installed only on the
  four intended repositories. Contents read/write and Actions permissions are
  independently scoped by repository; Variables read is required for the flag.
  Current Pages publication writes the existing `gh-pages` branch and needs no
  Pages API permission. Appicon/uDDNS dispatch paths need Actions write.
- `ghcr-token`, mode 0600, with only the required package-publishing authority
  for Audio/uDDNS. Keep it out of `stack.env` and pipeline command environments.

All mounts are explicit and refuse missing host paths. The state directory
contains `replay/` and `leases/`, also mode 0700, writable only by the broker UID.
Run one broker instance against this directory; its lock serializes state writes
within that process. Do not share this filesystem between replicas.

Configure only the four native GitHub repositories' secret extension as
`http://publisher-broker:8080/secrets`, without netrc transfer. The optional Compose
override allows private extension destinations. If the server already uses other
extensions, review its host allowlist rather than replacing unrelated choices.
Caddy and the broker share `ingress-admin`; server-to-extension traffic uses the
stack network. Only exact trusted proxy peers can assert forwarded HTTPS/host.
The normal agent build networks do not need direct access to the internal
extension endpoint.

## Review, verify and operate

Before changing live state, record image/configuration paths, database identities
and counts, signing-public-key hash, and existing secret/registry metadata without
values. Make an application-consistent database backup plus private broker/config
and agent-registration backups. Verify an isolated restore and integrity before
changing any configuration. Preserve unrelated services and settings.

Build and select the override only after configuration and independent review:

```sh
docker compose -f docker-compose.yml -f docker-compose.publisher-broker.yml build publisher-broker
docker compose -f docker-compose.yml -f docker-compose.publisher-broker.yml up -d --no-deps publisher-broker
```

Any required server or Caddy recreation/reload is a separate scoped step after
running workflows drain. The default stack remains independent of this override.
Verify health, a genuine signed extension request, real proxy/TLS routing,
absence of fallback secrets, negative PR/feature cases, an authorized source
fixture, expired/replayed leases, and a queued publisher redeeming just in time.
Use isolated fixtures rather than publishing a real release as a probe. Verify
unchanged database identities, records and agent registration after the change.

The instance signing key is stored in Woodpecker's database under
`signature-private-key`, so normal restarts preserving the database retain the
PEM key. Compare its hash before/after restart; never automatically trust a new
key. On failed acceptance, restore the verified configuration/state and prior
compatible image. Retain backups when verification is inconclusive. Remove only
operation-created temporary backup/restore copies after successful acceptance.

Local source validation:

```sh
go test -race -tags repositoryfixtures ./...
go vet ./...
```

The root Woodpecker workflow runs these commands in a pinned Go image. The
Dockerfile builds a static binary in a pinned builder and includes CA certificates
in a scratch runtime; its allowlisted build context excludes runtime files.
The `repositoryfixtures` tag additionally validates real preparation against an
isolated copy with a stub Docker CLI; the narrow image build context runs the
self-contained service tests. Mocked tests cover signatures, freshness, persistent replay, lease scope/lifetime,
redemption limits, TLS/proxy trust, source metadata and signed-tag binding. They
do not establish live credentials, routing, backup recovery or publication.
