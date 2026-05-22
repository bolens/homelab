# Paperless-AI next

AI-assisted classification and OCR rescue workflows for `paperless-ngx`.

**Docs:** https://paperless-ai-next.admon.me  
**Image:** https://hub.docker.com/r/admonstrator/paperless-ai-next  
**Repo:** https://github.com/admonstrator/paperless-ai-next

## Dependencies

- `paperless-ngx` stack (API token required)
- `ollama` stack (for local LLM inference)
- Shared `monitor` network

## Quick start

1. Prepare local files:
   - `./prepare-stack.sh`
2. Edit `stack.env`:
   - Set `PAPERLESS_API_TOKEN`
   - Confirm `PAPERLESS_API_URL` / `PAPERLESS_PUBLIC_URL`
   - Set `OLLAMA_API_URL` and `OLLAMA_MODEL`
3. Start:
   - `docker compose --env-file stack.env up -d`
4. Open:
   - `https://paperless-ai.example.com` (via Caddy)

## Portainer

Repository compose path `stacks/paperless-ai-next/docker-compose.yml`; attach **`monitor`**; ensure external volume `paperless-ai-next_paperless_ai_next_data` exists. Run `./prepare-stack.sh` on the host before deploy.

## Notes

- `ALLOW_REMOTE_SETUP=yes` is useful during first setup only; set it to `no` after onboarding.
- Keep `COOKIE_SECURE_MODE=auto` when serving via HTTPS behind Caddy.
