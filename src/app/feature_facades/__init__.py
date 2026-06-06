from __future__ import annotations

from importlib import import_module


_EXPORTS: dict[str, tuple[str, str]] = {
    "AppearanceFeature": ("app.feature_facades.appearance", "AppearanceFeature"),
    "BlockcheckFeature": ("app.feature_facades.blockcheck", "BlockcheckFeature"),
    "DiagnosticsFeature": ("app.feature_facades.diagnostics", "DiagnosticsFeature"),
    "DnsFeature": ("app.feature_facades.dns", "DnsFeature"),
    "DpiSettingsFeature": ("app.feature_facades.dpi_settings", "DpiSettingsFeature"),
    "ExternalActionsFeature": ("app.feature_facades.external", "ExternalActionsFeature"),
    "HostsFeature": ("app.feature_facades.hosts", "HostsFeature"),
    "ListsFeature": ("app.feature_facades.lists", "ListsFeature"),
    "LogsFeature": ("app.feature_facades.logs", "LogsFeature"),
    "OrchestraFeature": ("app.feature_facades.orchestra", "OrchestraFeature"),
    "PremiumFeature": ("app.feature_facades.premium", "PremiumFeature"),
    "PresetsFeature": ("app.feature_facades.presets", "PresetsFeature"),
    "ProfileFeature": ("app.feature_facades.profile", "ProfileFeature"),
    "ProgramSettingsFeature": ("app.feature_facades.program_settings", "ProgramSettingsFeature"),
    "RuntimeFeature": ("app.feature_facades.runtime", "RuntimeFeature"),
    "TelegramProxyFeature": ("app.feature_facades.telegram_proxy", "TelegramProxyFeature"),
    "TrayFeature": ("app.feature_facades.tray", "TrayFeature"),
    "UpdaterFeature": ("app.feature_facades.updater", "UpdaterFeature"),
    "WindowGeometryFeature": ("app.feature_facades.window_geometry", "WindowGeometryFeature"),
    "build_appearance_feature": ("app.feature_facades.appearance", "build_appearance_feature"),
    "build_diagnostics_feature": ("app.feature_facades.diagnostics", "build_diagnostics_feature"),
    "build_dns_feature": ("app.feature_facades.dns", "build_dns_feature"),
    "build_dpi_settings_feature": ("app.feature_facades.dpi_settings", "build_dpi_settings_feature"),
    "build_external_actions_feature": ("app.feature_facades.external", "build_external_actions_feature"),
    "build_hosts_feature": ("app.feature_facades.hosts", "build_hosts_feature"),
    "build_lists_feature": ("app.feature_facades.lists", "build_lists_feature"),
    "build_orchestra_feature": ("app.feature_facades.orchestra", "build_orchestra_feature"),
    "build_premium_feature": ("app.feature_facades.premium", "build_premium_feature"),
    "build_program_settings_feature": ("app.feature_facades.program_settings", "build_program_settings_feature"),
    "build_runtime_feature": ("app.feature_facades.runtime", "build_runtime_feature"),
    "build_telegram_proxy_feature": ("app.feature_facades.telegram_proxy", "build_telegram_proxy_feature"),
    "build_tray_feature": ("app.feature_facades.tray", "build_tray_feature"),
    "build_updater_feature": ("app.feature_facades.updater", "build_updater_feature"),
    "build_window_geometry_feature": ("app.feature_facades.window_geometry", "build_window_geometry_feature"),
}


def __getattr__(name: str):
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc

    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


def build_logs_feature():
    from app.feature_facades.logs import LogsFeature

    return LogsFeature()


def iter_lazy_feature_facade_modules() -> tuple[str, ...]:
    return tuple(sorted({module_name for module_name, _ in _EXPORTS.values()}))


def __dir__() -> list[str]:
    return sorted((*globals().keys(), *_EXPORTS.keys()))


__all__ = sorted((*_EXPORTS, "build_logs_feature", "iter_lazy_feature_facade_modules"))
