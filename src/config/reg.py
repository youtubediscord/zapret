# reg.py ─ универсальный helper для работы с реестром
import sys
import winreg

HKCU = winreg.HKEY_CURRENT_USER
HKLM = winreg.HKEY_LOCAL_MACHINE

def _log(msg, level="INFO"):
    """Отложенный импорт log для избежания циклических зависимостей"""
    try:
        from log import log
        log(msg, level)
    except ImportError:
        print(f"[{level}] {msg}")

# Специальная константа для обозначения отсутствующего значения
class _UnsetType:
    """Sentinel object для обозначения 'не задано'"""
    def __repr__(self):
        return "<UNSET>"

_UNSET = _UnsetType()

def _detect_reg_type(value):
    """Определяет подходящий winreg тип по питоновскому value."""
    if isinstance(value, str):
        return winreg.REG_SZ
    if isinstance(value, int):
        return winreg.REG_DWORD
    if isinstance(value, bytes):
        return winreg.REG_BINARY
    # fallback – строка
    return winreg.REG_SZ


def reg(subkey: str,
        name: str | None = None,
        value=_UNSET,
        *,
        root=HKCU):
    """
    Упрощённый доступ к реестру.

    Аргументы
    ---------
    subkey : str
        Путь относительно root, например 'Software\\Zapret'
    name : str | None
        Имя параметра.  Если None → работаем с default-value.
    value :  _UNSET  → чтение,
             None    → удаление параметра,
             любое другое → запись этого значения.
    root  : winreg.HKEY_*
        Hive (по-умолчанию HKCU).

    Возврат
    -------
    • при чтении – возвращает значение или None, если нет,
    • при записи / удалении – True/False (успех).
    """
    try:
        # --- чтение --------------------------------------------------
        if value is _UNSET:
            with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ) as k:
                data, _ = winreg.QueryValueEx(k, name)
                return data

        # --- удаление -----------------------------------------------
        if value is None:
            # открываем с правом WRITE
            with winreg.OpenKey(root, subkey, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, name or "")
            return True

        # --- запись --------------------------------------------------
        k = winreg.CreateKeyEx(root, subkey, 0, winreg.KEY_SET_VALUE)
        reg_type = _detect_reg_type(value)
        winreg.SetValueEx(k, name or "", 0, reg_type, value)
        winreg.CloseKey(k)
        return True

    except FileNotFoundError:
        # Ключ не найден - нормальная ситуация при первом запуске
        return None if value is _UNSET else False
    except Exception as e:
        # Логируем неожиданные ошибки
        try:
            from log import log
            log(f"❌ reg() error [{subkey}\\{name}]: {e}", "ERROR")
        except:
            print(f"[ERROR] reg error: {e}")
        return None if value is _UNSET else False


# ───────────── DPI-автозапуск ─────────────
_DPI_NAME  = "DPIAutoStart"          # REG_DWORD (0/1)

def get_dpi_autostart() -> bool:
    """True – запускать DPI автоматически; False – не запускать."""
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _DPI_NAME)
    return bool(val) if val is not None else True  # Default to True if not set

def set_dpi_autostart(state: bool) -> bool:
    """Сохраняет флаг автозапуска DPI в реестре."""
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _DPI_NAME, 1 if state else 0)


def get_subscription_check_interval() -> int:
    """Возвращает интервал проверки подписки в минутах (по умолчанию 10)"""
    from config import REGISTRY_PATH
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH) as key:
            value, _ = winreg.QueryValueEx(key, "SubscriptionCheckInterval")
            return max(1, int(value))  # Минимум 1 минута
    except FileNotFoundError:
        return 10  # По умолчанию 10 минут
    except Exception:
        return 10

def set_subscription_check_interval(minutes: int):
    """Устанавливает интервал проверки подписки в минутах"""
    from config import REGISTRY_PATH
    try:
        winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "SubscriptionCheckInterval", 0, winreg.REG_DWORD, int(minutes))
    except Exception as e:
        _log(f"Ошибка записи интервала проверки подписки: {e}", "❌ ERROR")

