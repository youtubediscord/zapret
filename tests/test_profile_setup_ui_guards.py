from __future__ import annotations

import unittest


class _TextWidget:
    def __init__(self, text: str = "") -> None:
        self._text = str(text)
        self.calls: list[str] = []

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:  # noqa: N802
        value = str(text)
        self.calls.append(value)
        self._text = value


class _BoolWidget:
    def __init__(self, *, checked: bool = False, enabled: bool = True, visible: bool = True) -> None:
        self._checked = bool(checked)
        self._enabled = bool(enabled)
        self._visible = bool(visible)
        self.checked_calls: list[bool] = []
        self.enabled_calls: list[bool] = []
        self.visible_calls: list[bool] = []

    def isChecked(self) -> bool:  # noqa: N802
        return self._checked

    def setChecked(self, checked: bool) -> None:  # noqa: N802
        value = bool(checked)
        self.checked_calls.append(value)
        self._checked = value

    def isEnabled(self) -> bool:  # noqa: N802
        return self._enabled

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        value = bool(enabled)
        self.enabled_calls.append(value)
        self._enabled = value

    def isVisible(self) -> bool:  # noqa: N802
        return self._visible

    def setVisible(self, visible: bool) -> None:  # noqa: N802
        value = bool(visible)
        self.visible_calls.append(value)
        self._visible = value


class _IndexWidget:
    def __init__(self, index: int = 0) -> None:
        self._index = int(index)
        self.calls: list[int] = []

    def currentIndex(self) -> int:  # noqa: N802
        return self._index

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802
        value = int(index)
        self.calls.append(value)
        self._index = value


class ProfileSetupUiGuardTests(unittest.TestCase):
    def test_text_update_skips_duplicate_value(self) -> None:
        from profile.ui.profile_setup_page import set_widget_text_if_changed

        widget = _TextWidget("Готово")

        self.assertFalse(set_widget_text_if_changed(widget, "Готово"))
        self.assertEqual(widget.calls, [])

        self.assertTrue(set_widget_text_if_changed(widget, "Обновлено"))
        self.assertEqual(widget.calls, ["Обновлено"])

    def test_boolean_updates_skip_duplicate_values(self) -> None:
        from profile.ui.profile_setup_page import (
            set_widget_checked_if_changed,
            set_widget_enabled_if_changed,
            set_widget_visible_if_changed,
        )

        widget = _BoolWidget(checked=True, enabled=False, visible=True)

        self.assertFalse(set_widget_checked_if_changed(widget, True))
        self.assertFalse(set_widget_enabled_if_changed(widget, False))
        self.assertFalse(set_widget_visible_if_changed(widget, True))
        self.assertEqual(widget.checked_calls, [])
        self.assertEqual(widget.enabled_calls, [])
        self.assertEqual(widget.visible_calls, [])

        self.assertTrue(set_widget_checked_if_changed(widget, False))
        self.assertTrue(set_widget_enabled_if_changed(widget, True))
        self.assertTrue(set_widget_visible_if_changed(widget, False))
        self.assertEqual(widget.checked_calls, [False])
        self.assertEqual(widget.enabled_calls, [True])
        self.assertEqual(widget.visible_calls, [False])

    def test_current_index_update_skips_duplicate_value(self) -> None:
        from profile.ui.profile_setup_page import set_current_index_if_changed

        widget = _IndexWidget(1)

        self.assertFalse(set_current_index_if_changed(widget, 1))
        self.assertEqual(widget.calls, [])

        self.assertTrue(set_current_index_if_changed(widget, 0))
        self.assertEqual(widget.calls, [0])


if __name__ == "__main__":
    unittest.main()
