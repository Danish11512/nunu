import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useEvents } from '../hooks/useEvents';
import { useWebSocket } from '../hooks/useWebSocket';
import { useWSStore, getPriceTimestamp, getEventTimestamp } from '../stores/wsStore';
import { useScannerConfig } from '../hooks/useScannerConfig';
import ProgressBar from '../components/ProgressBar';
import Badge from '../components/Badge';
import { ROUTES } from '../lib/routes';
import type { EventSummary } from '../lib/types';

function ageStr(ts: number | null): string | null {
  if (ts === null) return null;
  const sec = Math.floor((Date.now() - ts) / 1000);
  if (sec < 0) return '0s';
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m`;
  return `${Math.floor(min / 60)}h`;
}

function LastRefreshPill({ lastTs }: { lastTs: number | null }) {
  const [sec, setSec] = useState(() => lastTs ? Math.floor((Date.now() - lastTs) / 1000) : 0);
  useEffect(() => {
    if (!lastTs) { setSec(0); return; }
    const tick = () => setSec(Math.floor((Date.now() - lastTs) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [lastTs]);
  if (!lastTs) return null;
  const fresh = sec < 30;
  const bg = fresh ? 'bg-purple-900 text-purple-200' : 'bg-amber-900 text-amber-200';
  const ago = sec < 60 ? `${sec}s` : sec < 3600 ? `${Math.floor(sec / 60)}m` : `${Math.floor(sec / 3600)}h`;
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-mono ${bg}`} title={`Data · ${ago} ago`}>
      {ago}
    </span>
  );
}

