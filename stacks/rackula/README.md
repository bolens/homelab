# Rackula

Rackula is a static site generator that turns a Rack-compatible Ruby app into a static website.

**GitHub:** https://github.com/socketry/rackula

## Usage

Rackula is a CLI tool run to generate static output from a Rack app; it is not a persistent service.
Use `docker compose run` to invoke the generator against your app source and produce static files.
No web UI or reverse proxy is needed.

## Setup

1. Copy `stack.env.example` to `stack.env` and review the source/output paths.
2. Run `./prepare-stack.sh` to prepare local files.
3. Build once with `docker compose build rackula`.
4. Run: `docker compose run --rm rackula <arguments>`.

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| RACKULA_SOURCE_PATH | No | ~/dev/rackula-source | Read-only Rack application source |
| RACKULA_OUTPUT_PATH | No | ~/dev/rackula-output | Generated static output |

## Notes

- Primarily useful as a one-shot CLI generator; not a long-running service.
- Networking is disabled for the generation job.
