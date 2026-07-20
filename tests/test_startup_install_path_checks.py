from __future__ import annotations

from pathlib import Path
import inspect
import os
import sys
import unittest
from unittest.mock import patch


PUBLIC_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PUBLIC_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from startup import check_start  # noqa: E402
from config.runtime_layout import ApplicationPaths  # noqa: E402


class StartupInstallPathChecksTests(unittest.TestCase):
    def test_internal_runtime_path_is_not_treated_as_install_path(self) -> None:
        with (
            patch.object(
                check_start,
                "APPLICATION_PATHS",
                ApplicationPaths.from_root(r"C:\Zapret\Dev"),
            ),
            patch.object(
                check_start.sys,
                "executable",
                r"C:\Zapret\Dev\_INTER~1\python.exe",
            ),
        ):
            has_special_chars, message = check_start.check_path_for_special_chars()

        self.assertFalse(has_special_chars)
        self.assertEqual(message, "")

    def test_onedrive_check_uses_application_root_only(self) -> None:
        with (
            patch.object(
                check_start,
                "APPLICATION_PATHS",
                ApplicationPaths.from_root(r"C:\Zapret\Dev"),
            ),
            patch.object(
                check_start.sys,
                "executable",
                r"C:\Users\privacy\OneDrive\_INTER~1\python.exe",
            ),
            patch.dict(
                os.environ,
                {"ONEDRIVE": r"C:\Users\privacy\OneDrive"},
                clear=False,
            ),
        ):
            in_onedrive, message = check_start.check_path_for_onedrive()

        self.assertFalse(in_onedrive)
        self.assertEqual(message, "")

    def test_real_problem_in_application_root_is_reported(self) -> None:
        with patch.object(
            check_start,
            "APPLICATION_PATHS",
            ApplicationPaths.from_root(r"C:\Zapret Builds\Dev"),
        ):
            has_special_chars, message = check_start.check_path_for_special_chars()

        self.assertTrue(has_special_chars)
        self.assertIn(r"C:\Zapret Builds\Dev", message)

    def test_temporary_directory_check_uses_application_root(self) -> None:
        environment = {
            "TEMP": r"C:\Users\privacy\AppData\Local\Temp",
            "TMP": r"C:\Users\privacy\AppData\Local\Temp",
            "WINDIR": r"C:\Windows",
        }
        with (
            patch.object(
                check_start,
                "APPLICATION_PATHS",
                ApplicationPaths.from_root(
                    r"C:\Users\privacy\AppData\Local\Temp\Zapret"
                ),
            ),
            patch.object(check_start.sys, "executable", r"C:\Python314\python.exe"),
            patch.dict(os.environ, environment, clear=False),
        ):
            self.assertTrue(check_start.check_if_application_root_is_temporary())

    def test_similar_directory_prefix_is_not_treated_as_temporary(self) -> None:
        environment = {
            "TEMP": r"C:\Temp",
            "TMP": r"C:\Temp",
            "WINDIR": r"C:\Windows",
        }
        with (
            patch.object(
                check_start,
                "APPLICATION_PATHS",
                ApplicationPaths.from_root(r"C:\TempBackup\Zapret"),
            ),
            patch.dict(os.environ, environment, clear=False),
        ):
            self.assertFalse(check_start.check_if_application_root_is_temporary())

    def test_path_validation_has_no_dependency_on_runtime_executable(self) -> None:
        source = inspect.getsource(check_start)

        self.assertNotIn("sys.executable", source)
        self.assertNotIn("BIN_FOLDER", source)


if __name__ == "__main__":
    unittest.main()
