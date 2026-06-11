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
        self._accessible_name = ""
        self.text_calls: list[str] = []
        self.property_calls: list[tuple[str, object]] = []

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:  # noqa: N802
        value = str(text)
        self.text_calls.append(value)
        self._text = value

    def accessibleName(self) -> str:  # noqa: N802
        return self._accessible_name

    def setAccessibleName(self, text: str) -> None:  # noqa: N802
        self._accessible_name = str(text)

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
        self.plain_text_read_calls: list[str] = []
        self.plain_text_calls: list[str] = []
        self.read_only_calls: list[bool] = []
        self.placeholder_calls: list[str] = []

    def blockSignals(self, blocked: bool) -> None:  # noqa: N802
        self.block_calls.append(bool(blocked))

    def toPlainText(self) -> str:  # noqa: N802
        self.plain_text_read_calls.append(self._text)
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


class _TabTextWidget:
    def __init__(self, texts: dict[str, str] | None = None) -> None:
        self._texts = dict(texts or {})
        self.calls: list[tuple[str, str]] = []

    def itemText(self, key: str):  # noqa: N802
        return self._texts.get(str(key), "")

    def setItemText(self, key: str, text: str) -> None:  # noqa: N802
        route_key = str(key)
        value = str(text)
        self.calls.append((route_key, value))
        self._texts[route_key] = value


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


class _Timer:
    def __init__(self) -> None:
        self.start_calls: list[int | None] = []
        self.stop_calls = 0

    def start(self, interval: int | None = None) -> None:
        self.start_calls.append(interval)

    def stop(self) -> None:
        self.stop_calls += 1


class _LoadWorker:
    def __init__(self) -> None:
        self.loaded = _Signal()
        self.failed = _Signal()
        self.finished = _Signal()
        self.start_calls = 0

    def start(self) -> None:
        self.start_calls += 1

    def deleteLater(self) -> None:  # noqa: N802
        pass


class _SaveWorker:
    def __init__(self) -> None:
        self.saved = _Signal()
        self.failed = _Signal()
        self.finished = _Signal()
        self.start_calls = 0

    def start(self) -> None:
        self.start_calls += 1

    def deleteLater(self) -> None:  # noqa: N802
        pass


class _ValidationWorker:
    def __init__(self) -> None:
        self.validated = _Signal()
        self.failed = _Signal()
        self.finished = _Signal()
        self.start_calls = 0

    def start(self) -> None:
        self.start_calls += 1

    def deleteLater(self) -> None:  # noqa: N802
        pass


