# https://github.com/MagilaWEB/unblock-youtube-discord
# https://github.com/ankddev/zapret-discord-youtube

#config/config.py
import os, sys

# ═══════════════════════════════════════════════════════════════════
# ОСНОВНАЯ ПАПКА ПРОГРАММЫ
# ═══════════════════════════════════════════════════════════════════
# Путь определяется автоматически по расположению exe файла
# Работает независимо от того, куда пользователь установил программу
MAIN_DIRECTORY = os.path.dirname(sys.executable)

# Канал сборки (для информации)
try:
    from config.build_info import CHANNEL
except ImportError:
    CHANNEL = "stable"

# Путь к папке данных = путь установки программы
# (пользователь может выбрать любую папку в инсталляторе)
PROGRAMDATA_PATH = MAIN_DIRECTORY

# ═══════════════════════════════════════════════════════════════════

# Все папки относительно MAIN_DIRECTORY
BIN_FOLDER = os.path.join(MAIN_DIRECTORY, "bin")
BAT_FOLDER = os.path.join(MAIN_DIRECTORY, "bat")
INDEXJSON_FOLDER = os.path.join(MAIN_DIRECTORY, "json")
EXE_FOLDER = os.path.join(MAIN_DIRECTORY, "exe")
LUA_FOLDER = os.path.join(MAIN_DIRECTORY, "lua")  # Lua библиотеки для Zapret 2
ICO_FOLDER = os.path.join(MAIN_DIRECTORY, "ico")
LISTS_FOLDER = os.path.join(MAIN_DIRECTORY, "lists")
THEME_FOLDER = os.path.join(MAIN_DIRECTORY, "themes")
LOGS_FOLDER = os.path.join(MAIN_DIRECTORY, "logs")
HELP_FOLDER = os.path.join(MAIN_DIRECTORY, "help")

# Настройка количества сохраняемых лог-файлов
MAX_LOG_FILES = 50           # zapret_log_*.txt - основные логи приложения
MAX_DEBUG_LOG_FILES = 20     # zapret_winws2_debug_*.log - debug логи winws2

WINDIVERT_FILTER = os.path.join(MAIN_DIRECTORY, "windivert.filter")

# Пути к файлам
WINWS_EXE = os.path.join(EXE_FOLDER, "winws.exe")      # Для BAT режима (Zapret 1)
WINWS2_EXE = os.path.join(EXE_FOLDER, "winws2.exe")    # Для прямого запуска (Zapret 2)

# ═══════════════════════════════════════════════════════════════════
# ОПРЕДЕЛЕНИЕ EXE ПО МЕТОДУ ЗАПУСКА
# ═══════════════════════════════════════════════════════════════════
# Все режимы, которые используют winws2.exe (Zapret 2 с Lua)
ZAPRET2_MODES = ("direct", "direct_orchestra", "orchestra")

