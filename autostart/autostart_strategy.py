from pathlib import Path
import sys, subprocess, traceback
from log import log
from typing import Callable, Optional
from utils import run_hidden, get_system_exe  # обёртка для subprocess.run
from .registry_check import set_autostart_enabled


def _resolve_bat_folder(bat_folder: str) -> Path:
    """Возвращает абсолютный путь к bat, учитывая PyInstaller one-file."""
    p = Path(bat_folder)
    if p.is_absolute():
        return p

    # 1) <cwd>\bat
    cwd_variant = (Path.cwd() / p).resolve()
    if cwd_variant.exists():
        return cwd_variant

    # 2) рядом с exe / _MEIPASS
    base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    exe_variant = (base / p).resolve()
    if exe_variant.exists():
        return exe_variant

    return p.resolve()


def _find_bat_by_name(bat_dir: Path, strategy_name: str) -> Optional[Path]:
    """
    Находит .bat файл по имени стратегии.
    Сначала проверяет REM NAME: в файлах, затем пробует имя файла.
    """
    import re
    
    if not bat_dir.is_dir():
        return None
    
    name_pattern = re.compile(r'^REM\s+NAME:\s*(.+)$', re.IGNORECASE)
    
    # Сначала ищем по REM NAME:
    for bat_file in bat_dir.glob('*.bat'):
        try:
            with open(bat_file, 'r', encoding='utf-8-sig', errors='ignore') as f:
                for i, line in enumerate(f):
                    if i > 30:  # Читаем только первые 30 строк
                        break
                    line = line.strip()
                    match = name_pattern.match(line)
                    if match and match.group(1).strip() == strategy_name:
                        return bat_file
        except Exception:
            continue
    
    # Пробуем прямое соответствие имени файла
    # strategy_name -> strategy_name.bat
    direct_path = bat_dir / f"{strategy_name}.bat"
    if direct_path.is_file():
        return direct_path
    
    # Пробуем без пробелов и с подчёркиваниями
    # "My Strategy" -> "my_strategy.bat"
    normalized = strategy_name.lower().replace(' ', '_')
    for bat_file in bat_dir.glob('*.bat'):
        if bat_file.stem.lower().replace(' ', '_') == normalized:
            return bat_file
    
    return None


def setup_autostart_for_strategy(
    selected_mode: str,
    bat_folder: str,
    index_path: str | None = None,  # Устарел, игнорируется
    ui_error_cb: Optional[Callable[[str], None]] = None,
) -> bool:
    """
    Создаёт задачу в планировщике на BAT-файл выбранной стратегии.

    Args:
        selected_mode: отображаемое имя стратегии (поле "name" из REM NAME: в .bat)
        bat_folder:    каталог с *.bat файлами
        index_path:    устарел, игнорируется

    Returns:
        True  – задача создана;
        False – возникла ошибка (подробности в log()).
    """
    try:
        # ----------- ищем BAT ------------------------------------------------
        bat_dir = _resolve_bat_folder(bat_folder)

        if not bat_dir.is_dir():
            log(f"Папка стратегий не найдена: {bat_dir}", "❌ ERROR")
            return False

        # Ищем .bat файл по имени стратегии
        bat_path = _find_bat_by_name(bat_dir, selected_mode)
        
        if not bat_path or not bat_path.is_file():
            log(f"Стратегия «{selected_mode}» не найдена в {bat_dir}", "❌ ERROR")
            return False

        log(f"Найден .bat файл для стратегии '{selected_mode}': {bat_path}", "DEBUG")

        # ----------- создаём/обновляем задачу Планировщика -------------------
        ok = _create_task_scheduler_job(
                task_name="ZapretStrategy",
                bat_path = bat_path,
                ui_error_cb = ui_error_cb
        )
        
        if ok:
            # Обновляем статус автозапуска в реестре
            set_autostart_enabled(True, "task")
        
        return ok

    except Exception as exc:
        log(f"setup_autostart_for_strategy: {exc}", "❌ ERROR")
        return False

