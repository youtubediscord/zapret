from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_SRC = PROJECT_ROOT / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class SingleOwnerGuardTests(unittest.TestCase):
    """Архитектурный инвариант: состоянием главного окна управляет ТОЛЬКО
    WindowGeometryRuntime.

    История: баг с обрезанным окном после восстановления из трея возник из-за
    нескольких независимых «актёров», манипулировавших состоянием и геометрией
    окна (см. .agent/tasks/tray-restore-window-state/problems.md). Этот тест
    падает, если в оркестрирующих модулях снова появляются прямые вызовы
    смены состояния окна.
    """

    STATE_MUTATORS = ("showMaximized(", "showNormal(", "setWindowState(", "showFullScreen(")

    # Модули, которые оркестрируют показ/скрытие главного окна и НЕ имеют
    # права менять его состояние напрямую.
    ORCHESTRATOR_FILES = (
        "src/ui/window_adapter.py",
        "src/tray.py",
        "src/main/tray_window_port.py",
        "src/main/window_native_commands.py",
        "src/ui/window_close_flow.py",
        "src/startup/show_window_bridge.py",
    )

    def test_orchestrators_do_not_mutate_window_state(self) -> None:
        for rel_path in self.ORCHESTRATOR_FILES:
            source = (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")
            for mutator in self.STATE_MUTATORS:
                self.assertNotIn(
                    mutator,
                    source,
                    f"{rel_path} не должен вызывать {mutator} — состоянием окна "
                    "владеет только WindowGeometryRuntime",
                )

    def test_window_lifecycle_mixin_only_overrides_minimize(self) -> None:
        source = (PROJECT_ROOT / "src/main/window_lifecycle.py").read_text(encoding="utf-8")
        for mutator in self.STATE_MUTATORS:
            self.assertNotIn(mutator, source)
        # разрешён только собственный override showMinimized с делегированием базе
        self.assertIn("super().showMinimized()", source)

    def test_runtime_has_no_fsm_and_no_dead_api(self) -> None:
        import inspect

        import ui.window_geometry_runtime as runtime_module

        source = inspect.getsource(runtime_module.WindowGeometryRuntime)
        for removed in (
            "_window_fsm",
            "_window_state_settle",
            "_persist_window_maximized_state_now",
            "_window_maximized_persist_timer",
            "_window_zoom_visual_state",
            "toggle_maximize_restore",
            "restore_from_zoom_for_drag",
            "def request_minimize",
        ):
            self.assertNotIn(removed, source, f"{removed} должен быть удалён из runtime")

    def test_reshow_entry_points_are_single(self) -> None:
        """show_from_hidden — только из window_adapter; restore_geometry — только из startup."""
        callers_show = []
        callers_restore = []
        for path in (PROJECT_SRC).rglob("*.py"):
            source = path.read_text(encoding="utf-8", errors="ignore")
            rel = path.relative_to(PROJECT_SRC).as_posix()
            if rel == "ui/window_geometry_runtime.py":
                continue
            if "show_from_hidden" in source:
                callers_show.append(rel)
            if ".restore_geometry()" in source:
                callers_restore.append(rel)
        self.assertEqual(callers_show, ["ui/window_adapter.py"])
        self.assertEqual(callers_restore, ["main/window_lifecycle_setup.py"])


class _FakeHost:
    def __init__(self, *, visible: bool, maximized: bool) -> None:
        self.calls: list[str] = []
        self._visible = visible
        self._maximized = maximized

    def isVisible(self) -> bool:  # noqa: N802 (Qt-style API)
        return self._visible

    def isMinimized(self) -> bool:  # noqa: N802 (Qt-style API)
        return False

    def isMaximized(self) -> bool:  # noqa: N802 (Qt-style API)
        return self._maximized

    def isFullScreen(self) -> bool:  # noqa: N802 (Qt-style API)
        return False

    def windowState(self):  # noqa: N802 (Qt-style API)
        from PyQt6.QtCore import Qt

        if self._maximized:
            return Qt.WindowState.WindowMaximized
        return Qt.WindowState.WindowNoState

    def showMaximized(self) -> None:  # noqa: N802 (Qt-style API)
        self.calls.append("showMaximized")
        self._maximized = True
        self._visible = True

    def showNormal(self) -> None:  # noqa: N802 (Qt-style API)
        self.calls.append("showNormal")
        self._maximized = False
        self._visible = True


def _make_runtime(host):
    import ui.window_geometry_runtime as runtime_module

    runtime = runtime_module.WindowGeometryRuntime.__new__(runtime_module.WindowGeometryRuntime)
    runtime.host = host
    runtime._pending_restore_maximized = False
    runtime._last_non_minimized_zoomed = host.isMaximized()
    runtime._persistence_enabled = False  # _schedule_geometry_save станет no-op
    runtime._restore_in_progress = False
    return runtime


class RequestZoomStateTests(unittest.TestCase):
    """request_zoom_state — прямая команда без FSM."""

    def test_visible_window_already_in_target_mode_is_noop(self) -> None:
        host = _FakeHost(visible=True, maximized=True)
        runtime = _make_runtime(host)

        result = runtime.request_zoom_state(True)

        self.assertEqual(host.calls, [])
        self.assertTrue(result)
        self.assertTrue(runtime._last_non_minimized_zoomed)

    def test_hidden_window_gets_mode_command_even_when_mode_matches(self) -> None:
        """Скрытому окну команда нужна всегда: showMaximized() заодно показывает его."""
        host = _FakeHost(visible=False, maximized=True)
        runtime = _make_runtime(host)

        result = runtime.request_zoom_state(True)

        self.assertEqual(host.calls, ["showMaximized"])
        self.assertTrue(result)

    def test_visible_normal_window_maximizes_and_records_state(self) -> None:
        host = _FakeHost(visible=True, maximized=False)
        runtime = _make_runtime(host)

        result = runtime.request_zoom_state(True)

        self.assertEqual(host.calls, ["showMaximized"])
        self.assertTrue(result)
        self.assertTrue(runtime._last_non_minimized_zoomed)

    def test_visible_maximized_window_restores_to_normal(self) -> None:
        host = _FakeHost(visible=True, maximized=True)
        runtime = _make_runtime(host)

        result = runtime.request_zoom_state(False)

        self.assertEqual(host.calls, ["showNormal"])
        self.assertFalse(result)
        self.assertFalse(runtime._last_non_minimized_zoomed)

    def test_request_clears_pending_restore_flag(self) -> None:
        host = _FakeHost(visible=True, maximized=True)
        runtime = _make_runtime(host)
        runtime._pending_restore_maximized = True

        runtime.request_zoom_state(True)

        self.assertFalse(runtime._pending_restore_maximized)


if __name__ == "__main__":
    unittest.main()
