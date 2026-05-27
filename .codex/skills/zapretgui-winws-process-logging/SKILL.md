---
name: zapretgui-winws-process-logging
description: Use when changing or diagnosing ZapretGUI winws/winws2 process output, the Logs page winws panel, stdout/stderr pipes, --debug=@file, --dry-run, preset handoff, WinDivert launch behavior, or reports that opening Logs changes internet/process behavior.
---

# ZapretGUI Winws Process Logging

Используй этот skill, когда проблема связана с запуском `winws1` / `winws2`,
логами процесса, страницей "Логи", переключением пресетов или странным
поведением вида "интернет оживает после открытия логов".

## Что было проблемой

В GUI нельзя держать долгоживущий `winws2` на `stdout=PIPE` / `stderr=PIPE`,
если эти потоки читает страница интерфейса.

Плохая цепочка выглядела так:

1. Runner запускал `winws2` с `stdout` / `stderr` как pipe.
2. `WinwsOutputWorker` на странице "Логи" был читателем этих pipe.
3. Если страница "Логи" не открыта или worker не активен, буфер pipe мог
   заполниться.
4. `winws2` мог зависнуть на записи сообщений в `stdout` / `stderr`.
5. Открытие страницы "Логи" начинало читать pipe, и у пользователя это
   выглядело так, будто интернет восстановился после перехода в логи.

Это не баг `winws2` сам по себе. Это ошибка владения процессом в GUI:
сетевой процесс не должен зависеть от того, открыта ли страница логов.

## Что говорит оригинальный zapret2

Проверяй это в `/mnt/g/Privacy/zapret2_orig_bolvan`.

Важные факты из оригинала:

- `@<config_file>` должен быть единственным аргументом командной строки.
  Остальные аргументы рядом с ним игнорируются.
- Поэтому дополнительные параметры для `winws2` нужно писать внутрь временного
  `@config`, а не добавлять вторым аргументом к `winws2.exe @file`.
- `--debug=0|1|syslog|@<filename>`:
  `--debug=1` пишет в консоль, `--debug=@file` пишет в файл.
- Ошибки `DLOG_ERR` и важные сообщения `DLOG_CONDUP` дублируются в консоль
  независимо от выбранной цели debug-лога.
- Ошибки пишутся в `stderr`.
- `--dry-run` только проверяет параметры и наличие файлов, затем выходит.
  Он не запускает реальный перехват и не проверяет синтаксис Lua.
- `--dry-run` нельзя добавлять в настоящий рабочий запуск.
- `--wf-dup-check` по умолчанию включен и не дает запустить второй `winws2`
  с таким же WinDivert-фильтром.

Полезные места в оригинале:

- `docs/manual.md`: `@config`, `--debug`, `--dry-run`, правила вывода ошибок.
- `nfq2/nfqws.c`: разбор `@config`, `--debug`, `--dry-run`,
  `--wf-dup-check`, проверка дубликатов через mutex.
- `nfq2/params.c`: вывод `DLOG`, `DLOG_CONDUP`, `DLOG_ERR`.

## Правильная архитектура в ZapretGUI

Долгоживущий прямой запуск `winws1` / `winws2` должен быть максимально
независимым от GUI:

- `stdin=subprocess.DEVNULL`
- `stdout=subprocess.DEVNULL`
- `stderr=subprocess.DEVNULL`

Страница "Логи" может показывать логи приложения и статус процесса, но не
должна владеть live-потоком `stdout` / `stderr` прямого runner-а.

Если нужен лог самого `winws2`, безопасный путь такой:

1. Включить `--debug=@logs/...` внутри временного `@config`.
2. Читать этот файл снимками, с паузами и backoff.
3. Если файл не меняется, ничего не писать в лог GUI.
4. Не держать `stdout` / `stderr` процесса открытыми ради UI.

Короткий диагностический запуск с pipe разрешен только для `--dry-run`, потому
что это отдельный короткий процесс с timeout. Он должен завершиться до
настоящего запуска.

## Что можно

- `subprocess.run(..., stdout=PIPE, stderr=PIPE, timeout=...)` для короткого
  `--dry-run`.
- Добавлять `--dry-run`, `--debug=@file`, `--wf-dup-check=0` внутрь временного
  `@config`.
- Читать debug-файл `winws2` снимками, если пользователь явно включил такой
  режим или это нужно для диагностики.
- Хранить последние строки диагностического файла в памяти GUI, если это не
  влияет на процесс.

## Что нельзя

- `Popen(..., stdout=PIPE, stderr=PIPE)` для долгоживущего прямого `winws1` /
  `winws2`.
- Делать страницу "Логи" единственным читателем pipe процесса.
- Лечить проблему бесконечным drain-worker-ом как основной архитектурой.
  Это временный обход, а не правильное владение процессом.
- Добавлять `--dry-run` в настоящий рабочий запуск.
- Передавать `--debug` или другие параметры рядом с `@config` вторым аргументом.
- Делать так, чтобы открытие или закрытие страницы GUI влияло на сеть.

## Где смотреть в ZapretGUI

- `src/winws_runtime/runners/zapret2_runner.py` - прямой запуск `winws2`,
  `--dry-run`, временный `@config`.
- `src/winws_runtime/runners/zapret1_runner.py` - прямой запуск `winws1`.
- `src/winws_runtime/runners/runner_base.py` - общее состояние runner-а.
- `src/log/ui/page.py` - страница "Логи".
- `src/log/commands.py` - команды страницы логов.
- `src/log/winws_output_worker.py` - старый опасный паттерн для прямого runner-а;
  не подключай его к долгоживущему `winws`.
- `src/profile/settings.py` и `src/presets/preset_text_ops.py` - места, где
  может включаться debug-лог через текст пресета.

## Быстрая проверка после правок

Сначала проверь, что долгоживущий прямой запуск не вернулся на pipe:

```bash
rg -n "stdout=subprocess\\.PIPE|stderr=subprocess\\.PIPE|WinwsOutputWorker|get_process\\(" src/winws_runtime src/log tests
```

Ожидание: pipe допустим только для короткого `--dry-run` или тестов,
а не для рабочего `Popen` прямого `winws1` / `winws2`.

Потом прогоняй фокусные проверки:

```bash
PYTHONPATH=src python -m unittest \
  tests.test_winws2_launch_preset_validation \
  tests.test_log_page_runtime \
  tests.test_preset_switch_runtime \
  tests.test_windivert_service_recovery \
  tests.test_preset_runtime_coordinator \
  tests.test_preset_status_bar

PYTHONPATH=src python -m app.architecture_checks
```

## Быстрая сверка с оригиналом

Если нужно перепроверить факты по `winws2`:

```bash
rg -n -- "--debug|--dry-run|--wf-dup-check|@<config_file>|DLOG_ERR|LOG_TARGET|CreateMutexA|WinDivertOpen" \
  /mnt/g/Privacy/zapret2_orig_bolvan/docs/manual.md \
  /mnt/g/Privacy/zapret2_orig_bolvan/nfq2
```

Главное правило: `winws2` должен работать сам по себе. GUI может запускать,
останавливать и наблюдать, но не должен становиться частью его сетевого
контура через открытые pipe.
