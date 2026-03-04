#!/usr/bin/env bash
# Print the repo directory layout (portainer/, stacks/<name>/, documents/, .gitignore).
# Run from the docker/ repo root. Use this to regenerate or verify the layout in README.
set -e
cd "$(dirname "$0")/.."
echo 'docker/'
echo '├── portainer/          # Portainer stack'
echo '├── stacks/'
shopt -s nullglob
stacks=( stacks/*/ )
n=${#stacks[@]}
for i in "${!stacks[@]}"; do
  name=$(basename "${stacks[i]}")
  if (( i == n - 1 )); then
    echo "│   └── ${name}/"
  else
    echo "│   ├── ${name}/"
  fi
done
echo '├── documents/          # ENV-VARS.md, ACCESS-SSO.md, other guides'
echo '└── .gitignore          # Excludes .env, config.yml, Caddyfile, etc.'
