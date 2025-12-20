# ui/acrylic.py
"""
Acrylic/Mica Effect для Windows 11
Создаёт полупрозрачный размытый фон в стиле Windows 11
"""
import ctypes
from ctypes import wintypes
import sys

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from log import log


class ACCENT_POLICY(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_int),
    ]


class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [
        ("Attrib", ctypes.c_int),
        ("pvData", ctypes.c_void_p),
        ("cbData", ctypes.c_size_t),
    ]


class MARGINS(ctypes.Structure):
    _fields_ = [
        ("cxLeftWidth", ctypes.c_int),
        ("cxRightWidth", ctypes.c_int),
        ("cyTopHeight", ctypes.c_int),
        ("cyBottomHeight", ctypes.c_int),
    ]


# Константы для Windows API
ACCENT_DISABLED = 0
ACCENT_ENABLE_GRADIENT = 1
ACCENT_ENABLE_TRANSPARENTGRADIENT = 2
ACCENT_ENABLE_BLURBEHIND = 3
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4  # Windows 10 1803+
ACCENT_ENABLE_HOSTBACKDROP = 5  # Windows 11

WCA_ACCENT_POLICY = 19
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_MICA_EFFECT = 1029
DWMWA_SYSTEMBACKDROP_TYPE = 38

# Backdrop Types для Windows 11
DWMSBT_MAINWINDOW = 2  # Mica
DWMSBT_TRANSIENTWINDOW = 3  # Acrylic
DWMSBT_TABBEDWINDOW = 4  # Tabbed

# Window Corner Preference для Windows 11
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_DEFAULT = 0
DWMWCP_DONOTROUND = 1
DWMWCP_ROUND = 2
DWMWCP_ROUNDSMALL = 3


def get_windows_build():
    """Возвращает номер сборки Windows"""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
        build = winreg.QueryValueEx(key, "CurrentBuildNumber")[0]
        return int(build)
    except:
        return 0


def is_pyinstaller_build() -> bool:
    """Проверяет, запущено ли приложение из PyInstaller сборки"""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def apply_translucent_background(widget: QWidget, opacity: float = 0.92):
    """
    Применяет полупрозрачный фон через Qt (безопасная альтернатива Acrylic).
    Работает стабильно в PyInstaller сборках.
    
    Args:
        widget: QWidget окна
        opacity: Прозрачность (0.0 - полностью прозрачный, 1.0 - непрозрачный)
    """
    try:
        # Устанавливаем атрибут для прозрачного фона
        widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        # Устанавливаем общую прозрачность окна
        widget.setWindowOpacity(opacity)
        
        log(f"Qt прозрачность применена (opacity={opacity})", "INFO")
        return True
    except Exception as e:
        log(f"Ошибка при применении Qt прозрачности: {e}", "WARNING")
        return False


def apply_blur_effect(widget: QWidget, color: QColor = None):
    """
    Применяет Blur эффект (более стабильный чем Acrylic).
    Безопасен для PyInstaller сборок.
    
    Args:
        widget: QWidget окна
        color: Цвет подложки (с альфа-каналом)
    """
    if sys.platform != 'win32':
        return False
    
    try:
        hwnd = int(widget.winId())
    except Exception:
        return False
        
    if hwnd == 0:
        return False
    
    build = get_windows_build()
    
    if color is None:
        color = QColor(25, 25, 25, 180)
    
    try:
        user32 = ctypes.windll.user32
        
        # Используем SetWindowCompositionAttribute с BLUR (не ACRYLIC!)
        SetWindowCompositionAttribute = user32.SetWindowCompositionAttribute
        SetWindowCompositionAttribute.argtypes = [wintypes.HWND, ctypes.POINTER(WINDOWCOMPOSITIONATTRIBDATA)]
        SetWindowCompositionAttribute.restype = ctypes.c_int
        
        # Конвертируем QColor в ARGB
        gradient_color = (
            (color.alpha() << 24) |
            (color.blue() << 16) |
            (color.green() << 8) |
            color.red()
        )
        
        # Создаём политику акцента - BLUR (более стабильный!)
        accent = ACCENT_POLICY()
        accent.AccentState = ACCENT_ENABLE_BLURBEHIND  # Blur вместо Acrylic!
        accent.AccentFlags = 2
        accent.GradientColor = gradient_color
        
        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attrib = WCA_ACCENT_POLICY
        data.pvData = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
        data.cbData = ctypes.sizeof(accent)
        
        result = SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
        
        if result:
            log(f"Blur эффект применён (build {build})", "INFO")
            return True
        else:
            log("Не удалось применить Blur эффект", "WARNING")
            return False
            
    except Exception as e:
        log(f"Ошибка при применении Blur: {e}", "WARNING")
        return False


