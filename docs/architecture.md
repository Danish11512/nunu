# System Architecture — Nunu Prediction Market Scanner

> **Visual architecture document.** All diagrams use Mermaid. Every component, every data flow, every async boundary is mapped.

---

## 1. Generic System Architecture (High-Level)

```mermaid
graph TB
    subgraph External["External Systems"]
        KAL["Kalshi API<br/>REST + WebSocket"]
    end

    subgraph Backend["Python Backend (FastAPI)"]
        direction TB
        ADAPTER["Kalshi Adapter<br/>HTTP + WS Client"]
        ENGINES["Engine Pipeline<br/>E1 → E2 → ... → E8"]
        STATE["Scanner State<br/>In-Memory"]
        STRATEGIES["Strategy Profiles<br/>6 Pluggable Strategies"]
        TRADING["Trade Executor<br/>Dry-Run / Read-Only / Live"]
        API["REST API + WebSocket<br/>FastAPI Routes"]
    end

    subgraph Frontend["TypeScript Frontend (React + Vite)"]
        direction TB
        UI["React UI<br/>6 Pages"]
        HOOKS["React Hooks<br/>useWebSocket, useScanner"]
        CLIENT["API Client<br/>ScannerAPI Class"]
    end

    KAL <-->|"REST + WS"| ADAPTER
    ADAPTER --> ENGINES
    ENGINES <--> STATE
    ENGINES --> STRATEGIES
    ENGINES --> TRADING
    TRADING --> API
    STATE --> API
    API <-->|"HTTP/JSON + WS"| CLIENT
    CLIENT --> HOOKS
    HOOKS --> UI
```

### Key

| Element | Technology | Role |
|---------|-----------|------|
| Kalshi API | External REST + WS | Source of market data |
| Kalshi Adapter | Python/httpx/websockets | Protocol translation, rate limiting |
| Engine Pipeline | Python asyncio | 8 sequential processing stages |
| Scanner State | Python dicts | In-memory runtime state |
| Strategy Profiles | Python ABC | Pluggable market/side selection |
| Trade Executor | Python | Mode-aware order placement |
| FastAPI | Python | REST + WebSocket server |
| React UI | TypeScript/Vite | Browser dashboard |
| React Hooks | TypeScript | State management, WS integration |
| API Client | TypeScript | Type-safe HTTP client |

---

## 2. Backend Architecture — Deep Dive

### 2.1 Module Dependency Hierarchy

```mermaid
graph BT
    subgraph Core["Layer 0: Core"]
        MODELS["core/models.py"]
        INTERFACES["core/interfaces.py"]
        STATE["core/scanner_state.py"]
        SETTINGS["config/settings.py"]
    end

    subgraph Adapter["Layer 1: Kalshi Adapter"]
        CLIENT["adapters/kalshi/client.py"]
        TYPES["adapters/kalshi/types.py"]
        WS["adapters/kalshi/websocket.py"]
        ADAPTER["adapters/kalshi/adapter.py"]
    end

    subgraph Strategies["Layer 2a: Strategies"]
        BASE["strategies/base.py"]
        MOST["strategies/most_bet.py"]
        VOL["strategies/highest_volume.py"]
        SPREAD["strategies/widest_spread.py"]
        DEPTH["strategies/deepest_book.py"]
        MOMENTUM["strategies/momentum_shift.py"]
        CUSTOM["strategies/custom_threshold.py"]
        REGISTRY["strategies/__init__.py"]
    end

    subgraph Engines["Layer 2b: Engines"]
        E1["engine1_discovery.py"]
        E2["engine2_classification.py"]
        E3["engine3_grouping.py"]
        E4["engine4_orderbook.py"]
        E5["engine5_ranking.py"]
        E6["engine6_progress_gate.py"]
        E7["engine7_validation.py"]
        E8["engine8_orchestrator.py"]
        LIVE["engines/live/*"]
    end

    subgraph Trading["Layer 3: Trading"]
        EXECUTOR["trading/trade_executor.py"]
    end

    subgraph Logging["Layer 3: Logging"]
        CSV["logging/csv_logger.py"]
    end

    subgraph API_Layer["Layer 4: API"]
        REST["api/rest.py"]
        WS_HANDLER["api/websocket_handler.py"]
        MAIN["main.py"]
    end

    MODELS --> INTERFACES
    MODELS --> STATE
    SETTINGS --> MAIN

    MODELS --> TYPES
    MODELS --> CLIENT
    CLIENT --> ADAPTER
    TYPES --> ADAPTER
    WS --> ADAPTER
    
    MODELS --> BASE
    BASE --> MOST --> REGISTRY
    BASE --> VOL --> REGISTRY
    BASE --> SPREAD --> REGISTRY
    BASE --> DEPTH --> REGISTRY
    BASE --> MOMENTUM --> REGISTRY
    BASE --> CUSTOM --> REGISTRY

    MODELS --> E2
    ADAPTER --> E1
    ADAPTER --> E4
    E2 --> E3
    E3 --> E4
    E4 --> E5
    E2 --> E6
    STRATEGIES --> E6
    E5 --> E6
    E6 --> E7
    ADAPTER --> E7
    STRATEGIES --> E7
    E1 --> E8
    E2 --> E8
    E3 --> E8
    E4 --> E8
    E5 --> E8
    E6 --> E8
    E7 --> E8
    E8 --> LIVE

    E7 --> EXECUTOR
    ADAPTER --> EXECUTOR
    STRATEGIES --> EXECUTOR
    EXECUTOR --> REST
    STATE --> REST
    E8 --> REST
    REST --> MAIN
    WS_HANDLER --> MAIN
```