class ProfileSetupUiGuardTests(unittest.TestCase):
    def test_strategy_tabs_items_read_name_and_selection_for_screen_reader(self) -> None:
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

        from PyQt6.QtWidgets import QApplication
        from qfluentwidgets import SegmentedWidget

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        type(self)._app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(type(self)._app)

        tabs = SegmentedWidget()
        self.addCleanup(tabs.deleteLater)
        tabs.addItem("strategies", "Готовые стратегии", lambda: None)
        tabs.addItem("editor", "Редактор", lambda: None)
        tabs.addItem("match", "Когда применяется", lambda: None)
        tabs.setCurrentItem("strategies")

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._strategy_tabs = tabs
        page._editor_tab_available = True
        page._payload = None

        ProfileSetupPageBase._update_strategy_tabs_accessibility(page, "strategies")

        self.assertEqual(
            tabs.items["strategies"].accessibleName(),
            "Разделы profile: Готовые стратегии, выбрано",
        )
        self.assertEqual(
            tabs.items["editor"].accessibleName(),
            "Разделы profile: Редактор, не выбрано",
        )

        tabs.setCurrentItem("match")
        ProfileSetupPageBase._update_strategy_tabs_accessibility(page, "match")

        self.assertEqual(
            tabs.items["strategies"].accessibleName(),
            "Разделы profile: Готовые стратегии, не выбрано",
        )
        self.assertEqual(
            tabs.items["match"].accessibleName(),
            "Разделы profile: Когда применяется, выбрано",
        )

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

    def test_tab_item_text_update_skips_duplicate_value(self) -> None:
        from profile.ui.profile_setup_page import set_tab_item_text_if_changed

        widget = _TabTextWidget({"editor": "Редактор"})

        self.assertFalse(set_tab_item_text_if_changed(widget, "editor", "Редактор"))
        self.assertEqual(widget.calls, [])

        self.assertTrue(set_tab_item_text_if_changed(widget, "editor", "Hostlist"))
        self.assertEqual(widget.calls, [("editor", "Hostlist")])

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
        page._work_button = _PropertyWidget(
            enabled=True,
            properties={
                "selected": True,
                "screenReaderStateText": "Отметить стратегию как рабочую. Оценка стратегии: выбрана.",
            },
        )
        page._work_button._accessible_name = "Отметить стратегию как рабочую. Оценка стратегии: выбрана."
        page._notwork_button = _PropertyWidget(
            enabled=True,
            properties={
                "selected": False,
                "screenReaderStateText": "Отметить стратегию как нерабочую. Оценка стратегии: не выбрана.",
            },
        )
        page._notwork_button._accessible_name = "Отметить стратегию как нерабочую. Оценка стратегии: не выбрана."
        page._favorite_button = _PropertyWidget(
            enabled=True,
            properties={
                "screenReaderStateText": "Убрать стратегию из избранного. Избранное: включено.",
            },
        )
        page._favorite_button._accessible_name = "Убрать стратегию из избранного. Избранное: включено."
        page._favorite_button._text = "Убрать из избранного"
        page._clear_feedback_button = _PropertyWidget(
            enabled=True,
            properties={
                "screenReaderStateText": "Убрать оценку стратегии. Текущая оценка: работает.",
            },
        )
        page._clear_feedback_button._accessible_name = "Убрать оценку стратегии. Текущая оценка: работает."

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
        self.assertEqual(page._clear_feedback_button.property_calls, [])
        self.assertEqual(page._favorite_button.text_calls, [])
        self.assertEqual(page._favorite_button._text, "Убрать из избранного")

    def test_feedback_buttons_expose_selected_state_to_screen_reader(self) -> None:
        from types import SimpleNamespace

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._work_button = _PropertyWidget(enabled=True, properties={"selected": False})
        page._notwork_button = _PropertyWidget(enabled=True, properties={"selected": False})
        page._favorite_button = _PropertyWidget(enabled=True)
        page._clear_feedback_button = _PropertyWidget(enabled=True)

        payload = SimpleNamespace(
            item=SimpleNamespace(in_preset=True, enabled=True, strategy_id="tls_fake"),
            current_strategy_state=SimpleNamespace(favorite=False, rating="work"),
        )

        ProfileSetupPageBase._apply_feedback_buttons(page, payload)

        self.assertEqual(
            page._work_button.accessibleName(),
            "Отметить стратегию как рабочую. Оценка стратегии: выбрана.",
        )
        self.assertEqual(
            page._work_button.property("screenReaderStateText"),
            "Отметить стратегию как рабочую. Оценка стратегии: выбрана.",
        )
        self.assertEqual(
            page._notwork_button.accessibleName(),
            "Отметить стратегию как нерабочую. Оценка стратегии: не выбрана.",
        )
        self.assertEqual(
            page._notwork_button.property("screenReaderStateText"),
            "Отметить стратегию как нерабочую. Оценка стратегии: не выбрана.",
        )

    def test_favorite_button_exposes_state_to_screen_reader(self) -> None:
        from types import SimpleNamespace

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._work_button = _PropertyWidget(enabled=True)
        page._notwork_button = _PropertyWidget(enabled=True)
        page._favorite_button = _PropertyWidget(enabled=True)
        page._clear_feedback_button = _PropertyWidget(enabled=True)

        payload = SimpleNamespace(
            item=SimpleNamespace(in_preset=True, enabled=True, strategy_id="tls_fake"),
            current_strategy_state=SimpleNamespace(favorite=False, rating=""),
        )

        ProfileSetupPageBase._apply_feedback_buttons(page, payload)

        self.assertEqual(
            page._favorite_button.accessibleName(),
            "Добавить стратегию в избранное. Избранное: не включено.",
        )
        self.assertEqual(
            page._favorite_button.property("screenReaderStateText"),
            "Добавить стратегию в избранное. Избранное: не включено.",
        )

    def test_clear_feedback_button_exposes_current_rating_to_screen_reader(self) -> None:
        from types import SimpleNamespace

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._work_button = _PropertyWidget(enabled=True)
        page._notwork_button = _PropertyWidget(enabled=True)
        page._favorite_button = _PropertyWidget(enabled=True)
        page._clear_feedback_button = _PropertyWidget(enabled=True)

        payload = SimpleNamespace(
            item=SimpleNamespace(in_preset=True, enabled=True, strategy_id="tls_fake"),
            current_strategy_state=SimpleNamespace(favorite=False, rating="work"),
        )

        ProfileSetupPageBase._apply_feedback_buttons(page, payload)

        self.assertEqual(
            page._clear_feedback_button.accessibleName(),
            "Убрать оценку стратегии. Текущая оценка: работает.",
        )
        self.assertEqual(
            page._clear_feedback_button.property("screenReaderStateText"),
            "Убрать оценку стратегии. Текущая оценка: работает.",
        )

    def test_enabled_checkbox_exposes_state_text_to_screen_reader(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._enabled_checkbox = _PropertyWidget(checked=True)

        ProfileSetupPageBase._update_profile_setup_accessibility(page)

        self.assertEqual(page._enabled_checkbox.accessibleName(), "Profile, включено")
        self.assertEqual(
            page._enabled_checkbox.property("screenReaderStateText"),
            "Profile, включено",
        )

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
        from settings.mode import ZAPRET2_MODE

        worker = _LoadWorker()
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "profile-1"
        page._setup_load_request_id = 0
        page._summary = _TextWidget("Загрузка profile...")
        page._enabled_checkbox = _BoolWidget(enabled=False)
        page._create_profile_setup_load_worker_fn = Mock(return_value=worker)

        ProfileSetupPageBase._request_profile_setup_payload(page)

        self.assertEqual(page._summary.calls, [])
        self.assertEqual(page._enabled_checkbox.enabled_calls, [])
        page._create_profile_setup_load_worker_fn.assert_called_once_with(
            1,
            ZAPRET2_MODE,
            profile_key="profile-1",
            parent=page,
        )
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

    def test_strategy_list_rows_store_screen_reader_text(self) -> None:
        from types import SimpleNamespace

        from PyQt6.QtCore import Qt

        from profile.strategy_state import ProfileStrategyState
        from profile.ui.profile_setup_page import ProfileStrategyListWidget

        widget = ProfileStrategyListWidget.__new__(ProfileStrategyListWidget)
        widget._search = _TextWidget("")
        widget._list = _ListWidget()
        widget._entries = {
            "tls_fake": SimpleNamespace(
                name="TLS fake",
                args="--lua-desync=fake",
                visual=SimpleNamespace(
                    label="Fake",
                    description="Подмена TLS",
                    icon_name="",
                    color="",
                ),
            )
        }
        widget._states = {"tls_fake": ProfileStrategyState(rating="work", favorite=True)}
        widget._current_strategy_id = "tls_fake"
        widget._item_by_strategy_id = {}
        widget._summary = _TextWidget("")

        ProfileStrategyListWidget._rebuild_tree(widget)

        self.assertEqual(len(widget._list.items), 1)
        accessible_text = widget._list.items[0].data(Qt.ItemDataRole.AccessibleTextRole)
        self.assertEqual(
            accessible_text,
            "TLS fake, выбрана, в избранном, работает, Fake, Подмена TLS. "
            "Нажмите Enter, чтобы выбрать стратегию.",
        )

    def test_strategy_item_refresh_updates_screen_reader_text(self) -> None:
        from types import SimpleNamespace

        from PyQt6.QtCore import Qt

        from profile.ui.profile_setup_page import ProfileStrategyListWidget

        widget = ProfileStrategyListWidget.__new__(ProfileStrategyListWidget)
        widget._states = {"tls_fake": SimpleNamespace(favorite=False, rating="")}
        widget._list = _ListWidget()
        item = _StrategyItem(
            data={
                ProfileStrategyListWidget._ROLE_NAME_TEXT: "TLS fake",
                ProfileStrategyListWidget._ROLE_STATUS_TEXT: "",
                ProfileStrategyListWidget._ROLE_IS_ACTIVE: False,
                ProfileStrategyListWidget._ROLE_VISUAL_LABEL_TEXT: "Fake",
                ProfileStrategyListWidget._ROLE_VISUAL_DESCRIPTION: "Подмена TLS",
                Qt.ItemDataRole.AccessibleTextRole: (
                    "TLS fake, не выбрана, Fake, Подмена TLS. "
                    "Нажмите Enter, чтобы выбрать стратегию."
                ),
            },
            selected=False,
        )

        ProfileStrategyListWidget._refresh_strategy_item(widget, item, "tls_fake", is_current=True)

        self.assertIn(
            (
                Qt.ItemDataRole.AccessibleTextRole,
                "TLS fake, выбрана, Fake, Подмена TLS. Нажмите Enter, чтобы выбрать стратегию.",
            ),
            item.data_calls,
        )

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
        page.create_profile_list_file_load_worker = Mock(return_value=worker)

        ProfileSetupPageBase._request_list_file_editor_state(page)

        self.assertEqual(page._list_file_status_label.calls, [])
        page.create_profile_list_file_load_worker.assert_called_once_with(
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
        page._list_file_base_text_snapshot = "base.example"
        page._list_file_text_snapshot = "user.example"
        page._list_file_save_button = _BoolWidget(enabled=True)
        page._list_file_status_label = _TextWidget("Записей всего: 2 • ваших: 1")
        page._render_list_file_validation = Mock()

        state = SimpleNamespace(
            kind="hostlist",
            display_path="",
            text="user.example",
            base_text="base.example",
            user_text="user.example",
            base_entries_count=1,
            user_entries_count=1,
            base_display_path="",
            user_display_path="",
            editable=True,
            error_text="",
            invalid_lines=(),
        )

        ProfileSetupPageBase._apply_list_file_editor_state(page, state)

        self.assertEqual(page._list_file_base_text.plain_text_calls, [])
        self.assertEqual(page._list_file_base_text.plain_text_read_calls, [])
        self.assertEqual(page._list_file_text.plain_text_calls, [])
        self.assertEqual(page._list_file_text.plain_text_read_calls, [])
        self.assertEqual(page._list_file_text.read_only_calls, [])
        self.assertEqual(page._list_file_status_label.calls, [])

    def test_list_file_editor_state_uses_worker_entry_counts(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import Mock
        import inspect

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_title = None
        page._list_file_base_title = None
        page._list_file_base_text = _PlainTextWidget("")
        page._list_file_user_title = None
        page._list_file_text = _PlainTextWidget("", read_only=False)
        page._list_file_base_text_snapshot = ""
        page._list_file_text_snapshot = ""
        page._list_file_save_button = _BoolWidget(enabled=True)
        page._list_file_status_label = _TextWidget("")
        page._render_list_file_validation = Mock()

        state = SimpleNamespace(
            kind="hostlist",
            display_path="",
            text="visible.example\nignored-for-count.example\n",
            base_text="base.example\nignored-for-count.example\n",
            user_text="user.example\nignored-for-count.example\n",
            base_entries_count=10,
            user_entries_count=3,
            base_display_path="",
            user_display_path="",
            editable=True,
            error_text="",
            invalid_lines=(),
        )

        ProfileSetupPageBase._apply_list_file_editor_state(page, state)

        source = inspect.getsource(ProfileSetupPageBase._apply_list_file_editor_state)
        self.assertNotIn("_list_file_entries_count", source)
        self.assertEqual(page._list_file_base_entries_count, 10)
        self.assertEqual(page._list_file_user_entries_count, 3)
        self.assertEqual(page._list_file_status_label.text(), "Записей всего: 13 • ваших: 3")

    def test_list_file_editor_state_apply_is_deferred_after_worker_signal(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import Mock, patch

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        state = SimpleNamespace(
            kind="hostlist",
            display_path="lists/youtube.txt",
            text="example.com",
            base_text="base.example",
            user_text="user.example",
            editable=True,
            error_text="",
            invalid_lines=(),
        )
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_load_request_id = 9
        page._cleanup_in_progress = False
        page._list_file_dirty = True
        page._apply_list_file_editor_state = Mock()
        callbacks = []

        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_list_file_editor_state_loaded(page, 9, state)

        page._apply_list_file_editor_state.assert_not_called()
        self.assertFalse(page._list_file_dirty)
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page._apply_list_file_editor_state.assert_called_once_with(state)

    def test_pending_list_file_state_apply_is_ignored_after_new_load_is_pending(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        state = SimpleNamespace(
            kind="hostlist",
            display_path="lists/old.txt",
            text="old.example",
            base_text="",
            user_text="old.example",
            editable=True,
            error_text="",
            invalid_lines=(),
        )
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._pending_list_file_state_apply = state
        page._list_file_state_apply_scheduled = True
        page._cleanup_in_progress = False
        page._pending_list_file_load = True
        page._apply_list_file_editor_state = Mock(
            side_effect=AssertionError("pending newer list file load must own the visible editor state")
        )

        ProfileSetupPageBase._run_scheduled_list_file_editor_state_apply(page)

        page._apply_list_file_editor_state.assert_not_called()
        self.assertTrue(page._pending_list_file_load)

    def test_pending_list_file_load_ignores_old_load_error(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_load_request_id = 9
        page._pending_list_file_load = True
        page._list_file_status_label = _TextWidget("Загружаем новый список...")

        ProfileSetupPageBase._on_list_file_editor_state_failed(page, 9, "old error")

        self.assertEqual(page._list_file_status_label.text(), "Загружаем новый список...")
        self.assertEqual(page._list_file_status_label.calls, [])

    def test_pending_profile_setup_payload_apply_is_ignored_after_new_load_is_pending(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        payload = SimpleNamespace(
            item=SimpleNamespace(enabled=True),
            match_summary="TCP 443",
        )
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._pending_profile_setup_payload_apply = payload
        page._profile_setup_payload_apply_scheduled = True
        page._cleanup_in_progress = False
        page._setup_load_dirty = True
        page._apply_payload = Mock(
            side_effect=AssertionError("pending newer profile setup load must own the visible payload")
        )

        ProfileSetupPageBase._run_scheduled_profile_setup_payload_apply(page)

        page._apply_payload.assert_not_called()
        self.assertTrue(page._setup_load_dirty)

    def test_pending_profile_setup_load_ignores_old_load_error(self) -> None:
        from unittest.mock import patch

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._setup_load_request_id = 7
        page._setup_load_dirty = True
        page._profile_key = "profile-1"
        page._summary = _TextWidget("Загружаем новый профиль...")
        page._enabled_checkbox = _BoolWidget(enabled=True)

        with patch("profile.ui.profile_setup_page.log") as log_mock:
            ProfileSetupPageBase._on_profile_setup_payload_failed(page, 7, "old error")

        log_mock.assert_not_called()
        self.assertEqual(page._summary.text(), "Загружаем новый профиль...")
        self.assertEqual(page._summary.calls, [])
        self.assertEqual(page._enabled_checkbox.enabled_calls, [])

    def test_pending_list_file_load_restarts_after_worker_signal(self) -> None:
        from unittest.mock import Mock, patch

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._pending_list_file_load = True
        page._request_list_file_editor_state = Mock()
        callbacks = []

        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_list_file_worker_finished(page, object())

        page._request_list_file_editor_state.assert_not_called()
        self.assertTrue(page._pending_list_file_load)
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page._request_list_file_editor_state.assert_called_once_with()
        self.assertFalse(page._pending_list_file_load)

    def test_stale_list_file_load_worker_finished_does_not_restart_pending_load(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import Mock, patch

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        current_worker = SimpleNamespace()
        old_worker = SimpleNamespace()
        page._list_file_load_runtime_worker = current_worker
        page._pending_list_file_load = True
        page._request_list_file_editor_state = Mock()
        callbacks = []

        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_list_file_worker_finished(page, old_worker)

        page._request_list_file_editor_state.assert_not_called()
        self.assertTrue(page._pending_list_file_load)
        self.assertEqual(callbacks, [])
        self.assertIs(page._list_file_load_runtime_worker, current_worker)

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
        page._list_file_text_snapshot = "user.example"
        page._list_file_user_entries_count = 1
        page._list_file_base_entries_count = 1
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

    def test_list_file_validation_result_uses_cached_text_and_counts(self) -> None:
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_validation_request_id = 7
        page._pending_list_file_validation = None
        page._list_file_kind = "hostlist"
        page._list_file_text = _PlainTextWidget("user.example\nsecond.example", read_only=False)
        page._list_file_base_text = _PlainTextWidget("base.example")
        page._list_file_save_button = _BoolWidget(enabled=False)
        page._list_file_status_label = _TextWidget("")
        page._list_file_text_snapshot = "user.example\nsecond.example"
        page._list_file_user_entries_count = 2
        page._list_file_base_entries_count = 1
        page._render_list_file_validation = Mock()

        ProfileSetupPageBase._on_list_file_validation_finished(
            page,
            7,
            "hostlist",
            "user.example\nsecond.example",
            (),
        )

        self.assertEqual(page._list_file_text.plain_text_read_calls, [])
        self.assertEqual(page._list_file_base_text.plain_text_read_calls, [])
        self.assertEqual(
            page._list_file_status_label.text(),
            "Записей всего: 3 • ваших: 2 • есть несохранённые изменения",
        )

    def test_list_file_status_updates_screen_reader_state(self) -> None:
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_validation_request_id = 7
        page._pending_list_file_validation = None
        page._list_file_kind = "hostlist"
        page._list_file_text = _PlainTextWidget("user.example\nsecond.example", read_only=False)
        page._list_file_save_button = _BoolWidget(enabled=False)
        page._list_file_status_label = _PropertyWidget()
        page._list_file_text_snapshot = "user.example\nsecond.example"
        page._list_file_user_entries_count = 2
        page._list_file_base_entries_count = 1
        page._render_list_file_validation = Mock()

        ProfileSetupPageBase._on_list_file_validation_finished(
            page,
            7,
            "hostlist",
            "user.example\nsecond.example",
            (),
        )

        self.assertEqual(
            page._list_file_status_label.accessibleName(),
            "Статус списка profile: Записей всего: 3 • ваших: 2 • есть несохранённые изменения",
        )
        self.assertEqual(
            page._list_file_status_label.property("screenReaderStateText"),
            "Статус списка profile: Записей всего: 3 • ваших: 2 • есть несохранённые изменения",
        )

    def test_list_file_text_change_defers_large_editor_read_until_timer(self) -> None:
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._list_file_kind = "hostlist"
        page._list_file_text = _PlainTextWidget("user.example\nsecond.example")
        page._list_file_status_label = _TextWidget("")
        page._list_file_validation_timer = _Timer()
        page._request_list_file_validation = Mock(
            side_effect=AssertionError("validation must wait for the timer")
        )

        ProfileSetupPageBase._on_list_file_text_changed(page)

        self.assertEqual(page._list_file_text.plain_text_read_calls, [])
        self.assertEqual(page._list_file_validation_timer.start_calls, [180])
        page._request_list_file_validation.assert_not_called()

    def test_list_file_text_change_disables_save_until_worker_validation_finishes(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._list_file_text = _PlainTextWidget("user.example\nsecond.example")
        page._list_file_status_label = _TextWidget("")
        page._list_file_save_button = _BoolWidget(enabled=True)
        page._list_file_validation_timer = _Timer()

        ProfileSetupPageBase._on_list_file_text_changed(page)

        self.assertEqual(page._list_file_text.plain_text_read_calls, [])
        self.assertEqual(page._list_file_save_button.enabled_calls, [False])

    def test_scheduled_list_file_validation_does_not_count_entries_in_gui(self) -> None:
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._list_file_kind = "hostlist"
        page._list_file_text = _PlainTextWidget("user.example\nsecond.example")
        page._list_file_text_snapshot = ""
        page._list_file_user_entries_count = 0
        page._request_list_file_validation = Mock()

        ProfileSetupPageBase._run_scheduled_list_file_validation(page)

        self.assertEqual(page._list_file_text.plain_text_read_calls, [])
        self.assertEqual(page._list_file_text_snapshot, "")
        self.assertEqual(page._list_file_user_entries_count, 0)
        page._request_list_file_validation.assert_called_once_with({
            "kind": "hostlist",
            "text": None,
        })

    def test_list_file_validation_uses_snapshot_when_editor_is_unchanged(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_text = _PlainTextWidget("user.example\nsecond.example")
        page._list_file_text_snapshot = "user.example\nsecond.example"
        page._list_file_text_dirty = False

        request = ProfileSetupPageBase._resolve_list_file_validation_request(
            page,
            {"kind": "hostlist", "text": None},
        )

        self.assertEqual(request, {
            "kind": "hostlist",
            "text": "user.example\nsecond.example",
        })
        self.assertEqual(page._list_file_text.plain_text_read_calls, [])

    def test_list_file_validation_after_text_change_uses_cached_snapshot(self) -> None:
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        worker = _ValidationWorker()
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._list_file_kind = "hostlist"
        page._list_file_text = _PlainTextWidget("new.example\nsecond.example")
        page._list_file_text_snapshot = "old.example"
        page._list_file_text_dirty = False
        page._list_file_validation_request_id = 0
        page.create_profile_list_file_validation_worker = Mock(return_value=worker)
        page._list_file_inserted_text = Mock(return_value="new.example\nsecond.example")

        ProfileSetupPageBase._on_list_file_text_contents_changed(
            page,
            0,
            len("old.example"),
            len("new.example\nsecond.example"),
        )
        page._list_file_text.plain_text_read_calls.clear()
        ProfileSetupPageBase._start_list_file_validation_worker(page, {
            "kind": "hostlist",
            "text": None,
        })

        self.assertEqual(page._list_file_text.plain_text_read_calls, [])
        page.create_profile_list_file_validation_worker.assert_called_once_with(
            1,
            kind="hostlist",
            text="new.example\nsecond.example",
            parent=page,
        )
        self.assertEqual(worker.start_calls, 1)

    def test_list_file_validation_result_updates_entries_count_from_worker(self) -> None:
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_validation_request_id = 7
        page._pending_list_file_validation = None
        page._list_file_kind = "hostlist"
        page._list_file_text = _PlainTextWidget("user.example\nsecond.example", read_only=False)
        page._list_file_save_button = _BoolWidget(enabled=False)
        page._list_file_status_label = _TextWidget("")
        page._list_file_text_snapshot = "user.example\nsecond.example"
        page._list_file_user_entries_count = 0
        page._list_file_base_entries_count = 1
        page._render_list_file_validation = Mock()

        ProfileSetupPageBase._on_list_file_validation_finished(
            page,
            7,
            "hostlist",
            "user.example\nsecond.example",
            {"invalid_lines": (), "entries_count": 2},
        )

        self.assertEqual(page._list_file_user_entries_count, 2)
        self.assertEqual(
            page._list_file_status_label.text(),
            "Записей всего: 3 • ваших: 2 • есть несохранённые изменения",
        )

    def test_list_file_validation_error_is_ignored_when_new_validation_is_pending(self) -> None:
        from unittest.mock import Mock, patch

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_validation_request_id = 7
        page._pending_list_file_validation = {"kind": "hostlist", "text": "new.example"}
        page._render_list_file_validation = Mock()
        page._list_file_save_button = _BoolWidget(enabled=True)
        page._list_file_status_label = _TextWidget("Проверка списка...")

        with patch("profile.ui.profile_setup_page.log") as log_mock:
            ProfileSetupPageBase._on_list_file_validation_failed(page, 7, "old error")

        log_mock.assert_not_called()
        page._render_list_file_validation.assert_not_called()
        self.assertEqual(page._list_file_save_button.enabled_calls, [])
        self.assertEqual(page._list_file_status_label.calls, [])

    def test_pending_list_file_validation_restarts_after_worker_signal(self) -> None:
        from unittest.mock import Mock, patch

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        pending = {"kind": "hostlist", "text": "next.example"}
        page._pending_list_file_validation = pending
        page._start_list_file_validation_worker = Mock()
        callbacks = []

        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_list_file_validation_worker_finished(page, object())

        page._start_list_file_validation_worker.assert_not_called()
        self.assertEqual(page._pending_list_file_validation, pending)
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page._start_list_file_validation_worker.assert_called_once_with(pending)
        self.assertIsNone(page._pending_list_file_validation)

    def test_stale_list_file_validation_worker_finished_does_not_restart_pending_validation(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import Mock, patch

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        current_worker = SimpleNamespace()
        old_worker = SimpleNamespace()
        pending = {"kind": "hostlist", "text": "next.example"}
        page._list_file_validation_runtime_worker = current_worker
        page._pending_list_file_validation = pending
        page._start_list_file_validation_worker = Mock()
        callbacks = []

        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_list_file_validation_worker_finished(page, old_worker)

        page._start_list_file_validation_worker.assert_not_called()
        self.assertEqual(page._pending_list_file_validation, pending)
        self.assertEqual(callbacks, [])
        self.assertIs(page._list_file_validation_runtime_worker, current_worker)

    def test_list_file_save_uses_cached_text_snapshot(self) -> None:
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        worker = _SaveWorker()
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._list_file_text = _PlainTextWidget("user.example\nsecond.example")
        page._list_file_text_snapshot = "user.example\nsecond.example"
        page._list_file_save_worker = None
        page._list_file_save_request_id = 0
        page._list_file_status_label = _TextWidget("")
        page._list_file_save_button = _BoolWidget(enabled=False)
        page.create_profile_list_file_save_worker = Mock(return_value=worker)

        ProfileSetupPageBase._on_list_file_save_clicked(page)

        self.assertEqual(page._list_file_text.plain_text_read_calls, [])
        page.create_profile_list_file_save_worker.assert_called_once_with(
            1,
            "profile-1",
            "user.example\nsecond.example",
            parent=page,
        )
        self.assertEqual(worker.start_calls, 1)

    def test_pending_list_file_save_restarts_after_worker_signal(self) -> None:
        from unittest.mock import Mock, patch

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        pending = ("profile-1", "latest.example")
        page._pending_list_file_save = pending
        page._start_next_profile_setup_write_operation = Mock(return_value=False)
        page._start_list_file_save_worker = Mock()
        callbacks = []

        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_list_file_save_worker_finished(page, object())

        page._start_list_file_save_worker.assert_not_called()
        self.assertEqual(page._list_file_save_state_obj().pending, pending)
        self.assertTrue(page._list_file_save_state_obj().start_scheduled)
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page._start_list_file_save_worker.assert_called_once_with("profile-1", "latest.example")

    def test_list_file_save_waits_while_scheduled_save_start_is_pending(self) -> None:
        from unittest.mock import Mock, patch

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        first_pending = ("profile-1", "first.example")
        page._pending_list_file_save = first_pending
        page._pending_profile_setup_write_operations = []
        page._start_next_profile_setup_write_operation = Mock(return_value=False)
        page._start_list_file_save_worker = Mock()
        callbacks = []

        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_list_file_save_worker_finished(page, object())
            ProfileSetupPageBase._request_list_file_save(page, "profile-1", "second.example")

        page._start_list_file_save_worker.assert_not_called()
        self.assertEqual(page._list_file_save_state_obj().pending, ("profile-1", "first.example"))
        self.assertEqual(
            page._pending_profile_setup_write_operations,
            [{"kind": "list_file_save", "profile_key": "profile-1", "text": "second.example"}],
        )
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page._start_list_file_save_worker.assert_called_once_with("profile-1", "first.example")
        self.assertEqual(
            page._pending_profile_setup_write_operations,
            [{"kind": "list_file_save", "profile_key": "profile-1", "text": "second.example"}],
        )

    def test_list_file_save_error_ignored_when_new_save_is_pending(self) -> None:
        from unittest.mock import Mock, patch

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_save_request_id = 5
        page._pending_list_file_save = ("profile-1", "latest.example")
        page._list_file_save_button = _BoolWidget(enabled=False)
        page._render_list_file_validation = Mock()
        page.window = Mock(return_value=object())

        with patch("profile.ui.profile_setup_page.InfoBar.error") as error_mock:
            ProfileSetupPageBase._on_list_file_save_failed(page, 5, "old error")

        page._render_list_file_validation.assert_not_called()
        self.assertEqual(page._list_file_save_button.enabled_calls, [])
        error_mock.assert_not_called()

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

    def test_list_file_error_label_exposes_screen_reader_state(self) -> None:
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_text = _PlainTextWidget("bad value")
        page._refresh_list_file_editor_style = Mock()
        page._list_file_error_label = _LabelWidget("", visible=False)

        ProfileSetupPageBase._render_list_file_validation(page, ((1, "bad value"),))

        expected = "Ошибка списка profile: Неверные строки: Строка 1: bad value"

        self.assertEqual(page._list_file_error_label.accessibleName(), expected)
        self.assertEqual(page._list_file_error_label.property("screenReaderStateText"), expected)

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

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        match_text = "prepared match text"
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
            match_tab_text=match_text,
        )
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._payload = payload
        page._match_tab_built = True
        page._match_text = _PlainTextWidget(match_text)
        page._match_text_snapshot = match_text
        page._raw_profile_text = _PlainTextWidget(payload.raw_profile_text, read_only=False)
        page._raw_profile_text_cache = payload.raw_profile_text
        page._raw_profile_save_button = _BoolWidget(enabled=True)
        page._apply_feedback_buttons = Mock()

        ProfileSetupPageBase._apply_match_tab_payload(page)

        self.assertEqual(page._match_text.plain_text_calls, [])
        self.assertEqual(page._match_text.plain_text_read_calls, [])
        self.assertEqual(page._raw_profile_text.plain_text_read_calls, [])
        self.assertEqual(page._raw_profile_text.plain_text_calls, [])
        self.assertEqual(page._raw_profile_text.read_only_calls, [])
        self.assertEqual(page._raw_profile_save_button.enabled_calls, [])
        page._apply_feedback_buttons.assert_called_once_with(payload)

    def test_match_tab_payload_uses_cached_raw_profile_text(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        raw_text = "--new\n--lua-desync=fake"
        payload = SimpleNamespace(
            item=SimpleNamespace(
                in_preset=True,
                strategy_id="tls_fake",
                strategy_name="Fake TLS",
            ),
            strategy_entries={},
            match_summary="hostlist: youtube.txt",
            raw_profile_text=raw_text,
            match_tab_text="prepared match text",
        )
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._payload = payload
        page._match_tab_built = True
        page._match_text = None
        page._raw_profile_text = _PlainTextWidget(raw_text, read_only=False)
        page._raw_profile_text_cache = raw_text
        page._raw_profile_save_button = _BoolWidget(enabled=True)
        page._apply_feedback_buttons = Mock()

        ProfileSetupPageBase._apply_match_tab_payload(page)

        self.assertEqual(page._raw_profile_text.plain_text_read_calls, [])
        self.assertEqual(page._raw_profile_text.plain_text_calls, [])
        page._apply_feedback_buttons.assert_called_once_with(payload)

    def test_match_tab_payload_sets_match_text_without_reading_editor(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        match_text = "prepared match text"
        payload = SimpleNamespace(
            item=SimpleNamespace(in_preset=True, strategy_id="tls_fake", strategy_name="Fake TLS"),
            strategy_entries={"tls_fake": SimpleNamespace(args="--lua-desync=fake")},
            match_summary="hostlist: youtube.txt",
            raw_profile_text="--new\n--lua-desync=fake",
            match_tab_text=match_text,
        )
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._payload = payload
        page._match_tab_built = True
        page._match_text = _PlainTextWidget("old match text")
        page._match_text_snapshot = "old match text"
        page._raw_profile_text = None
        page._raw_profile_save_button = None
        page._apply_feedback_buttons = Mock()

        ProfileSetupPageBase._apply_match_tab_payload(page)

        self.assertEqual(page._match_text.plain_text_read_calls, [])
        self.assertEqual(page._match_text.plain_text_calls, [match_text])
        self.assertEqual(page._match_text_snapshot, match_text)

    def test_match_tab_payload_sets_raw_profile_text_without_reading_editor(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        raw_text = "--new\n--lua-desync=fake"
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._payload = SimpleNamespace(
            item=SimpleNamespace(in_preset=True, strategy_id="tls_fake", strategy_name="Fake TLS"),
            strategy_entries={},
            match_summary="hostlist: youtube.txt",
            raw_profile_text=raw_text,
        )
        page._match_tab_built = True
        page._match_text = None
        page._raw_profile_text = _PlainTextWidget("--old\n", read_only=False)
        page._raw_profile_text_cache = "--old\n"
        page._raw_profile_save_button = _BoolWidget(enabled=True)
        page._apply_feedback_buttons = Mock()

        ProfileSetupPageBase._apply_match_tab_payload(page)

        self.assertEqual(page._raw_profile_text.plain_text_read_calls, [])
        self.assertEqual(page._raw_profile_text.plain_text_calls, [raw_text])
        self.assertEqual(page._raw_profile_text_cache, raw_text)

    def test_raw_profile_save_uses_cached_payload_text_when_unchanged(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase

        raw_text = "--new\n--lua-desync=fake"
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._raw_profile_text = _PlainTextWidget(raw_text)
        page._raw_profile_text_cache = raw_text

        text = ProfileSetupPageBase._resolve_raw_profile_save_text(page, None)

        self.assertEqual(text, raw_text)
        self.assertEqual(page._raw_profile_text.plain_text_read_calls, [])

    def test_raw_profile_save_after_text_change_uses_cache_without_worker_start_read(self) -> None:
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        raw_text = "--new\n--lua-desync=fake"
        worker = _SaveWorker()
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._raw_profile_text = _PlainTextWidget(raw_text)
        page._raw_profile_text_cache = "--old\n"
        page._raw_profile_save_request_id = 0
        page._raw_profile_save_button = None
        page.create_profile_raw_text_save_worker = Mock(return_value=worker)
        page._raw_profile_inserted_text = Mock(return_value=raw_text)

        ProfileSetupPageBase._on_raw_profile_text_contents_changed(page, 0, len("--old\n"), len(raw_text))
        page._raw_profile_text.plain_text_read_calls.clear()
        ProfileSetupPageBase._on_raw_profile_save_clicked(page)

        self.assertEqual(page._raw_profile_text.plain_text_read_calls, [])
        page.create_profile_raw_text_save_worker.assert_called_once_with(
            1,
            "profile-1",
            raw_text,
            parent=page,
        )
        self.assertEqual(worker.start_calls, 1)

    def test_raw_profile_save_skips_duplicate_button_disable(self) -> None:
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        worker = _SaveWorker()
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._raw_profile_text = _PlainTextWidget("--new\n")
        page._raw_profile_text_cache = "--new\n"
        page._raw_profile_save_request_id = 0
        page._raw_profile_save_button = _BoolWidget(enabled=False)
        page.create_profile_raw_text_save_worker = Mock(return_value=worker)

        ProfileSetupPageBase._on_raw_profile_save_clicked(page)

        self.assertEqual(page._raw_profile_save_button.enabled_calls, [])
        page.create_profile_raw_text_save_worker.assert_called_once_with(
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
        page._enabled_save_request_id = 0
        page._enabled_checkbox = _BoolWidget(checked=True, enabled=False)
        page._current_filter_kind = lambda: "hostlist"
        page._current_filter_value = lambda: "lists/youtube.txt"
        page.create_profile_enabled_save_worker = Mock(return_value=worker)

        ProfileSetupPageBase._on_enabled_changed(page, 2)

        self.assertEqual(page._enabled_checkbox.enabled_calls, [])
        page.create_profile_enabled_save_worker.assert_called_once_with(
            1,
            profile_key="profile-1",
            enabled=True,
            filter_kind="hostlist",
            filter_value="lists/youtube.txt",
            parent=page,
        )
        self.assertEqual(worker.start_calls, 1)

    def test_enabled_change_skips_same_payload_state(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import Mock

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._payload = SimpleNamespace(item=SimpleNamespace(enabled=True))
        page._enabled_save_request_id = 0
        page._enabled_checkbox = _BoolWidget(checked=True, enabled=True)
        page._current_filter_kind = lambda: "hostlist"
        page._current_filter_value = lambda: "lists/youtube.txt"
        page.create_profile_enabled_save_worker = Mock(
            side_effect=AssertionError("same enabled state must not start worker")
        )

        ProfileSetupPageBase._on_enabled_changed(page, 2)

        page.create_profile_enabled_save_worker.assert_not_called()
        self.assertEqual(page._enabled_checkbox.enabled_calls, [])

    def test_enabled_save_failure_skips_duplicate_checkbox_enable(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._enabled_save_request_id = 4
        page._enabled_checkbox = _BoolWidget(enabled=True)

        ProfileSetupPageBase._on_enabled_save_failed(page, 4, "boom")

        self.assertEqual(page._enabled_checkbox.enabled_calls, [])

    def test_enabled_save_error_ignored_when_new_toggle_is_pending(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._enabled_save_request_id = 5
        page._pending_enabled_save = False
        page._enabled_checkbox = _BoolWidget(enabled=False)

        ProfileSetupPageBase._on_enabled_save_failed(page, 5, "old error")

        self.assertEqual(page._enabled_checkbox.enabled_calls, [])

    def test_raw_profile_save_error_ignored_when_new_save_is_pending(self) -> None:
        from unittest.mock import Mock, patch

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._raw_profile_save_request_id = 6
        page._pending_raw_profile_save = ("profile-1", "--new\nlatest")
        page._raw_profile_save_button = _BoolWidget(enabled=False)
        page.window = Mock(return_value=object())

        with patch("profile.ui.profile_setup_page.InfoBar.error") as error_mock:
            ProfileSetupPageBase._on_raw_profile_save_failed(page, 6, "old error")

        self.assertEqual(page._raw_profile_save_button.enabled_calls, [])
        error_mock.assert_not_called()

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

    def test_strategy_apply_error_ignored_when_new_strategy_is_pending(self) -> None:
        from unittest.mock import Mock, patch

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._strategy_apply_request_id = 8
        page._pending_strategy_apply = "new-strategy"
        page.reload_current_profile = Mock()

        with patch("profile.ui.profile_setup_page.log") as log_mock:
            ProfileSetupPageBase._on_strategy_apply_failed(page, 8, "old error")

        log_mock.assert_not_called()
        page.reload_current_profile.assert_not_called()

    def test_strategy_feedback_error_ignored_when_new_feedback_is_pending(self) -> None:
        from unittest.mock import Mock, patch

        from profile.ui.profile_setup_page import ProfileSetupPageBase

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._strategy_feedback_save_request_id = 9
        page._pending_strategy_feedback_save = {"rating": "work", "favorite": None}
        page.reload_current_profile = Mock()

        with patch("profile.ui.profile_setup_page.log") as log_mock:
            ProfileSetupPageBase._on_strategy_feedback_save_failed(page, 9, "old error")

        log_mock.assert_not_called()
        page.reload_current_profile.assert_not_called()

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