# ───────────── Удаление GitHub API из hosts ─────────────
_GITHUB_API_NAME = "RemoveGitHubAPI"     # REG_DWORD (1/0)

def get_remove_github_api() -> bool:
    """True – удалять api.github.com из hosts при запуске, False – не удалять."""
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _GITHUB_API_NAME)
    return bool(val) if val is not None else True # По умолчанию True

def set_remove_github_api(enabled: bool) -> bool:
    """Включает/выключает удаление api.github.com из hosts при запуске."""
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _GITHUB_API_NAME, 1 if enabled else 0)


# ───────────── Единоразовый bootstrap hosts ─────────────
_HOSTS_BOOTSTRAP_V1_DONE_NAME = "HostsBootstrapV1Done"  # REG_DWORD (1/0)

def get_hosts_bootstrap_v1_done() -> bool:
    """True - bootstrap hosts уже выполнен, False - ещё нет."""
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _HOSTS_BOOTSTRAP_V1_DONE_NAME)
    return bool(val) if val is not None else False

def set_hosts_bootstrap_v1_done(done: bool = True) -> bool:
    """Отмечает выполнение единоразового bootstrap hosts."""
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _HOSTS_BOOTSTRAP_V1_DONE_NAME, 1 if done else 0)


_HOSTS_BOOTSTRAP_SIGNATURE_NAME = "HostsBootstrapSignature"  # REG_SZ

def get_hosts_bootstrap_signature() -> str | None:
    """Возвращает последнюю применённую сигнатуру bootstrap hosts или None."""
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _HOSTS_BOOTSTRAP_SIGNATURE_NAME)
    if isinstance(val, str) and val.strip():
        return val
    return None

def set_hosts_bootstrap_signature(signature: str) -> bool:
    """Сохраняет сигнатуру применённого bootstrap hosts."""
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _HOSTS_BOOTSTRAP_SIGNATURE_NAME, str(signature))

# ───────────── Активные домены hosts ─────────────
_HOSTS_DOMAINS_NAME = "ActiveHostsDomains"  # REG_SZ (JSON строка)

def get_active_hosts_domains() -> set:
    """Возвращает множество активных доменов из реестра"""
    from config import REGISTRY_PATH
    import json
    try:
        val = reg(REGISTRY_PATH, _HOSTS_DOMAINS_NAME)
        if val:
            domains_list = json.loads(val)
            return set(domains_list)
    except Exception as e:
        _log(f"Ошибка чтения активных доменов: {e}", "DEBUG")
    return set()

def set_active_hosts_domains(domains: set) -> bool:
    """Сохраняет множество активных доменов в реестр"""
    from config import REGISTRY_PATH
    import json
    try:
        domains_json = json.dumps(list(domains))
        return reg(REGISTRY_PATH, _HOSTS_DOMAINS_NAME, domains_json)
    except Exception as e:
        _log(f"Ошибка записи активных доменов: {e}", "❌ ERROR")
        return False

def add_active_hosts_domain(domain: str) -> bool:
    """Добавляет домен в список активных"""
    domains = get_active_hosts_domains()
    domains.add(domain)
    return set_active_hosts_domains(domains)

def remove_active_hosts_domain(domain: str) -> bool:
    """Удаляет домен из списка активных"""
    domains = get_active_hosts_domains()
    domains.discard(domain)
    return set_active_hosts_domains(domains)

def clear_active_hosts_domains() -> bool:
    """Очищает список активных доменов"""
    return set_active_hosts_domains(set())

# ───────────── Автообновления при старте ─────────────
_AUTO_UPDATE_NAME = "AutoUpdateEnabled"  # REG_DWORD (1/0)

def get_auto_update_enabled() -> bool:
    """True – проверять обновления при старте, False – не проверять."""
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _AUTO_UPDATE_NAME)
    return bool(val) if val is not None else True  # По умолчанию включено

