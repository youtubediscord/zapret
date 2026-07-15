"""Strategy scan data models — pure Python, no Qt dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StrategyProbeResult:
    """Result of testing a single strategy against a target."""

    strategy_name: str
    strategy_id: str
    strategy_args: str
    target: str
    success: bool
    time_ms: float
    error: str = ""
    http_code: int = 0
    scan_protocol: str = "tcp_https"
    probe_type: str = "https"
    target_port: int = 443
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyScanReport:
    """Aggregated result of scanning multiple strategies."""

    target: str
    total_tested: int
    total_available: int = 0
    working_strategies: list[StrategyProbeResult] = field(default_factory=list)
    failed_strategies: list[StrategyProbeResult] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    cancelled: bool = False
    baseline_accessible: bool = False
    scan_protocol: str = "tcp_https"
    # Причина аварийной остановки скана (например, WinDivert недоступен);
    # пустая строка — скан завершился или отменён пользователем.
    fatal_error: str = ""
