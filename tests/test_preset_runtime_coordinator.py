from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PyQt6.QtWidgets import QApplication


class PresetRuntimeCoordinatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_saving_active_preset_uses_content_apply_not_preset_switch(self) -> None:
        from core.runtime.preset_runtime_coordinator import PresetRuntimeCoordinator
        from settings.mode import ZAPRET2_MODE

        switch_calls: list[tuple[str, str, str]] = []
        content_calls: list[tuple[str, str, str]] = []
        active_path = "C:/Zapret/Dev/presets/winws2/Default v5.txt"
        presets_feature = SimpleNamespace(
            is_selected_source_preset_file=lambda method, file_name: (
                method == ZAPRET2_MODE and file_name == "Default v5.txt"
            )
        )
        ui_state = SimpleNamespace(
            content_revision=0,
            bump_preset_content_revision=lambda: setattr(
                ui_state,
                "content_revision",
                ui_state.content_revision + 1,
            ),
        )
        coordinator = PresetRuntimeCoordinator(
            presets_feature=presets_feature,
            ui_state_store=ui_state,
            get_launch_method=lambda: ZAPRET2_MODE,
            get_active_preset_path=lambda: active_path,
            refresh_after_switch=lambda: None,
            request_selected_source_preset_apply=lambda method, reason, file_name: switch_calls.append(
                (method, reason, file_name)
            )
            or True,
            request_preset_content_apply=lambda method, reason, file_name: content_calls.append(
                (method, reason, file_name)
            )
            or True,
        )
        coordinator._active_preset_file_path = active_path
        coordinator.setup_active_preset_file_watcher = lambda: None

        coordinator.handle_preset_content_changed(ZAPRET2_MODE, "Default v5.txt")

        self.assertEqual(content_calls, [(ZAPRET2_MODE, "preset_content_changed", "Default v5.txt")])
        self.assertEqual(switch_calls, [])
        self.assertEqual(ui_state.content_revision, 1)

    def test_duplicate_active_preset_content_change_does_not_reapply_same_runtime_payload(self) -> None:
        from core.runtime.preset_runtime_coordinator import PresetRuntimeCoordinator
        from settings.mode import ZAPRET2_MODE

        content_calls: list[tuple[str, str, str]] = []
        ui_state = SimpleNamespace(
            content_revision=0,
            bump_preset_content_revision=lambda: setattr(
                ui_state,
                "content_revision",
                ui_state.content_revision + 1,
            ),
        )
        presets_feature = SimpleNamespace(
            is_selected_source_preset_file=lambda method, file_name: (
                method == ZAPRET2_MODE and file_name == "Default v5.txt"
            )
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            active_path = Path(tmp_dir) / "Default v5.txt"
            active_path.write_text("--new\n--filter-tcp=443\n", encoding="utf-8")
            coordinator = PresetRuntimeCoordinator(
                presets_feature=presets_feature,
                ui_state_store=ui_state,
                get_launch_method=lambda: ZAPRET2_MODE,
                get_active_preset_path=lambda: str(active_path),
                refresh_after_switch=lambda: None,
                request_selected_source_preset_apply=lambda *_args: True,
                request_preset_content_apply=lambda method, reason, file_name: content_calls.append(
                    (method, reason, file_name)
                )
                or True,
            )
            coordinator._active_preset_file_path = str(active_path)
            coordinator.setup_active_preset_file_watcher = lambda: None

            coordinator.handle_preset_content_changed(ZAPRET2_MODE, "Default v5.txt")
            coordinator.handle_preset_content_changed(ZAPRET2_MODE, "Default v5.txt")
            active_path.write_text("--new\n--filter-tcp=80\n", encoding="utf-8")
            coordinator.handle_preset_content_changed(ZAPRET2_MODE, "Default v5.txt")

        self.assertEqual(
            content_calls,
            [
                (ZAPRET2_MODE, "preset_content_changed", "Default v5.txt"),
                (ZAPRET2_MODE, "preset_content_changed", "Default v5.txt"),
            ],
        )
        self.assertEqual(ui_state.content_revision, 3)

    def test_preset_content_fingerprint_does_not_read_file_body_in_qt_handler(self) -> None:
        from core.runtime.preset_runtime_coordinator import PresetRuntimeCoordinator

        source = inspect.getsource(PresetRuntimeCoordinator._build_preset_content_apply_fingerprint)

        self.assertNotIn("open(", source)
        self.assertNotIn(".read(", source)
        self.assertNotIn("hashlib", source)
        self.assertIn("os.stat", source)

    def test_active_preset_revision_is_published_after_click_event(self) -> None:
        from core.runtime.preset_runtime_coordinator import PresetRuntimeCoordinator
        from settings.mode import ZAPRET2_MODE

        class _UiState:
            def __init__(self) -> None:
                self.active_revision = 0

            def bump_active_preset_revision(self) -> None:
                self.active_revision += 1

        ui_state = _UiState()
        coordinator = PresetRuntimeCoordinator(
            presets_feature=SimpleNamespace(),
            ui_state_store=ui_state,
            get_launch_method=lambda: ZAPRET2_MODE,
            get_active_preset_path=lambda: "",
            refresh_after_switch=lambda: None,
            request_selected_source_preset_apply=lambda *_args: True,
            request_preset_content_apply=lambda *_args: True,
        )
        coordinator.setup_active_preset_file_watcher = lambda: None

        coordinator.handle_preset_switched(ZAPRET2_MODE, "Default v5.txt")

        self.assertEqual(ui_state.active_revision, 0)
        self._app.processEvents()
        self.assertEqual(ui_state.active_revision, 1)

    def test_preset_switch_defers_active_file_watcher_setup_after_click_event(self) -> None:
        from core.runtime.preset_runtime_coordinator import PresetRuntimeCoordinator
        from settings.mode import ZAPRET2_MODE

        watcher_calls: list[str] = []
        coordinator = PresetRuntimeCoordinator(
            presets_feature=SimpleNamespace(),
            ui_state_store=None,
            get_launch_method=lambda: ZAPRET2_MODE,
            get_active_preset_path=lambda: "C:/Zapret/Dev/presets/winws2/Default v5.txt",
            refresh_after_switch=lambda: None,
            request_selected_source_preset_apply=lambda *_args: True,
            request_preset_content_apply=lambda *_args: True,
        )
        coordinator.setup_active_preset_file_watcher = lambda: watcher_calls.append("watcher")

        coordinator.handle_preset_switched(ZAPRET2_MODE, "Default v5.txt")

        self.assertEqual(watcher_calls, [])
        self._app.processEvents()
        self.assertEqual(watcher_calls, ["watcher"])

    def test_get_selected_source_path_does_not_build_launch_snapshot(self) -> None:
        import inspect

        from presets import commands as preset_commands

        source = inspect.getsource(preset_commands.get_selected_source_path)

        self.assertNotIn("get_launch_snapshot", source)
        self.assertIn("preset_mode_coordinator.get_selected_source_path", source)

    def test_preset_switch_apply_runs_next_event_loop_turn_without_visible_debounce(self) -> None:
        from core.runtime.preset_runtime_coordinator import PresetRuntimeCoordinator
        from settings.mode import ZAPRET2_MODE

        class _Signal:
            def __init__(self) -> None:
                self.callback = None

            def connect(self, callback) -> None:
                self.callback = callback

        class _FakeTimer:
            instances = []

            def __init__(self, *_args, **_kwargs) -> None:
                self.timeout = _Signal()
                self.delay_ms = None
                _FakeTimer.instances.append(self)

            def setSingleShot(self, _single_shot: bool) -> None:
                pass

            def start(self, delay_ms: int) -> None:
                self.delay_ms = int(delay_ms)

            def fire(self) -> None:
                self.timeout.callback()

        switch_calls: list[tuple[str, str, str]] = []
        coordinator = PresetRuntimeCoordinator(
            presets_feature=SimpleNamespace(),
            ui_state_store=None,
            get_launch_method=lambda: ZAPRET2_MODE,
            get_active_preset_path=lambda: "",
            refresh_after_switch=lambda: None,
            request_selected_source_preset_apply=lambda method, reason, file_name: switch_calls.append(
                (method, reason, file_name)
            )
            or True,
            request_preset_content_apply=lambda *_args: True,
        )
        coordinator.setup_active_preset_file_watcher = lambda: None

        with patch("core.runtime.preset_runtime_coordinator.QTimer", _FakeTimer):
            coordinator.handle_preset_switched(ZAPRET2_MODE, "Default v5.txt")

            apply_timers = [
                timer
                for timer in _FakeTimer.instances
                if getattr(timer.timeout.callback, "__name__", "") == "_apply_pending_selected_source_preset"
            ]
            self.assertEqual(len(apply_timers), 1)
            self.assertEqual(apply_timers[0].delay_ms, 0)
            self.assertEqual(switch_calls, [])

            apply_timers[0].fire()

        self.assertEqual(switch_calls, [(ZAPRET2_MODE, "preset_switched", "Default v5.txt")])

    def test_reapplying_same_preset_skips_ui_refresh_and_runtime_apply(self) -> None:
        from core.runtime.preset_runtime_coordinator import PresetRuntimeCoordinator
        from settings.mode import ZAPRET2_MODE

        switch_calls: list[tuple[str, str, str]] = []
        refresh_calls: list[str] = []

        ui_state = SimpleNamespace(
            active_revision=0,
            bump_active_preset_revision=lambda: setattr(
                ui_state,
                "active_revision",
                ui_state.active_revision + 1,
            ),
        )
        coordinator = PresetRuntimeCoordinator(
            presets_feature=SimpleNamespace(),
            ui_state_store=ui_state,
            get_launch_method=lambda: ZAPRET2_MODE,
            get_active_preset_path=lambda: "",
            refresh_after_switch=lambda: refresh_calls.append("refresh"),
            request_selected_source_preset_apply=lambda method, reason, file_name: switch_calls.append(
                (method, reason, file_name)
            )
            or True,
            request_preset_content_apply=lambda *_args: True,
        )
        coordinator.setup_active_preset_file_watcher = lambda: None

        coordinator.handle_preset_switched(ZAPRET2_MODE, "Default v5.txt")
        self._app.processEvents()
        coordinator.handle_preset_switched(ZAPRET2_MODE, "Default v5.txt")
        self._app.processEvents()

        self.assertEqual(
            switch_calls,
            [
                (ZAPRET2_MODE, "preset_switched", "Default v5.txt"),
            ],
        )
        self.assertEqual(ui_state.active_revision, 1)
        self.assertEqual(refresh_calls, ["refresh"])

    def test_selecting_same_preset_file_does_not_emit_switch_signal(self) -> None:
        from presets.file_service import PresetFileService
        from presets.models import PresetManifest
        from settings.mode import ENGINE_WINWS2, ZAPRET2_MODE

        manifest = PresetManifest(
            file_name="Default v5.txt",
            name="Default v5",
            updated_at="",
            kind="user",
        )
        notified: list[str] = []

        class _PresetModeCoordinator:
            def get_selected_source_manifest(self, _launch_method):
                return manifest

            def select_preset_file_name(self, _launch_method, _file_name):
                return SimpleNamespace(preset_file_name=manifest.file_name)

        class _PresetFileStore:
            def resolve_file_name(self, _engine, file_name):
                return file_name

        class _PresetUiStore:
            def notify_preset_switched(self, file_name):
                notified.append(file_name)

        store = _PresetUiStore()
        service = PresetFileService(
            engine=ENGINE_WINWS2,
            launch_method=ZAPRET2_MODE,
            app_paths=object(),
            preset_mode_coordinator=_PresetModeCoordinator(),
            preset_file_store=_PresetFileStore(),
            preset_selection_service=object(),
            preset_store_winws2=store,
            preset_store_winws1=store,
        )

        service.select_file_name("Default v5.txt")

        self.assertEqual(notified, [])

    def test_raw_editor_can_save_active_preset_without_publishing_until_commit(self) -> None:
        from presets.raw_preset_editor_workflow import RawPresetEditorController
        from settings.mode import ZAPRET2_MODE

        save_calls: list[tuple[str, str, str, bool]] = []
        publish_calls: list[tuple[str, str]] = []

        class _PresetsFeature:
            def save_preset_source_by_file_name(
                self,
                launch_method,
                file_name,
                source_text,
                *,
                publish_content_changed=True,
            ):
                save_calls.append((launch_method, file_name, source_text, publish_content_changed))
                return type("Manifest", (), {"name": "Default v5", "file_name": file_name})()

            def get_preset_source_path_by_file_name(self, _launch_method, file_name):
                from pathlib import Path

                return Path("C:/Zapret/Dev/presets/winws2") / file_name

            def publish_preset_content_changed(self, launch_method, file_name):
                publish_calls.append((launch_method, file_name))

        feature = _PresetsFeature()
        controller = RawPresetEditorController(
            save_preset_source_by_file_name=feature.save_preset_source_by_file_name,
            get_preset_source_path_by_file_name=feature.get_preset_source_path_by_file_name,
            get_preset_manifest_by_file_name=Mock(),
            open_preset_source_file=Mock(),
            rename_preset_by_file_name=Mock(),
            duplicate_preset_by_file_name=Mock(),
            export_preset_plain_text=Mock(),
            reset_preset_to_builtin_by_file_name=Mock(),
            delete_preset_by_file_name=Mock(),
            get_selected_source_preset_manifest=Mock(return_value=None),
            get_selected_source_preset_file_name=Mock(return_value=""),
            activate_preset_file=Mock(),
            publish_preset_content_changed=feature.publish_preset_content_changed,
            launch_method=ZAPRET2_MODE,
        )

        controller.save_text(
            file_name="Default v5.txt",
            source_text="--new\n--filter-tcp=80\n",
            publish_content_changed=False,
        )
        controller.publish_content_changed("Default v5.txt")

        self.assertEqual(
            save_calls,
            [(ZAPRET2_MODE, "Default v5.txt", "--new\n--filter-tcp=80\n", False)],
        )
        self.assertEqual(publish_calls, [(ZAPRET2_MODE, "Default v5.txt")])

    def test_preset_content_apply_switches_running_preset_once(self) -> None:
        from pathlib import Path
        import tempfile
        from unittest.mock import Mock

        from winws_runtime.flow.apply_policy import request_preset_runtime_content_apply
        from settings.mode import ZAPRET2_MODE

        with tempfile.TemporaryDirectory() as tmp_dir:
            preset_path = Path(tmp_dir) / "selected.txt"
            preset_path.write_text(
                "--wf-tcp-out=80,443\n--filter-tcp=80\n--hostlist=list.txt\n--lua-desync=fake\n",
                encoding="utf-8",
            )

            launch_runtime = SimpleNamespace(
                is_running=Mock(return_value=True),
                switch_presets_async=Mock(),
                stop_dpi_async=Mock(),
            )
            presets_feature = SimpleNamespace(
                get_launch_snapshot=Mock(return_value=SimpleNamespace(preset_path=str(preset_path)))
            )
            runtime_feature = SimpleNamespace(
                objects=SimpleNamespace(launch_runtime=launch_runtime),
                dependencies=SimpleNamespace(presets_feature=presets_feature),
            )

            self.assertTrue(
                request_preset_runtime_content_apply(
                    runtime_feature=runtime_feature,
                    launch_method=ZAPRET2_MODE,
                    reason="preset_content_changed",
                )
            )

            launch_runtime.switch_presets_async.assert_called_once_with(ZAPRET2_MODE, delay_ms=900)
            launch_runtime.stop_dpi_async.assert_not_called()

    def test_preset_content_apply_does_not_validate_preset_on_ui_request_path(self) -> None:
        from pathlib import Path
        import tempfile
        from unittest.mock import Mock

        from winws_runtime.flow.apply_policy import request_preset_runtime_content_apply
        from settings.mode import ZAPRET2_MODE

        with tempfile.TemporaryDirectory() as tmp_dir:
            preset_path = Path(tmp_dir) / "selected.txt"
            preset_path.write_text(
                "--wf-tcp-out=80,443\n--filter-tcp=80\n--hostlist=list.txt\n--lua-desync=fake\n",
                encoding="utf-8",
            )

            launch_runtime = SimpleNamespace(
                is_running=Mock(return_value=True),
                switch_presets_async=Mock(),
                stop_dpi_async=Mock(),
            )
            presets_feature = SimpleNamespace(
                get_launch_snapshot=Mock(return_value=SimpleNamespace(preset_path=str(preset_path)))
            )
            runtime_feature = SimpleNamespace(
                objects=SimpleNamespace(launch_runtime=launch_runtime),
                dependencies=SimpleNamespace(presets_feature=presets_feature),
            )

            with patch.object(
                Path,
                "read_text",
                side_effect=AssertionError("preset reading must run in the preset switch worker"),
            ):
                self.assertTrue(
                    request_preset_runtime_content_apply(
                        runtime_feature=runtime_feature,
                        launch_method=ZAPRET2_MODE,
                        reason="preset_content_changed",
                    )
                )

            launch_runtime.switch_presets_async.assert_called_once_with(ZAPRET2_MODE, delay_ms=900)
            launch_runtime.stop_dpi_async.assert_not_called()

    def test_preset_content_publish_refreshes_launch_snapshot_before_signal(self) -> None:
        from presets.file_service import PresetFileService
        from presets.models import PresetManifest
        from settings.mode import ENGINE_WINWS2, ZAPRET2_MODE

        manifest = PresetManifest(
            file_name="Default v5.txt",
            name="Default v5",
            updated_at="",
        )
        launch_snapshot_refreshed = False
        events: list[tuple[str, bool]] = []

        class _PresetModeCoordinator:
            def get_selected_source_manifest(self, _launch_method):
                return manifest

            def refresh_selected_launch_preset(self, _launch_method):
                nonlocal launch_snapshot_refreshed
                launch_snapshot_refreshed = True
                events.append(("refresh", launch_snapshot_refreshed))
                return object()

        class _PresetFileStore:
            def get_manifest(self, _engine, _file_name):
                return manifest

            def resolve_file_name(self, _engine, file_name):
                return file_name

        class _PresetUiStore:
            def notify_preset_content_changed(self, _file_name):
                events.append(("notify", launch_snapshot_refreshed))

        store = _PresetUiStore()
        service = PresetFileService(
            engine=ENGINE_WINWS2,
            launch_method=ZAPRET2_MODE,
            app_paths=object(),
            preset_mode_coordinator=_PresetModeCoordinator(),
            preset_file_store=_PresetFileStore(),
            preset_selection_service=object(),
            preset_store_winws2=store,
            preset_store_winws1=store,
        )

        service.publish_preset_content_changed_by_file_name("Default v5.txt")

        self.assertEqual(events, [("refresh", True), ("notify", True)])

    def test_reset_selected_preset_refreshes_launch_snapshot_before_signal(self) -> None:
        from pathlib import Path
        import tempfile

        from presets.models import PresetManifest
        from presets.preset_file_ops import reset_to_builtin_by_file_name
        from settings.mode import ENGINE_WINWS2

        manifest = PresetManifest(
            file_name="Default v5.txt",
            name="Default v5",
            updated_at="",
            kind="user",
        )
        updated = PresetManifest(
            file_name="Default v5.txt",
            name="Default v5",
            updated_at="",
            kind="builtin",
        )
        launch_snapshot_refreshed = False
        deleted = False
        events: list[tuple[str, bool]] = []

        class _EnginePaths:
            def __init__(self, builtin_dir: Path) -> None:
                self.builtin_presets_dir = builtin_dir

            def ensure_directories(self):
                return self

        class _AppPaths:
            def __init__(self, builtin_dir: Path) -> None:
                self._builtin_dir = builtin_dir

            def engine_paths(self, _engine):
                return _EnginePaths(self._builtin_dir)

        class _PresetFileStore:
            def delete_preset(self, _engine, _file_name):
                nonlocal deleted
                deleted = True

        class _Backend:
            engine = ENGINE_WINWS2
            preset_file_store = _PresetFileStore()

            def __init__(self, builtin_dir: Path) -> None:
                self.app_paths = _AppPaths(builtin_dir)

            def get_manifest_by_file_name(self, _file_name):
                return updated if deleted else manifest

            def is_selected_file_name(self, _file_name):
                return True

            def _refresh_selected_source_preset(self):
                nonlocal launch_snapshot_refreshed
                launch_snapshot_refreshed = True
                events.append(("refresh", launch_snapshot_refreshed))

            def notify_preset_content_changed(self, _file_name):
                events.append(("notify", launch_snapshot_refreshed))

        with tempfile.TemporaryDirectory() as tmp_dir:
            builtin_dir = Path(tmp_dir)
            (builtin_dir / manifest.file_name).write_text("--new\n", encoding="utf-8")

            reset_to_builtin_by_file_name(_Backend(builtin_dir), manifest.file_name)

        self.assertEqual(events, [("refresh", True), ("notify", True)])


if __name__ == "__main__":
    unittest.main()
