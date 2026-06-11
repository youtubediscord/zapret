from __future__ import annotations

import unittest
from unittest.mock import Mock, patch


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


class _PlaceholderWidget:
    def __init__(self, text: str = "") -> None:
        self._placeholder = str(text)
        self.calls: list[str] = []

    def placeholderText(self) -> str:  # noqa: N802
        return self._placeholder

    def setPlaceholderText(self, text: str) -> None:  # noqa: N802
        value = str(text)
        self.calls.append(value)
        self._placeholder = value


class UserPresetsLifecycleGuardTests(unittest.TestCase):
    def test_text_update_skips_duplicate_value(self) -> None:
        from presets.ui.common.user_presets_page_lifecycle import set_widget_text_if_changed

        widget = _TextWidget("Импорт")

        self.assertFalse(set_widget_text_if_changed(widget, "Импорт"))
        self.assertEqual(widget.calls, [])

        self.assertTrue(set_widget_text_if_changed(widget, "Загрузить"))
        self.assertEqual(widget.calls, ["Загрузить"])

    def test_placeholder_update_skips_duplicate_value(self) -> None:
        from presets.ui.common.user_presets_page_lifecycle import set_placeholder_if_changed

        widget = _PlaceholderWidget("Поиск пресетов по имени...")

        self.assertFalse(set_placeholder_if_changed(widget, "Поиск пресетов по имени..."))
        self.assertEqual(widget.calls, [])

        self.assertTrue(set_placeholder_if_changed(widget, "Поиск"))
        self.assertEqual(widget.calls, ["Поиск"])

    def test_page_mode_labels_skip_duplicate_text(self) -> None:
        from types import SimpleNamespace

        from presets.ui.common.user_presets_page import UserPresetsPageBase

        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page.title_label = _TextWidget("Мои пресеты")
        page.subtitle_label = _TextWidget("")
        page._config = SimpleNamespace(title_key="page.title")
        page._tr = lambda _key, default: default

        UserPresetsPageBase._apply_mode_labels(page)

        self.assertEqual(page.title_label.calls, [])
        self.assertEqual(page.subtitle_label.calls, [])

    def test_sidebar_search_skips_duplicate_query_refresh(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase

        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_search_input = _TextWidget("Discord")
        page._apply_preset_search = Mock(side_effect=AssertionError("same search query must not refresh presets"))

        self.assertTrue(UserPresetsPageBase.apply_sidebar_search_query(page, "Discord"))

        page._apply_preset_search.assert_not_called()

    def test_clean_activation_restores_presets_list_after_show(self) -> None:
        from presets.ui.common.user_presets_page import UserPresetsPageBase

        class _List:
            def __init__(self) -> None:
                self.visible_calls: list[bool] = []

            def setVisible(self, value: bool) -> None:  # noqa: N802
                self.visible_calls.append(bool(value))

        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        presets_list = _List()
        page.presets_list = presets_list
        page._cleanup_in_progress = False
        page._presets_list_show_scheduled = False
        page._layout_resync_timer = Mock()
        page._layout_resync_delayed_timer = Mock()
        page._runtime_service = Mock()
        page._runtime_service.is_ui_dirty.return_value = False
        page._apply_mode_labels = Mock()
        page._resync_layout_metrics = Mock(
            side_effect=AssertionError("clean activation must not fully resync layout")
        )
        page._start_watching_presets = Mock()
        page.refresh_presets_view_if_possible = Mock(
            side_effect=AssertionError("clean activation must not reload presets")
        )
        page._update_presets_view_height = Mock()
        page._schedule_layout_resync = Mock(
            side_effect=AssertionError("clean activation must not schedule full layout resync")
        )
        scheduled: list[object] = []

        with patch(
            "presets.ui.common.user_presets_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: scheduled.append(callback),
        ):
            UserPresetsPageBase.on_page_hidden(page)
            UserPresetsPageBase.on_page_activated(page)

        self.assertEqual(presets_list.visible_calls, [False])
        page.refresh_presets_view_if_possible.assert_not_called()
        page._update_presets_view_height.assert_called_once_with()
        self.assertEqual(len(scheduled), 1)

        scheduled[0]()

        self.assertEqual(presets_list.visible_calls, [False, True])


if __name__ == "__main__":
    unittest.main()
