# presets/__init__.py
"""
Preset system for direct_zapret2 mode.

Presets are stored as txt files in %APPDATA%/zapret/presets_v2/.
Each preset contains:
- Metadata (name, created, modified)
- Base arguments (lua-init, wf-*, blobs)
- Category configurations (youtube, discord, etc.)

Switching presets = selecting a source preset + regenerating runtime config + DPI reload.

Usage:
    from presets import PresetManager, Preset

    manager = PresetManager()

    # List available presets
    presets = manager.list_presets()

    # Switch to a preset
    manager.switch_preset("Gaming")

    # Get current preset
    preset = manager.get_active_preset()

    # Create new preset from current configuration
    manager.create_preset_from_current("My Backup")

    # Edit preset
    preset = manager.load_preset("Default")
    preset.categories["youtube"].tcp_args = "--lua-desync=multisplit:pos=1"
    manager.save_preset(preset)

Low-level API:
    from presets import (
        get_presets_dir,
        list_presets,
        load_preset,
        save_preset,
        delete_preset,
        rename_preset,
    )

Parser API (for txt files):
    from presets.txt_preset_parser import (
        parse_preset_file,
        generate_preset_file,
        PresetData,
        CategoryBlock,
    )
"""

from pathlib import Path

# Model classes
from .preset_model import CategoryConfig, Preset, SyndataSettings, validate_preset

# Storage functions (low-level)
from .preset_storage import (
    delete_preset,
    duplicate_preset,
    export_preset,
    get_active_preset_name,
    get_active_preset_path,
    get_preset_path,
    get_presets_dir,
    get_user_settings_path,
    import_preset,
    list_presets,
    load_preset,
    preset_exists,
    rename_preset,
    save_preset,
    set_active_preset_name,
)

# High-level manager
from .preset_manager import PresetManager

# Central in-memory store (singleton)
from .preset_store import PresetStore, get_preset_store

# Txt parser (for advanced usage)
from .txt_preset_parser import (
    CategoryBlock,
    PresetData,
    extract_category_from_args,
    extract_protocol_and_port,
    extract_strategy_args,
    invalidate_category_inference_cache,
    generate_preset_content,
    generate_preset_file,
    parse_preset_content,
    parse_preset_file,
    update_category_in_preset,
)

# Default settings parser & template functions
from .preset_defaults import (
    get_default_category_settings,
    get_category_default_filter_mode,
    get_category_default_syndata,
    parse_syndata_from_args,
    get_default_template_content,
    get_default_template_name,
    get_template_content,
    get_template_canonical_name,
    invalidate_templates_cache,
    ensure_templates_copied_to_presets,
)

# Strategy inference (for loading presets)
from .strategy_inference import (
    infer_strategy_id_from_args,
    infer_strategy_ids_batch,
    normalize_args,
)


