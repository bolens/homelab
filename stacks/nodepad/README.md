# nodepad

Spatial, AI-augmented thinking canvas ([nodepad](https://github.com/mskayyali/nodepad)) — notes on a canvas with automatic classification and connections. **API keys are stored only in the browser** (per upstream); the container just serves the Next.js UI.

- **Homepage:** [nodepad.space](https://nodepad.space)
- **Repo:** [github.com/mskayyali/nodepad](https://github.com/mskayyali/nodepad)

## Homelab patches (`patches/*.patch`)

Upstream sources live in `./repo` (gitignored). **`clone-repo.sh`** fetches
the pinned [mskayyali/nodepad](https://github.com/mskayyali/nodepad) revision,
resets the tree to that clean checkout, then applies **`patches/*.patch` in
sorted order** so overlays survive deliberate upstream updates.

- **`docker compose build`** copies `./repo` as-is; it must already be patched. Run **`./clone-repo.sh` before every build** (or after editing patches) so `repo/` matches upstream + `patches/*.patch`. Patches are not re-applied inside the Dockerfile (that would double-apply when `repo/` is already patched).
- If a patch **fails** after updating `UPSTREAM_REVISION` in `clone-repo.sh`,
  upstream changed overlapping lines. Refresh the affected patch(es): apply
  `0001…000N-1` in order, commit a baseline (`git commit -am baseline`), make
  edits, then save the resulting patch and restore the pinned checkout.
- **`./verify-patches.sh`** — runs `clone-repo.sh` then `npm ci` + `npm run build` in `./repo` (optional CI check).

Current patches (apply in lexical order; do not rename):

| Patch | Purpose |
|-------|---------|
| `0001-homelab-ollama-proxy.patch` | Ollama provider + `/api/ollama/...` proxy to `OLLAMA_ORIGIN`. |
| `0002-homelab-umami-and-metadata.patch` | Self-hosted Umami (`UMAMI_*` env), CSP from script URL, `generateMetadata` + `NODEPAD_SITE_URL`. |
| `0003-homelab-ux-selfhost.patch` | Build-time default provider/model, OpenRouter `Referer` = current origin, About + banner copy for homelab. |
| `0004-homelab-ops-health-and-proxy-guard.patch` | `GET /api/health`, optional `NODEPAD_ALLOWED_ORIGINS` on mutating Ollama proxy calls. |
| `0005-homelab-fetch-url-useragent-ollama-patch-health-head.patch` | `/api/fetch-url` User-Agent uses `NODEPAD_SITE_URL` origin; `PATCH` on `/api/ollama` proxy; `HEAD /api/health` for probes. |
| `0006-homelab-fetch-url-redirect-ssrf-guard.patch` | After `redirect: "follow"`, reject the **final** response URL if it matches the same blocked-host rules as the initial URL (redirect SSRF bypass). |

## Environment (stack / build)

| Variable | Where | Purpose |
|----------|--------|---------|
| `OLLAMA_ORIGIN` | runtime | Ollama base URL inside Docker (default `http://ollama:11434`). |
| `NODEPAD_SITE_URL` | runtime | Public site URL for metadata / OpenGraph (e.g. `https://nodepad.example.com`). |
| `UMAMI_SCRIPT_URL` | runtime | Full URL to your Umami `script.js` (omit to disable analytics). |
| `UMAMI_WEBSITE_ID` | runtime | Umami website id (required with `UMAMI_SCRIPT_URL`). |
| `NODEPAD_ALLOWED_ORIGINS` | runtime | Comma-separated allowed `Origin` values for POST/PUT/PATCH/DELETE to `/api/ollama` (omit to allow any origin). |
| `NEXT_PUBLIC_HOMELAB_DEFAULT_PROVIDER` | **build** arg (optional) | e.g. `ollama` — first-visit default in the client bundle. Not read from `stack.env` at build unless you pass it explicitly (see below). |
| `NEXT_PUBLIC_HOMELAB_DEFAULT_OLLAMA_MODEL` | **build** arg (optional) | e.g. `llama3.2` when default provider is Ollama. Same as above. |

**Runtime:** Put `OLLAMA_ORIGIN`, `NODEPAD_SITE_URL`, `UMAMI_*`, `NODEPAD_ALLOWED_ORIGINS` in **`stack.env`**. `docker-compose.yml` loads them with **`env_file: stack.env`** only — Compose does **not** need a project `.env` or symlink for those variables.

**Optional `NEXT_PUBLIC_*` (baked into the JS bundle):** Compose does **not** read `env_file` during `docker compose build`. Pass **`docker compose build --build-arg NEXT_PUBLIC_HOMELAB_DEFAULT_PROVIDER=ollama --build-arg NEXT_PUBLIC_HOMELAB_DEFAULT_OLLAMA_MODEL=llama3.2`** (see Dockerfile `ARG` lines), or add your own `build.args` + project env file if you prefer interpolation-driven builds.

## Ollama (local models)

1. Run the **Ollama** stack on **`ai-backend`** so `http://ollama:11434` resolves from Nodepad.
2. Rebuild/restart nodepad after changing patches or compose.
3. In the app: **☰ → Settings → Provider → Ollama (local)**. Set **Model** to a pulled tag (e.g. `llama3.2`). API key is optional (Ollama ignores it unless you enable auth upstream).

## Quick start

### Local (`docker compose`)

1. From this directory:

   ```bash
   ./prepare-stack.sh
   ./clone-repo.sh
   ./verify-patches.sh   # optional: confirms patches + npm build
   docker compose build   # add --build-arg for NEXT_PUBLIC_* if needed
   docker compose up -d
   ```

2. Point Caddy at this stack: ensure `stacks/caddy/` imports `stacks/*/caddy_snippet.conf`, copy `caddy_snippet.conf.example` → `caddy_snippet.conf` (done by `prepare-stack.sh`), set your real hostname, reload Caddy.

3. Open `https://nodepad.example.com` (replace with your hostname). In the app: menu → **Settings** → choose provider → API key and/or **Ollama** model (settings stay in browser `localStorage`; Ollama traffic is proxied through this app to `OLLAMA_ORIGIN`).

Until a registry (for example Harbor) is reachable, **this path is the simplest** — compose builds and tags **`nodepad:latest`** by default.

### Portainer

1. **Image:** On any host that has this stack directory (or a copy of `Dockerfile` + `clone-repo.sh`), run `./clone-repo.sh` then `docker build -t <your-registry>/homelab/nodepad:latest .` and push that tag. The Git repo does not include `./repo` (it is gitignored), so Portainer cannot build from a bare git checkout unless you run `clone-repo.sh` on the server first or use a CI job that embeds the upstream sources. In `docker-compose.yml`, **comment out the `build:` block** and set **`image:`** to your pushed tag (or override the image in the Portainer stack UI).
2. **Networks:** Ensure external **`ai-backend`** and **`ingress-public`** exist.
3. **Stack:** In Portainer → **Stacks** → **Add stack** → use **Repository** (recommended) with this monorepo’s URL and **Compose path** `stacks/nodepad/docker-compose.yml`, or paste the contents of that file in the web editor.
4. **Environment:** Paste the same variables as `stack.env.example` into Portainer’s stack environment (or attach an env file). Runtime keys match **`env_file`** usage in compose.
5. **Caddy:** Add or enable the snippet from `caddy_snippet.conf.example` (via `prepare-stack.sh` or manual copy) on your Caddy host and reload Caddy.

## Networking

- **Internal AI/Caddy:** `http://nodepad:3000` on `ai-backend` and `ingress-public`.
- **No host ports** — use Caddy only.

## Updating

**Local:**

```bash
./clone-repo.sh
docker compose build --no-cache
docker compose up -d
```

**Registry / Portainer:** Rebuild and push a new tag (or `:latest`), update **`image:`** (or the Portainer image field) if the tag changed, then **Pull and redeploy** the stack in Portainer.

**Changing `stack.env` locally:** Edit `stack.env`, then `docker compose up -d` (or `--force-recreate`) so the container picks up runtime vars. Rebuild only when you change **`NEXT_PUBLIC_*`**, patches, or the image build itself.

## Resources

Builds can use significant RAM during `next build`; allow ~2–4 GiB free on the Docker host for the build step. Runtime is modest (~512 MiB–1 GiB).
