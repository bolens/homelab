# LibreChat Stack

Enhanced ChatGPT Clone with support for multiple AI providers, agents, MCP, code interpreter, and more.

**Website:** https://www.librechat.ai  
**Docs:** https://docs.librechat.ai  
**GitHub:** https://github.com/LibreChat-AI/LibreChat  
**Docker image:** https://github.com/LibreChat-AI/LibreChat/pkgs/container/librechat  
**Releases:** https://github.com/LibreChat-AI/LibreChat/releases  

## Features

- **Multi-Provider Support**: OpenAI, Anthropic, Google, Azure, Ollama, and more
- **Agents & Tools**: Build custom AI agents with MCP support
- **Code Interpreter**: Secure sandboxed code execution
- **Web Search**: Internet search integration
- **Image Generation**: DALL-E, Stable Diffusion, Flux
- **Artifacts**: Generate React, HTML, and Mermaid diagrams
- **Multi-User**: Secure authentication with OAuth2, LDAP, Email
- **Presets**: Create and share custom presets
- **Conversation Management**: Search, import, export conversations

## Setup

1. Copy `stack.env.example` to `stack.env`:
   ```bash
   cp stack.env.example stack.env
   ```

2. **IMPORTANT**: Generate secure JWT secrets:
   ```bash
   openssl rand -base64 32  # For JWT_SECRET
   openssl rand -base64 32  # For JWT_REFRESH_SECRET
   ```
   Update `JWT_SECRET` and `JWT_REFRESH_SECRET` in `stack.env`.

3. Ensure the config files exist (included in this stack):
   - `config/librechat.yaml` – app config (edit for custom endpoints, UI, etc.)
   - `config/auth.json` – service keys for social login (empty `{}` by default; app can write to it)

4. Generate and set MongoDB and Redis passwords (and JWT secrets if not done in step 2):
   ```bash
   # MongoDB root password
   openssl rand -base64 24
   # Redis password
   openssl rand -base64 24
   ```
   Update `MONGO_INITDB_ROOT_PASSWORD` and `REDIS_PASSWORD` in `stack.env` with the outputs. For JWT secrets (step 2), use `openssl rand -base64 32` for both `JWT_SECRET` and `JWT_REFRESH_SECRET`.

5. (Optional) Configure Ollama connection:
   - If Ollama is on the same Docker network: `OLLAMA_BASE_URL=http://ollama:11434`
   - If Ollama is on host: `OLLAMA_BASE_URL=http://host.docker.internal:11434`

6. (Optional) Configure OpenAI API key if you want to use OpenAI directly:
   ```bash
   OPENAI_API_KEY=sk-your-api-key-here
   ```

7. Start the stack (access via Caddy reverse proxy; no host port by default):
   ```bash
   docker compose --env-file stack.env up -d
   ```

## Usage

Once running, access LibreChat via your Caddy reverse proxy (e.g. `https://librechat.yourdomain.com`).

### Initial Setup

1. Open the web UI at your LibreChat URL (e.g. behind Caddy)
2. Create your first admin account
3. Configure AI providers in Settings
4. Start chatting!

### AI Providers

LibreChat supports:
- **Ollama** (local models) - Recommended for privacy
- **OpenAI** (GPT-3.5, GPT-4, GPT-4o, o1, GPT-5)
- **Anthropic** (Claude)
- **Google** (Gemini)
- **Azure OpenAI**
- **AWS Bedrock**
- **Groq**
- **DeepSeek**
- **Mistral**
- **OpenRouter**
- **And many more...**

Configure providers in Settings → Endpoints after login.

### Key Features

#### Agents & Tools
- Build custom AI agents with no-code interface
- MCP (Model Context Protocol) support
- Agent marketplace
- Share agents with users/groups

#### Code Interpreter
- Secure sandboxed execution
- Supports Python, Node.js, Go, C/C++, Java, PHP, Rust, Fortran
- File upload/download support
- Fully isolated execution

#### Web Search
- Search the internet and inject results into context
- Multiple search providers
- Customizable reranking

#### Image Generation
- DALL-E 3/2
- Stable Diffusion
- Flux
- GPT-Image-1
- Image-to-image editing

#### Artifacts
- Generate React components
- Create HTML pages
- Draw Mermaid diagrams
- All generated in chat

## Configuration

### Connecting to Ollama

If you're running Ollama in another Docker stack:
1. Add Ollama to the same Docker network (`monitor` network)
2. Set `OLLAMA_BASE_URL=http://ollama:11434` in `stack.env`

For shared Ollama backend and one-time setup, see [SHARED-RESOURCES.md](../../documents/SHARED-RESOURCES.md).

### Authentication

- **Registration**: Control with `ALLOW_REGISTRATION` (default: true)
- **Social Login**: Enable Google/Microsoft with respective env vars
- **OAuth2**: Configure in Settings → Authentication
- **LDAP**: Available for enterprise deployments

### Security

- **JWT Secrets**: Must be set for production deployments
- **Passwords**: Change default MongoDB and Redis passwords
- **Domain**: Update `DOMAIN_CLIENT` and `DOMAIN_SERVER` for production

## Troubleshooting

### MongoDB Connection Issues
- Check MongoDB is healthy: `docker ps | grep mongodb`
- Verify credentials match in `stack.env`
- Check MongoDB logs: `docker logs librechat-mongodb`

### Redis Connection Issues
- Check Redis is healthy: `docker ps | grep redis`
- Verify password matches in `stack.env`
- Check Redis logs: `docker logs librechat-redis`

### Ollama Connection Issues
- Verify Ollama is accessible at the configured URL
- Check network connectivity between containers
- Ensure Ollama is running and models are available

### Config / auth.json errors
- Ensure `config/librechat.yaml` and `config/auth.json` exist. The stack ships with minimal defaults; edit `config/librechat.yaml` for custom endpoints and see [LibreChat config docs](https://www.librechat.ai/docs/configuration/librechat_yaml).

### Permission Issues
- Ensure data directories have proper permissions
- Container runs as non-root user

## Advanced Configuration

### Environment Variables

LibreChat supports many environment variables for customization. See the official documentation for a complete list.

### Database Options

While MongoDB is used by default, LibreChat can be configured to use other databases. See documentation for details.

### Config file (`config/librechat.yaml`)

The stack mounts a minimal `librechat.yaml` (v1.3.4). To add custom AI endpoints (Groq, Mistral, OpenRouter, etc.), edit `config/librechat.yaml` and restart. See the [config docs](https://www.librechat.ai/docs/configuration/librechat_yaml) and [example](https://www.librechat.ai/docs/configuration/librechat_yaml/example).

### Reverse Proxy

This stack does not expose host ports; use a reverse proxy (Caddy, Nginx, Traefik) in front of LibreChat.

## Documentation

For more information, visit: https://docs.librechat.ai
