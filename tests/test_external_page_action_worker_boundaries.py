from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

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

    def test_support_open_actions_are_queued_while_worker_runs(self) -> None:
        class _Runtime:
            def is_running(self) -> bool:
                return True

        page = SupportPage.__new__(SupportPage)
        page._support_open_runtime = _Runtime()
        page._support_open_pending = []
        page._start_support_open_action_worker = Mock()
        first_action = Mock()
        second_action = Mock()

        SupportPage._request_support_open_action(
            page,
            "telegram",
            first_action,
            error_key="telegram.error",
            error_default="telegram {error}",
        )
        SupportPage._request_support_open_action(
            page,
            "discord",
            second_action,
            error_key="discord.error",
            error_default="discord {error}",
        )

        self.assertEqual(
            page._support_open_pending,
            [
                ("telegram", first_action, "telegram.error", "telegram {error}"),
                ("discord", second_action, "discord.error", "discord {error}"),
            ],
        )
        page._start_support_open_action_worker.assert_not_called()

    def test_duplicate_support_open_action_is_queued_once(self) -> None:
        class _Runtime:
            def is_running(self) -> bool:
                return True

        page = SupportPage.__new__(SupportPage)
        page._support_open_runtime = _Runtime()
        page._support_open_pending = []
        page._start_support_open_action_worker = Mock()
        action = Mock()

        SupportPage._request_support_open_action(
            page,
            "telegram",
            action,
            error_key="telegram.error",
            error_default="telegram {error}",
        )
        SupportPage._request_support_open_action(
            page,
            "telegram",
            action,
            error_key="telegram.error",
            error_default="telegram {error}",
        )

        self.assertEqual(
            page._support_open_pending,
            [("telegram", action, "telegram.error", "telegram {error}")],
        )
        page._start_support_open_action_worker.assert_not_called()

    def test_support_open_worker_finished_schedules_next_queued_action(self) -> None:
        import ui.pages.support_page as support_page

        page = SupportPage.__new__(SupportPage)
        first_action = Mock()
        second_action = Mock()
        page._support_open_pending = [
            ("telegram", first_action, "telegram.error", "telegram {error}"),
            ("discord", second_action, "discord.error", "discord {error}"),
        ]
        page._start_support_open_action_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(support_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            SupportPage._on_support_open_action_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_support_open_action_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_support_open_action_worker.assert_called_once_with(
            "telegram",
            first_action,
            "telegram.error",
            "telegram {error}",
        )
        self.assertEqual(
            page._support_open_pending,
            [("discord", second_action, "discord.error", "discord {error}")],
        )

    def test_support_open_scheduled_start_queues_next_action(self) -> None:
        import ui.pages.support_page as support_page

        page = SupportPage.__new__(SupportPage)
        page._support_open_start_scheduled = False
        page._support_open_pending = []
        page._start_support_open_action_worker = Mock()
        first_action = Mock()
        second_action = Mock()
        first = ("telegram", first_action, "telegram.error", "telegram {error}")
        second = ("discord", second_action, "discord.error", "discord {error}")
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(support_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            SupportPage._schedule_support_open_action_worker_start(page, first)
            SupportPage._schedule_support_open_action_worker_start(page, second)

        single_shot.assert_called_once()
        self.assertEqual(page._support_open_pending, [second])

        single_shot.call_args.args[1]()

        page._start_support_open_action_worker.assert_called_once_with(
            "telegram",
            first_action,
            "telegram.error",
            "telegram {error}",
        )
        self.assertEqual(page._support_open_pending, [second])

    def test_about_open_actions_are_queued_while_worker_runs(self) -> None:
        class _Runtime:
            def is_running(self) -> bool:
                return True

        page = AboutPage.__new__(AboutPage)
        page._about_open_runtime = _Runtime()
        page._about_open_pending = []
        page._start_about_open_action_worker = Mock()
        first_action = Mock()
        second_action = Mock()

        AboutPage._request_about_open_action(
            page,
            "telegram",
            first_action,
            error_default="telegram {error}",
        )
        AboutPage._request_about_open_action(
            page,
            "github",
            second_action,
            error_default="github {error}",
            raw_error_message="raw",
        )

        self.assertEqual(
            page._about_open_pending,
            [
                ("telegram", first_action, "telegram {error}", ""),
                ("github", second_action, "github {error}", "raw"),
            ],
        )
        page._start_about_open_action_worker.assert_not_called()

    def test_duplicate_about_open_action_is_queued_once(self) -> None:
        class _Runtime:
            def is_running(self) -> bool:
                return True

        page = AboutPage.__new__(AboutPage)
        page._about_open_runtime = _Runtime()
        page._about_open_pending = []
        page._start_about_open_action_worker = Mock()
        action = Mock()

        AboutPage._request_about_open_action(
            page,
            "telegram",
            action,
            error_default="telegram {error}",
        )
        AboutPage._request_about_open_action(
            page,
            "telegram",
            action,
            error_default="telegram {error}",
        )

        self.assertEqual(page._about_open_pending, [("telegram", action, "telegram {error}", "")])
        page._start_about_open_action_worker.assert_not_called()

    def test_about_open_worker_finished_schedules_next_queued_action(self) -> None:
        import ui.pages.about_page as about_page

        page = AboutPage.__new__(AboutPage)
        page._cleanup_in_progress = False
        first_action = Mock()
        second_action = Mock()
        page._about_open_pending = [
            ("telegram", first_action, "telegram {error}", ""),
            ("github", second_action, "github {error}", "raw"),
        ]
        page._start_about_open_action_worker = Mock()
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(about_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            AboutPage._on_about_open_action_worker_finished(page, object())

        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 0)
        page._start_about_open_action_worker.assert_not_called()

        single_shot.call_args.args[1]()

        page._start_about_open_action_worker.assert_called_once_with(
            "telegram",
            first_action,
            "telegram {error}",
            "",
        )
        self.assertEqual(
            page._about_open_pending,
            [("github", second_action, "github {error}", "raw")],
        )

    def test_about_open_scheduled_start_queues_next_action(self) -> None:
        import ui.pages.about_page as about_page

        page = AboutPage.__new__(AboutPage)
        page._cleanup_in_progress = False
        page._about_open_start_scheduled = False
        page._about_open_pending = []
        page._start_about_open_action_worker = Mock()
        first_action = Mock()
        second_action = Mock()
        first = ("telegram", first_action, "telegram {error}", "")
        second = ("github", second_action, "github {error}", "raw")
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with patch.object(about_page, "QTimer", SimpleNamespace(singleShot=single_shot), create=True):
            AboutPage._schedule_about_open_action_worker_start(page, first)
            AboutPage._schedule_about_open_action_worker_start(page, second)

        single_shot.assert_called_once()
        self.assertEqual(page._about_open_pending, [second])

        single_shot.call_args.args[1]()

        page._start_about_open_action_worker.assert_called_once_with(
            "telegram",
            first_action,
            "telegram {error}",
            "",
        )
        self.assertEqual(page._about_open_pending, [second])


if __name__ == "__main__":
    unittest.main()
