#!/usr/bin/env bash
# Summarize read-model reconcile trend logs from asking-api.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

WINDOW="${1:-24h}"
OUT_DIR="${STACK_DIR}/artifacts/reconcile-trends"
TIMESTAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
OUT_FILE="${OUT_DIR}/reconcile-trend-report-${TIMESTAMP}.json"

mkdir -p "${OUT_DIR}"

docker compose \
  -f "${STACK_DIR}/docker-compose.yml" \
  logs --since "${WINDOW}" asking-api \
  | node -e "
const fs = require('node:fs');
const lines = fs.readFileSync(0, 'utf8').split('\n');
let total = 0;
let alerts = 0;
let maxMismatchCount = 0;
let maxDiffTotalVotes = 0;
let maxDiffVotesLast1m = 0;
let maxDiffVotesLast24h = 0;
let maxDiffQuarantinedVotesPending = 0;
for (const raw of lines) {
  const idx = raw.indexOf('{');
  if (idx < 0) continue;
  const payload = raw.slice(idx);
  let entry;
  try {
    entry = JSON.parse(payload);
  } catch {
    continue;
  }
  if (entry?.event !== 'read_model.reconcile.summary') continue;
  total += 1;
  const mismatchCount = Number(entry.mismatchCount) || 0;
  const alert = entry.alert === true;
  const diffTotalVotes = Number(entry.maxDiffTotalVotes) || 0;
  const diffVotesLast1m = Number(entry.maxDiffVotesLast1m) || 0;
  const diffVotesLast24h = Number(entry.maxDiffVotesLast24h) || 0;
  const diffQuarantinedVotesPending = Number(entry.maxDiffQuarantinedVotesPending) || 0;
  if (alert) alerts += 1;
  if (mismatchCount > maxMismatchCount) maxMismatchCount = mismatchCount;
  if (diffTotalVotes > maxDiffTotalVotes) maxDiffTotalVotes = diffTotalVotes;
  if (diffVotesLast1m > maxDiffVotesLast1m) maxDiffVotesLast1m = diffVotesLast1m;
  if (diffVotesLast24h > maxDiffVotesLast24h) maxDiffVotesLast24h = diffVotesLast24h;
  if (diffQuarantinedVotesPending > maxDiffQuarantinedVotesPending) {
    maxDiffQuarantinedVotesPending = diffQuarantinedVotesPending;
  }
}
const report = {
  generated_at: new Date().toISOString(),
  window: process.argv[1],
  samples: total,
  alert_samples: alerts,
  alert_rate_pct: total > 0 ? Number(((alerts / total) * 100).toFixed(2)) : 0,
  max_mismatch_count: maxMismatchCount,
  max_diff_total_votes: maxDiffTotalVotes,
  max_diff_votes_last_1m: maxDiffVotesLast1m,
  max_diff_votes_last_24h: maxDiffVotesLast24h,
  max_diff_quarantined_votes_pending: maxDiffQuarantinedVotesPending,
};
process.stdout.write(JSON.stringify(report, null, 2) + '\n');
" "${WINDOW}" > "${OUT_FILE}"

echo "Wrote reconcile trend report: ${OUT_FILE}"
