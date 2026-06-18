import { useEffect, useRef, useCallback } from 'react';
import type { WSMessage } from '../lib/types';

export function useWebSocket<T = unknown>(
  channel: string,
  onMessage: (msg: WSMessage<T>) => void,
  onStatusChange?: (connected: boolean) => void,
) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const onMessageRef = useRef(onMessage);
  const onStatusRef = useRef(onStatusChange);
  onMessageRef.current = onMessage;
  onStatusRef.current = onStatusChange;

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}/api/v1/ws/${channel}`;

    const ws = new WebSocket(url);
    ws.onopen = () => onStatusRef.current?.(true);
    ws.onmessage = (event) => {
      const msg: WSMessage<T> = JSON.parse(event.data);
      onMessageRef.current(msg);
    };
    ws.onclose = () => {
      onStatusRef.current?.(false);
      reconnectTimer.current = window.setTimeout(connect, 3000);
    };
    ws.onerror = () => { ws.close(); };
    wsRef.current = ws;
  }, [channel]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      clearTimeout(reconnectTimer.current);
    };
  }, [connect]);

  return { ws: wsRef };
}
