"""
Загрузчик стратегий из TXT файлов (INI-подобный формат).

Стратегии загружаются из:
1. {INDEXJSON_FOLDER}/strategies/builtin/ - встроенные стратегии (обновляются с программой)
2. {INDEXJSON_FOLDER}/strategies/user/ - пользовательские стратегии (сохраняются при обновлении)

Каждая категория имеет свой TXT файл:
- tcp.txt - TCP стратегии (YouTube, Discord TCP, и т.д.)
- udp.txt - UDP стратегии (QUIC, игры)
- http80.txt - HTTP порт 80
- discord_voice.txt - Discord голос

Формат TXT файла:
    [strategy_id]
    name = Название стратегии
    author = Автор
    label = recommended|experimental|game|deprecated
    description = Описание
    blobs = blob1, blob2
    --arg1=value1
    --arg2=value2

    [another_strategy]
    ...
"""

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from log import log
from config import INDEXJSON_FOLDER
from strategy_menu.user_categories_store import get_user_categories_file_path

# Путь к папке со стратегиями - используем INDEXJSON_FOLDER из конфига
# Структура: {INDEXJSON_FOLDER}/strategies/builtin/ и {INDEXJSON_FOLDER}/strategies/user/
STRATEGIES_DIR = Path(INDEXJSON_FOLDER) / "strategies"

# Fallback на локальную папку (для разработки)
_LOCAL_STRATEGIES_DIR = Path(__file__).parent

# Fallback на соседнюю папку zapret (для разработки из IDE)
# /home/privacy/zapretgui -> /home/privacy/zapret
_DEV_ZAPRET_DIR = Path(__file__).parent.parent.parent / "zapret" / "json" / "strategies"


# In-memory cache for parsed files (key = absolute path, value = (mtime_ns, size, data)).
# Reduces repeated disk parsing during startup and page rebuilds.
_CACHE_MAX_ENTRIES = 128
_JSON_FILE_CACHE: Dict[str, tuple[int, int, Any]] = {}
_TXT_FILE_CACHE: Dict[str, tuple[int, int, Any]] = {}
_CATEGORIES_TXT_CACHE: Dict[str, tuple[int, int, Any]] = {}


_EXTERNAL_STRATEGY_BASENAME_MAP: Dict[str, Dict[str, str]] = {
    "basic": {
        "tcp": "tcp_zapret2_basic",
        "udp": "udp_zapret_basic",
        "http80": "http80_zapret2_basic",
        "discord_voice": "discord_voice_zapret2_basic",
    },
    "advanced": {
        "tcp": "tcp_zapret2_advanced",
        "tcp_fake": "tcp_fake_zapret2_advanced",
        "udp": "udp_zapret2_advanced",
        "http80": "http80_zapret2_advanced",
        "discord_voice": "discord_voice_zapret2_advanced",
    },
    "orchestra": {
        "tcp": "tcp_orchestra",
        "http80": "http80_orchestra",
    },
}


def _to_cache_key(filepath: Path) -> str:
    try:
        return str(filepath.resolve())
    except Exception:
        return str(filepath)


def _file_signature(filepath: Path) -> tuple[int, int]:
    st = filepath.stat()
    mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)))
    return mtime_ns, int(st.st_size)


def _get_cached_data(cache: Dict[str, tuple[int, int, Any]], filepath: Path) -> Optional[Any]:
    key = _to_cache_key(filepath)
    cached = cache.get(key)
    if not cached:
        return None

    try:
        current_sig = _file_signature(filepath)
    except Exception:
        return None

    if (cached[0], cached[1]) != current_sig:
        return None

    return deepcopy(cached[2])


def _set_cached_data(cache: Dict[str, tuple[int, int, Any]], filepath: Path, signature: tuple[int, int], data: Any) -> None:
    key = _to_cache_key(filepath)
    cache[key] = (signature[0], signature[1], deepcopy(data))
    if len(cache) > _CACHE_MAX_ENTRIES:
        cache.pop(next(iter(cache)), None)


def _invalidate_file_cache(filepath: Path) -> None:
    key = _to_cache_key(filepath)
    _JSON_FILE_CACHE.pop(key, None)
    _TXT_FILE_CACHE.pop(key, None)
    _CATEGORIES_TXT_CACHE.pop(key, None)


def _has_categories_file(directory: Path) -> bool:
    """Проверяет наличие файла категорий (TXT)."""
    return (directory / "categories.txt").exists()


