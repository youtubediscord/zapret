"""Censorliber, [08.08.2025 1:02]
ну окей начнем с дискодра и ютуба

Censorliber, [08.08.2025 1:02]
а там добавим возможность отключения для обхода части сайтов

Censorliber, [08.08.2025 1:02]
хз как

Censorliber, [08.08.2025 1:02]
чет тту без идей

Censorliber, [08.08.2025 1:02]
или делать нулевую стратегию в качестве затычки в коде чтобы проще было или... прям кнопку добавлять
"""

"""
------ добавить в остьальное tcp по всем портам --------------------
--filter-tcp=4950-4955 --dpi-desync=fake,multidisorder --dpi-desync-split-pos=1,midsld --dpi-desync-repeats=8 --dpi-desync-fooling=md5sig,badseq --new

--filter-udp=443-9000 --ipset=ipset-all.txt --hostlist-domains=riotcdn.net,playvalorant.com,riotgames.com,pvp.net,rgpub.io,rdatasrv.net,riotcdn.com,riotgames.es,RiotClientServices.com,LeagueofLegends.com --dpi-desync=fake --dpi-desync-repeats=6 --dpi-desync-fake-quic=quic_initial_www_google_com.bin --new

------ ВАЖНЫЕ И НЕОБЫЧНЫЕ СТРАТЕГИИ по идее надо писать syndata в конце в порядке исключения для всех доменов--------------------
--filter-tcp=443 --dpi-desync=fake --dpi-desync-fooling=badsum --dpi-desync-fake-tls-mod=rnd,rndsni,padencap
--filter-tcp=443 --dpi-desync=fake --dpi-desync-ttl=4 --dpi-desync-fake-tls-mod=rnd,rndsni,padencap
--filter-tcp=443 --dpi-desync=split --dpi-desync-split-pos=1 --dpi-desync-autottl --dpi-desync-fooling=badseq --dpi-desync-repeats=8 --new
--filter-tcp=443 --dpi-desync=split --dpi-desync-split-pos=1 --dpi-desync-autottl --dpi-desync-fooling=badseq --dpi-desync-repeats=8 --dpi-desync-fake-tls-mod=rnd,dupsid,sni=www.google.com

--filter-tcp=443 --dpi-desync=split2 --dpi-desync-split-seqovl=681 --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq,hopbyhop2 --dpi-desync-split-seqovl-pattern=tls_clienthello_www_google_com.bin

--filter-tcp=443 --dpi-desync=split2 --dpi-desync-split-seqovl=681 --dpi-desync-split-pos=1 --dpi-desync-repeats=2 --dpi-desync-fooling=badseq,hopbyhop2 --dpi-desync-split-seqovl-pattern=tls_clienthello_www_google_com.bin

--filter-tcp=443 --dpi-desync=split2 --dpi-desync-repeats=2 --dpi-desync-split-seqovl=681 --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq,hopbyhop2 --dpi-desync-split-seqovl-pattern=tls_clienthello_www_google_com.bin --new
--filter-tcp=443 --dpi-desync=fake,split2 --dpi-desync-repeats=6 --dpi-desync-fooling=md5sig --dpi-desync-fake-tls=tls_clienthello_www_google_com.bin --new
--filter-tcp=443 --dpi-desync=fake,split2 --dpi-desync-split-seqovl=1 --dpi-desync-split-tls=sniext --dpi-desync-fake-tls=tls_clienthello_2.bin --dpi-desync-ttl=2 --new
--filter-tcp=443 --dpi-desync=fake,split2 --dpi-desync-split-seqovl=681 --dpi-desync-split-pos=1 --dpi-desync-fooling=badseq --dpi-desync-repeats=8 --dpi-desync-split-seqovl-pattern=tls_clienthello_www_google_com.bin --dpi-desync-fake-tls-mod=rnd,dupsid,sni=www.google.com --new
--filter-tcp=443 --dpi-desync=fake,multidisorder --dpi-desync-split-pos=midsld --dpi-desync-repeats=6 --dpi-desync-fooling=badseq,md5sig --new bol-van
--filter-tcp=443 --dpi-desync=fake,multidisorder --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=midsld+1 --dpi-desync-fooling=md5sig,badseq --dpi-desync-fake-tls=tls_clienthello_5.bin --dpi-desync-fake-tls-mod=rnd --dpi-desync-autottl --new
--filter-tcp=443 --dpi-desync=fake,multidisorder --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=sld+1 --dpi-desync-fake-tls=0x0F0F0E0F --dpi-desync-fake-tls=tls_clienthello_9.bin --dpi-desync-fake-tls-mod=rnd,dupsid --dpi-desync-fooling=md5sig --dpi-desync-autottl --dup=2 --dup-fooling=md5sig --dup-autottl --dup-cutoff=n3 --new
--filter-tcp=443 --dpi-desync=fake,fakedsplit --dpi-desync-split-pos=1 --dpi-desync-fake-tls=tls_clienthello_7.bin
--filter-tcp=443 --dpi-desync=fake,fakedsplit --dpi-desync-split-pos=1 --dpi-desync-fake-tls=tls_clienthello_7.bin --dpi-desync-fooling=badseq --dpi-desync-autottl
--filter-tcp=443 --dpi-desync=fake,fakedsplit --dpi-desync-split-pos=1 --dpi-desync-fake-tls=tls_clienthello_9.bin
--filter-tcp=443 --dpi-desync=fake,fakedsplit --dpi-desync-split-pos=1 --dpi-desync-fake-tls=tls_clienthello_9.bin --dpi-desync-fooling=badseq --dpi-desync-autottl
--filter-tcp=443 --dpi-desync=fake,disorder2 --dpi-desync-autottl=2 --dpi-desync-fooling=badseq --dpi-desync-fake-tls=tls_clienthello_www_google_com.bin

---------- LABEL_GAME ----------------
--filter-tcp=443 --dpi-desync=multisplit --dpi-desync-split-seqovl=293 --dpi-desync-split-seqovl-pattern=tls_clienthello_12.bin --new
--filter-tcp=443 --dpi-desync=multisplit --dpi-desync-split-seqovl=308 --dpi-desync-split-seqovl-pattern=tls_clienthello_15.bin --new
--filter-tcp=443 --dpi-desync=multisplit --dpi-desync-split-seqovl=308 --dpi-desync-split-seqovl-pattern=tls_clienthello_5.bin --dup=2 --dup-cutoff=n3 --new
--filter-tcp=443 --dpi-desync=multisplit --dpi-desync-split-seqovl=226 --dpi-desync-split-seqovl-pattern=tls_clienthello_18.bin --dup=2 --dup-cutoff=n3 --new

--comment Cloudflare WARP(1.1.1.1, 1.0.0.1)
--filter-tcp=443 --ipset-ip=162.159.36.1,162.159.46.1,2606:4700:4700::1111,2606:4700:4700::1001 --filter-l7=tls --dpi-desync=fake --dpi-desync-fake-tls=0x00 --dpi-desync-start=n2 --dpi-desync-cutoff=n3 --dpi-desync-fooling=md5sig --new

--comment WireGuard
--filter-l7=wireguard --dpi-desync=fake --dpi-desync-fake-wireguard=0x00 --dpi-desync-cutoff=n2

----------------------- LABEL_WARP -------------------------------
--filter-tcp=443 --dpi-desync=fake,multisplit --dpi-desync-split-seqovl=1 --dpi-desync-fooling=md5sig,badseq 
--filter-tcp=443 --dpi-desync=fake,multisplit --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=1 --dpi-desync-fake-tls=tls_clienthello_vk_com.bin --dpi-desync-ttl=5 --new
--filter-tcp=443 --dpi-desync=fake,multisplit --dpi-desync-fooling=md5sig --dpi-desync-autottl --new
--filter-tcp=443 --dpi-desync=fake,multisplit --dpi-desync-split-seqovl=1 --dpi-desync-split-pos=1,midsld --dpi-desync-fake-tls=0x0F0F0E0F --dpi-desync-fake-tls=tls_clienthello_9.bin --dpi-desync-fake-tls-mod=rnd,dupsid --dpi-desync-fooling=md5sig --dpi-desync-autottl --dup=2 --dup-fooling=md5sig --dup-autottl --dup-cutoff=n3 --new
--filter-tcp=443 --dpi-desync=fake,multisplit --dpi-desync-split-seqovl=1 --dpi-desync-fooling=md5sig,badseq --dpi-desync-fake-tls=tls_clienthello_7.bin --dpi-desync-fake-tls-mod=rnd,padencap --dpi-desync-autottl --new

--filter-tcp=443 --dpi-desync=fakeddisorder --dpi-desync-split-pos=2,midsld --dpi-desync-fakedsplit-pattern=tls_clienthello_1.bin --dpi-desync-fooling=badseq --new
--filter-tcp=443 --dpi-desync=fakeddisorder --dpi-desync-split-pos=2,midsld+1 --dpi-desync-fakedsplit-pattern=tls_clienthello_4.bin --dpi-desync-fooling=badseq --new

--filter-tcp=443 --dpi-desync=fakedsplit --dpi-desync-fooling=badseq --dpi-desync-split-pos=2,midsld-1 --dpi-desync-fakedsplit-pattern=tls_clienthello_4.bin --new
--filter-tcp=443 --dpi-desync=fakedsplit --dpi-desync-split-pos=7 --dpi-desync-fakedsplit-pattern=tls_clienthello_5.bin --dpi-desync-fooling=md5sig --dpi-desync-autottl --dup=2 --dup-fooling=md5sig --dup-autottl --dup-cutoff=n3 --new


--filter-tcp=443 --ipcache-hostname --dpi-desync=syndata,fake,multisplit --dpi-desync-split-pos=sld+1 --dpi-desync-fake-syndata=tls_clienthello_7.bin --dpi-desync-fake-tls=0x0F0F0E0F --dpi-desync-fake-tls=tls_clienthello_9.bin --dpi-desync-fake-tls-mod=rnd,dupsid --dpi-desync-fooling=md5sig --dpi-desync-autottl --dup=2 --dup-fooling=md5sig --dup-autottl --dup-cutoff=n3 --new

--filter-tcp=443 --dpi-desync=syndata --new
--filter-tcp=443 --dpi-desync=syndata,multisplit --dpi-desync-split-seqovl=1 --dpi-desync-fake-syndata=tls_clienthello_16.bin --dup=2 --dup-cutoff=n3 --new
--filter-tcp=443 --dpi-desync=syndata,multisplit --dpi-desync-split-seqovl=2 --dpi-desync-fake-syndata=tls_clienthello_16.bin --dup=2 --dup-cutoff=n3 --new

--filter-tcp=2099,5222,5223,8393-8400 --ipset=ipset-cloudflare.txt --dpi-desync=syndata --new

--filter-udp=5000-5500 --ipset=ipset-lol-ru.txt --dpi-desync=fake --dpi-desync-repeats=6 --new

--filter-tcp=2099 --ipset=ipset-lol-ru.txt --dpi-desync=syndata --new
--filter-tcp=5222,5223 --ipset=ipset-lol-euw.txt --dpi-desync=syndata --new
--filter-udp=5000-5500 --ipset=ipset-lol-euw.txt --dpi-desync=fake --dpi-desync-repeats=6

--filter-tcp=2000-8400 --dpi-desync=syndata
--filter-tcp=5222 --ipset="%LISTS%ipset-cloudflare.txt" --dpi-desync=syndata --new ^
--filter-tcp=5223 --ipset="%LISTS%ipset-cloudflare.txt" --dpi-desync=syndata --new ^

--filter-udp=8886 --ipset-ip=188.114.96.0/22 --dpi-desync=fake --dpi-desync-any-protocol --dpi-desync-fake-unknown-udp=quic_4.bin --dpi-desync-cutoff=d2 --dpi-desync-autottl --new
"""

