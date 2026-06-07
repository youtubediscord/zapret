from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class ProxyStats:
    """Live proxy statistics."""

    total_connections: int = 0
    active_connections: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    wss_connections: int = 0
    tcp_fallback_connections: int = 0
    cloudflare_connections: int = 0
    cloudflare_worker_connections: int = 0
    cloudflare_failures: int = 0
    failed_connections: int = 0
    pool_hits: int = 0
    pool_misses: int = 0
    cloudflare_worker_pool_hits: int = 0
    cloudflare_worker_pool_misses: int = 0
    passthrough_connections: int = 0
    upstream_connections: int = 0
    recv_zero_count: int = 0
    recv_zero_per_dc: dict = field(default_factory=dict)
    http_rejected: int = 0
    start_time: float = field(default_factory=time.monotonic)

    @property
    def uptime_seconds(self) -> float:
        return time.monotonic() - self.start_time


__all__ = ["ProxyStats"]
