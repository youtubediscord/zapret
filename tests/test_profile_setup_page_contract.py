from __future__ import annotations

import inspect
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch

from profile.ui.profile_setup_page import (
    CompactDisplayComboBox,
    ProfileSetupPageBase,
    ProfileStrategyListDelegate,
    ProfileStrategyListWidget,
    _profile_has_list_file_editor,
    _profile_editor_tab_title,
    set_segmented_current_item_if_changed,
)
from profile.setup_match_text import build_profile_setup_match_tab_text
from profile.profile_setup_loader import (
    ProfileEnabledSaveWorker,
    ProfileItemRefreshWorker,
    ProfileListFileValidationWorker,
    ProfileListFileSaveWorker,
    ProfileSetupLoadResult,
    ProfilePresetProfileMoveWorker,
    ProfilePresetProfileActionWorker,
    ProfileRawTextSaveWorker,
    ProfileSettingsSaveWorker,
    ProfileStrategyFeedbackSaveWorker,
    ProfileStrategyApplyWorker,
    ProfileUserProfileCreateWorker,
    ProfileUserProfileDeleteWorker,
    ProfileUserProfileUpdateWorker,
)
from profile.strategy_list_filter import ProfileStrategyListFilterWorker, build_profile_strategy_list_plan
from profile.state import ProfileListItem, ProfileSetupPayload, ProfileStrategyBranch
from profile.strategy_catalog import StrategyEntry
from profile.strategy_state import ProfileStrategyState
from profile.ui.preset_setup_page import PresetSetupPageBase, preset_setup_title_for_payload
from profile.ui.profile_payload_controller import ProfilePayloadController
from profile.ui.shell import build_profile_shell
from profile.ui.profiles_list import ProfileListViewStateWorker, ProfilesList
from ui.presets_menu.delegate import PresetListDelegate


class _TextWidget:
    def __init__(self, text: str = "") -> None:
        self._text = str(text)
        self.text_calls: list[str] = []

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:  # noqa: N802
        value = str(text)
        self.text_calls.append(value)
        self._text = value


class _EnabledWidget:
    def __init__(self, enabled: bool = True) -> None:
        self._enabled = bool(enabled)
        self.enabled_calls: list[bool] = []

    def isEnabled(self) -> bool:  # noqa: N802
        return self._enabled

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        value = bool(enabled)
        self.enabled_calls.append(value)
        self._enabled = value


