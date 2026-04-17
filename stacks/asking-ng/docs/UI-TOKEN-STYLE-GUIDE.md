# UI Token Style Guide

Scope: `stacks/asking-ng/client/src/ui/ui-kit.css`

## Token Layers

- Global tokens: foundational design values (spacing, radii, shadows, typography scales when added).
- Semantic tokens: intent/meaning aliases (`surface`, `text`, `border`, `accent`, `success`, `warning`, `danger`).
- Component tokens: primitive internals (`button`, `input`, `dialog`) that map to semantic/global tokens.

## Naming Rules

- Prefix all UI-kit tokens with `--ui-`.
- Use layer-specific names:
  - Global: `--ui-radius-*`, `--ui-space-*`, `--ui-shadow-*`
  - Semantic: `--ui-surface-*`, `--ui-text-*`, `--ui-border-*`, `--ui-accent-*`, `--ui-success-*`, `--ui-warning-*`, `--ui-danger-*`
  - Component: `--ui-button-*`, `--ui-input-*`, `--ui-dialog-*`
- Prefer semantic tokens inside component styles; avoid wiring components directly to raw palette vars unless unavoidable.

## Usage Rules

- New UI primitives should consume component tokens first, then semantic/global tokens.
- App/page-level custom CSS should consume semantic tokens, not component internals.
- When introducing a new visual decision:
  - If reused broadly across components, add a semantic token.
  - If specific to one primitive, add a component token.
  - If it is a raw scale value (space/radius/shadow), add a global token.

## Migration Guidance

- During migration, alias old palette variables through semantic tokens instead of replacing everything in one pass.
- Keep behavioral changes out of token-only PRs; token cleanup should be visual no-op unless explicitly intended.
