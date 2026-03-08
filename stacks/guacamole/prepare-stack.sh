#!/bin/bash
# Create stack.env from example if missing; ensure ~/.config/guacamole has guacamole.properties (from example).
# Set POSTGRES_PASSWORD in stack.env before first run.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
if [ ! -f stack.env ]; then
  cp stack.env.example stack.env
  echo "Created stack.env from stack.env.example — set POSTGRES_PASSWORD (e.g. openssl rand -hex 32) before first deploy"
else
  echo "stack.env already exists"
fi
CONFIG_DIR="${GUACAMOLE_CONFIG_PATH:-${HOME:-/tmp}/.config/guacamole}"
if [ -f stack.env ]; then
  val=$(grep -E '^GUACAMOLE_CONFIG_PATH=' stack.env 2>/dev/null | cut -d= -f2-)
  [ -n "$val" ] && CONFIG_DIR="$val"
fi
mkdir -p "$CONFIG_DIR"
if [ -f "$CONFIG_DIR/guacamole.properties" ]; then
  echo "Config already present at $CONFIG_DIR/guacamole.properties"
else
  cp guacamole.properties.example "$CONFIG_DIR/guacamole.properties"
  echo "Created $CONFIG_DIR/guacamole.properties from guacamole.properties.example (GUACAMOLE-2127 workaround)"
fi
