import { useEffect, useRef } from 'react';
import type { WSMessage } from '../lib/types';
import { registerListener } from '../stores/wsStore';

/** Subscribes a message handler to an app-level WebSocket channel.
 *  Connections are managed by `initialize()` in wsStore — the hook
 *  only registers/unregisters the listener, never opens or closes WS. */
export function useWebSocket<T = unknown>(
  channel: string,
  onMessage: (msg: WSMessage<T>) => void,
) {
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    const unsub = registerListener(channel, (msg) => onMessageRef.current(msg as WSMessage<T>));
    return unsub;
  }, [channel]);
}
