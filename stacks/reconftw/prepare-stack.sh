#!/bin/bash
# Create ~/.config/reconftw/, download reconftw.cfg if missing, copy stack.env from example if missing
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
CONFIG_DIR="${RECONFTW_CONFIG_DIR:-$HOME/.config/reconftw}"
mkdir -p "$CONFIG_DIR"
mkdir -p "$CONFIG_DIR/Recon"
if [ ! -f "$CONFIG_DIR/reconftw.cfg" ]; then
  curl -sSL -o "$CONFIG_DIR/reconftw.cfg" https://raw.githubusercontent.com/six2dez/reconftw/main/reconftw.cfg
  echo "Downloaded reconftw.cfg to $CONFIG_DIR/reconftw.cfg"
fi
if [ ! -f stack.env ]; then
  cp stack.env.example stack.env
  echo "Created stack.env from stack.env.example"
fi
