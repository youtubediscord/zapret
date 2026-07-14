"""Тесты надёжного переключения upstream-сервера Telegram Proxy.

Покрывают spec .agent/tasks/tg-proxy-upstream-switch/spec.md:
- AC1/AC2 — конвейер save→restart не теряет запросы (merge, отложенный повтор);
- AC3 — порт освобождается первым шагом stop, bind ретраится;
- AC4 — горячая замена upstream-конфига меняет одно общее поколение соединений.
"""

from __future__ import annotations

import asyncio
import unittest

from telegram_proxy import TelegramProxyRuntime
from telegram_proxy.ui.settings_save_flow import merge_restart_request, normalize_restart_request
from telegram_proxy.wss_proxy import TelegramWSProxy, UpstreamProxyConfig
from telegram_proxy.proxy.routing import UpstreamProxyEndpoint


def _endpoint(host: str, preset_id: str = "") -> UpstreamProxyEndpoint:
    return UpstreamProxyEndpoint(
        host=host, port=443, username="", password="", preset_id=preset_id or host
    )


def _config_with_fallbacks(primary: str, fallbacks: tuple[str, ...]) -> UpstreamProxyConfig:
    return UpstreamProxyConfig(
        enabled=True,
        host=primary,
        port=443,
        preset_id=primary,
        preset_name=primary.upper(),
        fallback_proxies=tuple(_endpoint(h) for h in fallbacks),
    )


class SingleActiveUpstreamTests(unittest.TestCase):
    """Каталог задаёт порядок, но каждое соединение получает один общий сервер."""

    def test_fresh_start_uses_catalog_primary_for_every_connection(self) -> None:
        proxy = TelegramWSProxy(
            port=11353, upstream_config=_config_with_fallbacks("uk", ("de", "no", "nl"))
        )
        controller = proxy._upstream_runtime.controller
        self.assertEqual([item.host for item in controller.endpoints], ["uk", "de", "no", "nl"])
        self.assertEqual(
            {controller.select_attempt().endpoint.host for _ in range(20)},
            {"uk"},
        )

    def test_plain_and_tls_catalog_entries_are_both_preserved(self) -> None:
        tls = UpstreamProxyEndpoint(host="tls", port=443, tls=True)
        plain = UpstreamProxyEndpoint(host="plain", port=1080, tls=False)
        config = UpstreamProxyConfig(
            enabled=True,
            host=tls.host,
            port=tls.port,
            tls=True,
            fallback_proxies=(plain,),
        )
        proxy = TelegramWSProxy(port=11353, upstream_config=config)
        self.assertEqual(
            [item.host for item in proxy._upstream_runtime.controller.endpoints],
            ["tls", "plain"],
        )


class MergeRestartRequestTests(unittest.TestCase):
    def test_restart_family_dominates_hot_swap(self) -> None:
        # Полный рестарт применяет ВСЁ (включая upstream), поэтому при слиянии
        # в одном проходе очереди он побеждает горячую замену.
        self.assertEqual(merge_restart_request("upstream", "schedule"), "schedule")
        self.assertEqual(merge_restart_request("schedule", "upstream"), "schedule")
        self.assertEqual(merge_restart_request("upstream", "now"), "now")
        self.assertEqual(merge_restart_request("now", "upstream"), "now")

    def test_immediate_dominates_scheduled_within_hot_swap(self) -> None:
        self.assertEqual(merge_restart_request("upstream_schedule", "upstream"), "upstream")
        self.assertEqual(merge_restart_request("upstream", "upstream_schedule"), "upstream")

    def test_immediate_dominates_scheduled_within_restart(self) -> None:
        self.assertEqual(merge_restart_request("schedule", "now"), "now")
        self.assertEqual(merge_restart_request("now", "schedule"), "now")

    def test_normalize_accepts_new_values(self) -> None:
        self.assertEqual(normalize_restart_request("upstream"), "upstream")
        self.assertEqual(normalize_restart_request("upstream_schedule"), "upstream_schedule")
        self.assertEqual(normalize_restart_request("bogus"), "")


