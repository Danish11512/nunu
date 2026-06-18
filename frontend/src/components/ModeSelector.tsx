import { useState } from 'react';
import Badge from './Badge';
import ConfirmDialog from './ConfirmDialog';
import { ScannerMode, LiveMode } from '../lib/types';

interface ModeSelectorProps {
  currentMode: ScannerMode;
  onSwitch: (mode: LiveMode) => void;
  hasCredentials: boolean;
  switching?: boolean;
}

export default function ModeSelector({ currentMode, onSwitch, hasCredentials, switching = false }: ModeSelectorProps) {
  const [showConfirm, setShowConfirm] = useState(false);
  const isReadOnly = currentMode === ScannerMode.READ_ONLY;
  const isLive = currentMode === ScannerMode.LIVE;
  const badgeVariant = isLive ? 'live' : isReadOnly ? 'read_only' : 'dry_run';

  const handleToggleClick = () => {
    if (isLive) {
      // Switching to dry_run — no confirmation needed
      onSwitch(LiveMode.DRY_RUN);
    } else {
      // Switching to live — requires confirmation
      setShowConfirm(true);
    }
  };

  const handleConfirm = () => {
    setShowConfirm(false);
    onSwitch(LiveMode.LIVE);
  };

  return (
    <>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Badge variant={badgeVariant} label={currentMode} size="md" />
          <span className="text-gray-400 text-sm">
            {isLive
              ? 'Live trading enabled'
              : isReadOnly
                ? 'Read only — switch to live requires credentials'
                : 'Dry run — no real orders'}
          </span>
        </div>
        <button
          onClick={handleToggleClick}
          disabled={isReadOnly || !hasCredentials || switching}
          className="px-4 py-1.5 bg-blue-700 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed rounded text-sm"
        >
          {switching
            ? 'Switching...'
            : isReadOnly
              ? 'Locked'
              : isLive
                ? 'Switch to Dry Run'
                : 'Switch to Live'}
        </button>
      </div>

      <ConfirmDialog
        isOpen={showConfirm}
        title="Switch to Live Mode"
        message="Live mode will place real orders on Kalshi. This action cannot be undone. Are you sure you want to proceed?"
        confirmLabel="Confirm Live"
        onConfirm={handleConfirm}
        onCancel={() => setShowConfirm(false)}
        danger
      />
    </>
  );
}
