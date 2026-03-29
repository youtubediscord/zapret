# ui/pages/zapret2/direct_zapret2_page.py
"""
Страница выбора стратегий для режима direct_zapret2 (preset-based).
При клике на target открывается отдельная страница StrategyDetailPage.
"""

from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QFrame, QSizePolicy
)
import qtawesome as qta

from ui.pages.base_page import BasePage
from ui.compat_widgets import SettingsCard, ActionButton, RefreshButton
from ui.widgets import PresetTargetsList
from ui.theme import get_theme_tokens
from ui.text_catalog import tr as tr_catalog
from log import log

try:
    from qfluentwidgets import CaptionLabel, BodyLabel, PushButton, TransparentPushButton
    _HAS_FLUENT_LABELS = True
except ImportError:
    from PyQt6.QtWidgets import QLabel as BodyLabel, QLabel as CaptionLabel, QPushButton as PushButton
    TransparentPushButton = PushButton
    _HAS_FLUENT_LABELS = False

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
        self._breadcrumb = None
        try:
            from qfluentwidgets import BreadcrumbBar as _BreadcrumbBar
            self._breadcrumb = _BreadcrumbBar()
            self._rebuild_breadcrumb()
            self._breadcrumb.currentItemChanged.connect(self._on_breadcrumb_item_changed)
            self.layout.insertWidget(0, self._breadcrumb)
        except Exception:
            self._breadcrumb = None
            # Fallback: original back button
            try:
                import qtawesome as _qta
                from PyQt6.QtCore import QSize as _QSize
                from PyQt6.QtWidgets import QHBoxLayout as _QHBoxLayout, QWidget as _QWidget
                from ui.theme import get_theme_tokens as _get_tokens
                _tokens = _get_tokens()
                _back_btn = TransparentPushButton()
                _back_btn.setText(
                    tr_catalog("page.z2_direct.back.control", language=self._ui_language, default="Управление")
                )
                _back_btn.setIcon(_qta.icon("fa5s.chevron-left", color=_tokens.fg_muted))
                _back_btn.setIconSize(_QSize(12, 12))
                _back_btn.clicked.connect(self.back_clicked.emit)
                self._back_btn = _back_btn
                _back_layout = _QHBoxLayout()
                _back_layout.setContentsMargins(0, 0, 0, 0)
                _back_layout.setSpacing(0)
                _back_layout.addWidget(_back_btn)
                _back_layout.addStretch()
                _back_widget = _QWidget()
                _back_widget.setLayout(_back_layout)
                self.layout.insertWidget(0, _back_widget)
            except Exception:
                pass

        self.target_selections = {}
        self._targets_list = None
        self._built = False
        self._build_scheduled = False
        self._strategy_set_snapshot = None
        self._telegram_hint_label = None
        self._telegram_btn = None
        self._expand_btn = None
        self._collapse_btn = None
        self._info_btn = None
        self._back_btn = None

        # Совместимость со старым кодом
        self.content_layout = self.layout
        self.content_container = self.content

        # Заглушки для совместимости с main_window.py
        self.select_strategy_btn = PushButton()
        self.select_strategy_btn.hide()

        self.current_strategy_label = BodyLabel(
            tr_catalog("page.z2_direct.current.not_selected", language=self._ui_language, default="Не выбрана")
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

    def showEvent(self, event):
        """При показе страницы загружаем/обновляем контент"""
        super().showEvent(event)
        self._rebuild_breadcrumb()  # Fix state if user navigated away via breadcrumb

        # Если режим direct_zapret2 (basic/advanced) переключился в другом месте,
        # перестраиваем список при следующем показе страницы.
        try:
            from strategy_menu.ui_prefs_store import get_direct_zapret2_ui_mode
            current_set = get_direct_zapret2_ui_mode()
        except Exception:
            current_set = None

        if self._built and current_set != getattr(self, "_strategy_set_snapshot", None):
            try:
                self._reload_strategies()
                return
            except Exception:
                pass

        if self._built:
            try:
                self.refresh_from_preset_switch()
            except Exception:
                pass

        if not self._built and not self._build_scheduled:
            self._build_scheduled = True
            QTimer.singleShot(0, self._build_content)

    def _build_content(self):
        """Строит содержимое страницы"""
        try:
            self._build_scheduled = False
            if self._built:
                return

            from core.presets.direct_facade import DirectPresetFacade

            facade = DirectPresetFacade.from_launch_method("direct_zapret2")
            target_views = facade.list_target_views() or []
            target_items = facade.get_target_ui_items() or {}
            self.target_selections = facade.get_strategy_selections() or {}
            filter_modes = {key: facade.get_target_filter_mode(key) for key in target_items.keys()}

            # Карточка с кнопкой Telegram (выделенная, акцентная)
            telegram_card = SettingsCard()
            telegram_layout = QHBoxLayout()
            telegram_layout.setContentsMargins(0, 0, 0, 0)
            telegram_layout.setSpacing(16)

            # Описательный текст слева
            _hint_text = tr_catalog(
                "page.z2_direct.telegram.hint",
                language=self._ui_language,
                default=(
                    "Хотите добавить новый сайт или сервис в direct preset? Напишите нам. "
                    "Запрос можно оставить на сайте-форуме в разделе Zapret GUI."
                ),
            )
            telegram_hint = CaptionLabel(_hint_text)
            self._telegram_hint_label = telegram_hint
            telegram_hint.setWordWrap(True)
            telegram_hint.setContentsMargins(12, 0, 0, 0)
            telegram_hint.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            telegram_hint.setMinimumWidth(0)
            telegram_layout.addWidget(telegram_hint, 1)

            # Кнопка Telegram
            telegram_btn = ActionButton(
                tr_catalog("page.z2_direct.telegram.button", language=self._ui_language, default="ОТКРЫТЬ TELEGRAM БОТА"),
                "fa5b.telegram-plane",
            )
            self._telegram_btn = telegram_btn
            telegram_btn.setFixedHeight(36)
            telegram_btn.clicked.connect(self._open_custom_domains)
            telegram_layout.addWidget(telegram_btn, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            telegram_card.add_layout(telegram_layout)
            self.content_layout.addWidget(telegram_card)

            # Панель действий (toolbar)
            actions_card = SettingsCard()
            actions_layout = QHBoxLayout()
            actions_layout.setSpacing(8)

            self._reload_btn = RefreshButton()
            self._reload_btn.clicked.connect(self._reload_strategies)
            actions_layout.addWidget(self._reload_btn)

            expand_btn = ActionButton(
                tr_catalog("page.z2_direct.toolbar.expand", language=self._ui_language, default="Развернуть"),
                "fa5s.expand-alt",
            )
            expand_btn.clicked.connect(self._expand_all)
            actions_layout.addWidget(expand_btn)
            self._expand_btn = expand_btn

            collapse_btn = ActionButton(
                tr_catalog("page.z2_direct.toolbar.collapse", language=self._ui_language, default="Свернуть"),
                "fa5s.compress-alt",
            )
            collapse_btn.clicked.connect(self._collapse_all)
            actions_layout.addWidget(collapse_btn)
            self._collapse_btn = collapse_btn

            info_btn = ActionButton(
                tr_catalog("page.z2_direct.toolbar.info", language=self._ui_language, default="Что это такое?"),
                "fa5s.question-circle",
                accent=False,
            )
            info_btn.clicked.connect(self._show_info_popup)
            actions_layout.addWidget(info_btn)
            self._info_btn = info_btn

            actions_layout.addStretch()

            actions_card.add_layout(actions_layout)
            self.content_layout.addWidget(actions_card)

            # Выборы уже загружены в начале _build_content()

            # Список target'ов (без правой панели - теперь отдельная страница)
            self._targets_list = PresetTargetsList(self, strategy_name_resolver=self._strategy_name)
            self._targets_list.strategy_selected.connect(self._on_target_clicked)
            self._targets_list.selections_changed.connect(self._on_selections_changed)

            # Строим список из PresetTargetView[]; metadata используется только для enrich UI.
            self._targets_list.build_from_target_views(
                target_views,
                metadata=target_items,
                selections=self.target_selections,
                filter_modes=filter_modes,
            )

            self.content_layout.addWidget(self._targets_list, 1)

            # Запоминаем текущий UI-режим direct_zapret2, чтобы понимать,
            # нужно ли перестраивать страницу после возврата.
            try:
                from strategy_menu.ui_prefs_store import get_direct_zapret2_ui_mode
                self._strategy_set_snapshot = get_direct_zapret2_ui_mode()
            except Exception:
                self._strategy_set_snapshot = None

            self._built = True
            log("Zapret2StrategiesPageNew построена", "INFO")

        except Exception as e:
            self._build_scheduled = False
            log(f"Ошибка построения Zapret2StrategiesPageNew: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")

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
            from dpi.zapret2_core_restart import trigger_dpi_reload

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
                on_dpi_reload_needed=lambda: trigger_dpi_reload(
                    self.parent_app,
                    reason="strategy_changed"
                )
            )
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
        from dpi.zapret2_core_restart import trigger_dpi_reload
        trigger_dpi_reload(
            self.parent_app,
            reason="strategy_changed"
        )

    def _reload_strategies(self):
        """Перезагружает стратегии"""
        if hasattr(self, '_reload_btn'):
            self._reload_btn.set_loading(True)
        try:
            # Перестраиваем UI
            self._built = False
            self._build_scheduled = False

            # Удаляем старые виджеты, сохраняя заголовки.
            # Ищем subtitle_label динамически, т.к. back_button может быть
            # вставлен в позицию 0, сдвигая subtitle с индекса 1 на 2.
            _keep = 2  # fallback: title + subtitle
            _sub = getattr(self, "subtitle_label", None)
            if _sub is not None:
                for _i in range(min(self.content_layout.count(), 6)):
                    _item = self.content_layout.itemAt(_i)
                    if _item and _item.widget() is _sub:
                        _keep = _i + 1
                        break
            while self.content_layout.count() > _keep:
                item = self.content_layout.takeAt(_keep)
                if item.widget():
                    item.widget().deleteLater()

            self._targets_list = None
            self._build_content()

            log("Стратегии перезагружены", "INFO")

        except Exception as e:
            log(f"Ошибка перезагрузки: {e}", "ERROR")
        finally:
            if hasattr(self, '_reload_btn'):
                self._reload_btn.set_loading(False)

    def refresh_from_preset_switch(self):
        """
        Перечитывает активный пресет и обновляет UI списка (без перестроения).
        Вызывается асинхронно из MainWindow после активации пресета.
        """
        try:
            from core.presets.direct_facade import DirectPresetFacade

            facade = DirectPresetFacade.from_launch_method("direct_zapret2")
            target_items = facade.get_target_ui_items() or {}
            self.target_selections = facade.get_strategy_selections() or {}
            filter_modes = {key: facade.get_target_filter_mode(key) for key in target_items.keys()}

            if self._targets_list:
                self._targets_list.set_selections(self.target_selections)

                # Sync badges for ALL targets so stale/invalid badges disappear.
                for target_key in target_items.keys():
                    try:
                        self._targets_list.update_filter_mode(target_key, (filter_modes or {}).get(target_key))
                    except Exception:
                        continue

            # Совместимость: обновить счетчик активных
            self._update_current_strategies_display()

        except Exception as e:
            log(f"Ошибка refresh_from_preset_switch: {e}", "DEBUG")

    def _strategy_name(self, target_key: str, strategy_id: str) -> str:
        sid = (strategy_id or "").strip() or "none"
        if sid == "none":
            return tr_catalog("page.z2_direct.strategy.off", language=self._ui_language, default="Отключено")
        if sid == "custom":
            return tr_catalog("page.z2_direct.strategy.custom", language=self._ui_language, default="Свой набор")
        try:
            from core.presets.direct_facade import DirectPresetFacade

            strategies = DirectPresetFacade.from_launch_method("direct_zapret2").get_target_strategies(target_key) or {}
            entry = strategies.get(sid) or {}
            return str(entry.get("name") or sid)
        except Exception:
            return sid

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
        if name and name != "Автостарт DPI отключен":
            self.current_strategy_label.setText(name)
        else:
            self.current_strategy_label.setText(
                tr_catalog("page.z2_direct.current.not_selected", language=self._ui_language, default="Не выбрана")
            )

    def show_loading(self):
        """Совместимость: показывает спиннер"""
        pass

    def show_success(self):
        """Совместимость: показывает галочку"""
        pass

    def _update_current_strategies_display(self):
        """Совместимость: обновляет отображение текущих стратегий"""
        try:
            from core.presets.direct_facade import DirectPresetFacade

            selections = DirectPresetFacade.from_launch_method("direct_zapret2").get_strategy_selections() or {}
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
        self._reload_strategies()

    def _show_info_popup(self):
        """Показывает информационный диалог о режиме прямого запуска."""
        try:
            from qfluentwidgets import MessageBox
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

        if self._back_btn is not None:
            self._back_btn.setText(
                tr_catalog("page.z2_direct.back.control", language=self._ui_language, default="Управление")
            )

        if self._telegram_hint_label is not None:
            self._telegram_hint_label.setText(
                tr_catalog(
                    "page.z2_direct.telegram.hint",
                    language=self._ui_language,
                    default=(
                        "Хотите добавить новый сайт или сервис в direct preset? Напишите нам. "
                        "Запрос можно оставить на сайте-форуме в разделе Zapret GUI."
                    ),
                )
            )
        if self._telegram_btn is not None:
            self._telegram_btn.setText(
                tr_catalog("page.z2_direct.telegram.button", language=self._ui_language, default="ОТКРЫТЬ TELEGRAM БОТА")
            )
        if self._expand_btn is not None:
            self._expand_btn.setText(
                tr_catalog("page.z2_direct.toolbar.expand", language=self._ui_language, default="Развернуть")
            )
        if self._collapse_btn is not None:
            self._collapse_btn.setText(
                tr_catalog("page.z2_direct.toolbar.collapse", language=self._ui_language, default="Свернуть")
            )
        if self._info_btn is not None:
            self._info_btn.setText(
                tr_catalog("page.z2_direct.toolbar.info", language=self._ui_language, default="Что это такое?")
            )

        self._update_current_strategies_display()

    def _open_custom_domains(self):
        """Открывает пост в Telegram для запроса добавления сайтов"""
        from config.telegram_links import open_telegram_link
        open_telegram_link("bypassblock", post=1359)
