"""Serve the static showcase and optional exact Python trace API."""

import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .trace import build_trace

STATIC = Path(__file__).with_name("site") / "dist"


class ShowcaseHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def respond(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/api/config":
            self.respond(200, {"engine": "python", "schema_version": 1})
        else:
            super().do_GET()

    def do_POST(self) -> None:
        if self.path != "/api/trace":
            self.respond(404, {"error": "Unknown endpoint."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384:
                raise ValueError("Trace requests must contain at most 16 KiB of JSON.")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Expected a JSON object.")
            result = build_trace(
                payload.get("sequence"),
                payload.get("strategy", "treap"),
                payload.get("seed", 2026),
            )
        except (ValueError, TypeError, UnicodeError) as error:
            self.respond(400, {"error": str(error)})
            return
        self.respond(200, result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--export", type=Path, help="write a portable JSON trace instead of serving"
    )
    parser.add_argument("--strategy", default="treap")
    parser.add_argument("--sequence", default="1,2,3,4,5,6,7,8,9,10,11,12")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    if args.export:
        from .trace import parse_sequence

        try:
            trace = build_trace(parse_sequence(args.sequence), args.strategy, args.seed)
        except ValueError as error:
            parser.error(str(error))
        args.export.parent.mkdir(parents=True, exist_ok=True)
        args.export.write_text(
            json.dumps(trace, separators=(",", ":")), encoding="utf-8"
        )
        print(f"Trace written to {args.export}")
        return
    with ThreadingHTTPServer(
        (args.host, args.port), partial(ShowcaseHandler)
    ) as server:
        print(f"Rotation Lab: http://{args.host}:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
