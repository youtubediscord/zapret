from main.early_startup_crash import install_early_startup_crash_handler


install_early_startup_crash_handler()


def _run() -> None:
    from main.prelaunch import prepare_prelaunch

    prepare_prelaunch()
    from main.entry import main as run_main

    run_main()


if __name__ == "__main__":
    _run()
