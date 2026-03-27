from __future__ import annotations

# presets/preset_storage.py
"""Storage layer for preset system.

Handles reading/writing preset files to disk.

Presets are stored in a stable per-user directory (Windows):
  %APPDATA%\\zapret\\presets_v2

This avoids reliance on the installation folder location.
Selected source preset state is managed by the core selection service.
"""
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, TYPE_CHECKING

from log import log
from .preset_model import DEFAULT_PRESET_ICON_COLOR, normalize_preset_icon_color

if TYPE_CHECKING:
    from .preset_model import Preset

# Lazy imports to avoid circular dependencies
# NOTE: APP_CORE_PATH is where the app is installed / located (where Zapret.exe lives).
_APP_CORE_PATH: Optional[str] = None
_PRESETS_ROOT_PATH: Optional[str] = None
_MAIN_DIRECTORY: Optional[str] = None

def _core_engine_id() -> str:
    return "winws2"


def _core_paths():
    from core.services import get_app_paths

    return get_app_paths().engine_paths(_core_engine_id()).ensure_directories()


def _get_app_core_path() -> str:
    """Lazily gets the app core path (APP_CORE_PATH) to avoid import cycles."""
    global _APP_CORE_PATH
    if _APP_CORE_PATH is None:
        from config import APP_CORE_PATH

        _APP_CORE_PATH = APP_CORE_PATH
    return _APP_CORE_PATH


def _get_presets_root_path() -> str:
    """Returns the stable presets root (prefer %APPDATA%\\zapret\\presets_v2)."""
    global _PRESETS_ROOT_PATH
    if _PRESETS_ROOT_PATH is None:
        try:
            from config import get_zapret_presets_v2_dir

            p = (get_zapret_presets_v2_dir() or "").strip()
            _PRESETS_ROOT_PATH = p
        except Exception:
            _PRESETS_ROOT_PATH = ""

        if not _PRESETS_ROOT_PATH:
            # Fallback for non-Windows/dev environments.
            _PRESETS_ROOT_PATH = str(Path(_get_app_core_path()) / "presets_v2")
    return _PRESETS_ROOT_PATH


def _get_main_directory() -> str:
    """Lazily gets MAIN_DIRECTORY to avoid import cycles."""
    global _MAIN_DIRECTORY
    if _MAIN_DIRECTORY is None:
        from config import MAIN_DIRECTORY
        _MAIN_DIRECTORY = MAIN_DIRECTORY
    return _MAIN_DIRECTORY

# ============================================================================
# PATH FUNCTIONS
# ============================================================================

def get_presets_dir() -> Path:
    """
    Returns path to presets directory.

    Creates directory if it doesn't exist.

    Returns:
        Path to %APPDATA%/zapret/presets_v2/
    """
    presets_dir = Path(_get_presets_root_path())
    presets_dir.mkdir(parents=True, exist_ok=True)
    return presets_dir


def get_preset_path(name: str) -> Path:
    """
    Returns path to a specific preset file.

    Args:
        name: Preset name (without .txt extension)

    Returns:
        Path to presets/{name}.txt
    """
    # Sanitize name (remove dangerous characters)
    safe_name = _sanitize_filename(name)
    return get_presets_dir() / f"{safe_name}.txt"


def get_runtime_config_path() -> Path:
    """
    Returns path to the generated runtime config for direct_zapret2.

    Returns:
        Path to runtime effective config for winws2
    """
    return _core_paths().effective_config_path


def get_active_preset_path() -> Path:
    """Compatibility alias for get_runtime_config_path()."""
    return get_runtime_config_path()


def get_user_settings_path() -> Path:
    """
    Returns path to user settings file.

    This stores user-specific settings related to preset UX.

    Returns:
        Path to %APPDATA%/zapret/presets_v2/user_settings.json
    """
    return get_presets_dir() / "user_settings.json"


def _sanitize_filename(name: str) -> str:
    """
    Sanitizes filename by removing dangerous characters.

    Args:
        name: Original filename

    Returns:
        Safe filename
    """
    # Remove path separators and other dangerous chars
    dangerous = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\0']
    safe_name = name
    for char in dangerous:
        safe_name = safe_name.replace(char, '_')
    # Limit length
    return safe_name[:100]


# ============================================================================
# LIST OPERATIONS
# ============================================================================

