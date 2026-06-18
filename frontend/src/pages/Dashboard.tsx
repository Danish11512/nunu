import { useState, useCallback } from 'react';
import { useEvents } from '../hooks/useEvents';
import { useWebSocket } from '../hooks/useWebSocket';
import type { EventSummary } from '../lib/types';

function EventCard({ event }: { event: EventSummary }) {
  const progressColor = event.event_progress_percent >= 65 ? 'bg-green-500' : 'bg-gray-500';
  const candidateBadge = () => {
    if (!event.has_active_candidate) return null;
    if (event.candidate_side === 'yes') return <span className="ml-2 px-2 py-0.5 rounded bg-green-800 text-green-200 text-xs font-semibold">YES</span>;
    if (event.candidate_side === 'no') return <span className="ml-2 px-2 py-0.5 rounded bg-red-800 text-red-200 text-xs font-semibold">NO</span>;
    return <span className="ml-2 px-2 py-0.5 rounded bg-yellow-700 text-yellow-200 text-xs font-semibold">REVIEW</span>;
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-lg font-semibold text-gray-100">{event.event_ticker}</h3>
        {candidateBadge()}
      </div>
      <div className="mb-3">
        <div className="flex justify-between text-xs text-gray-400 mb-1">
          <span>Progress</span>
          <span>{event.event_progress_percent.toFixed(1)}%</span>
        </div>
        <div className="w-full bg-gray-700 rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all duration-500 ${progressColor}`}
            style={{ width: `${Math.min(event.event_progress_percent, 100)}%` }}
          />
        </div>
      </div>
      <div className="space-y-1">
        {event.top_markets.slice(0, 3).map((m) => (
          <div key={m.ticker} className="flex items-center justify-between text-sm">
            <span className="text-gray-300 truncate flex-1">{m.ticker}</span>
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
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [wsConnected, setWsConnected] = useState(false);

  const { data, isLoading, isError, error, refetch } = useEvents();

  useWebSocket<EventSummary>('events', useCallback((msg) => {
    if (msg.type === 'event:updated' || msg.type === 'event:discovered') {
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
  }, []), setWsConnected);

  const displayEvents = events.length > 0 ? events : (data ?? []);

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      <header className="bg-gray-800 border-b border-gray-700 px-6 py-3 flex items-center justify-between">
        <h1 className="text-xl font-bold">Nunu Scanner</h1>
        <div className="flex items-center gap-4 text-sm">
          <span className={`flex items-center gap-1.5 ${wsConnected ? 'text-green-400' : 'text-red-400'}`}>
            <span className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-400' : 'bg-red-400'}`} />
            {wsConnected ? 'Connected' : 'Disconnected'}
          </span>
          <span className="text-gray-400">Mode: <span className="text-blue-300">unknown</span></span>
          <a href="/settings" className="text-blue-400 hover:text-blue-300 underline">Settings</a>
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
            <p className="text-red-200">{(error as Error)?.message ?? 'Failed to load events'}</p>
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
              <EventCard key={event.event_ticker} event={event} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
