from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.page_names import PageName
from ui.window_adapter import show_page
from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE
from ui.navigation_pages import (
    resolve_preset_raw_editor_back_page_for_method,
    resolve_preset_raw_editor_root_page_for_method,
    resolve_profile_setup_root_page_for_method,
)
from ui.profile_setup_workflow import on_open_profile_setup, on_profile_setup_changed
from ui.navigation.text_sync import on_ui_language_changed
from ui.window_appearance_state import (
    on_animations_changed,
    on_background_preset_changed,
    on_background_refresh_needed,
    on_editor_smooth_scroll_changed,
    on_mica_changed,
    on_opacity_changed,
    on_smooth_scroll_changed,
)
from ui.workflows.mode import open_preset_raw_editor_for_method, show_active_mode_control_page


PageDepsBuilder = Callable[[object, PageName], dict]


@dataclass(frozen=True, slots=True)
class DnsPageDeps:
    dns_feature: object


@dataclass(frozen=True, slots=True)
class HostsPageDeps:
    hosts_feature: object


@dataclass(frozen=True, slots=True)
class PremiumPageDeps:
    premium_feature: object
    subscription_state_store: object


def _runtime_parts(window):
    app_runtime = window.app_runtime
    return app_runtime.features, app_runtime.state


def _build_control_page_kwargs(window, page_name: PageName) -> dict:
    features, state = _runtime_parts(window)
    if page_name in {
        PageName.ZAPRET2_MODE_CONTROL,
        PageName.ZAPRET1_MODE_CONTROL,
    }:
        if page_name == PageName.ZAPRET2_MODE_CONTROL:
            user_presets_page = PageName.ZAPRET2_USER_PRESETS
            preset_setup_page = PageName.ZAPRET2_PRESET_SETUP
        else:
            user_presets_page = PageName.ZAPRET1_USER_PRESETS
            preset_setup_page = PageName.ZAPRET1_PRESET_SETUP
        return {
            "presets_feature": features.presets,
            "profile_feature": features.profile,
            "runtime_feature": features.runtime,
            "program_settings_feature": features.program_settings,
            "set_status": window.set_status,
            "request_exit": window.request_exit,
            "open_connection_test": window.open_connection_test,
            "open_folder": window.open_folder,
            "open_presets": lambda page=user_presets_page: show_page(window, page, allow_internal=True),
            "open_preset_setup": lambda page=preset_setup_page: show_page(window, page, allow_internal=True),
            "open_blobs": lambda: show_page(window, PageName.BLOBS, allow_internal=True),
            "external_actions_feature": features.external_actions,
            "ui_state_store": state.ui,
        }



def _build_preset_setup_page_kwargs(window, page_name: PageName) -> dict:
    features, _state = _runtime_parts(window)
    method = ZAPRET2_MODE if page_name == PageName.ZAPRET2_PRESET_SETUP else ZAPRET1_MODE
    control_page = (
        PageName.ZAPRET2_MODE_CONTROL
        if page_name == PageName.ZAPRET2_PRESET_SETUP
        else PageName.ZAPRET1_MODE_CONTROL
    )
    return {
        "profile_feature": features.profile,
        "open_control": lambda page=control_page: show_page(window, page, allow_internal=True),
        "open_profile_setup": lambda profile_key, m=method: on_open_profile_setup(window, m, profile_key),
    }


def _build_profile_setup_page_kwargs(window, page_name: PageName) -> dict:
    features, _state = _runtime_parts(window)
    method = ZAPRET2_MODE if page_name == PageName.ZAPRET2_PROFILE_SETUP else ZAPRET1_MODE
    profiles_page = (
        PageName.ZAPRET2_PRESET_SETUP
        if page_name == PageName.ZAPRET2_PROFILE_SETUP
        else PageName.ZAPRET1_PRESET_SETUP
    )
    return {
        "profile_feature": features.profile,
        "open_profiles": lambda page=profiles_page: show_page(window, page, allow_internal=True),
        "open_root": lambda m=method: show_page(window, resolve_profile_setup_root_page_for_method(m), allow_internal=True),
        "on_profile_changed": lambda profile_key, change_kind, m=method: on_profile_setup_changed(
            window,
            m,
            profile_key,
            change_kind,
        ),
    }


def _build_user_presets_page_kwargs(window, page_name: PageName) -> dict:
    features, state = _runtime_parts(window)
    method = ZAPRET2_MODE if page_name == PageName.ZAPRET2_USER_PRESETS else ZAPRET1_MODE
    control_page = (
        PageName.ZAPRET2_MODE_CONTROL
        if page_name == PageName.ZAPRET2_USER_PRESETS
        else PageName.ZAPRET1_MODE_CONTROL
    )
    return {
        "presets_feature": features.presets,
        "runtime_feature": features.runtime,
        "open_control": lambda page=control_page: show_page(window, page, allow_internal=True),
        "open_preset_raw_editor": lambda preset_name, m=method: open_preset_raw_editor_for_method(
            window,
            m,
            preset_name,
            allow_internal=True,
        ),
        "external_actions_feature": features.external_actions,
        "ui_state_store": state.ui,
    }