# strategy_menu/strategy_lists_separated.py

"""
Модуль объединения стратегий в одну командную строку.
✅ Использует новую логику: base_filter из категории + техника из стратегии
✅ Автоматически определяет нужные фильтры портов по выбранным категориям
"""

import re
import os
from .constants import LABEL_RECOMMENDED, LABEL_GAME, LABEL_CAUTION, LABEL_EXPERIMENTAL, LABEL_STABLE
from log import log
from .strategies_registry import registry
from .strategies.blobs import build_args_with_deduped_blobs


def calculate_required_filters(category_strategies: dict) -> dict:
    """
    Автоматически вычисляет нужные фильтры портов на основе выбранных категорий.

    Использует filters_config.py для определения какие фильтры нужны.

    Args:
        category_strategies: dict {category_key: strategy_id}

    Returns:
        dict с флагами фильтров
    """
    from .filters_config import get_filter_for_category, FILTERS

    # Инициализируем все фильтры как False
    filters = {key: False for key in FILTERS.keys()}

    none_strategies = registry.get_none_strategies()

    for category_key, strategy_id in category_strategies.items():
        # Пропускаем неактивные категории
        if not strategy_id:
            continue
        none_id = none_strategies.get(category_key)
        if strategy_id == none_id or strategy_id == "none":
            continue

        # Получаем информацию о категории
        category_info = registry.get_category_info(category_key)
        if not category_info:
            continue

        # Получаем нужные фильтры через конфиг
        required_filters = get_filter_for_category(category_info)
        for filter_key in required_filters:
            filters[filter_key] = True

    log(f"Автоматически определены фильтры: TCP=[80={filters.get('tcp_80')}, 443={filters.get('tcp_443')}, 6568={filters.get('tcp_6568')}, warp={filters.get('tcp_warp')}, all={filters.get('tcp_all_ports')}], "
        f"UDP=[443={filters.get('udp_443')}, all={filters.get('udp_all_ports')}], "
        f"raw=[discord={filters.get('raw_discord')}, stun={filters.get('raw_stun')}, wg={filters.get('raw_wireguard')}]", "DEBUG")

    return filters


