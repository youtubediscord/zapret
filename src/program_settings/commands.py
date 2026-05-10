from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class AutoDpiUpdateResult:
    enabled: bool
    message: str
    title: str


@dataclass(slots=True)
class ProgramSettingActionResult:
    level: str
    title: str
    content: str
    revert_checked: bool | None
    final_status: str


def is_user_admin() -> bool:
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def is_auto_dpi_enabled() -> bool:
    try:
        from settings.store import get_dpi_autostart

        return bool(get_dpi_autostart())
    except Exception:
        return False


def set_auto_dpi_enabled(enabled: bool) -> AutoDpiUpdateResult:
    try:
        from settings.store import set_dpi_autostart

        set_dpi_autostart(bool(enabled))
    except Exception:
        pass

    message = (
        "DPI будет запускаться автоматически после старта ZapretGUI"
        if enabled
        else "Автозапуск DPI после старта программы отключён"
    )
    return AutoDpiUpdateResult(
        enabled=bool(enabled),
        message=message,
        title="Автозапуск DPI после старта программы",
    )


def set_defender_disabled(
    disable: bool,
    *,
    status_callback: Callable[[str], None] | None = None,
) -> ProgramSettingActionResult:
    try:
        from windows_features.defender_manager import WindowsDefenderManager
        from windows_features.defender_manager import set_defender_disabled as remember_defender_disabled

        manager = WindowsDefenderManager(status_callback=status_callback)

        if disable:
            success, count = manager.disable_defender()
            if success:
                remember_defender_disabled(True)
                return ProgramSettingActionResult(
                    level="success",
                    title="Windows Defender отключен",
                    content=(
                        "Windows Defender успешно отключен. "
                        f"Применено {count} настроек. Может потребоваться перезагрузка."
                    ),
                    revert_checked=None,
                    final_status="Готово",
                )
            return ProgramSettingActionResult(
                level="error",
                title="Ошибка",
                content=(
                    "Не удалось отключить Windows Defender. "
                    "Возможно, некоторые настройки заблокированы системой."
                ),
                revert_checked=False,
                final_status="Готово",
            )

        success, _count = manager.enable_defender()
        if success:
            remember_defender_disabled(False)
            return ProgramSettingActionResult(
                level="success",
                title="Windows Defender включен",
                content=(
                    "Windows Defender успешно включен. "
                    "Защита вашего компьютера восстановлена."
                ),
                revert_checked=None,
                final_status="Готово",
            )
        return ProgramSettingActionResult(
            level="warning",
            title="Частичный успех",
            content=(
                "Windows Defender включен частично. "
                "Некоторые настройки могут потребовать ручного исправления."
            ),
            revert_checked=None,
            final_status="Готово",
        )
    except Exception as e:
        return ProgramSettingActionResult(
            level="error",
            title="Ошибка",
            content=f"Произошла ошибка при изменении настроек Windows Defender: {e}",
            revert_checked=None,
            final_status="",
        )


def set_max_block_enabled(
    enable: bool,
    *,
    status_callback: Callable[[str], None] | None = None,
) -> ProgramSettingActionResult:
    try:
        from windows_features.max_blocker import MaxBlockerManager

        manager = MaxBlockerManager(status_callback=status_callback)

        if enable:
            success, message = manager.enable_blocking()
            if success:
                return ProgramSettingActionResult(
                    level="success",
                    title="Блокировка включена",
                    content=message,
                    revert_checked=None,
                    final_status="Готово",
                )
            return ProgramSettingActionResult(
                level="warning",
                title="Ошибка",
                content=f"Не удалось полностью включить блокировку: {message}",
                revert_checked=False,
                final_status="Готово",
            )

        success, message = manager.disable_blocking()
        if success:
            return ProgramSettingActionResult(
                level="success",
                title="Блокировка отключена",
                content=message,
                revert_checked=None,
                final_status="Готово",
            )
        return ProgramSettingActionResult(
            level="warning",
            title="Ошибка",
            content=f"Не удалось полностью отключить блокировку: {message}",
            revert_checked=None,
            final_status="Готово",
        )
    except Exception as e:
        return ProgramSettingActionResult(
            level="error",
            title="Ошибка",
            content=f"Ошибка при переключении блокировки MAX: {e}",
            revert_checked=None,
            final_status="",
        )
