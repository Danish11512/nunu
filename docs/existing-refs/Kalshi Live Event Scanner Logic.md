# Kalshi Same-Day Live Event Scanner Logic

## Purpose

Build a Kalshi scanner/app that:

1. Finds any event that is live today and ends today.
2. Groups markets into events.
3. Shows the top 3 markets inside each event by current resting order quantity.
4. After a user-configurable event-progress threshold passes, selects:
   - the most-bet market
   - the most-bet side: YES or NO
5. Creates an order candidate.
6. Runs pre-trade validation before any actual order placement.

The logic must run as separate sequential engines.

```txt
Engine 1: Fetch open markets
Engine 2: Classify same-day live markets
Engine 3: Group same-day live markets into events
Engine 4: Fetch orderbooks for child markets
Engine 5: Rank top markets inside each event by current orders
Engine 6: Apply event progress threshold and select most-bet market/side
Engine 7: Pre-trade validation
Engine 8: Final output/orchestration
```

Do **not** use category allowlists, keyword allowlists, whitelists, or manual topic filters.

---

# Core Kalshi Model

Kalshi structure:

```txt
Series -> Event -> Market
```

Definitions:

```txt
Series = recurring category/template.
Event = grouped real-world occurrence.
Market = tradable binary outcome inside an event.
```

Important rule:

```txt
Orders are placed against markets, not abstract events.
Events are used for grouping and reasoning.
```

Therefore:

```txt
Classify markets first.
Group by event_ticker.
Fetch orderbooks for those markets.
Rank markets inside each event.
Create order candidates only after the progress threshold passes.
Validate again before order placement.
```

---

# Engine 1: Open Market Fetch Engine

## Purpose

Pull all currently open Kalshi markets.

Endpoint:

```txt
GET https://external-api.kalshi.com/trade-api/v2/markets
```

Recommended request:

```txt
GET /markets?status=open&limit=1000&mve_filter=exclude
```

Use pagination with `cursor`.

## Engine 1 Output

```ts
type OpenMarketFetchOutput = {
  scanned_market_count: number;
  markets: Market[];
};
```

---

# Engine 2: Same-Day Live Market Classification Engine

## Purpose

Classify which markets are:

```txt
open now
happening today
ending today
```

## Primary Rule

```txt
SAME_DAY_LIVE_MARKET =
  market.status == "open"
  AND market.open_time <= now
  AND market.close_time > now
  AND expected_expiration_time is today in America/New_York
  AND latest_expiration_time is today in America/New_York
```

This engine must not filter by:

```txt
orderbook
volume
liquidity
spread
category
keyword
```

## Engine 2 Output

```ts
type SameDayLiveMarketOutput = Array<{
  market: Market;
  classification: MarketClassification;
}>;
```

---

# Engine 3: Same-Day Live Event Grouping Engine

## Purpose

Group qualifying markets by:

```txt
event_ticker
```

## Event Inclusion Rule

```txt
event qualifies if ANY child market passes SAME_DAY_LIVE_MARKET
```

## Engine 3 Output

```ts
type ClassifiedEvent = {
  event_ticker: string;
  market_count: number;
  same_day_live_market_count: number;
  same_day_live_markets: Array<{
    market: Market;
    classification: MarketClassification;
  }>;
};
```

---

# Engine 4: Market Orderbook Fetch Engine

## Purpose

For each same-day live event, fetch orderbooks for each same-day-live child market.

Endpoint:

```txt
GET /markets/{ticker}/orderbook
```

This engine enriches events. It does not decide whether an event is same-day live.

## Orderbook Meaning

Kalshi orderbooks return YES bids and NO bids.

They do not directly return asks.

For current order ranking, use:

```txt
orderbook_fp.yes_dollars
orderbook_fp.no_dollars
```

Each level:

```ts
type OrderbookLevel = [string, string]; // [price_dollars, count_fp]
```

---

# Engine 5: Top Markets By Current Orders Ranking Engine

## Purpose

Rank markets inside each event by current resting order quantity.

This answers:

```txt
Which markets inside this event currently have the most orders/bidding activity?
```

## Ranking Metric

```txt
total_resting_order_quantity =
  sum(orderbook_fp.yes_dollars[*].count_fp)
  + sum(orderbook_fp.no_dollars[*].count_fp)
```

Also calculate:

```txt
yes_order_quantity
no_order_quantity
depth_level_count
best_yes_bid
best_no_bid
volume_24h
total_volume
```

Sort markets inside each event by:

```txt
1. total_resting_order_quantity DESC
2. depth_level_count DESC
3. volume_24h DESC
4. total_volume DESC
```

Return:

```txt
top 3 markets by total_resting_order_quantity
```

Important:

```txt
This engine ranks child markets.
It should not remove the event from the discovery output.
```

---

# Engine 6: Event Progress Threshold + Most-Bet Market/Side Selection Engine

## Purpose

Create an order candidate only after a configured percentage of the event has passed.

The engine should:

