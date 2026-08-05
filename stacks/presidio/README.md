# Presidio

Microsoft Presidio is a data protection and PII detection/anonymization API for text and images.

**Website:** https://microsoft.github.io/presidio/
**GitHub:** https://github.com/microsoft/presidio

## Usage

Presidio exposes REST API services: the anonymizer (port 5001) strips PII from text, and the
image-redactor (port 5003) redacts PII from images. The APIs run on `security-research` and `ingress-admin`
and are consumed by other stacks (e.g. document pipelines, AI integrations) rather than end users.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Ensure the `security-research` and `ingress-admin` Docker networks exist before deploying.
3. If using Ollama for NER, set `OLLAMA_HOST` to match the Ollama service address.
4. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| OLLAMA_HOST | No | http://ollama:11434 | Ollama base URL for NER-based PII detection |

## Notes

- No web UI; services are API-only (REST/JSON).
- Research tools reach the APIs through `security-research`; Caddy reaches them through `ingress-admin`.
- TZ and locale are provided by `shared.env`, not `stack.env`.
- Worker count is pinned to 1 by default; increase `WORKERS` in compose environment for throughput.
