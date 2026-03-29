# zapret2_launcher/strategy_builder.py
"""
Strategy list builder for Zapret 2 (winws2.exe).

Full version WITH:
- --lua-init (Lua library loading)
- --wf-tcp-out= (V2 syntax)
- --wf-udp-out= (V2 syntax)
- --wf-tcp-in= (orchestra mode)

This module is designed specifically for Zapret 2 (winws2.exe) and does NOT
support Zapret 1 (winws.exe). For V1 compatibility, use strategy_lists_v1.py.

Important:
- direct_zapret2 now launches from the selected source preset via direct_preset_core;
- this builder remains a legacy combiner for orchestra and other registry-driven flows.
"""

import re
import os
from log import log
from strategy_menu.strategies_registry import registry
from launcher_common.blobs import extract_and_dedupe_blobs, get_user_blobs_args
from strategy_menu.command_builder import build_syndata_args, get_out_range_args, build_send_args


# ==================== ЗАХАРДКОЖЕННЫЕ СИСТЕМНЫЕ БЛОБЫ ====================
# Все системные блобы добавляются в начало preset файла.
# Это избегает динамической генерации и упрощает код.
# Пути к файлам относительные (@bin/...) - они разрешаются winws2.exe.
# fake_default_quic, fake_default_tls, fake_default_http уже есть в коде и его указывать не надо будет ошибка Error: duplicate blob name
HARDCODED_BLOBS = (
    "--blob=tls_google:@bin/tls_clienthello_www_google_com.bin "
    "--blob=tls1:@bin/tls_clienthello_1.bin "
    "--blob=tls2:@bin/tls_clienthello_2.bin "
    "--blob=tls2n:@bin/tls_clienthello_2n.bin "
    "--blob=tls3:@bin/tls_clienthello_3.bin "
    "--blob=tls4:@bin/tls_clienthello_4.bin "
    "--blob=tls5:@bin/tls_clienthello_5.bin "
    "--blob=tls6:@bin/tls_clienthello_6.bin "
    "--blob=tls7:@bin/tls_clienthello_7.bin "
    "--blob=tls8:@bin/tls_clienthello_8.bin "
    "--blob=tls9:@bin/tls_clienthello_9.bin "
    "--blob=tls10:@bin/tls_clienthello_10.bin "
    "--blob=tls11:@bin/tls_clienthello_11.bin "
    "--blob=tls12:@bin/tls_clienthello_12.bin "
    "--blob=tls13:@bin/tls_clienthello_13.bin "
    "--blob=tls14:@bin/tls_clienthello_14.bin "
    "--blob=tls17:@bin/tls_clienthello_17.bin "
    "--blob=tls18:@bin/tls_clienthello_18.bin "
    "--blob=tls_sber:@bin/tls_clienthello_sberbank_ru.bin "
    "--blob=tls_vk:@bin/tls_clienthello_vk_com.bin "
    "--blob=tls_vk_kyber:@bin/tls_clienthello_vk_com_kyber.bin "
    "--blob=tls_deepseek:@bin/tls_clienthello_chat_deepseek_com.bin "
    "--blob=tls_max:@bin/tls_clienthello_max_ru.bin "
    "--blob=tls_iana:@bin/tls_clienthello_iana_org.bin "
    "--blob=tls_4pda:@bin/tls_clienthello_4pda_to.bin "
    "--blob=tls_gosuslugi:@bin/tls_clienthello_gosuslugi_ru.bin "
    "--blob=syndata3:@bin/tls_clienthello_3.bin "
    "--blob=syn_packet:@bin/syn_packet.bin "
    "--blob=dtls_w3:@bin/dtls_clienthello_w3_org.bin "
    "--blob=quic_google:@bin/quic_initial_www_google_com.bin "
    "--blob=quic_vk:@bin/quic_initial_vk_com.bin "
    "--blob=quic1:@bin/quic_1.bin "
    "--blob=quic2:@bin/quic_2.bin "
    "--blob=quic3:@bin/quic_3.bin "
    "--blob=quic4:@bin/quic_4.bin "
    "--blob=quic5:@bin/quic_5.bin "
    "--blob=quic6:@bin/quic_6.bin "
    "--blob=quic7:@bin/quic_7.bin "
    "--blob=quic_test:@bin/quic_test_00.bin "
    "--blob=fake_tls:@bin/fake_tls_1.bin "
    "--blob=fake_tls_1:@bin/fake_tls_1.bin "
    "--blob=fake_tls_2:@bin/fake_tls_2.bin "
    "--blob=fake_tls_3:@bin/fake_tls_3.bin "
    "--blob=fake_tls_4:@bin/fake_tls_4.bin "
    "--blob=fake_tls_5:@bin/fake_tls_5.bin "
    "--blob=fake_tls_6:@bin/fake_tls_6.bin "
    "--blob=fake_tls_7:@bin/fake_tls_7.bin "
    "--blob=fake_tls_8:@bin/fake_tls_8.bin "
    "--blob=fake_quic:@bin/fake_quic.bin "
    "--blob=fake_quic_1:@bin/fake_quic_1.bin "
    "--blob=fake_quic_2:@bin/fake_quic_2.bin "
    "--blob=fake_quic_3:@bin/fake_quic_3.bin "
    "--blob=fake_default_udp:0x00000000000000000000000000000000 "
    "--blob=http_req:@bin/http_iana_org.bin "
    "--blob=hex_0e0e0f0e:0x0E0E0F0E "
    "--blob=hex_0f0e0e0f:0x0F0E0E0F "
    "--blob=hex_0f0f0f0f:0x0F0F0F0F "
    "--blob=hex_00:0x00"
)