### 2.2 Engine Pipeline — Detailed Flow

```mermaid
flowchart LR
    subgraph Input["Input"]
        direction LR
        KALSHI_API["Kalshi<br/>REST API"]
    end

    subgraph Pipeline["8-Engine Pipeline (sequential)"]
        direction TB
        
        E1["Engine 1<br/>Market Discovery<br/><i>fetch_all_open_markets()</i>"]
        E2["Engine 2<br/>Live Classification<br/><i>classify_same_day_live()</i>"]
        E3["Engine 3<br/>Event Grouping<br/><i>group_by_event_ticker()</i>"]
        E4["Engine 4<br/>Orderbook Fetch<br/><i>fetch_orderbooks()</i>"]
        E5["Engine 5<br/>Market Ranking<br/><i>rank_by_resting_orders()</i>"]
        E6["Engine 6<br/>Progress Gate<br/><i>select_market + select_side</i>"]
        E7["Engine 7<br/>Pre-Trade Validate<br/><i>re-validate live data</i>"]
        E8["Engine 8<br/>Orchestration<br/><i>coordinate + dispatch</i>"]
    end

    subgraph Output["Output"]
        direction LR
        CANDIDATES["Order Candidates"]
        EVENTS["Ranked Events"]
        TRADES["Trade Records"]
    end

    KALSHI_API --> E1
    E1 --> E2
    E2 --> E3
    E3 --> E4
    E4 --> E5
    E5 --> E6
    E6 --> E7
    E7 --> E8
    E8 --> CANDIDATES
    E8 --> EVENTS
    E8 --> TRADES

    style E1 fill:#4A90D9,color:#fff
    style E2 fill:#4A90D9,color:#fff
    style E3 fill:#4A90D9,color:#fff
    style E4 fill:#4A90D9,color:#fff
    style E5 fill:#4A90D9,color:#fff
    style E6 fill:#F5A623,color:#fff
    style E7 fill:#D0021B,color:#fff
    style E8 fill:#7ED321,color:#fff
```

### 2.3 Engine Data Flow — Types In/Out

```mermaid
flowchart LR
    E1["Engine 1"] -->|"list[Market]"| E2
    E2["Engine 2"] -->|"list[tuple[Market, Classification]]"| E3
    E3["Engine 3"] -->|"list[ClassifiedEvent]"| E4
    E4["Engine 4"] -->|"list[tuple[ClassifiedEvent, dict[str, Orderbook]]]"| E5
    E5["Engine 5"] -->|"list[EventWithTopMarkets]"| E6
    E6["Engine 6"] -->|"list[ProgressBasedOrderCandidate]"| E7
    E7["Engine 7"] -->|"list[ValidatedOrderCandidate]"| E8
    E8["Engine 8"] -->|"ScannerResult"| API["API Layer"]

    style E1 fill:#4A90D9,color:#fff
    style E2 fill:#4A90D9,color:#fff
    style E3 fill:#4A90D9,color:#fff
    style E4 fill:#4A90D9,color:#fff
    style E5 fill:#4A90D9,color:#fff
    style E6 fill:#F5A623,color:#fff
    style E7 fill:#D0021B,color:#fff
    style E8 fill:#7ED321,color:#fff
```

