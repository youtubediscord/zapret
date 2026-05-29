from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class TrayOpacityWorkerTests(unittest.TestCase):
    def test_tray_opacity_save_runs_through_worker(self) -> None:
        from app.feature_facades.tray import TrayFeature
        import tray_commands

        command_source = inspect.getsource(tray_commands.apply_window_opacity)
        feature_source = inspect.getsource(TrayFeature.apply_window_opacity)
        request_source = inspect.getsource(TrayFeature._request_window_opacity_save)

        self.assertNotIn("settings.store", command_source)
        self.assertNotIn("set_window_opacity as save_window_opacity", command_source)
        self.assertIn("_request_window_opacity_save", feature_source)
        self.assertIn("_opacity_save_pending", request_source)

    def test_tray_opacity_applies_window_immediately_and_starts_save_worker(self) -> None:
        from app.feature_facades.tray import TrayFeature

        class FakeWorker:
            def __init__(self) -> None:
                self.finished = SimpleNamespace(connect=Mock())
                self.started = False

            def isRunning(self) -> bool:
                return False

            def start(self) -> None:
                self.started = True

        worker = FakeWorker()
        deps = SimpleNamespace(set_window_opacity=Mock())
        feature = TrayFeature(
            _deps=deps,
            _runtime_feature=SimpleNamespace(),
            _telegram_proxy_feature=SimpleNamespace(),
        )
        commands = SimpleNamespace(apply_window_opacity=Mock())

        with (
            patch.object(TrayFeature, "_commands", staticmethod(lambda: commands)),
            patch.object(TrayFeature, "create_opacity_save_worker", return_value=worker) as create_worker,
        ):
            feature.apply_window_opacity(72)

        commands.apply_window_opacity.assert_called_once_with(
            set_window_opacity=deps.set_window_opacity,
            value=72,
        )
        create_worker.assert_called_once_with(72)
        self.assertTrue(worker.started)

    def test_github_api_removal_toggle_starts_worker_instead_of_direct_command(self) -> None:
        from app.feature_facades.tray import TrayFeature
        from tray_workers import TrayGithubApiRemovalToggleWorker

        class FakeWorker:
            def __init__(self) -> None:
                self.completed = SimpleNamespace(connect=Mock())
                self.failed = SimpleNamespace(connect=Mock())
                self.finished = SimpleNamespace(connect=Mock())
                self.started = False

            def isRunning(self) -> bool:
                return False

            def start(self) -> None:
                self.started = True

        worker = FakeWorker()
        status_callback = Mock()
        deps = SimpleNamespace(set_window_opacity=Mock())
        feature = TrayFeature(
            _deps=deps,
            _runtime_feature=SimpleNamespace(),
            _telegram_proxy_feature=SimpleNamespace(),
        )
        commands = SimpleNamespace(toggle_github_api_removal=Mock(return_value=True))

        with (
            patch.object(TrayFeature, "_commands", staticmethod(lambda: commands)),
            patch.object(
                TrayFeature,
                "create_github_api_removal_toggle_worker",
                return_value=worker,
            ) as create_worker,
        ):
            queued = feature.toggle_github_api_removal(status_callback=status_callback)

        self.assertTrue(queued)
        commands.toggle_github_api_removal.assert_not_called()
        create_worker.assert_called_once_with(parent=None)
        self.assertTrue(worker.started)

        feature_source = inspect.getsource(TrayFeature.create_github_api_removal_toggle_worker)
        worker_init_signature = inspect.signature(TrayGithubApiRemovalToggleWorker.__init__)
        worker_source = inspect.getsource(TrayGithubApiRemovalToggleWorker.run)

        self.assertIn("toggle_github_api_removal=self._commands().toggle_github_api_removal", feature_source)
        self.assertIn("toggle_github_api_removal", worker_init_signature.parameters)
        self.assertIn("self._toggle_github_api_removal", worker_source)
        self.assertNotIn("import tray_commands", worker_source)


if __name__ == "__main__":
    unittest.main()
