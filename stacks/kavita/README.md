# Kavita

Comics, manga, and eBook server with a built-in web reader, OPDS support, and reading progress. Single app for mixed libraries (CBZ, CBR, EPUB, etc.). Can run alongside Komga and Calibre-Web or replace one of them depending on preference.

**Homepage:** https://www.kavitareader.com  
**GitHub:** https://github.com/Kareadita/Kavita  
**Docker (LinuxServer):** https://docs.linuxserver.io/images/docker-kavita  

Access via Caddy at **https://kavita.yourdomain.com** (or your configured hostname).

## Quick start

1. Copy `stack.env.example` → `stack.env`; set the library paths and optionally `PUID`, `PGID`, and `TZ`.
2. From the stack directory: `docker compose up -d`.
3. Open the web UI and add separate libraries rooted at `/data/calibre-books`, `/data/comics`, and `/data/manga`.

**Portainer:** Add stack → paste `docker-compose.yml` → set env vars → deploy.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy only (no host port; reverse-proxy to `kavita:5000`) |
| **Network** | `ingress-public` for dedicated Caddy-to-service traffic |
| **Images** | `lscr.io/linuxserver/kavita:latest` |
| **Storage** | Local `kavita_config`; books, Calibre exports, comics, and manga are mounted read-only below `/data` |

## Calibre compatibility

Use Calibre as the metadata source and export copies to
`KAVITA_CALIBRE_EXPORT_PATH`. Configure a Kavita **Book** library rooted at
`/data/calibre-books`. Do not point that library at `/data/books`: Calibre's
database tree and Readarr's source files can expose duplicate books and loose
files that violate Kavita's scanner layout.

Mylar3 remains the writer for `/mnt/unraid/media/comics`; Kavita and Komga only
scan it. Keep manga in `/mnt/unraid/media/manga`. Each series must have its own
subdirectory, and files must not sit directly in either library root.

Install `scripts/calibre-kavita-sync.sh` as
`/usr/local/libexec/calibre-kavita-sync`, install the matching units from
`scripts/systemd/`, then enable `calibre-kavita-sync.timer`. The timer runs
daily at 04:30 local time with up to ten minutes of randomized delay.

## Caddy reverse proxy

Add a site block for the Kavita hostname (e.g. `kavita.yourdomain.com`):

```
kavita.yourdomain.com {
	reverse_proxy kavita:5000
}
```

## Health and monitoring

Kavita does not expose a dedicated health endpoint. Use a generic HTTP check to the app URL (e.g. `https://kavita.yourdomain.com`) in Uptime Kuma.

## Media preparation prerequisite

Verify the configured media directories exist on the intended filesystem before
running preparation. The helper refuses to create missing media paths. Directory
existence alone does not verify the remote mount; check its source and access.

## Independent provider services (experimental)

`docker-compose.providers.yml` selects a locally built Kavita integration and a
private provider gateway. The gateway connects directly to provider APIs. It does
not use the hosted Kavita+ backend or create a paid subscription. The default
Compose deployment stays stock.

This is an incomplete implementation of the requested feature parity. Fixture
tests and source compilation do not prove provider acceptance or live readiness.
The current coverage is:

| Feature | Current implementation | Remaining acceptance |
| --- | --- | --- |
| Hardcover metadata/covers | Direct book/series GraphQL adapter | Genuine token-backed field and series/edition checks |
| MangaBaka metadata/covers | Public search, detail, image, relationship and edition APIs | Full requested field coverage |
| Recommendations and reviews | Provider-supported Hardcover and MangaBaka feeds | Review availability/privacy, pagination and missing feeds |
| Personal reading sync | Direct AniList, MAL, Hardcover and MangaBaka adapters | Each account, scope, action and recovery path |
| MangaBaka account sync | Account identity, private library status/progress/rating and guarded removal | Genuine account and scope acceptance |
| ComicBookRoundup | Cached lookup in up to six publisher indexes, exact URL details, ratings and critic/user excerpts | Partial publisher coverage; series review enrichment is bounded |
| Want-to-read import | Exact provider IDs with library/access filters; ambiguous matches skipped | Intended-account acceptance for each provider |
| OAuth onboarding | Fixed native callback, single-use browser-bound state, PKCE and persistent refresh protection | Registered clients and real provider exchanges |

Use the gateway's authenticated `/capabilities` endpoint for its current detailed
limits. Missing providers or actions fail explicitly. Personal controls and queue admission use the selected provider's sync-adapter
action capabilities. Unsupported saved preferences remain stored. Unconfirmed
events remain pending through outages and rate limits. Rereads and unread resets
remain held. AniList/MAL planning-entry removal refuses entries with other account
data and verifies absence before acknowledging deletion. Native personal token forms
can be used where supported. The Hardcover catalog credential is never a fallback
credential for a user's reading updates.

### Private configuration

Create a private directory outside the checkout with mode `0700`. Put a shared
key of at least 32 characters in `provider_key` and a Hardcover API token in
`hardcover_token`. The latter may be empty until configured. Set the following
paths in the ignored `stack.env`, preserving every existing setting:

```dotenv
KAVITA_PROVIDER_KEY_PATH=/path/to/private/kavita/provider_key
KAVITA_HARDCOVER_TOKEN_PATH=/path/to/private/kavita/hardcover_token
# Optional account onboarding:
KAVITA_PUBLIC_URL=https://kavita.yourdomain.com
KAVITA_OAUTH_CLIENTS_PATH=/path/to/private/kavita/oauth-clients.json
```

