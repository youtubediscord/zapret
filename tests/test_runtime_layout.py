from __future__ import annotations

from pathlib import Path
import sys
import unittest


PUBLIC_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PUBLIC_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from config.runtime_layout import (  # noqa: E402
    ApplicationPaths,
    RUNTIME_DIR_NAME,
    SourceApplicationLaunchForbidden,
    require_packaged_application,
    resolve_application_root,
    resolve_runtime_root,
)
from config import runtime_layout  # noqa: E402
from core.paths import AppPaths  # noqa: E402


class RuntimeLayoutTests(unittest.TestCase):
    def test_all_application_folders_follow_a_changed_install_root(self) -> None:
        root = Path("D:/Программы/ZapretCustom").resolve()
        paths = ApplicationPaths.from_root(root)

        expected = {
            "runtime_dir": root / "_internal",
            "executable": root / "_internal" / "Zapret.exe",
            "bin_dir": root / "bin",
            "exe_dir": root / "exe",
            "ico_dir": root / "ico",
            "json_dir": root / "json",
            "lists_dir": root / "lists",
            "lists_base_dir": root / "lists" / "base",
            "lists_user_dir": root / "lists" / "user",
            "lua_dir": root / "lua",
            "presets_dir": root / "presets",
            "profile_dir": root / "profile",
            "settings_dir": root / "settings",
            "settings_file": root / "settings" / "settings.json",
            "logs_dir": root / "logs",
            "crash_logs_dir": root / "logs" / "crashes",
            "tmp_dir": root / "tmp",
            "themes_dir": root / "themes",
            "sos_dir": root / "sos",
            "windivert_filter_dir": root / "windivert.filter",
            "update_cache_dir": root / "_update_cache",
            "stable_icon": root / "ico" / "Zapret2.ico",
            "dev_icon": root / "ico" / "ZapretDevLogo4.ico",
            "sidebar_icons_dir": root / "ico" / "windows11_fluent" / "sidebar",
        }

        for attribute, expected_path in expected.items():
            with self.subTest(attribute=attribute):
                self.assertEqual(getattr(paths, attribute), expected_path)

    def test_runtime_path_consumers_do_not_restore_separate_folder_constants(self) -> None:
        config_source = (SRC_ROOT / "config" / "config.py").read_text(encoding="utf-8")
        forbidden_names = (
            "BIN_FOLDER",
            "INDEXJSON_FOLDER",
            "EXE_FOLDER",
            "LUA_FOLDER",
            "ICO_FOLDER",
            "THEME_FOLDER",
            "WINDIVERT_FILTER",
            "ICON_PATH",
            "ICON_DEV_PATH",
        )

        for name in forbidden_names:
            with self.subTest(name=name):
                self.assertNotIn(name, config_source)

        critical_sources = (
            SRC_ROOT / "main" / "early_startup_crash.py",
            SRC_ROOT / "main" / "prelaunch.py",
            SRC_ROOT / "autostart" / "nssm_service.py",
            SRC_ROOT / "app" / "navigation_icon_resources.py",
        )
        for path in critical_sources:
            source = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertTrue(
                    "APPLICATION_PATHS" in source or "APPLICATION_RESOURCE_PATHS" in source
                )
                self.assertNotIn("Path.cwd()", source)
                self.assertNotIn("abspath(__file__)", source)

    def test_source_tree_has_no_hard_coded_install_root(self) -> None:
        for path in SRC_ROOT.rglob("*.py"):
            source = path.read_text(encoding="utf-8", errors="replace")
            with self.subTest(path=path.relative_to(SRC_ROOT)):
                self.assertNotIn(r"C:\Zapret", source)
                self.assertNotIn("C:/Zapret", source)

    def test_packaged_detection_supports_nuitka_and_pyinstaller(self) -> None:
        previous_frozen = getattr(sys, "frozen", None)
        had_frozen = hasattr(sys, "frozen")
        try:
            sys.frozen = True
            self.assertTrue(runtime_layout.is_packaged_runtime())
        finally:
            if had_frozen:
                sys.frozen = previous_frozen
            else:
                delattr(sys, "frozen")

        runtime_layout.__dict__["__compiled__"] = object()
        try:
            self.assertTrue(runtime_layout.is_packaged_runtime())
        finally:
            runtime_layout.__dict__.pop("__compiled__", None)

    def test_packaged_runtime_uses_parent_of_internal(self) -> None:
        executable = Path("C:/Zapret/Dev") / RUNTIME_DIR_NAME / "Zapret.exe"

        root = resolve_application_root(
            executable=executable,
            module_file=SRC_ROOT / "config" / "runtime_layout.py",
            packaged=True,
        )

        self.assertEqual(root, Path("C:/Zapret/Dev").resolve())
        self.assertEqual(
            resolve_runtime_root(executable=executable, packaged=True),
            (Path("C:/Zapret/Dev") / RUNTIME_DIR_NAME).resolve(),
        )

    def test_packaged_preset_paths_stay_inside_channel_install_root(self) -> None:
        executable = Path("C:/Zapret/Dev") / RUNTIME_DIR_NAME / "Zapret.exe"
        app_root = resolve_application_root(
            executable=executable,
            module_file=SRC_ROOT / "config" / "runtime_layout.py",
            packaged=True,
        )

        engine_paths = AppPaths(user_root=app_root, local_root=app_root).engine_paths("winws2")

        self.assertEqual(engine_paths.presets_root_dir, Path("C:/Zapret/Dev/presets").resolve())
        self.assertEqual(engine_paths.user_presets_dir, Path("C:/Zapret/Dev/presets/winws2").resolve())
        self.assertEqual(
            engine_paths.builtin_presets_dir,
            Path("C:/Zapret/Dev/presets/winws2_builtin").resolve(),
        )
        self.assertNotEqual(engine_paths.presets_root_dir, Path("C:/Zapret/presets").resolve())

    def test_flat_packaged_runtime_is_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Некорректная структура"):
            resolve_application_root(
                executable=Path("C:/Zapret/Dev/Zapret.exe"),
                module_file=SRC_ROOT / "config" / "runtime_layout.py",
                packaged=True,
            )

    def test_build_tool_import_uses_public_repository_root(self) -> None:
        module_file = PUBLIC_ROOT / "src" / "config" / "runtime_layout.py"

        root = resolve_application_root(
            executable=sys.executable,
            module_file=module_file,
            packaged=False,
        )

        self.assertEqual(root, PUBLIC_ROOT.resolve())
        self.assertIsNone(resolve_runtime_root(executable=sys.executable, packaged=False))

    def test_source_application_entrypoint_is_forbidden(self) -> None:
        with self.assertRaisesRegex(SourceApplicationLaunchForbidden, "запрещён"):
            require_packaged_application()

    def test_main_checks_packaged_runtime_before_application_imports(self) -> None:
        main_source = (SRC_ROOT / "main.py").read_text(encoding="utf-8")

        gate = main_source.index("require_packaged_application()")
        process_start = main_source.index("import main.process_start_time")
        crash_handler = main_source.index("from main.early_startup_crash")

        self.assertLess(gate, process_start)
        self.assertLess(gate, crash_handler)

    def test_internal_application_entrypoint_repeats_packaged_runtime_gate(self) -> None:
        entry_source = (SRC_ROOT / "main" / "entry.py").read_text(encoding="utf-8")

        main_body = entry_source.split("def main() -> None:", 1)[1]
        self.assertIn("require_packaged_application()", main_body)
        self.assertLess(
            main_body.index("require_packaged_application()"),
            main_body.index('log("=== ЗАПУСК ПРИЛОЖЕНИЯ ==="'),
        )

    def test_runtime_helpers_do_not_fall_back_to_source_launch(self) -> None:
        admin_source = (SRC_ROOT / "startup" / "admin_check.py").read_text(encoding="utf-8")
        kaspersky_source = (SRC_ROOT / "startup" / "kaspersky.py").read_text(encoding="utf-8")

        self.assertNotIn("sys.argv[0]", admin_source)
        self.assertNotIn("zapret.pyw", kaspersky_source)
        self.assertNotIn("getattr(sys, \"frozen\"", kaspersky_source)


if __name__ == "__main__":
    unittest.main()
