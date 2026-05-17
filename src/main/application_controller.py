from __future__ import annotations

from dataclasses import dataclass
import time as _time
from typing import Any

from app.runtime import build_app_runtime
from main.runtime_state import log_startup_metric as emit_startup_metric
from main.tray_window_port import build_tray_window_port
from main.window_feature_ports import build_feature_window_deps
from main.window_feature_deps import build_window_feature_deps
from main.window_page_actions import build_window_page_actions
from main.window_runtime_setup import attach_app_runtime_to_window
from main.window_state_actions import WindowStateActions
from ui.app_window_locator import register_app_window


@dataclass(slots=True)
class ApplicationController:
    """Собирает приложение, но не рисует интерфейс."""

    window_cls: type
    start_in_tray: bool = False
    _window: Any | None = None
    _app_runtime: Any | None = None
    _window_state_actions: WindowStateActions | None = None

    @property
    def window(self) -> Any:
        if self._window is None:
            raise RuntimeError("Главное окно ещё не создано")
        return self._window

    @property
    def app_runtime(self) -> Any:
        if self._app_runtime is None:
            raise RuntimeError("AppRuntime ещё не создан")
        return self._app_runtime

    @property
    def window_state_actions(self) -> WindowStateActions:
        if self._window_state_actions is None:
            raise RuntimeError("WindowStateActions ещё не созданы")
        return self._window_state_actions

    def create_window(self) -> Any:
        if self._window is not None:
            raise RuntimeError("Главное окно уже создано")

        t_window = _time.perf_counter()
        window = self.window_cls(start_in_tray=self.start_in_tray)
        emit_startup_metric(
            "StartupWindowBootstrapWindow",
            f"{(_time.perf_counter() - t_window) * 1000:.0f}ms",
        )
        register_app_window(window)
        tray_window_port = build_tray_window_port(window)
        feature_window_deps = build_feature_window_deps(
            window,
            tray_window_port=tray_window_port,
        )

        def _build_feature_deps(state):
            appearance_actions = WindowStateActions(window=window, ui_state_store=state.ui)
            self._window_state_actions = appearance_actions
            return build_window_feature_deps(
                feature_window_deps,
                appearance_actions=appearance_actions,
            )

        app_runtime = build_app_runtime(
            initial_ui_state=window._build_initial_ui_state(),
            feature_deps_factory=_build_feature_deps,
        )
        attach_app_runtime_to_window(
            window,
            app_runtime,
            page_actions_factory=lambda target_window: build_window_page_actions(
                window=target_window,
                appearance_actions=self.window_state_actions,
            ),
        )
        self._window = window
        self._app_runtime = app_runtime
        return window


__all__ = ["ApplicationController"]
