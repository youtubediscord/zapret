# utils/ipsets_manager.py
"""
Менеджер IPset файлов.
- ipset-base.txt - базовые IP (Cloudflare DNS и т.д.)
- my-ipset.txt - пользовательские IP (управляется через GUI)
"""

import os
from datetime import datetime
from log import log
from config import LISTS_FOLDER

# Пути к файлам
IPSET_ALL_PATH = os.path.join(LISTS_FOLDER, "ipset-base.txt")
MY_IPSET_PATH = os.path.join(LISTS_FOLDER, "my-ipset.txt")

# Базовые IP диапазоны (всегда включены в ipset-base.txt)
BASE_IPS_TEXT = """
# Cloudflare DNS
1.1.1.1
1.1.1.2
1.1.1.3
1.0.0.1
1.0.0.2
1.0.0.3
"""


def get_base_ips() -> list[str]:
    """Возвращает список базовых IP"""
    ips = []
    for line in BASE_IPS_TEXT.strip().split('\n'):
        line = line.strip()
        if line and not line.startswith('#'):
            ips.append(line)
    return ips


def ensure_ipsets_exist():
    """Проверяет существование файлов IPsets и создает их если нужно"""
    try:
        os.makedirs(LISTS_FOLDER, exist_ok=True)
        
        # Создаём ipset-base.txt если нет
        if not os.path.exists(IPSET_ALL_PATH):
            log("Создание ipset-base.txt...", "INFO")
            _create_ipset_base()
        
        # Создаём my-ipset.txt если нет (пустой, для пользователя)
        if not os.path.exists(MY_IPSET_PATH):
            log("Создание my-ipset.txt...", "INFO")
            _create_my_ipset()
        
        return True
        
    except Exception as e:
        log(f"Ошибка создания файлов IPsets: {e}", "❌ ERROR")
        return False


def startup_ipsets_check():
    """Проверка IPsets при запуске программы"""
    try:
        log("=== Проверка IPsets при запуске ===", "🔧 IPSETS")
        
        os.makedirs(LISTS_FOLDER, exist_ok=True)
        
        # Проверяем/создаём ipset-base.txt
        if not os.path.exists(IPSET_ALL_PATH) or os.path.getsize(IPSET_ALL_PATH) < 50:
            log("Создаем/обновляем ipset-base.txt", "WARNING")
            _create_ipset_base()
        else:
            log(f"ipset-base.txt: {os.path.getsize(IPSET_ALL_PATH)} байт", "INFO")
        
        # Проверяем/создаём my-ipset.txt (НЕ перезаписываем если есть!)
        if not os.path.exists(MY_IPSET_PATH):
            log("Создаем my-ipset.txt", "WARNING")
            _create_my_ipset()
        else:
            log(f"my-ipset.txt: {os.path.getsize(MY_IPSET_PATH)} байт", "INFO")
        
        return True
        
    except Exception as e:
        log(f"❌ Ошибка при проверке IPsets: {e}", "ERROR")
        return False


def _create_ipset_base():
    """Создаёт ipset-base.txt с базовыми IP"""
    try:
        with open(IPSET_ALL_PATH, 'w', encoding='utf-8') as f:
            f.write("# Базовые IP диапазоны\n")
            f.write(f"# Создано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            for ip in get_base_ips():
                f.write(f"{ip}\n")
        
        log(f"✅ Создан ipset-base.txt ({os.path.getsize(IPSET_ALL_PATH)} байт)", "SUCCESS")
    except Exception as e:
        log(f"❌ Ошибка создания ipset-base.txt: {e}", "ERROR")


def _create_my_ipset():
    """Создаёт пустой my-ipset.txt для пользователя"""
    try:
        with open(MY_IPSET_PATH, 'w', encoding='utf-8') as f:
            f.write("# Пользовательские IP-адреса и подсети\n")
            f.write("# Этот файл не перезаписывается обновлениями\n")
            f.write(f"# Создано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        log(f"✅ Создан my-ipset.txt", "SUCCESS")
    except Exception as e:
        log(f"❌ Ошибка создания my-ipset.txt: {e}", "ERROR")
