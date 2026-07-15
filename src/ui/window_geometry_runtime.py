from __future__ import annotations

from dataclasses import dataclass
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication

from log.log import log
from ui.latest_value_worker_state import LatestValueWorkerState
from ui.one_shot_worker_runtime import OneShotWorkerRuntime



@dataclass(slots=True)
class StoredWindowGeometry:
    position: tuple[int, int] | None
    size: tuple[int, int] | None
    maximized: bool


class SettingsWindowGeometryStore:
    """Низкоуровневое хранилище геометрии окна в settings.json."""

    def load(self) -> StoredWindowGeometry:
        from settings import store as settings_store

        geometry = settings_store.get_window_geometry()
        x = geometry.get("x")
        y = geometry.get("y")
        width = geometry.get("width")
        height = geometry.get("height")
        position = None if x is None or y is None else (int(x), int(y))
        size = None if width is None or height is None else (int(width), int(height))
        return StoredWindowGeometry(
            position=position,
            size=size,
            maximized=bool(geometry.get("maximized")),
        )

    def save_geometry(self, x: int, y: int, width: int, height: int) -> None:
        from config.window_geometry_store import set_window_position, set_window_size


        set_window_position(int(x), int(y))
        set_window_size(int(width), int(height))

    def save_maximized(self, maximized: bool) -> None:
        from config.window_geometry_store import set_window_maximized


        set_window_maximized(bool(maximized))


