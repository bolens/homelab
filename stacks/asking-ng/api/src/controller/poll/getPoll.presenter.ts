export function presentPollResponse(data: Record<string, unknown>): Record<string, unknown> {
  return {
    status: 'success',
    data,
  };
}
