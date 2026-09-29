#!/usr/bin/env bash
set -euo pipefail
_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"
prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_copy_caddy
prepare_stack_ensure_docker_network "media-automation"
prepare_stack_ensure_docker_network "ingress-admin"
prepare_stack_ensure_docker_network "torrents"
prepare_stack_ensure_docker_network "usenet"
prepare_stack_ensure_dir_from_env "MYLAR3_MEDIA_PATH" "${MEDIA_ROOT:-/srv/media}" require-existing
prepare_stack_msg "Configure Activity intake and optional handoff settings in Mylar. Back up its complete config volume, including workflow.sqlite. Deploy Mylar before the maintenance worker. Enable pack verification only with matching worker pack_import enabled."
prepare_stack_msg "Legacy ComicTagger remains default; Modern is an experimental CBZ ComicRack opt-in in settings. Mylar startup owns media-writer protocol creation; configure the matching normalizer coordination override separately and preserve pending recovery markers."
prepare_stack_msg "DDL discovery defaults to Requests; optional Curl is selected in Mylar settings. Archive transfers stay on Requests. No extra runtime preparation is needed."
prepare_stack_msg "Converted metadata follow-up requires matching Mylar first, shared writer coordination, Modern ComicRack tagging, and private mylar.tag_converted opt-in. Existing settings are preserved."
prepare_stack_end
