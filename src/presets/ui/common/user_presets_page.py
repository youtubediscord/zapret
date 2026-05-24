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
)
from ui.pages.base_page import BasePage
from presets.ui.common.preset_actions_menu import show_preset_actions_menu
from presets.ui.common.preset_rating_menu import show_preset_rating_menu
from presets.folders import delete_preset_item_meta
from presets.user_presets_runtime_service import (
    UserPresetsRuntimeAdapter,
    UserPresetsRuntimeService,
)
from presets.ui.common.user_presets_page_runtime import (
    UserPresetsPageRuntime,
    UserPresetsPageRuntimeConfig,
    apply_preset_content_reload,
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
    PresetStatusBar,
    build_runtime_preset_status_plan,
)
from presets.ui.common.user_presets_actions_workflow import (
    import_preset_action,
    restore_reset_all_button_label,
    run_reset_all_presets_action,
    show_inline_action_create,
    show_inline_action_rename,
    show_reset_all_result,
)
from presets.ui.common.user_presets_item_actions_workflow import (
    activate_preset_action,
    delete_preset_action,
    duplicate_preset_action,
    export_preset_action,
    handle_item_dropped_action,
    move_preset_by_step_action,
    open_edit_preset_menu_action,
    open_new_configs_post_action,
    open_presets_info_action,
    rename_preset_action,
    reset_preset_action,
    show_rating_menu_action,
    toggle_pin_preset_action,
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
        runtime_feature,
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
        self._runtime_feature = runtime_feature
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
        self._preset_status_bar = None

        self._ui_state_store: Optional[MainWindowStateStore] = None
        self._ui_state_unsubscribe = None
        self._cleanup_in_progress = False
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
        bar = self._preset_status_bar
        if bar is None:
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
        bar.set_plan(plan)

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
        self._preset_status_bar = PresetStatusBar(self)
        self._toolbar_layout.set_inline_widget(self._preset_status_bar, minimum_width=160)
        self._toolbar_layout.refresh_for_viewport(self.viewport().width(), self.layout.contentsMargins())

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

    def _update_presets_view_height(self):
        update_presets_view_height(
            presets_model=self._presets_model,
            presets_list=getattr(self, "presets_list", None),
            viewport=self.viewport(),
            layout=self.layout,
        )

    def _show_inline_action_create(self):
        show_inline_action_create(
            dialog_cls=self._config.create_dialog_cls,
            parent_window=self.window(),
            language=self._ui_language,
            actions_api=self._actions_api(),
            runtime_service=self._runtime_service,
            log_fn=log,
            info_bar_cls=InfoBar,
            tr_fn=self._tr,
            tr_prefix=self._config.tr_prefix,
        )

    def _show_inline_action_rename(self, current_name: str):
        show_inline_action_rename(
            current_name=current_name,
            resolve_display_name_fn=self._resolve_display_name,
            is_builtin_preset_file_fn=self._is_builtin_preset_file,
            dialog_cls=self._config.rename_dialog_cls,
            parent_window=self.window(),
            language=self._ui_language,
            actions_api=self._actions_api(),
            runtime_service=self._runtime_service,
            log_fn=log,
            info_bar_cls=InfoBar,
            tr_fn=self._tr,
            tr_prefix=self._config.tr_prefix,
        )

    def _on_create_clicked(self):
        self._show_inline_action_create()

    def _on_import_clicked(self):
        import_preset_action(
            file_dialog_cls=QFileDialog,
            parent=self,
            parent_window=self.window(),
            tr_fn=self._tr,
            actions_api=self._actions_api(),
            runtime_service=self._runtime_service,
            log_fn=log,
            info_bar_cls=InfoBar,
            tr_prefix=self._config.tr_prefix,
        )

    def _on_reset_all_presets_clicked(self):
        run_reset_all_presets_action(
            dialog_cls=self._config.reset_all_dialog_cls,
            parent_window=self.window(),
            language=self._ui_language,
            actions_api=self._actions_api(),
            runtime_service=self._runtime_service,
            log_fn=log,
            info_bar_cls=InfoBar,
            tr_fn=self._tr,
            show_result_fn=self._show_reset_all_result,
            is_visible=self.isVisible(),
            refresh_view_fn=self.refresh_presets_view_if_possible,
            set_bulk_reset_running_fn=lambda value: setattr(self, "_bulk_reset_running", value),
            tr_prefix=self._config.tr_prefix,
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
        toggle_pin_preset_action(
            name=name,
            resolve_display_name_fn=self._resolve_display_name,
            storage_api=self._storage_api(),
            refresh_presets_view_from_cache_fn=self._refresh_presets_view_from_cache,
            log_fn=log,
        )

    def _on_rate_preset(self, name: str):
        self._show_rating_menu(name)

    def _move_preset_by_step(self, name: str, direction: int):
        move_preset_by_step_action(
            name=name,
            direction=direction,
            storage_api=self._storage_api(),
            runtime_service=self._runtime_service,
            refresh_presets_view_from_cache_fn=self._refresh_presets_view_from_cache,
            log_fn=log,
        )

    def _on_item_dropped(self, source_kind: str, source_id: str, destination_kind: str, destination_id: str):
        handle_item_dropped_action(
            source_kind=source_kind,
            source_id=source_id,
            destination_kind=destination_kind,
            destination_id=destination_id,
            storage_api=self._storage_api(),
            refresh_presets_view_from_cache_fn=self._refresh_presets_view_from_cache,
            log_fn=log,
        )

    def _on_activate_preset(self, name: str) -> bool:
        return activate_preset_action(
            name=name,
            resolve_display_name_fn=self._resolve_display_name,
            actions_api=self._actions_api(),
            runtime_service=self._runtime_service,
            info_bar_cls=InfoBar,
            tr_fn=self._tr,
            parent_window=self.window(),
            log_fn=log,
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
        duplicate_preset_action(
            name=name,
            resolve_display_name_fn=self._resolve_display_name,
            actions_api=self._actions_api(),
            runtime_service=self._runtime_service,
            info_bar_cls=InfoBar,
            tr_fn=self._tr,
            parent_window=self.window(),
            log_fn=log,
            tr_prefix=self._config.tr_prefix,
        )

    def _on_reset_preset(self, name: str):
        reset_preset_action(
            name=name,
            resolve_display_name_fn=self._resolve_display_name,
            actions_api=self._actions_api(),
            message_box_cls=MessageBox,
            info_bar_cls=InfoBar,
            tr_fn=self._tr,
            parent_window=self.window(),
            log_fn=log,
            tr_prefix=self._config.tr_prefix,
        )

    def _on_delete_preset(self, name: str):
        delete_preset_action(
            name=name,
            resolve_display_name_fn=self._resolve_display_name,
            storage_api=self._storage_api(),
            actions_api=self._actions_api(),
            runtime_service=self._runtime_service,
            message_box_cls=MessageBox,
            info_bar_cls=InfoBar,
            tr_fn=self._tr,
            parent_window=self.window(),
            log_fn=log,
            tr_prefix=self._config.tr_prefix,
        )

    def _on_export_preset(self, name: str):
        export_preset_action(
            page=self,
            name=name,
            resolve_display_name_fn=self._resolve_display_name,
            file_dialog_cls=QFileDialog,
            actions_api=self._actions_api(),
            info_bar_cls=InfoBar,
            tr_fn=self._tr,
            parent_window=self.window(),
            log_fn=log,
            tr_prefix=self._config.tr_prefix,
        )

    def _on_dpi_reload_needed(self):
        apply_preset_content_reload(
            runtime_feature=self._runtime_feature,
            launch_method=self._config.launch_method,
            reason="preset_content_changed",
            log_fn=log,
        )

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
