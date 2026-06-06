from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from PyQt6.QtCore import QTimer

from ui.one_shot_worker_runtime import OneShotWorkerRuntime


@dataclass(slots=True)
class TelegramProxyTrayToggleState:
    pending_count: int = 0
    start_scheduled: bool = False


@dataclass(frozen=True, slots=True)
class TelegramProxyFeature:
    start_proxy_if_enabled_async: Callable
    get_proxy_manager: Callable
    get_start_config: Callable
    set_enabled: Callable
    build_upstream_config: Callable
    load_page_initial_state: Callable
    save_settings_action: Callable
    check_relay_reachable: Callable
    check_relay_http: Callable
    build_diagnostics_start_plan: Callable
    build_diagnostics_poll_plan: Callable
    build_diagnostics_finish_plan: Callable
    copy_text: Callable
    open_log_file: Callable
    open_external_link: Callable
    ensure_telegram_hosts: Callable
    run_diagnostics: Callable
    append_log_line: Callable
    consume_auto_deeplink_request: Callable
    _tray_start_runtime: OneShotWorkerRuntime = field(default_factory=OneShotWorkerRuntime)
    _tray_stop_runtime: OneShotWorkerRuntime = field(default_factory=OneShotWorkerRuntime)
    _tray_toggle_state: TelegramProxyTrayToggleState = field(default_factory=TelegramProxyTrayToggleState)

    def is_running(self) -> bool:
        try:
            return bool(self.get_proxy_manager().is_running)
        except Exception:
            return False

    def status_label(self) -> str:
        try:
            manager = self.get_proxy_manager()
            if manager.is_running:
                return f"Telegram Proxy: вкл ({manager.port})"
        except Exception:
            pass
        return "Telegram Proxy: выкл"

    def connect_status_changed(self, callback) -> None:
        try:
            self.get_proxy_manager().status_changed.connect(callback)
        except Exception:
            pass

    def cleanup(self) -> None:
        self._tray_toggle_state.pending_count = 0
        self._tray_toggle_state.start_scheduled = False
        self._tray_start_runtime.stop(blocking=False, warning_prefix="Telegram Proxy tray start worker")
        self._tray_stop_runtime.stop(blocking=False, warning_prefix="Telegram Proxy tray stop worker")
        try:
            self.get_proxy_manager().cleanup()
        except Exception:
            pass

    def create_start_worker(self, *, manager, port: int, mode: str, host: str, upstream_config=None, parent=None):
        from telegram_proxy.workers import TelegramProxyStartWorker

        return TelegramProxyStartWorker(
            manager=manager,
            port=port,
            mode=mode,
            host=host,
            upstream_config=upstream_config,
            build_upstream_config=self.build_upstream_config,
            parent=parent,
        )

    def create_stop_runtime_worker(
        self,
        *,
        manager,
        emit_status: bool = False,
        set_enabled=None,
        enabled_after_stop=None,
        parent=None,
    ):
        from telegram_proxy.workers import TelegramProxyStopRuntimeWorker

        return TelegramProxyStopRuntimeWorker(
            manager=manager,
            emit_status=bool(emit_status),
            set_enabled=set_enabled,
            enabled_after_stop=enabled_after_stop,
            parent=parent,
        )

    def create_open_log_file_worker(self, *, path: str, parent=None):
        from telegram_proxy.workers import TelegramProxyOpenLogFileWorker

        return TelegramProxyOpenLogFileWorker(
            open_log_file_fn=self.open_log_file,
            path=str(path or ""),
            parent=parent,
        )

    def create_external_link_worker(self, *, url: str, success_log: str, error_prefix: str, parent=None):
        from telegram_proxy.workers import TelegramProxyExternalLinkWorker

        return TelegramProxyExternalLinkWorker(
            open_external_link_fn=self.open_external_link,
            url=str(url or ""),
            success_log=str(success_log or ""),
            error_prefix=str(error_prefix or ""),
            parent=parent,
        )

    def create_log_line_worker(self, request_id: int, *, message: str, parent=None):
        from telegram_proxy.workers import TelegramProxyLogLineWorker

        return TelegramProxyLogLineWorker(
            request_id,
            append_log_line_fn=self.append_log_line,
            message=str(message or ""),
            parent=parent,
        )

    def create_auto_deeplink_worker(self, request_id: int, *, parent=None):
        from telegram_proxy.workers import TelegramProxyAutoDeeplinkWorker

        return TelegramProxyAutoDeeplinkWorker(
            request_id,
            consume_auto_deeplink_request_fn=self.consume_auto_deeplink_request,
            parent=parent,
        )

    def create_relay_check_worker(self, *, generation: int, get_zapret_running, parent=None):
        from telegram_proxy.workers import TelegramProxyRelayCheckWorker

        return TelegramProxyRelayCheckWorker(
            generation=generation,
            check_relay_reachable=self.check_relay_reachable,
            check_relay_http=self.check_relay_http,
            get_zapret_running=get_zapret_running,
            parent=parent,
        )

    def create_diagnostics_worker(self, *, proxy_port: int, parent=None):
        from telegram_proxy.workers import TelegramProxyDiagnosticsWorker

        return TelegramProxyDiagnosticsWorker(
            run_diagnostics_fn=self.run_diagnostics,
            proxy_port=proxy_port,
            parent=parent,
        )

    def create_ensure_hosts_worker(self, request_id: int, *, parent=None):
        from telegram_proxy.workers import TelegramHostsEnsureWorker

        return TelegramHostsEnsureWorker(
            request_id,
            ensure_hosts_fn=self.ensure_telegram_hosts,
            parent=parent,
        )

    def create_settings_save_worker(self, request_id: int, **kwargs):
        from telegram_proxy.workers import TelegramProxySettingsSaveWorker

        return TelegramProxySettingsSaveWorker(
            request_id,
            save_settings_action=self.save_settings_action,
            **kwargs,
        )

    def create_page_initial_state_worker(self, request_id: int, *, parent=None):
        from telegram_proxy.workers import TelegramProxyInitialStateWorker

        return TelegramProxyInitialStateWorker(
            request_id,
            load_page_initial_state=self.load_page_initial_state,
            parent=parent,
        )

    def toggle_async(self) -> None:
        try:
            if self._tray_toggle_is_busy():
                self._queue_tray_toggle()
                return
            manager = self.get_proxy_manager()
            if manager.is_running:
                self._tray_stop_runtime.start_qthread_worker(
                    worker_factory=lambda request_id: self._create_tray_stop_worker(
                        request_id,
                        manager=manager,
                    ),
                    on_finished=self._on_tray_toggle_worker_finished,
                    signal_includes_request_id=False,
                    loaded_signal_name="stopped",
                )
                return

            config = self.get_start_config()
            self._tray_start_runtime.start_qthread_worker(
                worker_factory=lambda request_id: self._create_tray_start_worker(
                    request_id,
                    manager=manager,
                    port=config.port,
                    mode=config.mode,
                    host=config.host,
                    upstream_config=config.upstream_config,
                ),
                on_finished=self._on_tray_toggle_worker_finished,
                signal_includes_request_id=False,
                loaded_signal_name="completed",
            )
        except Exception as exc:
            from log.log import log

            log(f"Telegram Proxy toggle error: {exc}", "WARNING")

    def _tray_toggle_is_busy(self) -> bool:
        return (
            self._tray_start_runtime.is_running()
            or self._tray_stop_runtime.is_running()
            or bool(self._tray_toggle_state.start_scheduled)
        )

    def _queue_tray_toggle(self) -> None:
        self._tray_toggle_state.pending_count += 1

    def _on_tray_toggle_worker_finished(self, _worker) -> None:
        if not self._is_current_tray_toggle_worker_finish(_worker):
            return
        if self._tray_toggle_state.pending_count > 0:
            self._schedule_tray_toggle_start()

    def _create_tray_start_worker(self, request_id: int, **kwargs):
        worker = self.create_start_worker(**kwargs)
        self._mark_tray_toggle_worker(worker, request_id, "start")
        return worker

    def _create_tray_stop_worker(self, request_id: int, *, manager):
        worker = self.create_stop_runtime_worker(
            manager=manager,
            emit_status=True,
            set_enabled=self.set_enabled,
            enabled_after_stop=False,
        )
        self._mark_tray_toggle_worker(worker, request_id, "stop")
        return worker

    def _mark_tray_toggle_worker(self, worker, request_id: int, runtime_name: str) -> None:
        try:
            worker._request_id = int(request_id)
            worker._tray_toggle_runtime = str(runtime_name)
        except Exception:
            pass

    def _is_current_tray_toggle_worker_finish(self, worker) -> bool:
        runtime_name = getattr(worker, "_tray_toggle_runtime", None)
        runtime = None
        if runtime_name == "start":
            runtime = self._tray_start_runtime
        elif runtime_name == "stop":
            runtime = self._tray_stop_runtime
        else:
            for candidate in (self._tray_start_runtime, self._tray_stop_runtime):
                current_worker = getattr(candidate, "worker", None)
                if current_worker is not None and worker is current_worker:
                    return True
            return False

        request_id = getattr(worker, "_request_id", None)
        if request_id is None:
            current_worker = getattr(runtime, "worker", None)
            return current_worker is not None and worker is current_worker
        try:
            return int(request_id) == int(getattr(runtime, "request_id", -1))
        except (TypeError, ValueError):
            return False

    def _schedule_tray_toggle_start(self) -> None:
        if self._tray_toggle_state.start_scheduled:
            return
        self._tray_toggle_state.start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_tray_toggle)

    def _run_scheduled_tray_toggle(self) -> None:
        self._tray_toggle_state.start_scheduled = False
        if self._tray_toggle_state.pending_count <= 0:
            return
        self._tray_toggle_state.pending_count -= 1
        self.toggle_async()


