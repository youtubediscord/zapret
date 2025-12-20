"""
Профилировщик для определения узких мест
"""

import time
from functools import wraps
from log import log


class PerformanceProfiler:
    """Простой профилировщик производительности"""
    
    def __init__(self, name):
        self.name = name
        self.start_time = None
        self.checkpoints = []
        
    def start(self):
        """Начинает профилирование"""
        self.start_time = time.perf_counter()
        self.checkpoints = []
        log(f"[PROFILE] {self.name} - START", "DEBUG")
        
    def checkpoint(self, label):
        """Добавляет контрольную точку"""
        if self.start_time is None:
            return
            
        elapsed = (time.perf_counter() - self.start_time) * 1000  # в миллисекундах
        self.checkpoints.append((label, elapsed))
        log(f"[PROFILE] {self.name} - {label}: {elapsed:.2f}ms", "DEBUG")
        
    def end(self):
        """Завершает профилирование"""
        if self.start_time is None:
            return
            
        total = (time.perf_counter() - self.start_time) * 1000
        log(f"[PROFILE] {self.name} - TOTAL: {total:.2f}ms", "INFO")
        
        # Показываем детализацию
        if self.checkpoints:
            log(f"[PROFILE] {self.name} - Breakdown:", "DEBUG")
            prev_time = 0
            for label, elapsed in self.checkpoints:
                delta = elapsed - prev_time
                log(f"  • {label}: {delta:.2f}ms (cumulative: {elapsed:.2f}ms)", "DEBUG")
                prev_time = elapsed
                
        self.start_time = None
        self.checkpoints = []


def profile_function(func):
    """Декоратор для профилирования функций"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        profiler = PerformanceProfiler(f"{func.__name__}")
        profiler.start()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            profiler.end()
    return wrapper