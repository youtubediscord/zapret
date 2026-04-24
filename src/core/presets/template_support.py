from __future__ import annotations

from .z2_template_runtime import (
    get_builtin_base_from_copy_name,
    get_category_default_syndata,
    get_default_category_settings,
    get_default_template_content,
    get_template_content,
    reset_user_overrides_to_builtin_v2,
)
from .v1_template_runtime import (
    get_builtin_base_from_copy_name_v1,
    get_builtin_preset_content_v1,
    get_default_template_content_v1,
    get_template_content_v1,
    reset_user_overrides_to_builtin_v1,
)


def _resolve_reset_template_v2_from_runtime(preset_name: str) -> str:
    content = get_template_content(preset_name)
    if not content:
        base = get_builtin_base_from_copy_name(preset_name)
        if base:
            content = get_template_content(base)
    if not content:
        content = get_default_template_content()
    return str(content or "")


def _resolve_reset_template_v1_from_runtime(preset_name: str) -> str:
    content = get_template_content_v1(preset_name)
    if not content:
        base = get_builtin_base_from_copy_name_v1(preset_name)
        if base:
            content = get_template_content_v1(base)
    if not content:
        content = get_default_template_content_v1()
    if not content:
        content = get_builtin_preset_content_v1("Default")
    return str(content or "")


def resolve_reset_template(launch_method: str, preset_name: str) -> str:
    method = str(launch_method or "").strip().lower()
    if method == "direct_zapret2":
        content = _resolve_reset_template_v2_from_runtime(preset_name)
        return content if content else ""

    content = _resolve_reset_template_v1_from_runtime(preset_name)
    return content if content else ""


def reset_all_templates(launch_method: str) -> tuple[int, int, list[str]]:
    method = str(launch_method or "").strip().lower()
    if method == "direct_zapret2":
        return reset_user_overrides_to_builtin_v2()

    return reset_user_overrides_to_builtin_v1()


def get_default_target_settings_v2(category_key: str | None = None) -> dict:
    if category_key is None:
        return {
            "enabled": True,
            "blob": "tls_google",
            "tls_mod": "none",
            "autottl_delta": -2,
            "autottl_min": 3,
            "autottl_max": 20,
            "tcp_flags_unset": "none",
            "out_range": 8,
            "out_range_mode": "d",
            "send_enabled": True,
            "send_repeats": 2,
            "send_ip_ttl": 0,
            "send_ip6_ttl": 0,
            "send_ip_id": "none",
            "send_badsum": False,
        }

    all_defaults = get_default_category_settings()
    if category_key not in all_defaults:
        return get_default_target_settings_v2(None)
    return get_category_default_syndata(category_key, protocol="tcp")
