from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication


def _profile_item(name: str, *, key: str, order: int = 0, in_preset: bool = True):
    from profile.state import ProfileListItem

    return ProfileListItem(
        key=key,
        persistent_key=key,
        profile_index=order,
        display_name=name,
        enabled=True,
        in_preset=in_preset,
        strategy_id="pass",
        strategy_name="pass",
        match_lines=("--filter-tcp=443", f"--hostlist=lists/{key}.txt"),
        list_type="hostlist",
        rating="",
        favorite=False,
        group="youtube",
        group_name="YouTube",
        order=order,
        profile_name=name,
    )


def _items(count: int = 12):
    return tuple(
        _profile_item(f"Profile {index:02d}", key=f"profile-{index:02d}", order=index)
        for index in range(count)
    )


def _view_state(items, *, search_query: str = "", show_only_added: bool = False):
    from profile.list_view_state import build_profile_list_view_state

    return build_profile_list_view_state(
        tuple(items),
        active_profile_types={"all"},
        search_query=search_query,
        show_only_added=show_only_added,
        group_expanded={},
    )


class ProfilesListFilterIntentRaceTests(unittest.TestCase):
    """Регрессия P1 (profile-list-architecture-refactor): канон фильтров —
    общий объект со страницей, и страница пишет в него ДО вызова виджета.
    Поэтому «значение канона совпало» не значит «фильтр применён»: пока
    view-state воркер занят, его in-flight результат снят с устаревших
    фильтров, и повторный запрос обязан встать в pending — иначе устаревший
    результат затирает свежее намерение пользователя (список фильтруется по
    стёртому запросу, испорченный канон уходит обратно на страницу)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _widget_with_shared_canon(self, items):
        from profile.ui.profile_list_filter_state import ProfileListFilterState
        from profile.ui.profiles_list import ProfilesList

        filter_state = ProfileListFilterState()
        widget = ProfilesList(filter_state=filter_state)
        self.addCleanup(widget.deleteLater)
        widget.apply_view_state(_view_state(items))
        self._app.processEvents()
        return widget, filter_state

    def test_stale_search_result_is_discarded_when_canon_matches(self) -> None:
        items = _items()
        widget, filter_state = self._widget_with_shared_canon(items)
        total_rows = widget._model.rowCount()

        # Пользователь ввёл "profile 0": канон уже "profile 0", воркер R1
        # «в полёте» (эмулируем busy-машину без реального QThread).
        filter_state.search_query = "profile 0"
        widget._view_state_state.start_scheduled = True
        stale_state = _view_state(items, search_query="profile 0")

        # Пользователь стёр запрос: страница пишет канон ДО вызова виджета
        # (см. PresetSetupPageBase._on_profile_search_text_changed).
        filter_state.search_query = ""
        widget.set_search_query("")

        self.assertTrue(
            widget._view_state_state.has_pending(),
            "при busy-машине повторный запрос обязан встать в pending, "
            "даже если значение канона совпало",
        )

        # Завершается устаревший R1 — при выставленном pending он отбрасывается.
        widget._on_view_state_loaded(widget._view_state_runtime.request_id, stale_state)

        self.assertEqual(widget._model.rowCount(), total_rows, "список не должен отфильтроваться по стёртому запросу")
        self.assertEqual(filter_state.search_query, "", "устаревший результат не должен затирать канон")
        self.assertEqual(str(widget._model.view_state_options().get("search_query") or ""), "")

    def test_stale_show_only_added_result_is_discarded_when_canon_matches(self) -> None:
        items = _items(6) + tuple(
            _profile_item(f"Template {index}", key=f"template-{index}", order=20 + index, in_preset=False)
            for index in range(3)
        )
        widget, filter_state = self._widget_with_shared_canon(items)
        total_rows = widget._model.rowCount()

        filter_state.show_only_added = True
        widget._view_state_state.start_scheduled = True
        stale_state = _view_state(items, show_only_added=True)

        filter_state.show_only_added = False
        widget.set_show_only_added(False)

        self.assertTrue(widget._view_state_state.has_pending())

        widget._on_view_state_loaded(widget._view_state_runtime.request_id, stale_state)

        self.assertEqual(widget._model.rowCount(), total_rows)
        self.assertFalse(filter_state.show_only_added)
        self.assertFalse(bool(widget._model.view_state_options().get("show_only_added")))

    def test_idle_machine_with_matching_canon_still_short_circuits(self) -> None:
        # Контроль анти-шторма: когда воркер не занят и применённый снимок
        # совпадает с каноном, повторный set_* не запускает новый rebuild.
        items = _items()
        widget, filter_state = self._widget_with_shared_canon(items)
        request_id_before = widget._view_state_runtime.request_id

        widget.set_search_query("")
        widget.set_show_only_added(False)

        self.assertEqual(widget._view_state_runtime.request_id, request_id_before)
        self.assertFalse(widget._view_state_state.has_pending())


if __name__ == "__main__":
    unittest.main()
