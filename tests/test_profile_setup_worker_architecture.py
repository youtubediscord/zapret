from __future__ import annotations

import inspect
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class ProfileSetupWorkerArchitectureTests(unittest.TestCase):
    def test_profile_setup_page_receives_worker_factories_instead_of_controller(self) -> None:
        from app.feature_facades.profile import ProfileFeature
        from profile.ui.profile_setup_page import ProfileSetupPageBase
        from ui.navigation_pages import PageName
        from ui.page_deps.presets import build_profile_setup_page_kwargs

        init_source = inspect.getsource(ProfileSetupPageBase.__init__)
        page_source = inspect.getsource(ProfileSetupPageBase)
        deps_source = inspect.getsource(build_profile_setup_page_kwargs)
        feature_source = inspect.getsource(ProfileFeature)
        worker_factories = (
            "create_profile_setup_load_worker",
            "create_profile_list_file_load_worker",
            "create_profile_list_file_save_worker",
            "create_profile_list_file_validation_worker",
            "create_profile_settings_save_worker",
            "create_profile_raw_text_save_worker",
            "create_profile_enabled_save_worker",
            "create_profile_user_update_worker",
            "create_profile_user_delete_worker",
            "create_profile_strategy_apply_worker",
            "create_profile_strategy_feedback_save_worker",
        )

        for factory_name in worker_factories:
            self.assertIn(factory_name, init_source)
            self.assertIn(factory_name, deps_source)
            self.assertIn(factory_name, feature_source)
            self.assertIn(f"_{factory_name}_fn", page_source)

        self.assertNotIn("ProfileSetupController", page_source)
        self.assertNotIn("profile_setup_actions", page_source)
        self.assertNotIn("profile_setup_actions", init_source)
        self.assertNotIn("profile_feature", init_source)

        profile_feature = Mock()
        kwargs = build_profile_setup_page_kwargs(
            page_name=PageName.ZAPRET2_PROFILE_SETUP,
            profile_feature=profile_feature,
            show_page=Mock(),
            on_profile_setup_changed=Mock(),
        )

        for factory_name in worker_factories:
            self.assertIs(kwargs[factory_name], getattr(profile_feature, factory_name))

        self.assertNotIn("profile_setup_actions", kwargs)
        self.assertNotIn("profile_feature", kwargs)

    def test_profile_setup_load_worker_comes_from_profile_feature(self) -> None:
        from app.feature_facades.profile import ProfileFeature
        from profile.ui.profile_setup_page import ProfileSetupPageBase
        from profile.service import ProfilePresetService
        from ui.navigation_pages import PageName
        from ui.page_deps.presets import build_profile_setup_page_kwargs

        from profile.ui.profile_setup_payload_controller import ProfileSetupPayloadController

        init_source = inspect.getsource(ProfileSetupPageBase.__init__)
        request_source = inspect.getsource(ProfileSetupPayloadController._request_profile_setup_payload)
        start_source = inspect.getsource(ProfileSetupPayloadController._start_profile_setup_load_worker)
        create_source = inspect.getsource(ProfileSetupPageBase.create_profile_setup_load_worker)
        feature_source = inspect.getsource(ProfileFeature)
        service_init_source = inspect.getsource(ProfilePresetService.__init__)
        setup_source = inspect.getsource(ProfilePresetService.get_profile_setup)
        setup_locked_source = inspect.getsource(ProfilePresetService._get_profile_setup_locked)

        self.assertIn("create_profile_setup_load_worker", init_source)
        self.assertIn("_create_profile_setup_load_worker_fn", init_source)
        self.assertIn("_start_profile_setup_load_worker", request_source)
        self.assertIn("create_profile_setup_load_worker", start_source)
        self.assertNotIn("_controller.create_load_worker", request_source)
        self.assertNotIn("_controller.create_load_worker", start_source)
        self.assertIn("_create_profile_setup_load_worker_fn", create_source)
        self.assertIn("create_profile_setup_load_worker", feature_source)
        self.assertIn("ProfileDerivedCache()", service_init_source)
        self.assertNotIn("_profile_setup_payload_cache", service_init_source)
        self.assertIn("_profile_list_lock", setup_source)
        self.assertIn("_profile_derived_cache.core_for", setup_locked_source)
        self.assertIn("_profile_sources_cache.sources_for", setup_locked_source)
        self.assertNotIn("_remember_profile_setup_payload", setup_locked_source)

        profile_feature = Mock()
        kwargs = build_profile_setup_page_kwargs(
            page_name=PageName.ZAPRET2_PROFILE_SETUP,
            profile_feature=profile_feature,
            show_page=Mock(),
            on_profile_setup_changed=Mock(),
        )

        self.assertIs(
            kwargs["create_profile_setup_load_worker"],
            profile_feature.create_profile_setup_load_worker,
        )
        self.assertNotIn("profile_feature", kwargs)

    def test_profile_list_warmup_does_not_precompute_setup_payloads(self) -> None:
        from app.feature_facades.profile import ProfileFeature
        from profile.service import ProfilePresetService

        warm_source = inspect.getsource(ProfileFeature.warm_profile_list)

        self.assertNotIn("warm_profile_setups", warm_source)
        self.assertFalse(hasattr(ProfilePresetService, "warm_profile_setups"))

    def test_profile_setup_reload_waits_while_load_worker_runs(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase

        runtime = SimpleNamespace(
            is_running=Mock(return_value=True),
            start_qthread_worker=Mock(),
        )
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "profile-1"
        page._setup_load_runtime = runtime
        page._setup_load_request_id = 4
        page._setup_load_dirty = False
        page._setup_load_start_scheduled = False
        page._summary = Mock()
        page._enabled_checkbox = Mock()

        ProfileSetupPageBase.reload_current_profile(page)

        runtime.start_qthread_worker.assert_not_called()
        self.assertTrue(page._setup_load_dirty)
        self.assertEqual(page._setup_load_request_id, 5)

    def test_profile_setup_pending_reload_starts_after_worker_signal(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase

        worker = SimpleNamespace(_request_id=1)
        runtime = SimpleNamespace(
            is_running=Mock(return_value=False),
            start_qthread_worker=Mock(return_value=(1, worker)),
        )
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "profile-1"
        page._setup_load_runtime = runtime
        page._setup_load_runtime_request_id = 1
        page._setup_load_request_id = 2
        page._setup_load_dirty = True
        page._setup_load_start_scheduled = False
        page._cleanup_in_progress = False
        page._summary = Mock()
        page._enabled_checkbox = Mock()
        page.create_profile_setup_load_worker = Mock()
        callbacks = []

        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_profile_setup_worker_finished(page, worker)

        runtime.start_qthread_worker.assert_not_called()
        self.assertEqual(len(callbacks), 1)
        self.assertTrue(page._setup_load_start_scheduled)

        callbacks[0]()

        runtime.start_qthread_worker.assert_called_once()
        self.assertFalse(page._setup_load_dirty)
        self.assertFalse(page._setup_load_start_scheduled)

    def test_stale_profile_setup_worker_finished_does_not_restart_pending_reload(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase

        stale_worker = SimpleNamespace(_request_id=3)
        runtime = SimpleNamespace(
            is_running=Mock(return_value=False),
            start_qthread_worker=Mock(),
        )
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._profile_key = "profile-1"
        page._setup_load_runtime = runtime
        page._setup_load_runtime_request_id = 4
        page._setup_load_request_id = 5
        page._setup_load_dirty = True
        page._setup_load_start_scheduled = False
        page._cleanup_in_progress = False
        page._summary = Mock()
        page._enabled_checkbox = Mock()
        page.create_profile_setup_load_worker = Mock()
        callbacks = []

        with patch(
            "profile.ui.profile_setup_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: callbacks.append(callback),
        ):
            ProfileSetupPageBase._on_profile_setup_worker_finished(page, stale_worker)

        runtime.start_qthread_worker.assert_not_called()
        self.assertEqual(callbacks, [])
        self.assertTrue(page._setup_load_dirty)

    def test_profile_setup_load_queue_uses_shared_latest_worker_state(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase
        from ui.latest_value_worker_state import LatestValueWorkerState

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._setup_load_runtime = SimpleNamespace(is_running=Mock(return_value=False))

        from profile.ui.profile_setup_payload_controller import ProfileSetupPayloadController

        init_source = inspect.getsource(ProfileSetupPageBase.__init__)
        request_source = inspect.getsource(ProfileSetupPayloadController._request_profile_setup_payload)
        start_source = inspect.getsource(ProfileSetupPayloadController._start_profile_setup_load_worker)
        finished_source = inspect.getsource(ProfileSetupPageBase._on_profile_setup_worker_finished)
        cleanup_source = inspect.getsource(ProfileSetupPageBase.cleanup)

        self.assertTrue(hasattr(ProfileSetupPageBase, "_setup_load_state_obj"))
        self.assertIsInstance(page._setup_load_state_obj(), LatestValueWorkerState)
        self.assertIn("_setup_load_state = LatestValueWorkerState", init_source)
        self.assertIn("_setup_load_state_obj()", request_source)
        self.assertIn("_setup_load_state_obj()", finished_source)
        self.assertIn("_setup_load_state_obj().reset()", cleanup_source)
        self.assertIn("_setup_load_runtime_request_id", start_source)
        self.assertIn("_setup_load_runtime_request_id = 0", cleanup_source)
        self.assertNotIn("_setup_load_runtime_worker", init_source)
        self.assertNotIn("_setup_load_runtime_worker", start_source)
        self.assertNotIn("_setup_load_runtime_worker", finished_source)
        self.assertNotIn("_setup_load_runtime_worker", cleanup_source)
        self.assertNotIn("self._setup_load_dirty = False", init_source)
        self.assertNotIn("self._setup_load_start_scheduled = False", init_source)

    def test_list_file_reload_invalidates_running_load_result(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase

        runtime = SimpleNamespace(
            is_running=Mock(return_value=True),
            start_qthread_worker=Mock(),
        )
        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._editor_tab_built = True
        page._profile_key = "profile-1"
        page._list_file_load_runtime = runtime
        page._list_file_load_request_id = 4
        page._pending_list_file_load = False
        page._list_file_load_start_scheduled = False
        page._list_file_status_label = Mock()
        page._schedule_list_file_editor_state_apply = Mock()
        page._current_filter_kind = Mock(return_value="hostlist")
        page._current_filter_value = Mock(return_value="lists/youtube.txt")

        from profile.profile_setup_loader import ProfileListFileLoadResult

        ProfileSetupPageBase._request_list_file_editor_state(page)
        ProfileSetupPageBase._on_list_file_editor_state_loaded(
            page,
            4,
            ProfileListFileLoadResult(
                profile_key="profile-1",
                filter_kind="hostlist",
                filter_value="lists/youtube.txt",
                state=object(),
            ),
        )

        runtime.start_qthread_worker.assert_not_called()
        self.assertTrue(page._pending_list_file_load)
        self.assertEqual(page._list_file_load_request_id, 4)
        page._schedule_list_file_editor_state_apply.assert_not_called()

    def test_list_file_load_queue_uses_shared_latest_worker_state(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase
        from ui.latest_value_worker_state import LatestValueWorkerState

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_load_runtime = SimpleNamespace(is_running=Mock(return_value=False))

        from profile.ui.profile_list_file_editor_controller import ProfileListFileEditorController

        init_source = inspect.getsource(ProfileSetupPageBase.__init__)
        request_source = inspect.getsource(ProfileListFileEditorController._request_list_file_editor_state)
        finished_source = inspect.getsource(ProfileSetupPageBase._on_list_file_worker_finished)
        cleanup_source = inspect.getsource(ProfileSetupPageBase.cleanup)

        self.assertTrue(hasattr(ProfileSetupPageBase, "_list_file_load_state_obj"))
        self.assertIsInstance(page._list_file_load_state_obj(), LatestValueWorkerState)
        self.assertIn("_list_file_load_state = LatestValueWorkerState", init_source)
        self.assertIn("_list_file_load_state_obj()", request_source)
        self.assertIn("_list_file_load_state_obj()", finished_source)
        self.assertIn("_list_file_load_state_obj().reset()", cleanup_source)
        self.assertNotIn("self._pending_list_file_load = False", init_source)
        self.assertNotIn("self._list_file_load_start_scheduled = False", init_source)

    def test_list_file_validation_queue_uses_shared_latest_worker_state(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase
        from ui.latest_value_worker_state import LatestValueWorkerState

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_validation_runtime = SimpleNamespace(is_running=Mock(return_value=False))

        from profile.ui.profile_list_file_editor_controller import ProfileListFileEditorController

        init_source = inspect.getsource(ProfileSetupPageBase.__init__)
        request_source = inspect.getsource(ProfileListFileEditorController._request_list_file_validation)
        finished_source = inspect.getsource(ProfileSetupPageBase._on_list_file_validation_worker_finished)
        cleanup_source = inspect.getsource(ProfileSetupPageBase.cleanup)

        self.assertTrue(hasattr(ProfileSetupPageBase, "_list_file_validation_state_obj"))
        self.assertIsInstance(page._list_file_validation_state_obj(), LatestValueWorkerState)
        self.assertIn("_list_file_validation_state = LatestValueWorkerState", init_source)
        self.assertIn("_list_file_validation_state_obj()", request_source)
        self.assertIn("_list_file_validation_state_obj()", finished_source)
        self.assertIn("_list_file_validation_state_obj().reset()", cleanup_source)
        self.assertNotIn("self._pending_list_file_validation = None", init_source)
        self.assertNotIn("self._list_file_validation_start_scheduled = False", init_source)

    def test_list_file_save_queue_uses_shared_latest_worker_state(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase
        from ui.latest_value_worker_state import LatestValueWorkerState

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._list_file_save_runtime = SimpleNamespace(is_running=Mock(return_value=False))

        from profile.ui.profile_list_file_editor_controller import ProfileListFileEditorController

        init_source = inspect.getsource(ProfileSetupPageBase.__init__)
        request_source = inspect.getsource(ProfileListFileEditorController._request_list_file_save)
        finished_source = inspect.getsource(ProfileListFileEditorController._on_list_file_save_worker_finished)
        cleanup_source = inspect.getsource(ProfileSetupPageBase.cleanup)

        self.assertTrue(hasattr(ProfileSetupPageBase, "_list_file_save_state_obj"))
        self.assertIsInstance(page._list_file_save_state_obj(), LatestValueWorkerState)
        self.assertIn("_list_file_save_state = LatestValueWorkerState", init_source)
        self.assertIn("_list_file_save_state_obj()", request_source)
        self.assertIn("_list_file_save_state_obj()", finished_source)
        self.assertIn("_list_file_save_state_obj().reset()", cleanup_source)
        self.assertNotIn("self._pending_list_file_save", init_source)
        self.assertNotIn("self._scheduled_list_file_save", init_source)
        self.assertNotIn("self._list_file_save_start_scheduled = False", init_source)

    def test_raw_profile_save_queue_uses_shared_latest_worker_state(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase
        from ui.latest_value_worker_state import LatestValueWorkerState

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._raw_profile_save_runtime = SimpleNamespace(is_running=Mock(return_value=False))

        from profile.ui.profile_setup_save_controllers import ProfileSetupSaveController

        init_source = inspect.getsource(ProfileSetupPageBase.__init__)
        request_source = inspect.getsource(ProfileSetupSaveController._request_raw_profile_save)
        finished_source = inspect.getsource(ProfileSetupSaveController._on_raw_profile_save_worker_finished)
        cleanup_source = inspect.getsource(ProfileSetupPageBase.cleanup)

        self.assertTrue(hasattr(ProfileSetupPageBase, "_raw_profile_save_state_obj"))
        self.assertIsInstance(page._raw_profile_save_state_obj(), LatestValueWorkerState)
        self.assertIn("_raw_profile_save_state = LatestValueWorkerState", init_source)
        self.assertIn("_raw_profile_save_state_obj()", request_source)
        self.assertIn("_raw_profile_save_state_obj()", finished_source)
        self.assertIn("_raw_profile_save_state_obj().reset()", cleanup_source)
        self.assertNotIn("self._pending_raw_profile_save", init_source)

    def test_settings_save_queue_uses_shared_latest_worker_state(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase
        from ui.latest_value_worker_state import LatestValueWorkerState

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._settings_save_runtime = SimpleNamespace(is_running=Mock(return_value=False))

        from profile.ui.profile_setup_save_controllers import ProfileSetupSaveController

        init_source = inspect.getsource(ProfileSetupPageBase.__init__)
        request_source = inspect.getsource(ProfileSetupSaveController._request_settings_save)
        finished_source = inspect.getsource(ProfileSetupSaveController._on_settings_save_worker_finished)
        cleanup_source = inspect.getsource(ProfileSetupPageBase.cleanup)

        self.assertTrue(hasattr(ProfileSetupPageBase, "_settings_save_state_obj"))
        self.assertIsInstance(page._settings_save_state_obj(), LatestValueWorkerState)
        self.assertIn("_settings_save_state = LatestValueWorkerState", init_source)
        self.assertIn("_settings_save_state_obj()", request_source)
        self.assertIn("_settings_save_state_obj()", finished_source)
        self.assertIn("_settings_save_state_obj().reset()", cleanup_source)
        self.assertNotIn("self._pending_settings_save", init_source)

    def test_enabled_save_queue_uses_shared_latest_worker_state(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase
        from ui.latest_value_worker_state import LatestValueWorkerState

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._enabled_save_runtime = SimpleNamespace(is_running=Mock(return_value=False))

        init_source = inspect.getsource(ProfileSetupPageBase.__init__)
        from profile.ui.profile_setup_save_controllers import ProfileSetupSaveController

        request_source = inspect.getsource(ProfileSetupPageBase._on_enabled_changed)
        finished_source = inspect.getsource(ProfileSetupSaveController._on_enabled_save_worker_finished)
        cleanup_source = inspect.getsource(ProfileSetupPageBase.cleanup)

        self.assertTrue(hasattr(ProfileSetupPageBase, "_enabled_save_state_obj"))
        self.assertIsInstance(page._enabled_save_state_obj(), LatestValueWorkerState)
        self.assertIn("_enabled_save_state = LatestValueWorkerState", init_source)
        self.assertIn("_enabled_save_state_obj()", request_source)
        self.assertIn("_enabled_save_state_obj()", finished_source)
        self.assertIn("_enabled_save_state_obj().reset()", cleanup_source)
        self.assertNotIn("self._pending_enabled_save", init_source)
        self.assertNotIn("self._enabled_save_start_scheduled = False", init_source)

    def test_strategy_feedback_save_queue_uses_shared_latest_worker_state(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase
        from ui.latest_value_worker_state import LatestValueWorkerState

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._strategy_feedback_save_runtime = SimpleNamespace(is_running=Mock(return_value=False))

        from profile.ui.profile_strategy_controller import ProfileStrategyController

        init_source = inspect.getsource(ProfileSetupPageBase.__init__)
        request_source = inspect.getsource(ProfileStrategyController._request_strategy_feedback_save)
        finished_source = inspect.getsource(ProfileStrategyController._on_strategy_feedback_save_worker_finished)
        cleanup_source = inspect.getsource(ProfileSetupPageBase.cleanup)

        self.assertTrue(hasattr(ProfileSetupPageBase, "_strategy_feedback_save_state_obj"))
        self.assertIsInstance(page._strategy_feedback_save_state_obj(), LatestValueWorkerState)
        self.assertIn("_strategy_feedback_save_state = LatestValueWorkerState", init_source)
        self.assertIn("_strategy_feedback_save_state_obj()", request_source)
        self.assertIn("_strategy_feedback_save_state_obj()", finished_source)
        self.assertIn("_strategy_feedback_save_state_obj().reset()", cleanup_source)
        self.assertNotIn("self._pending_strategy_feedback_save", init_source)
        self.assertNotIn("self._strategy_feedback_save_start_scheduled = False", init_source)

    def test_strategy_apply_queue_uses_shared_latest_worker_state(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase
        from ui.latest_value_worker_state import LatestValueWorkerState

        page = ProfileSetupPageBase.__new__(ProfileSetupPageBase)
        page._strategy_apply_runtime = SimpleNamespace(is_running=Mock(return_value=False))

        from profile.ui.profile_strategy_controller import ProfileStrategyController

        init_source = inspect.getsource(ProfileSetupPageBase.__init__)
        request_source = inspect.getsource(ProfileStrategyController._request_strategy_apply)
        finished_source = inspect.getsource(ProfileStrategyController._on_strategy_apply_worker_finished)
        cleanup_source = inspect.getsource(ProfileSetupPageBase.cleanup)

        self.assertTrue(hasattr(ProfileSetupPageBase, "_strategy_apply_state_obj"))
        self.assertIsInstance(page._strategy_apply_state_obj(), LatestValueWorkerState)
        self.assertIn("_strategy_apply_state = LatestValueWorkerState", init_source)
        self.assertIn("_strategy_apply_state_obj()", request_source)
        self.assertIn("_strategy_apply_state_obj()", finished_source)
        self.assertIn("_strategy_apply_state_obj().reset()", cleanup_source)
        self.assertNotIn("self._pending_strategy_apply", init_source)

    def test_context_action_worker_receives_action_functions(self) -> None:
        from profile.profile_setup_loader import ProfilePresetProfileActionWorker

        init_source = inspect.getsource(ProfilePresetProfileActionWorker.__init__)
        run_source = inspect.getsource(ProfilePresetProfileActionWorker.run)

        self.assertIn("set_profile_enabled", init_source)
        self.assertIn("duplicate_profile", init_source)
        self.assertIn("delete_profile", init_source)
        self.assertIn("load_profile_item", init_source)
        self.assertIn("self._set_profile_enabled", init_source)
        self.assertIn("self._duplicate_profile", init_source)
        self.assertIn("self._delete_profile", init_source)
        self.assertIn("self._load_profile_item", init_source)
        self.assertNotIn("self._service", init_source)
        self.assertNotIn("self._profile", init_source)
        self.assertNotIn("launch_method", init_source)
        self.assertIn("self._set_profile_enabled(", run_source)
        self.assertIn("self._duplicate_profile(", run_source)
        self.assertIn("self._delete_profile(", run_source)
        self.assertIn("self._load_profile_item(", run_source)
        self.assertNotIn("self._service.", run_source)

    def test_profile_move_worker_receives_move_functions(self) -> None:
        from profile.profile_setup_loader import ProfilePresetProfileMoveWorker

        init_source = inspect.getsource(ProfilePresetProfileMoveWorker.__init__)
        run_source = inspect.getsource(ProfilePresetProfileMoveWorker.run)

        self.assertIn("move_profile_before", init_source)
        self.assertIn("move_profile_after", init_source)
        self.assertIn("move_profile_to_end", init_source)
        self.assertIn("move_profile_to_folder", init_source)
        self.assertIn("self._move_profile_before", init_source)
        self.assertIn("self._move_profile_after", init_source)
        self.assertIn("self._move_profile_to_end", init_source)
        self.assertIn("self._move_profile_to_folder", init_source)
        self.assertNotIn("self._service", init_source)
        self.assertNotIn("self._profile", init_source)
        self.assertNotIn("launch_method", init_source)
        self.assertIn("self._move_profile_before(", run_source)
        self.assertIn("self._move_profile_after(", run_source)
        self.assertIn("self._move_profile_to_end(", run_source)
        self.assertIn("self._move_profile_to_folder(", run_source)
        self.assertNotIn("self._service.", run_source)

    def test_preset_setup_page_receives_worker_factories_instead_of_profile_feature(self) -> None:
        from profile.ui.preset_setup_page import PresetSetupPageBase
        from ui.page_deps.presets import build_preset_setup_page_kwargs
        from ui.navigation_pages import PageName
        from unittest.mock import Mock

        init_source = inspect.getsource(PresetSetupPageBase.__init__)
        page_source = inspect.getsource(PresetSetupPageBase)
        action_source = inspect.getsource(PresetSetupPageBase._create_profile_context_action_worker)
        item_refresh_source = inspect.getsource(PresetSetupPageBase._create_profile_item_refresh_worker)
        move_source = inspect.getsource(PresetSetupPageBase._create_profile_move_worker)
        create_user_source = inspect.getsource(PresetSetupPageBase._create_user_profile_create_worker)
        update_user_source = inspect.getsource(PresetSetupPageBase._create_user_profile_update_worker)
        delete_user_source = inspect.getsource(PresetSetupPageBase._create_user_profile_delete_worker)

        self.assertIn("create_profile_list_load_worker", init_source)
        self.assertIn("create_profile_item_refresh_worker", init_source)
        self.assertIn("create_profile_context_action_worker", init_source)
        self.assertIn("create_profile_move_worker", init_source)
        self.assertIn("create_user_profile_create_worker", init_source)
        self.assertIn("create_user_profile_update_worker", init_source)
        self.assertIn("create_user_profile_delete_worker", init_source)
        self.assertIn("create_profile_folder_action_worker", init_source)
        self.assertIn("create_profile_request_form_open_worker", init_source)
        self.assertNotIn("list_profiles", init_source)
        self.assertNotIn("create_user_profile,", init_source)
        self.assertNotIn("update_user_profile,", init_source)
        self.assertNotIn("delete_user_profile,", init_source)
        self.assertNotIn("profile_feature", init_source)
        self.assertNotIn("self._profile =", page_source)
        self.assertNotIn("self._profile.", page_source)
        self.assertNotIn("_list_profiles_fn", page_source)
        self.assertNotIn("_create_user_profile_fn", page_source)
        self.assertNotIn("_update_user_profile_fn", page_source)
        self.assertNotIn("_delete_user_profile_fn", page_source)
        self.assertNotIn("self._profile.create_profile_context_action_worker", action_source)
        self.assertNotIn("ProfilePresetProfileActionWorker(", action_source)
        self.assertNotIn("self._profile.create_profile_item_refresh_worker", item_refresh_source)
        self.assertNotIn("ProfileItemRefreshWorker(", item_refresh_source)
        self.assertNotIn("self._profile.create_profile_move_worker", move_source)
        self.assertNotIn("ProfilePresetProfileMoveWorker(", move_source)
        self.assertNotIn("ProfileUserProfileCreateWorker(", create_user_source)
        self.assertNotIn("ProfileUserProfileUpdateWorker(", update_user_source)
        self.assertNotIn("ProfileUserProfileDeleteWorker(", delete_user_source)
        self.assertIn("_create_user_profile_create_worker_fn", create_user_source)
        self.assertIn("_create_user_profile_update_worker_fn", update_user_source)
        self.assertIn("_create_user_profile_delete_worker_fn", delete_user_source)

        profile_feature = Mock()
        external_actions_feature = Mock()
        kwargs = build_preset_setup_page_kwargs(
            page_name=PageName.ZAPRET2_PRESET_SETUP,
            profile_feature=profile_feature,
            external_actions_feature=external_actions_feature,
            open_profile_setup=Mock(),
            show_page=Mock(),
            ui_state_store=Mock(),
        )

        self.assertIs(kwargs["create_profile_list_load_worker"], profile_feature.create_profile_list_load_worker)
        self.assertIs(
            kwargs["create_profile_item_refresh_worker"],
            profile_feature.create_profile_item_refresh_worker,
        )
        self.assertIs(
            kwargs["create_profile_context_action_worker"],
            profile_feature.create_profile_context_action_worker,
        )
        self.assertIs(kwargs["create_profile_move_worker"], profile_feature.create_profile_move_worker)
        self.assertIs(
            kwargs["create_user_profile_create_worker"],
            profile_feature.create_user_profile_create_worker,
        )
        self.assertIs(
            kwargs["create_user_profile_update_worker"],
            profile_feature.create_user_profile_update_worker,
        )
        self.assertIs(
            kwargs["create_user_profile_delete_worker"],
            profile_feature.create_user_profile_delete_worker,
        )
        self.assertIs(
            kwargs["create_profile_folder_action_worker"],
            profile_feature.create_profile_folder_action_worker,
        )
        self.assertIs(
            kwargs["create_profile_request_form_open_worker"],
            external_actions_feature.create_open_url_worker,
        )
        self.assertNotIn("list_profiles", kwargs)
        self.assertNotIn("create_user_profile", kwargs)
        self.assertNotIn("update_user_profile", kwargs)
        self.assertNotIn("delete_user_profile", kwargs)
        self.assertNotIn("profile_feature", kwargs)

    def test_preset_setup_page_uses_worker_runtime_instead_of_manual_worker_fields(self) -> None:
        from profile.ui.preset_setup_page import PresetSetupPageBase
        from profile.ui.profile_payload_controller import ProfilePayloadController

        init_source = inspect.getsource(PresetSetupPageBase.__init__)
        page_source = inspect.getsource(PresetSetupPageBase)
        from profile.ui.preset_write_queue import PresetWriteQueue
        from profile.ui.profile_folder_controller import ProfileFolderController

        worker_start_sources = (
            inspect.getsource(ProfilePayloadController._request_profiles_payload),
            inspect.getsource(PresetWriteQueue._request_profile_context_action)
            + inspect.getsource(PresetWriteQueue._start_profile_context_action_worker),
            inspect.getsource(PresetWriteQueue._request_user_profile_create),
            inspect.getsource(PresetWriteQueue._request_user_profile_update),
            inspect.getsource(PresetWriteQueue._request_user_profile_delete),
            inspect.getsource(PresetWriteQueue._request_profile_move)
            + inspect.getsource(PresetWriteQueue._start_profile_move_worker),
            inspect.getsource(ProfileFolderController._request_profile_folder_action),
        )

        self.assertIn("OneShotWorkerRuntime", init_source)
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
            self.assertIn(attr, init_source)

        for source in worker_start_sources:
            self.assertIn("start_qthread_worker", source)
            self.assertNotIn("worker.start()", source)

        for attr in (
            "_profile_load_worker =",
            "_profile_context_action_worker =",
            "_profile_move_worker =",
            "_profile_folder_action_worker =",
            "_user_profile_create_worker =",
            "_user_profile_update_worker =",
            "_user_profile_delete_worker =",
        ):
            self.assertNotIn(attr, page_source)

    def test_preset_setup_profile_load_refresh_uses_shared_latest_worker_state(self) -> None:
        from profile.ui.preset_setup_page import PresetSetupPageBase
        from profile.ui.profile_payload_controller import ProfilePayloadController
        from ui.latest_value_worker_state import LatestValueWorkerState

        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_load_runtime = SimpleNamespace(is_running=Mock(return_value=False))

        init_source = inspect.getsource(PresetSetupPageBase.__init__)
        request_source = inspect.getsource(ProfilePayloadController._request_profiles_payload)
        loaded_source = inspect.getsource(ProfilePayloadController._on_profile_payload_loaded)
        failed_source = inspect.getsource(ProfilePayloadController._on_profile_payload_failed)
        finished_source = inspect.getsource(ProfilePayloadController._on_profile_worker_finished)
        cleanup_source = inspect.getsource(PresetSetupPageBase.cleanup)

        self.assertTrue(hasattr(PresetSetupPageBase, "_profile_load_refresh_state_obj"))
        self.assertIsInstance(page._profile_load_refresh_state_obj(), LatestValueWorkerState)
        self.assertIn("_profile_load_refresh_state = LatestValueWorkerState", init_source)
        self.assertIn("_profile_load_refresh_state_obj()", request_source)
        self.assertIn("_profile_load_refresh_state_obj()", loaded_source)
        self.assertIn("_profile_load_refresh_state_obj()", failed_source)
        self.assertIn("_profile_load_refresh_state_obj()", finished_source)
        self.assertIn("_profile_load_refresh_state_obj().reset()", cleanup_source)
        self.assertNotIn("self._profile_load_refresh_pending = False", init_source)

    def test_user_profile_write_queue_uses_shared_profile_preset_queued_state(self) -> None:
        from profile.ui.preset_setup_page import PresetSetupPageBase
        from ui.queued_worker_state import QueuedWorkerState

        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_context_action_runtime = SimpleNamespace(is_running=Mock(return_value=False))

        from profile.ui.preset_write_queue import PresetWriteQueue

        init_source = inspect.getsource(PresetSetupPageBase.__init__)
        queue_source = inspect.getsource(PresetWriteQueue._queue_profile_preset_write_operation)
        pop_source = inspect.getsource(PresetWriteQueue._pop_next_profile_preset_write_operation)
        has_pending_source = inspect.getsource(PresetSetupPageBase._has_pending_profile_preset_write_operation)
        schedule_source = inspect.getsource(PresetWriteQueue._schedule_next_profile_preset_write_operation_start)
        cleanup_source = inspect.getsource(PresetSetupPageBase.cleanup)

        self.assertIsInstance(page._profile_preset_write_state_obj(), QueuedWorkerState)
        page._pending_user_profile_operations = [
            {
                "action": "update",
                "profile_id": "user-1",
                "name": "Latest",
                "protocol": "udp",
                "ports": "443",
            }
        ]
        self.assertEqual(
            [
                (
                    operation.get("kind"),
                    operation.get("action"),
                    operation.get("profile_id"),
                )
                for operation in page._profile_preset_write_state_obj().pending
            ],
            [("user_profile", "update", "user-1")],
        )
        self.assertIn("_profile_preset_write_state_obj()", queue_source)
        self.assertIn("_profile_preset_write_state_obj()", pop_source)
        self.assertIn("_profile_preset_write_state_obj()", has_pending_source)
        self.assertIn("_profile_preset_write_state_obj()", schedule_source)
        self.assertIn("_profile_preset_write_state_obj().reset()", cleanup_source)
        self.assertNotIn("self._pending_user_profile_operations", init_source)

    def test_context_and_move_write_queues_use_shared_profile_preset_queued_state(self) -> None:
        from profile.ui.preset_setup_page import PresetSetupPageBase

        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_context_action_runtime = SimpleNamespace(is_running=Mock(return_value=False))

        from profile.ui.preset_write_queue import PresetWriteQueue

        init_source = inspect.getsource(PresetSetupPageBase.__init__)
        queue_source = inspect.getsource(PresetWriteQueue._queue_profile_preset_write_operation)
        pop_source = inspect.getsource(PresetWriteQueue._pop_next_profile_preset_write_operation)
        has_pending_source = inspect.getsource(PresetSetupPageBase._has_pending_profile_preset_write_operation)
        cleanup_source = inspect.getsource(PresetSetupPageBase.cleanup)

        page._pending_profile_context_actions = [
            {
                "action": "set_enabled",
                "profile_key": "profile-a",
                "enabled": False,
            }
        ]
        page._pending_profile_moves = [
            {
                "action": "folder",
                "source_profile_key": "profile-b",
                "destination_profile_key": "",
                "destination_group_key": "games",
            }
        ]

        self.assertEqual(
            [
                (
                    operation.get("kind"),
                    operation.get("action"),
                    operation.get("profile_key"),
                    operation.get("source_profile_key"),
                )
                for operation in page._profile_preset_write_state_obj().pending
            ],
            [
                ("context", "set_enabled", "profile-a", ""),
                ("move", "folder", "profile-b", "profile-b"),
            ],
        )
        self.assertIn("_profile_preset_write_state_obj()", queue_source)
        self.assertIn("_profile_preset_write_state_obj()", pop_source)
        self.assertIn("_profile_preset_write_state_obj()", has_pending_source)
        self.assertIn("_profile_preset_write_state_obj().reset()", cleanup_source)
        self.assertNotIn("self._pending_profile_context_actions", init_source)
        self.assertNotIn("self._pending_profile_moves", init_source)

    def test_profile_folder_action_waits_while_restart_is_scheduled(self) -> None:
        from profile.ui.preset_setup_page import PresetSetupPageBase

        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_folder_action_start_scheduled = True
        page._profile_folder_action_pending = []
        page._profile_folder_action_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())

        PresetSetupPageBase._request_profile_folder_action(
            page,
            "move",
            folder_key="favorites",
            name="Profile",
            direction=1,
            collapsed=False,
            refresh=True,
            context_extra={"source": "menu"},
        )

        page._profile_folder_action_runtime.start_qthread_worker.assert_not_called()
        self.assertEqual(
            page._profile_folder_action_pending,
            [
                {
                    "action": "move",
                    "folder_key": "favorites",
                    "name": "Profile",
                    "direction": 1,
                    "collapsed": False,
                    "refresh": True,
                    "context_extra": {"source": "menu"},
                }
            ],
        )

    def test_duplicate_profile_folder_action_is_queued_once(self) -> None:
        from profile.ui.preset_setup_page import PresetSetupPageBase

        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_folder_action_start_scheduled = True
        page._profile_folder_action_pending = []
        page._profile_folder_action_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())

        for _ in range(2):
            PresetSetupPageBase._request_profile_folder_action(
                page,
                "move",
                folder_key="favorites",
                name="Profile",
                direction=1,
                collapsed=False,
                refresh=True,
                context_extra={"source": "menu"},
            )

        page._profile_folder_action_runtime.start_qthread_worker.assert_not_called()
        self.assertEqual(
            page._profile_folder_action_pending,
            [
                {
                    "action": "move",
                    "folder_key": "favorites",
                    "name": "Profile",
                    "direction": 1,
                    "collapsed": False,
                    "refresh": True,
                    "context_extra": {"source": "menu"},
                }
            ],
        )

    def test_profile_folder_set_collapsed_keeps_latest_pending_state(self) -> None:
        from profile.ui.preset_setup_page import PresetSetupPageBase

        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_folder_action_start_scheduled = True
        page._profile_folder_action_pending = []
        page._profile_folder_action_runtime = SimpleNamespace(is_running=Mock(return_value=False), start_qthread_worker=Mock())

        PresetSetupPageBase._request_profile_folder_action(
            page,
            "set_collapsed",
            folder_key="games",
            collapsed=True,
            refresh=False,
        )
        PresetSetupPageBase._request_profile_folder_action(
            page,
            "set_collapsed",
            folder_key="games",
            collapsed=False,
            refresh=False,
        )

        page._profile_folder_action_runtime.start_qthread_worker.assert_not_called()
        self.assertEqual(
            page._profile_folder_action_pending,
            [
                {
                    "action": "set_collapsed",
                    "folder_key": "games",
                    "name": "",
                    "direction": 0,
                    "collapsed": False,
                    "refresh": False,
                    "context_extra": {},
                }
            ],
        )

    def test_profile_context_action_waits_while_next_write_start_is_scheduled(self) -> None:
        from profile.ui.preset_setup_page import PresetSetupPageBase

        page = PresetSetupPageBase.__new__(PresetSetupPageBase)
        page._profile_preset_write_operation_start_scheduled = True
        page._profile_context_action_runtime = SimpleNamespace(
            is_running=Mock(return_value=False),
            start_qthread_worker=Mock(),
        )
        page._profile_move_runtime = SimpleNamespace(is_running=Mock(return_value=False))
        page._user_profile_create_runtime = SimpleNamespace(is_running=Mock(return_value=False))
        page._user_profile_update_runtime = SimpleNamespace(is_running=Mock(return_value=False))
        page._user_profile_delete_runtime = SimpleNamespace(is_running=Mock(return_value=False))
        page._pending_profile_preset_write_operations = []
        page._pending_profile_context_actions = []
        page._pending_profile_moves = []
        page._pending_user_profile_operations = []

        PresetSetupPageBase._request_profile_context_action(
            page,
            "enable",
            "profile-1",
            enabled=True,
        )

        page._profile_context_action_runtime.start_qthread_worker.assert_not_called()
        self.assertEqual(
            page._pending_profile_preset_write_operations,
            [
                {
                    "kind": "context",
                    "action": "enable",
                    "profile_key": "profile-1",
                    "enabled": True,
                    "source_profile_key": "",
                    "destination_profile_key": "",
                    "destination_group_key": "",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
