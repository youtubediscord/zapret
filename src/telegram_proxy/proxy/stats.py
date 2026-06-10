from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class ProxyRouteEvent:
    """Last route decision for a Telegram connection."""

    dc: int
    is_media: bool
    route: str
    status: str
    reason: str = ""


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
    mtproxy_invalid_init_count: int = 0
    mtproxy_bad_handshake_count: int = 0
    mtproxy_last_problem: str = ""
    route_events: list[ProxyRouteEvent] = field(default_factory=list)
    start_time: float = field(default_factory=time.monotonic)

    @property
    def uptime_seconds(self) -> float:
        return time.monotonic() - self.start_time

    def record_route_event(
        self,
        *,
        dc: int,
        is_media: bool,
        route: str,
        status: str,
        reason: str = "",
    ) -> None:
        self.route_events.append(
            ProxyRouteEvent(
                dc=int(dc),
                is_media=bool(is_media),
                route=str(route),
                status=str(status),
                reason=str(reason or ""),
            )
        )
        del self.route_events[:-12]


__all__ = ["ProxyRouteEvent", "ProxyStats"]
