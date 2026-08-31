# Trilium

TriliumNext Notes is a self-hosted hierarchical note-taking application with rich text, code blocks, and relation maps.

**Website:** https://triliumnotes.org
**Docs:** https://docs.triliumnotes.org/user-guide/setup/server/installation/docker
**GitHub:** https://github.com/TriliumNext/Trilium

## Usage

Personal knowledge base accessible via web UI on port 8080, proxied through Caddy
on `ingress-public`. Notes are stored in a named Docker volume. Supports desktop
sync clients for offline access.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Ensure the `ingress-public` external Docker network exists before deploying.
3. Optionally set TRILIUM_PORT if you need a port other than 8080.
4. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| TRILIUM_PORT | No | 8080 | Internal port the app listens on |

## Notes

- TZ and locale come from shared.env.
- Data is stored in the `trilium_data` named volume, back it up regularly.
- No host ports are exposed by default; Caddy proxies to `trilium:8080` over the ingress-public network.
- Desktop sync clients connect to your Caddy hostname using a sync password set in the UI.
