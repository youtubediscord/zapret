# blobs/service.py

"""
Определения блобов для стратегий Zapret 2.
Блобы загружаются из JSON файла и могут использоваться в нескольких стратегиях.

Поддерживает:
1. HARDCODED_BLOBS - системные блобы, жёстко заданные в коде
2. Пользовательские блобы из json/blobs.json (секция "user_blobs")
3. Автоматическую дедупликацию при сборке командной строки
"""

import re
import os
import json

from log import log

# Примечание: blobs.json находится в /home/privacy/zapret/json/blobs.json
# (не в папке проекта zapretgui, а в родительской папке zapret)

# Кэш для блобов - заполняется при первом вызове get_blobs()
_BLOBS_CACHE = None
_BLOBS_JSON_PATH = None

# Все системные блобы добавляются в начало preset файла.
# Пути к файлам относительные (@bin/...) - они разрешаются winws2.exe.
HARDCODED_BLOBS = (
    "--blob=tls_google:@bin/tls_clienthello_www_google_com.bin "
    "--blob=tls1:@bin/tls_clienthello_1.bin "
    "--blob=tls2:@bin/tls_clienthello_2.bin "
    "--blob=tls2n:@bin/tls_clienthello_2n.bin "
    "--blob=tls3:@bin/tls_clienthello_3.bin "
    "--blob=tls4:@bin/tls_clienthello_4.bin "
    "--blob=tls5:@bin/tls_clienthello_5.bin "
    "--blob=tls6:@bin/tls_clienthello_6.bin "
    "--blob=tls7:@bin/tls_clienthello_7.bin "
    "--blob=tls8:@bin/tls_clienthello_8.bin "
    "--blob=tls9:@bin/tls_clienthello_9.bin "
    "--blob=tls10:@bin/tls_clienthello_10.bin "
    "--blob=tls11:@bin/tls_clienthello_11.bin "
    "--blob=tls12:@bin/tls_clienthello_12.bin "
    "--blob=tls13:@bin/tls_clienthello_13.bin "
    "--blob=tls14:@bin/tls_clienthello_14.bin "
    "--blob=tls17:@bin/tls_clienthello_17.bin "
    "--blob=tls18:@bin/tls_clienthello_18.bin "
    "--blob=tls_sber:@bin/tls_clienthello_sberbank_ru.bin "
    "--blob=tls_vk:@bin/tls_clienthello_vk_com.bin "
    "--blob=tls_vk_kyber:@bin/tls_clienthello_vk_com_kyber.bin "
    "--blob=tls_deepseek:@bin/tls_clienthello_chat_deepseek_com.bin "
    "--blob=tls_max:@bin/tls_clienthello_max_ru.bin "
    "--blob=tls_iana:@bin/tls_clienthello_iana_org.bin "
    "--blob=tls_4pda:@bin/tls_clienthello_4pda_to.bin "
    "--blob=tls_gosuslugi:@bin/tls_clienthello_gosuslugi_ru.bin "
    "--blob=syndata3:@bin/tls_clienthello_3.bin "
    "--blob=syn_packet:@bin/syn_packet.bin "
    "--blob=dtls_w3:@bin/dtls_clienthello_w3_org.bin "
    "--blob=quic_google:@bin/quic_initial_www_google_com.bin "
    "--blob=quic_vk:@bin/quic_initial_vk_com.bin "
    "--blob=quic1:@bin/quic_1.bin "
    "--blob=quic2:@bin/quic_2.bin "
    "--blob=quic3:@bin/quic_3.bin "
    "--blob=quic4:@bin/quic_4.bin "
    "--blob=quic5:@bin/quic_5.bin "
    "--blob=quic6:@bin/quic_6.bin "
    "--blob=quic7:@bin/quic_7.bin "
    "--blob=quic_test:@bin/quic_test_00.bin "
    "--blob=fake_tls:@bin/fake_tls_1.bin "
    "--blob=fake_tls_1:@bin/fake_tls_1.bin "
    "--blob=fake_tls_2:@bin/fake_tls_2.bin "
    "--blob=fake_tls_3:@bin/fake_tls_3.bin "
    "--blob=fake_tls_4:@bin/fake_tls_4.bin "
    "--blob=fake_tls_5:@bin/fake_tls_5.bin "
    "--blob=fake_tls_6:@bin/fake_tls_6.bin "
    "--blob=fake_tls_7:@bin/fake_tls_7.bin "
    "--blob=fake_tls_8:@bin/fake_tls_8.bin "
    "--blob=fake_quic:@bin/fake_quic.bin "
    "--blob=fake_quic_1:@bin/fake_quic_1.bin "
    "--blob=fake_quic_2:@bin/fake_quic_2.bin "
    "--blob=fake_quic_3:@bin/fake_quic_3.bin "
    "--blob=fake_default_udp:0x00000000000000000000000000000000 "
    "--blob=http_req:@bin/http_iana_org.bin "
    "--blob=hex_0e0e0f0e:0x0E0E0F0E "
    "--blob=hex_0f0e0e0f:0x0F0E0E0F "
    "--blob=hex_0f0f0f0f:0x0F0F0F0F "
    "--blob=hex_00:0x00"
)


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


