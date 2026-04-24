# updater/ui/page.py
"""Страница мониторинга серверов обновлений"""

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
)
import qtawesome as qta

from ui.pages.base_page import BasePage
from ui.compat_widgets import SettingsCard, ActionButton
from ui.theme import get_theme_tokens
from ui.text_catalog import tr as tr_catalog
from updater.update_page_controller import UpdatePageController
from updater.server_status_table_state import ServerStatusTableState
from updater.update_page_view_controller import UpdatePageViewController
from updater.ui.main_build import (
    build_servers_header_widgets,
    build_servers_table_widget,
)
from updater.ui.language import apply_servers_page_language
from updater.ui.table_workflow import (
    refresh_server_rows,
    render_server_row,
    reset_server_rows as reset_servers_table_rows,
    upsert_server_status as upsert_server_table_status,
)
from updater.ui.settings_build import (
    build_servers_settings_section,
    build_servers_telegram_section,
)
from ui.widgets.win11_controls import Win11ToggleRow

try:
    from qfluentwidgets import (
        BodyLabel, CaptionLabel,
        PushButton,
        SwitchButton,
        PushSettingCard, SettingCardGroup,
    )
    _HAS_FLUENT = True
except ImportError:
    from PyQt6.QtWidgets import QPushButton, QCheckBox
    BodyLabel = QLabel
    CaptionLabel = QLabel
    PushButton = QPushButton
    SwitchButton = QCheckBox  # type: ignore[assignment]
    PushSettingCard = None  # type: ignore[assignment]
    SettingCardGroup = None  # type: ignore[assignment]
    _HAS_FLUENT = False

from config.build_info import APP_VERSION, CHANNEL

from updater.ui.update_card import UpdateStatusCard
from updater.ui.changelog_card import ChangelogCard



# ═══════════════════════════════════════════════════════════════════════════════
# ИНДЕТЕРМИНИРОВАННАЯ КНОПКА С ПРОГРЕСС-КОЛЬЦОМ (аналог IndeterminateProgressPushButton Pro)
# ═══════════════════════════════════════════════════════════════════════════════