def _build_base_args_from_filters(
    lua_init: str,
    windivert_filter_folder: str,
    tcp_80: bool,
    tcp_443: bool,
    tcp_6568: bool,
    tcp_warp: bool,
    tcp_all_ports: bool,
    udp_443: bool,
    udp_all_ports: bool,
    raw_discord_media: bool,
    raw_stun: bool,
    raw_wireguard: bool,
) -> str:
    """
    Собирает базовые аргументы WinDivert из отдельных фильтров.

    Логика:
    - TCP порты перехватываются целиком через --wf-tcp-out
    - UDP порты перехватываются целиком через --wf-udp-out (нагружает CPU!)
    - Raw-part фильтры перехватывают только конкретные пакеты (экономят CPU)
    - Для режима direct_orchestra также добавляется --wf-tcp-in с теми же портами
    """
    from strategy_menu import get_strategy_launch_method

    parts = [lua_init]
    launch_method = get_strategy_launch_method()

    # === TCP порты ===
    tcp_port_parts = []
    if tcp_80:
        tcp_port_parts.append("80")
    if tcp_443:
        tcp_port_parts.append("443")
    if tcp_warp:
        tcp_port_parts.append("853")
    if tcp_6568:
        tcp_port_parts.append("6568")
    if tcp_all_ports:
        tcp_port_parts.append("444-65535")

    if tcp_port_parts:
        tcp_ports_str = ','.join(tcp_port_parts)
        parts.append(f"--wf-tcp-out={tcp_ports_str}")
        # ✅ Для режима Оркестратор Zapret 2 также перехватываем входящий TCP
        if launch_method == "direct_orchestra":
            parts.append(f"--wf-tcp-in={tcp_ports_str}")
    
    # === UDP порты ===
    udp_port_parts = []
    if udp_443:
        udp_port_parts.append("443")
    if udp_all_ports:
        udp_port_parts.append("444-65535")
    
    if udp_port_parts:
        parts.append(f"--wf-udp-out={','.join(udp_port_parts)}")
    
    # === Raw-part фильтры (экономят CPU) ===
    # Эти фильтры перехватывают только конкретные пакеты по сигнатуре
    
    if raw_discord_media:
        filter_path = os.path.join(windivert_filter_folder, "windivert_part.discord_media.txt")
        parts.append(f"--wf-raw-part=@{filter_path}")
    
    if raw_stun:
        filter_path = os.path.join(windivert_filter_folder, "windivert_part.stun.txt")
        parts.append(f"--wf-raw-part=@{filter_path}")
    
    if raw_wireguard:
        filter_path = os.path.join(windivert_filter_folder, "windivert_part.wireguard.txt")
        parts.append(f"--wf-raw-part=@{filter_path}")
    
    result = " ".join(parts)
    log(f"Собраны базовые аргументы: TCP=[80={tcp_80}, 443={tcp_443}, all={tcp_all_ports}], "
        f"UDP=[443={udp_443}, all={udp_all_ports}], "
        f"raw=[discord={raw_discord_media}, stun={raw_stun}, wg={raw_wireguard}]", "DEBUG")
    
    return result


