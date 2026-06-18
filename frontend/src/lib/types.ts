// ============================================================
// Enum / Literal Types
// ============================================================

export type ScannerMode = "dry_run" | "read_only" | "live";
export type CandidateSide = "yes" | "no" | "tie" | "none";
export type TradeStatus = "open" | "closed" | "cancelled";

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
  duration_ms?: number;
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
  uptime_seconds: number | null;
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
  mode?: string;
  strategy?: string;
  threshold_percent?: number;
}

export interface StartResult {
  scanner_id: string;
  started_at: string;
  events_processed: number;
  candidates_generated: number;
  trades_executed: number;
}

export interface StopResult {
  stopped_at: string;
  scan_duration_seconds: number | null;
  events_processed: number;
  candidates_generated: number;
}

// ============================================================
// Events (GET /api/v1/events)
// ============================================================

export interface EventsQueryParams {
  min_progress?: number;
  has_candidate?: boolean;
  sort_by?: "progress" | "market_count" | "total_orders";
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
  candidate_side: string | null;
}

// ============================================================
// Event Detail (GET /api/v1/events/{event_ticker})
// ============================================================

export interface RankedMarket {
  market_ticker: string;
  volume: number;
  spread_cents: number;
  yes_price_cents: number;
  no_price_cents: number;
  yes_price: number;
  no_price: number;
  rank: number;
  score: number;
}

export interface ValidatedCandidate {
  event_ticker: string;
  market_ticker: string;
  side: string;
  price_cents: number;
  price: number;
  confidence: number;
  volume: number;
  progress_pct: number;
  is_valid: boolean;
  validation_errors: string[];
  risk_score: number;
  estimated_entry_price_cents: number;
  estimated_entry_price: number;
  estimated_exit_price_cents: number;
  estimated_exit_price: number;
  max_contracts: number;
}

export interface EventDetail {
  event_ticker: string;
  event_title: string;
  top_markets: RankedMarket[];
  total_volume: number;
  num_top_markets: number;
  candidate: ValidatedCandidate | null;
}

// ============================================================
// Orderbook (GET /api/v1/events/{event_ticker}/orderbook)
// ============================================================

export interface OrderbookLevel {
  price: number;
  price_cents: number;
  count: number;
}

export interface OrderbookSnapshot {
  market_ticker: string;
  event_ticker: string;
  yes_bids: OrderbookLevel[];
  no_bids: OrderbookLevel[];
  fetch_time: string | null;
}

// ============================================================
// Candidates
// ============================================================

export interface ApproveCandidateRequest {
  max_price?: number;
  size_override?: number;
}

export interface ApproveResult {
  event_ticker: string;
  market_ticker: string;
  side: string;
  price_cents: number;
  price: number;
  volume: number;
  approved: boolean;
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
  side: string;
  entry_price_cents: number;
  entry_price: number;
  exit_price_cents: number | null;
  exit_price: number | null;
  quantity: number;
  entry_time: string | null;
  exit_time: string | null;
  pnl: number;
  status: TradeStatus;
  mode: string;
  error: string | null;
}

export interface TradeListResponse {
  trades: TradeRecord[];
  total: number;
  limit: number;
  offset: number;
}

// ============================================================
// Config
// ============================================================

export interface UpdateConfigRequest {
  strategy?: string;
  threshold_percent?: number;
}

export interface ScannerConfigResponse {
  mode: string;
  strategy: {
    name: string | null;
    params: Record<string, unknown>;
  };
  available_strategies: string[];
  threshold_percent: number;
  kalshi: {
    connected: boolean;
    base_url: string;
    rate_limit: number;
  };
  scanner: {
    min_markets_per_event: number;
    min_volume_before_entry: number;
    min_side_signal_strength: number;
    poll_interval_seconds: number;
  };
  risk: {
    max_position_size_per_market: number;
    max_total_positions: number;
    max_daily_trades: number;
  };
}

// ============================================================
// Mode Switch
// ============================================================

export interface SwitchModeRequest {
  mode: ScannerMode;
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
