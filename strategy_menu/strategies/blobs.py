# strategy_menu/strategies/blobs.py

"""
Определения блобов для стратегий Zapret 2.
Блобы загружаются из JSON файла и могут использоваться в нескольких стратегиях.

Поддерживает:
1. Системные блобы из json/blobs.json (секция "blobs")
2. Пользовательские блобы из json/blobs.json (секция "user_blobs")
3. Автоматическую дедупликацию при сборке командной строки
"""

import re
import os
import json

from log import log

# Кэш для блобов - заполняется при первом вызове get_blobs()
_BLOBS_CACHE = None
_BLOBS_JSON_PATH = None


def _get_blobs_json_path() -> str:
    """Возвращает путь к JSON файлу блобов"""
    global _BLOBS_JSON_PATH
    if _BLOBS_JSON_PATH is None:
        from config import INDEXJSON_FOLDER
        _BLOBS_JSON_PATH = os.path.join(INDEXJSON_FOLDER, "blobs.json")
    return _BLOBS_JSON_PATH


def _load_blobs_from_json() -> dict:
    """
    Загружает блобы из JSON файла.
    Объединяет системные блобы (blobs) и пользовательские (user_blobs).
    
    Returns:
        Словарь {имя_блоба: значение_для_командной_строки}
    """
    from config import BIN_FOLDER
    
    json_path = _get_blobs_json_path()
    result = {}
    
    def _process_blob(name: str, data: dict) -> str | None:
        """Обрабатывает один блоб из JSON"""
        if not isinstance(data, dict):
            return None
            
        # Hex значение
        if "hex" in data:
            return data["hex"]
            
        # Путь к файлу
        if "path" in data:
            path = data["path"]
            # Если путь относительный - добавляем BIN_FOLDER
            if not os.path.isabs(path):
                path = os.path.join(BIN_FOLDER, path)
            return f"@{path}"
            
        return None
    
    try:
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Загружаем системные блобы
            if "blobs" in data and isinstance(data["blobs"], dict):
                for name, blob_data in data["blobs"].items():
                    if name.startswith("_"):  # Пропускаем комментарии
                        continue
                    value = _process_blob(name, blob_data)
                    if value:
                        result[name] = value
            
            # Загружаем пользовательские блобы (перезаписывают системные)
            if "user_blobs" in data and isinstance(data["user_blobs"], dict):
                for name, blob_data in data["user_blobs"].items():
                    if name.startswith("_"):  # Пропускаем комментарии
                        continue
                    value = _process_blob(name, blob_data)
                    if value:
                        result[name] = value
                        log(f"Загружен пользовательский блоб: {name}", "DEBUG")
            
            log(f"Загружено {len(result)} блобов из {json_path}", "DEBUG")
        else:
            log(f"⚠️ Файл блобов не найден: {json_path}", "WARNING")
            
    except json.JSONDecodeError as e:
        log(f"❌ Ошибка парсинга JSON блобов: {e}", "ERROR")
    except Exception as e:
        log(f"❌ Ошибка загрузки блобов: {e}", "ERROR")
    
    return result




def get_blobs() -> dict:
    """
    Возвращает словарь блобов с правильными путями.
    Ленивая инициализация - загрузка происходит при первом вызове.
    """
    global _BLOBS_CACHE
    if _BLOBS_CACHE is not None:
        return _BLOBS_CACHE
    
    _BLOBS_CACHE = _load_blobs_from_json()
    return _BLOBS_CACHE


def reload_blobs() -> dict:
    """
    Перезагружает блобы из JSON файла (сбрасывает кэш).
    Полезно после редактирования пользователем.
    
    Returns:
        Обновлённый словарь блобов
    """
    global _BLOBS_CACHE
    _BLOBS_CACHE = None
    return get_blobs()


