# auto-identity-remove

Local LLM-powered PII redaction service. Accepts document uploads and returns
redacted PDFs with personal information blacked out. Runs entirely on-prem, no
data leaves the host.

Upstream: https://github.com/stephenlthorn/auto-identity-remove
Image:    stephenlthorn/auto-identity-remove:latest
License:  MIT

## Supported formats

PDF, DOCX, XLSX, XLS, PPTX, DOC, PPT, ODT, ODS, ODP, RTF, TXT

## Requirements

- NVIDIA GPU with 8 GB+ VRAM (16 GB recommended)
- NVIDIA Container Toolkit installed on the host
- 16 GB RAM minimum (32 GB recommended)
- Ollama running with a compatible model (llama3.2 default)

## Setup

    cp stack.env.example stack.env
    # Edit stack.env, set OLLAMA_MODEL and confirm OLLAMA_HOST
    docker compose up -d

First start pulls the image (large, CUDA base + baked-in Ollama model).

## API

Swagger UI:   http://localhost:5000/docs (or via Caddy at auto-identity-remove.home)
Redact a doc: POST /redact   (multipart/form-data, field: file)

    curl -X POST http://localhost:5000/redact \
      -F "file=@/path/to/document.pdf" \
      -o redacted.pdf

## Ollama integration

By default OLLAMA_HOST points to the shared ollama stack (http://ollama:11434).
The upstream image also has Ollama baked in, to use it instead set:

    OLLAMA_HOST=http://localhost:11434

and remove the extra_hosts block from docker-compose.yml.

## Volumes

  air_output, redacted PDFs written here; mounted at /app/output inside the container

## Notes

- The service is internal-only by default; caddy_snippet.conf.example has no public block.
- Temporary upload files are cleaned up after each job (stored in /app/uploads inside container, not volume-mounted).