### 2.4 Strategy Resolution

```mermaid
flowchart TB
    CONFIG["settings.yaml<br/>strategy.active_profile: most-bet"] --> REGISTRY
    REGISTRY["strategies/__init__.py<br/>STRATEGY_REGISTRY"] --> FACTORY["get_strategy()"]
    FACTORY --> MOST["MostBetStrategy ✅ tested"]
    FACTORY --> HV["HighestVolumeStrategy ⏸"]
    FACTORY --> WS["WidestSpreadStrategy ⏸"]
    FACTORY --> DB["DeepestBookStrategy ⏸"]
    FACTORY --> MS["MomentumShiftStrategy ⏸"]
    FACTORY --> CT["CustomThresholdStrategy ⏸"]
    
    MOST --> E6["Engine 6<br/>Progress Gate"]
    HV -.-> E6
    WS -.-> E6
    DB -.-> E6
    MS -.-> E6
    CT -.-> E6
    
    E6 -->|"select_market()"| MARKET["Picks market from ranked list"]
    E6 -->|"select_side()"| SIDE["Returns yes/no/tie/none"]
```

---

## 3. Async Runtime Architecture

### 3.1 One-Shot Mode (Synchronous Pipeline)

```mermaid
sequenceDiagram
    participant User
    participant API as FastAPI
    participant E8 as Engine 8
    participant E1 as Engine 1
    participant E2 as Engine 2
    participant E3 as Engine 3
    participant E4 as Engine 4
    participant E5 as Engine 5
    participant E6 as Engine 6
    participant E7 as Engine 7
    participant K as Kalshi API

    User->>API: POST /api/v1/scanner/start
    API->>E8: run_one_shot()
    
    E8->>E1: fetch_all_open_markets()
    E1->>K: GET /markets (paginated)
    K-->>E1: list[Market]
    E1-->>E8: list[Market]
    
    E8->>E2: get_same_day_live_markets()
    E2-->>E8: list[tuple[Market, Classification]]
    
    E8->>E3: group_by_event_ticker()
    E3-->>E8: list[ClassifiedEvent]
    
    E8->>E4: fetch_orderbooks()
    par Concurrent (semaphore=10)
        E4->>K: GET /markets/{t}/orderbook
        E4->>K: GET /markets/{t}/orderbook
        E4->>K: GET /markets/{t}/orderbook
    end
    K-->>E4: list[Orderbook]
    E4-->>E8: list[tuple[ClassifiedEvent, orderbooks]]
    
    E8->>E5: rank_all_events()
    E5-->>E8: list[EventWithTopMarkets]
    
    E8->>E6: process_all_events()
    E6->>E6: strategy.select_market()
    E6->>E6: strategy.select_side()
    E6-->>E8: list[ProgressBasedOrderCandidate]
    
    E8->>E7: validate_candidate() (per actionable)
    E7->>K: GET /markets/{t}
    E7->>K: GET /markets/{t}/orderbook
    K-->>E7: fresh data
    E7-->>E8: ValidatedOrderCandidate
    
    E8-->>API: ScannerResult
    API-->>User: JSON response
```

### 3.2 Live Mode (Async Event Loop)

