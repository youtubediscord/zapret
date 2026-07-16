from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class _FakeRect:
    def __init__(self, x: int, y: int, width: int, height: int) -> None:
        self._x, self._y, self._w, self._h = x, y, width, height

    def x(self) -> int:
        return self._x

    def y(self) -> int:
        return self._y

    def width(self) -> int:
        return self._w

    def height(self) -> int:
        return self._h


class _FakeHost:
    """Живая геометрия скрытого окна намеренно минимальная (900×580) —
    именно её runtime НЕ должен записывать в store."""

    def __init__(
        self,
        *,
        visible: bool,
        maximized: bool = False,
        minimized: bool = False,
        live_geometry: tuple[int, int, int, int] = (0, 0, 900, 580),
        normal_geometry: tuple[int, int, int, int] | None = None,
    ) -> None:
        self._visible = visible
        self._maximized = maximized
        self._minimized = minimized
        self._live = live_geometry
        self._normal = normal_geometry

    def isVisible(self) -> bool:  # noqa: N802 (Qt-style API)
        return self._visible

    def isMinimized(self) -> bool:  # noqa: N802 (Qt-style API)
        return self._minimized

    def isMaximized(self) -> bool:  # noqa: N802 (Qt-style API)
        return self._maximized

    def isFullScreen(self) -> bool:  # noqa: N802 (Qt-style API)
        return False

    def windowState(self):  # noqa: N802 (Qt-style API)
        from PyQt6.QtCore import Qt

        state = Qt.WindowState.WindowNoState
        if self._maximized:
            state |= Qt.WindowState.WindowMaximized
        if self._minimized:
            state |= Qt.WindowState.WindowMinimized
        return state

    def x(self) -> int:
        return self._live[0]

    def y(self) -> int:
        return self._live[1]

    def width(self) -> int:
        return self._live[2]

    def height(self) -> int:
        return self._live[3]

    def normalGeometry(self):  # noqa: N802 (Qt-style API)
        if self._normal is None:
            return _FakeRect(0, 0, 0, 0)
        return _FakeRect(*self._normal)


class _RecordingStore:
    def __init__(self) -> None:
        self.saved_geometry: list[tuple[int, int, int, int]] = []
        self.saved_maximized: list[bool] = []

    def save_geometry(self, x: int, y: int, width: int, height: int) -> None:
        self.saved_geometry.append((x, y, width, height))

    def save_maximized(self, maximized: bool) -> None:
        self.saved_maximized.append(bool(maximized))


def _make_runtime(host, store):
    import ui.window_geometry_runtime as runtime_module

    runtime = runtime_module.WindowGeometryRuntime.__new__(
        runtime_module.WindowGeometryRuntime
    )
    runtime.host = host
    runtime.store = store
    runtime.min_width = 900
    runtime.min_height = 580
    runtime._last_normal_geometry = None
    runtime._last_non_minimized_zoomed = False
    runtime._last_persisted_geometry = None
    runtime._last_persisted_maximized = None
    runtime._restore_in_progress = False
    runtime._persistence_enabled = True
    return runtime


