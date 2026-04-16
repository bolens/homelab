import type { Metric } from 'web-vitals';
import { onCLS, onFCP, onINP, onLCP, onTTFB } from 'web-vitals';
import { apiUrl } from './apiBase';

type WebVitalsIngestPayload = {
  metric: {
    id: string;
    name: string;
    value: number;
    delta: number;
    rating: string;
    navigationType: string;
  };
  page: {
    path: string;
    href: string;
  };
  capturedAt: string;
};

function toPayload(metric: Metric): WebVitalsIngestPayload {
  const path = typeof window !== 'undefined' ? window.location.pathname : '/';
  const href = typeof window !== 'undefined' ? window.location.href : '';
  return {
    metric: {
      id: metric.id,
      name: metric.name,
      value: metric.value,
      delta: metric.delta,
      rating: metric.rating,
      navigationType: metric.navigationType,
    },
    page: { path, href },
    capturedAt: new Date().toISOString(),
  };
}

function sendMetricToApi(metric: Metric): void {
  const payload = JSON.stringify(toPayload(metric));
  const url = apiUrl('/telemetry/web-vitals');

  if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
    const ok = navigator.sendBeacon(url, new Blob([payload], { type: 'application/json' }));
    if (ok) return;
  }

  void fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: payload,
    keepalive: true,
  }).catch(() => {
    // Metrics are best-effort and should never affect user flows.
  });
}

function sendMetric(metric: Metric): void {
  if (import.meta.env.DEV) {
    console.debug(`[web-vitals] ${metric.name}`, { value: metric.value, rating: metric.rating });
  }
  if (import.meta.env.PROD) {
    sendMetricToApi(metric);
  }
}

/** Registers Core Web Vitals + paint/navigation metrics (dev: console; prod: API ingest). */
export function reportWebVitals(): void {
  onCLS(sendMetric);
  onINP(sendMetric);
  onLCP(sendMetric);
  onFCP(sendMetric);
  onTTFB(sendMetric);
}
