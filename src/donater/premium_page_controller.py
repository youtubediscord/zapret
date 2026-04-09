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


@dataclass(slots=True)
class PremiumStatusCheckPlan:
    valid: bool
    is_premium: bool
    is_linked: bool
    hide_activation_section: bool
    stop_autopoll: bool
    sync_autopoll: bool
    emitted_is_premium: bool
    emitted_days: int
    badge_plan: PremiumStatusBadgePlan
    days_plan: PremiumDaysPlan


@dataclass(slots=True)
class PremiumPairCodeStartPlan:
    activation_in_progress: bool
    stop_autopoll: bool
    clear_key_input: bool
    activate_enabled: bool
    activate_text_key: str
    activate_text_default: str
    activation_status_plan: PremiumActivationStatusPlan


@dataclass(slots=True)
class PremiumPairCodeResultPlan:
    activation_in_progress: bool
    activate_enabled: bool
    activate_text_key: str
    activate_text_default: str
    clear_key_input: bool
    key_input_text: str
    copy_to_clipboard: bool
    activation_status_plan: PremiumActivationStatusPlan
    update_device_info: bool
    start_autopoll: bool
    stop_autopoll: bool


@dataclass(slots=True)
class PremiumConnectionTestPlan:
    connection_in_progress: bool
    test_enabled: bool
    test_text_key: str
    test_text_default: str
    server_status_plan: PremiumServerStatusPlan


@dataclass(slots=True)
class PremiumResetPlan:
    clear_pair_input: bool
    activation_status_plan: PremiumActivationStatusPlan
    badge_plan: PremiumStatusBadgePlan
    days_plan: PremiumDaysPlan
    show_activation_section: bool
    stop_autopoll: bool
    emitted_is_premium: bool
    emitted_days: int


@dataclass(slots=True)
class PremiumDeviceInfoPlan:
    device_id_text_key: str
    device_id_text_default: str
    device_id_kwargs: dict
    saved_key_text: str
    last_check_text_key: str
    last_check_text_default: str
    last_check_kwargs: dict


