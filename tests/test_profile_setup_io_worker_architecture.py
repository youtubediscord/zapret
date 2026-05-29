from __future__ import annotations

import inspect
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
        self.assertNotIn("self._controller.load_list_file_editor_state", run_source)

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


if __name__ == "__main__":
    unittest.main()