class RestartDispatchTests(unittest.TestCase):
    """Каждый restart-ключ ведёт в СВОЁ терминальное действие (без перегрузки).

    Регрессия, которую это фиксирует: pool_size/buffer_kb ("schedule") должны
    вызывать полный рестарт, а НЕ горячую замену upstream.
    """

    def _run_dispatch(self, restart: str):
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        from telegram_proxy.ui import page as telegram_proxy_page

        page = telegram_proxy_page.TelegramProxyPage.__new__(telegram_proxy_page.TelegramProxyPage)
        page._cleanup_in_progress = False
        page._settings_save_restart_pending = restart
        runtime = Mock()
        runtime.is_current.return_value = True
        page._settings_save_runtime = runtime
        # очередь пуста → доходим до диспетчеризации restart
        page._queued_worker_state = Mock(
            return_value=SimpleNamespace(has_pending=Mock(return_value=False))
        )
        calls = []
        page._schedule_restart = lambda: calls.append("schedule")
        page._schedule_upstream_apply = lambda: calls.append("upstream_schedule")
        page._apply_upstream_hot_swap = lambda: calls.append("upstream")
        page._restart_if_running = lambda: calls.append("now")
        page._update_manual_instructions = lambda: None
        with patch.object(telegram_proxy_page, "log"):
            telegram_proxy_page.TelegramProxyPage._on_settings_save_finished(
                page, 1, "act", None, {"restart": restart}
            )
        return calls

    def test_schedule_triggers_full_restart_not_hot_swap(self) -> None:
        self.assertEqual(self._run_dispatch("schedule"), ["schedule"])

    def test_upstream_schedule_triggers_debounced_hot_swap(self) -> None:
        self.assertEqual(self._run_dispatch("upstream_schedule"), ["upstream_schedule"])

    def test_upstream_triggers_immediate_hot_swap(self) -> None:
        self.assertEqual(self._run_dispatch("upstream"), ["upstream"])

    def test_now_triggers_immediate_restart(self) -> None:
        self.assertEqual(self._run_dispatch("now"), ["now"])


class RestartPendingNotLostTests(unittest.TestCase):
    """AC1/AC2: запрос рестарта не дропается, когда цикл рестарта/старта занят."""

    class _Page:
        _starting = False

        def __init__(self, runtime_busy: bool):
            self._runtime_busy = runtime_busy
            self._restart_stop_runtime = self

        # интерфейс OneShotWorkerRuntime, который использует workflow
        def is_running(self) -> bool:
            return self._runtime_busy

        def start_qthread_worker(self, **kwargs) -> None:
            self.started = True

    class _Manager:
        is_running = True

    class _Label:
        def setText(self, _text: str) -> None:
            pass

    def _call(self, *, restarting: bool, runtime_busy: bool, starting: bool = False):
        from telegram_proxy.ui.proxy_runtime_workflow import restart_proxy_if_running

        page = self._Page(runtime_busy)
        page._starting = starting
        flags: list[bool] = []
        restart_proxy_if_running(
            page=page,
            manager=self._Manager(),
            restarting=restarting,
            set_restarting=flags.append,
            status_label=self._Label(),
            create_stop_runtime_worker=lambda **kwargs: None,
        )
        return page, flags

    def test_request_during_restart_marks_pending_again(self) -> None:
        page, flags = self._call(restarting=True, runtime_busy=False)
        self.assertTrue(getattr(page, "_restart_again_pending", False))
        self.assertEqual(flags, [])  # флаг _restarting не трогали

    def test_request_during_start_phase_marks_pending_again(self) -> None:
        # прокси ещё не запущен (is_running=False у менеджера), идёт старт
        class _StoppedManager:
            is_running = False

        from telegram_proxy.ui.proxy_runtime_workflow import restart_proxy_if_running

        page = self._Page(runtime_busy=False)
        page._starting = True
        restart_proxy_if_running(
            page=page,
            manager=_StoppedManager(),
            restarting=False,
            set_restarting=lambda _v: None,
            status_label=self._Label(),
            create_stop_runtime_worker=lambda **kwargs: None,
        )
        self.assertTrue(getattr(page, "_restart_again_pending", False))

    def test_busy_stop_runtime_does_not_leave_stuck_restarting_flag(self) -> None:
        page, flags = self._call(restarting=False, runtime_busy=True)
        self.assertTrue(getattr(page, "_restart_again_pending", False))
        self.assertEqual(flags, [])  # set_restarting(True) не вызывался

    def test_normal_restart_sets_flag_and_starts_worker(self) -> None:
        page, flags = self._call(restarting=False, runtime_busy=False)
        self.assertEqual(flags, [True])
        self.assertTrue(getattr(page, "started", False))
        self.assertFalse(getattr(page, "_restart_again_pending", False))


