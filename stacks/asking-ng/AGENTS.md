# AGENTS.md

## Definition of done

Before treating a change as complete:

- Run **`pnpm run verify`** from the repository root (Biome `check:ci` plus Turborepo `verify` for `@asking-ng/contracts`, `api`, and `client`).
- Use **`pnpm run test`** (Vitest via Turbo), not ad-hoc `vitest` without the workspace scripts, unless you are debugging a single package with an explicit filter.

## Project snapshot

asking-ng is a small homelab stack: React (Vite) client, Fastify API, PostgreSQL. Shared Zod shapes and types live in **`@asking-ng/contracts`** (`packages/contracts`). Do not add barrel `index.ts` files there; use **`package.json` `exports`** subpaths only.

## Priorities

1. Correctness and predictable behavior (auth, polls, admin APIs, URL search validation).
2. Keep client and API in sync via **contracts** for any shared wire shapes.
3. Performance is important but secondary to correctness for this codebase size.

## Monorepo commands (root)

| Goal        | Command              |
| ----------- | -------------------- |
| Full gate   | `pnpm run verify`    |
| Format/lint | `pnpm run check`     |
| CI format   | `pnpm run check:ci`  |
| Typecheck   | `pnpm run typecheck` |
| Tests       | `pnpm run test`      |
| Build all   | `pnpm run build`     |

Turborepo respects **`turbo.json`** `globalEnv` for cache keys; if a build or test outcome depends on an env var, add it there.

## Package roles

- **`client`**: Vite + React UI, TanStack Router/Query, admin and public poll UX.
- **`api`**: Fastify, Sequelize, admin routes, OpenAPI, poll CRUD.
- **`@asking-ng/contracts`**: Zod schemas and inferred types shared by client and API. Build with `tsc` to `dist/`; api uses **Node16** module resolution to consume `exports`.

## Maintainability

Prefer extending **`@asking-ng/contracts`** (or a small shared helper) over duplicating validation or DTO shapes in both `client` and `api`. If you add env vars that affect builds or tests, update **`turbo.json`** `globalEnv` and, when relevant, **`pnpm-workspace.yaml`** `catalog` for shared dependency versions.
