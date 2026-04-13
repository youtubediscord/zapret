# filters/ui/targets_list.py
"""Единый список direct-target'ов с группировкой и фильтрацией."""

import time as _time

from types import SimpleNamespace
from typing import Callable, Dict, Iterable, Optional, Set
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSignal

from .filter_chip_button import FilterButtonGroup
from .collapsible_group import CollapsibleGroup
from .strategy_radio_item import StrategyRadioItem
from ui.theme import get_theme_tokens
from log.log import log



class TargetsList(QWidget):
    """
    Единый список target'ов с фильтрацией и группировкой.

    Структура:
    - FilterButtonGroup сверху (TCP, UDP, Discord, Voice, Games)
    - QScrollArea со сворачиваемыми группами по command_group

    Особенности:
    - Список создается ОДИН раз при загрузке
    - Фильтрация только через setVisible() - БЕЗ перестроения
    - Поддержка выбора стратегий для каждого target'а

    Signals:
        strategy_selected(str, str): (target_key, strategy_id)
        selections_changed(dict): весь словарь выборов
    """

    strategy_selected = pyqtSignal(str, str)
    selections_changed = pyqtSignal(dict)

    # Маппинг command_group -> отображаемое название
    GROUP_NAMES = {
        "youtube": "YouTube",
        "discord": "Discord",
        "telegram": "Telegram",
        "messengers": "Мессенджеры",
        "obsidian": "Обсидиан",
        "social": "Социальные сети",
        "music": "Музыка",
        "games": "Игры",
        "remote": "Удалённый доступ",
        "trackers": "Торренты",
        "streaming": "Стриминг",
        "hostlists": "Хостлисты",
        "ipsets": "IPset (по IP)",
        "github": "GitHub",
        "vpn": "VPN",
        "user": "Пользовательские",
        "default": "Прочее",
    }

    # Порядок групп
    GROUP_ORDER = [
        "youtube", "discord", "telegram", "obsidian", "messengers", "social",
        "music", "streaming", "games", "remote", "trackers",
        "hostlists", "github", "ipsets", "vpn", "user", "default"
    ]

    def __init__(
        self,
        parent=None,
        *,
        strategy_name_resolver: Callable[[str, str], str] | None = None,
        startup_scope: str | None = None,
    ):
        super().__init__(parent)
        self._targets = {}  # {target_key: TargetInfo}
        self._selections = {}  # {target_key: strategy_id}
        self._filter_modes = {}  # {target_key: "hostlist"|"ipset"}
        self._groups = {}  # {group_key: CollapsibleGroup}
        self._items = {}  # {target_key: StrategyRadioItem}
        self._target_to_group = {}  # {target_key: group_key}
        self._strategy_names_by_target = {}  # {target_key: {strategy_id: strategy_name}}
        self._built = False
        self._strategy_name_resolver = strategy_name_resolver
        self._startup_scope = str(startup_scope or "").strip() or None

        self._build_ui()

    def _log_startup_metric(self, section: str, elapsed_ms: float, *, extra: str | None = None) -> None:
        scope = self._startup_scope
        if not scope:
            return
        try:
            rounded = int(round(float(elapsed_ms)))
        except Exception:
            rounded = 0
        suffix = f" ({extra})" if extra else ""
        log(f"⏱ Startup UI Section: {scope} {section} {rounded}ms{suffix}", "⏱ STARTUP")

    def set_strategy_name_resolver(self, resolver: Callable[[str, str], str] | None) -> None:
        self._strategy_name_resolver = resolver

    def _build_ui(self):
        """Создает базовый UI (без вложенного scroll - используем scroll родителя)"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Панель фильтров
        self._filter_group = FilterButtonGroup(self)
        self._filter_group.filters_changed.connect(self._on_filters_changed)
        layout.addWidget(self._filter_group)

        # Контейнер для групп (без scroll - родитель BasePage уже scroll area)
        tokens = get_theme_tokens()
        self._content = QWidget()
        self._content.setStyleSheet(f"background: {'transparent' if tokens.is_light else 'transparent'};")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)
        self._content_layout.addStretch()

        layout.addWidget(self._content)

    def _build_targets_from_views(self, target_views, metadata: Optional[Dict[str, object]] = None) -> Dict[str, object]:
        """Build metadata-enriched target items from PresetTargetView[].

        The list composition must come from the source preset itself.
        Metadata is applied only to enrich UI labels, icons and grouping.
        """
        meta_map = metadata or {}
        built_targets: Dict[str, object] = {}
        fallback_order = 0

        for view in target_views or []:
            target_key = str(getattr(view, "target_key", "") or "").strip()
            if not target_key:
                continue

            display_name = str(getattr(view, "display_name", "") or target_key).strip() or target_key
            raw_meta = meta_map.get(target_key)
            if raw_meta is None:
                raw_meta = SimpleNamespace()

            built_targets[target_key] = SimpleNamespace(
                key=target_key,
                full_name=str(getattr(raw_meta, "full_name", "") or display_name).strip() or display_name,
                description=str(getattr(raw_meta, "description", "") or "").strip(),
                tooltip=str(getattr(raw_meta, "tooltip", "") or "").strip(),
                protocol=str(getattr(raw_meta, "protocol", "") or "").strip(),
                ports=str(getattr(raw_meta, "ports", "") or "").strip(),
                order=int(getattr(raw_meta, "order", fallback_order) or fallback_order),
                command_order=int(getattr(raw_meta, "command_order", fallback_order) or fallback_order),
                command_group=str(getattr(raw_meta, "command_group", "default") or "default").strip() or "default",
                icon_name=getattr(raw_meta, "icon_name", None),
                icon_color=str(getattr(raw_meta, "icon_color", "#2196F3") or "#2196F3"),
                base_filter=str(getattr(raw_meta, "base_filter", "") or "").strip(),
                base_filter_hostlist=str(getattr(raw_meta, "base_filter_hostlist", "") or "").strip(),
                base_filter_ipset=str(getattr(raw_meta, "base_filter_ipset", "") or "").strip(),
                strategy_type=str(getattr(raw_meta, "strategy_type", "tcp") or "tcp").strip() or "tcp",
                requires_all_ports=bool(getattr(raw_meta, "requires_all_ports", False)),
            )
            fallback_order += 1

        return built_targets

    def build_from_target_views(
        self,
        target_views,
        metadata: Optional[Dict[str, object]] = None,
        selections: Optional[Dict[str, str]] = None,
        strategy_names_by_target: Optional[Dict[str, Dict[str, str]]] = None,
        filter_modes: Optional[Dict[str, str]] = None,
    ) -> None:
        """Build the direct list from PresetTargetView[] plus optional metadata."""
        _t_total = _time.perf_counter()
        target_views = tuple(target_views or ())
        view_count = len(target_views)
        metadata_count = len(metadata or {})

        _t_metadata = _time.perf_counter()
        targets = self._build_targets_from_views(target_views, metadata)
        self._log_startup_metric(
            "_build_content.targets_list.build_from_target_views.metadata",
            (_time.perf_counter() - _t_metadata) * 1000,
            extra=f"views={view_count}, metadata={metadata_count}, built_targets={len(targets)}",
        )

        _t_build = _time.perf_counter()
        self.build_list(
            targets,
            selections=selections,
            strategy_names_by_target=strategy_names_by_target,
            filter_modes=filter_modes,
        )
        self._log_startup_metric(
            "_build_content.targets_list.build_from_target_views.build_list",
            (_time.perf_counter() - _t_build) * 1000,
            extra=f"targets={len(targets)}",
        )
        self._log_startup_metric(
            "_build_content.targets_list.build_from_target_views.total",
            (_time.perf_counter() - _t_total) * 1000,
            extra=f"targets={len(targets)}",
        )

    def build_list(
        self,
        targets: Dict,
        selections: Optional[Dict[str, str]] = None,
        strategy_names_by_target: Optional[Dict[str, Dict[str, str]]] = None,
        filter_modes: Optional[Dict[str, str]] = None,
    ):
        """
        Строит список target один раз.

        Args:
            targets: {target_key: TargetInfo} - все target
            selections: {target_key: strategy_id} - текущие выборы
        """
        if self._built:
            log("TargetsList: список уже построен, пропускаем", "DEBUG")
            return

        _t_total = _time.perf_counter()
        self._targets = targets
        self._selections = selections or {}
        self.set_strategy_names_by_target(strategy_names_by_target or {})
        self._filter_modes = filter_modes or {}

        # Группируем target'ы по command_group из metadata enrichment слоя.
        _t_grouping = _time.perf_counter()
        grouped = {}  # {group_key: [target_key, ...]}
        for target_key, target_info in targets.items():
            group_key = getattr(target_info, 'command_group', 'default') or 'default'
            if group_key not in grouped:
                grouped[group_key] = []
            grouped[group_key].append(target_key)
            self._target_to_group[target_key] = group_key
        self._log_startup_metric(
            "_build_content.targets_list.build_list.grouping",
            (_time.perf_counter() - _t_grouping) * 1000,
            extra=f"targets={len(targets)}, groups={len(grouped)}",
        )

        # Создаем группы в порядке GROUP_ORDER
        sort_elapsed_ms = 0.0
        create_group_elapsed_ms = 0.0
        create_item_elapsed_ms = 0.0
        add_item_elapsed_ms = 0.0
        insert_group_elapsed_ms = 0.0
        created_groups = 0
        created_items = 0

        for group_key in self.GROUP_ORDER:
            if group_key not in grouped:
                continue

            target_keys = grouped[group_key]
            if not target_keys:
                continue

            # Сортируем target внутри группы по order
            _t_sort = _time.perf_counter()
            target_keys.sort(key=lambda k: getattr(targets[k], 'order', 999))
            sort_elapsed_ms += (_time.perf_counter() - _t_sort) * 1000

            # Создаем группу
            group_name = self.GROUP_NAMES.get(group_key, group_key.title())
            _t_create_group = _time.perf_counter()
            group = CollapsibleGroup(group_key, group_name, self)
            group.toggled.connect(self._on_group_toggled)
            create_group_elapsed_ms += (_time.perf_counter() - _t_create_group) * 1000
            created_groups += 1

            # Добавляем target в группу
            for target_key in target_keys:
                target_info = targets[target_key]
                _t_create_item = _time.perf_counter()
                item = self._create_target_item(target_key, target_info)
                create_item_elapsed_ms += (_time.perf_counter() - _t_create_item) * 1000

                _t_add_item = _time.perf_counter()
                group.add_widget(item)
                add_item_elapsed_ms += (_time.perf_counter() - _t_add_item) * 1000
                self._items[target_key] = item
                created_items += 1

            self._groups[group_key] = group
            # Вставляем перед stretch
            _t_insert_group = _time.perf_counter()
            self._content_layout.insertWidget(
                self._content_layout.count() - 1, group
            )
            insert_group_elapsed_ms += (_time.perf_counter() - _t_insert_group) * 1000

        self._log_startup_metric(
            "_build_content.targets_list.build_list.group_sorting",
            sort_elapsed_ms,
            extra=f"groups={created_groups}",
        )
        self._log_startup_metric(
            "_build_content.targets_list.build_list.create_groups",
            create_group_elapsed_ms,
            extra=f"groups={created_groups}",
        )
        self._log_startup_metric(
            "_build_content.targets_list.build_list.create_items",
            create_item_elapsed_ms,
            extra=f"targets={created_items}",
        )
        self._log_startup_metric(
            "_build_content.targets_list.build_list.add_items",
            add_item_elapsed_ms,
            extra=f"targets={created_items}",
        )
        self._log_startup_metric(
            "_build_content.targets_list.build_list.insert_groups",
            insert_group_elapsed_ms,
            extra=f"groups={created_groups}",
        )

        self._built = True
        log(f"TargetsList: построено {len(self._groups)} групп, "
            f"{len(self._items)} target", "INFO")
        self._log_startup_metric(
            "_build_content.targets_list.build_list.total",
            (_time.perf_counter() - _t_total) * 1000,
            extra=f"groups={len(self._groups)}, targets={len(self._items)}",
        )

    def _get_strategy_name(self, target_key: str, strategy_id: str) -> str:
        """Получает название стратегии по ID без старого registry как источника истины."""
        sid = (strategy_id or "").strip() or "none"
        if sid == "none":
            return "Отключено"
        if sid == "custom":
            return "Свой набор"
        target_names = self._strategy_names_by_target.get(str(target_key or "").strip(), {})
        resolved = str(target_names.get(sid) or "").strip()
        if resolved:
            return resolved
        resolver = self._strategy_name_resolver
        if callable(resolver):
            try:
                resolved = str(resolver(target_key, sid) or "").strip()
                if resolved:
                    return resolved
            except Exception:
                pass
        return sid

    def _create_target_item(self, target_key: str, target_info) -> StrategyRadioItem:
        """Создает элемент для target."""
        # Получаем текущую выбранную стратегию
        selected_strategy = self._selections.get(target_key, 'none')
        strategy_name = self._get_strategy_name(target_key, selected_strategy)

        # Формируем описание
        desc_parts = []
        if hasattr(target_info, 'protocol') and target_info.protocol:
            desc_parts.append(target_info.protocol)
        if hasattr(target_info, 'ports') and target_info.ports:
            desc_parts.append(f"порты: {target_info.ports}")
        description = " | ".join(desc_parts) if desc_parts else ""

        # Получаем tooltip
        tooltip = getattr(target_info, 'tooltip', '') or ""
        # Metadata may contain literal "\n" sequences; decode them for Qt tooltips.
        if isinstance(tooltip, str) and "\\n" in tooltip:
            tooltip = tooltip.replace("\\n", "\n")

        # Determine list_type based on user's SELECTED filter mode (not availability)
        # 'ipset' if user selected ipset, 'hostlist' if user selected hostlist, None if neither available
        has_ipset = bool(getattr(target_info, 'base_filter_ipset', ''))
        has_hostlist = bool(getattr(target_info, 'base_filter_hostlist', ''))
        if has_ipset and has_hostlist:
            list_type = (self._filter_modes.get(target_key) or "hostlist").strip().lower()
            if list_type not in ("hostlist", "ipset"):
                list_type = "hostlist"
        elif has_ipset:
            list_type = 'ipset'
        elif has_hostlist:
            list_type = 'hostlist'
        else:
            list_type = None

        item = StrategyRadioItem(
            target_key=target_key,
            name=target_info.full_name,
            description=description,
            icon_name=getattr(target_info, 'icon_name', None),
            icon_color=getattr(target_info, 'icon_color', '#2196F3'),
            tooltip=tooltip,
            list_type=list_type,
            parent=self
        )
        item.item_activated.connect(self._on_item_clicked)

        # Устанавливаем выбранную стратегию
        item.set_strategy(selected_strategy, strategy_name)

        return item

    def _on_item_clicked(self, target_key: str):
        """Обработчик клика по элементу target'а."""
        strategy_id = self._selections.get(target_key, 'none')
        self.strategy_selected.emit(target_key, strategy_id)

    def _on_group_toggled(self, group_key: str, is_expanded: bool):
        """Обработчик сворачивания группы"""
        log(f"Группа {group_key} {'развернута' if is_expanded else 'свернута'}", "DEBUG")

    def _on_filters_changed(self, active_filters: Set[str]):
        """Обработчик изменения фильтров"""
        self._apply_filters(active_filters)

    def _apply_filters(self, active_filters: Set[str]):
        """
        Применяет фильтры к элементам (только setVisible).

        Args:
            active_filters: set с активными filter_key
        """
        if "all" in active_filters:
            # Показываем все
            for item in self._items.values():
                item.setVisible(True)
            for group in self._groups.values():
                group.setVisible(True)
            return

        # Определяем какие target'ы показывать
        visible_targets = set()

        for target_key, target_info in self._targets.items():
            show = False

            # TCP фильтр
            if "tcp" in active_filters:
                if hasattr(target_info, 'protocol') and 'TCP' in target_info.protocol.upper():
                    show = True

            # UDP фильтр
            if "udp" in active_filters:
                if hasattr(target_info, 'protocol'):
                    proto = target_info.protocol.upper()
                    if 'UDP' in proto or 'QUIC' in proto:
                        show = True

            # Discord фильтр
            if "discord" in active_filters:
                group = getattr(target_info, 'command_group', '')
                if group == 'discord' or 'discord' in target_key.lower():
                    show = True

            # Voice фильтр
            if "voice" in active_filters:
                strategy_type = getattr(target_info, 'strategy_type', '')
                if strategy_type == 'discord_voice' or 'voice' in target_key.lower():
                    show = True

            # Games фильтр
            if "games" in active_filters:
                requires_all = getattr(target_info, 'requires_all_ports', False)
                group = getattr(target_info, 'command_group', '')
                if requires_all or group == 'games':
                    show = True

            if show:
                visible_targets.add(target_key)

        # Применяем видимость к элементам
        for target_key, item in self._items.items():
            item.setVisible(target_key in visible_targets)

        # Скрываем пустые группы
        for group_key, group in self._groups.items():
            has_visible = False
            for target_key, item in self._items.items():
                if self._target_to_group.get(target_key) == group_key:
                    if item.isVisible():
                        has_visible = True
                        break
            group.setVisible(has_visible)

    def update_selection(self, target_key: str, strategy_id: str):
        """
        Обновляет выбор для target'а.

        Args:
            target_key: ключ target'а
            strategy_id: ID выбранной стратегии
        """
        self._selections[target_key] = strategy_id

        # Обновляем отображение элемента
        item = self._items.get(target_key)
        if item:
            strategy_name = self._get_strategy_name(target_key, strategy_id)
            item.set_strategy(strategy_id, strategy_name)

        self.selections_changed.emit(self._selections)

    def update_filter_mode(self, target_key: str, filter_mode: str):
        """Updates hostlist/ipset badge for a target (UI-only)."""
        self._apply_filter_mode(target_key, filter_mode)

    def get_selections(self) -> Dict[str, str]:
        """Возвращает текущие выборы"""
        return self._selections.copy()

    def set_selections(self, selections: Optional[Dict[str, str]]):
        """Устанавливает выборы для всех target'ов."""
        selections = selections or {}
        _t_total = _time.perf_counter()
        resolve_names_elapsed_ms = 0.0
        apply_to_items_elapsed_ms = 0.0

        # IMPORTANT:
        # Source preset может вернуть разреженный словарь только для target'ов,
        # которые реально есть в текущем пресете. Если обновлять только
        # пришедшие ключи, отсутствующие target'ы сохранят старое состояние UI.
        # UI state (stale "enabled" labels). Always sync every visible item.

        new_selections: Dict[str, str] = {}
        for target_key in (self._items or {}).keys():
            strategy_id = (selections.get(target_key) or "none")
            new_selections[target_key] = strategy_id

            item = self._items.get(target_key)
            if item:
                _t_resolve = _time.perf_counter()
                strategy_name = self._get_strategy_name(target_key, strategy_id)
                resolve_names_elapsed_ms += (_time.perf_counter() - _t_resolve) * 1000

                _t_apply = _time.perf_counter()
                item.set_strategy(strategy_id, strategy_name)
                apply_to_items_elapsed_ms += (_time.perf_counter() - _t_apply) * 1000

        # Сохраняем лишние ключи на случай, если в пресете есть target,
        # который ещё не попал в текущий список UI.
        for target_key, strategy_id in selections.items():
            if target_key not in new_selections:
                new_selections[target_key] = strategy_id

        self._selections = new_selections
        self._log_startup_metric(
            "targets_list.set_selections.resolve_names",
            resolve_names_elapsed_ms,
            extra=f"visible_targets={len(self._items)}, incoming={len(selections)}",
        )
        self._log_startup_metric(
            "targets_list.set_selections.apply_to_items",
            apply_to_items_elapsed_ms,
            extra=f"visible_targets={len(self._items)}",
        )
        self._log_startup_metric(
            "targets_list.set_selections.total",
            (_time.perf_counter() - _t_total) * 1000,
            extra=f"visible_targets={len(self._items)}, stored={len(self._selections)}",
        )

    def set_strategy_names_by_target(self, strategy_names_by_target: Optional[Dict[str, Dict[str, str]]]) -> None:
        names = strategy_names_by_target or {}
        normalized: Dict[str, Dict[str, str]] = {}
        for target_key, strategy_map in names.items():
            key = str(target_key or "").strip()
            if not key:
                continue
            normalized[key] = {
                str(strategy_id or "").strip(): str(strategy_name or "").strip()
                for strategy_id, strategy_name in (strategy_map or {}).items()
                if str(strategy_id or "").strip()
            }
        self._strategy_names_by_target = normalized

    def set_filter_modes(
        self,
        filter_modes: Optional[Dict[str, str]],
        *,
        target_keys: Optional[Iterable[str]] = None,
    ) -> None:
        """Пакетно обновляет badge Hostlist/IPset и пишет одну агрегированную метрику."""
        modes = filter_modes or {}
        keys = list(target_keys) if target_keys is not None else list((self._items or {}).keys())
        _t_total = _time.perf_counter()

        updated_count = 0
        for target_key in keys:
            self._apply_filter_mode(target_key, modes.get(target_key) or "")
            updated_count += 1

        self._log_startup_metric(
            "targets_list.set_filter_modes.total",
            (_time.perf_counter() - _t_total) * 1000,
            extra=f"updated={updated_count}",
        )

    def reset_filters(self):
        """Сбрасывает фильтры"""
        self._filter_group.reset()

    def expand_all(self):
        """Разворачивает все группы"""
        for group in self._groups.values():
            group.set_expanded(True)

    def collapse_all(self):
        """Сворачивает все группы"""
        for group in self._groups.values():
            group.set_expanded(False)

    def get_target_item(self, target_key: str) -> Optional[StrategyRadioItem]:
        """Возвращает элемент target."""
        return self._items.get(target_key)

    def _apply_filter_mode(self, target_key: str, filter_mode: str) -> None:
        target_info = self._targets.get(target_key)
        item = self._items.get(target_key)

        has_ipset = bool(getattr(target_info, "base_filter_ipset", "")) if target_info else False
        has_hostlist = bool(getattr(target_info, "base_filter_hostlist", "")) if target_info else False

        # If target doesn't support list-mode toggle, ensure badge is cleared.
        if not (has_ipset or has_hostlist):
            self._filter_modes.pop(target_key, None)
            if item:
                item.set_list_type(None)
            return

        # If only one mode exists, show that fixed badge (consistent with build_list()).
        if has_ipset and not has_hostlist:
            self._filter_modes[target_key] = "ipset"
            if item:
                item.set_list_type("ipset")
            return
        if has_hostlist and not has_ipset:
            self._filter_modes[target_key] = "hostlist"
            if item:
                item.set_list_type("hostlist")
            return

        # Both available: use the selected mode (fallback to hostlist).
        mode = (filter_mode or "").strip().lower()
        if mode not in ("hostlist", "ipset"):
            mode = "hostlist"
        self._filter_modes[target_key] = mode
        if item:
            item.set_list_type(mode)
