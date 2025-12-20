# utils/hostlists_manager.py
"""
Менеджер Hostlist файлов.
- other.txt - базовые домены (YouTube, Discord и т.д.)
- other2.txt - пользовательские домены (управляется через GUI)
"""

import os
from datetime import datetime
from log import log
from config import OTHER_PATH, OTHER2_PATH
from .BASE_DOMAINS_TEXT import BASE_DOMAINS_TEXT


def get_base_domains() -> list[str]:
    """Возвращает список базовых доменов"""
    try:
        domains = [
            domain.strip() 
            for domain in BASE_DOMAINS_TEXT.strip().split('\n') 
            if domain.strip() and not domain.strip().startswith('#')
        ]
        
        if len(domains) < 5:
            log(f"⚠ WARNING: Мало доменов в BASE_DOMAINS_TEXT: {len(domains)}", "WARNING")
            return []
        
        return domains
        
    except Exception as e:
        log(f"❌ Ошибка в get_base_domains: {e}", "ERROR")
        return []


def ensure_hostlists_exist():
    """Проверяет существование файлов хостлистов и создает их если нужно"""
    try:
        os.makedirs(os.path.dirname(OTHER_PATH), exist_ok=True)
        
        # Создаём other.txt если нет или пустой
        if not os.path.exists(OTHER_PATH) or os.path.getsize(OTHER_PATH) == 0:
            log("Создание other.txt...", "INFO")
            _create_other()
        
        # Создаём other2.txt если нет (пустой, для пользователя)
        if not os.path.exists(OTHER2_PATH):
            log("Создание other2.txt...", "INFO")
            _create_other2()
        
        return True
        
    except Exception as e:
        log(f"Ошибка создания файлов хостлистов: {e}", "❌ ERROR")
        return False


def startup_hostlists_check():
    """Проверка хостлистов при запуске программы"""
    try:
        log("=== Проверка хостлистов при запуске ===", "🔧 HOSTLISTS")
        
        os.makedirs(os.path.dirname(OTHER_PATH), exist_ok=True)
        
        # Проверяем other.txt
        if not os.path.exists(OTHER_PATH):
            log("Создаем other.txt", "WARNING")
            _create_other()
        else:
            # Проверяем что файл не пустой
            with open(OTHER_PATH, 'r', encoding='utf-8') as f:
                lines = [l.strip() for l in f if l.strip() and not l.strip().startswith('#')]
            
            if not lines:
                log("other.txt пуст, пересоздаем", "WARNING")
                _create_other()
            else:
                log(f"other.txt: {len(lines)} доменов", "INFO")
        
        # Проверяем other2.txt (НЕ перезаписываем если есть!)
        if not os.path.exists(OTHER2_PATH):
            log("Создаем other2.txt", "WARNING")
            _create_other2()
        else:
            log(f"other2.txt: {os.path.getsize(OTHER2_PATH)} байт", "INFO")
        
        return True
        
    except Exception as e:
        log(f"Ошибка при проверке хостлистов: {e}", "❌ ERROR")
        return False


def _create_other():
    """Создаёт other.txt с базовыми доменами"""
    try:
        base_domains = get_base_domains()
        
        if not base_domains:
            # Аварийный минимум
            base_domains = ['youtube.com', 'googlevideo.com', 'discord.com', 'discord.gg']
            log("Используем аварийный минимум доменов", "WARNING")
        
        with open(OTHER_PATH, 'w', encoding='utf-8') as f:
            for domain in sorted(set(base_domains)):
                f.write(f"{domain}\n")
        
        log(f"✅ Создан other.txt ({len(base_domains)} доменов)", "SUCCESS")
    except Exception as e:
        log(f"❌ Ошибка создания other.txt: {e}", "ERROR")


def _create_other2():
    """Создаёт пустой other2.txt для пользователя"""
    try:
        with open(OTHER2_PATH, 'w', encoding='utf-8') as f:
            f.write("# Пользовательские домены\n")
            f.write("# Этот файл не перезаписывается обновлениями\n")
            f.write(f"# Создано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        log(f"✅ Создан other2.txt", "SUCCESS")
    except Exception as e:
        log(f"❌ Ошибка создания other2.txt: {e}", "ERROR")
