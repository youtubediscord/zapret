from __future__ import annotations

import inspect
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from profile.ui.profile_setup_page import ProfileSetupPageBase, ProfileStrategyListDelegate, ProfileStrategyListWidget, _match_tab_text
from ui.presets_menu.delegate import PresetListDelegate


class ProfileSetupPageContractTests(unittest.TestCase):
    def test_strategy_list_click_handlers_match_qlistwidget_signals(self) -> None:
        clicked = inspect.signature(ProfileStrategyListWidget._on_item_clicked)
        activated = inspect.signature(ProfileStrategyListWidget._on_item_activated)

        self.assertEqual(tuple(clicked.parameters), ("self", "item"))
        self.assertEqual(tuple(activated.parameters), ("self", "item"))

    def test_match_tab_text_contains_match_strategy_and_raw_profile(self) -> None:
        payload = SimpleNamespace(
            item=SimpleNamespace(
                strategy_id="tls_fake",
                strategy_name="TLS Fake",
            ),
            match_summary="TCP • TCP 80,443 • hostlist",
            strategy_entries={
                "tls_fake": SimpleNamespace(args="--lua-desync=fake")
            },
            raw_strategy_text="--lua-desync=fake",
            raw_profile_text="--filter-tcp=80,443\n--hostlist=lists/youtube.txt\n--lua-desync=fake",
        )

        text = _match_tab_text(payload)

        self.assertIn("Когда profile применяется", text)
        self.assertIn("TCP • TCP 80,443 • hostlist", text)
        self.assertIn("Текущая готовая стратегия", text)
        self.assertIn("TLS Fake", text)
        self.assertIn("--lua-desync=fake", text)
        self.assertIn("--hostlist=lists/youtube.txt", text)

    def test_strategy_list_rows_store_visual_description(self) -> None:
        set_rows = inspect.getsource(ProfileStrategyListWidget._rebuild_tree)
        paint = inspect.getsource(ProfileStrategyListDelegate.paint)

        self.assertIn("_ROLE_VISUAL_ICON_NAME", set_rows)
        self.assertIn("_ROLE_VISUAL_LABEL_TEXT", set_rows)
        self.assertIn("_ROLE_VISUAL_DESCRIPTION", set_rows)
        self.assertIn("visual.label", set_rows)
        self.assertIn("get_cached_qta_pixmap", paint)

    def test_strategy_and_preset_lists_share_hover_row_painter(self) -> None:
        strategy_paint = inspect.getsource(ProfileStrategyListDelegate.paint)
        preset_paint = inspect.getsource(PresetListDelegate._paint_preset_row)

        self.assertIn("paint_profile_hover_row", strategy_paint)
        self.assertIn("profile_hover_row_rect", strategy_paint)
        self.assertIn("paint_profile_hover_row", preset_paint)
        self.assertIn("profile_hover_row_rect", preset_paint)

    def test_clicking_active_strategy_applies_without_opening_detail_page(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._payload = SimpleNamespace(item=SimpleNamespace(strategy_id="tls_fake"))
        page._controller = Mock()
        page._controller.apply_strategy.return_value = None
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()
        page._apply_strategy_detail = Mock(side_effect=AssertionError("detail page must not open"))

        ProfileSetupPageBase._on_strategy_list_activated(page, "tls_fake")

        page._controller.apply_strategy.assert_called_once_with(
            profile_key="profile-1",
            strategy_id="tls_fake",
        )


if __name__ == "__main__":
    unittest.main()
