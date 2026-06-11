from __future__ import annotations

import inspect

from PyQt6.QtCore import QEvent, QObject, QTimer

from ui.theme import get_theme_tokens
from qfluentwidgets import qconfig


def build_theme_refresh_key(tokens) -> tuple[str, str, str, str, str]:
    """Возвращает ключ актуальности локальных theme-стилей."""
    return (
        str(getattr(tokens, "theme_name", "")),
        str(getattr(tokens, "accent_hex", "")),
        str(getattr(tokens, "font_family_qss", "")),
        str(getattr(tokens, "surface_bg", "")),
        str(getattr(tokens, "surface_border", "")),
    )


class ThemeRefreshBinding(QObject):
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
        self._cleanup_in_progress = False

        try:
            target.installEventFilter(self)
        except Exception:
            pass

        try:
            qconfig.themeChanged.connect(self._on_theme_signal)
        except Exception:
            pass
        try:
            qconfig.themeColorChanged.connect(self._on_theme_signal)
        except Exception:
            pass

    def eventFilter(self, watched, event):  # noqa: N802 (Qt override)
        if self._cleanup_in_progress:
            return False
        try:
            if watched is self._target:
                event_type = event.type()
                if event_type in (
                    QEvent.Type.StyleChange,
                    QEvent.Type.PaletteChange,
                ):
                    self.request_refresh()
                elif event_type == QEvent.Type.Show:
                    QTimer.singleShot(0, self.flush_pending)
        except Exception:
            pass
        return super().eventFilter(watched, event)

    def invalidate(self) -> None:
        self._last_theme_key = None

    def request_refresh(self, *, force: bool = False) -> None:
        if self._cleanup_in_progress or self._target is None:
            return
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
        if self._cleanup_in_progress:
            return
        if not self._refresh_pending_when_hidden and not self._pending_force:
            return
        self._refresh_pending_when_hidden = False
        pending_force = bool(self._pending_force)
        self._pending_force = False
        self.request_refresh(force=pending_force)

    def _on_theme_signal(self, *_args) -> None:
        if self._cleanup_in_progress:
            return
        self.request_refresh()

    def _apply_debounced(self) -> None:
        if self._cleanup_in_progress or self._target is None:
            self._refresh_scheduled = False
            return
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

    def cleanup(self) -> None:
        if self._cleanup_in_progress:
            return
        self._cleanup_in_progress = True
        self._refresh_scheduled = False
        self._refresh_pending_when_hidden = False
        self._pending_force = False

        target = self._target
        if target is not None:
            try:
                target.removeEventFilter(self)
            except Exception:
                pass

        if qconfig is not None:
            try:
                qconfig.themeChanged.disconnect(self._on_theme_signal)
            except Exception:
                pass
            try:
                qconfig.themeColorChanged.disconnect(self._on_theme_signal)
            except Exception:
                pass

        self._target = None


def flush_pending_theme_refreshes(root) -> int:
    """Сбрасывает отложенные theme-refresh привязки внутри видимого окна."""
    if root is None:
        return 0

    try:
        bindings = list(root.findChildren(ThemeRefreshBinding))
    except Exception:
        bindings = []

    flushed = 0
    for binding in bindings:
        try:
            binding.flush_pending()
            flushed += 1
        except Exception:
            pass
    return flushed
