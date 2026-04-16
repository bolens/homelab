export function presentPollsMineResponse(payload: {
  polls: Record<string, unknown>[];
  total: number;
  limit: number;
  offset: number;
}): Record<string, unknown> {
  return payload;
}
