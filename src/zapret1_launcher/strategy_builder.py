# zapret1_launcher/strategy_builder.py
"""
Strategy list builder for Zapret 1 (winws.exe).

Simplified version WITHOUT:
- --lua-init (no Lua support in V1)
- --wf-tcp-out= / --wf-udp-out= (uses old syntax --wf-tcp= / --wf-udp=)
- --wf-tcp-in= (no orchestra mode in V1)
- --wf-raw-part= (no raw filters in V1)

This module is designed specifically for Zapret 1 (winws.exe) and does NOT
support Zapret 2 features. For V2 compatibility, use strategy_lists_v2.py.

Important:
- direct_zapret1 now launches from the selected source preset via direct_preset_core;
- this builder remains a legacy combiner for registry-driven flows.
"""

import re
import os
from log import log
from strategy_menu.strategies_registry import registry
from launcher_common.builder_common import (
    calculate_required_filters,
    _apply_settings,
    _clean_spaces,
    get_strategy_display_name,
    get_active_targets_count,
    validate_target_strategies
)
from launcher_common.blobs import build_args_with_deduped_blobs


# ==================== V1-SPECIFIC FUNCTIONS ====================

def _build_base_args_v1(
    tcp_80: bool,
    tcp_443: bool,
    tcp_6568: bool,
    tcp_warp: bool,
    tcp_all_ports: bool,
    udp_443: bool,
    udp_all_ports: bool,
) -> str:
    """
    Builds base WinDivert arguments for Zapret 1.

    Features:
    - NO --lua-init (Lua not supported in V1)
    - --wf-tcp= (V1 syntax, NOT --wf-tcp-out=)
    - --wf-udp= (V1 syntax, NOT --wf-udp-out=)
    - NO --wf-tcp-in= (orchestra mode not supported in V1)
    - NO --wf-raw-part= (raw filters not supported in V1)

    Args:
        tcp_80: Enable TCP port 80 filter
        tcp_443: Enable TCP port 443 filter
        tcp_6568: Enable TCP port 6568 (AnyDesk) filter
        tcp_warp: Enable TCP WARP ports filter (443, 853)
        tcp_all_ports: Enable TCP all ports (444-65535) filter
        udp_443: Enable UDP port 443 (QUIC) filter
        udp_all_ports: Enable UDP all ports (444-65535) filter

    Returns:
        Base arguments string for Zapret 1
    """
    parts = []

    # === TCP ports - V1 syntax ===
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
        # Zapret 1 uses --wf-tcp= (NOT --wf-tcp-out= like V2)
        parts.append(f"--wf-tcp={tcp_ports_str}")

    # === UDP ports - V1 syntax ===
    udp_port_parts = []
    if udp_443:
        udp_port_parts.append("443")
    if udp_all_ports:
        udp_port_parts.append("444-65535")

    if udp_port_parts:
        udp_ports_str = ','.join(udp_port_parts)
        # Zapret 1 uses --wf-udp= (NOT --wf-udp-out= like V2)
        parts.append(f"--wf-udp={udp_ports_str}")

    # NOTE: V1 does NOT support --wf-raw-part= filters
    # Discord voice, STUN, WireGuard raw filters are V2-only

    result = " ".join(parts)
    log(f"[V1] Built base args: TCP=[80={tcp_80}, 443={tcp_443}, 6568={tcp_6568}, warp={tcp_warp}, all={tcp_all_ports}], "
        f"UDP=[443={udp_443}, all={udp_all_ports}]", "DEBUG")

    return result


def _remove_lua_init(args: str) -> str:
    """
    Removes all --lua-init arguments from strategy arguments.

    V1 (winws.exe) does NOT support Lua scripting.
    This function strips any --lua-init=... from the command line.

    Args:
        args: Strategy arguments string

    Returns:
        Arguments with --lua-init removed
    """
    result = re.sub(r'--lua-init=[^\s]+\s*', '', args)
    return _clean_spaces(result)


def _convert_v2_syntax_to_v1(args: str) -> str:
    """
    Converts V2 WinDivert syntax to V1.

    V2 uses:
    - --wf-tcp-out=
    - --wf-udp-out=
    - --wf-tcp-in=

    V1 uses:
    - --wf-tcp=
    - --wf-udp=
    - (no --wf-tcp-in=)

    Args:
        args: Strategy arguments string with potential V2 syntax

    Returns:
        Arguments converted to V1 syntax
    """
    result = args

    # Convert --wf-tcp-out= to --wf-tcp=
    result = re.sub(r'--wf-tcp-out=', '--wf-tcp=', result)

    # Convert --wf-udp-out= to --wf-udp=
    result = re.sub(r'--wf-udp-out=', '--wf-udp=', result)

    # Remove --wf-tcp-in= entirely (orchestra mode not supported)
    result = re.sub(r'--wf-tcp-in=[^\s]+\s*', '', result)

    # Remove --wf-udp-in= entirely (not supported)
    result = re.sub(r'--wf-udp-in=[^\s]+\s*', '', result)

    # Remove --wf-raw-part= entirely (not supported in V1)
    result = re.sub(r'--wf-raw-part=[^\s]+\s*', '', result)

    return _clean_spaces(result)


