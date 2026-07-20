# https://github.com/MagilaWEB/unblock-youtube-discord
# https://github.com/ankddev/zapret-discord-youtube

#config/config.py
import os

from config.runtime_layout import APPLICATION_ROOT

# ═══════════════════════════════════════════════════════════════════
# ОСНОВНАЯ ПАПКА ПРОГРАММЫ
# ═══════════════════════════════════════════════════════════════════
# Единственный источник истины для собранного приложения.
# Импорт из исходников допустим только для тестов и сборочных инструментов.
# В установленной сборке ресурсы принадлежат корню над `_internal`.
MAIN_DIRECTORY = str(APPLICATION_ROOT)

# Канал сборки (для информации)
from config.build_info import CHANNEL

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


# Все папки относительно MAIN_DIRECTORY
BIN_FOLDER = os.path.join(MAIN_DIRECTORY, "bin")
INDEXJSON_FOLDER = os.path.join(MAIN_DIRECTORY, "json")
EXE_FOLDER = os.path.join(MAIN_DIRECTORY, "exe")
LUA_FOLDER = os.path.join(MAIN_DIRECTORY, "lua")  # Lua библиотеки для Zapret 2
ICO_FOLDER = os.path.join(MAIN_DIRECTORY, "ico")
THEME_FOLDER = os.path.join(MAIN_DIRECTORY, "themes")
LOGS_FOLDER = os.path.join(MAIN_DIRECTORY, "logs")

# Настройка количества сохраняемых лог-файлов
MAX_LOG_FILES = 50           # zapret_log_*.txt - основные логи приложения
MAX_DEBUG_LOG_FILES = 20     # zapret_winws2_debug_*.log - debug логи winws2

WINDIVERT_FILTER = os.path.join(MAIN_DIRECTORY, "windivert.filter")

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
