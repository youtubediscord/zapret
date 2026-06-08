# telegram_proxy/__main__.py
"""CLI entry point for standalone/service mode.

Usage:
    python -m telegram_proxy --port 1353 --mode socks5
    python -m telegram_proxy --port 1443 --mode mtproxy --secret HEX_SECRET
    python -m telegram_proxy --mode mtproxy --dc-ip 2:149.154.167.220
    python -m telegram_proxy --port 1353
"""

import argparse
import asyncio
import logging
import signal
import sys

from telegram_proxy.wss_proxy import TelegramWSProxy
from telegram_proxy.proxy.dc_map import parse_dc_endpoint_overrides


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Telegram WebSocket Proxy — bypass IP blocking",
    )
    parser.add_argument(
        "--port", type=int, default=1353,
        help="Listen port (default: 1353)",
    )
    parser.add_argument(
        "--mode", choices=["socks5", "mtproxy"], default="socks5",
        help="Proxy mode (default: socks5)",
    )
    parser.add_argument(
        "--secret", default="",
        help="MTProxy secret: 32 hex characters",
    )
    parser.add_argument(
        "--dc-ip",
        action="append",
        default=[],
        help="MTProxy target IP for a DC, for example: --dc-ip 2:149.154.167.220",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable debug logging",
    )
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    proxy = TelegramWSProxy(
        port=args.port,
        mode=args.mode,
        mtproxy_secret=args.secret,
        dc_endpoint_overrides=parse_dc_endpoint_overrides(args.dc_ip),
        on_log=lambda msg: print(f"[TG-PROXY] {msg}"),
    )

    async def run():
        await proxy.start()

        # Handle graceful shutdown
        stop_event = asyncio.Event()

        def on_signal():
            stop_event.set()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, on_signal)
            except NotImplementedError:
                # Windows doesn't support add_signal_handler
                pass

        # On Windows, use Ctrl+C via KeyboardInterrupt
        try:
            await stop_event.wait()
        except (KeyboardInterrupt, SystemExit):
            pass

        await proxy.stop()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
