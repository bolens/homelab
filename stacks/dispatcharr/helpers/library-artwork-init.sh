#!/usr/bin/env bash
set -euo pipefail
/dispatcharrpy/bin/python /opt/dispatcharr-library-artwork.py
exec /app/docker/entrypoint.sh "$@"
