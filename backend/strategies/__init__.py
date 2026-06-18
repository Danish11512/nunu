"""Strategy Experiment Registry.

Maps experiment names to their StrategyExperiment subclasses and provides
a factory function for instantiation.

Usage:
    from backend.strategies import get_experiment
    
    # At runtime (Engine 6):
    strategy = get_experiment("favorite-side-follower", {})
    decision = strategy.select_trade(event_features)
    
    # In backtesting (Phase 5):
    strategy = get_experiment("hybrid-score-follower", {})
    for event in historical_events:
        decision = strategy.select_trade(build_features(event))
"""

from backend.strategies.executed_volume_follower import ExecutedVolumeFollower
from backend.strategies.executed_volume_fade import ExecutedVolumeFade
from backend.strategies.favorite_side_follower import FavoriteSideFollower
from backend.strategies.momentum_follower import MomentumFollower
from backend.strategies.liquidity_filtered_follower import LiquidityFilteredFollower
from backend.strategies.resting_depth_follower import RestingDepthFollower
from backend.strategies.hybrid_score_follower import HybridScoreFollower
from backend.strategies.base import StrategyExperiment


EXPERIMENT_REGISTRY: dict[str, type[StrategyExperiment]] = {
    "executed-volume-follower": ExecutedVolumeFollower,
    "executed-volume-fade": ExecutedVolumeFade,
    "favorite-side-follower": FavoriteSideFollower,
    "momentum-follower": MomentumFollower,
    "liquidity-filtered-follower": LiquidityFilteredFollower,
    "resting-depth-follower": RestingDepthFollower,
    "hybrid-score-follower": HybridScoreFollower,
}


def get_experiment(
    name: str,
    config: dict | None = None,
) -> StrategyExperiment:
    """Factory: instantiate a strategy experiment by name.
    
    Args:
        name: Key in EXPERIMENT_REGISTRY (e.g. "favorite-side-follower")
        config: Optional dict of strategy-specific parameters passed to the
            constructor as keyword arguments.
    
    Returns:
        An instance of the requested StrategyExperiment subclass.
    
    Raises:
        ValueError: If the experiment name is not registered.
    """
    if name not in EXPERIMENT_REGISTRY:
        raise ValueError(
            f"Unknown experiment: {name!r}. "
            f"Available: {list(EXPERIMENT_REGISTRY.keys())}"
        )
    cls = EXPERIMENT_REGISTRY[name]
    config = config or {}
    # Always pass the registry name so StrategyProfile.__init__ gets it.
    # config values override the positional name if provided.
    return cls(name=name, **config)
