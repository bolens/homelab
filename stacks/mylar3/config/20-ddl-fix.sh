#!/bin/sh
set -eu
python3 /opt/mylar3-fixes/patch_ddl.py /app/mylar3/mylar
python3 /opt/mylar3-fixes/patch_workers.py /app/mylar3/mylar
python3 /opt/mylar3-fixes/patch_health.py /app/mylar3/mylar
python3 /opt/mylar3-fixes/patch_integrity.py /app/mylar3/mylar
python3 /opt/mylar3-fixes/patch_queue_progress.py /app/mylar3/mylar
python3 /opt/mylar3-fixes/patch_queue_control.py /app/mylar3/mylar
python3 /opt/mylar3-fixes/patch_queue_views.py /app/mylar3/mylar
python3 /opt/mylar3-fixes/patch_pp_monitor.py /app/mylar3/mylar
python3 /opt/mylar3-fixes/patch_wide_layout.py /app/mylar3/mylar
