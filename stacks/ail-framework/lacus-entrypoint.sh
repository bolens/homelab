#!/bin/sh
set -eu

cd /app/lacus/cache
./run_redis.sh

cd /app/lacus
exec /usr/bin/supervisord -c /etc/supervisor/supervisord.conf
