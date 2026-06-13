from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PyQt6.QtWidgets import QApplication

from app_notifications import advisory_notification
from log.log import log


@dataclass(frozen=True, slots=True)
class WindowNotificationRuntimeActions:
    is_available: Callable[[], bool]
    cancel_start_after_conflict_prompt: Callable[[int], object]
    execute_windivert_autofix: Callable[[str], tuple[bool, str]]
    install_windows_server_wlanapi: Callable[[], tuple[bool, str]]
    prepare_launch_conflict_resolution: Callable[..., tuple[bool, str]]
    continue_start_after_conflict_resolution: Callable[[int], object]


class WindowNotificationActionHandler:
    """Выполняет действия кнопок внутри системных уведомлений."""

    def __init__(
        self,
        *,
        notify: Callable[[dict | None], None],
        runtime_actions: WindowNotificationRuntimeActions,
        show_page,
        open_url: Callable[[str], None],
        request_disable_proxy: Callable[[object | None], None],
        request_disable_kaspersky_warning: Callable[[object | None], None],
        request_disable_telega_warning: Callable[[object | None], None],
        request_windivert_autofix: Callable[[str, object | None], None],
        request_windows_server_wlanapi_install: Callable[[object | None], None],
        request_launch_conflict_action: Callable[[int, bool, object | None], None],
    ) -> None:
        self._notify = notify
        self._runtime_actions = runtime_actions
        self._show_page = show_page
        self._open_url = open_url
        self._request_disable_proxy = request_disable_proxy
        self._request_disable_kaspersky_warning = request_disable_kaspersky_warning
        self._request_disable_telega_warning = request_disable_telega_warning
        self._request_windivert_autofix = request_windivert_autofix
        self._request_windows_server_wlanapi_install = request_windows_server_wlanapi_install
        self._request_launch_conflict_action = request_launch_conflict_action

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
            return lambda: self._open_url(str(action.get("value") or ""))

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
            return lambda: self._request_disable_proxy(bar)

        if kind == "disable_kaspersky_warning":
            return lambda: self._request_disable_kaspersky_warning(bar)

        if kind == "disable_telega_warning":
            return lambda: self._request_disable_telega_warning(bar)

        if kind == "autofix":
            return lambda: self._request_windivert_autofix(str(action.get("value") or ""), bar)

        if kind == "install_windows_server_wlanapi":
            return lambda: self._request_windows_server_wlanapi_install(bar)

        if kind == "dismiss":
            return lambda: self._close_bar(bar)

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

    def _run_launch_conflict_action(self, *, request_id: int, close_conflicts: bool, bar=None) -> None:
        if not self._runtime_actions.is_available():
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

        self._request_launch_conflict_action(int(request_id or 0), bool(close_conflicts), bar)

    def _cancel_launch_conflict_action(self, *, request_id: int, bar=None) -> None:
        if not self._runtime_actions.is_available():
            return

        self._close_bar(bar)

        try:
            self._runtime_actions.cancel_start_after_conflict_prompt(int(request_id or 0))
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

    @staticmethod
    def _close_bar(bar) -> None:
        try:
            if bar is not None:
                bar.close()
        except Exception:
            pass
