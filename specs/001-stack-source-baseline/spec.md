# Feature specification: Portable stack examples and generated catalog

**Created**: 2026-09-05
**Status**: Retrospective baseline
**Inspected revision**: `6ff2483b49f6fcfdf9094ed85659cd09d321c6c0`
**Input**: The owner requested a fleet-wide Spec Kit retrofit and implementation audit.

Compose examples, environment templates, preparation helpers, and stack metadata form a source catalog separate from live homelab deployments.

This specification records existing contracts after implementation. It does not
claim that the original work followed Spec Kit. New behavior requires a separate
change contract. Existing feature specifications remain authoritative within their
own scope.

## User scenarios and testing

### User story 1: Use the documented entry points (P1)

An operator selects a supported command or source workflow.

**Acceptance**: Inputs, output/status, and ownership remain consistent with the source contracts below.

### User story 2: Handle invalid input and partial failure (P2)

A configuration, dependency, subprocess, or persistence operation fails.

**Acceptance**: The named regression fixtures preserve failure reporting and recovery without claiming an unverified successful operation.

### User story 3: Maintain the contract (P3)

A maintainer changes the implementation or adds a supported capability.

**Acceptance**: The source registry, public documentation, tests, and delivery checks change together; operational actions remain separately scoped.

## Requirements

- **FR-001**: Compose MUST remain the container-behavior authority while each stack.yaml describes its catalog and operational metadata.
- **FR-002**: Preparation MUST preserve operator-authored configuration; the documented generated .env mirror may be refreshed from stack.env. It MUST report unfinished secret keys without their values and avoid starting containers.
- **FR-003**: Preparation MUST not create media bind directories over missing remote mounts or silently enable optional privileged/GPU overrides.
- **FR-004**: Validation MUST render portable example environments in temporary contexts without deploying stacks or reading live secrets.
- **FR-005**: Generated stack catalog, topology, and public application pages MUST remain reproducible from their declared sources.
- **FR-006**: Source delivery MUST preserve GitHub authority and permit only non-destructive fast-forward backup synchronization.

## Success criteria

- **SC-001**: Every requirement has a named source owner and acceptance check in `coverage.md`.
- **SC-002**: The listed native checks pass for the reviewed candidate, with unavailable environments and operational checks recorded separately.
- **SC-003**: Retrofitting preserves existing interfaces and completed specifications. Any confirmed implementation gap is corrected under an explicit requirement before it is marked complete.

## Edge cases and operational limits

This is a source-catalog baseline, not evidence that 217 live services are deployed, healthy, or recoverable. Runtime .env files, private keys, mounts, secrets, and live monitoring controls are not fixtures. Per-stack operational readiness and backup restoration remain separately authorized work.
