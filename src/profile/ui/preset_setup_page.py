from __future__ import annotations

import time

from PyQt6.QtCore import QTimer

from log.log import log
from profile.match_filters import filter_values
from profile.list_apply_signature import profile_payload_apply_signature
from profile.ui.profile_context_menu import ProfileContextMenuActions, show_profile_context_menu
from profile.ui.profile_folder_menu import show_profile_folder_menu
from profile.ui.profiles_list import ProfilesList
from profile.ui.shell import build_profile_shell
from profile.ui.user_profile_dialog import CreateUserProfileDialog
from qfluentwidgets import BodyLabel, InfoBar, MessageBox
from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE
from ui.pages.base_page import BasePage
from app.ui_texts import tr as tr_catalog
from ui.latest_value_worker_state import LatestValueWorkerState
from ui.message_box_accessibility import set_message_box_button_accessibility
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.queued_worker_state import QueuedWorkerState


PROFILE_UI_TIMING_LOG_LEVEL = "⏱ PROFILE"
PROFILE_UI_VISIBLE_TIMING_LABELS = frozenset(
    {
        "profile_ui.apply_payload.total",
        "profile_ui.profile_list.build",
    }
)
PROFILE_PAYLOAD_PRESET_SWITCH_RELOAD_DELAY_MS = 180


def preset_setup_title_for_payload(payload, default_title: str = "Настройка пресета") -> str:
    preset_name = str(getattr(payload, "selected_preset_name", "") or "").strip()
    if not preset_name:
        preset_name = str(getattr(payload, "selected_preset_file_name", "") or "").strip()
    if not preset_name:
        return default_title
    return f"{default_title}: {preset_name}"


def set_widget_text_if_changed(widget, text: str) -> bool:
    value = str(text or "")
    try:
        if str(widget.text()) == value:
            return False
    except Exception:
        pass
    widget.setText(value)
    return True


def set_widget_enabled_if_changed(widget, enabled: bool) -> bool:
    value = bool(enabled)
    try:
        if bool(widget.isEnabled()) == value:
            return False
    except Exception:
        pass
    widget.setEnabled(value)
    return True


