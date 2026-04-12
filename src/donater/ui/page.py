# donater/ui/page.py
"""Страница управления Premium подпиской"""

import time

from PyQt6.QtCore import Qt, pyqtSignal, QTimer

try:
    from qfluentwidgets import (
        MessageBox, InfoBar,
        BodyLabel, SubtitleLabel,
    )
    _HAS_FLUENT = True
except ImportError:
    from PyQt6.QtWidgets import (   # type: ignore[assignment]
        QLabel as BodyLabel,
        QLabel as SubtitleLabel,
    )
    MessageBox = None
    InfoBar = None
    _HAS_FLUENT = False

from donater.premium_page_controller import PremiumPageController
from ui.pages.base_page import BasePage
from donater.ui.build import (
    build_premium_actions_section,
    build_premium_activation_section,
    build_premium_device_info_section,
)
from donater.ui.status_card import StatusCard
from donater.ui.pairing_workflow import (
    apply_pair_code_error_ui,
    apply_pair_code_result_ui,
    apply_pair_code_start_ui,
    can_poll_pairing_status,
    has_pending_pair_code,
    poll_pairing_status,
    start_pairing_status_autopoll,
    stop_pairing_status_autopoll,
    sync_pairing_status_autopoll,
    update_device_info_labels,
)
from donater.ui.page_lifecycle import (
    activate_premium_page,
    apply_premium_language,
    apply_subscription_snapshot_ui,
    bind_premium_ui_state_store,
    cleanup_premium_page,
    close_premium_page,
    handle_premium_ui_state_changed,
    hide_premium_page,
    render_activation_status_label,
    run_premium_runtime_init_once,
)
from donater.ui.status_workflow import (
    apply_connection_test_plan,
    apply_reset_plan_ui,
    apply_status_check_exception,
    apply_status_check_start_ui,
    apply_status_check_success,
    render_server_status_label,
)
from app_state.main_window_state import AppUiState, MainWindowStateStore
from ui.theme_semantic import get_semantic_palette
from ui.text_catalog import tr as tr_catalog

# ─────────────────────────────────────────────────────────────────────────────
# PremiumPage
# ─────────────────────────────────────────────────────────────────────────────

