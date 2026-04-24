from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Callable, Generic, TypeVar

from PyQt6.QtCore import QThread, pyqtSignal
from log.log import log

from direct_preset.service import BasicUiPayload, TargetDetailPayload
from core.presets.cache_signatures import path_cache_signature
from direct_preset.facade import DirectPresetFacade
from direct_preset.modes import (
    DIRECT_UI_MODE_DEFAULT,
    load_current_direct_ui_mode,
    normalize_direct_ui_mode_for_engine,
)


SnapshotT = TypeVar("SnapshotT")


@dataclass(frozen=True, slots=True)
class DirectBasicUiSnapshot:
    revision: tuple[object, ...]
    payload: BasicUiPayload
    empty_state: dict[str, str] | None = None


@dataclass(frozen=True, slots=True)
class DirectTargetDetailSnapshot:
    revision: tuple[object, ...]
    target_key: str
    payload: TargetDetailPayload | None


@dataclass(frozen=True, slots=True)
class DirectDictSnapshot:
    revision: tuple[object, ...]
    payload: dict


class _SnapshotCache(Generic[SnapshotT]):
    def __init__(self) -> None:
        self.revision: tuple[object, ...] | None = None
        self.value: SnapshotT | None = None

    def matches(self, revision: tuple[object, ...]) -> bool:
        return self.value is not None and self.revision == revision

    def get(self) -> SnapshotT | None:
        return self.value

    def store(self, revision: tuple[object, ...], value: SnapshotT) -> SnapshotT:
        self.revision = revision
        self.value = value
        return value


