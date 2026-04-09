from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QThread, pyqtSignal

from log import log


class AutostartDetectorWorker(QThread):
    """Background worker that resolves the current autostart type."""

    finished = pyqtSignal(str)

    METHOD_TO_TYPE = {
        "exe": "gui",
        "direct_task": "gui",
        "direct_boot": "gui",
        "direct_service": "gui",
        "service": "gui",
        "task": "gui",
        "direct_task_bat": "gui",
        "direct_boot_bat": "gui",
    }

    def run(self):
        try:
            autostart_type = AutostartPageController.detect_autostart_type()
            self.finished.emit(autostart_type or "")
        except Exception as e:
            log(f"AutostartDetectorWorker error: {e}", "WARNING")
            self.finished.emit("")


@dataclass(slots=True)
class AutostartActionResult:
    ok: bool
    autostart_type: str | None
    strategy_name: str | None = None
    removed_count: int = 0


@dataclass(slots=True)
class AutostartModePlan:
    method: str
    mode_text: str


@dataclass(slots=True)
class AutostartStatusPlan:
    enabled: bool
    active_type: str | None
    status_title: str
    status_description: str
    status_icon_kind: str
    disable_visible: bool
    strategy_text: str


@dataclass(slots=True)
class AutostartOptionState:
    disabled: bool
    is_active: bool


@dataclass(slots=True)
class AutostartShowEventPlan:
    should_schedule_detection: bool
    detection_delay_ms: int


@dataclass(slots=True)
class AutostartDetectionStartPlan:
    should_start: bool


@dataclass(slots=True)
class AutostartDetectionResultPlan:
    detection_pending: bool
    autostart_type: str | None
    enabled: bool


@dataclass(slots=True)
class AutostartAppInitPlan:
    app_instance: object | None
    strategy_name: str | None
    strategy_text: str