def get_winws_exe_for_method(method: str) -> str:
    """
    Возвращает путь к winws exe в зависимости от метода запуска.

    Args:
        method: Метод запуска (direct, direct_orchestra, orchestra, bat)

    Returns:
        Путь к winws2.exe для Zapret 2 режимов, winws.exe для BAT режима
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

# ═══════════════════════════════════════════════════════════════════

ICON_PATH = os.path.join(ICO_FOLDER, "Zapret2.ico")
ICON_TEST_PATH = os.path.join(ICO_FOLDER, "ZapretDevLogo4.ico")

OTHER_PATH = os.path.join(LISTS_FOLDER, "other.txt")
OTHER2_PATH = os.path.join(LISTS_FOLDER, "other2.txt")
NETROGAT_PATH = os.path.join(LISTS_FOLDER, "netrogat.txt")
NETROGAT2_PATH = os.path.join(LISTS_FOLDER, "netrogat2.txt")

DEFAULT_STRAT = "Alt 2"
REG_LATEST_STRATEGY = "LastStrategy2"

# ═══════════════════════════════════════════════════════════════════
# ПУТИ РЕЕСТРА (все в одном месте)
# ═══════════════════════════════════════════════════════════════════
# Базовый путь зависит от канала сборки (stable/test)
REGISTRY_PATH = r"Software\Zapret2DevReg" if CHANNEL == "test" else r"Software\Zapret2Reg"

# Подпути внутри базового пути
REGISTRY_PATH_AUTOSTART = rf"{REGISTRY_PATH}\Autostart"         # Настройки автозапуска
REGISTRY_PATH_GUI = rf"{REGISTRY_PATH}\GUI"                     # Настройки GUI (MAX blocker, donate и т.д.)
REGISTRY_PATH_DIRECT = rf"{REGISTRY_PATH}\DirectAutostart"      # Настройки Direct режима
REGISTRY_PATH_STRATEGIES = rf"{REGISTRY_PATH}\Strategies"       # Настройки стратегий
REGISTRY_PATH_WINDOW = rf"{REGISTRY_PATH}\Window"               # Позиция и размер окна
# ═══════════════════════════════════════════════════════════════════

# Настройки для GitHub стратегий
STRATEGIES_FOLDER = BAT_FOLDER

BASE_WIDTH = 1000  # Базовый размер для бокового меню в стиле Windows 11
BASE_HEIGHT = 950  # Базовая высота для нового интерфейса
MIN_WIDTH = 680    # Минимальная ширина (уменьшено для экранов 1366x768)
MIN_HEIGHT = 580   # Минимальная высота (уменьшено для экранов 1366x768)

def get_display_scale():
    """Получает масштабирование экрана Windows (например, 1.0, 1.25, 1.5, 1.75, 2.0)"""
    try:
        import ctypes
        # Включаем DPI awareness для получения реального масштаба
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass
        
        # Получаем DPI экрана
        hdc = ctypes.windll.user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX = 88
        ctypes.windll.user32.ReleaseDC(0, hdc)
        
        # Стандартный DPI = 96, масштаб = DPI / 96
        scale = dpi / 96.0
        return scale
    except Exception:
        return 1.0

def get_screen_resolution():
    """Получает реальное разрешение экрана в пикселях"""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        # Включаем DPI awareness для получения реального разрешения
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass
        screen_width = user32.GetSystemMetrics(0)   # SM_CXSCREEN
        screen_height = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        return screen_width, screen_height
    except Exception:
        return 1920, 1080  # Значение по умолчанию

def get_scaled_window_size():
    """Возвращает размер окна с учетом масштабирования и разрешения экрана"""
    scale = get_display_scale()
    screen_width, screen_height = get_screen_resolution()
    
    # Базовое разрешение для которого оптимизированы размеры окна
    REFERENCE_WIDTH = 1920
    REFERENCE_HEIGHT = 1080
    
    # Начинаем с базовых размеров
    width = BASE_WIDTH
    height = BASE_HEIGHT
    
    # Учитываем DPI масштабирование (при масштабе > 100% уменьшаем окно)
    if scale > 1.0:
        reduction = 1.0 / scale
        width = int(width * reduction)
        height = int(height * reduction)
    
    # Учитываем разрешение экрана если оно меньше 1920x1080
    if screen_width < REFERENCE_WIDTH or screen_height < REFERENCE_HEIGHT:
        # Вычисляем коэффициенты масштабирования по ширине и высоте
        width_ratio = screen_width / REFERENCE_WIDTH
        height_ratio = screen_height / REFERENCE_HEIGHT

        # Используем меньший коэффициент для сохранения пропорций
        # и чтобы окно гарантированно поместилось на экране
        screen_scale = min(width_ratio, height_ratio)

        # Применяем масштабирование, оставляя немного места для панели задач и рамок
        # Для маленьких экранов (1366x768) используем больший коэффициент
        margin_factor = 0.92 if screen_height <= 768 else 0.9
        width = int(BASE_WIDTH * screen_scale * margin_factor)
        height = int(BASE_HEIGHT * screen_scale * margin_factor)
    
    # Гарантируем минимальные размеры
    width = max(width, MIN_WIDTH)
    height = max(height, MIN_HEIGHT)
    
    return width, height

# Получаем актуальные размеры с учетом масштабирования
WIDTH, HEIGHT = get_scaled_window_size()

# Discord TCP конфигурации

#DiscordFix (ALT v10).bat
Ankddev10_1 = ""

#$UDP6 = "--filter-udp=50000-65535 --dpi-desync=fake,split2 --dpi-desync-any-protocol --dpi-desync-cutoff=d2 --dpi-desync-fake-quic=quic_test_00.bin --new"

# Отладочная информация (можно убрать в продакшене)
if __name__ == "__main__":
    print(f"MAIN_DIRECTORY: {MAIN_DIRECTORY}")
    print(f"BAT_FOLDER: {BAT_FOLDER}")
    print(f"Существует BAT_FOLDER: {os.path.exists(BAT_FOLDER)}")


def get_window_position():
    """Получает сохраненную позицию окна из реестра"""
    try:
        import winreg
        from log import log

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH, 0, winreg.KEY_READ)
        try:
            x = winreg.QueryValueEx(key, "WindowX")[0]
            y = winreg.QueryValueEx(key, "WindowY")[0]
            winreg.CloseKey(key)
            return (x, y)
        except FileNotFoundError:
            winreg.CloseKey(key)
            return None
    except Exception as e:
        log(f"Ошибка чтения позиции окна: {e}", "DEBUG")
        return None

def set_window_position(x, y):
    """Сохраняет позицию окна в реестр"""
    try:
        import winreg
        from log import log

        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH)
        winreg.SetValueEx(key, "WindowX", 0, winreg.REG_DWORD, int(x))
        winreg.SetValueEx(key, "WindowY", 0, winreg.REG_DWORD, int(y))
        winreg.CloseKey(key)
        log(f"Позиция окна сохранена: ({x}, {y})", "DEBUG")
        return True
    except Exception as e:
        log(f"Ошибка сохранения позиции окна: {e}", "❌ ERROR")
        return False

def get_window_size():
    """Получает сохраненный размер окна из реестра"""
    try:
        import winreg
        from log import log

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH, 0, winreg.KEY_READ)
        try:
            width = winreg.QueryValueEx(key, "WindowWidth")[0]
            height = winreg.QueryValueEx(key, "WindowHeight")[0]
            winreg.CloseKey(key)
            return (width, height)
        except FileNotFoundError:
            winreg.CloseKey(key)
            return None
    except Exception as e:
        log(f"Ошибка чтения размера окна: {e}", "DEBUG")
        return None

def set_window_size(width, height):
    """Сохраняет размер окна в реестр"""
    try:
        import winreg
        from log import log
        
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH)
        winreg.SetValueEx(key, "WindowWidth", 0, winreg.REG_DWORD, int(width))
        winreg.SetValueEx(key, "WindowHeight", 0, winreg.REG_DWORD, int(height))
        winreg.CloseKey(key)
        log(f"Размер окна сохранен: ({width}x{height})", "DEBUG")
        return True
    except Exception as e:
        log(f"Ошибка сохранения размера окна: {e}", "❌ ERROR")
        return False

def get_wall_animation_enabled():
    """Получает настройку анимации стены из реестра (по умолчанию включена)"""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH_GUI, 0, winreg.KEY_READ)
        try:
            enabled = winreg.QueryValueEx(key, "WallAnimationEnabled")[0]
            winreg.CloseKey(key)
            return bool(enabled)
        except FileNotFoundError:
            winreg.CloseKey(key)
            return True  # По умолчанию анимация включена
    except Exception:
        return True  # По умолчанию анимация включена

def set_wall_animation_enabled(enabled: bool):
    """Сохраняет настройку анимации стены в реестр"""
    try:
        import winreg
        from log import log
        
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH_GUI)
        winreg.SetValueEx(key, "WallAnimationEnabled", 0, winreg.REG_DWORD, int(enabled))
        winreg.CloseKey(key)
        log(f"Анимация стены {'включена' if enabled else 'отключена'}", "DEBUG")
        return True
    except Exception as e:
        try:
            from log import log
            log(f"Ошибка сохранения настройки анимации: {e}", "❌ ERROR")
        except:
            pass
        return False