def combine_strategies(*args, **kwargs) -> dict:
    """
    Объединяет выбранные стратегии в одну общую с правильным порядком командной строки.
    
    ✅ Применяет все настройки из UI:
    - Базовые аргументы (windivert)
    - Debug лог (если включено)
    - Удаление hostlist (если включено)
    - Удаление ipset (если включено)
    - Добавление wssize (если включено)
    - Замена other.txt на allzone.txt (если включено)
    """
    
    # Определяем источник выборов категорий
    if kwargs and not args:
        log("Используется новый способ вызова combine_strategies", "DEBUG")
        category_strategies = kwargs
    elif not args and not kwargs:
        log("Используются значения по умолчанию", "DEBUG")
        category_strategies = registry.get_default_selections()
    else:
        raise ValueError("Нельзя одновременно использовать позиционные и именованные аргументы")
    
    # ==================== БАЗОВЫЕ АРГУМЕНТЫ ====================
    from strategy_menu import get_debug_log_enabled
    from config import LUA_FOLDER, WINDIVERT_FILTER, LOGS_FOLDER

    # Lua библиотеки должны загружаться первыми (обязательно для Zapret 2)
    # Порядок загрузки важен:
    # 1. zapret-lib.lua - базовые функции
    # 2. zapret-antidpi.lua - функции десинхронизации
    # 3. custom_funcs.lua - пользовательские функции
    lua_lib_path = os.path.join(LUA_FOLDER, "zapret-lib.lua")
    lua_antidpi_path = os.path.join(LUA_FOLDER, "zapret-antidpi.lua")
    lua_auto_path = os.path.join(LUA_FOLDER, "zapret-auto.lua")
    custom_funcs_path = os.path.join(LUA_FOLDER, "custom_funcs.lua")
    # Пути БЕЗ кавычек - subprocess.Popen с списком аргументов сам правильно обрабатывает пути
    LUA_INIT = f'--lua-init=@{lua_lib_path} --lua-init=@{lua_antidpi_path} --lua-init=@{lua_auto_path} --lua-init=@{custom_funcs_path}'

    # ✅ Автоматически определяем нужные фильтры по выбранным категориям
    filters = calculate_required_filters(category_strategies)

    # Собираем базовые аргументы из автоматически определённых фильтров
    base_args = _build_base_args_from_filters(
        LUA_INIT,
        WINDIVERT_FILTER,
        filters['tcp_80'],
        filters['tcp_443'],
        filters['tcp_6568'],
        filters['tcp_warp'],
        filters['tcp_all_ports'],
        filters['udp_443'],
        filters['udp_all_ports'],
        filters['raw_discord'],
        filters['raw_stun'],
        filters['raw_wireguard'],
    )
    
    # ==================== СБОР АКТИВНЫХ КАТЕГОРИЙ ====================
    category_keys_ordered = registry.get_all_category_keys_by_command_order()
    none_strategies = registry.get_none_strategies()
    
    # Собираем активные категории с их аргументами
    active_categories = []  # [(category_key, args, category_info), ...]
    descriptions = []
    
    # Загружаем настройки out-range
    from strategy_menu import get_out_range_discord, get_out_range_youtube
    out_range_discord = get_out_range_discord()
    out_range_youtube = get_out_range_youtube()
    
    for category_key in category_keys_ordered:
        strategy_id = category_strategies.get(category_key)
        
        if not strategy_id:
            continue
            
        # Пропускаем "none" стратегии
        none_id = none_strategies.get(category_key)
        if strategy_id == none_id:
            continue
            
        # ✅ Получаем полные аргументы через registry (base_filter + техника)
        args = registry.get_strategy_args_safe(category_key, strategy_id)
        if args:
            # ✅ Заменяем out-range для Discord и YouTube категорий
            # ⚠️ НО: для direct_orchestra НЕ заменяем - стратегии уже содержат правильные out-range
            from strategy_menu import get_strategy_launch_method
            launch_method = get_strategy_launch_method()

            if launch_method != "direct_orchestra":
                if category_key == "discord" and out_range_discord > 0:
                    args = _replace_out_range(args, out_range_discord)
                elif category_key == "discord_voice" and out_range_discord > 0:
                    args = _replace_out_range(args, out_range_discord)
                elif category_key == "youtube" and out_range_youtube > 0:
                    args = _replace_out_range(args, out_range_youtube)
            
            category_info = registry.get_category_info(category_key)
            active_categories.append((category_key, args, category_info))
            
            # Добавляем в описание
            strategy_name = registry.get_strategy_name_safe(category_key, strategy_id)
            if category_info:
                descriptions.append(f"{category_info.full_name}: {strategy_name}")
    
    # ==================== СБОРКА КОМАНДНОЙ СТРОКИ ====================
    # Собираем аргументы категорий с разделителями --new
    category_args_parts = []
    
    for i, (category_key, args, category_info) in enumerate(active_categories):
        category_args_parts.append(args)
        
        # ✅ ИСПРАВЛЕНО: Добавляем --new только если:
        # 1. Категория требует разделитель (needs_new_separator=True)
        # 2. И это НЕ последняя активная категория
        is_last = (i == len(active_categories) - 1)
        if category_info and category_info.needs_new_separator and not is_last:
            category_args_parts.append("--new")
    
    # ✅ Дедуплицируем блобы: извлекаем все --blob=... из категорий,
    # убираем дубликаты и выносим в начало командной строки
    category_args_str = " ".join(category_args_parts)
    deduped_args = build_args_with_deduped_blobs([category_args_str])
    
    # Собираем финальную командную строку
    args_parts = []
    
    # ==================== DEBUG LOG ====================
    # Добавляется в начало командной строки если включено
    if get_debug_log_enabled():
        from datetime import datetime
        from log.log import cleanup_old_logs
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"zapret_winws2_debug_{timestamp}.log"
        log_path = os.path.join(LOGS_FOLDER, log_filename)
        # Создаём папку logs если её нет
        os.makedirs(LOGS_FOLDER, exist_ok=True)
        # Очищаем старые логи (оставляем максимум 50)
        cleanup_old_logs(LOGS_FOLDER)
        args_parts.append(f"--debug=@{log_path}")
        log(f"Debug лог включён: {log_path}", "INFO")
    
    if base_args:
        args_parts.append(base_args)
    if deduped_args:
        args_parts.append(deduped_args)
    
    combined_args = " ".join(args_parts)
    
    # ==================== ПРИМЕНЕНИЕ НАСТРОЕК ====================
    combined_args = _apply_settings(combined_args)
    
    # ==================== ФИНАЛИЗАЦИЯ ====================
    combined_description = " | ".join(descriptions) if descriptions else "Пользовательская комбинация"
    
    log(f"Создана комбинированная стратегия: {len(combined_args)} символов, {len(active_categories)} категорий", "DEBUG")
    
    return {
        "name": "Комбинированная стратегия",
        "description": combined_description,
        "version": "1.0", 
        "provider": "universal",
        "author": "Combined",
        "updated": "2024",
        "all_sites": True,
        "args": combined_args,
        "_is_builtin": True,
        "_active_categories": len(active_categories),
        **{f"_{key}_id": strategy_id for key, strategy_id in category_strategies.items()}
    }