def _sanitize_args_for_v1(args: str) -> str:
    """
    Sanitizes strategy arguments for V1 compatibility.

    Removes all V2-only features:
    - --lua-init
    - --wf-tcp-out= (converts to --wf-tcp=)
    - --wf-udp-out= (converts to --wf-udp=)
    - --wf-tcp-in= (removed)
    - --wf-raw-part= (removed)

    Args:
        args: Strategy arguments string

    Returns:
        Sanitized arguments for V1
    """
    result = args

    # Remove Lua initialization
    result = _remove_lua_init(result)

    # Convert V2 syntax to V1
    result = _convert_v2_syntax_to_v1(result)

    return _clean_spaces(result)


def combine_strategies_v1(**kwargs) -> dict:
    """
    Combines strategies for Zapret 1 (winws.exe).

    Simplified version without:
    - Lua library support (no --lua-init)
    - Orchestra mode (no --wf-tcp-in=)
    - Raw filters (no --wf-raw-part=)

    Uses V1 WinDivert syntax:
    - --wf-tcp= instead of --wf-tcp-out=
    - --wf-udp= instead of --wf-udp-out=

    Args:
        **kwargs: Category selections {target_key: strategy_id}

    Returns:
        Combined strategy dict with 'args', 'name', 'description', etc.

    Applies all settings from UI:
    - Base arguments (windivert)
    - Debug log (if enabled)
    - Wssize addition (if enabled)
    """

    # Determine target selections source inside legacy registry flow
    if kwargs:
        log("[V1] Using provided target strategies", "DEBUG")
        target_strategies = kwargs
    else:
        log("[V1] Using default selections", "DEBUG")
        target_strategies = registry.get_default_selections()

    # ==================== BASE ARGUMENTS ====================
    from strategy_menu import get_debug_log_enabled, get_strategy_launch_method
    from config import LOGS_FOLDER

    # NO Lua initialization for V1 - winws.exe doesn't support Lua

    # Auto-detect required filters based on selected targets
    filters = calculate_required_filters(target_strategies)

    # Build base arguments from auto-detected filters (V1 syntax)
    # Note: V1 does NOT support raw filters (discord, stun, wireguard)
    base_args = _build_base_args_v1(
        filters['tcp_80'],
        filters['tcp_443'],
        filters.get('tcp_6568', False),
        filters.get('tcp_warp', False),
        filters['tcp_all_ports'],
        filters['udp_443'],
        filters['udp_all_ports'],
        # V1 ignores: raw_discord, raw_stun, raw_wireguard
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
            # Sanitize args for V1 compatibility
            # Removes --lua-init, converts V2 syntax
            args = _sanitize_args_for_v1(args)

            target_info = registry.get_target_info(target_key)
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

    # Deduplicate blobs: extract all --blob=... from target arguments,
    # remove duplicates and move to the beginning of command line
    target_args_str = " ".join(target_args_parts)
    deduped_args = build_args_with_deduped_blobs([target_args_str])

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
        log_filename = f"zapret_winws_debug_{timestamp}.log"
        log_path = os.path.join(LOGS_FOLDER, log_filename)
        # Create logs folder if it doesn't exist
        os.makedirs(LOGS_FOLDER, exist_ok=True)
        # Clean up old logs (keep max 50)
        cleanup_old_logs(LOGS_FOLDER)
        args_parts.append(f"--debug=@{log_path}")
        log(f"[V1] Debug log enabled: {log_path}", "INFO")

    if base_args:
        args_parts.append(base_args)
    if deduped_args:
        args_parts.append(deduped_args)

    combined_args = " ".join(args_parts)

    # ==================== APPLY SETTINGS ====================
    combined_args = _apply_settings(combined_args)

    # ==================== FINAL SANITIZATION FOR V1 ====================
    # Double-check that no V2-only arguments slipped through
    combined_args = _sanitize_args_for_v1(combined_args)

    # ==================== FINALIZE ====================
    combined_description = " | ".join(descriptions) if descriptions else "Custom combination"

    log(f"[V1] Created combined strategy: {len(combined_args)} chars, {len(active_targets)} targets", "DEBUG")

    return {
        "name": "Combined Strategy (V1)",
        "description": combined_description,
        "version": "1.0",
        "provider": "universal",
        "author": "Combined",
        "updated": "2024",
        "all_sites": True,
        "args": combined_args,
        "_is_builtin": True,
        "_is_v1": True,
        "_is_orchestra": False,  # V1 never supports orchestra
        "_active_targets": len(active_targets),
        **{f"_{key}_id": strategy_id for key, strategy_id in target_strategies.items()}
    }


# ==================== EXPORTS ====================

__all__ = [
    # Main function
    'combine_strategies_v1',

    # Filter calculation (from common)
    'calculate_required_filters',

    # Helper functions (from common)
    'get_strategy_display_name',
    'get_active_targets_count',
    'validate_target_strategies',

    # V1-specific internal (for testing)
    '_build_base_args_v1',
    '_remove_lua_init',
    '_convert_v2_syntax_to_v1',
    '_sanitize_args_for_v1',
]