```mermaid
sequenceDiagram
    participant User
    participant API as FastAPI
    participant Main as App Lifespan
    participant DP as Discovery Poller
    participant WS as WS Updater
    participant PG as Progress Gate
    participant State as Scanner State
    participant K as Kalshi API
    participant FE as Frontend

    Main->>DP: asyncio.create_task(discovery_poller.run())
    Main->>PG: asyncio.create_task(progress_gate.run())
    
    loop Every 30s
        DP->>K: GET /markets
        K-->>DP: new market list
        DP->>DP: diff with previous state
        DP->>State: update events
        DP->>FE: WS: event:discovered / event:removed
    end
    
    loop Every ~100ms (on WS update)
        WS->>K: WebSocket: orderbook update
        K-->>WS: partial orderbook
        WS->>State: patch orderbook stats
        WS->>WS: rerank affected event
        WS->>FE: WS: event:orderbook_update
    end
    
    loop Every 10s
        PG->>State: read ranked events
        PG->>PG: recalculate progress
        PG->>PG: strategy.select_market()
        PG->>PG: strategy.select_side()
        PG->>State: update candidates
        alt candidate is actionable
            PG->>FE: WS: candidate:created
        end
        PG->>FE: WS: event:progress_updated
    end
    
    User->>FE: approve candidate
    FE->>API: POST /candidates/{id}/approve
    API->>API: validate + execute
    API->>FE: WS: candidate:executed / trade:dry_run
```

### 3.3 Async Task Graph

```mermaid
graph TB
    subgraph MainLoop["Main Async Loop"]
        direction TB
        
        subgraph Task1["Task: Discovery Poller"]
            DP_LOOP["while not stop_event:<br/>  fetch_all_open_markets()<br/>  classify_same_day_live()<br/>  group_by_event_ticker()<br/>  diff_events()<br/>  update_state()<br/>  broadcast_updates()<br/>  await asyncio.sleep(30)"]
        end
        
        subgraph Task2["Task: WS Live Updater"]
            WS_LOOP["while not stop_event:<br/>  ws.listen()<br/>  parse_message()<br/>  patch_orderbook_state()<br/>  rerank_affected_event()<br/>  broadcast_orderbook_update()"]
        end
        
        subgraph Task3["Task: Progress Gate"]
            PG_LOOP["while not stop_event:<br/>  for each ranked_event:<br/>    calculate_progress()<br/>    strategy.select_market()<br/>    strategy.select_side()<br/>    update_candidate()<br/>    if actionable: broadcast()<br/>  await asyncio.sleep(10)"]
        end
        
        subgraph Task4["Task: State Broadcast"]
            BC_LOOP["while not stop_event:<br/>  broadcast_scanner_status()<br/>  await asyncio.sleep(5)"]
        end
    end

    subgraph State["Shared State<br/>(thread-safe via asyncio)"]
        MARKETS["markets_by_ticker: dict[str, Market]"]
        EVENTS["events: dict[str, ClassifiedEvent]"]
        OB_STATS["orderbook_stats: dict[str, MarketOrderbookStats]"]
        RANKED["ranked_events: dict[str, EventWithTopMarkets]"]
        CANDIDATES["candidates: dict[str, ProgressBasedOrderCandidate]"]
    end

    Task1 -->|"writes"| EVENTS
    Task2 -->|"writes"| OB_STATS
    Task2 -->|"writes"| RANKED
    Task3 -->|"reads"| RANKED
    Task3 -->|"writes"| CANDIDATES

    subgraph Concurrency["Concurrency Controls"]
        SEM["asyncio.Semaphore(10)<br/>for Kalshi API calls"]
        STOP["asyncio.Event()<br/>for graceful shutdown"]
    end

    Task1 --> SEM
    Task2 --> SEM
    Task3 --> SEM
    Task1 --> STOP
    Task2 --> STOP
    Task3 --> STOP
```

### 3.4 State Synchronization

```mermaid
flowchart LR
    subgraph Writers["Who Writes"]
        DP["Discovery Poller<br/>writes: events, markets"]
        WS_U["WS Updater<br/>writes: orderbooks, reranked events"]
        PG["Progress Gate<br/>writes: candidates"]
    end

    subgraph StateLayer["ScannerState (dicts)"]
        MARKETS["markets_by_ticker"]
        EVENTS["events"]
        OB["orderbook_stats"]
        RANKED["ranked_events"]
        CAND["candidates"]
    end

    subgraph Readers["Who Reads"]
        REST_API["REST API routes"]
        WS_BROAD["WS broadcasts"]
        E8["Engine 8"]
    end

    DP --> MARKETS
    DP --> EVENTS
    WS_U --> OB
    WS_U --> RANKED
    PG --> CAND

    REST_API --> MARKETS
    REST_API --> EVENTS
    REST_API --> RANKED
    REST_API --> CAND
    WS_BROAD --> RANKED
    WS_BROAD --> CAND
    E8 --> MARKETS
    E8 --> EVENTS

    style Writers fill:#4A90D9,color:#fff
    style Readers fill:#7ED321,color:#fff
    style StateLayer fill:#F5A623,color:#fff
```

