import { memo, useMemo } from 'react';
import type { ScannerStatusInfo } from '../../lib/types';

interface Props {
  status: ScannerStatusInfo | null;
}

const pillBase = 'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium';

function StatusBarInner({ status }: Props) {
  const uptime = useMemo(() => {
    if (!status?.uptime_seconds) return '—';
    const sec = Math.round(status.uptime_seconds);
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    return h > 0 ? `${h}h ${m}m` : m > 0 ? `${m}m ${s}s` : `${s}s`;
  }, [status?.uptime_seconds]);

  return (
    <div className="flex flex-wrap gap-2 mb-4">
      {/* Mode */}
      <span className={`${pillBase} bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300`}>
        <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
        {status?.mode ?? '—'}
      </span>

      {/* Uptime */}
      <span className={`${pillBase} bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-400`}>
        ⏱ {uptime}
      </span>

      {/* Markets tracked */}
      <span className={`${pillBase} bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300`}>
        📊 {status?.markets_tracked ?? 0} markets
      </span>

      {/* Events tracked */}
      <span className={`${pillBase} bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300`}>
        🎯 {status?.events_tracked ?? 0} events
      </span>

      {/* Rate limit */}
      <span className={`${pillBase} ${
        (status?.active_candidates ?? 0) > 50
          ? 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300'
          : (status?.active_candidates ?? 0) > 20
            ? 'bg-yellow-50 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300'
            : 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300'
      }`}>
        ⚡ {status?.active_candidates ?? 0}%
      </span>

      {/* WS status */}
      <span className={`${pillBase} ${
        status?.connected_to_kalshi
          ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300'
          : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300'
      }`}>
        <span className={`w-1.5 h-1.5 rounded-full ${
          status?.connected_to_kalshi ? 'bg-green-500' : 'bg-red-500'
        }`} />
        {status?.connected_to_kalshi ? 'WS Connected' : 'WS Disconnected'}
      </span>

      {/* Running state */}
      <span className={`${pillBase} ${
        status?.is_running
          ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300'
          : 'bg-gray-50 dark:bg-gray-800 text-gray-500'
      }`}>
        <span className={`w-1.5 h-1.5 rounded-full ${status?.is_running ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
        {status?.is_running ? 'Scanning' : 'Idle'}
      </span>
    </div>
  );
}

export default memo(StatusBarInner);
