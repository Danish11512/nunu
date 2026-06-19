import { memo, useRef, useEffect } from 'react';
import type { DiscoveryEvent } from '../../lib/types';
import StatusPill from './shared';

interface Props {
  events: DiscoveryEvent[];
  isRunning: boolean;
}

function DiscoveryColumnInner({ events, isRunning }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events.length]);

  const lastTime = events.length > 0 ? events[events.length - 1]?.timestamp : null;
  const age = lastTime
    ? `${Math.round((Date.now() - new Date(lastTime).getTime()) / 1000)}s ago`
    : '—';

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-hidden flex flex-col h-80">
      <div className="px-3 py-2 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm">🔍 Discovery</span>
          <StatusPill isLive={isRunning} />
        </div>
        <span className="text-xs text-gray-400">{age}</span>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1 text-xs font-mono">
        {events.length === 0 && (
          <div className="text-gray-400 italic p-2">Waiting for discovery cycles...</div>
        )}
        {events.map((ev) => (
          <div key={ev.id} className="flex items-center gap-2 p-1 rounded hover:bg-gray-50 dark:hover:bg-gray-750">
            <span className="text-gray-400 shrink-0 w-16">{new Date(ev.timestamp).toLocaleTimeString()}</span>
            <span className="text-blue-500 shrink-0">🔍</span>
            <span>
              <strong>{ev.data.total_markets}</strong> markets · <strong>{ev.data.total_events}</strong> events
              <span className="text-green-500"> +{ev.data.added}</span>
              <span className="text-red-500"> −{ev.data.removed}</span>
            </span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

export default memo(DiscoveryColumnInner);