---

## 4. Frontend Architecture — Deep Dive

### 4.1 Component Tree

```mermaid
graph TB
    APP["App.tsx<br/>BrowserRouter + Layout"]
    
    subgraph Pages["Pages (6 routes)"]
        DASH["Dashboard.tsx<br/>Route: /"]
        EVENTS["Events.tsx<br/>Route: /events"]
        EVENT_DETAIL["EventDetail.tsx<br/>Route: /events/:id"]
        CAND["Candidates.tsx<br/>Route: /candidates"]
        TRADES["Trades.tsx<br/>Route: /trades"]
        SETTINGS["Settings.tsx<br/>Route: /settings"]
    end
    
    subgraph Hooks["Custom Hooks"]
        useWS["useWebSocket(channel, handler)"]
        useSC["useScanner()"]
        useCAND["useCandidates()"]
    end
    
    subgraph Lib["Library"]
        API["api.ts<br/>ScannerAPI class"]
        TYPES["types.ts<br/>All interfaces"]
        CONST["constants.ts"]
    end
    
    subgraph Components["Reusable Components"]
        direction TB
        
        subgraph Dashboard_Group["Dashboard"]
            EC["EventCard.tsx"]
            EL["EventList.tsx"]
            MR["MarketRow.tsx"]
            SS["ScannerStatus.tsx"]
        end
        
        subgraph Orderbook_Group["Orderbook"]
            OD["OrderbookDepth.tsx"]
            BA["BidAskChart.tsx"]
            SI["SpreadIndicator.tsx"]
        end
        
        subgraph Candidate_Group["Candidates"]
            CC["CandidateCard.tsx"]
            CL["CandidateList.tsx"]
            CA["CandidateActions.tsx"]
        end
        
        subgraph Trading_Group["Trading"]
            MS["ModeSelector.tsx"]
            CD["ConfirmDialog.tsx"]
            TH["TradeHistory.tsx"]
        end
        
        subgraph Controls_Group["Controls"]
            TS["ThresholdSlider.tsx"]
            SS2["StrategySelector.tsx"]
            RC["RefreshControl.tsx"]
        end
        
        subgraph Common_Group["Common"]
            B["Badge.tsx"]
            PB["ProgressBar.tsx"]
            SD["SideIndicator.tsx"]
        end
    end

    APP --> DASH
    APP --> EVENTS
    APP --> EVENT_DETAIL
    APP --> CAND
    APP --> TRADES
    APP --> SETTINGS
    
    DASH --> EC
    DASH --> SS
    EVENTS --> EL
    EVENT_DETAIL --> MR
    EVENT_DETAIL --> OD
    EVENT_DETAIL --> BA
    EVENT_DETAIL --> PB
    CAND --> CC
    CAND --> CL
    CAND --> CA
    TRADES --> TH
    SETTINGS --> MS
    SETTINGS --> TS
    SETTINGS --> SS2
    
    EC --> B
    EC --> PB
    EC --> SD
    MR --> SD
    MR --> SI
    CC --> B
    CC --> PB
    CC --> CA
    CA --> CD
    MS --> CD
    MS --> B

    DASH --> useWS
    DASH --> useSC
    CAND --> useCAND
    useWS --> API
    useSC --> API
    useCAND --> API
    API --> TYPES
```

### 4.2 Frontend Data Flow

