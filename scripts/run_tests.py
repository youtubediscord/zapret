"""Прогон всего тестового пакета с изоляцией по файлам.

На Python 3.14 + PyQt6 6.11 длинный однопроцессный прогон Qt-тестов
повреждает кучу на C++-стороне (осиротевшие обёртки, гонки потоков
QFileSystemWatcher/QThread) и падает с access violation / fail-fast
0xC0000409 — при этом каждый файл в одиночку проходит.  pytest-forked не
работает на Windows, а воркеры pytest-xdist переиспользуют процесс и
накапливают то же повреждение.  Поэтому: один pytest-процесс на файл,
несколько файлов параллельно.

Использование:
    python scripts/run_tests.py            # весь пакет tests/
    python scripts/run_tests.py -j 8       # степень параллелизма
    python scripts/run_tests.py tests/test_foo.py tests/test_bar.py

Код выхода: 0 — все файлы прошли, 1 — есть падения.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = REPO_ROOT / "tests"

# Консоль Windows может быть в cp1251 — вывод дочерних pytest в UTF-8.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass


def _run_file(path: Path) -> tuple[Path, int, str, float]:
    started = time.monotonic()
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(path), "-q", "-p", "no:cacheprovider"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    return path, proc.returncode, output, time.monotonic() - started


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", help="конкретные файлы тестов (по умолчанию весь tests/)")
    parser.add_argument("-j", "--jobs", type=int, default=max(2, (os.cpu_count() or 4) // 2))
    args = parser.parse_args(argv)

    if args.files:
        files = [Path(f).resolve() for f in args.files]
    else:
        files = sorted(TESTS_DIR.glob("test_*.py"))
    if not files:
        print("Нет файлов тестов.", file=sys.stderr)
        return 2

    print(f"{len(files)} файлов, параллелизм {args.jobs}", flush=True)
    failed: list[tuple[Path, int, str]] = []
    started = time.monotonic()
    done = 0
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for path, code, output, duration in pool.map(_run_file, files):
            done += 1
            rel = path.relative_to(REPO_ROOT)
            if code == 0:
                print(f"[{done}/{len(files)}] OK   {rel} ({duration:.1f}s)", flush=True)
            else:
                failed.append((path, code, output))
                print(f"[{done}/{len(files)}] FAIL {rel} (exit {code}, {duration:.1f}s)", flush=True)

    total = time.monotonic() - started
    if failed:
        print(f"\n{'=' * 70}\nУпавшие файлы ({len(failed)}):", flush=True)
        for path, code, output in failed:
            rel = path.relative_to(REPO_ROOT)
            print(f"\n--- {rel} (exit {code}) ---", flush=True)
            lines = output.strip().splitlines()
            print("\n".join(lines[-30:]), flush=True)
        print(f"\n{len(failed)} из {len(files)} файлов упали за {total:.0f}s", flush=True)
        return 1

    print(f"\nВсе {len(files)} файлов прошли за {total:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
