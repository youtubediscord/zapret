from __future__ import annotations

import time

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class TelegramProxyInitialStateWorker(QThread):
    completed = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, *, load_page_initial_state, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._load_page_initial_state = load_page_initial_state

    def run(self) -> None:
        try:
            result = self._load_page_initial_state()
        except Exception as exc:
            log(f"TelegramProxyInitialStateWorker: не удалось загрузить начальное состояние: {exc}", "WARNING")
            self.failed.emit(self._request_id, str(exc))
            return
        self.completed.emit(self._request_id, result)


class TelegramProxyStartWorker(QThread):
    completed = pyqtSignal(bool)

    def __init__(
        self,
        *,
        manager,
        port: int,
        mode: str,
        host: str,
        build_upstream_config,
        upstream_config=None,
        parent=None,
    ):
        super().__init__(parent)
        self._manager = manager
        self._port = int(port)
        self._mode = str(mode or "socks5")
        self._host = str(host or "127.0.0.1")
        self._build_upstream_config = build_upstream_config
        self._upstream_config = upstream_config

    def run(self) -> None:
        try:
            upstream_config = self._upstream_config
            if upstream_config is None:
                upstream_config = self._build_upstream_config()
            ok = self._manager.start_proxy(
                port=self._port,
                mode=self._mode,
                host=self._host,
                upstream_config=upstream_config,
            )
        except Exception as exc:
            log(f"TelegramProxyStartWorker: ошибка запуска proxy: {exc}", "WARNING")
            ok = False
        self.completed.emit(bool(ok))


class TelegramProxyStopRuntimeWorker(QThread):
    stopped = pyqtSignal()

    def __init__(
        self,
        *,
        manager,
        emit_status: bool = False,
        set_enabled=None,
        enabled_after_stop=None,
        parent=None,
    ):
        super().__init__(parent)
        self._manager = manager
        self._emit_status = bool(emit_status)
        self._set_enabled = set_enabled
        self._enabled_after_stop = enabled_after_stop

    def run(self) -> None:
        try:
            if self._emit_status:
                self._manager.stop_proxy()
            else:
                self._manager._stop_runtime_only()
            if self._set_enabled is not None and self._enabled_after_stop is not None:
                self._set_enabled(bool(self._enabled_after_stop))
        except Exception as exc:
            log(f"TelegramProxyStopRuntimeWorker: ошибка остановки proxy: {exc}", "WARNING")
        self.stopped.emit()


class TelegramProxyOpenLogFileWorker(QThread):
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, *, open_log_file_fn, path: str, parent=None):
        super().__init__(parent)
        self._open_log_file_fn = open_log_file_fn
        self._path = str(path or "")

    def run(self) -> None:
        try:
            result = self._open_log_file_fn(self._path)
        except Exception as exc:
            log(f"TelegramProxyOpenLogFileWorker: не удалось открыть файл лога: {exc}", "WARNING")
            self.failed.emit(str(exc))
            return
        self.completed.emit(result)


class TelegramProxyExternalLinkWorker(QThread):
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(
        self,
        *,
        open_external_link_fn,
        url: str,
        success_log: str,
        error_prefix: str,
        parent=None,
    ):
        super().__init__(parent)
        self._open_external_link_fn = open_external_link_fn
        self._url = str(url or "")
        self._success_log = str(success_log or "")
        self._error_prefix = str(error_prefix or "")

    def run(self) -> None:
        try:
            result = self._open_external_link_fn(
                self._url,
                success_log=self._success_log,
                error_prefix=self._error_prefix,
            )
        except Exception as exc:
            log(f"TelegramProxyExternalLinkWorker: не удалось открыть ссылку: {exc}", "WARNING")
            self.failed.emit(str(exc))
            return
        self.completed.emit(result)


class TelegramProxyLogLineWorker(QThread):
    completed = pyqtSignal(int)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        *,
        append_log_line_fn,
        message: str,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._append_log_line_fn = append_log_line_fn
        self._message = str(message or "")

    def run(self) -> None:
        try:
            self._append_log_line_fn(self._message)
        except Exception as exc:
            log(f"TelegramProxyLogLineWorker: не удалось записать строку лога: {exc}", "WARNING")
            self.failed.emit(self._request_id, str(exc))
            return
        self.completed.emit(self._request_id)


