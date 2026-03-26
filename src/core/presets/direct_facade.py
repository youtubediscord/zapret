from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from core.services import get_app_paths, get_direct_flow_coordinator, get_preset_repository, get_selection_service

from .models import PresetDocument


def _rewrite_preset_header_name(source_text: str, target_name: str) -> str:
    text = (source_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.splitlines()
    replaced = False

    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped.lower().startswith("# preset:"):
            lines[idx] = f"# Preset: {target_name}"
            replaced = True
            break
        if stripped and not stripped.startswith("#"):
            break

    if not replaced:
        lines.insert(0, f"# Preset: {target_name}")

    rewritten = "\n".join(lines).rstrip("\n")
    return rewritten + "\n"


def _rewrite_preset_headers(
    source_text: str,
    target_name: str,
    *,
    created: str | None = None,
    modified: str | None = None,
) -> str:
    text = (source_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.splitlines()

    header_end = 0
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped and not stripped.startswith("#"):
            header_end = idx
            break
    else:
        header_end = len(lines)

    header = lines[:header_end]
    body = lines[header_end:]
    out_header: list[str] = []
    saw_preset = False
    saw_created = False
    saw_modified = False

    for raw in header:
        stripped = raw.strip()
        lowered = stripped.lower()
        if lowered.startswith("# preset:"):
            out_header.append(f"# Preset: {target_name}")
            saw_preset = True
            continue
        if lowered.startswith("# created:"):
            if created is not None:
                out_header.append(f"# Created: {created}")
                saw_created = True
            else:
                out_header.append(raw.rstrip("\n"))
                saw_created = True
            continue
        if lowered.startswith("# modified:"):
            if modified is not None:
                out_header.append(f"# Modified: {modified}")
                saw_modified = True
            else:
                out_header.append(raw.rstrip("\n"))
                saw_modified = True
            continue
        if lowered.startswith("# activepreset:"):
            continue
        out_header.append(raw.rstrip("\n"))

    if not saw_preset:
        out_header.insert(0, f"# Preset: {target_name}")

    insert_idx = 1 if out_header and out_header[0].startswith("# Preset:") else 0
    if created is not None and not saw_created:
        out_header.insert(insert_idx, f"# Created: {created}")
        insert_idx += 1
    if modified is not None and not saw_modified:
        out_header.insert(insert_idx, f"# Modified: {modified}")

    rewritten = "\n".join(out_header + body).rstrip("\n")
    return rewritten + "\n"


def _drop_active_preset_headers(source_text: str) -> str:
    text = (source_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line for line in text.splitlines() if not line.strip().lower().startswith("# activepreset:")]
    return "\n".join(lines).rstrip("\n") + "\n"


def _resolve_reset_template(launch_method: str, preset_name: str) -> str:
    if launch_method == "direct_zapret2":
        from preset_zapret2.preset_defaults import (
            get_builtin_base_from_copy_name,
            get_default_template_content,
            get_template_content,
        )

        content = get_template_content(preset_name)
        if not content:
            base = get_builtin_base_from_copy_name(preset_name)
            if base:
                content = get_template_content(base)
        if not content:
            content = get_default_template_content()
        return str(content or "")

    from preset_zapret1.preset_defaults import (
        get_builtin_base_from_copy_name_v1,
        get_builtin_preset_content_v1,
        get_default_template_content_v1,
        get_template_content_v1,
    )

    content = get_template_content_v1(preset_name)
    if not content:
        base = get_builtin_base_from_copy_name_v1(preset_name)
        if base:
            content = get_template_content_v1(base)
    if not content:
        content = get_default_template_content_v1()
    if not content:
        content = get_builtin_preset_content_v1("Default")
    return str(content or "")


@dataclass(frozen=True)
class DirectPresetFacade:
    engine: str
    launch_method: str
    on_dpi_reload_needed: Optional[Callable[[], None]] = None

    @classmethod
    def from_launch_method(
        cls,
        launch_method: str,
        *,
        on_dpi_reload_needed: Optional[Callable[[], None]] = None,
    ) -> "DirectPresetFacade":
        method = str(launch_method or "").strip().lower()
        if method == "direct_zapret2":
            return cls(engine="winws2", launch_method=method, on_dpi_reload_needed=on_dpi_reload_needed)
        if method == "direct_zapret1":
            return cls(engine="winws1", launch_method=method, on_dpi_reload_needed=on_dpi_reload_needed)
        raise ValueError(f"Unsupported launch method for direct preset facade: {launch_method}")

    def _get_manager(self):
        if self.launch_method == "direct_zapret2":
            from preset_zapret2 import PresetManager

            return PresetManager(on_dpi_reload_needed=self.on_dpi_reload_needed)

        from preset_zapret1 import PresetManagerV1

        return PresetManagerV1(on_dpi_reload_needed=self.on_dpi_reload_needed)

    def list_presets(self) -> list[PresetDocument]:
        return get_preset_repository().list_presets(self.engine)

    def list_names(self) -> list[str]:
        return [item.manifest.name for item in self.list_presets()]

    def exists(self, name: str) -> bool:
        return self.get_document(name) is not None

    def get_selected_name(self) -> str:
        preset = get_selection_service().ensure_selected_preset(self.engine, "Default")
        return preset.manifest.name if preset is not None else ""

    def get_selected_document(self) -> PresetDocument | None:
        return get_direct_flow_coordinator().get_selected_source_preset(self.launch_method)

    def is_selected(self, name: str) -> bool:
        return (self.get_selected_name() or "").strip().lower() == str(name or "").strip().lower()

    def get_document(self, name: str) -> PresetDocument | None:
        return get_preset_repository().find_preset_by_name(self.engine, name)

    def get_source_path(self, name: str) -> Path:
        document = self.get_document(name)
        if document is None:
            raise ValueError(f"Preset not found: {name}")
        return get_app_paths().engine_paths(self.engine).ensure_directories().presets_dir / document.manifest.file_name

    def save_source_text(self, name: str, source_text: str) -> PresetDocument:
        document = self.get_document(name)
        if document is None:
            raise ValueError(f"Preset not found: {name}")
        normalized = _drop_active_preset_headers(source_text)
        updated = get_preset_repository().update_preset(self.engine, document.manifest.id, normalized, None)
        if self.is_selected(updated.manifest.name):
            get_direct_flow_coordinator().refresh_selected_runtime(self.launch_method)
        return updated

    def select(self, name: str):
        return get_direct_flow_coordinator().select_preset(self.launch_method, name)

    def rename(self, old_name: str, new_name: str) -> PresetDocument:
        document = self.get_document(old_name)
        if document is None:
            raise ValueError(f"Preset not found: {old_name}")
        was_selected = self.is_selected(old_name)

        renamed = get_preset_repository().rename_preset(self.engine, document.manifest.id, new_name)
        rewritten = _rewrite_preset_headers(
            document.source_text,
            new_name,
            modified=datetime.now().isoformat(),
        )
        updated = get_preset_repository().update_preset(self.engine, renamed.manifest.id, rewritten, None)

        if was_selected:
            get_direct_flow_coordinator().refresh_selected_runtime(self.launch_method)
        return updated

    def duplicate(self, name: str, new_name: str) -> PresetDocument:
        document = self.get_document(name)
        if document is None:
            raise ValueError(f"Preset not found: {name}")
        now = datetime.now().isoformat()
        rewritten = _rewrite_preset_headers(
            document.source_text,
            new_name,
            created=now,
            modified=now,
        )
        return get_preset_repository().create_preset(self.engine, new_name, rewritten)

    def create(self, name: str, *, from_current: bool = True) -> PresetDocument:
        source_text = ""
        if from_current:
            selected = self.get_selected_document()
            source_text = selected.source_text if selected is not None else ""
        else:
            source_text = _resolve_reset_template(self.launch_method, "Default")
        now = datetime.now().isoformat()
        rewritten = _rewrite_preset_headers(
            source_text,
            name,
            created=now,
            modified=now,
        )
        return get_preset_repository().create_preset(self.engine, name, rewritten)

    def import_from_file(self, src_path: Path, name: str | None = None) -> PresetDocument:
        src = Path(src_path)
        if not src.exists():
            raise ValueError(f"Import source not found: {src}")
        target_name = str(name or src.stem or "Imported").strip() or "Imported"
        source_text = src.read_text(encoding="utf-8", errors="replace")
        rewritten = _rewrite_preset_headers(source_text, target_name)

        if self.launch_method == "direct_zapret2":
            from config import get_zapret_presets_v2_template_dir
            from preset_zapret2.preset_defaults import unmark_preset_deleted

            template_dir = Path(get_zapret_presets_v2_template_dir())
            template_dir.mkdir(parents=True, exist_ok=True)
            (template_dir / f"{target_name}.txt").write_text(rewritten, encoding="utf-8")
            try:
                unmark_preset_deleted(target_name)
            except Exception:
                pass
        else:
            from config import get_zapret_presets_v1_template_dir
            from preset_zapret1.preset_defaults import unmark_preset_deleted_v1

            template_dir = Path(get_zapret_presets_v1_template_dir())
            template_dir.mkdir(parents=True, exist_ok=True)
            (template_dir / f"{target_name}.txt").write_text(rewritten, encoding="utf-8")
            try:
                unmark_preset_deleted_v1(target_name)
            except Exception:
                pass

        return get_preset_repository().create_preset(self.engine, target_name, rewritten)

    def export_plain_text(self, name: str, dest_path: Path) -> Path:
        document = self.get_document(name)
        if document is None:
            raise ValueError(f"Preset not found: {name}")
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = document.source_text or ""
        if not text.endswith("\n"):
            text += "\n"
        dest.write_text(text, encoding="utf-8")
        return dest

    def reset_to_template(self, name: str) -> PresetDocument:
        document = self.get_document(name)
        if document is None:
            raise ValueError(f"Preset not found: {name}")
        template_content = _resolve_reset_template(self.launch_method, name)
        if not template_content:
            raise ValueError("Template content not found")
        rewritten = _rewrite_preset_headers(template_content, name)
        updated = get_preset_repository().update_preset(self.engine, document.manifest.id, rewritten, None)
        if self.is_selected(name):
            get_direct_flow_coordinator().refresh_selected_runtime(self.launch_method)
        return updated

    def reset_all_to_templates(self) -> tuple[int, int, list[str]]:
        if self.launch_method == "direct_zapret2":
            from preset_zapret2.preset_defaults import overwrite_templates_to_presets

            result = overwrite_templates_to_presets()
        else:
            from preset_zapret1.preset_defaults import overwrite_v1_templates_to_presets

            result = overwrite_v1_templates_to_presets()

        selected_name = self.get_selected_name()
        if selected_name and self.get_document(selected_name) is not None:
            try:
                get_direct_flow_coordinator().refresh_selected_runtime(self.launch_method)
            except Exception:
                pass
        return result

    def restore_deleted(self) -> None:
        if self.launch_method == "direct_zapret2":
            from preset_zapret2.preset_defaults import clear_all_deleted_presets, ensure_templates_copied_to_presets

            clear_all_deleted_presets()
            ensure_templates_copied_to_presets()
        else:
            from preset_zapret1.preset_defaults import clear_all_deleted_presets_v1, ensure_v1_templates_copied_to_presets

            clear_all_deleted_presets_v1()
            ensure_v1_templates_copied_to_presets()

        selected_name = self.get_selected_name()
        if selected_name and self.get_document(selected_name) is not None:
            try:
                get_direct_flow_coordinator().refresh_selected_runtime(self.launch_method)
            except Exception:
                pass

    def delete(self, name: str) -> None:
        document = self.get_document(name)
        if document is None:
            raise ValueError(f"Preset not found: {name}")
        get_selection_service().ensure_can_delete(self.engine, document.manifest.id)
        get_preset_repository().delete_preset(self.engine, document.manifest.id)

    def get_strategy_selections(self) -> dict:
        return self._get_manager().get_strategy_selections() or {}

    def set_strategy_selection(self, category_key: str, strategy_id: str, *, save_and_sync: bool = True) -> bool:
        return bool(self._get_manager().set_strategy_selection(category_key, strategy_id, save_and_sync=save_and_sync))

    def get_active_preset(self):
        return self._get_manager().get_active_preset()

    def get_category_filter_mode(self, category_key: str) -> str:
        return self._get_manager().get_category_filter_mode(category_key)

    def update_category_filter_mode(self, category_key: str, filter_mode: str, *, save_and_sync: bool = True) -> bool:
        return bool(self._get_manager().update_category_filter_mode(category_key, filter_mode, save_and_sync=save_and_sync))

    def reset_category_settings(self, category_key: str) -> bool:
        return bool(self._get_manager().reset_category_settings(category_key))

    def get_category_syndata(self, category_key: str, *, protocol: str = "tcp"):
        return self._get_manager().get_category_syndata(category_key, protocol=protocol)

    def update_category_syndata(self, category_key: str, syndata, *, protocol: str = "tcp", save_and_sync: bool = True) -> bool:
        return bool(
            self._get_manager().update_category_syndata(
                category_key,
                syndata,
                protocol=protocol,
                save_and_sync=save_and_sync,
            )
        )

    def get_category_sort_order(self, category_key: str) -> str:
        return self._get_manager().get_category_sort_order(category_key)

    def update_category_sort_order(self, category_key: str, sort_order: str, *, save_and_sync: bool = True) -> bool:
        return bool(self._get_manager().update_category_sort_order(category_key, sort_order, save_and_sync=save_and_sync))

    def ensure_category(self, preset, category_key: str):
        manager = self._get_manager()
        if self.launch_method == "direct_zapret2":
            if category_key not in preset.categories:
                preset.categories[category_key] = manager._create_category_with_defaults(category_key)
            return preset.categories[category_key]

        from preset_zapret1.preset_model import CategoryConfigV1

        if category_key not in preset.categories:
            preset.categories[category_key] = CategoryConfigV1(name=category_key)
        return preset.categories[category_key]

    def save_preset_model(self, preset, *, changed_category: str | None = None) -> bool:
        manager = self._get_manager()
        if self.launch_method == "direct_zapret2":
            return bool(manager._save_and_sync_preset(preset, changed_category=changed_category))
        return bool(manager._save_and_sync_preset(preset))

    def save_category_preserving_layout(self, preset, category_key: str) -> bool:
        manager = self._get_manager()
        if self.launch_method == "direct_zapret2":
            return bool(manager._save_and_sync_preset(preset, changed_category=category_key))
        return bool(manager._save_and_sync_category(preset, category_key))
