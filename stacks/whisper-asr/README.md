# Whisper ASR webservice

**OpenAI-compatible** transcription HTTP API (audio → text) using Whisper, **faster-whisper**, or WhisperX.

**GitHub:** https://github.com/ahmetoner/whisper-asr-webservice  
**Image:** `onerahmet/openai-whisper-asr-webservice:latest` (CPU) or `...:latest-gpu` with NVIDIA

## Quick start

1. `./prepare-stack.sh`
2. Tune **`ASR_MODEL`** / **`ASR_ENGINE`** in `stack.env` (see `stack.env.example`).
3. `docker compose --env-file stack.env up -d`
4. Caddy snippet → `https://stt.example.com` (internal try first with `*.home` / `*.local` blocks in the example).

## Integration

| Client | Hint |
|--------|------|
| **Open WebUI** | Admin → Audio: set a compatible OpenAI-style transcription base URL to your public Whisper URL (or internal `http://whisper-asr:9000` if the UI can reach Docker DNS). |
| **AnythingLLM** | Configure custom STT in the app UI to the same URL. |
| **n8n / scripts** | POST audio per [upstream API / Swagger](https://ahmetoner.github.io/whisper-asr-webservice) at `/` on port **9000**. |

## GPU

For faster inference, switch the image to **`onerahmet/openai-whisper-asr-webservice:latest-gpu`**, set **`ASR_DEVICE=cuda`**, install the **NVIDIA Container Toolkit**, and add the same **`deploy.resources.reservations.devices`** NVIDIA block used in `stacks/ollama/docker-compose.yml`.

## Portainer

Compose path `stacks/whisper-asr/docker-compose.yml`; attach **`monitor`**; no secrets required beyond optional tuning in `stack.env`.
