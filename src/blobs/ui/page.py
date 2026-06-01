# blobs/ui/page.py
"""Страница управления блобами (Zapret 2 / Direct режим)"""

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QLabel
)

from ui.pages.base_page import BasePage
from ui.one_shot_worker_runtime import OneShotWorkerRuntime
from blobs.ui.build import build_blobs_page_header
from blobs.ui.components import BlobItemWidget
from blobs.ui.runtime_helpers import (
    add_blob_via_dialog,
    apply_blobs_language,
    delete_blob_named,
    filter_blobs_in_ui,
    load_blobs_into_ui,
)
from ui.fluent_widgets import (
    QuickActionsBar,
    RefreshButton,
)
from ui.theme import get_cached_qta_pixmap, get_theme_tokens
from app.ui_texts import tr as tr_catalog
from log.log import log
from qfluentwidgets import LineEdit, MessageBox, InfoBar, PrimaryPushButton, PushButton, SettingCardGroup


class BlobsPage(BasePage):
    """Страница управления блобами"""

    def __init__(self, parent=None, *, blobs_feature, open_control):
        super().__init__(
            "Блобы",
            "Управление бинарными данными для стратегий",
            parent,
            title_key="page.blobs.title",
            subtitle_key="page.blobs.subtitle",
        )

        self._blobs = blobs_feature
        self._open_control_callback = open_control
        self._desc_label = None
        self._filter_icon_label = None
        self._runtime_initialized = False
        self._cleanup_in_progress = False
        self._actions_group = None
        self._actions_meta_card = None
        self._actions_bar = None
        self._blobs_load_runtime = OneShotWorkerRuntime()
        self._blobs_load_pending = False
        self._blobs_load_pending_reload = False
        self._blobs_load_start_scheduled = False
        self._blob_action_runtime = OneShotWorkerRuntime()
        self._blob_action_pending: list[dict[str, str]] = []
        self._blob_action_start_scheduled = False
        self._blob_open_action_runtime = OneShotWorkerRuntime()
        self._blob_open_action_pending: list[str] = []
        self._blob_open_action_start_scheduled = False

        self._build_ui()
        self._apply_page_theme(force=True)

    def _run_runtime_init_once(self) -> None:
        if self._runtime_initialized:
            return
        self._runtime_initialized = True
        QTimer.singleShot(0, lambda: (not self._cleanup_in_progress) and self._load_blobs())

    def on_page_activated(self) -> None:
        self._run_runtime_init_once()

    def _tr(self, key: str, default: str, **kwargs) -> str:
        text = tr_catalog(key, language=self._ui_language, default=default)
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def _build_ui(self):
        """Строит UI страницы"""
        widgets = build_blobs_page_header(
            page=self,
            setting_card_group_cls=SettingCardGroup,
            line_edit_cls=LineEdit,
            action_button_cls=PushButton,
            primary_action_button_cls=PrimaryPushButton,
            quick_actions_bar_cls=QuickActionsBar,
            refresh_button_cls=RefreshButton,
            add_widget=self.add_widget,
            tr_fn=self._tr,
            on_back=self._open_control_callback,
            on_add_blob=self._add_blob,
            on_reload_blobs=self._reload_blobs,
            on_open_bin_folder=self._open_bin_folder,
            on_open_json=self._open_json,
            on_filter_blobs=self._filter_blobs,
        )
        self._breadcrumb = widgets.breadcrumb
        self._desc_label = widgets.desc_label
        self._actions_group = widgets.actions_group
        self._actions_meta_card = widgets.actions_meta_card
        self._actions_bar = widgets.actions_bar
        self.add_btn = widgets.add_btn
        self.reload_btn = widgets.reload_btn
        self.open_folder_btn = widgets.open_folder_btn
        self.open_json_btn = widgets.open_json_btn
        self.count_label = widgets.count_label
        self._filter_icon_label = widgets.filter_icon_label
        self.filter_edit = widgets.filter_edit
        self.blobs_container = widgets.blobs_container
        self.blobs_layout = widgets.blobs_layout
        
    def _apply_page_theme(self, tokens=None, force: bool = False) -> None:
        _ = force
        tokens = tokens or get_theme_tokens()

        if self._desc_label is not None:
            self._desc_label.setStyleSheet(
                f"color: {tokens.fg_muted}; font-size: 13px;"
            )

        if hasattr(self, "count_label") and self.count_label is not None:
            self.count_label.setStyleSheet(
                f"color: {tokens.fg_faint}; font-size: 11px; padding-top: 4px;"
            )

        if self._filter_icon_label is not None:
            self._filter_icon_label.setPixmap(
                get_cached_qta_pixmap('fa5s.search', color=tokens.fg_faint, size=14)
            )

        # filter_edit is a qfluentwidgets LineEdit — it styles itself.

        # Update section headers + blob items.
        if hasattr(self, "blobs_layout") and self.blobs_layout is not None:
            for i in range(self.blobs_layout.count()):
                item = self.blobs_layout.itemAt(i)
                w = item.widget() if item else None
                if w is None:
                    continue
                if isinstance(w, BlobItemWidget):
                    try:
                        w.refresh_theme()
                    except Exception:
                        pass
                elif isinstance(w, QLabel):
                    section = w.property("blobSection")
                    if section == "user":
                        w.setStyleSheet(
                            "color: #ffc107; font-size: 12px; font-weight: 600; padding: 8px 4px 4px 4px;"
                        )
                    elif section == "system":
                        w.setStyleSheet(
                            f"color: {tokens.fg_faint}; font-size: 12px; font-weight: 600; padding: 12px 4px 4px 4px;"
                        )
                    elif section == "error":
                        w.setStyleSheet("color: #ff6b6b; font-size: 13px;")
        
    def _load_blobs(self):
        """Загружает и отображает список блобов"""
        self._request_blobs_load(reload=False)

    def create_blobs_load_worker(self, request_id: int, *, reload: bool = False):
        return self._blobs.create_blobs_load_worker(
            request_id,
            reload=bool(reload),
            parent=self,
        )

    def _request_blobs_load(self, *, reload: bool = False) -> None:
        if self._cleanup_in_progress:
            return
        if reload and hasattr(self, "reload_btn"):
            self.reload_btn.set_loading(True)
        if self._blobs_load_runtime.is_running() or self.__dict__.get("_blobs_load_start_scheduled", False):
            self._blobs_load_pending = True
            self._blobs_load_pending_reload = bool(self._blobs_load_pending_reload) or bool(reload)
            return
        self._start_blobs_load_worker(reload=bool(reload))

    def _start_blobs_load_worker(self, *, reload: bool = False) -> None:
        self._blobs_load_pending = False
        self._blobs_load_pending_reload = False
        self._blobs_load_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_blobs_load_worker(
                request_id,
                reload=bool(reload),
            ),
            on_loaded=self._on_blobs_loaded,
            on_failed=self._on_blobs_load_failed,
            on_finished=self._on_blobs_load_worker_finished,
        )

    def _on_blobs_loaded(self, request_id: int, blobs_info: dict, reloaded: bool) -> None:
        if not self._blobs_load_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        load_blobs_into_ui(
            cleanup_in_progress=self._cleanup_in_progress,
            blobs_layout=self.blobs_layout,
            blobs_info=blobs_info,
            ui_language=self._ui_language,
            tr_fn=self._tr,
            on_delete_blob=self._delete_blob,
            count_label=self.count_label,
            apply_page_theme=self._apply_page_theme,
            log_error=lambda text: log(text, "ERROR"),
            log_debug=lambda text: log(text, "DEBUG"),
        )
        if reloaded:
            log("Блобы перезагружены", "INFO")

    def _on_blobs_load_failed(self, request_id: int, error: str, _reload: bool) -> None:
        if not self._blobs_load_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        log(f"Ошибка загрузки блобов: {error}", "ERROR")
        try:
            from blobs.ui.runtime_helpers import clear_blobs_layout

            clear_blobs_layout(self.blobs_layout)
            error_label = QLabel(self._tr("page.blobs.error.load", "❌ Ошибка загрузки: {error}", error=error))
            error_label.setProperty("blobSection", "error")
            self.blobs_layout.addWidget(error_label)
            self._apply_page_theme(force=True)
        except Exception:
            pass

    def _on_blobs_load_worker_finished(self, _worker) -> None:
        if hasattr(self, "reload_btn"):
            self.reload_btn.set_loading(False)
        if self._blobs_load_pending and not self._cleanup_in_progress:
            self._schedule_blobs_load_worker_start()

    def _schedule_blobs_load_worker_start(self) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_blobs_load_start_scheduled", False):
            return
        self._blobs_load_start_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_blobs_load_worker_start)

    def _run_scheduled_blobs_load_worker_start(self) -> None:
        self._blobs_load_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        if not self.__dict__.get("_blobs_load_pending", False):
            return
        reload = bool(self.__dict__.get("_blobs_load_pending_reload", False))
        self._blobs_load_pending = False
        self._blobs_load_pending_reload = False
        self._start_blobs_load_worker(reload=bool(reload))
            
    def _filter_blobs(self, text: str):
        """Фильтрует блобы по тексту"""
        filter_blobs_in_ui(
            cleanup_in_progress=self._cleanup_in_progress,
            blobs_layout=self.blobs_layout,
            text=text,
        )
                    
    def _add_blob(self):
        """Открывает диалог добавления блоба"""
        add_blob_via_dialog(
            window=self.window(),
            ui_language=self._ui_language,
            reload_callback=self._load_blobs,
            tr_fn=self._tr,
            info_bar_cls=InfoBar,
            get_bin_folder_fn=self._blobs.get_bin_folder,
            request_blob_action_fn=self._request_blob_action,
            log_info=lambda text: log(text, "INFO"),
            log_error=lambda text: log(text, "ERROR"),
        )
                
    def _delete_blob(self, name: str):
        """Удаляет пользовательский блоб"""
        delete_blob_named(
            name=name,
            reload_callback=self._load_blobs,
            tr_fn=self._tr,
            info_bar_cls=InfoBar,
            request_blob_action_fn=self._request_blob_action,
            window=self.window(),
            log_info=lambda text: log(text, "INFO"),
            log_error=lambda text: log(text, "ERROR"),
        )

    def create_blob_action_worker(
        self,
        request_id: int,
        *,
        action: str,
        name: str = "",
        blob_type: str = "",
        value: str = "",
        description: str = "",
    ):
        return self._blobs.create_blob_action_worker(
            request_id,
            action=action,
            name=name,
            blob_type=blob_type,
            value=value,
            description=description,
            parent=self,
        )

    def _request_blob_action(
        self,
        action: str,
        *,
        name: str = "",
        blob_type: str = "",
        value: str = "",
        description: str = "",
    ) -> None:
        payload = {
            "action": str(action or "").strip(),
            "name": str(name or "").strip(),
            "blob_type": str(blob_type or "").strip(),
            "value": str(value or ""),
            "description": str(description or ""),
        }
        if self._blob_action_runtime.is_running() or self.__dict__.get("_blob_action_start_scheduled", False):
            self._blob_action_pending.append(payload)
            return
        self._start_blob_action_worker(payload)

    def _start_blob_action_worker(self, payload: dict[str, str]) -> None:
        self._blob_action_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_blob_action_worker(
                request_id,
                action=payload.get("action", ""),
                name=payload.get("name", ""),
                blob_type=payload.get("blob_type", ""),
                value=payload.get("value", ""),
                description=payload.get("description", ""),
            ),
            on_failed=self._on_blob_action_failed,
            on_finished=self._on_blob_action_worker_finished,
            bind_worker=self._bind_blob_action_worker,
        )

    def _bind_blob_action_worker(self, worker) -> None:
        worker.completed.connect(self._on_blob_action_finished)

    def _on_blob_action_finished(self, request_id: int, action: str, result: bool, context) -> None:
        if not self._blob_action_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        context = dict(context or {})
        name = str(context.get("name") or "")
        if bool(result):
            if action == "save":
                log(f"Добавлен блоб: {name}", "INFO")
            elif action == "delete":
                log(f"Удалён блоб: {name}", "INFO")
            self._request_blobs_load(reload=False)
            return

        if action == "delete":
            content = self._tr("page.blobs.error.delete_named", "Не удалось удалить блоб '{name}'", name=name)
        else:
            content = self._tr("page.blobs.error.save", "Не удалось сохранить блоб")
        InfoBar.warning(
            title=self._tr("common.error.title", "Ошибка"),
            content=content,
            parent=self.window(),
        )

    def _on_blob_action_failed(self, request_id: int, action: str, error: str, context) -> None:
        if not self._blob_action_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        log(f"Ошибка действия blob ({action}): {error}", "ERROR")
        name = str((dict(context or {})).get("name") or "")
        content = (
            self._tr("page.blobs.error.delete", "Не удалось удалить блоб: {error}", error=error)
            if action == "delete"
            else self._tr("page.blobs.error.add", "Не удалось добавить блоб: {error}", error=error)
        )
        if name and action == "delete":
            content = self._tr("page.blobs.error.delete_named", "Не удалось удалить блоб '{name}'", name=name)
        InfoBar.warning(
            title=self._tr("common.error.title", "Ошибка"),
            content=content,
            parent=self.window(),
        )

    def _on_blob_action_worker_finished(self, _worker) -> None:
        if self._blob_action_pending and not self._cleanup_in_progress:
            pending = self._blob_action_pending.pop(0)
            self._schedule_blob_action_worker_start(pending)

    def _schedule_blob_action_worker_start(self, payload: dict[str, str]) -> None:
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        queued = dict(payload or {})
        if self.__dict__.get("_blob_action_start_scheduled", False):
            self._blob_action_pending.append(queued)
            return
        self._blob_action_start_scheduled = True
        QTimer.singleShot(0, lambda value=queued: self._run_scheduled_blob_action_worker_start(value))

    def _run_scheduled_blob_action_worker_start(self, payload: dict[str, str]) -> None:
        self._blob_action_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._start_blob_action_worker(dict(payload or {}))
            
    def _reload_blobs(self):
        """Перезагружает блобы из settings.json."""
        self._request_blobs_load(reload=True)
            
    def _open_bin_folder(self):
        """Открывает папку bin"""
        self._request_blob_open_action("bin_folder")
            
    def _open_json(self):
        """Открывает settings.json в редакторе."""
        self._request_blob_open_action("blobs_json")

    def create_blob_open_action_worker(self, request_id: int, *, action: str):
        return self._blobs.create_blob_open_action_worker(
            request_id,
            action=action,
            parent=self,
        )

    def _request_blob_open_action(self, action: str) -> None:
        action = str(action or "").strip()
        if not action:
            return
        if self._blob_open_action_runtime.is_running() or self.__dict__.get("_blob_open_action_start_scheduled", False):
            self._blob_open_action_pending.append(action)
            return
        self._start_blob_open_action_worker(action)

    def _start_blob_open_action_worker(self, action: str) -> None:
        self._blob_open_action_runtime.start_qthread_worker(
            worker_factory=lambda request_id: self.create_blob_open_action_worker(
                request_id,
                action=action,
            ),
            on_failed=self._on_blob_open_action_failed,
            on_finished=self._on_blob_open_action_worker_finished,
        )

    def _on_blob_open_action_failed(self, request_id: int, action: str, error: str) -> None:
        if not self._blob_open_action_runtime.is_current(
            request_id,
            cleanup_in_progress=self._cleanup_in_progress,
        ):
            return
        log(f"Ошибка открытия blobs action {action}: {error}", "ERROR")
        message_key = "page.blobs.error.open_file" if action == "blobs_json" else "page.blobs.error.open_folder"
        fallback = "Не удалось открыть файл: {error}" if action == "blobs_json" else "Не удалось открыть папку: {error}"
        InfoBar.warning(
            title=self._tr("common.error.title", "Ошибка"),
            content=self._tr(message_key, fallback, error=error),
            parent=self.window(),
        )

    def _on_blob_open_action_worker_finished(self, _worker) -> None:
        if self._blob_open_action_pending and not self._cleanup_in_progress:
            pending = self._blob_open_action_pending.pop(0)
            self._schedule_blob_open_action_worker_start(pending)

    def _schedule_blob_open_action_worker_start(self, action: str) -> None:
        clean_action = str(action or "").strip()
        if not clean_action or self.__dict__.get("_cleanup_in_progress", False):
            return
        if self.__dict__.get("_blob_open_action_start_scheduled", False):
            self._blob_open_action_pending.append(clean_action)
            return
        self._blob_open_action_start_scheduled = True
        QTimer.singleShot(0, lambda value=clean_action: self._run_scheduled_blob_open_action_worker_start(value))

    def _run_scheduled_blob_open_action_worker_start(self, action: str) -> None:
        self._blob_open_action_start_scheduled = False
        if self.__dict__.get("_cleanup_in_progress", False):
            return
        self._start_blob_open_action_worker(str(action or "").strip())

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        apply_blobs_language(
            tr_fn=self._tr,
            breadcrumb=getattr(self, "_breadcrumb", None),
            desc_label=self._desc_label,
            actions_group=self._actions_group,
            add_btn=self.add_btn,
            reload_btn=self.reload_btn,
            open_folder_btn=self.open_folder_btn,
            open_json_btn=self.open_json_btn,
            filter_edit=self.filter_edit,
            reload_callback=self._load_blobs,
        )

    def cleanup(self) -> None:
        self._cleanup_in_progress = True
        self._blob_action_pending.clear()
        self._blob_open_action_pending.clear()
        self._blobs_load_pending = False
        self._blobs_load_pending_reload = False
        self._blobs_load_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="blobs_load_worker",
        )
        self._blobs_load_runtime.cancel()
        self._blob_action_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="blob_action_worker",
        )
        self._blob_action_runtime.cancel()
        self._blob_open_action_runtime.stop(
            blocking=False,
            log_fn=log,
            warning_prefix="blob_open_action_worker",
        )
        self._blob_open_action_runtime.cancel()
