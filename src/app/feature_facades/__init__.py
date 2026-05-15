from __future__ import annotations

from app.feature_facades.autostart import AutostartFeature, build_autostart_feature
from app.feature_facades.blockcheck import BlockcheckFeature
from app.feature_facades.blobs import BlobsFeature, build_blobs_feature
from app.feature_facades.diagnostics import DiagnosticsFeature, build_diagnostics_feature
from app.feature_facades.dns import DnsFeature, build_dns_feature
from app.feature_facades.dpi_settings import DpiSettingsFeature, build_dpi_settings_feature
from app.feature_facades.external import ExternalActionsFeature, build_external_actions_feature
from app.feature_facades.hosts import HostsFeature, build_hosts_feature
from app.feature_facades.lists import ListsFeature, build_lists_feature
from app.feature_facades.logs import LogsFeature
from app.feature_facades.orchestra import OrchestraFeature, build_orchestra_feature
from app.feature_facades.premium import PremiumFeature, build_premium_feature
from app.feature_facades.presets import PresetsFeature
from app.feature_facades.profile import ProfileFeature
from app.feature_facades.program_settings import ProgramSettingsFeature, build_program_settings_feature
from app.feature_facades.runtime import RuntimeFeature, build_runtime_feature
from app.feature_facades.telegram_proxy import TelegramProxyFeature, build_telegram_proxy_feature
from app.feature_facades.tray import TrayFeature, build_tray_feature
from app.feature_facades.updater import UpdaterFeature, build_updater_feature


def build_logs_feature() -> LogsFeature:
    return LogsFeature()

__all__ = [
    "AutostartFeature",
    "BlockcheckFeature",
    "BlobsFeature",
    "DiagnosticsFeature",
    "DnsFeature",
    "DpiSettingsFeature",
    "ExternalActionsFeature",
    "HostsFeature",
    "ListsFeature",
    "LogsFeature",
    "OrchestraFeature",
    "PremiumFeature",
    "PresetsFeature",
    "ProfileFeature",
    "ProgramSettingsFeature",
    "RuntimeFeature",
    "TelegramProxyFeature",
    "TrayFeature",
    "UpdaterFeature",
    "build_autostart_feature",
    "build_blobs_feature",
    "build_diagnostics_feature",
    "build_dns_feature",
    "build_dpi_settings_feature",
    "build_external_actions_feature",
    "build_hosts_feature",
    "build_lists_feature",
    "build_logs_feature",
    "build_orchestra_feature",
    "build_premium_feature",
    "build_program_settings_feature",
    "build_runtime_feature",
    "build_telegram_proxy_feature",
    "build_tray_feature",
    "build_updater_feature",
]
