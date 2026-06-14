"""Build-helper вкладки «Справка» для About page."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout, QFrame, QSizePolicy

from ui.pages.about_page_help_accessibility import set_help_card_accessibility
from ui.accessibility import set_state_text


@dataclass(slots=True)
class AboutPageHelpWidgets:
    motto_wrap: object
    docs_group: object
    forum_card: object
    info_card: object
    folder_card: object
    android_card: object
    github_card: object
    news_group: object
    telegram_card: object
    mastodon_card: object
    bastyon_card: object


def build_about_page_motto_block(*, tr_fn: Callable[[str, str], str], tokens):
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
        tr_fn("page.about.help.motto.title", "keep thinking, keep searching, keep learning....")
    )
    motto_title.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
    motto_title.setWordWrap(True)
    motto_title.setStyleSheet(
        f"QLabel {{ color: {tokens.fg}; font-size: 25px; font-weight: 700; "
        f"letter-spacing: 0.8px; "
        f"font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif; }}"
    )

    motto_translate = QLabel(
        tr_fn(
            "page.about.help.motto.subtitle",
            "Продолжай думать, продолжай искать, продолжай учиться....",
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
        tr_fn(
            "page.about.help.motto.cta",
            "Zapret2 - думай свободно, ищи смелее, учись всегда.",
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
    return motto_wrap


def build_about_page_help_content(
    layout: QVBoxLayout,
    *,
    tr_fn: Callable[[str, str], str],
    tokens,
    content_parent,
    make_section_label: Callable[[str], object],
    hyperlink_card_cls,
    push_setting_card_cls,
    setting_card_group_cls,
    fluent_icon,
    on_open_forum,
    on_open_help_folder,
    on_open_telegram_news,
) -> AboutPageHelpWidgets:
    try:
        from config.urls import INFO_URL, ANDROID_URL
    except Exception:
        INFO_URL = ""
        ANDROID_URL = ""

    motto_wrap = build_about_page_motto_block(tr_fn=tr_fn, tokens=tokens)
    layout.addWidget(motto_wrap)
    layout.addSpacing(6)
    layout.addWidget(make_section_label(tr_fn("page.about.help.section.links", "Ссылки")))

    docs_title = tr_fn("page.about.help.group.docs", "Документация")
    docs_group = setting_card_group_cls(
        docs_title,
        content_parent,
    )
    set_state_text(docs_group, f"Раздел справки: {docs_title}")

    forum_card = push_setting_card_cls(
        tr_fn("page.about.help.button.open", "Открыть"),
        fluent_icon.SEND,
        tr_fn("page.about.help.docs.forum.title", "Вики-сайт"),
        tr_fn("page.about.help.docs.forum.desc", "Документация и инструкции"),
    )
    set_help_card_accessibility(
        forum_card,
        action_name=tr_fn(
            "page.about.help.docs.forum.accessible_name",
            "Открыть вики-сайт",
        ),
        description=tr_fn("page.about.help.docs.forum.desc", "Документация и инструкции"),
    )
    forum_card.clicked.connect(on_open_forum)

    info_card = hyperlink_card_cls(
        INFO_URL,
        tr_fn("page.about.help.button.open", "Открыть"),
        fluent_icon.INFO,
        tr_fn("page.about.help.docs.info.title", "Что это такое?"),
        tr_fn("page.about.help.docs.info.desc", "Руководство и ответы на вопросы"),
    )
    set_help_card_accessibility(
        info_card,
        action_name=tr_fn(
            "page.about.help.docs.info.accessible_name",
            "Открыть руководство и ответы",
        ),
        description=tr_fn("page.about.help.docs.info.desc", "Руководство и ответы на вопросы"),
    )

    folder_card = push_setting_card_cls(
        tr_fn("page.about.help.button.open", "Открыть"),
        fluent_icon.FOLDER,
        tr_fn("page.about.help.docs.folder.title", "Папка с инструкциями"),
        tr_fn("page.about.help.docs.folder.desc", "Открыть локальную папку help"),
    )
    set_help_card_accessibility(
        folder_card,
        action_name=tr_fn(
            "page.about.help.docs.folder.accessible_name",
            "Открыть папку с инструкциями",
        ),
        description=tr_fn("page.about.help.docs.folder.desc", "Открыть локальную папку help"),
    )
    folder_card.clicked.connect(on_open_help_folder)

    android_card = hyperlink_card_cls(
        ANDROID_URL,
        tr_fn("page.about.help.button.open", "Открыть"),
        fluent_icon.PHONE,
        tr_fn("page.about.help.docs.android.title", "На Android (Magisk Zapret, ByeByeDPI и др.)"),
        tr_fn("page.about.help.docs.android.desc", "Открыть инструкцию на сайте"),
    )
    set_help_card_accessibility(
        android_card,
        action_name=tr_fn(
            "page.about.help.docs.android.accessible_name",
            "Открыть инструкцию для Android",
        ),
        description=tr_fn("page.about.help.docs.android.desc", "Открыть инструкцию на сайте"),
    )

    github_card = hyperlink_card_cls(
        "https://github.com/youtubediscord/zapret",
        tr_fn("page.about.help.button.open", "Открыть"),
        fluent_icon.GITHUB,
        "GitHub",
        tr_fn("page.about.help.docs.github.desc", "Исходный код и документация"),
    )
    set_help_card_accessibility(
        github_card,
        action_name=tr_fn("page.about.help.docs.github.accessible_name", "Открыть GitHub"),
        description=tr_fn("page.about.help.docs.github.desc", "Исходный код и документация"),
    )

    docs_group.addSettingCards([forum_card, info_card, folder_card, android_card, github_card])
    layout.addWidget(docs_group)
    layout.addSpacing(8)

    news_title = tr_fn("page.about.help.group.news", "Новости")
    news_group = setting_card_group_cls(
        news_title,
        content_parent,
    )
    set_state_text(news_group, f"Раздел справки: {news_title}")

    telegram_card = push_setting_card_cls(
        tr_fn("page.about.help.button.open", "Открыть"),
        fluent_icon.MEGAPHONE,
        tr_fn("page.about.help.news.telegram.title", "Telegram канал"),
        tr_fn("page.about.help.news.telegram.desc", "Новости и обновления"),
    )
    set_help_card_accessibility(
        telegram_card,
        action_name=tr_fn(
            "page.about.help.news.telegram.accessible_name",
            "Открыть Telegram канал",
        ),
        description=tr_fn("page.about.help.news.telegram.desc", "Новости и обновления"),
    )
    telegram_card.clicked.connect(on_open_telegram_news)

    mastodon_card = hyperlink_card_cls(
        "https://mastodon.social/@zapret",
        tr_fn("page.about.help.button.open", "Открыть"),
        fluent_icon.GLOBE,
        tr_fn("page.about.help.news.mastodon.title", "Mastodon профиль"),
        tr_fn("page.about.help.news.mastodon.desc", "Новости в Fediverse"),
    )
    set_help_card_accessibility(
        mastodon_card,
        action_name=tr_fn(
            "page.about.help.news.mastodon.accessible_name",
            "Открыть Mastodon профиль",
        ),
        description=tr_fn("page.about.help.news.mastodon.desc", "Новости в Fediverse"),
    )

    bastyon_card = hyperlink_card_cls(
        "https://bastyon.com/zapretgui",
        tr_fn("page.about.help.button.open", "Открыть"),
        fluent_icon.GLOBE,
        tr_fn("page.about.help.news.bastyon.title", "Bastyon профиль"),
        tr_fn("page.about.help.news.bastyon.desc", "Новости в Bastyon"),
    )
    set_help_card_accessibility(
        bastyon_card,
        action_name=tr_fn(
            "page.about.help.news.bastyon.accessible_name",
            "Открыть Bastyon профиль",
        ),
        description=tr_fn("page.about.help.news.bastyon.desc", "Новости в Bastyon"),
    )

    news_group.addSettingCards([telegram_card, mastodon_card, bastyon_card])
    layout.addWidget(news_group)
    layout.addStretch()

    return AboutPageHelpWidgets(
        motto_wrap=motto_wrap,
        docs_group=docs_group,
        forum_card=forum_card,
        info_card=info_card,
        folder_card=folder_card,
        android_card=android_card,
        github_card=github_card,
        news_group=news_group,
        telegram_card=telegram_card,
        mastodon_card=mastodon_card,
        bastyon_card=bastyon_card,
    )
