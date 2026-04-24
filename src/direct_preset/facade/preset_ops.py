from __future__ import annotations

from pathlib import Path

from core.presets.template_support import (
    resolve_reset_template as _template_support_resolve_reset_template,
    reset_all_templates as _template_support_reset_all_templates,
)
from .text_ops import (
    _extract_debug_log_file,
    _header_preset_kind,
    _join_arg_lines,
    _normalize_direct_preset_source_text,
    _ports_include_443,
    _rewrite_debug_log_setting,
    _rewrite_preset_headers,
    _split_arg_lines,
)


def _resolve_reset_template(launch_method: str, preset_name: str) -> str:
    return _template_support_resolve_reset_template(launch_method, preset_name)


def get_advanced_settings_state(backend) -> dict[str, bool]:
    discord_restart = True
    try:
        from discord.discord_restart import get_discord_restart_setting

        discord_restart = bool(get_discord_restart_setting(default=True))
    except Exception:
        pass

    manifest = backend.get_selected_manifest()
    if manifest is None:
        return {
            "discord_restart": discord_restart,
            "wssize_enabled": False,
            "debug_log_enabled": False,
        }

    debug_log_enabled = False
    try:
        debug_log_enabled = bool(_extract_debug_log_file(backend.read_source_text_by_file_name(manifest.file_name)))
    except Exception:
        debug_log_enabled = False

    wssize_enabled = False
    try:
        preset = backend.get_selected_source_preset_model()
        if preset:
            contexts = backend._service().collect_target_contexts(preset)
            for target_key, ctx in contexts.items():
                if ctx.protocol_kind != "tcp":
                    continue
                profile = preset.profiles[ctx.profile_index]
                if not any(
                    line.strip().startswith("--filter-tcp=") and _ports_include_443(line.split("=", 1)[1].strip())
                    for line in profile.match_lines
                ):
                    continue
                args_text = backend._service()._get_raw_args(preset, target_key)
                if backend._adapter().wssize_enabled_from_args(args_text):
                    wssize_enabled = True
                    break
    except Exception:
        wssize_enabled = False

    return {
        "discord_restart": discord_restart,
        "wssize_enabled": bool(wssize_enabled),
        "debug_log_enabled": bool(debug_log_enabled),
    }


def set_debug_log_enabled(backend, enabled: bool) -> bool:
    manifest = backend.get_selected_manifest()
    if manifest is None:
        return False
    display_name = str(manifest.name or "").strip() or Path(manifest.file_name).stem
    source_text = backend.read_source_text_by_file_name(manifest.file_name)
    rewritten = _rewrite_debug_log_setting(source_text, display_name, bool(enabled))
    backend.save_source_text_by_file_name(manifest.file_name, rewritten)
    return True


def get_wssize_enabled(backend) -> bool:
    preset = backend.get_selected_source_preset_model()
    if not preset:
        return False

    contexts = backend._service().collect_target_contexts(preset)
    for target_key, ctx in contexts.items():
        if ctx.protocol_kind != "tcp":
            continue
        profile = preset.profiles[ctx.profile_index]
        if not any(
            line.strip().startswith("--filter-tcp=") and _ports_include_443(line.split("=", 1)[1].strip())
            for line in profile.match_lines
        ):
            continue
        args_text = backend._service()._get_raw_args(preset, target_key)
        if backend._adapter().wssize_enabled_from_args(args_text):
            return True
    return False


def set_wssize_enabled(backend, enabled: bool) -> bool:
    preset = backend.get_selected_source_preset_model()
    if not preset:
        return False

    changed = False
    touched_any_tcp_443 = False
    target_keys = list(backend._service().collect_target_contexts(preset).keys())

    for target_key in target_keys:
        normalized_key = str(target_key or "").strip().lower()
        current_ctx = backend._service().collect_target_contexts(preset).get(normalized_key)
        if not normalized_key or current_ctx is None or current_ctx.protocol_kind != "tcp":
            continue
        profile = preset.profiles[current_ctx.profile_index]
        if not any(
            line.strip().startswith("--filter-tcp=") and _ports_include_443(line.split("=", 1)[1].strip())
            for line in profile.match_lines
        ):
            continue

        touched_any_tcp_443 = True
        current_args = backend._service()._get_raw_args(preset, normalized_key) or ""
        next_args = backend._adapter().rewrite_wssize_args(current_args, bool(enabled))
        if next_args != _join_arg_lines(_split_arg_lines(current_args)):
            if backend._service()._update_raw_args(preset, normalized_key, next_args):
                changed = True

    if not touched_any_tcp_443:
        return False if enabled else True
    if not changed:
        return True

    try:
        preset.touch()
    except Exception:
        pass
    return bool(backend.save_preset_model(preset))


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
        backend._refresh_selected_launch_profile_from_source()
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
    return duplicated


def create_preset(backend, name: str, *, from_current: bool = True):
    source_text = backend.read_selected_source_text() if from_current else _resolve_reset_template(backend.launch_method, "Default")
    rewritten = _rewrite_preset_headers(source_text, name)
    return backend.preset_file_store.create_preset(backend.engine, name, rewritten)


def import_from_file(backend, src_path: Path, name: str | None = None):
    src = Path(src_path)
    if not src.exists():
        raise ValueError(f"Import source not found: {src}")
    target_name = str(name or src.stem or "Imported").strip() or "Imported"
    source_text = src.read_text(encoding="utf-8", errors="replace")
    rewritten = _rewrite_preset_headers(
        source_text,
        target_name,
        preset_kind="imported",
    )
    imported = backend.preset_file_store.create_preset(backend.engine, target_name, rewritten, kind="imported")
    backend._delete_library_meta(imported.file_name, display_name=imported.name)
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
            backend._refresh_selected_launch_profile_from_source()
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
        backend._refresh_selected_launch_profile_from_source()
    return updated


def reset_all_to_templates(backend) -> tuple[int, int, list[str]]:
    result = _template_support_reset_all_templates(backend.launch_method)
    selected_file_name = backend.get_selected_file_name()
    if selected_file_name and backend.get_manifest_by_file_name(selected_file_name) is not None:
        backend.notify_preset_saved(selected_file_name)
        backend._refresh_selected_launch_profile_from_source()
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
