from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import donater.commands as premium_commands


@dataclass(slots=True)
class PremiumFeature:
    _thread_parent: Any = None
    _ui_actions: Any = None
    _subscription_manager: Any = None
    _checker: Any = None
    _storage: Any = None

    def _ensure_subscription_manager(self):
        if self._subscription_manager is None:
            self._subscription_manager = premium_commands.create_subscription_manager(
                thread_parent=self._thread_parent,
                ui_actions=self._ui_actions,
            )
        return self._subscription_manager

    def prepare_subscription(self) -> None:
        self._ensure_subscription_manager()

    def initialize_subscription(self) -> None:
        premium_commands.initialize_subscription_manager(self._ensure_subscription_manager())

    def cleanup_subscription(self) -> None:
        manager = self._subscription_manager
        self._subscription_manager = None
        premium_commands.cleanup_subscription_manager(manager)

    def ensure_checker_ready(self) -> bool:
        if self._checker is not None and self._storage is not None:
            return True
        bundle = premium_commands.resolve_checker_bundle()
        self._checker = bundle.checker
        self._storage = bundle.storage
        return bool(bundle.init_ok and self._checker is not None and self._storage is not None)

    def is_checker_ready(self) -> bool:
        return bool(self._checker)

    def is_storage_ready(self) -> bool:
        return bool(self._storage)

    def _require_checker(self):
        if self.ensure_checker_ready() and self._checker is not None:
            return self._checker
        raise RuntimeError("premium checker init failed")

    def open_extend_bot(self):
        return premium_commands.open_extend_bot()

    def create_premium_worker_thread(self, task):
        return premium_commands.create_premium_worker_thread(task)

    def start_pairing(self):
        return premium_commands.start_pairing(self._require_checker())

    def check_device_activation(self):
        return premium_commands.check_device_activation(self._require_checker())

    def reset_premium_storage(self):
        self.ensure_checker_ready()
        premium_commands.reset_premium_storage(self._checker, self._storage)
        self._checker = None
        self._storage = None

    def read_pairing_snapshot(self, *, current_time: int):
        self.ensure_checker_ready()
        return premium_commands.read_pairing_snapshot(self._storage, current_time=int(current_time))

    def read_device_info_snapshot(self, *, current_time: int):
        if not self.ensure_checker_ready():
            return None
        snapshot = premium_commands.read_device_storage_snapshot(
            self._storage,
            current_time=int(current_time),
        )
        snapshot["device_id"] = str(getattr(self._checker, "device_id", "") or "")
        return snapshot

    def test_connection(self):
        return self._require_checker().test_connection()

    def get_premium_state(self, *, use_cache: bool = True):
        return premium_commands.get_premium_state(use_cache=use_cache)

    def apply_subscription_state_to_ui_store(self, *, is_premium: bool, days_remaining: int | None) -> None:
        premium_commands.apply_premium_state_to_store(
            ui_state_store=self._ui_actions.ui_state_store,
            state=premium_commands.PremiumState(
                is_premium=bool(is_premium),
                days_remaining=int(days_remaining or 0) if is_premium else None,
                source="premium_page",
            ),
        )


def build_premium_feature(*, host, ui_state_store) -> PremiumFeature:
    from donater.subscription_ui import SubscriptionUiActions

    return PremiumFeature(
        _thread_parent=host,
        _ui_actions=SubscriptionUiActions(
            set_status=host.set_status,
            ui_state_store=ui_state_store,
            update_title_badge=host.update_subscription_title_badge,
            init_holiday_effects=lambda effects_allowed: host.init_holiday_effects_from_settings(
                effects_allowed=effects_allowed,
            ),
            mark_startup_ready=host.mark_startup_subscription_ready,
        ),
    )