# ==================== COMMON UTILITIES ====================

def calculate_required_filters(target_strategies: dict) -> dict:
    """
    Automatically calculates required port filters based on selected categories.

    Uses filters_config.py to determine which filters are needed.

    Args:
        target_strategies: dict {target_key: strategy_id}

    Returns:
        dict with filter flags
    """
    from launcher_common.port_filters import get_filter_for_target, FILTERS

    # Initialize all filters as False
    filters = {key: False for key in FILTERS.keys()}

    none_strategies = registry.get_none_strategies()

    for target_key, strategy_id in target_strategies.items():
        # Skip inactive categories
        if not strategy_id:
            continue
        none_id = none_strategies.get(target_key)
        if strategy_id == none_id or strategy_id == "none":
            continue

        # Get category info
        target_info = registry.get_target_info(target_key)
        if not target_info:
            continue

        # Get required filters via config
        required_filters = get_filter_for_target(target_info)
        for filter_key in required_filters:
            filters[filter_key] = True

    log(f"[V2] Auto-detected filters: TCP=[80={filters.get('tcp_80')}, 443={filters.get('tcp_443')}, "
        f"6568={filters.get('tcp_6568')}, warp={filters.get('tcp_warp')}, all={filters.get('tcp_all_ports')}], "
        f"UDP=[443={filters.get('udp_443')}, all={filters.get('udp_all_ports')}], "
        f"raw=[discord={filters.get('raw_discord')}, stun={filters.get('raw_stun')}, wg={filters.get('raw_wireguard')}]", "DEBUG")

    return filters