function EventCard({ event, lastPriceTs }: { event: EventSummary; lastPriceTs: number | null }) {
  const progressColor = event.event_progress_percent >= 65 ? 'green' : 'gray';
  const candidateBadge = () => {
    if (!event.has_active_candidate) return null;
    if (event.candidate_side === 'yes') return <Badge variant="yes" label="YES" />;
    if (event.candidate_side === 'no') return <Badge variant="no" label="NO" />;
    return <Badge variant="tie" label="REVIEW" />;
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-lg font-semibold text-gray-100">{event.event_sub_title || event.event_title || event.event_ticker}</h3>
        <div className="flex items-center gap-2">
          <LastRefreshPill lastTs={lastPriceTs} />
          {candidateBadge()}
        </div>
      </div>
      <div className="mb-3">
        <div className="flex justify-between text-xs text-gray-400 mb-1">
          <span>Progress</span>
        </div>
        <ProgressBar percent={event.event_progress_percent} color={progressColor} size="sm" decimals={1} />
      </div>
      <div className="space-y-1">
        {event.top_markets.slice(0, 3).map((m) => (
          <div key={m.ticker} className="flex items-center justify-between text-sm">
            <span className="text-gray-300 truncate flex-1">{m.title || m.ticker}</span>
            <span className="text-green-400 font-mono ml-2">{m.yes_bid?.toFixed(2) ?? '-'}</span>
            <span className="text-gray-500 mx-1">/</span>
            <span className="text-red-400 font-mono">{m.no_bid?.toFixed(2) ?? '-'}</span>
            <span className="text-gray-500 ml-2 text-xs">{m.total_resting_order_quantity}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [events, setEvents] = useState<EventSummary[]>([]);
  const wsConnected = useWSStore((s) => s.connectedChannels.events ?? false);
  const setPriceTimestamp = useWSStore((s) => s.setPriceTimestamp);
  const setEventTimestamp = useWSStore((s) => s.setEventTimestamp);

  const { data, isLoading, isError, error, refetch } = useEvents();
  const { config } = useScannerConfig();
  const currentMode = config.data?.mode ?? 'unknown';

  useWebSocket<EventSummary>('events', useCallback((msg) => {
    if (msg.type === 'event:updated' || msg.type === 'event:discovered') {
      const ts = new Date(msg.timestamp).getTime();
      if (!isNaN(ts)) setEventTimestamp(msg.data.event_ticker, ts);
      setEvents((prev) => {
        const idx = prev.findIndex((e) => e.event_ticker === msg.data.event_ticker);
        if (idx >= 0) {
          const next = [...prev];
          next[idx] = msg.data;
          return next;
        }
        return [...prev, msg.data];
      });
    }
    if (msg.type === 'event:removed') {
      const removed = msg.data as { event_ticker: string };
      setEvents((prev) => prev.filter((e) => e.event_ticker !== removed.event_ticker));
    }
  }, [setEventTimestamp]));

  const displayEvents = events.length > 0 ? events : (data ?? []);

  // ── price age: track latest WS price:changed timestamp ──
  const [lastPriceTs, setLastPriceTs] = useState<number | null>(null);

  useWebSocket<{ ticker: string; timestamp: string }>('prices', useCallback((msg) => {
    if (msg.type === 'price:changed') {
      const ts = new Date(msg.data.timestamp ?? msg.timestamp).getTime();
      if (!isNaN(ts)) {
        setLastPriceTs((prev) => (prev === null || ts > prev) ? ts : prev);
        setPriceTimestamp(msg.data.ticker, ts);
      }
    }
  }, [setPriceTimestamp]));

  // Global price-age pill in header
  const [globalAgeLabel, setGlobalAgeLabel] = useState<string | null>(null);
  useEffect(() => {
    setGlobalAgeLabel(ageStr(lastPriceTs));
    const id = setInterval(() => setGlobalAgeLabel(ageStr(lastPriceTs)), 1000);
    return () => clearInterval(id);
  }, [lastPriceTs]);

  // Per-event age: most recent timestamp across its event refresh + price updates
  // Uses Zustand store (survives HMR and route changes) + MarketSummary fallback.
  function eventAgeTs(event: EventSummary): number | null {
    let youngest: number | null = null;
    // Check event-level refresh timestamp (from event:updated WS messages in store)
    const eventTs = getEventTimestamp(event.event_ticker);
    if (eventTs !== undefined && (youngest === null || eventTs > youngest)) youngest = eventTs;
    // Check per-market price timestamps (from price:changed WS messages in store)
    for (const m of event.top_markets) {
      const ts = getPriceTimestamp(m.ticker);
      if (ts !== undefined && (youngest === null || ts > youngest)) youngest = ts;
      // Fallback: use last_price_update from the MarketSummary REST data
      if (youngest === null && m.last_price_update) {
        const restTs = new Date(m.last_price_update).getTime();
        if (!isNaN(restTs)) youngest = restTs;
      }
    }
    return youngest;
  }

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      <header className="bg-gray-800 border-b border-gray-700 px-6 py-3 flex items-center justify-between">
        <h1 className="text-xl font-bold">Nunu Scanner</h1>
        <div className="flex items-center gap-4 text-sm">
          <span className={`flex items-center gap-1.5 ${wsConnected ? 'text-green-400' : 'text-red-400'}`}>
            <span className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-400' : 'bg-red-400'}`} />
            {wsConnected ? 'Connected' : 'Disconnected'}
          </span>
          <span className="text-gray-400">Mode: <span className="text-blue-300">{currentMode}</span></span>
          {globalAgeLabel && (
            <span className="text-xs px-2 py-0.5 rounded-full font-mono bg-blue-900 text-blue-200">
              Prices {globalAgeLabel} ago
            </span>
          )}
          <button onClick={() => navigate(ROUTES.SETTINGS)} className="text-blue-400 hover:text-blue-300 underline bg-transparent border-none cursor-pointer">Settings</button>
        </div>
      </header>

      <main className="p-6">
        {isLoading && (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
            <span className="ml-3 text-gray-400">Loading events...</span>
          </div>
        )}

        {isError && (
          <div className="bg-red-900/50 border border-red-700 rounded-lg p-4 mb-4">
            <p className="text-red-200">{error?.message ?? 'Failed to load events'}</p>
            <button
              onClick={() => refetch()}
              className="mt-2 px-4 py-1.5 bg-red-700 hover:bg-red-600 text-white rounded text-sm"
            >
              Retry
            </button>
          </div>
        )}

        {!isLoading && !isError && displayEvents.length === 0 && (
          <div className="flex flex-col items-center justify-center h-64 text-gray-500">
            <p className="text-lg">No same-day-live events found</p>
            <p className="text-sm mt-1">Events will appear here once the scanner discovers them</p>
          </div>
        )}

        {!isLoading && !isError && displayEvents.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {displayEvents.map((event) => (
              <EventCard key={event.event_ticker} event={event} lastPriceTs={eventAgeTs(event)} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