class PremiumPage(BasePage):
    """Страница управления Premium подпиской"""

    subscription_updated = pyqtSignal(bool, int)  # is_premium, days_remaining
    _PAIRING_AUTOPOLL_INTERVAL_MS = 4000

    def __init__(self, parent=None):
        super().__init__(
            "Premium",
            "Управление подпиской Zapret Premium",
            parent,
            title_key="page.premium.title",
            subtitle_key="page.premium.subtitle",
        )
        self.checker = None
        self.RegistryManager = None
        self.current_thread = None
        self._cleanup_in_progress = False
        self._activation_in_progress = False
        self._connection_test_in_progress = False
        self._server_status_mode = "checking"
        self._server_status_message = ""
        self._server_status_success = None
        self._days_state_kind = "none"
        self._days_state_value = 0
        self._status_badge_state = {
            "text": "",
            "details": "",
            "status": "neutral",
            "text_key": None,
            "text_default": "",
            "text_kwargs": {},
            "details_key": None,
            "details_default": "",
            "details_kwargs": {},
        }
        self._activation_status_state = {
            "text": "",
            "text_key": None,
            "text_default": "",
            "text_kwargs": {},
        }
        self._pairing_status_timer = QTimer(self)
        self._pairing_status_timer.setInterval(self._PAIRING_AUTOPOLL_INTERVAL_MS)
        self._pairing_status_timer.timeout.connect(self._poll_pairing_status)
        self._actions_bar = None
        self._runtime_initialized = False

        self._build_ui()
        self._ui_state_store = None
        self._ui_state_unsubscribe = None

    def _tr(self, key: str, default: str, **kwargs) -> str:
        text = tr_catalog(key, language=self._ui_language, default=default)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def _set_status_badge(
        self,
        *,
        status: str,
        text: str | None = None,
        details: str = "",
        text_key: str | None = None,
        text_default: str = "",
        text_kwargs: dict | None = None,
        details_key: str | None = None,
        details_default: str = "",
        details_kwargs: dict | None = None,
    ) -> None:
        resolved_text = text if text is not None else ""
        if text_key:
            resolved_text = self._tr(text_key, text_default, **(text_kwargs or {}))

        resolved_details = details or ""
        if details_key:
            resolved_details = self._tr(details_key, details_default, **(details_kwargs or {}))

        self._status_badge_state = {
            "text": resolved_text,
            "details": resolved_details,
            "status": status,
            "text_key": text_key,
            "text_default": text_default,
            "text_kwargs": dict(text_kwargs or {}),
            "details_key": details_key,
            "details_default": details_default,
            "details_kwargs": dict(details_kwargs or {}),
        }
        self.status_badge.set_status(resolved_text, resolved_details, status)

    def _render_status_badge(self) -> None:
        state = self._status_badge_state
        text = state.get("text") or ""
        details = state.get("details") or ""
        text_key = state.get("text_key")
        details_key = state.get("details_key")

        if text_key:
            text = self._tr(text_key, state.get("text_default") or "", **(state.get("text_kwargs") or {}))
        if details_key:
            details = self._tr(
                details_key,
                state.get("details_default") or "",
                **(state.get("details_kwargs") or {}),
            )

        self.status_badge.set_status(text, details, state.get("status") or "neutral")

    def _render_days_label(self) -> None:
        semantic = get_semantic_palette()
        kind = self._days_state_kind
        days = self._days_state_value

        if kind == "normal":
            self.days_label.setText(
                self._tr("page.premium.days_label.normal", "Осталось дней: {days}", days=days)
            )
            self.days_label.setStyleSheet(f"color: {semantic.success};")
            return
        if kind == "warning":
            self.days_label.setText(
                self._tr("page.premium.days_label.warning", "⚠️ Осталось дней: {days}", days=days)
            )
            self.days_label.setStyleSheet(f"color: {semantic.warning};")
            return
        if kind == "urgent":
            self.days_label.setText(
                self._tr("page.premium.days_label.urgent", "⚠️ Срочно продлите! Осталось: {days}", days=days)
            )
            self.days_label.setStyleSheet(f"color: {semantic.error};")
            return

        self.days_label.setText("")
        self.days_label.setStyleSheet("")

    def _set_activation_status(
        self,
        *,
        text: str | None = None,
        text_key: str | None = None,
        text_default: str = "",
        text_kwargs: dict | None = None,
    ) -> None:
        plan = PremiumPageController.build_activation_status_plan(
            text=text,
            text_key=text_key,
            text_default=text_default,
            text_kwargs=text_kwargs,
        )
        resolved_text = plan.text
        if plan.text_key:
            resolved_text = self._tr(plan.text_key, plan.text_default, **plan.text_kwargs)

        self._activation_status_state = {
            "text": resolved_text,
            "text_key": plan.text_key,
            "text_default": plan.text_default,
            "text_kwargs": dict(plan.text_kwargs),
        }
        self.activation_status.setText(resolved_text)

    def bind_ui_state_store(self, store: MainWindowStateStore) -> None:
        bind_premium_ui_state_store(
            current_store=self._ui_state_store,
            store=store,
            current_unsubscribe=self._ui_state_unsubscribe,
            set_store_fn=lambda value: setattr(self, "_ui_state_store", value),
            set_unsubscribe_fn=lambda value: setattr(self, "_ui_state_unsubscribe", value),
            on_ui_state_changed_fn=self._on_ui_state_changed,
        )

    def _on_ui_state_changed(self, state: AppUiState, _changed_fields: frozenset[str]) -> None:
        handle_premium_ui_state_changed(
            state=state,
            apply_subscription_snapshot_fn=self._apply_subscription_snapshot,
        )

    def _apply_subscription_snapshot(self, is_premium: bool, days_remaining: int | None) -> None:
        apply_subscription_snapshot_ui(
            is_premium=is_premium,
            days_remaining=days_remaining,
            build_subscription_snapshot_plan_fn=PremiumPageController.build_subscription_snapshot_plan,
            set_status_badge_fn=self._set_status_badge,
            set_days_state_kind_fn=lambda value: setattr(self, "_days_state_kind", value),
            set_days_state_value_fn=lambda value: setattr(self, "_days_state_value", value),
            render_days_label_fn=self._render_days_label,
        )

    def _render_activation_status(self) -> None:
        render_activation_status_label(
            activation_status_state=self._activation_status_state,
            tr_fn=self._tr,
            activation_status_label=self.activation_status,
        )

    def _render_server_status(self) -> None:
        render_server_status_label(
            self.server_status_label,
            tr=self._tr,
            mode=self._server_status_mode,
            message=self._server_status_message,
            success=self._server_status_success,
        )

    def _set_server_status_state(self, mode: str, message: str, success: bool | None) -> None:
        self._server_status_mode = mode
        self._server_status_message = message
        self._server_status_success = success

    def _run_runtime_init_once(self) -> None:
        run_premium_runtime_init_once(
            runtime_initialized=self._runtime_initialized,
            build_page_init_plan_fn=PremiumPageController.build_page_init_plan,
            set_runtime_initialized_fn=lambda value: setattr(self, "_runtime_initialized", value),
            init_checker_fn=self._init_checker,
            set_server_status_mode_fn=lambda value: setattr(self, "_server_status_mode", value),
            set_server_status_message_fn=lambda value: setattr(self, "_server_status_message", value),
            set_server_status_success_fn=lambda value: setattr(self, "_server_status_success", value),
            render_server_status_fn=self._render_server_status,
        )

    # ── lifecycle ────────────────────────────────────────────────────────────

    def on_page_activated(self) -> None:
        activate_premium_page(
            sync_pairing_status_autopoll_fn=self._sync_pairing_status_autopoll,
        )

    def on_page_hidden(self) -> None:
        hide_premium_page(
            stop_pairing_status_autopoll_fn=self._stop_pairing_status_autopoll,
        )

    def closeEvent(self, event):
        close_premium_page(
            set_cleanup_in_progress_fn=lambda value: setattr(self, "_cleanup_in_progress", value),
            build_close_plan_fn=PremiumPageController.build_close_plan,
            current_thread=self.current_thread,
            stop_pairing_status_autopoll_fn=self._stop_pairing_status_autopoll,
            set_current_thread_fn=lambda value: setattr(self, "current_thread", value),
            event=event,
        )

    def cleanup(self) -> None:
        cleanup_premium_page(
            set_cleanup_in_progress_fn=lambda value: setattr(self, "_cleanup_in_progress", value),
            stop_pairing_status_autopoll_fn=self._stop_pairing_status_autopoll,
            current_thread=self.current_thread,
            set_current_thread_fn=lambda value: setattr(self, "current_thread", value),
        )

    # ── initialization ───────────────────────────────────────────────────────

    def _init_checker(self):
        try:
            init_result = PremiumPageController.resolve_checker_bundle()
            self.checker = init_result.checker
            self.RegistryManager = init_result.storage
            if not init_result.init_ok:
                raise RuntimeError("premium checker init failed")
            self._update_device_info()
        except Exception as e:
            from log import log
            log(f"Ошибка инициализации PremiumPage checker: {e}", "ERROR")

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        # ─── Статус подписки ─────────────────────────────────────────────────
        self.add_section_title(text_key="page.premium.section.subscription_status")

        self.status_badge = StatusCard()
        self._set_status_badge(
            status="neutral",
            text_key="page.premium.status.checking.title",
            text_default="Проверка...",
            details="",
        )
        self.add_widget(self.status_badge)

        self.days_label = SubtitleLabel("") if _HAS_FLUENT else BodyLabel("")
        self.days_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.add_widget(self.days_label)

        self.add_spacing(8)

        # ─── Привязка устройства ─────────────────────────────────────────────
        self.activation_section_title = self.add_section_title(
            return_widget=True,
            text_key="page.premium.section.device_binding",
        )
        activation_widgets = build_premium_activation_section(
            tr=self._tr,
            on_create_pair_code=self._create_pair_code,
        )
        self.activation_card = activation_widgets.card
        self.instructions_label = activation_widgets.instructions_label
        self.key_input_container = activation_widgets.key_input_container
        self.key_input = activation_widgets.key_input
        self.activate_btn = activation_widgets.activate_btn
        self.activation_status = activation_widgets.activation_status
        self.add_widget(self.activation_card)

        self.add_spacing(8)

        # ─── Информация об устройстве ─────────────────────────────────────────
        self.add_section_title(text_key="page.premium.section.device_info")
        device_widgets = build_premium_device_info_section(
            tr=self._tr,
            on_open_bot=self._open_extend_bot,
        )
        self.device_id_label = device_widgets.device_id_label
        self.saved_key_label = device_widgets.saved_key_label
        self.last_check_label = device_widgets.last_check_label
        self.server_status_label = device_widgets.server_status_label
        self.open_bot_btn = device_widgets.open_bot_btn
        self.add_widget(device_widgets.card)

        self.add_spacing(8)

        # ─── Действия ────────────────────────────────────────────────────────
        self.add_section_title(text_key="page.premium.section.actions")
        actions_widgets = build_premium_actions_section(
            parent=self.content,
            tr=self._tr,
            on_check_status=self._check_status,
            on_change_key=self._change_key,
            on_test_connection=self._test_connection,
            on_open_bot=self._open_extend_bot,
        )
        self._actions_bar = actions_widgets.actions_bar
        self.refresh_btn = actions_widgets.refresh_btn
        self.change_key_btn = actions_widgets.change_key_btn
        self.test_btn = actions_widgets.test_btn
        self.extend_btn = actions_widgets.extend_btn
        self.add_widget(self._actions_bar)
        self._run_runtime_init_once()

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        apply_premium_language(
            tr_fn=self._tr,
            activation_in_progress=self._activation_in_progress,
            connection_test_in_progress=self._connection_test_in_progress,
            instructions_label=self.instructions_label,
            key_input=self.key_input,
            activate_btn=self.activate_btn,
            open_bot_btn=self.open_bot_btn,
            refresh_btn=self.refresh_btn,
            change_key_btn=self.change_key_btn,
            extend_btn=self.extend_btn,
            test_btn=self.test_btn,
            update_device_info_fn=self._update_device_info,
            render_server_status_fn=self._render_server_status,
            render_days_label_fn=self._render_days_label,
            render_status_badge_fn=self._render_status_badge,
            render_activation_status_fn=self._render_activation_status,
        )

    # ── helpers ──────────────────────────────────────────────────────────────

    def _set_activation_section_visible(self, visible: bool):
        if hasattr(self, "key_input_container"):
            self.key_input_container.setVisible(visible)

    def _has_pending_pair_code(self) -> bool:
        return has_pending_pair_code(
            self.RegistryManager,
            current_time=int(time.time()),
        )

    def _can_poll_pairing_status(self) -> bool:
        return can_poll_pairing_status(
            checker_ready=bool(self.checker),
            storage=self.RegistryManager,
            page_visible=self.isVisible(),
            activation_in_progress=self._activation_in_progress,
            connection_test_in_progress=self._connection_test_in_progress,
            worker_running=bool(self.current_thread and self.current_thread.isRunning()),
            current_time=int(time.time()),
        )

    def _start_pairing_status_autopoll(self) -> None:
        start_pairing_status_autopoll(
            self._pairing_status_timer,
            checker_ready=bool(self.checker),
            storage=self.RegistryManager,
            page_visible=self.isVisible(),
            activation_in_progress=self._activation_in_progress,
            connection_test_in_progress=self._connection_test_in_progress,
            worker_running=bool(self.current_thread and self.current_thread.isRunning()),
            current_time=int(time.time()),
        )

    def _stop_pairing_status_autopoll(self) -> None:
        stop_pairing_status_autopoll(self._pairing_status_timer)

    def _sync_pairing_status_autopoll(self) -> None:
        sync_pairing_status_autopoll(
            self._pairing_status_timer,
            checker_ready=bool(self.checker),
            storage=self.RegistryManager,
            page_visible=self.isVisible(),
            activation_in_progress=self._activation_in_progress,
            connection_test_in_progress=self._connection_test_in_progress,
            worker_running=bool(self.current_thread and self.current_thread.isRunning()),
            current_time=int(time.time()),
        )

    def _poll_pairing_status(self) -> None:
        poll_pairing_status(
            can_poll=self._can_poll_pairing_status(),
            stop_autopoll=self._stop_pairing_status_autopoll,
            check_status=self._check_status,
        )

    def _update_device_info(self):
        def _on_error(exc: Exception) -> None:
            from log import log

            log(f"Ошибка обновления информации об устройстве: {exc}", "DEBUG")

        update_device_info_labels(
            checker=self.checker,
            storage=self.RegistryManager,
            tr=self._tr,
            device_id_label=self.device_id_label,
            saved_key_label=self.saved_key_label,
            last_check_label=self.last_check_label,
            on_error=_on_error,
            current_time=int(time.time()),
        )

    def _open_extend_bot(self) -> None:
        result = PremiumPageController.open_extend_bot()
        if result.ok:
            return
        if InfoBar:
            InfoBar.warning(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr(
                    "page.premium.error.open_telegram",
                    "Не удалось открыть Telegram: {error}",
                    error=result.message,
                ),
                parent=self.window(),
            )

    # ── pair code ────────────────────────────────────────────────────────────

    def _create_pair_code(self):
        self._cleanup_in_progress = False
        gate_plan = PremiumPageController.build_worker_gate_plan(
            thread_running=bool(self.current_thread and self.current_thread.isRunning()),
        )
        if not gate_plan.can_start:
            return
        if not self.checker:
            self._init_checker()
            if not self.checker:
                self._set_activation_status(
                    text_key="page.premium.activation.error.init",
                    text_default="❌ Ошибка инициализации",
                )
                return

        plan = apply_pair_code_start_ui(
            activate_btn=self.activate_btn,
            key_input=self.key_input,
            tr=self._tr,
            set_activation_status=self._set_activation_status,
            stop_autopoll=self._stop_pairing_status_autopoll,
        )
        self._activation_in_progress = plan.activation_in_progress

        self._start_worker_thread(
            PremiumPageController.create_worker_thread(self.checker.pair_start),
            self._on_pair_code_created,
            self._on_activation_error,
        )

    def _on_pair_code_created(self, result):
        if self._cleanup_in_progress:
            return
        plan = apply_pair_code_result_ui(
            result,
            activate_btn=self.activate_btn,
            key_input=self.key_input,
            tr=self._tr,
            set_activation_status=self._set_activation_status,
            update_device_info=self._update_device_info,
            start_autopoll=self._start_pairing_status_autopoll,
            stop_autopoll=self._stop_pairing_status_autopoll,
        )
        self._activation_in_progress = plan.activation_in_progress

    def _on_activation_error(self, error):
        if self._cleanup_in_progress:
            return
        plan = apply_pair_code_error_ui(
            error,
            activate_btn=self.activate_btn,
            key_input=self.key_input,
            tr=self._tr,
            set_activation_status=self._set_activation_status,
            update_device_info=self._update_device_info,
            stop_autopoll=self._stop_pairing_status_autopoll,
        )
        self._activation_in_progress = plan.activation_in_progress

    # ── status check ─────────────────────────────────────────────────────────

    def _check_status(self):
        self._cleanup_in_progress = False
        gate_plan = PremiumPageController.build_worker_gate_plan(
            thread_running=bool(self.current_thread and self.current_thread.isRunning()),
        )
        if not gate_plan.can_start:
            return
        if not self.checker:
            self._init_checker()
            if not self.checker:
                self._set_status_badge(
                    status="expired",
                    text_key="page.premium.status.error.title",
                    text_default="Ошибка",
                    details_key="page.premium.status.error.init_failed",
                    details_default="Не удалось инициализировать",
                )
                return

        apply_status_check_start_ui(
            refresh_btn=self.refresh_btn,
            set_status_badge=self._set_status_badge,
        )

        self._start_worker_thread(
            PremiumPageController.create_worker_thread(self.checker.check_device_activation),
            self._on_status_complete,
            self._on_status_error,
        )

    def _on_status_complete(self, result):
        if self._cleanup_in_progress:
            return
        try:
            days_kind, days_value = apply_status_check_success(
                result,
                tr=self._tr,
                refresh_btn=self.refresh_btn,
                update_device_info=self._update_device_info,
                set_status_badge=self._set_status_badge,
                set_activation_section_visible=self._set_activation_section_visible,
                stop_autopoll=self._stop_pairing_status_autopoll,
                sync_autopoll=self._sync_pairing_status_autopoll,
                emit_subscription_updated=self.subscription_updated.emit,
            )
            self._days_state_kind = days_kind
            self._days_state_value = days_value
            self._render_days_label()

        except Exception as e:
            self._sync_pairing_status_autopoll()
            self._set_status_badge(
                status="expired",
                text_key="page.premium.status.error.title",
                text_default="Ошибка",
                details=str(e),
            )
            self._set_activation_section_visible(True)

    def _on_status_error(self, error):
        if self._cleanup_in_progress:
            return
        apply_status_check_exception(
            error,
            tr=self._tr,
            sync_autopoll=self._sync_pairing_status_autopoll,
            refresh_btn=self.refresh_btn,
            set_status_badge=self._set_status_badge,
        )

    # ── connection test ───────────────────────────────────────────────────────

    def _test_connection(self):
        self._cleanup_in_progress = False
        gate_plan = PremiumPageController.build_worker_gate_plan(
            thread_running=bool(self.current_thread and self.current_thread.isRunning()),
        )
        if not gate_plan.can_start:
            return
        if not self.checker:
            self._init_checker()
        plan = PremiumPageController.build_connection_test_start_plan(
            checker_ready=bool(self.checker),
        )
        self._connection_test_in_progress = apply_connection_test_plan(
            plan,
            tr=self._tr,
            test_btn=self.test_btn,
            render_server_status=self._render_server_status,
            set_server_status_state=self._set_server_status_state,
        )
        if not self.checker:
            return

        self._start_worker_thread(
            PremiumPageController.create_worker_thread(self.checker.test_connection),
            self._on_connection_test_complete,
            self._on_connection_test_error,
        )

    def _on_connection_test_complete(self, result):
        if self._cleanup_in_progress:
            return
        plan = PremiumPageController.build_connection_test_result_plan(result)
        self._connection_test_in_progress = apply_connection_test_plan(
            plan,
            tr=self._tr,
            test_btn=self.test_btn,
            render_server_status=self._render_server_status,
            set_server_status_state=self._set_server_status_state,
        )

    def _on_connection_test_error(self, error):
        if self._cleanup_in_progress:
            return
        plan = PremiumPageController.build_connection_test_error_plan(str(error or ""))
        self._connection_test_in_progress = apply_connection_test_plan(
            plan,
            tr=self._tr,
            test_btn=self.test_btn,
            render_server_status=self._render_server_status,
            set_server_status_state=self._set_server_status_state,
        )

    def _start_worker_thread(self, thread, result_handler, error_handler) -> None:
        self.current_thread = thread
        self.current_thread.result_ready.connect(result_handler)
        self.current_thread.error_occurred.connect(error_handler)
        self.current_thread.finished.connect(self._on_worker_thread_finished)
        self.current_thread.finished.connect(self.current_thread.deleteLater)
        self.current_thread.start()

    def _on_worker_thread_finished(self) -> None:
        self.current_thread = None

    # ── reset activation ──────────────────────────────────────────────────────

    def _change_key(self):
        if MessageBox:
            box = MessageBox(
                self._tr("page.premium.dialog.reset.title", "Подтверждение"),
                self._tr(
                    "page.premium.dialog.reset.body",
                    "Сбросить активацию на этом устройстве?\nБудут удалены device token, offline-кэш и код привязки.\nДля восстановления потребуется повторная привязка в боте.",
                ),
                self.window(),
            )
            if not box.exec():
                return

        self._days_state_kind, self._days_state_value = apply_reset_plan_ui(
            checker=self.checker,
            storage=self.RegistryManager,
            key_input=self.key_input,
            set_activation_status=self._set_activation_status,
            update_device_info=self._update_device_info,
            set_status_badge=self._set_status_badge,
            render_days_label=self._render_days_label,
            set_activation_section_visible=self._set_activation_section_visible,
            stop_autopoll=self._stop_pairing_status_autopoll,
            emit_subscription_updated=self.subscription_updated.emit,
        )
        self._render_days_label()
