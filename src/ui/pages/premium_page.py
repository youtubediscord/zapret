# ui/pages/premium_page.py
"""Страница управления Premium подпиской"""

import time

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout, QApplication, QSizePolicy, QPushButton
import qtawesome as qta

try:
    from qfluentwidgets import (
        LineEdit, MessageBox, InfoBar,
        PushButton, PrimaryPushButton,
        BodyLabel, CaptionLabel, StrongBodyLabel, SubtitleLabel,
    )
    _HAS_FLUENT = True
except ImportError:
    from PyQt6.QtWidgets import (   # type: ignore[assignment]
        QLineEdit as LineEdit, QLabel as BodyLabel, QLabel as CaptionLabel,
        QLabel as StrongBodyLabel, QLabel as SubtitleLabel,
    )
    PushButton = QPushButton  # type: ignore[assignment]
    PrimaryPushButton = QPushButton  # type: ignore[assignment]
    MessageBox = None
    InfoBar = None
    _HAS_FLUENT = False

import webbrowser

from donater.premium_page_controller import PremiumPageController
from donater.premium_worker import PremiumWorkerThread
from .base_page import BasePage
from ui.compat_widgets import SettingsCard, RefreshButton, QuickActionsBar
from ui.main_window_state import AppUiState, MainWindowStateStore
from ui.theme_semantic import get_semantic_palette
from ui.text_catalog import tr as tr_catalog


# ─────────────────────────────────────────────────────────────────────────────
# StatusCard — full-width subscription status display
# ─────────────────────────────────────────────────────────────────────────────

