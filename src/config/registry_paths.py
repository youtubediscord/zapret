from config.build_info import CHANNEL
from config.config import CHANNEL_DEV


def is_dev_build_channel() -> bool:
    """True для dev-канала сборки."""
    return str(CHANNEL or "").strip().lower() == CHANNEL_DEV


REGISTRY_PATH = r"Software\Zapret2DevReg" if is_dev_build_channel() else r"Software\Zapret2Reg"
REGISTRY_PATH_GUI = rf"{REGISTRY_PATH}\GUI"
REGISTRY_PATH_STRATEGIES = rf"{REGISTRY_PATH}\Strategies"
REGISTRY_PATH_WINDOW = rf"{REGISTRY_PATH}\Window"
