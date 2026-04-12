from __future__ import annotations

import atexit
import ctypes
import sys
import time
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMessageBox

from app_notifications import advisory_notification
from log import is_verbose_logging_enabled, log
from main.runtime_state import is_cpu_diagnostic_enabled

if TYPE_CHECKING:
    from main import LupiDPIApp


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

    def _native_message_safe(title: str, message: str, flags: int) -> int:
        try:
            from startup.check_start import _native_message

            return int(_native_message(title, message, flags))
        except Exception:
            try:
                return int(ctypes.windll.user32.MessageBoxW(None, str(message), str(title), int(flags)))
            except Exception:
                return 0

    def _on_startup_checks_finished(payload: dict) -> None:
        if not _window_alive():
            return
        try:
            controller = getattr(window, "window_notification_controller", None)
            blocking_notification = payload.get("blocking_notification")
            notifications = payload.get("notifications") or []
            duration_ms = int(payload.get("duration_ms") or 0)

            if duration_ms > 0:
                window.log_startup_metric("StartupChecksFinished", f"{duration_ms}ms")

            if blocking_notification:
                if controller is not None:
                    controller.notify(blocking_notification)
                else:
                    title = str(blocking_notification.get("title") or "Ошибка")
                    content = str(blocking_notification.get("content") or "")
                    try:
                        QMessageBox.critical(window, title, content)
                    except Exception:
                        _native_message_safe(title, content, 0x10)
                QApplication.quit()
                return

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
        started_at = time.perf_counter()
        try:
            from startup.bfe_util import preload_service_status, ensure_bfe_running, cleanup as bfe_cleanup
            from startup.check_start import collect_startup_notifications, check_goodbyedpi, check_mitmproxy

            notifications: list[dict] = []
            blocking_notification: dict | None = None

            preload_service_status("BFE")

            bfe_ok, bfe_notification = ensure_bfe_running()
            if bfe_notification is not None:
                notifications.append(bfe_notification)
            if not bfe_ok:
                log("BFE не запущен, продолжаем работу после предупреждения", "⚠ WARNING")

            startup_notifications, blocking_notification = collect_startup_notifications()
            notifications.extend(startup_notifications or [])
            log(
                "Startup notifications collected: "
                f"count={len(startup_notifications or [])}, "
                f"blocking={'yes' if blocking_notification else 'no'}",
                "⏱ STARTUP",
            )

            has_gdpi, gdpi_msg = check_goodbyedpi()
            if has_gdpi and gdpi_msg:
                notifications.append(
                    advisory_notification(
                        level="warning",
                        title="Проверка при запуске",
                        content=gdpi_msg,
                        source="startup.goodbyedpi",
                        queue="startup",
                        duration=15000,
                        dedupe_key="startup.goodbyedpi",
                    )
                )

            has_mitmproxy, mitmproxy_msg = check_mitmproxy()
            if has_mitmproxy and mitmproxy_msg:
                notifications.append(
                    advisory_notification(
                        level="warning",
                        title="Проверка при запуске",
                        content=mitmproxy_msg,
                        source="startup.mitmproxy",
                        queue="startup",
                        duration=15000,
                        dedupe_key="startup.mitmproxy",
                    )
                )

            try:
                from startup.kaspersky import _check_kaspersky_antivirus, build_kaspersky_notification

                kaspersky_detected = bool(_check_kaspersky_antivirus())
                log(
                    f"Kaspersky startup check: detected={'yes' if kaspersky_detected else 'no'}",
                    "⏱ STARTUP",
                )
                if kaspersky_detected:
                    kaspersky_notification = build_kaspersky_notification()
                    if kaspersky_notification is not None:
                        log("Обнаружен антивирус Kaspersky", "⚠️ KASPERSKY")
                        notifications.append(kaspersky_notification)
            except Exception:
                pass

            if is_verbose_logging_enabled():
                from startup.admin_check_debug import debug_admin_status

                debug_admin_status()

            try:
                atexit.register(bfe_cleanup)
            except Exception:
                pass

            startup_bridge.finished.emit(
                {
                    "notifications": notifications,
                    "blocking_notification": blocking_notification,
                    "duration_ms": int((time.perf_counter() - started_at) * 1000),
                }
            )
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
                    "blocking_notification": None,
                    "duration_ms": int((time.perf_counter() - started_at) * 1000),
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
        started_at = time.perf_counter()
        telega_found_path = None
        notifications: list[dict] = []
        try:
            try:
                from startup.telega_check import _check_telega_installed, build_telega_notification

                telega_found_path = _check_telega_installed()
                log(
                    "Telega deferred check: "
                    f"found={'yes' if bool(telega_found_path) else 'no'}"
                    + (f", value={telega_found_path}" if telega_found_path else ""),
                    "⏱ STARTUP",
                )
                if telega_found_path:
                    log(f"Обнаружена Telega Desktop: {telega_found_path}", "🚨 TELEGA")
                    telega_notification = build_telega_notification(found_path=str(telega_found_path))
                    if telega_notification is not None:
                        notifications.append(telega_notification)
            except Exception:
                telega_found_path = None
        except Exception as exc:
            log(f"Ошибка поздних служебных проверок: {exc}", "❌ ERROR")
        finally:
            try:
                log(
                    f"Deferred maintenance notifications collected: count={len(notifications)}",
                    "⏱ STARTUP",
                )
            except Exception:
                pass
            deferred_maintenance_bridge.finished.emit(
                {
                    "notifications": notifications,
                    "telega_found_path": telega_found_path,
                    "duration_ms": int((time.perf_counter() - started_at) * 1000),
                }
            )

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
            window.show_page(StartupPageName.SERVERS)
            page = window.pages.get(StartupPageName.SERVERS)
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
            from updater.startup_update_check import check_for_update_sync

            result = check_for_update_sync()
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
            from config import get_auto_update_enabled

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

    def _cpu_diagnostic_worker() -> None:
        import threading as _threads
        import traceback as _traceback
        import time as _time

        _time.sleep(15)
        try:
            import psutil as _psutil

            this_proc = _psutil.Process()
            this_proc.cpu_percent(interval=None)
            _time.sleep(1)

            log("=== CPU DIAGNOSTIC: начало ===", "INFO")
            log(f"Активных тредов Python: {_threads.active_count()}", "INFO")

            frames = sys._current_frames()
            for tid, frame in frames.items():
                thread = next((item for item in _threads.enumerate() if item.ident == tid), None)
                name = thread.name if thread else f"tid-{tid}"
                stack = "".join(_traceback.format_stack(frame)).strip()
                log(f"[STACK '{name}']\n{stack[-1200:]}", "INFO")

            samples_gui = []
            for idx in range(5):
                cpu_gui = this_proc.cpu_percent(interval=2.0)
                samples_gui.append(cpu_gui)
                winws_parts = []
                for proc in _psutil.process_iter(["name", "cpu_percent"]):
                    try:
                        proc_name = (proc.info.get("name") or "").lower()
                        if proc_name in ("winws.exe", "winws2.exe"):
                            winws_parts.append(f"{proc_name}={proc.cpu_percent():.1f}%")
                    except Exception:
                        pass
                winws_str = ", ".join(winws_parts) if winws_parts else "не запущен"
                log(f"[CPU {idx + 1}/5] Python GUI: {cpu_gui:.1f}%  |  winws: {winws_str}", "INFO")

            avg = sum(samples_gui) / len(samples_gui) if samples_gui else 0
            log(f"=== CPU DIAGNOSTIC DONE: avg Python GUI = {avg:.1f}% ===", "INFO")

            if avg > 20:
                try:
                    from collections import Counter

                    sample_counts: dict = Counter()
                    for _ in range(50):
                        _time.sleep(0.1)
                        frames2 = sys._current_frames()
                        for tid2, frame2 in frames2.items():
                            thread2 = next((item for item in _threads.enumerate() if item.ident == tid2), None)
                            thread_name = thread2.name if thread2 else f"tid-{tid2}"
                            stack2 = _traceback.extract_stack(frame2)
                            key = thread_name + " | " + " → ".join(
                                f"{frame.filename.split('/')[-1].split(chr(92))[-1]}:{frame.lineno}:{frame.name}"
                                for frame in stack2[-4:]
                            )
                            sample_counts[key] += 1
                    top = sample_counts.most_common(15)
                    report = "\n".join(f"  {count:3d}x  {key}" for key, count in top)
                    log(f"[SAMPLING top-15 hotspots (50 samples × 100ms)]\n{report}", "INFO")
                except Exception as exc:
                    log(f"Sampling error: {exc}", "WARNING")
        except Exception as exc:
            log(f"CPU diagnostic error: {exc}", "WARNING")

    if is_cpu_diagnostic_enabled():
        import threading

        threading.Thread(target=_cpu_diagnostic_worker, daemon=True, name="CPUDiagnostic").start()

    def _global_exception_handler(exctype, value, tb_obj) -> None:
        import traceback as tb

        try:
            error_msg = "".join(tb.format_exception(exctype, value, tb_obj))
        except Exception as format_error:
            try:
                base_error = "".join(tb.format_exception_only(exctype, value)).strip()
            except Exception:
                base_error = f"{getattr(exctype, '__name__', exctype)}: {value!r}"
            error_msg = f"{base_error}\n[traceback formatting failed: {format_error!r}]"
        log(f"UNCAUGHT EXCEPTION: {error_msg}", level="❌ CRITICAL")

    sys.excepthook = _global_exception_handler
