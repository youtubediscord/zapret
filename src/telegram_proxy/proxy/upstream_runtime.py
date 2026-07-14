from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Callable

from telegram_proxy.proxy import socks5
from telegram_proxy.proxy.routing import UpstreamProxyConfig, UpstreamProxyEndpoint
from telegram_proxy.proxy.upstream_controller import (
    UpstreamAttempt,
    UpstreamRuntimeSnapshot,
    UpstreamStateController,
    UpstreamTransition,
    endpoint_display_name,
)


MAX_QUEUED_CONNECTIONS = 64
QUEUE_TIMEOUT = 2.0
FULL_CONNECT_TIMEOUT = 5.0


class UpstreamRuntimeError(Exception):
    pass


class UpstreamBusyError(UpstreamRuntimeError):
    pass


class UpstreamUnavailableError(UpstreamRuntimeError):
    pass


class UpstreamStaleError(UpstreamRuntimeError):
    pass


class UpstreamConnectError(UpstreamRuntimeError):
    def __init__(
        self,
        message: str,
        *,
        endpoint: UpstreamProxyEndpoint | None = None,
    ) -> None:
        super().__init__(message)
        self.endpoint = endpoint


@dataclass(slots=True)
class OpenedUpstream:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    attempt: UpstreamAttempt
    elapsed: float
    task: asyncio.Task | None
    verdict_recorded: bool = False

    @property
    def endpoint(self) -> UpstreamProxyEndpoint:
        return self.attempt.endpoint