```mermaid
sequenceDiagram
    participant User
    participant Page as React Page
    participant Hook as React Hook
    participant API as ScannerAPI
    participant BE as Backend
    participant WS as WebSocket

    Note over User,WS: Page Load
    
    Page->>Hook: useScanner()
    Hook->>API: getStatus()
    API->>BE: GET /api/v1/scanner/status
    BE-->>API: ScannerStatus
    API-->>Hook: status
    Hook-->>Page: render
    
    Hook->>API: getEvents()
    API->>BE: GET /api/v1/events
    BE-->>API: EventSummary[]
    API-->>Hook: events
    Hook-->>Page: render event list
    
    Note over User,WS: Real-time Updates
    
    Hook->>WS: connect /api/v1/ws/events
    WS-->>Hook: event:updated (payload)
    Hook->>Hook: merge into state
    Hook-->>Page: re-render with new data
    
    WS-->>Hook: event:progress_updated
    Hook->>Hook: update progress bar
    Hook-->>Page: progress bar animates
    
    Note over User,WS: User Action
    
    User->>Page: click "Approve" on candidate
    Page->>Hook: useCandidates().approve()
    Hook->>API: approveCandidate(eventTicker)
    API->>BE: POST /candidates/{id}/approve
    BE-->>API: ApproveCandidateResult
    API-->>Hook: result
    Hook-->>Page: show success/error toast
```

### 4.3 Frontend State Management

```mermaid
flowchart LR
    subgraph Server["Server State (via API)"]
        STATUS["ScannerStatus<br/>GET /status"]
        EVENTS["EventSummary[]<br/>GET /events"]
        CANDIDATES["CandidateResponse[]<br/>GET /candidates"]
        CONFIG["ScannerConfig<br/>GET /config"]
    end

    subgraph RealTime["Real-Time State (via WS)"]
        WS_EVENTS["Event Updates<br/>WS /ws/events"]
        WS_CAND["Candidate Updates<br/>WS /ws/candidates"]
        WS_TRADES["Trade Updates<br/>WS /ws/trades"]
        WS_SCANNER["Scanner Status<br/>WS /ws/scanner"]
    end

    subgraph Local["Local React State"]
        HOOKS["Custom Hooks<br/>useState + useCallback"]
        CONTEXT["React Context<br/>(optional, for cross-page state)"]
    end

    subgraph UI["UI Rendering"]
        PAGES["Pages"]
        COMPONENTS["Components"]
    end

    Server -->|"SWR / React Query"| HOOKS
    RealTime -->|"useWebSocket<br/>mergeDiff"| HOOKS
    HOOKS --> PAGES
    HOOKS --> COMPONENTS
    
    style Server fill:#4A90D9,color:#fff
    style RealTime fill:#7ED321,color:#fff
    style Local fill:#F5A623,color:#fff
```

---

## 5. Three Operating Modes

### 5.1 Mode Decision Tree

```mermaid
flowchart TB
    START["Scanner Starts"] --> MODE{Operating Mode?}
    
    MODE -->|"default"| DRY["Dry-Run"]
    MODE -->|"config or --mode readonly"| RO["Read-Only"]
    MODE -->|"user switches via UI"| LIVE["Live"]
    
    subgraph DryRun["Dry-Run Mode"]
        DRY_E1["E1-E6: Full pipeline"] --> DRY_E7["E7: Full validation"] --> DRY_OUT["Candidates displayed<br/>with simulated fills"]
        DRY_OUT --> DRY_BADGE["🧪 DRY RUN badge on all UI"]
    end
    
    subgraph ReadOnly["Read-Only Mode"]
        RO_E1["E1-E6: Full pipeline"] --> RO_E7["E7: Skipped"] --> RO_OUT["Candidates displayed<br/>for manual review only"]
        RO_OUT --> RO_BADGE["👁️ READ ONLY badge on all UI"]
    end
    
    subgraph LiveMode["Live Trading Mode"]
        LIVE_E1["E1-E6: Full pipeline"] --> LIVE_E7["E7: Full validation + API call"] --> LIVE_OUT["Real orders placed"]
        LIVE_OUT --> LIVE_BADGE["🔴 LIVE badge on all UI"]
    end

    DRY -.->|"user clicks switch + confirm"| LIVE
    LIVE -.->|"user clicks switch"| DRY
```

### 5.2 Mode State Machine

```mermaid
stateDiagram-v2
    [*] --> DryRun: startup (default)
    
    DryRun --> Live: toggle + confirm
    DryRun --> ReadOnly: boot-time flag
    
    Live --> DryRun: toggle
    
    ReadOnly --> [*]: restart required
    
    Live --> DryRun: auth failure
    Live --> DryRun: API error
    Live --> DryRun: manual stop
```

