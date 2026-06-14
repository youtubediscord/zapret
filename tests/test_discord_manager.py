import os
import sys
import tempfile
import threading
import time
import types
import unittest


try:
    import psutil  # noqa: F401
except ModuleNotFoundError:
    psutil_stub = types.ModuleType("psutil")
    psutil_stub.NoSuchProcess = RuntimeError
    psutil_stub.AccessDenied = PermissionError
    psutil_stub.ZombieProcess = RuntimeError
    psutil_stub.process_iter = lambda _attrs=None: iter(())
    sys.modules["psutil"] = psutil_stub


class FakeProcess:
    def __init__(self, *, name="Discord.exe", exe=""):
        self.info = {"name": name, "exe": exe, "cmdline": [exe] if exe else []}
        self.terminated = False
        self.killed = False

    def exe(self):
        return self.info.get("exe")

    def cmdline(self):
        return list(self.info.get("cmdline") or [])

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


class FakeScanner:
    def __init__(self, snapshots):
        self._snapshots = list(snapshots)
        self.calls = 0

    def scan(self):
        self.calls += 1
        if self._snapshots:
            return self._snapshots.pop(0)
        from discord.discord import DiscordProcessSnapshot

        return DiscordProcessSnapshot(processes=[])


class DiscordManagerTests(unittest.TestCase):
    def test_latest_app_directory_is_selected_by_version_number(self):
        from discord.discord import DiscordInstallLocator

        with tempfile.TemporaryDirectory() as temp_dir:
            old_exe = os.path.join(temp_dir, "app-1.9.99", "Discord.exe")
            new_exe = os.path.join(temp_dir, "app-1.10.2", "Discord.exe")
            os.makedirs(os.path.dirname(old_exe))
            os.makedirs(os.path.dirname(new_exe))
            open(old_exe, "w", encoding="utf-8").close()
            open(new_exe, "w", encoding="utf-8").close()

            locator = DiscordInstallLocator()

            self.assertEqual(locator.find_latest_app_exe(temp_dir), new_exe)

    def test_restart_uses_one_initial_process_snapshot_for_path_and_termination(self):
        from discord.discord import (
            DiscordInstallLocator,
            DiscordProcessSnapshot,
            DiscordRestartService,
        )

        discord_exe = r"C:\Users\User\AppData\Local\Discord\app-1.10.2\Discord.exe"
        process = FakeProcess(exe=discord_exe)
        scanner = FakeScanner(
            [
                DiscordProcessSnapshot(processes=[process], running_discord_path=discord_exe),
                DiscordProcessSnapshot(processes=[]),
            ]
        )
        launched = []
        statuses = []
        service = DiscordRestartService(
            scanner=scanner,
            locator=DiscordInstallLocator(path_patterns=[]),
            runner=launched.append,
            sleep=lambda _seconds: None,
            status_callback=statuses.append,
            log_func=lambda *_args, **_kwargs: None,
        )

        service.restart_once()

        self.assertEqual(scanner.calls, 2)
        self.assertTrue(process.terminated)
        self.assertFalse(process.killed)
        self.assertEqual(launched, [discord_exe])
        self.assertIn("Discord запущен. Перезапускаем...", statuses)

    def test_restart_thread_start_is_protected_from_parallel_calls(self):
        from discord.discord import DiscordManager

        class SlowThread:
            created = []

            def __init__(self, target=None, daemon=None):
                self.target = target
                self.daemon = daemon
                self.started = False
                SlowThread.created.append(self)

            def is_alive(self):
                return self.started

            def start(self):
                time.sleep(0.02)
                self.started = True

        manager = DiscordManager(thread_factory=SlowThread)
        barrier = threading.Barrier(8)
        results = []
        results_lock = threading.Lock()

        def call_restart():
            barrier.wait()
            result = manager.restart_discord_if_running()
            with results_lock:
                results.append(result)

        callers = [threading.Thread(target=call_restart) for _ in range(8)]
        for caller in callers:
            caller.start()
        for caller in callers:
            caller.join()

        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 7)
        self.assertEqual(len(SlowThread.created), 1)


if __name__ == "__main__":
    unittest.main()
