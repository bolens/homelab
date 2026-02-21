# Perplexica Stack

Privacy-focused AI-powered answering engine that combines web search with AI models for accurate, cited answers.

## Features

- **Privacy-First**: Runs entirely on your hardware
- **Smart Search Modes**: Speed, Balanced, or Quality modes
- **Multiple Sources**: Web, discussions, academic papers
- **Widgets**: Weather, calculations, stock prices, and more
- **File Uploads**: Upload documents and ask questions
- **Image/Video Search**: Visual content search
- **Search History**: All searches saved locally

## Setup

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Set your data path (absolute path recommended):
   ```bash
   PERPLEXICA_DATA_PATH=/path/to/perplexica/data
   ```

3. Configure Ollama connection:
   - If Ollama is on the same Docker network: `OLLAMA_BASE_URL=http://ollama:11434`
   - If Ollama is on host: `OLLAMA_BASE_URL=http://host.docker.internal:11434`

4. (Optional) If you have an external SearxNG instance:
   ```bash
   SEARXNG_API_URL=http://searxng:8080
   ```
   Leave empty to use the bundled SearxNG (recommended).

5. Start the stack:
   ```bash
   docker compose up -d
   ```

## Usage

Once running, Perplexica will be available at `http://localhost:3000`.

### Initial Setup

1. Open the web UI at `http://localhost:3000`
2. Configure your AI provider settings (API keys, models, etc.)
3. Start searching!

### AI Providers

Perplexica supports:
- **Local LLMs**: Ollama (recommended for privacy)
- **Cloud Providers**: OpenAI, Anthropic Claude, Google Gemini, Groq, and more

Configure providers in the settings screen after first launch.

### Search Modes

- **Speed Mode**: Quick answers for simple queries
- **Balanced Mode**: Good balance of speed and quality
- **Quality Mode**: Deep research with comprehensive results

### Using with External SearxNG

If you have a SearxNG instance running elsewhere:

1. Ensure SearxNG has JSON format enabled
2. Ensure Wolfram Alpha search engine is enabled in SearxNG
3. Set `SEARXNG_API_URL` in `.env` to your SearxNG instance URL

## Configuration

### Connecting to Ollama

If you're running Ollama in another Docker stack:
1. Add Ollama to the same Docker network (`monitor` network)
2. Set `OLLAMA_BASE_URL=http://ollama:11434` in `.env`

### Data Storage

Perplexica data (including search history) is stored in `PERPLEXICA_DATA_PATH`.

## Troubleshooting

### SearxNG Connection Issues
- Verify SearxNG is accessible at the configured URL
- Check that JSON format is enabled in SearxNG settings
- Ensure Wolfram Alpha engine is enabled

### Ollama Connection Issues
- Verify Ollama is accessible at the configured URL
- Check network connectivity between containers
- Ensure Ollama is running and models are available

### Port Conflicts
- Change `PERPLEXICA_HOST_PORT` in `.env` if port 3000 is already in use

## Documentation

For more information, visit: https://github.com/ItzCrazyKns/Perplexica
