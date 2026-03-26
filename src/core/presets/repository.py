from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Iterable
from uuid import uuid4
import zipfile

from core.paths import AppPaths

from .models import PresetDocument, PresetManifest

_PRESET_HEADER_RE = re.compile(r"^\s*#\s*Preset:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_preset_id() -> str:
    try:
        from uuid import uuid7  # type: ignore[attr-defined]

        return str(uuid7())
    except Exception:
        return str(uuid4())


def _sanitize_file_stem(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "Preset"
    sanitized = re.sub(r'[\\/:*?"<>|\x00]+', "_", text)
    sanitized = re.sub(r"\s+", " ", sanitized).strip().rstrip(".")
    return sanitized[:100] or "Preset"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


class PresetRepository:
    def __init__(self, paths: AppPaths):
        self._paths = paths

    def list_presets(self, engine: str) -> list[PresetDocument]:
        manifests = self._load_index(engine)
        docs = [self._load_document(engine, manifest) for manifest in manifests]
        return sorted(docs, key=lambda item: item.manifest.name.lower())

    def get_preset(self, engine: str, preset_id: str) -> PresetDocument | None:
        for manifest in self._load_index(engine):
            if manifest.id == preset_id:
                return self._load_document(engine, manifest)
        return None

    def find_preset_by_name(self, engine: str, name: str) -> PresetDocument | None:
        target = str(name or "").strip().lower()
        if not target:
            return None
        for manifest in self._load_index(engine):
            if manifest.name.strip().lower() == target:
                return self._load_document(engine, manifest)
        return None

    def create_preset(self, engine: str, name: str, source_text: str) -> PresetDocument:
        engine_paths = self._engine_paths(engine)
        manifests = self._load_index(engine)
        normalized_name = self._validate_new_name(manifests, name)
        created_at = _now_iso()
        preset_id = self._unique_id(manifests)
        file_name = self._unique_file_name(engine_paths.presets_dir, normalized_name)
        manifest = PresetManifest(
            id=preset_id,
            name=normalized_name,
            file_name=file_name,
            created_at=created_at,
            updated_at=created_at,
        )
        self._write_source(engine_paths.presets_dir / file_name, source_text)
        manifests.append(manifest)
        self._save_index(engine, manifests)
        return self._load_document(engine, manifest)

    def update_preset(
        self,
        engine: str,
        preset_id: str,
        source_text: str,
        name: str | None,
    ) -> PresetDocument:
        manifests = self._load_index(engine)
        idx = self._find_index(manifests, preset_id)
        current = manifests[idx]
        next_name = current.name if name is None else self._validate_new_name(manifests, name, exclude_id=preset_id)
        updated = PresetManifest(
            id=current.id,
            name=next_name,
            file_name=current.file_name,
            created_at=current.created_at,
            updated_at=_now_iso(),
            kind=current.kind,
        )
        manifests[idx] = updated
        self._write_source(self._engine_paths(engine).presets_dir / updated.file_name, source_text)
        self._save_index(engine, manifests)
        return self._load_document(engine, updated)

    def rename_preset(self, engine: str, preset_id: str, new_name: str) -> PresetDocument:
        manifests = self._load_index(engine)
        idx = self._find_index(manifests, preset_id)
        current = manifests[idx]
        normalized_name = self._validate_new_name(manifests, new_name, exclude_id=preset_id)
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
        updated = PresetManifest(
            id=current.id,
            name=normalized_name,
            file_name=target_file_name,
            created_at=current.created_at,
            updated_at=_now_iso(),
            kind=current.kind,
        )
        manifests[idx] = updated
        self._save_index(engine, manifests)
        return self._load_document(engine, updated)

    def delete_preset(self, engine: str, preset_id: str) -> None:
        manifests = self._load_index(engine)
        idx = self._find_index(manifests, preset_id)
        manifest = manifests.pop(idx)
        preset_path = self._engine_paths(engine).presets_dir / manifest.file_name
        try:
            preset_path.unlink()
        except FileNotFoundError:
            pass
        self._save_index(engine, manifests)

    def export_preset(self, engine: str, preset_id: str, dest_path: Path) -> None:
        preset = self.get_preset(engine, preset_id)
        if preset is None:
            raise ValueError(f"Preset not found: {preset_id}")
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dest_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(asdict(preset.manifest), ensure_ascii=False, indent=2))
            zf.writestr("preset.txt", preset.source_text)

    def import_preset(self, engine: str, src_path: Path) -> PresetDocument:
        src_path = Path(src_path)
        with zipfile.ZipFile(src_path, "r") as zf:
            manifest_data = json.loads(zf.read("manifest.json").decode("utf-8"))
            source_text = zf.read("preset.txt").decode("utf-8")

        requested_name = str(manifest_data.get("name") or "Imported").strip() or "Imported"
        unique_name = self._unique_name(engine, requested_name)
        return self.create_preset(engine, unique_name, source_text)

    def _engine_paths(self, engine: str):
        return self._paths.engine_paths(engine).ensure_directories()

    def _index_path(self, engine: str) -> Path:
        return self._engine_paths(engine).index_path

    def _load_index(self, engine: str) -> list[PresetManifest]:
        self._bootstrap_index(engine)
        path = self._index_path(engine)
        if not path.exists():
            return []
        data = json.loads(_read_text(path) or "[]")
        manifests = [PresetManifest(**item) for item in data]
        return manifests

    def _bootstrap_index(self, engine: str) -> None:
        engine_paths = self._engine_paths(engine)
        path = engine_paths.index_path
        existing_data: list[dict[str, str]] = []
        if path.exists():
            try:
                existing_data = json.loads(_read_text(path) or "[]")
            except Exception:
                existing_data = []

        manifests_by_file = {}
        used_ids: set[str] = set()
        for raw in existing_data:
            file_name = str(raw.get("file_name") or "").strip()
            if not file_name:
                continue
            preset_id = str(raw.get("id") or "").strip() or _new_preset_id()
            while preset_id in used_ids:
                preset_id = _new_preset_id()
            used_ids.add(preset_id)
            manifests_by_file[file_name.lower()] = PresetManifest(
                id=preset_id,
                name=str(raw.get("name") or "").strip() or Path(file_name).stem,
                file_name=file_name,
                created_at=str(raw.get("created_at") or _now_iso()),
                updated_at=str(raw.get("updated_at") or raw.get("created_at") or _now_iso()),
                kind=str(raw.get("kind") or "user"),
            )

        manifests: list[PresetManifest] = []
        used_names: set[str] = set()
        for preset_path in sorted(engine_paths.presets_dir.glob("*.txt"), key=lambda p: p.name.lower()):
            current = manifests_by_file.get(preset_path.name.lower())
            source_text = _read_text(preset_path)
            extracted_name = self._extract_name(source_text, preset_path.stem)
            display_name = extracted_name
            if current is not None:
                display_name = current.name or extracted_name
            display_name = self._dedupe_name(display_name, used_names)

            manifests.append(
                PresetManifest(
                    id=current.id if current is not None else self._unique_id(manifests),
                    name=display_name,
                    file_name=preset_path.name,
                    created_at=current.created_at if current is not None else _now_iso(),
                    updated_at=_now_iso(),
                    kind=current.kind if current is not None else "user",
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

    def _load_document(self, engine: str, manifest: PresetManifest) -> PresetDocument:
        path = self._engine_paths(engine).presets_dir / manifest.file_name
        return PresetDocument(manifest=manifest, source_text=_read_text(path))

    def _save_index(self, engine: str, manifests: Iterable[PresetManifest]) -> None:
        path = self._index_path(engine)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(item) for item in manifests]
        self._atomic_write_json(path, payload)

    def _find_index(self, manifests: list[PresetManifest], preset_id: str) -> int:
        for idx, manifest in enumerate(manifests):
            if manifest.id == preset_id:
                return idx
        raise ValueError(f"Preset not found: {preset_id}")

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

    def _validate_new_name(
        self,
        manifests: list[PresetManifest],
        name: str,
        *,
        exclude_id: str | None = None,
    ) -> str:
        normalized_name = str(name or "").strip()
        if not normalized_name:
            raise ValueError("Preset name is required")
        lowered = normalized_name.lower()
        for manifest in manifests:
            if exclude_id is not None and manifest.id == exclude_id:
                continue
            if manifest.name.lower() == lowered:
                raise ValueError(f"Preset name already exists: {normalized_name}")
        return normalized_name

    def _unique_id(self, manifests: list[PresetManifest]) -> str:
        used = {item.id for item in manifests}
        preset_id = _new_preset_id()
        while preset_id in used:
            preset_id = _new_preset_id()
        return preset_id

    @staticmethod
    def _dedupe_name(name: str, used_names: set[str]) -> str:
        base = str(name or "").strip() or "Preset"
        candidate = base
        counter = 2
        while candidate.lower() in used_names:
            candidate = f"{base} ({counter})"
            counter += 1
        used_names.add(candidate.lower())
        return candidate

    def _unique_name(self, engine: str, name: str) -> str:
        used_names = {item.manifest.name.lower() for item in self.list_presets(engine)}
        return self._dedupe_name(name, used_names)

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