def build_telegram_proxy_feature() -> TelegramProxyFeature:
    def _commands():
        from telegram_proxy import commands as telegram_proxy_commands

        return telegram_proxy_commands

    def _public():
        from telegram_proxy import public as telegram_proxy_public

        return telegram_proxy_public

    return TelegramProxyFeature(
        start_proxy_if_enabled_async=lambda *args, **kwargs: _public().start_proxy_if_enabled_async(*args, **kwargs),
        get_proxy_manager=lambda *args, **kwargs: _commands().get_proxy_manager(*args, **kwargs),
        get_start_config=lambda *args, **kwargs: _commands().get_start_config(*args, **kwargs),
        set_enabled=lambda *args, **kwargs: _public().set_enabled(*args, **kwargs),
        build_upstream_config=lambda *args, **kwargs: _commands().build_upstream_config(*args, **kwargs),
        load_page_initial_state=lambda *args, **kwargs: _commands().load_page_initial_state(*args, **kwargs),
        save_settings_action=lambda *args, **kwargs: _commands().save_settings_action(*args, **kwargs),
        check_relay_reachable=lambda *args, **kwargs: _commands().check_relay_reachable(*args, **kwargs),
        check_relay_http=lambda *args, **kwargs: _commands().check_relay_http(*args, **kwargs),
        build_diagnostics_start_plan=lambda *args, **kwargs: _public().build_diagnostics_start_plan(*args, **kwargs),
        build_diagnostics_poll_plan=lambda *args, **kwargs: _public().build_diagnostics_poll_plan(*args, **kwargs),
        build_diagnostics_finish_plan=lambda *args, **kwargs: _public().build_diagnostics_finish_plan(*args, **kwargs),
        copy_text=lambda *args, **kwargs: _public().copy_text(*args, **kwargs),
        open_log_file=lambda *args, **kwargs: _public().open_log_file(*args, **kwargs),
        open_external_link=lambda *args, **kwargs: _public().open_external_link(*args, **kwargs),
        ensure_telegram_hosts=lambda *args, **kwargs: _public().ensure_telegram_hosts(*args, **kwargs),
        run_diagnostics=lambda *args, **kwargs: _public().run_diagnostics(*args, **kwargs),
        append_log_line=lambda *args, **kwargs: _public().append_log_line(*args, **kwargs),
        consume_auto_deeplink_request=lambda *args, **kwargs: _public().consume_auto_deeplink_request(*args, **kwargs),
    )
