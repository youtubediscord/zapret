from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QIcon, QKeyEvent
from PyQt6.QtWidgets import QApplication, QWidget
from qfluentwidgets import CaptionLabel, IndeterminateProgressBar, PrimaryPushButton, PushButton, PushSettingCard


class _ButtonTarget:
    def __init__(self) -> None:
        self._text = ""
        self._accessible_name = ""
        self._accessible_description = ""
        self._properties = {}
        self.fixed_width = None

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:  # noqa: N802
        self._text = str(text)

    def accessibleName(self) -> str:  # noqa: N802
        return self._accessible_name

    def setAccessibleName(self, text: str) -> None:  # noqa: N802
        self._accessible_name = str(text)

    def accessibleDescription(self) -> str:  # noqa: N802
        return self._accessible_description

    def setAccessibleDescription(self, text: str) -> None:  # noqa: N802
        self._accessible_description = str(text)

    def setIcon(self, _icon) -> None:  # noqa: N802
        pass

    def setMinimumWidth(self, _width: int) -> None:  # noqa: N802
        pass

    def setFixedWidth(self, width: int) -> None:  # noqa: N802
        self.fixed_width = int(width)

    def property(self, name: str) -> object:  # noqa: A003
        return self._properties.get(name)

    def setProperty(self, name: str, value: object) -> None:  # noqa: N802
        self._properties[name] = value


class _TitleLabel:
    def __init__(self) -> None:
        self.text = ""

    def setText(self, text: str) -> None:  # noqa: N802
        self.text = str(text)


class _CardTarget:
    def __init__(self) -> None:
        self.titleLabel = _TitleLabel()
        self.button = _ButtonTarget()

    def setTitle(self, text: str) -> None:  # noqa: N802
        self.title = str(text)

    def setContent(self, text: str) -> None:  # noqa: N802
        self.content = str(text)


class _SignalTarget:
    def __init__(self) -> None:
        self.callback = None

    def connect(self, callback) -> None:
        self.callback = callback


class _PushSettingCardTarget(_CardTarget):
    def __init__(self, button_text, _icon, title_text, content_text, _parent=None) -> None:
        super().__init__()
        self.button.setText(button_text)
        self.title = str(title_text)
        self.content = str(content_text or "")
        self.clicked = _SignalTarget()

    def setProperty(self, _name: str, _value: object) -> None:  # noqa: N802
        pass


class _ToggleTarget:
    def set_texts(self, _title: str, _description: str) -> None:
        pass


def _language_refresh_kwargs() -> dict[str, object]:
    kwargs = {
        "language": "ru",
        "program_settings_card": _CardTarget(),
        "auto_dpi_toggle": _ToggleTarget(),
        "gui_autostart_toggle": _ToggleTarget(),
        "tray_close_mode_combo": _ToggleTarget(),
        "defender_toggle": _ToggleTarget(),
        "max_block_toggle": _ToggleTarget(),
        "test_card": _CardTarget(),
        "internet_cleanup_card": _CardTarget(),
        "folder_card": _CardTarget(),
        "docs_card": _CardTarget(),
        "additional_settings_card": _CardTarget(),
        "additional_settings_notice": _TitleLabel(),
        "discord_restart_toggle": _ToggleTarget(),
        "wssize_toggle": _ToggleTarget(),
        "debug_log_toggle": _ToggleTarget(),
    }
    for key in ("test_card", "internet_cleanup_card", "folder_card", "docs_card"):
        kwargs[key].button.setProperty("controlIconTextGap", True)
    return kwargs


class ControlAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_management_buttons_have_screen_reader_names_and_descriptions(self) -> None:
        from presets.ui.control.shared_builders import build_mode_management_section_common

        _card, start_btn, stop_btn, stop_exit_btn, progress, loading = build_mode_management_section_common(
            tr_fn=lambda _key, default: default,
            caption_label_cls=CaptionLabel,
            indeterminate_progress_bar_cls=IndeterminateProgressBar,
            big_action_button_cls=PrimaryPushButton,
            stop_button_cls=PushButton,
            start_key="start",
            start_default="Запустить Zapret",
            stop_key="stop",
            stop_default="Остановить winws.exe",
            stop_exit_key="stop_exit",
            stop_exit_default="Остановить и закрыть",
            on_start=lambda: None,
            on_stop=lambda: None,
            on_stop_and_exit=lambda: None,
            parent=QWidget(),
        )

        self.assertEqual(start_btn.accessibleName(), "Запустить Zapret")
        self.assertEqual(start_btn.property("screenReaderStateText"), "Запустить Zapret")
        self.assertIn("Запускает", start_btn.accessibleDescription())
        self.assertEqual(stop_btn.accessibleName(), "Остановить winws.exe")
        self.assertEqual(stop_btn.property("screenReaderStateText"), "Остановить winws.exe")
        self.assertIn("Останавливает", stop_btn.accessibleDescription())
        self.assertEqual(stop_exit_btn.accessibleName(), "Остановить и закрыть")
        self.assertEqual(stop_exit_btn.property("screenReaderStateText"), "Остановить и закрыть")
        self.assertIn("закрывает программу", stop_exit_btn.accessibleDescription())
        self.assertEqual(progress.accessibleName(), "Ход запуска Zapret: не выполняется")
        self.assertEqual(progress.property("screenReaderStateText"), "Ход запуска Zapret: не выполняется")
        self.assertIn("Показывает", progress.accessibleDescription())
        self.assertEqual(loading.accessibleName(), "Статус запуска Zapret: нет активного запуска")
        self.assertEqual(loading.property("screenReaderStateText"), "Статус запуска Zapret: нет активного запуска")

    def test_stop_button_loads_square_stop_icon_after_first_paint(self) -> None:
        from presets.ui.control.shared_builders import build_mode_management_section_common

        scheduled: list[tuple[int, object]] = []
        with patch(
            "presets.ui.control.shared_builders.get_themed_qta_icon",
            return_value=QIcon(),
        ) as get_icon, patch(
            "presets.ui.control.shared_builders.QTimer.singleShot",
            side_effect=lambda delay_ms, callback: scheduled.append((delay_ms, callback)),
        ):
            build_mode_management_section_common(
                tr_fn=lambda _key, default: default,
                caption_label_cls=CaptionLabel,
                indeterminate_progress_bar_cls=IndeterminateProgressBar,
                big_action_button_cls=PrimaryPushButton,
                stop_button_cls=PushButton,
                start_key="start",
                start_default="Запустить Zapret",
                stop_key="stop",
                stop_default="Остановить winws.exe",
                stop_exit_key="stop_exit",
                stop_exit_default="Остановить и закрыть",
                on_start=lambda: None,
                on_stop=lambda: None,
                on_stop_and_exit=lambda: None,
                parent=QWidget(),
            )

            get_icon.assert_not_called()
            self.assertEqual(len(scheduled), 1)
            self.assertGreaterEqual(scheduled[0][0], 200)
            scheduled[0][1]()
            get_icon.assert_called_once_with("fa5s.stop")

    def test_push_setting_card_button_has_specific_screen_reader_name(self) -> None:
        from presets.ui.control.shared_builders import ACTION_CARD_BUTTON_WIDTH, build_push_setting_card_common

        card = build_push_setting_card_common(
            push_setting_card_cls=_PushSettingCardTarget,
            button_text="Открыть",
            icon=QIcon(),
            title_text="Тест соединения",
            content_text="Проверить доступность сети и состояние обхода",
            on_click=lambda: None,
        )

        self.assertEqual(card.button.accessibleName(), "Открыть тест соединения")
        self.assertEqual(card.button.text(), "  Открыть")
        self.assertEqual(card.button.fixed_width, ACTION_CARD_BUTTON_WIDTH)
        self.assertIn("Проверить доступность сети", card.button.accessibleDescription())
        self.assertEqual(card.button.property("screenReaderStateText"), "Открыть тест соединения")

    def test_push_setting_card_itself_works_from_keyboard(self) -> None:
        from presets.ui.control.shared_builders import build_push_setting_card_common

        opened: list[bool] = []
        card = build_push_setting_card_common(
            push_setting_card_cls=PushSettingCard,
            button_text="Открыть",
            icon=QIcon(),
            title_text="Тест соединения",
            content_text="Проверить доступность сети и состояние обхода",
            on_click=lambda: opened.append(True),
        )

        self.assertEqual(card.accessibleName(), "Открыть тест соединения")
        self.assertEqual(card.property("screenReaderStateText"), "Открыть тест соединения")
        self.assertIn("Проверить доступность сети", card.accessibleDescription())
        self.assertEqual(card.focusPolicy(), Qt.FocusPolicy.StrongFocus)

        card.keyPressEvent(
            QKeyEvent(
                QEvent.Type.KeyPress,
                Qt.Key.Key_Return,
                Qt.KeyboardModifier.NoModifier,
            )
        )

        self.assertEqual(opened, [True])

    def test_winws1_language_refresh_updates_control_button_screen_reader_names(self) -> None:
        from presets.ui.control.zapret1.runtime_helpers import apply_winws1_pages_language

        start_btn = _ButtonTarget()
        stop_btn = _ButtonTarget()
        stop_exit_btn = _ButtonTarget()

        apply_winws1_pages_language(
            **_language_refresh_kwargs(),
            start_btn=start_btn,
            stop_winws_btn=stop_btn,
            stop_and_exit_btn=stop_exit_btn,
            refresh_preset_name=lambda: None,
            get_current_dpi_runtime_state=lambda: ("stopped", ""),
            update_status=lambda _phase, _last_error: None,
        )

        self.assertEqual(start_btn.accessibleName(), "Запустить Zapret")
        self.assertEqual(stop_btn.accessibleName(), "Остановить winws.exe")
        self.assertEqual(stop_exit_btn.accessibleName(), "Остановить и закрыть")

    def test_winws1_language_refresh_updates_extra_action_button_screen_reader_names(self) -> None:
        from presets.ui.control.zapret1.runtime_helpers import apply_winws1_pages_language

        kwargs = _language_refresh_kwargs()
        apply_winws1_pages_language(
            **kwargs,
            start_btn=_ButtonTarget(),
            stop_winws_btn=_ButtonTarget(),
            stop_and_exit_btn=_ButtonTarget(),
            refresh_preset_name=lambda: None,
            get_current_dpi_runtime_state=lambda: ("stopped", ""),
            update_status=lambda _phase, _last_error: None,
        )

        self.assertEqual(kwargs["test_card"].button.accessibleName(), "Открыть тест соединения")
        self.assertEqual(kwargs["internet_cleanup_card"].button.accessibleName(), "Сбросить сеть Windows")
        self.assertEqual(kwargs["folder_card"].button.accessibleName(), "Открыть папку программы")
        self.assertEqual(kwargs["docs_card"].button.accessibleName(), "Открыть документацию")
        self.assertEqual(kwargs["test_card"].button.text(), "  Открыть")
        self.assertEqual(kwargs["internet_cleanup_card"].button.text(), "  Сбросить")
        self.assertEqual(kwargs["folder_card"].button.text(), "  Открыть")
        self.assertEqual(kwargs["docs_card"].button.text(), "  Открыть")
        self.assertEqual(kwargs["test_card"].button.property("screenReaderStateText"), "Открыть тест соединения")
        self.assertEqual(kwargs["internet_cleanup_card"].button.property("screenReaderStateText"), "Сбросить сеть Windows")
        self.assertEqual(kwargs["folder_card"].button.property("screenReaderStateText"), "Открыть папку программы")
        self.assertEqual(kwargs["docs_card"].button.property("screenReaderStateText"), "Открыть документацию")

    def test_winws2_language_refresh_updates_control_button_screen_reader_names(self) -> None:
        from presets.ui.control.zapret2.runtime_helpers import apply_profile_language

        start_btn = _ButtonTarget()
        stop_exit_btn = _ButtonTarget()

        apply_profile_language(
            **_language_refresh_kwargs(),
            start_btn=start_btn,
            stop_and_exit_btn=stop_exit_btn,
            update_stop_button_text=lambda: None,
        )

        self.assertEqual(start_btn.accessibleName(), "Запустить Zapret")
        self.assertEqual(stop_exit_btn.accessibleName(), "Остановить и закрыть программу")

    def test_winws2_language_refresh_updates_extra_action_button_screen_reader_names(self) -> None:
        from presets.ui.control.zapret2.runtime_helpers import apply_profile_language

        kwargs = _language_refresh_kwargs()
        apply_profile_language(
            **kwargs,
            start_btn=_ButtonTarget(),
            stop_and_exit_btn=_ButtonTarget(),
            update_stop_button_text=lambda: None,
        )

        self.assertEqual(kwargs["test_card"].button.accessibleName(), "Открыть тест соединения")
        self.assertEqual(kwargs["internet_cleanup_card"].button.accessibleName(), "Сбросить сеть Windows")
        self.assertEqual(kwargs["folder_card"].button.accessibleName(), "Открыть папку программы")
        self.assertEqual(kwargs["docs_card"].button.accessibleName(), "Открыть документацию")
        self.assertEqual(kwargs["test_card"].button.text(), "  Открыть")
        self.assertEqual(kwargs["internet_cleanup_card"].button.text(), "  Сбросить")
        self.assertEqual(kwargs["folder_card"].button.text(), "  Открыть")
        self.assertEqual(kwargs["docs_card"].button.text(), "  Открыть")
        self.assertEqual(kwargs["test_card"].button.property("screenReaderStateText"), "Открыть тест соединения")
        self.assertEqual(kwargs["internet_cleanup_card"].button.property("screenReaderStateText"), "Сбросить сеть Windows")
        self.assertEqual(kwargs["folder_card"].button.property("screenReaderStateText"), "Открыть папку программы")
        self.assertEqual(kwargs["docs_card"].button.property("screenReaderStateText"), "Открыть документацию")


if __name__ == "__main__":
    unittest.main()
