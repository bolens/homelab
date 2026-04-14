# asking-ng client

React UI built with **Vite**. Install dependencies with **pnpm** (version pinned in `package.json` → `packageManager`; Docker uses Corepack).

## Scripts

| Command        | Description                                      |
| -------------- | ------------------------------------------------ |
| `pnpm start`   | Dev server on `0.0.0.0:3000` (see `vite.config.js`) |
| `pnpm build`   | Production bundle → `build/`                    |
| `pnpm preview` | Serve the production build locally               |
| `pnpm test`    | Placeholder (no test runner wired yet)           |

## Configuration

- **`VITE_API_BASE`** — Prefix or origin for API calls (e.g. `/api` when Caddy strips `/api` to the backend, or `http://127.0.0.1:3001` for a direct API during local dev).
- **`VITE_DEV_API_TARGET`** — Used by Vite’s dev proxy (`vite.config.js`) for `/api` → API container/host.

## Running with the API locally

From `client/`, `./start-all.sh` starts the API (`../api`) then the Vite dev server.

## Docker

`Dockerfile.dev` and `Dockerfile.prod` run `corepack enable && pnpm install --frozen-lockfile`. After changing dependencies, run `pnpm install` locally and commit `pnpm-lock.yaml`.
