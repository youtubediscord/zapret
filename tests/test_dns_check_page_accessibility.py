import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from dns.ui.dns_check_page import DNSCheckPage


class _DnsFeatureStub:
    pass


class DNSCheckPageAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_actions_status_and_results_are_named_for_screen_reader(self) -> None:
        page = DNSCheckPage(dns_feature=_DnsFeatureStub())
        self.addCleanup(page.deleteLater)

        self.assertEqual(page.check_button.accessibleName(), "Начать полную проверку DNS")
        self.assertIn("расширенный отчёт", page.check_button.accessibleDescription())
        self.assertEqual(page.quick_check_button.accessibleName(), "Начать быструю проверку DNS")
        self.assertIn("текущего системного DNS", page.quick_check_button.accessibleDescription())
        self.assertEqual(page.save_button.accessibleName(), "Сохранить результаты проверки DNS")
        self.assertIn("текстовый файл", page.save_button.accessibleDescription())
        self.assertEqual(page.status_label.accessibleName(), "Статус проверки DNS: Готово к проверке")
        self.assertEqual(page.result_text.accessibleName(), "Результаты проверки DNS")
        self.assertIn("отчёт DNS-проверки", page.result_text.accessibleDescription())


if __name__ == "__main__":
    unittest.main()