def _apply_settings(args: str) -> str:
    """
    Applies all user settings to the command line.

    Handles:
    - Adding --wssize 1:6
    """
    from strategy_menu import get_strategy_launch_method, get_wssize_enabled

    result = args
    launch_method = (get_strategy_launch_method() or "").strip().lower()
    allow_launch_injection = launch_method not in {"direct_zapret1", "direct_zapret2"}

    # ==================== WSSIZE ADDITION ====================
    if allow_launch_injection and get_wssize_enabled():
        # Add --wssize 1:6 for TCP 443
        if "--wssize" not in result:
            # Insert after --wf-* arguments
            if "--wf-" in result:
                # Find end of wf arguments
                wf_end = 0
                for match in re.finditer(r'--wf-[^\s]+=[^\s]+', result):
                    wf_end = max(wf_end, match.end())

                if wf_end > 0:
                    result = result[:wf_end] + " --wssize 1:6" + result[wf_end:]
                else:
                    result = "--wssize 1:6 " + result
            else:
                result = "--wssize 1:6 " + result

            log("[V2] Added --wssize 1:6 parameter", "DEBUG")

    # ==================== FINAL CLEANUP ====================
    result = _clean_spaces(result)

    # Remove empty --new (if left after other modifications)
    result = re.sub(r'--new\s+--new', '--new', result)
    result = re.sub(r'\s+--new\s*$', '', result)  # Trailing --new
    result = re.sub(r'^--new\s+', '', result)  # Leading --new

    return result.strip()


def _clean_spaces(text: str) -> str:
    """Cleans multiple spaces"""
    return ' '.join(text.split())


# ==================== V2-SPECIFIC FUNCTIONS ====================

def _build_base_args_v2(
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
    is_orchestra: bool = False,
) -> str:
    """
    Builds base WinDivert arguments for Zapret 2.

    Features:
    - --lua-init for Lua library loading (required for Zapret 2)
    - --wf-tcp-out= / --wf-udp-out= (V2 syntax)
    - --wf-tcp-in= for orchestra mode

    Args:
        lua_init: Lua initialization string (--lua-init=@path --lua-init=@path ...)
        windivert_filter_folder: Path to WinDivert filter files
        tcp_80: Enable TCP port 80 filter
        tcp_443: Enable TCP port 443 filter
        tcp_6568: Enable TCP port 6568 (AnyDesk) filter
        tcp_warp: Enable TCP WARP ports filter (443, 853)
        tcp_all_ports: Enable TCP all ports (444-65535) filter
        udp_443: Enable UDP port 443 (QUIC) filter
        udp_all_ports: Enable UDP all ports (444-65535) filter
        raw_discord_media: Enable Discord media raw-part filter
        raw_stun: Enable STUN raw-part filter
        raw_wireguard: Enable WireGuard raw-part filter
        is_orchestra: If True, adds --wf-tcp-in= for orchestra mode

    Returns:
        Base arguments string for Zapret 2
    """
    parts = []

    # Lua initialization is REQUIRED for Zapret 2
    parts.append(lua_init)

    # === TCP ports - V2 syntax ===
    tcp_port_parts = []
    if tcp_80:
        tcp_port_parts.append("80")
    if tcp_443:
        tcp_port_parts.append("443,1080,2053,2083,2087,2096,8443")
    if tcp_warp:
        tcp_port_parts.append("853")
    if tcp_6568:
        tcp_port_parts.append("6568")
    if tcp_all_ports:
        tcp_port_parts.append("444-65535")

    if tcp_port_parts:
        tcp_ports_str = ','.join(tcp_port_parts)
        # Zapret 2 uses --wf-tcp-out= (NOT --wf-tcp= like V1)
        parts.append(f"--wf-tcp-out={tcp_ports_str}")
        # For orchestra mode, also intercept incoming TCP
        if is_orchestra:
            parts.append(f"--wf-tcp-in={tcp_ports_str}")

    # === UDP ports - V2 syntax ===
    udp_port_parts = []
    if udp_443:
        udp_port_parts.append("443")
    if udp_all_ports:
        udp_port_parts.append("444-65535")

    if udp_port_parts:
        udp_ports_str = ','.join(udp_port_parts)
        # Zapret 2 uses --wf-udp-out= (NOT --wf-udp= like V1)
        parts.append(f"--wf-udp-out={udp_ports_str}")

    # === Raw-part filters (CPU-efficient) ===
    # These filters intercept only specific packets by signature

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
    log(f"[V2] Built base args (orchestra={is_orchestra}): TCP=[80={tcp_80}, 443={tcp_443}, all={tcp_all_ports}], "
        f"UDP=[443={udp_443}, all={udp_all_ports}], "
        f"raw=[discord={raw_discord_media}, stun={raw_stun}, wg={raw_wireguard}]", "DEBUG")

    return result


