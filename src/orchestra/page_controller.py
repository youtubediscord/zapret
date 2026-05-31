"""Контроллер основной страницы orchestra."""

from __future__ import annotations

import orchestra.log_history_workflow as orchestra_log_history_workflow
import orchestra.log_context_actions as orchestra_log_context_actions


class OrchestraPageController:
    """Действия страницы логов orchestra без привязки к QWidget."""

    def __init__(self, *, orchestra_feature, is_runtime_running) -> None:
        self._orchestra = orchestra_feature
        self._is_runtime_running = is_runtime_running

    def runner(self):
        return self._orchestra.runner

    def is_runtime_running(self) -> bool:
        return bool(self._is_runtime_running())

    def clear_learned_data(self) -> bool:
        if self.runner() is None:
            return False
        self._orchestra.clear_learned_data()
        return True

    def load_log_history(self) -> list[dict]:
        runner = self.runner()
        if runner is None:
            return []
        return list(runner.get_log_history() or [])

    def is_strategy_blocked(self, *, domain: str, strategy: int) -> bool:
        return bool(
            orchestra_log_context_actions.is_strategy_blocked(
                runner=self.runner(),
                domain=domain,
                strategy=int(strategy or 0),
            )
        )

    def run_log_context_action(self, *, action: str, domain: str, strategy: int, protocol: str):
        runner = self.runner()
        if runner is None:
            raise RuntimeError("Orchestra runner is not ready")

        normalized_action = str(action or "").strip()
        if normalized_action == "lock":
            return orchestra_log_context_actions.lock_strategy_from_log(
                runner=runner,
                domain=domain,
                strategy=int(strategy or 0),
                protocol=protocol,
            )
        if normalized_action == "block":
            return orchestra_log_context_actions.block_strategy_from_log(
                runner=runner,
                domain=domain,
                strategy=int(strategy or 0),
                protocol=protocol,
            )
        if normalized_action == "unblock":
            return orchestra_log_context_actions.unblock_strategy_from_log(
                runner=runner,
                domain=domain,
                strategy=int(strategy or 0),
                protocol=protocol,
            )
        if normalized_action == "whitelist":
            return orchestra_log_context_actions.add_to_whitelist_from_log(
                runner=runner,
                domain=domain,
            )
        raise ValueError(f"Неизвестное действие строки лога: {normalized_action}")

    def run_log_history_action(self, *, action: str, log_id: str):
        runner = self.runner()
        if runner is None:
            raise RuntimeError("Orchestra runner is not ready")

        normalized_action = str(action or "").strip()
        if normalized_action == "view":
            return orchestra_log_history_workflow.view_log_history_entry(
                runner=runner,
                log_id=str(log_id or ""),
            )
        if normalized_action == "delete":
            return orchestra_log_history_workflow.delete_log_history_entry(
                runner=runner,
                log_id=str(log_id or ""),
            )
        if normalized_action == "clear":
            return orchestra_log_history_workflow.clear_log_history_entries(
                runner=runner,
            )
        raise ValueError(f"Неизвестное действие истории логов: {normalized_action}")

    def create_clear_learned_worker(self, request_id: int, parent=None):
        from orchestra.page_workers import OrchestraClearLearnedWorker

        return OrchestraClearLearnedWorker(request_id, self.clear_learned_data, parent)

    def create_log_history_load_worker(self, request_id: int, parent=None):
        from orchestra.page_workers import OrchestraLogHistoryLoadWorker

        return OrchestraLogHistoryLoadWorker(request_id, self.load_log_history, parent)

    def create_log_history_action_worker(self, request_id: int, *, action: str, log_id: str, parent=None):
        from orchestra.page_workers import OrchestraLogHistoryActionWorker

        return OrchestraLogHistoryActionWorker(
            request_id,
            action=action,
            log_id=log_id,
            run_action=self.run_log_history_action,
            parent=parent,
        )

    def create_log_context_action_worker(
        self,
        request_id: int,
        *,
        action: str,
        domain: str,
        strategy: int,
        protocol: str,
        parent=None,
    ):
        from orchestra.page_workers import OrchestraLogContextActionWorker

        return OrchestraLogContextActionWorker(
            request_id,
            action=action,
            domain=domain,
            strategy=int(strategy or 0),
            protocol=protocol,
            run_action=self.run_log_context_action,
            parent=parent,
        )
