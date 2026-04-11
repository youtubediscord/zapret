# ui/pages/zapret2/direct_zapret2_page.py
"""
Страница выбора стратегий для режима direct_zapret2 (preset-based).
При клике на target открывается отдельная страница StrategyDetailPage.
"""

import time as _time

from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QFrame, QSizePolicy
)
import qtawesome as qta

from core.runtime.direct_ui_snapshot_service import DirectBasicUiSnapshotWorker
from ui.pages.base_page import BasePage
from ui.compat_widgets import QuickActionsBar, RefreshButton
from ui.main_window_state import AppUiState, MainWindowStateStore
from ui.widgets.preset_targets_list import PresetTargetsList
from ui.theme import get_theme_tokens
from ui.text_catalog import tr as tr_catalog
from log import log

from qfluentwidgets import (
    BreadcrumbBar,
    MessageBox,
    CaptionLabel,
    BodyLabel,
    PushButton,
    PrimaryPushButton,
)


_CATEGORY_REQUEST_FORM_URL = (
    "https://github.com/youtubediscord/zapret/issues/new?template=hostlist_ipset_request.yml"
)


def _log_startup_z2_direct_metric(section: str, elapsed_ms: float) -> None:
    try:
        rounded = int(round(float(elapsed_ms)))
    except Exception:
        rounded = 0
    log(f"⏱ Startup UI Section: ZAPRET2_DIRECT {section} {rounded}ms", "⏱ STARTUP")

