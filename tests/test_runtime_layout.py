from __future__ import annotations

from pathlib import Path
import sys
import unittest


PUBLIC_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PUBLIC_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from config.runtime_layout import (  # noqa: E402
    RUNTIME_DIR_NAME,
    SourceApplicationLaunchForbidden,
    require_packaged_application,
    resolve_application_root,
    resolve_runtime_root,
)
from config import runtime_layout  # noqa: E402


class RuntimeLayoutTests(unittest.TestCase):
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

    def test_runtime_helpers_do_not_fall_back_to_source_launch(self) -> None:
        admin_source = (SRC_ROOT / "startup" / "admin_check.py").read_text(encoding="utf-8")
        kaspersky_source = (SRC_ROOT / "startup" / "kaspersky.py").read_text(encoding="utf-8")

        self.assertNotIn("sys.argv[0]", admin_source)
        self.assertNotIn("zapret.pyw", kaspersky_source)
        self.assertNotIn("getattr(sys, \"frozen\"", kaspersky_source)


if __name__ == "__main__":
    unittest.main()
