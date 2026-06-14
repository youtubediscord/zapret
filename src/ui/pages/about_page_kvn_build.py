"""Build-helper вкладки Zapret KVN для About page."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QFrame
from qfluentwidgets import SubtitleLabel, SettingCardGroup, SettingCard, PushSettingCard, PrimaryPushSettingCard
from ui.pages.about_page_kvn_accessibility import set_kvn_card_accessibility
from ui.accessibility import set_state_text
from ui.theme import get_cached_qta_pixmap, get_themed_qta_icon


@dataclass(slots=True)
class AboutPageKvnWidgets:
    hero_wrap: object
    features_group: object
    yt_card: object
    game_card: object
    links_group: object
    tg_card: object
    bot_card: object
    bypass_card: object
    gh_card: object


def build_about_page_kvn_content(
    layout: QVBoxLayout,
    *,
    tokens,
    content_parent,
    on_open_kvn_channel,
    on_open_kvn_bot,
    on_open_kvn_bypass,
    on_open_kvn_github,
) -> AboutPageKvnWidgets:
    hero_wrap = QFrame()
    hero_wrap.setStyleSheet("QFrame { background: transparent; border: none; }")

    hero_layout = QVBoxLayout(hero_wrap)
    hero_layout.setContentsMargins(0, 8, 0, 0)
    hero_layout.setSpacing(4)

    hero_icon = QLabel()
    hero_icon.setPixmap(get_cached_qta_pixmap("fa5s.globe-americas", color=tokens.accent_hex, size=48))
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

    features_title = "Возможности"
    features_group = SettingCardGroup(features_title, content_parent)
    set_state_text(features_group, f"Раздел Zapret KVN: {features_title}")

    yt_card = SettingCard(
        get_themed_qta_icon("fa5s.rocket", color=tokens.accent_hex),
        "Ускорение YouTube и Discord",
        "Позволяет ускорить замедленные сервера в случае если те перестали работать и начали деградировать",
        content_parent,
    )
    game_card = SettingCard(
        get_themed_qta_icon("fa5s.gamepad", color="#4CAF50"),
        "Игровые серверы",
        "Также подходит для ускорения игровых серверов",
        content_parent,
    )
    features_group.addSettingCards([yt_card, game_card])
    layout.addWidget(features_group)
    layout.addSpacing(16)

    links_title = "Ссылки"
    links_group = SettingCardGroup(links_title, content_parent)
    set_state_text(links_group, f"Раздел Zapret KVN: {links_title}")

    tg_card = PushSettingCard(
        "Открыть",
        get_themed_qta_icon("fa5b.telegram", color="#229ED9"),
        "Канал Zapret KVN",
        "Новости и обновления",
    )
    set_kvn_card_accessibility(
        tg_card,
        action_name="Открыть канал Zapret KVN",
        description="Новости и обновления",
    )
    tg_card.clicked.connect(on_open_kvn_channel)

    bot_card = PrimaryPushSettingCard(
        "Купить",
        get_themed_qta_icon("fa5s.shopping-cart", color="#f59e0b"),
        "Купить подписку",
        "Оформление через Telegram-бота @zapretvpns_bot",
    )
    set_kvn_card_accessibility(
        bot_card,
        action_name="Купить подписку Zapret KVN",
        description="Оформление через Telegram-бота @zapretvpns_bot",
    )
    bot_card.clicked.connect(on_open_kvn_bot)

    bypass_card = PushSettingCard(
        "Открыть",
        get_themed_qta_icon("fa5b.telegram", color="#229ED9"),
        "Канал BypassBlock",
        "Второй канал с новостями",
    )
    set_kvn_card_accessibility(
        bypass_card,
        action_name="Открыть канал BypassBlock",
        description="Второй канал с новостями",
    )
    bypass_card.clicked.connect(on_open_kvn_bypass)

    gh_card = PushSettingCard(
        "Открыть",
        get_themed_qta_icon("fa5b.github", color=tokens.accent_hex),
        "Исходный код",
        "GitHub репозиторий Zapret KVN",
    )
    set_kvn_card_accessibility(
        gh_card,
        action_name="Открыть исходный код Zapret KVN",
        description="GitHub репозиторий Zapret KVN",
    )
    gh_card.clicked.connect(on_open_kvn_github)

    links_group.addSettingCards([tg_card, bot_card, bypass_card, gh_card])
    layout.addWidget(links_group)
    layout.addStretch()

    return AboutPageKvnWidgets(
        hero_wrap=hero_wrap,
        features_group=features_group,
        yt_card=yt_card,
        game_card=game_card,
        links_group=links_group,
        tg_card=tg_card,
        bot_card=bot_card,
        bypass_card=bypass_card,
        gh_card=gh_card,
    )
