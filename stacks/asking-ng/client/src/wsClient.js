// Basic WebSocket client for real-time admin updates
// Usage: import { useAdminWebSocket } from './wsClient';
import { useEffect } from 'react';

export function useAdminWebSocket({ onUserUpdate, onPollUpdate }) {
  useEffect(() => {
    const ws = new window.WebSocket(
      window.location.protocol === 'https:'
        ? 'wss://' + window.location.host + '/ws/admin'
        : 'ws://' + window.location.host + '/ws/admin'
    );
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'user-update' && onUserUpdate) onUserUpdate(msg.data);
        if (msg.type === 'poll-update' && onPollUpdate) onPollUpdate(msg.data);
      } catch (e) {
        // ignore
      }
    };
    return () => ws.close();
  }, [onUserUpdate, onPollUpdate]);
}
