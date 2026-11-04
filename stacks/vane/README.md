# Vane (formerly Perplexica)

Privacy-focused AI-powered answering engine that combines web search with AI models for cited answers. Vane uses `ingress-public` for Caddy and `ai-backend` for shared AI/search backends.

**Website:** https://github.com/ItzCrazyKns/Vane

**Docs:** https://github.com/ItzCrazyKns/Vane#readme

**GitHub:** https://github.com/ItzCrazyKns/Vane

**Docker image:** https://hub.docker.com/r/itzcrazykns1337/vane

**Releases:** https://github.com/ItzCrazyKns/Vane/releases

## Quick start

1. Run `./prepare-stack.sh` to create `stack.env`, copy the Caddy snippet template, and ensure `ingress-public` plus `ai-backend`.
2. Edit `stack.env`:
   - Leave `SEARXNG_API_URL` empty to use the bundled SearxNG backend.
   - Set `OLLAMA_BASE_URL=http://ollama:11434` if you want to use the shared Ollama stack on the same Docker network.
   - Set `OLLAMA_BASE_URL=http://host.docker.internal:11434` if Ollama runs directly on the same Docker host.
   - Leave `OLLAMA_BASE_URL` empty when using LiteLLM instead.
3. Replace the placeholder hostname in `caddy_snippet.conf` and reload Caddy so `https://vane.example.com` (your real hostname locally) proxies to `vane:3000`. Protect the full public hostname with owner-only Cloudflare Access before configuring provider keys.
4. Deploy:

   ```bash
   docker compose up -d --build
   ```

5. Open Vane via Caddy. The app listens on `3000` inside the container and bundles SearXNG on internal port `8080`.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy -> `vane:3000` |
| **Network** | `ingress-public` for Caddy; `ai-backend` for Ollama and SearXNG |
| **Storage** | Docker-managed volume `vane_data` mounted at `/home/vane/data` |
| **Uploads** | Docker-managed volume `vane_uploads` mounted at `/home/vane/uploads` |
| **Search backend** | Bundled SearxNG by default; override with `SEARXNG_API_URL` |
| **LLM backend** | Optional Ollama via `OLLAMA_BASE_URL` |
| **Caddy** | See `caddy_snippet.conf.example` (placeholder `vane.example.com`) |

## Access and users

Vane 1.12.2 has no built-in user accounts or per-user history isolation. Settings,
provider keys, uploads, and saved chats are shared by everyone who can access the
instance. Protect the entire public hostname, including `/api/*`, with an
owner-only Cloudflare Access policy before configuring provider credentials.
The settings API returns provider configuration, so protecting only the home
page is insufficient. Local Caddy aliases assume a trusted operator network and
need equivalent authentication if other users can reach them.

## Initial setup

After the container is up:

1. Open the web UI through your Caddy hostname.
2. Go to the Vane settings page.
3. Configure the AI providers you want to use:
   - Local Ollama models
   - OpenAI-compatible APIs
   - Anthropic
   - Gemini
   - Other providers supported upstream

Provider keys can be stored in application data through the settings UI or supplied
through private `stack.env`. Include both locations in configuration backups.

## Integrations

### LiteLLM

Use the shared [LiteLLM stack](../litellm/README.md) on `ai-backend`. In Vane's
settings, add an **OpenAI** provider with base URL `http://litellm:4000/v1` and a
dedicated LiteLLM virtual key restricted to the models this client should use.
Keep the master administration key out of Vane.

Add the gateway's exact model alias to that provider's chat models. Vane does not
automatically discover models for a custom OpenAI base URL. Select a model that
supports tool calling, then verify a request through Vane. For Copilot models,
apply the system-message setting documented in the LiteLLM README. Use Vane's built-in
Transformers provider for local embeddings, or add a gateway embedding model only
after verifying its `/v1/embeddings` endpoint.

For environment-based provider credentials, set `OPENAI_BASE_URL` and
`OPENAI_API_KEY` in private `stack.env`, synchronize its `.env` mirror, and recreate
Vane. The provider still needs an explicit model list in the UI. When replacing
unreachable direct Ollama connections, remove those connections in Vane and clear
`OLLAMA_BASE_URL`; otherwise startup imports that connection again. Preserve the
data volume and verify a backup before changing provider settings.

### Ollama

If you are using the shared Ollama stack, keep both stacks on `ai-backend` and set:

```bash
OLLAMA_BASE_URL=http://ollama:11434
```

For shared Ollama backend notes, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).

### External SearxNG

If you prefer an external SearxNG instance instead of the bundled backend:

