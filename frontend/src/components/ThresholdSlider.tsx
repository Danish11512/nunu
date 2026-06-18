interface ThresholdSliderProps {
  value: number;
  onChange: (value: number) => void;
  disabled?: boolean;
}

const TICK_MARKS = [0, 25, 50, 65, 75, 100];

export default function ThresholdSlider({ value, onChange, disabled }: ThresholdSliderProps) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-sm text-gray-400">Progress Threshold</span>
        <span className="text-xl font-mono font-bold text-blue-400">{value}%</span>
      </div>
      <div className="relative">
        <input
          type="range"
          min={0}
          max={100}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          disabled={disabled}
          aria-label="Progress Threshold"
          className="w-full accent-blue-500 disabled:opacity-50"
        />
        <div className="flex justify-between px-0.5 -mt-1">
          {TICK_MARKS.filter((t) => t === 0 || t === 100).map((tick) => (
            <span key={tick} className="text-[10px] text-gray-500">{tick}</span>
          ))}
        </div>
        <div className="flex justify-between px-0.5">
          {TICK_MARKS.map((tick) => (
            <span key={tick} className="w-0.5 h-1.5 bg-gray-600" />
          ))}
        </div>
      </div>
    </div>
  );
}