def _create_task_scheduler_job(
    task_name: str,
    bat_path:  Path,
    ui_error_cb: Optional[Callable[[str], None]] = None,
) -> bool:
    """
    Создаёт (или перезаписывает) задачу в Планировщике Windows.

    Args:
        task_name : Имя задачи (напр. "ZapretStrategy")
        bat_path  : Полный путь к .bat
        ui_error_cb : callback для вывода ошибки в GUI (QMessageBox/label)

    Returns:
        True  – задача успешно создана/обновлена
        False – ошибка (уже залогирована, ui_error_cb вызван)
    """
    cmd = [
        "schtasks", "/Create",
        "/TN", task_name,
        "/TR", f'"{bat_path}"',
        "/SC", "ONLOGON",        # При входе в систему
        "/RU", "SYSTEM",
        "/RL", "HIGHEST",        # Запуск с повышенными правами
        "/IT",                   # Интерактивное выполнение (важно для ONLOGON)
        "/F"                     # перезаписать, если задача уже существует
    ]

    try:
        res = run_hidden(
            cmd,
            capture_output=True,
            text=True,
            encoding="cp866",  # Используем cp866 для совместимости с русским языком
        )
        if res.returncode == 0:
            log(f'Задача "{task_name}" создана/обновлена', "INFO")
            return True

        # Ошибка — готовим информативное сообщение
        err_msg = (f'Не удалось создать задачу автозапуска "{task_name}". '
                   f'Код {res.returncode}.\n{res.stderr.strip()}')
        log(err_msg, "❌ ERROR")
        if ui_error_cb:
            ui_error_cb(err_msg)
        return False

    except FileNotFoundError:
        # schtasks отсутствует (теоретически возможно в WinPE)
        err_msg = "Команда schtasks не найдена – автозапуск невозможен"
        log(err_msg, "❌ ERROR")
        if ui_error_cb:
            ui_error_cb(err_msg)
        return False
    except UnicodeDecodeError:
        try:
            res = run_hidden(
                cmd,
                capture_output=True,
                text=True,
                encoding="cp866",
                errors="ignore"
            )
            if res.returncode == 0:
                log(f'Задача "{task_name}" создана/обновлена (триггер: при входе в систему)', "INFO")
                return True
            else:
                err_msg = (f'Не удалось создать задачу автозапуска "{task_name}". '
                          f'Код {res.returncode}.\n{res.stderr.strip()}')
                log(err_msg, "❌ ERROR")
                if ui_error_cb:
                    ui_error_cb(err_msg)
                return False
        except Exception as fallback_exc:
            err_msg = f"Ошибка кодировки при создании задачи: {fallback_exc}"
            log(err_msg, "❌ ERROR")
            if ui_error_cb:
                ui_error_cb("Ошибка кодировки; подробности в логе.")
            return False
    except Exception as exc:
        err_msg = f"_create_task_scheduler_job: {exc}\n{traceback.format_exc()}"
        log(err_msg, "❌ ERROR")
        if ui_error_cb:
            ui_error_cb("Ошибка создания задачи автозапуска; подробности в логе.")
        return False


def remove_task_scheduler_job(task_name: str = "ZapretStrategy") -> bool:
    """
    Удаляет задачу из планировщика Windows
    
    Args:
        task_name: Имя задачи для удаления
        
    Returns:
        True если задача удалена, False если её не было или ошибка
    """
    try:
        schtasks = get_system_exe("schtasks.exe")
        # Проверяем существование задачи
        check_cmd = [schtasks, "/Query", "/TN", task_name]
        check_res = run_hidden(
            check_cmd,
            capture_output=True,
            text=True,
            encoding="cp866",
            errors="ignore"
        )

        if check_res.returncode != 0:
            # Задачи нет
            return False

        # Удаляем задачу
        delete_cmd = [schtasks, "/Delete", "/TN", task_name, "/F"]
        delete_res = run_hidden(
            delete_cmd,
            capture_output=True,
            text=True,
            encoding="cp866",
            errors="ignore"
        )
        
        if delete_res.returncode == 0:
            log(f'Задача "{task_name}" удалена', "INFO")
            
            # Проверяем остались ли другие методы автозапуска
            from .checker import CheckerManager
            checker = CheckerManager(None)
            if not checker.check_autostart_exists_full():
                # Если ничего не осталось - отключаем в реестре
                set_autostart_enabled(False)
            
            return True
        else:
            log(f"Не удалось удалить задачу {task_name}: {delete_res.stderr}", "❌ ERROR")
            return False
            
    except Exception as e:
        log(f"Ошибка удаления задачи планировщика: {e}", "❌ ERROR")
        return False
