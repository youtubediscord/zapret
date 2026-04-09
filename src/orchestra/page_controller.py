from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True)
class OrchestraStateTransition:
    next_state: str | None


@dataclass(slots=True)
class OrchestraParsedStrategyLine:
    domain: str
    strategy: int
    protocol: str


@dataclass(slots=True)
class OrchestraMonitoringPlan:
    reset_log_position: bool
    queue_timer_interval_ms: int | None
    update_timer_interval_ms: int | None
    run_update_now: bool


@dataclass(slots=True)
class OrchestraLogHistoryEntryPlan:
    text: str
    log_id: str | None
    is_current: bool
    is_placeholder: bool


@dataclass(slots=True)
class OrchestraLogHistoryPlan:
    entries: list[OrchestraLogHistoryEntryPlan]


@dataclass(slots=True)
class OrchestraHistoryActionPlan:
    message_text: str


@dataclass(slots=True)
class OrchestraRunnerActionPlan:
    messages: list[str]
    refresh_learned: bool


@dataclass(slots=True)
class OrchestraUpdateCyclePlan:
    next_state: str | None
    refresh_learned: bool
    refresh_history: bool


@dataclass(slots=True)
class OrchestraLearnedDataPlan:
    data: dict


class OrchestraPageController:
    @staticmethod
    def build_start_monitoring_plan() -> OrchestraMonitoringPlan:
        return OrchestraMonitoringPlan(
            reset_log_position=True,
            queue_timer_interval_ms=50,
            update_timer_interval_ms=5000,
            run_update_now=True,
        )

    @staticmethod
    def build_stop_monitoring_plan() -> OrchestraMonitoringPlan:
        return OrchestraMonitoringPlan(
            reset_log_position=False,
            queue_timer_interval_ms=None,
            update_timer_interval_ms=None,
            run_update_now=False,
        )

    @staticmethod
    def detect_state_from_line(*, line: str, current_state: str, idle_state: str, learning_state: str, running_state: str, unlocked_state: str) -> OrchestraStateTransition:
        if "PRELOADED:" in line or "🔒" in line or "LOCKED:" in line:
            return OrchestraStateTransition(next_state=running_state)

        if "🔓" in line or "UNLOCKED:" in line:
            return OrchestraStateTransition(next_state=unlocked_state)

        if "RST detected" in line or "rotated" in line.lower():
            return OrchestraStateTransition(next_state=learning_state)

        if "✓" in line or "SUCCESS:" in line or "✗" in line or "FAIL:" in line:
            if current_state in (idle_state, unlocked_state):
                return OrchestraStateTransition(next_state=learning_state)
            return OrchestraStateTransition(next_state=None)

        return OrchestraStateTransition(next_state=None)

    @staticmethod
    def matches_filter(*, text: str, domain_filter: str, protocol_filter: str) -> bool:
        normalized_domain = str(domain_filter or "").strip().lower()
        if normalized_domain and normalized_domain not in text.lower():
            return False

        protocol = str(protocol_filter or "all").strip().lower()
        if protocol == "all":
            return True

        text_upper = text.upper()
        if protocol == "tls":
            return "[TLS]" in text_upper or "TLS" in text_upper
        if protocol == "http":
            return "[HTTP]" in text_upper or "HTTP" in text_upper
        if protocol == "udp":
            return "UDP" in text_upper
        if protocol == "success":
            return "SUCCESS" in text_upper or "✓" in text
        if protocol == "fail":
            return "FAIL" in text_upper or "✗" in text or "X " in text
        return True

    def filter_lines(self, *, lines: list[str], domain_filter: str, protocol_filter: str) -> list[str]:
        return [
            line
            for line in lines
            if self.matches_filter(
                text=line,
                domain_filter=domain_filter,
                protocol_filter=protocol_filter,
            )
        ]

    @staticmethod
    def parse_log_line_for_strategy(line: str) -> OrchestraParsedStrategyLine | None:
        match = re.search(r'(?:SUCCESS|FAIL):\s*(\S+)\s+:(\d+)\s+strategy[=:](\d+)', line, re.IGNORECASE)
        if match:
            domain = match.group(1)
            port = match.group(2)
            strategy = int(match.group(3))
            protocol = "tls" if port == "443" else ("http" if port == "80" else "udp")
            return OrchestraParsedStrategyLine(domain=domain, strategy=strategy, protocol=protocol)

        match = re.search(r'(?:SUCCESS|FAIL):\s*(\S+)\s+UDP\s+strategy[=:](\d+)', line, re.IGNORECASE)
        if match:
            return OrchestraParsedStrategyLine(
                domain=match.group(1),
                strategy=int(match.group(2)),
                protocol="udp",
            )

        match = re.search(r'LOCKED:\s*(\S+)\s+:(\d+)\s*=\s*strategy\s+(\d+)', line, re.IGNORECASE)
        if match:
            domain = match.group(1)
            port = match.group(2)
            strategy = int(match.group(3))
            protocol = "tls" if port == "443" else ("http" if port == "80" else "udp")
            return OrchestraParsedStrategyLine(domain=domain, strategy=strategy, protocol=protocol)

        match = re.search(r'UNLOCKED:\s*(\S+)\s+:(\d+)', line, re.IGNORECASE)
        if match:
            domain = match.group(1)
            port = match.group(2)
            protocol = "tls" if port == "443" else ("http" if port == "80" else "udp")
            return OrchestraParsedStrategyLine(domain=domain, strategy=0, protocol=protocol)

        return None

    @staticmethod
    def build_log_history_plan(*, logs: list[dict], current_suffix_text: str, none_text: str) -> OrchestraLogHistoryPlan:
        entries: list[OrchestraLogHistoryEntryPlan] = []
        for log_info in logs:
            is_current = bool(log_info.get("is_current", False))
            prefix = "▶ " if is_current else "  "
            suffix = current_suffix_text if is_current else ""
            text = f"{prefix}{log_info['created']} | {log_info['size_str']}{suffix}"
            entries.append(
                OrchestraLogHistoryEntryPlan(
                    text=text,
                    log_id=str(log_info["id"]),
                    is_current=is_current,
                    is_placeholder=False,
                )
            )

        if not entries:
            entries.append(
                OrchestraLogHistoryEntryPlan(
                    text=none_text,
                    log_id=None,
                    is_current=False,
                    is_placeholder=True,
                )
            )

        return OrchestraLogHistoryPlan(entries=entries)

    @staticmethod
    def build_log_history_view_plan(*, log_id: str, has_content: bool) -> OrchestraHistoryActionPlan:
        if has_content:
            return OrchestraHistoryActionPlan(
                message_text=f"\n[INFO] === Загружен лог: {log_id} ===",
            )
        return OrchestraHistoryActionPlan(
            message_text=f"[ERROR] Не удалось прочитать лог: {log_id}",
        )

    @staticmethod
    def build_log_history_delete_plan(*, log_id: str, deleted: bool) -> OrchestraHistoryActionPlan:
        if deleted:
            return OrchestraHistoryActionPlan(
                message_text=f"[INFO] Удалён лог: {log_id}",
            )
        return OrchestraHistoryActionPlan(
            message_text="[WARNING] Не удалось удалить лог (возможно, активный)",
        )

    @staticmethod
    def build_log_history_clear_all_plan(*, deleted_count: int) -> OrchestraHistoryActionPlan:
        if deleted_count > 0:
            return OrchestraHistoryActionPlan(
                message_text=f"[INFO] Удалено {deleted_count} лог-файлов",
            )
        return OrchestraHistoryActionPlan(
            message_text="[INFO] Нет логов для удаления",
        )

    @staticmethod
    def lock_strategy(runner, *, domain: str, strategy: int, protocol: str, ignored_target: bool) -> OrchestraRunnerActionPlan:
        if ignored_target:
            return OrchestraRunnerActionPlan(
                messages=[f"[WARNING] {domain} относится к Telegram Proxy модулю и не управляется оркестратором"],
                refresh_learned=False,
            )
        if strategy == 0:
            return OrchestraRunnerActionPlan(
                messages=["[WARNING] Невозможно залочить: стратегия неизвестна"],
                refresh_learned=False,
            )
        if runner is None:
            return OrchestraRunnerActionPlan(
                messages=["[ERROR] Оркестратор не инициализирован"],
                refresh_learned=False,
            )

        runner.locked_manager.lock(domain, strategy, protocol, user_lock=True)
        messages = [f"[INFO] [USER] 🔒 Залочена стратегия #{strategy} для {domain} [{protocol.upper()}]"]
        is_running = runner.is_running()
        messages.append(f"[DEBUG] is_running={is_running}, process={runner.running_process}")
        if is_running:
            messages.append("[INFO] Применяю user lock (перезапуск)...")
            runner.stop()
            if runner.start():
                messages.append("[INFO] ✓ User lock применён")
            else:
                messages.append("[ERROR] Не удалось перезапустить оркестратор")
        else:
            messages.append("[WARNING] Оркестратор не запущен, user lock сохранён в реестр")

        return OrchestraRunnerActionPlan(messages=messages, refresh_learned=True)

    @staticmethod
    def block_strategy(runner, *, domain: str, strategy: int, protocol: str, ignored_target: bool) -> OrchestraRunnerActionPlan:
        if ignored_target:
            return OrchestraRunnerActionPlan(
                messages=[f"[WARNING] {domain} относится к Telegram Proxy модулю и не управляется оркестратором"],
                refresh_learned=False,
            )
        if strategy == 0:
            return OrchestraRunnerActionPlan(
                messages=["[WARNING] Невозможно заблокировать: стратегия неизвестна"],
                refresh_learned=False,
            )
        if runner is None:
            return OrchestraRunnerActionPlan(
                messages=["[ERROR] Оркестратор не инициализирован"],
                refresh_learned=False,
            )

        runner.blocked_manager.block(domain, strategy, protocol)
        messages = [f"[INFO] 🚫 Заблокирована стратегия #{strategy} для {domain} [{protocol.upper()}]"]
        if runner.is_running():
            messages.append("[INFO] Перезапуск оркестратора для применения блокировки...")
            runner.restart()

        return OrchestraRunnerActionPlan(messages=messages, refresh_learned=True)

    @staticmethod
    def unblock_strategy(runner, *, domain: str, strategy: int, protocol: str) -> OrchestraRunnerActionPlan:
        if runner is None:
            return OrchestraRunnerActionPlan(
                messages=["[ERROR] Оркестратор не инициализирован"],
                refresh_learned=False,
            )

        runner.blocked_manager.unblock(domain, strategy)
        messages = [f"[INFO] ✅ Разблокирована стратегия #{strategy} для {domain} [{protocol.upper()}]"]
        if runner.is_running():
            messages.append("[INFO] Перезапуск оркестратора для применения разблокировки...")
            runner.restart()

        return OrchestraRunnerActionPlan(messages=messages, refresh_learned=True)

    @staticmethod
    def add_to_whitelist(runner, *, domain: str) -> OrchestraRunnerActionPlan:
        if runner is None:
            return OrchestraRunnerActionPlan(
                messages=["[ERROR] Оркестратор не инициализирован"],
                refresh_learned=False,
            )

        if runner.add_to_whitelist(domain):
            return OrchestraRunnerActionPlan(
                messages=[f"[INFO] ✅ Добавлен в белый список: {domain}"],
                refresh_learned=False,
            )
        return OrchestraRunnerActionPlan(
            messages=[f"[WARNING] Не удалось добавить: {domain}"],
            refresh_learned=False,
        )

    @staticmethod
    def build_update_cycle_plan(*, runner_alive: bool) -> OrchestraUpdateCyclePlan:
        return OrchestraUpdateCyclePlan(
            next_state=None if runner_alive else "idle",
            refresh_learned=bool(runner_alive),
            refresh_history=True,
        )

    @staticmethod
    def build_learned_data_plan(learned_data: dict | None) -> OrchestraLearnedDataPlan:
        if isinstance(learned_data, dict):
            return OrchestraLearnedDataPlan(data=learned_data)
        return OrchestraLearnedDataPlan(data={'tls': {}, 'http': {}, 'udp': {}})
