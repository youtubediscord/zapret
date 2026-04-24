from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

from app_notifications import advisory_notification
from log.log import is_verbose_logging_enabled, log

from main.post_startup_workers import (
    build_global_exception_handler,
    collect_deferred_maintenance_payload,
    collect_startup_checks_payload,
    run_cpu_diagnostic,
    run_startup_update_check,
)
from main.runtime_state import is_cpu_diagnostic_enabled
from ui.window_adapter import get_loaded_page, show_page

if TYPE_CHECKING:
    from main.window import LupiDPIApp


def _bind_startup_gate(signal, callback, *, is_ready) -> None:
    started = False

    def _run(*_args) -> None:
        nonlocal started
        if started:
            return
        started = True
        callback()

    try:
        signal.connect(_run)
    except Exception:
        QTimer.singleShot(0, _run)
        return

    try:
        if bool(is_ready()):
            QTimer.singleShot(0, _run)
    except Exception:
        QTimer.singleShot(0, _run)


def install_post_startup_tasks(window: "LupiDPIApp") -> None:
    def _window_alive() -> bool:
        return not bool(
            getattr(window, "_is_exiting", False)
            or getattr(window, "_closing_completely", False)
        )

    class _StartupChecksBridge(QObject):
        finished = pyqtSignal(dict)

    startup_bridge = _StartupChecksBridge()

    class _DeferredMaintenanceBridge(QObject):
        finished = pyqtSignal(dict)

    deferred_maintenance_bridge = _DeferredMaintenanceBridge()

    class _UpdateCheckBridge(QObject):
        update_found = pyqtSignal(str, str)
        no_update = pyqtSignal(str)
        check_error = pyqtSignal(str)

    update_bridge = _UpdateCheckBridge()

    def _on_startup_checks_finished(payload: dict) -> None:
        if not _window_alive():
            return
        try:
            controller = getattr(window, "window_notification_controller", None)
            notifications = payload.get("notifications") or []
            duration_ms = int(payload.get("duration_ms") or 0)

            if duration_ms > 0:
                window.log_startup_metric("StartupChecksFinished", f"{duration_ms}ms")

            if controller is not None:
                controller.notify_many([item for item in notifications if isinstance(item, dict)])

            log("✅ Все проверки пройдены", "🔹 main")
        except Exception as exc:
            log(f"Ошибка при обработке результатов проверок: {exc}", "❌ ERROR")

    startup_bridge.finished.connect(_on_startup_checks_finished)

    def _on_deferred_maintenance_finished(payload: dict) -> None:
        if not _window_alive():
            return
        try:
            controller = getattr(window, "window_notification_controller", None)
            duration_ms = int(payload.get("duration_ms") or 0)
            if duration_ms > 0:
                window.log_startup_metric("DeferredMaintenanceFinished", f"{duration_ms}ms")

            if controller is not None:
                controller.notify_many(payload.get("notifications") or [])
        except Exception as exc:
            log(f"Ошибка поздней служебной проверки: {exc}", "❌ ERROR")

    deferred_maintenance_bridge.finished.connect(_on_deferred_maintenance_finished)

    def _startup_checks_worker() -> None:
        try:
            payload = collect_startup_checks_payload(
                verbose_logging_enabled=is_verbose_logging_enabled(),
            )
            startup_bridge.finished.emit(payload)
        except Exception as exc:
            log(f"Ошибка при асинхронных проверках: {exc}", "❌ ERROR")
            if hasattr(window, "set_status"):
                try:
                    window.set_status(f"Ошибка проверок: {exc}")
                except Exception:
                    pass
            startup_bridge.finished.emit(
                {
                    "notifications": [],
                    "duration_ms": 0,
                }
            )

    def _start_startup_checks() -> None:
        import threading

        window.log_startup_metric("StartupChecksStarted", "startup_checks_worker")
        threading.Thread(target=_startup_checks_worker, daemon=True).start()

    _bind_startup_gate(
        window.startup_interactive_ready,
        _start_startup_checks,
        is_ready=lambda: bool(getattr(window, "_startup_interactive_logged", False)),
    )

    def _deferred_maintenance_worker() -> None:
        try:
            payload = collect_deferred_maintenance_payload()
        except Exception as exc:
            log(f"Ошибка поздних служебных проверок: {exc}", "❌ ERROR")
            payload = {
                "notifications": [],
                "telega_found_path": None,
                "duration_ms": 0,
            }
        deferred_maintenance_bridge.finished.emit(payload)

    def _start_deferred_maintenance() -> None:
        if not _window_alive():
            return
        import threading

        window.log_startup_metric("DeferredMaintenanceStarted", "telega_association_worker")
        threading.Thread(target=_deferred_maintenance_worker, daemon=True).start()

    def _schedule_deferred_maintenance() -> None:
        if not _window_alive():
            return
        delay_ms = 6000
        log(
            f"Проверка Telega Desktop и служебные действия отложены на {delay_ms}ms после post-init",
            "DEBUG",
        )
        QTimer.singleShot(delay_ms, lambda: _window_alive() and _start_deferred_maintenance())

    _bind_startup_gate(
        window.startup_post_init_ready,
        _schedule_deferred_maintenance,
        is_ready=lambda: bool(getattr(window, "_startup_post_init_ready", False)),
    )

    def _on_update_found(version: str, release_notes: str) -> None:
        if not _window_alive():
            return
        try:
            try:
                window.set_status(f"Доступно обновление v{version}")
            except Exception:
                pass
            from qfluentwidgets import MessageBox as FluentMessageBox
            from ui.page_names import PageName as StartupPageName

            box = FluentMessageBox(
                "Доступно обновление",
                f"Выпущена версия {version}. Скачать и установить сейчас?",
                window,
            )
            box.yesButton.setText("Скачать и установить")
            box.cancelButton.setText("Позже")
            if not box.exec():
                return
            show_page(window, StartupPageName.SERVERS)
            page = get_loaded_page(window, StartupPageName.SERVERS)
            if page is not None:
                page.present_startup_update(
                    version,
                    release_notes,
                    install_after_show=True,
                )
        except Exception as exc:
            log(f"Ошибка при показе диалога обновления: {exc}", "❌ ERROR")

    def _on_no_update(current_version: str) -> None:
        if not _window_alive():
            return
        try:
            try:
                window.set_status(f"Обновлений нет, установлена версия {current_version}")
            except Exception:
                pass
            controller = getattr(window, "window_notification_controller", None)
            if controller is not None:
                controller.notify(
                    advisory_notification(
                        level="success",
                        title="Обновлений нет",
                        content=f"Установлена актуальная версия {current_version}",
                        source="startup.update_check",
                        presentation="infobar",
                        queue="immediate",
                        duration=4000,
                        dedupe_key=f"startup.update_check:{current_version}",
                    )
                )
        except Exception as exc:
            log(f"Ошибка при показе InfoBar: {exc}", "❌ ERROR")

    def _on_update_check_error(error: str) -> None:
        if not _window_alive():
            return
        try:
            window.set_status("Не удалось проверить обновления")
        except Exception:
            pass
        log(f"Не удалось проверить обновления при запуске: {error}", "⚠️ UPDATE")

    update_bridge.update_found.connect(_on_update_found)
    update_bridge.no_update.connect(_on_no_update)
    update_bridge.check_error.connect(_on_update_check_error)

    def _startup_update_worker() -> None:
        try:
            result = run_startup_update_check()
            if result.get("error"):
                update_bridge.check_error.emit(result["error"])
            elif result.get("has_update"):
                update_bridge.update_found.emit(
                    result.get("version") or "",
                    result.get("release_notes") or "",
                )
            else:
                update_bridge.no_update.emit(result.get("version") or "")
        except Exception as exc:
            log(f"Ошибка воркера проверки обновлений: {exc}", "❌ ERROR")

    def _schedule_startup_update_check() -> None:
        if not _window_alive():
            return
        try:
            from settings.store import get_auto_update_enabled


            if not get_auto_update_enabled():
                log("Автопроверка обновлений при запуске отключена", "🔁 UPDATE")
                return
        except Exception:
            pass
        try:
            window.set_status("Проверка обновлений...")
        except Exception:
            pass
        import threading

        threading.Thread(target=_startup_update_worker, daemon=True).start()

    def _schedule_startup_update_check_deferred() -> None:
        if not _window_alive():
            return
        delay_ms = 12000
        log(f"Автопроверка обновлений отложена на {delay_ms}ms после готовности UI", "DEBUG")
        QTimer.singleShot(delay_ms, lambda: _window_alive() and _schedule_startup_update_check())

    _bind_startup_gate(
        window.startup_post_init_ready,
        _schedule_startup_update_check_deferred,
        is_ready=lambda: bool(getattr(window, "_startup_post_init_ready", False)),
    )

    if is_cpu_diagnostic_enabled():
        import threading

        threading.Thread(target=run_cpu_diagnostic, daemon=True, name="CPUDiagnostic").start()

    sys.excepthook = build_global_exception_handler()
