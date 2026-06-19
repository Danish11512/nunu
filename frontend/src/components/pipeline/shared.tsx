import type { ReactNode } from 'react';

export default function StatusPill({ isLive }: { isLive: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1 text-xs ${
      isLive ? 'text-green-500' : 'text-gray-400'
    }`}>
      <span className={`w-1.5 h-1.5 rounded-full ${
        isLive ? 'bg-green-500 animate-pulse' : 'bg-gray-300 dark:bg-gray-600'
      }`} />
      {isLive ? 'Live' : 'Idle'}
    </span>
  );
}
