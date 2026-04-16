export function presentModerateVoteBatch(payload: {
  action: string;
  selector: string;
  selectorValue: string;
  reasonCode: string;
  affectedCount: number;
}): Record<string, unknown> {
  return {
    status: 'success',
    data: {
      action: payload.action,
      selector: payload.selector,
      selector_value: payload.selectorValue,
      reason_code: payload.reasonCode,
      affected_count: payload.affectedCount,
    },
  };
}