class UpstreamConnectionExecutor:
    """Queues only SOCKS handshakes; established Telegram relays run freely."""

    def __init__(
        self,
        config: UpstreamProxyConfig,
        *,
        connect_limit: int = 4,
        on_snapshot: Callable[[UpstreamRuntimeSnapshot], None] | None = None,
        on_log: Callable[[str], None] | None = None,
        connector=None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clock = clock
        self._on_log = on_log
        self._connector = connector
        self._connect_limit = max(1, min(32, int(connect_limit or 4)))
        self._semaphore = asyncio.Semaphore(self._connect_limit)
        self._queued = 0
        self._rejected = 0
        self._tasks: dict[asyncio.Task, int] = {}
        self._controller = UpstreamStateController(config, on_snapshot=on_snapshot, clock=clock)

    @property
    def controller(self) -> UpstreamStateController:
        return self._controller

    @property
    def queued_connections(self) -> int:
        return self._queued

    @property
    def rejected_connections(self) -> int:
        return self._rejected

    def snapshot(self) -> UpstreamRuntimeSnapshot:
        return self._controller.snapshot()

    def emit_snapshot(self, *, force: bool = False) -> UpstreamRuntimeSnapshot:
        return self._controller.emit_snapshot(force=force)

    def current_endpoint(self) -> UpstreamProxyEndpoint | None:
        return self._controller.current_endpoint()

    def has_available_endpoint(self) -> bool:
        return self._controller.has_available_endpoint()

    async def open_connection(
        self,
        target_host: str,
        target_port: int,
    ) -> OpenedUpstream:
        attempt = self._controller.select_attempt()
        if attempt is None:
            raise UpstreamUnavailableError("внешний SOCKS временно недоступен")

        task = asyncio.current_task()
        if task is not None:
            self._tasks[task] = attempt.generation
        started = self._clock()
        acquired = False
        try:
            await self._acquire_slot(started)
            acquired = True
            remaining = FULL_CONNECT_TIMEOUT - (self._clock() - started)
            if remaining <= 0:
                raise UpstreamBusyError("истекло общее время ожидания подключения")
            endpoint = attempt.endpoint
            try:
                reader, writer = await asyncio.wait_for(
                    (self._connector or socks5.connect_via_socks5)(
                        endpoint.host,
                        endpoint.port,
                        target_host,
                        target_port,
                        username=endpoint.username,
                        password=endpoint.password,
                        timeout=remaining,
                        tls=endpoint.tls,
                        tls_server_name=endpoint.tls_server_name,
                        tls_verify=endpoint.tls_verify,
                    ),
                    timeout=remaining,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                transition = self._controller.record_connect_failure(
                    attempt,
                    f"{type(exc).__name__}: {exc}",
                )
                self._handle_transition(transition, current_task=task)
                raise UpstreamConnectError(
                    str(exc) or type(exc).__name__,
                    endpoint=attempt.endpoint,
                ) from exc

            if attempt.generation != self._controller.generation:
                await self._close_writer(writer)
                raise UpstreamStaleError("сервер сменился во время подключения")
            return OpenedUpstream(
                reader=reader,
                writer=writer,
                attempt=attempt,
                elapsed=self._clock() - started,
                task=task,
            )
        except BaseException:
            self._controller.abandon_attempt(attempt)
            if task is not None:
                self._tasks.pop(task, None)
            raise
        finally:
            if acquired:
                self._semaphore.release()

    def record_recv_ok(self, opened: OpenedUpstream) -> None:
        if opened.verdict_recorded:
            return
        opened.verdict_recorded = True
        transition = self._controller.record_recv_ok(opened.attempt)
        self._handle_transition(transition, current_task=opened.task)

    def record_zero_recv(self, opened: OpenedUpstream) -> None:
        if opened.verdict_recorded:
            return
        opened.verdict_recorded = True
        transition = self._controller.record_zero_recv(opened.attempt)
        self._handle_transition(transition, current_task=opened.task)

    def release(self, opened: OpenedUpstream) -> None:
        if not opened.verdict_recorded:
            self._controller.abandon_attempt(opened.attempt)
        if opened.task is not None:
            self._tasks.pop(opened.task, None)

    def apply_config(self, config: UpstreamProxyConfig) -> None:
        try:
            current = asyncio.current_task()
        except RuntimeError:
            current = None
        transition = self._controller.replace_config(config, reason="выбран другой основной сервер")
        self._handle_transition(transition, current_task=current)

    async def close(self) -> None:
        current = asyncio.current_task()
        tasks = [task for task in self._tasks if task is not current and not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

    async def _acquire_slot(self, started: float) -> None:
        if not self._semaphore.locked():
            await self._semaphore.acquire()
            return
        if self._queued >= MAX_QUEUED_CONNECTIONS:
            self._rejected += 1
            self._sync_queue_snapshot()
            raise UpstreamBusyError("очередь подключения переполнена")
        self._queued += 1
        self._sync_queue_snapshot()
        try:
            remaining = min(QUEUE_TIMEOUT, FULL_CONNECT_TIMEOUT - (self._clock() - started))
            if remaining <= 0:
                raise asyncio.TimeoutError
            await asyncio.wait_for(self._semaphore.acquire(), timeout=remaining)
        except asyncio.TimeoutError as exc:
            self._rejected += 1
            raise UpstreamBusyError("ожидание в очереди превысило 2 секунды") from exc
        finally:
            self._queued -= 1
            self._sync_queue_snapshot()

    def _sync_queue_snapshot(self) -> None:
        self._controller.set_queue_state(self._queued, self._rejected)

    def _handle_transition(
        self,
        transition: UpstreamTransition | None,
        *,
        current_task: asyncio.Task | None,
    ) -> None:
        if transition is None:
            return
        old_name = endpoint_display_name(transition.old_endpoint) or "нет"
        new_name = endpoint_display_name(transition.new_endpoint) or "временно недоступно"
        wait_text = f", повтор через {int(transition.retry_after)} с" if transition.retry_after > 0 else ""
        if self._on_log is not None:
            self._on_log(
                f"SOCKS переключён: {old_name} -> {new_name}; "
                f"причина: {transition.reason}{wait_text}"
            )
        for task, generation in list(self._tasks.items()):
            if task.done():
                self._tasks.pop(task, None)
                continue
            if generation == transition.old_generation and task is not current_task:
                task.cancel()
        if current_task is not None and current_task in self._tasks:
            self._tasks[current_task] = transition.generation

    @staticmethod
    async def _close_writer(writer: asyncio.StreamWriter) -> None:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


__all__ = [
    "FULL_CONNECT_TIMEOUT",
    "MAX_QUEUED_CONNECTIONS",
    "QUEUE_TIMEOUT",
    "OpenedUpstream",
    "UpstreamBusyError",
    "UpstreamConnectError",
    "UpstreamConnectionExecutor",
    "UpstreamRuntimeError",
    "UpstreamStaleError",
    "UpstreamUnavailableError",
]