class HotSwapUpstreamTests(unittest.TestCase):
    """AC4: apply_upstream_config атомарно меняет общий основной сервер."""

    def test_apply_replaces_config_and_runtime_snapshot(self) -> None:
        proxy = TelegramWSProxy(
            port=11353,
            upstream_config=UpstreamProxyConfig(
                enabled=True, host="old.example", port=1080, preset_id="old", preset_name="OLD"
            ),
        )
        new_cfg = UpstreamProxyConfig(
            enabled=True, host="new.example", port=1080, preset_id="uk", preset_name="UK"
        )
        proxy.apply_upstream_config(new_cfg)

        self.assertEqual(proxy._upstream.host, "new.example")
        self.assertEqual(proxy._upstream.preset_id, "uk")
        self.assertEqual(proxy.upstream_state.selected_preset_id, "uk")
        self.assertEqual(proxy.upstream_state.active_name, "UK")

    def test_apply_none_disables_upstream(self) -> None:
        proxy = TelegramWSProxy(
            port=11353,
            upstream_config=UpstreamProxyConfig(enabled=True, host="x", port=1080),
        )
        proxy.apply_upstream_config(None)
        self.assertFalse(proxy._upstream.enabled)
        self.assertEqual(proxy.upstream_state.state, "unavailable")

    def test_new_primary_becomes_the_one_active_endpoint(self) -> None:
        proxy = TelegramWSProxy(port=11353)
        proxy.apply_upstream_config(
            UpstreamProxyConfig(enabled=True, host="new.example", port=1080, preset_id="uk"),
        )
        self.assertEqual(proxy._upstream_runtime.current_endpoint().host, "new.example")

    def test_apply_cancels_only_connections_of_old_upstream_generation(self) -> None:
        proxy = TelegramWSProxy(
            port=11353,
            upstream_config=UpstreamProxyConfig(enabled=True, host="old.example", port=1080),
        )

        async def _scenario() -> tuple[bool, bool]:
            async def _connector(*_args, **_kwargs):
                return asyncio.StreamReader(), _Writer()

            class _Writer:
                def close(self):
                    return None

                async def wait_closed(self):
                    return None

            proxy._upstream_runtime._connector = _connector
            opened = asyncio.Event()

            async def _upstream_client() -> None:
                connection = await proxy._upstream_runtime.open_connection("149.154.167.51", 443)
                opened.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    proxy._upstream_runtime.release(connection)

            async def _direct_client() -> None:
                await asyncio.Event().wait()

            upstream_task = asyncio.create_task(_upstream_client())
            direct_task = asyncio.create_task(_direct_client())
            proxy._tasks.add(direct_task)
            await opened.wait()
            proxy.apply_upstream_config(
                UpstreamProxyConfig(enabled=True, host="new.example", port=1080)
            )
            await asyncio.sleep(0)
            upstream_cancelled = upstream_task.cancelled()
            direct_still_running = not direct_task.done()
            direct_task.cancel()
            await asyncio.gather(upstream_task, direct_task, return_exceptions=True)
            return upstream_cancelled, direct_still_running

        self.assertEqual(asyncio.run(_scenario()), (True, True))


class RuntimeHotSwapTests(unittest.TestCase):
    def test_apply_returns_false_when_not_running(self) -> None:
        runtime = TelegramProxyRuntime(port=11353)
        cfg = UpstreamProxyConfig(enabled=True, host="x", port=1080)
        self.assertFalse(runtime.apply_upstream_config(cfg))

    def test_apply_delivers_config_to_running_proxy(self) -> None:
        runtime = TelegramProxyRuntime(port=0)  # порт 0 — эфемерный, без конфликтов
        started = runtime.start()
        try:
            self.assertTrue(started)
            cfg = UpstreamProxyConfig(enabled=True, host="new.example", port=1080, preset_id="uk")
            self.assertTrue(runtime.apply_upstream_config(cfg))
            # call_soon_threadsafe — даём loop время применить
            for _ in range(100):
                if runtime._proxy is not None and runtime._proxy._upstream.host == "new.example":
                    break
                import time

                time.sleep(0.02)
            self.assertEqual(runtime._proxy._upstream.host, "new.example")
        finally:
            runtime.stop()


class StopReleasesPortFirstTests(unittest.TestCase):
    """AC3: слушающий сокет закрывается до долгой очистки пулов, порт можно
    занять повторно сразу после stop()."""

    def test_port_can_be_rebound_immediately_after_stop(self) -> None:
        async def _scenario() -> None:
            proxy1 = TelegramWSProxy(port=11454, host="127.0.0.1")
            await proxy1.start()
            proxy2 = TelegramWSProxy(port=11454, host="127.0.0.1")
            await proxy1.stop()
            # bind сразу после stop — не должен упасть (retry допускается)
            await proxy2.start()
            await proxy2.stop()

        asyncio.run(_scenario())

    def test_bind_retry_survives_temporary_port_conflict(self) -> None:
        async def _scenario() -> None:
            blocker = TelegramWSProxy(port=11455, host="127.0.0.1")
            await blocker.start()
            proxy = TelegramWSProxy(port=11455, host="127.0.0.1")

            async def _release_soon() -> None:
                await asyncio.sleep(0.5)
                await blocker.stop()

            release_task = asyncio.ensure_future(_release_soon())
            # на Linux SO_REUSEADDR может позволить двойной bind — тогда
            # start() просто пройдёт; ключевое, что он не падает мгновенно.
            await proxy.start()
            await release_task
            await proxy.stop()

        asyncio.run(_scenario())


if __name__ == "__main__":
    unittest.main()
