# OpenGist

OpenGist is a self-hosted Gist service backed by Git, providing paste/snippet sharing with syntax highlighting.

**Website:** https://opengist.io
**GitHub:** https://github.com/thomiceli/opengist

## Usage

Provides a GitHub Gist-compatible web UI for creating and sharing code snippets stored as real Git
repositories. Typically proxied through Caddy on the dedicated `ingress-public` network. Supports public and private
snippets with OAuth login.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Set OPENGIST_CONFIG_DIR_ON_HOST to an absolute path on your host for the config bind mount.
3. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| PUID | Yes | 1000 | Host UID for bind-mount file ownership |
| PGID | Yes | 1000 | Host GID for bind-mount file ownership |
| OPENGIST_CONFIG_DIR | No | /config | Container path for OpenGist config directory |
| OPENGIST_CONFIG_DIR_ON_HOST | Yes | /home/youruser/.config/opengist | Host path for config bind mount |

## Notes

- TZ and locale come from shared.env.
- OAuth providers (GitHub, Gitea, etc.) are configured in opengist.yml inside the config directory.
- SSH git access requires exposing port 2222 (or host 22) in the compose file.
