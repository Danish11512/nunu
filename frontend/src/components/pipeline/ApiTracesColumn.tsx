import { memo, useMemo, useRef, useEffect } from 'react';
import type { ApiTraceInfo } from '../../lib/types';
import StatusPill from './shared';

interface Props {
  traces: ApiTraceInfo[];
  isRunning: boolean;
  onClear?: () => void;
}

function ApiTracesColumnInner({ traces, isRunning, onClear }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [traces.length]);

  const errorCount = useMemo(
    () => traces.filter((t) => (t?.status ?? 0) >= 400).length,
    [traces],
  );

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-hidden flex flex-col h-80">
      <div className="px-3 py-2 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm">📡 API Calls</span>
          <StatusPill isLive={isRunning} />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">{traces.length} total{errorCount > 0 ? ` · ${errorCount} errors` : ''}</span>
          {onClear && (
            <button
              onClick={onClear}
              className="text-xs px-1.5 py-0.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500"
            >
              clear
            </button>
          )}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1 text-xs font-mono">
        {traces.length === 0 && (
          <div className="text-gray-400 italic p-2">No API calls recorded...</div>
        )}
        {traces.map((t, i) => {
          const status = t?.status ?? 0;
          const icon = status >= 500 ? '🔴' : status >= 400 ? '⚠️' : '↗️';
          return (
            <div key={`${i}-${t?.duration_ms ?? 0}`} className="flex items-center gap-2 p-1 rounded hover:bg-gray-50 dark:hover:bg-gray-750 whitespace-nowrap">
              <span className="shrink-0">{icon}</span>
              <span className="font-medium text-gray-600 dark:text-gray-400 shrink-0 w-10">{t?.method ?? '?'}</span>
              <span className="text-gray-700 dark:text-gray-300">{t?.path ?? ''}</span>
              <span className={`shrink-0 font-medium tabular-nums ${status >= 400 ? 'text-red-500' : 'text-gray-500'}`}>
                {status}
              </span>
              <span className="shrink-0 text-gray-400 tabular-nums w-12 text-right">
                {t?.duration_ms ?? 0}ms
              </span>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

export default memo(ApiTracesColumnInner);
