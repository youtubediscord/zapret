from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any


@dataclass(frozen=True, slots=True)
class PremiumPageData:
    device_info: dict | None
    premium_state: Any | None


@dataclass(slots=True)
class PremiumFeature:
    _thread_parent: Any = None
    _deps: Any = None
    _ui_state_store: Any = None
    _ui_actions: Any = None
    _subscription_manager: Any = None
    _checker: Any = None
    _storage: Any = None
    _warmed_page_data: PremiumPageData | None = None

    @staticmethod
    def _commands():
        import donater.commands as premium_commands

        return premium_commands

    def _ensure_ui_actions(self):
        if self._ui_actions is None:
            from donater.subscription_ui import SubscriptionUiActions

            deps = self._deps
            self._ui_actions = SubscriptionUiActions(
                set_status=deps.set_status,
                ui_state_store=self._ui_state_store,
                update_title_badge=deps.update_title_badge,
                init_holiday_effects=deps.init_holiday_effects,
                mark_startup_ready=deps.mark_startup_ready,
            )
        return self._ui_actions

    def _ensure_subscription_manager(self):
        if self._subscription_manager is None:
            self._subscription_manager = self._commands().create_subscription_manager(
                thread_parent=self._thread_parent,
                ui_actions=self._ensure_ui_actions(),
            )
        return self._subscription_manager

    def prepare_subscription(self) -> None:
        self._ensure_subscription_manager()

    def initialize_subscription(self) -> None:
        self._commands().initialize_subscription_manager(self._ensure_subscription_manager())

    def cleanup_subscription(self) -> None:
        manager = self._subscription_manager
        self._subscription_manager = None
        self._commands().cleanup_subscription_manager(manager)

    def ensure_checker_ready(self) -> bool:
        if self._checker is not None and self._storage is not None:
            return True
        bundle = self._commands().resolve_checker_bundle()
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
        return self._commands().open_extend_bot()

    def create_premium_worker_thread(self, task):
        return self._commands().create_premium_worker_thread(task)

    def start_pairing(self):
        return self._commands().start_pairing(self._require_checker())

    def check_device_activation(self):
        return self._commands().check_device_activation(self._require_checker())

    def reset_premium_storage(self):
        self.ensure_checker_ready()
        self._commands().reset_premium_storage(self._checker, self._storage)
        self._checker = None
        self._storage = None

    def read_pairing_snapshot(self, *, current_time: int):
        self.ensure_checker_ready()
        return self._commands().read_pairing_snapshot(self._storage, current_time=int(current_time))

    def read_device_info_snapshot(self, *, current_time: int):
        if not self.ensure_checker_ready():
            return None
        snapshot = self._commands().read_device_storage_snapshot(
            self._storage,
            current_time=int(current_time),
        )
        snapshot["device_id"] = str(getattr(self._checker, "device_id", "") or "")
        return snapshot

    def test_connection(self):
        return self._require_checker().test_connection()

    def get_premium_state(self, *, use_cache: bool = True):
        return self._commands().get_premium_state(use_cache=use_cache)

    def warm_page_data_cache(self) -> PremiumPageData:
        current_time = int(time.time())
        device_info = self.read_device_info_snapshot(current_time=current_time)
        premium_state = None
        try:
            premium_state = self.get_premium_state(use_cache=True)
            self.apply_subscription_state_to_ui_store(
                is_premium=bool(premium_state.is_premium),
                days_remaining=premium_state.days_remaining,
            )
        except Exception:
            premium_state = None

        self._warmed_page_data = PremiumPageData(
            device_info=device_info,
            premium_state=premium_state,
        )
        return self._warmed_page_data

    def consume_warmed_page_data(self) -> PremiumPageData | None:
        warmed = self._warmed_page_data
        self._warmed_page_data = None
        return warmed

    def apply_subscription_state_to_ui_store(self, *, is_premium: bool, days_remaining: int | None) -> None:
        premium_commands = self._commands()
        premium_commands.apply_premium_state_to_store(
            ui_state_store=self._ui_state_store or self._ensure_ui_actions().ui_state_store,
            state=premium_commands.PremiumState(
                is_premium=bool(is_premium),
                days_remaining=int(days_remaining or 0) if is_premium else None,
                source="premium_page",
            ),
        )


def build_premium_feature(*, deps, ui_state_store) -> PremiumFeature:
    return PremiumFeature(
        _thread_parent=deps.thread_parent,
        _deps=deps,
        _ui_state_store=ui_state_store,
    )
