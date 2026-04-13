import os
import re
from typing import List, Tuple

from config.config import LISTS_FOLDER, NETROGAT_PATH

from log.log import log



NETROGAT_BASE_PATH = os.path.join(LISTS_FOLDER, "netrogat.base.txt")
NETROGAT_USER_PATH = os.path.join(LISTS_FOLDER, "netrogat.user.txt")


# Базовые домены исключений.
# Хранятся в netrogat.base.txt (системная база) и автоматически
# объединяются с пользовательскими записями из netrogat.user.txt.
DEFAULT_NETROGAT_DOMAINS = [
    # Государственные
    "gosuslugi.ru",
    "government.ru",
    "mos.ru",
    "nalog.ru",
    # VK / Mail.ru
    "vk.com",
    "vk.ru",
    "vkvideo.ru",
    "vk-portal.net",
    "userapi.com",
    "mail.ru",
    "max.ru",
    "ok.ru",
    "okcdn.ru",
    "mycdn.me",
    "api.mycdn.me",
    "tns-counter.ru",
    "vc.ru",
    "osnova.io",
    # Яндекс
    "ya.ru",
    "yandex.net",
    "yandex.ru",
    "yandex.by",
    "yandex.kz",
    "dzen.ru",
    "rutube.ru",
    # Банки
    "sberbank.ru",
    "sberbank.com",
    "sbrf.ru",
    "sbercloud.ru",
    "vtb.ru",
    "tbank.ru",
    "tinkoff.ru",
    "cdn-tinkoff.ru",
    "t-j.ru",
    "t-static.ru",
    "tinkoffjournal.ru",
    "tjournal.tech",
    "alfabank.ru",
    # Операторы связи
    "megafon.ru",
    "mts.ru",
    # Антивирусы и безопасность
    "kaspersky.com",
    "kaspersky.ru",
    "drweb.ru",
    "drweb.com",
    # Маркетплейсы
    "ozon.ru",
    "ozone.ru",
    "ozonusercontent.com",
    "wildberries.ru",
    "wb.ru",
    "wbbasket.ru",
    # Сервисы
    "deepl.com",
    "ixbt.com",
    "gitflic.ru",
    "searchengines.guru",
    "habr.com",
    "apteka.ru",
    "comss.ru",
    "teletype.in",
    "avtoradio.ru",
    "lifehacker.ru",
    "zapretdpi.ru",
    "beget.com",
    "boosty.to",
    "rzd.ru",
    "tvil.ru",
    "tutu.ru",
    "dp.ru",
    "rustore.ru",
    # СМИ
    "smi2.ru",
    "smi2.net",
    "smi24.net",
    "24smi.net",
    # Техно
    "yadro.ru",
    "createjs.com",
    "cdn.ampproject.org",
    "st.top100.ru",
    "use.fontawesome.com",
    # Punycode домены
    "xn----7sba3awldles.xn--p1ai",
    "xn--80aamekfkttt8n.xn--p1ai",
    "xn--80aneaalhfjfdkj7ah7o.xn--p1ai",
    # Растения (?)
    "rootsplants.co.uk",
    "podviliepitomnik.ru",
    "cvetovod.by",
    "veresk.by",
    # Microsoft
    "microsoft.com",
    "live.com",
    "office.com",
    # Локальные адреса
    "localhost",
    "127.0.0.1",
    # Образование
    "netschool.edu22.info",
    "edu22.info",
    # Конструкторы сайтов
    "tilda.ws",
    "tilda.cc",
    "tildacdn.com",
    # AI сервисы
    "claude.ai",
    "anthropic.com",
    "claude.com",
    "lmarena.ai",
    "ppl-ai-file-upload.s3.amazonaws.com",
]


_NETROGAT_BASE_HEADER = """\
# Системная база доменов-исключений (автоматически управляется приложением).
# Этот файл НЕ редактируется из интерфейса напрямую.
#
# Итоговый lists/netrogat.txt формируется автоматически как:
#   netrogat.base.txt + netrogat.user.txt
#
# Формат: один домен на строку, без протокола и пути.
# Строки, начинающиеся с #, игнорируются.
"""


