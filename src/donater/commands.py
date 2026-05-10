from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from donater.state import PremiumState, premium_state_from_subscription_info


@dataclass(frozen=True, slots=True)
class PremiumCheckerBundle:
    checker: object | None
    storage: object | None
    init_ok: bool


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
