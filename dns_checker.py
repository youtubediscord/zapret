# dns_checker.py
"""
Модуль для проверки DNS подмены провайдером
Проверяет резолвинг доменов YouTube и Discord через разные DNS серверы
"""

import socket
import subprocess
import re, os, sys
from typing import Dict, List, Tuple, Optional
from log import log


class DNSChecker:
    """Класс для проверки DNS подмены"""
    
    def __init__(self):
        # Известные легитимные IP диапазоны для сервисов
        self.known_ranges = {
            'youtube': {
                'domains': ['www.youtube.com', 'youtube.com', 'googlevideo.com'],
                'valid_ranges': [
                    '142.250.',  # Google
                    '142.251.',  # Google
                    '172.217.',  # Google
                    '172.253.',  # Google
                    '173.194.',  # Google
                    '74.125.',   # Google
                    '209.85.',   # Google
                    '216.58.',   # Google
                    '108.177.',  # Google
                    '64.233.',   # Google
                    '192.178.',  # Google (новый диапазон!)
                    '192.179.',  # Google (новый диапазон!)
                ]
            },
            'discord': {
                'domains': ['discord.com', 'discordapp.com', 'discord.gg'],
                'valid_ranges': [
                    '162.159.',  # Cloudflare
                    '104.16.',   # Cloudflare
                    '104.17.',   # Cloudflare
                    '104.18.',   # Cloudflare
                    '104.19.',   # Cloudflare
                    '104.20.',   # Cloudflare
                    '104.21.',   # Cloudflare
                    '104.22.',   # Cloudflare
                    '104.23.',   # Cloudflare
                    '104.24.',   # Cloudflare
                    '104.25.',   # Cloudflare
                    '104.26.',   # Cloudflare
                    '104.27.',   # Cloudflare
                    '172.64.',   # Cloudflare
                    '172.65.',   # Cloudflare
                    '172.66.',   # Cloudflare
                    '172.67.',   # Cloudflare
                ]
            }
        }
        
        # DNS серверы для проверки
        self.dns_servers = {
            'System Default': None,  # Системный DNS (провайдера)
            'Google DNS': '8.8.8.8',
            'Google DNS 2': '8.8.4.4',
            'Cloudflare': '1.1.1.1',
            'Cloudflare 2': '1.0.0.1',
            'Quad9': '9.9.9.9',
            'OpenDNS': '208.67.222.222',
            'Yandex DNS': '77.88.8.8',
            'AdGuard DNS': '94.140.14.14',
        }
        
        # Известные IP адреса блокировок провайдеров
        self.known_block_ips = [
            '127.0.0.1',
            '0.0.0.0',
            '10.10.10.10',
            '195.82.146.214',  # Ростелеком заглушка
            '81.19.72.32',     # МТС заглушка
            '213.180.193.250', # Билайн заглушка
            '217.169.80.229',  # Мегафон заглушка
            '62.33.207.196',   # Заглушка РКН
            '62.33.207.197',   # Заглушка РКН
            '62.33.207.198',   # Заглушка РКН
        ]
    
    def check_dns_poisoning(self, log_callback=None) -> Dict:
        """
        Главная функция проверки DNS подмены
        
        Args:
            log_callback: функция для вывода лога
            
        Returns:
            Dict с результатами проверки
        """
        results = {
            'youtube': {},
            'discord': {},
            'summary': {
                'youtube_blocked': False,
                'discord_blocked': False,
                'dns_poisoning_detected': False,
                'recommended_dns': None,
                'external_dns_blocked': False
            }
        }
        
        self._log("=" * 40, log_callback)
        self._log("🔍 ПРОВЕРКА DNS ПОДМЕНЫ", log_callback)
        self._log("=" * 40, log_callback)
        
        # Сначала проверяем доступность внешних DNS
        self._log("\n🌐 Проверка доступности DNS серверов:", log_callback)
        dns_availability = self._check_dns_servers_availability(log_callback)
        
        if not any(dns_availability.values()):
            self._log("⚠️ Все внешние DNS серверы недоступны!", log_callback)
            self._log("Возможно, провайдер блокирует альтернативные DNS", log_callback)
            results['summary']['external_dns_blocked'] = True
        
        # Проверяем YouTube
        self._log("\n📹 Проверка DNS для YouTube:", log_callback)
        results['youtube'] = self._check_service('youtube', log_callback)
        
        # Проверяем Discord
        self._log("\n💬 Проверка DNS для Discord:", log_callback)
        results['discord'] = self._check_service('discord', log_callback)
        
        # Анализируем результаты
        self._analyze_results(results, log_callback)
        
        return results

    def _nslookup(self, domain: str, dns_server: str) -> Optional[str]:
        """Выполняет nslookup для домена через указанный DNS сервер"""
        try:
            # Формируем команду nslookup
            command = ["nslookup", domain, dns_server]
            
            # Выполняем команду
            result = subprocess.run(
                command,
                capture_output=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith('win') else 0
            )
            
            # Декодируем вывод с правильной кодировкой для Windows
            try:
                output = result.stdout.decode('cp866', errors='ignore')
            except:
                output = result.stdout.decode('utf-8', errors='ignore')
            
            # Логируем для отладки
            log(f"nslookup {domain} @{dns_server} returned code {result.returncode}", "DEBUG")
            
            # Проверяем на ошибки
            if "can't find" in output.lower() or "non-existent" in output.lower():
                return None
                
            if "timed out" in output.lower() or "timeout" in output.lower():
                return None
            
            # Проверяем успешность по коду возврата
            if result.returncode != 0 and not output:
                return None
            
            # Специальная обработка для multiline Addresses
            lines = output.split('\n')
            
            # Ищем строку "Addresses:" или "Адреса:"
            addresses_idx = -1
            for i, line in enumerate(lines):
                if any(addr in line for addr in ['Addresses:', 'Адреса:']):
                    addresses_idx = i
                    break
            
            # Если нашли "Addresses:", проверяем следующие строки
            if addresses_idx >= 0:
                # Сначала проверяем есть ли IP в той же строке
                addr_line = lines[addresses_idx]
                ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', addr_line)
                if ip_match:
                    ip = ip_match.group(1)
                    if self._is_valid_ip(ip) and ip != dns_server:
                        log(f"Found IP in Addresses line: {ip}", "DEBUG")
                        return ip
                
                # Проверяем следующие строки (обычно IP адреса идут с отступом)
                for j in range(addresses_idx + 1, min(addresses_idx + 30, len(lines))):
                    line = lines[j].strip()
                    
                    # Прекращаем если встретили новую секцию
                    if line and not line[0].isspace() and ':' in line:
                        break
                    
                    # Ищем IPv4 адрес
                    ip_match = re.search(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$', line)
                    if ip_match:
                        ip = ip_match.group(1)
                        if self._is_valid_ip(ip) and ip != dns_server:
                            log(f"Found IP in multiline: {ip}", "DEBUG")
                            return ip
            
            # Альтернативный метод - ищем секцию "Non-authoritative answer"
            in_answer_section = False
            
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                
                # Проверяем начало секции ответа
                if any(marker in line.lower() for marker in [
                    'non-authoritative answer', 
                    'не заслуживающий доверия',
                    'неавторитетный ответ'
                ]):
                    in_answer_section = True
                    continue
                
                # Если мы в секции ответа
                if in_answer_section:
                    # Ищем строки "Address:" (одиночный адрес)
                    if 'Address:' in line or 'Адрес:' in line:
                        ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
                        if ip_match:
                            ip = ip_match.group(1)
                            if self._is_valid_ip(ip) and ip != dns_server:
                                log(f"Found IP in Address line: {ip}", "DEBUG")
                                return ip
                    
                    # Проверяем просто строки с IP (для multiline вывода)
                    ip_match = re.search(r'^\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*$', line)
                    if ip_match:
                        ip = ip_match.group(1)
                        if self._is_valid_ip(ip) and ip != dns_server:
                            log(f"Found standalone IP: {ip}", "DEBUG")
                            return ip
            
            # Последняя попытка - ищем все IP адреса
            all_ips = re.findall(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', output)
            
            # Отладка
            if all_ips:
                log(f"All IPs found: {all_ips}", "DEBUG")
            
            # Фильтруем и возвращаем первый подходящий
            for ip in all_ips:
                if (self._is_valid_ip(ip) and 
                    ip != dns_server and 
                    not ip.startswith('127.') and
                    not ip.startswith('192.168.') and
                    not ip.startswith('10.')):
                    log(f"Returning IP from all IPs: {ip}", "DEBUG")
                    return ip
            
            log(f"No valid IP found for {domain} via {dns_server}", "DEBUG")
            return None
            
        except subprocess.TimeoutExpired:
            log(f"nslookup timeout for {domain} via {dns_server}", "DEBUG")
            return None
        except Exception as e:
            log(f"nslookup error: {e}", "DEBUG")
            return None

    def _ping_dns_server(self, dns_server: str) -> bool:
        """Проверяет доступность DNS сервера через ping"""
        try:
            # Простой ping для проверки доступности хоста
            command = ["ping", "-n", "1", "-w", "1000", dns_server]
            result = subprocess.run(
                command,
                capture_output=True,
                timeout=2,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith('win') else 0  # ✅ ИСПРАВЛЕНО
            )
            
            output = result.stdout.decode('cp866', errors='ignore')
            
            # Проверяем успешность ping
            return any(pattern in output for pattern in ["TTL=", "ttl=", "bytes=", "байт="])
            
        except Exception:
            return False

    def _check_dns_servers_availability(self, log_callback=None) -> Dict[str, bool]:
        """Проверяет доступность DNS серверов через DNS запросы"""
        availability = {}
        
        self._log("Проверка доступности DNS серверов...", log_callback)
        
        for dns_name, dns_server in self.dns_servers.items():
            if dns_server is None:  # Пропускаем системный DNS
                continue
            
            # Проверяем может ли DNS сервер резолвить домены
            test_successful = False
            
            # Пробуем несколько популярных доменов
            test_domains = ["google.com", "cloudflare.com", "example.com"]
            
            for test_domain in test_domains:
                result = self._resolve_domain(test_domain, dns_server)
                if result['ip'] is not None:
                    test_successful = True
                    break
            
            availability[dns_name] = test_successful
            
            if test_successful:
                self._log(f"  {dns_name} ({dns_server}): ✅ Доступен", log_callback)
            else:
                self._log(f"  {dns_name} ({dns_server}): ❌ Недоступен", log_callback)
        
        return availability


    def _resolve_via_socket(self, domain: str, dns_server: str) -> Optional[str]:
        """Альтернативный метод резолвинга через DNS библиотеку"""
        try:
            # Пробуем использовать встроенный резолвер Python
            # Это не будет работать с кастомным DNS, но хотя бы проверит доступность
            import socket
            
            # Временно меняем DNS (работает не всегда)
            # Это больше для проверки что домен вообще резолвится
            try:
                result = socket.gethostbyname(domain)
                if self._is_valid_ip(result):
                    log(f"Socket resolved {domain} to {result}", "DEBUG")
                    return result
            except:
                pass
                
            return None
            
        except Exception as e:
            log(f"Socket resolve error: {e}", "DEBUG")
            return None
            
    def _check_service(self, service: str, log_callback=None) -> Dict:
        """Проверяет DNS для конкретного сервиса"""
        service_results = {
            'domains': {},
            'dns_servers': {},
            'blocked': False,
            'poisoned': False
        }
        
        service_info = self.known_ranges[service]
        
        # Проверяем каждый домен
        for domain in service_info['domains']:
            self._log(f"\nПроверка домена: {domain}", log_callback)
            domain_results = {}
            
            # Проверяем через разные DNS серверы
            for dns_name, dns_server in self.dns_servers.items():
                result = self._resolve_domain(domain, dns_server)
                domain_results[dns_name] = result
                
                if result['ip']:
                    status = self._check_ip_validity(result['ip'], service)
                    
                    if status == 'valid':
                        icon = "✅"
                        status_text = "Валидный IP"
                    elif status == 'blocked':
                        icon = "🚫"
                        status_text = "Заглушка провайдера!"
                        service_results['blocked'] = True
                        service_results['poisoned'] = True
                    else:
                        icon = "⚠️"
                        status_text = "Подозрительный IP"
                        service_results['poisoned'] = True
                    
                    self._log(f"  {dns_name}: {result['ip']} - {icon} {status_text}", log_callback)
                else:
                    if result.get('error'):
                        if 'timeout' in str(result['error']).lower():
                            self._log(f"  {dns_name}: ⏱️ Таймаут", log_callback)
                        else:
                            self._log(f"  {dns_name}: ❌ Не разрешается", log_callback)
                    else:
                        self._log(f"  {dns_name}: ❌ Не разрешается", log_callback)
            
            service_results['domains'][domain] = domain_results
        
        return service_results
    
    def _resolve_domain(self, domain: str, dns_server: Optional[str] = None) -> Dict:
        """Резолвит домен через указанный DNS сервер"""
        result = {
            'ip': None,
            'error': None,
            'dns_server': dns_server
        }
        
        try:
            if dns_server:
                # Используем nslookup для конкретного DNS сервера
                result['ip'] = self._nslookup(domain, dns_server)
            else:
                # Используем системный DNS
                result['ip'] = socket.gethostbyname(domain)
                
        except socket.gaierror as e:
            result['error'] = f"DNS resolution failed: {e}"
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Проверяет, является ли строка валидным IP адресом"""
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            for part in parts:
                if not 0 <= int(part) <= 255:
                    return False
            return True
        except:
            return False
    
    def _check_ip_validity(self, ip: str, service: str) -> str:
        """
        Проверяет валидность IP адреса для сервиса
        
        Returns:
            'valid' - легитимный IP
            'blocked' - известная заглушка
            'suspicious' - подозрительный IP
        """
        # Проверяем на известные заглушки
        if ip in self.known_block_ips:
            return 'blocked'
        
        # Проверяем на локальные адреса
        if ip.startswith('127.') or ip.startswith('10.') or ip.startswith('192.168.'):
            return 'blocked'
        
        # Проверяем на легитимные диапазоны
        valid_ranges = self.known_ranges[service]['valid_ranges']
        for range_prefix in valid_ranges:
            if ip.startswith(range_prefix):
                return 'valid'
        
        # IP не в известных диапазонах - подозрительный
        return 'suspicious'
    
    def _analyze_results(self, results: Dict, log_callback=None):
        """Анализирует результаты и формирует рекомендации"""
        self._log("\n" + "=" * 40, log_callback)
        self._log("📊 АНАЛИЗ РЕЗУЛЬТАТОВ", log_callback)
        self._log("=" * 40, log_callback)
        
        # Проверяем YouTube
        if results['youtube']['poisoned']:
            results['summary']['youtube_blocked'] = True
            results['summary']['dns_poisoning_detected'] = True
            self._log("❌ YouTube: Обнаружена DNS подмена!", log_callback)
        else:
            self._log("✅ YouTube: DNS резолвинг корректный", log_callback)
        
        # Проверяем Discord
        if results['discord']['poisoned']:
            results['summary']['discord_blocked'] = True
            results['summary']['dns_poisoning_detected'] = True
            self._log("❌ Discord: Обнаружена DNS подмена!", log_callback)
        else:
            self._log("✅ Discord: DNS резолвинг корректный", log_callback)
        
        # Анализируем ситуацию с DNS серверами
        self._log("", log_callback)
        
        # Проверяем есть ли вообще рабочие внешние DNS
        working_dns_count = 0
        for service_data in [results['youtube'], results['discord']]:
            for domain_data in service_data['domains'].values():
                for dns_name, dns_result in domain_data.items():
                    if dns_name != 'System Default' and dns_result.get('ip'):
                        working_dns_count += 1
                        break
        
        if working_dns_count == 0 and not results['summary']['dns_poisoning_detected']:
            self._log("ℹ️ ИНФОРМАЦИЯ:", log_callback)
            self._log("Внешние DNS серверы не отвечают на запросы.", log_callback)
            self._log("", log_callback)
            self._log("Возможные причины:", log_callback)
            self._log("  • Firewall блокирует исходящие DNS запросы (UDP порт 53)", log_callback)
            self._log("  • Антивирус блокирует нестандартные DNS запросы", log_callback)
            self._log("  • Корпоративная сеть с ограничениями", log_callback)
            self._log("  • Провайдер перехватывает все DNS запросы", log_callback)
            self._log("", log_callback)
            self._log("Что можно сделать:", log_callback)
            self._log("  1. Проверьте настройки firewall/антивируса", log_callback)
            self._log("  2. Попробуйте DNS-over-HTTPS в браузере", log_callback)
            self._log("  3. Используйте VPN со встроенным DNS", log_callback)
            self._log("", log_callback)
            
        # Итоговое заключение
        if results['summary']['dns_poisoning_detected']:
            self._log("⚠️ ТРЕБУЕТСЯ ДЕЙСТВИЕ:", log_callback)
            self._log("Обнаружена DNS подмена! Смените DNS или используйте Zapret.", log_callback)
        elif working_dns_count == 0:
            self._log("💡 РЕКОМЕНДАЦИЯ:", log_callback)
            self._log("DNS работает корректно, но внешние DNS недоступны.", log_callback)
            self._log("Если есть проблемы с сайтами - используйте Zapret для обхода DPI.", log_callback)
        else:
            self._log("✅ РЕЗУЛЬТАТ:", log_callback)
            self._log("DNS работает корректно. Если сайты недоступны - используйте Zapret.", log_callback)
    
    def _find_working_dns(self, results: Dict) -> Optional[str]:
        """Находит DNS сервер который дает валидные результаты"""
        # Собираем статистику по DNS серверам
        dns_scores = {}
        
        for service in ['youtube', 'discord']:
            for domain, domain_results in results[service]['domains'].items():
                for dns_name, dns_result in domain_results.items():
                    if dns_name not in dns_scores:
                        dns_scores[dns_name] = 0
                    
                    if dns_result['ip']:
                        status = self._check_ip_validity(dns_result['ip'], service)
                        if status == 'valid':
                            dns_scores[dns_name] += 1
                        elif status == 'blocked':
                            dns_scores[dns_name] -= 2
        
        # Находим лучший DNS
        best_dns = None
        best_score = -1
        
        for dns_name, score in dns_scores.items():
            if score > best_score and dns_name != 'System Default':
                best_score = score
                best_dns = dns_name
        
        return best_dns if best_score > 0 else None
    
    def _log(self, message: str, callback=None):
        """Выводит сообщение в лог"""
        if callback:
            callback(message)
        else:
            print(message)
    
    def get_quick_dns_check(self, domain: str) -> Dict:
        """Быстрая проверка DNS для одного домена"""
        result = {
            'domain': domain,
            'system_dns': None,
            'google_dns': None,
            'cloudflare_dns': None,
            'is_blocked': False
        }
        
        # Проверяем через системный DNS
        system_result = self._resolve_domain(domain, None)
        result['system_dns'] = system_result['ip']
        
        # Проверяем через Google DNS
        google_result = self._resolve_domain(domain, '8.8.8.8')
        result['google_dns'] = google_result['ip']
        
        # Проверяем через Cloudflare
        cf_result = self._resolve_domain(domain, '1.1.1.1')
        result['cloudflare_dns'] = cf_result['ip']
        
        # Определяем сервис
        service = None
        if 'youtube' in domain or 'google' in domain:
            service = 'youtube'
        elif 'discord' in domain:
            service = 'discord'
        
        # Проверяем блокировку
        if service and result['system_dns']:
            status = self._check_ip_validity(result['system_dns'], service)
            result['is_blocked'] = (status == 'blocked')
        
        return result