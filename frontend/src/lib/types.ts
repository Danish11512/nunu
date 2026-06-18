// ============================================================
// Constants (enforced by backend/kalshi docs)
// ============================================================

/** Base side values matching Kalshi API docs */
export const Side = {
  YES: "yes",
  NO: "no",
} as const;
export type Side = (typeof Side)[keyof typeof Side];

/** Extended side used by CandidateResponse (adds tie/none) */
export const CandidateSide = {
  ...Side,
  TIE: "tie",
  NONE: "none",
} as const;
export type CandidateSide = (typeof CandidateSide)[keyof typeof CandidateSide];

export const ScannerMode = {
  DRY_RUN: "dry_run",
  READ_ONLY: "read_only",
  LIVE: "live",
} as const;
export type ScannerMode = (typeof ScannerMode)[keyof typeof ScannerMode];

/** "one-shot" | "live" — used by StartScannerRequest */
export const StartMode = {
  ONE_SHOT: "one-shot",
  LIVE: "live",
} as const;
export type StartMode = (typeof StartMode)[keyof typeof StartMode];

/** "dry_run" | "live" — used by SwitchModeRequest and TradeRecord */
export const LiveMode = {
  DRY_RUN: "dry_run",
  LIVE: "live",
} as const;
export type LiveMode = (typeof LiveMode)[keyof typeof LiveMode];

export const TradeStatus = {
  FILLED: "filled",
  PARTIAL: "partial",
  FAILED: "failed",
} as const;
export type TradeStatus = (typeof TradeStatus)[keyof typeof TradeStatus];

export const MarketStatus = {
  UNOPENED: "unopened",
  OPEN: "open",
  CLOSED: "closed",
  SETTLED: "settled",
} as const;
export type MarketStatus = (typeof MarketStatus)[keyof typeof MarketStatus];

// ============================================================
// Response Envelope
// ============================================================

export interface APIError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface ResponseMeta {
  timestamp: string;
  duration_ms: number;
}

export interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: APIError;
  meta?: ResponseMeta;
}

// ============================================================
// Scanner Status (GET /api/v1/scanner/status)
// ============================================================

export interface ScannerStatus {
  mode: ScannerMode;
  is_running: boolean;
  connected_to_kalshi: boolean;
  uptime_seconds: number;
  markets_tracked: number;
  events_tracked: number;
  active_candidates: number;
  last_discovery: string | null;
  last_progress_check: string | null;
}

// ============================================================
// Scanner Control
// ============================================================

export interface StartScannerRequest {
  mode?: StartMode;
  strategy?: string;
  threshold_percent?: number;
}

export interface StartResult {
  scanner_id: string;
  started_at: string;
}

export interface StopResult {
  stopped_at: string;
  scan_duration_seconds: number;
  events_processed: number;
  candidates_generated: number;
}

// ============================================================
// Events (GET /api/v1/events)
// ============================================================

export interface EventsQueryParams {
  min_progress?: number;
  has_candidate?: boolean;
  sort_by?: "total_orders" | "progress" | "market_count";
}

export interface MarketSummary {
  ticker: string;
  title: string;
  yes_bid: number | null;
  no_bid: number | null;
  total_resting_order_quantity: number;
  yes_order_quantity: number;
  no_order_quantity: number;
  volume_24h: number;
}

export interface EventSummary {
  event_ticker: string;
  market_count: number;
  live_market_count: number;
  total_resting_order_quantity: number;
  active_orderbook_market_count: number;
  top_markets: MarketSummary[];
  event_progress_percent: number;
  has_active_candidate: boolean;
  candidate_side: Side | null;
}

// ============================================================
// Event Detail (GET /api/v1/events/{event_ticker})
// ============================================================

export interface MarketDetail {
  ticker: string;
  title: string;
  status: MarketStatus;
  open_time: string;
  close_time: string;
  expected_expiration_time: string | null;
  latest_expiration_time: string | null;
  yes_bid: number | null;
  yes_ask: number | null;
  no_bid: number | null;
  no_ask: number | null;
  total_resting_order_quantity: number;
  yes_order_quantity: number;
  no_order_quantity: number;
  depth_level_count: number;
  best_yes_bid: number | null;
  best_no_bid: number | null;
  volume_24h: number;
  total_volume: number;
  rank: number;
}

export interface CandidateResponse {
  event_ticker: string;
  threshold_percent: number;
  event_progress_percent: number;
  event_passes_progress_threshold: boolean;
  selected_market_ticker: string | null;
  selected_market_title: string | null;
  most_bet_side: CandidateSide;
  yes_order_quantity: number;
  no_order_quantity: number;
  total_resting_order_quantity: number;
  should_create_order_candidate: boolean;
  requires_manual_review: boolean;
  reasons: string[];
}

export interface EventDetail {
  event_ticker: string;
  market_count: number;
  same_day_live_market_count: number;
  total_event_resting_order_quantity: number;
  active_orderbook_market_count: number;
  event_progress_percent: number;
  threshold_percent: number;
  all_markets_ranked: MarketDetail[];
  active_candidate: CandidateResponse | null;
}

// ============================================================
// Orderbook (GET /api/v1/events/{event_ticker}/orderbook)
// ============================================================

export interface OrderbookLevel {
  price: number;
  size: number;
}

export interface OrderbookSnapshot {
  market_ticker: string;
  event_ticker: string;
  yes_bids: OrderbookLevel[];
  no_bids: OrderbookLevel[];
  timestamp: string;
}

// ============================================================
// Candidates
// ============================================================

export interface ApproveCandidateRequest {
  max_price?: number;
  size_override?: number;
}

export interface ApproveCandidateResult {
  candidate_id: string;
  approved: boolean;
  validation: Record<string, unknown>;
  order_result: Record<string, unknown> | null;
}

export interface RejectCandidateRequest {
  reason?: string;
}

// ============================================================
// Trades (GET /api/v1/trades)
// ============================================================

export interface TradeRecord {
  trade_id: string;
  event_ticker: string;
  market_ticker: string;
  side: Side;
  price: number;
  size: number;
  mode: LiveMode;
  status: TradeStatus;
  timestamp: string;
  validation_latency_ms: number;
}

// ============================================================
// Config
// ============================================================

export interface UpdateConfigRequest {
  strategy?: string;
  threshold_percent?: number;
}

export interface ScannerConfigResponse {
  mode: ScannerMode;
  strategy: {
    active_profile: string;
    profiles: Record<string, unknown>;
  };
  threshold_percent: number;
  available_strategies: Array<{ name: string; description: string }>;
  kalshi_connected: boolean;
  has_credentials: boolean;
}

// ============================================================
// Mode Switch
// ============================================================

export interface SwitchModeRequest {
  mode: LiveMode;
  confirm?: boolean;
}

export interface SwitchModeResult {
  previous_mode: string;
  current_mode: string;
  switched_at: string;
  requires_auth: boolean;
  auth_configured: boolean;
}

// ============================================================
// WebSocket
// ============================================================

export interface WSMessage<T = unknown> {
  type: string;
  data: T;
  timestamp: string;
}