def _normalize_newlines(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if normalized and not normalized.endswith("\n"):
        normalized += "\n"
    return normalized


def _write_text_file(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(_normalize_newlines(content))


def _read_text_file_safe(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def _normalize_domain(text: str) -> str | None:
    """Приводит строку к домену, убирает схемы/путь/порт, нижний регистр."""
    s = text.strip()
    if not s or s.startswith("#"):
        return None

    if s.startswith("."):
        s = s[1:]
    if "://" in s:
        s = s.split("://", 1)[1]
    s = s.split("/", 1)[0]
    s = s.split(":", 1)[0]
    if s.startswith("www."):
        s = s[4:]
    if s.startswith("."):
        s = s[1:]

    s = s.strip().lower()
    if not s:
        return None

    # Одиночные TLD (com, ru, org) тоже валидны
    if re.match(r"^[a-z]{2,10}$", s):
        return s

    if "." in s and re.match(r"^[a-z0-9][a-z0-9\-\.\*]*[a-z0-9]$", s):
        return s

    return None


def _dedup_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _read_effective_domain_entries(path: str) -> list[str]:
    if not os.path.exists(path):
        return []

    out: list[str] = []
    seen: set[str] = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                norm = _normalize_domain(raw)
                if not norm or norm in seen:
                    continue
                seen.add(norm)
                out.append(norm)
    except Exception:
        return []

    return out


def _sanitize_user_lines(lines: List[str]) -> list[str]:
    out: list[str] = []
    seen_domains: set[str] = set()
    for raw in lines:
        line = str(raw or "").strip()
        if not line:
            continue
        if line.startswith("#"):
            out.append(line)
            continue
        norm = _normalize_domain(line)
        if not norm or norm in seen_domains:
            continue
        seen_domains.add(norm)
        out.append(norm)
    return out


def _count_effective_entries(path: str) -> int:
    return len(_read_effective_domain_entries(path))


def _get_default_domains() -> list[str]:
    defaults: list[str] = []
    seen: set[str] = set()
    for item in DEFAULT_NETROGAT_DOMAINS:
        norm = _normalize_domain(item)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        defaults.append(norm)
    return defaults


def _build_base_content() -> str:
    defaults = _get_default_domains()
    lines: list[str] = [ln.rstrip() for ln in _NETROGAT_BASE_HEADER.split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    lines.extend(defaults)
    return "\n".join(lines) + "\n"


def _ensure_netrogat_base_updated() -> tuple[bool, int]:
    """Гарантирует корректный системный netrogat.base.txt.

    Возвращает (ok, added_missing_defaults_count).
    """
    try:
        os.makedirs(os.path.dirname(NETROGAT_BASE_PATH), exist_ok=True)

        existing_entries = _read_effective_domain_entries(NETROGAT_BASE_PATH)
        existing_set = set(existing_entries)
        defaults = _get_default_domains()
        added_missing = sum(1 for d in defaults if d not in existing_set)

        expected_content = _build_base_content()
        current_content = _read_text_file_safe(NETROGAT_BASE_PATH)

        if _normalize_newlines(current_content or "") != _normalize_newlines(expected_content):
            _write_text_file(NETROGAT_BASE_PATH, expected_content)
            if current_content is None:
                log(
                    f"Создан netrogat.base.txt с {len(defaults)} доменами",
                    "INFO",
                )
            else:
                log(
                    f"Обновлен netrogat.base.txt (доменов: {len(defaults)})",
                    "DEBUG",
                )

        return True, added_missing
    except Exception as e:
        log(f"Ошибка подготовки netrogat.base.txt: {e}", "ERROR")
        return False, 0


def _ensure_netrogat_user_file_exists() -> bool:
    try:
        os.makedirs(os.path.dirname(NETROGAT_USER_PATH), exist_ok=True)

        if os.path.exists(NETROGAT_USER_PATH):
            return True

        _write_text_file(NETROGAT_USER_PATH, "")
        return True
    except Exception as e:
        log(f"Ошибка подготовки netrogat.user.txt: {e}", "ERROR")
        return False


def _write_combined_netrogat_file() -> bool:
    """Генерирует итоговый netrogat.txt = base + user (dedup, base-first)."""
    try:
        base_entries = _read_effective_domain_entries(NETROGAT_BASE_PATH)
        user_entries = _read_effective_domain_entries(NETROGAT_USER_PATH)

        base_set = set(base_entries)
        combined = list(base_entries)
        for domain in user_entries:
            if domain not in base_set:
                combined.append(domain)

        combined = _dedup_preserve_order(combined)
        content = "\n".join(combined) + ("\n" if combined else "")
        _write_text_file(NETROGAT_PATH, content)
        return True
    except Exception as e:
        log(f"Ошибка генерации netrogat.txt: {e}", "ERROR")
        return False


def get_netrogat_base_entries() -> list[str]:
    return _read_effective_domain_entries(NETROGAT_BASE_PATH)


def get_netrogat_base_set() -> set[str]:
    return set(get_netrogat_base_entries())


def get_user_netrogat_entries() -> list[str]:
    return _read_effective_domain_entries(NETROGAT_USER_PATH)


def ensure_netrogat_user_file() -> bool:
    """Публичный helper: гарантирует наличие netrogat.user.txt."""
    ok, _ = _ensure_netrogat_base_updated()
    if not ok:
        return False
    return _ensure_netrogat_user_file_exists()


def sync_netrogat_after_user_change() -> bool:
    """Быстрый sync после правки netrogat.user.txt."""
    try:
        ok, _ = _ensure_netrogat_base_updated()
        if not ok:
            return False

        if not _ensure_netrogat_user_file_exists():
            return False

        return _write_combined_netrogat_file()
    except Exception as e:
        log(f"Ошибка sync_netrogat_after_user_change: {e}", "ERROR")
        return False


def ensure_netrogat_exists() -> bool:
    """Гарантирует валидный набор netrogat.base/user/final файлов."""
    try:
        ok, _ = _ensure_netrogat_base_updated()
        if not ok:
            return False

        if not _ensure_netrogat_user_file_exists():
            return False

        if not _write_combined_netrogat_file():
            return False

        return _count_effective_entries(NETROGAT_PATH) > 0
    except Exception as e:
        log(f"Ошибка создания netrogat файлов: {e}", "ERROR")
        return False


def load_netrogat() -> List[str]:
    """Загружает netrogat.user.txt (комментарии + нормализованные домены)."""
    ensure_netrogat_exists()

    lines: list[str] = []
    seen_domains: set[str] = set()
    try:
        with open(NETROGAT_USER_PATH, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                if line.startswith("#"):
                    lines.append(line)
                    continue
                norm = _normalize_domain(line)
                if norm and norm not in seen_domains:
                    seen_domains.add(norm)
                    lines.append(norm)
    except Exception as e:
        log(f"Ошибка чтения netrogat.user.txt: {e}", "ERROR")

    return lines


def save_netrogat(domains: List[str]) -> bool:
    """Сохраняет пользовательский список в netrogat.user.txt и синхронизирует итог."""
    try:
        if not ensure_netrogat_user_file():
            return False

        lines = _sanitize_user_lines(domains)
        content = "\n".join(lines) + ("\n" if lines else "")
        _write_text_file(NETROGAT_USER_PATH, content)

        if not sync_netrogat_after_user_change():
            return False

        user_domains_count = len([ln for ln in lines if not ln.startswith("#")])
        log(f"Сохранено {user_domains_count} доменов в netrogat.user.txt", "INFO")
        return True
    except Exception as e:
        log(f"Ошибка сохранения netrogat.user.txt: {e}", "ERROR")
        return False


def ensure_netrogat_base_defaults() -> int:
    """Восстанавливает системную базу netrogat.base.txt, возвращает число добавленных дефолтов."""
    ok, added_missing = _ensure_netrogat_base_updated()
    if not ok:
        return 0
    _write_combined_netrogat_file()
    return added_missing


def add_missing_defaults(current: List[str]) -> Tuple[List[str], int]:
    """Legacy helper: добавляет дефолтные домены к текущему списку."""
    current_set: set[str] = set()
    for item in current:
        norm = _normalize_domain(item)
        if norm:
            current_set.add(norm)

    added = 0
    for domain in _get_default_domains():
        if domain not in current_set:
            current_set.add(domain)
            added += 1

    return sorted(current_set), added
