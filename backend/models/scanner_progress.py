"""Dataclasses for pipeline diagnostics — broadcast over WS to frontend."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PipelineStage:
    stage: str          # "E1" through "E7"
    label: str          # "Discovery", "Classification", "Grouping", "Orderbook", "Ranking", "Progress Gate", "Validation"
    status: str         # "pending" | "running" | "done" | "error" | "skipped"
    input_count: int = 0
    output_count: int = 0
    duration_ms: int = 0
    error: str | None = None


@dataclass
class PipelineCycle:
    cycle_id: int
    status: str         # "running" | "completed" | "error"
    stages: dict[str, PipelineStage] = field(default_factory=dict)
    started_at: str | None = None
    completed_at: str | None = None
    total_markets_discovered: int = 0
    total_events_active: int = 0
    total_candidates_found: int = 0


@dataclass
class ApiTrace:
    method: str
    path: str
    status: int
    duration_ms: int
    rate_remaining: int | None = None
    timestamp: str = ""
    error: str | None = None


# In-memory store for the REST fallback endpoint
_cycle_store: PipelineCycle | None = None


def get_current_cycle() -> PipelineCycle | None:
    return _cycle_store


def set_current_cycle(cycle: PipelineCycle | None) -> None:
    global _cycle_store
    _cycle_store = cycle
