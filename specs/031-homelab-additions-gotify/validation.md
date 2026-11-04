# Acceptance evidence

## Repository

The source contracts include eleven added stacks, affected notification consumers, OAuth client connections and generated inventories. Focused adapter/preparation tests pass. The custom-image suite passes in a public-source fixture. The working checkout's custom-image inventory test also sees unrelated untracked/vendor Dockerfiles, which is why its unrestricted run is not reported as passing.

`make validate` passes with 227 Compose examples and 230 metadata records. PostHog's externally generated bundle is skipped. The preparation audit reports the existing Stoat legacy-backend example warning. This is the repository gate, not a claim that the broader CI-local or hosted checks ran.

## Notifications and applications

All five Alertmanager categories delivered firing and resolved notifications. Kuma and Diun native tests delivered, with Kuma record identities/bindings and SMTP fallback preserved and Diun's 190 tracked image identities retained. Public Gotify verifies TLS, token refusal and WebSocket routing. The Authentik plugin passed isolated binary compatibility, failed-login parsing and password-omission checks. Native Authentik transport delivery succeeds without changing existing identity objects or notification rules. Changedetection and Wallos native notification tests deliver. Watchtower remains stopped and n8n workflows remain inactive. ntfy is stopped with original state retained.

All nine local application routes pass TLS and HTTP checks. Application accounts have verified native logins or native password checks. Termix registration is closed. Music Assistant uses the existing read-only music tree through its filesystem provider. SSH target credentials, actual music player selection/playback and location client onboarding remain explicit operator choices.

## Modernization and recovery

Komodo native authentication and inventory work, with no imported stacks or procedures and 233 existing container identities/start times preserved during onboarding. Backrest restores its original state in an isolated matching-image fixture, indexes all 18 existing snapshots through a read-only repository and completes a bounded restore with a matching hash. No backup plans or command hooks are added. Restic retains its schedule and image after a verified cache backup and a scoped stop/start repairs its stale mount. All snapshot IDs remain unchanged.

Alloy imports all eight final Promtail file positions, persists a journal cursor, delivers unique file and journal markers once each, and continues the existing Docker canary. The original image and Docker state are preserved. Promtail is stopped and its required scrape/alerts are retired after delivery acceptance.

## OAuth and dashboard login

A separate user-completed OAuth login is stored in its dedicated volume. The pinned proxy has no published ports and shares a network only with LiteLLM. Completion and streaming work through the authenticated gateway. Existing nine model routes remain. Open WebUI and LibreChat use separate internal-user service keys restricted to the personal model route. Both clients complete real requests, and neither service key can access LiteLLM administration. Full Open WebUI file/SQLite restoration and LibreChat file/MongoDB restoration are verified, preserving existing users, conversations and providers. Only two proven permission-table startup `updatedAt` fields change in LibreChat.

A regular LiteLLM administrator works before and after disabling environment-credential login. Environment-password and master-key UI sign-ins fail, while API authentication remains valid. Runtime credentials and detailed receipts are stored privately outside Git.

## TubeArchivist and Zimi follow-up

Both authorized additions have complete stack contracts and local Caddy ingress. TubeArchivist v0.6.0 uses dedicated Elasticsearch/Redis storage and an internal backend. Zimi v1.15.2 runs as UID/GID 1000 with an isolated, repeatable empty-volume initialization helper. Neither stack publishes host ports. HTTPS certificate verification, native administrator login and anonymous API refusal pass through Caddy after restart. TubeArchivist has no videos, subscriptions or queued downloads. Zimi has two image-bundled ZIMs, no queued downloads, and automatic updates and BitTorrent disabled. No existing libraries were migrated.

All six new persistent volumes were quiesced, copied and restored in isolation with matching file hashes. Three restored SQLite databases passed integrity checks. Matching-image recovered applications passed native authentication and library/management reads on an internal network with no published ports. Caddy's prior configuration and persistent state also passed isolated-copy verification before routing changes. Temporary recovery containers, network and operation-created backup/restore copies were removed after acceptance; receipts and private credentials remain outside Git.

The final repository gate passes with 232 metadata records and 229 rendered Compose stacks. PostHog's generated bundle remains skipped; the existing Stoat optional-example warning remains. The focused added-stack preparation test and `git diff --check` pass. This does not claim hosted CI or the broader CI-local suite ran.
