from __future__ import annotations

import inspect
import importlib
import importlib.util
import unittest
from unittest.mock import Mock, patch

from profile import commands as profile_commands
import profile.additional_settings_loader as profile_additional_settings_loader
import profile.profile_setup_loader as profile_setup_loader
from profile.profile_list_loader import ProfileListLoadWorker
from profile.service import ProfilePresetService
from profile.ui.profile_setup_page import ProfileSetupPageBase
from profile.ui.preset_setup_page import PresetSetupPageBase
from presets import display_state
from presets import commands as preset_commands
from presets.ui.common.preset_subpage_base import PresetRawEditorPage
from presets.ui.common.user_presets_page import UserPresetsPageBase
from presets.raw_preset_loader import RawPresetActionWorker, RawPresetActivateWorker, RawPresetSaveWorker
from presets.user_presets_action_workers import UserPresetActivateWorker, UserPresetItemActionWorker
from presets.user_presets_page_plans import build_preset_rows_plan
from ui.presets_menu.model import PresetListModel
import presets.user_presets_action_workers as user_presets_action_workers
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
from presets.user_presets_runtime_service import UserPresetsMetadataLoadWorker, UserPresetsRuntimeService
from hosts.ui.page import HostsPage
import hosts.ui.page_runtime as hosts_page_runtime
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
from ui.pages.appearance_page import AppearancePage
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
from app.feature_facades.diagnostics import DiagnosticsFeature
import ui.navigation.text_sync as navigation_text_sync
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

    def test_user_presets_full_metadata_loading_is_worker_only(self) -> None:
        load_source = inspect.getsource(UserPresetsRuntimeService.load_presets)
        watcher_source = inspect.getsource(UserPresetsRuntimeService.reload_presets_from_watcher)

        self.assertNotIn("adapter.load_all_metadata()", load_source)
        self.assertNotIn("adapter.load_all_metadata()", watcher_source)
        self.assertIn("UserPresetsMetadataLoadWorker", load_source)

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

    def test_user_presets_active_marker_does_not_force_synchronous_repaint(self) -> None:
        source = inspect.getsource(UserPresetsRuntimeService.apply_active_preset_marker_for_file)

        self.assertIn("viewport().update()", source)
        self.assertNotIn("viewport().repaint()", source)

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

    def test_user_presets_activation_runs_through_worker(self) -> None:
        handler_source = inspect.getsource(UserPresetsPageBase._on_activate_preset)
        request_source = inspect.getsource(UserPresetsPageBase._request_preset_activation)
        worker_source = inspect.getsource(UserPresetActivateWorker.run)

        self.assertNotIn("activate_preset_action", handler_source)
        self.assertNotIn(".activate_preset(", handler_source)
        self.assertIn("apply_active_preset_marker_for_file", handler_source)
        self.assertIn("_request_preset_activation", handler_source)
        self.assertIn("create_preset_activate_worker", request_source)
        self.assertIn("actions_api.activate_preset", worker_source)

    def test_user_presets_item_file_actions_run_through_worker(self) -> None:
        worker_source = inspect.getsource(UserPresetItemActionWorker.run)
        request_source = inspect.getsource(UserPresetsPageBase._request_preset_item_action)

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

        self.assertIn("create_preset_item_action_worker", request_source)
        self.assertIn("actions_api.duplicate_preset", worker_source)
        self.assertIn("actions_api.reset_preset_to_builtin", worker_source)
        self.assertIn("actions_api.delete_preset", worker_source)
        self.assertIn("actions_api.export_preset", worker_source)

    def test_user_presets_import_and_reset_all_run_through_worker(self) -> None:
        import_source = inspect.getsource(UserPresetsPageBase._on_import_clicked)
        reset_source = inspect.getsource(UserPresetsPageBase._on_reset_all_presets_clicked)

        self.assertTrue(hasattr(user_presets_action_workers, "UserPresetBulkActionWorker"))
        worker_source = inspect.getsource(user_presets_action_workers.UserPresetBulkActionWorker.run)
        request_source = inspect.getsource(UserPresetsPageBase._request_preset_bulk_action)

        for source in (import_source, reset_source):
            self.assertIn("_request_preset_bulk_action", source)
            self.assertNotIn("import_preset_action", source)
            self.assertNotIn("run_reset_all_presets_action", source)
            self.assertNotIn(".import_preset_from_file(", source)
            self.assertNotIn(".reset_all_presets(", source)

        self.assertIn("create_preset_bulk_action_worker", request_source)
        self.assertIn("actions_api.import_preset_from_file", worker_source)
        self.assertIn("actions_api.reset_all_presets", worker_source)

    def test_user_presets_create_and_rename_run_through_worker(self) -> None:
        create_source = inspect.getsource(UserPresetsPageBase._show_inline_action_create)
        rename_source = inspect.getsource(UserPresetsPageBase._show_inline_action_rename)

        self.assertTrue(hasattr(user_presets_action_workers, "UserPresetEditActionWorker"))
        worker_source = inspect.getsource(user_presets_action_workers.UserPresetEditActionWorker.run)
        request_source = inspect.getsource(UserPresetsPageBase._request_preset_edit_action)

        for source in (create_source, rename_source):
            body_source = "\n".join(source.splitlines()[1:])
            self.assertIn("_request_preset_edit_action", source)
            self.assertNotIn("show_inline_action_create(", body_source)
            self.assertNotIn("show_inline_action_rename(", body_source)
            self.assertNotIn(".create_preset(", source)
            self.assertNotIn(".rename_preset(", source)

        self.assertIn("create_preset_edit_action_worker", request_source)
        self.assertIn("actions_api.create_preset", worker_source)
        self.assertIn("actions_api.rename_preset", worker_source)

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
        self.assertIn("storage_api.toggle_preset_pin", worker_source)
        self.assertIn("storage_api.set_preset_rating", worker_source)
        self.assertIn("storage_api.move_preset_by_step", worker_source)
        self.assertIn("storage_api.move_preset_on_drop", worker_source)
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
        self.assertIn("create_preset_folder", worker_source)
        self.assertIn("rename_preset_folder", worker_source)
        self.assertIn("delete_preset_folder", worker_source)
        self.assertIn("move_preset_folder_by_step", worker_source)
        self.assertIn("set_preset_folder_collapsed", worker_source)
        self.assertIn("reset_preset_folders", worker_source)
        self.assertIn("load_preset_folder_state", worker_source)
        self.assertIn('context["folder_state"]', worker_source)
        self.assertIn("_preset_folder_action_pending.append", request_source)
        self.assertIn("_preset_folder_action_pending.pop(0)", finished_source)
        self.assertIn("update_cached_folder_state", action_finished_source)
        self.assertIn("show_menu", action_finished_source)
        self.assertIn("create_preset_folder_action_worker", request_source)

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
        self.assertIn("create_profile_folder", worker_source)
        self.assertIn("rename_profile_folder", worker_source)
        self.assertIn("delete_profile_folder", worker_source)
        self.assertIn("move_profile_folder_by_step", worker_source)
        self.assertIn("set_profile_folder_collapsed", worker_source)
        self.assertIn("reset_profile_folders", worker_source)
        self.assertIn("load_profile_folder_state", worker_source)
        self.assertIn("_profile_folder_action_pending.append", request_source)
        self.assertIn("_profile_folder_action_pending.pop(0)", finished_source)
        self.assertIn("show_menu", action_finished_source)
        self.assertIn("_create_profile_folder_action_worker", request_source)
        self.assertIn("ProfileFolderActionWorker", inspect.getsource(PresetSetupPageBase._create_profile_folder_action_worker))

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

    def test_preset_setup_page_uses_cached_profile_payload_before_worker(self) -> None:
        source = inspect.getsource(PresetSetupPageBase._request_profiles_payload)

        self.assertIn("get_cached_profile_list", source)
        self.assertIn("_apply_cached_profile_payload", source)
        self.assertLess(source.index("get_cached_profile_list"), source.index("worker.isRunning()"))
        self.assertLess(source.index("get_cached_profile_list"), source.index("create_profile_list_load_worker"))
        self.assertNotIn("_show_loading_skeleton", source)

    def test_profile_service_has_selected_preset_snapshot(self) -> None:
        source = inspect.getsource(ProfilePresetService.load_selected_preset)
        helper_source = inspect.getsource(ProfilePresetService._load_selected_preset_for_revision)

        self.assertIn("_selected_preset_revision", source)
        self.assertIn("_selected_preset_snapshot", helper_source)

    def test_profile_list_worker_logs_full_profile_payload_duration(self) -> None:
        source = inspect.getsource(ProfileListLoadWorker.run)

        self.assertIn("time.perf_counter", source)
        self.assertIn("profile_feature.worker.list_profiles.total", source)

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
        worker_source = inspect.getsource(appearance_workers.AppearanceInitialStateLoadWorker.run)
        page_source = inspect.getsource(AppearancePage)
        build_source = inspect.getsource(AppearancePage._build_ui)

        self.assertIn("load_page_initial_state", worker_source)
        self.assertIn("create_initial_state_load_worker", page_source)
        self.assertIn("_initial_state_load_worker", page_source)
        self.assertIn("_request_initial_state_load", build_source)

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
        page_source = inspect.getsource(AppearancePage)

        self.assertTrue(hasattr(appearance_workers, "AppearanceSettingsSaveWorker"))
        worker_source = inspect.getsource(appearance_workers.AppearanceSettingsSaveWorker.run)
        request_source = inspect.getsource(AppearancePage._request_appearance_save)
        finished_source = inspect.getsource(AppearancePage._on_appearance_save_worker_finished)

        for method_name in (
            "_on_display_mode_changed",
            "_on_ui_language_changed",
            "_on_rkn_background_changed",
            "_on_bg_preset_toggled",
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
        self.assertIn("_coalesce_appearance_save_pending", request_source)
        self.assertIn("_appearance_save_pending.append", page_source)
        self.assertIn("_appearance_save_pending.pop(0)", finished_source)
        self.assertIn("save_display_mode", worker_source)
        self.assertIn("save_ui_language", worker_source)
        self.assertIn("save_background_preset", worker_source)
        self.assertIn("save_window_opacity", worker_source)
        self.assertIn("save_accent_color", worker_source)
        self.assertIn("save_animations_enabled", worker_source)

    def test_appearance_rkn_background_options_load_through_worker(self) -> None:
        page_source = inspect.getsource(AppearancePage)
        reload_source = inspect.getsource(AppearancePage._reload_rkn_background_options)

        self.assertTrue(hasattr(appearance_workers, "AppearanceRknBackgroundOptionsLoadWorker"))
        worker_source = inspect.getsource(appearance_workers.AppearanceRknBackgroundOptionsLoadWorker.run)

        self.assertIn("_rkn_background_options_worker", page_source)
        self.assertIn("create_rkn_background_options_load_worker", page_source)
        self.assertIn("_request_rkn_background_options_load", reload_source)
        self.assertNotIn("appearance_settings.load_rkn_background()", reload_source)
        self.assertNotIn("get_rkn_background_options()", reload_source)
        self.assertIn("load_rkn_background", worker_source)
        self.assertIn("get_rkn_background_options", worker_source)

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
        device_info_source = inspect.getsource(PremiumPage._update_device_info)

        self.assertNotIn("def _has_pending_pair_code", page_source)
        self.assertNotIn("has_pending_pair_code(", page_source)
        self.assertIn("pairing_snapshot=self._pairing_autopoll_snapshot", sync_source)
        self.assertIn("_set_pairing_autopoll_snapshot_from_device_info", device_info_source)

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
        page_source = inspect.getsource(TelegramProxyPage)
        settings_build_source = inspect.getsource(telegram_proxy_settings_build.build_telegram_proxy_settings_panel)
        settings_source = inspect.getsource(telegram_proxy_settings.load_page_initial_state)
        feature_source = inspect.getsource(TelegramProxyFeature)
        worker_source = inspect.getsource(telegram_proxy_workers.TelegramProxyInitialStateWorker.run)

        self.assertIn("_request_initial_state_load", init_source)
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

    def test_dns_check_save_runs_through_worker(self) -> None:
        page_source = inspect.getsource(dns_check_page.DNSCheckPage)
        save_source = inspect.getsource(dns_check_page.DNSCheckPage.save_results)

        self.assertTrue(hasattr(dns_check_worker, "DNSCheckSaveWorker"))
        worker_source = inspect.getsource(dns_check_worker.DNSCheckSaveWorker.run)

        self.assertIn("create_dns_check_save_worker", page_source)
        self.assertIn("_start_save_results_worker", save_source)
        self.assertNotIn("save_results_text(", save_source)
        self.assertIn("save_results_text", worker_source)

    def test_dns_quick_check_runs_through_worker(self) -> None:
        page_source = inspect.getsource(dns_check_page.DNSCheckPage)
        quick_source = inspect.getsource(dns_check_page.DNSCheckPage.quick_dns_check)
        feature_source = inspect.getsource(__import__("app.feature_facades.dns", fromlist=["DnsFeature"]).DnsFeature)
        plans_source = inspect.getsource(dns_check_page_plans)
        commands_source = inspect.getsource(__import__("dns.commands", fromlist=["run_quick_dns_check"]).run_quick_dns_check)

        self.assertTrue(hasattr(dns_check_worker, "DNSQuickCheckWorker"))
        worker_source = inspect.getsource(dns_check_worker.DNSQuickCheckWorker.run)

        self.assertIn("create_dns_quick_check_worker", page_source)
        self.assertIn("_start_quick_dns_check_worker", quick_source)
        self.assertNotIn("run_quick_dns_check(", quick_source)
        self.assertIn("create_dns_quick_check_worker", feature_source)
        self.assertIn("run_quick_dns_check", worker_source)
        self.assertNotIn("socket.", plans_source)
        self.assertIn("socket.gethostbyname", commands_source)

    def test_telegram_proxy_settings_save_runs_through_worker(self) -> None:
        page_source = inspect.getsource(TelegramProxyPage)
        upstream_source = inspect.getsource(telegram_upstream_workflow)
        runtime_source = inspect.getsource(telegram_runtime_workflow)
        request_source = inspect.getsource(TelegramProxyPage._request_settings_save)
        finished_source = inspect.getsource(TelegramProxyPage._on_settings_save_worker_finished)

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
        self.assertIn("set_host", worker_source)
        self.assertIn("set_port", worker_source)
        self.assertIn("set_proxy_enabled", worker_source)
        self.assertIn("set_upstream_enabled", worker_source)
        self.assertIn("set_upstream_fields", worker_source)
        self.assertIn("set_upstream_mode", worker_source)

    def test_telegram_proxy_relay_http_probe_is_command_not_ui_runtime(self) -> None:
        page_runtime_source = inspect.getsource(telegram_page.telegram_proxy_page_runtime)
        worker_source = inspect.getsource(telegram_proxy_workers.TelegramProxyRelayCheckWorker.run)

        self.assertTrue(hasattr(telegram_proxy_commands, "check_relay_http"))
        command_source = inspect.getsource(telegram_proxy_commands.check_relay_http)

        self.assertNotIn("socket.", page_runtime_source)
        self.assertIn("telegram_proxy.commands", worker_source)
        self.assertIn("check_relay_http", worker_source)
        self.assertIn("socket.create_connection", command_source)

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
        self.assertNotIn("def load_page_initial_state", feature_source)
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
        self.assertIn("run_log_started", worker_source)
        self.assertIn("start_run_log", worker_source)
        self.assertIn("append_run_log", worker_source)

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
        self.assertIn("blockcheck.page_runtime", worker_source)
        self.assertIn("prepare_support", worker_source)

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
        self.assertIn("blockcheck.strategy_scan_logs", worker_source)
        self.assertIn("prepare_support", worker_source)

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
        page_source = inspect.getsource(BlobsPage)
        load_worker_source = inspect.getsource(blobs_workers.BlobsLoadWorker.run)
        action_worker_source = inspect.getsource(blobs_workers.BlobActionWorker.run)
        feature_source = inspect.getsource(blobs_feature.BlobsFeature)

        self.assertIn("_request_blobs_load", load_source)
        self.assertIn("_request_blobs_load", reload_source)
        self.assertIn("_request_blob_action", add_source)
        self.assertIn("_request_blob_action", delete_source)
        for source in (load_source, reload_source, add_source, delete_source):
            self.assertNotIn(".get_blobs_info(", source)
            self.assertNotIn(".reload_blobs(", source)
            self.assertNotIn(".save_user_blob(", source)
            self.assertNotIn(".delete_user_blob(", source)

        self.assertIn("create_blobs_load_worker", page_source)
        self.assertIn("create_blob_action_worker", page_source)
        self.assertIn("_blobs_load_pending", page_source)
        self.assertIn("create_blobs_load_worker", feature_source)
        self.assertIn("create_blob_action_worker", feature_source)
        self.assertIn("get_blobs_info", load_worker_source)
        self.assertIn("reload_blobs", load_worker_source)
        self.assertIn("save_user_blob", action_worker_source)
        self.assertIn("delete_user_blob", action_worker_source)

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
        self.assertIn("set_auto_update_enabled", worker_source)

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
        self.assertIn("prepare_support_bundle", worker_source)

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

        self.assertFalse(hasattr(Zapret2ModeControlPage, "_load_enabled_profile_count"))
        self.assertFalse(hasattr(Zapret1ModeControlPage, "_load_enabled_profile_count"))
        self.assertNotIn("count_enabled_profiles", zapret2_source)
        self.assertNotIn("count_enabled_profiles", zapret1_source)
        self.assertIn("get_enabled_profile_count_snapshot", worker_source)

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

        self.assertIn("launch_method", worker_init_source)
        self.assertIn("self._launch_method", worker_init_source)
        self.assertIn("launch_method=self._launch_method", worker_run_source)
        self.assertNotIn("ZAPRET2_MODE", worker_run_source)

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
        self.assertIn("set_discord_restart_setting", worker_source)
        self.assertIn("set_wssize_enabled", worker_source)
        self.assertIn("set_debug_log_enabled", worker_source)
        self.assertIn("launch_method=self._launch_method", worker_source)

    def test_control_program_settings_save_runs_through_worker(self) -> None:
        zapret1_auto_source = inspect.getsource(Zapret1ModeControlPage._on_auto_dpi_toggled)
        zapret1_tray_source = inspect.getsource(Zapret1ModeControlPage._on_hide_to_tray_toggled)
        zapret2_auto_source = inspect.getsource(Zapret2ModeControlPage._on_auto_dpi_toggled)
        zapret2_tray_source = inspect.getsource(Zapret2ModeControlPage._on_hide_to_tray_toggled)
        defender_source = inspect.getsource(windows_features_runtime.ControlPageWindowsFeatureMixin._on_defender_toggled)
        max_source = inspect.getsource(windows_features_runtime.ControlPageWindowsFeatureMixin._on_max_blocker_toggled)

        self.assertTrue(hasattr(program_settings_workers, "ProgramSettingsSaveWorker"))
        worker_source = inspect.getsource(program_settings_workers.ProgramSettingsSaveWorker.run)
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
        self.assertIn("set_auto_dpi_enabled", worker_source)
        self.assertIn("set_hide_to_tray_on_minimize_close", worker_source)
        self.assertIn('_request_program_settings_save("defender_disabled"', defender_source)
        self.assertIn('_request_program_settings_save("max_block"', max_source)
        self.assertNotIn("self._program_settings.set_defender_disabled", defender_source)
        self.assertNotIn("self._program_settings.set_max_block_enabled", max_source)
        self.assertIn("set_defender_disabled", worker_source)
        self.assertIn("set_max_block_enabled", worker_source)

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

    def test_zapret2_control_defers_initial_store_snapshot_during_startup(self) -> None:
        helper_source = inspect.getsource(control_page_shared.bind_control_ui_state_store)
        bind_source = inspect.getsource(Zapret2ModeControlPage.bind_ui_state_store)

        self.assertIn("emit_initial: bool = True", helper_source)
        self.assertIn("emit_initial=bool(emit_initial)", helper_source)
        self.assertIn("defer_initial_state", bind_source)
        self.assertIn("emit_initial=not defer_initial_state", bind_source)
        self.assertIn("_wait_for_startup_interactive_before_initial_ui_state", bind_source)

    def test_raw_preset_editor_loads_file_through_worker(self) -> None:
        source = inspect.getsource(PresetRawEditorPage._load_file)

        self.assertNotIn("self._controller.load_text(", source)
        self.assertIn("_request_raw_preset_text", source)

    def test_raw_preset_editor_saves_file_through_worker(self) -> None:
        save_source = inspect.getsource(PresetRawEditorPage._save_file)
        workflow_source = inspect.getsource(__import__("presets.raw_preset_editor_workflow", fromlist=["RawPresetEditorController"]).RawPresetEditorController)
        worker_source = inspect.getsource(RawPresetSaveWorker.run)

        self.assertNotIn("self._controller.save_text(", save_source)
        self.assertIn("_request_raw_preset_save", save_source)
        self.assertIn("create_save_worker", workflow_source)
        self.assertIn("RawPresetSaveWorker", workflow_source)
        self.assertIn("controller.save_text", worker_source)

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
        worker_source = inspect.getsource(RawPresetActivateWorker.run)

        self.assertNotIn("_activate_selected_preset()", source)
        self.assertNotIn("self._controller.activate(", source)
        self.assertIn("_request_preset_activation", source)
        self.assertIn("create_activate_worker", request_source)
        self.assertIn("controller.activate", worker_source)

    def test_raw_preset_editor_file_actions_run_through_worker(self) -> None:
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
        workflow_source = inspect.getsource(__import__("presets.raw_preset_editor_workflow", fromlist=["RawPresetEditorController"]).RawPresetEditorController)
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
        self.assertIn("create_action_worker", workflow_source)
        self.assertIn("RawPresetActionWorker", workflow_source)
        self.assertIn("controller.rename", worker_source)
        self.assertIn("controller.duplicate", worker_source)
        self.assertIn("controller.export", worker_source)
        self.assertIn("controller.reset_to_builtin", worker_source)
        self.assertIn("controller.delete", worker_source)

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
        worker_source = inspect.getsource(control_additional_settings_runtime.ControlTopSummaryWorker.run)

        self.assertIn("_request_top_summary_worker", winws1_refresh_source)
        self.assertIn("_request_top_summary_worker", winws2_refresh_source)
        self.assertNotIn("_load_preset_name()", winws1_refresh_source)
        self.assertNotIn("_load_selected_preset_name()", winws2_refresh_source)
        self.assertNotIn("_load_enabled_profile_count()", winws1_refresh_source)
        self.assertNotIn("_load_enabled_profile_count()", winws2_refresh_source)
        self.assertNotIn("get_selected_source_preset_display", winws1_page_source)
        self.assertNotIn("get_selected_source_preset_display", winws2_page_source)
        self.assertNotIn("get_enabled_profile_count_snapshot", winws1_page_source)
        self.assertNotIn("get_enabled_profile_count_snapshot", winws2_page_source)
        self.assertIn("create_top_summary_worker", runtime_source)
        self.assertIn("get_selected_source_preset_display", worker_source)
        self.assertIn("get_enabled_profile_count_snapshot", worker_source)

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
        self.assertIn("load_user_selection", worker_source)

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
        self.assertIn("get_hosts_state", worker_source)

    def test_hosts_page_cache_cannot_sync_read_runtime_state(self) -> None:
        page_source = inspect.getsource(HostsPage)
        cache_source = inspect.getsource(hosts_page_runtime.HostsPageRuntimeCache)

        self.assertFalse(hasattr(HostsPage, "_get_hosts_runtime_state"))
        self.assertFalse(hasattr(HostsPage, "_get_active_domains"))
        self.assertNotIn("self._controller.get_hosts_state", page_source)
        self.assertNotIn("get_runtime_state(", cache_source)
        self.assertNotIn("get_active_domains(", cache_source)

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
        worker_source = inspect.getsource(dpi_workers.DpiSettingsWorker.run)

        self.assertIn("_request_dpi_initial_state_load", load_source)
        self.assertNotIn("self._dpi_settings.load_initial_state", load_source)
        self.assertIn("_request_launch_method_apply", select_source)
        self.assertNotIn("self._dpi_settings.apply_launch_method", select_source)
        self.assertIn("create_dpi_settings_worker", page_source)
        self.assertIn("load_initial_state", worker_source)
        self.assertIn("apply_launch_method", worker_source)
        self.assertIn("load_orchestra_settings", worker_source)

    def test_dpi_orchestra_settings_save_runs_through_worker(self) -> None:
        spec = importlib.util.find_spec("orchestra.settings_worker")
        self.assertIsNotNone(spec)
        orchestra_settings_worker = importlib.import_module("orchestra.settings_worker")

        page_source = inspect.getsource(DpiSettingsPage)
        request_source = inspect.getsource(DpiSettingsPage._request_orchestra_setting_save)
        finished_source = inspect.getsource(DpiSettingsPage._on_orchestra_setting_save_worker_finished)
        worker_source = inspect.getsource(orchestra_settings_worker.OrchestraSettingSaveWorker.run)

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
        workflow_source = inspect.getsource(dns_load_workflow.start_background_loading)
        page_source = inspect.getsource(dns_page.NetworkPage)
        worker_source = inspect.getsource(DnsPageLoadWorker)

        self.assertIn("load_page_data_fn", workflow_source)
        self.assertNotIn("load_data_fn", workflow_source)
        self.assertIn("loaded = pyqtSignal", worker_source)
        self.assertIn("self.loaded.emit", worker_source)
        self.assertNotIn("self._load_data_fn()", worker_source)
        self.assertNotIn("load_data_fn=self._load_data", page_source)

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
        self.assertIn("flush_dns_cache", worker_source)
        self.assertIn("build_flush_dns_cache_result_plan", worker_source)

    def test_dns_apply_actions_run_through_worker(self) -> None:
        page_workers = importlib.import_module("dns.page_workers")
        feature_source = inspect.getsource(__import__("app.feature_facades.dns", fromlist=["DnsFeature"]).DnsFeature)
        page_source = inspect.getsource(dns_page.NetworkPage)

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
        worker_source = inspect.getsource(TelegramProxyDiagnosticsWorker)

        self.assertNotIn("progress_callback=publish_diag_result", workflow_source)
        self.assertIn("worker.progress.connect(publish_diag_result)", workflow_source)
        self.assertIn("progress = pyqtSignal", worker_source)
        self.assertIn("progress_callback=self.progress.emit", worker_source)

    def test_connection_support_bundle_prepares_through_worker(self) -> None:
        support_worker = importlib.import_module("diagnostics.support_worker")
        page_source = inspect.getsource(ConnectionTestPage)
        handler_source = inspect.getsource(ConnectionTestPage.open_support_with_log)
        handler_body = handler_source.split("\n", 1)[1]
        worker_source = inspect.getsource(support_worker.ConnectionSupportPrepareWorker.run)
        feature_source = inspect.getsource(DiagnosticsFeature)

        self.assertIn("_request_support_prepare", handler_source)
        self.assertNotIn("open_support_with_log(", handler_body)
        self.assertIn("create_support_prepare_worker", page_source)
        self.assertIn("_support_prepare_worker", page_source)
        self.assertIn("create_connection_support_prepare_worker", feature_source)
        self.assertIn("diagnostics.commands", worker_source)
        self.assertIn("prepare_connection_support", worker_source)


if __name__ == "__main__":
    unittest.main()
