from __future__ import annotations

import inspect
import unittest


class ProfileSetupWorkerArchitectureTests(unittest.TestCase):
    def test_context_action_worker_receives_narrow_profile_service(self) -> None:
        from profile.profile_setup_loader import ProfilePresetProfileActionWorker

        init_source = inspect.getsource(ProfilePresetProfileActionWorker.__init__)
        run_source = inspect.getsource(ProfilePresetProfileActionWorker.run)

        self.assertIn("profile_service", init_source)
        self.assertIn("self._service", init_source)
        self.assertNotIn("self._profile", init_source)
        self.assertNotIn("launch_method", init_source)
        self.assertIn("self._service.set_profile_enabled", run_source)
        self.assertIn("self._service.duplicate_profile", run_source)
        self.assertIn("self._service.delete_profile", run_source)

    def test_profile_move_worker_receives_narrow_profile_service(self) -> None:
        from profile.profile_setup_loader import ProfilePresetProfileMoveWorker

        init_source = inspect.getsource(ProfilePresetProfileMoveWorker.__init__)
        run_source = inspect.getsource(ProfilePresetProfileMoveWorker.run)

        self.assertIn("profile_service", init_source)
        self.assertIn("self._service", init_source)
        self.assertNotIn("self._profile", init_source)
        self.assertNotIn("launch_method", init_source)
        self.assertIn("self._service.move_profile_before", run_source)
        self.assertIn("self._service.move_profile_after", run_source)
        self.assertIn("self._service.move_profile_to_end", run_source)
        self.assertIn("self._service.move_profile_to_folder", run_source)

    def test_preset_setup_page_asks_feature_to_create_context_workers(self) -> None:
        from profile.ui.preset_setup_page import PresetSetupPageBase

        action_source = inspect.getsource(PresetSetupPageBase._create_profile_context_action_worker)
        move_source = inspect.getsource(PresetSetupPageBase._create_profile_move_worker)

        self.assertIn("self._profile.create_profile_context_action_worker", action_source)
        self.assertNotIn("ProfilePresetProfileActionWorker(", action_source)
        self.assertIn("self._profile.create_profile_move_worker", move_source)
        self.assertNotIn("ProfilePresetProfileMoveWorker(", move_source)


if __name__ == "__main__":
    unittest.main()
