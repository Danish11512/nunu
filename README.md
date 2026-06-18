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

**✅ Phase 1 (Backend Core + Utils) — Complete.** Core domain models, interfaces, configuration, and utility modules are implemented and importable.

**✅ Phase 2 (Kalshi Adapter) — Complete.** HTTP client, WebSocket client, types, and adapter facade implementing `AbstractMarketAdapter`.

**⬜ Phases 3–13 — Not yet started.**
- Phase 3: 8-engine pipeline (discovery → classification → grouping → orderbook → ranking → progress gate → validation → orchestration)
- Phase 4: 7 strategy experiments + registry
- Phase 5: Backtesting infrastructure
- Phase 6: Trading executor + logging + portfolio
- Phase 7: FastAPI REST + WebSocket layer
- Phase 8: Frontend scaffolding (Vite + React + TypeScript)
- Phase 9: Frontend hooks (WebSocket, scanner state)
- Phase 10: Frontend pages (6 routes)
- Phase 11: Frontend components (15+)
- Phase 12: Test infrastructure
- Phase 13: Docker + integration

**No `frontend/` directory exists yet.** See the [build plan](docs/build-plan.md) and [API contract](docs/api-contract.md) for the target architecture.
