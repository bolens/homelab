#!/bin/sh
set -eu

owner="${PUID:-1000}:${PGID:-1000}"

for path in /config/nzb /config/queue /config/tmp /config/scripts; do
    mkdir -p "$path"
    chown "$owner" "$path"
done

find /config -maxdepth 1 -type f -name 'nzbget*.log' -exec chown "$owner" {} +
