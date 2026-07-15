from __future__ import annotations

import time

from PyQt6.QtCore import QTimer, QUrl
from PyQt6.QtGui import QDesktopServices

from log.log import log
from profile.match_filters import filter_values
from profile.key_resolution import profile_reference_key
from profile.list_apply_signature import profile_payload_apply_signature
from profile.ui.profile_context_menu import ProfileContextMenuActions, show_profile_context_menu
from profile.ui.profile_folder_menu import show_profile_folder_menu
from profile.ui.profile_list_filter_state import ProfileListFilterState
from profile.ui.profile_payload_controller import (
    ProfilePayloadController,
    ProfilePayloadLoadState,
)
from profile.ui.preset_write_queue import PresetWriteQueue
from profile.ui.profile_folder_controller import ProfileFolderController
from profile.ui.profiles_list import ProfilesList
from profile.ui.shell import build_profile_shell, wire_profile_search_keyboard_activation
from profile.ui.user_profile_dialog import CreateUserProfileDialog
from qfluentwidgets import BodyLabel, InfoBar, MessageBox, PushButton
from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE
from ui.pages.base_page import BasePage
from app.ui_texts import tr as tr_catalog
from config.urls import PROFILE_INFO_URL
from ui.accessibility import set_control_accessibility, set_state_text
from ui.latest_value_worker_state import LatestValueWorkerState
from ui.message_box_accessibility import set_message_box_button_accessibility
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from ui.performance_metrics import log_ui_timing_since
from ui.queued_worker_state import QueuedWorkerState


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


def _bool_cast(value) -> bool:
    return bool(value)


def _request_id_cast(value) -> int:
    return int(value or 0)


def _payload_state_property(field: str, cast=None):
    """Test-facing thin-property страницы поверх `ProfilePayloadLoadState`:
    канон состояния один, тестозависимые имена страницы сохранены."""

    def _get(self):
        value = getattr(self._profile_load_state_obj(), field)
        return cast(value) if cast is not None else value

    def _set(self, value) -> None:
        setattr(self._profile_load_state_obj(), field, cast(value) if cast is not None else value)

    return property(_get, _set)


def _worker_state_property(state_obj_attr: str, field: str, *, get_cast=None, set_cast=None):
    """Test-facing thin-property страницы поверх QueuedWorkerState /
    LatestValueWorkerState; аксессор состояния берётся по имени метода
    страницы, поэтому instance-подмены аксессора в тестах сохраняются."""

    def _get(self):
        value = getattr(getattr(self, state_obj_attr)(), field)
        return get_cast(value) if get_cast is not None else value

    def _set(self, value) -> None:
        setattr(getattr(self, state_obj_attr)(), field, set_cast(value) if set_cast is not None else value)

    return property(_get, _set)


