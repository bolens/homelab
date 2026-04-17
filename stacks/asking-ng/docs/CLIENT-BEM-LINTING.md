# Client BEM Linting

Scope: `stacks/asking-ng/client`

## Purpose

Keep class naming predictable across CSS and TSX so selectors, tests, and accessibility hooks stay stable.

## Enforcement Layers

- CSS selector linting: `pnpm run lint:bem` (Stylelint).
- TSX class-token linting: `pnpm run lint:classnames` (`client/scripts/check-classname-bem.mjs`).
- Combined client lint path: `pnpm run lint`.

## Allowed Class Prefixes

Class tokens must match one of these block prefixes:

- `ui-*` (UI primitives/shared design system)
- `asking-*` (app/page/domain classes)
- `leaflet-*` (third-party Leaflet override surfaces)

## Naming Pattern

Supported token shapes:

- Block: `asking-poll-page`
- Element: `asking-poll-page__title`
- Modifier: `asking-poll-page--live-connected`
- Element modifier: `asking-poll-page__status--error`

## TSX Guard Behavior

The TSX checker validates:

- literal `className='...'`, `className="..."`, ``className={`...`}`` (without interpolation),
- string literals passed to `cx(...)`.

It intentionally skips:

- template strings with interpolation (for example `--${tone}`),
- non-class enum/variant strings in `cx(...)` argument lists.

For dynamic modifiers, prefer typed maps over raw interpolation.

## Preferred Dynamic Modifier Pattern

```ts
const STATUS_TONE_CLASS: Record<'ok' | 'error' | 'pending', string> = {
  ok: 'asking-status-page__badge--ok',
  error: 'asking-status-page__badge--error',
  pending: 'asking-status-page__badge--pending',
};
```

Then compose with:

```ts
className={`asking-status-page__badge ${STATUS_TONE_CLASS[tone]}`}
```

## Intentional Exceptions

- Third-party library classes are allowed only for documented integration surfaces (currently `leaflet-*`).
- If a new external namespace is required, update both:
  - Stylelint `selector-class-pattern` in `client/stylelint.config.mjs`,
  - TSX checker regex in `client/scripts/check-classname-bem.mjs`.

## Quick Commands

- Check TSX class tokens only: `pnpm run lint:classnames`
- Check CSS selectors only: `pnpm run lint:bem`
- Run full client lint path: `pnpm run lint`
