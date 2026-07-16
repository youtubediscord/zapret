from __future__ import annotations

import os
import time
import unittest
from dataclasses import replace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QApplication


def _profile_item(
    name: str,
    *,
    key: str,
    order: int = 0,
    enabled: bool = True,
    group: str = "youtube",
    group_name: str = "YouTube",
):
    from profile.state import ProfileListItem

    return ProfileListItem(
        key=key,
        persistent_key=key,
        profile_index=order,
        display_name=name,
        enabled=enabled,
        in_preset=True,
        strategy_id="pass",
        strategy_name="pass",
        match_lines=("--filter-tcp=443", f"--hostlist=lists/{key}.txt"),
        list_type="hostlist",
        rating="",
        favorite=False,
        group=group,
        group_name=group_name,
        order=order,
        profile_name=name,
    )


def _many_profile_items(count: int = 40):
    return tuple(
        _profile_item(f"Profile {index:02d}", key=f"profile-{index:02d}", order=index)
        for index in range(count)
    )


def _view_state(items):
    from profile.list_view_state import build_profile_list_view_state

    return build_profile_list_view_state(
        tuple(items),
        active_profile_types={"all"},
        search_query="",
        group_expanded={},
    )


class ProfilesListScrollPositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _build_scrolled_widget(self, items):
        from profile.ui.profiles_list import ProfilesList

        widget = ProfilesList()
        self.addCleanup(widget.deleteLater)
        widget.resize(420, 320)
        widget.apply_view_state(_view_state(items))
        widget.show()
        self._app.processEvents()

        resets: list[int] = []
        widget._model.modelAboutToBeReset.connect(lambda: resets.append(1))

        scrollbar = widget._view.verticalScrollBar()
        self.assertGreater(scrollbar.maximum(), 0, "список должен быть прокручиваемым")
        scrollbar.setValue(scrollbar.maximum() // 3)
        self.assertGreater(scrollbar.value(), 0)
        return widget, scrollbar, resets

    def test_item_removal_keeps_scroll_and_avoids_model_reset(self) -> None:
        items = _many_profile_items()
        widget, scrollbar, resets = self._build_scrolled_widget(items)
        saved_value = scrollbar.value()

        widget.apply_view_state(_view_state(item for item in items if item.key != "profile-20"))
        self._app.processEvents()

        self.assertEqual(resets, [], "удаление одной строки не должно делать reset модели")
        self.assertEqual(scrollbar.value(), saved_value)

    def test_removing_last_profile_of_group_keeps_scroll(self) -> None:
        # Папка с единственным profile: удаление уносит две соседние строки
        # (заголовок папки + profile) — непрерывный блок, reset не нужен.
        items = _many_profile_items() + (
            _profile_item("Discord", key="profile-discord", order=0, group="discord", group_name="Discord"),
        )
        widget, scrollbar, resets = self._build_scrolled_widget(items)
        saved_value = scrollbar.value()
        old_row_count = widget._model.rowCount()

        widget.apply_view_state(_view_state(item for item in items if item.key != "profile-discord"))
        self._app.processEvents()

        self.assertEqual(widget._model.rowCount(), old_row_count - 2)
        self.assertEqual(resets, [], "удаление profile вместе с пустой папкой не должно делать reset")
        self.assertEqual(scrollbar.value(), saved_value)

    def test_enable_toggle_keeps_scroll_and_avoids_model_reset(self) -> None:
        items = _many_profile_items()
        widget, scrollbar, resets = self._build_scrolled_widget(items)
        saved_value = scrollbar.value()

        toggled = tuple(
            replace(item, enabled=False) if item.key == "profile-20" else item
            for item in items
        )
        widget.apply_view_state(_view_state(toggled))
        self._app.processEvents()

        self.assertEqual(resets, [], "переключение enabled не должно делать reset модели")
        self.assertEqual(scrollbar.value(), saved_value)

    def test_scroll_position_survives_async_remove_profile_item(self) -> None:
        items = _many_profile_items()
        widget, scrollbar, resets = self._build_scrolled_widget(items)
        saved_value = scrollbar.value()
        old_row_count = widget._model.rowCount()

        self.assertTrue(widget.remove_profile_item("profile-20"))
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and widget._model.rowCount() == old_row_count:
            self._app.processEvents()
            time.sleep(0.01)

        self.assertEqual(widget._model.rowCount(), old_row_count - 1)
        self._app.processEvents()
        self.assertEqual(resets, [])
        self.assertEqual(scrollbar.value(), saved_value)

    def test_duplicate_profile_keeps_scroll_and_avoids_model_reset(self) -> None:
        items = _many_profile_items()
        widget, scrollbar, resets = self._build_scrolled_widget(items)
        saved_value = scrollbar.value()

        duplicate = replace(items[20], key="profile-20-copy", persistent_key="profile-20-copy")
        widget.apply_view_state(_view_state(items + (duplicate,)))
        self._app.processEvents()

        self.assertEqual(resets, [], "дублирование profile не должно делать reset модели")
        self.assertEqual(scrollbar.value(), saved_value)

    def test_scroll_clamps_when_tail_rows_removed(self) -> None:
        items = _many_profile_items()
        widget, scrollbar, resets = self._build_scrolled_widget(items)
        scrollbar.setValue(scrollbar.maximum())

        widget.apply_view_state(_view_state(items[:8]))
        self._app.processEvents()

        self.assertEqual(resets, [], "удаление хвостового блока строк не должно делать reset")
        self.assertLessEqual(scrollbar.value(), scrollbar.maximum())

    def test_wholesale_list_change_resets_model_and_scrolls_to_top(self) -> None:
        items = _many_profile_items()
        widget, scrollbar, resets = self._build_scrolled_widget(items)

        # Полностью другой состав строк (другие ключи вразнобой) — это уже не
        # точечная правка: модель делает reset, список ожидаемо идёт наверх.
        other_items = tuple(
            _profile_item(f"Other {index:02d}", key=f"other-{index:02d}", order=index)
            for index in range(30)
        )
        widget.apply_view_state(_view_state(other_items))
        self._app.processEvents()

        self.assertEqual(resets, [1])
        self.assertEqual(scrollbar.value(), 0)
        # Fallback выставляет текущую строку для скринридера и возвращает
        # autoScroll в исходное состояние.
        self.assertEqual(widget._view.currentIndex().row(), 0)
        self.assertTrue(widget._view.hasAutoScroll())

    def _top_visible_anchor(self, widget) -> tuple[tuple[str, str], int]:
        index = widget._view.indexAt(QPoint(0, 0))
        self.assertTrue(index.isValid(), "верхняя видимая строка должна существовать")
        identity = widget._model.stable_row_identity_at(index.row())
        self.assertIsNotNone(identity)
        return identity, int(widget._view.visualRect(index).top())

    def _wait_for(self, condition, timeout: float = 10.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not condition():
            self._app.processEvents()
            time.sleep(0.01)
        self.assertTrue(condition(), "условие не выполнилось за отведённое время")

    def test_same_list_reset_restores_scroll_anchor(self) -> None:
        # AC3: reset «того же списка» (изменение, не сводимое к точечным
        # сигналам) восстанавливает позицию: верхняя видимая строка та же,
        # пиксельное смещение то же (±2 px на округление делегата).
        items = _many_profile_items()
        widget, scrollbar, resets = self._build_scrolled_widget(items)
        anchor_identity, anchor_offset = self._top_visible_anchor(widget)

        # Удаление строки в начале и добавление двух в конце — два
        # несмежных изменения разной длины: точечные ветки не подходят.
        next_items = tuple(item for item in items if item.key != "profile-01") + (
            _profile_item("Extra 90", key="profile-90", order=90),
            _profile_item("Extra 91", key="profile-91", order=91),
        )
        old_row_count = widget._model.rowCount()
        widget.apply_view_state(_view_state(next_items))
        self._wait_for(lambda: widget._model.rowCount() != old_row_count or resets)
        self._app.processEvents()

        self.assertEqual(resets, [1], "изменение не сводится к точечным сигналам — ожидается reset")
        self.assertGreater(scrollbar.value(), 0, "прокрутка не должна сброситься наверх")
        restored_identity, restored_offset = self._top_visible_anchor(widget)
        self.assertEqual(restored_identity, anchor_identity)
        self.assertLessEqual(abs(restored_offset - anchor_offset), 2)

    def test_build_profiles_with_other_items_scrolls_to_top(self) -> None:
        # AC4: реальная смена списка (build_profiles / другой preset) — якорь
        # прежнего списка не применяется, прокрутка уходит наверх.
        items = _many_profile_items()
        widget, scrollbar, resets = self._build_scrolled_widget(items)

        other_items = tuple(
            _profile_item(f"Other {index:02d}", key=f"other-{index:02d}", order=index)
            for index in range(30)
        )
        widget.build_profiles(other_items)
        self._wait_for(lambda: bool(resets))
        self._app.processEvents()

        self.assertEqual(resets, [1])
        self.assertEqual(scrollbar.value(), 0)

    def test_replace_user_profile_items_keeps_positions_and_scroll(self) -> None:
        # AC5: замена элементов user-профиля тем же количеством не переносит
        # их в конец списка и не сбрасывает прокрутку.
        items = tuple(
            replace(item, user_profile_id="user-20") if item.key == "profile-20" else item
            for item in _many_profile_items()
        )
        widget, scrollbar, resets = self._build_scrolled_widget(items)
        saved_value = scrollbar.value()
        old_row = widget._model._row_index_for_profile_key("profile-20")
        self.assertGreaterEqual(old_row, 0)

        replacement = replace(
            items[20],
            key="profile-20-updated",
            persistent_key="profile-20-updated",
            display_name="Updated user profile",
        )
        self.assertTrue(widget.replace_user_profile_items("user-20", (replacement,)))
        self._wait_for(lambda: widget._model._row_index_for_profile_key("profile-20-updated") >= 0)
        self._app.processEvents()

        self.assertEqual(
            widget._model._row_index_for_profile_key("profile-20-updated"),
            old_row,
            "замена на месте: элемент остаётся на прежней позиции",
        )
        self.assertEqual(resets, [], "та же длина и kind по позициям — reset не нужен")
        self.assertEqual(scrollbar.value(), saved_value)

    def test_identity_edit_through_setup_change_keeps_row_and_scroll(self) -> None:
        # AC11: правка, сменившая persistent_key, доезжает до списка парой
        # old→new через apply_profile_setup_change: строка остаётся на месте,
        # прокрутка сохранена, имя обновлено.
        from profile.ui.preset_setup_page import PresetSetupPageBase

        items = _many_profile_items()
        widget, scrollbar, resets = self._build_scrolled_widget(items)
        saved_value = scrollbar.value()
        old_row = widget._model._row_index_for_profile_key("profile-20")
        self.assertGreaterEqual(old_row, 0)

        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page.__dict__["_profiles_list"] = widget
        page._clear_deferred_profile_payload_apply = Mock()

        renamed = replace(
            items[20],
            key="profile-20-renamed",
            persistent_key="profile-20-renamed",
            display_name="Renamed profile",
            profile_name="Renamed profile",
        )
        PresetSetupPageBase.apply_profile_setup_change(
            page,
            "profile-20-renamed",
            "settings",
            renamed,
            "profile-20",
        )
        self._wait_for(lambda: widget._model._row_index_for_profile_key("profile-20-renamed") >= 0)
        self._app.processEvents()

        new_row = widget._model._row_index_for_profile_key("profile-20-renamed")
        self.assertEqual(new_row, old_row, "строка профиля осталась на той же позиции")
        self.assertEqual(resets, [], "in-place смена идентичности не должна делать reset")
        self.assertEqual(scrollbar.value(), saved_value)
        index = widget._model.index(new_row, 0)
        self.assertEqual(index.data(), "Renamed profile")

    def test_view_state_failure_clears_scroll_to_top_flag(self) -> None:
        # Регрессия P5: флаг «после reset — наверх» взводится в build_profiles
        # и штатно снимается в finally apply_view_state. При падении воркера
        # apply не случится — _on_view_state_failed обязан снять флаг, иначе
        # все последующие reset «того же списка» прыгали бы наверх.
        items = _many_profile_items()
        widget, scrollbar, resets = self._build_scrolled_widget(items)

        widget._scroll_to_top_on_reset = True  # как в build_profiles до apply

        # Устаревший (не текущий) request_id не трогает состояние.
        stale_request_id = widget._view_state_runtime.request_id - 1
        widget._on_view_state_failed(stale_request_id, "stale boom")
        self.assertTrue(widget._scroll_to_top_on_reset)

        widget._on_view_state_failed(widget._view_state_runtime.request_id, "boom")
        self.assertFalse(widget._scroll_to_top_on_reset, "падение воркера обязано снять флаг")

        # Последующий reset «того же списка» восстанавливает якорь,
        # а не уходит наверх.
        anchor_identity, _anchor_offset = self._top_visible_anchor(widget)
        next_items = tuple(item for item in items if item.key != "profile-01") + (
            _profile_item("Extra 90", key="profile-90", order=90),
            _profile_item("Extra 91", key="profile-91", order=91),
        )
        widget.apply_view_state(_view_state(next_items))
        self._app.processEvents()

        self.assertEqual(resets, [1])
        self.assertGreater(scrollbar.value(), 0, "прокрутка не должна сброситься наверх")
        restored_identity, _offset = self._top_visible_anchor(widget)
        self.assertEqual(restored_identity, anchor_identity)

    def test_filter_change_with_same_shape_rows_resets_and_scrolls_to_top(self) -> None:
        # Регрессия P4 (уровень виджета): смена поиска, при которой новый
        # список случайно совпал по «форме» (то же количество строк, kind по
        # позициям), — всё равно «новый список»: reset + прокрутка наверх,
        # без in-place dataChanged с унаследованной прокруткой.
        from profile.list_view_state import build_profile_list_view_state

        items = _many_profile_items()
        # Две группы по 20: запрос "profile 0" и "profile 1" дают списки
        # одинаковой формы (по 10 профилей), но с разными идентичностями.
        widget, scrollbar, resets = self._build_scrolled_widget(items)

        widget.apply_view_state(
            build_profile_list_view_state(
                items,
                active_profile_types={"all"},
                search_query="profile 0",
                group_expanded={},
            )
        )
        self._app.processEvents()
        self.assertEqual(resets, [1])
        scrollbar.setValue(scrollbar.maximum())
        self.assertGreaterEqual(scrollbar.value(), 0)

        widget.apply_view_state(
            build_profile_list_view_state(
                items,
                active_profile_types={"all"},
                search_query="profile 1",
                group_expanded={},
            )
        )
        self._app.processEvents()

        self.assertEqual(resets, [1, 1], "смена фильтра с совпавшей формой — всё равно reset")
        self.assertEqual(scrollbar.value(), 0, "новый список начинается сверху")

    def test_search_filter_change_still_resets_model(self) -> None:
        from profile.list_view_state import build_profile_list_view_state

        items = _many_profile_items()
        widget, scrollbar, resets = self._build_scrolled_widget(items)

        # Смена поискового запроса — «оптовое» изменение: даже если строки
        # случайно сложились в непрерывный блок, ведём себя как новый список.
        widget.apply_view_state(
            build_profile_list_view_state(
                items,
                active_profile_types={"all"},
                search_query="profile 0",
                group_expanded={},
            )
        )
        self._app.processEvents()

        self.assertEqual(resets, [1])
        self.assertEqual(scrollbar.value(), 0)


if __name__ == "__main__":
    unittest.main()
