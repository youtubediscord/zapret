from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from donater.state import PremiumState, premium_state_from_subscription_info


@dataclass(frozen=True, slots=True)
class PremiumCheckerBundle:
    checker: object | None
    storage: object | None
    init_ok: bool


@dataclass(frozen=True, slots=True)
class PremiumActionResult:
    ok: bool
    message: str


def get_premium_checker():
    from donater.service import get_premium_service

    return get_premium_service()


def resolve_checker_bundle() -> PremiumCheckerBundle:
    try:
        from donater.storage import PremiumStorage

        return PremiumCheckerBundle(
            checker=get_premium_checker(),
            storage=PremiumStorage,
            init_ok=True,
        )
    except Exception:
        return PremiumCheckerBundle(checker=None, storage=None, init_ok=False)


def create_subscription_manager(*, thread_parent, ui_actions):
    from donater.subscription_manager import SubscriptionManager

    return SubscriptionManager(thread_parent=thread_parent, ui_actions=ui_actions)


def initialize_subscription_manager(subscription_manager) -> None:
    if subscription_manager is not None:
        subscription_manager.initialize_async()


def cleanup_subscription_manager(subscription_manager) -> None:
    if subscription_manager is not None:
        subscription_manager.cleanup()


def start_pairing(checker: object | None = None, *, device_name: str | None = None):
    service = checker if checker is not None else get_premium_checker()
    return service.pair_start(device_name=device_name)


def check_device_activation(
    checker: object | None = None,
    *,
    use_cache: bool = False,
    automatic: bool = False,
) -> dict[str, Any]:
    service = checker if checker is not None else get_premium_checker()
    return dict(service.check_device_activation(use_cache=use_cache, automatic=automatic) or {})


def get_premium_state(
    checker: object | None = None,
    *,
    use_cache: bool = True,
    automatic: bool = False,
) -> PremiumState:
    service = checker if checker is not None else get_premium_checker()
    info = dict(service.get_full_subscription_info(use_cache=use_cache, automatic=automatic) or {})
    return premium_state_from_subscription_info(info)


def apply_premium_state_to_store(*, ui_state_store, state: PremiumState) -> None:
    from donater.subscription_ui import apply_premium_state_to_store as apply_state

    apply_state(ui_state_store=ui_state_store, state=state)


def create_premium_worker_thread(target, args=None):
    from donater.premium_worker import PremiumWorkerThread

    return PremiumWorkerThread(target, args=args)


def reset_premium_storage(checker, storage) -> None:
    try:
        if checker:
            checker.clear_activation()
            return
    except Exception:
        pass

    if storage:
        try:
            storage.clear_device_token()
            storage.clear_premium_cache()
            storage.clear_pair_code()
            storage.save_last_check()
        except Exception:
            pass


def read_device_storage_snapshot(storage, *, current_time: int) -> dict:
    if storage is None:
        return {
            "device_token": None,
            "pair_code": None,
            "last_check": None,
        }

    device_token = None
    pair_code = None
    pair_expires_at = None
    last_check = None

    try:
        device_token = storage.get_device_token()
    except Exception:
        pass

    try:
        pair_code = storage.get_pair_code()
        pair_expires_at = storage.get_pair_expires_at()
    except Exception:
        pass

    if pair_code and pair_expires_at:
        try:
            if int(pair_expires_at) < int(current_time):
                storage.clear_pair_code()
                pair_code = None
        except Exception:
            pass

    try:
        last_check = storage.get_last_check()
    except Exception:
        pass

    return {
        "device_token": device_token,
        "pair_code": pair_code,
        "last_check": last_check,
    }


def read_pairing_snapshot(storage, *, current_time: int) -> dict:
    if storage is None:
        return {
            "has_device_token": False,
            "has_pending_pair_code": False,
        }

    has_device_token = False
    has_pending_pair_code = False
    try:
        has_device_token = bool(storage.get_device_token())
    except Exception:
        has_device_token = False

    try:
        pair_code = storage.get_pair_code()
        pair_expires_at = storage.get_pair_expires_at()
        has_pending_pair_code = bool(pair_code and pair_expires_at and int(pair_expires_at) >= int(current_time))
    except Exception:
        has_pending_pair_code = False

    return {
        "has_device_token": has_device_token,
        "has_pending_pair_code": has_pending_pair_code,
    }


def open_extend_bot() -> PremiumActionResult:
    try:
        from config.telegram_links import open_telegram_link

        open_telegram_link("zapretvpns_bot")
        return PremiumActionResult(ok=True, message="zapretvpns_bot")
    except Exception:
        try:
            import webbrowser

            webbrowser.open("https://t.me/zapretvpns_bot")
            return PremiumActionResult(ok=True, message="https://t.me/zapretvpns_bot")
        except Exception as exc:
            return PremiumActionResult(ok=False, message=str(exc))