def list_presets() -> List[str]:
    """
    Lists all available preset names.

    Returns:
        List of preset names (without .txt extension), sorted alphabetically.
    """
    presets_dir = get_presets_dir()

    presets: set[str] = set()

    if presets_dir.exists():
        for f in presets_dir.glob("*.txt"):
            if f.is_file():
                # Do not treat the active runtime file as a user preset.
                if f.stem.lower() == "preset-zapret2":
                    continue
                presets.add(f.stem)

    return sorted(presets, key=lambda s: s.lower())


def preset_exists(name: str) -> bool:
    """
    Checks if preset with given name exists.

    Args:
        name: Preset name

    Returns:
        True if preset file exists
    """
    return get_preset_path(name).exists()


# ============================================================================
# LOAD/SAVE OPERATIONS
# ============================================================================

def load_preset(name: str) -> Optional[Preset]:
    """
    Loads preset from file.

    Args:
        name: Preset name

    Returns:
        Preset object or None if not found
    """
    from .block_semantics import (
        SEMANTIC_STATUS_STRUCTURED_SUPPORTED,
        analyze_block_semantics,
        extract_structured_out_range,
        extract_structured_send,
        extract_structured_syndata,
    )
    from .preset_model import Preset, CategoryConfig, SyndataSettings
    from .txt_preset_parser import (
        PresetData,
        extract_strategy_args_preserving_helpers,
        parse_preset_file,
    )

    preset_path = get_preset_path(name)

    if not preset_path.exists():
        log(f"Preset not found: {preset_path}", "WARNING")
        return None

    data: PresetData = parse_preset_file(preset_path)

    try:
        # Convert to Preset model
        preset = Preset(
            name=data.name if data.name != "Unnamed" else name,
            base_args=data.base_args,
        )

        # Parse metadata from raw_header
        preset.created, preset.modified, preset.description, preset.icon_color = _parse_metadata_from_header(data.raw_header)

        # Convert category blocks to CategoryConfig
        # Also track full block args (filter-stripped but syndata/send-inclusive) for inference.
        # This is needed so basic-mode strategies that embed syndata/send in their args
        # are correctly identified on reload (block.strategy_args strips those lines).
        _full_args_for_inference: dict = {}  # cat_name -> (tcp_full, udp_full)

        for block in data.categories:
            cat_name = block.category

            # Store raw block text for lossless round-trip save.
            # Multiple CategoryBlocks can share the same raw_args (e.g., a block
            # with multiple --hostlist= lines creates one CategoryBlock per list).
            # We deduplicate by raw_text to avoid writing the same --new block
            # multiple times when saving.
            raw_text = getattr(block, "raw_args", "") or getattr(block, "args", "")
            # Check if this exact raw_text was already stored (shared block)
            already_stored = any(rt == raw_text for _, _, rt in preset._raw_blocks)
            if already_stored:
                # Add this category to the existing entry's category set
                for idx, (cats, proto, rt) in enumerate(preset._raw_blocks):
                    if rt == raw_text:
                        cats.add(cat_name)
                        break
            else:
                preset._raw_blocks.append(({cat_name}, block.protocol, raw_text))

            # Get or create category config
            if cat_name not in preset.categories:
                # Normalize filter_file: ensure it has a relative path prefix
                raw_filter_file = getattr(block, "filter_file", "") or ""
                if raw_filter_file and "/" not in raw_filter_file and "\\" not in raw_filter_file:
                    raw_filter_file = f"lists/{raw_filter_file}"
                preset.categories[cat_name] = CategoryConfig(
                    name=cat_name,
                    filter_mode=block.filter_mode,
                    filter_file=raw_filter_file,
                )

            cat = preset.categories[cat_name]
            raw_strategy_args = extract_strategy_args_preserving_helpers(
                block.args or "",
                category_key=cat_name,
                filter_mode=block.filter_mode,
            )

            # Restore structured advanced settings only when the semantic layer says
            # the block is structurally editable. Raw-only and invalid tokens stay
            # in raw strategy_args and must not be partially hydrated.
            block_text_for_semantics = str(raw_text or getattr(block, "args", "") or "")
            block_semantics = analyze_block_semantics(block_text_for_semantics)
            if block.protocol == "tcp":
                base = SyndataSettings.get_defaults().to_dict()
                base["enabled"] = False
                base["send_enabled"] = False
                base["out_range"] = 0
                base["out_range_mode"] = "n"

                if block_semantics.out_range.status == SEMANTIC_STATUS_STRUCTURED_SUPPORTED:
                    base.update(extract_structured_out_range(block_text_for_semantics))
                if block_semantics.syndata.status == SEMANTIC_STATUS_STRUCTURED_SUPPORTED:
                    base.update(extract_structured_syndata(block_text_for_semantics))
                if block_semantics.send.status == SEMANTIC_STATUS_STRUCTURED_SUPPORTED:
                    base.update(extract_structured_send(block_text_for_semantics))
                cat.syndata_tcp = SyndataSettings.from_dict(base)
            elif block.protocol == "udp":
                base = SyndataSettings.get_defaults_udp().to_dict()
                base["out_range"] = 0
                base["out_range_mode"] = "n"

                if block_semantics.out_range.status == SEMANTIC_STATUS_STRUCTURED_SUPPORTED:
                    base.update(extract_structured_out_range(block_text_for_semantics))
                cat.syndata_udp = SyndataSettings.from_dict(base)

            # Set args based on protocol
            if block.protocol == "tcp":
                cat.tcp_args = block.strategy_args
                cat.tcp_args_raw = raw_strategy_args
                cat.tcp_port = block.port
                cat.tcp_enabled = True
                # TCP filter_mode takes priority over UDP
                cat.filter_mode = block.filter_mode
                # Compute filter-stripped but syndata/send-inclusive args for inference
                try:
                    from .txt_preset_parser import extract_strategy_args_incl_syndata
                    full_tcp = extract_strategy_args_incl_syndata(
                        block.args,
                        category_key=cat_name,
                        filter_mode=block.filter_mode,
                    )
                    prev = _full_args_for_inference.get(cat_name, ("", ""))
                    _full_args_for_inference[cat_name] = (full_tcp, prev[1])
                except Exception:
                    pass
            elif block.protocol == "udp":
                cat.udp_args = block.strategy_args
                cat.udp_args_raw = raw_strategy_args
                cat.udp_port = block.port
                cat.udp_enabled = True
                # UDP sets filter_mode only if TCP didn't set it
                if not cat.filter_mode:
                    cat.filter_mode = block.filter_mode

        # ✅ INFERENCE: Determine strategy_id from args for all categories
        # This is needed because preset files store args but not strategy_id
        from .strategy_inference import infer_strategy_id_from_args

        try:
            from strategy_menu.strategies_registry import get_current_strategy_set
            current_strategy_set = get_current_strategy_set()
        except Exception:
            current_strategy_set = None

        for cat_name, cat in preset.categories.items():
            # Use full args (syndata/send inclusive, filter stripped) for inference when
            # available so that basic-mode strategies embedding syndata/send are found.
            tcp_full, _ = _full_args_for_inference.get(cat_name, ("", ""))

            # Try TCP first (most common)
            if cat.tcp_args and cat.tcp_args.strip():
                inferred_id = infer_strategy_id_from_args(
                    category_key=cat_name,
                    args=tcp_full if tcp_full and tcp_full.strip() else cat.tcp_args,
                    protocol="tcp",
                    strategy_set=current_strategy_set,
                )
                if inferred_id != "none":
                    cat.strategy_id = inferred_id
                    continue

            # Try UDP if TCP didn't work or is empty
            if cat.udp_args and cat.udp_args.strip():
                inferred_id = infer_strategy_id_from_args(
                    category_key=cat_name,
                    args=cat.udp_args,
                    protocol="udp",
                    strategy_set=current_strategy_set,
                )
                if inferred_id != "none":
                    cat.strategy_id = inferred_id

        log(f"Loaded preset '{name}': {len(preset.categories)} categories", "DEBUG")
        return preset

    except Exception as e:
        log(f"Error loading preset '{name}': {e}", "ERROR")
        return None


