# filters/pages/direct_zapret1_targets_page.py
"""Zapret 1 target page with Zapret 2-style interface."""

from __future__ import annotations

import time as _time

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import QWidget, QHBoxLayout

from core.runtime.direct_ui_snapshot_service import DirectBasicUiSnapshotWorker
from filters.ui import TargetsList
from filters.runtime.targets_payload_runtime import (
    apply_payload_snapshot,
    clear_dynamic_payload_widgets,
    set_payload_loading,
)
from ui.pages.base_page import BasePage
from ui.compat_widgets import QuickActionsBar, RefreshButton
from app_state.main_window_state import AppUiState, MainWindowStateStore
from ui.text_catalog import tr as tr_catalog
from ui.theme import get_themed_qta_icon
from log import log

from qfluentwidgets import (
    BreadcrumbBar,
    MessageBox,
    BodyLabel,
    PushButton,
)


_INFO_TEXT = (
    "Здесь выбирается стратегия обхода DPI для каждого target'а, который реально найден "
    "в выбранном source preset.\n\n"
    "То есть список строится не из старого реестра как источника истины, а из самого "
    "текущего пресета. Внешние метаданные используются только для красивых названий и иконок.\n\n"
    "Откройте target и выберите стратегию Zapret 1. "
    "Если стратегия не подходит — попробуйте другую или задайте аргументы вручную "
    "в карточке target'а."
)


def _log_startup_z1_direct_metric(section: str, elapsed_ms: float) -> None:
    try:
        rounded = int(round(float(elapsed_ms)))
    except Exception:
        rounded = 0
    log(f"⏱ Startup UI Section: ZAPRET1_DIRECT {section} {rounded}ms", "⏱ STARTUP")


