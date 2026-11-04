#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "ingress-admin"
prepare_stack_msg "Set the public URL and session secret before deployment. No host ports are published."
prepare_stack_msg "Optional docker-compose.subnet.yml requires an operator-selected nonoverlapping PAPERCLIP_SUBNET. It is not activated by preparation."
prepare_stack_msg "Optional docker-compose.codex-git.yml builds the pinned release's Codex Git broker workaround. It is not activated by preparation."
prepare_stack_msg "Optional prepare-web-toolchain.sh prepares persistent, versioned Node 26/Chromium, Python, developer checkers and publication scanning tools inside the app container. This wrapper never installs it."
prepare_stack_msg "Optional docker-compose.codex-sandbox.yml permits nested Codex namespaces with a scoped seccomp profile, without privileged mode or added capabilities. It is not activated by preparation."
prepare_stack_end