def set_auto_update_enabled(enabled: bool) -> bool:
    """Включает/выключает автоматическую проверку обновлений при старте."""
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _AUTO_UPDATE_NAME, 1 if enabled else 0)

# ───────────── Новогодняя гирлянда ─────────────
_GARLAND_NAME = "GarlandEnabled"  # REG_DWORD (1/0)

def get_garland_enabled() -> bool:
    """True – показывать новогоднюю гирлянду, False – не показывать."""
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _GARLAND_NAME)
    return bool(val) if val is not None else False  # По умолчанию выключено

def set_garland_enabled(enabled: bool) -> bool:
    """Включает/выключает новогоднюю гирлянду."""
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _GARLAND_NAME, 1 if enabled else 0)


# ───────────── Снежинки ─────────────
_SNOWFLAKES_NAME = "SnowflakesEnabled"  # REG_DWORD (1/0)

def get_snowflakes_enabled() -> bool:
    """True – показывать снежинки, False – не показывать."""
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _SNOWFLAKES_NAME)
    return bool(val) if val is not None else False  # По умолчанию выключено

def set_snowflakes_enabled(enabled: bool) -> bool:
    """Включает/выключает снежинки."""
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _SNOWFLAKES_NAME, 1 if enabled else 0)


# ───────────── Уведомление о сворачивании в трей ─────────────
_TRAY_HINT_SHOWN_NAME = "TrayHintShown"  # REG_DWORD (1/0)

def get_tray_hint_shown() -> bool:
    """True – уведомление о трее уже показывалось, False – ещё не показывалось."""
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _TRAY_HINT_SHOWN_NAME)
    return bool(val) if val is not None else False  # По умолчанию не показывалось

def set_tray_hint_shown(shown: bool = True) -> bool:
    """Отмечает что уведомление о трее было показано."""
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _TRAY_HINT_SHOWN_NAME, 1 if shown else 0)


# ───────────── Прозрачность окна ─────────────
_WINDOW_OPACITY_NAME = "WindowOpacity"  # REG_DWORD (0-100)


def _is_win11_plus() -> bool:
    try:
        return sys.platform == "win32" and sys.getwindowsversion().build >= 22000
    except Exception:
        return False

def get_window_opacity() -> int:
    """Возвращает прозрачность окна (0-100%).

    По умолчанию:
    - Win11+: 0 (минимальная тонировка Mica)
    - Win10 и ниже: 100 (полностью непрозрачный fallback)
    """
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _WINDOW_OPACITY_NAME)
    if val is None:
        return 0 if _is_win11_plus() else 100
    try:
        # Ограничиваем значение диапазоном 0-100
        return max(0, min(100, int(val)))
    except (TypeError, ValueError):
        return 0 if _is_win11_plus() else 100

def set_window_opacity(opacity: int) -> bool:
    """Устанавливает прозрачность окна (0-100%)."""
    from config import REGISTRY_PATH
    # Ограничиваем значение диапазоном 0-100
    opacity = max(0, min(100, int(opacity)))
    return reg(REGISTRY_PATH, _WINDOW_OPACITY_NAME, opacity)


# ───────────── Акцентный цвет (qfluentwidgets) ─────────────
_ACCENT_COLOR_NAME = "AccentColor"  # REG_SZ (hex, e.g. "#0078d4")

def get_accent_color() -> str | None:
    """Возвращает сохранённый акцентный цвет (hex) или None если не задан."""
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _ACCENT_COLOR_NAME)

def set_accent_color(hex_color: str) -> bool:
    """Сохраняет акцентный цвет (hex string, e.g. '#0078d4')."""
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _ACCENT_COLOR_NAME, str(hex_color))


# ───────────── Системный акцент Windows ─────────────

