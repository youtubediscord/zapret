from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LogsFeature:
    @staticmethod
    def _commands():
        import log.commands as log_commands

        return log_commands

    @staticmethod
    def _runtime():
        import log.runtime_workflow as log_runtime

        return log_runtime

    def get_current_log_file(self) -> str:
        return self._commands().get_current_log_file()

    def list_logs(self, *, run_cleanup: bool):
        return self._commands().list_logs(run_cleanup=run_cleanup)

    def build_stats(self):
        return self._commands().build_stats()

    def warm_page_data_cache(self):
        return self._commands().warm_page_data_cache(run_cleanup=False)

    def consume_warmed_page_data(self):
        return self._commands().consume_warmed_page_data()

    def resolve_winws_exe_name(self, launch_method: str) -> str:
        return self._commands().resolve_winws_exe_name(launch_method)

    def get_running_runner_source(self, launch_method: str, orchestra_runner, direct_runner):
        return self._commands().get_running_runner_source(launch_method, orchestra_runner, direct_runner)

    def get_orchestra_log_path(self, orchestra_runner):
        return self._commands().get_orchestra_log_path(orchestra_runner)

    def prepare_support_bundle(self, *, current_log_file: str, orchestra_runner):
        return self._commands().prepare_support_bundle(
            current_log_file=current_log_file,
            orchestra_runner=orchestra_runner,
        )

    def open_logs_folder(self) -> None:
        return self._commands().open_logs_folder()

    def create_log_tail_worker(self, file_path: str, *, initial_max_bytes: int | None = 1024 * 1024):
        return self._commands().create_log_tail_worker(file_path, initial_max_bytes=initial_max_bytes)

    def create_winws_output_worker(self, process):
        return self._commands().create_winws_output_worker(process)

    def create_logs_overview_worker(self, *, run_cleanup: bool):
        return self._commands().create_logs_overview_worker(run_cleanup=run_cleanup)

    def build_thread_stop_plan(self, *, has_worker: bool, thread_running: bool, blocking: bool):
        return self._commands().build_thread_stop_plan(
            has_worker=has_worker,
            thread_running=thread_running,
            blocking=blocking,
        )

    def build_tail_start_plan(self, *, current_log_file: str, previous_signature=None):
        return self._commands().build_tail_start_plan(
            current_log_file=current_log_file,
            previous_signature=previous_signature,
        )

    def build_support_feedback(self, result):
        return self._commands().build_support_feedback(result)

    def build_support_error_feedback(self, error: str):
        return self._commands().build_support_error_feedback(error)

    def build_stats_text_plan(self, stats, *, language: str):
        return self._commands().build_stats_text_plan(stats, language=language)

    def build_winws_output_plan(self, *, launch_method: str, orchestra_runner, direct_runner, process_pid, language: str):
        return self._commands().build_winws_output_plan(
            launch_method=launch_method,
            orchestra_runner=orchestra_runner,
            direct_runner=direct_runner,
            process_pid=process_pid,
            language=language,
        )

    def run_runtime_init(self, **kwargs):
        return self._runtime().run_logs_runtime_init(**kwargs)

    def start_tail_worker(self, **kwargs):
        return self._runtime().start_tail_worker(**kwargs)

    def handle_thread_stop(self, **kwargs):
        return self._runtime().handle_thread_stop(**kwargs)

    def start_winws_output_worker(self, **kwargs):
        return self._runtime().start_winws_output_worker(**kwargs)