def _pending_kind_property(kind: str, from_operation, to_operation):
    """Test-facing проекция гетерогенной очереди записи пресета на операции
    одного kind (context/move/user_profile); конвертеры — из PresetWriteQueue."""

    def _get(self):
        operations = []
        for operation in self._profile_preset_write_state_obj().pending:
            converted = from_operation(operation)
            if converted is not None:
                operations.append(converted)
        return operations

    def _set(self, value) -> None:
        state = self._profile_preset_write_state_obj()
        state.pending[:] = [
            operation
            for operation in state.pending
            if str(operation.get("kind") or "") != kind
        ]
        state.pending.extend(to_operation(operation) for operation in list(value or []))

    return property(_get, _set)


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
        create_profile_request_form_open_worker,
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
        self._create_profile_request_form_open_worker_fn = create_profile_request_form_open_worker
        self._open_profile_setup = open_profile_setup
        self._open_profile_order_page = open_profile_order

        self._profiles_list: ProfilesList | None = None
        self._empty_state_label = None
        self._content_host_layout = None
        self._view_menu_btn = None
        self._request_btn = None
        self._info_btn = None
        self._add_profile_btn = None
        self._profile_search_input = None
        # Канон фильтров (намерение пользователя): страница создаёт объект и
        # передаёт его виджету списка — копий фильтров ни у кого больше нет.
        self._profile_filters = ProfileListFilterState()
        self._toolbar_actions_bar = None
        self._profile_load_state = ProfilePayloadLoadState()
        self._profile_load_runtime = OneShotWorkerRuntime()
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
        self._profile_request_form_open_runtime = OneShotWorkerRuntime()
        self._profile_request_form_open_state = QueuedWorkerState[str](
            self._profile_request_form_open_runtime,
        )
        self._profile_folder_action_refresh_by_request: dict[int, bool] = {}
        self._user_profile_create_request_id = 0
        self._user_profile_create_runtime = OneShotWorkerRuntime()
        self._user_profile_update_request_id = 0
        self._user_profile_update_runtime = OneShotWorkerRuntime()
        self._user_profile_delete_request_id = 0
        self._user_profile_delete_runtime = OneShotWorkerRuntime()
        self._profile_load_refresh_state = LatestValueWorkerState(self._profile_load_runtime, empty_value=False)
        self._profile_payload_controller = ProfilePayloadController(self)
        self._preset_write_queue = PresetWriteQueue(self)
        self._profile_folder_controller = ProfileFolderController(self)
        self._profile_context_action_enabled_by_request: dict[int, bool] = {}
        self._cleanup_in_progress = False
        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._build_content()
        self.bind_ui_state_store(ui_state_store)

    def on_page_activated(self) -> None:
        has_deferred_payload = self._deferred_profile_payload_apply is not None
        if self._apply_deferred_profile_payload_after_show():
            self._schedule_profiles_list_show_after_page_switch()
            return
        if has_deferred_payload and self._profile_payload_refresh_is_blocked():
            return
        if self._profile_payload_loaded_once and not self._profile_payload_dirty:
            self._mark_profiles_list_ready_after_page_switch()
            return
        self._schedule_profiles_payload_request()

    def warmup_initial_load(self) -> bool:
        if self._is_cleanup_in_progress():
            return False
        if self._deferred_profile_payload_apply is not None:
            return False
        if self._profile_payload_loaded_once and not self._profile_payload_dirty:
            return False
        if self._profile_load_refresh_state_obj().is_busy():
            return False
        self._request_profiles_payload()
        return True

    def _auto_mark_content_ready_after_activation(self) -> bool:
        return False

    def on_page_hidden(self) -> None:
        self._hide_profiles_list_for_next_switch()

    def _hide_profiles_list_for_next_switch(self) -> None:
        self._profiles_list_show_scheduled = False

    def _schedule_profiles_list_show_after_page_switch(self) -> None:
        if self._is_cleanup_in_progress():
            return
        if self._profiles_list_widget() is None:
            return
        if self._profiles_list_show_scheduled:
            return
        self._profiles_list_show_scheduled = True
        try:
            QTimer.singleShot(0, self._show_profiles_list_after_page_switch)
        except Exception:
            self._show_profiles_list_after_page_switch()

    def _show_profiles_list_after_page_switch(self) -> None:
        if not self._profiles_list_show_scheduled:
            return
        self._profiles_list_show_scheduled = False
        self._mark_profiles_list_ready_after_page_switch()

    def _mark_profiles_list_ready_after_page_switch(self) -> None:
        if self._is_cleanup_in_progress():
            return
        profile_list = self._profiles_list_widget()
        if profile_list is None:
            return
        self._mark_content_ready_safely(stage="content.profiles_list.visible", extra="list=visible")
        self._mark_content_paint_ready_safely(
            profile_list,
            stage="content.profiles_list.painted",
            extra="list=painted",
        )

    def _mark_content_ready_safely(self, *, stage: str, extra: str = "") -> None:
        marker = getattr(self, "mark_content_ready", None)
        if not callable(marker):
            return
        try:
            marker(stage=stage, extra=extra)
        except Exception:
            pass

    def _mark_content_paint_ready_safely(self, target, *, stage: str, extra: str = "") -> None:
        marker = getattr(self, "mark_content_ready_after_next_paint", None)
        if not callable(marker):
            return
        try:
            marker(target, stage=stage, extra=extra)
        except Exception:
            pass

    def _profile_filter_state(self) -> ProfileListFilterState:
        """Канон фильтров; лениво создаётся для duck-typed стабов из тестов."""
        filters = self.__dict__.get("_profile_filters")
        if filters is None:
            filters = ProfileListFilterState()
            self._profile_filters = filters
        return filters

    @property
    def _profile_search_query(self) -> str:
        """Тонкий test-facing доступ к канону фильтров."""
        return str(self._profile_filter_state().search_query or "")

    @_profile_search_query.setter
    def _profile_search_query(self, value: str) -> None:
        self._profile_filter_state().search_query = str(value or "")

    @property
    def _profile_show_only_added(self) -> bool:
        """Тонкий test-facing доступ к канону фильтров."""
        return bool(self._profile_filter_state().show_only_added)

    @_profile_show_only_added.setter
    def _profile_show_only_added(self, value: bool) -> None:
        self._profile_filter_state().show_only_added = bool(value)

    def _is_cleanup_in_progress(self) -> bool:
        """Cleanup-флаг; чтение устойчиво к duck-typed стабам из тестов."""
        return bool(self.__dict__.get("_cleanup_in_progress", False))

    def _profiles_list_widget(self) -> ProfilesList | None:
        """Виджет списка; чтение устойчиво к duck-typed стабам из тестов."""
        return self.__dict__.get("_profiles_list")

    def _profile_load_state_obj(self) -> ProfilePayloadLoadState:
        """Состояние payload-машины; лениво создаётся для стабов из тестов."""
        state = self.__dict__.get("_profile_load_state")
        if state is None:
            state = ProfilePayloadLoadState()
            self.__dict__["_profile_load_state"] = state
        return state

    # --- thin-property имена payload-машины (test-facing) поверх
    # --- ProfilePayloadLoadState: канон состояния один, имена сохранены.

    _profile_load_request_id = _payload_state_property("request_id", _request_id_cast)
    _profile_load_runtime_request_id = _payload_state_property("runtime_request_id", _request_id_cast)
    _profile_payload_loaded_once = _payload_state_property("loaded_once", _bool_cast)
    _profile_payload_dirty = _payload_state_property("dirty", _bool_cast)
    _profile_payload_load_failed = _payload_state_property("load_failed", _bool_cast)
    _profile_payload_request_scheduled = _payload_state_property("request_scheduled", _bool_cast)
    _profile_payload_request_force = _payload_state_property("request_force", _bool_cast)
    _profile_payload_reload_after_preset_switch_scheduled = _payload_state_property(
        "reload_after_preset_switch_scheduled", _bool_cast
    )
    _profile_payload_apply_scheduled = _payload_state_property("apply_scheduled", _bool_cast)
    _pending_profile_payload_apply = _payload_state_property("pending_apply")
    _deferred_profile_payload_apply = _payload_state_property("deferred_apply")
    _profiles_list_show_scheduled = _payload_state_property("show_scheduled", _bool_cast)
    _last_profile_payload_apply_signature = _payload_state_property("last_apply_signature")

    def _profile_context_action_enabled_map(self) -> dict[int, bool]:
        """Карта requested-enabled по request_id; setdefault — для стабов."""
        return self.__dict__.setdefault("_profile_context_action_enabled_by_request", {})

    def _profile_folder_action_refresh_map(self) -> dict[int, bool]:
        """Карта refresh-флагов по request_id; setdefault — для стабов."""
        return self.__dict__.setdefault("_profile_folder_action_refresh_by_request", {})

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

    # --- payload-машина: тонкие делегаты в ProfilePayloadController ---

    def _payload_controller_obj(self) -> ProfilePayloadController:
        """Контроллер payload-машины; лениво создаётся для стабов из тестов."""
        controller = self.__dict__.get("_profile_payload_controller")
        if controller is None:
            controller = ProfilePayloadController(self)
            self.__dict__["_profile_payload_controller"] = controller
        return controller

    def _schedule_profiles_payload_request(self, *, force: bool = False) -> None:
        self._payload_controller_obj()._schedule_profiles_payload_request(force=force)

    def _run_scheduled_profiles_payload_request(self) -> None:
        self._payload_controller_obj()._run_scheduled_profiles_payload_request()

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
            on_open_profile_request_form=self._open_profile_request_form,
            on_add_user_profile=self._on_add_user_profile_clicked,
            on_expand_all=self._expand_all,
            on_collapse_all=self._collapse_all,
            on_show_added_only=self._show_added_profiles_only,
            on_show_all_profiles=self._show_all_profiles,
            on_open_profile_order=self._open_profile_order,
            on_show_info_popup=self._show_profile_info,
            on_profile_search_text_changed=self._on_profile_search_text_changed,
        )
        self._toolbar_actions_bar = shell.toolbar_actions_bar
        self._add_profile_btn = shell.add_profile_btn
        self._request_btn = shell.request_btn
        self._view_menu_btn = shell.view_menu_btn
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
        self._deferred_profile_payload_apply = None
        self._schedule_profiles_payload_request(force=True)

    def _fallback_full_reload(self) -> None:
        """Единый fallback точечных мутаций: локальное применение не удалось
        (или недоступно) — полная перезагрузка payload, как при смене preset."""
        self.refresh_from_preset_switch()

    def _schedule_profiles_payload_reload_after_preset_switch(self) -> None:
        self._payload_controller_obj()._schedule_profiles_payload_reload_after_preset_switch()

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
        if "preset_content_revision" in changed:
            change_kind = str(getattr(_state, "preset_content_change_kind", "") or "").strip()
            if change_kind == "strategy_only":
                return
            self._deferred_profile_payload_apply = None
            self._profile_payload_dirty = True
            self._schedule_profiles_payload_request(force=True)
            return
        if self._activation_targets_displayed_preset(_state):
            return
        self._deferred_profile_payload_apply = None
        self._profile_payload_dirty = True
        self._schedule_profiles_payload_reload_after_preset_switch()

    def _activation_targets_displayed_preset(self, state) -> bool:
        """Активация уже отображаемого пресета не требует перегрузки списка."""
        active_file_name = str(getattr(state, "active_preset_file_name", "") or "").strip().lower()
        displayed = str(self.__dict__.get("_displayed_preset_file_name", "") or "").strip().lower()
        if not active_file_name or not displayed:
            return False
        return active_file_name == displayed

    def _request_profiles_payload(self, *, force: bool = False) -> None:
        self._payload_controller_obj()._request_profiles_payload(force=force)

    def _on_profile_payload_loaded(self, request_id: int, payload) -> None:
        self._payload_controller_obj()._on_profile_payload_loaded(request_id, payload)

    def _schedule_profile_payload_apply(self, payload, *, view_state=None, apply_signature_base=None) -> None:
        self._payload_controller_obj()._schedule_profile_payload_apply(
            payload, view_state=view_state, apply_signature_base=apply_signature_base
        )

    def _run_scheduled_profile_payload_apply(self) -> None:
        self._payload_controller_obj()._run_scheduled_profile_payload_apply()

    def _apply_deferred_profile_payload_after_show(self) -> bool:
        return self._payload_controller_obj()._apply_deferred_profile_payload_after_show()

    def _profile_payload_refresh_is_blocked(self) -> bool:
        return self._payload_controller_obj()._profile_payload_refresh_is_blocked()

    def _on_profile_payload_failed(self, request_id: int, error: str) -> None:
        self._payload_controller_obj()._on_profile_payload_failed(request_id, error)

    def _on_profile_worker_finished(self, worker) -> None:
        self._payload_controller_obj()._on_profile_worker_finished(worker)

    def _apply_payload(self, payload, *, view_state=None, apply_signature_base=None) -> None:
        if self._content_host_layout is None:
            return
        total_started_at = time.perf_counter()
        apply_signature = profile_payload_apply_signature(
            payload,
            view_state=view_state,
            search_query=self._profile_search_query,
            apply_signature_base=apply_signature_base,
        )
        if (
            self._profiles_list_widget() is not None
            and self._last_profile_payload_apply_signature == apply_signature
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
        # Намерение страницы фиксируем до применения снимка: apply_view_state
        # синхронизирует канон фильтров с применённым view_state, а страница
        # затем возвращает актуальный запрос/фильтр, если они разошлись.
        search_query = self._profile_search_query
        show_only_added = self._profile_show_only_added
        profiles_list = self._profiles_list
        if profiles_list is not None:
            started_at = time.perf_counter()
            if view_state is not None:
                profiles_list.apply_view_state(view_state)
                profiles_list.set_search_query(search_query)
                self._apply_profile_visibility_filter(profiles_list, show_only_added=show_only_added)
            else:
                profiles_list.update_profiles(tuple(payload.items))
                profiles_list.set_search_query(search_query)
                self._apply_profile_visibility_filter(profiles_list, show_only_added=show_only_added)
            self._log_ui_timing("profile_ui.profile_list.update", started_at, extra=f"{len(payload.items)} items")
            self._log_ui_timing("profile_ui.apply_payload.total", total_started_at)
            return

        self._clear_dynamic_widgets()
        create_started_at = time.perf_counter()
        profiles_list = ProfilesList(self, filter_state=self._profile_filter_state())
        profiles_list.profile_selected.connect(self._on_profile_clicked)
        profiles_list.profile_context_requested.connect(self._on_profile_context_requested)
        profiles_list.profile_move_requested.connect(self._on_profile_move_requested)
        profiles_list.profile_move_after_requested.connect(self._on_profile_move_after_requested)
        profiles_list.profile_move_to_folder_requested.connect(self._on_profile_move_to_folder_requested)
        profiles_list.profile_move_to_end_requested.connect(self._on_profile_move_to_end_requested)
        profiles_list.folder_context_requested.connect(self._on_folder_context_requested)
        profiles_list.folder_toggled.connect(self._on_folder_toggled)
        profiles_list.folders_toggled.connect(self._on_folders_toggled)
        wire_profile_search_keyboard_activation(self._profile_search_input, profiles_list)
        self._log_ui_timing("profile_ui.profile_list.create", create_started_at)

        started_at = time.perf_counter()
        if view_state is not None:
            profiles_list.apply_view_state(view_state)
            profiles_list.set_search_query(search_query)
            self._apply_profile_visibility_filter(profiles_list, show_only_added=show_only_added)
        else:
            profiles_list.build_profiles(tuple(payload.items or ()))
            profiles_list.set_search_query(search_query)
            self._apply_profile_visibility_filter(profiles_list, show_only_added=show_only_added)
        self._log_ui_timing("profile_ui.profile_list.build", started_at, extra=f"{len(payload.items)} items")

        attach_started_at = time.perf_counter()
        self._profiles_list = profiles_list
        self._content_host_layout.addWidget(profiles_list, 1)
        self._empty_state_label = None
        self._log_ui_timing("profile_ui.profile_list.attach", attach_started_at)
        self._log_ui_timing("profile_ui.apply_payload.total", total_started_at)

    def _on_profile_search_text_changed(self, text: str) -> None:
        query = str(text or "")
        self._profile_filter_state().search_query = query
        if self._profiles_list is not None:
            self._profiles_list.set_search_query(query)

    def _apply_profile_visibility_filter(self, profiles_list=None, *, show_only_added: bool | None = None) -> None:
        target = profiles_list if profiles_list is not None else self._profiles_list_widget()
        setter = getattr(target, "set_show_only_added", None)
        if callable(setter):
            value = self._profile_show_only_added if show_only_added is None else bool(show_only_added)
            setter(bool(value))

    def _show_added_profiles_only(self) -> None:
        self._profile_filter_state().show_only_added = True
        self._apply_profile_visibility_filter()

    def _show_all_profiles(self) -> None:
        self._profile_filter_state().show_only_added = False
        self._apply_profile_visibility_filter()

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
        log_ui_timing_since(
            "ui",
            self.__class__.__name__,
            label,
            started_at,
            extra=extra,
            important=label in {"profile_ui.apply_payload.total", "profile_ui.profile_list.build"},
        )

    def _show_profile_normalization_info(self, payload) -> None:
        split_count = int(getattr(payload, "normalized_split_profiles", 0) or 0)
        created_count = int(getattr(payload, "normalized_created_profiles", 0) or 0)
        if split_count <= 0 or created_count <= 0:
            return
        is_visible = getattr(self, "isVisible", None)
        if callable(is_visible):
            try:
                if not bool(is_visible()):
                    return
            except RuntimeError:
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
        self._displayed_preset_file_name = str(
            getattr(payload, "selected_preset_file_name", "") or ""
        ).strip()
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
        self._mark_content_ready_safely(stage="content.empty_state.visible", extra="empty_state=visible")

    def _on_profile_clicked(self, profile_key: str) -> None:
        self._open_profile_setup_by_reference(profile_key)

    def _profile_reference_for(self, profile_key: str) -> str:
        """Стабильная ссылка вместо позиционного "profile:N": позиционный ключ
        протухает, пока операция ждёт в очереди записи или пока открыт редактор."""
        profiles_list = self._profiles_list_widget()
        item = profiles_list.profile_item_for_key(profile_key) if profiles_list is not None else None
        reference = profile_reference_key(item) if item is not None else ""
        return reference or str(profile_key or "").strip()

    def _open_profile_setup_by_reference(self, profile_key: str) -> None:
        self._open_profile_setup(self._profile_reference_for(profile_key))

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
                open_profile=self._open_profile_setup_by_reference,
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

    # --- очередь записи пресета: тонкие делегаты в PresetWriteQueue ---

    def _write_queue_obj(self) -> PresetWriteQueue:
        """Очередь записи пресета; лениво создаётся для стабов из тестов."""
        queue = self.__dict__.get("_preset_write_queue")
        if queue is None:
            queue = PresetWriteQueue(self)
            self.__dict__["_preset_write_queue"] = queue
        return queue

    def _request_profile_context_action(self, action: str, profile_key: str, *, enabled: bool | None = None) -> None:
        self._write_queue_obj()._request_profile_context_action(action, profile_key, enabled=enabled)

    def _queue_profile_preset_write_operation(self, kind: str, **kwargs) -> None:
        self._write_queue_obj()._queue_profile_preset_write_operation(kind, **kwargs)

    def _has_pending_profile_preset_write_operation(self) -> bool:
        return self._profile_preset_write_state_obj().has_pending()

    def _has_pending_user_profile_operation(self) -> bool:
        return bool(self._pending_user_profile_operations)

    def _user_profile_operation_running(self) -> bool:
        return self._write_queue_obj()._user_profile_operation_running()

    def _schedule_next_profile_preset_write_operation_start(self) -> bool:
        return self._write_queue_obj()._schedule_next_profile_preset_write_operation_start()

    def _profile_load_refresh_state_obj(self) -> LatestValueWorkerState:
        return self._payload_controller_obj()._profile_load_refresh_state_obj()

    _profile_load_refresh_pending = _worker_state_property(
        "_profile_load_refresh_state_obj", "pending", get_cast=_bool_cast, set_cast=_bool_cast
    )
    _profile_load_refresh_start_scheduled = _worker_state_property(
        "_profile_load_refresh_state_obj", "start_scheduled", get_cast=_bool_cast, set_cast=_bool_cast
    )

    def _profile_preset_write_state_obj(self) -> QueuedWorkerState[dict[str, object]]:
        return self._write_queue_obj()._profile_preset_write_state_obj()

    _pending_profile_preset_write_operations = _worker_state_property(
        "_profile_preset_write_state_obj", "pending", set_cast=lambda value: list(value or [])
    )
    _profile_preset_write_operation_start_scheduled = _worker_state_property(
        "_profile_preset_write_state_obj", "start_scheduled", get_cast=_bool_cast, set_cast=_bool_cast
    )
    _pending_user_profile_operations = _pending_kind_property(
        "user_profile",
        PresetWriteQueue._user_profile_operation_from_profile_preset_write_operation,
        PresetWriteQueue._profile_preset_write_operation_from_user_profile_operation,
    )
    _pending_profile_context_actions = _pending_kind_property(
        "context",
        PresetWriteQueue._context_action_from_profile_preset_write_operation,
        PresetWriteQueue._profile_preset_write_operation_from_context_action,
    )
    _pending_profile_moves = _pending_kind_property(
        "move",
        PresetWriteQueue._move_operation_from_profile_preset_write_operation,
        PresetWriteQueue._profile_preset_write_operation_from_move_operation,
    )

    def _on_profile_context_action_finished(self, request_id: int, action: str, profile_key: str, result) -> None:
        self._write_queue_obj()._on_profile_context_action_finished(request_id, action, profile_key, result)

    def _on_profile_context_action_failed(self, request_id: int, error: str) -> None:
        self._write_queue_obj()._on_profile_context_action_failed(request_id, error)

    def _on_profile_context_action_worker_finished(self, worker) -> None:
        self._write_queue_obj()._on_profile_context_action_worker_finished(worker)

    # --- тонкие обёртки над инжектированными фабриками воркеров ---

    def _create_profile_context_action_worker(self, request_id: int, launch_method: str, **kwargs):
        return self._create_profile_context_action_worker_fn(request_id, launch_method, **kwargs)

    def _create_profile_list_load_worker(self, request_id: int, launch_method: str, parent=None, **kwargs):
        return self._create_profile_list_load_worker_fn(request_id, launch_method, parent, **kwargs)

    def _create_profile_item_refresh_worker(self, request_id: int, launch_method: str, **kwargs):
        return self._create_profile_item_refresh_worker_fn(request_id, launch_method, **kwargs)

    def _sync_profile_list_locally(self) -> None:
        self._profile_payload_dirty = True
        self._clear_deferred_profile_payload_apply()
        self._schedule_profiles_payload_request(force=True)

    def _refresh_profile_item_locally(self, old_profile_key: str, profile_key: str) -> None:
        self._payload_controller_obj()._refresh_profile_item_locally(old_profile_key, profile_key)

    def _on_profile_item_refreshed(self, request_id: int, old_profile_key: str, profile_key: str, item) -> None:
        self._payload_controller_obj()._on_profile_item_refreshed(request_id, old_profile_key, profile_key, item)

    def _replace_profile_item_locally(self, old_profile_key: str, item) -> bool:
        profiles_list = self._profiles_list_widget()
        if profiles_list is None:
            return False
        profile_key = str(getattr(item, "key", "") or old_profile_key or "").strip()
        if not profile_key:
            return False
        if not profiles_list.replace_profile_item(old_profile_key, item):
            return False
        self._profile_payload_dirty = True
        self._clear_deferred_profile_payload_apply()
        return True

    def _apply_profile_enabled_locally(self, profile_key: str, enabled: bool) -> bool:
        profiles_list = self._profiles_list_widget()
        if profiles_list is None:
            return False
        if not profiles_list.set_profile_enabled(profile_key, bool(enabled)):
            return False
        self._clear_deferred_profile_payload_apply()
        return True

    def _add_profile_item_locally(self, profile_key: str | None, new_profile_key: str | None = None) -> None:
        source_key = str(profile_key or "").strip()
        duplicate_key = str(new_profile_key or "").strip()
        profiles_list = self._profiles_list_widget()
        if (
            profiles_list is not None
            and source_key
            and duplicate_key
            and profiles_list.duplicate_profile_item(source_key, duplicate_key)
        ):
            self._profile_payload_dirty = True
            self._clear_deferred_profile_payload_apply()
            return
        self._profile_payload_dirty = True
        self._fallback_full_reload()

    def _remove_profile_item_locally(self, profile_key: str) -> None:
        profiles_list = self._profiles_list_widget()
        if profiles_list is not None and profiles_list.remove_profile_item(profile_key):
            self._profile_payload_dirty = True
            self._clear_deferred_profile_payload_apply()
            return
        self._fallback_full_reload()

    def _clear_deferred_profile_payload_apply(self) -> None:
        self._deferred_profile_payload_apply = None

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

    def _create_user_profile_create_worker(self, request_id: int, **kwargs):
        return self._create_user_profile_create_worker_fn(request_id, self.launch_method, parent=self, **kwargs)

    def _create_user_profile_update_worker(self, request_id: int, **kwargs):
        return self._create_user_profile_update_worker_fn(request_id, self.launch_method, parent=self, **kwargs)

    def _create_user_profile_delete_worker(self, request_id: int, **kwargs):
        return self._create_user_profile_delete_worker_fn(request_id, self.launch_method, parent=self, **kwargs)

    def _request_user_profile_create(self, *, name: str, protocol: str, ports: str) -> None:
        self._write_queue_obj()._request_user_profile_create(name=name, protocol=protocol, ports=ports)

    def _on_user_profile_create_finished(self, request_id: int, _profile_id: str, profile_item=None) -> None:
        self._write_queue_obj()._on_user_profile_create_finished(request_id, _profile_id, profile_item)

    def _add_created_user_profile_locally(self, profile_item) -> bool:
        profiles_list = self._profiles_list_widget()
        if profiles_list is None or profile_item is None:
            return False
        if not profiles_list.add_profile_item(profile_item):
            return False
        self._profile_payload_dirty = True
        self._clear_deferred_profile_payload_apply()
        return True

    def _on_user_profile_create_failed(self, request_id: int, error: str) -> None:
        self._write_queue_obj()._on_user_profile_create_failed(request_id, error)

    def _on_user_profile_create_worker_finished(self, worker) -> None:
        self._write_queue_obj()._on_user_profile_create_worker_finished(worker)

    def _request_user_profile_update(self, profile_id: str, *, name: str, protocol: str, ports: str) -> None:
        self._write_queue_obj()._request_user_profile_update(profile_id, name=name, protocol=protocol, ports=ports)

    def _on_user_profile_update_finished(self, request_id: int, profile_id: str, changed: int, profile_items=()) -> None:
        self._write_queue_obj()._on_user_profile_update_finished(request_id, profile_id, changed, profile_items)

    def _replace_user_profile_items_locally(self, profile_id: str, profile_items) -> bool:
        profiles_list = self._profiles_list_widget()
        if profiles_list is None:
            return False
        if not profiles_list.replace_user_profile_items(profile_id, tuple(profile_items or ())):
            return False
        self._profile_payload_dirty = True
        self._clear_deferred_profile_payload_apply()
        return True

    def _on_user_profile_update_failed(self, request_id: int, error: str) -> None:
        self._write_queue_obj()._on_user_profile_update_failed(request_id, error)

    def _on_user_profile_update_worker_finished(self, worker) -> None:
        self._write_queue_obj()._on_user_profile_update_worker_finished(worker)

    def _request_user_profile_delete(self, profile_id: str) -> None:
        self._write_queue_obj()._request_user_profile_delete(profile_id)

    def _on_user_profile_delete_finished(self, request_id: int, _profile_id: str, changed: int) -> None:
        self._write_queue_obj()._on_user_profile_delete_finished(request_id, _profile_id, changed)

    def _remove_user_profile_items_locally(self, profile_id: str) -> bool:
        profiles_list = self._profiles_list_widget()
        if profiles_list is None:
            return False
        if not profiles_list.remove_user_profile_items(profile_id):
            return False
        self._profile_payload_dirty = True
        self._clear_deferred_profile_payload_apply()
        return True

    def _on_user_profile_delete_failed(self, request_id: int, error: str) -> None:
        self._write_queue_obj()._on_user_profile_delete_failed(request_id, error)

    def _on_user_profile_delete_worker_finished(self, worker) -> None:
        self._write_queue_obj()._on_user_profile_delete_worker_finished(worker)

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
        self._write_queue_obj()._request_profile_move(
            action,
            source_profile_key,
            destination_profile_key=destination_profile_key,
            destination_group_key=destination_group_key,
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
        self._write_queue_obj()._on_profile_move_finished(
            request_id,
            action,
            source_profile_key,
            destination_profile_key,
            destination_group_key,
            result,
        )

    def _on_profile_move_failed(self, request_id: int, error: str) -> None:
        self._write_queue_obj()._on_profile_move_failed(request_id, error)

    def _on_profile_move_worker_finished(self, worker) -> None:
        self._write_queue_obj()._on_profile_move_worker_finished(worker)

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
        if not profiles_list.move_profile_item(
            source_profile_key,
            destination_kind,
            destination_profile_key,
            destination_group_key,
        ):
            return False
        self._clear_deferred_profile_payload_apply()
        return True

    def _create_profile_move_worker(self, request_id: int, launch_method: str, **kwargs):
        return self._create_profile_move_worker_fn(request_id, launch_method, parent=self, **kwargs)

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

    def _create_profile_folder_action_worker(self, request_id: int, **kwargs):
        return self._create_profile_folder_action_worker_fn(request_id, parent=self, **kwargs)

    # --- folder actions: тонкие делегаты в ProfileFolderController ---

    def _folder_controller_obj(self) -> ProfileFolderController:
        """Контроллер folder actions; лениво создаётся для стабов из тестов."""
        controller = self.__dict__.get("_profile_folder_controller")
        if controller is None:
            controller = ProfileFolderController(self)
            self.__dict__["_profile_folder_controller"] = controller
        return controller

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
        self._folder_controller_obj()._request_profile_folder_action(
            action,
            folder_key=folder_key,
            name=name,
            direction=direction,
            collapsed=collapsed,
            collapsed_by_key=collapsed_by_key,
            refresh=refresh,
            context_extra=context_extra,
        )

    def _apply_profile_folder_state_locally(self, folder_state: dict) -> bool:
        profiles_list = self._profiles_list_widget()
        if profiles_list is None:
            return False
        apply_state = getattr(profiles_list, "apply_profile_folder_state", None)
        if apply_state is None:
            return False
        if not apply_state(folder_state):
            return False
        self._profile_payload_dirty = True
        self._clear_deferred_profile_payload_apply()
        return True

    def _on_profile_folder_action_failed(self, request_id: int, action: str, error: str, _context) -> None:
        self._folder_controller_obj()._on_profile_folder_action_failed(request_id, action, error, _context)

    def _on_profile_folder_action_worker_finished(self, worker) -> None:
        self._folder_controller_obj()._on_profile_folder_action_worker_finished(worker)

    def _schedule_profile_folder_action_start(self, pending: dict[str, object]) -> None:
        self._folder_controller_obj()._schedule_profile_folder_action_start(pending)

    def _profile_folder_action_state_obj(self) -> QueuedWorkerState[dict[str, object]]:
        return self._folder_controller_obj()._profile_folder_action_state_obj()

    _profile_folder_action_pending = _worker_state_property(
        "_profile_folder_action_state_obj", "pending", set_cast=lambda value: list(value or [])
    )
    _profile_folder_action_start_scheduled = _worker_state_property(
        "_profile_folder_action_state_obj", "start_scheduled", get_cast=_bool_cast, set_cast=_bool_cast
    )

    def apply_profile_setup_change(
        self,
        profile_key: str,
        change_kind: str,
        profile_item=None,
        old_profile_key: str = "",
    ) -> None:
        clean_profile_key = str(profile_key or "").strip()
        kind = str(change_kind or "").strip()
        # Правка имени/match-строк меняет persistent_key: элемент в списке
        # всё ещё живёт под старым ключом, замену ищем по нему.
        old_key = str(old_profile_key or "").strip() or clean_profile_key
        if profile_item is not None and old_key:
            if self._replace_profile_item_locally(old_key, profile_item):
                self._clear_deferred_profile_payload_apply()
                return
        if (
            kind in {"strategy", "feedback", "settings", "raw_profile", "list_file", "user_profile_updated"}
            and clean_profile_key
        ):
            self._refresh_profile_item_locally(old_key, clean_profile_key)
            return
        if kind == "user_profile_deleted" and clean_profile_key:
            self._remove_profile_item_locally(clean_profile_key)
            return
        if kind in {"enabled", "disabled"} and clean_profile_key:
            if self._apply_profile_enabled_locally(clean_profile_key, kind == "enabled"):
                self._profile_payload_dirty = True
                self._clear_deferred_profile_payload_apply()
                return
        self._fallback_full_reload()

    def handle_page_command(self, command: str, payload: dict) -> bool:
        if command == "profile_setup_changed":
            profile_key = str((payload or {}).get("profile_key") or "")
            self.apply_profile_setup_change(
                profile_key,
                str((payload or {}).get("change_kind") or ""),
                (payload or {}).get("profile_item"),
                # Обратная совместимость: payload без old_profile_key ведёт
                # себя как раньше (old == new).
                str((payload or {}).get("old_profile_key") or "") or profile_key,
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
        self._deferred_profile_payload_apply = None
        self._profile_payload_apply_scheduled = False
        self._profiles_list_show_scheduled = False
        self._profile_load_refresh_state_obj().reset()
        self._profile_folder_action_state_obj().reset()
        self._profile_folder_action_refresh_map().clear()
        self._profile_context_action_enabled_map().clear()
        for attr, label in (
            ("_profile_load_runtime", "profile list load worker"),
            ("_profile_item_refresh_runtime", "profile item refresh worker"),
            ("_profile_context_action_runtime", "profile context action worker"),
            ("_profile_move_runtime", "profile move worker"),
            ("_profile_folder_action_runtime", "profile folder action worker"),
            ("_profile_request_form_open_runtime", "profile request form open worker"),
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

    def _create_profile_request_form_open_worker(self, request_id: int, *, url: str, parent=None):
        return self._create_profile_request_form_open_worker_fn(request_id, url=url, parent=parent)

    def _open_profile_request_form(self) -> None:
        from config.urls import PROFILE_REQUEST_FORM_URL

        self._request_profile_request_form_open(PROFILE_REQUEST_FORM_URL)

    def _request_profile_request_form_open(self, url: str) -> None:
        target = str(url or "").strip()
        self._profile_request_form_open_state.start_or_queue(
            target,
            self._start_profile_request_form_open_worker,
            self._queue_profile_request_form_open,
        )

    def _queue_profile_request_form_open(self, url: str) -> bool:
        return self._profile_request_form_open_state.append_unique(str(url or "").strip(), key=lambda item: item)

    def _start_profile_request_form_open_worker(self, url: str) -> None:
        self._profile_request_form_open_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self._create_profile_request_form_open_worker(
                request_id,
                url=url,
                parent=self,
            ),
            on_loaded=self._on_profile_request_form_open_finished,
            on_failed=self._on_profile_request_form_open_failed,
            on_finished=self._on_profile_request_form_open_worker_finished,
        )

    def _on_profile_request_form_open_finished(self, request_id: int, result) -> None:
        if not self._profile_request_form_open_runtime.is_current(
            request_id,
            cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False)),
        ):
            return
        if self._profile_request_form_open_state.has_pending():
            return
        if getattr(result, "ok", False):
            return
        self._show_profile_request_form_open_error(str(getattr(result, "error", "") or ""))

    def _on_profile_request_form_open_failed(self, request_id: int, error: str) -> None:
        if not self._profile_request_form_open_runtime.is_current(
            request_id,
            cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False)),
        ):
            return
        if self._profile_request_form_open_state.has_pending():
            return
        self._show_profile_request_form_open_error(str(error or ""))

    def _on_profile_request_form_open_worker_finished(self, worker) -> None:
        next_url = self._profile_request_form_open_state.pop_next_after_finish(
            worker,
            is_current_worker_finish=lambda runtime, finished_worker: getattr(runtime, "worker", None) is finished_worker,
            cleanup_in_progress=bool(getattr(self, "_cleanup_in_progress", False)),
        )
        if next_url is not None:
            self._schedule_profile_request_form_open_worker_start(next_url)

    def _schedule_profile_request_form_open_worker_start(self, url: str) -> None:
        if self._profile_request_form_open_state.start_scheduled:
            self._queue_profile_request_form_open(url)
            return
        self._profile_request_form_open_state.start_scheduled = True
        try:
            QTimer.singleShot(0, lambda target=url: self._run_scheduled_profile_request_form_open_worker_start(target))
        except Exception:
            self._run_scheduled_profile_request_form_open_worker_start(url)

    def _run_scheduled_profile_request_form_open_worker_start(self, url: str) -> None:
        self._profile_request_form_open_state.start_scheduled = False
        if bool(getattr(self, "_cleanup_in_progress", False)):
            return
        self._start_profile_request_form_open_worker(url)

    def _show_profile_request_form_open_error(self, error: str) -> None:
        InfoBar.warning(
            title="Не удалось открыть GitHub",
            content=f"Не удалось открыть форму GitHub:\n{error}",
            parent=self.window(),
        )

    def _show_profile_info(self) -> None:
        box = MessageBox(
            "Настройка пресета",
            "Это настройки выбранного пресета. Они относятся именно к тому пресету, "
            "который сейчас выбран на странице «Мои пресеты».\n\n"
            "Здесь показаны профили этого пресета: для каких сайтов, приложений, "
            "портов или типов соединений будет применяться обход. Вы можете включить "
            "нужный профиль, выбрать для него готовую стратегию, открыть подробную "
            "настройку профиля, добавить свой профиль, найти профиль в списке и "
            "изменить порядок профилей в пресете.\n\n"
            "Если профиля ещё нет в пресете, включите его или выберите для него "
            "готовую стратегию. Если профиль выключить, программа добавит --skip, "
            "чтобы движок пропустил этот профиль при запуске.",
            self,
        )
        site_button_text = "Открыть сайт с профилями"
        site_button = PushButton(site_button_text)
        site_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(PROFILE_INFO_URL)))
        set_state_text(site_button, site_button_text)
        set_control_accessibility(
            site_button,
            name=site_button_text,
            description="Открывает сайт, где можно посмотреть и скачать профили для пресетов.",
        )
        box.buttonLayout.insertWidget(0, site_button)
        box.cancelButton.hide()
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


