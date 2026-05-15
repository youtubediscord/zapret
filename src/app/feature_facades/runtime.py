from __future__ import annotations

from dataclasses import InitVar
from dataclasses import dataclass
from dataclasses import field
from typing import Any

from app.feature_facades.runtime_parts import RuntimeCommandPort
from app.feature_facades.runtime_parts import RuntimeDependencies
from app.feature_facades.runtime_parts import RuntimeEvents
from app.feature_facades.runtime_parts import RuntimeFlags
from app.feature_facades.runtime_parts import RuntimeLifecyclePort
from app.feature_facades.runtime_parts import RuntimeObjects
from app.feature_facades.runtime_parts import RuntimeUiPort


@dataclass(slots=True)
class RuntimeFeature:
    qt_parent: InitVar[Any] = None
    runtime_service: InitVar[Any] = None
    presets_feature: InitVar[Any] = None
    profile_feature: InitVar[Any] = None
    ui_state: InitVar[Any] = None
    orchestra_feature: InitVar[Any] = None
    startup_state: InitVar[Any] = None
    mark_stop_and_exit_requested: InitVar[Any] = None
    ui_port: RuntimeUiPort = field(init=False)
    lifecycle: RuntimeLifecyclePort = field(init=False)
    dependencies: RuntimeDependencies = field(init=False)
    flags: RuntimeFlags = field(init=False)
    objects: RuntimeObjects = field(init=False)
    events: RuntimeEvents = field(init=False)
    commands: RuntimeCommandPort = field(init=False)

    def __post_init__(
        self,
        qt_parent: Any,
        runtime_service: Any,
        presets_feature: Any,
        profile_feature: Any,
        ui_state: Any,
        orchestra_feature: Any,
        startup_state: Any,
        mark_stop_and_exit_requested: Any,
    ) -> None:
        self.ui_port = RuntimeUiPort()
        self.lifecycle = RuntimeLifecyclePort(
            startup_state=startup_state,
            qt_parent=qt_parent,
            mark_stop_and_exit_requested_callback=mark_stop_and_exit_requested,
        )
        self.dependencies = RuntimeDependencies(
            presets_feature=presets_feature,
            profile_feature=profile_feature,
            orchestra_feature=orchestra_feature,
        )
        self.flags = RuntimeFlags()
        self.objects = RuntimeObjects(runtime_service=runtime_service)
        self.events = RuntimeEvents(
            runtime_service=runtime_service,
            ui_port=self.ui_port,
            ui_state=ui_state,
            qt_parent=self.lifecycle.qt_parent,
        )
        self.commands = RuntimeCommandPort(self)

    def is_available(self) -> bool:
        return self.objects.is_available()

    def is_running(self) -> bool:
        return self.objects.is_running()

    def is_any_running(self, *, silent: bool = True) -> bool:
        return self.objects.is_any_running(silent=silent)

    def current_strategy_runner(self):
        return self.commands.current_strategy_runner()

    def configure_runtime_ui_bridge(self, bridge) -> None:
        self.ui_port.configure_runtime_ui_bridge(bridge)

    def snapshot(self):
        return self.objects.snapshot()

    def init_launch_runtime_api(self) -> None:
        self.commands.init_launch_runtime_api()

    def configure_notifications(self, *, notify) -> None:
        self.ui_port.configure_notifications(notify=notify)

    def init_launch_runtime(self) -> None:
        self.commands.init_launch_runtime()

    def init_process_monitor(self) -> None:
        self.commands.init_process_monitor()

    def cleanup_process_monitor(self) -> None:
        self.objects.cleanup_process_monitor()

    def init_core_startup(self) -> None:
        self.commands.init_core_startup()

    def start(
        self,
        selected_mode: Any = None,
        launch_method: Any = None,
        *,
        skip_conflict_prompt: bool = False,
        startup_autostart: bool = False,
    ) -> bool:
        return self.commands.start(
            selected_mode=selected_mode,
            launch_method=launch_method,
            skip_conflict_prompt=skip_conflict_prompt,
            startup_autostart=startup_autostart,
        )

    def transition_pipeline_in_progress(self, launch_method: str | None = None) -> bool:
        return self.objects.transition_pipeline_in_progress(launch_method)

    def stop(
        self,
        *,
        force_cleanup: bool = False,
        cleanup_services: bool = False,
    ) -> bool:
        return self.commands.stop(
            force_cleanup=force_cleanup,
            cleanup_services=cleanup_services,
        )

    def restart(self, *, force_full_stop: bool = False) -> bool:
        return self.commands.restart(force_full_stop=force_full_stop)

    def switch_preset(self, method: str | None = None) -> bool:
        return self.commands.switch_preset(method)

    def stop_and_exit(self) -> bool:
        return self.commands.stop_and_exit()

    def cleanup_threads(self) -> bool:
        return self.commands.cleanup_threads()

    def shutdown_sync(
        self,
        *,
        reason: str = "",
        include_cleanup: bool = True,
        cleanup_services: bool = True,
        update_runtime_state: bool = True,
    ):
        return self.commands.shutdown_sync(
            reason=reason,
            include_cleanup=include_cleanup,
            cleanup_services=cleanup_services,
            update_runtime_state=update_runtime_state,
        )

    def start_autostart(self, launch_method: str | None = None) -> bool:
        return self.commands.start_autostart(launch_method)

    def handle_launch_method_changed(self, method: str, *, set_status=None):
        return self.commands.handle_launch_method_changed(method, set_status=set_status)

    def apply_selected_source_preset(
        self,
        *,
        launch_method: str,
        reason: str,
        preset_file_name: str = "",
    ) -> bool:
        return self.commands.apply_selected_source_preset(
            launch_method=launch_method,
            reason=reason,
            preset_file_name=preset_file_name,
        )

    def apply_preset_content(
        self,
        *,
        launch_method: str,
        reason: str,
        profile_key: str | None = None,
    ) -> bool:
        return self.commands.apply_preset_content(
            launch_method=launch_method,
            reason=reason,
            profile_key=profile_key,
        )

    def create_preset_runtime_coordinator(self, **kwargs):
        return self.commands.create_preset_runtime_coordinator(**kwargs)

    def resume_start_after_conflict_resolution(
        self,
        request_id: int,
        *,
        close_conflicts: bool,
    ) -> bool:
        return self.commands.resume_start_after_conflict_resolution(
            request_id,
            close_conflicts=close_conflicts,
        )

    def cancel_start_after_conflict_prompt(self, request_id: int) -> bool:
        return self.commands.cancel_start_after_conflict_prompt(request_id)

    def execute_windivert_autofix(self, action: str) -> tuple[bool, str]:
        return self.commands.execute_windivert_autofix(action)


def build_runtime_feature(
    *,
    qt_parent,
    startup_state,
    mark_stop_and_exit_requested,
    state,
    presets_feature,
    profile_feature,
    orchestra_feature,
) -> RuntimeFeature:
    from winws_runtime.public import LaunchRuntimeService

    return RuntimeFeature(
        qt_parent=qt_parent,
        runtime_service=LaunchRuntimeService(state.ui),
        presets_feature=presets_feature,
        profile_feature=profile_feature,
        ui_state=state.ui,
        orchestra_feature=orchestra_feature,
        startup_state=startup_state,
        mark_stop_and_exit_requested=mark_stop_and_exit_requested,
    )
