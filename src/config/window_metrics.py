import ctypes

BASE_WIDTH = 1000
BASE_HEIGHT = 950
MIN_WIDTH = 680
MIN_HEIGHT = 580

PROCESS_SYSTEM_DPI_AWARE = 1
LOGPIXELSX = 88
SM_CXSCREEN = 0
SM_CYSCREEN = 1
USER_DEFAULT_SCREEN_DPI = 96
DEFAULT_SCREEN_WIDTH = 1920
DEFAULT_SCREEN_HEIGHT = 1080
_DPI_AWARENESS_SET = False


def _ensure_dpi_awareness() -> None:
    """Пытается включить DPI-awareness один раз за процесс."""
    global _DPI_AWARENESS_SET
    if _DPI_AWARENESS_SET:
        return

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(PROCESS_SYSTEM_DPI_AWARE)
    except (AttributeError, OSError):
        pass

    _DPI_AWARENESS_SET = True


def _get_screen_dpi() -> int | None:
    """Возвращает DPI основного экрана или None, если не удалось."""
    try:
        _ensure_dpi_awareness()
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        hdc = user32.GetDC(0)
        if not hdc:
            return None
        try:
            dpi = int(gdi32.GetDeviceCaps(hdc, LOGPIXELSX))
            return dpi if dpi > 0 else None
        finally:
            user32.ReleaseDC(0, hdc)
    except (AttributeError, OSError, ValueError):
        return None


def _get_primary_screen_size() -> tuple[int, int] | None:
    """Возвращает размер основного экрана или None, если не удалось."""
    try:
        _ensure_dpi_awareness()
        user32 = ctypes.windll.user32
        screen_width = int(user32.GetSystemMetrics(SM_CXSCREEN))
        screen_height = int(user32.GetSystemMetrics(SM_CYSCREEN))
        if screen_width > 0 and screen_height > 0:
            return screen_width, screen_height
    except (AttributeError, OSError, ValueError):
        pass
    return None


def get_display_scale():
    """Получает масштабирование экрана Windows."""
    dpi = _get_screen_dpi()
    if dpi is None:
        return 1.0
    return dpi / USER_DEFAULT_SCREEN_DPI


def get_screen_resolution():
    """Получает реальное разрешение экрана в пикселях."""
    size = _get_primary_screen_size()
    if size is None:
        return DEFAULT_SCREEN_WIDTH, DEFAULT_SCREEN_HEIGHT
    return size


def get_scaled_window_size():
    """Возвращает размер окна с учетом масштаба и разрешения экрана."""
    scale = get_display_scale()
    screen_width, screen_height = get_screen_resolution()

    reference_width = DEFAULT_SCREEN_WIDTH
    reference_height = DEFAULT_SCREEN_HEIGHT
    width = BASE_WIDTH
    height = BASE_HEIGHT

    if scale > 1.0:
        reduction = 1.0 / scale
        width = int(width * reduction)
        height = int(height * reduction)

    if screen_width < reference_width or screen_height < reference_height:
        width_ratio = screen_width / reference_width
        height_ratio = screen_height / reference_height
        screen_scale = min(width_ratio, height_ratio)
        margin_factor = 0.92 if screen_height <= 768 else 0.9
        width = int(BASE_WIDTH * screen_scale * margin_factor)
        height = int(BASE_HEIGHT * screen_scale * margin_factor)

    width = max(width, MIN_WIDTH)
    height = max(height, MIN_HEIGHT)
    return width, height


WIDTH, HEIGHT = get_scaled_window_size()