def _has_any_strategy_files(directory: Path) -> bool:
    """Проверяет, что директория похожа на strategies/* (есть txt/json файлы)."""
    try:
        return any(directory.glob("*.txt")) or any(directory.glob("*.json"))
    except Exception:
        return False


def _get_builtin_dir() -> Path:
    """Возвращает путь к builtin директории (с fallback)"""
    global_builtin = STRATEGIES_DIR / "builtin"
    local_builtin = _LOCAL_STRATEGIES_DIR / "builtin"
    dev_builtin = _DEV_ZAPRET_DIR / "builtin"

    # 1. Если глобальная папка существует и содержит стратегии - используем её
    if global_builtin.exists() and _has_any_strategy_files(global_builtin):
        return global_builtin

    # 2. Проверяем соседнюю папку zapret (для разработки из IDE)
    if dev_builtin.exists() and _has_any_strategy_files(dev_builtin):
        return dev_builtin

    # 3. Проверяем локальную папку strategy_menu/strategies/builtin
    if local_builtin.exists() and _has_any_strategy_files(local_builtin):
        return local_builtin

    # Возвращаем глобальную по умолчанию
    return global_builtin


def _get_user_dir() -> Path:
    """Возвращает путь к user директории"""
    global_user = STRATEGIES_DIR / "user"
    local_user = _LOCAL_STRATEGIES_DIR / "user"
    dev_user = _DEV_ZAPRET_DIR / "user"
    
    # Определяем откуда загружается builtin
    builtin_dir = _get_builtin_dir()
    
    # Если builtin из dev папки - user тоже оттуда
    if builtin_dir == _DEV_ZAPRET_DIR / "builtin":
        return dev_user
    
    # Если builtin из локальной папки - user тоже оттуда
    if builtin_dir == _LOCAL_STRATEGIES_DIR / "builtin":
        return local_user
    
    # Иначе используем глобальную
    return global_user


# Маппинг label строк на константы
LABEL_MAP = {
    "recommended": "recommended",
    "game": "game", 
    "caution": "caution",
    "experimental": "experimental",
    "stable": "stable",
    None: None,
    "null": None,
}


def ensure_directories():
    """Создаёт необходимые директории если их нет"""
    _get_builtin_dir().mkdir(parents=True, exist_ok=True)
    _get_user_dir().mkdir(parents=True, exist_ok=True)


def load_json_file(filepath: Path) -> Optional[Dict]:
    """Загружает JSON файл"""
    try:
        if not filepath.exists():
            return None

        cached = _get_cached_data(_JSON_FILE_CACHE, filepath)
        if cached is not None:
            return cached

        signature = _file_signature(filepath)
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        _set_cached_data(_JSON_FILE_CACHE, filepath, signature, data)
        return deepcopy(data)
    except json.JSONDecodeError as e:
        log(f"Ошибка парсинга JSON {filepath}: {e}", "ERROR")
        return None
    except Exception as e:
        log(f"Ошибка чтения {filepath}: {e}", "ERROR")
        return None


