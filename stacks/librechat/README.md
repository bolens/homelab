# LibreChat Stack

Enhanced ChatGPT Clone with support for multiple AI providers, agents, MCP, code interpreter, and more.

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

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. **IMPORTANT**: Generate secure JWT secrets:
   ```bash
   openssl rand -base64 32  # For JWT_SECRET
   openssl rand -base64 32  # For JWT_REFRESH_SECRET
   ```
   Update `JWT_SECRET` and `JWT_REFRESH_SECRET` in `.env`.

3. Set your data paths (absolute paths recommended):
   ```bash
   MONGODB_DATA_PATH=/path/to/mongodb/data
   REDIS_DATA_PATH=/path/to/redis/data
   LIBRECHAT_DATA_PATH=/path/to/librechat/data
   ```

4. Generate and set MongoDB and Redis passwords (and JWT secrets if not done in step 2):
   ```bash
   # MongoDB root password
   openssl rand -base64 24
   # Redis password
   openssl rand -base64 24
   ```
   Update `MONGO_INITDB_ROOT_PASSWORD` and `REDIS_PASSWORD` in `.env` with the outputs. For JWT secrets (step 2), use `openssl rand -base64 32` for both `JWT_SECRET` and `JWT_REFRESH_SECRET`.

5. Configure Ollama connection:
   - If Ollama is on the same Docker network: `OLLAMA_BASE_URL=http://ollama:11434`
   - If Ollama is on host: `OLLAMA_BASE_URL=http://host.docker.internal:11434`

6. (Optional) Configure OpenAI API key if you want to use OpenAI directly:
   ```bash
   OPENAI_API_KEY=sk-your-api-key-here
   ```

7. Start the stack:
   ```bash
   docker compose up -d
   ```

## Usage

Once running, LibreChat will be available at `http://localhost:3080`.

### Initial Setup

1. Open the web UI at `http://localhost:3080`
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
2. Set `OLLAMA_BASE_URL=http://ollama:11434` in `.env`

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
- Verify credentials match in `.env`
- Check MongoDB logs: `docker logs librechat-mongodb`

### Redis Connection Issues
- Check Redis is healthy: `docker ps | grep redis`
- Verify password matches in `.env`
- Check Redis logs: `docker logs librechat-redis`

### Ollama Connection Issues
- Verify Ollama is accessible at the configured URL
- Check network connectivity between containers
- Ensure Ollama is running and models are available

### Port Conflicts
- Change ports in `.env` if conflicts occur:
  - `LIBRECHAT_HOST_PORT` (default: 3080)
  - `MONGODB_HOST_PORT` (default: 27017)
  - `REDIS_HOST_PORT` (default: 6379)

### Permission Issues
- Ensure data directories have proper permissions
- Container runs as non-root user

## Advanced Configuration

### Environment Variables

LibreChat supports many environment variables for customization. See the official documentation for a complete list.

### Database Options

While MongoDB is used by default, LibreChat can be configured to use other databases. See documentation for details.

### Reverse Proxy

For production deployments, use a reverse proxy (Caddy, Nginx, Traefik) in front of LibreChat.

## Documentation

For more information, visit: https://docs.librechat.ai
