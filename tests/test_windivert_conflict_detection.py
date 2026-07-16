import os
import unittest
from unittest.mock import patch

from winws_runtime.health import launch_conflicts


def _make_holder_env(records, modules_by_pid):
    return (
        patch.object(launch_conflicts, "iter_process_records_winapi", return_value=records),
        patch.object(
            launch_conflicts,
            "iter_process_module_paths_winapi",
            side_effect=lambda pid: modules_by_pid.get(int(pid), []),
        ),
    )


class OwnDirsRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_dirs = set(launch_conflicts._OWN_WINDIVERT_DIRS)
        launch_conflicts._OWN_WINDIVERT_DIRS.clear()

    def tearDown(self) -> None:
        launch_conflicts._OWN_WINDIVERT_DIRS.clear()
        launch_conflicts._OWN_WINDIVERT_DIRS.update(self._saved_dirs)

    def test_registered_dir_marks_nested_paths_as_own(self) -> None:
        launch_conflicts.register_own_windivert_dirs(r"C:\Program Files\Zapret2")

        own_file = os.path.join(r"C:\Program Files\Zapret2", "bin", "WinDivert64.sys")
        self.assertTrue(launch_conflicts._is_own_path(own_file))
        self.assertFalse(launch_conflicts._is_own_path(r"C:\GoodbyeDPI\WinDivert64.sys"))

    def test_prefix_of_dir_name_is_not_own(self) -> None:
        launch_conflicts.register_own_windivert_dirs(r"C:\Zapret")

        foreign = os.path.join(r"C:\ZapretOther", "WinDivert64.sys")
        self.assertFalse(launch_conflicts._is_own_path(foreign))

    def test_empty_and_blank_dirs_are_ignored(self) -> None:
        launch_conflicts.register_own_windivert_dirs("", "   ")
        self.assertEqual(launch_conflicts._OWN_WINDIVERT_DIRS, set())


class WinDivertHolderProcessesTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_dirs = set(launch_conflicts._OWN_WINDIVERT_DIRS)
        launch_conflicts._OWN_WINDIVERT_DIRS.clear()

    def tearDown(self) -> None:
        launch_conflicts._OWN_WINDIVERT_DIRS.clear()
        launch_conflicts._OWN_WINDIVERT_DIRS.update(self._saved_dirs)

    def test_foreign_process_with_windivert_dll_is_reported(self) -> None:
        records = [(1234, "GoodbyeDPI.exe"), (5678, "notepad.exe")]
        modules = {
            1234: [
                r"C:\GoodbyeDPI\GoodbyeDPI.exe",
                r"C:\Windows\System32\kernel32.dll",
                r"C:\GoodbyeDPI\WinDivert64.dll",
            ],
            5678: [r"C:\Windows\notepad.exe", r"C:\Windows\System32\kernel32.dll"],
        }

        records_patch, modules_patch = _make_holder_env(records, modules)
        with records_patch, modules_patch:
            holders = launch_conflicts.find_windivert_holder_processes()

        self.assertEqual(len(holders), 1)
        self.assertEqual(holders[0]["name"], "GoodbyeDPI.exe")
        self.assertEqual(holders[0]["pid"], 1234)
        self.assertEqual(holders[0]["exe"], r"C:\GoodbyeDPI\GoodbyeDPI.exe")
        self.assertEqual(holders[0]["windivert_dll"], r"C:\GoodbyeDPI\WinDivert64.dll")

    def test_own_process_is_not_reported(self) -> None:
        launch_conflicts.register_own_windivert_dirs(r"C:\Zapret2")
        records = [(1234, "winws2.exe")]
        modules = {
            1234: [
                os.path.join(r"C:\Zapret2", "exe", "winws2.exe"),
                os.path.join(r"C:\Zapret2", "bin", "WinDivert64.dll"),
            ],
        }

        records_patch, modules_patch = _make_holder_env(records, modules)
        with records_patch, modules_patch:
            holders = launch_conflicts.find_windivert_holder_processes()

        self.assertEqual(holders, [])

    def test_current_process_pid_is_skipped(self) -> None:
        own_pid = os.getpid()
        records = [(own_pid, "python.exe")]
        modules = {own_pid: [r"C:\Python\python.exe", r"C:\Python\WinDivert64.dll"]}

        records_patch, modules_patch = _make_holder_env(records, modules)
        with records_patch, modules_patch:
            holders = launch_conflicts.find_windivert_holder_processes()

        self.assertEqual(holders, [])

    def test_foreign_winws_from_other_folder_is_reported(self) -> None:
        launch_conflicts.register_own_windivert_dirs(r"C:\Zapret2")
        records = [(4321, "winws.exe")]
        modules = {
            4321: [
                r"C:\OtherZapret\winws.exe",
                r"C:\OtherZapret\WinDivert.dll",
            ],
        }

        records_patch, modules_patch = _make_holder_env(records, modules)
        with records_patch, modules_patch:
            holders = launch_conflicts.find_windivert_holder_processes()

        self.assertEqual(len(holders), 1)
        self.assertEqual(holders[0]["exe"], r"C:\OtherZapret\winws.exe")


