# winws_runtime/health/antivirus_detection.py
"""Обнаружение активного антивируса по uninstall-реестру и процессам."""

from typing import Optional

from utils.windows_process_probe import iter_process_names_winapi, iter_uninstall_display_names

_ANTIVIRUS_PRODUCT_MARKERS = (
    ("kaspersky", "Kaspersky"),
    ("каспер", "Kaspersky"),
    ("dr.web", "Dr.Web"),
    ("eset", "ESET"),
    ("norton", "Norton"),
    ("avast", "Avast"),
    ("avg", "AVG"),
    ("bitdefender", "Bitdefender"),
    ("mcafee", "McAfee"),
    ("comodo", "Comodo"),
    ("malwarebytes", "Malwarebytes"),
    ("trend micro", "Trend Micro"),
    ("360 total security", "360 Total Security"),
)

_ANTIVIRUS_PROCESS_MARKERS = {
    "avp.exe": "Kaspersky",
    "ksde.exe": "Kaspersky",
    "klnagent.exe": "Kaspersky",
    "drweb32.exe": "Dr.Web",
    "spideragent.exe": "Dr.Web",
    "egui.exe": "ESET",
    "ekrn.exe": "ESET",
    "nortonsecurity.exe": "Norton",
    "navw32.exe": "Norton",
    "avastui.exe": "Avast",
    "avgui.exe": "AVG",
    "bdagent.exe": "Bitdefender",
    "vsserv.exe": "Bitdefender",
    "uihost.exe": "McAfee",
    "mfemms.exe": "McAfee",
    "cmdagent.exe": "Comodo",
    "mbam.exe": "Malwarebytes",
    "mbamtray.exe": "Malwarebytes",
    "pccntmon.exe": "Trend Micro",
    "360tray.exe": "360 Total Security",
    "360sd.exe": "360 Total Security",
}


def _find_known_antivirus_name() -> Optional[str]:
    """Возвращает имя обнаруженного антивируса по uninstall-реестру и WinAPI-процессам."""
    try:
        for display_name in iter_uninstall_display_names():
            normalized = str(display_name or "").strip().casefold()
            for marker, title in _ANTIVIRUS_PRODUCT_MARKERS:
                if marker in normalized:
                    return title
    except Exception:
        pass

    try:
        for process_name in iter_process_names_winapi():
            normalized = str(process_name or "").strip().casefold()
            match = _ANTIVIRUS_PROCESS_MARKERS.get(normalized)
            if match:
                return match
    except Exception:
        pass

    return None


def _is_windows_defender_active() -> bool:
    """Возвращает True, если Windows Defender выглядит активным по прямым Windows-признакам."""
    try:
        from startup.bfe_util import is_service_running

        if is_service_running("WinDefend"):
            return True
    except Exception:
        pass

    try:
        for process_name in iter_process_names_winapi():
            normalized = str(process_name or "").strip().casefold()
            if normalized in {"msmpeng.exe", "nisserv.exe", "securityhealthservice.exe"}:
                return True
    except Exception:
        pass

    try:
        from windows_features.defender_manager import WindowsDefenderManager

        return not bool(WindowsDefenderManager().is_defender_disabled())
    except Exception:
        return False


def _detect_active_antivirus() -> Optional[str]:
    """Return name of active antivirus or None."""
    try:
        antivirus_name = _find_known_antivirus_name()
        if antivirus_name:
            return antivirus_name
        if _is_windows_defender_active():
            return "Windows Defender"
    except Exception:
        pass
    return None
