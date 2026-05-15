from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.feature_facades import (
    AutostartFeature,
    BlockcheckFeature,
    BlobsFeature,
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
    build_autostart_feature,
    build_blobs_feature,
    build_diagnostics_feature,
    build_dns_feature,
    build_dpi_settings_feature,
    build_external_actions_feature,
    build_hosts_feature,
    build_lists_feature,
    build_logs_feature,
    build_orchestra_feature,
    build_premium_feature,
    build_program_settings_feature,
    build_runtime_feature,
    build_telegram_proxy_feature,
    build_tray_feature,
    build_updater_feature,
)


@dataclass(frozen=True, slots=True)
class AppFeatures:
    runtime: RuntimeFeature
    premium: PremiumFeature
    presets: PresetsFeature
    profile: ProfileFeature
    blockcheck: BlockcheckFeature
    blobs: BlobsFeature
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
    autostart: AutostartFeature


def build_app_features(*, host: Any, paths: Any, state: Any) -> AppFeatures:
    orchestra_feature = build_orchestra_feature()
    presets_feature = PresetsFeature.create(paths)
    profile_feature = ProfileFeature(
        _presets_feature=presets_feature,
        _app_paths=paths,
    )
    presets_feature.attach_profile_feature(profile_feature)

    runtime_feature = build_runtime_feature(
        qt_parent=host,
        startup_state=host.startup_state,
        mark_stop_and_exit_requested=lambda: (
            setattr(host.close_state, "is_exiting", True),
            setattr(host.close_state, "closing_completely", True),
        ),
        state=state,
        presets_feature=presets_feature,
        profile_feature=profile_feature,
        orchestra_feature=orchestra_feature,
    )
    telegram_proxy_feature = build_telegram_proxy_feature()
    tray_feature = build_tray_feature(
        host=host,
        runtime_feature=runtime_feature,
        telegram_proxy_feature=telegram_proxy_feature,
    )

    return AppFeatures(
        runtime=runtime_feature,
        premium=build_premium_feature(host=host, ui_state_store=state.ui),
        presets=presets_feature,
        profile=profile_feature,
        blockcheck=BlockcheckFeature(presets_feature=presets_feature, profile_feature=profile_feature),
        blobs=build_blobs_feature(),
        diagnostics=build_diagnostics_feature(),
        dns=build_dns_feature(),
        hosts=build_hosts_feature(),
        lists=build_lists_feature(),
        logs=build_logs_feature(),
        dpi_settings=build_dpi_settings_feature(),
        telegram_proxy=telegram_proxy_feature,
        tray=tray_feature,
        updater=build_updater_feature(),
        external_actions=build_external_actions_feature(),
        orchestra=orchestra_feature,
        program_settings=build_program_settings_feature(),
        autostart=build_autostart_feature(runtime_state=state.runtime),
    )
