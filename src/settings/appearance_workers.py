from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log.log import log


class AppearanceInitialStateLoadWorker(QThread):
    """Загружает начальное состояние страницы оформления вне UI-потока."""

    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, *, load_page_initial_state, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._load_page_initial_state = load_page_initial_state

    def run(self) -> None:
        try:
            result = self._load_page_initial_state()
        except Exception as exc:
            log(f"AppearanceInitialStateLoadWorker: не удалось загрузить состояние: {exc}", "WARNING")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, result)


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
        save_display_mode,
        save_ui_language,
        save_background_preset,
        save_mica_enabled,
        save_rkn_background,
        save_window_opacity,
        save_snowflakes_enabled,
        save_garland_enabled,
        save_accent_color,
        save_follow_windows_accent,
        save_tinted_background,
        save_tinted_background_intensity,
        save_animations_enabled,
        save_smooth_scroll_enabled,
        save_editor_smooth_scroll_enabled,
        save_sidebar_icon_style,
        load_tinted_settings,
        load_editor_smooth_scroll_enabled,
        parent=None,
    ):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._action = str(action or "").strip()
        self._value = value
        self._context_extra = dict(context_extra or {})
        self._save_display_mode = save_display_mode
        self._save_ui_language = save_ui_language
        self._save_background_preset = save_background_preset
        self._save_mica_enabled = save_mica_enabled
        self._save_rkn_background = save_rkn_background
        self._save_window_opacity = save_window_opacity
        self._save_snowflakes_enabled = save_snowflakes_enabled
        self._save_garland_enabled = save_garland_enabled
        self._save_accent_color = save_accent_color
        self._save_follow_windows_accent = save_follow_windows_accent
        self._save_tinted_background = save_tinted_background
        self._save_tinted_background_intensity = save_tinted_background_intensity
        self._save_animations_enabled = save_animations_enabled
        self._save_smooth_scroll_enabled = save_smooth_scroll_enabled
        self._save_editor_smooth_scroll_enabled = save_editor_smooth_scroll_enabled
        self._save_sidebar_icon_style = save_sidebar_icon_style
        self._load_tinted_settings = load_tinted_settings
        self._load_editor_smooth_scroll_enabled = load_editor_smooth_scroll_enabled

    def run(self) -> None:
        context = {"value": self._value}
        context.update(self._context_extra)
        try:
            if self._action == "display_mode":
                result = self._save_display_mode(str(self._value or "dark"))
            elif self._action == "ui_language":
                result = self._save_ui_language(str(self._value or ""))
            elif self._action == "background_preset":
                result = self._save_background_preset(str(self._value or "standard"))
            elif self._action == "mica_enabled":
                result = self._save_mica_enabled(bool(self._value))
            elif self._action == "rkn_background":
                result = self._save_rkn_background(self._value)
            elif self._action == "window_opacity":
                result = self._save_window_opacity(int(self._value or 0))
            elif self._action == "snowflakes_enabled":
                result = self._save_snowflakes_enabled(bool(self._value))
            elif self._action == "garland_enabled":
                result = self._save_garland_enabled(bool(self._value))
            elif self._action == "accent_color":
                result = {
                    "accent": self._save_accent_color(str(self._value or "")),
                    "tinted": self._load_tinted_settings(),
                }
            elif self._action == "follow_windows_accent":
                result = self._save_follow_windows_accent(bool(self._value))
            elif self._action == "tinted_background":
                result = self._save_tinted_background(bool(self._value))
            elif self._action == "tinted_intensity":
                result = self._save_tinted_background_intensity(int(self._value or 0))
            elif self._action == "animations_enabled":
                result = {
                    "animations": self._save_animations_enabled(bool(self._value)),
                    "editor_smooth_scroll": self._load_editor_smooth_scroll_enabled(),
                }
            elif self._action == "smooth_scroll_enabled":
                result = self._save_smooth_scroll_enabled(bool(self._value))
            elif self._action == "editor_smooth_scroll_enabled":
                result = self._save_editor_smooth_scroll_enabled(bool(self._value))
            elif self._action == "sidebar_icon_style":
                result = self._save_sidebar_icon_style(str(self._value or "standard"))
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

    def __init__(self, request_id: int, *, load_rkn_background, get_rkn_background_options, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._load_rkn_background = load_rkn_background
        self._get_rkn_background_options = get_rkn_background_options

    def run(self) -> None:
        try:
            result = {
                "saved_value": self._load_rkn_background().value,
                "options": tuple(self._get_rkn_background_options()),
            }
        except Exception as exc:
            log(f"AppearanceRknBackgroundOptionsLoadWorker: не удалось загрузить RKN-фоны: {exc}", "WARNING")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, result)


class AppearanceWindowsAccentLoadWorker(QThread):
    """Читает системный акцент Windows вне UI-потока."""

    loaded = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, request_id: int, *, load_windows_system_accent, parent=None):
        super().__init__(parent)
        self._request_id = int(request_id)
        self._load_windows_system_accent = load_windows_system_accent

    def run(self) -> None:
        try:
            result = self._load_windows_system_accent()
        except Exception as exc:
            log(f"AppearanceWindowsAccentLoadWorker: не удалось загрузить системный акцент: {exc}", "WARNING")
            self.failed.emit(self._request_id, str(exc))
            return
        self.loaded.emit(self._request_id, result)


class ThemePersistWorker(QThread):
    saved = pyqtSignal(str, bool)
    failed = pyqtSignal(str, str)

    def __init__(self, theme_name: str, *, save_selected_theme, parent=None):
        super().__init__(parent)
        self._theme_name = str(theme_name or "").strip()
        self._save_selected_theme = save_selected_theme

    def run(self) -> None:
        try:
            result = self._save_selected_theme(self._theme_name)
        except Exception as exc:
            self.failed.emit(self._theme_name, str(exc))
            return
        self.saved.emit(self._theme_name, bool(result))