```txt
1. Take a user-defined progress threshold.
2. Default to 65% if not provided.
3. Determine whether the event has passed that threshold.
4. Select the most-bet market inside the event.
5. Select the most-bet side inside that market: YES or NO.
6. Return an order candidate, not an automatic order.
```

Default:

```txt
event_progress_threshold_percent = 65
```

User override example:

```txt
event_progress_threshold_percent = 50
```

## Event Progress Definition

Use the selected most-bet market to estimate event progress.

Recommended default:

```txt
event_start_time = selected_market.open_time
event_end_time = selected_market.expected_expiration_time
```

Fallbacks:

```txt
If expected_expiration_time is missing:
  use latest_expiration_time

If latest_expiration_time is missing:
  use close_time
```

Progress formula:

```txt
elapsed_ms = now - event_start_time
total_ms = event_end_time - event_start_time

event_progress_percent = (elapsed_ms / total_ms) * 100
```

Clamp output:

```txt
event_progress_percent = max(0, min(100, event_progress_percent))
```

Threshold rule:

```txt
event_passes_progress_threshold =
  event_progress_percent >= user_threshold_percent
```

## Most-Bet Market Definition

Use **most current orders** as the primary ranking.

Selected market:

```txt
most_bet_market =
  first market in all_same_day_live_markets_ranked
```

This assumes Engine 5 has already ranked markets by:

```txt
total_resting_order_quantity DESC
depth_level_count DESC
volume_24h DESC
total_volume DESC
```

## Most-Bet Side Definition

Inside the selected market:

```txt
if yes_order_quantity > no_order_quantity:
  most_bet_side = "yes"

else if no_order_quantity > yes_order_quantity:
  most_bet_side = "no"

else if total_resting_order_quantity > 0:
  most_bet_side = "tie"

else:
  most_bet_side = "none"
```

Default behavior:

```txt
If side == "tie", do not automatically create an order candidate.
If side == "none", do not create an order candidate.
```

## Order Candidate Rule

Create an order candidate only if:

```txt
event passes progress threshold
AND selected market exists
AND selected market still passes SAME_DAY_LIVE_MARKET
AND selected market has total_resting_order_quantity > 0
AND most_bet_side is "yes" or "no"
```

This engine does not place orders.

It only returns candidates to Engine 7.

---

# Engine 7: Pre-Trade Validation Engine

## Purpose

Validate a selected market immediately before any actual order placement.

Before placing any order:

```txt
1. Take the order candidate from Engine 6.
2. Re-fetch the selected market.
3. Confirm the market still passes SAME_DAY_LIVE_MARKET.
4. Re-fetch the market orderbook.
5. Recalculate total resting quantity and YES/NO side.
6. Confirm the selected side is still valid.
7. Confirm bid/ask/spread/size are acceptable.
8. Confirm the market has not moved significantly since selection.
9. Place order only if still valid.
```

Never place an order based only on stale scanner output.

---

# Engine 8: Final Output / Orchestration Engine

## Purpose

Run all engines in sequence and return structured output.

Final output should include:

```txt
scanned_market_count
same_day_live_event_count
same_day_live_events
progress_based_order_candidates
actionable_candidates
manual_review_candidates
```

---

# TypeScript Reference Implementation

## Shared Types

```ts
type Market = {
  ticker: string;
  event_ticker: string;
  status: "unopened" | "open" | "closed" | "settled" | string;

  open_time: string;
  close_time: string;

  expected_expiration_time?: string;
  latest_expiration_time?: string;
  expiration_time?: string;

  yes_bid_dollars?: string;
  yes_ask_dollars?: string;
  no_bid_dollars?: string;
  no_ask_dollars?: string;

  volume_fp?: string;
  volume_24h_fp?: string;
  liquidity_dollars?: string;

  title?: string;
  subtitle?: string;
  category?: string;
  series_ticker?: string;
};

type MarketClassification = {
  ticker: string;
  event_ticker: string;
  liveNow: boolean;
  expectedToResolveToday: boolean;
  latestExpirationToday: boolean;
  sameDayLiveMarket: boolean;
  reasons: string[];
};

type OrderbookLevel = [string, string];

type KalshiOrderbookResponse = {
  orderbook_fp?: {
    yes_dollars?: OrderbookLevel[];
    no_dollars?: OrderbookLevel[];
  };
  orderbook?: {
    yes?: Array<[number, number]>;
    no?: Array<[number, number]>;
  };
};

type MarketOrderbookStats = {
  ticker: string;
  event_ticker: string;

  total_resting_order_quantity: number;
  yes_order_quantity: number;
  no_order_quantity: number;

  depth_level_count: number;
  best_yes_bid: number | null;
  best_no_bid: number | null;

  volume_24h: number;
  total_volume: number;
};

type ClassifiedEvent = {
  event_ticker: string;
  market_count: number;
  same_day_live_market_count: number;
  same_day_live_markets: Array<{
    market: Market;
    classification: MarketClassification;
  }>;
};

type EventWithTopMarkets = {
  event_ticker: string;
  market_count: number;
  same_day_live_market_count: number;

  total_event_resting_order_quantity: number;
  active_orderbook_market_count: number;

  top_3_markets_by_current_orders: Array<{
    market: Market;
    classification: MarketClassification;
    orderbook_stats: MarketOrderbookStats;
  }>;

  all_same_day_live_markets_ranked: Array<{
    market: Market;
    classification: MarketClassification;
    orderbook_stats: MarketOrderbookStats;
  }>;
};

type OrderCandidateSide = "yes" | "no" | "tie" | "none";

type ProgressBasedOrderCandidate = {
  event_ticker: string;

  threshold_percent: number;
  event_progress_percent: number;
  event_passes_progress_threshold: boolean;

  selected_market: Market | null;
  selected_market_stats: MarketOrderbookStats | null;

  most_bet_side: OrderCandidateSide;

  yes_order_quantity: number;
  no_order_quantity: number;
  total_resting_order_quantity: number;

  should_create_order_candidate: boolean;
  requires_manual_review: boolean;

  reasons: string[];
};
```

