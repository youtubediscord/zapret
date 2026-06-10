from __future__ import annotations

from log.log import log
from profile.ui.profile_order_list import ProfileOrderList
from PyQt6.QtCore import QTimer
from qfluentwidgets import BodyLabel, BreadcrumbBar, InfoBar
from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE
from ui.latest_value_worker_state import LatestValueWorkerState
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.pages.base_page import BasePage
from ui.queued_worker_state import QueuedWorkerState
from app.ui_texts import tr as tr_catalog


class ProfileOrderPageBase(BasePage):
    launch_method = ZAPRET2_MODE
    title_key = "page.winws2_profile_order.title"
    control_key = "page.winws2_profile_setup.breadcrumb.control"
    profiles_key = "page.winws2_pages.title"
    profiles_default = "Настройка пресета"

    def __init__(
        self,
        parent=None,
        *,
        create_profile_order_load_worker,
        create_preset_profile_order_move_worker,
        open_profiles,
        open_root,
    ):
        super().__init__(
            title="Порядок в пресете",
            parent=parent,
            title_key=self.title_key,
        )
        self._create_profile_order_load_worker_fn = create_profile_order_load_worker
        self._create_preset_profile_order_move_worker_fn = create_preset_profile_order_move_worker
        self._open_profiles = open_profiles
        self._open_root = open_root
        self._payload = None
        self._order_list: ProfileOrderList | None = None
        self._order_load_runtime = OneShotWorkerRuntime()
        self._order_load_state = LatestValueWorkerState(
            self._order_load_runtime,
            empty_value=False,
        )
        self._order_payload_apply_scheduled = False
        self._pending_order_payload_apply = None
        self._order_move_runtime = OneShotWorkerRuntime()
        self._order_move_state = QueuedWorkerState[dict[str, str]](self._order_move_runtime)
        self._order_move_reload_required = False
        self._breadcrumb = None
        self._cleanup_in_progress = False
        self._build_content()

    def on_page_activated(self) -> None:
        self._reload_order_profiles()

    def _build_content(self) -> None:
        if self.title_label is not None:
            self.title_label.hide()
        if self.subtitle_label is not None:
            self.subtitle_label.hide()

        self._breadcrumb = BreadcrumbBar(self)
        self._breadcrumb.currentItemChanged.connect(self._on_breadcrumb_item_changed)
        self.layout.addWidget(self._breadcrumb)

        hint = BodyLabel(
            "Profile выше в списке имеет больший приоритет. "
            "Если два profile-а подходят к одному домену или IP, будет применён тот, который находится выше."
        )
        hint.setWordWrap(True)
        self.layout.addWidget(hint)

        self._order_list = ProfileOrderList(self)
        self._order_list.profile_move_requested.connect(self._on_profile_move_requested)
        self._order_list.profile_move_after_requested.connect(self._on_profile_move_after_requested)
        self._order_list.profile_move_to_end_requested.connect(self._on_profile_move_to_end_requested)
        self.layout.addWidget(self._order_list, 1)
        self._rebuild_breadcrumb()

    def _reload_order_profiles(self, *, force: bool = False) -> None:
        if bool(self.__dict__.get("_cleanup_in_progress", False)):
            return
        runtime = self._order_load_runtime
        state = self._order_load_state_obj()
        if state.start_scheduled:
            if force:
                state.pending = True
            return
        if runtime.is_running():
            if force:
                runtime.next_request_id()
                state.pending = True
                return
            return
        state.pending = False
        runtime.start_qthread_worker(
            worker_factory=lambda request_id: self._create_profile_order_load_worker(
                request_id,
                self.launch_method,
                self,
            ),
            on_loaded=self._on_order_profiles_loaded,
            on_failed=self._on_order_profiles_failed,
            on_finished=self._on_order_profiles_worker_finished,
        )

    def _create_profile_order_load_worker(self, request_id: int, launch_method: str, parent=None):
        return self._create_profile_order_load_worker_fn(request_id, launch_method, parent)

    def _on_order_profiles_loaded(self, request_id: int, payload) -> None:
        if not self._order_load_runtime.is_current(
            request_id,
            cleanup_in_progress=bool(self.__dict__.get("_cleanup_in_progress", False)),
        ):
            return
        self._payload = getattr(payload, "payload", payload)
        self._schedule_order_payload_apply(payload)

    def _schedule_order_payload_apply(self, payload) -> None:
        self._pending_order_payload_apply = payload
        if self.__dict__.get("_order_payload_apply_scheduled", False):
            return
        self._order_payload_apply_scheduled = True
        try:
            QTimer.singleShot(0, self._run_scheduled_order_payload_apply)
        except Exception:
            self._run_scheduled_order_payload_apply()

    def _run_scheduled_order_payload_apply(self) -> None:
        payload = self.__dict__.get("_pending_order_payload_apply")
        self._pending_order_payload_apply = None
        self._order_payload_apply_scheduled = False
        if payload is None or bool(self.__dict__.get("_cleanup_in_progress", False)):
            return
        state = self._order_load_state_obj()
        if state.has_pending() or state.start_scheduled:
            return
        if self._order_list is not None:
            view_state = getattr(payload, "view_state", None)
            if view_state is not None:
                self._order_list.apply_view_state(view_state)
            else:
                payload_items = getattr(getattr(payload, "payload", payload), "items", ())
                self._order_list.set_profiles(tuple(payload_items or ()))
        self._rebuild_breadcrumb()

    def _on_order_profiles_failed(self, request_id: int, error: str) -> None:
        if not self._order_load_runtime.is_current(
            request_id,
            cleanup_in_progress=bool(self.__dict__.get("_cleanup_in_progress", False)),
        ):
            return
        log(f"{self.__class__.__name__}: не удалось прочитать порядок profile-ов: {error}", "ERROR")
        InfoBar.error(title="Ошибка", content=str(error), parent=self.window())

    def _on_order_profiles_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_order_load_runtime"), _worker):
            return
        if self._order_load_state_obj().has_pending() and not bool(self.__dict__.get("_cleanup_in_progress", False)):
            self._schedule_order_profiles_reload()

    def _schedule_order_profiles_reload(self) -> None:
        state = self._order_load_state_obj()

        def _single_shot(delay: int, callback) -> None:
            try:
                QTimer.singleShot(delay, callback)
            except Exception:
                callback()

        state.schedule_start(
            _single_shot,
            self._run_scheduled_order_profiles_reload,
            cleanup_in_progress=bool(self.__dict__.get("_cleanup_in_progress", False)),
        )

    def _run_scheduled_order_profiles_reload(self) -> None:
        pending = self._order_load_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=bool(self.__dict__.get("_cleanup_in_progress", False)),
        )
        if not pending:
            return
        self._reload_order_profiles(force=True)

    def _order_load_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_order_load_state")
        runtime = self.__dict__.get("_order_load_runtime")
        if state is None:
            pending = bool(self.__dict__.pop("_order_load_dirty", False))
            start_scheduled = bool(self.__dict__.pop("_order_load_restart_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=False,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_order_load_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _order_load_dirty(self) -> bool:
        return bool(self._order_load_state_obj().pending)

    @_order_load_dirty.setter
    def _order_load_dirty(self, value: bool) -> None:
        self._order_load_state_obj().pending = bool(value)

    @property
    def _order_load_restart_scheduled(self) -> bool:
        return bool(self._order_load_state_obj().start_scheduled)

    @_order_load_restart_scheduled.setter
    def _order_load_restart_scheduled(self, value: bool) -> None:
        self._order_load_state_obj().start_scheduled = bool(value)

    def _on_profile_move_requested(self, source_profile_key: str, destination_profile_key: str) -> None:
        self._request_profile_order_move(
            "before",
            source_profile_key,
            destination_profile_key=destination_profile_key,
        )

    def _on_profile_move_after_requested(self, source_profile_key: str, destination_profile_key: str) -> None:
        self._request_profile_order_move(
            "after",
            source_profile_key,
            destination_profile_key=destination_profile_key,
        )

    def _on_profile_move_to_end_requested(self, profile_key: str) -> None:
        self._request_profile_order_move("end", profile_key)

    def _request_profile_order_move(
        self,
        action: str,
        source_profile_key: str,
        *,
        destination_profile_key: str = "",
    ) -> None:
        if bool(self.__dict__.get("_cleanup_in_progress", False)):
            return
        source_profile_key = str(source_profile_key or "").strip()
        if not source_profile_key:
            return
        if self._order_move_state_obj().is_busy():
            self._queue_profile_order_move(
                action,
                source_profile_key,
                destination_profile_key=destination_profile_key,
            )
            return
        self._start_profile_order_move_worker(
            action,
            source_profile_key,
            destination_profile_key=destination_profile_key,
        )

    def _queue_profile_order_move(
        self,
        action: str,
        source_profile_key: str,
        *,
        destination_profile_key: str = "",
    ) -> None:
        source = str(source_profile_key or "").strip()
        if not source:
            return
        self._order_move_state_obj().replace_by_key(
            {
                "action": str(action or ""),
                "source_profile_key": source,
                "destination_profile_key": str(destination_profile_key or ""),
            },
            key=lambda pending: str(pending.get("source_profile_key") or "").strip(),
        )

    def _start_profile_order_move_worker(
        self,
        action: str,
        source_profile_key: str,
        *,
        destination_profile_key: str = "",
    ) -> None:
        self._order_move_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self._create_profile_order_move_worker(
                request_id,
                self.launch_method,
                action=str(action or ""),
                source_profile_key=source_profile_key,
                destination_profile_key=str(destination_profile_key or ""),
                parent=self,
            ),
            on_loaded=self._on_profile_order_moved,
            on_failed=self._on_profile_order_move_failed,
            on_finished=self._on_profile_order_move_worker_finished,
            loaded_signal_name="moved",
        )

    def _create_profile_order_move_worker(
        self,
        request_id: int,
        launch_method: str,
        *,
        action: str,
        source_profile_key: str,
        destination_profile_key: str = "",
        parent=None,
    ):
        return self._create_preset_profile_order_move_worker_fn(
            request_id,
            launch_method,
            action=action,
            source_profile_key=source_profile_key,
            destination_profile_key=destination_profile_key,
            parent=parent,
        )

    def _on_profile_order_moved(
        self,
        request_id: int,
        action: str,
        source_profile_key: str,
        destination_profile_key: str,
        result,
    ) -> None:
        if not self._order_move_runtime.is_current(
            request_id,
            cleanup_in_progress=bool(self.__dict__.get("_cleanup_in_progress", False)),
        ):
            return
        applied_locally = False
        if result:
            applied_locally = self._apply_profile_order_move_locally(
                action,
                source_profile_key,
                destination_profile_key=destination_profile_key,
            )
        if self._order_move_state_obj().has_pending():
            if result and not applied_locally:
                self._order_move_reload_required = True
            return
        if self.__dict__.get("_order_move_reload_required", False):
            self._order_move_reload_required = False
            self._reload_order_profiles(force=True)
            return
        if applied_locally:
            return
        if result:
            self._reload_order_profiles(force=True)

    def _on_profile_order_move_failed(self, request_id: int, error: str) -> None:
        if not self._order_move_runtime.is_current(
            request_id,
            cleanup_in_progress=bool(self.__dict__.get("_cleanup_in_progress", False)),
        ):
            return
        if self._order_move_state_obj().has_pending():
            return
        log(f"{self.__class__.__name__}: не удалось переместить profile в порядке preset: {error}", "ERROR")
        InfoBar.error(title="Ошибка", content=str(error), parent=self.window())
        if self.__dict__.get("_order_move_reload_required", False) and not self._order_move_state_obj().has_pending():
            self._order_move_reload_required = False
            self._reload_order_profiles(force=True)

    def _on_profile_order_move_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_order_move_runtime"), _worker):
            return
        if self._order_move_state_obj().has_pending() and not bool(
            self.__dict__.get("_cleanup_in_progress", False)
        ):
            self._schedule_next_profile_order_move_start()

    def _schedule_next_profile_order_move_start(self) -> None:
        state = self._order_move_state_obj()
        if state.start_scheduled:
            return
        state.start_scheduled = True
        try:
            QTimer.singleShot(0, self._run_scheduled_profile_order_move_start)
        except Exception:
            self._run_scheduled_profile_order_move_start()

    def _run_scheduled_profile_order_move_start(self) -> None:
        state = self._order_move_state_obj()
        state.start_scheduled = False
        pending = state.pop_next()
        if pending is None or bool(self.__dict__.get("_cleanup_in_progress", False)):
            return
        self._start_profile_order_move_worker(
            str(pending.get("action") or ""),
            str(pending.get("source_profile_key") or ""),
            destination_profile_key=str(pending.get("destination_profile_key") or ""),
        )

    def _order_move_state_obj(self) -> QueuedWorkerState[dict[str, str]]:
        state = self.__dict__.get("_order_move_state")
        runtime = self.__dict__.get("_order_move_runtime")
        if state is None:
            pending = list(self.__dict__.pop("_pending_profile_order_moves", []) or [])
            start_scheduled = bool(self.__dict__.pop("_order_move_start_scheduled", False))
            state = QueuedWorkerState(
                runtime,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_order_move_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _pending_profile_order_moves(self) -> list[dict[str, str]]:
        return self._order_move_state_obj().pending

    @_pending_profile_order_moves.setter
    def _pending_profile_order_moves(self, value: list[dict[str, str]]) -> None:
        self._order_move_state_obj().pending = list(value or [])

    @property
    def _order_move_start_scheduled(self) -> bool:
        return bool(self._order_move_state_obj().start_scheduled)

    @_order_move_start_scheduled.setter
    def _order_move_start_scheduled(self, value: bool) -> None:
        self._order_move_state_obj().start_scheduled = bool(value)

    def _is_current_worker_finish(self, runtime, worker) -> bool:
        if self.__dict__.get("_cleanup_in_progress", False):
            return False
        request_id = getattr(worker, "_request_id", None)
        if request_id is None:
            current_worker = getattr(runtime, "worker", None)
            if current_worker is not None:
                return worker is current_worker
            return True
        try:
            return int(request_id) == int(getattr(runtime, "request_id", -1))
        except (TypeError, ValueError):
            return False

    def _apply_profile_order_move_locally(
        self,
        action: str,
        source_profile_key: str,
        *,
        destination_profile_key: str = "",
    ) -> bool:
        order_list = self._order_list
        if order_list is None:
            return False
        return order_list.move_profile_item(
            source_profile_key,
            action,
            destination_profile_key,
        )

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        self._order_load_state_obj().reset()
        self._pending_order_payload_apply = None
        self._order_payload_apply_scheduled = False
        self._order_move_state_obj().reset()
        self._order_move_reload_required = False
        self._order_load_runtime.stop(
            blocking=False,
            warning_prefix="Profile order load worker",
        )
        self._order_load_runtime.cancel()
        self._order_move_runtime.stop(
            blocking=False,
            warning_prefix="Profile order move worker",
        )
        self._order_move_runtime.cancel()
        try:
            super().cleanup()
        except Exception:
            pass

    def _rebuild_breadcrumb(self) -> None:
        if self._breadcrumb is None:
            return
        self._breadcrumb.blockSignals(True)
        try:
            self._breadcrumb.clear()
            self._breadcrumb.addItem("control", tr_catalog(self.control_key, language=self._ui_language, default="Управление"))
            self._breadcrumb.addItem("profiles", tr_catalog(self.profiles_key, language=self._ui_language, default=self.profiles_default))
            self._breadcrumb.addItem("order", "Порядок в пресете")
        finally:
            self._breadcrumb.blockSignals(False)

    def _on_breadcrumb_item_changed(self, key: str) -> None:
        if key == "control":
            self._open_root()
        elif key == "profiles":
            self._open_profiles()
        elif key == "order":
            self._rebuild_breadcrumb()


class Zapret2ProfileOrderPage(ProfileOrderPageBase):
    launch_method = ZAPRET2_MODE
    title_key = "page.winws2_profile_order.title"
    control_key = "page.winws2_profile_setup.breadcrumb.control"
    profiles_key = "page.winws2_pages.title"
    profiles_default = "Настройка пресета"


class Zapret1ProfileOrderPage(ProfileOrderPageBase):
    launch_method = ZAPRET1_MODE
    title_key = "page.winws1_profile_order.title"
    control_key = "page.winws1_profile_setup.breadcrumb.control"
    profiles_key = "page.winws1_pages.title"
    profiles_default = "Настройка пресета"


__all__ = ["ProfileOrderPageBase", "Zapret1ProfileOrderPage", "Zapret2ProfileOrderPage"]
