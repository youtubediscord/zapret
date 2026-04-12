"""
Модуль для применения различных модификаций к аргументам стратегий
"""

import os
from log import log


def _is_direct_source_preset_launch() -> bool:
    try:
        from strategy_menu import get_strategy_launch_method

        return (get_strategy_launch_method() or "").strip().lower() in {"direct_zapret1", "direct_zapret2"}
    except Exception:
        return False


def _has_port_443(ports_part: str) -> bool:
    """
    Проверяет, содержит ли строка с портами порт 443

    Args:
        ports_part: Строка с портами (например: "80,443" или "444-65535")

    Returns:
        True если порт 443 присутствует
    """
    for port_spec in ports_part.split(","):
        port_spec = port_spec.strip()

        if "-" in port_spec:
            # Диапазон портов (например: 80-8080, 444-65535)
            try:
                parts = port_spec.split("-", 1)
                start = int(parts[0].strip())
                end = int(parts[1].strip())
                if start <= 443 <= end:
                    return True
            except (ValueError, IndexError):
                continue
        else:
            # Отдельный порт
            try:
                if int(port_spec) == 443:
                    return True
            except ValueError:
                continue

    return False


def apply_wssize_parameter(args: list) -> list:
    """
    Применяет параметры --wssize 1:6 и --wssize-forced-cutoff=0 к аргументам стратегии если включено в настройках

    Args:
        args: Список аргументов командной строки

    Returns:
        Модифицированный список аргументов с добавленными wssize параметрами
    """
    if _is_direct_source_preset_launch():
        return args

    from strategy_menu import get_wssize_enabled

    if not get_wssize_enabled():
        return args

    new_args = []
    i = 0

    while i < len(args):
        arg = args[i]
        new_args.append(arg)

        # Ищем --filter-tcp с портом 443
        if arg.startswith("--filter-tcp="):
            ports_part = arg.split("=", 1)[1]
            has_port_443 = _has_port_443(ports_part)

            if has_port_443:
                # Копируем все аргументы этого фильтра до следующего --new или конца
                j = i + 1
                filter_args = []

                while j < len(args) and args[j] != "--new":
                    filter_args.append(args[j])
                    j += 1

                # Добавляем аргументы фильтра
                new_args.extend(filter_args)

                # Проверяем, нет ли уже параметров wssize в этом блоке
                has_wssize = any("--wssize" in arg for arg in filter_args)
                has_cutoff = any("--wssize-forced-cutoff" in arg for arg in filter_args)

                if not has_wssize:
                    # Разделяем на два отдельных аргумента
                    new_args.append("--wssize")
                    new_args.append("1:6")
                    log(f"Добавлен параметр --wssize 1:6 после {arg}", "DEBUG")

                if not has_cutoff:
                    new_args.append("--wssize-forced-cutoff=0")
                    log(f"Добавлен параметр --wssize-forced-cutoff=0 после {arg}", "DEBUG")

                # Переходим к следующему аргументу (пропускаем уже обработанные)
                i = j - 1  # -1 потому что в конце цикла будет i += 1

        i += 1

    return new_args


def ensure_list_files_exist(args: list, lists_dir: str) -> list:
    """
    Проверяет и создаёт недостающие файлы hostlist/ipset

    Если файл не существует - создаёт пустой файл с комментарием,
    чтобы winws мог запуститься.

    Args:
        args: Список аргументов командной строки
        lists_dir: Путь к директории со списками

    Returns:
        Исходный список аргументов (без изменений)
    """
    # Префиксы аргументов с путями к файлам
    file_prefixes = [
        "--hostlist=",
        "--hostlist-exclude=",
        "--ipset=",
        "--ipset-exclude=",
    ]

    created_files = []

    for arg in args:
        for prefix in file_prefixes:
            if arg.startswith(prefix):
                file_path = arg[len(prefix):]

                # Убираем @ в начале если есть (формат @filepath)
                if file_path.startswith("@"):
                    file_path = file_path[1:]

                # Если путь относительный - добавляем lists_dir
                if not os.path.isabs(file_path):
                    file_path = os.path.join(lists_dir, file_path)

                # Проверяем существование файла
                if not os.path.exists(file_path):
                    try:
                        # Создаём директорию если её нет
                        os.makedirs(os.path.dirname(file_path), exist_ok=True)

                        # Создаём пустой файл с комментарием
                        file_type = "hostlist" if "hostlist" in prefix else "ipset"
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(f"# {file_type} file - add domains/IPs here (one per line)\n")
                            f.write("# Добавьте домены или IP адреса, по одному на строку\n")

                        created_files.append(os.path.basename(file_path))
                        log(f"✅ Создан файл списка: {file_path}", "INFO")
                    except Exception as e:
                        log(f"⚠️ Не удалось создать файл {file_path}: {e}", "WARNING")

                break  # Файл обработан, переходим к следующему аргументу

    if created_files:
        log(f"✅ Созданы недостающие файлы списков: {', '.join(created_files)}", "SUCCESS")

    return args


def apply_all_filters(args: list, lists_dir: str) -> list:
    """
    Применяет все фильтры в правильном порядке

    ПОРЯДОК ВАЖЕН:
    0. Сначала создаём недостающие файлы hostlist/ipset
    1. В конце применяем wssize параметры

    Args:
        args: Исходный список аргументов
        lists_dir: Путь к директории со списками

    Returns:
        Полностью обработанный список аргументов
    """
    # 0. Создаём недостающие файлы списков
    args = ensure_list_files_exist(args, lists_dir)

    # 1. Применяем wssize параметры (если включено)
    args = apply_wssize_parameter(args)

    return args
