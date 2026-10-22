# Independent Kavita image

Build from this directory with `docker build -t kavita-independent:0.9.1.4-local .`.
The image pins upstream commit `879b8b73eb41d66f88dde8eb874cc99a3397eb11`
(tag `v0.9.1.4`) and the installed LinuxServer base digest. This tag's source
AssemblyVersion is `0.9.1.3`; the custom image name does not change that assembly value.
Only Linux amd64 is supported. Node and SDK image digests and application dependency lockfiles
are fixed; build-stage OS package repositories still resolve their current packages.
This is source-pinned, not a claim of bit-for-bit reproducible output.

Set `KAVITA_PROVIDER_URL=http://kavita-providers:8080` and
`KAVITA_PROVIDER_KEY_FILE=/run/secrets/provider_key` through the opt-in Compose override.
The key file must contain at least 32 characters and match the gateway's key. Requests use
`X-Provider-Key`. Redirects are disabled. Billing/license endpoints are refused before
sending requests in independent mode. The official paid-license service continues to
return false/null, and its UI remains separate from functional capability state.

Capabilities are loaded from authenticated `/capabilities` protocol version 1, cached for
30 seconds, and exposed to authenticated Kavita users at `/api/providercapabilities`.
Unavailable or incompatible manifests disable functional gates. Settings displays the
independent status and gateway limitations. Existing roles, users and library rules remain
in place. This patch does not implement provider APIs itself.

Personal controls and native event admission use the selected provider's sync-adapter action capabilities. Unsupported saved settings remain stored and existing events remain pending.
Rereads and unread resets are held. Delivery requires a current supported manifest and explicit
success. During transport outages, creation retains previously supported actions so new
reading events survive. Provider cooldowns persist across gateway restarts. AniList/MAL
planning-entry removal preserves other account data and verifies absence before confirmation. OAuth onboarding uses the existing public Kavita origin and a private gateway exchange.
MAL stacks, unsupported sync
operations, ComicBookRoundup coverage and full parity remain acceptance gaps. Changing
capabilities requires a page reload to refresh frontend state. No paid license, billing
response or successful unsupported operation is fabricated.

## Exact Want-to-Read import matching

Independent imports use only each list entry's authoritative provider ID and its originating
provider. Names, authors, synonyms and informational cross-provider IDs never select a
local book. AniList and MAL may use an exact parsed manga WebLink when the corresponding
local provider ID is unset. Prefix IDs, spoofed hosts, conflicting links/IDs and multiple
visible matches are rejected. MangaBaka uses the exact local `Series.MangaBakaId`.

Hardcover book entries must carry `isStandAlone: true`: their ID can match a standalone
local series or an exact chapter book ID mapped to its parent series. A provider series ID
with the same number does not match a book. Ambiguous containers are skipped. Matching
uses the existing library-membership and age-restriction repository path before choosing
one visible result, and caps database candidates at 1000. Official matching remains
unchanged. Provider-list API acceptance and capability advertisement are separate gates.

## Token validity and unknown expiry

Independent mode treats OAuth and personal tokens as opaque credentials. Actual expiry
comes only from the gateway's issued-token registry; it never derives an expiry from an
assumed JWT format. A missing registry entry means unknown expiry, not expired or valid
forever. A successful provider account lookup permits a personal token to be used without
inventing a timestamp. Failed account checks retain pending events for retry. Stored
legacy timestamps are preserved when expiry is unknown, and independent settings and
admin views explicitly show "Expiry unknown" instead of presenting those timestamps.
Expiry emails and automatic refresh decisions use only actual registered expiry.

The source patch retains official-mode token behavior, including its existing local
checks. Set `KAVITA_SERVICES_ASSEMBLY` to the compiled pinned `Kavita.Services.dll` to
exercise the native private expiry method against the isolated registry fixture for all
four providers, including opaque tokens and unknown personal-token expiry.

## OAuth callback boundary

