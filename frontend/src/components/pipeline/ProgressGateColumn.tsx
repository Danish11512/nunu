import { memo, useRef, useEffect } from 'react';
import type { ProgressGateEvent, PipelineCycleInfo } from '../../lib/types';
import StatusPill from './shared';

interface Props {
  events: ProgressGateEvent[];
  isRunning: boolean;
  currentCycle?: PipelineCycleInfo | null;
}

function ProgressGateColumnInner({ events, isRunning, currentCycle }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events.length]);

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-hidden flex flex-col h-80">
      <div className="px-3 py-2 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm">⏱ Progress Gate</span>
          <StatusPill isLive={isRunning} />
        </div>
        {currentCycle?.total_candidates_found ? (
          <span className="text-xs text-green-500">🎯 {currentCycle.total_candidates_found} candidates</span>
        ) : null}
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1 text-xs font-mono">
        {events.length === 0 && (
          <div className="text-gray-400 italic p-2">Waiting for progress cycles...</div>
        )}
        {events.map((ev) => (
          <div key={ev.id} className="flex items-center gap-2 p-1 rounded hover:bg-gray-50 dark:hover:bg-gray-750">
            <span className="text-gray-400 shrink-0 w-16">
              {new Date(ev.timestamp).toLocaleTimeString()}
            </span>
            <span className="text-yellow-500 shrink-0">⏱</span>
            <span>
              Checked <strong>{ev.data.events_checked}</strong> events
            </span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

export default memo(ProgressGateColumnInner);
