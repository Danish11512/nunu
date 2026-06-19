import { memo, useState, useRef, useEffect, useCallback } from 'react';
import { API_BASE } from '../../lib/constants';
import type { CandidateSummary } from '../../lib/types';

interface Props {
  isRunning: boolean;
}

function CandidateQueueInner({ isRunning }: Props) {
  const [candidates, setCandidates] = useState<CandidateSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);

  const fetchCandidates = useCallback(async () => {
    if (!mountedRef.current) return;
    try {
      setIsLoading(true);
      setError(null);
      const resp = await fetch(`${API_BASE}/scanner/candidates`);
      const json = await resp.json();
      if (mountedRef.current) {
        if (json?.success && Array.isArray(json?.data)) {
          setCandidates(json.data as CandidateSummary[]);
        } else if (Array.isArray(json)) {
          setCandidates(json as CandidateSummary[]);
        }
      }
    } catch (e) {
      if (mountedRef.current) {
        setError(e instanceof Error ? e.message : 'Fetch failed');
      }
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    // Only poll when scanner is running
    if (isRunning) {
      fetchCandidates();
      intervalRef.current = setInterval(fetchCandidates, 3000);
    } else {
      setCandidates([]);
    }

    return () => {
      mountedRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [isRunning, fetchCandidates]);

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-hidden flex flex-col h-48">
      <div className="px-3 py-2 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm">📋 Candidate Queue</span>
          {isLoading && <span className="w-3 h-3 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />}
        </div>
        <span className="text-xs text-gray-400">{candidates.length} queued</span>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1 text-xs font-mono">
        {error && (
          <div className="text-red-500 italic p-1">{error}</div>
        )}
        {!isRunning && !error && (
          <div className="text-gray-400 italic p-2">Scanner idle — no candidates</div>
        )}
        {isRunning && candidates.length === 0 && !error && (
          <div className="text-gray-400 italic p-2">Waiting for candidates...</div>
        )}
        {candidates.slice(-20).map((c, i) => {
          const side = c?.side ?? '?';
          const sideCol = side === 'yes' ? 'text-green-500' : side === 'no' ? 'text-red-500' : 'text-gray-400';
          return (
            <div key={`${c?.event_ticker}-${i}`} className="flex items-center gap-2 p-1 rounded hover:bg-gray-50 dark:hover:bg-gray-750">
              <span className={`shrink-0 font-medium ${sideCol}`}>{side === 'yes' ? 'Y' : 'N'}</span>
              <span className="text-gray-700 dark:text-gray-300 whitespace-nowrap">{c?.event_ticker ?? '?'}</span>
              <span className="shrink-0 text-gray-500 tabular-nums">${typeof c?.price === 'number' ? c.price.toFixed(2) : '0.00'}</span>
              <span className={`shrink-0 text-xs ${c?.is_valid ? 'text-green-500' : 'text-yellow-500'}`}>
                {c?.is_valid ? '✓' : '⏳'}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default memo(CandidateQueueInner);
