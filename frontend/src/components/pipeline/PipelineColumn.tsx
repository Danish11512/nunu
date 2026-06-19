import { memo, useMemo } from 'react';
import type { PipelineCycleInfo } from '../../lib/types';
import StatusPill from './shared';

interface Props {
  currentCycle: PipelineCycleInfo | null;
  completedCycles: PipelineCycleInfo[];
  isRunning: boolean;
}

const STAGE_ORDER = ['E1', 'E2', 'E3', 'E4', 'E5', 'E6', 'E7'] as const;

const stageLabels: Record<string, string> = {
  E1: 'Scan Markets',
  E2: 'Filter New Events',
  E3: 'Analyze Markets',
  E4: 'Price Filter',
  E5: 'Volatility Filter',
  E6: 'Time Filter',
  E7: 'Generate Signals',
};

function stageBadge(status: string | undefined) {
  switch (status) {
    case 'done': return <span className="text-green-500 shrink-0">✅</span>;
    case 'running': return <span className="text-blue-500 shrink-0">▶️</span>;
    case 'error': return <span className="text-red-500 shrink-0">❌</span>;
    case 'skipped': return <span className="text-gray-400 shrink-0">⏭️</span>;
    default: return <span className="text-gray-300 shrink-0">⏺</span>;
  }
}

function PipelineColumnInner({ currentCycle, completedCycles, isRunning }: Props) {
  const sortedStages = useMemo(() => {
    if (!currentCycle) return [];
    return STAGE_ORDER
      .filter((s) => currentCycle.stages[s])
      .map((s) => currentCycle.stages[s])
      .filter(Boolean);
  }, [currentCycle]);

  const latestCompleted = completedCycles[0];

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-hidden flex flex-col h-80">
      <div className="px-3 py-2 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm">📊 Pipeline</span>
          <StatusPill isLive={isRunning} />
        </div>
        <span className="text-xs text-gray-400">
          {currentCycle?.cycle_id
            ? `Cycle #${currentCycle.cycle_id}`
            : completedCycles.length > 0
              ? `Last cycle #${completedCycles[0]?.cycle_id}`
              : ''}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {/* Active cycle — running stages */}
        {sortedStages.length > 0 && (
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
              <span>Markets: {currentCycle?.total_markets_discovered ?? 0}</span>
              <span>·</span>
              <span>Events: {currentCycle?.total_events_active ?? 0}</span>
              <span>·</span>
              <span>Candidates: {currentCycle?.total_candidates_found ?? 0}</span>
            </div>
            {sortedStages.map((stg) => {
              if (!stg) return null;
              return (
                <div
                  key={stg.stage}
                  className={`flex items-center gap-2 p-1.5 rounded text-xs font-mono ${
                    stg.status === 'running'
                      ? 'bg-blue-50 dark:bg-blue-900/20 ring-1 ring-blue-200 dark:ring-blue-800'
                      : stg.status === 'error'
                        ? 'bg-red-50 dark:bg-red-900/20'
                        : 'hover:bg-gray-50 dark:hover:bg-gray-750'
                  }`}
                >
                  {stageBadge(stg.status)}
                  <span className="font-medium text-gray-700 dark:text-gray-300 flex-1">
                    {stg.label || stageLabels[stg.stage] || stg.stage}
                  </span>
                  <span className="text-gray-400 tabular-nums shrink-0">
                    {stg.input_count ?? 0}→{stg.output_count ?? 0}
                  </span>
                  <span className="text-gray-400 tabular-nums w-14 text-right shrink-0">
                    {stg.duration_ms ?? 0}ms
                  </span>
                </div>
              );
            })}
          </div>
        )}

        {!currentCycle && !latestCompleted && (
          <div className="text-gray-400 italic p-2 text-xs">Waiting for pipeline to start...</div>
        )}

        {!currentCycle && latestCompleted && (
          <div className="text-gray-400 italic p-2 text-xs">Pipeline idle — last cycle shown below</div>
        )}

        {/* Completed cycles */}
        {completedCycles.slice(0, 2).map((cycle) => (
          <div key={cycle.cycle_id} className="border-t border-gray-100 dark:border-gray-700 pt-1.5 mt-1.5">
            <div className="flex items-center gap-1.5 text-xs mb-1">
              <span className="text-green-500">✅</span>
              <span className="font-medium text-gray-600 dark:text-gray-400">
                Cycle #{cycle.cycle_id}
              </span>
              <span className="text-gray-400">
                · {cycle.total_markets_discovered}m · {cycle.total_events_active}e · {cycle.total_candidates_found}c
              </span>
            </div>
            <div className="flex gap-1 flex-wrap">
              {STAGE_ORDER.map((s) => {
                const stg = cycle.stages[s];
                if (!stg) return null;
                return (
                  <span
                    key={s}
                    className={`text-xs px-1 py-0.5 rounded ${
                      stg.status === 'done'
                        ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300'
                        : stg.status === 'error'
                          ? 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300'
                          : 'bg-gray-50 dark:bg-gray-800 text-gray-500'
                    }`}
                    title={`${stg.label}: ${stg.input_count}→${stg.output_count} (${stg.duration_ms}ms)`}
                  >
                    {s}
                  </span>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default memo(PipelineColumnInner);