class Zapret2StrategiesPageNew(BasePage):
    """
    Страница выбора стратегий с единым списком target'ов.

    При клике на target эмитит сигнал open_target_detail для навигации
    к отдельной странице StrategyDetailPage.
    """

    strategy_selected = pyqtSignal(str, str)  # target_key, strategy_id
    strategies_changed = pyqtSignal(dict)  # все выборы
    launch_method_changed = pyqtSignal(str)  # для совместимости
    open_target_detail = pyqtSignal(str, str)  # target_key, current_strategy_id
    back_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(
            title="Прямой запуск Zapret 2",
            parent=parent,
            title_key="page.z2_direct.title",
        )
        self.parent_app = parent

        # Breadcrumb navigation: Управление › Прямой запуск Zapret 2
        self._breadcrumb = BreadcrumbBar()
        self._rebuild_breadcrumb()
        self._breadcrumb.currentItemChanged.connect(self._on_breadcrumb_item_changed)
        self.layout.insertWidget(0, self._breadcrumb)

        self.target_selections = {}
        self._targets_list = None
        self._built = False
        self._ui_state_store = None
        self._ui_state_unsubscribe = None
        self._preset_refresh_pending = False
        self._list_structure_signature = None
        self._empty_state_label = None
        self._content_host = None
        self._content_host_layout = None
        self._loading_label = None
        self._request_btn = None
        self._reload_btn = None
        self._expand_btn = None
        self._collapse_btn = None
        self._info_btn = None
        self._toolbar_actions_bar = None
        self._basic_payload_worker = None
        self._basic_payload_request_id = 0
        self._payload_load_started_at = None
        self._render_probe_build_started_at = None
        self._render_probe_build_finished_at = None
        self._render_probe_first_paint_logged = False
        self._render_probe_idle_logged = False
        self._suppress_next_preset_refresh = False
        self._runtime_initialized = False

        # Совместимость со старым кодом
        self.content_layout = self.layout
        self.content_container = self.content

        try:
            self.viewport().installEventFilter(self)
            self.content.installEventFilter(self)
        except Exception:
            pass

        # Заглушки для совместимости с main_window.py
        self.select_strategy_btn = PushButton()
        self.select_strategy_btn.hide()

        self.current_strategy_label = BodyLabel(
            tr_catalog("page.z2_direct.current.not_selected", language=self._ui_language, default="Не выбрана")
        )
        self._build_content()
        self._after_ui_built()

    def _after_ui_built(self) -> None:
        self._run_runtime_init_once()

    def _run_runtime_init_once(self) -> None:
        if self._runtime_initialized:
            return
        self._runtime_initialized = True
        self._request_payload_refresh(
            refresh=False,
            startup_scope="ZAPRET2_DIRECT",
            reason="init.initial",
        )

    def _rebuild_breadcrumb(self) -> None:
        """Restore full breadcrumb path (BreadcrumbBar deletes items on back-click)."""
        if self._breadcrumb is None:
            return
        self._breadcrumb.blockSignals(True)
        try:
            self._breadcrumb.clear()
            self._breadcrumb.addItem(
                "control",
                tr_catalog("page.z2_direct.back.control", language=self._ui_language, default="Управление"),
            )
            self._breadcrumb.addItem(
                "strategies",
                tr_catalog("page.z2_direct.title", language=self._ui_language, default="Прямой запуск Zapret 2"),
            )
        finally:
            self._breadcrumb.blockSignals(False)

    def _on_breadcrumb_item_changed(self, key: str) -> None:
        # BreadcrumbBar already deleted the trailing item — restore immediately
        self._rebuild_breadcrumb()
        if key == "control":
            self.back_clicked.emit()

    def on_page_activated(self) -> None:
        """При активации страницы загружаем/обновляем контент."""
        self._rebuild_breadcrumb()  # Fix state if user navigated away via breadcrumb

        if self._built and self._preset_refresh_pending:
            self._preset_refresh_pending = False
            try:
                self.refresh_from_preset_switch()
                return
            except Exception:
                pass

    def eventFilter(self, obj, event):
        try:
            if (
                event.type() == QEvent.Type.Paint
                and not self._render_probe_first_paint_logged
                and self._render_probe_build_finished_at is not None
                and obj in {self.viewport(), self.content}
            ):
                self._render_probe_first_paint_logged = True
                finished_at = self._render_probe_build_finished_at
                build_started_at = self._render_probe_build_started_at
                if finished_at is not None:
                    _log_startup_z2_direct_metric(
                        "_build_content.render.first_paint_after_build",
                        (_time.perf_counter() - finished_at) * 1000,
                    )
                if build_started_at is not None:
                    _log_startup_z2_direct_metric(
                        "_build_content.render.total_to_first_paint",
                        (_time.perf_counter() - build_started_at) * 1000,
                    )
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def _build_content(self):
        """Строит только лёгкий shell страницы.

        Тяжёлый payload списка target'ов приходит отдельным snapshot-запросом
        вне момента сборки shell, чтобы первый показ страницы оставался быстрым.
        """
        _t_total = _time.perf_counter()
        try:
            if self._built:
                return
            self._render_probe_build_started_at = _t_total
            self._render_probe_build_finished_at = None
            self._render_probe_first_paint_logged = False
            self._render_probe_idle_logged = False

            # Панель быстрых действий: только stock fluent-кнопки без описаний.
            _t_toolbar = _time.perf_counter()
            self.add_section_title(text_key="page.z2_direct.toolbar.title")
            self._toolbar_actions_bar = QuickActionsBar(self.content)

            self._request_btn = PrimaryPushButton()
            self._request_btn.setText(
                tr_catalog("page.z2_direct.request.button", language=self._ui_language, default="ОТКРЫТЬ ФОРМУ НА GITHUB")
            )
            self._request_btn.setIcon(qta.icon("fa5b.github", color=get_theme_tokens().accent_hex))
            self._request_btn.clicked.connect(self._open_category_request_form)
            self._request_btn.setToolTip(
                tr_catalog(
                    "page.z2_direct.request.hint",
                    language=self._ui_language,
                    default=(
                        "Хотите добавить новый сайт или сервис в Zapret 2? "
                        "Откройте готовую форму на GitHub и опишите, что нужно добавить в hostlist или ipset."
                    ),
                )
            )
            self._toolbar_actions_bar.add_button(self._request_btn)

            self._reload_btn = RefreshButton()
            self._reload_btn.clicked.connect(self._reload_strategies)
            self._reload_btn.setToolTip(
                tr_catalog(
                    "page.z2_direct.toolbar.reload.description",
                    language=self._ui_language,
                    default="Обновить список категорий, target'ов и выбранных стратегий.",
                )
            )
            self._toolbar_actions_bar.add_button(self._reload_btn)

            self._expand_btn = PushButton()
            self._expand_btn.setText(
                tr_catalog("page.z2_direct.toolbar.expand", language=self._ui_language, default="Развернуть")
            )
            self._expand_btn.setIcon(qta.icon("fa5s.expand-alt", color="#4CAF50"))
            self._expand_btn.clicked.connect(self._expand_all)
            self._expand_btn.setToolTip(
                tr_catalog(
                    "page.z2_direct.toolbar.expand.description",
                    language=self._ui_language,
                    default="Развернуть все категории и target'ы в списке.",
                )
            )
            self._toolbar_actions_bar.add_button(self._expand_btn)

            self._collapse_btn = PushButton()
            self._collapse_btn.setText(
                tr_catalog("page.z2_direct.toolbar.collapse", language=self._ui_language, default="Свернуть")
            )
            self._collapse_btn.setIcon(qta.icon("fa5s.compress-alt", color="#ff9800"))
            self._collapse_btn.clicked.connect(self._collapse_all)
            self._collapse_btn.setToolTip(
                tr_catalog(
                    "page.z2_direct.toolbar.collapse.description",
                    language=self._ui_language,
                    default="Свернуть все категории и target'ы в списке.",
                )
            )
            self._toolbar_actions_bar.add_button(self._collapse_btn)

            self._info_btn = PushButton()
            self._info_btn.setText(
                tr_catalog("page.z2_direct.toolbar.info", language=self._ui_language, default="Что это такое?")
            )
            self._info_btn.setIcon(qta.icon("fa5s.question-circle", color="#60cdff"))
            self._info_btn.clicked.connect(self._show_info_popup)
            self._info_btn.setToolTip(
                tr_catalog(
                    "page.z2_direct.toolbar.info.description",
                    language=self._ui_language,
                    default="Показать краткое объяснение по работе прямого запуска Zapret 2.",
                )
            )
            self._toolbar_actions_bar.add_button(self._info_btn)
            self.content_layout.addWidget(self._toolbar_actions_bar)
            _log_startup_z2_direct_metric("_build_content.toolbar", (_time.perf_counter() - _t_toolbar) * 1000)

            self._content_host = QWidget(self.content)
            self._content_host_layout = QVBoxLayout(self._content_host)
            self._content_host_layout.setContentsMargins(0, 0, 0, 0)
            self._content_host_layout.setSpacing(8)

            self._loading_label = BodyLabel(
                tr_catalog(
                    "page.z2_direct.loading",
                    language=self._ui_language,
                    default="Загрузка категорий и target'ов...",
                )
            )
            self._loading_label.setWordWrap(True)
            self._loading_label.hide()
            self._content_host_layout.addWidget(self._loading_label)

            self.content_layout.addWidget(self._content_host, 1)

            self._built = True
            log("Zapret2StrategiesPageNew: shell построен", "INFO")
            _log_startup_z2_direct_metric("_build_content.total", (_time.perf_counter() - _t_total) * 1000)
            self._render_probe_build_finished_at = _time.perf_counter()
            QTimer.singleShot(0, self._log_render_probe_idle)

        except Exception as e:
            log(f"Ошибка построения Zapret2StrategiesPageNew: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")

    def _build_list_structure_signature(self, payload) -> tuple:
        """Собирает сигнатуру структуры списка для решения: rebuild нужен или нет."""
        selected_preset_file_name = str(getattr(payload, "selected_preset_file_name", "") or "").strip().lower()
        target_items = payload.target_items or {}
        signature_rows = []
        for view in tuple(payload.target_views or ()):
            target_key = str(getattr(view, "target_key", "") or "").strip()
            meta = target_items.get(target_key)
            signature_rows.append(
                (
                    target_key,
                    str(getattr(view, "display_name", "") or "").strip(),
                    str(getattr(meta, "full_name", "") or "").strip(),
                    str(getattr(meta, "command_group", "") or "").strip(),
                    int(getattr(meta, "order", 999) or 999),
                    int(getattr(meta, "command_order", 999) or 999),
                    str(getattr(meta, "protocol", "") or "").strip(),
                    str(getattr(meta, "ports", "") or "").strip(),
                    str(getattr(meta, "icon_name", "") or "").strip(),
                    str(getattr(meta, "icon_color", "") or "").strip(),
                    str(getattr(meta, "base_filter_hostlist", "") or "").strip(),
                    str(getattr(meta, "base_filter_ipset", "") or "").strip(),
                    str(getattr(meta, "strategy_type", "") or "").strip(),
                    bool(getattr(meta, "requires_all_ports", False)),
                )
            )
        return (selected_preset_file_name, tuple(signature_rows))

    def _apply_payload_to_existing_list(self, payload, *, reason: str) -> bool:
        """Обновляет уже построенный список без полной перестройки страницы."""
        if self._targets_list is None:
            return False

        target_items = payload.target_items or {}
        self.target_selections = payload.strategy_selections or {}
        filter_modes = payload.filter_modes or {}

        self._targets_list.set_strategy_names_by_target(payload.strategy_names_by_target or {})
        self._targets_list.set_selections(self.target_selections)
        self._targets_list.set_filter_modes(filter_modes, target_keys=target_items.keys())

        self._list_structure_signature = self._build_list_structure_signature(payload)
        self._update_current_strategies_display()
        log(f"Список стратегий обновлен без полной перестройки ({reason})", "DEBUG")
        return True

    def _payload_requires_rebuild(self, payload) -> bool:
        """Определяет, нужно ли физически пересобирать список."""
        if self._targets_list is None:
            return True
        return self._build_list_structure_signature(payload) != self._list_structure_signature

    def _set_payload_loading(self, loading: bool) -> None:
        try:
            if self._reload_btn is not None:
                self._reload_btn.set_loading(bool(loading))
        except Exception:
            pass

        if self._loading_label is None:
            return

        should_show_placeholder = bool(loading) and self._targets_list is None and self._empty_state_label is None
        self._loading_label.setVisible(should_show_placeholder)

    def _clear_dynamic_payload_widgets(self) -> None:
        host_layout = self._content_host_layout
        if host_layout is None:
            return

        while host_layout.count() > 1:
            item = host_layout.takeAt(1)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()

        self._targets_list = None
        self._empty_state_label = None
        self._list_structure_signature = None

    def _build_targets_list_widget(self, payload) -> None:
        target_items = payload.target_items or {}
        target_views = list(payload.target_views or ())
        strategy_names_by_target = payload.strategy_names_by_target or {}
        filter_modes = payload.filter_modes or {}
        self.target_selections = payload.strategy_selections or {}

        if not target_items:
            self._empty_state_label = BodyLabel(self._build_empty_state_text())
            self._empty_state_label.setWordWrap(True)
            self._content_host_layout.addWidget(self._empty_state_label)
            log("Zapret2StrategiesPageNew: target'ы не найдены, показано empty state", "INFO")
            return

        self._targets_list = PresetTargetsList(
            self,
            startup_scope="ZAPRET2_DIRECT",
        )
        self._targets_list.strategy_selected.connect(self._on_target_clicked)
        self._targets_list.selections_changed.connect(self._on_selections_changed)
        self._targets_list.build_from_target_views(
            target_views,
            metadata=target_items,
            selections=self.target_selections,
            strategy_names_by_target=strategy_names_by_target,
            filter_modes=filter_modes,
        )
        self._content_host_layout.addWidget(self._targets_list, 1)

    def _apply_payload_snapshot(self, payload, *, reason: str) -> None:
        if self._payload_requires_rebuild(payload):
            _t_targets = _time.perf_counter()
            self._clear_dynamic_payload_widgets()
            self._build_targets_list_widget(payload)
            _log_startup_z2_direct_metric("_build_content.targets_list", (_time.perf_counter() - _t_targets) * 1000)
        else:
            self._apply_payload_to_existing_list(payload, reason=reason)
            return

        self._list_structure_signature = self._build_list_structure_signature(payload)
        self._update_current_strategies_display()
        log(f"Список стратегий применен из runtime snapshot ({reason})", "DEBUG")

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
            launch_method="direct_zapret2",
            refresh=refresh,
            startup_scope=startup_scope,
            parent=self,
        )
        worker.loaded.connect(
            lambda loaded_request_id, snapshot, load_token=token: self._on_payload_snapshot_loaded(
                loaded_request_id,
                snapshot,
                load_token,
                reason=reason,
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
            _log_startup_z2_direct_metric("_build_content.payload", (_time.perf_counter() - started_at) * 1000)

        self._apply_payload_snapshot(payload, reason=reason)
        self._render_probe_build_finished_at = _time.perf_counter()
        QTimer.singleShot(0, self._log_render_probe_idle)

    def _log_render_probe_idle(self) -> None:
        if self._render_probe_idle_logged:
            return
        finished_at = self._render_probe_build_finished_at
        if finished_at is None:
            return
        self._render_probe_idle_logged = True
        _log_startup_z2_direct_metric(
            "_build_content.render.next_event_loop",
            (_time.perf_counter() - finished_at) * 1000,
        )

    def _on_target_clicked(self, target_key: str, strategy_id: str):
        """Обработчик клика по target - открывает страницу выбора стратегий"""
        try:
            current_strategy = self.target_selections.get(target_key, 'none')
            # Defer navigation to the next event loop tick: prevents page switch
            # while Qt is still processing the mouse event (can break hover/cursor updates).
            QTimer.singleShot(0, lambda tk=target_key, cs=current_strategy: self.open_target_detail.emit(tk, cs))
        except Exception as e:
            log(f"Ошибка открытия детальной страницы: {e}", "ERROR")

    def apply_strategy_selection(self, target_key: str, strategy_id: str):
        """Применяет выбор стратегии (вызывается из StrategyDetailPage)"""
        try:
            from core.presets.direct_facade import DirectPresetFacade
            from dpi.direct_runtime_apply_policy import request_direct_runtime_content_apply

            # Multi-phase TCP UI persists args directly (strategy_detail_page.py).
            # Avoid clobbering preset args by re-applying a non-existent single strategy.
            if (strategy_id or "").strip().lower() == "custom":
                self.target_selections[target_key] = "custom"
                if self._targets_list:
                    self._targets_list.update_selection(target_key, "custom")
                return

            # Сохраняем в preset файл
            direct_facade = DirectPresetFacade.from_launch_method(
                "direct_zapret2",
                on_dpi_reload_needed=lambda: request_direct_runtime_content_apply(
                    self.parent_app,
                    launch_method="direct_zapret2",
                    reason="strategy_changed"
                )
            )
            self._suppress_next_preset_refresh = True
            direct_facade.set_strategy_selection(target_key, strategy_id, save_and_sync=True)

            self.target_selections[target_key] = strategy_id

            # Обновляем UI
            if self._targets_list:
                self._targets_list.update_selection(target_key, strategy_id)

            # Эмитим сигналы
            self.strategy_selected.emit(target_key, strategy_id)
            self.strategies_changed.emit(self.target_selections)

            log(f"Выбрана стратегия: {target_key} = {strategy_id}", "INFO")

        except Exception as e:
            log(f"Ошибка сохранения выбора: {e}", "ERROR")

    def apply_filter_mode_change(self, target_key: str, filter_mode: str):
        """Обновляет badge Hostlist/IPset на главной странице без перестроения списка."""
        try:
            self._suppress_next_preset_refresh = True
            if self._targets_list:
                self._targets_list.update_filter_mode(target_key, filter_mode)
        except Exception as e:
            log(f"Ошибка обновления filter_mode: {e}", "DEBUG")

    def _on_selections_changed(self, selections: dict):
        """Обработчик изменения выборов"""
        self.target_selections = selections
        self.strategies_changed.emit(selections)

    def _apply_changes(self):
        """Применяет изменения - перезапускает DPI если запущен"""
        from dpi.direct_runtime_apply_policy import request_direct_runtime_content_apply
        request_direct_runtime_content_apply(
            self.parent_app,
            launch_method="direct_zapret2",
            reason="strategy_changed"
        )

    def _reload_strategies(self):
        """Перезагружает стратегии"""
        try:
            self._request_payload_refresh(refresh=True, reason="manual_reload")
        except Exception as e:
            log(f"Ошибка перезагрузки: {e}", "ERROR")

    def refresh_from_preset_switch(self):
        """
        Перечитывает активный пресет и обновляет UI списка (без перестроения).
        Вызывается асинхронно из MainWindow после активации пресета.
        """
        if not self.isVisible():
            self._preset_refresh_pending = True
            return
        try:
            self._request_payload_refresh(refresh=True, reason="preset_switch")
        except Exception as e:
            log(f"Ошибка refresh_from_preset_switch: {e}", "DEBUG")

    def _build_empty_state_text(self) -> str:
        empty_state = None
        try:
            from core.services import get_direct_ui_snapshot_service

            empty_state = get_direct_ui_snapshot_service().get_basic_ui_empty_state("direct_zapret2")
        except Exception as e:
            log(f"Zapret2StrategiesPageNew: не удалось определить причину пустого списка: {e}", "DEBUG")

        reason = str((empty_state or {}).get("reason") or "").strip().lower()
        preset_name = str((empty_state or {}).get("preset_name") or "").strip()

        if reason == "no_presets":
            return tr_catalog(
                "page.z2_direct.empty.no_presets",
                language=self._ui_language,
                default=(
                    "Пресеты Zapret 2 не найдены. Обычно здесь должны быть txt-файлы в "
                    "%APPDATA%\\zapret\\presets_v2. Если папка пустая, встроенные пресеты не были "
                    "скопированы или были удалены."
                ),
            )

        if reason == "no_selected_preset":
            return tr_catalog(
                "page.z2_direct.empty.no_selected_preset",
                language=self._ui_language,
                default=(
                    "Не удалось определить выбранный source preset. "
                    "Откройте список пресетов, выберите любой пресет заново и нажмите «Обновить»."
                ),
            )

        if reason == "preset_read_error":
            return tr_catalog(
                "page.z2_direct.empty.preset_read_error",
                language=self._ui_language,
                default=(
                    "Не удалось прочитать выбранный source preset «{preset_name}». "
                    "Такое бывает, если файл пустой, повреждён или недоступен для чтения."
                ),
            ).format(preset_name=preset_name or "без имени")

        return tr_catalog(
            "page.z2_direct.empty.no_categories",
            language=self._ui_language,
            default=(
                "В выбранном source preset «{preset_name}» не найдено ни одной категории для этой страницы. "
                "Это значит, что после разбора файла программа не увидела ни одного target'а "
                "с фильтрами вроде hostlist, hostlist-domains или ipset."
            ),
        ).format(preset_name=preset_name or "без имени")

    def _expand_all(self):
        """Разворачивает все группы"""
        if self._targets_list:
            self._targets_list.expand_all()

    def _collapse_all(self):
        """Сворачивает все группы"""
        if self._targets_list:
            self._targets_list.collapse_all()

    # ==================== Совместимость со старым кодом ====================

    def update_current_strategy(self, name: str):
        """Совместимость: обновляет отображение текущей стратегии"""
        if not self.isVisible():
            self._preset_refresh_pending = True
            return
        disabled_label = tr_catalog(
            "page.strategies_base.strategy.autostart_disabled",
            language=self._ui_language,
            default="Автозапуск DPI после старта программы отключён",
        )
        if name and name != disabled_label:
            self.current_strategy_label.setText(name)
        else:
            self.current_strategy_label.setText(
                tr_catalog("page.z2_direct.current.not_selected", language=self._ui_language, default="Не выбрана")
            )

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
            fields={"current_strategy_summary", "active_preset_revision", "preset_content_revision", "mode_revision"},
            emit_initial=True,
        )

    def _on_ui_state_changed(self, state: AppUiState, changed_fields: frozenset[str]) -> None:
        if "mode_revision" in changed_fields:
            self.reload_for_mode_change()
            return
        if "active_preset_revision" in changed_fields:
            if not self.isVisible():
                self._preset_refresh_pending = True
                return
            self.refresh_from_preset_switch()
        if "preset_content_revision" in changed_fields:
            if self._suppress_next_preset_refresh:
                self._suppress_next_preset_refresh = False
                return
            if not self.isVisible():
                self._preset_refresh_pending = True
                return
            self.refresh_from_preset_switch()
        if "current_strategy_summary" in changed_fields or not changed_fields:
            self.update_current_strategy(state.current_strategy_summary)

    def show_loading(self):
        """Совместимость: показывает спиннер"""
        self._set_payload_loading(True)

    def show_success(self):
        """Совместимость: показывает галочку"""
        self._set_payload_loading(False)

    def _update_current_strategies_display(self):
        """Совместимость: обновляет отображение текущих стратегий"""
        try:
            selections = dict(self.target_selections or {})
            active_count = sum(1 for s in selections.values() if s and s != 'none')

            if active_count > 0:
                self.current_strategy_label.setText(
                    tr_catalog(
                        "page.z2_direct.current.active_count",
                        language=self._ui_language,
                        default="{count} активных",
                    ).format(count=active_count)
                )
            else:
                self.current_strategy_label.setText(
                    tr_catalog("page.z2_direct.current.not_selected", language=self._ui_language, default="Не выбрана")
                )
        except Exception as e:
            log(f"Ошибка обновления отображения: {e}", "DEBUG")

    def _start_process_monitoring(self):
        """Совместимость: заглушка для мониторинга процесса"""
        pass

    def disable_categories_for_filter(self, filter_key: str):
        """Совместимость: отключает элементы списка для фильтра."""
        log(f"disable_categories_for_filter: {filter_key}", "DEBUG")
        # В новой версии фильтры работают иначе

    def on_external_filters_changed(self, filters: dict):
        """Совместимость: обработчик внешних фильтров"""
        log(f"on_external_filters_changed: {filters}", "DEBUG")

    def on_external_sort_changed(self, sort_key: str):
        """Совместимость: обработчик внешней сортировки"""
        log(f"on_external_sort_changed: {sort_key}", "DEBUG")

    def reload_for_mode_change(self):
        """Совместимость: перезагружает страницу при смене режима"""
        self.refresh_from_preset_switch()

    def _show_info_popup(self):
        """Показывает информационный диалог о режиме прямого запуска."""
        try:
            box = MessageBox(
                tr_catalog("page.z2_direct.info.title", language=self._ui_language, default="Прямой запуск Zapret 2"),
                self._tr_info_text(),
                self.window(),
            )
            box.hideCancelButton()
            box.yesButton.setText(tr_catalog("common.ok.got_it", language=self._ui_language, default="Понятно"))
            box.exec()
        except Exception:
            pass

    def _tr_info_text(self) -> str:
        return tr_catalog(
            "page.z2_direct.info.body",
            language=self._ui_language,
            default=(
                "Здесь Вы можете тонко изменить стратегию для каждого target'а, который найден в выбранном source preset. "
                "Всего существует несколько фаз дурения (send, syndata, fake, multisplit и т.д.). "
                "Последовательность сама определяется программой.\n\n"
                "Вы можете править пресет вручную через txt-файл или выбирать готовые стратегии в этом меню. "
                "Каждая стратегия — это всего лишь набор аргументов, то есть техник (дурения или фуллинга) для того "
                "чтобы изменить содержимое пакетов по модели TCP/IP, которое отправляет Ваше устройство. "
                "Чтобы алгоритмы ТСПУ провайдера сбились и не заметили (или пропустили) запрещённый контент."
            ),
        )

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        self._rebuild_breadcrumb()

        if self._request_btn is not None:
            self._request_btn.setText(
                tr_catalog("page.z2_direct.request.button", language=self._ui_language, default="ОТКРЫТЬ ФОРМУ НА GITHUB")
            )
            self._request_btn.setToolTip(
                tr_catalog(
                    "page.z2_direct.request.hint",
                    language=self._ui_language,
                    default=(
                        "Хотите добавить новый сайт или сервис в Zapret 2? "
                        "Откройте готовую форму на GitHub и опишите, что нужно добавить в hostlist или ipset."
                    ),
                )
            )
        if self._expand_btn is not None:
            self._expand_btn.setText(
                tr_catalog("page.z2_direct.toolbar.expand", language=self._ui_language, default="Развернуть")
            )
            self._expand_btn.setToolTip(
                tr_catalog(
                    "page.z2_direct.toolbar.expand.description",
                    language=self._ui_language,
                    default="Развернуть все категории и target'ы в списке.",
                )
            )
        if self._collapse_btn is not None:
            self._collapse_btn.setText(
                tr_catalog("page.z2_direct.toolbar.collapse", language=self._ui_language, default="Свернуть")
            )
            self._collapse_btn.setToolTip(
                tr_catalog(
                    "page.z2_direct.toolbar.collapse.description",
                    language=self._ui_language,
                    default="Свернуть все категории и target'ы в списке.",
                )
            )
        if self._info_btn is not None:
            self._info_btn.setText(
                tr_catalog("page.z2_direct.toolbar.info", language=self._ui_language, default="Что это такое?")
            )
            self._info_btn.setToolTip(
                tr_catalog(
                    "page.z2_direct.toolbar.info.description",
                    language=self._ui_language,
                    default="Показать краткое объяснение по работе прямого запуска Zapret 2.",
                )
            )

        self._update_current_strategies_display()

    def _open_category_request_form(self):
        """Открывает GitHub-форму запроса на добавление сайтов в hostlist/ipset."""
        import webbrowser

        webbrowser.open(_CATEGORY_REQUEST_FORM_URL)
