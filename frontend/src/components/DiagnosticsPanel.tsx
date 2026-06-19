import React, { useState, useRef, useEffect, useMemo } from 'react';
import { useDiagnostics, type DiagnosticLogEntry } from '../hooks/useDiagnostics';
import type { PipelineCycleInfo, PipelineStageInfo } from '../lib/types';

// ── Helpers ──

function stageBadgeColor(status: string): string {
  switch (status) {
    case 'done': return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400';
    case 'running': return 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400 animate-pulse';
    case 'error': return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400';
    case 'skipped': return 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-500';
    default: return 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-500';
  }
}

function StageRow({ stage }: { stage: PipelineStageInfo }) {
  return (
    <div className="flex items-center gap-2 py-1 text-sm">
      <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${stageBadgeColor(stage.status)}`}>
        {stage.stage}
      </span>
      <span className="flex-1">{stage.label}</span>
      <span className="text-gray-400 text-xs">
        {stage.input_count > 0 && `in:${stage.input_count} `}
        {stage.output_count > 0 && `out:${stage.output_count} `}
      </span>
      {stage.duration_ms > 0 && (
        <span className="text-gray-400 text-xs w-16 text-right">{stage.duration_ms}ms</span>
      )}
      {stage.error && <span className="text-red-500 text-xs truncate max-w-[120px]" title={stage.error}>⚠️</span>}
    </div>
  );
}

function CycleCard({ cycle }: { cycle: PipelineCycleInfo }) {
  const sortedStages = useMemo(() => {
    const order = ['E1', 'E2', 'E3', 'E4', 'E5', 'E6', 'E7'];
    return order.map(id => cycle.stages[id]).filter(Boolean);
  }, [cycle]);

  return (
    <div className="border rounded-lg p-3 mb-2 dark:border-gray-700 bg-white dark:bg-gray-900">
      <div className="flex items-center justify-between mb-2">
        <span className="font-medium text-sm">
          Cycle #{cycle.cycle_id}
          <span className={`ml-2 px-1.5 py-0.5 rounded text-xs font-medium ${
            cycle.status === 'completed' ? 'bg-green-100 text-green-700' :
            cycle.status === 'error' ? 'bg-red-100 text-red-700' :
            'bg-blue-100 text-blue-700'
          }`}>
            {cycle.status}
          </span>
        </span>
        <span className="text-xs text-gray-400">
          {cycle.total_markets_discovered} markets · {cycle.total_events_active} events · {cycle.total_candidates_found} candidates
        </span>
      </div>
      <div className="space-y-0.5">
        {sortedStages.map(s => s && <StageRow key={s.stage} stage={s} />)}
      </div>
    </div>
  );
}

function LogRow({ entry }: { entry: DiagnosticLogEntry }) {
  const iconMap: Record<string, string> = {
    stage: '', cycle_start: '🔄', cycle_end: '✅', cycle_error: '❌',
    trace: '', discovery: '🔍', progress: '⏱',
  };
  const icon = iconMap[entry.type] || '';
  return (
    <div className="font-mono text-[11px] leading-5 border-b border-gray-100 dark:border-gray-800 last:border-0">
      <span className="text-gray-400 mr-1">{entry.timestamp.slice(11, 22)}</span>
      {icon && <span className="mr-1">{icon}</span>}
      <span className={entry.type === 'cycle_error' ? 'text-red-500' :
        entry.type === 'cycle_end' ? 'text-green-600' :
        entry.type === 'trace' && entry.detail && (entry.detail as any).status >= 400 ? 'text-yellow-600' :
        'text-gray-700 dark:text-gray-300'}>
        {entry.message}
      </span>
    </div>
  );
}

// ── Main Component ──

const DiagnosticsPanel: React.FC = () => {
  const [expanded, setExpanded] = useState(false);
  const [logFilter, setLogFilter] = useState<string>('all');
  const [autoScroll, setAutoScroll] = useState(true);
  const logEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const { completedCycles, currentCycle, apiTraces, logs, isRunning, reset } = useDiagnostics();

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  // Detect user scroll
  const handleScroll = () => {
    if (!scrollContainerRef.current) return;
    const el = scrollContainerRef.current;
    const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50;
    if (!isAtBottom) setAutoScroll(false);
    else setAutoScroll(true);
  };

  const filteredLogs = useMemo(() => {
    if (logFilter === 'all') return logs;
    if (logFilter === 'cycle') return logs.filter(l => ['cycle_start', 'cycle_end', 'cycle_error', 'stage'].includes(l.type));
    if (logFilter === 'traces') return logs.filter(l => l.type === 'trace');
    if (logFilter === 'info') return logs.filter(l => ['discovery', 'progress'].includes(l.type));
    return logs;
  }, [logs, logFilter]);

  const allCycles = useMemo(() => {
    const list: PipelineCycleInfo[] = [...completedCycles];
    if (currentCycle) list.unshift(currentCycle);
    return list;
  }, [completedCycles, currentCycle]);

  return (
    <div className="mt-6 border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden bg-gray-50 dark:bg-gray-800/50">
      {/* Header — div with role=button to avoid nested <button> violation */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => setExpanded(!expanded)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpanded(!expanded); } }}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors cursor-pointer"
      >
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm">🔧 Pipeline Diagnostics</span>
          {isRunning && (
            <span className="inline-flex items-center gap-1 text-xs text-blue-600">
              <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse" />
              Running
            </span>
          )}
          {!isRunning && completedCycles.length > 0 && (
            <span className="text-xs text-gray-400">{completedCycles.length} cycles</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {expanded && (
            <>
              <button
                onClick={(e) => { e.stopPropagation(); reset(); }}
                className="text-xs px-2 py-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500"
              >
                Clear
              </button>
              <select
                onClick={(e) => e.stopPropagation()}
                value={logFilter}
                onChange={e => setLogFilter(e.target.value)}
                className="text-xs border rounded px-1 py-0.5 dark:bg-gray-800 dark:border-gray-600"
              >
                <option value="all">All</option>
                <option value="cycle">Stages</option>
                <option value="traces">API Traces</option>
                <option value="info">Info</option>
              </select>
            </>
          )}
          <span className="text-gray-400 text-lg">{expanded ? '▼' : '▶'}</span>
        </div>
      </div>

      {/* Body */}
      {expanded && (
        <div className="px-4 pb-4">
          {/* Cycle summary cards */}
          <div className="mb-3">
            {allCycles.length === 0 && !isRunning && (
              <p className="text-xs text-gray-400 italic py-4 text-center">No pipeline cycles yet. Run a scan to see diagnostics.</p>
            )}
            {allCycles.map(cycle => (
              <CycleCard key={`${cycle.cycle_id}-${cycle.status}`} cycle={cycle} />
            ))}
            {currentCycle && currentCycle.status === 'running' && (
              <div className="flex items-center gap-2 text-xs text-blue-600 py-2">
                <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
                Pipeline running...
              </div>
            )}
          </div>

          {/* Log viewer */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-medium text-gray-500">Live Log</span>
              <button
                onClick={() => setAutoScroll(!autoScroll)}
                className={`text-xs px-1.5 py-0.5 rounded ${autoScroll ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-500'}`}
              >
                {autoScroll ? '🔽 Auto-scroll' : 'Manual scroll'}
              </button>
            </div>
            <div
              ref={scrollContainerRef}
              onScroll={handleScroll}
              className="h-48 overflow-y-auto bg-white dark:bg-gray-900 border dark:border-gray-700 rounded p-2"
            >
              {filteredLogs.map(entry => (
                <LogRow key={entry.id} entry={entry} />
              ))}
              {filteredLogs.length === 0 && (
                <p className="text-xs text-gray-400 italic py-4 text-center">Waiting for events...</p>
              )}
              <div ref={logEndRef} />
            </div>
          </div>

          {/* API trace summary */}
          {apiTraces.length > 0 && (
            <div className="mt-2 text-xs text-gray-400">
              {apiTraces.length} API calls traced |
              {apiTraces.filter(t => t.status >= 400).length > 0 && (
                <span className="text-yellow-600"> {apiTraces.filter(t => t.status >= 400).length} errors</span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default React.memo(DiagnosticsPanel);
