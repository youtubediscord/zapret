from __future__ import annotations

from app.page_names import PageName
from ui.page_deps.common import PageDepsSpec
from ui.page_deps.presets import (
    build_control_page_kwargs,
    build_preset_raw_editor_page_kwargs,
    build_preset_setup_page_kwargs,
    build_profile_order_page_kwargs,
    build_profile_setup_page_kwargs,
    build_user_presets_page_kwargs,
)
from ui.page_deps.system import (
    build_about_page_kwargs,
    build_appearance_page_kwargs,
    build_autostart_page_kwargs,
    build_blobs_page_kwargs,
    build_blockcheck_page_kwargs,
    build_dpi_settings_page_kwargs,
    build_hosts_page_kwargs,
    build_logs_page_kwargs,
    build_network_page_kwargs,
    build_orchestra_page_kwargs,
    build_orchestra_settings_page_kwargs,
    build_premium_page_kwargs,
    build_servers_page_kwargs,
    build_support_page_kwargs,
    build_telegram_proxy_page_kwargs,
)
from ui.page_deps.types import DnsPageDeps, HostsPageDeps, PremiumPageDeps


PAGE_DEPS_BUILDERS: dict[PageName, PageDepsSpec] = {
    PageName.ZAPRET2_MODE_CONTROL: PageDepsSpec(
        build_control_page_kwargs,
        features=("presets", "profile", "runtime", "program_settings", "external_actions"),
        actions=("set_status", "request_exit", "open_connection_test", "open_folder", "show_page"),
        include_ui_state_store=True,
    ),
    PageName.ZAPRET1_MODE_CONTROL: PageDepsSpec(
        build_control_page_kwargs,
        features=("presets", "profile", "runtime", "program_settings", "external_actions"),
        actions=("set_status", "request_exit", "open_connection_test", "open_folder", "show_page"),
        include_ui_state_store=True,
    ),
    PageName.ZAPRET2_PRESET_SETUP: PageDepsSpec(
        build_preset_setup_page_kwargs,
        features=("profile",),
        actions=("open_profile_setup", "show_page"),
        include_ui_state_store=True,
    ),
    PageName.ZAPRET1_PRESET_SETUP: PageDepsSpec(
        build_preset_setup_page_kwargs,
        features=("profile",),
        actions=("open_profile_setup", "show_page"),
        include_ui_state_store=True,
    ),
    PageName.ZAPRET2_PROFILE_SETUP: PageDepsSpec(
        build_profile_setup_page_kwargs,
        features=("profile",),
        actions=("show_page", "on_profile_setup_changed"),
    ),
    PageName.ZAPRET1_PROFILE_SETUP: PageDepsSpec(
        build_profile_setup_page_kwargs,
        features=("profile",),
        actions=("show_page", "on_profile_setup_changed"),
    ),
    PageName.ZAPRET2_PROFILE_ORDER: PageDepsSpec(
        build_profile_order_page_kwargs,
        features=("profile",),
        actions=("show_page",),
    ),
    PageName.ZAPRET1_PROFILE_ORDER: PageDepsSpec(
        build_profile_order_page_kwargs,
        features=("profile",),
        actions=("show_page",),
    ),
    PageName.ZAPRET2_USER_PRESETS: PageDepsSpec(
        build_user_presets_page_kwargs,
        features=("presets", "external_actions"),
        actions=("open_preset_raw_editor",),
        include_ui_state_store=True,
    ),
    PageName.ZAPRET1_USER_PRESETS: PageDepsSpec(
        build_user_presets_page_kwargs,
        features=("presets", "external_actions"),
        actions=("open_preset_raw_editor",),
        include_ui_state_store=True,
    ),
    PageName.ZAPRET2_PRESET_RAW_EDITOR: PageDepsSpec(
        build_preset_raw_editor_page_kwargs,
        features=("presets", "runtime"),
        actions=("show_page",),
        include_ui_state_store=True,
    ),
    PageName.ZAPRET1_PRESET_RAW_EDITOR: PageDepsSpec(
        build_preset_raw_editor_page_kwargs,
        features=("presets", "runtime"),
        actions=("show_page",),
        include_ui_state_store=True,
    ),
    PageName.DPI_SETTINGS: PageDepsSpec(
        build_dpi_settings_page_kwargs,
        features=("dpi_settings", "orchestra", "runtime"),
        actions=("set_status", "after_launch_method_changed"),
    ),
    PageName.BLOBS: PageDepsSpec(
        build_blobs_page_kwargs,
        features=("blobs",),
        actions=("show_active_mode_control_page",),
    ),
    PageName.NETWORK: PageDepsSpec(build_network_page_kwargs, features=("dns",)),
    PageName.HOSTS: PageDepsSpec(build_hosts_page_kwargs, features=("hosts",)),
    PageName.PREMIUM: PageDepsSpec(
        build_premium_page_kwargs,
        features=("premium",),
        include_ui_state_store=True,
    ),
    PageName.SUPPORT: PageDepsSpec(build_support_page_kwargs, features=("external_actions",)),
    PageName.AUTOSTART: PageDepsSpec(
        build_autostart_page_kwargs,
        features=("autostart",),
        actions=("show_page", "notify"),
        include_ui_state_store=True,
    ),
    PageName.APPEARANCE: PageDepsSpec(
        build_appearance_page_kwargs,
        features=("appearance",),
        actions=(
            "set_garland_enabled",
            "set_snowflakes_enabled",
            "on_background_refresh_needed",
            "on_background_preset_changed",
            "on_opacity_changed",
            "on_mica_changed",
            "on_animations_changed",
            "on_smooth_scroll_changed",
            "on_editor_smooth_scroll_changed",
            "on_ui_language_changed",
            "on_sidebar_icon_style_changed",
        ),
        include_ui_state_store=True,
    ),
    PageName.ABOUT: PageDepsSpec(
        build_about_page_kwargs,
        features=("external_actions",),
        actions=("show_page",),
        include_ui_state_store=True,
    ),
    PageName.SERVERS: PageDepsSpec(
        build_servers_page_kwargs,
        features=("runtime", "updater", "external_actions"),
        actions=("show_page",),
    ),
    PageName.BLOCKCHECK: PageDepsSpec(
        build_blockcheck_page_kwargs,
        features=("blockcheck", "diagnostics", "dns", "runtime"),
    ),
    PageName.LOGS: PageDepsSpec(
        build_logs_page_kwargs,
        features=("logs", "orchestra", "runtime"),
    ),
    PageName.TELEGRAM_PROXY: PageDepsSpec(
        build_telegram_proxy_page_kwargs,
        features=("runtime", "telegram_proxy"),
    ),
    PageName.ORCHESTRA: PageDepsSpec(
        build_orchestra_page_kwargs,
        features=("orchestra", "runtime"),
    ),
    PageName.ORCHESTRA_SETTINGS: PageDepsSpec(
        build_orchestra_settings_page_kwargs,
        features=("orchestra",),
    ),
}


def validate_page_deps_builder_coverage(page_names) -> None:
    missing = tuple(page_name for page_name in page_names if page_name not in PAGE_DEPS_BUILDERS)
    if missing:
        names = ", ".join(page_name.name for page_name in missing)
        raise RuntimeError(f"Missing page deps builders: {names}")


def build_page_deps(context, page_name: PageName) -> dict:
    """Возвращает зависимости страницы по явной карте."""
    spec = PAGE_DEPS_BUILDERS.get(page_name)
    if spec is None:
        raise RuntimeError(f"Missing page deps builder for {page_name.name}")
    return spec.build(context, page_name)


__all__ = [
    "DnsPageDeps",
    "HostsPageDeps",
    "PAGE_DEPS_BUILDERS",
    "PremiumPageDeps",
    "build_page_deps",
    "validate_page_deps_builder_coverage",
]
