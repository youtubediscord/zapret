from __future__ import annotations

from pathlib import Path

from core.presets.template_support import (
    resolve_reset_template as _template_support_resolve_reset_template,
    reset_all_templates as _template_support_reset_all_templates,
)
from presets.preset_text_ops import (
    _header_preset_kind,
    _rewrite_preset_headers,
)


def _resolve_reset_template(launch_method: str, preset_name: str) -> str:
    return _template_support_resolve_reset_template(launch_method, preset_name)


def rename_by_file_name(backend, file_name: str, new_name: str):
    manifest = backend.get_manifest_by_file_name(file_name)
    if manifest is None:
        raise ValueError(f"Preset not found: {file_name}")
    if str(manifest.kind or "").strip().lower() == "builtin":
        raise ValueError(f"Built-in preset cannot be renamed: {manifest.name}")
    was_selected = backend.is_selected_file_name(manifest.file_name)
    source_text = backend.read_source_text_by_file_name(manifest.file_name)
    renamed = backend.preset_file_store.rename_preset(backend.engine, manifest.file_name, new_name)
    rewritten = _rewrite_preset_headers(
        source_text,
        new_name,
        template_origin=manifest.template_origin,
        preset_kind=_header_preset_kind(manifest.kind),
    )
    updated = backend.preset_file_store.update_preset(backend.engine, renamed.file_name, rewritten, None)
    backend._rename_library_meta(
        manifest.file_name,
        updated.file_name,
        old_display_name=manifest.name,
        new_display_name=updated.name,
    )
    if was_selected:
        backend.preset_selection_service.select_preset(backend.engine, updated.file_name)
        backend.notify_preset_identity_changed(updated.file_name)
        backend._refresh_selected_source_preset()
    return updated


def duplicate_by_file_name(backend, file_name: str, new_name: str):
    manifest = backend.get_manifest_by_file_name(file_name)
    if manifest is None:
        raise ValueError(f"Preset not found: {file_name}")
    source_text = backend.read_source_text_by_file_name(manifest.file_name)
    rewritten = _rewrite_preset_headers(
        source_text,
        new_name,
        template_origin=manifest.template_origin,
        preset_kind=_header_preset_kind(manifest.kind),
    )
    duplicated = backend.preset_file_store.create_preset(backend.engine, new_name, rewritten)
    backend._copy_library_meta(
        manifest.file_name,
        duplicated.file_name,
        source_display_name=manifest.name,
        new_display_name=duplicated.name,
    )
    backend.notify_presets_changed()
    return duplicated


def create_preset(backend, name: str, *, from_current: bool = True):
    source_text = backend.read_selected_source_text() if from_current else _resolve_reset_template(backend.launch_method, "Default")
    rewritten = _rewrite_preset_headers(source_text, name)
    created = backend.preset_file_store.create_preset(backend.engine, name, rewritten)
    backend.notify_presets_changed()
    return created


def import_from_file(backend, src_path: Path, name: str | None = None):
    src = Path(src_path)
    if not src.exists():
        raise ValueError(f"Import source not found: {src}")
    preset_name = str(name or src.stem or "Imported").strip() or "Imported"
    source_text = src.read_text(encoding="utf-8", errors="replace")
    rewritten = _rewrite_preset_headers(
        source_text,
        preset_name,
        preset_kind="imported",
    )
    imported = backend.preset_file_store.create_preset(backend.engine, preset_name, rewritten, kind="imported")
    backend._delete_library_meta(imported.file_name, display_name=imported.name)
    backend.notify_presets_changed()
    return imported


def export_plain_text_by_file_name(backend, file_name: str, dest_path: Path) -> Path:
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = backend.read_source_text_by_file_name(file_name)
    if not text.endswith("\n"):
        text += "\n"
    dest.write_text(text, encoding="utf-8")
    return dest


def reset_to_template_by_file_name(backend, file_name: str):
    manifest = backend.get_manifest_by_file_name(file_name)
    if manifest is None:
        raise ValueError(f"Preset not found: {file_name}")
    builtin_path = backend.app_paths.engine_paths(backend.engine).ensure_directories().builtin_presets_dir / manifest.file_name
    if str(manifest.kind or "").strip().lower() == "builtin":
        return manifest
    if builtin_path.exists():
        backend.preset_file_store.delete_preset(backend.engine, manifest.file_name)
        updated = backend.get_manifest_by_file_name(manifest.file_name)
        if updated is None:
            raise ValueError("Built-in preset not found after reset")
        backend.notify_preset_saved(updated.file_name)
        if backend.is_selected_file_name(manifest.file_name):
            backend._refresh_selected_source_preset()
        return updated
    template_key = str(manifest.template_origin or manifest.name or "").strip()
    template_content = _resolve_reset_template(backend.launch_method, template_key)
    if not template_content:
        raise ValueError("Template content not found")
    rewritten = _rewrite_preset_headers(
        template_content,
        manifest.name,
        template_origin=str(manifest.template_origin or "").strip() or None,
        preset_kind=_header_preset_kind(manifest.kind),
    )
    updated = backend.preset_file_store.update_preset(backend.engine, manifest.file_name, rewritten, None)
    backend.notify_preset_saved(updated.file_name)
    if backend.is_selected_file_name(manifest.file_name):
        backend._refresh_selected_source_preset()
    return updated


def reset_all_to_templates(backend) -> tuple[int, int, list[str]]:
    result = _template_support_reset_all_templates(backend.launch_method)
    backend.notify_presets_changed()
    selected_file_name = backend.get_selected_file_name()
    if selected_file_name and backend.get_manifest_by_file_name(selected_file_name) is not None:
        backend.notify_preset_saved(selected_file_name)
        backend._refresh_selected_source_preset()
    return result


def delete_by_file_name(backend, file_name: str) -> None:
    manifest = backend.get_manifest_by_file_name(file_name)
    if manifest is None:
        raise ValueError(f"Preset not found: {file_name}")
    if str(manifest.kind or "").strip().lower() == "builtin":
        raise ValueError(f"Built-in preset cannot be deleted: {manifest.name}")
    backend.preset_selection_service.ensure_can_delete(backend.engine, manifest.file_name)
    backend.preset_file_store.delete_preset(backend.engine, manifest.file_name)
    backend._delete_library_meta(manifest.file_name, display_name=manifest.name)
    backend.notify_presets_changed()
