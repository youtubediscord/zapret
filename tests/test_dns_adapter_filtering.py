from __future__ import annotations

import ctypes
import importlib
import sys
import types
import unittest
from types import SimpleNamespace


class _FakeWindowsApi:
    def __getattr__(self, _name: str):
        return self


def _load_dns_core():
    try:
        import winreg  # noqa: F401
    except ModuleNotFoundError:
        sys.modules.setdefault("winreg", types.SimpleNamespace())

    if not hasattr(ctypes, "windll"):
        ctypes.windll = _FakeWindowsApi()

    sys.modules.pop("dns.dns_core", None)
    return importlib.import_module("dns.dns_core")


class _FakeWmi:
    def __init__(self, adapters):
        self._adapters = adapters

    def Win32_NetworkAdapter(self, PhysicalAdapter=True):  # noqa: N802
        return list(self._adapters)


class DnsAdapterFilteringTests(unittest.TestCase):
    def test_dns_changes_target_only_wifi_and_ethernet_adapters(self) -> None:
        dns_core = _load_dns_core()
        manager = dns_core.DNSManager()
        manager._wmi_conn = _FakeWmi(
            [
                SimpleNamespace(
                    NetConnectionID="Ethernet",
                    Description="Realtek PCIe GbE Family Controller",
                    NetConnectionStatus=7,
                    PNPDeviceID=r"PCI\VEN_10EC&DEV_8168",
                    ServiceName="rt640x64",
                    AdapterTypeID=0,
                ),
                SimpleNamespace(
                    NetConnectionID="Wi-Fi",
                    Description="Intel(R) Wi-Fi 6 AX200",
                    NetConnectionStatus=2,
                    PNPDeviceID=r"PCI\VEN_8086&DEV_2723",
                    ServiceName="Netwtw10",
                    AdapterTypeID=9,
                ),
                SimpleNamespace(
                    NetConnectionID="Пидорашка",
                    Description="WAN Miniport (PPPOE)",
                    NetConnectionStatus=2,
                    PNPDeviceID=r"SWD\MSRRAS\MS_PPPOEMINIPORT",
                    ServiceName="RasPppoe",
                    AdapterTypeID=None,
                ),
                SimpleNamespace(
                    NetConnectionID="Сетевое подключение Bluetooth",
                    Description="Bluetooth Device (Personal Area Network)",
                    NetConnectionStatus=7,
                    PNPDeviceID=r"BTH\MS_BTHPAN",
                    ServiceName="BthPan",
                    AdapterTypeID=None,
                ),
                SimpleNamespace(
                    NetConnectionID="vEthernet (WSL)",
                    Description="Hyper-V Virtual Ethernet Adapter",
                    NetConnectionStatus=2,
                    PNPDeviceID=r"ROOT\VMS_MP",
                    ServiceName="VMSMP",
                    AdapterTypeID=0,
                ),
            ]
        )

        adapters = manager.get_network_adapters_fast(
            include_ignored=False,
            include_disconnected=True,
        )

        self.assertEqual(
            [name for name, _description in adapters],
            ["Ethernet", "Wi-Fi"],
        )


if __name__ == "__main__":
    unittest.main()
