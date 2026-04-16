type CounterKey = string;

const counters = new Map<CounterKey, number>();
const startedAtMs = Date.now();
let asyncQueueDepth = 0;

function inc(key: CounterKey, by = 1): void {
  counters.set(key, (counters.get(key) || 0) + by);
}

function metricName(input: string): string {
  return input.replace(/[^a-zA-Z0-9_:]/g, '_');
}

function labels(input: Record<string, string | number>): string {
  const parts = Object.entries(input).map(([k, v]) => `${k}="${String(v).replace(/"/g, '\\"')}"`);
  return parts.length ? `{${parts.join(',')}}` : '';
}

export function observeHttpRequest(args: { route: string; method: string; statusCode: number }): void {
  inc('asking_ng_http_requests_total');
  inc(
    `asking_ng_http_requests_by_route_total${labels({
      route: args.route || 'unknown',
      method: args.method.toUpperCase(),
      status: args.statusCode,
    })}`,
  );
  if (args.statusCode >= 500) inc('asking_ng_http_errors_5xx_total');
  else if (args.statusCode >= 400) inc('asking_ng_http_errors_4xx_total');
}

export function observeIntegrationEvent(name: string): void {
  inc(`asking_ng_integrations_events_total${labels({ event: metricName(name) })}`);
}

export function observeIntegrationDelivery(args: {
  sink: 'notify' | 'audit' | 'error';
  outcome: 'ok' | 'non_2xx' | 'timeout' | 'error' | 'skipped_open';
}): void {
  inc(
    `asking_ng_integrations_delivery_total${labels({
      sink: args.sink,
      outcome: args.outcome,
    })}`,
  );
}

export function setAsyncQueueDepth(depth: number): void {
  asyncQueueDepth = Math.max(0, Math.floor(depth));
}

export function observeAsyncJobDrop(category: string): void {
  inc(`asking_ng_async_job_dropped_total${labels({ category: metricName(category) })}`);
}

export function renderPrometheusMetrics(): string {
  const lines: string[] = [];
  lines.push('# HELP asking_ng_process_uptime_seconds Process uptime in seconds.');
  lines.push('# TYPE asking_ng_process_uptime_seconds gauge');
  lines.push(`asking_ng_process_uptime_seconds ${Math.floor((Date.now() - startedAtMs) / 1000)}`);
  lines.push('# HELP asking_ng_async_queue_depth Current async job queue depth.');
  lines.push('# TYPE asking_ng_async_queue_depth gauge');
  lines.push(`asking_ng_async_queue_depth ${asyncQueueDepth}`);

  for (const [key, value] of counters.entries()) {
    const typeLineKey = key.split('{')[0] || key;
    lines.push(`# TYPE ${typeLineKey} counter`);
    lines.push(`${key} ${value}`);
  }
  return `${lines.join('\n')}\n`;
}
