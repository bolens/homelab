# asking-ng client

React UI built with **Vite** and [Vite+](https://viteplus.dev/) (`vp`) as the CLI.

## Scripts

| Command           | Description                                      |
| ----------------- | ------------------------------------------------ |
| `vp dev`          | Dev server on `0.0.0.0:3000` (see `vite.config.ts`) |
| `pnpm run dev`    | Same as `vp dev` (npm script wrapper)            |
| `vp build`        | Production bundle → `build/`                     |
| `pnpm run build`  | Same as `vp build`                               |
| `vp preview`      | Serve the production build locally               |
| `pnpm run test`   | Vitest unit tests (`src/**/*.test.ts`)           |

From the **repo root**: `pnpm --filter client exec vp <command>` (e.g. `vp dev`, `vp build`).

## Configuration

- **`VITE_API_BASE`** — Prefix or origin for API calls (e.g. `/api` when Caddy strips `/api` to the backend, or `http://127.0.0.1:3001` for a direct API during local dev).
- **`VITE_DEV_API_TARGET`** — Used by Vite’s dev proxy (`vite.config.ts`) for `/api` → API container/host.
- **`VITE_STREAMING_OBS_DOC_URL`** — Optional absolute URL for the in-app “OBS / browser source” doc link (My Polls, Poll owner kit, Home post-create, Developer). Defaults to the upstream GitHub doc when unset (baked at image build).
- **`VITE_UMAMI_SCRIPT_URL`** + **`VITE_UMAMI_WEBSITE_ID`** — Optional Umami integration; when both are set, client injects the analytics script at runtime.
- **`VITE_UMAMI_DOMAINS`** — Optional comma-separated domain allowlist for Umami `data-domains`.
- **`VITE_PLAUSIBLE_SCRIPT_URL`** + **`VITE_PLAUSIBLE_DOMAIN`** — Optional Plausible integration; script is injected only when both are set.
- **`VITE_MATOMO_BASE_URL`** + **`VITE_MATOMO_SITE_ID`** — Optional Matomo tracker integration.

The in-app **API / LLM** page (`/developer`) links to Swagger (`/api-docs`), probes the LLM gateway when enabled, and can send non-streaming chat requests (optional session-stored gateway token when the API uses `LLM_GATEWAY_TOKEN`).

## UI kit (incremental)

The client now includes a lightweight in-repo UI kit in `src/ui/`:

- `Button`, `Card`, `Container`, `Field`, `Input`, `Select`, `Textarea`, `Stack` primitives
- `Card` supports `padding="none"` when outer layout CSS (e.g. legal panels) supplies padding
- `Inline`, `Checkbox` for repeated action rows and boolean toggles
- `FormRow`, `FormSection` to reduce form label/hint boilerplate
- shared utility `cx()` for class composition (e.g. `Link` + `ui-button` / `ui-button--primary` for router CTAs)
- CSS tokens/components in `src/ui/ui-kit.css`

The kit is designed for incremental adoption: keep existing page classes and migrate page-by-page without adding Tailwind or another component framework.

## Running with the API locally

From `client/`, `./start-all.sh` starts the API (`../api`) then `vp dev` (requires `pnpm install` at the repo root first).

During Playwright runs you may see Vite+ log lines like `ws proxy error: connect ECONNREFUSED 127.0.0.1:3001`. This is expected in tests that do not exercise the API websocket path; it is non-fatal as long as test assertions still pass.

## Docker

`Dockerfile.dev` / `Dockerfile.prod` use the **repository root** as build context: they copy the root `pnpm-workspace.yaml` + `pnpm-lock.yaml` and both workspace `package.json` files, then `pnpm install --frozen-lockfile --filter client...`. The production image runs **`vp build`**. Commit lockfile changes from the repo root after dependency changes.

## Playwright WebKit on Arch / CachyOS

Playwright's Linux WebKit bundle is built against Ubuntu-flavored runtime SONAMEs (notably ICU/flite/jxl variants), so Arch-compatible packages alone can still leave `mobile-webkit` unable to launch.

Use the built-in guard + sync flow:

1. Sync Ubuntu runtime libraries into a local extras directory and active Playwright WebKit bundles:
   - `pnpm run sync:webkit-ubuntu-libs`
2. Run WebKit e2e (guarded command):
   - `pnpm run e2e:webkit`

Notes:

- `e2e:webkit` runs `e2e/scripts/ensure-webkit-libs.sh` first. If required libs are missing, it auto-runs `e2e/scripts/sync-webkit-ubuntu-libs.sh` locally.
- `e2e:webkit` sets `PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1` so Playwright's Ubuntu-only host validator does not block Arch/Cachy hosts after runtime libs are synced.
- In CI (Ubuntu), `.github/workflows/client.yml` installs browsers with deps and runs the same guarded `e2e:webkit` command.
