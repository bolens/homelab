#!/usr/bin/env bash
set -euo pipefail

echo "==> Prometheus jobs/targets smoke check"
python - <<'PY'
import json
import subprocess
import sys

def get_json(cmd):
    raw = subprocess.check_output(cmd, text=True)
    return json.loads(raw)

targets = get_json(["docker", "exec", "prometheus", "wget", "-qO-", "http://localhost:9090/api/v1/targets?state=active"])
rules = get_json(["docker", "exec", "prometheus", "wget", "-qO-", "http://localhost:9090/api/v1/rules"])

active_targets = targets.get("data", {}).get("activeTargets", [])
jobs_present = {t.get("labels", {}).get("job") for t in active_targets}

required_jobs = {
    "prometheus",
    "blackbox_public",
    "blackbox_http_paths_public",
    "alloy",
    "loki",
    "promtail",
}

missing_jobs = sorted(j for j in required_jobs if j not in jobs_present)
if missing_jobs:
    print("ERROR missing active jobs:", ", ".join(missing_jobs))
    sys.exit(1)

rule_names = set()
for g in rules.get("data", {}).get("groups", []):
    for r in g.get("rules", []):
        name = r.get("name")
        if name:
            rule_names.add(name)

required_rules = {
    "BlackboxRootCriticalDown",
    "BlackboxPathCriticalDown",
    "BlackboxAvailabilitySloCritical",
    "BlackboxAvailabilityBurnRateCritical",
    "BlackboxPublicTargetMissing",
    "BlackboxPathTargetMissing",
}

missing_rules = sorted(r for r in required_rules if r not in rule_names)
if missing_rules:
    print("ERROR missing loaded rules:", ", ".join(missing_rules))
    sys.exit(1)

print("OK required jobs present:", ", ".join(sorted(required_jobs)))
print("OK required rules present:", ", ".join(sorted(required_rules)))
PY

echo "==> Alertmanager readiness smoke check"
docker exec alertmanager wget -qO- http://localhost:9093/-/ready >/dev/null
echo "OK alertmanager ready"

echo "==> Loki LogQL alert-query smoke check"
python - <<'PY'
import json
import os
import subprocess
import sys
from urllib.parse import quote

LOKI_CONTAINER = os.environ.get("LOKI_CONTAINER", "loki")
LOKI_QUERY_WINDOW = os.environ.get("LOKI_QUERY_WINDOW", "15m")
LOKI_ENFORCE_THRESHOLDS = os.environ.get("LOKI_ENFORCE_THRESHOLDS", "0") == "1"

fallback_threshold = int(os.environ.get("LOKI_FALLBACK_THRESHOLD", "20"))
reconcile_threshold = int(os.environ.get("LOKI_RECONCILE_THRESHOLD", "0"))
http_5xx_threshold = int(os.environ.get("LOKI_HTTP_5XX_THRESHOLD", "10"))
llm_threshold = int(os.environ.get("LOKI_LLM_UPSTREAM_THRESHOLD", "5"))

def query_loki(expr: str) -> dict:
    encoded = quote(expr, safe="")
    url = f"http://localhost:3100/loki/api/v1/query?query={encoded}"
    raw = subprocess.check_output(
        ["docker", "exec", LOKI_CONTAINER, "wget", "-qO-", url],
        text=True,
    )
    payload = json.loads(raw)
    if payload.get("status") != "success":
        raise RuntimeError(f"Loki query failed for: {expr}")
    return payload

def value_as_float(payload: dict) -> float:
    data = payload.get("data", {})
    result_type = data.get("resultType")
    result = data.get("result", [])
    if result_type != "vector" or not result:
        return 0.0
    # Prometheus/Loki scalar samples are [timestamp, "value"].
    first = result[0].get("value", [0, "0"])
    return float(first[1])

checks = [
    (
        "fallback_burst",
        (
            "sum(count_over_time("
            "{service=\"asking-ng-api\"} | json | "
            "event=~\"poll.read_model.*_fallback|admin.read_model.*_fallback\" "
            f"[{LOKI_QUERY_WINDOW}]"
            "))"
        ),
        fallback_threshold,
    ),
    (
        "reconcile_alert_presence",
        (
            "sum(count_over_time("
            "{service=\"asking-ng-api\"} | json | event=\"read_model.reconcile.alert\" "
            f"[{LOKI_QUERY_WINDOW}]"
            "))"
        ),
        reconcile_threshold,
    ),
    (
        "http_5xx",
        (
            "sum(count_over_time("
            "{service=\"asking-ng-api\"} | json | event=\"http.error\" | statusCode >= 500 "
            "[5m]"
            "))"
        ),
        http_5xx_threshold,
    ),
    (
        "llm_upstream_errors",
        (
            "sum(count_over_time("
            "{service=\"asking-ng-api\"} | json | "
            "event=~\"llm.models.upstream_error|llm.chat.upstream_error\" "
            "[10m]"
            "))"
        ),
        llm_threshold,
    ),
]

for name, expr, threshold in checks:
    payload = query_loki(expr)
    value = value_as_float(payload)
    print(f"OK {name}: value={value:.0f} threshold={threshold} query_valid=true")
    if LOKI_ENFORCE_THRESHOLDS and value > threshold:
        print(
            f"ERROR {name}: value {value:.0f} exceeds threshold {threshold} "
            f"(set by env, enforcement enabled)"
        )
        sys.exit(1)

print("OK Loki LogQL smoke checks passed")
PY

echo "Monitoring smoke check passed."
