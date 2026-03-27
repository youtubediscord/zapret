# preset_zapret2/preset_manager.py
"""Mutation shell for direct_zapret2 source presets and runtime sync."""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from log import log

from .preset_model import (
    CategoryConfig,
    DEFAULT_PRESET_ICON_COLOR,
    Preset,
    SyndataSettings,
    normalize_preset_icon_color,
    validate_preset,
)
from .mode_projection import normalize_direct_zapret2_ui_mode, project_preset_for_direct_ui_mode
from .preset_storage import (
    get_preset_path,
    preset_exists,
    save_preset,
)


class PresetManager:
    """Direct mutation shell over selected source preset state for Zapret 2."""

    def __init__(
        self,
        on_preset_switched: Optional[Callable[[str], None]] = None,
        on_dpi_reload_needed: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize preset manager.

        Args:
            on_preset_switched: Callback after preset switch
            on_dpi_reload_needed: Callback to reload DPI service
        """
        self.on_preset_switched = on_preset_switched
        self.on_dpi_reload_needed = on_dpi_reload_needed

        # Cache for the selected source preset to avoid repeated file parsing
        self._active_preset_cache: Optional[Preset] = None
        self._active_preset_mtime: float = 0.0
        self._active_preset_mode: str = ""
        self._sync_layer = None

    # ========================================================================
    # LIST OPERATIONS
    # ========================================================================

    @staticmethod
    def _get_store():
        """Returns the global PresetStore singleton."""
        from .preset_store import get_preset_store
        return get_preset_store()

    def _get_sync_layer(self):
        if self._sync_layer is None:
            from .sync_layer import (
                Zapret2PresetSyncLayer,
                inject_debug_into_base_args,
                update_wf_out_ports_in_base_args,
            )

            self._sync_layer = Zapret2PresetSyncLayer(
                on_dpi_reload_needed=self.on_dpi_reload_needed,
                invalidate_cache=self._invalidate_active_preset_cache,
                inject_debug_into_base_args=inject_debug_into_base_args,
                update_wf_out_ports_in_base_args=update_wf_out_ports_in_base_args,
            )
        return self._sync_layer

    def _get_facade(self):
        from core.presets.direct_facade import DirectPresetFacade

        return DirectPresetFacade.from_launch_method("direct_zapret2")

    def list_presets(self) -> List[str]:
        """
        Lists all available preset names.

        Returns:
            List of preset names sorted alphabetically
        """
        return self._get_store().get_preset_names()

    def preset_exists(self, name: str) -> bool:
        """
        Checks if preset exists.

        Args:
            name: Preset name

        Returns:
            True if preset file exists
        """
        return self._get_store().preset_exists(name)

    def load_preset(self, name: str) -> Optional[Preset]:
        """
        Loads preset by name from the central PresetStore (in-memory).

        Args:
            name: Preset name

        Returns:
            Preset object or None if not found
        """
        return self._get_store().get_preset(name)

    def load_all_presets(self) -> List[Preset]:
        """
        Loads all presets from the central PresetStore (in-memory).

        Returns:
            List of all Preset objects, sorted by name.
        """
        store = self._get_store()
        all_presets = store.get_all_presets()
        return [all_presets[n] for n in sorted(all_presets.keys(), key=lambda s: s.lower())]

    def save_preset(self, preset: Preset) -> bool:
        """
        Saves preset to file.

        Args:
            preset: Preset to save

        Returns:
            True if saved successfully
        """
        # Validate before saving
        errors = validate_preset(preset)
        if errors:
            log(f"Preset validation failed: {errors}", "WARNING")
            # Still save but log warnings

        result = save_preset(preset)
        if result:
            self.invalidate_preset_cache(preset.name)
        return result

    # ========================================================================
    # SELECTED SOURCE PRESET OPERATIONS
    # ========================================================================

    def get_selected_source_preset_name(self) -> Optional[str]:
        """
        Gets name of the currently selected source preset.

        Returns:
            Selected source preset name or None
        """
        try:
            from core.services import get_direct_flow_coordinator

            return get_direct_flow_coordinator().get_selected_source_preset_name("direct_zapret2")
        except Exception:
            try:
                return self._get_store().get_selected_source_preset_name()
            except Exception:
                return None

    def get_active_preset_name(self) -> Optional[str]:
        """Compatibility alias for get_selected_source_preset_name()."""
        return self.get_selected_source_preset_name()

    def get_selected_source_preset(self) -> Optional[Preset]:
        """
        Loads the currently selected source preset with caching.

        Returns:
            Selected source Preset or None
        """
        current_mode = self._get_direct_ui_mode()
        # Check cache validity
        if self._active_preset_cache is not None:
            current_mtime = self._get_active_file_mtime()
            if (
                current_mtime == self._active_preset_mtime
                and current_mtime > 0
                and current_mode == self._active_preset_mode
            ):
                # Cache is valid
                return self._active_preset_cache

        name = self.get_selected_source_preset_name()
        preset = None
        if name:
            base_preset = self.load_preset(name)
            if base_preset is not None:
                preset = project_preset_for_direct_ui_mode(base_preset, current_mode)

        # Update cache
        if preset:
            self._active_preset_cache = preset
            self._active_preset_mtime = self._get_active_file_mtime()
            self._active_preset_mode = current_mode

        return preset

    def get_active_preset(self) -> Optional[Preset]:
        """Compatibility alias for get_selected_source_preset()."""
        return self.get_selected_source_preset()

    @staticmethod
    def _extract_icon_color_from_header(header: str) -> str:
        for line in (header or "").splitlines():
            match = re.match(r"#\s*(?:IconColor|PresetIconColor):\s*(.+)", line.strip(), re.IGNORECASE)
            if match:
                return normalize_preset_icon_color(match.group(1).strip())
        return DEFAULT_PRESET_ICON_COLOR

    def _get_active_file_mtime(self) -> float:
        """
        Gets modification time of the selected source preset file.

        Returns:
            mtime as float timestamp, 0.0 if file does not exist
        """
        try:
            from core.services import get_direct_flow_coordinator

            preset_path = get_direct_flow_coordinator().get_selected_source_path("direct_zapret2")
            if preset_path.exists():
                return os.path.getmtime(str(preset_path))
            return 0.0
        except Exception as e:
            log(f"Error getting selected preset mtime: {e}", "WARNING")
            return 0.0

    def _invalidate_active_preset_cache(self) -> None:
        """
        Invalidates the selected preset cache.

        Should be called after any modification to the selected source preset.
        """
        self._active_preset_cache = None
        self._active_preset_mtime = 0.0
        self._active_preset_mode = ""

    @staticmethod
    def _get_direct_ui_mode() -> str:
        try:
            from strategy_menu import get_direct_zapret2_ui_mode

            return normalize_direct_zapret2_ui_mode(get_direct_zapret2_ui_mode())
        except Exception:
            return "basic"

    def _select_source_preset(self, name: str) -> bool:
        try:
            from core.services import get_selection_service

            get_selection_service().select_preset_by_name("winws2", name)
            self._invalidate_active_preset_cache()
            return True
        except Exception as e:
            log(f"Error selecting source preset '{name}': {e}", "ERROR")
            return False

    def invalidate_preset_cache(self, name: Optional[str] = None) -> None:
        """
        Invalidates the preset cache in the central PresetStore.

        For single-preset content changes, re-reads just that preset.
        For None (full invalidation), does a full refresh.

        Args:
            name: Preset name to invalidate, or None to do a full refresh.
        """
        store = self._get_store()
        if name is None:
            store.refresh()
        else:
            store.notify_preset_saved(name)

    def _notify_list_changed(self) -> None:
        """Notifies the central store that the preset list changed (add/remove/rename)."""
        self._get_store().notify_presets_changed()

    def create_preset(self, name: str, from_current: bool = True) -> Optional[Preset]:
        """
        Creates a new preset.

        Args:
            name: Name for new preset
            from_current: If True, copy the selected source preset.
                         If False, create empty preset.

        Returns:
            Created Preset or None on error
        """
        if self.preset_exists(name):
            log(f"Cannot create: preset '{name}' already exists", "WARNING")
            return None

        try:
            self._get_facade().create(name, from_current=from_current)
            self._notify_list_changed()
            log(f"Created preset '{name}'", "INFO")
            return self.load_preset(name)
        except Exception as e:
            log(f"Error creating preset: {e}", "ERROR")
            return None

    def delete_preset(self, name: str) -> bool:
        """
        Deletes preset.

        Cannot delete the currently selected preset.

        Args:
            name: Preset name

        Returns:
            True if deleted
        """
        # Check if active
        active_name = self.get_active_preset_name()
        if active_name == name:
            log(f"Cannot delete selected preset '{name}'", "WARNING")
            return False

        try:
            self._get_facade().delete(name)
            self._notify_list_changed()
            return True
        except Exception as e:
            log(f"Error deleting preset '{name}': {e}", "ERROR")
            return False

    def rename_preset(self, old_name: str, new_name: str) -> bool:
        """
        Renames preset.

        Updates the selected preset if the renamed preset was selected.

        Args:
            old_name: Current name
            new_name: New name

        Returns:
            True if renamed
        """
        try:
            was_selected = self.get_active_preset_name() == old_name
            self._get_facade().rename(old_name, new_name)
            if was_selected:
                self._get_store().notify_preset_switched(new_name)
            self._notify_list_changed()
            return True
        except Exception as e:
            log(f"Error renaming preset '{old_name}' -> '{new_name}': {e}", "ERROR")
            return False

    def duplicate_preset(self, name: str, new_name: str) -> bool:
        """
        Creates a copy of preset.

        Args:
            name: Source preset name
            new_name: Name for the copy

        Returns:
            True if duplicated
        """
        try:
            self._get_facade().duplicate(name, new_name)
            self._notify_list_changed()
            return True
        except Exception as e:
            log(f"Error duplicating preset '{name}' -> '{new_name}': {e}", "ERROR")
            return False

    # ========================================================================
    # IMPORT/EXPORT OPERATIONS
    # ========================================================================

    def export_preset(self, name: str, dest_path: Path) -> bool:
        """
        Exports preset to external file.

        Args:
            name: Preset name
            dest_path: Destination path

        Returns:
            True if exported
        """
        try:
            self._get_facade().export_plain_text(name, dest_path)
            return True
        except Exception as e:
            log(f"Error exporting preset '{name}' to '{dest_path}': {e}", "ERROR")
            return False

    def import_preset(self, src_path: Path, name: Optional[str] = None) -> bool:
        """
        Imports preset from external file.

        Copies the file to both presets_v2_template/ (as reset source)
        and presets/ (as editable copy).

        Args:
            src_path: Source file path
            name: Optional name (uses filename if None)

        Returns:
            True if imported
        """
        try:
            actual_name = name if name else Path(src_path).stem
            self._get_facade().import_from_file(src_path, actual_name)
            self._notify_list_changed()
            return True
        except Exception as e:
            log(f"Error importing preset '{src_path}' as '{name}': {e}", "ERROR")
            return False

    def sync_preset_to_active_file(self, preset: Preset, changed_category: str = None) -> bool:
        """
        Regenerates the generated launch config from a source preset.

        Use this when editing the selected source preset without re-selecting it.
        Triggers DPI reload.

        When changed_category is provided and preset has raw blocks from file,
        uses RAW BLOCK PRESERVATION: only the changed category's block(s) are
        regenerated, all other blocks are written back as-is (lossless round-trip).

        Args:
            preset: Preset to write
            changed_category: Category key that was changed (None = full regeneration)

        Returns:
            True if successful
        """
        return self._get_sync_layer().sync_preset(preset, changed_category=changed_category)

    # ========================================================================
    # CATEGORY SETTINGS OPERATIONS
    # ========================================================================

    @staticmethod
    def _normalize_syndata_protocol(protocol: str) -> str:
        proto = (protocol or "").strip().lower()
        if proto in ("udp", "quic", "l7", "raw"):
            return "udp"
        return "tcp"

    def get_category_syndata(self, category_key: str, protocol: str = "tcp") -> SyndataSettings:
        """
        Gets syndata settings for a category from the selected source preset.

        Args:
            category_key: Category name (e.g., "youtube", "discord")
            protocol: "tcp" or "udp" (udp also covers QUIC/L7)

        Returns:
            SyndataSettings for the category (defaults if not found)
        """
        preset = self.get_active_preset()
        if not preset:
            return SyndataSettings.get_defaults() if self._normalize_syndata_protocol(protocol) == "tcp" else SyndataSettings.get_defaults_udp()

        category = preset.categories.get(category_key)
        if not category:
            return SyndataSettings.get_defaults() if self._normalize_syndata_protocol(protocol) == "tcp" else SyndataSettings.get_defaults_udp()

        return category.syndata_tcp if self._normalize_syndata_protocol(protocol) == "tcp" else category.syndata_udp

    def update_category_syndata(
        self,
        category_key: str,
        syndata: SyndataSettings,
        save_and_sync: bool = True,
        protocol: str = "tcp",
    ) -> bool:
        """
        Updates syndata settings for a category.

        Args:
            category_key: Category name
            syndata: New syndata settings
            save_and_sync: If True, save preset and sync the generated launch config
            protocol: "tcp" or "udp" (udp also covers QUIC/L7)

        Returns:
            True if successful
        """
        preset = self.get_active_preset()
        if not preset:
            log(f"Cannot update syndata: no selected preset", "WARNING")
            return False

        # Create category if not exists
        if category_key not in preset.categories:
            preset.categories[category_key] = self._create_category_with_defaults(category_key)

        try:
            syndata_value = SyndataSettings.from_dict(syndata.to_dict())
        except Exception:
            syndata_value = syndata

        protocol_key = self._normalize_syndata_protocol(protocol)
        if protocol_key == "udp":
            syndata_value.enabled = False
            syndata_value.send_enabled = False
            preset.categories[category_key].syndata_udp = syndata_value
        else:
            preset.categories[category_key].syndata_tcp = syndata_value
        preset.touch()

        if save_and_sync:
            return self._save_and_sync_preset(preset)

        return True

    def get_category_filter_mode(self, category_key: str) -> str:
        """
        Gets filter mode for a category.

        Args:
            category_key: Category name

        Returns:
            "hostlist" or "ipset"
        """
        preset = self.get_active_preset()
        if not preset:
            return "hostlist"

        category = preset.categories.get(category_key)
        if not category:
            return "hostlist"

        return category.filter_mode

    def update_category_filter_mode(
        self,
        category_key: str,
        filter_mode: str,
        save_and_sync: bool = True
    ) -> bool:
        """
        Updates filter mode for a category.

        Args:
            category_key: Category name
            filter_mode: "hostlist" or "ipset"
            save_and_sync: If True, save preset and sync the generated launch config

        Returns:
            True if successful
        """
        if filter_mode not in ("hostlist", "ipset"):
            log(f"Invalid filter_mode: {filter_mode}", "WARNING")
            return False

        preset = self.get_active_preset()
        if not preset:
            log(f"Cannot update filter_mode: no selected preset", "WARNING")
            return False

        # Create category if not exists
        if category_key not in preset.categories:
            preset.categories[category_key] = self._create_category_with_defaults(category_key)

        preset.categories[category_key].filter_mode = filter_mode
        preset.touch()

        if save_and_sync:
            return self._save_and_sync_preset(preset)

        return True

    def get_category_sort_order(self, category_key: str) -> str:
        """
        Gets sort order for a category.

        Args:
            category_key: Category name

        Returns:
            "default", "name_asc", or "name_desc"
        """
        preset = self.get_active_preset()
        if not preset:
            return "default"

        category = preset.categories.get(category_key)
        if not category:
            return "default"

        return category.sort_order

    def update_category_sort_order(
        self,
        category_key: str,
        sort_order: str,
        save_and_sync: bool = True
    ) -> bool:
        """
        Updates sort order for a category.

        Args:
            category_key: Category name
            sort_order: "default", "name_asc", or "name_desc"
            save_and_sync: If True, save preset and sync the generated launch config

        Returns:
            True if successful
        """
        if sort_order not in ("default", "name_asc", "name_desc"):
            log(f"Invalid sort_order: {sort_order}", "WARNING")
            return False

        preset = self.get_active_preset()
        if not preset:
            log(f"Cannot update sort_order: no selected preset", "WARNING")
            return False

        # Create category if not exists
        if category_key not in preset.categories:
            preset.categories[category_key] = self._create_category_with_defaults(category_key)

        preset.categories[category_key].sort_order = sort_order
        preset.touch()

        if save_and_sync:
            return self._save_and_sync_preset(preset)

        return True

    def reset_category_settings(self, category_key: str) -> bool:
        """
        Resets category settings to defaults from the selected preset template.

        Args:
            category_key: Category name

        Returns:
            True if successful
        """
        preset = self.get_active_preset()
        if not preset:
            return False

        # Ensure category exists so UI can reset even if it wasn't enabled before.
        if category_key not in preset.categories:
            preset.categories[category_key] = self._create_category_with_defaults(category_key)

        cat = preset.categories[category_key]

        from .preset_defaults import (
            get_default_category_settings,
            get_category_default_filter_mode,
            get_category_default_syndata,
            get_template_content,
            get_default_template_content,
            get_builtin_base_from_copy_name,
            invalidate_templates_cache,
        )
        from .strategy_inference import infer_strategy_id_from_args
        from .txt_preset_parser import parse_preset_content

        try:
            from strategy_menu.strategies_registry import get_current_strategy_set
            current_strategy_set = get_current_strategy_set()
        except Exception:
            current_strategy_set = None

        default_filter_mode = get_category_default_filter_mode(category_key)
        default_settings = get_default_category_settings().get(category_key) or {}

        # Prefer defaults from the selected preset's matching template.
        active_preset_name = (self.get_active_preset_name() or preset.name or "").strip()
        category_key_l = str(category_key or "").strip().lower()
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
                    if not block_cat or block_cat != category_key_l:
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
        except Exception as e:
            log(f"Failed to resolve template defaults for category '{category_key}': {e}", "DEBUG")

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
            tcp_defaults = get_category_default_syndata(category_key, protocol="tcp")
            udp_defaults = get_category_default_syndata(category_key, protocol="udp")

        # Reset non-strategy state.
        cat.syndata_tcp = SyndataSettings.from_dict(tcp_defaults)
        cat.syndata_udp = SyndataSettings.from_dict(udp_defaults)
        cat.filter_mode = default_filter_mode
        cat.sort_order = "default"

        # Reset args/ports from template when available, otherwise keep
        # selection but normalize args from strategy_id.
        if default_settings:
            cat.tcp_enabled = bool(default_settings.get("tcp_enabled", False))
            cat.udp_enabled = bool(default_settings.get("udp_enabled", False))
            cat.tcp_port = str(default_settings.get("tcp_port") or cat.tcp_port or "443")
            cat.udp_port = str(default_settings.get("udp_port") or cat.udp_port or "443")
            cat.tcp_args = str(default_settings.get("tcp_args") or "").strip()
            cat.udp_args = str(default_settings.get("udp_args") or "").strip()

            # Infer strategy_id for UI highlight, if possible.
            inferred = "none"
            if cat.tcp_args:
                inferred = infer_strategy_id_from_args(
                    category_key=category_key,
                    args=cat.tcp_args,
                    protocol="tcp",
                    strategy_set=current_strategy_set,
                )
            if inferred == "none" and cat.udp_args:
                inferred = infer_strategy_id_from_args(
                    category_key=category_key,
                    args=cat.udp_args,
                    protocol="udp",
                    strategy_set=current_strategy_set,
                )
            cat.strategy_id = inferred or "none"
        else:
            # Unknown category in template: keep current strategy_id but reset advanced settings.
            if cat.strategy_id and cat.strategy_id != "none":
                self._update_category_args_from_strategy(preset, category_key, cat.strategy_id)
            else:
                cat.tcp_args = ""
                cat.udp_args = ""
                cat.strategy_id = "none"
        preset.touch()

        return self._save_and_sync_preset(preset)

    def reset_active_preset_to_default_template(self) -> bool:
        """
        Global reset: replace the selected preset content with a built-in template and regenerate the launch config.

        Does not depend on preset_zapret2/default.txt existing on disk.
        """
        from .preset_defaults import (
            get_template_content,
            get_default_template_content,
            get_builtin_base_from_copy_name,
            invalidate_templates_cache,
        )
        from .txt_preset_parser import parse_preset_content
        from .strategy_inference import infer_strategy_id_from_args

        try:
            from strategy_menu.strategies_registry import get_current_strategy_set
            current_strategy_set = get_current_strategy_set()
        except Exception:
            current_strategy_set = None

        preset_name = self.get_active_preset_name() or "Current"

        try:
            try:
                invalidate_templates_cache()
            except Exception:
                pass

            # Try matching template for this preset name first
            template_content = get_template_content(preset_name)
            if not template_content:
                # Try base name for copies (e.g. "Default (копия)" -> "Default")
                base = get_builtin_base_from_copy_name(preset_name)
                if base:
                    template_content = get_template_content(base)
            if not template_content:
                template_content = get_default_template_content()
            if not template_content:
                log(
                    "Cannot reset selected preset: no preset templates found. "
                    "Expected at least one file in presets_v2_template/.",
                    "ERROR",
                )
                return False

            data = parse_preset_content(template_content)

            # Build Preset model, then reuse sync logic to generate a proper launch config
            # (including absolute list paths and normalized base filters).
            preset = Preset(name=preset_name, base_args=data.base_args)
            existing = self.load_preset(preset_name) if preset_exists(preset_name) else None
            if existing:
                preset.created = existing.created
                preset.description = existing.description
                preset.icon_color = normalize_preset_icon_color(existing.icon_color)
            else:
                preset.icon_color = self._extract_icon_color_from_header(data.raw_header)

            for block in data.categories:
                cat_name = block.category
                if cat_name not in preset.categories:
                    raw_filter_file = getattr(block, "filter_file", "") or ""
                    if raw_filter_file and "/" not in raw_filter_file and "\\" not in raw_filter_file:
                        raw_filter_file = f"lists/{raw_filter_file}"
                    preset.categories[cat_name] = CategoryConfig(
                        name=cat_name,
                        filter_mode=block.filter_mode or "hostlist",
                        filter_file=raw_filter_file,
                        syndata_tcp=SyndataSettings.get_defaults(),
                        syndata_udp=SyndataSettings.get_defaults_udp(),
                    )

                cat = preset.categories[cat_name]
                cat.filter_mode = block.filter_mode or cat.filter_mode or "hostlist"

                if block.protocol == "tcp":
                    cat.tcp_enabled = True
                    cat.tcp_port = block.port
                    cat.tcp_args = (block.strategy_args or "").strip()
                elif block.protocol == "udp":
                    cat.udp_enabled = True
                    cat.udp_port = block.port
                    cat.udp_args = (block.strategy_args or "").strip()

                # Prefer explicit overrides from the template block if present.
                if getattr(block, "syndata_dict", None):
                    if block.protocol == "tcp":
                        base = cat.syndata_tcp.to_dict()
                        base.update(block.syndata_dict or {})  # type: ignore[arg-type]
                        cat.syndata_tcp = SyndataSettings.from_dict(base)
                    elif block.protocol == "udp":
                        base = cat.syndata_udp.to_dict()
                        base.update(block.syndata_dict or {})  # type: ignore[arg-type]
                        cat.syndata_udp = SyndataSettings.from_dict(base)

            for cat_name, cat in preset.categories.items():
                inferred = "none"
                if cat.tcp_args:
                    inferred = infer_strategy_id_from_args(
                        category_key=cat_name,
                        args=cat.tcp_args,
                        protocol="tcp",
                        strategy_set=current_strategy_set,
                    )
                if inferred == "none" and cat.udp_args:
                    inferred = infer_strategy_id_from_args(
                        category_key=cat_name,
                        args=cat.udp_args,
                        protocol="udp",
                        strategy_set=current_strategy_set,
                    )
                cat.strategy_id = inferred or "none"

            # Persist reset into the preset file.
            if preset.name and preset.name != "Current" and preset_exists(preset.name):
                save_preset(preset)
                self.invalidate_preset_cache(preset.name)

            return self.sync_preset_to_active_file(preset)
        except Exception as e:
            log(f"Error resetting selected preset to built-in template: {e}", "ERROR")
            return False

    def reset_all_presets_to_default_templates(self) -> tuple[int, int, list[str]]:
        """Overwrites V2 presets from templates and reapplies the active one."""
        from .preset_defaults import invalidate_templates_cache, overwrite_templates_to_presets

        success_count = 0
        total_count = 0
        failed: list[str] = []

        try:
            try:
                invalidate_templates_cache()
                success_count, total_count, failed = overwrite_templates_to_presets()
            except Exception as e:
                log(f"Bulk reset: template overwrite error: {e}", "DEBUG")

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

            if active_name:
                try:
                    from core.services import get_direct_flow_coordinator

                    profile = get_direct_flow_coordinator().select_preset("direct_zapret2", active_name)
                    self._invalidate_active_preset_cache()
                    self._get_store().notify_preset_switched(profile.preset_name)
                    if self.on_preset_switched:
                        try:
                            self.on_preset_switched(profile.preset_name)
                        except Exception:
                            pass
                except Exception as e:
                    log(f"Bulk reset: failed to re-apply selected preset '{active_name}': {e}", "WARNING")

            return (success_count, total_count, failed)
        except Exception as e:
            log(f"Bulk reset error: {e}", "ERROR")
            return (success_count, total_count, failed)

    def reset_preset_to_default_template(
        self,
        preset_name: str,
        *,
        make_active: bool = True,
        sync_active_file: bool = True,
        emit_switched: bool = True,
        invalidate_templates: bool = True,
    ) -> bool:
        """
        Resets a preset by force-copying its matching template content.

        By default, also selects it and regenerates the launch config.

        First tries to find a template matching the preset name in presets_v2_template/,
        then falls back to the default template.

        Overwrites:
        - presets/{preset_name}.txt
        - generated launch config (if sync_active_file=True)
        """
        from .preset_defaults import (
            get_template_content,
            get_default_template_content,
            get_builtin_base_from_copy_name,
            invalidate_templates_cache,
        )

        name = (preset_name or "").strip()
        if not name:
            return False

        def _render_template_for_preset(raw_template: str, target_name: str) -> str:
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

        try:
            if not preset_exists(name):
                log(f"Cannot reset: preset '{name}' not found", "ERROR")
                return False

            if invalidate_templates:
                try:
                    invalidate_templates_cache()
                except Exception:
                    pass

            # Try matching template first, then fall back to default
            template_content = get_template_content(name)
            if not template_content:
                # Try base name for duplicates (e.g. "Default (копия 2)" -> "Default")
                base = get_builtin_base_from_copy_name(name)
                if base:
                    template_content = get_template_content(base)
            if not template_content:
                template_content = get_default_template_content()
            if not template_content:
                log(
                    "Cannot reset preset: no preset templates found. "
                    "Expected at least one file in presets_v2_template/.",
                    "ERROR",
                )
                return False
            rendered_content = _render_template_for_preset(template_content, name)

            # Persist exact template reset into the preset file (force, regardless of version).
            preset_path = get_preset_path(name)
            try:
                preset_path.parent.mkdir(parents=True, exist_ok=True)
                preset_path.write_text(rendered_content, encoding="utf-8")
            except PermissionError as e:
                log(f"Cannot write preset file (locked by winws2?): {e}", "ERROR")
                raise
            except Exception as e:
                log(f"Error writing reset preset '{name}': {e}", "ERROR")
                return False

            self.invalidate_preset_cache(name)

            # Avoid producing a mismatched selected-preset launch config.
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

            # Sync generated launch config through the regular preset sync path.
            if do_sync:
                try:
                    preset = self.load_preset(name)
                    if preset is None:
                        log(f"Cannot sync reset preset '{name}': failed to reload source preset", "ERROR")
                        return False
                    if not self.sync_preset_to_active_file(preset):
                        return False
                except PermissionError as e:
                    log(f"Cannot write generated launch config (locked by winws2?): {e}", "ERROR")
                    raise
                except Exception as e:
                    log(f"Error syncing reset preset '{name}' to generated launch config: {e}", "ERROR")
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
                    # Keep store active name in sync without emitting preset_switched.
                    try:
                        self._get_store().notify_active_name_changed()
                    except Exception:
                        pass

            return True

        except Exception as e:
            log(f"Error resetting preset '{name}' to Default template: {e}", "ERROR")
            return False

    def _save_and_sync_preset(self, preset: Preset, changed_category: str = None) -> bool:
        """
        Saves preset to file and syncs the generated launch config.

        Args:
            preset: Preset to save
            changed_category: Category key that was changed (for raw block preservation)

        Returns:
            True if successful
        """
        # Normalize/update wf-*-out before persisting anywhere.
        from .sync_layer import update_wf_out_ports_in_base_args

        preset.base_args = update_wf_out_ports_in_base_args(preset)

        # Save to presets folder if it has a name.
        if preset.name and preset.name != "Current":
            save_preset(preset)
            self.invalidate_preset_cache(preset.name)

        # Then sync the generated launch config (triggers DPI reload via callback)
        # Note: sync_preset_to_active_file() already invalidates active cache
        return self.sync_preset_to_active_file(preset, changed_category=changed_category)

    def _create_category_with_defaults(self, category_key: str) -> CategoryConfig:
        """
        Creates a new CategoryConfig with defaults from DEFAULT_PRESET_CONTENT.

        If category exists in DEFAULT_PRESET_CONTENT (youtube, discord, etc.),
        uses its specific settings (syndata, filter_mode).
        Otherwise, uses fallback defaults.

        Args:
            category_key: Category name (e.g., "youtube", "discord")

        Returns:
            CategoryConfig with proper defaults
        """
        category_key = str(category_key or "").strip().lower()
        from .preset_defaults import (
            get_category_default_syndata,
            get_category_default_filter_mode
        )

        # Get defaults from DEFAULT_PRESET_CONTENT
        syndata_tcp = SyndataSettings.from_dict(get_category_default_syndata(category_key, protocol="tcp"))
        syndata_udp = SyndataSettings.from_dict(get_category_default_syndata(category_key, protocol="udp"))
        filter_mode = get_category_default_filter_mode(category_key)

        return CategoryConfig(
            name=category_key,
            syndata_tcp=syndata_tcp,
            syndata_udp=syndata_udp,
            filter_mode=filter_mode
        )

    # ========================================================================
    # STRATEGY SELECTION OPERATIONS
    # ========================================================================

    def get_strategy_selections(self) -> dict:
        """
        Gets strategy selections from the selected source preset.

        Returns:
            Dict of category_key -> strategy_id
        """
        preset = self.get_active_preset()
        if not preset:
            return {}

        selections = {}
        for cat_key, cat_config in preset.categories.items():
            selections[cat_key] = cat_config.strategy_id
        return selections

    def set_strategy_selection(
        self,
        category_key: str,
        strategy_id: str,
        save_and_sync: bool = True
    ) -> bool:
        """
        Sets strategy selection for a category.

        Args:
            category_key: Category name (e.g., "youtube")
            strategy_id: Strategy ID (e.g., "youtube_tcp_split") or "none"
            save_and_sync: If True, save preset and sync the generated launch config

        Returns:
            True if successful
        """
        category_key = str(category_key or "").strip().lower()
        preset = self.get_active_preset()
        if not preset:
            log(f"Cannot set strategy: no selected preset", "WARNING")
            return False

        # Create category if not exists
        if category_key not in preset.categories:
            preset.categories[category_key] = self._create_category_with_defaults(category_key)

        preset.categories[category_key].strategy_id = strategy_id

        # Update tcp_args/udp_args based on strategy_id
        self._update_category_args_from_strategy(preset, category_key, strategy_id)

        preset.touch()

        if save_and_sync:
            return self._save_and_sync_preset(preset, changed_category=category_key)

        return True

    def _update_category_args_from_strategy(
        self,
        preset: Preset,
        category_key: str,
        strategy_id: str
    ) -> None:
        """
        Updates tcp_args/udp_args based on strategy_id.

        Args:
            preset: Preset to update
            category_key: Category name
            strategy_id: Strategy ID
        """
        cat = preset.categories.get(category_key)
        if not cat:
            return

        if strategy_id == "none":
            # Clear args when strategy is disabled
            cat.tcp_args = ""
            cat.udp_args = ""
            cat.tcp_args_raw = ""
            cat.udp_args_raw = ""
            return

        from .catalog import load_categories, load_strategies

        categories = load_categories()
        category_info = categories.get(category_key) or {}
        strategy_type = (category_info.get("strategy_type") or "tcp").strip() or "tcp"

        try:
            # Keep strategy args resolution in sync with UI-selected strategy set
            # (direct_zapret2 Basic/Advanced load from %APPDATA%\zapret\direct_zapret2\*_strategies\*.txt).
            from strategy_menu.strategies_registry import get_current_strategy_set
            strategy_set = get_current_strategy_set()
        except Exception:
            strategy_set = None

        strategies = load_strategies(strategy_type, strategy_set=strategy_set)
        args = (strategies.get(strategy_id) or {}).get("args", "") or ""

        # TCP presets may include strategies from tcp_fake.txt (multi-phase UI).
        # Keep selection working by falling back to that catalog file.
        if not args and strategy_type == "tcp":
            try:
                # tcp_fake is a special catalog used by the multi-phase TCP UI.
                # In advanced mode load from advanced_strategies; otherwise keep legacy fallback.
                fake_strategy_set = "advanced" if strategy_set == "advanced" else None
                fake_strategies = load_strategies("tcp_fake", strategy_set=fake_strategy_set)
                args = (fake_strategies.get(strategy_id) or {}).get("args", "") or ""
            except Exception:
                args = args or ""

        from .block_semantics import (
            apply_structured_block_overrides_to_category,
            reset_structured_advanced_state,
        )
        from .txt_preset_parser import extract_strategy_args

        if args:
            protocol = (category_info.get("protocol") or "").upper()
            is_udp = any(t in protocol for t in ("UDP", "QUIC", "L7", "RAW"))
            
            # If we are in 'advanced', we extract syndata properties so the UI sliders map correctly.
            # If 'basic', we shouldn't map them; just leave them raw in tcp_args.
            if strategy_set == "advanced":
                pure_strategy_args = extract_strategy_args(args, category_key=category_key)
                
                if is_udp:
                    cat.udp_args = pure_strategy_args
                    cat.udp_args_raw = args
                    cat.tcp_args = ""
                    cat.tcp_args_raw = ""
                    apply_structured_block_overrides_to_category(cat, args, protocol="udp")
                else:
                    cat.tcp_args = pure_strategy_args
                    cat.tcp_args_raw = args
                    cat.udp_args = ""
                    cat.udp_args_raw = ""
                    apply_structured_block_overrides_to_category(cat, args, protocol="tcp")
            else:
                # Basic mode: keep the strategy exact strings as they are in the file.
                if is_udp:
                    cat.udp_args = args
                    cat.udp_args_raw = args
                    cat.tcp_args = ""
                    cat.tcp_args_raw = ""
                else:
                    cat.tcp_args = args
                    cat.tcp_args_raw = args
                    cat.udp_args = ""
                    cat.udp_args_raw = ""

                # Keep raw strategy text authoritative in basic mode.
                reset_structured_advanced_state(cat)

    def set_strategy_selections(
        self,
        selections: dict,
        save_and_sync: bool = True
    ) -> bool:
        """
        Sets multiple strategy selections at once.

        Args:
            selections: Dict of category_key -> strategy_id
            save_and_sync: If True, save preset and sync the generated launch config

        Returns:
            True if successful
        """
        preset = self.get_active_preset()
        if not preset:
            log(f"Cannot set strategies: no selected preset", "WARNING")
            return False

        for cat_key, strategy_id in (selections or {}).items():
            cat_key = str(cat_key or "").strip().lower()
            if not cat_key:
                continue
            if cat_key not in preset.categories:
                preset.categories[cat_key] = self._create_category_with_defaults(cat_key)
            preset.categories[cat_key].strategy_id = strategy_id
            # Update args from strategy_id
            self._update_category_args_from_strategy(preset, cat_key, strategy_id)

        preset.touch()

        if save_and_sync:
            return self._save_and_sync_preset(preset)

        return True

    def reset_strategy_selections_to_defaults(self, save_and_sync: bool = True) -> bool:
        """
        Resets all strategy selections to defaults from categories.txt.

        Returns:
            True if successful
        """
        from .catalog import load_categories

        preset = self.get_active_preset()
        if not preset:
            log(f"Cannot reset strategies: no selected preset", "WARNING")
            return False

        categories = load_categories()
        defaults = {
            key: (info.get("default_strategy") or "none")
            for key, info in categories.items()
        }

        for cat_key, default_strategy in defaults.items():
            if cat_key not in preset.categories:
                preset.categories[cat_key] = self._create_category_with_defaults(cat_key)
            preset.categories[cat_key].strategy_id = default_strategy
            # Update args from strategy_id
            self._update_category_args_from_strategy(preset, cat_key, default_strategy)

        preset.touch()

        if save_and_sync:
            return self._save_and_sync_preset(preset)

        return True

    def clear_all_strategy_selections(self, save_and_sync: bool = True) -> bool:
        """
        Sets all strategy selections to "none".

        Returns:
            True if successful
        """
        from .catalog import load_categories

        preset = self.get_active_preset()
        if not preset:
            log(f"Cannot clear strategies: no selected preset", "WARNING")
            return False

        for cat_key in load_categories().keys():
            if cat_key not in preset.categories:
                preset.categories[cat_key] = self._create_category_with_defaults(cat_key)
            preset.categories[cat_key].strategy_id = "none"
            # Clear args when strategy is "none"
            preset.categories[cat_key].tcp_args = ""
            preset.categories[cat_key].udp_args = ""

        preset.touch()

        if save_and_sync:
            return self._save_and_sync_preset(preset)

        return True