class Zapret1StrategiesPage(BasePage):
    """Список target'ов Zapret 1 с breadcrumb-навигацией."""

    target_clicked = pyqtSignal(str, dict)  # target_key, target_info
    back_clicked = pyqtSignal()

    def _require_app_context(self):
        app_context = getattr(self.parent(), "app_context", None)
        if app_context is None:
            app_context = getattr(self.window(), "app_context", None)
        if app_context is None:
            raise RuntimeError("AppContext is required for Zapret1 strategies page")
        return app_context

    def __init__(self, parent=None):
        super().__init__(
            title="Прямой запуск Zapret 1",
            parent=parent,
            title_key="page.z1_direct.title",
        )
        self.parent_app = parent

        self._built = False
        self._breadcrumb = None
        self._targets_list: TargetsList | None = None
        self.target_selections: dict[str, str] = {}
        self._targets: dict[str, Any] = {}
        self._expand_btn = None
        self._collapse_btn = None
        self._info_btn = None
        self._toolbar_actions_bar = None
        self._empty_state_label = None
        self._content_host = None
        self._content_host_layout = None
        self._loading_label = None
        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._cleanup_in_progress = False
        self._basic_payload_worker = None
        self._basic_payload_request_id = 0
        self._payload_load_started_at = None
        self._preset_refresh_pending = False
        self._list_structure_signature = None
        self._runtime_initialized = False

        self._setup_breadcrumb()
        self._build_content()
        self._after_ui_built()

    # ------------------------------------------------------------------
    # Breadcrumb
    # ------------------------------------------------------------------

    def _setup_breadcrumb(self) -> None:
        self._breadcrumb = BreadcrumbBar(self)
        self._rebuild_breadcrumb()
        self._breadcrumb.currentItemChanged.connect(self._on_breadcrumb_changed)
        self.layout.insertWidget(0, self._breadcrumb)

    def _rebuild_breadcrumb(self) -> None:
        if self._breadcrumb is None:
            return
        self._breadcrumb.blockSignals(True)
        try:
            self._breadcrumb.clear()
            self._breadcrumb.addItem(
                "control",
                tr_catalog("page.z1_direct.breadcrumb.control", language=self._ui_language, default="Управление"),
            )
            self._breadcrumb.addItem(
                "strategies",
                tr_catalog("page.z1_direct.title", language=self._ui_language, default="Прямой запуск Zapret 1"),
            )
        finally:
            self._breadcrumb.blockSignals(False)

    def _on_breadcrumb_changed(self, key: str) -> None:
        self._rebuild_breadcrumb()
        if key == "control":
            self.back_clicked.emit()

    # ------------------------------------------------------------------
    # Build lifecycle
    # ------------------------------------------------------------------

    def _after_ui_built(self) -> None:
        self._run_runtime_init_once()

    def _run_runtime_init_once(self) -> None:
        if self._runtime_initialized:
            return
        self._runtime_initialized = True
        self._request_payload_refresh(
            refresh=False,
            startup_scope="ZAPRET1_DIRECT",
            reason="init.initial",
        )

    def on_page_activated(self) -> None:
        if self._cleanup_in_progress:
            return
        if self._breadcrumb is not None:
            self._rebuild_breadcrumb()
        if self._built and self._preset_refresh_pending:
            self._preset_refresh_pending = False
            QTimer.singleShot(0, lambda: (not self._cleanup_in_progress) and self._refresh_from_preset_switch())
            return

    def _refresh_from_preset_switch(self) -> None:
        if self._cleanup_in_progress:
            return
        if not self.isVisible():
            self._preset_refresh_pending = True
            return
        self._request_payload_refresh(refresh=True, reason="preset_switch")

    def _build_content(self) -> None:
        _t_total = _time.perf_counter()
        try:
            self._do_build_shell()
        except Exception as e:
            log(f"Zapret1StrategiesPage: ошибка построения: {e}", "ERROR")
            import traceback

            log(traceback.format_exc(), "DEBUG")
        self._built = True
        _log_startup_z1_direct_metric("_build_content.total", (_time.perf_counter() - _t_total) * 1000)

    def _do_build_shell(self) -> None:
        _t_toolbar = _time.perf_counter()
        self._clear_dynamic_widgets()
        self._empty_state_label = None

        self._build_toolbar()
        _log_startup_z1_direct_metric("_build_content.toolbar", (_time.perf_counter() - _t_toolbar) * 1000)

        self._content_host = QWidget(self.content)
        self._content_host_layout = QVBoxLayout(self._content_host)
        self._content_host_layout.setContentsMargins(0, 0, 0, 0)
        self._content_host_layout.setSpacing(8)

        self._loading_label = BodyLabel(
            tr_catalog(
                "page.z1_direct.loading",
                language=self._ui_language,
                default="Загрузка категорий и target'ов...",
            )
        )
        self._loading_label.setWordWrap(True)
        self._loading_label.hide()
        self._content_host_layout.addWidget(self._loading_label)
        self.add_widget(self._content_host, 1)

    def _build_toolbar(self) -> None:
        self.add_section_title(text_key="page.z1_direct.toolbar.title")
        self._toolbar_actions_bar = QuickActionsBar(self.content)

        self._reload_btn = RefreshButton()
        self._reload_btn.clicked.connect(self._reload)
        self._reload_btn.setToolTip(
            tr_catalog(
                "page.z1_direct.toolbar.reload.description",
                language=self._ui_language,
                default="Обновить список категорий, target'ов и выбранных стратегий.",
            )
        )
        self._toolbar_actions_bar.add_button(self._reload_btn)

        self._expand_btn = PushButton()
        self._expand_btn.setText(
            tr_catalog("page.z1_direct.toolbar.expand", language=self._ui_language, default="Развернуть")
        )
        self._expand_btn.setIcon(get_themed_qta_icon("fa5s.expand-alt", color="#4CAF50"))
        self._expand_btn.setToolTip(
            tr_catalog(
                "page.z1_direct.toolbar.expand.description",
                language=self._ui_language,
                default="Развернуть все категории и target'ы в списке.",
            )
        )
        self._expand_btn.clicked.connect(self._expand_all)
        self._toolbar_actions_bar.add_button(self._expand_btn)

        self._collapse_btn = PushButton()
        self._collapse_btn.setText(
            tr_catalog("page.z1_direct.toolbar.collapse", language=self._ui_language, default="Свернуть")
        )
        self._collapse_btn.setIcon(get_themed_qta_icon("fa5s.compress-alt", color="#ff9800"))
        self._collapse_btn.setToolTip(
            tr_catalog(
                "page.z1_direct.toolbar.collapse.description",
                language=self._ui_language,
                default="Свернуть все категории и target'ы в списке.",
            )
        )
        self._collapse_btn.clicked.connect(self._collapse_all)
        self._toolbar_actions_bar.add_button(self._collapse_btn)

        self._info_btn = PushButton()
        self._info_btn.setText(
            tr_catalog("page.z1_direct.toolbar.info", language=self._ui_language, default="Что это?")
        )
        self._info_btn.setIcon(get_themed_qta_icon("fa5s.question-circle", color="#60cdff"))
        self._info_btn.setToolTip(
            tr_catalog(
                "page.z1_direct.toolbar.info.description",
                language=self._ui_language,
                default="Показать краткое объяснение, как устроен прямой запуск Zapret 1.",
            )
        )
        self._info_btn.clicked.connect(self._show_info)
        self._toolbar_actions_bar.add_button(self._info_btn)
        self.add_widget(self._toolbar_actions_bar)

    def _set_payload_loading(self, loading: bool) -> None:
        set_payload_loading(
            reload_btn=self._reload_btn,
            loading_label=self._loading_label,
            loading=loading,
            targets_list=self._targets_list,
            empty_state_label=self._empty_state_label,
        )

    def _clear_dynamic_payload_widgets(self) -> None:
        clear_dynamic_payload_widgets(content_host_layout=self._content_host_layout)
        self._targets_list = None
        self._empty_state_label = None
        self._targets = {}
        self._list_structure_signature = None

    def _apply_payload_snapshot(self, payload, *, reason: str) -> None:
        result = apply_payload_snapshot(
            page=self,
            payload=payload,
            reason=reason,
            targets_list=self._targets_list,
            list_structure_signature=self._list_structure_signature,
            content_host_layout=self._content_host_layout,
            startup_scope="ZAPRET1_DIRECT",
            empty_state_text=tr_catalog(
                "page.z1_direct.empty.no_categories",
                language=self._ui_language,
                default="Target'ы не найдены. Проверьте выбранный source preset и его содержимое.",
            ),
            empty_label_cls=BodyLabel,
            on_target_clicked=self._on_target_clicked,
            on_selections_changed=self._on_selections_changed,
            startup_metric_logger=_log_startup_z1_direct_metric,
            update_current_strategies_display=None,
            log_debug=lambda text: log(text, "DEBUG"),
        )
        self._targets_list = result["targets_list"]
        self._empty_state_label = result["empty_state_label"]
        self._targets = result["target_items"]
        incoming_selections = result["target_selections"]
        self.target_selections = {
            key: incoming_selections.get(key, "none")
            for key in self._targets.keys()
        }
        if not self._targets:
            self.target_selections = dict(incoming_selections or {})
        self._list_structure_signature = result["list_structure_signature"]

    def _request_payload_refresh(
        self,
        *,
        refresh: bool,
        reason: str,
        startup_scope: str | None = None,
    ) -> None:
        if not self.isVisible():
            self._preset_refresh_pending = True
            return
        token = self.issue_page_load_token(reason=reason)
        self._basic_payload_request_id += 1
        request_id = self._basic_payload_request_id
        self._payload_load_started_at = _time.perf_counter()
        self._set_payload_loading(True)
        worker = DirectBasicUiSnapshotWorker(
            request_id,
            snapshot_service=self._require_app_context().direct_ui_snapshot_service,
            launch_method="direct_zapret1",
            refresh=refresh,
            startup_scope=startup_scope,
            parent=self,
        )
        worker.loaded.connect(
            lambda loaded_request_id, snapshot, load_token=token, request_reason=reason: self._on_payload_snapshot_loaded(
                loaded_request_id,
                snapshot,
                load_token,
                reason=request_reason,
            )
        )
        self._basic_payload_worker = worker
        worker.start()

    def _on_payload_snapshot_loaded(self, request_id: int, snapshot, token: int, *, reason: str) -> None:
        if request_id != self._basic_payload_request_id:
            return
        if not self.is_page_load_token_current(token):
            return
        if not self.isVisible():
            self._preset_refresh_pending = True
            return
        self._set_payload_loading(False)
        payload = getattr(snapshot, "payload", None)
        if payload is None:
            return
        started_at = self._payload_load_started_at
        if started_at is not None:
            _log_startup_z1_direct_metric("_build_content.payload", (_time.perf_counter() - started_at) * 1000)
        self._apply_payload_snapshot(payload, reason=reason)

    @staticmethod
    def _target_info_to_dict(target_key: str, target_info: Any) -> dict:
        if isinstance(target_info, dict):
            data = dict(target_info)
            data.setdefault("key", target_key)
            data.setdefault("full_name", data.get("name", target_key))
            data.setdefault("description", "")
            data.setdefault("base_filter", data.get("base_filter", ""))
            data.setdefault("base_filter_hostlist", data.get("base_filter_hostlist", ""))
            data.setdefault("base_filter_ipset", data.get("base_filter_ipset", ""))
            return data

        data = {
            "key": getattr(target_info, "key", target_key),
            "full_name": getattr(target_info, "full_name", target_key),
            "description": getattr(target_info, "description", ""),
            "protocol": getattr(target_info, "protocol", ""),
            "ports": getattr(target_info, "ports", ""),
            "icon_name": getattr(target_info, "icon_name", ""),
            "icon_color": getattr(target_info, "icon_color", "#909090"),
            "command_group": getattr(target_info, "command_group", "default"),
            "base_filter": getattr(target_info, "base_filter", ""),
            "base_filter_hostlist": getattr(target_info, "base_filter_hostlist", ""),
            "base_filter_ipset": getattr(target_info, "base_filter_ipset", ""),
        }

        data.setdefault("key", target_key)
        data.setdefault("full_name", target_key)
        data.setdefault("description", "")
        return data

    # ------------------------------------------------------------------
    # Actions / handlers
    # ------------------------------------------------------------------

    def _on_target_clicked(self, target_key: str, _strategy_id: str) -> None:
        try:
            target_info = (self._targets or {}).get(target_key)
        except Exception:
            target_info = None

        info_dict = self._target_info_to_dict(target_key, target_info)

        # Важно: отложенная навигация убирает артефакты hover/cursor в Qt.
        QTimer.singleShot(
            0,
            lambda k=target_key, info=dict(info_dict): self.target_clicked.emit(k, info),
        )

    def _on_selections_changed(self, selections: dict) -> None:
        self.target_selections = dict(selections or {})

    def _refresh_subtitles(self, payload=None) -> None:
        if not self._targets_list:
            return

        if payload is None:
            payload = self._require_app_context().direct_ui_snapshot_service.load_basic_ui_payload("direct_zapret1", refresh=True)
        self.target_selections = payload.strategy_selections or {}
        self.target_selections = {
            key: self.target_selections.get(key, "none")
            for key in (self._targets or {}).keys()
        }
        self._targets_list.set_strategy_names_by_target(payload.strategy_names_by_target or {})
        self._targets_list.set_selections(self.target_selections)

        filter_modes = payload.filter_modes or {}
        self._targets_list.set_filter_modes(filter_modes, target_keys=(self._targets or {}).keys())

    def refresh_strategy_list_state(self) -> None:
        if not self.isVisible() or not self._built:
            self._preset_refresh_pending = True
            return
        try:
            self._refresh_subtitles()
        except Exception:
            self._preset_refresh_pending = True

    def _reload(self, *_args) -> None:
        try:
            self._request_payload_refresh(refresh=True, reason="manual_reload")
        except Exception:
            pass

    def _expand_all(self, *_args) -> None:
        if self._targets_list:
            self._targets_list.expand_all()

    def _collapse_all(self, *_args) -> None:
        if self._targets_list:
            self._targets_list.collapse_all()

    def _show_info(self, *_args) -> None:
        try:
            box = MessageBox(
                tr_catalog("page.z1_direct.info.title", language=self._ui_language, default="Прямой запуск Zapret 1"),
                tr_catalog("page.z1_direct.info.body", language=self._ui_language, default=_INFO_TEXT),
                self.window(),
            )
            box.hideCancelButton()
            box.yesButton.setText(tr_catalog("common.ok.got_it", language=self._ui_language, default="Понятно"))
            box.exec()
        except Exception:
            pass

    def _clear_dynamic_widgets(self) -> None:
        keep: set[QWidget] = {self.title_label}
        if self.subtitle_label:
            keep.add(self.subtitle_label)
        if self._breadcrumb:
            keep.add(self._breadcrumb)

        to_remove = []
        for i in range(self.vBoxLayout.count()):
            item = self.vBoxLayout.itemAt(i)
            w = item.widget() if item else None
            if w is not None and w not in keep:
                to_remove.append(w)

        for w in to_remove:
            self.vBoxLayout.removeWidget(w)
            w.setParent(None)

    # ------------------------------------------------------------------
    # Main-window callbacks
    # ------------------------------------------------------------------

    def reload_for_mode_change(self) -> None:
        self._clear_dynamic_payload_widgets()
        if not self.isVisible():
            self._preset_refresh_pending = True
            return
        self._request_payload_refresh(refresh=True, reason="mode_change")

    def update_current_strategy(self, name: str) -> None:
        # Direct Z1 target list page does not show a separate current-strategy label,
        # but MainWindow still calls this hook on all strategy pages.
        _ = name

    def bind_ui_state_store(self, store: MainWindowStateStore) -> None:
        if self._ui_state_store is store:
            return

        unsubscribe = getattr(self, "_ui_state_unsubscribe", None)
        if callable(unsubscribe):
            try:
                unsubscribe()
            except Exception:
                pass

        self._ui_state_store = store
        self._ui_state_unsubscribe = store.subscribe(
            self._on_ui_state_changed,
            fields={"active_preset_revision", "preset_content_revision", "mode_revision"},
            emit_initial=True,
        )

    def _on_ui_state_changed(self, _state: AppUiState, changed_fields: frozenset[str]) -> None:
        if self._cleanup_in_progress:
            return
        if (
            "active_preset_revision" in changed_fields
            or "preset_content_revision" in changed_fields
            or "mode_revision" in changed_fields
        ):
            if not self.isVisible():
                self._preset_refresh_pending = True
                return
            self._refresh_from_preset_switch()

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)

        self._rebuild_breadcrumb()

        if self._expand_btn is not None:
            self._expand_btn.setText(
                tr_catalog("page.z1_direct.toolbar.expand", language=self._ui_language, default="Развернуть")
            )
            self._expand_btn.setToolTip(
                tr_catalog(
                    "page.z1_direct.toolbar.expand.description",
                    language=self._ui_language,
                    default="Развернуть все категории и target'ы в списке.",
                )
            )
        if self._collapse_btn is not None:
            self._collapse_btn.setText(
                tr_catalog("page.z1_direct.toolbar.collapse", language=self._ui_language, default="Свернуть")
            )
            self._collapse_btn.setToolTip(
                tr_catalog(
                    "page.z1_direct.toolbar.collapse.description",
                    language=self._ui_language,
                    default="Свернуть все категории и target'ы в списке.",
                )
            )
        if self._info_btn is not None:
            self._info_btn.setText(
                tr_catalog("page.z1_direct.toolbar.info", language=self._ui_language, default="Что это?")
            )
            self._info_btn.setToolTip(
                tr_catalog(
                    "page.z1_direct.toolbar.info.description",
                    language=self._ui_language,
                    default="Показать краткое объяснение, как устроен прямой запуск Zapret 1.",
                )
            )

        if self._empty_state_label is not None:
            self._empty_state_label.setText(
                tr_catalog(
                    "page.z1_direct.empty.no_categories",
                    language=self._ui_language,
                    default="Target'ы не найдены. Проверьте выбранный source preset и его содержимое.",
                )
            )

        if self._built:
            self._refresh_subtitles()

    def cleanup(self) -> None:
        self._cleanup_in_progress = True

        unsubscribe = getattr(self, "_ui_state_unsubscribe", None)
        if callable(unsubscribe):
            try:
                unsubscribe()
            except Exception:
                pass
        self._ui_state_unsubscribe = None
        self._ui_state_store = None