def _apply_settings(args: str) -> str:
    """
    Применяет все пользовательские настройки к командной строке.
    
    ✅ Обрабатывает:
    - Удаление --hostlist (применить ко всем сайтам)
    - Удаление --ipset (применить ко всем IP)
    - Добавление --wssize 1:6
    - Замена other.txt на allzone.txt
    """
    from strategy_menu import (
        get_remove_hostlists_enabled,
        get_remove_ipsets_enabled,
        get_wssize_enabled,
        get_allzone_hostlist_enabled
    )
    
    result = args
    
    # ==================== ЗАМЕНА ALLZONE ====================
    # Делаем ДО удаления hostlist, чтобы замена сработала
    if get_allzone_hostlist_enabled():
        result = result.replace("--hostlist=other.txt", "--hostlist=allzone.txt")
        result = result.replace("--hostlist=other2.txt", "--hostlist=allzone.txt")
        log("Применена замена other.txt -> allzone.txt", "DEBUG")
    
    # ==================== УДАЛЕНИЕ HOSTLIST ====================
    if get_remove_hostlists_enabled():
        # Удаляем все варианты hostlist
        patterns = [
            r'--hostlist-domains=[^\s]+',
            r'--hostlist-exclude=[^\s]+',
            r'--hostlist=[^\s]+',
        ]
        for pattern in patterns:
            result = re.sub(pattern, '', result)
        
        # Очищаем лишние пробелы
        result = _clean_spaces(result)
        log("Удалены все --hostlist параметры", "DEBUG")
    
    # ==================== УДАЛЕНИЕ IPSET ====================
    if get_remove_ipsets_enabled():
        # Удаляем все варианты ipset
        patterns = [
            r'--ipset-ip=[^\s]+',
            r'--ipset-exclude=[^\s]+',
            r'--ipset=[^\s]+',
        ]
        for pattern in patterns:
            result = re.sub(pattern, '', result)
        
        # Очищаем лишние пробелы
        result = _clean_spaces(result)
        log("Удалены все --ipset параметры", "DEBUG")
    
    # ==================== ДОБАВЛЕНИЕ WSSIZE ====================
    if get_wssize_enabled():
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
    
    # Удаляем пустые --new (если после удаления hostlist/ipset остались)
    result = re.sub(r'--new\s+--new', '--new', result)
    result = re.sub(r'\s+--new\s*$', '', result)  # Trailing --new
    result = re.sub(r'^--new\s+', '', result)  # Leading --new
    
    return result.strip()


