export const API_BASE = "/api/v1";

export const CANDIDATE_FILTERS = {
  ALL: "all",
  ACTIONABLE: "actionable",
  MANUAL_REVIEW: "manual_review",
} as const;

export const WS_CHANNELS = {
  SCANNER: "scanner",
  EVENTS: "events",
  CANDIDATES: "candidates",
  TRADES: "trades",
} as const;

export const DEFAULT_PAGE_SIZE = 50;
export const DEFAULT_ORDERBOOK_DEPTH = 10;
export const WS_RECONNECT_DELAY_MS = 3000;
