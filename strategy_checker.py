# strategy_checker.py
"""
Модуль для проверки и анализа текущей стратегии DPI
Поддерживает BAT стратегии, встроенные и кастомные комбинированные стратегии
"""

import os
from typing import Dict, Optional, List
from config import (
    get_last_strategy,
    BAT_FOLDER
)
from log import log
from strategy_menu import get_strategy_launch_method


class StrategyChecker:
    """Класс для проверки и анализа стратегий"""
    
    def __init__(self):
        self.launch_method = get_strategy_launch_method()
        self.current_strategy = None
        self.strategy_type = None  # 'bat', 'builtin', 'combined'
        self.strategy_details = {}
        
    def check_current_strategy(self) -> Dict:
        """
        Проверяет текущую выбранную стратегию
        
        Returns:
            Dict с информацией о стратегии:
            - name: название стратегии
            - type: тип ('bat', 'builtin', 'combined')
            - method: метод запуска ('bat', 'direct')
            - file_status: статус файла ('found', 'not_found', 'N/A')
            - details: дополнительные детали
        """
        try:
            result = {
                'name': 'Неизвестная',
                'type': 'unknown',
                'method': self.launch_method,
                'file_status': 'N/A',
                'details': {}
            }
            
            if self.launch_method == 'direct':
                result.update(self._check_direct_strategy())
            else:
                result.update(self._check_bat_strategy())
                
            return result
            
        except Exception as e:
            log(f"Ошибка проверки стратегии: {e}", "❌ ERROR")
            return {
                'name': f'Ошибка: {e}',
                'type': 'error',
                'method': self.launch_method,
                'file_status': 'error',
                'details': {}
            }
    
    def _check_direct_strategy(self) -> Dict:
        """Проверка стратегии в direct режиме"""
        try:
            # Получаем выборы категорий
            from strategy_menu import get_direct_strategy_selections
            selections = get_direct_strategy_selections()
            
            # Это комбинированная стратегия
            from strategy_menu.strategy_lists_separated import combine_strategies
            from strategy_menu.strategies_registry import registry
            
            # Получаем комбинированную конфигурацию
            combined = combine_strategies(**selections)
            
            # Формируем детали
            active_categories = []
            strategy_names = []
            
            for category_key in registry.get_all_category_keys():
                strategy_id = selections.get(category_key)
                
                # Проверяем, что стратегия активна (не "none" и не пустая)
                if strategy_id and strategy_id != "none":
                    category_info = registry.get_category_info(category_key)
                    strategy_name = registry.get_strategy_name_safe(category_key, strategy_id)
                    
                    if category_info:
                        active_categories.append(category_info.full_name)
                        strategy_names.append(f"{category_info.full_name}: {strategy_name}")
            
            # Подсчитываем параметры
            args_list = combined['args'].split() if combined['args'] else []
            
            # Анализируем флаги
            flags_analysis = self._analyze_strategy_flags(args_list)
            
            return {
                'name': combined['description'],
                'type': 'combined',
                'method': 'direct',
                'file_status': 'N/A',
                'details': {
                    'active_categories': active_categories,
                    'strategy_names': strategy_names,
                    'selections': selections,
                    'args_count': len(args_list),
                    'hostlists': flags_analysis.get('hostlists', []),
                    'ipsets': flags_analysis.get('ipsets', []),
                    'filters': flags_analysis.get('filters', []),
                    'dpi_techniques': flags_analysis.get('dpi_techniques', []),
                    'special_params': flags_analysis.get('special_params', [])
                }
            }
            
        except Exception as e:
            log(f"Ошибка проверки direct стратегии: {e}", "DEBUG")
            return {
                'name': 'Direct стратегия (ошибка чтения)',
                'type': 'direct',
                'method': 'direct',
                'file_status': 'error',
                'details': {'error': str(e)}
            }
    
    def _check_bat_strategy(self) -> Dict:
        """Проверка BAT стратегии"""
        try:
            strategy_name = get_last_strategy()
            
            # Ищем файл стратегии
            strategy_file = self._find_strategy_file(strategy_name)
            file_status = 'found' if strategy_file else 'not_found'
            
            details = {}
            
            if strategy_file and os.path.exists(strategy_file):
                # Читаем содержимое файла
                try:
                    with open(strategy_file, 'r', encoding='utf-8-sig', errors='ignore') as f:
                        content = f.read()
                    
                    # Анализируем содержимое
                    details['file_size'] = os.path.getsize(strategy_file)
                    details['file_path'] = strategy_file
                    
                    # Ищем версию
                    for line in content.split('\n'):
                        if 'VERSION:' in line:
                            details['version'] = line.split('VERSION:')[1].strip()
                            break
                    
                    # Анализируем команды winws
                    winws_commands = self._extract_winws_commands(content)
                    if winws_commands:
                        details['commands_count'] = len(winws_commands)
                        
                        # Анализируем флаги из первой команды
                        if winws_commands:
                            flags_analysis = self._analyze_bat_command(winws_commands[0])
                            details.update(flags_analysis)
                            
                except Exception as e:
                    log(f"Ошибка чтения BAT файла: {e}", "DEBUG")
                    details['read_error'] = str(e)
            
            return {
                'name': strategy_name,
                'type': 'bat',
                'method': 'bat',
                'file_status': file_status,
                'details': details
            }
            
        except Exception as e:
            log(f"Ошибка проверки BAT стратегии: {e}", "DEBUG")
            return {
                'name': 'BAT стратегия (ошибка)',
                'type': 'bat',
                'method': 'bat',
                'file_status': 'error',
                'details': {'error': str(e)}
            }
    
    def _analyze_strategy_flags(self, args_list: List[str]) -> Dict:
        """Анализирует флаги стратегии zapret/winws"""
        analysis = {
            'hostlists': [],
            'ipsets': [],
            'filters': [],
            'dpi_techniques': [],
            'special_params': []
        }
        
        i = 0
        while i < len(args_list):
            arg = args_list[i]
            
            # Хостлисты
            if arg.startswith('--hostlist='):
                hostlist = arg.split('=', 1)[1]
                analysis['hostlists'].append(hostlist)
            elif arg.startswith('--hostlist-domains='):
                domains = arg.split('=', 1)[1]
                analysis['hostlists'].append(f"domains:{domains}")
            
            # IPsets
            elif arg.startswith('--ipset='):
                ipset = arg.split('=', 1)[1]
                analysis['ipsets'].append(ipset)
            elif arg.startswith('--ipset-ip='):
                ip = arg.split('=', 1)[1]
                analysis['ipsets'].append(f"ip:{ip}")
            
            # Фильтры портов и протоколов
            elif arg.startswith('--filter-tcp='):
                ports = arg.split('=', 1)[1]
                analysis['filters'].append(f"TCP:{ports}")
            elif arg.startswith('--filter-udp='):
                ports = arg.split('=', 1)[1]
                analysis['filters'].append(f"UDP:{ports}")
            elif arg.startswith('--filter-l7='):
                l7 = arg.split('=', 1)[1]
                analysis['filters'].append(f"L7:{l7}")
            elif arg.startswith('--filter-l3='):
                l3 = arg.split('=', 1)[1]
                analysis['filters'].append(f"L3:{l3}")
            
            # DPI техники (ключевые!)
            elif arg.startswith('--dpi-desync='):
                technique = arg.split('=', 1)[1]
                analysis['dpi_techniques'].append(f"desync:{technique}")
            elif arg.startswith('--dpi-desync-split-pos='):
                pos = arg.split('=', 1)[1]
                analysis['dpi_techniques'].append(f"split-pos:{pos}")
            elif arg.startswith('--dpi-desync-split-seqovl='):
                seqovl = arg.split('=', 1)[1]
                analysis['dpi_techniques'].append(f"seqovl:{seqovl}")
            elif arg.startswith('--dpi-desync-fooling='):
                fooling = arg.split('=', 1)[1]
                analysis['dpi_techniques'].append(f"fooling:{fooling}")
            elif arg.startswith('--dpi-desync-repeats='):
                repeats = arg.split('=', 1)[1]
                analysis['dpi_techniques'].append(f"repeats:{repeats}")
            elif arg.startswith('--dpi-desync-ttl='):
                ttl = arg.split('=', 1)[1]
                analysis['dpi_techniques'].append(f"ttl:{ttl}")
            elif arg == '--dpi-desync-autottl':
                analysis['dpi_techniques'].append("autottl")
            elif arg.startswith('--dpi-desync-autottl='):
                autottl = arg.split('=', 1)[1]
                analysis['dpi_techniques'].append(f"autottl:{autottl}")
            elif arg.startswith('--dpi-desync-fake-'):
                # --dpi-desync-fake-tls, --dpi-desync-fake-http, etc.
                fake_type = arg.split('=')[0].replace('--dpi-desync-fake-', '')
                analysis['dpi_techniques'].append(f"fake-{fake_type}")
            elif arg == '--dpi-desync-any-protocol':
                analysis['dpi_techniques'].append("any-protocol")
            
            # Специальные параметры
            elif arg.startswith('--dup='):
                dup = arg.split('=', 1)[1]
                analysis['special_params'].append(f"dup:{dup}")
            elif arg == '--dup-autottl':
                analysis['special_params'].append("dup-autottl")
            elif arg.startswith('--dup-cutoff='):
                cutoff = arg.split('=', 1)[1]
                analysis['special_params'].append(f"dup-cutoff:{cutoff}")
            elif arg.startswith('--dup-fooling='):
                fooling = arg.split('=', 1)[1]
                analysis['special_params'].append(f"dup-fooling:{fooling}")
            elif arg == '--new':
                analysis['special_params'].append("--new (multi-strategy)")
            
            i += 1
        
        return analysis
    
    def _analyze_bat_command(self, command: str) -> Dict:
        """Анализирует команду из BAT файла"""
        import shlex
        
        try:
            # Парсим команду
            parts = shlex.split(command, posix=False)
            
            # Убираем путь к exe и start /min если есть
            filtered_parts = []
            skip_next = False
            for part in parts:
                if skip_next:
                    skip_next = False
                    continue
                if 'winws.exe' in part.lower():
                    continue
                if part.lower() in ['start', '/min', '/b']:
                    skip_next = (part.lower() == 'start')
                    continue
                filtered_parts.append(part)
            
            # Анализируем флаги
            return self._analyze_strategy_flags(filtered_parts)
            
        except Exception as e:
            log(f"Ошибка анализа BAT команды: {e}", "DEBUG")
            return {}
    
    def _extract_winws_commands(self, bat_content: str) -> List[str]:
        """Извлекает команды winws из BAT файла"""
        commands = []
        
        for line in bat_content.split('\n'):
            line = line.strip()
            if 'winws.exe' in line.lower() and not line.startswith('::') and not line.startswith('REM'):
                commands.append(line)
        
        return commands
    
    def _find_strategy_file(self, strategy_name: str) -> Optional[str]:
        """Ищет файл стратегии в папке bat"""
        try:
            if not os.path.exists(BAT_FOLDER):
                return None
            
            # Ищем файлы .bat
            for file in os.listdir(BAT_FOLDER):
                if file.lower().endswith('.bat'):
                    file_path = os.path.join(BAT_FOLDER, file)
                    
                    # Простое сопоставление по имени
                    if strategy_name.lower() in file.lower():
                        return file_path
            
            # Если не нашли по имени, возвращаем первый .bat файл
            for file in os.listdir(BAT_FOLDER):
                if file.lower().endswith('.bat'):
                    return os.path.join(BAT_FOLDER, file)
            
            return None
            
        except Exception as e:
            log(f"Ошибка поиска файла стратегии: {e}", "DEBUG")
            return None
    
    def format_strategy_info(self, info: Dict) -> List[str]:
        """Форматирует информацию о стратегии для вывода в лог"""
        lines = []
        
        lines.append("📋 ИНФОРМАЦИЯ О СТРАТЕГИИ:")
        lines.append(f"   Название: {info['name']}")
        lines.append(f"   Тип: {self._format_type(info['type'])}")
        lines.append(f"   Метод запуска: {self._format_method(info['method'])}")
        
        if info['file_status'] != 'N/A':
            status_icon = "✅" if info['file_status'] == 'found' else "❌"
            lines.append(f"   Файл стратегии: {status_icon} {info['file_status']}")
        
        details = info.get('details', {})
        
        # Для комбинированных стратегий
        if info['type'] == 'combined' and details:
            if details.get('active_categories'):
                lines.append(f"   Активные категории ({len(details['active_categories'])}):")
                for cat in details['active_categories']:
                    lines.append(f"      • {cat}")
            
            if details.get('strategy_names'):
                lines.append("   Используемые стратегии:")
                for name in details['strategy_names']:
                    lines.append(f"      • {name}")
            
            if details.get('args_count'):
                lines.append(f"   Количество аргументов: {details['args_count']}")
        
        # Анализ фильтров
        if details.get('filters'):
            lines.append(f"   Фильтры: {', '.join(details['filters'][:5])}")
            if len(details['filters']) > 5:
                lines.append(f"      ... и еще {len(details['filters']) - 5}")
        
        # Анализ хостлистов
        if details.get('hostlists'):
            lines.append(f"   Хостлисты: {', '.join(details['hostlists'][:5])}")
            if len(details['hostlists']) > 5:
                lines.append(f"      ... и еще {len(details['hostlists']) - 5}")
        
        # IPsets
        if details.get('ipsets'):
            lines.append(f"   IPsets: {', '.join(details['ipsets'][:3])}")
            if len(details['ipsets']) > 3:
                lines.append(f"      ... и еще {len(details['ipsets']) - 3}")
        
        # DPI техники (ключевая информация!)
        if details.get('dpi_techniques'):
            lines.append("   DPI техники:")
            for tech in details['dpi_techniques'][:8]:
                lines.append(f"      • {tech}")
            if len(details['dpi_techniques']) > 8:
                lines.append(f"      ... и еще {len(details['dpi_techniques']) - 8}")
        
        # Специальные параметры
        if details.get('special_params'):
            lines.append(f"   Спец. параметры: {', '.join(details['special_params'][:5])}")
        
        # Для BAT стратегий
        if info['type'] == 'bat' and details:
            if details.get('version'):
                lines.append(f"   Версия: {details['version']}")
            
            if details.get('file_size'):
                size_kb = details['file_size'] / 1024
                lines.append(f"   Размер файла: {size_kb:.1f} KB")
            
            if details.get('commands_count'):
                lines.append(f"   Команд winws: {details['commands_count']}")
        
        return lines
    
    def _format_type(self, type_str: str) -> str:
        """Форматирует тип стратегии"""
        types = {
            'bat': '📄 BAT файл',
            'builtin': '⚡ Встроенная',
            'combined': '🔀 Комбинированная',
            'direct': '🎯 Прямая',
            'unknown': '❓ Неизвестный',
            'error': '❌ Ошибка'
        }
        return types.get(type_str, type_str)
    
    def _format_method(self, method: str) -> str:
        """Форматирует метод запуска"""
        methods = {
            'bat': '📄 Классический (BAT)',
            'direct': '🎯 Прямой запуск',
            'unknown': '❓ Неизвестный'
        }
        return methods.get(method, method)


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def check_and_log_strategy():
    """Проверяет текущую стратегию и выводит в лог"""
    checker = StrategyChecker()
    info = checker.check_current_strategy()
    
    for line in checker.format_strategy_info(info):
        log(line, "INFO")
    
    return info


def get_strategy_summary() -> str:
    """Возвращает краткую сводку о текущей стратегии"""
    checker = StrategyChecker()
    info = checker.check_current_strategy()
    
    if info['type'] == 'combined':
        active_count = len(info['details'].get('active_categories', []))
        return f"🔀 Комбинированная ({active_count} категорий)"
    elif info['type'] == 'bat':
        return f"📄 {info['name']}"
    else:
        return f"{info['name']}"