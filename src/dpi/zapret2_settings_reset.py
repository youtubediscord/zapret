r"""
dpi/zapret2_settings_reset.py - Сброс настроек категории на значения по умолчанию

Настройки категории хранятся в реестре:
- Путь: HKEY_CURRENT_USER\Software\Zapret2Reg\CategorySyndata (или Zapret2DevReg)
- Ключ: category_key (например "youtube_https")
- Формат: JSON строка

Использование:
    from dpi.zapret2_settings_reset import (
        DEFAULT_CATEGORY_SETTINGS,
        get_default_category_settings,
        reset_category_settings,
        reset_all_categories_settings
    )

    # Получить дефолты
    defaults = get_default_category_settings()

    # Сбросить одну категорию
    reset_category_settings("youtube_https")

    # Сбросить все категории
    reset_all_categories_settings()
"""

from log import log


# ═══════════════════════════════════════════════════════════════════════════════
# ДЕФОЛТНЫЕ НАСТРОЙКИ КАТЕГОРИИ (FALLBACK)
# ═══════════════════════════════════════════════════════════════════════════════

# Fallback настройки для категорий, НЕ включённых в DEFAULT_PRESET_CONTENT
DEFAULT_CATEGORY_SETTINGS = {
    # ═══════ SYNDATA параметры ═══════
    "enabled": True,
    "blob": "tls_google",
    "tls_mod": "none",
    "autottl_delta": -2,
    "autottl_min": 3,
    "autottl_max": 20,
    "tcp_flags_unset": "none",

    # ═══════ OUT RANGE параметры ═══════
    "out_range": 8,
    "out_range_mode": "n",  # "n" (packets count) or "d" (delay)

    # ═══════ SEND параметры ═══════
    "send_enabled": True,
    "send_repeats": 2,
    "send_ip_ttl": 0,
    "send_ip6_ttl": 0,
    "send_ip_id": "none",
    "send_badsum": False,
}


# ═══════════════════════════════════════════════════════════════════════════════
# API ФУНКЦИИ
# ═══════════════════════════════════════════════════════════════════════════════

def get_default_category_settings(category_key: str = None) -> dict:
    """
    Возвращает дефолтные настройки для категории.

    Парсит DEFAULT_PRESET_CONTENT и извлекает настройки для указанной категории.
    Если категория включена в Default.txt - берёт настройки оттуда.
    Если категории нет в Default.txt - возвращает DEFAULT_CATEGORY_SETTINGS (fallback).

    Args:
        category_key: Имя категории (например "youtube", "discord").
                     Если None - возвращает fallback настройки.

    Returns:
        dict: Словарь с дефолтными настройками категории
    """
    # Fallback если category_key не указан
    if category_key is None:
        return DEFAULT_CATEGORY_SETTINGS.copy()

    try:
        from preset_zapret2.preset_defaults import (
            get_default_category_settings as get_parsed_defaults,
            get_category_default_syndata
        )

        # Получаем все настройки из DEFAULT_PRESET_CONTENT
        all_defaults = get_parsed_defaults()

        # Ищем настройки для нашей категории
        if category_key not in all_defaults:
            # Категории нет в DEFAULT_PRESET_CONTENT → возвращаем fallback
            log(f"Категория {category_key} не найдена в DEFAULT_PRESET_CONTENT, используем fallback", "DEBUG")
            return DEFAULT_CATEGORY_SETTINGS.copy()

        # Парсим syndata настройки из DEFAULT_PRESET_CONTENT
        syndata_settings = get_category_default_syndata(category_key, protocol="tcp")

        log(f"Используем настройки из DEFAULT_PRESET_CONTENT для {category_key}", "DEBUG")
        return syndata_settings

    except Exception as e:
        log(f"Ошибка получения дефолтных настроек для {category_key}: {e}", "WARNING")
        import traceback
        log(traceback.format_exc(), "DEBUG")
        return DEFAULT_CATEGORY_SETTINGS.copy()


def reset_category_settings(category_key: str) -> bool:
    """
    Сбрасывает настройки категории на значения по умолчанию.

    Использует PresetManager для сброса настроек в активном пресете.
    Это автоматически:
    - Сбрасывает syndata на дефолты
    - Устанавливает filter_mode = "hostlist"
    - Устанавливает sort_order = "default"
    - Сохраняет preset файл
    - Вызывает DPI reload через callback

    Args:
        category_key: Ключ категории (например "youtube")

    Returns:
        True если успешно, False при ошибке
    """
    try:
        from core.presets.direct_facade import DirectPresetFacade

        manager = DirectPresetFacade.from_launch_method("direct_zapret2")
        success = manager.reset_category_settings(category_key)

        if success:
            log(f"Настройки категории {category_key} сброшены через DirectPresetFacade", "INFO")
        else:
            log(f"Не удалось сбросить настройки категории {category_key}", "WARNING")

        return success

    except Exception as e:
        log(f"Ошибка сброса настроек категории {category_key}: {e}", "ERROR")
        import traceback
        log(traceback.format_exc(), "DEBUG")
        return False


def reset_all_categories_settings() -> bool:
    """
    Сбрасывает настройки ВСЕХ категорий.

    Получает список категорий из активного пресета и сбрасывает каждую.

    Returns:
        True если все категории успешно сброшены, False при ошибке
    """
    try:
        from core.presets.direct_facade import DirectPresetFacade

        manager = DirectPresetFacade.from_launch_method("direct_zapret2")
        preset = manager.get_active_preset()

        if not preset:
            log("Нет активного пресета для сброса категорий", "WARNING")
            return False

        if not preset.categories:
            log("Нет категорий в активном пресете", "INFO")
            return True

        # Сбрасываем каждую категорию
        all_success = True
        reset_count = 0

        for category_key in list(preset.categories.keys()):
            success = manager.reset_category_settings(category_key)
            if success:
                reset_count += 1
            else:
                all_success = False
                log(f"Ошибка сброса категории {category_key}", "WARNING")

        log(f"Сброшено {reset_count} из {len(preset.categories)} категорий", "INFO")
        return all_success

    except Exception as e:
        log(f"Ошибка сброса всех настроек категорий: {e}", "ERROR")
        import traceback
        log(traceback.format_exc(), "DEBUG")
        return False


# Алиас для обратной совместимости
reset_all_category_settings = reset_all_categories_settings