def load_txt_file(filepath: Path) -> Optional[Dict]:
    """
    Загружает стратегии из TXT файла в INI-подобном формате.

    Формат:
        [strategy_id]
        name = Название стратегии
        author = Автор
        label = recommended|experimental|game|deprecated
        description = Описание
        blobs = blob1, blob2
        --arg1=value1
        --arg2=value2

        [another_strategy]
        ...

    Returns:
        Dict в формате {'strategies': [...]} или None при ошибке
    """
    try:
        if not filepath.exists():
            return None

        cached = _get_cached_data(_TXT_FILE_CACHE, filepath)
        if cached is not None:
            return cached

        signature = _file_signature(filepath)

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        strategies = []
        current_strategy = None
        current_args = []

        for line in content.splitlines():
            line = line.rstrip()

            # Пропускаем пустые строки
            if not line:
                continue

            # Пропускаем комментарии (строки начинающиеся с #)
            if line.startswith('#'):
                continue

            # Начало новой стратегии [id]
            if line.startswith('[') and line.endswith(']'):
                # Сохраняем предыдущую стратегию
                if current_strategy is not None:
                    current_strategy['args'] = '\n'.join(current_args)
                    strategies.append(current_strategy)

                # Начинаем новую
                strategy_id = line[1:-1].strip()
                current_strategy = {
                    'id': strategy_id,
                    'name': strategy_id,  # По умолчанию имя = id
                    'description': '',
                    'author': 'unknown',
                    'label': None,
                    'blobs': [],
                    'args': ''
                }
                current_args = []
                continue

            # Если нет текущей стратегии - пропускаем
            if current_strategy is None:
                continue

            # Аргументы (строки начинающиеся с --)
            if line.startswith('--'):
                current_args.append(line)
                continue

            # Метаданные (key = value)
            if '=' in line:
                key, _, value = line.partition('=')
                key = key.strip().lower()
                value = value.strip()

                if key == 'name':
                    current_strategy['name'] = value
                elif key == 'author':
                    current_strategy['author'] = value
                elif key == 'label':
                    current_strategy['label'] = value if value else None
                elif key == 'description':
                    current_strategy['description'] = value
                elif key == 'blobs':
                    # blobs = tls7, tls_google -> ['tls7', 'tls_google']
                    current_strategy['blobs'] = [b.strip() for b in value.split(',') if b.strip()]

        # Сохраняем последнюю стратегию
        if current_strategy is not None:
            current_strategy['args'] = '\n'.join(current_args)
            strategies.append(current_strategy)

        log(f"Загружено {len(strategies)} стратегий из TXT: {filepath.name}", "DEBUG")
        result = {'strategies': strategies}
        _set_cached_data(_TXT_FILE_CACHE, filepath, signature, result)
        return deepcopy(result)

    except Exception as e:
        log(f"Ошибка чтения TXT {filepath}: {e}", "ERROR")
        return None


def validate_strategy(strategy: Dict, strategy_id: Optional[str] = None) -> tuple[bool, str]:
    """
    Валидирует стратегию.
    
    Returns:
        (is_valid, error_message)
    """
    # Обязательные поля
    if strategy_id:
        strategy['id'] = strategy_id
    
    if 'id' not in strategy or not strategy['id']:
        return False, "Отсутствует id стратегии"
    
    if 'name' not in strategy or not strategy['name']:
        return False, "Отсутствует name стратегии"
    
    if 'args' not in strategy:
        return False, "Отсутствует args стратегии"
    
    # Проверка id на допустимые символы
    strategy_id = strategy['id']
    if not all(c.isalnum() or c == '_' for c in strategy_id):
        return False, f"id '{strategy_id}' содержит недопустимые символы (разрешены: a-z, 0-9, _)"
    
    # Проверка label
    label = strategy.get('label')
    if label is not None and label not in LABEL_MAP:
        return False, f"Неизвестный label: {label}"
    
    # Проверка blobs - должен быть список
    blobs = strategy.get('blobs', [])
    if not isinstance(blobs, list):
        return False, "blobs должен быть списком"
    
    return True, ""


def _process_args(args: Union[str, List[str]], auto_number: bool = False) -> str:
    """
    Обрабатывает args:
    1. Если это список - склеивает в строку через пробел
    2. Удаляет legacy-теги :strategy=N (runtime-нумерация выполняется перед запуском)
    """
    if not args:
        return ''

    if isinstance(args, list):
        args = ' '.join(args)
    else:
        args = str(args)

    args = re.sub(r':strategy=\d+', '', args)

    return args


def normalize_strategy(strategy: Dict, auto_number: bool = False) -> Dict:
    """Нормализует стратегию, добавляя значения по умолчанию"""
    raw_args = strategy.get('args', '')
    processed_args = _process_args(raw_args, auto_number=auto_number)

    return {
        'id': strategy.get('id', ''),
        'name': strategy.get('name', 'Без названия'),
        'description': strategy.get('description', ''),
        'author': strategy.get('author', 'unknown'),
        'version': strategy.get('version', '1.0'),
        'label': LABEL_MAP.get(strategy.get('label'), None),
        'blobs': strategy.get('blobs', []),
        'args': processed_args,
        'enabled': strategy.get('enabled', True),
        'user_created': strategy.get('user_created', False),
    }


def _load_strategy_file(directory: Path, basename: str) -> Optional[Dict]:
    """
    Загружает файл стратегий в TXT (INI-подобном) формате.

    Args:
        directory: Директория с файлами
        basename: Имя файла без расширения (например 'tcp' или 'tcp_orchestra')

    Returns:
        Dict с ключом 'strategies' или None
    """
    txt_file = directory / f"{basename}.txt"
    if txt_file.exists():
        return load_txt_file(txt_file)

    json_file = directory / f"{basename}.json"
    if json_file.exists():
        return load_json_file(json_file)

    return None


