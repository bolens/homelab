# Open WebUI Stack

Extensible, feature-rich, and user-friendly self-hosted AI platform designed to operate entirely offline. Supports Ollama and OpenAI-compatible APIs.

## Features

- **Multi-Provider Support**: Ollama, OpenAI, Anthropic, Google, and more
- **RAG Integration**: Local RAG with 9+ vector database options
- **Web Search**: 15+ search providers for enhanced context
- **Voice/Video**: Speech-to-text and text-to-speech support
- **Image Generation**: DALL-E, Stable Diffusion, ComfyUI integration
- **Multi-User**: Role-based access control
- **Responsive Design**: Works on desktop and mobile
- **PWA Support**: Progressive Web App for mobile

## Setup

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Configure Ollama connection:
   - If Ollama is on the same Docker network: `OLLAMA_BASE_URL=http://ollama:11434`
   - If Ollama is on host: `OLLAMA_BASE_URL=http://host.docker.internal:11434`

3. (Optional) Configure OpenAI API key if you want to use OpenAI directly:
   ```bash
   OPENAI_API_KEY=sk-your-api-key-here
   ```

4. (Optional) Generate security keys for production:
   ```bash
   openssl rand -base64 32  # For WEBUI_SECRET_KEY
   openssl rand -base64 32  # For WEBUI_JWT_SECRET_KEY
   ```

5. Start the stack:
   ```bash
   docker compose up -d
   ```

## Usage

Once running, Open WebUI will be available at `http://localhost:3000`.

### Initial Setup

1. Open the web UI at `http://localhost:3000`
2. Create your first admin account
3. Configure AI providers in Settings
4. Start chatting!

### AI Providers

Open WebUI supports:
- **Ollama** (local models) - Recommended for privacy
- **OpenAI** (GPT-3.5, GPT-4, etc.)
- **Anthropic** (Claude)
- **Google** (Gemini)
- **Azure OpenAI**
- **OpenRouter**
- **And many more...**

Configure providers in Settings → Connections after login.

### Ollama model management (install & maintain models)

Open WebUI can manage your Ollama models so you don’t need `docker exec`:

- **Settings → Connections → Ollama → Manage** (wrench icon): pull new models, see installed models, and configure the Ollama connection.
- In chat, when you pick a model that isn’t installed, Open WebUI can prompt you to download it.

Use this as your web UI for installing and maintaining Ollama models.

### Features

#### RAG (Retrieval Augmented Generation)
- Upload documents to your library
- Use `#` command in chat to reference documents
- Supports PDFs, text files, images, and more

#### Web Search
- Enable web search in chat settings
- Supports SearXNG, Google, Brave, Kagi, and more
- Automatically injects search results into context

#### Voice & Video
- Speech-to-text with Whisper, OpenAI, Deepgram, Azure
- Text-to-speech with Azure, ElevenLabs, OpenAI, Transformers

#### Image Generation
- DALL-E 3/2
- Stable Diffusion (local)
- ComfyUI (local)
- GPT-Image-1

## Configuration

### Connecting to Ollama

If you're running Ollama in another Docker stack:
1. Add Ollama to the same Docker network (`monitor` network)
2. Set `OLLAMA_BASE_URL=http://ollama:11434` in `.env`

### Database Options

Open WebUI uses SQLite by default. For production, you can configure:
- PostgreSQL
- Cloud storage backends (S3, GCS, Azure Blob)

See Open WebUI documentation for advanced database configuration.

### Authentication

- **Signups**: Control with `ENABLE_SIGNUP` (default: true)
- **Default Role**: Set with `DEFAULT_USER_ROLE` (user/admin)
- **OAuth**: Configure in Settings → Authentication
- **LDAP/AD**: Available for enterprise deployments

## Troubleshooting

### Ollama Connection Issues
- Verify Ollama is accessible at the configured URL
- Check network connectivity between containers
- Ensure Ollama is running and models are available
- Try `http://host.docker.internal:11434` if on same host

### Port Conflicts
- Change `OPEN_WEBUI_HOST_PORT` in `.env` if port 3000 is already in use

### Permission Issues
- Ensure data directory has proper permissions
- Container runs as non-root user

### Database Issues
- Check data directory is writable
- Verify disk space is available
- For SQLite issues, check file permissions

## Advanced Configuration

### Using CUDA Image

For GPU acceleration with Ollama, you can use the CUDA image:
```yaml
image: ghcr.io/open-webui/open-webui:cuda
```

### Using Bundled Ollama

For a single-container setup with Ollama included:
```yaml
image: ghcr.io/open-webui/open-webui:ollama
```

## Documentation

For more information, visit: https://docs.openwebui.com