---

## Utility Functions

```ts
function dayKeyET(date: Date): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

function sameETDay(a: Date, b: Date): boolean {
  return dayKeyET(a) === dayKeyET(b);
}

function parseDate(value?: string): Date | null {
  if (!value) return null;

  const date = new Date(value);

  return Number.isNaN(date.getTime()) ? null : date;
}

function parseNumber(value?: string | number): number {
  if (value === undefined || value === null) return 0;

  const parsed = Number(value);

  return Number.isFinite(parsed) ? parsed : 0;
}
```

---

## Engine 1 Implementation

```ts
async function fetchAllOpenMarkets(): Promise<Market[]> {
  const allMarkets: Market[] = [];
  let cursor: string | undefined = undefined;

  do {
    const url = new URL(
      "https://external-api.kalshi.com/trade-api/v2/markets"
    );

    url.searchParams.set("status", "open");
    url.searchParams.set("limit", "1000");
    url.searchParams.set("mve_filter", "exclude");

    if (cursor) {
      url.searchParams.set("cursor", cursor);
    }

    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(
        `Kalshi request failed: ${response.status} ${response.statusText}`
      );
    }

    const data = await response.json();

    allMarkets.push(...(data.markets ?? []));

    cursor = data.cursor || undefined;
  } while (cursor);

  return [...new Map(allMarkets.map(m => [m.ticker, m])).values()];
}
```

---

## Engine 2 Implementation

```ts
function classifyMarket(
  market: Market,
  now = new Date()
): MarketClassification {
  const reasons: string[] = [];

  const openTime = parseDate(market.open_time);
  const closeTime = parseDate(market.close_time);
  const expectedExpiration = parseDate(market.expected_expiration_time);
  const latestExpiration = parseDate(market.latest_expiration_time);

  const liveNow =
    market.status === "open" &&
    !!openTime &&
    !!closeTime &&
    openTime <= now &&
    closeTime > now;

  if (!liveNow) {
    reasons.push("Market is not currently live/open.");
  }

  const expectedToResolveToday =
    !!expectedExpiration && sameETDay(expectedExpiration, now);

  if (!expectedToResolveToday) {
    reasons.push("Market is not expected to resolve today.");
  }

  const latestExpirationToday =
    !!latestExpiration && sameETDay(latestExpiration, now);

  if (!latestExpirationToday) {
    reasons.push("Latest expiration is not today.");
  }

  const sameDayLiveMarket =
    liveNow && expectedToResolveToday && latestExpirationToday;

  return {
    ticker: market.ticker,
    event_ticker: market.event_ticker,
    liveNow,
    expectedToResolveToday,
    latestExpirationToday,
    sameDayLiveMarket,
    reasons,
  };
}

function getSameDayLiveMarkets(markets: Market[], now = new Date()) {
  return markets
    .map(market => ({
      market,
      classification: classifyMarket(market, now),
    }))
    .filter(x => x.classification.sameDayLiveMarket);
}
```

---

## Engine 3 Implementation

```ts
function classifyEvents(
  sameDayLiveMarkets: Array<{
    market: Market;
    classification: MarketClassification;
  }>
): ClassifiedEvent[] {
  const byEvent = new Map<
    string,
    Array<{
      market: Market;
      classification: MarketClassification;
    }>
  >();

  for (const item of sameDayLiveMarkets) {
    const existing = byEvent.get(item.market.event_ticker) ?? [];
    existing.push(item);
    byEvent.set(item.market.event_ticker, existing);
  }

  return [...byEvent.entries()].map(([eventTicker, eventMarkets]) => ({
    event_ticker: eventTicker,
    market_count: eventMarkets.length,
    same_day_live_market_count: eventMarkets.length,
    same_day_live_markets: eventMarkets,
  }));
}
```

---

## Engine 4 Implementation

