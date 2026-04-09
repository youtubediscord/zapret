# ui/pages/about_page.py
"""Страница О программе — версия, подписка, поддержка, справка"""

from __future__ import annotations

import os
import subprocess
import webbrowser

import qtawesome as qta
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget,
    QFrame, QSizePolicy, QLayout,
)

from .base_page import BasePage
from ui.compat_widgets import SettingsCard, ActionButton, SettingsRow
from ui.main_window_state import AppUiState, MainWindowStateStore
from ui.text_catalog import tr as tr_catalog
from ui.theme import get_theme_tokens
from log import log

try:
    from qfluentwidgets import (
        SubtitleLabel, BodyLabel, StrongBodyLabel, CaptionLabel,
        SegmentedWidget, InfoBar,
        HyperlinkCard, PushSettingCard, SettingCardGroup, FluentIcon,
    )
    _HAS_FLUENT = True
except ImportError:
    _HAS_FLUENT = False
    FluentIcon = None
    InfoBar = None

def _make_section_label(text: str, parent: QWidget | None = None) -> QLabel:
    """Создаёт заголовок секции для использования внутри sub-layout."""
    if _HAS_FLUENT:
        lbl = StrongBodyLabel(text, parent)
    else:
        lbl = QLabel(text, parent)
        lbl.setStyleSheet("font-size: 13px; font-weight: 600; padding-top: 8px; padding-bottom: 4px;")
    lbl.setProperty("tone", "primary")
    return lbl


