#!/bin/sh
set -eu

owner="${PUID:-1000}:${PGID:-1000}"

chown "$owner" /cache
chmod u+rwx /cache
