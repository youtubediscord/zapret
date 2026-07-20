from __future__ import annotations

from pathlib import Path
import sys


RUNTIME_DIR_NAME = "_internal"
RUNTIME_EXE_NAME = "Zapret.exe"


class SourceApplicationLaunchForbidden(RuntimeError):
    pass


def is_packaged_runtime() -> bool:
    """True, только если процесс собран PyInstaller или Nuitka."""
    return bool(getattr(sys, "frozen", False) or "__compiled__" in globals())


def require_packaged_application() -> None:
    """Запрещает вход в приложение из обычного Python-сценария."""
    if is_packaged_runtime():
        return
    raise SourceApplicationLaunchForbidden(
        "Запуск приложения из исходников запрещён. "
        f"Используйте установленный {RUNTIME_DIR_NAME}\\{RUNTIME_EXE_NAME}."
    )


def resolve_application_root(
    *,
    executable: str | Path,
    module_file: str | Path,
    packaged: bool,
) -> Path:
    """Возвращает единственный корень ресурсов и пользовательского состояния.

    Собранное приложение поддерживает только одну структуру::

        <app root>/_internal/Zapret.exe

    Тесты и сборочные инструменты могут импортировать модули из репозитория.
    Само приложение до импорта своих модулей обязано вызвать
    ``require_packaged_application``.
    """
    if packaged:
        runtime_root = Path(executable).resolve().parent
        if runtime_root.name.casefold() != RUNTIME_DIR_NAME.casefold():
            raise RuntimeError(
                "Некорректная структура установленного Zapret: "
                f"ожидался запуск из папки {RUNTIME_DIR_NAME}, получено {runtime_root}"
            )
        return runtime_root.parent

    # config/runtime_layout.py -> config -> src -> public_zapretgui
    return Path(module_file).resolve().parents[2]


def resolve_runtime_root(*, executable: str | Path, packaged: bool) -> Path | None:
    if not packaged:
        return None
    runtime_root = Path(executable).resolve().parent
    if runtime_root.name.casefold() != RUNTIME_DIR_NAME.casefold():
        raise RuntimeError(
            "Некорректная структура среды Zapret: "
            f"ожидалась папка {RUNTIME_DIR_NAME}, получено {runtime_root}"
        )
    return runtime_root


PACKAGED_RUNTIME = is_packaged_runtime()
APPLICATION_ROOT = resolve_application_root(
    executable=sys.executable,
    module_file=__file__,
    packaged=PACKAGED_RUNTIME,
)
RUNTIME_ROOT = resolve_runtime_root(
    executable=sys.executable,
    packaged=PACKAGED_RUNTIME,
)


__all__ = [
    "APPLICATION_ROOT",
    "PACKAGED_RUNTIME",
    "RUNTIME_DIR_NAME",
    "RUNTIME_EXE_NAME",
    "RUNTIME_ROOT",
    "SourceApplicationLaunchForbidden",
    "is_packaged_runtime",
    "require_packaged_application",
    "resolve_application_root",
    "resolve_runtime_root",
]