class ProfileSetupPageContractTests(unittest.TestCase):
    def test_profile_setup_page_tracks_detail_workers_by_request_id(self) -> None:
        page_source = inspect.getsource(ProfileSetupPageBase)

        self.assertIn("_accept_current_profile_setup_worker_finished", page_source)
        self.assertIn("_request_id", page_source)
        for attr in (
            "_list_file_load_runtime_worker",
            "_list_file_save_runtime_worker",
            "_list_file_validation_runtime_worker",
            "_settings_save_runtime_worker",
            "_raw_profile_save_runtime_worker",
            "_enabled_save_runtime_worker",
            "_user_profile_update_runtime_worker",
            "_user_profile_delete_runtime_worker",
            "_strategy_apply_runtime_worker",
            "_strategy_feedback_save_runtime_worker",
        ):
            self.assertNotIn(attr, page_source)

    def test_preset_setup_page_tracks_detail_workers_by_request_id(self) -> None:
        page_source = inspect.getsource(PresetSetupPageBase)

        self.assertIn("_accept_current_preset_setup_worker_finished", page_source)
        self.assertIn("_request_id", page_source)
        for attr in (
            "_profile_context_action_runtime_worker",
            "_profile_item_refresh_runtime_worker",
            "_profile_move_runtime_worker",
            "_profile_folder_action_runtime_worker",
            "_user_profile_create_runtime_worker",
            "_user_profile_update_runtime_worker",
            "_user_profile_delete_runtime_worker",
        ):
            self.assertNotIn(attr, page_source)

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

    def test_selected_preset_title_skips_duplicate_text_update(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page.title_label = _TextWidget("Настройка пресета: custom.txt")
        page.title_key = "page.winws2_pages.title"
        page.page_title = "Настройка пресета"
        page._ui_language = "ru"
        payload = SimpleNamespace(
            selected_preset_name="",
            selected_preset_file_name="custom.txt",
        )

        PresetSetupPageBase._apply_selected_preset_title(page, payload)

        self.assertEqual(page.title_label.text_calls, [])

    def test_user_profile_action_enabled_skips_duplicate_state(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._add_profile_btn = _EnabledWidget(True)

        PresetSetupPageBase._set_user_profile_actions_enabled(page, True)

        self.assertEqual(page._add_profile_btn.enabled_calls, [])

    def test_segmented_current_item_skips_duplicate_selection(self) -> None:
        widget = SimpleNamespace(
            currentItem=Mock(return_value="strategies"),
            setCurrentItem=Mock(),
        )

        self.assertFalse(set_segmented_current_item_if_changed(widget, "strategies"))

        widget.setCurrentItem.assert_not_called()

    def test_preset_setup_page_shows_normalization_infobar(self) -> None:
        apply_payload = inspect.getsource(PresetSetupPageBase._apply_payload)
        notify = inspect.getsource(PresetSetupPageBase._show_profile_normalization_info)

        self.assertIn("_show_profile_normalization_info(payload)", apply_payload)
        self.assertIn("normalized_split_profiles", notify)
        self.assertIn("normalized_created_profiles", notify)
        self.assertIn("InfoBar.info", notify)

    def test_preset_setup_page_skips_normalization_infobar_while_hidden(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page.isVisible = Mock(return_value=False)
        page.window = Mock(return_value=None)
        payload = SimpleNamespace(normalized_split_profiles=1, normalized_created_profiles=1)

        with patch("profile.ui.preset_setup_page.InfoBar.info") as info:
            PresetSetupPageBase._show_profile_normalization_info(page, payload)

        info.assert_not_called()

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
        self.assertIn("_request_user_profile_create", handler)
        self.assertNotIn("_profile.create_user_profile", handler)

    def test_preset_setup_user_profile_actions_start_workers_without_direct_profile_calls(self) -> None:
        class _Signal:
            def __init__(self) -> None:
                self.callbacks = []

            def connect(self, callback) -> None:
                self.callbacks.append(callback)

        class _CreateWorker:
            def __init__(self) -> None:
                self.created = _Signal()
                self.failed = _Signal()
                self.finished = _Signal()
                self.start = Mock()
                self.deleteLater = Mock()

            def isRunning(self) -> bool:
                return False

        class _UpdateWorker:
            def __init__(self) -> None:
                self.updated = _Signal()
                self.failed = _Signal()
                self.finished = _Signal()
                self.start = Mock()
                self.deleteLater = Mock()

            def isRunning(self) -> bool:
                return False

        class _DeleteWorker:
            def __init__(self) -> None:
                self.deleted = _Signal()
                self.failed = _Signal()
                self.finished = _Signal()
                self.start = Mock()
                self.deleteLater = Mock()

            def isRunning(self) -> bool:
                return False

        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile = Mock()
        page._profile.create_user_profile.side_effect = AssertionError("create must run in worker")
        page._profile.update_user_profile.side_effect = AssertionError("update must run in worker")
        page._profile.delete_user_profile.side_effect = AssertionError("delete must run in worker")
        page._user_profile_create_request_id = 0
        page._user_profile_update_request_id = 0
        page._user_profile_delete_request_id = 0
        page._set_user_profile_actions_enabled = Mock()
        create_worker = _CreateWorker()
        update_worker = _UpdateWorker()
        delete_worker = _DeleteWorker()
        page._create_user_profile_create_worker = Mock(return_value=create_worker)
        page._create_user_profile_update_worker = Mock(return_value=update_worker)
        page._create_user_profile_delete_worker = Mock(return_value=delete_worker)

        PresetSetupPageBase._request_user_profile_create(
            page,
            name="YouTube",
            protocol="TCP",
            ports="443",
        )
        PresetSetupPageBase._request_user_profile_update(
            page,
            "user-1",
            name="YouTube",
            protocol="TCP",
            ports="443",
        )
        PresetSetupPageBase._request_user_profile_delete(page, "user-1")

        page._profile.create_user_profile.assert_not_called()
        page._profile.update_user_profile.assert_not_called()
        page._profile.delete_user_profile.assert_not_called()
        page._create_user_profile_create_worker.assert_called_once_with(
            1,
            name="YouTube",
            protocol="TCP",
            ports="443",
        )
        page._create_user_profile_update_worker.assert_called_once_with(
            1,
            profile_id="user-1",
            name="YouTube",
            protocol="TCP",
            ports="443",
        )
        page._create_user_profile_delete_worker.assert_called_once_with(1, profile_id="user-1")
        self.assertEqual(page._set_user_profile_actions_enabled.call_args_list, [
            call(False),
            call(False),
            call(False),
        ])
        create_worker.start.assert_called_once()
        update_worker.start.assert_called_once()
        delete_worker.start.assert_called_once()

    def test_preset_setup_user_profile_create_worker_emits_profile_item(self) -> None:
        created_item = ProfileListItem(
            key="profile:user-1",
            persistent_key="profile:user-1",
            profile_index=1,
            display_name="YouTube",
            enabled=False,
            in_preset=False,
            strategy_id="",
            strategy_name="",
            match_lines=(),
            list_type="",
            rating="",
            favorite=False,
            group="common",
            group_name="",
            order=1,
            user_profile_id="user-1",
            profile_name="YouTube",
        )
        create_user_profile = Mock(return_value="user-1")
        load_user_profile_items = Mock(return_value=(created_item,))
        worker = ProfileUserProfileCreateWorker(
            5,
            create_user_profile,
            load_user_profile_items,
            name="YouTube",
            protocol="TCP",
            ports="443",
        )
        created = []

        worker.created.connect(
            lambda request_id, profile_id, item: created.append((request_id, profile_id, item))
        )

        worker.run()

        create_user_profile.assert_called_once_with(
            name="YouTube",
            protocol="TCP",
            ports="443",
        )
        load_user_profile_items.assert_called_once_with("user-1")
        self.assertEqual(created, [(5, "user-1", created_item)])

    def test_preset_setup_user_profile_create_adds_item_without_full_refresh(self) -> None:
        created_item = ProfileListItem(
            key="profile:user-1",
            persistent_key="profile:user-1",
            profile_index=1,
            display_name="YouTube",
            enabled=False,
            in_preset=False,
            strategy_id="",
            strategy_name="",
            match_lines=(),
            list_type="",
            rating="",
            favorite=False,
            group="common",
            group_name="",
            order=1,
            user_profile_id="user-1",
            profile_name="YouTube",
        )
        profiles_list = Mock()
        profiles_list.add_profile_item.return_value = True
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._user_profile_create_request_id = 5
        page._profiles_list = profiles_list
        page._profile_payload_dirty = False
        page.refresh_from_preset_switch = Mock()
        page.window = Mock(return_value=None)

        with patch("profile.ui.preset_setup_page.InfoBar.success"):
            PresetSetupPageBase._on_user_profile_create_finished(page, 5, "user-1", created_item)

        profiles_list.add_profile_item.assert_called_once_with(created_item)
        page.refresh_from_preset_switch.assert_not_called()
        self.assertTrue(page._profile_payload_dirty)

    def test_preset_setup_user_profile_update_worker_emits_profile_items(self) -> None:
        updated_item = ProfileListItem(
            key="profile:user-1",
            persistent_key="profile:user-1",
            profile_index=1,
            display_name="YouTube New",
            enabled=True,
            in_preset=True,
            strategy_id="strategy",
            strategy_name="Strategy",
            match_lines=("--filter-tcp=443",),
            list_type="hostlist",
            rating="good",
            favorite=True,
            group="common",
            group_name="",
            order=1,
            user_profile_id="user-1",
            profile_name="YouTube New",
        )
        update_user_profile = Mock(return_value=2)
        load_user_profile_items = Mock(return_value=(updated_item,))
        worker = ProfileUserProfileUpdateWorker(
            6,
            update_user_profile,
            load_user_profile_items,
            profile_id="user-1",
            name="YouTube New",
            protocol="TCP",
            ports="443",
        )
        updated = []

        worker.updated.connect(
            lambda request_id, profile_id, changed, items: updated.append((request_id, profile_id, changed, items))
        )

        worker.run()

        update_user_profile.assert_called_once_with(
            profile_id="user-1",
            name="YouTube New",
            protocol="TCP",
            ports="443",
        )
        load_user_profile_items.assert_called_once_with("user-1")
        self.assertEqual(updated, [(6, "user-1", 2, (updated_item,))])

    def test_preset_setup_user_profile_update_replaces_items_without_full_refresh(self) -> None:
        updated_item = ProfileListItem(
            key="profile:user-1",
            persistent_key="profile:user-1",
            profile_index=1,
            display_name="YouTube New",
            enabled=True,
            in_preset=True,
            strategy_id="strategy",
            strategy_name="Strategy",
            match_lines=("--filter-tcp=443",),
            list_type="hostlist",
            rating="good",
            favorite=True,
            group="common",
            group_name="",
            order=1,
            user_profile_id="user-1",
            profile_name="YouTube New",
        )
        profiles_list = Mock()
        profiles_list.replace_user_profile_items.return_value = True
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._user_profile_update_request_id = 6
        page._profiles_list = profiles_list
        page._profile_payload_dirty = False
        page.refresh_from_preset_switch = Mock()
        page.window = Mock(return_value=None)

        with patch("profile.ui.preset_setup_page.InfoBar.success"):
            PresetSetupPageBase._on_user_profile_update_finished(page, 6, "user-1", 2, (updated_item,))

        profiles_list.replace_user_profile_items.assert_called_once_with("user-1", (updated_item,))
        page.refresh_from_preset_switch.assert_not_called()
        self.assertTrue(page._profile_payload_dirty)

    def test_preset_setup_user_profile_delete_removes_items_without_full_refresh(self) -> None:
        profiles_list = Mock()
        profiles_list.remove_user_profile_items.return_value = True
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._user_profile_delete_request_id = 7
        page._profiles_list = profiles_list
        page._profile_payload_dirty = False
        page.refresh_from_preset_switch = Mock()
        page.window = Mock(return_value=None)

        with patch("profile.ui.preset_setup_page.InfoBar.success"):
            PresetSetupPageBase._on_user_profile_delete_finished(page, 7, "user-1", 3)

        profiles_list.remove_user_profile_items.assert_called_once_with("user-1")
        page.refresh_from_preset_switch.assert_not_called()
        self.assertTrue(page._profile_payload_dirty)

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

    def test_profile_list_builds_model_through_worker_view_state(self) -> None:
        from profile.ui.profile_list_model import ProfileListModel

        list_source = inspect.getsource(ProfilesList.build_profiles)
        model_source = inspect.getsource(ProfileListModel.set_profiles)

        self.assertIn("_request_view_state_rebuild", list_source)
        self.assertIn("reset_group_expanded=True", list_source)
        self.assertNotIn("self._model.set_profiles", list_source)
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

    def test_preset_setup_skips_duplicate_loaded_payload_for_existing_list(self) -> None:
        item = ProfileListItem(
            key="profile:1",
            persistent_key="profile:1",
            profile_index=0,
            display_name="YouTube",
            enabled=True,
            in_preset=True,
            strategy_id="strategy",
            strategy_name="Strategy",
            match_lines=(),
            list_type="",
            rating="",
            favorite=False,
            group="common",
            group_name="Common",
            order=0,
        )
        payload = SimpleNamespace(
            items=(item,),
            selected_preset_name="",
            selected_preset_file_name="custom.txt",
            normalized_split_profiles=0,
            normalized_created_profiles=0,
        )
        profiles_list = SimpleNamespace(
            update_profiles=Mock(),
            set_search_query=Mock(),
            apply_view_state=Mock(),
        )
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._content_host_layout = object()
        page._profiles_list = profiles_list
        page._profile_search_query = ""
        page.title_label = _TextWidget("Настройка пресета: custom.txt")
        page.title_key = "page.winws2_pages.title"
        page.page_title = "Настройка пресета"
        page._ui_language = "ru"
        page._show_profile_normalization_info = Mock()
        page._show_empty_state = Mock()
        page._log_ui_timing = Mock()

        PresetSetupPageBase._apply_payload(page, payload)
        profiles_list.update_profiles.reset_mock()
        profiles_list.set_search_query.reset_mock()
        page._show_profile_normalization_info.reset_mock()

        PresetSetupPageBase._apply_payload(page, payload)

        profiles_list.update_profiles.assert_not_called()
        profiles_list.set_search_query.assert_not_called()
        page._show_profile_normalization_info.assert_not_called()

    def test_preset_setup_skips_duplicate_loaded_view_state_for_existing_list(self) -> None:
        item = ProfileListItem(
            key="profile:1",
            persistent_key="profile:1",
            profile_index=0,
            display_name="YouTube",
            enabled=True,
            in_preset=True,
            strategy_id="strategy",
            strategy_name="Strategy",
            match_lines=(),
            list_type="",
            rating="",
            favorite=False,
            group="common",
            group_name="Common",
            order=0,
        )
        payload = SimpleNamespace(
            items=(item,),
            selected_preset_name="",
            selected_preset_file_name="custom.txt",
            normalized_split_profiles=0,
            normalized_created_profiles=0,
        )
        view_state = SimpleNamespace(rows=[{"kind": "profile", "key": "profile:1"}])
        profiles_list = SimpleNamespace(
            update_profiles=Mock(),
            set_search_query=Mock(),
            apply_view_state=Mock(),
        )
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._content_host_layout = object()
        page._profiles_list = profiles_list
        page._profile_search_query = ""
        page.title_label = _TextWidget("Настройка пресета: custom.txt")
        page.title_key = "page.winws2_pages.title"
        page.page_title = "Настройка пресета"
        page._ui_language = "ru"
        page._show_profile_normalization_info = Mock()
        page._show_empty_state = Mock()
        page._log_ui_timing = Mock()

        PresetSetupPageBase._apply_payload(page, payload, view_state=view_state)
        profiles_list.apply_view_state.reset_mock()
        page._show_profile_normalization_info.reset_mock()

        PresetSetupPageBase._apply_payload(page, payload, view_state=view_state)

        profiles_list.apply_view_state.assert_not_called()
        page._show_profile_normalization_info.assert_not_called()

    def test_loaded_view_state_keeps_current_page_search_and_added_filter(self) -> None:
        item = ProfileListItem(
            key="profile:1",
            persistent_key="profile:1",
            profile_index=0,
            display_name="YouTube",
            enabled=True,
            in_preset=True,
            strategy_id="strategy",
            strategy_name="Strategy",
            match_lines=(),
            list_type="",
            rating="",
            favorite=False,
            group="common",
            group_name="Common",
            order=0,
        )
        payload = SimpleNamespace(
            items=(item,),
            selected_preset_name="",
            selected_preset_file_name="custom.txt",
            normalized_split_profiles=0,
            normalized_created_profiles=0,
        )
        view_state = SimpleNamespace(
            rows=[{"kind": "profile", "key": "profile:1"}],
            search_query="old query",
            show_only_added=False,
        )
        profiles_list = SimpleNamespace(
            update_profiles=Mock(),
            set_search_query=Mock(),
            set_show_only_added=Mock(),
            apply_view_state=Mock(),
        )
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._content_host_layout = object()
        page._profiles_list = profiles_list
        page._profile_search_query = "new query"
        page._profile_show_only_added = True
        page.title_label = _TextWidget("Настройка пресета: custom.txt")
        page.title_key = "page.winws2_pages.title"
        page.page_title = "Настройка пресета"
        page._ui_language = "ru"
        page._show_profile_normalization_info = Mock()
        page._show_empty_state = Mock()
        page._log_ui_timing = Mock()

        PresetSetupPageBase._apply_payload(page, payload, view_state=view_state)

        profiles_list.apply_view_state.assert_called_once_with(view_state)
        profiles_list.set_search_query.assert_called_once_with("new query")
        profiles_list.set_show_only_added.assert_called_once_with(True)

    def test_profile_list_does_not_own_page_background_color(self) -> None:
        list_source = inspect.getsource(ProfilesList._build_ui)

        self.assertNotIn("#272727", list_source)
        self.assertIn("background: transparent", list_source)

    def test_profile_list_respects_global_smooth_scroll_setting(self) -> None:
        list_source = inspect.getsource(ProfilesList)

        self.assertIn("apply_page_smooth_scroll_preference", list_source)
        self.assertIn("def set_smooth_scroll_enabled", list_source)
        self.assertIn("apply_smooth_scroll_mode(self._view, enabled)", list_source)

    def test_profile_list_skips_duplicate_search_query(self) -> None:
        profiles_list = ProfilesList.__new__(ProfilesList)
        profiles_list._search_query = "youtube"
        profiles_list._model = SimpleNamespace(set_search_query=Mock())

        ProfilesList.set_search_query(profiles_list, "youtube")

        profiles_list._model.set_search_query.assert_not_called()

    def test_profile_list_search_requests_worker_view_state_rebuild(self) -> None:
        profiles_list = ProfilesList.__new__(ProfilesList)
        profiles_list._search_query = ""
        profiles_list._model = SimpleNamespace(
            set_search_query=Mock(side_effect=AssertionError("search rows must be built in worker"))
        )
        profiles_list._request_view_state_rebuild = Mock()

        ProfilesList.set_search_query(profiles_list, "youtube")

        self.assertEqual(profiles_list._search_query, "youtube")
        profiles_list._model.set_search_query.assert_not_called()
        profiles_list._request_view_state_rebuild.assert_called_once()

    def test_profile_list_skips_duplicate_type_filter(self) -> None:
        profiles_list = ProfilesList.__new__(ProfilesList)
        profiles_list._active_profile_types = {"all"}
        profiles_list._model = SimpleNamespace(set_active_profile_types=Mock())

        ProfilesList._apply_profile_type_filter(profiles_list, {"all"})

        profiles_list._model.set_active_profile_types.assert_not_called()

    def test_profile_list_type_filter_requests_worker_view_state_rebuild(self) -> None:
        profiles_list = ProfilesList.__new__(ProfilesList)
        profiles_list._active_profile_types = {"all"}
        profiles_list._model = SimpleNamespace(
            set_active_profile_types=Mock(side_effect=AssertionError("type filter rows must be built in worker"))
        )
        profiles_list._request_view_state_rebuild = Mock()

        ProfilesList._apply_profile_type_filter(profiles_list, {"tcp"})

        self.assertEqual(profiles_list._active_profile_types, {"tcp"})
        profiles_list._model.set_active_profile_types.assert_not_called()
        profiles_list._request_view_state_rebuild.assert_called_once()

    def test_profile_list_apply_view_state_syncs_widget_filters(self) -> None:
        class _InvalidIndex:
            def isValid(self) -> bool:  # noqa: N802
                return False

        profiles_list = ProfilesList.__new__(ProfilesList)
        profiles_list._active_profile_types = {"all"}
        profiles_list._search_query = ""
        profiles_list._profile_type_selector = SimpleNamespace(set_active_profile_types=Mock())
        profiles_list._model = SimpleNamespace(
            apply_view_state=Mock(),
            rowCount=Mock(return_value=0),
        )
        profiles_list._view = SimpleNamespace(
            currentIndex=Mock(return_value=_InvalidIndex()),
            setCurrentIndex=Mock(),
        )
        state = SimpleNamespace(active_profile_types={"tcp"}, search_query="youtube")

        ProfilesList.apply_view_state(profiles_list, state)

        self.assertEqual(profiles_list._active_profile_types, {"tcp"})
        self.assertEqual(profiles_list._search_query, "youtube")
        profiles_list._profile_type_selector.set_active_profile_types.assert_called_once_with({"tcp"})
        profiles_list._model.apply_view_state.assert_called_once_with(state)
        profiles_list._view.setCurrentIndex.assert_not_called()

    def test_profile_list_folder_toggle_requests_worker_view_state_rebuild(self) -> None:
        profiles_list = ProfilesList.__new__(ProfilesList)
        profiles_list._model = SimpleNamespace(
            is_group_expanded=Mock(return_value=True),
            set_group_expanded=Mock(side_effect=AssertionError("folder rows must be built in worker")),
            view_state_options=Mock(return_value={"group_expanded": {"video": True}}),
        )
        profiles_list._request_view_state_rebuild = Mock()
        profiles_list.folder_toggled = SimpleNamespace(emit=Mock())

        ProfilesList._on_delegate_action(profiles_list, "toggle_folder", "video")

        profiles_list._model.set_group_expanded.assert_not_called()
        profiles_list._request_view_state_rebuild.assert_called_once_with(group_expanded={"video": False})
        profiles_list.folder_toggled.emit.assert_called_once_with("video", False)

    def test_profile_list_expand_all_requests_worker_view_state_rebuild(self) -> None:
        profiles_list = ProfilesList.__new__(ProfilesList)
        profiles_list._model = SimpleNamespace(
            set_all_groups_expanded=Mock(side_effect=AssertionError("expand all rows must be built in worker")),
            view_state_options=Mock(return_value={"group_expanded": {"video": False, "voice": True}}),
        )
        profiles_list._request_view_state_rebuild = Mock()
        profiles_list.folder_toggled = SimpleNamespace(emit=Mock())
        profiles_list.folders_toggled = SimpleNamespace(emit=Mock())

        ProfilesList.expand_all(profiles_list)

        profiles_list._model.set_all_groups_expanded.assert_not_called()
        profiles_list._request_view_state_rebuild.assert_called_once_with(
            group_expanded={"video": True, "voice": True}
        )
        profiles_list.folder_toggled.emit.assert_not_called()
        profiles_list.folders_toggled.emit.assert_called_once_with({"video": True}, True)

    def test_profile_list_expand_all_saves_groups_as_one_worker_action(self) -> None:
        from profile.ui.preset_setup_page import PresetSetupPageBase

        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._request_profile_folder_action = Mock()

        PresetSetupPageBase._on_folders_toggled(
            page,
            {"video": True, "voice": False},
            True,
        )

        page._request_profile_folder_action.assert_called_once_with(
            "set_collapsed_many",
            collapsed_by_key={"video": False, "voice": True},
            refresh=False,
        )

    def test_profile_list_folder_state_requests_worker_view_state_rebuild(self) -> None:
        profiles_list = ProfilesList.__new__(ProfilesList)
        profiles_list._model = SimpleNamespace(
            apply_folder_state=Mock(side_effect=AssertionError("folder state rows must be built in worker")),
        )
        profiles_list._request_view_state_rebuild = Mock()
        folder_state = {"folders": {"common": {"name": "Новая папка"}}}

        self.assertTrue(ProfilesList.apply_profile_folder_state(profiles_list, folder_state))

        profiles_list._model.apply_folder_state.assert_not_called()
        profiles_list._request_view_state_rebuild.assert_called_once_with(
            folder_state=folder_state,
            reset_group_expanded=True,
        )

    def test_profile_list_item_changes_request_worker_view_state_rebuild(self) -> None:
        current = SimpleNamespace(key="profile-1", user_profile_id="", enabled=False)
        updated = SimpleNamespace(key="profile-1", user_profile_id="", enabled=True)
        created = SimpleNamespace(key="profile-2", user_profile_id="", enabled=True)
        profiles_list = ProfilesList.__new__(ProfilesList)
        profiles_list._model = SimpleNamespace(
            view_state_options=Mock(return_value={"items": (current,), "group_expanded": {"common": True}}),
            replace_profile=Mock(side_effect=AssertionError("replace rows must be built in worker")),
            add_profile=Mock(side_effect=AssertionError("add rows must be built in worker")),
            remove_profile=Mock(side_effect=AssertionError("remove rows must be built in worker")),
        )
        profiles_list._request_view_state_rebuild = Mock()

        self.assertTrue(ProfilesList.replace_profile_item(profiles_list, "profile-1", updated))
        self.assertTrue(ProfilesList.add_profile_item(profiles_list, created))
        self.assertTrue(ProfilesList.remove_profile_item(profiles_list, "profile-1"))

        profiles_list._model.replace_profile.assert_not_called()
        profiles_list._model.add_profile.assert_not_called()
        profiles_list._model.remove_profile.assert_not_called()
        self.assertEqual(
            profiles_list._request_view_state_rebuild.call_args_list,
            [
                call(items=(updated,)),
                call(items=(current, created)),
                call(items=()),
            ],
        )

    def test_profile_list_build_and_update_request_worker_view_state_rebuild(self) -> None:
        first = SimpleNamespace(key="profile-1", user_profile_id="", enabled=True)
        second = SimpleNamespace(key="profile-2", user_profile_id="", enabled=True)
        profiles_list = ProfilesList.__new__(ProfilesList)
        profiles_list._active_profile_types = {"all"}
        profiles_list._search_query = ""
        profiles_list._model = SimpleNamespace(
            set_profiles=Mock(side_effect=AssertionError("initial rows must be built in worker")),
            update_profiles=Mock(side_effect=AssertionError("updated rows must be built in worker")),
        )
        profiles_list._request_view_state_rebuild = Mock()

        ProfilesList.build_profiles(profiles_list, (first,))
        self.assertTrue(ProfilesList.update_profiles(profiles_list, (first, second)))

        profiles_list._model.set_profiles.assert_not_called()
        profiles_list._model.update_profiles.assert_not_called()
        self.assertEqual(
            profiles_list._request_view_state_rebuild.call_args_list,
            [
                call(items=(first,), reset_group_expanded=True),
                call(items=(first, second)),
            ],
        )

    def test_profile_list_move_requests_worker_view_state_rebuild(self) -> None:
        first = SimpleNamespace(key="profile-1", group="common", group_name="Общие", order=0, order_is_manual=False)
        second = SimpleNamespace(key="profile-2", group="video", group_name="Видео", order=1, order_is_manual=False)
        profiles_list = ProfilesList.__new__(ProfilesList)
        profiles_list._model = SimpleNamespace(
            move_profile=Mock(side_effect=AssertionError("move rows must be built in worker")),
            view_state_options=Mock(return_value={
                "items": (first, second),
                "group_expanded": {"common": True, "video": True},
            }),
        )
        profiles_list._request_view_state_rebuild = Mock()

        self.assertTrue(
            ProfilesList.move_profile_item(
                profiles_list,
                "profile-1",
                "profile_after",
                "profile-2",
                "video",
            )
        )

        profiles_list._model.move_profile.assert_not_called()
        self.assertEqual(
            profiles_list._request_view_state_rebuild.call_args.kwargs,
            {
                "move_request": {
                    "source_profile_key": "profile-1",
                    "destination_kind": "profile_after",
                    "destination_profile_key": "profile-2",
                    "destination_group_key": "video",
                },
            },
        )

    def test_profile_list_move_builds_local_view_state_in_worker(self) -> None:
        move_source = inspect.getsource(ProfilesList.move_profile_item)
        worker_source = inspect.getsource(ProfileListViewStateWorker.run)

        self.assertNotIn("_moved_profile_items", move_source)
        self.assertNotIn("_group_expanded_with_target", move_source)
        self.assertIn("_moved_profile_items", worker_source)
        self.assertIn("_group_expanded_with_target", worker_source)

    def test_profile_list_move_worker_returns_moved_view_state(self) -> None:
        first = SimpleNamespace(
            key="profile-1",
            persistent_key="profile-1",
            profile_index=0,
            profile_name="First",
            enabled=True,
            in_preset=True,
            strategy_id="none",
            strategy_name="None",
            match_lines=(),
            list_type="",
            rating="",
            favorite=False,
            group="common",
            group_name="Общие",
            order=0,
            source_order=0,
            group_rank=0,
            group_collapsed=False,
            user_profile_id="",
        )
        second = SimpleNamespace(
            key="profile-2",
            persistent_key="profile-2",
            profile_index=1,
            profile_name="Second",
            enabled=True,
            in_preset=True,
            strategy_id="none",
            strategy_name="None",
            match_lines=(),
            list_type="",
            rating="",
            favorite=False,
            group="video",
            group_name="Видео",
            order=1,
            source_order=1,
            group_rank=1,
            group_collapsed=False,
            user_profile_id="",
        )
        loaded = []
        worker = ProfileListViewStateWorker(
            5,
            items=(first, second),
            active_profile_types={"all"},
            search_query="",
            show_only_added=False,
            group_expanded={"common": True, "video": True},
            move_request={
                "source_profile_key": "profile-1",
                "destination_kind": "profile_after",
                "destination_profile_key": "profile-2",
                "destination_group_key": "video",
            },
        )
        worker.loaded.connect(lambda _request_id, state: loaded.append(state))

        worker.run()

        self.assertEqual(len(loaded), 1)
        moved = loaded[0].profile_items["profile-1"]
        self.assertEqual(moved.group, "video")
        self.assertEqual(moved.group_name, "Видео")
        self.assertEqual(moved.order, 1)

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
        from profile.ui.profile_list_delegate import _profile_row_is_interactive

        self.assertTrue(_profile_row_is_interactive(1, hovered=False, selected=False, hover_row=1, pressed_row=-1, selected_rows=set()))
        self.assertTrue(_profile_row_is_interactive(1, hovered=False, selected=False, hover_row=-1, pressed_row=1, selected_rows=set()))
        self.assertTrue(_profile_row_is_interactive(1, hovered=False, selected=False, hover_row=-1, pressed_row=-1, selected_rows={1}))

    def test_profile_delegate_uses_shared_accent_row_painter(self) -> None:
        from profile.ui.profile_list_delegate import ProfileListDelegate

        source = inspect.getsource(ProfileListDelegate._paint_profile_row)

        self.assertIn("paint_profile_hover_row", source)
        self.assertIn("profile_hover_row_rect", source)
        self.assertIn("active=False", source)
        self.assertIn("show_active_marker=False", source)
        self.assertNotIn("active=accent_active", source)
        self.assertNotIn("_paint_profile_row_background", source)
        self.assertIn('painter.drawText(row_layout.dot_rect', source)

    def test_profile_delegate_uses_soft_badge_colors(self) -> None:
        from profile.ui.profile_list_delegate import _badge_palette, _profile_row_uses_accent, _status_dot_color
        from ui.widgets.profile_row_style import (
            PROFILE_BADGE_HOSTLIST_BG,
            PROFILE_BADGE_HOSTLIST_FG,
            PROFILE_BADGE_IPSET_BG,
            PROFILE_BADGE_IPSET_FG,
        )

        self.assertEqual(_badge_palette("hostlist"), (PROFILE_BADGE_HOSTLIST_BG, PROFILE_BADGE_HOSTLIST_FG))
        self.assertEqual(_badge_palette("ipset"), (PROFILE_BADGE_IPSET_BG, PROFILE_BADGE_IPSET_FG))
        self.assertFalse(_profile_row_uses_accent(True, tinted_background=False))
        self.assertTrue(_profile_row_uses_accent(True, tinted_background=True))
        self.assertEqual(
            _status_dot_color(True, active_color="#00c2b5", fallback="#8f9aa6", tinted_background=False),
            "#00c2b5",
        )
        self.assertEqual(
            _status_dot_color(True, active_color="#00c2b5", fallback="#8f9aa6", tinted_background=True),
            "#00c2b5",
        )
        self.assertEqual(
            _status_dot_color(False, active_color="#00c2b5", fallback="#8f9aa6", tinted_background=True),
            "#8f9aa6",
        )

        source = inspect.getsource(_badge_palette)
        self.assertNotIn("#00B900", source)

    def test_profile_simple_icons_are_cached_for_fast_repaint(self) -> None:
        from profile.ui import profile_icon

        source = inspect.getsource(profile_icon.profile_icon_pixmap)
        cache_source = inspect.getsource(profile_icon._cached_profile_pixmap)

        self.assertIn("_cached_profile_pixmap", source)
        self.assertIn("_PROFILE_PIXMAP_CACHE", cache_source)
        self.assertIn("QPixmap(cached)", cache_source)

    def test_profile_delegate_no_longer_uses_fixed_dark_row_colors(self) -> None:
        import profile.ui.profile_list_delegate as delegate_module

        self.assertFalse(hasattr(delegate_module, "_profile_row_background"))
        source = inspect.getsource(delegate_module.ProfileListDelegate._paint_profile_row)
        self.assertNotIn("PROFILE_ROW_BG_DARK", source)
        self.assertNotIn("PROFILE_ROW_BG_DARK_HOVER", source)

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

    def test_profile_model_set_profiles_skips_reset_for_same_payload(self) -> None:
        from profile.ui.profile_list_model import ProfileListModel

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
        model.set_profiles((youtube,))
        model.beginResetModel = Mock(side_effect=AssertionError("same profile payload must not reset the whole model"))

        model.set_profiles((youtube,))

        self.assertEqual(model.rowCount(), 2)
        self.assertEqual(model.index(1, 0).data(ProfileListModel.ProfileKeyRole), "profile:1")

    def test_profile_model_apply_view_state_skips_reset_for_same_state(self) -> None:
        from profile.list_view_state import build_profile_list_view_state
        from profile.ui.profile_list_model import ProfileListModel

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

        state = build_profile_list_view_state((youtube,))
        model = ProfileListModel()
        model.apply_view_state(state)
        model.beginResetModel = Mock(side_effect=AssertionError("same view state must not reset the whole model"))

        model.apply_view_state(state)

        self.assertEqual(model.rowCount(), 2)
        self.assertEqual(model.index(1, 0).data(ProfileListModel.ProfileKeyRole), "profile:1")

    def test_profile_list_view_state_can_show_only_added_profiles(self) -> None:
        from profile.list_view_state import build_profile_list_view_state

        added = SimpleNamespace(
            key="profile:added",
            persistent_key="p-added",
            profile_index=1,
            display_name="YouTube",
            enabled=True,
            in_preset=True,
            strategy_id="fake",
            strategy_name="Fake",
            match_lines=("--filter-tcp=443",),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="video",
            group_name="Video",
            order=1,
            source_order=1,
            group_rank=1,
            group_collapsed=False,
        )
        unused = SimpleNamespace(
            **{
                **vars(added),
                "key": "profile:unused",
                "persistent_key": "p-unused",
                "display_name": "Unused",
                "in_preset": False,
            }
        )

        state = build_profile_list_view_state(
            (added, unused),
            show_only_added=True,
        )

        profile_keys = [
            row.get("key")
            for row in state.rows
            if row.get("kind") == "profile"
        ]
        self.assertEqual(profile_keys, ["profile:added"])
        self.assertTrue(state.show_only_added)

    def test_profile_model_apply_view_state_updates_stable_rows_without_full_reset(self) -> None:
        from profile.list_view_state import build_profile_list_view_state
        from profile.ui.profile_list_model import ProfileListModel

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
        updated = SimpleNamespace(
            **{
                **vars(youtube),
                "display_name": "YouTube updated",
                "profile_name": "YouTube updated",
                "strategy_id": "fake",
                "strategy_name": "Fake",
            }
        )

        model = ProfileListModel()
        model.apply_view_state(build_profile_list_view_state((youtube,)))
        model.beginResetModel = Mock(side_effect=AssertionError("stable view state rows must not reset the whole model"))

        model.apply_view_state(build_profile_list_view_state((updated,)))

        self.assertEqual(model.rowCount(), 2)
        self.assertEqual(model.index(1, 0).data(ProfileListModel.ProfileKeyRole), "profile:1")
        self.assertEqual(model.index(1, 0).data(ProfileListModel.DisplayNameRole), "YouTube updated")
        self.assertEqual(model.index(1, 0).data(ProfileListModel.StrategyNameRole), "Fake")

    def test_profile_model_toggles_one_folder_without_resetting_whole_model(self) -> None:
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
        model.beginResetModel = Mock(side_effect=AssertionError("folder toggle must not reset the whole model"))

        model.set_group_expanded("voice", True)
        self.assertEqual(model.rowCount(), 4)

        model.set_group_expanded("voice", False)
        self.assertEqual(model.rowCount(), 3)

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
            source_order=1,
            group_rank=1,
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

    def test_profile_model_search_skips_reset_when_visible_rows_do_not_change(self) -> None:
        from profile.ui.profile_list_model import ProfileListModel

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
        model.set_profiles((youtube,))
        model.set_search_query("you")
        model.beginResetModel = Mock(side_effect=AssertionError("search update with same visible rows must not reset"))

        model.set_search_query("youtube")

        self.assertEqual(model.rowCount(), 2)
        self.assertEqual(model.index(1, 0).data(ProfileListModel.ProfileKeyRole), "profile:1")

    def test_profile_model_type_filter_skips_reset_when_visible_rows_do_not_change(self) -> None:
        from profile.ui.profile_list_model import ProfileListModel

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
        model.set_profiles((youtube,))
        model.beginResetModel = Mock(side_effect=AssertionError("type filter with same visible rows must not reset"))

        model.set_active_profile_types({"tcp"})

        self.assertEqual(model.rowCount(), 2)
        self.assertEqual(model.index(1, 0).data(ProfileListModel.ProfileKeyRole), "profile:1")

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
            source_order=0,
            group_rank=0,
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
            source_order=0,
            group_rank=0,
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

    def test_profile_model_moves_profile_inside_folder_without_full_reset(self) -> None:
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
            rating="",
            favorite=False,
            group="common",
            group_name="Общие",
            order=0,
            order_is_manual=True,
            group_collapsed=False,
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
            group="common",
            group_name="Общие",
            order=1,
            order_is_manual=True,
            group_collapsed=False,
        )

        model = ProfileListModel()
        model.set_profiles((first, second))
        model.beginResetModel = Mock(side_effect=AssertionError("profile move must not reset the whole model"))

        self.assertTrue(model.move_profile("profile:0", "profile_after", "profile:1", "common"))

        rows = [
            (
                model.index(row, 0).data(ProfileListModel.KindRole),
                model.index(row, 0).data(ProfileListModel.ProfileKeyRole),
            )
            for row in range(model.rowCount())
        ]
        self.assertLess(rows.index(("profile", "profile:1")), rows.index(("profile", "profile:0")))

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
            source_order=0,
            group_rank=0,
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

    def test_profile_model_profile_row_lookup_uses_cached_visible_index(self) -> None:
        from profile.ui import profile_list_model

        source = inspect.getsource(profile_list_model.ProfileListModel._row_index_for_profile_key)

        self.assertIn("_profile_row_by_key", source)
        self.assertNotIn("for index, row in enumerate", source)

    def test_profile_model_skips_replacing_identical_profile_row(self) -> None:
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
            source_order=0,
            group_rank=0,
            group_collapsed=False,
        )

        model = ProfileListModel()
        model.set_profiles((youtube,))
        model.beginResetModel = Mock(side_effect=AssertionError("same profile row must not reset the whole model"))
        model.index = Mock(side_effect=AssertionError("same profile row must not repaint"))

        self.assertTrue(model.replace_profile("profile:0", youtube))
        self.assertEqual(model.rowCount(), 2)

    def test_profile_model_updates_hidden_profile_without_reset(self) -> None:
        from profile.ui.profile_list_model import ProfileListModel

        discord = SimpleNamespace(
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
            group="voice",
            group_name="Voice",
            order=0,
            source_order=0,
            group_rank=0,
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
            order=1,
            source_order=1,
            group_rank=1,
            group_collapsed=False,
        )
        updated_discord = SimpleNamespace(
            **{
                **discord.__dict__,
                "strategy_id": "updated",
                "strategy_name": "Updated",
            }
        )

        model = ProfileListModel()
        model.set_profiles((discord, youtube))
        model.set_search_query("youtube")
        model.beginResetModel = Mock(side_effect=AssertionError("hidden profile update must not reset visible rows"))

        self.assertTrue(model.replace_profile("profile:0", updated_discord))

        rows = [
            (
                model.index(row, 0).data(ProfileListModel.KindRole),
                model.index(row, 0).data(ProfileListModel.ProfileKeyRole),
            )
            for row in range(model.rowCount())
        ]
        self.assertIn(("profile", "profile:1"), rows)
        self.assertNotIn(("profile", "profile:0"), rows)
        self.assertEqual(model.profile_item_for_key("profile:0").strategy_id, "updated")

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
            source_order=0,
            group_rank=0,
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

    def test_profile_model_removes_hidden_profile_without_reset(self) -> None:
        from profile.ui.profile_list_model import ProfileListModel

        discord = SimpleNamespace(
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
            group="voice",
            group_name="Voice",
            order=0,
            source_order=0,
            group_rank=0,
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
            order=1,
            source_order=1,
            group_rank=1,
            group_collapsed=False,
        )

        model = ProfileListModel()
        model.set_profiles((discord, youtube))
        model.set_search_query("youtube")
        model.beginResetModel = Mock(side_effect=AssertionError("hidden profile remove must not reset visible rows"))

        self.assertTrue(model.remove_profile("profile:0"))

        rows = [
            (
                model.index(row, 0).data(ProfileListModel.KindRole),
                model.index(row, 0).data(ProfileListModel.ProfileKeyRole),
            )
            for row in range(model.rowCount())
        ]
        self.assertIn(("profile", "profile:1"), rows)
        self.assertNotIn(("profile", "profile:0"), rows)
        self.assertIsNone(model.profile_item_for_key("profile:0"))

    def test_profile_model_adds_hidden_profile_without_reset(self) -> None:
        from profile.ui.profile_list_model import ProfileListModel

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
            order=1,
            source_order=1,
            group_rank=1,
            group_collapsed=False,
        )
        discord = SimpleNamespace(
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
            group="voice",
            group_name="Voice",
            order=0,
            source_order=0,
            group_rank=0,
            group_collapsed=False,
        )

        model = ProfileListModel()
        model.set_profiles((youtube,))
        model.set_search_query("youtube")
        model.beginResetModel = Mock(side_effect=AssertionError("hidden profile add must not reset visible rows"))

        self.assertTrue(model.add_profile(discord))

        rows = [
            (
                model.index(row, 0).data(ProfileListModel.KindRole),
                model.index(row, 0).data(ProfileListModel.ProfileKeyRole),
            )
            for row in range(model.rowCount())
        ]
        self.assertIn(("profile", "profile:1"), rows)
        self.assertNotIn(("profile", "profile:0"), rows)
        self.assertIsNotNone(model.profile_item_for_key("profile:0"))

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
            source_order=0,
            group_rank=0,
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

    def test_profile_drag_handlers_run_move_worker_then_update_visible_list_locally(self) -> None:
        from profile.ui.preset_write_queue import PresetWriteQueue

        before_handler = inspect.getsource(PresetSetupPageBase._on_profile_move_requested)
        after_handler = inspect.getsource(PresetSetupPageBase._on_profile_move_after_requested)
        request_handler = inspect.getsource(PresetWriteQueue._request_profile_move)
        start_handler = inspect.getsource(PresetWriteQueue._start_profile_move_worker)
        finish_handler = inspect.getsource(PresetWriteQueue._on_profile_move_finished)

        self.assertIn("_request_profile_move", before_handler)
        self.assertIn("_request_profile_move", after_handler)
        self.assertNotIn("_apply_profile_move_locally", before_handler)
        self.assertNotIn("_apply_profile_move_locally", after_handler)
        self.assertIn("_create_profile_move_worker", request_handler + start_handler)
        self.assertIn("_apply_profile_move_locally", finish_handler)
        self.assertIn("refresh_from_preset_switch()", finish_handler)
        self.assertLess(finish_handler.index("_apply_profile_move_locally"), finish_handler.index("refresh_from_preset_switch()"))
        self.assertNotIn("_profile.move_profile_before", before_handler)
        self.assertNotIn("_profile.move_profile_after", after_handler)
        self.assertNotIn("refresh_from_preset_switch()", before_handler)
        self.assertNotIn("refresh_from_preset_switch()", after_handler)

    def test_preset_setup_cleanup_stops_all_profile_workers(self) -> None:
        source = inspect.getsource(PresetSetupPageBase.cleanup)

        for attr in (
            "_profile_load_runtime",
            "_profile_item_refresh_runtime",
            "_profile_context_action_runtime",
            "_profile_move_runtime",
            "_profile_folder_action_runtime",
            "_user_profile_create_runtime",
            "_user_profile_update_runtime",
            "_user_profile_delete_runtime",
        ):
            self.assertIn(attr, source)
        self.assertIn("_profile_folder_action_state_obj().reset()", source)
        self.assertIn("_deferred_profile_payload_apply = None", source)
        self.assertIn(".stop(", source)
        self.assertIn(".cancel()", source)

    def test_stale_profile_load_worker_finished_does_not_schedule_refresh(self) -> None:
        old_worker = SimpleNamespace(_request_id=6)
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_load_runtime_request_id = 7
        page._profile_load_refresh_pending = True
        page._profile_payload_dirty = True
        page._cleanup_in_progress = False
        page._schedule_profiles_payload_request = Mock(
            side_effect=AssertionError("stale profile load worker must not schedule refresh")
        )

        PresetSetupPageBase._on_profile_worker_finished(page, old_worker)

        self.assertEqual(page._profile_load_runtime_request_id, 7)
        self.assertTrue(page._profile_load_refresh_pending)
        page._schedule_profiles_payload_request.assert_not_called()

    def test_stale_profile_context_worker_finished_does_not_drive_write_queue(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_context_action_request_id = 7
        page._schedule_next_profile_preset_write_operation_start = Mock(
            side_effect=AssertionError("stale context worker must not drive write queue")
        )

        PresetSetupPageBase._on_profile_context_action_worker_finished(page, SimpleNamespace(_request_id=6))

        self.assertEqual(page._profile_context_action_request_id, 7)
        page._schedule_next_profile_preset_write_operation_start.assert_not_called()

    def test_stale_profile_move_worker_finished_does_not_drive_write_queue(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_move_request_id = 7
        page._schedule_next_profile_preset_write_operation_start = Mock(
            side_effect=AssertionError("stale move worker must not drive write queue")
        )

        PresetSetupPageBase._on_profile_move_worker_finished(page, SimpleNamespace(_request_id=6))

        self.assertEqual(page._profile_move_request_id, 7)
        page._schedule_next_profile_preset_write_operation_start.assert_not_called()

    def test_stale_profile_folder_worker_finished_does_not_pop_pending_action(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_folder_action_request_id = 7
        page._cleanup_in_progress = False
        page._profile_folder_action_pending = [{"action": "set_collapsed", "folder_key": "video"}]
        page._schedule_profile_folder_action_start = Mock(
            side_effect=AssertionError("stale folder worker must not start pending action")
        )

        PresetSetupPageBase._on_profile_folder_action_worker_finished(page, SimpleNamespace(_request_id=6))

        self.assertEqual(page._profile_folder_action_request_id, 7)
        self.assertEqual(page._profile_folder_action_pending, [{"action": "set_collapsed", "folder_key": "video"}])
        page._schedule_profile_folder_action_start.assert_not_called()

    def test_stale_user_profile_workers_finished_do_not_enable_actions_or_drive_queue(self) -> None:
        for attr, handler_name in (
            ("_user_profile_create_request_id", "_on_user_profile_create_worker_finished"),
            ("_user_profile_update_request_id", "_on_user_profile_update_worker_finished"),
            ("_user_profile_delete_request_id", "_on_user_profile_delete_worker_finished"),
        ):
            with self.subTest(attr=attr):
                page = PresetSetupPageBase.__new__(PresetSetupPageBase)
                setattr(page, attr, 7)
                page._schedule_next_profile_preset_write_operation_start = Mock(
                    side_effect=AssertionError("stale user profile worker must not drive write queue")
                )
                page._user_profile_operation_running = Mock(return_value=False)
                page._set_user_profile_actions_enabled = Mock()

                getattr(PresetSetupPageBase, handler_name)(page, SimpleNamespace(_request_id=6))

                self.assertEqual(getattr(page, attr), 7)
                page._schedule_next_profile_preset_write_operation_start.assert_not_called()
                page._set_user_profile_actions_enabled.assert_not_called()

    def test_list_file_load_result_is_current_for_multi_file_filter_value(self) -> None:
        # Профили «Все сайты (айпи)» несут несколько файлов через запятую —
        # результат, эхом повторяющий пару последнего запроса, обязан пройти
        # проверку актуальности (AC1: раньше выбрасывался из-за имени файла).
        multi_value = "lists/ipset-ru.txt,lists/ipset-dns.txt,lists/ipset-exclude.txt"
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "profile:3"
        page._list_file_editor_filter = ("ipset", multi_value)
        result = SimpleNamespace(
            profile_key="profile:3",
            filter_kind="ipset",
            filter_value=multi_value,
        )

        self.assertTrue(ProfileSetupPageBase._list_file_load_result_is_current(page, result))

    def test_list_file_load_result_is_current_for_kind_switch_preview(self) -> None:
        # Регрессия «бесконечная загрузка файла списка»: при переключении типа
        # Hostlist → IPset сервис легитимно ремапит пару (youtube.txt →
        # ipset-youtube.txt) — состояние описывает ДРУГОЙ файл, чем пара
        # запроса. Идентичность результата — эхо пары, а не сравнение имён.
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "profile:0"
        page._list_file_editor_filter = ("ipset", "lists/youtube.txt")
        result = SimpleNamespace(
            profile_key="profile:0",
            filter_kind="ipset",
            filter_value="lists/youtube.txt",
            state=SimpleNamespace(display_path="lists/ipset-youtube.txt", editable=True),
        )

        self.assertTrue(ProfileSetupPageBase._list_file_load_result_is_current(page, result))

    def test_list_file_load_result_is_stale_for_other_request_pair(self) -> None:
        # Результат чужого запроса (контекст уже перезапрошен с другой парой)
        # не применяется.
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "profile:3"
        page._list_file_editor_filter = ("ipset", "lists/ipset-youtube.txt,lists/ipset-dns.txt")
        result = SimpleNamespace(
            profile_key="profile:3",
            filter_kind="ipset",
            filter_value="lists/ipset-ru.txt,lists/ipset-dns.txt",
        )

        self.assertFalse(ProfileSetupPageBase._list_file_load_result_is_current(page, result))

    def test_list_file_load_result_is_stale_for_other_profile_key(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "profile:4"
        page._list_file_editor_filter = ("hostlist", "lists/youtube.txt")
        result = SimpleNamespace(
            profile_key="profile:3",
            filter_kind="hostlist",
            filter_value="lists/youtube.txt",
        )

        self.assertFalse(ProfileSetupPageBase._list_file_load_result_is_current(page, result))

    def test_list_file_none_state_shows_error_instead_of_endless_loading(self) -> None:
        # Профиль не разрешился (удалён/переименован во время загрузки):
        # молчаливый return оставлял статус «Загрузка файла списка...» навсегда.
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "profile:0"
        page._list_file_load_request_id = 5
        page._list_file_editor_filter = ("hostlist", "lists/youtube.txt")
        page._list_file_load_state_obj = Mock(return_value=SimpleNamespace(has_pending=lambda: False))
        page._list_file_status_label = object()
        page._schedule_list_file_editor_state_apply = Mock(
            side_effect=AssertionError("None state must not be applied")
        )
        result = SimpleNamespace(
            profile_key="profile:0",
            filter_kind="hostlist",
            filter_value="lists/youtube.txt",
            state=None,
        )

        with patch("profile.ui.profile_setup_page.set_profile_list_status_text") as set_status:
            ProfileSetupPageBase._on_list_file_editor_state_loaded(page, 5, result)

        set_status.assert_called_once()
        self.assertIn("Ошибка загрузки файла списка", set_status.call_args.args[1])

    def test_filter_value_editing_finished_reloads_editor_for_changed_pair(self) -> None:
        # Правка пути в поле — мутация контекста редактора: без перезагрузки
        # последний результат навсегда остался бы про другой файл.
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._current_filter_kind = lambda: "hostlist"
        page._current_filter_value = lambda: "lists/edited.txt"
        page._list_file_editor_filter = ("hostlist", "lists/original.txt")
        page._flush_list_file_autosave_before_filter_switch = Mock()
        page._editor_tab_built = True
        page._strategy_stack = SimpleNamespace(currentIndex=lambda: 1)
        page._request_list_file_editor_state = Mock()

        ProfileSetupPageBase._on_filter_value_editing_finished(page)

        page._flush_list_file_autosave_before_filter_switch.assert_called_once()
        page._request_list_file_editor_state.assert_called_once()

    def test_filter_value_editing_finished_skips_reload_for_same_pair(self) -> None:
        # editingFinished срабатывает и на потере фокуса без правок —
        # незачем гонять воркер и терять несохранённый baseline.
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._current_filter_kind = lambda: "hostlist"
        page._current_filter_value = lambda: "lists/original.txt"
        page._list_file_editor_filter = ("hostlist", "lists/original.txt")
        page._flush_list_file_autosave_before_filter_switch = Mock(
            side_effect=AssertionError("unchanged pair must not flush")
        )
        page._request_list_file_editor_state = Mock(
            side_effect=AssertionError("unchanged pair must not reload")
        )

        ProfileSetupPageBase._on_filter_value_editing_finished(page)

    def test_breadcrumb_click_restores_crumbs_before_navigation(self) -> None:
        # Клик по крошке физически удаляет из BreadcrumbBar элементы правее
        # выбранного — обработчик обязан перестроить полный путь до навигации.
        for key, navigate_attr in (("control", "_open_root"), ("profiles", "_open_profiles")):
            with self.subTest(key=key):
                page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
                page._rebuild_breadcrumb = Mock()
                page._open_root = Mock()
                page._open_profiles = Mock()

                ProfileSetupPageBase._on_breadcrumb_item_changed(page, key)

                page._rebuild_breadcrumb.assert_called_once()
                getattr(page, navigate_attr).assert_called_once()

    def test_profile_setup_cleanup_stops_all_detail_workers_and_pending_requests(self) -> None:
        class _Worker:
            def __init__(self) -> None:
                self.quit = Mock()

        class _Runtime:
            def __init__(self) -> None:
                self.stop = Mock()
                self.cancel = Mock()

        runtime_attrs = (
            "_setup_load_runtime",
            "_list_file_load_runtime",
            "_list_file_save_runtime",
            "_list_file_validation_runtime",
            "_settings_save_runtime",
            "_raw_profile_save_runtime",
            "_enabled_save_runtime",
            "_user_profile_update_runtime",
            "_user_profile_delete_runtime",
            "_strategy_apply_runtime",
            "_strategy_feedback_save_runtime",
        )
        worker_attrs = ()
        worker_ref_attrs = ()
        request_attrs = (
            "_setup_load_request_id",
            "_list_file_load_request_id",
            "_list_file_save_request_id",
            "_list_file_validation_request_id",
            "_settings_save_request_id",
            "_raw_profile_save_request_id",
            "_enabled_save_request_id",
            "_user_profile_update_request_id",
            "_user_profile_delete_request_id",
            "_strategy_apply_request_id",
            "_strategy_feedback_save_request_id",
        )
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        runtimes = {attr: _Runtime() for attr in runtime_attrs}
        for attr, runtime in runtimes.items():
            setattr(page, attr, runtime)
        workers = {attr: _Worker() for attr in worker_attrs}
        for attr, worker in workers.items():
            setattr(page, attr, worker)
        worker_refs = {attr: object() for attr in worker_ref_attrs}
        for attr, worker in worker_refs.items():
            setattr(page, attr, worker)
        for attr in request_attrs:
            setattr(page, attr, 7)
        page._pending_list_file_validation = {"kind": "hostlist"}
        page._pending_settings_save = {"setting": "filter"}
        page._pending_strategy_apply = "strategy-id"
        page._pending_strategy_feedback_save = {"rating": "work"}
        page._setup_load_dirty = True
        page._setup_load_start_scheduled = True
        page._settings_save_timer = SimpleNamespace(stop=Mock())

        ProfileSetupPageBase.cleanup(page)

        for runtime in runtimes.values():
            runtime.stop.assert_called_once()
            runtime.cancel.assert_called_once()
        for worker in workers.values():
            worker.quit.assert_called_once()
        for attr in worker_attrs:
            self.assertIsNone(getattr(page, attr))
        for attr in worker_ref_attrs:
            self.assertIsNone(getattr(page, attr))
        for attr in request_attrs:
            self.assertEqual(getattr(page, attr), 8)
        self.assertIsNone(page._pending_list_file_validation)
        self.assertIsNone(page._pending_settings_save)
        self.assertIsNone(page._pending_strategy_apply)
        self.assertIsNone(page._pending_strategy_feedback_save)
        self.assertFalse(page._setup_load_dirty)
        self.assertFalse(page._setup_load_start_scheduled)
        page._settings_save_timer.stop.assert_called_once()

    def test_profile_move_starts_worker_without_direct_profile_call(self) -> None:
        class _Signal:
            def __init__(self) -> None:
                self.callbacks = []

            def connect(self, callback) -> None:
                self.callbacks.append(callback)

        class _Worker:
            def __init__(self) -> None:
                self.moved = _Signal()
                self.failed = _Signal()
                self.finished = _Signal()
                self.start = Mock()
                self.deleteLater = Mock()

            def isRunning(self) -> bool:
                return False

        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page.launch_method = "zapret2_mode"
        page._profile = Mock()
        page._profile.move_profile_before.side_effect = AssertionError("move must run in worker")
        page._profile_move_request_id = 0
        page._create_profile_move_worker = Mock(return_value=_Worker())

        PresetSetupPageBase._request_profile_move(
            page,
            "before",
            "profile-1",
            destination_profile_key="profile-2",
            destination_group_key="youtube",
        )

        page._profile.move_profile_before.assert_not_called()
        page._create_profile_move_worker.assert_called_once_with(
            1,
            "zapret2_mode",
            action="before",
            source_profile_key="profile-1",
            destination_profile_key="profile-2",
            destination_group_key="youtube",
        )
        page._create_profile_move_worker.return_value.start.assert_called_once()

    def test_profile_move_worker_emits_move_result(self) -> None:
        move_profile_before = Mock(return_value="profile-1")
        move_profile_after = Mock()
        move_profile_to_end = Mock()
        move_profile_to_folder = Mock()
        worker = ProfilePresetProfileMoveWorker(
            9,
            move_profile_before,
            move_profile_after,
            move_profile_to_end,
            move_profile_to_folder,
            action="before",
            source_profile_key="profile-1",
            destination_profile_key="profile-2",
            destination_group_key="youtube",
        )
        moved = []

        worker.moved.connect(
            lambda request_id, action, source_key, destination_key, group_key, result: moved.append((
                request_id,
                action,
                source_key,
                destination_key,
                group_key,
                result,
            ))
        )

        worker.run()

        move_profile_before.assert_called_once_with(
            "profile-1",
            "profile-2",
            destination_folder_key="youtube",
        )
        self.assertEqual(moved, [(9, "before", "profile-1", "profile-2", "youtube", "profile-1")])

    def test_profile_move_result_applies_locally_when_new_action_is_pending(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_move_request_id = 4
        page._profile_payload_dirty = False
        page._pending_profile_preset_write_operations = [
            {
                "kind": "move",
                "action": "after",
                "profile_key": "profile-1",
                "enabled": None,
                "source_profile_key": "profile-1",
                "destination_profile_key": "profile-3",
                "destination_group_key": "youtube",
            }
        ]
        page._pending_profile_context_actions = []
        page._pending_profile_moves = [
            {
                "action": "after",
                "source_profile_key": "profile-1",
                "destination_profile_key": "profile-3",
                "destination_group_key": "youtube",
            }
        ]
        page._pending_user_profile_operations = []
        page._apply_profile_move_locally = Mock(return_value=True)
        page.refresh_from_preset_switch = Mock()

        PresetSetupPageBase._on_profile_move_finished(
            page,
            4,
            "before",
            "profile-1",
            "profile-2",
            "youtube",
            True,
        )

        page._apply_profile_move_locally.assert_called_once_with(
            "before",
            "profile-1",
            destination_profile_key="profile-2",
            destination_group_key="youtube",
        )
        page.refresh_from_preset_switch.assert_not_called()
        self.assertTrue(page._profile_payload_dirty)

    def test_profile_context_actions_refresh_current_list_through_worker(self) -> None:
        from profile.ui.preset_write_queue import PresetWriteQueue

        enable_handler = inspect.getsource(PresetSetupPageBase._set_profile_enabled_from_menu)
        duplicate_handler = inspect.getsource(PresetSetupPageBase._duplicate_profile_from_menu)
        delete_handler = inspect.getsource(PresetSetupPageBase._delete_profile_from_menu)
        request_handler = inspect.getsource(PresetWriteQueue._request_profile_context_action)
        start_handler = inspect.getsource(PresetWriteQueue._start_profile_context_action_worker)
        finish_handler = inspect.getsource(PresetWriteQueue._on_profile_context_action_finished)
        sync_handler = inspect.getsource(PresetSetupPageBase._sync_profile_list_locally)

        self.assertIn("_request_profile_context_action", enable_handler)
        self.assertIn("_request_profile_context_action", duplicate_handler)
        self.assertIn("_request_profile_context_action", delete_handler)
        self.assertIn("create_profile_context_action_worker", request_handler + start_handler)
        self.assertIn("_refresh_profile_item_locally", finish_handler)
        self.assertIn("_add_profile_item_locally", finish_handler)
        self.assertIn("_remove_profile_item_locally", finish_handler)
        self.assertNotIn("_profile.set_profile_enabled", enable_handler)
        self.assertNotIn("_profile.duplicate_profile", duplicate_handler)
        self.assertNotIn("_profile.delete_profile", delete_handler)
        self.assertIn("_schedule_profiles_payload_request(force=True)", sync_handler)
        self.assertNotIn(".list_profiles(", sync_handler)
        self.assertNotIn("update_profiles", sync_handler)
        self.assertNotIn("build_profiles", sync_handler)

    def test_profile_list_local_refresh_helpers_do_not_read_profiles_in_gui_thread(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile = Mock()
        page._profile.list_profiles.side_effect = AssertionError("list must load in worker")
        page._profile.get_profile_setup.side_effect = AssertionError("profile setup must load in worker")
        page._profile_payload_dirty = False
        page._cleanup_in_progress = False
        page._profile_item_refresh_runtime = Mock()
        page._profile_item_refresh_runtime.start_qthread_worker.return_value = (1, Mock())
        page._schedule_profiles_payload_request = Mock()

        PresetSetupPageBase._sync_profile_list_locally(page)
        PresetSetupPageBase._refresh_profile_item_locally(page, "profile-1", "profile-1")
        PresetSetupPageBase._add_profile_item_locally(page, "profile-1")

        page._profile.list_profiles.assert_not_called()
        page._profile.get_profile_setup.assert_not_called()
        self.assertTrue(page._profile_payload_dirty)
        self.assertEqual(
            page._schedule_profiles_payload_request.call_args_list,
            [call(force=True), call(force=True)],
        )
        page._profile_item_refresh_runtime.start_qthread_worker.assert_called_once()

    def test_profile_item_refresh_loads_one_item_through_worker_without_full_reload(self) -> None:
        class _Signal:
            def __init__(self) -> None:
                self.callbacks = []

            def connect(self, callback) -> None:
                self.callbacks.append(callback)

        worker = SimpleNamespace(refreshed=_Signal(), failed=_Signal())

        def _start_worker(*, worker_factory, bind_worker, **_kwargs):
            created = worker_factory(12)
            bind_worker(created)
            return 12, created

        item = SimpleNamespace(key="profile-1")
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._cleanup_in_progress = False
        page._profile_payload_dirty = False
        page._profile_item_refresh_runtime = SimpleNamespace(
            start_qthread_worker=Mock(side_effect=_start_worker),
        )
        page._create_profile_item_refresh_worker = Mock(return_value=worker)
        page._replace_profile_item_locally = Mock(return_value=True)
        page._schedule_profiles_payload_request = Mock()

        PresetSetupPageBase._refresh_profile_item_locally(page, "profile-1", "profile-1")
        PresetSetupPageBase._on_profile_item_refreshed(page, 12, "profile-1", "profile-1", item)

        page._create_profile_item_refresh_worker.assert_called_once_with(
            12,
            page.launch_method,
            old_profile_key="profile-1",
            profile_key="profile-1",
            parent=page,
        )
        page._replace_profile_item_locally.assert_called_once_with("profile-1", item)
        page._schedule_profiles_payload_request.assert_not_called()
        self.assertTrue(page._profile_payload_dirty)

    def test_profile_enabled_finish_updates_existing_row_without_full_reload(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_context_action_request_id = 3
        page._profile_payload_dirty = False
        page._profiles_list = Mock()
        page._profiles_list.set_profile_enabled.return_value = True
        page.refresh_from_preset_switch = Mock()
        page._schedule_profiles_payload_request = Mock()

        PresetSetupPageBase._on_profile_context_action_finished(
            page,
            3,
            "set_enabled",
            "profile-1",
            "profile-1",
        )

        page._profiles_list.set_profile_enabled.assert_called_once_with("profile-1", True)
        page.refresh_from_preset_switch.assert_not_called()
        page._schedule_profiles_payload_request.assert_not_called()
        self.assertTrue(page._profile_payload_dirty)

    def test_profile_enabled_finish_adds_created_row_without_full_reload(self) -> None:
        created_item = ProfileListItem(
            key="profile-2",
            persistent_key="profile-2",
            profile_index=2,
            display_name="YouTube",
            enabled=True,
            in_preset=True,
            strategy_id="strategy",
            strategy_name="Strategy",
            match_lines=("--filter-tcp=443",),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="common",
            group_name="",
            order=2,
        )
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_context_action_request_id = 6
        page._profile_payload_dirty = False
        page._profiles_list = Mock()
        page._profiles_list.set_profile_enabled.return_value = False
        page._profiles_list.add_profile_item.return_value = True
        page.refresh_from_preset_switch = Mock()
        page._schedule_profiles_payload_request = Mock()

        PresetSetupPageBase._on_profile_context_action_finished(
            page,
            6,
            "set_enabled",
            "template:youtube",
            {"profile_key": "profile-2", "profile_item": created_item},
        )

        page._profiles_list.set_profile_enabled.assert_not_called()
        page._profiles_list.add_profile_item.assert_called_once_with(created_item)
        page.refresh_from_preset_switch.assert_not_called()
        page._schedule_profiles_payload_request.assert_not_called()
        self.assertTrue(page._profile_payload_dirty)

    def test_profile_delete_finish_removes_existing_row_without_full_reload(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_context_action_request_id = 4
        page._profile_payload_dirty = False
        page._profiles_list = Mock()
        page._profiles_list.remove_profile_item.return_value = True
        page.refresh_from_preset_switch = Mock()
        page._schedule_profiles_payload_request = Mock()

        PresetSetupPageBase._on_profile_context_action_finished(
            page,
            4,
            "delete",
            "profile-1",
            True,
        )

        page._profiles_list.remove_profile_item.assert_called_once_with("profile-1")
        page.refresh_from_preset_switch.assert_not_called()
        page._schedule_profiles_payload_request.assert_not_called()
        self.assertTrue(page._profile_payload_dirty)

    def test_profile_duplicate_finish_adds_row_without_full_reload(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_context_action_request_id = 5
        page._profile_payload_dirty = False
        page._profiles_list = Mock()
        page._profiles_list.duplicate_profile_item.return_value = True
        page.refresh_from_preset_switch = Mock()
        page._schedule_profiles_payload_request = Mock()

        PresetSetupPageBase._on_profile_context_action_finished(
            page,
            5,
            "duplicate",
            "profile-1",
            "profile-2",
        )

        page._profiles_list.duplicate_profile_item.assert_called_once_with("profile-1", "profile-2")
        page.refresh_from_preset_switch.assert_not_called()
        page._schedule_profiles_payload_request.assert_not_called()
        self.assertTrue(page._profile_payload_dirty)

    def test_profile_duplicate_finish_adds_worker_item_without_full_reload(self) -> None:
        duplicated_item = ProfileListItem(
            key="profile-2",
            persistent_key="profile-2",
            profile_index=2,
            display_name="YouTube Copy",
            enabled=True,
            in_preset=True,
            strategy_id="strategy",
            strategy_name="Strategy",
            match_lines=("--filter-tcp=443",),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="common",
            group_name="",
            order=2,
        )
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_context_action_request_id = 8
        page._profile_payload_dirty = False
        page._profiles_list = Mock()
        page._profiles_list.add_profile_item.return_value = True
        page.refresh_from_preset_switch = Mock()
        page._schedule_profiles_payload_request = Mock()

        PresetSetupPageBase._on_profile_context_action_finished(
            page,
            8,
            "duplicate",
            "profile-1",
            {"profile_key": "profile-2", "profile_item": duplicated_item},
        )

        page._profiles_list.duplicate_profile_item.assert_not_called()
        page._profiles_list.add_profile_item.assert_called_once_with(duplicated_item)
        page.refresh_from_preset_switch.assert_not_called()
        page._schedule_profiles_payload_request.assert_not_called()
        self.assertTrue(page._profile_payload_dirty)

    def test_profile_context_action_result_applies_enabled_locally_when_new_action_is_pending(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_context_action_request_id = 3
        page._profile_payload_dirty = False
        page._pending_profile_preset_write_operations = [
            {
                "kind": "context",
                "action": "set_enabled",
                "profile_key": "profile-1",
                "enabled": False,
                "source_profile_key": "",
                "destination_profile_key": "",
                "destination_group_key": "",
            }
        ]
        page._pending_profile_context_actions = [
            {"action": "set_enabled", "profile_key": "profile-1", "enabled": False}
        ]
        page._pending_profile_moves = []
        page._pending_user_profile_operations = []
        page._profile_context_action_enabled_by_request = {3: True}
        page._apply_profile_enabled_locally = Mock()
        page._add_created_user_profile_locally = Mock()
        page._refresh_profile_item_locally = Mock()

        PresetSetupPageBase._on_profile_context_action_finished(
            page,
            3,
            "set_enabled",
            "profile-1",
            "profile-1",
        )

        page._apply_profile_enabled_locally.assert_called_once_with("profile-1", True)
        page._add_created_user_profile_locally.assert_not_called()
        page._refresh_profile_item_locally.assert_not_called()
        self.assertTrue(page._profile_payload_dirty)
        self.assertNotIn(3, page._profile_context_action_enabled_by_request)

    def test_profile_context_actions_start_worker_without_direct_profile_calls(self) -> None:
        class _Signal:
            def __init__(self) -> None:
                self.callbacks = []

            def connect(self, callback) -> None:
                self.callbacks.append(callback)

        class _Worker:
            def __init__(self) -> None:
                self.finished_action = _Signal()
                self.failed = _Signal()
                self.finished = _Signal()
                self.start = Mock()
                self.deleteLater = Mock()

            def isRunning(self) -> bool:
                return False

        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page.launch_method = "zapret2_mode"
        page._profile = Mock()
        page._profile.set_profile_enabled.side_effect = AssertionError("enable must run in worker")
        page._profile.duplicate_profile.side_effect = AssertionError("duplicate must run in worker")
        page._profile.delete_profile.side_effect = AssertionError("delete must run in worker")
        page._profile_context_action_request_id = 0
        worker = _Worker()
        page._create_profile_context_action_worker = Mock(return_value=worker)

        PresetSetupPageBase._request_profile_context_action(
            page,
            "set_enabled",
            "profile-1",
            enabled=True,
        )

        page._profile.set_profile_enabled.assert_not_called()
        page._profile.duplicate_profile.assert_not_called()
        page._profile.delete_profile.assert_not_called()
        page._create_profile_context_action_worker.assert_called_once_with(
            1,
            "zapret2_mode",
            action="set_enabled",
            profile_key="profile-1",
            enabled=True,
            parent=page,
        )
        worker.start.assert_called_once()

    def test_profile_context_action_worker_emits_result(self) -> None:
        set_profile_enabled = Mock(return_value="profile-2")
        duplicate_profile = Mock()
        delete_profile = Mock()
        load_profile_item = Mock(return_value=None)
        worker = ProfilePresetProfileActionWorker(
            6,
            set_profile_enabled,
            duplicate_profile,
            delete_profile,
            load_profile_item,
            action="set_enabled",
            profile_key="profile-1",
            enabled=True,
        )
        finished = []

        worker.finished_action.connect(
            lambda request_id, action, profile_key, result: finished.append((
                request_id,
                action,
                profile_key,
                result,
            ))
        )

        worker.run()

        set_profile_enabled.assert_called_once_with("profile-1", True)
        self.assertEqual(finished, [(6, "set_enabled", "profile-1", "profile-2")])

    def test_profile_context_action_worker_emits_duplicated_item(self) -> None:
        duplicated_item = ProfileListItem(
            key="profile-2",
            persistent_key="profile-2",
            profile_index=2,
            display_name="YouTube Copy",
            enabled=True,
            in_preset=True,
            strategy_id="strategy",
            strategy_name="Strategy",
            match_lines=("--filter-tcp=443",),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="common",
            group_name="",
            order=2,
        )
        set_profile_enabled = Mock()
        duplicate_profile = Mock(return_value="profile-2")
        delete_profile = Mock()
        load_profile_item = Mock(return_value=duplicated_item)
        worker = ProfilePresetProfileActionWorker(
            8,
            set_profile_enabled,
            duplicate_profile,
            delete_profile,
            load_profile_item,
            action="duplicate",
            profile_key="profile-1",
        )
        finished = []

        worker.finished_action.connect(
            lambda request_id, action, profile_key, result: finished.append((
                request_id,
                action,
                profile_key,
                result,
            ))
        )

        worker.run()

        duplicate_profile.assert_called_once_with("profile-1")
        load_profile_item.assert_called_once_with("profile-2")
        self.assertEqual(finished[0][:3], (8, "duplicate", "profile-1"))
        self.assertEqual(finished[0][3], {"profile_key": "profile-2", "profile_item": duplicated_item})

    def test_profile_context_action_worker_emits_created_item_for_new_enabled_profile(self) -> None:
        created_item = ProfileListItem(
            key="profile-2",
            persistent_key="profile-2",
            profile_index=2,
            display_name="YouTube",
            enabled=True,
            in_preset=True,
            strategy_id="strategy",
            strategy_name="Strategy",
            match_lines=("--filter-tcp=443",),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="common",
            group_name="",
            order=2,
        )
        set_profile_enabled = Mock(return_value="profile-2")
        duplicate_profile = Mock()
        delete_profile = Mock()
        load_profile_item = Mock(return_value=created_item)
        worker = ProfilePresetProfileActionWorker(
            7,
            set_profile_enabled,
            duplicate_profile,
            delete_profile,
            load_profile_item,
            action="set_enabled",
            profile_key="template:youtube",
            enabled=True,
        )
        finished = []

        worker.finished_action.connect(
            lambda request_id, action, profile_key, result: finished.append((
                request_id,
                action,
                profile_key,
                result,
            ))
        )

        worker.run()

        set_profile_enabled.assert_called_once_with("template:youtube", True)
        load_profile_item.assert_called_once_with("profile-2")
        self.assertEqual(finished[0][:3], (7, "set_enabled", "template:youtube"))
        self.assertEqual(finished[0][3], {"profile_key": "profile-2", "profile_item": created_item})

    def test_strategy_list_repaints_viewport_rect_after_current_strategy_changes(self) -> None:
        source = inspect.getsource(ProfileStrategyListWidget.set_current_strategy_id)
        helper_source = inspect.getsource(ProfileStrategyListWidget._refresh_strategy_item)

        self.assertIn("_refresh_strategy_item", source)
        self.assertIn("viewport().update", helper_source)
        self.assertNotIn("_list.update(self._list.visualItemRect", helper_source)

    def test_strategy_list_updates_current_rows_by_id_without_full_scan(self) -> None:
        init_source = inspect.getsource(ProfileStrategyListWidget.__init__)
        rebuild_source = inspect.getsource(ProfileStrategyListWidget._rebuild_tree)
        source = inspect.getsource(ProfileStrategyListWidget.set_current_strategy_id)

        self.assertIn("_item_by_strategy_id", init_source)
        self.assertIn("_item_by_strategy_id.clear()", rebuild_source)
        self.assertIn("_item_by_strategy_id[strategy_id] = item", rebuild_source)
        self.assertNotIn("for row in range", source)

    def test_strategy_list_skips_rebuild_when_rows_are_unchanged(self) -> None:
        widget = ProfileStrategyListWidget.__new__(ProfileStrategyListWidget)
        widget._entries = {}
        widget._states = {}
        widget._current_strategy_id = "none"
        widget._rebuild_tree = Mock()
        widget.set_current_strategy_id = Mock()
        entries = {
            "fake": SimpleNamespace(
                name="Fake",
                args="--lua-desync=fake",
                visual=SimpleNamespace(icon_name="bolt", color="#fff", label="Fake", description="Fake TLS"),
            )
        }
        states = {"fake": ProfileStrategyState(rating="work", favorite=False)}

        ProfileStrategyListWidget.set_rows(
            widget,
            entries=entries,
            states=states,
            current_strategy_id="fake",
        )
        ProfileStrategyListWidget.set_rows(
            widget,
            entries=dict(entries),
            states=dict(states),
            current_strategy_id="fake",
        )

        widget._rebuild_tree.assert_called_once()
        widget.set_current_strategy_id.assert_not_called()

    def test_strategy_list_initial_rows_start_worker_without_search_delay(self) -> None:
        from ui.latest_value_worker_state import LatestValueWorkerState

        widget = ProfileStrategyListWidget.__new__(ProfileStrategyListWidget)
        widget._entries = {}
        widget._states = {}
        widget._current_strategy_id = "none"
        widget._item_by_strategy_id = {}
        widget._rows_signature = None
        widget._strategy_filter_runtime = SimpleNamespace(is_running=Mock(return_value=False))
        widget._strategy_filter_state = LatestValueWorkerState(widget._strategy_filter_runtime, empty_value=None)
        widget._strategy_filter_timer = SimpleNamespace(start=Mock())
        widget._search = SimpleNamespace(text=Mock(return_value=""))
        widget._run_debounced_tree_rebuild = Mock()
        entries = {
            "fake": SimpleNamespace(
                name="Fake",
                args="--lua-desync=fake",
                visual=SimpleNamespace(icon_name="bolt", color="#fff", label="Fake", description="Fake TLS"),
            )
        }

        ProfileStrategyListWidget.set_rows(
            widget,
            entries=entries,
            states={},
            current_strategy_id="fake",
        )

        widget._strategy_filter_timer.start.assert_not_called()
        widget._run_debounced_tree_rebuild.assert_called_once()
        self.assertEqual(widget._strategy_filter_state.pending[2:], ("fake", ""))

    def test_strategy_list_search_rebuild_is_debounced_through_worker(self) -> None:
        from ui.latest_value_worker_state import LatestValueWorkerState

        widget = ProfileStrategyListWidget.__new__(ProfileStrategyListWidget)
        widget._entries = {
            "fake": SimpleNamespace(
                name="Fake",
                args="--lua-desync=fake",
                visual=SimpleNamespace(icon_name="bolt", color="#fff", label="Fake", description="Fake TLS"),
            )
        }
        widget._states = {"fake": ProfileStrategyState(rating="work", favorite=False)}
        widget._current_strategy_id = "fake"
        widget._strategy_filter_runtime = SimpleNamespace(is_running=Mock(return_value=False))
        widget._strategy_filter_state = LatestValueWorkerState(widget._strategy_filter_runtime, empty_value=None)
        widget._strategy_filter_timer = SimpleNamespace(start=Mock())
        widget._search = SimpleNamespace(text=Mock(return_value="fake"))
        widget._rebuild_tree = Mock(side_effect=AssertionError("search must not rebuild rows in GUI thread"))

        ProfileStrategyListWidget._apply_filter(widget)

        widget._strategy_filter_timer.start.assert_called_once_with(120)
        widget._rebuild_tree.assert_not_called()
        self.assertEqual(widget._strategy_filter_state.pending[2:], ("fake", "fake"))

    def test_strategy_list_filter_worker_builds_rows_without_widgets(self) -> None:
        entries = {
            "fake": SimpleNamespace(
                name="Fake TLS",
                args="--lua-desync=fake",
                visual=SimpleNamespace(icon_name="bolt", color="#fff", label="Fake", description="Fake TLS"),
            ),
            "udp": SimpleNamespace(
                name="UDP",
                args="--filter-udp=443",
                visual=SimpleNamespace(icon_name="wifi", color="#0ff", label="UDP", description="UDP mode"),
            ),
        }
        states = {
            "fake": ProfileStrategyState(rating="work", favorite=True),
            "udp": ProfileStrategyState(rating="", favorite=False),
        }

        plan = build_profile_strategy_list_plan(
            entries=entries,
            states=states,
            current_strategy_id="fake",
            search_text="tls",
        )

        self.assertEqual(plan.visible_count, 1)
        self.assertEqual(plan.total_count, 2)
        self.assertEqual(plan.rows[0].strategy_id, "fake")
        self.assertEqual(plan.rows[0].status_text, "Выбрана • В избранном • Работает")
        self.assertEqual(
            plan.rows[0].accessible_text,
            "Fake TLS, выбрана, в избранном, работает, Fake, Fake TLS. "
            "Нажмите Enter или Пробел, чтобы выбрать стратегию.",
        )

    def test_strategy_list_filter_worker_emits_latest_plan(self) -> None:
        loaded = []
        failed = []
        worker = ProfileStrategyListFilterWorker(
            4,
            entries={
                "fake": SimpleNamespace(
                    name="Fake",
                    args="--lua-desync=fake",
                    visual=SimpleNamespace(icon_name="bolt", color="#fff", label="Fake", description="Fake TLS"),
                )
            },
            states={"fake": ProfileStrategyState(rating="", favorite=False)},
            current_strategy_id="fake",
            search_text="fake",
        )
        worker.loaded.connect(lambda request_id, plan: loaded.append((request_id, plan)))
        worker.failed.connect(lambda request_id, error: failed.append((request_id, error)))

        worker.run()

        self.assertEqual(failed, [])
        self.assertEqual(loaded[0][0], 4)
        self.assertEqual(loaded[0][1].rows[0].strategy_id, "fake")

    def test_strategy_list_updates_state_rows_without_rebuild_when_order_is_stable(self) -> None:
        widget = ProfileStrategyListWidget.__new__(ProfileStrategyListWidget)
        strategy_item = object()
        entries = {
            "fake": SimpleNamespace(
                name="Fake",
                args="--lua-desync=fake",
                visual=SimpleNamespace(icon_name="bolt", color="#fff", label="Fake", description="Fake TLS"),
            )
        }
        widget._entries = dict(entries)
        widget._states = {"fake": ProfileStrategyState(rating="", favorite=False)}
        widget._current_strategy_id = "fake"
        widget._rows_signature = (("entry",), ("old-state",))
        widget._item_by_strategy_id = {"fake": strategy_item}
        widget._rebuild_tree = Mock(side_effect=AssertionError("strategy feedback must not rebuild the whole list"))
        widget._refresh_strategy_item = Mock()

        ProfileStrategyListWidget.set_rows(
            widget,
            entries=dict(entries),
            states={"fake": ProfileStrategyState(rating="work", favorite=False)},
            current_strategy_id="fake",
        )

        widget._rebuild_tree.assert_not_called()
        widget._refresh_strategy_item.assert_called_once_with(strategy_item, "fake", is_current=True)

    def test_strategy_list_moves_favorite_row_without_rebuild_when_order_changes(self) -> None:
        class _FakeList:
            def __init__(self, items):
                self.items = list(items)

            def row(self, item):
                return self.items.index(item)

            def takeItem(self, row):  # noqa: N802
                return self.items.pop(row)

            def insertItem(self, row, item):  # noqa: N802
                self.items.insert(row, item)

        widget = ProfileStrategyListWidget.__new__(ProfileStrategyListWidget)
        first_item = object()
        second_item = object()
        entries = {
            "first": SimpleNamespace(
                name="Alpha",
                args="--lua-desync=fake",
                visual=SimpleNamespace(icon_name="bolt", color="#fff", label="Alpha", description="Alpha TLS"),
            ),
            "second": SimpleNamespace(
                name="Beta",
                args="--lua-desync=fake",
                visual=SimpleNamespace(icon_name="bolt", color="#fff", label="Beta", description="Beta TLS"),
            ),
        }
        fake_list = _FakeList([first_item, second_item])
        widget._entries = dict(entries)
        widget._states = {
            "first": ProfileStrategyState(rating="", favorite=False),
            "second": ProfileStrategyState(rating="", favorite=False),
        }
        widget._current_strategy_id = "second"
        widget._rows_signature = (("entry",), ("old-state",))
        widget._item_by_strategy_id = {"first": first_item, "second": second_item}
        widget._list = fake_list
        widget._rebuild_tree = Mock(side_effect=AssertionError("favorite move must not rebuild the whole list"))
        widget._refresh_strategy_item = Mock()

        ProfileStrategyListWidget.set_rows(
            widget,
            entries=dict(entries),
            states={
                "first": ProfileStrategyState(rating="", favorite=False),
                "second": ProfileStrategyState(rating="", favorite=True),
            },
            current_strategy_id="second",
        )

        widget._rebuild_tree.assert_not_called()
        self.assertEqual(fake_list.items, [second_item, first_item])
        widget._refresh_strategy_item.assert_called_once_with(second_item, "second", is_current=True)

    def test_strategy_change_refreshes_only_changed_profile_row(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._refresh_profile_item_locally = Mock()
        page.refresh_from_preset_switch = Mock()

        PresetSetupPageBase.apply_profile_setup_change(page, "profile-1", "strategy")

        page._refresh_profile_item_locally.assert_called_once_with("profile-1", "profile-1")
        page.refresh_from_preset_switch.assert_not_called()

    def test_profile_setup_change_with_ready_item_replaces_visible_row_without_worker_refresh(self) -> None:
        item = SimpleNamespace(key="profile-1")
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._replace_profile_item_locally = Mock(return_value=True)
        page._refresh_profile_item_locally = Mock()
        page.refresh_from_preset_switch = Mock()

        PresetSetupPageBase.apply_profile_setup_change(page, "profile-1", "strategy", item)

        page._replace_profile_item_locally.assert_called_once_with("profile-1", item)
        page._refresh_profile_item_locally.assert_not_called()
        page.refresh_from_preset_switch.assert_not_called()

    def test_profile_setup_change_with_ready_item_clears_deferred_payload(self) -> None:
        item = SimpleNamespace(key="profile-1")
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._deferred_profile_payload_apply = (object(), None, None)
        page._replace_profile_item_locally = Mock(return_value=True)
        page._refresh_profile_item_locally = Mock()
        page.refresh_from_preset_switch = Mock()

        PresetSetupPageBase.apply_profile_setup_change(page, "profile-1", "strategy", item)

        self.assertIsNone(page._deferred_profile_payload_apply)

    def test_local_profile_list_mutations_clear_deferred_payload(self) -> None:
        class ProfilesList:
            def add_profile_item(self, _item) -> bool:
                return True

            def replace_user_profile_items(self, _profile_id, _items) -> bool:
                return True

            def remove_user_profile_items(self, _profile_id) -> bool:
                return True

            def apply_profile_folder_state(self, _state) -> bool:
                return True

            def move_profile_item(self, *_args) -> bool:
                return True

        cases = (
            (
                "_add_created_user_profile_locally",
                lambda page: PresetSetupPageBase._add_created_user_profile_locally(
                    page,
                    SimpleNamespace(key="profile-1"),
                ),
            ),
            (
                "_replace_user_profile_items_locally",
                lambda page: PresetSetupPageBase._replace_user_profile_items_locally(
                    page,
                    "user-1",
                    (SimpleNamespace(key="profile-1"),),
                ),
            ),
            (
                "_remove_user_profile_items_locally",
                lambda page: PresetSetupPageBase._remove_user_profile_items_locally(page, "user-1"),
            ),
            (
                "_apply_profile_folder_state_locally",
                lambda page: PresetSetupPageBase._apply_profile_folder_state_locally(page, {"folder": True}),
            ),
            (
                "_apply_profile_move_locally",
                lambda page: PresetSetupPageBase._apply_profile_move_locally(
                    page,
                    "before",
                    "profile-1",
                    destination_profile_key="profile-2",
                ),
            ),
        )

        for name, mutate in cases:
            with self.subTest(name=name):
                page = PresetSetupPageBase.__new__(PresetSetupPageBase)
                page._profiles_list = ProfilesList()
                page._deferred_profile_payload_apply = (object(), None, None)
                page._profile_payload_dirty = False

                self.assertTrue(mutate(page))

                self.assertIsNone(page._deferred_profile_payload_apply)

    def test_enabled_change_refreshes_only_changed_profile_row(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._apply_profile_enabled_locally = Mock(return_value=True)
        page.refresh_from_preset_switch = Mock()

        PresetSetupPageBase.apply_profile_setup_change(page, "profile-1", "disabled")

        page._apply_profile_enabled_locally.assert_called_once_with("profile-1", False)
        page.refresh_from_preset_switch.assert_not_called()

    def test_profile_editor_changes_refresh_only_changed_profile_row(self) -> None:
        for change_kind in ("settings", "raw_profile", "list_file"):
            with self.subTest(change_kind=change_kind):
                page = PresetSetupPageBase.__new__(PresetSetupPageBase)
                page._refresh_profile_item_locally = Mock()
                page.refresh_from_preset_switch = Mock()

                PresetSetupPageBase.apply_profile_setup_change(page, "profile-1", change_kind)

                page._refresh_profile_item_locally.assert_called_once_with("profile-1", "profile-1")
                page.refresh_from_preset_switch.assert_not_called()

    def test_user_profile_detail_changes_update_visible_list_locally(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._refresh_profile_item_locally = Mock()
        page._remove_profile_item_locally = Mock()
        page.refresh_from_preset_switch = Mock()

        PresetSetupPageBase.apply_profile_setup_change(page, "profile-1", "user_profile_updated")
        PresetSetupPageBase.apply_profile_setup_change(page, "profile-2", "user_profile_deleted")

        page._refresh_profile_item_locally.assert_called_once_with("profile-1", "profile-1")
        page._remove_profile_item_locally.assert_called_once_with("profile-2")
        page.refresh_from_preset_switch.assert_not_called()

    def test_profile_setup_shell_has_search_input_for_all_profiles(self) -> None:
        build_content = inspect.getsource(PresetSetupPageBase._build_content)
        apply_payload = inspect.getsource(PresetSetupPageBase._apply_payload)
        shell_builder = inspect.getsource(build_profile_shell)

        self.assertIn("profile_search_input", shell_builder)
        self.assertIn("on_profile_search_text_changed", shell_builder)
        self.assertIn("Поиск профиля по имени, портам и т.д.", shell_builder)
        self.assertIn("set_search_query", apply_payload)
        self.assertIn("on_profile_search_text_changed=self._on_profile_search_text_changed", build_content)

    def test_preset_setup_shell_has_separate_preset_order_button(self) -> None:
        init_source = inspect.getsource(PresetSetupPageBase.__init__)
        build_content = inspect.getsource(PresetSetupPageBase._build_content)
        shell_builder = inspect.getsource(build_profile_shell)

        self.assertIn("open_profile_order", init_source)
        self.assertIn("on_open_profile_order=self._open_profile_order", build_content)
        self.assertIn("Порядок в пресете", shell_builder)
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
        schedule_source = inspect.getsource(ProfilePayloadController._schedule_profiles_payload_request)
        run_source = inspect.getsource(ProfilePayloadController._run_scheduled_profiles_payload_request)

        self.assertIn("_schedule_profiles_payload_request", activated_source)
        self.assertNotIn("_request_profiles_payload()", activated_source)
        self.assertIn("QTimer.singleShot", schedule_source)
        self.assertIn("_run_scheduled_profiles_payload_request", schedule_source)
        self.assertIn("_request_profiles_payload", run_source)

    def test_preset_setup_coalesces_queued_profile_refresh_requests(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._request_profiles_payload = Mock()
        callbacks = []

        with patch(
            "profile.ui.preset_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            PresetSetupPageBase._schedule_profiles_payload_request(page)
            PresetSetupPageBase._schedule_profiles_payload_request(page, force=True)
            PresetSetupPageBase._schedule_profiles_payload_request(page)

        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page._request_profiles_payload.assert_called_once_with(force=True)
        self.assertFalse(page._profile_payload_request_scheduled)

    def test_loaded_profile_payload_apply_is_deferred_after_worker_signal(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_load_request_id = 7
        page._cleanup_in_progress = False
        page._profile_payload_loaded_once = False
        page._profile_payload_dirty = True
        page._apply_payload = Mock()
        payload = SimpleNamespace(items=(), selected_preset_name="Default")
        callbacks = []

        with patch(
            "profile.ui.preset_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            PresetSetupPageBase._on_profile_payload_loaded(page, 7, payload)

        page._apply_payload.assert_not_called()
        self.assertEqual(len(callbacks), 1)
        self.assertTrue(page._profile_payload_loaded_once)
        self.assertFalse(page._profile_payload_dirty)

        callbacks[0]()

        page._apply_payload.assert_called_once_with(payload, view_state=None, apply_signature_base=None)

    def test_loaded_profile_payload_passes_worker_signature_to_apply(self) -> None:
        from profile.profile_list_loader import ProfileListLoadResult

        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_load_request_id = 7
        page._cleanup_in_progress = False
        page._profile_payload_loaded_once = False
        page._profile_payload_dirty = True
        page._schedule_profile_payload_apply = Mock()
        payload = SimpleNamespace(items=(), selected_preset_file_name="Default.txt")
        result = ProfileListLoadResult(payload=payload, view_state="state")

        PresetSetupPageBase._on_profile_payload_loaded(page, 7, result)

        page._schedule_profile_payload_apply.assert_called_once_with(
            payload,
            view_state="state",
            apply_signature_base=result.apply_signature_base,
        )

    def test_loaded_profile_payload_apply_coalesces_latest_payload(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_load_request_id = 8
        page._cleanup_in_progress = False
        page._profile_payload_loaded_once = False
        page._profile_payload_dirty = True
        page._apply_payload = Mock()
        first_payload = SimpleNamespace(items=(), selected_preset_name="First")
        second_payload = SimpleNamespace(items=(), selected_preset_name="Second")
        callbacks = []

        with patch(
            "profile.ui.preset_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            PresetSetupPageBase._on_profile_payload_loaded(page, 8, first_payload)
            PresetSetupPageBase._on_profile_payload_loaded(page, 8, second_payload)

        self.assertEqual(len(callbacks), 1)
        page._apply_payload.assert_not_called()

        callbacks[0]()

        page._apply_payload.assert_called_once_with(second_payload, view_state=None, apply_signature_base=None)

    def test_profile_list_load_result_precomputes_apply_signature_base(self) -> None:
        from profile.profile_list_loader import ProfileListLoadResult

        payload = SimpleNamespace(
            items=("profile-1", "profile-2"),
            selected_preset_file_name="Default.txt",
            selected_preset_name="Default",
            normalized_split_profiles=1,
            normalized_created_profiles=2,
        )

        result = ProfileListLoadResult(payload=payload, view_state="state")

        self.assertEqual(
            result.apply_signature_base,
            (("profile-1", "profile-2"), "Default.txt", "Default", 1, 2, "state"),
        )

    def test_profile_list_load_result_signature_does_not_keep_profile_objects(self) -> None:
        from profile.profile_list_loader import ProfileListLoadResult

        item = SimpleNamespace(
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
        payload = SimpleNamespace(
            items=(item,),
            selected_preset_file_name="Default.txt",
            selected_preset_name="Default",
        )

        result = ProfileListLoadResult(payload=payload)

        self.assertIsNot(result.apply_signature_base[0][0], item)
        self.assertEqual(result.apply_signature_base[0][0][0], "profile:1")

    def test_pending_profile_payload_apply_is_ignored_after_refresh_is_requested(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_load_request_id = 8
        page._cleanup_in_progress = False
        page._profile_payload_loaded_once = False
        page._profile_payload_dirty = True
        page._profile_load_refresh_pending = False
        page._profile_payload_request_scheduled = False
        page._profile_payload_request_force = False
        page._apply_payload = Mock()
        page._request_profiles_payload = Mock()
        payload = SimpleNamespace(items=(), selected_preset_name="Old")
        callbacks = []

        with patch(
            "profile.ui.preset_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            PresetSetupPageBase._on_profile_payload_loaded(page, 8, payload)
            PresetSetupPageBase.refresh_from_preset_switch(page)

        self.assertEqual(len(callbacks), 2)
        self.assertTrue(page._profile_payload_request_scheduled)

        callbacks[0]()

        page._apply_payload.assert_not_called()

    def test_pending_profile_payload_apply_builds_hidden_list_without_showing_it(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_load_request_id = 8
        page._cleanup_in_progress = False
        page._profile_payload_loaded_once = False
        page._profile_payload_dirty = True
        page._profile_load_refresh_pending = False
        page._profile_payload_request_scheduled = False
        page.isVisible = Mock(return_value=False)
        page._apply_payload = Mock()
        page._schedule_profiles_list_show_after_page_switch = Mock(
            side_effect=AssertionError("hidden warmup must not show the list immediately")
        )
        page._hide_profiles_list_for_next_switch = Mock(
            side_effect=AssertionError("hidden warmup must not force a list relayout")
        )
        payload = SimpleNamespace(items=(), selected_preset_name="Old")
        callbacks = []

        with patch(
            "profile.ui.preset_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            PresetSetupPageBase._on_profile_payload_loaded(page, 8, payload)

        self.assertEqual(len(callbacks), 1)
        self.assertFalse(page._profile_payload_dirty)

        callbacks[0]()

        page._apply_payload.assert_called_once_with(payload, view_state=None, apply_signature_base=None)
        page._schedule_profiles_list_show_after_page_switch.assert_not_called()
        page._hide_profiles_list_for_next_switch.assert_not_called()
        self.assertFalse(page._profile_payload_dirty)
        self.assertIsNone(page._deferred_profile_payload_apply)

    def test_hidden_profile_payload_apply_builds_hidden_profile_list_for_warmup(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_load_request_id = 8
        page._cleanup_in_progress = False
        page._profile_payload_loaded_once = False
        page._profile_payload_dirty = True
        page._profile_load_refresh_pending = False
        page._profile_payload_request_scheduled = False
        page.isVisible = Mock(return_value=False)
        page._apply_payload = Mock()
        page._schedule_profiles_list_show_after_page_switch = Mock(
            side_effect=AssertionError("hidden warmup must not show the list immediately")
        )
        page._hide_profiles_list_for_next_switch = Mock(
            side_effect=AssertionError("hidden warmup must not force a list relayout")
        )
        payload = SimpleNamespace(items=(), selected_preset_name="Default")
        callbacks = []

        with patch(
            "profile.ui.preset_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            PresetSetupPageBase._on_profile_payload_loaded(page, 8, payload)

        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page._apply_payload.assert_called_once_with(payload, view_state=None, apply_signature_base=None)
        page._schedule_profiles_list_show_after_page_switch.assert_not_called()
        page._hide_profiles_list_for_next_switch.assert_not_called()
        self.assertIsNone(page._deferred_profile_payload_apply)
        self.assertFalse(page._profile_payload_dirty)

    def test_profile_list_ready_marker_marks_page_content_ready_without_visibility_toggle(self) -> None:
        profile_list = SimpleNamespace(setVisible=Mock())
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._cleanup_in_progress = False
        page._profiles_list = profile_list
        page._profiles_list_show_scheduled = True
        page.mark_content_ready = Mock()
        page.mark_content_ready_after_next_paint = Mock()

        PresetSetupPageBase._mark_profiles_list_ready_after_page_switch(page)

        profile_list.setVisible.assert_not_called()
        page.mark_content_ready.assert_called_once_with(
            stage="content.profiles_list.visible",
            extra="list=visible",
        )
        page.mark_content_ready_after_next_paint.assert_called_once_with(
            profile_list,
            stage="content.profiles_list.painted",
            extra="list=painted",
        )

    def test_hidden_warmed_profile_payload_is_applied_on_next_activation(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        state = SimpleNamespace(
            is_busy=Mock(return_value=False),
            has_pending=Mock(return_value=False),
        )
        payload = SimpleNamespace(items=(), selected_preset_name="Default")
        page._cleanup_in_progress = False
        page._profile_payload_loaded_once = True
        page._profile_payload_dirty = True
        page._profile_payload_request_scheduled = False
        page._deferred_profile_payload_apply = (payload, "view-state", ("signature",))
        page._profile_load_refresh_state_obj = Mock(return_value=state)
        page._apply_payload = Mock()
        page._schedule_profiles_list_show_after_page_switch = Mock()
        page._schedule_profiles_payload_request = Mock(
            side_effect=AssertionError("warmed hidden payload must be used before starting another worker")
        )

        PresetSetupPageBase.on_page_activated(page)

        page._apply_payload.assert_called_once_with(
            payload,
            view_state="view-state",
            apply_signature_base=("signature",),
        )
        page._schedule_profiles_payload_request.assert_not_called()
        page._schedule_profiles_list_show_after_page_switch.assert_called_once_with()
        self.assertIsNone(page._deferred_profile_payload_apply)
        self.assertTrue(page._profile_payload_loaded_once)
        self.assertFalse(page._profile_payload_dirty)

    def test_hidden_warmed_profile_payload_waits_when_refresh_is_busy_on_activation(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        state = SimpleNamespace(
            is_busy=Mock(return_value=True),
            has_pending=Mock(return_value=False),
        )
        page._cleanup_in_progress = False
        page._profile_payload_loaded_once = True
        page._profile_payload_dirty = False
        page._profile_payload_request_scheduled = False
        page._deferred_profile_payload_apply = (object(), "view-state", ("signature",))
        page._profile_load_refresh_state_obj = Mock(return_value=state)
        page._apply_payload = Mock()
        page._schedule_profiles_list_show_after_page_switch = Mock(
            side_effect=AssertionError("stale visible state must not be shown while refresh is busy")
        )
        page._schedule_profiles_payload_request = Mock(
            side_effect=AssertionError("busy refresh must finish before another request starts")
        )

        PresetSetupPageBase.on_page_activated(page)

        page._apply_payload.assert_not_called()
        page._schedule_profiles_list_show_after_page_switch.assert_not_called()
        page._schedule_profiles_payload_request.assert_not_called()
        self.assertIsNotNone(page._deferred_profile_payload_apply)
        self.assertFalse(page._profile_payload_dirty)

    def test_hidden_warmed_profile_payload_waits_when_newer_apply_is_scheduled(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        state = SimpleNamespace(
            is_busy=Mock(return_value=False),
            has_pending=Mock(return_value=False),
        )
        page._cleanup_in_progress = False
        page._profile_payload_loaded_once = True
        page._profile_payload_dirty = False
        page._profile_payload_request_scheduled = False
        page._profile_payload_apply_scheduled = True
        page._pending_profile_payload_apply = (object(), "new-view-state", ("new",))
        page._deferred_profile_payload_apply = (object(), "old-view-state", ("old",))
        page._profile_load_refresh_state_obj = Mock(return_value=state)
        page._apply_payload = Mock(
            side_effect=AssertionError("old deferred payload must wait for newer scheduled apply")
        )
        page._schedule_profiles_list_show_after_page_switch = Mock(
            side_effect=AssertionError("old deferred payload must not be shown before newer apply")
        )
        page._schedule_profiles_payload_request = Mock(
            side_effect=AssertionError("scheduled apply already owns the next visible list")
        )

        PresetSetupPageBase.on_page_activated(page)

        page._apply_payload.assert_not_called()
        page._schedule_profiles_list_show_after_page_switch.assert_not_called()
        page._schedule_profiles_payload_request.assert_not_called()
        self.assertIsNotNone(page._deferred_profile_payload_apply)
        self.assertFalse(page._profile_payload_dirty)

    def test_hidden_warmed_profile_payload_applies_after_busy_worker_finish_when_page_visible(self) -> None:
        from ui.latest_value_worker_state import LatestValueWorkerState

        runtime = SimpleNamespace(is_running=Mock(return_value=False))
        state = LatestValueWorkerState(runtime, empty_value=False)
        worker = SimpleNamespace(_request_id=9)
        payload = SimpleNamespace(items=(), selected_preset_name="Default")
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._cleanup_in_progress = False
        page._profile_payload_dirty = False
        page._profile_load_runtime_request_id = 9
        page._profile_load_refresh_state = state
        page._profile_load_runtime = runtime
        page._profile_payload_request_scheduled = False
        page._deferred_profile_payload_apply = (payload, "view-state", ("signature",))
        page.isVisible = Mock(return_value=True)
        page._apply_payload = Mock()
        page._schedule_profiles_list_show_after_page_switch = Mock()

        PresetSetupPageBase._on_profile_worker_finished(page, worker)

        page._apply_payload.assert_called_once_with(
            payload,
            view_state="view-state",
            apply_signature_base=("signature",),
        )
        page._schedule_profiles_list_show_after_page_switch.assert_called_once_with()
        self.assertIsNone(page._deferred_profile_payload_apply)
        self.assertTrue(page._profile_payload_loaded_once)
        self.assertFalse(page._profile_payload_dirty)

    def test_visible_profile_payload_apply_clears_older_deferred_payload(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        state = SimpleNamespace(has_pending=Mock(return_value=False))
        old_payload = SimpleNamespace(items=(), selected_preset_name="Old")
        new_payload = SimpleNamespace(items=(), selected_preset_name="New")
        page._cleanup_in_progress = False
        page._profile_payload_request_scheduled = False
        page._deferred_profile_payload_apply = (old_payload, "old-view", ("old",))
        page._pending_profile_payload_apply = (new_payload, "new-view", ("new",))
        page._profile_load_refresh_state_obj = Mock(return_value=state)
        page.isVisible = Mock(return_value=True)
        page._apply_payload = Mock()
        page._schedule_profiles_list_show_after_page_switch = Mock()

        PresetSetupPageBase._run_scheduled_profile_payload_apply(page)

        page._apply_payload.assert_called_once_with(
            new_payload,
            view_state="new-view",
            apply_signature_base=("new",),
        )
        page._schedule_profiles_list_show_after_page_switch.assert_called_once_with()
        self.assertIsNone(page._deferred_profile_payload_apply)

    def test_preset_setup_warmup_initial_load_starts_background_payload_request(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        state = SimpleNamespace(is_busy=Mock(return_value=False))
        page._cleanup_in_progress = False
        page._profile_payload_loaded_once = False
        page._profile_payload_dirty = True
        page._profile_load_refresh_state_obj = Mock(return_value=state)
        page._request_profiles_payload = Mock()

        self.assertTrue(PresetSetupPageBase.warmup_initial_load(page))

        page._request_profiles_payload.assert_called_once_with()

    def test_preset_setup_warmup_initial_load_keeps_deferred_payload(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        state = SimpleNamespace(is_busy=Mock(return_value=False))
        page._cleanup_in_progress = False
        page._profile_payload_loaded_once = True
        page._profile_payload_dirty = True
        page._deferred_profile_payload_apply = (object(), None, None)
        page._profile_load_refresh_state_obj = Mock(return_value=state)
        page._request_profiles_payload = Mock(
            side_effect=AssertionError("ready warmed payload must not be replaced by another warmup load")
        )

        self.assertFalse(PresetSetupPageBase.warmup_initial_load(page))

        page._request_profiles_payload.assert_not_called()

    def test_loaded_profile_payload_is_ignored_while_refresh_is_pending(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_load_request_id = 8
        page._cleanup_in_progress = False
        page._profile_payload_loaded_once = False
        page._profile_payload_dirty = True
        page._profile_load_refresh_pending = True
        page._schedule_profile_payload_apply = Mock(
            side_effect=AssertionError("pending newer profile list load must own the visible payload")
        )
        payload = SimpleNamespace(items=(), selected_preset_name="Old")

        PresetSetupPageBase._on_profile_payload_loaded(page, 8, payload)

        self.assertFalse(page._profile_payload_loaded_once)
        self.assertTrue(page._profile_payload_dirty)
        self.assertTrue(page._profile_load_refresh_pending)
        page._schedule_profile_payload_apply.assert_not_called()

    def test_failed_profile_payload_is_ignored_while_refresh_is_pending(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_load_request_id = 8
        page._cleanup_in_progress = False
        page._profile_payload_dirty = True
        page._profile_load_refresh_pending = True
        page._show_empty_state = Mock(
            side_effect=AssertionError("pending newer profile list load must own the error state")
        )

        PresetSetupPageBase._on_profile_payload_failed(page, 8, "boom")

        self.assertTrue(page._profile_payload_dirty)
        self.assertTrue(page._profile_load_refresh_pending)
        page._show_empty_state.assert_not_called()

    def test_failed_profile_payload_is_ignored_while_refresh_request_is_scheduled(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_load_request_id = 8
        page._cleanup_in_progress = False
        page._profile_payload_dirty = True
        page._profile_load_refresh_pending = False
        page._profile_payload_request_scheduled = True
        page._show_empty_state = Mock(
            side_effect=AssertionError("scheduled newer profile list load must own the error state")
        )

        PresetSetupPageBase._on_profile_payload_failed(page, 8, "boom")

        self.assertTrue(page._profile_payload_dirty)
        self.assertTrue(page._profile_payload_request_scheduled)
        page._show_empty_state.assert_not_called()

    def test_failed_profile_payload_load_is_not_retried_after_worker_finish(self) -> None:
        from ui.latest_value_worker_state import LatestValueWorkerState

        runtime = SimpleNamespace(is_running=Mock(return_value=False))
        state = LatestValueWorkerState(runtime, empty_value=False)
        worker = SimpleNamespace(_request_id=8)
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._cleanup_in_progress = False
        page._profile_load_request_id = 8
        page._profile_load_runtime_request_id = 8
        page._profile_load_refresh_state = state
        page._profile_load_runtime = runtime
        page._profile_payload_request_scheduled = False
        page._profile_payload_dirty = True
        page._profile_payload_load_failed = False
        page._deferred_profile_payload_apply = None
        page.isVisible = Mock(return_value=True)
        page._show_empty_state = Mock()
        page._schedule_profiles_list_show_after_page_switch = Mock()

        PresetSetupPageBase._on_profile_payload_failed(page, 8, "boom")
        PresetSetupPageBase._on_profile_worker_finished(page, worker)

        page._show_empty_state.assert_called_once()
        self.assertFalse(state.has_pending(), "failed load must not convert dirty into a pending retry")
        self.assertFalse(state.start_scheduled, "failed load must not schedule another load start")
        self.assertFalse(page._profile_payload_load_failed, "failure flag must be consumed by worker finish")
        self.assertTrue(page._profile_payload_dirty, "payload must stay dirty for the next explicit refresh")

    def test_dirty_profile_payload_without_failure_is_retried_after_worker_finish(self) -> None:
        from ui.latest_value_worker_state import LatestValueWorkerState

        runtime = SimpleNamespace(is_running=Mock(return_value=False))
        state = LatestValueWorkerState(runtime, empty_value=False)
        worker = SimpleNamespace(_request_id=8)
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._cleanup_in_progress = False
        page._profile_load_request_id = 8
        page._profile_load_runtime_request_id = 8
        page._profile_load_refresh_state = state
        page._profile_load_runtime = runtime
        page._profile_payload_request_scheduled = False
        page._profile_payload_dirty = True
        page._profile_payload_load_failed = False
        page._deferred_profile_payload_apply = None
        page.isVisible = Mock(return_value=True)
        page._schedule_profiles_list_show_after_page_switch = Mock()

        PresetSetupPageBase._on_profile_worker_finished(page, worker)

        self.assertTrue(
            state.start_scheduled or state.has_pending(),
            "dirty payload after a successful stale finish must schedule a refresh",
        )

    def test_preset_switch_refresh_schedules_profile_payload_request(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._schedule_profiles_payload_request = Mock()
        page._request_profiles_payload = Mock(side_effect=AssertionError("preset switch must not load immediately"))

        PresetSetupPageBase.refresh_from_preset_switch(page)

        page._schedule_profiles_payload_request.assert_called_once_with(force=True)
        page._request_profiles_payload.assert_not_called()

    def test_running_profile_payload_worker_coalesces_force_refresh_requests(self) -> None:
        runtime = SimpleNamespace(is_running=Mock(return_value=True))
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._cleanup_in_progress = False
        page._profile_payload_loaded_once = True
        page._profile_payload_dirty = False
        page._profile_load_runtime = runtime
        page._profile_load_request_id = 7
        page._profile_load_refresh_pending = False
        page._create_profile_list_load_worker = Mock(
            side_effect=AssertionError("running worker must not start another worker immediately")
        )

        PresetSetupPageBase._request_profiles_payload(page, force=True)
        PresetSetupPageBase._request_profiles_payload(page, force=True)

        self.assertEqual(page._profile_load_request_id, 8)
        self.assertTrue(page._profile_payload_dirty)
        self.assertTrue(page._profile_load_refresh_pending)
        page._create_profile_list_load_worker.assert_not_called()

    def test_profile_payload_worker_receives_current_view_state_options(self) -> None:
        class _Runtime:
            def is_running(self) -> bool:
                return False

            def start_qthread_worker(self, *, worker_factory, bind_worker, on_finished):
                worker = worker_factory(1)
                return 1, worker

        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._cleanup_in_progress = False
        page._profile_payload_loaded_once = False
        page._profile_payload_dirty = False
        page._profile_load_refresh_pending = False
        page._profile_load_request_id = 41
        page._profile_load_runtime = _Runtime()
        page._profile_search_query = "youtube"
        page.launch_method = "zapret2"
        page._profiles_list = SimpleNamespace(
            view_state_options=Mock(
                return_value={
                    "active_profile_types": {"tcp"},
                    "search_query": "youtube",
                    "group_expanded": {"video": False},
                }
            )
        )
        page._create_profile_list_load_worker = Mock(return_value=SimpleNamespace())

        PresetSetupPageBase._request_profiles_payload(page, force=True)

        page._profiles_list.view_state_options.assert_called_once()
        page._create_profile_list_load_worker.assert_called_once_with(
            42,
            "zapret2",
            page,
            view_state_options={
                "active_profile_types": {"tcp"},
                "search_query": "youtube",
                "group_expanded": {"video": False},
            },
        )

    def test_forced_profile_payload_request_clears_deferred_payload_before_start(self) -> None:
        class _Runtime:
            def is_running(self) -> bool:
                return False

            def start_qthread_worker(self, *, worker_factory, bind_worker, on_finished):
                worker = worker_factory(1)
                return 1, worker

        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._cleanup_in_progress = False
        page._profile_payload_loaded_once = True
        page._profile_payload_dirty = False
        page._profile_load_refresh_pending = False
        page._profile_load_request_id = 41
        page._profile_load_runtime = _Runtime()
        page._deferred_profile_payload_apply = (object(), None, None)
        page._profile_search_query = ""
        page.launch_method = "zapret2"
        page._profiles_list = SimpleNamespace(view_state_options=Mock(return_value={}))
        page._create_profile_list_load_worker = Mock(return_value=SimpleNamespace())

        PresetSetupPageBase._request_profiles_payload(page, force=True)

        self.assertIsNone(page._deferred_profile_payload_apply)

    def test_forced_profile_payload_request_drops_pending_apply_before_start(self) -> None:
        class _Runtime:
            def is_running(self) -> bool:
                return False

            def start_qthread_worker(self, *, worker_factory, bind_worker, on_finished):
                worker = worker_factory(1)
                return 1, worker

        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._cleanup_in_progress = False
        page._profile_payload_loaded_once = True
        page._profile_payload_dirty = False
        page._profile_load_refresh_pending = False
        page._profile_load_request_id = 41
        page._profile_load_runtime = _Runtime()
        page._pending_profile_payload_apply = (object(), None, None)
        page._profile_payload_apply_scheduled = True
        page._profile_search_query = ""
        page.launch_method = "zapret2"
        page._profiles_list = SimpleNamespace(view_state_options=Mock(return_value={}))
        page._create_profile_list_load_worker = Mock(return_value=SimpleNamespace())

        PresetSetupPageBase._request_profiles_payload(page, force=True)

        self.assertIsNone(page._pending_profile_payload_apply)
        self.assertTrue(page._profile_payload_apply_scheduled)

    def test_pending_running_profile_refresh_does_not_schedule_extra_timer(self) -> None:
        runtime = SimpleNamespace(is_running=Mock(return_value=True))
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_load_runtime = runtime
        page._profile_load_refresh_pending = True
        page._profile_payload_request_scheduled = False
        page._profile_payload_request_force = False
        page._profile_payload_dirty = False
        page._run_scheduled_profiles_payload_request = Mock(
            side_effect=AssertionError("pending running worker must not queue another timer")
        )

        with patch(
            "profile.ui.preset_setup_page.QTimer.singleShot",
            side_effect=AssertionError("pending running worker must not queue another timer"),
        ):
            PresetSetupPageBase._schedule_profiles_payload_request(page, force=True)

        self.assertTrue(page._profile_payload_dirty)
        self.assertFalse(page._profile_payload_request_scheduled)
        self.assertTrue(page._profile_load_refresh_pending)

    def test_pending_running_forced_profile_refresh_clears_deferred_payload(self) -> None:
        runtime = SimpleNamespace(is_running=Mock(return_value=True))
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_load_runtime = runtime
        page._profile_load_refresh_pending = True
        page._profile_payload_request_scheduled = False
        page._profile_payload_request_force = False
        page._profile_payload_dirty = False
        page._deferred_profile_payload_apply = (object(), None, None)
        page._run_scheduled_profiles_payload_request = Mock(
            side_effect=AssertionError("pending running worker must not queue another timer")
        )

        with patch(
            "profile.ui.preset_setup_page.QTimer.singleShot",
            side_effect=AssertionError("pending running worker must not queue another timer"),
        ):
            PresetSetupPageBase._schedule_profiles_payload_request(page, force=True)

        self.assertIsNone(page._deferred_profile_payload_apply)

    def test_pending_running_forced_profile_refresh_drops_pending_apply(self) -> None:
        runtime = SimpleNamespace(is_running=Mock(return_value=True))
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_load_runtime = runtime
        page._profile_load_refresh_pending = True
        page._profile_payload_request_scheduled = False
        page._profile_payload_request_force = False
        page._profile_payload_dirty = False
        page._pending_profile_payload_apply = (object(), None, None)
        page._profile_payload_apply_scheduled = True
        page._run_scheduled_profiles_payload_request = Mock(
            side_effect=AssertionError("pending running worker must not queue another timer")
        )

        with patch(
            "profile.ui.preset_setup_page.QTimer.singleShot",
            side_effect=AssertionError("pending running worker must not queue another timer"),
        ):
            PresetSetupPageBase._schedule_profiles_payload_request(page, force=True)

        self.assertIsNone(page._pending_profile_payload_apply)
        self.assertTrue(page._profile_payload_apply_scheduled)

    def test_preset_setup_content_state_change_schedules_profile_refresh(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._cleanup_in_progress = False
        page._profile_payload_dirty = False
        page.isVisible = Mock(return_value=True)
        page._schedule_profiles_payload_request = Mock()
        page._request_profiles_payload = Mock(side_effect=AssertionError("state signal must not load immediately"))

        PresetSetupPageBase._on_ui_state_changed(page, object(), frozenset({"preset_content_revision"}))

        self.assertTrue(page._profile_payload_dirty)
        page._schedule_profiles_payload_request.assert_called_once_with(force=True)
        page._request_profiles_payload.assert_not_called()

    def test_preset_setup_strategy_only_content_state_change_skips_full_profile_refresh(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._cleanup_in_progress = False
        page._profile_payload_dirty = False
        page.isVisible = Mock(return_value=True)
        page._schedule_profiles_payload_request = Mock(
            side_effect=AssertionError("strategy_only must not rebuild the full profile list")
        )
        page._request_profiles_payload = Mock(side_effect=AssertionError("state signal must not load immediately"))
        state = SimpleNamespace(preset_content_change_kind="strategy_only")

        PresetSetupPageBase._on_ui_state_changed(page, state, frozenset({"preset_content_revision"}))

        self.assertFalse(page._profile_payload_dirty)
        page._schedule_profiles_payload_request.assert_not_called()
        page._request_profiles_payload.assert_not_called()

    def test_preset_setup_active_preset_state_change_coalesces_profile_refresh(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._cleanup_in_progress = False
        page._profile_payload_dirty = False
        page.isVisible = Mock(return_value=True)
        page._schedule_profiles_payload_request = Mock()
        page._request_profiles_payload = Mock(side_effect=AssertionError("state signal must not load immediately"))
        callbacks = []

        with patch(
            "profile.ui.preset_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            PresetSetupPageBase._on_ui_state_changed(page, object(), frozenset({"active_preset_revision"}))
            PresetSetupPageBase._on_ui_state_changed(page, object(), frozenset({"active_preset_revision"}))

        self.assertTrue(page._profile_payload_dirty)
        page._schedule_profiles_payload_request.assert_not_called()
        page._request_profiles_payload.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page._schedule_profiles_payload_request.assert_called_once_with(force=True)

    def test_hidden_preset_setup_active_preset_change_preloads_profiles(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._cleanup_in_progress = False
        page._profile_payload_dirty = False
        page.isVisible = Mock(return_value=False)
        page._schedule_profiles_payload_request = Mock()
        callbacks = []

        with patch(
            "profile.ui.preset_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            PresetSetupPageBase._on_ui_state_changed(page, object(), frozenset({"active_preset_revision"}))

        self.assertTrue(page._profile_payload_dirty)
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page._schedule_profiles_payload_request.assert_called_once_with(force=True)

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
                self.deleteLater = Mock()

            def isRunning(self) -> bool:
                return False

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._user_profile_update_request_id = 0
        page._user_profile_update_worker = None
        page._update_user_profile_button = Mock()
        page._delete_user_profile_button = Mock()
        worker = _Worker()
        page.create_profile_user_update_worker = Mock(return_value=worker)

        ProfileSetupPageBase._request_user_profile_update(
            page,
            "user-1",
            name="YouTube",
            protocol="TCP",
            ports="443",
        )

        page.create_profile_user_update_worker.assert_called_once_with(
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

    def test_user_profile_update_queues_pending_requests_while_worker_runs(self) -> None:
        class _Signal:
            def __init__(self) -> None:
                self.callbacks = []

            def connect(self, callback) -> None:
                self.callbacks.append(callback)

        class _Worker:
            def __init__(self, *, running: bool) -> None:
                self._running = running
                self.updated = _Signal()
                self.failed = _Signal()
                self.finished = _Signal()
                self.start = Mock()
                self.deleteLater = Mock()

            def isRunning(self) -> bool:
                return self._running

        next_worker = _Worker(running=False)

        class _Runtime:
            def __init__(self) -> None:
                self.running = True

            def is_running(self) -> bool:
                return self.running

            def start_qthread_worker(self, *, worker_factory, **_kwargs):
                worker = worker_factory(0)
                worker.start()
                return 0, worker

        runtime = _Runtime()
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._user_profile_update_request_id = 1
        page._user_profile_update_runtime = runtime
        page._pending_user_profile_updates = []
        page._update_user_profile_button = Mock()
        page._delete_user_profile_button = Mock()
        page.create_profile_user_update_worker = Mock(return_value=next_worker)

        ProfileSetupPageBase._request_user_profile_update(
            page,
            "user-1",
            name="YouTube New",
            protocol="TCP",
            ports="80,443",
        )
        ProfileSetupPageBase._request_user_profile_update(
            page,
            "user-2",
            name="Discord New",
            protocol="UDP",
            ports="50000-65535",
        )

        page.create_profile_user_update_worker.assert_not_called()
        self.assertEqual(
            page._pending_user_profile_updates,
            [
                {
                    "profile_id": "user-1",
                    "name": "YouTube New",
                    "protocol": "TCP",
                    "ports": "80,443",
                },
                {
                    "profile_id": "user-2",
                    "name": "Discord New",
                    "protocol": "UDP",
                    "ports": "50000-65535",
                },
            ],
        )

        runtime.running = False
        callbacks = []
        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_user_profile_update_worker_finished(
                page, SimpleNamespace(_request_id=1)
            )

        page.create_profile_user_update_worker.assert_not_called()
        next_worker.start.assert_not_called()
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page.create_profile_user_update_worker.assert_called_once_with(
            2,
            profile_id="user-1",
            name="YouTube New",
            protocol="TCP",
            ports="80,443",
            parent=page,
        )
        next_worker.start.assert_called_once()
        self.assertEqual(
            page._pending_user_profile_updates,
            [
                {
                    "profile_id": "user-2",
                    "name": "Discord New",
                    "protocol": "UDP",
                    "ports": "50000-65535",
                }
            ],
        )

    def test_profile_setup_user_profile_queue_restarts_after_worker_signal_returns(self) -> None:
        from profile.ui.profile_user_profile_controller import ProfileUserProfileController

        update_finished = inspect.getsource(ProfileUserProfileController._on_user_profile_update_worker_finished)
        delete_finished = inspect.getsource(ProfileUserProfileController._on_user_profile_delete_worker_finished)
        schedule_source = inspect.getsource(
            ProfileUserProfileController._schedule_next_pending_user_profile_write_operation_start
        )
        run_source = inspect.getsource(ProfileUserProfileController._run_scheduled_user_profile_write_operation_start)

        for source in (update_finished, delete_finished):
            self.assertIn("_schedule_next_user_profile_write_operation_after_finish", source)
            self.assertNotIn("_start_next_pending_user_profile_write_operation()", source)

        self.assertIn("QTimer.singleShot", schedule_source)
        self.assertIn("_run_scheduled_user_profile_write_operation_start", schedule_source)
        self.assertIn("_start_next_pending_user_profile_write_operation", run_source)

    def test_profile_setup_write_finished_uses_queued_state_finish_guard(self) -> None:
        from profile.ui.profile_setup_save_controllers import ProfileSetupSaveController
        from profile.ui.profile_strategy_controller import ProfileStrategyController

        profile_write_helper = inspect.getsource(
            ProfileSetupSaveController._schedule_next_profile_setup_write_operation_after_finish
        )
        from profile.ui.profile_user_profile_controller import ProfileUserProfileController

        user_profile_write_helper = inspect.getsource(
            ProfileUserProfileController._schedule_next_user_profile_write_operation_after_finish
        )

        for source in (profile_write_helper, user_profile_write_helper):
            self.assertIn("schedule_next_after_finish", source)
            self.assertIn("_accept_current_profile_setup_worker_finished", source)
            self.assertIn("is_current_worker_finish", source)

        from profile.ui.profile_list_file_editor_controller import ProfileListFileEditorController

        for handler in (
            ProfileListFileEditorController._on_list_file_save_worker_finished,
            ProfileSetupSaveController._on_settings_save_worker_finished,
            ProfileSetupSaveController._on_raw_profile_save_worker_finished,
            ProfileSetupSaveController._on_enabled_save_worker_finished,
            ProfileStrategyController._on_strategy_apply_worker_finished,
        ):
            self.assertIn(
                "_schedule_next_profile_setup_write_operation_after_finish",
                inspect.getsource(handler),
            )

        for handler in (
            ProfileUserProfileController._on_user_profile_update_worker_finished,
            ProfileUserProfileController._on_user_profile_delete_worker_finished,
        ):
            self.assertIn(
                "_schedule_next_user_profile_write_operation_after_finish",
                inspect.getsource(handler),
            )

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
                self.deleteLater = Mock()

            def isRunning(self) -> bool:
                return False

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._user_profile_delete_request_id = 0
        page._user_profile_delete_worker = None
        page._update_user_profile_button = Mock()
        page._delete_user_profile_button = Mock()
        worker = _Worker()
        page.create_profile_user_delete_worker = Mock(return_value=worker)

        ProfileSetupPageBase._request_user_profile_delete(page, "user-1")

        page.create_profile_user_delete_worker.assert_called_once_with(
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

    def test_user_profile_update_result_ignored_when_new_operation_is_pending(self) -> None:
        updated_item = SimpleNamespace(key="profile-1", user_profile_id="user-1")
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._user_profile_update_request_id = 1
        page._profile_key = "profile-1"
        page._payload = SimpleNamespace(item=SimpleNamespace(key="profile-1", user_profile_id="user-1"))
        page._pending_user_profile_operations = [
            {
                "action": "update",
                "profile_id": "user-1",
                "name": "Latest",
                "protocol": "TCP",
                "ports": "443",
            }
        ]
        page.reload_current_profile = Mock()
        page._apply_user_profile_update_locally = Mock()
        page._on_profile_changed_callback = Mock()
        page.window = Mock(return_value=None)

        with patch("profile.ui.profile_setup_page.InfoBar.success") as success:
            ProfileSetupPageBase._on_user_profile_update_finished(page, 1, "user-1", 3, (updated_item,))

        page.reload_current_profile.assert_not_called()
        page._apply_user_profile_update_locally.assert_not_called()
        page._on_profile_changed_callback.assert_not_called()
        success.assert_not_called()

    def test_user_profile_delete_result_ignored_when_new_operation_is_pending(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._user_profile_delete_request_id = 2
        page._profile_key = "profile-1"
        page._payload = SimpleNamespace(item=SimpleNamespace(key="profile-1", user_profile_id="user-1"))
        page._pending_user_profile_operations = [
            {
                "action": "update",
                "profile_id": "user-1",
                "name": "Latest",
                "protocol": "TCP",
                "ports": "443",
            }
        ]
        page._on_profile_changed_callback = Mock()
        page._open_profiles = Mock()
        page.window = Mock(return_value=None)

        with patch("profile.ui.profile_setup_page.InfoBar.success") as success:
            ProfileSetupPageBase._on_user_profile_delete_finished(page, 2, "user-1", 3)

        page._on_profile_changed_callback.assert_not_called()
        page._open_profiles.assert_not_called()
        success.assert_not_called()

    def test_user_profile_update_result_updates_detail_without_reload(self) -> None:
        current_item = ProfileListItem(
            key="profile-1",
            persistent_key="profile-1",
            profile_index=1,
            display_name="YouTube",
            enabled=True,
            in_preset=True,
            strategy_id="strategy",
            strategy_name="Strategy",
            match_lines=("--filter-tcp=443",),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="common",
            group_name="",
            order=1,
            user_profile_id="user-1",
            profile_name="YouTube",
        )
        updated_item = ProfileListItem(
            key="profile-1",
            persistent_key="profile-1",
            profile_index=1,
            display_name="YouTube New",
            enabled=True,
            in_preset=True,
            strategy_id="strategy",
            strategy_name="Strategy",
            match_lines=("--filter-tcp=443",),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="common",
            group_name="",
            order=1,
            user_profile_id="user-1",
            profile_name="YouTube New",
        )
        payload = ProfileSetupPayload(
            item=current_item,
            strategy_entries={},
            strategy_states={},
            raw_profile_text="",
            raw_strategy_text="",
            match_summary="",
        )
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._user_profile_update_request_id = 1
        page._profile_key = "profile-1"
        page._payload = payload
        page._apply_payload = Mock()
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()
        page.window = Mock(return_value=None)
        callbacks = []

        with (
            patch("profile.ui.profile_setup_page.InfoBar.success"),
            patch(
                "profile.ui.profile_setup_page.QTimer.singleShot",
                side_effect=lambda _delay, callback: callbacks.append(callback),
            ),
        ):
            ProfileSetupPageBase._on_user_profile_update_finished(page, 1, "user-1", 3, (updated_item,))

        page.reload_current_profile.assert_not_called()
        page._apply_payload.assert_not_called()
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        page._apply_payload.assert_called_once_with(page._payload)
        self.assertIs(page._payload.item, updated_item)
        page._on_profile_changed_callback.assert_called_once_with(
            "profile-1",
            "user_profile_updated",
            updated_item,
        )

    def test_user_profile_update_result_skips_duplicate_item_apply(self) -> None:
        item = ProfileListItem(
            key="profile-1",
            persistent_key="profile-1",
            profile_index=1,
            display_name="YouTube",
            enabled=True,
            in_preset=True,
            strategy_id="strategy",
            strategy_name="Strategy",
            match_lines=("--filter-tcp=443",),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="common",
            group_name="",
            order=1,
            user_profile_id="user-1",
            profile_name="YouTube",
        )
        payload = ProfileSetupPayload(
            item=item,
            strategy_entries={},
            strategy_states={},
            raw_profile_text="",
            raw_strategy_text="",
            match_summary="",
        )
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._user_profile_update_request_id = 1
        page._profile_key = "profile-1"
        page._payload = payload
        page._apply_payload = Mock(side_effect=AssertionError("same user profile item must not repaint page"))
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()
        page.window = Mock(return_value=None)

        with patch("profile.ui.profile_setup_page.InfoBar.success") as success:
            ProfileSetupPageBase._on_user_profile_update_finished(page, 1, "user-1", 3, (item,))

        page.reload_current_profile.assert_not_called()
        page._apply_payload.assert_not_called()
        page._on_profile_changed_callback.assert_not_called()
        success.assert_called_once()

    def test_user_profile_update_result_skips_equal_item_apply(self) -> None:
        current_item = ProfileListItem(
            key="profile-1",
            persistent_key="profile-1",
            profile_index=1,
            display_name="YouTube",
            enabled=True,
            in_preset=True,
            strategy_id="strategy",
            strategy_name="Strategy",
            match_lines=("--filter-tcp=443",),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="common",
            group_name="",
            order=1,
            user_profile_id="user-1",
            profile_name="YouTube",
        )
        updated_item = ProfileListItem(
            key="profile-1",
            persistent_key="profile-1",
            profile_index=1,
            display_name="YouTube",
            enabled=True,
            in_preset=True,
            strategy_id="strategy",
            strategy_name="Strategy",
            match_lines=("--filter-tcp=443",),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="common",
            group_name="",
            order=1,
            user_profile_id="user-1",
            profile_name="YouTube",
        )
        payload = ProfileSetupPayload(
            item=current_item,
            strategy_entries={},
            strategy_states={},
            raw_profile_text="",
            raw_strategy_text="",
            match_summary="",
        )
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._user_profile_update_request_id = 1
        page._profile_key = "profile-1"
        page._payload = payload
        page._apply_payload = Mock(side_effect=AssertionError("equal user profile item must not repaint page"))
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()
        page.window = Mock(return_value=None)

        with patch("profile.ui.profile_setup_page.InfoBar.success") as success:
            ProfileSetupPageBase._on_user_profile_update_finished(page, 1, "user-1", 3, (updated_item,))

        page.reload_current_profile.assert_not_called()
        page._apply_payload.assert_not_called()
        page._on_profile_changed_callback.assert_not_called()
        success.assert_called_once()

    def test_user_profile_update_worker_emits_changed_count_and_items(self) -> None:
        updated_item = ProfileListItem(
            key="profile:user-1",
            persistent_key="profile:user-1",
            profile_index=1,
            display_name="YouTube",
            enabled=True,
            in_preset=True,
            strategy_id="strategy",
            strategy_name="Strategy",
            match_lines=("--filter-tcp=443",),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="common",
            group_name="",
            order=1,
            user_profile_id="user-1",
            profile_name="YouTube",
        )
        update_user_profile = Mock(return_value=3)
        load_user_profile_items = Mock(return_value=(updated_item,))
        worker = ProfileUserProfileUpdateWorker(
            7,
            update_user_profile,
            load_user_profile_items,
            profile_id="user-1",
            name="YouTube",
            protocol="TCP",
            ports="443",
        )
        updated = []

        worker.updated.connect(
            lambda request_id, profile_id, changed, items: updated.append((request_id, profile_id, changed, items))
        )

        worker.run()

        update_user_profile.assert_called_once_with(
            profile_id="user-1",
            name="YouTube",
            protocol="TCP",
            ports="443",
        )
        load_user_profile_items.assert_called_once_with("user-1")
        self.assertEqual(updated, [(7, "user-1", 3, (updated_item,))])

    def test_user_profile_delete_worker_emits_changed_count(self) -> None:
        delete_user_profile = Mock(return_value=2)
        worker = ProfileUserProfileDeleteWorker(8, delete_user_profile, profile_id="user-1")
        deleted = []

        worker.deleted.connect(
            lambda request_id, profile_id, changed: deleted.append((request_id, profile_id, changed))
        )

        worker.run()

        delete_user_profile.assert_called_once_with(profile_id="user-1")
        self.assertEqual(deleted, [(8, "user-1", 2)])

    def test_strategy_list_click_handlers_match_qlistwidget_signals(self) -> None:
        clicked = inspect.signature(ProfileStrategyListWidget._on_item_clicked)
        activated = inspect.signature(ProfileStrategyListWidget._on_item_activated)

        self.assertEqual(tuple(clicked.parameters), ("self", "item"))
        self.assertEqual(tuple(activated.parameters), ("self", "item"))

    def test_match_tab_text_contains_match_strategy_and_raw_profile(self) -> None:
        text = build_profile_setup_match_tab_text(
            match_summary="TCP • TCP 80,443 • hostlist",
            strategy_id="tls_fake",
            strategy_name="TLS Fake",
            raw_strategy_text="--lua-desync=fake",
        )

        self.assertIn("Когда profile применяется", text)
        self.assertIn("TCP • TCP 80,443 • hostlist", text)
        self.assertIn("Текущая готовая стратегия", text)
        self.assertIn("TLS Fake", text)
        self.assertIn("--lua-desync=fake", text)
        self.assertNotIn("--hostlist=lists/youtube.txt", text)

    def test_match_tab_payload_uses_worker_prepared_text(self) -> None:
        apply_match = inspect.getsource(ProfileSetupPageBase._apply_match_tab_payload)

        self.assertIn("match_tab_text", apply_match)
        self.assertNotIn("strategy_entries", apply_match)
        self.assertNotIn("raw_strategy_text", apply_match)
        self.assertNotIn("_match_tab_text(", apply_match)

    def test_profile_setup_page_has_raw_profile_editor_for_current_preset(self) -> None:
        build = inspect.getsource(ProfileSetupPageBase._build_content)
        ensure_match = inspect.getsource(ProfileSetupPageBase._ensure_match_tab_built)
        apply_match = inspect.getsource(ProfileSetupPageBase._apply_match_tab_payload)
        handler = inspect.getsource(ProfileSetupPageBase._on_raw_profile_save_clicked)
        from profile.ui.profile_setup_save_controllers import ProfileSetupSaveController

        start_handler = inspect.getsource(ProfileSetupSaveController._start_raw_profile_save_worker)
        saved_handler = inspect.getsource(ProfileSetupSaveController._on_raw_profile_save_finished)

        self.assertNotIn("self._raw_profile_text = PlainTextEdit()", build)
        self.assertIn("_raw_profile_text", ensure_match)
        self.assertIn("Сохранить текст profile", ensure_match)
        self.assertIn("in_preset", apply_match)
        self.assertIn("_request_raw_profile_save", handler)
        self.assertIn("create_profile_raw_text_save_worker", start_handler)
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
                self.deleteLater = Mock()

            def isRunning(self) -> bool:
                return False

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._raw_profile_text = SimpleNamespace(toPlainText=lambda: "--new\n--lua-desync=fake")
        page._raw_profile_text_cache = "--new\n--lua-desync=fake"
        page._raw_profile_save_request_id = 0
        page._raw_profile_save_button = Mock()
        worker = _Worker()
        page.create_profile_raw_text_save_worker = Mock(return_value=worker)

        ProfileSetupPageBase._on_raw_profile_save_clicked(page)

        page.create_profile_raw_text_save_worker.assert_called_once_with(
            1,
            "profile-1",
            "--new\n--lua-desync=fake",
            parent=page,
        )
        page._raw_profile_save_button.setEnabled.assert_called_once_with(False)
        worker.start.assert_called_once()

    def test_raw_profile_save_keeps_latest_pending_click_while_worker_runs(self) -> None:
        class _Signal:
            def __init__(self) -> None:
                self.callbacks = []

            def connect(self, callback) -> None:
                self.callbacks.append(callback)

        class _Worker:
            def __init__(self, *, running: bool) -> None:
                self._running = running
                self.saved = _Signal()
                self.failed = _Signal()
                self.finished = _Signal()
                self.start = Mock()
                self.deleteLater = Mock()

            def isRunning(self) -> bool:
                return self._running

        next_worker = _Worker(running=False)

        class _Runtime:
            def __init__(self) -> None:
                self.running = True

            def is_running(self) -> bool:
                return self.running

            def start_qthread_worker(self, *, worker_factory, **_kwargs):
                worker = worker_factory(0)
                worker.start()
                return 0, worker

        runtime = _Runtime()
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._raw_profile_text = SimpleNamespace(toPlainText=lambda: "--new\n--lua-desync=split")
        page._raw_profile_text_cache = "--new\n--lua-desync=split"
        page._raw_profile_save_request_id = 1
        page._raw_profile_save_runtime = runtime
        page._pending_raw_profile_save = None
        page._raw_profile_save_button = Mock()
        page.create_profile_raw_text_save_worker = Mock(return_value=next_worker)

        ProfileSetupPageBase._on_raw_profile_save_clicked(page)

        page.create_profile_raw_text_save_worker.assert_not_called()
        self.assertEqual(page._pending_raw_profile_save, ("profile-1", None))

        runtime.running = False
        callbacks = []
        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_raw_profile_save_worker_finished(
                page, SimpleNamespace(_request_id=1)
            )

        page.create_profile_raw_text_save_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()

        page.create_profile_raw_text_save_worker.assert_called_once_with(
            2,
            "profile-1",
            "--new\n--lua-desync=split",
            parent=page,
        )
        next_worker.start.assert_called_once()
        self.assertIsNone(page._pending_raw_profile_save)

    def test_raw_profile_save_worker_emits_new_profile_key_and_payload(self) -> None:
        save_raw_text = Mock()
        load_profile = Mock()
        payload = SimpleNamespace(item=SimpleNamespace(key="profile-2"))
        save_raw_text.return_value = "profile-2"
        load_profile.return_value = payload
        worker = ProfileRawTextSaveWorker(7, save_raw_text, load_profile, "profile-1", "--new\n")
        saved = []

        worker.saved.connect(lambda request_id, profile_key, emitted_payload: saved.append(
            (request_id, profile_key, emitted_payload)
        ))

        worker.run()

        save_raw_text.assert_called_once_with(
            profile_key="profile-1",
            raw_text="--new\n",
        )
        load_profile.assert_called_once_with("profile-2")
        self.assertEqual(len(saved), 1)
        # Воркер нормализует результат save к паре (old, new) persistent_key.
        self.assertEqual(saved[0][:2], (7, ("profile-2", "profile-2")))
        self.assertIs(saved[0][2].payload, payload)
        self.assertTrue(saved[0][2].apply_signature)

    def test_raw_profile_save_finish_passes_updated_item_to_preset_page(self) -> None:
        item = SimpleNamespace(key="profile-2")
        payload = SimpleNamespace(item=item)
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._raw_profile_save_request_id = 7
        page._profile_key = "profile-1"
        page.reload_current_profile = Mock()
        page._apply_payload = Mock()
        page._on_profile_changed_callback = Mock()
        page.window = Mock(return_value=None)
        callbacks = []

        with (
            patch("profile.ui.profile_setup_page.InfoBar.success"),
            patch(
                "profile.ui.profile_setup_page.QTimer.singleShot",
                side_effect=lambda _delay, callback: callbacks.append(callback),
            ),
        ):
            ProfileSetupPageBase._on_raw_profile_save_finished(page, 7, "profile-2", payload)

        self.assertEqual(page._profile_key, "profile-2")
        page.reload_current_profile.assert_not_called()
        page._apply_payload.assert_not_called()
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        page._apply_payload.assert_called_once_with(payload)
        page._on_profile_changed_callback.assert_called_once_with("profile-2", "raw_profile", item)

    def test_raw_profile_save_finish_ignores_result_when_new_save_is_pending(self) -> None:
        payload = SimpleNamespace(item=SimpleNamespace(key="profile-2"))
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._raw_profile_save_request_id = 7
        page._profile_key = "profile-1"
        page._pending_raw_profile_save = ("profile-1", "--new\n--lua-desync=split")
        page.reload_current_profile = Mock()
        page._schedule_profile_setup_payload_apply = Mock()
        page._on_profile_changed_callback = Mock()
        page.window = Mock(return_value=None)

        with patch("profile.ui.profile_setup_page.InfoBar.success") as success:
            ProfileSetupPageBase._on_raw_profile_save_finished(page, 7, "profile-2", payload)

        self.assertEqual(page._profile_key, "profile-1")
        page.reload_current_profile.assert_not_called()
        page._schedule_profile_setup_payload_apply.assert_not_called()
        page._on_profile_changed_callback.assert_not_called()
        success.assert_not_called()

    def test_raw_profile_save_finish_skips_duplicate_payload_apply(self) -> None:
        item = SimpleNamespace(key="profile-1")
        payload = SimpleNamespace(item=item)
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._raw_profile_save_request_id = 7
        page._profile_key = "profile-1"
        page._payload = payload
        page.reload_current_profile = Mock()
        page._apply_payload = Mock(side_effect=AssertionError("same raw profile payload must not repaint page"))
        page._on_profile_changed_callback = Mock()
        page.window = Mock(return_value=None)

        with patch("profile.ui.profile_setup_page.InfoBar.success") as success:
            ProfileSetupPageBase._on_raw_profile_save_finished(page, 7, "profile-1", payload)

        self.assertEqual(page._profile_key, "profile-1")
        page.reload_current_profile.assert_not_called()
        page._apply_payload.assert_not_called()
        page._on_profile_changed_callback.assert_not_called()
        success.assert_called_once()

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
                self.deleteLater = Mock()
                self.deleteLater = Mock()

            def isRunning(self) -> bool:
                return False

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._enabled_save_request_id = 0
        page._enabled_checkbox = Mock()
        page._current_filter_kind = lambda: "hostlist"
        page._current_filter_value = lambda: "lists/youtube.txt"
        worker = _Worker()
        page.create_profile_enabled_save_worker = Mock(return_value=worker)

        ProfileSetupPageBase._on_enabled_changed(page, 2)

        page.create_profile_enabled_save_worker.assert_called_once_with(
            1,
            profile_key="profile-1",
            enabled=True,
            filter_kind="hostlist",
            filter_value="lists/youtube.txt",
            parent=page,
        )
        page._enabled_checkbox.setEnabled.assert_called_once_with(False)
        worker.start.assert_called_once()

    def test_enabled_save_worker_emits_new_profile_key_and_payload(self) -> None:
        set_enabled = Mock(return_value="profile-2")
        load_profile = Mock()
        payload = SimpleNamespace(item=SimpleNamespace(key="profile-2"))
        load_profile.return_value = payload
        worker = ProfileEnabledSaveWorker(
            8,
            set_enabled,
            load_profile,
            profile_key="profile-1",
            enabled=False,
            filter_kind="hostlist",
            filter_value="lists/youtube.txt",
        )
        saved = []

        worker.saved.connect(
            lambda request_id, profile_key, enabled, emitted_payload: saved.append(
                (request_id, profile_key, enabled, emitted_payload)
            )
        )

        worker.run()

        set_enabled.assert_called_once_with(
            profile_key="profile-1",
            enabled=False,
            filter_kind="hostlist",
            filter_value="lists/youtube.txt",
        )
        load_profile.assert_called_once_with("profile-2")
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0][:3], (8, "profile-2", False))
        self.assertIs(saved[0][3].payload, payload)
        self.assertTrue(saved[0][3].apply_signature)

    def test_enabled_save_finish_updates_detail_without_reload(self) -> None:
        item = ProfileListItem(
            key="profile-1",
            persistent_key="profile-1",
            profile_index=1,
            display_name="YouTube",
            enabled=False,
            in_preset=True,
            strategy_id="strategy",
            strategy_name="Strategy",
            match_lines=("--filter-tcp=443",),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="common",
            group_name="",
            order=1,
        )
        payload = ProfileSetupPayload(
            item=item,
            strategy_entries={},
            strategy_states={},
            raw_profile_text="",
            raw_strategy_text="",
            match_summary="",
        )
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._enabled_save_request_id = 8
        page._profile_key = "profile-1"
        page._payload = payload
        page._enabled_checkbox = Mock()
        page._enabled_checkbox.isChecked.return_value = False
        page._enabled_checkbox.isEnabled.return_value = False
        page._loading = False
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()

        ProfileSetupPageBase._on_enabled_save_finished(page, 8, "profile-1", True)

        page.reload_current_profile.assert_not_called()
        self.assertTrue(page._payload.item.enabled)
        page._enabled_checkbox.setChecked.assert_called_once_with(True)
        page._enabled_checkbox.setEnabled.assert_called_once_with(True)
        page._on_profile_changed_callback.assert_called_once_with(
            "profile-1",
            "enabled",
            page._payload.item,
        )

    def test_enabled_save_finish_applies_worker_payload_without_reload(self) -> None:
        item = ProfileListItem(
            key="profile-2",
            persistent_key="profile-2",
            profile_index=2,
            display_name="YouTube",
            enabled=True,
            in_preset=True,
            strategy_id="strategy",
            strategy_name="Strategy",
            match_lines=("--filter-tcp=443",),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="common",
            group_name="",
            order=2,
        )
        payload = ProfileSetupPayload(
            item=item,
            strategy_entries={},
            strategy_states={},
            raw_profile_text="",
            raw_strategy_text="",
            match_summary="",
        )
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._enabled_save_request_id = 9
        page._profile_key = "template:profile-1"
        page._payload = None
        page._apply_payload = Mock()
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()
        callbacks = []

        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_enabled_save_finished(page, 9, "profile-2", True, payload)

        page.reload_current_profile.assert_not_called()
        page._apply_payload.assert_not_called()
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        page._apply_payload.assert_called_once_with(payload)
        page._on_profile_changed_callback.assert_called_once_with("profile-2", "enabled", item)

    def test_enabled_save_finish_ignores_result_when_new_toggle_is_pending(self) -> None:
        item = SimpleNamespace(key="profile-2")
        payload = SimpleNamespace(item=item)
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._enabled_save_request_id = 9
        page._profile_key = "profile-1"
        page._pending_enabled_save = False
        page._payload = None
        page._schedule_profile_setup_payload_apply = Mock()
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()

        ProfileSetupPageBase._on_enabled_save_finished(page, 9, "profile-2", True, payload)

        self.assertEqual(page._profile_key, "profile-1")
        page.reload_current_profile.assert_not_called()
        page._schedule_profile_setup_payload_apply.assert_not_called()
        page._on_profile_changed_callback.assert_not_called()

    def test_enabled_save_finish_skips_duplicate_payload(self) -> None:
        item = SimpleNamespace(key="profile-1")
        payload = SimpleNamespace(item=item)
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._enabled_save_request_id = 9
        page._profile_key = "profile-1"
        page._payload = payload
        page._apply_payload = Mock(side_effect=AssertionError("same enabled payload must not repaint page"))
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()

        ProfileSetupPageBase._on_enabled_save_finished(page, 9, "profile-1", True, payload)

        self.assertEqual(page._profile_key, "profile-1")
        page.reload_current_profile.assert_not_called()
        page._apply_payload.assert_not_called()
        page._on_profile_changed_callback.assert_not_called()

    def test_enabled_save_scheduled_restart_uses_latest_pending_value(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._payload = SimpleNamespace(item=SimpleNamespace(enabled=False))
        page._enabled_save_runtime = SimpleNamespace(is_running=Mock(return_value=False))
        page._enabled_save_runtime_enabled = None
        page._enabled_save_start_scheduled = True
        page._pending_enabled_save = False
        page._start_enabled_save_worker = Mock()

        ProfileSetupPageBase._on_enabled_changed(page, 2)

        page._start_enabled_save_worker.assert_not_called()
        self.assertTrue(page._pending_enabled_save)

        ProfileSetupPageBase._run_scheduled_enabled_save_worker_start(page)

        page._start_enabled_save_worker.assert_called_once_with(True)

    def test_profile_setup_page_has_list_file_editor_as_second_tab(self) -> None:
        build = inspect.getsource(ProfileSetupPageBase._build_content)
        ensure_editor = inspect.getsource(ProfileSetupPageBase._ensure_editor_tab_built)
        apply_payload = inspect.getsource(ProfileSetupPageBase._apply_payload)
        sync_label = inspect.getsource(ProfileSetupPageBase._sync_editor_tab_label)
        switch_tab = inspect.getsource(ProfileSetupPageBase._switch_strategy_tab)
        save_handler = inspect.getsource(ProfileSetupPageBase._on_list_file_save_clicked)
        from profile.ui.profile_list_file_editor_controller import ProfileListFileEditorController

        save_start_handler = inspect.getsource(ProfileListFileEditorController._start_list_file_save_worker)
        validation = inspect.getsource(ProfileSetupPageBase._render_list_file_validation)

        self.assertIn('addItem("editor", "Редактор"', build)
        self.assertIn("_sync_editor_tab_label(payload)", apply_payload)
        self.assertIn('set_tab_item_text_if_changed(self._strategy_tabs, "editor", editor_title)', sync_label)
        self.assertNotIn("self._list_file_text = PlainTextEdit()", build)
        self.assertIn("_ensure_editor_tab_built", switch_tab)
        self.assertIn("_request_list_file_editor_state", switch_tab)
        self.assertIn("_list_file_text", ensure_editor)
        self.assertIn("_list_file_base_text", ensure_editor)
        self.assertIn("Ваши записи", ensure_editor)
        self.assertNotIn("_apply_list_file_editor_state", apply_payload)
        self.assertIn("_request_list_file_save", save_handler)
        self.assertIn("create_profile_list_file_save_worker", save_start_handler)
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
                self.deleteLater = Mock()

            def isRunning(self) -> bool:
                return False

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._list_file_text = SimpleNamespace(toPlainText=lambda: "example.com")
        page._list_file_text_snapshot = "example.com"
        page._list_file_save_request_id = 0
        page._list_file_save_worker = None
        page._list_file_status_label = Mock()
        page._list_file_save_button = Mock()
        page._current_filter_kind = Mock(return_value="ipset")
        page._current_filter_value = Mock(return_value="lists/ipset-all.txt")
        worker = _Worker()
        page.create_profile_list_file_save_worker = Mock(return_value=worker)

        ProfileSetupPageBase._on_list_file_save_clicked(page)

        page.create_profile_list_file_save_worker.assert_called_once_with(
            1,
            "profile-1",
            "example.com",
            filter_kind="ipset",
            filter_value="lists/ipset-all.txt",
            parent=page,
        )
        page._list_file_save_button.setEnabled.assert_called_once_with(False)
        worker.start.assert_called_once()

    def test_list_file_save_keeps_latest_pending_click_while_worker_runs(self) -> None:
        class _Signal:
            def __init__(self) -> None:
                self.callbacks = []

            def connect(self, callback) -> None:
                self.callbacks.append(callback)

        class _Worker:
            def __init__(self, *, running: bool) -> None:
                self._running = running
                self.saved = _Signal()
                self.failed = _Signal()
                self.finished = _Signal()
                self.start = Mock()
                self.deleteLater = Mock()

            def isRunning(self) -> bool:
                return self._running

        next_worker = _Worker(running=False)

        class _Runtime:
            def __init__(self) -> None:
                self.running = True

            def is_running(self) -> bool:
                return self.running

            def start_qthread_worker(self, *, worker_factory, **_kwargs):
                worker = worker_factory(0)
                worker.start()
                return 0, worker

        runtime = _Runtime()
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._list_file_text = SimpleNamespace(toPlainText=lambda: "ignored.example")
        page._list_file_text_snapshot = "latest.example"
        # Мемо чистое: клик сохраняет согласованный текст мемо, без повторного
        # чтения редактора на рестарте отложенного сохранения.
        page._list_file_text_dirty = False
        page._list_file_save_request_id = 1
        page._list_file_save_runtime = runtime
        page._pending_list_file_save = None
        page._list_file_status_label = Mock()
        page._list_file_save_button = Mock()
        page._current_filter_kind = Mock(return_value="hostlist")
        page._current_filter_value = Mock(return_value="lists/youtube.txt")
        page.create_profile_list_file_save_worker = Mock(return_value=next_worker)

        ProfileSetupPageBase._on_list_file_save_clicked(page)

        page.create_profile_list_file_save_worker.assert_not_called()
        self.assertEqual(
            page._pending_list_file_save,
            {
                "profile_key": "profile-1",
                "text": "latest.example",
                "filter_kind": "hostlist",
                "filter_value": "lists/youtube.txt",
            },
        )

        runtime.running = False
        callbacks = []
        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_list_file_save_worker_finished(
                page, SimpleNamespace(_request_id=1)
            )

        page.create_profile_list_file_save_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()

        page.create_profile_list_file_save_worker.assert_called_once_with(
            2,
            "profile-1",
            "latest.example",
            filter_kind="hostlist",
            filter_value="lists/youtube.txt",
            parent=page,
        )
        next_worker.start.assert_called_once()
        self.assertIsNone(page._pending_list_file_save)

    def test_list_file_save_worker_emits_saved_state_and_payload(self) -> None:
        save_text = Mock()
        load_profile = Mock()
        state = object()
        payload = SimpleNamespace(item=SimpleNamespace(key="profile-1"))
        save_text.return_value = state
        load_profile.return_value = payload
        worker = ProfileListFileSaveWorker(
            3,
            save_text,
            load_profile,
            "profile-1",
            "example.com",
            filter_kind="ipset",
            filter_value="lists/ipset-all.txt",
        )
        saved = []

        worker.saved.connect(lambda request_id, emitted_state, emitted_payload: saved.append(
            (request_id, emitted_state, emitted_payload)
        ))

        worker.run()

        save_text.assert_called_once_with(
            profile_key="profile-1",
            text="example.com",
            filter_kind="ipset",
            filter_value="lists/ipset-all.txt",
        )
        load_profile.assert_called_once_with("profile-1")
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0][:2], (3, state))
        self.assertIs(saved[0][2].payload, payload)
        self.assertTrue(saved[0][2].apply_signature)

    def _make_list_editor_page(self, *, snapshot: str, server_snapshot: str | None):
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_kind = ""
        page._list_file_text_snapshot = snapshot
        # Мемо чистое: снапшот моделирует текущий текст редактора (Mock не
        # умеет отдавать осмысленный toPlainText).
        page._list_file_text_dirty = False
        page._list_file_server_text_snapshot = server_snapshot
        # Состояние приходит для того же файла, что уже показан.
        page._list_file_applied_identity = ("hostlist", "lists/site.txt")
        page._list_file_base_text_snapshot = ""
        page._list_file_title = None
        page._list_file_base_title = None
        page._list_file_base_text = None
        page._list_file_user_title = None
        page._list_file_text = Mock()
        page._list_file_save_button = None
        page._list_file_status_label = None
        page._render_list_file_validation = Mock()
        return page

    def _list_editor_state(self, user_text: str):
        return SimpleNamespace(
            kind="hostlist",
            display_path="lists/site.txt",
            text=user_text,
            base_text="",
            user_text=user_text,
            base_display_path="",
            user_display_path="lists/user/site.txt",
            editable=True,
            error_text="",
            invalid_lines=(),
            base_entries_count=0,
            user_entries_count=1,
        )

    def test_apply_list_file_state_keeps_unsaved_user_text(self) -> None:
        """Поздний ответ воркера не затирает домены, набранные пользователем."""
        page = self._make_list_editor_page(snapshot="typed.example.com\n", server_snapshot="old.example.com\n")
        ProfileSetupPageBase._apply_list_file_editor_state(page, self._list_editor_state("old.example.com\n"))

        page._list_file_text.setPlainText.assert_not_called()
        self.assertEqual(page._list_file_text_snapshot, "typed.example.com\n")

    def test_apply_list_file_state_keeps_unsaved_text_even_after_validation_cycle(self) -> None:
        """Дыра флага dirty: валидация его сбрасывала, и ответ, пришедший позже,
        затирал несохранённый текст. Несохранённость — производное от
        server_text_snapshot, и от валидации не зависит."""
        page = self._make_list_editor_page(snapshot="typed.example.com\n", server_snapshot="old.example.com\n")
        page._list_file_text_dirty = False  # состояние после цикла валидации
        ProfileSetupPageBase._apply_list_file_editor_state(page, self._list_editor_state("old.example.com\n"))

        page._list_file_text.setPlainText.assert_not_called()
        self.assertEqual(page._list_file_text_snapshot, "typed.example.com\n")

    def test_apply_list_file_state_updates_clean_editor(self) -> None:
        page = self._make_list_editor_page(snapshot="old.example.com\n", server_snapshot="old.example.com\n")
        ProfileSetupPageBase._apply_list_file_editor_state(page, self._list_editor_state("fresh.example.com\n"))

        page._list_file_text.setPlainText.assert_called_once_with("fresh.example.com\n")
        self.assertEqual(page._list_file_text_snapshot, "fresh.example.com\n")
        self.assertEqual(page._list_file_server_text_snapshot, "fresh.example.com\n")

    def test_apply_list_file_state_applies_first_state_after_profile_open(self) -> None:
        page = self._make_list_editor_page(snapshot="", server_snapshot=None)
        ProfileSetupPageBase._apply_list_file_editor_state(page, self._list_editor_state("fresh.example.com\n"))

        page._list_file_text.setPlainText.assert_called_once_with("fresh.example.com\n")
        self.assertEqual(page._list_file_server_text_snapshot, "fresh.example.com\n")

    def test_apply_list_file_state_records_server_text_even_when_keeping_user_text(self) -> None:
        page = self._make_list_editor_page(snapshot="typed.example.com\n", server_snapshot="old.example.com\n")
        ProfileSetupPageBase._apply_list_file_editor_state(page, self._list_editor_state("newer.example.com\n"))

        page._list_file_text.setPlainText.assert_not_called()
        self.assertEqual(page._list_file_text_snapshot, "typed.example.com\n")
        self.assertEqual(page._list_file_server_text_snapshot, "newer.example.com\n")

    def _make_autosave_page(self, *, snapshot: str, server_snapshot: str | None, profile_key: str = "name:Site"):
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = profile_key
        page._list_file_text = Mock()
        page._list_file_text.isReadOnly.return_value = False
        page._list_file_text_snapshot = snapshot
        # Мемо чистое: снапшот моделирует текущий текст редактора.
        page._list_file_text_dirty = False
        page._list_file_server_text_snapshot = server_snapshot
        page._list_file_validation_has_error = False
        page._current_filter_kind = Mock(return_value="hostlist")
        page._current_filter_value = Mock(return_value="lists/site.txt")
        page._request_list_file_save = Mock()
        return page

    def test_autosave_sends_unsaved_valid_text(self) -> None:
        page = self._make_autosave_page(snapshot="typed.example.com\n", server_snapshot="old.example.com\n")
        ProfileSetupPageBase._maybe_autosave_list_file(page)

        page._request_list_file_save.assert_called_once_with(
            "name:Site",
            "typed.example.com\n",
            filter_kind="hostlist",
            filter_value="lists/site.txt",
        )

    def test_autosave_skips_when_text_matches_server(self) -> None:
        page = self._make_autosave_page(snapshot="same.example.com\n", server_snapshot="same.example.com\n")
        ProfileSetupPageBase._maybe_autosave_list_file(page)

        page._request_list_file_save.assert_not_called()

    def test_autosave_skips_read_only_editor(self) -> None:
        page = self._make_autosave_page(snapshot="typed.example.com\n", server_snapshot="")
        page._list_file_text.isReadOnly.return_value = True
        ProfileSetupPageBase._maybe_autosave_list_file(page)

        page._request_list_file_save.assert_not_called()

    def test_switch_flush_saves_unsaved_text_for_previous_profile(self) -> None:
        page = self._make_autosave_page(snapshot="typed.example.com\n", server_snapshot="old.example.com\n")
        ProfileSetupPageBase._flush_list_file_autosave_before_switch(page, "name:Previous")

        page._request_list_file_save.assert_called_once_with(
            "name:Previous",
            "typed.example.com\n",
            filter_kind="hostlist",
            filter_value="lists/site.txt",
        )

    def test_switch_flush_skips_invalid_text(self) -> None:
        page = self._make_autosave_page(snapshot="typed example com", server_snapshot="old.example.com\n")
        page._list_file_validation_has_error = True
        ProfileSetupPageBase._flush_list_file_autosave_before_switch(page, "name:Previous")

        page._request_list_file_save.assert_not_called()

    def test_list_file_save_finish_ignores_result_for_other_profile(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_save_request_id = 3
        page._profile_key = "name:Current"
        page._list_file_save_profile_key = "name:Previous"
        page._list_file_status_label = Mock()
        page.reload_current_profile = Mock()
        page._apply_list_file_editor_state = Mock()
        page._on_profile_changed_callback = Mock()
        page.window = Mock(return_value=None)

        with patch("profile.ui.profile_setup_page.InfoBar.success"):
            ProfileSetupPageBase._on_list_file_save_finished(page, 3, object(), None)

        page._apply_list_file_editor_state.assert_not_called()
        page.reload_current_profile.assert_not_called()
        # Запись на диск состоялась — другие страницы должны узнать о ней,
        # даже когда state к текущему редактору не применяется.
        page._on_profile_changed_callback.assert_called_once_with("name:Previous", "list_file")

    def test_write_queue_keeps_list_file_saves_for_different_targets(self) -> None:
        """Регресс: автосейв профиля B не должен вытеснять из очереди флаш
        профиля A — это разные файлы, потеря одного из них невосстановима."""
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        state = SimpleNamespace(pending=[], start_scheduled=False)
        page._profile_setup_write_state_obj = lambda: state

        op_a = {"kind": "list_file_save", "profile_key": "name:A", "filter_kind": "hostlist", "filter_value": "lists/a.txt", "text": "a.example\n"}
        op_b = {"kind": "list_file_save", "profile_key": "name:B", "filter_kind": "hostlist", "filter_value": "lists/b.txt", "text": "b.example\n"}
        ProfileSetupPageBase._queue_profile_setup_write_operation(page, op_a)
        ProfileSetupPageBase._queue_profile_setup_write_operation(page, op_b)

        self.assertEqual([op["profile_key"] for op in state.pending], ["name:A", "name:B"])

    def test_write_queue_replaces_list_file_save_for_same_target(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        state = SimpleNamespace(pending=[], start_scheduled=False)
        page._profile_setup_write_state_obj = lambda: state

        op_old = {"kind": "list_file_save", "profile_key": "name:A", "filter_kind": "hostlist", "filter_value": "lists/a.txt", "text": "old\n"}
        op_new = {"kind": "list_file_save", "profile_key": "name:A", "filter_kind": "hostlist", "filter_value": "lists/a.txt", "text": "new\n"}
        ProfileSetupPageBase._queue_profile_setup_write_operation(page, op_old)
        ProfileSetupPageBase._queue_profile_setup_write_operation(page, op_new)

        self.assertEqual([op["text"] for op in state.pending], ["new\n"])

    def test_autosave_targets_filter_pair_editor_was_loaded_with(self) -> None:
        """Регресс: правка поля значения фильтра не должна пересаживать текст
        редактора в другой файл — сохраняем в пару, под которую он загружен."""
        page = self._make_autosave_page(snapshot="typed.example.com\n", server_snapshot="old.example.com\n")
        page._list_file_editor_filter = ("hostlist", "lists/a.txt")
        page._current_filter_value = Mock(return_value="lists/b.txt")
        ProfileSetupPageBase._maybe_autosave_list_file(page)

        page._request_list_file_save.assert_called_once_with(
            "name:Site",
            "typed.example.com\n",
            filter_kind="hostlist",
            filter_value="lists/a.txt",
        )

    def test_list_file_save_finish_passes_updated_item_to_preset_page(self) -> None:
        item = SimpleNamespace(key="profile-1")
        payload = SimpleNamespace(item=item)
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_save_request_id = 3
        page._profile_key = "profile-1"
        page._list_file_status_label = Mock()
        page.reload_current_profile = Mock()
        page._apply_list_file_editor_state = Mock()
        page._apply_payload = Mock()
        page._on_profile_changed_callback = Mock()
        page.window = Mock(return_value=None)
        callbacks = []

        with (
            patch("profile.ui.profile_setup_page.InfoBar.success"),
            patch(
                "profile.ui.profile_setup_page.QTimer.singleShot",
                side_effect=lambda _delay, callback: callbacks.append(callback),
            ),
        ):
            ProfileSetupPageBase._on_list_file_save_finished(page, 3, object(), payload)

        page.reload_current_profile.assert_not_called()
        page._apply_payload.assert_not_called()
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        page._apply_payload.assert_called_once_with(payload)
        page._on_profile_changed_callback.assert_called_once_with("profile-1", "list_file", item)

    def test_list_file_save_finish_ignores_result_when_new_save_is_pending(self) -> None:
        payload = SimpleNamespace(item=SimpleNamespace(key="profile-1"))
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_save_request_id = 3
        page._profile_key = "profile-1"
        page._pending_list_file_save = ("profile-1", "latest.example")
        page._list_file_status_label = Mock()
        page.reload_current_profile = Mock()
        page._apply_list_file_editor_state = Mock()
        page._schedule_profile_setup_payload_apply = Mock()
        page._on_profile_changed_callback = Mock()
        page.window = Mock(return_value=None)

        with patch("profile.ui.profile_setup_page.InfoBar.success") as success:
            ProfileSetupPageBase._on_list_file_save_finished(page, 3, object(), payload)

        page._apply_list_file_editor_state.assert_not_called()
        page._list_file_status_label.setText.assert_not_called()
        page.reload_current_profile.assert_not_called()
        page._schedule_profile_setup_payload_apply.assert_not_called()
        page._on_profile_changed_callback.assert_not_called()
        success.assert_not_called()

    def test_list_file_save_finish_skips_duplicate_payload_apply(self) -> None:
        item = SimpleNamespace(key="profile-1")
        payload = SimpleNamespace(item=item)
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_save_request_id = 3
        page._profile_key = "profile-1"
        page._payload = payload
        page._list_file_status_label = Mock()
        page.reload_current_profile = Mock()
        page._apply_list_file_editor_state = Mock()
        page._apply_payload = Mock(side_effect=AssertionError("same list file payload must not repaint page"))
        page._on_profile_changed_callback = Mock()
        page.window = Mock(return_value=None)

        with patch("profile.ui.profile_setup_page.InfoBar.success") as success:
            ProfileSetupPageBase._on_list_file_save_finished(page, 3, object(), payload)

        page._apply_list_file_editor_state.assert_called_once()
        page.reload_current_profile.assert_not_called()
        page._apply_payload.assert_not_called()
        page._on_profile_changed_callback.assert_not_called()
        success.assert_called_once()

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
                self.deleteLater = Mock()

            def isRunning(self) -> bool:
                return False

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._list_file_kind = "hostlist"
        page._list_file_text = SimpleNamespace(
            toPlainText=Mock(side_effect=AssertionError("GUI must not read full list text")),
            isReadOnly=lambda: False,
        )
        page._list_file_text_snapshot = "bad domain"
        page._list_file_base_text = SimpleNamespace(toPlainText=lambda: "base.example\n")
        page._list_file_validation_request_id = 0
        page._list_file_validation_worker = None
        page._list_file_status_label = Mock()
        page._list_file_save_button = Mock()
        page._render_list_file_validation = Mock()
        worker = _Worker()
        page.create_profile_list_file_validation_worker = Mock(return_value=worker)

        ProfileSetupPageBase._on_list_file_text_changed(page)

        page.create_profile_list_file_validation_worker.assert_called_once_with(
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
        page._list_file_text_snapshot = "bad domain"
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

    def test_list_file_validation_scheduled_restart_uses_latest_pending_text(self) -> None:
        import profile.ui.profile_setup_page as profile_setup_page

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_validation_request_id = 1
        page._pending_list_file_validation = {"kind": "hostlist", "text": "old.example"}
        page._list_file_validation_runtime = SimpleNamespace(is_running=Mock(return_value=False))
        page._start_list_file_validation_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(profile_setup_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            ProfileSetupPageBase._on_list_file_validation_worker_finished(
                page, SimpleNamespace(_request_id=1)
            )
            ProfileSetupPageBase._request_list_file_validation(
                page,
                {"kind": "hostlist", "text": "latest.example"},
            )

        page._start_list_file_validation_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_list_file_validation_worker.assert_called_once_with(
            {"kind": "hostlist", "text": "latest.example"}
        )

    def test_list_file_validation_worker_emits_invalid_lines(self) -> None:
        validate_text = Mock(return_value=((2, "bad domain"),))
        worker = ProfileListFileValidationWorker(
            4,
            validate_text,
            kind="hostlist",
            text="ok.example\nbad domain",
        )
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

        validate_text.assert_called_once_with(
            kind="hostlist",
            text="ok.example\nbad domain",
        )
        self.assertEqual(
            validated,
            [(
                4,
                "hostlist",
                "ok.example\nbad domain",
                {"invalid_lines": ((2, "bad domain"),), "entries_count": 2},
            )],
        )

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
        self.assertIn("set_widget_visible_if_changed(self._filter_combo, filter_switchable)", apply_settings)
        self.assertIn("set_widget_visible_if_changed(self._filter_value, filter_switchable)", apply_settings)

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
                self.deleteLater = Mock()

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
        page._pending_settings_save = None
        worker = _Worker()
        page.create_profile_settings_save_worker = Mock(return_value=worker)

        ProfileSetupPageBase._autosave_editable_settings(page)

        page.create_profile_settings_save_worker.assert_called_once_with(
            1,
            profile_key="profile-1",
            filter_kind="hostlist",
            filter_value="lists/youtube.txt",
            in_range="x",
            out_range="x",
            parent=page,
        )
        worker.start.assert_called_once()

    def test_settings_autosave_skips_when_controls_match_payload(self) -> None:
        class _Combo:
            def __init__(self, value: str) -> None:
                self._value = value

            def currentIndex(self) -> int:
                return 0

            def itemData(self, _index: int) -> str:
                return self._value

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page.launch_method = "zapret2_mode"
        page._loading = False
        page._profile_key = "profile-1"
        page._payload = SimpleNamespace(
            editable_filter_enabled=True,
            editable_filter_kind="hostlist",
            editable_filter_value="lists/youtube.txt",
            in_range="x",
            out_range="a",
        )
        page._filter_value = SimpleNamespace(text=lambda: "lists/youtube.txt")
        page._current_filter_kind = lambda: "hostlist"
        page._in_range_mode = _Combo("x")
        page._out_range_mode = _Combo("a")
        page._in_range_value = SimpleNamespace(text=lambda: "")
        page._out_range_value = SimpleNamespace(text=lambda: "")
        page._request_settings_save = Mock(side_effect=AssertionError("same settings must not start save worker"))

        ProfileSetupPageBase._autosave_editable_settings(page)

        page._request_settings_save.assert_not_called()

    def test_filter_kind_change_reloads_visible_list_file_for_preset_profile(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page.launch_method = "zapret2_mode"
        page._loading = False
        page._profile_key = "profile-1"
        page._payload = SimpleNamespace(
            item=SimpleNamespace(in_preset=True),
            editable_filter_role="primary",
        )
        page._filter_value = SimpleNamespace(
            text=lambda: "lists/other.txt",
            setText=Mock(),
        )
        page._current_filter_kind = Mock(return_value="ipset")
        page._editor_tab_built = True
        page._strategy_stack = SimpleNamespace(currentIndex=lambda: 1)
        page._request_list_file_editor_state = Mock()
        page._settings_save_timer = Mock()

        ProfileSetupPageBase._on_filter_kind_changed(page)

        page._request_list_file_editor_state.assert_called_once_with()
        page._settings_save_timer.start.assert_called_once_with()

    def test_settings_save_worker_emits_new_profile_key_and_payload(self) -> None:
        save_settings = Mock()
        load_profile = Mock()
        payload = SimpleNamespace(item=SimpleNamespace(key="profile-2"))
        save_settings.return_value = "profile-2"
        load_profile.return_value = payload
        worker = ProfileSettingsSaveWorker(
            4,
            save_settings,
            load_profile,
            profile_key="profile-1",
            filter_kind="hostlist",
            filter_value="lists/youtube.txt",
            in_range="x",
            out_range="a",
        )
        saved = []

        worker.saved.connect(lambda request_id, profile_key, emitted_payload: saved.append(
            (request_id, profile_key, emitted_payload)
        ))

        worker.run()

        save_settings.assert_called_once_with(
            profile_key="profile-1",
            filter_kind="hostlist",
            filter_value="lists/youtube.txt",
            in_range="x",
            out_range="a",
        )
        load_profile.assert_called_once_with("profile-2")
        self.assertEqual(len(saved), 1)
        # Воркер нормализует результат save к паре (old, new) persistent_key.
        self.assertEqual(saved[0][:2], (4, ("profile-2", "profile-2")))
        self.assertIs(saved[0][2].payload, payload)
        self.assertTrue(saved[0][2].apply_signature)

    def test_settings_save_finish_passes_worker_signature_to_deferred_apply(self) -> None:
        item = SimpleNamespace(key="profile-2")
        payload = SimpleNamespace(item=item)
        result = SimpleNamespace(payload=payload, apply_signature=("settings", "profile-2"))
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._settings_save_request_id = 4
        page._pending_settings_save = None
        page._profile_key = "profile-1"
        page._payload = None
        page.reload_current_profile = Mock()
        page._schedule_profile_setup_payload_apply = Mock()
        page._on_profile_changed_callback = Mock()

        ProfileSetupPageBase._on_settings_save_finished(page, 4, "profile-2", result)

        self.assertEqual(page._profile_key, "profile-2")
        page.reload_current_profile.assert_not_called()
        self.assertIs(page._payload, payload)
        page._schedule_profile_setup_payload_apply.assert_called_once_with(
            payload,
            apply_signature=("settings", "profile-2"),
        )
        page._on_profile_changed_callback.assert_called_once_with("profile-2", "settings", item)

    def test_settings_save_finish_passes_updated_item_to_preset_page(self) -> None:
        item = SimpleNamespace(key="profile-2")
        payload = SimpleNamespace(item=item)
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._settings_save_request_id = 4
        page._pending_settings_save = None
        page._profile_key = "profile-1"
        page.reload_current_profile = Mock()
        page._apply_payload = Mock()
        page._on_profile_changed_callback = Mock()
        callbacks = []

        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_settings_save_finished(page, 4, "profile-2", payload)

        self.assertEqual(page._profile_key, "profile-2")
        page.reload_current_profile.assert_not_called()
        page._apply_payload.assert_not_called()
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        page._apply_payload.assert_called_once_with(payload)
        page._on_profile_changed_callback.assert_called_once_with("profile-2", "settings", item)

    def test_settings_save_finish_skips_duplicate_payload(self) -> None:
        item = SimpleNamespace(key="profile-1")
        payload = SimpleNamespace(item=item)
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._settings_save_request_id = 4
        page._pending_settings_save = None
        page._profile_key = "profile-1"
        page._payload = payload
        page.reload_current_profile = Mock()
        page._apply_payload = Mock(side_effect=AssertionError("same payload must not repaint page"))
        page._on_profile_changed_callback = Mock()

        ProfileSetupPageBase._on_settings_save_finished(page, 4, "profile-1", payload)

        self.assertEqual(page._profile_key, "profile-1")
        page.reload_current_profile.assert_not_called()
        page._apply_payload.assert_not_called()
        page._on_profile_changed_callback.assert_not_called()

    def test_settings_autosave_while_worker_runs_keeps_last_pending_request(self) -> None:
        class _Runtime:
            def is_running(self) -> bool:
                return True

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._settings_save_runtime = _Runtime()
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

    def test_settings_autosave_while_worker_runs_skips_duplicate_pending_request(self) -> None:
        class _Runtime:
            def is_running(self) -> bool:
                return True

        request = {
            "profile_key": "profile-1",
            "filter_kind": "hostlist",
            "filter_value": "lists/new.txt",
            "in_range": "x",
            "out_range": "a",
        }
        pending = dict(request)
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._settings_save_runtime = _Runtime()
        page._pending_settings_save = pending
        page._start_settings_save_worker = Mock()

        ProfileSetupPageBase._request_settings_save(page, request)

        self.assertIs(page._pending_settings_save, pending)
        page._start_settings_save_worker.assert_not_called()

    def test_settings_save_error_is_ignored_when_new_save_is_pending(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._settings_save_request_id = 4
        page._pending_settings_save = {
            "profile_key": "profile-1",
            "filter_kind": "hostlist",
            "filter_value": "lists/new.txt",
            "in_range": "x",
            "out_range": "a",
        }

        with patch("profile.ui.profile_setup_page.log") as log_mock:
            ProfileSetupPageBase._on_settings_save_failed(page, 4, "old error")

        log_mock.assert_not_called()

    def test_strategy_list_uses_fluent_item_tooltip(self) -> None:
        delegate_init = inspect.getsource(ProfileStrategyListDelegate.__init__)
        help_event = inspect.getsource(ProfileStrategyListDelegate.helpEvent)

        self.assertIn("FluentItemToolTipController", delegate_init)
        self.assertIn("_ROLE_TOOLTIP_TEXT", help_event)
        self.assertIn("show_text", help_event)

    def test_strategy_and_preset_lists_share_hover_row_painter(self) -> None:
        from profile.ui.profile_list_delegate import ProfileListDelegate

        strategy_paint = inspect.getsource(ProfileStrategyListDelegate.paint)
        preset_paint = inspect.getsource(PresetListDelegate._paint_preset_row)
        profile_paint = inspect.getsource(ProfileListDelegate._paint_profile_row)

        self.assertIn("paint_profile_hover_row", strategy_paint)
        self.assertIn("profile_hover_row_rect", strategy_paint)
        self.assertIn("paint_profile_hover_row", preset_paint)
        self.assertIn("profile_hover_row_rect", preset_paint)
        self.assertIn("paint_profile_hover_row", profile_paint)
        self.assertIn("profile_hover_row_rect", profile_paint)

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
                self.deleteLater = Mock()

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._payload = SimpleNamespace(item=SimpleNamespace(strategy_id="pass", in_preset=True, enabled=True))
        page._strategy_apply_request_id = 0
        page._pending_strategy_apply = None
        worker = _Worker()
        page.create_profile_strategy_apply_worker = Mock(return_value=worker)
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()
        page._apply_strategy_detail = Mock(side_effect=AssertionError("detail page must not open"))
        page._apply_strategy_locally = Mock(return_value=True)

        ProfileSetupPageBase._on_strategy_list_activated(page, "tls_fake")

        page.create_profile_strategy_apply_worker.assert_called_once_with(
            1,
            profile_key="profile-1",
            strategy_id="tls_fake",
            parent=page,
        )
        page.reload_current_profile.assert_not_called()
        page._apply_strategy_locally.assert_called_once_with("tls_fake")
        page._on_profile_changed_callback.assert_not_called()
        worker.start.assert_called_once()

    def test_clicking_template_strategy_applies_worker_payload_without_reload(self) -> None:
        class _Signal:
            def connect(self, _callback) -> None:
                pass

        class _Worker:
            def __init__(self) -> None:
                self.applied = _Signal()
                self.failed = _Signal()
                self.finished = _Signal()
                self.start = Mock()
                self.deleteLater = Mock()

        item = SimpleNamespace(key="profile-1", strategy_id="tls_fake", in_preset=True, enabled=True)
        payload = SimpleNamespace(item=item)
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "template:profile-1"
        page._payload = SimpleNamespace(item=SimpleNamespace(strategy_id="none", in_preset=False, enabled=True))
        page._strategy_apply_request_id = 0
        page._pending_strategy_apply = None
        page.create_profile_strategy_apply_worker = Mock(return_value=_Worker())
        page.reload_current_profile = Mock()
        page._apply_payload = Mock()
        page._on_profile_changed_callback = Mock()
        page._apply_strategy_locally = Mock(return_value=False)
        callbacks = []

        ProfileSetupPageBase._on_strategy_list_activated(page, "tls_fake")

        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_strategy_apply_finished(
                page,
                1,
                "template:profile-1",
                "profile-1",
                "tls_fake",
                payload,
            )

        page.reload_current_profile.assert_not_called()
        page._apply_payload.assert_not_called()
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        page._apply_payload.assert_called_once_with(payload)
        page._on_profile_changed_callback.assert_called_once_with("profile-1", "strategy", item)

    def test_in_preset_strategy_finish_keeps_local_ui_when_worker_returns_payload(self) -> None:
        current_item = SimpleNamespace(key="profile-1", strategy_id="tls_fake", in_preset=True, enabled=True)
        worker_item = SimpleNamespace(key="profile-1", strategy_id="tls_fake", in_preset=True, enabled=True)
        worker_payload = SimpleNamespace(item=worker_item)
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "profile-1"
        page._strategy_apply_request_id = 1
        page._pending_strategy_apply = None
        page._payload = SimpleNamespace(item=current_item)
        page._apply_payload = Mock(side_effect=AssertionError("already applied strategy must not repaint full page"))
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()
        page._apply_strategy_locally = Mock(side_effect=AssertionError("strategy was already applied locally"))

        ProfileSetupPageBase._on_strategy_apply_finished(
            page,
            1,
            "profile-1",
            "profile-1",
            "tls_fake",
            worker_payload,
        )

        page._apply_payload.assert_not_called()
        page._apply_strategy_locally.assert_not_called()
        page.reload_current_profile.assert_not_called()
        page._on_profile_changed_callback.assert_called_once_with("profile-1", "strategy", current_item)

    def test_clicking_strategy_while_apply_is_running_keeps_last_choice_pending(self) -> None:
        class _Runtime:
            def is_running(self) -> bool:
                return True

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._payload = SimpleNamespace(item=SimpleNamespace(strategy_id="first", in_preset=True, enabled=True))
        page._strategy_apply_runtime = _Runtime()
        page._strategy_apply_request_id = 1
        page._strategy_apply_runtime_strategy_id = "first"
        page._pending_strategy_apply = None
        page.create_profile_strategy_apply_worker = Mock()
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()
        page._apply_strategy_locally = Mock(return_value=True)

        ProfileSetupPageBase._on_strategy_list_activated(page, "second")

        page._apply_strategy_locally.assert_called_once_with("second")
        self.assertEqual(page._pending_strategy_apply, "second")
        page.create_profile_strategy_apply_worker.assert_not_called()
        page._on_profile_changed_callback.assert_not_called()

    def test_clicking_strategy_while_apply_is_running_preserves_branch_pending(self) -> None:
        class _Runtime:
            def is_running(self) -> bool:
                return True

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._payload = SimpleNamespace(
            item=SimpleNamespace(strategy_id="first", in_preset=True, enabled=True),
            current_strategy_branch_id="branch:2",
            strategy_branches=(
                SimpleNamespace(branch_id="branch:1", strategy_id="first"),
                SimpleNamespace(branch_id="branch:2", strategy_id="first"),
            ),
        )
        page._strategy_apply_runtime = _Runtime()
        page._strategy_apply_request_id = 1
        page._strategy_apply_runtime_strategy_id = "first"
        page._strategy_apply_runtime_branch_id = "branch:1"
        page._pending_strategy_apply = None
        page.create_profile_strategy_apply_worker = Mock()
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()
        page._apply_strategy_locally = Mock(return_value=True)

        ProfileSetupPageBase._on_strategy_list_activated(page, "second")

        page._apply_strategy_locally.assert_called_once_with("second")
        self.assertEqual(page._pending_strategy_apply, ("second", "branch:2"))
        page.create_profile_strategy_apply_worker.assert_not_called()
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

    def test_strategy_apply_reload_result_refreshes_profile_without_local_reapply(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "profile-1"
        page._strategy_apply_request_id = 1
        page._pending_strategy_apply = None
        page._apply_strategy_locally = Mock(side_effect=AssertionError("reload result must not be applied locally"))
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()
        worker_result = SimpleNamespace(
            payload=None,
            apply_signature=(None,),
            apply_result=SimpleNamespace(status="profile_missing", profile_key="", should_reload=True),
        )

        ProfileSetupPageBase._on_strategy_apply_finished(
            page,
            1,
            "profile-1",
            "",
            "tls_fake",
            worker_result,
        )

        page.reload_current_profile.assert_called_once_with()
        page._on_profile_changed_callback.assert_called_once_with("profile-1", "strategy")
        page._apply_strategy_locally.assert_not_called()

    def test_stale_strategy_apply_worker_finished_does_not_flush_pending_choice(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._strategy_apply_request_id = 4
        page._strategy_apply_runtime_strategy_id = "current"
        page._strategy_apply_runtime_branch_id = "branch:1"
        page._pending_strategy_apply = "second"
        page._start_next_profile_setup_write_operation = Mock(
            side_effect=AssertionError("stale worker must not drive write queue")
        )
        page._schedule_profile_setup_write_operation_start = Mock()

        ProfileSetupPageBase._on_strategy_apply_worker_finished(page, SimpleNamespace(_request_id=3))

        self.assertEqual(page._strategy_apply_request_id, 4)
        self.assertEqual(page._strategy_apply_runtime_strategy_id, "current")
        self.assertEqual(page._strategy_apply_runtime_branch_id, "branch:1")
        self.assertEqual(page._pending_strategy_apply, "second")
        page._schedule_profile_setup_write_operation_start.assert_not_called()

    def test_cleared_strategy_apply_worker_finished_does_not_flush_pending_choice(self) -> None:
        old_worker = object()
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._strategy_apply_request_id = 4
        page._strategy_apply_runtime_strategy_id = "current"
        page._strategy_apply_runtime_branch_id = "branch:1"
        page._pending_strategy_apply = "second"
        page._start_next_profile_setup_write_operation = Mock(
            side_effect=AssertionError("cleared strategy worker must not drive write queue")
        )
        page._schedule_profile_setup_write_operation_start = Mock()

        ProfileSetupPageBase._on_strategy_apply_worker_finished(page, old_worker)

        self.assertEqual(page._strategy_apply_request_id, 4)
        self.assertEqual(page._strategy_apply_runtime_strategy_id, "current")
        self.assertEqual(page._strategy_apply_runtime_branch_id, "branch:1")
        self.assertEqual(page._pending_strategy_apply, "second")
        page._schedule_profile_setup_write_operation_start.assert_not_called()

    def test_stale_list_file_save_worker_finished_does_not_drive_write_queue(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_save_request_id = 4
        page._pending_list_file_save = ("profile-1", "example.com")
        page._start_next_profile_setup_write_operation = Mock(
            side_effect=AssertionError("stale list file worker must not drive write queue")
        )
        page._schedule_pending_list_file_save_start = Mock()

        ProfileSetupPageBase._on_list_file_save_worker_finished(page, SimpleNamespace(_request_id=3))

        self.assertEqual(page._list_file_save_request_id, 4)
        self.assertEqual(page._pending_list_file_save, ("profile-1", "example.com"))
        page._schedule_pending_list_file_save_start.assert_not_called()

    def test_stale_settings_save_worker_finished_does_not_drive_write_queue(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._settings_save_request_id = 4
        page._pending_settings_save = {"filter_kind": "hostlist"}
        page._start_next_profile_setup_write_operation = Mock(
            side_effect=AssertionError("stale settings worker must not drive write queue")
        )
        page._schedule_profile_setup_write_operation_start = Mock()

        ProfileSetupPageBase._on_settings_save_worker_finished(page, SimpleNamespace(_request_id=3))

        self.assertEqual(page._settings_save_request_id, 4)
        self.assertEqual(page._pending_settings_save, {"filter_kind": "hostlist"})
        page._schedule_profile_setup_write_operation_start.assert_not_called()

    def test_cleared_settings_save_worker_finished_does_not_drive_write_queue(self) -> None:
        old_worker = object()
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._settings_save_request_id = 4
        page._pending_settings_save = {"filter_kind": "hostlist"}
        page._start_next_profile_setup_write_operation = Mock(
            side_effect=AssertionError("cleared settings worker must not drive write queue")
        )
        page._schedule_profile_setup_write_operation_start = Mock()

        ProfileSetupPageBase._on_settings_save_worker_finished(page, old_worker)

        self.assertEqual(page._settings_save_request_id, 4)
        self.assertEqual(page._pending_settings_save, {"filter_kind": "hostlist"})
        page._schedule_profile_setup_write_operation_start.assert_not_called()

    def test_stale_raw_profile_save_worker_finished_does_not_drive_write_queue(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._raw_profile_save_request_id = 4
        page._pending_raw_profile_save = ("profile-1", "--filter-tcp=443")
        page._start_next_profile_setup_write_operation = Mock(
            side_effect=AssertionError("stale raw profile worker must not drive write queue")
        )
        page._schedule_profile_setup_write_operation_start = Mock()

        ProfileSetupPageBase._on_raw_profile_save_worker_finished(page, SimpleNamespace(_request_id=3))

        self.assertEqual(page._raw_profile_save_request_id, 4)
        self.assertEqual(page._pending_raw_profile_save, ("profile-1", "--filter-tcp=443"))
        page._schedule_profile_setup_write_operation_start.assert_not_called()

    def test_stale_enabled_save_worker_finished_does_not_drive_write_queue(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._enabled_save_request_id = 4
        page._enabled_save_runtime_enabled = True
        page._pending_enabled_save = False
        page._start_next_profile_setup_write_operation = Mock(
            side_effect=AssertionError("stale enabled worker must not drive write queue")
        )
        page._schedule_enabled_save_worker_start = Mock()

        ProfileSetupPageBase._on_enabled_save_worker_finished(page, SimpleNamespace(_request_id=3))

        self.assertEqual(page._enabled_save_request_id, 4)
        self.assertIs(page._enabled_save_runtime_enabled, True)
        self.assertIs(page._pending_enabled_save, False)
        page._schedule_enabled_save_worker_start.assert_not_called()

    def test_stale_strategy_feedback_save_worker_finished_does_not_reschedule_pending_save(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._strategy_feedback_save_request_id = 4
        page._pending_strategy_feedback_save = {"rating": "work"}
        page._schedule_strategy_feedback_save_worker_start = Mock(
            side_effect=AssertionError("stale feedback worker must not reschedule save")
        )

        ProfileSetupPageBase._on_strategy_feedback_save_worker_finished(page, SimpleNamespace(_request_id=3))

        self.assertEqual(page._strategy_feedback_save_request_id, 4)
        self.assertEqual(page._pending_strategy_feedback_save, {"rating": "work"})
        page._schedule_strategy_feedback_save_worker_start.assert_not_called()

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

    def test_strategy_apply_finish_passes_updated_item_to_preset_page(self) -> None:
        updated_item = SimpleNamespace(strategy_id="tls_fake", in_preset=True, enabled=True)
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "profile-1"
        page._strategy_apply_request_id = 1
        page._pending_strategy_apply = None
        page._payload = SimpleNamespace(item=updated_item)
        page._apply_strategy_locally = Mock(return_value=True)
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()

        ProfileSetupPageBase._on_strategy_apply_finished(page, 1, "profile-1", "profile-1", "tls_fake")

        page.reload_current_profile.assert_not_called()
        page._on_profile_changed_callback.assert_called_once_with("profile-1", "strategy", updated_item)

    def test_strategy_apply_finish_does_not_apply_same_strategy_locally_again(self) -> None:
        updated_item = SimpleNamespace(strategy_id="tls_fake", in_preset=True, enabled=True)
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "profile-1"
        page._strategy_apply_request_id = 1
        page._pending_strategy_apply = None
        page._payload = SimpleNamespace(item=updated_item)
        page._apply_strategy_locally = Mock(side_effect=AssertionError("confirmed strategy must not redraw twice"))
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()

        ProfileSetupPageBase._on_strategy_apply_finished(page, 1, "profile-1", "profile-1", "tls_fake")

        page._apply_strategy_locally.assert_not_called()
        page.reload_current_profile.assert_not_called()
        page._on_profile_changed_callback.assert_called_once_with("profile-1", "strategy", updated_item)

    def test_apply_strategy_locally_does_not_rebuild_breadcrumb(self) -> None:
        item = ProfileListItem(
            key="profile-1",
            persistent_key="profile-1",
            profile_index=0,
            display_name="YouTube",
            enabled=True,
            in_preset=True,
            strategy_id="old",
            strategy_name="Old",
            match_lines=(),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="video",
            group_name="Video",
            order=0,
        )
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._payload = ProfileSetupPayload(
            item=item,
            strategy_entries={
                "tls_fake": StrategyEntry(
                    strategy_id="tls_fake",
                    catalog_name="tls",
                    name="TLS fake",
                    args="--lua-desync=fake",
                    visual=SimpleNamespace(label="", description=""),
                ),
            },
            strategy_states={"tls_fake": ProfileStrategyState(rating="work", favorite=False)},
            raw_profile_text="",
            raw_strategy_text="",
            match_summary="",
        )
        page._strategy_list = SimpleNamespace(set_current_strategy_id=Mock())
        page._apply_feedback_buttons = Mock()
        page._match_tab_built = False
        page._apply_match_tab_payload = Mock()
        page._rebuild_breadcrumb = Mock(side_effect=AssertionError("strategy change must not rebuild breadcrumbs"))

        self.assertTrue(ProfileSetupPageBase._apply_strategy_locally(page, "tls_fake"))

        page._strategy_list.set_current_strategy_id.assert_called_once_with("tls_fake")
        page._apply_feedback_buttons.assert_called_once()
        page._apply_match_tab_payload.assert_not_called()
        page._rebuild_breadcrumb.assert_not_called()

    def test_apply_strategy_locally_updates_profile_item_when_payload_has_branch(self) -> None:
        item = ProfileListItem(
            key="profile-1",
            persistent_key="profile-1",
            profile_index=0,
            display_name="YouTube",
            enabled=True,
            in_preset=True,
            strategy_id="old",
            strategy_name="Old",
            match_lines=(),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="video",
            group_name="Video",
            order=0,
        )
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._payload = ProfileSetupPayload(
            item=item,
            strategy_entries={
                "tls_fake": StrategyEntry(
                    strategy_id="tls_fake",
                    catalog_name="tls",
                    name="TLS fake",
                    args="--payload=tls_client_hello\n--lua-desync=fake",
                    visual=SimpleNamespace(label="", description=""),
                ),
            },
            strategy_states={"tls_fake": ProfileStrategyState(rating="work", favorite=True)},
            raw_profile_text="",
            raw_strategy_text="",
            match_summary="",
            current_strategy_branch_id="branch:0",
            strategy_branches=(
                ProfileStrategyBranch(
                    branch_id="branch:0",
                    payload="tls_client_hello",
                    in_range="x",
                    out_range="a",
                    strategy_id="old",
                    strategy_name="Old",
                    raw_strategy_text="--payload=tls_client_hello\n--lua-desync=old",
                    match_tab_text="Old match",
                ),
            ),
        )
        page._strategy_list = SimpleNamespace(set_current_strategy_id=Mock())
        page._apply_strategy_branch_selector = Mock()
        page._apply_feedback_buttons = Mock()
        page._match_tab_built = False
        page._apply_match_tab_payload = Mock()

        self.assertTrue(ProfileSetupPageBase._apply_strategy_locally(page, "tls_fake"))

        self.assertEqual(page._payload.item.strategy_id, "tls_fake")
        self.assertEqual(page._payload.item.strategy_name, "TLS fake")
        self.assertEqual(page._payload.item.rating, "work")
        self.assertTrue(page._payload.item.favorite)

    def test_strategy_branch_selector_updates_labels_without_rebuilding_combo(self) -> None:
        class _Bar:
            def __init__(self) -> None:
                self._visible = True

            def isVisible(self) -> bool:  # noqa: N802
                return self._visible

            def setVisible(self, visible: bool) -> None:  # noqa: N802
                self._visible = bool(visible)

        class _Combo:
            def __init__(self) -> None:
                self.rows: list[tuple[str, str]] = []
                self.current_index = 0
                self.clear_calls = 0
                self.add_calls = 0
                self.text_updates: list[tuple[int, str]] = []

            def blockSignals(self, _blocked: bool) -> None:  # noqa: N802
                pass

            def clear(self) -> None:
                self.clear_calls += 1
                self.rows.clear()

            def addItem(self, text: str, userData: str = "") -> None:  # noqa: N802
                self.add_calls += 1
                self.rows.append((str(text), str(userData)))

            def count(self) -> int:
                return len(self.rows)

            def itemData(self, index: int):
                return self.rows[index][1]

            def itemText(self, index: int) -> str:  # noqa: N802
                return self.rows[index][0]

            def setItemText(self, index: int, text: str) -> None:  # noqa: N802
                self.text_updates.append((index, str(text)))
                self.rows[index] = (str(text), self.rows[index][1])

            def currentIndex(self) -> int:  # noqa: N802
                return self.current_index

            def setCurrentIndex(self, index: int) -> None:  # noqa: N802
                self.current_index = int(index)

        def _payload(first_name: str):
            return SimpleNamespace(
                current_strategy_branch_id="branch:1",
                strategy_branches=(
                    SimpleNamespace(
                        branch_id="branch:1",
                        payload="tls",
                        in_range="",
                        out_range="",
                        strategy_name=first_name,
                    ),
                    SimpleNamespace(
                        branch_id="branch:2",
                        payload="http",
                        in_range="",
                        out_range="",
                        strategy_name="HTTP fake",
                    ),
                ),
            )

        combo = _Combo()
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._strategy_branch_combo = combo
        page._strategy_branch_bar = _Bar()

        ProfileSetupPageBase._apply_strategy_branch_selector(page, _payload("Old TLS"))
        ProfileSetupPageBase._apply_strategy_branch_selector(page, _payload("New TLS"))

        self.assertEqual(combo.clear_calls, 1)
        self.assertEqual(combo.add_calls, 2)
        self.assertEqual(combo.text_updates, [(0, "payload: tls — New TLS")])

    def test_strategy_branch_change_updates_visible_range_settings(self) -> None:
        class _Combo:
            def __init__(self) -> None:
                self.current_index = 1
                self.rows = ("branch:1", "branch:2")

            def currentIndex(self) -> int:  # noqa: N802
                return self.current_index

            def itemData(self, index: int):
                return self.rows[index]

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._strategy_branch_combo = _Combo()
        page._payload = ProfileSetupPayload(
            item=SimpleNamespace(in_preset=True, enabled=True),
            strategy_entries={},
            raw_profile_text="",
            raw_strategy_text="--lua-desync=fake",
            match_summary="",
            current_strategy_branch_id="branch:1",
            in_range="x",
            out_range="a",
            strategy_states={"http_fake": ProfileStrategyState(rating="work")},
            strategy_branches=(
                ProfileStrategyBranch(
                    branch_id="branch:1",
                    payload="tls_client_hello",
                    in_range="x",
                    out_range="a",
                    strategy_id="tls_fake",
                    strategy_name="TLS fake",
                    raw_strategy_text="--lua-desync=fake",
                    match_tab_text="TLS branch",
                ),
                ProfileStrategyBranch(
                    branch_id="branch:2",
                    payload="http_req",
                    in_range="x",
                    out_range="-d8",
                    strategy_id="http_fake",
                    strategy_name="HTTP fake",
                    raw_strategy_text="--out-range=-d8\n--payload=http_req\n--lua-desync=fake",
                    match_tab_text="HTTP branch",
                ),
            ),
        )
        page._strategy_list = SimpleNamespace(set_current_strategy_id=Mock())
        page._apply_editable_settings = Mock()
        page._apply_feedback_buttons = Mock()
        page._match_tab_built = False
        page._apply_match_tab_payload = Mock()

        ProfileSetupPageBase._on_strategy_branch_changed(page, 1)

        self.assertEqual(page._payload.current_strategy_branch_id, "branch:2")
        self.assertEqual(page._payload.in_range, "x")
        self.assertEqual(page._payload.out_range, "-d8")
        page._apply_editable_settings.assert_called_once_with(page._payload)
        page._strategy_list.set_current_strategy_id.assert_called_once_with("http_fake")

    def test_strategy_apply_worker_emits_new_profile_key(self) -> None:
        apply_result = SimpleNamespace(status="applied", profile_key="profile-1", should_reload=False)
        apply_strategy = Mock(return_value=apply_result)
        load_profile = Mock()
        payload = SimpleNamespace(item=SimpleNamespace(key="profile-1"))
        load_profile.return_value = payload
        worker = ProfileStrategyApplyWorker(9, apply_strategy, load_profile, "template:profile-1", "tls_fake")
        applied = []

        worker.applied.connect(
            lambda request_id, requested_profile_key, profile_key, strategy_id, emitted_payload: applied.append((
                request_id,
                requested_profile_key,
                profile_key,
                strategy_id,
                emitted_payload,
            ))
        )

        worker.run()

        apply_strategy.assert_called_once_with(
            profile_key="template:profile-1",
            strategy_id="tls_fake",
        )
        load_profile.assert_called_once_with("profile-1")
        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0][:4], (9, "template:profile-1", "profile-1", "tls_fake"))
        self.assertIs(applied[0][4].payload, payload)
        self.assertTrue(applied[0][4].apply_signature)

    def test_strategy_apply_worker_emits_reload_result_without_error_when_profile_is_missing(self) -> None:
        apply_result = SimpleNamespace(status="profile_missing", profile_key="", should_reload=True)
        apply_strategy = Mock(return_value=apply_result)
        load_profile = Mock(side_effect=AssertionError("missing profile must not be loaded"))
        worker = ProfileStrategyApplyWorker(9, apply_strategy, load_profile, "profile:0", "tls_fake")
        applied = []
        failed = []

        worker.applied.connect(
            lambda request_id, requested_profile_key, profile_key, strategy_id, emitted_payload: applied.append((
                request_id,
                requested_profile_key,
                profile_key,
                strategy_id,
                emitted_payload,
            ))
        )
        worker.failed.connect(lambda request_id, error: failed.append((request_id, error)))

        worker.run()

        self.assertEqual(failed, [])
        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0][:4], (9, "profile:0", "", "tls_fake"))
        self.assertIsNone(applied[0][4].payload)
        self.assertIs(applied[0][4].apply_result, apply_result)

    def test_strategy_apply_worker_skips_profile_load_when_result_says_payload_is_unchanged(self) -> None:
        apply_result = SimpleNamespace(
            status="already_applied",
            profile_key="profile:0",
            should_reload=False,
            profile_payload_changed=False,
        )
        apply_strategy = Mock(return_value=apply_result)
        load_profile = Mock(side_effect=AssertionError("unchanged strategy must not load profile payload"))
        worker = ProfileStrategyApplyWorker(9, apply_strategy, load_profile, "profile:0", "tls_fake")
        applied = []

        worker.applied.connect(
            lambda request_id, requested_profile_key, profile_key, strategy_id, emitted_payload: applied.append((
                request_id,
                requested_profile_key,
                profile_key,
                strategy_id,
                emitted_payload,
            ))
        )

        worker.run()

        load_profile.assert_not_called()
        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0][:4], (9, "profile:0", "profile:0", "tls_fake"))
        self.assertIsNone(applied[0][4].payload)
        self.assertIs(applied[0][4].apply_result, apply_result)

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
                self.deleteLater = Mock()

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
        worker = _Worker()
        page.create_profile_strategy_feedback_save_worker = Mock(return_value=worker)
        page._strategy_feedback_save_request_id = 0
        page._strategy_list = Mock()
        page._apply_feedback_buttons = Mock()
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()

        ProfileSetupPageBase._set_current_strategy_feedback(page, rating="work")

        page.create_profile_strategy_feedback_save_worker.assert_called_once_with(
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
        page._on_profile_changed_callback.assert_called_once_with("profile-1", "feedback", page._payload.item)

    def test_repeating_same_strategy_rating_does_not_start_feedback_worker(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._payload = SimpleNamespace(
            current_strategy_state=ProfileStrategyState(rating="work", favorite=False),
        )
        page._request_strategy_feedback_save = Mock(side_effect=AssertionError("same rating must not start worker"))

        ProfileSetupPageBase._set_current_strategy_feedback(page, rating="work")

        page._request_strategy_feedback_save.assert_not_called()

    def test_strategy_feedback_pending_save_merges_rating_and_favorite_while_worker_runs(self) -> None:
        class _Runtime:
            def is_running(self) -> bool:
                return True

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._strategy_feedback_save_runtime = _Runtime()
        page._pending_strategy_feedback_save = None
        page._start_strategy_feedback_save_worker = Mock()

        ProfileSetupPageBase._request_strategy_feedback_save(
            page,
            {"rating": "work", "favorite": None},
        )
        ProfileSetupPageBase._request_strategy_feedback_save(
            page,
            {"rating": None, "favorite": True},
        )

        self.assertEqual(
            page._pending_strategy_feedback_save,
            {"rating": "work", "favorite": True},
        )
        page._start_strategy_feedback_save_worker.assert_not_called()

    def test_strategy_feedback_scheduled_restart_merges_latest_pending_request(self) -> None:
        import profile.ui.profile_setup_page as profile_setup_page

        class _Runtime:
            def is_running(self) -> bool:
                return False

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._strategy_feedback_save_request_id = 1
        page._strategy_feedback_save_runtime = _Runtime()
        page._pending_strategy_feedback_save = {"rating": "work", "favorite": None}
        page._start_strategy_feedback_save_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(profile_setup_page, "QTimer", SimpleNamespace(singleShot=single_shot)):
            ProfileSetupPageBase._on_strategy_feedback_save_worker_finished(
                page, SimpleNamespace(_request_id=1)
            )
            ProfileSetupPageBase._request_strategy_feedback_save(
                page,
                {"rating": None, "favorite": True},
            )

        page._start_strategy_feedback_save_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_strategy_feedback_save_worker.assert_called_once_with(
            {"rating": "work", "favorite": True}
        )

    def test_strategy_feedback_scheduled_restart_clears_pending_during_cleanup(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._cleanup_in_progress = True
        page._strategy_feedback_save_start_scheduled = True
        page._pending_strategy_feedback_save = {"rating": "work", "favorite": True}
        page._start_strategy_feedback_save_worker = Mock()

        ProfileSetupPageBase._run_scheduled_strategy_feedback_save_worker_start(page)

        self.assertFalse(page._strategy_feedback_save_start_scheduled)
        self.assertIsNone(page._pending_strategy_feedback_save)
        page._start_strategy_feedback_save_worker.assert_not_called()

    def test_strategy_feedback_finish_skips_duplicate_state(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "profile-1"
        page._strategy_feedback_save_request_id = 1
        page._pending_strategy_feedback_save = None
        page._payload = SimpleNamespace(
            item=SimpleNamespace(strategy_id="tls_fake", rating="work", favorite=False),
            current_strategy_state=ProfileStrategyState(rating="work", favorite=False),
        )
        page._apply_strategy_feedback_locally = Mock(
            side_effect=AssertionError("duplicate feedback state must not repaint strategy list")
        )
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()

        ProfileSetupPageBase._on_strategy_feedback_save_finished(
            page,
            1,
            "profile-1",
            "tls_fake",
            ProfileStrategyState(rating="work", favorite=False),
        )

        page._apply_strategy_feedback_locally.assert_not_called()
        page.reload_current_profile.assert_not_called()
        page._on_profile_changed_callback.assert_not_called()

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

    def test_show_profile_skips_reload_when_profile_is_already_loaded(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "profile-1"
        page._payload = SimpleNamespace(item=SimpleNamespace(key="profile-1"))
        page.reload_current_profile = Mock(side_effect=AssertionError("same loaded profile must not reload"))

        ProfileSetupPageBase.show_profile(page, "profile-1")

        page.reload_current_profile.assert_not_called()

    def test_show_profile_clears_stale_payload_when_switching_profile(self) -> None:
        old_payload = SimpleNamespace(item=SimpleNamespace(key="deleted-profile"))
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "deleted-profile"
        page._payload = old_payload
        page._pending_profile_setup_payload_apply = (old_payload, ("deleted-profile",))
        page._profile_setup_payload_apply_scheduled = True
        page._last_profile_setup_payload_apply_signature = ("deleted-profile",)
        page.reload_current_profile = Mock()

        ProfileSetupPageBase.show_profile(page, "profile-2")

        self.assertEqual(page._profile_key, "profile-2")
        self.assertIsNone(page._payload)
        self.assertIsNone(page._pending_profile_setup_payload_apply)
        self.assertFalse(page._profile_setup_payload_apply_scheduled)
        self.assertIsNone(page._last_profile_setup_payload_apply_signature)
        page.reload_current_profile.assert_called_once_with()

    def test_loaded_same_profile_payload_skips_full_repaint(self) -> None:
        payload = SimpleNamespace(
            item=SimpleNamespace(enabled=True),
            match_summary="TCP 443",
        )
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._setup_load_request_id = 7
        page._payload = payload
        page._summary = _TextWidget("Загрузка profile...")
        page._enabled_checkbox = _EnabledWidget(False)
        page._enabled_checkbox.isChecked = Mock(return_value=True)
        page._enabled_checkbox.setChecked = Mock()
        page._apply_payload = Mock(side_effect=AssertionError("same payload must not repaint profile page"))

        ProfileSetupPageBase._on_profile_setup_payload_loaded(page, 7, payload)

        page._apply_payload.assert_not_called()
        self.assertEqual(page._summary.text(), "TCP 443")
        self.assertEqual(page._enabled_checkbox.enabled_calls, [True])
        page._enabled_checkbox.setChecked.assert_not_called()

    def test_loaded_profile_setup_payload_apply_is_deferred_after_worker_signal(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._setup_load_request_id = 7
        page._cleanup_in_progress = False
        page._payload = None
        page._apply_payload = Mock()
        payload = SimpleNamespace(
            item=SimpleNamespace(enabled=True),
            match_summary="TCP 443",
        )
        callbacks = []

        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_profile_setup_payload_loaded(page, 7, payload)

        page._apply_payload.assert_not_called()
        self.assertIs(page._payload, payload)
        self.assertEqual(len(callbacks), 1)

        callbacks[0]()

        page._apply_payload.assert_called_once_with(payload)

    def test_loaded_profile_setup_result_uses_worker_apply_signature(self) -> None:
        payload = SimpleNamespace(
            item=SimpleNamespace(enabled=True),
            match_summary="TCP 443",
        )
        result = SimpleNamespace(payload=payload, apply_signature=("profile", "same"))
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._setup_load_request_id = 7
        page._setup_load_dirty = False
        page._last_profile_setup_payload_apply_signature = ("profile", "same")
        page._payload = payload
        page._summary = _TextWidget("Загрузка profile...")
        page._enabled_checkbox = _EnabledWidget(False)
        page._enabled_checkbox.isChecked = Mock(return_value=True)
        page._enabled_checkbox.setChecked = Mock()
        page._schedule_profile_setup_payload_apply = Mock(
            side_effect=AssertionError("same worker signature must not repaint profile page")
        )

        ProfileSetupPageBase._on_profile_setup_payload_loaded(page, 7, result)

        page._schedule_profile_setup_payload_apply.assert_not_called()
        self.assertEqual(page._summary.text(), "TCP 443")
        self.assertEqual(page._enabled_checkbox.enabled_calls, [True])
        page._enabled_checkbox.setChecked.assert_not_called()

    def test_profile_setup_load_result_precomputes_apply_signature(self) -> None:
        item = ProfileListItem(
            key="profile-1",
            persistent_key="profile-1",
            profile_index=1,
            display_name="Profile",
            enabled=True,
            in_preset=True,
            strategy_id="strategy",
            strategy_name="Strategy",
            match_lines=("--filter-tcp=443",),
            list_type="hostlist",
            rating="",
            favorite=False,
            group="common",
            group_name="",
            order=1,
        )
        payload = ProfileSetupPayload(
            item=item,
            strategy_entries={},
            strategy_states={},
            raw_profile_text="",
            raw_strategy_text="--dpi-desync=fake",
            match_summary="TCP 443",
        )

        result = ProfileSetupLoadResult(payload=payload)

        self.assertIs(result.payload, payload)
        self.assertTrue(result.apply_signature)

    def test_loaded_profile_setup_payload_is_ignored_while_new_load_is_pending(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._setup_load_request_id = 7
        page._setup_load_dirty = True
        page._payload = None
        page._schedule_profile_setup_payload_apply = Mock(
            side_effect=AssertionError("pending newer profile setup load must own the page payload")
        )
        payload = SimpleNamespace(
            item=SimpleNamespace(enabled=True),
            match_summary="TCP 443",
        )

        ProfileSetupPageBase._on_profile_setup_payload_loaded(page, 7, payload)

        self.assertIsNone(page._payload)
        self.assertTrue(page._setup_load_dirty)
        page._schedule_profile_setup_payload_apply.assert_not_called()

    def test_profile_setup_worker_result_payloads_use_deferred_apply(self) -> None:
        from profile.ui.profile_list_file_editor_controller import ProfileListFileEditorController

        from profile.ui.profile_setup_save_controllers import ProfileSetupSaveController
        from profile.ui.profile_strategy_controller import ProfileStrategyController

        handlers = (
            ProfileSetupPageBase._apply_user_profile_update_locally,
            ProfileListFileEditorController._on_list_file_save_finished,
            ProfileSetupSaveController._on_settings_save_finished,
            ProfileSetupSaveController._on_raw_profile_save_finished,
            ProfileSetupSaveController._on_enabled_save_finished,
            ProfileStrategyController._on_strategy_apply_finished,
        )

        for handler in handlers:
            source = inspect.getsource(handler)
            self.assertNotIn("self._apply_payload(payload)", source)
            self.assertNotIn("self._apply_payload(self._payload)", source)
            self.assertIn("_schedule_profile_setup_payload_apply", source)

    def test_strategy_feedback_worker_emits_state(self) -> None:
        state = ProfileStrategyState(rating="work", favorite=True)
        save_feedback = Mock(return_value=state)
        worker = ProfileStrategyFeedbackSaveWorker(
            10,
            save_feedback,
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

        save_feedback.assert_called_once_with(
            profile_key="profile-1",
            rating="work",
            favorite=True,
        )
        self.assertEqual(saved, [(10, "profile-1", "tls_fake", state)])

    def test_clicking_current_strategy_does_not_apply_strategy_again(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._payload = SimpleNamespace(item=SimpleNamespace(in_preset=True, enabled=True, strategy_id="tls_fake"))
        page._apply_strategy_locally = Mock(side_effect=AssertionError("current strategy must not be applied again"))
        page._request_strategy_apply = Mock(side_effect=AssertionError("current strategy must not start worker again"))
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()

        ProfileSetupPageBase._on_strategy_list_activated(page, "tls_fake")

        page._apply_strategy_locally.assert_not_called()
        page._request_strategy_apply.assert_not_called()
        page.reload_current_profile.assert_not_called()
        page._on_profile_changed_callback.assert_not_called()

    def test_clicking_strategy_for_skipped_profile_does_not_apply_strategy(self) -> None:
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._loading = False
        page._profile_key = "profile-1"
        page._payload = SimpleNamespace(item=SimpleNamespace(in_preset=True, enabled=False))
        page.create_profile_strategy_apply_worker = Mock()
        page.reload_current_profile = Mock()
        page._on_profile_changed_callback = Mock()

        ProfileSetupPageBase._on_strategy_list_activated(page, "tls_fake")

        page.create_profile_strategy_apply_worker.assert_not_called()
        page.reload_current_profile.assert_not_called()
        page._on_profile_changed_callback.assert_not_called()

if __name__ == "__main__":
    unittest.main()
