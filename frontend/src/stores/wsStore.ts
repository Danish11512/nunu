import { create } from 'zustand';
import type { WSMessage } from '../lib/types';

const PING_INTERVAL_MS = 30_000;

// ── Module-level (non-serializable) state ──
// These live outside Zustand because WebSocket / timer objects don't belong in
// a reactive store. The store only exposes the reactive derived state (connection
// status) that React components care about.
const sockets = new Map<string, WebSocket>();
const listeners = new Map<string, Set<(msg: WSMessage) => void>>();
const reconnectTimers = new Map<string, ReturnType<typeof setTimeout>>();
let pingTimer: ReturnType<typeof setInterval> | null = null;

// ── Reactive store ──

interface WSStore {
  connectedChannels: Record<string, boolean>;
  /** Last price:changed timestamp (epoch ms) per market ticker */
  priceTimestamps: Record<string, number>;
  /** Last event:updated timestamp (epoch ms) per event ticker */
  eventTimestamps: Record<string, number>;
  setPriceTimestamp: (ticker: string, ts: number) => void;
  setEventTimestamp: (eventTicker: string, ts: number) => void;
}

const useWSStore = create<WSStore>((set) => ({
  connectedChannels: {},
  priceTimestamps: {},
  eventTimestamps: {},
  setPriceTimestamp: (ticker, ts) =>
    set((s) => ({ priceTimestamps: { ...s.priceTimestamps, [ticker]: ts } })),
  setEventTimestamp: (eventTicker, ts) =>
    set((s) => ({ eventTimestamps: { ...s.eventTimestamps, [eventTicker]: ts } })),
}));

// ── Ping ──

function ensurePing() {
  if (pingTimer) return;
  pingTimer = setInterval(() => {
    for (const ws of sockets.values()) {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    }
  }, PING_INTERVAL_MS);
}

// ── Connect / Disconnect ──

export function connect(channel: string, onClose?: () => void) {
  if (sockets.has(channel)) return;

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  const url = `${protocol}//${host}/api/v1/ws/${channel}`;

  const ws = new WebSocket(url);

  ws.onopen = () => {
    useWSStore.setState((s) => ({
      connectedChannels: { ...s.connectedChannels, [channel]: true },
    }));
  };

  ws.onmessage = (event) => {
    let msg: WSMessage;
    try {
      msg = JSON.parse(event.data);
    } catch (e) {
      return;
    }
    if (msg.type === 'pong') return;
    const cbs = listeners.get(channel);
    if (cbs) {
      cbs.forEach(cb => {
        try { cb(msg); } catch (e) { console.warn(`WS listener error on ${channel}:`, e); }
      });
    }
  };

  ws.onclose = () => {
    useWSStore.setState((s) => ({
      connectedChannels: { ...s.connectedChannels, [channel]: false },
    }));
    sockets.delete(channel);
    onClose?.();
  };

  ws.onerror = () => {
    ws.close();
  };

  sockets.set(channel, ws);
  ensurePing();
}

export function disconnect(channel: string) {
  cancelReconnect(channel);

  const ws = sockets.get(channel);
  if (ws) {
    ws.onclose = null;
    ws.close();
    sockets.delete(channel);
    useWSStore.setState((s) => ({
      connectedChannels: { ...s.connectedChannels, [channel]: false },
    }));
  }
}

// ── Reconnect ──

/** Reconnect logic: creates a fresh connection whose onclose will re-invoke
 *  `scheduleReconnect` to keep the cycle alive. Cancel the timer (or
 *  disconnect the socket) to break the cycle on unmount.
 *  Call this from a `connect()` onClose callback. */
export function scheduleReconnect(channel: string) {
  cancelReconnect(channel);
  const timer = setTimeout(() => {
    reconnectTimers.delete(channel);
    connect(channel, () => scheduleReconnect(channel));
  }, 3000);
  reconnectTimers.set(channel, timer);
}

export function cancelReconnect(channel: string) {
  const timer = reconnectTimers.get(channel);
  if (timer) {
    clearTimeout(timer);
    reconnectTimers.delete(channel);
  }
}

// ── Listeners ──

export function registerListener(channel: string, cb: (msg: WSMessage) => void): () => void {
  if (!listeners.has(channel)) {
    listeners.set(channel, new Set());
  }
  listeners.get(channel)!.add(cb);
  return () => { listeners.get(channel)?.delete(cb); };
}

export function unregisterListener(channel: string) {
  listeners.delete(channel);
}

// ── App-level initialization ──

const WS_CHANNELS = ['scanner', 'events', 'candidates', 'trades', 'prices'] as const;
let initialized = false;

/** Pre-connect all WS channels at app startup. After this, hooks only
 *  register listeners — the connections are already established. */
export function initialize() {
  if (initialized) return;
  initialized = true;
  for (const channel of WS_CHANNELS) {
    connect(channel, () => scheduleReconnect(channel));
  }
}

export { useWSStore };

// ── Timestamp getters (non-reactive — read latest values without subscribing) ──

/** Last price:changed timestamp for a ticker (epoch ms), or undefined. */
export function getPriceTimestamp(ticker: string): number | undefined {
  return useWSStore.getState().priceTimestamps[ticker];
}

/** Last event:updated timestamp for an event ticker (epoch ms), or undefined. */
export function getEventTimestamp(eventTicker: string): number | undefined {
  return useWSStore.getState().eventTimestamps[eventTicker];
}
