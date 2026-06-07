# telegram_proxy/service.py
"""Windows service management for Telegram WSS proxy.

Creates/removes a Windows service so the proxy can run independently
of the GUI, surviving reboots.
"""

import os
import sys
import logging

log = logging.getLogger("tg_proxy.service")

TG_SERVICE_NAME = "ZapretTelegramProxy"
TG_SERVICE_DISPLAY = "Zapret Telegram Proxy"
TG_SERVICE_DESC = "Telegram WebSocket proxy for bypassing IP blocks"


def _get_python_exe() -> str:
    """Get path to current Python executable."""
    return sys.executable


def _get_proxy_module_path() -> str:
    """Get path to telegram_proxy package."""
    return os.path.dirname(os.path.abspath(__file__))


def build_service_args(port: int = 1353, mode: str = "socks5", mtproxy_secret: str = "") -> str:
    args = f"-m telegram_proxy --port {int(port)} --mode {str(mode or 'socks5')}"
    secret = str(mtproxy_secret or "").strip()
    if str(mode or "").strip().lower() == "mtproxy" and secret:
        args += f" --secret {secret}"
    return args


def create_tg_proxy_service(port: int = 1353, mode: str = "socks5", mtproxy_secret: str = "") -> bool:
    """Create a Windows service for the Telegram proxy.

    Uses NSSM if available, falls back to native Windows API.
    """
    try:
        python_exe = _get_python_exe()
        # Service runs: python.exe -m telegram_proxy --port PORT --mode MODE
        args = build_service_args(port=port, mode=mode, mtproxy_secret=mtproxy_secret)
        work_dir = os.path.dirname(_get_proxy_module_path())

        # Try NSSM first (better restart handling)
        try:
            from autostart.nssm_service import create_service_with_nssm, find_nssm
            nssm_path = find_nssm()
            if nssm_path:
                ok = create_service_with_nssm(
                    service_name=TG_SERVICE_NAME,
                    display_name=TG_SERVICE_DISPLAY,
                    exe_path=python_exe,
                    args=args,
                    work_dir=work_dir,
                    description=TG_SERVICE_DESC,
                    auto_start=True,
                )
                if ok:
                    log.info("TG proxy service created via NSSM")
                    return True
        except (ImportError, Exception) as e:
            log.debug(f"NSSM not available: {e}")

        # Fallback: native Windows API
        try:
            from autostart.service_api import create_zapret_service
            binary_path = f'"{python_exe}" {args}'
            ok = create_zapret_service(
                service_name=TG_SERVICE_NAME,
                display_name=TG_SERVICE_DISPLAY,
                exe_path=binary_path,
                args="",
                description=TG_SERVICE_DESC,
                auto_start=True,
            )
            if ok:
                log.info("TG proxy service created via Windows API")
                return True
        except (ImportError, Exception) as e:
            log.warning(f"Windows API service creation failed: {e}")

        return False
    except Exception as e:
        log.error(f"Failed to create TG proxy service: {e}")
        return False


def remove_tg_proxy_service() -> bool:
    """Remove the Telegram proxy Windows service."""
    try:
        from autostart.service_api import stop_service, delete_service, service_exists

        if not service_exists(TG_SERVICE_NAME):
            return True  # Already doesn't exist

        stop_service(TG_SERVICE_NAME)
        ok = delete_service(TG_SERVICE_NAME)
        if ok:
            log.info("TG proxy service removed")
        return ok
    except Exception as e:
        log.error(f"Failed to remove TG proxy service: {e}")
        return False


def is_tg_proxy_service_installed() -> bool:
    """Check if the service is installed."""
    try:
        from autostart.service_api import service_exists
        return service_exists(TG_SERVICE_NAME)
    except Exception:
        return False


def is_tg_proxy_service_running() -> bool:
    """Check if the service is currently running."""
    try:
        from autostart.service_api import get_service_state
        import win32service
        state = get_service_state(TG_SERVICE_NAME)
        return state == win32service.SERVICE_RUNNING
    except Exception:
        return False


def start_tg_proxy_service() -> bool:
    """Start the installed service."""
    try:
        from autostart.service_api import start_service
        return start_service(TG_SERVICE_NAME)
    except Exception as e:
        log.error(f"Failed to start TG proxy service: {e}")
        return False


def stop_tg_proxy_service() -> bool:
    """Stop the running service."""
    try:
        from autostart.service_api import stop_service
        return stop_service(TG_SERVICE_NAME)
    except Exception as e:
        log.error(f"Failed to stop TG proxy service: {e}")
        return False
