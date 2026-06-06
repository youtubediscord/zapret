from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.feature_facades import (
        AppearanceFeature,
        BlockcheckFeature,
        DiagnosticsFeature,
        DnsFeature,
        DpiSettingsFeature,
        ExternalActionsFeature,
        HostsFeature,
        ListsFeature,
        LogsFeature,
        OrchestraFeature,
        PremiumFeature,
        PresetsFeature,
        ProfileFeature,
        ProgramSettingsFeature,
        RuntimeFeature,
        TelegramProxyFeature,
        TrayFeature,
        UpdaterFeature,
        WindowGeometryFeature,
    )


@dataclass(frozen=True, slots=True)
class AppFeatures:
    appearance: AppearanceFeature
    runtime: RuntimeFeature
    premium: PremiumFeature
    presets: PresetsFeature
    profile: ProfileFeature
    blockcheck: BlockcheckFeature
    diagnostics: DiagnosticsFeature
    dns: DnsFeature
    hosts: HostsFeature
    lists: ListsFeature
    logs: LogsFeature
    dpi_settings: DpiSettingsFeature
    telegram_proxy: TelegramProxyFeature
    tray: TrayFeature
    updater: UpdaterFeature
    external_actions: ExternalActionsFeature
    orchestra: OrchestraFeature
    program_settings: ProgramSettingsFeature
    window_geometry: WindowGeometryFeature