def combine_strategies_v2(is_orchestra: bool = False, **kwargs) -> dict:
    """
    Combines strategies for Zapret 2 (winws2.exe).

    Full version with:
    - Lua library support (--lua-init)
    - V2 WinDivert syntax (--wf-tcp-out=, --wf-udp-out=)
    - Orchestra mode support (--wf-tcp-in=)

    Args:
        is_orchestra: If True, enables orchestra mode with --wf-tcp-in=
        **kwargs: Category selections {target_key: strategy_id}

    Returns:
        Combined strategy dict with 'args', 'name', 'description', etc.

    Applies all settings from UI:
    - Base arguments (windivert)
    - Debug log (if enabled)
    - Wssize addition (if enabled)
    """

    # Determine category selections source
    if kwargs:
        log("[V2] Using provided category strategies", "DEBUG")
        target_strategies = kwargs
    else:
        log("[V2] Using default selections", "DEBUG")
        target_strategies = registry.get_default_selections()

    # ==================== BASE ARGUMENTS ====================
    from strategy_menu import get_debug_log_enabled, get_strategy_launch_method
    from config import LUA_FOLDER, WINDIVERT_FILTER, LOGS_FOLDER

    # Lua libraries must be loaded first (REQUIRED for Zapret 2)
    # Load order is important:
    # 1. zapret-lib.lua - base functions
    # 2. zapret-antidpi.lua - desync functions
    # 3. zapret-auto.lua - auto-detection helpers
    # 4. custom_funcs.lua - user custom functions
    lua_lib_path = os.path.join(LUA_FOLDER, "zapret-lib.lua")
    lua_antidpi_path = os.path.join(LUA_FOLDER, "zapret-antidpi.lua")
    lua_auto_path = os.path.join(LUA_FOLDER, "zapret-auto.lua")
    custom_funcs_path = os.path.join(LUA_FOLDER, "custom_funcs.lua")
    zapret_multishake_path = os.path.join(LUA_FOLDER, "zapret-multishake.lua")
    # Paths WITHOUT quotes - subprocess.Popen with list of args handles paths correctly
    LUA_INIT = f'--lua-init=@{lua_lib_path} --lua-init=@{lua_antidpi_path} --lua-init=@{lua_auto_path} --lua-init=@{custom_funcs_path} --lua-init=@{zapret_multishake_path}'

    # Auto-detect required filters based on selected targets from legacy registry flow
    filters = calculate_required_filters(target_strategies)

    # Build base arguments from auto-detected filters (V2 syntax)
    base_args = _build_base_args_v2(
        LUA_INIT,
        WINDIVERT_FILTER,
        filters['tcp_80'],
        filters['tcp_443'],
        filters.get('tcp_6568', False),
        filters.get('tcp_warp', False),
        filters['tcp_all_ports'],
        filters['udp_443'],
        filters['udp_all_ports'],
        filters.get('raw_discord', False),
        filters.get('raw_stun', False),
        filters.get('raw_wireguard', False),
        is_orchestra,
    )

    # ==================== COLLECT ACTIVE TARGETS ====================
    target_keys_ordered = registry.get_all_target_keys_by_command_order()
    none_strategies = registry.get_none_strategies()

    # Collect active targets with their arguments
    active_targets = []  # [(target_key, args, target_info), ...]
    descriptions = []

    for target_key in target_keys_ordered:
        strategy_id = target_strategies.get(target_key)

        if not strategy_id:
            continue

        # Skip "none" strategies
        none_id = none_strategies.get(target_key)
        if strategy_id == none_id:
            continue

        # Get full arguments via registry (base_filter + technique)
        args = registry.get_strategy_args_safe(target_key, strategy_id)
        if args:
            target_info = registry.get_target_info(target_key)

            # ==================== SYNDATA/SEND INJECTION ====================
            # Apply syndata and send settings from UI (if enabled for this category)
            #
            # ВАЖНО: Порядок аргументов:
            # {base_filter} {out_range} {send} {syndata} {strategy}
            # Пример:
            #   --filter-tcp=80,443 --hostlist=youtube.txt --out-range=-n8 --lua-desync=send:repeats=2 --lua-desync=syndata:blob=tls7 --lua-desync=multisplit:pos=1,midsld
            #   ├─ base_filter ─────────────────────────┤├─ out_range ─┤├─ send ────────────────────┤├─ syndata ─────────────────┤├─ strategy ──────────────────────────┤
            #
            proto_raw = str(getattr(target_info, "protocol", "") or "").upper()
            is_udp_like = ("UDP" in proto_raw) or ("QUIC" in proto_raw) or ("L7" in proto_raw)
            protocol_key = "udp" if is_udp_like else "tcp"

            out_range_args = get_out_range_args(target_key, protocol=protocol_key)
            send_args = build_send_args(target_key, protocol=protocol_key)
            syndata_args = build_syndata_args(target_key, protocol=protocol_key)

            # Если есть что вставить - разделяем args на base_filter и strategy части
            if syndata_args or out_range_args or send_args:
                # Разделяем по первому --lua-desync= (это начало strategy части)
                if " --lua-desync=" in args:
                    parts = args.split(" --lua-desync=", 1)
                    base_filter_part = parts[0]  # Всё до первого --lua-desync=
                    strategy_part = "--lua-desync=" + parts[1]  # Первый --lua-desync= и всё после
                else:
                    # Нет --lua-desync= - вся строка это base_filter
                    base_filter_part = args
                    strategy_part = ""

                # Собираем в правильном порядке: base_filter + out_range + send + syndata + strategy
                result_parts = [base_filter_part]

                if out_range_args:
                    result_parts.append(out_range_args)
                    log(f"[V2] Applied out_range for '{target_key}': {out_range_args}", "DEBUG")

                if send_args:
                    result_parts.append(send_args)
                    log(f"[V2] Applied send for '{target_key}': {send_args}", "DEBUG")

                if syndata_args:
                    result_parts.append(syndata_args)
                    log(f"[V2] Applied syndata for '{target_key}': {syndata_args}", "DEBUG")

                if strategy_part:
                    result_parts.append(strategy_part)

                args = " ".join(result_parts)

            active_targets.append((target_key, args, target_info))

            # Add to description
            strategy_name = registry.get_strategy_name_safe(target_key, strategy_id)
            if target_info:
                descriptions.append(f"{target_info.full_name}: {strategy_name}")

    # ==================== BUILD COMMAND LINE ====================
    # Collect target arguments with --new separators
    target_args_parts = []

    for i, (target_key, args, target_info) in enumerate(active_targets):
        target_args_parts.append(args)

        # Add --new only if:
        # 1. Target requires separator (needs_new_separator=True)
        # 2. And this is NOT the last active target
        is_last = (i == len(active_targets) - 1)
        if target_info and target_info.needs_new_separator and not is_last:
            target_args_parts.append("--new")

    # ==================== БЛОБЫ И АРГУМЕНТЫ TARGET'ОВ ====================
    # Системные блобы захардкожены в HARDCODED_BLOBS
    # Пользовательские блобы загружаются динамически
    # Из аргументов target'ов удаляются дублирующиеся блобы
    target_args_str = " ".join(target_args_parts)

    # Извлекаем только пользовательские блобы (если есть)
    user_blobs = get_user_blobs_args()

    # Удаляем дублирующиеся --blob=... из аргументов target'ов,
    # т.к. все системные блобы уже есть в HARDCODED_BLOBS
    _, cleaned_target_args = extract_and_dedupe_blobs([target_args_str])

    # Build final command line
    args_parts = []

    # ==================== DEBUG LOG ====================
    # Added at the beginning of command line if enabled
    launch_method = (get_strategy_launch_method() or "").strip().lower()
    allow_launch_injection = launch_method not in {"direct_zapret1", "direct_zapret2"}

    if allow_launch_injection and get_debug_log_enabled():
        from datetime import datetime
        from log.log import cleanup_old_logs
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"zapret_winws2_debug_{timestamp}.log"
        log_path = os.path.join(LOGS_FOLDER, log_filename)
        # Create logs folder if it doesn't exist
        os.makedirs(LOGS_FOLDER, exist_ok=True)
        # Clean up old logs (keep max 50)
        cleanup_old_logs(LOGS_FOLDER)
        args_parts.append(f"--debug=@{log_path}")
        log(f"[V2] Debug log enabled: {log_path}", "INFO")

    # Порядок: base_args → захардкоженные блобы → пользовательские блобы → аргументы target'ов
    if base_args:
        args_parts.append(base_args)
    args_parts.append(HARDCODED_BLOBS)
    if user_blobs:
        args_parts.append(user_blobs)
    if cleaned_target_args:
        args_parts.append(cleaned_target_args)

    combined_args = " ".join(args_parts)

    # ==================== APPLY SETTINGS ====================
    combined_args = _apply_settings(combined_args)

    # ==================== FINALIZE ====================
    combined_description = " | ".join(descriptions) if descriptions else "Custom combination"

    log(f"[V2] Created combined strategy: {len(combined_args)} chars, {len(active_targets)} targets, "
        f"orchestra={is_orchestra}", "DEBUG")

    return {
        "name": "Combined Strategy (V2)",
        "description": combined_description,
        "version": "2.0",
        "provider": "universal",
        "author": "Combined",
        "updated": "2024",
        "all_sites": True,
        "args": combined_args,
        "_is_builtin": True,
        "_is_v2": True,
        "_is_orchestra": is_orchestra,
        "_active_targets": len(active_targets),
        **{f"_{key}_id": strategy_id for key, strategy_id in target_strategies.items()}
    }