def _parse_metadata_from_header(header: str) -> Tuple[str, str, str, str]:
    """
    Parses created/modified/description/icon_color metadata from header comments.

    Args:
        header: Raw header string

    Returns:
        Tuple of (created, modified, description, icon_color)
    """
    created = datetime.now().isoformat()
    modified = datetime.now().isoformat()
    description = ""
    icon_color = DEFAULT_PRESET_ICON_COLOR

    for line in (header or "").split('\n'):
        created_match = re.match(r'#\s*Created:\s*(.+)', line, re.IGNORECASE)
        if created_match:
            created = created_match.group(1).strip()

        modified_match = re.match(r'#\s*Modified:\s*(.+)', line, re.IGNORECASE)
        if modified_match:
            modified = modified_match.group(1).strip()

        desc_match = re.match(r'#\s*Description:\s*(.*)', line, re.IGNORECASE)
        if desc_match:
            description = desc_match.group(1).strip()

        icon_color_match = re.match(r'#\s*(?:IconColor|PresetIconColor):\s*(.+)', line, re.IGNORECASE)
        if icon_color_match:
            icon_color = normalize_preset_icon_color(icon_color_match.group(1).strip())

    return created, modified, description, icon_color


def _parse_builtin_version_from_header(header: str) -> Optional[str]:
    """Parses `# BuiltinVersion: X.Y` from header comments."""
    for line in (header or "").split('\n'):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            break
        match = re.match(r'#\s*BuiltinVersion:\s*(.+)', line, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            return value or None
    return None


def _read_existing_builtin_version(path: Path) -> Optional[str]:
    """Reads BuiltinVersion from existing preset file (if present)."""
    try:
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8", errors="replace")
        return _parse_builtin_version_from_header(content)
    except Exception:
        return None


def _parse_timestamps_from_header(header: str) -> Tuple[str, str]:
    """Backward-compatible helper returning (created, modified) only."""
    created, modified, _desc, _icon = _parse_metadata_from_header(header)
    return created, modified


def save_preset(preset: Preset) -> bool:
    """
    Saves preset to file.

    Uses atomic write (temp file + rename) for safety.

    Args:
        preset: Preset object to save

    Returns:
        True if successful
    """
    from .txt_preset_parser import PresetData, CategoryBlock, generate_preset_file

    preset_path = get_preset_path(preset.name)

    try:
        # Convert Preset to PresetData
        data = PresetData(
            name=preset.name,
            base_args=preset.base_args,
        )

        icon_color = normalize_preset_icon_color(getattr(preset, "icon_color", DEFAULT_PRESET_ICON_COLOR))
        preset.icon_color = icon_color

        # Build raw header. Preserve BuiltinVersion if this file already has it
        # so versioned auto-updates can compare against local state correctly.
        builtin_version = _read_existing_builtin_version(preset_path)
        header_lines = [f"# Preset: {preset.name}"]
        if builtin_version:
            header_lines.append(f"# BuiltinVersion: {builtin_version}")
        header_lines.extend(
            [
                f"# Created: {preset.created}",
                f"# Modified: {datetime.now().isoformat()}",
                f"# IconColor: {icon_color}",
                f"# Description: {preset.description}",
            ]
        )
        data.raw_header = "\n".join(header_lines)

        # Convert categories to CategoryBlocks
        for cat_name, cat in preset.categories.items():
            # TCP block
            if cat.tcp_enabled and cat.has_tcp():
                from .base_filter import build_category_base_filter_lines
                base_filter_lines = build_category_base_filter_lines(cat_name, cat.filter_mode)

                args_lines = list(base_filter_lines)
                if not args_lines:
                    filter_file_relative = cat.get_filter_file()
                    filter_file = os.path.normpath(os.path.join(_get_main_directory(), filter_file_relative))
                    args_lines = [f"--filter-tcp={cat.tcp_port}"]
                    if cat.filter_mode in ("hostlist", "ipset"):
                        args_lines.append(f"--{cat.filter_mode}={filter_file}")
                # Use get_full_tcp_args() to include syndata/send/out-range
                full_tcp_args = cat.get_full_tcp_args()
                for line in full_tcp_args.strip().split('\n'):
                    if line.strip():
                        args_lines.append(line.strip())

                block = CategoryBlock(
                    category=cat_name,
                    protocol="tcp",
                    filter_mode=cat.filter_mode if cat.filter_mode in ("hostlist", "ipset") else "",
                    filter_file="",
                    port=cat.tcp_port,
                    args='\n'.join(args_lines),
                    strategy_args=cat.tcp_args,
                )
                data.categories.append(block)

            # UDP block
            if cat.udp_enabled and cat.has_udp():
                from .base_filter import build_category_base_filter_lines
                base_filter_lines = build_category_base_filter_lines(cat_name, cat.filter_mode)

                args_lines = list(base_filter_lines)
                if not args_lines:
                    filter_file_relative = cat.get_filter_file()
                    filter_file = os.path.normpath(os.path.join(_get_main_directory(), filter_file_relative))
                    args_lines = [f"--filter-udp={cat.udp_port}"]
                    if cat.filter_mode in ("hostlist", "ipset"):
                        args_lines.append(f"--{cat.filter_mode}={filter_file}")
                # Use get_full_udp_args() to include out-range (UDP has no syndata/send)
                full_udp_args = cat.get_full_udp_args()
                for line in full_udp_args.strip().split('\n'):
                    if line.strip():
                        args_lines.append(line.strip())

                block = CategoryBlock(
                    category=cat_name,
                    protocol="udp",
                    filter_mode=cat.filter_mode if cat.filter_mode in ("hostlist", "ipset") else "",
                    filter_file="",
                    port=cat.udp_port,
                    args='\n'.join(args_lines),
                    strategy_args=cat.udp_args,
                )
                data.categories.append(block)

        # Deduplicate categories before writing
        data.deduplicate_categories()

        # Write file
        success = generate_preset_file(data, preset_path, atomic=True)

        if success:
            log(f"Saved preset '{preset.name}' to {preset_path}", "DEBUG")
        else:
            log(f"Failed to save preset '{preset.name}'", "ERROR")

        return success

    except PermissionError as e:
        log(f"Cannot write preset file (locked by winws2?): {e}", "ERROR")
        raise
    except Exception as e:
        log(f"Error saving preset '{preset.name}': {e}", "ERROR")
        return False


# ============================================================================
# DELETE/RENAME OPERATIONS
# ============================================================================

def delete_preset(name: str) -> bool:
    """
    Deletes preset file.

    Args:
        name: Preset name

    Returns:
        True if deleted successfully
    """
    preset_path = get_preset_path(name)

    if not preset_path.exists():
        log(f"Cannot delete: preset '{name}' not found", "WARNING")
        return False

    try:
        preset_path.unlink()
        log(f"Deleted preset '{name}'", "DEBUG")
        return True
    except Exception as e:
        log(f"Error deleting preset '{name}': {e}", "ERROR")
        return False


def rename_preset(old_name: str, new_name: str) -> bool:
    """
    Renames preset file.

    Args:
        old_name: Current preset name
        new_name: New preset name

    Returns:
        True if renamed successfully
    """
    old_path = get_preset_path(old_name)
    new_path = get_preset_path(new_name)

    if not old_path.exists():
        log(f"Cannot rename: preset '{old_name}' not found", "WARNING")
        return False

    if new_path.exists():
        log(f"Cannot rename: preset '{new_name}' already exists", "WARNING")
        return False

    try:
        preset = load_preset(old_name)
        if preset is None:
            return False

        preset.name = new_name
        preset.touch()

        if save_preset(preset):
            # Delete old file
            old_path.unlink()
            log(f"Renamed preset '{old_name}' to '{new_name}'", "DEBUG")
            return True
        else:
            return False

    except Exception as e:
        log(f"Error renaming preset: {e}", "ERROR")
        return False


# ============================================================================
# IMPORT/EXPORT OPERATIONS
# ============================================================================

def export_preset(name: str, dest_path: Path) -> bool:
    """
    Exports preset to external file.

    Args:
        name: Preset name
        dest_path: Destination path

    Returns:
        True if exported successfully
    """
    preset_path = get_preset_path(name)

    if not preset_path.exists():
        log(f"Cannot export: preset '{name}' not found", "WARNING")
        return False

    try:
        shutil.copy2(preset_path, dest_path)
        log(f"Exported preset '{name}' to {dest_path}", "DEBUG")
        return True
    except Exception as e:
        log(f"Error exporting preset: {e}", "ERROR")
        return False


def import_preset(src_path: Path, name: Optional[str] = None) -> bool:
    """
    Imports preset from external file.

    Args:
        src_path: Source file path
        name: Optional name for imported preset (uses filename if None)

    Returns:
        True if imported successfully
    """
    src_path = Path(src_path)

    if not src_path.exists():
        log(f"Cannot import: file '{src_path}' not found", "WARNING")
        return False

    # Determine name
    if name is None:
        name = src_path.stem

    # Check for existing
    if preset_exists(name):
        log(f"Cannot import: preset '{name}' already exists", "WARNING")
        return False

    try:
        dest_path = get_preset_path(name)
        shutil.copy2(src_path, dest_path)
        log(f"Imported preset '{name}' from {src_path}", "DEBUG")
        return True
    except Exception as e:
        log(f"Error importing preset: {e}", "ERROR")
        return False


def duplicate_preset(name: str, new_name: str) -> bool:
    """
    Creates a copy of preset with new name.

    Args:
        name: Source preset name
        new_name: Name for the copy

    Returns:
        True if duplicated successfully
    """
    if not preset_exists(name):
        log(f"Cannot duplicate: preset '{name}' not found", "WARNING")
        return False

    if preset_exists(new_name):
        log(f"Cannot duplicate: preset '{new_name}' already exists", "WARNING")
        return False

    try:
        preset = load_preset(name)
        if preset is None:
            return False

        preset.name = new_name
        preset.created = datetime.now().isoformat()
        preset.modified = datetime.now().isoformat()

        return save_preset(preset)

    except Exception as e:
        log(f"Error duplicating preset: {e}", "ERROR")
        return False
