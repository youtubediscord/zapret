"""Build-helper секции Premium страницы."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton

try:
    from qfluentwidgets import (
        LineEdit,
        PushButton,
        PrimaryPushButton,
        BodyLabel,
        CaptionLabel,
    )
except ImportError:
    from PyQt6.QtWidgets import (  # type: ignore[assignment]
        QLineEdit as LineEdit,
        QLabel as BodyLabel,
        QLabel as CaptionLabel,
    )

    PushButton = QPushButton  # type: ignore[assignment]
    PrimaryPushButton = QPushButton  # type: ignore[assignment]

from ui.fluent_widgets import SettingsCard, RefreshButton, QuickActionsBar
from ui.theme import get_themed_qta_icon


@dataclass(slots=True)
class PremiumActivationWidgets:
    card: SettingsCard
    instructions_label: BodyLabel
    key_input_container: QWidget
    key_input: LineEdit
    activate_btn: PrimaryPushButton
    activation_status: CaptionLabel


@dataclass(slots=True)
class PremiumDeviceInfoWidgets:
    card: SettingsCard
    device_id_label: CaptionLabel
    saved_key_label: CaptionLabel
    last_check_label: CaptionLabel
    server_status_label: CaptionLabel
    open_bot_btn: PushButton


@dataclass(slots=True)
class PremiumActionsWidgets:
    actions_bar: QuickActionsBar
    refresh_btn: RefreshButton
    change_key_btn: PushButton
    test_btn: PushButton
    extend_btn: PrimaryPushButton


def build_premium_activation_section(
    *,
    tr: Callable[[str, str], str],
    on_create_pair_code: Callable[[], None],
) -> PremiumActivationWidgets:
    card = SettingsCard()

    instructions_label = BodyLabel(
        tr(
            "page.premium.instructions",
            "1. Нажмите «Создать код»\n2. Отправьте код боту @zapretvpns_bot в Telegram (сообщением)\n3. Вернитесь сюда и нажмите «Проверить статус»",
        )
    )
    instructions_label.setWordWrap(True)
    card.add_widget(instructions_label)

    key_input_container = QWidget()
    key_v = QVBoxLayout(key_input_container)
    key_v.setContentsMargins(0, 0, 0, 0)
    key_v.setSpacing(8)

    key_row = QHBoxLayout()
    key_row.setSpacing(8)

    key_input = LineEdit()
    key_input.setPlaceholderText(
        tr("page.premium.placeholder.pair_code", "ABCD12EF")
    )
    key_input.setReadOnly(True)
    key_row.addWidget(key_input, 1)

    activate_btn = PrimaryPushButton()
    activate_btn.setText(tr("page.premium.button.create_code", "Создать код"))
    activate_btn.setIcon(get_themed_qta_icon("fa5s.link", color="#60cdff"))
    activate_btn.clicked.connect(on_create_pair_code)
    key_row.addWidget(activate_btn)

    key_v.addLayout(key_row)

    activation_status = CaptionLabel("")
    activation_status.setWordWrap(True)
    key_v.addWidget(activation_status)

    card.add_widget(key_input_container)

    return PremiumActivationWidgets(
        card=card,
        instructions_label=instructions_label,
        key_input_container=key_input_container,
        key_input=key_input,
        activate_btn=activate_btn,
        activation_status=activation_status,
    )


def build_premium_device_info_section(
    *,
    tr: Callable[[str, str], str],
    on_open_bot: Callable[[], None],
) -> PremiumDeviceInfoWidgets:
    card = SettingsCard()

    device_id_label = CaptionLabel(
        tr("page.premium.label.device_id.loading", "ID устройства: загрузка...")
    )
    saved_key_label = CaptionLabel(
        tr("page.premium.label.device_token.none", "device token: —")
    )
    last_check_label = CaptionLabel(
        tr("page.premium.label.last_check.none", "Последняя проверка: —")
    )
    server_status_label = CaptionLabel(
        tr("page.premium.label.server.checking", "Сервер: проверка...")
    )

    labels_layout = QVBoxLayout()
    labels_layout.setSpacing(4)
    labels_layout.setContentsMargins(0, 0, 0, 0)
    labels_layout.addWidget(device_id_label)
    labels_layout.addWidget(saved_key_label)
    labels_layout.addWidget(last_check_label)
    labels_layout.addWidget(server_status_label)

    open_bot_btn = PushButton()
    open_bot_btn.setText(tr("page.premium.button.open_bot", "Открыть бота"))
    open_bot_btn.setIcon(get_themed_qta_icon("fa5b.telegram", color="#229ED9"))
    open_bot_btn.clicked.connect(on_open_bot)

    row_layout = QHBoxLayout()
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.addLayout(labels_layout)
    row_layout.addStretch(1)
    row_layout.addWidget(open_bot_btn, 0, Qt.AlignmentFlag.AlignVCenter)
    card.add_layout(row_layout)

    return PremiumDeviceInfoWidgets(
        card=card,
        device_id_label=device_id_label,
        saved_key_label=saved_key_label,
        last_check_label=last_check_label,
        server_status_label=server_status_label,
        open_bot_btn=open_bot_btn,
    )


def build_premium_actions_section(
    *,
    parent,
    tr: Callable[[str, str], str],
    on_check_status: Callable[[], None],
    on_change_key: Callable[[], None],
    on_test_connection: Callable[[], None],
    on_open_bot: Callable[[], None],
) -> PremiumActionsWidgets:
    refresh_btn = RefreshButton(tr("page.premium.button.refresh_status", "Обновить статус"))
    refresh_btn.clicked.connect(on_check_status)
    refresh_btn.setToolTip(
        tr(
            "page.premium.action.refresh_status.description",
            "Повторно запросить Premium-статус и обновить данные устройства.",
        )
    )

    actions_bar = QuickActionsBar(parent)
    actions_bar.add_button(refresh_btn)

    change_key_btn = PushButton()
    change_key_btn.setText(tr("page.premium.button.reset_activation", "Сбросить активацию"))
    change_key_btn.setIcon(get_themed_qta_icon("fa5s.exchange-alt", color="#ff9800"))
    change_key_btn.setToolTip(
        tr(
            "page.premium.action.reset_activation.description",
            "Удалить токен устройства, офлайн-кэш и код привязки на этом компьютере.",
        )
    )
    change_key_btn.clicked.connect(on_change_key)
    actions_bar.add_button(change_key_btn)

    test_btn = PushButton()
    test_btn.setText(tr("page.premium.button.test_connection", "Проверить соединение"))
    test_btn.setIcon(get_themed_qta_icon("fa5s.plug", color="#60cdff"))
    test_btn.setToolTip(
        tr(
            "page.premium.action.test_connection.description",
            "Проверить доступность Premium backend и соединение с сервером.",
        )
    )
    test_btn.clicked.connect(on_test_connection)
    actions_bar.add_button(test_btn)

    extend_btn = PrimaryPushButton()
    extend_btn.setText(tr("page.premium.button.extend", "Продлить подписку"))
    extend_btn.setIcon(get_themed_qta_icon("fa5b.telegram", color="#229ED9"))
    extend_btn.setToolTip(
        tr(
            "page.premium.action.extend.description",
            "Открыть Telegram-бота для продления подписки или покупки Premium.",
        )
    )
    extend_btn.clicked.connect(on_open_bot)
    actions_bar.add_button(extend_btn)

    return PremiumActionsWidgets(
        actions_bar=actions_bar,
        refresh_btn=refresh_btn,
        change_key_btn=change_key_btn,
        test_btn=test_btn,
        extend_btn=extend_btn,
    )