class AboutPage(BasePage):
    """Страница О программе с вкладками: О программе / Поддержка / Справка"""

    def __init__(self, parent=None):
        super().__init__(
            "О программе",
            "Версия, подписка и информация",
            parent,
            title_key="page.about.title",
            subtitle_key="page.about.subtitle",
        )

        # UI refs (support tab)
        self._support_icon_label: QLabel | None = None

        # Tab lazy init flags
        self._support_tab_initialized = False
        self._help_tab_initialized = False
        self._kvn_tab_initialized = False

        self._sub_is_premium = False
        self._sub_days_left: int | None = None
        self._ui_state_store = None
        self._ui_state_unsubscribe = None

        self.enable_deferred_ui_build()

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
        self.update_subscription_status(
            state.subscription_is_premium,
            state.subscription_days_remaining,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # UI building
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Pivot (tabs) ──────────────────────────────────────────────────
        if _HAS_FLUENT:
            self.tabs_pivot = SegmentedWidget()
            self.tabs_pivot.addItem(routeKey="about", text=" " + tr_catalog("page.about.tab.about", default="О ПРОГРАММЕ"),
                                    onClick=lambda: self._switch_tab(0))
            self.tabs_pivot.addItem(routeKey="support", text=" " + tr_catalog("page.about.tab.support", default="ПОДДЕРЖКА"),
                                    onClick=lambda: self._switch_tab(1))
            self.tabs_pivot.addItem(routeKey="help", text=" " + tr_catalog("page.about.tab.help", default="СПРАВКА"),
                                    onClick=lambda: self._switch_tab(2))
            self.tabs_pivot.addItem(routeKey="kvn", text=" ZAPRET KVN",
                                    onClick=lambda: self._switch_tab(3))
            self.tabs_pivot.setCurrentItem("about")
            self.tabs_pivot.setItemFontSize(13)
            self.add_widget(self.tabs_pivot)

        # ── QStackedWidget ────────────────────────────────────────────────
        self.stacked_widget = QStackedWidget()

        # Tab 0: О программе
        self._about_tab = QWidget()
        about_layout = QVBoxLayout(self._about_tab)
        about_layout.setContentsMargins(0, 0, 0, 0)
        about_layout.setSpacing(16)
        self._build_about_content(about_layout)

        # Tab 1: Поддержка (lazy)
        self._support_tab = QWidget()
        self._support_layout = QVBoxLayout(self._support_tab)
        self._support_layout.setContentsMargins(0, 0, 0, 0)
        self._support_layout.setSpacing(16)

        # Tab 2: Справка (lazy)
        self._help_tab = QWidget()
        self._help_layout = QVBoxLayout(self._help_tab)
        self._help_layout.setContentsMargins(0, 0, 0, 0)
        self._help_layout.setSpacing(16)

        # Tab 3: Zapret KVN (lazy)
        self._kvn_tab = QWidget()
        self._kvn_layout = QVBoxLayout(self._kvn_tab)
        self._kvn_layout.setContentsMargins(0, 0, 0, 0)
        self._kvn_layout.setSpacing(16)

        self.stacked_widget.addWidget(self._about_tab)
        self.stacked_widget.addWidget(self._support_tab)
        self.stacked_widget.addWidget(self._help_tab)
        self.stacked_widget.addWidget(self._kvn_tab)

        self.add_widget(self.stacked_widget)

    def _switch_tab(self, index: int):
        if index == 1 and not self._support_tab_initialized:
            self._support_tab_initialized = True
            try:
                self._build_support_content(self._support_layout)
            except Exception as e:
                log(f"Ошибка построения вкладки поддержки: {e}", "ERROR")

        if index == 2 and not self._help_tab_initialized:
            self._help_tab_initialized = True
            try:
                self._build_help_content(self._help_layout)
            except Exception as e:
                log(f"Ошибка построения вкладки справки: {e}", "ERROR")

        if index == 3 and not self._kvn_tab_initialized:
            self._kvn_tab_initialized = True
            try:
                self._build_kvn_content(self._kvn_layout)
            except Exception as e:
                log(f"Ошибка построения вкладки KVN: {e}", "ERROR")

        self.stacked_widget.setCurrentIndex(index)

        if _HAS_FLUENT and hasattr(self, "tabs_pivot"):
            keys = ["about", "support", "help", "kvn"]
            try:
                self.tabs_pivot.setCurrentItem(keys[index])
            except Exception:
                pass

    def switch_to_tab(self, key: str) -> None:
        """External API: switch to About/Support/Help tab by key."""
        normalized = str(key or "").strip().lower()
        if normalized in {"about", "support", "help", "kvn"}:
            self._switch_tab({"about": 0, "support": 1, "help": 2, "kvn": 3}[normalized])

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        if _HAS_FLUENT and hasattr(self, "tabs_pivot"):
            try:
                self.tabs_pivot.setItemText("about", " " + tr_catalog("page.about.tab.about", language=language, default="О ПРОГРАММЕ"))
                self.tabs_pivot.setItemText("support", " " + tr_catalog("page.about.tab.support", language=language, default="ПОДДЕРЖКА"))
                self.tabs_pivot.setItemText("help", " " + tr_catalog("page.about.tab.help", language=language, default="СПРАВКА"))
                self.tabs_pivot.setItemText("kvn", " ZAPRET KVN")
            except Exception:
                pass

        self._retranslate_about_tab()
        if self._support_tab_initialized:
            self._rebuild_support_tab()
        if self._help_tab_initialized:
            self._rebuild_help_tab()
        if self._kvn_tab_initialized:
            self._rebuild_kvn_tab()

    def _clear_layout(self, layout: QLayout | None) -> None:
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                try:
                    widget.deleteLater()
                except Exception:
                    pass
            elif child_layout is not None:
                try:
                    self._clear_layout(child_layout)
                except Exception:
                    pass

    def _retranslate_about_tab(self) -> None:
        try:
            from config import APP_VERSION

            self.about_section_version_label.setText(
                tr_catalog("page.about.section.version", language=self._ui_language, default="Версия")
            )
            self.about_app_name_label.setText(
                tr_catalog("page.about.app_name", language=self._ui_language, default="Zapret 2 GUI")
            )
            self.about_version_value_label.setText(
                tr_catalog(
                    "page.about.version.value_template",
                    language=self._ui_language,
                    default="Версия {version}",
                ).format(version=APP_VERSION)
            )
            self.update_btn.setText(
                tr_catalog("page.about.button.update_settings", language=self._ui_language, default="Настройка обновлений")
            )

            self.about_section_device_label.setText(
                tr_catalog("page.about.section.device", language=self._ui_language, default="Устройство")
            )
            self.device_title_label.setText(
                tr_catalog("page.about.device.id", language=self._ui_language, default="ID устройства")
            )
            self.copy_btn.setText(
                tr_catalog("page.about.button.copy_id", language=self._ui_language, default="Копировать ID")
            )

            self.about_section_subscription_label.setText(
                tr_catalog("page.about.section.subscription", language=self._ui_language, default="Подписка")
            )
            self.sub_desc_label.setText(
                tr_catalog(
                    "page.about.subscription.desc",
                    language=self._ui_language,
                    default="Подписка Zapret Premium открывает доступ к дополнительным темам, приоритетной поддержке и VPN-сервису.",
                )
            )
            self.premium_btn.setText(
                tr_catalog("page.about.button.premium_vpn", language=self._ui_language, default="Premium и VPN")
            )
        except Exception:
            pass

        try:
            self.update_subscription_status(self._sub_is_premium, self._sub_days_left)
        except Exception:
            pass

    def _rebuild_support_tab(self) -> None:
        self._clear_layout(self._support_layout)
        self._build_support_content(self._support_layout)

    def _rebuild_help_tab(self) -> None:
        self._clear_layout(self._help_layout)
        self._build_help_content(self._help_layout)

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 0: О программе
    # ─────────────────────────────────────────────────────────────────────────

    def _build_about_content(self, layout: QVBoxLayout):
        from config import APP_VERSION
        tokens = get_theme_tokens()

        # ── Версия ────────────────────────────────────────────────────────
        self.about_section_version_label = _make_section_label(
            tr_catalog("page.about.section.version", language=self._ui_language, default="Версия")
        )
        layout.addWidget(self.about_section_version_label)

        version_card = SettingsCard()
        version_layout = QHBoxLayout()
        version_layout.setSpacing(16)

        icon_label = QLabel()
        icon_label.setPixmap(qta.icon('fa5s.shield-alt', color=tokens.accent_hex).pixmap(40, 40))
        icon_label.setFixedSize(48, 48)
        version_layout.addWidget(icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        if _HAS_FLUENT:
            name_label = SubtitleLabel(
                tr_catalog("page.about.app_name", language=self._ui_language, default="Zapret 2 GUI")
            )
            version_label = CaptionLabel(
                tr_catalog(
                    "page.about.version.value_template",
                    language=self._ui_language,
                    default="Версия {version}",
                ).format(version=APP_VERSION)
            )
        else:
            name_label = QLabel(
                tr_catalog("page.about.app_name", language=self._ui_language, default="Zapret 2 GUI")
            )
            name_label.setStyleSheet(f"color: {tokens.fg}; font-size: 16px; font-weight: 600;")
            version_label = QLabel(
                tr_catalog(
                    "page.about.version.value_template",
                    language=self._ui_language,
                    default="Версия {version}",
                ).format(version=APP_VERSION)
            )
            version_label.setStyleSheet(f"color: {tokens.fg_muted}; font-size: 12px;")
        self.about_app_name_label = name_label
        text_layout.addWidget(name_label)
        self.about_version_value_label = version_label
        text_layout.addWidget(self.about_version_value_label)
        version_layout.addLayout(text_layout, 1)

        self.update_btn = ActionButton(
            tr_catalog("page.about.button.update_settings", language=self._ui_language, default="Настройка обновлений"),
            "fa5s.sync-alt",
        )
        self.update_btn.setFixedHeight(36)
        version_layout.addWidget(self.update_btn)

        version_card.add_layout(version_layout)
        layout.addWidget(version_card)

        layout.addSpacing(16)

        # ── Устройство ────────────────────────────────────────────────────
        self.about_section_device_label = _make_section_label(
            tr_catalog("page.about.section.device", language=self._ui_language, default="Устройство")
        )
        layout.addWidget(self.about_section_device_label)

        device_card = SettingsCard()
        device_layout = QHBoxLayout()
        device_layout.setSpacing(16)

        device_icon = QLabel()
        device_icon.setPixmap(qta.icon('fa5s.key', color=tokens.accent_hex).pixmap(20, 20))
        device_icon.setFixedSize(24, 24)
        device_layout.addWidget(device_icon)

        try:
            from tgram import get_client_id
            client_id = get_client_id()
        except Exception:
            client_id = ""

        device_text_layout = QVBoxLayout()
        device_text_layout.setSpacing(2)
        if _HAS_FLUENT:
            device_title = BodyLabel(tr_catalog("page.about.device.id", language=self._ui_language, default="ID устройства"))
            self.client_id_label = CaptionLabel(client_id or "—")
        else:
            device_title = QLabel(tr_catalog("page.about.device.id", language=self._ui_language, default="ID устройства"))
            device_title.setStyleSheet(f"color: {tokens.fg}; font-size: 13px; font-weight: 500;")
            self.client_id_label = QLabel(client_id or "—")
            self.client_id_label.setStyleSheet(f"color: {tokens.fg_muted}; font-size: 12px;")
        self.device_title_label = device_title
        self.client_id_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        device_text_layout.addWidget(self.device_title_label)
        device_text_layout.addWidget(self.client_id_label)
        device_layout.addLayout(device_text_layout, 1)

        self.copy_btn = ActionButton(
            tr_catalog("page.about.button.copy_id", language=self._ui_language, default="Копировать ID"),
            "fa5s.copy",
        )
        self.copy_btn.setFixedHeight(36)
        self.copy_btn.clicked.connect(self._copy_client_id)
        device_layout.addWidget(self.copy_btn)

        device_card.add_layout(device_layout)
        layout.addWidget(device_card)

        layout.addSpacing(16)

        # ── Подписка ──────────────────────────────────────────────────────
        self.about_section_subscription_label = _make_section_label(
            tr_catalog("page.about.section.subscription", language=self._ui_language, default="Подписка")
        )
        layout.addWidget(self.about_section_subscription_label)

        sub_card = SettingsCard()
        sub_layout = QVBoxLayout()
        sub_layout.setSpacing(12)

        sub_status_layout = QHBoxLayout()
        sub_status_layout.setSpacing(8)

        self.sub_status_icon = QLabel()
        self.sub_status_icon.setPixmap(qta.icon('fa5s.user', color=tokens.fg_faint).pixmap(18, 18))
        self.sub_status_icon.setFixedSize(22, 22)
        sub_status_layout.addWidget(self.sub_status_icon)

        if _HAS_FLUENT:
            self.sub_status_label = StrongBodyLabel(
                tr_catalog("page.about.subscription.free", language=self._ui_language, default="Free версия")
            )
        else:
            self.sub_status_label = QLabel(
                tr_catalog("page.about.subscription.free", language=self._ui_language, default="Free версия")
            )
            self.sub_status_label.setStyleSheet(f"color: {tokens.fg}; font-size: 13px; font-weight: 500;")
        sub_status_layout.addWidget(self.sub_status_label, 1)
        sub_layout.addLayout(sub_status_layout)

        if _HAS_FLUENT:
            self.sub_desc_label = CaptionLabel(
                tr_catalog(
                    "page.about.subscription.desc",
                    language=self._ui_language,
                    default="Подписка Zapret Premium открывает доступ к дополнительным темам, приоритетной поддержке и VPN-сервису.",
                )
            )
        else:
            self.sub_desc_label = QLabel(
                tr_catalog(
                    "page.about.subscription.desc",
                    language=self._ui_language,
                    default="Подписка Zapret Premium открывает доступ к дополнительным темам, приоритетной поддержке и VPN-сервису.",
                )
            )
            self.sub_desc_label.setStyleSheet(f"color: {tokens.fg_muted}; font-size: 11px;")
        self.sub_desc_label.setWordWrap(True)
        sub_layout.addWidget(self.sub_desc_label)

        sub_btns = QHBoxLayout()
        sub_btns.setSpacing(8)
        self.premium_btn = ActionButton(
            tr_catalog("page.about.button.premium_vpn", language=self._ui_language, default="Premium и VPN"),
            "fa5s.star",
            accent=True,
        )
        self.premium_btn.setFixedHeight(36)
        sub_btns.addWidget(self.premium_btn)
        sub_btns.addStretch()
        sub_layout.addLayout(sub_btns)

        sub_card.add_layout(sub_layout)
        layout.addWidget(sub_card)

        layout.addStretch()

    def _copy_client_id(self) -> None:
        try:
            cid = self.client_id_label.text().strip() if hasattr(self, "client_id_label") else ""
            if not cid or cid == "—":
                return
            QGuiApplication.clipboard().setText(cid)
        except Exception as e:
            log(f"Ошибка копирования ID: {e}", "DEBUG")

    def update_subscription_status(self, is_premium: bool, days: int | None = None):
        """Обновляет отображение статуса подписки"""
        self._sub_is_premium = bool(is_premium)
        self._sub_days_left = days

        tokens = get_theme_tokens()
        if is_premium:
            self.sub_status_icon.setPixmap(qta.icon('fa5s.star', color='#ffc107').pixmap(18, 18))
            if days:
                self.sub_status_label.setText(
                    tr_catalog(
                        "page.about.subscription.premium_days",
                        language=self._ui_language,
                        default="Premium (осталось {days} дней)",
                    ).format(days=days)
                )
            else:
                self.sub_status_label.setText(
                    tr_catalog(
                        "page.about.subscription.premium_active",
                        language=self._ui_language,
                        default="Premium активен",
                    )
                )
        else:
            self.sub_status_icon.setPixmap(qta.icon('fa5s.user', color=tokens.fg_faint).pixmap(18, 18))
            self.sub_status_label.setText(
                tr_catalog("page.about.subscription.free", language=self._ui_language, default="Free версия")
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 1: Поддержка
    # ─────────────────────────────────────────────────────────────────────────

    def _build_support_content(self, layout: QVBoxLayout):
        tokens = get_theme_tokens()

        # ── GitHub Discussions ────────────────────────────────────────────
        layout.addWidget(
            _make_section_label(
                tr_catalog(
                    "page.about.support.section.discussions",
                    language=self._ui_language,
                    default="GitHub Discussions",
                )
            )
        )

        support_card = SettingsCard()
        support_layout = QHBoxLayout()
        support_layout.setSpacing(16)

        icon_label = QLabel()
        icon_label.setPixmap(qta.icon("fa5b.github", color=tokens.accent_hex).pixmap(36, 36))
        icon_label.setFixedSize(44, 44)
        self._support_icon_label = icon_label
        support_layout.addWidget(icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        if _HAS_FLUENT:
            title = StrongBodyLabel(
                tr_catalog(
                    "page.about.support.discussions.title",
                    language=self._ui_language,
                    default="GitHub Discussions",
                )
            )
            title.setProperty("tone", "primary")
            text_layout.addWidget(title)
            desc = CaptionLabel(
                tr_catalog(
                    "page.about.support.discussions.desc",
                    language=self._ui_language,
                    default="Основной канал поддержки. Здесь можно задать вопрос, описать проблему и приложить материалы вручную.",
                )
            )
            desc.setWordWrap(True)
            desc.setProperty("tone", "muted")
            text_layout.addWidget(desc)
        else:
            title = QLabel(
                tr_catalog(
                    "page.about.support.discussions.title",
                    language=self._ui_language,
                    default="GitHub Discussions",
                )
            )
            text_layout.addWidget(title)
            desc = QLabel(
                tr_catalog(
                    "page.about.support.discussions.desc",
                    language=self._ui_language,
                    default="Основной канал поддержки. Здесь можно задать вопрос, описать проблему и приложить материалы вручную.",
                )
            )
            desc.setWordWrap(True)
            text_layout.addWidget(desc)

        support_layout.addLayout(text_layout, 1)

        support_btn = ActionButton(
            tr_catalog("page.about.support.discussions.button", language=self._ui_language, default="Открыть"),
            "fa5s.external-link-alt",
            accent=True,
        )
        support_btn.setProperty("noDrag", True)
        support_btn.setFixedHeight(36)
        support_btn.clicked.connect(self._open_support_discussions)
        support_layout.addWidget(support_btn)

        support_card.add_layout(support_layout)
        layout.addWidget(support_card)

        layout.addSpacing(16)

        # ── Каналы сообщества ─────────────────────────────────────────────
        layout.addWidget(
            _make_section_label(
                tr_catalog(
                    "page.about.support.section.community",
                    language=self._ui_language,
                    default="Каналы сообщества",
                )
            )
        )

        channels_card = SettingsCard()

        self.tg_row = SettingsRow(
            "fa5b.telegram",
            tr_catalog("page.about.support.telegram.title", language=self._ui_language, default="Telegram"),
            tr_catalog(
                "page.about.support.telegram.desc",
                language=self._ui_language,
                default="Быстрые вопросы и общение с сообществом",
            ),
        )
        self.tg_btn = ActionButton(
            tr_catalog("page.about.support.button.open", language=self._ui_language, default="Открыть"),
            "fa5s.external-link-alt",
            accent=False,
        )
        self.tg_btn.setProperty("noDrag", True)
        self.tg_btn.clicked.connect(self._open_telegram_support)
        self.tg_row.set_control(self.tg_btn)
        channels_card.add_widget(self.tg_row)

        self.dc_row = SettingsRow(
            "fa5b.discord",
            tr_catalog("page.about.support.discord.title", language=self._ui_language, default="Discord"),
            tr_catalog(
                "page.about.support.discord.desc",
                language=self._ui_language,
                default="Обсуждение и живое общение",
            ),
        )
        self.dc_btn = ActionButton(
            tr_catalog("page.about.support.button.open", language=self._ui_language, default="Открыть"),
            "fa5s.external-link-alt",
            accent=False,
        )
        self.dc_btn.setProperty("noDrag", True)
        self.dc_btn.clicked.connect(self._open_discord)
        self.dc_row.set_control(self.dc_btn)
        channels_card.add_widget(self.dc_row)

        layout.addWidget(channels_card)

        layout.addStretch()

    def _open_support_discussions(self) -> None:
        try:
            from config.urls import SUPPORT_DISCUSSIONS_URL

            webbrowser.open(SUPPORT_DISCUSSIONS_URL)
            log(f"Открыт GitHub Discussions: {SUPPORT_DISCUSSIONS_URL}", "INFO")
        except Exception as e:
            if InfoBar:
                InfoBar.warning(title="Ошибка", content=f"Не удалось открыть GitHub Discussions:\n{e}",
                                parent=self.window())

    def _open_telegram_support(self) -> None:
        try:
            from config.telegram_links import open_telegram_link
            open_telegram_link("zaprethelp")
            log("Открыт Telegram: zaprethelp", "INFO")
        except Exception as e:
            if InfoBar:
                InfoBar.warning(title="Ошибка", content=f"Не удалось открыть Telegram:\n{e}",
                                parent=self.window())

    def _open_discord(self) -> None:
        try:
            url = "https://discord.gg/kkcBDG2uws"
            webbrowser.open(url)
            log(f"Открыт Discord: {url}", "INFO")
        except Exception as e:
            if InfoBar:
                InfoBar.warning(title="Ошибка", content=f"Не удалось открыть Discord:\n{e}",
                                parent=self.window())

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 2: Справка
    # ─────────────────────────────────────────────────────────────────────────

    def _build_help_content(self, layout: QVBoxLayout):
        self._add_motto_block(layout)
        layout.addSpacing(6)
        layout.addWidget(_make_section_label(tr_catalog("page.about.help.section.links", language=self._ui_language, default="Ссылки")))

        try:
            from config.urls import INFO_URL, ANDROID_URL
        except Exception:
            INFO_URL = ""
            ANDROID_URL = ""

        if not _HAS_FLUENT:
            layout.addStretch()
            return

        # ── Документация ──────────────────────────────────────────────────
        docs_group = SettingCardGroup(
            tr_catalog("page.about.help.group.docs", language=self._ui_language, default="Документация"),
            self.content,
        )

        forum_card = PushSettingCard(
            tr_catalog("page.about.help.button.open", language=self._ui_language, default="Открыть"),
            FluentIcon.SEND,
            tr_catalog("page.about.help.docs.forum.title", language=self._ui_language, default="Сайт-форум для новичков"),
            tr_catalog("page.about.help.docs.forum.desc", language=self._ui_language, default="Авторизация через Telegram-бота"),
        )
        forum_card.clicked.connect(self._open_forum_for_beginners)

        info_card = HyperlinkCard(
            INFO_URL,
            tr_catalog("page.about.help.button.open", language=self._ui_language, default="Открыть"),
            FluentIcon.INFO,
            tr_catalog("page.about.help.docs.info.title", language=self._ui_language, default="Что это такое?"),
            tr_catalog("page.about.help.docs.info.desc", language=self._ui_language, default="Руководство и ответы на вопросы"),
        )

        folder_card = PushSettingCard(
            tr_catalog("page.about.help.button.open", language=self._ui_language, default="Открыть"),
            FluentIcon.FOLDER,
            tr_catalog("page.about.help.docs.folder.title", language=self._ui_language, default="Папка с инструкциями"),
            tr_catalog("page.about.help.docs.folder.desc", language=self._ui_language, default="Открыть локальную папку help"),
        )
        folder_card.clicked.connect(self._open_help_folder)

        android_card = HyperlinkCard(
            ANDROID_URL,
            tr_catalog("page.about.help.button.open", language=self._ui_language, default="Открыть"),
            FluentIcon.PHONE,
            tr_catalog("page.about.help.docs.android.title", language=self._ui_language, default="На Android (Magisk Zapret, ByeByeDPI и др.)"),
            tr_catalog("page.about.help.docs.android.desc", language=self._ui_language, default="Открыть инструкцию на сайте"),
        )

        github_card = HyperlinkCard(
            "https://github.com/youtubediscord/zapret",
            tr_catalog("page.about.help.button.open", language=self._ui_language, default="Открыть"),
            FluentIcon.GITHUB,
            "GitHub",
            tr_catalog("page.about.help.docs.github.desc", language=self._ui_language, default="Исходный код и документация"),
        )

        docs_group.addSettingCards([forum_card, info_card, folder_card, android_card, github_card])
        layout.addWidget(docs_group)
        layout.addSpacing(8)

        # ── Новости ───────────────────────────────────────────────────────
        news_group = SettingCardGroup(
            tr_catalog("page.about.help.group.news", language=self._ui_language, default="Новости"),
            self.content,
        )

        telegram_card = PushSettingCard(
            tr_catalog("page.about.help.button.open", language=self._ui_language, default="Открыть"),
            FluentIcon.MEGAPHONE,
            tr_catalog("page.about.help.news.telegram.title", language=self._ui_language, default="Telegram канал"),
            tr_catalog("page.about.help.news.telegram.desc", language=self._ui_language, default="Новости и обновления"),
        )
        telegram_card.clicked.connect(self._open_telegram_news)

        youtube_card = HyperlinkCard(
            "https://www.youtube.com/@приватность",
            tr_catalog("page.about.help.button.open", language=self._ui_language, default="Открыть"),
            FluentIcon.PLAY,
            tr_catalog("page.about.help.news.youtube.title", language=self._ui_language, default="YouTube канал"),
            tr_catalog("page.about.help.news.youtube.desc", language=self._ui_language, default="Видео и обновления"),
        )

        mastodon_card = HyperlinkCard(
            "https://mastodon.social/@zapret",
            tr_catalog("page.about.help.button.open", language=self._ui_language, default="Открыть"),
            FluentIcon.GLOBE,
            tr_catalog("page.about.help.news.mastodon.title", language=self._ui_language, default="Mastodon профиль"),
            tr_catalog("page.about.help.news.mastodon.desc", language=self._ui_language, default="Новости в Fediverse"),
        )

        bastyon_card = HyperlinkCard(
            "https://bastyon.com/zapretgui",
            tr_catalog("page.about.help.button.open", language=self._ui_language, default="Открыть"),
            FluentIcon.GLOBE,
            tr_catalog("page.about.help.news.bastyon.title", language=self._ui_language, default="Bastyon профиль"),
            tr_catalog("page.about.help.news.bastyon.desc", language=self._ui_language, default="Новости в Bastyon"),
        )

        news_group.addSettingCards([telegram_card, youtube_card, mastodon_card, bastyon_card])
        layout.addWidget(news_group)

        layout.addStretch()

    def _add_motto_block(self, layout: QVBoxLayout):
        tokens = get_theme_tokens()
        motto_wrap = QFrame()
        motto_wrap.setStyleSheet("QFrame { background: transparent; border: none; }")

        motto_row = QHBoxLayout(motto_wrap)
        motto_row.setContentsMargins(0, 0, 0, 0)
        motto_row.setSpacing(0)

        motto_text_wrap = QFrame()
        motto_text_wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        motto_text_wrap.setStyleSheet("QFrame { background: transparent; border: none; }")

        motto_text_layout = QVBoxLayout(motto_text_wrap)
        motto_text_layout.setContentsMargins(0, 0, 0, 0)
        motto_text_layout.setSpacing(2)

        motto_title = QLabel(
            tr_catalog(
                "page.about.help.motto.title",
                language=self._ui_language,
                default="keep thinking, keep searching, keep learning....",
            )
        )
        motto_title.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        motto_title.setWordWrap(True)
        motto_title.setStyleSheet(
            f"QLabel {{ color: {tokens.fg}; font-size: 25px; font-weight: 700; "
            f"letter-spacing: 0.8px; "
            f"font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif; }}"
        )

        motto_translate = QLabel(
            tr_catalog(
                "page.about.help.motto.subtitle",
                language=self._ui_language,
                default="Продолжай думать, продолжай искать, продолжай учиться....",
            )
        )
        motto_translate.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        motto_translate.setWordWrap(True)
        motto_translate.setStyleSheet(
            f"QLabel {{ color: {tokens.fg_muted}; font-size: 17px; font-style: italic; "
            f"font-weight: 600; letter-spacing: 0.5px; "
            f"font-family: 'Palatino Linotype', 'Book Antiqua', 'Georgia', serif; "
            f"padding-top: 2px; }}"
        )

        motto_cta = QLabel(
            tr_catalog(
                "page.about.help.motto.cta",
                language=self._ui_language,
                default="Zapret2 - думай свободно, ищи смелее, учись всегда.",
            )
        )
        motto_cta.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        motto_cta.setWordWrap(True)
        motto_cta.setStyleSheet(
            f"QLabel {{ color: {tokens.fg_faint}; font-size: 12px; letter-spacing: 1.1px; "
            f"font-family: 'Segoe UI', sans-serif; text-transform: uppercase; "
            f"padding-top: 6px; }}"
        )

        motto_text_layout.addWidget(motto_title)
        motto_text_layout.addWidget(motto_translate)
        motto_text_layout.addWidget(motto_cta)
        motto_row.addWidget(motto_text_wrap, 1)
        layout.addWidget(motto_wrap)

    def _open_forum_for_beginners(self):
        try:
            from config.telegram_links import open_telegram_link
            open_telegram_link("bypassblock", post=1359)
            log("Открыт пост: bypassblock/1359", "INFO")
        except Exception as e:
            if InfoBar:
                InfoBar.warning(title="Ошибка", content=f"Не удалось открыть Telegram:\n{e}",
                                parent=self.window())

    def _open_help_folder(self):
        try:
            from config import HELP_FOLDER
            if os.path.exists(HELP_FOLDER):
                subprocess.Popen(f'explorer "{HELP_FOLDER}"')
                log(f"Открыта папка: {HELP_FOLDER}", "INFO")
            else:
                if InfoBar:
                    InfoBar.warning(title="Ошибка", content="Папка с инструкциями не найдена",
                                    parent=self.window())
        except Exception as e:
            if InfoBar:
                InfoBar.warning(title="Ошибка", content=f"Не удалось открыть папку:\n{e}",
                                parent=self.window())

    def _open_telegram_news(self):
        try:
            from config.telegram_links import open_telegram_link
            open_telegram_link("bypassblock")
            log("Открыт Telegram: bypassblock", "INFO")
        except Exception as e:
            if InfoBar:
                InfoBar.warning(title="Ошибка", content=f"Не удалось открыть Telegram:\n{e}",
                                parent=self.window())

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 3: Zapret KVN
    # ─────────────────────────────────────────────────────────────────────────

    def _rebuild_kvn_tab(self) -> None:
        self._clear_layout(self._kvn_layout)
        self._build_kvn_content(self._kvn_layout)

    def _build_kvn_content(self, layout: QVBoxLayout):
        tokens = get_theme_tokens()

        # ── Hero-баннер ────────────────────────────────────────────────────
        hero_wrap = QFrame()
        hero_wrap.setStyleSheet("QFrame { background: transparent; border: none; }")

        hero_layout = QVBoxLayout(hero_wrap)
        hero_layout.setContentsMargins(0, 8, 0, 0)
        hero_layout.setSpacing(4)

        hero_icon = QLabel()
        hero_icon.setPixmap(qta.icon("fa5s.globe-americas", color=tokens.accent_hex).pixmap(48, 48))
        hero_icon.setFixedSize(56, 56)
        hero_layout.addWidget(hero_icon)

        if _HAS_FLUENT:
            hero_title = SubtitleLabel("Zapret KVN")
        else:
            hero_title = QLabel("Zapret KVN")
            hero_title.setStyleSheet(f"color: {tokens.fg}; font-size: 20px; font-weight: 700;")
        hero_title.setProperty("tone", "primary")
        hero_layout.addWidget(hero_title)

        subtitle = QLabel("Уникальный туннель до любой страны мира")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            f"QLabel {{ color: {tokens.fg}; font-size: 15px; font-weight: 600; "
            f"font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif; }}"
        )
        hero_layout.addWidget(subtitle)

        desc = QLabel("Создан передовыми мировыми инженерами (не является тем чем вы думаете)")
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"QLabel {{ color: {tokens.fg_muted}; font-size: 12px; font-style: italic; "
            f"font-family: 'Palatino Linotype', 'Book Antiqua', 'Georgia', serif; "
            f"padding-top: 2px; }}"
        )
        hero_layout.addWidget(desc)

        layout.addWidget(hero_wrap)
        layout.addSpacing(8)

        # ── Возможности ────────────────────────────────────────────────────
        layout.addWidget(_make_section_label("Возможности"))

        features_card = SettingsCard()

        yt_row = SettingsRow(
            "fa5s.rocket",
            "Ускорение YouTube и Discord",
            "Позволяет ускорить замедленные сервера в случае если те перестали работать и начали деградировать",
        )
        features_card.add_widget(yt_row)

        game_row = SettingsRow(
            "fa5s.gamepad",
            "Игровые серверы",
            "Также подходит для ускорения игровых серверов",
        )
        features_card.add_widget(game_row)

        layout.addWidget(features_card)
        layout.addSpacing(16)

        # ── Ссылки ─────────────────────────────────────────────────────────
        layout.addWidget(_make_section_label("Ссылки"))

        links_card = SettingsCard()

        tg_row = SettingsRow(
            "fa5b.telegram",
            "Канал Zapret KVN",
            "Новости и обновления",
        )
        tg_btn = ActionButton("Открыть", "fa5s.external-link-alt", accent=False)
        tg_btn.setProperty("noDrag", True)
        tg_btn.setFixedHeight(36)
        tg_btn.clicked.connect(self._open_kvn_channel)
        tg_row.set_control(tg_btn)
        links_card.add_widget(tg_row)

        bot_row = SettingsRow(
            "fa5s.shopping-cart",
            "Купить подписку",
            "Оформление через Telegram-бота @zapretvpns_bot",
        )
        bot_btn = ActionButton("Купить", "fa5s.star", accent=True)
        bot_btn.setProperty("noDrag", True)
        bot_btn.setFixedHeight(36)
        bot_btn.clicked.connect(self._open_kvn_bot)
        bot_row.set_control(bot_btn)
        links_card.add_widget(bot_row)

        bypass_row = SettingsRow(
            "fa5b.telegram",
            "Канал BypassBlock",
            "Второй канал с новостями",
        )
        bypass_btn = ActionButton("Открыть", "fa5s.external-link-alt", accent=False)
        bypass_btn.setProperty("noDrag", True)
        bypass_btn.setFixedHeight(36)
        bypass_btn.clicked.connect(self._open_kvn_bypass)
        bypass_row.set_control(bypass_btn)
        links_card.add_widget(bypass_row)

        gh_row = SettingsRow(
            "fa5b.github",
            "Исходный код",
            "GitHub репозиторий Zapret KVN",
        )
        gh_btn = ActionButton("Открыть", "fa5s.external-link-alt", accent=False)
        gh_btn.setProperty("noDrag", True)
        gh_btn.setFixedHeight(36)
        gh_btn.clicked.connect(self._open_kvn_github)
        gh_row.set_control(gh_btn)
        links_card.add_widget(gh_row)

        layout.addWidget(links_card)

        layout.addStretch()

    def _open_kvn_channel(self):
        try:
            from config.telegram_links import open_telegram_link
            open_telegram_link("vpndiscordyooutube")
            log("Открыт Telegram: vpndiscordyooutube", "INFO")
        except Exception as e:
            if InfoBar:
                InfoBar.warning(title="Ошибка", content=f"Не удалось открыть Telegram:\n{e}",
                                parent=self.window())

    def _open_kvn_bot(self):
        try:
            from config.telegram_links import open_telegram_link
            open_telegram_link("zapretvpns_bot")
            log("Открыт Telegram: zapretvpns_bot", "INFO")
        except Exception as e:
            if InfoBar:
                InfoBar.warning(title="Ошибка", content=f"Не удалось открыть Telegram:\n{e}",
                                parent=self.window())

    def _open_kvn_bypass(self):
        try:
            from config.telegram_links import open_telegram_link
            open_telegram_link("bypassblock")
            log("Открыт Telegram: bypassblock", "INFO")
        except Exception as e:
            if InfoBar:
                InfoBar.warning(title="Ошибка", content=f"Не удалось открыть Telegram:\n{e}",
                                parent=self.window())

    def _open_kvn_github(self):
        try:
            webbrowser.open("https://github.com/youtubediscord/zapret-kvn")
            log("Открыт GitHub: zapret-kvn", "INFO")
        except Exception as e:
            if InfoBar:
                InfoBar.warning(title="Ошибка", content=f"Не удалось открыть GitHub:\n{e}",
                                parent=self.window())

    # ─────────────────────────────────────────────────────────────────────────
    # Theme
    # ─────────────────────────────────────────────────────────────────────────

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()
        if self._support_icon_label is not None:
            try:
                self._support_icon_label.setPixmap(
                    qta.icon("fa5b.github", color=tokens.accent_hex).pixmap(36, 36)
                )
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────────────
    # showEvent
    # ─────────────────────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
