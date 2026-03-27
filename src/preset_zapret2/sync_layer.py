from __future__ import annotations

import os
from datetime import datetime
from typing import Callable, Optional

from config import REGISTRY_PATH
from log import log

from .ports import subtract_port_specs, union_port_specs
from .preset_model import DEFAULT_PRESET_ICON_COLOR, Preset, normalize_preset_icon_color
from .preset_storage import get_runtime_config_path


def _strip_debug_from_base_args(base_args: str) -> str:
    """Keep runtime-only --debug out of source preset content."""
    try:
        lines = (base_args or "").splitlines()
        kept: list[str] = []
        for raw in lines:
            stripped = raw.strip()
            if not stripped:
                continue
            if stripped.lower().startswith("--debug"):
                continue
            kept.append(stripped)
        return "\n".join(kept).strip()
    except Exception:
        return (base_args or "").strip()


def inject_debug_into_base_args(base_args: str) -> str:
    """Apply runtime --debug injection from direct_zapret2 registry settings."""
    import winreg

    cleaned = _strip_debug_from_base_args(base_args)

    enabled = False
    debug_file = ""
    try:
        direct_path = rf"{REGISTRY_PATH}\DirectMethod"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, direct_path) as key:
            value, _ = winreg.QueryValueEx(key, "DebugLogEnabled")
            enabled = bool(value)
            try:
                debug_file, _ = winreg.QueryValueEx(key, "DebugLogFile")
            except Exception:
                debug_file = ""
    except Exception:
        enabled = False

    if not enabled:
        return cleaned

    if not debug_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_file = f"logs/zapret_winws2_debug_{timestamp}.log"
        try:
            direct_path = rf"{REGISTRY_PATH}\DirectMethod"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, direct_path) as key:
                winreg.SetValueEx(key, "DebugLogFile", 0, winreg.REG_SZ, debug_file)
        except Exception:
            pass

    debug_file_norm = str(debug_file).replace("\\", "/").lstrip("@").lstrip("/")
    debug_line = f"--debug=@{debug_file_norm}"

    lines = cleaned.splitlines() if cleaned else []
    insert_at = 0
    for i, raw in enumerate(lines):
        if raw.strip().startswith("--lua-init="):
            insert_at = i + 1

    lines.insert(insert_at, debug_line)
    return "\n".join(lines).strip()


