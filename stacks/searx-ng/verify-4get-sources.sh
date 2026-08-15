#!/usr/bin/env bash
set -euo pipefail

_expected_hijacker="${FOURGET_HIJACKED_REVISION:?Set FOURGET_HIJACKED_REVISION}"
_expected_fourget="${FOURGET_REVISION:?Set FOURGET_REVISION}"
_hijacker_path="${FOURGET_HIJACKED_SOURCE_PATH:?Set FOURGET_HIJACKED_SOURCE_PATH}"
_fourget_path="${FOURGET_SOURCE_PATH:?Set FOURGET_SOURCE_PATH}"

verify_checkout() {
  local _name="$1"
  local _path="$2"
  local _expected="$3"
  local _actual

  if [[ ! -d "$_path/.git" ]]; then
    printf 'ERROR: %s is not a Git checkout: %s\n' "$_name" "$_path" >&2
    return 1
  fi

  _actual="$(git -C "$_path" rev-parse HEAD)"
  if [[ "$_actual" != "$_expected" ]]; then
    printf 'ERROR: %s revision is %s; expected %s\n' "$_name" "$_actual" "$_expected" >&2
    return 1
  fi

  if [[ -n "$(git -C "$_path" status --short)" ]]; then
    printf 'ERROR: %s checkout has uncommitted changes: %s\n' "$_name" "$_path" >&2
    return 1
  fi

  printf 'verified %s at %s\n' "$_name" "$_actual"
}

verify_checkout "4get-hijacked" "$_hijacker_path" "$_expected_hijacker"
verify_checkout "4get" "$_fourget_path" "$_expected_fourget"
