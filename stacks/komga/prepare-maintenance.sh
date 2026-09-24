#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_ensure_dir_from_env "MYLAR_COMPLETED_PATH" "${MEDIA_ROOT:-/srv/media}/downloads/usenet/completed/comics" require-existing
prepare_stack_ensure_dir_from_env "MYLAR_DDL_CACHE_PATH" "/srv/mylar/cache" require-existing
prepare_stack_msg "Run prepare-normalizer.sh too. Enable maintenance in normalizer.json only after configuring Mylar and the completed-download mount."
prepare_stack_end
