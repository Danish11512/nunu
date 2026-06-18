interface ProgressBarProps {
  percent: number;
  threshold?: number;
  size?: 'sm' | 'md' | 'lg';
  color?: 'green' | 'yellow' | 'gray';
  decimals?: number;
}

const heightStyles = {
  sm: 'h-1.5',
  md: 'h-2.5',
  lg: 'h-4',
};

const colorStyles = {
  green: 'bg-green-500',
  yellow: 'bg-yellow-500',
  gray: 'bg-gray-500',
};

export default function ProgressBar({
  percent,
  threshold,
  size = 'md',
  color = 'gray',
  decimals = 0,
}: ProgressBarProps) {
  const clampedPercent = Math.max(0, Math.min(100, percent));

  return (
    <div className="flex items-center gap-2">
      <div
        className={`flex-1 relative bg-gray-700 rounded-full overflow-visible ${heightStyles[size]}`}
        role="progressbar"
        aria-valuenow={clampedPercent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${clampedPercent.toFixed(decimals)}%`}
      >
        <div
          className={`h-full rounded-full transition-all duration-500 ${colorStyles[color]}`}
          style={{ width: `${clampedPercent}%` }}
        />
        {threshold !== undefined && (
          <div
            className="absolute top-0 bottom-0 w-0.5 bg-gray-400 opacity-70"
            style={{ left: `${Math.max(0, Math.min(100, threshold))}%` }}
          />
        )}
      </div>
      <span className="text-xs font-mono text-gray-400 min-w-[3ch] text-right">
        {clampedPercent.toFixed(decimals)}%
      </span>
    </div>
  );
}
