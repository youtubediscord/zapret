from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import zipfile

from core.paths import AppPaths

from .models import PresetManifest


_PRESET_HEADER_RE = re.compile(r"^\s*#\s*Preset:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_TEMPLATE_ORIGIN_RE = re.compile(r"^\s*#\s*TemplateOrigin:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_PRESET_KIND_RE = re.compile(r"^\s*#\s*PresetKind:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)


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


def _normalize_preset_file_name_candidate(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text if Path(text).suffix else f"{text}.txt"


class PresetFileStore:
    def __init__(self, paths: AppPaths):
        self._paths = paths
        self._manifest_cache: dict[str, tuple[tuple[object, ...], list[PresetManifest]]] = {}

    def list_manifests(self, engine: str) -> list[PresetManifest]:
        manifests = self._load_manifests(engine)
        return sorted(manifests, key=lambda item: (item.name.lower(), item.file_name.lower()))

    def get_manifest(self, engine: str, file_name: str) -> PresetManifest | None:
        target = self.resolve_file_name(engine, file_name).lower()
        if not target:
            return None
        for manifest in self._load_manifests(engine):
            if manifest.file_name.strip().lower() == target:
                return manifest
        return None

    def resolve_file_name(self, engine: str, file_name: str) -> str:
        candidate = str(file_name or "").strip()
        if not candidate:
            return ""

        normalized_candidate = _normalize_preset_file_name_candidate(candidate)
        engine_paths = self._engine_paths(engine)
        for presets_dir in (engine_paths.user_presets_dir, engine_paths.builtin_presets_dir):
            direct_path = presets_dir / normalized_candidate
            if direct_path.exists():
                return direct_path.name

            raw_path = presets_dir / candidate
            if raw_path.exists():
                return raw_path.name

        lowered_candidate = candidate.lower()
        lowered_normalized = normalized_candidate.lower()
        stem_candidate = Path(candidate).stem.strip().lower()

        for manifest in self._load_manifests(engine):
            manifest_name = str(manifest.file_name or "").strip()
            if not manifest_name:
                continue
            lowered_manifest = manifest_name.lower()
            if lowered_manifest in {lowered_candidate, lowered_normalized}:
                return manifest_name
            if stem_candidate and Path(manifest_name).stem.strip().lower() == stem_candidate:
                return manifest_name

        return normalized_candidate or candidate

    def read_source_text(self, engine: str, file_name: str) -> str:
        manifest = self.get_manifest(engine, file_name)
        if manifest is None:
            raise ValueError(f"Preset not found: {file_name}")
        return _read_text(self._manifest_path(engine, manifest))

    def get_source_path(self, engine: str, file_name: str) -> Path:
        manifest = self.get_manifest(engine, file_name)
        if manifest is None:
            raise ValueError(f"Preset not found: {file_name}")
        return self._manifest_path(engine, manifest)

    def create_preset(
        self,
        engine: str,
        name: str,
        source_text: str,
        *,
        kind: str = "user",
    ) -> PresetManifest:
        engine_paths = self._engine_paths(engine)
        normalized_name = str(name or "").strip()
        if not normalized_name:
            raise ValueError("Preset name is required")

        file_name = self._unique_file_name(
            (engine_paths.user_presets_dir, engine_paths.builtin_presets_dir),
            normalized_name,
        )
        display_name = self._extract_name(source_text, Path(file_name).stem)
        template_origin = self._extract_template_origin(source_text)
        updated_at = _now_iso()
        normalized_kind = self._infer_kind(
            engine,
            template_origin,
            current_kind=kind,
            storage_scope="user",
        )

        manifest = PresetManifest(
            file_name=file_name,
            name=display_name,
            template_origin=template_origin,
            updated_at=updated_at,
            kind=normalized_kind,
            storage_scope="user",
        )
        self._write_source(engine_paths.user_presets_dir / file_name, source_text)
        self._invalidate_manifest_cache(engine)
        return manifest

    def update_preset(
        self,
        engine: str,
        file_name: str,
        source_text: str,
        name: str | None,
    ) -> PresetManifest:
        _ = name
        manifests = self._load_manifests(engine)
        idx = self._find_index(manifests, file_name)
        current = manifests[idx]
        target_scope = "user"
        target_path = self._engine_paths(engine).user_presets_dir / current.file_name
        template_origin = self._extract_template_origin(source_text)

        updated = PresetManifest(
            file_name=current.file_name,
            name=self._extract_name(source_text, Path(current.file_name).stem),
            template_origin=template_origin,
            updated_at=_now_iso(),
            kind=self._infer_kind(
                engine,
                template_origin,
                current_kind=current.kind,
                storage_scope=target_scope,
            ),
            storage_scope=target_scope,
        )
        self._write_source(target_path, source_text)
        self._invalidate_manifest_cache(engine)
        return updated

    def rename_preset(self, engine: str, file_name: str, new_name: str) -> PresetManifest:
        manifests = self._load_manifests(engine)
        idx = self._find_index(manifests, file_name)
        current = manifests[idx]
        if str(current.storage_scope or "").strip().lower() != "user":
            raise ValueError(f"Built-in preset cannot be renamed: {current.name}")
        normalized_name = str(new_name or "").strip()
        if not normalized_name:
            raise ValueError("Preset name is required")

        engine_paths = self._engine_paths(engine)
        src_path = self._manifest_path(engine, current)
        target_file_name = self._unique_file_name(
            (engine_paths.user_presets_dir, engine_paths.builtin_presets_dir),
            normalized_name,
            exclude_file_name=current.file_name,
        )
        target_path = engine_paths.user_presets_dir / target_file_name
        if src_path.exists() and src_path != target_path:
            src_path.rename(target_path)

        source_text = _read_text(target_path) if target_path.exists() else ""
        template_origin = self._extract_template_origin(source_text)
        updated = PresetManifest(
            file_name=target_file_name,
            name=self._extract_name(source_text, Path(target_file_name).stem),
            template_origin=template_origin,
            updated_at=_now_iso(),
            kind=self._infer_kind(
                engine,
                template_origin,
                current_kind=current.kind,
                storage_scope="user",
            ),
            storage_scope="user",
        )
        self._invalidate_manifest_cache(engine)
        return updated

    def delete_preset(self, engine: str, file_name: str) -> None:
        manifests = self._load_manifests(engine)
        idx = self._find_index(manifests, file_name)
        manifest = manifests[idx]
        if str(manifest.storage_scope or "").strip().lower() != "user":
            raise ValueError(f"Built-in preset cannot be deleted: {manifest.name}")
        preset_path = self._manifest_path(engine, manifest)
        try:
            preset_path.unlink()
        except FileNotFoundError:
            pass
        self._invalidate_manifest_cache(engine)

    def export_preset(self, engine: str, file_name: str, dest_path: Path) -> None:
        manifest = self.get_manifest(engine, file_name)
        if manifest is None:
            raise ValueError(f"Preset not found: {file_name}")
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "file_name": manifest.file_name,
            "name": manifest.name,
            "template_origin": manifest.template_origin,
            "updated_at": manifest.updated_at,
            "kind": manifest.kind,
        }
        with zipfile.ZipFile(dest_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(payload, ensure_ascii=False, indent=2))
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

    def _load_manifests(self, engine: str) -> list[PresetManifest]:
        normalized_engine = str(engine or "").strip().lower()
        cache_key = self._current_manifest_cache_key(normalized_engine)
        cached_entry = self._manifest_cache.get(normalized_engine)
        if cache_key is not None and cached_entry is not None and cached_entry[0] == cache_key:
            return list(cached_entry[1])

        manifests = self._scan_manifests_from_files(engine)
        self._cache_manifests(normalized_engine, manifests)
        return manifests

    def _scan_manifests_from_files(self, engine: str) -> list[PresetManifest]:
        engine_paths = self._engine_paths(engine)
        manifests_by_file_name: dict[str, PresetManifest] = {}
        for storage_scope, presets_dir in (
            ("builtin", engine_paths.builtin_presets_dir),
            ("user", engine_paths.user_presets_dir),
        ):
            for preset_path in sorted(presets_dir.glob("*.txt"), key=lambda p: p.name.lower()):
                header_text = _read_header_text(preset_path)
                display_name = self._extract_name(header_text, preset_path.stem)
                template_origin = self._extract_template_origin(header_text)
                updated_at = self._file_time_to_iso(preset_path) or _now_iso()
                preset_kind = self._extract_preset_kind(header_text)
                kind = self._infer_kind(
                    engine,
                    template_origin,
                    current_kind=preset_kind,
                    storage_scope=storage_scope,
                )
                manifests_by_file_name[preset_path.name.lower()] = PresetManifest(
                    file_name=preset_path.name,
                    name=display_name,
                    template_origin=template_origin,
                    updated_at=updated_at,
                    kind=kind,
                    storage_scope=storage_scope,
                )
        return list(manifests_by_file_name.values())

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

    @staticmethod
    def _extract_preset_kind(source_text: str) -> str | None:
        match = _PRESET_KIND_RE.search(source_text or "")
        if not match:
            return None
        value = str(match.group(1) or "").strip().lower()
        return value or None

    @classmethod
    def _infer_kind(
        cls,
        engine: str,
        template_origin: str | None,
        *,
        current_kind: str | None = None,
        storage_scope: str,
    ) -> str:
        _ = engine
        _ = template_origin
        normalized_storage_scope = str(storage_scope or "").strip().lower()
        if normalized_storage_scope == "builtin":
            return "builtin"
        normalized_current_kind = str(current_kind or "").strip().lower()
        if normalized_current_kind == "imported":
            return "imported"
        return "user"

    def _cache_manifests(self, engine: str, manifests: list[PresetManifest]) -> None:
        cache_key = self._current_manifest_cache_key(engine)
        if cache_key is None:
            return
        self._manifest_cache[str(engine or "").strip().lower()] = (
            cache_key,
            list(manifests),
        )

    def _current_manifest_cache_key(self, engine: str) -> tuple[object, ...] | None:
        try:
            engine_paths = self._engine_paths(engine)
        except Exception:
            return None
        return (
            *self._path_signature(engine_paths.user_presets_dir),
            *self._path_signature(engine_paths.builtin_presets_dir),
        )

    def _invalidate_manifest_cache(self, engine: str) -> None:
        self._manifest_cache.pop(str(engine or "").strip().lower(), None)

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
    def _file_time_to_iso(path: Path) -> str:
        try:
            value = float(path.stat().st_mtime)
        except Exception:
            value = 0.0
        if value <= 0:
            return ""
        return datetime.fromtimestamp(value, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _write_source(path: Path, source_text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = (source_text or "").replace("\r\n", "\n").replace("\r", "\n")
        if not text.endswith("\n"):
            text += "\n"
        path.write_text(text, encoding="utf-8", newline="\n")

    def _manifest_path(self, engine: str, manifest: PresetManifest) -> Path:
        engine_paths = self._engine_paths(engine)
        if str(manifest.storage_scope or "").strip().lower() == "builtin":
            return engine_paths.builtin_presets_dir / manifest.file_name
        return engine_paths.user_presets_dir / manifest.file_name

    @staticmethod
    def _unique_file_name(
        presets_dirs: tuple[Path, ...],
        name: str,
        *,
        exclude_file_name: str | None = None,
    ) -> str:
        base = _sanitize_file_stem(name)
        candidate = f"{base}.txt"
        counter = 2
        excluded = (exclude_file_name or "").strip().lower()
        while any((presets_dir / candidate).exists() for presets_dir in presets_dirs) and candidate.lower() != excluded:
            candidate = f"{base} ({counter}).txt"
            counter += 1
        return candidate
