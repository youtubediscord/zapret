from __future__ import annotations

import inspect
import importlib
import importlib.util
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from profile import commands as profile_commands
import profile.additional_settings_loader as profile_additional_settings_loader
import profile.profile_setup_loader as profile_setup_loader
from profile.profile_list_loader import ProfileListLoadWorker
from profile.service import ProfilePresetService
from profile.ui.profile_list_model import ProfileListModel as ProfileSetupListModel
from profile.ui.profiles_list import ProfilesList
from profile.ui.profile_setup_page import ProfileSetupPageBase
from profile.ui.preset_setup_page import PresetSetupPageBase
from presets import display_state
from presets import commands as preset_commands
from presets.ui.common.preset_subpage_base import PresetRawEditorPage
from presets.ui.common.user_presets_page import UserPresetsPageBase
from presets.raw_preset_loader import RawPresetActionWorker, RawPresetActivateWorker, RawPresetLoadWorker, RawPresetSaveWorker
from presets.user_presets_action_workers import UserPresetActivateWorker, UserPresetItemActionWorker
from presets.user_presets_page_plans import build_preset_rows_plan
from ui.presets_menu.model import PresetListModel
import presets.user_presets_action_workers as user_presets_action_workers
import presets.ui.common.user_presets_page_runtime as user_presets_page_runtime
import app.feature_facades.presets as presets_feature_facade
import presets.ui.control.additional_settings_runtime as control_additional_settings_runtime
import presets.ui.control.control_page_shared as control_page_shared
import presets.ui.control.windows_features.runtime as windows_features_runtime
import program_settings.runtime as program_settings_runtime
import program_settings.workers as program_settings_workers
import presets.ui.common.preset_folder_menu as preset_folder_menu
import presets.ui.common.preset_rating_menu as preset_rating_menu
import profile.ui.profile_folder_menu as profile_folder_menu
import presets.ui.control.zapret1.runtime_helpers as zapret1_runtime_helpers
from presets.ui.control.zapret1.page import Zapret1ModeControlPage
import presets.ui.control.zapret2.page_runtime as zapret2_page_runtime
from presets.ui.control.zapret2.page import Zapret2ModeControlPage
from presets.user_presets_runtime_service import (
    UserPresetsMetadataLoadWorker,
    UserPresetsRuntimeService,
)
from hosts.ui.page import HostsPage
import hosts.ui.page_runtime as hosts_page_runtime
import hosts.commands as hosts_commands
from autostart.ui.page import AutostartPage
import log.commands as log_commands
from log.ui.page import LogsPage
from blobs.ui.page import BlobsPage
import blockcheck.page_runtime as blockcheck_page_runtime
import blockcheck.page_run_workflow as blockcheck_page_run_workflow
import blockcheck.worker as blockcheck_worker
from blockcheck.ui.page import BlockcheckPage
from blockcheck.ui.strategy_scan_page import StrategyScanPage
import blockcheck.ui.helpers as blockcheck_ui_helpers
from app.feature_facades.blockcheck import BlockcheckFeature
from updater.ui.page import ServersPage
import donater.pairing_workflow as premium_pairing_workflow
import donater.ui.page_plans as premium_page_plans
from donater.ui.page import PremiumPage
import donater.ui.page_lifecycle as premium_page_lifecycle
from settings.dpi.page import DpiSettingsPage
from ui.pages.about_page import AboutPage
from ui.pages.appearance_page import AppearancePage
from ui.pages.base_page import BasePage
from ui.pages.support_page import SupportPage
import settings.appearance as appearance_settings
import settings.appearance_workers as appearance_workers
from orchestra.ui.page import OrchestraPage
from orchestra.ui.blocked_page import OrchestraBlockedPage
from orchestra.ui.locked_page import OrchestraLockedPage
from orchestra.ui.ratings_page import OrchestraRatingsPage
from orchestra.ui.settings_page import OrchestraSettingsPage
from orchestra.ui.whitelist_page import OrchestraWhitelistPage
import orchestra.managed_lists_controller as orchestra_managed_lists_controller
import orchestra.ratings_controller as orchestra_ratings_controller
import orchestra.page_controller as orchestra_page_controller
import dns.page_diagnostics_warning_workflow as dns_diag_workflow
import dns.page_load_workflow as dns_load_workflow
import dns.ui.page as dns_page
import dns.ui.dns_check_page as dns_check_page
import dns.commands as dns_commands
import dns.dns_check_plans as dns_check_page_plans
import dns.dns_check_worker as dns_check_worker
from dns.page_workers import DnsPageLoadWorker
import telegram_proxy.ui.diagnostics_workflow as telegram_diag_workflow
import telegram_proxy.ui.proxy_runtime_workflow as telegram_runtime_workflow
import telegram_proxy.ui.page as telegram_page
import telegram_proxy.commands as telegram_proxy_commands
import telegram_proxy.settings as telegram_proxy_settings
import telegram_proxy.ui.settings_build as telegram_proxy_settings_build
from app.feature_facades.telegram_proxy import TelegramProxyFeature
import telegram_proxy.ui.upstream_workflow as telegram_upstream_workflow
import telegram_proxy.workers as telegram_proxy_workers
from telegram_proxy.ui.page import TelegramProxyPage
from telegram_proxy.workers import TelegramProxyDiagnosticsWorker
from diagnostics.ui.page import ConnectionTestPage
import diagnostics.ui.runtime_helpers as diagnostics_runtime_helpers
import app.feature_facades.diagnostics as diagnostics_feature_facade
from app.feature_facades.diagnostics import DiagnosticsFeature
import ui.navigation.text_sync as navigation_text_sync
import ui.theme as ui_theme
import ui.window_appearance_bindings as window_appearance_bindings
import ui.window_appearance_state as window_appearance_state
import ui.smooth_scroll as smooth_scroll
import ui.animation_policy as animation_policy
import main.entry as main_entry
from app.page_names import PageName
from ui.widgets.win11_controls import Win11RadioOption
from ui.page_host import WindowPageHost