def update_wf_out_ports_in_base_args(preset: Preset) -> str:
    """Normalize wf out-port args from enabled category filters."""
    from .base_filter import build_category_base_filter_lines
    from .preset_defaults import get_builtin_preset_content

    base_args = preset.base_args or ""
    lines = base_args.splitlines()

    marker_prefix = "# AutoWFOutExtra:"
    marker_prefix_l = marker_prefix.lower()

    existing_wf_tcp = ""
    existing_wf_udp = ""
    prev_extra_tcp = ""
    prev_extra_udp = ""
    marker_present = False
    keep_empty_marker = False
    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith("--wf-tcp-out="):
            existing_wf_tcp = stripped.split("=", 1)[1].strip()
        elif stripped.startswith("--wf-udp-out="):
            existing_wf_udp = stripped.split("=", 1)[1].strip()
        elif stripped.lower().startswith(marker_prefix_l):
            marker_present = True
            payload = stripped.split(":", 1)[1].strip() if ":" in stripped else ""
            for token in payload.split():
                k, _sep, v = token.partition("=")
                k_l = k.strip().lower()
                if k_l == "tcp":
                    prev_extra_tcp = v.strip()
                elif k_l == "udp":
                    prev_extra_udp = v.strip()

    if not marker_present and (preset.name or "").strip().lower() == "default":
        try:
            template_tcp = ""
            template_udp = ""
            template = get_builtin_preset_content("Default") or ""
            for raw in template.splitlines():
                line = raw.strip()
                if line.startswith("--wf-tcp-out="):
                    template_tcp = line.split("=", 1)[1].strip()
                    if template_udp:
                        break
                elif line.startswith("--wf-udp-out="):
                    template_udp = line.split("=", 1)[1].strip()
                    if template_tcp:
                        break

            if template_tcp:
                existing_wf_tcp = template_tcp
            if template_udp:
                existing_wf_udp = template_udp
            if template_tcp or template_udp:
                keep_empty_marker = True
        except Exception:
            pass

    base_wf_tcp = subtract_port_specs(existing_wf_tcp, prev_extra_tcp) if prev_extra_tcp else (existing_wf_tcp or "")
    base_wf_udp = subtract_port_specs(existing_wf_udp, prev_extra_udp) if prev_extra_udp else (existing_wf_udp or "")

    if base_wf_tcp:
        base_wf_tcp = union_port_specs([base_wf_tcp])
    if base_wf_udp:
        base_wf_udp = union_port_specs([base_wf_udp])

    tcp_specs: list[str] = []
    udp_specs: list[str] = []

    for cat_name, cat in preset.categories.items():
        if cat.tcp_enabled and cat.has_tcp():
            base_filter_lines = build_category_base_filter_lines(cat_name, cat.filter_mode)
            spec = ""
            for token in base_filter_lines:
                token_s = token.strip()
                if token_s.startswith("--filter-tcp="):
                    spec = token_s.split("=", 1)[1].strip()
                    break
            if not spec:
                spec = (cat.tcp_port or "").strip()
            if spec:
                tcp_specs.append(spec)

        if cat.udp_enabled and cat.has_udp():
            base_filter_lines = build_category_base_filter_lines(cat_name, cat.filter_mode)
            spec = ""
            for token in base_filter_lines:
                token_s = token.strip()
                if token_s.startswith("--filter-udp="):
                    spec = token_s.split("=", 1)[1].strip()
                    break
            if not spec:
                spec = (cat.udp_port or "").strip()
            if spec:
                udp_specs.append(spec)

    cats_wf_tcp = union_port_specs(tcp_specs) if tcp_specs else ""
    cats_wf_udp = union_port_specs(udp_specs) if udp_specs else ""

    new_extra_tcp = subtract_port_specs(cats_wf_tcp, base_wf_tcp) if cats_wf_tcp else ""
    new_extra_udp = subtract_port_specs(cats_wf_udp, base_wf_udp) if cats_wf_udp else ""

    new_wf_tcp = union_port_specs([base_wf_tcp, new_extra_tcp]) if (base_wf_tcp or new_extra_tcp) else ""
    new_wf_udp = union_port_specs([base_wf_udp, new_extra_udp]) if (base_wf_udp or new_extra_udp) else ""

    def _replace_or_add(prefix: str, value: str) -> None:
        nonlocal lines
        if not value:
            return
        replaced = False
        out: list[str] = []
        for raw in lines:
            if raw.strip().startswith(prefix):
                out.append(f"{prefix}{value}")
                replaced = True
            else:
                out.append(raw)
        if not replaced:
            insert_at = 0
            for i, raw in enumerate(out):
                if raw.strip().startswith("--lua-init="):
                    insert_at = i + 1
            out.insert(insert_at, f"{prefix}{value}")
        lines = out

    def _set_marker(extra_tcp: str, extra_udp: str, keep_empty: bool = False) -> None:
        nonlocal lines
        parts: list[str] = []
        if extra_tcp:
            parts.append(f"tcp={extra_tcp}")
        if extra_udp:
            parts.append(f"udp={extra_udp}")
        if parts:
            marker_line = f"{marker_prefix} {' '.join(parts)}".rstrip()
        elif keep_empty:
            marker_line = marker_prefix
        else:
            marker_line = ""

        out: list[str] = []
        replaced = False
        for raw in lines:
            if raw.strip().lower().startswith(marker_prefix_l):
                replaced = True
                if marker_line:
                    out.append(marker_line)
            else:
                out.append(raw)

        if not replaced and marker_line:
            insert_at = 0
            for i, raw in enumerate(out):
                stripped = raw.strip()
                if stripped.startswith("--wf-"):
                    insert_at = i + 1
                elif stripped.startswith("--lua-init=") and insert_at == 0:
                    insert_at = i + 1
            out.insert(insert_at, marker_line)

        lines = out

    if new_wf_tcp:
        _replace_or_add("--wf-tcp-out=", new_wf_tcp)
    if new_wf_udp:
        _replace_or_add("--wf-udp-out=", new_wf_udp)

    keep_empty_final = marker_present or keep_empty_marker
    _set_marker(new_extra_tcp, new_extra_udp, keep_empty=keep_empty_final)

    return "\n".join(lines).strip()


