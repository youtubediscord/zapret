# dpi_controller.py
"""
Контроллер для управления DPI - содержит всю логику запуска и остановки
"""
import psutil
from PyQt6.QtCore import QThread, QObject, pyqtSignal

from config import get_strategy_launch_method
from log import log


class DPIStartWorker(QObject):
    """Worker для асинхронного запуска DPI"""
    finished = pyqtSignal(bool, str)  # success, error_message
    progress = pyqtSignal(str)        # status_message
    
    def __init__(self, app_instance, selected_mode, launch_method):
        super().__init__()
        self.app_instance = app_instance
        self.selected_mode = selected_mode
        self.launch_method = launch_method
        self.dpi_starter = app_instance.dpi_starter
    
    def run(self):
        try:
            self.progress.emit("Подготовка к запуску...")
            
            # Проверяем, не запущен ли уже процесс
            if self.dpi_starter.check_process_running_wmi(silent=True):
                self.progress.emit("Останавливаем предыдущий процесс...")
                # Останавливаем через соответствующий метод
                if self.launch_method == "direct":
                    from strategy_menu.strategy_runner import get_strategy_runner
                    runner = get_strategy_runner(self.app_instance.dpi_starter.winws_exe)
                    runner.stop()
                else:
                    from dpi.stop import stop_dpi
                    stop_dpi(self.app_instance)
            
            self.progress.emit("Запуск DPI...")
            
            # Выбираем метод запуска
            if self.launch_method == "direct":
                success = self._start_direct()
            else:
                success = self._start_bat()
            
            if success:
                self.progress.emit("DPI успешно запущен")
                self.finished.emit(True, "")
            else:
                self.finished.emit(False, "Не удалось запустить DPI")
                
        except Exception as e:
            error_msg = f"Ошибка запуска DPI: {str(e)}"
            log(error_msg, "❌ ERROR")
            self.finished.emit(False, error_msg)

    def _start_direct(self):
        """Запуск через прямой метод (StrategyRunner)"""
        try:
            from strategy_menu.strategy_runner import get_strategy_runner
            
            # Получаем runner
            runner = get_strategy_runner(self.app_instance.dpi_starter.winws_exe)
            
            mode_param = self.selected_mode
            
            # Обработка комбинированных стратегий
            if isinstance(mode_param, dict) and mode_param.get('is_combined'):
                strategy_name = mode_param.get('name', 'Комбинированная стратегия')
                args_str = mode_param.get('args', '')
                
                log(f"Запуск комбинированной стратегии: {strategy_name}", "INFO")
                
                if not args_str:
                    log("Отсутствуют аргументы для комбинированной стратегии", "❌ ERROR")
                    return False
                
                # Парсим аргументы
                import shlex
                try:
                    custom_args = shlex.split(args_str)
                    log(f"Аргументы комбинированной стратегии ({len(custom_args)} шт.)", "DEBUG")
                    
                    # Запускаем стратегию напрямую через runner
                    success = runner.start_strategy_custom(custom_args, strategy_name)
                    
                    if success:
                        log("Комбинированная стратегия успешно запущена", "✅ SUCCESS")
                        return True
                    else:
                        log("Не удалось запустить комбинированную стратегию", "❌ ERROR")
                        return False
                        
                except Exception as parse_error:
                    log(f"Ошибка парсинга аргументов: {parse_error}", "❌ ERROR")
                    return False
            
            # Для Direct режима поддерживаются только комбинированные стратегии
            else:
                log(f"Direct режим поддерживает только комбинированные стратегии, получен: {type(mode_param)}", "❌ ERROR")
                return False
                
        except Exception as e:
            log(f"Ошибка прямого запуска: {e}", "❌ ERROR")
            return False

    def _start_bat(self):
        """Запуск через старый метод (.bat файлы)"""
        try:
            # Нормализуем selected_mode
            mode_param = self.selected_mode
            
            if isinstance(mode_param, dict):
                mode_param = mode_param.get('name') or 'default'
            elif mode_param is None:
                mode_param = 'default'
            
            log(f"Запуск BAT стратегии: {mode_param}", "DEBUG")
            
            # Используем BatDPIStart для BAT режима
            result = self.app_instance.dpi_starter.start_dpi(selected_mode=mode_param)
            
            # Добавляем дополнительную проверку
            if result:
                import time
                time.sleep(1)  # Даем процессу время на инициализацию
                
                # Проверяем, действительно ли процесс запущен
                if self.app_instance.dpi_starter.check_process_running_wmi(silent=True):
                    log("Процесс winws.exe успешно запущен и работает", "✅ SUCCESS")
                    return True
                else:
                    log("Процесс winws.exe завершился после запуска", "❌ ERROR")
                    # Пытаемся получить код ошибки
                    try:
                        import subprocess
                        # Проверяем последние события Windows
                        result = subprocess.run(
                            ['wevtutil', 'qe', 'Application', '/c:5', '/rd:true', '/f:text'],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.stdout and 'winws' in result.stdout.lower():
                            log(f"События Windows: {result.stdout[:500]}", "DEBUG")
                    except:
                        pass
                    return False
            
            return result
            
        except Exception as e:
            log(f"Ошибка запуска через .bat: {e}", "❌ ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")
            return False

class DPIStopWorker(QObject):
    """Worker для асинхронной остановки DPI"""
    finished = pyqtSignal(bool, str)  # success, error_message
    progress = pyqtSignal(str)        # status_message
    
    def __init__(self, app_instance, launch_method):
        super().__init__()
        self.app_instance = app_instance
        self.launch_method = launch_method

    def _kill_process_by_name(name: str):
        killed = []
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'].lower() == name.lower():
                try:
                    proc.terminate()  # soft kill
                    proc.wait(timeout=3)
                    killed.append(proc.info['pid'])
                except psutil.NoSuchProcess:
                    pass
                except psutil.TimeoutExpired:
                    proc.kill()  # if not soft killed - kill it to death hehe
                    killed.append(proc.info['pid'])
        return killed

    def run(self):
        try:
            self.progress.emit("Остановка DPI...")
            
            # Проверяем, запущен ли процесс
            if not self.app_instance.dpi_starter.check_process_running_wmi(silent=True):
                self.progress.emit("DPI уже остановлен")
                self.finished.emit(True, "DPI уже был остановлен")
                return
            
            self.progress.emit("Завершение процессов...")
            
            # Выбираем метод остановки
            if self.launch_method == "direct":
                success = self._stop_direct()
            else:
                success = self._stop_bat()
            
            if success:
                self.progress.emit("DPI успешно остановлен")
                self.finished.emit(True, "")
            else:
                self.finished.emit(False, "Не удалось полностью остановить процесс")
                
        except Exception as e:
            error_msg = f"Ошибка остановки DPI: {str(e)}"
            log(error_msg, "❌ ERROR")
            self.finished.emit(False, error_msg)
    
    def _stop_direct(self):
        """Остановка через новый метод"""
        try:
            from strategy_menu.strategy_runner import get_strategy_runner
            
            runner = get_strategy_runner(self.app_instance.dpi_starter.winws_exe)
            success = runner.stop()
            
            # Дополнительно убиваем все процессы winws.exe
            if not success or self.app_instance.dpi_starter.check_process_running_wmi(silent=True):
                killed_pids = self._kill_process_by_name("winws.exe")
                if killed_pids:
                    pass # add any debug logs if needed
                else:
                    pass # add any debug logs if needed
            
            # Проверяем результат
            return not self.app_instance.dpi_starter.check_process_running_wmi(silent=True)
            
        except Exception as e:
            log(f"Ошибка прямой остановки: {e}", "❌ ERROR")
            return False
    
    def _stop_bat(self):
        """Остановка через старый метод"""
        try:
            from dpi.stop import stop_dpi
            stop_dpi(self.app_instance)
            
            # Проверяем результат
            return not self.app_instance.dpi_starter.check_process_running_wmi(silent=True)
            
        except Exception as e:
            log(f"Ошибка остановки через .bat: {e}", "❌ ERROR")
            return False


class StopAndExitWorker(QObject):
    """Worker для остановки DPI и выхода из программы"""
    finished = pyqtSignal()
    progress = pyqtSignal(str)
    
    def __init__(self, app_instance):
        super().__init__()
        self.app_instance = app_instance
        self.launch_method = get_strategy_launch_method()
    
    def run(self):
        try:
            self.progress.emit("Остановка DPI перед закрытием...")
            
            # Выбираем метод остановки
            if self.launch_method == "direct":
                from strategy_menu.strategy_runner import get_strategy_runner
                runner = get_strategy_runner(self.app_instance.dpi_starter.winws_exe)
                runner.stop()
                
                # Дополнительная очистка
                from dpi.stop import stop_dpi_direct
                stop_dpi_direct(self.app_instance)
            else:
                from dpi.stop import stop_dpi
                stop_dpi(self.app_instance)
            
            self.progress.emit("Завершение работы...")
            self.finished.emit()
            
        except Exception as e:
            log(f"Ошибка при остановке перед закрытием: {e}", "❌ ERROR")
            self.finished.emit()


class DPIController:
    """Основной контроллер для управления DPI"""
    
    def __init__(self, app_instance):
        self.app = app_instance
        self._dpi_start_thread = None
        self._dpi_stop_thread = None
        self._stop_exit_thread = None

    def start_dpi_async(self, selected_mode=None):
        """Асинхронно запускает DPI без блокировки UI"""
        # Проверка на уже запущенный поток
        try:
            if self._dpi_start_thread and self._dpi_start_thread.isRunning():
                log("Запуск DPI уже выполняется", "DEBUG")
                return
        except RuntimeError:
            self._dpi_start_thread = None
        
        # Проверяем выбранный метод запуска
        launch_method = get_strategy_launch_method()
        log(f"Используется метод запуска: {launch_method}", "INFO")
        
        # ✅ ИСПРАВЛЕНИЕ: Если стратегия не выбрана, берем из реестра
        if selected_mode is None or selected_mode == 'default':
            if launch_method == "direct":
                # Для Direct режима берем сохраненные выборы из реестра
                from config import get_direct_strategy_selections
                from strategy_menu.strategy_lists_separated import combine_strategies
                
                # Получаем сохраненные выборы категорий из реестра
                saved_selections = get_direct_strategy_selections()
                log(f"Загружены сохраненные выборы из реестра: {saved_selections}", "DEBUG")
                
                # Создаем комбинированную стратегию на основе сохраненных выборов
                combined = combine_strategies(
                    saved_selections.get('youtube'),
                    saved_selections.get('discord'),
                    saved_selections.get('discord_voice'),
                    saved_selections.get('other')
                )
                
                selected_mode = {
                    'is_combined': True,
                    'name': combined.get('description', 'Сохраненная стратегия'),
                    'args': combined['args'],
                    'selections': saved_selections
                }
                log(f"Используется сохраненная комбинированная стратегия: {selected_mode['name']}", "INFO")
                
            else:  # BAT режим
                # Для BAT режима берем последнюю выбранную стратегию из реестра
                from config import get_last_strategy
                
                last_strategy_name = get_last_strategy()
                log(f"Последняя использованная стратегия из реестра: {last_strategy_name}", "DEBUG")
                
                if last_strategy_name and hasattr(self.app, 'strategy_manager'):
                    try:
                        strategies = self.app.strategy_manager.get_local_strategies_only()
                        
                        # Ищем стратегию по имени
                        found_strategy = None
                        for sid, sinfo in strategies.items():
                            if sinfo.get('name') == last_strategy_name:
                                found_strategy = sinfo
                                break
                        
                        if found_strategy:
                            selected_mode = found_strategy
                            log(f"Используется сохраненная стратегия: {found_strategy.get('name')}", "INFO")
                        else:
                            # Если сохраненная стратегия не найдена, ищем рекомендуемую
                            log(f"Стратегия '{last_strategy_name}' не найдена, ищем рекомендуемую", "⚠ WARNING")
                            
                            # Ищем рекомендуемую стратегию
                            for sid, sinfo in strategies.items():
                                if sinfo.get('label') == 'recommended':
                                    selected_mode = sinfo
                                    log(f"Используется рекомендуемая стратегия: {sinfo.get('name')}", "INFO")
                                    break
                            
                            # Если не нашли рекомендуемую, берем первую
                            if not selected_mode and strategies:
                                selected_mode = next(iter(strategies.values()))
                                log(f"Используется первая доступная стратегия: {selected_mode.get('name')}", "INFO")
                            
                            if not selected_mode:
                                log("Нет доступных стратегий в index.json", "❌ ERROR")
                                self.app.set_status("❌ Нет доступных стратегий")
                                return
                                
                    except Exception as e:
                        log(f"Ошибка получения стратегии из реестра: {e}", "❌ ERROR")
                        self.app.set_status(f"❌ Ошибка: {e}")
                        return
                else:
                    # Если в реестре ничего нет, ищем рекомендуемую
                    if hasattr(self.app, 'strategy_manager'):
                        try:
                            strategies = self.app.strategy_manager.get_local_strategies_only()
                            
                            # Ищем рекомендуемую стратегию
                            for sid, sinfo in strategies.items():
                                if sinfo.get('label') == 'recommended':
                                    selected_mode = sinfo
                                    log(f"Используется рекомендуемая стратегия: {sinfo.get('name')}", "INFO")
                                    break
                            
                            # Если не нашли рекомендуемую, берем первую
                            if not selected_mode and strategies:
                                selected_mode = next(iter(strategies.values()))
                                log(f"Используется первая доступная стратегия: {selected_mode.get('name')}", "INFO")
                            
                            if not selected_mode:
                                log("Нет доступных стратегий", "❌ ERROR")
                                self.app.set_status("❌ Нет доступных стратегий")
                                return
                                
                        except Exception as e:
                            log(f"Ошибка получения стратегий: {e}", "❌ ERROR")
                            self.app.set_status(f"❌ Ошибка: {e}")
                            return
                    else:
                        log("strategy_manager недоступен", "❌ ERROR")
                        self.app.set_status("❌ Менеджер стратегий недоступен")
                        return
        
        # ✅ ОБРАБОТКА всех типов стратегий (остальной код без изменений)
        mode_name = "Неизвестная стратегия"
        
        if isinstance(selected_mode, dict) and selected_mode.get('is_combined'):
            # Комбинированная стратегия
            mode_name = selected_mode.get('name', 'Комбинированная стратегия')
            log(f"Обработка комбинированной стратегии: {mode_name}", "DEBUG")
            
            # Сохраняем выборы в реестр для будущего использования
            if 'selections' in selected_mode:
                from config import set_direct_strategy_selections
                selections = selected_mode['selections']
                set_direct_strategy_selections(selections)
                log(f"Выбранные стратегии - YouTube: {selections.get('youtube')}, "
                    f"Discord: {selections.get('discord')}, "
                    f"Discord Voice: {selections.get('discord_voice')}, "
                    f"Остальные: {selections.get('other')}", "DEBUG")
            
        elif isinstance(selected_mode, tuple) and len(selected_mode) == 2:
            # Встроенная стратегия (ID, название)
            strategy_id, strategy_name = selected_mode
            mode_name = strategy_name
            log(f"Обработка встроенной стратегии: {strategy_name} (ID: {strategy_id})", "DEBUG")
            
        elif isinstance(selected_mode, dict):
            # BAT стратегия
            mode_name = selected_mode.get('name', str(selected_mode))
            log(f"Обработка BAT стратегии: {mode_name}", "DEBUG")
            
            # Сохраняем имя стратегии в реестр для будущего использования
            from config import set_last_strategy
            set_last_strategy(mode_name)
            
        elif isinstance(selected_mode, str):
            # Строковое название
            mode_name = selected_mode
            log(f"Обработка стратегии по имени: {mode_name}", "DEBUG")
            
            # Сохраняем имя стратегии в реестр
            from config import set_last_strategy
            set_last_strategy(mode_name)
        
        # Показываем состояние запуска
        method_name = "прямой" if launch_method == "direct" else "классический"
        self.app.set_status(f"🚀 Запуск DPI ({method_name} метод): {mode_name}")
        
        # Блокируем кнопки во время операции
        if hasattr(self.app, 'start_btn'):
            self.app.start_btn.setEnabled(False)
        if hasattr(self.app, 'stop_btn'):
            self.app.stop_btn.setEnabled(False)
        
        # Создаем поток и worker
        self._dpi_start_thread = QThread()
        self._dpi_start_worker = DPIStartWorker(self.app, selected_mode, launch_method)
        self._dpi_start_worker.moveToThread(self._dpi_start_thread)
        
        # Подключение сигналов
        self._dpi_start_thread.started.connect(self._dpi_start_worker.run)
        self._dpi_start_worker.progress.connect(self.app.set_status)
        self._dpi_start_worker.finished.connect(self._on_dpi_start_finished)
        
        # Очистка ресурсов
        def cleanup_start_thread():
            try:
                if self._dpi_start_thread:
                    self._dpi_start_thread.quit()
                    self._dpi_start_thread.wait(2000)
                    self._dpi_start_thread = None
                    
                if hasattr(self, '_dpi_start_worker'):
                    self._dpi_start_worker.deleteLater()
                    self._dpi_start_worker = None
            except Exception as e:
                log(f"Ошибка при очистке потока запуска: {e}", "❌ ERROR")
        
        self._dpi_start_worker.finished.connect(cleanup_start_thread)
        
        # Запускаем поток
        self._dpi_start_thread.start()
        
        log(f"Запуск асинхронного старта DPI: {mode_name} (метод: {method_name})", "INFO")    

    def stop_dpi_async(self):
        """Асинхронно останавливает DPI без блокировки UI"""
        # Проверка на уже запущенный поток
        try:
            if self._dpi_stop_thread and self._dpi_stop_thread.isRunning():
                log("Остановка DPI уже выполняется", "DEBUG")
                return
        except RuntimeError:
            self._dpi_stop_thread = None
        
        launch_method = get_strategy_launch_method()
        
        # Показываем состояние остановки
        method_name = "прямой" if launch_method == "direct" else "классический"
        self.app.set_status(f"🛑 Остановка DPI ({method_name} метод)...")
        
        # Блокируем кнопки во время операции
        if hasattr(self.app, 'start_btn'):
            self.app.start_btn.setEnabled(False)
        if hasattr(self.app, 'stop_btn'):
            self.app.stop_btn.setEnabled(False)
        
        # Создаем поток и worker
        self._dpi_stop_thread = QThread()
        self._dpi_stop_worker = DPIStopWorker(self.app, launch_method)
        self._dpi_stop_worker.moveToThread(self._dpi_stop_thread)
        
        # Подключение сигналов
        self._dpi_stop_thread.started.connect(self._dpi_stop_worker.run)
        self._dpi_stop_worker.progress.connect(self.app.set_status)
        self._dpi_stop_worker.finished.connect(self._on_dpi_stop_finished)
        
        # Очистка ресурсов
        def cleanup_stop_thread():
            try:
                if self._dpi_stop_thread:
                    self._dpi_stop_thread.quit()
                    self._dpi_stop_thread.wait(2000)
                    self._dpi_stop_thread = None
                    
                if hasattr(self, '_dpi_stop_worker'):
                    self._dpi_stop_worker.deleteLater()
                    self._dpi_stop_worker = None
            except Exception as e:
                log(f"Ошибка при очистке потока остановки: {e}", "❌ ERROR")
        
        self._dpi_stop_worker.finished.connect(cleanup_stop_thread)
        
        # Устанавливаем флаг ручной остановки
        self.app.manually_stopped = True
        
        # Запускаем поток
        self._dpi_stop_thread.start()
        
        log(f"Запуск асинхронной остановки DPI (метод: {method_name})", "INFO")
    
    def stop_and_exit_async(self):
        """Асинхронно останавливает DPI и закрывает программу"""
        self.app._is_exiting = True
        
        # Создаем worker и поток
        self._stop_exit_thread = QThread()
        self._stop_exit_worker = StopAndExitWorker(self.app)
        self._stop_exit_worker.moveToThread(self._stop_exit_thread)
        
        # Подключаем сигналы
        self._stop_exit_thread.started.connect(self._stop_exit_worker.run)
        self._stop_exit_worker.progress.connect(self.app.set_status)
        self._stop_exit_worker.finished.connect(self._on_stop_and_exit_finished)
        self._stop_exit_worker.finished.connect(self._stop_exit_thread.quit)
        self._stop_exit_worker.finished.connect(self._stop_exit_worker.deleteLater)
        self._stop_exit_thread.finished.connect(self._stop_exit_thread.deleteLater)
        
        # Запускаем поток
        self._stop_exit_thread.start()
    
    def _on_dpi_start_finished(self, success, error_message):
        """Обрабатывает завершение асинхронного запуска DPI"""
        try:
            # Восстанавливаем кнопки
            if hasattr(self.app, 'start_btn'):
                self.app.start_btn.setEnabled(True)
            if hasattr(self.app, 'stop_btn'):
                self.app.stop_btn.setEnabled(True)
            
            if success:
                log("DPI запущен асинхронно", "INFO")
                self.app.set_status("✅ DPI успешно запущен")
                
                # Обновляем UI
                self.app.update_ui(running=True)
                
                # Обновляем статус процесса
                self.app.on_process_status_changed(True)
                
                # Устанавливаем флаг намеренного запуска
                self.app.intentional_start = True
                
                # Перезапускаем Discord если нужно
                from discord.discord_restart import get_discord_restart_setting
                if not self.app.first_start and get_discord_restart_setting():
                    self.app.discord_manager.restart_discord_if_running()
                else:
                    self.app.first_start = False
                    
            else:
                log(f"Ошибка асинхронного запуска DPI: {error_message}", "❌ ERROR")
                self.app.set_status(f"❌ Ошибка запуска: {error_message}")
                
                # Обновляем UI как неактивный
                self.app.update_ui(running=False)
                self.app.on_process_status_changed(False)
                
        except Exception as e:
            log(f"Ошибка при обработке результата запуска DPI: {e}", "❌ ERROR")
            self.app.set_status(f"Ошибка: {e}")
    
    def _on_dpi_stop_finished(self, success, error_message):
        """Обрабатывает завершение асинхронной остановки DPI"""
        try:
            # Восстанавливаем кнопки
            if hasattr(self.app, 'start_btn'):
                self.app.start_btn.setEnabled(True)
            if hasattr(self.app, 'stop_btn'):
                self.app.stop_btn.setEnabled(True)
            
            if success:
                log("DPI остановлен асинхронно", "INFO")
                if error_message:
                    self.app.set_status(f"✅ {error_message}")
                else:
                    self.app.set_status("✅ DPI успешно остановлен")
                
                # Обновляем UI
                self.app.update_ui(running=False)
                
                # Обновляем статус процесса
                self.app.on_process_status_changed(False)
                
            else:
                log(f"Ошибка асинхронной остановки DPI: {error_message}", "❌ ERROR")
                self.app.set_status(f"❌ Ошибка остановки: {error_message}")
                
                # Проверяем реальный статус процесса
                is_running = self.app.dpi_starter.check_process_running_wmi(silent=True)
                self.app.update_ui(running=is_running)
                self.app.on_process_status_changed(is_running)
                
        except Exception as e:
            log(f"Ошибка при обработке результата остановки DPI: {e}", "❌ ERROR")
            self.app.set_status(f"Ошибка: {e}")
    
    def _on_stop_and_exit_finished(self):
        """Завершает приложение после остановки DPI"""
        self.app.set_status("Завершение...")
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()
    
    def cleanup_threads(self):
        """Очищает все потоки при закрытии приложения"""
        try:
            if self._dpi_start_thread and self._dpi_start_thread.isRunning():
                self._dpi_start_thread.quit()
                self._dpi_start_thread.wait(1000)
            
            if self._dpi_stop_thread and self._dpi_stop_thread.isRunning():
                self._dpi_stop_thread.quit()
                self._dpi_stop_thread.wait(1000)
        except Exception as e:
            log(f"Ошибка при очистке потоков DPI контроллера: {e}", "❌ ERROR")