class PresetSetupPageBase(BasePage):
    launch_method = ZAPRET2_MODE
    engine_label = "Zapret 2"
    page_title = "Настройка пресета"
    title_key = "page.winws2_pages.title"
    control_key = "page.winws2_pages.back.control"
    toolbar_title_key = "page.winws2_pages.toolbar.title"
    request_button_key = "page.winws2_pages.request.button"
    request_hint_key = "page.winws2_pages.request.hint"
    loading_key = "page.winws2_pages.loading"

    def __init__(
        self,
        parent=None,
        *,
        create_profile_list_load_worker,
        create_profile_item_refresh_worker,
        create_profile_context_action_worker,
        create_profile_move_worker,
        create_user_profile_create_worker,
        create_user_profile_update_worker,
        create_user_profile_delete_worker,
        create_profile_folder_action_worker,
        open_profile_setup,
        open_profile_order,
        ui_state_store=None,
    ):
        super().__init__(
            title=self.page_title,
            parent=parent,
            title_key=self.title_key,
        )
        self._create_profile_list_load_worker_fn = create_profile_list_load_worker
        self._create_profile_item_refresh_worker_fn = create_profile_item_refresh_worker
        self._create_profile_context_action_worker_fn = create_profile_context_action_worker
        self._create_profile_move_worker_fn = create_profile_move_worker
        self._create_user_profile_create_worker_fn = create_user_profile_create_worker
        self._create_user_profile_update_worker_fn = create_user_profile_update_worker
        self._create_user_profile_delete_worker_fn = create_user_profile_delete_worker
        self._create_profile_folder_action_worker_fn = create_profile_folder_action_worker
        self._open_profile_setup = open_profile_setup
        self._open_profile_order_page = open_profile_order

        self._profiles_list: ProfilesList | None = None
        self._empty_state_label = None
        self._content_host_layout = None
        self._expand_btn = None
        self._collapse_btn = None
        self._request_btn = None
        self._info_btn = None
        self._add_profile_btn = None
        self._profile_search_input = None
        self._profile_search_query = ""
        self._toolbar_actions_bar = None
        self._profile_load_request_id = 0
        self._profile_load_runtime = OneShotWorkerRuntime()
        self._profile_load_runtime_request_id = 0
        self._profile_item_refresh_request_id = 0
        self._profile_item_refresh_runtime = OneShotWorkerRuntime()
        self._profile_context_action_request_id = 0
        self._profile_context_action_runtime = OneShotWorkerRuntime()
        self._profile_move_request_id = 0
        self._profile_move_runtime = OneShotWorkerRuntime()
        self._profile_preset_write_state = QueuedWorkerState[dict[str, object]](
            self._profile_context_action_runtime,
        )
        self._profile_folder_action_request_id = 0
        self._profile_folder_action_runtime = OneShotWorkerRuntime()
        self._profile_folder_action_state = QueuedWorkerState[dict[str, object]](
            self._profile_folder_action_runtime,
        )
        self._profile_folder_action_refresh_by_request: dict[int, bool] = {}
        self._user_profile_create_request_id = 0
        self._user_profile_create_runtime = OneShotWorkerRuntime()
        self._user_profile_update_request_id = 0
        self._user_profile_update_runtime = OneShotWorkerRuntime()
        self._user_profile_delete_request_id = 0
        self._user_profile_delete_runtime = OneShotWorkerRuntime()
        self._profile_payload_loaded_once = False
        self._profile_payload_dirty = True
        self._profile_load_refresh_state = LatestValueWorkerState(self._profile_load_runtime, empty_value=False)
        self._profile_payload_request_scheduled = False
        self._profile_payload_request_force = False
        self._profile_payload_reload_after_preset_switch_scheduled = False
        self._profile_payload_apply_scheduled = False
        self._pending_profile_payload_apply = None
        self._profiles_list_show_scheduled = False
        self._profile_context_action_enabled_by_request: dict[int, bool] = {}
        self._cleanup_in_progress = False
        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._build_content()
        self.bind_ui_state_store(ui_state_store)

    def on_page_activated(self) -> None:
        if self.__dict__.get("_profile_payload_loaded_once", False) and not self.__dict__.get(
            "_profile_payload_dirty",
            True,
        ):
            self._schedule_profiles_list_show_after_page_switch()
            return
        self._schedule_profiles_payload_request()

    def on_page_hidden(self) -> None:
        self._hide_profiles_list_for_next_switch()

    def _hide_profiles_list_for_next_switch(self) -> None:
        profile_list = self.__dict__.get("_profiles_list")
        if profile_list is None:
            return
        try:
            profile_list.setVisible(False)
        except Exception:
            pass
        self._profiles_list_show_scheduled = False

    def _schedule_profiles_list_show_after_page_switch(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_profiles_list") is None:
            return
        if self.__dict__.get("_profiles_list_show_scheduled", False):
            return
        self._profiles_list_show_scheduled = True
        try:
            QTimer.singleShot(0, self._show_profiles_list_after_page_switch)
        except Exception:
            self._show_profiles_list_after_page_switch()

    def _show_profiles_list_after_page_switch(self) -> None:
        self._profiles_list_show_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        profile_list = self.__dict__.get("_profiles_list")
        if profile_list is None:
            return
        try:
            profile_list.setVisible(True)
        except Exception:
            pass

    def _worker_runtime(self, attr: str) -> OneShotWorkerRuntime:
        runtime = self.__dict__.get(attr)
        if runtime is None:
            runtime = OneShotWorkerRuntime()
            setattr(self, attr, runtime)
        return runtime

    def _worker_runtime_is_running(self, attr: str) -> bool:
        runtime = self.__dict__.get(attr)
        if runtime is None:
            return False
        return bool(runtime.is_running())

    def _accept_current_preset_setup_worker_finished(self, request_attr: str, worker) -> bool:
        request_id = getattr(worker, "_request_id", None)
        if request_id is None:
            return False
        try:
            return int(request_id) == int(self.__dict__.get(request_attr, 0) or 0)
        except (TypeError, ValueError):
            return False

    def _schedule_profiles_payload_request(self, *, force: bool = False) -> None:
        if bool(force) and self._profile_load_refresh_state_obj().has_pending():
            if self._worker_runtime_is_running("_profile_load_runtime"):
                self._profile_payload_dirty = True
                return
        self._profile_payload_request_force = (
            bool(self.__dict__.get("_profile_payload_request_force", False)) or bool(force)
        )
        if self.__dict__.get("_profile_payload_request_scheduled", False):
            return
        self._profile_payload_request_scheduled = True
        try:
            QTimer.singleShot(0, self._run_scheduled_profiles_payload_request)
        except Exception:
            self._run_scheduled_profiles_payload_request()

    def _run_scheduled_profiles_payload_request(self) -> None:
        force = bool(self.__dict__.get("_profile_payload_request_force", False))
        self._profile_payload_request_scheduled = False
        self._profile_payload_request_force = False
        self._request_profiles_payload(force=force)

    def _build_content(self) -> None:
        shell = build_profile_shell(
            content_parent=self.content,
            content_layout=self.layout,
            add_section_title=self.add_section_title,
            tr_fn=lambda key, default: tr_catalog(key, language=self._ui_language, default=default),
            engine_label=self.engine_label,
            toolbar_title_key=self.toolbar_title_key,
            request_button_key=self.request_button_key,
            request_hint_key=self.request_hint_key,
            loading_key=self.loading_key,
            on_open_profile_request_form=self._show_profile_info,
            on_add_user_profile=self._on_add_user_profile_clicked,
            on_expand_all=self._expand_all,
            on_collapse_all=self._collapse_all,
            on_open_profile_order=self._open_profile_order,
            on_show_info_popup=self._show_profile_info,
            on_profile_search_text_changed=self._on_profile_search_text_changed,
        )
        self._toolbar_actions_bar = shell.toolbar_actions_bar
        self._add_profile_btn = shell.add_profile_btn
        self._request_btn = shell.request_btn
        self._expand_btn = shell.expand_btn
        self._collapse_btn = shell.collapse_btn
        self._info_btn = shell.info_btn
        self._profile_search_input = shell.profile_search_input
        self._content_host_layout = shell.content_host_layout

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refresh_toolbar_layout()

    def _refresh_toolbar_layout(self) -> None:
        toolbar = self._toolbar_actions_bar
        if toolbar is None:
            return
        try:
            toolbar.refresh_for_viewport(self.viewport().width(), self.layout.contentsMargins())
        except Exception:
            pass

    def refresh_from_preset_switch(self) -> None:
        self._schedule_profiles_payload_request(force=True)

    def _schedule_profiles_payload_reload_after_preset_switch(self) -> None:
        self._profile_payload_dirty = True
        if bool(self.__dict__.get("_profile_payload_reload_after_preset_switch_scheduled", False)):
            return
        self._profile_payload_reload_after_preset_switch_scheduled = True
        try:
            QTimer.singleShot(
                PROFILE_PAYLOAD_PRESET_SWITCH_RELOAD_DELAY_MS,
                self._run_scheduled_profiles_payload_reload_after_preset_switch,
            )
        except Exception:
            self._run_scheduled_profiles_payload_reload_after_preset_switch()

    def _run_scheduled_profiles_payload_reload_after_preset_switch(self) -> None:
        self._profile_payload_reload_after_preset_switch_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if not self.__dict__.get("_profile_payload_dirty", False):
            return
        if not self.isVisible():
            return
        self._schedule_profiles_payload_request(force=True)

    def bind_ui_state_store(self, store) -> None:
        if self._ui_state_store is store:
            return
        unsubscribe = self._ui_state_unsubscribe
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
        if self._cleanup_in_progress:
            return
        if not (changed & {"active_preset_revision", "preset_content_revision"}):
            return
        self._profile_payload_dirty = True
        if not self.isVisible():
            return
        if "preset_content_revision" in changed:
            self._schedule_profiles_payload_request(force=True)
            return
        self._schedule_profiles_payload_reload_after_preset_switch()

    def _request_profiles_payload(self, *, force: bool = False) -> None:
        if self._cleanup_in_progress:
            return
        if not force and self._profile_payload_loaded_once and not self._profile_payload_dirty:
            return
        self._profile_payload_dirty = True
        runtime = self._worker_runtime("_profile_load_runtime")
        refresh_state = self._profile_load_refresh_state_obj()
        if runtime.is_running() or refresh_state.start_scheduled:
            if force:
                self._profile_payload_dirty = True
                if not refresh_state.has_pending():
                    refresh_state.pending = True
                    if runtime.is_running():
                        self._profile_load_request_id += 1
            return
        refresh_state.pending = False
        self._profile_load_request_id += 1
        request_id = self._profile_load_request_id
        if self.__dict__.get("_profiles_list") is None:
            self._clear_dynamic_widgets()
        view_state_options = self._profile_list_view_state_options()

        def _bind_worker(worker) -> None:
            worker.loaded.connect(self._on_profile_payload_loaded)
            worker.failed.connect(self._on_profile_payload_failed)

        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self._create_profile_list_load_worker(
                request_id,
                self.launch_method,
                self,
                view_state_options=view_state_options,
            ),
            bind_worker=_bind_worker,
            on_finished=self._on_profile_worker_finished,
        )
        self._profile_load_runtime_request_id = request_id

    def _profile_list_view_state_options(self) -> dict[str, object]:
        profiles_list = self.__dict__.get("_profiles_list")
        getter = getattr(profiles_list, "view_state_options", None)
        if callable(getter):
            try:
                return dict(getter() or {})
            except Exception:
                pass
        return {
            "active_profile_types": {"all"},
            "search_query": str(self.__dict__.get("_profile_search_query", "") or ""),
            "group_expanded": {},
        }

    def _on_profile_payload_loaded(self, request_id: int, payload) -> None:
        if request_id != self._profile_load_request_id or self._cleanup_in_progress:
            return
        if self._profile_load_refresh_state_obj().has_pending():
            return
        view_state = getattr(payload, "view_state", None)
        apply_signature_base = getattr(payload, "apply_signature_base", None)
        payload = getattr(payload, "payload", payload)
        self._profile_payload_loaded_once = True
        self._profile_payload_dirty = False
        self._schedule_profile_payload_apply(payload, view_state=view_state, apply_signature_base=apply_signature_base)

    def _schedule_profile_payload_apply(self, payload, *, view_state=None, apply_signature_base=None) -> None:
        self._pending_profile_payload_apply = (payload, view_state, apply_signature_base)
        if self.__dict__.get("_profile_payload_apply_scheduled", False):
            return
        self._profile_payload_apply_scheduled = True
        try:
            QTimer.singleShot(0, self._run_scheduled_profile_payload_apply)
        except Exception:
            self._run_scheduled_profile_payload_apply()

    def _run_scheduled_profile_payload_apply(self) -> None:
        pending = self.__dict__.get("_pending_profile_payload_apply")
        self._pending_profile_payload_apply = None
        self._profile_payload_apply_scheduled = False
        if pending is None or self._cleanup_in_progress:
            return
        if (
            self._profile_load_refresh_state_obj().has_pending()
            or self.__dict__.get("_profile_payload_request_scheduled", False)
        ):
            return
        is_page_hidden = False
        is_visible = getattr(self, "isVisible", None)
        if callable(is_visible):
            try:
                is_page_hidden = not bool(is_visible())
            except RuntimeError:
                is_page_hidden = False
        if is_page_hidden:
            self._profile_payload_dirty = True
            return
        payload, view_state, apply_signature_base = pending
        self._apply_payload(payload, view_state=view_state, apply_signature_base=apply_signature_base)
        self._schedule_profiles_list_show_after_page_switch()

    def _on_profile_payload_failed(self, request_id: int, error: str) -> None:
        if request_id != self._profile_load_request_id or self._cleanup_in_progress:
            return
        if (
            self._profile_load_refresh_state_obj().has_pending()
            or self.__dict__.get("_profile_payload_request_scheduled", False)
        ):
            return
        self._profile_payload_dirty = True
        log(f"{self.__class__.__name__}: не удалось прочитать профили: {error}", "ERROR")
        self._show_empty_state(
            "Не удалось показать профили выбранного пресета. "
            "Файл мог быть удалён, очищен или повреждён. "
            "Выберите пресет заново в разделе «Мои пресеты»."
        )

    def _on_profile_worker_finished(self, worker) -> None:
        state = self._profile_load_refresh_state_obj()
        if self.__dict__.get("_profile_payload_dirty", False):
            state.pending = True
        state.schedule_pending_after_finish(
            worker,
            is_current_worker_finish=lambda _runtime, finished_worker: self._accept_current_profile_load_worker_finished(
                finished_worker
            ),
            single_shot=QTimer.singleShot,
            run_scheduled=self._run_scheduled_profile_load_refresh_start,
            cleanup_in_progress=bool(self.__dict__.get("_cleanup_in_progress", False)),
        )

    def _schedule_profile_load_refresh_start(self) -> None:
        self._profile_load_refresh_state_obj().schedule_start(
            QTimer.singleShot,
            self._run_scheduled_profile_load_refresh_start,
            cleanup_in_progress=bool(self.__dict__.get("_cleanup_in_progress", False)),
            pending_when_already_scheduled=True,
        )

    def _run_scheduled_profile_load_refresh_start(self) -> None:
        pending = self._profile_load_refresh_state_obj().take_pending_for_scheduled_start(
            cleanup_in_progress=bool(self.__dict__.get("_cleanup_in_progress", False)),
        )
        if not pending:
            return
        self._schedule_profiles_payload_request(force=True)

    def _accept_current_profile_load_worker_finished(self, worker) -> bool:
        request_id = getattr(worker, "_request_id", None)
        if request_id is None:
            return False
        try:
            current_request_id = int(self.__dict__.get("_profile_load_runtime_request_id", 0) or 0)
            if int(request_id) != current_request_id:
                return False
        except (TypeError, ValueError):
            return False
        self._profile_load_runtime_request_id = 0
        return True

    def _apply_payload(self, payload, *, view_state=None, apply_signature_base=None) -> None:
        if self._content_host_layout is None:
            return
        total_started_at = time.perf_counter()
        apply_signature = profile_payload_apply_signature(
            payload,
            view_state=view_state,
            search_query=self.__dict__.get("_profile_search_query", ""),
            apply_signature_base=apply_signature_base,
        )
        if (
            self.__dict__.get("_profiles_list") is not None
            and self.__dict__.get("_last_profile_payload_apply_signature") == apply_signature
        ):
            self._log_ui_timing("profile_ui.apply_payload.duplicate", total_started_at)
            return
        self._last_profile_payload_apply_signature = apply_signature
        self._apply_selected_preset_title(payload)
        self._show_profile_normalization_info(payload)
        if not payload.items:
            self._show_empty_state(
                "В выбранном пресете нет профилей, которые можно показать на этой странице. "
                "Попробуйте другой пресет или добавьте нужный профиль."
            )
            self._log_ui_timing("profile_ui.apply_payload.total", total_started_at)
            return
        profiles_list = self._profiles_list
        if profiles_list is not None:
            started_at = time.perf_counter()
            if view_state is not None:
                profiles_list.apply_view_state(view_state)
            else:
                profiles_list.update_profiles(tuple(payload.items))
                profiles_list.set_search_query(self._profile_search_query)
            self._log_ui_timing("profile_ui.profile_list.update", started_at, extra=f"{len(payload.items)} items")
            self._log_ui_timing("profile_ui.apply_payload.total", total_started_at)
            return

        self._clear_dynamic_widgets()
        create_started_at = time.perf_counter()
        profiles_list = ProfilesList(self)
        profiles_list.profile_selected.connect(self._on_profile_clicked)
        profiles_list.profile_context_requested.connect(self._on_profile_context_requested)
        profiles_list.profile_move_requested.connect(self._on_profile_move_requested)
        profiles_list.profile_move_after_requested.connect(self._on_profile_move_after_requested)
        profiles_list.profile_move_to_folder_requested.connect(self._on_profile_move_to_folder_requested)
        profiles_list.profile_move_to_end_requested.connect(self._on_profile_move_to_end_requested)
        profiles_list.folder_context_requested.connect(self._on_folder_context_requested)
        profiles_list.folder_toggled.connect(self._on_folder_toggled)
        profiles_list.folders_toggled.connect(self._on_folders_toggled)
        self._log_ui_timing("profile_ui.profile_list.create", create_started_at)

        started_at = time.perf_counter()
        if view_state is not None:
            profiles_list.apply_view_state(view_state)
        else:
            profiles_list.build_profiles(tuple(payload.items or ()))
            profiles_list.set_search_query(self._profile_search_query)
        self._log_ui_timing("profile_ui.profile_list.build", started_at, extra=f"{len(payload.items)} items")

        attach_started_at = time.perf_counter()
        self._profiles_list = profiles_list
        self._content_host_layout.addWidget(profiles_list, 1)
        self._empty_state_label = None
        self._log_ui_timing("profile_ui.profile_list.attach", attach_started_at)
        self._log_ui_timing("profile_ui.apply_payload.total", total_started_at)

    def _on_profile_search_text_changed(self, text: str) -> None:
        self._profile_search_query = str(text or "")
        if self._profiles_list is not None:
            self._profiles_list.set_search_query(self._profile_search_query)

    def apply_sidebar_search_query(self, text: str) -> bool:
        query = str(text or "")
        search_input = self._profile_search_input
        if search_input is not None:
            try:
                if str(search_input.text() or "") == query:
                    return True
                search_input.setText(query)
                return True
            except Exception:
                pass
        self._on_profile_search_text_changed(query)
        return True

    def _log_ui_timing(self, label: str, started_at: float, *, extra: str = "") -> None:
        try:
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0
            extra_text = f" | {extra}" if extra else ""
            level = PROFILE_UI_TIMING_LOG_LEVEL if label in PROFILE_UI_VISIBLE_TIMING_LABELS else "DEBUG"
            log(f"{self.__class__.__name__}: {label}: {elapsed_ms:.1f}ms{extra_text}", level)
        except Exception:
            pass

    def _show_profile_normalization_info(self, payload) -> None:
        split_count = int(getattr(payload, "normalized_split_profiles", 0) or 0)
        created_count = int(getattr(payload, "normalized_created_profiles", 0) or 0)
        if split_count <= 0 or created_count <= 0:
            return
        try:
            InfoBar.info(
                title="Profile-ы разделены",
                content=(
                    f"Найдено сложных profile-ов: {split_count}. "
                    f"Создано отдельных profile-ов: {created_count}. "
                    "Теперь каждому списку можно менять стратегию отдельно."
                ),
                parent=self.window(),
                duration=6500,
            )
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось показать уведомление о разделении profile-ов: {exc}", "DEBUG")

    def _apply_selected_preset_title(self, payload) -> None:
        if self.title_label is None:
            return
        base_title = tr_catalog(self.title_key, language=self._ui_language, default=self.page_title)
        set_widget_text_if_changed(self.title_label, preset_setup_title_for_payload(payload, base_title))

    def _clear_dynamic_widgets(self) -> None:
        if self._content_host_layout is None:
            return
        while self._content_host_layout.count() > 0:
            item = self._content_host_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self._profiles_list = None
        self._empty_state_label = None

    def _show_empty_state(self, text: str) -> None:
        self._clear_dynamic_widgets()
        if self._content_host_layout is None:
            return
        label = BodyLabel(text)
        label.setWordWrap(True)
        self._content_host_layout.addWidget(label)
        self._empty_state_label = label

    def _on_profile_clicked(self, profile_key: str) -> None:
        self._open_profile_setup(profile_key)

    def _on_profile_context_requested(self, profile_key: str, global_pos) -> None:
        if self._profiles_list is None:
            return
        item = self._profiles_list.profile_item_for_key(profile_key)
        if item is None:
            return
        show_profile_context_menu(
            parent=self,
            item=item,
            global_pos=global_pos,
            actions=ProfileContextMenuActions(
                open_profile=self._open_profile_setup,
                set_enabled=self._set_profile_enabled_from_menu,
                duplicate_profile=self._duplicate_profile_from_menu,
                delete_from_preset=self._delete_profile_from_menu,
                edit_user_profile=self._edit_user_profile_from_menu,
                delete_user_profile=self._delete_user_profile_from_menu,
            ),
        )

    def _set_profile_enabled_from_menu(self, profile_key: str, enabled: bool) -> None:
        self._request_profile_context_action("set_enabled", profile_key, enabled=bool(enabled))

    def _duplicate_profile_from_menu(self, profile_key: str) -> None:
        self._request_profile_context_action("duplicate", profile_key)

    def _delete_profile_from_menu(self, profile_key: str) -> None:
        body = "Profile будет убран только из текущего preset. Файлы списков и пользовательский шаблон не удаляются."
        dialog = MessageBox(
            "Удалить profile из preset",
            body,
            self,
        )
        dialog.yesButton.setText("Удалить")
        dialog.cancelButton.setText("Отмена")
        set_message_box_button_accessibility(
            dialog,
            yes_name="Удалить profile из текущего preset",
            yes_description=body,
            cancel_name="Отменить удаление profile из preset",
            cancel_description="Закрывает диалог без удаления profile из текущего preset.",
        )
        if not dialog.exec():
            return
        self._request_profile_context_action("delete", profile_key)

    def _request_profile_context_action(self, action: str, profile_key: str, *, enabled: bool | None = None) -> None:
        profile_key = str(profile_key or "").strip()
        if not profile_key:
            return
        if self._profile_preset_write_operation_running():
            self._queue_profile_preset_write_operation(
                "context",
                action=str(action or ""),
                profile_key=profile_key,
                enabled=enabled,
            )
            return
        self._start_profile_context_action_worker(str(action or ""), profile_key, enabled=enabled)

    def _profile_preset_write_operation_running(self) -> bool:
        if self._profile_preset_write_state_obj().start_scheduled:
            return True
        return (
            self._worker_runtime("_profile_context_action_runtime").is_running()
            or self._worker_runtime("_profile_move_runtime").is_running()
            or self._user_profile_operation_running()
        )

    def _queue_profile_preset_write_operation(
        self,
        kind: str,
        *,
        action: str,
        profile_key: str = "",
        enabled: bool | None = None,
        source_profile_key: str = "",
        destination_profile_key: str = "",
        destination_group_key: str = "",
        profile_id: str = "",
        name: str = "",
        protocol: str = "",
        ports: str = "",
    ) -> None:
        operation = {
            "kind": str(kind or ""),
            "action": str(action or ""),
            "profile_key": str(profile_key or source_profile_key or profile_id or ""),
            "enabled": enabled,
            "source_profile_key": str(source_profile_key or ""),
            "destination_profile_key": str(destination_profile_key or ""),
            "destination_group_key": str(destination_group_key or ""),
        }
        if operation["kind"] == "user_profile":
            operation.update(
                {
                    "profile_id": str(profile_id or ""),
                    "name": str(name or ""),
                    "protocol": str(protocol or ""),
                    "ports": str(ports or ""),
                }
            )
            if operation["action"] == "update":
                profile_id_to_replace = str(operation["profile_id"] or "")
                pending_operations = self._profile_preset_write_state_obj().pending
                pending_operations[:] = [
                    pending
                    for pending in pending_operations
                    if not (
                        str(pending.get("kind") or "") == "user_profile"
                        and str(pending.get("action") or "") == "update"
                        and str(pending.get("profile_id") or "") == profile_id_to_replace
                    )
                ]
        if operation["kind"] == "context" and operation["action"] == "set_enabled":
            profile_key_to_replace = str(operation["profile_key"] or "")
            pending_operations = self._profile_preset_write_state_obj().pending
            pending_operations[:] = [
                pending
                for pending in pending_operations
                if not (
                    str(pending.get("kind") or "") == "context"
                    and str(pending.get("action") or "") == "set_enabled"
                    and str(pending.get("profile_key") or "") == profile_key_to_replace
                )
            ]
        if operation["kind"] == "move":
            source_profile_key_to_replace = str(operation["source_profile_key"] or "")
            pending_operations = self._profile_preset_write_state_obj().pending
            pending_operations[:] = [
                pending
                for pending in pending_operations
                if not (
                    str(pending.get("kind") or "") == "move"
                    and str(pending.get("source_profile_key") or "") == source_profile_key_to_replace
                )
            ]
        self._profile_preset_write_state_obj().append(operation)

    def _pop_next_profile_preset_write_operation(self) -> dict[str, object] | None:
        pending_operations = self._profile_preset_write_state_obj().pending
        if pending_operations:
            return dict(pending_operations.pop(0))
        return None

    def _has_pending_profile_preset_write_operation(self) -> bool:
        return self._profile_preset_write_state_obj().has_pending()

    def _has_pending_user_profile_operation(self) -> bool:
        return bool(self._pending_user_profile_operations)

    def _schedule_next_profile_preset_write_operation_start(self) -> bool:
        if self._profile_preset_write_operation_running():
            return True
        if not self._has_pending_profile_preset_write_operation():
            return False
        if self._profile_preset_write_state_obj().start_scheduled:
            return True
        self._profile_preset_write_state_obj().start_scheduled = True
        try:
            QTimer.singleShot(0, self._run_scheduled_profile_preset_write_operation_start)
        except Exception:
            self._run_scheduled_profile_preset_write_operation_start()
        return True

    def _run_scheduled_profile_preset_write_operation_start(self) -> None:
        self._profile_preset_write_state_obj().start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._start_next_profile_preset_write_operation()

    def _queue_profile_preset_write_operation_from_dict(self, operation: dict[str, object]) -> bool:
        pending = dict(operation or {})
        self._queue_profile_preset_write_operation(
            str(pending.get("kind") or ""),
            action=str(pending.get("action") or ""),
            profile_key=str(pending.get("profile_key") or ""),
            enabled=pending.get("enabled"),
            source_profile_key=str(pending.get("source_profile_key") or ""),
            destination_profile_key=str(pending.get("destination_profile_key") or ""),
            destination_group_key=str(pending.get("destination_group_key") or ""),
            profile_id=str(pending.get("profile_id") or ""),
            name=str(pending.get("name") or ""),
            protocol=str(pending.get("protocol") or ""),
            ports=str(pending.get("ports") or ""),
        )
        return True

    def _schedule_next_profile_preset_write_operation_after_finish(
        self,
        request_attr: str,
        worker,
    ) -> tuple[bool, bool]:
        accepted = False

        def _is_current_worker_finish(_runtime, finished_worker) -> bool:
            nonlocal accepted
            accepted = self._accept_current_preset_setup_worker_finished(request_attr, finished_worker)
            return accepted

        def _single_shot(delay: int, callback) -> None:
            try:
                QTimer.singleShot(delay, callback)
            except Exception:
                callback()

        operation = self._profile_preset_write_state_obj().schedule_next_after_finish(
            worker,
            is_current_worker_finish=_is_current_worker_finish,
            single_shot=_single_shot,
            start=lambda pending: self._run_profile_preset_write_operation(dict(pending or {})),
            queue_item=self._queue_profile_preset_write_operation_from_dict,
            is_cleanup_in_progress=lambda: bool(self.__dict__.get("_cleanup_in_progress", False)),
        )
        return accepted, operation is not None

    def _profile_load_refresh_state_obj(self) -> LatestValueWorkerState:
        state = self.__dict__.get("_profile_load_refresh_state")
        runtime = self.__dict__.get("_profile_load_runtime")
        if state is None:
            pending = bool(self.__dict__.pop("_profile_load_refresh_pending", False))
            start_scheduled = bool(self.__dict__.pop("_profile_load_refresh_start_scheduled", False))
            state = LatestValueWorkerState(
                runtime,
                empty_value=False,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_profile_load_refresh_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _profile_load_refresh_pending(self) -> bool:
        return bool(self._profile_load_refresh_state_obj().pending)

    @_profile_load_refresh_pending.setter
    def _profile_load_refresh_pending(self, value: bool) -> None:
        self._profile_load_refresh_state_obj().pending = bool(value)

    @property
    def _profile_load_refresh_start_scheduled(self) -> bool:
        return bool(self._profile_load_refresh_state_obj().start_scheduled)

    @_profile_load_refresh_start_scheduled.setter
    def _profile_load_refresh_start_scheduled(self, value: bool) -> None:
        self._profile_load_refresh_state_obj().start_scheduled = bool(value)

    def _profile_preset_write_state_obj(self) -> QueuedWorkerState[dict[str, object]]:
        state = self.__dict__.get("_profile_preset_write_state")
        runtime = self.__dict__.get("_profile_context_action_runtime")
        if state is None:
            pending = list(self.__dict__.pop("_pending_profile_preset_write_operations", []) or [])
            pending.extend(
                self._profile_preset_write_operation_from_context_action(operation)
                for operation in list(self.__dict__.pop("_pending_profile_context_actions", []) or [])
            )
            pending.extend(
                self._profile_preset_write_operation_from_move_operation(operation)
                for operation in list(self.__dict__.pop("_pending_profile_moves", []) or [])
            )
            pending.extend(
                self._profile_preset_write_operation_from_user_profile_operation(operation)
                for operation in list(self.__dict__.pop("_pending_user_profile_operations", []) or [])
            )
            start_scheduled = bool(self.__dict__.pop("_profile_preset_write_operation_start_scheduled", False))
            state = QueuedWorkerState(
                runtime,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_profile_preset_write_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _pending_profile_preset_write_operations(self) -> list[dict[str, object]]:
        return self._profile_preset_write_state_obj().pending

    @_pending_profile_preset_write_operations.setter
    def _pending_profile_preset_write_operations(self, value: list[dict[str, object]]) -> None:
        self._profile_preset_write_state_obj().pending = list(value or [])

    @property
    def _profile_preset_write_operation_start_scheduled(self) -> bool:
        return bool(self._profile_preset_write_state_obj().start_scheduled)

    @_profile_preset_write_operation_start_scheduled.setter
    def _profile_preset_write_operation_start_scheduled(self, value: bool) -> None:
        self._profile_preset_write_state_obj().start_scheduled = bool(value)

    @staticmethod
    def _profile_preset_write_operation_from_context_action(operation) -> dict[str, object]:
        pending = dict(operation or {})
        return {
            "kind": "context",
            "action": str(pending.get("action") or ""),
            "profile_key": str(pending.get("profile_key") or ""),
            "enabled": pending.get("enabled"),
            "source_profile_key": "",
            "destination_profile_key": "",
            "destination_group_key": "",
        }

    @staticmethod
    def _context_action_from_profile_preset_write_operation(operation) -> dict[str, object] | None:
        pending = dict(operation or {})
        if str(pending.get("kind") or "") != "context":
            return None
        return {
            "action": str(pending.get("action") or ""),
            "profile_key": str(pending.get("profile_key") or ""),
            "enabled": pending.get("enabled"),
        }

    @staticmethod
    def _profile_preset_write_operation_from_move_operation(operation) -> dict[str, object]:
        pending = dict(operation or {})
        source_profile_key = str(pending.get("source_profile_key") or "")
        return {
            "kind": "move",
            "action": str(pending.get("action") or ""),
            "profile_key": source_profile_key,
            "enabled": None,
            "source_profile_key": source_profile_key,
            "destination_profile_key": str(pending.get("destination_profile_key") or ""),
            "destination_group_key": str(pending.get("destination_group_key") or ""),
        }

    @staticmethod
    def _move_operation_from_profile_preset_write_operation(operation) -> dict[str, str] | None:
        pending = dict(operation or {})
        if str(pending.get("kind") or "") != "move":
            return None
        return {
            "action": str(pending.get("action") or ""),
            "source_profile_key": str(pending.get("source_profile_key") or pending.get("profile_key") or ""),
            "destination_profile_key": str(pending.get("destination_profile_key") or ""),
            "destination_group_key": str(pending.get("destination_group_key") or ""),
        }

    @staticmethod
    def _profile_preset_write_operation_from_user_profile_operation(operation) -> dict[str, object]:
        pending = dict(operation or {})
        profile_id = str(pending.get("profile_id") or "")
        return {
            "kind": "user_profile",
            "action": str(pending.get("action") or ""),
            "profile_key": profile_id,
            "enabled": None,
            "source_profile_key": "",
            "destination_profile_key": "",
            "destination_group_key": "",
            "profile_id": profile_id,
            "name": str(pending.get("name") or ""),
            "protocol": str(pending.get("protocol") or ""),
            "ports": str(pending.get("ports") or ""),
        }

    @staticmethod
    def _user_profile_operation_from_profile_preset_write_operation(operation) -> dict[str, str] | None:
        pending = dict(operation or {})
        if str(pending.get("kind") or "") != "user_profile":
            return None
        return {
            "action": str(pending.get("action") or ""),
            "profile_id": str(pending.get("profile_id") or pending.get("profile_key") or ""),
            "name": str(pending.get("name") or ""),
            "protocol": str(pending.get("protocol") or ""),
            "ports": str(pending.get("ports") or ""),
        }

    @property
    def _pending_user_profile_operations(self) -> list[dict[str, str]]:
        operations: list[dict[str, str]] = []
        for operation in self._profile_preset_write_state_obj().pending:
            user_profile_operation = self._user_profile_operation_from_profile_preset_write_operation(operation)
            if user_profile_operation is not None:
                operations.append(user_profile_operation)
        return operations

    @_pending_user_profile_operations.setter
    def _pending_user_profile_operations(self, value: list[dict[str, str]]) -> None:
        state = self._profile_preset_write_state_obj()
        state.pending[:] = [
            operation
            for operation in state.pending
            if str(operation.get("kind") or "") != "user_profile"
        ]
        state.pending.extend(
            self._profile_preset_write_operation_from_user_profile_operation(operation)
            for operation in list(value or [])
        )

    @property
    def _pending_profile_context_actions(self) -> list[dict[str, object]]:
        operations: list[dict[str, object]] = []
        for operation in self._profile_preset_write_state_obj().pending:
            context_action = self._context_action_from_profile_preset_write_operation(operation)
            if context_action is not None:
                operations.append(context_action)
        return operations

    @_pending_profile_context_actions.setter
    def _pending_profile_context_actions(self, value: list[dict[str, object]]) -> None:
        state = self._profile_preset_write_state_obj()
        state.pending[:] = [
            operation
            for operation in state.pending
            if str(operation.get("kind") or "") != "context"
        ]
        state.pending.extend(
            self._profile_preset_write_operation_from_context_action(operation)
            for operation in list(value or [])
        )

    @property
    def _pending_profile_moves(self) -> list[dict[str, str]]:
        operations: list[dict[str, str]] = []
        for operation in self._profile_preset_write_state_obj().pending:
            move_operation = self._move_operation_from_profile_preset_write_operation(operation)
            if move_operation is not None:
                operations.append(move_operation)
        return operations

    @_pending_profile_moves.setter
    def _pending_profile_moves(self, value: list[dict[str, str]]) -> None:
        state = self._profile_preset_write_state_obj()
        state.pending[:] = [
            operation
            for operation in state.pending
            if str(operation.get("kind") or "") != "move"
        ]
        state.pending.extend(
            self._profile_preset_write_operation_from_move_operation(operation)
            for operation in list(value or [])
        )

    def _start_next_profile_preset_write_operation(self) -> bool:
        if self._profile_preset_write_operation_running():
            return True
        pending = self._pop_next_profile_preset_write_operation()
        if not pending:
            return False
        return self._run_profile_preset_write_operation(pending)

    def _run_profile_preset_write_operation(self, pending: dict[str, object] | None) -> bool:
        pending = dict(pending or {})
        if self.__dict__.get("_cleanup_in_progress", False):
            return False
        if self._profile_preset_write_operation_running():
            self._queue_profile_preset_write_operation_from_dict(pending)
            return False
        if pending.get("kind") == "context":
            self._start_profile_context_action_worker(
                str(pending.get("action") or ""),
                str(pending.get("profile_key") or ""),
                enabled=pending.get("enabled"),
            )
            return True
        if pending.get("kind") == "move":
            self._start_profile_move_worker(
                str(pending.get("action") or ""),
                str(pending.get("source_profile_key") or ""),
                destination_profile_key=str(pending.get("destination_profile_key") or ""),
                destination_group_key=str(pending.get("destination_group_key") or ""),
            )
            return True
        if pending.get("kind") == "user_profile":
            action = str(pending.get("action") or "")
            if action == "create":
                self._request_user_profile_create(
                    name=str(pending.get("name") or ""),
                    protocol=str(pending.get("protocol") or ""),
                    ports=str(pending.get("ports") or ""),
                )
                return True
            if action == "update":
                self._request_user_profile_update(
                    str(pending.get("profile_id") or ""),
                    name=str(pending.get("name") or ""),
                    protocol=str(pending.get("protocol") or ""),
                    ports=str(pending.get("ports") or ""),
                )
                return True
            if action == "delete":
                self._request_user_profile_delete(str(pending.get("profile_id") or ""))
                return True
        return self._start_next_profile_preset_write_operation()

    def _start_profile_context_action_worker(
        self,
        action: str,
        profile_key: str,
        *,
        enabled: bool | None = None,
    ) -> None:
        runtime = self._worker_runtime("_profile_context_action_runtime")
        self._profile_context_action_request_id = int(
            self.__dict__.get("_profile_context_action_request_id", 0) or 0
        ) + 1
        request_id = self._profile_context_action_request_id
        if str(action or "") == "set_enabled" and enabled is not None:
            self.__dict__.setdefault("_profile_context_action_enabled_by_request", {})[request_id] = bool(enabled)

        def _bind_worker(worker) -> None:
            worker.finished_action.connect(self._on_profile_context_action_finished)
            worker.failed.connect(self._on_profile_context_action_failed)

        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self._create_profile_context_action_worker(
                request_id,
                self.launch_method,
                action=str(action or ""),
                profile_key=profile_key,
                enabled=enabled,
                parent=self,
            ),
            bind_worker=_bind_worker,
            on_finished=self._on_profile_context_action_worker_finished,
        )

    def _on_profile_context_action_finished(self, request_id: int, action: str, profile_key: str, result) -> None:
        if request_id != int(getattr(self, "_profile_context_action_request_id", 0) or 0):
            return
        applied_pending_result = False
        if action == "set_enabled":
            applied_pending_result = self._apply_profile_context_enabled_result(
                request_id,
                profile_key,
                result,
            )
        if self._has_pending_profile_preset_write_operation():
            return
        if action == "set_enabled":
            if not applied_pending_result:
                target_key = _profile_context_action_result_key(result) or str(profile_key or "").strip()
                self._refresh_profile_item_locally(profile_key, target_key)
            return
        if action == "duplicate":
            target_item = _profile_context_action_result_item(result)
            if target_item is not None and self._add_created_user_profile_locally(target_item):
                return
            self._add_profile_item_locally(profile_key, _profile_context_action_result_key(result))
            return
        if action == "delete" and bool(result):
            self._remove_profile_item_locally(profile_key)

    def _apply_profile_context_enabled_result(self, request_id: int, profile_key: str, result) -> bool:
        target_key = _profile_context_action_result_key(result) or str(profile_key or "").strip()
        target_item = _profile_context_action_result_item(result)
        requested_enabled = bool(
            self.__dict__.get("_profile_context_action_enabled_by_request", {}).pop(request_id, True)
        )
        if target_key == str(profile_key or "") and self._apply_profile_enabled_locally(profile_key, requested_enabled):
            self._profile_payload_dirty = True
            return True
        if target_item is not None and self._add_created_user_profile_locally(target_item):
            return True
        return False

    def _on_profile_context_action_failed(self, request_id: int, error: str) -> None:
        if request_id != int(getattr(self, "_profile_context_action_request_id", 0) or 0):
            return
        if self._has_pending_profile_preset_write_operation():
            self.__dict__.get("_profile_context_action_enabled_by_request", {}).pop(request_id, None)
            return
        self.__dict__.get("_profile_context_action_enabled_by_request", {}).pop(request_id, None)
        log(f"{self.__class__.__name__}: не удалось выполнить действие profile: {error}", "ERROR")
        InfoBar.error(title="Ошибка", content=str(error), parent=self.window())

    def _on_profile_context_action_worker_finished(self, worker) -> None:
        self._schedule_next_profile_preset_write_operation_after_finish(
            "_profile_context_action_request_id",
            worker,
        )

    def _create_profile_context_action_worker(
        self,
        request_id: int,
        launch_method: str,
        *,
        action: str,
        profile_key: str,
        enabled: bool | None = None,
        parent=None,
    ):
        return self._create_profile_context_action_worker_fn(
            request_id,
            launch_method,
            action=action,
            profile_key=profile_key,
            enabled=enabled,
            parent=parent,
        )

    def _create_profile_list_load_worker(
        self,
        request_id: int,
        launch_method: str,
        parent=None,
        *,
        view_state_options: dict[str, object] | None = None,
    ):
        return self._create_profile_list_load_worker_fn(
            request_id,
            launch_method,
            parent,
            view_state_options=view_state_options,
        )

    def _create_profile_item_refresh_worker(
        self,
        request_id: int,
        launch_method: str,
        *,
        old_profile_key: str,
        profile_key: str,
        parent=None,
    ):
        return self._create_profile_item_refresh_worker_fn(
            request_id,
            launch_method,
            old_profile_key=old_profile_key,
            profile_key=profile_key,
            parent=parent,
        )

    def _sync_profile_list_locally(self) -> None:
        self._profile_payload_dirty = True
        self._schedule_profiles_payload_request(force=True)

    def _refresh_profile_item_locally(self, old_profile_key: str, profile_key: str) -> None:
        old_key = str(old_profile_key or "").strip()
        clean_profile_key = str(profile_key or "").strip()
        self._profile_payload_dirty = True
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if not clean_profile_key:
            self._schedule_profiles_payload_request(force=True)
            return
        runtime = self._worker_runtime("_profile_item_refresh_runtime")

        def _bind_worker(worker) -> None:
            worker.refreshed.connect(self._on_profile_item_refreshed)
            worker.failed.connect(self._on_profile_item_refresh_failed)

        request_id, _worker = runtime.start_qthread_worker(
            worker_factory=lambda runtime_request_id: self._create_profile_item_refresh_worker(
                runtime_request_id,
                self.launch_method,
                old_profile_key=old_key or clean_profile_key,
                profile_key=clean_profile_key,
                parent=self,
            ),
            bind_worker=_bind_worker,
        )
        self._profile_item_refresh_request_id = request_id

    def _on_profile_item_refreshed(
        self,
        request_id: int,
        old_profile_key: str,
        profile_key: str,
        item,
    ) -> None:
        if request_id != int(self.__dict__.get("_profile_item_refresh_request_id", 0) or 0):
            return
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if item is not None and self._replace_profile_item_locally(old_profile_key or profile_key, item):
            return
        self._schedule_profiles_payload_request(force=True)

    def _on_profile_item_refresh_failed(self, request_id: int, error: str) -> None:
        if request_id != int(self.__dict__.get("_profile_item_refresh_request_id", 0) or 0):
            return
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        log(f"{self.__class__.__name__}: не удалось обновить profile item: {error}", "DEBUG")
        self._schedule_profiles_payload_request(force=True)

    def _replace_profile_item_locally(self, old_profile_key: str, item) -> bool:
        profiles_list = self.__dict__.get("_profiles_list")
        if profiles_list is None:
            return False
        profile_key = str(getattr(item, "key", "") or old_profile_key or "").strip()
        if not profile_key:
            return False
        if not profiles_list.replace_profile_item(old_profile_key, item):
            return False
        self._profile_payload_dirty = True
        return True

    def _apply_profile_enabled_locally(self, profile_key: str, enabled: bool) -> bool:
        profiles_list = self.__dict__.get("_profiles_list")
        if profiles_list is None:
            return False
        return profiles_list.set_profile_enabled(profile_key, bool(enabled))

    def _add_profile_item_locally(self, profile_key: str | None, new_profile_key: str | None = None) -> None:
        source_key = str(profile_key or "").strip()
        duplicate_key = str(new_profile_key or "").strip()
        profiles_list = self.__dict__.get("_profiles_list")
        if (
            profiles_list is not None
            and source_key
            and duplicate_key
            and profiles_list.duplicate_profile_item(source_key, duplicate_key)
        ):
            self._profile_payload_dirty = True
            return
        self._profile_payload_dirty = True
        self._schedule_profiles_payload_request(force=True)

    def _remove_profile_item_locally(self, profile_key: str) -> None:
        profiles_list = self.__dict__.get("_profiles_list")
        if profiles_list is not None and profiles_list.remove_profile_item(profile_key):
            self._profile_payload_dirty = True
            return
        self.refresh_from_preset_switch()

    def _edit_user_profile_from_menu(self, profile_key: str) -> None:
        if self._profiles_list is None:
            return
        item = self._profiles_list.profile_item_for_key(profile_key)
        if item is None:
            return
        profile_id = _user_profile_id_from_item(profile_key, item)
        if not profile_id:
            return
        protocol, ports = _protocol_and_ports_from_match_lines(tuple(getattr(item, "match_lines", ()) or ()))
        dialog = CreateUserProfileDialog(
            self,
            title="Изменить profile",
            subtitle="Изменяет пользовательский profile и обновляет все preset-ы, где есть profile с таким же именем.",
            button_text="Сохранить",
            name=str(getattr(item, "display_name", "") or ""),
            protocol=protocol,
            ports=ports,
        )
        if not dialog.exec():
            return
        name, protocol, ports = dialog.values()
        self._request_user_profile_update(
            profile_id,
            name=name,
            protocol=protocol,
            ports=ports,
        )

    def _delete_user_profile_from_menu(self, profile_key: str) -> None:
        if self._profiles_list is None:
            return
        item = self._profiles_list.profile_item_for_key(profile_key)
        if item is None:
            return
        profile_id = _user_profile_id_from_item(profile_key, item)
        if not profile_id:
            return
        body = (
            "Profile будет удалён из библиотеки, его файлы списков будут удалены, "
            "а profile-ы с таким же именем будут убраны из preset-ов."
        )
        dialog = MessageBox(
            "Удалить пользовательский profile",
            body,
            self,
        )
        dialog.yesButton.setText("Удалить")
        dialog.cancelButton.setText("Отмена")
        set_message_box_button_accessibility(
            dialog,
            yes_name="Удалить пользовательский profile",
            yes_description=body,
            cancel_name="Отменить удаление пользовательского profile",
            cancel_description="Закрывает диалог без удаления пользовательского profile.",
        )
        if not dialog.exec():
            return
        self._request_user_profile_delete(profile_id)

    def _set_user_profile_actions_enabled(self, enabled: bool) -> None:
        if self._add_profile_btn is not None:
            set_widget_enabled_if_changed(self._add_profile_btn, enabled)

    def _user_profile_operation_running(self) -> bool:
        for attr in (
            "_user_profile_create_runtime",
            "_user_profile_update_runtime",
            "_user_profile_delete_runtime",
        ):
            runtime = self.__dict__.get(attr)
            if runtime is None:
                continue
            try:
                if runtime.is_running():
                    return True
            except Exception:
                return True
        return False

    def _create_user_profile_create_worker(self, request_id: int, *, name: str, protocol: str, ports: str):
        return self._create_user_profile_create_worker_fn(
            request_id,
            self.launch_method,
            name=name,
            protocol=protocol,
            ports=ports,
            parent=self,
        )

    def _create_user_profile_update_worker(
        self,
        request_id: int,
        *,
        profile_id: str,
        name: str,
        protocol: str,
        ports: str,
    ):
        return self._create_user_profile_update_worker_fn(
            request_id,
            self.launch_method,
            profile_id=profile_id,
            name=name,
            protocol=protocol,
            ports=ports,
            parent=self,
        )

    def _create_user_profile_delete_worker(self, request_id: int, *, profile_id: str):
        return self._create_user_profile_delete_worker_fn(
            request_id,
            self.launch_method,
            profile_id=profile_id,
            parent=self,
        )

    def _request_user_profile_create(self, *, name: str, protocol: str, ports: str) -> None:
        if self._profile_preset_write_operation_running():
            self._queue_profile_preset_write_operation(
                "user_profile",
                action="create",
                name=name,
                protocol=protocol,
                ports=ports,
            )
            return
        self._user_profile_create_request_id = int(self.__dict__.get("_user_profile_create_request_id", 0) or 0) + 1
        request_id = self._user_profile_create_request_id
        self._set_user_profile_actions_enabled(False)
        runtime = self._worker_runtime("_user_profile_create_runtime")

        def _bind_worker(worker) -> None:
            worker.created.connect(self._on_user_profile_create_finished)
            worker.failed.connect(self._on_user_profile_create_failed)

        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self._create_user_profile_create_worker(
                request_id,
                name=name,
                protocol=protocol,
                ports=ports,
            ),
            bind_worker=_bind_worker,
            on_finished=self._on_user_profile_create_worker_finished,
        )

    def _on_user_profile_create_finished(self, request_id: int, _profile_id: str, profile_item=None) -> None:
        if request_id != int(getattr(self, "_user_profile_create_request_id", 0) or 0):
            return
        if self._has_pending_user_profile_operation():
            return
        InfoBar.success(
            title="Profile добавлен",
            content="Он появился в общем списке и пока выключен во всех preset-ах.",
            parent=self.window(),
        )
        if self._add_created_user_profile_locally(profile_item):
            return
        self.refresh_from_preset_switch()

    def _add_created_user_profile_locally(self, profile_item) -> bool:
        profiles_list = self.__dict__.get("_profiles_list")
        if profiles_list is None or profile_item is None:
            return False
        if not profiles_list.add_profile_item(profile_item):
            return False
        self._profile_payload_dirty = True
        return True

    def _on_user_profile_create_failed(self, request_id: int, error: str) -> None:
        if request_id != int(getattr(self, "_user_profile_create_request_id", 0) or 0):
            return
        if self._has_pending_user_profile_operation():
            return
        log(f"{self.__class__.__name__}: не удалось создать пользовательский profile: {error}", "ERROR")
        InfoBar.error(title="Ошибка", content=str(error), parent=self.window())

    def _on_user_profile_create_worker_finished(self, worker) -> None:
        accepted, scheduled = self._schedule_next_profile_preset_write_operation_after_finish(
            "_user_profile_create_request_id",
            worker,
        )
        if not accepted:
            return
        if scheduled:
            return
        if not self._user_profile_operation_running():
            self._set_user_profile_actions_enabled(True)

    def _request_user_profile_update(self, profile_id: str, *, name: str, protocol: str, ports: str) -> None:
        profile_id = str(profile_id or "").strip()
        if not profile_id:
            return
        if self._profile_preset_write_operation_running():
            self._queue_profile_preset_write_operation(
                "user_profile",
                action="update",
                profile_id=profile_id,
                name=name,
                protocol=protocol,
                ports=ports,
            )
            return
        self._user_profile_update_request_id = int(self.__dict__.get("_user_profile_update_request_id", 0) or 0) + 1
        request_id = self._user_profile_update_request_id
        self._set_user_profile_actions_enabled(False)
        runtime = self._worker_runtime("_user_profile_update_runtime")

        def _bind_worker(worker) -> None:
            worker.updated.connect(self._on_user_profile_update_finished)
            worker.failed.connect(self._on_user_profile_update_failed)

        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self._create_user_profile_update_worker(
                request_id,
                profile_id=profile_id,
                name=name,
                protocol=protocol,
                ports=ports,
            ),
            bind_worker=_bind_worker,
            on_finished=self._on_user_profile_update_worker_finished,
        )

    def _on_user_profile_update_finished(
        self,
        request_id: int,
        profile_id: str,
        changed: int,
        profile_items=(),
    ) -> None:
        if request_id != int(getattr(self, "_user_profile_update_request_id", 0) or 0):
            return
        if self._has_pending_user_profile_operation():
            return
        InfoBar.success(
            title="Profile изменён",
            content=f"Обновлено profile-ов в preset-ах: {int(changed or 0)}.",
            parent=self.window(),
        )
        if self._replace_user_profile_items_locally(profile_id, profile_items):
            return
        self.refresh_from_preset_switch()

    def _replace_user_profile_items_locally(self, profile_id: str, profile_items) -> bool:
        profiles_list = self.__dict__.get("_profiles_list")
        if profiles_list is None:
            return False
        if not profiles_list.replace_user_profile_items(profile_id, tuple(profile_items or ())):
            return False
        self._profile_payload_dirty = True
        return True

    def _on_user_profile_update_failed(self, request_id: int, error: str) -> None:
        if request_id != int(getattr(self, "_user_profile_update_request_id", 0) or 0):
            return
        if self._has_pending_user_profile_operation():
            return
        log(f"{self.__class__.__name__}: не удалось изменить пользовательский profile: {error}", "ERROR")
        InfoBar.error(title="Ошибка", content=str(error), parent=self.window())

    def _on_user_profile_update_worker_finished(self, worker) -> None:
        accepted, scheduled = self._schedule_next_profile_preset_write_operation_after_finish(
            "_user_profile_update_request_id",
            worker,
        )
        if not accepted:
            return
        if scheduled:
            return
        if not self._user_profile_operation_running():
            self._set_user_profile_actions_enabled(True)

    def _request_user_profile_delete(self, profile_id: str) -> None:
        profile_id = str(profile_id or "").strip()
        if not profile_id:
            return
        if self._profile_preset_write_operation_running():
            self._queue_profile_preset_write_operation(
                "user_profile",
                action="delete",
                profile_id=profile_id,
            )
            return
        self._user_profile_delete_request_id = int(self.__dict__.get("_user_profile_delete_request_id", 0) or 0) + 1
        request_id = self._user_profile_delete_request_id
        self._set_user_profile_actions_enabled(False)
        runtime = self._worker_runtime("_user_profile_delete_runtime")

        def _bind_worker(worker) -> None:
            worker.deleted.connect(self._on_user_profile_delete_finished)
            worker.failed.connect(self._on_user_profile_delete_failed)

        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self._create_user_profile_delete_worker(
                request_id,
                profile_id=profile_id,
            ),
            bind_worker=_bind_worker,
            on_finished=self._on_user_profile_delete_worker_finished,
        )

    def _on_user_profile_delete_finished(self, request_id: int, _profile_id: str, changed: int) -> None:
        if request_id != int(getattr(self, "_user_profile_delete_request_id", 0) or 0):
            return
        if self._has_pending_user_profile_operation():
            return
        InfoBar.success(
            title="Profile удалён",
            content=f"Удалено profile-ов из preset-ов: {int(changed or 0)}.",
            parent=self.window(),
        )
        if self._remove_user_profile_items_locally(_profile_id):
            return
        self.refresh_from_preset_switch()

    def _remove_user_profile_items_locally(self, profile_id: str) -> bool:
        profiles_list = self.__dict__.get("_profiles_list")
        if profiles_list is None:
            return False
        if not profiles_list.remove_user_profile_items(profile_id):
            return False
        self._profile_payload_dirty = True
        return True

    def _on_user_profile_delete_failed(self, request_id: int, error: str) -> None:
        if request_id != int(getattr(self, "_user_profile_delete_request_id", 0) or 0):
            return
        if self._has_pending_user_profile_operation():
            return
        log(f"{self.__class__.__name__}: не удалось удалить пользовательский profile: {error}", "ERROR")
        InfoBar.error(title="Ошибка", content=str(error), parent=self.window())

    def _on_user_profile_delete_worker_finished(self, worker) -> None:
        accepted, scheduled = self._schedule_next_profile_preset_write_operation_after_finish(
            "_user_profile_delete_request_id",
            worker,
        )
        if not accepted:
            return
        if scheduled:
            return
        if not self._user_profile_operation_running():
            self._set_user_profile_actions_enabled(True)

    def _on_profile_move_requested(
        self,
        source_profile_key: str,
        destination_profile_key: str,
        destination_group_key: str = "",
    ) -> None:
        self._request_profile_move(
            "before",
            source_profile_key,
            destination_profile_key=destination_profile_key,
            destination_group_key=destination_group_key,
        )

    def _on_profile_move_after_requested(
        self,
        source_profile_key: str,
        destination_profile_key: str,
        destination_group_key: str = "",
    ) -> None:
        self._request_profile_move(
            "after",
            source_profile_key,
            destination_profile_key=destination_profile_key,
            destination_group_key=destination_group_key,
        )

    def _on_profile_move_to_end_requested(self, profile_key: str) -> None:
        self._request_profile_move("end", profile_key)

    def _on_profile_move_to_folder_requested(self, profile_key: str, folder_key: str) -> None:
        self._request_profile_move("folder", profile_key, destination_group_key=folder_key)

    def _request_profile_move(
        self,
        action: str,
        source_profile_key: str,
        *,
        destination_profile_key: str = "",
        destination_group_key: str = "",
    ) -> None:
        source_profile_key = str(source_profile_key or "").strip()
        if not source_profile_key:
            return
        if self._profile_preset_write_operation_running():
            self._queue_profile_preset_write_operation(
                "move",
                action=str(action or ""),
                source_profile_key=source_profile_key,
                destination_profile_key=str(destination_profile_key or ""),
                destination_group_key=str(destination_group_key or ""),
            )
            return
        self._start_profile_move_worker(
            str(action or ""),
            source_profile_key,
            destination_profile_key=destination_profile_key,
            destination_group_key=destination_group_key,
        )

    def _start_profile_move_worker(
        self,
        action: str,
        source_profile_key: str,
        *,
        destination_profile_key: str = "",
        destination_group_key: str = "",
    ) -> None:
        runtime = self._worker_runtime("_profile_move_runtime")
        self._profile_move_request_id = int(self.__dict__.get("_profile_move_request_id", 0) or 0) + 1
        request_id = self._profile_move_request_id

        def _bind_worker(worker) -> None:
            worker.moved.connect(self._on_profile_move_finished)
            worker.failed.connect(self._on_profile_move_failed)

        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self._create_profile_move_worker(
                request_id,
                self.launch_method,
                action=str(action or ""),
                source_profile_key=source_profile_key,
                destination_profile_key=destination_profile_key,
                destination_group_key=destination_group_key,
            ),
            bind_worker=_bind_worker,
            on_finished=self._on_profile_move_worker_finished,
        )

    def _on_profile_move_finished(
        self,
        request_id: int,
        action: str,
        source_profile_key: str,
        destination_profile_key: str,
        destination_group_key: str,
        result,
    ) -> None:
        if request_id != int(getattr(self, "_profile_move_request_id", 0) or 0):
            return
        applied_locally = False
        if result:
            applied_locally = self._apply_profile_move_locally(
                action,
                source_profile_key,
                destination_profile_key=destination_profile_key,
                destination_group_key=destination_group_key,
            )
        if self._has_pending_profile_preset_write_operation():
            if applied_locally:
                self._profile_payload_dirty = True
            return
        if applied_locally:
            self._profile_payload_dirty = True
            return
        self.refresh_from_preset_switch()

    def _on_profile_move_failed(self, request_id: int, error: str) -> None:
        if request_id != int(getattr(self, "_profile_move_request_id", 0) or 0):
            return
        if self._has_pending_profile_preset_write_operation():
            return
        log(f"{self.__class__.__name__}: не удалось переместить profile: {error}", "ERROR")
        self.refresh_from_preset_switch()

    def _on_profile_move_worker_finished(self, worker) -> None:
        self._schedule_next_profile_preset_write_operation_after_finish(
            "_profile_move_request_id",
            worker,
        )

    def _apply_profile_move_locally(
        self,
        action: str,
        source_profile_key: str,
        *,
        destination_profile_key: str = "",
        destination_group_key: str = "",
    ) -> bool:
        profiles_list = self._profiles_list
        if profiles_list is None:
            return False
        destination_kind_by_action = {
            "before": "profile",
            "after": "profile_after",
            "end": "end",
            "folder": "folder",
        }
        destination_kind = destination_kind_by_action.get(str(action or "").strip())
        if not destination_kind:
            return False
        return profiles_list.move_profile_item(
            source_profile_key,
            destination_kind,
            destination_profile_key,
            destination_group_key,
        )

    def _create_profile_move_worker(
        self,
        request_id: int,
        launch_method: str,
        *,
        action: str,
        source_profile_key: str,
        destination_profile_key: str = "",
        destination_group_key: str = "",
    ):
        return self._create_profile_move_worker_fn(
            request_id,
            launch_method,
            action=action,
            source_profile_key=source_profile_key,
            destination_profile_key=destination_profile_key,
            destination_group_key=destination_group_key,
            parent=self,
        )

    def _on_folder_context_requested(self, folder_key: str, global_pos) -> None:
        self._request_profile_folder_action(
            "load_state",
            folder_key=folder_key,
            context_extra={
                "show_menu": True,
                "folder_key": str(folder_key or ""),
                "global_pos": global_pos,
            },
        )

    def _show_folder_menu_with_state(self, folder_key: str, global_pos, folder_state: dict) -> None:
        show_profile_folder_menu(
            parent=self,
            folder_key=folder_key,
            global_pos=global_pos,
            folder_state=folder_state,
            refresh_fn=self.refresh_from_preset_switch,
            request_folder_action_fn=self._request_profile_folder_action,
            log_fn=log,
        )

    def _on_folder_toggled(self, folder_key: str, is_expanded: bool) -> None:
        self._request_profile_folder_action(
            "set_collapsed",
            folder_key=folder_key,
            collapsed=not bool(is_expanded),
            refresh=False,
        )

    def _on_folders_toggled(self, expanded_by_key: object, _expanded: bool) -> None:
        collapsed_by_key = {
            str(folder_key or "").strip(): not bool(is_expanded)
            for folder_key, is_expanded in dict(expanded_by_key or {}).items()
            if str(folder_key or "").strip()
        }
        if not collapsed_by_key:
            return
        self._request_profile_folder_action(
            "set_collapsed_many",
            collapsed_by_key=collapsed_by_key,
            refresh=False,
        )

    def _create_profile_folder_action_worker(
        self,
        request_id: int,
        *,
        action: str,
        folder_key: str = "",
        name: str = "",
        direction: int = 0,
        collapsed: bool = False,
        collapsed_by_key: dict[str, bool] | None = None,
        context_extra: dict | None = None,
    ):
        return self._create_profile_folder_action_worker_fn(
            request_id,
            action=action,
            folder_key=folder_key,
            name=name,
            direction=direction,
            collapsed=collapsed,
            collapsed_by_key=collapsed_by_key,
            context_extra=context_extra,
            parent=self,
        )

    def _request_profile_folder_action(
        self,
        action: str,
        *,
        folder_key: str = "",
        name: str = "",
        direction: int = 0,
        collapsed: bool = False,
        collapsed_by_key: dict[str, bool] | None = None,
        refresh: bool = True,
        context_extra: dict | None = None,
    ) -> None:
        runtime = self._worker_runtime("_profile_folder_action_runtime")
        payload = {
            "action": str(action or ""),
            "folder_key": str(folder_key or ""),
            "name": str(name or ""),
            "direction": int(direction or 0),
            "collapsed": bool(collapsed),
            "refresh": bool(refresh),
            "context_extra": dict(context_extra or {}),
        }
        collapsed_map = {
            str(key or "").strip(): bool(value)
            for key, value in dict(collapsed_by_key or {}).items()
            if str(key or "").strip()
        }
        if collapsed_map:
            payload["collapsed_by_key"] = collapsed_map
        if self._profile_folder_action_state_obj().is_busy():
            self._queue_profile_folder_action(payload)
            return
        self._profile_folder_action_request_id = int(
            self.__dict__.get("_profile_folder_action_request_id", 0) or 0
        ) + 1
        request_id = self._profile_folder_action_request_id
        self.__dict__.setdefault("_profile_folder_action_refresh_by_request", {})[request_id] = bool(refresh)

        def _bind_worker(worker) -> None:
            worker.completed.connect(self._on_profile_folder_action_finished)
            worker.failed.connect(self._on_profile_folder_action_failed)

        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self._create_profile_folder_action_worker(
                request_id,
                action=str(action or ""),
                folder_key=str(folder_key or ""),
                name=str(name or ""),
                direction=int(direction or 0),
                collapsed=bool(collapsed),
                collapsed_by_key={
                    str(key or "").strip(): bool(value)
                    for key, value in dict(collapsed_by_key or {}).items()
                    if str(key or "").strip()
                },
                context_extra=dict(context_extra or {}),
            ),
            bind_worker=_bind_worker,
            on_finished=self._on_profile_folder_action_worker_finished,
        )

    def _queue_profile_folder_action(self, payload: dict[str, object]) -> None:
        queued = dict(payload or {})
        action = str(queued.get("action") or "")
        folder_key = str(queued.get("folder_key") or "")
        pending = self._profile_folder_action_state_obj().pending
        if action == "move" and queued in pending:
            return
        if action == "set_collapsed" and folder_key:
            pending[:] = [
                item
                for item in pending
                if not (
                    str(item.get("action") or "") == "set_collapsed"
                    and str(item.get("folder_key") or "") == folder_key
                )
            ]
        if action == "set_collapsed_many":
            collapsed_by_key = dict(queued.get("collapsed_by_key") or {})
            changed_keys = {
                str(key or "").strip()
                for key in collapsed_by_key.keys()
                if str(key or "").strip()
            }
            pending[:] = [
                item
                for item in pending
                if not (
                    str(item.get("action") or "") == "set_collapsed_many"
                    or (
                        str(item.get("action") or "") == "set_collapsed"
                        and str(item.get("folder_key") or "") in changed_keys
                    )
                )
            ]
        pending.append(queued)

    def _on_profile_folder_action_finished(self, request_id: int, action: str, result, context) -> None:
        if request_id != int(getattr(self, "_profile_folder_action_request_id", 0) or 0):
            return
        if self._profile_folder_action_state_obj().has_pending():
            self.__dict__.setdefault("_profile_folder_action_refresh_by_request", {}).pop(request_id, None)
            return
        context = dict(context or {})
        folder_state = result if isinstance(result, dict) else context.get("folder_state")
        should_refresh = bool(
            self.__dict__.setdefault("_profile_folder_action_refresh_by_request", {}).pop(request_id, True)
        )
        if str(action or "") == "load_state" and bool(context.get("show_menu")):
            self._show_folder_menu_with_state(
                str(context.get("folder_key") or ""),
                context.get("global_pos"),
                result if isinstance(result, dict) else {},
            )
            return
        if bool(result) and should_refresh:
            if isinstance(folder_state, dict) and self._apply_profile_folder_state_locally(folder_state):
                return
            self.refresh_from_preset_switch()

    def _apply_profile_folder_state_locally(self, folder_state: dict) -> bool:
        profiles_list = self.__dict__.get("_profiles_list")
        if profiles_list is None:
            return False
        apply_state = getattr(profiles_list, "apply_profile_folder_state", None)
        if apply_state is None:
            return False
        if not apply_state(folder_state):
            return False
        self._profile_payload_dirty = True
        return True

    def _on_profile_folder_action_failed(self, request_id: int, action: str, error: str, _context) -> None:
        if request_id != int(getattr(self, "_profile_folder_action_request_id", 0) or 0):
            return
        if self._profile_folder_action_state_obj().has_pending():
            self.__dict__.setdefault("_profile_folder_action_refresh_by_request", {}).pop(request_id, None)
            return
        self.__dict__.setdefault("_profile_folder_action_refresh_by_request", {}).pop(request_id, None)
        log(f"{self.__class__.__name__}: не удалось выполнить действие папки profile ({action}): {error}", "ERROR")

    def _on_profile_folder_action_worker_finished(self, worker) -> None:
        if not self._accept_current_preset_setup_worker_finished("_profile_folder_action_request_id", worker):
            return
        if not self.__dict__.get("_cleanup_in_progress", False):
            pending = self._profile_folder_action_state_obj().pop_next()
        else:
            pending = None
        if pending:
            self._schedule_profile_folder_action_start(pending)

    def _schedule_profile_folder_action_start(self, pending: dict[str, object]) -> None:
        queued = dict(pending or {})
        state = self._profile_folder_action_state_obj()

        def _single_shot(delay: int, callback) -> None:
            try:
                QTimer.singleShot(delay, callback)
            except Exception:
                callback()

        state.schedule_start(
            queued,
            _single_shot,
            self._run_scheduled_profile_folder_action_start,
            queue_item=self._queue_profile_folder_action,
            is_cleanup_in_progress=lambda: bool(self.__dict__.get("_cleanup_in_progress", False)),
        )

    def _run_scheduled_profile_folder_action_start(self, pending: dict[str, object]) -> None:
        self._profile_folder_action_state_obj().start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._request_profile_folder_action(
            str(pending.get("action") or ""),
            folder_key=str(pending.get("folder_key") or ""),
            name=str(pending.get("name") or ""),
            direction=int(pending.get("direction") or 0),
            collapsed=bool(pending.get("collapsed")),
            collapsed_by_key=(
                dict(pending.get("collapsed_by_key") or {})
                if "collapsed_by_key" in pending
                else None
            ),
            refresh=bool(pending.get("refresh", True)),
            context_extra=dict(pending.get("context_extra") or {}),
        )

    def _profile_folder_action_state_obj(self) -> QueuedWorkerState[dict[str, object]]:
        state = self.__dict__.get("_profile_folder_action_state")
        runtime = self.__dict__.get("_profile_folder_action_runtime")
        if state is None:
            pending = list(self.__dict__.pop("_profile_folder_action_pending", []) or [])
            start_scheduled = bool(self.__dict__.pop("_profile_folder_action_start_scheduled", False))
            state = QueuedWorkerState(
                runtime,
                pending=pending,
                start_scheduled=start_scheduled,
            )
            self.__dict__["_profile_folder_action_state"] = state
        elif getattr(state, "runtime", None) is None and runtime is not None:
            state.runtime = runtime
        return state

    @property
    def _profile_folder_action_pending(self) -> list[dict[str, object]]:
        return self._profile_folder_action_state_obj().pending

    @_profile_folder_action_pending.setter
    def _profile_folder_action_pending(self, value: list[dict[str, object]]) -> None:
        self._profile_folder_action_state_obj().pending = list(value or [])

    @property
    def _profile_folder_action_start_scheduled(self) -> bool:
        return bool(self._profile_folder_action_state_obj().start_scheduled)

    @_profile_folder_action_start_scheduled.setter
    def _profile_folder_action_start_scheduled(self, value: bool) -> None:
        self._profile_folder_action_state_obj().start_scheduled = bool(value)

    def apply_profile_setup_change(self, profile_key: str, change_kind: str, profile_item=None) -> None:
        clean_profile_key = str(profile_key or "").strip()
        kind = str(change_kind or "").strip()
        if profile_item is not None and clean_profile_key:
            if self._replace_profile_item_locally(clean_profile_key, profile_item):
                return
        if (
            kind in {"strategy", "feedback", "settings", "raw_profile", "list_file", "user_profile_updated"}
            and clean_profile_key
        ):
            self._refresh_profile_item_locally(profile_key, profile_key)
            return
        if kind == "user_profile_deleted" and clean_profile_key:
            self._remove_profile_item_locally(clean_profile_key)
            return
        if kind in {"enabled", "disabled"} and clean_profile_key:
            if self._apply_profile_enabled_locally(clean_profile_key, kind == "enabled"):
                self._profile_payload_dirty = True
                return
        self.refresh_from_preset_switch()

    def handle_page_command(self, command: str, payload: dict) -> bool:
        if command == "profile_setup_changed":
            self.apply_profile_setup_change(
                str((payload or {}).get("profile_key") or ""),
                str((payload or {}).get("change_kind") or ""),
                (payload or {}).get("profile_item"),
            )
            return True
        return False

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        unsubscribe = self._ui_state_unsubscribe
        if callable(unsubscribe):
            try:
                unsubscribe()
            except Exception:
                pass
        self._ui_state_unsubscribe = None
        self._ui_state_store = None
        self._profile_preset_write_state_obj().reset()
        self._pending_profile_payload_apply = None
        self._profile_payload_apply_scheduled = False
        self._profiles_list_show_scheduled = False
        self._profile_load_refresh_state_obj().reset()
        self._profile_folder_action_state_obj().reset()
        self.__dict__.setdefault("_profile_folder_action_refresh_by_request", {}).clear()
        self.__dict__.setdefault("_profile_context_action_enabled_by_request", {}).clear()
        for attr, label in (
            ("_profile_load_runtime", "profile list load worker"),
            ("_profile_item_refresh_runtime", "profile item refresh worker"),
            ("_profile_context_action_runtime", "profile context action worker"),
            ("_profile_move_runtime", "profile move worker"),
            ("_profile_folder_action_runtime", "profile folder action worker"),
            ("_user_profile_create_runtime", "user profile create worker"),
            ("_user_profile_update_runtime", "user profile update worker"),
            ("_user_profile_delete_runtime", "user profile delete worker"),
        ):
            runtime = self.__dict__.get(attr)
            if runtime is None:
                continue
            runtime.stop(
                blocking=False,
                log_fn=log,
                warning_prefix=label,
            )
            runtime.cancel()
        self._profile_load_runtime_request_id = 0
        for attr in (
            "_profile_item_refresh_request_id",
            "_profile_context_action_request_id",
            "_profile_move_request_id",
            "_profile_folder_action_request_id",
            "_user_profile_create_request_id",
            "_user_profile_update_request_id",
            "_user_profile_delete_request_id",
        ):
            setattr(self, attr, int(getattr(self, attr, 0) or 0) + 1)

    def _expand_all(self) -> None:
        if self._profiles_list is not None:
            self._profiles_list.expand_all()

    def _collapse_all(self) -> None:
        if self._profiles_list is not None:
            self._profiles_list.collapse_all()

    def _open_profile_order(self) -> None:
        self._open_profile_order_page()

    def _show_profile_info(self) -> None:
        box = MessageBox(
            "Настройка пресета",
            "На этой странице показаны профили выбранного пресета. "
            "Если профиля ещё нет в пресете, включите его или выберите для него готовую стратегию. "
            "Если профиль выключить, программа добавит --skip, чтобы движок его пропустил.",
            self,
        )
        set_message_box_button_accessibility(
            box,
            yes_name="Закрыть справку о настройке пресета",
            yes_description="Закрывает справку о профилях выбранного пресета.",
            cancel_name="Отменить закрытие справки о настройке пресета",
            cancel_description="Скрытая кнопка отмены в справочном окне.",
        )
        box.exec()

    def _on_add_user_profile_clicked(self) -> None:
        dialog = CreateUserProfileDialog(self)
        if not dialog.exec():
            return
        name, protocol, ports = dialog.values()
        self._request_user_profile_create(name=name, protocol=protocol, ports=ports)


