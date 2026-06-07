# updater/ui/page.py
"""Страница мониторинга серверов обновлений"""

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
)

from ui.pages.base_page import BasePage
from ui.fluent_widgets import SettingsCard
from ui.theme import get_theme_tokens
from app.ui_texts import tr as tr_catalog
from updater.update_page_runtime import UpdatePageRuntime
from ui.page_deps.types import UpdateRuntimeActions
from updater.server_status_table_state import ServerStatusTableState
from updater.ui.main_build import (
    build_servers_header_widgets,
    build_servers_table_widget,
)
from updater.ui.language import apply_servers_page_language
from updater.ui.table_view import (
    refresh_server_rows,
    render_server_row,
    reset_server_rows as reset_servers_table_rows,
    upsert_server_status as upsert_server_table_status,
)
from updater.ui.settings_build import (
    build_servers_settings_section,
    build_servers_telegram_section,
)
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.widgets.win11_controls import Win11ToggleRow
from qfluentwidgets import (
    CaptionLabel, PushSettingCard, SettingCardGroup, InfoBar,
)

from config.build_info import APP_VERSION, CHANNEL

from updater.ui.update_card import UpdateStatusCard
from updater.ui.changelog_card import ChangelogCard



# ═══════════════════════════════════════════════════════════════════════════════
# ИНДЕТЕРМИНИРОВАННАЯ КНОПКА С ПРОГРЕСС-КОЛЬЦОМ (аналог IndeterminateProgressPushButton Pro)
# ═══════════════════════════════════════════════════════════════════════════════

