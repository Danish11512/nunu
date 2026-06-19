import { memo, useMemo, useRef, useEffect } from 'react';
import type { PipelineCycleInfo, DiscoveryEvent, ProgressGateEvent } from '../../lib/types';

interface Props {
  currentCycle: PipelineCycleInfo | null;
  completedCycles: PipelineCycleInfo[];
  lastDiscovery: DiscoveryEvent | null;
  lastProgress: ProgressGateEvent | null;
}

interface MetricRow {
  label: string;
  value: string;
  sub?: string;
  color?: string;
}

function LiveEventMetricsInner({ currentCycle, completedCycles, lastDiscovery, lastProgress }: Props) {
  const prevRef = useRef<{ markets: number; events: number; candidates: number }>({
    markets: 0, events: 0, candidates: 0,
  });

  const metrics = useMemo<MetricRow[]>(() => {
    const latest = currentCycle ?? completedCycles[0];

    // Δ calculations from previous cycle
    const prev = prevRef.current;
    const now = {
      markets: latest?.total_markets_discovered ?? 0,
      events: latest?.total_events_active ?? 0,
      candidates: latest?.total_candidates_found ?? 0,
    };
    const delta = {
      markets: now.markets - prev.markets,
      events: now.events - prev.events,
      candidates: now.candidates - prev.candidates,
    };
    prevRef.current = now;

    const rows: MetricRow[] = [];

    if (latest) {
      rows.push({
        label: 'Cycle',
        value: `#${latest.cycle_id}`,
        sub: latest.status,
        color: latest.status === 'completed' ? 'text-green-500' : latest.status === 'error' ? 'text-red-500' : 'text-blue-500',
      });
      rows.push({
        label: 'Markets',
        value: String(latest.total_markets_discovered),
        sub: delta.markets !== 0 ? `${delta.markets > 0 ? '+' : ''}${delta.markets}` : undefined,
        color: delta.markets > 0 ? 'text-green-500' : 'text-gray-700 dark:text-gray-300',
      });
      rows.push({
        label: 'Events',
        value: String(latest.total_events_active),
        sub: delta.events !== 0 ? `${delta.events > 0 ? '+' : ''}${delta.events}` : undefined,
        color: delta.events > 0 ? 'text-green-500' : 'text-gray-700 dark:text-gray-300',
      });
      rows.push({
        label: 'Candidates',
        value: String(latest.total_candidates_found),
        sub: delta.candidates !== 0 ? `${delta.candidates > 0 ? '+' : ''}${delta.candidates}` : undefined,
        color: delta.candidates > 0 ? 'text-green-500' : 'text-gray-700 dark:text-gray-300',
      });
    }

    if (lastDiscovery) {
      rows.push({
        label: 'Last Discovery',
        value: new Date(lastDiscovery.timestamp).toLocaleTimeString(),
        sub: `+${lastDiscovery.data.added}/−${lastDiscovery.data.removed}`,
        color: 'text-gray-600 dark:text-gray-400',
      });
    }

    if (lastProgress) {
      rows.push({
        label: 'Last Gate Check',
        value: `${lastProgress.data.events_checked} events`,
        sub: new Date(lastProgress.timestamp).toLocaleTimeString(),
        color: 'text-gray-600 dark:text-gray-400',
      });
    }

    return rows;
  }, [currentCycle, completedCycles, lastDiscovery, lastProgress]);

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-hidden h-48">
      <div className="px-3 py-2 border-b border-gray-200 dark:border-gray-700 shrink-0">
        <span className="font-semibold text-sm">📊 Live Metrics</span>
      </div>
      <div className="p-2 space-y-0.5 text-xs font-mono h-[calc(100%-2.25rem)] overflow-y-auto">
        {metrics.map((m) => (
          <div key={m.label} className="flex items-center justify-between py-0.5">
            <span className="text-gray-500 dark:text-gray-400">{m.label}</span>
            <div className="flex items-center gap-1.5">
              {m.sub && <span className="text-gray-400">{m.sub}</span>}
              <span className={`font-medium ${m.color ?? 'text-gray-700 dark:text-gray-300'}`}>
                {m.value}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default memo(LiveEventMetricsInner);
