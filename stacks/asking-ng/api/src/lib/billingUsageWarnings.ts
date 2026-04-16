/** Threshold labels for UI (aligned with MONETIZATION 80%/95% guidance). */
export type BillingMeterWarningCode = '80' | '95';

export type BillingUsageWarnings = {
  activePolls?: BillingMeterWarningCode;
  votesThisMonth?: BillingMeterWarningCode;
  dataExports?: BillingMeterWarningCode;
};

function meterWarning(cur: number, max: number): BillingMeterWarningCode | undefined {
  if (max <= 0 || max >= Number.MAX_SAFE_INTEGER / 2) return undefined;
  const r = cur / max;
  if (r >= 0.95) return '95';
  if (r >= 0.8) return '80';
  return undefined;
}

export function buildBillingUsageWarnings(args: {
  activePolls: number;
  maxActivePolls: number;
  votesThisMonth: number;
  maxVotesPerMonth: number;
  exportsToday: number;
  maxExportsPerDay: number;
}): BillingUsageWarnings | undefined {
  const out: BillingUsageWarnings = {};
  const ap = meterWarning(args.activePolls, args.maxActivePolls);
  if (ap) out.activePolls = ap;
  const vm = meterWarning(args.votesThisMonth, args.maxVotesPerMonth);
  if (vm) out.votesThisMonth = vm;
  const ex = meterWarning(args.exportsToday, args.maxExportsPerDay);
  if (ex) out.dataExports = ex;
  return Object.keys(out).length > 0 ? out : undefined;
}
