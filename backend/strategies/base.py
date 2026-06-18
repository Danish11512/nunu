from backend.core.interfaces.strategy import (
    StrategyProfile,
    MarketFeatures,
    EventFeatures,
    TradeDecision,
)


class StrategyExperiment(StrategyProfile):
    """
    Base class for all 7 strategy experiments in Phase 4.
    
    Extends StrategyProfile from core/interfaces, which defines:
    - name: str
    - description: str
    - abstract select_trade(event_features: EventFeatures) -> TradeDecision
    
    Each experiment overrides select_trade() with its specific logic.
    
    Alignment note:
    MarketFeatures now includes optional extended fields
    (total_executed_volume, yes_executed_volume, no_executed_volume,
     trade_count, yes_price_momentum, yes_total_depth, no_total_depth)
    that default to 0. At runtime (Engine 6/7) these get defaults and
    strategies fall back to proxy signals from core fields. Phase 5
    FeatureBuilder enriches them from historical trade data.
    """
    pass
