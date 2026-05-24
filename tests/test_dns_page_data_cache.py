from __future__ import annotations

import unittest


class DnsPageDataCacheTests(unittest.TestCase):
    def test_warmed_page_data_is_consumed_once(self) -> None:
        from dns import runtime

        state = runtime.NetworkPageData(
            adapters=[("Ethernet", "Intel")],
            dns_info={"Ethernet": {"IPv4": ["1.1.1.1"], "IPv6": []}},
            ipv6_available=True,
            force_dns_active=False,
        )

        runtime.clear_warmed_page_data_cache()
        runtime.store_warmed_page_data(state)

        self.assertIs(runtime.consume_warmed_page_data(), state)
        self.assertIsNone(runtime.consume_warmed_page_data())


if __name__ == "__main__":
    unittest.main()
