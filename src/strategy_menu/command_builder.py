# strategy_menu/command_builder.py
"""
Command Builder Module
Централизованная сборка командной строки для winws/winws2.

Использование:
    from strategy_menu.command_builder import build_full_command, build_syndata_args

    result = build_full_command({"youtube": "strategy_1", "discord": "strategy_2"})
    args = result["args"]
"""

import re
from typing import Optional

from launcher_common.blobs import get_blobs

# ===================== HELPERS =====================

def clean_spaces(text: str) -> str:
    """Удаляет лишние пробелы"""
    return re.sub(r'\s+', ' ', text).strip()


def strip_payload_from_args(args: str) -> str:
    """Убирает --payload= из стратегии (для IPset категорий)"""
    return re.sub(r'--payload=[^\s]+\s*', '', args)


def replace_out_range(args: str, value: int, mode: str = "n") -> str:
    """
    Заменяет значение --out-range в аргументах.

    Args:
        args: строка аргументов
        value: значение (1-999)
        mode: режим "n" (packets count) или "d" (delay)
    """
    if mode not in ("n", "d"):
        mode = "n"
    return re.sub(r'--out-range=[^\s]+', f'--out-range=-{mode}{value}', args)


def extract_payload(args: str) -> tuple[str, str]:
    """
    Извлекает --payload=... из строки аргументов.

    Args:
        args: строка аргументов стратегии

    Returns:
        tuple[str, str]: (payload_part, remaining_args)

    Example:
        extract_payload("--lua-desync=fake --payload=tls_client_hello --out-range=5")
        returns ("--payload=tls_client_hello", "--lua-desync=fake --out-range=5")
    """
    if not args:
        return ("", "")

    # Ищем --payload=...
    match = re.search(r'--payload=[^\s]+', args)
    if match:
        payload_part = match.group(0)
        remaining = re.sub(r'--payload=[^\s]+\s*', '', args)
        return (payload_part, clean_spaces(remaining))

    return ("", args)


# ===================== SYNDATA =====================


def _get_active_zapret2_preset():
    try:
        from preset_zapret2.preset_store import get_preset_store

        store = get_preset_store()
        active_name = (store.get_active_preset_name() or "").strip()
        if not active_name:
            return None
        return store.get_preset(active_name)
    except Exception:
        return None


def _get_tcp_syndata(category_key: str):
    from preset_zapret2.preset_model import SyndataSettings

    preset = _get_active_zapret2_preset()
    if not preset:
        return SyndataSettings.get_defaults()
    category = (preset.categories or {}).get(category_key)
    if not category:
        return SyndataSettings.get_defaults()
    return category.syndata_tcp


def build_syndata_args(category_key: str, protocol: str = "tcp") -> str:
    """
    Собирает --lua-desync=syndata:... из настроек активного пресета.

    Returns:
        str: например "--lua-desync=syndata:blob=tls7:ip_autottl=-2,3-20" или ""
    """
    try:
        proto = (protocol or "").strip().lower()
        if proto in ("udp", "quic", "l7", "raw"):
            return ""

        syndata = _get_tcp_syndata(category_key)

        if not syndata.enabled:
            return ""

        parts = ["syndata"]

        blob = syndata.blob
        if blob and blob != "none":
            parts.append(f"blob={blob}")

        tls_mod = syndata.tls_mod
        if tls_mod and tls_mod != "none":
            parts.append(f"tls_mod={tls_mod}")

        # AutoTTL: ip_autottl=delta,min-max
        parts.append(f"ip_autottl={syndata.autottl_delta},{syndata.autottl_min}-{syndata.autottl_max}")

        tcp_flags = syndata.tcp_flags_unset
        if tcp_flags and tcp_flags != "none":
            parts.append(f"tcp_flags_unset={tcp_flags}")

        # ВАЖНО: out_range НЕ добавляется в syndata!
        # Он передается как отдельный аргумент --out-range=-dVALUE
        # Используй get_out_range_args() для получения этого аргумента

        if len(parts) > 1:
            return f"--lua-desync={':'.join(parts)}"
        return "--lua-desync=syndata"

    except Exception as e:
        from log import log
        log(f"Error building syndata_args for {category_key}: {e}", "DEBUG")
        return ""


