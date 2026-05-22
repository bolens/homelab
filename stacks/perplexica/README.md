# Perplexica Stack

Privacy-focused AI-powered answering engine that combines web search with AI models for cited answers. This stack runs Perplexica behind Caddy on the shared `monitor` network with no published host ports.

**Website:** https://perplexica.ai  
**Docs:** https://github.com/ItzCrazyKns/Perplexica#readme  
**GitHub:** https://github.com/ItzCrazyKns/Perplexica  
**Docker image:** https://hub.docker.com/r/itzcrazykns1337/perplexica  
**Releases:** https://github.com/ItzCrazyKns/Perplexica/releases  

## Quick start

1. From this directory, run `./prepare-stack.sh` to create `stack.env` from the example, copy the Caddy snippet template if needed, and ensure the shared `monitor` network exists.
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
| **Network** | `monitor` (external) |
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

If you are using the shared Ollama stack, keep both stacks on the `monitor` network and set:

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
- Internal monitoring: use `http://perplexica:3000/` from the `monitor` network if needed

## Resource limits and backup

- Compose includes baseline limits (`cpus` and `mem_limit`) to prevent one AI stack from starving others.
- Persistent data is in Docker volume `perplexica_data`; include it in regular backups.
- Recommended cadence: daily snapshots for active usage, plus pre-upgrade backup before image/tag changes.

## Portainer

For a Portainer deployment that matches the rest of this repo:

- Preferred: `Stacks` -> `Add stack` -> `Repository`, then point Portainer at this repo and use compose path `stacks/perplexica/docker-compose.yml`.
- Run `./prepare-stack.sh` on the Docker host first so `stack.env` and `caddy_snippet.conf` exist.
- If deploying by pasting compose into Portainer instead of using the repo path, create the same `stack.env` values in Portainer's environment UI and keep the app attached to the external `monitor` network.
- Do not publish ports from this stack; let Caddy remain the only HTTP entrypoint.

## Troubleshooting

### Ollama connection issues

- Verify Ollama is reachable at the configured `OLLAMA_BASE_URL`
- If using the shared stack, verify both containers are on the `monitor` network
- Ensure the target Ollama host already has models pulled

### Search backend issues

- If `SEARXNG_API_URL` is set, verify the URL is reachable from the container
- If using bundled SearxNG, check the Perplexica container logs for startup errors

### Caddy / hostname issues

- Verify `caddy_snippet.conf` uses your real hostname locally
- Reload Caddy after changing the snippet
- Confirm DNS / tunnel routing points at your Caddy entrypoint
