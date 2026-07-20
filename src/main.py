import sys

from config.runtime_layout import SourceApplicationLaunchForbidden, require_packaged_application


try:
    require_packaged_application()
except SourceApplicationLaunchForbidden as exc:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            0,
            str(exc),
            "Zapret — запуск запрещён",
            0x10,
        )
    except Exception:
        print(str(exc))
    raise SystemExit(1)


import main.process_start_time  # noqa: E402,F401  # первым после проверки packaged runtime

from main.early_startup_crash import install_early_startup_crash_handler  # noqa: E402


install_early_startup_crash_handler()

from startup.windows_version_guard import enforce_early_windows_version_guard  # noqa: E402

enforce_early_windows_version_guard()


def _run() -> None:
    from main.prelaunch import prepare_prelaunch

    prepare_prelaunch()
    from main.entry import main as run_main

    run_main()


if __name__ == "__main__":
    _run()