def _external_strategy_basenames(category: str, strategy_set_key: str) -> List[str]:
    # Strict mapping: only explicitly listed filenames are supported.
    target_key = (category or "").strip().lower()
    set_key = (strategy_set_key or "").strip().lower()
    mapped = _EXTERNAL_STRATEGY_BASENAME_MAP.get(set_key, {}).get(target_key)
    return [mapped] if mapped else []



def load_category_strategies(category: str, strategy_set: Optional[str] = None) -> Dict[str, Dict]:
    """
    Загружает стратегии для категории из builtin и user директорий.
    User стратегии имеют приоритет (перезаписывают builtin с тем же id).
    Поддерживает TXT (INI-подобный) и JSON форматы. TXT имеет приоритет.

    Args:
        category: Имя категории (tcp, udp, http80, discord_voice)
        strategy_set: Набор стратегий (например: basic/advanced, None = стандартный)

    Returns:
        Словарь {strategy_id: strategy_dict}
    """
    strategy_set_key = (strategy_set or "").strip().lower()

    # direct_zapret2 Basic/Advanced: load from a
    # stable per-user directory to avoid
    # depending on the install location / INDEXJSON_FOLDER.
    if strategy_set_key in ("basic", "advanced"):
        strategies: Dict[str, Dict] = {}

        try:
            from config import get_zapret_userdata_dir
            base = (get_zapret_userdata_dir() or "").strip()
        except Exception:
            base = ""

        mode_dir = Path(base) / "direct_zapret2" / f"{strategy_set_key}_strategies" if base else None
        try:
            if mode_dir is not None:
                mode_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        mode_data = None
        loaded_basename = None
        if mode_dir is not None:
            for basename in _external_strategy_basenames(category, strategy_set_key):
                txt_path = mode_dir / f"{basename}.txt"
                json_path = mode_dir / f"{basename}.json"
                if not txt_path.exists() and not json_path.exists():
                    continue
                mode_data = _load_strategy_file(mode_dir, basename)
                loaded_basename = basename
                break
        auto_number = False

        if mode_data and 'strategies' in mode_data:
            for strategy in mode_data['strategies']:
                is_valid, error = validate_strategy(strategy)
                if is_valid:
                    normalized = normalize_strategy(strategy, auto_number=auto_number)
                    normalized['_source'] = strategy_set_key
                    strategies[normalized['id']] = normalized
                else:
                    log(f"Пропущена невалидная {strategy_set_key} стратегия: {error}", "WARNING")

        log(
            f"Загружено {len(strategies)} {strategy_set_key} стратегий для категории "
            f"'{category}' ({mode_dir}, file={loaded_basename or 'missing'})",
            "DEBUG",
        )
        return strategies

    ensure_directories()
    strategies = {}

    # Определяем базовое имя файла на основе strategy_set
    if strategy_set_key:
        basename = f"{category}_{strategy_set_key}"
    else:
        basename = category

    builtin_dir = _get_builtin_dir()

    # Загружаем builtin стратегии (TXT или JSON)
    builtin_data = _load_strategy_file(builtin_dir, basename)

    # Если файл с суффиксом не найден, fallback на стандартный
    if builtin_data is None and strategy_set_key:
        log(f"Файл {basename}.txt/.json не найден, используем стандартный {category}", "DEBUG")
        builtin_data = _load_strategy_file(builtin_dir, category)

    auto_number = False

    if builtin_data and 'strategies' in builtin_data:
        for strategy in builtin_data['strategies']:
            is_valid, error = validate_strategy(strategy)
            if is_valid:
                normalized = normalize_strategy(strategy, auto_number=auto_number)
                normalized['_source'] = 'builtin'
                strategies[normalized['id']] = normalized
            else:
                log(f"Пропущена невалидная builtin стратегия: {error}", "WARNING")

    # Загружаем user стратегии (перезаписывают builtin)
    user_data = _load_strategy_file(_get_user_dir(), category)

    if user_data and 'strategies' in user_data:
        for strategy in user_data['strategies']:
            is_valid, error = validate_strategy(strategy)
            if is_valid:
                normalized = normalize_strategy(strategy, auto_number=auto_number)
                normalized['_source'] = 'user'
                normalized['user_created'] = True
                strategies[normalized['id']] = normalized
            else:
                log(f"Пропущена невалидная user стратегия: {error}", "WARNING")
    
    log(f"Загружено {len(strategies)} стратегий для категории '{category}'", "DEBUG")
    return strategies


