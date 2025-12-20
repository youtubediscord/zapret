"""
Загрузчик стратегий из JSON файлов.

Стратегии загружаются из:
1. {INDEXJSON_FOLDER}/strategies/builtin/ - встроенные стратегии (обновляются с программой)
2. {INDEXJSON_FOLDER}/strategies/user/ - пользовательские стратегии (сохраняются при обновлении)

Каждая категория имеет свой JSON файл:
- tcp.json - TCP стратегии (YouTube, Discord TCP, и т.д.)
- udp.json - UDP стратегии (QUIC, игры)
- http80.json - HTTP порт 80
- discord_voice.json - Discord голос
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from log import log
from config import INDEXJSON_FOLDER

# Путь к папке со стратегиями - используем INDEXJSON_FOLDER из конфига
# Структура: {INDEXJSON_FOLDER}/strategies/builtin/ и {INDEXJSON_FOLDER}/strategies/user/
STRATEGIES_DIR = Path(INDEXJSON_FOLDER) / "strategies"

# Fallback на локальную папку (для разработки)
_LOCAL_STRATEGIES_DIR = Path(__file__).parent

# Fallback на соседнюю папку zapret (для разработки из IDE)
_DEV_ZAPRET_DIR = Path(__file__).parent.parent.parent.parent / "zapret" / "json" / "strategies"


def _get_builtin_dir() -> Path:
    """Возвращает путь к builtin директории (с fallback)"""
    global_builtin = STRATEGIES_DIR / "builtin"
    local_builtin = _LOCAL_STRATEGIES_DIR / "builtin"
    dev_builtin = _DEV_ZAPRET_DIR / "builtin"
    
    # 1. Если глобальная папка существует и содержит categories.json - используем её
    if global_builtin.exists() and (global_builtin / "categories.json").exists():
        return global_builtin
    
    # 2. Проверяем соседнюю папку zapret (для разработки из IDE)
    if dev_builtin.exists() and (dev_builtin / "categories.json").exists():
        return dev_builtin
    
    # 3. Проверяем локальную папку strategy_menu/strategies/builtin
    if local_builtin.exists() and (local_builtin / "categories.json").exists():
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
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        log(f"Ошибка парсинга JSON {filepath}: {e}", "ERROR")
        return None
    except Exception as e:
        log(f"Ошибка чтения {filepath}: {e}", "ERROR")
        return None


def save_json_file(filepath: Path, data: Dict) -> bool:
    """Сохраняет данные в JSON файл"""
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log(f"Ошибка сохранения {filepath}: {e}", "ERROR")
        return False


def validate_strategy(strategy: Dict, strategy_id: str = None) -> tuple[bool, str]:
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
    2. Если auto_number=True - добавляет :strategy=N ко ВСЕМ --lua-desync= на каждой строке
       (для combo стратегий все --lua-desync на одной строке получают одинаковый N)
    """
    if not args:
        return ''

    # Авто-нумерация стратегий (только для orchestra)
    if auto_number and isinstance(args, list):
        strategy_counter = 0
        processed_lines = []

        for line in args:
            # Пропускаем строки без lua-desync
            if '--lua-desync=' not in line:
                processed_lines.append(line)
                continue

            # Проверяем первый lua-desync на строке
            match = re.search(r'--lua-desync=([^\s]+)', line)
            if match:
                content = match.group(1)
                # circular/pass - это управление, не нумеруем
                if content.startswith('circular') or content == 'pass':
                    processed_lines.append(line)
                    continue
                # Если уже есть :strategy= - не добавляем
                if ':strategy=' in line:
                    processed_lines.append(line)
                    continue

                # Добавляем ОДИНАКОВЫЙ :strategy=N ко ВСЕМ lua-desync на строке (combo)
                strategy_counter += 1
                new_line = re.sub(
                    r'(--lua-desync=[^\s]+)',
                    rf'\1:strategy={strategy_counter}',
                    line
                )
                processed_lines.append(new_line)
            else:
                processed_lines.append(line)

        args = ' '.join(processed_lines)
    elif isinstance(args, list):
        args = ' '.join(args)

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


