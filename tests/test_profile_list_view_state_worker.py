from __future__ import annotations

import inspect
import unittest


class ProfileListViewStateWorkerTests(unittest.TestCase):
    def test_profile_list_worker_builds_view_state_off_gui_thread(self) -> None:
        from profile.profile_list_loader import ProfileListLoadWorker

        init_source = inspect.getsource(ProfileListLoadWorker.__init__)
        run_source = inspect.getsource(ProfileListLoadWorker.run)

        self.assertIn("build_view_state", init_source)
        self.assertIn("self._build_view_state", run_source)
        self.assertIn("ProfileListLoadResult", run_source)

    def test_profile_feature_builds_profile_list_state_without_ui_model_import(self) -> None:
        from app.feature_facades.profile import ProfileFeature

        warm_source = inspect.getsource(ProfileFeature.warm_profile_list)
        worker_source = inspect.getsource(ProfileFeature.create_profile_list_load_worker)

        self.assertIn("profile.list_view_state", warm_source)
        self.assertIn("profile.list_view_state", worker_source)
        self.assertNotIn("profile.ui.profile_list_model", warm_source)
        self.assertNotIn("profile.ui.profile_list_model", worker_source)

    def test_preset_setup_page_applies_worker_view_state_to_profile_list(self) -> None:
        from profile.ui.preset_setup_page import PresetSetupPageBase

        apply_source = inspect.getsource(PresetSetupPageBase._apply_payload)

        self.assertIn("view_state", apply_source)
        self.assertIn("apply_view_state", apply_source)
        self.assertNotIn("profiles_list.build_profiles(tuple(payload.items))", apply_source)

    def test_preset_setup_page_does_not_read_cached_profile_payload_in_gui(self) -> None:
        from profile.ui.preset_setup_page import PresetSetupPageBase
        from ui.page_deps.presets import build_preset_setup_page_kwargs

        init_source = inspect.getsource(PresetSetupPageBase.__init__)
        request_source = inspect.getsource(PresetSetupPageBase._request_profiles_payload)
        page_source = inspect.getsource(PresetSetupPageBase)
        deps_source = inspect.getsource(build_preset_setup_page_kwargs)

        self.assertNotIn("get_cached_profile_list", init_source)
        self.assertNotIn("get_cached_profile_list", request_source)
        self.assertNotIn("_apply_cached_profile_payload", page_source)
        self.assertNotIn("get_cached_profile_list", deps_source)


if __name__ == "__main__":
    unittest.main()
