# reg.py ─ универсальный helper для работы с реестром
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


# ------------------------------------------------------------------
# Шорткаты вашей программы - ОТДЕЛЬНЫЕ КЛЮЧИ ДЛЯ РАЗНЫХ РЕЖИМОВ
# ------------------------------------------------------------------

# ───────────── BAT режим (Запрет 1) ─────────────
def get_last_bat_strategy():
    """Получает последнюю BAT-стратегию из реестра"""
    from config import DEFAULT_STRAT, REGISTRY_PATH
    return reg(REGISTRY_PATH, "LastBatStrategy") or DEFAULT_STRAT


def set_last_bat_strategy(name: str) -> bool:
    """Сохраняет последнюю BAT-стратегию в реестр"""
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, "LastBatStrategy", name)


# ───────────── Direct режим (Запрет 2) ─────────────
# Для Direct режима selections сохраняются отдельно через get/set_direct_mode_selections
# Отдельный ключ LastDirectStrategy не нужен, т.к. selections и есть состояние


# ───────────── LEGACY - для обратной совместимости ─────────────
def get_last_strategy():
    """УСТАРЕВШАЯ функция - используйте get_last_bat_strategy()"""
    return get_last_bat_strategy()


def set_last_strategy(name: str) -> bool:
    """УСТАРЕВШАЯ функция - используйте set_last_bat_strategy()"""
    return set_last_bat_strategy(name)

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


# ───────────── Эффект размытия (Acrylic/Mica) ─────────────
_BLUR_EFFECT_NAME = "BlurEffectEnabled"  # REG_DWORD (1/0)

def get_blur_effect_enabled() -> bool:
    """True – включён эффект размытия окна, False – выключен."""
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _BLUR_EFFECT_NAME)
    return bool(val) if val is not None else False  # По умолчанию выключено

def set_blur_effect_enabled(enabled: bool) -> bool:
    """Включает/выключает эффект размытия окна."""
    from config import REGISTRY_PATH
    return reg(REGISTRY_PATH, _BLUR_EFFECT_NAME, 1 if enabled else 0)


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

def get_window_opacity() -> int:
    """Возвращает прозрачность окна (0-100%). По умолчанию 100 (непрозрачное)."""
    from config import REGISTRY_PATH
    val = reg(REGISTRY_PATH, _WINDOW_OPACITY_NAME)
    if val is None:
        return 95  # По умолчанию 95% прозрачности
    # Ограничиваем значение диапазоном 0-100
    return max(0, min(100, int(val)))

def set_window_opacity(opacity: int) -> bool:
    """Устанавливает прозрачность окна (0-100%)."""
    from config import REGISTRY_PATH
    # Ограничиваем значение диапазоном 0-100
    opacity = max(0, min(100, int(opacity)))
    return reg(REGISTRY_PATH, _WINDOW_OPACITY_NAME, opacity)


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