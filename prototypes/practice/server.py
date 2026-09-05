"""V2-008: serve only the public flow study and its one synthetic audio fixture."""

import argparse
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
ASSETS = {
    "/scenarios.js": (ROOT / "prototypes/practice/scenarios.js", "text/javascript; charset=utf-8"),
    "/": (ROOT / "prototypes/practice/index.html", "text/html; charset=utf-8"),
    "/index.html": (ROOT / "prototypes/practice/index.html", "text/html; charset=utf-8"),
    "/practice.css": (ROOT / "prototypes/practice/practice.css", "text/css; charset=utf-8"),
    "/practice.js": (ROOT / "prototypes/practice/practice.js", "text/javascript; charset=utf-8"),
    "/sample-answer.wav": (ROOT / "benchmarks/fixtures/v1/audio/answer.wav", "audio/wav"),
}


class PrototypeHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self._respond(body=True)

    def do_HEAD(self) -> None:
        self._respond(body=False)

    def _respond(self, *, body: bool) -> None:
        asset = ASSETS.get(urlsplit(self.path).path)
        if asset is None:
            self.send_error(404)
            return
        path, content_type = asset
        content = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Permissions-Policy", "microphone=(), camera=(), geolocation=()")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body:
            self.wfile.write(content)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", args.port), PrototypeHandler) as server:
        print(f"Synthetic practice prototype: http://127.0.0.1:{server.server_port}")  # noqa: T201
        with suppress(KeyboardInterrupt):
            server.serve_forever()


if __name__ == "__main__":
    main()
