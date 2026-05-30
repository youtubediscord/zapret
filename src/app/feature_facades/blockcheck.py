from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BlockcheckFeature:
    presets_feature: Any
    profile_feature: Any

    @staticmethod
    def _commands():
        import blockcheck.public as blockcheck_commands

        return blockcheck_commands

    @staticmethod
    def _worker_commands():
        from blockcheck import commands as blockcheck_worker_commands

        return blockcheck_worker_commands

    def create_blockcheck_worker(self, **kwargs):
        from blockcheck.worker import BlockcheckWorker

        return BlockcheckWorker(
            start_run_log=self.start_blockcheck_run_log,
            append_run_log=self.append_blockcheck_run_log,
            **kwargs,
        )

    def create_strategy_scan_worker(self, **kwargs):
        from blockcheck.strategy_scan_worker import StrategyScanWorker

        return StrategyScanWorker(
            start_run_log=self.start_strategy_scan_run_log,
            append_run_log=self.append_strategy_scan_run_log,
            **kwargs,
        )

    def create_strategy_apply_worker(self, request_id: int, **kwargs):
        from blockcheck.strategy_apply_worker import StrategyApplyWorker

        return StrategyApplyWorker(request_id, apply_strategy=self.apply_strategy, **kwargs)

    def create_page_initial_state_worker(self, request_id: int, *, parent=None):
        from blockcheck.workers import BlockcheckInitialStateWorker

        return BlockcheckInitialStateWorker(
            request_id,
            load_page_initial_state=self.load_page_initial_state,
            parent=parent,
        )

    def create_blockcheck_support_prepare_worker(self, request_id: int, **kwargs):
        from blockcheck.workers import BlockcheckSupportPrepareWorker

        return BlockcheckSupportPrepareWorker(
            request_id,
            prepare_support=self.prepare_support,
            **kwargs,
        )

    def create_user_domain_action_worker(self, request_id: int, **kwargs):
        from blockcheck.workers import BlockcheckUserDomainActionWorker

        return BlockcheckUserDomainActionWorker(
            request_id,
            run_user_domain_action=self.run_user_domain_action,
            **kwargs,
        )

    def create_strategy_scan_support_prepare_worker(self, request_id: int, **kwargs):
        from blockcheck.workers import StrategyScanSupportPrepareWorker

        return StrategyScanSupportPrepareWorker(
            request_id,
            prepare_strategy_scan_support=self.prepare_strategy_scan_support,
            **kwargs,
        )

    def create_strategy_scan_quick_targets_worker(self, request_id: int, **kwargs):
        from blockcheck.workers import StrategyScanQuickTargetsWorker

        return StrategyScanQuickTargetsWorker(
            request_id,
            build_quick_target_menu_plan=self.build_quick_target_menu_plan,
            **kwargs,
        )

    def create_strategy_scan_resume_save_worker(self, request_id: int, **kwargs):
        from blockcheck.workers import StrategyScanResumeSaveWorker

        return StrategyScanResumeSaveWorker(
            request_id,
            save_resume_state=self.save_resume_state,
            **kwargs,
        )

    def create_strategy_scan_finalize_worker(self, request_id: int, **kwargs):
        from blockcheck.workers import StrategyScanFinalizeWorker

        return StrategyScanFinalizeWorker(
            request_id,
            finalize_scan_report=self.finalize_scan_report,
            **kwargs,
        )

    def load_page_initial_state(self, *args, **kwargs):
        return self._worker_commands().load_page_initial_state(*args, **kwargs)

    def append_run_log(self, *args, **kwargs) -> None:
        return self._commands().append_run_log(*args, **kwargs)

    def start_run_log(self, *args, **kwargs):
        return self._commands().start_run_log(*args, **kwargs)

    def save_resume_state(self, *args, **kwargs):
        return self._commands().save_resume_state(*args, **kwargs)

    def start_blockcheck_run_log(self, *args, **kwargs):
        return self._worker_commands().start_blockcheck_run_log(*args, **kwargs)

    def append_blockcheck_run_log(self, *args, **kwargs) -> None:
        return self._worker_commands().append_blockcheck_run_log(*args, **kwargs)

    def start_strategy_scan_run_log(self, *args, **kwargs):
        return self._worker_commands().start_strategy_scan_run_log(*args, **kwargs)

    def append_strategy_scan_run_log(self, *args, **kwargs) -> None:
        return self._worker_commands().append_strategy_scan_run_log(*args, **kwargs)

    def prepare_support(self, *args, **kwargs):
        return self._worker_commands().prepare_support(*args, **kwargs)

    def run_user_domain_action(self, *args, **kwargs):
        return self._worker_commands().run_user_domain_action(*args, **kwargs)

    def prepare_strategy_scan_support(self, *args, **kwargs):
        return self._worker_commands().prepare_strategy_scan_support(*args, **kwargs)

    def apply_strategy(self, **kwargs):
        return self._commands().apply_strategy(
            presets_feature=self.presets_feature,
            profile_feature=self.profile_feature,
            **kwargs,
        )

    def build_selection_state(self, *args, **kwargs):
        return self._commands().build_selection_state(*args, **kwargs)

    def build_protocol_ui_plan(self, *args, **kwargs):
        return self._commands().build_protocol_ui_plan(*args, **kwargs)

    def build_udp_scope_hint_plan(self, *args, **kwargs):
        return self._commands().build_udp_scope_hint_plan(*args, **kwargs)

    def build_quick_target_menu_plan(self, *args, **kwargs):
        return self._commands().build_quick_target_menu_plan(*args, **kwargs)

    def plan_scan_start(self, *args, **kwargs):
        return self._commands().plan_scan_start(*args, **kwargs)

    def build_running_interaction_plan(self, *args, **kwargs):
        return self._commands().build_running_interaction_plan(*args, **kwargs)

    def build_idle_interaction_plan(self, *args, **kwargs):
        return self._commands().build_idle_interaction_plan(*args, **kwargs)

    def build_progress_plan(self, *args, **kwargs):
        return self._commands().build_progress_plan(*args, **kwargs)

    def build_result_presentation(self, *args, **kwargs):
        return self._commands().build_result_presentation(*args, **kwargs)

    def finalize_scan_report(self, *args, **kwargs):
        return self._commands().finalize_scan_report(*args, **kwargs)

    def build_finish_notification_plan(self, *args, **kwargs):
        return self._commands().build_finish_notification_plan(*args, **kwargs)

    def build_apply_success_plan(self, *args, **kwargs):
        return self._commands().build_apply_success_plan(*args, **kwargs)

    def build_apply_error_plan(self, *args, **kwargs):
        return self._commands().build_apply_error_plan(*args, **kwargs)

    def build_log_expand_plan(self, *args, **kwargs):
        return self._commands().build_log_expand_plan(*args, **kwargs)

    def build_language_plan(self, *args, **kwargs):
        return self._commands().build_language_plan(*args, **kwargs)

    def build_support_context(self, *args, **kwargs):
        return self._commands().build_support_context(*args, **kwargs)

    def build_support_success_plan(self, *args, **kwargs):
        return self._commands().build_support_success_plan(*args, **kwargs)

    def build_support_error_plan(self, *args, **kwargs):
        return self._commands().build_support_error_plan(*args, **kwargs)
