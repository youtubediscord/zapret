# https://github.com/MagilaWEB/unblock-youtube-discord
# https://github.com/ankddev/zapret-discord-youtube

#config/config.py

# Канал сборки (для информации)
from config.build_info import CHANNEL

CHANNEL_STABLE = "stable"
CHANNEL_DEV = "dev"


def is_dev_build_channel() -> bool:
    """True для dev-канала сборки."""
    return str(CHANNEL or "").strip().lower() == CHANNEL_DEV

# Настройка количества сохраняемых лог-файлов
MAX_LOG_FILES = 50           # zapret_log_*.txt - основные логи приложения
MAX_DEBUG_LOG_FILES = 20     # zapret_winws2_debug_*.log - debug логи winws2

# Discord TCP конфигурации

# DiscordFix (ALT v10)
Ankddev10_1 = ""

#$UDP6 = "--filter-udp=50000-65535 --dpi-desync=fake,split2 --dpi-desync-any-protocol --dpi-desync-cutoff=d2 --dpi-desync-fake-quic=quic_test_00.bin --new"
