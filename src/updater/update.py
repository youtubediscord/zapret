"""
updater/update.py
────────────────────────────────────────────────────────────────
ОПТИМИЗИРОВАННАЯ ВЕРСИЯ ДЛЯ БЫСТРОГО СКАЧИВАНИЯ
"""
import os, sys, tempfile, subprocess, shutil, time, requests
from typing import Callable
from time import sleep

from PyQt6.QtCore    import QObject, pyqtSignal, QTimer
from packaging import version

from .release_manager import get_latest_release
from .github_release import normalize_version
from .channel_utils import is_dev_update_channel
from config.build_info import CHANNEL, APP_VERSION

from log.log import log

from .rate_limiter import UpdateRateLimiter
from .network_hints import maybe_log_disable_dpi_for_update


TIMEOUT = 15
NUM_SEGMENTS = 4        # параллельные сегменты для скачивания
CHUNK_SIZE = 1024 * 1024  # 1 MB

# ──────────────────────────── Запуск установщика с UAC ─────────────────────────
# ВАЖНО ДЛЯ БУДУЩИХ РАЗРАБОТЧИКОВ:
# НЕ ИСПОЛЬЗОВАТЬ ctypes.windll.shell32.ShellExecuteW с "runas"!
# Причина: ShellExecuteW асинхронный - возвращает успех (HINSTANCE>32) сразу,
# но установщик фактически не запускается (причина до конца не ясна,
# возможно связано с тем что приложение закрывается через os._exit()).
#
# РЕШЕНИЕ: PowerShell Start-Process -Verb RunAs
# Работает стабильно. Если приложение уже запущено с правами админа
# (а Zapret требует админ для WinDivert), UAC не появляется.
# Проверено 25.12.2025.


def launch_installer_winapi(exe_path: str, arguments: str, working_dir: str = None) -> bool:
    """
    Запускает установщик с правами администратора через PowerShell Start-Process.

    ВНИМАНИЕ: Не заменять на ShellExecuteW! См. комментарий выше.

    Args:
        exe_path: Путь к установщику (.exe)
        arguments: Аргументы командной строки (разделённые пробелами)
        working_dir: Рабочая директория (не используется, оставлен для совместимости)

    Returns:
        True если процесс успешно запущен
    """
    # Проверяем существование файла
    if not os.path.exists(exe_path):
        log(f"❌ Файл установщика не найден: {exe_path}", "🔁❌ ERROR")
        return False

    file_size = os.path.getsize(exe_path)
    log(f"📦 Размер установщика: {file_size / 1024 / 1024:.1f} MB", "🔁 UPDATE")

    log(f"🚀 Запуск через PowerShell (RunAs): {exe_path}", "🔁 UPDATE")
    log(f"   Параметры: {arguments}", "🔁 UPDATE")

    try:
        # Разбиваем аргументы на список для PowerShell
        args_list = arguments.split()
        # Формируем строку аргументов для PowerShell: '/arg1','/arg2',...
        ps_args = ",".join(f"'{arg}'" for arg in args_list)

        # PowerShell команда для запуска с правами админа
        ps_command = f"Start-Process -FilePath '{exe_path}' -ArgumentList {ps_args} -Verb RunAs"

        log(f"   PowerShell: {ps_command}", "🔁 UPDATE")

        # Запускаем PowerShell с командой
        process = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", ps_command],
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Даём время на появление UAC (не ждём завершения установщика!)
        time.sleep(0.5)

        # Проверяем, не завершился ли PowerShell с ошибкой
        retcode = process.poll()
        if retcode is not None and retcode != 0:
            stderr = process.stderr.read().decode('utf-8', errors='ignore')
            log(f"❌ PowerShell ошибка (код {retcode}): {stderr}", "🔁❌ ERROR")
            return False

        log(f"✅ Установщик запущен успешно", "🔁 UPDATE")
        return True

    except Exception as e:
        log(f"❌ Ошибка запуска: {e}", "🔁❌ ERROR")
        return False


