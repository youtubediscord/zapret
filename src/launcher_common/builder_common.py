# launcher_common/builder_common.py

"""
Common utilities for legacy strategy combiners shared between V1 and V2.

Important:
- direct_zapret1/direct_zapret2 no longer build launch args from registry selections;
- those modes launch from the selected source preset via direct_preset_core;
- this module remains relevant only for legacy combiners such as orchestra/non-direct flows.
"""

import re
import os
from log import log
from .constants import LABEL_RECOMMENDED, LABEL_GAME, LABEL_CAUTION, LABEL_EXPERIMENTAL, LABEL_STABLE
from strategy_menu.strategies_registry import registry
from .blobs import build_args_with_deduped_blobs


def _is_direct_source_preset_launch() -> bool:
    try:
        from strategy_menu import get_strategy_launch_method

        return (get_strategy_launch_method() or "").strip().lower() in {"direct_zapret1", "direct_zapret2"}
    except Exception:
        return False


def calculate_required_filters(target_strategies: dict) -> dict:
    """
    Автоматически вычисляет нужные фильтры портов на основе выбранных target'ов.

    Используется legacy builder-слоем, который всё ещё работает через registry metadata.

    Args:
        target_strategies: dict {target_key: strategy_id}

    Returns:
        dict с флагами фильтров
    """
    from .port_filters import get_filter_for_target, FILTERS

    # Инициализируем все фильтры как False
    filters = {key: False for key in FILTERS.keys()}

    none_strategies = registry.get_none_strategies()

    for target_key, strategy_id in target_strategies.items():
        # Пропускаем неактивные target'ы
        if not strategy_id:
            continue
        none_id = none_strategies.get(target_key)
        if strategy_id == none_id or strategy_id == "none":
            continue

        # Получаем metadata target'а из legacy registry
        target_info = registry.get_target_info(target_key)
        if not target_info:
            continue

        # Получаем нужные фильтры через конфиг
        required_filters = get_filter_for_target(target_info)
        for filter_key in required_filters:
            filters[filter_key] = True

    log(f"Автоматически определены фильтры: TCP=[80={filters.get('tcp_80')}, 443={filters.get('tcp_443')}, 6568={filters.get('tcp_6568')}, warp={filters.get('tcp_warp')}, all={filters.get('tcp_all_ports')}], "
        f"UDP=[443={filters.get('udp_443')}, all={filters.get('udp_all_ports')}], "
        f"raw=[discord={filters.get('raw_discord')}, stun={filters.get('raw_stun')}, wg={filters.get('raw_wireguard')}]", "DEBUG")

    return filters


def _apply_settings(args: str) -> str:
    """
    Применяет все пользовательские настройки к командной строке.

    Обрабатывает:
    - Добавление --wssize 1:6
    """
    from strategy_menu import (
        get_wssize_enabled,
    )

    result = args

    # ==================== ДОБАВЛЕНИЕ WSSIZE ====================
    if not _is_direct_source_preset_launch() and get_wssize_enabled():
        # Добавляем --wssize 1:6 для TCP 443
        # Ищем место после базовых аргументов
        if "--wssize" not in result:
            # Вставляем после --wf-* аргументов
            if "--wf-" in result:
                # Находим конец wf аргументов
                wf_end = 0
                for match in re.finditer(r'--wf-[^\s]+=[^\s]+', result):
                    wf_end = max(wf_end, match.end())

                if wf_end > 0:
                    result = result[:wf_end] + " --wssize 1:6" + result[wf_end:]
                else:
                    result = "--wssize 1:6 " + result
            else:
                result = "--wssize 1:6 " + result

            log("Добавлен параметр --wssize 1:6", "DEBUG")

    # ==================== ФИНАЛЬНАЯ ОЧИСТКА ====================
    result = _clean_spaces(result)

    # Удаляем пустые --new (если вдруг после модификаций остались)
    result = re.sub(r'--new\s+--new', '--new', result)
    result = re.sub(r'\s+--new\s*$', '', result)  # Trailing --new
    result = re.sub(r'^--new\s+', '', result)  # Leading --new

    return result.strip()


def _clean_spaces(text: str) -> str:
    """Очищает множественные пробелы"""
    return ' '.join(text.split())


def get_strategy_display_name(target_key: str, strategy_id: str) -> str:
    """Получает отображаемое имя стратегии"""
    if strategy_id == "none":
        return "Отключено"

    return registry.get_strategy_name_safe(target_key, strategy_id)


def get_active_targets_count(target_strategies: dict) -> int:
    """Подсчитывает количество активных target'ов в legacy registry flow."""
    none_strategies = registry.get_none_strategies()
    count = 0

    for target_key, strategy_id in target_strategies.items():
        if strategy_id and strategy_id != none_strategies.get(target_key):
            count += 1

    return count


def validate_target_strategies(target_strategies: dict) -> list:
    """
    Проверяет корректность выбранных стратегий.
    Возвращает список ошибок (пустой если всё ок).
    """
    errors = []

    for target_key, strategy_id in target_strategies.items():
        if not strategy_id:
            continue

        if strategy_id == "none":
            continue

        # Проверяем существование target'а
        target_info = registry.get_target_info(target_key)
        if not target_info:
            errors.append(f"Неизвестный target: {target_key}")
            continue

        # Проверяем существование стратегии
        args = registry.get_strategy_args_safe(target_key, strategy_id)
        if args is None:
            errors.append(f"Стратегия '{strategy_id}' не найдена для target '{target_key}'")

    return errors