class PresetProfileAsyncArchitectureTests(unittest.TestCase):
    def test_preset_setup_page_loads_profiles_through_worker(self) -> None:
        refresh_source = inspect.getsource(PresetSetupPageBase.refresh_from_preset_switch)
        activated_source = inspect.getsource(PresetSetupPageBase.on_page_activated)
        init_source = inspect.getsource(PresetSetupPageBase.__init__)
        request_source = inspect.getsource(PresetSetupPageBase._request_profiles_payload)

        self.assertNotIn(".list_profiles(", refresh_source)
        self.assertIn("_request_profiles_payload(force=True)", refresh_source)
        self.assertIn("_schedule_profiles_payload_request", activated_source)
        self.assertNotIn("QTimer.singleShot(0, self._request_profiles_payload)", init_source)
        self.assertIn("_request_profiles_payload", inspect.getsource(PresetSetupPageBase._schedule_profiles_payload_request))
        self.assertIn("_profile_payload_dirty", request_source)
        self.assertIn("_profile_payload_loaded_once", request_source)

    def test_preset_setup_page_refreshes_after_active_preset_content_change_signal(self) -> None:
        init_source = inspect.getsource(PresetSetupPageBase.__init__)
        bind_source = inspect.getsource(PresetSetupPageBase.bind_ui_state_store)
        handler_source = inspect.getsource(PresetSetupPageBase._on_ui_state_changed)
        cleanup_source = inspect.getsource(PresetSetupPageBase.cleanup)

        self.assertIn("ui_state_store", init_source)
        self.assertIn("bind_ui_state_store", init_source)
        self.assertIn("preset_content_revision", bind_source)
        self.assertIn("active_preset_revision", bind_source)
        self.assertIn("_profile_payload_dirty = True", handler_source)
        self.assertIn("_request_profiles_payload(force=True)", handler_source)
        self.assertIn("_ui_state_unsubscribe", cleanup_source)

    def test_preset_setup_page_ignores_stale_profile_worker_after_preset_switch(self) -> None:
        request_source = inspect.getsource(PresetSetupPageBase._request_profiles_payload)
        finished_source = inspect.getsource(PresetSetupPageBase._on_profile_worker_finished)

        running_branch = request_source.split("worker.isRunning():", 1)[1].split("return", 1)[0]
        self.assertIn("if force:", running_branch)
        self.assertIn("_profile_load_request_id += 1", running_branch)
        self.assertIn("_profile_payload_dirty = True", running_branch)
        self.assertIn("_schedule_profiles_payload_request(force=True)", finished_source)

    def test_profile_folder_worker_returns_folder_state_after_write_action(self) -> None:
        worker_source = inspect.getsource(profile_setup_loader.ProfileFolderActionWorker.run)

        self.assertIn('context["folder_state"]', worker_source)
        self.assertIn('self._action != "load_state"', worker_source)

    def test_profile_folder_action_updates_visible_list_without_reload(self) -> None:
        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_folder_action_request_id = 7
        page._profile_folder_action_worker = SimpleNamespace(_refresh_profile_page_after_action=True)
        page._profiles_list = Mock()
        page._profiles_list.apply_profile_folder_state.return_value = True
        page._profile_payload_dirty = False
        page.refresh_from_preset_switch = Mock(
            side_effect=AssertionError("folder action must not reload the whole profile list")
        )

        PresetSetupPageBase._on_profile_folder_action_finished(
            page,
            7,
            "rename",
            True,
            {"folder_state": {"folders": {}, "items": {}}},
        )

        page._profiles_list.apply_profile_folder_state.assert_called_once_with({"folders": {}, "items": {}})
        page.refresh_from_preset_switch.assert_not_called()
        self.assertTrue(page._profile_payload_dirty)

    def test_profile_model_applies_folder_state_without_loading_profiles_again(self) -> None:
        model = ProfileSetupListModel()
        model.set_profiles((
            SimpleNamespace(
                key="profile-1",
                persistent_key="persistent-1",
                profile_index=0,
                profile_name="Discord",
                enabled=True,
                in_preset=True,
                strategy_id="none",
                strategy_name="Стратегия не выбрана",
                match_lines=("--filter-tcp=443",),
                list_type="hostlist",
                rating="",
                favorite=False,
                group="common",
                group_name="Общие",
                order=0,
                order_is_manual=False,
                group_collapsed=False,
                user_profile_id="",
            ),
        ))
        model.beginResetModel = Mock(side_effect=AssertionError("folder rename must not reload profiles"))

        self.assertTrue(model.apply_folder_state({
            "folders": {
                "common": {"name": "Новая папка", "order": 0, "collapsed": False},
            },
            "items": {
                "persistent-1": {"folder_key": "common", "order": 0},
            },
        }))

        self.assertEqual(model.index(0, 0).data(ProfileSetupListModel.GroupNameRole), "Новая папка")

    def test_raw_preset_editor_saves_without_runtime_publish_until_editor_is_left(self) -> None:
        save_source = inspect.getsource(PresetRawEditorPage._save_file)
        text_changed_source = inspect.getsource(PresetRawEditorPage._on_text_changed)
        commit_source = inspect.getsource(PresetRawEditorPage._commit_pending_content_change)
        event_source = inspect.getsource(PresetRawEditorPage.eventFilter)
        controller_source = inspect.getsource(PresetRawEditorPage.__init__)

        self.assertIn("publish_content_changed: bool = False", save_source)
        self.assertIn("publish_content_changed", save_source)
        self.assertIn("_content_publish_pending", text_changed_source)
        self.assertIn("publish_content_changed=True", commit_source)
        self.assertIn("QEvent.Type.FocusOut", event_source)
        self.assertIn("QEvent.Type.Leave", event_source)
        self.assertIn("QEvent.Type.MouseButtonPress", event_source)
        self.assertIn("installEventFilter", controller_source)

    def test_raw_preset_editor_has_inline_text_search(self) -> None:
        build_source = inspect.getsource(PresetRawEditorPage._build_ui)

        self.assertTrue(hasattr(PresetRawEditorPage, "_search_preset_text"))
        search_source = inspect.getsource(PresetRawEditorPage._search_preset_text)
        self.assertIn("SearchLineEdit", build_source)
        self.assertIn("self.searchInput.setPlaceholderText", build_source)
        self.assertIn("actions_layout.addStretch(1)", build_source)
        self.assertIn("actions_layout.addWidget(self.searchInput, 0)", build_source)
        self.assertIn(".find(query", search_source)
        self.assertIn("QTextDocument.FindFlag(0)", search_source)

    def test_refresh_after_switch_uses_profile_snapshot_not_full_list(self) -> None:
        source = inspect.getsource(display_state.resolve_profile_strategy_display_state)

        self.assertNotIn(".list_profiles(", source)
        self.assertIn("get_profile_strategy_display_state", source)

    def test_preset_switch_summary_refresh_runs_through_worker_runtime(self) -> None:
        import ui.window_bootstrap_runtime as bootstrap_runtime

        source = inspect.getsource(bootstrap_runtime.create_preset_runtime_coordinator)

        self.assertIn("PresetProfileStrategySummaryRefreshRuntime", source)
        self.assertIn("summary_refresh_runtime.request_refresh", source)
        self.assertNotIn(
            "refresh_after_switch=lambda: runtime_deps.presets_feature.refresh_profile_strategy_summary_in_store",
            source,
        )

    def test_preset_switch_summary_worker_does_not_touch_ui_state_store(self) -> None:
        import presets.display_state_refresh as display_state_refresh

        worker_source = inspect.getsource(display_state_refresh.PresetProfileStrategySummaryWorker.run)
        runtime_source = inspect.getsource(
            display_state_refresh.PresetProfileStrategySummaryRefreshRuntime._on_summary_loaded,
        )
        publish_source = inspect.getsource(display_state.publish_profile_strategy_summary_in_store)

        self.assertIn("resolve_profile_strategy_display_state", worker_source)
        self.assertNotIn("ui_state_store", worker_source)
        self.assertIn("publish_profile_strategy_summary_in_store", runtime_source)
        self.assertIn("set_current_strategy_summary", publish_source)

    def test_user_presets_full_metadata_loading_is_worker_only(self) -> None:
        load_source = inspect.getsource(UserPresetsRuntimeService.load_presets)
        watcher_source = inspect.getsource(UserPresetsRuntimeService.reload_presets_from_watcher)

        self.assertNotIn("adapter.load_all_metadata()", load_source)
        self.assertNotIn("adapter.load_all_metadata()", watcher_source)
        self.assertIn("UserPresetsMetadataLoadWorker", load_source)

    def test_user_presets_single_metadata_refresh_is_worker_only(self) -> None:
        import presets.user_presets_runtime_service as runtime_service

        self.assertTrue(hasattr(runtime_service, "UserPresetsSingleMetadataWorker"))
        changed_source = inspect.getsource(UserPresetsRuntimeService.on_store_content_changed)
        request_source = inspect.getsource(UserPresetsRuntimeService._request_single_metadata_refresh)
        loaded_source = inspect.getsource(UserPresetsRuntimeService._on_single_metadata_loaded)
        worker_source = inspect.getsource(runtime_service.UserPresetsSingleMetadataWorker.run)

        self.assertNotIn("adapter.read_single_metadata(file_name)", changed_source)
        self.assertIn("_request_single_metadata_refresh", changed_source)
        self.assertIn("UserPresetsSingleMetadataWorker", request_source)
        self.assertIn("_read_single_metadata", worker_source)
        self.assertIn("try_apply_single_preset_metadata_update", loaded_source)

    def test_user_presets_folder_state_for_rows_is_worker_loaded(self) -> None:
        worker_source = inspect.getsource(UserPresetsMetadataLoadWorker.run)
        load_source = inspect.getsource(UserPresetsRuntimeService.load_presets)
        loaded_source = inspect.getsource(UserPresetsRuntimeService._on_metadata_loaded)
        cache_refresh_source = inspect.getsource(UserPresetsRuntimeService.refresh_presets_view_from_cache)
        rebuild_source = inspect.getsource(UserPresetsPageBase._rebuild_presets_rows)
        plan_source = inspect.getsource(build_preset_rows_plan)

        self.assertIn("_load_folder_state", worker_source)
        self.assertIn("folder_state", load_source)
        self.assertIn("_cached_folder_state", loaded_source)
        self.assertIn("_cached_folder_state", cache_refresh_source)
        self.assertIn("folder_state=folder_state", rebuild_source)
        fallback_branch = plan_source.split("effective_folder_state", 1)[1]
        self.assertNotIn("load_preset_folder_state", fallback_branch)

    def test_user_presets_active_marker_uses_model_signals_without_full_viewport_update(self) -> None:
        source = inspect.getsource(UserPresetsRuntimeService.apply_active_preset_marker_for_file)

        self.assertIn("set_active_preset", source)
        self.assertIn("set_current_preset_index", source)
        self.assertNotIn("viewport().update()", source)
        self.assertNotIn("viewport().repaint()", source)

    def test_user_presets_single_metadata_update_uses_model_signals_without_full_viewport_update(self) -> None:
        source = inspect.getsource(UserPresetsRuntimeService.try_apply_single_preset_metadata_update)

        self.assertIn("update_preset_row", source)
        self.assertNotIn("viewport().update()", source)
        self.assertNotIn("viewport().repaint()", source)

    def test_user_presets_switched_signal_uses_delivered_file_name(self) -> None:
        source = inspect.getsource(UserPresetsRuntimeService.on_store_switched)

        self.assertIn("apply_active_preset_marker_for_file", source)
        self.assertNotIn("apply_active_preset_marker(page)", source)

    def test_user_presets_page_uses_warmed_smooth_scroll_preference(self) -> None:
        source = inspect.getsource(UserPresetsPageBase._build_ui)

        self.assertIn("get_page_smooth_scroll_enabled", source)
        self.assertNotIn("load_smooth_scroll_enabled", source)

    def test_user_presets_page_uses_narrow_preset_dependencies(self) -> None:
        after_ui_source = inspect.getsource(UserPresetsPageBase._after_ui_built)
        open_folder_source = inspect.getsource(UserPresetsPageBase._open_presets_folder)
        page_source = inspect.getsource(UserPresetsPageBase)

        self.assertIn("self._connect_preset_signals", after_ui_source)
        self.assertIn("_request_preset_open_folder_action", open_folder_source)
        self.assertNotIn("open_presets_folder_action", open_folder_source)
        self.assertNotIn("open_user_presets_folder", open_folder_source)
        self.assertIn("create_preset_open_folder_worker", page_source)
        self.assertIn("_preset_open_folder_worker", page_source)
        self.assertNotIn("self._presets_feature", page_source)
        self.assertNotIn("self._presets.", after_ui_source)
        self.assertNotIn("self._presets.", open_folder_source)

        self.assertTrue(hasattr(user_presets_action_workers, "UserPresetOpenFolderWorker"))
        create_worker_source = inspect.getsource(UserPresetsPageBase.create_preset_open_folder_worker)
        worker_source = inspect.getsource(user_presets_action_workers.UserPresetOpenFolderWorker.run)
        worker_init_source = inspect.getsource(user_presets_action_workers.UserPresetOpenFolderWorker.__init__)
        feature_source = inspect.getsource(presets_feature_facade.PresetsFeature.create_user_presets_open_folder_worker)
        self.assertIn("_create_user_presets_open_folder_worker", create_worker_source)
        self.assertNotIn("UserPresetOpenFolderWorker(", create_worker_source)
        self.assertNotIn("_presets_feature", worker_init_source)
        self.assertIn("open_folder", worker_init_source)
        self.assertIn("self._open_folder", worker_init_source)
        self.assertIn("self._open_folder()", worker_source)
        self.assertNotIn("preset_commands.open_user_presets_folder", worker_source)
        self.assertNotIn("_preset_services", worker_init_source)
        self.assertIn("open_user_presets_folder", feature_source)

    def test_preset_list_active_marker_updates_indexed_rows_only(self) -> None:
        class CountingRow(dict):
            def __init__(self, *args, **kwargs) -> None:
                super().__init__(*args, **kwargs)
                self.get_count = 0

            def get(self, key, default=None):
                self.get_count += 1
                return super().get(key, default)

        rows = [
            CountingRow(
                {
                    "kind": "preset",
                    "file_name": f"preset-{index}.txt",
                    "is_active": index == 3,
                }
            )
            for index in range(100)
        ]
        model = PresetListModel()
        model.set_rows(rows)
        for row in rows:
            row.get_count = 0

        self.assertTrue(model.set_active_preset("preset-70.txt"))

        touched_rows = [row for row in rows if row.get_count]
        self.assertLessEqual(len(touched_rows), 2)
        self.assertFalse(rows[3]["is_active"])
        self.assertTrue(rows[70]["is_active"])

    def test_user_presets_current_index_uses_model_row_index(self) -> None:
        source = inspect.getsource(UserPresetsRuntimeService.set_current_preset_index)

        self.assertIn("find_preset_row", source)
        self.assertNotIn("for row in range", source)

    def test_user_presets_current_index_skips_already_selected_row(self) -> None:
        class _Index:
            def __init__(self, row: int) -> None:
                self.row = row

            def isValid(self) -> bool:
                return True

            def __eq__(self, other) -> bool:
                return isinstance(other, _Index) and self.row == other.row

        target_index = _Index(4)
        model = Mock()
        model.find_preset_row.return_value = 4
        model.index.return_value = target_index
        presets_list = Mock()
        presets_list.currentIndex.return_value = target_index
        page = SimpleNamespace(_presets_model=model, presets_list=presets_list)
        service = UserPresetsRuntimeService.__new__(UserPresetsRuntimeService)
        service._resolve_page = Mock(return_value=page)

        UserPresetsRuntimeService.set_current_preset_index(service, "Default.txt")

        presets_list.setCurrentIndex.assert_not_called()

    def test_user_presets_restore_view_state_skips_same_scroll_value(self) -> None:
        scrollbar = Mock()
        scrollbar.value.return_value = 42
        presets_list = Mock()
        presets_list.verticalScrollBar.return_value = scrollbar
        page = SimpleNamespace(presets_list=presets_list)
        service = UserPresetsRuntimeService.__new__(UserPresetsRuntimeService)
        service._resolve_page = Mock(return_value=page)

        UserPresetsRuntimeService.restore_presets_view_state(
            service,
            {"current_file_name": "", "scroll_value": 42},
        )

        scrollbar.setValue.assert_not_called()

    def test_user_presets_activation_runs_through_worker(self) -> None:
        handler_source = inspect.getsource(UserPresetsPageBase._on_activate_preset)
        request_source = inspect.getsource(UserPresetsPageBase._request_preset_activation)
        worker_source = inspect.getsource(UserPresetActivateWorker.run)

        self.assertNotIn("activate_preset_action", handler_source)
        self.assertNotIn(".activate_preset(", handler_source)
        self.assertIn("apply_active_preset_marker_for_file", handler_source)
        self.assertIn("_request_preset_activation", handler_source)
        self.assertIn("create_preset_activate_worker", request_source)
        self.assertIn("self._activate_preset", worker_source)
        self.assertNotIn("actions_api.activate_preset", worker_source)

    def test_user_presets_activation_error_restores_marker_without_list_reload(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_activate_request_id = 4
        page._pending_preset_activation = None
        page._restore_preset_activation_marker_file_name = "Before.txt"
        page._runtime_service = Mock()
        page._refresh_presets_view_from_cache = Mock(
            side_effect=AssertionError("activation error must not reload the whole preset list")
        )
        page._tr = Mock(side_effect=lambda _key, default, **_kwargs: default)
        page.window = Mock(return_value=None)
        result = SimpleNamespace(
            ok=False,
            log_message="Ошибка активации",
            log_level="ERROR",
            infobar_level="error",
            infobar_title="Ошибка",
            infobar_content="Не удалось",
            activated_file_name=None,
        )

        with patch("presets.ui.common.user_presets_page.InfoBar.error"):
            UserPresetsPageBase._on_preset_activation_finished(page, 4, result)

        page._runtime_service.apply_active_preset_marker.assert_not_called()
        page._runtime_service.apply_active_preset_marker_for_file.assert_called_once_with("Before.txt")

    def test_user_presets_activation_failure_restores_marker_without_list_reload(self) -> None:
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_activate_request_id = 5
        page._pending_preset_activation = None
        page._restore_preset_activation_marker_file_name = "Before.txt"
        page._runtime_service = Mock()
        page._refresh_presets_view_from_cache = Mock(
            side_effect=AssertionError("activation failure must not reload the whole preset list")
        )
        page._tr = Mock(side_effect=lambda _key, default, **_kwargs: default)
        page.window = Mock(return_value=None)

        with patch("presets.ui.common.user_presets_page.InfoBar.error"):
            UserPresetsPageBase._on_preset_activation_failed(page, 5, "bad")

        page._runtime_service.apply_active_preset_marker.assert_not_called()
        page._runtime_service.apply_active_preset_marker_for_file.assert_called_once_with("Before.txt")

    def test_preset_model_removes_visible_preset_without_full_reset(self) -> None:
        model = PresetListModel()
        model.set_rows([
            {
                "kind": "folder",
                "folder_key": "common",
                "text": "Общие",
                "count": 2,
                "is_collapsed": False,
            },
            {
                "kind": "preset",
                "file_name": "first.txt",
                "name": "First",
                "folder_key": "common",
            },
            {
                "kind": "preset",
                "file_name": "second.txt",
                "name": "Second",
                "folder_key": "common",
            },
        ])
        model.beginResetModel = Mock(side_effect=AssertionError("delete must not reset the whole preset list"))

        self.assertTrue(model.remove_preset("first.txt"))

        self.assertEqual(model.rowCount(), 2)
        self.assertEqual(model.find_preset_row("first.txt"), -1)
        self.assertEqual(model.find_preset_row("second.txt"), 1)
        self.assertEqual(model.index(0, 0).data(PresetListModel.CountRole), 1)

    def test_preset_model_skips_identical_rows_without_full_reset(self) -> None:
        rows = [
            {
                "kind": "folder",
                "folder_key": "common",
                "text": "Общие",
                "count": 1,
                "is_collapsed": False,
            },
            {
                "kind": "preset",
                "file_name": "first.txt",
                "name": "First",
                "folder_key": "common",
            },
        ]
        model = PresetListModel()
        model.set_rows(rows)
        model.beginResetModel = Mock(side_effect=AssertionError("same rows must not reset the preset list"))

        model.set_rows([dict(row) for row in rows])

        self.assertEqual(model.rowCount(), 2)
        self.assertEqual(model.find_preset_row("first.txt"), 1)

    def test_preset_model_reports_whether_set_rows_changed_model(self) -> None:
        rows = [
            {
                "kind": "preset",
                "file_name": "first.txt",
                "name": "First",
                "folder_key": "common",
            },
        ]
        model = PresetListModel()

        self.assertTrue(model.set_rows(rows))
        self.assertFalse(model.set_rows([dict(row) for row in rows]))
        self.assertTrue(model.set_rows([{**rows[0], "name": "First updated"}]))

    def test_preset_model_updates_stable_rows_without_full_reset(self) -> None:
        model = PresetListModel()
        model.set_rows([
            {
                "kind": "folder",
                "folder_key": "common",
                "text": "Общие",
                "count": 1,
                "is_collapsed": False,
            },
            {
                "kind": "preset",
                "file_name": "first.txt",
                "name": "First",
                "folder_key": "common",
                "description": "old",
                "rating": 1,
            },
        ])
        model.beginResetModel = Mock(side_effect=AssertionError("stable rows must not reset the preset list"))

        model.set_rows([
            {
                "kind": "folder",
                "folder_key": "common",
                "text": "Общие",
                "count": 1,
                "is_collapsed": False,
            },
            {
                "kind": "preset",
                "file_name": "first.txt",
                "name": "First updated",
                "folder_key": "common",
                "description": "new",
                "rating": 5,
            },
        ])

        self.assertEqual(model.rowCount(), 2)
        self.assertEqual(model.find_preset_row("first.txt"), 1)
        self.assertEqual(model.index(1, 0).data(PresetListModel.NameRole), "First updated")
        self.assertEqual(model.index(1, 0).data(PresetListModel.DescriptionRole), "new")
        self.assertEqual(model.index(1, 0).data(PresetListModel.RatingRole), 5)

    def test_preset_model_moves_single_reordered_row_without_full_reset(self) -> None:
        model = PresetListModel()
        model.set_rows([
            {
                "kind": "folder",
                "folder_key": "common",
                "text": "Общие",
                "count": 3,
                "is_collapsed": False,
            },
            {
                "kind": "preset",
                "file_name": "first.txt",
                "name": "First",
                "folder_key": "common",
                "rating": 0,
            },
            {
                "kind": "preset",
                "file_name": "second.txt",
                "name": "Second",
                "folder_key": "common",
                "rating": 0,
            },
            {
                "kind": "preset",
                "file_name": "third.txt",
                "name": "Third",
                "folder_key": "common",
                "rating": 0,
            },
        ])
        model.beginResetModel = Mock(side_effect=AssertionError("single-row reorder must not reset the whole preset list"))

        changed = model.set_rows([
            {
                "kind": "folder",
                "folder_key": "common",
                "text": "Общие",
                "count": 3,
                "is_collapsed": False,
            },
            {
                "kind": "preset",
                "file_name": "second.txt",
                "name": "Second",
                "folder_key": "common",
                "rating": 0,
            },
            {
                "kind": "preset",
                "file_name": "first.txt",
                "name": "First",
                "folder_key": "common",
                "rating": 5,
            },
            {
                "kind": "preset",
                "file_name": "third.txt",
                "name": "Third",
                "folder_key": "common",
                "rating": 0,
            },
        ])

        self.assertTrue(changed)
        self.assertEqual(model.find_preset_row("first.txt"), 2)
        self.assertEqual(model.index(2, 0).data(PresetListModel.FileNameRole), "first.txt")
        self.assertEqual(model.index(2, 0).data(PresetListModel.RatingRole), 5)

    def test_preset_model_single_move_detection_is_not_bruteforce(self) -> None:
        helper_source = inspect.getsource(__import__("ui.presets_menu.model", fromlist=["_single_row_move"])._single_row_move)

        self.assertNotIn("for insert_index in range", helper_source)
        self.assertNotIn("candidate =", helper_source)
        self.assertIn("current_positions", helper_source)

    def test_preset_rows_rebuild_skips_layout_when_rows_do_not_change(self) -> None:
        from presets.ui.common.user_presets_page_runtime import rebuild_presets_rows

        runtime_service = Mock()
        runtime_service.capture_presets_view_state.return_value = {}
        runtime_service.current_search_query.return_value = ""
        presets_model = Mock()
        presets_model.set_rows.return_value = False
        listing_api = Mock()
        listing_api.build_preset_rows_plan.return_value = SimpleNamespace(
            rows=[
                {
                    "kind": "preset",
                    "file_name": "first.txt",
                    "name": "First",
                    "folder_key": "common",
                }
            ],
            total_presets=1,
        )
        update_height = Mock(side_effect=AssertionError("unchanged rows must not recalculate list height"))
        schedule_resync = Mock(side_effect=AssertionError("unchanged rows must not resync layout"))
        presets_delegate = Mock()

        rebuild_presets_rows(
            runtime_service=runtime_service,
            listing_api=listing_api,
            presets_delegate=presets_delegate,
            presets_model=presets_model,
            presets_list=object(),
            get_selected_source_preset_file_name_light_fn=Mock(return_value="first.txt"),
            ui_language="ru",
            schedule_layout_resync_fn=schedule_resync,
            update_presets_view_height_fn=update_height,
            log_fn=Mock(),
            all_presets={"first.txt": {"display_name": "First"}},
            folder_state={},
        )

        presets_delegate.reset_interaction_state.assert_not_called()
        runtime_service.ensure_preset_list_current_index.assert_not_called()
        runtime_service.restore_presets_view_state.assert_not_called()

    def test_preset_rows_rebuild_skips_layout_when_row_count_is_unchanged(self) -> None:
        from presets.ui.common.user_presets_page_runtime import rebuild_presets_rows

        runtime_service = Mock()
        runtime_service.capture_presets_view_state.return_value = {}
        runtime_service.current_search_query.return_value = ""
        presets_model = PresetListModel()
        presets_model.set_rows([
            {
                "kind": "folder",
                "folder_key": "common",
                "text": "Общие",
                "count": 2,
                "is_collapsed": False,
            },
            {
                "kind": "preset",
                "file_name": "first.txt",
                "name": "First",
                "folder_key": "common",
            },
            {
                "kind": "preset",
                "file_name": "second.txt",
                "name": "Second",
                "folder_key": "common",
            },
        ])
        listing_api = Mock()
        listing_api.build_preset_rows_plan.return_value = SimpleNamespace(
            rows=[
                {
                    "kind": "folder",
                    "folder_key": "common",
                    "text": "Общие",
                    "count": 2,
                    "is_collapsed": False,
                },
                {
                    "kind": "preset",
                    "file_name": "second.txt",
                    "name": "Second",
                    "folder_key": "common",
                },
                {
                    "kind": "preset",
                    "file_name": "first.txt",
                    "name": "First",
                    "folder_key": "common",
                    "rating": 5,
                },
            ],
            total_presets=2,
        )
        update_height = Mock()
        schedule_resync = Mock()

        rebuild_presets_rows(
            runtime_service=runtime_service,
            listing_api=listing_api,
            presets_delegate=Mock(),
            presets_model=presets_model,
            presets_list=object(),
            get_selected_source_preset_file_name_light_fn=Mock(return_value="first.txt"),
            ui_language="ru",
            schedule_layout_resync_fn=schedule_resync,
            update_presets_view_height_fn=update_height,
            log_fn=Mock(),
            all_presets={"first.txt": {"display_name": "First"}, "second.txt": {"display_name": "Second"}},
            folder_state={},
        )

        update_height.assert_not_called()
        schedule_resync.assert_not_called()
        runtime_service.ensure_preset_list_current_index.assert_called_once_with()

    def test_user_presets_delete_updates_visible_row_without_reload(self) -> None:
        result = SimpleNamespace(
            ok=True,
            structure_changed=True,
            log_message="Удалён пресет",
            log_level="INFO",
            infobar_level="",
            infobar_title="",
            infobar_content="",
            error_code="",
        )
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_item_action_request_id = 4
        page._runtime_service = Mock()
        page._runtime_service.remove_deleted_preset_locally.return_value = True
        page._tr = Mock(side_effect=lambda _key, default, **_kwargs: default)
        page.window = Mock(return_value=None)

        with patch("presets.ui.common.user_presets_page.InfoBar.success"):
            UserPresetsPageBase._on_preset_item_action_finished(
                page,
                4,
                "delete",
                result,
                {"file_name": "first.txt"},
            )

        page._runtime_service.remove_deleted_preset_locally.assert_called_once_with("first.txt")
        page._runtime_service.mark_presets_structure_changed.assert_not_called()

    def test_preset_model_renames_visible_preset_without_full_reset(self) -> None:
        model = PresetListModel()
        model.set_rows([
            {
                "kind": "preset",
                "file_name": "old.txt",
                "name": "Old",
                "folder_key": "common",
                "is_active": True,
            },
        ])
        model.beginResetModel = Mock(side_effect=AssertionError("rename must not reset the whole preset list"))

        self.assertTrue(model.rename_preset("old.txt", "new.txt", name="New"))

        self.assertEqual(model.find_preset_row("old.txt"), -1)
        self.assertEqual(model.find_preset_row("new.txt"), 0)
        self.assertEqual(model.index(0, 0).data(PresetListModel.FileNameRole), "new.txt")
        self.assertEqual(model.index(0, 0).data(PresetListModel.NameRole), "New")
        self.assertEqual(model.active_preset_file_name(), "new.txt")

    def test_user_presets_rename_updates_visible_row_without_reload(self) -> None:
        result = SimpleNamespace(
            ok=True,
            structure_changed=True,
            log_message="Переименован",
            log_level="INFO",
            infobar_level="",
            infobar_title="",
            infobar_content="",
            error_code="",
            preset_file_name="new.txt",
            preset_display_name="New",
        )
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_edit_action_request_id = 5
        page._runtime_service = Mock()
        page._runtime_service.rename_preset_locally.return_value = True

        UserPresetsPageBase._on_preset_edit_action_finished(
            page,
            5,
            "rename",
            result,
            {"current_name": "old.txt", "new_name": "New"},
        )

        page._runtime_service.rename_preset_locally.assert_called_once_with(
            "old.txt",
            "new.txt",
            "New",
        )
        page._runtime_service.mark_presets_structure_changed.assert_not_called()

    def test_preset_model_inserts_created_preset_without_full_reset(self) -> None:
        model = PresetListModel()
        model.set_rows([
            {
                "kind": "folder",
                "folder_key": "common",
                "name": "Общие",
                "text": "Общие",
                "count": 1,
                "is_collapsed": False,
            },
            {
                "kind": "preset",
                "file_name": "old.txt",
                "name": "Old",
                "folder_key": "common",
                "is_active": False,
            },
        ])
        model.beginResetModel = Mock(side_effect=AssertionError("create must not reset the whole preset list"))

        self.assertTrue(model.insert_preset({
            "kind": "preset",
            "file_name": "new.txt",
            "name": "New",
            "folder_key": "common",
            "is_active": False,
        }))

        self.assertEqual(model.find_preset_row("new.txt"), 2)
        self.assertEqual(model.index(0, 0).data(PresetListModel.CountRole), 2)

    def test_user_presets_create_updates_visible_row_without_reload(self) -> None:
        result = SimpleNamespace(
            ok=True,
            structure_changed=True,
            log_message="Создан",
            log_level="INFO",
            infobar_level="",
            infobar_title="",
            infobar_content="",
            error_code="",
            preset_file_name="new.txt",
            preset_display_name="New",
        )
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_edit_action_request_id = 6
        page._runtime_service = Mock()
        page._runtime_service.add_created_preset_locally.return_value = True

        UserPresetsPageBase._on_preset_edit_action_finished(
            page,
            6,
            "create",
            result,
            {"name": "New"},
        )

        page._runtime_service.add_created_preset_locally.assert_called_once_with(
            "new.txt",
            "New",
        )
        page._runtime_service.mark_presets_structure_changed.assert_not_called()

    def test_user_presets_duplicate_updates_visible_row_without_reload(self) -> None:
        result = SimpleNamespace(
            ok=True,
            structure_changed=True,
            log_message="Дублирован",
            log_level="INFO",
            infobar_level="",
            infobar_title="",
            infobar_content="",
            error_code="",
            preset_file_name="copy.txt",
            preset_display_name="Copy",
        )
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_item_action_request_id = 7
        page._runtime_service = Mock()
        page._runtime_service.add_created_preset_locally.return_value = True
        page._tr = Mock(side_effect=lambda _key, default, **_kwargs: default)
        page.window = Mock(return_value=None)

        UserPresetsPageBase._on_preset_item_action_finished(
            page,
            7,
            "duplicate",
            result,
            {"file_name": "source.txt", "display_name": "Source"},
        )

        page._runtime_service.add_created_preset_locally.assert_called_once_with(
            "copy.txt",
            "Copy",
        )
        page._runtime_service.mark_presets_structure_changed.assert_not_called()

    def test_user_presets_import_updates_visible_row_without_reload(self) -> None:
        result = SimpleNamespace(
            ok=True,
            structure_changed=True,
            log_message="Импортирован",
            log_level="INFO",
            infobar_level="success",
            infobar_title="Пресет импортирован",
            infobar_content="Готово",
            actual_file_name="imported.txt",
            actual_name="Imported",
        )
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._preset_bulk_action_request_id = 8
        page._runtime_service = Mock()
        page._runtime_service.add_created_preset_locally.return_value = True
        page.window = Mock(return_value=None)

        with patch("presets.ui.common.user_presets_page.InfoBar.success"):
            UserPresetsPageBase._on_preset_bulk_action_finished(
                page,
                8,
                "import",
                result,
                {},
            )

        page._runtime_service.add_created_preset_locally.assert_called_once_with(
            "imported.txt",
            "Imported",
        )
        page._runtime_service.mark_presets_structure_changed.assert_not_called()

    def test_user_presets_display_name_uses_visible_cache_not_backend_manifest(self) -> None:
        class _ListingApi:
            def resolve_display_name(self, _reference: str) -> str:
                raise AssertionError("display name must not be resolved from backend in GUI path")

        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._page_api = type("_PageApi", (), {"listing": _ListingApi()})()
        page._runtime_service = UserPresetsRuntimeService()
        page._runtime_service._cached_presets_metadata = {
            "cached.txt": {"display_name": "Cached Preset"},
        }
        page._presets_model = PresetListModel()
        page._presets_model.set_rows(
            [
                {
                    "kind": "preset",
                    "file_name": "visible.txt",
                    "name": "Visible Preset",
                }
            ]
        )

        self.assertEqual(page._resolve_display_name("visible.txt"), "Visible Preset")
        self.assertEqual(page._resolve_display_name("cached.txt"), "Cached Preset")
        self.assertEqual(page._resolve_display_name("fallback.txt"), "fallback")

    def test_user_presets_builtin_check_uses_visible_cache_not_backend_storage(self) -> None:
        class _StorageApi:
            def is_builtin_preset_file_with_cache(self, _name: str, _cached_metadata) -> bool:
                raise AssertionError("builtin check must not be resolved from backend in GUI path")

        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        page._page_api = type("_PageApi", (), {"storage": _StorageApi()})()
        page._runtime_service = UserPresetsRuntimeService()
        page._runtime_service._cached_presets_metadata = {
            "cached.txt": {"is_builtin": True},
        }
        page._presets_model = PresetListModel()
        page._presets_model.set_rows(
            [
                {
                    "kind": "preset",
                    "file_name": "visible.txt",
                    "name": "Visible Preset",
                    "is_builtin": True,
                }
            ]
        )

        self.assertTrue(page._is_builtin_preset_file("visible.txt"))
        self.assertTrue(page._is_builtin_preset_file("cached.txt"))
        self.assertFalse(page._is_builtin_preset_file("fallback.txt"))

    def test_user_presets_cleanup_stops_action_workers_and_pending_requests(self) -> None:
        class _Worker:
            def __init__(self) -> None:
                self.quit = Mock()

        class _Timer:
            def __init__(self) -> None:
                self.stop = Mock()

        worker_attrs = (
            "_preset_activate_worker",
            "_preset_item_action_worker",
            "_preset_bulk_action_worker",
            "_preset_edit_action_worker",
            "_preset_storage_action_worker",
            "_preset_folder_action_worker",
            "_preset_open_folder_worker",
            "_preset_link_action_worker",
        )
        request_attrs = (
            "_preset_activate_request_id",
            "_preset_item_action_request_id",
            "_preset_bulk_action_request_id",
            "_preset_edit_action_request_id",
            "_preset_storage_action_request_id",
            "_preset_folder_action_request_id",
            "_preset_open_folder_request_id",
            "_preset_link_action_request_id",
        )
        page = UserPresetsPageBase.__new__(UserPresetsPageBase)
        workers = {attr: _Worker() for attr in worker_attrs}
        for attr, worker in workers.items():
            setattr(page, attr, worker)
        for attr in request_attrs:
            setattr(page, attr, 7)
        page._pending_preset_activation = ("next.txt", "Next")
        page._preset_folder_action_pending = [{"action": "load_state"}]
        page._preset_open_folder_pending = True
        page._preset_link_action_pending = "info"
        page._preset_bulk_action_kind = "reset_all"
        page._bulk_reset_running = True
        page._layout_resync_timer = _Timer()
        page._layout_resync_delayed_timer = _Timer()
        page._preset_search_timer = _Timer()
        page._ui_state_unsubscribe = Mock()
        page._ui_state_store = object()
        page._runtime_service = Mock()

        UserPresetsPageBase.cleanup(page)

        for worker in workers.values():
            worker.quit.assert_called_once()
        for attr in worker_attrs:
            self.assertIsNone(getattr(page, attr))
        for attr in request_attrs:
            self.assertEqual(getattr(page, attr), 8)
        self.assertIsNone(page._pending_preset_activation)
        self.assertEqual(page._preset_folder_action_pending, [])
        self.assertFalse(page._preset_open_folder_pending)
        self.assertEqual(page._preset_link_action_pending, "")
        self.assertEqual(page._preset_bulk_action_kind, "")
        self.assertFalse(page._bulk_reset_running)
        page._runtime_service.stop_watching_presets.assert_called_once()

    def test_user_presets_menu_selected_check_uses_runtime_marker(self) -> None:
        source = inspect.getsource(UserPresetsPageBase._is_selected_source_preset_file)

        self.assertIn("active_preset_file_name", source)
        self.assertNotIn("_get_selected_source_preset_file_name_light", source)

    def test_user_preset_activation_worker_is_created_through_feature(self) -> None:
        request_source = inspect.getsource(UserPresetsPageBase._request_preset_activation)
        create_worker_source = inspect.getsource(UserPresetsPageBase.create_preset_activate_worker)

        self.assertIn("create_preset_activate_worker", request_source)
        self.assertNotIn("UserPresetActivateWorker", create_worker_source)
        self.assertIn("_create_preset_activate_worker_fn", create_worker_source)

    def test_user_presets_runtime_does_not_keep_file_action_fallbacks(self) -> None:
        page_source = inspect.getsource(UserPresetsPageBase)
        runtime_source = inspect.getsource(user_presets_page_runtime)

        self.assertNotIn("def _actions_api", page_source)
        self.assertNotIn("class UserPresetsActionsApi", runtime_source)
        self.assertNotIn("class _UserPresetsActionsApiImpl", runtime_source)
        self.assertNotIn("def create_preset(self, *, name", runtime_source)
        self.assertNotIn("def import_preset_from_file(self, *, file_path", runtime_source)
        self.assertNotIn("def activate_preset(self, *, file_name", runtime_source)
        self.assertNotIn("def duplicate_preset(self, *, file_name", runtime_source)
        self.assertNotIn("def open_presets_info(self)", runtime_source)
        self.assertNotIn(
            "presets.ui.common.user_presets_page_runtime",
            inspect.getsource(presets_feature_facade),
        )

    def test_user_presets_item_file_actions_run_through_worker(self) -> None:
        worker_source = inspect.getsource(UserPresetItemActionWorker.run)
        request_source = inspect.getsource(UserPresetsPageBase._request_preset_item_action)
        create_worker_source = inspect.getsource(UserPresetsPageBase.create_preset_item_action_worker)

        for method in (
            UserPresetsPageBase._on_duplicate_preset,
            UserPresetsPageBase._on_reset_preset,
            UserPresetsPageBase._on_delete_preset,
            UserPresetsPageBase._on_export_preset,
        ):
            source = inspect.getsource(method)
            self.assertIn("_request_preset_item_action", source)
            self.assertNotIn("duplicate_preset_action", source)
            self.assertNotIn("reset_preset_action", source)
            self.assertNotIn("delete_preset_action", source)
            self.assertNotIn("export_preset_action", source)
            self.assertNotIn(".duplicate_preset(", source)
            self.assertNotIn(".reset_preset_to_builtin(", source)
            self.assertNotIn(".delete_preset(", source)
            self.assertNotIn(".export_preset(", source)

        delete_source = inspect.getsource(UserPresetsPageBase._on_delete_preset)
        self.assertIn("_is_builtin_preset_file", delete_source)
        self.assertNotIn("_storage_api().is_builtin_preset_file", delete_source)
        self.assertIn("create_preset_item_action_worker", request_source)
        self.assertNotIn("UserPresetItemActionWorker", create_worker_source)
        self.assertIn("_create_preset_item_action_worker_fn", create_worker_source)
        self.assertIn("self._duplicate_preset", worker_source)
        self.assertIn("self._reset_preset_to_builtin", worker_source)
        self.assertIn("self._delete_preset", worker_source)
        self.assertIn("self._export_preset", worker_source)
        self.assertNotIn("actions_api.", worker_source)

    def test_user_presets_import_and_reset_all_run_through_worker(self) -> None:
        import_source = inspect.getsource(UserPresetsPageBase._on_import_clicked)
        reset_source = inspect.getsource(UserPresetsPageBase._on_reset_all_presets_clicked)

        self.assertTrue(hasattr(user_presets_action_workers, "UserPresetBulkActionWorker"))
        worker_source = inspect.getsource(user_presets_action_workers.UserPresetBulkActionWorker.run)
        request_source = inspect.getsource(UserPresetsPageBase._request_preset_bulk_action)
        create_worker_source = inspect.getsource(UserPresetsPageBase.create_preset_bulk_action_worker)

        for source in (import_source, reset_source):
            self.assertIn("_request_preset_bulk_action", source)
            self.assertNotIn("import_preset_action", source)
            self.assertNotIn("run_reset_all_presets_action", source)
            self.assertNotIn(".import_preset_from_file(", source)
            self.assertNotIn(".reset_all_presets(", source)

        self.assertIn("create_preset_bulk_action_worker", request_source)
        self.assertNotIn("UserPresetBulkActionWorker", create_worker_source)
        self.assertIn("_create_preset_bulk_action_worker_fn", create_worker_source)
        self.assertIn("self._import_preset_from_file", worker_source)
        self.assertIn("self._reset_all_presets", worker_source)
        self.assertNotIn("actions_api.", worker_source)

    def test_user_presets_create_and_rename_run_through_worker(self) -> None:
        create_source = inspect.getsource(UserPresetsPageBase._show_inline_action_create)
        rename_source = inspect.getsource(UserPresetsPageBase._show_inline_action_rename)

        self.assertTrue(hasattr(user_presets_action_workers, "UserPresetEditActionWorker"))
        worker_source = inspect.getsource(user_presets_action_workers.UserPresetEditActionWorker.run)
        request_source = inspect.getsource(UserPresetsPageBase._request_preset_edit_action)
        create_worker_source = inspect.getsource(UserPresetsPageBase.create_preset_edit_action_worker)

        for source in (create_source, rename_source):
            body_source = "\n".join(source.splitlines()[1:])
            self.assertIn("_request_preset_edit_action", source)
            self.assertNotIn("show_inline_action_create(", body_source)
            self.assertNotIn("show_inline_action_rename(", body_source)
            self.assertNotIn(".create_preset(", source)
            self.assertNotIn(".rename_preset(", source)

        self.assertIn("create_preset_edit_action_worker", request_source)
        self.assertNotIn("UserPresetEditActionWorker", create_worker_source)
        self.assertIn("_create_preset_edit_action_worker_fn", create_worker_source)
        self.assertIn("self._create_preset", worker_source)
        self.assertIn("self._rename_preset", worker_source)
        self.assertNotIn("actions_api.", worker_source)

    def test_user_presets_info_links_open_through_worker(self) -> None:
        info_source = inspect.getsource(UserPresetsPageBase._open_presets_info)
        post_source = inspect.getsource(UserPresetsPageBase._open_new_configs_post)
        request_source = inspect.getsource(UserPresetsPageBase._request_preset_link_action)
        cleanup_source = inspect.getsource(UserPresetsPageBase._stop_action_workers_for_cleanup)

        self.assertTrue(hasattr(user_presets_action_workers, "UserPresetLinkActionWorker"))
        worker_source = inspect.getsource(user_presets_action_workers.UserPresetLinkActionWorker.run)
        create_worker_source = inspect.getsource(UserPresetsPageBase.create_preset_link_action_worker)

        for source in (info_source, post_source):
            self.assertIn("_request_preset_link_action", source)
            self.assertNotIn("open_presets_info_action", source)
            self.assertNotIn("open_new_configs_post_action", source)

        self.assertIn("create_preset_link_action_worker", request_source)
        self.assertNotIn("UserPresetLinkActionWorker", create_worker_source)
        self.assertIn("_create_preset_link_action_worker_fn", create_worker_source)
        self.assertIn("self._open_presets_info", worker_source)
        self.assertIn("self._open_new_configs_post", worker_source)
        self.assertNotIn("actions_api.", worker_source)
        self.assertIn("_preset_link_action_worker", cleanup_source)

    def test_user_presets_storage_actions_run_through_worker(self) -> None:
        pin_source = inspect.getsource(UserPresetsPageBase._on_toggle_pin_preset)
        rating_source = inspect.getsource(UserPresetsPageBase._show_rating_menu)
        rating_menu_source = inspect.getsource(preset_rating_menu.show_preset_rating_menu)
        move_source = inspect.getsource(UserPresetsPageBase._move_preset_by_step)
        drop_source = inspect.getsource(UserPresetsPageBase._on_item_dropped)
        finished_source = inspect.getsource(UserPresetsPageBase._on_preset_storage_action_finished)

        self.assertTrue(hasattr(user_presets_action_workers, "UserPresetStorageActionWorker"))
        worker_source = inspect.getsource(user_presets_action_workers.UserPresetStorageActionWorker.run)
        request_source = inspect.getsource(UserPresetsPageBase._request_preset_storage_action)
        create_source = inspect.getsource(UserPresetsPageBase.create_preset_storage_action_worker)
        runtime_source = inspect.getsource(user_presets_page_runtime.UserPresetsPageRuntime)

        for source in (pin_source, rating_source, move_source, drop_source):
            self.assertIn("_request_preset_storage_action", source)
            self.assertNotIn("toggle_pin_preset_action", source)
            self.assertNotIn("move_preset_by_step_action", source)
            self.assertNotIn("handle_item_dropped_action", source)
            self.assertNotIn("set_preset_rating(", source)
            self.assertNotIn(".toggle_preset_pin(", source)
            self.assertNotIn(".move_preset_by_step(", source)
            self.assertNotIn(".move_preset_on_drop(", source)

        self.assertNotIn("set_preset_rating(", rating_menu_source)
        self.assertNotIn("get_preset_item_meta", rating_menu_source)
        self.assertNotIn("folder_scope", rating_menu_source)
        self.assertIn("current_rating=", rating_source)
        self.assertIn("cached_presets_metadata", rating_source)
        self.assertIn("_update_cached_preset_rating", finished_source)
        self.assertIn("create_preset_storage_action_worker", request_source)
        self.assertNotIn("UserPresetStorageActionWorker", create_source)
        self.assertIn("_create_preset_storage_action_worker_fn", create_source)
        self.assertNotIn("from presets.folders import toggle_preset_pin", runtime_source)
        self.assertNotIn("from presets.folders import set_preset_rating", runtime_source)
        self.assertNotIn("from presets.folders import move_preset_by_step", runtime_source)
        self.assertNotIn("from presets.folders import move_preset_after", runtime_source)
        self.assertIn("self._toggle_preset_pin", worker_source)
        self.assertIn("self._set_preset_rating", worker_source)
        self.assertIn("self._move_preset_by_step", worker_source)
        self.assertIn("self._move_preset_on_drop", worker_source)
        self.assertIn("self._load_folder_state", worker_source)
        self.assertNotIn("storage_api.", worker_source)
        self.assertIn('self._action == "pin"', worker_source)
        self.assertIn('context["folder_state"]', worker_source)
        self.assertIn("update_cached_folder_state", finished_source)

    def test_user_presets_folder_actions_run_through_worker(self) -> None:
        toggle_source = inspect.getsource(UserPresetsPageBase._on_toggle_folder)
        menu_source = inspect.getsource(UserPresetsPageBase._show_folder_menu)
        folder_menu_source = inspect.getsource(preset_folder_menu.show_preset_folder_menu)

        self.assertTrue(hasattr(user_presets_action_workers, "UserPresetFolderActionWorker"))
        worker_source = inspect.getsource(user_presets_action_workers.UserPresetFolderActionWorker.run)
        request_source = inspect.getsource(UserPresetsPageBase._request_preset_folder_action)
        action_finished_source = inspect.getsource(UserPresetsPageBase._on_preset_folder_action_finished)
        finished_source = inspect.getsource(UserPresetsPageBase._on_preset_folder_action_worker_finished)
        show_source = inspect.getsource(UserPresetsPageBase._show_folder_menu)

        for source in (toggle_source, menu_source):
            self.assertIn("_request_preset_folder_action", source)
            self.assertNotIn("set_preset_folder_collapsed(", source)
            self.assertNotIn("create_preset_folder(", source)
            self.assertNotIn("rename_preset_folder(", source)
            self.assertNotIn("delete_preset_folder(", source)
            self.assertNotIn("reset_preset_folders(", source)

        for forbidden in (
            "create_preset_folder(",
            "rename_preset_folder(",
            "delete_preset_folder(",
            "move_preset_folder_by_step(",
            "set_preset_folder_collapsed(",
            "reset_preset_folders(",
        ):
            self.assertNotIn(forbidden, folder_menu_source)

        self.assertNotIn("load_preset_folder_state", folder_menu_source)
        self.assertIn("folder_state", folder_menu_source)
        self.assertIn('"load_state"', show_source)
        self.assertIn("self._create_preset_folder", worker_source)
        self.assertIn("self._rename_preset_folder", worker_source)
        self.assertIn("self._delete_preset_folder", worker_source)
        self.assertIn("self._move_preset_folder_by_step", worker_source)
        self.assertIn("self._set_preset_folder_collapsed", worker_source)
        self.assertIn("self._reset_preset_folders", worker_source)
        self.assertIn("self._load_preset_folder_state", worker_source)
        self.assertNotIn("from presets.folders", worker_source)
        self.assertNotIn("from presets.folders import", inspect.getsource(UserPresetsPageBase))
        self.assertIn('context["folder_state"]', worker_source)
        self.assertIn("_preset_folder_action_pending.append", request_source)
        self.assertIn("_preset_folder_action_pending.pop(0)", finished_source)
        self.assertIn("update_cached_folder_state", action_finished_source)
        self.assertIn("show_menu", action_finished_source)
        self.assertIn("create_preset_folder_action_worker", request_source)
        create_source = inspect.getsource(UserPresetsPageBase.create_preset_folder_action_worker)
        self.assertNotIn("UserPresetFolderActionWorker", create_source)
        self.assertIn("_create_preset_folder_action_worker_fn", create_source)

    def test_profile_folder_actions_run_through_worker(self) -> None:
        toggle_source = inspect.getsource(PresetSetupPageBase._on_folder_toggled)
        menu_source = inspect.getsource(PresetSetupPageBase._on_folder_context_requested)
        folder_menu_source = inspect.getsource(profile_folder_menu.show_profile_folder_menu)

        self.assertTrue(hasattr(profile_setup_loader, "ProfileFolderActionWorker"))
        worker_source = inspect.getsource(profile_setup_loader.ProfileFolderActionWorker.run)
        request_source = inspect.getsource(PresetSetupPageBase._request_profile_folder_action)
        action_finished_source = inspect.getsource(PresetSetupPageBase._on_profile_folder_action_finished)
        finished_source = inspect.getsource(PresetSetupPageBase._on_profile_folder_action_worker_finished)
        show_source = inspect.getsource(PresetSetupPageBase._on_folder_context_requested)

        for source in (toggle_source, menu_source):
            self.assertIn("_request_profile_folder_action", source)
            self.assertNotIn("set_profile_folder_collapsed(", source)
            self.assertNotIn("create_profile_folder(", source)
            self.assertNotIn("rename_profile_folder(", source)
            self.assertNotIn("delete_profile_folder(", source)
            self.assertNotIn("reset_profile_folders(", source)

        for forbidden in (
            "create_profile_folder(",
            "rename_profile_folder(",
            "delete_profile_folder(",
            "move_profile_folder_by_step(",
            "set_profile_folder_collapsed(",
            "reset_profile_folders(",
        ):
            self.assertNotIn(forbidden, folder_menu_source)

        self.assertNotIn("load_profile_folder_state", folder_menu_source)
        self.assertIn("folder_state", folder_menu_source)
        self.assertIn('"load_state"', show_source)
        self.assertIn("self._create_profile_folder", worker_source)
        self.assertIn("self._rename_profile_folder", worker_source)
        self.assertIn("self._delete_profile_folder", worker_source)
        self.assertIn("self._move_profile_folder_by_step", worker_source)
        self.assertIn("self._set_profile_folder_collapsed", worker_source)
        self.assertIn("self._reset_profile_folders", worker_source)
        self.assertIn("self._load_profile_folder_state", worker_source)
        self.assertNotIn("from profile.folders", worker_source)
        self.assertNotIn("from profile.folders import", inspect.getsource(PresetSetupPageBase))
        self.assertIn("_profile_folder_action_pending.append", request_source)
        self.assertIn("_profile_folder_action_pending.pop(0)", finished_source)
        self.assertIn("show_menu", action_finished_source)
        self.assertIn("_create_profile_folder_action_worker", request_source)
        create_source = inspect.getsource(PresetSetupPageBase._create_profile_folder_action_worker)
        self.assertNotIn("ProfileFolderActionWorker", create_source)
        self.assertIn("_create_profile_folder_action_worker_fn", create_source)

    def test_profile_move_updates_visible_list_locally_after_worker(self) -> None:
        finished_source = inspect.getsource(PresetSetupPageBase._on_profile_move_finished)
        local_source = inspect.getsource(PresetSetupPageBase._apply_profile_move_locally)
        list_source = inspect.getsource(ProfilesList)

        self.assertIn("_apply_profile_move_locally", finished_source)
        self.assertIn("refresh_from_preset_switch", finished_source)
        self.assertLess(finished_source.index("_apply_profile_move_locally"), finished_source.index("refresh_from_preset_switch"))
        self.assertIn("move_profile_item", list_source)
        self.assertIn("move_profile_item", local_source)

    def test_profile_commands_reuse_service_cache(self) -> None:
        source = inspect.getsource(profile_commands._profile_preset_service)

        self.assertIn("_preset_service_cache", source)
        self.assertIn("cache[key]", source)

    def test_profile_service_exposes_cached_profile_payload_without_rebuilding(self) -> None:
        service_source = inspect.getsource(ProfilePresetService.get_cached_profile_list)
        revision_source = inspect.getsource(ProfilePresetService._current_profile_list_revision)
        command_source = inspect.getsource(profile_commands.get_cached_profile_list)

        self.assertIn("_profile_list_lock", service_source)
        self.assertIn("acquire(blocking=False)", service_source)
        self.assertIn("_profile_list_snapshot_revision", service_source)
        self.assertIn("return snapshot", service_source)
        self.assertNotIn("_list_profiles_locked(", service_source)
        self.assertIn("_selected_preset_revision", revision_source)
        self.assertIn("load_profile_folder_state", revision_source)
        self.assertIn("get_cached_profile_list", command_source)

    def test_preset_setup_page_always_uses_worker_for_profile_payload(self) -> None:
        source = inspect.getsource(PresetSetupPageBase._request_profiles_payload)

        self.assertNotIn("get_cached_profile_list", source)
        self.assertNotIn("_apply_cached_profile_payload", source)
        self.assertIn("create_profile_list_load_worker", source)
        self.assertNotIn("_show_loading_skeleton", source)

    def test_preset_setup_force_refresh_still_uses_worker_path(self) -> None:
        source = inspect.getsource(PresetSetupPageBase._request_profiles_payload)

        before_worker = source.split("worker =", 1)[0]

        self.assertNotIn("get_cached_profile_list", before_worker)
        self.assertNotIn("if not force:", before_worker)
        self.assertNotIn("_apply_cached_profile_payload", before_worker)

    def test_profile_service_has_selected_preset_snapshot(self) -> None:
        source = inspect.getsource(ProfilePresetService.load_selected_preset)
        helper_source = inspect.getsource(ProfilePresetService._load_selected_preset_for_revision)

        self.assertIn("_selected_preset_revision", source)
        self.assertIn("_selected_preset_snapshot", helper_source)

    def test_profile_list_worker_logs_full_profile_payload_duration(self) -> None:
        source = inspect.getsource(ProfileListLoadWorker.run)

        self.assertIn("time.perf_counter", source)
        self.assertIn("profile_feature.worker.list_profiles.total", source)

    def test_profile_list_worker_receives_loader_function(self) -> None:
        init_source = inspect.getsource(ProfileListLoadWorker.__init__)
        run_source = inspect.getsource(ProfileListLoadWorker.run)

        self.assertIn("load_profiles", init_source)
        self.assertIn("self._load_profiles", init_source)
        self.assertNotIn("self._service", init_source)
        self.assertNotIn("self._profile", init_source)
        self.assertNotIn("launch_method", init_source)
        self.assertIn("self._load_profiles()", run_source)
        self.assertNotIn("self._service.list_profiles", run_source)
        self.assertNotIn("self._profile.list_profiles", run_source)

    def test_profile_service_logs_profile_payload_stages(self) -> None:
        source = inspect.getsource(ProfilePresetService._list_profiles_locked)

        self.assertIn("profile_feature.strategy_catalogs.load", source)
        self.assertIn("profile_feature.templates.load", source)
        self.assertIn("profile_feature.folder_state.load", source)
        self.assertIn("profile_feature.sources.build", source)
        self.assertIn("profile_feature.profile_list_item.build", source)

    def test_profile_worker_yields_during_large_payload_builds(self) -> None:
        source = inspect.getsource(ProfilePresetService._list_profiles_locked)
        helper_source = inspect.getsource(ProfilePresetService._yield_profile_payload_worker)

        self.assertIn("_yield_profile_payload_worker", source)
        self.assertIn("time.sleep(0)", helper_source)

    def test_profile_service_serializes_profile_list_snapshot_builds(self) -> None:
        source = inspect.getsource(ProfilePresetService.list_profiles)

        self.assertIn("_profile_list_lock", source)
        self.assertIn("_list_profiles_locked", source)

    def test_preset_setup_page_logs_profile_list_ui_apply_stages(self) -> None:
        source = inspect.getsource(PresetSetupPageBase._apply_payload)

        self.assertIn("profile_ui.apply_payload.total", source)
        self.assertIn("profile_ui.profile_list.create", source)
        self.assertIn("profile_ui.profile_list.build", source)
        self.assertIn("profile_ui.profile_list.attach", source)

    def test_slow_navigation_pages_log_local_timing_stages(self) -> None:
        appearance_source = inspect.getsource(AppearancePage._build_ui)
        appearance_lower_source = inspect.getsource(AppearancePage._ensure_lower_sections_built)
        logs_refresh_source = inspect.getsource(LogsPage._refresh_logs_list)
        logs_stats_source = inspect.getsource(LogsPage._update_stats)
        telegram_init_source = inspect.getsource(TelegramProxyPage.__init__)
        telegram_loaded_source = inspect.getsource(TelegramProxyPage._on_initial_state_loaded)
        telegram_apply_source = inspect.getsource(TelegramProxyPage._apply_initial_settings_state)
        blockcheck_source = inspect.getsource(BlockcheckPage._build_ui)
        blockcheck_initial_source = inspect.getsource(BlockcheckPage._on_initial_state_loaded)
        hosts_activation_source = inspect.getsource(HostsPage.on_page_activated)
        hosts_rebuild_source = inspect.getsource(HostsPage._rebuild_services_selectors)

        self.assertIn("appearance_ui.build.total", appearance_source)
        self.assertIn("appearance_ui.accent_section.build", appearance_lower_source)
        self.assertIn("appearance_ui.lower_sections.build", appearance_lower_source)
        self.assertIn("logs_ui.refresh_logs_list.total", logs_refresh_source)
        self.assertIn("logs_ui.update_stats.total", logs_stats_source)
        self.assertIn("_request_initial_state_load", telegram_init_source)
        self.assertIn("telegram_proxy_ui.initial_state.load", telegram_loaded_source)
        self.assertIn("telegram_proxy_ui.settings.apply", telegram_apply_source)
        self.assertIn("blockcheck_ui.initial_state.load", blockcheck_initial_source)
        self.assertIn("blockcheck_ui.build.total", blockcheck_source)
        self.assertIn("blockcheck_ui.domain_chips.apply", blockcheck_source)
        self.assertIn("hosts_ui.activation.total", hosts_activation_source)
        self.assertIn("hosts_ui.services.rebuild", hosts_rebuild_source)

    def test_appearance_page_initial_state_is_single_backend_plan(self) -> None:
        build_source = inspect.getsource(AppearancePage._build_ui)
        ensure_source = inspect.getsource(AppearancePage._ensure_lower_sections_built)
        settings_source = inspect.getsource(appearance_settings.load_page_initial_state)

        self.assertNotIn("load_page_initial_state", build_source)
        self.assertNotIn("load_page_initial_state", ensure_source)
        self.assertIn("_request_initial_state_load", build_source)
        self.assertIn("initial_state.ui_language = self._ui_language", build_source)
        self.assertNotIn("appearance_settings.load_ui_language()", build_source)
        self.assertNotIn("appearance_settings.load_window_opacity()", build_source)
        self.assertNotIn("self._load_accent_color()", build_source)
        self.assertNotIn("self._load_extra_accent_settings()", build_source)
        self.assertNotIn("self._load_performance_settings()", build_source)
        self.assertNotIn("self._load_display_mode()", build_source)
        self.assertNotIn("self._load_bg_preset()", build_source)

        self.assertIn("read_settings", settings_source)
        self.assertNotIn("get_display_mode", settings_source)
        self.assertNotIn("get_window_opacity", settings_source)
        self.assertNotIn("get_animations_enabled", settings_source)

    def test_appearance_initial_state_loads_through_worker(self) -> None:
        self.assertTrue(hasattr(appearance_workers, "AppearanceInitialStateLoadWorker"))
        appearance_feature = importlib.import_module("app.feature_facades.appearance")
        worker_source = inspect.getsource(appearance_workers.AppearanceInitialStateLoadWorker.run)
        worker_init_source = inspect.getsource(appearance_workers.AppearanceInitialStateLoadWorker.__init__)
        page_source = inspect.getsource(AppearancePage)
        page_init_source = inspect.getsource(AppearancePage.__init__)
        create_source = inspect.getsource(AppearancePage.create_initial_state_load_worker)
        feature_source = inspect.getsource(appearance_feature.AppearanceFeature)
        build_source = inspect.getsource(AppearancePage._build_ui)

        self.assertIn("load_page_initial_state", worker_source)
        self.assertIn("load_page_initial_state", worker_init_source)
        self.assertIn("appearance_feature", page_init_source)
        self.assertIn("create_initial_state_load_worker", page_source)
        self.assertIn("create_initial_state_load_worker", feature_source)
        self.assertNotIn("AppearanceInitialStateLoadWorker", create_source)
        self.assertIn("self._appearance.create_initial_state_load_worker", create_source)
        self.assertIn("_initial_state_load_worker", page_source)
        self.assertIn("_request_initial_state_load", build_source)
        self.assertNotIn("settings.appearance", worker_source)

    def test_base_page_language_uses_warmed_cache_not_settings_read(self) -> None:
        base_source = inspect.getsource(BasePage._resolve_ui_language)
        navigation_source = inspect.getsource(navigation_text_sync.resolve_ui_language)

        self.assertIn("peek_warmed_ui_language", base_source)
        self.assertIn("peek_warmed_ui_language", navigation_source)
        self.assertNotIn("load_ui_language", base_source)
        self.assertNotIn("load_ui_language", navigation_source)

    def test_appearance_lower_sections_are_built_after_initial_shell(self) -> None:
        build_source = inspect.getsource(AppearancePage._build_ui)
        activated_source = inspect.getsource(AppearancePage.on_page_activated)
        schedule_source = inspect.getsource(AppearancePage._schedule_lower_sections_build)
        ensure_source = inspect.getsource(AppearancePage._ensure_lower_sections_built)

        self.assertNotIn("build_holiday_sections", build_source)
        self.assertNotIn("build_opacity_section", build_source)
        self.assertNotIn("build_performance_section", build_source)
        self.assertIn("_schedule_lower_sections_build", activated_source)
        self.assertIn("QTimer.singleShot", schedule_source)
        self.assertIn("build_holiday_sections", ensure_source)
        self.assertIn("build_performance_section", ensure_source)

    def test_appearance_settings_save_runs_through_worker(self) -> None:
        appearance_feature = importlib.import_module("app.feature_facades.appearance")
        page_source = inspect.getsource(AppearancePage)

        self.assertTrue(hasattr(appearance_workers, "AppearanceSettingsSaveWorker"))
        worker_source = inspect.getsource(appearance_workers.AppearanceSettingsSaveWorker.run)
        worker_init_source = inspect.getsource(appearance_workers.AppearanceSettingsSaveWorker.__init__)
        create_source = inspect.getsource(AppearancePage.create_appearance_save_worker)
        feature_source = inspect.getsource(appearance_feature.AppearanceFeature)
        request_source = inspect.getsource(AppearancePage._request_appearance_save)
        finished_source = inspect.getsource(AppearancePage._on_appearance_save_worker_finished)

        for method_name in (
            "_on_display_mode_changed",
            "_on_ui_language_changed",
            "_on_rkn_background_changed",
            "_on_bg_preset_toggled",
            "_on_mica_changed",
            "_on_opacity_changed",
            "_on_snowflakes_changed",
            "_on_garland_changed",
            "_on_accent_color_changed",
            "_on_follow_windows_accent_changed",
            "_on_tinted_bg_changed",
            "_on_tinted_intensity_changed",
            "set_premium_status",
            "_on_animations_changed",
            "_on_smooth_scroll_changed",
            "_on_editor_smooth_scroll_changed",
        ):
            source = inspect.getsource(getattr(AppearancePage, method_name))
            self.assertIn("_request_appearance_save", source)
            self.assertNotIn("appearance_settings.save_", source)

        self.assertIn("create_appearance_save_worker", page_source)
        self.assertIn("create_appearance_save_worker", feature_source)
        self.assertNotIn("AppearanceSettingsSaveWorker", create_source)
        self.assertIn("self._appearance.create_appearance_save_worker", create_source)
        self.assertIn("_coalesce_appearance_save_pending", request_source)
        self.assertIn("_appearance_save_pending.append", page_source)
        self.assertIn("_appearance_save_pending.pop(0)", finished_source)
        self.assertIn("save_display_mode", worker_init_source)
        self.assertIn("save_ui_language", worker_init_source)
        self.assertIn("save_background_preset", worker_init_source)
        self.assertIn("save_mica_enabled", worker_init_source)
        self.assertIn("save_window_opacity", worker_init_source)
        self.assertIn("save_accent_color", worker_init_source)
        self.assertIn("save_animations_enabled", worker_init_source)
        self.assertIn("save_display_mode", worker_source)
        self.assertIn("save_ui_language", worker_source)
        self.assertIn("save_background_preset", worker_source)
        self.assertIn("save_mica_enabled", worker_source)
        self.assertIn("save_window_opacity", worker_source)
        self.assertIn("save_accent_color", worker_source)
        self.assertIn("save_animations_enabled", worker_source)
        self.assertNotIn("settings.appearance", worker_source)

    def test_telegram_proxy_restart_request_survives_queued_settings_saves(self) -> None:
        from telegram_proxy.ui.settings_save_flow import merge_restart_request

        self.assertEqual(merge_restart_request("", "schedule"), "schedule")
        self.assertEqual(merge_restart_request("schedule", ""), "schedule")
        self.assertEqual(merge_restart_request("schedule", "now"), "now")
        self.assertEqual(merge_restart_request("now", "schedule"), "now")

        init_source = inspect.getsource(TelegramProxyPage.__init__)
        finished_source = inspect.getsource(TelegramProxyPage._on_settings_save_finished)

        self.assertIn("_settings_save_restart_pending", init_source)
        self.assertIn("merge_restart_request", finished_source)
        self.assertIn("_settings_save_restart_pending", finished_source)

    def test_appearance_rkn_background_options_load_through_worker(self) -> None:
        appearance_feature = importlib.import_module("app.feature_facades.appearance")
        page_source = inspect.getsource(AppearancePage)
        create_source = inspect.getsource(AppearancePage.create_rkn_background_options_load_worker)
        reload_source = inspect.getsource(AppearancePage._reload_rkn_background_options)

        self.assertTrue(hasattr(appearance_workers, "AppearanceRknBackgroundOptionsLoadWorker"))
        worker_source = inspect.getsource(appearance_workers.AppearanceRknBackgroundOptionsLoadWorker.run)
        worker_init_source = inspect.getsource(appearance_workers.AppearanceRknBackgroundOptionsLoadWorker.__init__)
        feature_source = inspect.getsource(appearance_feature.AppearanceFeature)

        self.assertIn("_rkn_background_options_worker", page_source)
        self.assertIn("create_rkn_background_options_load_worker", page_source)
        self.assertIn("create_rkn_background_options_load_worker", feature_source)
        self.assertNotIn("AppearanceRknBackgroundOptionsLoadWorker", create_source)
        self.assertIn("self._appearance.create_rkn_background_options_load_worker", create_source)
        self.assertIn("_request_rkn_background_options_load", reload_source)
        self.assertNotIn("appearance_settings.load_rkn_background()", reload_source)
        self.assertNotIn("get_rkn_background_options()", reload_source)
        self.assertIn("load_rkn_background", worker_init_source)
        self.assertIn("get_rkn_background_options", worker_init_source)
        self.assertIn("load_rkn_background", worker_source)
        self.assertIn("get_rkn_background_options", worker_source)
        self.assertNotIn("settings.appearance", worker_source)

    def test_window_background_uses_warmed_rkn_background_without_folder_scan(self) -> None:
        apply_source = inspect.getsource(ui_theme.apply_window_background)
        resolve_source = inspect.getsource(ui_theme.resolve_rkn_background_path)

        self.assertIn("peek_warmed_rkn_background", apply_source)
        self.assertNotIn("load_rkn_background", apply_source)
        self.assertNotIn("get_rkn_background_options", resolve_source)
        self.assertIn("_RKN_BG_PREFERRED", resolve_source)

    def test_theme_uses_warmed_accent_and_tinted_settings(self) -> None:
        tint_source = inspect.getsource(ui_theme._compute_tint_color)
        accent_source = inspect.getsource(ui_theme._sync_theme_accent_to_qfluent)

        self.assertIn("peek_warmed_tinted_settings", tint_source)
        self.assertIn("peek_warmed_accent_color", accent_source)
        self.assertNotIn("load_tinted_settings", tint_source)
        self.assertNotIn("load_accent_color", accent_source)

    def test_window_appearance_uses_warmed_state_without_settings_reads(self) -> None:
        background_source = inspect.getsource(ui_theme.apply_window_background)
        opacity_source = inspect.getsource(window_appearance_state.apply_window_opacity_value)
        startup_source = inspect.getsource(main_entry._configure_window_appearance)

        combined = "\n".join((background_source, opacity_source, startup_source))
        self.assertIn("peek_warmed_background_preset", combined)
        self.assertIn("peek_warmed_mica_enabled", combined)
        self.assertIn("peek_warmed_window_opacity", combined)
        self.assertNotIn("load_background_preset", combined)
        self.assertNotIn("load_mica_enabled", combined)
        self.assertNotIn("load_window_opacity", combined)

    def test_window_appearance_bindings_use_warmed_state_without_settings_reads(self) -> None:
        bindings_source = inspect.getsource(window_appearance_bindings.initialize_window_appearance_bindings)
        holiday_source = inspect.getsource(window_appearance_bindings.initialize_window_holiday_effects)
        smooth_source = "\n".join(
            (
                inspect.getsource(smooth_scroll.get_page_smooth_scroll_enabled),
                inspect.getsource(smooth_scroll.get_editor_smooth_scroll_enabled),
                inspect.getsource(smooth_scroll.get_effective_editor_smooth_scroll_enabled),
            )
        )
        animation_source = "\n".join(
            (
                inspect.getsource(animation_policy.are_animations_enabled),
                inspect.getsource(animation_policy.apply_window_animation_policy),
            )
        )
        combined = "\n".join((bindings_source, holiday_source, smooth_source, animation_source))

        self.assertIn("peek_warmed_animations_enabled", combined)
        self.assertIn("peek_warmed_smooth_scroll_enabled", combined)
        self.assertIn("peek_warmed_editor_smooth_scroll_enabled", combined)
        self.assertIn("peek_warmed_premium_effects", combined)
        self.assertNotIn("load_animations_enabled", combined)
        self.assertNotIn("load_smooth_scroll_enabled", combined)
        self.assertNotIn("load_editor_smooth_scroll_enabled", combined)
        self.assertNotIn("load_premium_effects", combined)
        self.assertNotIn("load_window_opacity", combined)

    def test_appearance_windows_accent_loads_through_worker(self) -> None:
        appearance_feature = importlib.import_module("app.feature_facades.appearance")
        self.assertTrue(hasattr(appearance_workers, "AppearanceWindowsAccentLoadWorker"))
        worker_source = inspect.getsource(appearance_workers.AppearanceWindowsAccentLoadWorker.run)
        worker_init_source = inspect.getsource(appearance_workers.AppearanceWindowsAccentLoadWorker.__init__)
        page_source = inspect.getsource(AppearancePage)
        create_source = inspect.getsource(AppearancePage.create_windows_accent_load_worker)
        handler_source = inspect.getsource(AppearancePage._on_follow_windows_accent_changed)
        apply_source = inspect.getsource(AppearancePage._apply_windows_accent)
        feature_source = inspect.getsource(appearance_feature.AppearanceFeature)

        self.assertIn("load_windows_system_accent", worker_source)
        self.assertIn("load_windows_system_accent", worker_init_source)
        self.assertIn("create_windows_accent_load_worker", page_source)
        self.assertIn("create_windows_accent_load_worker", feature_source)
        self.assertNotIn("AppearanceWindowsAccentLoadWorker", create_source)
        self.assertIn("self._appearance.create_windows_accent_load_worker", create_source)
        self.assertIn("_windows_accent_load_worker", page_source)
        self.assertIn("_request_windows_accent_load", handler_source)
        self.assertNotIn("load_windows_system_accent", apply_source)
        self.assertNotIn("settings.appearance", worker_source)

    def test_premium_navigation_does_not_read_device_info_during_language_refresh(self) -> None:
        language_source = inspect.getsource(premium_page_lifecycle.apply_premium_language)

        self.assertNotIn("update_device_info_fn()", language_source)
        self.assertNotIn("update_device_info_fn", inspect.signature(premium_page_lifecycle.apply_premium_language).parameters)

    def test_premium_pairing_autopoll_does_not_initialize_checker_when_storage_is_not_ready(self) -> None:
        class _PremiumFeature:
            def is_checker_ready(self) -> bool:
                return False

            def is_storage_ready(self) -> bool:
                return False

            def read_pairing_snapshot(self, *, current_time: int):
                raise AssertionError("read_pairing_snapshot must not run before storage is ready")

        self.assertFalse(
            premium_pairing_workflow.can_poll_pairing_status(
                premium_feature=_PremiumFeature(),
                page_visible=True,
                activation_in_progress=False,
                connection_test_in_progress=False,
                worker_running=False,
                current_time=1,
            )
        )

    def test_premium_pairing_autopoll_uses_cached_snapshot_when_storage_is_ready(self) -> None:
        class _PremiumFeature:
            def is_checker_ready(self) -> bool:
                return True

            def is_storage_ready(self) -> bool:
                return True

            def read_pairing_snapshot(self, *, current_time: int):
                raise AssertionError("activation must not read pairing snapshot when cached snapshot is available")

        self.assertTrue(
            premium_pairing_workflow.can_poll_pairing_status(
                premium_feature=_PremiumFeature(),
                page_visible=True,
                activation_in_progress=False,
                connection_test_in_progress=False,
                worker_running=False,
                current_time=1,
                pairing_snapshot={
                    "has_device_token": False,
                    "has_pending_pair_code": True,
                },
            )
        )

    def test_premium_page_passes_cached_pairing_snapshot_to_autopoll(self) -> None:
        page_source = inspect.getsource(PremiumPage)
        sync_source = inspect.getsource(PremiumPage._sync_pairing_status_autopoll)
        device_info_loaded_source = inspect.getsource(PremiumPage._on_device_info_loaded)

        self.assertNotIn("def _has_pending_pair_code", page_source)
        self.assertNotIn("has_pending_pair_code(", page_source)
        self.assertIn("pairing_snapshot=self._pairing_autopoll_snapshot", sync_source)
        self.assertIn("_set_pairing_autopoll_snapshot_from_device_info", device_info_loaded_source)

    def test_premium_device_info_refresh_runs_through_worker(self) -> None:
        spec = importlib.util.find_spec("donater.device_info_worker")
        self.assertIsNotNone(spec)
        device_info_worker = importlib.import_module("donater.device_info_worker")
        premium_feature_cls = __import__("app.feature_facades.premium", fromlist=["PremiumFeature"]).PremiumFeature

        page_source = inspect.getsource(PremiumPage)
        handler_source = inspect.getsource(PremiumPage._update_device_info)
        feature_source = inspect.getsource(premium_feature_cls)

        self.assertTrue(hasattr(device_info_worker, "PremiumDeviceInfoLoadWorker"))
        worker_source = inspect.getsource(device_info_worker.PremiumDeviceInfoLoadWorker.run)

        self.assertIn("_request_device_info_load", handler_source)
        self.assertNotIn("update_device_info_labels", handler_source)
        self.assertNotIn("read_device_info_snapshot", handler_source)
        self.assertIn("create_device_info_load_worker", page_source)
        self.assertIn("_device_info_runtime", page_source)
        self.assertIn("create_device_info_load_worker", feature_source)
        self.assertIn("read_device_info_snapshot=self.read_device_info_snapshot", feature_source)
        self.assertNotIn("premium_feature=self", feature_source)
        self.assertNotIn("self._premium", inspect.getsource(device_info_worker.PremiumDeviceInfoLoadWorker))
        self.assertIn("read_device_info_snapshot", worker_source)

    def test_premium_click_actions_initialize_checker_through_worker(self) -> None:
        create_source = inspect.getsource(PremiumPage._create_pair_code)
        status_source = inspect.getsource(PremiumPage._check_status)
        connection_source = inspect.getsource(PremiumPage._test_connection)
        init_request_source = inspect.getsource(PremiumPage._request_checker_init)

        for source in (create_source, status_source, connection_source):
            self.assertIn("_request_checker_init", source)
            self.assertNotIn("_init_checker()", source)
            self.assertNotIn("ensure_checker_ready", source)

        self.assertIn("_start_premium_init_worker", init_request_source)
        self.assertNotIn("ensure_checker_ready", init_request_source)

    def test_premium_runtime_init_starts_checker_in_worker(self) -> None:
        calls: list[str] = []

        premium_page_lifecycle.run_premium_runtime_init_once(
            runtime_initialized=False,
            build_page_init_plan_fn=premium_page_plans.build_page_init_plan,
            set_runtime_initialized_fn=lambda value: calls.append(f"runtime={value}"),
            start_init_worker_fn=lambda: calls.append("worker"),
            set_server_status_mode_fn=lambda value: calls.append(f"mode={value}"),
            set_server_status_message_fn=lambda value: calls.append(f"message={value}"),
            set_server_status_success_fn=lambda value: calls.append(f"success={value}"),
            render_server_status_fn=lambda: calls.append("render"),
        )

        self.assertIn("runtime=True", calls)
        self.assertIn("worker", calls)
        self.assertNotIn("init_checker", inspect.getsource(premium_page_lifecycle.run_premium_runtime_init_once))

    def test_premium_open_bot_runs_through_worker(self) -> None:
        spec = importlib.util.find_spec("donater.open_bot_worker")
        self.assertIsNotNone(spec)
        open_bot_worker = importlib.import_module("donater.open_bot_worker")

        page_source = inspect.getsource(PremiumPage)
        handler_source = inspect.getsource(PremiumPage._open_extend_bot)
        feature_source = inspect.getsource(__import__("app.feature_facades.premium", fromlist=["PremiumFeature"]).PremiumFeature)

        self.assertTrue(hasattr(open_bot_worker, "PremiumOpenBotWorker"))
        worker_source = inspect.getsource(open_bot_worker.PremiumOpenBotWorker.run)

        self.assertIn("_request_open_extend_bot", handler_source)
        self.assertNotIn(".open_extend_bot(", handler_source)
        self.assertIn("create_open_extend_bot_worker", page_source)
        self.assertIn("_open_bot_runtime", page_source)
        self.assertIn("create_open_extend_bot_worker", feature_source)
        self.assertIn("open_extend_bot=self.open_extend_bot", feature_source)
        self.assertIn("_open_extend_bot", worker_source)
        self.assertNotIn("premium_commands", worker_source)
        self.assertIn("open_extend_bot", worker_source)

    def test_premium_reset_storage_runs_through_worker(self) -> None:
        spec = importlib.util.find_spec("donater.reset_worker")
        self.assertIsNotNone(spec)
        reset_worker = importlib.import_module("donater.reset_worker")

        page_source = inspect.getsource(PremiumPage)
        handler_source = inspect.getsource(PremiumPage._change_key)
        workflow_source = inspect.getsource(__import__("donater.ui.status_workflow", fromlist=["apply_reset_plan_ui"]).apply_reset_plan_ui)
        feature_source = inspect.getsource(__import__("app.feature_facades.premium", fromlist=["PremiumFeature"]).PremiumFeature)

        self.assertTrue(hasattr(reset_worker, "PremiumResetStorageWorker"))
        worker_source = inspect.getsource(reset_worker.PremiumResetStorageWorker.run)

        self.assertIn("_request_reset_storage", handler_source)
        self.assertNotIn("apply_reset_plan_ui(", handler_source)
        self.assertNotIn("reset_premium_storage", workflow_source)
        self.assertIn("create_reset_storage_worker", page_source)
        self.assertIn("_reset_storage_runtime", page_source)
        self.assertIn("create_reset_storage_worker", feature_source)
        self.assertIn("reset_storage=self.reset_premium_storage", feature_source)
        self.assertNotIn("premium_feature=self", feature_source)
        self.assertNotIn("self._premium", inspect.getsource(reset_worker.PremiumResetStorageWorker))
        self.assertIn("_reset_storage", worker_source)

    def test_support_page_external_links_run_through_worker(self) -> None:
        from app.feature_facades.external import ExternalActionsFeature
        import app.external_workers as external_workers

        page_source = inspect.getsource(SupportPage)
        feature_source = inspect.getsource(ExternalActionsFeature)
        worker_source = inspect.getsource(external_workers.ExternalActionWorker.run)

        self.assertTrue(hasattr(external_workers, "ExternalActionWorker"))
        self.assertIn("_support_open_runtime", page_source)
        self.assertIn("create_support_open_action_worker", page_source)
        self.assertIn("_create_support_open_action_worker", page_source)
        self.assertIn("create_external_action_worker", feature_source)
        self.assertNotIn("ui.pages.support_open_worker", page_source)
        for method_name in (
            "_open_support_discussions",
            "_open_telegram_support",
            "_open_discord",
        ):
            source = inspect.getsource(getattr(SupportPage, method_name))
            self.assertIn("_request_support_open_action", source)
            self.assertNotIn("_open_discussions_action()", source)
            self.assertNotIn("_open_telegram_action()", source)
            self.assertNotIn("_open_discord_action()", source)

        self.assertIn("action_fn", worker_source)

    def test_about_page_external_actions_run_through_worker(self) -> None:
        from app.feature_facades.external import ExternalActionsFeature
        import app.external_workers as external_workers

        page_source = inspect.getsource(AboutPage)
        feature_source = inspect.getsource(ExternalActionsFeature)
        worker_source = inspect.getsource(external_workers.ExternalActionWorker.run)

        self.assertTrue(hasattr(external_workers, "ExternalActionWorker"))
        self.assertIn("_about_open_runtime", page_source)
        self.assertIn("create_about_open_action_worker", page_source)
        self.assertIn("_create_about_open_action_worker", page_source)
        self.assertIn("create_external_action_worker", feature_source)
        self.assertNotIn("ui.pages.about_open_worker", page_source)
        for method_name in (
            "_open_support_discussions",
            "_open_telegram_support",
            "_open_discord",
            "_open_forum_for_beginners",
            "_open_help_folder",
            "_open_telegram_news",
            "_open_kvn_channel",
            "_open_kvn_bot",
            "_open_kvn_bypass",
            "_open_kvn_github",
        ):
            source = inspect.getsource(getattr(AboutPage, method_name))
            self.assertIn("_request_about_open_action", source)
            self.assertNotIn("_action()", source)

        self.assertIn("action_fn", worker_source)

    def test_page_language_is_not_reapplied_on_every_repeat_navigation(self) -> None:
        class _Page:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def set_ui_language(self, language: str) -> None:
                self.calls.append(language)

        window = type("_Window", (), {})()
        window.ui_session = type("_Session", (), {"ui_language": "ru"})()
        page = _Page()

        navigation_text_sync.apply_ui_language_to_page(window, page)
        navigation_text_sync.apply_ui_language_to_page(window, page)
        window.ui_session.ui_language = "en"
        navigation_text_sync.apply_ui_language_to_page(window, page)

        self.assertEqual(page.calls, ["ru", "en"])

    def test_page_language_skips_initial_reapply_when_page_already_matches_window(self) -> None:
        class _Page:
            def __init__(self) -> None:
                self._ui_language = "ru"
                self.calls: list[str] = []

            def set_ui_language(self, language: str) -> None:
                self.calls.append(language)

        window = type("_Window", (), {})()
        window.ui_session = type("_Session", (), {"ui_language": "ru"})()
        page = _Page()

        navigation_text_sync.apply_ui_language_to_page(window, page)

        self.assertEqual(page.calls, [])
        self.assertEqual(page._last_applied_ui_language, "ru")

    def test_page_language_still_applies_when_page_language_is_unknown(self) -> None:
        class _Page:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def set_ui_language(self, language: str) -> None:
                self.calls.append(language)

        window = type("_Window", (), {})()
        window.ui_session = type("_Session", (), {"ui_language": "ru"})()
        page = _Page()

        navigation_text_sync.apply_ui_language_to_page(window, page)

        self.assertEqual(page.calls, ["ru"])

    def test_appearance_initial_state_plan_reads_settings_once(self) -> None:
        data = {
            "appearance": {
                "display_mode": "light",
                "ui_language": "en",
                "background_preset": "rkn_chan",
                "rkn_background": "rkn_tyan/bg.webp",
                "mica_enabled": False,
                "accent_color": "#112233",
                "follow_windows_accent": True,
                "tinted_background": True,
                "tinted_background_intensity": 17,
                "animations_enabled": True,
                "smooth_scroll_enabled": True,
                "editor_smooth_scroll_enabled": False,
                "garland_enabled": True,
                "snowflakes_enabled": False,
            },
            "window": {
                "opacity": 73,
            },
        }

        with patch("settings.store.read_settings", return_value=data) as read_settings:
            plan = appearance_settings.load_page_initial_state()

        self.assertEqual(read_settings.call_count, 1)
        self.assertEqual(plan.display_mode, "light")
        self.assertEqual(plan.ui_language, "en")
        self.assertEqual(plan.background_preset, "rkn_chan")
        self.assertEqual(plan.rkn_background, "rkn_tyan/bg.webp")
        self.assertFalse(plan.mica_enabled)
        self.assertEqual(plan.window_opacity, 73)
        self.assertEqual(plan.accent_color, "#112233")
        self.assertTrue(plan.follow_windows_accent)
        self.assertTrue(plan.tinted_background)
        self.assertEqual(plan.tinted_intensity, 17)
        self.assertTrue(plan.animations_enabled)
        self.assertTrue(plan.smooth_scroll_enabled)
        self.assertFalse(plan.editor_smooth_scroll_enabled)
        self.assertTrue(plan.garland_enabled)
        self.assertFalse(plan.snowflakes_enabled)

    def test_telegram_proxy_initial_state_is_backend_plan_not_ui_loading(self) -> None:
        telegram_proxy_workers = importlib.import_module("telegram_proxy.workers")

        init_source = inspect.getsource(TelegramProxyPage.__init__)
        after_source = inspect.getsource(TelegramProxyPage._after_ui_built)
        request_source = inspect.getsource(TelegramProxyPage._request_initial_state_load)
        loaded_source = inspect.getsource(TelegramProxyPage._on_initial_state_loaded)
        cleanup_source = inspect.getsource(TelegramProxyPage.cleanup)
        page_source = inspect.getsource(TelegramProxyPage)
        settings_build_source = inspect.getsource(telegram_proxy_settings_build.build_telegram_proxy_settings_panel)
        settings_source = inspect.getsource(telegram_proxy_settings.load_page_initial_state)
        feature_source = inspect.getsource(TelegramProxyFeature)
        worker_source = inspect.getsource(telegram_proxy_workers.TelegramProxyInitialStateWorker.run)

        self.assertIn("_request_initial_state_load", init_source)
        self.assertIn("_initial_state_runtime", page_source)
        self.assertIn("start_qthread_worker", request_source)
        self.assertIn("bind_worker", request_source)
        self.assertIn("worker.completed.connect(self._on_initial_state_loaded)", request_source)
        self.assertIn("worker.failed.connect(self._on_initial_state_failed)", request_source)
        self.assertIn("_initial_state_runtime.is_current", loaded_source)
        self.assertIn("_initial_state_runtime.stop", cleanup_source)
        self.assertNotIn("_initial_state_worker =", page_source)
        self.assertNotIn("worker.start()", request_source)
        self.assertNotIn("self._telegram_proxy.load_page_initial_state()", init_source)
        self.assertIn("_apply_initial_settings_state", page_source)
        self.assertNotIn("self._load_settings()", after_source)
        self.assertNotIn("load_settings_into_ui", after_source)
        self.assertNotIn("UpstreamCatalog.load_from_runtime", settings_build_source)
        self.assertIn("create_initial_state_worker", page_source)
        self.assertIn("create_page_initial_state_worker", feature_source)
        self.assertNotIn("def load_page_initial_state", feature_source)

        self.assertIn("read_settings", settings_source)
        self.assertNotIn("get_tg_proxy_host", settings_source)
        self.assertNotIn("get_tg_proxy_port", settings_source)
        self.assertNotIn("get_tg_proxy_upstream_enabled", settings_source)
        self.assertIn("load_page_initial_state=self.load_page_initial_state", feature_source)
        self.assertIn("_load_page_initial_state", worker_source)
        self.assertNotIn("telegram_proxy.commands", worker_source)
        self.assertNotIn("telegram_proxy.settings", worker_source)
        self.assertIn("load_page_initial_state", worker_source)

    def test_telegram_proxy_initial_state_plan_reads_settings_once(self) -> None:
        from telegram_proxy.upstream_catalog import UpstreamCatalog

        catalog = UpstreamCatalog(build_presets=[
            {
                "id": "build:test",
                "name": "Test",
                "type": "socks5",
                "source": "build",
                "host": "10.0.0.2",
                "port": 1081,
                "username": "u",
                "password": "p",
            }
        ])
        data = {
            "telegram_proxy": {
                "host": "0.0.0.0",
                "port": 1453,
                "upstream_enabled": True,
                "upstream_host": "10.0.0.2",
                "upstream_port": 1081,
                "upstream_user": "u",
                "upstream_pass": "p",
                "upstream_mode": "always",
            },
        }

        with (
            patch("telegram_proxy.upstream_catalog.UpstreamCatalog.load_from_runtime", return_value=catalog),
            patch("settings.store.read_settings", return_value=data) as read_settings,
        ):
            plan = telegram_proxy_settings.load_page_initial_state()

        self.assertEqual(read_settings.call_count, 1)
        self.assertIs(plan.upstream_catalog, catalog)
        self.assertEqual(plan.settings.host, "0.0.0.0")
        self.assertEqual(plan.settings.port, 1453)
        self.assertTrue(plan.settings.upstream_enabled)
        self.assertEqual(plan.settings.upstream_host, "10.0.0.2")
        self.assertEqual(plan.settings.upstream_port, 1081)
        self.assertEqual(plan.settings.upstream_user, "u")
        self.assertEqual(plan.settings.upstream_password, "p")
        self.assertEqual(plan.settings.upstream_mode, "always")
        self.assertEqual(plan.settings.upstream_preset_index, 1)

    def test_telegram_proxy_log_lines_write_through_worker(self) -> None:
        append_source = inspect.getsource(TelegramProxyPage._append_log_line)
        page_source = inspect.getsource(TelegramProxyPage)
        feature_source = inspect.getsource(TelegramProxyFeature)

        self.assertTrue(hasattr(telegram_proxy_commands, "append_log_line"))
        command_source = inspect.getsource(telegram_proxy_commands.append_log_line)
        self.assertTrue(hasattr(telegram_proxy_workers, "TelegramProxyLogLineWorker"))
        worker_source = inspect.getsource(telegram_proxy_workers.TelegramProxyLogLineWorker.run)

        self.assertIn("_request_log_line_append", append_source)
        self.assertNotIn("proxy_logger.log", append_source)
        self.assertIn("_log_line_worker", page_source)
        self.assertIn("create_log_line_worker", feature_source)
        self.assertIn("append_log_line", command_source)
        self.assertIn("append_log_line", worker_source)

    def test_telegram_proxy_auto_deeplink_check_runs_through_worker(self) -> None:
        try_source = inspect.getsource(TelegramProxyPage._try_auto_deeplink)
        page_source = inspect.getsource(TelegramProxyPage)
        feature_source = inspect.getsource(TelegramProxyFeature)

        self.assertTrue(hasattr(telegram_proxy_commands, "consume_auto_deeplink_request"))
        command_source = inspect.getsource(telegram_proxy_commands.consume_auto_deeplink_request)
        self.assertTrue(hasattr(telegram_proxy_workers, "TelegramProxyAutoDeeplinkWorker"))
        worker_source = inspect.getsource(telegram_proxy_workers.TelegramProxyAutoDeeplinkWorker.run)

        self.assertIn("_request_auto_deeplink_check", try_source)
        self.assertNotIn("telegram_proxy_settings.consume_auto_deeplink_request", try_source)
        self.assertIn("_auto_deeplink_worker", page_source)
        self.assertIn("create_auto_deeplink_worker", feature_source)
        self.assertIn("telegram_proxy.settings", command_source)
        self.assertIn("consume_auto_deeplink_request", worker_source)

    def test_dns_check_save_runs_through_worker(self) -> None:
        page_source = inspect.getsource(dns_check_page.DNSCheckPage)
        save_source = inspect.getsource(dns_check_page.DNSCheckPage.save_results)

        self.assertTrue(hasattr(dns_check_worker, "DNSCheckSaveWorker"))
        self.assertTrue(hasattr(dns_commands, "save_dns_check_results"))
        worker_source = inspect.getsource(dns_check_worker.DNSCheckSaveWorker.run)
        commands_source = inspect.getsource(dns_commands.save_dns_check_results)
        feature_source = inspect.getsource(__import__("app.feature_facades.dns", fromlist=["build_dns_feature"]).build_dns_feature)

        self.assertIn("create_dns_check_save_worker", page_source)
        self.assertIn("_start_save_results_worker", save_source)
        self.assertNotIn("save_results_text(", save_source)
        self.assertIn("save_dns_check_results=feature.save_dns_check_results", feature_source)
        self.assertIn("_save_dns_check_results", worker_source)
        self.assertNotIn("dns_commands", worker_source)
        self.assertNotIn("dns.dns_check_plans", worker_source)
        self.assertIn("save_results_text", commands_source)

    def test_dns_check_worker_runs_poisoning_check_through_commands(self) -> None:
        page_source = inspect.getsource(dns_check_page.DNSCheckPage)

        self.assertTrue(hasattr(dns_commands, "run_dns_poisoning_check"))
        worker_source = inspect.getsource(dns_check_worker.DNSCheckWorker.run)
        commands_source = inspect.getsource(dns_commands.run_dns_poisoning_check)
        feature_source = inspect.getsource(__import__("app.feature_facades.dns", fromlist=["build_dns_feature"]).build_dns_feature)

        self.assertIn("create_dns_check_worker", page_source)
        self.assertIn("run_dns_poisoning_check=feature.run_dns_poisoning_check", feature_source)
        self.assertIn("_run_dns_poisoning_check", worker_source)
        self.assertNotIn("dns_commands", worker_source)
        self.assertNotIn("dns_checker", worker_source)
        self.assertIn("DNSChecker", commands_source)

    def test_dns_quick_check_runs_through_worker(self) -> None:
        page_source = inspect.getsource(dns_check_page.DNSCheckPage)
        quick_source = inspect.getsource(dns_check_page.DNSCheckPage.quick_dns_check)
        feature_source = inspect.getsource(__import__("app.feature_facades.dns", fromlist=["build_dns_feature"]).build_dns_feature)
        plans_source = inspect.getsource(dns_check_page_plans)
        commands_source = inspect.getsource(__import__("dns.commands", fromlist=["run_quick_dns_check"]).run_quick_dns_check)

        self.assertTrue(hasattr(dns_check_worker, "DNSQuickCheckWorker"))
        worker_source = inspect.getsource(dns_check_worker.DNSQuickCheckWorker.run)

        self.assertIn("create_dns_quick_check_worker", page_source)
        self.assertIn("_start_quick_dns_check_worker", quick_source)
        self.assertNotIn("run_quick_dns_check(", quick_source)
        self.assertIn("create_dns_quick_check_worker", feature_source)
        self.assertIn("run_quick_dns_check=feature.run_quick_dns_check", feature_source)
        self.assertIn("_run_quick_dns_check", worker_source)
        self.assertNotIn("dns.commands", worker_source)
        self.assertNotIn("socket.", plans_source)
        self.assertIn("socket.gethostbyname", commands_source)

    def test_telegram_proxy_settings_save_runs_through_worker(self) -> None:
        page_source = inspect.getsource(TelegramProxyPage)
        upstream_source = inspect.getsource(telegram_upstream_workflow)
        runtime_source = inspect.getsource(telegram_runtime_workflow)
        request_source = inspect.getsource(TelegramProxyPage._request_settings_save)
        finished_source = inspect.getsource(TelegramProxyPage._on_settings_save_worker_finished)
        command_source = inspect.getsource(telegram_proxy_commands)

        self.assertTrue(hasattr(telegram_proxy_workers, "TelegramProxySettingsSaveWorker"))
        worker_source = inspect.getsource(telegram_proxy_workers.TelegramProxySettingsSaveWorker.run)

        for handler_name in (
            "_on_port_changed",
            "_on_host_changed",
            "_on_upstream_changed",
            "_on_upstream_preset_changed",
            "_on_upstream_host_changed",
            "_on_upstream_port_changed",
            "_on_upstream_user_changed",
            "_on_upstream_pass_changed",
            "_on_upstream_mode_changed",
        ):
            source = inspect.getsource(getattr(TelegramProxyPage, handler_name))
            self.assertIn("_request_settings_save", source)
            self.assertNotIn("telegram_proxy_settings.set_", source)
            self.assertNotIn("save_upstream_fields(", source)
            self.assertNotIn("save_upstream_mode(", source)

        self.assertIn("create_settings_save_worker", page_source)
        self.assertIn("_settings_save_pending.append", request_source)
        self.assertIn("_settings_save_pending.pop(0)", finished_source)
        self.assertNotIn("import telegram_proxy.settings", upstream_source)
        self.assertNotIn("telegram_proxy_settings.set_", upstream_source)
        self.assertNotIn("telegram_proxy_settings.set_proxy_enabled", runtime_source)
        self.assertIn("request_proxy_enabled_save", runtime_source)
        self.assertIn('"proxy_enabled"', page_source)
        feature_source = inspect.getsource(TelegramProxyFeature)
        self.assertIn("save_settings_action=self.save_settings_action", feature_source)
        self.assertIn("_save_settings_action", worker_source)
        self.assertNotIn("telegram_proxy.commands", worker_source)
        self.assertNotIn("telegram_proxy.settings", worker_source)
        self.assertIn("save_settings_action", worker_source)
        self.assertIn("set_host", command_source)
        self.assertIn("set_port", command_source)
        self.assertIn("set_proxy_enabled", command_source)
        self.assertIn("set_upstream_enabled", command_source)
        self.assertIn("set_upstream_fields", command_source)
        self.assertIn("set_upstream_mode", command_source)

    def test_telegram_proxy_relay_http_probe_is_command_not_ui_runtime(self) -> None:
        page_runtime_source = inspect.getsource(telegram_page.telegram_proxy_page_runtime)
        feature_source = inspect.getsource(TelegramProxyFeature)
        worker_source = inspect.getsource(telegram_proxy_workers.TelegramProxyRelayCheckWorker.run)

        self.assertTrue(hasattr(telegram_proxy_commands, "check_relay_http"))
        command_source = inspect.getsource(telegram_proxy_commands.check_relay_http)

        self.assertNotIn("socket.", page_runtime_source)
        self.assertIn("check_relay_reachable=self.check_relay_reachable", feature_source)
        self.assertIn("check_relay_http=self.check_relay_http", feature_source)
        self.assertIn("_check_relay_reachable", worker_source)
        self.assertIn("_check_relay_http", worker_source)
        self.assertNotIn("telegram_proxy.commands", worker_source)
        self.assertIn("check_relay_http", worker_source)
        self.assertIn("socket.create_connection", command_source)

    def test_telegram_proxy_open_log_file_runs_through_worker(self) -> None:
        page_source = inspect.getsource(TelegramProxyPage)
        handler_source = inspect.getsource(TelegramProxyPage._on_open_log_file)
        feature_source = inspect.getsource(TelegramProxyFeature)

        self.assertTrue(hasattr(telegram_proxy_workers, "TelegramProxyOpenLogFileWorker"))
        worker_source = inspect.getsource(telegram_proxy_workers.TelegramProxyOpenLogFileWorker.run)

        self.assertIn("_start_open_log_file_worker", handler_source)
        self.assertNotIn(".open_log_file(", handler_source)
        self.assertIn("create_open_log_file_worker", page_source)
        self.assertIn("_open_log_file_worker", page_source)
        self.assertIn("create_open_log_file_worker", feature_source)
        self.assertIn("open_log_file", worker_source)

    def test_telegram_proxy_external_links_run_through_worker(self) -> None:
        page_source = inspect.getsource(TelegramProxyPage)
        mtproxy_source = inspect.getsource(TelegramProxyPage._on_open_mtproxy)
        telegram_source = inspect.getsource(TelegramProxyPage._on_open_in_telegram)
        feature_source = inspect.getsource(TelegramProxyFeature)

        self.assertTrue(hasattr(telegram_proxy_workers, "TelegramProxyExternalLinkWorker"))
        worker_source = inspect.getsource(telegram_proxy_workers.TelegramProxyExternalLinkWorker.run)

        for source in (mtproxy_source, telegram_source):
            self.assertIn("_start_external_link_worker", source)
            self.assertNotIn(".open_external_link(", source)

        self.assertIn("create_external_link_worker", page_source)
        self.assertIn("_external_link_worker", page_source)
        self.assertIn("create_external_link_worker", feature_source)
        self.assertIn("open_external_link", worker_source)

    def test_telegram_proxy_stop_runs_through_worker(self) -> None:
        page_source = inspect.getsource(TelegramProxyPage)
        stop_source = inspect.getsource(TelegramProxyPage._stop_proxy)
        runtime_source = inspect.getsource(telegram_runtime_workflow.stop_proxy_runtime)

        self.assertTrue(hasattr(telegram_proxy_workers, "TelegramProxyStopRuntimeWorker"))
        worker_source = inspect.getsource(telegram_proxy_workers.TelegramProxyStopRuntimeWorker.run)

        self.assertIn("stop_proxy_runtime", stop_source)
        self.assertNotIn("manager.stop_proxy()", stop_source)
        self.assertNotIn("manager.stop_proxy()", runtime_source)
        self.assertIn("create_stop_runtime_worker", runtime_source)
        self.assertIn("_proxy_stop_worker", page_source)
        self.assertIn("_finish_stop_proxy", runtime_source)
        self.assertIn("QMetaObject.invokeMethod", runtime_source)
        self.assertIn('_request_settings_save("proxy_enabled", enabled=False)', page_source)
        self.assertIn("stop_proxy", worker_source)

    def test_blockcheck_initial_state_is_backend_plan_not_ui_loading(self) -> None:
        spec = importlib.util.find_spec("blockcheck.workers")
        self.assertIsNotNone(spec)
        blockcheck_workers = importlib.import_module("blockcheck.workers")

        init_source = inspect.getsource(BlockcheckPage.__init__)
        build_source = inspect.getsource(BlockcheckPage._build_ui)
        page_source = inspect.getsource(BlockcheckPage)
        helper_source = inspect.getsource(blockcheck_ui_helpers)
        runtime_source = inspect.getsource(blockcheck_page_runtime.load_page_initial_state)
        feature_source = inspect.getsource(BlockcheckFeature)
        worker_source = inspect.getsource(blockcheck_workers.BlockcheckInitialStateWorker.run)

        self.assertIn("_request_page_initial_state_load", init_source)
        self.assertNotIn("self._blockcheck.load_page_initial_state()", init_source)
        self.assertIn("_apply_initial_domain_chips", build_source)
        self.assertNotIn("self._load_domain_chips()", build_source)
        self.assertNotIn("load_domain_chips", helper_source)
        self.assertIn("read_settings", runtime_source)
        self.assertNotIn("get_blockcheck_settings", runtime_source)
        self.assertIn("create_initial_state_worker", page_source)
        self.assertIn("create_page_initial_state_worker", feature_source)
        self.assertIn("load_page_initial_state=self.load_page_initial_state", feature_source)
        self.assertIn("_load_page_initial_state", worker_source)
        self.assertNotIn("blockcheck.commands", worker_source)
        self.assertNotIn("blockcheck.page_runtime", worker_source)
        self.assertIn("load_page_initial_state", worker_source)

    def test_blockcheck_initial_state_plan_reads_settings_once(self) -> None:
        data = {
            "blockcheck": {
                "user_domains": [" Example.COM ", "", "discord.com"],
            },
        }

        with patch("settings.store.read_settings", return_value=data) as read_settings:
            plan = blockcheck_page_runtime.load_page_initial_state()

        self.assertEqual(read_settings.call_count, 1)
        self.assertEqual(plan.user_domains, ("example.com", "discord.com"))

    def test_blockcheck_run_log_writes_are_owned_by_worker(self) -> None:
        start_source = inspect.getsource(blockcheck_page_run_workflow.start_blockcheck_page_run)
        page_source = inspect.getsource(BlockcheckPage)
        worker_source = inspect.getsource(blockcheck_worker.BlockcheckWorker)

        self.assertNotIn("blockcheck_page_runtime.start_run_log", start_source)
        self.assertNotIn("blockcheck_page_runtime.append_run_log", page_source)
        self.assertNotIn("_append_run_log", page_source)
        self.assertNotIn("blockcheck.commands", worker_source)
        self.assertNotIn("blockcheck.page_runtime", worker_source)
        self.assertIn("run_log_started", worker_source)
        self.assertIn("_start_run_log", worker_source)
        self.assertIn("_append_run_log_action", worker_source)

    def test_strategy_scan_run_log_writes_are_owned_by_worker(self) -> None:
        strategy_scan_run_workflow = importlib.import_module("blockcheck.strategy_scan_run_workflow")
        strategy_scan_results_workflow = importlib.import_module("blockcheck.ui.strategy_scan_page_results_workflow")
        strategy_scan_worker = importlib.import_module("blockcheck.strategy_scan_worker")

        start_source = inspect.getsource(strategy_scan_run_workflow.start_strategy_scan_run)
        run_workflow_source = inspect.getsource(strategy_scan_run_workflow)
        results_workflow_source = inspect.getsource(strategy_scan_results_workflow)
        worker_source = inspect.getsource(strategy_scan_worker.StrategyScanWorker)

        self.assertNotIn(".start_run_log", start_source)
        self.assertNotIn(".append_run_log", run_workflow_source)
        self.assertNotIn("append_strategy_scan_log", results_workflow_source)
        self.assertNotIn("blockcheck.commands", worker_source)
        self.assertNotIn("blockcheck.strategy_scan_logs", worker_source)
        self.assertIn("run_log_started", worker_source)
        self.assertIn("_start_run_log_action", worker_source)
        self.assertIn("_append_run_log_action", worker_source)

    def test_blockcheck_support_bundle_prepares_through_worker(self) -> None:
        blockcheck_workers = importlib.import_module("blockcheck.workers")
        page_source = inspect.getsource(BlockcheckPage)
        handler_source = inspect.getsource(BlockcheckPage._prepare_support_from_blockcheck)
        worker_source = inspect.getsource(blockcheck_workers.BlockcheckSupportPrepareWorker.run)
        feature_source = inspect.getsource(BlockcheckFeature)

        self.assertIn("_request_support_prepare", handler_source)
        self.assertNotIn("blockcheck_page_runtime.prepare_support", handler_source)
        self.assertIn("create_support_prepare_worker", page_source)
        self.assertIn("_support_prepare_worker", page_source)
        self.assertIn("create_blockcheck_support_prepare_worker", feature_source)
        self.assertIn("prepare_support=self.prepare_support", feature_source)
        self.assertIn("_prepare_support", worker_source)
        self.assertNotIn("blockcheck.commands", worker_source)
        self.assertNotIn("blockcheck.page_runtime", worker_source)
        self.assertIn("prepare_support", worker_source)

    def test_blockcheck_user_domain_actions_run_through_commands(self) -> None:
        blockcheck_workers = importlib.import_module("blockcheck.workers")
        page_source = inspect.getsource(BlockcheckPage)
        feature_source = inspect.getsource(BlockcheckFeature)
        worker_source = inspect.getsource(blockcheck_workers.BlockcheckUserDomainActionWorker.run)

        self.assertIn("create_user_domain_action_worker", page_source)
        self.assertIn("create_user_domain_action_worker", feature_source)
        self.assertIn("run_user_domain_action=self.run_user_domain_action", feature_source)
        self.assertIn("_run_user_domain_action", worker_source)
        self.assertNotIn("blockcheck.commands", worker_source)
        self.assertNotIn("blockcheck.page_runtime", worker_source)
        self.assertIn("run_user_domain_action", worker_source)

    def test_strategy_scan_support_bundle_prepares_through_worker(self) -> None:
        blockcheck_workers = importlib.import_module("blockcheck.workers")
        page_source = inspect.getsource(StrategyScanPage)
        handler_source = inspect.getsource(StrategyScanPage._prepare_support_from_strategy_scan)
        worker_source = inspect.getsource(blockcheck_workers.StrategyScanSupportPrepareWorker.run)
        feature_source = inspect.getsource(BlockcheckFeature)

        self.assertIn("_request_support_prepare", handler_source)
        self.assertNotIn("prepare_strategy_scan_support", handler_source)
        self.assertIn("create_support_prepare_worker", page_source)
        self.assertIn("_support_prepare_worker", page_source)
        self.assertIn("create_strategy_scan_support_prepare_worker", feature_source)
        self.assertIn("prepare_strategy_scan_support=self.prepare_strategy_scan_support", feature_source)
        self.assertIn("_prepare_strategy_scan_support", worker_source)
        self.assertNotIn("blockcheck.commands", worker_source)
        self.assertNotIn("blockcheck.strategy_scan_logs", worker_source)
        self.assertIn("prepare_strategy_scan_support", worker_source)

    def test_strategy_scan_apply_runs_through_worker(self) -> None:
        spec = importlib.util.find_spec("blockcheck.strategy_apply_worker")
        self.assertIsNotNone(spec)
        strategy_apply_worker = importlib.import_module("blockcheck.strategy_apply_worker")

        apply_source = inspect.getsource(StrategyScanPage._on_apply_strategy)
        page_source = inspect.getsource(StrategyScanPage)
        finished_source = inspect.getsource(StrategyScanPage._on_strategy_apply_finished)
        feature_source = inspect.getsource(BlockcheckFeature)
        worker_source = inspect.getsource(strategy_apply_worker.StrategyApplyWorker.run)

        self.assertIn("_request_strategy_apply", apply_source)
        self.assertNotIn("self._blockcheck.apply_strategy(", apply_source)
        self.assertIn("create_strategy_apply_worker", page_source)
        self.assertIn("_strategy_apply_worker", page_source)
        self.assertIn("create_strategy_apply_worker", feature_source)
        self.assertIn("build_apply_success_plan", finished_source)
        self.assertIn("apply_strategy", worker_source)

    def test_strategy_scan_quick_targets_load_through_worker(self) -> None:
        import blockcheck.workers as blockcheck_workers

        page_source = inspect.getsource(StrategyScanPage)
        handler_source = inspect.getsource(StrategyScanPage._show_quick_domains_menu)
        feature_source = inspect.getsource(BlockcheckFeature)

        self.assertTrue(hasattr(blockcheck_workers, "StrategyScanQuickTargetsWorker"))
        worker_source = inspect.getsource(blockcheck_workers.StrategyScanQuickTargetsWorker.run)

        self.assertIn("create_quick_targets_worker", page_source)
        self.assertIn("create_strategy_scan_quick_targets_worker", feature_source)
        self.assertIn("build_quick_target_menu_plan=self.build_quick_target_menu_plan", feature_source)
        self.assertIn("_build_quick_target_menu_plan", worker_source)
        self.assertNotIn("blockcheck.commands", worker_source)
        self.assertNotIn("blockcheck.strategy_scan_page_plans", worker_source)
        self.assertIn("build_quick_target_menu_plan", worker_source)
        self.assertNotIn("build_quick_target_menu_plan", handler_source)

    def test_strategy_scan_resume_progress_saves_through_worker(self) -> None:
        import blockcheck.workers as blockcheck_workers

        page_source = inspect.getsource(StrategyScanPage)
        result_source = inspect.getsource(StrategyScanPage._on_strategy_result)
        feature_source = inspect.getsource(BlockcheckFeature)

        self.assertTrue(hasattr(blockcheck_workers, "StrategyScanResumeSaveWorker"))
        worker_source = inspect.getsource(blockcheck_workers.StrategyScanResumeSaveWorker.run)

        self.assertIn("_request_strategy_scan_resume_save", result_source)
        self.assertNotIn("record_strategy_scan_result(", result_source)
        self.assertIn("_strategy_scan_resume_save_worker", page_source)
        self.assertIn("create_strategy_scan_resume_save_worker", feature_source)
        self.assertIn("save_resume_state=self.save_resume_state", feature_source)
        self.assertIn("_save_resume_state", worker_source)
        self.assertNotIn("blockcheck_public", worker_source)
        self.assertIn("save_resume_state", worker_source)

    def test_strategy_scan_finish_plan_finalizes_through_worker(self) -> None:
        import blockcheck.workers as blockcheck_workers

        strategy_scan_results_workflow = importlib.import_module("blockcheck.ui.strategy_scan_page_results_workflow")
        page_source = inspect.getsource(StrategyScanPage)
        finished_source = inspect.getsource(StrategyScanPage._on_finished)
        apply_finished_source = inspect.getsource(strategy_scan_results_workflow.apply_finished_scan)
        feature_source = inspect.getsource(BlockcheckFeature)

        self.assertTrue(hasattr(blockcheck_workers, "StrategyScanFinalizeWorker"))
        worker_source = inspect.getsource(blockcheck_workers.StrategyScanFinalizeWorker.run)

        self.assertIn("_request_strategy_scan_finalize", finished_source)
        self.assertIn("create_strategy_scan_finalize_worker", page_source)
        self.assertIn("_strategy_scan_finalize_worker", page_source)
        self.assertIn("create_strategy_scan_finalize_worker", feature_source)
        self.assertNotIn("finalize_scan_report", apply_finished_source)
        self.assertIn("finalize_scan_report=self.finalize_scan_report", feature_source)
        self.assertIn("_finalize_scan_report", worker_source)
        self.assertNotIn("blockcheck_public", worker_source)
        self.assertIn("finalize_scan_report", worker_source)

    def test_logs_file_operations_log_internal_timing_stages(self) -> None:
        list_source = inspect.getsource(log_commands.list_logs)
        stats_source = inspect.getsource(log_commands.build_stats)

        self.assertIn("logs_feature.list_logs.total", list_source)
        self.assertIn("logs_feature.list_logs.glob", list_source)
        self.assertIn("logs_feature.list_logs.sort", list_source)
        self.assertIn("logs_feature.build_stats.total", stats_source)

    def test_logs_page_file_listing_and_stats_are_loaded_through_worker(self) -> None:
        refresh_source = inspect.getsource(LogsPage._refresh_logs_list)
        stats_source = inspect.getsource(LogsPage._update_stats)
        runtime_source = inspect.getsource(LogsPage._run_runtime_init_once)

        self.assertIn("_start_logs_overview_worker", refresh_source)
        self.assertIn("_start_logs_overview_worker", stats_source)
        self.assertNotIn(".list_logs(", refresh_source)
        self.assertNotIn(".build_stats(", stats_source)
        self.assertIn("refresh_logs_fn=self._refresh_logs_list", runtime_source)
        self.assertIn("update_stats_fn=self._update_stats", runtime_source)

    def test_logs_page_secondary_panels_are_built_after_initial_shell(self) -> None:
        build_source = inspect.getsource(LogsPage._build_logs_tab)
        activation_source = inspect.getsource(LogsPage.on_page_activated)
        runtime_schedule_source = inspect.getsource(LogsPage._schedule_runtime_init)
        runtime_flush_source = inspect.getsource(LogsPage._run_scheduled_runtime_init)
        scheduled_source = inspect.getsource(LogsPage._schedule_logs_secondary_panels)
        ensure_source = inspect.getsource(LogsPage._ensure_logs_secondary_panels)

        self.assertIn("build_logs_primary_tab_ui", build_source)
        self.assertNotIn("build_logs_secondary_panels_ui", build_source)
        self.assertIn("_schedule_logs_secondary_panels", activation_source)
        self.assertIn("_schedule_runtime_init", activation_source)
        self.assertNotIn("self._run_runtime_init_once()", activation_source)
        self.assertIn("QTimer.singleShot", runtime_schedule_source)
        self.assertIn("_run_runtime_init_once", runtime_flush_source)
        self.assertIn("QTimer.singleShot", scheduled_source)
        self.assertIn("build_logs_secondary_panels_ui", ensure_source)

    def test_blobs_page_actions_run_through_worker(self) -> None:
        spec = importlib.util.find_spec("blobs.workers")
        self.assertIsNotNone(spec)
        blobs_workers = importlib.import_module("blobs.workers")
        blobs_feature = importlib.import_module("app.feature_facades.blobs")

        load_source = inspect.getsource(BlobsPage._load_blobs)
        reload_source = inspect.getsource(BlobsPage._reload_blobs)
        add_source = inspect.getsource(BlobsPage._add_blob)
        delete_source = inspect.getsource(BlobsPage._delete_blob)
        open_bin_source = inspect.getsource(BlobsPage._open_bin_folder)
        open_json_source = inspect.getsource(BlobsPage._open_json)
        page_source = inspect.getsource(BlobsPage)
        load_worker_source = inspect.getsource(blobs_workers.BlobsLoadWorker.run)
        action_worker_source = inspect.getsource(blobs_workers.BlobActionWorker.run)
        feature_source = inspect.getsource(blobs_feature.BlobsFeature)

        self.assertIn("_request_blobs_load", load_source)
        self.assertIn("_request_blobs_load", reload_source)
        self.assertIn("_request_blob_action", add_source)
        self.assertIn("_request_blob_action", delete_source)
        self.assertIn("_request_blob_open_action", open_bin_source)
        self.assertIn("_request_blob_open_action", open_json_source)
        for source in (load_source, reload_source, add_source, delete_source):
            self.assertNotIn(".get_blobs_info(", source)
            self.assertNotIn(".reload_blobs(", source)
            self.assertNotIn(".save_user_blob(", source)
            self.assertNotIn(".delete_user_blob(", source)
        for source in (open_bin_source, open_json_source):
            self.assertNotIn(".open_bin_folder(", source)
            self.assertNotIn(".open_blobs_json(", source)

        self.assertIn("create_blobs_load_worker", page_source)
        self.assertIn("create_blob_action_worker", page_source)
        self.assertIn("create_blob_open_action_worker", page_source)
        self.assertIn("_blobs_load_pending", page_source)
        self.assertIn("_blob_open_action_runtime", page_source)
        self.assertIn("OneShotWorkerRuntime", page_source)
        self.assertIn("create_blobs_load_worker", feature_source)
        self.assertIn("create_blob_action_worker", feature_source)
        self.assertIn("create_blob_open_action_worker", feature_source)
        self.assertIn("get_blobs_info", load_worker_source)
        self.assertIn("reload_blobs", load_worker_source)
        self.assertIn("save_user_blob", action_worker_source)
        self.assertIn("delete_user_blob", action_worker_source)
        self.assertTrue(hasattr(blobs_workers, "BlobOpenActionWorker"))
        open_worker_source = inspect.getsource(blobs_workers.BlobOpenActionWorker.run)
        self.assertIn("open_bin_folder", open_worker_source)
        self.assertIn("open_blobs_json", open_worker_source)

    def test_common_one_shot_worker_runtime_is_used_by_shared_pages(self) -> None:
        self.assertIsNotNone(importlib.util.find_spec("ui.one_shot_worker_runtime"))
        runtime = importlib.import_module("ui.one_shot_worker_runtime")

        runtime_source = inspect.getsource(runtime)
        hosts_source = inspect.getsource(HostsPage)
        logs_source = inspect.getsource(LogsPage)
        locked_source = inspect.getsource(OrchestraLockedPage)
        blocked_source = inspect.getsource(OrchestraBlockedPage)
        ratings_source = inspect.getsource(OrchestraRatingsPage)
        updater_source = inspect.getsource(ServersPage)
        update_runtime_source = inspect.getsource(__import__("updater.update_page_runtime", fromlist=["UpdatePageRuntime"]).UpdatePageRuntime)

        self.assertIn("class OneShotWorkerRuntime", runtime_source)
        self.assertIn("start_qobject_worker", runtime_source)
        self.assertIn("start_qthread_worker", runtime_source)
        for source in (
            hosts_source,
            logs_source,
            locked_source,
            blocked_source,
            ratings_source,
            updater_source + update_runtime_source,
        ):
            self.assertIn("OneShotWorkerRuntime", source)

    def test_updater_auto_check_save_runs_through_worker(self) -> None:
        settings_workers = importlib.import_module("updater.settings_workers")
        update_runtime_cls = __import__("updater.update_page_runtime", fromlist=["UpdatePageRuntime"]).UpdatePageRuntime
        updater_feature_cls = __import__("app.feature_facades.updater", fromlist=["UpdaterFeature"]).UpdaterFeature

        handler_source = inspect.getsource(update_runtime_cls.set_auto_check_enabled)
        runtime_source = inspect.getsource(update_runtime_cls)
        feature_source = inspect.getsource(updater_feature_cls)

        self.assertTrue(hasattr(settings_workers, "UpdaterAutoCheckSaveWorker"))
        worker_source = inspect.getsource(settings_workers.UpdaterAutoCheckSaveWorker.run)

        self.assertIn("_request_auto_check_save", handler_source)
        self.assertNotIn("set_auto_update_enabled", handler_source)
        self.assertIn("_auto_check_save_pending", runtime_source)
        self.assertIn("create_auto_check_save_worker", feature_source)
        self.assertIn("set_auto_update_enabled=self.set_auto_update_enabled", feature_source)
        self.assertIn("_set_auto_update_enabled", worker_source)
        self.assertNotIn("updater_commands", worker_source)

    def test_updater_auto_check_initial_read_runs_through_worker(self) -> None:
        settings_workers = importlib.import_module("updater.settings_workers")
        update_runtime_cls = __import__("updater.update_page_runtime", fromlist=["UpdatePageRuntime"]).UpdatePageRuntime
        updater_feature_cls = __import__("app.feature_facades.updater", fromlist=["UpdaterFeature"]).UpdaterFeature

        init_source = inspect.getsource(update_runtime_cls.__init__)
        runtime_source = inspect.getsource(update_runtime_cls)
        page_source = inspect.getsource(ServersPage)
        feature_source = inspect.getsource(updater_feature_cls)

        self.assertTrue(hasattr(settings_workers, "UpdaterAutoCheckLoadWorker"))
        worker_source = inspect.getsource(settings_workers.UpdaterAutoCheckLoadWorker.run)

        self.assertNotIn("is_auto_update_enabled", init_source)
        self.assertIn("_request_auto_check_load", runtime_source)
        self.assertIn("_auto_check_load_runtime", runtime_source)
        self.assertIn("set_auto_check_toggle_checked", runtime_source)
        self.assertIn("start_auto_check_load", page_source)
        self.assertIn("create_auto_check_load_worker", feature_source)
        self.assertIn("is_auto_update_enabled=self.is_auto_update_enabled", feature_source)
        self.assertIn("_is_auto_update_enabled", worker_source)
        self.assertNotIn("updater_commands", worker_source)

    def test_updater_open_channel_runs_through_worker(self) -> None:
        settings_workers = importlib.import_module("updater.settings_workers")
        update_runtime_cls = __import__("updater.update_page_runtime", fromlist=["UpdatePageRuntime"]).UpdatePageRuntime
        updater_feature_cls = __import__("app.feature_facades.updater", fromlist=["UpdaterFeature"]).UpdaterFeature

        page_handler_source = inspect.getsource(ServersPage._open_telegram_channel)
        runtime_source = inspect.getsource(update_runtime_cls)
        feature_source = inspect.getsource(updater_feature_cls)

        self.assertTrue(hasattr(settings_workers, "UpdaterChannelOpenWorker"))
        worker_source = inspect.getsource(settings_workers.UpdaterChannelOpenWorker.run)

        self.assertIn("request_open_update_channel", page_handler_source)
        self.assertNotIn("self._update_runtime.open_update_channel", page_handler_source)
        self.assertIn("_update_channel_open_runtime", runtime_source)
        self.assertIn("create_update_channel_open_worker", feature_source)
        self.assertIn("open_update_channel=self.open_update_channel", feature_source)
        self.assertIn("_open_update_channel", worker_source)
        self.assertNotIn("updater_commands", worker_source)

    def test_updater_changelog_links_open_through_worker(self) -> None:
        external_workers = importlib.import_module("app.external_workers")
        page_source = inspect.getsource(ServersPage)
        build_source = inspect.getsource(ServersPage._build_ui)

        self.assertTrue(hasattr(external_workers, "ExternalOpenUrlWorker"))
        worker_source = inspect.getsource(external_workers.ExternalOpenUrlWorker.run)

        self.assertIn("open_url=self._request_changelog_link_open", build_source)
        self.assertNotIn("open_url=self._external_actions.open_url", build_source)
        self.assertIn("create_changelog_link_open_worker", page_source)
        self.assertIn("_request_changelog_link_open", page_source)
        self.assertIn("_changelog_link_open_runtime", page_source)
        self.assertIn("_stop_changelog_link_open_worker", page_source)
        self.assertIn("open_url", worker_source)

    def test_updater_install_worker_is_created_through_feature(self) -> None:
        update_runtime_cls = __import__("updater.update_page_runtime", fromlist=["UpdatePageRuntime"]).UpdatePageRuntime
        updater_feature_cls = __import__("app.feature_facades.updater", fromlist=["UpdaterFeature"]).UpdaterFeature

        runtime_factory_source = inspect.getsource(update_runtime_cls._create_update_worker_runtime)
        feature_source = inspect.getsource(updater_feature_cls)

        self.assertIn("create_update_install_worker", runtime_factory_source)
        self.assertNotIn("from updater.update import UpdateWorker", runtime_factory_source)
        self.assertIn("create_update_install_worker", feature_source)
        self.assertIn("UpdateWorker", feature_source)

    def test_updater_cache_invalidation_runs_through_worker(self) -> None:
        settings_workers = importlib.import_module("updater.settings_workers")
        update_runtime_cls = __import__("updater.update_page_runtime", fromlist=["UpdatePageRuntime"]).UpdatePageRuntime
        updater_feature_cls = __import__("app.feature_facades.updater", fromlist=["UpdaterFeature"]).UpdaterFeature

        manual_check_source = inspect.getsource(update_runtime_cls.request_manual_check)
        install_source = inspect.getsource(update_runtime_cls.install_update)
        runtime_source = inspect.getsource(update_runtime_cls)
        feature_source = inspect.getsource(updater_feature_cls)

        self.assertTrue(hasattr(settings_workers, "UpdaterCacheInvalidateWorker"))
        worker_source = inspect.getsource(settings_workers.UpdaterCacheInvalidateWorker.run)

        self.assertIn("_request_update_cache_invalidate", manual_check_source)
        self.assertIn("_request_update_cache_invalidate", install_source)
        self.assertNotIn("invalidate_cache", manual_check_source)
        self.assertNotIn("invalidate_cache", install_source)
        self.assertIn("_cache_invalidate_runtime", runtime_source)
        self.assertIn("create_cache_invalidate_worker", runtime_source)
        self.assertIn("create_cache_invalidate_worker", feature_source)
        self.assertIn("invalidate_update_cache=self.invalidate_update_cache", feature_source)
        self.assertIn("_invalidate_update_cache", worker_source)

    def test_updater_server_retry_without_dpi_runs_through_worker(self) -> None:
        retry_workers = importlib.import_module("updater.retry_workers")
        update_runtime_cls = __import__("updater.update_page_runtime", fromlist=["UpdatePageRuntime"]).UpdatePageRuntime
        updater_feature_cls = __import__("app.feature_facades.updater", fromlist=["UpdaterFeature"]).UpdaterFeature

        retry_source = inspect.getsource(update_runtime_cls._maybe_retry_server_check_without_dpi)
        runtime_source = inspect.getsource(update_runtime_cls)

        self.assertTrue(hasattr(retry_workers, "UpdaterServerRetryWithoutDpiWorker"))
        worker_source = inspect.getsource(retry_workers.UpdaterServerRetryWithoutDpiWorker.run)
        command_source = inspect.getsource(importlib.import_module("updater.commands").retry_server_check_without_dpi)
        feature_source = inspect.getsource(updater_feature_cls)

        self.assertIn("_request_server_retry_without_dpi", retry_source)
        self.assertNotIn("shutdown_sync", retry_source)
        self.assertNotIn("is_any_running", retry_source)
        self.assertIn("_server_retry_without_dpi_runtime", runtime_source)
        self.assertIn("create_server_retry_without_dpi_worker", runtime_source)
        self.assertIn("_teardown_server_retry_without_dpi_worker", runtime_source)
        self.assertIn("create_server_retry_without_dpi_worker", feature_source)
        self.assertIn("retry_server_check_without_dpi=self.retry_server_check_without_dpi", feature_source)
        self.assertIn("_retry_server_check_without_dpi", worker_source)
        self.assertNotIn("updater.commands", worker_source)
        self.assertIn("retry_server_check_without_dpi", worker_source)
        self.assertNotIn("self._is_any_running(", worker_source)
        self.assertNotIn("self._shutdown_sync(", worker_source)
        self.assertIn("is_any_running", command_source)
        self.assertIn("shutdown_sync", command_source)

    def test_updater_dpi_restart_runs_through_worker(self) -> None:
        retry_workers = importlib.import_module("updater.retry_workers")
        update_runtime_cls = __import__("updater.update_page_runtime", fromlist=["UpdatePageRuntime"]).UpdatePageRuntime

        restart_source = inspect.getsource(update_runtime_cls._restart_dpi_after_update)
        runtime_source = inspect.getsource(update_runtime_cls)

        self.assertTrue(hasattr(retry_workers, "UpdaterDpiRestartWorker"))
        worker_source = inspect.getsource(retry_workers.UpdaterDpiRestartWorker.run)
        command_source = inspect.getsource(importlib.import_module("updater.commands").restart_dpi_after_update)
        feature_source = inspect.getsource(__import__("app.feature_facades.updater", fromlist=["UpdaterFeature"]).UpdaterFeature)

        self.assertIn("_request_dpi_restart", restart_source)
        self.assertNotIn(".restart(", restart_source)
        self.assertNotIn(".is_available(", restart_source)
        self.assertIn("_dpi_restart_runtime", runtime_source)
        self.assertIn("create_dpi_restart_worker", runtime_source)
        self.assertIn("_teardown_dpi_restart_worker", runtime_source)
        self.assertIn("create_dpi_restart_worker", feature_source)
        self.assertIn("restart_dpi_after_update=self.restart_dpi_after_update", feature_source)
        self.assertIn("_restart_dpi_after_update", worker_source)
        self.assertNotIn("updater.commands", worker_source)
        self.assertIn("restart_dpi_after_update", worker_source)
        self.assertNotIn(".is_available(", worker_source)
        self.assertNotIn(".restart(", worker_source)
        self.assertIn("is_available", command_source)
        self.assertIn("restart", command_source)

    def test_logs_cleanup_stops_overview_worker(self) -> None:
        cleanup_source = inspect.getsource(LogsPage.cleanup)

        self.assertIn("_stop_logs_overview_worker(blocking=True)", cleanup_source)

    def test_logs_support_bundle_prepares_through_worker(self) -> None:
        support_worker = importlib.import_module("log.support_worker")
        page_source = inspect.getsource(LogsPage)
        handler_source = inspect.getsource(LogsPage._prepare_support_from_logs)
        feature_source = inspect.getsource(__import__("app.feature_facades.logs", fromlist=["LogsFeature"]).LogsFeature)

        self.assertTrue(hasattr(support_worker, "LogsSupportPrepareWorker"))
        worker_source = inspect.getsource(support_worker.LogsSupportPrepareWorker.run)

        self.assertIn("_request_support_prepare", handler_source)
        self.assertNotIn("prepare_support_bundle", handler_source)
        self.assertIn("create_support_prepare_worker", page_source)
        self.assertIn("_support_prepare_runtime", page_source)
        self.assertIn("create_support_prepare_worker", feature_source)
        self.assertIn("prepare_support_bundle=self.prepare_support_bundle", feature_source)
        self.assertIn("_prepare_support_bundle", worker_source)
        self.assertNotIn("log_commands", worker_source)
        self.assertIn("prepare_support_bundle", worker_source)

    def test_logs_open_folder_runs_through_worker(self) -> None:
        spec = importlib.util.find_spec("log.open_folder_worker")
        self.assertIsNotNone(spec)
        open_worker = importlib.import_module("log.open_folder_worker")
        page_source = inspect.getsource(LogsPage)
        handler_source = inspect.getsource(LogsPage._open_folder)
        feature_source = inspect.getsource(__import__("app.feature_facades.logs", fromlist=["LogsFeature"]).LogsFeature)

        self.assertTrue(hasattr(open_worker, "LogsOpenFolderWorker"))
        worker_source = inspect.getsource(open_worker.LogsOpenFolderWorker.run)

        self.assertIn("_request_open_logs_folder", handler_source)
        self.assertNotIn(".open_logs_folder(", handler_source)
        self.assertIn("create_open_folder_worker", page_source)
        self.assertIn("_open_folder_runtime", page_source)
        self.assertIn("create_open_folder_worker", feature_source)
        self.assertIn("open_logs_folder", worker_source)

    def test_profile_setup_page_loads_profile_payload_through_worker(self) -> None:
        source = inspect.getsource(ProfileSetupPageBase.reload_current_profile)

        self.assertNotIn("self._controller.load(", source)
        self.assertIn("_request_profile_setup_payload", source)

    def test_preset_selection_state_uses_profile_snapshot(self) -> None:
        source = inspect.getsource(preset_commands._profile_selection_details)

        self.assertNotIn(".list_profiles(", source)
        self.assertNotIn("get_profile_setup(", source)
        self.assertIn("get_profile_selection_details", source)

    def test_control_pages_use_cached_profile_count(self) -> None:
        zapret2_source = inspect.getsource(Zapret2ModeControlPage)
        zapret1_source = inspect.getsource(Zapret1ModeControlPage)
        worker_source = inspect.getsource(control_additional_settings_runtime.ControlTopSummaryWorker.run)
        factory_source = inspect.getsource(control_additional_settings_runtime.create_top_summary_worker)

        self.assertFalse(hasattr(Zapret2ModeControlPage, "_load_enabled_profile_count"))
        self.assertFalse(hasattr(Zapret1ModeControlPage, "_load_enabled_profile_count"))
        self.assertNotIn("count_enabled_profiles", zapret2_source)
        self.assertNotIn("count_enabled_profiles", zapret1_source)
        self.assertNotIn("get_enabled_profile_count_snapshot", worker_source)
        self.assertIn("get_enabled_profile_count_snapshot", factory_source)
        self.assertNotIn("presets_feature", factory_source)
        self.assertNotIn("profile_feature", factory_source)

    def test_control_page_docs_open_through_worker(self) -> None:
        spec = importlib.util.find_spec("app.external_workers")
        self.assertIsNotNone(spec)
        external_workers = importlib.import_module("app.external_workers")
        external_feature_cls = __import__("app.feature_facades.external", fromlist=["ExternalActionsFeature"]).ExternalActionsFeature
        shared_source = inspect.getsource(control_page_shared.ControlPageActionMixin)
        zapret1_open_source = inspect.getsource(Zapret1ModeControlPage._open_docs)
        zapret2_open_source = inspect.getsource(Zapret2ModeControlPage._open_docs)
        zapret1_cleanup_source = inspect.getsource(Zapret1ModeControlPage.cleanup)
        zapret2_cleanup_source = inspect.getsource(Zapret2ModeControlPage.cleanup)

        self.assertTrue(hasattr(external_workers, "ExternalOpenUrlWorker"))
        worker_source = inspect.getsource(external_workers.ExternalOpenUrlWorker.run)
        feature_source = inspect.getsource(external_feature_cls)

        for source in (zapret1_open_source, zapret2_open_source):
            self.assertIn("_request_external_open_url", source)
            self.assertNotIn(".open_url(", source)

        self.assertIn("create_open_url_worker", feature_source)
        self.assertIn("create_external_open_url_worker", shared_source)
        self.assertIn("_external_open_url_runtime", shared_source)
        self.assertIn("open_url=self.open_url", feature_source)
        self.assertIn("open_url", worker_source)
        self.assertNotIn("external_commands", worker_source)
        self.assertIn("_stop_external_open_url_worker", zapret1_cleanup_source)
        self.assertIn("_stop_external_open_url_worker", zapret2_cleanup_source)

    def test_zapret1_additional_settings_loads_through_worker(self) -> None:
        page_source = inspect.getsource(Zapret1ModeControlPage)
        refresh_source = inspect.getsource(Zapret1ModeControlPage._refresh_additional_settings)
        pending_source = inspect.getsource(Zapret1ModeControlPage._apply_pending_additional_settings_refresh)

        self.assertIn("_schedule_additional_settings_reload", refresh_source)
        self.assertIn("_schedule_additional_settings_reload", pending_source)
        self.assertIn("create_additional_settings_worker", page_source)
        self.assertNotIn("get_additional_settings_state", page_source)
        self.assertNotIn("_load_additional_settings_state", page_source)

    def test_additional_settings_worker_uses_requested_launch_method(self) -> None:
        worker_init_source = inspect.getsource(profile_additional_settings_loader.AdditionalSettingsLoadWorker.__init__)
        worker_run_source = inspect.getsource(profile_additional_settings_loader.AdditionalSettingsLoadWorker.run)

        self.assertIn("state_loader", worker_init_source)
        self.assertIn("self._state_loader", worker_init_source)
        self.assertNotIn("self._profile", worker_init_source)
        self.assertNotIn("launch_method", worker_init_source)
        self.assertNotIn("self._launch_method", worker_init_source)
        self.assertIn("self._state_loader()", worker_run_source)
        self.assertNotIn("get_additional_settings_state", worker_run_source)
        self.assertNotIn("ZAPRET2_MODE", worker_run_source)
        factory_source = inspect.getsource(control_additional_settings_runtime.create_additional_settings_worker)
        self.assertIn("create_load_worker", factory_source)
        self.assertNotIn("profile_feature", factory_source)

    def test_control_additional_settings_runtime_is_shared(self) -> None:
        shared_source = inspect.getsource(control_additional_settings_runtime)
        zapret1_source = inspect.getsource(zapret1_runtime_helpers)
        zapret2_source = inspect.getsource(zapret2_page_runtime)
        zapret2_page_source = inspect.getsource(Zapret2ModeControlPage._schedule_additional_settings_reload)

        self.assertIn("class ModeControlRefreshRuntime", shared_source)
        self.assertIn("class ControlAdditionalSettingsState", shared_source)
        self.assertIn("additional_settings_runtime", zapret1_source)
        self.assertIn("additional_settings_runtime", zapret2_source)
        self.assertNotIn("class ModeControlRefreshRuntime", zapret1_source)
        self.assertNotIn("class ModeControlRefreshRuntime", zapret2_source)
        self.assertNotIn("class ControlAdditionalSettingsState", zapret1_source)
        self.assertNotIn("class ControlAdditionalSettingsState", zapret2_source)
        self.assertNotIn("def create_additional_settings_worker", zapret2_source)
        self.assertIn("create_control_additional_settings_worker", zapret2_page_source)
        self.assertIn("launch_method=ZAPRET2_MODE", zapret2_page_source)

    def test_control_additional_settings_saves_through_worker(self) -> None:
        zapret1_discord_source = inspect.getsource(Zapret1ModeControlPage._on_discord_restart_changed)
        zapret1_wssize_source = inspect.getsource(Zapret1ModeControlPage._on_wssize_toggled)
        zapret1_debug_source = inspect.getsource(Zapret1ModeControlPage._on_debug_log_toggled)
        zapret2_discord_source = inspect.getsource(Zapret2ModeControlPage._on_discord_restart_changed)
        zapret2_wssize_source = inspect.getsource(Zapret2ModeControlPage._on_wssize_toggled)
        zapret2_debug_source = inspect.getsource(Zapret2ModeControlPage._on_debug_log_toggled)

        self.assertTrue(hasattr(control_additional_settings_runtime, "AdditionalSettingsSaveWorker"))
        worker_source = inspect.getsource(control_additional_settings_runtime.AdditionalSettingsSaveWorker.run)

        for source in (
            zapret1_wssize_source,
            zapret1_debug_source,
            zapret2_wssize_source,
            zapret2_debug_source,
        ):
            self.assertIn("_request_additional_settings_save", source)
            self.assertNotIn("save_wssize_enabled(", source)
            self.assertNotIn("save_debug_log_enabled(", source)
            self.assertNotIn("set_wssize_enabled(", source)
            self.assertNotIn("set_debug_log_enabled(", source)

        for source in (zapret1_discord_source, zapret2_discord_source):
            self.assertIn('_request_additional_settings_save("discord_restart"', source)
            self.assertNotIn("save_discord_restart_setting(", source)
            self.assertNotIn("set_discord_restart_setting(", source)
        self.assertIn("create_additional_settings_save_worker", inspect.getsource(control_additional_settings_runtime))
        worker_init_source = inspect.getsource(control_additional_settings_runtime.AdditionalSettingsSaveWorker.__init__)
        factory_source = inspect.getsource(control_additional_settings_runtime.create_additional_settings_save_worker)

        self.assertIn("save_setting", worker_init_source)
        self.assertIn("self._save_setting", worker_init_source)
        self.assertNotIn("_profile_feature", worker_init_source)
        self.assertNotIn("launch_method", worker_init_source)
        self.assertIn("self._save_setting(self._setting, self._enabled)", worker_source)
        self.assertNotIn("set_discord_restart_setting", worker_source)
        self.assertNotIn("set_wssize_enabled", worker_source)
        self.assertNotIn("set_debug_log_enabled", worker_source)
        self.assertIn("set_discord_restart_setting", factory_source)
        self.assertIn("set_wssize_enabled", factory_source)
        self.assertIn("set_debug_log_enabled", factory_source)
        self.assertNotIn("profile_feature", factory_source)

    def test_control_additional_settings_has_no_legacy_sync_save_helpers(self) -> None:
        for module in (zapret1_runtime_helpers, zapret2_page_runtime):
            self.assertFalse(hasattr(module, "save_wssize_enabled"))
            self.assertFalse(hasattr(module, "save_debug_log_enabled"))

    def test_control_program_settings_save_runs_through_worker(self) -> None:
        zapret1_auto_source = inspect.getsource(Zapret1ModeControlPage._on_auto_dpi_toggled)
        zapret1_tray_source = inspect.getsource(Zapret1ModeControlPage._on_hide_to_tray_toggled)
        zapret2_auto_source = inspect.getsource(Zapret2ModeControlPage._on_auto_dpi_toggled)
        zapret2_tray_source = inspect.getsource(Zapret2ModeControlPage._on_hide_to_tray_toggled)
        defender_source = inspect.getsource(windows_features_runtime.ControlPageWindowsFeatureMixin._continue_defender_toggle)
        max_source = inspect.getsource(windows_features_runtime.ControlPageWindowsFeatureMixin._on_max_blocker_toggled)

        self.assertTrue(hasattr(program_settings_workers, "ProgramSettingsSaveWorker"))
        worker_source = inspect.getsource(program_settings_workers.ProgramSettingsSaveWorker.run)
        feature_source = inspect.getsource(
            __import__("app.feature_facades.program_settings", fromlist=["ProgramSettingsFeature"])
            .ProgramSettingsFeature.create_program_settings_save_worker
        )
        shared_source = inspect.getsource(control_page_shared.ControlPageActionMixin)

        for source in (
            zapret1_auto_source,
            zapret1_tray_source,
            zapret2_auto_source,
            zapret2_tray_source,
        ):
            self.assertIn("_request_program_settings_save", source)
            self.assertNotIn("self._program_settings.set_auto_dpi_enabled", source)
            self.assertNotIn("self._program_settings.set_hide_to_tray_on_minimize_close", source)

        self.assertIn("create_program_settings_save_worker", shared_source)
        self.assertIn("program_settings_save_pending", shared_source)
        self.assertIn("save_action=self._program_settings_save_action(action)", feature_source)
        self.assertIn("_save_action", worker_source)
        self.assertNotIn("program_settings_commands", worker_source)
        self.assertIn('_request_program_settings_save("defender_disabled"', defender_source)
        self.assertIn('_request_program_settings_save("max_block"', max_source)
        self.assertNotIn("self._program_settings.set_defender_disabled", defender_source)
        self.assertNotIn("self._program_settings.set_max_block_enabled", max_source)
        self.assertNotIn("set_defender_disabled", worker_source)
        self.assertNotIn("set_max_block_enabled", worker_source)

    def test_defender_admin_check_runs_through_worker(self) -> None:
        defender_source = "\n".join(
            (
                inspect.getsource(windows_features_runtime.ControlPageWindowsFeatureMixin._on_defender_toggled),
                inspect.getsource(windows_features_runtime.ControlPageWindowsFeatureMixin._continue_defender_toggle),
            )
        )
        mixin_source = inspect.getsource(windows_features_runtime.ControlPageWindowsFeatureMixin)
        feature_source = inspect.getsource(__import__("app.feature_facades.program_settings", fromlist=["ProgramSettingsFeature"]).ProgramSettingsFeature)

        self.assertTrue(hasattr(program_settings_workers, "ProgramSettingsAdminCheckWorker"))
        worker_source = inspect.getsource(program_settings_workers.ProgramSettingsAdminCheckWorker.run)

        self.assertIn("_request_defender_admin_check", defender_source)
        self.assertNotIn("self._program_settings.is_user_admin", defender_source)
        self.assertIn("create_program_settings_admin_check_worker", mixin_source)
        self.assertIn("create_program_settings_admin_check_worker", feature_source)
        self.assertIn("is_user_admin", worker_source)

    def test_control_program_settings_load_runs_through_worker(self) -> None:
        zapret1_sync_source = inspect.getsource(Zapret1ModeControlPage._sync_program_settings)
        zapret2_sync_source = inspect.getsource(Zapret2ModeControlPage._sync_program_settings)
        shared_source = inspect.getsource(control_page_shared.ControlPageActionMixin)
        runtime_source = inspect.getsource(control_additional_settings_runtime.ModeControlRefreshRuntime)
        worker_source = inspect.getsource(program_settings_workers.ProgramSettingsLoadWorker.run)
        attach_source = inspect.getsource(program_settings_runtime.attach_program_settings_runtime)

        self.assertIn("_request_program_settings_load", zapret1_sync_source)
        self.assertIn("_request_program_settings_load", zapret2_sync_source)
        self.assertNotIn("refresh_program_settings_snapshot", zapret1_sync_source)
        self.assertNotIn("refresh_program_settings_snapshot", zapret2_sync_source)
        self.assertIn("create_program_settings_load_worker", shared_source)
        self.assertIn("program_settings_load_worker", runtime_source)
        self.assertIn("load_program_settings_snapshot", worker_source)
        self.assertIn("publish_program_settings_snapshot", shared_source)
        self.assertIn("emit_initial=False", attach_source)

    def test_zapret2_control_initial_store_snapshot_is_applied_immediately(self) -> None:
        helper_source = inspect.getsource(control_page_shared.bind_control_ui_state_store)
        bind_source = inspect.getsource(Zapret2ModeControlPage.bind_ui_state_store)

        self.assertIn("emit_initial: bool = True", helper_source)
        self.assertIn("emit_initial=bool(emit_initial)", helper_source)
        self.assertNotIn("defer_initial_state", bind_source)
        self.assertNotIn("emit_initial=not defer_initial_state", bind_source)
        self.assertNotIn("_wait_for_startup_interactive_before_initial_ui_state", bind_source)

    def test_raw_preset_editor_loads_file_through_worker(self) -> None:
        source = inspect.getsource(PresetRawEditorPage._load_file)
        set_source = inspect.getsource(PresetRawEditorPage.set_preset_file_name)
        header_source = inspect.getsource(PresetRawEditorPage._refresh_header)
        worker_init_source = inspect.getsource(RawPresetLoadWorker.__init__)
        worker_source = inspect.getsource(RawPresetLoadWorker.run)

        self.assertNotIn("self._controller.load_text(", source)
        self.assertIn("_request_raw_preset_text", source)
        self.assertNotIn("self._controller.manifest", set_source)
        self.assertNotIn("self._controller.source_path", set_source)
        self.assertNotIn("self._controller.manifest", header_source)
        self.assertIn("load_preset", worker_init_source)
        self.assertIn("self._load_preset", worker_init_source)
        self.assertNotIn("self._controller", worker_init_source)
        self.assertIn("self._load_preset(self._file_name)", worker_source)
        self.assertNotIn("self._controller.load_preset", worker_source)

    def test_raw_preset_editor_saves_file_through_worker(self) -> None:
        from app.feature_facades.presets import PresetsFeature

        save_source = inspect.getsource(PresetRawEditorPage._save_file)
        feature_source = inspect.getsource(PresetsFeature.create_raw_preset_save_worker)
        worker_init_source = inspect.getsource(RawPresetSaveWorker.__init__)
        worker_source = inspect.getsource(RawPresetSaveWorker.run)

        self.assertNotIn("self._controller.save_text(", save_source)
        self.assertIn("_request_raw_preset_save", save_source)
        self.assertIn("RawPresetSaveWorker", feature_source)
        self.assertIn("save_text", worker_init_source)
        self.assertIn("self._save_text", worker_init_source)
        self.assertNotIn("controller", worker_init_source)
        self.assertIn("self._save_text(", worker_source)
        self.assertNotIn("controller.save_text", worker_source)

    def test_raw_preset_editor_waits_for_pending_save_before_file_actions(self) -> None:
        set_file_source = inspect.getsource(PresetRawEditorPage.set_preset_file_name)
        activate_source = inspect.getsource(PresetRawEditorPage._activate_preset)
        open_source = inspect.getsource(PresetRawEditorPage._open_external)
        rename_source = inspect.getsource(PresetRawEditorPage._rename_preset)
        duplicate_source = inspect.getsource(PresetRawEditorPage._duplicate_preset)
        export_source = inspect.getsource(PresetRawEditorPage._export_preset)
        reset_source = inspect.getsource(PresetRawEditorPage._reset_preset)
        delete_source = inspect.getsource(PresetRawEditorPage._delete_preset)
        save_finished_source = inspect.getsource(PresetRawEditorPage._on_raw_preset_save_worker_finished)

        for source in (
            set_file_source,
            activate_source,
            open_source,
            rename_source,
            duplicate_source,
            export_source,
            reset_source,
            delete_source,
        ):
            self.assertIn("_run_after_raw_preset_save", source)
        self.assertIn("_after_raw_preset_save", save_finished_source)
        self.assertIn("_raw_save_succeeded", save_finished_source)

    def test_raw_preset_editor_activation_runs_through_worker(self) -> None:
        source = inspect.getsource(PresetRawEditorPage._activate_preset)
        request_source = inspect.getsource(PresetRawEditorPage._request_preset_activation)
        worker_init_source = inspect.getsource(RawPresetActivateWorker.__init__)
        worker_source = inspect.getsource(RawPresetActivateWorker.run)

        self.assertNotIn("_activate_selected_preset()", source)
        self.assertNotIn("self._controller.activate(", source)
        self.assertIn("_request_preset_activation", source)
        self.assertIn("create_raw_preset_activate_worker", request_source)
        self.assertIn("activate", worker_init_source)
        self.assertIn("self._activate", worker_init_source)
        self.assertNotIn("controller", worker_init_source)
        self.assertIn("self._activate(file_name=self._file_name)", worker_source)
        self.assertNotIn("controller.activate", worker_source)

    def test_raw_preset_editor_file_actions_run_through_worker(self) -> None:
        from app.feature_facades.presets import PresetsFeature

        action_sources = "\n".join(
            inspect.getsource(method)
            for method in (
                PresetRawEditorPage._open_external,
                PresetRawEditorPage._rename_preset,
                PresetRawEditorPage._duplicate_preset,
                PresetRawEditorPage._export_preset,
                PresetRawEditorPage._reset_preset,
                PresetRawEditorPage._delete_preset,
            )
        )
        feature_source = inspect.getsource(PresetsFeature.create_raw_preset_action_worker)
        worker_init_source = inspect.getsource(RawPresetActionWorker.__init__)
        worker_source = inspect.getsource(RawPresetActionWorker.run)

        for call in (
            "self._controller.open_source_file(",
            "self._controller.rename(",
            "self._controller.duplicate(",
            "self._controller.export(",
            "self._controller.reset_to_builtin(",
            "self._controller.delete(",
        ):
            self.assertNotIn(call, action_sources)
        self.assertIn("_request_raw_preset_action", action_sources)
        self.assertIn("RawPresetActionWorker", feature_source)
        self.assertIn("open_source_file", worker_init_source)
        self.assertIn("rename_preset", worker_init_source)
        self.assertIn("duplicate_preset", worker_init_source)
        self.assertIn("export_preset", worker_init_source)
        self.assertIn("reset_to_builtin", worker_init_source)
        self.assertIn("delete_preset", worker_init_source)
        self.assertIn("source_path", worker_init_source)
        self.assertNotIn("run_action", worker_init_source)
        self.assertNotIn("controller", worker_init_source)
        self.assertIn("self._rename_preset(", worker_source)
        self.assertIn("self._duplicate_preset(", worker_source)
        self.assertIn("self._export_preset(", worker_source)
        self.assertIn("self._reset_to_builtin(", worker_source)
        self.assertIn("self._delete_preset(", worker_source)
        self.assertIn("self._source_path(", worker_source)
        self.assertNotIn("self._run_action", worker_source)
        self.assertNotIn("controller.rename", worker_source)
        self.assertNotIn("controller.duplicate", worker_source)
        self.assertNotIn("controller.export", worker_source)
        self.assertNotIn("controller.reset_to_builtin", worker_source)
        self.assertNotIn("controller.delete", worker_source)

    def test_profile_setup_builds_hidden_tabs_lazily(self) -> None:
        build_source = inspect.getsource(ProfileSetupPageBase._build_content)
        switch_source = inspect.getsource(ProfileSetupPageBase._switch_strategy_tab)
        apply_source = inspect.getsource(ProfileSetupPageBase._apply_payload)

        self.assertNotIn("self._list_file_text = PlainTextEdit()", build_source)
        self.assertNotIn("self._raw_profile_text = PlainTextEdit()", build_source)
        self.assertIn("_ensure_editor_tab_built()", switch_source)
        self.assertIn("_request_list_file_editor_state()", switch_source)
        self.assertNotIn("_apply_list_file_editor_state", apply_source)

    def test_orchestra_settings_does_not_build_first_tab_in_constructor(self) -> None:
        init_source = inspect.getsource(OrchestraSettingsPage.__init__)
        show_source = inspect.getsource(OrchestraSettingsPage.showEvent)

        self.assertNotIn("self._switch_tab(0)", init_source)
        self.assertIn("self._switch_tab(0)", show_source)

    def test_orchestra_settings_language_uses_warmed_cache_not_settings_read(self) -> None:
        source = inspect.getsource(OrchestraSettingsPage._resolve_ui_language)

        self.assertIn("peek_warmed_ui_language", source)
        self.assertNotIn("load_ui_language", source)

    def test_orchestra_heavy_tabs_load_state_through_workers(self) -> None:
        locked_reload_source = inspect.getsource(OrchestraLockedPage._reload_from_settings)
        blocked_reload_source = inspect.getsource(OrchestraBlockedPage._reload_from_settings)
        ratings_refresh_source = inspect.getsource(OrchestraRatingsPage._refresh_data)
        managed_controller_source = inspect.getsource(orchestra_managed_lists_controller)
        ratings_controller_source = inspect.getsource(orchestra_ratings_controller)

        self.assertIn("_start_snapshot_worker", locked_reload_source)
        self.assertIn("_start_snapshot_worker", blocked_reload_source)
        self.assertIn("_start_ratings_state_worker", ratings_refresh_source)
        self.assertNotIn(".reload_snapshot(", locked_reload_source)
        self.assertNotIn(".reload_snapshot(", blocked_reload_source)
        self.assertNotIn(".load_state(", ratings_refresh_source)
        self.assertIn("create_snapshot_load_worker", managed_controller_source)
        self.assertIn("create_state_load_worker", ratings_controller_source)

    def test_control_top_summary_loads_preset_and_profile_count_through_worker(self) -> None:
        winws1_refresh_source = inspect.getsource(Zapret1ModeControlPage._refresh_top_summary)
        winws2_refresh_source = inspect.getsource(Zapret2ModeControlPage._refresh_top_summary)
        winws1_page_source = inspect.getsource(Zapret1ModeControlPage)
        winws2_page_source = inspect.getsource(Zapret2ModeControlPage)
        runtime_source = inspect.getsource(control_additional_settings_runtime)
        worker_init_source = inspect.getsource(control_additional_settings_runtime.ControlTopSummaryWorker.__init__)
        worker_source = inspect.getsource(control_additional_settings_runtime.ControlTopSummaryWorker.run)
        factory_source = inspect.getsource(control_additional_settings_runtime.create_top_summary_worker)

        self.assertIn("_request_top_summary_worker", winws1_refresh_source)
        self.assertIn("_request_top_summary_worker", winws2_refresh_source)
        self.assertNotIn("_load_preset_name()", winws1_refresh_source)
        self.assertNotIn("_load_selected_preset_name()", winws2_refresh_source)
        self.assertNotIn("_load_enabled_profile_count()", winws1_refresh_source)
        self.assertNotIn("_load_enabled_profile_count()", winws2_refresh_source)
        self.assertNotIn("get_selected_source_preset_display(", winws1_page_source)
        self.assertNotIn("get_selected_source_preset_display(", winws2_page_source)
        self.assertNotIn("get_enabled_profile_count_snapshot(", winws1_page_source)
        self.assertNotIn("get_enabled_profile_count_snapshot(", winws2_page_source)
        self.assertIn("create_top_summary_worker", runtime_source)
        self.assertIn("summary_loader", worker_init_source)
        self.assertIn("self._summary_loader", worker_init_source)
        self.assertNotIn("_presets_feature", worker_init_source)
        self.assertNotIn("_profile_feature", worker_init_source)
        self.assertNotIn("launch_method", worker_init_source)
        self.assertIn("self._summary_loader()", worker_source)
        self.assertNotIn("get_selected_source_preset_display", worker_source)
        self.assertNotIn("get_enabled_profile_count_snapshot", worker_source)
        self.assertIn("get_selected_source_preset_display", factory_source)
        self.assertIn("get_enabled_profile_count_snapshot", factory_source)
        self.assertNotIn("presets_feature", factory_source)
        self.assertNotIn("profile_feature", factory_source)

    def test_orchestra_clear_learned_runs_through_worker(self) -> None:
        spec = importlib.util.find_spec("orchestra.page_workers")
        self.assertIsNotNone(spec)
        orchestra_page_workers = importlib.import_module("orchestra.page_workers")

        clear_source = inspect.getsource(OrchestraPage._clear_learned)
        page_source = inspect.getsource(OrchestraPage)
        controller_source = inspect.getsource(orchestra_page_controller.OrchestraPageController)
        worker_source = inspect.getsource(orchestra_page_workers.OrchestraClearLearnedWorker.run)

        self.assertIn("_start_clear_learned_worker", clear_source)
        self.assertNotIn("self._controller.clear_learned_data()", clear_source)
        self.assertIn("OneShotWorkerRuntime", page_source)
        self.assertIn("create_clear_learned_worker", page_source)
        self.assertIn("create_clear_learned_worker", controller_source)
        self.assertIn("clear_learned_data", worker_source)

    def test_orchestra_log_history_loads_through_worker(self) -> None:
        spec = importlib.util.find_spec("orchestra.page_workers")
        self.assertIsNotNone(spec)
        orchestra_page_workers = importlib.import_module("orchestra.page_workers")
        orchestra_page_runtime_helpers = importlib.import_module("orchestra.ui.page_runtime_helpers")

        update_source = inspect.getsource(OrchestraPage._update_log_history)
        helper_source = inspect.getsource(orchestra_page_runtime_helpers.update_log_history_view)
        page_source = inspect.getsource(OrchestraPage)
        controller_source = inspect.getsource(orchestra_page_controller.OrchestraPageController)

        self.assertTrue(hasattr(orchestra_page_workers, "OrchestraLogHistoryLoadWorker"))
        worker_source = inspect.getsource(orchestra_page_workers.OrchestraLogHistoryLoadWorker.run)

        self.assertIn("_request_log_history_load", update_source)
        self.assertNotIn("runner.get_log_history", update_source)
        self.assertNotIn("runner.get_log_history", helper_source)
        self.assertIn("logs=", helper_source)
        self.assertIn("_log_history_runtime", page_source)
        self.assertIn("create_log_history_load_worker", page_source)
        self.assertIn("create_log_history_load_worker", controller_source)
        self.assertIn("load_log_history", worker_source)

    def test_orchestra_whitelist_actions_run_through_worker(self) -> None:
        whitelist_workers = importlib.import_module("orchestra.managed_lists_workers")

        add_source = inspect.getsource(OrchestraWhitelistPage._add_domain)
        remove_source = inspect.getsource(OrchestraWhitelistPage._on_row_delete_requested)
        clear_source = inspect.getsource(OrchestraWhitelistPage._clear_user_domains)
        page_source = inspect.getsource(OrchestraWhitelistPage)
        controller_source = inspect.getsource(orchestra_managed_lists_controller.WhitelistController)
        worker_source = inspect.getsource(whitelist_workers.OrchestraWhitelistActionWorker.run)

        for source in (add_source, remove_source, clear_source):
            self.assertIn("_request_whitelist_action", source)
            self.assertNotIn("self._controller.add_domain", source)
            self.assertNotIn("self._controller.remove_domain", source)
            self.assertNotIn("self._controller.clear_user_domains", source)

        self.assertIn("OneShotWorkerRuntime", page_source)
        self.assertIn("create_action_worker", page_source)
        self.assertIn("create_action_worker", controller_source)
        self.assertIn("add_domain", worker_source)
        self.assertIn("remove_domain", worker_source)
        self.assertIn("clear_user_domains", worker_source)

    def test_orchestra_whitelist_snapshot_loads_through_worker(self) -> None:
        whitelist_workers = importlib.import_module("orchestra.managed_lists_workers")
        sync_source = inspect.getsource(OrchestraWhitelistPage._sync_whitelist_view)
        controller_source = inspect.getsource(orchestra_managed_lists_controller.WhitelistController)

        self.assertTrue(hasattr(whitelist_workers, "OrchestraWhitelistSnapshotLoadWorker"))
        worker_source = inspect.getsource(whitelist_workers.OrchestraWhitelistSnapshotLoadWorker.run)
        self.assertIn("_start_snapshot_worker", sync_source)
        self.assertNotIn(".snapshot(", sync_source)
        self.assertIn("create_snapshot_load_worker", controller_source)
        self.assertIn("snapshot(refresh=self._refresh)", worker_source)

    def test_orchestra_managed_list_actions_run_through_worker(self) -> None:
        managed_workers = importlib.import_module("orchestra.managed_lists_workers")

        blocked_sources = (
            inspect.getsource(OrchestraBlockedPage._on_row_strategy_changed),
            inspect.getsource(OrchestraBlockedPage._on_row_delete_requested),
            inspect.getsource(OrchestraBlockedPage._block_strategy),
            inspect.getsource(OrchestraBlockedPage._unblock_all),
        )
        locked_sources = (
            inspect.getsource(OrchestraLockedPage._on_row_strategy_changed),
            inspect.getsource(OrchestraLockedPage._on_row_delete_requested),
            inspect.getsource(OrchestraLockedPage._lock_strategy),
            inspect.getsource(OrchestraLockedPage._unlock_all),
        )
        page_sources = "\n".join(
            (
                inspect.getsource(OrchestraBlockedPage),
                inspect.getsource(OrchestraLockedPage),
            )
        )
        controller_source = inspect.getsource(orchestra_managed_lists_controller)

        for source in blocked_sources + locked_sources:
            self.assertIn("_request_managed_action", source)
            self.assertNotIn("self._managed.change_strategy", source)
            self.assertNotIn("self._managed.remove_strategy", source)
            self.assertNotIn("self._managed.add_strategy", source)
            self.assertNotIn("self._managed.clear_user_strategies", source)
            self.assertNotIn("self._managed.clear_strategies", source)

        self.assertTrue(hasattr(managed_workers, "OrchestraManagedActionWorker"))
        worker_source = inspect.getsource(managed_workers.OrchestraManagedActionWorker.run)
        self.assertIn("OneShotWorkerRuntime", page_sources)
        self.assertIn("create_action_worker", page_sources)
        self.assertIn("create_action_worker", controller_source)
        self.assertIn("change_strategy", worker_source)
        self.assertIn("remove_strategy", worker_source)
        self.assertIn("add_strategy", worker_source)
        self.assertIn("clear_user_strategies", worker_source)
        self.assertIn("clear_strategies", worker_source)

    def test_orchestra_locked_blocked_strategy_validation_runs_through_worker(self) -> None:
        managed_workers = importlib.import_module("orchestra.managed_lists_workers")

        change_source = inspect.getsource(OrchestraLockedPage._on_row_strategy_changed)
        add_source = inspect.getsource(OrchestraLockedPage._lock_strategy)
        loaded_source = inspect.getsource(OrchestraLockedPage._on_managed_action_loaded)
        worker_source = inspect.getsource(managed_workers.OrchestraManagedActionWorker.run)

        for source in (change_source, add_source):
            self.assertIn("_request_managed_action", source)
            self.assertNotIn("self._managed.is_blocked_strategy", source)
            self.assertNotIn("self._managed.current_strategy", source)

        self.assertIn("blocked_by_policy", loaded_source)
        self.assertIn("current_strategy", loaded_source)
        self.assertIn("is_blocked_strategy", worker_source)
        self.assertIn("current_strategy", worker_source)

    def test_page_host_logs_first_and_repeat_show_for_all_pages(self) -> None:
        init_source = inspect.getsource(WindowPageHost.__init__)
        show_source = inspect.getsource(WindowPageHost.show_page)
        ensure_source = inspect.getsource(WindowPageHost.ensure_page)

        self.assertIn("_shown_pages", init_source)
        self.assertIn("show.first", show_source)
        self.assertIn("show.repeat", show_source)
        self.assertIn("log_page_metric", show_source)
        self.assertIn("show.ensure_page", show_source)
        self.assertIn("show.stack", show_source)
        self.assertIn("show.switch", show_source)
        self.assertIn("show.navigation", show_source)
        self.assertIn("animate=False", show_source)
        self.assertNotIn("animate=bool(first_show and use_nav_route)", show_source)
        self.assertIn("ensure.cached.language", ensure_source)
        self.assertIn("ensure.created.language", ensure_source)

    def test_page_host_repeat_show_budget_allows_animated_navigation(self) -> None:
        self.assertEqual(
            WindowPageHost._show_budget_ms(
                PageName.ZAPRET2_USER_PRESETS,
                first_show=False,
                use_nav_route=True,
            ),
            120,
        )
        self.assertEqual(
            WindowPageHost._show_budget_ms(
                PageName.ZAPRET2_USER_PRESETS,
                first_show=False,
                use_nav_route=False,
            ),
            40,
        )

    def test_page_host_disables_qfluent_animation_for_direct_switch(self) -> None:
        class _FakeStack:
            def __init__(self) -> None:
                self.isAnimationEnabled = True
                self.animation_seen_during_switch = None

            def setCurrentWidget(self, page, need_pop_out=False):
                _ = page
                _ = need_pop_out
                self.animation_seen_during_switch = self.isAnimationEnabled

        stack = _FakeStack()
        host = WindowPageHost(window=type("Window", (), {"stackedWidget": stack})(), page_factory=None)

        self.assertTrue(host.set_stacked_widget_current_page(object(), animate=False))
        self.assertFalse(stack.animation_seen_during_switch)
        self.assertTrue(stack.isAnimationEnabled)

    def test_telegram_proxy_builds_secondary_tabs_lazily(self) -> None:
        setup_source = inspect.getsource(TelegramProxyPage._setup_ui)
        after_source = inspect.getsource(TelegramProxyPage._after_ui_built)
        switch_source = inspect.getsource(TelegramProxyPage._switch_tab)
        timer_source = inspect.getsource(TelegramProxyPage._sync_log_timer)

        self.assertIn("_built_panel_indexes", setup_source)
        self.assertNotIn("build_telegram_proxy_logs_panel(", setup_source)
        self.assertNotIn("build_telegram_proxy_diag_panel(", setup_source)
        self.assertNotIn("_log_timer.start", after_source)
        self.assertIn("_ensure_panel_built(index)", switch_source)
        self.assertIn("self._stacked.currentIndex() == 1", timer_source)

    def test_user_presets_hide_keeps_clean_cache_clean(self) -> None:
        source = inspect.getsource(UserPresetsPageBase.on_page_hidden)

        self.assertNotIn("stop_watching_presets", source)

    def test_hosts_page_first_render_does_not_read_hosts_state_in_constructor(self) -> None:
        init_source = inspect.getsource(HostsPage.__init__)
        build_status_source = inspect.getsource(HostsPage._build_status_section)
        activated_source = inspect.getsource(HostsPage.on_page_activated)

        self.assertNotIn("_run_runtime_init_once()", init_source)
        self.assertNotIn("_get_active_domains()", build_status_source)
        self.assertIn("_run_runtime_init_once(show_access_errors=True)", activated_source)

    def test_hosts_warmup_defers_access_error_until_real_activation(self) -> None:
        page = HostsPage.__new__(HostsPage)
        page._runtime_initialized = True
        page._runtime_access_checked = False
        page._check_hosts_access = Mock()

        HostsPage._run_runtime_init_once(page, show_access_errors=False)

        page._check_hosts_access.assert_not_called()
        self.assertFalse(page._runtime_access_checked)

        HostsPage._run_runtime_init_once(page, show_access_errors=True)

        page._check_hosts_access.assert_called_once_with()
        self.assertTrue(page._runtime_access_checked)

    def test_hosts_services_catalog_is_prepared_through_worker_not_page_reading(self) -> None:
        rebuild_source = inspect.getsource(HostsPage._rebuild_services_selectors)
        build_source = inspect.getsource(HostsPage._build_services_selectors)

        self.assertIn("_start_services_catalog_worker", rebuild_source)
        self.assertNotIn("read_active_domains_map", build_source)
        self.assertNotIn("build_services_catalog_plan", build_source)

    def test_hosts_user_selection_loads_through_worker(self) -> None:
        spec = importlib.util.find_spec("hosts.selection_load_worker")
        self.assertIsNotNone(spec)
        selection_load_worker = importlib.import_module("hosts.selection_load_worker")

        init_source = inspect.getsource(HostsPage.__init__)
        runtime_source = inspect.getsource(HostsPage._run_runtime_init_once)
        worker_source = inspect.getsource(selection_load_worker.HostsSelectionLoadWorker.run)
        controller_source = inspect.getsource(__import__("hosts.page_controller", fromlist=["HostsPageController"]).HostsPageController)

        self.assertIn("_selection_load_runtime", init_source)
        self.assertIn("_start_user_selection_load_worker", runtime_source)
        self.assertNotIn("self._controller.load_user_selection()", runtime_source)
        self.assertIn("create_selection_load_worker", controller_source)
        self.assertIn("load_user_selection=self._hosts.load_user_selection", controller_source)
        self.assertIn("_load_user_selection", worker_source)
        self.assertNotIn("hosts.commands", worker_source)
        self.assertNotIn("self._controller", worker_source)
        self.assertIn("load_user_selection", inspect.getsource(hosts_commands.load_user_selection))

    def test_hosts_runtime_state_loads_through_worker(self) -> None:
        spec = importlib.util.find_spec("hosts.state_load_worker")
        self.assertIsNotNone(spec)
        state_load_worker = importlib.import_module("hosts.state_load_worker")

        init_source = inspect.getsource(HostsPage.__init__)
        update_source = inspect.getsource(HostsPage._update_ui)
        access_source = inspect.getsource(HostsPage._check_hosts_access)
        controller_source = inspect.getsource(__import__("hosts.page_controller", fromlist=["HostsPageController"]).HostsPageController)
        worker_source = inspect.getsource(state_load_worker.HostsStateLoadWorker.run)

        self.assertIn("_state_load_runtime", init_source)
        self.assertIn("_request_hosts_state_load", update_source)
        self.assertIn("_request_hosts_state_load", access_source)
        self.assertNotIn("_get_hosts_runtime_state()", update_source)
        self.assertNotIn("_get_hosts_runtime_state()", access_source)
        self.assertIn("create_state_load_worker", controller_source)
        self.assertIn("get_hosts_state=self._hosts.get_hosts_state", controller_source)
        self.assertIn("_get_hosts_state", worker_source)
        self.assertNotIn("hosts.commands", worker_source)
        self.assertNotIn("self._controller", worker_source)
        self.assertIn("get_hosts_state", inspect.getsource(hosts_commands.get_hosts_state))

    def test_hosts_open_file_runs_through_worker(self) -> None:
        spec = importlib.util.find_spec("hosts.open_file_worker")
        self.assertIsNotNone(spec)
        open_file_worker = importlib.import_module("hosts.open_file_worker")

        init_source = inspect.getsource(HostsPage.__init__)
        open_source = inspect.getsource(HostsPage._open_hosts_file)
        page_source = inspect.getsource(HostsPage)
        controller_source = inspect.getsource(__import__("hosts.page_controller", fromlist=["HostsPageController"]).HostsPageController)
        worker_source = inspect.getsource(open_file_worker.HostsOpenFileWorker.run)

        self.assertIn("_open_file_runtime", init_source)
        self.assertIn("_request_open_hosts_file", open_source)
        self.assertNotIn(".open_hosts_file(", open_source)
        self.assertIn("create_open_hosts_file_worker", page_source)
        self.assertIn("create_open_hosts_file_worker", controller_source)
        self.assertIn("open_hosts_file=self._hosts.open_hosts_file", controller_source)
        self.assertIn("_open_hosts_file", worker_source)
        self.assertNotIn("hosts.commands", worker_source)
        self.assertNotIn("self._controller", worker_source)
        self.assertIn("open_hosts_file", inspect.getsource(hosts_commands.open_hosts_file))

    def test_hosts_restore_permissions_runs_through_worker(self) -> None:
        spec = importlib.util.find_spec("hosts.permission_restore_worker")
        self.assertIsNotNone(spec)
        permission_restore_worker = importlib.import_module("hosts.permission_restore_worker")

        init_source = inspect.getsource(HostsPage.__init__)
        restore_source = inspect.getsource(HostsPage._restore_hosts_permissions)
        request_source = inspect.getsource(HostsPage._request_restore_hosts_permissions)
        controller_source = inspect.getsource(__import__("hosts.page_controller", fromlist=["HostsPageController"]).HostsPageController)
        worker_source = inspect.getsource(permission_restore_worker.HostsPermissionRestoreWorker.run)

        self.assertIn("_permission_restore_runtime", init_source)
        self.assertIn("_request_restore_hosts_permissions", restore_source)
        self.assertNotIn("restore_hosts_permissions_flow(", restore_source)
        self.assertIn("create_permission_restore_worker", request_source)
        self.assertIn("create_permission_restore_worker", controller_source)
        self.assertIn("restore_hosts_permissions=self._hosts.restore_hosts_permissions", controller_source)
        self.assertIn("_restore_hosts_permissions", worker_source)
        self.assertNotIn("hosts.commands", worker_source)
        self.assertNotIn("self._controller", worker_source)
        self.assertIn("restore_hosts_permissions", inspect.getsource(hosts_commands.restore_hosts_permissions))

    def test_hosts_page_cache_cannot_sync_read_runtime_state(self) -> None:
        page_source = inspect.getsource(HostsPage)
        cache_source = inspect.getsource(hosts_page_runtime.HostsPageRuntimeCache)

        self.assertFalse(hasattr(HostsPage, "_get_hosts_runtime_state"))
        self.assertFalse(hasattr(HostsPage, "_get_active_domains"))
        self.assertNotIn("self._controller.get_hosts_state", page_source)
        self.assertNotIn("get_runtime_state(", cache_source)
        self.assertNotIn("get_active_domains(", cache_source)

    def test_dns_isp_warning_settings_access_runs_through_worker(self) -> None:
        dns_workers = importlib.import_module("dns.page_workers")
        dns_feature_module = importlib.import_module("app.feature_facades.dns")

        page_source = inspect.getsource(dns_page.NetworkPage)
        check_source = inspect.getsource(dns_page.NetworkPage._check_and_show_isp_dns_warning)
        feature_source = inspect.getsource(dns_feature_module.DnsFeature)

        self.assertTrue(hasattr(dns_workers, "DnsIspWarningWorker"))
        worker_source = inspect.getsource(dns_workers.DnsIspWarningWorker.run)
        self.assertIn("_request_isp_dns_warning_plan", check_source)
        self.assertNotIn("self._dns.is_isp_dns_warning_shown", check_source)
        self.assertNotIn("self._dns.mark_isp_dns_warning_shown", check_source)
        self.assertIn("_isp_warning_runtime", page_source)
        self.assertIn("OneShotWorkerRuntime", page_source)
        self.assertIn("create_isp_dns_warning_worker", feature_source)
        self.assertIn("is_isp_dns_warning_shown", worker_source)
        self.assertIn("mark_isp_dns_warning_shown", worker_source)

    def test_lazy_pages_start_runtime_after_activation_not_constructor(self) -> None:
        page_classes = (
            dns_page.NetworkPage,
            BlobsPage,
            ServersPage,
            TelegramProxyPage,
            PremiumPage,
            DpiSettingsPage,
            OrchestraWhitelistPage,
            OrchestraLockedPage,
            OrchestraBlockedPage,
            OrchestraRatingsPage,
        )

        for page_cls in page_classes:
            with self.subTest(page=page_cls.__name__):
                init_source = inspect.getsource(page_cls.__init__)
                activated_source = inspect.getsource(page_cls.on_page_activated)

                self.assertNotIn("self._run_runtime_init_once()", init_source)
                self.assertIn("self._run_runtime_init_once()", activated_source)

    def test_dpi_settings_page_keeps_radio_icons_visible_immediately(self) -> None:
        page_build_source = inspect.getsource(DpiSettingsPage._build_ui)
        activation_source = inspect.getsource(DpiSettingsPage.on_page_activated)
        radio_source = inspect.getsource(Win11RadioOption.setSelected)
        radio_init_source = inspect.getsource(Win11RadioOption.__init__)

        self.assertNotIn("defer_icon=True", page_build_source)
        self.assertNotIn("_schedule_deferred_icons()", activation_source)
        self.assertNotIn("defer_icon", radio_init_source)
        self.assertIn("if self._selected == selected", radio_source)

    def test_dpi_settings_initial_load_reuses_initial_visibility(self) -> None:
        apply_source = inspect.getsource(DpiSettingsPage._apply_dpi_initial_state)
        sync_source = inspect.getsource(DpiSettingsPage._sync_visible_settings)

        self.assertIn("initial.visibility", apply_source)
        self.assertNotIn("describe_visibility(initial.launch_method)", apply_source)
        self.assertIn("visibility=None", sync_source)
        self.assertNotIn("load_orchestra_settings", sync_source)

    def test_dpi_settings_load_and_method_apply_run_through_worker(self) -> None:
        spec = importlib.util.find_spec("settings.dpi.workers")
        self.assertIsNotNone(spec)
        dpi_workers = importlib.import_module("settings.dpi.workers")

        load_source = inspect.getsource(DpiSettingsPage._load_settings)
        select_source = inspect.getsource(DpiSettingsPage._select_method)
        page_source = inspect.getsource(DpiSettingsPage)
        dpi_feature_module = __import__("app.feature_facades.dpi_settings", fromlist=["DpiSettingsFeature"])
        feature_source = inspect.getsource(dpi_feature_module.DpiSettingsFeature)
        feature_build_source = inspect.getsource(dpi_feature_module.build_dpi_settings_feature)
        feature_factory_source = inspect.getsource(dpi_feature_module._create_dpi_settings_worker)
        worker_init_source = inspect.getsource(dpi_workers.DpiSettingsWorker.__init__)
        worker_source = inspect.getsource(dpi_workers.DpiSettingsWorker.run)

        self.assertIn("_request_dpi_initial_state_load", load_source)
        self.assertNotIn("self._dpi_settings.load_initial_state", load_source)
        self.assertIn("_request_launch_method_apply", select_source)
        self.assertNotIn("self._dpi_settings.apply_launch_method", select_source)
        self.assertIn("create_dpi_settings_worker", page_source)
        self.assertIn("load_initial_state", worker_init_source)
        self.assertIn("apply_launch_method", worker_init_source)
        self.assertIn("load_orchestra_settings", worker_init_source)
        self.assertIn("create_dpi_settings_worker", feature_source)
        self.assertIn("load_initial_state=", feature_build_source)
        self.assertIn("apply_launch_method=", feature_build_source)
        self.assertIn("describe_visibility=", feature_build_source)
        self.assertIn("load_orchestra_settings=", feature_build_source)
        self.assertIn("load_initial_state=load_initial_state", feature_factory_source)
        self.assertIn("load_initial_state", worker_source)
        self.assertIn("apply_launch_method", worker_source)
        self.assertIn("load_orchestra_settings", worker_source)
        self.assertNotIn("settings.dpi.commands", worker_source)

    def test_dpi_orchestra_settings_save_runs_through_worker(self) -> None:
        spec = importlib.util.find_spec("orchestra.settings_worker")
        self.assertIsNotNone(spec)
        orchestra_settings_worker = importlib.import_module("orchestra.settings_worker")

        page_source = inspect.getsource(DpiSettingsPage)
        request_source = inspect.getsource(DpiSettingsPage._request_orchestra_setting_save)
        finished_source = inspect.getsource(DpiSettingsPage._on_orchestra_setting_save_worker_finished)
        worker_source = inspect.getsource(orchestra_settings_worker.OrchestraSettingSaveWorker.run)
        feature_source = inspect.getsource(__import__("app.feature_facades.orchestra", fromlist=["OrchestraFeature"]).OrchestraFeature)

        for method_name in (
            "_on_strict_detection_changed",
            "_on_debug_file_changed",
            "_on_auto_restart_discord_changed",
            "_on_discord_fails_changed",
            "_on_lock_successes_changed",
            "_on_unlock_fails_changed",
        ):
            source = inspect.getsource(getattr(DpiSettingsPage, method_name))
            self.assertIn("_request_orchestra_setting_save", source)
            self.assertNotIn("self._orchestra.set_setting", source)

        self.assertIn("create_orchestra_setting_save_worker", page_source)
        self.assertIn("_orchestra_settings_save_pending", request_source)
        self.assertIn("_orchestra_settings_save_pending.pop(0)", finished_source)
        self.assertIn("set_setting=self.set_setting", feature_source)
        self.assertIn("_set_setting", worker_source)
        self.assertNotIn("orchestra_commands", worker_source)
        self.assertIn("set_setting", worker_source)

    def test_autostart_page_actions_run_through_worker(self) -> None:
        spec = importlib.util.find_spec("autostart.workers")
        self.assertIsNotNone(spec)
        autostart_workers = importlib.import_module("autostart.workers")

        page_source = inspect.getsource(AutostartPage)
        enable_source = inspect.getsource(AutostartPage._on_gui_autostart)
        disable_source = inspect.getsource(AutostartPage._on_disable_clicked)
        push_source = inspect.getsource(AutostartPage._push_autostart_state)
        finished_source = inspect.getsource(AutostartPage._on_autostart_action_finished)
        worker_source = inspect.getsource(autostart_workers.AutostartActionWorker.run)

        for source in (enable_source, disable_source, push_source):
            self.assertIn("_request_autostart_action", source)
            self.assertNotIn("self._autostart.enable_gui_autostart", source)
            self.assertNotIn("self._autostart.disable_gui_autostart", source)
            self.assertNotIn("self._autostart.set_autostart_enabled", source)

        self.assertIn("create_autostart_action_worker", page_source)
        self.assertIn("_autostart_action_pending", page_source)
        self.assertIn("set_autostart_runtime_state", finished_source)
        self.assertIn("enable_gui_autostart", worker_source)
        self.assertIn("disable_gui_autostart", worker_source)
        self.assertIn("save_gui_autostart_enabled", worker_source)

    def test_autostart_mode_load_runs_through_worker(self) -> None:
        spec = importlib.util.find_spec("autostart.workers")
        self.assertIsNotNone(spec)
        autostart_workers = importlib.import_module("autostart.workers")

        init_source = inspect.getsource(AutostartPage.__init__)
        update_mode_source = inspect.getsource(AutostartPage._update_mode)
        page_source = inspect.getsource(AutostartPage)
        feature_source = inspect.getsource(__import__("app.feature_facades.autostart", fromlist=["AutostartFeature"]).AutostartFeature)

        self.assertTrue(hasattr(autostart_workers, "AutostartModeLoadWorker"))
        worker_source = inspect.getsource(autostart_workers.AutostartModeLoadWorker.run)

        self.assertIn("_mode_load_worker", init_source)
        self.assertIn("_request_mode_load", update_mode_source)
        self.assertNotIn("get_current_launch_method()", update_mode_source)
        self.assertIn("create_autostart_mode_load_worker", page_source)
        self.assertIn("create_autostart_mode_load_worker", feature_source)
        self.assertIn("get_current_launch_method", worker_source)

    def test_network_and_telegram_ui_do_not_create_python_threads(self) -> None:
        modules = (
            dns_diag_workflow,
            dns_load_workflow,
            telegram_diag_workflow,
            telegram_runtime_workflow,
            telegram_page,
        )

        for module in modules:
            source = inspect.getsource(module)
            self.assertNotIn("threading.Thread", source)

    def test_dns_page_worker_returns_state_instead_of_calling_page_method(self) -> None:
        feature_source = inspect.getsource(__import__("app.feature_facades.dns", fromlist=["build_dns_feature"]).build_dns_feature)
        loading_source = inspect.getsource(dns_page.NetworkPage._start_loading)
        page_source = inspect.getsource(dns_page.NetworkPage)
        worker_source = inspect.getsource(DnsPageLoadWorker)

        self.assertIn("create_page_load_worker", feature_source)
        self.assertIn("create_page_load_worker", loading_source)
        self.assertIn("start_qthread_worker", loading_source)
        self.assertIn("loaded = pyqtSignal", worker_source)
        self.assertIn("self.loaded.emit", worker_source)
        self.assertNotIn("self._load_data_fn()", worker_source)
        self.assertNotIn("load_data_fn=self._load_data", page_source)

    def test_network_force_dns_status_is_applied_from_page_load_worker(self) -> None:
        build_force_source = inspect.getsource(dns_page.NetworkPage._build_force_dns_card)
        loaded_source = inspect.getsource(dns_page.NetworkPage._on_page_state_loaded)
        apply_source = inspect.getsource(dns_page.NetworkPage._apply_loaded_force_dns_state)

        self.assertNotIn("get_force_dns_status_fn=dns_feature.get_force_dns_status", build_force_source)
        self.assertIn("get_force_dns_status_fn=lambda: self._force_dns_active", build_force_source)
        self.assertIn("_apply_loaded_force_dns_state()", loaded_source)
        self.assertIn("_set_force_dns_toggle", apply_source)
        self.assertIn("_update_force_dns_status", apply_source)
        self.assertIn("_update_dns_selection_state", apply_source)

    def test_dns_force_dns_actions_run_through_worker(self) -> None:
        page_workers = importlib.import_module("dns.page_workers")
        feature_source = inspect.getsource(__import__("app.feature_facades.dns", fromlist=["DnsFeature"]).DnsFeature)
        page_source = inspect.getsource(dns_page.NetworkPage)
        toggle_source = inspect.getsource(dns_page.NetworkPage._on_force_dns_toggled)
        reset_source = inspect.getsource(dns_page.NetworkPage._reset_dns_to_dhcp)
        toggle_result_source = inspect.getsource(dns_page.NetworkPage._apply_force_dns_toggle_worker_result)
        reset_result_source = inspect.getsource(dns_page.NetworkPage._apply_force_dns_reset_worker_result)

        self.assertTrue(hasattr(page_workers, "DnsForceDnsActionWorker"))
        worker_source = inspect.getsource(page_workers.DnsForceDnsActionWorker)

        for source in (toggle_source, reset_source):
            self.assertIn("_request_force_dns_action", source)
            self.assertNotIn("handle_force_dns_toggled_action", source)
            self.assertNotIn("reset_dns_to_dhcp_action", source)
            self.assertNotIn(".enable_force_dns(", source)
            self.assertNotIn(".disable_force_dns(", source)

        self.assertIn("create_force_dns_action_worker", feature_source)
        self.assertIn("create_force_dns_action_worker", page_source)
        self.assertIn("_force_dns_action_pending", page_source)
        self.assertIn("get_force_dns_status", worker_source)
        self.assertIn("enable_force_dns", worker_source)
        self.assertIn("disable_force_dns", worker_source)
        self.assertIn("refresh_dns_info", worker_source)
        self.assertNotIn("_refresh_adapters_dns", toggle_result_source)
        self.assertNotIn("_refresh_adapters_dns", reset_result_source)

    def test_dns_flush_cache_runs_through_worker(self) -> None:
        page_workers = importlib.import_module("dns.page_workers")
        feature_source = inspect.getsource(__import__("app.feature_facades.dns", fromlist=["DnsFeature"]).DnsFeature)
        page_source = inspect.getsource(dns_page.NetworkPage)
        flush_source = inspect.getsource(dns_page.NetworkPage._flush_dns_cache)

        self.assertTrue(hasattr(page_workers, "DnsFlushCacheWorker"))
        worker_source = inspect.getsource(page_workers.DnsFlushCacheWorker)

        self.assertIn("_request_dns_flush_cache", flush_source)
        self.assertNotIn("flush_dns_cache_action", flush_source)
        self.assertNotIn(".flush_dns_cache(", flush_source)
        self.assertIn("create_dns_flush_cache_worker", feature_source)
        self.assertIn("create_dns_flush_cache_worker", page_source)
        self.assertIn("_dns_flush_cache_pending", page_source)
        self.assertIn("_flush_dns_cache", worker_source)
        self.assertNotIn("dns_public.flush_dns_cache", worker_source)
        self.assertIn("build_flush_dns_cache_result_plan", worker_source)

    def test_dns_apply_actions_run_through_worker(self) -> None:
        page_workers = importlib.import_module("dns.page_workers")
        feature_source = inspect.getsource(__import__("app.feature_facades.dns", fromlist=["DnsFeature"]).DnsFeature)
        page_source = inspect.getsource(dns_page.NetworkPage)
        force_workflow = importlib.import_module("dns.page_force_dns_workflow")

        self.assertTrue(hasattr(page_workers, "DnsApplyWorker"))
        worker_source = inspect.getsource(page_workers.DnsApplyWorker)

        for method_name, old_action in (
            ("_apply_auto_dns_quick", "apply_auto_dns_quick"),
            ("_apply_provider_dns_quick", "apply_provider_dns_quick"),
            ("_apply_custom_dns_quick", "apply_custom_dns_quick"),
        ):
            source = inspect.getsource(getattr(dns_page.NetworkPage, method_name))
            body_source = source.split("\n", 1)[1]
            self.assertIn("_request_dns_apply", source)
            self.assertNotIn(f"{old_action}(", body_source)
            self.assertNotIn(".apply_auto_dns(", body_source)
            self.assertNotIn(".apply_provider_dns(", body_source)
            self.assertNotIn(".apply_custom_dns(", body_source)

        self.assertIn("create_dns_apply_worker", feature_source)
        self.assertIn("create_dns_apply_worker", page_source)
        self.assertIn("_dns_apply_pending", page_source)
        self.assertIn("apply_auto_dns", worker_source)
        self.assertIn("apply_provider_dns", worker_source)
        self.assertIn("apply_custom_dns", worker_source)
        self.assertIn("refresh_dns_info", worker_source)
        self.assertFalse(hasattr(dns_page.NetworkPage, "_refresh_adapters_dns"))
        self.assertIsNone(importlib.util.find_spec("dns.page_apply_workflow"))
        self.assertFalse(hasattr(force_workflow, "handle_force_dns_toggled_action"))
        self.assertFalse(hasattr(force_workflow, "flush_dns_cache_action"))
        self.assertFalse(hasattr(force_workflow, "reset_dns_to_dhcp_action"))

    def test_network_loaded_adapters_do_not_wait_for_current_dns(self) -> None:
        stored = {}
        build_calls = []

        dns_load_workflow.handle_loaded_adapters(
            adapters=[("Ethernet", "Intel")],
            current_dns_info={},
            ui_built=False,
            set_adapters_fn=lambda adapters: stored.setdefault("adapters", adapters),
            build_dynamic_ui_fn=lambda: build_calls.append("build"),
        )

        self.assertEqual(stored["adapters"], [("Ethernet", "Intel")])
        self.assertEqual(build_calls, ["build"])

    def test_network_page_builds_dns_choices_before_runtime_load(self) -> None:
        build_source = inspect.getsource(dns_page.NetworkPage._build_ui)
        choices_source = inspect.getsource(dns_page.NetworkPage._build_dns_choices_ui)

        self.assertIn("self._build_dns_choices_ui()", build_source)
        self.assertNotIn("load_page_data", choices_source)
        self.assertNotIn("refresh_dns_info", choices_source)

    def test_network_page_adds_dns_containers_before_showing_dns_choices(self) -> None:
        build_source = inspect.getsource(dns_page.NetworkPage._build_ui)

        choices_pos = build_source.index("self._build_dns_choices_ui()")
        dns_container_pos = build_source.index("self.add_widget(self.dns_cards_container)")
        custom_card_pos = build_source.index("self.add_widget(self.custom_card)")

        self.assertLess(dns_container_pos, choices_pos)
        self.assertLess(custom_card_pos, choices_pos)

    def test_telegram_diagnostics_worker_uses_progress_signal(self) -> None:
        workflow_source = inspect.getsource(telegram_diag_workflow.start_diagnostics)
        page_source = inspect.getsource(TelegramProxyPage)
        worker_source = inspect.getsource(TelegramProxyDiagnosticsWorker)

        self.assertNotIn("progress_callback=publish_diag_result", workflow_source)
        self.assertIn("worker.progress.connect(publish_diag_result)", workflow_source)
        self.assertIn("progress = pyqtSignal", worker_source)
        self.assertIn("progress_callback=self.progress.emit", worker_source)
        self.assertIn("_diag_runtime", page_source)
        self.assertIn("start_qthread_worker", workflow_source)
        self.assertNotIn("_diag_worker", page_source)
        self.assertNotIn("worker.start()", workflow_source)

    def test_telegram_ensure_hosts_runs_through_worker_runtime(self) -> None:
        page_source = inspect.getsource(TelegramProxyPage)
        ensure_source = inspect.getsource(TelegramProxyPage._ensure_telegram_hosts)
        cleanup_source = inspect.getsource(TelegramProxyPage.cleanup)
        feature_source = inspect.getsource(TelegramProxyFeature)
        worker_source = inspect.getsource(telegram_proxy_workers.TelegramHostsEnsureWorker)

        self.assertIn("_ensure_hosts_runtime", page_source)
        self.assertIn("start_qthread_worker", ensure_source)
        self.assertIn("bind_worker", ensure_source)
        self.assertIn("worker.completed.connect(self._on_telegram_hosts_ensured)", ensure_source)
        self.assertIn("create_ensure_hosts_worker", feature_source)
        self.assertIn("completed = pyqtSignal(int, object)", worker_source)
        self.assertIn("_ensure_hosts_runtime.stop", cleanup_source)
        self.assertNotIn("_ensure_hosts_worker =", page_source)
        self.assertNotIn("worker.start()", ensure_source)

    def test_connection_support_bundle_prepares_through_worker(self) -> None:
        support_worker = importlib.import_module("diagnostics.support_worker")
        page_source = inspect.getsource(ConnectionTestPage)
        handler_source = inspect.getsource(ConnectionTestPage.open_support_with_log)
        request_source = inspect.getsource(ConnectionTestPage._request_support_prepare)
        handler_body = handler_source.split("\n", 1)[1]
        worker_source = inspect.getsource(support_worker.ConnectionSupportPrepareWorker.run)
        feature_source = inspect.getsource(DiagnosticsFeature)
        feature_build_source = inspect.getsource(diagnostics_feature_facade.build_diagnostics_feature)

        self.assertIn("_request_support_prepare", handler_source)
        self.assertNotIn("open_support_with_log(", handler_body)
        self.assertIn("create_support_prepare_worker", page_source)
        self.assertIn("_support_prepare_runtime", page_source)
        self.assertIn("start_qthread_worker", request_source)
        self.assertNotIn("worker.start()", request_source)
        self.assertIn("create_connection_support_prepare_worker", feature_source)
        self.assertIn("prepare_connection_support=", feature_build_source)
        self.assertIn("_prepare_connection_support", worker_source)
        self.assertNotIn("diagnostics.commands", worker_source)
        self.assertIn("prepare_connection_support", worker_source)
        self.assertFalse(hasattr(diagnostics_runtime_helpers, "open_support_with_log"))

    def test_connection_test_run_uses_page_worker_runtime(self) -> None:
        page_source = inspect.getsource(ConnectionTestPage)
        start_source = inspect.getsource(ConnectionTestPage.start_test)
        stop_source = inspect.getsource(ConnectionTestPage.stop_test)
        cleanup_source = inspect.getsource(ConnectionTestPage.cleanup)
        runtime_source = inspect.getsource(diagnostics_runtime_helpers.start_connection_test)
        cleanup_runtime_source = inspect.getsource(diagnostics_runtime_helpers.cleanup_connection_runtime)

        self.assertIn("_connection_test_runtime", page_source)
        self.assertIn("OneShotWorkerRuntime", page_source)
        self.assertIn("start_qobject_worker", start_source)
        self.assertIn("stop_connection_test", stop_source)
        self.assertIn("runtime=self._connection_test_runtime", cleanup_source)
        self.assertIn("runtime.stop", cleanup_runtime_source)
        self.assertNotIn("self.worker_thread", page_source)
        self.assertNotIn("QThread", runtime_source)
        self.assertNotIn("worker_thread.start()", runtime_source)


if __name__ == "__main__":
    unittest.main()
