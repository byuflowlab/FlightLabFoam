"""``flightlabfoam`` / ``python -m flightlabfoam``: start the app and open it in a browser."""

from __future__ import annotations

import argparse
import socket
import threading
import webbrowser

from . import __version__

DEFAULT_PORT = 5150  # not 5000, which macOS AirPlay Receiver holds


def _free_port(preferred: int) -> int:
    """``preferred`` if nothing is listening on it, otherwise any free port."""
    for port in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    raise RuntimeError("could not find a free port")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="flightlabfoam", description="Hot-wire foam cutter G-code generator")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port to serve on (default {DEFAULT_PORT})")
    parser.add_argument("--no-open", action="store_true", help="do not open a browser window")
    parser.add_argument("--settings", help="settings file (default: settings.yaml in the repository)")
    parser.add_argument("--version", action="version", version=f"flightlabfoam {__version__}")
    args = parser.parse_args(argv)

    from .app import create_app

    app = create_app(args.settings)
    port = _free_port(args.port)
    url = f"http://127.0.0.1:{port}/"
    print(f"FlightLabFoam {__version__} is running at {url}")
    print("Keep this window open while you use the app. Press Ctrl-C to stop.")
    if not args.no_open:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    # 127.0.0.1 only: the app has no authentication and must not be reachable from the network
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
