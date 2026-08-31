# Open Notebook Stack

An open source, privacy-focused alternative to Google's Notebook LM with support for multiple AI providers.

**Website:** https://www.open-notebook.ai  
**Docs:** https://github.com/lfnovo/open-notebook#readme  
**GitHub:** https://github.com/lfnovo/open-notebook  
**Docker image:** https://hub.docker.com/r/lfnovo/open_notebook  
**Releases:** https://github.com/lfnovo/open-notebook/releases  

## Features

- **Privacy-First**: Your data stays under your control
- **Multi-Model Support**: Works with OpenAI, Anthropic, Ollama, and more
- **Multi-Modal Content**: PDFs, videos, audio, web pages, and more
- **Podcast Generation**: Create professional podcasts from your research
- **Vector Search**: Full-text and vector search across content

## Setup

1. Run `./prepare-stack.sh` (creates `stack.env` and `caddy_snippet.conf` from examples when missing).

2. **IMPORTANT**: Generate secure keys and set them in `stack.env` (see **Generating keys and secrets** below for the full list).

3. Configure Ollama connection:
   - If Ollama is on the same Docker network: `OLLAMA_BASE_URL=http://ollama:11434`
   - If Ollama is on host: `OLLAMA_BASE_URL=http://host.docker.internal:11434`

4. Set `API_URL` in `stack.env` to the **exact URL you open in the browser** (default stack Caddy snippet is split-horizon only, e.g. `https://open-notebook.home`). Add a public hostname in Caddy yourself only if you need remote access.

5. Start the stack:
   ```bash
   docker compose up -d
   ```

## Generating keys and secrets

Run these and set the outputs in `stack.env`:

```bash
# OPEN_NOTEBOOK_ENCRYPTION_KEY – app encryption (required for storing API keys)
openssl rand -base64 32

# SURREAL_PASSWORD – SurrealDB password
openssl rand -base64 24

# OPEN_NOTEBOOK_PASSWORD – UI login password (optional; use after logout)
openssl rand -base64 24
```

Set each variable to the corresponding output. `OPEN_NOTEBOOK_ENCRYPTION_KEY` and `SURREAL_PASSWORD` are required; `OPEN_NOTEBOOK_PASSWORD` is optional but recommended so you can log in after logout. Do not use placeholder values in production.

## Usage

Once running, Open Notebook is available through Caddy on `ingress-public`. No host ports are exposed.

## Portainer

1. Run `./prepare-stack.sh` on the Docker host first; it prepares config and ensures `ai-backend` plus `ingress-public`.
2. In Portainer, use **Stacks** -> **Add stack** -> **Repository** and set compose path to `stacks/open-notebook/docker-compose.yml` (preferred).
3. If you deploy by pasting compose instead, mirror the same values from `stack.env` in Portainer's environment section.
4. Keep this stack private behind Caddy and Cloudflare Access (no published host ports).

### Initial setup

1. Go to **Settings** → **API Keys**
2. Add your AI provider credentials (OpenAI, Anthropic, etc.)
3. If using Ollama, configure it in the settings

### Connecting to Ollama

If you're running Ollama in another Docker stack, you can connect by:
1. Adding Ollama to the shared `ai-backend` network
2. Setting `OLLAMA_BASE_URL=http://ollama:11434` in `stack.env`

For shared Ollama backend and one-time setup, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).

### SurrealDB connection

This stack expects Open Notebook to connect to SurrealDB over:

`SURREAL_URL=ws://surrealdb:8000/rpc`

Keep that default unless you intentionally run SurrealDB outside this compose stack.

The bundled database uses SurrealDB v3 and stores data in the explicitly named
`open-notebook_surrealdb_data_v3` volume. SurrealDB v3 cannot open a v2 RocksDB
datastore in place. Existing v2 installations must create a v3-compatible
export, import it into this fresh v3 volume, and retain the old volume until the
migrated application has been verified.

## Configuration

### AI providers

Open Notebook supports:
- OpenAI
- Anthropic (Claude)
- Google (GenAI)
- Ollama (local models)
- Groq
- And many more...

Configure API keys in the web UI after first login.

### Data storage

- SurrealDB data and Open Notebook app data are stored in Docker-managed named volumes (`surrealdb_data`, `open_notebook_data`).

### Resource limits and backup

- Compose includes baseline `cpus`/`mem_limit` caps for both `open_notebook` and `surrealdb`.
- Include both `surrealdb_data` and `open_notebook_data` in backups (both are required for full restore).
- Recommended cadence: daily snapshots plus pre-upgrade backups.

## Troubleshooting

### Password prompt after logout
- The UI login uses **`OPEN_NOTEBOOK_PASSWORD`**. Set it in `stack.env` (e.g. `OPEN_NOTEBOOK_PASSWORD=your-chosen-password`), recreate the container, then use that password when the app asks for it after logout. If you never set it, the app may still show a password field; set it now and restart the stack, then use that value to log in.

### Unable to Connect to API Server
- Set `API_URL` in `stack.env` to the exact URL you use in the browser (e.g. `https://open-notebook.home`, or your own public hostname if you added one in Caddy).
- Ensure Caddy proxies the hostname to `open-notebook:8502`.

### Encryption key error
- Ensure `OPEN_NOTEBOOK_ENCRYPTION_KEY` is set and is a secure random string
- Never reuse encryption keys between installations

### SurrealDB connection issues
- Check that SurrealDB is running: `docker ps | grep surrealdb`
- Verify credentials match in both services

### Ollama connection issues
- Verify Ollama is accessible at the configured URL
- Check network connectivity between containers
- Ensure Ollama is running and models are available

## Documentation

For more information, visit: https://www.open-notebook.ai
