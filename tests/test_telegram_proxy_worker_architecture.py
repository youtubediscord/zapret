import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from telegram_proxy.runtime import commands as telegram_proxy_commands
from telegram_proxy.runtime import workers as telegram_proxy_workers
import app.feature_facades.telegram_proxy as telegram_proxy_feature_module
from app.feature_facades.telegram_proxy import TelegramProxyFeature
from telegram_proxy.ui.worker_state import (
    TelegramProxyPageQueuedWorkerState,
    TelegramProxyPageWorkerState,
)


def _set_state(page, name: str, *, runtime=None, pending: bool = False, start_scheduled: bool = False):
    runtime_attr = f"_{name}_runtime"
    state_attr = f"_{name}_state"
    if runtime is None:
        runtime = page.__dict__.get(runtime_attr, SimpleNamespace(is_running=Mock(return_value=False)))
    setattr(page, runtime_attr, runtime)
    state = TelegramProxyPageWorkerState(
        runtime=runtime,
        pending=bool(pending),
        start_scheduled=bool(start_scheduled),
    )
    setattr(page, state_attr, state)
    return state


def _set_queue_state(page, name: str, *, runtime=None, pending=None, start_scheduled: bool = False):
    runtime_attr = f"_{name}_runtime"
    state_attr = f"_{name}_state"
    if runtime is None:
        runtime = page.__dict__.get(runtime_attr, SimpleNamespace(is_running=Mock(return_value=False)))
    setattr(page, runtime_attr, runtime)
    state = TelegramProxyPageQueuedWorkerState(
        runtime=runtime,
        pending=list(pending or []),
        start_scheduled=bool(start_scheduled),
    )
    setattr(page, state_attr, state)
    return state


