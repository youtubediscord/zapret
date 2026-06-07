from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget

from donater.ui.build import (
    build_premium_actions_section,
    build_premium_activation_section,
    build_premium_device_info_section,
)
from donater.ui.page_plans import build_connection_test_start_plan
from donater.ui.pairing_workflow import apply_pair_code_start_ui
from donater.ui.page_lifecycle import apply_premium_language
from donater.ui.status_workflow import apply_connection_test_plan


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
        self.assertIn("Telegram", activation.activate_btn.accessibleDescription())
        self.assertEqual(device.open_bot_btn.accessibleName(), "Открыть Premium-бота")
        self.assertIn("Telegram", device.open_bot_btn.accessibleDescription())
        self.assertEqual(actions.refresh_btn.accessibleName(), "Обновить Premium-статус")
        self.assertIn("Premium-статус", actions.refresh_btn.accessibleDescription())
        self.assertEqual(actions.change_key_btn.accessibleName(), "Сбросить Premium-активацию")
        self.assertIn("Удаляет токен", actions.change_key_btn.accessibleDescription())
        self.assertEqual(actions.test_btn.accessibleName(), "Проверить соединение Premium")
        self.assertIn("Premium backend", actions.test_btn.accessibleDescription())
        self.assertEqual(actions.extend_btn.accessibleName(), "Продлить Premium-подписку")
        self.assertIn("Telegram-бота", actions.extend_btn.accessibleDescription())

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
        self.assertEqual(actions.test_btn.accessibleName(), "Проверка соединения Premium выполняется")
        self.assertEqual(actions.refresh_btn.accessibleName(), "Обновить Premium-статус")
        self.assertEqual(actions.extend_btn.accessibleName(), "Продлить Premium-подписку")

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
        self.assertEqual(actions.test_btn.accessibleName(), "Проверка соединения Premium выполняется")


if __name__ == "__main__":
    unittest.main()
