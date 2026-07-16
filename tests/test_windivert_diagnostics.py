"""Тесты единого центра диагностики WinDivert (windivert_diagnostics).

Покрытие по spec windivert-check-center:
- AC6a: полнота декларативной таблицы кодов;
- AC6b/AC8: describe_windivert_error содержит десятичный код и осмысленную
  русскую подсказку для 5/1058/1060/1072/1275/577;
- AC6c: transient-набор readiness recovery == {5, 1058, 1060, 1753, 1072}.
"""

import unittest
from unittest.mock import patch

from winws_runtime.health import launch_conflicts, windivert_diagnostics
from winws_runtime.health.windivert_diagnostics import (
    TRANSIENT_WINDIVERT_READINESS_CODES,
    WINDIVERT_ERROR_TABLE,
    describe_windivert_error,
    describe_windivert_readiness_failure,
)

# Коды из AC2 плюс дополнительные коды диагностики exit-кодов.
_REQUIRED_TABLE_CODES = (5, 577, 654, 1058, 1060, 1068, 1072, 1275, 8, 31, 87, 161, 1067)

# Смысловая инварианта пользовательских текстов (AC8): код → ключевое слово
# readiness-подсказки (доступ / отключена служба / не установлен /
# помечена на удаление / HVCI / подпись).
_READINESS_SEMANTIC_KEYWORDS = {
    5: "доступ",
    1058: "отключена",
    1060: "не установлен",
    1072: "удаление",
    1275: "HVCI",
    577: "подпис",
}


class WinDivertErrorTableTests(unittest.TestCase):
    def test_table_contains_all_required_codes(self) -> None:
        for code in _REQUIRED_TABLE_CODES:
            record = WINDIVERT_ERROR_TABLE.get(code)
            self.assertIsNotNone(record, f"нет записи для кода {code}")
            self.assertEqual(record.code, code)
            self.assertTrue(record.cause.strip(), f"пустая причина для кода {code}")
            self.assertTrue(record.solution.strip(), f"пустое решение для кода {code}")

    def test_codes_are_defined_once_via_named_constants(self) -> None:
        self.assertEqual(windivert_diagnostics._ERROR_ACCESS_DENIED, 5)
        self.assertEqual(windivert_diagnostics._ERROR_INVALID_IMAGE_HASH, 577)
        self.assertEqual(windivert_diagnostics._ERROR_DRIVER_FAILED_PRIOR_UNLOAD, 654)
        self.assertEqual(windivert_diagnostics._ERROR_SERVICE_DISABLED, 1058)
        self.assertEqual(windivert_diagnostics._ERROR_SERVICE_DOES_NOT_EXIST, 1060)
        self.assertEqual(windivert_diagnostics._ERROR_SERVICE_DEPENDENCY_FAIL, 1068)
        self.assertEqual(windivert_diagnostics._ERROR_SERVICE_MARKED_FOR_DELETE, 1072)
        self.assertEqual(windivert_diagnostics._ERROR_DRIVER_BLOCKED, 1275)
        self.assertEqual(windivert_diagnostics._ERROR_EPT_S_NOT_REGISTERED, 1753)

    def test_system_ops_imports_canonical_1072_constant(self) -> None:
        from winws_runtime.runtime import system_ops

        self.assertIs(
            system_ops._ERROR_SERVICE_MARKED_FOR_DELETE,
            windivert_diagnostics._ERROR_SERVICE_MARKED_FOR_DELETE,
        )


class DescribeWindivertErrorTests(unittest.TestCase):
    def test_readiness_text_contains_code_and_russian_hint(self) -> None:
        for code, keyword in _READINESS_SEMANTIC_KEYWORDS.items():
            text = describe_windivert_error(code, "readiness")
            self.assertIn(str(code), text, f"нет кода {code} в тексте: {text}")
            self.assertIn(keyword, text, f"нет ключевого слова '{keyword}' для {code}: {text}")
            self.assertTrue(WINDIVERT_ERROR_TABLE[code].short_hint_ru.strip())

    def test_exit_text_contains_code_and_solution(self) -> None:
        for code in _READINESS_SEMANTIC_KEYWORDS:
            record = WINDIVERT_ERROR_TABLE[code]
            text = describe_windivert_error(code, "exit")
            self.assertIn(str(code), text)
            self.assertIn(record.cause, text)
            self.assertIn(record.solution, text)

    def test_unknown_code_still_mentions_code(self) -> None:
        self.assertIn("4242", describe_windivert_error(4242, "exit"))
        self.assertIn("4242", describe_windivert_error(4242, "readiness"))

    def test_readiness_generic_text_keeps_probe_stage(self) -> None:
        text = describe_windivert_error(1753, "readiness", probe_stage="network_open")
        self.assertIn("1753", text)
        self.assertIn("network_open", text)
        self.assertIn("WinDivert ещё не готов к открытию фильтра", text)

    def test_exit_diagnosis_uses_table_base_texts(self) -> None:
        from winws_runtime.health.process_health_check import diagnose_winws_exit

        for code in (1275, 654, 1067):
            diagnosis = diagnose_winws_exit(code, "")
            self.assertIsNotNone(diagnosis)
            self.assertEqual(diagnosis.cause, WINDIVERT_ERROR_TABLE[code].cause)
            self.assertEqual(diagnosis.solution, WINDIVERT_ERROR_TABLE[code].solution)


class TransientReadinessCodesTests(unittest.TestCase):
    def test_transient_set_matches_frozen_recovery_codes(self) -> None:
        self.assertEqual(
            TRANSIENT_WINDIVERT_READINESS_CODES,
            frozenset({5, 1058, 1060, 1753, 1072}),
        )

    def test_non_transient_probe_skips_recovery_cycle(self) -> None:
        from winws_runtime.runtime.system_ops import WinDivertRuntimeProbeResult

        blocked_probe = WinDivertRuntimeProbeResult(
            installed=True,
            ready=False,
            error_code=1275,
            stage="network_open",
        )
        calls = []
        result = windivert_diagnostics.retry_windivert_spawn_readiness_after_recovery(
            blocked_probe,
            aggressive_cleanup=lambda: calls.append("cleanup"),
            wait_after_cleanup=lambda: calls.append("wait"),
        )
        self.assertIs(result, blocked_probe)
        self.assertEqual(calls, [])


class ReadinessFailureDescriptionTests(unittest.TestCase):
    def test_failure_text_for_disabled_service_probe(self) -> None:
        from winws_runtime.runtime.system_ops import WinDivertRuntimeProbeResult

        probe = WinDivertRuntimeProbeResult(
            installed=False,
            ready=False,
            error_code=1058,
            stage="network_open",
        )
        with patch.object(launch_conflicts, "build_windivert_conflict_hint", return_value=None):
            message = describe_windivert_readiness_failure(probe)

        self.assertIn("1058", message)
        self.assertIn("служба WinDivert отключена в системе", message)

    def test_conflict_hint_is_appended_when_found(self) -> None:
        hint = "Возможный конфликт: GoodbyeDPI.exe (PID 7, C:\\G\\GoodbyeDPI.exe) держит WinDivert — закройте эту программу"
        with patch.object(launch_conflicts, "build_windivert_conflict_hint", return_value=hint):
            message = describe_windivert_readiness_failure(None)

        self.assertIn("WinDivert ещё не готов к открытию фильтра", message)
        self.assertIn("GoodbyeDPI.exe", message)


if __name__ == "__main__":
    unittest.main()
