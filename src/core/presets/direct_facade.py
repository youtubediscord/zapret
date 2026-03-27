from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from core.services import get_app_paths, get_direct_flow_coordinator, get_preset_repository, get_selection_service

from .models import PresetDocument
from preset_zapret2.mode_projection import (
    normalize_direct_zapret2_ui_mode,
    project_preset_for_direct_ui_mode,
)


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


def _apply_zapret2_strategy_args(preset, category_key: str, strategy_id: str) -> None:
    from preset_zapret2.block_semantics import (
        apply_structured_block_overrides_to_category,
        reset_structured_advanced_state,
    )
    from preset_zapret2.catalog import load_categories, load_strategies
    from preset_zapret2.txt_preset_parser import extract_strategy_args

    category = (preset.categories or {}).get(category_key)
    if not category:
        return

    if strategy_id == "none":
        category.tcp_args = ""
        category.udp_args = ""
        category.tcp_args_raw = ""
        category.udp_args_raw = ""
        return

    categories = load_categories()
    category_info = categories.get(category_key) or {}
    strategy_type = (category_info.get("strategy_type") or "tcp").strip() or "tcp"

    try:
        from strategy_menu.strategies_registry import get_current_strategy_set

        strategy_set = get_current_strategy_set()
    except Exception:
        strategy_set = None

    strategies = load_strategies(strategy_type, strategy_set=strategy_set)
    args = (strategies.get(strategy_id) or {}).get("args", "") or ""

    if not args and strategy_type == "tcp":
        try:
            fake_strategy_set = "advanced" if strategy_set == "advanced" else None
            fake_strategies = load_strategies("tcp_fake", strategy_set=fake_strategy_set)
            args = (fake_strategies.get(strategy_id) or {}).get("args", "") or ""
        except Exception:
            args = args or ""

    if not args:
        return

    protocol = (category_info.get("protocol") or "").upper()
    is_udp = any(token in protocol for token in ("UDP", "QUIC", "L7", "RAW"))

    if strategy_set == "advanced":
        pure_strategy_args = extract_strategy_args(args, category_key=category_key)

        if is_udp:
            category.udp_args = pure_strategy_args
            category.udp_args_raw = args
            category.tcp_args = ""
            category.tcp_args_raw = ""
            apply_structured_block_overrides_to_category(category, args, protocol="udp")
            return

        category.tcp_args = pure_strategy_args
        category.tcp_args_raw = args
        category.udp_args = ""
        category.udp_args_raw = ""
        apply_structured_block_overrides_to_category(category, args, protocol="tcp")
        return

    if is_udp:
        category.udp_args = args
        category.udp_args_raw = args
        category.tcp_args = ""
        category.tcp_args_raw = ""
    else:
        category.tcp_args = args
        category.tcp_args_raw = args
        category.udp_args = ""
        category.udp_args_raw = ""

    reset_structured_advanced_state(category)


def _selection_id_from_zapret1_category(category) -> str:
    strategy_id = str(getattr(category, "strategy_id", "") or "").strip().lower() or "none"
    if strategy_id == "none":
        has_args = bool(
            (getattr(category, "tcp_args", "") or "").strip()
            or (getattr(category, "udp_args", "") or "").strip()
        )
        if has_args:
            return "custom"
    return strategy_id


