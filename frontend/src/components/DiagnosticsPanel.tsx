import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { useDiagnostics, type DiagnosticLogEntry } from '../hooks/useDiagnostics';
import { API_BASE } from '../lib/constants';
import type { DiscoveryEvent, ProgressGateEvent, ScannerStatus } from '../lib/types';
import StatusBar from './pipeline/StatusBar';
import DiscoveryColumn from './pipeline/DiscoveryColumn';
import PipelineColumn from './pipeline/PipelineColumn';
import ProgressGateColumn from './pipeline/ProgressGateColumn';
import ApiTracesColumn from './pipeline/ApiTracesColumn';
import ErrorFeed from './pipeline/ErrorFeed';
import CandidateQueue from './pipeline/CandidateQueue';
import LiveEventMetrics from './pipeline/LiveEventMetrics';

// ── Log Row (kept for the collapsible raw log section) ──

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
      <span className={
        entry.type === 'cycle_error' ? 'text-red-500' :
        entry.type === 'cycle_end' ? 'text-green-600' :
        entry.type === 'trace' && entry.detail && (entry.detail as Record<string, unknown>).status != null && (entry.detail as Record<string, unknown>).status as number >= 400 ? 'text-yellow-600' :
        'text-gray-700 dark:text-gray-300'}>
        {entry.message}
      </span>
    </div>
  );
}

// ── Main Component ──

