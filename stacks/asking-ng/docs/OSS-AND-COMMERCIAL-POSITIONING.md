# OSS and commercial positioning

One-pager for **contributors**, **operators**, and **public comms** when asking-ng ships hosted tiers, self-host Pro, and optional regulated modules. Canonical numbers and limits stay in [MONETIZATION-AND-PACKAGING.md](MONETIZATION-AND-PACKAGING.md).

---

## What stays free and open (adoption promise)

- **Core poll lifecycle:** create, read, vote, update, delete, clone (within whatever limits a deployment configures).
- **Basic moderation:** approve/reject quarantine, manual batch paths that exist today.
- **Basic exports** and **baseline realtime** (WebSocket refetch model) as implemented in the OSS tree.

Commercial packaging is meant to add **scale, automation, retention, analytics, ops templates, and regulated optional modules**—not to remove vote integrity or basic safety from the OSS baseline abruptly. When behavior moves tiers, use a **grandfathering window** and clear changelog language (see [MONETIZATION-AND-PACKAGING.md](MONETIZATION-AND-PACKAGING.md)).

---

## How hosted revenue relates to OSS

- **Hosted** (Polar-backed SMB tiers + enterprise) funds reliability, support, and continued development of the shared codebase.
- **Self-host Pro** funds advanced modules **on premises** for operators who cannot or will not use cloud.
- **Enterprise** covers custom limits, compliance, and Tracks A/D where counsel and licensing allow.

Messaging that tends to work: *“The core product stays forkable; paid tiers fund sustained engineering and operations.”*

---

## Open-core and contribution boundary

| Area | OSS repo expectation |
|---|---|
| Core API + client flows used by homelab | Stay in tree; review as today. |
| Plan flags / limit checks | Implement in tree with **`free` defaults** that preserve current OSS behavior until operators opt into billing/license env. |
| Settlement ledgers, risk engines, regulated-market matching | If policy requires, **commercial extension** or private package; public tree documents **interfaces and stubs** only. |
| Contributor PRs touching entitlements | Must not break default OSS deploy (no secret license required to boot). |

If you add **compile-time** or **runtime** gates for Pro-only code paths, document how contributors run and test them locally (feature flags, test keys) in the PR template or [CI-REPO-WORKFLOW.md](CI-REPO-WORKFLOW.md).

---

## Trademark and naming

- Use a single product name for OSS + hosted to reduce confusion; clearly label **“Official hosted”** (your domain) vs **self-hosted** community mirrors.
- Typosquat domains and unofficial “support” are an ops cost—publish the **canonical** URL and support channel in README and footer.

---

## When limits or admin features change

1. **Changelog:** what changed, who is affected (OSS self-host vs cloud), effective date.
2. **Grandfathering:** duration and countdown in-app ([MONETIZATION-AND-PACKAGING.md](MONETIZATION-AND-PACKAGING.md)).
3. **Migration:** export paths and, for cloud-bound users, link to assisted migration if applicable ([MONETIZATION-AND-PACKAGING.md](MONETIZATION-AND-PACKAGING.md) — self-host ↔ cloud).

### Changelog comms checklist (tone)

- State **what stays free** first; avoid sounding like the whole project “went commercial.”
- Link **why** (hosted revenue funds shared core) in one sentence—optional FAQ entry.
- Separate bullets for **self-host operators** vs **hosted workspaces** when behavior diverges.
- Link to **grandfathering end date** and **export** / downgrade simulator when a capability moves tiers.

---

## Related docs

- [MONETIZATION-AND-PACKAGING.md](MONETIZATION-AND-PACKAGING.md) — tiers, limits, add-ons, migration notes
- [POLAR-BILLING.md](POLAR-BILLING.md) — hosted billing and webhook ownership
- [OPERATIONS.md](OPERATIONS.md) — degraded modes, kill switches, `INCIDENT_MODE`
