#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_ensure_dir_from_env "MYLAR_WRITER_STATE_PATH" "/srv/mylar/media-writer" require-existing
prepare_stack_msg "Use Mylar's existing media-writer directory on local storage. Both services must use its owner UID. Set writer_state to /mylar-writer in normalizer.json only with the coordination override."
prepare_stack_msg "Back up both applications' state, drain existing upgrades, and deploy matching images before activation. Never remove protocol files or recovery markers while either writer is running."
prepare_stack_msg "Converted metadata follow-up requires matching Mylar first, shared writer coordination, Modern ComicRack tagging, and private mylar.tag_converted opt-in. Existing settings are preserved."
prepare_stack_msg "Publication-aware worker cycles require initialized native correction authority and explicit publication_roots mappings in normalizer.json. Preparation does not initialize authority or enable the worker. Keep prototypes held until complete mutation/handoff and matching-image acceptance."
prepare_stack_end