```ts
async function fetchMarketOrderbook(
  ticker: string
): Promise<KalshiOrderbookResponse> {
  const url = new URL(
    `https://external-api.kalshi.com/trade-api/v2/markets/${ticker}/orderbook`
  );

  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(
      `Orderbook request failed for ${ticker}: ${response.status} ${response.statusText}`
    );
  }

  return response.json();
}
```

---

## Engine 5 Implementation

```ts
function getOrderbookLevels(orderbook: KalshiOrderbookResponse): {
  yes: OrderbookLevel[];
  no: OrderbookLevel[];
} {
  if (orderbook.orderbook_fp) {
    return {
      yes: orderbook.orderbook_fp.yes_dollars ?? [],
      no: orderbook.orderbook_fp.no_dollars ?? [],
    };
  }

  // Legacy fallback: convert cents/count numbers to string pairs.
  const legacyYes = orderbook.orderbook?.yes ?? [];
  const legacyNo = orderbook.orderbook?.no ?? [];

  return {
    yes: legacyYes.map(([price, count]) => [String(price / 100), String(count)]),
    no: legacyNo.map(([price, count]) => [String(price / 100), String(count)]),
  };
}

function sumQuantity(levels: OrderbookLevel[] = []): number {
  return levels.reduce((sum, [, count]) => sum + parseNumber(count), 0);
}

function bestBid(levels: OrderbookLevel[] = []): number | null {
  if (levels.length === 0) return null;

  return Math.max(...levels.map(([price]) => parseNumber(price)));
}

function getMarketOrderbookStats(
  market: Market,
  orderbook: KalshiOrderbookResponse
): MarketOrderbookStats {
  const { yes, no } = getOrderbookLevels(orderbook);

  const yesQty = sumQuantity(yes);
  const noQty = sumQuantity(no);

  return {
    ticker: market.ticker,
    event_ticker: market.event_ticker,

    total_resting_order_quantity: yesQty + noQty,
    yes_order_quantity: yesQty,
    no_order_quantity: noQty,

    depth_level_count: yes.length + no.length,
    best_yes_bid: bestBid(yes),
    best_no_bid: bestBid(no),

    volume_24h: parseNumber(market.volume_24h_fp),
    total_volume: parseNumber(market.volume_fp),
  };
}

async function addTopMarketsByCurrentOrders(
  event: ClassifiedEvent
): Promise<EventWithTopMarkets> {
  const marketsWithStats = await Promise.all(
    event.same_day_live_markets.map(async ({ market, classification }) => {
      const orderbook = await fetchMarketOrderbook(market.ticker);
      const orderbookStats = getMarketOrderbookStats(market, orderbook);

      return {
        market,
        classification,
        orderbook_stats: orderbookStats,
      };
    })
  );

  const ranked = [...marketsWithStats].sort((a, b) => {
    return (
      b.orderbook_stats.total_resting_order_quantity -
        a.orderbook_stats.total_resting_order_quantity ||
      b.orderbook_stats.depth_level_count -
        a.orderbook_stats.depth_level_count ||
      b.orderbook_stats.volume_24h - a.orderbook_stats.volume_24h ||
      b.orderbook_stats.total_volume - a.orderbook_stats.total_volume
    );
  });

  return {
    event_ticker: event.event_ticker,
    market_count: event.market_count,
    same_day_live_market_count: event.same_day_live_market_count,

    total_event_resting_order_quantity: ranked.reduce(
      (sum, x) => sum + x.orderbook_stats.total_resting_order_quantity,
      0
    ),

    active_orderbook_market_count: ranked.filter(
      x => x.orderbook_stats.total_resting_order_quantity > 0
    ).length,

    top_3_markets_by_current_orders: ranked.slice(0, 3),

    all_same_day_live_markets_ranked: ranked,
  };
}
```

---

## Engine 6 Implementation

```ts
function getMarketEndTimeForProgress(market: Market): Date | null {
  return (
    parseDate(market.expected_expiration_time) ??
    parseDate(market.latest_expiration_time) ??
    parseDate(market.close_time)
  );
}

function calculateMarketProgressPercent(
  market: Market,
  now = new Date()
): number {
  const start = parseDate(market.open_time);
  const end = getMarketEndTimeForProgress(market);

  if (!start || !end) return 0;

  const totalMs = end.getTime() - start.getTime();
  const elapsedMs = now.getTime() - start.getTime();

  if (totalMs <= 0) return 100;

  const rawProgress = (elapsedMs / totalMs) * 100;

  return Math.max(0, Math.min(100, rawProgress));
}

function getMostBetSide(stats: MarketOrderbookStats): OrderCandidateSide {
  if (stats.yes_order_quantity > stats.no_order_quantity) {
    return "yes";
  }

  if (stats.no_order_quantity > stats.yes_order_quantity) {
    return "no";
  }

  if (stats.total_resting_order_quantity > 0) {
    return "tie";
  }

  return "none";
}

