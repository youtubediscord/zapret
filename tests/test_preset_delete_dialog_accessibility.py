import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from presets.ui.common.preset_subpage_base import PresetRawEditorPage
from presets.ui.common.user_presets_page import UserPresetsPageBase


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


class PresetDeleteDialogAccessibilityTests(unittest.TestCase):
    def _make_user_presets_page(self) -> UserPresetsPageBase:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._config = SimpleNamespace(tr_prefix="presets")
        page._tr = lambda _key, default, **kwargs: default.format(**kwargs)
        page._resolve_display_name = lambda _name: "Дом"
        page._is_builtin_preset_file = lambda _name: False
        page._request_preset_item_action = Mock()
        page.window = lambda: None
        return page

    def _make_raw_editor_page(self) -> PresetRawEditorPage:
        page = PresetRawEditorPage.__new__(PresetRawEditorPage)
        page._preset_name = "Дом"
        page._preset_file_name = "Дом.txt"
        page._is_current_builtin = lambda: False
        page._run_after_raw_preset_save = lambda _callback: True
        page._request_raw_preset_action = Mock()
        page._show_error = Mock()
        page.window = lambda: None
        return page

    def test_user_presets_reset_dialog_buttons_are_named_for_screen_reader(self) -> None:
        page = self._make_user_presets_page()
        _MessageBox.instances = []

        with patch("presets.ui.common.user_presets_page.MessageBox", _MessageBox):
            UserPresetsPageBase._on_reset_preset(page, "Дом.txt")

        dialog = _MessageBox.instances[0]
        self.assertEqual(dialog.yesButton.accessibleName(), "Вернуть встроенный пресет")
        self.assertIn("изменённый файл пресета", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить возврат встроенного пресета")
        self.assertTrue(dialog.exec_called)
        page._request_preset_item_action.assert_not_called()

    def test_user_presets_delete_dialog_buttons_are_named_for_screen_reader(self) -> None:
        page = self._make_user_presets_page()
        _MessageBox.instances = []

        with patch("presets.ui.common.user_presets_page.MessageBox", _MessageBox):
            UserPresetsPageBase._on_delete_preset(page, "Дом.txt")

        dialog = _MessageBox.instances[0]
        self.assertEqual(dialog.yesButton.accessibleName(), "Удалить пользовательский пресет")
        self.assertIn("пользовательский пресет", dialog.yesButton.accessibleDescription().lower())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить удаление пользовательского пресета")
        self.assertTrue(dialog.exec_called)
        page._request_preset_item_action.assert_not_called()

    def test_raw_preset_reset_dialog_buttons_are_named_for_screen_reader(self) -> None:
        page = self._make_raw_editor_page()
        _MessageBox.instances = []

        with patch("presets.ui.common.preset_subpage_base.MessageBox", _MessageBox):
            PresetRawEditorPage._reset_preset(page)

        dialog = _MessageBox.instances[0]
        self.assertEqual(dialog.yesButton.accessibleName(), "Вернуть встроенный пресет")
        self.assertIn("изменённый файл пресета", dialog.yesButton.accessibleDescription())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить возврат встроенного пресета")
        self.assertTrue(dialog.exec_called)
        page._request_raw_preset_action.assert_not_called()

    def test_raw_preset_delete_dialog_buttons_are_named_for_screen_reader(self) -> None:
        page = self._make_raw_editor_page()
        _MessageBox.instances = []

        with patch("presets.ui.common.preset_subpage_base.MessageBox", _MessageBox):
            PresetRawEditorPage._delete_preset(page)

        dialog = _MessageBox.instances[0]
        self.assertEqual(dialog.yesButton.accessibleName(), "Удалить пользовательский пресет")
        self.assertIn("пользовательский пресет", dialog.yesButton.accessibleDescription().lower())
        self.assertEqual(dialog.cancelButton.accessibleName(), "Отменить удаление пользовательского пресета")
        self.assertTrue(dialog.exec_called)
        page._request_raw_preset_action.assert_not_called()


if __name__ == "__main__":
    unittest.main()