@dataclass(slots=True)
class PremiumAutopollPlan:
    can_poll: bool
    start_timer: bool
    stop_timer: bool


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

    def build_status_check_plan(self, result, *, linked_hint: str, unlinked_hint: str, error_text: str = "") -> PremiumStatusCheckPlan:
        if result is None or not isinstance(result, dict):
            return PremiumStatusCheckPlan(
                valid=False,
                is_premium=False,
                is_linked=False,
                hide_activation_section=False,
                stop_autopoll=False,
                sync_autopoll=False,
                emitted_is_premium=False,
                emitted_days=0,
                badge_plan=PremiumStatusBadgePlan(
                    status="expired",
                    text_key="page.premium.status.error.title",
                    text_default="Ошибка",
                    text_kwargs={},
                    details_key="page.premium.status.error.invalid_response",
                    details_default="Неверный ответ сервера",
                    details_kwargs={},
                ),
                days_plan=PremiumDaysPlan(kind="none", value=0),
            )

        if "activated" not in result:
            return PremiumStatusCheckPlan(
                valid=False,
                is_premium=False,
                is_linked=False,
                hide_activation_section=False,
                stop_autopoll=False,
                sync_autopoll=False,
                emitted_is_premium=False,
                emitted_days=0,
                badge_plan=PremiumStatusBadgePlan(
                    status="expired",
                    text_key="page.premium.status.error.title",
                    text_default="Ошибка",
                    text_kwargs={},
                    details_key="page.premium.status.error.incomplete_response",
                    details_default="Неполный ответ",
                    details_kwargs={},
                ),
                days_plan=PremiumDaysPlan(kind="none", value=0),
            )

        is_premium = bool(result.get("is_premium", result.get("activated")))
        is_linked = bool(result.get("found"))

        if is_premium:
            days_remaining = result.get("days_remaining")
            if days_remaining is None:
                badge_plan = PremiumStatusBadgePlan(
                    status="active",
                    text_key="page.premium.status.active.title",
                    text_default="Подписка активна",
                    text_kwargs={},
                    details_key=None,
                    details_default="",
                    details_kwargs={},
                )
                details = result.get("status", "")
                badge_plan = PremiumStatusBadgePlan(
                    status=badge_plan.status,
                    text_key=badge_plan.text_key,
                    text_default=badge_plan.text_default,
                    text_kwargs=badge_plan.text_kwargs,
                    details_key=None,
                    details_default=str(details or ""),
                    details_kwargs={},
                )
                return PremiumStatusCheckPlan(
                    valid=True,
                    is_premium=True,
                    is_linked=True,
                    hide_activation_section=True,
                    stop_autopoll=True,
                    sync_autopoll=False,
                    emitted_is_premium=True,
                    emitted_days=0,
                    badge_plan=badge_plan,
                    days_plan=PremiumDaysPlan(kind="none", value=0),
                )

            if days_remaining > 30:
                status = "active"
                title_key = "page.premium.status.active.title"
                title_default = "Подписка активна"
                days_kind = "normal"
            elif days_remaining > 7:
                status = "warning"
                title_key = "page.premium.status.active.title"
                title_default = "Подписка активна"
                days_kind = "warning"
            else:
                status = "warning"
                title_key = "page.premium.status.expiring_soon.title"
                title_default = "Скоро истекает!"
                days_kind = "urgent"

            return PremiumStatusCheckPlan(
                valid=True,
                is_premium=True,
                is_linked=True,
                hide_activation_section=True,
                stop_autopoll=True,
                sync_autopoll=False,
                emitted_is_premium=True,
                emitted_days=int(days_remaining),
                badge_plan=PremiumStatusBadgePlan(
                    status=status,
                    text_key=title_key,
                    text_default=title_default,
                    text_kwargs={},
                    details_key="page.premium.status.active.days_left",
                    details_default="Осталось {days} дней",
                    details_kwargs={"days": days_remaining},
                ),
                days_plan=PremiumDaysPlan(kind=days_kind, value=int(days_remaining)),
            )

        details = result.get("status", "") or (linked_hint if is_linked else unlinked_hint)
        return PremiumStatusCheckPlan(
            valid=True,
            is_premium=False,
            is_linked=is_linked,
            hide_activation_section=bool(is_linked),
            stop_autopoll=bool(is_linked),
            sync_autopoll=not bool(is_linked),
            emitted_is_premium=False,
            emitted_days=0,
            badge_plan=PremiumStatusBadgePlan(
                status="expired",
                text_key="page.premium.status.inactive.title",
                text_default="Подписка не активна",
                text_kwargs={},
                details_key=None,
                details_default=str(details or ""),
                details_kwargs={},
            ),
            days_plan=PremiumDaysPlan(kind="none", value=0),
        )

    def build_pair_code_start_plan(self) -> PremiumPairCodeStartPlan:
        return PremiumPairCodeStartPlan(
            activation_in_progress=True,
            stop_autopoll=True,
            clear_key_input=True,
            activate_enabled=False,
            activate_text_key="page.premium.button.create_code.loading",
            activate_text_default="Создание...",
            activation_status_plan=self.build_activation_status_plan(
                text_key="page.premium.activation.progress.creating_code",
                text_default="🔄 Создаю код...",
            ),
        )

    def build_pair_code_result_plan(self, result) -> PremiumPairCodeResultPlan:
        try:
            success, message, code = result
        except Exception:
            success, message, code = False, "Неверный ответ", None

        if success:
            return PremiumPairCodeResultPlan(
                activation_in_progress=False,
                activate_enabled=True,
                activate_text_key="page.premium.button.create_code",
                activate_text_default="Создать код",
                clear_key_input=False,
                key_input_text=str(code or ""),
                copy_to_clipboard=bool(code),
                activation_status_plan=self.build_activation_status_plan(
                    text_key="page.premium.activation.success.code_created",
                    text_default="✅ Код создан и скопирован. Отправьте его боту в Telegram.",
                ),
                update_device_info=True,
                start_autopoll=True,
                stop_autopoll=False,
            )

        return PremiumPairCodeResultPlan(
            activation_in_progress=False,
            activate_enabled=True,
            activate_text_key="page.premium.button.create_code",
            activate_text_default="Создать код",
            clear_key_input=True,
            key_input_text="",
            copy_to_clipboard=False,
            activation_status_plan=self.build_activation_status_plan(
                text=f"❌ {message}",
            ),
            update_device_info=True,
            start_autopoll=False,
            stop_autopoll=True,
        )

    def build_pair_code_error_plan(self, error: str) -> PremiumPairCodeResultPlan:
        return PremiumPairCodeResultPlan(
            activation_in_progress=False,
            activate_enabled=True,
            activate_text_key="page.premium.button.create_code",
            activate_text_default="Создать код",
            clear_key_input=True,
            key_input_text="",
            copy_to_clipboard=False,
            activation_status_plan=self.build_activation_status_plan(
                text_key="page.premium.activation.error.generic",
                text_default="❌ Ошибка: {error}",
                text_kwargs={"error": error},
            ),
            update_device_info=True,
            start_autopoll=False,
            stop_autopoll=True,
        )

    def build_connection_test_start_plan(self, *, checker_ready: bool) -> PremiumConnectionTestPlan:
        if not checker_ready:
            return PremiumConnectionTestPlan(
                connection_in_progress=False,
                test_enabled=True,
                test_text_key="page.premium.button.test_connection",
                test_text_default="Проверить соединение",
                server_status_plan=self.build_server_status_plan(
                    mode="init_error",
                    message="",
                    success=False,
                ),
            )

        return PremiumConnectionTestPlan(
            connection_in_progress=True,
            test_enabled=False,
            test_text_key="page.premium.button.test_connection.loading",
            test_text_default="Проверка...",
            server_status_plan=self.build_server_status_plan(
                mode="checking",
                message="",
                success=None,
            ),
        )

    def build_connection_test_result_plan(self, result) -> PremiumConnectionTestPlan:
        try:
            success, message = result
        except Exception:
            success, message = False, "Неверный ответ"

        return PremiumConnectionTestPlan(
            connection_in_progress=False,
            test_enabled=True,
            test_text_key="page.premium.button.test_connection",
            test_text_default="Проверить соединение",
            server_status_plan=self.build_server_status_plan(
                mode="result",
                message=str(message or ""),
                success=bool(success),
            ),
        )

    def build_connection_test_error_plan(self, error: str) -> PremiumConnectionTestPlan:
        return PremiumConnectionTestPlan(
            connection_in_progress=False,
            test_enabled=True,
            test_text_key="page.premium.button.test_connection",
            test_text_default="Проверить соединение",
            server_status_plan=self.build_server_status_plan(
                mode="error",
                message=str(error or ""),
                success=False,
            ),
        )

    @staticmethod
    def reset_premium_storage(checker, storage) -> None:
        try:
            if checker:
                checker.clear_saved_key()
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

    def build_reset_plan(self) -> PremiumResetPlan:
        return PremiumResetPlan(
            clear_pair_input=True,
            activation_status_plan=self.build_activation_status_plan(text=""),
            badge_plan=PremiumStatusBadgePlan(
                status="expired",
                text_key="page.premium.status.reset.title",
                text_default="Привязка сброшена",
                text_kwargs={},
                details_key="page.premium.status.reset.details",
                details_default="Создайте новый код для привязки",
                details_kwargs={},
            ),
            days_plan=PremiumDaysPlan(kind="none", value=0),
            show_activation_section=True,
            stop_autopoll=True,
            emitted_is_premium=False,
            emitted_days=0,
        )

    @staticmethod
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

    def build_device_info_plan(
        self,
        *,
        device_id: str,
        device_token,
        pair_code,
        last_check,
        token_present_text: str,
        token_absent_text: str,
        pair_template_text: str,
    ) -> PremiumDeviceInfoPlan:
        parts = [
            token_present_text if device_token else token_absent_text,
        ]
        if pair_code:
            parts.append(pair_template_text.format(pair_code=pair_code))

        if last_check:
            return PremiumDeviceInfoPlan(
                device_id_text_key="page.premium.label.device_id.value",
                device_id_text_default="ID устройства: {device_id}...",
                device_id_kwargs={"device_id": device_id[:16]},
                saved_key_text=" | ".join(parts),
                last_check_text_key="page.premium.label.last_check.value",
                last_check_text_default="Последняя проверка: {date}",
                last_check_kwargs={"date": last_check.strftime('%d.%m.%Y %H:%M')},
            )

        return PremiumDeviceInfoPlan(
            device_id_text_key="page.premium.label.device_id.value",
            device_id_text_default="ID устройства: {device_id}...",
            device_id_kwargs={"device_id": device_id[:16]},
            saved_key_text=" | ".join(parts),
            last_check_text_key="page.premium.label.last_check.none",
            last_check_text_default="Последняя проверка: —",
            last_check_kwargs={},
        )

    @staticmethod
    def build_pairing_autopoll_plan(
        *,
        checker_ready: bool,
        storage_ready: bool,
        page_visible: bool,
        activation_in_progress: bool,
        connection_test_in_progress: bool,
        worker_running: bool,
        has_device_token: bool,
        has_pending_pair_code: bool,
    ) -> PremiumAutopollPlan:
        can_poll = (
            checker_ready
            and storage_ready
            and page_visible
            and not activation_in_progress
            and not connection_test_in_progress
            and not worker_running
            and not has_device_token
            and has_pending_pair_code
        )
        return PremiumAutopollPlan(
            can_poll=can_poll,
            start_timer=can_poll,
            stop_timer=not can_poll,
        )
