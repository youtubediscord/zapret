from __future__ import annotations

import inspect

from PyQt6.QtCore import QEvent, QObject, QTimer

from ui.theme import get_theme_tokens

try:
    from qfluentwidgets import qconfig
except ImportError:
    qconfig = None  # type: ignore[assignment]


def build_theme_refresh_key(tokens) -> tuple[str, str, str, str, str]:
    """Возвращает ключ актуальности локальных theme-стилей."""
    return (
        str(getattr(tokens, "theme_name", "")),
        str(getattr(tokens, "accent_hex", "")),
        str(getattr(tokens, "font_family_qss", "")),
        str(getattr(tokens, "surface_bg", "")),
        str(getattr(tokens, "surface_border", "")),
    )


class ThemeRefreshController(QObject):
    """Единый lifecycle обновления локальных theme-зависимых стилей."""

    def __init__(
        self,
        target,
        apply_callback,
        *,
        key_builder=None,
        is_build_pending=None,
    ) -> None:
        super().__init__(target)
        self._target = target
        self._apply_callback = apply_callback
        self._key_builder = key_builder or build_theme_refresh_key
        self._is_build_pending = is_build_pending
        self._refresh_scheduled = False
        self._refresh_pending_when_hidden = False
        self._pending_force = False
        self._applying_refresh = False
        self._last_theme_key = None

        try:
            target.installEventFilter(self)
        except Exception:
            pass

        if qconfig is not None:
            try:
                qconfig.themeChanged.connect(self._on_theme_signal)
            except Exception:
                pass
            try:
                qconfig.themeColorChanged.connect(self._on_theme_signal)
            except Exception:
                pass

    def eventFilter(self, watched, event):  # noqa: N802 (Qt override)
        try:
            if watched is self._target and event.type() in (
                QEvent.Type.StyleChange,
                QEvent.Type.PaletteChange,
            ):
                self.request_refresh()
        except Exception:
            pass
        return super().eventFilter(watched, event)

    def invalidate(self) -> None:
        self._last_theme_key = None

    def request_refresh(self, *, force: bool = False) -> None:
        if self._applying_refresh:
            self._pending_force = self._pending_force or bool(force)
            return

        if callable(self._is_build_pending):
            try:
                if bool(self._is_build_pending()):
                    self._refresh_pending_when_hidden = True
                    self._pending_force = self._pending_force or bool(force)
                    return
            except Exception:
                pass

        try:
            if not self._target.isVisible():
                self._refresh_pending_when_hidden = True
                self._pending_force = self._pending_force or bool(force)
                return
        except Exception:
            pass

        self._pending_force = self._pending_force or bool(force)
        if self._refresh_scheduled:
            return
        self._refresh_scheduled = True
        QTimer.singleShot(0, self._apply_debounced)

    def flush_pending(self) -> None:
        if not self._refresh_pending_when_hidden and not self._pending_force:
            return
        self._refresh_pending_when_hidden = False
        pending_force = bool(self._pending_force)
        self._pending_force = False
        self.request_refresh(force=pending_force)

    def _on_theme_signal(self, *_args) -> None:
        self.request_refresh()

    def _apply_debounced(self) -> None:
        self._refresh_scheduled = False
        force = bool(self._pending_force)
        self._pending_force = False

        if callable(self._is_build_pending):
            try:
                if bool(self._is_build_pending()):
                    self._refresh_pending_when_hidden = True
                    self._pending_force = self._pending_force or force
                    return
            except Exception:
                pass

        try:
            if not self._target.isVisible():
                self._refresh_pending_when_hidden = True
                self._pending_force = self._pending_force or force
                return
        except Exception:
            pass

        tokens = get_theme_tokens()
        theme_key = self._key_builder(tokens)
        if not force and theme_key == self._last_theme_key:
            return

        self._applying_refresh = True
        try:
            self._invoke_apply(tokens=tokens, force=force)
            self._last_theme_key = theme_key
        finally:
            self._applying_refresh = False

    def _invoke_apply(self, *, tokens, force: bool) -> None:
        callback = self._apply_callback
        try:
            signature = inspect.signature(callback)
            params = signature.parameters
        except (TypeError, ValueError):
            params = {}

        if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
            callback(tokens=tokens, force=force)
            return
        if "tokens" in params and "force" in params:
            callback(tokens=tokens, force=force)
            return
        if "tokens" in params:
            callback(tokens=tokens)
            return
        if "force" in params:
            callback(force=force)
            return
        callback()
