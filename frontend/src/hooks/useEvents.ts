import { useQuery } from '@tanstack/react-query';
import { ScannerAPI } from '../lib/api';
import type { EventSummary, EventsQueryParams } from '../lib/types';

const api = new ScannerAPI();

export function useEvents(params?: EventsQueryParams) {
  return useQuery<EventSummary[]>({
    queryKey: ['events', params],
    queryFn: async () => {
      const res = await api.getEvents(params);
      if (!res.success || !res.data) throw new Error(res.error?.message ?? 'Failed to fetch events');
      return res.data;
    },
    refetchInterval: 30_000,
  });
}
