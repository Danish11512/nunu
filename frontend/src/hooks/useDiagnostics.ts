import { useEffect, useCallback, useRef, useState } from 'react';
import { registerListener } from '../stores/wsStore';
import { API_BASE } from '../lib/constants';
import type {
  PipelineCycleInfo, ApiTraceInfo, DiscoveryEvent, ProgressGateEvent,
} from '../lib/types';

const MAX_CYCLES = 3;
const MAX_TRACES = 500;
const MAX_FEED = 100;

export interface DiagnosticLogEntry {
  id: number;
  timestamp: string;
  type: 'stage' | 'trace' | 'cycle_start' | 'cycle_end' | 'cycle_error' | 'discovery' | 'progress';
  message: string;
  detail?: Record<string, unknown>;
}

export function useDiagnostics() {
  const [completedCycles, setCompletedCycles] = useState<PipelineCycleInfo[]>([]);
  const [currentCycle, setCurrentCycle] = useState<PipelineCycleInfo | null>(null);
  const [apiTraces, setApiTraces] = useState<ApiTraceInfo[]>([]);
  const [logs, setLogs] = useState<DiagnosticLogEntry[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [discoveryFeed, setDiscoveryFeed] = useState<DiscoveryEvent[]>([]);
  const [progressGateFeed, setProgressGateFeed] = useState<ProgressGateEvent[]>([]);
  const logIdRef = useRef(0);
  const eventIdRef = useRef(0);
  const tracesRef = useRef<ApiTraceInfo[]>([]);
  const currentCycleRef = useRef<PipelineCycleInfo | null>(null);

  const addLog = useCallback((type: DiagnosticLogEntry['type'], message: string, detail?: Record<string, unknown>) => {
    logIdRef.current += 1;
    const entry: DiagnosticLogEntry = {
      id: logIdRef.current,
      timestamp: new Date().toISOString(),
      type,
      message,
      detail,
    };
    setLogs(prev => [...prev.slice(-199), entry]);  // keep last 200
  }, []);

  const addDiscoveryEvent = useCallback((data: DiscoveryEvent['data']) => {
    eventIdRef.current += 1;
    const entry: DiscoveryEvent = {
      id: eventIdRef.current,
      timestamp: new Date().toISOString(),
      data,
    };
    setDiscoveryFeed(prev => [...prev.slice(-(MAX_FEED - 1)), entry]);
  }, []);

  const addProgressEvent = useCallback((data: ProgressGateEvent['data']) => {
    eventIdRef.current += 1;
    const entry: ProgressGateEvent = {
      id: eventIdRef.current,
      timestamp: new Date().toISOString(),
      data,
    };
    setProgressGateFeed(prev => [...prev.slice(-(MAX_FEED - 1)), entry]);
  }, []);

  const reset = useCallback(() => {
    setCompletedCycles([]);
    setCurrentCycle(null);
    currentCycleRef.current = null;
    setApiTraces([]);
    setLogs([]);
    setDiscoveryFeed([]);
    setProgressGateFeed([]);
    tracesRef.current = [];
    setIsRunning(false);
  }, []);

  // Mount-only WS listeners — uses refs to avoid stale closures and
  // prevents listener re-registration on every state update.
  useEffect(() => {
    const unsubs: (() => void)[] = [];

    const listen = (type: string, handler: (data: any) => void) => {
      const unsub = registerListener('scanner', (msg: any) => {
        if (msg?.type === type) handler(msg.data);
      });
      unsubs.push(unsub);
    };

    listen('scanner:started', (data) => {
      setIsRunning(true);
      const cycle: PipelineCycleInfo = {
        cycle_id: data?.cycle_id ?? 0,
        status: 'running',
        stages: {},
        started_at: data?.started_at ?? null,
        completed_at: null,
        total_markets_discovered: 0,
        total_events_active: 0,
        total_candidates_found: 0,
      };
      currentCycleRef.current = cycle;
      setCurrentCycle(cycle);
      addLog('cycle_start', `Cycle #${data?.cycle_id ?? '?'} started`);
    });

    listen('scanner:stage_update', (data) => {
      setCurrentCycle(prev => {
        // Late join: if user navigated here after scanner:started was sent,
        // create a cycle on the fly so the update isn't dropped.
        const base = prev || {
          cycle_id: data?.cycle_id ?? 0,
          status: 'running',
          stages: {},
          started_at: null,
          completed_at: null,
          total_markets_discovered: 0,
          total_events_active: 0,
          total_candidates_found: 0,
        };
        const updated = {
          ...base,
          stages: {
            ...base.stages,
            [data?.stage ?? '?']: {
              stage: data?.stage ?? '?',
              label: data?.label ?? '',
              status: data?.status ?? 'pending',
              input_count: data?.input_count ?? 0,
              output_count: data?.output_count ?? 0,
              duration_ms: data?.duration_ms ?? 0,
              error: data?.error ?? null,
            },
          },
        };
        currentCycleRef.current = updated;
        return updated;
      });
      // Also set isRunning for late joiners
      setIsRunning(true);
      const statusIcon = data?.status === 'done' ? '✅' : data?.status === 'error' ? '❌' : data?.status === 'running' ? '▶️' : '⏭️';
      const detail = data?.duration_ms != null ? ` (${data.duration_ms}ms)` : '';
      const err = data?.error ? ` — ${data.error}` : '';
      addLog('stage', `${statusIcon} ${data?.label ?? ''}: ${data?.status ?? ''}${detail}${err}`, data ?? {});
    });

    listen('scanner:completed', (data) => {
      setIsRunning(false);
      setCompletedCycles(prev => {
        const cc = currentCycleRef.current;
        const updated: PipelineCycleInfo = {
          ...(cc || { cycle_id: data?.cycle_id ?? 0, stages: {}, started_at: data?.completed_at ?? null }),
          status: 'completed',
          completed_at: data?.completed_at ?? null,
          total_markets_discovered: data?.total_markets ?? 0,
          total_events_active: data?.total_events ?? 0,
          total_candidates_found: data?.total_candidates ?? 0,
        };
        return [updated, ...prev].slice(0, MAX_CYCLES);
      });
      currentCycleRef.current = null;
      setCurrentCycle(null);
      addLog('cycle_end', `Cycle #${data?.cycle_id ?? '?'} completed (${data?.total_duration_ms ?? 0}ms)`);
    });

    listen('scanner:error', (data) => {
      setIsRunning(false);
      setCurrentCycle(prev => {
        if (!prev) return prev;
        const errCycle = { ...prev, status: 'error' as const };
        currentCycleRef.current = errCycle;
        return errCycle;
      });
      setCompletedCycles(prev => {
        const cc = currentCycleRef.current;
        if (!cc) return prev;
        return [{ ...cc, status: 'error' as const }, ...prev].slice(0, MAX_CYCLES);
      });
      addLog('cycle_error', `Cycle #${data?.cycle_id ?? '?'} error: ${data?.error ?? 'unknown'}`, data ?? {});
    });

    listen('scanner:api_batch', (data) => {
      if (!Array.isArray(data)) return;
      const traces = data as ApiTraceInfo[];
      tracesRef.current = [...tracesRef.current, ...traces].slice(-MAX_TRACES);
      setApiTraces(tracesRef.current);
      for (const t of traces) {
        const icon = (t?.status ?? 0) >= 400 ? '⚠️' : '↗️';
        addLog('trace', `${icon} ${t?.method ?? '?'} ${t?.path ?? '?'} → ${t?.status ?? 0} (${t?.duration_ms ?? 0}ms)`, t as unknown as Record<string, unknown>);
      }
    });

    listen('scanner:discovery_cycle', (data) => {
      addDiscoveryEvent({
        total_markets: data?.total_markets ?? 0,
        total_events: data?.total_events ?? 0,
        added: data?.added ?? 0,
        removed: data?.removed ?? 0,
      });
      addLog('discovery',
        `🔍 Discovery: ${data?.total_markets ?? 0} markets, ${data?.total_events ?? 0} events (+${data?.added ?? 0}/−${data?.removed ?? 0})`,
        data as Record<string, unknown>);
    });

    listen('scanner:progress_cycle', (data) => {
      addProgressEvent({
        events_checked: data?.events_checked ?? 0,
      });
      addLog('progress',
        `⏱ Progress gate checked ${data?.events_checked ?? 0} events`,
        data as Record<string, unknown>);
    });

    return () => { unsubs.forEach(fn => fn()); };
  }, [addLog, addDiscoveryEvent, addProgressEvent]);

  // REST fallback for initial mount
  useEffect(() => {
    (async () => {
      try {
        const resp = await fetch(`${API_BASE}/scanner/progress`);
        const json = await resp.json();
        if (json?.success && json?.data) {
          setCurrentCycle(prev => prev ?? json.data);
        }
      } catch { /* ignore — WS will catch up */ }
    })();
  }, []);

  return { completedCycles, currentCycle, apiTraces, logs, isRunning, reset, discoveryFeed, progressGateFeed };
}

export type UseDiagnosticsReturn = ReturnType<typeof useDiagnostics>;
