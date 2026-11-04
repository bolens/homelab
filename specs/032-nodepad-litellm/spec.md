# Feature Specification: Selectable LiteLLM in Nodepad

**Feature Branch**: `codex/032-nodepad-litellm`

**Created**: 2026-11-04

**Status**: Specified

**Input**: Add a selectable shared LiteLLM provider to Nodepad and rebuild it, keeping current defaults while making the configured Google and GitHub Copilot models available.

## User Scenarios & Testing

### User Story 1 - Choose shared AI models (Priority: P1)

A Nodepad user chooses LiteLLM in AI settings, selects one of the three configured models, and uses AI enrichment without entering a provider secret in the browser.

**Why this priority**: It supplies the requested Google and Copilot access through the existing app.

**Independent Test**: Choose LiteLLM, discover its three permitted models, and complete a synthetic enrichment request.

**Acceptance Scenarios**:

1. **Given** a configured shared connection, **When** the user selects LiteLLM, **Then** Google Flash Lite, Copilot Sonnet, and Copilot Gemini are selectable without a browser key.
2. **Given** a selected shared model, **When** enrichment runs, **Then** that exact model is used and the result is returned normally.

### User Story 2 - Preserve existing work and choices (Priority: P1)

An existing user opens the updated app with the same notes, provider, model, and saved keys.

**Why this priority**: The user explicitly requested unchanged defaults.

**Independent Test**: Load representative saved settings for every existing provider and compare their meaning before and after the update. Preserve the deployed first-visit defaults when rebuilding.

**Acceptance Scenarios**:

1. **Given** saved Ollama or cloud settings, **When** the updated app opens, **Then** it keeps those selections and credentials.
2. **Given** a new browser, **When** the updated app opens, **Then** the prior first-visit defaults remain in effect.
3. **Given** an unconfigured shared connection, **When** LiteLLM is selected, **Then** the app reports unavailable configuration without changing another provider.

### User Story 3 - Keep shared access private (Priority: P1)

The operator enables a restricted server connection without publishing credentials or allowing unrelated gateway actions.

**Why this priority**: The shared connection consumes the operator's AI accounts.

**Independent Test**: Verify denied cross-site, unsupported, oversized, redirected, and disallowed-model requests, and inspect browser assets and responses for a test secret.

**Acceptance Scenarios**:

1. **Given** the enabled connection, **When** users inspect model discovery or browser assets, **Then** no upstream key is present.
2. **Given** an unsupported gateway action or model, **When** it is requested through Nodepad, **Then** it is rejected before reaching the gateway.
3. **Given** the public deployment, **When** shared access is enabled, **Then** the complete site including its AI endpoints retains owner-only access protection.

### Edge Cases

- Missing server settings, unavailable providers, cancellation, and slow responses produce bounded failures without revealing upstream error bodies.
- A stale custom URL or browser key cannot redirect the shared connection or replace its server credential.
- Streaming and ordinary replies remain usable.
- Existing Ollama and browser-managed cloud connections remain independent.

## Requirements

### Functional Requirements

- **FR-001**: Nodepad MUST offer LiteLLM as an additional provider, with the three configured model choices.
- **FR-002**: The shared connection MUST require no browser-stored provider key.
- **FR-003**: Existing saved settings, note data, and first-visit defaults MUST remain unchanged.
- **FR-004**: Shared access MUST expose only model discovery and chat generation for explicitly permitted models.
- **FR-005**: Credentials and raw upstream failures MUST remain private; request size, response generation, and waiting time MUST be bounded.
- **FR-006**: The operator MUST verify complete owner-only site protection before enabling the shared credential on the public deployment.
- **FR-007**: The change MUST remain reproducible from the pinned upstream source and maintained patch sequence, with portable examples and no live secrets.
- **FR-008**: Deployment MUST preserve the prior image and configuration until functional and preservation checks pass.

### Key Entities

- **Provider choice**: Existing per-browser provider selection, expanded with one shared option.
- **Shared model**: An exact configured alias available through the operator's gateway.
- **Server connection**: Private gateway location, restricted credential, model allowlist, and allowed browser origins.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All three configured models can be discovered and selected; at least one synthetic request succeeds through the deployed Nodepad connection.
- **SC-002**: Every existing provider passes saved-settings preservation checks, and the recorded first-visit defaults match the rebuilt app.
- **SC-003**: All defined rejection cases pass, and the test credential appears zero times in browser assets and client responses.
- **SC-004**: The full maintained patch sequence applies to the pinned upstream revision, with focused checks and a production build passing.

## Assumptions

- LiteLLM already serves `gemini-flash-lite`, `copilot-sonnet`, and `copilot-gemini` on the shared Docker network.
- The operator will use a model-only key restricted to those aliases.
- Existing Ollama, speech, embedding, search, and automated document-processing defaults are outside this feature and remain unchanged.
- No account linking, billing change, model download, or public gateway exposure is required.