Set `KAVITA_PUBLIC_URL` to the fixed public HTTPS Kavita URL, including its base path
if present. Configure each provider client to redirect to
`<KAVITA_PUBLIC_URL>/api/oauth/independent-callback`. The gateway derives the same
callback from its `KAVITA_PUBLIC_URL`; an explicit `OAUTH_CALLBACK_URL` must match exactly. HTTP is accepted only for loopback fixtures.
Provider client credentials remain gateway-only placeholders until provisioned.

Authenticated `/api/oauth/start?upstream=N` calls private `/oauth/start` using the shared
key. A protected binding contains the initiating user's API identity, upstream, expiry
and a browser-verifier hash. The gateway stores it with expiring single-use state and
returns an allowlisted provider authorization URL. A ten-minute HttpOnly, host-only,
SameSite=Lax cookie binds the eventual callback to that browser. Cookies are Secure on
HTTPS. One active onboarding flow per browser is supported.

The anonymous callback forwards the code, state, issuer and browser verifier privately
to `/oauth/complete`. The gateway validates and consumes state, checks issuer where
required, redeems the code and returns tokens with the protected binding. Kavita checks
that binding and attaches tokens to the initiating account through its existing service.
Tokens remain in server-to-server JSON; they are absent from redirect URLs. Independent
token validity, rate-limit, account/list and expiry reads also use POST JSON bodies;
their failures log only a fixed route and credential-free error. Standard
OAuth authorization codes and state pass through the callback URL. Responses use
`Cache-Control: no-store` and `Referrer-Policy: no-referrer`. The legacy token-in-query
callback refuses independent mode. No public gateway route or generic proxy is added.

Authorization destinations are fixed to MangaBaka, AniList, MAL and Hardcover origins
and exact authorize paths. Their client configuration, consent scopes, token refresh,
provider behavior and real login flows require separate acceptance evidence. The
capability manifest advertises OAuth only for configured clients.

`python3 -m unittest discover -s stacks/kavita/independent -p 'test_*.py'` checks source
pinning and patch structure. Set `KAVITA_SOURCE_EXPORT` to a clean export of the pinned
commit to also apply and inspect the entire patch. The script rejects source hash drift
and a second application. Compile and isolated container acceptance are separate checks.

The final stage retains LinuxServer s6 initialization, PUID/PGID support, `/config` symlink
and defaults. No startup or deployment is part of these tests. Follow the stack's backup,
isolated restore and data-baseline procedure before replacing an existing container.

## Restart retention and storage pressure

Independent credential clearing pauses synchronization and retains pending events and rule history. It does not run the stock missing-token deletion paths. Reconnection can resume the pending queue. Official mode retains its original cleanup.

The native client atomically saves `config/independent-actions.json` inside the existing configuration volume, with mode `0600`. It signs the capability snapshot with the shared key and binds it to the gateway origin. After restart, a verified snapshot can retain new local events during a gateway outage. Delivery still requires current capabilities. Changed origin/key, corrupt or oversized state cannot enable creation. Valid capability removal replaces the saved snapshot. An unsuccessful save adds a visible limitation. `KAVITA_PROVIDER_ACTIONS_FILE` overrides the default path for isolated fixtures.

The provider database caps metadata at 1024 entries/32 MiB and reserves capacity before protected progress writes. It retains at most 100000 combined receipts/reservations, with at most 1024 recent reconcilable receipts for seven days. Legacy receipts, dated-progress receipts and ambiguous reservations remain protected. Full protected capacity pauses new protected writes before a provider mutation. Never delete protected evidence to free space without reconciling remote completion and native acknowledgment. Stable identity mappings are not recycled.

SQLite's main database has a 512 MiB page budget. WAL autocheckpointing and a 16 MiB retained-journal target manage routine journal growth. These are not filesystem quotas, and long-lived readers can retain WAL data. Include both existing volumes in backups and monitor filesystem free space.
