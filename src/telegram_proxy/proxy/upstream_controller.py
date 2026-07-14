from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Literal

from telegram_proxy.proxy.routing import UpstreamProxyConfig, UpstreamProxyEndpoint


UpstreamState = Literal["primary", "fallback", "checking_primary", "unavailable"]
EndpointKey = tuple[str, int, str, str, bool, str, bool]

CONNECT_FAILURE_WINDOW = 10.0
CONNECT_FAILURE_LIMIT = 2
ZERO_RECV_LIMIT = 6
RETRY_DELAYS = (60.0, 180.0, 300.0)


def endpoint_key(endpoint: UpstreamProxyEndpoint) -> EndpointKey:
    return (
        str(endpoint.host or "").strip().lower(),
        int(endpoint.port or 0),
        str(endpoint.username or ""),
        str(endpoint.password or ""),
        bool(endpoint.tls),
        str(endpoint.tls_server_name or "").strip().lower(),
        bool(endpoint.tls_verify),
    )


def endpoint_display_name(endpoint: UpstreamProxyEndpoint | None) -> str:
    if endpoint is None:
        return ""
    name = str(endpoint.preset_name or "").strip()
    if name:
        return name
    host = str(endpoint.host or "").strip()
    port = int(endpoint.port or 0)
    return f"{host}:{port}" if host and port > 0 else "внешний прокси"


def _normalize_endpoint(endpoint: UpstreamProxyEndpoint) -> UpstreamProxyEndpoint | None:
    host = str(endpoint.host or "").strip()
    try:
        port = int(endpoint.port or 0)
    except (TypeError, ValueError):
        port = 0
    if not host or port <= 0:
        return None
    return UpstreamProxyEndpoint(
        host=host,
        port=port,
        username=str(endpoint.username or ""),
        password=str(endpoint.password or ""),
        tls=bool(endpoint.tls),
        tls_server_name=str(endpoint.tls_server_name or "").strip(),
        tls_verify=bool(endpoint.tls_verify),
        preset_id=str(endpoint.preset_id or "").strip(),
        preset_name=str(endpoint.preset_name or "").strip(),
    )


def endpoints_from_config(config: UpstreamProxyConfig) -> tuple[UpstreamProxyEndpoint, ...]:
    if not config.enabled:
        return ()
    primary = UpstreamProxyEndpoint(
        host=config.host,
        port=config.port,
        username=config.username,
        password=config.password,
        tls=config.tls,
        tls_server_name=config.tls_server_name,
        tls_verify=config.tls_verify,
        preset_id=config.preset_id,
        preset_name=config.preset_name,
    )
    result: list[UpstreamProxyEndpoint] = []
    seen: set[EndpointKey] = set()
    for raw_endpoint in (primary, *tuple(config.fallback_proxies or ())):
        endpoint = _normalize_endpoint(raw_endpoint)
        if endpoint is None:
            continue
        key = endpoint_key(endpoint)
        if key in seen:
            continue
        seen.add(key)
        result.append(endpoint)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class UpstreamRuntimeSnapshot:
    selected_preset_id: str = ""
    selected_name: str = ""
    active_preset_id: str = ""
    active_name: str = ""
    state: UpstreamState = "unavailable"
    reason: str = ""
    generation: int = 0
    queued_connections: int = 0
    rejected_connections: int = 0


@dataclass(frozen=True, slots=True)
class UpstreamAttempt:
    endpoint: UpstreamProxyEndpoint
    generation: int
    is_probe: bool = False
    primary_probe: bool = False


@dataclass(frozen=True, slots=True)
class UpstreamTransition:
    old_endpoint: UpstreamProxyEndpoint | None
    new_endpoint: UpstreamProxyEndpoint | None
    reason: str
    old_generation: int
    generation: int
    retry_after: float = 0.0


@dataclass(slots=True)
class _EndpointHealth:
    connect_failures: deque[float] = field(default_factory=deque)
    zero_recv_count: int = 0
    failure_round: int = 0
    unavailable_until: float = 0.0


