"""
updater/rate_limiter.py

────────────────────────────────────────────────────────────────

Rate limiting для проверки обновлений - защита от спама

────────────────────────────────────────────────────────────────
"""

import os
import json
import time
from typing import Optional
from config import LOGS_FOLDER
from log import log

# Файл для хранения времени последней проверки
RATE_LIMIT_FILE = os.path.join(LOGS_FOLDER, '.update_rate_limit.json')

# Минимальный интервал между РУЧНЫМИ проверками (30 минут)
MIN_MANUAL_CHECK_INTERVAL = 1800  # 30 минут в секундах

# Минимальный интервал между АВТОМАТИЧЕСКИМИ проверками (6 часов)
MIN_AUTO_CHECK_INTERVAL = 21600  # 6 часов в секундах


class UpdateRateLimiter:
    """Ограничитель частоты проверок обновлений"""
    
    @staticmethod
    def _load_state() -> dict:
        """Загружает состояние из файла"""
        try:
            if os.path.exists(RATE_LIMIT_FILE):
                with open(RATE_LIMIT_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            log(f"⚠️ Ошибка загрузки rate limit: {e}", "⏱️ RATE")
        return {}
    
    @staticmethod
    def _save_state(state: dict):
        """Сохраняет состояние в файл"""
        try:
            with open(RATE_LIMIT_FILE, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            log(f"⚠️ Ошибка сохранения rate limit: {e}", "⏱️ RATE")
    
    @staticmethod
    def can_check_update(is_auto: bool = False) -> tuple[bool, Optional[str]]:
        """
        Проверяет можно ли выполнить проверку обновлений
        
        Args:
            is_auto: True для автоматической проверки, False для ручной
            
        Returns:
            (разрешено, сообщение_об_ошибке)
        """
        state = UpdateRateLimiter._load_state()
        current_time = time.time()
        
        check_type = "auto" if is_auto else "manual"
        last_check_key = f"last_{check_type}_check"
        last_check_time = state.get(last_check_key, 0)
        
        # Определяем минимальный интервал
        min_interval = MIN_AUTO_CHECK_INTERVAL if is_auto else MIN_MANUAL_CHECK_INTERVAL
        
        time_since_last = current_time - last_check_time
        
        if time_since_last < min_interval:
            # Сколько осталось ждать
            remaining = min_interval - time_since_last
            remaining_minutes = int(remaining / 60)
            
            check_type_ru = "автоматическая проверка" if is_auto else "проверка"
            
            if remaining_minutes > 60:
                hours = remaining_minutes / 60
                msg = f"⏱️ Следующая {check_type_ru} возможна через {hours:.1f} ч"
            else:
                msg = f"⏱️ Следующая {check_type_ru} возможна через {remaining_minutes} мин"
            
            log(
                f"❌ Rate limit: {check_type} проверка заблокирована "
                f"(прошло {int(time_since_last)}с, нужно {min_interval}с)",
                "⏱️ RATE"
            )
            
            return False, msg
        
        log(f"✅ Rate limit: {check_type} проверка разрешена", "⏱️ RATE")
        return True, None
    
    @staticmethod
    def record_check(is_auto: bool = False):
        """Записывает факт выполненной проверки"""
        state = UpdateRateLimiter._load_state()
        current_time = time.time()
        
        check_type = "auto" if is_auto else "manual"
        last_check_key = f"last_{check_type}_check"
        
        state[last_check_key] = current_time
        state[f"{check_type}_check_count"] = state.get(f"{check_type}_check_count", 0) + 1
        
        UpdateRateLimiter._save_state(state)
        
        log(
            f"📝 Записана {check_type} проверка в {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time))}",
            "⏱️ RATE"
        )
    
    @staticmethod
    def get_stats() -> dict:
        """Возвращает статистику проверок"""
        state = UpdateRateLimiter._load_state()
        current_time = time.time()
        
        stats = {}
        
        for check_type in ["auto", "manual"]:
            last_check = state.get(f"last_{check_type}_check", 0)
            check_count = state.get(f"{check_type}_check_count", 0)
            
            if last_check > 0:
                time_since = current_time - last_check
                last_check_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_check))
            else:
                time_since = None
                last_check_str = "никогда"
            
            stats[check_type] = {
                "last_check": last_check_str,
                "time_since_seconds": time_since,
                "total_checks": check_count
            }
        
        return stats
    
    @staticmethod
    def reset():
        """Сбрасывает все ограничения (для отладки)"""
        try:
            if os.path.exists(RATE_LIMIT_FILE):
                os.remove(RATE_LIMIT_FILE)
            log("🔄 Rate limit сброшен", "⏱️ RATE")
        except Exception as e:
            log(f"⚠️ Ошибка сброса rate limit: {e}", "⏱️ RATE")
