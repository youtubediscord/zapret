---
name: zapretgui-telegram-socks-servers
description: "Use when diagnosing or changing ZapretGUI bundled Telegram SOCKS5 upstream servers, especially UK 144.31.213.169, Norway 31.76.5.8, Netherlands 94.156.154.147, TLS-wrapped SOCKS5 on port 443, stunnel, 3proxy, zapret-socks-stunnel, server limits, or errors like bad SOCKS version 72."
---

# ZapretGUI Telegram SOCKS Servers

## Core Rule

Treat these servers as TLS-wrapped SOCKS5 endpoints for ZapretGUI Telegram Proxy:

```text
uk  Великобритания  144.31.213.169:443
no  Норвегия        31.76.5.8:443
nl  Нидерланды      94.156.154.147:443
```

Do not store or print SOCKS usernames, SOCKS passwords, SSH passwords, or generated private proxy secrets in this skill, logs, commits, or public source. Proxy credentials belong in the private build config, not in `settings.json` and not in public files.

## Expected Server Shape

Each server should use the same layout:

```text
external clients
-> 0.0.0.0:443
-> zapret-socks-stunnel.service
-> /usr/bin/stunnel4 /etc/stunnel/zapret-socks.conf
-> 127.0.0.1:1443
-> 3proxy.service
-> authenticated SOCKS5
```

`zapret-socks-stunnel.service` is the desired owner of external port `443`. It makes the TLS wrapper self-restarting and enabled after reboot. A bare `stunnel4` process with `stunnel4.service` shown as inactive may work for the moment, but it is not the durable target state.

## Server Checks

Start with live evidence. Check which process owns the public port:

```bash
ss -ltnp "( sport = :443 or sport = :1443 )"
systemctl is-active zapret-socks-stunnel 3proxy telemt1 telemt-self-tls-redirect nginx 2>/dev/null || true
```

Expected:

```text
443   -> stunnel4 from zapret-socks-stunnel.service
1443  -> 3proxy on 127.0.0.1
zapret-socks-stunnel: active
3proxy: active
telemt/nginx on 443: inactive
```

If `openssl s_client -connect <ip>:443` shows `CN=zapret-socks`, the TLS wrapper is probably the intended one. If it shows a public Let's Encrypt name like `*.sslip.io`, or if `ss` shows `telemt`, `nginx`, `caddy`, or another service on `443`, ZapretGUI is not reaching the bundled SOCKS endpoint.

## Common Failure

`Socks5Error: Upstream proxy bad SOCKS version: 72` usually means the client reached an HTTP/TLS web service instead of SOCKS5. Byte `72` is ASCII `H`, often the start of an HTTP response.

For these servers, first suspect port ownership on the server:

```text
wrong: 443 -> telemt/nginx/other HTTPS service
right: 443 -> stunnel4 -> 127.0.0.1:1443 -> 3proxy
```

Only blame ZapretGUI client code after proving that `443` is owned by `zapret-socks-stunnel` and a source-side SOCKS check still fails.

## Repair Pattern

Use the same self-healing unit on every bundled SOCKS server:

```ini
[Unit]
Description=Zapret SOCKS5 TLS wrapper
After=network-online.target 3proxy.service
Wants=network-online.target
Requires=3proxy.service

[Service]
Type=simple
ExecStart=/usr/bin/stunnel4 /etc/stunnel/zapret-socks.conf
Restart=always
RestartSec=2
LimitNOFILE=524288
TasksMax=infinity

[Install]
WantedBy=multi-user.target
```

Safe recovery shape:

```bash
systemctl stop zapret-socks-stunnel stunnel4 2>/dev/null || true
pkill -x stunnel4 2>/dev/null || true
systemctl restart 3proxy
systemctl daemon-reload
systemctl enable zapret-socks-stunnel
systemctl start zapret-socks-stunnel
```

If another service owns `443`, stop and disable that conflicting service only after confirming it is not the intended SOCKS wrapper. On the Norway server this was previously `telemt1`, `telemt-self-tls-redirect`, and `nginx`.

## App-Side Verification

From the repo, verify using the generated private runtime config without printing credentials:

```bash
PYTHONPATH=src python - <<'PY'
import asyncio
from telegram_proxy.config.upstream_catalog import UpstreamPresetResolver
from telegram_proxy.proxy.socks5 import connect_via_socks5

TARGETS = [("149.154.162.123", 80), ("149.154.167.41", 80), ("149.154.167.91", 80)]

async def check(pid):
    resolver = UpstreamPresetResolver.load_from_runtime()
    p = resolver.socks5_by_id(pid)
    results = []
    for host, port in TARGETS:
        try:
            reader, writer = await asyncio.wait_for(
                connect_via_socks5(
                    p["host"],
                    int(p["port"]),
                    host,
                    port,
                    username=p.get("username") or None,
                    password=p.get("password") or None,
                    tls=bool(p.get("tls")),
                    tls_server_name=str(p.get("tls_server_name") or ""),
                    tls_verify=bool(p.get("tls_verify")),
                ),
                timeout=12,
            )
            writer.close()
            await writer.wait_closed()
            results.append("OK")
        except Exception as exc:
            results.append(type(exc).__name__)
    print(pid, p["host"], "tls=", p.get("tls"), " ".join(results))

async def main():
    await asyncio.gather(*(check(pid) for pid in ("no", "uk", "nl")))

asyncio.run(main())
PY
```

Good result:

```text
no 31.76.5.8 tls= True OK OK OK
uk 144.31.213.169 tls= True OK OK OK
nl 94.156.154.147 tls= True OK OK OK
```

## ZapretGUI Source Truth

Bundled proxy list and generated credentials are private build data. Public code should resolve them through the existing runtime/catalog flow, not duplicate secrets.

Relevant public code paths:

```text
src/telegram_proxy/config/upstream_catalog.py
src/telegram_proxy/config/settings.py
src/telegram_proxy/proxy/socks5.py
src/telegram_proxy/proxy/routing.py
src/telegram_proxy/wss_proxy.py
```

Relevant private source of truth:

```text
/mnt/g/Privacy/zapretgui/private_zapretgui/build_zapret/build_local_config.py
PUBLIC_PROXY_PRESETS
```

When logs are needed, it is safe to log host, port, and `tls=yes/no`. Do not log usernames or passwords.