class Zapret2PresetSetupPage(PresetSetupPageBase):
    launch_method = ZAPRET2_MODE
    engine_label = "Zapret 2"
    page_title = "Настройка пресета"
    title_key = "page.winws2_pages.title"
    control_key = "page.winws2_pages.back.control"
    toolbar_title_key = "page.winws2_pages.toolbar.title"
    request_button_key = "page.winws2_pages.request.button"
    request_hint_key = "page.winws2_pages.request.hint"
    loading_key = "page.winws2_pages.loading"


class Zapret1PresetSetupPage(PresetSetupPageBase):
    launch_method = ZAPRET1_MODE
    engine_label = "Zapret 1"
    page_title = "Настройка пресета"
    title_key = "page.winws1_pages.title"
    control_key = "page.winws1_pages.back.control"
    toolbar_title_key = "page.winws1_pages.toolbar.title"
    request_button_key = "page.winws1_pages.request.button"
    request_hint_key = "page.winws1_pages.request.hint"
    loading_key = "page.winws1_pages.loading"


def _protocol_and_ports_from_match_lines(match_lines: tuple[str, ...]) -> tuple[str, str]:
    for protocol, option_name in (("tcp", "--filter-tcp"), ("udp", "--filter-udp"), ("l7", "--filter-l7")):
        values = filter_values(match_lines, option_name)
        if values:
            return protocol, values[0]
    return "tcp", ""


def _user_profile_id_from_item(profile_key: str, item) -> str:
    profile_id = str(getattr(item, "user_profile_id", "") or "").strip()
    if profile_id:
        return profile_id
    key = str(profile_key or "").strip()
    if key.startswith("template:user:"):
        return key.split("template:user:", 1)[1].strip()
    return ""


def _profile_context_action_result_key(result) -> str:
    if isinstance(result, dict):
        return str(result.get("profile_key") or "").strip()
    return str(result or "").strip()


def _profile_context_action_result_item(result):
    if isinstance(result, dict):
        return result.get("profile_item")
    return None
