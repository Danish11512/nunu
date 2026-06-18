import { useState } from 'react';
import { useScannerConfig } from '../hooks/useScannerConfig';
import { ScannerMode } from '../lib/types';
import ModeSelector from '../components/ModeSelector';
import ThresholdSlider from '../components/ThresholdSlider';

export default function Settings() {
  const { config, updateConfig, switchMode } = useScannerConfig();
  const [threshold, setThreshold] = useState<number | null>(null);
  const [selectedStrategy, setSelectedStrategy] = useState<string | null>(null);

  const resolvedThreshold = threshold ?? config.data?.threshold_percent ?? 65;
  const resolvedStrategy = selectedStrategy ?? config.data?.strategy.active_profile ?? '';

  const handleSave = () => {
    updateConfig.mutate({
      threshold_percent: resolvedThreshold,
      strategy: resolvedStrategy,
    });
  };

  const currentMode = config.data?.mode ?? ScannerMode.DRY_RUN;

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      <header className="bg-gray-800 border-b border-gray-700 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <a href="/" className="text-blue-400 hover:text-blue-300">&larr; Dashboard</a>
          <h1 className="text-xl font-bold">Settings</h1>
        </div>
      </header>

      <main className="max-w-2xl mx-auto p-6 space-y-8">
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
                onSwitch={(mode) => switchMode.mutate({ mode })}
                hasCredentials={config.data.has_credentials}
                switching={switchMode.isPending}
              />
            </section>

            {/* Strategy Section */}
            <section className="bg-gray-800 rounded-lg p-5 border border-gray-700">
              <h2 className="text-lg font-semibold mb-3">Strategy</h2>
              <select
                value={resolvedStrategy}
                onChange={(e) => setSelectedStrategy(e.target.value)}
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-gray-100"
              >
                {config.data.available_strategies.map((s) => (
                  <option key={s.name} value={s.name}>
                    {s.name} - {s.description}
                  </option>
                ))}
              </select>
            </section>

            {/* Threshold Section */}
            <section className="bg-gray-800 rounded-lg p-5 border border-gray-700">
              <h2 className="text-lg font-semibold mb-3">Progress Threshold</h2>
              <ThresholdSlider
                value={resolvedThreshold}
                onChange={(value) => setThreshold(value)}
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
          </>
        )}
      </main>
    </div>
  );
}