def get_blobs_info() -> dict:
    """
    Возвращает расширенную информацию о блобах для UI.
    
    Returns:
        Словарь {имя_блоба: {value, description, is_user, exists}}
    """
    from config import BIN_FOLDER
    
    json_path = _get_blobs_json_path()
    result = {}
    
    try:
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Системные блобы
            if "blobs" in data and isinstance(data["blobs"], dict):
                for name, blob_data in data["blobs"].items():
                    if name.startswith("_"):
                        continue
                    if not isinstance(blob_data, dict):
                        continue
                        
                    info = {
                        "description": blob_data.get("description", ""),
                        "is_user": False,
                        "exists": True
                    }
                    
                    if "hex" in blob_data:
                        info["value"] = blob_data["hex"]
                        info["type"] = "hex"
                    elif "path" in blob_data:
                        path = blob_data["path"]
                        if not os.path.isabs(path):
                            full_path = os.path.join(BIN_FOLDER, path)
                        else:
                            full_path = path
                        info["value"] = f"@{full_path}"
                        info["path"] = full_path
                        info["type"] = "file"
                        info["exists"] = os.path.exists(full_path)
                    
                    result[name] = info
            
            # Пользовательские блобы
            if "user_blobs" in data and isinstance(data["user_blobs"], dict):
                for name, blob_data in data["user_blobs"].items():
                    if name.startswith("_"):
                        continue
                    if not isinstance(blob_data, dict):
                        continue
                        
                    info = {
                        "description": blob_data.get("description", "Пользовательский блоб"),
                        "is_user": True,
                        "exists": True
                    }
                    
                    if "hex" in blob_data:
                        info["value"] = blob_data["hex"]
                        info["type"] = "hex"
                    elif "path" in blob_data:
                        path = blob_data["path"]
                        if not os.path.isabs(path):
                            full_path = os.path.join(BIN_FOLDER, path)
                        else:
                            full_path = path
                        info["value"] = f"@{full_path}"
                        info["path"] = full_path
                        info["type"] = "file"
                        info["exists"] = os.path.exists(full_path)
                    
                    result[name] = info
                    
    except Exception as e:
        log(f"❌ Ошибка получения информации о блобах: {e}", "ERROR")
    
    return result


def save_user_blob(name: str, blob_type: str, value: str, description: str = "") -> bool:
    """
    Сохраняет пользовательский блоб в JSON.
    
    Args:
        name: Имя блоба (без пробелов, латиница и цифры)
        blob_type: "hex" или "file"
        value: Hex значение (0x...) или путь к файлу
        description: Описание блоба
        
    Returns:
        True если успешно
    """
    json_path = _get_blobs_json_path()
    
    try:
        # Загружаем текущий JSON
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {"blobs": {}, "user_blobs": {}}
        
        # Создаём секцию user_blobs если её нет
        if "user_blobs" not in data:
            data["user_blobs"] = {}
        
        # Добавляем блоб
        blob_data = {"description": description}
        if blob_type == "hex":
            blob_data["hex"] = value
        else:
            blob_data["path"] = value
        
        data["user_blobs"][name] = blob_data
        
        # Сохраняем
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        # Сбрасываем кэш
        reload_blobs()
        
        log(f"Сохранён пользовательский блоб: {name}", "INFO")
        return True
        
    except Exception as e:
        log(f"Ошибка сохранения блоба {name}: {e}", "ERROR")
        return False


def delete_user_blob(name: str) -> bool:
    """
    Удаляет пользовательский блоб из JSON.
    
    Args:
        name: Имя блоба
        
    Returns:
        True если успешно
    """
    json_path = _get_blobs_json_path()
    
    try:
        if not os.path.exists(json_path):
            return False
            
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if "user_blobs" not in data or name not in data["user_blobs"]:
            log(f"Блоб {name} не найден в user_blobs", "WARNING")
            return False
        
        del data["user_blobs"][name]
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        # Сбрасываем кэш
        reload_blobs()
        
        log(f"Удалён пользовательский блоб: {name}", "INFO")
        return True
        
    except Exception as e:
        log(f"Ошибка удаления блоба {name}: {e}", "ERROR")
        return False


# Для обратной совместимости - будет заполнен при первом использовании
# Используйте get_blobs() для гарантированно правильных путей
BLOBS = {}

# Регулярка для поиска --blob=name:value в строке аргументов
BLOB_PATTERN = re.compile(r'--blob=([^:\s]+):([^\s]+)')

# Паттерны для поиска использования блобов в lua-desync аргументах
# :blob=name, seqovl_pattern=name, pattern=name, fakedsplit_pattern=name
BLOB_USAGE_PATTERNS = [
    re.compile(r':blob=([a-zA-Z0-9_]+)'),           # :blob=tls5
    re.compile(r'seqovl_pattern=([a-zA-Z0-9_]+)'),  # seqovl_pattern=tls_google
    re.compile(r'pattern=([a-zA-Z0-9_]+)'),         # pattern=tls7 (но не pattern=0x...)
    re.compile(r'fakedsplit_pattern=([a-zA-Z0-9_]+)'),  # fakedsplit_pattern=tls4
]


def find_used_blobs(args: str) -> set:
    """
    Находит все блобы, используемые в строке аргументов.
    Ищет :blob=name, seqovl_pattern=name, pattern=name и т.д.
    
    Returns:
        Множество имён используемых блобов
    """
    blobs = get_blobs()
    used = set()
    for pattern in BLOB_USAGE_PATTERNS:
        for match in pattern.finditer(args):
            blob_name = match.group(1)
            # Пропускаем hex-значения (0x...) - они не являются именами блобов
            if not blob_name.startswith('0x') and blob_name in blobs:
                used.add(blob_name)
    return used