class ServiceImagePathTests(unittest.TestCase):
    def test_nt_prefix_and_quotes_are_stripped(self) -> None:
        self.assertEqual(
            launch_conflicts._normalize_service_image_path(r"\??\C:\GoodbyeDPI\WinDivert64.sys"),
            r"C:\GoodbyeDPI\WinDivert64.sys",
        )
        self.assertEqual(
            launch_conflicts._normalize_service_image_path('"C:\\A B\\WinDivert64.sys"'),
            r"C:\A B\WinDivert64.sys",
        )
        self.assertEqual(launch_conflicts._normalize_service_image_path(None), "")

    def test_returns_empty_list_when_winreg_is_unavailable(self) -> None:
        # На не-Windows системах функция должна тихо вернуть пустой список.
        result = launch_conflicts.find_foreign_windivert_service_paths()
        self.assertIsInstance(result, list)


class ConflictHintTests(unittest.TestCase):
    def test_hint_prefers_live_holder_process(self) -> None:
        holder = {
            "name": "GoodbyeDPI.exe",
            "exe": r"C:\GoodbyeDPI\GoodbyeDPI.exe",
            "windivert_dll": r"C:\GoodbyeDPI\WinDivert64.dll",
            "pid": 1234,
        }
        with (
            patch.object(launch_conflicts, "find_windivert_holder_processes", return_value=[holder]),
            patch.object(launch_conflicts, "find_foreign_windivert_service_paths", return_value=[]),
        ):
            hint = launch_conflicts.build_windivert_conflict_hint()

        self.assertIsNotNone(hint)
        assert hint is not None
        self.assertIn("GoodbyeDPI.exe", hint)
        self.assertIn("PID 1234", hint)

    def test_hint_falls_back_to_foreign_driver_path(self) -> None:
        with (
            patch.object(launch_conflicts, "find_windivert_holder_processes", return_value=[]),
            patch.object(
                launch_conflicts,
                "find_foreign_windivert_service_paths",
                return_value=[r"C:\GoodbyeDPI\WinDivert64.sys"],
            ),
        ):
            hint = launch_conflicts.build_windivert_conflict_hint()

        self.assertIsNotNone(hint)
        assert hint is not None
        self.assertIn(r"C:\GoodbyeDPI\WinDivert64.sys", hint)

    def test_hint_is_none_when_nothing_found(self) -> None:
        with (
            patch.object(launch_conflicts, "find_windivert_holder_processes", return_value=[]),
            patch.object(launch_conflicts, "find_foreign_windivert_service_paths", return_value=[]),
        ):
            self.assertIsNone(launch_conflicts.build_windivert_conflict_hint())


class DynamicLaunchAdviceTests(unittest.TestCase):
    def test_advice_uses_dynamic_detection_when_blacklist_is_empty(self) -> None:
        holder = {
            "name": "GoodbyeDPI.exe",
            "exe": r"C:\GoodbyeDPI\GoodbyeDPI.exe",
            "windivert_dll": r"C:\GoodbyeDPI\WinDivert64.dll",
            "pid": 1234,
        }
        with (
            patch.object(launch_conflicts, "check_conflicting_processes", return_value=[]),
            patch.object(launch_conflicts, "find_windivert_holder_processes", return_value=[holder]),
            patch.object(launch_conflicts, "find_foreign_windivert_service_paths", return_value=[]),
        ):
            advice = launch_conflicts.build_launch_conflict_advice()

        self.assertIsNotNone(advice)
        assert advice is not None
        cause, solution = advice
        self.assertIn("GoodbyeDPI.exe", cause)
        self.assertIn("Закройте эту программу", solution)

    def test_advice_reports_foreign_driver_when_no_process_found(self) -> None:
        with (
            patch.object(launch_conflicts, "check_conflicting_processes", return_value=[]),
            patch.object(launch_conflicts, "find_windivert_holder_processes", return_value=[]),
            patch.object(
                launch_conflicts,
                "find_foreign_windivert_service_paths",
                return_value=[r"C:\GoodbyeDPI\WinDivert64.sys"],
            ),
        ):
            advice = launch_conflicts.build_launch_conflict_advice()

        self.assertIsNotNone(advice)
        assert advice is not None
        cause, _solution = advice
        self.assertIn(r"C:\GoodbyeDPI\WinDivert64.sys", cause)

    def test_advice_is_none_when_nothing_found(self) -> None:
        with (
            patch.object(launch_conflicts, "check_conflicting_processes", return_value=[]),
            patch.object(launch_conflicts, "find_windivert_holder_processes", return_value=[]),
            patch.object(launch_conflicts, "find_foreign_windivert_service_paths", return_value=[]),
        ):
            self.assertIsNone(launch_conflicts.build_launch_conflict_advice())


class ReadinessErrorConflictSuffixTests(unittest.TestCase):
    def test_conflict_hint_is_appended_to_readiness_error(self) -> None:
        from winws_runtime.health import windivert_diagnostics

        hint = "Возможный конфликт: GoodbyeDPI.exe (PID 1234, C:\\GoodbyeDPI\\GoodbyeDPI.exe) держит WinDivert — закройте эту программу"

        with patch.object(launch_conflicts, "build_windivert_conflict_hint", return_value=hint):
            message = windivert_diagnostics.describe_windivert_readiness_failure(None)

        self.assertIn("WinDivert ещё не готов к открытию фильтра", message)
        self.assertIn("GoodbyeDPI.exe", message)

    def test_error_stays_clean_without_conflicts(self) -> None:
        from winws_runtime.health import windivert_diagnostics

        with patch.object(launch_conflicts, "build_windivert_conflict_hint", return_value=None):
            message = windivert_diagnostics.describe_windivert_readiness_failure(None)

        self.assertEqual(message, "WinDivert ещё не готов к открытию фильтра")


if __name__ == "__main__":
    unittest.main()
