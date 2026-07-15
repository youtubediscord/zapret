from __future__ import annotations

import asyncio
import unittest

from telegram_proxy.proxy.routing import UpstreamProxyConfig, UpstreamProxyEndpoint
from telegram_proxy.proxy.upstream_controller import (
    RETRY_DELAYS,
    ZERO_RECV_LIMIT,
    ZERO_RECV_OBSERVATION_WINDOW,
    UpstreamStateController,
)
from telegram_proxy.proxy.upstream_runtime import (
    FULL_CONNECT_TIMEOUT,
    MAX_QUEUED_CONNECTIONS,
    QUEUE_TIMEOUT,
    UpstreamBusyError,
    UpstreamConnectError,
    UpstreamConnectionExecutor,
)
from telegram_proxy.ui.runtime_helpers import format_upstream_runtime_state


class _Clock:
    def __init__(self) -> None:
        self.value = 1000.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += float(seconds)


class _Writer:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


def _endpoint(preset_id: str, name: str, host: str, port: int = 443) -> UpstreamProxyEndpoint:
    return UpstreamProxyEndpoint(
        host=host,
        port=port,
        username=f"{preset_id}_user",
        password=f"{preset_id}_password",
        tls=True,
        tls_server_name="www.google.com",
        preset_id=preset_id,
        preset_name=name,
    )


def _config(*, fallbacks: tuple[UpstreamProxyEndpoint, ...] = ()) -> UpstreamProxyConfig:
    primary = _endpoint("de1", "Германия 1", "95.128.157.251", 9443)
    return UpstreamProxyConfig(
        enabled=True,
        mode="always",
        host=primary.host,
        port=primary.port,
        username=primary.username,
        password=primary.password,
        tls=primary.tls,
        tls_server_name=primary.tls_server_name,
        preset_id=primary.preset_id,
        preset_name=primary.preset_name,
        fallback_proxies=fallbacks,
    )


class UpstreamStateControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = _Clock()
        self.uk = _endpoint("uk", "Великобритания", "144.31.213.98")
        self.no = _endpoint("no", "Норвегия", "31.76.5.8")
        self.controller = UpstreamStateController(
            _config(fallbacks=(self.uk, self.no)),
            clock=self.clock,
        )

    def _fail_active_twice(self):
        first = self.controller.select_attempt()
        second = self.controller.select_attempt()
        self.assertIsNone(self.controller.record_connect_failure(first, "timeout"))
        return self.controller.record_connect_failure(second, "timeout")

    def test_all_connections_use_one_active_server(self) -> None:
        attempts = [self.controller.select_attempt() for _ in range(50)]
        self.assertTrue(all(item is not None for item in attempts))
        self.assertEqual({item.endpoint.host for item in attempts}, {"95.128.157.251"})
        self.assertEqual({item.generation for item in attempts}, {1})

    def test_concurrent_failures_produce_one_global_switch(self) -> None:
        attempts = [self.controller.select_attempt() for _ in range(8)]
        transitions = [
            self.controller.record_connect_failure(item, "timeout")
            for item in attempts
        ]
        transitions = [item for item in transitions if item is not None]
        self.assertEqual(len(transitions), 1)
        self.assertEqual(self.controller.snapshot().active_name, "Великобритания")
        self.assertEqual(self.controller.snapshot().generation, 2)

    def test_recv_zero_is_not_success_and_switches_only_after_six(self) -> None:
        attempts = [self.controller.select_attempt() for _ in range(ZERO_RECV_LIMIT)]
        for item in attempts[:-1]:
            self.assertIsNone(self.controller.record_zero_recv(item))
            self.assertEqual(self.controller.snapshot().active_name, "Германия 1")
        self.clock.advance(ZERO_RECV_OBSERVATION_WINDOW)
        transition = self.controller.record_zero_recv(attempts[-1])
        self.assertIsNotNone(transition)
        self.assertEqual(self.controller.snapshot().active_name, "Великобритания")

    def test_concurrent_zero_burst_waits_for_inflight_real_data(self) -> None:
        attempts = [self.controller.select_attempt() for _ in range(ZERO_RECV_LIMIT + 1)]

        for item in attempts[:ZERO_RECV_LIMIT]:
            self.assertIsNone(self.controller.record_zero_recv(item))

        self.assertEqual(self.controller.snapshot().active_name, "Германия 1")
        self.assertIsNone(self.controller.record_recv_ok(attempts[-1]))
        self.assertEqual(self.controller.snapshot().active_name, "Германия 1")

    def test_primary_returns_only_after_probe_receives_real_data(self) -> None:
        self.assertIsNotNone(self._fail_active_twice())
        self.clock.advance(RETRY_DELAYS[0])
        probe = self.controller.select_attempt()
        self.assertTrue(probe.primary_probe)
        self.assertEqual(self.controller.snapshot().state, "checking_primary")
        regular = self.controller.select_attempt()
        self.assertEqual(regular.endpoint.preset_id, "uk")

        self.controller.record_zero_recv(probe)
        self.assertEqual(self.controller.snapshot().active_preset_id, "uk")
        self.assertEqual(self.controller.snapshot().state, "fallback")

        self.clock.advance(RETRY_DELAYS[1])
        probe = self.controller.select_attempt()
        transition = self.controller.record_recv_ok(probe)
        self.assertIsNotNone(transition)
        self.assertEqual(self.controller.snapshot().active_preset_id, "de1")
        self.assertEqual(self.controller.snapshot().state, "primary")

    def test_retry_delays_grow_to_five_minutes_without_busy_loop(self) -> None:
        manual = UpstreamProxyConfig(enabled=True, host="127.0.0.1", port=1080)
        controller = UpstreamStateController(manual, clock=self.clock)
        first = controller.select_attempt()
        second = controller.select_attempt()
        controller.record_connect_failure(first, "timeout")
        controller.record_connect_failure(second, "timeout")
        self.assertIsNone(controller.active)
        self.assertIsNone(controller.select_attempt())

        self.clock.advance(RETRY_DELAYS[0])
        probe = controller.select_attempt()
        self.assertIsNotNone(probe)
        controller.record_connect_failure(probe, "timeout")
        self.clock.advance(RETRY_DELAYS[1] - 1)
        self.assertIsNone(controller.select_attempt())
        self.clock.advance(1)
        probe = controller.select_attempt()
        controller.record_connect_failure(probe, "timeout")
        self.clock.advance(RETRY_DELAYS[2] - 1)
        self.assertIsNone(controller.select_attempt())
        self.clock.advance(1)
        self.assertIsNotNone(controller.select_attempt())

    def test_manual_server_has_no_hidden_bundled_fallback(self) -> None:
        manual = UpstreamProxyConfig(
            enabled=True,
            host="127.0.0.1",
            port=1080,
            username="user",
            password="password",
        )
        controller = UpstreamStateController(manual, clock=self.clock)
        first = controller.select_attempt()
        second = controller.select_attempt()
        controller.record_connect_failure(first, "timeout")
        controller.record_connect_failure(second, "timeout")
        self.assertIsNone(controller.active)
        self.assertEqual(len(controller.endpoints), 1)

    def test_gui_text_keeps_selected_server_separate_from_fallback(self) -> None:
        self._fail_active_twice()
        text = format_upstream_runtime_state(self.controller.snapshot())
        self.assertIn("Выбрано: Германия 1", text)
        self.assertIn("Сейчас используется: Великобритания (резерв)", text)


class UpstreamConnectionExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def test_each_connection_dials_only_the_global_active_server_once(self) -> None:
        calls: list[str] = []

        async def failing_connector(proxy_host, *_args, **_kwargs):
            calls.append(proxy_host)
            raise TimeoutError("dead")

        runtime = UpstreamConnectionExecutor(
            _config(fallbacks=(_endpoint("uk", "Великобритания", "144.31.213.98"),)),
            connector=failing_connector,
        )
        with self.assertRaises(UpstreamConnectError):
            await runtime.open_connection("149.154.167.51", 443)
        self.assertEqual(calls, ["95.128.157.251"])

        with self.assertRaises(UpstreamConnectError):
            await runtime.open_connection("149.154.167.51", 443)
        self.assertEqual(calls, ["95.128.157.251", "95.128.157.251"])
        self.assertEqual(runtime.snapshot().active_name, "Великобритания")

    async def test_established_relays_do_not_occupy_connect_slots(self) -> None:
        active = 0
        peak = 0

        async def connector(*_args, **_kwargs):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0)
            active -= 1
            return asyncio.StreamReader(), _Writer()

        runtime = UpstreamConnectionExecutor(_config(), connect_limit=4, connector=connector)
        opened = await asyncio.gather(
            *(runtime.open_connection("149.154.167.51", 443) for _ in range(40))
        )
        self.assertLessEqual(peak, 4)
        self.assertEqual(len(opened), 40)
        self.assertEqual(runtime.queued_connections, 0)
        for item in opened:
            runtime.release(item)

    async def test_burst_of_1000_never_queues_more_than_64(self) -> None:
        gate = asyncio.Event()
        entered = 0
        snapshots = []

        async def connector(*_args, **_kwargs):
            nonlocal entered
            entered += 1
            await gate.wait()
            return asyncio.StreamReader(), _Writer()

        runtime = UpstreamConnectionExecutor(
            _config(),
            connect_limit=4,
            connector=connector,
            on_snapshot=snapshots.append,
        )
        tasks = [
            asyncio.create_task(runtime.open_connection("149.154.167.51", 443))
            for _ in range(1000)
        ]
        for _ in range(100):
            if entered == 4 and runtime.queued_connections == MAX_QUEUED_CONNECTIONS:
                break
            await asyncio.sleep(0)
        self.assertEqual(entered, 4)
        self.assertEqual(runtime.queued_connections, MAX_QUEUED_CONNECTIONS)
        self.assertLessEqual(max(item.queued_connections for item in snapshots), 64)

        gate.set()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        opened = [item for item in results if not isinstance(item, BaseException)]
        rejected = [item for item in results if isinstance(item, UpstreamBusyError)]
        self.assertEqual(len(opened), 68)
        self.assertEqual(len(rejected), 932)
        self.assertEqual(runtime.queued_connections, 0)
        for item in opened:
            runtime.release(item)

    def test_limits_match_the_public_contract(self) -> None:
        self.assertEqual(MAX_QUEUED_CONNECTIONS, 64)
        self.assertLessEqual(QUEUE_TIMEOUT, 2.0)
        self.assertLessEqual(FULL_CONNECT_TIMEOUT, 5.0)


if __name__ == "__main__":
    unittest.main()
