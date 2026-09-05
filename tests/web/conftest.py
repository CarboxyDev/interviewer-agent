"""V2-008 browser checks, separate from Python/runtime validation."""

from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from threading import Thread

import pytest
from playwright.sync_api import Page, sync_playwright

from web.serve import WebPreviewHandler


@pytest.fixture(scope="session")
def prototype_url() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), WebPreviewHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture
def page(prototype_url: str) -> Iterator[Page]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context()
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(prototype_url)
        yield page
        browser.close()
        assert not errors
