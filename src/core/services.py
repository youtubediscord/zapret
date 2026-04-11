from __future__ import annotations

"""Переходный service-locator для старых use-site'ов.

Новый composition root должен жить в `app_context.py`. Этот модуль пока нужен
как совместимый мост для тех мест, которые ещё не переведены на `AppContext`.
Правило переходного этапа такое:
1. если установлен `AppContext`, брать сервисы только из него;
2. если контекст ещё не собран, использовать локальный fallback;
3. новые архитектурные изменения не должны расширять этот модуль без нужды.
"""

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .direct_flow import DirectFlowCoordinator
from .paths import AppPaths
from .presets.repository import PresetRepository
from .presets.selection_service import PresetSelectionService

if TYPE_CHECKING:
    from app_context import AppContext


_APP_CONTEXT: "AppContext | None" = None


def install_app_context(app_context: "AppContext | None") -> None:
    global _APP_CONTEXT
    _APP_CONTEXT = app_context


def get_installed_app_context() -> "AppContext | None":
    return _APP_CONTEXT


def _context_attr(name: str) -> Any | None:
    context = _APP_CONTEXT
    if context is None:
        return None
    return getattr(context, name, None)


@lru_cache(maxsize=1)
def _fallback_app_paths() -> AppPaths:
    from config import get_zapret_userdata_dir

    root = Path(get_zapret_userdata_dir()).resolve()
    return AppPaths(user_root=root, local_root=root)


@lru_cache(maxsize=1)
def _fallback_preset_repository() -> PresetRepository:
    return PresetRepository(_fallback_app_paths())


@lru_cache(maxsize=1)
def _fallback_selection_service() -> PresetSelectionService:
    return PresetSelectionService(_fallback_app_paths(), _fallback_preset_repository())


@lru_cache(maxsize=1)
def _fallback_direct_flow_coordinator() -> DirectFlowCoordinator:
    return DirectFlowCoordinator()


@lru_cache(maxsize=1)
def _fallback_preset_store():
    from .presets.runtime_store import DirectRuntimePresetStore

    return DirectRuntimePresetStore("winws2")


@lru_cache(maxsize=1)
def _fallback_preset_store_v1():
    from .presets.runtime_store import DirectRuntimePresetStore

    return DirectRuntimePresetStore("winws1")


@lru_cache(maxsize=1)
def _fallback_direct_ui_snapshot_service():
    from .runtime.direct_ui_snapshot_service import DirectUiSnapshotService

    return DirectUiSnapshotService()


@lru_cache(maxsize=1)
def _fallback_orchestra_whitelist_runtime_service():
    from .runtime.orchestra_whitelist_runtime_service import OrchestraWhitelistRuntimeService

    return OrchestraWhitelistRuntimeService()


@lru_cache(maxsize=1)
def _fallback_program_settings_runtime_service():
    from .runtime.program_settings_runtime_service import ProgramSettingsRuntimeService

    return ProgramSettingsRuntimeService()


@lru_cache(maxsize=2)
def _fallback_user_presets_runtime_service(scope_key: str):
    from .runtime.user_presets_runtime_service import UserPresetsRuntimeService

    return UserPresetsRuntimeService(scope_key=scope_key)


def get_app_paths() -> AppPaths:
    context_value = _context_attr("app_paths")
    if isinstance(context_value, AppPaths):
        return context_value
    return _fallback_app_paths()


def get_preset_repository() -> PresetRepository:
    context_value = _context_attr("preset_repository")
    if isinstance(context_value, PresetRepository):
        return context_value
    return _fallback_preset_repository()


def get_selection_service() -> PresetSelectionService:
    context_value = _context_attr("preset_selection_service")
    if isinstance(context_value, PresetSelectionService):
        return context_value
    return _fallback_selection_service()


def get_direct_flow_coordinator() -> DirectFlowCoordinator:
    context_value = _context_attr("direct_flow_coordinator")
    if isinstance(context_value, DirectFlowCoordinator):
        return context_value
    return _fallback_direct_flow_coordinator()


def get_preset_store():
    return _fallback_preset_store()


def get_preset_store_v1():
    return _fallback_preset_store_v1()


def get_direct_ui_snapshot_service():
    context_value = _context_attr("direct_ui_snapshot_service")
    if context_value is not None:
        return context_value
    return _fallback_direct_ui_snapshot_service()


def get_orchestra_whitelist_runtime_service():
    return _fallback_orchestra_whitelist_runtime_service()


def get_program_settings_runtime_service():
    context_value = _context_attr("program_settings_runtime_service")
    if context_value is not None:
        return context_value
    return _fallback_program_settings_runtime_service()


def get_user_presets_runtime_service(scope_key: str):
    factory = _context_attr("user_presets_runtime_service_factory")
    if callable(factory):
        return factory(scope_key)
    return _fallback_user_presets_runtime_service(scope_key)


def reset_cached_services() -> None:
    install_app_context(None)
    _fallback_direct_flow_coordinator.cache_clear()
    _fallback_selection_service.cache_clear()
    _fallback_preset_repository.cache_clear()
    _fallback_app_paths.cache_clear()
    _fallback_preset_store.cache_clear()
    _fallback_preset_store_v1.cache_clear()
    _fallback_direct_ui_snapshot_service.cache_clear()
    _fallback_orchestra_whitelist_runtime_service.cache_clear()
    _fallback_program_settings_runtime_service.cache_clear()
    _fallback_user_presets_runtime_service.cache_clear()
