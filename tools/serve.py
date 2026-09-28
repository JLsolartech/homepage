"""Minimal local static server for previewing docs/ (isolated, localhost only).

Usage: python tools/serve.py [--root docs] [--port 4173]
Binds to 127.0.0.1 only; never exposes the preview publicly.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import mimetypes
from pathlib import Path

mimetypes.add_type("image/avif", ".avif")
mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("text/javascript", ".js")


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".avif": "image/avif", ".webp": "image/webp", ".js": "text/javascript"}

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format: str, *args) -> None:  # keep test output quiet
        pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1] / "docs"))
    parser.add_argument("--port", type=int, default=4173)
    args = parser.parse_args()
    handler = functools.partial(Handler, directory=args.root)
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        print(f"Serving {args.root} at http://127.0.0.1:{args.port}/", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