class TelegramProxyWorkerArchitectureTests(unittest.TestCase):
    def _make_feature(self, *, manager, start_runtime=None, stop_runtime=None) -> TelegramProxyFeature:
        return TelegramProxyFeature(
            start_proxy_if_enabled_async=Mock(),
            get_proxy_manager=Mock(return_value=manager),
            get_start_config=Mock(return_value=SimpleNamespace(
                port=8080,
                mode="socks5",
                host="127.0.0.1",
                upstream_config=None,
                cloudflare_config=None,
                dc_endpoint_overrides={},
            )),
            set_enabled=Mock(),
            build_upstream_config=Mock(),
            build_cloudflare_config=Mock(),
            build_dc_endpoint_overrides=Mock(return_value={}),
            load_page_initial_state=Mock(),
            save_settings_action=Mock(),
            check_relay_reachable=Mock(),
            check_relay_http=Mock(),
            check_cloudflare_connectivity=Mock(),
            get_cloudflare_dns_records_text=Mock(),
            get_cloudflare_worker_code=Mock(),
            get_fake_tls_nginx_config=Mock(),
            build_diagnostics_start_plan=Mock(),
            build_diagnostics_poll_plan=Mock(),
            build_diagnostics_finish_plan=Mock(),
            copy_text=Mock(),
            open_log_file=Mock(),
            open_external_link=Mock(),
            ensure_telegram_hosts=Mock(),
            run_diagnostics=Mock(),
            append_log_line=Mock(),
            consume_auto_deeplink_request=Mock(),
            _tray_start_runtime=start_runtime or SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock()),
            _tray_stop_runtime=stop_runtime or SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock()),
        )

    def test_runtime_workflow_receives_worker_factories_not_full_feature(self) -> None:
        from telegram_proxy.ui import proxy_runtime_workflow
        from telegram_proxy.ui.page import TelegramProxyPage

        for function_name in (
            "restart_proxy_if_running",
            "start_proxy_runtime",
            "start_relay_check",
            "stop_proxy_runtime",
        ):
            signature = inspect.signature(getattr(proxy_runtime_workflow, function_name))
            self.assertNotIn("telegram_proxy_feature", signature.parameters)

        self.assertIn(
            "create_stop_runtime_worker",
            inspect.signature(proxy_runtime_workflow.restart_proxy_if_running).parameters,
        )
        self.assertIn(
            "on_finished",
            inspect.signature(proxy_runtime_workflow.restart_proxy_if_running).parameters,
        )
        self.assertIn(
            "create_start_worker",
            inspect.signature(proxy_runtime_workflow.start_proxy_runtime).parameters,
        )
        self.assertIn(
            "create_relay_check_worker",
            inspect.signature(proxy_runtime_workflow.start_relay_check).parameters,
        )
        self.assertIn(
            "create_stop_runtime_worker",
            inspect.signature(proxy_runtime_workflow.stop_proxy_runtime).parameters,
        )
        workflow_source = inspect.getsource(proxy_runtime_workflow)
        page_source = inspect.getsource(TelegramProxyPage)

        self.assertIn("start_qthread_worker", workflow_source)
        self.assertNotIn("worker.start()", workflow_source)
        self.assertIn("_proxy_start_runtime", page_source)
        self.assertIn("_proxy_stop_runtime", page_source)
        self.assertIn("_restart_stop_runtime", page_source)
        self.assertIn("_relay_check_runtime", page_source)
        self.assertNotIn("_proxy_start_worker =", page_source)
        self.assertNotIn("_proxy_stop_worker =", page_source)
        self.assertNotIn("_restart_stop_worker =", page_source)
        self.assertNotIn("_relay_check_worker =", page_source)

    def test_finish_proxy_start_refreshes_running_status_after_start_flag_is_cleared(self) -> None:
        from telegram_proxy.ui.proxy_runtime_workflow import finish_proxy_start

        state = {"starting": True}
        btn_toggle = SimpleNamespace(setEnabled=Mock())
        status_changes = []
        saved_enabled_values = []
        check_relay_after_start = Mock()

        finish_proxy_start(
            start_ok=True,
            set_starting=lambda value: state.update(starting=bool(value)),
            btn_toggle=btn_toggle,
            check_relay_after_start=check_relay_after_start,
            on_status_changed=status_changes.append,
            request_proxy_enabled_save=saved_enabled_values.append,
        )

        self.assertFalse(state["starting"])
        self.assertEqual(status_changes, [True])
        self.assertEqual(saved_enabled_values, [True])
        check_relay_after_start.assert_called_once_with()

    def test_relay_check_resyncs_status_button_before_relay_status_text(self) -> None:
        from telegram_proxy.ui.page import TelegramProxyPage

        manager = SimpleNamespace(is_running=True, host="127.0.0.1", port=1353)
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._relay_check_state = SimpleNamespace(pending=True)
        page._proxy_manager = Mock(return_value=manager)
        page._on_status_changed = Mock()
        page._relay_check_gen = 0
        page._status_label = Mock()
        page._get_zapret_running = Mock(return_value=False)
        page._telegram_proxy = SimpleNamespace(create_relay_check_worker=Mock())
        page._on_relay_check_worker_finished = Mock()

        with patch("telegram_proxy.ui.page.start_relay_check") as start_relay_check_mock:
            TelegramProxyPage._start_relay_check_worker(page)

        page._on_status_changed.assert_called_once_with(True)
        start_relay_check_mock.assert_called_once()

    def test_page_receives_zapret_running_callable_not_runtime_feature(self) -> None:
        from app.page_names import PageName
        from telegram_proxy.ui.page import TelegramProxyPage
        from ui.page_deps.system import build_telegram_proxy_page_kwargs

        init_source = inspect.getsource(TelegramProxyPage.__init__)
        relay_source = "\n".join(
            (
                inspect.getsource(TelegramProxyPage._check_relay_after_start),
                inspect.getsource(TelegramProxyPage._start_relay_check_worker),
            )
        )
        page_source = inspect.getsource(TelegramProxyPage)

        self.assertNotIn("runtime_feature", init_source)
        self.assertNotIn("self._runtime_feature", page_source)
        self.assertIn("get_zapret_running", init_source)
        self.assertIn("self._get_zapret_running", relay_source)

        runtime_feature = Mock()
        runtime_feature.is_any_running.return_value = True
        kwargs = build_telegram_proxy_page_kwargs(
            page_name=PageName.TELEGRAM_PROXY,
            runtime_feature=runtime_feature,
            telegram_proxy_feature=Mock(),
        )

        self.assertNotIn("runtime_feature", kwargs)
        self.assertIn("get_zapret_running", kwargs)
        self.assertTrue(kwargs["get_zapret_running"]())
        runtime_feature.is_any_running.assert_called_once_with(silent=True)

    def test_relay_reachability_probe_is_owned_by_commands(self) -> None:
        feature_source = inspect.getsource(TelegramProxyFeature)
        worker_source = inspect.getsource(telegram_proxy_workers.TelegramProxyRelayCheckWorker.run)

        self.assertTrue(hasattr(telegram_proxy_commands, "check_relay_reachable"))
        command_source = inspect.getsource(telegram_proxy_commands.check_relay_reachable)

        self.assertIn("check_relay_reachable=self.check_relay_reachable", feature_source)
        self.assertIn("_check_relay_reachable", worker_source)
        self.assertNotIn("telegram_proxy.runtime.commands", worker_source)
        self.assertNotIn("telegram_proxy.wss_proxy", worker_source)
        self.assertIn("telegram_proxy.wss_proxy", command_source)
        self.assertIn("check_relay_reachable", command_source)

    def test_cloudflare_check_probe_is_owned_by_commands_and_worker(self) -> None:
        feature_source = inspect.getsource(TelegramProxyFeature)
        worker_source = inspect.getsource(telegram_proxy_workers)

        self.assertTrue(hasattr(telegram_proxy_commands, "check_cloudflare_connectivity"))
        self.assertTrue(hasattr(telegram_proxy_workers, "TelegramProxyCloudflareCheckWorker"))
        self.assertIn("check_cloudflare_connectivity=self.check_cloudflare_connectivity", feature_source)
        self.assertIn("create_cloudflare_check_worker", feature_source)
        self.assertIn("_check_cloudflare_connectivity", worker_source)
        self.assertNotIn(
            "telegram_proxy.runtime.commands",
            inspect.getsource(telegram_proxy_workers.TelegramProxyCloudflareCheckWorker.run),
        )

    def test_start_worker_loads_upstream_config_outside_ui_runtime(self) -> None:
        from telegram_proxy.ui import proxy_runtime_workflow

        runtime_source = inspect.getsource(proxy_runtime_workflow.start_proxy_runtime)
        feature_source = inspect.getsource(TelegramProxyFeature)
        toggle_source = inspect.getsource(TelegramProxyFeature.toggle_async)
        worker_source = inspect.getsource(telegram_proxy_workers.TelegramProxyStartWorker.run)

        self.assertTrue(hasattr(telegram_proxy_commands, "build_upstream_config"))
        self.assertNotIn("telegram_proxy.settings", runtime_source)
        self.assertNotIn("build_upstream_config", runtime_source)
        self.assertIn("build_upstream_config=self.build_upstream_config", feature_source)
        self.assertIn("_tray_start_runtime", feature_source)
        self.assertIn("create_start_worker", feature_source)
        self.assertIn("_create_tray_start_worker", toggle_source)
        self.assertIn("start_qthread_worker", toggle_source)
        self.assertNotIn("worker.start()", toggle_source)
        self.assertNotIn("_tray_start_worker =", feature_source)
        self.assertIn("_build_upstream_config", worker_source)
        self.assertNotIn("telegram_proxy.runtime.commands", worker_source)

    def test_page_start_runtime_passes_selected_mode_and_mtproxy_secret(self) -> None:
        from telegram_proxy.ui import proxy_runtime_workflow

        class _Runtime:
            def __init__(self) -> None:
                self.started = None

            def is_running(self) -> bool:
                return False

            def start_qthread_worker(self, **kwargs) -> None:
                self.started = kwargs

        page = SimpleNamespace(_proxy_start_runtime=_Runtime())
        manager = Mock()
        create_start_worker = Mock(return_value=object())
        upstream_config = SimpleNamespace(
            host="upstream.example.com",
            port=1080,
            mode="fallback",
            username="user",
        )
        cloudflare_config = object()
        secret = "aabbccddeeff00112233445566778899"

        proxy_runtime_workflow.start_proxy_runtime(
            page=page,
            manager=manager,
            starting=False,
            running=False,
            host="127.0.0.1",
            port=1443,
            set_starting=Mock(),
            btn_toggle=Mock(),
            status_label=Mock(),
            append_log_line=Mock(),
            create_start_worker=create_start_worker,
            mode="mtproxy",
            upstream_config=upstream_config,
            cloudflare_config=cloudflare_config,
            mtproxy_secret=secret,
            fake_tls_domain="front.example.com",
            proxy_protocol=True,
        )

        self.assertIsNotNone(page._proxy_start_runtime.started)
        worker_factory = page._proxy_start_runtime.started["worker_factory"]
        worker_factory(1)

        create_start_worker.assert_called_once_with(
            manager=manager,
            port=1443,
            mode="mtproxy",
            host="127.0.0.1",
            upstream_config=upstream_config,
            cloudflare_config=cloudflare_config,
            mtproxy_secret=secret,
            pool_size=4,
            buffer_kb=256,
            fake_tls_domain="front.example.com",
            proxy_protocol=True,
            parent=page,
        )

    def test_page_connects_runtime_upstream_selection_signal(self) -> None:
        from telegram_proxy.ui.page import TelegramProxyPage

        source = inspect.getsource(TelegramProxyPage._connect_signals)

        self.assertIn("upstream_selected.connect", source)
        self.assertIn("_on_upstream_selected", source)

    def test_runtime_working_upstream_does_not_overwrite_saved_preset(self) -> None:
        from telegram_proxy.config.upstream_catalog import UpstreamCatalog
        from telegram_proxy.ui.page import TelegramProxyPage

        class _Combo:
            def __init__(self):
                self.index = 0

            def currentIndex(self):
                return self.index

        class _PresetRow:
            def __init__(self):
                self.combo = _Combo()
                self.indexes = []

            def setCurrentIndex(self, index: int, *, block_signals: bool = False):
                self.combo.index = int(index)
                self.indexes.append((int(index), bool(block_signals)))

        catalog = UpstreamCatalog(
            build_presets=[
                {
                    "id": "uk",
                    "name": "Великобритания",
                    "type": "socks5",
                    "host": "203.0.113.10",
                    "port": 443,
                    "tls": True,
                },
                {
                    "id": "no",
                    "name": "Норвегия",
                    "type": "socks5",
                    "host": "203.0.113.20",
                    "port": 443,
                    "tls": True,
                },
            ],
        )
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        page._advanced_settings_built = True
        page._upstream_catalog = catalog
        page._upstream_preset_row = _PresetRow()
        page._apply_upstream_preset_ui = Mock()
        page._request_settings_save = Mock()
        page._append_log_line = Mock()

        TelegramProxyPage._on_upstream_selected(page, "no", "Норвегия")

        self.assertEqual(page._upstream_preset_row.indexes, [])
        page._apply_upstream_preset_ui.assert_not_called()
        page._request_settings_save.assert_not_called()
        page._append_log_line.assert_called_once_with("Telegram Proxy: сейчас используется внешний прокси: Норвегия")

    def test_tray_toggle_stops_proxy_through_worker_runtime(self) -> None:
        feature_source = inspect.getsource(TelegramProxyFeature)
        toggle_source = inspect.getsource(TelegramProxyFeature.toggle_async)

        self.assertIn("_tray_stop_runtime", feature_source)
        self.assertIn("create_stop_runtime_worker", feature_source)
        self.assertIn("_create_tray_stop_worker", toggle_source)
        self.assertIn("_tray_stop_runtime.start_qthread_worker", toggle_source)
        self.assertNotIn("manager.stop_proxy()", toggle_source)
        self.assertNotIn("self.set_enabled(False)", toggle_source)

    def test_feature_cleanup_does_not_wait_for_tray_toggle_workers(self) -> None:
        start_runtime = SimpleNamespace(stop=Mock())
        stop_runtime = SimpleNamespace(stop=Mock())
        manager = SimpleNamespace(cleanup=Mock(), is_running=False)
        feature = self._make_feature(
            manager=manager,
            start_runtime=start_runtime,
            stop_runtime=stop_runtime,
        )
        feature._tray_toggle_state.pending_count = 2
        feature._tray_toggle_state.start_scheduled = True

        feature.cleanup()

        start_runtime.stop.assert_called_once_with(
            blocking=False,
            warning_prefix="Telegram Proxy tray start worker",
        )
        stop_runtime.stop.assert_called_once_with(
            blocking=False,
            warning_prefix="Telegram Proxy tray stop worker",
        )
        self.assertEqual(feature._tray_toggle_state.pending_count, 0)
        self.assertFalse(feature._tray_toggle_state.start_scheduled)
        manager.cleanup.assert_called_once_with()

    def test_tray_toggle_running_proxy_starts_stop_runtime(self) -> None:
        class _Runtime:
            def __init__(self) -> None:
                self.started = None

            def is_running(self) -> bool:
                return False

            def start_qthread_worker(self, **kwargs) -> None:
                self.started = kwargs

        manager = Mock()
        manager.is_running = True
        stop_runtime = _Runtime()
        enabled_values = []
        feature = TelegramProxyFeature(
            start_proxy_if_enabled_async=Mock(),
            get_proxy_manager=Mock(return_value=manager),
            get_start_config=Mock(),
            set_enabled=lambda value: enabled_values.append(bool(value)),
            build_upstream_config=Mock(),
            build_cloudflare_config=Mock(),
            build_dc_endpoint_overrides=Mock(return_value={}),
            load_page_initial_state=Mock(),
            save_settings_action=Mock(),
            check_relay_reachable=Mock(),
            check_relay_http=Mock(),
            check_cloudflare_connectivity=Mock(),
            get_cloudflare_dns_records_text=Mock(),
            get_cloudflare_worker_code=Mock(),
            get_fake_tls_nginx_config=Mock(),
            build_diagnostics_start_plan=Mock(),
            build_diagnostics_poll_plan=Mock(),
            build_diagnostics_finish_plan=Mock(),
            copy_text=Mock(),
            open_log_file=Mock(),
            open_external_link=Mock(),
            ensure_telegram_hosts=Mock(),
            run_diagnostics=Mock(),
            append_log_line=Mock(),
            consume_auto_deeplink_request=Mock(),
            _tray_stop_runtime=stop_runtime,
        )

        feature.toggle_async()

        manager.stop_proxy.assert_not_called()
        self.assertEqual(enabled_values, [])
        self.assertIsNotNone(stop_runtime.started)
        self.assertEqual(stop_runtime.started.get("loaded_signal_name"), "stopped")
        worker = stop_runtime.started["worker_factory"](1)

        worker.run()

        manager.stop_proxy.assert_called_once_with()
        self.assertEqual(enabled_values, [False])

    def test_tray_toggle_queues_while_start_worker_runs(self) -> None:
        start_runtime = SimpleNamespace(is_running=Mock(return_value=True), start_qthread_worker=Mock())
        stop_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())
        manager = Mock()
        manager.is_running = False
        feature = self._make_feature(
            manager=manager,
            start_runtime=start_runtime,
            stop_runtime=stop_runtime,
        )

        feature.toggle_async()

        start_runtime.start_qthread_worker.assert_not_called()
        stop_runtime.start_qthread_worker.assert_not_called()
        self.assertEqual(feature._tray_toggle_state.pending_count, 1)

    def test_tray_toggle_pending_restarts_after_event_loop_turn(self) -> None:
        start_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock(), request_id=1)
        stop_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())
        manager = Mock()
        manager.is_running = False
        feature = self._make_feature(
            manager=manager,
            start_runtime=start_runtime,
            stop_runtime=stop_runtime,
        )
        feature._tray_toggle_state.pending_count = 1
        worker = SimpleNamespace(_request_id=1, _tray_toggle_runtime="start")
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_feature_module, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            feature._on_tray_toggle_worker_finished(worker)

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        start_runtime.start_qthread_worker.assert_not_called()

        single_shot.call_args.args[1]()

        start_runtime.start_qthread_worker.assert_called_once()
        self.assertEqual(feature._tray_toggle_state.pending_count, 0)

    def test_stale_tray_toggle_worker_finish_does_not_schedule_pending_toggle(self) -> None:
        start_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock(), request_id=2)
        stop_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock(), request_id=1)
        manager = Mock()
        manager.is_running = False
        feature = self._make_feature(
            manager=manager,
            start_runtime=start_runtime,
            stop_runtime=stop_runtime,
        )
        feature._tray_toggle_state.pending_count = 1
        stale_worker = SimpleNamespace(_request_id=1, _tray_toggle_runtime="start")
        single_shot = Mock()

        with patch.object(telegram_proxy_feature_module, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            feature._on_tray_toggle_worker_finished(stale_worker)

        single_shot.assert_not_called()
        start_runtime.start_qthread_worker.assert_not_called()
        stop_runtime.start_qthread_worker.assert_not_called()
        self.assertEqual(feature._tray_toggle_state.pending_count, 1)

    def test_copy_logs_uses_cached_text_without_reading_log_widget(self) -> None:
        from telegram_proxy.ui import page as telegram_proxy_page_module
        from telegram_proxy.ui.page import TelegramProxyPage

        class LogEdit:
            def toPlainText(self):
                raise AssertionError("GUI log text should not be read during copy")

        copy_text = Mock(return_value=SimpleNamespace(ok=False, log_line=""))
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._log_edit = LogEdit()
        page._log_text_cache = "one\ntwo\n"
        page._log_text_line_count = 2
        page._telegram_proxy = SimpleNamespace(copy_text=copy_text)

        with patch.object(telegram_proxy_page_module, "InfoBar", None):
            TelegramProxyPage._on_copy_all_logs(page)

        copy_text.assert_called_once_with(
            "one\ntwo\n",
            success_title="Скопировано",
            success_content="2 строк",
        )

    def test_copy_diag_uses_cached_text_without_reading_diag_widget(self) -> None:
        from telegram_proxy.ui import page as telegram_proxy_page_module
        from telegram_proxy.ui.page import TelegramProxyPage

        class DiagEdit:
            def toPlainText(self):
                raise AssertionError("GUI diagnostics text should not be read during copy")

        copy_text = Mock(return_value=SimpleNamespace(ok=False, log_line=""))
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._diag_edit = DiagEdit()
        page._diag_text_cache = "diag result"
        page._telegram_proxy = SimpleNamespace(copy_text=copy_text)

        with patch.object(telegram_proxy_page_module, "InfoBar", None):
            TelegramProxyPage._on_copy_diag(page)

        copy_text.assert_called_once_with(
            "diag result",
            success_title="Скопировано",
            success_content="Результат диагностики",
        )

    def test_copy_fake_tls_nginx_config_uses_feature_helper(self) -> None:
        from telegram_proxy.ui import page as telegram_proxy_page_module
        from telegram_proxy.ui.page import TelegramProxyPage

        copy_text = Mock(return_value=SimpleNamespace(ok=False, log_line="Copied Nginx config"))
        get_config = Mock(return_value="nginx config")
        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._telegram_proxy = SimpleNamespace(
            copy_text=copy_text,
            get_fake_tls_nginx_config=get_config,
        )
        page._append_log_line = Mock()
        page._show_cloudflare_message = Mock()
        page._local_fake_tls_domain = Mock(return_value="front.example.com")
        page._host_edit = SimpleNamespace(text=Mock(return_value="127.0.0.1"))
        page._port_spin = SimpleNamespace(value=Mock(return_value=8446))

        with patch.object(telegram_proxy_page_module, "InfoBar", None):
            TelegramProxyPage._on_copy_fake_tls_nginx_config(page)

        get_config.assert_called_once_with(
            fake_tls_domain="front.example.com",
            upstream_host="127.0.0.1",
            upstream_port=8446,
        )
        copy_text.assert_called_once_with(
            "nginx config",
            success_title="Скопировано",
            success_content="Конфиг Nginx для Fake TLS",
            success_log="Copied Fake TLS Nginx config",
        )
        page._append_log_line.assert_called_once_with("Copied Nginx config")

    def test_start_worker_passes_command_loaded_upstream_config_to_manager(self) -> None:
        manager = Mock()
        manager.start_proxy.return_value = True
        upstream_config = object()
        cloudflare_config = object()
        worker = telegram_proxy_workers.TelegramProxyStartWorker(
            manager=manager,
            port=1353,
            mode="socks5",
            host="127.0.0.1",
            build_upstream_config=Mock(return_value=upstream_config),
            build_cloudflare_config=Mock(return_value=cloudflare_config),
        )

        worker.run()

        manager.start_proxy.assert_called_once_with(
            port=1353,
            mode="socks5",
            host="127.0.0.1",
            upstream_config=upstream_config,
            cloudflare_config=cloudflare_config,
            mtproxy_secret="",
            dc_endpoint_overrides={},
            pool_size=4,
            buffer_kb=256,
            fake_tls_domain="",
            proxy_protocol=False,
        )

    def test_external_links_are_queued_while_worker_runs(self) -> None:
        from telegram_proxy.ui.page import TelegramProxyPage

        class _Runtime:
            def is_running(self) -> bool:
                return True

        page = TelegramProxyPage.__new__(TelegramProxyPage)
        state = _set_queue_state(page, "external_link", runtime=_Runtime())
        page.create_external_link_worker = Mock()

        TelegramProxyPage._start_external_link_worker(
            page,
            "tg://proxy-one",
            success_log="one",
            error_prefix="bad one",
        )
        TelegramProxyPage._start_external_link_worker(
            page,
            "tg://proxy-two",
            success_log="two",
            error_prefix="bad two",
        )

        self.assertEqual(
            state.pending,
            [
                {"url": "tg://proxy-one", "success_log": "one", "error_prefix": "bad one"},
                {"url": "tg://proxy-two", "success_log": "two", "error_prefix": "bad two"},
            ],
        )
        page.create_external_link_worker.assert_not_called()

    def test_duplicate_external_link_request_is_queued_once(self) -> None:
        from telegram_proxy.ui.page import TelegramProxyPage

        class _Runtime:
            def is_running(self) -> bool:
                return True

        page = TelegramProxyPage.__new__(TelegramProxyPage)
        state = _set_queue_state(page, "external_link", runtime=_Runtime())
        page.create_external_link_worker = Mock()

        TelegramProxyPage._start_external_link_worker(
            page,
            "tg://proxy-one",
            success_log="one",
            error_prefix="bad one",
        )
        TelegramProxyPage._start_external_link_worker(
            page,
            "tg://proxy-one",
            success_log="one",
            error_prefix="bad one",
        )

        self.assertEqual(
            state.pending,
            [{"url": "tg://proxy-one", "success_log": "one", "error_prefix": "bad one"}],
        )
        page.create_external_link_worker.assert_not_called()

    def test_external_link_worker_finished_schedules_next_queued_link(self) -> None:
        import telegram_proxy.ui.page as telegram_proxy_page
        from telegram_proxy.ui.page import TelegramProxyPage

        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        state = _set_queue_state(
            page,
            "external_link",
            runtime=SimpleNamespace(request_id=1),
            pending=[
                {"url": "tg://proxy-one", "success_log": "one", "error_prefix": "bad one"},
                {"url": "tg://proxy-two", "success_log": "two", "error_prefix": "bad two"},
            ],
        )
        page._start_external_link_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._on_external_link_worker_finished(page, SimpleNamespace(_request_id=1))

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_external_link_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_external_link_worker.assert_called_once_with(
            "tg://proxy-one",
            success_log="one",
            error_prefix="bad one",
        )
        self.assertEqual(
            state.pending,
            [{"url": "tg://proxy-two", "success_log": "two", "error_prefix": "bad two"}],
        )

    def test_open_log_file_requests_are_queued_while_worker_runs(self) -> None:
        from telegram_proxy.ui.page import TelegramProxyPage

        class _Runtime:
            def is_running(self) -> bool:
                return True

        page = TelegramProxyPage.__new__(TelegramProxyPage)
        state = _set_queue_state(page, "open_log_file", runtime=_Runtime())
        page.create_open_log_file_worker = Mock()

        TelegramProxyPage._start_open_log_file_worker(page, "first.log")
        TelegramProxyPage._start_open_log_file_worker(page, "second.log")

        self.assertEqual(state.pending, ["first.log", "second.log"])
        page.create_open_log_file_worker.assert_not_called()

    def test_duplicate_open_log_file_request_is_queued_once(self) -> None:
        from telegram_proxy.ui.page import TelegramProxyPage

        class _Runtime:
            def is_running(self) -> bool:
                return True

        page = TelegramProxyPage.__new__(TelegramProxyPage)
        state = _set_queue_state(page, "open_log_file", runtime=_Runtime())
        page.create_open_log_file_worker = Mock()

        TelegramProxyPage._start_open_log_file_worker(page, "proxy.log")
        TelegramProxyPage._start_open_log_file_worker(page, "proxy.log")

        self.assertEqual(state.pending, ["proxy.log"])
        page.create_open_log_file_worker.assert_not_called()

    def test_open_log_file_worker_finished_schedules_next_queued_path(self) -> None:
        import telegram_proxy.ui.page as telegram_proxy_page
        from telegram_proxy.ui.page import TelegramProxyPage

        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        state = _set_queue_state(
            page,
            "open_log_file",
            runtime=SimpleNamespace(request_id=1),
            pending=["first.log", "second.log"],
        )
        page._start_open_log_file_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._on_open_log_file_worker_finished(page, SimpleNamespace(_request_id=1))

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_open_log_file_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_open_log_file_worker.assert_called_once_with("first.log")
        self.assertEqual(state.pending, ["second.log"])

    def test_log_line_worker_finished_schedules_next_queued_line(self) -> None:
        import telegram_proxy.ui.page as telegram_proxy_page
        from telegram_proxy.ui.page import TelegramProxyPage

        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        state = _set_queue_state(
            page,
            "log_line",
            runtime=SimpleNamespace(request_id=1),
            pending=["first", "second"],
        )
        page._start_log_line_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._on_log_line_worker_finished(page, SimpleNamespace(_request_id=1))

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_log_line_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_log_line_worker.assert_called_once_with("first")
        self.assertEqual(state.pending, ["second"])

    def test_log_line_error_ignored_when_new_line_is_pending(self) -> None:
        import telegram_proxy.ui.page as telegram_proxy_page
        from telegram_proxy.ui.page import TelegramProxyPage

        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        page._log_line_runtime = Mock()
        page._log_line_runtime.is_current.return_value = True
        _set_queue_state(page, "log_line", runtime=page._log_line_runtime, pending=["new line"])

        with patch.object(telegram_proxy_page, "log") as log_mock:
            TelegramProxyPage._on_log_line_worker_failed(page, 6, "old log append failed")

        log_mock.assert_not_called()

    def test_page_uses_queue_state_to_schedule_next_queued_worker(self) -> None:
        import inspect
        from telegram_proxy.ui.page import TelegramProxyPage
        from telegram_proxy.ui.worker_state import TelegramProxyPageQueuedWorkerState

        page_source = inspect.getsource(TelegramProxyPage)
        queued_state_source = inspect.getsource(TelegramProxyPageQueuedWorkerState)

        self.assertNotIn(".pop_next_after_finish(", page_source)
        self.assertIn("def schedule_next_after_finish", queued_state_source)

    def test_auto_deeplink_result_ignored_when_new_check_is_pending(self) -> None:
        import telegram_proxy.ui.page as telegram_proxy_page
        from telegram_proxy.ui.page import TelegramProxyPage

        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        page._auto_deeplink_runtime = Mock()
        page._auto_deeplink_runtime.is_current.return_value = True
        _set_state(page, "auto_deeplink", runtime=page._auto_deeplink_runtime, pending=True)
        page._on_open_in_telegram = Mock()
        page._append_log_line = Mock()
        single_shot = Mock()

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._on_auto_deeplink_checked(page, 6, True)

        single_shot.assert_not_called()
        page._append_log_line.assert_not_called()

    def test_auto_deeplink_error_ignored_when_new_check_is_pending(self) -> None:
        import telegram_proxy.ui.page as telegram_proxy_page
        from telegram_proxy.ui.page import TelegramProxyPage

        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        page._auto_deeplink_runtime = Mock()
        page._auto_deeplink_runtime.is_current.return_value = True
        _set_state(page, "auto_deeplink", runtime=page._auto_deeplink_runtime, pending=True)

        with patch.object(telegram_proxy_page, "log") as log_mock:
            TelegramProxyPage._on_auto_deeplink_failed(page, 6, "old deeplink failed")

        log_mock.assert_not_called()

    def test_settings_save_worker_finished_schedules_next_queued_save(self) -> None:
        import telegram_proxy.ui.page as telegram_proxy_page
        from telegram_proxy.ui.page import TelegramProxyPage

        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        _set_queue_state(
            page,
            "settings_save",
            runtime=SimpleNamespace(request_id=1),
            pending=[{"action": "port", "port": 8080}],
        )
        page._start_settings_save_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._on_settings_save_worker_finished(page, SimpleNamespace(_request_id=1))

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_settings_save_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_settings_save_worker.assert_called_once_with({"action": "port", "port": 8080})

    def test_relay_check_pending_restarts_after_event_loop_turn(self) -> None:
        import telegram_proxy.ui.page as telegram_proxy_page
        from telegram_proxy.ui.page import TelegramProxyPage

        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        _set_state(page, "relay_check", runtime=SimpleNamespace(request_id=1), pending=True)
        page._start_relay_check_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._on_relay_check_worker_finished(page, SimpleNamespace(_request_id=1))

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_relay_check_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_relay_check_worker.assert_called_once_with()
        self.assertFalse(page._relay_check_state.pending)

    def test_ensure_hosts_pending_restarts_after_event_loop_turn(self) -> None:
        import telegram_proxy.ui.page as telegram_proxy_page
        from telegram_proxy.ui.page import TelegramProxyPage

        page = TelegramProxyPage.__new__(TelegramProxyPage)
        page._cleanup_in_progress = False
        _set_state(page, "ensure_hosts", runtime=SimpleNamespace(request_id=1), pending=True)
        page._start_ensure_hosts_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(telegram_proxy_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            TelegramProxyPage._on_ensure_hosts_worker_finished(page, SimpleNamespace(_request_id=1))

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_ensure_hosts_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_ensure_hosts_worker.assert_called_once_with()
        self.assertFalse(page._ensure_hosts_state.pending)


if __name__ == "__main__":
    unittest.main()
