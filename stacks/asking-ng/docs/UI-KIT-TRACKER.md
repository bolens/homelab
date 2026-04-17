# UI Kit Implementation Tracker

Tracks post-migration UI kit work for `stacks/asking-ng/client`.

## In Progress (Quick Wins)

- [x] Add a reusable alert primitive for consistent error/warning/info rendering.
- [x] Replace legacy `error-message` class usage in React pages with UI kit alert styles/component.
- [x] Add migration guard script to catch legacy Bootstrap-style classnames in `className` literals.
- [x] Improve `Field` accessibility defaults (`id`, `aria-describedby`, `aria-invalid`) to reduce repeated wiring.

## Next Up

- [x] Extract repeated page patterns into UI primitives:
  - [x] `PageHeader`
  - [x] `SectionCard`
  - [x] `ActionRow`
  - [x] `KpiCard` (admin dashboards/status)
- [x] Start converting large pages (`MyPolls`, `Poll`) to compose primitives first, custom classes second.
  - [x] Initial `MyPolls` migration slice (header/actions + section cards + danger actions)
  - [x] Expand migration in `MyPolls` for generic action row wrappers (`ActionRow`)
  - [x] Start equivalent migration slice in `Poll` (`ActionRow` on top toolbar)
  - [x] Admin KPI surfaces switched to `KpiCard` (`AdminDashboard`, `AdminStatus`)
- [x] Add visual regression coverage for light/dark and key mobile breakpoints on migrated pages (`/`, `/about`, `/developer`, `/privacy`, `/terms`).

## Bootstrap Drawdown Plan

- [x] Stop introducing Bootstrap utility and component classnames in new UI.
- [x] Remove remaining Bootstrap utility dependencies from page markup.
- [x] Remove `@import "bootstrap/dist/css/bootstrap.min.css"` once usage reaches zero.
- [x] Remove temporary `--bs-*` bridge variables that are no longer needed after import removal.

## Token and Theming Cleanup

- [x] Formalize token layering:
  - [x] Global tokens (spacing, radii, typography, base colors)
  - [x] Semantic tokens (surface, accent, success, warning, danger)
  - [x] Component tokens (button/input/dialog internals)
- [x] Document token naming and usage rules in a short style guide.

## Component API Consistency

- [x] Evaluate polymorphic button/link strategy (single API for button and anchor behavior).
- [x] Consider `Card` sub-structure (`Card.Header`, `Card.Body`, `Card.Footer`) for repeated page blocks.
- [x] Consider dialog action/footer primitives for consistent modal actions.
- [x] Add `SectionPanel` primitive for admin section wrappers.
- [x] Migrate `AdminStatus` section shells to `SectionPanel` (title + hint + body wrapper).
- [x] Migrate `AdminDashboard` section shells to `SectionPanel` (simulation/setup/quick panels).
- [x] Standardize admin top headers with `PageHeader` (`AdminDashboard`, `AdminStatus`).
- [x] Add `Notice` primitive and migrate core admin status/error banners (`AdminDashboard`, `AdminStatus`).
- [x] Extend `Notice` migration across remaining admin pages (`AdminUsers`, `AdminPolls`, `AdminExport`, `AdminAuditLogs`, `AdminImpersonate`).
- [x] Standardize admin access-denied surfaces with `Notice` (all admin pages using `asking-admin-polls-page-error`).
- [x] Standardize remaining admin top headers with `PageHeader` (`AdminUsers`, `AdminPolls`, `AdminExport`, `AdminImpersonate`, `AdminAuditLogs`).
- [x] Start `SectionPanel` migration in high-repeat admin blocks (`AdminUsers` tools section, `AdminPolls` bulk actions section).
- [x] Continue `SectionPanel` migration for admin create/search sections (`AdminUsers`, `AdminPolls`).
- [x] Continue `SectionPanel` migration for admin bulk/export wrappers (`AdminUsers` bulk actions, `AdminExport` dataset section).
- [x] Continue `SectionPanel` migration for admin table/pagination wrappers (`AdminUsers` data table, `AdminPolls` data table + pagination).
- [x] Continue `SectionPanel` migration for impersonation shells (`AdminImpersonate` request + token sections).
- [x] Continue `SectionPanel` migration for admin audit shells (`AdminAuditLogs` filters + data table wrappers).
- [x] Start non-admin page-shell standardization with `PageHeader` (`Settings` page header).
- [x] Continue non-admin shell standardization with `SectionPanel` (`Developer` OpenAPI/Streaming/LLM sections).
- [x] Continue non-admin shell standardization with `SectionPanel` (`Developer` billing section).
- [x] Continue non-admin primitive adoption by replacing remaining `Home` row wrappers with `ActionRow`.
- [x] Continue non-admin feedback standardization by migrating `Home`/`Developer` danger alerts to `Notice`.
- [x] Continue non-admin feedback standardization by migrating high-severity billing warning states to `Notice` (`Home`, `Developer`).
- [x] Continue non-admin feedback standardization by migrating status/info toasts to `Notice` (`Home` link hint, `Developer` floating toast).
- [x] Continue non-admin page-shell standardization by migrating `Developer` top heading block to `PageHeader`.
- [x] Continue non-admin page-shell standardization by migrating `Home` hero header (non-created state) to `PageHeader`.
- [x] Continue non-admin page-shell standardization by migrating `Home` created-state success header to `PageHeader`.
- [x] Continue Bootstrap drawdown by replacing direct `var(--bs-*)` UI usages in `index.css` with app semantic tokens.
- [x] Continue Bootstrap drawdown by removing `--bs-body-font-family` fallbacks from reading-comfort font stacks.

## Follow-up Notes

- Admin shells that use `asking-admin-cq-root` now include dashboard, status, export, and impersonate (with users, polls, audit logs); narrow inline-size stacks simulation fields, impersonate row, dashboard columns, and KPI/quick grids without waiting on viewport breakpoints alone.
- Visual baselines intentionally exclude `/status` for now: React Query timestamp churn + occasional Vite/HMR error-boundary renders made snapshots unstable in `e2e:visual` even with `--workers=1`; keep `/status` in a dedicated deterministic spec if reintroduced.
- Keep this file updated whenever a migration PR lands.
- Prefer checking off a small vertical slice (component + 1-2 page migrations + tests) per PR.
- See `docs/UI-COMPONENT-API-REVIEW.md` for current API decisions and deferrals.

## Tooling

- [x] List `tsx` as a client devDependency (i18n audit scripts) and configure knip `ignoreIssues` for intentional library exports so `pnpm run knip` passes.
- [x] CI: `visual` job in `.github/workflows/client.yml` runs `pnpm --filter client run e2e:visual` on `ubuntu-latest` (snapshots are Linux-generated; use `e2e:visual:update` on Linux when updating baselines). Failed runs upload `client/test-results/` as `asking-ng-client-visual-playwright`.
- [x] Visual Playwright scripts use `--workers=1` so the shared Vite dev server is not hammered by parallel browsers (avoids flaky HMR / half-mounted app trees).
