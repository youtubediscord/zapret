from __future__ import annotations

import inspect
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from profile.ui.profile_setup_page import (
    CompactDisplayComboBox,
    ProfileSetupPageBase,
    ProfileStrategyListDelegate,
    ProfileStrategyListWidget,
    _profile_has_list_file_editor,
    _match_tab_text,
    _profile_editor_tab_title,
)
from profile.profile_setup_loader import (
    ProfileEnabledSaveWorker,
    ProfileListFileValidationWorker,
    ProfileListFileSaveWorker,
    ProfileRawTextSaveWorker,
    ProfileSettingsSaveWorker,
    ProfileStrategyFeedbackSaveWorker,
    ProfileStrategyApplyWorker,
    ProfileUserProfileDeleteWorker,
    ProfileUserProfileUpdateWorker,
)
from profile.state import ProfileListItem, ProfileSetupPayload
from profile.strategy_state import ProfileStrategyState
from profile.ui.preset_setup_page import PresetSetupPageBase, preset_setup_title_for_payload
from profile.ui.shell import build_profile_shell
from profile.ui.profiles_list import ProfilesList
from ui.presets_menu.delegate import PresetListDelegate


class ProfileSetupPageContractTests(unittest.TestCase):
    def test_preset_setup_title_shows_selected_preset_name(self) -> None:
        payload = SimpleNamespace(
            selected_preset_name="YouTube Russia RTMPS",
            selected_preset_file_name="youtube-russia.txt",
        )

        self.assertEqual(
            preset_setup_title_for_payload(payload),
            "Настройка пресета: YouTube Russia RTMPS",
        )

    def test_preset_setup_title_falls_back_to_file_name(self) -> None:
        payload = SimpleNamespace(
            selected_preset_name="",
            selected_preset_file_name="custom.txt",
        )

        self.assertEqual(
            preset_setup_title_for_payload(payload),
            "Настройка пресета: custom.txt",
        )

    def test_preset_setup_page_shows_normalization_infobar(self) -> None:
        apply_payload = inspect.getsource(PresetSetupPageBase._apply_payload)
        notify = inspect.getsource(PresetSetupPageBase._show_profile_normalization_info)

        self.assertIn("_show_profile_normalization_info(payload)", apply_payload)
        self.assertIn("normalized_split_profiles", notify)
        self.assertIn("normalized_created_profiles", notify)
        self.assertIn("InfoBar.info", notify)

    def test_preset_setup_page_has_add_user_profile_action(self) -> None:
        apply_payload = inspect.getsource(PresetSetupPageBase._apply_payload)
        build_content = inspect.getsource(PresetSetupPageBase._build_content)
        shell_builder = inspect.getsource(build_profile_shell)
        handler = inspect.getsource(PresetSetupPageBase._on_add_user_profile_clicked)

        self.assertNotIn('PrimaryPushButton("Добавить"', apply_payload)
        self.assertNotIn("addWidget(self._add_profile_btn)", apply_payload)
        self.assertIn("on_add_user_profile=self._on_add_user_profile_clicked", build_content)
        self.assertIn("PrimaryToolButton", shell_builder)
        self.assertIn("create_primary_tool_button", shell_builder)
        self.assertIn("FluentIcon.ADD", shell_builder)
        self.assertIn("toolbar_actions_bar.set_buttons", shell_builder)
        self.assertIn("CreateUserProfileDialog", handler)
        self.assertIn("create_user_profile", handler)
        self.assertIn("refresh_from_preset_switch", handler)

    def test_profile_rows_have_context_menu_path(self) -> None:
        list_source = inspect.getsource(ProfilesList)
        page_apply = inspect.getsource(PresetSetupPageBase._apply_payload)
        page_handler = inspect.getsource(PresetSetupPageBase._on_profile_context_requested)

        self.assertIn("profile_context_requested", list_source)
        self.assertIn("profile_context_requested.connect", page_apply)
        self.assertIn("show_profile_context_menu", page_handler)

    def test_profile_list_uses_model_view_delegate_not_item_widgets(self) -> None:
        from profile.ui.profile_list_delegate import ProfileListDelegate
        from profile.ui.profile_list_model import ProfileListModel
        from profile.ui.profile_list_view import ProfileListView

        list_source = inspect.getsource(ProfilesList)
        model_source = inspect.getsource(ProfileListModel)
        delegate_source = inspect.getsource(ProfileListDelegate)
        view_source = inspect.getsource(ProfileListView)

        self.assertIn("ProfileListModel", list_source)
        self.assertIn("ProfileListDelegate", list_source)
        self.assertIn("ProfileListView", list_source)
        self.assertNotIn("ProfileItem", list_source)
        self.assertIn("QAbstractListModel", model_source)
        self.assertIn("QStyledItemDelegate", delegate_source)
        self.assertIn("ListView", view_source)

    def test_profile_list_builds_model_in_one_reset(self) -> None:
        from profile.ui.profile_list_model import ProfileListModel

        list_source = inspect.getsource(ProfilesList.build_profiles)
        model_source = inspect.getsource(ProfileListModel.set_profiles)

        self.assertIn("active_profile_types=", list_source)
        self.assertIn("search_query=", list_source)
        self.assertNotIn("set_active_profile_types(self._active_profile_types)", list_source)
        self.assertNotIn("set_search_query(self._search_query)", list_source)
        self.assertIn("active_profile_types", model_source)
        self.assertIn("search_query", model_source)

    def test_preset_switch_updates_existing_profile_list_without_recreating_page_widgets(self) -> None:
        request_source = inspect.getsource(PresetSetupPageBase._request_profiles_payload)
        apply_source = inspect.getsource(PresetSetupPageBase._apply_payload)

        self.assertNotIn("if force or self._profiles_list is None", request_source)
        self.assertIn("profiles_list.update_profiles", apply_source)
        self.assertIn("return", apply_source.split("profiles_list.update_profiles", 1)[1])

    def test_profile_list_does_not_own_page_background_color(self) -> None:
        list_source = inspect.getsource(ProfilesList._build_ui)

        self.assertNotIn("#272727", list_source)
        self.assertIn("background: transparent", list_source)

    def test_profile_list_respects_global_smooth_scroll_setting(self) -> None:
        list_source = inspect.getsource(ProfilesList)

        self.assertIn("apply_page_smooth_scroll_preference", list_source)
        self.assertIn("def set_smooth_scroll_enabled", list_source)
        self.assertIn("apply_smooth_scroll_mode(self._view, enabled)", list_source)

    def test_profile_list_reserves_space_for_visible_fluent_scrollbar(self) -> None:
        list_source = inspect.getsource(ProfilesList._build_ui)

        self.assertIn("reserve_vertical_space=True", list_source)
        self.assertIn("scroll range", list_source)

    def test_profile_delegate_supports_fluent_list_interaction_state(self) -> None:
        from profile.ui.profile_list_delegate import ProfileListDelegate

        delegate = ProfileListDelegate.__new__(ProfileListDelegate)
        delegate._hover_row = -1
        delegate._pressed_row = -1
        delegate._selected_rows = set()

        ProfileListDelegate.setHoverRow(delegate, 2)
        ProfileListDelegate.setPressedRow(delegate, 4)
        ProfileListDelegate.setSelectedRows(delegate, [SimpleNamespace(row=lambda: 4), SimpleNamespace(row=lambda: 6)])

        self.assertEqual(delegate._hover_row, 2)
        self.assertEqual(delegate._pressed_row, -1)
        self.assertEqual(delegate._selected_rows, {4, 6})

    def test_profile_delegate_uses_one_soft_background_for_hover_press_and_selection(self) -> None:
        from profile.ui.profile_list_delegate import _profile_row_background, _profile_row_is_interactive
        from ui.widgets.profile_row_style import PROFILE_ROW_BG_DARK_HOVER

        tokens = SimpleNamespace(is_light=False, surface_bg_hover="#383838")

        self.assertTrue(_profile_row_is_interactive(1, hovered=False, selected=False, hover_row=1, pressed_row=-1, selected_rows=set()))
        self.assertTrue(_profile_row_is_interactive(1, hovered=False, selected=False, hover_row=-1, pressed_row=1, selected_rows=set()))
        self.assertTrue(_profile_row_is_interactive(1, hovered=False, selected=False, hover_row=-1, pressed_row=-1, selected_rows={1}))
        self.assertEqual(_profile_row_background(tokens, hovered=True, selected=False), PROFILE_ROW_BG_DARK_HOVER)
        self.assertEqual(_profile_row_background(tokens, hovered=False, selected=True), PROFILE_ROW_BG_DARK_HOVER)

    def test_profile_delegate_keeps_active_rows_visually_neutral(self) -> None:
        from profile.ui.profile_list_delegate import ProfileListDelegate

        source = inspect.getsource(ProfileListDelegate._paint_profile_row)

        self.assertIn("_paint_profile_row_background", source)
        self.assertNotIn("paint_profile_hover_row", source)
        self.assertIn('painter.drawText(row_layout.dot_rect', source)

    def test_profile_delegate_uses_soft_badge_colors(self) -> None:
        from profile.ui.profile_list_delegate import _badge_palette, _status_dot_color
        from ui.widgets.profile_row_style import (
            PROFILE_BADGE_HOSTLIST_BG,
            PROFILE_BADGE_HOSTLIST_FG,
            PROFILE_BADGE_IPSET_BG,
            PROFILE_BADGE_IPSET_FG,
            PROFILE_STATUS_DOT_ACTIVE,
        )

        self.assertEqual(_badge_palette("hostlist"), (PROFILE_BADGE_HOSTLIST_BG, PROFILE_BADGE_HOSTLIST_FG))
        self.assertEqual(_badge_palette("ipset"), (PROFILE_BADGE_IPSET_BG, PROFILE_BADGE_IPSET_FG))
        self.assertEqual(_status_dot_color(True), PROFILE_STATUS_DOT_ACTIVE)

        source = inspect.getsource(_badge_palette)
        self.assertNotIn("#00B900", source)

    def test_profile_simple_icons_are_cached_for_fast_repaint(self) -> None:
        from profile.ui import profile_icon

        source = inspect.getsource(profile_icon.profile_icon_pixmap)
        cache_source = inspect.getsource(profile_icon._cached_profile_pixmap)

        self.assertIn("_cached_profile_pixmap", source)
        self.assertIn("_PROFILE_PIXMAP_CACHE", cache_source)
        self.assertIn("QPixmap(cached)", cache_source)

    def test_profile_delegate_dark_rows_use_screenshot_background_colors(self) -> None:
        from profile.ui.profile_list_delegate import _profile_row_background
        from ui.widgets.profile_row_style import PROFILE_ROW_BG_DARK, PROFILE_ROW_BG_DARK_HOVER

        dark_tokens = SimpleNamespace(is_light=False, surface_bg_hover="#383838")
        light_tokens = SimpleNamespace(is_light=True, surface_bg_hover="#eeeeee")

        self.assertEqual(_profile_row_background(dark_tokens, hovered=False, selected=False), PROFILE_ROW_BG_DARK)
        self.assertEqual(_profile_row_background(dark_tokens, hovered=True, selected=False), PROFILE_ROW_BG_DARK_HOVER)
        self.assertEqual(_profile_row_background(light_tokens, hovered=False, selected=False), "#eeeeee")

    def test_profile_delegate_layout_keeps_row_parts_from_overlapping_on_narrow_width(self) -> None:
        from PyQt6.QtCore import QRect

        from profile.ui.profile_list_delegate import _profile_row_layout

        layout = _profile_row_layout(
            QRect(8, 2, 404, 40),
            strategy_text_width=260,
            feedback_text_width=260,
            badge_width=62,
        )

        self.assertGreater(layout.name_rect.width(), 64)
        self.assertFalse(layout.feedback_rect.isValid())
        self.assertTrue(layout.badge_rect.isValid())
        self.assertLess(layout.name_rect.right(), layout.badge_rect.left())
        self.assertLess(layout.badge_rect.right(), layout.dot_rect.left())
        self.assertLess(layout.dot_rect.right(), layout.strategy_rect.left())

        ultra_narrow = _profile_row_layout(
            QRect(8, 2, 240, 40),
            strategy_text_width=260,
            feedback_text_width=260,
            badge_width=62,
        )

        self.assertGreaterEqual(ultra_narrow.name_rect.width(), 0)
        self.assertLess(ultra_narrow.name_rect.right(), ultra_narrow.dot_rect.left())
        self.assertFalse(ultra_narrow.feedback_rect.isValid())

    def test_profile_delegate_places_badge_right_after_profile_text(self) -> None:
        from PyQt6.QtCore import QRect

        from profile.ui.profile_list_delegate import _profile_row_layout

        layout = _profile_row_layout(
            QRect(8, 2, 760, 40),
            strategy_text_width=180,
            feedback_text_width=0,
            badge_width=62,
            left_text_width=220,
        )

        self.assertTrue(layout.badge_rect.isValid())
        self.assertEqual(layout.name_rect.width(), 220)
        self.assertEqual(layout.badge_rect.left(), layout.name_rect.left() + layout.name_rect.width() + 8)
        self.assertLess(layout.badge_rect.left(), layout.dot_rect.left() - 120)

    def test_profile_model_keeps_folder_rows_and_hides_collapsed_profiles(self) -> None:
        from profile.ui.profile_list_model import ProfileListModel

        first = SimpleNamespace(
            key="profile:0",
            persistent_key="p0",
            profile_index=0,
            display_name="Discord",
            enabled=True,
            in_preset=True,
            strategy_id="fake",
            strategy_name="Fake",
            match_lines=("--filter-udp=443-65535", "--hostlist=lists/discord.txt"),
            list_type="hostlist",
            rating="work",
            favorite=True,
            group="voice",
            group_name="Voice",
            order=1,
            order_is_manual=False,
            group_collapsed=True,
        )
        second = SimpleNamespace(
            key="profile:1",
            persistent_key="p1",
            profile_index=1,
            display_name="YouTube",
            enabled=True,
            in_preset=True,
            strategy_id="none",
            strategy_name="Стратегия не выбрана",
            match_lines=("--filter-tcp=443", "--hostlist=lists/youtube.txt"),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="video",
            group_name="Video",
            order=2,
            order_is_manual=False,
            group_collapsed=False,
        )

        model = ProfileListModel()
        model.set_profiles((first, second))

        self.assertEqual(model.rowCount(), 3)
        rows = [
            (
                model.index(row, 0).data(ProfileListModel.KindRole),
                model.index(row, 0).data(ProfileListModel.GroupRole),
                model.index(row, 0).data(ProfileListModel.ProfileKeyRole),
            )
            for row in range(model.rowCount())
        ]
        self.assertEqual(sum(1 for kind, _group, _key in rows if kind == "folder"), 2)
        self.assertIn(("profile", "video", "profile:1"), rows)
        self.assertNotIn(("profile", "voice", "profile:0"), rows)

        model.set_group_expanded("voice", True)

        self.assertEqual(model.rowCount(), 4)
        expanded_rows = [
            (
                model.index(row, 0).data(ProfileListModel.KindRole),
                model.index(row, 0).data(ProfileListModel.GroupRole),
                model.index(row, 0).data(ProfileListModel.ProfileKeyRole),
            )
            for row in range(model.rowCount())
        ]
        self.assertIn(("profile", "voice", "profile:0"), expanded_rows)

    def test_profile_model_search_filters_by_name_ports_lists_and_strategy(self) -> None:
        from profile.ui.profile_list_model import ProfileListModel

        discord = SimpleNamespace(
            key="profile:0",
            persistent_key="p0",
            profile_index=0,
            display_name="Discord Voice",
            enabled=True,
            in_preset=True,
            strategy_id="fake",
            strategy_name="Fake",
            match_lines=("--filter-udp=443-65535", "--hostlist=lists/discord.txt"),
            list_type="hostlist",
            rating="work",
            favorite=True,
            group="voice",
            group_name="Voice",
            order=1,
            order_is_manual=False,
            group_collapsed=False,
        )
        youtube = SimpleNamespace(
            key="profile:1",
            persistent_key="p1",
            profile_index=1,
            display_name="YouTube",
            enabled=True,
            in_preset=True,
            strategy_id="none",
            strategy_name="Стратегия не выбрана",
            match_lines=("--filter-tcp=443", "--hostlist=lists/youtube.txt"),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="video",
            group_name="Video",
            order=2,
            order_is_manual=False,
            group_collapsed=False,
        )

        model = ProfileListModel()
        model.set_profiles((discord, youtube))
        model.set_search_query("youtube 443")

        rows = [
            (
                model.index(row, 0).data(ProfileListModel.KindRole),
                model.index(row, 0).data(ProfileListModel.ProfileKeyRole),
            )
            for row in range(model.rowCount())
        ]

        self.assertIn(("profile", "profile:1"), rows)
        self.assertNotIn(("profile", "profile:0"), rows)

        model.set_search_query("fake")
        rows = [
            (
                model.index(row, 0).data(ProfileListModel.KindRole),
                model.index(row, 0).data(ProfileListModel.ProfileKeyRole),
            )
            for row in range(model.rowCount())
        ]

        self.assertIn(("profile", "profile:0"), rows)
        self.assertNotIn(("profile", "profile:1"), rows)

    def test_profile_model_moves_profile_without_reloading_payload(self) -> None:
        from profile.ui.profile_list_model import ProfileListModel

        moved = SimpleNamespace(
            key="profile:0",
            persistent_key="p0",
            profile_index=0,
            display_name="Discord",
            enabled=True,
            in_preset=True,
            strategy_id="fake",
            strategy_name="Fake",
            match_lines=("--filter-udp=443-65535", "--hostlist=lists/discord.txt"),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="discord",
            group_name="Discord",
            order=0,
            order_is_manual=False,
            group_collapsed=False,
        )
        destination = SimpleNamespace(
            key="profile:1",
            persistent_key="p1",
            profile_index=1,
            display_name="YouTube",
            enabled=True,
            in_preset=True,
            strategy_id="none",
            strategy_name="Стратегия не выбрана",
            match_lines=("--filter-tcp=443", "--hostlist=lists/youtube.txt"),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="youtube",
            group_name="YouTube",
            order=0,
            order_is_manual=False,
            group_collapsed=False,
        )

        model = ProfileListModel()
        model.set_profiles((moved, destination))

        self.assertTrue(model.move_profile("profile:0", "profile_after", "profile:1", "youtube"))

        rows = [
            (
                model.index(row, 0).data(ProfileListModel.KindRole),
                model.index(row, 0).data(ProfileListModel.GroupRole),
                model.index(row, 0).data(ProfileListModel.ProfileKeyRole),
            )
            for row in range(model.rowCount())
        ]

        self.assertNotIn(("profile", "discord", "profile:0"), rows)
        self.assertIn(("profile", "youtube", "profile:0"), rows)
        self.assertLess(rows.index(("profile", "youtube", "profile:1")), rows.index(("profile", "youtube", "profile:0")))

    def test_profile_model_replaces_single_profile_row_without_reset(self) -> None:
        from profile.ui.profile_list_model import ProfileListModel

        youtube = SimpleNamespace(
            key="profile:0",
            persistent_key="p0",
            profile_index=0,
            display_name="YouTube",
            enabled=True,
            in_preset=True,
            strategy_id="tls_fake",
            strategy_name="TLS Fake",
            match_lines=("--filter-tcp=443", "--hostlist=lists/youtube.txt"),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="video",
            group_name="Video",
            order=0,
            order_is_manual=False,
            group_collapsed=False,
        )
        disabled = SimpleNamespace(
            **{
                **youtube.__dict__,
                "enabled": False,
                "strategy_id": "none",
                "strategy_name": "Выключен",
            }
        )

        model = ProfileListModel()
        model.set_profiles((youtube,))
        model.beginResetModel = Mock(side_effect=AssertionError("single-row update must not reset the whole model"))
        model.endResetModel = Mock(side_effect=AssertionError("single-row update must not reset the whole model"))

        self.assertTrue(model.replace_profile("profile:0", disabled))

        profile_rows = [
            row
            for row in range(model.rowCount())
            if model.index(row, 0).data(ProfileListModel.KindRole) == "profile"
        ]
        self.assertEqual(len(profile_rows), 1)
        row = profile_rows[0]
        self.assertFalse(model.index(row, 0).data(ProfileListModel.EnabledRole))
        self.assertEqual(model.index(row, 0).data(ProfileListModel.StrategyNameRole), "Выключен")

    def test_profile_model_removes_single_profile_row_without_reset(self) -> None:
        from profile.ui.profile_list_model import ProfileListModel

        first = SimpleNamespace(
            key="profile:0",
            persistent_key="p0",
            profile_index=0,
            display_name="Discord",
            enabled=True,
            in_preset=True,
            strategy_id="fake",
            strategy_name="Fake",
            match_lines=("--filter-tcp=443", "--hostlist=lists/discord.txt"),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="video",
            group_name="Video",
            order=0,
            order_is_manual=False,
            group_collapsed=False,
        )
        second = SimpleNamespace(
            **{
                **first.__dict__,
                "key": "profile:1",
                "persistent_key": "p1",
                "profile_index": 1,
                "display_name": "YouTube",
                "order": 1,
            }
        )

        model = ProfileListModel()
        model.set_profiles((first, second))
        model.beginResetModel = Mock(side_effect=AssertionError("single-row remove must not reset the whole model"))
        model.endResetModel = Mock(side_effect=AssertionError("single-row remove must not reset the whole model"))

        self.assertTrue(model.remove_profile("profile:0"))

        rows = [
            (
                model.index(row, 0).data(ProfileListModel.KindRole),
                model.index(row, 0).data(ProfileListModel.ProfileKeyRole),
            )
            for row in range(model.rowCount())
        ]
        self.assertNotIn(("profile", "profile:0"), rows)
        self.assertIn(("profile", "profile:1"), rows)

    def test_profile_model_updates_shifted_profile_keys_without_reset(self) -> None:
        from profile.ui.profile_list_model import ProfileListModel

        first = SimpleNamespace(
            key="profile:1",
            persistent_key="p1",
            profile_index=1,
            display_name="Discord",
            enabled=True,
            in_preset=True,
            strategy_id="fake",
            strategy_name="Fake",
            match_lines=("--filter-tcp=443", "--hostlist=lists/discord.txt"),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="video",
            group_name="Video",
            order=0,
            order_is_manual=False,
            group_collapsed=False,
        )
        second = SimpleNamespace(
            **{
                **first.__dict__,
                "key": "profile:2",
                "persistent_key": "p2",
                "profile_index": 2,
                "display_name": "YouTube",
                "order": 1,
            }
        )
        shifted_first = SimpleNamespace(**{**first.__dict__, "key": "profile:0", "profile_index": 0})
        shifted_second = SimpleNamespace(**{**second.__dict__, "key": "profile:1", "profile_index": 1})

        model = ProfileListModel()
        model.set_profiles((first, second))
        model.beginResetModel = Mock(side_effect=AssertionError("key refresh must not reset the whole model"))
        model.endResetModel = Mock(side_effect=AssertionError("key refresh must not reset the whole model"))

        self.assertTrue(model.update_profiles((shifted_first, shifted_second)))

        rows = [
            (
                model.index(row, 0).data(ProfileListModel.KindRole),
                model.index(row, 0).data(ProfileListModel.ProfileKeyRole),
            )
            for row in range(model.rowCount())
        ]
        self.assertIn(("profile", "profile:0"), rows)
        self.assertIn(("profile", "profile:1"), rows)
        self.assertNotIn(("profile", "profile:2"), rows)

    def test_profile_drag_handlers_update_current_list_without_full_refresh(self) -> None:
        before_handler = inspect.getsource(PresetSetupPageBase._on_profile_move_requested)
        after_handler = inspect.getsource(PresetSetupPageBase._on_profile_move_after_requested)

        self.assertIn("_apply_profile_move_locally", before_handler)
        self.assertIn("_apply_profile_move_locally", after_handler)
        self.assertNotIn("refresh_from_preset_switch()", before_handler)
        self.assertNotIn("refresh_from_preset_switch()", after_handler)

    def test_profile_context_actions_sync_current_list_without_rebuilding_model(self) -> None:
        enable_handler = inspect.getsource(PresetSetupPageBase._set_profile_enabled_from_menu)
        duplicate_handler = inspect.getsource(PresetSetupPageBase._duplicate_profile_from_menu)
        delete_handler = inspect.getsource(PresetSetupPageBase._delete_profile_from_menu)
        sync_handler = inspect.getsource(PresetSetupPageBase._sync_profile_list_locally)

        self.assertIn("_refresh_profile_item_locally", enable_handler)
        self.assertIn("_sync_profile_list_locally", enable_handler)
        self.assertIn("_sync_profile_list_locally", duplicate_handler)
        self.assertIn("_sync_profile_list_locally", delete_handler)
        self.assertIn("update_profiles", sync_handler)
        self.assertNotIn("build_profiles", sync_handler)
        self.assertNotIn("_add_profile_item_locally", duplicate_handler)
        self.assertNotIn("_remove_profile_item_locally", delete_handler)

    def test_strategy_list_repaints_viewport_rect_after_current_strategy_changes(self) -> None:
        source = inspect.getsource(ProfileStrategyListWidget.set_current_strategy_id)

        self.assertIn("viewport().update", source)
        self.assertNotIn("_list.update(self._list.visualItemRect", source)

    def test_strategy_change_refreshes_only_changed_profile_row(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._refresh_profile_item_locally = Mock()
        page.refresh_from_preset_switch = Mock()

        PresetSetupPageBase.apply_profile_setup_change(page, "profile-1", "strategy")

        page._refresh_profile_item_locally.assert_called_once_with("profile-1", "profile-1")
        page.refresh_from_preset_switch.assert_not_called()

    def test_profile_setup_shell_has_search_input_for_all_profiles(self) -> None:
        build_content = inspect.getsource(PresetSetupPageBase._build_content)
        apply_payload = inspect.getsource(PresetSetupPageBase._apply_payload)
        shell_builder = inspect.getsource(build_profile_shell)

        self.assertIn("profile_search_input", shell_builder)
        self.assertIn("on_profile_search_text_changed", shell_builder)
        self.assertIn("Поиск profile по имени, портам и т.д.", shell_builder)
        self.assertIn("set_search_query", apply_payload)
        self.assertIn("on_profile_search_text_changed=self._on_profile_search_text_changed", build_content)

    def test_preset_setup_shell_has_separate_preset_order_button(self) -> None:
        init_source = inspect.getsource(PresetSetupPageBase.__init__)
        build_content = inspect.getsource(PresetSetupPageBase._build_content)
        shell_builder = inspect.getsource(build_profile_shell)

        self.assertIn("open_profile_order", init_source)
        self.assertIn("on_open_profile_order=self._open_profile_order", build_content)
        self.assertIn("Порядок в preset", shell_builder)
        self.assertIn("order_btn", shell_builder)

    def test_preset_setup_page_does_not_show_loading_placeholder_text(self) -> None:
        shell_builder = inspect.getsource(build_profile_shell)
        request_profiles = inspect.getsource(PresetSetupPageBase._request_profiles_payload)
        payload_loaded = inspect.getsource(PresetSetupPageBase._on_profile_payload_loaded)
        clear_dynamic_widgets = inspect.getsource(PresetSetupPageBase._clear_dynamic_widgets)

        self.assertNotIn("Загрузка профилей выбранного пресета", shell_builder)
        self.assertNotIn("self._loading_label.show()", request_profiles)
        self.assertNotIn("_hide_loading_skeleton()", payload_loaded)
        self.assertIn("while self._content_host_layout.count() > 0", clear_dynamic_widgets)

    def test_preset_setup_activation_schedules_profile_refresh_after_lifecycle_returns(self) -> None:
        activated_source = inspect.getsource(PresetSetupPageBase.on_page_activated)
        schedule_source = inspect.getsource(PresetSetupPageBase._schedule_profiles_payload_request)

        self.assertIn("_schedule_profiles_payload_request", activated_source)
        self.assertNotIn("_request_profiles_payload()", activated_source)
        self.assertIn("QTimer.singleShot", schedule_source)
        self.assertIn("_request_profiles_payload", schedule_source)

    def test_preset_setup_page_does_not_use_profile_loading_skeleton(self) -> None:
        shell_builder = inspect.getsource(build_profile_shell)
        request_profiles = inspect.getsource(PresetSetupPageBase._request_profiles_payload)
        payload_loaded = inspect.getsource(PresetSetupPageBase._on_profile_payload_loaded)
        payload_failed = inspect.getsource(PresetSetupPageBase._on_profile_payload_failed)

        self.assertNotIn("ProfileLoadingSkeleton", shell_builder)
        self.assertNotIn("loading_skeleton", shell_builder)
        self.assertNotIn("_show_loading_skeleton()", request_profiles)
        self.assertNotIn("_hide_loading_skeleton()", inspect.getsource(PresetSetupPageBase._apply_payload))
        self.assertNotIn("_hide_loading_skeleton()", payload_loaded)
        self.assertNotIn("_hide_loading_skeleton()", payload_failed)

    def test_profile_setup_page_has_update_user_profile_action(self) -> None:
        build = inspect.getsource(ProfileSetupPageBase._build_content)
        apply_payload = inspect.getsource(ProfileSetupPageBase._apply_payload)
        handler = inspect.getsource(ProfileSetupPageBase._on_update_user_profile_clicked)
        delete_handler = inspect.getsource(ProfileSetupPageBase._on_delete_user_profile_clicked)

        self.assertIn("_update_user_profile_button", build)
        self.assertIn("_delete_user_profile_button", build)
        self.assertIn("_user_profile_id_from_payload", apply_payload)
        self.assertIn("CreateUserProfileDialog", handler)
        self.assertIn("_request_user_profile_update", handler)
        self.assertIn("_request_user_profile_delete", delete_handler)
        self.assertNotIn("_controller.update_user_profile", handler)
        self.assertNotIn("_controller.delete_user_profile", delete_handler)

    def test_user_profile_update_starts_worker_without_updating_in_gui_thread(self) -> None:
        class _Signal:
            def __init__(self) -> None:
                self.callbacks = []

            def connect(self, callback) -> None:
                self.callbacks.append(callback)

        class _Worker:
            def __init__(self) -> None:
                self.updated = _Signal()
                self.failed = _Signal()
                self.finished = _Signal()
                self.start = Mock()

            def isRunning(self) -> bool:
                return False

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._user_profile_update_request_id = 0
        page._user_profile_update_worker = None
        page._update_user_profile_button = Mock()
        page._delete_user_profile_button = Mock()
        page._controller = Mock()
        worker = _Worker()
        page._controller.create_user_profile_update_worker.return_value = worker
        page._controller.update_user_profile.side_effect = AssertionError("update must run in worker")

        ProfileSetupPageBase._request_user_profile_update(
            page,
            "user-1",
            name="YouTube",
            protocol="TCP",
            ports="443",
        )

        page._controller.update_user_profile.assert_not_called()
        page._controller.create_user_profile_update_worker.assert_called_once_with(
            1,
            profile_id="user-1",
            name="YouTube",
            protocol="TCP",
            ports="443",
            parent=page,
        )
        page._update_user_profile_button.setEnabled.assert_called_once_with(False)
        page._delete_user_profile_button.setEnabled.assert_called_once_with(False)
        worker.start.assert_called_once()

    def test_user_profile_delete_starts_worker_without_deleting_in_gui_thread(self) -> None:
        class _Signal:
            def __init__(self) -> None:
                self.callbacks = []

            def connect(self, callback) -> None:
                self.callbacks.append(callback)

        class _Worker:
            def __init__(self) -> None:
                self.deleted = _Signal()
                self.failed = _Signal()
                self.finished = _Signal()
                self.start = Mock()

            def isRunning(self) -> bool:
                return False

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._user_profile_delete_request_id = 0
        page._user_profile_delete_worker = None
        page._update_user_profile_button = Mock()
        page._delete_user_profile_button = Mock()
        page._controller = Mock()
        worker = _Worker()
        page._controller.create_user_profile_delete_worker.return_value = worker
        page._controller.delete_user_profile.side_effect = AssertionError("delete must run in worker")

        ProfileSetupPageBase._request_user_profile_delete(page, "user-1")

        page._controller.delete_user_profile.assert_not_called()
        page._controller.create_user_profile_delete_worker.assert_called_once_with(
            1,
            profile_id="user-1",
            parent=page,
        )
        page._update_user_profile_button.setEnabled.assert_called_once_with(False)
        page._delete_user_profile_button.setEnabled.assert_called_once_with(False)
        worker.start.assert_called_once()

    def test_stale_user_profile_update_result_is_ignored(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._user_profile_update_request_id = 1
        page._profile_key = "profile-1"
        page._payload = SimpleNamespace(item=SimpleNamespace(user_profile_id="user-2"))
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()

        ProfileSetupPageBase._on_user_profile_update_finished(page, 1, "user-1", 3)

        page.reload_current_profile.assert_not_called()
        page._on_profile_changed_callback.assert_not_called()

    def test_user_profile_update_worker_emits_changed_count(self) -> None:
        controller = Mock()
        controller.update_user_profile.return_value = 3
        worker = ProfileUserProfileUpdateWorker(
            7,
            controller,
            profile_id="user-1",
            name="YouTube",
            protocol="TCP",
            ports="443",
        )
        updated = []

        worker.updated.connect(
            lambda request_id, profile_id, changed: updated.append((request_id, profile_id, changed))
        )

        worker.run()

        controller.update_user_profile.assert_called_once_with(
            profile_id="user-1",
            name="YouTube",
            protocol="TCP",
            ports="443",
        )
        self.assertEqual(updated, [(7, "user-1", 3)])

    def test_user_profile_delete_worker_emits_changed_count(self) -> None:
        controller = Mock()
        controller.delete_user_profile.return_value = 2
        worker = ProfileUserProfileDeleteWorker(8, controller, profile_id="user-1")
        deleted = []

        worker.deleted.connect(
            lambda request_id, profile_id, changed: deleted.append((request_id, profile_id, changed))
        )

        worker.run()

        controller.delete_user_profile.assert_called_once_with(profile_id="user-1")
        self.assertEqual(deleted, [(8, "user-1", 2)])

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
        self.assertNotIn("--hostlist=lists/youtube.txt", text)

    def test_profile_setup_page_has_raw_profile_editor_for_current_preset(self) -> None:
        build = inspect.getsource(ProfileSetupPageBase._build_content)
        ensure_match = inspect.getsource(ProfileSetupPageBase._ensure_match_tab_built)
        apply_match = inspect.getsource(ProfileSetupPageBase._apply_match_tab_payload)
        handler = inspect.getsource(ProfileSetupPageBase._on_raw_profile_save_clicked)
        saved_handler = inspect.getsource(ProfileSetupPageBase._on_raw_profile_save_finished)

        self.assertNotIn("self._raw_profile_text = PlainTextEdit()", build)
        self.assertIn("_raw_profile_text", ensure_match)
        self.assertIn("Сохранить текст profile", ensure_match)
        self.assertIn("in_preset", apply_match)
        self.assertIn("create_raw_profile_save_worker", handler)
        self.assertNotIn("save_raw_profile_text", handler)
        self.assertIn("Текст profile обновлён только в текущем preset", saved_handler)

    def test_raw_profile_save_starts_worker_without_saving_in_gui_thread(self) -> None:
        class _Signal:
            def __init__(self) -> None:
                self.callbacks = []

            def connect(self, callback) -> None:
                self.callbacks.append(callback)

        class _Worker:
            def __init__(self) -> None:
                self.saved = _Signal()
                self.failed = _Signal()
                self.finished = _Signal()
                self.start = Mock()

            def isRunning(self) -> bool:
                return False

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._raw_profile_text = SimpleNamespace(toPlainText=lambda: "--new\n--lua-desync=fake")
        page._raw_profile_save_request_id = 0
        page._raw_profile_save_worker = None
        page._raw_profile_save_button = Mock()
        page._controller = Mock()
        worker = _Worker()
        page._controller.create_raw_profile_save_worker.return_value = worker
        page._controller.save_raw_profile_text.side_effect = AssertionError("raw save must run in worker")

        ProfileSetupPageBase._on_raw_profile_save_clicked(page)

        page._controller.save_raw_profile_text.assert_not_called()
        page._controller.create_raw_profile_save_worker.assert_called_once_with(
            1,
            "profile-1",
            "--new\n--lua-desync=fake",
            parent=page,
        )
        page._raw_profile_save_button.setEnabled.assert_called_once_with(False)
        worker.start.assert_called_once()

    def test_raw_profile_save_worker_emits_new_profile_key(self) -> None:
        controller = Mock()
        controller.save_raw_profile_text.return_value = "profile-2"
        worker = ProfileRawTextSaveWorker(7, controller, "profile-1", "--new\n")
        saved = []

        worker.saved.connect(lambda request_id, profile_key: saved.append((request_id, profile_key)))

        worker.run()

        controller.save_raw_profile_text.assert_called_once_with(
            profile_key="profile-1",
            raw_text="--new\n",
        )
        self.assertEqual(saved, [(7, "profile-2")])

    def test_enabled_change_starts_worker_without_saving_in_gui_thread(self) -> None:
        class _Signal:
            def __init__(self) -> None:
                self.callbacks = []

            def connect(self, callback) -> None:
                self.callbacks.append(callback)

        class _Worker:
            def __init__(self) -> None:
                self.saved = _Signal()
                self.failed = _Signal()
                self.finished = _Signal()
                self.start = Mock()

            def isRunning(self) -> bool:
                return False

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._enabled_save_request_id = 0
        page._enabled_save_worker = None
        page._enabled_checkbox = Mock()
        page._current_filter_kind = lambda: "hostlist"
        page._current_filter_value = lambda: "lists/youtube.txt"
        page._controller = Mock()
        worker = _Worker()
        page._controller.create_enabled_save_worker.return_value = worker
        page._controller.set_enabled.side_effect = AssertionError("enabled save must run in worker")

        ProfileSetupPageBase._on_enabled_changed(page, 2)

        page._controller.set_enabled.assert_not_called()
        page._controller.create_enabled_save_worker.assert_called_once_with(
            1,
            profile_key="profile-1",
            enabled=True,
            filter_kind="hostlist",
            filter_value="lists/youtube.txt",
            parent=page,
        )
        page._enabled_checkbox.setEnabled.assert_called_once_with(False)
        worker.start.assert_called_once()

    def test_enabled_save_worker_emits_new_profile_key(self) -> None:
        controller = Mock()
        controller.set_enabled.return_value = "profile-2"
        worker = ProfileEnabledSaveWorker(
            8,
            controller,
            profile_key="profile-1",
            enabled=False,
            filter_kind="hostlist",
            filter_value="lists/youtube.txt",
        )
        saved = []

        worker.saved.connect(lambda request_id, profile_key, enabled: saved.append((request_id, profile_key, enabled)))

        worker.run()

        controller.set_enabled.assert_called_once_with(
            profile_key="profile-1",
            enabled=False,
            filter_kind="hostlist",
            filter_value="lists/youtube.txt",
        )
        self.assertEqual(saved, [(8, "profile-2", False)])

    def test_profile_setup_page_has_list_file_editor_as_second_tab(self) -> None:
        build = inspect.getsource(ProfileSetupPageBase._build_content)
        ensure_editor = inspect.getsource(ProfileSetupPageBase._ensure_editor_tab_built)
        apply_payload = inspect.getsource(ProfileSetupPageBase._apply_payload)
        sync_label = inspect.getsource(ProfileSetupPageBase._sync_editor_tab_label)
        switch_tab = inspect.getsource(ProfileSetupPageBase._switch_strategy_tab)
        save_handler = inspect.getsource(ProfileSetupPageBase._on_list_file_save_clicked)
        validation = inspect.getsource(ProfileSetupPageBase._render_list_file_validation)

        self.assertIn('addItem("editor", "Редактор"', build)
        self.assertIn("_sync_editor_tab_label(payload)", apply_payload)
        self.assertIn('setItemText("editor", editor_title)', sync_label)
        self.assertNotIn("self._list_file_text = PlainTextEdit()", build)
        self.assertIn("_ensure_editor_tab_built", switch_tab)
        self.assertIn("_request_list_file_editor_state", switch_tab)
        self.assertIn("_list_file_text", ensure_editor)
        self.assertIn("_list_file_base_text", ensure_editor)
        self.assertIn("Ваши записи", ensure_editor)
        self.assertNotIn("_apply_list_file_editor_state", apply_payload)
        self.assertIn("create_list_file_save_worker", save_handler)
        self.assertNotIn("save_list_file_text", save_handler)
        self.assertIn("Неверные строки", validation)

    def test_list_file_save_starts_worker_without_saving_in_gui_thread(self) -> None:
        class _Signal:
            def __init__(self) -> None:
                self.callbacks = []

            def connect(self, callback) -> None:
                self.callbacks.append(callback)

        class _Worker:
            def __init__(self) -> None:
                self.saved = _Signal()
                self.failed = _Signal()
                self.finished = _Signal()
                self.start = Mock()

            def isRunning(self) -> bool:
                return False

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._list_file_text = SimpleNamespace(toPlainText=lambda: "example.com")
        page._list_file_save_request_id = 0
        page._list_file_save_worker = None
        page._list_file_status_label = Mock()
        page._list_file_save_button = Mock()
        page._controller = Mock()
        worker = _Worker()
        page._controller.create_list_file_save_worker.return_value = worker
        page._controller.save_list_file_text.side_effect = AssertionError("save must run in worker")

        ProfileSetupPageBase._on_list_file_save_clicked(page)

        page._controller.save_list_file_text.assert_not_called()
        page._controller.create_list_file_save_worker.assert_called_once_with(
            1,
            "profile-1",
            "example.com",
            parent=page,
        )
        page._list_file_save_button.setEnabled.assert_called_once_with(False)
        worker.start.assert_called_once()

    def test_list_file_save_worker_emits_saved_state(self) -> None:
        controller = Mock()
        state = object()
        controller.save_list_file_text.return_value = state
        worker = ProfileListFileSaveWorker(3, controller, "profile-1", "example.com")
        saved = []

        worker.saved.connect(lambda request_id, emitted_state: saved.append((request_id, emitted_state)))

        worker.run()

        controller.save_list_file_text.assert_called_once_with(
            profile_key="profile-1",
            text="example.com",
        )
        self.assertEqual(saved, [(3, state)])

    def test_list_file_validation_starts_worker_without_validating_in_gui_thread(self) -> None:
        class _Signal:
            def __init__(self) -> None:
                self.callbacks = []

            def connect(self, callback) -> None:
                self.callbacks.append(callback)

        class _Worker:
            def __init__(self) -> None:
                self.validated = _Signal()
                self.failed = _Signal()
                self.finished = _Signal()
                self.start = Mock()

            def isRunning(self) -> bool:
                return False

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._list_file_kind = "hostlist"
        page._list_file_text = SimpleNamespace(toPlainText=lambda: "bad domain", isReadOnly=lambda: False)
        page._list_file_base_text = SimpleNamespace(toPlainText=lambda: "base.example\n")
        page._list_file_validation_request_id = 0
        page._list_file_validation_worker = None
        page._list_file_status_label = Mock()
        page._list_file_save_button = Mock()
        page._render_list_file_validation = Mock()
        page._controller = Mock()
        worker = _Worker()
        page._controller.create_list_file_validation_worker.return_value = worker
        page._controller.validate_list_file_text.side_effect = AssertionError("validation must run in worker")

        ProfileSetupPageBase._on_list_file_text_changed(page)

        page._controller.validate_list_file_text.assert_not_called()
        page._controller.create_list_file_validation_worker.assert_called_once_with(
            1,
            kind="hostlist",
            text="bad domain",
            parent=page,
        )
        page._render_list_file_validation.assert_not_called()
        page._list_file_status_label.setText.assert_called_once_with("Проверка списка...")
        worker.start.assert_called_once()

    def test_list_file_validation_finished_updates_editor_for_current_text(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_kind = "hostlist"
        page._list_file_validation_request_id = 1
        page._pending_list_file_validation = None
        page._list_file_text = SimpleNamespace(toPlainText=lambda: "bad domain", isReadOnly=lambda: False)
        page._list_file_base_text = SimpleNamespace(toPlainText=lambda: "base.example\n")
        page._list_file_status_label = Mock()
        page._list_file_save_button = Mock()
        page._render_list_file_validation = Mock()

        ProfileSetupPageBase._on_list_file_validation_finished(
            page,
            1,
            "hostlist",
            "bad domain",
            ((1, "bad domain"),),
        )

        page._render_list_file_validation.assert_called_once_with(((1, "bad domain"),))
        page._list_file_save_button.setEnabled.assert_called_once_with(False)
        page._list_file_status_label.setText.assert_called_once_with("Исправьте ошибки перед сохранением.")

    def test_stale_list_file_validation_result_is_ignored(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_kind = "hostlist"
        page._list_file_validation_request_id = 1
        page._pending_list_file_validation = None
        page._list_file_text = SimpleNamespace(toPlainText=lambda: "new.example", isReadOnly=lambda: False)
        page._list_file_base_text = SimpleNamespace(toPlainText=lambda: "")
        page._list_file_status_label = Mock()
        page._list_file_save_button = Mock()
        page._render_list_file_validation = Mock()

        ProfileSetupPageBase._on_list_file_validation_finished(
            page,
            1,
            "hostlist",
            "old invalid",
            ((1, "old invalid"),),
        )

        page._render_list_file_validation.assert_not_called()
        page._list_file_save_button.setEnabled.assert_not_called()
        page._list_file_status_label.setText.assert_not_called()

    def test_list_file_validation_worker_emits_invalid_lines(self) -> None:
        controller = Mock()
        controller.validate_list_file_text.return_value = ((2, "bad domain"),)
        worker = ProfileListFileValidationWorker(4, controller, kind="hostlist", text="ok.example\nbad domain")
        validated = []

        worker.validated.connect(
            lambda request_id, kind, text, invalid_lines: validated.append((
                request_id,
                kind,
                text,
                invalid_lines,
            ))
        )

        worker.run()

        controller.validate_list_file_text.assert_called_once_with(
            kind="hostlist",
            text="ok.example\nbad domain",
        )
        self.assertEqual(validated, [(4, "hostlist", "ok.example\nbad domain", ((2, "bad domain"),))])

    def test_profile_setup_page_renames_editor_tab_for_exclusion_profiles(self) -> None:
        regular_payload = SimpleNamespace(
            item=SimpleNamespace(
                display_name="YouTube",
                match_lines=("--filter-tcp=443", "--hostlist=lists/youtube.txt"),
            )
        )
        exclude_payload = SimpleNamespace(
            item=SimpleNamespace(
                display_name="Все сайты TCP",
                match_lines=("--filter-tcp=80,443-65535", "--ipset-exclude=lists/ipset-ru.txt"),
            )
        )

        self.assertEqual(_profile_editor_tab_title(regular_payload), "Редактор")
        self.assertEqual(_profile_editor_tab_title(exclude_payload), "Исключения")

    def test_profile_setup_page_hides_editor_tab_when_profile_has_no_list_file(self) -> None:
        build = inspect.getsource(ProfileSetupPageBase._build_content)
        apply_payload = inspect.getsource(ProfileSetupPageBase._apply_payload)
        apply_settings = inspect.getsource(ProfileSetupPageBase._apply_editable_settings)
        page_source = inspect.getsource(ProfileSetupPageBase)
        l7_payload = SimpleNamespace(
            item=SimpleNamespace(
                match_lines=("--filter-l7=stun,discord", "--payload=stun,discord_ip_discovery"),
            ),
        )
        hostlist_payload = SimpleNamespace(
            item=SimpleNamespace(
                match_lines=("--filter-tcp=443", "--hostlist=lists/discord.txt"),
            ),
        )

        self.assertIn('addItem("editor", "Редактор"', build)
        self.assertIn("_set_list_file_editor_available(_profile_has_list_file_editor(payload))", apply_payload)
        self.assertIn('removeWidget("editor")', page_source)
        self.assertFalse(_profile_has_list_file_editor(l7_payload))
        self.assertTrue(_profile_has_list_file_editor(hostlist_payload))
        self.assertIn("filter_switchable", apply_settings)
        self.assertIn("setVisible(filter_switchable)", apply_settings)

    def test_strategy_list_rows_store_visual_description(self) -> None:
        set_rows = inspect.getsource(ProfileStrategyListWidget._rebuild_tree)
        paint = inspect.getsource(ProfileStrategyListDelegate.paint)

        self.assertIn("_ROLE_VISUAL_ICON_NAME", set_rows)
        self.assertIn("_ROLE_VISUAL_LABEL_TEXT", set_rows)
        self.assertIn("_ROLE_VISUAL_DESCRIPTION", set_rows)
        self.assertIn("_ROLE_TOOLTIP_TEXT", set_rows)
        self.assertIn("visual.label", set_rows)
        self.assertIn("get_cached_qta_pixmap", paint)
        self.assertNotIn("set" + "ToolTip", set_rows)

    def test_settings_autosave_starts_worker_without_saving_in_gui_thread(self) -> None:
        class _Signal:
            def __init__(self) -> None:
                self.callbacks = []

            def connect(self, callback) -> None:
                self.callbacks.append(callback)

        class _Worker:
            def __init__(self) -> None:
                self.saved = _Signal()
                self.failed = _Signal()
                self.finished = _Signal()
                self.start = Mock()

            def isRunning(self) -> bool:
                return False

        class _Combo:
            def currentIndex(self) -> int:
                return 0

            def itemData(self, _index: int) -> str:
                return "x"

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page.launch_method = "zapret2_mode"
        page._loading = False
        page._profile_key = "profile-1"
        page._payload = SimpleNamespace(editable_filter_enabled=True)
        page._filter_value = SimpleNamespace(text=lambda: "lists/youtube.txt")
        page._current_filter_kind = lambda: "hostlist"
        page._in_range_mode = _Combo()
        page._out_range_mode = _Combo()
        page._in_range_value = SimpleNamespace(text=lambda: "")
        page._out_range_value = SimpleNamespace(text=lambda: "")
        page._settings_save_request_id = 0
        page._settings_save_worker = None
        page._pending_settings_save = None
        page._controller = Mock()
        worker = _Worker()
        page._controller.create_settings_save_worker.return_value = worker
        page._controller.save_winws2_settings.side_effect = AssertionError("settings save must run in worker")

        ProfileSetupPageBase._autosave_editable_settings(page)

        page._controller.save_winws2_settings.assert_not_called()
        page._controller.create_settings_save_worker.assert_called_once_with(
            1,
            profile_key="profile-1",
            filter_kind="hostlist",
            filter_value="lists/youtube.txt",
            in_range="x",
            out_range="x",
            parent=page,
        )
        worker.start.assert_called_once()

    def test_settings_save_worker_emits_new_profile_key(self) -> None:
        controller = Mock()
        controller.save_winws2_settings.return_value = "profile-2"
        worker = ProfileSettingsSaveWorker(
            4,
            controller,
            profile_key="profile-1",
            filter_kind="hostlist",
            filter_value="lists/youtube.txt",
            in_range="x",
            out_range="a",
        )
        saved = []

        worker.saved.connect(lambda request_id, profile_key: saved.append((request_id, profile_key)))

        worker.run()

        controller.save_winws2_settings.assert_called_once_with(
            profile_key="profile-1",
            filter_kind="hostlist",
            filter_value="lists/youtube.txt",
            in_range="x",
            out_range="a",
        )
        self.assertEqual(saved, [(4, "profile-2")])

    def test_settings_autosave_while_worker_runs_keeps_last_pending_request(self) -> None:
        class _Worker:
            def isRunning(self) -> bool:
                return True

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._settings_save_worker = _Worker()
        page._pending_settings_save = None
        page._start_settings_save_worker = Mock()

        request = {
            "profile_key": "profile-1",
            "filter_kind": "hostlist",
            "filter_value": "lists/new.txt",
            "in_range": "x",
            "out_range": "a",
        }

        ProfileSetupPageBase._request_settings_save(page, request)

        self.assertEqual(page._pending_settings_save, request)
        page._start_settings_save_worker.assert_not_called()

    def test_strategy_list_uses_fluent_item_tooltip(self) -> None:
        delegate_init = inspect.getsource(ProfileStrategyListDelegate.__init__)
        help_event = inspect.getsource(ProfileStrategyListDelegate.helpEvent)

        self.assertIn("FluentItemToolTipController", delegate_init)
        self.assertIn("_ROLE_TOOLTIP_TEXT", help_event)
        self.assertIn("show_text", help_event)

    def test_strategy_and_preset_lists_share_hover_row_painter(self) -> None:
        strategy_paint = inspect.getsource(ProfileStrategyListDelegate.paint)
        preset_paint = inspect.getsource(PresetListDelegate._paint_preset_row)

        self.assertIn("paint_profile_hover_row", strategy_paint)
        self.assertIn("profile_hover_row_rect", strategy_paint)
        self.assertIn("paint_profile_hover_row", preset_paint)
        self.assertIn("profile_hover_row_rect", preset_paint)

    def test_strategy_list_uses_shared_fluent_scrollbar(self) -> None:
        init = inspect.getsource(ProfileStrategyListWidget.__init__)

        self.assertIn("install_fluent_scrollbars", init)
        self.assertIn("ScrollPerPixel", init)

    def test_profile_detail_header_is_compact_and_tooltipped(self) -> None:
        build = inspect.getsource(ProfileSetupPageBase._build_content)
        tooltips = inspect.getsource(ProfileSetupPageBase._install_profile_tooltips)

        self.assertNotIn("TitleLabel", build)
        self.assertNotIn("Настройки профиля", build)
        self.assertIn("header_layout.addWidget(self._summary, 1)", build)
        self.assertIn("header_layout.addWidget(self._enabled_checkbox", build)
        self.assertIn("Краткое условие profile", tooltips)
        self.assertIn("--in-range", tooltips)
        self.assertIn("--out-range", tooltips)

    def test_range_mode_menu_explains_short_values(self) -> None:
        compact_combo = inspect.getsource(CompactDisplayComboBox)
        fill = inspect.getsource(ProfileSetupPageBase._fill_range_combo)
        descriptions = inspect.getsource(ProfileSetupPageBase._range_mode_description)
        change = inspect.getsource(ProfileSetupPageBase._on_range_mode_changed)

        self.assertIn("_sync_compact_text", compact_combo)
        self.assertIn("compactText=\"n\"", fill)
        self.assertIn("compactText=\"d\"", fill)
        self.assertIn("n — номер пакета", fill)
        self.assertIn("d — пакет с данными", fill)
        self.assertIn("userData=\"n\"", fill)
        self.assertIn("userData=\"d\"", fill)
        self.assertIn("Служебные пакеты без данных не считаются", descriptions)
        self.assertIn("_update_range_tooltips", change)

    def test_profile_settings_row_does_not_force_horizontal_overflow(self) -> None:
        build = inspect.getsource(ProfileSetupPageBase._build_content)

        self.assertIn("self._settings_container.setMinimumWidth(0)", build)
        self.assertIn("self._filter_value.setMinimumWidth(0)", build)
        self.assertIn("settings_layout = QHBoxLayout", build)
        self.assertIn("CompactDisplayComboBox", build)
        self.assertIn("setMinimumWidth(82)", build)

    def test_clicking_active_strategy_starts_background_apply_without_opening_detail_page(self) -> None:
        class _Signal:
            def __init__(self) -> None:
                self.callbacks = []

            def connect(self, callback) -> None:
                self.callbacks.append(callback)

        class _Worker:
            def __init__(self) -> None:
                self.applied = _Signal()
                self.failed = _Signal()
                self.finished = _Signal()
                self.start = Mock()

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._payload = SimpleNamespace(item=SimpleNamespace(strategy_id="tls_fake", in_preset=True, enabled=True))
        page._strategy_apply_worker = None
        page._strategy_apply_request_id = 0
        page._pending_strategy_apply = None
        page._controller = Mock()
        worker = _Worker()
        page._controller.create_strategy_apply_worker.return_value = worker
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()
        page._apply_strategy_detail = Mock(side_effect=AssertionError("detail page must not open"))
        page._apply_strategy_locally = Mock(return_value=True)

        ProfileSetupPageBase._on_strategy_list_activated(page, "tls_fake")

        page._controller.apply_strategy.assert_not_called()
        page._controller.create_strategy_apply_worker.assert_called_once_with(
            1,
            profile_key="profile-1",
            strategy_id="tls_fake",
            parent=page,
        )
        page.reload_current_profile.assert_not_called()
        page._apply_strategy_locally.assert_called_once_with("tls_fake")
        page._on_profile_changed_callback.assert_not_called()
        worker.start.assert_called_once()

    def test_clicking_template_strategy_still_reloads_after_profile_is_added(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "template:profile-1"
        page._payload = SimpleNamespace(item=SimpleNamespace(strategy_id="none", in_preset=False, enabled=True))
        page._strategy_apply_worker = None
        page._strategy_apply_request_id = 0
        page._pending_strategy_apply = None
        page._controller = Mock()
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()
        page._apply_strategy_locally = Mock(return_value=False)

        ProfileSetupPageBase._on_strategy_list_activated(page, "tls_fake")

        ProfileSetupPageBase._on_strategy_apply_finished(page, 1, "template:profile-1", "profile-1", "tls_fake")

        page.reload_current_profile.assert_called_once()
        page._on_profile_changed_callback.assert_called_once_with("profile-1", "strategy")

    def test_clicking_strategy_while_apply_is_running_keeps_last_choice_pending(self) -> None:
        class _Worker:
            def isRunning(self) -> bool:
                return True

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._payload = SimpleNamespace(item=SimpleNamespace(strategy_id="first", in_preset=True, enabled=True))
        page._strategy_apply_worker = _Worker()
        page._strategy_apply_request_id = 1
        page._strategy_apply_worker_strategy_id = "first"
        page._pending_strategy_apply = None
        page._controller = Mock()
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()
        page._apply_strategy_locally = Mock(return_value=True)

        ProfileSetupPageBase._on_strategy_list_activated(page, "second")

        page._apply_strategy_locally.assert_called_once_with("second")
        self.assertEqual(page._pending_strategy_apply, "second")
        page._controller.create_strategy_apply_worker.assert_not_called()
        page._on_profile_changed_callback.assert_not_called()

    def test_stale_strategy_apply_finish_waits_for_pending_last_choice(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "profile-1"
        page._strategy_apply_request_id = 1
        page._pending_strategy_apply = "second"
        page._apply_strategy_locally = Mock(return_value=True)
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()

        ProfileSetupPageBase._on_strategy_apply_finished(page, 1, "profile-1", "profile-1", "first")

        page._apply_strategy_locally.assert_not_called()
        page.reload_current_profile.assert_not_called()
        page._on_profile_changed_callback.assert_not_called()

    def test_strategy_apply_finish_from_previous_profile_is_ignored(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "profile-2"
        page._strategy_apply_request_id = 1
        page._pending_strategy_apply = None
        page._apply_strategy_locally = Mock(return_value=True)
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()

        ProfileSetupPageBase._on_strategy_apply_finished(page, 1, "profile-1", "profile-1", "tls_fake")

        page._apply_strategy_locally.assert_not_called()
        page.reload_current_profile.assert_not_called()
        page._on_profile_changed_callback.assert_not_called()

    def test_strategy_apply_worker_emits_new_profile_key(self) -> None:
        controller = Mock()
        controller.apply_strategy.return_value = "profile-1"
        worker = ProfileStrategyApplyWorker(9, controller, "template:profile-1", "tls_fake")
        applied = []

        worker.applied.connect(
            lambda request_id, requested_profile_key, profile_key, strategy_id: applied.append((
                request_id,
                requested_profile_key,
                profile_key,
                strategy_id,
            ))
        )

        worker.run()

        controller.apply_strategy.assert_called_once_with(
            profile_key="template:profile-1",
            strategy_id="tls_fake",
        )
        self.assertEqual(applied, [(9, "template:profile-1", "profile-1", "tls_fake")])

    def test_strategy_feedback_updates_payload_without_reloading_profile(self) -> None:
        class _Signal:
            def __init__(self) -> None:
                self.callbacks = []

            def connect(self, callback) -> None:
                self.callbacks.append(callback)

        class _Worker:
            def __init__(self) -> None:
                self.saved = _Signal()
                self.failed = _Signal()
                self.finished = _Signal()
                self.start = Mock()

            def isRunning(self) -> bool:
                return False

        item = ProfileListItem(
            key="profile-1",
            persistent_key="persist-1",
            profile_index=0,
            display_name="Profile 1",
            enabled=True,
            in_preset=True,
            strategy_id="tls_fake",
            strategy_name="TLS fake",
            match_lines=(),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="",
            group_name="",
            order=0,
        )
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._payload = ProfileSetupPayload(
            item=item,
            strategy_entries={},
            strategy_states={},
            raw_profile_text="",
            raw_strategy_text="",
            match_summary="",
        )
        page._controller = Mock()
        worker = _Worker()
        page._controller.create_strategy_feedback_save_worker.return_value = worker
        page._controller.set_strategy_feedback.side_effect = AssertionError("feedback save must run in worker")
        page._strategy_feedback_save_request_id = 0
        page._strategy_feedback_save_worker = None
        page._strategy_list = Mock()
        page._apply_feedback_buttons = Mock()
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()

        ProfileSetupPageBase._set_current_strategy_feedback(page, rating="work")

        page._controller.set_strategy_feedback.assert_not_called()
        page._controller.create_strategy_feedback_save_worker.assert_called_once_with(
            1,
            profile_key="profile-1",
            strategy_id="tls_fake",
            rating="work",
            favorite=None,
            parent=page,
        )
        worker.start.assert_called_once()
        page._on_profile_changed_callback.assert_not_called()

        ProfileSetupPageBase._on_strategy_feedback_save_finished(
            page,
            1,
            "profile-1",
            "tls_fake",
            ProfileStrategyState(rating="work", favorite=False),
        )

        page.reload_current_profile.assert_not_called()
        self.assertEqual(page._payload.current_strategy_state.rating, "work")
        self.assertEqual(page._payload.item.rating, "work")
        page._apply_feedback_buttons.assert_called_once_with(page._payload)
        page._on_profile_changed_callback.assert_called_once_with("profile-1", "feedback")

    def test_strategy_feedback_finish_for_previous_strategy_is_ignored(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "profile-1"
        page._strategy_feedback_save_request_id = 1
        page._pending_strategy_feedback_save = None
        page._payload = SimpleNamespace(item=SimpleNamespace(strategy_id="new_strategy"))
        page._apply_strategy_feedback_locally = Mock(return_value=True)
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()

        ProfileSetupPageBase._on_strategy_feedback_save_finished(
            page,
            1,
            "profile-1",
            "old_strategy",
            ProfileStrategyState(rating="work", favorite=False),
        )

        page._apply_strategy_feedback_locally.assert_not_called()
        page.reload_current_profile.assert_not_called()
        page._on_profile_changed_callback.assert_not_called()

    def test_strategy_feedback_worker_emits_state(self) -> None:
        controller = Mock()
        state = ProfileStrategyState(rating="work", favorite=True)
        controller.set_strategy_feedback.return_value = state
        worker = ProfileStrategyFeedbackSaveWorker(
            10,
            controller,
            profile_key="profile-1",
            strategy_id="tls_fake",
            rating="work",
            favorite=True,
        )
        saved = []

        worker.saved.connect(
            lambda request_id, profile_key, strategy_id, emitted_state: saved.append((
                request_id,
                profile_key,
                strategy_id,
                emitted_state,
            ))
        )

        worker.run()

        controller.set_strategy_feedback.assert_called_once_with(
            profile_key="profile-1",
            rating="work",
            favorite=True,
        )
        self.assertEqual(saved, [(10, "profile-1", "tls_fake", state)])

    def test_clicking_strategy_for_skipped_profile_does_not_apply_strategy(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._payload = SimpleNamespace(item=SimpleNamespace(in_preset=True, enabled=False))
        page._controller = Mock()
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()

        ProfileSetupPageBase._on_strategy_list_activated(page, "tls_fake")

        page._controller.apply_strategy.assert_not_called()
        page.reload_current_profile.assert_not_called()
        page._on_profile_changed_callback.assert_not_called()

if __name__ == "__main__":
    unittest.main()
