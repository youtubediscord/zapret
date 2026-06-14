import unittest


class ProfileEditableSettingsTests(unittest.TestCase):
    def test_ipset_filter_preserves_explicit_file_name(self) -> None:
        from profile.editable_settings import normalize_filter_value

        self.assertEqual(
            normalize_filter_value("lists/cloudflare-ipset.txt", "ipset"),
            "lists/cloudflare-ipset.txt",
        )
        self.assertEqual(
            normalize_filter_value("lists/youtube.txt", "ipset"),
            "lists/youtube.txt",
        )

    def test_hostlist_filter_preserves_explicit_ipset_prefixed_file_name(self) -> None:
        from profile.editable_settings import normalize_filter_value

        self.assertEqual(
            normalize_filter_value("lists/ipset-youtube.txt", "hostlist"),
            "lists/ipset-youtube.txt",
        )


if __name__ == "__main__":
    unittest.main()
