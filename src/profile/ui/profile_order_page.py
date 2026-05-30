from __future__ import annotations

from log.log import log
from profile.ui.profile_order_list import ProfileOrderList
from qfluentwidgets import BodyLabel, BreadcrumbBar, InfoBar
from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE
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
        self._order_load_request_id = 0
        self._order_load_worker = None
        self._order_load_dirty = False
        self._order_move_request_id = 0
        self._order_move_worker = None
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
        worker = self.__dict__.get("_order_load_worker")
        if worker is not None:
            try:
                if worker.isRunning():
                    if force:
                        self._order_load_request_id = int(getattr(self, "_order_load_request_id", 0) or 0) + 1
                        self._order_load_dirty = True
                    return
            except Exception:
                return
        self._order_load_dirty = False
        self._order_load_request_id = int(getattr(self, "_order_load_request_id", 0) or 0) + 1
        request_id = self._order_load_request_id
        worker = self._create_profile_order_load_worker(request_id, self.launch_method, self)
        self._order_load_worker = worker
        worker.loaded.connect(self._on_order_profiles_loaded)
        worker.failed.connect(self._on_order_profiles_failed)
        worker.finished.connect(lambda w=worker: self._on_order_profiles_worker_finished(w))
        worker.start()

    def _create_profile_order_load_worker(self, request_id: int, launch_method: str, parent=None):
        return self._create_profile_order_load_worker_fn(request_id, launch_method, parent)

    def _on_order_profiles_loaded(self, request_id: int, payload) -> None:
        if bool(self.__dict__.get("_cleanup_in_progress", False)) or request_id != int(getattr(self, "_order_load_request_id", 0) or 0):
            return
        self._payload = payload
        if self._order_list is not None:
            self._order_list.set_profiles(tuple(getattr(payload, "items", ()) or ()))
        self._rebuild_breadcrumb()

    def _on_order_profiles_failed(self, request_id: int, error: str) -> None:
        if bool(self.__dict__.get("_cleanup_in_progress", False)) or request_id != int(getattr(self, "_order_load_request_id", 0) or 0):
            return
        log(f"{self.__class__.__name__}: не удалось прочитать порядок profile-ов: {error}", "ERROR")
        InfoBar.error(title="Ошибка", content=str(error), parent=self.window())

    def _on_order_profiles_worker_finished(self, worker) -> None:
        if self.__dict__.get("_order_load_worker") is worker:
            self._order_load_worker = None
        should_reload = bool(getattr(self, "_order_load_dirty", False))
        delete_later = getattr(worker, "deleteLater", None)
        if callable(delete_later):
            delete_later()
        if should_reload and not bool(self.__dict__.get("_cleanup_in_progress", False)):
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
        worker = self.__dict__.get("_order_move_worker")
        if worker is not None:
            try:
                if worker.isRunning():
                    return
            except Exception:
                return
        self._order_move_request_id = int(getattr(self, "_order_move_request_id", 0) or 0) + 1
        request_id = self._order_move_request_id
        worker = self._create_profile_order_move_worker(
            request_id,
            self.launch_method,
            action=str(action or ""),
            source_profile_key=source_profile_key,
            destination_profile_key=str(destination_profile_key or ""),
            parent=self,
        )
        self._order_move_worker = worker
        worker.moved.connect(self._on_profile_order_moved)
        worker.failed.connect(self._on_profile_order_move_failed)
        worker.finished.connect(lambda w=worker: self._on_profile_order_move_worker_finished(w))
        worker.start()

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
        if bool(self.__dict__.get("_cleanup_in_progress", False)) or request_id != int(getattr(self, "_order_move_request_id", 0) or 0):
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
        if bool(self.__dict__.get("_cleanup_in_progress", False)) or request_id != int(getattr(self, "_order_move_request_id", 0) or 0):
            return
        log(f"{self.__class__.__name__}: не удалось переместить profile в порядке preset: {error}", "ERROR")
        InfoBar.error(title="Ошибка", content=str(error), parent=self.window())

    def _on_profile_order_move_worker_finished(self, worker) -> None:
        if self.__dict__.get("_order_move_worker") is worker:
            self._order_move_worker = None
        delete_later = getattr(worker, "deleteLater", None)
        if callable(delete_later):
            delete_later()

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
        self._order_load_request_id = int(getattr(self, "_order_load_request_id", 0) or 0) + 1
        self._order_move_request_id = int(getattr(self, "_order_move_request_id", 0) or 0) + 1
        self._order_load_dirty = False
        for attr in ("_order_load_worker", "_order_move_worker"):
            worker = self.__dict__.get(attr)
            if worker is None:
                continue
            try:
                worker.quit()
            except Exception:
                pass
            setattr(self, attr, None)
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