# Для обратной совместимости - загрузка в старый формат
def load_strategies_as_dict(category: str, strategy_set: Optional[str] = None) -> Dict[str, Dict]:
    """
    Загружает стратегии и возвращает в формате совместимом со старым кодом.

    Args:
        category: Имя категории (tcp, udp, http80, discord_voice)
        strategy_set: Набор стратегий (например: basic/advanced/orchestra, None = стандартный)

    Returns:
        Словарь {strategy_id: {name, description, author, label, blobs, args}}
    """
    strategies = load_category_strategies(category, strategy_set)
    result = {}
    
    for sid, data in strategies.items():
        if not data.get('enabled', True):
            continue
        
        result[sid] = {
            'name': data['name'],
            'description': data['description'],
            'author': data['author'],
            'label': data['label'],
            'blobs': data['blobs'],
            'args': data['args'],
        }
    
    return result


# ==================== ЗАГРУЗКА КАТЕГОРИЙ ====================

def _parse_categories_txt_content(content: str, *, source_name: str) -> Optional[Dict]:
    try:
        categories = []
        current_category = None
        file_version = '1.0'
        file_description = ''
        section_index = 0

        for line in content.splitlines():
            line = line.rstrip()

            # Пропускаем пустые строки
            if not line:
                continue

            # Пропускаем комментарии (строки начинающиеся с #)
            if line.startswith('#'):
                continue

            # Начало новой категории [key]
            if line.startswith('[') and line.endswith(']'):
                # Сохраняем предыдущую категорию
                if current_category is not None:
                    # Строго следуем порядку секций в файле, независимо от order/command_order.
                    file_order = int(current_category.get("_file_order") or 0)
                    current_category["order"] = file_order
                    current_category["command_order"] = file_order
                    categories.append(current_category)

                # Начинаем новую
                # Normalize keys to lower-case so categories match preset parsing logic
                # (preset blocks infer category keys in lower-case from filter tokens/filenames).
                raw_key = line[1:-1].strip()
                target_key = raw_key.lower()
                section_index += 1
                current_category = {
                    'key': target_key,
                    'full_name': raw_key or target_key,  # По умолчанию имя = исходный key
                    '_file_order': section_index,
                }
                continue

            # Метаданные (key = value)
            if '=' in line:
                key, _, value = line.partition('=')
                key = key.strip().lower()
                value = value.strip()

                # Глобальные метаданные файла (до первой категории)
                if current_category is None:
                    if key == 'version':
                        file_version = value
                    elif key == 'description':
                        file_description = value
                    continue

                # Метаданные категории
                if key == 'full_name':
                    current_category['full_name'] = value
                elif key == 'description':
                    current_category['description'] = value
                elif key == 'tooltip':
                    # tooltip может содержать \n - оставляем как есть
                    current_category['tooltip'] = value
                elif key == 'color':
                    current_category['color'] = value
                elif key == 'default_strategy':
                    current_category['default_strategy'] = value
                elif key == 'ports':
                    current_category['ports'] = value
                elif key == 'protocol':
                    current_category['protocol'] = value
                elif key == 'order':
                    # Deprecated: order/command_order are ignored; ordering is determined by section order.
                    pass
                elif key == 'command_order':
                    # Deprecated: order/command_order are ignored; ordering is determined by section order.
                    pass
                elif key == 'needs_new_separator':
                    current_category['needs_new_separator'] = value.lower() == 'true'
                elif key == 'command_group':
                    current_category['command_group'] = value
                elif key == 'icon_name':
                    current_category['icon_name'] = value
                elif key == 'icon_color':
                    current_category['icon_color'] = value
                elif key == 'base_filter':
                    current_category['base_filter'] = value
                elif key == 'base_filter_ipset':
                    current_category['base_filter_ipset'] = value
                elif key == 'base_filter_hostlist':
                    current_category['base_filter_hostlist'] = value
                elif key == 'strategy_type':
                    current_category['strategy_type'] = value
                elif key == 'strip_payload':
                    current_category['strip_payload'] = value.lower() == 'true'
                elif key == 'requires_all_ports':
                    current_category['requires_all_ports'] = value.lower() == 'true'

        # Сохраняем последнюю категорию
        if current_category is not None:
            file_order = int(current_category.get("_file_order") or 0)
            current_category["order"] = file_order
            current_category["command_order"] = file_order
            categories.append(current_category)

        log(f"Загружено {len(categories)} категорий из TXT: {source_name}", "DEBUG")
        return {
            'version': file_version,
            'description': file_description,
            'categories': categories
        }
    except Exception as e:
        log(f"Ошибка парсинга TXT категорий ({source_name}): {e}", "ERROR")
        return None


