from __future__ import annotations

from dataclasses import dataclass

import telegram_proxy.config.settings as telegram_proxy_settings


@dataclass(frozen=True, slots=True)
class TelegramProxyAdvancedSettingsUiPlan:
    advanced_card_visible: bool
    should_build_advanced_widgets: bool
    auto_sections: frozenset[str]
    mtproxy_rows_visible: bool
    upstream_controls_visible: bool
    cloudflare_controls_visible: bool
    dc_ip_row_visible: bool
    performance_controls_visible: bool
    cloudflare_domains_visible: bool
    cloudflare_worker_domains_visible: bool
    cloudflare_worker_domains_enabled: bool


def build_advanced_settings_auto_sections(
    state: telegram_proxy_settings.TelegramProxySettingsState,
) -> frozenset[str]:
    sections: set[str] = set()
    if state.mode == "mtproxy":
        sections.add("mtproxy")
        sections.add("upstream")
    if (
        state.upstream_enabled
        or state.upstream_host
        or state.upstream_user
        or state.upstream_password
        or state.upstream_preset_id
        or state.upstream_udp_enabled
    ):
        sections.add("upstream")
    if (
        state.cloudflare_enabled
        or state.cloudflare_domains
        or state.cloudflare_worker_enabled
        or state.cloudflare_worker_domains
    ):
        sections.add("cloudflare")
    if state.dc_ip:
        sections.add("dc_ip")
    if state.pool_size != 4 or state.buffer_kb != 256:
        sections.add("performance")
    return frozenset(sections)


def is_advanced_section_visible(auto_sections: object, section: str) -> bool:
    sections = frozenset(str(item or "") for item in (auto_sections or ()))
    return not sections or str(section or "") in sections


def build_advanced_settings_ui_plan(
    *,
    advanced_checked: bool,
    proxy_mode: object,
    auto_sections: object,
    cloudflare_enabled: bool,
    cloudflare_worker_enabled: bool,
) -> TelegramProxyAdvancedSettingsUiPlan:
    sections = frozenset(str(item or "") for item in (auto_sections or ()))
    is_mtproxy = telegram_proxy_settings.normalize_proxy_mode(proxy_mode) == "mtproxy"
    show_cloudflare = is_advanced_section_visible(sections, "cloudflare")

    return TelegramProxyAdvancedSettingsUiPlan(
        advanced_card_visible=bool(advanced_checked),
        should_build_advanced_widgets=bool(advanced_checked or is_mtproxy),
        auto_sections=sections,
        mtproxy_rows_visible=is_mtproxy,
        upstream_controls_visible=is_advanced_section_visible(sections, "upstream"),
        cloudflare_controls_visible=show_cloudflare,
        dc_ip_row_visible=is_advanced_section_visible(sections, "dc_ip"),
        performance_controls_visible=is_advanced_section_visible(sections, "performance"),
        cloudflare_domains_visible=bool(show_cloudflare and cloudflare_enabled),
        cloudflare_worker_domains_visible=bool(show_cloudflare and cloudflare_worker_enabled),
        cloudflare_worker_domains_enabled=bool(show_cloudflare and cloudflare_worker_enabled),
    )
