from __future__ import annotations

import os
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QApplication, QLabel, QWidget
from qfluentwidgets import FluentIcon, LineEdit, PushButton, SettingCardGroup

from blobs.ui.page import BlobsPage
from ui.fluent_widgets import (
    QuickActionsBar,
    SettingsCard,
    _SettingCardGroupAutoHeightFilter,
    enable_setting_card_group_auto_height,
    insert_widget_into_setting_card_group,
)
from ui.presets_menu.toolbar import PresetsToolbarLayout
from ui.widgets.win11_controls import Win11ToggleRow


class QuickActionsBarLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_setting_card_group_height_keeps_quick_action_buttons_visible(self) -> None:
        group = SettingCardGroup("Действия")
        actions = QuickActionsBar()
        actions.add_buttons(
            [
                PushButton("Открыть файл", icon=FluentIcon.LINK),
                PushButton("Сбросить файл", icon=FluentIcon.RETURN),
                PushButton("Очистить всё", icon=FluentIcon.DELETE),
            ]
        )

        insert_widget_into_setting_card_group(group, 1, actions)

        needed_height = group.vBoxLayout.minimumSize().height()
        self.assertGreaterEqual(group.minimumHeight(), needed_height)
        self.assertGreaterEqual(group.maximumHeight(), needed_height)
        self.assertGreaterEqual(actions.sizeHint().height(), actions.actions_layout.minimumSize().height())

    def test_presets_toolbar_places_search_on_the_right_when_width_allows(self) -> None:
        parent = QWidget()
        toolbar = PresetsToolbarLayout(parent, row_count=3, button_spacing=8)
        first = PushButton("Импорт")
        second = PushButton("Папка")
        first.setFixedWidth(80)
        second.setFixedWidth(80)
        search = LineEdit()

        toolbar.set_buttons([first, second])
        toolbar.set_trailing_widget(search, minimum_width=180)
        toolbar.refresh_layout(420)

        row_layout = toolbar._rows[0][1]
        widgets = [row_layout.itemAt(index).widget() for index in range(row_layout.count())]

        self.assertEqual(widgets[:2], [first, second])
        self.assertIn(search, widgets)

    def test_presets_toolbar_moves_search_to_next_row_when_width_is_tight(self) -> None:
        parent = QWidget()
        toolbar = PresetsToolbarLayout(parent, row_count=3, button_spacing=8)
        first = PushButton("Импорт")
        second = PushButton("Папка")
        first.setFixedWidth(80)
        second.setFixedWidth(80)
        search = LineEdit()

        toolbar.set_buttons([first, second])
        toolbar.set_trailing_widget(search, minimum_width=180)
        toolbar.refresh_layout(230)

        first_row_widgets = [
            toolbar._rows[0][1].itemAt(index).widget()
            for index in range(toolbar._rows[0][1].count())
        ]
        second_row_widgets = [
            toolbar._rows[1][1].itemAt(index).widget()
            for index in range(toolbar._rows[1][1].count())
        ]

        self.assertIn(first, first_row_widgets)
        self.assertIn(second, first_row_widgets)
        self.assertIn(search, second_row_widgets)

    def test_presets_toolbar_uses_visible_container_width_for_wrapping(self) -> None:
        parent = QWidget()
        toolbar = PresetsToolbarLayout(parent, row_count=3, button_spacing=8)
        first = PushButton("Импорт")
        second = PushButton("Папка")
        first.setFixedWidth(80)
        second.setFixedWidth(80)
        search = LineEdit()

        toolbar.set_buttons([first, second])
        toolbar.set_trailing_widget(search, minimum_width=180)
        toolbar.container.setFixedWidth(230)
        parent.show()
        self._app.processEvents()

        toolbar.refresh_layout(420)

        first_row_widgets = [
            toolbar._rows[0][1].itemAt(index).widget()
            for index in range(toolbar._rows[0][1].count())
        ]
        second_row_widgets = [
            toolbar._rows[1][1].itemAt(index).widget()
            for index in range(toolbar._rows[1][1].count())
        ]

        self.assertIn(first, first_row_widgets)
        self.assertIn(second, first_row_widgets)
        self.assertNotIn(search, first_row_widgets)
        self.assertIn(search, second_row_widgets)

    def test_presets_toolbar_skips_relayout_when_state_is_unchanged(self) -> None:
        parent = QWidget()
        toolbar = PresetsToolbarLayout(parent, row_count=3, button_spacing=8)
        first = PushButton("Импорт")
        second = PushButton("Папка")
        search = LineEdit()

        toolbar.set_buttons([first, second])
        toolbar.set_trailing_widget(search, minimum_width=180)
        toolbar.refresh_layout(420)

        first_row_layout = toolbar._rows[0][1]
        original_clear_row = toolbar._clear_row
        clear_calls: list[int] = []

        def _count_clear(row_layout):
            clear_calls.append(row_layout.count())
            original_clear_row(row_layout)

        toolbar._clear_row = _count_clear
        toolbar.refresh_layout(420)

        self.assertEqual(clear_calls, [])
        self.assertIs(first_row_layout.itemAt(0).widget(), first)
        self.assertIs(first_row_layout.itemAt(1).widget(), second)

    def test_setting_card_group_height_updates_after_late_card_addition(self) -> None:
        group = SettingCardGroup("Управление")
        actions = QuickActionsBar()
        actions.add_buttons(
            [
                PushButton("Открыть", icon=FluentIcon.FOLDER),
                PushButton("Перестроить", icon=FluentIcon.SYNC),
            ]
        )

        insert_widget_into_setting_card_group(group, 1, actions)

        info_card = SettingsCard()
        info_card.add_widget(QLabel("Загрузка информации..."))
        group.addSettingCard(info_card)

        group.resize(638, 200)
        group.show()
        self._app.processEvents()

        needed_info_bottom = info_card.geometry().y() + info_card.sizeHint().height()
        self.assertGreaterEqual(group.minimumHeight(), needed_info_bottom)
        self.assertGreaterEqual(group.maximumHeight(), needed_info_bottom)
        self.assertLessEqual(group.minimumHeight(), needed_info_bottom + 1)
        self.assertLessEqual(group.maximumHeight(), needed_info_bottom + 1)

    def test_setting_card_group_auto_height_keeps_fluent_setting_card_height(self) -> None:
        group = SettingCardGroup("Настройки программы")
        rows = [
            Win11ToggleRow(
                "fa5s.bolt",
                "Автозапуск DPI после старта программы",
                "После запуска ZapretGUI автоматически запускать текущий DPI-режим",
            ),
            Win11ToggleRow(
                "fa5s.shield-alt",
                "Отключить Windows Defender",
                "Требуются права администратора",
            ),
        ]
        original_heights = [row.minimumHeight() for row in rows]

        for row in rows:
            group.addSettingCard(row)

        group.resize(710, 300)
        group.show()
        self._app.processEvents()

        enable_setting_card_group_auto_height(group)
        self._app.processEvents()

        for row, original_height in zip(rows, original_heights):
            self.assertGreaterEqual(row.minimumHeight(), original_height)
            self.assertGreaterEqual(row.maximumHeight(), original_height)

    def test_setting_card_group_auto_height_does_not_refresh_on_own_layout_requests(self) -> None:
        events = _SettingCardGroupAutoHeightFilter._EVENTS

        self.assertNotIn(QEvent.Type.LayoutRequest, events)
        self.assertNotIn(QEvent.Type.Resize, events)
        self.assertIn(QEvent.Type.ChildAdded, events)
        self.assertIn(QEvent.Type.ChildRemoved, events)

    def test_blobs_actions_group_keeps_meta_card_visible(self) -> None:
        feature = SimpleNamespace(
            get_blobs_info=lambda: {},
            get_bin_folder=lambda: "",
            save_user_blob=lambda *args, **kwargs: None,
            delete_user_blob=lambda *args, **kwargs: None,
            reload_blobs=lambda: None,
            open_bin_folder=lambda: None,
            open_blobs_json=lambda: None,
        )
        from blobs.workers import BlobActionWorker, BlobsLoadWorker

        feature.create_blobs_load_worker = lambda request_id, reload=False, parent=None: BlobsLoadWorker(
            request_id,
            reload=reload,
            parent=parent,
        )
        feature.create_blob_action_worker = lambda request_id, **kwargs: BlobActionWorker(
            request_id,
            **kwargs,
        )
        page = BlobsPage(blobs_feature=feature, open_control=lambda: None)
        page.resize(710, 500)
        page.show()
        self._app.processEvents()
        self._app.processEvents()

        group = page._actions_group
        meta_card = page._actions_meta_card
        needed_meta_bottom = meta_card.geometry().y() + meta_card.sizeHint().height()
        self.assertGreaterEqual(group.minimumHeight(), needed_meta_bottom)
        self.assertGreaterEqual(group.maximumHeight(), needed_meta_bottom)
        self.assertLessEqual(group.minimumHeight(), needed_meta_bottom + 1)
        self.assertLessEqual(group.maximumHeight(), needed_meta_bottom + 1)


if __name__ == "__main__":
    unittest.main()
