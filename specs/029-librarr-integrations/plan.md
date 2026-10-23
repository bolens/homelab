# Implementation Plan: Librarr integrations

**Branch**: `codex/librarr-integrations` | **Date**: 2026-10-23 | **Spec**: [spec.md](spec.md)

## Summary

Add a standalone Librarr v1.4.1 stack with optional reader connectivity. Keep
direct downloads within Librarr, and provide honest manual imports for Bookshelf
and Calibre-Web rather than an incompatible Torznab download bridge.

## Technical Context

Docker Compose on Linux amd64; upstream Go application; local persistent SQLite
and settings bind; shared media bind; Python unittest and repository validators.
No runtime Docker socket, host network, devices, extra privileges or public host
ports. Use a local reviewed sources registry rather than changing remote defaults.

## Constitution Check

- Portable examples: placeholders and independently selectable integrations.
- Complete contracts: Compose, environment, metadata, preparation, ingress and README.
- Safe preparation: existing media required; application config alone may be created.
- Security: pin image digest, require authentication, optional reader network, read-only reader mounts.
- Generated truth: update topology source and regenerate catalog, inventory and Pages.

## Project Structure

- `stacks/librarr/`: owning service contract, sources example and reader-network override.
- `stacks/{kavita,komga}/docker-compose.librarr.yml`: dedicated read-only reader roots.
- Existing integration READMEs: Prowlarr, qBittorrent, Bookshelf, Calibre-Web, Audiobookshelf.
- `scripts/tests/test_librarr_contract.py`: isolated preparation and Compose acceptance.
- `specs/029-librarr-integrations/`: research, contracts, tasks and validation.

## Ownership and verification

Single writer in the attached `librarr-integrations` worktree, based on
`origin/main` (`e6f9938` at inspection). The original checkout contains unrelated
work and remains untouched. Focused tests precede `make validate`, followed by the
broader delivery gate when available. Live credentials and media remain unread.