class WindowGeometryRuntime:
    """Единый источник истины для геометрии и режима окна."""

    def __init__(
        self,
        host,
        *,
        min_width: int,
        min_height: int,
        default_width: int,
        default_height: int,
        close_state,
        create_geometry_save_worker,
        store: SettingsWindowGeometryStore | None = None,
    ) -> None:
        self.host = host
        self.close_state = close_state
        self.min_width = int(min_width)
        self.min_height = int(min_height)
        self.default_width = int(default_width)
        self.default_height = int(default_height)
        self.store = store or SettingsWindowGeometryStore()
        self._create_geometry_save_worker = create_geometry_save_worker

        self._restore_in_progress = False
        self._persistence_enabled = False
        self._pending_restore_maximized = False
        self._applied_saved_maximize_state = False
        self._last_normal_geometry: tuple[int, int, int, int] | None = None
        self._last_persisted_geometry: tuple[int, int, int, int] | None = None
        self._last_persisted_maximized: bool | None = None
        self._geometry_save_runtime = OneShotWorkerRuntime()
        self._geometry_save_state = LatestValueWorkerState(self._geometry_save_runtime, empty_value=None)
        self._last_non_minimized_zoomed = False

        self._geometry_save_timer = QTimer(host)
        self._geometry_save_timer.setSingleShot(True)
        self._geometry_save_timer.setInterval(450)
        self._geometry_save_timer.timeout.connect(self._persist_geometry_now)

    def restore_geometry(self) -> None:
        """Восстанавливает сохранённую позицию, размер и maximized-флаг окна."""
        self._restore_in_progress = True
        try:
            saved = self.store.load()

            screen_geometry = QApplication.primaryScreen().availableGeometry()
            screens = QApplication.screens()

            def _looks_like_saved_maximized_geometry(width: int, height: int) -> bool:
                if not saved.maximized:
                    return False
                for screen in screens:
                    rect = screen.availableGeometry()
                    if width >= (rect.width() - 4) and height >= (rect.height() - 4):
                        return True
                return False

            if saved.size:
                width, height = saved.size
                if _looks_like_saved_maximized_geometry(width, height):
                    log(
                        "Обнаружена сохранённая normal-геометрия почти во весь экран; используем размер по умолчанию",
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
                if self._position_visible_on_any_screen(x, y):
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

    def show_from_hidden(self) -> None:
        """Единственная точка показа окна, скрытого в трей.

        Qt на Windows откладывает setWindowState() для скрытых окон, а
        resize()/move() пересинхронизируют Qt-состояние из нативного HWND
        (у него остаётся WS_MAXIMIZE) — поэтому скрытое maximized-окно нельзя
        ни «чистить», ни двигать: showMaximized() станет no-op и окно
        покажется с maximized-флагом при normal-геометрии (обрезание).

        Правильная последовательность: целевой режим берётся из памяти ДО
        любых мутаций, maximized-окно показывается как есть (Windows хранит
        его геометрию корректно), normal-геометрия применяется только когда
        окно скрыто без maximized-состояния. Затем один запрос режима через
        FSM — showMaximized()/showNormal() сами показывают скрытое окно и
        снимают stale-флаг Minimized после minimize-в-трей.
        """
        try:
            if self.host.isVisible():
                self.request_zoom_state(self.remembered_zoom_state())
                return
        except Exception:
            pass

        target_zoomed = bool(self._last_non_minimized_zoomed)

        if not target_zoomed and not self.is_zoomed():
            self._restore_in_progress = True
            try:
                self._apply_remembered_normal_geometry()
            finally:
                self._restore_in_progress = False

        self.request_zoom_state(target_zoomed)

    def _apply_remembered_normal_geometry(self) -> None:
        geometry = self._last_normal_geometry
        if geometry is None:
            return

        try:
            x, y, width, height = geometry
            width = max(int(width), self.min_width)
            height = max(int(height), self.min_height)
            self.host.resize(width, height)

            if self._position_visible_on_any_screen(int(x), int(y)):
                self.host.move(int(x), int(y))
            else:
                screen_geometry = QApplication.primaryScreen().availableGeometry()
                self.host.move(
                    screen_geometry.center().x() - self.host.width() // 2,
                    screen_geometry.center().y() - self.host.height() // 2,
                )
                log("Запомненная позиция за пределами экранов, окно отцентрировано", "WARNING")
        except Exception as e:
            log(f"Ошибка применения запомненной геометрии окна: {e}", "ERROR")

    @staticmethod
    def _position_visible_on_any_screen(x: int, y: int) -> bool:
        for screen in QApplication.screens():
            screen_rect = screen.availableGeometry()
            if (
                x + 100 > screen_rect.left()
                and x < screen_rect.right()
                and y + 100 > screen_rect.top()
                and y < screen_rect.bottom()
            ):
                return True
        return False

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
        """Переводит окно в maximized/normal одной командой.

        Кнопки заголовка и перетаскивание обрабатывает qframelesswindow
        нативно — runtime лишь наблюдает их через on_window_state_change().
        Этот метод вызывают только show_from_hidden() и стартовое
        восстановление, поэтому команда применяется напрямую, без FSM.
        Для скрытого окна команда выполняется даже при совпадении режима:
        showMaximized()/showNormal() заодно показывают окно.
        """
        self._pending_restore_maximized = False
        target_mode = "maximized" if bool(maximize) else "normal"

        try:
            host_visible = bool(self.host.isVisible())
        except Exception:
            host_visible = True

        if not host_visible or self.detect_mode() != target_mode:
            self._apply_window_mode_command(target_mode)

        actual_mode = self.detect_mode()
        if actual_mode != "minimized":
            self._last_non_minimized_zoomed = actual_mode == "maximized"
            self._schedule_geometry_save()
        return bool(actual_mode == "maximized")

    def on_geometry_changed(self) -> None:
        if self._restore_in_progress:
            return

        try:
            # resize-события скрытого окна (layout при отложенном build_ui)
            # не являются наблюдаемой пользователем геометрией
            if not self.host.isVisible():
                return
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
        if current_mode == "minimized":
            return

        self._last_non_minimized_zoomed = current_mode == "maximized"
        self._schedule_geometry_save()

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


    def _apply_window_mode_command(self, mode: str) -> bool:
        try:
            if mode == "maximized":
                self.host.showMaximized()
            elif mode == "normal":
                self.host.showNormal()
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
            state = state & ~Qt.WindowState.WindowMinimized
            state = state & ~Qt.WindowState.WindowFullScreen
            if mode == "maximized":
                state = state | Qt.WindowState.WindowMaximized
            else:
                state = state & ~Qt.WindowState.WindowMaximized

            self.host.setWindowState(state)
            return True
        except Exception:
            return False

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
        close_state = self.close_state
        if close_state is not None and bool(close_state.is_exiting):
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

    def _snapshot_for_persist(self) -> tuple[tuple[int, int, int, int] | None, bool]:
        """(normal_geometry, maximized) для записи в store.

        Скрытое или минимизированное окно отдаёт наблюдаемую модель
        (_last_normal_geometry, _last_non_minimized_zoomed) — живая геометрия
        скрытого окна недостоверна (layout приводит её к минимальной) и
        затирала сохранённый размер при перезагрузке Windows из трея.
        """
        try:
            visible = bool(self.host.isVisible())
        except Exception:
            visible = False
        if not visible or self._is_window_minimized_state():
            return self._last_normal_geometry, bool(self._last_non_minimized_zoomed)
        is_maximized = bool(self.is_zoomed())
        return self._get_normal_geometry_to_save(is_maximized), is_maximized

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
        if force:
            self._persist_geometry_sync(force=True)
            return

        if not force:
            if not self._persistence_enabled or self._restore_in_progress:
                return
            close_state = self.close_state
            if close_state is not None and bool(close_state.is_exiting):
                return

        try:
            geometry, is_maximized = self._snapshot_for_persist()

            maximized_changed = self._last_persisted_maximized != is_maximized

            if geometry is None:
                if maximized_changed:
                    self._request_geometry_save(geometry=None, maximized=is_maximized)
                return

            x, y, width, height = geometry
            width = max(int(width), self.min_width)
            height = max(int(height), self.min_height)
            normalized = (int(x), int(y), int(width), int(height))

            if maximized_changed or self._last_persisted_geometry != normalized:
                self._request_geometry_save(geometry=normalized, maximized=is_maximized)
        except Exception as e:
            log(f"Ошибка сохранения геометрии окна: {e}", "DEBUG")

    def _persist_geometry_sync(self, force: bool = False) -> None:
        if not force and (not self._persistence_enabled or self._restore_in_progress):
            return
        if force:
            self._stop_geometry_save_worker_for_sync()

        try:
            geometry, is_maximized = self._snapshot_for_persist()
            self.store.save_maximized(is_maximized)
            self._last_persisted_maximized = is_maximized
            if geometry is None:
                return
            x, y, width, height = geometry
            width = max(int(width), self.min_width)
            height = max(int(height), self.min_height)
            normalized = (int(x), int(y), int(width), int(height))
            self.store.save_geometry(*normalized)
            self._last_persisted_geometry = normalized
        except Exception as e:
            log(f"Ошибка синхронного сохранения геометрии окна: {e}", "DEBUG")

    def _stop_geometry_save_worker_for_sync(self) -> None:
        self._geometry_save_state_obj().reset()
        runtime = self.__dict__.get("_geometry_save_runtime")
        if runtime is None:
            return
        runtime.stop(
            blocking=False,
            wait_timeout_ms=1000,
            log_fn=log,
            warning_prefix="window geometry save worker",
        )
        runtime.cancel()

    def _request_geometry_save(self, *, geometry: tuple[int, int, int, int] | None, maximized: bool) -> None:
        payload = (geometry, bool(maximized))
        runtime = self.__dict__.get("_geometry_save_runtime")
        if runtime is None:
            runtime = OneShotWorkerRuntime()
            self._geometry_save_runtime = runtime
        state = self._geometry_save_state_obj()
        if state.is_busy():
            state.pending = self._merge_geometry_save_payload(
                state.pending,
                payload,
            )
            return
        self._start_geometry_save_worker(payload)

    @staticmethod
    def _merge_geometry_save_payload(current, requested):
        if current is None:
            return requested
        current_geometry, _current_maximized = current
        requested_geometry, requested_maximized = requested
        geometry = requested_geometry if requested_geometry is not None else current_geometry
        return (geometry, bool(requested_maximized))

    def _start_geometry_save_worker(self, payload) -> None:
        geometry, maximized = payload
        runtime = self.__dict__.get("_geometry_save_runtime")
        if runtime is None:
            runtime = OneShotWorkerRuntime()
            self._geometry_save_runtime = runtime
        runtime.start_qthread_worker(
            worker_factory=lambda request_id: self._create_geometry_save_worker(
                request_id,
                geometry=geometry,
                maximized=bool(maximized),
                parent=self.host,
            ),
            on_loaded=self._on_geometry_save_finished,
            on_failed=lambda _request_id, error: log(f"Ошибка сохранения геометрии окна: {error}", "DEBUG"),
            on_finished=self._on_geometry_save_worker_finished,
            signal_includes_request_id=False,
            loaded_signal_name="saved",
        )

    def _on_geometry_save_finished(self, _request_id: int, geometry, maximized) -> None:
        runtime = self.__dict__.get("_geometry_save_runtime")
        if not self._is_current_worker_request_id(runtime, _request_id):
            return
        self._last_persisted_maximized = bool(maximized)
        if geometry is not None:
            self._last_persisted_geometry = tuple(int(value) for value in geometry)

    def _on_geometry_save_worker_finished(self, _worker) -> None:
        self._geometry_save_state_obj().schedule_pending_after_finish(
            _worker,
            is_current_worker_finish=self._is_current_worker_finish,
            single_shot=QTimer.singleShot,
            run_scheduled=self._run_scheduled_geometry_save_worker_start,
            cleanup_in_progress=bool(self.__dict__.get("_cleanup_in_progress", False)),
        )

    def _schedule_geometry_save_worker_start(self, payload) -> None:
        state = self._geometry_save_state_obj()
        state.pending = self._merge_geometry_save_payload(
            state.pending,
            payload,
        )
        state.schedule_start(
            QTimer.singleShot,
            self._run_scheduled_geometry_save_worker_start,
            cleanup_in_progress=bool(self.__dict__.get("_cleanup_in_progress", False)),
        )

    def _run_scheduled_geometry_save_worker_start(self) -> None:
        pending = self._geometry_save_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=bool(self.__dict__.get("_cleanup_in_progress", False))
        )
        if pending is None:
            return
        self._start_geometry_save_worker(pending)

    def _geometry_save_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_geometry_save_state")
        runtime = self.__dict__.get("_geometry_save_runtime")
        if state is None:
            pending = self.__dict__.pop("_geometry_save_pending", None)
            start_scheduled = bool(self.__dict__.pop("_geometry_save_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=None,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_geometry_save_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _geometry_save_pending(self):
        return self._geometry_save_state_obj().pending

    @_geometry_save_pending.setter
    def _geometry_save_pending(self, value) -> None:
        self._geometry_save_state_obj().pending = value

    @property
    def _geometry_save_start_scheduled(self) -> bool:
        return bool(self._geometry_save_state_obj().start_scheduled)

    @_geometry_save_start_scheduled.setter
    def _geometry_save_start_scheduled(self, value: bool) -> None:
        self._geometry_save_state_obj().start_scheduled = bool(value)

    def _is_current_worker_finish(self, runtime, worker) -> bool:
        if self.__dict__.get("_cleanup_in_progress", False):
            return False
        request_id = getattr(worker, "_request_id", None)
        if request_id is None:
            current_worker = getattr(runtime, "worker", None)
            if current_worker is not None:
                return worker is current_worker
            return True
        return self._is_current_worker_request_id(runtime, request_id)

    def _is_current_worker_request_id(self, runtime, request_id) -> bool:
        try:
            return int(request_id) == int(getattr(runtime, "request_id", -1))
        except (TypeError, ValueError):
            return False
