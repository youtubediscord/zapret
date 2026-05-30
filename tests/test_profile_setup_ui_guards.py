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


class _PropertyWidget(_BoolWidget):
    def __init__(
        self,
        *,
        checked: bool = False,
        enabled: bool = True,
        visible: bool = True,
        properties: dict[str, object] | None = None,
    ) -> None:
        super().__init__(checked=checked, enabled=enabled, visible=visible)
        self._properties = dict(properties or {})
        self._text = ""
        self.text_calls: list[str] = []
        self.property_calls: list[tuple[str, object]] = []

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:  # noqa: N802
        value = str(text)
        self.text_calls.append(value)
        self._text = value

    def property(self, name: str):  # noqa: A003
        return self._properties.get(str(name))

    def setProperty(self, name: str, value) -> None:  # noqa: N802
        key = str(name)
        self.property_calls.append((key, value))
        self._properties[key] = value


class _LabelWidget(_PropertyWidget):
    def __init__(self, text: str = "", *, visible: bool = True) -> None:
        super().__init__(visible=visible)
        self._text = str(text)
        self.show_calls = 0
        self.hide_calls = 0
        self.clear_calls = 0

    def show(self) -> None:
        self.show_calls += 1
        self._visible = True

    def hide(self) -> None:
        self.hide_calls += 1
        self._visible = False

    def clear(self) -> None:
        self.clear_calls += 1
        self._text = ""


class _PlainTextWidget(_BoolWidget):
    def __init__(
        self,
        text: str = "",
        *,
        read_only: bool = False,
        placeholder: str = "",
        visible: bool = True,
    ) -> None:
        super().__init__(visible=visible)
        self._text = str(text)
        self._read_only = bool(read_only)
        self._placeholder = str(placeholder)
        self.block_calls: list[bool] = []
        self.plain_text_calls: list[str] = []
        self.read_only_calls: list[bool] = []
        self.placeholder_calls: list[str] = []

    def blockSignals(self, blocked: bool) -> None:  # noqa: N802
        self.block_calls.append(bool(blocked))

    def toPlainText(self) -> str:  # noqa: N802
        return self._text

    def setPlainText(self, text: str) -> None:  # noqa: N802
        value = str(text)
        self.plain_text_calls.append(value)
        self._text = value

    def isReadOnly(self) -> bool:  # noqa: N802
        return self._read_only

    def setReadOnly(self, read_only: bool) -> None:  # noqa: N802
        value = bool(read_only)
        self.read_only_calls.append(value)
        self._read_only = value

    def placeholderText(self) -> str:  # noqa: N802
        return self._placeholder

    def setPlaceholderText(self, text: str) -> None:  # noqa: N802
        value = str(text)
        self.placeholder_calls.append(value)
        self._placeholder = value


class _StyleWidget:
    def __init__(self, style: str = "") -> None:
        self._style = str(style)
        self.style_calls: list[str] = []

    def styleSheet(self) -> str:  # noqa: N802
        return self._style

    def setStyleSheet(self, style: str) -> None:  # noqa: N802
        value = str(style)
        self.style_calls.append(value)
        self._style = value


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


class _ListWidget:
    def __init__(self) -> None:
        self.clear_calls = 0
        self.items = []
        self.current_item = None
        self.current_item_calls = []
        self.update_calls = []

    def clear(self) -> None:
        self.clear_calls += 1
        self.items.clear()

    def addItem(self, item) -> None:  # noqa: N802
        self.items.append(item)

    def currentItem(self):  # noqa: N802
        return self.current_item

    def setCurrentItem(self, item) -> None:  # noqa: N802
        self.current_item_calls.append(item)
        self.current_item = item

    def viewport(self):
        return self

    def visualItemRect(self, item):  # noqa: N802
        return ("rect", item)

    def update(self, rect) -> None:
        self.update_calls.append(rect)


