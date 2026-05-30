from __future__ import annotations

from dataclasses import dataclass
import time as _time
from typing import Any

from app.features import AppFeatures
from main.runtime_state import log_startup_metric as emit_startup_metric


@dataclass(frozen=True, slots=True)
class PresetProfileFeatures:
    presets: PresetsFeature
    profile: ProfileFeature


@dataclass(frozen=True, slots=True)
class RuntimeFeatureDeps:
    qt_parent: Any
    startup_state: Any
    mark_stop_and_exit_requested: Any


@dataclass(frozen=True, slots=True)
class PremiumFeatureDeps:
    thread_parent: Any
    set_status: Any
    update_title_badge: Any
    init_holiday_effects: Any
    mark_startup_ready: Any


@dataclass(frozen=True, slots=True)
class TrayFeatureDeps:
    window_port: Any
    startup_state: Any
    close_state: Any
    start_in_tray: bool
    startup_post_init_ready: Any
    set_window_opacity: Any


@dataclass(frozen=True, slots=True)
class AppFeatureAssemblyDeps:
    runtime: RuntimeFeatureDeps
    premium: PremiumFeatureDeps
    tray: TrayFeatureDeps


def build_preset_profile_features(paths: Any) -> PresetProfileFeatures:
    t_import = _time.perf_counter()
    from app.feature_facades import PresetsFeature, ProfileFeature
    emit_startup_metric(
        "StartupFeatureAssemblyPresetProfileImport",
        f"{(_time.perf_counter() - t_import) * 1000:.0f}ms",
    )

    t_presets = _time.perf_counter()
    presets_feature = PresetsFeature.create(paths)
    emit_startup_metric(
        "StartupFeatureAssemblyPresets",
        f"{(_time.perf_counter() - t_presets) * 1000:.0f}ms",
    )
    t_profile = _time.perf_counter()
    profile_feature = ProfileFeature(
        _presets_feature=presets_feature,
        _app_paths=paths,
    )
    presets_feature.attach_profile_feature(profile_feature)
    emit_startup_metric(
        "StartupFeatureAssemblyProfile",
        f"{(_time.perf_counter() - t_profile) * 1000:.0f}ms",
    )
    return PresetProfileFeatures(
        presets=presets_feature,
        profile=profile_feature,
    )


def build_app_features(*, deps: AppFeatureAssemblyDeps, paths: Any, state: Any) -> AppFeatures:
    """Собирает feature-входы без превращения AppFeatures в общий контейнер."""
    t_import = _time.perf_counter()
    from app.feature_facades import (
        BlockcheckFeature,
        build_appearance_feature,
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
    emit_startup_metric(
        "StartupFeatureAssemblyImports",
        f"{(_time.perf_counter() - t_import) * 1000:.0f}ms",
    )

    t_orchestra = _time.perf_counter()
    orchestra_feature = build_orchestra_feature()
    emit_startup_metric(
        "StartupFeatureAssemblyOrchestra",
        f"{(_time.perf_counter() - t_orchestra) * 1000:.0f}ms",
    )
    t_preset_profile = _time.perf_counter()
    preset_profile = build_preset_profile_features(paths)
    emit_startup_metric(
        "StartupFeatureAssemblyPresetProfile",
        f"{(_time.perf_counter() - t_preset_profile) * 1000:.0f}ms",
    )

    t_runtime = _time.perf_counter()
    runtime_feature = build_runtime_feature(
        qt_parent=deps.runtime.qt_parent,
        startup_state=deps.runtime.startup_state,
        mark_stop_and_exit_requested=deps.runtime.mark_stop_and_exit_requested,
        state=state,
        presets_feature=preset_profile.presets,
        profile_feature=preset_profile.profile,
        orchestra_feature=orchestra_feature,
    )
    emit_startup_metric(
        "StartupFeatureAssemblyRuntime",
        f"{(_time.perf_counter() - t_runtime) * 1000:.0f}ms",
    )
    t_telegram_proxy = _time.perf_counter()
    telegram_proxy_feature = build_telegram_proxy_feature()
    emit_startup_metric(
        "StartupFeatureAssemblyTelegramProxy",
        f"{(_time.perf_counter() - t_telegram_proxy) * 1000:.0f}ms",
    )
    t_tray = _time.perf_counter()
    tray_feature = build_tray_feature(
        deps=deps.tray,
        runtime_feature=runtime_feature,
        telegram_proxy_feature=telegram_proxy_feature,
    )
    emit_startup_metric(
        "StartupFeatureAssemblyTray",
        f"{(_time.perf_counter() - t_tray) * 1000:.0f}ms",
    )

    t_secondary = _time.perf_counter()
    features = AppFeatures(
        appearance=build_appearance_feature(),
        runtime=runtime_feature,
        premium=build_premium_feature(deps=deps.premium, ui_state_store=state.ui),
        presets=preset_profile.presets,
        profile=preset_profile.profile,
        blockcheck=BlockcheckFeature(
            presets_feature=preset_profile.presets,
            profile_feature=preset_profile.profile,
        ),
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
    emit_startup_metric(
        "StartupFeatureAssemblySecondary",
        f"{(_time.perf_counter() - t_secondary) * 1000:.0f}ms",
    )
    return features


__all__ = [
    "AppFeatureAssemblyDeps",
    "PremiumFeatureDeps",
    "PresetProfileFeatures",
    "RuntimeFeatureDeps",
    "TrayFeatureDeps",
    "build_app_features",
    "build_preset_profile_features",
]