class DirectBasicUiSnapshotWorker(QThread):
    loaded = pyqtSignal(int, object)

    def __init__(
        self,
        request_id: int,
        *,
        snapshot_service: "DirectUiSnapshotService",
        launch_method: str,
        direct_mode_override: str | None = None,
        refresh: bool = False,
        startup_scope: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._request_id = int(request_id)
        self._snapshot_service = snapshot_service
        self._launch_method = str(launch_method or "").strip().lower()
        self._direct_mode_override = str(direct_mode_override or "").strip().lower() or None
        self._refresh = bool(refresh)
        self._startup_scope = startup_scope

    def run(self) -> None:
        snapshot = self._snapshot_service.get_basic_ui_snapshot(
            self._launch_method,
            direct_mode_override=self._direct_mode_override,
            refresh=self._refresh,
            startup_scope=self._startup_scope,
        )
        self.loaded.emit(self._request_id, snapshot)


class DirectTargetDetailSnapshotWorker(QThread):
    loaded = pyqtSignal(int, object)

    def __init__(
        self,
        request_id: int,
        *,
        snapshot_service: "DirectUiSnapshotService",
        launch_method: str,
        target_key: str,
        direct_mode_override: str | None = None,
        refresh: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._request_id = int(request_id)
        self._snapshot_service = snapshot_service
        self._launch_method = str(launch_method or "").strip().lower()
        self._target_key = str(target_key or "").strip().lower()
        self._direct_mode_override = str(direct_mode_override or "").strip().lower() or None
        self._refresh = bool(refresh)

    def run(self) -> None:
        snapshot = self._snapshot_service.get_target_detail_snapshot(
            self._launch_method,
            self._target_key,
            direct_mode_override=self._direct_mode_override,
            refresh=self._refresh,
        )
        self.loaded.emit(self._request_id, snapshot)


class DirectUiSnapshotService:
    """Service-owned snapshot cache for direct pages.

    Страницы не должны хранить канонические payload-кэши у себя. Этот сервис
    держит готовые снимки данных и умеет определять их ревизию по реальному
    source preset и текущему режиму direct UI.
    """

    def __init__(self, facade_factory: Callable[[str, str | None], DirectPresetFacade]) -> None:
        self._facade_factory = facade_factory
        self._lock = RLock()
        self._basic_payload_cache: dict[tuple[str, str], _SnapshotCache[DirectBasicUiSnapshot]] = {}
        self._target_detail_cache: dict[tuple[str, str, str], _SnapshotCache[TargetDetailPayload | None]] = {}
        self._advanced_settings_cache: dict[str, _SnapshotCache[dict]] = {}

    @staticmethod
    def _empty_basic_payload() -> BasicUiPayload:
        return BasicUiPayload(
            target_views=(),
            target_items={},
            strategy_selections={},
            strategy_names_by_target={},
            filter_modes={},
            selected_preset_file_name="",
            selected_preset_name="",
        )

    @staticmethod
    def _normalize_launch_method(launch_method: str) -> str:
        return str(launch_method or "").strip().lower()

    def _facade(self, launch_method: str, *, direct_mode_override: str | None = None) -> DirectPresetFacade:
        return self._facade_factory(
            self._normalize_launch_method(launch_method),
            str(direct_mode_override or "").strip().lower() or None,
        )

    def _resolve_selected_source_revision(self, launch_method: str) -> tuple[object, ...]:
        method = self._normalize_launch_method(launch_method)
        try:
            facade = self._facade(method)
            manifest = facade.get_selected_manifest()
        except Exception:
            manifest = None

        file_name = str(getattr(manifest, "file_name", "") or "").strip().lower()
        display_name = str(getattr(manifest, "name", "") or "").strip()
        if not file_name:
            return (method, "no-selected-preset")

        try:
            path = facade.get_source_path_by_file_name(file_name)
        except Exception:
            path = None

        if isinstance(path, Path):
            return (method, file_name, display_name, *path_cache_signature(path))
        return (method, file_name, display_name, "signature-unavailable")

    @staticmethod
    def _resolve_z2_direct_mode(direct_mode_override: str | None = None) -> str:
        if direct_mode_override is not None:
            return normalize_direct_ui_mode_for_engine("winws2", direct_mode_override)
        resolved = load_current_direct_ui_mode("winws2")
        return resolved or DIRECT_UI_MODE_DEFAULT

    def _resolve_basic_ui_revision(
        self,
        launch_method: str,
        *,
        direct_mode_override: str | None = None,
    ) -> tuple[object, ...]:
        method = self._normalize_launch_method(launch_method)
        if method == "direct_zapret2":
            return (
                *self._resolve_selected_source_revision(method),
                self._resolve_z2_direct_mode(direct_mode_override),
            )
        return self._resolve_selected_source_revision(method)

    def _resolve_target_detail_revision(
        self,
        launch_method: str,
        target_key: str,
        *,
        direct_mode_override: str | None = None,
    ) -> tuple[object, ...]:
        return (
            *self._resolve_basic_ui_revision(
                launch_method,
                direct_mode_override=direct_mode_override,
            ),
            str(target_key or "").strip().lower(),
        )

    def get_basic_ui_snapshot(
        self,
        launch_method: str,
        *,
        direct_mode_override: str | None = None,
        refresh: bool = False,
        startup_scope: str | None = None,
    ) -> DirectBasicUiSnapshot:
        method = self._normalize_launch_method(launch_method)
        normalized_mode = str(direct_mode_override or "").strip().lower() or None
        revision = self._resolve_basic_ui_revision(
            method,
            direct_mode_override=normalized_mode,
        )
        cache_key = (method, normalized_mode or "")

        with self._lock:
            cache = self._basic_payload_cache.setdefault(cache_key, _SnapshotCache())
            if not refresh and cache.matches(revision):
                return cache.get() or DirectBasicUiSnapshot(
                    revision=revision,
                    payload=self._empty_basic_payload(),
                    empty_state=None,
                )

        payload = self._empty_basic_payload()
        empty_state: dict[str, str] | None = None
        facade = None
        try:
            facade = self._facade(
                method,
                direct_mode_override=normalized_mode,
            )
        except Exception as exc:
            log(
                f"DirectUiSnapshotService[{method}]: failed to create facade for basic UI snapshot: {exc}",
                "ERROR",
            )

        if facade is not None:
            try:
                payload = facade.get_basic_ui_payload(startup_scope=startup_scope)
            except Exception as exc:
                log(
                    f"DirectUiSnapshotService[{method}]: failed to build basic UI payload: {exc}",
                    "ERROR",
                )
                payload = self._empty_basic_payload()

            try:
                empty_state = facade.get_basic_ui_empty_state()
            except Exception as exc:
                log(
                    f"DirectUiSnapshotService[{method}]: failed to resolve basic UI empty-state: {exc}",
                    "ERROR",
                )

        if empty_state is None and not (payload.target_items or {}):
            empty_state = {
                "reason": "unknown_error",
                "preset_name": str(getattr(payload, "selected_preset_name", "") or ""),
                "preset_file_name": str(getattr(payload, "selected_preset_file_name", "") or ""),
            }

        snapshot = DirectBasicUiSnapshot(
            revision=revision,
            payload=payload,
            empty_state=empty_state,
        )

        with self._lock:
            self._basic_payload_cache.setdefault(cache_key, _SnapshotCache()).store(revision, snapshot)
        return snapshot

    def get_target_detail_snapshot(
        self,
        launch_method: str,
        target_key: str,
        *,
        direct_mode_override: str | None = None,
        refresh: bool = False,
    ) -> DirectTargetDetailSnapshot:
        method = self._normalize_launch_method(launch_method)
        normalized_key = str(target_key or "").strip().lower()
        normalized_mode = str(direct_mode_override or "").strip().lower() or None
        revision = self._resolve_target_detail_revision(
            method,
            normalized_key,
            direct_mode_override=normalized_mode,
        )
        cache_key = (method, normalized_key, normalized_mode or "")

        with self._lock:
            cache = self._target_detail_cache.setdefault(cache_key, _SnapshotCache())
            if not refresh and cache.matches(revision):
                return DirectTargetDetailSnapshot(revision=revision, target_key=normalized_key, payload=cache.get())

        try:
            payload = self._facade(
                method,
                direct_mode_override=normalized_mode,
            ).get_target_detail_payload(normalized_key)
        except Exception as exc:
            log(
                f"DirectUiSnapshotService[{method}]: failed to build target detail payload "
                f"for '{normalized_key}': {exc}",
                "ERROR",
            )
            payload = None

        with self._lock:
            cache.store(revision, payload)
        return DirectTargetDetailSnapshot(revision=revision, target_key=normalized_key, payload=payload)

    def get_advanced_settings_snapshot(self, launch_method: str, *, refresh: bool = False) -> DirectDictSnapshot:
        method = self._normalize_launch_method(launch_method)
        revision = self._resolve_selected_source_revision(method)

        with self._lock:
            cache = self._advanced_settings_cache.setdefault(method, _SnapshotCache())
            if not refresh and cache.matches(revision):
                return DirectDictSnapshot(revision=revision, payload=dict(cache.get() or {}))

        try:
            payload = self._facade(method).get_advanced_settings_state() or {}
        except Exception:
            payload = {}

        normalized = dict(payload)
        with self._lock:
            cache.store(revision, normalized)
        return DirectDictSnapshot(revision=revision, payload=normalized)

    def load_basic_ui_payload(
        self,
        launch_method: str,
        *,
        direct_mode_override: str | None = None,
        refresh: bool = False,
        startup_scope: str | None = None,
    ) -> BasicUiPayload:
        return self.get_basic_ui_snapshot(
            launch_method,
            direct_mode_override=direct_mode_override,
            refresh=refresh,
            startup_scope=startup_scope,
        ).payload

    def load_target_detail_payload(
        self,
        launch_method: str,
        target_key: str,
        *,
        direct_mode_override: str | None = None,
        refresh: bool = False,
    ) -> TargetDetailPayload | None:
        return self.get_target_detail_snapshot(
            launch_method,
            target_key,
            direct_mode_override=direct_mode_override,
            refresh=refresh,
        ).payload

    def load_advanced_settings_state(self, launch_method: str, *, refresh: bool = False) -> dict:
        return dict(self.get_advanced_settings_snapshot(launch_method, refresh=refresh).payload)

    def get_basic_ui_empty_state(self, launch_method: str) -> dict[str, str] | None:
        try:
            return self._facade(launch_method).get_basic_ui_empty_state()
        except Exception:
            return None
