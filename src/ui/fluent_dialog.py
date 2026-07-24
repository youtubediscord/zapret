"""Безопасный жизненный цикл диалогов qfluentwidgets."""

from __future__ import annotations

from qfluentwidgets import (
    MessageBox as _QFluentMessageBox,
    MessageBoxBase as _QFluentMessageBoxBase,
)


class _ManagedMaskDialogLifecycle:
    """Снимает закрытый диалог с фильтра событий родительского окна."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mask_event_filter_host = self.window()

    def _detach_mask_event_filter(self) -> None:
        host = getattr(self, "_mask_event_filter_host", None)
        self._mask_event_filter_host = None
        if host is None:
            return

        try:
            host.removeEventFilter(self)
        except RuntimeError:
            # Родительское окно уже могло быть уничтожено вместе с диалогом.
            pass

    def _onDone(self, code):  # noqa: N802 (qfluentwidgets API)
        self._detach_mask_event_filter()
        return super()._onDone(code)

    def exec(self) -> int:
        try:
            return super().exec()
        finally:
            self._detach_mask_event_filter()


class MessageBoxBase(_ManagedMaskDialogLifecycle, _QFluentMessageBoxBase):
    """Основа проектных fluent-диалогов с корректным завершением."""


class MessageBox(_ManagedMaskDialogLifecycle, _QFluentMessageBox):
    """Стандартный fluent-диалог с корректным завершением."""


__all__ = ["MessageBox", "MessageBoxBase"]
