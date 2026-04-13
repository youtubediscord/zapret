from __future__ import annotations

import os
import subprocess
import webbrowser
from dataclasses import dataclass

from log.log import log



@dataclass(slots=True)
class AboutActionResult:
    ok: bool
    message: str


@dataclass(slots=True)
class AboutTabSwitchPlan:
    current_index: int
    route_key: str
    init_support: bool
    init_help: bool
    init_kvn: bool


@dataclass(slots=True)
class AboutSubscriptionPlan:
    icon_name: str
    icon_color: str
    label_text: str


class AboutPageController:
    TAB_KEYS = ("about", "support", "help", "kvn")

    @classmethod
    def build_tab_switch_plan(
        cls,
        *,
        index: int,
        support_initialized: bool,
        help_initialized: bool,
        kvn_initialized: bool,
    ) -> AboutTabSwitchPlan:
        safe_index = max(0, min(int(index), len(cls.TAB_KEYS) - 1))
        route_key = cls.TAB_KEYS[safe_index]
        return AboutTabSwitchPlan(
            current_index=safe_index,
            route_key=route_key,
            init_support=(safe_index == 1 and not support_initialized),
            init_help=(safe_index == 2 and not help_initialized),
            init_kvn=(safe_index == 3 and not kvn_initialized),
        )

    @classmethod
    def resolve_tab_index(cls, key: str) -> int | None:
        normalized = str(key or "").strip().lower()
        if normalized in cls.TAB_KEYS:
            return cls.TAB_KEYS.index(normalized)
        return None

    @staticmethod
    def build_subscription_status_plan(
        *,
        is_premium: bool,
        days: int | None,
        free_text: str,
        premium_active_text: str,
        premium_days_template: str,
        free_icon_color: str,
        premium_icon_color: str,
    ) -> AboutSubscriptionPlan:
        if is_premium:
            if days is not None:
                label_text = premium_days_template.format(days=days)
            else:
                label_text = premium_active_text
            return AboutSubscriptionPlan(
                icon_name="fa5s.star",
                icon_color=premium_icon_color,
                label_text=label_text,
            )

        return AboutSubscriptionPlan(
            icon_name="fa5s.user",
            icon_color=free_icon_color,
            label_text=free_text,
        )

    @staticmethod
    def get_client_id() -> str:
        try:
            from tgram import get_client_id

            return str(get_client_id() or "")
        except Exception:
            return ""

    @staticmethod
    def copy_client_id(client_id: str) -> AboutActionResult:
        from PyQt6.QtGui import QGuiApplication

        cid = str(client_id or "").strip()
        if not cid or cid == "—":
            return AboutActionResult(False, "")
        try:
            QGuiApplication.clipboard().setText(cid)
            return AboutActionResult(True, cid)
        except Exception as e:
            log(f"Ошибка копирования ID: {e}", "DEBUG")
            return AboutActionResult(False, str(e))

    @staticmethod
    def open_support_discussions() -> AboutActionResult:
        from config.urls import SUPPORT_DISCUSSIONS_URL

        try:
            webbrowser.open(SUPPORT_DISCUSSIONS_URL)
            log(f"Открыт GitHub Discussions: {SUPPORT_DISCUSSIONS_URL}", "INFO")
            return AboutActionResult(True, SUPPORT_DISCUSSIONS_URL)
        except Exception as e:
            return AboutActionResult(False, str(e))

    @staticmethod
    def open_telegram(domain: str, *, post: int | None = None) -> AboutActionResult:
        try:
            from config.telegram_links import open_telegram_link

            open_telegram_link(domain, post=post)
            log(f"Открыт Telegram: {domain}", "INFO")
            return AboutActionResult(True, domain)
        except Exception as e:
            return AboutActionResult(False, str(e))

    @staticmethod
    def open_discord(url: str) -> AboutActionResult:
        try:
            webbrowser.open(url)
            log(f"Открыт Discord: {url}", "INFO")
            return AboutActionResult(True, url)
        except Exception as e:
            return AboutActionResult(False, str(e))

    @staticmethod
    def open_github(url: str) -> AboutActionResult:
        try:
            webbrowser.open(url)
            log(f"Открыт GitHub: {url}", "INFO")
            return AboutActionResult(True, url)
        except Exception as e:
            return AboutActionResult(False, str(e))

    @staticmethod
    def open_help_folder() -> AboutActionResult:
        from config.config import HELP_FOLDER


        try:
            if os.path.exists(HELP_FOLDER):
                subprocess.Popen(f'explorer "{HELP_FOLDER}"')
                log(f"Открыта папка: {HELP_FOLDER}", "INFO")
                return AboutActionResult(True, HELP_FOLDER)
            return AboutActionResult(False, "Папка с инструкциями не найдена")
        except Exception as e:
            return AboutActionResult(False, str(e))