---

## 6. Deployment Architecture

```mermaid
graph TB
    subgraph DevMachine["Developer Machine"]
        CODE["Source Code<br/>nunu/"]
        DOCKER["Docker Compose"]
    end
    
    subgraph DockerContainers["Docker Containers"]
        direction TB
        
        subgraph BackendContainer["Backend (port 8000)"]
            UVICORN["uvicorn<br/>backend.main:app"]
            ENGINE_PROC["Engine Pipeline"]
            KALSHI_CONN["Kalshi Connection<br/>REST + WS"]
        end
        
        subgraph FrontendContainer["Frontend (port 5173)"]
            VITE["Vite Dev Server<br/>/api → proxy :8000"]
            REACT_APP["React App<br/>Hot Module Reload"]
        end
        
        subgraph Storage["Persistent Storage"]
            LOGS["logs/<br/>scanner.csv + trades.json"]
            CONFIG_FILES["config/<br/>settings.yaml"]
            ENV["backend/.env<br/>API keys"]
        end
    end
    
    subgraph ExternalServices["External"]
        KALSHI["Kalshi API<br/>external-api.kalshi.com"]
    end

    CODE --> DOCKER
    DOCKER --> BackendContainer
    DOCKER --> FrontendContainer
    
    BackendContainer --> KALSHI
    BackendContainer --> LOGS
    BackendContainer --> CONFIG_FILES
    BackendContainer --> ENV
    FrontendContainer -->|"proxy /api/*"| BackendContainer
    
    User["User Browser"] -->|"http://localhost:5173"| FrontendContainer
```

---

## 7. Data Schema Relationships

```mermaid
erDiagram
    Market ||--o{ Orderbook : has
    Market }o--|| Event : belongs_to
    Event ||--o{ OrderCandidate : produces
    OrderCandidate ||--|| ValidatedOrderCandidate : validated_as
    ValidatedOrderCandidate ||--o| TradeRecord : becomes
    
    Market {
        string ticker PK
        string event_ticker FK
        string status
        string open_time
        string close_time
        string expected_expiration_time
    }
    
    Event {
        string event_ticker PK
        int market_count
        int live_market_count
    }
    
    Orderbook {
        string market_id FK
        list yes_bids
        list no_bids
    }
    
    OrderCandidate {
        string event_ticker FK
        string market_id FK
        string side
        float progress_percent
        float threshold_percent
        bool should_create
    }
    
    ValidatedOrderCandidate {
        string event_ticker FK
        bool can_trade
        string confirmed_side
        float validation_latency_ms
    }
    
    TradeRecord {
        string trade_id PK
        string market_ticker FK
        string mode
        string status
        float price
        float size
    }
```

---

## 8. Security Boundaries

```mermaid
flowchart LR
    subgraph Untrusted["Untrusted Zone"]
        BROWSER["Browser<br/>(React App)"]
    end
    
    subgraph API_Boundary["API Boundary (FastAPI)"]
        CORS["CORS Middleware"]
        AUTH["Auth Check<br/>(live mode only)"]
        VALIDATION["Request Validation<br/>(Pydantic)"]
        RATE_LIMIT["Rate Limiter"]
    end
    
    subgraph Trusted["Trusted Zone"]
        ENGINES["Engine Pipeline"]
        ADAPTER["Kalshi Adapter"]
    end
    
    subgraph External["External"]
        KALSHI["Kalshi API"]
    end

    BROWSER -->|"HTTP/WS"| CORS
    CORS --> AUTH
    AUTH --> VALIDATION
    VALIDATION --> RATE_LIMIT
    RATE_LIMIT --> ENGINES
    ENGINES --> ADAPTER
    ADAPTER -->|"HTTPS + API Key"| KALSHI

    style Untrusted fill:#ffcccc
    style API_Boundary fill:#ffffcc
    style Trusted fill:#ccffcc
    style External fill:#e0e0e0
```

---

## 9. Key Async Patterns

### 9.1 Concurrent Orderbook Fetching

