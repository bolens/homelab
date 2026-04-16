import type { QueryClient } from '@tanstack/react-query';

/**
 * React Query key conventions:
 * - Namespace by feature first (`poll`, `admin`, `public`, `llm`, `profile`).
 * - Keep stable segment order from broad -> specific.
 * - Put optional filters/identifiers at the tail.
 * - Prefer helper functions over inline array literals in pages.
 */

export function pollQueryKey(id: string, embedToken: string, trackingKey = '') {
  return ['poll', id, embedToken || '', trackingKey] as const;
}

export function pollHeatmapQueryKey(id: string, embedToken: string, trackingKey = '') {
  return ['poll-heatmap', id, embedToken || '', trackingKey] as const;
}

export function pollReplayQueryKey(id: string, embedToken: string, trackingKey = '') {
  return ['poll-replay', id, embedToken || '', trackingKey] as const;
}

export function invalidatePollQueries(
  qc: QueryClient,
  id: string,
  embedToken: string,
  trackingKey = '',
): void {
  void qc.invalidateQueries({ queryKey: pollQueryKey(id, embedToken, trackingKey) });
  void qc.invalidateQueries({ queryKey: pollHeatmapQueryKey(id, embedToken, trackingKey) });
  void qc.invalidateQueries({ queryKey: pollReplayQueryKey(id, embedToken, trackingKey) });
}

export function mineQueryKey(jwt: string) {
  return ['poll', 'mine', jwt] as const;
}

export function mineQueryPrefix() {
  return ['poll', 'mine'] as const;
}

export function quarantineQueryKey(
  pollId: string,
  queueStatus: 'pending' | 'approved' | 'rejected' | 'all',
  jwt: string,
) {
  return ['poll', pollId, 'quarantine', queueStatus, jwt] as const;
}

export function adminStatusDashboardQueryKey() {
  return ['admin', 'status', 'dashboard'] as const;
}

export function adminStatusQueryKey() {
  return ['admin', 'status'] as const;
}

export function adminPollsQueryKey() {
  return ['admin', 'polls'] as const;
}

export function adminUsersQueryKey() {
  return ['admin', 'users'] as const;
}

export function invalidateAdminOverviewQueries(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: adminStatusDashboardQueryKey() });
  void queryClient.invalidateQueries({ queryKey: adminStatusQueryKey() });
  void queryClient.invalidateQueries({ queryKey: adminPollsQueryKey() });
  void queryClient.invalidateQueries({ queryKey: adminUsersQueryKey() });
}

export function adminVoteGeoQueryKey() {
  return ['admin', 'vote-geo'] as const;
}

export function publicInfoQueryKey() {
  return ['public', 'info'] as const;
}

export function publicHealthcheckQueryKey() {
  return ['public', 'healthcheck'] as const;
}

export function publicReadyQueryKey() {
  return ['public', 'ready'] as const;
}

export function adminDashboardReadyProbeQueryKey() {
  return ['public', 'ready', 'dashboard'] as const;
}

export function invalidateAdminStatusSurfaceQueries(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: adminStatusQueryKey() });
  void queryClient.invalidateQueries({ queryKey: adminVoteGeoQueryKey() });
}

export function publicStatusHealthcheckQueryKey() {
  return ['public-status', 'healthcheck'] as const;
}

export function publicStatusReadyQueryKey() {
  return ['public-status', 'ready'] as const;
}

export function publicStatusInfoQueryKey() {
  return ['public-status', 'info'] as const;
}

export function publicStatusHistoryQueryKey() {
  return ['public-status', 'history'] as const;
}

export function invalidatePublicStatusQueries(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: publicStatusHealthcheckQueryKey() });
  void queryClient.invalidateQueries({ queryKey: publicStatusReadyQueryKey() });
  void queryClient.invalidateQueries({ queryKey: publicStatusInfoQueryKey() });
  void queryClient.invalidateQueries({ queryKey: publicStatusHistoryQueryKey() });
}

export function profileLlmGatewayTokenQueryKey(userJwt: string) {
  return ['profile', 'llmGatewayToken', userJwt] as const;
}

export function profileBillingQueryKey(userJwt: string) {
  return ['profile', 'billing', userJwt] as const;
}

export function llmStatusQueryKey(gatewayToken: string) {
  return ['llm', 'status', gatewayToken] as const;
}

export function llmModelsQueryKey(gatewayToken: string) {
  return ['llm', 'models', gatewayToken] as const;
}

export function invalidateDeveloperLlmQueries(
  queryClient: QueryClient,
  userJwt: string,
  gatewayToken: string,
): void {
  if (userJwt) {
    void queryClient.invalidateQueries({ queryKey: profileLlmGatewayTokenQueryKey(userJwt) });
    void queryClient.invalidateQueries({ queryKey: profileBillingQueryKey(userJwt) });
  }
  void queryClient.invalidateQueries({ queryKey: llmStatusQueryKey(gatewayToken) });
  void queryClient.invalidateQueries({ queryKey: llmModelsQueryKey(gatewayToken) });
}

export function pollResultsQueryKey(id: string, embedToken: string) {
  return ['poll-results', id, embedToken] as const;
}

export function adminAuditLogsQueryKey(
  action: string,
  actor: string,
  target: string,
  start: string,
  end: string,
  limit: string,
) {
  return ['admin', 'audit-logs', action, actor, target, start, end, limit] as const;
}
