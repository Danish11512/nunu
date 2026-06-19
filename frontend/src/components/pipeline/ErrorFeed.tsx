import { memo, useMemo, useRef, useEffect } from 'react';
import type { PipelineCycleInfo, ApiTraceInfo } from '../../lib/types';

interface Props {
  completedCycles: PipelineCycleInfo[];
  apiTraces: ApiTraceInfo[];
}

interface ErrorEntry {
  id: number;
  timestamp: string;
  source: 'stage' | 'cycle' | 'api';
  message: string;
  detail?: unknown;
}

function ErrorFeedInner({ completedCycles, apiTraces }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  const errors = useMemo<ErrorEntry[]>(() => {
    const entries: ErrorEntry[] = [];
    let id = 0;

    for (const cycle of completedCycles) {
      if (cycle.status === 'error') {
        entries.push({
          id: ++id,
          timestamp: cycle.completed_at ?? cycle.started_at ?? '',
          source: 'cycle',
          message: `Cycle #${cycle.cycle_id} failed`,
        });
      }
      for (const stg of Object.values(cycle.stages)) {
        if (stg?.status === 'error' && stg?.error) {
          entries.push({
            id: ++id,
            timestamp: stg?.duration_ms ? String(stg.duration_ms) : '',
            source: 'stage',
            message: `[${stg?.label ?? '?'}] ${stg.error}`,
          });
        }
      }
    }

    for (const t of apiTraces) {
      if ((t?.status ?? 0) >= 500) {
        entries.push({
          id: ++id,
          timestamp: '',
          source: 'api',
          message: `${t?.method ?? '?'} ${t?.path ?? '?'} → ${t?.status ?? 0} (${t?.duration_ms ?? 0}ms)`,
        });
      }
    }

    return entries.sort((a, b) => {
      // Sort by id (first received first)
      return a.id - b.id;
    });
  }, [completedCycles, apiTraces]);

  useEffect(() => {
    if (errors.length > 0) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [errors.length]);

  return (
    <div className="rounded-lg border border-red-200 dark:border-red-900 bg-white dark:bg-gray-800 overflow-hidden flex flex-col h-48">
      <div className="px-3 py-2 border-b border-red-200 dark:border-red-900 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm text-red-600 dark:text-red-400">❌ Errors & Warnings</span>
          {errors.length > 0 && (
            <span className="text-xs bg-red-100 dark:bg-red-900/50 text-red-600 dark:text-red-400 rounded-full px-1.5 py-0.5">
              {errors.length}
            </span>
          )}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1 text-xs font-mono">
        {errors.length === 0 && (
          <div className="text-gray-400 italic p-2">No errors recorded</div>
        )}
        {errors.slice(-50).map((err) => (
          <div key={err.id} className="flex items-start gap-2 p-1 rounded bg-red-50 dark:bg-red-900/10">
            <span className="text-red-500 shrink-0 mt-0.5">⚠</span>
            <div>
              <span className="text-red-700 dark:text-red-300">{err.message}</span>
              <span className="text-gray-400 ml-1">[{err.source}]</span>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

export default memo(ErrorFeedInner);