Copy `providers/oauth-clients.json.example` to that private directory with mode
`0600` and fill each registered provider application's client ID and client
secret when available. Blank entries disable onboarding for that provider.
Register the exact callback `${KAVITA_PUBLIC_URL}/api/oauth/independent-callback`.
`KAVITA_PUBLIC_URL` must be the fixed HTTPS origin (and optional base path).
Tokens travel in private request bodies. Browser callbacks contain only the
provider authorization code and single-use state. Uncertain code exchanges or
refresh attempts require reconnecting; the gateway never retries a refresh token
whose prior outcome is unknown.

The gateway runs as UID/GID 1000. Its secret files must be readable by that UID
inside the container. For a UID 1000 operator, mode `0600` is sufficient. Keep
the private parent protected. Local Compose file secrets preserve host ownership.
The shared key must also be readable by Kavita's configured PUID.
Do not put tokens in build arguments, image layers or tracked examples. Configure
each user's personal provider connection in Kavita separately.

### Build and validate

The custom application is pinned to upstream commit
`879b8b73eb41d66f88dde8eb874cc99a3397eb11` and the LinuxServer base recorded in
[`independent/Dockerfile`](independent/Dockerfile). The upstream tag is v0.9.1.4,
although that tag's assembly version declares 0.9.1.3. Preserve the source pin
and custom build identity when checking compatibility. It retains LinuxServer's
PUID/PGID, s6 and `/config` contract. The build currently targets Linux amd64.

```bash
python3 -m unittest discover -s stacks/kavita/providers -p 'test_*.py'
python3 -m unittest discover -s stacks/kavita/independent -p 'test_*.py'
```

The full patch test requires `KAVITA_SOURCE_EXPORT` to point at a pristine export
of the pinned source. The native response test additionally requires
`KAVITA_MODEL_ASSEMBLY` to point at its compiled `Kavita.Models.dll`, and the exact
reading-list matcher test requires `KAVITA_SERVICES_ASSEMBLY` for the compiled
`Kavita.Services.dll`. Without those inputs, the corresponding checks report skips.

From the stack directory, build the images without recreating the running app:

```bash
docker compose --env-file stack.env -f docker-compose.yml \
  -f docker-compose.providers.yml build
```

The provider network allows outbound HTTPS but publishes no host port. Caddy
continues to proxy only Kavita. Do not expose the gateway or its token-bearing
sync routes through ingress. Its `/healthz` checks the process, not provider health.

If Docker has exhausted its automatic address pools, use a local override with
an explicit unused subnet for `kavita-providers`. Check Docker networks and host
routes for overlap first. Preserve every existing network.

### Live rollout and rollback

CI publishes experimental `homelab-kavita-independent` and
`homelab-kavita-providers` images under `ghcr.io/bolens`. To use them, set
`KAVITA_INDEPENDENT_IMAGE` and `KAVITA_PROVIDERS_IMAGE` to matching
`sha-<commit>` tags and remove both `build:` blocks from a private copy of the
provider override. The shipped override retains local builds. Publication proves
the build, not genuine provider-account behavior or full feature parity.

Pass image and restored-state application checks before selecting this override
against live state. A requested experimental rollout with placeholder credentials
must retain explicit provider acceptance gaps and reject unsupported operations.
Full provider readiness requires genuine intended-account scenario checks. Follow [AGENTS.md](../../AGENTS.md#live-configuration-and-updates):
capture the actual image/configuration and application-data baseline, quiesce
Kavita, back up its configuration and complete persistent application state,
and verify an isolated restore before recreation. Media mounts remain read-only.
Back up `kavita_provider_state` too after its first use; it contains confirmed
sync receipts and cached provider data. Keep credentials private and preserve
existing backups.

After rollout compare library titles, users, reading progress, bookmarks and
metadata locks with the baseline. Verify each advertised provider operation.
For recovery, stop the modified app and restore the verified compatible image,
configuration and application state. Omitting the override restores the stock
image selection but does not undo database changes by itself. External account
writes also need their own before/after evidence and recovery plan.

Feature scope and outstanding acceptance are tracked in
[`specs/028-kavita-independent-services`](../../specs/028-kavita-independent-services/tasks.md).
Distributed modified images must include the corresponding source and retain
upstream license notices. See [`independent/NOTICE`](independent/NOTICE).

### Recovery and storage retention

Clearing independent account credentials holds pending synchronization events until reconnection. A private, authenticated capability snapshot in the existing Kavita configuration volume preserves creation eligibility across restart during a gateway outage. It is bound to the gateway origin and shared key and never authorizes delivery. Include it in normal configuration backups.

Provider metadata cache is limited to 1024 entries/32 MiB. New progress writes reserve protected receipt capacity before a provider mutation. Confirmed progress, ambiguous outcomes and old unclassified receipts retain retry protection. Reconciled-operation receipts can expire after seven days, with a maximum of 1024 recent entries. Combined receipt/reservation capacity is 100000. Full protected capacity holds new writes for operator review. Do not delete protected receipts as routine cleanup. The main SQLite database has a 512 MiB page budget, with separate WAL checkpointing. Continue monitoring filesystem free space.