# ==================== HELPER FUNCTIONS ====================

def get_strategy_display_name(target_key: str, strategy_id: str) -> str:
    """Gets display name for a strategy"""
    if strategy_id == "none":
        return "Disabled"

    return registry.get_strategy_name_safe(target_key, strategy_id)


def get_active_targets_count(target_strategies: dict) -> int:
    """Counts the number of active targets in legacy registry flow."""
    none_strategies = registry.get_none_strategies()
    count = 0

    for target_key, strategy_id in target_strategies.items():
        if strategy_id and strategy_id != none_strategies.get(target_key):
            count += 1

    return count


def validate_target_strategies(target_strategies: dict) -> list:
    """
    Validates selected strategies.
    Returns list of errors (empty if all ok).
    """
    errors = []

    for target_key, strategy_id in target_strategies.items():
        if not strategy_id:
            continue

        if strategy_id == "none":
            continue

        # Check target exists
        target_info = registry.get_target_info(target_key)
        if not target_info:
            errors.append(f"Unknown target: {target_key}")
            continue

        # Check strategy exists
        args = registry.get_strategy_args_safe(target_key, strategy_id)
        if args is None:
            errors.append(f"Strategy '{strategy_id}' not found for target '{target_key}'")

    return errors


# ==================== EXPORTS ====================

__all__ = [
    # Main function
    'combine_strategies_v2',

    # Filter calculation
    'calculate_required_filters',

    # Helper functions
    'get_strategy_display_name',
    'get_active_targets_count',
    'validate_target_strategies',

    # Internal (for testing)
    '_build_base_args_v2',
    '_apply_settings',
    '_clean_spaces',
]
