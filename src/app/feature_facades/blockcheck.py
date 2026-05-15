from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import blockcheck.public as blockcheck_commands
from blockcheck import commands as blockcheck_worker_commands


@dataclass(frozen=True, slots=True)
class BlockcheckFeature:
    presets_feature: Any
    profile_feature: Any

    def create_blockcheck_worker(self, **kwargs):
        return blockcheck_worker_commands.create_blockcheck_worker(**kwargs)

    def create_strategy_scan_worker(self, **kwargs):
        return blockcheck_worker_commands.create_strategy_scan_worker(**kwargs)

    def append_run_log(self, *args, **kwargs) -> None:
        return blockcheck_commands.append_run_log(*args, **kwargs)

    def start_run_log(self, *args, **kwargs):
        return blockcheck_commands.start_run_log(*args, **kwargs)

    def save_resume_state(self, *args, **kwargs):
        return blockcheck_commands.save_resume_state(*args, **kwargs)

    def prepare_support(self, *args, **kwargs):
        return blockcheck_commands.prepare_support(*args, **kwargs)

    def apply_strategy(self, **kwargs):
        return blockcheck_commands.apply_strategy(
            presets_feature=self.presets_feature,
            profile_feature=self.profile_feature,
            **kwargs,
        )

    def build_selection_state(self, *args, **kwargs):
        return blockcheck_commands.build_selection_state(*args, **kwargs)

    def build_protocol_ui_plan(self, *args, **kwargs):
        return blockcheck_commands.build_protocol_ui_plan(*args, **kwargs)

    def build_udp_scope_hint_plan(self, *args, **kwargs):
        return blockcheck_commands.build_udp_scope_hint_plan(*args, **kwargs)

    def build_quick_target_menu_plan(self, *args, **kwargs):
        return blockcheck_commands.build_quick_target_menu_plan(*args, **kwargs)

    def plan_scan_start(self, *args, **kwargs):
        return blockcheck_commands.plan_scan_start(*args, **kwargs)

    def build_running_interaction_plan(self, *args, **kwargs):
        return blockcheck_commands.build_running_interaction_plan(*args, **kwargs)

    def build_idle_interaction_plan(self, *args, **kwargs):
        return blockcheck_commands.build_idle_interaction_plan(*args, **kwargs)

    def build_progress_plan(self, *args, **kwargs):
        return blockcheck_commands.build_progress_plan(*args, **kwargs)

    def build_result_presentation(self, *args, **kwargs):
        return blockcheck_commands.build_result_presentation(*args, **kwargs)

    def finalize_scan_report(self, *args, **kwargs):
        return blockcheck_commands.finalize_scan_report(*args, **kwargs)

    def build_finish_notification_plan(self, *args, **kwargs):
        return blockcheck_commands.build_finish_notification_plan(*args, **kwargs)

    def build_apply_success_plan(self, *args, **kwargs):
        return blockcheck_commands.build_apply_success_plan(*args, **kwargs)

    def build_apply_error_plan(self, *args, **kwargs):
        return blockcheck_commands.build_apply_error_plan(*args, **kwargs)

    def build_log_expand_plan(self, *args, **kwargs):
        return blockcheck_commands.build_log_expand_plan(*args, **kwargs)

    def build_language_plan(self, *args, **kwargs):
        return blockcheck_commands.build_language_plan(*args, **kwargs)

    def build_support_context(self, *args, **kwargs):
        return blockcheck_commands.build_support_context(*args, **kwargs)

    def build_support_success_plan(self, *args, **kwargs):
        return blockcheck_commands.build_support_success_plan(*args, **kwargs)

    def build_support_error_plan(self, *args, **kwargs):
        return blockcheck_commands.build_support_error_plan(*args, **kwargs)
