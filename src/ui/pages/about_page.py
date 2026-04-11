# ui/pages/about_page.py
"""Страница О программе — версия, подписка, поддержка, справка"""

from __future__ import annotations

import qtawesome as qta
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget,
    QFrame, QSizePolicy, QLayout,
)

from .base_page import BasePage
from ui.about_page_controller import AboutPageController
from ui.compat_widgets import SettingsCard
from ui.main_window_state import AppUiState, MainWindowStateStore
from ui.text_catalog import tr as tr_catalog
from ui.theme import get_theme_tokens
from log import log

from qfluentwidgets import (
    SubtitleLabel,
    BodyLabel,
    StrongBodyLabel,
    CaptionLabel,
    SegmentedWidget,
    InfoBar,
    HyperlinkCard,
    PushSettingCard,
    PrimaryPushSettingCard,
    SettingCard,
    SettingCardGroup,
    FluentIcon,
    PushButton,
    PrimaryPushButton,
)

def _make_section_label(text: str, parent: QWidget | None = None) -> QLabel:
    """Создаёт заголовок секции для использования внутри sub-layout."""
    lbl = StrongBodyLabel(text, parent)
    lbl.setProperty("tone", "primary")
    return lbl


class AboutPage(BasePage):
    """Страница О программе с вкладками: О программе / Поддержка / Справка"""

    open_premium_requested = pyqtSignal()
    open_updates_requested = pyqtSignal()

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
        self._support_discussions_card = None
        self._support_telegram_card = None
        self._support_discord_card = None

        # Tab lazy init flags
        self._support_tab_initialized = False
        self._help_tab_initialized = False
        self._kvn_tab_initialized = False

        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._pending_tab_key: str | None = None

        self._build_ui()
        self.set_ui_language(self._ui_language)

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

    def _apply_pending_tab_if_ready(self) -> None:
        pending_tab_key = str(getattr(self, "_pending_tab_key", "") or "").strip().lower()
        if not pending_tab_key:
            return
        if not self.is_page_ready():
            return
        self._pending_tab_key = None
        index = AboutPageController.resolve_tab_index(pending_tab_key)
        if index is not None:
            self._switch_tab(index)

    def _switch_tab(self, index: int):
        plan = AboutPageController.build_tab_switch_plan(
            index=index,
            support_initialized=self._support_tab_initialized,
            help_initialized=self._help_tab_initialized,
            kvn_initialized=self._kvn_tab_initialized,
        )
        if plan.init_support:
            self._support_tab_initialized = True
            try:
                self._build_support_content(self._support_layout)
            except Exception as e:
                log(f"Ошибка построения вкладки поддержки: {e}", "ERROR")

        if plan.init_help:
            self._help_tab_initialized = True
            try:
                self._build_help_content(self._help_layout)
            except Exception as e:
                log(f"Ошибка построения вкладки справки: {e}", "ERROR")

        if plan.init_kvn:
            self._kvn_tab_initialized = True
            try:
                self._build_kvn_content(self._kvn_layout)
            except Exception as e:
                log(f"Ошибка построения вкладки KVN: {e}", "ERROR")

        self.stacked_widget.setCurrentIndex(plan.current_index)

        try:
            self.tabs_pivot.setCurrentItem(plan.route_key)
        except Exception:
            pass

    def switch_to_tab(self, key: str) -> None:
        """External API: switch to About/Support/Help tab by key."""
        index = AboutPageController.resolve_tab_index(key)
        if index is None:
            return
        if not self.is_page_ready():
            self._pending_tab_key = AboutPageController.TAB_KEYS[index]
            self.run_when_page_ready(self._apply_pending_tab_if_ready)
            return
        self._pending_tab_key = None
        self._switch_tab(index)

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

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
            self.update_subscription_status(*self._current_subscription_state())
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
        self.about_app_name_label = name_label
        text_layout.addWidget(name_label)
        self.about_version_value_label = version_label
        text_layout.addWidget(self.about_version_value_label)
        version_layout.addLayout(text_layout, 1)

        self.update_btn = PushButton()
        self.update_btn.setText(
            tr_catalog("page.about.button.update_settings", language=self._ui_language, default="Настройка обновлений")
        )
        self.update_btn.setIcon(qta.icon("fa5s.sync-alt", color=tokens.accent_hex))
        self.update_btn.setFixedHeight(36)
        self.update_btn.clicked.connect(self.open_updates_requested.emit)
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

        client_id = AboutPageController.get_client_id()

        device_text_layout = QVBoxLayout()
        device_text_layout.setSpacing(2)
        device_title = BodyLabel(tr_catalog("page.about.device.id", language=self._ui_language, default="ID устройства"))
        self.client_id_label = CaptionLabel(client_id or "—")
        self.device_title_label = device_title
        self.client_id_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        device_text_layout.addWidget(self.device_title_label)
        device_text_layout.addWidget(self.client_id_label)
        device_layout.addLayout(device_text_layout, 1)

        self.copy_btn = PushButton()
        self.copy_btn.setText(
            tr_catalog("page.about.button.copy_id", language=self._ui_language, default="Копировать ID")
        )
        self.copy_btn.setIcon(qta.icon("fa5s.copy", color=tokens.accent_hex))
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

        self.sub_status_label = StrongBodyLabel(
            tr_catalog("page.about.subscription.free", language=self._ui_language, default="Free версия")
        )
        sub_status_layout.addWidget(self.sub_status_label, 1)
        sub_layout.addLayout(sub_status_layout)

        self.sub_desc_label = CaptionLabel(
            tr_catalog(
                "page.about.subscription.desc",
                language=self._ui_language,
                default="Подписка Zapret Premium открывает доступ к дополнительным темам, приоритетной поддержке и VPN-сервису.",
            )
        )
        self.sub_desc_label.setWordWrap(True)
        sub_layout.addWidget(self.sub_desc_label)

        sub_btns = QHBoxLayout()
        sub_btns.setSpacing(8)
        self.premium_btn = PrimaryPushButton()
        self.premium_btn.setText(
            tr_catalog("page.about.button.premium_vpn", language=self._ui_language, default="Premium и VPN")
        )
        self.premium_btn.setIcon(qta.icon("fa5s.star", color="#ffc107"))
        self.premium_btn.setFixedHeight(36)
        self.premium_btn.clicked.connect(self.open_premium_requested.emit)
        sub_btns.addWidget(self.premium_btn)
        sub_btns.addStretch()
        sub_layout.addLayout(sub_btns)

        sub_card.add_layout(sub_layout)
        layout.addWidget(sub_card)

        layout.addStretch()

    def _copy_client_id(self) -> None:
        cid = self.client_id_label.text().strip() if hasattr(self, "client_id_label") else ""
        AboutPageController.copy_client_id(cid)

    def update_subscription_status(self, is_premium: bool, days: int | None = None):
        """Обновляет отображение статуса подписки"""
        tokens = get_theme_tokens()
        plan = AboutPageController.build_subscription_status_plan(
            is_premium=is_premium,
            days=days,
            free_text=tr_catalog("page.about.subscription.free", language=self._ui_language, default="Free версия"),
            premium_active_text=tr_catalog(
                "page.about.subscription.premium_active",
                language=self._ui_language,
                default="Premium активен",
            ),
            premium_days_template=tr_catalog(
                "page.about.subscription.premium_days",
                language=self._ui_language,
                default="Premium (осталось {days} дней)",
            ),
            free_icon_color=tokens.fg_faint,
            premium_icon_color="#ffc107",
        )
        self.sub_status_icon.setPixmap(qta.icon(plan.icon_name, color=plan.icon_color).pixmap(18, 18))
        self.sub_status_label.setText(plan.label_text)

    def _current_subscription_state(self) -> tuple[bool, int | None]:
        store = self._ui_state_store
        if store is not None:
            try:
                snapshot = store.snapshot()
                return bool(snapshot.subscription_is_premium), snapshot.subscription_days_remaining
            except Exception:
                pass
        return False, None

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 1: Поддержка
    # ─────────────────────────────────────────────────────────────────────────

    def _build_support_content(self, layout: QVBoxLayout):
        self._support_icon_label = None
        self._support_discussions_card = None
        self._support_telegram_card = None
        self._support_discord_card = None
        tokens = get_theme_tokens()

        discussions_group = SettingCardGroup(
            tr_catalog(
                "page.about.support.section.discussions",
                language=self._ui_language,
                default="GitHub Discussions",
            ),
            self.content,
        )
        self._support_discussions_card = PrimaryPushSettingCard(
            tr_catalog("page.about.support.discussions.button", language=self._ui_language, default="Открыть"),
            qta.icon("fa5b.github", color=tokens.accent_hex),
            tr_catalog(
                "page.about.support.discussions.title",
                language=self._ui_language,
                default="GitHub Discussions",
            ),
            tr_catalog(
                "page.about.support.discussions.desc",
                language=self._ui_language,
                default="Основной канал поддержки. Здесь можно задать вопрос, описать проблему и приложить материалы вручную.",
            ),
        )
        self._support_discussions_card.clicked.connect(self._open_support_discussions)
        discussions_group.addSettingCard(self._support_discussions_card)
        layout.addWidget(discussions_group)

        layout.addSpacing(16)

        community_group = SettingCardGroup(
            tr_catalog(
                "page.about.support.section.community",
                language=self._ui_language,
                default="Каналы сообщества",
            ),
            self.content,
        )
        self._support_telegram_card = PushSettingCard(
            tr_catalog("page.about.support.button.open", language=self._ui_language, default="Открыть"),
            qta.icon("fa5b.telegram", color="#229ED9"),
            tr_catalog("page.about.support.telegram.title", language=self._ui_language, default="Telegram"),
            tr_catalog(
                "page.about.support.telegram.desc",
                language=self._ui_language,
                default="Быстрые вопросы и общение с сообществом",
            ),
        )
        self._support_telegram_card.clicked.connect(self._open_telegram_support)

        self._support_discord_card = PushSettingCard(
            tr_catalog("page.about.support.button.open", language=self._ui_language, default="Открыть"),
            qta.icon("fa5b.discord", color="#5865F2"),
            tr_catalog("page.about.support.discord.title", language=self._ui_language, default="Discord"),
            tr_catalog(
                "page.about.support.discord.desc",
                language=self._ui_language,
                default="Обсуждение и живое общение",
            ),
        )
        self._support_discord_card.clicked.connect(self._open_discord)

        community_group.addSettingCards([
            self._support_telegram_card,
            self._support_discord_card,
        ])
        layout.addWidget(community_group)

        layout.addStretch()

    def _open_support_discussions(self) -> None:
        result = AboutPageController.open_support_discussions()
        if (not result.ok) and InfoBar:
            InfoBar.warning(title="Ошибка", content=f"Не удалось открыть GitHub Discussions:\n{result.message}",
                            parent=self.window())

    def _open_telegram_support(self) -> None:
        result = AboutPageController.open_telegram("zaprethelp")
        if (not result.ok) and InfoBar:
            InfoBar.warning(title="Ошибка", content=f"Не удалось открыть Telegram:\n{result.message}",
                            parent=self.window())

    def _open_discord(self) -> None:
        result = AboutPageController.open_discord("https://discord.gg/kkcBDG2uws")
        if (not result.ok) and InfoBar:
            InfoBar.warning(title="Ошибка", content=f"Не удалось открыть Discord:\n{result.message}",
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
        result = AboutPageController.open_telegram("bypassblock", post=1359)
        if (not result.ok) and InfoBar:
            InfoBar.warning(title="Ошибка", content=f"Не удалось открыть Telegram:\n{result.message}",
                            parent=self.window())

    def _open_help_folder(self):
        result = AboutPageController.open_help_folder()
        if (not result.ok) and InfoBar:
            if result.message == "Папка с инструкциями не найдена":
                InfoBar.warning(title="Ошибка", content=result.message, parent=self.window())
            else:
                InfoBar.warning(title="Ошибка", content=f"Не удалось открыть папку:\n{result.message}",
                                parent=self.window())

    def _open_telegram_news(self):
        result = AboutPageController.open_telegram("bypassblock")
        if (not result.ok) and InfoBar:
            InfoBar.warning(title="Ошибка", content=f"Не удалось открыть Telegram:\n{result.message}",
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

        hero_title = SubtitleLabel("Zapret KVN")
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
        features_group = SettingCardGroup("Возможности", self.content)

        yt_card = SettingCard(
            qta.icon("fa5s.rocket", color=tokens.accent_hex),
            "Ускорение YouTube и Discord",
            "Позволяет ускорить замедленные сервера в случае если те перестали работать и начали деградировать",
            self.content,
        )
        game_card = SettingCard(
            qta.icon("fa5s.gamepad", color="#4CAF50"),
            "Игровые серверы",
            "Также подходит для ускорения игровых серверов",
            self.content,
        )
        features_group.addSettingCards([yt_card, game_card])
        layout.addWidget(features_group)
        layout.addSpacing(16)

        # ── Ссылки ─────────────────────────────────────────────────────────
        links_group = SettingCardGroup("Ссылки", self.content)

        tg_card = PushSettingCard(
            "Открыть",
            qta.icon("fa5b.telegram", color="#229ED9"),
            "Канал Zapret KVN",
            "Новости и обновления",
        )
        tg_card.clicked.connect(self._open_kvn_channel)

        bot_card = PrimaryPushSettingCard(
            "Купить",
            qta.icon("fa5s.shopping-cart", color="#f59e0b"),
            "Купить подписку",
            "Оформление через Telegram-бота @zapretvpns_bot",
        )
        bot_card.clicked.connect(self._open_kvn_bot)

        bypass_card = PushSettingCard(
            "Открыть",
            qta.icon("fa5b.telegram", color="#229ED9"),
            "Канал BypassBlock",
            "Второй канал с новостями",
        )
        bypass_card.clicked.connect(self._open_kvn_bypass)

        gh_card = PushSettingCard(
            "Открыть",
            qta.icon("fa5b.github", color=tokens.accent_hex),
            "Исходный код",
            "GitHub репозиторий Zapret KVN",
        )
        gh_card.clicked.connect(self._open_kvn_github)

        links_group.addSettingCards([tg_card, bot_card, bypass_card, gh_card])
        layout.addWidget(links_group)

        layout.addStretch()

    def _open_kvn_channel(self):
        result = AboutPageController.open_telegram("vpndiscordyooutube")
        if (not result.ok) and InfoBar:
            InfoBar.warning(title="Ошибка", content=f"Не удалось открыть Telegram:\n{result.message}",
                            parent=self.window())

    def _open_kvn_bot(self):
        result = AboutPageController.open_telegram("zapretvpns_bot")
        if (not result.ok) and InfoBar:
            InfoBar.warning(title="Ошибка", content=f"Не удалось открыть Telegram:\n{result.message}",
                            parent=self.window())

    def _open_kvn_bypass(self):
        result = AboutPageController.open_telegram("bypassblock")
        if (not result.ok) and InfoBar:
            InfoBar.warning(title="Ошибка", content=f"Не удалось открыть Telegram:\n{result.message}",
                            parent=self.window())

    def _open_kvn_github(self):
        result = AboutPageController.open_github("https://github.com/youtubediscord/zapret-kvn")
        if (not result.ok) and InfoBar:
            InfoBar.warning(title="Ошибка", content=f"Не удалось открыть GitHub:\n{result.message}",
                            parent=self.window())

    # ─────────────────────────────────────────────────────────────────────────
    # Theme
    # ─────────────────────────────────────────────────────────────────────────

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()
        if self._support_discussions_card is not None:
            try:
                self._support_discussions_card.iconLabel.setIcon(
                    qta.icon("fa5b.github", color=tokens.accent_hex)
                )
            except Exception:
                pass
        if self._support_telegram_card is not None:
            try:
                self._support_telegram_card.iconLabel.setIcon(
                    qta.icon("fa5b.telegram", color="#229ED9")
                )
            except Exception:
                pass
        if self._support_discord_card is not None:
            try:
                self._support_discord_card.iconLabel.setIcon(
                    qta.icon("fa5b.discord", color="#5865F2")
                )
            except Exception:
                pass
        if self._support_icon_label is not None:
            try:
                self._support_icon_label.setPixmap(
                    qta.icon("fa5b.github", color=tokens.accent_hex).pixmap(36, 36)
                )
            except Exception:
                pass
