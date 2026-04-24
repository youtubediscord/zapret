from __future__ import annotations


TCP_PHASE_TAB_ORDER: list[tuple[str, str]] = [
    ("fake", "FAKE"),
    ("multisplit", "MULTISPLIT"),
    ("multidisorder", "MULTIDISORDER"),
    ("multidisorder_legacy", "LEGACY"),
    ("tcpseg", "TCPSEG"),
    ("oob", "OOB"),
    ("other", "OTHER"),
]

TCP_PHASE_COMMAND_ORDER: list[str] = [
    "fake",
    "multisplit",
    "multidisorder",
    "multidisorder_legacy",
    "tcpseg",
    "oob",
    "other",
]

TCP_EMBEDDED_FAKE_TECHNIQUES: set[str] = {
    "fakedsplit",
    "fakeddisorder",
    "hostfakesplit",
}
