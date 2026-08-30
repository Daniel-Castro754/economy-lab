"""Desktop sidecar entry point for Economy Lab.

This module is bundled as a Tauri sidecar. It binds only to loopback and exposes
an authenticated shutdown hook so the desktop shell can stop the backend
cleanly before exiting.
"""

from __future__ import annotations

import argparse
import os

import uvicorn

from economy_lab.main import app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Economy Lab local desktop backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--log-level", default="warning")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("Desktop backend must bind to loopback only")
    if not 1 <= args.port <= 65535:
        raise SystemExit("Invalid TCP port")

    os.environ.setdefault("ECONOMY_LAB_RUNTIME_MODE", "desktop-sidecar")

    config = uvicorn.Config(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        access_log=False,
        server_header=False,
        date_header=False,
    )
    server = uvicorn.Server(config)

    # The API route calls this callback after authenticating the shutdown token.
    app.state.request_desktop_shutdown = lambda: setattr(server, "should_exit", True)
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
