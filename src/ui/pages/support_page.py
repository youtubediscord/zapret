# ui/pages/support_page.py
"""Страница Поддержка - GitHub Discussions и каналы сообщества"""

from __future__ import annotations

from PyQt6.QtCore import QTimer
from qfluentwidgets import InfoBar, PrimaryPushSettingCard, PushSettingCard, SettingCardGroup

from app.ui_texts import tr as tr_catalog
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.theme import get_theme_tokens, get_themed_qta_icon

from .base_page import BasePage


class SupportPage(BasePage):
    """Страница поддержки с одним основным маршрутом через GitHub Discussions."""

    def __init__(self, parent=None, *, open_discussions, open_telegram, open_discord, create_open_action_worker):
        super().__init__(
            "Поддержка",
            "GitHub Discussions и каналы сообщества",
            parent,
            title_key="page.support.title",
            subtitle_key="page.support.subtitle",
        )
        self._open_discussions_action = open_discussions
        self._open_telegram_action = open_telegram
        self._open_discord_action = open_discord
        self._create_support_open_action_worker = create_open_action_worker
        self._support_open_runtime = OneShotWorkerRuntime()
        self._support_open_pending: list[tuple[str, object, str, str]] = []
        self._support_open_start_scheduled = False

        self._support_card = None
        self._support_group = None

        self._tg_card = None
        self._dc_card = None
        self._community_group = None
        self._build_ui()
        self._apply_page_theme(force=True)

    def _tr(self, key: str, default: str) -> str:
        return tr_catalog(key, language=self._ui_language, default=default)

    def _build_ui(self) -> None:
        if SettingCardGroup is None or PushSettingCard is None or PrimaryPushSettingCard is None:
            raise RuntimeError("Stock qfluentwidgets setting cards недоступны для страницы поддержки")

        tokens = get_theme_tokens()

        self._support_group = SettingCardGroup(
            self._tr("page.support.section.discussions", "GitHub Discussions"),
            self.content,
        )
        self._support_card = PrimaryPushSettingCard(
            self._tr("page.support.discussions.button", "Открыть"),
            get_themed_qta_icon("fa5b.github", color=tokens.accent_hex),
            self._tr("page.support.discussions.title", "GitHub Discussions")
        ,
            self._tr(
                "page.support.discussions.description",
                "Основной канал поддержки. Здесь можно задать вопрос, описать проблему и приложить нужные материалы вручную.",
            ),
        )
        self._support_card.clicked.connect(self._open_support_discussions)
        self._support_group.addSettingCard(self._support_card)
        self.add_widget(self._support_group)

        self.add_spacing(16)

        self._community_group = SettingCardGroup(
            self._tr("page.support.section.community", "Каналы сообщества"),
            self.content,
        )

        self._tg_card = PushSettingCard(
            self._tr("page.support.channel.open", "Открыть"),
            get_themed_qta_icon("fa5b.telegram", color="#229ED9"),
            self._tr("page.support.channel.telegram.title", "Telegram"),
            self._tr("page.support.channel.telegram.desc", "Быстрые вопросы и общение с сообществом"),
        )
        self._tg_card.clicked.connect(self._open_telegram_support)

        self._dc_card = PushSettingCard(
            self._tr("page.support.channel.open", "Открыть"),
            get_themed_qta_icon("fa5b.discord", color="#5865F2"),
            self._tr("page.support.channel.discord.title", "Discord"),
            self._tr("page.support.channel.discord.desc", "Обсуждение и живое общение"),
        )
        self._dc_card.clicked.connect(self._open_discord)

        self._community_group.addSettingCards([self._tg_card, self._dc_card])
        self.add_widget(self._community_group)

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()
        if self._support_card is not None:
            try:
                self._support_card.iconLabel.setIcon(get_themed_qta_icon("fa5b.github", color=tokens.accent_hex))
            except Exception:
                pass
        if self._tg_card is not None:
            try:
                self._tg_card.iconLabel.setIcon(get_themed_qta_icon("fa5b.telegram", color="#229ED9"))
            except Exception:
                pass
        if self._dc_card is not None:
            try:
                self._dc_card.iconLabel.setIcon(get_themed_qta_icon("fa5b.discord", color="#5865F2"))
            except Exception:
                pass

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        if self._support_group is not None:
            try:
                self._support_group.titleLabel.setText(
                    self._tr("page.support.section.discussions", "GitHub Discussions")
                )
            except Exception:
                pass
        if self._support_card is not None:
            try:
                self._support_card.setTitle(
                    self._tr("page.support.discussions.title", "GitHub Discussions")
                )
                self._support_card.setContent(
                    self._tr(
                        "page.support.discussions.description",
                        "Основной канал поддержки. Здесь можно задать вопрос, описать проблему и приложить нужные материалы вручную.",
                    )
                )
                self._support_card.button.setText(
                    self._tr("page.support.discussions.button", "Открыть")
                )
            except Exception:
                pass

        if self._community_group is not None:
            try:
                self._community_group.titleLabel.setText(
                    self._tr("page.support.section.community", "Каналы сообщества")
                )
            except Exception:
                pass
        if self._tg_card is not None:
            try:
                self._tg_card.setTitle(self._tr("page.support.channel.telegram.title", "Telegram"))
                self._tg_card.setContent(
                    self._tr("page.support.channel.telegram.desc", "Быстрые вопросы и общение с сообществом")
                )
                self._tg_card.button.setText(self._tr("page.support.channel.open", "Открыть"))
            except Exception:
                pass
        if self._dc_card is not None:
            try:
                self._dc_card.setTitle(self._tr("page.support.channel.discord.title", "Discord"))
                self._dc_card.setContent(
                    self._tr("page.support.channel.discord.desc", "Обсуждение и живое общение")
                )
                self._dc_card.button.setText(self._tr("page.support.channel.open", "Открыть"))
            except Exception:
                pass

    def _open_support_discussions(self) -> None:
        self._request_support_open_action(
            "discussions",
            self._open_discussions_action,
            error_key="page.support.error.open_discussions",
            error_default="Не удалось открыть GitHub Discussions:\n{error}",
        )

    def _open_telegram_support(self) -> None:
        self._request_support_open_action(
            "telegram",
            self._open_telegram_action,
            error_key="page.support.error.open_telegram",
            error_default="Не удалось открыть Telegram:\n{error}",
        )

    def _open_discord(self) -> None:
        self._request_support_open_action(
            "discord",
            self._open_discord_action,
            error_key="page.support.error.open_discord",
            error_default="Не удалось открыть Discord:\n{error}",
        )

    def create_support_open_action_worker(self, request_id: int, *, action_name: str, action_fn):
        return self._create_support_open_action_worker(
            request_id,
            action_name=action_name,
            action_fn=action_fn,
            parent=self,
        )

    def _request_support_open_action(
        self,
        action_name: str,
        action_fn,
        *,
        error_key: str,
        error_default: str,
    ) -> None:
        request = (str(action_name or "").strip(), action_fn, str(error_key), str(error_default))
        if self._support_open_runtime.is_running() or self.__dict__.get("_support_open_start_scheduled", False):
            self._queue_support_open_action(request)
            return
        self._start_support_open_action_worker(*request)

    def _queue_support_open_action(self, request) -> None:
        pending = self.__dict__.setdefault("_support_open_pending", [])
        if request in pending:
            return
        pending.append(request)

    def _start_support_open_action_worker(
        self,
        action_name: str,
        action_fn,
        error_key: str,
        error_default: str,
    ) -> None:
        request_id, _worker = self._support_open_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_support_open_action_worker(
                request_id,
                action_name=action_name,
                action_fn=action_fn,
            ),
            on_loaded=lambda request_id, action_name, result: self._on_support_open_action_finished(
                request_id,
                action_name,
                result,
                error_key=error_key,
                error_default=error_default,
            ),
            on_failed=lambda request_id, action_name, error: self._on_support_open_action_failed(
                request_id,
                action_name,
                error,
                error_key=error_key,
                error_default=error_default,
            ),
            on_finished=self._on_support_open_action_worker_finished,
        )
        _ = request_id

    def _on_support_open_action_finished(
        self,
        request_id: int,
        _action_name: str,
        result,
        *,
        error_key: str,
        error_default: str,
    ) -> None:
        if not self._support_open_runtime.is_current(request_id):
            return
        if self.__dict__.get("_support_open_pending"):
            return
        if result.ok:
            return
        self._show_support_open_error(error_key, error_default, str(getattr(result, "message", "") or ""))

    def _on_support_open_action_failed(
        self,
        request_id: int,
        _action_name: str,
        error: str,
        *,
        error_key: str,
        error_default: str,
    ) -> None:
        if not self._support_open_runtime.is_current(request_id):
            return
        if self.__dict__.get("_support_open_pending"):
            return
        self._show_support_open_error(error_key, error_default, str(error))

    def _on_support_open_action_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_support_open_runtime"), _worker):
            return
        pending_actions = self.__dict__.setdefault("_support_open_pending", [])
        pending = pending_actions.pop(0) if pending_actions else None
        if pending is not None:
            self._schedule_support_open_action_worker_start(pending)

    def _schedule_support_open_action_worker_start(self, request) -> None:
        if self.__dict__.get("_support_open_start_scheduled", False):
            self._queue_support_open_action(request)
            return
        self._support_open_start_scheduled = True
        QTimer.singleShot(0, lambda value=request: self._run_scheduled_support_open_action_worker_start(value))

    def _run_scheduled_support_open_action_worker_start(self, request) -> None:
        self._support_open_start_scheduled = False
        if request is not None:
            self._start_support_open_action_worker(*request)

    def _show_support_open_error(self, error_key: str, error_default: str, error: str) -> None:
        if InfoBar is not None:
            InfoBar.warning(
                title=self._tr("page.support.error.title", "Ошибка"),
                content=self._tr(error_key, error_default).format(error=error),
                parent=self.window(),
            )

    def _is_current_worker_finish(self, runtime, worker) -> bool:
        if self.__dict__.get("_cleanup_in_progress", False):
            return False
        request_id = getattr(worker, "_request_id", None)
        if request_id is None:
            current_worker = getattr(runtime, "worker", None)
            if current_worker is not None:
                return worker is current_worker
            return True
        try:
            return int(request_id) == int(getattr(runtime, "request_id", -1))
        except (TypeError, ValueError):
            return False

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        self.__dict__.setdefault("_support_open_pending", []).clear()
        self._support_open_start_scheduled = False
        self._support_open_runtime.stop(blocking=False, warning_prefix="Support open action worker")
        self._support_open_runtime.cancel()
