import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ScannerAPI } from '../lib/api';
import type { ScannerConfigResponse, UpdateConfigRequest, SwitchModeRequest, SwitchCycleModeRequest } from '../lib/types';

const api = new ScannerAPI();

export function useScannerConfig() {
  const queryClient = useQueryClient();

  const config = useQuery<ScannerConfigResponse>({
    queryKey: ['config'],
    queryFn: async () => {
      const res = await api.getConfig();
      if (!res.success || !res.data) throw new Error(res.error?.message ?? 'Failed to fetch config');
      return res.data;
    },
  });

  const updateConfig = useMutation({
    mutationFn: async (req: UpdateConfigRequest) => {
      const res = await api.updateConfig(req);
      if (!res.success) throw new Error(res.error?.message ?? 'Failed to update config');
      return res.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['config'] }),
  });

  const switchMode = useMutation({
    mutationFn: async (req: SwitchModeRequest) => {
      const res = await api.switchMode(req);
      if (!res.success) throw new Error(res.error?.message ?? 'Failed to switch mode');
      return res.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['config'] }),
  });

  const switchCycleMode = useMutation({
    mutationFn: async (req: SwitchCycleModeRequest) => {
      const res = await api.switchCycleMode(req);
      if (!res.success) throw new Error(res.error?.message ?? 'Failed to switch cycle mode');
      return res.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['config'] }),
  });

  return { config, updateConfig, switchMode, switchCycleMode };
}