class ServersPage(BasePage):
    """Страница мониторинга серверов обновлений"""

    update_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(
            "Серверы",
            "Мониторинг серверов обновлений",
            parent,
            title_key="page.servers.title",
            subtitle_key="page.servers.subtitle",
        )

        self._tokens = get_theme_tokens()
        self._server_table_state = ServerStatusTableState()
        self._update_controller = UpdatePageController(self)
        self._runtime_initialized = False
        self._cleanup_in_progress = False

        self._build_ui()
        self._apply_page_theme(force=True)
        self._run_runtime_init_once()

    def _tr(self, key: str, default: str) -> str:
        return tr_catalog(key, language=self._ui_language, default=default)

    def _run_runtime_init_once(self) -> None:
        plan = self._update_controller.build_page_init_plan(
            runtime_initialized=self._runtime_initialized,
        )
        if not plan.should_apply_idle_view_state:
            return
        self._runtime_initialized = True
        QTimer.singleShot(
            0,
            lambda action=plan.view_action, elapsed=plan.elapsed_seconds: (not self._cleanup_in_progress) and self._update_controller.apply_idle_view_state(
                view_action=action,
                elapsed_seconds=elapsed,
            ),
        )

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        self._tokens = tokens or get_theme_tokens()
        tokens = self._tokens

        if hasattr(self, "servers_table"):
            try:
                accent_qcolor = QColor(tokens.accent_hex)
                for r in range(self.servers_table.rowCount()):
                    item = self.servers_table.item(r, 0)
                    if item and (item.text() or "").lstrip().startswith("⭐"):
                        item.setForeground(accent_qcolor)
            except Exception:
                pass

    def _render_server_row(self, row: int, server_name: str, status: dict) -> None:
        render_server_row(
            self.servers_table,
            row=row,
            server_name=server_name,
            status=status,
            channel=CHANNEL,
            language=self._ui_language,
            accent_hex=self._tokens.accent_hex,
        )

    def _refresh_server_rows(self) -> None:
        refresh_server_rows(
            self.servers_table,
            table_state=self._server_table_state,
            channel=CHANNEL,
            language=self._ui_language,
            accent_hex=self._tokens.accent_hex,
        )

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        apply_servers_page_language(
            tr_fn=self._tr,
            ui_language=self._ui_language,
            update_card=self.update_card,
            changelog_card=self.changelog_card,
            back_button=self._back_btn,
            page_title_label=self._page_title_label,
            servers_title_label=self._servers_title_label,
            legend_active_label=self._legend_active_label,
            servers_table=self.servers_table,
            settings_card=self._settings_card,
            toggle_label=self._toggle_label,
            auto_check_card=getattr(self, "_auto_check_card", None),
            version_info_label=self._version_info_label,
            telegram_card=self._tg_card,
            telegram_info_label=self._tg_info_label,
            telegram_button=self._tg_btn,
            refresh_server_rows=self._refresh_server_rows,
        )

    def _build_ui(self):
        # ── Custom header (back link + title) ───────────────────────────
        # Hide base title/subtitle and prevent _retranslate_base_texts
        # from re-showing them (it calls setVisible(bool(text))).
        if self.title_label is not None:
            self._title_key = None
            self.title_label.setText("")
            self.title_label.hide()
        if self.subtitle_label is not None:
            self._subtitle_key = None
            self.subtitle_label.setText("")
            self.subtitle_label.hide()

        header_widgets = build_servers_header_widgets(
            tr_fn=self._tr,
            qta_module=qta,
            parent=self,
            on_back_clicked=self._on_back_to_about,
        )
        self._back_btn = header_widgets.back_button
        self._page_title_label = header_widgets.page_title_label
        self._servers_title_label = header_widgets.servers_title_label
        self._legend_active_label = header_widgets.legend_active_label

        self.add_widget(header_widgets.header_widget)

        # Update status card
        self.update_card = UpdateStatusCard(language=self._ui_language)
        self.update_card.check_clicked.connect(self._request_check_updates)
        self.add_widget(self.update_card)

        # Changelog card (hidden by default)
        self.changelog_card = ChangelogCard(language=self._ui_language)
        self.changelog_card.install_clicked.connect(self._request_install_update)
        self.changelog_card.dismiss_clicked.connect(self._request_dismiss_update)
        self.add_widget(self.changelog_card)

        # Table header row
        self.add_widget(header_widgets.servers_header_widget)

        # Servers table
        self.servers_table = build_servers_table_widget(tr_fn=self._tr)
        self.add_widget(self.servers_table, stretch=1)

        # Settings card
        settings_widgets = build_servers_settings_section(
            content_parent=self.content,
            tr_fn=self._tr,
            accent_hex=get_theme_tokens().accent_hex,
            auto_check_enabled=self._update_controller.auto_check_enabled,
            app_version=APP_VERSION,
            channel=CHANNEL,
            has_fluent=_HAS_FLUENT,
            setting_card_group_cls=SettingCardGroup,
            settings_card_cls=SettingsCard,
            win11_toggle_row_cls=Win11ToggleRow,
            switch_button_cls=SwitchButton,
            body_label_cls=BodyLabel,
            caption_label_cls=CaptionLabel,
            qhbox_layout_cls=QHBoxLayout,
            qvbox_layout_cls=QVBoxLayout,
            on_auto_check_toggled=self._on_auto_check_toggled,
        )
        self._settings_card = settings_widgets.card
        self._auto_check_card = settings_widgets.auto_check_card
        self.auto_check_toggle = settings_widgets.auto_check_toggle
        self._toggle_label = settings_widgets.toggle_label
        self._version_info_label = settings_widgets.version_info_label
        self.add_widget(self._settings_card)

        # Telegram card
        telegram_widgets = build_servers_telegram_section(
            tr_fn=self._tr,
            accent_hex=self._tokens.accent_hex,
            has_fluent=_HAS_FLUENT,
            push_setting_card_cls=PushSettingCard,
            settings_card_cls=SettingsCard,
            body_label_cls=BodyLabel,
            action_button_cls=ActionButton,
            qta_module=qta,
            qhbox_layout_cls=QHBoxLayout,
            qvbox_layout_cls=QVBoxLayout,
            on_open_channel=self._open_telegram_channel,
        )
        self._tg_card = telegram_widgets.card
        self._tg_info_label = telegram_widgets.info_label
        self._tg_btn = telegram_widgets.button
        self.add_widget(self._tg_card)

        self._apply_page_theme(force=True)

    def get_ui_language(self) -> str:
        return self._ui_language

    def reset_server_rows(self) -> None:
        reset_servers_table_rows(
            self.servers_table,
            table_state=self._server_table_state,
        )

    def upsert_server_status(self, server_name: str, status: dict) -> None:
        upsert_server_table_status(
            self.servers_table,
            table_state=self._server_table_state,
            server_name=server_name,
            status=status,
            channel=CHANNEL,
            language=self._ui_language,
            accent_hex=self._tokens.accent_hex,
        )

    def start_checking(self) -> None:
        self.update_card.start_checking()

    def finish_checking(self, found_update: bool, version: str) -> None:
        self.update_card.stop_checking(found_update, version)

    def show_found_update_source(self, version: str, source: str) -> None:
        self.update_card.show_found_update(version, source)

    def show_update_offer(self, version: str, release_notes: str) -> None:
        self.changelog_card.show_update(version, release_notes)

    def hide_update_offer(self) -> None:
        self.changelog_card.hide()

    def is_update_download_in_progress(self) -> bool:
        return bool(getattr(self.changelog_card, "_is_downloading", False))

    def start_update_download(self, version: str) -> None:
        self.changelog_card.start_download(version)

    def update_download_progress(self, percent: int, done_bytes: int, total_bytes: int) -> None:
        self.changelog_card.update_progress(percent, done_bytes, total_bytes)

    def mark_update_download_complete(self) -> None:
        self.changelog_card.download_complete()

    def mark_update_download_failed(self, error: str) -> None:
        self.changelog_card.download_failed(error)

    def show_update_download_error(self) -> None:
        self.update_card.show_download_error()

    def show_update_deferred(self, version: str) -> None:
        self.update_card.show_deferred(version)

    def show_checked_ago(self, elapsed: float) -> None:
        self.update_card.show_checked_ago(elapsed)

    def show_manual_hint(self) -> None:
        self.update_card.show_manual_hint()

    def show_auto_enabled_hint(self) -> None:
        self.update_card.show_auto_enabled_hint()

    def hide_update_status_card(self) -> None:
        self.update_card.hide()

    def show_update_status_card(self) -> None:
        self.update_card.show()

    def set_update_check_enabled(self, enabled: bool) -> None:
        self.update_card.check_btn.setEnabled(bool(enabled))

    def present_startup_update(self, version: str, release_notes: str, *, install_after_show: bool = True) -> bool:
        return self._update_controller.present_startup_update(
            version,
            release_notes,
            install_after_show=install_after_show,
        )

    def _request_check_updates(self) -> None:
        self._update_controller.request_manual_check()

    def _request_install_update(self) -> None:
        self._update_controller.install_update()

    def _request_dismiss_update(self) -> None:
        self._update_controller.dismiss_update()

    def _open_telegram_channel(self):
        result = UpdatePageViewController.open_update_channel(CHANNEL)
        if not result.ok:
            try:
                from qfluentwidgets import InfoBar
            except Exception:
                InfoBar = None
            if InfoBar is not None:
                InfoBar.warning(
                    title=self._tr("page.servers.telegram.error.title", "Ошибка"),
                    content=self._tr(
                        "page.servers.telegram.error.open_channel",
                        "Не удалось открыть Telegram канал:\n{error}",
                    ).format(error=result.message),
                    parent=self.window(),
                )

    def _on_back_to_about(self):
        try:
            from ui.page_names import PageName
            from ui.window_adapter import show_page
            win = self.window()
            if win is not None:
                show_page(win, PageName.ABOUT)
        except Exception:
            pass

    def _on_auto_check_toggled(self, enabled: bool):
        self._update_controller.set_auto_check_enabled(bool(enabled))

    def cleanup(self):
        self._cleanup_in_progress = True
        self._update_controller.cleanup()
