from __future__ import annotations

import unittest
from unittest.mock import patch

from windows_features.state_media_blocker import (
    RussianStateMediaBlockerManager,
    build_hosts_content_with_state_media_block,
    get_state_media_domains,
)


class StateMediaBlockerTests(unittest.TestCase):
    def test_build_hosts_content_adds_expected_domains_once(self) -> None:
        content = "127.0.0.1 localhost\n"

        first = build_hosts_content_with_state_media_block(content, enabled=True)
        second = build_hosts_content_with_state_media_block(first, enabled=True)

        self.assertEqual(first, second)
        self.assertIn("127.0.0.1 tass.ru", first)
        self.assertIn("::1 russian.rt.com", first)
        self.assertIn("127.0.0.1 1tv.ru", first)
        self.assertEqual(first.count("zapretgui:russian-state-media-block begin"), 1)

    def test_build_hosts_content_removes_only_own_block(self) -> None:
        content = "\n".join(
            [
                "127.0.0.1 localhost",
                "# user row",
                "127.0.0.1 example.test",
                "",
            ]
        )
        blocked = build_hosts_content_with_state_media_block(content, enabled=True)

        restored = build_hosts_content_with_state_media_block(blocked, enabled=False)

        self.assertIn("127.0.0.1 localhost", restored)
        self.assertIn("127.0.0.1 example.test", restored)
        self.assertNotIn("tass.ru", restored)
        self.assertNotIn("zapretgui:russian-state-media-block", restored)

    def test_manager_writes_hosts_and_persists_memory(self) -> None:
        written: list[str] = []
        manager = RussianStateMediaBlockerManager(
            read_hosts_file=lambda: "127.0.0.1 localhost\n",
            write_hosts_file=lambda content: written.append(content) is None or True,
        )

        with patch("settings.store.set_russian_state_media_blocked", return_value=True) as save:
            success, message = manager.enable_blocking()

        self.assertTrue(success)
        self.assertIn("включена", message)
        self.assertEqual(save.call_args.args, (True,))
        self.assertIn("127.0.0.1 rg.ru", written[-1])

    def test_domain_list_has_no_duplicates(self) -> None:
        domains = get_state_media_domains()

        self.assertEqual(len(domains), len(set(domains)))
        self.assertIn("tass.ru", domains)
        self.assertIn("vesti.ru", domains)


if __name__ == "__main__":
    unittest.main()
