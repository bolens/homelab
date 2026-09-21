#!/bin/sh
# Called only by the successful-backup hook in the local repository override.
set -eu

keep_last=${LOCAL_KEEP_LAST:-3}
keep_daily=${LOCAL_KEEP_DAILY:-7}
keep_weekly=${LOCAL_KEEP_WEEKLY:-4}
keep_monthly=${LOCAL_KEEP_MONTHLY:-3}
for count in "$keep_last" "$keep_daily" "$keep_weekly" "$keep_monthly"; do
    case "$count" in
        ''|*[!0-9]*) echo "Retention counts must be positive integers" >&2; exit 1 ;;
    esac
    if [ "$count" -lt 1 ]; then
        echo "Retention counts must be positive integers" >&2
        exit 1
    fi
done

# Use an explicit local target so this hook cannot prune the old S3 repository.
# Group by source paths because container recreation changes its hostname.
restic --repo /repository forget --group-by paths \
    --keep-last "$keep_last" --keep-daily "$keep_daily" \
    --keep-weekly "$keep_weekly" --keep-monthly "$keep_monthly"

# Prune at most weekly, after a successful backup. A failed prune leaves the
# timestamp unchanged and will be retried after the next successful backup.
stamp=/cache/local-retention-last-prune
now=$(date +%s)
last=0
if [ -f "$stamp" ]; then
    read -r last < "$stamp" || last=0
fi
case "$last" in ''|*[!0-9]*) last=0 ;; esac
if [ "$now" -lt "$last" ] || [ "$((now - last))" -ge 604800 ]; then
    restic --repo /repository prune --max-repack-size 1G --max-unused 5%
    printf '%s\n' "$now" > "$stamp"
fi

# Report capacity pressure through the success hook's maintenance heartbeat.
# Run this after retention so a low-space warning never prevents cleanup.
free_percent=$(df -Pk /repository | awk 'NR == 2 { print int(100 * $4 / $2) }')
if [ -z "$free_percent" ] || [ "$free_percent" -lt 20 ]; then
    echo "Backup disk free space is below 20% or could not be measured" >&2
    exit 1
fi