1. Ensure the instance exposes the JSON API.
2. Ensure the engines you want are enabled there.
3. Set `SEARXNG_API_URL` in `stack.env` to the reachable internal URL.

## Health and monitoring

- Health check: container probes port **3000** on the container hostname (Next.js does not bind to loopback; see `docker-compose.yml`).
- External monitoring: use a normal HTTP check against the public app URL
- Internal access is limited to explicitly shared networks; use the public HTTPS URL for monitoring.

## Resource limits and backup

- Compose includes baseline limits (`cpus` and `mem_limit`) to prevent one AI stack from starving others.
- Back up both `vane_data` and `vane_uploads`. Provider settings and SQLite history live in the data volume; uploaded files live in the uploads volume.
- Recommended cadence: daily snapshots for active usage, plus pre-upgrade backup before image/tag changes.

## Pinned image and streaming fix

Compose builds `homelab/vane:1.12.2` from the current upstream Vane image, pinned
by digest in `Dockerfile`. It adds one guard for repeated empty OpenAI tool-call
argument deltas. The upstream parser otherwise throws `is empty`, which leaves
web research unfinished with compatible LiteLLM streaming providers.

The build checks the exact upstream server-bundle hash and runs the shipped
streaming method against native `partial-json` before and after the patch. Tests
cover repeated empty deltas, two tool calls, text streaming, malformed JSON, and
upstream source drift. Only the patched bundle enters the final image. The
allowlisted build context excludes runtime settings and credentials.

Use `docker compose up -d --build` after reviewing a base-image update. Watchtower
updates are disabled for this local image. Review the bundle and regression gate
when changing the upstream digest; the build refuses an unknown bundle. Linux
amd64 is verified. Other architectures need their own bundle verification.

## Upgrade from Perplexica

The renamed stack uses `stacks/vane`, Compose project and service `vane`, and
`vane` Caddy hostnames. The build uses the current upstream
`itzcrazykns1337/vane:latest` manifest, pinned in `Dockerfile`, with the streaming
fix described above. Update the Cloudflare Tunnel public hostname and DNS record
to match, preserving any existing Access policy and origin settings.

Before recreating the old container, stop it and back up the data volume, runtime
configuration, and `/home/perplexica/uploads` directory. Restore those copies into
an isolated location, compare file hashes, and run SQLite integrity and record
checks before proceeding.

Copy the existing runtime environment into the renamed stack. Set
`VANE_DATA_VOLUME` in both `stack.env` and its `.env` mirror to the actual existing
Docker data volume name, typically `perplexica_perplexica_data`. The new Compose
file mounts that same volume at `/home/vane/data`. Set `VANE_DATA_EXTERNAL=true`
in both files so Compose accepts the volume owned by the old project. Leaving
`VANE_DATA_VOLUME` empty selects a fresh `vane_vane_data` volume and will not show the old history.

Uploads now persist in `vane_uploads`. Older deployments kept uploads in the
container layer, so copy existing `/home/perplexica/uploads` into the new volume
before starting Vane. Retire the stopped old container after successful checks.

Check the UI, provider settings, search backend, uploaded files, and saved history
against the baseline. If preservation fails, stop Vane and restore the verified
backup with the prior image, mount paths, and configuration. An image downgrade
alone does not undo database changes. Remove only this operation's temporary
backup and restore copies after verification succeeds.

## Portainer

For a Portainer deployment that matches the rest of this repo:

- Preferred: `Stacks` -> `Add stack` -> `Repository`, then point Portainer at this repo and use compose path `stacks/vane/docker-compose.yml`.
- Run `./prepare-stack.sh` on the Docker host first so `stack.env` and `caddy_snippet.conf` exist.
- Build the image on that host before a Portainer deployment, or select a published commit-tagged custom image and omit `build`.
- If deploying through Portainer, attach the app to external `ingress-public` and `ai-backend`.
- Do not publish ports from this stack; let Caddy remain the only HTTP entrypoint.

## Troubleshooting

### Ollama connection issues

- Verify Ollama is reachable at the configured `OLLAMA_BASE_URL`
- If using the shared stack, verify both containers are on `ai-backend`
- Ensure the target Ollama host already has models pulled

### Search backend issues

- If `SEARXNG_API_URL` is set, verify the URL is reachable from the container
- If using bundled SearxNG, check the Vane container logs for startup errors

### Caddy / hostname issues

- Verify `caddy_snippet.conf` uses your real hostname locally
- Reload Caddy after changing the snippet
- Confirm DNS / tunnel routing points at your Caddy entrypoint
