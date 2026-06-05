from __future__ import annotations

from log.log import log
from profile.ui.profile_order_list import ProfileOrderList
from PyQt6.QtCore import QTimer
from qfluentwidgets import BodyLabel, BreadcrumbBar, InfoBar
from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.pages.base_page import BasePage
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
            title="Порядок в preset",
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
        self._order_load_dirty = False
        self._order_load_restart_scheduled = False
        self._order_payload_apply_scheduled = False
        self._pending_order_payload_apply = None
        self._order_move_runtime = OneShotWorkerRuntime()
        self._pending_profile_order_moves: list[dict[str, str]] = []
        self._order_move_start_scheduled = False
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
        if self.__dict__.get("_order_load_restart_scheduled", False):
            if force:
                self._order_load_dirty = True
            return
        if runtime.is_running():
            if force:
                runtime.next_request_id()
                self._order_load_dirty = True
                return
            return
        self._order_load_dirty = False
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
        self._payload = payload
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
        if self.__dict__.get("_order_load_dirty", False) or self.__dict__.get("_order_load_restart_scheduled", False):
            return
        if self._order_list is not None:
            self._order_list.set_profiles(tuple(getattr(payload, "items", ()) or ()))
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
        should_reload = bool(getattr(self, "_order_load_dirty", False))
        if should_reload and not bool(self.__dict__.get("_cleanup_in_progress", False)):
            self._schedule_order_profiles_reload()

    def _schedule_order_profiles_reload(self) -> None:
        if self.__dict__.get("_order_load_restart_scheduled", False):
            return
        self._order_load_restart_scheduled = True
        try:
            QTimer.singleShot(0, self._run_scheduled_order_profiles_reload)
        except Exception:
            self._run_scheduled_order_profiles_reload()

    def _run_scheduled_order_profiles_reload(self) -> None:
        self._order_load_restart_scheduled = False
        if bool(self.__dict__.get("_cleanup_in_progress", False)):
            return
        self._reload_order_profiles(force=True)

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
        if self._order_move_runtime.is_running() or self.__dict__.get("_order_move_start_scheduled", False):
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
        pending_moves = self.__dict__.setdefault("_pending_profile_order_moves", [])
        pending_moves[:] = [
            pending
            for pending in pending_moves
            if str(pending.get("source_profile_key") or "").strip() != source
        ]
        pending_moves.append(
            {
                "action": str(action or ""),
                "source_profile_key": source,
                "destination_profile_key": str(destination_profile_key or ""),
            }
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
        if self.__dict__.get("_pending_profile_order_moves"):
            if result:
                self._order_move_reload_required = True
            return
        if self.__dict__.get("_order_move_reload_required", False):
            self._order_move_reload_required = False
            self._reload_order_profiles(force=True)
            return
        if result and self._apply_profile_order_move_locally(
            action,
            source_profile_key,
            destination_profile_key=destination_profile_key,
        ):
            return
        if result:
            self._reload_order_profiles(force=True)

    def _on_profile_order_move_failed(self, request_id: int, error: str) -> None:
        if not self._order_move_runtime.is_current(
            request_id,
            cleanup_in_progress=bool(self.__dict__.get("_cleanup_in_progress", False)),
        ):
            return
        if self.__dict__.get("_pending_profile_order_moves"):
            return
        log(f"{self.__class__.__name__}: не удалось переместить profile в порядке preset: {error}", "ERROR")
        InfoBar.error(title="Ошибка", content=str(error), parent=self.window())
        if self.__dict__.get("_order_move_reload_required", False) and not self.__dict__.get(
            "_pending_profile_order_moves"
        ):
            self._order_move_reload_required = False
            self._reload_order_profiles(force=True)

    def _on_profile_order_move_worker_finished(self, _worker) -> None:
        if not self._is_current_worker_finish(self.__dict__.get("_order_move_runtime"), _worker):
            return
        if self.__dict__.get("_pending_profile_order_moves") and not bool(
            self.__dict__.get("_cleanup_in_progress", False)
        ):
            self._schedule_next_profile_order_move_start()

    def _schedule_next_profile_order_move_start(self) -> None:
        if self.__dict__.get("_order_move_start_scheduled", False):
            return
        self._order_move_start_scheduled = True
        try:
            QTimer.singleShot(0, self._run_scheduled_profile_order_move_start)
        except Exception:
            self._run_scheduled_profile_order_move_start()

    def _run_scheduled_profile_order_move_start(self) -> None:
        self._order_move_start_scheduled = False
        pending_moves = self.__dict__.setdefault("_pending_profile_order_moves", [])
        pending = pending_moves.pop(0) if pending_moves else None
        if pending is None or bool(self.__dict__.get("_cleanup_in_progress", False)):
            return
        self._start_profile_order_move_worker(
            str(pending.get("action") or ""),
            str(pending.get("source_profile_key") or ""),
            destination_profile_key=str(pending.get("destination_profile_key") or ""),
        )

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
        self._order_load_dirty = False
        self._order_load_restart_scheduled = False
        self._pending_order_payload_apply = None
        self._order_payload_apply_scheduled = False
        self._order_move_start_scheduled = False
        self._order_move_reload_required = False
        self.__dict__.setdefault("_pending_profile_order_moves", []).clear()
        self._order_load_runtime.stop(warning_prefix="Profile order load worker")
        self._order_load_runtime.cancel()
        self._order_move_runtime.stop(warning_prefix="Profile order move worker")
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
            self._breadcrumb.addItem("order", "Порядок в preset")
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