def apply_dark_titlebar(widget: QWidget):
    """
    Применяет тёмную тему к системному titlebar (безопасно для PyInstaller).
    Не использует Acrylic/Mica, только цвет titlebar.
    """
    if sys.platform != 'win32':
        return False
    
    try:
        hwnd = int(widget.winId())
        if hwnd == 0:
            return False
            
        dwmapi = ctypes.windll.dwmapi
        
        # Только тёмная тема для titlebar - это безопасно
        value = ctypes.c_int(1)
        result = dwmapi.DwmSetWindowAttribute(
            hwnd, 
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value),
            ctypes.sizeof(value)
        )
        
        if result == 0:
            log("Тёмный titlebar применён", "INFO")
            return True
        return False
        
    except Exception as e:
        log(f"Ошибка при применении тёмного titlebar: {e}", "WARNING")
        return False


def apply_acrylic_effect(widget: QWidget, color: QColor = None, dark_mode: bool = True):
    """
    Применяет Acrylic эффект к окну.
    
    Args:
        widget: QWidget окна
        color: Цвет подложки (с альфа-каналом)
        dark_mode: Использовать темную тему
    """
    if sys.platform != 'win32':
        log("Acrylic effect доступен только на Windows", "WARNING")
        return False
    
    # ⚠️ ОТКЛЮЧАЕМ ACRYLIC ДЛЯ PYINSTALLER СБОРОК
    # Причина: crash в Qt6Gui.dll (Access Violation) при использовании DWM API
    if is_pyinstaller_build():
        log("Acrylic отключен для PyInstaller сборки (стабильность)", "INFO")
        return False
    
    # Проверяем, что виджет существует и видим
    if widget is None or not widget.isVisible():
        log("Виджет не готов для Acrylic эффекта", "WARNING")
        return False
    
    try:
        hwnd = int(widget.winId())
    except Exception as e:
        log(f"Не удалось получить HWND: {e}", "WARNING")
        return False
        
    if hwnd == 0:
        log("Невалидный HWND для Acrylic", "WARNING")
        return False
        
    build = get_windows_build()
    
    if color is None:
        # Тёмный полупрозрачный фон
        color = QColor(25, 25, 25, 200)
    
    try:
        # Загружаем DLL
        user32 = ctypes.windll.user32
        dwmapi = ctypes.windll.dwmapi
        
        # Включаем тёмную тему для titlebar
        if dark_mode:
            value = ctypes.c_int(1)
            dwmapi.DwmSetWindowAttribute(
                hwnd, 
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(value),
                ctypes.sizeof(value)
            )
        
        # Windows 11 (build 22000+) - используем новый API
        if build >= 22000:
            # Отключаем системное скругление - используем CSS border-radius
            corner_preference = ctypes.c_int(DWMWCP_DONOTROUND)
            dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(corner_preference),
                ctypes.sizeof(corner_preference)
            )

            # Пробуем Acrylic через новый API
            backdrop_type = ctypes.c_int(DWMSBT_TRANSIENTWINDOW)  # Acrylic
            result = dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_SYSTEMBACKDROP_TYPE,
                ctypes.byref(backdrop_type),
                ctypes.sizeof(backdrop_type)
            )

            if result == 0:
                log(f"Windows 11 Acrylic применён (build {build})", "INFO")
                return True
        
        # Windows 10/11 fallback - используем SetWindowCompositionAttribute
        SetWindowCompositionAttribute = user32.SetWindowCompositionAttribute
        SetWindowCompositionAttribute.argtypes = [wintypes.HWND, ctypes.POINTER(WINDOWCOMPOSITIONATTRIBDATA)]
        SetWindowCompositionAttribute.restype = ctypes.c_int
        
        # Конвертируем QColor в ARGB
        gradient_color = (
            (color.alpha() << 24) |
            (color.blue() << 16) |
            (color.green() << 8) |
            color.red()
        )
        
        # Создаём политику акцента
        accent = ACCENT_POLICY()
        
        if build >= 17763:  # Windows 10 1809+
            accent.AccentState = ACCENT_ENABLE_ACRYLICBLURBEHIND
        else:
            accent.AccentState = ACCENT_ENABLE_BLURBEHIND
            
        accent.AccentFlags = 2  # Рисовать левую границу
        accent.GradientColor = gradient_color
        
        # Применяем
        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attrib = WCA_ACCENT_POLICY
        data.pvData = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
        data.cbData = ctypes.sizeof(accent)
        
        result = SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
        
        if result:
            log(f"Acrylic Blur применён (build {build})", "INFO")
            return True
        else:
            log("Не удалось применить Acrylic эффект", "WARNING")
            return False
            
    except Exception as e:
        log(f"Ошибка при применении Acrylic: {e}", "ERROR")
        return False


