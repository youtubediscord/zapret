from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class PremiumStatusBadgePlan:
    status: str
    text_key: str
    text_default: str
    text_kwargs: dict
    details_key: str | None
    details_default: str
    details_kwargs: dict


@dataclass(slots=True)
class PremiumDaysPlan:
    kind: str
    value: int


@dataclass(slots=True)
class PremiumActivationStatusPlan:
    text_key: str | None
    text_default: str
    text_kwargs: dict
    text: str


@dataclass(slots=True)
class PremiumServerStatusPlan:
    mode: str
    message: str
    success: bool | None


@dataclass(slots=True)
class PremiumCheckerInitResult:
    checker: object | None
    storage: object | None
    init_ok: bool


class PremiumPageController:
    @staticmethod
    def resolve_checker_bundle() -> PremiumCheckerInitResult:
        try:
            from donater.donate import DonateChecker
            from donater.storage import PremiumStorage

            return PremiumCheckerInitResult(
                checker=DonateChecker(),
                storage=PremiumStorage,
                init_ok=True,
            )
        except Exception:
            return PremiumCheckerInitResult(
                checker=None,
                storage=None,
                init_ok=False,
            )

    @staticmethod
    def create_worker_thread(target, args=None):
        worker_path = Path(__file__).with_name("premium_worker.py")
        spec = importlib.util.spec_from_file_location(
            "_premium_worker_runtime",
            worker_path,
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("premium worker module load failed")
        module = importlib.util.module_from_spec(spec)
        sys.modules.setdefault(spec.name, module)
        spec.loader.exec_module(module)
        return module.PremiumWorkerThread(target, args=args)

    @staticmethod
    def build_subscription_snapshot_plan(is_premium: bool, days_remaining: int | None) -> tuple[PremiumStatusBadgePlan, PremiumDaysPlan, int]:
        if is_premium:
            if days_remaining is None:
                return (
                    PremiumStatusBadgePlan(
                        status="active",
                        text_key="page.premium.status.active.title",
                        text_default="Premium активен",
                        text_kwargs={},
                        details_key=None,
                        details_default="",
                        details_kwargs={},
                    ),
                    PremiumDaysPlan(kind="none", value=0),
                    0,
                )
            if days_remaining > 30:
                return (
                    PremiumStatusBadgePlan(
                        status="active",
                        text_key="page.premium.status.active.title",
                        text_default="Premium активен",
                        text_kwargs={},
                        details_key="page.premium.status.active.days_left",
                        details_default="Осталось {days} дней",
                        details_kwargs={"days": days_remaining},
                    ),
                    PremiumDaysPlan(kind="normal", value=int(days_remaining)),
                    int(days_remaining),
                )
            if days_remaining > 7:
                return (
                    PremiumStatusBadgePlan(
                        status="warning",
                        text_key="page.premium.status.active.title",
                        text_default="Premium активен",
                        text_kwargs={},
                        details_key="page.premium.status.active.days_left",
                        details_default="Осталось {days} дней",
                        details_kwargs={"days": days_remaining},
                    ),
                    PremiumDaysPlan(kind="warning", value=int(days_remaining)),
                    int(days_remaining),
                )
            return (
                PremiumStatusBadgePlan(
                    status="expired",
                    text_key="page.premium.status.expiring_soon.title",
                    text_default="Premium скоро закончится",
                    text_kwargs={},
                    details_key="page.premium.status.active.days_left",
                    details_default="Осталось {days} дней",
                    details_kwargs={"days": days_remaining},
                ),
                PremiumDaysPlan(kind="urgent", value=int(days_remaining)),
                int(days_remaining),
            )

        return (
            PremiumStatusBadgePlan(
                status="neutral",
                text_key="page.premium.status.inactive.title",
                text_default="Подписка не активирована",
                text_kwargs={},
                details_key=None,
                details_default="",
                details_kwargs={},
            ),
            PremiumDaysPlan(kind="none", value=0),
            0,
        )

    @staticmethod
    def build_activation_status_plan(
        *,
        text: str | None = None,
        text_key: str | None = None,
        text_default: str = "",
        text_kwargs: dict | None = None,
    ) -> PremiumActivationStatusPlan:
        return PremiumActivationStatusPlan(
            text_key=text_key,
            text_default=text_default,
            text_kwargs=dict(text_kwargs or {}),
            text=str(text or ""),
        )

    @staticmethod
    def build_server_status_plan(*, mode: str, message: str = "", success: bool | None = None) -> PremiumServerStatusPlan:
        return PremiumServerStatusPlan(
            mode=str(mode or ""),
            message=str(message or ""),
            success=success,
        )
