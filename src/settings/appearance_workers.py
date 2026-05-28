from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class AppearanceSettingsSaveWorker(QThread):
    """Сохраняет настройки внешнего вида вне UI-потока."""

    completed = pyqtSignal(int, str, object, object)
    failed = pyqtSignal(int, str, str, object)

    def __init__(
        self,
        request_id: int,
        *,
        action: str,
        value=None,
        context_extra: dict | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._action = str(action or "").strip()
        self._value = value
        self._context_extra = dict(context_extra or {})

    def run(self) -> None:
        import settings.appearance as appearance_settings

        context = {"value": self._value}
        context.update(self._context_extra)
        try:
            if self._action == "display_mode":
                result = appearance_settings.save_display_mode(str(self._value or "dark"))
            elif self._action == "ui_language":
                result = appearance_settings.save_ui_language(str(self._value or ""))
            elif self._action == "background_preset":
                result = appearance_settings.save_background_preset(str(self._value or "standard"))
            elif self._action == "rkn_background":
                result = appearance_settings.save_rkn_background(self._value)
            elif self._action == "window_opacity":
                result = appearance_settings.save_window_opacity(int(self._value or 0))
            elif self._action == "snowflakes_enabled":
                result = appearance_settings.save_snowflakes_enabled(bool(self._value))
            elif self._action == "garland_enabled":
                result = appearance_settings.save_garland_enabled(bool(self._value))
            elif self._action == "accent_color":
                result = {
                    "accent": appearance_settings.save_accent_color(str(self._value or "")),
                    "tinted": appearance_settings.load_tinted_settings(),
                }
            elif self._action == "follow_windows_accent":
                result = appearance_settings.save_follow_windows_accent(bool(self._value))
            elif self._action == "tinted_background":
                result = appearance_settings.save_tinted_background(bool(self._value))
            elif self._action == "tinted_intensity":
                result = appearance_settings.save_tinted_background_intensity(int(self._value or 0))
            elif self._action == "animations_enabled":
                result = {
                    "animations": appearance_settings.save_animations_enabled(bool(self._value)),
                    "editor_smooth_scroll": appearance_settings.load_editor_smooth_scroll_enabled(),
                }
            elif self._action == "smooth_scroll_enabled":
                result = appearance_settings.save_smooth_scroll_enabled(bool(self._value))
            elif self._action == "editor_smooth_scroll_enabled":
                result = appearance_settings.save_editor_smooth_scroll_enabled(bool(self._value))
            else:
                raise ValueError(f"Неизвестная настройка внешнего вида: {self._action}")
        except Exception as exc:
            log(f"AppearanceSettingsSaveWorker: не удалось сохранить {self._action}: {exc}", "WARNING")
            self.failed.emit(self._request_id, self._action, str(exc), context)
            return
        self.completed.emit(self._request_id, self._action, result, context)


class AppearanceRknBackgroundOptionsLoadWorker(QThread):
    """Загружает список RKN-фонов вне UI-потока."""

    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)

    def run(self) -> None:
        try:
            import settings.appearance as appearance_settings
            from ui.theme import get_rkn_background_options

            result = {
                "saved_value": appearance_settings.load_rkn_background().value,
                "options": tuple(get_rkn_background_options()),
            }
        except Exception as exc:
            log(f"AppearanceRknBackgroundOptionsLoadWorker: не удалось загрузить RKN-фоны: {exc}", "WARNING")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, result)