# ──────────────────────────── вспомогательные утилиты ─────────────────────
def _safe_set_status(parent, msg: str):
    """Пишем в status-label, если она есть; иначе в консоль."""
    if parent and hasattr(parent, "set_status"):
        parent.set_status(msg)
    else:
        print(msg)

def _make_session(verify_ssl: bool = True) -> requests.Session:
    """Создаёт сессию без системного прокси."""
    import urllib3
    s = requests.Session()
    s.trust_env = False
    s.proxies = {"http": None, "https": None}
    s.headers.update({
        'User-Agent': 'Zapret-Updater/4.0',
        'Accept': 'application/octet-stream',
        'Accept-Encoding': 'identity',
    })
    if not verify_ssl:
        s.verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    return s


def _supports_range(url: str, verify_ssl: bool) -> tuple[bool, int]:
    """HEAD-запрос: поддерживает ли сервер Range и какой размер файла."""
    s = _make_session(verify_ssl)
    try:
        resp = s.head(url, timeout=(10, 15), verify=verify_ssl, allow_redirects=True)
        accepts = resp.headers.get("Accept-Ranges", "").lower()
        length = int(resp.headers.get("Content-Length", 0))
        return accepts == "bytes" and length > 0, length
    finally:
        s.close()


def _download_segment(
    url: str, verify_ssl: bool,
    start: int, end: int, seg_path: str,
    seg_index: int, lock: threading.Lock,
    progress_arr: list, total: int,
    on_progress: Callable[[int, int], None] | None,
):
    """Скачивает один сегмент файла через Range."""
    s = _make_session(verify_ssl)
    s.headers['Range'] = f'bytes={start}-{end}'
    try:
        with s.get(url, stream=True, timeout=(10, 90), verify=verify_ssl) as resp:
            resp.raise_for_status()
            with open(seg_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        with lock:
                            progress_arr[seg_index] += len(chunk)
                            if on_progress and total > 0:
                                done = sum(progress_arr)
                                on_progress(done, total)
    finally:
        s.close()


def _download_single(url: str, dest: str, verify_ssl: bool,
                     on_progress: Callable[[int, int], None] | None):
    """Однопоточное скачивание (fallback)."""
    s = _make_session(verify_ssl)
    try:
        with s.get(url, stream=True, timeout=(10, 90), verify=verify_ssl) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length", 0))
            done = 0
            if total > 0:
                log(f"📦 Размер: {total / (1024 * 1024):.1f} MB", "🔄 DOWNLOAD")
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        done += len(chunk)
                        if on_progress and total > 0:
                            on_progress(done, total)
    finally:
        s.close()


def _download_with_retry(url: str, dest: str, on_progress: Callable[[int, int], None] | None,
                         verify_ssl: bool = True, max_retries: int = 2,
                         enable_slow_mirror_switch: bool = True):
    """
    Многопоточное скачивание (4 сегмента параллельно).
    Если сервер не поддерживает Range — fallback на один поток.
    """
    from concurrent.futures import ThreadPoolExecutor
    from time import time as now

    # Защита от повторного скачивания
    if os.path.exists(dest):
        file_age = now() - os.path.getmtime(dest)
        file_size = os.path.getsize(dest)
        if file_age < 30 and file_size > 60_000_000:
            log(f"⏭️ Файл уже скачан {int(file_age)}с назад ({file_size / 1024 / 1024:.1f}MB)", "🔄 DOWNLOAD")
            return

    last_error = None
    for attempt in range(max_retries):
        try:
            log(f"Попытка {attempt + 1}/{max_retries} скачивания {url}", "🔄 DOWNLOAD")

            # Проверяем поддержку Range
            supports_range, total = False, 0
            try:
                supports_range, total = _supports_range(url, verify_ssl)
            except Exception:
                pass

            start_time = now()

            if supports_range and total > NUM_SEGMENTS * CHUNK_SIZE:
                # === МНОГОПОТОЧНОЕ СКАЧИВАНИЕ ===
                log(f"⚡ Многопоток: {NUM_SEGMENTS} сегментов, {total / (1024 * 1024):.1f} MB", "🔄 DOWNLOAD")

                seg_size = total // NUM_SEGMENTS
                segments = []
                for i in range(NUM_SEGMENTS):
                    s_start = i * seg_size
                    s_end = total - 1 if i == NUM_SEGMENTS - 1 else (i + 1) * seg_size - 1
                    segments.append((s_start, s_end))

                seg_dir = dest + "_segments"
                os.makedirs(seg_dir, exist_ok=True)
                seg_paths = [os.path.join(seg_dir, f"seg_{i}") for i in range(NUM_SEGMENTS)]

                lock = threading.Lock()
                progress_arr = [0] * NUM_SEGMENTS

                try:
                    with ThreadPoolExecutor(max_workers=NUM_SEGMENTS) as pool:
                        futures = []
                        for i, (s_start, s_end) in enumerate(segments):
                            fut = pool.submit(
                                _download_segment,
                                url, verify_ssl, s_start, s_end,
                                seg_paths[i], i, lock, progress_arr, total,
                                on_progress,
                            )
                            futures.append(fut)
                        for fut in futures:
                            fut.result()

                    # Склеиваем сегменты
                    with open(dest, "wb") as out:
                        for sp in seg_paths:
                            with open(sp, "rb") as seg_f:
                                shutil.copyfileobj(seg_f, out)
                finally:
                    shutil.rmtree(seg_dir, ignore_errors=True)
            else:
                # === ОДНОПОТОЧНОЕ СКАЧИВАНИЕ ===
                log("📥 Однопоток (Range не поддерживается или файл мал)", "🔄 DOWNLOAD")
                _download_single(url, dest, verify_ssl, on_progress)

            # Проверяем размер
            if os.path.exists(dest):
                actual = os.path.getsize(dest)
                if total > 0 and actual != total:
                    raise Exception(f"Размер не совпадает: {actual} != {total}")

            elapsed = now() - start_time
            size_mb = os.path.getsize(dest) / (1024 * 1024)
            speed = size_mb / max(elapsed, 0.01)
            log(f"✅ Скачано {size_mb:.1f} MB за {elapsed:.1f}с ({speed:.1f} MB/s)", "🔄 DOWNLOAD")

            if on_progress and total > 0:
                on_progress(total, total)
            return

        except Exception as e:
            last_error = str(e)
            log(f"❌ Попытка {attempt + 1} не удалась: {last_error}", "🔄 DOWNLOAD")
            maybe_log_disable_dpi_for_update(e, scope="download", level="🔄 DOWNLOAD")

            if os.path.exists(dest):
                try:
                    os.remove(dest)
                except Exception:
                    pass

            if attempt < max_retries - 1:
                sleep(min(2 ** (attempt + 1), 10))

    raise Exception(f"Не удалось скачать после {max_retries} попыток. Ошибка: {last_error}")

def compare_versions(v1: str, v2: str) -> int:
    """Сравнивает две версии"""
    from packaging import version
    
    try:
        v1_norm = normalize_version(v1)
        v2_norm = normalize_version(v2)
        
        ver1 = version.parse(v1_norm)
        ver2 = version.parse(v2_norm)
        
        if ver1 < ver2:
            return -1
        elif ver1 > ver2:
            return 1
        else:
            return 0
            
    except Exception as e:
        log(f"Error comparing versions '{v1}' and '{v2}': {e}", "🔁❌ ERROR")
        return -1 if v1 < v2 else (1 if v1 > v2 else 0)

# ──────────────────────────── фоновой воркер ──────────────────────────────
class UpdateWorker(QObject):
    progress = pyqtSignal(str)
    progress_value = pyqtSignal(int)
    progress_bytes = pyqtSignal(int, int, int)
    finished = pyqtSignal(bool)
    show_no_updates = pyqtSignal(str)
    download_complete = pyqtSignal()
    download_failed = pyqtSignal(str)
    dpi_restart_needed = pyqtSignal()

    def __init__(self, parent=None, silent: bool = False, skip_rate_limit: bool = False):
        super().__init__()
        self._parent = parent
        self._silent = silent
        self._skip_rate_limit = skip_rate_limit
        self._stop_requested = False

    def stop(self) -> None:
        self._stop_requested = True

    def is_stop_requested(self) -> bool:
        return self._stop_requested

    def _emit(self, msg: str):
        self.progress.emit(msg)

    def _emit_progress(self, percent: int):
        self.progress_value.emit(percent)
    
    def _get_download_urls(self, release_info: dict) -> list:
        """Формирует список URL: GitHub CDN первый, VPS как fallback"""
        urls = []
        upd_url = release_info["update_url"]
        verify_ssl = release_info.get("verify_ssl", True)

        # Извлекаем имя файла
        filename = (release_info.get("file_name") or "").strip()
        if not filename and not upd_url.startswith("telegram://"):
            filename = upd_url.split('/')[-1]
        if not filename:
            filename = "Zapret2Setup.exe"

        # 1. Основной URL (GitHub CDN если источник — GitHub)
        if not upd_url.startswith("telegram://"):
            urls.append((upd_url, verify_ssl))

        # 2. Если источник не GitHub — добавить GitHub как приоритетный fallback
        if "github.com" not in upd_url:
            try:
                from .github_release import get_latest_release as github_get_latest
                gh_release = github_get_latest(CHANNEL)
                if gh_release and gh_release.get("update_url"):
                    urls.append((gh_release["update_url"], True))
            except Exception:
                pass

        # 3. VPS серверы как финальный fallback
        try:
            from .server_config import VPS_SERVERS, should_verify_ssl

            for server in VPS_SERVERS:
                https_url = f"https://{server['host']}:{server['https_port']}/download/{filename}"
                if https_url != upd_url:
                    urls.append((https_url, should_verify_ssl()))

            for server in VPS_SERVERS:
                http_url = f"http://{server['host']}:{server['http_port']}/download/{filename}"
                if http_url != upd_url:
                    urls.append((http_url, False))

        except Exception as e:
            log(f"Не удалось добавить VPS fallback: {e}", "🔁 UPDATE")

        log(f"Сформировано {len(urls)} URL для скачивания", "🔁 UPDATE")
        return urls

    def _test_download_connectivity(self, url: str, verify_ssl: bool) -> bool:
        """Быстрый тест связи с сервером скачивания (HEAD, таймаут 5с)."""
        try:
            s = _make_session(verify_ssl)
            try:
                resp = s.head(url, timeout=(5, 5), verify=verify_ssl, allow_redirects=True)
                return resp.status_code < 500
            finally:
                s.close()
        except Exception:
            return False

    def _stop_dpi_for_download(self) -> bool:
        """Останавливает winws/winws2 если запущены. Возвращает True если что-то остановили."""
        from winws_runtime.runtime.sync_shutdown import is_any_runtime_running_sync, shutdown_runtime_sync

        if not is_any_runtime_running_sync():
            return False

        log("⚠️ DPI (winws) мешает скачиванию — временно останавливаем", "🔁 UPDATE")
        self._emit("Остановка DPI для скачивания...")

        shutdown_runtime_sync(reason="updater_download_connectivity", include_cleanup=True)
        time.sleep(0.5)
        return True

    def _run_installer(self, setup_exe: str, version: str, tmp_dir: str) -> bool:
        """
        Запускает установщик через ShellExecuteW с правами администратора.
        """
        try:
            self._emit("Запуск установщика…")

            # Путь установки
            from config.config import MAIN_DIRECTORY

            install_dir = MAIN_DIRECTORY
            persistent_dir = os.path.join(install_dir, "_update_cache")
            os.makedirs(persistent_dir, exist_ok=True)

            persistent_exe = os.path.join(persistent_dir, "Zapret2Setup.exe")

            # Удаляем старый файл
            if os.path.exists(persistent_exe):
                try:
                    os.remove(persistent_exe)
                except Exception:
                    pass

            # Копируем установщик рядом с установленной программой,
            # чтобы не зависеть от пользовательского LOCALAPPDATA.
            shutil.copy2(setup_exe, persistent_exe)
            file_size = os.path.getsize(persistent_exe)
            log(f"📁 Установщик скопирован: {persistent_exe} ({file_size / 1024 / 1024:.1f} MB)", "🔁 UPDATE")

            # Аргументы для тихой установки.
            base_args = (
                '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /NOCANCEL '
                '/CLOSEAPPLICATIONS /RESTARTAPPLICATIONS'
            )

            # Примечание: если путь содержит пробелы, нужно экранировать кавычки
            if ' ' in install_dir:
                arguments = f'{base_args} /DIR="{install_dir}"'
            else:
                arguments = f'{base_args} /DIR={install_dir}'

            # Запускаем установщик через WinAPI с правами администратора
            success = launch_installer_winapi(persistent_exe, arguments, persistent_dir)

            if not success:
                self._emit("Не удалось запустить установщик")
                log("❌ launch_installer_winapi вернул False", "🔁❌ ERROR")
                shutil.rmtree(tmp_dir, True)
                return False

            # Очищаем temp
            shutil.rmtree(tmp_dir, True)

            log("⏳ Закрытие через 5с (дождитесь UAC)...", "🔁 UPDATE")
            QTimer.singleShot(5000, lambda: os._exit(0))

            return True

        except Exception as e:
            self._emit(f"Ошибка запуска: {e}")
            log(f"❌ Ошибка запуска установщика: {e}", "🔁❌ ERROR")
            import traceback
            log(traceback.format_exc(), "🔁❌ ERROR")
            shutil.rmtree(tmp_dir, True)
            return False
    
    def _download_update(self, release_info: dict, is_retry: bool = False) -> bool:
        if self.is_stop_requested():
            self._emit("Обновление остановлено")
            return False
        new_ver = release_info["version"]
        log(f"UpdateWorker: загрузка v{new_ver} (retry={is_retry})", "🔁 UPDATE")

        tmp_dir = tempfile.mkdtemp(prefix="zapret_upd_")
        setup_exe = os.path.join(tmp_dir, "Zapret2Setup.exe")
        
        def _prog(done, total):
            percent = done * 100 // total if total > 0 else 0
            self.progress_bytes.emit(percent, done, total)
            self._emit(f"Скачивание… {percent}%")
        
        download_urls = self._get_download_urls(release_info)

        # ── Проверяем, не блокирует ли DPI скачивание ──
        dpi_was_stopped = False
        first_url = next(((u, s) for u, s in download_urls if not u.startswith("telegram://")), None)
        if first_url and not self._test_download_connectivity(first_url[0], first_url[1]):
            dpi_was_stopped = self._stop_dpi_for_download()

        download_error = None
        for idx, (url, verify_ssl) in enumerate(download_urls):
            if self.is_stop_requested():
                shutil.rmtree(tmp_dir, True)
                self._emit("Обновление остановлено")
                return False
            if url.startswith("telegram://"):
                continue

            try:
                log(f"Попытка #{idx+1} с {url} (SSL={verify_ssl})", "🔁 UPDATE")
                
                # Для тихих автообновлений не долбим сервер — максимум 1 попытка,
                # для ручного режима можно 2.
                retries = 1 if self._silent else 2
                
                _download_with_retry(
                    url,
                    setup_exe,
                    _prog,
                    verify_ssl=verify_ssl,
                    max_retries=retries,
                    enable_slow_mirror_switch=(idx < len(download_urls) - 1),
                )
                
                download_error = None
                self.download_complete.emit()
                break
                
            except Exception as e:
                download_error = e
                log(f"❌ Ошибка: {e}", "🔁❌ ERROR")
                
                if idx < len(download_urls) - 1:
                    self._emit("Пробуем альтернативный источник...")
                    time.sleep(1)
        
        if download_error:
            if dpi_was_stopped:
                self.dpi_restart_needed.emit()

            error_msg = str(download_error)
            if "ConnectionPool" in error_msg or "Connection" in error_msg:
                error_msg = "Ошибка подключения. Проверьте интернет."

            self.download_failed.emit(error_msg)
            self._emit(f"Ошибка: {error_msg}")
            shutil.rmtree(tmp_dir, True)
            return False

        if not os.path.exists(setup_exe):
            if dpi_was_stopped:
                self.dpi_restart_needed.emit()
            error_msg = "Нет доступных источников для скачивания обновления"
            log(f"❌ {error_msg}", "🔁❌ ERROR")
            self.download_failed.emit(error_msg)
            self._emit(f"Ошибка: {error_msg}")
            shutil.rmtree(tmp_dir, True)
            return False

        # Запуск установщика
        log(f"📦 Скачивание завершено, запускаем установщик: {setup_exe}", "🔁 UPDATE")
        log(f"   Файл существует: {os.path.exists(setup_exe)}", "🔁 UPDATE")
        if os.path.exists(setup_exe):
            log(f"   Размер: {os.path.getsize(setup_exe)} байт", "🔁 UPDATE")
        result = self._run_installer(setup_exe, new_ver, tmp_dir)
        if not result and dpi_was_stopped:
            self.dpi_restart_needed.emit()
        return result

    def run(self):
        try:
            if self.is_stop_requested():
                self.finished.emit(False)
                return
            ok = self._check_and_run_update()
            self.finished.emit(ok)
        except Exception as e:
            log(f"UpdateWorker error: {e}", "🔁❌ ERROR")
            self._emit(f"Ошибка: {e}")
            self.finished.emit(False)

    def _check_and_run_update(self) -> bool:
        if self.is_stop_requested():
            self._emit("Обновление остановлено")
            return False
        self._emit("Проверка обновлений…")
        
        # ═══════════════════════════════════════════════════════════════
        # ✅ ПРОВЕРКА RATE LIMIT (пропускается если skip_rate_limit=True)
        # ═══════════════════════════════════════════════════════════════
        if not self._skip_rate_limit:
            is_auto = self._silent
            can_check, error_msg = UpdateRateLimiter.can_check_update(is_auto=is_auto)
            
            if not can_check:
                self._emit(error_msg)
                log(f"⏱️ Проверка заблокирована rate limiter: {error_msg}", "🔁 UPDATE")
                
                # Для ручных проверок показываем сообщение только в stable-канале.
                if not self._silent and not is_dev_update_channel(CHANNEL):
                    self.show_no_updates.emit(f"Rate limit: {error_msg}")
                
                return False
            
            # Записываем факт проверки
            UpdateRateLimiter.record_check(is_auto=is_auto)
        else:
            log("⏭️ Rate limiter пропущен (ручная установка)", "🔁 UPDATE")
        
        # ✅ АВТООБНОВЛЕНИЯ ИСПОЛЬЗУЮТ КЭШ, РУЧНЫЕ - НЕТ
        use_cache = self._silent  # silent=True для автопроверок
        
        if not use_cache:
            log("🔄 Принудительная проверка обновлений (кэш игнорируется)", "🔁 UPDATE")
        
        release_info = get_latest_release(CHANNEL, use_cache=use_cache)
        
        if not release_info:
            self._emit("Не удалось проверить обновления.")
            return False

        new_ver = release_info["version"]
        notes   = release_info["release_notes"]
        is_pre  = release_info["prerelease"]
        
        try:
            app_ver_norm = normalize_version(APP_VERSION)
        except ValueError:
            log(f"Invalid APP_VERSION: {APP_VERSION}", "🔁❌ ERROR")
            self._emit("Ошибка версии.")
            return False
        
        log(f"Update check: {CHANNEL}, local={app_ver_norm}, remote={new_ver}, use_cache={use_cache}", "🔁 UPDATE")

        cmp_result = compare_versions(app_ver_norm, new_ver)

        if cmp_result >= 0:
            self._emit(f"✅ Обновлений нет (v{app_ver_norm})")
            if not self._silent:
                self.show_no_updates.emit(app_ver_norm)
            return False

        if self.is_stop_requested():
            self._emit("Обновление остановлено")
            return False

        return self._download_update(release_info)

# ──────────────────────────── public-API ──────────────────────────────────
# ПРИМЕЧАНИЕ: Автообновление при запуске ОТКЛЮЧЕНО.
# Обновления проверяются и устанавливаются только через вкладку "Серверы" (updater/ui/page.py)
# Функция run_update_async оставлена для обратной совместимости, но не используется.
