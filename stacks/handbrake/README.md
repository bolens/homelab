# HandBrake

HandBrake is an open-source video transcoder that converts video files between formats and compresses media.

**Website:** https://handbrake.fr
**GitHub:** https://github.com/jlesage/docker-handbrake

## Usage

Used in a homelab to batch-transcode media files via a web-based GUI (jlesage image). Drop files into
the watch folder and HandBrake auto-encodes them to the output folder. Access the UI on port 5800.

## Setup

1. Copy `stack.env.example` to `stack.env` and fill in required values.
2. Set USER_ID/GROUP_ID to match your host user (`id -u && id -g`) so bind-mount paths are writable.
3. Optionally override HANDBRAKE_CONFIG_PATH, HANDBRAKE_WATCH_PATH, HANDBRAKE_OUTPUT_PATH.
4. Deploy: `docker compose up -d`

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| USER_ID | Yes | 1000 | Host UID for file ownership on bind mounts |
| GROUP_ID | Yes | 1000 | Host GID for file ownership on bind mounts |
| UMASK | No | 002 | Umask applied to created files |
| HANDBRAKE_CONFIG_PATH | No | compose default | Host path for HandBrake config directory |
| HANDBRAKE_WATCH_PATH | No | compose default | Host path for auto-watch input folder |
| HANDBRAKE_OUTPUT_PATH | No | compose default | Host path for encoded output files |

## Notes

- TZ and locale come from shared.env; do not duplicate them here.
- The watch folder enables automatic encoding — files placed there are processed and moved to output.
- Web UI is served on port 5800 (VNC-in-browser); no auth by default, restrict via reverse proxy.
