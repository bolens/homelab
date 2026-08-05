# Paperless-GPT

LLM and OCR augmentation service for `paperless-ngx`.

**Repo/docs:** https://github.com/icereed/paperless-gpt  
**Image:** https://hub.docker.com/r/icereed/paperless-gpt

## Dependencies

- `paperless-ngx` stack (API token required)
- `ollama` stack (for local LLM/vision models)
- Shared `document-services` network for the Paperless API
- Shared `ai-backend` network for Ollama plus Caddy-only `ingress-sensitive`

## Quick start

1. Prepare local files:
   - `./prepare-stack.sh`
2. Edit `stack.env`:
   - Set `PAPERLESS_API_TOKEN`
   - Keep `PAPERLESS_BASE_URL` on `http://paperless-ngx:8000`
   - Set `PAPERLESS_PUBLIC_URL` to the browser-facing HTTPS URL
   - Set `OLLAMA_HOST`, `LLM_MODEL`, and `VISION_LLM_MODEL`
3. Start:
   - `docker compose --env-file stack.env up -d`
4. Open:
   - `https://paperless-gpt.example.com` (via Caddy)

## Portainer

Repository compose path `stacks/paperless-gpt/docker-compose.yml`; ensure
**`document-services`**, **`ai-backend`**, and **`ingress-sensitive`** exist; create
the three **external** volumes first (see compose). Run `./prepare-stack.sh` on
the host before deploy.

## Notes

- Healthcheck uses `wget` (the image does not include `curl`).
- Keep models in Ollama pre-pulled (`ollama pull <model>`) before first use.
