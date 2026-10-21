"""Pure channel quarantine policy. No application, filesystem or network access."""

from datetime import datetime, timezone


def decide(channels, results, previous, observed_at, minimum_days=14, failed_days=3):
    """Only complete, independent failed checks can admit deletion.

    A channel is not dead when any current alternate is untested or skipped.
    The caller supplies a completed check's original timestamp, never poll time.
    """
    stamp = datetime.fromtimestamp(observed_at, timezone.utc)
    today = stamp.date().isoformat()
    history = {key: dict(value) for key, value in previous.items()}
    grouped = {}
    for row in results:
        grouped.setdefault(row.get("channel_id"), []).append(row)
    actions = []
    for channel in channels:
        key = channel["uuid"]
        rows = grouped.get(channel["id"], [])
        if channel["protected"]:
            # Protection also rescues a channel quarantined before it was protected.
            if key in history:
                actions.append({"kind": "restore", "uuid": key, **history.pop(key)})
            continue
        current = set(channel["stream_ids"])
        checked = {row.get("stream_id") for row in rows}
        if any(row.get("status") == "Alive" for row in rows):
            if key in history:
                actions.append({"kind": "restore", "uuid": key, **history.pop(key)})
            continue
        if not current or not current.issubset(checked):
            continue
        considered = [row for row in rows if row.get("stream_id") in current]
        if not considered or not all(
            row.get("status") == "Dead"
            and row.get("error_type") not in {"Cancelled", "RateLimit", "Skipped"}
            for row in considered
        ):
            continue
        entry = history.setdefault(key, {
            "original_name": channel["name"],
            "original_group_id": channel["group_id"],
            "first_failure": observed_at,
            "failed_dates": [],
        })
        entry["failed_dates"] = sorted(set(entry["failed_dates"]) | {today})
        elapsed = observed_at - entry["first_failure"]
        kind = "delete" if (
            elapsed >= minimum_days * 86400 and len(entry["failed_dates"]) >= failed_days
        ) else "quarantine"
        actions.append({"kind": kind, "uuid": key, **entry})
    return history, actions


def source_unhealthy(status, updated_at, now, interval_hours):
    return status not in {"success", "idle"} or not updated_at or (
        now - updated_at > max(18, interval_hours * 3) * 3600
    )
