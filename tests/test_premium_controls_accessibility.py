from __future__ import annotations

import os
import unittest
from datetime import datetime
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qfluentwidgets import SubtitleLabel
from PyQt6.QtWidgets import QApplication, QWidget

from donater.ui.build import (
    build_premium_actions_section,
    build_premium_activation_section,
    build_premium_device_info_section,
)
from donater.ui.page_plans import build_connection_test_start_plan
from donater.ui.pairing_workflow import (
    apply_device_info_snapshot_labels,
    apply_pair_code_result_ui,
    apply_pair_code_start_ui,
)
from donater.ui.page_lifecycle import apply_premium_language, render_activation_status_label
from donater.ui.status_workflow import apply_connection_test_plan, render_server_status_label
from donater.ui.page import PremiumPage
from donater.ui.status_card import StatusCard


class PremiumControlsAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_premium_buttons_have_screen_reader_names(self) -> None:
        parent = QWidget()

        activation = build_premium_activation_section(
            tr=lambda _key, default: default,
            on_create_pair_code=lambda: None,
        )
        device = build_premium_device_info_section(
            tr=lambda _key, default: default,
            on_open_bot=lambda: None,
        )
        actions = build_premium_actions_section(
            parent=parent,
            tr=lambda _key, default: default,
            on_check_status=lambda: None,
            on_change_key=lambda: None,
            on_test_connection=lambda: None,
            on_open_bot=lambda: None,
        )

        self.assertEqual(activation.activate_btn.accessibleName(), "Создать код привязки Premium")
        self.assertEqual(activation.activate_btn.property("screenReaderStateText"), "Создать код привязки Premium")
        self.assertIn("Telegram", activation.activate_btn.accessibleDescription())
        self.assertEqual(device.open_bot_btn.accessibleName(), "Открыть Premium-бота")
        self.assertIn("Telegram", device.open_bot_btn.accessibleDescription())
        self.assertEqual(actions.refresh_btn.accessibleName(), "Обновить Premium-статус")
        self.assertIn("Premium-статус", actions.refresh_btn.accessibleDescription())
        self.assertEqual(actions.change_key_btn.accessibleName(), "Сбросить Premium-активацию")
        self.assertIn("Удаляет токен", actions.change_key_btn.accessibleDescription())
        self.assertEqual(actions.test_btn.accessibleName(), "Проверить соединение Premium")
        self.assertEqual(actions.test_btn.property("screenReaderStateText"), "Проверить соединение Premium")
        self.assertIn("Premium backend", actions.test_btn.accessibleDescription())
        self.assertEqual(actions.extend_btn.accessibleName(), "Продлить Premium-подписку")
        self.assertIn("Telegram-бота", actions.extend_btn.accessibleDescription())
        self.assertEqual(activation.key_input.accessibleName(), "Код привязки Premium: пока не создан")
        self.assertIn("код, который нужно отправить", activation.key_input.accessibleDescription())

    def test_premium_device_info_labels_expose_state_text(self) -> None:
        device = build_premium_device_info_section(
            tr=lambda _key, default: default,
            on_open_bot=lambda: None,
        )

        self.assertEqual(device.device_id_label.accessibleName(), "ID устройства: загрузка...")
        self.assertEqual(device.saved_key_label.accessibleName(), "Токен устройства: не найден")
        self.assertEqual(device.last_check_label.accessibleName(), "Последняя проверка Premium: —")
        self.assertEqual(device.server_status_label.accessibleName(), "Статус Premium-сервера: проверка...")

        apply_device_info_snapshot_labels(
            snapshot={
                "device_id": "abcdef0123456789abcdef",
                "device_token": "token",
                "pair_code": "ABCD12EF",
                "last_check": datetime(2026, 6, 10, 12, 30),
            },
            tr=lambda _key, default, **kwargs: default.format(**kwargs) if kwargs else default,
            device_id_label=device.device_id_label,
            saved_key_label=device.saved_key_label,
            last_check_label=device.last_check_label,
        )

        self.assertEqual(device.device_id_label.accessibleName(), "ID устройства: abcdef0123456789...")
        self.assertEqual(device.saved_key_label.accessibleName(), "Токен устройства: есть. Код привязки: ABCD12EF")
        self.assertEqual(device.last_check_label.accessibleName(), "Последняя проверка Premium: 10.06.2026 12:30")

    def test_premium_language_refresh_keeps_screen_reader_names(self) -> None:
        parent = QWidget()
        activation = build_premium_activation_section(
            tr=lambda _key, default: default,
            on_create_pair_code=lambda: None,
        )
        device = build_premium_device_info_section(
            tr=lambda _key, default: default,
            on_open_bot=lambda: None,
        )
        actions = build_premium_actions_section(
            parent=parent,
            tr=lambda _key, default: default,
            on_check_status=lambda: None,
            on_change_key=lambda: None,
            on_test_connection=lambda: None,
            on_open_bot=lambda: None,
        )

        apply_premium_language(
            tr_fn=lambda _key, default: default,
            activation_in_progress=True,
            connection_test_in_progress=True,
            instructions_label=activation.instructions_label,
            key_input=activation.key_input,
            activate_btn=activation.activate_btn,
            open_bot_btn=device.open_bot_btn,
            refresh_btn=actions.refresh_btn,
            change_key_btn=actions.change_key_btn,
            extend_btn=actions.extend_btn,
            test_btn=actions.test_btn,
            render_server_status_fn=lambda: None,
            render_days_label_fn=lambda: None,
            render_status_badge_fn=lambda: None,
            render_activation_status_fn=lambda: None,
        )

        self.assertEqual(activation.activate_btn.accessibleName(), "Создание кода привязки Premium")
        self.assertEqual(activation.activate_btn.property("screenReaderStateText"), "Создание кода привязки Premium")
        self.assertEqual(actions.test_btn.accessibleName(), "Проверка соединения Premium выполняется")
        self.assertEqual(actions.test_btn.property("screenReaderStateText"), "Проверка соединения Premium выполняется")
        self.assertEqual(actions.refresh_btn.accessibleName(), "Обновить Premium-статус")
        self.assertEqual(actions.extend_btn.accessibleName(), "Продлить Premium-подписку")
        self.assertEqual(activation.key_input.accessibleName(), "Код привязки Premium: пока не создан")

    def test_premium_runtime_actions_update_screen_reader_names(self) -> None:
        parent = QWidget()
        activation = build_premium_activation_section(
            tr=lambda _key, default: default,
            on_create_pair_code=lambda: None,
        )
        actions = build_premium_actions_section(
            parent=parent,
            tr=lambda _key, default: default,
            on_check_status=lambda: None,
            on_change_key=lambda: None,
            on_test_connection=lambda: None,
            on_open_bot=lambda: None,
        )

        apply_pair_code_start_ui(
            activate_btn=activation.activate_btn,
            key_input=activation.key_input,
            tr=lambda _key, default: default,
            set_activation_status=lambda **_kwargs: None,
            stop_autopoll=lambda: None,
        )
        apply_connection_test_plan(
            build_connection_test_start_plan(checker_ready=True),
            tr=lambda _key, default: default,
            test_btn=actions.test_btn,
            render_server_status=lambda: None,
            set_server_status_state=lambda *_args: None,
        )

        self.assertEqual(activation.activate_btn.accessibleName(), "Создание кода привязки Premium")
        self.assertEqual(activation.activate_btn.property("screenReaderStateText"), "Создание кода привязки Premium")
        self.assertEqual(actions.test_btn.accessibleName(), "Проверка соединения Premium выполняется")
        self.assertEqual(actions.test_btn.property("screenReaderStateText"), "Проверка соединения Premium выполняется")
        self.assertEqual(activation.key_input.accessibleName(), "Код привязки Premium: пока не создан")

        apply_pair_code_result_ui(
            (True, "ok", "ABCD12EF"),
            activate_btn=activation.activate_btn,
            key_input=activation.key_input,
            tr=lambda _key, default: default,
            set_activation_status=lambda **_kwargs: None,
            update_device_info=lambda: None,
            start_autopoll=lambda: None,
            stop_autopoll=lambda: None,
        )

        self.assertEqual(activation.key_input.accessibleName(), "Код привязки Premium: ABCD12EF")
        self.assertEqual(activation.key_input.property("screenReaderStateText"), "Код привязки Premium: ABCD12EF")

    def test_premium_status_labels_expose_state_text(self) -> None:
        activation = build_premium_activation_section(
            tr=lambda _key, default: default,
            on_create_pair_code=lambda: None,
        )
        device = build_premium_device_info_section(
            tr=lambda _key, default, **kwargs: default.format(**kwargs),
            on_open_bot=lambda: None,
        )

        render_activation_status_label(
            activation_status_state={
                "text_key": "page.premium.activation.created",
                "text_default": "Код создан: {code}",
                "text_kwargs": {"code": "ABCD12EF"},
            },
            tr_fn=lambda _key, default, **kwargs: default.format(**kwargs),
            activation_status_label=activation.activation_status,
        )
        render_server_status_label(
            device.server_status_label,
            tr=lambda _key, default, **kwargs: default.format(**kwargs),
            mode="result",
            message="соединение работает",
            success=True,
        )

        self.assertEqual(
            activation.activation_status.property("screenReaderStateText"),
            "Статус Premium-активации: Код создан: ABCD12EF",
        )
        self.assertEqual(
            device.server_status_label.property("screenReaderStateText"),
            "Статус Premium-сервера: соединение работает",
        )

    def test_premium_page_activation_status_updates_state_text(self) -> None:
        activation = build_premium_activation_section(
            tr=lambda _key, default: default,
            on_create_pair_code=lambda: None,
        )
        page = SimpleNamespace(
            activation_status=activation.activation_status,
            _tr=lambda _key, default, **kwargs: default.format(**kwargs),
        )

        PremiumPage._set_activation_status(
            page,
            text_key="page.premium.activation.created",
            text_default="Код создан: {code}",
            text_kwargs={"code": "ABCD12EF"},
        )

        self.assertEqual(
            activation.activation_status.property("screenReaderStateText"),
            "Статус Premium-активации: Код создан: ABCD12EF",
        )

    def test_premium_days_label_exposes_state_text(self) -> None:
        page = SimpleNamespace(
            days_label=SubtitleLabel(""),
            _tr=lambda _key, default, **kwargs: default.format(**kwargs),
        )
        self.addCleanup(page.days_label.deleteLater)

        page._days_state_kind = "normal"
        page._days_state_value = 40
        PremiumPage._render_days_label(page)

        self.assertEqual(page.days_label.accessibleName(), "Осталось дней Premium: 40")
        self.assertEqual(page.days_label.property("screenReaderStateText"), "Осталось дней Premium: 40")

        page._days_state_kind = "urgent"
        page._days_state_value = 3
        PremiumPage._render_days_label(page)

        self.assertEqual(page.days_label.accessibleName(), "Premium срочно нужно продлить, осталось дней: 3")
        self.assertEqual(
            page.days_label.property("screenReaderStateText"),
            "Premium срочно нужно продлить, осталось дней: 3",
        )

        page._days_state_kind = "none"
        page._days_state_value = 0
        PremiumPage._render_days_label(page)

        self.assertEqual(page.days_label.accessibleName(), "Premium-подписка не активна")
        self.assertEqual(page.days_label.property("screenReaderStateText"), "Premium-подписка не активна")

    def test_premium_status_card_exposes_state_text(self) -> None:
        card = StatusCard()
        self.addCleanup(card.deleteLater)

        card.set_status("Premium активен", "Осталось 7 дней", "active")

        self.assertEqual(card.accessibleName(), "Статус Premium: Premium активен. Осталось 7 дней")
        self.assertEqual(
            card.property("screenReaderStateText"),
            "Статус Premium: Premium активен. Осталось 7 дней",
        )


if __name__ == "__main__":
    unittest.main()
