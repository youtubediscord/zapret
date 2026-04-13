"""Build-helper вкладки «О программе» для About page."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

from PyQt6.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout

from ui.compat_widgets import SettingsCard
from qfluentwidgets import SubtitleLabel, StrongBodyLabel, CaptionLabel, PushButton, PrimaryPushButton
from ui.theme import get_cached_qta_pixmap, get_themed_qta_icon


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


def build_about_page_about_content(
    layout: QVBoxLayout,
    *,
    tr_fn: Callable[[str, str], str],
    tokens,
    app_version: str,
    make_section_label: Callable[[str], object],
    on_open_updates,
    on_open_premium,
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
    about_app_name_label = SubtitleLabel(
        tr_fn("page.about.app_name", "Zapret 2 GUI")
    )
    about_version_value_label = CaptionLabel(
        tr_fn("page.about.version.value_template", "Версия {version}").format(version=app_version)
    )
    text_layout.addWidget(about_app_name_label)
    text_layout.addWidget(about_version_value_label)
    version_layout.addLayout(text_layout, 1)

    update_btn = PushButton()
    update_btn.setText(
        tr_fn("page.about.button.update_settings", "Настройка обновлений")
    )
    update_btn.setIcon(get_themed_qta_icon("fa5s.sync-alt", color=tokens.accent_hex))
    update_btn.setFixedHeight(36)
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
    sub_status_layout.addWidget(sub_status_label, 1)
    sub_layout.addLayout(sub_status_layout)

    sub_desc_label = CaptionLabel(
        tr_fn(
            "page.about.subscription.desc",
            "Подписка Zapret Premium открывает доступ к дополнительным темам, приоритетной поддержке и VPN-сервису.",
        )
    )
    sub_desc_label.setWordWrap(True)
    sub_layout.addWidget(sub_desc_label)

    sub_btns = QHBoxLayout()
    sub_btns.setSpacing(8)
    premium_btn = PrimaryPushButton()
    premium_btn.setText(
        tr_fn("page.about.button.premium_vpn", "Premium и VPN")
    )
    premium_btn.setIcon(get_themed_qta_icon("fa5s.star", color="#ffc107"))
    premium_btn.setFixedHeight(36)
    premium_btn.clicked.connect(on_open_premium)
    sub_btns.addWidget(premium_btn)
    sub_btns.addStretch()
    sub_layout.addLayout(sub_btns)

    sub_card.add_layout(sub_layout)
    layout.addWidget(sub_card)
    layout.addStretch()

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
    )
