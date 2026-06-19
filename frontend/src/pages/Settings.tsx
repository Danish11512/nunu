import { useState, useCallback, useMemo, lazy, Suspense, memo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useScannerConfig } from '../hooks/useScannerConfig';
import { ScannerMode, LiveMode, CycleMode } from '../lib/types';
import { ROUTES } from '../lib/routes';
import ModeSelector from '../components/ModeSelector';
import ThresholdSlider from '../components/ThresholdSlider';

const DiagnosticsPanel = lazy(() => import('../components/DiagnosticsPanel'));

function SettingsInner() {
  const navigate = useNavigate();
  const { config, updateConfig, switchMode, switchCycleMode } = useScannerConfig();
  const [threshold, setThreshold] = useState<number | null>(null);
  const [selectedStrategy, setSelectedStrategy] = useState<string | null>(null);

  const resolvedThreshold = useMemo(
    () => threshold ?? config.data?.threshold_percent ?? 65,
    [threshold, config.data?.threshold_percent],
  );
  const resolvedStrategy = useMemo(
    () => selectedStrategy ?? config.data?.strategy.name ?? '',
    [selectedStrategy, config.data?.strategy.name],
  );

  const currentCycleMode = config.data?.cycle_mode ?? CycleMode.LIVE;
  const isLiveCycle = currentCycleMode === CycleMode.LIVE;

  const handleSave = useCallback(() => {
    updateConfig.mutate({
      threshold_percent: resolvedThreshold,
      strategy: resolvedStrategy,
    });
  }, [updateConfig, resolvedThreshold, resolvedStrategy]);

  const handleModeSwitch = useCallback(
    (mode: LiveMode) => switchMode.mutate({ mode, confirm: true }),
    [switchMode],
  );

  const handleCycleModeToggle = useCallback(() => {
    const next = isLiveCycle ? CycleMode.ONE_SHOT : CycleMode.LIVE;
    switchCycleMode.mutate({ cycle_mode: next });
  }, [isLiveCycle, switchCycleMode]);

  const handleStrategyChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => setSelectedStrategy(e.target.value),
    [],
  );
  const handleThresholdChange = useCallback(
    (value: number) => setThreshold(value),
    [],
  );

  const currentMode = config.data?.mode ?? ScannerMode.DRY_RUN;
  const kalshiConnected = config.data?.kalshi.connected ?? false;

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      <header className="bg-gray-800 border-b border-gray-700 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button onClick={() => navigate(ROUTES.DASHBOARD)} className="text-blue-400 hover:text-blue-300 bg-transparent border-none cursor-pointer">&larr; Dashboard</button>
          <h1 className="text-xl font-bold">Settings</h1>
        </div>
      </header>

      <main className="p-6 space-y-8">
        {config.isLoading && (
          <div className="flex items-center justify-center h-32">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500" />
            <span className="ml-2 text-gray-400">Loading config...</span>
          </div>
        )}

        {config.isError && (
          <div className="bg-red-900/50 border border-red-700 rounded-lg p-4">
            <p className="text-red-200">{config.error?.message ?? 'Failed to load config'}</p>
          </div>
        )}

        {config.data && (
          <>
            {/* Mode Section */}
            <section className="bg-gray-800 rounded-lg p-5 border border-gray-700">
              <h2 className="text-lg font-semibold mb-3">Mode</h2>
              <ModeSelector
                currentMode={currentMode}
                onSwitch={handleModeSwitch}
                hasCredentials={kalshiConnected}
                switching={switchMode.isPending}
              />
            </section>

            {/* Cycle Mode Section */}
            <section className="bg-gray-800 rounded-lg p-5 border border-gray-700">
              <h2 className="text-lg font-semibold mb-3">Scanner Cycle</h2>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className={`px-2 py-0.5 rounded text-xs font-semibold ${isLiveCycle ? 'bg-green-700 text-green-200' : 'bg-blue-700 text-blue-200'}`}>
                    {isLiveCycle ? 'Live Cycle' : 'One-Shot'}
                  </span>
                  <span className="text-gray-400 text-sm">
                    {isLiveCycle
                      ? 'Continuous discovery + progress gate running in background'
                      : 'Run pipeline once on demand via Start Scanner'}
                  </span>
                </div>
                <button
                  onClick={handleCycleModeToggle}
                  disabled={switchCycleMode.isPending}
                  className="px-4 py-1.5 bg-blue-700 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed rounded text-sm"
                >
                  {switchCycleMode.isPending
                    ? 'Switching...'
                    : isLiveCycle
                      ? 'Switch to One-Shot'
                      : 'Switch to Live Cycle'}
                </button>
              </div>
            </section>

            {/* Strategy Section */}
            <section className="bg-gray-800 rounded-lg p-5 border border-gray-700">
              <h2 className="text-lg font-semibold mb-3">Strategy</h2>
              <select
                value={resolvedStrategy}
                onChange={handleStrategyChange}
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-gray-100"
              >
                {config.data.available_strategies.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </section>

            {/* Threshold Section */}
            <section className="bg-gray-800 rounded-lg p-5 border border-gray-700">
              <h2 className="text-lg font-semibold mb-3">Progress Threshold</h2>
              <ThresholdSlider
                value={resolvedThreshold}
                onChange={handleThresholdChange}
              />
            </section>

            {/* Save Button */}
            <button
              onClick={handleSave}
              disabled={updateConfig.isPending}
              className="w-full py-3 bg-green-700 hover:bg-green-600 disabled:opacity-50 rounded-lg font-semibold text-lg"
            >
              {updateConfig.isPending ? 'Saving...' : 'Save Configuration'}
            </button>

            <Suspense fallback={null}>
              <DiagnosticsPanel />
            </Suspense>
          </>
        )}
      </main>
    </div>
  );
}
export default memo(SettingsInner);