class ServersPage(BasePage):
    """Страница мониторинга серверов обновлений"""

    def __init__(
        self,
        parent=None,
        *,
        runtime_actions: UpdateRuntimeActions,
        updater_feature,
        open_about,
        create_changelog_link_open_worker,
    ):
        super().__init__(
            "Серверы",
            "Мониторинг серверов обновлений",
            parent,
            title_key="page.servers.title",
            subtitle_key="page.servers.subtitle",
        )

        self._tokens = get_theme_tokens()
        self._server_table_state = ServerStatusTableState()
        self._update_runtime = UpdatePageRuntime(
            self,
            runtime_actions=runtime_actions,
            updater_feature=updater_feature,
        )
        self._create_changelog_link_open_worker = create_changelog_link_open_worker
        self._open_about = open_about
        self._runtime_initialized = False
        self._cleanup_in_progress = False
        self._changelog_link_open_runtime = OneShotWorkerRuntime()
        self._changelog_link_open_runtime_worker = None
        self._changelog_link_open_pending: str | None = None
        self._changelog_link_open_start_scheduled = False

        self._build_ui()
        self._apply_page_theme(force=True)
        self._update_runtime.start_auto_check_load()

    def _tr(self, key: str, default: str) -> str:
        return tr_catalog(key, language=self._ui_language, default=default)

    def _run_runtime_init_once(self) -> None:
        plan = self._update_runtime.build_page_init_plan(
            runtime_initialized=self._runtime_initialized,
        )
        if not plan.should_apply_idle_view_state:
            return
        self._runtime_initialized = True
        QTimer.singleShot(
            0,
            lambda action=plan.view_action, elapsed=plan.elapsed_seconds: (not self._cleanup_in_progress) and self._update_runtime.apply_idle_view_state(
                view_action=action,
                elapsed_seconds=elapsed,
                ),
        )

    def on_page_activated(self) -> None:
        self._run_runtime_init_once()

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
            breadcrumb=self._breadcrumb,
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
            parent=self,
            on_about_clicked=self._on_back_to_about,
        )
        self._breadcrumb = header_widgets.breadcrumb
        self._page_title_label = header_widgets.page_title_label
        self._servers_title_label = header_widgets.servers_title_label
        self._legend_active_label = header_widgets.legend_active_label

        self.add_widget(header_widgets.header_widget)

        # Update status card
        self.update_card = UpdateStatusCard(language=self._ui_language)
        self.update_card.check_clicked.connect(self._request_check_updates)
        self.add_widget(self.update_card)

        # Changelog card (hidden by default)
        self.changelog_card = ChangelogCard(
            language=self._ui_language,
            open_url=self._request_changelog_link_open,
        )
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
            auto_check_enabled=self._update_runtime.auto_check_enabled,
            app_version=APP_VERSION,
            channel=CHANNEL,
            setting_card_group_cls=SettingCardGroup,
            settings_card_cls=SettingsCard,
            win11_toggle_row_cls=Win11ToggleRow,
            caption_label_cls=CaptionLabel,
            qhbox_layout_cls=QHBoxLayout,
            on_auto_check_toggled=self._on_auto_check_toggled,
        )
        self._settings_card = settings_widgets.card
        self._auto_check_card = settings_widgets.auto_check_card
        self.auto_check_toggle = settings_widgets.auto_check_toggle
        self._toggle_label = settings_widgets.toggle_label
        self._version_info_label = settings_widgets.version_info_label
        self.add_widget(self._settings_card)
        self.add_widget(self._version_info_label)

        # Telegram card
        telegram_widgets = build_servers_telegram_section(
            tr_fn=self._tr,
            accent_hex=self._tokens.accent_hex,
            push_setting_card_cls=PushSettingCard,
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

    def update_download_status_text(self, message: str) -> None:
        self.changelog_card.set_download_status_text(message)

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

    def set_auto_check_toggle_checked(self, enabled: bool) -> None:
        toggle = getattr(self, "auto_check_toggle", None)
        if toggle is None:
            return
        try:
            toggle.setChecked(bool(enabled), block_signals=True)
        except TypeError:
            previous = toggle.blockSignals(True)
            try:
                toggle.setChecked(bool(enabled))
            finally:
                toggle.blockSignals(previous)

    def present_startup_update(self, version: str, release_notes: str, *, install_after_show: bool = True) -> bool:
        return self._update_runtime.present_startup_update(
            version,
            release_notes,
            install_after_show=install_after_show,
        )

    def _request_check_updates(self) -> None:
        self._update_runtime.request_manual_check()

    def _request_install_update(self) -> None:
        self._update_runtime.install_update()

    def _request_dismiss_update(self) -> None:
        self._update_runtime.dismiss_update()

    def create_changelog_link_open_worker(self, request_id: int, *, url: str):
        return self._create_changelog_link_open_worker(
            request_id,
            url=url,
            parent=self,
        )

    def _request_changelog_link_open(self, url: str) -> None:
        target = str(url or "").strip()
        if (
            self._changelog_link_open_runtime.is_running()
            or self.__dict__.get("_changelog_link_open_start_scheduled", False)
        ):
            self._changelog_link_open_pending = target
            return
        self._changelog_link_open_pending = None
        self._start_changelog_link_open_worker(target)

    def _start_changelog_link_open_worker(self, url: str) -> None:
        started = self._changelog_link_open_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_changelog_link_open_worker(
                request_id,
                url=url,
            ),
            on_loaded=self._on_changelog_link_open_finished,
            on_failed=self._on_changelog_link_open_failed,
            on_finished=self._on_changelog_link_open_worker_finished,
        )
        worker = (
            started[1]
            if isinstance(started, tuple) and len(started) > 1
            else getattr(self._changelog_link_open_runtime, "worker", None)
        )
        self._changelog_link_open_runtime_worker = worker

    def _on_changelog_link_open_finished(self, request_id: int, result) -> None:
        if not self._changelog_link_open_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self.__dict__.get("_changelog_link_open_pending") is not None:
            return
        if getattr(result, "ok", False):
            return
        self._show_changelog_link_open_error(str(getattr(result, "error", "") or ""))

    def _on_changelog_link_open_failed(self, request_id: int, error: str) -> None:
        if not self._changelog_link_open_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        if self.__dict__.get("_changelog_link_open_pending") is not None:
            return
        self._show_changelog_link_open_error(str(error or ""))

    def _on_changelog_link_open_worker_finished(self, worker) -> None:
        current_worker = self.__dict__.get("_changelog_link_open_runtime_worker")
        if current_worker is not None and worker is not current_worker:
            return
        self._changelog_link_open_runtime_worker = None
        pending = self._changelog_link_open_pending
        if pending is not None and not self._cleanup_in_progress:
            self._schedule_changelog_link_open_worker_start()

    def _schedule_changelog_link_open_worker_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_changelog_link_open_start_scheduled", False):
            return
        self._changelog_link_open_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_changelog_link_open_worker_start)

    def _run_scheduled_changelog_link_open_worker_start(self) -> None:
        self._changelog_link_open_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        pending = self.__dict__.get("_changelog_link_open_pending")
        self._changelog_link_open_pending = None
        if pending is None:
            return
        self._start_changelog_link_open_worker(str(pending or "").strip())

    def _show_changelog_link_open_error(self, error: str) -> None:
        InfoBar.warning(
            title=self._tr("page.servers.telegram.error.title", "Ошибка"),
            content=self._tr(
                "page.servers.telegram.error.open_channel",
                "Не удалось открыть Telegram канал:\n{error}",
            ).format(error=str(error or "")),
            parent=self.window(),
        )

    def _stop_changelog_link_open_worker(self) -> None:
        self._changelog_link_open_pending = None
        self._changelog_link_open_start_scheduled = False
        self._changelog_link_open_runtime_worker = None
        self._changelog_link_open_runtime.stop(
            blocking=False,
            warning_prefix="Changelog link open worker",
        )
        self._changelog_link_open_runtime.cancel()

    def _open_telegram_channel(self):
        self._update_runtime.request_open_update_channel(CHANNEL)

    def show_update_channel_open_error(self, error: str) -> None:
        InfoBar.warning(
            title=self._tr("page.servers.telegram.error.title", "Ошибка"),
            content=self._tr(
                "page.servers.telegram.error.open_channel",
                "Не удалось открыть Telegram канал:\n{error}",
            ).format(error=str(error or "")),
            parent=self.window(),
        )

    def _on_back_to_about(self):
        try:
            self._open_about()
        except Exception:
            pass

    def _on_auto_check_toggled(self, enabled: bool):
        self._update_runtime.set_auto_check_enabled(bool(enabled))

    def cleanup(self):
        self._cleanup_in_progress = True
        self._stop_changelog_link_open_worker()
        self._update_runtime.cleanup()