def load_category_strategies(category: str, strategy_set: str = None) -> Dict[str, Dict]:
    """
    Загружает стратегии для категории из builtin и user директорий.
    User стратегии имеют приоритет (перезаписывают builtin с тем же id).

    Args:
        category: Имя категории (tcp, udp, http80, discord_voice)
        strategy_set: Набор стратегий (None = стандартный, "orchestra" = tcp_orchestra.json и т.д.)

    Returns:
        Словарь {strategy_id: strategy_dict}
    """
    ensure_directories()
    strategies = {}

    # Определяем имя файла на основе strategy_set
    if strategy_set:
        filename = f"{category}_{strategy_set}.json"
    else:
        filename = f"{category}.json"

    # Загружаем builtin стратегии
    builtin_file = _get_builtin_dir() / filename

    # Если файл с суффиксом не найден, fallback на стандартный
    if strategy_set and not builtin_file.exists():
        log(f"Файл {filename} не найден, используем стандартный {category}.json", "DEBUG")
        builtin_file = _get_builtin_dir() / f"{category}.json"

    builtin_data = load_json_file(builtin_file)

    # Авто-нумерация :strategy=N только для orchestra
    auto_number = (strategy_set == "orchestra")

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
    user_file = _get_user_dir() / f"{category}.json"
    user_data = load_json_file(user_file)

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


def save_user_strategy(category: str, strategy: Dict) -> tuple[bool, str]:
    """
    Сохраняет пользовательскую стратегию.
    
    Args:
        category: Категория (tcp, udp, http80, discord_voice)
        strategy: Словарь стратегии
        
    Returns:
        (success, error_message)
    """
    is_valid, error = validate_strategy(strategy)
    if not is_valid:
        return False, error
    
    ensure_directories()
    user_file = _get_user_dir() / f"{category}.json"
    
    # Загружаем существующие user стратегии
    user_data = load_json_file(user_file) or {'strategies': []}
    
    # Ищем существующую стратегию с таким же id
    strategy_id = strategy['id']
    existing_idx = None
    for i, s in enumerate(user_data['strategies']):
        if s.get('id') == strategy_id:
            existing_idx = i
            break
    
    # Помечаем как пользовательскую
    strategy['user_created'] = True
    
    if existing_idx is not None:
        # Обновляем существующую
        user_data['strategies'][existing_idx] = strategy
    else:
        # Добавляем новую
        user_data['strategies'].append(strategy)
    
    if save_json_file(user_file, user_data):
        log(f"Сохранена пользовательская стратегия '{strategy_id}' в {category}", "INFO")
        return True, ""
    else:
        return False, "Ошибка записи файла"


def delete_user_strategy(category: str, strategy_id: str) -> tuple[bool, str]:
    """
    Удаляет пользовательскую стратегию.
    
    Returns:
        (success, error_message)
    """
    user_file = _get_user_dir() / f"{category}.json"
    user_data = load_json_file(user_file)
    
    if not user_data or 'strategies' not in user_data:
        return False, "Файл пользовательских стратегий не найден"
    
    # Ищем и удаляем
    original_len = len(user_data['strategies'])
    user_data['strategies'] = [s for s in user_data['strategies'] if s.get('id') != strategy_id]
    
    if len(user_data['strategies']) == original_len:
        return False, f"Стратегия '{strategy_id}' не найдена"
    
    if save_json_file(user_file, user_data):
        log(f"Удалена пользовательская стратегия '{strategy_id}' из {category}", "INFO")
        return True, ""
    else:
        return False, "Ошибка записи файла"


def get_all_categories() -> List[str]:
    """Возвращает список всех категорий с JSON файлами"""
    ensure_directories()
    categories = set()
    
    # Собираем из builtin
    for f in _get_builtin_dir().glob("*.json"):
        if f.name != "schema.json" and f.name != "categories.json":
            categories.add(f.stem)
    
    # Собираем из user
    for f in _get_user_dir().glob("*.json"):
        if f.name != "categories.json":
            categories.add(f.stem)
    
    return sorted(categories)


def export_strategies_to_json(strategies_dict: Dict[str, Dict], category: str, output_dir: Path = None) -> bool:
    """
    Экспортирует словарь стратегий в JSON файл.
    Используется для конвертации из старого формата.
    
    Args:
        strategies_dict: Словарь {id: strategy_data}
        category: Имя категории
        output_dir: Директория для сохранения (по умолчанию builtin)
    """
    if output_dir is None:
        output_dir = _get_builtin_dir()
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    strategies_list = []
    for strategy_id, data in strategies_dict.items():
        strategy = {
            'id': strategy_id,
            'name': data.get('name', strategy_id),
            'description': data.get('description', ''),
            'author': data.get('author', 'unknown'),
            'label': data.get('label'),
            'blobs': data.get('blobs', []),
            'args': data.get('args', ''),
        }
        strategies_list.append(strategy)
    
    output_data = {
        'category': category,
        'version': '1.0',
        'strategies': strategies_list
    }
    
    output_file = output_dir / f"{category}.json"
    return save_json_file(output_file, output_data)


