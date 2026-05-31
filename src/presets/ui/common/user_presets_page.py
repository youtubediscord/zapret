"""Общая страница пользовательских preset-ов для Zapret 1 и Zapret 2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from PyQt6.QtCore import (
    Qt,
    QTimer,
    QPoint,
)
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QSizePolicy,
    QWidget,
)
from ui.pages.base_page import BasePage
from presets.ui.common.preset_actions_menu import show_preset_actions_menu
from presets.ui.common.preset_rating_menu import show_preset_rating_menu
from presets.user_presets_runtime_service import (
    UserPresetsRuntimeAdapter,
    UserPresetsRuntimeService,
)
from presets.ui.common.user_presets_page_runtime import (
    UserPresetsPageRuntime,
    UserPresetsPageRuntimeConfig,
    UserPresetsRuntimeActions,
    apply_preset_search,
    apply_presets_rows_plan,
    schedule_preset_search,
    update_presets_view_height,
)
from presets.ui.common.preset_folder_menu import show_preset_folder_menu
from presets.ui.common.user_presets_action_dispatch import (
    UserPresetListActionHandlers,
    dispatch_user_preset_list_action,
)
from presets.ui.common.user_presets_build import build_user_presets_page_shell
from presets.ui.common.preset_status_bar import (
    PresetStatusIcon,
    build_runtime_preset_status_plan,
)
from presets.ui.common.user_presets_actions_workflow import (
    restore_reset_all_button_label,
    show_reset_all_result,
)
from presets.ui.common.user_presets_item_actions_workflow import (
    open_edit_preset_menu_action,
    rename_preset_action,
)
from presets.ui.common.user_presets_page_lifecycle import (
    activate_user_presets_page,
    after_user_presets_ui_built,
    apply_user_presets_language,
    apply_user_presets_page_theme,
    bind_user_presets_ui_state_store,
    cleanup_user_presets_page,
    handle_user_presets_ui_state_changed,
    resync_user_presets_layout_metrics,
    schedule_user_presets_layout_resync,
    set_widget_text_if_changed,
)
from app.state_store import MainWindowStateStore

from qfluentwidgets import (
    FluentIcon, InfoBar,
    LineEdit, MessageBox, PrimaryToolButton,
    RoundMenu, StrongBodyLabel,
)


from ui.theme import get_cached_qta_pixmap, get_theme_tokens
from ui.theme_semantic import get_semantic_palette
from log.log import log


from ui.presets_menu.common import fluent_icon, make_menu_action
from ui.presets_menu.delegate import PresetListDelegate
from ui.presets_menu.model import PresetListModel
from ui.presets_menu.toolbar import PresetsToolbarLayout
from ui.presets_menu.common import tr_text as _tr_text
from ui.one_shot_worker_runtime import OneShotWorkerRuntime


@dataclass(frozen=True, slots=True)
class UserPresetsPageConfig:
    launch_method: str
    folder_scope: str
    tr_prefix: str
    title_key: str
    log_prefix: str
    activate_error_level: str
    activate_error_mode: str
    create_dialog_cls: type
    rename_dialog_cls: type
    reset_all_dialog_cls: type
    delegate_language_scope: str = "winws2"
    delegate_help_name_role: str = "name"


class UserPresetsPageBase(BasePage):
    page_config: UserPresetsPageConfig

    def __init__(
        self,
        parent=None,
        *,
        preset_runtime_actions: UserPresetsRuntimeActions,
        connect_preset_signals,
        create_user_presets_open_folder_worker,
        create_preset_edit_action_worker,
        create_preset_bulk_action_worker,
        create_preset_activate_worker,
        create_preset_item_action_worker,
        create_preset_link_action_worker,
        create_preset_folder_action_worker,
        create_preset_storage_action_worker,
        load_preset_folder_state,
        open_preset_raw_editor,
        ui_state_store,
    ):
        self._config = self.page_config
        super().__init__(
            "Мои пресеты",
            "",
            parent,
            title_key=self._config.title_key,
        )
        self._preset_runtime_actions = preset_runtime_actions
        self._connect_preset_signals = connect_preset_signals
        self._create_user_presets_open_folder_worker = create_user_presets_open_folder_worker
        self._create_preset_edit_action_worker_fn = create_preset_edit_action_worker
        self._create_preset_bulk_action_worker_fn = create_preset_bulk_action_worker
        self._create_preset_activate_worker_fn = create_preset_activate_worker
        self._create_preset_item_action_worker_fn = create_preset_item_action_worker
        self._create_preset_link_action_worker_fn = create_preset_link_action_worker
        self._create_preset_folder_action_worker_fn = create_preset_folder_action_worker
        self._create_preset_storage_action_worker_fn = create_preset_storage_action_worker
        self._load_preset_folder_state_fn = load_preset_folder_state
        self._open_preset_raw_editor_callback = open_preset_raw_editor
        self._page_api = self._build_page_runtime().build_page_api()
        self._runtime_service = self._build_runtime_service()
        self._runtime_service.attach_page(self, self._build_runtime_adapter())

        self._configs_title_label = None
        self._get_configs_btn = None

        self._presets_model: Optional[PresetListModel] = None
        self._presets_delegate: Optional[PresetListDelegate] = None
        self._last_page_theme_key: tuple[str, str, str] | None = None

        self._bulk_reset_running = False
        self._layout_resync_timer = QTimer(self)
        self._layout_resync_timer.setSingleShot(True)
        self._layout_resync_timer.timeout.connect(self._resync_layout_metrics)
        self._layout_resync_delayed_timer = QTimer(self)
        self._layout_resync_delayed_timer.setSingleShot(True)
        self._layout_resync_delayed_timer.timeout.connect(self._resync_layout_metrics)

        self._preset_search_timer = QTimer(self)
        self._preset_search_timer.setSingleShot(True)
        self._preset_search_timer.timeout.connect(self._apply_preset_search)
        self._preset_search_input: Optional[LineEdit] = None
        self._toolbar_layout: Optional[PresetsToolbarLayout] = None
        self.open_folder_btn = None
        self._preset_status_icon = None

        self._ui_state_store: Optional[MainWindowStateStore] = None
        self._ui_state_unsubscribe = None
        self._cleanup_in_progress = False
        self._preset_activate_runtime = OneShotWorkerRuntime()
        self._preset_activate_request_id = 0
        self._pending_preset_activation: tuple[str, str] | None = None
        self._restore_preset_activation_marker_file_name = ""
        self._preset_item_action_runtime = OneShotWorkerRuntime()
        self._preset_item_action_request_id = 0
        self._preset_bulk_action_runtime = OneShotWorkerRuntime()
        self._preset_bulk_action_request_id = 0
        self._preset_bulk_action_kind = ""
        self._preset_bulk_action_pending: list[dict[str, str]] = []
        self._preset_edit_action_runtime = OneShotWorkerRuntime()
        self._preset_edit_action_request_id = 0
        self._preset_edit_action_pending: list[dict[str, object]] = []
        self._preset_storage_action_runtime = OneShotWorkerRuntime()
        self._preset_storage_action_request_id = 0
        self._pending_preset_storage_actions: list[dict[str, object]] = []
        self._pending_preset_write_actions: list[dict[str, object]] = []
        self._preset_write_action_start_scheduled = False
        self._preset_folder_action_runtime = OneShotWorkerRuntime()
        self._preset_folder_action_request_id = 0
        self._preset_folder_action_pending: list[dict[str, object]] = []
        self._preset_folder_action_start_scheduled = False
        self._preset_open_folder_runtime = OneShotWorkerRuntime()
        self._preset_open_folder_request_id = 0
        self._preset_open_folder_pending = False
        self._preset_open_folder_start_scheduled = False
        self._preset_item_action_pending: list[dict[str, str]] = []
        self._preset_link_action_runtime = OneShotWorkerRuntime()
        self._preset_link_action_request_id = 0
        self._preset_link_action_pending: list[str] = []
        self._preset_link_action_start_scheduled = False
        self._build_ui()
        self._after_ui_built()
        self.bind_ui_state_store(ui_state_store)

    def _tr(self, key: str, default: str, **kwargs) -> str:
        return _tr_text(key, self._ui_language, default, **kwargs)

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

    def _build_page_runtime(self):
        return UserPresetsPageRuntime(
            UserPresetsPageRuntimeConfig(
                launch_method=self._config.launch_method,
                folder_scope=self._config.folder_scope,
                empty_not_found_key=f"{self._config.tr_prefix}.empty.not_found",
                empty_none_key=f"{self._config.tr_prefix}.empty.none",
                list_log_prefix=self._config.log_prefix,
                activate_error_level=self._config.activate_error_level,
                activate_error_mode=self._config.activate_error_mode,
                preset_runtime_actions=self._preset_runtime_actions,
            )
        )

    def _build_runtime_service(self):
        return UserPresetsRuntimeService(scope_key=self._config.folder_scope)

    def _build_runtime_adapter(self) -> UserPresetsRuntimeAdapter:
        return UserPresetsRuntimeAdapter(
            bulk_reset_running=lambda: bool(self._bulk_reset_running),
            read_single_metadata=self._listing_api().read_single_preset_list_metadata_light,
            selected_source_file_name=self._listing_api().get_selected_source_preset_file_name_light,
            presets_dir=self._listing_api().get_presets_dir_light,
            cached_metadata=self._listing_api().get_cached_preset_list_metadata_light,
            load_all_metadata=self._listing_api().load_preset_list_metadata_light,
            load_folder_state=self._load_preset_folder_state_light,
            build_rows_plan=self._build_preset_rows_plan,
            apply_rows_plan=self._apply_presets_rows_plan,
        )

    def _apply_mode_labels(self) -> None:
        try:
            set_widget_text_if_changed(self.title_label, self._tr(self._config.title_key, "Мои пресеты"))
            if self.subtitle_label is not None:
                set_widget_text_if_changed(self.subtitle_label, "")
        except Exception:
            pass

    def _page_runtime_api(self):
        return self._page_api

    def _listing_api(self):
        return self._page_runtime_api().listing

    def _resolve_display_name(self, reference: str) -> str:
        candidate = str(reference or "").strip()
        if not candidate:
            return ""

        model = getattr(self, "_presets_model", None)
        try:
            row = model.find_preset_row(candidate) if model is not None else -1
            if row >= 0:
                index = model.index(row, 0)
                name_role = getattr(type(model), "NameRole", None)
                if index.isValid() and name_role is not None:
                    display_name = str(index.data(name_role) or "").strip()
                    if display_name:
                        return display_name
        except Exception:
            pass

        cached_metadata = self._runtime_service.cached_presets_metadata()
        metadata_key = candidate
        metadata = cached_metadata.get(metadata_key)
        if metadata is None and candidate and not candidate.lower().endswith(".txt"):
            metadata_key = f"{candidate}.txt"
            metadata = cached_metadata.get(metadata_key)
        if isinstance(metadata, dict):
            display_name = str(metadata.get("display_name") or "").strip()
            if display_name:
                return display_name

        return candidate[:-4].strip() if candidate.lower().endswith(".txt") else candidate

    def _on_store_changed(self):
        self._runtime_service.on_store_changed()

    def _on_store_content_changed(self, file_name: str):
        self._runtime_service.on_store_content_changed(file_name)

    def _on_store_switched(self, _name: str):
        self._runtime_service.on_store_switched(_name)

    def _on_ui_state_changed(self, state: AppUiState, changed_fields: frozenset[str]) -> None:
        handle_user_presets_ui_state_changed(
            cleanup_in_progress=self._cleanup_in_progress,
            runtime_service=self._runtime_service,
            state=state,
            changed_fields=changed_fields,
        )
        self._refresh_preset_status_bar(state)

    def _refresh_preset_status_bar(self, state: AppUiState | None = None) -> None:
        icon = self._preset_status_icon
        if icon is None:
            return
        if state is None and self._ui_state_store is not None:
            try:
                state = self._ui_state_store.snapshot()
            except Exception:
                state = None
        launch_running = bool(getattr(state, "launch_running", False)) if state is not None else False
        plan = build_runtime_preset_status_plan(
            base_status="selected" if launch_running else "selected_stopped",
            launch_method=self._config.launch_method,
            runtime_launch_method=getattr(state, "launch_method", "") if state is not None else "",
            launch_busy=bool(getattr(state, "launch_busy", False)) if state is not None else False,
            launch_busy_text=str(getattr(state, "launch_busy_text", "") or "") if state is not None else "",
            last_status_message=str(getattr(state, "last_status_message", "") or "") if state is not None else "",
        )
        icon.set_plan(plan)

    def _is_builtin_preset_file(self, name: str) -> bool:
        candidate = str(name or "").strip()
        if not candidate:
            return False

        model = getattr(self, "_presets_model", None)
        try:
            row = model.find_preset_row(candidate) if model is not None else -1
            if row >= 0:
                index = model.index(row, 0)
                builtin_role = getattr(type(model), "BuiltinRole", None)
                if index.isValid() and builtin_role is not None:
                    return bool(index.data(builtin_role))
        except Exception:
            pass

        cached_metadata = self._runtime_service.cached_presets_metadata()
        metadata = cached_metadata.get(candidate)
        if metadata is None and candidate and not candidate.lower().endswith(".txt"):
            metadata = cached_metadata.get(f"{candidate}.txt")
        if isinstance(metadata, dict):
            return bool(metadata.get("is_builtin", False))

        return False

    def _folder_scope_key(self) -> str:
        return self._config.folder_scope

    def _load_preset_folder_state_light(self) -> dict[str, object]:
        return self._load_preset_folder_state_fn(self._folder_scope_key())

    def on_page_activated(self) -> None:
        activate_user_presets_page(
            cleanup_in_progress=self._cleanup_in_progress,
            apply_mode_labels_fn=self._apply_mode_labels,
            resync_layout_metrics_fn=self._resync_layout_metrics,
            start_watching_presets_fn=self._start_watching_presets,
            runtime_service=self._runtime_service,
            refresh_presets_view_if_possible_fn=self.refresh_presets_view_if_possible,
            update_presets_view_height_fn=self._update_presets_view_height,
            schedule_layout_resync_fn=self._schedule_layout_resync,
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resync_layout_metrics()
        self._schedule_layout_resync()

    def on_page_hidden(self) -> None:
        self._layout_resync_timer.stop()
        self._layout_resync_delayed_timer.stop()

    def _after_ui_built(self) -> None:
        after_user_presets_ui_built(
            apply_page_theme_fn=self._apply_page_theme,
            connect_preset_signals_fn=lambda **callbacks: self._connect_preset_signals(
                self._config.launch_method,
                **callbacks,
            ),
            on_store_changed_fn=self._on_store_changed,
            on_store_switched_fn=self._on_store_switched,
            on_store_content_changed_fn=self._on_store_content_changed,
            log_fn=log,
            log_prefix=self._config.log_prefix,
        )

    def bind_ui_state_store(self, store: MainWindowStateStore) -> None:
        bind_user_presets_ui_state_store(
            current_store=self._ui_state_store,
            store=store,
            current_unsubscribe=self._ui_state_unsubscribe,
            set_store_fn=lambda value: setattr(self, "_ui_state_store", value),
            set_unsubscribe_fn=lambda value: setattr(self, "_ui_state_unsubscribe", value),
            on_ui_state_changed_fn=self._on_ui_state_changed,
        )

    def _schedule_layout_resync(self, include_delayed: bool = False):
        schedule_user_presets_layout_resync(
            cleanup_in_progress=self._cleanup_in_progress,
            layout_resync_timer=self._layout_resync_timer,
            layout_resync_delayed_timer=self._layout_resync_delayed_timer,
            include_delayed=include_delayed,
        )

    def _resync_layout_metrics(self):
        resync_user_presets_layout_metrics(
            cleanup_in_progress=self._cleanup_in_progress,
            toolbar_layout=getattr(self, "_toolbar_layout", None),
            viewport=self.viewport(),
            layout=self.layout,
            update_presets_view_height_fn=self._update_presets_view_height,
        )

    def set_smooth_scroll_enabled(self, enabled: bool) -> None:
        list_widget = getattr(self, "presets_list", None)
        delegate = getattr(list_widget, "scrollDelegate", None)
        if delegate is None:
            return
        try:
            from qfluentwidgets.common.smooth_scroll import SmoothMode
            mode = SmoothMode.COSINE if enabled else SmoothMode.NO_SMOOTH

            if hasattr(delegate, "useAni"):
                if not hasattr(delegate, "_zapret_base_use_ani"):
                    delegate._zapret_base_use_ani = bool(delegate.useAni)
                delegate.useAni = bool(delegate._zapret_base_use_ani) if enabled else False

            for smooth_attr in ("verticalSmoothScroll", "horizonSmoothScroll"):
                smooth = getattr(delegate, smooth_attr, None)
                smooth_setter = getattr(smooth, "setSmoothMode", None)
                if callable(smooth_setter):
                    smooth_setter(mode)

            setter = getattr(delegate, "setSmoothMode", None)
            if callable(setter):
                try:
                    setter(mode)
                except TypeError:
                    setter(mode, Qt.Orientation.Vertical)
            elif hasattr(delegate, "smoothMode"):
                delegate.smoothMode = mode
        except Exception:
            pass

    def _start_watching_presets(self):
        self._runtime_service.start_watching_presets()

    def _build_ui(self):
        tokens = get_theme_tokens()

        # This page should scroll only inside the presets list.
        # The outer BasePage scroll creates a second scrollbar and makes wheel
        # scrolling jump between two containers.
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.verticalScrollBar().hide()

        shell = build_user_presets_page_shell(
            parent=self,
            tr_fn=self._tr,
            tokens=tokens,
            strong_body_label_cls=StrongBodyLabel,
            line_edit_cls=LineEdit,
            primary_tool_button_cls=PrimaryToolButton,
            tr_prefix=self._config.tr_prefix,
            delegate_language_scope=self._config.delegate_language_scope,
            delegate_help_name_role=self._config.delegate_help_name_role,
            fluent_icon=FluentIcon,
            get_cached_qta_pixmap_fn=get_cached_qta_pixmap,
            on_open_new_configs_post=self._open_new_configs_post,
            on_create_clicked=self._on_create_clicked,
            on_import_clicked=self._on_import_clicked,
            on_open_folder_clicked=self._open_presets_folder,
            on_reset_all_presets_clicked=self._on_reset_all_presets_clicked,
            on_open_presets_info=self._open_presets_info,
            on_info_clicked=self._on_info_clicked,
            on_preset_search_text_changed=self._on_preset_search_text_changed,
            on_activate_preset=self._on_activate_preset,
            on_move_preset_by_step=self._move_preset_by_step,
            on_item_dropped=self._on_item_dropped,
            on_preset_context_requested=self._on_preset_context_requested,
            on_folder_context_requested=self._on_folder_context_requested,
            on_background_context_requested=self._on_folder_background_context_requested,
            on_preset_list_action=self._on_preset_list_action,
            ui_language=self._ui_language,
        )
        self._configs_icon = shell.configs_icon
        self._configs_title_label = shell.configs_title_label
        self._get_configs_btn = shell.get_configs_btn
        self._toolbar_layout = shell.toolbar_layout
        self.create_btn = shell.create_btn
        self.import_btn = shell.import_btn
        self.open_folder_btn = shell.open_folder_btn
        self.reset_all_btn = shell.reset_all_btn
        self.presets_info_btn = shell.presets_info_btn
        self.info_btn = shell.info_btn
        self._preset_search_input = shell.preset_search_input
        self.presets_list = shell.presets_list
        self._presets_model = shell.presets_model
        self._presets_delegate = shell.presets_delegate
        self._install_title_status_icon()

        self.add_widget(shell.configs_card)
        self.add_spacing(12)
        self.add_widget(self._toolbar_layout.container)
        try:
            from ui.smooth_scroll import get_page_smooth_scroll_enabled
            smooth_enabled = get_page_smooth_scroll_enabled()
            self.set_smooth_scroll_enabled(smooth_enabled)
        except Exception:
            pass
        self.add_widget(self.presets_list)
        self._refresh_preset_status_bar()

        # Make outer page scrolling feel less sluggish on long lists.
        self.verticalScrollBar().setSingleStep(48)

    def _install_title_status_icon(self) -> None:
        if self._preset_status_icon is not None:
            return
        title_index = self.layout.indexOf(self.title_label)
        if title_index < 0:
            return

        self.layout.removeWidget(self.title_label)
        self._title_status_header = QWidget(self.content)
        self._title_status_header.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        title_layout = QHBoxLayout(self._title_status_header)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(8)

        self._preset_status_icon = PresetStatusIcon(self._title_status_header, size=24)
        title_layout.addWidget(self._preset_status_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        title_layout.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignVCenter)
        title_layout.addStretch(1)
        self.layout.insertWidget(title_index, self._title_status_header)

    def _on_info_clicked(self) -> None:
        if MessageBox:
            box = MessageBox(
                self._tr(f"{self._config.tr_prefix}.info.title", "Что это такое?"),
                self._tr(
                    f"{self._config.tr_prefix}.info.body",
                    "Здесь простой режим: выберите любой пресет, примените его, "
                    "перезагрузите вкладку и проверьте, открывается ли ресурс. "
                    "Если не открывается, попробуйте следующий пресет. "
                    "Также здесь можно создавать, импортировать, экспортировать и переключать пользовательские пресеты.",
                ),
                self.window(),
            )
            box.cancelButton.hide()
            box.exec()

    def _open_presets_folder(self) -> None:
        self._request_preset_open_folder_action()

    def create_preset_open_folder_worker(self, request_id: int):
        return self._create_user_presets_open_folder_worker(
            request_id,
            launch_method=self._config.launch_method,
            parent=self,
        )

    def _request_preset_open_folder_action(self) -> None:
        if (
            self._worker_runtime_is_running("_preset_open_folder_runtime")
            or self.__dict__.get("_preset_open_folder_start_scheduled", False)
        ):
            self._preset_open_folder_pending = True
            return
        self._start_preset_open_folder_worker()

    def _start_preset_open_folder_worker(self) -> None:
        self._preset_open_folder_pending = False
        self._preset_open_folder_request_id = int(self.__dict__.get("_preset_open_folder_request_id", 0) or 0) + 1
        request_id = self._preset_open_folder_request_id

        def _bind_worker(worker) -> None:
            worker.failed.connect(self._on_preset_open_folder_failed)

        self._worker_runtime("_preset_open_folder_runtime").start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self.create_preset_open_folder_worker(request_id),
            bind_worker=_bind_worker,
            on_finished=self._on_preset_open_folder_worker_finished,
        )

    def _on_preset_open_folder_failed(self, request_id: int, error: str) -> None:
        if request_id != int(getattr(self, "_preset_open_folder_request_id", 0) or 0):
            return
        log(f"{self._config.log_prefix}: open presets folder failed: {error}", "WARNING")
        if InfoBar:
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr(
                    f"{self._config.tr_prefix}.error.open_folder",
                    "Не удалось открыть папку пресетов: {error}",
                    error=error,
                ),
                parent=self.window(),
            )

    def _on_preset_open_folder_worker_finished(self, worker) -> None:
        if self._preset_open_folder_pending:
            self._schedule_preset_open_folder_worker_start()

    def _schedule_preset_open_folder_worker_start(self) -> None:
        self._preset_open_folder_start_scheduled = True
        try:
            QTimer.singleShot(0, self._run_scheduled_preset_open_folder_worker_start)
        except Exception:
            self._run_scheduled_preset_open_folder_worker_start()

    def _run_scheduled_preset_open_folder_worker_start(self) -> None:
        self._preset_open_folder_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._start_preset_open_folder_worker()

    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        self._last_page_theme_key = apply_user_presets_page_theme(
            get_theme_tokens_fn=lambda: tokens or get_theme_tokens(),
            get_semantic_palette_fn=get_semantic_palette,
            get_cached_qta_pixmap_fn=get_cached_qta_pixmap,
            schedule_layout_resync_fn=self._schedule_layout_resync,
            configs_icon=getattr(self, "_configs_icon", None),
            reset_all_btn=getattr(self, "reset_all_btn", None),
            presets_list=getattr(self, "presets_list", None),
            previous_theme_key=self._last_page_theme_key,
            force=force,
            log_fn=log,
        )

    def _on_preset_search_text_changed(self, _text: str) -> None:
        schedule_preset_search(
            preset_search_timer=self._preset_search_timer,
            refresh_presets_view_from_cache_fn=self._refresh_presets_view_from_cache,
        )

    def _apply_preset_search(self) -> None:
        apply_preset_search(
            is_visible=self.isVisible(),
            runtime_service=self._runtime_service,
            refresh_presets_view_from_cache_fn=self._refresh_presets_view_from_cache,
        )

    def apply_sidebar_search_query(self, text: str) -> bool:
        query = str(text or "")
        search_input = self._preset_search_input
        if search_input is not None:
            try:
                if str(search_input.text() or "") == query:
                    return True
                search_input.setText(query)
                self._apply_preset_search()
                return True
            except Exception:
                pass
        self._apply_preset_search()
        return True

    def _update_presets_view_height(self):
        update_presets_view_height(
            presets_model=self._presets_model,
            presets_list=getattr(self, "presets_list", None),
            viewport=self.viewport(),
            layout=self.layout,
        )

    def _show_inline_action_create(self):
        dlg = self._config.create_dialog_cls([], self.window(), language=self._ui_language)
        if not dlg.exec():
            return
        name = dlg.nameEdit.text().strip()
        if not name:
            return
        self._request_preset_edit_action(
            "create",
            name=name,
            from_current=getattr(dlg, "_source", "current") == "current",
        )

    def _show_inline_action_rename(self, current_name: str):
        display_name = self._resolve_display_name(current_name)
        if self._is_builtin_preset_file(current_name):
            InfoBar.warning(
                title=self._tr("common.error.title", "Ошибка"),
                content="Встроенный пресет нельзя переименовать. Можно создать копию и работать уже с ней.",
                parent=self.window(),
            )
            return
        dlg = self._config.rename_dialog_cls(display_name, [], self.window(), language=self._ui_language)
        if not dlg.exec():
            return
        new_name = dlg.nameEdit.text().strip()
        if not new_name or new_name == display_name:
            return
        self._request_preset_edit_action(
            "rename",
            current_name=current_name,
            new_name=new_name,
        )

    def create_preset_edit_action_worker(
        self,
        request_id: int,
        *,
        action: str,
        name: str = "",
        current_name: str = "",
        new_name: str = "",
        from_current: bool = False,
    ):
        return self._create_preset_edit_action_worker_fn(
            request_id,
            launch_method=self._config.launch_method,
            action=action,
            name=name,
            current_name=current_name,
            new_name=new_name,
            from_current=from_current,
            parent=self,
        )

    def _request_preset_edit_action(
        self,
        action: str,
        *,
        name: str = "",
        current_name: str = "",
        new_name: str = "",
        from_current: bool = False,
    ) -> None:
        if self._preset_write_action_running():
            self._queue_preset_write_action(
                "edit",
                action=action,
                name=name,
                current_name=current_name,
                new_name=new_name,
                from_current=from_current,
            )
            return
        self._start_preset_edit_action_worker(
            action,
            name=name,
            current_name=current_name,
            new_name=new_name,
            from_current=from_current,
        )

    def _start_preset_edit_action_worker(
        self,
        action: str,
        *,
        name: str = "",
        current_name: str = "",
        new_name: str = "",
        from_current: bool = False,
    ) -> None:
        runtime = self._worker_runtime("_preset_edit_action_runtime")
        self._preset_edit_action_request_id = int(self.__dict__.get("_preset_edit_action_request_id", 0) or 0) + 1
        request_id = self._preset_edit_action_request_id

        def _bind_worker(worker) -> None:
            worker.completed.connect(self._on_preset_edit_action_finished)
            worker.failed.connect(self._on_preset_edit_action_failed)

        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self.create_preset_edit_action_worker(
                request_id,
                action=str(action or ""),
                name=str(name or ""),
                current_name=str(current_name or ""),
                new_name=str(new_name or ""),
                from_current=bool(from_current),
            ),
            bind_worker=_bind_worker,
            on_finished=self._on_preset_edit_action_worker_finished,
        )

    def _on_preset_edit_action_finished(self, request_id: int, action: str, result, context) -> None:
        if request_id != int(getattr(self, "_preset_edit_action_request_id", 0) or 0):
            return
        context = dict(context or {})
        structure_changed = bool(getattr(result, "structure_changed", False))
        if action == "create" and bool(getattr(result, "ok", False)):
            preset_file_name = str(getattr(result, "preset_file_name", "") or "").strip()
            preset_display_name = str(getattr(result, "preset_display_name", "") or context.get("name") or "").strip()
            if self._runtime_service.add_created_preset_locally(
                preset_file_name,
                preset_display_name,
            ):
                structure_changed = False
        if action == "rename" and bool(getattr(result, "ok", False)):
            preset_file_name = str(getattr(result, "preset_file_name", "") or "").strip()
            preset_display_name = str(getattr(result, "preset_display_name", "") or context.get("new_name") or "").strip()
            if self._runtime_service.rename_preset_locally(
                str(context.get("current_name") or ""),
                preset_file_name,
                preset_display_name,
            ):
                structure_changed = False
        if structure_changed:
            self._runtime_service.mark_presets_structure_changed()
        log(str(getattr(result, "log_message", "") or ""), str(getattr(result, "log_level", "") or "INFO"))

    def _on_preset_edit_action_failed(self, request_id: int, action: str, error: str, _context) -> None:
        if request_id != int(getattr(self, "_preset_edit_action_request_id", 0) or 0):
            return
        log(f"Ошибка действия preset ({action}): {error}", "ERROR")
        InfoBar.error(
            title=self._tr("common.error.title", "Ошибка"),
            content=self._tr(f"{self._config.tr_prefix}.error.generic", "Ошибка: {error}", error=error),
            parent=self.window(),
        )

    def _on_preset_edit_action_worker_finished(self, worker) -> None:
        if self._start_next_preset_write_action():
            return
        pending = self.__dict__.get("_preset_edit_action_pending") or []
        if pending and not bool(self.__dict__.get("_cleanup_in_progress", False)):
            next_action = pending.pop(0)
            self._start_preset_edit_action_worker(
                str(next_action.get("action") or ""),
                name=str(next_action.get("name") or ""),
                current_name=str(next_action.get("current_name") or ""),
                new_name=str(next_action.get("new_name") or ""),
                from_current=bool(next_action.get("from_current")),
            )

    def _on_create_clicked(self):
        self._show_inline_action_create()

    def _on_import_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self._tr(f"{self._config.tr_prefix}.file_dialog.import_title", "Импортировать пресет"),
            "",
            "Файлы пресетов (*.txt);;Все файлы (*.*)",
        )
        if not file_path:
            return
        self._request_preset_bulk_action("import", file_path=file_path)

    def _on_reset_all_presets_clicked(self):
        dlg = self._config.reset_all_dialog_cls(self.window(), language=self._ui_language)
        if not dlg.exec():
            return
        self._bulk_reset_running = True
        if not self._request_preset_bulk_action("reset_all"):
            self._bulk_reset_running = False

    def create_preset_bulk_action_worker(self, request_id: int, *, action: str, file_path: str = ""):
        return self._create_preset_bulk_action_worker_fn(
            request_id,
            launch_method=self._config.launch_method,
            action=action,
            file_path=file_path,
            parent=self,
        )

    def _request_preset_bulk_action(self, action: str, *, file_path: str = "") -> bool:
        if self._preset_write_action_running():
            self._queue_preset_write_action(
                "bulk",
                action=action,
                file_path=file_path,
            )
            return True
        self._start_preset_bulk_action_worker(action, file_path=file_path)
        return True

    def _start_preset_bulk_action_worker(self, action: str, *, file_path: str = "") -> None:
        runtime = self._worker_runtime("_preset_bulk_action_runtime")
        self._preset_bulk_action_request_id = int(self.__dict__.get("_preset_bulk_action_request_id", 0) or 0) + 1
        request_id = self._preset_bulk_action_request_id
        self._preset_bulk_action_kind = str(action or "")

        def _bind_worker(worker) -> None:
            worker.completed.connect(self._on_preset_bulk_action_finished)
            worker.failed.connect(self._on_preset_bulk_action_failed)

        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self.create_preset_bulk_action_worker(
                request_id,
                action=str(action or ""),
                file_path=str(file_path or ""),
            ),
            bind_worker=_bind_worker,
            on_finished=self._on_preset_bulk_action_worker_finished,
        )

    def _on_preset_bulk_action_finished(self, request_id: int, action: str, result, _context) -> None:
        if request_id != int(getattr(self, "_preset_bulk_action_request_id", 0) or 0):
            return
        log(str(getattr(result, "log_message", "") or ""), str(getattr(result, "log_level", "") or "INFO"))
        structure_changed = bool(getattr(result, "structure_changed", False))
        if action == "import" and bool(getattr(result, "ok", False)):
            if self._runtime_service.add_created_preset_locally(
                str(getattr(result, "actual_file_name", "") or ""),
                str(getattr(result, "actual_name", "") or ""),
            ):
                structure_changed = False
        if structure_changed:
            self._runtime_service.mark_presets_structure_changed()
        if action == "import":
            level = str(getattr(result, "infobar_level", "") or "")
            title = str(getattr(result, "infobar_title", "") or "")
            content = str(getattr(result, "infobar_content", "") or "")
            if level == "warning":
                InfoBar.warning(title=title, content=content, parent=self.window())
            else:
                InfoBar.success(title=title, content=content, parent=self.window())
        elif action == "reset_all":
            self._show_reset_all_result(
                int(getattr(result, "success_count", 0) or 0),
                int(getattr(result, "total_count", 0) or 0),
                int(getattr(result, "failed_count", 0) or 0),
            )

    def _on_preset_bulk_action_failed(self, request_id: int, action: str, error: str, _context) -> None:
        if request_id != int(getattr(self, "_preset_bulk_action_request_id", 0) or 0):
            return
        log(f"Ошибка массового действия preset ({action}): {error}", "ERROR")
        error_key = "error.import_exception" if action == "import" else "error.reset_all_exception"
        default = "Не удалось импортировать пресет: {error}" if action == "import" else "Ошибка восстановления пресетов: {error}"
        InfoBar.error(
            title=self._tr("common.error.title", "Ошибка"),
            content=self._tr(f"{self._config.tr_prefix}.{error_key}", default, error=error),
            parent=self.window(),
        )

    def _on_preset_bulk_action_worker_finished(self, worker) -> None:
        action = str(getattr(self, "_preset_bulk_action_kind", "") or "")
        self._preset_bulk_action_kind = ""
        if action == "reset_all":
            self._bulk_reset_running = False
            if self._runtime_service.is_ui_dirty() and self.isVisible():
                self.refresh_presets_view_if_possible()
        pending = self.__dict__.get("_preset_bulk_action_pending") or []
        if self._start_next_preset_write_action():
            return
        if pending and not self._cleanup_in_progress:
            next_action = pending.pop(0)
            self._start_preset_bulk_action_worker(
                str(next_action.get("action") or ""),
                file_path=str(next_action.get("file_path") or ""),
            )

    def _show_reset_all_result(self, success_count: int, total_count: int, failed_count: int = 0) -> None:
        show_reset_all_result(
            cleanup_in_progress=self._cleanup_in_progress,
            success_count=success_count,
            total_count=total_count,
            failed_count=failed_count,
            reset_all_btn=self.reset_all_btn,
            single_shot_fn=QTimer.singleShot,
            restore_label_fn=lambda: (not self._cleanup_in_progress) and self._restore_reset_all_button_label(),
        )

    def _restore_reset_all_button_label(self) -> None:
        restore_reset_all_button_label(
            cleanup_in_progress=self._cleanup_in_progress,
            reset_all_btn=self.reset_all_btn,
            tr_fn=self._tr,
            tr_prefix=self._config.tr_prefix,
        )

    def _load_presets(self):
        self._runtime_service.load_presets()

    def refresh_presets_view_if_possible(self) -> None:
        self._runtime_service.refresh_presets_view_if_possible()

    def _refresh_presets_view_from_cache(self) -> None:
        self._runtime_service.refresh_presets_view_from_cache()

    def _apply_preset_move_locally(
        self,
        file_name: str,
        destination_kind: str,
        destination_id: str = "",
        destination_folder_key: str = "",
    ) -> bool:
        if self._presets_model is None:
            return False
        view_state = self._runtime_service.capture_presets_view_state()
        moved = self._presets_model.move_preset(
            file_name,
            destination_kind,
            destination_id,
            destination_folder_key,
        )
        if moved:
            self._runtime_service.restore_presets_view_state(view_state)
            self._update_presets_view_height()
            self._schedule_layout_resync()
        return moved

    def _build_preset_rows_plan(
        self,
        *,
        all_presets: dict[str, dict[str, object]],
        query: str,
        active_file_name: str,
        language: str,
        folder_state: dict[str, object] | None = None,
    ):
        return self._listing_api().build_preset_rows_plan(
            all_presets=all_presets,
            query=query,
            active_file_name=active_file_name,
            language=language,
            folder_state=folder_state,
        )

    def _apply_presets_rows_plan(self, plan, started_at: float | None = None) -> None:
        apply_presets_rows_plan(
            runtime_service=self._runtime_service,
            presets_delegate=self._presets_delegate,
            presets_model=self._presets_model,
            presets_list=getattr(self, "presets_list", None),
            schedule_layout_resync_fn=self._schedule_layout_resync,
            update_presets_view_height_fn=self._update_presets_view_height,
            log_fn=log,
            plan=plan,
            started_at=started_at,
            log_source=self._config.log_prefix,
        )

    def _on_preset_list_action(self, action: str, name: str):
        dispatch_user_preset_list_action(
            action=action,
            name=name,
            handlers=UserPresetListActionHandlers(
                activate=self._on_activate_preset,
                open=self._open_preset_subpage,
                pin=self._on_toggle_pin_preset,
                rating=self._on_rate_preset,
                move_by_step=self._move_preset_by_step,
                edit=self._on_edit_preset,
                rename=self._on_rename_preset,
                duplicate=self._on_duplicate_preset,
                reset=self._on_reset_preset,
                delete=self._on_delete_preset,
                export=self._on_export_preset,
                toggle_folder=self._on_toggle_folder,
            ),
        )

    def _on_toggle_folder(self, folder_key: str) -> None:
        self._request_preset_folder_action("toggle_collapsed", folder_key=folder_key)

    def _open_preset_subpage(self, name: str):
        self._open_preset_raw_editor_callback(name)

    def _on_preset_context_requested(self, name: str, global_pos: QPoint):
        self._on_edit_preset(name, global_pos=global_pos)

    def _on_folder_context_requested(self, folder_key: str, global_pos: QPoint):
        self._show_folder_menu(folder_key, global_pos)

    def _on_folder_background_context_requested(self, global_pos: QPoint):
        self._show_folder_menu("", global_pos)

    def _show_folder_menu(self, folder_key: str, global_pos: QPoint):
        self._request_preset_folder_action(
            "load_state",
            folder_key=folder_key,
            context_extra={
                "show_menu": True,
                "folder_key": str(folder_key or ""),
                "global_pos": global_pos,
            },
        )

    def _show_folder_menu_with_state(self, folder_key: str, global_pos: QPoint, folder_state: dict):
        show_preset_folder_menu(
            parent=self,
            scope_key=self._folder_scope_key(),
            folder_key=folder_key,
            global_pos=global_pos,
            folder_state=folder_state,
            refresh_fn=self._refresh_presets_view_from_cache,
            request_folder_action_fn=self._request_preset_folder_action,
            log_fn=log,
        )

    def create_preset_folder_action_worker(
        self,
        request_id: int,
        *,
        action: str,
        folder_key: str = "",
        name: str = "",
        direction: int = 0,
        collapsed: bool = False,
        context_extra: dict | None = None,
    ):
        return self._create_preset_folder_action_worker_fn(
            request_id,
            scope_key=self._folder_scope_key(),
            action=action,
            folder_key=folder_key,
            name=name,
            direction=direction,
            collapsed=collapsed,
            context_extra=context_extra,
            parent=self,
        )

    def _request_preset_folder_action(
        self,
        action: str,
        *,
        folder_key: str = "",
        name: str = "",
        direction: int = 0,
        collapsed: bool = False,
        context_extra: dict | None = None,
    ) -> None:
        runtime = self._worker_runtime("_preset_folder_action_runtime")
        if runtime.is_running() or self.__dict__.get("_preset_folder_action_start_scheduled", False):
            self._preset_folder_action_pending.append(
                {
                    "action": str(action or ""),
                    "folder_key": str(folder_key or ""),
                    "name": str(name or ""),
                    "direction": int(direction or 0),
                    "collapsed": bool(collapsed),
                    "context_extra": dict(context_extra or {}),
                }
            )
            return
        self._preset_folder_action_request_id = int(
            self.__dict__.get("_preset_folder_action_request_id", 0) or 0
        ) + 1
        request_id = self._preset_folder_action_request_id

        def _bind_worker(worker) -> None:
            worker.completed.connect(self._on_preset_folder_action_finished)
            worker.failed.connect(self._on_preset_folder_action_failed)

        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self.create_preset_folder_action_worker(
                request_id,
                action=str(action or ""),
                folder_key=str(folder_key or ""),
                name=str(name or ""),
                direction=int(direction or 0),
                collapsed=bool(collapsed),
                context_extra=dict(context_extra or {}),
            ),
            bind_worker=_bind_worker,
            on_finished=self._on_preset_folder_action_worker_finished,
        )

    def _on_preset_folder_action_finished(self, request_id: int, action: str, result, context) -> None:
        if request_id != int(getattr(self, "_preset_folder_action_request_id", 0) or 0):
            return
        context = dict(context or {})
        if isinstance(result, dict):
            self._runtime_service.update_cached_folder_state(result)
        elif isinstance(context.get("folder_state"), dict):
            self._runtime_service.update_cached_folder_state(context.get("folder_state"))
        if str(action or "") == "load_state" and bool(context.get("show_menu")):
            self._show_folder_menu_with_state(
                str(context.get("folder_key") or ""),
                context.get("global_pos"),
                result if isinstance(result, dict) else {},
            )
            return
        if bool(result):
            self._refresh_presets_view_from_cache()

    def _on_preset_folder_action_failed(self, request_id: int, action: str, error: str, _context) -> None:
        if request_id != int(getattr(self, "_preset_folder_action_request_id", 0) or 0):
            return
        log(f"{self.__class__.__name__}: не удалось выполнить действие папки preset ({action}): {error}", "ERROR")

    def _on_preset_folder_action_worker_finished(self, worker) -> None:
        if self._preset_folder_action_pending:
            pending = self._preset_folder_action_pending.pop(0)
            self._schedule_preset_folder_action_start(pending)

    def _schedule_preset_folder_action_start(self, pending: dict[str, object]) -> None:
        queued = dict(pending or {})
        self._preset_folder_action_start_scheduled = True
        try:
            QTimer.singleShot(0, lambda: self._run_scheduled_preset_folder_action_start(queued))
        except Exception:
            self._run_scheduled_preset_folder_action_start(queued)

    def _run_scheduled_preset_folder_action_start(self, pending: dict[str, object]) -> None:
        self._preset_folder_action_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._request_preset_folder_action(
            str(pending.get("action") or ""),
            folder_key=str(pending.get("folder_key") or ""),
            name=str(pending.get("name") or ""),
            direction=int(pending.get("direction") or 0),
            collapsed=bool(pending.get("collapsed")),
            context_extra=dict(pending.get("context_extra") or {}),
        )

    def _on_toggle_pin_preset(self, name: str):
        self._request_preset_storage_action(
            "pin",
            name=name,
            display_name=self._resolve_display_name(name),
        )

    def _on_rate_preset(self, name: str):
        self._show_rating_menu(name)

    def _move_preset_by_step(self, name: str, direction: int):
        self._request_preset_storage_action(
            "move_step",
            name=name,
            direction=direction,
            cached_metadata=self._runtime_service.cached_presets_metadata(),
        )

    def _on_item_dropped(
        self,
        source_kind: str,
        source_id: str,
        destination_kind: str,
        destination_id: str,
        destination_folder_key: str = "",
    ):
        self._request_preset_storage_action(
            "drop",
            source_kind=source_kind,
            source_id=source_id,
            destination_kind=destination_kind,
            destination_id=destination_id,
            destination_folder_key=destination_folder_key,
        )

    def create_preset_storage_action_worker(
        self,
        request_id: int,
        *,
        action: str,
        name: str = "",
        display_name: str = "",
        rating: int = 0,
        direction: int = 0,
        cached_metadata=None,
        source_kind: str = "",
        source_id: str = "",
        destination_kind: str = "",
        destination_id: str = "",
        destination_folder_key: str = "",
    ):
        return self._create_preset_storage_action_worker_fn(
            request_id,
            scope_key=self._folder_scope_key(),
            list_preset_entries=self._listing_api().list_preset_entries_light,
            action=action,
            name=name,
            display_name=display_name,
            rating=rating,
            direction=direction,
            cached_metadata=cached_metadata,
            source_kind=source_kind,
            source_id=source_id,
            destination_kind=destination_kind,
            destination_id=destination_id,
            destination_folder_key=destination_folder_key,
            parent=self,
        )

    def _request_preset_storage_action(
        self,
        action: str,
        *,
        name: str = "",
        display_name: str = "",
        rating: int = 0,
        direction: int = 0,
        cached_metadata=None,
        source_kind: str = "",
        source_id: str = "",
        destination_kind: str = "",
        destination_id: str = "",
        destination_folder_key: str = "",
    ) -> None:
        if self._preset_write_action_running():
            self._queue_preset_write_action(
                "storage",
                action=action,
                name=name,
                display_name=display_name,
                rating=rating,
                direction=direction,
                cached_metadata=cached_metadata,
                source_kind=source_kind,
                source_id=source_id,
                destination_kind=destination_kind,
                destination_id=destination_id,
                destination_folder_key=destination_folder_key,
            )
            return
        self._start_preset_storage_action_worker(
            action,
            name=name,
            display_name=display_name,
            rating=rating,
            direction=direction,
            cached_metadata=cached_metadata,
            source_kind=source_kind,
            source_id=source_id,
            destination_kind=destination_kind,
            destination_id=destination_id,
            destination_folder_key=destination_folder_key,
        )

    def _preset_write_action_running(self) -> bool:
        if self.__dict__.get("_preset_write_action_start_scheduled", False):
            return True
        for attr in (
            "_preset_activate_runtime",
            "_preset_item_action_runtime",
            "_preset_bulk_action_runtime",
            "_preset_edit_action_runtime",
            "_preset_storage_action_runtime",
        ):
            if self._worker_runtime(attr).is_running():
                return True
        return False

    def _queue_preset_write_action(
        self,
        kind: str,
        *,
        action: str = "",
        name: str = "",
        display_name: str = "",
        rating: int = 0,
        direction: int = 0,
        cached_metadata=None,
        source_kind: str = "",
        source_id: str = "",
        destination_kind: str = "",
        destination_id: str = "",
        destination_folder_key: str = "",
        file_name: str = "",
        file_path: str = "",
        current_name: str = "",
        new_name: str = "",
        from_current: bool = False,
    ) -> None:
        operation = {
            "kind": str(kind or ""),
            "action": str(action or ""),
            "name": str(name or ""),
            "display_name": str(display_name or ""),
            "rating": int(rating or 0),
            "direction": int(direction or 0),
            "cached_metadata": cached_metadata,
            "source_kind": str(source_kind or ""),
            "source_id": str(source_id or ""),
            "destination_kind": str(destination_kind or ""),
            "destination_id": str(destination_id or ""),
            "destination_folder_key": str(destination_folder_key or ""),
            "file_name": str(file_name or ""),
            "file_path": str(file_path or ""),
        }
        if operation["kind"] == "edit":
            operation["current_name"] = str(current_name or "")
            operation["new_name"] = str(new_name or "")
            operation["from_current"] = bool(from_current)
        self.__dict__.setdefault("_pending_preset_write_actions", []).append(operation)
        if operation["kind"] == "storage":
            self.__dict__.setdefault("_pending_preset_storage_actions", []).append(
                {
                    "action": operation["action"],
                    "name": operation["name"],
                    "display_name": operation["display_name"],
                    "rating": operation["rating"],
                    "direction": operation["direction"],
                    "cached_metadata": operation["cached_metadata"],
                    "source_kind": operation["source_kind"],
                    "source_id": operation["source_id"],
                    "destination_kind": operation["destination_kind"],
                    "destination_id": operation["destination_id"],
                    "destination_folder_key": operation["destination_folder_key"],
                }
            )
        elif operation["kind"] == "activate":
            self._pending_preset_activation = (operation["file_name"], operation["display_name"])
        elif operation["kind"] == "bulk":
            self.__dict__.setdefault("_preset_bulk_action_pending", []).append(
                {
                    "action": operation["action"],
                    "file_path": operation["file_path"],
                }
            )
        elif operation["kind"] == "edit":
            self.__dict__.setdefault("_preset_edit_action_pending", []).append(
                {
                    "action": operation["action"],
                    "name": operation["name"],
                    "current_name": operation["current_name"],
                    "new_name": operation["new_name"],
                    "from_current": operation["from_current"],
                }
            )
        elif operation["kind"] == "item":
            self.__dict__.setdefault("_preset_item_action_pending", []).append(
                {
                    "action": operation["action"],
                    "file_name": operation["file_name"],
                    "display_name": operation["display_name"],
                    "file_path": operation["file_path"],
                }
            )

    def _pop_next_preset_write_action(self) -> dict[str, object] | None:
        pending_operations = self.__dict__.setdefault("_pending_preset_write_actions", [])
        if pending_operations:
            operation = dict(pending_operations.pop(0))
            if operation.get("kind") == "storage":
                pending_storage = self.__dict__.setdefault("_pending_preset_storage_actions", [])
                if pending_storage:
                    pending_storage.pop(0)
            elif operation.get("kind") == "item":
                pending_item = self.__dict__.setdefault("_preset_item_action_pending", [])
                if pending_item:
                    pending_item.pop(0)
            elif operation.get("kind") == "activate":
                self._pending_preset_activation = None
            elif operation.get("kind") == "bulk":
                pending_bulk = self.__dict__.setdefault("_preset_bulk_action_pending", [])
                if pending_bulk:
                    pending_bulk.pop(0)
            elif operation.get("kind") == "edit":
                pending_edit = self.__dict__.setdefault("_preset_edit_action_pending", [])
                if pending_edit:
                    pending_edit.pop(0)
            return operation
        pending_storage = self.__dict__.setdefault("_pending_preset_storage_actions", [])
        if pending_storage:
            pending = dict(pending_storage.pop(0))
            pending["kind"] = "storage"
            pending["file_name"] = ""
            pending["file_path"] = ""
            return pending
        pending_item = self.__dict__.setdefault("_preset_item_action_pending", [])
        if pending_item:
            pending = dict(pending_item.pop(0))
            return {
                "kind": "item",
                "action": str(pending.get("action") or ""),
                "name": "",
                "display_name": str(pending.get("display_name") or ""),
                "rating": 0,
                "direction": 0,
                "cached_metadata": None,
                "source_kind": "",
                "source_id": "",
                "destination_kind": "",
                "destination_id": "",
                "destination_folder_key": "",
                "file_name": str(pending.get("file_name") or ""),
                "file_path": str(pending.get("file_path") or ""),
                "current_name": "",
                "new_name": "",
                "from_current": False,
            }
        pending_activation = self.__dict__.get("_pending_preset_activation")
        if pending_activation:
            self._pending_preset_activation = None
            return {
                "kind": "activate",
                "action": "",
                "name": "",
                "display_name": str(pending_activation[1] or ""),
                "rating": 0,
                "direction": 0,
                "cached_metadata": None,
                "source_kind": "",
                "source_id": "",
                "destination_kind": "",
                "destination_id": "",
                "destination_folder_key": "",
                "file_name": str(pending_activation[0] or ""),
                "file_path": "",
                "current_name": "",
                "new_name": "",
                "from_current": False,
            }
        pending_bulk = self.__dict__.setdefault("_preset_bulk_action_pending", [])
        if pending_bulk:
            pending = dict(pending_bulk.pop(0))
            return {
                "kind": "bulk",
                "action": str(pending.get("action") or ""),
                "name": "",
                "display_name": "",
                "rating": 0,
                "direction": 0,
                "cached_metadata": None,
                "source_kind": "",
                "source_id": "",
                "destination_kind": "",
                "destination_id": "",
                "destination_folder_key": "",
                "file_name": "",
                "file_path": str(pending.get("file_path") or ""),
                "current_name": "",
                "new_name": "",
                "from_current": False,
            }
        pending_edit = self.__dict__.setdefault("_preset_edit_action_pending", [])
        if pending_edit:
            pending = dict(pending_edit.pop(0))
            return {
                "kind": "edit",
                "action": str(pending.get("action") or ""),
                "name": str(pending.get("name") or ""),
                "display_name": "",
                "rating": 0,
                "direction": 0,
                "cached_metadata": None,
                "source_kind": "",
                "source_id": "",
                "destination_kind": "",
                "destination_id": "",
                "destination_folder_key": "",
                "file_name": "",
                "file_path": "",
                "current_name": str(pending.get("current_name") or ""),
                "new_name": str(pending.get("new_name") or ""),
                "from_current": bool(pending.get("from_current")),
            }
        return None

    def _start_next_preset_write_action(self) -> bool:
        if self._preset_write_action_running():
            return True
        pending = self._pop_next_preset_write_action()
        if not pending:
            return False
        self._schedule_preset_write_action_start(pending)
        return True

    def _schedule_preset_write_action_start(self, operation: dict[str, object]) -> None:
        queued = dict(operation or {})
        if self.__dict__.get("_preset_write_action_start_scheduled", False):
            self.__dict__.setdefault("_pending_preset_write_actions", []).insert(0, queued)
            return
        self._preset_write_action_start_scheduled = True
        try:
            QTimer.singleShot(0, lambda: self._run_preset_write_action(queued))
        except Exception:
            self._run_preset_write_action(queued)

    def _run_preset_write_action(self, pending: dict[str, object]) -> bool:
        self._preset_write_action_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress"):
            return False
        if self._preset_write_action_running():
            self.__dict__.setdefault("_pending_preset_write_actions", []).insert(0, dict(pending or {}))
            return False
        if pending.get("kind") == "storage":
            self._start_preset_storage_action_worker(
                str(pending.get("action") or ""),
                name=str(pending.get("name") or ""),
                display_name=str(pending.get("display_name") or ""),
                rating=int(pending.get("rating") or 0),
                direction=int(pending.get("direction") or 0),
                cached_metadata=pending.get("cached_metadata"),
                source_kind=str(pending.get("source_kind") or ""),
                source_id=str(pending.get("source_id") or ""),
                destination_kind=str(pending.get("destination_kind") or ""),
                destination_id=str(pending.get("destination_id") or ""),
                destination_folder_key=str(pending.get("destination_folder_key") or ""),
            )
            return True
        if pending.get("kind") == "item":
            self._start_preset_item_action_worker(
                str(pending.get("action") or ""),
                file_name=str(pending.get("file_name") or ""),
                display_name=str(pending.get("display_name") or ""),
                file_path=str(pending.get("file_path") or ""),
            )
            return True
        if pending.get("kind") == "activate":
            self._start_preset_activation_worker(
                str(pending.get("file_name") or ""),
                str(pending.get("display_name") or ""),
            )
            return True
        if pending.get("kind") == "bulk":
            self._start_preset_bulk_action_worker(
                str(pending.get("action") or ""),
                file_path=str(pending.get("file_path") or ""),
            )
            return True
        if pending.get("kind") == "edit":
            self._start_preset_edit_action_worker(
                str(pending.get("action") or ""),
                name=str(pending.get("name") or ""),
                current_name=str(pending.get("current_name") or ""),
                new_name=str(pending.get("new_name") or ""),
                from_current=bool(pending.get("from_current")),
            )
            return True
        return False

    def _start_preset_storage_action_worker(
        self,
        action: str,
        *,
        name: str = "",
        display_name: str = "",
        rating: int = 0,
        direction: int = 0,
        cached_metadata=None,
        source_kind: str = "",
        source_id: str = "",
        destination_kind: str = "",
        destination_id: str = "",
        destination_folder_key: str = "",
    ) -> None:
        runtime = self._worker_runtime("_preset_storage_action_runtime")
        self._preset_storage_action_request_id = int(
            self.__dict__.get("_preset_storage_action_request_id", 0) or 0
        ) + 1
        request_id = self._preset_storage_action_request_id

        def _bind_worker(worker) -> None:
            worker.completed.connect(self._on_preset_storage_action_finished)
            worker.failed.connect(self._on_preset_storage_action_failed)

        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self.create_preset_storage_action_worker(
                request_id,
                action=str(action or ""),
                name=str(name or ""),
                display_name=str(display_name or ""),
                rating=int(rating or 0),
                direction=int(direction or 0),
                cached_metadata=cached_metadata,
                source_kind=str(source_kind or ""),
                source_id=str(source_id or ""),
                destination_kind=str(destination_kind or ""),
                destination_id=str(destination_id or ""),
                destination_folder_key=str(destination_folder_key or ""),
            ),
            bind_worker=_bind_worker,
            on_finished=self._on_preset_storage_action_worker_finished,
        )

    def _on_preset_storage_action_finished(self, request_id: int, action: str, result, context) -> None:
        if request_id != int(getattr(self, "_preset_storage_action_request_id", 0) or 0):
            return
        context = dict(context or {})
        if isinstance(context.get("folder_state"), dict):
            self._runtime_service.update_cached_folder_state(context.get("folder_state"))
        if action == "pin":
            display_name = str(context.get("display_name") or context.get("name") or "")
            log(f"Пресет '{display_name}' {'закреплён' if bool(result) else 'откреплён'}", "INFO")
            self._refresh_presets_view_from_cache()
        elif action == "rating":
            if bool(result):
                self._update_cached_preset_rating(
                    str(context.get("name") or ""),
                    int(context.get("rating") or 0),
                )
                self._refresh_presets_view_from_cache()
        elif action == "move_step":
            if bool(result):
                self._refresh_presets_view_from_cache()
        elif action == "drop" and bool(result):
            source_id = str(context.get("source_id") or "")
            destination_kind = str(context.get("destination_kind") or "")
            destination_id = str(context.get("destination_id") or "")
            destination_folder_key = str(context.get("destination_folder_key") or "")
            log(f"Элемент '{source_id}' перенесён перетаскиванием", "INFO")
            applied_locally = self._apply_preset_move_locally(
                source_id,
                destination_kind,
                destination_id,
                destination_folder_key,
            )
            if not applied_locally:
                self._refresh_presets_view_from_cache()

    def _on_preset_storage_action_failed(self, request_id: int, action: str, error: str, _context) -> None:
        if request_id != int(getattr(self, "_preset_storage_action_request_id", 0) or 0):
            return
        if action == "pin":
            log(f"Ошибка закрепления пресета: {error}", "ERROR")
        elif action == "move_step":
            log(f"Ошибка перестановки пресета: {error}", "ERROR")
        else:
            log(f"Ошибка перетаскивания элемента: {error}", "ERROR")

    def _on_preset_storage_action_worker_finished(self, worker) -> None:
        self._start_next_preset_write_action()

    def _on_activate_preset(self, name: str) -> bool:
        preset_file_name = str(name or "").strip()
        if not preset_file_name:
            return False
        current_file_name = str(self._runtime_service.active_preset_file_name() or "").strip()
        if current_file_name and current_file_name.lower() == preset_file_name.lower():
            return True
        display_name = self._resolve_display_name(preset_file_name) or preset_file_name
        if not self._preset_activation_worker_running():
            self._restore_preset_activation_marker_file_name = current_file_name
        self._request_preset_activation(preset_file_name, display_name)
        return True

    def _preset_activation_worker_running(self) -> bool:
        return self._worker_runtime_is_running("_preset_activate_runtime")

    def create_preset_activate_worker(self, request_id: int, *, file_name: str, display_name: str):
        return self._create_preset_activate_worker_fn(
            request_id,
            launch_method=self._config.launch_method,
            activate_error_level=self._config.activate_error_level,
            activate_error_mode=self._config.activate_error_mode,
            file_name=file_name,
            display_name=display_name,
            parent=self,
        )

    def _request_preset_activation(self, file_name: str, display_name: str) -> None:
        file_name = str(file_name or "").strip()
        display_name = str(display_name or "").strip()
        if self._preset_write_action_running():
            self._queue_preset_write_action(
                "activate",
                file_name=file_name,
                display_name=display_name,
            )
            return
        self._start_preset_activation_worker(file_name, display_name)

    def _start_preset_activation_worker(self, file_name: str, display_name: str) -> None:
        runtime = self._worker_runtime("_preset_activate_runtime")
        self._preset_activate_request_id = int(self.__dict__.get("_preset_activate_request_id", 0) or 0) + 1
        request_id = self._preset_activate_request_id
        self._runtime_service.apply_active_preset_marker_for_file(str(file_name or "").strip())

        def _bind_worker(worker) -> None:
            worker.activated.connect(self._on_preset_activation_finished)
            worker.failed.connect(self._on_preset_activation_failed)

        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self.create_preset_activate_worker(
                request_id,
                file_name=file_name,
                display_name=display_name,
            ),
            bind_worker=_bind_worker,
            on_finished=self._on_preset_activate_worker_finished,
        )

    def _on_preset_activation_finished(self, request_id: int, result) -> None:
        if request_id != int(getattr(self, "_preset_activate_request_id", 0) or 0):
            return
        if self.__dict__.get("_pending_preset_activation"):
            if bool(getattr(result, "ok", False)) and getattr(result, "activated_file_name", None):
                self._restore_preset_activation_marker_file_name = str(result.activated_file_name)
            return
        log(str(getattr(result, "log_message", "") or ""), str(getattr(result, "log_level", "") or "INFO"))
        if bool(getattr(result, "ok", False)) and getattr(result, "activated_file_name", None):
            return
        if str(getattr(result, "infobar_level", "") or "") == "error":
            InfoBar.error(
                title=str(getattr(result, "infobar_title", "") or self._tr("common.error.title", "Ошибка")),
                content=str(getattr(result, "infobar_content", "") or ""),
                parent=self.window(),
            )
        self._restore_preset_activation_marker()

    def _on_preset_activation_failed(self, request_id: int, error: str) -> None:
        if request_id != int(getattr(self, "_preset_activate_request_id", 0) or 0):
            return
        if self.__dict__.get("_pending_preset_activation"):
            return
        log(f"Ошибка активации preset-а: {error}", "ERROR")
        InfoBar.error(
            title=self._tr("common.error.title", "Ошибка"),
            content=str(error),
            parent=self.window(),
        )
        self._restore_preset_activation_marker()

    def _restore_preset_activation_marker(self) -> None:
        restore_file_name = str(self.__dict__.get("_restore_preset_activation_marker_file_name") or "").strip()
        if restore_file_name:
            self._runtime_service.apply_active_preset_marker_for_file(restore_file_name)
            return
        self._runtime_service.apply_active_preset_marker_for_file("")

    def _on_preset_activate_worker_finished(self, worker) -> None:
        if self._start_next_preset_write_action():
            return
        pending = self.__dict__.get("_pending_preset_activation")
        self._pending_preset_activation = None
        if pending:
            self._schedule_pending_preset_activation_start(pending[0], pending[1])

    def _schedule_pending_preset_activation_start(self, file_name: str, display_name: str) -> None:
        try:
            QTimer.singleShot(
                0,
                lambda: self._start_preset_activation_worker(
                    str(file_name or ""),
                    str(display_name or ""),
                ),
            )
        except Exception:
            self._start_preset_activation_worker(
                str(file_name or ""),
                str(display_name or ""),
            )

    def _on_edit_preset(self, name: str, global_pos: QPoint | None = None):
        open_edit_preset_menu_action(
            page=self,
            name=name,
            global_pos=global_pos,
            is_builtin_preset_file_fn=self._is_builtin_preset_file,
            is_selected_preset_file_fn=self._is_selected_source_preset_file,
            tr_fn=self._tr,
            make_menu_action=make_menu_action,
            fluent_icon=fluent_icon,
            round_menu_cls=RoundMenu,
            on_preset_list_action_fn=self._on_preset_list_action,
            show_preset_actions_menu_fn=show_preset_actions_menu,
            tr_prefix=self._config.tr_prefix,
        )

    def _is_selected_source_preset_file(self, name: str) -> bool:
        current = str(self._runtime_service.active_preset_file_name() or "").strip().lower()
        candidate = str(name or "").strip().lower()
        return bool(current and candidate and current == candidate)

    def _update_cached_preset_rating(self, name: str, rating: int) -> None:
        cached_metadata = self._runtime_service.cached_presets_metadata()
        preset_name = str(name or "").strip()
        if not preset_name:
            return
        metadata_key = preset_name
        metadata = cached_metadata.get(metadata_key)
        if metadata is None and not preset_name.lower().endswith(".txt"):
            metadata_key = f"{preset_name}.txt"
            metadata = cached_metadata.get(metadata_key)
        if metadata is None:
            return
        updated = dict(metadata)
        updated["rating"] = max(0, min(10, int(rating or 0)))
        cached_metadata[metadata_key] = updated

    def _show_rating_menu(self, name: str, global_pos: QPoint | None = None):
        display_name = self._resolve_display_name(name)
        current_rating = 0
        cached_metadata = self._runtime_service.cached_presets_metadata()
        preset_name = str(name or "").strip()
        rating_meta = cached_metadata.get(preset_name) or {}
        if not rating_meta and preset_name and not preset_name.lower().endswith(".txt"):
            rating_meta = cached_metadata.get(f"{preset_name}.txt") or {}
        try:
            current_rating = int(rating_meta.get("rating", 0) or 0)
        except (TypeError, ValueError):
            current_rating = 0
        rating = show_preset_rating_menu(
            self,
            current_rating=current_rating,
            clear_label=self._tr(f"{self._config.tr_prefix}.menu.rating_clear", "Сбросить рейтинг"),
            global_pos=global_pos,
        )
        if rating is None:
            return
        self._request_preset_storage_action(
            "rating",
            name=name,
            display_name=display_name,
            rating=int(rating),
        )

    def _on_rename_preset(self, name: str):
        rename_preset_action(
            name=name,
            is_builtin_preset_file_fn=self._is_builtin_preset_file,
            show_inline_action_rename_fn=self._show_inline_action_rename,
            info_bar_cls=InfoBar,
            tr_fn=self._tr,
            parent_window=self.window(),
        )

    def _on_duplicate_preset(self, name: str):
        display_name = self._resolve_display_name(name)
        self._request_preset_item_action(
            "duplicate",
            file_name=name,
            display_name=display_name,
        )

    def _on_reset_preset(self, name: str):
        display_name = self._resolve_display_name(name)
        if MessageBox:
            box = MessageBox(
                self._tr(f"{self._config.tr_prefix}.dialog.reset_single.title", "Вернуть встроенный пресет?"),
                self._tr(
                    f"{self._config.tr_prefix}.dialog.reset_single.body",
                    "Будет удалён ваш изменённый файл пресета «{name}».\n"
                    "После этого снова появится встроенный пресет с тем же именем файла.\n"
                    "Изменения в этом файле будут потеряны.",
                    name=display_name,
                ),
                self.window(),
            )
            box.yesButton.setText(self._tr(f"{self._config.tr_prefix}.dialog.reset_single.button", "Вернуть встроенный"))
            box.cancelButton.setText(self._tr(f"{self._config.tr_prefix}.dialog.button.cancel", "Отмена"))
            if not box.exec():
                return
        self._request_preset_item_action(
            "reset",
            file_name=name,
            display_name=display_name,
        )

    def _on_delete_preset(self, name: str):
        display_name = self._resolve_display_name(name)
        if not self._is_builtin_preset_file(name) and MessageBox:
            box = MessageBox(
                self._tr(f"{self._config.tr_prefix}.dialog.delete_single.title", "Удалить пресет?"),
                self._tr(
                    f"{self._config.tr_prefix}.dialog.delete_single.body",
                    "Пользовательский пресет «{name}» будет удалён.\n"
                    "Изменения в нём будут потеряны.\n"
                    "Вернуть его можно только создав новый пресет или импортировав txt-файл.",
                    name=display_name,
                ),
                self.window(),
            )
            box.yesButton.setText(self._tr(f"{self._config.tr_prefix}.dialog.delete_single.button", "Удалить"))
            box.cancelButton.setText(self._tr(f"{self._config.tr_prefix}.dialog.button.cancel", "Отмена"))
            if not box.exec():
                return
        self._request_preset_item_action(
            "delete",
            file_name=name,
            display_name=display_name,
        )

    def _on_export_preset(self, name: str):
        display_name = self._resolve_display_name(name)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self._tr(f"{self._config.tr_prefix}.file_dialog.export_title", "Экспортировать пресет"),
            f"{display_name}.txt",
            "Файлы пресетов (*.txt);;Все файлы (*.*)",
        )
        if not file_path:
            return
        self._request_preset_item_action(
            "export",
            file_name=name,
            display_name=display_name,
            file_path=file_path,
        )

    def create_preset_item_action_worker(
        self,
        request_id: int,
        *,
        action: str,
        file_name: str,
        display_name: str,
        file_path: str = "",
    ):
        return self._create_preset_item_action_worker_fn(
            request_id,
            launch_method=self._config.launch_method,
            action=action,
            file_name=file_name,
            display_name=display_name,
            file_path=file_path,
            parent=self,
        )

    def _request_preset_item_action(
        self,
        action: str,
        *,
        file_name: str,
        display_name: str,
        file_path: str = "",
    ) -> None:
        if self._preset_write_action_running():
            self._queue_preset_write_action(
                "item",
                action=action,
                file_name=file_name,
                display_name=display_name,
                file_path=file_path,
            )
            return
        self._start_preset_item_action_worker(
            action,
            file_name=file_name,
            display_name=display_name,
            file_path=file_path,
        )

    def _start_preset_item_action_worker(
        self,
        action: str,
        *,
        file_name: str,
        display_name: str,
        file_path: str = "",
    ) -> None:
        runtime = self._worker_runtime("_preset_item_action_runtime")
        self._preset_item_action_request_id = int(self.__dict__.get("_preset_item_action_request_id", 0) or 0) + 1
        request_id = self._preset_item_action_request_id

        def _bind_worker(worker) -> None:
            worker.completed.connect(self._on_preset_item_action_finished)
            worker.failed.connect(self._on_preset_item_action_failed)

        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self.create_preset_item_action_worker(
                request_id,
                action=str(action or ""),
                file_name=str(file_name or ""),
                display_name=str(display_name or ""),
                file_path=str(file_path or ""),
            ),
            bind_worker=_bind_worker,
            on_finished=self._on_preset_item_action_worker_finished,
        )

    def _on_preset_item_action_finished(self, request_id: int, action: str, result, context) -> None:
        if request_id != int(getattr(self, "_preset_item_action_request_id", 0) or 0):
            return
        context = dict(context or {})
        log(str(getattr(result, "log_message", "") or ""), str(getattr(result, "log_level", "") or "INFO"))
        if action == "delete" and str(getattr(result, "error_code", "") or "") == "not_found":
            # Файл уже исчез: синхронизируем локальное состояние списка, не показывая лишнюю ошибку.
            self._runtime_service.recover_missing_deleted_preset(str(context.get("file_name") or ""))
            return
        structure_changed = bool(getattr(result, "structure_changed", False))
        if action == "duplicate" and bool(getattr(result, "ok", False)):
            if self._runtime_service.add_created_preset_locally(
                str(getattr(result, "preset_file_name", "") or ""),
                str(getattr(result, "preset_display_name", "") or ""),
            ):
                structure_changed = False
        if action == "delete" and bool(getattr(result, "ok", False)):
            if self._runtime_service.remove_deleted_preset_locally(str(context.get("file_name") or "")):
                structure_changed = False
        if structure_changed:
            self._runtime_service.mark_presets_structure_changed()
        level = str(getattr(result, "infobar_level", "") or "")
        title = str(getattr(result, "infobar_title", "") or self._tr("common.error.title", "Ошибка"))
        content = str(getattr(result, "infobar_content", "") or "")
        if level == "success":
            InfoBar.success(title=title, content=content, parent=self.window())
        elif level == "warning":
            InfoBar.warning(title=title, content=content, parent=self.window())
        elif level == "error":
            InfoBar.error(title=title, content=content, parent=self.window())

    def _on_preset_item_action_failed(self, request_id: int, action: str, error: str) -> None:
        if request_id != int(getattr(self, "_preset_item_action_request_id", 0) or 0):
            return
        log(f"Ошибка действия preset ({action}): {error}", "ERROR")
        InfoBar.error(
            title=self._tr("common.error.title", "Ошибка"),
            content=self._tr(f"{self._config.tr_prefix}.error.generic", "Ошибка: {error}", error=error),
            parent=self.window(),
        )

    def _on_preset_item_action_worker_finished(self, worker) -> None:
        if not bool(self.__dict__.get("_cleanup_in_progress", False)):
            self._start_next_preset_write_action()

    def create_preset_link_action_worker(self, request_id: int, *, action: str):
        return self._create_preset_link_action_worker_fn(
            request_id,
            action=action,
            parent=self,
        )

    def _request_preset_link_action(self, action: str) -> None:
        action = str(action or "").strip()
        if not action:
            return
        runtime = self._worker_runtime("_preset_link_action_runtime")
        if runtime.is_running() or self.__dict__.get("_preset_link_action_start_scheduled", False):
            self.__dict__.setdefault("_preset_link_action_pending", []).append(action)
            return
        self._preset_link_action_request_id = int(self.__dict__.get("_preset_link_action_request_id", 0) or 0) + 1
        request_id = self._preset_link_action_request_id

        def _bind_worker(worker) -> None:
            worker.completed.connect(self._on_preset_link_action_finished)
            worker.failed.connect(self._on_preset_link_action_failed)

        runtime.start_qthread_worker(
            worker_factory=lambda _runtime_request_id: self.create_preset_link_action_worker(request_id, action=action),
            bind_worker=_bind_worker,
            on_finished=self._on_preset_link_action_worker_finished,
        )

    def _on_preset_link_action_finished(self, request_id: int, _action: str, result, _context) -> None:
        if request_id != int(getattr(self, "_preset_link_action_request_id", 0) or 0):
            return
        log(str(getattr(result, "log_message", "") or ""), str(getattr(result, "log_level", "") or "INFO"))
        if (not bool(getattr(result, "ok", False))) and getattr(result, "infobar_level", "") == "warning":
            InfoBar.warning(
                title=str(getattr(result, "infobar_title", "") or self._tr("common.error.title", "Ошибка")),
                content=str(getattr(result, "infobar_content", "") or ""),
                parent=self.window(),
            )

    def _on_preset_link_action_failed(self, request_id: int, _action: str, error: str, _context) -> None:
        if request_id != int(getattr(self, "_preset_link_action_request_id", 0) or 0):
            return
        log(f"{self.__class__.__name__}: не удалось открыть ссылку preset: {error}", "ERROR")
        InfoBar.warning(
            title=self._tr("common.error.title", "Ошибка"),
            content=str(error),
            parent=self.window(),
        )

    def _on_preset_link_action_worker_finished(self, worker) -> None:
        pending_actions = self.__dict__.setdefault("_preset_link_action_pending", [])
        pending = str(pending_actions.pop(0) if pending_actions else "").strip()
        if pending and not self._cleanup_in_progress:
            self._schedule_preset_link_action_start(pending)

    def _schedule_preset_link_action_start(self, action: str) -> None:
        clean_action = str(action or "").strip()
        self._preset_link_action_start_scheduled = True
        try:
            QTimer.singleShot(0, lambda: self._run_scheduled_preset_link_action_start(clean_action))
        except Exception:
            self._run_scheduled_preset_link_action_start(clean_action)

    def _run_scheduled_preset_link_action_start(self, action: str) -> None:
        self._preset_link_action_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._request_preset_link_action(str(action or "").strip())

    def _open_presets_info(self):
        self._request_preset_link_action("info")

    def _open_new_configs_post(self):
        self._request_preset_link_action("new_configs")

    def _stop_action_workers_for_cleanup(self) -> None:
        self._pending_preset_activation = None
        self._restore_preset_activation_marker_file_name = ""
        self.__dict__.setdefault("_preset_edit_action_pending", []).clear()
        self.__dict__.setdefault("_pending_preset_storage_actions", []).clear()
        self.__dict__.setdefault("_pending_preset_write_actions", []).clear()
        self._preset_write_action_start_scheduled = False
        self._preset_folder_action_pending.clear()
        self._preset_folder_action_start_scheduled = False
        self._preset_open_folder_pending = False
        self._preset_open_folder_start_scheduled = False
        self.__dict__.setdefault("_preset_item_action_pending", []).clear()
        self.__dict__.setdefault("_preset_link_action_pending", []).clear()
        self._preset_link_action_start_scheduled = False
        self.__dict__.setdefault("_preset_bulk_action_pending", []).clear()
        self._preset_bulk_action_kind = ""
        self._bulk_reset_running = False

        for attr in (
            "_preset_activate_request_id",
            "_preset_item_action_request_id",
            "_preset_bulk_action_request_id",
            "_preset_edit_action_request_id",
            "_preset_storage_action_request_id",
            "_preset_folder_action_request_id",
            "_preset_open_folder_request_id",
            "_preset_link_action_request_id",
        ):
            setattr(self, attr, int(getattr(self, attr, 0) or 0) + 1)

        for attr, label in (
            ("_preset_activate_runtime", "preset activate worker"),
            ("_preset_item_action_runtime", "preset item action worker"),
            ("_preset_bulk_action_runtime", "preset bulk action worker"),
            ("_preset_edit_action_runtime", "preset edit action worker"),
            ("_preset_storage_action_runtime", "preset storage action worker"),
            ("_preset_folder_action_runtime", "preset folder action worker"),
            ("_preset_open_folder_runtime", "preset open folder worker"),
            ("_preset_link_action_runtime", "preset link action worker"),
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

    def cleanup(self) -> None:
        self._stop_action_workers_for_cleanup()
        cleanup_user_presets_page(
            set_cleanup_in_progress_fn=lambda value: setattr(self, "_cleanup_in_progress", value),
            layout_resync_timer=self._layout_resync_timer,
            layout_resync_delayed_timer=self._layout_resync_delayed_timer,
            preset_search_timer=self._preset_search_timer,
            current_unsubscribe=self._ui_state_unsubscribe,
            set_unsubscribe_fn=lambda value: setattr(self, "_ui_state_unsubscribe", value),
            set_store_fn=lambda value: setattr(self, "_ui_state_store", value),
            stop_watching_presets_fn=self._runtime_service.stop_watching_presets,
        )

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        apply_user_presets_language(
            tr_fn=self._tr,
            configs_title_label=self._configs_title_label,
            get_configs_btn=self._get_configs_btn,
            create_btn=self.create_btn,
            import_btn=self.import_btn,
            open_folder_btn=self.open_folder_btn,
            reset_all_btn=self.reset_all_btn,
            presets_info_btn=self.presets_info_btn,
            info_btn=self.info_btn,
            preset_search_input=self._preset_search_input,
            presets_delegate=self._presets_delegate,
            ui_language=self._ui_language,
            viewport=self.viewport(),
            layout=self.layout,
            toolbar_layout=getattr(self, "_toolbar_layout", None),
            refresh_presets_view_from_cache_fn=self._refresh_presets_view_from_cache,
            apply_mode_labels_fn=self._apply_mode_labels,
            tr_prefix=self._config.tr_prefix,
        )


__all__ = ["UserPresetsPageBase", "UserPresetsPageConfig"]
