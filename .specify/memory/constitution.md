# Docker Stack Collection Constitution

## Core Principles

### I. Portable Public Examples
Each stack MUST be independently deployable and MUST use explicit, documented operator choices with placeholders for private host values. Runtime secrets and live configuration never enter committed examples.

### II. Complete Stack Contracts
Compose, environment examples, metadata, preparation, ingress examples, and README instructions form one contract and MUST change together. Local stack documentation is authoritative.

### III. Safe Preparation and Operations
Preparation MUST be idempotent, preserve existing config, avoid value disclosure, and never start containers. Validation is read-only; deployment and lifecycle changes require explicit operational authorization.

### IV. Security-Relevant Runtime Choices
Ports, privileges, host networking, Docker socket, devices, GPU, public ingress, persistence, and image pinning MUST be deliberate, documented, and represented accurately in metadata.

### V. Generated Truth and Validation
Generated catalog/topology content MUST come from its sources. Affected metadata, preparation, documentation, and Compose validators MUST pass; CI-equivalent claims require the strict gate.

## Governance

`documents/` defines cross-stack standards. Exceptions require explicit rationale in the stack documentation and regression validation. Amendments use semantic versioning.

**Version**: 1.0.0 | **Ratified**: 2026-08-15 | **Last Amended**: 2026-08-15
