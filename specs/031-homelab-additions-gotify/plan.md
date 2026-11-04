# Implementation Plan: Homelab additions and Gotify migration

**Date**: 2026-11-04 | **Spec**: [spec.md](spec.md)

## Summary

Add complete portable examples, then deploy applications and migrate current notification consumers with verified rollback copies.

## Technical Context

Docker Compose, Caddy, SQLite, PostGIS 17, Redis 8, and Python 3.13 standard library for an authenticated Alertmanager adapter. Existing ntfy publishes raw Alertmanager JSON; Gotify needs an explicit message conversion. Use separate Gotify applications for the existing alert categories, Kuma, Diun, Watchtower, and workflow approvals.

## Constitution Check

- Portable sources use placeholder domains and secrets, with immutable image digests.
- All stack contract surfaces change together.
- Preparation remains idempotent and never deploys.
- Web apps expose no host ports. Music Assistant uses documented upstream host networking for player discovery and streaming. Komodo Periphery deliberately receives the Docker socket for host management, with automatic updates and terminals disabled. Other additions have no Docker socket or elevated privileges.
- Preserve unrelated edits. Regenerate inventories and published catalog after source changes.

## Source Ownership

Own new stacks/gotify, changedetection, music-assistant, lubelogger, dawarich, homebox, and wallos. Own notification edits in alertmanager, diun, watchtower, n8n, uptime-kuma, prometheus, caddy examples, notification SQL examples, and cross-stack documentation. Preserve existing edits to prometheus documentation and generated sources. Historical specs and upstream fixture copies remain unchanged.

## Migration Order and Rollback

1. Inventory producers and capture image/configuration/data baselines privately.
2. Quiesce affected database writers for complete persistent-state backups, restore into isolated copies, verify file hashes and SQLite integrity.
3. Bring up Gotify and create separate application tokens. Test authenticated publishing and WebSocket access before moving producers.
4. Move Alertmanager through a bearer-authenticated internal adapter, Diun through its native notifier, and Kuma by updating the existing notification row without replacing monitor links or history.
5. Verify routed firing/resolved and producer test messages, SMTP fallback preservation, unrelated state, and ingress authentication. Preserve inactive services and workflows.
6. Stop ntfy only after consumer delivery succeeds. Keep its original volumes for historical access and rollback.
7. If cutover fails, restore the prior consumer configuration and compatible images/state and restart ntfy. Never remove historical volumes or perform destructive schema conversions.
8. Remove operation-created backup and isolated restore copies only after successful verification. Retain non-secret acceptance evidence and necessary live credentials privately.

## Validation

Use meaningful adapter tests against a local fake Gotify receiver, isolated preparation fixtures, exact example Compose rendering, metadata/preparation audits, generated inventory checks, and make validate. Live acceptance requires verified stored messages, application behavior and database preservation, not container health alone.

## Accepted scope additions

Termix, an Authentik Gotify plugin, Komodo inventory, a restricted Backrest browser, Promtail-to-Alloy migration, and a dedicated openai-oauth upstream behind LiteLLM are authorized. LiteLLM also receives a verified regular administrator before environment login is disabled. TubeArchivist and Docker ZIM library management remain research. Backrest repository attachment requires verified readable storage and snapshot-preservation proof. A host-readable repository with a stale container bind must be diagnosed before repair. No replacement backup schedule may bypass storage checks.

## TubeArchivist and Zimi deployment amendment

Own the two new stack directories, a preparation fixture extension, topology membership and generated catalog/site. Establish upstream tagged configuration, auth, persistence, image/architecture pins and resource prerequisites first. Use fresh named volumes rather than guessing media mount paths. Create private credentials and local ingress matching existing stacks. Verify anonymous denial, native authenticated reads, empty job queues and storage persistence. Existing Caddy reload changes routing only, with a verified private configuration preimage. No additional public hostname is required.
