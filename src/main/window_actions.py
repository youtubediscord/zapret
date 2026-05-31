from __future__ import annotations

from PyQt6.QtCore import QTimer

from log.log import log


class WindowActionsMixin:
    def bind_status_message_sink(self, sink) -> None:
        self._status_message_sink = sink if callable(sink) else None

    def bind_open_folder_worker_factory(self, factory) -> None:
        self._open_folder_worker_factory = factory if callable(factory) else None

    def set_status(self, text: str) -> None:
        """Пишет пользовательский статус в лог.

        Текст также уходит в узкий status-message sink, если он подключён
        при сборке приложения. Само окно не получает доступ к общему store.
        """
        normalized_text = str(text or "")
        level = "INFO"
        lower_text = normalized_text.lower()
        if "работает" in lower_text or "запущен" in lower_text or "успешно" in lower_text:
            level = "INFO"
        elif "останов" in lower_text or "ошибка" in lower_text or "выключен" in lower_text:
            level = "WARNING"
        elif "внимание" in lower_text or "предупреждение" in lower_text:
            level = "WARNING"
        log(normalized_text, level)

        sink = getattr(self, "_status_message_sink", None)
        if callable(sink):
            try:
                sink(normalized_text)
            except Exception:
                pass

    def open_folder(self) -> None:
        """Opens the DPI folder."""
        runtime = self._open_folder_runtime()
        if runtime.is_running() or getattr(self, "_open_folder_start_scheduled", False):
            self._open_folder_pending = True
            return
        self._start_open_folder_worker()

    def _open_folder_runtime(self):
        runtime = getattr(self, "_open_folder_runtime_instance", None)
        if runtime is None:
            from ui.one_shot_worker_runtime import OneShotWorkerRuntime

            runtime = OneShotWorkerRuntime()
            self._open_folder_runtime_instance = runtime
        return runtime

    def create_open_folder_worker(self):
        factory = getattr(self, "_open_folder_worker_factory", None)
        if not callable(factory):
            raise RuntimeError("Фабрика worker'а для открытия папки не подключена")
        return factory(parent=self)

    def _start_open_folder_worker(self) -> None:
        try:
            self._open_folder_pending = False
            self._open_folder_runtime().start_qthread_worker(
                worker_factory=lambda _request_id: self.create_open_folder_worker(),
                on_failed=lambda _request_id, error: self._on_open_folder_failed(error),
                on_finished=self._on_open_folder_worker_finished,
                signal_includes_request_id=False,
            )
        except Exception as e:
            self.set_status(f"Ошибка при открытии папки: {str(e)}")

    def _on_open_folder_failed(self, error: str) -> None:
        self.set_status(f"Ошибка при открытии папки: {str(error)}")

    def _on_open_folder_worker_finished(self, _worker) -> None:
        if getattr(self, "_open_folder_pending", False):
            self._schedule_open_folder_worker_start()

    def _schedule_open_folder_worker_start(self) -> None:
        if getattr(self, "_open_folder_start_scheduled", False):
            return
        self._open_folder_start_scheduled = True
        try:
            QTimer.singleShot(0, self._run_scheduled_open_folder_worker_start)
        except Exception:
            self._run_scheduled_open_folder_worker_start()

    def _run_scheduled_open_folder_worker_start(self) -> None:
        self._open_folder_start_scheduled = False
        if not getattr(self, "_open_folder_pending", False):
            return
        self._start_open_folder_worker()

    def open_connection_test(self) -> None:
        """Переключает на вкладку диагностики соединений."""
        try:
            from app.page_names import PageName
            from ui.page_actions import request_blockcheck_diagnostics_focus
            from ui.window_adapter import route_window_search_result, show_page

            if show_page(self, PageName.BLOCKCHECK):
                route_window_search_result(self, PageName.BLOCKCHECK, "diagnostics")
                request_blockcheck_diagnostics_focus(self)
                log("Открыта вкладка диагностики в BlockCheck", "INFO")
        except Exception as e:
            log(f"Ошибка при открытии вкладки тестирования: {e}", "❌ ERROR")
            self.set_status(f"Ошибка: {e}")
