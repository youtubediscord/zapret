"""Безопросная доставка текущего журнала в Qt-интерфейс."""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from log.log import LiveLogSnapshot, global_logger


class LiveLogBridge(QObject):
    """Переводит уведомления фонового писателя в очередь событий Qt."""

    new_text = pyqtSignal(int, str)

    def __init__(
        self,
        *,
        after_sequence: int | None,
        on_new_text,
        max_snapshot_chars: int = 1024 * 1024,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._subscription_token: int | None = None
        self.new_text.connect(on_new_text)
        token, snapshot = global_logger.open_live_subscription(
            self._forward_text,
            after_sequence=after_sequence,
            max_chars=max_snapshot_chars,
        )
        self._subscription_token = token
        self.snapshot: LiveLogSnapshot = snapshot

    def _forward_text(self, sequence: int, text: str) -> None:
        try:
            self.new_text.emit(int(sequence), str(text or ""))
        except RuntimeError:
            # QObject уже удаляется; подписка будет снята в close()/cleanup().
            pass

    def close(self) -> None:
        token = self._subscription_token
        self._subscription_token = None
        if token is not None:
            global_logger.close_live_subscription(token)
        try:
            self.new_text.disconnect()
        except (TypeError, RuntimeError):
            pass


__all__ = ["LiveLogBridge"]
