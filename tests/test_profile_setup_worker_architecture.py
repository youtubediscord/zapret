from __future__ import annotations

import inspect
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


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
        self.assertNotIn("_controller", page_source)
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

        init_source = inspect.getsource(ProfileSetupPageBase.__init__)
        request_source = inspect.getsource(ProfileSetupPageBase._request_profile_setup_payload)
        create_source = inspect.getsource(ProfileSetupPageBase.create_profile_setup_load_worker)
        feature_source = inspect.getsource(ProfileFeature)
        service_init_source = inspect.getsource(ProfilePresetService.__init__)
        setup_source = inspect.getsource(ProfilePresetService.get_profile_setup)
        setup_locked_source = inspect.getsource(ProfilePresetService._get_profile_setup_locked)

        self.assertIn("create_profile_setup_load_worker", init_source)
        self.assertIn("_create_profile_setup_load_worker_fn", init_source)
        self.assertIn("create_profile_setup_load_worker", request_source)
        self.assertNotIn("_controller.create_load_worker", request_source)
        self.assertIn("_create_profile_setup_load_worker_fn", create_source)
        self.assertIn("create_profile_setup_load_worker", feature_source)
        self.assertIn("_profile_setup_payload_cache", service_init_source)
        self.assertIn("_profile_list_lock", setup_source)
        self.assertIn("_profile_setup_cache_key", setup_locked_source)
        self.assertIn("_remember_profile_setup_payload", setup_locked_source)

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

    def test_profile_list_warmup_prepares_profile_setup_payloads(self) -> None:
        from app.feature_facades.profile import ProfileFeature
        from profile.service import ProfilePresetService

        warm_source = inspect.getsource(ProfileFeature.warm_profile_list)
        service_source = inspect.getsource(ProfilePresetService.warm_profile_setups)

        self.assertIn("service.warm_profile_setups", warm_source)
        self.assertIn('getattr(payload, "items"', warm_source)
        self.assertIn("get_profile_setup", service_source)
        self.assertIn("_yield_profile_payload_worker", service_source)

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
        move_source = inspect.getsource(PresetSetupPageBase._create_profile_move_worker)
        create_user_source = inspect.getsource(PresetSetupPageBase._create_user_profile_create_worker)
        update_user_source = inspect.getsource(PresetSetupPageBase._create_user_profile_update_worker)
        delete_user_source = inspect.getsource(PresetSetupPageBase._create_user_profile_delete_worker)

        self.assertIn("create_profile_list_load_worker", init_source)
        self.assertIn("create_profile_context_action_worker", init_source)
        self.assertIn("create_profile_move_worker", init_source)
        self.assertIn("create_user_profile_create_worker", init_source)
        self.assertIn("create_user_profile_update_worker", init_source)
        self.assertIn("create_user_profile_delete_worker", init_source)
        self.assertIn("create_profile_folder_action_worker", init_source)
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
        self.assertNotIn("self._profile.create_profile_move_worker", move_source)
        self.assertNotIn("ProfilePresetProfileMoveWorker(", move_source)
        self.assertNotIn("ProfileUserProfileCreateWorker(", create_user_source)
        self.assertNotIn("ProfileUserProfileUpdateWorker(", update_user_source)
        self.assertNotIn("ProfileUserProfileDeleteWorker(", delete_user_source)
        self.assertIn("_create_user_profile_create_worker_fn", create_user_source)
        self.assertIn("_create_user_profile_update_worker_fn", update_user_source)
        self.assertIn("_create_user_profile_delete_worker_fn", delete_user_source)

        profile_feature = Mock()
        kwargs = build_preset_setup_page_kwargs(
            page_name=PageName.ZAPRET2_PRESET_SETUP,
            profile_feature=profile_feature,
            open_profile_setup=Mock(),
            show_page=Mock(),
            ui_state_store=Mock(),
        )

        self.assertIs(kwargs["create_profile_list_load_worker"], profile_feature.create_profile_list_load_worker)
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
        self.assertNotIn("list_profiles", kwargs)
        self.assertNotIn("create_user_profile", kwargs)
        self.assertNotIn("update_user_profile", kwargs)
        self.assertNotIn("delete_user_profile", kwargs)
        self.assertNotIn("profile_feature", kwargs)

    def test_preset_setup_page_uses_worker_runtime_instead_of_manual_worker_fields(self) -> None:
        from profile.ui.preset_setup_page import PresetSetupPageBase

        init_source = inspect.getsource(PresetSetupPageBase.__init__)
        page_source = inspect.getsource(PresetSetupPageBase)
        worker_start_sources = (
            inspect.getsource(PresetSetupPageBase._request_profiles_payload),
            inspect.getsource(PresetSetupPageBase._request_profile_context_action)
            + inspect.getsource(PresetSetupPageBase._start_profile_context_action_worker),
            inspect.getsource(PresetSetupPageBase._request_user_profile_create),
            inspect.getsource(PresetSetupPageBase._request_user_profile_update),
            inspect.getsource(PresetSetupPageBase._request_user_profile_delete),
            inspect.getsource(PresetSetupPageBase._request_profile_move)
            + inspect.getsource(PresetSetupPageBase._start_profile_move_worker),
            inspect.getsource(PresetSetupPageBase._request_profile_folder_action),
        )

        self.assertIn("OneShotWorkerRuntime", init_source)
        for attr in (
            "_profile_load_runtime",
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
