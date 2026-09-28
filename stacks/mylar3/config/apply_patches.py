"""Apply checked native adapters in dependency order; no live configuration access."""

from pathlib import Path
import subprocess
import sys

PATCHES = (
    "patch_ddl_status",
    "patch_ddl_responses",
    "patch_ddl_exhaustion",
    "patch_tagger_timeout",
    "patch_ddl_mirror_retries",
    "patch_diagnostics_api",
    "patch_unnumbered_issues",
    "patch_ddl_resume",
    "patch_ddl_requeue",
    "patch_queue_progress",
    "patch_queue_control",
    "patch_search_cooldown",
    "patch_queue_views",
    "patch_pp_monitor",
    "patch_wide_layout",
    "patch_workflow",
    "patch_ddl_ui",
    "patch_postprocessing",
    "patch_ddl_schedule",
    "patch_series_preservation",
    "patch_pack_intake",
    "patch_database_transactions",
    "patch_file_matching",
    "patch_catalog_volumes",
    "patch_story_arcs",
    "patch_release_calendar",
)


def main(directory):
    for module in PATCHES:
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name(module + ".py")),
                str(directory),
            ],
            check=True,
        )


if __name__ == "__main__":
    main(sys.argv[1])