def _apply_zapret1_strategy_args(preset, category_key: str, strategy_id: str) -> None:
    from preset_zapret1.strategies_loader import load_v1_strategies
    from preset_zapret2.catalog import load_categories

    category = (preset.categories or {}).get(category_key)
    if not category:
        return

    if strategy_id == "none":
        category.tcp_args = ""
        category.udp_args = ""
        return

    categories = load_categories()
    category_info = categories.get(category_key) or {}
    strategies = load_v1_strategies(category_key)
    args = (strategies.get(strategy_id) or {}).get("args", "") or ""

    if not args:
        return

    protocol = (category_info.get("protocol") or "").upper()
    is_udp = any(token in protocol for token in ("UDP", "QUIC", "L7", "RAW"))
    if is_udp:
        category.udp_args = args
        category.tcp_args = ""
    else:
        category.tcp_args = args
        category.udp_args = ""


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

    def _load_selected_preset_model(self):
        selected_name = (self.get_selected_name() or "").strip()
        if not selected_name:
            return None

        if self.launch_method == "direct_zapret2":
            from preset_zapret2 import load_preset
            try:
                from strategy_menu import get_direct_zapret2_ui_mode

                ui_mode = normalize_direct_zapret2_ui_mode(get_direct_zapret2_ui_mode())
            except Exception:
                ui_mode = "basic"

            preset = load_preset(selected_name)
            if preset is None:
                return None
            return project_preset_for_direct_ui_mode(preset, ui_mode)

        from preset_zapret1 import load_preset_v1

        return load_preset_v1(selected_name)

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

    def is_builtin_name(self, name: str) -> bool:
        candidate = str(name or "").strip()
        if not candidate:
            return False

        if self.launch_method == "direct_zapret2":
            from preset_zapret2.preset_defaults import get_template_canonical_name

            canonical = get_template_canonical_name(candidate)
            return bool(canonical and canonical.casefold() == candidate.casefold())

        if self.launch_method == "direct_zapret1":
            from preset_zapret1.preset_defaults import get_template_canonical_name_v1

            canonical = get_template_canonical_name_v1(candidate)
            return bool(canonical and canonical.casefold() == candidate.casefold())

        return False

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

    def _refresh_selected_runtime_from_source(self) -> None:
        selected_name = self.get_selected_name()
        if not selected_name or self.get_document(selected_name) is None:
            return

        if self.launch_method == "direct_zapret2":
            from preset_zapret2 import load_preset
            from preset_zapret2.sync_layer import sync_preset_to_runtime

            preset = load_preset(selected_name)
            if preset is None:
                raise RuntimeError(f"Failed to reload selected preset after reset: {selected_name}")
            if not sync_preset_to_runtime(preset, on_dpi_reload_needed=self.on_dpi_reload_needed):
                raise RuntimeError(f"Failed to sync selected runtime after reset: {selected_name}")
            return

        get_direct_flow_coordinator().refresh_selected_runtime(self.launch_method)

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
            self._refresh_selected_runtime_from_source()
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
            self._refresh_selected_runtime_from_source()
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
            self._refresh_selected_runtime_from_source()

    def delete(self, name: str) -> None:
        document = self.get_document(name)
        if document is None:
            raise ValueError(f"Preset not found: {name}")
        if self.is_builtin_name(name):
            raise ValueError(f"Built-in preset cannot be deleted: {name}")
        get_selection_service().ensure_can_delete(self.engine, document.manifest.id)
        get_preset_repository().delete_preset(self.engine, document.manifest.id)

    def get_strategy_selections(self) -> dict:
        if self.launch_method == "direct_zapret2":
            preset = self.get_active_preset()
            if not preset:
                return {}
            return {
                str(cat_key or "").strip().lower(): (getattr(cat_config, "strategy_id", "") or "none")
                for cat_key, cat_config in (preset.categories or {}).items()
                if str(cat_key or "").strip()
            }
        if self.launch_method == "direct_zapret1":
            preset = self.get_active_preset()
            if not preset:
                return {}

            raw = {}
            for cat_key, cat_config in (preset.categories or {}).items():
                normalized_key = str(cat_key or "").strip().lower()
                if not normalized_key:
                    continue
                raw[normalized_key] = _selection_id_from_zapret1_category(cat_config)

            try:
                from preset_zapret1.sync_layer import Zapret1PresetSyncLayer

                present_from_lists = Zapret1PresetSyncLayer().infer_active_categories_from_launch_config()
                for key in present_from_lists:
                    if raw.get(key, "none") == "none":
                        raw[key] = "custom"
            except Exception:
                pass
            return raw
        raise ValueError(f"Unsupported launch method for strategy selections: {self.launch_method}")

    def set_strategy_selections(self, selections: dict, *, save_and_sync: bool = True) -> bool:
        if self.launch_method == "direct_zapret2":
            preset = self.get_active_preset()
            if not preset:
                return False

            for category_key, strategy_id in (selections or {}).items():
                normalized_key = str(category_key or "").strip().lower()
                if not normalized_key:
                    continue
                category = self.ensure_category(preset, normalized_key)
                if category is None:
                    continue
                category.strategy_id = strategy_id
                _apply_zapret2_strategy_args(preset, normalized_key, strategy_id)

            preset.touch()
            return self.save_preset_model(preset) if save_and_sync else True
        if self.launch_method == "direct_zapret1":
            preset = self.get_active_preset()
            if not preset:
                return False

            for category_key, strategy_id in (selections or {}).items():
                normalized_key = str(category_key or "").strip().lower()
                if not normalized_key:
                    continue
                category = self.ensure_category(preset, normalized_key)
                if category is None:
                    continue
                category.strategy_id = strategy_id
                _apply_zapret1_strategy_args(preset, normalized_key, strategy_id)

            preset.touch()
            return self.save_preset_model(preset) if save_and_sync else True
        raise ValueError(f"Unsupported launch method for strategy selections: {self.launch_method}")

    def set_strategy_selection(self, category_key: str, strategy_id: str, *, save_and_sync: bool = True) -> bool:
        if self.launch_method == "direct_zapret2":
            normalized_key = str(category_key or "").strip().lower()
            if not normalized_key:
                return False
            preset = self.get_active_preset()
            if not preset:
                return False
            category = self.ensure_category(preset, normalized_key)
            if category is None:
                return False
            category.strategy_id = strategy_id
            _apply_zapret2_strategy_args(preset, normalized_key, strategy_id)
            preset.touch()
            return self.save_preset_model(preset, changed_category=normalized_key) if save_and_sync else True
        if self.launch_method == "direct_zapret1":
            normalized_key = str(category_key or "").strip().lower()
            if not normalized_key:
                return False
            preset = self.get_active_preset()
            if not preset:
                return False
            category = self.ensure_category(preset, normalized_key)
            if category is None:
                return False
            category.strategy_id = strategy_id
            _apply_zapret1_strategy_args(preset, normalized_key, strategy_id)
            preset.touch()
            return self.save_category_preserving_layout(preset, normalized_key) if save_and_sync else True
        raise ValueError(f"Unsupported launch method for strategy selection: {self.launch_method}")

    def get_selected_source_preset(self):
        return self._load_selected_preset_model()

    def get_active_preset(self):
        """Compatibility alias for get_selected_source_preset()."""
        return self.get_selected_source_preset()

    def get_category_filter_mode(self, category_key: str) -> str:
        preset = self.get_active_preset()
        if not preset:
            return "hostlist"
        category = (preset.categories or {}).get(category_key)
        if not category:
            return "hostlist"

        mode = str(getattr(category, "filter_mode", "") or "").strip().lower()
        if mode in ("hostlist", "ipset"):
            return mode
        return "hostlist"

    def update_category_filter_mode(self, category_key: str, filter_mode: str, *, save_and_sync: bool = True) -> bool:
        if self.launch_method == "direct_zapret2":
            mode = str(filter_mode or "").strip().lower()
            if mode not in ("hostlist", "ipset"):
                return False
            preset = self.get_active_preset()
            if not preset:
                return False
            category = self.ensure_category(preset, category_key)
            if category is None:
                return False
            category.filter_mode = mode
            preset.touch()
            return self.save_preset_model(preset) if save_and_sync else True
        if self.launch_method == "direct_zapret1":
            normalized_key = str(category_key or "").strip().lower()
            mode = str(filter_mode or "").strip().lower()
            if mode not in ("hostlist", "ipset"):
                return False
            preset = self.get_active_preset()
            if not preset:
                return False
            category = self.ensure_category(preset, normalized_key)
            if category is None:
                return False
            category.filter_mode = mode
            preset.touch()
            return self.save_category_preserving_layout(preset, normalized_key) if save_and_sync else True
        raise ValueError(f"Unsupported launch method for category filter mode update: {self.launch_method}")

    def reset_category_settings(self, category_key: str) -> bool:
        if self.launch_method == "direct_zapret2":
            from preset_zapret2.preset_defaults import (
                get_builtin_base_from_copy_name,
                get_category_default_filter_mode,
                get_category_default_syndata,
                get_default_category_settings,
                get_default_template_content,
                get_template_content,
                invalidate_templates_cache,
            )
            from preset_zapret2.preset_model import SyndataSettings
            from preset_zapret2.strategy_inference import infer_strategy_id_from_args
            from preset_zapret2.txt_preset_parser import parse_preset_content

            preset = self.get_active_preset()
            if not preset:
                return False

            normalized_key = str(category_key or "").strip().lower()
            category = self.ensure_category(preset, normalized_key)
            if category is None:
                return False

            try:
                from strategy_menu.strategies_registry import get_current_strategy_set

                current_strategy_set = get_current_strategy_set()
            except Exception:
                current_strategy_set = None

            default_filter_mode = get_category_default_filter_mode(normalized_key)
            default_settings = get_default_category_settings().get(normalized_key) or {}

            active_preset_name = (self.get_selected_name() or getattr(preset, "name", "") or "").strip()
            try:
                try:
                    invalidate_templates_cache()
                except Exception:
                    pass

                template_content = ""
                if active_preset_name:
                    template_content = get_template_content(active_preset_name) or ""
                    if not template_content:
                        base_name = get_builtin_base_from_copy_name(active_preset_name)
                        if base_name:
                            template_content = get_template_content(base_name) or ""
                if not template_content:
                    template_content = get_default_template_content() or ""

                if template_content:
                    template_data = parse_preset_content(template_content)
                    template_category_settings: dict = {}

                    for block in template_data.categories:
                        block_cat = str(getattr(block, "category", "") or "").strip().lower()
                        if not block_cat or block_cat != normalized_key:
                            continue

                        if not template_category_settings:
                            template_category_settings = {
                                "filter_mode": str(getattr(block, "filter_mode", "") or "").strip().lower() or "hostlist",
                                "tcp_enabled": False,
                                "tcp_port": "",
                                "tcp_args": "",
                                "udp_enabled": False,
                                "udp_port": "",
                                "udp_args": "",
                                "syndata_overrides_tcp": {},
                                "syndata_overrides_udp": {},
                            }

                        overrides = getattr(block, "syndata_dict", None) or {}
                        if isinstance(overrides, dict) and overrides:
                            target = "syndata_overrides_tcp" if block.protocol == "tcp" else "syndata_overrides_udp"
                            template_category_settings[target].update(overrides)

                        if block.protocol == "tcp":
                            template_category_settings["tcp_enabled"] = True
                            template_category_settings["tcp_port"] = str(block.port or "").strip()
                            template_category_settings["tcp_args"] = str(block.strategy_args or "").strip()
                            mode = str(block.filter_mode or "").strip().lower()
                            if mode in ("hostlist", "ipset"):
                                template_category_settings["filter_mode"] = mode
                        elif block.protocol == "udp":
                            template_category_settings["udp_enabled"] = True
                            template_category_settings["udp_port"] = str(block.port or "").strip()
                            template_category_settings["udp_args"] = str(block.strategy_args or "").strip()
                            if not template_category_settings.get("tcp_enabled"):
                                mode = str(block.filter_mode or "").strip().lower()
                                if mode in ("hostlist", "ipset"):
                                    template_category_settings["filter_mode"] = mode

                    if template_category_settings:
                        default_settings = template_category_settings
                        mode = str(template_category_settings.get("filter_mode") or "").strip().lower()
                        if mode in ("hostlist", "ipset"):
                            default_filter_mode = mode
            except Exception:
                pass

            if default_settings:
                tcp_defaults = SyndataSettings.get_defaults().to_dict()
                udp_defaults = SyndataSettings.get_defaults_udp().to_dict()

                tcp_overrides = default_settings.get("syndata_overrides_tcp") or {}
                udp_overrides = default_settings.get("syndata_overrides_udp") or {}
                if isinstance(tcp_overrides, dict) and tcp_overrides:
                    tcp_defaults.update(tcp_overrides)
                if isinstance(udp_overrides, dict) and udp_overrides:
                    udp_defaults.update(udp_overrides)
            else:
                tcp_defaults = get_category_default_syndata(normalized_key, protocol="tcp")
                udp_defaults = get_category_default_syndata(normalized_key, protocol="udp")

            category.syndata_tcp = SyndataSettings.from_dict(tcp_defaults)
            category.syndata_udp = SyndataSettings.from_dict(udp_defaults)
            category.filter_mode = default_filter_mode
            category.sort_order = "default"

            if default_settings:
                category.tcp_enabled = bool(default_settings.get("tcp_enabled", False))
                category.udp_enabled = bool(default_settings.get("udp_enabled", False))
                category.tcp_port = str(default_settings.get("tcp_port") or category.tcp_port or "443")
                category.udp_port = str(default_settings.get("udp_port") or category.udp_port or "443")
                category.tcp_args = str(default_settings.get("tcp_args") or "").strip()
                category.udp_args = str(default_settings.get("udp_args") or "").strip()

                inferred = "none"
                if category.tcp_args:
                    inferred = infer_strategy_id_from_args(
                        category_key=normalized_key,
                        args=category.tcp_args,
                        protocol="tcp",
                        strategy_set=current_strategy_set,
                    )
                if inferred == "none" and category.udp_args:
                    inferred = infer_strategy_id_from_args(
                        category_key=normalized_key,
                        args=category.udp_args,
                        protocol="udp",
                        strategy_set=current_strategy_set,
                    )
                category.strategy_id = inferred or "none"
            else:
                if category.strategy_id and category.strategy_id != "none":
                    _apply_zapret2_strategy_args(preset, normalized_key, category.strategy_id)
                else:
                    category.tcp_args = ""
                    category.udp_args = ""
                    category.strategy_id = "none"

            preset.touch()
            return self.save_preset_model(preset)

        raise NotImplementedError(
            "direct_zapret1 does not expose a standalone reset_category_settings path in DirectPresetFacade."
        )

    def get_category_syndata(self, category_key: str, *, protocol: str = "tcp"):
        if self.launch_method == "direct_zapret1":
            raise NotImplementedError(
                "direct_zapret1 does not expose a structured syndata API; "
                "syndata-like flags live inside raw strategy args."
            )

        from preset_zapret2.preset_model import SyndataSettings

        preset = self.get_active_preset()
        if not preset:
            return (
                SyndataSettings.get_defaults()
                if str(protocol or "").strip().lower() == "tcp"
                else SyndataSettings.get_defaults_udp()
            )

        category = (preset.categories or {}).get(category_key)
        if not category:
            return (
                SyndataSettings.get_defaults()
                if str(protocol or "").strip().lower() == "tcp"
                else SyndataSettings.get_defaults_udp()
            )

        protocol_key = str(protocol or "").strip().lower()
        if protocol_key in ("udp", "quic", "l7", "raw"):
            return category.syndata_udp
        return category.syndata_tcp

    def update_category_syndata(self, category_key: str, syndata, *, protocol: str = "tcp", save_and_sync: bool = True) -> bool:
        if self.launch_method == "direct_zapret2":
            from preset_zapret2.preset_model import SyndataSettings

            preset = self.get_active_preset()
            if not preset:
                return False
            category = self.ensure_category(preset, category_key)
            if category is None:
                return False
            try:
                syndata_value = SyndataSettings.from_dict(syndata.to_dict())
            except Exception:
                syndata_value = syndata
            protocol_key = str(protocol or "").strip().lower()
            if protocol_key in ("udp", "quic", "l7", "raw"):
                try:
                    syndata_value.enabled = False
                    syndata_value.send_enabled = False
                except Exception:
                    pass
                category.syndata_udp = syndata_value
            else:
                category.syndata_tcp = syndata_value
            preset.touch()
            return self.save_preset_model(preset) if save_and_sync else True
        raise NotImplementedError(
            "direct_zapret1 does not expose a structured syndata API; "
            "syndata-like flags must be edited through raw strategy args."
        )

    def get_category_sort_order(self, category_key: str) -> str:
        if self.launch_method == "direct_zapret1":
            return "default"

        preset = self.get_active_preset()
        if not preset:
            return "default"
        category = (preset.categories or {}).get(category_key)
        if not category:
            return "default"

        sort_order = str(getattr(category, "sort_order", "") or "").strip().lower()
        if sort_order in ("default", "name_asc", "name_desc"):
            return sort_order
        return "default"

    def update_category_sort_order(self, category_key: str, sort_order: str, *, save_and_sync: bool = True) -> bool:
        if self.launch_method == "direct_zapret1":
            return False

        if self.launch_method == "direct_zapret2":
            value = str(sort_order or "").strip().lower()
            if value not in ("default", "name_asc", "name_desc"):
                return False
            preset = self.get_active_preset()
            if not preset:
                return False
            category = self.ensure_category(preset, category_key)
            if category is None:
                return False
            category.sort_order = value
            preset.touch()
            if not save_and_sync:
                return True
            return self.save_preset_model(preset)
        raise ValueError(f"Unsupported launch method for category sort order update: {self.launch_method}")

    def ensure_category(self, preset, category_key: str):
        if self.launch_method == "direct_zapret2":
            from preset_zapret2.preset_defaults import (
                get_category_default_filter_mode,
                get_category_default_syndata,
            )
            from preset_zapret2.preset_model import CategoryConfig, SyndataSettings

            normalized_key = str(category_key or "").strip().lower()
            if not normalized_key:
                return None
            if normalized_key not in preset.categories:
                preset.categories[normalized_key] = CategoryConfig(
                    name=normalized_key,
                    syndata_tcp=SyndataSettings.from_dict(get_category_default_syndata(normalized_key, protocol="tcp")),
                    syndata_udp=SyndataSettings.from_dict(get_category_default_syndata(normalized_key, protocol="udp")),
                    filter_mode=get_category_default_filter_mode(normalized_key),
                )
            return preset.categories[normalized_key]

        from preset_zapret1.preset_model import CategoryConfigV1

        if category_key not in preset.categories:
            preset.categories[category_key] = CategoryConfigV1(name=category_key)
        return preset.categories[category_key]

    def save_preset_model(self, preset, *, changed_category: str | None = None) -> bool:
        if self.launch_method == "direct_zapret2":
            from preset_zapret2.preset_storage import save_preset
            from preset_zapret2.preset_store import get_preset_store
            from preset_zapret2.sync_layer import sync_preset_to_runtime, update_wf_out_ports_in_base_args

            preset.base_args = update_wf_out_ports_in_base_args(preset)
            if preset.name and preset.name != "Current":
                if not save_preset(preset):
                    return False
                try:
                    get_preset_store().notify_preset_saved(preset.name)
                except Exception:
                    pass
            return bool(
                sync_preset_to_runtime(
                    preset,
                    changed_category=changed_category,
                    on_dpi_reload_needed=self.on_dpi_reload_needed,
                )
            )
        from preset_zapret1.preset_storage import save_preset_v1
        from preset_zapret1.preset_store import get_preset_store_v1
        from preset_zapret1.sync_layer import Zapret1PresetSyncLayer

        if preset.name and preset.name != "Current":
            if not save_preset_v1(preset):
                return False
            try:
                get_preset_store_v1().notify_preset_saved(preset.name)
            except Exception:
                pass

        selected_name = (self.get_selected_name() or "").strip().lower()
        preset_name = str(getattr(preset, "name", "") or "").strip().lower()
        if preset_name and selected_name and preset_name == selected_name:
            try:
                get_direct_flow_coordinator().refresh_selected_runtime("direct_zapret1")
                return True
            except Exception:
                return False

        layer = Zapret1PresetSyncLayer(
            on_dpi_reload_needed=self.on_dpi_reload_needed,
            get_selected_name=self.get_selected_name,
        )
        return bool(layer.sync_preset(preset))

    def save_category_preserving_layout(self, preset, category_key: str) -> bool:
        if self.launch_method == "direct_zapret2":
            return self.save_preset_model(preset, changed_category=category_key)
        from preset_zapret1.sync_layer import Zapret1PresetSyncLayer

        layer = Zapret1PresetSyncLayer(
            on_dpi_reload_needed=self.on_dpi_reload_needed,
            get_selected_name=self.get_selected_name,
        )
        return bool(layer.sync_category_preserving_layout(preset, category_key))
