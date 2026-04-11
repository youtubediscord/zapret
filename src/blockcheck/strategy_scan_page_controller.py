from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ui.text_catalog import tr as tr_catalog
from ui.support_request_actions import prepare_strategy_scan_support_request


@dataclass(slots=True)
class StrategyScanRunLogState:
    path: Path | None
    created: bool


@dataclass(slots=True)
class StrategyApplyResult:
    strategy_name: str
    applied_target: str
    selected_file_name: str


@dataclass(slots=True)
class StrategyScanStartPlan:
    target: str
    scan_protocol: str
    udp_games_scope: str
    mode: str
    resume_next_index: int
    resume_available: bool
    keep_current_results: bool
    scan_cursor: int
    status_text: str


@dataclass(slots=True)
class StrategyScanFinishPlan:
    total_available: int
    working_count: int
    total_count: int
    cancelled: bool
    baseline_accessible: bool
    status_text: str
    log_message: str | None
    support_status_code: str
    notification_kind: str
    baseline_variant: str


@dataclass(slots=True)
class StrategyScanProgressPlan:
    total: int
    working_count: int
    status_text: str


@dataclass(slots=True)
class StrategyScanResultPresentation:
    number_text: str
    strategy_name: str
    strategy_tooltip: str
    status_text: str
    status_tone: str
    status_tooltip: str
    time_text: str
    can_apply: bool
    stored_row: dict[str, object]


@dataclass(slots=True)
class StrategyScanNotificationPlan:
    kind: str
    title_key: str
    title_default: str
    body_key: str
    body_default: str
    body_text: str


@dataclass(slots=True)
class StrategyScanProtocolUiPlan:
    scan_protocol: str
    is_udp_games: bool
    show_target_controls: bool
    normalized_target: str
    placeholder_text: str


@dataclass(slots=True)
class StrategyScanUdpHintPlan:
    visible: bool
    text: str
    tooltip: str


@dataclass(slots=True)
class StrategyScanQuickMenuPlan:
    options: list[str]
    current_value: str


@dataclass(slots=True)
class StrategyScanInteractionPlan:
    start_enabled: bool
    stop_enabled: bool
    protocol_enabled: bool
    games_scope_enabled: bool
    mode_enabled: bool
    target_enabled: bool
    quick_domain_enabled: bool


@dataclass(slots=True)
class StrategyScanLogExpandPlan:
    control_visible: bool
    warning_visible: bool
    results_visible: bool
    log_min_height: int
    log_max_height: int
    button_text: str


@dataclass(slots=True)
class StrategyScanLanguagePlan:
    control_title: str
    results_title: str
    log_title: str
    expand_log_text: str
    warning_title: str
    start_text: str
    stop_text: str
    prepare_support_text: str
    protocol_items: list[str]
    udp_scope_label: str
    udp_scope_items: list[str]
    quick_domains_text: str
    quick_domains_tooltip: str


@dataclass(slots=True)
class StrategyScanUiMessagePlan:
    kind: str
    title_key: str
    title_default: str
    body_text: str
    status_text: str = ""


@dataclass(slots=True)
class StrategyScanSelectionState:
    scan_protocol: str
    udp_games_scope: str
    mode: str


@dataclass(slots=True)
class StrategyScanSupportContext:
    scan_protocol: str
    target: str
    protocol_label: str
    mode_label: str


