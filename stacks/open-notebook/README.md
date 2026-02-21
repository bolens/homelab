# Open Notebook Stack

An open source, privacy-focused alternative to Google's Notebook LM with support for multiple AI providers.

## Features

- **Privacy-First**: Your data stays under your control
- **Multi-Model Support**: Works with OpenAI, Anthropic, Ollama, and more
- **Multi-Modal Content**: PDFs, videos, audio, web pages, and more
- **Podcast Generation**: Create professional podcasts from your research
- **Vector Search**: Full-text and vector search across content

## Setup

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. **IMPORTANT**: Generate secure keys and set them in `.env` (see **Generating keys and secrets** below for the full list).

3. Configure Ollama connection:
   - If Ollama is on the same Docker network: `OLLAMA_BASE_URL=http://ollama:11434`
   - If Ollama is on host: `OLLAMA_BASE_URL=http://host.docker.internal:11434`

4. Start the stack:
   ```bash
   docker compose up -d
   ```

## Generating keys and secrets

Run these and set the outputs in `.env`:

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

Once running, Open Notebook is available via Caddy (e.g. `open-notebook.home`, `open-notebook.bolens.dev`) on the monitor network. No host ports are exposed.

### Initial Setup

1. Go to **Settings** → **API Keys**
2. Add your AI provider credentials (OpenAI, Anthropic, etc.)
3. If using Ollama, configure it in the settings

### Connecting to Ollama

If you're running Ollama in another Docker stack, you can connect by:
1. Adding Ollama to the same Docker network (`monitor` network)
2. Setting `OLLAMA_BASE_URL=http://ollama:11434` in `.env`

## Configuration

### AI Providers

Open Notebook supports:
- OpenAI
- Anthropic (Claude)
- Google (GenAI)
- Ollama (local models)
- Groq
- And many more...

Configure API keys in the web UI after first login.

### Data Storage

- SurrealDB data and Open Notebook app data are stored in Docker-managed named volumes (`surrealdb_data`, `open_notebook_data`).

## Troubleshooting

### Password prompt after logout
- The UI login uses **`OPEN_NOTEBOOK_PASSWORD`**. Set it in `.env` (e.g. `OPEN_NOTEBOOK_PASSWORD=your-chosen-password`), recreate the container, then use that password when the app asks for it after logout. If you never set it, the app may still show a password field; set it now and restart the stack, then use that value to log in.

### Unable to Connect to API Server
- Set `API_URL` in `.env` to the public URL you use in the browser (e.g. `https://notebook.bolens.dev` or `https://open-notebook.home`). Caddy must route both the site and `/api*` to this stack.

### Encryption Key Error
- Ensure `OPEN_NOTEBOOK_ENCRYPTION_KEY` is set and is a secure random string
- Never reuse encryption keys between installations

### SurrealDB Connection Issues
- Check that SurrealDB is running: `docker ps | grep surrealdb`
- Verify credentials match in both services

### Ollama Connection Issues
- Verify Ollama is accessible at the configured URL
- Check network connectivity between containers
- Ensure Ollama is running and models are available

## Documentation

For more information, visit: https://www.open-notebook.ai
