from __future__ import annotations

import unittest
import inspect
from unittest.mock import Mock, patch

from app.feature_facades.updater import UpdaterFeature
from core.runtime.update_check_coordinator import UpdateCheckCoordinator
from ui.page_deps.types import UpdateRuntimeActions
from updater.update_page_runtime import UpdatePageRuntime


class UpdateCheckCoordinatorTests(unittest.TestCase):
    def test_page_runtime_does_not_keep_a_second_check_state(self) -> None:
        source = inspect.getsource(UpdatePageRuntime)

        self.assertNotIn("self._check_state", source)
        self.assertIn("current_update_check_snapshot", source)
        self.assertIn("subscribe_update_check", source)

    def test_only_one_check_can_be_active_and_token_owns_completion(self) -> None:
        coordinator = UpdateCheckCoordinator()

        startup_token = coordinator.begin(source="startup")

        self.assertIsInstance(startup_token, int)
        self.assertIsNone(coordinator.begin(source="manual"))
        self.assertFalse(
            coordinator.finish(
                {"has_update": False, "version": "1.0"},
                source="startup",
                token=int(startup_token) + 1,
            )
        )
        self.assertEqual(coordinator.snapshot().phase, "checking")

        self.assertTrue(
            coordinator.finish(
                {"has_update": False, "version": "1.0"},
                source="startup",
                token=startup_token,
            )
        )
        self.assertEqual(coordinator.snapshot().phase, "completed")
        self.assertFalse(
            coordinator.finish(
                {"has_update": True, "version": "2.0"},
                source="startup",
                token=startup_token,
            )
        )
        self.assertFalse(coordinator.snapshot().has_update)

    def test_late_subscriber_receives_completed_startup_result(self) -> None:
        coordinator = UpdateCheckCoordinator()
        token = coordinator.begin(source="startup")
        coordinator.finish(
            {
                "has_update": True,
                "version": "2.0",
                "release_notes": "Изменения",
            },
            source="startup",
            token=token,
        )
        received = []

        coordinator.subscribe(received.append, emit_initial=True)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].phase, "completed")
        self.assertTrue(received[0].has_update)
        self.assertEqual(received[0].version, "2.0")

    def test_delayed_startup_check_does_not_repeat_completed_manual_check(self) -> None:
        coordinator = UpdateCheckCoordinator()
        manual_token = coordinator.begin(source="manual")
        coordinator.finish(
            {"has_update": False, "version": "1.0"},
            source="manual",
            token=manual_token,
        )

        self.assertIsNone(coordinator.begin(source="startup"))
        self.assertEqual(coordinator.snapshot().source, "manual")
        self.assertEqual(coordinator.snapshot().phase, "completed")

    def test_cancelled_manual_check_does_not_block_delayed_startup_check(self) -> None:
        coordinator = UpdateCheckCoordinator()
        manual_token = coordinator.begin(source="manual")
        coordinator.finish(
            {
                "has_update": False,
                "skipped": True,
                "skip_reason": "Страница закрыта",
            },
            source="manual",
            token=manual_token,
        )

        self.assertIsInstance(coordinator.begin(source="startup"), int)
        self.assertEqual(coordinator.snapshot().source, "startup")
        self.assertEqual(coordinator.snapshot().phase, "checking")

    def test_skipped_check_keeps_time_of_last_real_check(self) -> None:
        coordinator = UpdateCheckCoordinator()
        token = coordinator.begin(source="startup")

        coordinator.finish(
            {
                "has_update": False,
                "version": "1.0",
                "skipped": True,
                "skip_reason": "Лимит частоты",
                "checked_at": 123.0,
            },
            source="startup",
            token=token,
        )

        snapshot = coordinator.snapshot()
        self.assertEqual(snapshot.phase, "skipped")
        self.assertEqual(snapshot.completed_at, 123.0)
        self.assertEqual(snapshot.message, "Лимит частоты")

    def test_page_opened_after_startup_uses_coordinator_result(self) -> None:
        feature = UpdaterFeature()
        token = feature.begin_update_check(source="startup")
        feature.finish_update_check(
            {
                "has_update": False,
                "version": "21.1.5.5",
                "release_notes": "",
                "error": None,
            },
            source="startup",
            token=token,
        )
        view = Mock()
        view.is_update_download_in_progress.return_value = False
        runtime = UpdatePageRuntime(
            view,
            runtime_actions=UpdateRuntimeActions(
                is_any_running=Mock(return_value=False),
                shutdown_sync=Mock(),
                is_available=Mock(return_value=True),
                restart=Mock(),
            ),
            updater_feature=feature,
        )

        runtime.attach_update_check_coordinator()

        view.finish_checking.assert_called_once_with(False, "21.1.5.5")
        self.assertEqual(runtime._resolve_idle_view_decision().action, "checked_ago")

    def test_open_page_receives_live_startup_progress_and_result(self) -> None:
        feature = UpdaterFeature()
        view = Mock()
        view.is_update_download_in_progress.return_value = False
        runtime = UpdatePageRuntime(
            view,
            runtime_actions=UpdateRuntimeActions(
                is_any_running=Mock(return_value=False),
                shutdown_sync=Mock(),
                is_available=Mock(return_value=True),
                restart=Mock(),
            ),
            updater_feature=feature,
        )
        runtime.attach_update_check_coordinator()

        token = feature.begin_update_check(source="startup")
        feature.finish_update_check(
            {
                "has_update": False,
                "version": "21.1.5.5",
                "release_notes": "",
                "error": None,
            },
            source="startup",
            token=token,
        )

        view.start_checking.assert_called_once_with()
        view.finish_checking.assert_called_once_with(False, "21.1.5.5")

    def test_open_page_receives_startup_check_error(self) -> None:
        feature = UpdaterFeature()
        view = Mock()
        view.is_update_download_in_progress.return_value = False
        runtime = UpdatePageRuntime(
            view,
            runtime_actions=UpdateRuntimeActions(
                is_any_running=Mock(return_value=False),
                shutdown_sync=Mock(),
                is_available=Mock(return_value=True),
                restart=Mock(),
            ),
            updater_feature=feature,
        )
        runtime.attach_update_check_coordinator()

        token = feature.begin_update_check(source="startup")
        feature.finish_update_check(
            {
                "has_update": False,
                "version": "",
                "release_notes": "",
                "error": "Сервер обновлений недоступен",
            },
            source="startup",
            token=token,
        )

        view.show_update_check_error.assert_called_once_with("Сервер обновлений недоступен")
        view.finish_checking.assert_not_called()

    def test_page_uses_last_real_check_time_when_startup_check_is_skipped(self) -> None:
        feature = UpdaterFeature()
        token = feature.begin_update_check(source="startup")
        feature.finish_update_check(
            {
                "has_update": False,
                "version": "21.1.5.5",
                "skipped": True,
                "skip_reason": "Проверка недавно выполнялась",
                "checked_at": 123.0,
            },
            source="startup",
            token=token,
        )
        view = Mock()
        view.is_update_download_in_progress.return_value = False
        runtime = UpdatePageRuntime(
            view,
            runtime_actions=UpdateRuntimeActions(
                is_any_running=Mock(return_value=False),
                shutdown_sync=Mock(),
                is_available=Mock(return_value=True),
                restart=Mock(),
            ),
            updater_feature=feature,
        )

        with patch("updater.update_page_runtime.time.time", return_value=200.0):
            runtime.attach_update_check_coordinator()

        view.show_checked_ago.assert_called_once_with(77.0)


if __name__ == "__main__":
    unittest.main()