def _build_preset_raw_editor_page_kwargs(window, page_name: PageName) -> dict:
    features, state = _runtime_parts(window)
    method = ZAPRET2_MODE if page_name == PageName.ZAPRET2_PRESET_RAW_EDITOR else ZAPRET1_MODE
    return {
        "presets_feature": features.presets,
        "launch_method": method,
        "title": "Пресет Zapret 2" if method == ZAPRET2_MODE else "Пресет Zapret 1",
        "open_back": lambda m=method: show_page(
            window,
            resolve_preset_raw_editor_back_page_for_method(m),
            allow_internal=True,
        ),
        "open_root": lambda m=method: show_page(
            window,
            resolve_preset_raw_editor_root_page_for_method(m),
            allow_internal=True,
        ),
        "ui_state_store": state.ui,
    }


def _build_dpi_settings_page_kwargs(window, _page_name: PageName) -> dict:
    from ui.workflows.mode import apply_launch_method_changed_ui

    features, _state = _runtime_parts(window)
    return {
        "dpi_settings_feature": features.dpi_settings,
        "orchestra_feature": features.orchestra,
        "runtime_feature": features.runtime,
        "set_status": window.set_status,
        "after_launch_method_changed": lambda method: apply_launch_method_changed_ui(window, method),
    }


def _build_blobs_page_kwargs(window, _page_name: PageName) -> dict:
    features, _state = _runtime_parts(window)
    return {
        "blobs_feature": features.blobs,
        "open_control": lambda: show_active_mode_control_page(window, allow_internal=False),
    }


def _build_lists_page_kwargs(window, _page_name: PageName) -> dict:
    features, _state = _runtime_parts(window)
    return {
        "lists_feature": features.lists,
    }


def _build_network_page_kwargs(window, _page_name: PageName) -> dict:
    features, _state = _runtime_parts(window)
    return {
        "deps": DnsPageDeps(dns_feature=features.dns),
    }


def _build_hosts_page_kwargs(window, _page_name: PageName) -> dict:
    features, _state = _runtime_parts(window)
    return {
        "deps": HostsPageDeps(hosts_feature=features.hosts),
    }


def _build_premium_page_kwargs(window, _page_name: PageName) -> dict:
    features, state = _runtime_parts(window)
    return {
        "deps": PremiumPageDeps(
            premium_feature=features.premium,
            subscription_state_store=state.ui,
        ),
    }


def _build_support_page_kwargs(_window, _page_name: PageName) -> dict:
    import about.plans as about_page_plans

    return {
        "open_discussions": about_page_plans.open_support_discussions,
        "open_telegram": lambda: about_page_plans.open_telegram("zaprethelp"),
        "open_discord": lambda: about_page_plans.open_discord("https://discord.gg/kkcBDG2uws"),
    }


def _build_autostart_page_kwargs(window, _page_name: PageName) -> dict:
    features, state = _runtime_parts(window)
    return {
        "autostart_feature": features.autostart,
        "open_dpi_settings": lambda: show_page(window, PageName.DPI_SETTINGS),
        "ui_state_store": state.ui,
    }


def _build_appearance_page_kwargs(window, _page_name: PageName) -> dict:
    _features, state = _runtime_parts(window)
    return {
        "on_garland_changed": window.set_garland_enabled,
        "on_snowflakes_changed": window.set_snowflakes_enabled,
        "on_background_refresh_needed": lambda: on_background_refresh_needed(window),
        "on_background_preset_changed": lambda preset: on_background_preset_changed(window, preset),
        "on_opacity_changed": lambda value: on_opacity_changed(window, value),
        "on_mica_changed": lambda enabled: on_mica_changed(window, enabled),
        "on_animations_changed": lambda enabled: on_animations_changed(window, enabled),
        "on_smooth_scroll_changed": lambda enabled: on_smooth_scroll_changed(window, enabled),
        "on_editor_smooth_scroll_changed": lambda enabled: on_editor_smooth_scroll_changed(window, enabled),
        "on_ui_language_changed": lambda language: on_ui_language_changed(window, language),
        "ui_state_store": state.ui,
    }


def _build_about_page_kwargs(window, _page_name: PageName) -> dict:
    import about.plans as about_page_plans

    _features, state = _runtime_parts(window)
    return {
        "open_premium": lambda: show_page(window, PageName.PREMIUM),
        "open_updates": lambda: show_page(window, PageName.SERVERS, allow_internal=True),
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
        "ui_state_store": state.ui,
    }


def _build_servers_page_kwargs(window, _page_name: PageName) -> dict:
    features, _state = _runtime_parts(window)
    return {
        "runtime_feature": features.runtime,
        "updater_feature": features.updater,
        "open_about": lambda: show_page(window, PageName.ABOUT),
        "external_actions_feature": features.external_actions,
    }


