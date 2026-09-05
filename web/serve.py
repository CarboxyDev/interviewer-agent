"""V2-010: restricted loopback preview of the production web bundle, without API access."""

import argparse
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "web/dist"
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
}


class WebPreviewHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self._respond(body=True)

    def do_HEAD(self) -> None:
        self._respond(body=False)

    def _respond(self, *, body: bool) -> None:
        route = urlsplit(self.path).path
        if route == "/sample-answer.wav":
            path = ROOT / "benchmarks/fixtures/v1/audio/answer.wav"
            content_type = "audio/wav"
        else:
            # Only named build outputs, no repository files, source maps or SPA fallback.
            assets = {
                "/": DIST / "index.html",
                "/index.html": DIST / "index.html",
                "/theme-init.js": DIST / "theme-init.js",
            }
            assets.update(
                {
                    "/assets/" + item.name: item
                    for item in (DIST / "assets").glob("*")
                    if item.is_file() and item.suffix in {".css", ".js"}
                }
            )
            candidate = assets.get(route)
            if candidate is None or not candidate.is_file():
                self.send_error(404)
                return
            path = candidate
            content_type = CONTENT_TYPES[path.suffix]
        content = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Permissions-Policy", "microphone=(), camera=(), geolocation=()")
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self'; media-src 'self' blob:; connect-src 'none'; object-src 'none'; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        if body:
            self.wfile.write(content)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not (DIST / "index.html").is_file():
        parser.error("Build the web app first: npm --prefix web run build")
    with ThreadingHTTPServer(("127.0.0.1", args.port), WebPreviewHandler) as server:
        print(f"Practice Room: http://127.0.0.1:{server.server_port}")  # noqa: T201
        with suppress(KeyboardInterrupt):
            server.serve_forever()


if __name__ == "__main__":
    main()
