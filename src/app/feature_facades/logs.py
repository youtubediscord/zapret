from __future__ import annotations

from dataclasses import dataclass

import log.commands as log_commands
import log.runtime_workflow as log_runtime


@dataclass(frozen=True, slots=True)
class LogsFeature:
    def get_current_log_file(self) -> str:
        return log_commands.get_current_log_file()

    def list_logs(self, *, run_cleanup: bool):
        return log_commands.list_logs(run_cleanup=run_cleanup)

    def build_stats(self):
        return log_commands.build_stats()

    def resolve_winws_exe_name(self, launch_method: str) -> str:
        return log_commands.resolve_winws_exe_name(launch_method)

    def get_running_runner_source(self, launch_method: str, orchestra_runner, direct_runner):
        return log_commands.get_running_runner_source(launch_method, orchestra_runner, direct_runner)

    def get_runner_pid(self, runner):
        return log_commands.get_runner_pid(runner)

    def get_orchestra_log_path(self, orchestra_runner):
        return log_commands.get_orchestra_log_path(orchestra_runner)

    def prepare_support_bundle(self, *, current_log_file: str, orchestra_runner):
        return log_commands.prepare_support_bundle(
            current_log_file=current_log_file,
            orchestra_runner=orchestra_runner,
        )

    def open_logs_folder(self) -> None:
        return log_commands.open_logs_folder()

    def create_log_tail_worker(self, file_path: str):
        return log_commands.create_log_tail_worker(file_path)

    def create_winws_output_worker(self, process):
        return log_commands.create_winws_output_worker(process)

    def build_thread_stop_plan(self, *, has_worker: bool, thread_running: bool, blocking: bool):
        return log_commands.build_thread_stop_plan(
            has_worker=has_worker,
            thread_running=thread_running,
            blocking=blocking,
        )

    def build_tail_start_plan(self, *, current_log_file: str):
        return log_commands.build_tail_start_plan(current_log_file=current_log_file)

    def build_support_feedback(self, result):
        return log_commands.build_support_feedback(result)

    def build_support_error_feedback(self, error: str):
        return log_commands.build_support_error_feedback(error)

    def build_stats_text_plan(self, stats, *, language: str):
        return log_commands.build_stats_text_plan(stats, language=language)

    def build_winws_output_plan(self, *, launch_method: str, orchestra_runner, language: str):
        return log_commands.build_winws_output_plan(
            launch_method=launch_method,
            orchestra_runner=orchestra_runner,
            language=language,
        )

    def run_runtime_init(self, **kwargs):
        return log_runtime.run_logs_runtime_init(**kwargs)

    def start_tail_worker(self, **kwargs):
        return log_runtime.start_tail_worker(**kwargs)

    def handle_thread_stop(self, **kwargs):
        return log_runtime.handle_thread_stop(**kwargs)

    def start_winws_output_worker(self, **kwargs):
        return log_runtime.start_winws_output_worker(**kwargs)
