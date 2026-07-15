"""Build-helper вкладки «О программе» для About page."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

from PyQt6.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout

from ui.accessibility import set_state_text
from ui.pages.about_page_accessibility import apply_about_buttons_accessibility
from ui.pages.about_page_help_accessibility import set_help_card_accessibility as set_link_card_accessibility
from ui.fluent_widgets import SettingsCard
from qfluentwidgets import (
    CaptionLabel,
    FluentIcon,
    HyperlinkCard,
    PrimaryPushButton,
    PushButton,
    SettingCardGroup,
    StrongBodyLabel,
    SubtitleLabel,
)
from ui.theme import get_cached_qta_pixmap


@dataclass(slots=True)
class AboutPageAboutWidgets:
    about_section_version_label: object
    about_app_name_label: object
    about_version_value_label: object
    update_btn: object
    about_section_subscription_label: object
    sub_status_icon: QLabel
    sub_status_label: object
    sub_desc_label: object
    premium_btn: object
    kvn_btn: object
    course_group: object
    youtube_course_card: object
    youtube_playlist_card: object


def set_subscription_status_accessibility(label, text: object) -> None:
    value = " ".join(str(text or "").strip().split())
    if not value:
        return
    set_state_text(label, f"Статус подписки: {value}")


def set_subscription_description_accessibility(label, text: object) -> None:
    value = " ".join(str(text or "").strip().split())
    if not value:
        return
    set_state_text(label, f"Описание подписки: {value}")


def set_about_version_accessibility(app_name_label, version_label, *, app_name: object, app_version: object) -> None:
    app_name_value = " ".join(str(app_name or "").strip().split())
    app_version_value = " ".join(str(app_version or "").strip().split())
    if app_name_value:
        set_state_text(app_name_label, f"Название программы: {app_name_value}")
    if app_version_value:
        set_state_text(version_label, f"Версия программы: {app_version_value}")


def build_about_page_about_content(
    layout: QVBoxLayout,
    *,
    tr_fn: Callable[[str, str], str],
    tokens,
    content_parent,
    app_version: str,
    make_section_label: Callable[[str], object],
    on_open_updates,
    on_open_premium,
    on_open_kvn_github,
) -> AboutPageAboutWidgets:
    about_section_version_label = make_section_label(
        tr_fn("page.about.section.version", "Версия")
    )
    layout.addWidget(about_section_version_label)

    version_card = SettingsCard()
    version_layout = QHBoxLayout()
    version_layout.setSpacing(16)

    icon_label = QLabel()
    icon_label.setPixmap(get_cached_qta_pixmap('fa5s.shield-alt', color=tokens.accent_hex, size=40))
    icon_label.setFixedSize(48, 48)
    version_layout.addWidget(icon_label)

    text_layout = QVBoxLayout()
    text_layout.setSpacing(2)
    app_name_text = tr_fn("page.about.app_name", "Zapret 2 GUI")
    about_app_name_label = SubtitleLabel(app_name_text)
    about_version_value_label = CaptionLabel(
        tr_fn("page.about.version.value_template", "Версия {version}").format(version=app_version)
    )
    set_about_version_accessibility(
        about_app_name_label,
        about_version_value_label,
        app_name=app_name_text,
        app_version=app_version,
    )
    text_layout.addWidget(about_app_name_label)
    text_layout.addWidget(about_version_value_label)
    version_layout.addLayout(text_layout, 1)

    update_btn = PushButton(
        tr_fn("page.about.button.update_settings", "Настройка обновлений"),
        icon=FluentIcon.SYNC,
    )
    apply_about_buttons_accessibility(tr_fn=tr_fn, update_btn=update_btn)
    update_btn.clicked.connect(on_open_updates)
    version_layout.addWidget(update_btn)

    version_card.add_layout(version_layout)
    layout.addWidget(version_card)
    layout.addSpacing(16)

    about_section_subscription_label = make_section_label(
        tr_fn("page.about.section.subscription", "Подписка")
    )
    layout.addWidget(about_section_subscription_label)

    sub_card = SettingsCard()
    sub_layout = QVBoxLayout()
    sub_layout.setSpacing(12)

    sub_status_layout = QHBoxLayout()
    sub_status_layout.setSpacing(8)

    sub_status_icon = QLabel()
    sub_status_icon.setPixmap(get_cached_qta_pixmap('fa5s.user', color=tokens.fg_faint, size=18))
    sub_status_icon.setFixedSize(22, 22)
    sub_status_layout.addWidget(sub_status_icon)

    sub_status_label = StrongBodyLabel(
        tr_fn("page.about.subscription.free", "Free версия")
    )
    set_subscription_status_accessibility(sub_status_label, sub_status_label.text())
    sub_status_layout.addWidget(sub_status_label, 1)
    sub_layout.addLayout(sub_status_layout)

    sub_desc_label = CaptionLabel(
        tr_fn(
            "page.about.subscription.desc",
            "Подписка Zapret Premium открывает доступ к дополнительным темам, приоритетной поддержке и VPN-сервису.",
        )
    )
    sub_desc_label.setWordWrap(True)
    set_subscription_description_accessibility(sub_desc_label, sub_desc_label.text())
    sub_layout.addWidget(sub_desc_label)

    sub_btns = QHBoxLayout()
    sub_btns.setSpacing(8)
    premium_btn = PrimaryPushButton(
        tr_fn("page.about.button.premium_vpn", "Premium и VPN"),
        icon=FluentIcon.HEART,
    )
    apply_about_buttons_accessibility(tr_fn=tr_fn, premium_btn=premium_btn)
    premium_btn.clicked.connect(on_open_premium)
    sub_btns.addWidget(premium_btn)
    sub_btns.addStretch()
    kvn_btn = PushButton(
        tr_fn("page.about.button.zapret_kvn", "Zapret KVN"),
        icon=FluentIcon.GITHUB,
    )
    apply_about_buttons_accessibility(tr_fn=tr_fn, kvn_btn=kvn_btn)
    kvn_btn.clicked.connect(on_open_kvn_github)
    sub_btns.addWidget(kvn_btn)
    sub_layout.addLayout(sub_btns)

    sub_card.add_layout(sub_layout)
    layout.addWidget(sub_card)
    layout.addSpacing(16)

    course_title = tr_fn("page.about.course.group", "Обучение")
    course_group = SettingCardGroup(
        course_title,
        content_parent,
    )
    set_state_text(course_group, f"Раздел о программе: {course_title}")

    youtube_course_card = HyperlinkCard(
        "https://www.youtube.com/@%D0%9F%D1%80%D0%B8%D0%B2%D0%B0%D1%82%D0%BD%D0%BE%D1%81%D1%82%D1%8C/videos",
        tr_fn("page.about.button.open", "Открыть"),
        FluentIcon.PLAY,
        tr_fn("page.about.course.youtube.title", "Курс и гайд по Zapret 2"),
        tr_fn("page.about.course.youtube.desc", "Видео по настройке и пониманию Zapret 2"),
    )
    set_link_card_accessibility(
        youtube_course_card,
        action_name=tr_fn(
            "page.about.course.youtube.accessible_name",
            "Открыть курс и гайд по Zapret 2",
        ),
        description=tr_fn("page.about.course.youtube.desc", "Видео по настройке и пониманию Zapret 2"),
    )

    youtube_playlist_card = HyperlinkCard(
        "https://www.youtube.com/playlist?list=PLa6yzOvgEWW0F1PL0D8pOPI8lD_rfLL1s",
        tr_fn("page.about.button.open", "Открыть"),
        FluentIcon.PLAY,
        tr_fn("page.about.course.youtube_playlist.title", "Плейлист курса по Zapret 2"),
        tr_fn("page.about.course.youtube_playlist.desc", "Все видео курса одним списком"),
    )
    set_link_card_accessibility(
        youtube_playlist_card,
        action_name=tr_fn(
            "page.about.course.youtube_playlist.accessible_name",
            "Открыть плейлист курса по Zapret 2",
        ),
        description=tr_fn("page.about.course.youtube_playlist.desc", "Все видео курса одним списком"),
    )

    course_group.addSettingCards([youtube_course_card, youtube_playlist_card])
    layout.addWidget(course_group)

    return AboutPageAboutWidgets(
        about_section_version_label=about_section_version_label,
        about_app_name_label=about_app_name_label,
        about_version_value_label=about_version_value_label,
        update_btn=update_btn,
        about_section_subscription_label=about_section_subscription_label,
        sub_status_icon=sub_status_icon,
        sub_status_label=sub_status_label,
        sub_desc_label=sub_desc_label,
        premium_btn=premium_btn,
        kvn_btn=kvn_btn,
        course_group=course_group,
        youtube_course_card=youtube_course_card,
        youtube_playlist_card=youtube_playlist_card,
    )