def disable_acrylic(widget: QWidget):
    """
    Отключает Acrylic эффект (для производительности при перемещении окна)
    """
    if sys.platform != 'win32':
        return False
    
    # Пропускаем для PyInstaller сборок
    if is_pyinstaller_build():
        return False
    
    # Проверяем валидность виджета
    if widget is None:
        return False
        
    try:
        hwnd = int(widget.winId())
    except Exception:
        return False
        
    if hwnd == 0:
        return False
        
    build = get_windows_build()
    
    try:
        user32 = ctypes.windll.user32
        dwmapi = ctypes.windll.dwmapi
        
        # Windows 11 - отключаем backdrop
        if build >= 22000:
            # Оставляем отключённое системное скругление (используем CSS)
            corner_preference = ctypes.c_int(DWMWCP_DONOTROUND)
            dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(corner_preference),
                ctypes.sizeof(corner_preference)
            )

            backdrop_type = ctypes.c_int(0)  # DWMSBT_NONE
            dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_SYSTEMBACKDROP_TYPE,
                ctypes.byref(backdrop_type),
                ctypes.sizeof(backdrop_type)
            )
            return True
        
        # Windows 10 - отключаем через SetWindowCompositionAttribute
        SetWindowCompositionAttribute = user32.SetWindowCompositionAttribute
        SetWindowCompositionAttribute.argtypes = [wintypes.HWND, ctypes.POINTER(WINDOWCOMPOSITIONATTRIBDATA)]
        SetWindowCompositionAttribute.restype = ctypes.c_int
        
        accent = ACCENT_POLICY()
        accent.AccentState = ACCENT_DISABLED
        accent.AccentFlags = 0
        accent.GradientColor = 0
        
        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attrib = WCA_ACCENT_POLICY
        data.pvData = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
        data.cbData = ctypes.sizeof(accent)
        
        SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
        return True
        
    except Exception as e:
        log(f"Ошибка при отключении Acrylic: {e}", "ERROR")
        return False


def apply_mica_effect(widget: QWidget, dark_mode: bool = True):
    """
    Применяет Mica эффект (только Windows 11)
    """
    if sys.platform != 'win32':
        return False
    
    # Пропускаем для PyInstaller сборок
    if is_pyinstaller_build():
        log("Mica отключен для PyInstaller сборки", "INFO")
        return False
    
    build = get_windows_build()
    if build < 22000:
        log("Mica доступен только в Windows 11", "WARNING")
        return False
    
    # Проверяем валидность виджета
    if widget is None:
        return False
        
    try:
        hwnd = int(widget.winId())
    except Exception:
        return False
        
    if hwnd == 0:
        return False
    
    try:
        dwmapi = ctypes.windll.dwmapi
        
        # Включаем тёмную тему
        if dark_mode:
            value = ctypes.c_int(1)
            dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(value),
                ctypes.sizeof(value)
            )
        
        # Применяем Mica
        backdrop_type = ctypes.c_int(DWMSBT_MAINWINDOW)
        result = dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_SYSTEMBACKDROP_TYPE,
            ctypes.byref(backdrop_type),
            ctypes.sizeof(backdrop_type)
        )
        
        if result == 0:
            log("Mica эффект применён", "INFO")
            return True
        
        return False
        
    except Exception as e:
        log(f"Ошибка при применении Mica: {e}", "ERROR")
        return False


def extend_frame_into_client_area(widget: QWidget):
    """
    Расширяет рамку окна в клиентскую область для эффектов
    """
    if sys.platform != 'win32':
        return False
    
    # Пропускаем для PyInstaller сборок
    if is_pyinstaller_build():
        return False
    
    # Проверяем валидность виджета
    if widget is None:
        return False
    
    try:
        hwnd = int(widget.winId())
        if hwnd == 0:
            return False
        dwmapi = ctypes.windll.dwmapi
        
        margins = MARGINS()
        margins.cxLeftWidth = -1
        margins.cxRightWidth = -1
        margins.cyTopHeight = -1
        margins.cyBottomHeight = -1
        
        dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))
        return True
        
    except Exception as e:
        log(f"Ошибка при расширении рамки: {e}", "ERROR")
        return False