function createProgressBasedOrderCandidate(
  event: EventWithTopMarkets,
  options: {
    thresholdPercent?: number;
    now?: Date;
  } = {}
): ProgressBasedOrderCandidate {
  const thresholdPercent = options.thresholdPercent ?? 65;
  const now = options.now ?? new Date();

  const reasons: string[] = [];

  const selected = event.all_same_day_live_markets_ranked[0];

  if (!selected) {
    reasons.push("No same-day live market exists in event.");

    return {
      event_ticker: event.event_ticker,
      threshold_percent: thresholdPercent,
      event_progress_percent: 0,
      event_passes_progress_threshold: false,
      selected_market: null,
      selected_market_stats: null,
      most_bet_side: "none",
      yes_order_quantity: 0,
      no_order_quantity: 0,
      total_resting_order_quantity: 0,
      should_create_order_candidate: false,
      requires_manual_review: false,
      reasons,
    };
  }

  const selectedMarket = selected.market;
  const selectedStats = selected.orderbook_stats;

  const eventProgressPercent = calculateMarketProgressPercent(
    selectedMarket,
    now
  );

  const eventPassesProgressThreshold =
    eventProgressPercent >= thresholdPercent;

  if (!eventPassesProgressThreshold) {
    reasons.push(
      `Event has not passed progress threshold. Progress=${eventProgressPercent.toFixed(
        2
      )}%, threshold=${thresholdPercent}%.`
    );
  }

  const sameDayLive = classifyMarket(selectedMarket, now).sameDayLiveMarket;

  if (!sameDayLive) {
    reasons.push("Selected market no longer passes same-day live classification.");
  }

  if (selectedStats.total_resting_order_quantity <= 0) {
    reasons.push("Selected market has no resting order quantity.");
  }

  const mostBetSide = getMostBetSide(selectedStats);

  if (mostBetSide === "tie") {
    reasons.push("YES and NO have equal resting order quantity.");
  }

  if (mostBetSide === "none") {
    reasons.push("No most-bet side exists because order quantity is zero.");
  }

  const shouldCreateOrderCandidate =
    eventPassesProgressThreshold &&
    sameDayLive &&
    selectedStats.total_resting_order_quantity > 0 &&
    (mostBetSide === "yes" || mostBetSide === "no");

  return {
    event_ticker: event.event_ticker,

    threshold_percent: thresholdPercent,
    event_progress_percent: eventProgressPercent,
    event_passes_progress_threshold: eventPassesProgressThreshold,

    selected_market: selectedMarket,
    selected_market_stats: selectedStats,

    most_bet_side: mostBetSide,

    yes_order_quantity: selectedStats.yes_order_quantity,
    no_order_quantity: selectedStats.no_order_quantity,
    total_resting_order_quantity: selectedStats.total_resting_order_quantity,

    should_create_order_candidate: shouldCreateOrderCandidate,
    requires_manual_review: mostBetSide === "tie",

    reasons,
  };
}

