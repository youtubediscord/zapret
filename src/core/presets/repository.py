from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Iterable
import zipfile

from core.paths import AppPaths
from .v1_builtin_templates import is_builtin_preset_file_name_v1
from .z2_builtin_templates import is_builtin_preset_file_name_v2

from .models import PresetManifest

_PRESET_HEADER_RE = re.compile(r"^\s*#\s*Preset:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_TEMPLATE_ORIGIN_RE = re.compile(r"^\s*#\s*TemplateOrigin:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sanitize_file_stem(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "Preset"
    sanitized = re.sub(r'[\\/:*?"<>|\x00]+', "_", text)
    sanitized = re.sub(r"\s+", " ", sanitized).strip().rstrip(".")
    return sanitized[:100] or "Preset"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _read_header_text(path: Path) -> str:
    lines: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            stripped = raw.strip()
            if stripped and not stripped.startswith("#"):
                break
            lines.append(raw.rstrip("\n"))
    return "\n".join(lines)


class PresetRepository:
    def __init__(self, paths: AppPaths):
        self._paths = paths
        self._index_cache: dict[str, tuple[tuple[object, ...], list[PresetManifest]]] = {}
        self._prepared_runtime_engines: set[str] = set()

    def list_manifests(self, engine: str) -> list[PresetManifest]:
        manifests = self._load_index(engine)
        return sorted(manifests, key=lambda item: (item.name.lower(), item.file_name.lower()))

    def get_manifest(self, engine: str, file_name: str) -> PresetManifest | None:
        target = str(file_name or "").strip().lower()
        if not target:
            return None
        for manifest in self._load_index(engine):
            if manifest.file_name.strip().lower() == target:
                return manifest
        return None

    def read_source_text(self, engine: str, file_name: str) -> str:
        manifest = self.get_manifest(engine, file_name)
        if manifest is None:
            raise ValueError(f"Preset not found: {file_name}")
        path = self._engine_paths(engine).presets_dir / manifest.file_name
        return _read_text(path)

    def create_preset(
        self,
        engine: str,
        name: str,
        source_text: str,
        *,
        kind: str = "user",
    ) -> PresetManifest:
        engine_paths = self._engine_paths(engine)
        manifests = self._load_index(engine)
        normalized_name = str(name or "").strip()
        if not normalized_name:
            raise ValueError("Preset name is required")
        created_at = _now_iso()
        file_name = self._unique_file_name(engine_paths.presets_dir, normalized_name)
        normalized_kind = str(kind or "user").strip() or "user"
        display_name = self._extract_name(source_text, Path(file_name).stem)
        template_origin = self._extract_template_origin(source_text)
        manifest = PresetManifest(
            file_name=file_name,
            name=display_name,
            template_origin=template_origin,
            created_at=created_at,
            updated_at=created_at,
            kind=normalized_kind,
        )
        self._write_source(engine_paths.presets_dir / file_name, source_text)
        manifests.append(manifest)
        self._save_index(engine, manifests)
        return manifest

    def update_preset(
        self,
        engine: str,
        file_name: str,
        source_text: str,
        name: str | None,
    ) -> PresetManifest:
        _ = name
        manifests = self._load_index(engine)
        idx = self._find_index(manifests, file_name)
        current = manifests[idx]
        next_name = self._extract_name(source_text, Path(current.file_name).stem)
        next_template_origin = self._extract_template_origin(source_text)
        updated = PresetManifest(
            file_name=current.file_name,
            name=next_name,
            template_origin=next_template_origin,
            created_at=current.created_at,
            updated_at=_now_iso(),
            kind=current.kind,
        )
        manifests[idx] = updated
        self._write_source(self._engine_paths(engine).presets_dir / updated.file_name, source_text)
        self._save_index(engine, manifests)
        return updated

    def rename_preset(self, engine: str, file_name: str, new_name: str) -> PresetManifest:
        manifests = self._load_index(engine)
        idx = self._find_index(manifests, file_name)
        current = manifests[idx]
        normalized_name = str(new_name or "").strip()
        if not normalized_name:
            raise ValueError("Preset name is required")
        engine_paths = self._engine_paths(engine)
        src_path = engine_paths.presets_dir / current.file_name
        target_file_name = self._unique_file_name(
            engine_paths.presets_dir,
            normalized_name,
            exclude_file_name=current.file_name,
        )
        target_path = engine_paths.presets_dir / target_file_name
        if src_path.exists() and src_path != target_path:
            src_path.rename(target_path)
        source_text = _read_text(target_path) if target_path.exists() else ""
        updated = PresetManifest(
            file_name=target_file_name,
            name=self._extract_name(source_text, Path(target_file_name).stem),
            template_origin=self._extract_template_origin(source_text),
            created_at=current.created_at,
            updated_at=_now_iso(),
            kind=current.kind,
        )
        manifests[idx] = updated
        self._save_index(engine, manifests)
        return updated

    def delete_preset(self, engine: str, file_name: str) -> None:
        manifests = self._load_index(engine)
        idx = self._find_index(manifests, file_name)
        manifest = manifests.pop(idx)
        preset_path = self._engine_paths(engine).presets_dir / manifest.file_name
        try:
            preset_path.unlink()
        except FileNotFoundError:
            pass
        self._save_index(engine, manifests)

    def export_preset(self, engine: str, file_name: str, dest_path: Path) -> None:
        manifest = self.get_manifest(engine, file_name)
        if manifest is None:
            raise ValueError(f"Preset not found: {file_name}")
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dest_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(asdict(manifest), ensure_ascii=False, indent=2))
            zf.writestr("preset.txt", self.read_source_text(engine, manifest.file_name))

    def import_preset(self, engine: str, src_path: Path) -> PresetManifest:
        src_path = Path(src_path)
        with zipfile.ZipFile(src_path, "r") as zf:
            manifest_data = json.loads(zf.read("manifest.json").decode("utf-8"))
            source_text = zf.read("preset.txt").decode("utf-8")

        requested_file_stem = Path(str(manifest_data.get("file_name") or "").strip()).stem
        requested_name = requested_file_stem or str(manifest_data.get("name") or "Imported").strip() or "Imported"
        return self.create_preset(engine, requested_name, source_text, kind="imported")

    def _engine_paths(self, engine: str):
        return self._paths.engine_paths(engine).ensure_directories()

    def _index_path(self, engine: str) -> Path:
        return self._engine_paths(engine).index_path

    def _load_index(self, engine: str) -> list[PresetManifest]:
        normalized_engine = str(engine or "").strip().lower()
        self._ensure_runtime_support_ready(normalized_engine)
        cache_key = self._current_index_cache_key(normalized_engine)
        cached_entry = self._index_cache.get(normalized_engine)
        if cache_key is not None and cached_entry is not None and cached_entry[0] == cache_key:
            return list(cached_entry[1])

        self._bootstrap_index(engine)
        path = self._index_path(engine)
        if not path.exists():
            return []
        data = json.loads(_read_text(path) or "[]")
        manifests = [self._manifest_from_raw(item) for item in data if isinstance(item, dict)]
        self._cache_index(normalized_engine, manifests)
        return manifests

    def _ensure_runtime_support_ready(self, engine: str) -> None:
        normalized_engine = str(engine or "").strip().lower()
        if normalized_engine in self._prepared_runtime_engines:
            return

        launch_method = ""
        if normalized_engine == "winws1":
            launch_method = "direct_zapret1"
        elif normalized_engine == "winws2":
            launch_method = "direct_zapret2"

        if not launch_method:
            self._prepared_runtime_engines.add(normalized_engine)
            return

        from .support_files import prepare_direct_support_files

        prepare_direct_support_files(launch_method)
        self._prepared_runtime_engines.add(normalized_engine)

    def _bootstrap_index(self, engine: str) -> None:
        engine_paths = self._engine_paths(engine)
        path = engine_paths.index_path
        existing_data: list[dict[str, str]] = []
        if path.exists():
            try:
                raw_text = _read_text(path) or "[]"
            except OSError as exc:
                raise RuntimeError(f"Failed to read preset index: {path}") from exc

            try:
                existing_data = json.loads(raw_text)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Invalid preset index JSON: {path}") from exc

        manifests_by_file: dict[str, PresetManifest] = {}
        for raw in existing_data:
            manifest = self._manifest_from_raw(raw)
            if not manifest.file_name:
                continue
            manifests_by_file[manifest.file_name.lower()] = manifest

        manifests: list[PresetManifest] = []
        for preset_path in sorted(engine_paths.presets_dir.glob("*.txt"), key=lambda p: p.name.lower()):
            current = manifests_by_file.get(preset_path.name.lower())
            header_text = _read_header_text(preset_path)
            display_name = self._extract_name(header_text, preset_path.stem)
            template_origin = self._extract_template_origin(header_text)
            created_at = current.created_at if current is not None else _now_iso()
            updated_at = current.updated_at if current is not None else created_at
            kind = self._infer_kind(
                engine,
                preset_path.name,
                template_origin,
                current.kind if current is not None else None,
            )
            manifests.append(
                PresetManifest(
                    file_name=preset_path.name,
                    name=display_name,
                    template_origin=template_origin,
                    created_at=created_at,
                    updated_at=updated_at,
                    kind=kind,
                )
            )

        self._save_index(engine, manifests)

    @staticmethod
    def _extract_name(source_text: str, fallback: str) -> str:
        match = _PRESET_HEADER_RE.search(source_text or "")
        if match:
            value = match.group(1).strip()
            if value:
                return value
        return str(fallback or "Preset").strip() or "Preset"

    @staticmethod
    def _extract_template_origin(source_text: str) -> str | None:
        match = _TEMPLATE_ORIGIN_RE.search(source_text or "")
        if not match:
            return None
        value = str(match.group(1) or "").strip()
        return value or None

    @classmethod
    def _infer_kind(
        cls,
        engine: str,
        file_name: str,
        template_origin: str | None,
        current_kind: str | None = None,
    ) -> str:
        normalized_current_kind = str(current_kind or "").strip().lower()
        if normalized_current_kind == "imported":
            return "imported"
        engine_key = str(engine or "").strip().lower()
        if engine_key == "winws2":
            return "builtin" if is_builtin_preset_file_name_v2(file_name) else "user"
        if engine_key == "winws1":
            return "builtin" if is_builtin_preset_file_name_v1(file_name) else "user"
        return "user"

    def _save_index(self, engine: str, manifests: Iterable[PresetManifest]) -> None:
        normalized_engine = str(engine or "").strip().lower()
        path = self._index_path(engine)
        path.parent.mkdir(parents=True, exist_ok=True)
        manifest_list = list(manifests)
        payload = [asdict(item) for item in manifest_list]
        self._atomic_write_json(path, payload)
        self._cache_index(normalized_engine, manifest_list)

    def _cache_index(self, engine: str, manifests: Iterable[PresetManifest]) -> None:
        cache_key = self._current_index_cache_key(engine)
        if cache_key is None:
            return
        self._index_cache[str(engine or "").strip().lower()] = (
            cache_key,
            list(manifests),
        )

    def _current_index_cache_key(self, engine: str) -> tuple[object, ...] | None:
        try:
            engine_paths = self._engine_paths(engine)
        except Exception:
            return None
        return (
            *self._path_signature(engine_paths.index_path),
            *self._path_signature(engine_paths.presets_dir),
        )

    @staticmethod
    def _path_signature(path: Path) -> tuple[object, ...]:
        try:
            stat = path.stat()
            return (
                True,
                int(getattr(stat, "st_mtime_ns", 0) or 0),
                int(getattr(stat, "st_size", 0) or 0),
            )
        except Exception:
            return (False, 0, 0)

    def _find_index(self, manifests: list[PresetManifest], file_name: str) -> int:
        target = str(file_name or "").strip().lower()
        for idx, manifest in enumerate(manifests):
            if manifest.file_name.strip().lower() == target:
                return idx
        raise ValueError(f"Preset not found: {file_name}")

    @staticmethod
    def _manifest_from_raw(raw: dict) -> PresetManifest:
        file_name = str(raw.get("file_name") or "").strip()
        display_name = str(raw.get("name") or "").strip() or Path(file_name).stem or "Preset"
        created_at = str(raw.get("created_at") or _now_iso())
        updated_at = str(raw.get("updated_at") or raw.get("created_at") or created_at)
        kind = str(raw.get("kind") or "user").strip() or "user"
        return PresetManifest(
            file_name=file_name,
            name=display_name,
            template_origin=str(raw.get("template_origin") or "").strip() or None,
            created_at=created_at,
            updated_at=updated_at,
            kind=kind,
        )

    @staticmethod
    def _atomic_write_json(path: Path, payload) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f"{path.stem}_", suffix=".tmp", dir=str(path.parent))
        try:
            text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except Exception:
                    pass
            Path(tmp_name).replace(path)
        finally:
            try:
                Path(tmp_name).unlink()
            except FileNotFoundError:
                pass

    @staticmethod
    def _write_source(path: Path, source_text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = (source_text or "").replace("\r\n", "\n").replace("\r", "\n")
        if not text.endswith("\n"):
            text += "\n"
        fd, tmp_name = tempfile.mkstemp(prefix=f"{path.stem}_", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except Exception:
                    pass
            Path(tmp_name).replace(path)
        finally:
            try:
                Path(tmp_name).unlink()
            except FileNotFoundError:
                pass

    @staticmethod
    def _unique_file_name(
        presets_dir: Path,
        name: str,
        *,
        exclude_file_name: str | None = None,
    ) -> str:
        base = _sanitize_file_stem(name)
        candidate = f"{base}.txt"
        counter = 2
        excluded = (exclude_file_name or "").strip().lower()
        while (presets_dir / candidate).exists() and candidate.lower() != excluded:
            candidate = f"{base} ({counter}).txt"
            counter += 1
        return candidate
