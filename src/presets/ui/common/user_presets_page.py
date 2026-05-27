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
from presets.folders import delete_preset_item_meta
from presets.user_presets_runtime_service import (
    UserPresetsRuntimeAdapter,
    UserPresetsRuntimeService,
)
from presets.user_presets_action_workers import (
    UserPresetActivateWorker,
    UserPresetBulkActionWorker,
    UserPresetEditActionWorker,
    UserPresetItemActionWorker,
    UserPresetStorageActionWorker,
)
from presets.ui.common.user_presets_page_runtime import (
    UserPresetsPageRuntime,
    UserPresetsPageRuntimeConfig,
    apply_preset_search,
    rebuild_presets_rows,
    schedule_preset_search,
    update_presets_view_height,
)
from presets.ui.common.user_presets_page_actions import open_presets_folder_action
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
    open_new_configs_post_action,
    open_presets_info_action,
    rename_preset_action,
    show_rating_menu_action,
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
        presets_feature,
        open_preset_raw_editor,
        external_actions_feature,
        ui_state_store,
    ):
        self._config = self.page_config
        super().__init__(
            "Мои пресеты",
            "",
            parent,
            title_key=self._config.title_key,
        )
        self._presets_feature = presets_feature
        self._external_actions = external_actions_feature
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
        self._preset_activate_worker = None
        self._preset_activate_request_id = 0
        self._pending_preset_activation: tuple[str, str] | None = None
        self._preset_item_action_worker = None
        self._preset_item_action_request_id = 0
        self._preset_bulk_action_worker = None
        self._preset_bulk_action_request_id = 0
        self._preset_bulk_action_kind = ""
        self._preset_edit_action_worker = None
        self._preset_edit_action_request_id = 0
        self._preset_storage_action_worker = None
        self._preset_storage_action_request_id = 0
        self._build_ui()
        self._after_ui_built()
        self.bind_ui_state_store(ui_state_store)

    def _tr(self, key: str, default: str, **kwargs) -> str:
        return _tr_text(key, self._ui_language, default, **kwargs)

    def _resolve_presets_feature(self):
        return self._presets_feature

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
                get_presets_feature=self._resolve_presets_feature,
                open_url=self._external_actions.open_url,
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
            rebuild_rows=lambda all_presets, started_at=None: self._rebuild_presets_rows(
                all_presets,
                started_at=started_at,
            ),
            delete_preset_item_meta=lambda name: delete_preset_item_meta(self._folder_scope_key(), name),
        )

    def _apply_mode_labels(self) -> None:
        try:
            self.title_label.setText(self._tr(self._config.title_key, "Мои пресеты"))
            if self.subtitle_label is not None:
                self.subtitle_label.setText("")
        except Exception:
            pass

    def _page_runtime_api(self):
        return self._page_api

    def _listing_api(self):
        return self._page_runtime_api().listing

    def _actions_api(self):
        return self._page_runtime_api().actions

    def _storage_api(self):
        return self._page_runtime_api().storage

    def _get_selected_source_preset_file_name_light(self) -> str:
        return self._listing_api().get_selected_source_preset_file_name_light()

    def _resolve_display_name(self, reference: str) -> str:
        return self._listing_api().resolve_display_name(reference)

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
        return self._storage_api().is_builtin_preset_file_with_cache(
            name,
            self._runtime_service.cached_presets_metadata(),
        )

    def _folder_scope_key(self) -> str:
        return self._config.folder_scope

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
            connect_preset_signals_fn=lambda **callbacks: self._presets.connect_preset_signals(
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
            from settings.appearance import load_smooth_scroll_enabled
            smooth_enabled = load_smooth_scroll_enabled().enabled
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
        open_presets_folder_action(
            open_presets_folder_fn=lambda: self._presets.open_user_presets_folder(self.launch_method),
            info_bar_cls=InfoBar,
            tr_fn=self._tr,
            parent_window=self.window(),
            error_key=f"{self._config.tr_prefix}.error.open_folder",
            error_default="Не удалось открыть папку пресетов: {error}",
            log_prefix=self._config.log_prefix,
            log_fn=log,
        )

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
                if str(search_input.text() or "") != query:
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
        return UserPresetEditActionWorker(
            request_id,
            self._actions_api(),
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
        worker = self.__dict__.get("_preset_edit_action_worker")
        if worker is not None:
            try:
                if worker.isRunning():
                    return
            except Exception:
                return
        self._preset_edit_action_request_id = int(getattr(self, "_preset_edit_action_request_id", 0) or 0) + 1
        request_id = self._preset_edit_action_request_id
        worker = self.create_preset_edit_action_worker(
            request_id,
            action=str(action or ""),
            name=str(name or ""),
            current_name=str(current_name or ""),
            new_name=str(new_name or ""),
            from_current=bool(from_current),
        )
        self._preset_edit_action_worker = worker
        worker.completed.connect(self._on_preset_edit_action_finished)
        worker.failed.connect(self._on_preset_edit_action_failed)
        worker.finished.connect(lambda w=worker: self._on_preset_edit_action_worker_finished(w))
        worker.start()

    def _on_preset_edit_action_finished(self, request_id: int, _action: str, result, _context) -> None:
        if request_id != int(getattr(self, "_preset_edit_action_request_id", 0) or 0):
            return
        if bool(getattr(result, "structure_changed", False)):
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
        if self.__dict__.get("_preset_edit_action_worker") is worker:
            self._preset_edit_action_worker = None
        worker.deleteLater()

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
        return UserPresetBulkActionWorker(
            request_id,
            self._actions_api(),
            action=action,
            file_path=file_path,
            parent=self,
        )

    def _request_preset_bulk_action(self, action: str, *, file_path: str = "") -> bool:
        worker = self.__dict__.get("_preset_bulk_action_worker")
        if worker is not None:
            try:
                if worker.isRunning():
                    return False
            except Exception:
                return False
        self._preset_bulk_action_request_id = int(getattr(self, "_preset_bulk_action_request_id", 0) or 0) + 1
        request_id = self._preset_bulk_action_request_id
        self._preset_bulk_action_kind = str(action or "")
        worker = self.create_preset_bulk_action_worker(
            request_id,
            action=str(action or ""),
            file_path=str(file_path or ""),
        )
        self._preset_bulk_action_worker = worker
        worker.completed.connect(self._on_preset_bulk_action_finished)
        worker.failed.connect(self._on_preset_bulk_action_failed)
        worker.finished.connect(lambda w=worker: self._on_preset_bulk_action_worker_finished(w))
        worker.start()
        return True

    def _on_preset_bulk_action_finished(self, request_id: int, action: str, result, _context) -> None:
        if request_id != int(getattr(self, "_preset_bulk_action_request_id", 0) or 0):
            return
        log(str(getattr(result, "log_message", "") or ""), str(getattr(result, "log_level", "") or "INFO"))
        if bool(getattr(result, "structure_changed", False)):
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
        if self.__dict__.get("_preset_bulk_action_worker") is worker:
            self._preset_bulk_action_worker = None
            self._preset_bulk_action_kind = ""
        worker.deleteLater()
        if action == "reset_all":
            self._bulk_reset_running = False
            if self._runtime_service.is_ui_dirty() and self.isVisible():
                self.refresh_presets_view_if_possible()

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

    def _rebuild_presets_rows(self, all_presets: dict[str, dict[str, object]], *, started_at: float | None = None) -> None:
        rebuild_presets_rows(
            runtime_service=self._runtime_service,
            listing_api=self._listing_api(),
            presets_delegate=self._presets_delegate,
            presets_model=self._presets_model,
            presets_list=getattr(self, "presets_list", None),
            get_selected_source_preset_file_name_light_fn=self._get_selected_source_preset_file_name_light,
            ui_language=self._ui_language,
            schedule_layout_resync_fn=self._schedule_layout_resync,
            update_presets_view_height_fn=self._update_presets_view_height,
            log_fn=log,
            all_presets=all_presets,
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
        try:
            from presets.folders import load_preset_folder_state, set_preset_folder_collapsed

            state = load_preset_folder_state(self._folder_scope_key())
            folder = state.get("folders", {}).get(str(folder_key or "").strip())
            if not isinstance(folder, dict) and str(folder_key or "").strip() != "pinned":
                return
            set_preset_folder_collapsed(
                self._folder_scope_key(),
                folder_key,
                not bool(folder.get("collapsed", False)) if isinstance(folder, dict) else True,
            )
            self._refresh_presets_view_from_cache()
        except Exception as exc:
            log(f"{self.__class__.__name__}: не удалось свернуть папку preset-ов: {exc}", "ERROR")

    def _open_preset_subpage(self, name: str):
        self._open_preset_raw_editor_callback(name)

    def _on_preset_context_requested(self, name: str, global_pos: QPoint):
        self._on_edit_preset(name, global_pos=global_pos)

    def _on_folder_context_requested(self, folder_key: str, global_pos: QPoint):
        self._show_folder_menu(folder_key, global_pos)

    def _on_folder_background_context_requested(self, global_pos: QPoint):
        self._show_folder_menu("", global_pos)

    def _show_folder_menu(self, folder_key: str, global_pos: QPoint):
        show_preset_folder_menu(
            parent=self,
            scope_key=self._folder_scope_key(),
            folder_key=folder_key,
            global_pos=global_pos,
            refresh_fn=self._refresh_presets_view_from_cache,
            log_fn=log,
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
        direction: int = 0,
        cached_metadata=None,
        source_kind: str = "",
        source_id: str = "",
        destination_kind: str = "",
        destination_id: str = "",
        destination_folder_key: str = "",
    ):
        return UserPresetStorageActionWorker(
            request_id,
            self._storage_api(),
            action=action,
            name=name,
            display_name=display_name,
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
        direction: int = 0,
        cached_metadata=None,
        source_kind: str = "",
        source_id: str = "",
        destination_kind: str = "",
        destination_id: str = "",
        destination_folder_key: str = "",
    ) -> None:
        worker = self.__dict__.get("_preset_storage_action_worker")
        if worker is not None:
            try:
                if worker.isRunning():
                    return
            except Exception:
                return
        self._preset_storage_action_request_id = int(getattr(self, "_preset_storage_action_request_id", 0) or 0) + 1
        request_id = self._preset_storage_action_request_id
        worker = self.create_preset_storage_action_worker(
            request_id,
            action=str(action or ""),
            name=str(name or ""),
            display_name=str(display_name or ""),
            direction=int(direction or 0),
            cached_metadata=cached_metadata,
            source_kind=str(source_kind or ""),
            source_id=str(source_id or ""),
            destination_kind=str(destination_kind or ""),
            destination_id=str(destination_id or ""),
            destination_folder_key=str(destination_folder_key or ""),
        )
        self._preset_storage_action_worker = worker
        worker.completed.connect(self._on_preset_storage_action_finished)
        worker.failed.connect(self._on_preset_storage_action_failed)
        worker.finished.connect(lambda w=worker: self._on_preset_storage_action_worker_finished(w))
        worker.start()

    def _on_preset_storage_action_finished(self, request_id: int, action: str, result, context) -> None:
        if request_id != int(getattr(self, "_preset_storage_action_request_id", 0) or 0):
            return
        context = dict(context or {})
        if action == "pin":
            display_name = str(context.get("display_name") or context.get("name") or "")
            log(f"Пресет '{display_name}' {'закреплён' if bool(result) else 'откреплён'}", "INFO")
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
        if self.__dict__.get("_preset_storage_action_worker") is worker:
            self._preset_storage_action_worker = None
        worker.deleteLater()

    def _on_activate_preset(self, name: str) -> bool:
        preset_file_name = str(name or "").strip()
        if not preset_file_name:
            return False
        display_name = self._resolve_display_name(preset_file_name) or preset_file_name
        self._runtime_service.apply_active_preset_marker_for_file(preset_file_name)
        self._request_preset_activation(preset_file_name, display_name)
        return True

    def create_preset_activate_worker(self, request_id: int, *, file_name: str, display_name: str):
        return UserPresetActivateWorker(
            request_id,
            self._actions_api(),
            file_name=file_name,
            display_name=display_name,
            parent=self,
        )

    def _request_preset_activation(self, file_name: str, display_name: str) -> None:
        worker = self.__dict__.get("_preset_activate_worker")
        if worker is not None:
            try:
                if worker.isRunning():
                    self._pending_preset_activation = (str(file_name or "").strip(), str(display_name or "").strip())
                    return
            except Exception:
                return
        self._preset_activate_request_id = int(getattr(self, "_preset_activate_request_id", 0) or 0) + 1
        request_id = self._preset_activate_request_id
        worker = self.create_preset_activate_worker(
            request_id,
            file_name=file_name,
            display_name=display_name,
        )
        self._preset_activate_worker = worker
        worker.activated.connect(self._on_preset_activation_finished)
        worker.failed.connect(self._on_preset_activation_failed)
        worker.finished.connect(lambda w=worker: self._on_preset_activate_worker_finished(w))
        worker.start()

    def _on_preset_activation_finished(self, request_id: int, result) -> None:
        if request_id != int(getattr(self, "_preset_activate_request_id", 0) or 0):
            return
        if self.__dict__.get("_pending_preset_activation"):
            return
        log(str(getattr(result, "log_message", "") or ""), str(getattr(result, "log_level", "") or "INFO"))
        if bool(getattr(result, "ok", False)) and getattr(result, "activated_file_name", None):
            self._runtime_service.apply_active_preset_marker_for_file(str(result.activated_file_name))
            return
        if str(getattr(result, "infobar_level", "") or "") == "error":
            InfoBar.error(
                title=str(getattr(result, "infobar_title", "") or self._tr("common.error.title", "Ошибка")),
                content=str(getattr(result, "infobar_content", "") or ""),
                parent=self.window(),
            )
        self._refresh_presets_view_from_cache()

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
        self._refresh_presets_view_from_cache()

    def _on_preset_activate_worker_finished(self, worker) -> None:
        if self.__dict__.get("_preset_activate_worker") is worker:
            self._preset_activate_worker = None
        worker.deleteLater()
        pending = self.__dict__.get("_pending_preset_activation")
        self._pending_preset_activation = None
        if pending:
            self._request_preset_activation(pending[0], pending[1])

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
        current = str(self._get_selected_source_preset_file_name_light() or "").strip().lower()
        candidate = str(name or "").strip().lower()
        return bool(current and candidate and current == candidate)

    def _show_rating_menu(self, name: str, global_pos: QPoint | None = None):
        show_rating_menu_action(
            page=self,
            name=name,
            global_pos=global_pos,
            resolve_display_name_fn=self._resolve_display_name,
            folder_scope=self._folder_scope_key(),
            refresh_callback=lambda: self._refresh_presets_view_from_cache(),
            tr_fn=self._tr,
            show_preset_rating_menu_fn=show_preset_rating_menu,
            tr_prefix=self._config.tr_prefix,
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
        if not self._storage_api().is_builtin_preset_file(name) and MessageBox:
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
        return UserPresetItemActionWorker(
            request_id,
            self._actions_api(),
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
        worker = self.__dict__.get("_preset_item_action_worker")
        if worker is not None:
            try:
                if worker.isRunning():
                    return
            except Exception:
                return
        self._preset_item_action_request_id = int(getattr(self, "_preset_item_action_request_id", 0) or 0) + 1
        request_id = self._preset_item_action_request_id
        worker = self.create_preset_item_action_worker(
            request_id,
            action=str(action or ""),
            file_name=str(file_name or ""),
            display_name=str(display_name or ""),
            file_path=str(file_path or ""),
        )
        self._preset_item_action_worker = worker
        worker.completed.connect(self._on_preset_item_action_finished)
        worker.failed.connect(self._on_preset_item_action_failed)
        worker.finished.connect(lambda w=worker: self._on_preset_item_action_worker_finished(w))
        worker.start()

    def _on_preset_item_action_finished(self, request_id: int, action: str, result, context) -> None:
        if request_id != int(getattr(self, "_preset_item_action_request_id", 0) or 0):
            return
        context = dict(context or {})
        log(str(getattr(result, "log_message", "") or ""), str(getattr(result, "log_level", "") or "INFO"))
        if action == "delete" and str(getattr(result, "error_code", "") or "") == "not_found":
            # Файл уже исчез: синхронизируем локальное состояние списка, не показывая лишнюю ошибку.
            self._runtime_service.recover_missing_deleted_preset(str(context.get("file_name") or ""))
            return
        if bool(getattr(result, "structure_changed", False)):
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
        if self.__dict__.get("_preset_item_action_worker") is worker:
            self._preset_item_action_worker = None
        worker.deleteLater()

    def _open_presets_info(self):
        open_presets_info_action(
            actions_api=self._actions_api(),
            info_bar_cls=InfoBar,
            tr_fn=self._tr,
            parent_window=self.window(),
            log_fn=log,
        )

    def _open_new_configs_post(self):
        open_new_configs_post_action(
            actions_api=self._actions_api(),
            info_bar_cls=InfoBar,
            tr_fn=self._tr,
            parent_window=self.window(),
            log_fn=log,
        )

    def cleanup(self) -> None:
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
