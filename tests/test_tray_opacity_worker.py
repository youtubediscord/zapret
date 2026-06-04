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
        start_source = inspect.getsource(TrayFeature._start_window_opacity_save_worker)

        self.assertNotIn("settings.store", command_source)
        self.assertNotIn("set_window_opacity as save_window_opacity", command_source)
        self.assertIn("_request_window_opacity_save", feature_source)
        self.assertIn("_opacity_save_runtime", request_source)
        self.assertIn("_opacity_save_pending", request_source)
        self.assertIn("start_qthread_worker", start_source)
        self.assertNotIn("worker.start()", start_source)

    def test_pending_tray_opacity_save_restarts_after_event_loop_turn(self) -> None:
        import app.feature_facades.tray as tray
        from app.feature_facades.tray import TrayFeature

        feature = TrayFeature(
            _deps=SimpleNamespace(set_window_opacity=Mock()),
            _runtime_feature=SimpleNamespace(),
            _telegram_proxy_feature=SimpleNamespace(),
        )
        feature._opacity_save_pending = 64
        feature._opacity_save_runtime_worker = None
        single_shot = Mock(side_effect=lambda _delay, _callback: None)

        with (
            patch.object(tray, "QTimer", SimpleNamespace(singleShot=single_shot), create=True),
            patch.object(TrayFeature, "_start_window_opacity_save_worker") as start_worker,
        ):
            feature._on_window_opacity_save_worker_finished(object())

            single_shot.assert_called_once()
            self.assertEqual(single_shot.call_args.args[0], 0)
            start_worker.assert_not_called()

            single_shot.call_args.args[1]()

            start_worker.assert_called_once_with(64)

    def test_stale_tray_opacity_save_finish_does_not_restart_pending_save(self) -> None:
        import app.feature_facades.tray as tray
        from app.feature_facades.tray import TrayFeature

        current_worker = object()
        feature = TrayFeature(
            _deps=SimpleNamespace(set_window_opacity=Mock()),
            _runtime_feature=SimpleNamespace(),
            _telegram_proxy_feature=SimpleNamespace(),
        )
        feature._opacity_save_runtime_worker = current_worker
        feature._opacity_save_pending = 64
        single_shot = Mock()

        with (
            patch.object(tray, "QTimer", SimpleNamespace(singleShot=single_shot), create=True),
            patch.object(TrayFeature, "_start_window_opacity_save_worker") as start_worker,
        ):
            feature._on_window_opacity_save_worker_finished(object())

        single_shot.assert_not_called()
        start_worker.assert_not_called()
        self.assertEqual(feature._opacity_save_pending, 64)
        self.assertIs(feature._opacity_save_runtime_worker, current_worker)

    def test_tray_opacity_applies_window_immediately_and_starts_save_worker(self) -> None:
        from app.feature_facades.tray import TrayFeature

        class FakeWorker:
            def __init__(self) -> None:
                self.finished = SimpleNamespace(connect=Mock())
                self.deleteLater = Mock()
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
                self.deleteLater = Mock()
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

        toggle_source = inspect.getsource(TrayFeature.toggle_github_api_removal)
        feature_source = inspect.getsource(TrayFeature.create_github_api_removal_toggle_worker)
        worker_init_signature = inspect.signature(TrayGithubApiRemovalToggleWorker.__init__)
        worker_source = inspect.getsource(TrayGithubApiRemovalToggleWorker.run)

        self.assertIn("_github_api_removal_toggle_runtime", toggle_source)
        self.assertIn("start_qthread_worker", toggle_source)
        self.assertNotIn("worker.start()", toggle_source)
        self.assertIn("toggle_github_api_removal=self._commands().toggle_github_api_removal", feature_source)
        self.assertIn("toggle_github_api_removal", worker_init_signature.parameters)
        self.assertIn("self._toggle_github_api_removal", worker_source)
        self.assertNotIn("import tray_commands", worker_source)

    def test_discord_restart_toggle_starts_worker_instead_of_direct_command(self) -> None:
        from app.feature_facades.tray import TrayFeature
        from tray_workers import TrayDiscordRestartToggleWorker

        class FakeWorker:
            def __init__(self) -> None:
                self.completed = SimpleNamespace(connect=Mock())
                self.failed = SimpleNamespace(connect=Mock())
                self.finished = SimpleNamespace(connect=Mock())
                self.deleteLater = Mock()
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
        commands = SimpleNamespace(
            get_discord_restart_enabled=Mock(return_value=False),
            set_discord_restart_enabled=Mock(return_value=True),
            toggle_discord_restart=Mock(),
        )

        with (
            patch.object(TrayFeature, "_commands", staticmethod(lambda: commands)),
            patch.object(
                TrayFeature,
                "create_discord_restart_toggle_worker",
                return_value=worker,
            ) as create_worker,
        ):
            queued = feature.toggle_discord_restart(status_callback=status_callback)

        self.assertTrue(queued)
        commands.toggle_discord_restart.assert_not_called()
        create_worker.assert_called_once_with(enabled=True, parent=None)
        self.assertTrue(worker.started)

        toggle_source = inspect.getsource(TrayFeature.toggle_discord_restart)
        feature_source = inspect.getsource(TrayFeature.create_discord_restart_toggle_worker)
        worker_init_signature = inspect.signature(TrayDiscordRestartToggleWorker.__init__)
        worker_source = inspect.getsource(TrayDiscordRestartToggleWorker.run)

        self.assertIn("_discord_restart_toggle_runtime", toggle_source)
        self.assertIn("start_qthread_worker", toggle_source)
        self.assertNotIn("worker.start()", toggle_source)
        self.assertNotIn("_commands().toggle_discord_restart", toggle_source)
        self.assertIn("set_discord_restart_enabled=self._commands().set_discord_restart_enabled", feature_source)
        self.assertIn("set_discord_restart_enabled", worker_init_signature.parameters)
        self.assertIn("self._set_discord_restart_enabled", worker_source)
        self.assertNotIn("import tray_commands", worker_source)

    def test_discord_restart_commands_do_not_keep_legacy_qmessagebox_toggle(self) -> None:
        import discord.discord_restart as discord_restart

        source = inspect.getsource(discord_restart)

        self.assertFalse(hasattr(discord_restart, "toggle_discord_restart"))
        self.assertNotIn("QMessageBox", source)


if __name__ == "__main__":
    unittest.main()
