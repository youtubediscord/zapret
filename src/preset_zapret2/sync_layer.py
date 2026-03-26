from __future__ import annotations

import os
from datetime import datetime
from typing import Callable, Optional

from log import log

from .preset_model import DEFAULT_PRESET_ICON_COLOR, Preset, normalize_preset_icon_color
from .preset_storage import get_active_preset_path


class Zapret2PresetSyncLayer:
    def __init__(
        self,
        *,
        on_dpi_reload_needed: Optional[Callable[[], None]] = None,
        invalidate_cache: Optional[Callable[[], None]] = None,
        inject_debug_into_base_args: Optional[Callable[[str], str]] = None,
        update_wf_out_ports_in_base_args: Optional[Callable[[Preset], str]] = None,
    ):
        self._on_dpi_reload_needed = on_dpi_reload_needed
        self._invalidate_cache = invalidate_cache or (lambda: None)
        self._inject_debug_into_base_args = inject_debug_into_base_args or (lambda text: text)
        self._update_wf_out_ports_in_base_args = update_wf_out_ports_in_base_args or (lambda preset: preset.base_args)

    def sync_preset(self, preset: Preset, changed_category: str | None = None) -> bool:
        active_path = get_active_preset_path()
        is_basic_direct = self._is_basic_direct()

        try:
            preset.base_args = self._update_wf_out_ports_in_base_args(preset)
            raw_blocks = getattr(preset, "_raw_blocks", None) or []
            if changed_category and raw_blocks:
                return self._sync_with_raw_block_preservation(
                    preset,
                    active_path=str(active_path),
                    changed_category=str(changed_category),
                    raw_blocks=raw_blocks,
                    is_basic_direct=is_basic_direct,
                )
            return self._sync_full_regeneration(preset, active_path=str(active_path), is_basic_direct=is_basic_direct)
        except PermissionError as e:
            log(f"Cannot write generated launch config (locked by winws2?): {e}", "ERROR")
            raise
        except Exception as e:
            log(f"Error syncing to generated launch config: {e}", "ERROR")
            return False

    @staticmethod
    def _is_basic_direct() -> bool:
        try:
            from strategy_menu import get_direct_zapret2_ui_mode, get_strategy_launch_method

            return (
                (get_strategy_launch_method() or "").strip().lower() == "direct_zapret2"
                and (get_direct_zapret2_ui_mode() or "").strip().lower() == "basic"
            )
        except Exception:
            return False

    def _sync_with_raw_block_preservation(
        self,
        preset: Preset,
        *,
        active_path: str,
        changed_category: str,
        raw_blocks: list,
        is_basic_direct: bool,
    ) -> bool:
        from .txt_preset_parser import _normalize_known_path_line

        cat = preset.categories.get(changed_category)
        cat_disabled = (not cat) or (cat.strategy_id == "none")

        for cat_keys, _, _ in raw_blocks:
            if changed_category in cat_keys and len(cat_keys) > 1:
                log(
                    f"Changed category '{changed_category}' is in a shared block "
                    f"with {cat_keys}. Falling back to full regeneration.",
                    "DEBUG",
                )
                return self._sync_full_regeneration(preset, active_path=active_path, is_basic_direct=is_basic_direct)

        changed_cat_in_raw = any(changed_category in cat_keys for cat_keys, _, _ in raw_blocks)
        result_block_texts: list[str] = []

        for cat_keys, raw_protocol, raw_text in raw_blocks:
            if changed_category in cat_keys:
                if cat_disabled:
                    continue
                new_block_text = self._build_category_block_text(
                    preset,
                    changed_category,
                    raw_protocol,
                    is_basic_direct,
                )
                if new_block_text:
                    result_block_texts.append(new_block_text)
            else:
                result_block_texts.append(raw_text)

        if not changed_cat_in_raw and not cat_disabled:
            for proto in ("tcp", "udp"):
                new_block_text = self._build_category_block_text(
                    preset,
                    changed_category,
                    proto,
                    is_basic_direct,
                )
                if new_block_text:
                    result_block_texts.append(new_block_text)

        icon_color = normalize_preset_icon_color(getattr(preset, "icon_color", DEFAULT_PRESET_ICON_COLOR))
        preset.icon_color = icon_color

        lines: list[str] = [
            f"# Preset: {preset.name}",
            f"# Modified: {datetime.now().isoformat()}",
            f"# IconColor: {icon_color}",
            "",
        ]

        base_args_text = self._inject_debug_into_base_args(preset.base_args)
        if base_args_text:
            for line in base_args_text.split("\n"):
                if line.strip():
                    lines.append(_normalize_known_path_line(line.strip()))
            lines.append("")

        for idx, block_text in enumerate(result_block_texts):
            for line in block_text.split("\n"):
                if line.strip():
                    lines.append(line.strip())
            if idx < len(result_block_texts) - 1:
                lines.extend(["", "--new", ""])

        content = "\n".join(lines)
        return self._commit_generated_launch_config_text(
            content,
            log_message=f"Synced preset to generated launch config (raw block preservation, changed: {changed_category})",
        )

    def _build_category_block_text(
        self,
        preset: Preset,
        cat_key: str,
        protocol: str,
        is_basic_direct: bool,
    ) -> str:
        from .base_filter import build_category_base_filter_lines

        cat = preset.categories.get(cat_key)
        if not cat:
            return ""

        if protocol == "tcp":
            if not (cat.tcp_enabled and cat.has_tcp()):
                return ""
            strategy_text = str(getattr(cat, "tcp_args", "") or "")
            port = cat.tcp_port
        elif protocol == "udp":
            if not (cat.udp_enabled and cat.has_udp()):
                return ""
            strategy_text = str(getattr(cat, "udp_args", "") or "")
            port = cat.udp_port
        else:
            return ""

        base_filter_lines = build_category_base_filter_lines(cat_key, cat.filter_mode)
        args_lines = list(base_filter_lines)

        if not args_lines:
            filter_file_relative = cat.get_filter_file()
            try:
                from config import MAIN_DIRECTORY

                filter_file = os.path.normpath(os.path.join(MAIN_DIRECTORY, filter_file_relative))
            except Exception:
                filter_file = filter_file_relative
            args_lines = [f"--filter-{protocol}={port}"]
            if cat.filter_mode in ("hostlist", "ipset"):
                args_lines.append(f"--{cat.filter_mode}={filter_file}")

        strat_lines = [ln.strip() for ln in strategy_text.splitlines() if ln.strip()]

        if is_basic_direct:
            syndata_settings = cat.syndata_tcp if protocol == "tcp" else cat.syndata_udp
            try:
                out_range_arg = cat._get_out_range_args(syndata_settings)
            except Exception:
                out_range_arg = ""
            if out_range_arg:
                args_lines.append(str(out_range_arg).strip())
            args_lines.extend(strat_lines)
        else:
            send_present = any(ln.lower().startswith("--lua-desync=send") for ln in strat_lines)
            syndata_present = any(ln.lower().startswith("--lua-desync=syndata") for ln in strat_lines)
            strat_lines_no_out = [ln for ln in strat_lines if not ln.lower().startswith("--out-range=")]
            strategy_text_clean = "\n".join(strat_lines_no_out).strip()
            parts: list[str] = []

            syndata_settings = cat.syndata_tcp if protocol == "tcp" else cat.syndata_udp

            try:
                out_range_arg = cat._get_out_range_args(syndata_settings)
            except Exception:
                out_range_arg = ""
            if out_range_arg:
                parts.append(str(out_range_arg).strip())

            if protocol == "tcp":
                try:
                    if bool(getattr(syndata_settings, "send_enabled", False)) and not send_present:
                        send_arg = cat._get_send_args(syndata_settings)
                        if send_arg:
                            parts.append(str(send_arg).strip())
                except Exception:
                    pass

                try:
                    if bool(getattr(syndata_settings, "enabled", False)) and not syndata_present:
                        syndata_arg = cat._get_syndata_args(syndata_settings)
                        if syndata_arg:
                            parts.append(str(syndata_arg).strip())
                except Exception:
                    pass

            if strategy_text_clean:
                parts.append(strategy_text_clean)

            full_args = "\n".join([p for p in parts if p]).strip()
            for raw_line in full_args.splitlines():
                line = (raw_line or "").strip()
                if line:
                    args_lines.append(line)

        return "\n".join(args_lines)

    def _sync_full_regeneration(self, preset: Preset, *, active_path: str, is_basic_direct: bool) -> bool:
        from .txt_preset_parser import CategoryBlock, PresetData, generate_preset_file

        data = PresetData(
            name=preset.name,
            base_args=self._inject_debug_into_base_args(preset.base_args),
        )

        icon_color = normalize_preset_icon_color(getattr(preset, "icon_color", DEFAULT_PRESET_ICON_COLOR))
        preset.icon_color = icon_color
        data.raw_header = f"""# Preset: {preset.name}
# Modified: {datetime.now().isoformat()}
# IconColor: {icon_color}"""

        for cat_name, cat in preset.categories.items():
            if cat.tcp_enabled and cat.has_tcp():
                block_text = self._build_category_block_text(preset, cat_name, "tcp", is_basic_direct)
                if block_text:
                    data.categories.append(
                        CategoryBlock(
                            category=cat_name,
                            protocol="tcp",
                            filter_mode=cat.filter_mode if cat.filter_mode in ("hostlist", "ipset") else "",
                            filter_file="",
                            port=cat.tcp_port,
                            args=block_text,
                            strategy_args=cat.tcp_args,
                        )
                    )

            if cat.udp_enabled and cat.has_udp():
                block_text = self._build_category_block_text(preset, cat_name, "udp", is_basic_direct)
                if block_text:
                    data.categories.append(
                        CategoryBlock(
                            category=cat_name,
                            protocol="udp",
                            filter_mode=cat.filter_mode if cat.filter_mode in ("hostlist", "ipset") else "",
                            filter_file="",
                            port=cat.udp_port,
                            args=block_text,
                            strategy_args=cat.udp_args,
                        )
                    )

        data.deduplicate_categories()
        success = generate_preset_file(data, active_path, atomic=True)
        if success:
            self._invalidate_cache()
            log("Synced preset to generated launch config", "DEBUG")
            if self._on_dpi_reload_needed:
                self._on_dpi_reload_needed()
        return success

    def _commit_generated_launch_config_text(self, content: str, *, log_message: str) -> bool:
        active_path = get_active_preset_path()
        try:
            active_path.parent.mkdir(parents=True, exist_ok=True)
            active_path.write_text(str(content or ""), encoding="utf-8")
            self._invalidate_cache()
            log(log_message, "DEBUG")
            if self._on_dpi_reload_needed:
                self._on_dpi_reload_needed()
            return True
        except PermissionError as e:
            log(f"Cannot write generated launch config (locked by winws2?): {e}", "ERROR")
            raise
        except Exception as e:
            log(f"Error writing generated launch config: {e}", "ERROR")
            return False
