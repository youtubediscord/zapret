from __future__ import annotations

import inspect
import unittest
from unittest.mock import Mock


class ProfileSetupWorkerArchitectureTests(unittest.TestCase):
    def test_profile_setup_page_receives_actions_instead_of_profile_feature(self) -> None:
        from profile.setup_controller import ProfileSetupController
        from profile.ui.profile_setup_page import ProfileSetupPageBase
        from ui.navigation_pages import PageName
        from ui.page_deps.presets import build_profile_setup_page_kwargs

        init_source = inspect.getsource(ProfileSetupPageBase.__init__)
        controller_init_source = inspect.getsource(ProfileSetupController.__init__)
        controller_source = inspect.getsource(ProfileSetupController)

        self.assertIn("profile_setup_actions", init_source)
        self.assertNotIn("profile_feature", init_source)
        self.assertIn("profile_setup_actions", controller_init_source)
        self.assertNotIn("profile_feature", controller_init_source)
        self.assertNotIn("self._profile", controller_source)

        profile_feature = Mock()
        kwargs = build_profile_setup_page_kwargs(
            page_name=PageName.ZAPRET2_PROFILE_SETUP,
            profile_feature=profile_feature,
            show_page=Mock(),
            on_profile_setup_changed=Mock(),
        )

        self.assertIn("profile_setup_actions", kwargs)
        self.assertNotIn("profile_feature", kwargs)
        actions = kwargs["profile_setup_actions"]
        self.assertIs(actions.get_profile_setup, profile_feature.get_profile_setup)
        self.assertIs(actions.apply_strategy_to_profile, profile_feature.apply_strategy_to_profile)
        self.assertIs(actions.update_profile_raw_text, profile_feature.update_profile_raw_text)

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

        self.assertIn("get_cached_profile_list", init_source)
        self.assertIn("list_profiles", init_source)
        self.assertIn("create_user_profile", init_source)
        self.assertIn("update_user_profile", init_source)
        self.assertIn("delete_user_profile", init_source)
        self.assertIn("create_profile_list_load_worker", init_source)
        self.assertIn("create_profile_context_action_worker", init_source)
        self.assertIn("create_profile_move_worker", init_source)
        self.assertNotIn("profile_feature", init_source)
        self.assertNotIn("self._profile =", page_source)
        self.assertNotIn("self._profile.", page_source)
        self.assertNotIn("self._profile.create_profile_context_action_worker", action_source)
        self.assertNotIn("ProfilePresetProfileActionWorker(", action_source)
        self.assertNotIn("self._profile.create_profile_move_worker", move_source)
        self.assertNotIn("ProfilePresetProfileMoveWorker(", move_source)

        profile_feature = Mock()
        kwargs = build_preset_setup_page_kwargs(
            page_name=PageName.ZAPRET2_PRESET_SETUP,
            profile_feature=profile_feature,
            open_profile_setup=Mock(),
            show_page=Mock(),
            ui_state_store=Mock(),
        )

        self.assertIs(kwargs["get_cached_profile_list"], profile_feature.get_cached_profile_list)
        self.assertIs(kwargs["list_profiles"], profile_feature.list_profiles)
        self.assertIs(kwargs["create_user_profile"], profile_feature.create_user_profile)
        self.assertIs(kwargs["update_user_profile"], profile_feature.update_user_profile)
        self.assertIs(kwargs["delete_user_profile"], profile_feature.delete_user_profile)
        self.assertIs(kwargs["create_profile_list_load_worker"], profile_feature.create_profile_list_load_worker)
        self.assertIs(
            kwargs["create_profile_context_action_worker"],
            profile_feature.create_profile_context_action_worker,
        )
        self.assertIs(kwargs["create_profile_move_worker"], profile_feature.create_profile_move_worker)
        self.assertNotIn("profile_feature", kwargs)


if __name__ == "__main__":
    unittest.main()
