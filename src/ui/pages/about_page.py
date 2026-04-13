# ui/pages/about_page.py
"""Страница О программе — версия, подписка, поддержка, справка"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QSizePolicy, QLayout,
)

from .base_page import BasePage
from ui.about_page_controller import AboutPageController
from ui.pages.about_page_about_build import build_about_page_about_content
from ui.pages.about_page_help_build import build_about_page_help_content
from ui.pages.about_page_kvn_build import build_about_page_kvn_content
from ui.pages.about_page_support_build import build_about_page_support_content
from ui.pages.about_page_tabs_build import build_about_page_tabs
from app_state.main_window_state import AppUiState, MainWindowStateStore
from ui.text_catalog import tr as tr_catalog
from ui.theme import get_cached_qta_pixmap, get_theme_tokens, get_themed_qta_icon
from log.log import log


from qfluentwidgets import (
    StrongBodyLabel,
    InfoBar,
    HyperlinkCard,
    PushSettingCard,
    SettingCardGroup,
    FluentIcon,
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
        self._cleanup_in_progress = False

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
        if self._cleanup_in_progress:
            return
        self.update_subscription_status(
            state.subscription_is_premium,
            state.subscription_days_remaining,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # UI building
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        tabs_widgets = build_about_page_tabs(
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            on_switch_tab=self._switch_tab,
        )
        self.tabs_pivot = tabs_widgets.tabs_pivot
        self.add_widget(self.tabs_pivot)

        self.stacked_widget = tabs_widgets.stacked_widget
        self._about_tab = tabs_widgets.about_tab
        self._support_tab = tabs_widgets.support_tab
        self._help_tab = tabs_widgets.help_tab
        self._kvn_tab = tabs_widgets.kvn_tab
        self._support_layout = tabs_widgets.support_layout
        self._help_layout = tabs_widgets.help_layout
        self._kvn_layout = tabs_widgets.kvn_layout
        self._build_about_content(tabs_widgets.about_layout)

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
        if self._cleanup_in_progress:
            return
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
            from config.build_info import APP_VERSION


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
        from config.build_info import APP_VERSION

        tokens = get_theme_tokens()
        widgets = build_about_page_about_content(
            layout,
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            tokens=tokens,
            app_version=APP_VERSION,
            client_id=AboutPageController.get_client_id(),
            make_section_label=lambda text: _make_section_label(text),
            on_open_updates=self.open_updates_requested.emit,
            on_copy_client_id=self._copy_client_id,
            on_open_premium=self.open_premium_requested.emit,
        )
        self.about_section_version_label = widgets.about_section_version_label
        self.about_app_name_label = widgets.about_app_name_label
        self.about_version_value_label = widgets.about_version_value_label
        self.update_btn = widgets.update_btn
        self.about_section_device_label = widgets.about_section_device_label
        self.device_title_label = widgets.device_title_label
        self.client_id_label = widgets.client_id_label
        self.copy_btn = widgets.copy_btn
        self.about_section_subscription_label = widgets.about_section_subscription_label
        self.sub_status_icon = widgets.sub_status_icon
        self.sub_status_label = widgets.sub_status_label
        self.sub_desc_label = widgets.sub_desc_label
        self.premium_btn = widgets.premium_btn

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
        self.sub_status_icon.setPixmap(get_cached_qta_pixmap(plan.icon_name, color=plan.icon_color, size=18))
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
        widgets = build_about_page_support_content(
            layout,
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            content_parent=self.content,
            tokens=tokens,
            on_open_discussions=self._open_support_discussions,
            on_open_telegram=self._open_telegram_support,
            on_open_discord=self._open_discord,
        )
        self._support_discussions_card = widgets.discussions_card
        self._support_telegram_card = widgets.telegram_card
        self._support_discord_card = widgets.discord_card

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
        build_about_page_help_content(
            layout,
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            tokens=get_theme_tokens(),
            content_parent=self.content,
            make_section_label=lambda text: _make_section_label(text),
            hyperlink_card_cls=HyperlinkCard,
            push_setting_card_cls=PushSettingCard,
            setting_card_group_cls=SettingCardGroup,
            fluent_icon=FluentIcon,
            on_open_forum=self._open_forum_for_beginners,
            on_open_help_folder=self._open_help_folder,
            on_open_telegram_news=self._open_telegram_news,
        )

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
        build_about_page_kvn_content(
            layout,
            tokens=get_theme_tokens(),
            content_parent=self.content,
            on_open_kvn_channel=self._open_kvn_channel,
            on_open_kvn_bot=self._open_kvn_bot,
            on_open_kvn_bypass=self._open_kvn_bypass,
            on_open_kvn_github=self._open_kvn_github,
        )

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
                    get_themed_qta_icon("fa5b.github", color=tokens.accent_hex)
                )
            except Exception:
                pass
        if self._support_telegram_card is not None:
            try:
                self._support_telegram_card.iconLabel.setIcon(
                    get_themed_qta_icon("fa5b.telegram", color="#229ED9")
                )
            except Exception:
                pass
        if self._support_discord_card is not None:
            try:
                self._support_discord_card.iconLabel.setIcon(
                    get_themed_qta_icon("fa5b.discord", color="#5865F2")
                )
            except Exception:
                pass
        if self._support_icon_label is not None:
            try:
                self._support_icon_label.setPixmap(
                    get_cached_qta_pixmap("fa5b.github", color=tokens.accent_hex, size=36)
                )
            except Exception:
                pass

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        self._pending_tab_key = None

        unsubscribe = getattr(self, "_ui_state_unsubscribe", None)
        if callable(unsubscribe):
            try:
                unsubscribe()
            except Exception:
                pass
        self._ui_state_unsubscribe = None
        self._ui_state_store = None
