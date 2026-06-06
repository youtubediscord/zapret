from __future__ import annotations

from app.page_names import PageName
from ui.page_deps.types import (
    DnsPageDeps,
    DpiRuntimeActions,
    HostsPageDeps,
    PremiumPageDeps,
    UpdateRuntimeActions,
)


def build_dpi_settings_page_kwargs(
    *,
    page_name: PageName,
    dpi_settings_feature,
    orchestra_feature,
    runtime_feature,
    set_status,
    after_launch_method_changed,
) -> dict:
    _ = page_name
    return {
        "dpi_settings_feature": dpi_settings_feature,
        "orchestra_feature": orchestra_feature,
        "runtime_actions": DpiRuntimeActions(
            handle_launch_method_changed=runtime_feature.handle_launch_method_changed,
        ),
        "set_status": set_status,
        "after_launch_method_changed": after_launch_method_changed,
    }


def build_network_page_kwargs(*, page_name: PageName, dns_feature) -> dict:
    _ = page_name
    return {
        "deps": DnsPageDeps(dns_feature=dns_feature),
    }


def build_hosts_page_kwargs(*, page_name: PageName, hosts_feature) -> dict:
    _ = page_name
    return {
        "deps": HostsPageDeps(hosts_feature=hosts_feature),
    }


def build_premium_page_kwargs(*, page_name: PageName, premium_feature, ui_state_store) -> dict:
    _ = page_name
    return {
        "deps": PremiumPageDeps(
            premium_feature=premium_feature,
            subscription_state_store=ui_state_store,
        ),
    }


def build_support_page_kwargs(*, page_name: PageName, external_actions_feature) -> dict:
    _ = page_name
    import about.plans as about_page_plans

    return {
        "open_discussions": about_page_plans.open_support_discussions,
        "open_telegram": lambda: about_page_plans.open_telegram("zaprethelp"),
        "open_discord": lambda: about_page_plans.open_discord("https://discord.gg/kkcBDG2uws"),
        "create_open_action_worker": external_actions_feature.create_external_action_worker,
    }


def build_autostart_page_kwargs(*, page_name: PageName, autostart_feature, show_page, notify, ui_state_store) -> dict:
    _ = page_name
    return {
        "autostart_feature": autostart_feature,
        "open_dpi_settings": lambda: show_page(PageName.DPI_SETTINGS),
        "notify": notify,
        "ui_state_store": ui_state_store,
    }


def build_appearance_page_kwargs(
    *,
    page_name: PageName,
    appearance_feature,
    set_garland_enabled,
    set_snowflakes_enabled,
    on_background_refresh_needed,
    on_background_preset_changed,
    on_opacity_changed,
    on_mica_changed,
    on_animations_changed,
    on_smooth_scroll_changed,
    on_editor_smooth_scroll_changed,
    on_ui_language_changed,
    on_sidebar_icon_style_changed,
    ui_state_store,
) -> dict:
    _ = page_name
    return {
        "on_garland_changed": set_garland_enabled,
        "on_snowflakes_changed": set_snowflakes_enabled,
        "on_background_refresh_needed": on_background_refresh_needed,
        "on_background_preset_changed": on_background_preset_changed,
        "on_opacity_changed": on_opacity_changed,
        "on_mica_changed": on_mica_changed,
        "on_animations_changed": on_animations_changed,
        "on_smooth_scroll_changed": on_smooth_scroll_changed,
        "on_editor_smooth_scroll_changed": on_editor_smooth_scroll_changed,
        "on_ui_language_changed": on_ui_language_changed,
        "on_sidebar_icon_style_changed": on_sidebar_icon_style_changed,
        "appearance_feature": appearance_feature,
        "ui_state_store": ui_state_store,
    }