def load_categories_txt(filepath: Path) -> Optional[Dict]:
    """
    Загружает категории из TXT файла в INI-подобном формате.

    Формат:
        # Categories configuration
        version = 1.0
        description = Описание

        [category_key]
        full_name = Название категории
        description = Описание
        tooltip = Подсказка с \n для переносов строк
        color = #ff6666
        default_strategy = strategy_id
        ports = 80, 443
        protocol = TCP
        order = 1  # устарело (игнорируется)
        command_order = 3  # устарело (игнорируется)
        needs_new_separator = true
        command_group = youtube
        icon_name = fa5b.youtube
        icon_color = #FF0000
        base_filter = --filter-tcp=80,443 --ipset=ipset-youtube.txt
        strategy_type = tcp
        strip_payload = true
        requires_all_ports = true

        [another_category]
        ...

    Returns:
        Dict в формате {'version': '...', 'description': '...', 'categories': [...]} или None при ошибке
    """
    try:
        if not filepath.exists():
            return None

        cached = _get_cached_data(_CATEGORIES_TXT_CACHE, filepath)
        if cached is not None:
            return cached

        signature = _file_signature(filepath)

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        parsed = _parse_categories_txt_content(content, source_name=filepath.name)
        if parsed is not None:
            _set_cached_data(_CATEGORIES_TXT_CACHE, filepath, signature, parsed)
            return deepcopy(parsed)
        return None

    except Exception as e:
        log(f"Ошибка чтения TXT категорий {filepath}: {e}", "ERROR")
        return None


def load_categories_txt_text(text: str, *, source_name: str = "<embedded>") -> Optional[Dict]:
    """Парсит категории из TXT-строки в том же формате, что и `load_categories_txt()`."""
    return _parse_categories_txt_content(text, source_name=source_name)


def load_categories() -> Dict[str, Dict]:
    """
    Загружает категории (вкладки сервисов) из TXT файла.

    Порядок загрузки:
    1. builtin/categories.txt - встроенные категории
    2. один общий user_categories.txt вне папки установки - пользовательские категории (добавляются к builtin)

    Returns:
        Словарь {category_key: category_data}
    """
    ensure_directories()
    categories = {}

    builtin_dir = _get_builtin_dir()

    # Загружаем builtin категории только из categories.txt
    builtin_txt = builtin_dir / "categories.txt"
    builtin_data = load_categories_txt(builtin_txt)

    if builtin_data and 'categories' in builtin_data:
        for cat in builtin_data['categories']:
            key = cat.get('key')
            if key:
                cat['_source'] = 'builtin'
                categories[key] = cat
        log(f"Загружено {len(categories)} встроенных категорий", "DEBUG")
    else:
        log(f"Не удалось загрузить встроенные категории из {builtin_txt}", "WARNING")

    # Загружаем user категории (добавляются к builtin, НЕ перезаписывают builtin).
    # Храним вне папки установки (pyinstaller/обновления могут затереть файлы).
    user_txt = get_user_categories_file_path()
    user_data = None
    if user_txt.exists():
        user_data = load_categories_txt(user_txt)

    if user_data and 'categories' in user_data:
        user_count = 0
        for cat in user_data['categories']:
            key = cat.get('key')
            if key:
                cat['_source'] = 'user'
                # If user forgot/typoed command_group, default to "user" so it shows
                # under the "Пользовательские" group in the GUI.
                if 'command_group' not in cat or not str(cat.get('command_group') or '').strip():
                    cat['command_group'] = 'user'
                if key in categories:
                    # User is not allowed to override built-in categories.
                    log(f"Пользовательская категория '{key}' конфликтует с системной и будет проигнорирована", "WARNING")
                else:
                    categories[key] = cat
                user_count += 1
        if user_count > 0:
            log(f"Загружено {user_count} пользовательских категорий", "DEBUG")

    return categories