class StatusCard(QFrame):
    """Full-width subscription status card (no InfoBar dependency)."""

    _STATUS_CONFIG = {
        'active':  {'bg': '#1c2e24', 'fg': '#7ecb9a', 'icon': '✓'},
        'warning': {'bg': '#2a2516', 'fg': '#c8a96e', 'icon': '⚠'},
        'expired': {'bg': '#2a1e1e', 'fg': '#c98080', 'icon': '✕'},
        'neutral': {'bg': '#1a2030', 'fg': '#7aa8d4', 'icon': 'ℹ'},
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(52)

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(10)

        self._icon_lbl = QLabel()
        self._icon_lbl.setFixedWidth(22)
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._title_lbl = QLabel()
        self._detail_lbl = QLabel()

        row.addWidget(self._icon_lbl)
        row.addWidget(self._title_lbl)
        row.addSpacing(8)
        row.addWidget(self._detail_lbl)
        row.addStretch(1)

        self.set_status("", "", "neutral")

    def set_status(self, text: str, details: str = "", status: str = "neutral"):
        cfg = self._STATUS_CONFIG.get(status, self._STATUS_CONFIG['neutral'])

        self._icon_lbl.setText(cfg['icon'])
        self._icon_lbl.setStyleSheet(
            f"color: {cfg['fg']}; font-size: 15px; font-weight: bold; background: transparent;"
        )

        self._title_lbl.setText(text)
        self._title_lbl.setStyleSheet(
            f"color: {cfg['fg']}; font-weight: 600; font-size: 13px; background: transparent;"
        )

        self._detail_lbl.setText(details)
        self._detail_lbl.setStyleSheet(
            "color: rgba(255,255,255,180); font-size: 13px; background: transparent;"
        )
        self._detail_lbl.setVisible(bool(details))

        self.setStyleSheet(f"""
            StatusCard {{
                background-color: {cfg['bg']};
                border: none;
                border-radius: 8px;
            }}
        """)


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
        if self._ui_state_store is store:
            return

        unsubscribe = getattr(self, "_ui_state_unsubscribe", None)
        if callable(unsubscribe):
            try:
                unsubscribe()
            except Exception:
                pass

        self._ui_state_store = store
        self._ui_state_unsubscribe = store.subscribe(
            self._on_ui_state_changed,
            fields={"subscription_is_premium", "subscription_days_remaining"},
            emit_initial=True,
        )

    def _on_ui_state_changed(self, state: AppUiState, _changed_fields: frozenset[str]) -> None:
        self._apply_subscription_snapshot(
            state.subscription_is_premium,
            state.subscription_days_remaining,
        )

    def _apply_subscription_snapshot(self, is_premium: bool, days_remaining: int | None) -> None:
        badge_plan, days_plan, _emitted_days = PremiumPageController.build_subscription_snapshot_plan(
            is_premium=is_premium,
            days_remaining=days_remaining,
        )
        self._set_status_badge(
            status=badge_plan.status,
            text_key=badge_plan.text_key,
            text_default=badge_plan.text_default,
            text_kwargs=badge_plan.text_kwargs,
            details_key=badge_plan.details_key,
            details_default=badge_plan.details_default,
            details_kwargs=badge_plan.details_kwargs,
        )
        self._days_state_kind = days_plan.kind
        self._days_state_value = days_plan.value

        self._render_days_label()

    def _render_activation_status(self) -> None:
        state = self._activation_status_state
        text_key = state.get("text_key")
        if text_key:
            self.activation_status.setText(
                self._tr(
                    text_key,
                    state.get("text_default") or "",
                    **(state.get("text_kwargs") or {}),
                )
            )
            return
        self.activation_status.setText(state.get("text") or "")

    def _render_server_status(self) -> None:
        mode = self._server_status_mode
        if mode == "checking":
            self.server_status_label.setText(
                self._tr("page.premium.connection.progress.testing", "🔄 Проверка соединения...")
            )
            return
        if mode == "idle":
            self.server_status_label.setText(
                self._tr("page.premium.label.server.idle", "Сервер: нажмите «Проверить соединение»")
            )
            return
        if mode == "init_error":
            self.server_status_label.setText(
                self._tr("page.premium.activation.error.init", "❌ Ошибка инициализации")
            )
            return
        if mode == "result":
            icon = "✅" if self._server_status_success else "❌"
            self.server_status_label.setText(
                self._tr(
                    "page.premium.connection.result.template",
                    "{icon} {message}",
                    icon=icon,
                    message=self._server_status_message,
                )
            )
            return
        if mode == "error":
            self.server_status_label.setText(
                self._tr(
                    "page.premium.activation.error.generic",
                    "❌ Ошибка: {error}",
                    error=self._server_status_message,
                )
            )
            return

        self.server_status_label.setText(self._tr("page.premium.label.server.checking", "Сервер: проверка..."))

    def _run_runtime_init_once(self) -> None:
        plan = PremiumPageController.build_page_init_plan(
            runtime_initialized=self._runtime_initialized,
        )
        if not plan.ensure_checker_once:
            return

        self._runtime_initialized = True
        self._init_checker()
        self._server_status_mode = plan.init_server_status_plan.mode
        self._server_status_message = plan.init_server_status_plan.message
        self._server_status_success = plan.init_server_status_plan.success
        self._render_server_status()

    # ── lifecycle ────────────────────────────────────────────────────────────

    def on_page_activated(self, first_show: bool) -> None:
        self._sync_pairing_status_autopoll()

    def on_page_hidden(self) -> None:
        self._stop_pairing_status_autopoll()

    def closeEvent(self, event):
        plan = PremiumPageController.build_close_plan(
            thread_running=bool(self.current_thread and self.current_thread.isRunning()),
        )
        if plan.stop_autopoll:
            self._stop_pairing_status_autopoll()
        if plan.should_quit_thread and self.current_thread and self.current_thread.isRunning():
            self.current_thread.quit()
            self.current_thread.wait(plan.wait_timeout_ms)
        event.accept()

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

        self.activation_card = SettingsCard()

        self.instructions_label = BodyLabel(
            self._tr(
                "page.premium.instructions",
                "1. Нажмите «Создать код»\n2. Отправьте код боту @zapretvpns_bot в Telegram (сообщением)\n3. Вернитесь сюда и нажмите «Проверить статус»",
            )
        )
        self.instructions_label.setWordWrap(True)
        self.activation_card.add_widget(self.instructions_label)

        # Контейнер с кодом привязки (скрывается при активной подписке)
        self.key_input_container = QWidget()
        key_v = QVBoxLayout(self.key_input_container)
        key_v.setContentsMargins(0, 0, 0, 0)
        key_v.setSpacing(8)

        key_row = QHBoxLayout()
        key_row.setSpacing(8)

        self.key_input = LineEdit()
        self.key_input.setPlaceholderText(
            self._tr("page.premium.placeholder.pair_code", "ABCD12EF")
        )
        self.key_input.setReadOnly(True)
        key_row.addWidget(self.key_input, 1)

        self.activate_btn = PrimaryPushButton()
        self.activate_btn.setText(self._tr("page.premium.button.create_code", "Создать код"))
        self.activate_btn.setIcon(qta.icon("fa5s.link", color="#60cdff"))
        self.activate_btn.clicked.connect(self._create_pair_code)
        key_row.addWidget(self.activate_btn)

        key_v.addLayout(key_row)

        self.activation_status = CaptionLabel("")
        self.activation_status.setWordWrap(True)
        key_v.addWidget(self.activation_status)

        self.activation_card.add_widget(self.key_input_container)
        self.add_widget(self.activation_card)

        self.add_spacing(8)

        # ─── Информация об устройстве ─────────────────────────────────────────
        self.add_section_title(text_key="page.premium.section.device_info")

        device_card = SettingsCard()

        self.device_id_label = CaptionLabel(
            self._tr("page.premium.label.device_id.loading", "ID устройства: загрузка...")
        )
        self.saved_key_label = CaptionLabel(
            self._tr("page.premium.label.device_token.none", "device token: —")
        )
        self.last_check_label = CaptionLabel(
            self._tr("page.premium.label.last_check.none", "Последняя проверка: —")
        )
        self.server_status_label = CaptionLabel(
            self._tr("page.premium.label.server.checking", "Сервер: проверка...")
        )

        labels_layout = QVBoxLayout()
        labels_layout.setSpacing(4)
        labels_layout.setContentsMargins(0, 0, 0, 0)
        labels_layout.addWidget(self.device_id_label)
        labels_layout.addWidget(self.saved_key_label)
        labels_layout.addWidget(self.last_check_label)
        labels_layout.addWidget(self.server_status_label)

        self.open_bot_btn = PushButton()
        self.open_bot_btn.setText(self._tr("page.premium.button.open_bot", "Открыть бота"))
        self.open_bot_btn.setIcon(qta.icon("fa5b.telegram", color="#229ED9"))
        self.open_bot_btn.clicked.connect(self._open_extend_bot)

        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addLayout(labels_layout)
        row_layout.addStretch(1)
        row_layout.addWidget(self.open_bot_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        device_card.add_layout(row_layout)

        self.add_widget(device_card)

        self.add_spacing(8)

        # ─── Действия ────────────────────────────────────────────────────────
        self.add_section_title(text_key="page.premium.section.actions")

        self.refresh_btn = RefreshButton(self._tr("page.premium.button.refresh_status", "Обновить статус"))
        self.refresh_btn.clicked.connect(self._check_status)
        self.refresh_btn.setToolTip(
            self._tr(
                "page.premium.action.refresh_status.description",
                "Повторно запросить Premium-статус и обновить данные устройства.",
            )
        )

        self._actions_bar = QuickActionsBar(self.content)
        self._actions_bar.add_button(self.refresh_btn)

        self.change_key_btn = PushButton()
        self.change_key_btn.setText(self._tr("page.premium.button.reset_activation", "Сбросить активацию"))
        self.change_key_btn.setIcon(qta.icon("fa5s.exchange-alt", color="#ff9800"))
        self.change_key_btn.setToolTip(
            self._tr(
                "page.premium.action.reset_activation.description",
                "Удалить токен устройства, офлайн-кэш и код привязки на этом компьютере.",
            )
        )
        self.change_key_btn.clicked.connect(self._change_key)
        self._actions_bar.add_button(self.change_key_btn)

        self.test_btn = PushButton()
        self.test_btn.setText(self._tr("page.premium.button.test_connection", "Проверить соединение"))
        self.test_btn.setIcon(qta.icon("fa5s.plug", color="#60cdff"))
        self.test_btn.setToolTip(
            self._tr(
                "page.premium.action.test_connection.description",
                "Проверить доступность Premium backend и соединение с сервером.",
            )
        )
        self.test_btn.clicked.connect(self._test_connection)
        self._actions_bar.add_button(self.test_btn)

        self.extend_btn = PrimaryPushButton()
        self.extend_btn.setText(self._tr("page.premium.button.extend", "Продлить подписку"))
        self.extend_btn.setIcon(qta.icon("fa5b.telegram", color="#229ED9"))
        self.extend_btn.setToolTip(
            self._tr(
                "page.premium.action.extend.description",
                "Открыть Telegram-бота для продления подписки или покупки Premium.",
            )
        )
        self.extend_btn.clicked.connect(self._open_extend_bot)
        self._actions_bar.add_button(self.extend_btn)

        self.add_widget(self._actions_bar)
        self._run_runtime_init_once()

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        self.instructions_label.setText(
            self._tr(
                "page.premium.instructions",
                "1. Нажмите «Создать код»\n2. Отправьте код боту @zapretvpns_bot в Telegram (сообщением)\n3. Вернитесь сюда и нажмите «Проверить статус»",
            )
        )
        self.key_input.setPlaceholderText(self._tr("page.premium.placeholder.pair_code", "ABCD12EF"))

        if self._activation_in_progress:
            self.activate_btn.setText(self._tr("page.premium.button.create_code.loading", "Создание..."))
        else:
            self.activate_btn.setText(self._tr("page.premium.button.create_code", "Создать код"))

        self.open_bot_btn.setText(self._tr("page.premium.button.open_bot", "Открыть бота"))
        self.refresh_btn.setText(self._tr("page.premium.button.refresh_status", "Обновить статус"))
        self.change_key_btn.setText(self._tr("page.premium.button.reset_activation", "Сбросить активацию"))
        self.extend_btn.setText(self._tr("page.premium.button.extend", "Продлить подписку"))
        self.refresh_btn.setToolTip(
            self._tr(
                "page.premium.action.refresh_status.description",
                "Повторно запросить Premium-статус и обновить данные устройства.",
            )
        )
        self.change_key_btn.setToolTip(
            self._tr(
                "page.premium.action.reset_activation.description",
                "Удалить токен устройства, офлайн-кэш и код привязки на этом компьютере.",
            )
        )
        self.extend_btn.setToolTip(
            self._tr(
                "page.premium.action.extend.description",
                "Открыть Telegram-бота для продления подписки или покупки Premium.",
            )
        )

        if self._connection_test_in_progress:
            self.test_btn.setText(self._tr("page.premium.button.test_connection.loading", "Проверка..."))
        else:
            self.test_btn.setText(self._tr("page.premium.button.test_connection", "Проверить соединение"))
        self.test_btn.setToolTip(
            self._tr(
                "page.premium.action.test_connection.description",
                "Проверить доступность Premium backend и соединение с сервером.",
            )
        )

        self._update_device_info()
        self._render_server_status()
        self._render_days_label()
        self._render_status_badge()
        self._render_activation_status()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _set_activation_section_visible(self, visible: bool):
        if hasattr(self, "key_input_container"):
            self.key_input_container.setVisible(visible)

    def _has_pending_pair_code(self) -> bool:
        snapshot = PremiumPageController.read_pairing_snapshot(
            self.RegistryManager,
            current_time=int(time.time()),
        )
        return snapshot.has_pending_pair_code

    def _can_poll_pairing_status(self) -> bool:
        snapshot = PremiumPageController.read_pairing_snapshot(
            self.RegistryManager,
            current_time=int(time.time()),
        )

        plan = PremiumPageController.build_pairing_autopoll_plan(
            checker_ready=bool(self.checker),
            storage_ready=bool(self.RegistryManager),
            page_visible=self.isVisible(),
            activation_in_progress=self._activation_in_progress,
            connection_test_in_progress=self._connection_test_in_progress,
            worker_running=bool(self.current_thread and self.current_thread.isRunning()),
            has_device_token=snapshot.has_device_token,
            has_pending_pair_code=snapshot.has_pending_pair_code,
        )
        return plan.can_poll

    def _start_pairing_status_autopoll(self) -> None:
        snapshot = PremiumPageController.read_pairing_snapshot(
            self.RegistryManager,
            current_time=int(time.time()),
        )
        plan = PremiumPageController.build_pairing_autopoll_plan(
            checker_ready=bool(self.checker),
            storage_ready=bool(self.RegistryManager),
            page_visible=self.isVisible(),
            activation_in_progress=self._activation_in_progress,
            connection_test_in_progress=self._connection_test_in_progress,
            worker_running=bool(self.current_thread and self.current_thread.isRunning()),
            has_device_token=snapshot.has_device_token,
            has_pending_pair_code=snapshot.has_pending_pair_code,
        )
        if plan.start_timer and not self._pairing_status_timer.isActive():
            self._pairing_status_timer.start()

    def _stop_pairing_status_autopoll(self) -> None:
        if self._pairing_status_timer.isActive():
            self._pairing_status_timer.stop()

    def _sync_pairing_status_autopoll(self) -> None:
        snapshot = PremiumPageController.read_pairing_snapshot(
            self.RegistryManager,
            current_time=int(time.time()),
        )

        plan = PremiumPageController.build_pairing_autopoll_plan(
            checker_ready=bool(self.checker),
            storage_ready=bool(self.RegistryManager),
            page_visible=self.isVisible(),
            activation_in_progress=self._activation_in_progress,
            connection_test_in_progress=self._connection_test_in_progress,
            worker_running=bool(self.current_thread and self.current_thread.isRunning()),
            has_device_token=snapshot.has_device_token,
            has_pending_pair_code=snapshot.has_pending_pair_code,
        )
        if plan.start_timer:
            self._start_pairing_status_autopoll()
        if plan.stop_timer:
            self._stop_pairing_status_autopoll()

    def _poll_pairing_status(self) -> None:
        plan = PremiumPageController.build_pairing_poll_plan(
            can_poll=self._can_poll_pairing_status(),
        )
        if plan.should_stop_timer:
            self._stop_pairing_status_autopoll()
            return
        if plan.should_check_status:
            self._check_status()

    def _update_device_info(self):
        if not self.checker:
            return
        try:
            snapshot = PremiumPageController.read_device_storage_snapshot(
                self.RegistryManager,
                current_time=int(time.time()),
            )
            plan = PremiumPageController.build_device_info_plan(
                device_id=self.checker.device_id,
                device_token=snapshot.get("device_token"),
                pair_code=snapshot.get("pair_code"),
                last_check=snapshot.get("last_check"),
                token_present_text=self._tr("page.premium.label.device_token.present", "device token: ✅"),
                token_absent_text=self._tr("page.premium.label.device_token.absent", "device token: ❌"),
                pair_template_text=self._tr("page.premium.label.pair_code.value", "pair: {pair_code}"),
            )

            self.device_id_label.setText(
                self._tr(
                    plan.device_id_text_key,
                    plan.device_id_text_default,
                    **plan.device_id_kwargs,
                )
            )
            self.saved_key_label.setText(plan.saved_key_text)
            self.last_check_label.setText(
                self._tr(
                    plan.last_check_text_key,
                    plan.last_check_text_default,
                    **plan.last_check_kwargs,
                )
            )
        except Exception as e:
            from log import log
            log(f"Ошибка обновления информации об устройстве: {e}", "DEBUG")

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

        plan = PremiumPageController.build_pair_code_start_plan()
        self._activation_in_progress = plan.activation_in_progress
        if plan.stop_autopoll:
            self._stop_pairing_status_autopoll()
        if plan.clear_key_input:
            self.key_input.clear()
        self.activate_btn.setEnabled(plan.activate_enabled)
        self.activate_btn.setText(
            self._tr(plan.activate_text_key, plan.activate_text_default)
        )
        self._set_activation_status(
            text=plan.activation_status_plan.text,
            text_key=plan.activation_status_plan.text_key,
            text_default=plan.activation_status_plan.text_default,
            text_kwargs=plan.activation_status_plan.text_kwargs,
        )

        self.current_thread = PremiumPageController.create_worker_thread(self.checker.pair_start)
        self.current_thread.result_ready.connect(self._on_pair_code_created)
        self.current_thread.error_occurred.connect(self._on_activation_error)
        self.current_thread.start()

    def _on_pair_code_created(self, result):
        plan = PremiumPageController.build_pair_code_result_plan(result)
        self._activation_in_progress = plan.activation_in_progress
        self.activate_btn.setEnabled(plan.activate_enabled)
        self.activate_btn.setText(self._tr(plan.activate_text_key, plan.activate_text_default))
        if plan.clear_key_input:
            self.key_input.clear()
        else:
            self.key_input.setText(plan.key_input_text)
        if plan.copy_to_clipboard and plan.key_input_text:
            try:
                QApplication.clipboard().setText(plan.key_input_text)
            except Exception:
                pass
        self._set_activation_status(
            text=plan.activation_status_plan.text,
            text_key=plan.activation_status_plan.text_key,
            text_default=plan.activation_status_plan.text_default,
            text_kwargs=plan.activation_status_plan.text_kwargs,
        )
        if plan.update_device_info:
            self._update_device_info()
        if plan.start_autopoll:
            self._start_pairing_status_autopoll()
        if plan.stop_autopoll:
            self._stop_pairing_status_autopoll()

    def _on_activation_error(self, error):
        plan = PremiumPageController.build_pair_code_error_plan(str(error or ""))
        self._activation_in_progress = plan.activation_in_progress
        if plan.clear_key_input:
            self.key_input.clear()
        self.activate_btn.setEnabled(plan.activate_enabled)
        self.activate_btn.setText(self._tr(plan.activate_text_key, plan.activate_text_default))
        self._set_activation_status(
            text=plan.activation_status_plan.text,
            text_key=plan.activation_status_plan.text_key,
            text_default=plan.activation_status_plan.text_default,
            text_kwargs=plan.activation_status_plan.text_kwargs,
        )
        if plan.update_device_info:
            self._update_device_info()
        if plan.stop_autopoll:
            self._stop_pairing_status_autopoll()

    # ── status check ─────────────────────────────────────────────────────────

    def _check_status(self):
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

        self.refresh_btn.set_loading(True)
        self._set_status_badge(
            status="neutral",
            text_key="page.premium.status.checking.title",
            text_default="Проверка...",
            details_key="page.premium.status.checking.details",
            details_default="Подключение к серверу",
        )

        self.current_thread = PremiumPageController.create_worker_thread(self.checker.check_device_activation)
        self.current_thread.result_ready.connect(self._on_status_complete)
        self.current_thread.error_occurred.connect(self._on_status_error)
        self.current_thread.start()

    def _on_status_complete(self, result):
        self.refresh_btn.set_loading(False)
        self._update_device_info()
        try:
            plan = PremiumPageController.build_status_check_plan(
                result,
                linked_hint=self._tr(
                    "page.premium.status.inactive.linked_hint",
                    "Продлите подписку в боте и нажмите «Обновить статус».",
                ),
                unlinked_hint=self._tr(
                    "page.premium.status.inactive.unlinked_hint",
                    "Создайте код и привяжите устройство.",
                ),
            )

            self._set_status_badge(
                status=plan.badge_plan.status,
                text_key=plan.badge_plan.text_key,
                text_default=plan.badge_plan.text_default,
                text_kwargs=plan.badge_plan.text_kwargs,
                details_key=plan.badge_plan.details_key,
                details_default=plan.badge_plan.details_default,
                details_kwargs=plan.badge_plan.details_kwargs,
            )
            self._days_state_kind = plan.days_plan.kind
            self._days_state_value = plan.days_plan.value
            self._render_days_label()
            self._set_activation_section_visible(not plan.hide_activation_section)

            if plan.stop_autopoll:
                self._stop_pairing_status_autopoll()
            elif plan.sync_autopoll:
                self._sync_pairing_status_autopoll()

            self.subscription_updated.emit(plan.emitted_is_premium, plan.emitted_days)

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
        self._sync_pairing_status_autopoll()
        self.refresh_btn.set_loading(False)
        plan = PremiumPageController.build_status_check_plan(
            {"activated": False, "status": str(error or ""), "found": False},
            linked_hint=self._tr(
                "page.premium.status.inactive.linked_hint",
                "Продлите подписку в боте и нажмите «Обновить статус».",
            ),
            unlinked_hint=self._tr(
                "page.premium.status.inactive.unlinked_hint",
                "Создайте код и привяжите устройство.",
            ),
        )
        self._set_status_badge(
            status="expired",
            text_key="page.premium.status.error.check_failed",
            text_default="Ошибка проверки",
            details=plan.badge_plan.details_default or str(error or ""),
        )

    # ── connection test ───────────────────────────────────────────────────────

    def _test_connection(self):
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
        self._connection_test_in_progress = plan.connection_in_progress
        self.test_btn.setEnabled(plan.test_enabled)
        self.test_btn.setText(self._tr(plan.test_text_key, plan.test_text_default))
        self._server_status_mode = plan.server_status_plan.mode
        self._server_status_message = plan.server_status_plan.message
        self._server_status_success = plan.server_status_plan.success
        self._render_server_status()
        if not self.checker:
            return

        self.current_thread = PremiumPageController.create_worker_thread(self.checker.test_connection)
        self.current_thread.result_ready.connect(self._on_connection_test_complete)
        self.current_thread.error_occurred.connect(self._on_connection_test_error)
        self.current_thread.start()

    def _on_connection_test_complete(self, result):
        plan = PremiumPageController.build_connection_test_result_plan(result)
        self._connection_test_in_progress = plan.connection_in_progress
        self.test_btn.setEnabled(plan.test_enabled)
        self.test_btn.setText(self._tr(plan.test_text_key, plan.test_text_default))
        self._server_status_mode = plan.server_status_plan.mode
        self._server_status_message = plan.server_status_plan.message
        self._server_status_success = plan.server_status_plan.success
        self._render_server_status()

    def _on_connection_test_error(self, error):
        plan = PremiumPageController.build_connection_test_error_plan(str(error or ""))
        self._connection_test_in_progress = plan.connection_in_progress
        self.test_btn.setEnabled(plan.test_enabled)
        self.test_btn.setText(self._tr(plan.test_text_key, plan.test_text_default))
        self._server_status_mode = plan.server_status_plan.mode
        self._server_status_message = plan.server_status_plan.message
        self._server_status_success = plan.server_status_plan.success
        self._render_server_status()

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

        PremiumPageController.reset_premium_storage(self.checker, self.RegistryManager)
        plan = PremiumPageController.build_reset_plan()

        if plan.clear_pair_input:
            self.key_input.clear()
        self._set_activation_status(
            text=plan.activation_status_plan.text,
            text_key=plan.activation_status_plan.text_key,
            text_default=plan.activation_status_plan.text_default,
            text_kwargs=plan.activation_status_plan.text_kwargs,
        )
        self._update_device_info()
        self._set_status_badge(
            status=plan.badge_plan.status,
            text_key=plan.badge_plan.text_key,
            text_default=plan.badge_plan.text_default,
            text_kwargs=plan.badge_plan.text_kwargs,
            details_key=plan.badge_plan.details_key,
            details_default=plan.badge_plan.details_default,
            details_kwargs=plan.badge_plan.details_kwargs,
        )
        self._days_state_kind = plan.days_plan.kind
        self._days_state_value = plan.days_plan.value
        self._render_days_label()
        self._set_activation_section_visible(plan.show_activation_section)
        if plan.stop_autopoll:
            self._stop_pairing_status_autopoll()
        self.subscription_updated.emit(plan.emitted_is_premium, plan.emitted_days)
