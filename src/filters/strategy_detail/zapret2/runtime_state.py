from __future__ import annotations

from dataclasses import dataclass


class StrategyDetailTargetPayloadRuntime:
    def __init__(self) -> None:
        self.pending_target_key: str | None = None
        self.worker = None
        self.request_id = 0
        self.request_started_at = None

    def current_or_pending_target_key(self, current_target_key: str | None) -> str:
        return str(self.pending_target_key or current_target_key or "").strip().lower()

    def remember_pending_target(self, target_key: str | None) -> None:
        normalized_key = str(target_key or "").strip().lower()
        self.pending_target_key = normalized_key or None

    def clear_pending_target(self) -> None:
        self.pending_target_key = None

    def take_pending_target_if_ready(self, *, is_visible: bool, content_built: bool) -> str | None:
        pending_target_key = str(self.pending_target_key or "").strip().lower()
        if not pending_target_key:
            return None
        if not is_visible or not content_built:
            return None
        self.pending_target_key = None
        return pending_target_key

    def restore_pending_target(self, target_key: str | None) -> None:
        self.remember_pending_target(target_key)

    def current_request_id(self) -> int:
        return int(self.request_id)

    def register_request(self, *, request_id: int, started_at, worker) -> None:
        self.request_id = int(request_id)
        self.request_started_at = started_at
        self.worker = worker


class StrategyDetailPresetRefreshRuntime:
    def __init__(self) -> None:
        self.pending = False
        self.suppress_next = False

    def mark_pending(self) -> None:
        self.pending = True

    def clear_pending(self) -> None:
        self.pending = False

    def consume_pending(self) -> bool:
        if not self.pending:
            return False
        self.pending = False
        return True

    def mark_suppressed(self) -> None:
        self.suppress_next = True

    def set_suppressed(self, enabled: bool) -> None:
        self.suppress_next = bool(enabled)

    def consume_suppressed(self) -> bool:
        if not self.suppress_next:
            return False
        self.suppress_next = False
        return True


@dataclass(slots=True)
class StrategyDetailPendingStrategyItem:
    strategy_id: str
    name: str
    arg_text: str
    is_custom: bool = False


class StrategyDetailStrategiesLoadRuntime:
    def __init__(self) -> None:
        self.timer = None
        self.generation = 0
        self.pending_items: list[StrategyDetailPendingStrategyItem] = []
        self.pending_index = 0

    def bump_generation(self) -> int:
        self.generation += 1
        return int(self.generation)

    def stop_timer(self, *, delete_later: bool) -> None:
        timer = self.timer
        if timer is None:
            return
        try:
            timer.stop()
        except Exception:
            pass
        if delete_later:
            try:
                timer.deleteLater()
            except Exception:
                pass
            self.timer = None

    def reset(self, *, delete_later: bool) -> None:
        self.bump_generation()
        self.stop_timer(delete_later=delete_later)
        self.pending_items = []
        self.pending_index = 0

    def set_pending_items(self, items: list[StrategyDetailPendingStrategyItem]) -> None:
        self.pending_items = list(items or [])
        self.pending_index = 0

    def ensure_timer(self, *, parent, timeout_callback):
        if self.timer is not None:
            return self.timer
        from PyQt6.QtCore import QTimer

        timer = QTimer(parent)
        timer.timeout.connect(timeout_callback)
        self.timer = timer
        return timer

    def total_items(self) -> int:
        return len(self.pending_items or [])

    def start_index(self) -> int:
        return int(self.pending_index or 0)

    def item_at(self, index: int) -> StrategyDetailPendingStrategyItem:
        return self.pending_items[index]

    def advance_to(self, index: int) -> None:
        self.pending_index = int(index)


def create_target_payload_runtime() -> StrategyDetailTargetPayloadRuntime:
    return StrategyDetailTargetPayloadRuntime()


def create_preset_refresh_runtime() -> StrategyDetailPresetRefreshRuntime:
    return StrategyDetailPresetRefreshRuntime()


def create_strategies_load_runtime() -> StrategyDetailStrategiesLoadRuntime:
    return StrategyDetailStrategiesLoadRuntime()
