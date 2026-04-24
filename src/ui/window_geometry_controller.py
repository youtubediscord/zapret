from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication

from log.log import log



@dataclass(slots=True)
class StoredWindowGeometry:
    position: tuple[int, int] | None
    size: tuple[int, int] | None
    maximized: bool


class RegistryWindowGeometryStore:
    """Низкоуровневое хранилище геометрии окна в config/registry слое."""

    def load(self) -> StoredWindowGeometry:
        from config.window_geometry_store import get_window_maximized, get_window_position, get_window_size


        return StoredWindowGeometry(
            position=get_window_position(),
            size=get_window_size(),
            maximized=bool(get_window_maximized()),
        )

    def save_geometry(self, x: int, y: int, width: int, height: int) -> None:
        from config.window_geometry_store import set_window_position, set_window_size


        set_window_position(int(x), int(y))
        set_window_size(int(width), int(height))

    def save_maximized(self, maximized: bool) -> None:
        from config.window_geometry_store import set_window_maximized


        set_window_maximized(bool(maximized))


class WindowGeometryController:
    """Единый источник истины для геометрии и режима окна."""

    def __init__(
        self,
        host,
        *,
        min_width: int,
        min_height: int,
        default_width: int,
        default_height: int,
        store: RegistryWindowGeometryStore | None = None,
    ) -> None:
        self.host = host
        self.min_width = int(min_width)
        self.min_height = int(min_height)
        self.default_width = int(default_width)
        self.default_height = int(default_height)
        self.store = store or RegistryWindowGeometryStore()

        self._restore_in_progress = False
        self._persistence_enabled = False
        self._pending_restore_maximized = False
        self._applied_saved_maximize_state = False
        self._last_normal_geometry: tuple[int, int, int, int] | None = None
        self._last_persisted_geometry: tuple[int, int, int, int] | None = None
        self._last_persisted_maximized: bool | None = None
        self._pending_window_maximized_state: bool | None = None
        self._window_fsm_active = False
        self._window_fsm_target_mode: str | None = None
        self._window_fsm_retry_count = 0
        self._last_non_minimized_zoomed = False
        self._window_zoom_visual_state: bool | None = None

        self._geometry_save_timer = QTimer(host)
        self._geometry_save_timer.setSingleShot(True)
        self._geometry_save_timer.setInterval(450)
        self._geometry_save_timer.timeout.connect(self._persist_geometry_now)

        self._window_state_settle_timer = QTimer(host)
        self._window_state_settle_timer.setSingleShot(True)
        self._window_state_settle_timer.setInterval(180)
        self._window_state_settle_timer.timeout.connect(self._on_window_state_settle_timeout)

        self._window_maximized_persist_timer = QTimer(host)
        self._window_maximized_persist_timer.setSingleShot(True)
        self._window_maximized_persist_timer.setInterval(140)
        self._window_maximized_persist_timer.timeout.connect(self._persist_window_maximized_state_now)

    def restore_geometry(self) -> None:
        """Восстанавливает сохранённую позицию, размер и maximized-флаг окна."""
        self._restore_in_progress = True
        try:
            saved = self.store.load()

            screen_geometry = QApplication.primaryScreen().availableGeometry()
            screens = QApplication.screens()

            def _looks_like_legacy_maximized_geometry(width: int, height: int) -> bool:
                if not saved.maximized:
                    return False
                for screen in screens:
                    rect = screen.availableGeometry()
                    if width >= (rect.width() - 4) and height >= (rect.height() - 4):
                        return True
                return False

            if saved.size:
                width, height = saved.size
                if _looks_like_legacy_maximized_geometry(width, height):
                    log(
                        "Обнаружена legacy normal-геометрия (размер почти как fullscreen); используем размер по умолчанию",
                        "WARNING",
                    )
                    width, height = self.default_width, self.default_height

                if width >= self.min_width and height >= self.min_height:
                    self.host.resize(width, height)
                    log(f"Восстановлен размер окна: {width}x{height}", "DEBUG")
                else:
                    log(
                        f"Сохраненный размер слишком мал ({width}x{height}), используем по умолчанию",
                        "DEBUG",
                    )
                    self.host.resize(self.default_width, self.default_height)
            else:
                self.host.resize(self.default_width, self.default_height)

            if saved.position:
                x, y = saved.position
                is_visible = False
                for screen in screens:
                    screen_rect = screen.availableGeometry()
                    if (
                        x + 100 > screen_rect.left()
                        and x < screen_rect.right()
                        and y + 100 > screen_rect.top()
                        and y < screen_rect.bottom()
                    ):
                        is_visible = True
                        break

                if is_visible:
                    self.host.move(x, y)
                    log(f"Восстановлена позиция окна: ({x}, {y})", "DEBUG")
                else:
                    self.host.move(
                        screen_geometry.center().x() - self.host.width() // 2,
                        screen_geometry.center().y() - self.host.height() // 2,
                    )
                    log("Сохраненная позиция за пределами экранов, окно отцентрировано", "WARNING")
            else:
                self.host.move(
                    screen_geometry.center().x() - self.host.width() // 2,
                    screen_geometry.center().y() - self.host.height() // 2,
                )
                log("Позиция не сохранена, окно отцентрировано", "DEBUG")

            self._last_normal_geometry = (
                int(self.host.x()),
                int(self.host.y()),
                int(self.host.width()),
                int(self.host.height()),
            )
            self._last_non_minimized_zoomed = bool(saved.maximized)
            self._pending_restore_maximized = bool(saved.maximized)
        except Exception as e:
            log(f"Ошибка восстановления геометрии окна: {e}", "ERROR")
            self.host.resize(self.default_width, self.default_height)
        finally:
            self._restore_in_progress = False

    def enable_persistence(self) -> None:
        self._persistence_enabled = True

    def is_zoomed(self) -> bool:
        state = None
        try:
            state = self.host.windowState()
        except Exception:
            state = None

        try:
            if self.host.isMaximized() or self.host.isFullScreen():
                return True
        except Exception:
            pass

        if state is not None:
            try:
                if state & Qt.WindowState.WindowMaximized:
                    return True
                if state & Qt.WindowState.WindowFullScreen:
                    return True
            except Exception:
                pass

        if state is None:
            return bool(self._last_non_minimized_zoomed)

        return False

    def detect_mode(self) -> str:
        if self._is_window_minimized_state():
            return "minimized"
        if self.is_zoomed():
            return "maximized"
        return "normal"

    def request_zoom_state(self, maximize: bool) -> bool:
        self._pending_restore_maximized = False
        target_mode = "maximized" if bool(maximize) else "normal"
        resulting_mode = self._request_window_mode(target_mode)
        if resulting_mode == "minimized":
            return bool(self._last_non_minimized_zoomed)
        return bool(resulting_mode == "maximized")

    def request_minimize(self) -> bool:
        resulting_mode = self._request_window_mode("minimized")
        return bool(resulting_mode == "minimized" or self._is_window_minimized_state())

    def restore_from_zoom_for_drag(self) -> bool:
        current_mode = self.detect_mode()
        current_zoomed = current_mode == "maximized"

        if not current_zoomed and not (
            self._window_fsm_active and self._window_fsm_target_mode == "maximized"
        ):
            return False

        self.request_zoom_state(False)

        if self.is_zoomed():
            if not self._apply_window_mode_command("normal"):
                return False

        actual_mode = self.detect_mode()
        if actual_mode != "maximized":
            self._finish_window_fsm_transition(actual_mode)

        return bool(actual_mode != "maximized")

    def toggle_maximize_restore(self) -> bool:
        if self._window_fsm_active and self._window_fsm_target_mode in ("normal", "maximized"):
            current_zoomed = bool(self._window_fsm_target_mode == "maximized")
        else:
            current_mode = self.detect_mode()
            if current_mode == "minimized":
                current_zoomed = bool(self._last_non_minimized_zoomed)
            else:
                current_zoomed = bool(current_mode == "maximized")

        return bool(self.request_zoom_state(not current_zoomed))

    def on_geometry_changed(self) -> None:
        if self._restore_in_progress:
            return

        try:
            if self.host.isMinimized() or self.is_zoomed():
                return
        except Exception:
            return

        self._last_normal_geometry = (
            int(self.host.x()),
            int(self.host.y()),
            int(self.host.width()),
            int(self.host.height()),
        )
        self._schedule_geometry_save()

    def on_window_state_change(self) -> None:
        current_mode = self.detect_mode()

        if self._window_fsm_active and self._window_fsm_target_mode is not None:
            target_mode = str(self._window_fsm_target_mode)
            if current_mode == target_mode:
                self._finish_window_fsm_transition(current_mode)
            elif target_mode != "minimized":
                self._apply_window_zoom_visual_state(target_mode == "maximized")
        elif current_mode != "minimized":
            zoomed = bool(current_mode == "maximized")
            self._last_non_minimized_zoomed = zoomed
            self._apply_window_zoom_visual_state(zoomed)
            self._schedule_window_maximized_persist(zoomed)

    def apply_saved_maximized_state_if_needed(self) -> None:
        if self._applied_saved_maximize_state:
            return

        self._applied_saved_maximize_state = True
        pending_restore_maximized = bool(self._pending_restore_maximized)
        self._pending_restore_maximized = False

        if pending_restore_maximized:
            try:
                if not self.is_zoomed():
                    self._restore_in_progress = True
                    self.request_zoom_state(True)
            except Exception:
                pass
            finally:
                self._restore_in_progress = False

    def persist_now(self, force: bool = False) -> None:
        self._persist_geometry_now(force=force)

    def remembered_zoom_state(self) -> bool:
        current_mode = self.detect_mode()
        if current_mode == "minimized":
            return bool(self._last_non_minimized_zoomed)
        return bool(current_mode == "maximized")

    def _apply_window_zoom_visual_state(self, is_zoomed: bool) -> None:
        zoomed = bool(is_zoomed)
        if self._window_zoom_visual_state is zoomed:
            return

        self._window_zoom_visual_state = zoomed
        self._last_non_minimized_zoomed = zoomed

        if hasattr(self.host, "_update_border_radius"):
            self.host._update_border_radius(not zoomed)

        if hasattr(self.host, "_set_handles_visible"):
            self.host._set_handles_visible(not zoomed)

    def _schedule_window_maximized_persist(self, is_zoomed: bool) -> None:
        self._pending_window_maximized_state = bool(is_zoomed)
        try:
            self._window_maximized_persist_timer.start()
        except Exception:
            self._persist_window_maximized_state_now()

    def _persist_window_maximized_state_now(self) -> None:
        state = self._pending_window_maximized_state
        if state is None:
            return

        self._pending_window_maximized_state = None
        state_bool = bool(state)

        try:
            if self._last_persisted_maximized != state_bool:
                self.store.save_maximized(state_bool)
                self._last_persisted_maximized = state_bool
        except Exception as e:
            log(f"Ошибка сохранения состояния maximized: {e}", "DEBUG")

    def _apply_window_mode_command(self, mode: str) -> bool:
        mode_str = str(mode)

        try:
            if mode_str == "maximized":
                self.host.showMaximized()
            elif mode_str == "normal":
                self.host.showNormal()
            elif mode_str == "minimized":
                self.host.showMinimized()
            else:
                return False
            return True
        except Exception:
            pass

        try:
            state = self.host.windowState()
        except Exception:
            state = Qt.WindowState.WindowNoState

        try:
            if mode_str == "maximized":
                state = state & ~Qt.WindowState.WindowMinimized
                state = state & ~Qt.WindowState.WindowFullScreen
                state = state | Qt.WindowState.WindowMaximized
            elif mode_str == "normal":
                state = state & ~Qt.WindowState.WindowMinimized
                state = state & ~Qt.WindowState.WindowMaximized
                state = state & ~Qt.WindowState.WindowFullScreen
            elif mode_str == "minimized":
                state = state & ~Qt.WindowState.WindowFullScreen
                state = state | Qt.WindowState.WindowMinimized
            else:
                return False

            self.host.setWindowState(state)
            return True
        except Exception:
            return False

    def _start_window_fsm_transition(self, target_mode: str) -> None:
        self._window_fsm_active = True
        self._window_fsm_target_mode = str(target_mode)
        self._window_fsm_retry_count = 0

        if self._window_fsm_target_mode != "minimized":
            self._apply_window_zoom_visual_state(self._window_fsm_target_mode == "maximized")

        self._apply_window_mode_command(self._window_fsm_target_mode)

        try:
            self._window_state_settle_timer.start()
        except Exception:
            pass

    def _finish_window_fsm_transition(self, actual_mode: str | None = None) -> None:
        mode = str(actual_mode) if actual_mode is not None else str(self.detect_mode())

        self._window_fsm_active = False
        self._window_fsm_target_mode = None
        self._window_fsm_retry_count = 0

        try:
            self._window_state_settle_timer.stop()
        except Exception:
            pass

        if mode == "minimized":
            return

        zoomed = mode == "maximized"
        self._last_non_minimized_zoomed = zoomed
        self._apply_window_zoom_visual_state(zoomed)
        self._schedule_window_maximized_persist(zoomed)

    def _on_window_state_settle_timeout(self) -> None:
        if not self._window_fsm_active:
            return

        target_mode = self._window_fsm_target_mode
        if target_mode is None:
            return

        actual_mode = self.detect_mode()
        if actual_mode == target_mode:
            self._finish_window_fsm_transition(actual_mode)
            return

        if self._window_fsm_retry_count < 2:
            self._window_fsm_retry_count += 1
            self._apply_window_mode_command(target_mode)
            try:
                self._window_state_settle_timer.start()
            except Exception:
                pass
            return

        self._finish_window_fsm_transition(actual_mode)

    def _request_window_mode(self, target_mode: str) -> str:
        mode = str(target_mode)
        if mode not in ("normal", "maximized", "minimized"):
            return self.detect_mode()

        if self._window_fsm_active and self._window_fsm_target_mode == mode:
            return mode

        current_mode = self.detect_mode()
        if not self._window_fsm_active and current_mode == mode:
            try:
                if not self.host.isVisible():
                    self._apply_window_mode_command(mode)
            except Exception:
                pass
            self._finish_window_fsm_transition(current_mode)
            return current_mode

        self._start_window_fsm_transition(mode)
        return mode

    def _is_window_minimized_state(self) -> bool:
        try:
            if self.host.isMinimized():
                return True
        except Exception:
            pass

        try:
            return bool(self.host.windowState() & Qt.WindowState.WindowMinimized)
        except Exception:
            return False

    def _schedule_geometry_save(self) -> None:
        if not self._persistence_enabled or self._restore_in_progress:
            return
        if getattr(self.host, "_is_exiting", False):
            return

        try:
            if self.host.isMinimized():
                return
        except Exception:
            return

        try:
            self._geometry_save_timer.start()
        except Exception:
            pass

    def _get_normal_geometry_to_save(self, is_maximized: bool) -> tuple[int, int, int, int] | None:
        if not is_maximized:
            return (int(self.host.x()), int(self.host.y()), int(self.host.width()), int(self.host.height()))

        try:
            normal_geo = self.host.normalGeometry()
            width = int(normal_geo.width())
            height = int(normal_geo.height())
            if width > 0 and height > 0:
                return (int(normal_geo.x()), int(normal_geo.y()), width, height)
        except Exception:
            pass

        return self._last_normal_geometry

    def _persist_geometry_now(self, force: bool = False) -> None:
        if not force:
            if not self._persistence_enabled or self._restore_in_progress:
                return
            if getattr(self.host, "_is_exiting", False):
                return

        try:
            if self.host.isMinimized():
                return
        except Exception:
            pass

        try:
            is_maximized = bool(self.is_zoomed())

            if force or self._last_persisted_maximized != is_maximized:
                self.store.save_maximized(is_maximized)
                self._last_persisted_maximized = is_maximized
                self._pending_window_maximized_state = is_maximized
                try:
                    self._window_maximized_persist_timer.stop()
                except Exception:
                    pass

            geometry = self._get_normal_geometry_to_save(is_maximized)
            if geometry is None:
                return

            x, y, width, height = geometry
            width = max(int(width), self.min_width)
            height = max(int(height), self.min_height)
            normalized = (int(x), int(y), int(width), int(height))

            if force or self._last_persisted_geometry != normalized:
                self.store.save_geometry(*normalized)
                self._last_persisted_geometry = normalized
        except Exception as e:
            log(f"Ошибка сохранения геометрии окна: {e}", "DEBUG")
