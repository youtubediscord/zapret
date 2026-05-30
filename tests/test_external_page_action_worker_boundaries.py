from __future__ import annotations

import inspect
import unittest

from app.feature_facades.external import ExternalActionsFeature
from ui.page_composition import PAGE_DEPS_BUILDERS
from ui.page_deps import system as system_deps
from ui.pages.about_page import AboutPage
from ui.pages.support_page import SupportPage
from app.page_names import PageName


class ExternalPageActionWorkerBoundaryTests(unittest.TestCase):
    def test_support_and_about_use_external_action_worker_factory(self) -> None:
        feature_source = inspect.getsource(ExternalActionsFeature)
        support_source = inspect.getsource(SupportPage)
        about_source = inspect.getsource(AboutPage)
        support_deps_source = inspect.getsource(system_deps.build_support_page_kwargs)
        about_deps_source = inspect.getsource(system_deps.build_about_page_kwargs)

        self.assertIn("create_external_action_worker", feature_source)
        self.assertIn("external_actions", PAGE_DEPS_BUILDERS[PageName.SUPPORT].features)
        self.assertIn("external_actions", PAGE_DEPS_BUILDERS[PageName.ABOUT].features)
        self.assertIn("create_open_action_worker", support_deps_source)
        self.assertIn("external_actions_feature.create_external_action_worker", support_deps_source)
        self.assertIn("create_open_action_worker", about_deps_source)
        self.assertIn("external_actions_feature.create_external_action_worker", about_deps_source)
        self.assertIn("_create_support_open_action_worker", support_source)
        self.assertIn("_create_about_open_action_worker", about_source)
        self.assertNotIn("ui.pages.support_open_worker", support_source)
        self.assertNotIn("ui.pages.about_open_worker", about_source)


if __name__ == "__main__":
    unittest.main()