def sync_preset_to_runtime(
    preset: Preset,
    *,
    changed_category: str | None = None,
    on_dpi_reload_needed: Optional[Callable[[], None]] = None,
    invalidate_cache: Optional[Callable[[], None]] = None,
) -> bool:
    layer = Zapret2PresetSyncLayer(
        on_dpi_reload_needed=on_dpi_reload_needed,
        invalidate_cache=invalidate_cache,
        inject_debug_into_base_args=inject_debug_into_base_args,
        update_wf_out_ports_in_base_args=update_wf_out_ports_in_base_args,
    )
    return layer.sync_preset(preset, changed_category=changed_category)


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
        active_path = get_runtime_config_path()
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

        from .block_semantics import SEMANTIC_STATUS_STRUCTURED_SUPPORTED, analyze_block_semantics

        send_present = any(ln.lower().startswith("--lua-desync=send") for ln in strat_lines)
        syndata_present = any(ln.lower().startswith("--lua-desync=syndata") for ln in strat_lines)
        strategy_semantics = analyze_block_semantics(strategy_text)
        syndata_settings = cat.syndata_tcp if protocol == "tcp" else cat.syndata_udp

        if is_basic_direct:
            # In basic direct mode strategy text stays authoritative, but source
            # preset parsing may already have lifted structured out-range/send/
            # syndata into category settings. Restore only the missing helper
            # lines so effective.txt preserves the source preset behaviour
            # without duplicating raw tokens that are still present in args.
            helper_lines: list[str] = []

            try:
                if not strategy_semantics.has_explicit_out_range:
                    out_range_arg = cat._get_out_range_args(syndata_settings)
                    if out_range_arg:
                        helper_lines.append(str(out_range_arg).strip())
            except Exception:
                pass

            if protocol == "tcp":
                try:
                    if bool(getattr(syndata_settings, "send_enabled", False)) and not send_present:
                        send_arg = cat._get_send_args(syndata_settings)
                        if send_arg:
                            helper_lines.append(str(send_arg).strip())
                except Exception:
                    pass

                try:
                    if bool(getattr(syndata_settings, "enabled", False)) and not syndata_present:
                        syndata_arg = cat._get_syndata_args(syndata_settings)
                        if syndata_arg:
                            helper_lines.append(str(syndata_arg).strip())
                except Exception:
                    pass

            args_lines.extend(helper_lines)
            args_lines.extend(strat_lines)
        else:
            strat_lines_no_out = []
            for ln in strat_lines:
                semantics = analyze_block_semantics(ln)
                if (
                    strategy_semantics.out_range.status == SEMANTIC_STATUS_STRUCTURED_SUPPORTED
                    and ln.lower().startswith("--out-range=")
                    and semantics.out_range.status == SEMANTIC_STATUS_STRUCTURED_SUPPORTED
                ):
                    continue
                strat_lines_no_out.append(ln)
            strategy_text_clean = "\n".join(strat_lines_no_out).strip()
            parts: list[str] = []

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
        active_path = get_runtime_config_path()
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
