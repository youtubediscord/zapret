# https://github.com/MagilaWEB/unblock-youtube-discord
# https://github.com/ankddev/zapret-discord-youtube

#config/config.py
import os, sys

# ═══════════════════════════════════════════════════════════════════
# ОСНОВНАЯ ПАПКА ПРОГРАММЫ
# ═══════════════════════════════════════════════════════════════════
# Путь определяется автоматически по расположению exe файла.
MAIN_DIRECTORY = os.path.dirname(sys.executable)

# Канал сборки (для информации)
try:
    from config.build_info import CHANNEL
except ImportError:
    CHANNEL = "stable"

CHANNEL_STABLE = "stable"
CHANNEL_DEV = "dev"
INSTALL_DIR_STABLE = "Stable"
INSTALL_DIR_DEV = "Dev"

def get_system_drive() -> str:
    """Возвращает системный диск Windows, обычно `C:`."""
    return (os.environ.get("SystemDrive") or "C:").strip() or "C:"


def is_dev_build_channel() -> bool:
    """True для dev-канала сборки."""
    return str(CHANNEL or "").strip().lower() == CHANNEL_DEV


def get_install_dir_name() -> str:
    """Возвращает имя папки установки по каналу: `Dev` или `Stable`."""
    return INSTALL_DIR_DEV if is_dev_build_channel() else INSTALL_DIR_STABLE


def get_default_install_dir() -> str:
    """Возвращает базовый путь установки по каналу."""
    return os.path.join(get_system_drive(), "Zapret", get_install_dir_name())


def get_presets_root_dir() -> str:
    """Возвращает общий корень всех пресетов рядом с программой."""
    return os.path.join(MAIN_DIRECTORY, "presets")


def get_presets_v1_dir() -> str:
    """Возвращает пользовательскую папку пресетов Zapret 1."""
    return os.path.join(get_presets_root_dir(), "presets_v1")


def get_presets_v2_dir() -> str:
    """Возвращает пользовательскую папку пресетов Zapret 2."""
    return os.path.join(get_presets_root_dir(), "presets_v2")


def get_builtin_presets_v1_dir() -> str:
    """Возвращает системную папку встроенных пресетов Zapret 1."""
    return os.path.join(get_presets_root_dir(), "presets_v1_builtin")


def get_builtin_presets_v2_dir() -> str:
    """Возвращает системную папку встроенных пресетов Zapret 2."""
    return os.path.join(get_presets_root_dir(), "presets_v2_builtin")

# ═══════════════════════════════════════════════════════════════════

# Все папки относительно MAIN_DIRECTORY
BIN_FOLDER = os.path.join(MAIN_DIRECTORY, "bin")
INDEXJSON_FOLDER = os.path.join(MAIN_DIRECTORY, "json")
EXE_FOLDER = os.path.join(MAIN_DIRECTORY, "exe")
LUA_FOLDER = os.path.join(MAIN_DIRECTORY, "lua")  # Lua библиотеки для Zapret 2
ICO_FOLDER = os.path.join(MAIN_DIRECTORY, "ico")
THEME_FOLDER = os.path.join(MAIN_DIRECTORY, "themes")
LOGS_FOLDER = os.path.join(MAIN_DIRECTORY, "logs")
HELP_FOLDER = os.path.join(MAIN_DIRECTORY, "help")

# Настройка количества сохраняемых лог-файлов
MAX_LOG_FILES = 50           # zapret_log_*.txt - основные логи приложения
MAX_DEBUG_LOG_FILES = 20     # zapret_winws2_debug_*.log - debug логи winws2

WINDIVERT_FILTER = os.path.join(MAIN_DIRECTORY, "windivert.filter")

# Пути к файлам
WINWS_EXE = os.path.join(EXE_FOLDER, "winws.exe")      # Для Zapret 1
WINWS2_EXE = os.path.join(EXE_FOLDER, "winws2.exe")    # Для Zapret 2

# ═══════════════════════════════════════════════════════════════════
# ОПРЕДЕЛЕНИЕ EXE ПО МЕТОДУ ЗАПУСКА
# ═══════════════════════════════════════════════════════════════════
# Все режимы, которые используют winws2.exe (Zapret 2 с Lua)
ZAPRET2_MODES = ("direct_zapret2", "orchestra")
# Режимы, которые используют winws.exe (Zapret 1)
ZAPRET1_DIRECT_MODES = ("direct_zapret1",)

def get_winws_exe_for_method(method: str) -> str:
    """
    Возвращает путь к winws exe в зависимости от метода запуска.

    Args:
        method: Метод запуска (direct_zapret2, orchestra, direct_zapret1)

    Returns:
        Путь к winws2.exe для Zapret 2 режимов, winws.exe для остальных
    """
    if method in ZAPRET2_MODES:
        return WINWS2_EXE
    return WINWS_EXE

def is_zapret2_mode(method: str) -> bool:
    """
    Проверяет, является ли метод режимом Zapret 2 (использует winws2.exe).

    Args:
        method: Метод запуска

    Returns:
        True если режим использует winws2.exe
    """
    return method in ZAPRET2_MODES

def is_zapret1_direct_mode(method: str) -> bool:
    """
    Проверяет, является ли метод режимом Zapret 1 (winws.exe).

    Args:
        method: Метод запуска

    Returns:
        True если режим использует winws.exe
    """
    return method in ZAPRET1_DIRECT_MODES


def get_current_winws_exe() -> str:
    """
    ЕДИНАЯ точка определения winws.exe для всего проекта.

    Получает текущий метод запуска из реестра и возвращает
    соответствующий путь к исполняемому файлу.

    Returns:
        Путь к winws2.exe для Zapret 2 режимов (direct_zapret2, orchestra),
        winws.exe для Zapret 1 режимов (direct_zapret1)

    Примечание:
        Используйте эту функцию когда метод запуска не передаётся явно.
        Если метод известен заранее, используйте get_winws_exe_for_method(method).
    """
    try:
        from log.log import log

    except ImportError:
        log = lambda msg, level="DEBUG": print(f"[{level}] {msg}")

    try:
        # Импортируем здесь чтобы избежать циклических зависимостей
        from settings.dpi.strategy_settings import get_strategy_launch_method

        method = get_strategy_launch_method()
        exe_path = get_winws_exe_for_method(method)

        log(f"get_current_winws_exe(): method={method}, exe={os.path.basename(exe_path)}", "DEBUG")

        return exe_path

    except Exception as e:
        # Fallback - возвращаем winws2.exe (Zapret 2) как основной вариант
        log(f"get_current_winws_exe() error: {e}, fallback to winws2.exe", "DEBUG")
        return WINWS2_EXE


# ═══════════════════════════════════════════════════════════════════

ICON_PATH = os.path.join(ICO_FOLDER, "Zapret2.ico")
ICON_DEV_PATH = os.path.join(ICO_FOLDER, "ZapretDevLogo4.ico")

# Discord TCP конфигурации

# DiscordFix (ALT v10)
Ankddev10_1 = ""

#$UDP6 = "--filter-udp=50000-65535 --dpi-desync=fake,split2 --dpi-desync-any-protocol --dpi-desync-cutoff=d2 --dpi-desync-fake-quic=quic_test_00.bin --new"

# Отладочная информация (можно убрать в продакшене)
if __name__ == "__main__":
    print(f"MAIN_DIRECTORY: {MAIN_DIRECTORY}")
    print(f"EXE_FOLDER: {EXE_FOLDER}")
    print(f"Существует EXE_FOLDER: {os.path.exists(EXE_FOLDER)}")