def _atomic_write_text(path, content: str, *, encoding: str = "utf-8") -> None:
    """Writes text via temp file + replace to avoid partial files."""
    import os
    import tempfile
    from pathlib import Path

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = (content or "").replace("\r\n", "\n").replace("\r", "\n")
    if not data.endswith("\n"):
        data += "\n"

    fd, tmp_name = tempfile.mkstemp(
        prefix=f"{path.stem}_",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as f:
            f.write(data)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        os.replace(tmp_name, str(path))
    finally:
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except Exception:
            pass

def ensure_builtin_presets_exist() -> bool:
    """
    Ensures that preset templates directory (presets_v2_template/) exists and
    syncs templates to presets/ (including version-based auto-updates).

    In dev mode, seeds templates from the repo folder
    `preset_zapret2/builtin_presets/*.txt` into `presets_v2_template/`.

    Returns:
        True if presets exist or were created successfully.
    """
    from log import log
    from .preset_defaults import (
        invalidate_templates_cache,
        ensure_templates_copied_to_presets,
    )

    try:
        # Ensure presets_v2_template/ directory exists
        try:
            from config import get_zapret_presets_v2_template_dir

            templates_dir = Path(get_zapret_presets_v2_template_dir())
        except Exception:
            templates_dir = get_presets_dir().parent / "presets_v2_template"
        templates_dir.mkdir(parents=True, exist_ok=True)

        # Dev convenience: seed templates from the repo (if present)
        try:
            from config import MAIN_DIRECTORY

            src_dir = Path(MAIN_DIRECTORY) / "preset_zapret2" / "builtin_presets"
            if src_dir.exists() and src_dir.is_dir():
                for p in sorted(src_dir.glob("*.txt"), key=lambda x: x.name.lower()):
                    if p.name.startswith("_"):
                        continue
                    dst = templates_dir / p.name
                    if dst.exists():
                        continue
                    try:
                        dst.write_text(p.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
                        log(f"Seeded preset template: {dst}", "DEBUG")
                    except Exception:
                        pass
        except Exception:
            pass

        # Templates may have just been seeded from the repo; refresh cache.
        try:
            invalidate_templates_cache()
        except Exception:
            pass

        # Sync templates to presets/ (create missing + version-based overwrite)
        ensure_templates_copied_to_presets()
        return True

    except Exception as e:
        log(f"Error ensuring built-in presets: {e}", "ERROR")
        import traceback
        log(traceback.format_exc(), "DEBUG")
        return False


def ensure_basic_strategies_exist() -> bool:
    """Ensures direct_zapret2 Basic strategies exist in Roaming AppData.

    Installer target:
      %APPDATA%\\zapret\\direct_zapret2\\basic_strategies\\*.txt

    Dev convenience: seed files from repo folder
      preset_zapret2/basic_strategies/
    """
    from log import log

    try:
        try:
            from config import get_zapret_userdata_dir
            dst_dir = Path(get_zapret_userdata_dir()) / "direct_zapret2" / "basic_strategies"
        except Exception:
            # Fallback: keep everything under presets root.
            dst_dir = get_presets_dir().parent / "direct_zapret2" / "basic_strategies"

        dst_dir.mkdir(parents=True, exist_ok=True)

        # Dev convenience: seed from repo folder if present (do not overwrite user edits)
        try:
            from config import MAIN_DIRECTORY
            src_dir = Path(MAIN_DIRECTORY) / "preset_zapret2" / "basic_strategies"
            if src_dir.exists() and src_dir.is_dir():
                for p in sorted(list(src_dir.glob("*.txt")) + list(src_dir.glob("*.json")), key=lambda x: x.name.lower()):
                    if p.name.startswith("_"):
                        continue
                    dst = dst_dir / p.name
                    if dst.exists():
                        continue
                    try:
                        dst.write_text(p.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
                        log(f"Seeded basic strategies file: {dst}", "DEBUG")
                    except Exception:
                        pass
        except Exception:
            pass

        return True

    except Exception as e:
        log(f"Error ensuring basic strategies: {e}", "ERROR")
        return False


def ensure_advanced_strategies_exist() -> bool:
    """Ensures direct_zapret2 Advanced strategies exist in Roaming AppData.

    Installer target:
      %APPDATA%\\zapret\\direct_zapret2\\advanced_strategies\\*.txt

    Dev convenience: seed files from repo folder
      preset_zapret2/advanced_strategies/
    """
    from log import log

    try:
        try:
            from config import get_zapret_userdata_dir
            dst_dir = Path(get_zapret_userdata_dir()) / "direct_zapret2" / "advanced_strategies"
        except Exception:
            # Fallback: keep everything under presets root.
            dst_dir = get_presets_dir().parent / "direct_zapret2" / "advanced_strategies"

        dst_dir.mkdir(parents=True, exist_ok=True)

        # Dev convenience: seed from repo folder if present (do not overwrite user edits)
        try:
            from config import MAIN_DIRECTORY
            src_dir = Path(MAIN_DIRECTORY) / "preset_zapret2" / "advanced_strategies"
            if src_dir.exists() and src_dir.is_dir():
                for p in sorted(list(src_dir.glob("*.txt")) + list(src_dir.glob("*.json")), key=lambda x: x.name.lower()):
                    if p.name.startswith("_"):
                        continue
                    dst = dst_dir / p.name
                    if dst.exists():
                        continue
                    try:
                        dst.write_text(p.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
                        log(f"Seeded advanced strategies file: {dst}", "DEBUG")
                    except Exception:
                        pass
        except Exception:
            pass

        return True

    except Exception as e:
        log(f"Error ensuring advanced strategies: {e}", "ERROR")
        return False


def ensure_default_preset_exists() -> bool:
    """
    Ensures that a default preset exists for direct_zapret2 mode.

    Ensures a selected preset exists and runtime config can be generated.

    This function should be called during application startup
    when running in direct_zapret2 mode.

    Returns:
        True if preset exists or was created successfully
    """
    from log import log

    try:
        from core.services import get_direct_flow_coordinator

        profile = get_direct_flow_coordinator().ensure_launch_profile(
            "direct_zapret2",
            require_filters=False,
        )
        log(f"Selected winws2 preset ensured and launch config regenerated: {profile.launch_config_path}", "INFO")
        return True

    except Exception as e:
        log(f"Error creating default preset: {e}", "ERROR")
        import traceback
        log(traceback.format_exc(), "DEBUG")
        return False


def restore_builtin_preset(preset_name: str) -> bool:
    """
    Restores a preset from the template in presets_v2_template/.

    Overwrites the preset in presets/ with the template content.
    If the preset is currently selected, also updates the runtime config.

    Returns:
        True if restore was successful, False otherwise
    """
    from log import log
    from .preset_defaults import get_template_content, get_template_canonical_name

    try:
        canonical = get_template_canonical_name(preset_name)
        content = get_template_content(preset_name)
        if not canonical or content is None:
            log(f"Unknown preset template '{preset_name}'", "ERROR")
            return False

        # Overwrite the presets/ file with template content
        preset_path = get_preset_path(canonical)
        preset_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(preset_path, content, encoding="utf-8")
        log(f"Restored preset '{canonical}' from template to {preset_path}", "INFO")

        # If this preset is currently selected, update runtime config
        active_name = (get_active_preset_name() or "").strip()
        if active_name and active_name.lower() == canonical.lower():
            active_path = get_active_preset_path()
            _atomic_write_text(active_path, content, encoding="utf-8")
            log(f"Also updated active preset at {active_path}", "SUCCESS")

        return True

    except Exception as e:
        log(f"Error restoring preset '{preset_name}' from template: {e}", "ERROR")
        import traceback
        log(traceback.format_exc(), "DEBUG")
        return False


def restore_default_preset() -> bool:
    """
    Restores Default preset from the built-in template.

    This function can be used to:
    1. Fix a corrupted Default.txt
    2. Reset Default.txt to factory settings
    3. Recover from accidental modifications

    Returns:
        True if restore was successful, False otherwise
    """
    return restore_builtin_preset("Default")


def restore_gaming_preset() -> bool:
    """
    Restores Gaming.txt preset from the built-in code template.

    Returns:
        True if restore was successful, False otherwise
    """
    return restore_builtin_preset("Gaming")


__all__ = [
    # Model
    "Preset",
    "CategoryConfig",
    "SyndataSettings",
    "validate_preset",
    # Storage functions
    "get_presets_dir",
    "get_preset_path",
    "get_active_preset_path",
    "get_user_settings_path",
    "list_presets",
    "preset_exists",
    "load_preset",
    "save_preset",
    "delete_preset",
    "rename_preset",
    "duplicate_preset",
    "export_preset",
    "import_preset",
    "get_active_preset_name",
    "set_active_preset_name",
    # Manager
    "PresetManager",
    # Central store
    "PresetStore",
    "get_preset_store",
    # Utility functions
    "ensure_builtin_presets_exist",
    "ensure_default_preset_exists",
    "restore_builtin_preset",
    "restore_default_preset",
    "restore_gaming_preset",
    "get_default_category_settings",
    "get_category_default_filter_mode",
    "get_category_default_syndata",
    "parse_syndata_from_args",
    # Template functions
    "get_default_template_content",
    "get_default_template_name",
    "get_template_content",
    "get_template_canonical_name",
    "invalidate_templates_cache",
    "ensure_templates_copied_to_presets",
    # Parser
    "PresetData",
    "CategoryBlock",
    "parse_preset_file",
    "parse_preset_content",
    "generate_preset_file",
    "generate_preset_content",
    "extract_category_from_args",
    "extract_protocol_and_port",
    "extract_strategy_args",
    "update_category_in_preset",
    # Strategy inference
    "infer_strategy_id_from_args",
    "infer_strategy_ids_batch",
    "normalize_args",
]
