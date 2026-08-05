# Paperless-GPT

LLM and OCR augmentation service for `paperless-ngx`.

**Repo/docs:** https://github.com/icereed/paperless-gpt  
**Image:** https://hub.docker.com/r/icereed/paperless-gpt

## Dependencies

- `paperless-ngx` stack (API token required)
- `ollama` stack (for local LLM/vision models)
- Shared `ai-services` network plus Caddy-only `proxy-ingress`

## Quick start

1. Prepare local files:
   - `./prepare-stack.sh`
2. Edit `stack.env`:
   - Set `PAPERLESS_API_TOKEN`
   - Confirm `PAPERLESS_BASE_URL`
   - Set `OLLAMA_HOST`, `LLM_MODEL`, and `VISION_LLM_MODEL`
3. Start:
   - `docker compose --env-file stack.env up -d`
4. Open:
   - `https://paperless-gpt.example.com` (via Caddy)

## Portainer

Repository compose path `stacks/paperless-gpt/docker-compose.yml`; ensure **`ai-services`** and **`proxy-ingress`** exist; create the three **external** volumes first (see compose). Run `./prepare-stack.sh` on the host before deploy.

## Notes

- Healthcheck uses `wget` (the image does not include `curl`).
- Keep models in Ollama pre-pulled (`ollama pull <model>`) before first use.
