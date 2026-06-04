from __future__ import annotations

import ast
from pathlib import Path
import unittest


SRC_ROOT = Path(__file__).resolve().parents[1] / "src"

GUI_ROOTS = (
    SRC_ROOT / "ui" / "pages",
    SRC_ROOT / "autostart" / "ui",
    SRC_ROOT / "blobs" / "ui",
    SRC_ROOT / "blockcheck" / "ui",
    SRC_ROOT / "diagnostics" / "ui",
    SRC_ROOT / "dns" / "ui",
    SRC_ROOT / "donater" / "ui",
    SRC_ROOT / "hosts" / "ui",
    SRC_ROOT / "log" / "ui",
    SRC_ROOT / "orchestra" / "ui",
    SRC_ROOT / "presets" / "ui",
    SRC_ROOT / "profile" / "ui",
    SRC_ROOT / "settings" / "dpi",
    SRC_ROOT / "telegram_proxy" / "ui",
    SRC_ROOT / "updater" / "ui",
)

GUI_SHELL_PATTERNS = (
    "ui/navigation/**/*.py",
    "ui/page_*.py",
    "ui/page_deps/**/*.py",
    "ui/runtime_ui_bridge.py",
    "ui/theme*.py",
    "ui/ui_root.py",
    "ui/window_*.py",
    "ui/workflows/**/*.py",
    "main/window_*.py",
)

FORBIDDEN_IMPORT_ROOTS = {
    "requests",
    "socket",
    "subprocess",
    "urllib",
    "webbrowser",
    "winreg",
}

FORBIDDEN_BUILTIN_CALLS = {"open"}

FORBIDDEN_ATTRIBUTE_CALLS = {
    ("os", "startfile"),
    ("subprocess", "run"),
    ("subprocess", "Popen"),
    ("subprocess", "check_call"),
    ("subprocess", "check_output"),
    ("webbrowser", "open"),
    ("requests", "get"),
    ("requests", "post"),
}

FORBIDDEN_IO_METHODS = {
    "exists",
    "glob",
    "iterdir",
    "mkdir",
    "read_bytes",
    "read_text",
    "rename",
    "replace",
    "rglob",
    "stat",
    "unlink",
    "write_bytes",
    "write_text",
}


class GuiDirectWorkContractTests(unittest.TestCase):
    def test_gui_pages_do_not_touch_file_windows_or_network_directly(self) -> None:
        offenders: list[str] = []
        for root in GUI_ROOTS:
            for path in root.rglob("*.py"):
                offenders.extend(self._collect_offenders(path))

        self.assertEqual([], offenders)

    def test_gui_shell_does_not_touch_file_windows_or_network_directly(self) -> None:
        offenders: list[str] = []
        for path in self._iter_shell_files():
            offenders.extend(self._collect_offenders(path))

        self.assertEqual([], offenders)

    def _iter_shell_files(self) -> list[Path]:
        files: set[Path] = set()
        for pattern in GUI_SHELL_PATTERNS:
            files.update(path for path in SRC_ROOT.glob(pattern) if path.is_file())
        return sorted(files)

    def _collect_offenders(self, path: Path) -> list[str]:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel_path = path.relative_to(SRC_ROOT).as_posix()
        offenders = self._find_forbidden_imports(tree, rel_path)
        offenders.extend(self._find_forbidden_calls(tree, rel_path))
        return offenders

    def _find_forbidden_imports(self, tree: ast.Module, rel_path: str) -> list[str]:
        offenders: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = str(alias.name or "").split(".", 1)[0]
                    if root in FORBIDDEN_IMPORT_ROOTS:
                        offenders.append(f"{rel_path}:{node.lineno}:import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                root = str(node.module or "").split(".", 1)[0]
                if root in FORBIDDEN_IMPORT_ROOTS:
                    offenders.append(f"{rel_path}:{node.lineno}:from {node.module} import ...")
        return offenders

    def _find_forbidden_calls(self, tree: ast.Module, rel_path: str) -> list[str]:
        offenders: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            call_name = self._call_name(node.func)
            if call_name in FORBIDDEN_BUILTIN_CALLS:
                offenders.append(f"{rel_path}:{node.lineno}:{call_name}()")
                continue
            if isinstance(node.func, ast.Attribute):
                owner_name = self._call_name(node.func.value)
                pair = (owner_name, node.func.attr)
                if pair in FORBIDDEN_ATTRIBUTE_CALLS:
                    offenders.append(f"{rel_path}:{node.lineno}:{owner_name}.{node.func.attr}()")
                    continue
                if node.func.attr in FORBIDDEN_IO_METHODS and self._looks_like_path_io(node.func.value):
                    offenders.append(f"{rel_path}:{node.lineno}:path.{node.func.attr}()")
        return offenders

    def _call_name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            owner = self._call_name(node.value)
            return f"{owner}.{node.attr}" if owner else node.attr
        return ""

    def _looks_like_path_io(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Call):
            return self._call_name(node.func) in {"Path", "pathlib.Path"}
        if isinstance(node, ast.Name):
            return any(marker in node.id.lower() for marker in ("path", "file", "dir", "folder"))
        if isinstance(node, ast.Attribute):
            name = node.attr.lower()
            return any(marker in name for marker in ("path", "file", "dir", "folder"))
        if isinstance(node, ast.BinOp):
            return self._looks_like_path_io(node.left) or self._looks_like_path_io(node.right)
        return False


if __name__ == "__main__":
    unittest.main()
