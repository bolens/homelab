#!/bin/bash
# Create stack.env from example if missing; ensure config dir has vhost.conf and proxy-https-fix.php; create .env from YOURLS_IMAGE for compose
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
if [ ! -f stack.env ]; then
  cp stack.env.example stack.env
  echo "Created stack.env from stack.env.example"
fi
CONFIG_DIR="${HOME:-/tmp}/.config/yourls"
if [ -f stack.env ]; then
  val=$(grep -E '^YOURLS_CONFIG_DIR=' stack.env 2>/dev/null | cut -d= -f2-)
  [ -n "$val" ] && CONFIG_DIR="$val"
fi
mkdir -p "$CONFIG_DIR"
if [ ! -f "$CONFIG_DIR/vhost.conf" ]; then
  cp vhost.conf.example "$CONFIG_DIR/vhost.conf"
  echo "Created $CONFIG_DIR/vhost.conf from vhost.conf.example"
fi
if [ ! -f "$CONFIG_DIR/proxy-https-fix.php" ]; then
  cp proxy-https-fix.php.example "$CONFIG_DIR/proxy-https-fix.php"
  echo "Created $CONFIG_DIR/proxy-https-fix.php from proxy-https-fix.php.example"
fi
if [ -f stack.env ] && grep -q "^YOURLS_IMAGE=" stack.env; then
  grep "^YOURLS_IMAGE=" stack.env > .env
  echo "Updated .env from YOURLS_IMAGE in stack.env"
fi