def get_system_blobs_info() -> dict:
    """
    Возвращает информацию о всех системных блобах (из HARDCODED_BLOBS).

    Returns:
        dict: {
            "blob_name": {
                "value": "@bin/file.bin" или "0x...",
                "type": "file" или "hex",
                "is_user": False,
                "exists": True/False (для файлов),
                "description": ""
            }
        }
    """
    from config import BIN_FOLDER

    # Парсим HARDCODED_BLOBS строку
    # Формат: "--blob=name:value --blob=name2:value2 ..."
    pattern = r'--blob=([^:]+):([^\s]+)'

    result = {}
    for match in re.finditer(pattern, HARDCODED_BLOBS):
        name = match.group(1)
        value = match.group(2)

        # Определяем тип
        if value.startswith("0x"):
            blob_type = "hex"
            exists = True  # hex значения всегда "существуют"
        else:
            blob_type = "file"
            # Проверяем существование файла
            file_path = value[1:] if value.startswith("@") else value
            # Убираем "bin/" если есть, т.к. BIN_FOLDER уже указывает на bin/
            if file_path.startswith("bin/") or file_path.startswith("bin\\"):
                file_path = file_path[4:]
            full_path = os.path.join(BIN_FOLDER, file_path)
            exists = os.path.exists(full_path)

        result[name] = {
            "value": value,
            "type": blob_type,
            "is_user": False,
            "exists": exists,
            "description": ""  # Системные блобы без описания
        }

    return result


def _load_user_blobs_info() -> dict:
    """
    Загружает информацию о пользовательских блобах из JSON.

    Returns:
        dict: Словарь с информацией о пользовательских блобах
    """
    from config import BIN_FOLDER

    json_path = _get_blobs_json_path()
    result = {}

    try:
        if not os.path.exists(json_path):
            return {}

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        user_blobs_data = data.get("user_blobs", {})

        for name, blob_data in user_blobs_data.items():
            if name.startswith("_"):  # Пропускаем комментарии
                continue
            if not isinstance(blob_data, dict):
                continue

            info = {
                "description": blob_data.get("description", "Пользовательский блоб"),
                "is_user": True,
                "exists": True
            }

            # Определяем тип и значение
            if "hex" in blob_data:
                value = blob_data["hex"]
                info["value"] = value
                info["type"] = "hex"
            elif "path" in blob_data:
                path = blob_data["path"]
                # Если относительный путь - добавляем @
                if not path.startswith("@"):
                    value = f"@{path}"
                else:
                    value = path
                info["value"] = value
                info["type"] = "file"

                # Проверяем существование
                file_path = value[1:] if value.startswith("@") else value
                if not os.path.isabs(file_path):
                    full_path = os.path.join(BIN_FOLDER, file_path)
                else:
                    full_path = file_path
                info["path"] = full_path
                info["exists"] = os.path.exists(full_path)
            else:
                continue

            result[name] = info

    except Exception as e:
        log(f"Ошибка загрузки user blobs: {e}", "ERROR")

    return result


def get_blobs_info() -> dict:
    """
    Возвращает информацию обо ВСЕХ блобах (системные + пользовательские).

    Returns:
        dict: {имя_блоба: {value, type, description, is_user, exists}}
    """
    # Загружаем системные блобы
    system_blobs = get_system_blobs_info()

    # Загружаем пользовательские блобы
    user_blobs = _load_user_blobs_info()

    # Объединяем (пользовательские перезаписывают системные если есть конфликт)
    result = system_blobs.copy()
    result.update(user_blobs)

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


def get_user_blobs_args() -> str:
    """
    Возвращает строку с определениями ТОЛЬКО пользовательских блобов.
    Системные блобы игнорируются - они захардкожены в HARDCODED_BLOBS.

    Returns:
        Строка с --blob=name:value для каждого пользовательского блоба,
        или пустая строка если пользовательских блобов нет.
    """
    from config import BIN_FOLDER

    json_path = _get_blobs_json_path()
    user_blobs_parts = []

    try:
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Загружаем ТОЛЬКО пользовательские блобы
            if "user_blobs" in data and isinstance(data["user_blobs"], dict):
                for name, blob_data in data["user_blobs"].items():
                    if name.startswith("_"):  # Пропускаем комментарии
                        continue
                    if not isinstance(blob_data, dict):
                        continue

                    # Hex значение
                    if "hex" in blob_data:
                        user_blobs_parts.append(f"--blob={name}:{blob_data['hex']}")
                    # Путь к файлу
                    elif "path" in blob_data:
                        path = blob_data["path"]
                        if not os.path.isabs(path):
                            path = os.path.join(BIN_FOLDER, path)
                        user_blobs_parts.append(f"--blob={name}:@{path}")

    except Exception as e:
        log(f"Ошибка загрузки пользовательских блобов: {e}", "ERROR")

    return " ".join(user_blobs_parts)
