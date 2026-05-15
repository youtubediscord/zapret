from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal

from app_notifications import advisory_notification
from log.log import log
from main.post_startup_gate import bind_startup_gate, is_window_alive
from main.post_startup_threading import schedule_after, start_daemon_thread
from ui.window_adapter import get_loaded_page, show_page

if TYPE_CHECKING:
    from main.window import LupiDPIApp


class _UpdateCheckBridge(QObject):
    update_found = pyqtSignal(str, str)
    no_update = pyqtSignal(str)
    check_error = pyqtSignal(str)


def install_update_check(
    window: "LupiDPIApp",
    *,
    updater_feature,
    notify,
    set_status,
) -> None:
    update_bridge = _UpdateCheckBridge()

    def _on_update_found(version: str, release_notes: str) -> None:
        if not is_window_alive(window):
            return
        try:
            try:
                set_status(f"Доступно обновление v{version}")
            except Exception:
                pass
            from qfluentwidgets import MessageBox as FluentMessageBox
            from app.page_names import PageName as StartupPageName

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
        if not is_window_alive(window):
            return
        try:
            try:
                set_status(f"Обновлений нет, установлена версия {current_version}")
            except Exception:
                pass
            notify(
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
        if not is_window_alive(window):
            return
        try:
            set_status("Не удалось проверить обновления")
        except Exception:
            pass
        log(f"Не удалось проверить обновления при запуске: {error}", "⚠️ UPDATE")

    update_bridge.update_found.connect(_on_update_found)
    update_bridge.no_update.connect(_on_no_update)
    update_bridge.check_error.connect(_on_update_check_error)

    def _startup_update_worker() -> None:
        try:
            result = updater_feature.run_startup_update_check()
            if result.get("skipped"):
                log(
                    f"Автопроверка обновлений пропущена: {result.get('skip_reason') or 'нет необходимости'}",
                    "🔁 UPDATE",
                )
            elif result.get("error"):
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
        if not is_window_alive(window):
            return
        if not updater_feature.is_auto_update_enabled():
            log("Автопроверка обновлений при запуске отключена", "🔁 UPDATE")
            return
        try:
            set_status("Проверка обновлений...")
        except Exception:
            pass

        start_daemon_thread("StartupUpdateCheckWorker", _startup_update_worker)

    def _schedule_startup_update_check_deferred() -> None:
        if not is_window_alive(window):
            return
        delay_ms = 12000
        log(f"Автопроверка обновлений отложена на {delay_ms}ms после готовности UI", "DEBUG")
        schedule_after(
            delay_ms,
            lambda: is_window_alive(window) and _schedule_startup_update_check(),
        )

    bind_startup_gate(
        window.startup_post_init_ready,
        _schedule_startup_update_check_deferred,
        is_ready=lambda: bool(window.startup_state.post_init_ready),
    )