```python
# Pattern: bounded concurrency with asyncio.Semaphore
semaphore = asyncio.Semaphore(10)

async def fetch_one(ticker: str) -> tuple[str, Orderbook]:
    async with semaphore:
        return ticker, await adapter.get_orderbook(ticker)

# Fire all requests concurrently, wait for all to complete
tasks = [fetch_one(t) for t in tickers]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

### 9.2 WebSocket Auto-Reconnect

```python
# Pattern: infinite loop with reconnection
async def listen_with_reconnect(self, tickers):
    while self._running:
        try:
            await self.connect()
            await self.subscribe(tickers)
            async for message in self.listen():
                await self.handle_message(message)
        except ConnectionClosed:
            await asyncio.sleep(self.reconnect_delay)
```

### 9.3 Graceful Shutdown

```python
# Pattern: asyncio.Event for cross-task cancellation
stop_event = asyncio.Event()

async def discovery_poller():
    while not stop_event.is_set():
        await do_work()
        await asyncio.sleep(30)

async def progress_gate():
    while not stop_event.is_set():
        await do_work()
        await asyncio.sleep(10)

# On shutdown:
stop_event.set()
await asyncio.gather(*tasks, return_exceptions=True)
```

### 9.4 State Isolation (No Locks Needed)

Because all tasks run in the same event loop (asyncio single-threaded), shared state access is implicitly safe:

```python
# All tasks in same event loop = no race conditions on plain dicts
# Task 1 writes:
state.events[event_ticker] = new_event

# Task 2 reads (same thread, different await point):
current = state.events.get(event_ticker)

# No locks needed — asyncio yields only at await points
```

---

## 10. Configuration Flow

```mermaid
flowchart LR
    subgraph Sources["Config Sources"]
        YAML["config/settings.yaml"]
        ENV[".env file"]
        ENV_VARS["Environment Variables"]
        UI["Frontend Settings UI<br/>PUT /api/v1/config"]
    end

    subgraph Merge["Merge Order (later overrides earlier)"]
        PYTHON["Pydantic defaults"]
        YAML_VALS["YAML values"]
        ENV_VALS["Env vars"]
    end

    subgraph Consumers["Consumers"]
        ADAPTER["KalshiAdapter"]
        ENGINES["Engines"]
        STRATEGIES["Strategy config"]
        TRADING["Risk config"]
        FRONTEND["Frontend (via GET /config)"]
    end

    YAML --> Merge
    ENV --> Merge
    ENV_VARS --> Merge
    Merge --> ADAPTER
    Merge --> ENGINES
    Merge --> STRATEGIES
    Merge --> TRADING
    UI -->|"runtime override"| STRATEGIES
    UI -->|"runtime override"| ENGINES
    Merge --> FRONTEND
```

---

## Diagram Index

| Diagram | File | What It Shows |
|---------|------|---------------|
| 1. Generic System | Above | High-level backend ↔ frontend ↔ Kalshi |
| 2.1 Module Deps | Above | Every Python file, import dependencies |
| 2.2 Engine Pipeline | Above | 8 engines with colored stages |
| 2.3 Engine Data Flow | Above | Types flowing between engines |
| 2.4 Strategy Resolution | Above | Config → registry → strategy instance |
| 3.1 One-Shot Sequence | Above | Full async sequence diagram |
| 3.2 Live Mode Sequence | Above | Async event loop with 3 parallel tasks |
| 3.3 Async Task Graph | Above | asyncio task structure with shared state |
| 3.4 State Sync | Above | Writers, readers, state layer |
| 4.1 Component Tree | Above | All React components with nesting |
| 4.2 Frontend Data Flow | Above | Sequence: page → hook → API → render |
| 4.3 Frontend State | Above | Server + real-time + local state sources |
| 5.1 Mode Decision Tree | Above | 3 modes, what runs in each |
| 5.2 Mode State Machine | Above | States and transitions |
| 6. Deployment | Above | Docker, ports, volumes, external |
| 7. ER Diagram | Above | Data model relationships |
| 8. Security | Above | Trust boundaries |
| 9. Async Patterns | Above | Code snippets for key patterns |
| 10. Config Flow | Above | Config sources and merge order |
