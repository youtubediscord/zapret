from __future__ import annotations

from log.log import log
from settings import store as settings_store

_LAUNCH_METHOD_DEFAULT = "direct_zapret2"
_SUPPORTED_LAUNCH_METHODS = {
    "direct_zapret2",
    "direct_zapret1",
    "orchestra",
}

DIRECT_UI_MODE_DEFAULT = "basic"
_VALID_DIRECT_ZAPRET2_UI_MODES = frozenset({"basic", "advanced"})


def normalize_direct_ui_mode(value: object) -> str:
    mode = str(value or "").strip().lower()
    if mode in _VALID_DIRECT_ZAPRET2_UI_MODES:
        return mode
    return DIRECT_UI_MODE_DEFAULT


def get_strategy_launch_method() -> str:
    try:
        normalized = str(settings_store.get_strategy_launch_method() or "").strip().lower()
        if normalized in _SUPPORTED_LAUNCH_METHODS:
            return normalized
    except Exception as e:
        log(f"Ошибка чтения метода запуска из settings.json: {e}", "ERROR")
    return _LAUNCH_METHOD_DEFAULT


def set_strategy_launch_method(method: str) -> bool:
    try:
        normalized = str(method or "").strip().lower()
        if normalized not in _SUPPORTED_LAUNCH_METHODS:
            log(
                f"Попытка сохранить неподдерживаемый метод запуска: {normalized or 'empty'}. "
                f"Используем {_LAUNCH_METHOD_DEFAULT}",
                "WARNING",
            )
            normalized = _LAUNCH_METHOD_DEFAULT
        settings_store.set_strategy_launch_method(normalized)
        log(f"Метод запуска стратегий изменен на: {normalized}", "INFO")
        return True
    except Exception as e:
        log(f"Ошибка сохранения метода запуска: {e}", "ERROR")
        return False


def get_direct_ui_mode() -> str:
    try:
        return normalize_direct_ui_mode(settings_store.get_direct_ui_mode())
    except Exception as e:
        log(f"Ошибка чтения режима direct UI из settings.json: {e}", "DEBUG")
        return DIRECT_UI_MODE_DEFAULT


def set_direct_ui_mode(mode: str) -> bool:
    value = normalize_direct_ui_mode(mode)
    try:
        settings_store.set_direct_ui_mode(value)
        log(f"Direct UI mode set to: {value}", "DEBUG")
        return True
    except Exception as e:
        log(f"Ошибка сохранения режима direct UI: {e}", "ERROR")
        return False


def _build_direct_runtime_reload_callback(*, launch_method: str, app_context, reason: str):
    method = str(launch_method or "").strip().lower()
    if method not in ("direct_zapret2", "direct_zapret1") or app_context is None:
        return None

    def _reload() -> None:
        try:
            from ui.app_window_locator import find_app_window
            from winws_runtime.flow.apply_policy import request_direct_runtime_content_apply

            host = find_app_window("launch_controller", "app_context")
            if host is None:
                return

            host_context = getattr(host, "app_context", None)
            if host_context is not None and host_context is not app_context:
                return

            request_direct_runtime_content_apply(
                host,
                launch_method=method,
                reason=str(reason or "").strip() or "settings_changed",
            )
        except Exception:
            return

    return _reload


def _get_direct_preset_facade(*, app_context=None, launch_method: str | None = None, reload_reason: str | None = None):
    try:
        method = str(launch_method or get_strategy_launch_method() or "").strip().lower()
        if method in ("direct_zapret2", "direct_zapret1") and app_context is not None:
            from direct_preset.facade import DirectPresetFacade

            reload_callback = None
            if reload_reason:
                reload_callback = _build_direct_runtime_reload_callback(
                    launch_method=method,
                    app_context=app_context,
                    reason=str(reload_reason or "").strip(),
                )

            return DirectPresetFacade.from_launch_method(
                method,
                app_context=app_context,
                on_dpi_reload_needed=reload_callback,
            )
    except Exception:
        pass
    return None


def get_wssize_enabled(*, app_context=None, launch_method: str | None = None) -> bool:
    facade = _get_direct_preset_facade(app_context=app_context, launch_method=launch_method)
    if facade is not None:
        try:
            return bool(facade.get_wssize_enabled())
        except Exception:
            return False
    return False


def set_wssize_enabled(enabled: bool, *, app_context=None, launch_method: str | None = None) -> bool:
    facade = _get_direct_preset_facade(
        app_context=app_context,
        launch_method=launch_method,
        reload_reason="wssize_toggled",
    )
    if facade is not None:
        try:
            return bool(facade.set_wssize_enabled(bool(enabled)))
        except Exception:
            return False
    return False


def get_debug_log_enabled(*, app_context=None, launch_method: str | None = None) -> bool:
    facade = _get_direct_preset_facade(app_context=app_context, launch_method=launch_method)
    if facade is not None:
        try:
            return bool(facade.get_debug_log_enabled())
        except Exception:
            return False
    return False


def set_debug_log_enabled(enabled: bool, *, app_context=None, launch_method: str | None = None) -> bool:
    facade = _get_direct_preset_facade(
        app_context=app_context,
        launch_method=launch_method,
        reload_reason="debug_log_toggled",
    )
    if facade is not None:
        try:
            return bool(facade.set_debug_log_enabled(bool(enabled)))
        except Exception:
            return False
    return False


def get_debug_log_file(*, app_context=None, launch_method: str | None = None) -> str:
    facade = _get_direct_preset_facade(app_context=app_context, launch_method=launch_method)
    if facade is not None:
        try:
            return str(facade.get_debug_log_file() or "")
        except Exception:
            return ""
    return ""


__all__ = [
    "get_strategy_launch_method",
    "set_strategy_launch_method",
    "DIRECT_UI_MODE_DEFAULT",
    "normalize_direct_ui_mode",
    "get_direct_ui_mode",
    "set_direct_ui_mode",
    "get_wssize_enabled",
    "set_wssize_enabled",
    "get_debug_log_enabled",
    "get_debug_log_file",
    "set_debug_log_enabled",
]