function createProgressBasedOrderCandidates(
  events: EventWithTopMarkets[],
  options: {
    thresholdPercent?: number;
    now?: Date;
  } = {}
) {
  const candidates = events.map(event =>
    createProgressBasedOrderCandidate(event, options)
  );

  return {
    threshold_percent: options.thresholdPercent ?? 65,

    candidate_count: candidates.filter(
      candidate => candidate.should_create_order_candidate
    ).length,

    candidates,

    actionable_candidates: candidates.filter(
      candidate => candidate.should_create_order_candidate
    ),

    manual_review_candidates: candidates.filter(
      candidate => candidate.requires_manual_review
    ),
  };
}
```

---

## Engine 7 Implementation

```ts
async function validateCandidateBeforeTrade(
  candidate: ProgressBasedOrderCandidate
) {
  if (!candidate.should_create_order_candidate || !candidate.selected_market) {
    return {
      canTrade: false,
      reason: "Candidate is not actionable.",
      candidate,
    };
  }

  const market = candidate.selected_market;

  const latestMarketResponse = await fetch(
    `https://external-api.kalshi.com/trade-api/v2/markets/${market.ticker}`
  );

  if (!latestMarketResponse.ok) {
    throw new Error(`Failed to re-fetch market ${market.ticker}`);
  }

  const latestMarketData = await latestMarketResponse.json();
  const latestMarket = latestMarketData.market ?? latestMarketData;

  const classification = classifyMarket(latestMarket);

  if (!classification.sameDayLiveMarket) {
    return {
      canTrade: false,
      reason: "Market no longer passes same-day live classification.",
      classification,
    };
  }

  const orderbook = await fetchMarketOrderbook(market.ticker);
  const stats = getMarketOrderbookStats(latestMarket, orderbook);
  const currentSide = getMostBetSide(stats);

  if (currentSide !== candidate.most_bet_side) {
    return {
      canTrade: false,
      reason: "Most-bet side changed during validation.",
      previous_side: candidate.most_bet_side,
      current_side: currentSide,
      stats,
    };
  }

  return {
    canTrade: true,
    latestMarket,
    classification,
    orderbook,
    orderbook_stats: stats,
    side: currentSide,
  };
}
```

---

## Engine 8 Implementation

```ts
async function runSameDayLiveEventScannerWithOrderCandidates(options: {
  thresholdPercent?: number;
  now?: Date;
} = {}) {
  const openMarkets = await fetchAllOpenMarkets();

  const sameDayLiveMarkets = getSameDayLiveMarkets(
    openMarkets,
    options.now ?? new Date()
  );

  const sameDayLiveEvents = classifyEvents(sameDayLiveMarkets);

  const eventsWithTopMarkets = await Promise.all(
    sameDayLiveEvents.map(event => addTopMarketsByCurrentOrders(event))
  );

  const progressBasedCandidates = createProgressBasedOrderCandidates(
    eventsWithTopMarkets,
    {
      thresholdPercent: options.thresholdPercent ?? 65,
      now: options.now ?? new Date(),
    }
  );

  return {
    scanned_market_count: openMarkets.length,
    same_day_live_event_count: eventsWithTopMarkets.length,
    same_day_live_events: eventsWithTopMarkets,
    progress_based_order_candidates: progressBasedCandidates,
  };
}
```

---

# Most Bets vs Most Current Orders

There are two different concepts.

## Most executed bets/trades

Use market fields:

```txt
volume_24h_fp
volume_fp
```

Ranking:

```txt
volume_24h_fp DESC
```

This answers:

```txt
Which markets have people actually traded the most recently?
```

## Most current orders/bidding activity

Use orderbook fields:

```txt
orderbook_fp.yes_dollars
orderbook_fp.no_dollars
```

Ranking:

```txt
total_resting_order_quantity DESC
```

This answers:

```txt
Which markets currently have the most orders sitting in the book?
```

For this app, “most-bet market” means:

```txt
market with the highest total_resting_order_quantity
```

For this app, “most-bet side” means:

```txt
YES if yes_order_quantity > no_order_quantity
NO if no_order_quantity > yes_order_quantity
tie if equal and non-zero
none if both are zero
```

---


---

# Non-Empty Events / Markets + Live Update Strategy

## Purpose

This section defines how to fetch same-day live events/markets, detect which ones are non-empty, and keep rankings updated over time.

Important separation:

```txt
same_day_live_event = lifecycle-based discovery
non_empty_event = same_day_live_event + evidence of market activity
ranked_event = non_empty_event with child markets ranked by current orders
order_candidate = ranked_event + progress threshold + selected side
```

Do not use non-empty checks to decide if an event exists. Use non-empty checks to prioritize and rank events/markets.

---

## Non-Empty Definitions

### Non-Empty Market

A market is non-empty if:

```txt
market is SAME_DAY_LIVE_MARKET
AND (
  market has current orderbook depth
  OR market has recent executed volume/trades
)
```

Primary current-order definition:

```txt
non_empty_market_by_orders =
  total_resting_order_quantity > 0
```

Where:

```txt
total_resting_order_quantity =
  sum(orderbook_fp.yes_dollars[*].count_fp)
  + sum(orderbook_fp.no_dollars[*].count_fp)
```

Secondary executed-trade definition:

```txt
non_empty_market_by_volume =
  volume_24h_fp > 0
  OR volume_fp > 0
```

Recommended combined definition:

```txt
non_empty_market =
  SAME_DAY_LIVE_MARKET
  AND (
    total_resting_order_quantity > 0
    OR volume_24h_fp > 0
  )
```

### Non-Empty Event

An event is non-empty if:

```txt
ANY child same-day live market is non-empty
```

Do not require every child market to have orders.

Multi-market events often have most activity concentrated in the top 1-3 markets.

---

# Live Update Architecture

Use a hybrid model:

```txt
Startup:
  1. REST snapshot of open markets.
  2. Same-day live lifecycle filter.
  3. Group by event_ticker.
  4. Batch/single fetch orderbooks.
  5. Rank top markets inside each event.
  6. Create progress-based order candidates if threshold passes.

Runtime:
  7. Poll market discovery periodically.
  8. Subscribe to WebSocket orderbook updates if available.
  9. Subscribe to WebSocket trades if available.
  10. Subscribe to market lifecycle/status updates if available.
  11. Re-rank only the affected event when a child market updates.
  12. Re-run progress threshold checks every X seconds.
  13. Re-fetch selected market/orderbook before any order placement.