def generate_blob_definitions(blob_names: set) -> str:
    """
    Генерирует строку с --blob=name:value для всех указанных блобов.
    """
    blobs = get_blobs()
    definitions = []
    for name in sorted(blob_names):  # Сортируем для стабильного порядка
        if name in blobs:
            definitions.append(f"--blob={name}:{blobs[name]}")
    return " ".join(definitions)


def extract_and_dedupe_blobs(args_list: list[str]) -> tuple[str, str]:
    """
    Извлекает все --blob=... из списка строк аргументов,
    дедуплицирует их, и возвращает отдельно.
    
    Args:
        args_list: Список строк с аргументами (от разных стратегий)
        
    Returns:
        Кортеж (blobs_str, remaining_args_str):
        - blobs_str: Уникальные --blob=... объединённые в строку
        - remaining_args_str: Остальные аргументы без --blob=...
    """
    seen_blobs = {}  # name -> full_definition
    remaining_parts = []
    
    for args in args_list:
        if not args:
            continue
            
        # Находим все блобы в этой строке
        for match in BLOB_PATTERN.finditer(args):
            blob_name = match.group(1)
            blob_value = match.group(2)
            full_def = f"--blob={blob_name}:{blob_value}"
            
            # Сохраняем только первое определение каждого блоба
            if blob_name not in seen_blobs:
                seen_blobs[blob_name] = full_def
        
        # Убираем блобы из строки аргументов
        cleaned = BLOB_PATTERN.sub('', args).strip()
        # Убираем множественные пробелы
        cleaned = ' '.join(cleaned.split())
        if cleaned:
            remaining_parts.append(cleaned)
    
    blobs_str = ' '.join(seen_blobs.values())
    remaining_str = ' '.join(remaining_parts)
    
    return blobs_str, remaining_str


def build_args_with_deduped_blobs(args_list: list[str]) -> str:
    """
    Собирает финальную командную строку с дедуплицированными блобами.
    
    1. Извлекает явные --blob=name:value из аргументов
    2. Находит все используемые блобы (:blob=name, seqovl_pattern=name, etc.)
    3. Автоматически добавляет --blob=name:@path для каждого используемого блоба (кроме уже определённых)
    4. Блобы выносятся в начало командной строки
    
    Args:
        args_list: Список строк с аргументами (от разных стратегий/профилей)
        
    Returns:
        Финальная командная строка с блобами в начале
    """
    # Извлекаем явно заданные блобы и получаем их имена
    seen_blob_names = set()
    for args in args_list:
        if args:
            for match in BLOB_PATTERN.finditer(args):
                seen_blob_names.add(match.group(1))
    
    # Извлекаем явно заданные блобы
    explicit_blobs_str, remaining_str = extract_and_dedupe_blobs(args_list)
    
    # Находим все используемые блобы в оставшихся аргументах
    all_used_blobs = set()
    for args in args_list:
        if args:
            all_used_blobs.update(find_used_blobs(args))
    
    # Исключаем блобы которые уже явно определены
    blobs_to_auto_generate = all_used_blobs - seen_blob_names
    
    # Генерируем определения только для недостающих блобов
    auto_blobs_str = generate_blob_definitions(blobs_to_auto_generate)
    
    # Объединяем: явные блобы + автоматические блобы + остальные аргументы
    parts = []
    if explicit_blobs_str:
        parts.append(explicit_blobs_str)
    if auto_blobs_str:
        parts.append(auto_blobs_str)
    if remaining_str:
        parts.append(remaining_str)
    
    return " ".join(parts)


def get_blob_definition(blob_name: str) -> str:
    """
    Возвращает строку определения блоба для командной строки.
    
    Args:
        blob_name: Имя блоба из словаря BLOBS
        
    Returns:
        Строка вида "--blob=name:@path" или "--blob=name:0xHEX"
    """
    blobs = get_blobs()
    if blob_name not in blobs:
        raise ValueError(f"Unknown blob: {blob_name}")
    return f"--blob={blob_name}:{blobs[blob_name]}"


def get_blobs_args(blob_names: list[str]) -> str:
    """
    Возвращает строку с определениями всех указанных блобов.
    Дубликаты автоматически удаляются.
    
    Args:
        blob_names: Список имён блобов
        
    Returns:
        Строка с --blob=... для каждого уникального блоба
    """
    unique_blobs = list(dict.fromkeys(blob_names))  # Сохраняем порядок, убираем дубли
    return " ".join(get_blob_definition(name) for name in unique_blobs)


def collect_blobs_from_strategies(strategies: list[dict]) -> list[str]:
    """
    Собирает все уникальные блобы из списка стратегий.
    
    Args:
        strategies: Список словарей стратегий с полем 'blobs'
        
    Returns:
        Список уникальных имён блобов
    """
    all_blobs = []
    for strategy in strategies:
        if "blobs" in strategy:
            all_blobs.extend(strategy["blobs"])
    # Убираем дубликаты, сохраняя порядок
    return list(dict.fromkeys(all_blobs))
