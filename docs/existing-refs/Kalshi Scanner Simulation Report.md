# Kalshi Scanner Simulation Report

## Simulation Setup

```txt
now = 2026-06-09T15:45:00-04:00 America/New_York
default progress threshold = 65%
```

The simulation uses synthetic Kalshi-like markets and orderbooks to validate the document logic.

## Sample Events

```txt
EVTA:
  EVTA-M1: same-day live, YES qty 80, NO qty 20, total 100
  EVTA-M2: same-day live, YES qty 50, NO qty 100, total 150
  EVTA-M3: same-day live, YES qty 0, NO qty 0, total 0

EVTB:
  EVTB-M1: same-day live, YES qty 10, NO qty 20, total 30
  Progress is only 25%, so no order candidate at 65%.

EVTC:
  EVTC-M1: excluded because latest_expiration_time is tomorrow.

EVTD:
  EVTD-M1: excluded because close_time is already in the past.

EVTE:
  EVTE-M1: same-day live, but orderbook has zero resting quantity.
```

## Engine Results

### Engine 1: Fetch Open Markets

```json
{
  "open_market_count": 7
}
```

### Engine 2: Same-Day Live Market Classification

```json
[
  "EVTA-M1",
  "EVTA-M2",
  "EVTA-M3",
  "EVTB-M1",
  "EVTE-M1"
]
```

Correct result:

```txt
Included:
  EVTA-M1
  EVTA-M2
  EVTA-M3
  EVTB-M1
  EVTE-M1

Excluded:
  EVTC-M1 because latest_expiration_time is not today.
  EVTD-M1 because close_time is already past.
```

### Engine 3: Event Grouping

```json
[
  "EVTA",
  "EVTB",
  "EVTE"
]
```

Correct result:

```txt
EVTA qualifies because at least one child market is same-day live.
EVTB qualifies because at least one child market is same-day live.
EVTE qualifies because at least one child market is same-day live, even with zero orderbook quantity.
```

### Engine 5: Top Markets By Current Orders

```json
{
  "EVTA": [
    {
      "ticker": "EVTA-M2",
      "total_resting_order_quantity": 150.0,
      "yes_order_quantity": 50.0,
      "no_order_quantity": 100.0,
      "volume_24h": 300.0
    },
    {
      "ticker": "EVTA-M1",
      "total_resting_order_quantity": 100.0,
      "yes_order_quantity": 80.0,
      "no_order_quantity": 20.0,
      "volume_24h": 500.0
    },
    {
      "ticker": "EVTA-M3",
      "total_resting_order_quantity": 0,
      "yes_order_quantity": 0,
      "no_order_quantity": 0,
      "volume_24h": 900.0
    }
  ],
  "EVTB": [
    {
      "ticker": "EVTB-M1",
      "total_resting_order_quantity": 30.0,
      "yes_order_quantity": 10.0,
      "no_order_quantity": 20.0,
      "volume_24h": 1000.0
    }
  ],
  "EVTE": [
    {
      "ticker": "EVTE-M1",
      "total_resting_order_quantity": 0,
      "yes_order_quantity": 0,
      "no_order_quantity": 0,
      "volume_24h": 50.0
    }
  ]
}
```

Correct result:

```txt
EVTA top market is EVTA-M2 because total resting order quantity = 150.
EVTA-M2 side is NO because NO qty 100 > YES qty 50.

EVTB top market is EVTB-M1 because it is the only market.
EVTB-M1 side is NO because NO qty 20 > YES qty 10.

EVTE top market is EVTE-M1 but total resting quantity is 0.
It remains discoverable but cannot create an order candidate.
```

### Engine 6: Progress-Based Order Candidates

```json
[
  {
    "event_ticker": "EVTA",
    "threshold_percent": 65,
    "event_progress_percent": 68.75,
    "selected_market": "EVTA-M2",
    "most_bet_side": "no",
    "yes_order_quantity": 50.0,
    "no_order_quantity": 100.0,
    "total_resting_order_quantity": 150.0,
    "should_create_order_candidate": true,
    "reasons": []
  },
  {
    "event_ticker": "EVTB",
    "threshold_percent": 65,
    "event_progress_percent": 25.0,
    "selected_market": "EVTB-M1",
    "most_bet_side": "no",
    "yes_order_quantity": 10.0,
    "no_order_quantity": 20.0,
    "total_resting_order_quantity": 30.0,
    "should_create_order_candidate": false,
    "reasons": [
      "progress 25.00% is below threshold 65%"
    ]
  },
  {
    "event_ticker": "EVTE",
    "threshold_percent": 65,
    "event_progress_percent": 93.75,
    "selected_market": "EVTE-M1",
    "most_bet_side": "none",
    "yes_order_quantity": 0,
    "no_order_quantity": 0,
    "total_resting_order_quantity": 0,
    "should_create_order_candidate": false,
    "reasons": [
      "selected market has zero resting order quantity",
      "no YES/NO side exists"
    ]
  }
]
```

Correct result:

```txt
EVTA creates an order candidate:
  progress = 68.75%
  threshold = 65%
  selected market = EVTA-M2
  selected side = NO

EVTB does not create an order candidate:
  progress = 25%
  threshold = 65%

EVTE does not create an order candidate:
  progress passes threshold
  but selected market has zero resting order quantity
```

## Mismatch Found and Corrected

The previous document had a sequence mismatch:

```txt
Previous order:
  Engine 7: Pre-trade validation
  Engine 8: Progress threshold + most-bet market/side selection
```

That order is incorrect because pre-trade validation needs a candidate first.

Corrected order:

```txt
Engine 6: Progress threshold + most-bet market/side selection
Engine 7: Pre-trade validation
Engine 8: Final output/orchestration
```

## Final Validation

The corrected logic is internally consistent:

```txt
Discovery:
  status/time fields only

Ranking:
  orderbook quantity only after event discovery

Candidate creation:
  only after progress threshold passes

Side selection:
  YES if yes_order_quantity > no_order_quantity
  NO if no_order_quantity > yes_order_quantity
  tie/none blocks automatic candidate

Pre-trade validation:
  must re-fetch market and orderbook before order placement
```