def build_about_page_kwargs(*, page_name: PageName, external_actions_feature, show_page, ui_state_store) -> dict:
    _ = page_name
    import about.plans as about_page_plans

    return {
        "open_premium": lambda: show_page(PageName.PREMIUM),
        "open_updates": lambda: show_page(PageName.SERVERS, allow_internal=True),
        "open_discussions": about_page_plans.open_support_discussions,
        "open_support_telegram": lambda: about_page_plans.open_telegram("zaprethelp"),
        "open_support_discord": lambda: about_page_plans.open_discord("https://discord.gg/kkcBDG2uws"),
        "open_forum_for_beginners": lambda: about_page_plans.open_telegram("bypassblock", post=1359),
        "open_help_folder": about_page_plans.open_help_folder,
        "open_telegram_news": lambda: about_page_plans.open_telegram("bypassblock"),
        "open_kvn_channel": lambda: about_page_plans.open_telegram("vpndiscordyooutube"),
        "open_kvn_bot": lambda: about_page_plans.open_telegram("zapretvpns_bot"),
        "open_kvn_bypass": lambda: about_page_plans.open_telegram("bypassblock"),
        "open_kvn_github": lambda: about_page_plans.open_github("https://github.com/youtubediscord/zapret-kvn"),
        "create_open_action_worker": external_actions_feature.create_external_action_worker,
        "ui_state_store": ui_state_store,
    }


def build_servers_page_kwargs(
    *,
    page_name: PageName,
    runtime_feature,
    updater_feature,
    external_actions_feature,
    show_page,
) -> dict:
    _ = page_name

    def _create_changelog_link_open_worker(request_id: int, *, url: str, parent=None):
        return external_actions_feature.create_open_url_worker(
            request_id,
            url=url,
            parent=parent,
        )

    return {
        "runtime_actions": UpdateRuntimeActions(
            is_any_running=runtime_feature.is_any_running,
            shutdown_sync=runtime_feature.shutdown_sync,
            is_available=runtime_feature.is_available,
            restart=runtime_feature.restart,
        ),
        "updater_feature": updater_feature,
        "open_about": lambda: show_page(PageName.ABOUT),
        "create_changelog_link_open_worker": _create_changelog_link_open_worker,
    }


def build_blockcheck_page_kwargs(
    *,
    page_name: PageName,
    blockcheck_feature,
    diagnostics_feature,
    dns_feature,
    runtime_feature,
) -> dict:
    _ = page_name

    def _create_strategy_scan_worker(**kwargs):
        return blockcheck_feature.create_strategy_scan_worker(
            **kwargs,
            shutdown_sync=runtime_feature.shutdown_sync,
        )

    return {
        "blockcheck_feature": blockcheck_feature,
        "diagnostics_feature": diagnostics_feature,
        "dns_feature": dns_feature,
        "create_strategy_scan_worker": _create_strategy_scan_worker,
    }


def build_logs_page_kwargs(*, page_name: PageName, logs_feature, orchestra_feature) -> dict:
    _ = page_name
    return {
        "logs_feature": logs_feature,
        "orchestra_feature": orchestra_feature,
    }


def build_telegram_proxy_page_kwargs(*, page_name: PageName, runtime_feature, telegram_proxy_feature) -> dict:
    _ = page_name

    def _get_zapret_running() -> bool:
        return bool(runtime_feature.is_any_running(silent=True))

    return {
        "telegram_proxy_feature": telegram_proxy_feature,
        "get_zapret_running": _get_zapret_running,
    }


def build_orchestra_page_kwargs(*, page_name: PageName, orchestra_feature, runtime_feature) -> dict:
    _ = page_name

    def _is_runtime_running() -> bool:
        return bool(runtime_feature.is_any_running(silent=True))

    return {
        "orchestra_feature": orchestra_feature,
        "is_runtime_running": _is_runtime_running,
    }


def build_orchestra_settings_page_kwargs(*, page_name: PageName, orchestra_feature) -> dict:
    _ = page_name

    return {
        "orchestra_feature": orchestra_feature,
    }


__all__ = [
    "build_about_page_kwargs",
    "build_appearance_page_kwargs",
    "build_autostart_page_kwargs",
    "build_blockcheck_page_kwargs",
    "build_dpi_settings_page_kwargs",
    "build_hosts_page_kwargs",
    "build_logs_page_kwargs",
    "build_network_page_kwargs",
    "build_orchestra_page_kwargs",
    "build_orchestra_settings_page_kwargs",
    "build_premium_page_kwargs",
    "build_servers_page_kwargs",
    "build_support_page_kwargs",
    "build_telegram_proxy_page_kwargs",
]