def _replace_out_range(args: str, value: int) -> str:
    """
    Заменяет --out-range в аргументах стратегии.
    Удаляет существующий --out-range и вставляет новый после --filter-tcp/--filter-udp.
    """
    # Удаляем существующий --out-range=...
    args = re.sub(r'--out-range=[^\s]+\s*', '', args)
    args = args.strip()
    
    # Вставляем новый --out-range после --filter-tcp=... или --filter-udp=...
    # Ищем паттерн --filter-tcp=... или --filter-udp=...
    match = re.search(r'(--filter-(?:tcp|udp|l7)=[^\s]+)', args)
    if match:
        insert_pos = match.end()
        args = args[:insert_pos] + f" --out-range=-d{value}" + args[insert_pos:]
    else:
        # Если нет filter, добавляем в начало
        args = f"--out-range=-d{value} {args}"
    
    return _clean_spaces(args)


def _clean_spaces(text: str) -> str:
    """Очищает множественные пробелы"""
    return ' '.join(text.split())


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def get_strategy_display_name(category_key: str, strategy_id: str) -> str:
    """Получает отображаемое имя стратегии"""
    if strategy_id == "none":
        return "⛔ Отключено"
    
    return registry.get_strategy_name_safe(category_key, strategy_id)


def get_active_categories_count(category_strategies: dict) -> int:
    """Подсчитывает количество активных категорий"""
    none_strategies = registry.get_none_strategies()
    count = 0
    
    for category_key, strategy_id in category_strategies.items():
        if strategy_id and strategy_id != none_strategies.get(category_key):
            count += 1
    
    return count


def validate_category_strategies(category_strategies: dict) -> list:
    """
    Проверяет корректность выбранных стратегий.
    Возвращает список ошибок (пустой если всё ок).
    """
    errors = []
    
    for category_key, strategy_id in category_strategies.items():
        if not strategy_id:
            continue
            
        if strategy_id == "none":
            continue
            
        # Проверяем существование категории
        category_info = registry.get_category_info(category_key)
        if not category_info:
            errors.append(f"Неизвестная категория: {category_key}")
            continue
        
        # Проверяем существование стратегии
        args = registry.get_strategy_args_safe(category_key, strategy_id)
        if args is None:
            errors.append(f"Стратегия '{strategy_id}' не найдена в категории '{category_key}'")
    
    return errors