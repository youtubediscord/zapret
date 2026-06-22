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
        self.assertEqual(
            normalize_filter_value("lists/ipset-all.txt", "hostlist"),
            "lists/ipset-all.txt",
        )

    def test_ipset_filter_preserves_explicit_other_file_name(self) -> None:
        from profile.editable_settings import normalize_filter_value

        self.assertEqual(
            normalize_filter_value("lists/other.txt", "ipset"),
            "lists/other.txt",
        )

    def test_exclude_filter_preserves_explicit_file_names(self) -> None:
        from profile.editable_settings import normalize_filter_value

        self.assertEqual(
            normalize_filter_value("lists/netrogat.txt", "ipset", filter_role="exclude"),
            "lists/netrogat.txt",
        )
        self.assertEqual(
            normalize_filter_value("lists/custom-exclude.txt", "hostlist", filter_role="exclude"),
            "lists/custom-exclude.txt",
        )
        self.assertEqual(
            normalize_filter_value(
                "lists/ipset-ru.txt,lists/ipset-dns.txt,lists/ipset-exclude.txt",
                "hostlist",
                filter_role="exclude",
            ),
            "lists/ipset-ru.txt,lists/ipset-dns.txt,lists/ipset-exclude.txt",
        )

    def test_file_filter_value_rejects_domain_without_list_extension(self) -> None:
        from profile.editable_settings import filter_value_is_file_reference

        self.assertTrue(filter_value_is_file_reference("lists/ipset-discord.txt"))
        self.assertTrue(filter_value_is_file_reference("ipset-discord.txt"))
        self.assertFalse(filter_value_is_file_reference("discord.com"))


if __name__ == "__main__":
    unittest.main()
