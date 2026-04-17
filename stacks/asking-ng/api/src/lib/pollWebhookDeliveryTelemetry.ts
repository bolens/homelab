type PollWebhookDeliveryTelemetryKind =
  | 'attempted'
  | 'delivered_ok'
  | 'delivered_non_2xx'
  | 'delivery_failed'
  | 'shed';

type PollWebhookDeliveryMinuteBucket = Record<PollWebhookDeliveryTelemetryKind, number>;

export type PollWebhookDeliveryTelemetrySnapshot = {
  window_minutes: number;
  as_of_ms: number;
  attempted: number;
  delivered_ok: number;
  delivered_non_2xx: number;
  delivery_failed: number;
  shed: number;
  current_minute_attempted: number;
  current_minute_shed: number;
};

const buckets = new Map<number, PollWebhookDeliveryMinuteBucket>();
const RETENTION_MINUTES = 120;

function utcMinuteEpoch(ms: number): number {
  return Math.floor(ms / 60_000);
}

function emptyBucket(): PollWebhookDeliveryMinuteBucket {
  return {
    attempted: 0,
    delivered_ok: 0,
    delivered_non_2xx: 0,
    delivery_failed: 0,
    shed: 0,
  };
}

function pruneBuckets(nowMinute: number): void {
  for (const minute of buckets.keys()) {
    if (minute < nowMinute - RETENTION_MINUTES) buckets.delete(minute);
  }
}

export function recordPollWebhookDeliveryTelemetry(kind: PollWebhookDeliveryTelemetryKind): void {
  const nowMinute = utcMinuteEpoch(Date.now());
  pruneBuckets(nowMinute);
  const bucket = buckets.get(nowMinute) ?? emptyBucket();
  bucket[kind] += 1;
  buckets.set(nowMinute, bucket);
}

export function readPollWebhookDeliveryTelemetry(
  windowMinutes = 15,
): PollWebhookDeliveryTelemetrySnapshot {
  const safeWindow = Math.max(1, Math.min(RETENTION_MINUTES, Math.floor(windowMinutes) || 15));
  const asOfMs = Date.now();
  const nowMinute = utcMinuteEpoch(asOfMs);
  pruneBuckets(nowMinute);

  const total = emptyBucket();
  for (let minute = nowMinute - safeWindow + 1; minute <= nowMinute; minute += 1) {
    const bucket = buckets.get(minute);
    if (!bucket) continue;
    total.attempted += bucket.attempted;
    total.delivered_ok += bucket.delivered_ok;
    total.delivered_non_2xx += bucket.delivered_non_2xx;
    total.delivery_failed += bucket.delivery_failed;
    total.shed += bucket.shed;
  }

  const currentMinute = buckets.get(nowMinute) ?? emptyBucket();
  return {
    window_minutes: safeWindow,
    as_of_ms: asOfMs,
    attempted: total.attempted,
    delivered_ok: total.delivered_ok,
    delivered_non_2xx: total.delivered_non_2xx,
    delivery_failed: total.delivery_failed,
    shed: total.shed,
    current_minute_attempted: currentMinute.attempted,
    current_minute_shed: currentMinute.shed,
  };
}

export function resetPollWebhookDeliveryTelemetryForTests(): void {
  buckets.clear();
}
