# AnythingLLM

All-in-one **RAG workspace**: upload documents, build vector workspaces, and chat with **Ollama** (or other providers) using built-in **LanceDB**.

**Docs:** https://github.com/Mintplex-Labs/anything-llm/blob/master/docker/HOW_TO_USE_DOCKER.md  
**Image:** `mintplexlabs/anythingllm:latest` (pin a digest or version tag for production)

## Quick start

1. `./prepare-stack.sh`
2. Set **`JWT_SECRET`** in `stack.env` (`openssl rand -base64 32`).
3. On **Ollama**, pull chat + embedding models matching `stack.env` (defaults: `llama3.2`, `nomic-embed-text:latest`).
4. `docker compose --env-file stack.env up -d`
5. Caddy: merge `caddy_snippet.conf` (split-horizon + **anything-llm.example.com**), put the public hostname behind **Cloudflare Access**, reload Caddy.

## Ollama

Use **`http://ollama:11434`** when this stack and **ollama** share the **`monitor`** network (defaults in `stack.env.example`). For Ollama on the Docker host only, use `http://host.docker.internal:11434`.

## Whisper (optional)

Deploy **`stacks/whisper-asr`** and configure custom speech-to-text in the AnythingLLM UI to your public or internal Whisper URL (e.g. `http://whisper-asr:9000`), or use bundled local Whisper per upstream docs.

## Security note

Compose includes **`cap_add: [SYS_ADMIN]`** as required by the upstream image for certain filesystem features. Treat the service like any other admin-facing AI app: keep it behind **Caddy** + **Cloudflare Access** (or similar).

## Portainer

Repository path `stacks/anything-llm/docker-compose.yml`; attach **`monitor`**; set the same env vars as `stack.env.example`.
