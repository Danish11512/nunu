from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

# Load .env from project root (where this file is at backend/config/)
_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)


# YAML → model field name translation for keys that differ.
_YAML_KEY_MAP: dict[str, dict[str, str]] = {
    "kalshi": {
        "base_url": "api_base_url",
    },
    "scanner": {
        "discovery_poll_interval": "poll_interval_seconds",
        "progress_gate_interval": "progress_check_interval_seconds",
    },
}


def _translate_yaml_section(section_name: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Rename YAML keys to match pydantic field names."""
    mapping = _YAML_KEY_MAP.get(section_name, {})
    return {mapping.get(k, k): v for k, v in raw.items()}


class KalshiConfig(BaseSettings):
    """Kalshi API connection configuration."""

    model_config = {"populate_by_name": True}

    # API connection
    api_base_url: str = Field(
        default="https://api.elections.kalshi.com/trade-api/v2",
        alias="KALSHI_API_BASE_URL",
        description="Kalshi API base URL",
    )
    ws_base_url: str = Field(
        default="wss://api.elections.kalshi.com/trade-api/ws/v2",
        alias="KALSHI_WS_BASE_URL",
        description="Kalshi WebSocket base URL",
    )

    # Authentication
    key_id: str = Field(default="", alias="KALSHI_API_KEY_ID")
    private_key_path: str = Field(default="", description="Path to RSA private key PEM file")
    private_key: str = Field(default="", alias="KALSHI_PRIVATE_KEY")
    member_id: str = Field(default="", alias="KALSHI_MEMBER_ID")
    funder_address: str = Field(default="", alias="KALSHI_FUNDER_ADDRESS")

    # Rate limiting
    rate_limit: int = Field(default=10, description="Max requests per second")
    max_retries: int = Field(default=3, description="Max retry attempts")
    timeout_seconds: int = Field(default=30, description="Request timeout")

    # Connection pool
    max_connections: int = Field(default=20, description="Max HTTP connections")


class ScannerConfig(BaseSettings):
    """Scanner behavior configuration."""

    model_config = {"populate_by_name": True}

    # Core settings
    default_mode: str = Field(
        default="live", alias="SCANNER_DEFAULT_MODE", description="Scanner mode: oneshot or live"
    )
    default_threshold: int = Field(
        default=65, alias="SCANNER_DEFAULT_THRESHOLD", description="Progress threshold (0-100)"
    )
    default_strategy: str = Field(
        default="favorite-side-follower",
        alias="SCANNER_DEFAULT_STRATEGY",
        description="Default strategy name",
    )
    min_markets_per_event: int = Field(
        default=3, description="Minimum markets for event to qualify"
    )
    min_volume_before_entry: int = Field(
        default=100, description="Minimum volume before entry"
    )
    min_side_signal_strength: float = Field(
        default=0.50, description="Minimum side confidence"
    )
    max_candidates_per_cycle: int = Field(
        default=10, description="Max candidates per scan cycle"
    )

    # Polling (live mode)
    poll_interval_seconds: int = Field(
        default=30, description="Discovery poll interval"
    )
    progress_check_interval_seconds: int = Field(
        default=10, description="Progress check interval"
    )

    # Event filtering
    max_event_expiry_hours: int = Field(
        default=48, description="Max hours until event expiry to include"
    )
    exclude_expired: bool = Field(
        default=True, description="Exclude already-expired events"
    )

    # Output
    out_dir: str = Field(default="./kalshi_out", description="Output directory")


class LoggingConfig(BaseSettings):
    """Logging configuration."""

    model_config = {"populate_by_name": True}

    level: str = Field(default="INFO", alias="LOG_LEVEL", description="Log level")
    format: str = Field(
        default="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        description="Log format string",
    )
    file: str = Field(default="", description="Log file path (empty = stderr)")
    csv_path: str = Field(
        default="", alias="CSV_LOG_PATH", description="Path for CSV scanner log"
    )
    trade_history_path: str = Field(
        default="", alias="TRADE_HISTORY_PATH", description="Path for trade history JSON"
    )


class StrategyConfig(BaseSettings):
    """Strategy configuration (forward-looking for Phase 4+)."""

    model_config = {"populate_by_name": True}

    name: str = Field(default="", description="Strategy name")
    params: dict[str, Any] = Field(default_factory=dict, description="Strategy-specific parameters")


class ValidationConfigSection(BaseSettings):
    """Validation rules (forward-looking for Phase 6+)."""

    model_config = {"populate_by_name": True}

    max_spread_cents: int = Field(default=5)
    min_volume: int = Field(default=100)
    max_position_size: int = Field(default=1000)
    min_confidence: float = Field(default=0.6)
    allow_overtime: bool = Field(default=False)


class RiskConfigSection(BaseSettings):
    """Risk management limits (forward-looking for Phase 6+)."""

    model_config = {"populate_by_name": True}

    max_position_size_per_market: int = Field(default=500)
    max_position_size_per_event: int = Field(default=1000)
    max_total_positions: int = Field(default=20)
    max_daily_trades: int = Field(default=50)
    stop_loss_cents: int = Field(default=20)
    take_profit_cents: int = Field(default=40)


class Settings(BaseSettings):
    """Root settings aggregating all sub-configs."""

    kalshi: KalshiConfig = Field(default_factory=KalshiConfig)
    scanner: ScannerConfig = Field(default_factory=ScannerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    validation: ValidationConfigSection = Field(default_factory=ValidationConfigSection)
    risk: RiskConfigSection = Field(default_factory=RiskConfigSection)

    model_config = {"env_nested_delimiter": "__", "populate_by_name": True}


def load_settings(config_path: str | None = None) -> Settings:
    """Load settings from YAML file, overlaying env vars.

    Args:
        config_path: Path to settings.yaml. If None, resolves relative
                     to the project root by searching upward for the
                     'config' directory.
    """
    if config_path is None:
        # Resolve relative to project root
        current = Path.cwd()
        for parent in [current] + list(current.parents):
            candidate = parent / "config" / "settings.yaml"
            if candidate.exists():
                config_path = str(candidate)
                break
        if config_path is None:
            config_path = "config/settings.yaml"

    settings = Settings()

    if os.path.exists(config_path):
        with open(config_path) as f:
            yaml_config: dict[str, Any] = yaml.safe_load(f) or {}

        def _filter_known(section: str, model: type[BaseSettings],
                          data: dict[str, Any]) -> dict[str, Any]:
            """Translate YAML keys and keep only fields the model recognises.

            Returns kwargs keyed by the field's *alias* (not python name) so
            that ``pydantic-settings`` doesn't see a conflict between an env
            var (resolved by the alias) and a positional kwarg (resolved by
            the python name).
            """
            known = set(model.model_fields)
            translated = _translate_yaml_section(section, data)
            filtered = {k: v for k, v in translated.items() if k in known}
            # Map python names → alias names when an alias is defined
            out: dict[str, Any] = {}
            for k, v in filtered.items():
                field = model.model_fields[k]
                out[field.alias if field.alias else k] = v
            return out

        # Map YAML sections to settings (with key translation + unknown filtering)
        if "kalshi" in yaml_config:
            settings.kalshi = KalshiConfig(
                **_filter_known("kalshi", KalshiConfig, yaml_config["kalshi"])
            )
        if "scanner" in yaml_config:
            settings.scanner = ScannerConfig(
                **_filter_known("scanner", ScannerConfig, yaml_config["scanner"])
            )
        if "logging" in yaml_config:
            settings.logging = LoggingConfig(
                **_filter_known("logging", LoggingConfig, yaml_config["logging"])
            )
        if "strategy" in yaml_config:
            settings.strategy = StrategyConfig(
                **_filter_known("strategy", StrategyConfig, yaml_config["strategy"])
            )
        if "validation" in yaml_config:
            settings.validation = ValidationConfigSection(
                **_filter_known("validation", ValidationConfigSection, yaml_config["validation"])
            )
        if "risk" in yaml_config:
            settings.risk = RiskConfigSection(
                **_filter_known("risk", RiskConfigSection, yaml_config["risk"])
            )

    return settings