class UpstreamStateController:
    """Owns the one active bundled SOCKS server for the whole proxy."""

    def __init__(
        self,
        config: UpstreamProxyConfig,
        *,
        on_snapshot: Callable[[UpstreamRuntimeSnapshot], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clock = clock
        self._on_snapshot = on_snapshot
        self._queued_connections = 0
        self._rejected_connections = 0
        self._last_snapshot: UpstreamRuntimeSnapshot | None = None
        self._generation = 0
        self._reason = ""
        self._health: dict[EndpointKey, _EndpointHealth] = {}
        self._probe_key: EndpointKey | None = None
        self._probe_is_primary = False
        self._endpoints: tuple[UpstreamProxyEndpoint, ...] = ()
        self._active: UpstreamProxyEndpoint | None = None
        self.replace_config(config, reason="запуск")

    @property
    def endpoints(self) -> tuple[UpstreamProxyEndpoint, ...]:
        return self._endpoints

    @property
    def selected(self) -> UpstreamProxyEndpoint | None:
        return self._endpoints[0] if self._endpoints else None

    @property
    def active(self) -> UpstreamProxyEndpoint | None:
        return self._active

    @property
    def generation(self) -> int:
        return self._generation

    def snapshot(self) -> UpstreamRuntimeSnapshot:
        selected = self.selected
        active = self._active
        if active is None:
            state: UpstreamState = (
                "checking_primary"
                if self._probe_key is not None
                and selected is not None
                and self._probe_key == endpoint_key(selected)
                else "unavailable"
            )
        elif self._probe_is_primary:
            state = "checking_primary"
        elif selected is not None and endpoint_key(active) == endpoint_key(selected):
            state = "primary"
        else:
            state = "fallback"
        return UpstreamRuntimeSnapshot(
            selected_preset_id=str(selected.preset_id or "") if selected else "",
            selected_name=endpoint_display_name(selected),
            active_preset_id=str(active.preset_id or "") if active else "",
            active_name=endpoint_display_name(active),
            state=state,
            reason=self._reason,
            generation=self._generation,
            queued_connections=self._queued_connections,
            rejected_connections=self._rejected_connections,
        )

    def emit_snapshot(self, *, force: bool = False) -> UpstreamRuntimeSnapshot:
        snapshot = self.snapshot()
        if force or snapshot != self._last_snapshot:
            self._last_snapshot = snapshot
            if self._on_snapshot is not None:
                try:
                    self._on_snapshot(snapshot)
                except Exception:
                    pass
        return snapshot

    def set_queue_state(self, queued: int, rejected: int) -> None:
        self._queued_connections = max(0, int(queued))
        self._rejected_connections = max(0, int(rejected))
        self.emit_snapshot()

    def replace_config(
        self,
        config: UpstreamProxyConfig,
        *,
        reason: str = "настройка изменена",
    ) -> UpstreamTransition | None:
        old_endpoint = self._active
        old_generation = self._generation
        self._endpoints = endpoints_from_config(config)
        self._health = {endpoint_key(item): _EndpointHealth() for item in self._endpoints}
        self._active = self._endpoints[0] if self._endpoints else None
        self._probe_key = None
        self._probe_is_primary = False
        self._reason = reason if self._active is not None else "сервер не настроен"
        old_key = endpoint_key(old_endpoint) if old_endpoint is not None else None
        new_key = endpoint_key(self._active) if self._active is not None else None
        if self._generation == 0 and self._active is not None:
            self._generation = 1
        elif old_key != new_key:
            self._generation += 1
        transition = None
        if old_generation > 0 and old_key != new_key:
            transition = UpstreamTransition(
                old_endpoint=old_endpoint,
                new_endpoint=self._active,
                reason=reason,
                old_generation=old_generation,
                generation=self._generation,
            )
        self.emit_snapshot(force=True)
        return transition

    def current_endpoint(self) -> UpstreamProxyEndpoint | None:
        return self._active

    def has_available_endpoint(self) -> bool:
        if self._active is not None:
            return True
        now = self._clock()
        return any(self._health_for(item).unavailable_until <= now for item in self._endpoints)

    def select_attempt(self) -> UpstreamAttempt | None:
        if not self._endpoints:
            return None
        now = self._clock()
        primary = self.selected
        if (
            self._active is not None
            and primary is not None
            and endpoint_key(self._active) != endpoint_key(primary)
            and self._probe_key is None
            and self._health_for(primary).unavailable_until <= now
        ):
            self._probe_key = endpoint_key(primary)
            self._probe_is_primary = True
            self._reason = "проверяем восстановление основного сервера"
            self.emit_snapshot()
            return UpstreamAttempt(primary, self._generation, is_probe=True, primary_probe=True)

        if self._active is not None:
            return UpstreamAttempt(self._active, self._generation)

        if self._probe_key is not None:
            return None
        candidate = self._first_available(now)
        if candidate is None:
            self._reason = "все серверы временно недоступны"
            self.emit_snapshot()
            return None
        self._probe_key = endpoint_key(candidate)
        self._probe_is_primary = primary is not None and self._probe_key == endpoint_key(primary)
        self._reason = f"пробная проверка: {endpoint_display_name(candidate)}"
        self.emit_snapshot()
        return UpstreamAttempt(
            candidate,
            self._generation,
            is_probe=True,
            primary_probe=self._probe_is_primary,
        )

    def record_connect_failure(
        self,
        attempt: UpstreamAttempt,
        reason: str,
    ) -> UpstreamTransition | None:
        if not self._attempt_is_current(attempt):
            return None
        now = self._clock()
        health = self._health_for(attempt.endpoint)
        if attempt.is_probe:
            retry_after = self._penalize(attempt.endpoint, now)
            self._clear_probe(attempt)
            self._reason = f"пробное подключение не удалось: {reason}"
            self.emit_snapshot()
            return None
        health.connect_failures.append(now)
        while health.connect_failures and now - health.connect_failures[0] > CONNECT_FAILURE_WINDOW:
            health.connect_failures.popleft()
        if len(health.connect_failures) < CONNECT_FAILURE_LIMIT:
            return None
        retry_after = self._penalize(attempt.endpoint, now)
        return self._fail_active(
            attempt,
            reason=f"две ошибки подключения за 10 секунд: {reason}",
            retry_after=retry_after,
        )

    def record_zero_recv(
        self,
        attempt: UpstreamAttempt,
        reason: str = "соединение не получило ответных данных",
    ) -> UpstreamTransition | None:
        if not self._attempt_is_current(attempt):
            return None
        now = self._clock()
        health = self._health_for(attempt.endpoint)
        if attempt.is_probe:
            self._penalize(attempt.endpoint, now)
            self._clear_probe(attempt)
            self._reason = f"пробная проверка не получила данные: {endpoint_display_name(attempt.endpoint)}"
            self.emit_snapshot()
            return None
        health.zero_recv_count += 1
        if health.zero_recv_count < ZERO_RECV_LIMIT:
            return None
        retry_after = self._penalize(attempt.endpoint, now)
        return self._fail_active(
            attempt,
            reason=f"шесть соединений без ответных данных: {reason}",
            retry_after=retry_after,
        )

    def record_recv_ok(self, attempt: UpstreamAttempt) -> UpstreamTransition | None:
        if not self._attempt_is_current(attempt):
            return None
        health = self._health_for(attempt.endpoint)
        health.connect_failures.clear()
        health.zero_recv_count = 0
        health.failure_round = 0
        health.unavailable_until = 0.0
        if attempt.is_probe:
            self._clear_probe(attempt)
            if self._active is None or attempt.primary_probe:
                return self._switch_active(
                    attempt.endpoint,
                    reason="сервер подтвердил работу реальными данными",
                )
        if self._active is not None and endpoint_key(self._active) == endpoint_key(attempt.endpoint):
            self._reason = "сервер передаёт данные"
            self.emit_snapshot()
        return None

    def abandon_attempt(self, attempt: UpstreamAttempt) -> None:
        """Release a probe cancelled locally without blaming the server."""
        if attempt.is_probe and self._attempt_is_current(attempt):
            self._clear_probe(attempt)
            self._reason = (
                "основной сервер ждёт следующей пробной проверки"
                if self._active is not None
                else "все серверы временно недоступны"
            )
            self.emit_snapshot()

    def _attempt_is_current(self, attempt: UpstreamAttempt) -> bool:
        if attempt.generation != self._generation:
            return False
        key = endpoint_key(attempt.endpoint)
        if attempt.is_probe:
            return key == self._probe_key
        return self._active is not None and key == endpoint_key(self._active)

    def _health_for(self, endpoint: UpstreamProxyEndpoint) -> _EndpointHealth:
        return self._health.setdefault(endpoint_key(endpoint), _EndpointHealth())

    def _first_available(self, now: float, *, exclude: EndpointKey | None = None) -> UpstreamProxyEndpoint | None:
        for endpoint in self._endpoints:
            key = endpoint_key(endpoint)
            if key == exclude:
                continue
            if self._health_for(endpoint).unavailable_until <= now:
                return endpoint
        return None

    def _penalize(self, endpoint: UpstreamProxyEndpoint, now: float) -> float:
        health = self._health_for(endpoint)
        health.failure_round += 1
        retry_after = RETRY_DELAYS[min(health.failure_round - 1, len(RETRY_DELAYS) - 1)]
        health.unavailable_until = now + retry_after
        health.connect_failures.clear()
        health.zero_recv_count = 0
        return retry_after

    def _clear_probe(self, attempt: UpstreamAttempt) -> None:
        if self._probe_key == endpoint_key(attempt.endpoint):
            self._probe_key = None
            self._probe_is_primary = False

    def _fail_active(
        self,
        attempt: UpstreamAttempt,
        *,
        reason: str,
        retry_after: float,
    ) -> UpstreamTransition | None:
        if self._active is None or endpoint_key(self._active) != endpoint_key(attempt.endpoint):
            return None
        replacement = self._first_available(self._clock(), exclude=endpoint_key(attempt.endpoint))
        return self._switch_active(replacement, reason=reason, retry_after=retry_after)

    def _switch_active(
        self,
        endpoint: UpstreamProxyEndpoint | None,
        *,
        reason: str,
        retry_after: float = 0.0,
    ) -> UpstreamTransition | None:
        old_endpoint = self._active
        old_key = endpoint_key(old_endpoint) if old_endpoint is not None else None
        new_key = endpoint_key(endpoint) if endpoint is not None else None
        if old_key == new_key:
            self._reason = reason
            self.emit_snapshot()
            return None
        old_generation = self._generation
        self._generation += 1
        self._active = endpoint
        self._probe_key = None
        self._probe_is_primary = False
        self._reason = reason if endpoint is not None else "все серверы временно недоступны"
        transition = UpstreamTransition(
            old_endpoint=old_endpoint,
            new_endpoint=endpoint,
            reason=reason,
            old_generation=old_generation,
            generation=self._generation,
            retry_after=retry_after,
        )
        self.emit_snapshot(force=True)
        return transition


__all__ = [
    "CONNECT_FAILURE_LIMIT",
    "CONNECT_FAILURE_WINDOW",
    "RETRY_DELAYS",
    "ZERO_RECV_LIMIT",
    "UpstreamAttempt",
    "UpstreamRuntimeSnapshot",
    "UpstreamStateController",
    "UpstreamTransition",
    "endpoint_display_name",
    "endpoint_key",
    "endpoints_from_config",
]