def get_windows_system_accent() -> str | None:
    """Read Windows system accent color from registry (ABGR format in AccentColorMenu)."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Accent",
            0, winreg.KEY_READ) as k:
            value, _ = winreg.QueryValueEx(k, "AccentColorMenu")
            # AccentColorMenu is DWORD in ABGR order: R=bits7-0, G=bits15-8, B=bits23-16
            r = value & 0xFF
            g = (value >> 8) & 0xFF
            b = (value >> 16) & 0xFF
            return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return None


# ───────────── Follow Windows Accent ─────────────
_FOLLOW_WINDOWS_ACCENT_NAME = "FollowWindowsAccent"

def get_follow_windows_accent() -> bool:
    from config import REGISTRY_PATH
    return bool(reg(REGISTRY_PATH, _FOLLOW_WINDOWS_ACCENT_NAME) or 0)

def set_follow_windows_accent(value: bool) -> bool:
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _FOLLOW_WINDOWS_ACCENT_NAME, int(value))


# ───────────── Tinted Background ─────────────
_TINTED_BG_NAME = "TintedBackground"

def get_tinted_background() -> bool:
    from config import REGISTRY_PATH
    return bool(reg(REGISTRY_PATH, _TINTED_BG_NAME) or 0)

def set_tinted_background(value: bool) -> bool:
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _TINTED_BG_NAME, int(value))


_TINTED_BG_INTENSITY_NAME = "TintedBackgroundIntensity"
_TINTED_BG_INTENSITY_DEFAULT = 15  # 0-30

def get_tinted_background_intensity() -> int:
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _TINTED_BG_INTENSITY_NAME)
    if val is None:
        return _TINTED_BG_INTENSITY_DEFAULT
    return max(0, min(30, int(val)))

def set_tinted_background_intensity(value: int) -> bool:
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _TINTED_BG_INTENSITY_NAME, max(0, min(30, int(value))))


# ───────────── Режим отображения (тёмный/светлый/авто) ─────────────
_DISPLAY_MODE_NAME = "DisplayMode"  # REG_SZ: "dark" | "light" | "system"


def _coerce_display_mode(mode: str | None) -> str:
    """Normalizes mode and enforces dark mode for AMOLED/RKN presets."""
    normalized = str(mode or "").strip().lower()
    if normalized not in ("dark", "light", "system"):
        normalized = "dark"

    # AMOLED and RKN presets are designed for dark mode only.
    try:
        from config import REGISTRY_PATH
        preset = reg(REGISTRY_PATH, "BackgroundPreset")
        preset_name = str(preset or "").strip().lower()
        if preset_name in ("amoled", "rkn_chan"):
            return "dark"
    except Exception:
        pass

    return normalized

def get_display_mode() -> str:
    """Возвращает режим отображения: 'dark', 'light' или 'system'. По умолчанию 'dark'."""
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _DISPLAY_MODE_NAME)
    coerced = _coerce_display_mode(val)

    # Self-heal incompatible/legacy values so UI and startup stay consistent.
    if val != coerced:
        try:
            reg(REGISTRY_PATH, _DISPLAY_MODE_NAME, coerced)
        except Exception:
            pass

    return coerced

def set_display_mode(mode: str) -> bool:
    """Сохраняет режим отображения ('dark', 'light' или 'system')."""
    from config import REGISTRY_PATH
    mode = _coerce_display_mode(mode)
    return reg(REGISTRY_PATH, _DISPLAY_MODE_NAME, mode)


# ───────────── Язык интерфейса ─────────────
_UI_LANGUAGE_NAME = "UILanguage"  # REG_SZ: "ru" | "en"


def get_ui_language() -> str:
    """Возвращает язык интерфейса ('ru' или 'en'). По умолчанию 'ru'."""
    from config import REGISTRY_PATH

    val = reg(REGISTRY_PATH, _UI_LANGUAGE_NAME)
    if val in ("ru", "en"):
        return val
    return "ru"


def set_ui_language(language: str) -> bool:
    """Сохраняет язык интерфейса ('ru' или 'en')."""
    from config import REGISTRY_PATH

    value = (language or "ru").strip().lower()
    if value not in ("ru", "en"):
        value = "ru"
    return reg(REGISTRY_PATH, _UI_LANGUAGE_NAME, value)


# ───────────── Mica эффект ─────────────
_MICA_ENABLED_NAME = "MicaEnabled"  # REG_DWORD (0 | 1)

def get_mica_enabled() -> bool:
    """Включён ли Mica-эффект (Win11+). По умолчанию True."""
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _MICA_ENABLED_NAME)
    return True if val is None else bool(val)

def set_mica_enabled(value: bool) -> bool:
    """Сохраняет флаг Mica-эффекта (Win11+)."""
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _MICA_ENABLED_NAME, int(value))


# ───────────── Фоновый пресет ─────────────
_BACKGROUND_PRESET_NAME = "BackgroundPreset"  # REG_SZ: "standard" | "amoled" | "rkn_chan"
_RKN_BACKGROUND_NAME = "RknBackground"        # REG_SZ: relative path in ./themes

def get_background_preset() -> str:
    """Возвращает фоновый пресет: 'standard', 'amoled' или 'rkn_chan'. По умолчанию 'standard'."""
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _BACKGROUND_PRESET_NAME)
    if val in ("standard", "amoled", "rkn_chan"):
        return val
    return "standard"

def set_background_preset(preset: str) -> bool:
    """Сохраняет фоновый пресет ('standard', 'amoled' или 'rkn_chan')."""
    from config import REGISTRY_PATH
    if preset not in ("standard", "amoled", "rkn_chan"):
        preset = "standard"
    return reg(REGISTRY_PATH, _BACKGROUND_PRESET_NAME, preset)


def get_rkn_background() -> str | None:
    """Возвращает выбранный фон РКН Тян (относительный путь внутри ./themes) или None."""
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _RKN_BACKGROUND_NAME)
    if isinstance(val, str):
        cleaned = val.strip().replace("\\", "/")
        return cleaned or None
    return None


def set_rkn_background(value: str | None) -> bool:
    """Сохраняет выбранный фон РКН Тян (относительный путь внутри ./themes)."""
    from config import REGISTRY_PATH
    if value is None:
        return reg(REGISTRY_PATH, _RKN_BACKGROUND_NAME, None)
    cleaned = str(value).strip().replace("\\", "/")
    if not cleaned:
        return reg(REGISTRY_PATH, _RKN_BACKGROUND_NAME, None)
    return reg(REGISTRY_PATH, _RKN_BACKGROUND_NAME, cleaned)


# ───────────── Анимации интерфейса ─────────────
_ANIMATIONS_ENABLED_NAME = "AnimationsEnabled"  # REG_DWORD (0 | 1)

def get_animations_enabled() -> bool:
    """Включены ли анимации интерфейса. По умолчанию False."""
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _ANIMATIONS_ENABLED_NAME)
    return False if val is None else bool(val)

def set_animations_enabled(value: bool) -> bool:
    """Сохраняет флаг анимаций интерфейса."""
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _ANIMATIONS_ENABLED_NAME, int(value))


# ───────────── Плавная прокрутка ─────────────
_SMOOTH_SCROLL_ENABLED_NAME = "SmoothScrollEnabled"  # REG_DWORD (0 | 1)
_EDITOR_SMOOTH_SCROLL_ENABLED_NAME = "EditorSmoothScrollEnabled"  # REG_DWORD (0 | 1)

def get_smooth_scroll_enabled() -> bool:
    """Включена ли плавная прокрутка страниц. По умолчанию True."""
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _SMOOTH_SCROLL_ENABLED_NAME)
    return True if val is None else bool(val)

def set_smooth_scroll_enabled(value: bool) -> bool:
    """Сохраняет флаг плавной прокрутки."""
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _SMOOTH_SCROLL_ENABLED_NAME, int(value))


def get_editor_smooth_scroll_enabled() -> bool:
    """Включена ли плавная прокрутка внутри редакторов. По умолчанию False."""
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _EDITOR_SMOOTH_SCROLL_ENABLED_NAME)
    return False if val is None else bool(val)


def set_editor_smooth_scroll_enabled(value: bool) -> bool:
    """Сохраняет флаг плавной прокрутки внутри редакторов."""
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _EDITOR_SMOOTH_SCROLL_ENABLED_NAME, int(value))


# ───────────── Telegram WebSocket Proxy ─────────────
_TG_PROXY_ENABLED_NAME = "TgProxyEnabled"          # REG_DWORD (0/1)
_TG_PROXY_AUTOSTART_NAME = "TgProxyAutoStart"      # REG_DWORD (0/1)
_TG_PROXY_PORT_NAME = "TgProxyPort"                # REG_DWORD
_TG_PROXY_MODE_NAME = "TgProxyMode"                # REG_SZ ("socks5"|"transparent"|"both")

def get_tg_proxy_enabled() -> bool:
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _TG_PROXY_ENABLED_NAME)
    return bool(val) if val is not None else False

def set_tg_proxy_enabled(enabled: bool) -> bool:
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _TG_PROXY_ENABLED_NAME, 1 if enabled else 0)

def get_tg_proxy_autostart() -> bool:
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _TG_PROXY_AUTOSTART_NAME)
    return bool(val) if val is not None else True  # Default: auto-start ON

def set_tg_proxy_autostart(autostart: bool) -> bool:
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _TG_PROXY_AUTOSTART_NAME, 1 if autostart else 0)

def get_tg_proxy_port() -> int:
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _TG_PROXY_PORT_NAME)
    return int(val) if val is not None else 1353

def set_tg_proxy_port(port: int) -> bool:
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _TG_PROXY_PORT_NAME, int(port))

def get_tg_proxy_mode() -> str:
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _TG_PROXY_MODE_NAME)
    return str(val) if val else "socks5"

def set_tg_proxy_mode(mode: str) -> bool:
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _TG_PROXY_MODE_NAME, str(mode))


# ── Telegram Proxy Host (bind address) ──
_TG_PROXY_HOST_NAME = "TgProxyHost"               # REG_SZ

def get_tg_proxy_host() -> str:
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _TG_PROXY_HOST_NAME)
    return str(val) if val else "127.0.0.1"

def set_tg_proxy_host(host: str) -> bool:
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _TG_PROXY_HOST_NAME, str(host))


# ── Telegram Proxy Upstream (external SOCKS5 fallback) ──
_TG_PROXY_UPSTREAM_ENABLED_NAME = "TgProxyUpstreamEnabled"    # REG_DWORD (0/1)
_TG_PROXY_UPSTREAM_HOST_NAME = "TgProxyUpstreamHost"          # REG_SZ
_TG_PROXY_UPSTREAM_PORT_NAME = "TgProxyUpstreamPort"          # REG_DWORD
_TG_PROXY_UPSTREAM_MODE_NAME = "TgProxyUpstreamMode"          # REG_SZ

def get_tg_proxy_upstream_enabled() -> bool:
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _TG_PROXY_UPSTREAM_ENABLED_NAME)
    return bool(val) if val is not None else False

def set_tg_proxy_upstream_enabled(enabled: bool) -> bool:
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _TG_PROXY_UPSTREAM_ENABLED_NAME, 1 if enabled else 0)

def get_tg_proxy_upstream_host() -> str:
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _TG_PROXY_UPSTREAM_HOST_NAME)
    return str(val) if val else ""

def set_tg_proxy_upstream_host(host: str) -> bool:
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _TG_PROXY_UPSTREAM_HOST_NAME, str(host))

def get_tg_proxy_upstream_port() -> int:
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _TG_PROXY_UPSTREAM_PORT_NAME)
    return int(val) if val is not None else 0

def set_tg_proxy_upstream_port(port: int) -> bool:
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _TG_PROXY_UPSTREAM_PORT_NAME, int(port))

def get_tg_proxy_upstream_mode() -> str:
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _TG_PROXY_UPSTREAM_MODE_NAME)
    return str(val) if val else "always"

def set_tg_proxy_upstream_mode(mode: str) -> bool:
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _TG_PROXY_UPSTREAM_MODE_NAME, str(mode))

_TG_PROXY_UPSTREAM_USER_NAME = "TgProxyUpstreamUser"      # REG_SZ
_TG_PROXY_UPSTREAM_PASS_NAME = "TgProxyUpstreamPass"      # REG_SZ

def get_tg_proxy_upstream_user() -> str:
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _TG_PROXY_UPSTREAM_USER_NAME)
    return str(val) if val else ""

def set_tg_proxy_upstream_user(user: str) -> bool:
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _TG_PROXY_UPSTREAM_USER_NAME, str(user))

def get_tg_proxy_upstream_pass() -> str:
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _TG_PROXY_UPSTREAM_PASS_NAME)
    return str(val) if val else ""

def set_tg_proxy_upstream_pass(password: str) -> bool:
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _TG_PROXY_UPSTREAM_PASS_NAME, str(password))


# ───────────── Registry Subkey Helpers ─────────────

def reg_enumerate_values(subkey: str, *, root=HKCU) -> dict:
    """
    Перечисляет все значения в ключе реестра.

    Returns:
        {name: value, ...} или {} если ключ не существует
    """
    result = {}
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ) as k:
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(k, i)
                    result[name] = value
                    i += 1
                except OSError:
                    break  # Больше значений нет
    except FileNotFoundError:
        pass  # Ключ не существует
    except Exception as e:
        _log(f"reg_enumerate_values error [{subkey}]: {e}", "DEBUG")
    return result


def reg_delete_value(subkey: str, name: str, *, root=HKCU) -> bool:
    """
    Удаляет одно значение из ключа реестра.

    Args:
        subkey: путь к ключу
        name: имя значения для удаления

    Returns:
        True если успешно, False при ошибке
    """
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_ALL_ACCESS) as k:
            winreg.DeleteValue(k, name)
        return True
    except FileNotFoundError:
        return True  # Значение не существует - считаем успехом
    except Exception as e:
        _log(f"reg_delete_value error [{subkey}\\{name}]: {e}", "DEBUG")
        return False


def reg_delete_all_values(subkey: str, *, root=HKCU) -> bool:
    """
    Удаляет все значения в ключе реестра (сам ключ остаётся).

    Returns:
        True если успешно, False при ошибке
    """
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_ALL_ACCESS) as k:
            # Сначала получаем список имён
            names = []
            i = 0
            while True:
                try:
                    name, _, _ = winreg.EnumValue(k, i)
                    names.append(name)
                    i += 1
                except OSError:
                    break
            # Удаляем каждое значение
            for name in names:
                try:
                    winreg.DeleteValue(k, name)
                except Exception:
                    pass
        return True
    except FileNotFoundError:
        return True  # Ключ не существует - считаем успехом
    except Exception as e:
        _log(f"reg_delete_all_values error [{subkey}]: {e}", "ERROR")
        return False


def reg_set_values(subkey: str, values: dict, *, root=HKCU) -> bool:
    """
    Записывает несколько значений в ключ реестра.

    Args:
        subkey: путь к ключу
        values: {name: value, ...}

    Returns:
        True если все записаны успешно
    """
    try:
        k = winreg.CreateKeyEx(root, subkey, 0, winreg.KEY_SET_VALUE)
        for name, value in values.items():
            reg_type = _detect_reg_type(value)
            winreg.SetValueEx(k, name, 0, reg_type, value)
        winreg.CloseKey(k)
        return True
    except Exception as e:
        _log(f"reg_set_values error [{subkey}]: {e}", "ERROR")
        return False
