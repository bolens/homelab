# Kokoro FastAPI (TTS)

**Kokoro-82M** text-to-speech with a **built-in web UI** (`/web`), **OpenAPI docs** (`/docs`), and an **OpenAI-compatible** speech API (`/v1/audio/speech`).

**GitHub:** https://github.com/remsky/Kokoro-FastAPI
**Image (CPU):** `ghcr.io/remsky/kokoro-fastapi-cpu:latest`, **GPU:** `ghcr.io/remsky/kokoro-fastapi-gpu:latest`

## Quick start

1. `./prepare-stack.sh`
2. Optional: set `KOKORO_IMAGE_TAG` and `API_LOG_LEVEL` in `stack.env` (see `stack.env.example`).
3. `docker compose up -d` (after `./prepare-stack.sh` copies `stack.env` → `.env`)
4. Merge `caddy_snippet.conf` into Caddy (default is **split-horizon only**: `kokoro-tts.home` / `.local`, no public site in-repo), reload Caddy.

Open **https://kokoro-tts.home/web** (or your internal hostname) to try voices. API base on Docker: **`http://kokoro-tts:8880/v1`** with a dummy API key (e.g. `not-needed`). Add your own public `site` in Caddy only if you intentionally expose TTS on the Internet.

## Integration

| Client | Hint |
|--------|------|
| **Open WebUI** | Admin → Audio: OpenAI-compatible TTS base URL → **`http://kokoro-tts:8880/v1`** on `ai-backend` (preferred), or a public `https://…/v1` only if you add that in Caddy yourself. See the upstream [Open WebUI integration wiki](https://github.com/remsky/Kokoro-FastAPI/wiki/Integrations-OpenWebUi). |
| **Scripts / n8n** | `GET /v1/audio/voices`, `POST /v1/audio/speech` with `model: kokoro`, `voice` (e.g. `af_bella`), `input`, `response_format` (`mp3`, `wav`, …). |

## GPU

For faster inference on NVIDIA hosts, switch the image to **`ghcr.io/remsky/kokoro-fastapi-gpu:latest`** (set `KOKORO_IMAGE_TAG=latest` on the GPU image name by editing `docker-compose.yml` or use a compose override), install the **NVIDIA Container Toolkit**, and add the same **`deploy.resources.reservations.devices`** block as in `stacks/ollama/docker-compose.yml`.

## Portainer

Compose path `stacks/kokoro-tts/docker-compose.yml`; attach **`ai-backend`** and **`ingress-public`**; env from `stack.env` (optional tuning only).
