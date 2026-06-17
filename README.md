# Nunu — Kalshi Prediction Market Scanner

Python backend + TypeScript/React frontend. Scans Kalshi prediction markets for same-day live events, ranks markets by orderbook activity, and produces order candidates with a configurable progress threshold.

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, httpx, WebSockets |
| Frontend | TypeScript, React, Vite, Tailwind CSS |
| Infrastructure | Docker, docker-compose |

## Operating Modes

| Mode | Description | Orders |
|------|-------------|--------|
| **Dry-Run** (default) | Full pipeline, simulated fills | Simulated only |
| **Read-Only** | Scan + display + save candidates | Never called |
| **Live Trading** | Full pipeline + pre-trade validation + real orders | Real Kalshi API |

## Quick Start

```bash
# Backend
cd backend && pip install -r requirements.txt
python main.py

# Frontend
cd frontend && npm install
npm run dev
```

## Architecture

```
8-engine pipeline (Python) → FastAPI + WebSocket → React Dashboard

Engine 1:  Market Discovery     → Fetch all open markets
Engine 2:  Live Classification  → Classify same-day live markets
Engine 3:  Event Grouping       → Group by event_ticker
Engine 4:  Orderbook Fetch      → Fetch YES/NO bids
Engine 5:  Market Ranking       → Rank by resting order quantity
Engine 6:  Progress Gate        → Check threshold → select YES/NO
Engine 7:  Pre-Trade Validate   → Re-fetch, re-validate
Engine 8:  Orchestration        → Run pipeline, manage state
```

## Docs

- [Full Platform Plan](docs/plans/generic-prediction-market-scanner-platform.md)
- [Adapter Contract](docs/adapters/adapter-contract.md)
- [Engine Specs](docs/engines/)
- [Kalshi Reference Docs](docs/existing-refs/)

## Status

**Planning phase.** See the plan document for open questions and next steps.