const DiagnosticsPanel: React.FC = () => {
  const [expanded, setExpanded] = useState(false);
  const [logExpanded, setLogExpanded] = useState(false);
  const [logFilter, setLogFilter] = useState<string>('all');
  const [autoScroll, setAutoScroll] = useState(true);
  const [scannerStatus, setScannerStatus] = useState<ScannerStatus | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const { completedCycles, currentCycle, apiTraces, logs, isRunning, reset, discoveryFeed, progressGateFeed } = useDiagnostics();

  const lastDiscovery = useMemo<DiscoveryEvent | null>(
    () => discoveryFeed.length > 0 ? discoveryFeed[discoveryFeed.length - 1] : null,
    [discoveryFeed],
  );

  const lastProgress = useMemo<ProgressGateEvent | null>(
    () => progressGateFeed.length > 0 ? progressGateFeed[progressGateFeed.length - 1] : null,
    [progressGateFeed],
  );

  // Poll scanner status
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const resp = await fetch(`${API_BASE}/scanner/status`);
        const json = await resp.json();
        if (!cancelled && json?.success && json?.data) {
          setScannerStatus(json.data as ScannerStatus);
        }
      } catch { /* ignore */ }
    };
    poll();
    const id = setInterval(poll, 5000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  // Auto-scroll for raw log
  useEffect(() => {
    if (autoScroll && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const handleScroll = useCallback(() => {
    if (!scrollContainerRef.current) return;
    const el = scrollContainerRef.current;
    const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50;
    if (!isAtBottom) setAutoScroll(false);
    else setAutoScroll(true);
  }, []);

  const handleLogFilter = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    setLogFilter(e.target.value);
  }, []);

  const handleReset = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    reset();
  }, [reset]);

  const handleToggleLog = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setLogExpanded(prev => !prev);
  }, []);

  const handleAutoScrollToggle = useCallback(() => {
    setAutoScroll(prev => !prev);
  }, []);

  const handleToggleExpand = useCallback(() => {
    setExpanded(prev => !prev);
  }, []);

  const filteredLogs = useMemo(() => {
    if (logFilter === 'all') return logs;
    if (logFilter === 'cycle') return logs.filter(l => ['cycle_start', 'cycle_end', 'cycle_error', 'stage'].includes(l.type));
    if (logFilter === 'traces') return logs.filter(l => l.type === 'trace');
    if (logFilter === 'info') return logs.filter(l => ['discovery', 'progress'].includes(l.type));
    return logs;
  }, [logs, logFilter]);

  const handleHeaderKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpanded(prev => !prev); }
  }, []);

  return (
    <div className="mt-6 border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden bg-gray-50 dark:bg-gray-800/50">
      {/* Header — div with role=button to avoid nested <button> violation */}
      <div
        role="button"
        tabIndex={0}
        onClick={handleToggleExpand}
        onKeyDown={handleHeaderKeyDown}
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
            <button
              onClick={handleReset}
              className="text-xs px-2 py-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500"
            >
              Clear
            </button>
          )}
          <span className="text-gray-400 text-lg">{expanded ? '▼' : '▶'}</span>
        </div>
      </div>

      {/* Body */}
      {expanded && (
        <div className="px-4 pb-4 space-y-4 overflow-x-auto">
          {/* Status bar pills */}
          <StatusBar status={scannerStatus as unknown as ScannerStatus} />

          {/* Main 4-column flex row — each column uses its natural width */}
          <div className="flex flex-nowrap gap-4 overflow-x-auto">
            <div className="flex-shrink-0 w-max min-w-80"><DiscoveryColumn events={discoveryFeed} isRunning={isRunning} /></div>
            <div className="flex-shrink-0 w-max min-w-80"><PipelineColumn currentCycle={currentCycle} completedCycles={completedCycles} isRunning={isRunning} /></div>
            <div className="flex-shrink-0 w-max min-w-80"><ProgressGateColumn events={progressGateFeed} isRunning={isRunning} currentCycle={currentCycle} /></div>
            <div className="flex-shrink-0 w-max min-w-80"><ApiTracesColumn traces={apiTraces} isRunning={isRunning} /></div>
          </div>

          {/* Secondary row: error feed + candidate queue + live metrics */}
          <div className="flex flex-nowrap gap-4 overflow-x-auto">
            <div className="flex-shrink-0 w-max min-w-80"><ErrorFeed completedCycles={completedCycles} apiTraces={apiTraces} /></div>
            <div className="flex-shrink-0 w-max min-w-80"><CandidateQueue isRunning={isRunning} /></div>
            <div className="flex-shrink-0 w-max min-w-80"><LiveEventMetrics
              currentCycle={currentCycle}
              completedCycles={completedCycles}
              lastDiscovery={lastDiscovery}
              lastProgress={lastProgress}
            /></div>
          </div>

          {/* Collapsible raw log */}
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden bg-white dark:bg-gray-900 min-w-0">
            <div
              role="button"
              tabIndex={0}
              onClick={handleToggleLog}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setLogExpanded(prev => !prev); } }}
              className="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800"
            >
              <span className="text-xs font-medium text-gray-500">📄 Raw Event Log</span>
              <div className="flex items-center gap-2">
                {logExpanded && (
                  <>
                    <button
                      onClick={(e) => { e.stopPropagation(); setAutoScroll(prev => !prev); }}
                      className={`text-xs px-1.5 py-0.5 rounded ${autoScroll ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-500'}`}
                    >
                      {autoScroll ? '🔽 Auto' : 'Manual'}
                    </button>
                    <select
                      onClick={(e) => e.stopPropagation()}
                      value={logFilter}
                      onChange={handleLogFilter}
                      className="text-xs border rounded px-1 py-0.5 dark:bg-gray-800 dark:border-gray-600"
                    >
                      <option value="all">All</option>
                      <option value="cycle">Stages</option>
                      <option value="traces">Traces</option>
                      <option value="info">Info</option>
                    </select>
                  </>
                )}
                <span className="text-gray-400 text-xs">{logExpanded ? '▼' : '▶'}</span>
              </div>
            </div>
            {logExpanded && (
              <div
                ref={scrollContainerRef}
                onScroll={handleScroll}
                className="h-48 overflow-y-auto p-2 border-t border-gray-100 dark:border-gray-800"
              >
                {filteredLogs.map(entry => (
                  <LogRow key={entry.id} entry={entry} />
                ))}
                {filteredLogs.length === 0 && (
                  <p className="text-xs text-gray-400 italic py-4 text-center">Waiting for events...</p>
                )}
                <div ref={logEndRef} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default React.memo(DiagnosticsPanel);
