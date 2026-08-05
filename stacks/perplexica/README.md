# Perplexica Stack

Privacy-focused AI-powered answering engine that combines web search with AI models for cited answers. Perplexica uses `ingress-public` for Caddy and `ai-backend` for shared AI/search backends.

**Website:** https://perplexica.ai  
**Docs:** https://github.com/ItzCrazyKns/Perplexica#readme  
**GitHub:** https://github.com/ItzCrazyKns/Perplexica  
**Docker image:** https://hub.docker.com/r/itzcrazykns1337/perplexica  
**Releases:** https://github.com/ItzCrazyKns/Perplexica/releases  

## Quick start

1. Run `./prepare-stack.sh` to create `stack.env`, copy the Caddy snippet template, and ensure `ingress-public` plus `ai-backend`.
2. Edit `stack.env`:
   - Leave `SEARXNG_API_URL` empty to use the bundled SearxNG backend.
   - Set `OLLAMA_BASE_URL=http://ollama:11434` if you want to use the shared Ollama stack on the same Docker network.
   - Keep `OLLAMA_BASE_URL=http://host.docker.internal:11434` if Ollama runs directly on the same Docker host.
3. Replace the placeholder hostname in `caddy_snippet.conf` and reload Caddy so `https://perplexica.example.com` (your real hostname locally) proxies to `perplexica:3000`.
4. Deploy:

   ```bash
   docker compose up -d
   ```

5. Open Perplexica via Caddy. The app listens on `3000` inside the container and uses `8080` for the internal health check.

## Configuration

| Item | Details |
|------|---------|
| **Access** | Via Caddy -> `perplexica:3000` |
| **Network** | `ingress-public` for Caddy; `ai-backend` for Ollama and SearXNG |
| **Storage** | Docker-managed volume `perplexica_data` mounted at `/home/perplexica/data` |
| **Search backend** | Bundled SearxNG by default; override with `SEARXNG_API_URL` |
| **LLM backend** | Optional Ollama via `OLLAMA_BASE_URL` |
| **Caddy** | See `caddy_snippet.conf.example` (placeholder `perplexica.example.com`) |

## Initial setup

After the container is up:

1. Open the web UI through your Caddy hostname.
2. Go to the Perplexica settings page.
3. Configure the AI providers you want to use:
   - Local Ollama models
   - OpenAI-compatible APIs
   - Anthropic
   - Gemini
   - Other providers supported upstream

Provider API keys are stored in the application, not in `stack.env`.

## Integrations

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
- Persistent data is in Docker volume `perplexica_data`; include it in regular backups.
- Recommended cadence: daily snapshots for active usage, plus pre-upgrade backup before image/tag changes.

## Portainer

For a Portainer deployment that matches the rest of this repo:

- Preferred: `Stacks` -> `Add stack` -> `Repository`, then point Portainer at this repo and use compose path `stacks/perplexica/docker-compose.yml`.
- Run `./prepare-stack.sh` on the Docker host first so `stack.env` and `caddy_snippet.conf` exist.
- If deploying through Portainer, attach the app to external `ingress-public` and `ai-backend`.
- Do not publish ports from this stack; let Caddy remain the only HTTP entrypoint.

## Troubleshooting

### Ollama connection issues

- Verify Ollama is reachable at the configured `OLLAMA_BASE_URL`
- If using the shared stack, verify both containers are on `ai-backend`
- Ensure the target Ollama host already has models pulled

### Search backend issues

- If `SEARXNG_API_URL` is set, verify the URL is reachable from the container
- If using bundled SearxNG, check the Perplexica container logs for startup errors

### Caddy / hostname issues

- Verify `caddy_snippet.conf` uses your real hostname locally
- Reload Caddy after changing the snippet
- Confirm DNS / tunnel routing points at your Caddy entrypoint
