# AFFiNE

AFFiNE is a self-hosted collaborative knowledge workspace combining docs, whiteboards, and a knowledge graph in one app.

**Website:** https://affine.pro
**Docs:** https://docs.affine.pro/self-host-affine
**GitHub:** https://github.com/toeverything/AFFiNE

## Usage

Accessed via browser through a Caddy reverse proxy on the monitor network. Serves as an all-in-one Notion/Miro alternative for personal or team knowledge management. No port is exposed directly; Caddy proxies to affine:3010.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Set AFFINE_SERVER_EXTERNAL_URL to your public hostname in stack.env.
3. Ensure the external Docker network `monitor` exists before deploying.
4. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| AFFINE_SERVER_EXTERNAL_URL | No | — | Public URL for callbacks and generated links |

## Notes

- The monitor network must be created externally: `docker network create monitor`.
- Data is persisted in the affine_data named volume at /root/.affine inside the container.
- First-run setup happens in the browser on initial visit.