class _StrategyItem:
    def __init__(self, *, data: dict[int, object] | None = None, selected: bool = False) -> None:
        self._data = dict(data or {})
        self._selected = bool(selected)
        self.data_calls: list[tuple[int, object]] = []
        self.selected_calls: list[bool] = []

    def data(self, role: int):
        return self._data.get(role)

    def setData(self, role: int, value) -> None:  # noqa: N802
        self.data_calls.append((role, value))
        self._data[role] = value

    def isSelected(self) -> bool:  # noqa: N802
        return self._selected

    def setSelected(self, selected: bool) -> None:  # noqa: N802
        value = bool(selected)
        self.selected_calls.append(value)
        self._selected = value


class _Signal:
    def connect(self, _callback) -> None:
        pass


class _LoadWorker:
    def __init__(self) -> None:
        self.loaded = _Signal()
        self.failed = _Signal()
        self.finished = _Signal()
        self.start_calls = 0

    def start(self) -> None:
        self.start_calls += 1


class _SaveWorker:
    def __init__(self) -> None:
        self.saved = _Signal()
        self.failed = _Signal()
        self.finished = _Signal()
        self.start_calls = 0

    def start(self) -> None:
        self.start_calls += 1


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

    def test_property_update_skips_duplicate_value(self) -> None:
        from profile.ui.profile_setup_page import set_widget_property_if_changed

        widget = _PropertyWidget(properties={"selected": True})

        self.assertFalse(set_widget_property_if_changed(widget, "selected", True))
        self.assertEqual(widget.property_calls, [])

        self.assertTrue(set_widget_property_if_changed(widget, "selected", False))
        self.assertEqual(widget.property_calls, [("selected", False)])

    def test_feedback_buttons_skip_duplicate_state(self) -> None:
        from types import SimpleNamespace

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._work_button = _PropertyWidget(enabled=True, properties={"selected": True})
        page._notwork_button = _PropertyWidget(enabled=True, properties={"selected": False})
        page._favorite_button = _PropertyWidget(enabled=True)
        page._favorite_button._text = "Убрать из избранного"
        page._clear_feedback_button = _PropertyWidget(enabled=True)

        payload = SimpleNamespace(
            item=SimpleNamespace(in_preset=True, enabled=True, strategy_id="tls_fake"),
            current_strategy_state=SimpleNamespace(favorite=True, rating="work"),
        )

        ProfileSetupPageBase._apply_feedback_buttons(page, payload)

        self.assertEqual(page._work_button.enabled_calls, [])
        self.assertEqual(page._notwork_button.enabled_calls, [])
        self.assertEqual(page._favorite_button.enabled_calls, [])
        self.assertEqual(page._clear_feedback_button.enabled_calls, [])
        self.assertEqual(page._work_button.property_calls, [])
        self.assertEqual(page._notwork_button.property_calls, [])
        self.assertEqual(page._favorite_button.text_calls, [])
        self.assertEqual(page._favorite_button._text, "Убрать из избранного")

    def test_user_profile_buttons_skip_duplicate_enabled_state(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._update_user_profile_button = _BoolWidget(enabled=False)
        page._delete_user_profile_button = _BoolWidget(enabled=False)

        ProfileSetupPageBase._set_user_profile_buttons_enabled(page, False)

        self.assertEqual(page._update_user_profile_button.enabled_calls, [])
        self.assertEqual(page._delete_user_profile_button.enabled_calls, [])

    def test_profile_payload_request_skips_duplicate_loading_state(self) -> None:
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        worker = _LoadWorker()
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "profile-1"
        page._setup_load_request_id = 0
        page._summary = _TextWidget("Загрузка profile...")
        page._enabled_checkbox = _BoolWidget(enabled=False)
        page._controller = Mock()
        page._controller.create_load_worker.return_value = worker

        ProfileSetupPageBase._request_profile_setup_payload(page)

        self.assertEqual(page._summary.calls, [])
        self.assertEqual(page._enabled_checkbox.enabled_calls, [])
        page._controller.create_load_worker.assert_called_once_with(1, "profile-1", page)
        self.assertEqual(worker.start_calls, 1)

    def test_strategy_list_summary_skips_duplicate_text(self) -> None:
        from types import SimpleNamespace

        from profile.ui.profile_setup_page import ProfileStrategyListWidget

        widget = ProfileStrategyListWidget.__new__(ProfileStrategyListWidget)
        widget._search = _TextWidget("")
        widget._list = _ListWidget()
        widget._entries = {
            "tls_fake": SimpleNamespace(
                name="TLS fake",
                args="--lua-desync=fake",
                visual=SimpleNamespace(
                    label="",
                    description="",
                    icon_name="",
                    color="",
                ),
            )
        }
        widget._states = {}
        widget._current_strategy_id = "none"
        widget._item_by_strategy_id = {}
        widget._summary = _TextWidget("1 из 1")

        ProfileStrategyListWidget._rebuild_tree(widget)

        self.assertEqual(widget._summary.calls, [])

    def test_strategy_item_refresh_skips_duplicate_repaint(self) -> None:
        from types import SimpleNamespace

        from profile.ui.profile_setup_page import ProfileStrategyListWidget

        widget = ProfileStrategyListWidget.__new__(ProfileStrategyListWidget)
        widget._states = {"tls_fake": SimpleNamespace(favorite=True, rating="work")}
        widget._list = _ListWidget()
        item = _StrategyItem(
            data={
                ProfileStrategyListWidget._ROLE_STATUS_TEXT: "В избранном • Работает",
                ProfileStrategyListWidget._ROLE_IS_ACTIVE: False,
            },
            selected=False,
        )

        ProfileStrategyListWidget._refresh_strategy_item(widget, item, "tls_fake", is_current=False)

        self.assertEqual(item.data_calls, [])
        self.assertEqual(item.selected_calls, [])
        self.assertEqual(widget._list.current_item_calls, [])
        self.assertEqual(widget._list.update_calls, [])

    def test_list_file_request_skips_duplicate_loading_status(self) -> None:
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        worker = _LoadWorker()
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._editor_tab_built = True
        page._profile_key = "profile-1"
        page._list_file_load_worker = None
        page._list_file_load_request_id = 0
        page._list_file_status_label = _TextWidget("Загрузка файла списка...")
        page._current_filter_kind = lambda: "hostlist"
        page._current_filter_value = lambda: "lists/youtube.txt"
        page._controller = Mock()
        page._controller.create_list_file_load_worker.return_value = worker

        ProfileSetupPageBase._request_list_file_editor_state(page)

        self.assertEqual(page._list_file_status_label.calls, [])
        page._controller.create_list_file_load_worker.assert_called_once_with(
            1,
            "profile-1",
            filter_kind="hostlist",
            filter_value="lists/youtube.txt",
            parent=page,
        )
        self.assertEqual(worker.start_calls, 1)

    def test_list_file_editor_state_skips_duplicate_plain_text(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_title = None
        page._list_file_base_title = None
        page._list_file_base_text = _PlainTextWidget("base.example")
        page._list_file_user_title = None
        page._list_file_text = _PlainTextWidget("user.example", read_only=False)
        page._list_file_save_button = _BoolWidget(enabled=True)
        page._list_file_status_label = _TextWidget("Записей всего: 2 • ваших: 1")
        page._render_list_file_validation = Mock()

        state = SimpleNamespace(
            kind="hostlist",
            display_path="",
            text="user.example",
            base_text="base.example",
            user_text="user.example",
            base_display_path="",
            user_display_path="",
            editable=True,
            error_text="",
            invalid_lines=(),
        )

        ProfileSetupPageBase._apply_list_file_editor_state(page, state)

        self.assertEqual(page._list_file_base_text.plain_text_calls, [])
        self.assertEqual(page._list_file_text.plain_text_calls, [])
        self.assertEqual(page._list_file_text.read_only_calls, [])
        self.assertEqual(page._list_file_status_label.calls, [])

    def test_list_file_validation_skips_duplicate_status_updates(self) -> None:
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_validation_request_id = 7
        page._pending_list_file_validation = None
        page._list_file_kind = "hostlist"
        page._list_file_text = _PlainTextWidget("user.example", read_only=False)
        page._list_file_base_text = _PlainTextWidget("base.example")
        page._list_file_save_button = _BoolWidget(enabled=True)
        page._list_file_status_label = _TextWidget(
            "Записей всего: 2 • ваших: 1 • есть несохранённые изменения"
        )
        page._render_list_file_validation = Mock()

        ProfileSetupPageBase._on_list_file_validation_finished(
            page,
            7,
            "hostlist",
            "user.example",
            (),
        )

        self.assertEqual(page._list_file_save_button.enabled_calls, [])
        self.assertEqual(page._list_file_status_label.calls, [])
        page._render_list_file_validation.assert_called_once_with(())

    def test_list_file_validation_label_skips_duplicate_error_render(self) -> None:
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_text = _PlainTextWidget("bad value")
        page._refresh_list_file_editor_style = Mock()
        page._list_file_error_label = _LabelWidget("Неверные строки:\nСтрока 1: bad value", visible=True)

        ProfileSetupPageBase._render_list_file_validation(page, ((1, "bad value"),))

        self.assertEqual(page._list_file_error_label.text_calls, [])
        self.assertEqual(page._list_file_error_label.visible_calls, [])
        self.assertEqual(page._list_file_error_label.show_calls, 0)
        page._refresh_list_file_editor_style.assert_called_once_with(has_error=True)

    def test_list_file_editor_style_skips_duplicate_stylesheet_updates(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import patch

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        tokens = SimpleNamespace(
            surface_bg="#111111",
            surface_border="#222222",
            surface_bg_hover="#333333",
            surface_border_hover="#444444",
            accent_hex="#55aaff",
            fg="#eeeeee",
            fg_faint="#999999",
        )
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_base_text = _StyleWidget()
        page._list_file_text = _StyleWidget()
        page._list_file_error_label = _StyleWidget()
        page._list_file_status_label = _StyleWidget()

        with patch("profile.ui.profile_setup_page.get_theme_tokens", return_value=tokens):
            ProfileSetupPageBase._refresh_list_file_editor_style(page, has_error=True)
            page._list_file_base_text.style_calls.clear()
            page._list_file_text.style_calls.clear()
            page._list_file_error_label.style_calls.clear()
            page._list_file_status_label.style_calls.clear()

            ProfileSetupPageBase._refresh_list_file_editor_style(page, has_error=True)

        self.assertEqual(page._list_file_base_text.style_calls, [])
        self.assertEqual(page._list_file_text.style_calls, [])
        self.assertEqual(page._list_file_error_label.style_calls, [])
        self.assertEqual(page._list_file_status_label.style_calls, [])

    def test_match_tab_payload_skips_duplicate_plain_text(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase, _match_tab_text

        payload = SimpleNamespace(
            item=SimpleNamespace(
                in_preset=True,
                strategy_id="tls_fake",
                strategy_name="Fake TLS",
            ),
            strategy_entries={
                "tls_fake": SimpleNamespace(args="--lua-desync=fake"),
            },
            match_summary="hostlist: youtube.txt",
            raw_profile_text="--new\n--lua-desync=fake",
        )
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._payload = payload
        page._match_tab_built = True
        page._match_text = _PlainTextWidget(_match_tab_text(payload))
        page._raw_profile_text = _PlainTextWidget(payload.raw_profile_text, read_only=False)
        page._raw_profile_save_button = _BoolWidget(enabled=True)
        page._apply_feedback_buttons = Mock()

        ProfileSetupPageBase._apply_match_tab_payload(page)

        self.assertEqual(page._match_text.plain_text_calls, [])
        self.assertEqual(page._raw_profile_text.plain_text_calls, [])
        self.assertEqual(page._raw_profile_text.read_only_calls, [])
        self.assertEqual(page._raw_profile_save_button.enabled_calls, [])
        page._apply_feedback_buttons.assert_called_once_with(payload)

    def test_raw_profile_save_skips_duplicate_button_disable(self) -> None:
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        worker = _SaveWorker()
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._raw_profile_text = _PlainTextWidget("--new\n")
        page._raw_profile_save_worker = None
        page._raw_profile_save_request_id = 0
        page._raw_profile_save_button = _BoolWidget(enabled=False)
        page._controller = Mock()
        page._controller.create_raw_profile_save_worker.return_value = worker

        ProfileSetupPageBase._on_raw_profile_save_clicked(page)

        self.assertEqual(page._raw_profile_save_button.enabled_calls, [])
        page._controller.create_raw_profile_save_worker.assert_called_once_with(
            1,
            "profile-1",
            "--new\n",
            parent=page,
        )
        self.assertEqual(worker.start_calls, 1)

    def test_enabled_change_skips_duplicate_checkbox_disable(self) -> None:
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        worker = _SaveWorker()
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._enabled_save_worker = None
        page._enabled_save_request_id = 0
        page._enabled_checkbox = _BoolWidget(checked=True, enabled=False)
        page._current_filter_kind = lambda: "hostlist"
        page._current_filter_value = lambda: "lists/youtube.txt"
        page._controller = Mock()
        page._controller.create_enabled_save_worker.return_value = worker

        ProfileSetupPageBase._on_enabled_changed(page, 2)

        self.assertEqual(page._enabled_checkbox.enabled_calls, [])
        page._controller.create_enabled_save_worker.assert_called_once_with(
            1,
            profile_key="profile-1",
            enabled=True,
            filter_kind="hostlist",
            filter_value="lists/youtube.txt",
            parent=page,
        )
        self.assertEqual(worker.start_calls, 1)

    def test_enabled_save_failure_skips_duplicate_checkbox_enable(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._enabled_save_request_id = 4
        page._enabled_checkbox = _BoolWidget(enabled=True)

        ProfileSetupPageBase._on_enabled_save_failed(page, 4, "boom")

        self.assertEqual(page._enabled_checkbox.enabled_calls, [])

    def test_apply_enabled_locally_skips_duplicate_checkbox_state(self) -> None:
        from dataclasses import dataclass, replace

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        @dataclass(frozen=True)
        class _Item:
            enabled: bool

        @dataclass(frozen=True)
        class _Payload:
            item: _Item

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._payload = _Payload(item=_Item(enabled=True))
        page._enabled_checkbox = _BoolWidget(checked=True, enabled=True)
        page._loading = False

        updated_item = ProfileSetupPageBase._apply_enabled_locally(page, True)

        self.assertEqual(updated_item, replace(page._payload.item, enabled=True))
        self.assertEqual(page._enabled_checkbox.checked_calls, [])
        self.assertEqual(page._enabled_checkbox.enabled_calls, [])
        self.assertFalse(page._loading)

    def test_editable_settings_skip_duplicate_text_and_visibility(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import Mock, patch

        from profile.ui.profile_setup_page import ProfileSetupPageBase
        from settings.mode import ZAPRET2_MODE

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page.launch_method = ZAPRET2_MODE
        page._settings_container = _BoolWidget(visible=True)
        page._filter_combo = _BoolWidget(visible=False)
        page._filter_value = _PropertyWidget(visible=False)
        page._filter_value._text = "youtube.txt"
        page._in_range_label = _BoolWidget(visible=True)
        page._in_range_mode = _BoolWidget(visible=True)
        page._in_range_value = _BoolWidget(visible=True)
        page._out_range_label = _BoolWidget(visible=True)
        page._out_range_mode = _BoolWidget(visible=True)
        page._out_range_value = _BoolWidget(visible=True)
        page._rebuild_filter_kind_combo = Mock()
        page._update_all_range_tooltips = Mock()
        payload = SimpleNamespace(
            editable_filter_enabled=True,
            editable_filter_kinds=("hostlist",),
            editable_filter_kind="hostlist",
            editable_filter_value="youtube.txt",
            in_range="x",
            out_range="a",
        )

        with (
            patch("profile.ui.profile_setup_page.set_combo_by_data"),
            patch("profile.ui.profile_setup_page.set_range_controls"),
        ):
            ProfileSetupPageBase._apply_editable_settings(page, payload)

        self.assertEqual(page._settings_container.visible_calls, [])
        self.assertEqual(page._filter_combo.visible_calls, [])
        self.assertEqual(page._filter_value.visible_calls, [])
        self.assertEqual(page._filter_value.text_calls, [])
        for widget in (
            page._in_range_label,
            page._in_range_mode,
            page._in_range_value,
            page._out_range_label,
            page._out_range_mode,
            page._out_range_value,
        ):
            self.assertEqual(widget.visible_calls, [])


if __name__ == "__main__":
    unittest.main()
