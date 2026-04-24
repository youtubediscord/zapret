import os
import re
from typing import List, Tuple

from lists.core.layered_runtime import LayeredListPaths, ensure_user_layer, rebuild_layered_list
from lists.core.files import write_text_file
from lists.core.paths import get_list_base_path, get_list_final_path, get_list_user_path

from log.log import log


NETROGAT_PATH = get_list_final_path("netrogat")
NETROGAT_BASE_PATH = get_list_base_path("netrogat")
NETROGAT_USER_PATH = get_list_user_path("netrogat")
NETROGAT_LIST_PATHS = LayeredListPaths(
    base_path=NETROGAT_BASE_PATH,
    user_path=NETROGAT_USER_PATH,
    final_path=NETROGAT_PATH,
)


# Базовые домены исключений.
# Хранятся в lists/base/netrogat.txt (системная база) и автоматически
# объединяются с пользовательскими записями из lists/user/netrogat.txt.
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
# Системная база доменов-исключений.
# Этот файл поставляется установщиком и не редактируется из интерфейса.
#
# Итоговый lists/netrogat.txt формируется автоматически как:
#   lists/base/netrogat.txt + lists/user/netrogat.txt
#
# Формат: один домен на строку, без протокола и пути.
# Строки, начинающиеся с #, игнорируются.
"""


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


def get_netrogat_base_entries() -> list[str]:
    base_entries = _read_effective_domain_entries(NETROGAT_BASE_PATH)
    if base_entries:
        return base_entries
    log("Не найдена системная база lists/base/netrogat.txt", "ERROR")
    return []


def get_netrogat_base_set() -> set[str]:
    return set(get_netrogat_base_entries())


def get_user_netrogat_entries() -> list[str]:
    return _read_effective_domain_entries(NETROGAT_USER_PATH)


def ensure_netrogat_user_file() -> bool:
    """Публичный helper: гарантирует наличие netrogat.user.txt."""
    return ensure_user_layer(NETROGAT_LIST_PATHS, error_message="Ошибка подготовки netrogat.user.txt", log_func=log)


def sync_netrogat_after_user_change() -> bool:
    """Быстрый sync после правки netrogat.user.txt."""
    try:
        return rebuild_layered_list(
            NETROGAT_LIST_PATHS,
            get_base_entries=get_netrogat_base_entries,
            read_entries=_read_effective_domain_entries,
            log_func=log,
            user_error_message="Ошибка подготовки netrogat.user.txt",
            final_error_label="Ошибка генерации netrogat.txt",
        )
    except Exception as exc:
        log(f"Ошибка sync_netrogat_after_user_change: {exc}", "ERROR")
        return False


def ensure_netrogat_exists() -> bool:
    """Гарантирует валидный набор netrogat base/user/final файлов."""
    try:
        return rebuild_layered_list(
            NETROGAT_LIST_PATHS,
            get_base_entries=get_netrogat_base_entries,
            read_entries=_read_effective_domain_entries,
            log_func=log,
            user_error_message="Ошибка подготовки netrogat.user.txt",
            final_error_label="Ошибка генерации netrogat.txt",
            require_non_empty=True,
        )
    except Exception as exc:
        log(f"Ошибка создания netrogat файлов: {exc}", "ERROR")
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
        write_text_file(NETROGAT_USER_PATH, content)

        if not sync_netrogat_after_user_change():
            return False

        user_domains_count = len([ln for ln in lines if not ln.startswith("#")])
        log(f"Сохранено {user_domains_count} доменов в netrogat.user.txt", "INFO")
        return True
    except Exception as e:
        log(f"Ошибка сохранения netrogat.user.txt: {e}", "ERROR")
        return False


def ensure_netrogat_base_defaults() -> int:
    """Возвращает число доменов системной базы для совместимости старых use-site'ов."""
    return len(get_netrogat_base_entries())


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
