from __future__ import annotations

import inspect
from types import SimpleNamespace
import unittest


class ProfileSetupIoWorkerArchitectureTests(unittest.TestCase):
    def test_setup_load_worker_receives_loader_function(self) -> None:
        from profile.profile_setup_loader import ProfileSetupLoadWorker

        init_source = inspect.getsource(ProfileSetupLoadWorker.__init__)
        run_source = inspect.getsource(ProfileSetupLoadWorker.run)

        self.assertIn("load_profile", init_source)
        self.assertIn("self._load_profile", init_source)
        self.assertNotIn("self._controller", init_source)
        self.assertIn("self._load_profile(self._profile_key)", run_source)
        self.assertNotIn("self._controller.load", run_source)

    def test_list_file_load_worker_receives_loader_function(self) -> None:
        from profile.profile_setup_loader import ProfileListFileLoadWorker

        init_source = inspect.getsource(ProfileListFileLoadWorker.__init__)
        run_source = inspect.getsource(ProfileListFileLoadWorker.run)

        self.assertIn("load_state", init_source)
        self.assertIn("self._load_state", init_source)
        self.assertNotIn("self._controller", init_source)
        self.assertIn("self._load_state(", run_source)
        self.assertIn("ProfileListFileLoadResult(", run_source)
        self.assertNotIn("self._controller.load_list_file_editor_state", run_source)

    def test_list_file_load_result_keeps_profile_and_file_identity(self) -> None:
        from profile.profile_setup_loader import ProfileListFileLoadResult

        state = SimpleNamespace(display_path="lists/facebook.txt")

        result = ProfileListFileLoadResult(
            profile_key="profile-facebook",
            filter_kind="hostlist",
            filter_value="lists/facebook.txt",
            state=state,
        )

        self.assertEqual(result.profile_key, "profile-facebook")
        self.assertEqual(result.filter_kind, "hostlist")
        self.assertEqual(result.filter_value, "lists/facebook.txt")
        self.assertIs(result.state, state)

    def test_list_file_validation_worker_receives_validator_function(self) -> None:
        from profile.profile_setup_loader import ProfileListFileValidationWorker

        init_source = inspect.getsource(ProfileListFileValidationWorker.__init__)
        run_source = inspect.getsource(ProfileListFileValidationWorker.run)

        self.assertIn("validate_text", init_source)
        self.assertIn("self._validate_text", init_source)
        self.assertNotIn("self._controller", init_source)
        self.assertIn("self._validate_text(", run_source)
        self.assertNotIn("self._controller.validate_list_file_text", run_source)

    def test_list_file_save_worker_receives_save_and_load_functions(self) -> None:
        from profile.profile_setup_loader import ProfileListFileSaveWorker

        init_source = inspect.getsource(ProfileListFileSaveWorker.__init__)
        run_source = inspect.getsource(ProfileListFileSaveWorker.run)

        self.assertIn("save_text", init_source)
        self.assertIn("load_profile", init_source)
        self.assertIn("self._save_text", init_source)
        self.assertIn("self._load_profile", init_source)
        self.assertNotIn("self._controller", init_source)
        self.assertIn("self._save_text(", run_source)
        self.assertIn("self._load_profile(self._profile_key)", run_source)
        self.assertNotIn("self._controller.save_list_file_text", run_source)
        self.assertNotIn("self._controller.load", run_source)

    def test_settings_save_worker_receives_save_and_load_functions(self) -> None:
        from profile.profile_setup_loader import ProfileSettingsSaveWorker

        init_source = inspect.getsource(ProfileSettingsSaveWorker.__init__)
        run_source = inspect.getsource(ProfileSettingsSaveWorker.run)

        self.assertIn("save_settings", init_source)
        self.assertIn("load_profile", init_source)
        self.assertIn("self._save_settings", init_source)
        self.assertIn("self._load_profile", init_source)
        self.assertNotIn("self._controller", init_source)
        self.assertIn("self._save_settings(", run_source)
        self.assertIn("self._load_profile(", run_source)
        self.assertNotIn("self._controller.save_winws2_settings", run_source)
        self.assertNotIn("self._controller.load", run_source)

    def test_raw_text_save_worker_receives_save_and_load_functions(self) -> None:
        from profile.profile_setup_loader import ProfileRawTextSaveWorker

        init_source = inspect.getsource(ProfileRawTextSaveWorker.__init__)
        run_source = inspect.getsource(ProfileRawTextSaveWorker.run)

        self.assertIn("save_raw_text", init_source)
        self.assertIn("load_profile", init_source)
        self.assertIn("self._save_raw_text", init_source)
        self.assertIn("self._load_profile", init_source)
        self.assertNotIn("self._controller", init_source)
        self.assertIn("self._save_raw_text(", run_source)
        self.assertIn("self._load_profile(", run_source)
        self.assertNotIn("self._controller.save_raw_profile_text", run_source)
        self.assertNotIn("self._controller.load", run_source)

    def test_enabled_save_worker_receives_save_and_load_functions(self) -> None:
        from profile.profile_setup_loader import ProfileEnabledSaveWorker

        init_source = inspect.getsource(ProfileEnabledSaveWorker.__init__)
        run_source = inspect.getsource(ProfileEnabledSaveWorker.run)

        self.assertIn("set_enabled", init_source)
        self.assertIn("load_profile", init_source)
        self.assertIn("self._set_enabled", init_source)
        self.assertIn("self._load_profile", init_source)
        self.assertNotIn("self._controller", init_source)
        self.assertIn("self._set_enabled(", run_source)
        self.assertIn("self._load_profile(", run_source)
        self.assertNotIn("self._controller.set_enabled", run_source)
        self.assertNotIn("self._controller.load", run_source)

    def test_strategy_apply_worker_receives_apply_and_load_functions(self) -> None:
        from profile.profile_setup_loader import ProfileStrategyApplyWorker

        init_source = inspect.getsource(ProfileStrategyApplyWorker.__init__)
        run_source = inspect.getsource(ProfileStrategyApplyWorker.run)

        self.assertIn("apply_strategy", init_source)
        self.assertIn("load_profile", init_source)
        self.assertIn("self._apply_strategy", init_source)
        self.assertIn("self._load_profile", init_source)
        self.assertNotIn("self._controller", init_source)
        self.assertIn("self._apply_strategy(", run_source)
        self.assertIn("self._load_profile(", run_source)
        self.assertNotIn("self._controller.apply_strategy", run_source)
        self.assertNotIn("self._controller.load", run_source)

    def test_strategy_feedback_worker_receives_save_function(self) -> None:
        from profile.profile_setup_loader import ProfileStrategyFeedbackSaveWorker

        init_source = inspect.getsource(ProfileStrategyFeedbackSaveWorker.__init__)
        run_source = inspect.getsource(ProfileStrategyFeedbackSaveWorker.run)

        self.assertIn("save_feedback", init_source)
        self.assertIn("self._save_feedback", init_source)
        self.assertNotIn("self._controller", init_source)
        self.assertIn("self._save_feedback(", run_source)
        self.assertNotIn("self._controller.set_strategy_feedback", run_source)

    def test_user_profile_create_worker_receives_create_and_lookup_functions(self) -> None:
        from profile.profile_setup_loader import ProfileUserProfileCreateWorker

        init_source = inspect.getsource(ProfileUserProfileCreateWorker.__init__)
        run_source = inspect.getsource(ProfileUserProfileCreateWorker.run)

        self.assertIn("create_user_profile", init_source)
        self.assertIn("load_user_profile_items", init_source)
        self.assertIn("self._create_user_profile", init_source)
        self.assertIn("self._load_user_profile_items", init_source)
        self.assertNotIn("self._profile", init_source)
        self.assertNotIn("launch_method", init_source)
        self.assertIn("self._create_user_profile(", run_source)
        self.assertIn("self._load_user_profile_items(", run_source)
        self.assertNotIn("self._profile.create_user_profile", run_source)

    def test_user_profile_update_worker_receives_update_and_lookup_functions(self) -> None:
        from profile.profile_setup_loader import ProfileUserProfileUpdateWorker

        init_source = inspect.getsource(ProfileUserProfileUpdateWorker.__init__)
        run_source = inspect.getsource(ProfileUserProfileUpdateWorker.run)

        self.assertIn("update_user_profile", init_source)
        self.assertIn("load_user_profile_items", init_source)
        self.assertIn("self._update_user_profile", init_source)
        self.assertIn("self._load_user_profile_items", init_source)
        self.assertNotIn("self._controller", init_source)
        self.assertNotIn("launch_method", init_source)
        self.assertIn("self._update_user_profile(", run_source)
        self.assertIn("self._load_user_profile_items(", run_source)
        self.assertNotIn("self._controller.update_user_profile", run_source)

    def test_user_profile_delete_worker_receives_delete_function(self) -> None:
        from profile.profile_setup_loader import ProfileUserProfileDeleteWorker

        init_source = inspect.getsource(ProfileUserProfileDeleteWorker.__init__)
        run_source = inspect.getsource(ProfileUserProfileDeleteWorker.run)

        self.assertIn("delete_user_profile", init_source)
        self.assertIn("self._delete_user_profile", init_source)
        self.assertNotIn("self._controller", init_source)
        self.assertIn("self._delete_user_profile(", run_source)
        self.assertNotIn("self._controller.delete_user_profile", run_source)


if __name__ == "__main__":
    unittest.main()
