# Implementation Plan: Nodepad LiteLLM

**Branch**: `codex/032-nodepad-litellm` | **Date**: 2026-11-04 | **Spec**: [spec.md](spec.md)

## Summary

Add an optional LiteLLM provider with fixed same-origin model discovery and chat endpoints. Keep its scoped service key on the server. Preserve all existing browser settings and first-visit defaults, and deploy only the rebuilt Nodepad service after checks.

## Technical Context

- Language/runtime: TypeScript and JavaScript, existing Next.js 16 / React 19 / Node 26 stack.
- Dependencies: Existing application dependencies and Node built-in request, stream, and test APIs. No new runtime package.
- Storage: Existing browser settings and notes remain unchanged. Server connection values are private environment settings.
- Testing: Node built-in tests with mocked upstreams, focused TypeScript checks, pinned patch application, production build, browser asset secret canary, native discovery and synthetic generation.
- Platform/scope: Independently deployable Docker stack, existing `ai-backend` and Caddy ingress. No additional host ports, volumes, privileges, or networks.
- Constraints: Fixed gateway origin, exact permitted routes/models, strict browser-origin check, bounded body/token/time budgets, no redirects, no raw upstream errors or sensitive headers.

## Constitution Check

- Portable examples: Pass. Optional fields use placeholders or empty values; no user hostnames/keys enter source.
- Complete contract: Update patch, README, environment example, Compose comments, preparation messaging, metadata, and ingress protection guidance together. Regenerate affected generated documentation from source.
- Operations: User explicitly approved connector, rebuild, and scoped rollout. Preserve old image/environment for rollback and verify defaults and native behavior before cleanup.
- Security choices: Pass with existing full-site owner access verified before credential enablement; no public gateway route or new port.
- Validation: Focused route/client security checks, build, and `make validate`. Any unavailable optional validator is reported separately.

## Project Structure

- `stacks/nodepad/patches/0008-homelab-litellm-provider.patch`: client integration, plain server module, route adapters, and source tests.
- `stacks/nodepad/verify-litellm.sh`: focused native checks after the normal pinned clone/patch preparation.
- Existing stack contract files: operator setup and protected optional server connection.
- `specs/032-nodepad-litellm/`: specification, research, data model, contract, validation guide, tasks, and acceptance evidence.

## Design

Client preset is `litellm`, with three exact static model choices and normal dynamic discovery. Its URL always remains `/api/litellm/v1`; browser credentials and stale custom URLs do not alter it. Existing settings storage and defaults stay unchanged.

Only GET `models` and POST `chat/completions` pass through the server. The server validates configuration, origin, permitted model and fields, request size, and generation limits. It sets its own authorization, disables redirects, filters discovery, sanitizes response headers/errors, and connects cancellation to bounded upstream requests. Successful JSON and SSE remain streamable.

Deployment uses a newly tagged image from the checked pinned source and private scoped connection values, preserves current first-visit build defaults, and changes only the Nodepad service. Existing apps are operated independently under their own backup and preservation checks.

## Design Review

No additional constitutional exceptions. Research resolved the custom URL, browser key gate, build type-check, patch ordering, first-visit default, and existing proxy hazards.
