"""Run in Dispatcharr's installed Django runtime, using the native models.

Called by the host runner through a scoped docker exec. Never prints credentials.
"""

import json
import os
import subprocess
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.channels.models import (
    Channel, ChannelGroup, ChannelProfile, ChannelProfileMembership, Recording,
    RecurringRecordingRule,
)
from apps.epg.models import EPGSource, ProgramData
from apps.plugins.models import PluginConfig


def snapshot(config):
    if ChannelProfile.objects.filter(name__in=config["protected_profiles"]).count() != len(
        config["protected_profiles"]
    ):
        raise RuntimeError("Protected channel profile is missing or renamed")
    protected = set(ChannelProfileMembership.objects.filter(
        channel_profile__name__in=config["protected_profiles"], enabled=True,
    ).values_list("channel_id", flat=True))
    protected.update(Recording.objects.values_list("channel_id", flat=True))
    protected.update(RecurringRecordingRule.objects.values_list("channel_id", flat=True))
    rows = []
    for channel in Channel.objects.select_related("channel_group").prefetch_related("streams"):
        group = channel.channel_group.name if channel.channel_group else ""
        rows.append({
            "id": channel.id, "uuid": str(channel.uuid), "name": channel.name,
            "group_id": channel.channel_group_id,
            "stream_ids": [stream.id for stream in channel.streams.all()],
            "protected": channel.id in protected or group.startswith("Local news - "),
        })
    progress_path = Path("/data/iptv_checker_progress.json")
    result_path = Path("/data/iptv_checker_results.json")
    progress = json.loads(progress_path.read_text()) if progress_path.exists() else {}
    results = json.loads(result_path.read_text()) if result_path.exists() else []
    now = timezone.now()
    failed_recordings = sum(
        (record.custom_properties or {}).get("status") in {"failed", "error"}
        for record in Recording.objects.filter(end_time__gte=now-timedelta(days=1))
    )
    return {
        "channels": rows, "results": results, "progress": progress,
        "guides": [{"id": source.id, "status": source.status,
                    "updated_at": source.updated_at.timestamp(),
                    "interval": source.refresh_interval}
                   for source in EPGSource.objects.filter(is_active=True, source_type="xmltv")],
        "current_programs": ProgramData.objects.filter(end_time__gt=now).count(),
        "failed_recordings": failed_recordings,
    }


def library_guide(config):
    """Bounded read-only DTO for the optional ErsatzTV correctness observer."""
    now = timezone.now()
    finish = now + timedelta(hours=int(config["hours"]) + 1)
    channels = Channel.objects.filter(streams__m3u_account_id=config["account_id"]).distinct()
    bindings = [{"uuid": str(c.uuid), "output_number": format(c.channel_number, "g"),
                 "guide_id": str(c.epg_data.tvg_id) if c.epg_data else ""}
                for c in channels.select_related("epg_data")]
    rows = ProgramData.objects.filter(epg__epg_source_id=config["source_id"],
                                     end_time__gt=now, start_time__lt=finish).values_list(
        "epg__tvg_id", "start_time", "end_time", "title", "sub_title")
    return {"bindings": bindings,
            "programmes": [[str(key), int(start.timestamp()), int(end.timestamp()), title, subtitle]
                           for key, start, end, title, subtitle in rows],
            "recordings": Recording.objects.filter(end_time__gt=now).count()}


def apply(config):
    # Re-evaluate protection at mutation time, not only from the prior snapshot.
    protected = {row["uuid"] for row in snapshot(config)["channels"] if row["protected"]}
    counts = {"quarantine": 0, "restore": 0, "delete": 0}
    with transaction.atomic():
        for action in config["actions"]:
            channel = Channel.objects.select_for_update().filter(uuid=action["uuid"]).first()
            if not channel:
                continue
            kind = action["kind"]
            if kind != "restore" and str(channel.uuid) in protected:
                kind = "restore"
            if kind == "delete" and (
                not channel.channel_group or channel.channel_group.name != "IPTV quarantine"
            ):
                continue
            if kind == "delete":
                channel.delete()
            elif kind == "quarantine":
                group, _ = ChannelGroup.objects.get_or_create(name="IPTV quarantine")
                channel.channel_group = group
                channel.name = action["original_name"][:235] + " [Unavailable]"
                channel.save(update_fields=["channel_group", "name"])
            elif kind == "restore":
                original = action["original_group_id"]
                if original is None or ChannelGroup.objects.filter(id=original).exists():
                    channel.channel_group_id = original
                channel.name = action["original_name"]
                channel.save(update_fields=["channel_group", "name"])
            else:
                raise ValueError("Unknown quarantine action")
            counts[kind] += 1
    return counts


def backup(config):
    database = settings.DATABASES["default"]
    env = os.environ.copy()
    env["PGPASSWORD"] = database["PASSWORD"]
    args = ["-h", database.get("HOST") or "localhost", "-U", database["USER"]]
    name = "iptv_restore_" + str(os.getpid())
    dump = Path("/tmp/iptv-maintenance-" + str(os.getpid()) + ".dump")
    try:
        with dump.open("wb") as output:
            subprocess.run(["pg_dump", *args, "-Fc", database["NAME"]],
                           env=env, stdout=output, stderr=subprocess.PIPE, check=True, timeout=90)
        dump.chmod(0o600)
        subprocess.run(["createdb", *args, name], env=env, capture_output=True,
                       check=True, timeout=30)
        try:
            subprocess.run(["pg_restore", *args, "--no-owner", "--no-privileges", "-d", name,
                            str(dump)], env=env, capture_output=True, check=True, timeout=90)
            import psycopg
            with psycopg.connect(dbname=name, host=database.get("HOST") or "localhost",
                                user=database["USER"], password=database["PASSWORD"]) as db:
                with db.cursor() as cur:
                    # Compare selected dump rows with the live source only when counts
                    # remain stable. A concurrently edited catalog refuses verification.
                    for model in [Channel, Recording, EPGSource, PluginConfig]:
                        cur.execute("SELECT COUNT(*) FROM " + model._meta.db_table)
                        if cur.fetchone()[0] != model.objects.count():
                            raise RuntimeError("Concurrent catalog change during backup")
        finally:
            subprocess.run(["dropdb", *args, name], env=env, capture_output=True,
                           check=True, timeout=30)
        return {"verified": True, "dump": str(dump), "channels": Channel.objects.count()}
    except BaseException:
        dump.unlink(missing_ok=True)
        raise


config = json.loads(os.environ["IPTV_MAINTENANCE_INPUT"])
mode = config.pop("mode")
result = {"snapshot": snapshot, "apply": apply, "backup": backup,
          "library_guide": library_guide}[mode](config)
print("IPTV_MAINTENANCE " + json.dumps(result, default=str))