def _build_blockcheck_page_kwargs(window, _page_name: PageName) -> dict:
    features, _state = _runtime_parts(window)
    return {
        "blockcheck_feature": features.blockcheck,
        "diagnostics_feature": features.diagnostics,
        "dns_feature": features.dns,
        "runtime_feature": features.runtime,
    }


def _build_logs_page_kwargs(window, _page_name: PageName) -> dict:
    features, _state = _runtime_parts(window)
    return {
        "logs_feature": features.logs,
        "orchestra_feature": features.orchestra,
        "runtime_feature": features.runtime,
    }


def _build_telegram_proxy_page_kwargs(window, _page_name: PageName) -> dict:
    features, _state = _runtime_parts(window)
    return {
        "runtime_feature": features.runtime,
        "telegram_proxy_feature": features.telegram_proxy,
    }


def _build_orchestra_page_kwargs(window, _page_name: PageName) -> dict:
    features, _state = _runtime_parts(window)
    return {
        "orchestra_feature": features.orchestra,
        "runtime_feature": features.runtime,
    }


def _build_orchestra_settings_page_kwargs(window, _page_name: PageName) -> dict:
    features, _state = _runtime_parts(window)
    return {
        "orchestra_feature": features.orchestra,
    }


PAGE_DEPS_BUILDERS: dict[PageName, PageDepsBuilder] = {
    PageName.ZAPRET2_MODE_CONTROL: _build_control_page_kwargs,
    PageName.ZAPRET1_MODE_CONTROL: _build_control_page_kwargs,
    PageName.ZAPRET2_PRESET_SETUP: _build_preset_setup_page_kwargs,
    PageName.ZAPRET1_PRESET_SETUP: _build_preset_setup_page_kwargs,
    PageName.ZAPRET2_PROFILE_SETUP: _build_profile_setup_page_kwargs,
    PageName.ZAPRET1_PROFILE_SETUP: _build_profile_setup_page_kwargs,
    PageName.ZAPRET2_USER_PRESETS: _build_user_presets_page_kwargs,
    PageName.ZAPRET1_USER_PRESETS: _build_user_presets_page_kwargs,
    PageName.ZAPRET2_PRESET_RAW_EDITOR: _build_preset_raw_editor_page_kwargs,
    PageName.ZAPRET1_PRESET_RAW_EDITOR: _build_preset_raw_editor_page_kwargs,
    PageName.DPI_SETTINGS: _build_dpi_settings_page_kwargs,
    PageName.BLOBS: _build_blobs_page_kwargs,
    PageName.HOSTLIST: _build_lists_page_kwargs,
    PageName.NETROGAT: _build_lists_page_kwargs,
    PageName.CUSTOM_DOMAINS: _build_lists_page_kwargs,
    PageName.CUSTOM_IPSET: _build_lists_page_kwargs,
    PageName.NETWORK: _build_network_page_kwargs,
    PageName.HOSTS: _build_hosts_page_kwargs,
    PageName.PREMIUM: _build_premium_page_kwargs,
    PageName.SUPPORT: _build_support_page_kwargs,
    PageName.AUTOSTART: _build_autostart_page_kwargs,
    PageName.APPEARANCE: _build_appearance_page_kwargs,
    PageName.ABOUT: _build_about_page_kwargs,
    PageName.SERVERS: _build_servers_page_kwargs,
    PageName.BLOCKCHECK: _build_blockcheck_page_kwargs,
    PageName.LOGS: _build_logs_page_kwargs,
    PageName.TELEGRAM_PROXY: _build_telegram_proxy_page_kwargs,
    PageName.ORCHESTRA: _build_orchestra_page_kwargs,
    PageName.ORCHESTRA_SETTINGS: _build_orchestra_settings_page_kwargs,
}


def validate_page_deps_builder_coverage(page_names) -> None:
    missing = tuple(page_name for page_name in page_names if page_name not in PAGE_DEPS_BUILDERS)
    if missing:
        names = ", ".join(page_name.name for page_name in missing)
        raise RuntimeError(f"Missing page deps builders: {names}")


def build_page_deps(window, page_name: PageName) -> dict:
    """Собирает явные зависимости для страницы.

    Navigation schema говорит, какая страница существует.
    PageFactory создаёт виджет.
    Этот слой выдаёт странице только нужные feature/state/callback.
    """
    builder = PAGE_DEPS_BUILDERS.get(page_name)
    if builder is None:
        raise RuntimeError(f"Missing page deps builder for {page_name.name}")
    return builder(window, page_name)


__all__ = [
    "DnsPageDeps",
    "HostsPageDeps",
    "PAGE_DEPS_BUILDERS",
    "PremiumPageDeps",
    "build_page_deps",
    "validate_page_deps_builder_coverage",
]