def get_out_range_args(category_key: str, protocol: str = "tcp") -> str:
    """
    Возвращает --out-range=-{mode}{value} (всегда, дефолт -n8).

    out_range - это ОТДЕЛЬНЫЙ аргумент командной строки,
    а НЕ часть syndata.

    Режимы:
        -n = количество пакетов с самого первого
        -d = отсчитывать ТОЛЬКО количество пакетов с данными (исключая SYN-ACK-SYN рукопожатие)"

    Правильно:   --out-range=-n8 --lua-desync=syndata:blob=tls7
    Неправильно: --lua-desync=syndata:blob=tls7:out_range=10

    ВАЖНО: --out-range добавляется ВСЕГДА для каждой категории.
    Дефолтные значения: mode="n", value=8

    Returns:
        str: например "--out-range=-n8" или "--out-range=-d10"
    """
    DEFAULT_OUT_RANGE = 8
    DEFAULT_MODE = "n"
    try:
        syndata = _get_tcp_syndata(category_key)

        out_range = syndata.out_range
        if out_range is None or out_range == 0:
            out_range = DEFAULT_OUT_RANGE

        # Получаем режим (n или d)
        out_range_mode = syndata.out_range_mode
        if out_range_mode not in ("n", "d"):
            out_range_mode = DEFAULT_MODE

        return f"--out-range=-{out_range_mode}{out_range}"

    except Exception as e:
        from log import log
        log(f"Error getting out_range_args for {category_key}: {e}", "DEBUG")
        # Всегда возвращаем дефолтное значение
        return f"--out-range=-{DEFAULT_MODE}{DEFAULT_OUT_RANGE}"


def build_send_args(category_key: str, protocol: str = "tcp") -> str:
    """
    Собирает --lua-desync=send:... из настроек активного пресета.

    Параметры send:
        - send_enabled (bool) - включена ли функция send
        - send_repeats (int, 0-10) - количество повторов
        - send_ip_ttl (int, 0-255) - TTL для IPv4
        - send_ip6_ttl (int, 0-255) - TTL для IPv6
        - send_ip_id (str: "none", "seq", "rnd", "zero") - режим IP ID
        - send_badsum (bool) - испортить checksum

    Returns:
        str: например "--lua-desync=send:repeats=2:ip_ttl=5:badsum" или ""
    """
    try:
        proto = (protocol or "").strip().lower()
        if proto in ("udp", "quic", "l7", "raw"):
            return ""

        syndata = _get_tcp_syndata(category_key)

        # Проверяем, включен ли send
        if not syndata.send_enabled:
            return ""

        parts = ["send"]

        # repeats (0-10)
        repeats = syndata.send_repeats
        if repeats and repeats > 0:
            parts.append(f"repeats={repeats}")

        # send_ip_ttl (0-255) - TTL для send пакетов
        send_ip_ttl = syndata.send_ip_ttl
        if send_ip_ttl and send_ip_ttl > 0:
            parts.append(f"ip_ttl={send_ip_ttl}")

        # ip6_ttl (0-255)
        ip6_ttl = syndata.send_ip6_ttl
        if ip6_ttl and ip6_ttl > 0:
            parts.append(f"ip6_ttl={ip6_ttl}")

        # ip_id (none, seq, rnd, zero)
        ip_id = syndata.send_ip_id
        if ip_id and ip_id != "none":
            parts.append(f"ip_id={ip_id}")

        # badsum (bool)
        badsum = syndata.send_badsum
        if badsum:
            parts.append("badsum")

        # Всегда возвращаем хотя бы --lua-desync=send если включено
        if len(parts) > 1:
            return f"--lua-desync={':'.join(parts)}"
        return "--lua-desync=send"

    except Exception as e:
        from log import log
        log(f"Error building send_args for {category_key}: {e}", "DEBUG")
        return ""


# ===================== CATEGORY ARGS =====================

def build_category_args(
    base_filter: str,
    strategy_args: str,
    category_key: str,
    strip_payload: bool = False
) -> str:
    """
    Собирает полную строку для категории:
    base_filter + payload + syndata + remaining_strategy_args

    Args:
        base_filter: фильтр категории (--filter-tcp=443 --hostlist=youtube.txt)
        strategy_args: техника стратегии (--lua-desync=multisplit...)
        category_key: ключ категории для syndata
        strip_payload: убрать --payload= (для IPset)

    Returns:
        str: полная командная строка для категории
    """
    syndata_args = build_syndata_args(category_key)

    # Извлекаем payload из strategy_args
    payload_part, remaining_strategy_args = extract_payload(strategy_args)

    if strip_payload:
        payload_part = ""

    parts = []
    if base_filter:
        parts.append(base_filter)
    if payload_part:
        parts.append(payload_part)
    if syndata_args:
        parts.append(syndata_args)
    if remaining_strategy_args:
        parts.append(remaining_strategy_args)

    return " ".join(parts)


# ===================== PREVIEW =====================

def preview_syndata(category_key: str) -> str:
    """Возвращает превью syndata для отображения в UI"""
    args = build_syndata_args(category_key)
    if not args:
        return "Syndata: выключено"
    return f"Syndata: {args}"


# ===================== FILTER MODE =====================

def get_filter_mode(category_key: str) -> str:
    """
    Получает режим фильтрации для категории из активного пресета.

    Returns:
        "hostlist" или "ipset"
    """
    try:
        preset = _get_active_zapret2_preset()
        if not preset:
            return "hostlist"
        category = (preset.categories or {}).get(category_key)
        if not category:
            return "hostlist"
        filter_mode = category.filter_mode
        if filter_mode in ("hostlist", "ipset"):
            return filter_mode
        return "hostlist"
    except Exception as e:
        from log import log
        log(f"Error getting filter_mode for {category_key}: {e}", "DEBUG")
        return "hostlist"
