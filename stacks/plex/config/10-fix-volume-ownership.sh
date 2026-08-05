#!/bin/sh
set -eu

owner="${PUID:-1000}:${PGID:-1000}"

chown "$owner" /transcode
chmod u+rwx /transcode