class TelegramProxyAutoDeeplinkWorker(QThread):
    completed = pyqtSignal(int, bool)
    failed = pyqtSignal(int, str)

    def __init__(
        self,
        request_id: int,
        *,
        consume_auto_deeplink_request_fn,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._consume_auto_deeplink_request_fn = consume_auto_deeplink_request_fn

    def run(self) -> None:
        try:
            should_open = bool(self._consume_auto_deeplink_request_fn())
        except Exception as exc:
            log(f"TelegramProxyAutoDeeplinkWorker: не удалось проверить автоссылку: {exc}", "WARNING")
            self.failed.emit(self._request_id, str(exc))
            return
        self.completed.emit(self._request_id, should_open)


class TelegramProxyRelayCheckWorker(QThread):
    completed = pyqtSignal(int, dict)
    warning = pyqtSignal(str)

    def __init__(self, *, generation: int, check_relay_reachable, check_relay_http, get_zapret_running, parent=None):
        super().__init__(parent)
        self._generation = int(generation)
        self._check_relay_reachable = check_relay_reachable
        self._check_relay_http = check_relay_http
        self._get_zapret_running = get_zapret_running

    def run(self) -> None:
        try:
            time.sleep(2)
            best_result = None
            for attempt in range(3):
                result = self._check_relay_reachable(timeout=5.0)
                if result["reachable"]:
                    best_result = result
                    break
                if attempt < 2:
                    time.sleep(2)

            if best_result and best_result["reachable"]:
                diag = {"status": "ok", "ms": best_result["ms"]}
            else:
                diag = {
                    "status": "fail",
                    "http_ok": self._check_relay_http(),
                    "zapret_running": bool(self._get_zapret_running()),
                }
            self.completed.emit(self._generation, diag)
        except Exception as exc:
            self.warning.emit(f"Relay check error: {exc}")


class TelegramProxyDiagnosticsWorker(QThread):
    progress = pyqtSignal(str)
    completed = pyqtSignal(str)

    def __init__(self, *, run_diagnostics_fn, proxy_port: int, parent=None):
        super().__init__(parent)
        self._run_diagnostics_fn = run_diagnostics_fn
        self._proxy_port = int(proxy_port)

    def run(self) -> None:
        try:
            result_text = self._run_diagnostics_fn(
                proxy_port=self._proxy_port,
                progress_callback=self.progress.emit,
            )
        except Exception as exc:
            log(f"TelegramProxyDiagnosticsWorker: ошибка диагностики: {exc}", "WARNING")
            result_text = str(exc)
        self.completed.emit(str(result_text or ""))


class TelegramHostsEnsureWorker(QThread):
    completed = pyqtSignal(int, object)

    def __init__(self, request_id: int, *, ensure_hosts_fn, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._ensure_hosts_fn = ensure_hosts_fn

    def run(self) -> None:
        try:
            plan = self._ensure_hosts_fn()
        except Exception as exc:
            log(f"TelegramHostsEnsureWorker: ошибка проверки hosts: {exc}", "WARNING")
            plan = None
        self.completed.emit(self._request_id, plan)


class TelegramProxySettingsSaveWorker(QThread):
    completed = pyqtSignal(int, str, object, object)
    failed = pyqtSignal(int, str, str, object)

    def __init__(
        self,
        request_id: int,
        *,
        save_settings_action,
        action: str,
        host: str = "",
        port: int = 0,
        user: str = "",
        password: str = "",
        enabled: bool = False,
        context_extra: dict | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._save_settings_action = save_settings_action
        self._action = str(action or "").strip()
        self._host = str(host or "").strip()
        self._port = int(port or 0)
        self._user = str(user or "").strip()
        self._password = str(password or "")
        self._enabled = bool(enabled)
        self._context_extra = dict(context_extra or {})

    def run(self) -> None:
        context = {
            "host": self._host,
            "port": self._port,
            "user": self._user,
            "password": self._password,
            "enabled": self._enabled,
        }
        context.update(self._context_extra)
        try:
            result = self._save_settings_action(
                self._action,
                host=self._host,
                port=self._port,
                user=self._user,
                password=self._password,
                enabled=self._enabled,
            )
        except Exception as exc:
            log(f"TelegramProxySettingsSaveWorker: не удалось сохранить настройку {self._action}: {exc}", "WARNING")
            self.failed.emit(self._request_id, self._action, str(exc), context)
            return
        self.completed.emit(self._request_id, self._action, result, context)
