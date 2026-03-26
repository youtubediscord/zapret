from __future__ import annotations

from datetime import datetime
from pathlib import PureWindowsPath
from typing import Callable, Optional

from log import log

from .preset_model import CategoryConfigV1, PresetV1
from .preset_storage import get_active_preset_path_v1, get_preset_path_v1


class Zapret1PresetSyncLayer:
    def __init__(
        self,
        *,
        on_dpi_reload_needed: Optional[Callable[[], None]] = None,
        invalidate_cache: Optional[Callable[[], None]] = None,
        get_selected_name: Optional[Callable[[], str]] = None,
    ):
        self._on_dpi_reload_needed = on_dpi_reload_needed
        self._invalidate_cache = invalidate_cache or (lambda: None)
        self._get_selected_name = get_selected_name or (lambda: "")

    def sync_preset(self, preset: PresetV1, changed_category: str | None = None) -> bool:
        _ = changed_category
        import os as _os
        from preset_zapret2.txt_preset_parser import CategoryBlock, PresetData, generate_preset_file
        from .preset_model import DEFAULT_PRESET_ICON_COLOR, normalize_preset_icon_color_v1

        active_path = get_active_preset_path_v1()

        try:
            data = PresetData(
                name=preset.name,
                base_args=preset.base_args,
            )

            icon_color = normalize_preset_icon_color_v1(getattr(preset, "icon_color", DEFAULT_PRESET_ICON_COLOR))
            preset.icon_color = icon_color
            data.raw_header = f"""# Preset: {preset.name}
# Modified: {datetime.now().isoformat()}
# IconColor: {icon_color}"""

            for cat_name, cat in preset.categories.items():
                from preset_zapret2.base_filter import build_category_base_filter_lines

                if cat.tcp_enabled and cat.has_tcp():
                    args_lines = build_category_base_filter_lines(cat_name, cat.filter_mode)
                    custom_port = str(cat.tcp_port or "").strip()
                    if custom_port and custom_port != "443":
                        for i, line in enumerate(args_lines):
                            if line.startswith("--filter-tcp="):
                                args_lines[i] = f"--filter-tcp={custom_port}"
                            elif line.startswith("--filter-l7="):
                                args_lines[i] = f"--filter-l7={custom_port}"
                    for raw in cat.tcp_args.splitlines():
                        line = raw.strip()
                        if line:
                            args_lines.append(line)
                    data.categories.append(
                        CategoryBlock(
                            category=cat_name,
                            protocol="tcp",
                            filter_mode=cat.filter_mode,
                            filter_file="",
                            port=cat.tcp_port,
                            args="\n".join(args_lines),
                            strategy_args=cat.tcp_args,
                        )
                    )

                if cat.udp_enabled and cat.has_udp():
                    args_lines = build_category_base_filter_lines(cat_name, cat.filter_mode)
                    custom_port = str(cat.udp_port or "").strip()
                    if custom_port and custom_port != "443":
                        for i, line in enumerate(args_lines):
                            if line.startswith("--filter-udp="):
                                args_lines[i] = f"--filter-udp={custom_port}"
                            elif line.startswith("--filter-l7="):
                                args_lines[i] = f"--filter-l7={custom_port}"
                    for raw in cat.udp_args.splitlines():
                        line = raw.strip()
                        if line:
                            args_lines.append(line)
                    data.categories.append(
                        CategoryBlock(
                            category=cat_name,
                            protocol="udp",
                            filter_mode=cat.filter_mode,
                            filter_file="",
                            port=cat.udp_port,
                            args="\n".join(args_lines),
                            strategy_args=cat.udp_args,
                        )
                    )

            data.deduplicate_categories()
            success = generate_preset_file(data, active_path, atomic=True)
            if success:
                self._invalidate_cache()
                log("Synced V1 preset to generated launch config", "DEBUG")
                if self._on_dpi_reload_needed:
                    self._on_dpi_reload_needed()
            return success
        except PermissionError as e:
            log(f"Cannot write V1 preset file: {e}", "ERROR")
            raise
        except Exception as e:
            log(f"Error syncing V1 preset to generated launch config: {e}", "ERROR")
            return False

    def infer_active_categories_from_launch_config(self) -> set[str]:
        present_files = self._active_list_filenames()
        if not present_files:
            return set()

        try:
            from preset_zapret2.catalog import load_categories

            categories = load_categories()
        except Exception:
            categories = {}

        present: set[str] = set()
        for key in categories.keys():
            cat_key = str(key or "").strip().lower()
            if not cat_key:
                continue
            cat_files = self._category_filter_filenames(cat_key)
            if cat_files and (cat_files & present_files):
                present.add(cat_key)
        return present

    def sync_category_preserving_layout(self, preset: PresetV1, category_key: str) -> bool:
        category_key = str(category_key or "").strip().lower()
        if not category_key:
            return False

        cat = (preset.categories or {}).get(category_key)
        active_path = get_active_preset_path_v1()

        try:
            if active_path.exists():
                content = active_path.read_text(encoding="utf-8", errors="ignore")
            else:
                content = ""

            if not content.strip():
                return self.sync_preset(preset)

            header_lines, base_lines, blocks = self._split_preset_text_sections(content)

            if not base_lines and str(getattr(preset, "base_args", "") or "").strip():
                base_lines = [ln.strip() for ln in str(preset.base_args).splitlines() if ln.strip()]

            if not header_lines:
                active_name = str(self._get_selected_name() or preset.name or "Current").strip() or "Current"
                header_lines = [
                    f"# Preset: {active_name}",
                    f"# Modified: {datetime.now().isoformat()}",
                ]

            category_filenames = self._category_filter_filenames(category_key)
            if not category_filenames:
                log(f"V1: cannot resolve list filenames for category '{category_key}', fallback to full sync", "WARNING")
                return self.sync_preset(preset)

            new_blocks: list[list[str]] = []
            for block in blocks:
                updated_block, _removed = self._remove_category_from_block(block, category_filenames)
                if updated_block:
                    new_blocks.append(updated_block)

            if cat is not None:
                category_block = self._build_single_category_block(category_key, cat)
                if category_block:
                    new_blocks.append(category_block)

            rendered = self._render_preset_text_sections(header_lines, base_lines, new_blocks)

            return self._commit_generated_launch_config_text(
                rendered,
                mirror_selected_source=True,
            )
        except PermissionError as e:
            log(f"Cannot write V1 generated launch config (locked?): {e}", "ERROR")
            raise
        except Exception as e:
            log(f"Error syncing single V1 category '{category_key}': {e}", "ERROR")
            return self.sync_preset(preset)

    def _commit_generated_launch_config_text(
        self,
        content: str,
        *,
        mirror_selected_source: bool = False,
    ) -> bool:
        active_path = get_active_preset_path_v1()
        try:
            active_path.parent.mkdir(parents=True, exist_ok=True)
            active_path.write_text(str(content or ""), encoding="utf-8")

            if mirror_selected_source:
                active_name = str(self._get_selected_name() or "").strip()
                if active_name and active_name.lower() != "current":
                    preset_path = get_preset_path_v1(active_name)
                    if preset_path.resolve() != active_path.resolve():
                        preset_path.parent.mkdir(parents=True, exist_ok=True)
                        preset_path.write_text(str(content or ""), encoding="utf-8")

            self._invalidate_cache()
            if self._on_dpi_reload_needed:
                self._on_dpi_reload_needed()
            return True
        except PermissionError as e:
            log(f"Cannot write V1 generated launch config (locked?): {e}", "ERROR")
            raise
        except Exception as e:
            log(f"Error writing V1 generated launch config: {e}", "ERROR")
            return False

    @staticmethod
    def _split_preset_text_sections(content: str) -> tuple[list[str], list[str], list[list[str]]]:
        text = (content or "").replace("\r\n", "\n").replace("\r", "\n")
        lines = text.split("\n")

        header_lines: list[str] = []
        content_start_idx = 0
        for i, raw in enumerate(lines):
            stripped = raw.strip()
            if stripped.startswith("#") or not stripped:
                header_lines.append(raw)
                content_start_idx = i + 1
                continue
            content_start_idx = i
            break
        else:
            return header_lines, [], []

        remaining = lines[content_start_idx:]
        first_filter_idx = None
        for i, raw in enumerate(remaining):
            stripped = raw.strip().lower()
            if stripped.startswith("--filter-tcp") or stripped.startswith("--filter-udp") or stripped.startswith("--filter-l7"):
                first_filter_idx = i
                break

        if first_filter_idx is None:
            base_lines = [ln.strip() for ln in remaining if ln.strip() and not ln.strip().startswith("#")]
            return header_lines, base_lines, []

        base_lines = [
            ln.strip()
            for ln in remaining[:first_filter_idx]
            if ln.strip() and not ln.strip().startswith("#")
        ]

        blocks: list[list[str]] = []
        current: list[str] = []
        for raw in remaining[first_filter_idx:]:
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped == "--new":
                if current:
                    blocks.append(current)
                    current = []
                continue
            current.append(stripped)

        if current:
            blocks.append(current)

        return header_lines, base_lines, blocks

    @staticmethod
    def _render_preset_text_sections(
        header_lines: list[str],
        base_lines: list[str],
        blocks: list[list[str]],
    ) -> str:
        lines: list[str] = []

        normalized_header = [str(ln or "").rstrip("\n") for ln in (header_lines or [])]
        if normalized_header:
            lines.extend(normalized_header)
            if normalized_header[-1].strip():
                lines.append("")

        normalized_base = [str(ln or "").strip() for ln in (base_lines or []) if str(ln or "").strip()]
        if normalized_base:
            lines.extend(normalized_base)
            lines.append("")

        clean_blocks = [
            [str(ln or "").strip() for ln in block if str(ln or "").strip()]
            for block in (blocks or [])
        ]
        clean_blocks = [block for block in clean_blocks if block]

        for i, block in enumerate(clean_blocks):
            lines.extend(block)
            if i < len(clean_blocks) - 1:
                lines.extend(["", "--new", ""])

        text = "\n".join(lines).rstrip("\n")
        return text + "\n"

    @staticmethod
    def _line_list_filename(line: str) -> tuple[str, str]:
        raw = str(line or "").strip()
        if not raw.startswith("--") or "=" not in raw:
            return "", ""

        key, _sep, value = raw.partition("=")
        key_l = key.strip().lower()
        if key_l not in ("--hostlist", "--ipset"):
            return "", ""

        value = value.strip().strip('"').strip("'")
        if value.startswith("@"):
            value = value[1:]

        return key_l, PureWindowsPath(value).name.lower()

    @classmethod
    def _block_has_target_filters(cls, block_lines: list[str]) -> bool:
        for raw in (block_lines or []):
            line = str(raw or "").strip().lower()
            if line.startswith("--hostlist=") or line.startswith("--ipset="):
                return True
            if line.startswith("--hostlist-domains=") or line.startswith("--ipset-ip="):
                return True
        return False

    @classmethod
    def _block_has_filter_start(cls, block_lines: list[str]) -> bool:
        for raw in (block_lines or []):
            line = str(raw or "").strip().lower()
            if line.startswith("--filter-tcp") or line.startswith("--filter-udp") or line.startswith("--filter-l7"):
                return True
        return False

    @classmethod
    def _remove_category_from_block(
        cls,
        block_lines: list[str],
        category_filenames: set[str],
    ) -> tuple[list[str], bool]:
        if not category_filenames:
            return list(block_lines or []), False

        out: list[str] = []
        removed = False
        for raw in (block_lines or []):
            key_l, filename = cls._line_list_filename(raw)
            if key_l and filename and filename in category_filenames:
                removed = True
                continue
            out.append(str(raw or "").strip())

        out = [ln for ln in out if ln]
        if removed:
            if not cls._block_has_filter_start(out):
                return [], True
            if not cls._block_has_target_filters(out):
                return [], True
        return out, removed

    def _category_filter_filenames(self, category_key: str) -> set[str]:
        from preset_zapret2.base_filter import build_category_base_filter_lines

        names: set[str] = set()
        for mode in ("hostlist", "ipset"):
            try:
                for raw in build_category_base_filter_lines(category_key, mode):
                    _k, filename = self._line_list_filename(raw)
                    if filename:
                        names.add(filename)
            except Exception:
                continue
        return names

    def _active_list_filenames(self) -> set[str]:
        path = get_active_preset_path_v1()
        if not path.exists():
            return set()

        names: set[str] = set()
        try:
            for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                _k, filename = self._line_list_filename(raw)
                if filename:
                    names.add(filename)
        except Exception:
            return set()
        return names

    @staticmethod
    def _category_is_udp_like(category_key: str) -> bool:
        try:
            from preset_zapret2.catalog import load_categories

            info = load_categories().get(category_key) or {}
            protocol = str(info.get("protocol") or "").upper()
            return any(token in protocol for token in ("UDP", "QUIC", "L7", "RAW"))
        except Exception:
            return False

    def _build_single_category_block(self, category_key: str, cat: CategoryConfigV1) -> list[str]:
        from preset_zapret2.base_filter import build_category_base_filter_lines

        tcp_args = str(getattr(cat, "tcp_args", "") or "").strip()
        udp_args = str(getattr(cat, "udp_args", "") or "").strip()

        if not tcp_args and not udp_args:
            return []

        if udp_args and not tcp_args:
            use_udp = True
            strategy_text = udp_args
            custom_port = str(getattr(cat, "udp_port", "") or "").strip()
        elif tcp_args and not udp_args:
            use_udp = False
            strategy_text = tcp_args
            custom_port = str(getattr(cat, "tcp_port", "") or "").strip()
        else:
            use_udp = self._category_is_udp_like(category_key)
            strategy_text = udp_args if use_udp else tcp_args
            custom_port = str(
                (getattr(cat, "udp_port", "") if use_udp else getattr(cat, "tcp_port", "")) or ""
            ).strip()

        lines = build_category_base_filter_lines(category_key, getattr(cat, "filter_mode", "hostlist") or "hostlist")
        if not lines:
            log(f"V1: base_filter lines not found for category '{category_key}'", "WARNING")
            return []

        if custom_port:
            for i, line in enumerate(lines):
                low = line.lower()
                if use_udp and low.startswith("--filter-udp="):
                    lines[i] = f"--filter-udp={custom_port}"
                elif use_udp and low.startswith("--filter-l7="):
                    lines[i] = f"--filter-l7={custom_port}"
                elif (not use_udp) and low.startswith("--filter-tcp="):
                    lines[i] = f"--filter-tcp={custom_port}"

        for raw in strategy_text.splitlines():
            line = raw.strip()
            if line:
                lines.append(line)

        return lines
