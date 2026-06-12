from __future__ import annotations

from log.log import log
from profile.key_resolution import (
    preset_profile_move_key_map,
    preset_profile_move_result_key,
    remap_profile_operation_keys,
)
from profile.ui.profile_order_list import ProfileOrderList
from PyQt6.QtCore import QTimer
from qfluentwidgets import BodyLabel, BreadcrumbBar, InfoBar
from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE
from ui.latest_value_worker_state import LatestValueWorkerState
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.pages.base_page import BasePage
from ui.queued_worker_state import QueuedWorkerState
from app.ui_texts import tr as tr_catalog


ORDER_PAYLOAD_PRESET_SWITCH_RELOAD_DELAY_MS = 180


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
        ui_state_store=None,
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
        self._order_payload_loaded_once = False
        self._order_payload_dirty = True
        self._order_list_show_scheduled = False
        self._order_reload_after_preset_switch_scheduled = False
        self._order_move_runtime = OneShotWorkerRuntime()
        self._order_move_state = QueuedWorkerState[dict[str, str]](self._order_move_runtime)
        self._order_move_reload_required = False
        self._breadcrumb = None
        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._cleanup_in_progress = False
        self._build_content()
        self.bind_ui_state_store(ui_state_store)

    def on_page_activated(self) -> None:
        if not self.__dict__.get("_order_payload_loaded_once", False) or self.__dict__.get(
            "_order_payload_dirty",
            True,
        ):
            self._reload_order_profiles()
            return
        self._schedule_order_list_show_after_page_switch()

    def on_page_hidden(self) -> None:
        self._hide_order_list_for_next_switch()

    def _hide_order_list_for_next_switch(self) -> None:
        order_list = self.__dict__.get("_order_list")
        if order_list is None:
            return
        try:
            order_list.setVisible(False)
        except Exception:
            pass
        self._order_list_show_scheduled = False

    def _schedule_order_list_show_after_page_switch(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_order_list") is None:
            return
        if self.__dict__.get("_order_list_show_scheduled", False):
            return
        self._order_list_show_scheduled = True
        try:
            QTimer.singleShot(0, self._show_order_list_after_page_switch)
        except Exception:
            self._show_order_list_after_page_switch()

    def _show_order_list_after_page_switch(self) -> None:
        self._order_list_show_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        order_list = self.__dict__.get("_order_list")
        if order_list is None:
            return
        try:
            order_list.setVisible(True)
        except Exception:
            pass

    def bind_ui_state_store(self, store) -> None:
        if self.__dict__.get("_ui_state_store") is store:
            return
        unsubscribe = self.__dict__.get("_ui_state_unsubscribe")
        if callable(unsubscribe):
            try:
                unsubscribe()
            except Exception:
                pass
        self._ui_state_store = store
        self._ui_state_unsubscribe = None
        if store is None:
            return
        self._ui_state_unsubscribe = store.subscribe(
            self._on_ui_state_changed,
            fields={"active_preset_revision", "preset_content_revision"},
            emit_initial=False,
        )

    def _on_ui_state_changed(self, _state, changed: frozenset[str]) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if not (set(changed or ()) & {"active_preset_revision", "preset_content_revision"}):
            return
        self._order_payload_dirty = True
        if not self.isVisible():
            return
        if "preset_content_revision" in changed:
            self._reload_order_profiles(force=True)
            return
        self._schedule_order_reload_after_preset_switch()

    def _schedule_order_reload_after_preset_switch(self) -> None:
        if self.__dict__.get("_order_reload_after_preset_switch_scheduled", False):
            return
        self._order_reload_after_preset_switch_scheduled = True
        try:
            QTimer.singleShot(
                ORDER_PAYLOAD_PRESET_SWITCH_RELOAD_DELAY_MS,
                self._run_scheduled_order_reload_after_preset_switch,
            )
        except Exception:
            self._run_scheduled_order_reload_after_preset_switch()

    def _run_scheduled_order_reload_after_preset_switch(self) -> None:
        self._order_reload_after_preset_switch_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if not self.__dict__.get("_order_payload_dirty", False):
            return
        if not self.isVisible():
            return
        self._reload_order_profiles(force=True)

    def _mark_order_payload_dirty(self, *, reload_if_visible: bool = False) -> None:
        self._order_payload_dirty = True
        if reload_if_visible and self.isVisible():
            self._reload_order_profiles(force=True)

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
        if not force and self.__dict__.get("_order_payload_loaded_once", False) and not self.__dict__.get(
            "_order_payload_dirty",
            True,
        ):
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
        self._order_payload_loaded_once = True
        self._order_payload_dirty = False
        self._schedule_order_list_show_after_page_switch()

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

    def _queue_profile_order_move_from_dict(self, operation: dict[str, str]) -> bool:
        pending = dict(operation or {})
        self._queue_profile_order_move(
            str(pending.get("action") or ""),
            str(pending.get("source_profile_key") or ""),
            destination_profile_key=str(pending.get("destination_profile_key") or ""),
        )
        return True

    def _run_profile_order_move_operation(self, operation: dict[str, str] | None) -> None:
        if bool(self.__dict__.get("_cleanup_in_progress", False)):
            return
        pending = dict(operation or {})
        self._start_profile_order_move_worker(
            str(pending.get("action") or ""),
            str(pending.get("source_profile_key") or ""),
            destination_profile_key=str(pending.get("destination_profile_key") or ""),
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
        result_key = preset_profile_move_result_key(result)
        key_map = preset_profile_move_key_map(result)
        if result_key:
            applied_locally = self._apply_profile_order_move_locally(
                action,
                source_profile_key,
                destination_profile_key=destination_profile_key,
            )
            self._remap_profile_order_after_file_rebuild(key_map)
        if self._order_move_state_obj().has_pending():
            if result_key and not applied_locally:
                self._order_move_reload_required = True
            return
        if self.__dict__.get("_order_move_reload_required", False):
            self._order_move_reload_required = False
            self._reload_order_profiles(force=True)
            return
        if applied_locally:
            self._order_payload_dirty = False
            return
        if result_key:
            self._reload_order_profiles(force=True)

    def _remap_profile_order_after_file_rebuild(self, key_map: dict[str, str]) -> None:
        clean_map = dict(key_map or {})
        if not clean_map:
            return
        order_list = self.__dict__.get("_order_list")
        if order_list is not None:
            try:
                order_list.remap_profile_keys(clean_map)
            except Exception:
                pass
        state = self._order_move_state_obj()
        state.pending[:] = [
            remap_profile_operation_keys(dict(operation or {}), clean_map)
            for operation in list(state.pending or [])
        ]

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
        self._schedule_next_profile_order_move_after_finish(_worker)

    def _schedule_next_profile_order_move_after_finish(self, worker) -> bool:
        def _single_shot(delay: int, callback) -> None:
            try:
                QTimer.singleShot(delay, callback)
            except Exception:
                callback()

        operation = self._order_move_state_obj().schedule_next_after_finish(
            worker,
            is_current_worker_finish=self._is_current_worker_finish,
            single_shot=_single_shot,
            start=lambda pending: self._run_profile_order_move_operation(dict(pending or {})),
            queue_item=self._queue_profile_order_move_from_dict,
            is_cleanup_in_progress=lambda: bool(self.__dict__.get("_cleanup_in_progress", False)),
        )
        return operation is not None

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
        self._run_profile_order_move_operation(pending)

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
        unsubscribe = self.__dict__.get("_ui_state_unsubscribe")
        if callable(unsubscribe):
            try:
                unsubscribe()
            except Exception:
                pass
        self._ui_state_unsubscribe = None
        self._ui_state_store = None
        self._order_load_state_obj().reset()
        self._pending_order_payload_apply = None
        self._order_payload_apply_scheduled = False
        self._order_list_show_scheduled = False
        self._order_reload_after_preset_switch_scheduled = False
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

    def handle_page_command(self, command: str, payload: dict) -> bool:
        if command == "profile_order_changed":
            self._mark_order_payload_dirty(
                reload_if_visible=bool((payload or {}).get("reload_if_visible", False)),
            )
            return True
        return False


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
