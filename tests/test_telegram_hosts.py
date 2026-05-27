from __future__ import annotations

import unittest
from unittest.mock import patch

from telegram_proxy.telegram_hosts import TELEGRAM_RELAY_IP, ensure_telegram_hosts


class TelegramHostsTests(unittest.TestCase):
    def test_ensure_hosts_writes_telegram_cdn_and_download_domains(self) -> None:
        written: list[str] = []

        with (
            patch("hosts.public.read_hosts_file", return_value=""),
            patch("hosts.public.write_hosts_file", side_effect=lambda text: written.append(text) or True),
        ):
            changed, message = ensure_telegram_hosts()

        self.assertTrue(changed)
        self.assertIn("добавлено", message)
        self.assertEqual(len(written), 1)
        for domain in (
            "cdn1.telesco.pe",
            "cdn2.telesco.pe",
            "cdn3.telesco.pe",
            "cdn4.telesco.pe",
            "desktop.telegram.org",
            "macos.telegram.org",
        ):
            self.assertIn(f"{TELEGRAM_RELAY_IP} {domain}", written[0])


if __name__ == "__main__":
    unittest.main()