class StrategyScanPageController:
    _quick_domains_cache: list[str] | None = None
    _quick_stun_targets_cache: list[str] | None = None

    @staticmethod
    def scan_protocol_from_value(value) -> str:
        raw = str(value or "").strip().lower()
        if raw == "stun_voice":
            return "stun_voice"
        if raw == "udp_games":
            return "udp_games"
        return "tcp_https"

    @staticmethod
    def mode_from_index(index: int) -> str:
        mode_map = {0: "quick", 1: "standard", 2: "full"}
        return mode_map.get(int(index), "quick")

    @classmethod
    def build_selection_state(
        cls,
        *,
        protocol_value,
        udp_scope_value,
        mode_index: int,
    ) -> StrategyScanSelectionState:
        scan_protocol = cls.scan_protocol_from_value(protocol_value)
        udp_games_scope = (
            cls.normalize_udp_games_scope(udp_scope_value)
            if scan_protocol == "udp_games"
            else "all"
        )
        return StrategyScanSelectionState(
            scan_protocol=scan_protocol,
            udp_games_scope=udp_games_scope,
            mode=cls.mode_from_index(mode_index),
        )

    @staticmethod
    def normalize_udp_games_scope(scope: str) -> str:
        raw = (scope or "").strip().lower()
        if raw in {"games_only", "games", "only_games", "targeted"}:
            return "games_only"
        return "all"

    @staticmethod
    def default_target_for_protocol(scan_protocol: str) -> str:
        protocol = (scan_protocol or "").strip().lower()
        if protocol == "stun_voice":
            return "stun.l.google.com:19302"
        if protocol == "udp_games":
            return "stun.cloudflare.com:3478"
        return "discord.com"

    @staticmethod
    def stun_target_parts(value: str, default_port: int = 3478) -> tuple[str, int]:
        raw = (value or "").strip()
        if not raw:
            return "", default_port

        if raw.upper().startswith("STUN:"):
            raw = raw[5:].strip()

        raw = re.sub(r"^https?://", "", raw, flags=re.IGNORECASE)
        raw = raw.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].strip()
        if not raw:
            return "", default_port

        if raw.startswith("["):
            right = raw.find("]")
            if right > 1:
                host = raw[1:right].strip()
                rest = raw[right + 1 :].strip()
                if rest.startswith(":"):
                    try:
                        port = int(rest[1:])
                        if 1 <= port <= 65535:
                            return host, port
                    except ValueError:
                        pass
                return host, default_port

        if raw.count(":") == 1:
            host, port_str = raw.rsplit(":", 1)
            host = host.strip()
            if host:
                try:
                    port = int(port_str)
                    if 1 <= port <= 65535:
                        return host, port
                except ValueError:
                    pass
                return host, default_port

        return raw, default_port

    @staticmethod
    def format_stun_target(host: str, port: int) -> str:
        host = (host or "").strip()
        if not host:
            return ""
        if ":" in host and not host.startswith("["):
            return f"[{host}]:{int(port)}"
        return f"{host}:{int(port)}"

    @staticmethod
    def normalize_target_domain(value: str) -> str:
        raw = (value or "").strip()
        if not raw:
            return ""
        try:
            from blockcheck.targets import _normalize_domain

            return _normalize_domain(raw)
        except Exception:
            return raw.lower()

    @classmethod
    def normalize_target_input(cls, value: str, scan_protocol: str) -> str:
        protocol = (scan_protocol or "").strip().lower()
        if protocol in {"stun_voice", "udp_games"}:
            host, port = cls.stun_target_parts(value)
            if not host:
                return ""
            return cls.format_stun_target(host, port)
        return cls.normalize_target_domain(value)

    @classmethod
    def resolve_games_ipset_paths(cls, udp_games_scope: str = "all") -> list[str]:
        scope = cls.normalize_udp_games_scope(udp_games_scope)

        explicit_game_files = (
            "ipset-roblox.txt",
            "ipset-amazon.txt",
            "ipset-steam.txt",
            "ipset-epicgames.txt",
            "ipset-epic.txt",
            "ipset-lol-ru.txt",
            "ipset-lol-euw.txt",
            "ipset-tankix.txt",
        )

        list_dirs: list[Path] = []

        appdata = (os.environ.get("APPDATA") or "").strip()
        if appdata:
            list_dirs.extend(
                [
                    Path(appdata) / "ZapretTwoDev" / "lists",
                    Path(appdata) / "ZapretTwo" / "lists",
                ]
            )

        try:
            from config import APPDATA_DIR, get_zapret_userdata_dir

            app_channel_dir = (APPDATA_DIR or "").strip()
            if app_channel_dir:
                list_dirs.append(Path(app_channel_dir) / "lists")

            user_data_dir = (get_zapret_userdata_dir() or "").strip()
            if user_data_dir:
                list_dirs.append(Path(user_data_dir) / "lists")
        except Exception:
            pass

        try:
            from config import MAIN_DIRECTORY

            list_dirs.append(Path(MAIN_DIRECTORY) / "lists")
        except Exception:
            list_dirs.append(Path.cwd() / "lists")

        files: list[str] = []
        seen: set[str] = set()
        for base_dir in list_dirs:
            if scope == "all":
                ipset_all = base_dir / "ipset-all.txt"
                key_all = str(ipset_all)
                if key_all not in seen:
                    seen.add(key_all)
                    if ipset_all.exists():
                        return [str(ipset_all)]

            for filename in explicit_game_files:
                candidate = base_dir / filename
                key = str(candidate)
                if key in seen:
                    continue
                seen.add(key)
                if candidate.exists():
                    files.append(str(candidate))

            if scope == "games_only":
                continue

            try:
                for candidate in sorted(base_dir.glob("ipset-*.txt")):
                    key = str(candidate)
                    if key in seen:
                        continue
                    seen.add(key)
                    if candidate.exists():
                        files.append(str(candidate))
            except OSError:
                continue

        if files:
            return files

        if scope == "games_only":
            return ["lists/ipset-roblox.txt"]
        return ["lists/ipset-all.txt"]

    @classmethod
    def load_quick_domains(cls) -> list[str]:
        if cls._quick_domains_cache is not None:
            return list(cls._quick_domains_cache)

        try:
            from blockcheck.targets import load_domains

            raw_domains = load_domains()
        except Exception:
            raw_domains = []

        normalized_domains: list[str] = []
        seen: set[str] = set()
        for raw in raw_domains:
            domain = cls.normalize_target_domain(str(raw))
            if not domain or domain in seen:
                continue
            seen.add(domain)
            normalized_domains.append(domain)

        cls._quick_domains_cache = normalized_domains
        return list(cls._quick_domains_cache)

    @classmethod
    def load_quick_stun_targets(cls) -> list[str]:
        if cls._quick_stun_targets_cache is not None:
            return list(cls._quick_stun_targets_cache)

        try:
            from blockcheck.targets import get_default_stun_targets

            raw_targets = get_default_stun_targets()
        except Exception:
            raw_targets = []

        targets: list[str] = []
        seen: set[str] = set()
        for item in raw_targets:
            value = str(item.get("value", ""))
            normalized = cls.normalize_target_input(value, "stun_voice")
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            targets.append(normalized)

        cls._quick_stun_targets_cache = targets
        return list(cls._quick_stun_targets_cache)

    @classmethod
    def build_protocol_ui_plan(cls, *, scan_protocol: str, current_value: str) -> StrategyScanProtocolUiPlan:
        current = str(current_value or "")
        is_udp_games = scan_protocol == "udp_games"
        show_target_controls = scan_protocol != "udp_games"

        if scan_protocol in {"stun_voice", "udp_games"} and current and ":" not in current and not current.upper().startswith("STUN:"):
            current = ""

        normalized = cls.normalize_target_input(current, scan_protocol)
        if not normalized:
            normalized = cls.default_target_for_protocol(scan_protocol)

        return StrategyScanProtocolUiPlan(
            scan_protocol=scan_protocol,
            is_udp_games=is_udp_games,
            show_target_controls=show_target_controls,
            normalized_target=normalized,
            placeholder_text=cls.default_target_for_protocol(scan_protocol),
        )

    @classmethod
    def build_udp_scope_hint_plan(
        cls,
        *,
        scan_protocol: str,
        udp_games_scope: str,
        scope_all_label: str,
        scope_games_only_label: str,
    ) -> StrategyScanUdpHintPlan:
        if scan_protocol != "udp_games":
            return StrategyScanUdpHintPlan(
                visible=False,
                text="",
                tooltip="",
            )

        paths = cls.resolve_games_ipset_paths(udp_games_scope)
        scope_label = scope_games_only_label if udp_games_scope == "games_only" else scope_all_label

        short_names = [Path(p).name or p for p in paths]
        preview = ", ".join(short_names[:4])
        if len(short_names) > 4:
            preview += f", ... (+{len(short_names) - 4})"

        return StrategyScanUdpHintPlan(
            visible=True,
            text=f"UDP scope: {scope_label} | ipset files: {len(paths)} | {preview}",
            tooltip="\n".join(paths),
        )

    @classmethod
    def build_quick_target_menu_plan(cls, *, scan_protocol: str, current_value: str) -> StrategyScanQuickMenuPlan:
        current = cls.normalize_target_input(current_value, scan_protocol)
        options = cls.load_quick_domains() if scan_protocol == "tcp_https" else cls.load_quick_stun_targets()
        return StrategyScanQuickMenuPlan(
            options=options,
            current_value=current,
        )

    @staticmethod
    def build_running_interaction_plan() -> StrategyScanInteractionPlan:
        return StrategyScanInteractionPlan(
            start_enabled=False,
            stop_enabled=True,
            protocol_enabled=False,
            games_scope_enabled=False,
            mode_enabled=False,
            target_enabled=False,
            quick_domain_enabled=False,
        )

    @staticmethod
    def build_idle_interaction_plan(*, is_udp_games: bool) -> StrategyScanInteractionPlan:
        return StrategyScanInteractionPlan(
            start_enabled=True,
            stop_enabled=False,
            protocol_enabled=True,
            games_scope_enabled=bool(is_udp_games),
            mode_enabled=True,
            target_enabled=True,
            quick_domain_enabled=True,
        )

    @staticmethod
    def build_log_expand_plan(*, expanded: bool, language: str) -> StrategyScanLogExpandPlan:
        if expanded:
            return StrategyScanLogExpandPlan(
                control_visible=False,
                warning_visible=False,
                results_visible=False,
                log_min_height=400,
                log_max_height=16777215,
                button_text=tr_catalog("page.strategy_scan.collapse_log", language=language, default="Свернуть"),
            )
        return StrategyScanLogExpandPlan(
            control_visible=True,
            warning_visible=True,
            results_visible=True,
            log_min_height=180,
            log_max_height=300,
            button_text=tr_catalog("page.strategy_scan.expand_log", language=language, default="Развернуть"),
        )

    @staticmethod
    def build_language_plan(*, language: str, log_expanded: bool) -> StrategyScanLanguagePlan:
        return StrategyScanLanguagePlan(
            control_title=tr_catalog("page.strategy_scan.control", language=language, default="Управление сканированием"),
            results_title=tr_catalog("page.strategy_scan.results", language=language, default="Результаты"),
            log_title=tr_catalog("page.strategy_scan.log", language=language, default="Подробный лог"),
            expand_log_text=(
                tr_catalog("page.strategy_scan.collapse_log", language=language, default="Свернуть")
                if log_expanded
                else tr_catalog("page.strategy_scan.expand_log", language=language, default="Развернуть")
            ),
            warning_title=tr_catalog("page.strategy_scan.warning_title", language=language, default="Внимание"),
            start_text=tr_catalog("page.strategy_scan.start", language=language, default="Начать сканирование"),
            stop_text=tr_catalog("page.strategy_scan.stop", language=language, default="Остановить"),
            prepare_support_text=tr_catalog(
                "page.strategy_scan.prepare_support",
                language=language,
                default="Подготовить обращение",
            ),
            protocol_items=[
                tr_catalog("page.strategy_scan.protocol_tcp", language=language, default="TCP/HTTPS"),
                tr_catalog(
                    "page.strategy_scan.protocol_stun",
                    language=language,
                    default="STUN Voice (Discord/Telegram)",
                ),
                tr_catalog(
                    "page.strategy_scan.protocol_games",
                    language=language,
                    default="UDP Games (Roblox/Amazon/Steam)",
                ),
            ],
            udp_scope_label=tr_catalog("page.strategy_scan.udp_scope", language=language, default="Охват UDP:"),
            udp_scope_items=[
                tr_catalog(
                    "page.strategy_scan.udp_scope_all",
                    language=language,
                    default="Все ipset (по умолчанию)",
                ),
                tr_catalog(
                    "page.strategy_scan.udp_scope_games_only",
                    language=language,
                    default="Только игровые ipset",
                ),
            ],
            quick_domains_text=tr_catalog("page.strategy_scan.quick_domains", language=language, default="Быстрый выбор"),
            quick_domains_tooltip=tr_catalog(
                "page.strategy_scan.quick_domains_hint",
                language=language,
                default="Выберите домен из готового списка",
            ),
        )

    @staticmethod
    def build_apply_success_plan(result: StrategyApplyResult) -> StrategyScanUiMessagePlan:
        return StrategyScanUiMessagePlan(
            kind="success",
            title_key="page.strategy_scan.applied",
            title_default="Стратегия добавлена",
            body_text=f"{result.strategy_name} добавлена в пресет для {result.applied_target}",
        )

    @staticmethod
    def build_apply_error_plan(error_text: str) -> StrategyScanUiMessagePlan:
        return StrategyScanUiMessagePlan(
            kind="warning",
            title_key="common.error",
            title_default="Ошибка",
            body_text=str(error_text or ""),
        )

    @staticmethod
    def build_support_success_plan(feedback) -> StrategyScanUiMessagePlan:
        return StrategyScanUiMessagePlan(
            kind="success",
            title_key="page.strategy_scan.support_prepared_title",
            title_default="Обращение подготовлено",
            body_text=str(getattr(feedback, "info_text", "") or ""),
            status_text=str(getattr(feedback, "status_text", "") or ""),
        )

    @staticmethod
    def build_support_error_plan(error_text: str) -> StrategyScanUiMessagePlan:
        return StrategyScanUiMessagePlan(
            kind="warning",
            title_key="page.strategy_scan.error",
            title_default="Ошибка сканирования",
            body_text=f"Не удалось подготовить обращение:\n{error_text}",
            status_text="Ошибка подготовки",
        )

    @classmethod
    def build_support_context(
        cls,
        *,
        stored_scan_protocol: str,
        stored_scan_target: str,
        raw_protocol_value,
        raw_target_input: str,
        raw_protocol_label: str,
        raw_mode_label: str,
        stored_mode: str,
    ) -> StrategyScanSupportContext:
        scan_protocol = stored_scan_protocol or cls.scan_protocol_from_value(raw_protocol_value)
        target = stored_scan_target or cls.normalize_target_input(raw_target_input, scan_protocol)
        if not target:
            target = cls.default_target_for_protocol(scan_protocol)

        protocol_label = str(raw_protocol_label or "").strip() or scan_protocol
        mode_label = str(raw_mode_label or "").strip() or str(stored_mode or "")
        return StrategyScanSupportContext(
            scan_protocol=scan_protocol,
            target=target,
            protocol_label=protocol_label,
            mode_label=mode_label,
        )

    @staticmethod
    def count_working_results(result_rows: list[dict]) -> int:
        return sum(1 for row in result_rows if row.get("success"))

    @classmethod
    def build_progress_plan(
        cls,
        *,
        strategy_name: str,
        index: int,
        total: int,
        result_rows: list[dict],
    ) -> StrategyScanProgressPlan:
        working = cls.count_working_results(result_rows)
        return StrategyScanProgressPlan(
            total=max(0, int(total)),
            working_count=working,
            status_text=f"[{index + 1}/{total}] {strategy_name}  |  {working} рабочих",
        )

    @staticmethod
    def build_result_presentation(result, *, scan_cursor: int) -> StrategyScanResultPresentation:
        tip_parts = [result.strategy_args]
        if result.error:
            tip_parts.append(f"\n--- Ошибка ---\n{result.error}")

        error_text = str(getattr(result, "error", "") or "")
        error_lower = error_text.lower()
        if result.success:
            status_text = "OK"
            status_tone = "success"
        elif "timeout" in error_lower:
            status_text = "TIMEOUT"
            status_tone = "timeout"
        else:
            status_text = "FAIL"
            status_tone = "fail"

        time_ms = float(getattr(result, "time_ms", 0) or 0)
        time_text = f"{time_ms:.0f}" if time_ms > 0 else "—"

        return StrategyScanResultPresentation(
            number_text=str(scan_cursor + 1),
            strategy_name=result.strategy_name,
            strategy_tooltip="".join(tip_parts),
            status_text=status_text,
            status_tone=status_tone,
            status_tooltip=error_text if error_text else "OK",
            time_text=time_text,
            can_apply=bool(result.success),
            stored_row={
                "id": getattr(result, "strategy_id", ""),
                "name": result.strategy_name,
                "args": result.strategy_args,
                "success": bool(result.success),
            },
        )

    @classmethod
    def plan_scan_start(
        cls,
        *,
        raw_target_input: str,
        scan_protocol: str,
        udp_games_scope: str,
        mode: str,
        previous_target: str,
        previous_protocol: str,
        previous_scope: str,
        result_rows_count: int,
        table_row_count: int,
        starting_status_text: str,
    ) -> StrategyScanStartPlan:
        target = cls.normalize_target_input(raw_target_input, scan_protocol)
        if not target:
            target = cls.default_target_for_protocol(scan_protocol)

        prev_target_key = cls.target_key(previous_target, previous_protocol, previous_scope)
        target_key = cls.target_key(target, scan_protocol, udp_games_scope)

        resume_next_index = cls.get_resume_index(target, scan_protocol, udp_games_scope)
        resume_available = resume_next_index > 0

        keep_current_results = (
            resume_available
            and previous_protocol == scan_protocol
            and previous_scope == udp_games_scope
            and prev_target_key == target_key
            and result_rows_count == resume_next_index
            and table_row_count == result_rows_count
        )

        scan_cursor = resume_next_index if resume_available else 0
        if resume_available:
            status_text = f"Возобновление сканирования с [{scan_cursor + 1}]..."
        else:
            status_text = starting_status_text

        return StrategyScanStartPlan(
            target=target,
            scan_protocol=scan_protocol,
            udp_games_scope=udp_games_scope,
            mode=mode,
            resume_next_index=resume_next_index,
            resume_available=resume_available,
            keep_current_results=keep_current_results,
            scan_cursor=scan_cursor,
            status_text=status_text,
        )

    @staticmethod
    def resume_state_path() -> Path:
        try:
            from config import APPDATA_DIR

            base_dir = Path(APPDATA_DIR)
        except Exception:
            try:
                from config import MAIN_DIRECTORY

                base_dir = Path(MAIN_DIRECTORY)
            except Exception:
                base_dir = Path.cwd()
        return base_dir / "strategy_scan_resume.json"

    @staticmethod
    def target_key(
        target: str,
        scan_protocol: str = "tcp_https",
        udp_games_scope: str = "all",
    ) -> str:
        normalized_target = (target or "").strip().lower()
        normalized_protocol = (scan_protocol or "tcp_https").strip().lower() or "tcp_https"
        if not normalized_target:
            return ""

        if normalized_protocol == "udp_games":
            scope = (udp_games_scope or "all").strip().lower()
            if scope not in {"all", "games_only"}:
                scope = "all"
            return f"{normalized_protocol}|{scope}|{normalized_target}"

        return f"{normalized_protocol}|{normalized_target}"

    @classmethod
    def load_resume_state(cls) -> dict:
        path = cls.resume_state_path()
        empty_state = {"domains": {}}
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                return empty_state

            domains = data.get("domains")
            if isinstance(domains, dict):
                cleaned_domains = {}
                for raw_key, raw_value in domains.items():
                    raw_key_str = str(raw_key).strip().lower()
                    if not raw_key_str:
                        continue
                    if "|" in raw_key_str:
                        parts = raw_key_str.split("|")
                        if len(parts) == 2 and parts[0] == "udp_games":
                            key = f"udp_games|all|{parts[1]}"
                        else:
                            key = raw_key_str
                    else:
                            key = cls.target_key(raw_key_str, "tcp_https")
                    if not key:
                        continue
                    if isinstance(raw_value, dict):
                        raw_index = raw_value.get("next_index", 0)
                    else:
                        raw_index = raw_value
                    try:
                        next_index = max(0, int(raw_index))
                    except Exception:
                        next_index = 0
                    cleaned_domains[key] = {"next_index": next_index}
                return {"domains": cleaned_domains}

            key = cls.target_key(str(data.get("target", "") or ""))
            try:
                next_index = max(0, int(data.get("next_index", 0) or 0))
            except Exception:
                next_index = 0
            if key and next_index > 0:
                return {"domains": {key: {"next_index": next_index}}}
            return empty_state
        except Exception:
            return empty_state

    @classmethod
    def write_resume_state(cls, state: dict) -> None:
        path = cls.resume_state_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    @classmethod
    def get_resume_index(cls, target: str, scan_protocol: str, udp_games_scope: str = "all") -> int:
        key = cls.target_key(target, scan_protocol, udp_games_scope)
        if not key:
            return 0
        state = cls.load_resume_state()
        domains = state.get("domains", {})
        entry = domains.get(key, {})

        if not entry and (scan_protocol or "").strip().lower() == "udp_games":
            legacy_key = f"udp_games|{(target or '').strip().lower()}"
            entry = domains.get(legacy_key, {})

        if not entry and (scan_protocol or "").strip().lower() == "tcp_https":
            legacy_key = (target or "").strip().lower()
            entry = domains.get(legacy_key, {})
        try:
            return max(0, int(entry.get("next_index", 0) or 0))
        except Exception:
            return 0

    @classmethod
    def save_resume_state(
        cls,
        target: str,
        scan_protocol: str,
        next_index: int,
        udp_games_scope: str = "all",
    ) -> None:
        key = cls.target_key(target, scan_protocol, udp_games_scope)
        if not key:
            return
        state = cls.load_resume_state()
        domains = state.setdefault("domains", {})
        domains[key] = {"next_index": max(0, int(next_index))}
        cls.write_resume_state(state)

    @classmethod
    def clear_resume_state(cls, target: str, scan_protocol: str, udp_games_scope: str = "all") -> None:
        key = cls.target_key(target, scan_protocol, udp_games_scope)
        if not key:
            return
        state = cls.load_resume_state()
        domains = state.get("domains", {})
        if key in domains:
            del domains[key]

        if (scan_protocol or "").strip().lower() == "udp_games":
            legacy_key = f"udp_games|{(target or '').strip().lower()}"
            if legacy_key in domains:
                del domains[legacy_key]

        if (scan_protocol or "").strip().lower() == "tcp_https":
            legacy_key = (target or "").strip().lower()
            if legacy_key in domains:
                del domains[legacy_key]

        if domains:
            state["domains"] = domains
            cls.write_resume_state(state)
        else:
            path = cls.resume_state_path()
            try:
                if path.exists():
                    path.unlink()
            except Exception:
                pass

    @staticmethod
    def _sanitize_slug(value: str, fallback: str) -> str:
        raw = (value or "").strip().lower()
        cleaned = "".join(ch if (ch.isalnum() or ch in ("_", "-")) else "_" for ch in raw)
        cleaned = cleaned.strip("_")
        return cleaned or fallback

    @staticmethod
    def _resolve_log_dir() -> Path:
        try:
            from config import LOGS_FOLDER

            log_dir = Path(LOGS_FOLDER)
        except Exception:
            log_dir = Path.cwd() / "logs"

        try:
            from log import global_logger

            active_log = getattr(global_logger, "log_file", None)
            if isinstance(active_log, str) and active_log.strip():
                resolved_dir = Path(active_log).parent
                if str(resolved_dir):
                    log_dir = resolved_dir
        except Exception:
            pass

        return log_dir

    @classmethod
    def make_run_log_path(
        cls,
        target: str,
        mode: str,
        scan_protocol: str,
        udp_games_scope: str = "all",
    ) -> Path:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        safe_mode = cls._sanitize_slug(mode, "mode")
        safe_protocol = cls._sanitize_slug(scan_protocol, "protocol")
        safe_scope = cls._sanitize_slug(udp_games_scope, "scope")
        safe_target = cls._sanitize_slug(target, "target")
        scope_suffix = f"_{safe_scope}" if scan_protocol == "udp_games" else ""
        filename = (
            f"blockcheck_run_{ts}_strategy_scan_{safe_mode}_{safe_protocol}"
            f"{scope_suffix}_{safe_target}.log"
        )
        return cls._resolve_log_dir() / filename

    @classmethod
    def start_run_log(
        cls,
        *,
        target: str,
        mode: str,
        scan_protocol: str,
        resume_index: int,
        udp_games_scope: str = "all",
    ) -> StrategyScanRunLogState:
        primary_path = cls.make_run_log_path(
            target=target,
            mode=mode,
            scan_protocol=scan_protocol,
            udp_games_scope=udp_games_scope,
        )
        candidates = [primary_path]

        try:
            from config import APPDATA_DIR

            candidates.append(Path(APPDATA_DIR) / "logs" / primary_path.name)
        except Exception:
            pass

        candidates.append(Path.cwd() / "logs" / primary_path.name)

        tried: set[Path] = set()
        for path in candidates:
            if path in tried:
                continue
            tried.add(path)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("w", encoding="utf-8-sig") as f:
                    f.write(f"=== Strategy Scan Run Log ({datetime.now():%Y-%m-%d %H:%M:%S}) ===\n")
                    f.write(f"Mode: {mode}\n")
                    f.write(f"Protocol: {scan_protocol}\n")
                    if scan_protocol == "udp_games":
                        f.write(f"UDP games scope: {udp_games_scope}\n")
                    f.write(f"Target: {target}\n")
                    f.write(f"Resume index: {max(0, int(resume_index))}\n")
                    f.write("=" * 70 + "\n\n")
                return StrategyScanRunLogState(path=path, created=True)
            except Exception:
                continue

        return StrategyScanRunLogState(path=None, created=False)

    @staticmethod
    def append_run_log(path: Path | None, message: str) -> None:
        if path is None:
            return
        try:
            text = str(message or "")
            if not text.endswith("\n"):
                text += "\n"
            with path.open("a", encoding="utf-8-sig") as f:
                f.write(text)
        except Exception:
            pass

    @classmethod
    def prepare_support(
        cls,
        *,
        run_log_file: Path | None,
        target: str,
        protocol_label: str,
        mode_label: str,
        scan_protocol: str,
    ):
        return prepare_strategy_scan_support_request(
            run_log_file=str(run_log_file) if run_log_file is not None else None,
            target=target,
            protocol_label=protocol_label,
            mode_label=mode_label,
            resume_state_path=cls.resume_state_path(),
            scan_protocol=scan_protocol,
        )

    @classmethod
    def finalize_scan_report(
        cls,
        report,
        *,
        scan_target: str,
        scan_protocol: str,
        scan_udp_games_scope: str,
        scan_mode: str,
        scan_cursor: int,
        result_rows: list[dict],
    ) -> StrategyScanFinishPlan:
        working = sum(1 for row in result_rows if row.get("success"))

        if report is None:
            if scan_cursor > 0:
                cls.save_resume_state(
                    scan_target,
                    scan_protocol,
                    scan_cursor,
                    scan_udp_games_scope,
                )
            return StrategyScanFinishPlan(
                total_available=0,
                working_count=working,
                total_count=scan_cursor,
                cancelled=False,
                baseline_accessible=False,
                status_text="Ошибка сканирования",
                log_message="ERROR: Strategy scan execution failed",
                support_status_code="ready_after_error",
                notification_kind="none",
                baseline_variant="stun" if scan_protocol in {"stun_voice", "udp_games"} else "tcp",
            )

        total_available = max(0, int(getattr(report, "total_available", 0) or 0))

        if report.cancelled:
            if scan_cursor > 0:
                cls.save_resume_state(
                    scan_target,
                    scan_protocol,
                    scan_cursor,
                    scan_udp_games_scope,
                )
            else:
                cls.clear_resume_state(
                    scan_target,
                    scan_protocol,
                    scan_udp_games_scope,
                )
        else:
            full_scan_completed = (
                scan_mode == "full"
                and total_available > 0
                and report.total_tested >= total_available
            )
            if full_scan_completed:
                cls.clear_resume_state(
                    scan_target,
                    scan_protocol,
                    scan_udp_games_scope,
                )
            else:
                cls.save_resume_state(
                    scan_target,
                    scan_protocol,
                    report.total_tested,
                    scan_udp_games_scope,
                )

        total_count = max(scan_cursor, report.total_tested)
        elapsed = report.elapsed_seconds

        if report.cancelled:
            status_text = f"Отменено. Протестировано: {total_count}, рабочих: {working} ({elapsed:.1f}s)"
        else:
            status_text = f"Готово. Протестировано: {total_count}, рабочих: {working} ({elapsed:.1f}s)"

        if report.baseline_accessible:
            notification_kind = "baseline_accessible"
        elif working > 0:
            notification_kind = "found"
        else:
            notification_kind = "not_found"

        return StrategyScanFinishPlan(
            total_available=total_available,
            working_count=working,
            total_count=total_count,
            cancelled=bool(report.cancelled),
            baseline_accessible=bool(report.baseline_accessible),
            status_text=status_text,
            log_message=f"\n{status_text}",
            support_status_code="ready",
            notification_kind=notification_kind,
            baseline_variant="stun" if scan_protocol in {"stun_voice", "udp_games"} else "tcp",
        )

    @staticmethod
    def build_finish_notification_plan(finish_plan: StrategyScanFinishPlan, *, scan_protocol: str) -> StrategyScanNotificationPlan:
        if finish_plan.notification_kind == "baseline_accessible":
            if scan_protocol == "udp_games":
                title_default = "UDP уже доступен"
            elif finish_plan.baseline_variant == "stun":
                title_default = "STUN уже доступен"
            else:
                title_default = "Домен уже доступен"

            if finish_plan.baseline_variant == "stun":
                return StrategyScanNotificationPlan(
                    kind="warning",
                    title_key="page.strategy_scan.baseline_ok_title_stun",
                    title_default=title_default,
                    body_key="page.strategy_scan.baseline_ok_text_stun",
                    body_default="STUN/UDP уже доступен без обхода DPI — результаты могут быть ложноположительными",
                    body_text="",
                )

            return StrategyScanNotificationPlan(
                kind="warning",
                title_key="page.strategy_scan.baseline_ok_title",
                title_default=title_default,
                body_key="page.strategy_scan.baseline_ok_text",
                body_default="Домен доступен без обхода DPI — результаты могут быть ложноположительными",
                body_text="",
            )

        if finish_plan.notification_kind == "found":
            return StrategyScanNotificationPlan(
                kind="success",
                title_key="page.strategy_scan.found",
                title_default="Найдены рабочие стратегии",
                body_key="",
                body_default="",
                body_text=f"{finish_plan.working_count} из {finish_plan.total_count}",
            )

        if finish_plan.notification_kind == "not_found":
            return StrategyScanNotificationPlan(
                kind="warning",
                title_key="page.strategy_scan.not_found",
                title_default="Рабочих стратегий не найдено",
                body_key="page.strategy_scan.try_full",
                body_default="Попробуйте полный режим сканирования",
                body_text="",
            )

        return StrategyScanNotificationPlan(
            kind="none",
            title_key="",
            title_default="",
            body_key="",
            body_default="",
            body_text="",
        )

    @staticmethod
    def generate_blob_lines_for_apply(strategy_args: str) -> list[str]:
        try:
            from launcher_common.blobs import find_used_blobs, get_blobs

            used = find_used_blobs(strategy_args)
            if not used:
                return []
            blobs = get_blobs()
            return [f"--blob={name}:{blobs[name]}" for name in sorted(used) if name in blobs]
        except Exception:
            return []

    @staticmethod
    def prepend_strategy_block(existing_content: str, strategy_lines: list[str], blob_lines: list[str]) -> str:
        normalized = (existing_content or "").replace("\r\n", "\n").replace("\r", "\n")
        all_lines = normalized.split("\n")

        first_filter_idx = len(all_lines)
        filter_prefixes = ("--filter-tcp", "--filter-udp", "--filter-l7")
        for idx, raw_line in enumerate(all_lines):
            if raw_line.strip().startswith(filter_prefixes):
                first_filter_idx = idx
                break

        prefix_lines = all_lines[:first_filter_idx]
        body_lines = all_lines[first_filter_idx:]

        while prefix_lines and not prefix_lines[-1].strip():
            prefix_lines.pop()

        prefix_set = {line.strip() for line in prefix_lines if line.strip()}
        missing_blob_lines = [line for line in blob_lines if line.strip() and line.strip() not in prefix_set]
        if missing_blob_lines:
            if prefix_lines and prefix_lines[-1].strip():
                prefix_lines.append("")
            prefix_lines.extend(missing_blob_lines)

        cleaned_strategy_lines = [line.strip() for line in strategy_lines if line and line.strip()]

        if prefix_lines and prefix_lines[-1].strip():
            prefix_lines.append("")

        result_lines = list(prefix_lines)
        result_lines.extend(cleaned_strategy_lines)

        while body_lines and not body_lines[0].strip():
            body_lines.pop(0)

        if body_lines:
            result_lines.extend(["", "--new", ""])
            result_lines.extend(body_lines)

        return "\n".join(result_lines).rstrip("\n") + "\n"

    @classmethod
    def apply_strategy(
        cls,
        *,
        strategy_args: str,
        strategy_name: str,
        scan_target: str,
        scan_protocol: str,
        scan_udp_games_scope: str,
    ) -> StrategyApplyResult:
        from core.presets.direct_facade import DirectPresetFacade
        from core.presets.direct_runtime_events import notify_direct_preset_saved

        facade = DirectPresetFacade.from_launch_method("direct_zapret2")
        selected_file_name = str(facade.get_selected_file_name() or "").strip()
        if not selected_file_name:
            raise RuntimeError("Не удалось определить выбранный пресет")

        target = scan_target or cls.default_target_for_protocol(scan_protocol)
        blob_lines = cls.generate_blob_lines_for_apply(strategy_args)

        if scan_protocol == "stun_voice":
            target_host, target_port = cls.stun_target_parts(target)
            if not target_host:
                target_host = "stun.l.google.com"
                target_port = 19302

            new_strategy_lines = [
                "--wf-udp-out=443-65535",
                "--filter-l7=stun,discord",
                "--payload=stun,discord_ip_discovery",
                strategy_args,
            ]
            applied_target = f"voice (probe: {cls.format_stun_target(target_host, target_port)})"
        elif scan_protocol == "udp_games":
            games_ipset_paths = cls.resolve_games_ipset_paths(scan_udp_games_scope)
            probe_host, probe_port = cls.stun_target_parts(target)
            if not probe_host:
                probe_host = "stun.cloudflare.com"
                probe_port = 3478

            new_strategy_lines = [
                "--wf-udp-out=443,50000-65535",
                "--filter-udp=443,50000-65535",
                *[f"--ipset={path}" for path in games_ipset_paths],
                strategy_args,
            ]
            shown_paths = ", ".join(games_ipset_paths[:3])
            if len(games_ipset_paths) > 3:
                shown_paths += f", ... (+{len(games_ipset_paths) - 3})"
            applied_target = (
                f"Games UDP ipsets ({shown_paths}), "
                f"probe {cls.format_stun_target(probe_host, probe_port)}"
            )
        else:
            normalized_target = cls.normalize_target_domain(target) or "discord.com"
            new_strategy_lines = [
                "--filter-tcp=443",
                f"--hostlist-domains={normalized_target}",
                "--out-range=-d8",
                strategy_args,
            ]
            applied_target = normalized_target

        existing_content = facade.read_selected_source_text()
        updated_content = cls.prepend_strategy_block(
            existing_content=existing_content,
            strategy_lines=new_strategy_lines,
            blob_lines=blob_lines,
        )

        facade.save_source_text_by_file_name(selected_file_name, updated_content)
        notify_direct_preset_saved("direct_zapret2", selected_file_name)

        return StrategyApplyResult(
            strategy_name=strategy_name,
            applied_target=applied_target,
            selected_file_name=selected_file_name,
        )
