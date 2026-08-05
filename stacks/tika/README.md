# Apache Tika

Apache Tika is a content detection and extraction toolkit that parses text and metadata from hundreds of file types.

**Website:** https://tika.apache.org
**GitHub:** https://github.com/apache/tika

## Usage

Tika exposes a REST API for extracting text and metadata from documents, PDFs, images, and more.
It is typically consumed by other stacks (e.g. search indexers, AI pipelines) rather than end users directly.
No web UI; interact via HTTP API calls to the Tika server port.

## Setup

1. Copy `stack.env.example` to `stack.env` (no required values beyond TZ).
2. Run `./prepare-stack.sh` to prepare local files.
3. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| TZ | No | America/New_York | Container timezone |

## Notes

- Tika can be memory-intensive when parsing large or complex documents; set a memory limit in compose.
- The default Tika server port is 9998.
- The API is internal-only on the shared `ingress-public` network; no host port or
  public Caddy route is created.
- The `latest-full` image includes OCR and additional parsers. Change to
  `apache/tika:latest` when the smaller core image is sufficient.