class AutostartPageController:
    @staticmethod
    def create_detector_worker() -> AutostartDetectorWorker:
        return AutostartDetectorWorker()

    @staticmethod
    def detect_autostart_type() -> str | None:
        from autostart.registry_check import AutostartRegistryChecker

        if AutostartRegistryChecker.is_autostart_enabled():
            method = AutostartRegistryChecker.get_autostart_method()
            if method and method in AutostartDetectorWorker.METHOD_TO_TYPE:
                return AutostartDetectorWorker.METHOD_TO_TYPE[method]
        return None

    @staticmethod
    def build_show_event_plan(*, spontaneous: bool) -> AutostartShowEventPlan:
        return AutostartShowEventPlan(
            should_schedule_detection=not bool(spontaneous),
            detection_delay_ms=50,
        )

    @staticmethod
    def build_detection_start_plan(*, detection_pending: bool, worker_running: bool) -> AutostartDetectionStartPlan:
        return AutostartDetectionStartPlan(
            should_start=not bool(detection_pending) and not bool(worker_running),
        )

    @staticmethod
    def build_detection_result_plan(autostart_type: str | None) -> AutostartDetectionResultPlan:
        normalized_type = str(autostart_type or "").strip() or None
        return AutostartDetectionResultPlan(
            detection_pending=False,
            autostart_type=normalized_type,
            enabled=bool(normalized_type),
        )

    @staticmethod
    def resolve_app_init_plan(parent_widget, *, strategy_name: str | None, strategy_not_selected_text: str) -> AutostartAppInitPlan:
        app_instance = None
        widget = parent_widget
        while widget is not None:
            if hasattr(widget, "dpi_controller"):
                app_instance = widget
                log("AutostartPage: app_instance найден через parent", "DEBUG")
                break
            widget = widget.parent() if hasattr(widget, "parent") else None

        resolved_strategy = strategy_name
        if app_instance is not None and not resolved_strategy:
            store = getattr(app_instance, "ui_state_store", None)
            if store is not None:
                current = store.snapshot().current_strategy_summary
                if current:
                    resolved_strategy = current

        return AutostartAppInitPlan(
            app_instance=app_instance,
            strategy_name=resolved_strategy,
            strategy_text=resolved_strategy or strategy_not_selected_text,
        )

    @staticmethod
    def disable_autostart() -> AutostartActionResult:
        from autostart.autostart_remove import AutoStartCleaner

        cleaner = AutoStartCleaner()
        removed = int(cleaner.run() or 0)
        return AutostartActionResult(
            ok=True,
            autostart_type=None,
            strategy_name=None,
            removed_count=removed,
        )

    @staticmethod
    def setup_gui_autostart(strategy_name: str | None) -> AutostartActionResult:
        from autostart.autostart_exe import setup_autostart_for_exe

        selected_mode = strategy_name or "Default"
        ok = bool(
            setup_autostart_for_exe(
                selected_mode=selected_mode,
                status_cb=lambda msg: log(msg, "INFO"),
            )
        )
        return AutostartActionResult(
            ok=ok,
            autostart_type="gui" if ok else None,
            strategy_name=strategy_name,
        )

    @staticmethod
    def _collect_direct_strategy(app_instance):
        from autostart.autostart_direct import collect_direct_strategy_args

        if not app_instance:
            return None, None, None
        return collect_direct_strategy_args(app_instance)

    def setup_direct_service(self, app_instance) -> AutostartActionResult:
        from autostart.autostart_direct_service import setup_direct_service

        args, name, winws_exe = self._collect_direct_strategy(app_instance)
        if not args or not winws_exe:
            return AutostartActionResult(False, None, None)

        ok = bool(
            setup_direct_service(
                winws_exe=winws_exe,
                strategy_args=args,
                strategy_name=name,
                ui_error_cb=lambda msg: log(msg, "ERROR"),
            )
        )
        return AutostartActionResult(ok=ok, autostart_type="service" if ok else None, strategy_name=name)

    def setup_direct_logon_task(self, app_instance) -> AutostartActionResult:
        from autostart.autostart_direct import setup_direct_autostart_task

        args, name, winws_exe = self._collect_direct_strategy(app_instance)
        if not args or not winws_exe:
            return AutostartActionResult(False, None, None)

        ok = bool(
            setup_direct_autostart_task(
                winws_exe=winws_exe,
                strategy_args=args,
                strategy_name=name,
                ui_error_cb=lambda msg: log(msg, "ERROR"),
            )
        )
        return AutostartActionResult(ok=ok, autostart_type="logon" if ok else None, strategy_name=name)

    def setup_direct_boot_task(self, app_instance) -> AutostartActionResult:
        from autostart.autostart_direct import setup_direct_autostart_service

        args, name, winws_exe = self._collect_direct_strategy(app_instance)
        if not args or not winws_exe:
            return AutostartActionResult(False, None, None)

        ok = bool(
            setup_direct_autostart_service(
                winws_exe=winws_exe,
                strategy_args=args,
                strategy_name=name,
                ui_error_cb=lambda msg: log(msg, "ERROR"),
            )
        )
        return AutostartActionResult(ok=ok, autostart_type="boot" if ok else None, strategy_name=name)

    @staticmethod
    def build_mode_plan(method: str | None) -> AutostartModePlan:
        normalized = str(method or "").strip()
        if normalized == "direct_zapret2":
            mode_text = "Прямой запуск (Zapret 2)"
        elif normalized == "direct_zapret2_orchestra":
            mode_text = "Оркестратор Zapret 2"
        elif normalized == "orchestra":
            mode_text = "Оркестр (автообучение)"
        elif normalized:
            mode_text = "Классический (BAT файлы)"
        else:
            mode_text = "Неизвестно"
        return AutostartModePlan(method=normalized, mode_text=mode_text)

    @staticmethod
    def build_status_plan(
        *,
        enabled: bool,
        strategy_name: str | None,
        autostart_type: str | None,
        current_strategy_text: str,
        enabled_base_text: str,
        gui_type_text: str,
        disabled_title_text: str,
        disabled_desc_text: str,
        enabled_title_text: str,
        strategy_not_selected_text: str,
    ) -> AutostartStatusPlan:
        enabled = bool(enabled)
        active_type = autostart_type if enabled else None

        if enabled:
            type_desc = ""
            if autostart_type:
                type_map = {"gui": gui_type_text}
                type_desc = type_map.get(autostart_type, "")
            status_description = enabled_base_text if not type_desc else f"{enabled_base_text} {type_desc}"
            strategy_text = strategy_name or current_strategy_text or strategy_not_selected_text
            return AutostartStatusPlan(
                enabled=True,
                active_type=active_type,
                status_title=enabled_title_text,
                status_description=status_description,
                status_icon_kind="enabled",
                disable_visible=True,
                strategy_text=strategy_text,
            )

        strategy_text = strategy_name or current_strategy_text or strategy_not_selected_text
        return AutostartStatusPlan(
            enabled=False,
            active_type=None,
            status_title=disabled_title_text,
            status_description=disabled_desc_text,
            status_icon_kind="disabled",
            disable_visible=False,
            strategy_text=strategy_text,
        )

    @staticmethod
    def build_option_state_map(*, autostart_enabled: bool, active_type: str | None) -> dict[str, AutostartOptionState]:
        if autostart_enabled and active_type:
            return {
                "gui": AutostartOptionState(disabled=True, is_active=active_type == "gui"),
            }
        if autostart_enabled:
            return {
                "gui": AutostartOptionState(disabled=True, is_active=False),
            }
        return {
            "gui": AutostartOptionState(disabled=False, is_active=False),
        }