class HiddenWindowPersistTests(unittest.TestCase):
    """AC1-AC3: скрытое/минимизированное окно пишет наблюдаемую модель."""

    def _persist_force(self, runtime) -> None:
        # persist_now(force=True) → _persist_geometry_sync; worker-остановку
        # для force-пути подменяем no-op (нет реального QThread-раниайма)
        runtime._stop_geometry_save_worker_for_sync = lambda: None
        runtime.persist_now(force=True)

    def test_hidden_window_persists_remembered_model_not_live(self) -> None:
        host = _FakeHost(visible=False, live_geometry=(0, 0, 900, 580))
        store = _RecordingStore()
        runtime = _make_runtime(host, store)
        runtime._last_normal_geometry = (100, 100, 1500, 900)
        runtime._last_non_minimized_zoomed = True

        self._persist_force(runtime)

        self.assertEqual(store.saved_geometry, [(100, 100, 1500, 900)])
        self.assertEqual(store.saved_maximized, [True])

    def test_hidden_window_without_remembered_geometry_keeps_store_size(self) -> None:
        host = _FakeHost(visible=False)
        store = _RecordingStore()
        runtime = _make_runtime(host, store)
        runtime._last_non_minimized_zoomed = True

        self._persist_force(runtime)

        self.assertEqual(store.saved_geometry, [])
        self.assertEqual(store.saved_maximized, [True])

    def test_minimized_window_persists_remembered_model(self) -> None:
        host = _FakeHost(
            visible=True, minimized=True, live_geometry=(5, 5, 901, 581)
        )
        store = _RecordingStore()
        runtime = _make_runtime(host, store)
        runtime._last_normal_geometry = (200, 150, 1400, 800)
        runtime._last_non_minimized_zoomed = False

        self._persist_force(runtime)

        self.assertEqual(store.saved_geometry, [(200, 150, 1400, 800)])
        self.assertEqual(store.saved_maximized, [False])

    def test_tray_only_session_round_trips_loaded_values(self) -> None:
        """Сценарий перезагрузки из трея: то, что restore загрузил и записал в
        наблюдаемую модель, уходит обратно в store без искажений."""
        loaded = (300, 200, 1600, 1000)
        host = _FakeHost(visible=False, live_geometry=(0, 0, 900, 580))
        store = _RecordingStore()
        runtime = _make_runtime(host, store)
        runtime._last_normal_geometry = loaded
        runtime._last_non_minimized_zoomed = True  # засижено из saved.maximized

        self._persist_force(runtime)
        self._persist_force(runtime)

        self.assertEqual(store.saved_geometry, [loaded, loaded])
        self.assertEqual(store.saved_maximized, [True, True])


class VisibleWindowPersistTests(unittest.TestCase):
    """AC4: пути видимого окна не изменились."""

    def _persist_force(self, runtime) -> None:
        runtime._stop_geometry_save_worker_for_sync = lambda: None
        runtime.persist_now(force=True)

    def test_visible_normal_window_persists_live_geometry(self) -> None:
        host = _FakeHost(visible=True, live_geometry=(50, 60, 1280, 720))
        store = _RecordingStore()
        runtime = _make_runtime(host, store)
        runtime._last_normal_geometry = (999, 999, 1111, 1111)

        self._persist_force(runtime)

        self.assertEqual(store.saved_geometry, [(50, 60, 1280, 720)])
        self.assertEqual(store.saved_maximized, [False])

    def test_visible_maximized_window_persists_normal_geometry(self) -> None:
        host = _FakeHost(
            visible=True,
            maximized=True,
            live_geometry=(0, 0, 2560, 1400),
            normal_geometry=(120, 90, 1500, 950),
        )
        store = _RecordingStore()
        runtime = _make_runtime(host, store)

        self._persist_force(runtime)

        self.assertEqual(store.saved_geometry, [(120, 90, 1500, 950)])
        self.assertEqual(store.saved_maximized, [True])

    def test_small_visible_geometry_is_clamped_to_minimum(self) -> None:
        host = _FakeHost(visible=True, live_geometry=(10, 10, 640, 480))
        store = _RecordingStore()
        runtime = _make_runtime(host, store)

        self._persist_force(runtime)

        self.assertEqual(store.saved_geometry, [(10, 10, 900, 580)])


class ObservedModelGuardTests(unittest.TestCase):
    """AC1 (усиление модели): события скрытого окна не попадают в модель."""

    def test_on_geometry_changed_ignores_hidden_window(self) -> None:
        host = _FakeHost(visible=False, live_geometry=(0, 0, 900, 580))
        store = _RecordingStore()
        runtime = _make_runtime(host, store)
        runtime._last_normal_geometry = (100, 100, 1500, 900)
        runtime._schedule_geometry_save = lambda: self.fail(
            "save не должен планироваться для скрытого окна"
        )

        runtime.on_geometry_changed()

        self.assertEqual(runtime._last_normal_geometry, (100, 100, 1500, 900))

    def test_on_geometry_changed_updates_model_for_visible_window(self) -> None:
        host = _FakeHost(visible=True, live_geometry=(70, 80, 1300, 850))
        store = _RecordingStore()
        runtime = _make_runtime(host, store)
        scheduled: list[bool] = []
        runtime._schedule_geometry_save = lambda: scheduled.append(True)

        runtime.on_geometry_changed()

        self.assertEqual(runtime._last_normal_geometry, (70, 80, 1300, 850))
        self.assertEqual(scheduled, [True])


if __name__ == "__main__":
    unittest.main()
