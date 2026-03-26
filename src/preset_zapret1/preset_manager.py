# preset_zapret1/preset_manager.py
"""High-level preset manager for Zapret 1 (direct_zapret1) mode."""

import os
import re
import shutil
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Callable, Dict, List, Optional

from log import log

from .preset_model import (
    CategoryConfigV1,
    DEFAULT_PRESET_ICON_COLOR,
    PresetV1,
    normalize_preset_icon_color_v1,
    validate_preset_v1,
)
from .preset_storage import (
    get_active_preset_name_v1,
    get_active_preset_path_v1,
    get_preset_path_v1,
    get_presets_dir_v1,
    preset_exists_v1,
    save_preset_v1,
)


class PresetManagerV1:
    """High-level manager for Zapret 1 preset operations."""

    def __init__(
        self,
        on_preset_switched: Optional[Callable[[str], None]] = None,
        on_dpi_reload_needed: Optional[Callable[[], None]] = None,
    ):
        self.on_preset_switched = on_preset_switched
        self.on_dpi_reload_needed = on_dpi_reload_needed
        self._active_preset_cache: Optional[PresetV1] = None
        self._active_preset_mtime: float = 0.0
        self._sync_layer = None

    @staticmethod
    def _get_store():
        from .preset_store import get_preset_store_v1
        return get_preset_store_v1()

    def _get_sync_layer(self):
        if self._sync_layer is None:
            from .sync_layer import Zapret1PresetSyncLayer

            self._sync_layer = Zapret1PresetSyncLayer(
                on_dpi_reload_needed=self.on_dpi_reload_needed,
                invalidate_cache=self._invalidate_active_preset_cache,
                get_selected_name=lambda: self.get_active_preset_name() or "",
            )
        return self._sync_layer

    def _get_facade(self):
        from core.presets.direct_facade import DirectPresetFacade

        return DirectPresetFacade.from_launch_method("direct_zapret1")

    def list_presets(self) -> List[str]:
        return self._get_store().get_preset_names()

    def preset_exists(self, name: str) -> bool:
        return self._get_store().preset_exists(name)

    def get_preset_count(self) -> int:
        return len(self._get_store().get_preset_names())

    def load_preset(self, name: str) -> Optional[PresetV1]:
        return self._get_store().get_preset(name)

    def load_all_presets(self) -> List[PresetV1]:
        store = self._get_store()
        all_presets = store.get_all_presets()
        return [all_presets[n] for n in sorted(all_presets.keys(), key=lambda s: s.lower())]

    def save_preset(self, preset: PresetV1) -> bool:
        errors = validate_preset_v1(preset)
        if errors:
            log(f"V1 preset validation failed: {errors}", "WARNING")
        result = save_preset_v1(preset)
        if result:
            self.invalidate_preset_cache(preset.name)
        return result

    def get_active_preset_name(self) -> Optional[str]:
        """Returns the currently selected source preset name."""
        try:
            from core.services import get_direct_flow_coordinator

            return get_direct_flow_coordinator().get_selected_preset_name("direct_zapret1")
        except Exception:
            try:
                return self._get_store().get_active_preset_name()
            except Exception:
                return get_active_preset_name_v1()

    def get_active_preset(self) -> Optional[PresetV1]:
        """Loads the currently selected source preset with caching."""
        if self._active_preset_cache is not None:
            current_mtime = self._get_active_file_mtime()
            if current_mtime == self._active_preset_mtime and current_mtime > 0:
                return self._active_preset_cache

        name = self.get_active_preset_name()
        preset = None
        if name:
            preset = self.load_preset(name)

        if preset:
            self._active_preset_cache = preset
            self._active_preset_mtime = self._get_active_file_mtime()

        return preset

    @staticmethod
    def _extract_icon_color_from_header(header: str) -> str:
        for line in (header or "").splitlines():
            match = re.match(r"#\s*(?:IconColor|PresetIconColor):\s*(.+)", line.strip(), re.IGNORECASE)
            if match:
                return normalize_preset_icon_color_v1(match.group(1).strip())
        return DEFAULT_PRESET_ICON_COLOR

    def _get_active_file_mtime(self) -> float:
        """Gets mtime of the selected source preset file."""
        try:
            from core.services import get_direct_flow_coordinator

            preset_path = get_direct_flow_coordinator().get_selected_source_path("direct_zapret1")
            if preset_path.exists():
                return os.path.getmtime(str(preset_path))
            active_path = get_active_preset_path_v1()
            if active_path.exists():
                return os.path.getmtime(str(active_path))
            return 0.0
        except Exception:
            return 0.0

    def _invalidate_active_preset_cache(self) -> None:
        self._active_preset_cache = None
        self._active_preset_mtime = 0.0

    def _select_source_preset(self, name: str) -> bool:
        try:
            from core.services import get_selection_service

            get_selection_service().select_preset_by_name("winws1", name)
            self._invalidate_active_preset_cache()
            return True
        except Exception as e:
            log(f"Error selecting V1 source preset '{name}': {e}", "ERROR")
            return False

    def invalidate_preset_cache(self, name: Optional[str] = None) -> None:
        store = self._get_store()
        if name is None:
            store.refresh()
        else:
            store.notify_preset_saved(name)

    def _notify_list_changed(self) -> None:
        self._get_store().notify_presets_changed()

    def switch_preset(self, name: str, reload_dpi: bool = True) -> bool:
        """Selects a preset and regenerates the Zapret 1 launch config."""
        if not preset_exists_v1(name):
            log(f"Cannot switch V1: preset '{name}' not found", "ERROR")
            return False

        try:
            from core.services import get_direct_flow_coordinator

            profile = get_direct_flow_coordinator().select_preset("direct_zapret1", name)

            self._invalidate_active_preset_cache()
            self._get_store().notify_preset_switched(profile.preset_name)

            if reload_dpi and self.on_dpi_reload_needed:
                self.on_dpi_reload_needed()

            log(f"Switched V1 to preset '{profile.preset_name}'", "INFO")

            if self.on_preset_switched:
                self.on_preset_switched(profile.preset_name)
            return True

        except Exception as e:
            log(f"Error switching V1 preset: {e}", "ERROR")
            return False

    def create_preset(self, name: str, from_current: bool = True) -> Optional[PresetV1]:
        if self.preset_exists(name):
            log(f"Cannot create V1: preset '{name}' already exists", "WARNING")
            return None
        try:
            self._get_facade().create(name, from_current=from_current)
            self._notify_list_changed()
            log(f"Created V1 preset '{name}'", "INFO")
            return self.load_preset(name)
        except Exception as e:
            log(f"Error creating V1 preset: {e}", "ERROR")
            return None

    def create_default_preset(self, name: str = "Default") -> Optional[PresetV1]:
        if self.preset_exists(name):
            log(f"Cannot create V1: preset '{name}' already exists", "WARNING")
            return None
        try:
            self._get_facade().create(name, from_current=False)
            self._notify_list_changed()
            log(f"Created V1 preset '{name}' from default template", "INFO")
            return self.load_preset(name)
        except Exception as e:
            log(f"Error creating V1 default preset: {e}", "ERROR")
            return None

    def delete_preset(self, name: str) -> bool:
        active_name = self.get_active_preset_name()
        if active_name == name:
            log(f"Cannot delete active V1 preset '{name}'", "WARNING")
            return False
        try:
            self._get_facade().delete(name)
            self._notify_list_changed()
            return True
        except Exception as e:
            log(f"Error deleting V1 preset '{name}': {e}", "ERROR")
            return False

    def rename_preset(self, old_name: str, new_name: str) -> bool:
        try:
            was_selected = self.get_active_preset_name() == old_name
            self._get_facade().rename(old_name, new_name)
            if was_selected:
                self._get_store().notify_preset_switched(new_name)
            self._notify_list_changed()
            return True
        except Exception as e:
            log(f"Error renaming V1 preset '{old_name}' -> '{new_name}': {e}", "ERROR")
            return False

    def duplicate_preset(self, name: str, new_name: str) -> bool:
        try:
            self._get_facade().duplicate(name, new_name)
            self._notify_list_changed()
            return True
        except Exception as e:
            log(f"Error duplicating V1 preset '{name}' -> '{new_name}': {e}", "ERROR")
            return False

    def export_preset(self, name: str, dest_path: Path) -> bool:
        try:
            self._get_facade().export_plain_text(name, dest_path)
            return True
        except Exception as e:
            log(f"Error exporting V1 preset '{name}' to '{dest_path}': {e}", "ERROR")
            return False

    def sync_preset_to_active_file(self, preset: PresetV1) -> bool:
        """Regenerates the Zapret 1 launch config from a source preset."""
        return self._get_sync_layer().sync_preset(preset)

    @staticmethod
    def _render_template_for_preset(raw_template: str, target_name: str) -> str:
        """Rewrites # Preset header for target preset name."""
        text = (raw_template or "").replace("\r\n", "\n").replace("\r", "\n")
        lines = text.split("\n")

        header_end = 0
        for i, raw in enumerate(lines):
            stripped = raw.strip()
            if stripped and not stripped.startswith("#"):
                header_end = i
                break
        else:
            header_end = len(lines)

        header = lines[:header_end]
        body = lines[header_end:]

        out_header: list[str] = []
        saw_preset = False
        for raw in header:
            stripped = raw.strip().lower()
            if stripped.startswith("# preset:"):
                out_header.append(f"# Preset: {target_name}")
                saw_preset = True
                continue
            if stripped.startswith("# builtinversion:"):
                out_header.append(raw.rstrip("\n"))
                continue
            if stripped.startswith("# created:") or stripped.startswith("# modified:") or stripped.startswith("# iconcolor:") or stripped.startswith("# description:"):
                out_header.append(raw.rstrip("\n"))
                continue
            if stripped.startswith("#"):
                continue
            out_header.append(raw.rstrip("\n"))

        if not saw_preset:
            out_header.insert(0, f"# Preset: {target_name}")

        return "\n".join(out_header + body).rstrip("\n") + "\n"

    def reset_preset_to_default_template(
        self,
        preset_name: str,
        *,
        make_active: bool = True,
        sync_active_file: bool = True,
        emit_switched: bool = True,
        invalidate_templates: bool = True,
    ) -> bool:
        """Force-resets a preset to matching content from presets_v1_template/."""
        from .preset_defaults import (
            get_template_content_v1,
            get_default_template_content_v1,
            get_builtin_preset_content_v1,
            get_builtin_base_from_copy_name_v1,
            invalidate_templates_cache_v1,
        )

        name = (preset_name or "").strip()
        if not name:
            return False

        try:
            if not preset_exists_v1(name):
                log(f"Cannot reset V1: preset '{name}' not found", "ERROR")
                return False

            if invalidate_templates:
                try:
                    invalidate_templates_cache_v1()
                except Exception:
                    pass

            template_content = get_template_content_v1(name)
            if not template_content:
                base = get_builtin_base_from_copy_name_v1(name)
                if base:
                    template_content = get_template_content_v1(base)
            if not template_content:
                template_content = get_default_template_content_v1()
            if not template_content:
                template_content = get_builtin_preset_content_v1("Default")
            if not template_content:
                log(
                    "Cannot reset V1 preset: no templates found. "
                    "Expected at least one file in presets_v1_template/.",
                    "ERROR",
                )
                return False

            rendered_content = self._render_template_for_preset(template_content, name)

            preset_path = get_preset_path_v1(name)
            try:
                preset_path.parent.mkdir(parents=True, exist_ok=True)
                preset_path.write_text(rendered_content, encoding="utf-8")
            except PermissionError as e:
                log(f"Cannot write V1 preset file (locked?): {e}", "ERROR")
                raise
            except Exception as e:
                log(f"Error writing reset V1 preset '{name}': {e}", "ERROR")
                return False

            self.invalidate_preset_cache(name)

            do_sync = bool(sync_active_file)
            if do_sync and not make_active:
                try:
                    current_active = (self.get_active_preset_name() or "").strip().lower()
                except Exception:
                    current_active = ""
                if current_active != name.lower():
                    do_sync = False

            if make_active:
                if not self._select_source_preset(name):
                    return False

            if do_sync:
                try:
                    preset = self.load_preset(name)
                    if preset is None:
                        log(f"Cannot sync reset V1 preset '{name}': failed to reload source preset", "ERROR")
                        return False
                    if not self.sync_preset_to_active_file(preset):
                        return False
                except PermissionError as e:
                    log(f"Cannot write V1 generated launch config (locked?): {e}", "ERROR")
                    raise
                except Exception as e:
                    log(f"Error syncing reset V1 preset '{name}' to generated launch config: {e}", "ERROR")
                    return False

            if make_active:
                if emit_switched:
                    self._get_store().notify_preset_switched(name)
                    if self.on_preset_switched:
                        try:
                            self.on_preset_switched(name)
                        except Exception:
                            pass
                else:
                    try:
                        self._get_store().notify_active_name_changed()
                    except Exception:
                        pass

            return True

        except Exception as e:
            log(f"Error resetting V1 preset '{name}' to template: {e}", "ERROR")
            return False

    def reset_active_preset_to_default_template(self) -> bool:
        """Resets currently active V1 preset to its matching template."""
        active_name = (self.get_active_preset_name() or "").strip()
        if not active_name:
            return False
        return self.reset_preset_to_default_template(
            active_name,
            make_active=True,
            sync_active_file=True,
            emit_switched=True,
            invalidate_templates=True,
        )

    def reset_all_presets_to_default_templates(self) -> tuple[int, int, list[str]]:
        """Overwrites V1 presets from templates and reapplies the active one."""
        from .preset_defaults import invalidate_templates_cache_v1, overwrite_v1_templates_to_presets

        success_count = 0
        total_count = 0
        failed: list[str] = []

        try:
            try:
                invalidate_templates_cache_v1()
                success_count, total_count, failed = overwrite_v1_templates_to_presets()
            except Exception as e:
                log(f"V1 bulk reset: template overwrite error: {e}", "DEBUG")

            try:
                self.invalidate_preset_cache(None)
            except Exception:
                pass

            names = sorted(self.list_presets(), key=lambda s: s.lower())
            if not names:
                return (success_count, total_count, failed)

            name_by_key = {name.lower(): name for name in names}
            original_active = (self.get_active_preset_name() or "").strip()
            active_name = name_by_key.get(original_active.lower(), "") if original_active else ""
            if not active_name:
                active_name = name_by_key.get("default", "") or names[0]

            if active_name and not self.switch_preset(active_name, reload_dpi=False):
                log(f"V1 bulk reset: failed to re-apply selected preset '{active_name}'", "WARNING")

            return (success_count, total_count, failed)
        except Exception as e:
            log(f"V1 bulk reset error: {e}", "ERROR")
            return (success_count, total_count, failed)

    def set_strategy_selection(self, category_key: str, strategy_id: str, save_and_sync: bool = True) -> bool:
        category_key = str(category_key or "").strip().lower()
        preset = self.get_active_preset()
        if not preset:
            log("Cannot set V1 strategy: no selected preset", "WARNING")
            return False

        if category_key not in preset.categories:
            preset.categories[category_key] = CategoryConfigV1(name=category_key)

        preset.categories[category_key].strategy_id = strategy_id
        self._update_category_args_from_strategy(preset, category_key, strategy_id)
        preset.touch()

        if save_and_sync:
            return self._save_and_sync_category(preset, category_key)
        return True

    def get_category_filter_mode(self, category_key: str) -> str:
        category_key = str(category_key or "").strip().lower()
        preset = self.get_active_preset()
        if not preset:
            return "hostlist"

        category = preset.categories.get(category_key)
        if not category:
            return "hostlist"

        mode = str(getattr(category, "filter_mode", "") or "").strip().lower()
        if mode in ("hostlist", "ipset"):
            return mode
        return "hostlist"

    def update_category_filter_mode(
        self,
        category_key: str,
        filter_mode: str,
        save_and_sync: bool = True,
    ) -> bool:
        category_key = str(category_key or "").strip().lower()
        filter_mode = str(filter_mode or "").strip().lower()

        if filter_mode not in ("hostlist", "ipset"):
            log(f"Invalid V1 filter_mode: {filter_mode}", "WARNING")
            return False

        preset = self.get_active_preset()
        if not preset:
            log("Cannot update V1 filter_mode: no selected preset", "WARNING")
            return False

        if category_key not in preset.categories:
            preset.categories[category_key] = CategoryConfigV1(name=category_key)

        preset.categories[category_key].filter_mode = filter_mode
        preset.touch()

        if save_and_sync:
            return self._save_and_sync_category(preset, category_key)
        return True

    @staticmethod
    def _selection_id_from_category(cat: CategoryConfigV1) -> str:
        """Return stable selection id for UI from category config."""
        sid = str(getattr(cat, "strategy_id", "") or "").strip().lower() or "none"
        if sid == "none":
            has_args = bool((getattr(cat, "tcp_args", "") or "").strip() or (getattr(cat, "udp_args", "") or "").strip())
            if has_args:
                # Args exist but strategy id couldn't be matched -> treat as custom.
                return "custom"
        return sid

    def get_strategy_selections(self) -> dict:
        preset = self.get_active_preset()
        if not preset:
            return {}

        raw: dict[str, str] = {}
        for key, cat in (preset.categories or {}).items():
            norm_key = str(key or "").strip().lower()
            if not norm_key:
                continue
            raw[norm_key] = self._selection_id_from_category(cat)

        # If the selected preset has shared blocks with multiple hostlists in one instance,
        # parser may map only one category from that block. Keep categories visible by
        # marking additionally detected hostlist/ipset categories as custom.
        try:
            present_from_lists = self._get_sync_layer().infer_active_categories_from_launch_config()
            for key in present_from_lists:
                if raw.get(key, "none") == "none":
                    raw[key] = "custom"
        except Exception:
            pass

        return raw

    def _update_category_args_from_strategy(self, preset: PresetV1, category_key: str, strategy_id: str) -> None:
        cat = preset.categories.get(category_key)
        if not cat:
            return
        if strategy_id == "none":
            cat.tcp_args = ""
            cat.udp_args = ""
            return

        from preset_zapret2.catalog import load_categories
        from preset_zapret1.strategies_loader import load_v1_strategies

        categories = load_categories()
        category_info = categories.get(category_key) or {}

        strategies = load_v1_strategies(category_key)
        args = (strategies.get(strategy_id) or {}).get("args", "") or ""

        if args:
            protocol = (category_info.get("protocol") or "").upper()
            is_udp = any(t in protocol for t in ("UDP", "QUIC", "L7", "RAW"))
            if is_udp:
                cat.udp_args = args
                cat.tcp_args = ""
            else:
                cat.tcp_args = args
                cat.udp_args = ""

    def _save_and_sync_category(self, preset: PresetV1, category_key: str) -> bool:
        return self._get_sync_layer().sync_category_preserving_layout(preset, category_key)

    def _save_and_sync_preset(self, preset: PresetV1) -> bool:
        if preset.name and preset.name != "Current":
            save_preset_v1(preset)
            self.invalidate_preset_cache(preset.name)
        return self.sync_preset_to_active_file(preset)

    def ensure_presets_dir(self) -> Path:
        return get_presets_dir_v1()

    def get_active_preset_path(self) -> Path:
        return get_active_preset_path_v1()
