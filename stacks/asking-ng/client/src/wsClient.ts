import { useEffect } from 'react';
import ReconnectingWebSocket from 'reconnecting-websocket';

type AdminWebSocketHandlers = {
  onUserUpdate?: (data: unknown) => void;
  onPollUpdate?: (data: unknown) => void;
};

function adminWebSocketUrl(): string {
  const host = typeof window !== 'undefined' ? window.location.host : '';
  const isSecure = typeof window !== 'undefined' && window.location.protocol === 'https:';
  return isSecure ? `wss://${host}/ws/admin` : `ws://${host}/ws/admin`;
}

/** Basic WebSocket client for real-time admin updates (optional backend feature). */
export function useAdminWebSocket({ onUserUpdate, onPollUpdate }: AdminWebSocketHandlers): void {
  useEffect(() => {
    if (typeof window === 'undefined' || typeof WebSocket === 'undefined') return;

    let ws: ReconnectingWebSocket;
    try {
      ws = new ReconnectingWebSocket(adminWebSocketUrl(), [], {
        WebSocket,
        minReconnectionDelay: 1000,
        maxReconnectionDelay: 10_000,
        reconnectionDelayGrowFactor: 1.5,
        connectionTimeout: 4000,
      });
    } catch {
      return;
    }

    ws.onmessage = (event: MessageEvent<string>) => {
      try {
        const msg = JSON.parse(event.data) as { type?: string; data?: unknown };
        if (msg.type === 'user-update' && onUserUpdate) onUserUpdate(msg.data);
        if (msg.type === 'poll-update' && onPollUpdate) onPollUpdate(msg.data);
      } catch {
        // ignore malformed payloads
      }
    };

    return () => {
      try {
        ws.close(1000, 'component unmount');
      } catch {
        /* already closed */
      }
    };
  }, [onUserUpdate, onPollUpdate]);
}