```

---

# Update Engine A: Discovery Poller

## Purpose

Periodically catch:

```txt
newly opened markets
markets that are no longer open
changed close/expiration times
new same-day live events
events that should be removed
```

Recommended interval:

```txt
30-60 seconds
```

Endpoint:

```txt
GET /markets?status=open&limit=1000&mve_filter=exclude
```

Optional incremental optimization if supported:

```txt
min_updated_ts
```

Discovery poller responsibilities:

```txt
1. Fetch open markets.
2. Dedupe by ticker.
3. Re-run same-day live classifier.
4. Group by event_ticker.
5. Compare to previous state.
6. Identify added/removed/changed markets.
7. Trigger orderbook snapshot for new markets.
8. Trigger event rerank for changed events.
```

Output:

```ts
type DiscoveryPollerOutput = {
  markets: Market[];
  same_day_live_markets: Array<{
    market: Market;
    classification: MarketClassification;
  }>;
  same_day_live_events: ClassifiedEvent[];
  added_market_tickers: string[];
  removed_market_tickers: string[];
  changed_market_tickers: string[];
};
```

---

# Update Engine B: Orderbook Snapshot Loader

## Purpose

Build an initial orderbook state for same-day live markets.

Use this:

```txt
on startup
after discovery poller finds new markets
after WebSocket reconnect
before pre-trade validation
```

Single-market endpoint:

```txt
GET /markets/{ticker}/orderbook
```

Batch endpoint if available:

```txt
GET /markets/orderbooks?tickers=TICKER1,TICKER2,TICKER3
```

Snapshot loader responsibilities:

```txt
1. Take same-day live market tickers.
2. Fetch orderbooks.
3. Compute orderbook stats.
4. Store stats by ticker.
5. Trigger event rerank for affected events.
```

Output:

```ts
type OrderbookSnapshotOutput = {
  orderbook_stats_by_ticker: Map<string, MarketOrderbookStats>;
  non_empty_market_tickers: string[];
  affected_event_tickers: string[];
};
```

---

# Update Engine C: WebSocket Live Updater

## Purpose

Keep local market/orderbook state current after the REST snapshot.

Use WebSockets for:

```txt
orderbook updates
trade executions
market lifecycle/status updates
```

Required state:

```ts
type LiveState = {
  marketsByTicker: Map<string, Market>;
  orderbookStatsByTicker: Map<string, MarketOrderbookStats>;
  eventMarkets: Map<string, Set<string>>;
  rankedEvents: Map<string, EventWithTopMarkets>;
  candidatesByEvent: Map<string, ProgressBasedOrderCandidate>;
};
```

On orderbook update:

```txt
1. Identify market ticker.
2. Patch local orderbook state.
3. Recalculate MarketOrderbookStats.
4. Find market.event_ticker.
5. Re-rank only that event.
6. Recalculate most-bet market and most-bet side.
7. Re-run progress candidate logic for that event.
```

On trade update:

```txt
1. Identify market ticker.
2. Update recent trade/volume stats if tracked.
3. Find market.event_ticker.
4. Re-rank event if volume is used as a tie-breaker.
```

On market lifecycle/status update:

```txt
1. Re-fetch or patch market.
2. Re-run SAME_DAY_LIVE_MARKET classification.
3. Add/remove the market from its event group.
4. Re-rank affected event.
5. Remove event if it has no same-day live markets.
```

Do not recompute all events on every update. Only recompute the event that owns the updated market.

---

# Update Engine D: Event Reranker

## Purpose

Recompute rankings for one event when one of its child markets changes.

Input:

```txt
event_ticker
markets for that event
latest orderbook stats for those markets
```

Ranking:

```txt
1. total_resting_order_quantity DESC
2. depth_level_count DESC
3. volume_24h DESC
4. total_volume DESC
```

Reranker responsibilities:

```txt
1. Get all same-day live child markets for event_ticker.
2. Attach latest MarketOrderbookStats.
3. Sort markets.
4. Update:
   - top_3_markets_by_current_orders
   - all_same_day_live_markets_ranked
   - total_event_resting_order_quantity
   - active_orderbook_market_count
5. Store updated event in rankedEvents.
```

Output:

```ts
type RerankedEvent = EventWithTopMarkets;
```

---

# Update Engine E: Progress Gate

## Purpose

Create or update order candidates after the user-defined event-progress threshold passes.

Default threshold:

```txt
65%
```

User input example:

```txt
50%
```

Run this:

```txt
every 5-15 seconds
on event rerank
on orderbook update for selected/most-bet market
```

Progress gate responsibilities:

```txt
1. Take EventWithTopMarkets.
2. Select most-bet market from all_same_day_live_markets_ranked[0].
3. Calculate event progress using selected market:
   open_time -> expected_expiration_time
4. Check progress >= threshold.
5. Select most-bet side:
   YES if yes_order_quantity > no_order_quantity
   NO if no_order_quantity > yes_order_quantity
   tie if equal and non-zero
   none if both zero
