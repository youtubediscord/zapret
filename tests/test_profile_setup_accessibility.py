import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from profile.ui.preset_setup_page import PresetSetupPageBase
from profile.ui.profile_setup_page import ProfileSetupPageBase


def _worker_stub(*_args, **_kwargs):
    return None


class _DialogButton:
    def __init__(self) -> None:
        self._text = ""
        self._accessible_name = ""
        self._accessible_description = ""

    def setText(self, text: str) -> None:  # noqa: N802
        self._text = str(text)

    def text(self) -> str:
        return self._text

    def accessibleName(self) -> str:  # noqa: N802
        return self._accessible_name

    def setAccessibleName(self, text: str) -> None:  # noqa: N802
        self._accessible_name = str(text)

    def accessibleDescription(self) -> str:  # noqa: N802
        return self._accessible_description

    def setAccessibleDescription(self, text: str) -> None:  # noqa: N802
        self._accessible_description = str(text)


class _MessageBox:
    instances: list["_MessageBox"] = []

    def __init__(self, title: str, body: str, parent=None) -> None:
        self.title = title
        self.body = body
        self.parent = parent
        self.yesButton = _DialogButton()
        self.cancelButton = _DialogButton()
        self.exec_called = False
        _MessageBox.instances.append(self)

    def exec(self) -> bool:
        self.exec_called = True
        return False


class ProfileSetupAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _make_page(self) -> ProfileSetupPageBase:
        return ProfileSetupPageBase(
            create_profile_setup_load_worker=_worker_stub,
            create_profile_list_file_load_worker=_worker_stub,
            create_profile_list_file_save_worker=_worker_stub,
            create_profile_list_file_validation_worker=_worker_stub,
            create_profile_settings_save_worker=_worker_stub,
            create_profile_raw_text_save_worker=_worker_stub,
            create_profile_enabled_save_worker=_worker_stub,
            create_profile_user_update_worker=_worker_stub,
            create_profile_user_delete_worker=_worker_stub,
            create_profile_strategy_apply_worker=_worker_stub,
            create_profile_strategy_feedback_save_worker=_worker_stub,
            open_profiles=lambda: None,
            open_root=lambda: None,
            on_profile_changed=lambda: None,
        )

    def test_main_controls_are_named_for_screen_reader(self) -> None:
        page = self._make_page()
        self.addCleanup(page.deleteLater)
        page._ensure_editor_tab_built()
        page._ensure_match_tab_built()

        self.assertEqual(page._enabled_checkbox.accessibleName(), "Profile, выключено")
        self.assertEqual(page._enabled_checkbox.property("screenReaderStateText"), "Profile, выключено")
        self.assertIn("Включает или отключает", page._enabled_checkbox.accessibleDescription())
        self.assertEqual(page._filter_combo.accessibleName(), "Тип списка profile, выбрано: Hostlist")
        self.assertEqual(
            page._filter_combo.property("screenReaderStateText"),
            "Тип списка profile, выбрано: Hostlist",
        )
        self.assertEqual(page._filter_value.accessibleName(), "Файл списка profile")
        self.assertEqual(page._in_range_mode.accessibleName(), "Режим in-range, выбрано: a — всегда")
        self.assertEqual(
            page._in_range_mode.property("screenReaderStateText"),
            "Режим in-range, выбрано: a — всегда",
        )
        self.assertEqual(page._out_range_mode.accessibleName(), "Режим out-range, выбрано: a — всегда")
        self.assertEqual(
            page._out_range_mode.property("screenReaderStateText"),
            "Режим out-range, выбрано: a — всегда",
        )
        self.assertEqual(page._strategy_branch_combo.accessibleName(), "Ветка готовой стратегии, не выбрано")
        self.assertEqual(
            page._strategy_branch_combo.property("screenReaderStateText"),
            "Ветка готовой стратегии, не выбрано",
        )
        self.assertEqual(page._list_file_base_text.accessibleName(), "Базовая часть списка profile")
        self.assertEqual(page._list_file_text.accessibleName(), "Ваши записи списка profile")
        self.assertEqual(page._list_file_save_button.accessibleName(), "Сохранить список profile")
        self.assertEqual(page._match_text.accessibleName(), "Условия применения profile")
        self.assertEqual(page._raw_profile_text.accessibleName(), "Текст profile в текущем preset")
        self.assertEqual(page._raw_profile_save_button.accessibleName(), "Сохранить текст profile")
        self.assertEqual(page._work_button.accessibleName(), "Отметить стратегию как рабочую")
        self.assertEqual(page._notwork_button.accessibleName(), "Отметить стратегию как нерабочую")
        self.assertEqual(page._favorite_button.accessibleName(), "Добавить стратегию в избранное")
        self.assertEqual(page._clear_feedback_button.accessibleName(), "Убрать оценку стратегии")

    def test_strategy_tabs_read_current_section_for_screen_reader(self) -> None:
        page = self._make_page()
        self.addCleanup(page.deleteLater)

        self.assertEqual(page._strategy_tabs.accessibleName(), "Разделы profile, выбрано: Готовые стратегии")
        self.assertIn("Готовые стратегии, Редактор или Когда применяется", page._strategy_tabs.accessibleDescription())

        page._strategy_tabs.setCurrentItem("match")

        self.assertEqual(page._strategy_tabs.accessibleName(), "Разделы profile, выбрано: Когда применяется")
        self.assertEqual(
            page._strategy_tabs.property("screenReaderStateText"),
            "Разделы profile, выбрано: Когда применяется",
        )

    def test_strategy_branch_combo_options_are_named_for_screen_reader(self) -> None:
        page = self._make_page()
        self.addCleanup(page.deleteLater)
        payload = SimpleNamespace(
            current_strategy_branch_id="branch:2",
            strategy_branches=(
                SimpleNamespace(
                    branch_id="branch:1",
                    payload="tls",
                    in_range="",
                    out_range="",
                    strategy_name="TLS fake",
                ),
                SimpleNamespace(
                    branch_id="branch:2",
                    payload="http",
                    in_range="",
                    out_range="",
                    strategy_name="HTTP fake",
                ),
            ),
        )

        page._apply_strategy_branch_selector(payload)
        create_menu = getattr(page._strategy_branch_combo, "_create_accessible_combo_menu", None)
        self.assertIsNotNone(create_menu)
        menu = create_menu()

        self.assertEqual(
            menu.view.item(0).data(Qt.ItemDataRole.AccessibleTextRole),
            "Ветка готовой стратегии: payload: tls — TLS fake, не выбрана",
        )
        self.assertEqual(
            menu.view.item(1).data(Qt.ItemDataRole.AccessibleTextRole),
            "Ветка готовой стратегии: payload: http — HTTP fake, выбрана",
        )

    def test_range_mode_combo_options_are_named_for_screen_reader(self) -> None:
        page = self._make_page()
        self.addCleanup(page.deleteLater)

        menu = page._in_range_mode._create_accessible_combo_menu()

        self.assertEqual(
            menu.view.item(0).data(Qt.ItemDataRole.AccessibleTextRole),
            "Режим in-range: a — всегда, выбран",
        )
        self.assertEqual(
            menu.view.item(1).data(Qt.ItemDataRole.AccessibleTextRole),
            "Режим in-range: x — никогда, не выбран",
        )

    def test_filter_kind_combo_options_are_named_for_screen_reader(self) -> None:
        page = self._make_page()
        self.addCleanup(page.deleteLater)
        create_menu = getattr(page._filter_combo, "_create_accessible_combo_menu", None)
        self.assertIsNotNone(create_menu)

        menu = create_menu()

        self.assertEqual(
            menu.view.item(0).data(Qt.ItemDataRole.AccessibleTextRole),
            "Тип списка profile: Hostlist, выбран",
        )
        self.assertEqual(
            menu.view.item(1).data(Qt.ItemDataRole.AccessibleTextRole),
            "Тип списка profile: IPset, не выбран",
        )

    def test_delete_user_profile_dialog_buttons_are_named_for_screen_reader(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "template:user:user-1"
        page._payload = SimpleNamespace(item=SimpleNamespace(user_profile_id=""))
        page._request_user_profile_delete = Mock()
        _MessageBox.instances = []

        with patch("profile.ui.profile_setup_page.MessageBox", _MessageBox):
            ProfileSetupPageBase._on_delete_user_profile_clicked(page)

        dialog = _MessageBox.instances[0]
        self.assertEqual(dialog.yesButton.accessibleName(), "Удалить пользовательский profile")
        self.assertIn("будет удалён из библиотеки", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить удаление пользовательского profile")
        self.assertTrue(dialog.exec_called)
        page._request_user_profile_delete.assert_not_called()

    def test_delete_profile_from_preset_dialog_buttons_are_named_for_screen_reader(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._request_profile_context_action = Mock()
        _MessageBox.instances = []

        with patch("profile.ui.preset_setup_page.MessageBox", _MessageBox):
            PresetSetupPageBase._delete_profile_from_menu(page, "profile-1")

        dialog = _MessageBox.instances[0]
        self.assertEqual(dialog.yesButton.accessibleName(), "Удалить profile из текущего preset")
        self.assertIn("только из текущего preset", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить удаление profile из preset")
        self.assertTrue(dialog.exec_called)
        page._request_profile_context_action.assert_not_called()

    def test_delete_user_profile_from_preset_dialog_buttons_are_named_for_screen_reader(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profiles_list = SimpleNamespace(
            profile_item_for_key=lambda _profile_key: SimpleNamespace(user_profile_id="")
        )
        page._request_user_profile_delete = Mock()
        _MessageBox.instances = []

        with patch("profile.ui.preset_setup_page.MessageBox", _MessageBox):
            PresetSetupPageBase._delete_user_profile_from_menu(page, "template:user:user-1")

        dialog = _MessageBox.instances[0]
        self.assertEqual(dialog.yesButton.accessibleName(), "Удалить пользовательский profile")
        self.assertIn("будет удалён из библиотеки", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить удаление пользовательского profile")
        self.assertTrue(dialog.exec_called)
        page._request_user_profile_delete.assert_not_called()

    def test_preset_profile_info_dialog_close_button_is_named_for_screen_reader(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        _MessageBox.instances = []

        with patch("profile.ui.preset_setup_page.MessageBox", _MessageBox):
            PresetSetupPageBase._show_profile_info(page)

        dialog = _MessageBox.instances[0]
        self.assertEqual(dialog.yesButton.accessibleName(), "Закрыть справку о настройке пресета")
        self.assertIn("Закрывает справку", dialog.yesButton.accessibleDescription())
        self.assertTrue(dialog.exec_called)


if __name__ == "__main__":
    unittest.main()
