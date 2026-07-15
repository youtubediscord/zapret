from __future__ import annotations

import inspect
import unittest


class ProfileSetupWorkerRuntimeArchitectureTests(unittest.TestCase):
    def test_profile_setup_save_workers_start_through_runtime(self) -> None:
        from profile.ui.profile_setup_page import ProfileSetupPageBase
        from profile.ui.profile_list_file_editor_controller import ProfileListFileEditorController
        from profile.ui.profile_setup_save_controllers import ProfileSetupSaveController
        from profile.ui.profile_setup_payload_controller import ProfileSetupPayloadController
        from profile.ui.profile_strategy_controller import ProfileStrategyController
        from profile.ui.profile_user_profile_controller import ProfileUserProfileController

        module_source = inspect.getsource(
            __import__("profile.ui.profile_setup_page", fromlist=[""])
        )
        init_source = inspect.getsource(ProfileSetupPageBase.__init__)
        payload_source = inspect.getsource(ProfileSetupPayloadController._request_profile_setup_payload)
        payload_start_source = inspect.getsource(ProfileSetupPayloadController._start_profile_setup_load_worker)
        list_load_source = inspect.getsource(ProfileListFileEditorController._request_list_file_editor_state)
        validation_request_source = inspect.getsource(ProfileListFileEditorController._request_list_file_validation)
        validation_start_source = inspect.getsource(ProfileListFileEditorController._start_list_file_validation_worker)
        save_request_source = inspect.getsource(ProfileListFileEditorController._request_list_file_save)
        save_start_source = inspect.getsource(ProfileListFileEditorController._start_list_file_save_worker)
        settings_request_source = inspect.getsource(ProfileSetupSaveController._request_settings_save)
        settings_start_source = inspect.getsource(ProfileSetupSaveController._start_settings_save_worker)
        raw_request_source = inspect.getsource(ProfileSetupSaveController._request_raw_profile_save)
        raw_start_source = inspect.getsource(ProfileSetupSaveController._start_raw_profile_save_worker)
        enabled_source = inspect.getsource(ProfileSetupPageBase._on_enabled_changed)
        enabled_start_source = inspect.getsource(ProfileSetupSaveController._start_enabled_save_worker)
        user_update_request_source = inspect.getsource(ProfileUserProfileController._request_user_profile_update)
        user_update_start_source = inspect.getsource(ProfileUserProfileController._start_user_profile_update_worker)
        user_delete_source = inspect.getsource(ProfileUserProfileController._request_user_profile_delete)
        user_delete_start_source = inspect.getsource(ProfileUserProfileController._start_user_profile_delete_worker)
        strategy_apply_request_source = inspect.getsource(ProfileStrategyController._request_strategy_apply)
        strategy_apply_start_source = inspect.getsource(ProfileStrategyController._start_strategy_apply_worker)
        strategy_feedback_request_source = inspect.getsource(ProfileStrategyController._request_strategy_feedback_save)
        strategy_feedback_start_source = inspect.getsource(ProfileStrategyController._start_strategy_feedback_save_worker)
        cleanup_source = inspect.getsource(ProfileSetupPageBase.cleanup)

        expected_runtimes = (
            "_setup_load_runtime",
            "_list_file_load_runtime",
            "_list_file_validation_runtime",
            "_list_file_save_runtime",
            "_settings_save_runtime",
            "_raw_profile_save_runtime",
            "_enabled_save_runtime",
            "_user_profile_update_runtime",
            "_user_profile_delete_runtime",
            "_strategy_apply_runtime",
            "_strategy_feedback_save_runtime",
        )
        for attr in expected_runtimes:
            self.assertIn(f"{attr} = OneShotWorkerRuntime()", init_source)
            self.assertIn(attr, module_source)

        self.assertIn("_PROFILE_SETUP_CLEANUP_RUNTIMES", cleanup_source)
        for attr, source in (
            ("_setup_load_runtime", payload_source + payload_start_source),
            ("_list_file_load_runtime", list_load_source),
            ("_list_file_validation_runtime", validation_request_source + validation_start_source),
            ("_list_file_save_runtime", save_request_source + save_start_source),
            ("_settings_save_runtime", settings_request_source + settings_start_source),
            ("_raw_profile_save_runtime", raw_request_source + raw_start_source),
            ("_enabled_save_runtime", enabled_source + enabled_start_source),
            ("_user_profile_update_runtime", user_update_request_source + user_update_start_source),
            ("_user_profile_delete_runtime", user_delete_source + user_delete_start_source),
            ("_strategy_apply_runtime", strategy_apply_request_source + strategy_apply_start_source),
            ("_strategy_feedback_save_runtime", strategy_feedback_request_source + strategy_feedback_start_source),
        ):
            self.assertIn(f'_worker_runtime("{attr}")', source)
            self.assertIn("start_qthread_worker", source)
            self.assertNotIn("worker.start()", source)

        for old_attr in (
            "self._setup_load_worker",
            "self._list_file_load_worker",
            "self._list_file_validation_worker",
            "self._list_file_save_worker",
            "self._settings_save_worker",
            "self._raw_profile_save_worker",
            "self._enabled_save_worker",
            "self._user_profile_update_worker",
            "self._user_profile_delete_worker",
            "self._strategy_apply_worker",
            "self._strategy_feedback_save_worker",
        ):
            self.assertNotIn(old_attr, init_source)


if __name__ == "__main__":
    unittest.main()
