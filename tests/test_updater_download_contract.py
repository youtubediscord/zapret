from __future__ import annotations

import ast
import inspect
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


SRC_ROOT = Path(__file__).resolve().parents[1] / "src"


class UpdaterDownloadContractTests(unittest.TestCase):
    def test_update_module_imports_threading_when_download_code_uses_it(self) -> None:
        tree = ast.parse((SRC_ROOT / "updater" / "update.py").read_text(encoding="utf-8"))

        uses_threading = any(
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "threading"
            for node in ast.walk(tree)
        )
        imports_threading = any(
            (isinstance(node, ast.Import) and any(alias.name == "threading" for alias in node.names))
            or (
                isinstance(node, ast.ImportFrom)
                and node.module == "threading"
            )
            for node in ast.walk(tree)
        )

        self.assertTrue(uses_threading)
        self.assertTrue(
            imports_threading,
            "updater.update использует threading, поэтому модуль должен импортировать его явно",
        )

    def test_update_worker_uses_narrow_runtime_actions_for_download_dpi_stop(self) -> None:
        import updater.commands as updater_commands
        from updater.update import UpdateWorker

        init_signature = inspect.signature(UpdateWorker.__init__)
        worker_source = inspect.getsource(UpdateWorker)
        stop_source = inspect.getsource(UpdateWorker._stop_dpi_for_download)
        self.assertTrue(hasattr(updater_commands, "stop_dpi_for_download"))
        command_source = inspect.getsource(updater_commands.stop_dpi_for_download)

        self.assertNotIn("runtime_feature", init_signature.parameters)
        self.assertNotIn("_runtime_feature", worker_source)
        self.assertIn("updater_commands.stop_dpi_for_download", stop_source)
        self.assertNotIn("self._shutdown_sync(", stop_source)
        self.assertNotIn("self._is_any_running(", stop_source)
        self.assertIn("shutdown_sync", command_source)
        self.assertIn("is_any_running", command_source)

        runtime_feature = SimpleNamespace(
            is_any_running=Mock(return_value=True),
            shutdown_sync=Mock(),
        )
        worker = UpdateWorker(
            silent=True,
            skip_rate_limit=True,
            is_any_running=runtime_feature.is_any_running,
            shutdown_sync=runtime_feature.shutdown_sync,
        )
        progress = []
        worker.progress.connect(progress.append)

        with patch("updater.update.time.sleep") as sleep:
            self.assertTrue(worker._stop_dpi_for_download())

        runtime_feature.shutdown_sync.assert_called_once_with(
            reason="updater_download_connectivity",
            include_cleanup=True,
        )
        sleep.assert_called_once_with(0.5)
        self.assertIn("Остановка DPI для скачивания...", progress)


if __name__ == "__main__":
    unittest.main()
