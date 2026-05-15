from __future__ import annotations

import webbrowser
from typing import Callable

from PyQt6.QtWidgets import QApplication

from app_notifications import advisory_notification
from log.log import log


class WindowNotificationActionHandler:
    """Выполняет действия кнопок внутри системных уведомлений."""

    def __init__(
        self,
        *,
        notify: Callable[[dict | None], None],
        runtime_feature,
        show_page,
    ) -> None:
        self._notify = notify
        self._runtime = runtime_feature
        self._show_page = show_page

    def build_action_callback(self, action: dict, bar):
        kind = str(action.get("kind") or "").strip().lower()
        if not kind:
            return None

        if kind == "copy_text":
            return lambda: self.copy_to_clipboard_with_feedback(
                str(action.get("value") or ""),
                label=str(action.get("feedback_label") or "Текст"),
            )

        if kind == "open_url":
            return lambda: webbrowser.open(str(action.get("value") or ""))

        if kind == "open_preset_setup_page":
            return lambda: self._open_preset_setup_page_for_method(str(action.get("value") or ""), bar)

        if kind == "launch_conflict_kill_start":
            return lambda: self._run_launch_conflict_action(
                request_id=int(action.get("value") or 0),
                close_conflicts=True,
                bar=bar,
            )

        if kind == "launch_conflict_ignore_start":
            return lambda: self._run_launch_conflict_action(
                request_id=int(action.get("value") or 0),
                close_conflicts=False,
                bar=bar,
            )

        if kind == "launch_conflict_cancel":
            return lambda: self._cancel_launch_conflict_action(
                request_id=int(action.get("value") or 0),
                bar=bar,
            )

        if kind == "disable_proxy":
            return self._disable_proxy_with_feedback

        if kind == "disable_kaspersky_warning":
            return lambda: self._disable_kaspersky_warning_forever(bar)

        if kind == "disable_telega_warning":
            return lambda: self._disable_telega_warning_forever(bar)

        if kind == "autofix":
            return lambda: self._run_windivert_autofix(str(action.get("value") or ""), bar)

        return None

    def copy_to_clipboard_with_feedback(self, text: str, *, label: str = "Текст") -> None:
        try:
            clipboard = QApplication.clipboard()
            if clipboard is None:
                raise RuntimeError("Буфер обмена недоступен")
            clipboard.setText(str(text or ""))
            self._notify(
                advisory_notification(
                    level="info",
                    title="Скопировано",
                    content=f"{label} скопирован в буфер обмена",
                    source="system.clipboard",
                    presentation="infobar",
                    queue="immediate",
                    duration=5000,
                    dedupe_key=f"clipboard.success:{label.lower()}",
                )
            )
        except Exception as e:
            log(f"Не удалось скопировать в буфер обмена: {e}", "DEBUG")
            self._notify(
                advisory_notification(
                    level="warning",
                    title="Не удалось скопировать",
                    content=f"Не удалось скопировать {label.lower()}",
                    source="system.clipboard",
                    presentation="infobar",
                    queue="immediate",
                    duration=7000,
                    dedupe_key=f"clipboard.failure:{label.lower()}",
                )
            )

    def _disable_proxy_with_feedback(self) -> None:
        try:
            from startup.check_start import _disable_proxy

            success, disable_error = _disable_proxy()
        except Exception as e:
            success, disable_error = False, str(e)

        self._notify(
            advisory_notification(
                level="success" if success else "warning",
                title="Прокси отключен" if success else "Не удалось отключить прокси",
                content=(
                    "Ручной системный прокси был отключен."
                    if success else str(disable_error or "Настройки прокси не были изменены.")
                ),
                source="startup.proxy.action",
                presentation="infobar",
                queue="immediate",
                duration=7000 if success else 10000,
                dedupe_key="startup.proxy.action",
            )
        )

    def _run_launch_conflict_action(self, *, request_id: int, close_conflicts: bool, bar=None) -> None:
        runtime = self._runtime
        if not runtime.is_available():
            self._notify(
                advisory_notification(
                    level="warning",
                    title="Не удалось продолжить запуск",
                    content="Runtime запуска DPI недоступен.",
                    source="launch.conflicting_processes.action",
                    presentation="infobar",
                    queue="immediate",
                    duration=7000,
                    dedupe_key="launch.conflicting_processes.action",
                )
            )
            return

        self._close_bar(bar)

        try:
            runtime.resume_start_after_conflict_resolution(
                int(request_id or 0),
                close_conflicts=bool(close_conflicts),
            )
        except Exception as e:
            log(f"Не удалось обработать действие по конфликтующим процессам: {e}", "DEBUG")
            self._notify(
                advisory_notification(
                    level="warning",
                    title="Не удалось продолжить запуск",
                    content="Во время обработки конфликтующих процессов произошла ошибка.",
                    source="launch.conflicting_processes.action",
                    presentation="infobar",
                    queue="immediate",
                    duration=7000,
                    dedupe_key="launch.conflicting_processes.action",
                )
            )

    def _cancel_launch_conflict_action(self, *, request_id: int, bar=None) -> None:
        runtime = self._runtime
        if not runtime.is_available():
            return

        self._close_bar(bar)

        try:
            runtime.cancel_start_after_conflict_prompt(int(request_id or 0))
        except Exception as e:
            log(f"Не удалось отменить запуск после предупреждения о конфликтах: {e}", "DEBUG")

    def _open_preset_setup_page_for_method(self, method: str, bar=None) -> None:
        try:
            from ui.navigation_pages import resolve_preset_setup_page_for_method

            preset_setup_page = resolve_preset_setup_page_for_method(method)
            if preset_setup_page is None:
                raise RuntimeError("Не удалось определить страницу настройки preset-а для текущего режима")

            ok = bool(self._show_page(preset_setup_page, allow_internal=True))
            if not ok:
                raise RuntimeError("Не удалось открыть страницу настройки preset-а")

            self._close_bar(bar)
        except Exception as e:
            log(f"Не удалось открыть страницу настройки preset-а: {e}", "DEBUG")
            self._notify(
                advisory_notification(
                    level="warning",
                    title="Не удалось открыть раздел",
                    content="Не удалось перейти в настройку preset-а автоматически.",
                    source="navigation.preset_setup_page",
                    presentation="infobar",
                    queue="immediate",
                    duration=7000,
                    dedupe_key="navigation.preset_setup_page",
                )
            )

    def _disable_kaspersky_warning_forever(self, bar=None) -> None:
        try:
            from startup.kaspersky import disable_kaspersky_warning_forever

            success = bool(disable_kaspersky_warning_forever())
        except Exception as e:
            log(f"Не удалось отключить предупреждение Kaspersky: {e}", "DEBUG")
            success = False

        if success:
            self._close_bar(bar)

        self._notify(
            advisory_notification(
                level="success" if success else "warning",
                title="Напоминание отключено" if success else "Не удалось отключить напоминание",
                content=(
                    "Предупреждение о Kaspersky больше не будет показываться."
                    if success else
                    "Не удалось сохранить настройку для предупреждения о Kaspersky."
                ),
                source="startup.kaspersky.action",
                presentation="infobar",
                queue="immediate",
                duration=5000 if success else 8000,
                dedupe_key="startup.kaspersky.action.disable_warning",
            )
        )

    def _disable_telega_warning_forever(self, bar=None) -> None:
        try:
            from startup.telega_check import disable_telega_warning_forever

            success = bool(disable_telega_warning_forever())
        except Exception as e:
            log(f"Не удалось отключить предупреждение Telega: {e}", "DEBUG")
            success = False

        if success:
            self._close_bar(bar)

        self._notify(
            advisory_notification(
                level="success" if success else "warning",
                title="Напоминание отключено" if success else "Не удалось отключить напоминание",
                content=(
                    "Предупреждение о Telega Desktop больше не будет показываться."
                    if success else
                    "Не удалось сохранить настройку для предупреждения о Telega Desktop."
                ),
                source="startup.telega.action",
                presentation="infobar",
                queue="immediate",
                duration=5000 if success else 8000,
                dedupe_key="startup.telega.action.disable_warning",
            )
        )

    def _run_windivert_autofix(self, action: str, bar) -> None:
        if not action:
            return

        try:
            ok, message = self._runtime.execute_windivert_autofix(action)
            self._close_bar(bar)

            self._notify(
                advisory_notification(
                    level="success" if ok else "warning",
                    title="Готово" if ok else "Не удалось",
                    content=str(message or ""),
                    source="launch.autofix",
                    presentation="infobar",
                    queue="immediate",
                    duration=5000 if ok else 8000,
                    dedupe_key=f"launch.autofix:{action}",
                )
            )
        except Exception as e:
            log(f"Auto-fix error: {e}", "ERROR")

    @staticmethod
    def _close_bar(bar) -> None:
        try:
            if bar is not None:
                bar.close()
        except Exception:
            pass
