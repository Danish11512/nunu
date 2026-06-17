# Adapter Contract Specification

## Purpose

Define the contract that every prediction market platform adapter must implement to integrate with the generic scanner pipeline.

---

## `MarketPlatformAdapter` Interface

```typescript
interface MarketPlatformAdapter {
  /** Human-readable provider name */
  readonly name: string;

  /** IANA timezone used for "today" classification */
  readonly timezone: string;

  // ──── Engine 1: Discovery ────

  /** Fetch all currently open markets across all events */
  fetchAllOpenMarkets(options?: DiscoveryOptions): Promise<Market[]>;

  // ──── Engine 4: Orderbook ────

  /** Fetch the current orderbook for a single market */
  fetchOrderbook(marketId: string): Promise<Orderbook>;

  /**
   * Batch fetch orderbooks for multiple markets.
   * Default implementation calls fetchOrderbook for each.
   * Override if provider has a batch endpoint.
   */
  fetchOrderbooks?(marketIds: string[]): Promise<Map<string, Orderbook>>;

  // ──── Engine 7: Trade Execution (Optional) ────

  /** Whether this adapter supports order placement */
  readonly supportsTrading: boolean;

  /**
   * Place an order. Only called after Engine 7 validation passes.
   * Not required for read-only scanners.
   */
  placeOrder?(candidate: ValidatedOrderCandidate): Promise<OrderResult>;

  // ──── Live Updates (Optional) ────

  /** Whether this adapter supports WebSocket live updates */
  readonly supportsWebSocket: boolean;

  /**
   * Create a WebSocket connection for live orderbook/market updates.
   * Return null if WebSocket is not available.
   */
  createWebSocketConnection?(marketIds: string[]): Promise<LiveConnection | null>;

  // ──── Adapter Metadata ────

  /** Provider-specific configuration */
  readonly config: PlatformConfig;
}
```

## Supporting Types

```typescript
interface DiscoveryOptions {
  status?: "open" | "all";
  limit?: number;
}

interface LiveConnection {
  /** Unique connection ID */
  id: string;

  /** Register a callback for orderbook updates */
  onOrderbookUpdate(callback: (marketId: string, book: Orderbook) => void): void;

  /** Register a callback for market lifecycle updates (status changes) */
  onMarketUpdate(callback: (market: Market) => void): void;

  /** Register a callback for trade execution updates */
  onTradeUpdate(callback: (trade: TradeUpdate) => void): void;

  /** Close the connection */
  close(): Promise<void>;
}

interface TradeUpdate {
  marketId: string;
  side: "buy" | "sell";
  outcome: "yes" | "no";
  size: number;
  price: number;
  timestamp: string;
}

interface OrderResult {
  success: boolean;
  orderId?: string;
  filledSize?: number;
  averagePrice?: number;
  error?: string;
}

interface ValidatedOrderCandidate extends OrderCandidate {
  validationTimestamp: string;
  validationLatencyMs: number;
  preTradeMarket: Market;
  preTradeOrderbook: Orderbook;
  preTradeStats: MarketOrderbookStats;
}

interface PlatformConfig {
  /** REST API base URLs */
  restUrls: string[];
  /** WebSocket URL (if applicable) */
  websocketUrl?: string;
  /** API rate limit (requests per second) */
  rateLimit: number;
  /** Whether authentication is needed for trading */
  requiresAuth: boolean;
}
```

## Contract Rules

1. **Adapters must not filter** — return all open markets, all orderbook levels. Filtering is the pipeline's job.
2. **Adapters must throw typed errors** — `RateLimitError`, `AuthError`, `NetworkError`, `InvalidResponseError`.
3. **Adapters must handle pagination** internally — the pipeline gets a complete result.
4. **Adapters must normalize timestamps** to ISO 8601 UTC strings.
5. **Adapters must normalize prices** to dollar values (not cents, not token units).
6. **Adapters should batch** when the provider supports it, but must also work with individual requests.