# Для обратной совместимости - загрузка в старый формат
def load_strategies_as_dict(category: str, strategy_set: str = None) -> Dict[str, Dict]:
    """
    Загружает стратегии и возвращает в формате совместимом со старым кодом.

    Args:
        category: Имя категории (tcp, udp, http80, discord_voice)
        strategy_set: Набор стратегий (None = стандартный, "orchestra" и т.д.)

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

def load_categories() -> Dict[str, Dict]:
    """
    Загружает категории (вкладки сервисов) из JSON файлов.
    
    Порядок загрузки:
    1. builtin/categories.json - встроенные категории
    2. user/categories.json - пользовательские категории (добавляются к builtin)
    
    Returns:
        Словарь {category_key: category_data}
    """
    ensure_directories()
    categories = {}
    
    # Загружаем builtin категории
    builtin_file = _get_builtin_dir() / "categories.json"
    builtin_data = load_json_file(builtin_file)
    
    if builtin_data and 'categories' in builtin_data:
        for cat in builtin_data['categories']:
            key = cat.get('key')
            if key:
                cat['_source'] = 'builtin'
                categories[key] = cat
        log(f"Загружено {len(categories)} встроенных категорий", "DEBUG")
    else:
        log(f"Не найден файл категорий: {builtin_file}", "WARNING")
    
    # Загружаем user категории (добавляются/перезаписывают builtin)
    user_file = _get_user_dir() / "categories.json"
    user_data = load_json_file(user_file)
    
    if user_data and 'categories' in user_data:
        user_count = 0
        for cat in user_data['categories']:
            key = cat.get('key')
            if key:
                cat['_source'] = 'user'
                # Если категория уже есть - мержим настройки
                if key in categories:
                    categories[key].update(cat)
                else:
                    categories[key] = cat
                user_count += 1
        if user_count > 0:
            log(f"Загружено {user_count} пользовательских категорий", "DEBUG")
    
    return categories


def save_user_category(category: Dict) -> tuple[bool, str]:
    """
    Сохраняет пользовательскую категорию.
    
    Args:
        category: Словарь с данными категории (обязательно поле 'key')
        
    Returns:
        (success, error_message)
    """
    key = category.get('key')
    if not key:
        return False, "Отсутствует key категории"
    
    if not category.get('full_name'):
        return False, "Отсутствует full_name категории"
    
    ensure_directories()
    user_file = _get_user_dir() / "categories.json"
    
    # Загружаем существующие user категории
    user_data = load_json_file(user_file) or {'categories': [], 'version': '1.0'}
    
    # Ищем существующую категорию с таким же key
    existing_idx = None
    for i, c in enumerate(user_data['categories']):
        if c.get('key') == key:
            existing_idx = i
            break
    
    if existing_idx is not None:
        user_data['categories'][existing_idx] = category
    else:
        user_data['categories'].append(category)
    
    if save_json_file(user_file, user_data):
        log(f"Сохранена пользовательская категория '{key}'", "INFO")
        return True, ""
    else:
        return False, "Ошибка записи файла"


def delete_user_category(key: str) -> tuple[bool, str]:
    """
    Удаляет пользовательскую категорию.
    
    Returns:
        (success, error_message)
    """
    user_file = _get_user_dir() / "categories.json"
    user_data = load_json_file(user_file)
    
    if not user_data or 'categories' not in user_data:
        return False, "Файл пользовательских категорий не найден"
    
    original_len = len(user_data['categories'])
    user_data['categories'] = [c for c in user_data['categories'] if c.get('key') != key]
    
    if len(user_data['categories']) == original_len:
        return False, f"Категория '{key}' не найдена"
    
    if save_json_file(user_file, user_data):
        log(f"Удалена пользовательская категория '{key}'", "INFO")
        return True, ""
    else:
        return False, "Ошибка записи файла"