6. Create/update candidate only if side is YES or NO.
```

Output:

```ts
type ProgressGateOutput = {
  candidate: ProgressBasedOrderCandidate;
  changed: boolean;
};
```

---

# Update Engine F: Pre-Trade Validator

## Purpose

Protect order placement from stale market/orderbook data.

Run immediately before any order placement.

Validation flow:

```txt
1. Take ProgressBasedOrderCandidate.
2. Re-fetch selected market.
3. Confirm SAME_DAY_LIVE_MARKET still passes.
4. Re-fetch selected market orderbook.
5. Recalculate MarketOrderbookStats.
6. Confirm selected side is still the most-bet side.
7. Confirm spread/price/size constraints.
8. Confirm threshold still passes.
9. Only then allow order placement.
```

If any check fails:

```txt
do not place order
return canTrade = false with reason
```

---

# Non-Empty Ranking Fields

## Current Orders

Use orderbook fields:

```txt
orderbook_fp.yes_dollars[*].count_fp
orderbook_fp.no_dollars[*].count_fp
```

Derived fields:

```txt
yes_order_quantity
no_order_quantity
total_resting_order_quantity
depth_level_count
best_yes_bid
best_no_bid
```

## Executed Bets / Trades

Use market fields:

```txt
volume_24h_fp
volume_fp
```

Optional trades endpoint:

```txt
GET /trades
```

Derived fields:

```txt
recent_trade_count
recent_trade_quantity
recent_trade_notional
```

Recommended current app behavior:

```txt
Primary ranking:
  total_resting_order_quantity DESC

Tie-breakers:
  depth_level_count DESC
  volume_24h_fp DESC
  volume_fp DESC
```

---

# Non-Empty Event Output Shape

```ts
type NonEmptyEventOutput = {
  event_ticker: string;

  same_day_live_market_count: number;
  non_empty_market_count: number;

  total_event_resting_order_quantity: number;
  total_event_24h_volume: number;

  top_3_markets_by_current_orders: Array<{
    market: Market;
    classification: MarketClassification;
    orderbook_stats: MarketOrderbookStats;
  }>;

  non_empty_markets: Array<{
    market: Market;
    classification: MarketClassification;
    orderbook_stats: MarketOrderbookStats;
  }>;
};
```

---

# Recommended Full Runtime Flow

```txt
1. Discovery Poller:
   Fetch open markets and classify same-day live markets.

2. Event Grouper:
   Group by event_ticker.

3. Orderbook Snapshot Loader:
   Fetch orderbooks for same-day live child markets.

4. Non-Empty Marker:
   Mark markets/events with current orders or recent volume.

5. Event Reranker:
   Rank child markets by total resting order quantity.

6. Progress Gate:
   After threshold passes, select most-bet market and YES/NO side.

7. WebSocket Live Updater:
   Patch orderbook/trade/lifecycle updates.

8. Incremental Reranker:
   Re-rank only affected event_ticker.

9. Pre-Trade Validator:
   Re-fetch selected market/orderbook before placing an order.
```

---

# Non-Negotiable Runtime Rules

1. Same-day live discovery remains lifecycle-based only.
2. Non-empty status is an enrichment/ranking signal, not the event-discovery source of truth.
3. A non-empty event requires at least one non-empty child market.
4. Do not require every market inside an event to have orders.
5. Rank markets by current resting order quantity first.
6. Use recent volume/trades as secondary ranking or fallback.
7. Use REST snapshots to initialize state.
8. Use batch orderbook snapshots when many markets are involved.
9. Use WebSockets to keep orderbook/trade/lifecycle state current when available.
10. On update, rerank only the affected event.
11. Re-run progress gate after event rerank.
12. Re-fetch market and orderbook immediately before order placement.
13. Do not place orders from stale in-memory state.


# Output Requirements

```ts
type ScannerOutput = {
  scanned_market_count: number;
  same_day_live_event_count: number;

  same_day_live_events: EventWithTopMarkets[];

  progress_based_order_candidates: {
    threshold_percent: number;
    candidate_count: number;
    candidates: ProgressBasedOrderCandidate[];
    actionable_candidates: ProgressBasedOrderCandidate[];
    manual_review_candidates: ProgressBasedOrderCandidate[];
  };
};
```

---

# Non-Negotiable Rules

1. Do not use allowlists, whitelists, category filters, or keyword filters.
2. Do not use orderbook/action filters to decide if an event is same-day live.
3. Do not use volume, liquidity, or spread filters during same-day event discovery.
4. Do not classify event status directly as the source of truth.
5. Always classify markets first.
6. Always group markets by `event_ticker` after classification.
7. Use America/New_York for “today.”
8. Treat `expiration_time` as deprecated.
9. Require `expected_expiration_time` to be today.
10. Require `latest_expiration_time` to be today.
11. Require `status == "open"`.
12. Require `open_time <= now`.
13. Require `close_time > now`.
14. Include all matching same-day events even if liquidity, orderbook, or volume appears weak.
15. After discovery, fetch orderbooks for child markets to rank the top 3 markets by current orders.
16. Rank top markets by total resting order quantity first, depth level count second, 24h volume third, and total volume fourth.
17. Progress threshold must be user-configurable.
18. Default progress threshold is 65%.
19. Do not create an order candidate before the event passes the threshold.
20. Select the most-bet market from current orderbook rankings.
21. Select YES or NO based on which side has more resting order quantity.
22. If YES and NO are tied, require manual review.
23. Engine 6 creates candidates only; it does not place orders.
24. Run Engine 7 pre-trade validation before any order placement.
25. Re-fetch market and orderbook data before placing any order.
26. Do not place orders from stale market data.
27. Do not include multivariate events until explicitly supported.
